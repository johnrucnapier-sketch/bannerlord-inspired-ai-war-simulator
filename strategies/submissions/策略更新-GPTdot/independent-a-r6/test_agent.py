"""Small, deterministic behavior checks. Not a competitive benchmark.
Run with PYTHONPATH=<repo>/game python test_agent.py from this directory.
"""
import copy
import importlib.util
import json
import pathlib
import unittest
from aiwar.sdk import Environment, command_error

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('candidate', HERE / 'agent.py')
a = importlib.util.module_from_spec(spec); spec.loader.exec_module(a)


def context(policy, observation):
    # Establish exactly the public fields without executing a trajectory.
    policy.initialized = True
    policy.decide(copy.deepcopy(observation))
    policy.commands = []; policy.pending = {}; policy.ordered = set(); policy.holding = set()
    policy.evacuating = set(); policy.home_claims = {}; policy.stranded = set(); policy.supplied_now = set()
    return policy


def fixture():
    env = Environment(seed=701220)
    w = env.world
    w.terrain = [[0]*60 for _ in range(40)]
    # Public fixture state only. Rules/configuration are unchanged.
    w.hour = 24
    for c in w.cities.values():
        c['food'] = 2000000
    return env


class StrategyTests(unittest.TestCase):
    def test_opening_commands_accepted(self):
        env = Environment(seed=701220); p = a.Policy()
        cmds = p.decide(env.observations()[0])
        self.assertTrue(all(command_error(c) is None for c in cmds))
        self.assertTrue(all(x['ok'] for x in env.step([cmds, []])['outcomes'][0]))
        self.assertFalse(any(c['type'] == 'assemble' for c in cmds))

    def test_empty_city_is_not_food_destination(self):
        env = fixture(); w=env.world; c=w.cities['c00']; c['food']=0
        u=next(u for u in w.units.values() if u['nation']==0 and u['kind']=='party')
        u.update(x=c['x'],y=c['y'],food=2000000)
        p=context(a.Policy(),w.observe(0)); home=p.safe_city(p.units[u['id']],True)
        self.assertIsNotNone(home); self.assertNotEqual(home['id'],c['id'])

    def test_unreachable_food_is_not_survivable(self):
        env=fixture(); w=env.world; c=w.cities['c00']; c['food']=0
        u=next(u for u in w.units.values() if u['nation']==0 and u['kind']=='party')
        u.update(x=c['x'],y=c['y'],food=0)
        p=context(a.Policy(),w.observe(0)); self.assertIsNone(p.safe_city(p.units[u['id']],True))

    def test_adjacent_dispatch_acceptance_and_delivery(self):
        env=fixture();w=env.world;c=w.cities['c00'];donor=w.cities['c01']
        c['food']=0
        # Short physical edge for finite mechanism test, not altered movement rules.
        donor.update(x=c['x']+2000,y=c['y'])
        for uid in [donor['garrison'],donor['militia']]:
            w.units[uid].update(x=donor['x'],y=donor['y'])
        w.units[donor['garrison']]['healthy']=100
        p=context(a.Policy(),w.observe(0)); p.logistics();cmds=p.finalize_commands()
        dispatches=[x for x in cmds if x['type']=='dispatch' and x['destination']=='c00']
        self.assertTrue(dispatches)
        outcomes=[w.command(0,x) for x in cmds];self.assertTrue(all(x['ok'] for x in outcomes),outcomes)
        w.step(24)
        self.assertGreater(c['food'],0)

    def test_disconnected_starvation_reports_stranded_not_fake_rescue(self):
        env=fixture();w=env.world;c=w.cities['c00'];c.update(food=0,neighbors=[])
        g=w.units[c['garrison']];g.update(healthy=0,wounded=0)
        for other in w.cities.values():
            other['neighbors']=[i for i in other['neighbors'] if i!='c00']
        u=next(u for u in w.units.values() if u['nation']==0 and u['kind']=='party')
        u.update(x=c['x'],y=c['y'],healthy=40,wounded=5,food=0,path=[],order=None)
        p=context(a.Policy(),w.observe(0));p.roles[u['id']]='war';p.stranded_recovery();cmds=p.finalize_commands()
        transfers=[x for x in cmds if x['type']=='transfer' and x['unit']==u['id']]
        self.assertFalse(transfers);self.assertFalse(any(x['type']=='dispatch' for x in cmds))
        self.assertIn(u['id'],p.stranded)
        self.assertTrue(any(d['action']=='stranded' for d in p.decisions))
        self.assertEqual(g['healthy'],0);self.assertIn(u['id'],w.units)

    def test_garrison_capacity_ledger(self):
        env=fixture();w=env.world;c=w.cities['c00'];g=w.units[c['garrison']];g.update(healthy=480,wounded=10)
        units=[u for u in w.units.values() if u['nation']==0 and u['kind']=='party'][:2]
        for u in units:u.update(x=c['x'],y=c['y'],healthy=40,wounded=0)
        p=context(a.Policy(),w.observe(0))
        for u in units:p.emit(dict(type='transfer',unit=u['id'],target=g['id'],count=40))
        cmds=p.finalize_commands();self.assertEqual(sum(x['count'] for x in cmds),10)
        self.assertTrue(all(w.command(0,x)['ok'] for x in cmds))

    def test_cooldown_releases_on_material_change(self):
        env=fixture();p=context(a.Policy(),env.observations()[0]);t=next(c for c in p.o['cities'] if c['nation']!=0)
        t=dict(t,stale=False,healthy=100,militia_healthy=100)
        p.remember_failure(t,[dict(healthy=300)],'fixture')
        self.assertTrue(p.target_blocked(t,[dict(healthy=300)]))
        self.assertFalse(p.target_blocked(t,[dict(healthy=600)]))
        self.assertFalse(p.target_blocked(dict(t,healthy=0,militia_healthy=50),[dict(healthy=300)]))

    def test_remembered_enemy_not_proven_absent(self):
        env=fixture();p=context(a.Policy(),env.observations()[0]);point=dict(x=60000,y=40000)
        p.enemies=[];p.last_enemies={'missing':dict(at=p.hour,unit=dict(healthy=100,**point))}
        self.assertEqual(p.field_risk(point),100)

    def test_funded_depot_claims_do_not_double_promise(self):
        env=fixture();w=env.world
        for c in w.cities.values():
            if c['nation']==0:c['food']=0
        c=w.cities['c00'];c['food']=150000
        units=[u for u in w.units.values() if u['nation']==0 and u['kind']=='party'][:2]
        for u in units:u.update(x=c['x'],y=c['y'],healthy=100,wounded=0,food=0)
        p=context(a.Policy(),w.observe(0));c=p.owned_cities[c['id']]
        c['food']=p.city_demand(c)+60000+p.refit_claim(p.units[units[0]['id']],c)+1000
        first=p.safe_city(p.units[units[0]['id']],True);self.assertEqual(first['id'],c['id'])
        p.move(p.units[units[0]['id']],first)
        self.assertIsNone(p.safe_city(p.units[units[1]['id']],True))

    def economic_fixture(self):
        env=fixture();w=env.world;depot=w.cities['c05']
        parties=[u for u in w.units.values() if u['kind']=='party' and u['nation']==0]
        for p in parties[:4]:p.update(x=depot['x'],y=depot['y'],healthy=100,wounded=0,food=3000000,path=[],order=None)
        for p in parties[4:]:del w.units[p['id']]
        for p in w.units.values():
            if p['kind']=='party' and p['nation']==1:p.update(x=110000,y=70000,path=[],order=None)
        v=w.villages['v110'];v.update(x=54000,y=68000,population=300,disabled_until=0,raid=None)
        w.update_known()
        p=context(a.Policy(),w.observe(0));p.roles={u['id']:'war' for u in p.parties}
        p.phase='economic';p.economic_until=w.hour+168;p.depot=depot['id'];p.target=None
        return env,p,v

    def test_blocked_campaign_chooses_real_economic_objective(self):
        env,p,v=self.economic_fixture();w=env.world
        p.campaign();cmds=p.finalize_commands()
        self.assertTrue(any(c['type']=='raid' and c['target']==v['id'] for c in cmds),cmds)
        self.assertTrue(all(w.command(0,c)['ok'] for c in cmds))
        w.step(48)
        self.assertLessEqual(v['population'],185)
        self.assertGreater(v['disabled_until'],w.hour)
        p.decide(w.observe(0));self.assertIsNone(p.operation)

    def test_operation_aborts_new_local_mass(self):
        env,p,v=self.economic_fixture();p.campaign()
        self.assertIsNotNone(p.operation)
        fake=dict(id='visible_new',kind='party',nation=1,healthy=500,wounded=0,x=v['x'],y=v['y'],battle=None)
        p.enemies.append(fake);p.units[fake['id']]=fake;p.commands=[];p.ordered=set()
        p.campaign();self.assertIsNone(p.operation)
        self.assertTrue(any(c['type']=='stop' for c in p.commands))

    def test_no_raid_of_depleted_or_disabled_village(self):
        env,p,v=self.economic_fixture()
        for obj in p.o['villages']:
            if obj['nation']!=0:obj.update(population=20,disabled_until=p.hour+168)
        p.campaign();self.assertFalse(any(c['type']=='raid' for c in p.commands))

    def test_economic_defense_targets_observed_corridor_threat(self):
        env,p,v=self.economic_fixture();w=env.world
        ownv=w.villages['v050'];ownv.update(x=53000,y=67000,population=500)
        enemy=next(u for u in w.units.values() if u['kind']=='party' and u['nation']==1)
        enemy.update(x=53000,y=67000,healthy=30,food=1000000,path=[],order=None)
        w.update_known()
        p=context(a.Policy(),w.observe(0));p.roles={u['id']:'war' for u in p.parties};p.phase='economic';p.economic_until=w.hour+168;p.depot='c05'
        p.campaign();cmds=p.finalize_commands()
        self.assertTrue(any(c['type']=='attack' and c['target']==enemy['id'] for c in cmds),cmds)
        self.assertTrue(all(w.command(0,c)['ok'] for c in cmds))
        w.step(72)
        self.assertNotIn(enemy['id'],w.units)

    def test_empty_recovery_depot_cannot_override_food_choice(self):
        env=fixture();w=env.world;c=w.cities['c00'];c['food']=0
        u=next(u for u in w.units.values() if u['kind']=='party' and u['nation']==0)
        u.update(x=c['x'],y=c['y'],food=1000000)
        p=context(a.Policy(),w.observe(0));p.depot='c00';p.phase='recover'
        p.move(p.units[u['id']],p.owned_cities['c00'])
        moves=[x for x in p.commands if x['type']=='move']
        self.assertTrue(moves)
        self.assertNotEqual((moves[0]['x'],moves[0]['y']),(c['x'],c['y']))

    def test_newly_unsafe_existing_route_is_stopped(self):
        env=fixture();w=env.world;c=w.cities['c00'];dest=w.cities['c01']
        u=next(u for u in w.units.values() if u['nation']==0 and u['kind']=='party')
        u.update(x=c['x']+2000,y=c['y'],healthy=30,food=900000,path=[],order=None)
        self.assertTrue(w.command(0,dict(type='move',unit=u['id'],x=dest['x'],y=dest['y']))['ok'])
        e=next(u for u in w.units.values() if u['nation']==1 and u['kind']=='party')
        e.update(x=u['path'][0][0],y=u['path'][0][1],healthy=300,path=[],order=None)
        p=context(a.Policy(),w.observe(0));p.move(p.units[u['id']],p.owned_cities[dest['id']])
        stops=[x for x in p.commands if x['type']=='stop' and x['unit']==u['id']]
        self.assertTrue(stops,p.commands)
        self.assertTrue(w.command(0,stops[0])['ok']);self.assertFalse(u['path']);self.assertIsNone(u['order'])

    def test_two_hungry_arrivals_not_promised_same_partial_stock(self):
        env=fixture();w=env.world;c=w.cities['c00']
        own=[u for u in w.units.values() if u['nation']==0 and u['kind']=='party']
        for other in w.cities.values():
            if other['nation']==0:other['food']=0
        for i,u in enumerate(own[:2]):u.update(x=c['x']+1000,y=c['y']+i*100,healthy=100,wounded=0,food=20000,refill_target=100,path=[],order=None)
        for u in own[2:]:u.update(x=45000,y=45000)
        w.units[c['garrison']]['healthy']=0
        p=context(a.Policy(),w.observe(0));city=p.owned_cities['c00']
        stock=p.city_demand(city)+60000+p.refit_claim(p.units[own[0]['id']],city)+100
        city['food']=c['food']=stock
        for u in own[:2]:p.move(p.units[u['id']],city)
        moves=[x for x in p.commands if x['type']=='move' and x.get('unit') in [u['id'] for u in own[:2]]]
        self.assertEqual(len(moves),1,p.commands)
        self.assertTrue(w.command(0,moves[0])['ok']);w.step(3)
        self.assertGreater(own[0]['food'],290000)
        self.assertEqual(own[1]['x'],c['x']+1000)
        self.assertGreater(c['food'],0)

    def test_empty_city_does_not_mobilize_or_automatic_refill_new_men(self):
        env=fixture();w=env.world;c=w.cities['c00'];c.update(food=0,neighbors=[])
        for d in w.cities.values():d['neighbors']=[x for x in d['neighbors'] if x!='c00']
        u=next(u for u in w.units.values() if u['nation']==0 and u['kind']=='party')
        u.update(x=c['x'],y=c['y'],healthy=40,wounded=0,food=0,refill_target=150,path=[],order=None)
        w.units[c['garrison']]['healthy']=80
        p=context(a.Policy(),w.observe(0));p.logistics();cmds=p.finalize_commands()
        self.assertFalse(any(x['type']=='create' and x['city']=='c00' for x in cmds))
        self.assertFalse(any(x['type']=='transfer' and x['unit']==c['garrison'] for x in cmds))
        for cmd in cmds:self.assertTrue(w.command(0,cmd)['ok'],cmd)
        before=u['healthy'];w.step(1);self.assertLessEqual(u['healthy'],before)

    def test_expired_failure_does_not_rescout_identical_observed_fortress(self):
        env=fixture();p=context(a.Policy(),env.observations()[0]);p.enemies=[]
        t=dict(next(c for c in p.o['cities'] if c['nation']!=0),stale=False,healthy=500,militia_healthy=200)
        p.remember_failure(t,[dict(healthy=300)],'fixture');p.hour+=1000
        self.assertTrue(p.target_blocked(t,[dict(healthy=300)]))
        self.assertFalse(p.target_blocked(dict(t,healthy=20,militia_healthy=20),[dict(healthy=300)]))

    def test_active_battle_is_not_canceled_on_cold_restart(self):
        env=fixture();w=env.world;u=next(u for u in w.units.values() if u['nation']==0 and u['kind']=='party')
        e=next(u for u in w.units.values() if u['nation']==1 and u['kind']=='party')
        u.update(x=60000,y=40000,healthy=150,food=450000);e.update(x=60000,y=40000,healthy=150,food=450000)
        self.assertTrue(w.command(0,dict(type='attack',unit=u['id'],target=e['id']))['ok'])
        w.step(1);self.assertIsNotNone(u['battle'])
        p=a.Policy();cmds=p.decide(w.observe(0))
        self.assertFalse(any(x.get('unit')==u['id'] and x['type'] in ('stop','move','transfer') for x in cmds))
        self.assertTrue(all(w.command(0,c)['ok'] for c in cmds))

    def test_fresh_affordable_alternate_city_outranks_raid(self):
        env,p,v=self.economic_fixture()
        t=next(c for c in p.o['cities'] if c['id']=='c11')
        t.update(stale=False,healthy=5,militia_healthy=5)
        p.o['frontier_targets']=['c11'];p.owned_cities['c05']['neighbors'].append('c11')
        p.economic_campaign(p.parties)
        self.assertEqual(p.phase,'rally');self.assertEqual(p.target,'c11')
        self.assertIsNone(p.operation)

    def test_cart_rendezvous_then_real_supply(self):
        env=fixture();w=env.world
        self.assertTrue(w.command(0,dict(type='dispatch',city='c00',destination='c01',food=200000))['ok'])
        cart=next(u for u in w.units.values() if u['kind']=='city_cart' and u['nation']==0)
        cart.update(x=62000,y=40000,path=[])
        u=next(u for u in w.units.values() if u['kind']=='party' and u['nation']==0)
        u.update(x=60000,y=40000,healthy=40,wounded=0,food=10000,path=[],order=None)
        for c in w.cities.values():
            if c['nation']==0:c['food']=0
        p=context(a.Policy(),w.observe(0));p.stranded_recovery()
        moves=[c for c in p.commands if c['type']=='move' and c['unit']==u['id']]
        self.assertTrue(moves);self.assertTrue(w.command(0,moves[0])['ok'])
        w.step(3);self.assertLessEqual(a.distance(u,cart),1000)
        p=context(a.Policy(),w.observe(0));p.logistics()
        supply=[c for c in p.commands if c['type']=='supply' and c['target']==u['id']]
        self.assertTrue(supply,p.commands);self.assertTrue(w.command(0,supply[0])['ok'])
        self.assertGreater(u['food'],10000)

    def test_constrained_city_preserves_dispatch_crew_and_local_floor(self):
        env=fixture();w=env.world;c=w.cities['c00'];g=w.units[c['garrison']]
        g.update(healthy=100,wounded=0)
        for u in w.units.values():
            if u['kind']=='party' and u['nation']==0:u.update(x=45000,y=45000)
        w.units[c['militia']]['healthy']=0
        e=next(u for u in w.units.values() if u['kind']=='party' and u['nation']==1)
        e.update(x=c['x'],y=c['y']+15000,healthy=50,path=[],order=None)
        p=context(a.Policy(),w.observe(0));p.enemies=[dict(e)]
        floor=p.defense_floor(p.owned_cities['c00']);self.assertEqual(floor,58)
        p.emit(dict(type='dispatch',city='c00',destination='c01',food=60000))
        p.emit(dict(type='create',city='c00',count=22,clan=0),'war')
        cmds=p.finalize_commands();self.assertTrue(all(w.command(0,c)['ok'] for c in cmds))
        self.assertEqual(g['healthy'],58)

    def test_expired_economic_window_reconsiders_real_operation(self):
        env,p,v=self.economic_fixture()
        p.o['frontier_targets']=[]
        p.economic_until=p.hour
        p.campaign();self.assertEqual(p.phase,'rally');self.assertIsNone(p.target)
        p.commands=[];p.ordered=set();p.campaign()
        self.assertEqual(p.phase,'economic');self.assertIsNotNone(p.operation)
        self.assertTrue(any(c['type']=='raid' and c['target']==v['id'] for c in p.commands))
        self.assertGreater(p.economic_until,p.hour)


if __name__=='__main__': unittest.main(verbosity=2)
