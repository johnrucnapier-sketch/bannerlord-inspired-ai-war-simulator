import unittest,copy,tempfile
from pathlib import Path
from aiwar.engine import World
from aiwar import military
from aiwar.navigation import travel_hours
from aiwar.sdk import command_error
from aiwar.replay import replay

class CastleRules(unittest.TestCase):
    def world(self):return World(1,{'mode':'realmap','auto_city_service':False,'bandit_cap':0})
    def pair(self,w):
        for c in w.cities.values():
            for key in c['supply_neighbors']:
                d=w.cities[key]
                if c['nation']==d['nation']:return c,d
        self.fail('no friendly supply edge')
    def food(self,w):return sum(c['food'] for c in w.cities.values())+sum(u['food']+u['cargo_food'] for u in w.units.values())
    def men(self,w):return sum(w.size(u) for u in w.units.values())
    def execute_trip(self,w,u):
        elapsed=0;spent=0
        for _ in range(3):
            while u['path']:
                w.move_units();elapsed+=1
                if elapsed%24==0:
                    before=u['food']+u['cargo_food'];w.eat([u],w.cfg['field_ration']);spent+=before-u['food']-u['cargo_food']
            military.arrival(w,u)
            if u['id'] not in w.units:break
        return elapsed,spent

    def test_types_and_training(self):
        w=self.world();cs=[c for c in w.cities.values() if c['settlement_type']=='castle']
        self.assertEqual(len(cs),17);self.assertEqual(len(w.cities)-len(cs),12)
        before={c['id']:w.units[c['garrison']]['healthy'] for c in cs}
        for _ in range(71):military.train(w)
        self.assertEqual(sum(u['cavalry'] for u in w.units.values()),0)
        military.train(w)
        for c in cs:
            g=w.units[c['garrison']];self.assertEqual(g['cavalry'],1);self.assertEqual(g['healthy'],before[c['id']])
        self.assertTrue(all(w.units[c['garrison']]['cavalry']==0 for c in w.cities.values() if c['settlement_type']=='town'))
        c=cs[0];g=w.units[c['garrison']];g['cavalry']=g['healthy']
        for _ in range(200):military.train(w)
        self.assertEqual(c['training_hours'],0)
        g['cavalry']-=1;military.train(w);self.assertEqual(c['training_hours'],1)

    def test_besieged_training_pauses(self):
        w=self.world();c=next(c for c in w.cities.values() if c['settlement_type']=='castle')
        c['training_hours']=40;w.battles={'test':{'city':c['id']}}
        for _ in range(100):military.train(w)
        self.assertEqual(c['training_hours'],40)

    def test_mixed_and_army_speed(self):
        w=self.world();parties=[u for u in w.units.values() if u['kind']=='party']
        a,b=parties[:2];a.update(healthy=100,cavalry=0);b.update(healthy=50,cavalry=50)
        self.assertEqual(military.speed(a,w.cfg['speeds']),1000)
        self.assertEqual(military.speed(b,w.cfg['speeds']),1200)
        a['cavalry']=50;self.assertEqual(military.speed(a,w.cfg['speeds']),1100)
        a['army']=b['army']='a';w.armies={'a':[a['id'],b['id']]}
        self.assertEqual(military.speed(a,w.cfg['speeds'],[a,b]),566)
        self.assertEqual(military.speed(b,w.cfg['speeds'],[a,b]),566)
        speed={u['id']:u['movement_speed'] for u in w.observe()['units']}
        self.assertEqual(speed[a['id']],speed[b['id']])

    def test_selected_transfer_and_exchange(self):
        w=self.world();c=next(c for c in w.cities.values() if c['nation']==0);g=w.units[c['garrison']];g['cavalry']=12
        p=next(u for u in w.units.values() if u['kind']=='party' and u['nation']==0)
        p.update(x=c['x'],y=c['y']);before=self.men(w)
        r=w.command(0,{'type':'transfer','unit':g['id'],'target':p['id'],'count':7,'troop_type':'cavalry'})
        self.assertTrue(r['ok'],r);self.assertEqual((g['cavalry'],p['cavalry']),(5,7));self.assertEqual(self.men(w),before)
        snapshot=copy.deepcopy(w.units)
        r=w.command(0,{'type':'transfer','unit':g['id'],'target':p['id'],'count':6,'troop_type':'cavalry'})
        self.assertFalse(r['ok']);self.assertEqual(w.units,snapshot)
        w.cfg['auto_city_service']=True;p['refill_target']=w.size(p)
        r=w.command(0,{'type':'set_composition','unit':p['id'],'cavalry_target':0})
        self.assertTrue(r['ok']);self.assertEqual(p['cavalry'],0);self.assertEqual(g['cavalry'],12);self.assertEqual(self.men(w),before)

    def test_create_selected_cavalry(self):
        w=self.world();c=next(iter(w.cities.values()));g=w.units[c['garrison']];g['cavalry']=20
        p=next(u for u in w.units.values() if u['kind']=='party' and u['clan']==c['clan']);w.remove(p['id'])
        before=self.men(w)
        r=w.command(c['nation'],{'type':'create','city':c['id'],'count':15,'troop_type':'cavalry'})
        self.assertTrue(r['ok'],r);self.assertEqual(w.units[r['unit']]['cavalry'],15);self.assertEqual(g['cavalry'],5);self.assertEqual(self.men(w),before)

    def test_casualties_healing_and_starvation(self):
        w=self.world();u=next(u for u in w.units.values() if u['kind']=='party');u.update(healthy=100,wounded=0,cavalry=40,cavalry_wounded=0)
        military.casualties(u,20,5);u['healthy']-=20;u['wounded']+=15
        self.assertEqual((u['cavalry'],u['cavalry_wounded']),(32,6))
        military.heal(u,15);u['wounded']-=15;u['healthy']+=15
        self.assertEqual((u['cavalry'],u['cavalry_wounded']),(38,0))
        u['food']=0;w.eat([u],100);w.check()

    def test_equal_combat_power(self):
        powers=[]
        for cavalry in (0,30):
            w=self.world();a=next(u for u in w.units.values() if u['kind']=='party' and u['nation']==0);b=next(u for u in w.units.values() if u['kind']=='party' and u['nation']==1)
            a['cavalry']=cavalry;b.update(x=a['x'],y=a['y'])
            bid=w.start_battle(a,b);powers.append(w.battles[bid]['power'][a['id']])
        self.assertEqual(powers[0],powers[1])

    def test_delivery_militia_food_and_return_conservation(self):
        w=self.world();c,d=self.pair(w);c['food']=2000000;d['food']=100000
        beforefood=self.food(w);beforemen=self.men(w);m=w.units[c['militia']];g=w.units[c['garrison']];gh=g['healthy']
        r=w.command(c['nation'],{'type':'dispatch','city':c['id'],'destination':d['id'],'food':900000})
        self.assertTrue(r['ok'],r);u=w.units[r['unit']]
        self.assertEqual((u['healthy'],m['healthy'],g['healthy']),(50,50,gh))
        self.assertEqual((u['food'],u['cargo_food']),(150000,900000))
        self.assertFalse(w.command(c['nation'],{'type':'dispatch','city':c['id'],'destination':d['id']})['ok'])
        hours,spent=self.execute_trip(w,u)
        self.assertGreater(hours,0);self.assertGreater(spent,0)
        self.assertNotIn(u['id'],w.units);self.assertIsNone(c['convoy']);self.assertEqual(m['healthy'],100)
        self.assertEqual(self.men(w),beforemen);self.assertEqual(self.food(w),beforefood-spent);w.check()

    def test_fetch_empty_cargo_and_stock_floor(self):
        w=self.world();c,d=self.pair(w);c['food']=200000;d['food']=600000;before=self.food(w)
        r=w.command(c['nation'],{'type':'dispatch','city':c['id'],'destination':d['id'],'mission':'fetch','food':1000000})
        self.assertTrue(r['ok'],r);u=w.units[r['unit']];self.assertEqual(u['cargo_food'],0)
        _,spent=self.execute_trip(w,u)
        self.assertEqual(d['food'],150000);self.assertEqual(self.food(w),before-spent);self.assertNotIn(u['id'],w.units)

    def test_full_destination_returns_undelivered_cargo(self):
        w=self.world();c,d=self.pair(w);c['food']=2000000;d['food']=w.cfg['warehouse'];before=self.food(w)
        r=w.command(c['nation'],{'type':'dispatch','city':c['id'],'destination':d['id'],'food':900000});u=w.units[r['unit']]
        _,spent=self.execute_trip(w,u);self.assertEqual(d['food'],w.cfg['warehouse']);self.assertEqual(self.food(w),before-spent)

    def test_neighbor_and_enemy_rejection(self):
        w=self.world();c,d=self.pair(w)
        far=next(z for z in w.cities.values() if z['nation']==c['nation'] and z['id'] not in c['supply_neighbors'] and z!=c)
        before=self.food(w);m=w.units[c['militia']]['healthy']
        self.assertFalse(w.command(c['nation'],{'type':'dispatch','city':c['id'],'destination':far['id']})['ok'])
        d['nation']=1-c['nation']
        self.assertFalse(w.command(c['nation'],{'type':'dispatch','city':c['id'],'destination':d['id']})['ok'])
        self.assertEqual(self.food(w),before);self.assertEqual(w.units[c['militia']]['healthy'],m)

    def test_bandit_immunity_enemy_army_can_attack(self):
        w=self.world();c,d=self.pair(w);r=w.command(c['nation'],{'type':'dispatch','city':c['id'],'destination':d['id'],'food':0});u=w.units[r['unit']]
        b=w.new_unit('bandit',-1,-1,100,u['x'],u['y'])
        self.assertIsNone(w.start_battle(b,u));self.assertFalse(w.bandit_can_target(u));self.assertIsNone(u['battle'])
        enemy=next(p for p in w.units.values() if p['kind']=='party' and p['nation']!=u['nation']);enemy.update(x=u['x'],y=u['y'])
        bid=w.start_battle(enemy,u);self.assertIsNotNone(bid);self.assertEqual(w.battles[bid]['power'][u['id']],50)

    def test_militia_growth_reserves_away_places(self):
        w=self.world();c,d=self.pair(w);m=w.units[c['militia']];m['healthy']=200;c['food']=3000000
        r=w.command(c['nation'],{'type':'dispatch','city':c['id'],'destination':d['id'],'food':0});self.assertTrue(r['ok'],r)
        for _ in range(20):w.daily()
        self.assertEqual(m['healthy'],150)

    def test_destination_capture_aborts_fetch(self):
        w=self.world();c,d=self.pair(w);r=w.command(c['nation'],{'type':'dispatch','city':c['id'],'destination':d['id'],'mission':'fetch'});u=w.units[r['unit']]
        d['nation']=1-u['nation'];stock=d['food'];military.resume(w,u)
        self.assertEqual(u['phase'],'return');military.arrival(w,u);self.assertEqual(d['food'],stock)

    def test_home_capture_redirects_without_duplicate_slot(self):
        w=self.world();c,d=self.pair(w);r=w.command(c['nation'],{'type':'dispatch','city':c['id'],'destination':d['id'],'food':0});u=w.units[r['unit']]
        c['nation']=1-u['nation'];military.resume(w,u)
        self.assertNotEqual(u['home'],c['id']);self.assertEqual(w.cities[u['home']]['convoy'],u['id']);self.assertIsNone(c['convoy']);w.check()

    def test_recaptured_home_reclaims_convoy_slot(self):
        w=self.world();c,d=self.pair(w)
        r=w.command(c['nation'],{'type':'dispatch','city':c['id'],'destination':d['id'],'food':0});u=w.units[r['unit']]
        nation=u['nation'];original={key:x['nation'] for key,x in w.cities.items()}
        for x in w.cities.values():x['nation']=1-nation
        military.resume(w,u);self.assertEqual(u['phase'],'orphan_return');self.assertIsNone(c['convoy'])
        for key,x in w.cities.items():x['nation']=original[key]
        military.resume(w,u);self.assertEqual(c['convoy'],u['id']);w.check()

    def test_save_replay_training_and_dispatch(self):
        w=self.world();c,d=self.pair(w)
        self.assertTrue(w.command(c['nation'],{'type':'dispatch','city':c['id'],'destination':d['id'],'food':50000})['ok'])
        w.step(90);w.check()
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'save.json';w.save(p);restored=replay(p)
            self.assertEqual(restored.physics_digest(),w.physics_digest())
            w.step(20);restored.step(20);self.assertEqual(w.physics_digest(),restored.physics_digest())

    def test_api_and_observation(self):
        self.assertIsNone(command_error({'type':'set_composition','unit':'u1','cavalry_target':20}))
        self.assertIsNone(command_error({'type':'dispatch','city':'a','destination':'b','mission':'fetch'}))
        w=self.world();obs=w.observe(0)
        self.assertTrue(obs['castle_logistics']);self.assertTrue(all('settlement_type' in c for c in obs['cities']))
        self.assertTrue(all('movement_speed' in u for u in obs['units']))

if __name__=='__main__':unittest.main()
