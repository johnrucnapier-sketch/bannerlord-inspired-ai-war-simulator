import tempfile
import unittest
from pathlib import Path
from aiwar.engine import World,dist
from aiwar.policies import decide
from aiwar.relief import staging_point
from aiwar.replay import replay

class ExternalRelief(unittest.TestCase):
    def siege(self,attackers=100,relievers=40):
        w=World(1,{'bandit_cap':0});w.terrain=[[0]*60 for _ in range(40)]
        c=w.cities['c11'];g=w.units[c['garrison']];m=w.units[c['militia']]
        parties=[u for u in w.units.values() if u['kind']=='party']
        for u in parties:u.update(x=1000,y=1000,healthy=0)
        a=next(u for u in parties if u['nation']==0)
        r=next(u for u in parties if u['nation']==1)
        a.update(x=c['x'],y=c['y'],healthy=attackers,food=450000)
        r.update(x=c['x']+700,y=c['y'],healthy=relievers,food=450000)
        # Put the relief force outside the city when the siege is established.
        r['x']+=5000
        w.start_battle(a,g,c['id']);p=w.battles[a['battle']]
        r['x']-=5000
        return w,c,g,m,a,r,p

    def field(self,attackers=100,relievers=40):
        w,c,g,m,a,r,p=self.siege(attackers,relievers)
        w.hour=10;w.start_battle(r,a)
        f=w.battles[p['relief_battle']]
        return w,c,g,m,a,r,p,f

    def test_arrival_does_not_enter_city_defense(self):
        w,c,g,m,a,r,p=self.siege()
        w.contacts({})
        self.assertIsNone(r['battle']);self.assertNotIn(r['id'],p['sides']['1'])
        self.assertEqual(g['battle'],p['id']);self.assertEqual(m['battle'],p['id'])

    def test_field_separates_all_attackers_and_has_no_castle_bonus(self):
        w,c,g,m,a,r,p,f=self.field()
        self.assertIsNone(f['city']);self.assertEqual(f['kind'],'relief_field')
        self.assertEqual(a['battle'],f['id']);self.assertEqual(r['battle'],f['id'])
        self.assertEqual(p['sides']['0'],[])
        self.assertNotIn(g['id'],[i for ids in f['sides'].values() for i in ids])
        self.assertNotIn(m['id'],[i for ids in f['sides'].values() for i in ids])
        self.assertEqual(f['power'][r['id']],r['healthy']*2)
        self.assertEqual(f['power'][a['id']],a['healthy']*2)
        w.check()

    def test_pause_preserves_city_health_and_remaining_preparation(self):
        w,c,g,m,a,r,p,f=self.field()
        before=(g['healthy'],m['healthy'],p['start'])
        for hour in range(11,25):w.hour=hour;w.battle_tick();w.check()
        self.assertEqual((g['healthy'],m['healthy'],p['start']),before)
        self.assertEqual(w.hour-p['start']-p['paused_hours'],10)
        self.assertEqual(a['healthy'],100) # external battle is still preparing

    def test_pause_stops_already_active_assault_damage(self):
        w,c,g,m,a,r,p=self.siege(150,100)
        w.hour=72;w.battle_tick()
        before=(g['healthy'],m['healthy'])
        w.start_battle(r,a)
        for hour in range(73,80):w.hour=hour;w.battle_tick()
        self.assertEqual((g['healthy'],m['healthy']),before)
        self.assertEqual(w.hour-p['start']-p['paused_hours'],72)

    def test_besieger_win_resumes_remaining_clock_not_new_siege(self):
        w,c,g,m,a,r,p,f=self.field(150,20)
        for hour in range(11,200):
            w.hour=hour;w.battle_tick();w.check()
            if f['id'] not in w.battles:break
        self.assertIn(p['id'],w.battles);self.assertEqual(p['start'],0)
        self.assertNotIn('relief_battle',p);self.assertEqual(a['battle'],p['id'])
        self.assertLess(a['healthy'],150)
        health=(g['healthy'],m['healthy'])
        elapsed=w.hour-p['paused_hours']
        self.assertLess(elapsed,72)
        while w.hour-p['paused_hours']<71:w.hour+=1;w.battle_tick()
        self.assertEqual((g['healthy'],m['healthy']),health)
        w.hour+=1;w.battle_tick()
        self.assertLess(g['healthy']+m['healthy'],sum(health))

    def test_relief_win_lifts_siege_without_capturing_city(self):
        w,c,g,m,a,r,p,f=self.field(20,150)
        before=(g['healthy'],m['healthy'])
        for hour in range(11,200):
            w.hour=hour;w.battle_tick();w.check()
            if f['id'] not in w.battles:break
        self.assertNotIn(p['id'],w.battles);self.assertEqual(c['nation'],1)
        self.assertEqual((g['healthy'],m['healthy']),before)
        self.assertIsNone(g['battle']);self.assertIsNone(m['battle'])
        self.assertNotIn(a['id'],w.units);self.assertIn(r['id'],w.units)
        self.assertTrue(any(e['kind']=='siege_lifted' for e in w.events))

    def test_second_relief_joins_same_field_without_reset(self):
        w,c,g,m,a,r,p,f=self.field()
        reinforcement=next(u for u in w.units.values() if u['kind']=='party' and u['nation']==1 and u['id']!=r['id'])
        reinforcement.update(x=r['x'],y=r['y'],healthy=50)
        start=f['start'];w.start_battle(reinforcement,a)
        self.assertEqual(reinforcement['battle'],f['id']);self.assertEqual(f['start'],start)
        self.assertEqual(len(w.battles),2);w.check()

    def test_weak_relief_waits_then_coordinates_after_enemy_losses(self):
        w,c,g,m,a,r,p=self.siege(100,40)
        w.update_known();obs=w.observe(1);alert=obs['relief_requests'][0]
        stage=staging_point(obs,alert,[x for x in obs['cities'] if x['nation']==1])
        r.update(x=stage['x'],y=stage['y'])
        cmds=decide(w.observe(1),'guard')
        self.assertFalse(any(cmd['type']=='attack' and cmd['unit']==r['id'] for cmd in cmds))
        self.assertTrue(any(cmd.get('relief_action')=='wait' and cmd['unit']==r['id'] for cmd in cmds))
        # Only current healthy numbers matter: depleted besiegers can now be attacked.
        a['healthy']=30;w.update_known()
        cmds=decide(w.observe(1),'guard')
        self.assertTrue(any(cmd['type']=='attack' and cmd['unit']==r['id'] and cmd['target']==a['id'] for cmd in cmds))

    def test_reinforcements_must_physically_gather_before_combined_attack(self):
        w,c,g,m,a,r,p=self.siege(100,60)
        other=next(u for u in w.units.values() if u['kind']=='party' and u['nation']==1 and u['id']!=r['id'])
        obs=w.observe(1);stage=staging_point(obs,obs['relief_requests'][0],[x for x in obs['cities'] if x['nation']==1])
        r.update(x=stage['x'],y=stage['y']);other.update(x=stage['x']+5000,y=stage['y'],healthy=60,food=450000)
        w.update_known();cmds=decide(w.observe(1),'guard')
        self.assertFalse(any(cmd['type']=='attack' and cmd.get('campaign_phase')=='relief' for cmd in cmds))
        other.update(x=stage['x'],y=stage['y'])
        cmds=decide(w.observe(1),'guard')
        self.assertTrue(any(cmd['type']=='assemble' for cmd in cmds))
        self.assertTrue(any(cmd['type']=='attack' and cmd.get('campaign_phase')=='relief' for cmd in cmds))
        for cmd in cmds:
            if cmd['type'] in ('assemble','attack'):
                self.assertTrue(w.command(1,cmd)['ok'],cmd)
        self.assertEqual(r['army'],other['army']);self.assertIsNotNone(r['army'])

    def test_waiting_route_avoids_the_besieged_city(self):
        w,c,g,m,a,r,p=self.siege()
        r.update(x=c['x']+10000,y=c['y'])
        cmd=dict(type='move',unit=r['id'],x=c['x']-4000,y=c['y'],campaign_phase='relief',relief_city=c['id'],relief_action='wait')
        self.assertTrue(w.command(1,cmd)['ok'])
        while r['path']:
            w.move_units();self.assertGreater(dist(r,c),2000)
        self.assertIsNone(r['battle'])

    def test_save_and_replay_during_linked_battles(self):
        w=World(1,{'bandit_cap':0,'initial_soldiers':150})
        c=w.cities['c13']
        a=next(u for u in w.units.values() if u['kind']=='party' and u['clan']==3)
        r=next(u for u in w.units.values() if u['kind']=='party' and u['clan']==8)
        self.assertTrue(w.command(0,dict(type='move',unit=a['id'],x=c['x']-7000,y=c['y']))['ok'])
        self.assertTrue(w.command(1,dict(type='move',unit=r['id'],x=c['x']+4000,y=c['y']))['ok'])
        for _ in range(150):
            w.step()
            if not a['path']:break
        self.assertTrue(w.command(0,dict(type='siege',unit=a['id'],target=c['id']))['ok'])
        for _ in range(150):
            w.step()
            if a['battle']:break
        self.assertTrue(w.command(1,dict(type='attack',unit=r['id'],target=a['id']))['ok'])
        for _ in range(100):
            w.step()
            if any(b.get('relief_for') for b in w.battles.values()):break
        self.assertTrue(any(b.get('relief_for') for b in w.battles.values()));w.check()
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'active.json';w.save(path)
            loaded=replay(path);self.assertEqual(loaded.physics_digest(),w.physics_digest())
            loaded.step(80);w.step(80)
            self.assertEqual(loaded.physics_digest(),w.physics_digest());w.check()

    def test_external_relief_cannot_draw_food_from_city(self):
        w,c,g,m,a,r,p=self.siege()
        r.update(x=c['x'],y=c['y'],food=0)
        w.start_battle(r,a);c['food']=1000000
        w.hour=24;w.daily()
        self.assertEqual(c['food'],1000000-(g['healthy']+g['wounded']+m['healthy']+m['wounded'])*w.cfg['city_ration'])
        self.assertTrue(r['hungry']);self.assertEqual(r['healthy'],36)

    def test_empty_city_cannot_start_a_second_siege_while_relief_field_active(self):
        w,c,g,m,a,r,p,f=self.field()
        w.remove(g['id'],'starved');w.remove(m['id'],'starved')
        other=next(u for u in w.units.values() if u['kind']=='party' and u['nation']==0 and u['id']!=a['id'])
        other.update(x=c['x'],y=c['y'],healthy=50)
        w.start_battle(other,g,c['id'])
        self.assertEqual(len(w.battles),2)
        self.assertEqual(other['battle'],f['id'])
        self.assertEqual(sum(b['city']==c['id'] for b in w.battles.values()),1)
        w.check()
