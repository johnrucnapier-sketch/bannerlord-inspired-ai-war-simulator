import copy
import gzip
import importlib.util
import json
import unittest
from pathlib import Path
from aiwar.engine import World
from aiwar.organization_policy import augment_commands,can_support,attached_members,combat_strength
from aiwar.clan_policy import ClanLogisticsPlanner
from aiwar.vanilla_policy import decide
from aiwar import organization


class OrganizationPolicyTests(unittest.TestCase):
    def test_recorded_natural_match_fog_failures(self):
        source=Path(__file__).with_name('data')/'fog_ownership_failure_r3.json.gz'
        if not source.is_file():self.skipTest('Optional local historical fixture is not distributed; synthetic fog coverage runs below')
        fixtures=json.loads(gzip.decompress(source.read_bytes()))['fixtures']
        policies=[('vanilla',decide)]
        from aiwar.strategy_catalog import ADAPTED_SOURCE
        if (ADAPTED_SOURCE/'agent.py').is_file():
            spec=importlib.util.spec_from_file_location('dev19_fog_regression',ADAPTED_SOURCE/'agent.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            policies.append(('dev19',module.decide))
        for fixture in fixtures:
            for request in (fixture['first_failure']['request'],fixture['last_healthy_request']):
                obs=request['observation'];before=copy.deepcopy(obs)
                for name,policy in policies:
                    with self.subTest(nation=obs['nation'],hour=obs['hour'],policy=name):
                        commands=policy(obs)
                        self.assertLessEqual(len(commands),100)
                        self.assertEqual(obs,before)

    def test_all_countries_ignore_former_owned_public_city(self):
        policies=[decide]
        from aiwar.strategy_catalog import ADAPTED_SOURCE
        if (ADAPTED_SOURCE/'agent.py').is_file():
            spec=importlib.util.spec_from_file_location('dev19_synthetic_fog_regression',ADAPTED_SOURCE/'agent.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            policies.append(module.decide)
        w=World(1,{'mode':'realmap'})
        for nation in w.nation_ids():
            obs=w.observe(nation)
            city=next(c for c in obs['cities'] if c['nation']==nation and 'food' in c)
            remembered=copy.deepcopy(w.known[str(nation)][city['id']]);remembered['stale']=True
            obs['cities']=[remembered if c['id']==city['id'] else c for c in obs['cities']]
            before=copy.deepcopy(obs)
            for policy in policies:
                commands=policy(obs)
                self.assertEqual(obs,before)
                self.assertFalse(any(c.get('city')==city['id'] for c in commands))

    def fixture(self):
        w=World(1,{'mode':'realmap','bandit_cap':0,'auto_city_service':False})
        clan=w.nations['0']['ruler_clan']
        leader=next(u for u in w.units.values() if u['kind']=='party' and u['clan']==clan)
        city=next(c for c in w.cities.values() if c['nation']==0 and c['clan']==clan and c.get('settlement_type')=='castle')
        support=next(u for u in w.units.values() if u['nation']==0 and u['kind']=='party' and w.clan_party_limit(u['clan'])==1)
        for u in (leader,support):u.update(x=city['x'],y=city['y'],healthy=150,wounded=0,food=600000)
        target=next(c['id'] for c in w.cities.values() if c['nation']!=0 and w.can_siege(0,c['id']))
        for u in (leader,support):
            u['order']=dict(type='move',x=city['x'],y=city['y'],vanilla_task='muster',vanilla_target=target,
                            vanilla_started=0,vanilla_base=city['id'],vanilla_expected=300,vanilla_wait_since=0)
        w.update_known()
        return w,leader,support,city,target

    def test_default_emits_lawful_local_ruler_support(self):
        w,leader,support,city,target=self.fixture()
        # Keep target estimate modest, without granting the planner hidden data.
        for uid in (w.cities[target]['garrison'],w.cities[target]['militia']):w.units[uid]['healthy']=0
        w.update_known();obs=w.observe(0);before=copy.deepcopy(obs)
        commands=decide(obs)
        assemblies=[c for c in commands if c['type']=='assemble' and c['unit']==leader['id']]
        self.assertTrue(assemblies,commands)
        self.assertIn(support['id'],assemblies[0]['units'])
        self.assertEqual(obs,before)
        for c in commands:self.assertTrue((r:=w.command(0,c))['ok'],(c,r))
        self.assertEqual(leader['army'],support['army'])

    def test_support_matches_engine_and_not_remote(self):
        w,leader,support,city,target=self.fixture();obs=w.observe(0)
        byid={u['id']:u for u in obs['units']}
        for unit in [u for u in w.units.values() if u['nation']==0 and u['kind']=='party' and u['clan']!=leader['clan']]:
            self.assertEqual(can_support(obs,byid[unit['id']],byid[leader['id']]),organization.can_support(w,unit,leader))
        cmds=[dict(type='move',unit=u['id'],x=city['x'],y=city['y'],vanilla_task='clan_campaign',vanilla_target=target) for u in (leader,support)]
        support['x']+=10000;w.update_known()
        self.assertFalse(any(c['type']=='assemble' for c in augment_commands(w.observe(0),cmds)))

    def test_rebuilt_ruler_or_marshal_party_cannot_start_second_army(self):
        for role in ('ruler','marshal'):
            for metadata in (True,False):
                with self.subTest(role=role,metadata=metadata):
                    w,leader,support,city,target=self.fixture()
                    if role=='marshal':
                        w.cfg['marshal_clans']={'0':leader['clan']}
                        w.nations['0']['ruler_clan']=support['clan']
                    family=[u for u in w.units.values() if u['kind']=='party'
                            and u['clan']==leader['clan'] and u['id']!=leader['id']]
                    for u in family:u.update(x=city['x'],y=city['y'])
                    first=dict(type='assemble',unit=family[0]['id'],units=[family[1]['id']])
                    self.assertTrue((r:=w.command(0,first))['ok'],r)
                    duplicate=dict(type='assemble',unit=leader['id'],units=[support['id']])
                    self.assertEqual(w.command(0,duplicate),dict(ok=False,error='同一家族最多拥有一个军团'))
                    w.update_known();obs=w.observe(0)
                    if not metadata:obs.pop('army_metadata')
                    byid={u['id']:u for u in obs['units']}
                    # Donor eligibility does not waive the receiver's army cap.
                    self.assertTrue(can_support(obs,byid[support['id']],byid[leader['id']]))
                    commands=[dict(type='move',unit=u['id'],x=city['x'],y=city['y'],
                                   vanilla_task='clan_campaign',vanilla_target=target) for u in (leader,support)]
                    before=copy.deepcopy(obs);original=copy.deepcopy(commands)
                    result=augment_commands(obs,commands)
                    self.assertEqual(result,original)
                    self.assertEqual(commands,original);self.assertEqual(obs,before)
                    for cmd in result:self.assertTrue((r:=w.command(0,cmd))['ok'],(cmd,r))
                    self.assertEqual(len(w.armies),1)

    def test_batch_reserves_host_clan_for_planned_or_added_army(self):
        for planned in (False,True):
            with self.subTest(planned=planned):
                w,leader,support,city,target=self.fixture()
                family=[u for u in w.units.values() if u['kind']=='party'
                        and u['clan']==leader['clan'] and u['id']!=leader['id']]
                other=family[-1]
                donor=next(u for u in w.units.values() if u['nation']==0 and u['kind']=='party'
                           and w.clan_party_limit(u['clan'])==1 and u['clan']!=support['clan'])
                for u in (other,donor):u.update(x=city['x']+2000,y=city['y'],healthy=150,wounded=0)
                commands=[]
                if planned:
                    family[0].update(x=city['x'],y=city['y'])
                    commands.append(dict(type='assemble',unit=leader['id'],units=[family[0]['id']],campaign_target=target))
                commands.extend(dict(type='move',unit=u['id'],x=u['x'],y=u['y'],
                                     vanilla_task='clan_campaign',vanilla_target=target) for u in (leader,other,support,donor))
                w.update_known();obs=w.observe(0);before=copy.deepcopy(obs);original=copy.deepcopy(commands)
                result=augment_commands(obs,commands)
                assemblies=[c for c in result if c['type']=='assemble']
                self.assertEqual(len(assemblies),1,assemblies)
                self.assertEqual(assemblies[0]['unit'],leader['id'])
                self.assertIn(support['id'],assemblies[0]['units'])
                self.assertTrue(any(c['type']=='move' and c['unit']==donor['id'] for c in result))
                self.assertEqual(commands,original);self.assertEqual(obs,before)
                for cmd in result:self.assertTrue((r:=w.command(0,cmd))['ok'],(cmd,r))
                self.assertEqual(len(w.armies),1)

    def test_support_membership_does_not_spend_host_clan_army_slot(self):
        w,ruler,support,city,target=self.fixture()
        marshal=next(u for u in w.units.values() if u['nation']==0 and u['kind']=='party'
                     and u['clan']!=ruler['clan'] and w.clan_party_limit(u['clan'])>=2)
        marshal.update(x=city['x'],y=city['y']);w.cfg['marshal_clans']={'0':marshal['clan']}
        self.assertTrue((r:=w.command(0,dict(type='assemble',unit=marshal['id'],units=[ruler['id']])))['ok'],r)
        leader=next(u for u in w.units.values() if u['kind']=='party'
                    and u['clan']==ruler['clan'] and not u['army'])
        leader.update(x=city['x'],y=city['y'])
        commands=[dict(type='move',unit=u['id'],x=city['x'],y=city['y'],
                       vanilla_task='clan_campaign',vanilla_target=target) for u in (leader,support)]
        w.update_known();obs=w.observe(0);before=copy.deepcopy(obs)
        result=augment_commands(obs,commands)
        assemblies=[c for c in result if c['type']=='assemble']
        self.assertEqual(len(assemblies),1)
        self.assertEqual(assemblies[0]['unit'],leader['id'])
        self.assertEqual(assemblies[0]['units'],[support['id']])
        self.assertEqual(obs,before)
        for cmd in result:self.assertTrue((r:=w.command(0,cmd))['ok'],(cmd,r))
        self.assertEqual(len(w.armies),2)
        self.assertNotEqual(leader['army'],ruler['army'])
        organization.check(w)

    def test_mobilize_existing_and_new_army_and_suppression(self):
        w,leader,support,city,target=self.fixture()
        # Visible foreign regular troops exceed the own national field strength.
        for u in w.units.values():
            if u['kind']=='party' and u['nation'] in (1,2):u.update(x=city['x'],y=city['y'],healthy=150)
        w.update_known();obs=w.observe(0)
        self.assertTrue(any(c['type']=='mobilize' for c in decide(obs)))
        assembly=dict(type='assemble',unit=leader['id'],units=[support['id']],campaign_target=target)
        commands=augment_commands(obs,[assembly])
        self.assertEqual([c['type'] for c in commands],['assemble','mobilize'])
        for c in commands:self.assertTrue((r:=w.command(0,c))['ok'],(c,r))
        self.assertFalse(any(c['type']=='mobilize' for c in augment_commands(w.observe(0),[])))
        # Fresh observations with insufficient courier food never request it.
        obs['cities']=copy.deepcopy(obs['cities'])
        next(c for c in obs['cities'] if c['id']==city['id'])['food']=0
        self.assertFalse(any(c['type']=='mobilize' for c in augment_commands(obs,[assembly])))
        # Existing family army uses its real ID, not a fabricated new army.
        fresh=w.observe(0);fresh['mobilizations']=[]
        self.assertEqual([c['army'] for c in augment_commands(fresh,[]) if c['type']=='mobilize'],[leader['army']])

    def test_demobilizes_only_ended_record(self):
        w,leader,support,city,target=self.fixture()
        w.command(0,dict(type='assemble',unit=leader['id'],units=[support['id']],campaign_target=target))
        obs=w.observe(0)
        obs['mobilizations']=[dict(id='mob-test',nation=0,clan=leader['clan'],army=leader['army'],rally=city['id'],started=0,rally_until=None,status='mobilizing')]
        self.assertFalse(any(c['type']=='demobilize' for c in augment_commands(obs,[])))
        commands=augment_commands(obs,[dict(type='disband',unit=leader['id'])])
        self.assertEqual(sum(c['type']=='demobilize' for c in commands),1)
        obs['mobilizations'][0]['demobilize_requested']=True
        self.assertFalse(any(c['type']=='demobilize' for c in augment_commands(obs,[dict(type='disband',unit=leader['id'])])))

    def test_remote_threatened_army_prepares_at_actual_own_castle(self):
        w,leader,support,city,target=self.fixture()
        w.command(0,dict(type='assemble',unit=leader['id'],units=[support['id']],campaign_target=target))
        # Public route, actual army food, and a private own-clan siege alert.
        obs=w.observe(0);before=copy.deepcopy(obs)
        own=[u for u in obs['units'] if u.get('army')==leader['army']]
        for u in own:u.update(x=u['x']+2000,food=900000)
        home=next(c for c in obs['cities'] if c.get('clan')==leader['clan'] and c['id']!=city['id'])
        obs['battles'].append(dict(id='own-siege',city=home['id']))
        from unittest.mock import patch
        with patch('aiwar.organization_policy.find_route',side_effect=lambda terrain,u,x,y:[[x,y]]):
            commands=augment_commands(obs,[])
        move=next(c for c in commands if c['type']=='move')
        self.assertEqual(move['vanilla_task'],'mobilization_prepare')
        self.assertEqual((move['x'],move['y']),(city['x'],city['y']))
        self.assertFalse(any(c['type']=='mobilize' for c in commands))
        # No actual state moved remotely by planning.
        self.assertEqual(w.observe(0),before)
        for u in own:u['order']=dict(move)
        obs['battles']=[b for b in obs['battles'] if b['id']!='own-siege']
        campaign=dict(type='move',unit=leader['id'],x=city['x']+9000,y=city['y'],vanilla_task='clan_campaign')
        self.assertEqual(augment_commands(obs,[campaign]),[campaign])
        obs['battles'].append(dict(id='own-siege',city=home['id']))
        for u in own:u['food']=1
        with patch('aiwar.organization_policy.find_route',side_effect=lambda terrain,u,x,y:[[x,y]]):
            self.assertFalse(any(c['type']=='move' for c in augment_commands(obs,[])))

    def test_collection_wait_resumes_and_does_not_override_combat(self):
        w,leader,support,city,target=self.fixture()
        w.command(0,dict(type='assemble',unit=leader['id'],units=[support['id']],campaign_target=target))
        obs=w.observe(0)
        obs['mobilizations']=[dict(id='mob-test',nation=0,clan=leader['clan'],army=leader['army'],
                                  rally=city['id'],started=0,rally_until=72,status='mobilizing')]
        original=dict(type='move',unit=leader['id'],x=city['x']+4000,y=city['y'],
                      west_task='clan_campaign',west_target=target,vanilla_target=target)
        commands=augment_commands(obs,[original])
        wait=next(c for c in commands if c['type']=='move')
        self.assertEqual(wait['vanilla_task'],'mobilization_rally')
        self.assertEqual(wait['west_target'],target)
        self.assertEqual((wait['x'],wait['y']),(city['x'],city['y']))
        attack=dict(type='attack',unit=leader['id'],target='visible-enemy')
        self.assertIn(attack,augment_commands(obs,[attack]))
        self.assertFalse(any(c['type']=='move' for c in augment_commands(obs,[attack])))
        relief=dict(original,vanilla_task='relief',relief_action='wait',relief_city=target)
        self.assertEqual(augment_commands(obs,[relief]),[relief])
        current=next(u for u in obs['units'] if u['id']==leader['id'])
        old=current['order'];current['order']=dict(relief)
        self.assertEqual(augment_commands(obs,[]),[])
        current['order']=old
        obs['hour']=72
        self.assertEqual(augment_commands(obs,[original]),[original])
        obs['mobilizations'][0]['rally_until']=None;obs['hour']=168
        self.assertEqual(augment_commands(obs,[original]),[original])
        obs['hour']=0
        for u in obs['units']:
            if u.get('army')==leader['army']:u['food']=1
        next(c for c in obs['cities'] if c['id']==city['id'])['food']=0
        self.assertEqual(augment_commands(obs,[original]),[original])

    def test_courier_preserves_planned_dispatch_rations_and_troops(self):
        w,leader,support,city,target=self.fixture()
        w.command(0,dict(type='assemble',unit=leader['id'],units=[support['id']],campaign_target=target))
        for u in w.units.values():
            if u['kind']=='party' and u['nation'] in (1,2):u.update(x=city['x'],y=city['y'],healthy=150)
        reserve=w.cfg['city_crew']*w.cfg['field_ration']*w.cfg['carry_days']
        city['food']=reserve+500
        destination=next(cid for cid in city['supply_neighbors'] if w.cities[cid]['nation']==0)
        dispatch=dict(type='dispatch',city=city['id'],destination=destination,mission='deliver',food=0)
        w.update_known();commands=augment_commands(w.observe(0),[dispatch])
        self.assertFalse(any(c['type']=='mobilize' for c in commands))
        for c in commands:self.assertTrue((r:=w.command(0,c))['ok'],(c,r))
        # A garrison transfer that uses its final body also outranks a courier.
        obs=w.observe(0);next(c for c in obs['cities'] if c['id']==city['id'])['food']=900000
        count=next(u for u in obs['units'] if u['id']==city['garrison'])['healthy']
        transfer=dict(type='transfer',unit=city['garrison'],target=leader['id'],count=count)
        self.assertFalse(any(c['type']=='mobilize' for c in augment_commands(obs,[transfer])))

    def test_attached_levy_has_real_food_and_half_strength(self):
        w,leader,support,city,target=self.fixture()
        w.command(0,dict(type='assemble',unit=leader['id'],units=[support['id']],campaign_target=target))
        obs=w.observe(0);regular=[u for u in obs['units'] if u.get('army')==leader['army']]
        levy=dict(id='test-levy',kind='levy',nation=0,clan=leader['clan'],army=leader['army'],healthy=100,wounded=20,food=120000,x=city['x'],y=city['y'],battle=None,order=None)
        obs['units'].append(levy)
        remote=dict(levy,id='not-attached',army=None);obs['units'].append(remote)
        group=attached_members(obs,regular)
        self.assertEqual(len(group),len(regular)+1)
        self.assertEqual(combat_strength(group),sum(u['healthy'] for u in regular)+50)
        planner=ClanLogisticsPlanner(obs)
        self.assertEqual(len(planner.armies[leader['army']]),len(group))
        self.assertNotIn(levy,planner.parties)
        expected=sum(u['food'] for u in group)/sum((u['healthy']+u['wounded'])*obs['limits']['field_ration'] for u in group)
        self.assertEqual(planner.group_days(planner.armies[leader['army']]),expected)

if __name__=='__main__':unittest.main()
