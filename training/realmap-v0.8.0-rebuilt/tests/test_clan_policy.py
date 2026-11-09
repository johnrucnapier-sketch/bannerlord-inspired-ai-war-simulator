import unittest
from unittest.mock import patch
from aiwar.clan_policy import ClanPlanner
from aiwar.vanilla_policy import decide
from aiwar.engine import World


def party(i,clan,x=0,y=0,army=None):
    return dict(id=i,clan=clan,nation=0,kind='party',x=x,y=y,healthy=100,wounded=0,food=1000000,
                army=army,battle=None,army_target='enemy',army_formed=0,
                order=dict(type='move',vanilla_task='muster',vanilla_target='enemy',vanilla_started=0,
                           vanilla_base='base',vanilla_expected=400))


def planner(parties):
    p=ClanPlanner.__new__(ClanPlanner)
    p.parties=parties;p.cmd=[];p.done=set();p.hour=1;p.sieged=set()
    p.bycity={'base':dict(id='base',x=0,y=0)}
    p.targets={'enemy':dict(id='enemy',x=4000,y=0,healthy=10,militia_healthy=0)}
    p.hostiles=[];p.armies={}
    for u in parties:
        if u['army']:p.armies.setdefault(u['army'],[]).append(u)
    p.days=lambda u:30;p.eta=lambda u,c:1;p.stage=lambda base,target:dict(x=2000,y=0)
    p.base=lambda u:p.bycity['base']
    return p


class ClanPolicyTests(unittest.TestCase):
    def test_far_sides_of_target_are_not_combined_strength(self):
        units=[party('a',1,2000),party('b',2,6000)]
        for u in units:u['order']['vanilla_task']='clan_campaign'
        p=planner(units);p.campaigns()
        self.assertFalse(any(c['type']=='siege' for c in p.cmd))
        units[1]['x']=2000;p=planner(units);p.campaigns()
        self.assertEqual({c['unit'] for c in p.cmd if c['type']=='siege'},{'a','b'})

    def test_visible_enemy_levy_counts_as_half_regular_strength(self):
        from aiwar.clan_policy import ClanLogisticsPlanner
        obs=World(1,{'mode':'realmap'}).observe(0)
        target=next(c for c in obs['cities'] if c['id'] in obs['frontier_targets'])
        before=ClanLogisticsPlanner(obs).defence(target)
        obs['units'].append(dict(id='visible-hostile-levy',kind='levy',nation=1,clan=17,
            x=target['x'],y=target['y'],healthy=1000,wounded=0,battle=None,army='enemy-army'))
        after=ClanLogisticsPlanner(obs).defence(target)
        self.assertEqual(after-before,500)

    def test_muster_assembles_clans_separately(self):
        units=[party('a',1),party('b',1),party('c',2),party('d',2)]
        p=planner(units);p.musters()
        assemblies=[c for c in p.cmd if c['type']=='assemble']
        self.assertEqual(len(assemblies),2)
        byid={u['id']:u for u in units}
        for c in assemblies:
            self.assertEqual(len({byid[i]['clan'] for i in [c['unit']]+c['units']}),1)
        moves=[c for c in p.cmd if c['type']=='move']
        self.assertEqual({c['unit'] for c in moves},{'a','c'})
        self.assertEqual({c['vanilla_target'] for c in moves},{'enemy'})

    def test_single_clan_members_remain_independent(self):
        units=[party('a',1),party('b',2)]
        p=planner(units);p.musters()
        self.assertFalse(any(c['type']=='assemble' for c in p.cmd))
        self.assertEqual({c['unit'] for c in p.cmd if c['type']=='move'},{'a','b'})

    def test_remote_promises_do_not_authorize_attack(self):
        units=[party('a',1,x=2000),party('b',2,x=0)]
        for u in units:u['order']['vanilla_task']='clan_campaign'
        p=planner(units);p.campaigns()
        self.assertFalse(any(c['type']=='siege' for c in p.cmd))
        units[1]['x']=2000
        p=planner(units);p.campaigns()
        self.assertEqual({c['unit'] for c in p.cmd if c['type']=='siege'},{'a','b'})
        self.assertFalse(any(c['type']=='assemble' for c in p.cmd))

    def test_existing_clan_armies_attack_independently(self):
        units=[party('a',1,2000,army='one'),party('b',1,2000,army='one'),
               party('c',2,2000,army='two'),party('d',2,2000,army='two')]
        for u in units:u['order']['vanilla_task']='clan_campaign'
        p=planner(units);p.campaigns()
        self.assertEqual({c['unit'] for c in p.cmd if c['type']=='siege'},{'a','c'})
        self.assertFalse(any(c['type'] in ('assemble','disband') for c in p.cmd))

    def test_relief_keeps_formations_separate(self):
        units=[party('a',1),party('b',2)]
        p=planner(units)
        p.o={'terrain':{},'relief_requests':[dict(assault_at=10,city='home',battle='siege',x=5000,y=0)]}
        p.safe=[p.bycity['base']]
        p.hostiles=[dict(id='hostile',kind='party',battle='siege',healthy=150,x=5000,y=0)]
        with patch('aiwar.clan_policy.find_route',return_value=[(0,0)]),patch('aiwar.clan_policy.relief_terrain',return_value={}):
            p.relief()
        self.assertEqual({c['unit'] for c in p.cmd if c['type']=='attack'},{'a','b'})
        self.assertFalse(any(c['type'] in ('assemble','disband') for c in p.cmd))
        units[1]['x']=1000
        p=planner(units);p.o={'terrain':{},'relief_requests':[dict(assault_at=10,city='home',battle='siege',x=5000,y=0)]}
        p.safe=[p.bycity['base']];p.hostiles=[dict(id='hostile',kind='party',battle='siege',healthy=150,x=5000,y=0)]
        with patch('aiwar.clan_policy.find_route',return_value=[(0,0)]),patch('aiwar.clan_policy.relief_terrain',return_value={}):
            p.relief()
        self.assertFalse(any(c['type']=='attack' for c in p.cmd))

    def test_existing_army_prevents_second_clan_army(self):
        existing=party('old',1,x=10000,army='already')
        units=[existing,party('a',1),party('b',1)]
        p=planner(units);p.musters()
        self.assertFalse(any(c['type']=='assemble' for c in p.cmd))
        self.assertEqual({c['unit'] for c in p.cmd if c['type']=='move'},{'a','b'})

    def test_multiple_musters_reserve_one_army_per_clan(self):
        units=[party('a',1),party('b',1),party('c',1),party('d',1)]
        for u in units[2:]:u['order']['vanilla_started']=1
        p=planner(units);p.musters()
        self.assertEqual(sum(c['type']=='assemble' for c in p.cmd),1)
        self.assertEqual({c['unit'] for c in p.cmd if c['type']=='move'},{'a','c','d'})

    def test_all_builtin_create_loops_respect_clan_caps(self):
        from aiwar import policies, policies_v014, policies_v015, policies_legacy, patrols
        world=World(1,{'mode':'realmap','days':1})
        obs=world.observe(0)
        parties=[u for u in obs['units'] if u['nation']==0 and u['kind']=='party']
        obs['limits']['clan_party_caps']={str(u['clan']):sum(v['clan']==u['clan'] for v in parties) for u in parties}
        # Make recruitment attractive; only the per-clan limit should block it.
        for c in obs['cities']:
            if c['nation']==0:c['recruits']=10000;c['food']=10000000
        cases=[('vanilla',decide,{}),('march',policies.decide,{}),
               ('v014',policies_v014.decide,{'rule_version':'0.1.4'}),
               ('v015',policies_v015.decide,{'rule_version':'0.1.5'}),
               ('legacy',policies_legacy.decide,{})]
        for name,fn,overrides in cases:
            with self.subTest(policy=name):
                self.assertFalse(any(c['type']=='create' for c in fn(dict(obs,**overrides))))
        # A filtered patrol subset must still count parties outside that subset.
        self.assertFalse(any(c['type']=='create' for c in patrols.decide(obs,'p3',available_ids=set())))

    def test_dispatch_preserves_legacy_path(self):
        obs=dict(mode='realmap',castle_logistics=True)
        with patch('aiwar.vanilla_policy.Planner') as old,patch('aiwar.clan_policy.decide',return_value=['clan']) as clan:
            old.return_value.run.return_value=['legacy']
            self.assertEqual(decide(obs),['legacy']);clan.assert_not_called()
            self.assertEqual(decide(dict(obs,organization={'army_scope':'clan'})),['clan'])

    def test_real_observations_generate_valid_commands(self):
        world=World(1,{'mode':'realmap','days':1})
        observations=[world.observe(n) for n in world.nation_ids()]
        batches=[decide(o) for o in observations]
        for n,commands in enumerate(batches):
            for c in commands:
                result=world.command(n,c)
                self.assertTrue(result['ok'],(n,c,result))
        world.check()

if __name__=='__main__':unittest.main()
