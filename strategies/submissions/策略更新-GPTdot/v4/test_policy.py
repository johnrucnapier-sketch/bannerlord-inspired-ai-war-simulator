"""Synthetic observation-only regression tests. No matches or hidden state."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('tested_v2_guard',HERE/'policy.py')
p=importlib.util.module_from_spec(spec);sys.modules[spec.name]=p;spec.loader.exec_module(p)
from scripts.escort_p5_defense_v2_policy import Controller as D2
from scripts.escort_p5_defense_policy import Controller as D1

def unit(uid,kind,nation,x,y,healthy,clan=0):
    return dict(id=uid,kind=kind,nation=nation,x=x,y=y,healthy=healthy,wounded=0,clan=clan,
        battle=None,army=None,food=healthy*100*30,order=None,path=[],refill_target=27,
        reserve_refill_target=0,home=None,last_battle=-1000,phase='idle')

def fixture(enemy=True, enemy_health=250, local_health=27, donor_health=60):
    cities=[];units=[];villages=[];controller=p.Controller(opening_guard=False,emergency_days=0)
    for i,(x,y) in enumerate(((30000,40000),(20000,40000),(20000,60000))):
        cid=f'c{i}';c=dict(id=cid,nation=0,x=x,y=y,clan=i,recruits=0,food=3000000,garrison=f'g{i}',militia=f'm{i}',neighbors=[f'c{j}' for j in range(3) if j!=i]+(['enemy'] if i==0 else []))
        cities.append(c);units.extend([unit(f'g{i}','garrison',0,x,y,0,i),unit(f'm{i}','militia',0,x,y,100,i)])
        for j in range(3):
            uid=f'p{i}{j}';units.append(unit(uid,'party',0,x,y,local_health if i==0 else donor_health,i))
            controller.assigned[(cid,j)]=uid;controller.targets[uid]=27
            villages.append(dict(id=f'v{i}{j}',nation=0,city=cid,x=x+3000*j,y=y+11000,cart=None))
    cities.append(dict(id='enemy',nation=1,x=60000,y=40000,healthy=50,militia_healthy=100,stale=False))
    if enemy:units.append(unit('foe','party',1,55000,40000,enemy_health,6))
    obs=dict(nation=0,hour=120,cities=cities,units=units,villages=villages,
        terrain=[[0]*60 for _ in range(40)],battles=[],relief_requests=[],frontier_targets=['enemy'],
        limits=dict(field_ration=100,carry_days=30,clan_party_cap=3,party_cap=150),
        speeds=dict(party=500,army=250,village_cart=250,city_cart=250,bandit=375,militia=0),
        direct_garrison_delivery=True)
    controller.bootstrapped=True
    return controller,obs

def emergency_fixture():
    c,o=fixture(enemy_health=350,local_health=27,donor_health=27)
    c.config=p.Config(emergency_days=30)
    # Six complete homes, 18 real mobile squads, no garrison recruits counted.
    for i,(x,y) in enumerate(((10000,40000),(20000,20000),(30000,20000)),3):
        cid=f'c{i}';o['cities'].append(dict(id=cid,nation=0,x=x,y=y,clan=i,recruits=999,
            food=3000000,garrison=f'g{i}',militia=f'm{i}',neighbors=['c0']))
        o['units'] += [unit(f'g{i}','garrison',0,x,y,500,i),unit(f'm{i}','militia',0,x,y,100,i)]
        for j in range(3):
            uid=f'p{i}{j}';o['units'].append(unit(uid,'party',0,x,y,27,i))
            c.assigned[(cid,j)]=uid;c.targets[uid]=27
            o['villages'].append(dict(id=f'v{i}{j}',nation=0,city=cid,x=x+3000*j,y=y+11000,cart=None))
    next(u for u in o['units'] if u['id']=='foe')['x']=48000
    return c,o

class Tests(unittest.TestCase):
    def test_immutable_v1_and_inherited_economy(self):
        v1=p.ROOT/'strategies/submissions/cloud_campaign_v7_min600/policy.py'
        if not v1.exists():v1=p.ROOT/'strategies/submissions/策略更新-GPTdot/policy.py'
        self.assertEqual(hashlib.sha256(v1.read_bytes()).hexdigest(),'1aed9815302f846238d4756c378b7161ba2170869008205a20662b1a96ba6c44')
        self.assertIs(p.Controller.decide,D2.decide)
        self.assertIs(p.Controller.escort_order,D1.escort_order)
        self.assertEqual(p.Config().attack_minimum,600)
        self.assertFalse(p.Config().opening_guard)

    def test_returning_mission_counts_toward_rear_coverage(self):
        c,o=fixture(False,local_health=150,donor_health=150)
        c.config=p.Config(require_switched=False,opening_guard=False)
        c.guard_ids={'p00'}
        c.missions={'p01':dict(home='c0',phase='return')}
        next(u for u in o['units'] if u['id']=='p01')['x']=10000
        c.campaign_military(o)
        self.assertNotIn('p02',c.missions)

    def test_observed_full_defender_threshold(self):
        c,o=fixture(False);t=o['cities'][-1]
        o['units'] += [unit('guard','party',1,60000,40000,200),unit('near','party',1,67000,40000,100),unit('far','party',1,80000,40000,999),unit('cart','village_cart',1,60000,40000,20)]
        self.assertEqual(c.siege_strength(o,t), (350+120)*(4*350+2*120))
        self.assertEqual(c.siege_strength(o,t,False),(250+120)*(4*250+2*120))
        self.assertGreater(c.attack_requirement(o,t,True),180)

    def test_stale_friendly_flag_does_not_count_own_army(self):
        c,o=fixture(False);t=o['cities'][-1];t.update(nation=0,stale=True)
        o['units'] += [unit('ours','party',0,60000,40000,999),unit('theirs','party',1,60000,40000,100)]
        self.assertEqual(c.siege_strength(o,t),(150+100)*(4*150+2*100))

    def test_guard_quadratic_minimum(self):
        for g,m,a in ((0,107,350),(50,100,400),(500,200,100)):
            d=c=p.Controller.guard_requirement(g,m,a,1.2)
            self.assertGreaterEqual((g+d+m)*(4*(g+d)+2*m),2*(1.2*a)**2)
            if d:self.assertLess((g+d-1+m)*(4*(g+d-1)+2*m),2*(1.2*a)**2)

    def test_complete_timely_guard_and_rear_floor(self):
        c,o=fixture();commands=c.plan_guards(o)
        self.assertIn('c0',c.guard_covered)
        self.assertGreaterEqual(sum(u['healthy'] for u in o['units'] if u['id'] in c.guards),139)
        self.assertLessEqual(sum(r['home']=='c1' for r in c.guards.values()),2)
        self.assertTrue(all(cmd['type']!='siege' for cmd in commands))

    def test_late_partial_reinforcement_is_rejected(self):
        c,o=fixture(enemy_health=350)
        for u in o['units']:
            if u['id']=='foe':u['x']=35000
        self.assertEqual(c.plan_guards(o),[])
        self.assertEqual(c.guards,{})

    def test_no_siege_late_join(self):
        c,o=fixture();o['battles']=[dict(id='b1',city='c0')]
        commands=c.plan_guards(o)
        self.assertFalse(c.guards)
        self.assertFalse(any(x.get('campaign_phase')=='city_guard' for x in commands))

    def test_food_shortage_does_not_count_as_reinforcement(self):
        c,o=fixture(enemy_health=350)
        for u in o['units']:
            if u['id'].startswith('p1') or u['id'].startswith('p2'):u['food']=0
        self.assertFalse(c.plan_guards(o))
        self.assertFalse(c.guards)

    def test_reservations_protect_from_economy_overwrite(self):
        c,o=fixture();before=copy.deepcopy(o);commands=c.decide(o)
        guarded=set(c.guards)
        self.assertTrue(guarded)
        self.assertTrue(all(c.missions[uid]['role']=='guard' for uid in guarded))
        for cmd in commands:
            if cmd.get('unit') in guarded and cmd['type']=='move':
                self.assertEqual(cmd.get('campaign_phase'),'city_guard')
        self.assertEqual(o,before)

    def test_guard_release_after_clear_cooldown(self):
        c,o=fixture();c.plan_guards(o);self.assertTrue(c.guards)
        o['units']=[u for u in o['units'] if u['id']!='foe'];o['hour']=167
        c.plan_guards(o);self.assertTrue(c.guards)
        o['hour']=168;c.plan_guards(o);self.assertFalse(c.guards)
        self.assertTrue(any(m['phase']=='return' for m in c.missions.values()))

    def test_guard_return_restores_prior_economy_target(self):
        c,o=fixture();c.plan_guards(o)
        o['units']=[u for u in o['units'] if u['id']!='foe'];o['hour']=168
        prior=set(c.guards);c.plan_guards(o);c.campaign_military(o)
        self.assertTrue(prior)
        for uid in prior:
            if uid not in c.missions:
                self.assertEqual(c.targets[uid],27)

    def test_bootstrap_identical_to_frozen_d2(self):
        c,o=fixture(False);o['hour']=0
        o['units']=[u for u in o['units'] if u['kind']!='party' or u['id'].endswith('0')]
        for u in o['units']:
            if u['kind']=='party':u['healthy']=30
            elif u['kind']=='garrison':u['healthy']=50
        self.assertEqual(p.Controller().decide(o),D2().decide(o))

    def test_guard_in_battle_has_no_commands(self):
        c,o=fixture();c.plan_guards(o);uid=next(iter(c.guards))
        for u in o['units']:
            if u['id']==uid:u['battle']='b1'
        o['battles']=[dict(id='b1',city='c0')]
        commands=c.plan_guards(o)
        self.assertIn(uid,c.guards)
        self.assertFalse(any(x.get('unit')==uid for x in commands))

    def test_opening_disabled_is_noop_without_threat(self):
        c,o=fixture(False);self.assertFalse(c.plan_guards(o));self.assertFalse(c.guards)

    def test_opening_optional_preserves_all_home_coverage(self):
        c,o=fixture(False,donor_health=60);c.config=p.Config(opening_guard=True)
        c.plan_guards(o);self.assertEqual(c.opening_city,'c0');self.assertTrue(c.guards)
        for cid in ('c0','c1','c2'):
            self.assertLessEqual(sum(r['home']==cid for r in c.guards.values()),2)

    def test_opening_before_first_economic_assignment(self):
        c,o=fixture(False,local_health=27,donor_health=27);o['hour']=6
        o['cities'][0]['neighbors'].append('c3')
        o['cities'].append(dict(id='c3',nation=0,x=20000,y=20000,clan=3,recruits=0,food=3000000,garrison='g3',militia='m3',neighbors=['c0']))
        o['units'] += [unit('g3','garrison',0,20000,20000,0,3),unit('m3','militia',0,20000,20000,100,3)]
        o['units'] += [unit('p3'+str(j),'party',0,20000,20000,27,3) for j in range(3)]
        c.assigned={};c.targets={};c.config=p.Config(opening_guard=True)
        c.plan_guards(o)
        self.assertEqual(len(c.guards),7)
        self.assertEqual(sum(u['healthy'] for u in o['units'] if u['id'] in c.guards),189)
        self.assertTrue(all(r['restore_target']==27 for r in c.guards.values()))
        for cid in ('c0','c1','c2','c3'):
            self.assertLessEqual(sum(r['home']==cid for r in c.guards.values()),2)

    def test_fragmented_army_cannot_siege(self):
        c,o=fixture(False);o['hour']=200
        for u in o['units']:
            if u['id'] in ('p00','p01'):
                u['healthy']=150;u['food']=150*100*30
                u['army']=None
        next(u for u in o['units'] if u['id']=='p01')['x']=20000
        c.missions={uid:dict(home='c0',phase='field') for uid in ('p00','p01')}
        c.campaign=dict(kind='attack',target='enemy',stage=dict(x=30000,y=40000),required=300,start=100,last_seen=100,serial=1,launched=True)
        commands=c.campaign_military(o)
        self.assertFalse(any(x['type']=='siege' for x in commands))
        self.assertIsNone(c.campaign)
        self.assertEqual(c.war_events[-1]['reason'],'formation_fragmented')

    def test_lost_home_does_not_disband_valid_field_army(self):
        c,o=fixture(False);o['hour']=200
        for u in o['units']:
            if u['id'] in ('p00','p01'):
                u['healthy']=150;u['food']=150*100*30;u['army']='army'
        c.missions={uid:dict(home='captured_home',phase='field') for uid in ('p00','p01')}
        c.campaign=dict(kind='attack',target='enemy',stage=dict(x=30000,y=40000),required=300,start=100,last_seen=100,serial=1,launched=True)
        commands=c.campaign_military(o)
        self.assertFalse(any(x['type']=='disband' for x in commands))
        self.assertTrue(any(x['type']=='siege' for x in commands))

class EmergencyTests(unittest.TestCase):
    def test_early_visibility_and_outside_staging(self):
        c,o=emergency_fixture();commands=c.military(o)
        self.assertTrue(c.campaign['emergency'])
        self.assertEqual(c.campaign['kind'],'defense')
        self.assertGreaterEqual(p.distance(c.campaign['stage'],o['cities'][0]),3900)
        self.assertFalse(any(x.get('relief_action')=='wait' for x in commands))
        self.assertFalse(any(x['type']=='attack' for x in commands))
        self.assertTrue(any(x['type']=='move' and x.get('campaign_phase')=='cloud_stage' for x in commands))

    def test_sixteen_actual_squads_with_two_global_keepers(self):
        c,o=emergency_fixture();c.military(o)
        self.assertEqual(len(c.missions),16)
        self.assertEqual(sum(m['expected'] for m in c.missions.values()),432)
        self.assertEqual(c.campaign['required'],420)
        self.assertGreater(max(sum(m['home']==cid for m in c.missions.values()) for cid in ('c0','c1','c2','c3','c4','c5')),2)
        self.assertTrue(all(m['restore_economy_target']==27 for m in c.missions.values()))

    def test_no_imaginary_garrison_or_recruit_strength(self):
        c,o=emergency_fixture()
        for u in o['units']:
            if u['nation']==0 and u['kind']=='party':u['healthy']=20;u['food']=60000
        commands=c.military(o)
        self.assertIsNone(c.campaign)
        self.assertFalse(any(x['type'] in ('transfer','recruit') for x in commands))

    def test_food_shortage_blocks_unfunded_trip(self):
        c,o=emergency_fixture()
        for u in o['units']:
            if u['nation']==0 and u['kind']=='party':u['food']=0
        c.military(o)
        self.assertIsNone(c.campaign)

    def test_after_cutoff_normal_home_floor_is_restored(self):
        c,o=emergency_fixture();o['hour']=30*24
        next(u for u in o['units'] if u['id']=='foe')['x']=35000
        c.military(o)
        self.assertIsNone(c.campaign)  # 12*27 < 1.2*350; no early exception.
        self.assertFalse(c.early_threats(o))

    def test_actual_arrived_quorum_not_remote_roster(self):
        c,o=emergency_fixture();c.military(o);stage=c.campaign['stage']
        for i,uid in enumerate(c.missions):
            if i<3:
                u=next(u for u in o['units'] if u['id']==uid);u.update(x=stage['x'],y=stage['y'])
        o['hour']+=6;commands=c.military(o)
        self.assertFalse(c.campaign['launched'])
        self.assertFalse(any(x['type'] in ('assemble','attack') for x in commands))

    def test_only_complete_co_located_force_launches_external_relief(self):
        c,o=emergency_fixture();c.military(o);stage=c.campaign['stage']
        for uid in c.missions:
            u=next(u for u in o['units'] if u['id']==uid);u.update(x=stage['x'],y=stage['y'])
        foe=next(u for u in o['units'] if u['id']=='foe');foe.update(x=30000,y=40000,battle='siege1')
        o['hour']=180;o['battles']=[dict(id='siege1',city='c0')]
        o['relief_requests']=[dict(city='c0',battle='siege1',relief_battle=None,x=30000,y=40000,assault_at=239)]
        commands=c.military(o)
        self.assertTrue(c.campaign['launched'])
        self.assertEqual(sum(x['type']=='assemble' for x in commands),1)
        self.assertEqual(sum(x['type']=='attack' and x['target']=='foe' for x in commands),1)
        self.assertFalse(any(x['type']=='siege' for x in commands))

    def test_clear_returns_original_targets(self):
        c,o=emergency_fixture();c.military(o);selected=set(c.missions)
        o['units']=[u for u in o['units'] if u['id']!='foe'];o['hour']+=24
        c.military(o)
        self.assertIsNone(c.campaign)
        self.assertTrue(all(c.targets[uid]==27 for uid in selected))
        self.assertTrue(all(m['phase']=='return' for m in c.missions.values()))

    def test_early_exception_ends_after_thirty_days(self):
        c,o=emergency_fixture();c.military(o);o['hour']=720
        c.military(o)
        self.assertIsNone(c.campaign)
        self.assertTrue(all(m['phase']=='return' for m in c.missions.values()))

if __name__=='__main__':unittest.main(verbosity=2)
