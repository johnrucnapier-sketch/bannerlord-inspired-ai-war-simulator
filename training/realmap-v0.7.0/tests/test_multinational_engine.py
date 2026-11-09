import copy
import tempfile
import unittest
from pathlib import Path
from aiwar.engine import World
from aiwar import military
from aiwar.replay import replay


class MultinationalEngine(unittest.TestCase):
    def world(self, **config):
        return World(9271,dict(mode='realmap',bandit_cap=0,auto_city_service=False,frontier_only=False,**config))

    def parties(self,w,nations=(0,1,2),sizes=(100,100,100)):
        for u in w.units.values():
            if u['kind']=='party':u['healthy']=0
        spot=next(iter(w.cities.values()))
        out=[]
        for n,size in zip(nations,sizes):
            u=next(u for u in w.units.values() if u['nation']==n and u['kind']=='party')
            u.update(x=spot['x'],y=spot['y'],healthy=size,wounded=0,food=1000000,order=None)
            out.append(u)
        return out

    def test_registry_sources_and_country_control(self):
        w=self.world()
        self.assertEqual((len(w.cities),len(w.villages),len(w.map_clans)),(120,273,73))
        self.assertEqual(w.nation_ids(),tuple(range(8)))
        for n in w.nation_ids():
            u=next(u for u in w.units.values() if u['kind']=='party' and u['nation']==n)
            self.assertTrue(w.command(n,dict(type='stop',unit=u['id']))['ok'])
            self.assertFalse(w.command((n+1)%8,dict(type='stop',unit=u['id']))['ok'])
        self.assertFalse(w.command(True,dict(type='stop',unit=u['id']))['ok'])
        w.check()

    def test_fog_counterfactual_all_eight_and_no_reference_leak(self):
        w=self.world()
        for n in w.nation_ids():
            before=w.observe(n)
            hidden=next(u for u in w.units.values() if u['nation']!=n and not w.visible(n,u) and u['kind']=='party')
            saved=copy.deepcopy(hidden)
            hidden.update(food=hidden['food']+123,healthy=149,order={'type':'move','x':0,'y':0})
            self.assertEqual(before,w.observe(n))
            self.assertFalse(w.command(n,dict(type='attack',unit=next(u['id'] for u in w.units.values() if u['kind']=='party' and u['nation']==n),target=hidden['id']),record=False)['ok'])
            hidden.clear();hidden.update(saved)
            before['nations']['0']['name']='tampered'
            self.assertNotEqual(w.nations['0']['name'],'tampered')
            self.assertNotIn('observer_totals',before)
            self.assertEqual(before['events'],[])

    def test_hidden_capture_stays_stale_in_frontier_intelligence(self):
        w=self.world();n=0
        hidden=next(c for c in w.cities.values() if c['nation']!=n and not w.visible(n,c))
        old=w.known[str(n)][hidden['id']]['nation']
        hidden['nation']=7 if old!=7 else 6
        w.update_known()
        seen=next(c for c in w.observe(n)['cities'] if c['id']==hidden['id'])
        self.assertEqual(seen['nation'],old);self.assertTrue(seen['stale'])

    def test_former_owned_stale_city_does_not_leak_new_culture(self):
        w=self.world();n=0;w.hour=1
        hidden=next(c for c in w.cities.values() if c['nation']!=n and not w.visible(n,c))
        w.known[str(n)][hidden['id']]['nation']=n # Last seen before an unseen loss.
        hidden['nation']=4
        before=w.observe(n)
        stale=next(c for c in before['cities'] if c['id']==hidden['id'])
        self.assertTrue(stale['stale']);self.assertEqual(stale['nation'],n)
        self.assertNotIn('militia_cap',stale);self.assertNotIn('cavalry_training_period',stale)
        hidden['nation']=3
        self.assertEqual(before,w.observe(n))

    def test_three_nations_are_three_hostile_sides(self):
        w=self.world();a,b,c=self.parties(w)
        bid=w.start_battle(a,b);battle=w.battles[bid]
        self.assertEqual(set(battle['sides']),{'0','1','2'})
        w.hour=battle['prepare_hours'];w.battle_tick()
        self.assertIn(bid,w.battles)
        self.assertTrue(all(u['healthy']<100 for u in (a,b,c)))
        w.check()

    def test_late_third_party_joins_and_no_damage_overkill(self):
        w=self.world();a,b,c=self.parties(w,sizes=(150,1,150));c['x']+=10000
        bid=w.start_battle(a,b);battle=w.battles[bid]
        c.update(x=a['x'],y=a['y']);w.start_battle(c,a)
        self.assertEqual(c['battle'],bid)
        battle['combat_hours']=1
        battle['power']={a['id']:4,b['id']:0,c['id']:4}
        battle['pair_remainders']={'0:1':[99,100],'2:1':[99,100]}
        w.hour=battle['prepare_hours'];w.battle_tick()
        self.assertGreaterEqual(b['healthy'],0)
        self.assertEqual(len([n for n,ids in battle['sides'].items() if any(w.units.get(i,{}).get('healthy',0)>0 for i in ids)]),2)
        self.assertIn(bid,w.battles);w.check()

    def test_multiple_besiegers_detach_and_third_party_can_resume(self):
        w=self.world();a,r,t=self.parties(w,sizes=(5,10,150))
        city=next(c for c in w.cities.values() if c['nation']==1)
        for u in (a,t):u.update(x=city['x'],y=city['y'])
        r.update(x=city['x']+5000,y=city['y'])
        bid=w.start_battle(a,w.units[city['garrison']],city['id']);parent=w.battles[bid]
        self.assertIn(t['id'],parent['sides']['2'])
        r.update(x=city['x'],y=city['y'])
        child_id=w.start_relief_battle(r,parent);child=w.battles[child_id]
        self.assertEqual(set(child['sides']),{'0','1','2'})
        self.assertEqual(parent['sides']['0'],[]);self.assertEqual(parent['sides']['2'],[])
        self.assertNotIn(city['garrison'],[uid for ids in child['sides'].values() for uid in ids])
        for hour in range(child['prepare_hours'],1000):
            w.hour=hour;w.battle_tick()
            if child_id not in w.battles:break
        self.assertIn(bid,w.battles)
        self.assertEqual(t['battle'],bid);self.assertEqual(city['nation'],1)
        w.check()

    def test_bandits_cannot_capture_or_join_national_siege(self):
        w=self.world();a,b,c=self.parties(w)
        city=next(c for c in w.cities.values() if c['nation']==1)
        a.update(x=city['x'],y=city['y'])
        bandit=w.new_unit('bandit',-1,-1,20,a['x'],a['y'])
        bid=w.start_battle(a,w.units[city['garrison']],city['id'])
        self.assertNotIn('-1',w.battles[bid]['sides']);self.assertIsNone(bandit['battle'])

    def test_rejected_idle_cart_leaves_no_phantom_battle_side(self):
        w=self.world();cart=next(u for u in w.units.values() if u['nation']==1 and u['kind']=='village_cart')
        a=next(u for u in w.units.values() if u['nation']==0 and u['kind']=='party')
        a.update(x=cart['x'],y=cart['y'])
        bandit=w.new_unit('bandit',-1,-1,20,cart['x'],cart['y'])
        w.units={u['id']:u for u in (cart,a,bandit)}
        bid=w.start_battle(a,bandit);b=w.battles[bid]
        self.assertIsNone(cart['battle']);self.assertNotIn('1',b['sides'])
        self.assertEqual((b['kind'],b['prepare_hours']),('skirmish',2))

    def test_real_culture_hooks_training_capacity_rations(self):
        w=self.world()
        bat=next(c for c in w.cities.values() if c['nation']==4)
        w.units[bat['militia']]['healthy']=249;w.hour=24;w.daily()
        self.assertEqual(w.units[bat['militia']]['healthy'],250)
        empire=next(c for c in w.cities.values() if c['nation']==0)
        g=w.units[empire['garrison']];g.update(healthy=100,wounded=0);empire['food']=100000
        w.eat([g],50,empire);self.assertEqual(empire['food'],95500)
        kh=next(c for c in w.cities.values() if c['nation']==3 and c['settlement_type']=='castle')
        other=next(c for c in w.cities.values() if c['nation']==0 and c['settlement_type']=='castle')
        kh['training_hours']=143;other['training_hours']=143;military.train(w)
        self.assertEqual(w.units[kh['garrison']]['cavalry'],1)
        self.assertEqual(w.units[other['garrison']]['cavalry'],0)
        w.check()

    def test_save_load_replay_and_culture_remainder(self):
        w=self.world(days=1)
        v=next(v for v in w.villages.values() if v['nation']==5 and w.cities[v['city']]['settlement_type']=='castle')
        v['culture_recruit_remainder']=7
        # Save/load serializes new registries, relations, cohort origins and fractional yields.
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'save.json';w.save(path);loaded=World.load(path)
            self.assertEqual(w.digest(),loaded.digest())
            w.step(3);loaded.step(3)
            self.assertEqual(w.physics_digest(),loaded.physics_digest())

    def test_terminal_tie_and_selectable_two_country_scenario(self):
        w=self.world(nations=['battania','vlandia'],days=1)
        self.assertEqual(w.nation_ids(),(0,1));self.assertEqual(len(w.cities),29)
        # Deliberately tied scoreboard: unknown city owner is not allowed in actual scenarios.
        for i,c in enumerate(w.cities.values()):c['nation']=i%2
        w.cities.pop(next(iter(w.cities)))
        w.hour=24;w.finish()
        self.assertIsNone(w.result['winner']);self.assertEqual(w.result['tied_leaders'],[0,1])


if __name__=='__main__':unittest.main()
