import importlib.util,unittest
from pathlib import Path
from aiwar.sdk import Environment
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('ar6_review_candidate',HERE/'agent.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Review(unittest.TestCase):
 def world(self):
  w=Environment(seed=701891).world;w.terrain=[[0]*60 for _ in range(40)];w.hour=240
  for c in w.cities.values():c['food']=2000000;w.units[c['garrison']]['healthy']=0
  own=[u for u in w.units.values() if u['nation']==0 and u['kind']=='party'];origin=w.cities['c00'];dest=w.cities['c01'];w.units[dest['garrison']]['healthy']=500
  for clan in range(6):
   while sum(u['kind']=='party' and u['clan']==clan for u in w.units.values())<3:w.new_unit('party',0,clan,150,origin['x'],origin['y'])
  own=[u for u in w.units.values() if u['nation']==0 and u['kind']=='party']
  for u in own:u.update(x=origin['x'],y=origin['y'],healthy=150,wounded=0,food=450000,path=[],order=None)
  p0=own[0];p0.update(healthy=3,food=9000)
  p=m.Policy();p.initialized=True;p.phase='economic';p.economic_until=1000;p.roles={u['id']:'war' for u in own}
  return w,p,p0,dest
 def test_same_turn_dispatched_food_not_promised(self):
  w,p,u,d=self.world();p.decide(w.observe(0));d=p.owned_cities[d['id']];d['food']=900000
  p.commands=[dict(type='dispatch',city=d['id'],destination=d['neighbors'][0],food=800000)]
  p.ordered=set();p.home_claims={};p.refit_routes={};p.refitting=set();p.evacuating=set();p.rotate_capacity()
  self.assertNotIn(u['id'],p.refit_routes)
 def test_expired_economy_resets_rally_epoch(self):
  w,p,u,d=self.world();u.update(healthy=150,food=450000);p.phase_at=0;p.economic_until=w.hour-1
  o=w.observe(0)
  for c in o['cities']:
   if c['nation']!=0:c['stale']=True
  p.decide(o);self.assertEqual(p.phase,'rally');self.assertEqual(p.phase_at,w.hour)
 def test_invalidated_assignment_physically_stops(self):
  w,p,u,d=self.world();cmds=p.decide(w.observe(0));self.assertIn(u['id'],p.refit_routes)
  for c in cmds:self.assertTrue(w.command(0,c)['ok'],c)
  self.assertTrue(u['path'])
  for c in w.cities.values():c['food']=0
  w.hour+=6;cmds=p.decide(w.observe(0))
  for c in cmds:self.assertTrue(w.command(0,c)['ok'],c)
  self.assertNotIn(u['id'],p.refit_routes);self.assertFalse(u['path'])
 def test_resident_automatic_surplus_not_double_promised(self):
  w,p,u,d=self.world();own=[x for x in w.units.values() if x['kind']=='party' and x['nation']==0]
  for q in own[:4]:q.update(healthy=19,food=57000)
  guard=own[-1];guard.update(x=d['x'],y=d['y'],healthy=20,food=60000,refill_target=20);p.roles[guard['id']]='guard'
  p.decide(w.observe(0));p.commands=[];p.home_claims={};p.ordered=set();p.evacuating=set();p.holding=set();p.refit_routes={};p.refitting=set();p.rotate_capacity()
  promised=sum(r['goal']-p.units[uid]['healthy'] for uid,r in p.refit_routes.items() if r['city']==d['id'])
  self.assertLessEqual(promised,400)
 def test_real_move_and_existing_reserve_refill(self):
  w,p,u,d=self.world();cmds=p.decide(w.observe(0));self.assertIn(u['id'],p.refit_routes);r=p.refit_routes[u['id']];d=w.cities[r['city']];g=w.units[d['garrison']];before=u['healthy']+g['healthy'];start=(u['x'],u['y']);food_before=u['food']+d['food']
  for c in cmds:self.assertTrue(w.command(0,c)['ok'],c)
  for _ in range(300):
   w.move_units();w.hour+=1
   if m.distance(u,d)<=500:break
  self.assertNotEqual(start,(u['x'],u['y']));self.assertLessEqual(m.distance(u,d),500);w.service_party(u,d)
  self.assertGreaterEqual(u['healthy'],120);self.assertEqual(before,u['healthy']+g['healthy']);self.assertEqual(food_before,u['food']+d['food'])
  p.decide(w.observe(0));self.assertNotIn(u['id'],p.refit_routes)
if __name__=='__main__':unittest.main(verbosity=2)
