import copy, importlib.util, unittest
from pathlib import Path
from aiwar.sdk import Environment
spec=importlib.util.spec_from_file_location('capacity',Path(__file__).with_name('agent.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class CapacityTests(unittest.TestCase):
    def world(self):
        env=Environment(seed=701891);w=env.world;w.terrain=[[0]*60 for _ in range(40)];w.hour=240
        for c in w.cities.values():c['food']=3000000
        return w
    def parties(self,w,n=0):return [u for u in w.units.values() if u['nation']==n and u['kind']=='party']
    def setup_rotation(self):
        w=self.world();front=w.cities['c00'];rear=w.cities['c01']
        for u in list(w.units.values()):
            if u['kind']=='party' and u['nation']==1:u.update(x=115000,y=75000)
        for c in w.cities.values():
            if c['nation']==0:w.units[c['garrison']]['healthy']=0
        # All clan slots occupied; no new parties can substitute for rotation.
        own=self.parties(w)
        for clan in range(6):
            for _ in range(2):w.new_unit('party',0,clan,19,front['x'],front['y'],food=57000)
        for p in self.parties(w):p.update(x=front['x'],y=front['y'],healthy=19,wounded=0,food=57000,refill_target=150,path=[],order=None)
        w.units[rear['garrison']]['healthy']=500
        pol=m.Policy();pol.initialized=True;pol.phase='rally';pol.phase_at=0;pol.depot=front['id'];pol.target='c15'
        return w,pol,front,rear
    def test_rotation_reserves_real_garrison_and_food_then_replenishes(self):
        w,p,front,rear=self.setup_rotation();before=sum(x['healthy'] for x in self.parties(w))
        commands=p.decide(w.observe(0));routes=copy.deepcopy(p.refit_routes)
        self.assertEqual(len(routes),4)
        self.assertLessEqual(sum(x['goal']-19 for x in routes.values()),500)
        self.assertTrue(all(x['city']==rear['id'] for x in routes.values()))
        for c in commands:self.assertTrue(w.command(0,c)['ok'],c)
        outcomes=[]
        for _ in range(40):
            w.step(6)
            cmds=p.decide(w.observe(0),outcomes);outcomes=[w.command(0,c) for c in cmds]
            self.assertTrue(all(x['ok'] for x in outcomes),outcomes)
            if all(w.units[uid]['healthy']>=120 for uid in routes):break
        self.assertTrue(all(w.units[uid]['healthy']>=120 for uid in routes))
        self.assertGreater(sum(x['healthy'] for x in self.parties(w)),before+400)
        self.assertTrue(all(uid not in p.refit_routes for uid in routes))
    def test_no_manpower_or_no_food_means_no_fake_refit(self):
        for resource in ('manpower','food'):
            w,p,front,rear=self.setup_rotation()
            if resource=='manpower':w.units[rear['garrison']]['healthy']=0
            else:rear['food']=0
            p.decide(w.observe(0));self.assertEqual(p.refit_routes,{})
    def test_cold_restart_discovers_depleted_reservoir_need(self):
        w,p,front,rear=self.setup_rotation();p=m.Policy();cmd=p.decide(w.observe(0))
        self.assertTrue(p.refit_routes);self.assertTrue(any(x['type']=='move' for x in cmd))
    def test_recent_mobile_reserve_uses_commitment_reach_and_expires(self):
        w=self.world();p=m.Policy();p.initialized=True;p.decide(w.observe(0))
        target=dict(x=73000,y=68000,healthy=50,militia_healthy=100,id='test',stale=False)
        members=[dict(x=66500,y=68000,healthy=400,food=1200000,wounded=0)]
        foe=dict(id='remembered',kind='party',nation=1,x=48000,y=68000,healthy=418)
        p.last_enemies={'remembered':dict(at=p.hour-48,unit=foe)}
        self.assertEqual(p.reserve_threat(target,members),418)
        p.last_enemies['remembered']['at']=p.hour-336
        self.assertEqual(p.reserve_threat(target,members),418)
        p.last_enemies['remembered']['at']=p.hour-337
        self.assertEqual(p.reserve_threat(target,members),0)
    def test_outside_fastest_arrival_envelope_not_counted(self):
        w=self.world();p=m.Policy();p.initialized=True;p.decide(w.observe(0))
        target=dict(x=119000,y=79000,healthy=1,militia_healthy=1,id='test')
        p.last_enemies={'far':dict(at=p.hour,unit=dict(id='far',kind='party',x=1000,y=1000,healthy=400))}
        self.assertEqual(p.reserve_threat(target,[dict(x=119000,y=79000,healthy=400)]),0)
    def test_invalid_old_refit_destination_is_physically_stopped(self):
        w,p,front,rear=self.setup_rotation();cmd=p.decide(w.observe(0));ids=set(p.refit_routes)
        for c in cmd:self.assertTrue(w.command(0,c)['ok'])
        w.step(6);rear['food']=0
        cmd=p.decide(w.observe(0))
        stopped={c['unit'] for c in cmd if c['type']=='stop'}
        self.assertTrue(ids <= stopped)
        for c in cmd:self.assertTrue(w.command(0,c)['ok'],c)
        for uid in ids:
            order=w.units[uid].get('order') or {}
            self.assertFalse(order.get('type')=='move' and order.get('x')==rear['x'] and order.get('y')==rear['y'])

    def test_visible_city_defender_not_double_counted(self):
        w=self.world();p=m.Policy();p.initialized=True;p.decide(w.observe(0))
        target=dict(x=73000,y=68000,healthy=50,militia_healthy=100,id='test')
        foe=dict(id='known',kind='party',nation=1,x=73000,y=68000,healthy=150)
        p.units['known']=foe;p.last_enemies={'known':dict(at=p.hour,unit=foe)}
        self.assertEqual(p.reserve_threat(target,[dict(x=66500,y=68000,healthy=400)]),0)

if __name__=='__main__':unittest.main(verbosity=2)
