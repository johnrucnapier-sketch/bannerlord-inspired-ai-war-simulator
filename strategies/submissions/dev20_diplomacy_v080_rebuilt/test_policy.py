import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'training'/'realmap-v0.8.0-rebuilt'))
from aiwar import diplomacy_policy as p
spec = importlib.util.spec_from_file_location('rebuilt_adapter',Path(__file__).with_name('agent.py'))
a = importlib.util.module_from_spec(spec); spec.loader.exec_module(a)


def obs():
    return dict(nation=0,hour=0,limits=dict(party_cap=150,field_ration=100),
        units=[dict(id='own',nation=0,kind='party',healthy=150,wounded=0,food=450000)],
        cities=[dict(id='a',nation=0,neighbors=['b','c'],food=1000000),dict(id='b',nation=1,neighbors=['a']),dict(id='c',nation=2,neighbors=['a'])],
        villages=[],frontier_targets=['b','c'],diplomacy=dict(enabled=True,decision_due=True,incoming=[],outgoing=[],alliance_components=[[0],[1],[2]],
        public_relations={str(i):{str(j):'self' if i==j else 'war' for j in range(3)} for i in range(3)}))


def rel(o,x,y,value):
    for i,j in ((x,y),(y,x)):
        o['diplomacy']['public_relations'][str(i)][str(j)] = value


class PolicyTests(unittest.TestCase):
    def test_determinism_no_mutation(self):
        o=obs(); original=copy.deepcopy(o)
        self.assertEqual(p.decide(o),p.decide(copy.deepcopy(o)));self.assertEqual(o,original)
        self.assertIn('enemy_estimate',p.decide(o)[0]['reason'])

    def test_hidden_resources_not_read(self):
        o=obs(); other=copy.deepcopy(o);other['cities'][1].update(food=10**20,recruits=10**20)
        other['enemy_true_armies']=[dict(healthy=10**20)]
        self.assertEqual(p.decide(o),p.decide(other))

    def test_weekly_gate_and_immediate_reply(self):
        o=obs();o['diplomacy']['decision_due']=False;self.assertEqual(p.decide(o),[])
        o['diplomacy']['incoming']=[dict(id='p1',from_nation=1,to_nation=0,kind='peace',created_hour=0,expires_hour=168)]
        c=p.decide(o);self.assertEqual(len(c),1);self.assertEqual(c[0]['action'],'accept')

    def test_live_outgoing_prevents_duplicate_proposal(self):
        o=obs(); chosen=p.decide(o)[0]['target']
        o['diplomacy']['outgoing']=[dict(id='p1',from_nation=0,to_nation=chosen,kind='peace',created_hour=0,expires_hour=168)]
        self.assertFalse(any(c.get('target')==chosen for c in p.decide(o)))

    def test_busy_all_targets_issues_hold_not_duplicates(self):
        o=obs();o['diplomacy']['outgoing']=[dict(to_nation=i,expires_hour=168) for i in (1,2)]
        self.assertEqual(p.decide(o)[-1]['action'],'hold')

    def test_deployable_underfilled_party_not_emergency(self):
        o=obs();o['units'][0]['healthy']=40;rel(o,0,2,'peace');v=p.assessment(o)
        self.assertEqual(v['readiness'],1);self.assertLess(v['reinforcement_fill'],.3)
        self.assertLess(p.scores(o,v,1)['peace'],p.PARAMETERS['peace_threshold'])

    def test_food_shortage_increases_peace(self):
        o=obs();old=p.scores(o,p.assessment(o),1)['peace'];o['units'][0]['food']=1
        self.assertGreater(p.scores(o,p.assessment(o),1)['peace'],old)

    def test_imported_wars_and_nap_veto(self):
        o=obs();rel(o,0,1,'peace');old=p.scores(o,p.assessment(o),1)['alliance'];rel(o,0,2,'nap')
        self.assertLess(p.scores(o,p.assessment(o),1)['alliance'],old)
        self.assertFalse(p.alliance_feasible(o,1));rel(o,0,2,'peace');self.assertTrue(p.alliance_feasible(o,1))

    def test_nap_not_declared_on(self):
        o=obs();rel(o,0,1,'nap');rel(o,0,2,'nap')
        self.assertFalse(any(c['action']=='declare_war' for c in p.decide(o)))

    def test_filter_keeps_bandits_not_neutrals(self):
        o=obs();rel(o,0,1,'peace');o['units'] += [dict(id='neutral',nation=1),dict(id='bandit',nation=-1)]
        o['villages']=[dict(id='v1',nation=1),dict(id='v2',nation=2)]
        v=a.military_observation(o)
        self.assertEqual({u['id'] for u in v['units']},{'own','bandit'})
        self.assertEqual(v['frontier_targets'],['c']);self.assertEqual(v['villages'],[dict(id='v2',nation=2)])
        self.assertEqual(v['cities'][1]['nation'],1)

    def test_attack_and_move_audit_retains_recovery(self):
        o=obs();rel(o,0,1,'alliance');o['villages']=[dict(id='v1',nation=1)]
        cmds=[dict(type='siege',unit='own',target='b'),dict(type='raid',unit='own',target='v1'),
              dict(type='move',unit='own',west_target='b',west_task='scout',x=1,y=2),
              dict(type='move',unit='own',west_target='b',west_task='recover',x=0,y=0)]
        self.assertEqual(a.audit_commands(o,cmds),[dict(type='stop',unit='own'),dict(type='move',unit='own',west_task='recover',x=0,y=0)])

    def test_neutral_campaign_audit_does_not_leave_orphan_disband(self):
        o=obs();rel(o,0,1,'peace')
        tx=[dict(type='disband',unit='own'),dict(type='assemble',unit='own',units=['b'],campaign_target='b'),dict(type='move',unit='own',x=1,y=2,west_target='b')]
        self.assertEqual(a.audit_commands(o,tx),[])

    def test_transaction_safe_cap(self):
        prefix=[dict(type='stop',unit=str(i)) for i in range(98)]
        tx=[dict(type='disband',unit='a'),dict(type='assemble',unit='a',units=['b']),dict(type='move',unit='a',x=1,y=2)]
        self.assertEqual(a.bounded_military(prefix+tx,99),prefix)
        self.assertEqual(a.bounded_military(prefix+tx[1:],99),prefix)
        self.assertEqual(a.bounded_military(prefix+tx,101),prefix+tx)
        o=obs();o.update(mode='realmap',logistics_limits=dict(rations_separate=True))
        with patch.object(a.WesternPlanner,'__init__',return_value=None),patch.object(a.WesternPlanner,'run',return_value=prefix+tx[:2]),patch.object(p,'decide',return_value=[dict(type='diplomacy',action='hold')]):
            self.assertEqual(a.decide(o),[dict(type='diplomacy',action='hold')]+prefix)

    def test_vendored_baseline_exact(self):
        for name in ('agent.py','dev19_base.py','dev19_original.py'):
            self.assertEqual((a.BASE/name).read_bytes(),(ROOT/'strategies/submissions/dev20_cavalry_v070'/name).read_bytes())

    def test_engine_hold_consumes_gate_and_rejection_does_not_reopen_it(self):
        from aiwar.engine import World
        from aiwar import diplomacy
        w=World(13,dict(mode='realmap',diplomacy_enabled=True))
        self.assertEqual(w.cfg['diplomacy_event_cooldown_hours'],0)
        self.assertTrue(w.observe(0)['diplomacy']['decision_due'])
        self.assertTrue(w.command(0,dict(type='diplomacy',action='hold'))['ok'])
        self.assertFalse(w.observe(0)['diplomacy']['decision_due'])
        self.assertFalse(w.command(0,dict(type='diplomacy',action='propose_peace',target=1))['ok'])
        self.assertTrue(w.command(1,dict(type='diplomacy',action='propose_peace',target=0))['ok'])
        diplomacy.resolve(w)
        o=w.observe(0);self.assertTrue(o['diplomacy']['reply_due'])
        commands=p.decide(o)
        self.assertTrue(commands);self.assertTrue(all(c['action'] in ('accept','reject') for c in commands))
        pid=o['diplomacy']['incoming'][0]['id']
        self.assertTrue(w.command(0,dict(type='diplomacy',action='reject',proposal_id=pid))['ok'])
        diplomacy.resolve(w)
        self.assertEqual(p.decide(w.observe(0)),[])
        w.hour=168
        self.assertTrue(w.observe(0)['diplomacy']['decision_due'])

    def test_real_world_military_equivalence(self):
        from aiwar.engine import World
        w=World(13,dict(mode='realmap',diplomacy_enabled=False))
        for n in w.nation_ids():
            o=w.observe(n);self.assertEqual(a.decide(o),a._baseline.decide(o))
            o['diplomacy']=dict(enabled=True,public_relations={str(i):{str(j):'self' if i==j else 'war' for j in w.nation_ids()} for i in w.nation_ids()})
            self.assertEqual(a.WesternPlanner(o).run(),a._baseline.decide(o))


if __name__=='__main__':unittest.main()
