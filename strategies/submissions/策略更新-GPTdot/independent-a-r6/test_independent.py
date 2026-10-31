import copy,importlib.util,sys,unittest,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
from aiwar.sdk import Environment
spec=importlib.util.spec_from_file_location('candidate',HERE/'agent.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class IndependentTests(unittest.TestCase):
    def world(self):
        env=Environment(seed=701891);w=env.world;w.terrain=[[0]*60 for _ in range(40)];w.hour=240
        for c in w.cities.values():c['food']=2000000
        return env,w
    def parties(self,w,n=0):return [u for u in w.units.values() if u['nation']==n and u['kind']=='party']
    def test_accepted_stop_clears_real_siege_before_contact(self):
        env,w=self.world();target=w.cities['c11'];depot=w.cities['c05'];own=self.parties(w)[:3]
        for p in own:p.update(x=target['x']-6500,y=target['y'],healthy=150,wounded=0,food=3000000,path=[],order=None)
        for p in own:self.assertTrue(w.command(0,dict(type='siege',unit=p['id'],target=target['id']))['ok'])
        w.units[target['garrison']]['healthy']=500
        for e in self.parties(w,1):e.update(x=target['x'],y=target['y'],healthy=150,wounded=0,path=[],order=None)
        pol=m.Policy();pol.initialized=True;pol.phase='engaged';pol.phase_at=w.hour;pol.target=target['id'];pol.depot=depot['id'];pol.cohort=[p['id'] for p in own];pol.sortie_strength=450
        cmds=pol.decide(w.observe(0));stops=[c for c in cmds if c['type']=='stop' and c['unit'] in pol.cohort]
        self.assertEqual(len(stops),3)
        for cmd in cmds:self.assertTrue(w.command(0,cmd)['ok'],cmd)
        w.step(6)
        for p in own:self.assertNotEqual((p.get('order') or {}).get('type'),'siege');self.assertIsNone(p['battle'])
    def test_stranded_then_actual_food_arrival_releases_state(self):
        env,w=self.world();c=w.cities['c00'];c['food']=0;c['neighbors']=[]
        for d in w.cities.values():d['neighbors']=[x for x in d['neighbors'] if x!=c['id']]
        u=self.parties(w)[0];u.update(x=c['x'],y=c['y'],healthy=40,wounded=0,food=0,path=[],order=None)
        pol=m.Policy();pol.initialized=True;pol.phase='economic';pol.economic_until=w.hour+168;pol.depot=c['id']
        first=pol.decide(w.observe(0));self.assertIn(u['id'],pol.stranded)
        self.assertFalse(any(x['type']=='transfer' and x['unit']==u['id'] for x in first))
        self.assertTrue(any(x['action']=='stranded' for x in pol.decisions))
        # Arrival is an externally constructed fixture fact, not policy-created food.
        c['food']=1500000;w.hour+=6
        second=pol.decide(w.observe(0));self.assertNotIn(u['id'],pol.stranded)
        self.assertTrue(any(x['type'] in ('move','create','transfer','set_strength') for x in second))
        for cmd in second:self.assertTrue(w.command(0,cmd)['ok'],cmd)
    def test_blocked_fresh_scout_enters_economic_not_same_siege(self):
        env,w=self.world();target=w.cities['c11'];depot=w.cities['c05'];own=self.parties(w)
        for u in own:u.update(x=target['x']-6500,y=target['y'],healthy=100,wounded=0,food=3000000,path=[],order=None)
        for e in self.parties(w,1):e.update(x=target['x'],y=target['y'],healthy=150,wounded=0,path=[],order=None)
        w.units[target['garrison']]['healthy']=500
        pol=m.Policy();pol.initialized=True;pol.phase='scout';pol.phase_at=0;pol.target=target['id'];pol.depot=depot['id'];pol.cohort=[p['id'] for p in own];pol.sortie_strength=600
        cmds=pol.decide(w.observe(0));self.assertEqual(pol.phase,'economic');self.assertIn(target['id'],pol.failures)
        self.assertFalse(any(c['type']=='siege' for c in cmds));self.assertTrue(any(c['type']=='move' for c in cmds))
        for cmd in cmds:self.assertTrue(w.command(0,cmd)['ok'],cmd)
        w.step(6)
        self.assertTrue(all(u['x']<target['x']-6500 for u in own))

if __name__=='__main__':unittest.main(verbosity=2)
