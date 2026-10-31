import copy
import json
import tempfile
import unittest
from pathlib import Path
from aiwar.engine import allocate
from tests.legacy_world import LegacyWorld as World
from aiwar.policies import decision_cycle

class Rules(unittest.TestCase):
    def world(self):
        return World(7,{'bandit_cap':0,'days':1680})

    def party(self,w,n=0):
        return next(u for u in w.units.values() if u['kind']=='party' and u['nation']==n)

    def test_population_rebuild_no_double_charge(self):
        w=self.world();v=w.villages['v000']
        self.assertEqual(v['population'],180)
        w.remove(v['cart'],'defeated')
        self.assertEqual(v['population'],180)
        w.hour=24;w.daily()
        self.assertEqual(v['population'],161)
        self.assertEqual(w.units[v['cart']]['healthy'],20)
        w.remove(v['cart']);v['population']=18
        w.hour=48;w.daily();self.assertIsNone(v['cart'])
        w.hour=72;w.daily();self.assertIsNotNone(v['cart']);self.assertEqual(v['population'],0)

    def test_weekly_recruits_are_actual_cargo(self):
        w=self.world();v=w.villages['v000'];c=w.cities[v['city']]
        v['population']=199
        w.hour=168;w.weekly();u=w.units[v['cart']]
        self.assertEqual(u['cargo_recruits'],1)
        self.assertEqual(u['cargo_food'],199000)
        self.assertEqual(c['recruits'],0)
        w.remove(u['id'],'defeated')
        self.assertEqual(c['recruits'],0)
        self.assertEqual(v['population'],199)

    def test_weekly_under_100_no_recruits(self):
        w=self.world();v=w.villages['v000'];v['population']=99
        w.weekly();self.assertEqual(w.units[v['cart']]['cargo_recruits'],0)

    def test_cart_returns_same_people(self):
        w=self.world();v=w.villages['v000'];uid=v['cart'];c=w.cities[v['city']]
        w.hour=168;w.weekly();u=w.units[uid]
        u.update(x=c['x'],y=c['y'],path=[])
        w.arrivals();self.assertEqual(c['recruits'],1)
        self.assertEqual(u['phase'],'return')
        u.update(x=v['x'],y=v['y'],path=[])
        w.arrivals();self.assertEqual(v['cart'],uid);self.assertEqual(v['population'],180)

    def test_hunger_ceil_partial_same_as_zero(self):
        for food in (0,2299):
            w=self.world();u=self.party(w);u.update(healthy=23,food=food,x=50000,y=40000)
            w.eat([u],100)
            self.assertEqual(u['healthy'],20)
            self.assertEqual(u['food'],0)
        w=self.world();u=self.party(w);u.update(healthy=23,food=2300)
        w.eat([u],100);self.assertEqual(u['healthy'],23)

    def test_city_shares_food_including_party_bags(self):
        w=self.world();c=w.cities['c00'];g=w.units[c['garrison']];u=self.party(w)
        c['food']=0;u['food']=4000
        w.eat([u,g],50,c)
        self.assertEqual(g['healthy'],50);self.assertEqual(u['healthy'],30)
        self.assertEqual(u['food'],0)

    def test_raid_timing_and_disabled_production(self):
        w=self.world();u=self.party(w);v=w.villages['v100']
        u.update(x=v['x'],y=v['y'],order={'type':'raid','target':v['id']},path=[])
        w.raids();w.hour=23;w.raids();self.assertEqual(v['population'],180)
        w.hour=24;w.raids();self.assertEqual(v['population'],108)
        self.assertEqual(v['disabled_until'],192)
        w.daily();self.assertEqual(v['population'],108)
        w.hour=168;w.weekly();self.assertEqual(v['food'],0)
        w.hour=192;w.daily();self.assertEqual(v['population'],109)

    def test_battle_prepare_reinforcement_and_loss_split(self):
        w=self.world();a=self.party(w);b=self.party(w,1)
        a.update(x=60000,y=40000,healthy=150);b.update(x=60000,y=40000,healthy=150)
        w.start_battle(a,b);battle=w.battles[a['battle']]
        w.hour=23;w.battle_tick();self.assertEqual(a['healthy'],150)
        w.hour=24;w.battle_tick();self.assertEqual(a['healthy'],144)
        self.assertEqual(a['wounded'],5);self.assertEqual(w.stats['war_dead'],2)
        ally=w.new_unit('party',0,1,100,60000,40000)
        w.contacts({});self.assertEqual(ally['battle'],battle['id']);self.assertEqual(battle['start'],0)
        self.assertEqual(battle['days'],1)
        for h in range(25,60): w.hour=h;w.battle_tick()
        self.assertNotIn(b['id'],w.units)
        self.assertIn(a['id'],w.units)

    def test_mutual_destruction(self):
        w=self.world();a=self.party(w);b=self.party(w,1)
        a.update(x=60000,y=40000,healthy=30);b.update(x=60000,y=40000,healthy=30)
        w.start_battle(a,b)
        for h in range(24,48):w.hour=h;w.battle_tick()
        self.assertNotIn(a['id'],w.units);self.assertNotIn(b['id'],w.units)
        self.assertFalse(w.battles)

    def test_empty_city_capture_has_delay(self):
        w=self.world();a=self.party(w);c=w.cities['c11'];g=w.units[c['garrison']]
        # Move the initial defending party away; other entities remain outside contact.
        for u in w.units.values():
            if u['kind']=='party' and u['nation']==1:u.update(x=100000,y=50000)
        g.update(healthy=0);w.units[c['militia']]['healthy']=0;a.update(x=c['x'],y=c['y'])
        w.start_battle(a,g,c['id']);w.hour=71;w.battle_tick();self.assertEqual(c['nation'],1)
        w.hour=72;w.battle_tick();self.assertEqual(c['nation'],0)
        self.assertEqual(g['healthy'],0)
        self.assertEqual(w.villages['v110']['nation'],0)

    def test_siege_defender_power_is_double(self):
        w=self.world();a=self.party(w);c=w.cities['c11'];g=w.units[c['garrison']]
        a.update(x=c['x'],y=c['y'])
        w.start_battle(a,g,c['id']);b=w.battles[a['battle']]
        self.assertEqual(b['power'][g['id']],200)
        self.assertEqual(b['power'][a['id']],60)

    def test_fog_no_inventory_leak_and_no_hidden_target(self):
        w=self.world();obs=w.observe(0)
        c=next(c for c in obs['cities'] if c['id']=='c10')
        self.assertNotIn('food',c);self.assertNotIn('healthy',c)
        enemy=self.party(w,1)
        self.assertNotIn(enemy['id'],[u['id'] for u in obs['units']])
        a=self.party(w)
        bad=w.command(0,{'type':'attack','unit':a['id'],'target':enemy['id']})
        self.assertFalse(bad['ok'])
        a.update(x=enemy['x'],y=enemy['y']);w.update_known();obs=w.observe(0)
        seen=next(u for u in obs['units'] if u['id']==enemy['id'])
        self.assertNotIn('food',seen);self.assertNotIn('order',seen)
        seen['healthy']=0;self.assertEqual(enemy['healthy'],30)

    def test_save_reload_replay_exact(self):
        w=self.world()
        for _ in range(220):
            if w.hour%6==0:decision_cycle(w)
            w.step()
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'state.json';w.save(path);v=World.load(path)
            self.assertEqual(w.digest(),v.digest())
            for _ in range(100):
                for x in (w,v):
                    if x.hour%6==0:decision_cycle(x)
                    x.step()
            self.assertEqual(w.digest(),v.digest())

    def test_commands_replay(self):
        w=self.world()
        for _ in range(200):
            if w.hour%6==0:decision_cycle(w)
            w.step()
        v=World(w.seed,w.cfg)
        for hour in range(w.hour):
            for item in w.commands:
                if item['hour']==hour:v.command(item['nation'],item['command'])
            v.step()
        self.assertEqual(w.digest(),v.digest())

    def test_dispatch_real_garrison_and_capacity(self):
        w=self.world();c=w.cities['c00'];g=w.units[c['garrison']]
        result=w.command(0,{'type':'dispatch','city':c['id'],'destination':'c01','food':100000})
        self.assertTrue(result['ok']);u=w.units[result['unit']]
        self.assertEqual(g['healthy'],30);self.assertEqual(c['food'],140000)
        self.assertEqual(u['food']+u['cargo_food'],160000)
        self.assertFalse(w.command(0,{'type':'dispatch','city':c['id'],'destination':'c01'})['ok'])
        self.assertFalse(w.command(0,{'type':'dispatch','city':'c02','destination':'c10'})['ok'])

    def test_army_hunger_rounds_once(self):
        w=self.world();a=self.party(w);a.update(healthy=1,food=0)
        b=w.new_unit('party',0,1,1,a['x'],a['y'])
        r=w.command(0,{'type':'assemble','unit':a['id'],'units':[b['id']]})
        self.assertTrue(r['ok']);w.eat([a,b],100)
        self.assertEqual(w.stats['starved'],1)
        self.assertEqual(sum(w.size(u) for u in w.units.values() if u.get('army')==r['army']),1)

    def test_recruit_cap_and_no_population_deduction(self):
        w=self.world();c=w.cities['c00'];c['recruits']=1000
        a=self.party(w);p=w.villages['v000']['population']
        self.assertTrue(w.command(0,{'type':'recruit','city':c['id'],'unit':a['id'],'count':120})['ok'])
        self.assertFalse(w.command(0,{'type':'recruit','city':c['id'],'unit':a['id'],'count':1})['ok'])
        self.assertEqual(w.villages['v000']['population'],p)

    def test_recovery_only_after_battle_and_fed(self):
        w=self.world();a=self.party(w);a.update(wounded=11,last_battle=24,food=50000)
        w.hour=47;w.daily();self.assertEqual(a['wounded'],11)
        w.hour=48;w.daily();self.assertEqual(a['wounded'],9)

    def test_swept_contact_catches_crossing(self):
        a={'id':'a','x':2000,'y':0};b={'id':'b','x':0,'y':0}
        self.assertTrue(World.swept(a,b,{'a':(0,0),'b':(2000,0)}))

    def test_unification_and_tie(self):
        w=self.world()
        for c in w.cities.values(): c['nation']=0
        w.finish();self.assertEqual(w.result['winner'],0)
        w=self.world();w.hour=1680*24;w.finish();self.assertIsNone(w.result['winner'])

    def test_largest_remainder(self):
        self.assertEqual(sum(allocate(7,{'a':3,'b':12}).values()),7)
        self.assertEqual(allocate(1,{'a':1,'b':1}),{'a':1,'b':0})

if __name__=='__main__':unittest.main()
