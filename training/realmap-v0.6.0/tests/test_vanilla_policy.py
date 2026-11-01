import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from aiwar.engine import World
from aiwar.policies import decide,decision_cycle,default_styles
from aiwar.vanilla_policy import Planner,PARAMETERS
from aiwar.strategy_catalog import catalog
from aiwar.server import Session
from aiwar.replay import replay

class VanillaBaseline(unittest.TestCase):
    def world(self):return World(7,{'mode':'realmap','bandit_cap':0})
    def prepare(self,w):
        c=next(c for c in w.cities.values() if c['nation']==0 and any(w.cities[k]['nation']==1 for k in c['neighbors']))
        for u in w.units.values():
            if u['kind']=='party' and u['nation']==0:u.update(healthy=110,wounded=0,food=330000,x=c['x'],y=c['y'],path=[],order=None)
        w.update_known();return c
    def apply(self,w,commands):
        for c in commands:self.assertTrue((r:=w.command(0,c))['ok'],(c,r))
        w.check()
    def test_mode_defaults(self):
        self.assertEqual(default_styles('realmap'),('vanilla_v1','vanilla_v1'))
        self.assertEqual(default_styles('duel'),('march','march'))
        self.assertFalse(any(s['id']=='vanilla_v1' for s in catalog('duel')))
        self.assertEqual(catalog('realmap')[0]['id'],'vanilla_v1')
        s=Session(2)
        with patch.object(s,'record_run'):
            s.reset(2,'realmap');self.assertEqual(s.styles,['vanilla_v1']*2)
            s.reset(2,'rural');self.assertEqual(s.styles,['guard','manual'])
            s.reset(2,'duel');self.assertEqual(s.styles,['march']*2)
        s.strategy_runtime.close()
    def test_observation_pure_and_deterministic(self):
        w=self.world();obs=w.observe(0);before=copy.deepcopy(obs)
        a=decide(obs);self.assertEqual(obs,before);self.assertEqual(a,decide(copy.deepcopy(obs)))
        self.assertEqual(a,decide(obs,'vanilla_v1'))
        self.assertLessEqual(len(a),100)
    def test_no_automatic_muster_for_understrength_parties(self):
        w=self.world();plan=Planner(w.observe(0));plan.launch()
        self.assertFalse(plan.cmd)
    def test_no_army_invitation_with_fifteen_days_or_less(self):
        w=self.world();self.prepare(w)
        for u in w.units.values():
            if u['kind']=='party' and u['nation']==0:u['food']=u['healthy']*100*15
        p=Planner(w.observe(0));p.launch();self.assertFalse(p.cmd)
    def test_muster_keeps_mobile_reserve_and_requires_arrival(self):
        w=self.world();self.prepare(w);p=Planner(w.observe(0));p.launch()
        self.assertTrue(p.cmd);self.assertTrue(all(c['type']=='move' for c in p.cmd))
        self.assertLessEqual(len(p.cmd),int(27*.7));self.apply(w,p.cmd)
        for c in p.cmd:
            u=w.units[c['unit']];u.update(x=c['x']+2000,y=c['y']+2000)
        p2=Planner(w.observe(0));p2.musters();self.assertFalse(any(c['type']=='assemble' for c in p2.cmd))
        for c in p.cmd:
            u=w.units[c['unit']];u.update(x=c['x'],y=c['y'],path=[])
        p3=Planner(w.observe(0));p3.musters();self.assertTrue(any(c['type']=='assemble' for c in p3.cmd));self.apply(w,p3.cmd)
    def test_lost_target_cancels_muster(self):
        w=self.world();self.prepare(w);p=Planner(w.observe(0));p.launch();self.apply(w,p.cmd)
        tid=p.cmd[0]['vanilla_target'];c=w.cities[tid];w.capture(tid,0,[next(u['clan'] for u in w.units.values() if u['kind']=='party' and u['nation']==0)]);w.update_known()
        q=Planner(w.observe(0));q.musters();self.assertFalse(any(c['type']=='assemble' for c in q.cmd));self.assertTrue(any(c.get('vanilla_task')=='refit' for c in q.cmd))
    def test_exhausted_army_disbands_instead_of_pushing(self):
        w=self.world();base=self.prepare(w);members=[u for u in w.units.values() if u['kind']=='party' and u['nation']==0][:3]
        tid=next(k for k in base['neighbors'] if w.cities[k]['nation']==1)
        self.apply(w,[dict(type='assemble',unit=members[0]['id'],units=[u['id'] for u in members[1:]],campaign_target=tid)])
        for u in members:u['food']=0
        p=Planner(w.observe(0));p.campaigns();self.assertEqual(p.cmd[0]['type'],'disband');self.apply(w,p.cmd)
    def test_cavalry_only_garrison_does_not_raise_infantry(self):
        w=self.world();u=next(u for u in w.units.values() if u['kind']=='party' and u['nation']==0);w.remove(u['id'])
        for c in w.cities.values():
            if c['nation']==0:
                g=w.units[c['garrison']];g.update(healthy=100,cavalry=100);c['food']=1000000
        p=Planner(w.observe(0));p.refill_and_raise();self.assertFalse(any(c['type']=='create' for c in p.cmd))
    def test_logistics_transports_only_on_allowed_friendly_edges(self):
        w=self.world()
        for c in w.cities.values():
            if c['nation']==0:c['food']=150000
        c=next(c for c in w.cities.values() if c['nation']==0 and any(w.cities[k]['nation']==0 for k in c['supply_neighbors']));c['food']=2000000
        p=Planner(w.observe(0));p.logistics();self.assertTrue(p.cmd)
        for cmd in p.cmd:
            self.assertIn(cmd['destination'],w.cities[cmd['city']]['supply_neighbors']);self.assertEqual(w.cities[cmd['destination']]['nation'],0)
        self.apply(w,p.cmd)
    def test_policy_save_replay_and_resume_need_no_external_memory(self):
        w=self.world()
        for _ in range(72):
            if w.hour%3==0:
                self.assertTrue(all(r['ok'] for r in decision_cycle(w)))
            w.step();w.check()
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'world.json';w.save(p);r=replay(p)
            self.assertEqual(w.physics_digest(),r.physics_digest())
            self.assertEqual(decide(w.observe(0)),decide(r.observe(0)))
            for state in (w,r):decision_cycle(state);state.step(3)
            self.assertEqual(w.physics_digest(),r.physics_digest())

if __name__=='__main__':unittest.main()
