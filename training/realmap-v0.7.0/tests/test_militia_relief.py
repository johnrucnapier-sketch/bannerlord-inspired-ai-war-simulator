import unittest
from aiwar.engine import World,dist
from aiwar.navigation import travel_hours
from aiwar.policies import decide

class MilitiaRelief(unittest.TestCase):
    def siege(self,legacy=False):
        w=World(1,{'bandit_cap':0});w.terrain=[[0]*60 for _ in range(40)]
        if legacy:w.cfg.update(version='0.1.5',external_relief=False)
        c=w.cities['c11'];g=w.units[c['garrison']];m=w.units[c['militia']]
        for u in w.units.values():
            if u['kind']=='party':u.update(x=1000,y=1000)
        a=next(u for u in w.units.values() if u['kind']=='party' and u['nation']==0)
        a.update(x=c['x'],y=c['y'],healthy=150,food=450000)
        w.start_battle(a,g,c['id']);c['food']=1000000
        return w,c,g,m,a,w.battles[a['battle']]

    def test_initial_growth_cap_food_and_capture_reset(self):
        w=World(1,{'bandit_cap':0});c=w.cities['c00'];m=w.units[c['militia']]
        self.assertEqual(m['healthy'],100)
        food=c['food'];w.hour=24;w.daily()
        self.assertEqual(m['healthy'],101)
        self.assertEqual(food-c['food'],(30+50+101)*w.cfg['city_ration'])
        m.update(healthy=199,wounded=1);w.hour=48;w.daily()
        self.assertEqual(w.size(m),200)
        w.capture(c['id'],1,[6]);self.assertEqual(w.size(m),0);self.assertEqual(m['nation'],1)
        w.daily();self.assertEqual(w.size(m),0)
        w.hour=72;w.daily();self.assertEqual(m['healthy'],1);w.check()

    def test_militia_has_half_power_and_cannot_leave_or_transfer(self):
        w,c,g,m,a,b=self.siege()
        self.assertEqual(b['power'][m['id']]/m['healthy'],b['power'][g['id']]/g['healthy']/2)
        m['battle']=None
        self.assertFalse(w.command(1,{'type':'move','unit':m['id'],'x':1000,'y':1000})['ok'])
        self.assertFalse(w.command(1,{'type':'create','city':c['id'],'count':10,'source':m['id']})['ok'])

    def test_seventy_two_hours_before_any_combat_damage(self):
        w,c,g,m,a,b=self.siege()
        for hour in range(1,72):w.hour=hour;w.battle_tick()
        self.assertEqual((a['healthy'],g['healthy'],m['healthy']),(150,50,100))
        self.assertEqual(c['nation'],1)
        w.hour=72;w.battle_tick()
        self.assertLess(a['healthy'],150)
        self.assertLess(g['healthy']+m['healthy'],150)

    def test_legacy_alert_is_national_and_nearby_reliever_really_walks(self):
        w,c,g,m,a,b=self.siege(legacy=True)
        parties=[u for u in w.units.values() if u['kind']=='party' and u['nation']==1]
        near,far=parties[:2]
        for u in parties:u['healthy']=0
        near.update(x=c['x']+10000,y=c['y'],healthy=40,food=120000)
        far.update(x=1000,y=1000,healthy=40,food=120000)
        w.update_known();obs=w.observe(1)
        self.assertEqual(obs['relief_requests'][0]['city'],c['id'])
        self.assertFalse(w.observe(0)['relief_requests'])
        cmds=decide(obs,'guard')
        relief=[cmd for cmd in cmds if cmd.get('campaign_phase')=='relief']
        self.assertIn(near['id'],[cmd['unit'] for cmd in relief]);self.assertNotIn(far['id'],[cmd['unit'] for cmd in relief])
        start=(near['x'],near['y']);cmd=next(cmd for cmd in relief if cmd['unit']==near['id'])
        self.assertTrue(w.command(1,cmd)['ok']);self.assertEqual((near['x'],near['y']),start)
        eta=travel_hours(w.terrain,near,c,w.cfg['speeds'],72)
        for _ in range(eta):w.step()
        self.assertEqual(near['battle'],b['id']);self.assertLess(w.hour,72)
        self.assertTrue(any(e['kind']=='relief_arrived' for e in w.events))

    def test_route_eta_handles_forest_armies_and_blocked_paths(self):
        w=World(1,{'bandit_cap':0});w.terrain=[[1]*60 for _ in range(40)]
        u=next(u for u in w.units.values() if u['kind']=='party');u.update(x=11000,y=11000)
        target={'x':31000,'y':11000}
        eta=travel_hours(w.terrain,u,target,w.cfg['speeds'],100)
        u['army']='test';slow=travel_hours(w.terrain,u,target,w.cfg['speeds'],200)
        self.assertGreater(slow,eta)
        u['army']=None;w.go(u,**target)
        hours=0
        while dist(u,target)>1000:w.move_units();hours+=1
        self.assertEqual(hours,eta)
        for y in range(40):w.terrain[y][10]=2
        u.update(x=11000,y=11000)
        self.assertIsNone(travel_hours(w.terrain,u,target,w.cfg['speeds'],100))

    def test_militia_does_not_join_nearby_field_fight_or_duplicate(self):
        w=World(1,{'bandit_cap':0});c=w.cities['c00'];m=w.units[c['militia']]
        a=next(u for u in w.units.values() if u['kind']=='party' and u['nation']==0)
        enemy=next(u for u in w.units.values() if u['kind']=='party' and u['nation']==1)
        a.update(x=c['x'],y=c['y']);enemy.update(x=c['x'],y=c['y'])
        w.start_battle(a,enemy);self.assertIsNone(m['battle'])
        w,c,g,m,a,b=self.siege();m['battle']=None;w.join(b,m)
        self.assertEqual(b['sides']['1'].count(m['id']),1)

    def test_finished_siege_cancels_relief_and_returns_home(self):
        w,c,g,m,a,b=self.siege()
        u=next(u for u in w.units.values() if u['kind']=='party' and u['nation']==1)
        u.update(x=c['x']+5000,y=c['y'],order={'type':'move','campaign_phase':'relief','relief_city':c['id'],'x':c['x'],'y':c['y']})
        w.battles.clear()
        for troop in w.units.values():troop['battle']=None
        cmds=decide(w.observe(1),'guard')
        self.assertTrue(any(cmd.get('unit')==u['id'] and cmd.get('campaign_phase')=='return' for cmd in cmds))

    def test_legacy_existing_defenders_prevent_unlimited_reinforcement_calls(self):
        w,c,g,m,a,b=self.siege(legacy=True)
        defenders=[u for u in w.units.values() if u['kind']=='party' and u['nation']==1]
        defenders[0].update(x=c['x'],y=c['y'],healthy=150)
        w.join(b,defenders[0])
        defenders[1].update(x=c['x']+5000,y=c['y'],healthy=40,food=120000)
        w.update_known()
        self.assertFalse(any(cmd.get('campaign_phase')=='relief' for cmd in decide(w.observe(1),'guard')))
