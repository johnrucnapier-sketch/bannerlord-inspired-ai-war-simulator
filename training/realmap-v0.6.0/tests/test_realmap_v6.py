import copy
import tempfile
import unittest
from pathlib import Path
from aiwar.engine import World
from aiwar import military, realmap_rules as rules
from aiwar.replay import replay
from aiwar.sdk import command_error


class RealmapV6(unittest.TestCase):
    def world(self):return World(7,{'mode':'realmap','auto_city_service':False,'bandit_cap':0})
    def pair(self,w):
        return next((c,w.cities[i]) for c in w.cities.values() for i in c['supply_neighbors'] if c['nation']==w.cities[i]['nation'])
    def dispatch(self,w,c,d,**kw):
        result=w.command(c['nation'],dict(type='dispatch',city=c['id'],destination=d['id'],**kw))
        self.assertTrue(result['ok'],result)
        return w.units[result['unit']]
    def at(self,u,target):u.update(x=target['x'],y=target['y'],path=[])
    def stocks(self,w):return sum(c['food'] for c in w.cities.values())+sum(u['food']+u['cargo_food'] for u in w.units.values())
    def men(self,w):return sum(w.size(u) for u in w.units.values())

    def test_mixed_load_has_full_2000_and_separate_210_rations(self):
        w=self.world();c,d=self.pair(w);c['food']=3000000
        g=w.units[c['garrison']];g['cavalry']=20
        men=self.men(w);food=self.stocks(w)
        u=self.dispatch(w,c,d,troops=20,troop_type='cavalry',food=2000000)
        self.assertEqual((u['healthy'],u['regular_healthy'],u['cavalry']),(70,20,20))
        self.assertEqual((u['cargo_food'],u['food']),(2000000,210000))
        self.assertEqual(g['healthy'],30)
        self.assertEqual(military.away_militia(w,c),50)
        self.assertEqual(self.men(w),men);self.assertEqual(self.stocks(w),food);w.check()
        self.at(u,d);military.arrival(w,u)
        self.assertEqual(w.units[d['garrison']]['cavalry'],20)
        self.assertEqual((u['healthy'],u['regular_healthy'],u['cavalry']),(50,0,0))
        self.at(u,c);military.arrival(w,u)
        self.assertNotIn(u['id'],w.units);self.assertEqual(self.men(w),men);self.assertEqual(self.stocks(w),food);w.check()

    def test_transport_may_empty_garrison_and_failures_are_atomic(self):
        w=self.world();c,d=self.pair(w);w.units[c['garrison']]['healthy']=20;c['food']=1000000
        before=copy.deepcopy(w.units)
        self.assertFalse(w.command(c['nation'],dict(type='dispatch',city=c['id'],destination=d['id'],troops=21))['ok'])
        self.assertEqual(w.units,before)
        self.dispatch(w,c,d,troops=20,food=0)
        self.assertEqual(w.units[c['garrison']]['healthy'],0)
        self.assertIsNone(command_error(dict(type='dispatch',city=c['id'],destination=d['id'],troops=20)))
        self.assertIsNotNone(command_error(dict(type='dispatch',city=c['id'],destination=d['id'],troops=True)))

    def test_mixed_combat_power_and_casualty_healing_cohorts(self):
        w=self.world();c,d=self.pair(w);c['food']=1000000;w.units[c['garrison']]['cavalry']=20
        u=self.dispatch(w,c,d,troops=20,troop_type='cavalry',food=0)
        b=dict(id='test',city=None,sides={str(c['nation']):[],str(1-c['nation']):[]},power={},kind='field',defender=1-c['nation'])
        b.update(x=u['x'],y=u['y']);w.battles['test']=b;w.join(b,u,forced=True)
        self.assertEqual(b['power'][u['id']],90)  # 50 militia + 20 regular x2
        military.casualties(u,14,3);u['healthy']-=14;u['wounded']+=11
        self.assertEqual(u['regular_healthy'],16)
        self.assertEqual(u['regular_wounded'],3)
        military.heal(u,11);u['healthy']+=11;u['wounded']-=11
        self.assertEqual((u['regular_healthy'],u['regular_wounded'],u['cavalry']),(19,0,19))
        w.eat([u],1000000)
        self.assertLessEqual(u['cavalry'],u['regular_healthy']);w.check()

    def test_full_destination_returns_troops_without_turning_them_into_militia(self):
        w=self.world();c,d=self.pair(w);c['food']=1000000
        w.units[d['garrison']]['healthy']=500
        u=self.dispatch(w,c,d,troops=20,food=0)
        self.at(u,d);military.arrival(w,u);self.assertEqual(u['regular_healthy'],20)
        self.at(u,c);military.arrival(w,u)
        self.assertEqual(w.units[c['garrison']]['healthy'],50)
        self.assertEqual(w.units[c['militia']]['healthy'],100);w.check()

    def target(self,w,c):
        p=next(u for u in w.units.values() if u['kind']=='party' and u['nation']==c['nation'])
        self.at(p,c);p['food']=0
        return p
    def block(self,w,p,city=None):
        w.battles['test']=dict(id='test',city=city,defender=1-p['nation'],start=w.hour,prepare_hours=72,sides={str(p['nation']):[p['id']],str(1-p['nation']):[]},power={})
        p['battle']='test'

    def test_supply_target_allowed_during_field_and_waits_then_delivers(self):
        w=self.world();c,d=self.pair(w);p=self.target(w,c);self.block(w,p)
        u=self.dispatch(w,c,p,mission='supply',food=100000)
        self.assertEqual(u['phase'],'waiting_supply');self.assertEqual(p['food'],0)
        military.arrival(w,u);self.assertEqual(p['food'],0)
        w.join(w.battles['test'],u);self.assertIsNone(u['battle'])
        p['battle']=None;del w.battles['test'];military.resume(w,u);military.arrival(w,u)
        self.assertEqual(p['food'],90000);self.assertEqual(u['cargo_food'],10000);self.assertEqual(u['phase'],'return')

    def test_siege_preparation_allowed_assault_and_pause_blocked(self):
        w=self.world();c,d=self.pair(w);p=self.target(w,c);self.block(w,p,d['id'])
        self.assertTrue(rules.can_supply(w,p))
        w.hour=72;self.assertFalse(rules.can_supply(w,p))
        w.battles['test'].update(assault_started=True,paused_hours=100)
        self.assertFalse(rules.can_supply(w,p))
        w.battles['test'].pop('assault_started');w.hour=0;w.battles['test']['relief_battle']='child'
        self.assertFalse(rules.can_supply(w,p))

    def test_supply_target_destroyed_returns_with_cargo(self):
        w=self.world();c,d=self.pair(w);p=self.target(w,c)
        u=self.dispatch(w,c,p,mission='supply',food=100000);w.remove(p['id'],'defeated')
        military.resume(w,u);self.assertEqual(u['phase'],'return');self.assertEqual(u['cargo_food'],100000)

    def test_army_leader_loss_does_not_cancel_surviving_army_supply(self):
        w=self.world();c,d=self.pair(w);p=self.target(w,c)
        q=next(u for u in w.units.values() if u['kind']=='party' and u['nation']==p['nation'] and u!=p);self.at(q,p)
        r=w.command(p['nation'],dict(type='assemble',unit=p['id'],units=[q['id']]))
        self.assertTrue(r['ok']);u=self.dispatch(w,c,p,mission='supply',food=100000)
        w.remove(p['id'],'defeated');military.resume(w,u)
        self.assertEqual(u['phase'],'outbound');self.assertEqual(u['supply_target'],q['id'])

    def test_two_convoys_never_overfill_target(self):
        w=self.world();c,d=self.pair(w);p=self.target(w,c);c['food']=d['food']=1000000
        a=self.dispatch(w,c,p,mission='supply',food=100000)
        b=self.dispatch(w,d,p,mission='supply',food=100000)
        for u in (a,b):self.at(u,p);military.arrival(w,u)
        self.assertEqual(p['food'],w.food_cap(p));self.assertEqual(a['cargo_food']+b['cargo_food'],110000)

    def test_assemble_only_expands_cap_disband_discards_and_discard_command(self):
        w=self.world();c,d=self.pair(w);p=self.target(w,c)
        q=next(u for u in w.units.values() if u['kind']=='party' and u['nation']==p['nation'] and u!=p);self.at(q,p)
        p['food']=q['food']=90000
        self.assertTrue(w.command(p['nation'],dict(type='assemble',unit=p['id'],units=[q['id']]))['ok'])
        self.assertEqual(p['food']+q['food'],180000);self.assertEqual(w.food_cap(p),180000)
        p['food']=q['food']=180000
        self.assertTrue(w.command(p['nation'],dict(type='discard',unit=p['id'],food=10000))['ok'])
        before=w.stats['food_lost']
        self.assertTrue(w.command(p['nation'],dict(type='disband',unit=p['id']))['ok'])
        self.assertEqual(p['food']+q['food'],180000);self.assertEqual(w.stats['food_lost']-before,170000)

    def test_loot_at_battle_end_is_once_capped_and_removed_from_loser(self):
        w=self.world();c,d=self.pair(w);p=self.target(w,c)
        enemy=w.new_unit('village_cart',1-p['nation'],0,0,c['x'],c['y'],food=10000)
        enemy.update(cargo_food=200000,wounded=10,home=next(iter(w.villages)))
        w.units={p['id']:p,enemy['id']:enemy};p['battle']=enemy['battle']='b'
        b=dict(id='b',city=None,x=p['x'],y=p['y'],start=0,prepare_hours=0,combat_hours=24,sides={str(p['nation']):[p['id']],str(enemy['nation']):[enemy['id']]},power={},remainders={str(p['nation']):[0,1],str(enemy['nation']):[0,1]})
        w.battles={'b':b};before=w.stats['food_lost'];w.battle_tick()
        self.assertEqual(p['food'],90000);self.assertEqual(w.stats['food_looted'],90000);self.assertEqual(w.stats['food_lost']-before,120000)
        self.assertNotIn(enemy['id'],w.units);w.battle_tick();self.assertEqual(p['food'],90000)

    def test_raid_includes_existing_food_and_household_food_once(self):
        w=self.world();c,d=self.pair(w);p=self.target(w,c)
        v=next(v for v in w.villages.values() if v['nation']!=p['nation']);self.at(p,v)
        v.update(population=200,food=30000,raid={'unit':p['id'],'start':0});p['order']={'type':'raid','target':v['id']}
        w.hour=24;before=w.stats['food_lost'];w.raids()
        self.assertEqual(v['population'],120);self.assertEqual(p['food'],90000)
        self.assertEqual(w.stats['raid_food_generated'],80000);self.assertEqual(w.stats['food_lost']-before,20000)
        w.raids();self.assertEqual(w.stats['raid_food_generated'],80000)

    def test_patrol_threshold_no_lord_slot_and_24_hour_rest(self):
        w=self.world();c,d=self.pair(w);g=w.units[c['garrison']];g['healthy']=74
        rules.patrol_tick(w);self.assertFalse(any(u['kind']=='patrol' for u in w.units.values()))
        g['healthy']=75;before=self.men(w);rules.patrol_tick(w)
        p=next(u for u in w.units.values() if u['kind']=='patrol');self.assertEqual(g['healthy'],50);self.assertEqual(p['healthy'],25)
        self.assertEqual(self.men(w),before);self.assertEqual(len([u for u in w.units.values() if u['kind']=='party']),54)
        p['patrol_phase']='return';self.at(p,c);rules.patrol_tick(w)
        self.assertNotIn(p['id'],w.units);self.assertEqual(g['healthy'],75)
        w.hour=23;rules.patrol_tick(w);self.assertFalse(any(u['kind']=='patrol' for u in w.units.values()))
        w.hour=24;rules.patrol_tick(w);self.assertEqual(len([u for u in w.units.values() if u['kind']=='patrol']),1);w.check()

    def test_patrol_chase_cannot_extend_indefinitely(self):
        w=self.world();c,d=self.pair(w);w.units[c['garrison']]['healthy']=75;rules.patrol_tick(w)
        p=next(u for u in w.units.values() if u['kind']=='patrol')
        e=w.new_unit('bandit',-1,-1,20,p['x'],p['y'])
        rules.patrol_tick(w);self.assertEqual(p['patrol_phase'],'chase')
        w.hour=6;rules.patrol_tick(w)
        self.assertNotEqual(p.get('chase_start'),6)  # Expiry must not immediately reacquire.

    def test_no_mandatory_garrison_floor_for_service(self):
        w=self.world();c,d=self.pair(w);p=self.target(w,c);w.cfg['auto_city_service']=True
        military.service(w,p,c);self.assertEqual(w.units[c['garrison']]['healthy'],0)

    def test_waiting_convoy_can_be_directly_attacked(self):
        w=self.world();c,d=self.pair(w);p=self.target(w,c);self.block(w,p)
        cart=self.dispatch(w,c,p,mission='supply',food=100000)
        enemy=w.new_unit('party',1-p['nation'],next(int(k) for k,v in w.map_clans.items() if v['nation']!=p['nation']),30,cart['x'],cart['y'])
        bid=w.start_battle(enemy,cart)
        self.assertIsNotNone(bid);self.assertEqual(cart['battle'],bid)

    def test_relief_winner_gets_besieger_food(self):
        w=self.world();c,d=self.pair(w);p=self.target(w,c)
        enemy=next(u for u in w.units.values() if u['kind']=='party' and u['nation']!=p['nation'])
        enemy['food']=50000
        field={'id':'relief','relief_for':'siege','sides':{str(p['nation']):[p['id']],str(enemy['nation']):[enemy['id']]}}
        rules.spoils(w,field,p['nation']);self.assertEqual(p['food'],50000);self.assertEqual(enemy['food'],0)
        rules.spoils(w,field,p['nation']);self.assertEqual(p['food'],50000)

    def test_mutual_destruction_produces_no_spoils(self):
        w=self.world();c,d=self.pair(w);p=self.target(w,c);p['food']=30000
        field={'id':'field','sides':{str(p['nation']):[p['id']],str(1-p['nation']):[]}}
        rules.spoils(w,field,None);self.assertEqual(p['food'],30000);self.assertNotIn('food_looted',w.stats)

    def test_patrol_can_join_rescue_and_stops_at_distance_limit(self):
        w=self.world();c,d=self.pair(w);w.units[c['garrison']]['healthy']=75;rules.patrol_tick(w)
        p=next(u for u in w.units.values() if u['kind']=='patrol')
        b={'id':'ambush','city':None,'kind':'ambush','sides':{str(p['nation']):[],'-1':[]},'power':{},'x':p['x'],'y':p['y'],'defender':p['nation']}
        w.join(b,p);self.assertEqual(p['battle'],'ambush');self.assertEqual(b['power'][p['id']],150)
        p['battle']=None
        enemy=w.new_unit('bandit',-1,-1,20,p['x'],p['y'])
        rules.patrol_tick(w);self.assertEqual(p['patrol_phase'],'chase')
        enemy['x']+=4000;rules.patrol_tick(w)
        self.assertEqual(p['patrol_phase'],'route');self.assertEqual(p['order']['type'],'move')

    def test_dispatch_fetch_capacity_excludes_rations(self):
        w=self.world();c,d=self.pair(w);c['food']=300000;d['food']=3000000
        u=self.dispatch(w,c,d,mission='fetch',food=2000000)
        self.at(u,d);military.arrival(w,u)
        self.assertEqual(u['cargo_food'],2000000);self.assertEqual(u['food'],150000);w.check()

    def test_mixed_dispatch_command_journal_replays_exactly(self):
        w=self.world();c,d=self.pair(w)
        self.dispatch(w,c,d,troops=20,food=50000)
        w.step(48);w.check()
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'mixed.save.json';w.save(path)
            rebuilt=replay(path);self.assertEqual(w.physics_digest(),rebuilt.physics_digest());rebuilt.check()

    def test_new_save_replay_and_old_config_keep_rule_boundary(self):
        w=self.world();w.step(6)
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'save.json';w.save(path);loaded=World.load(path)
            self.assertEqual(w.digest(),loaded.digest());loaded.step(3);w.step(3);self.assertEqual(w.digest(),loaded.digest())
            old=copy.deepcopy(w.cfg);old.pop('realmap_rules_v6');old['local_baseline']='v0.4.1-castles-cavalry'
            legacy=World(7,old);self.assertFalse(rules.enabled(legacy));legacy.save(path)
            self.assertFalse(rules.enabled(World.load(path)))
        rebuilt=World(7,w.cfg);rebuilt.step(9);self.assertEqual(w.physics_digest(),rebuilt.physics_digest())

if __name__=='__main__':unittest.main()
