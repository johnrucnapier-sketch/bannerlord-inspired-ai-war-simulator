import copy,tempfile,unittest
from pathlib import Path
from aiwar.engine import World
from aiwar.vanilla_policy import decide
from aiwar.vanilla_logistics import LogisticsPlanner
from aiwar.replay import replay

class LogisticsPolicyTests(unittest.TestCase):
    def world(self):return World(31,{'mode':'realmap','auto_city_service':False,'bandit_cap':0})
    def apply(self,w,cmds):
        for cmd in cmds:self.assertTrue((r:=w.command(0,cmd))['ok'],(cmd,r))
        w.check()
    def army(self,w,days=4):
        c=next(c for c in w.cities.values() if c['nation']==0 and any(w.cities[i]['nation']==1 for i in c['neighbors']))
        members=[u for u in w.units.values() if u['kind']=='party' and u['nation']==0][:3]
        for p in members:p.update(x=c['x'],y=c['y'],healthy=110,food=11000*days)
        target=next(i for i in c['neighbors'] if w.cities[i]['nation']==1)
        self.apply(w,[dict(type='assemble',unit=members[0]['id'],units=[p['id'] for p in members[1:]],campaign_target=target)])
        # Field camp 6 map units along a valid route: this must use a real transport, not city refill.
        friend=next(w.cities[i] for i in c['supply_neighbors'] if w.cities[i]['nation']==0)
        points=w.route(members[0],friend['x'],friend['y']);x,y=c['x'],c['y'];remaining=6000
        import math
        for nx,ny in points:
            length=math.hypot(nx-x,ny-y)
            if length>=remaining:
                x,y=round(x+(nx-x)*remaining/length),round(y+(ny-y)*remaining/length);break
            remaining-=length;x,y=nx,ny
        for unit in members:unit.update(x=x,y=y)
        c['food']=3000000;w.update_known();return c,members
    def test_default_dispatches_supply_and_holds_army_not_disbands(self):
        w=self.world();c,m=self.army(w);commands=decide(w.observe(0))
        self.assertTrue(any(x['type']=='dispatch' and x.get('mission')=='supply' for x in commands))
        self.assertTrue(any(x.get('vanilla_task')=='await_supply' for x in commands));self.assertFalse(any(x['type']=='disband' for x in commands))
        self.apply(w,commands)
        again=decide(w.observe(0));self.assertFalse(any(x['type']=='dispatch' and x.get('mission')=='supply' for x in again))
        w.step(32);self.assertGreater(sum(p['food'] for p in m),3*44000)
    def test_starving_army_does_not_wait_for_unreachable_supplies(self):
        w=self.world();c,m=self.army(w,days=0)
        cmds=decide(w.observe(0));self.assertFalse(any(x.get('mission')=='supply' for x in cmds));self.assertTrue(any(x['type']=='disband' for x in cmds));self.apply(w,cmds)
    def test_rear_garrison_moves_toward_front_and_mixes_food(self):
        w=self.world();p=LogisticsPlanner(w.observe(0))
        c,d=next((c,w.cities[i]) for c in p.safe for i in c['supply_neighbors'] if i in p.bycity and p.depth.get(i,999)<p.depth.get(c['id'],999))
        c=w.cities[c['id']];d=w.cities[d['id']]
        w.units[c['garrison']]['healthy']=120;c['food']=3000000;d['food']=150000
        cmds=decide(w.observe(0));moves=[x for x in cmds if x['type']=='dispatch' and x.get('troops',0)]
        self.assertTrue(moves);self.assertTrue(any(x['food']>0 for x in moves));self.assertTrue(all(x['troops']<=20 for x in moves))
        self.apply(w,cmds);self.assertEqual(w.units[c['garrison']]['healthy'],100)
        p=LogisticsPlanner(w.observe(0));self.assertEqual(p.incoming_troops[moves[0]['destination']],20)
    def test_supply_sources_keep_stock_and_unsafe_routes_rejected(self):
        w=self.world();c,m=self.army(w,days=10);p=LogisticsPlanner(w.observe(0));p.safe_route=lambda a,b:False;p.logistics()
        self.assertFalse(any(x.get('mission')=='supply' for x in p.cmd))
        p=LogisticsPlanner(w.observe(0));p.logistics()
        for cmd in p.cmd:
            if cmd.get('mission')=='supply':self.assertGreaterEqual(p.stock[cmd['city']],p.floors[cmd['city']])
    def raid_fixture(self):
        w=self.world();p=next(u for u in w.units.values() if u['kind']=='party' and u['nation']==0)
        for u in w.units.values():
            if u['nation']==1 and u['kind']=='party':u['healthy']=0
        own=[c for c in w.cities.values() if c['nation']==0]
        v=min((v for v in w.villages.values() if v['nation']==1),key=lambda v:min((v['x']-c['x'])**2+(v['y']-c['y'])**2 for c in own))
        p.update(x=v['x'],y=v['y'],healthy=100,food=100000);v['population']=200;w.update_known();return w,p,v
    def test_raid_supply_uses_visible_population_not_hidden_food(self):
        w,u,v=self.raid_fixture();obs=w.observe(0);before=copy.deepcopy(obs)
        p=LogisticsPlanner(obs);self.assertTrue(p.raid_for_food([p.units[u['id']]]));self.assertEqual(p.cmd[-1]['target'],v['id']);self.assertEqual(obs,before)
        self.apply(w,p.cmd);start=u['food'];w.step(25);self.assertGreater(u['food'],start);self.assertEqual(w.stats['raid_food_generated'],81000)
    def test_stale_or_disabled_village_is_not_used_for_supply(self):
        w,u,v=self.raid_fixture();obs=w.observe(0)
        for item in obs['villages']:item['stale']=True
        p=LogisticsPlanner(obs);self.assertFalse(p.raid_for_food([p.units[u['id']]]))
    def test_farmer_cart_is_a_legal_default_patrol_target(self):
        w,u,v=self.raid_fixture();u['food']=300000
        e=next(e for e in w.units.values() if e['kind']=='village_cart' and e['nation']==1)
        e.update(x=u['x'],y=u['y'],phase='outbound');w.update_known()
        p=LogisticsPlanner(w.observe(0));p.independent()
        self.assertTrue(any(x['type']=='attack' and x['target']==e['id'] for x in p.cmd));self.apply(w,p.cmd)
    def test_default_observation_pure_deterministic_and_replay(self):
        w=self.world();obs=w.observe(0);before=copy.deepcopy(obs)
        self.assertEqual(decide(obs),decide(copy.deepcopy(obs)));self.assertEqual(obs,before)
        for _ in range(24):
            for n in (0,1):
                for cmd in decide(w.observe(n)):self.assertTrue(w.command(n,cmd)['ok'],cmd)
            w.step(3);w.check()
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'save.json';w.save(path);r=replay(path);self.assertEqual(r.physics_digest(),w.physics_digest())
