"""Targeted policy regressions, not a match benchmark.

Usage: HENGYUE_AGENT=/absolute/path/agent.py python3 test_hengyue.py -v
Synthetic *observation* fixtures isolate controller decisions. The food test
uses a synthetic late-game World state with unchanged engine code/config.
No game/release files are changed. Tests express desired corrected behavior.
"""
import copy
import importlib.util
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'game'))
from aiwar.engine import World
from aiwar.sdk import Environment, command_error
AGENT = Path(os.environ.get('HENGYUE_AGENT', str(Path(__file__).with_name('agent.py'))))
spec = importlib.util.spec_from_file_location('hengyue_under_test', AGENT)
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)


def siege_fixture(*, resident=False, unrelated=False):
    """National observation fixture: one nearby besieger; one 300-man relief force."""
    world = World(1)
    obs = world.observe(0)
    obs['hour'] = 240
    own_cities = [c for c in obs['cities'] if c['nation'] == 0]
    city = own_cities[0]
    nearest = min(own_cities[1:], key=lambda c: agent.dist(c, city))
    helper = agent.Policy()
    helper.terrain = obs['terrain']
    stage = helper.point(city, nearest, 4500)
    parties = [u for u in obs['units'] if u['nation'] == 0 and u['kind'] == 'party']
    reserve, first, second = parties[:3]
    selected = [reserve, first, second] if resident else [first, second]
    keep = {u['id'] for u in selected}
    obs['units'] = [u for u in obs['units'] if u['nation'] == 0 and (u['kind'] != 'party' or u['id'] in keep)]
    for u in obs['units']:
        if u['kind'] == 'garrison':
            u['healthy'] = 0  # Suppress unrelated new-party creation.
        if u['kind'] == 'party':
            u.update(healthy=150, wounded=0, food=450000, x=stage['x'], y=stage['y'], path=[], order=None, battle=None, refill_target=150)
    if resident:
        reserve.update(healthy=30, food=90000, x=city['x'], y=city['y'], battle='siege-test')
    enemy = dict(id='besieger-test',kind='party',nation=1,clan=6,x=city['x'],y=city['y'],healthy=30,wounded=0,battle='siege-test',army=None)
    obs['units'].append(enemy)
    if unrelated:
        # A stronger *unengaged* unit at another visible location is not a besieger.
        obs['units'].append(dict(enemy,id='unrelated-test',healthy=100,battle=None,x=nearest['x']+7000,y=nearest['y']))
    obs['battles'] = [dict(id='siege-test',x=city['x'],y=city['y'],start=210,days=1,city=city['id'],kind='siege',prepare_hours=72,paused_hours=0)]
    obs['relief_requests'] = [dict(city=city['id'],battle='siege-test',x=city['x'],y=city['y'],start=210,assault_at=282,phase='siege',relief_battle=None)]
    return obs, enemy, (first['id'], second['id'])


def physical_siege_fixture(relief_each):
    """Synthetic valid-capacity positions, then actual frozen-engine 72h preparation.

    No physics/config changes: the frontline city is legally besiegeable, units
    remain within 150/500/200 caps, and all subsequent attack commands are legal.
    """
    world=World(1)
    city=world.cities['c01']
    assert world.can_siege(1,city['id'])
    stage={'x':city['x'],'y':city['y']+3000}
    blue=[u for u in world.units.values() if u['kind']=='party' and u['nation']==0][:2]
    red=[u for u in world.units.values() if u['kind']=='party' and u['nation']==1][:2]
    for u in world.units.values():
        if u['kind']=='garrison' and u['nation']==0:u['healthy']=0
    world.units[city['garrison']]['healthy']=300
    world.units[city['militia']]['healthy']=100
    for u in blue:u.update(healthy=relief_each,food=relief_each*3000,x=stage['x'],y=stage['y'],refill_target=relief_each)
    for u in red:u.update(healthy=125,food=375000,x=city['x'],y=city['y'])
    battle=world.start_battle(red[0],world.units[city['garrison']],city['id'])
    assert battle is not None
    world.step(72)
    world.check()
    return world,tuple(u['id'] for u in red),tuple(u['id'] for u in blue)


class HengYueRegressionTests(unittest.TestCase):
    def test_initial_commands_sdk_legal_and_restart_safe(self):
        env = Environment(seed=971083)
        policy = agent.Policy()
        outcomes = []
        for tick in range(12):
            if tick == 6:
                policy = agent.Policy()  # Simulate agent process restart midgame.
            commands = policy.decide(env.observations()[0], outcomes)
            self.assertLessEqual(len(commands), 100)
            self.assertTrue(all(command_error(c) is None for c in commands))
            t = env.step([commands, []])
            outcomes = t['outcomes'][0]
            self.assertTrue(all(o['ok'] for o in outcomes), (tick, commands, outcomes))

    def test_resident_defender_does_not_block_external_relief(self):
        obs, enemy, relief_ids = siege_fixture(resident=True)
        commands = agent.Policy().decide(obs)
        for uid in relief_ids:
            self.assertTrue(any(c['type']=='attack' and c.get('unit')==uid and c.get('target')==enemy['id'] for c in commands), commands)

    def test_none_battle_does_not_include_remote_enemy_in_siege(self):
        obs, enemy, relief_ids = siege_fixture(unrelated=True)
        commands = agent.Policy().decide(obs)
        attacks = [c for c in commands if c['type']=='attack' and c.get('unit') in relief_ids]
        self.assertEqual(len(attacks), 2, commands)
        self.assertEqual({c['target'] for c in attacks}, {enemy['id']}, commands)

    def test_relief_attack_persists_between_stage_and_contact(self):
        obs, enemy, relief_ids = siege_fixture()
        policy = agent.Policy()
        commands = policy.decide(obs)
        self.assertEqual({c.get('unit') for c in commands if c['type']=='attack'}, set(relief_ids), commands)
        # Six hours later the force has left its staging point, but is still outside
        # the 1000-unit contact radius. Existing attack orders must keep advancing.
        later = copy.deepcopy(obs)
        later['hour'] += 6
        for p in later['units']:
            if p['id'] not in relief_ids:
                continue
            distance = agent.dist(p, enemy)
            p['x'] = round(p['x'] + (enemy['x']-p['x'])*2000/distance)
            p['y'] = round(p['y'] + (enemy['y']-p['y'])*2000/distance)
            p['order'] = {'type':'attack', 'unit':p['id'], 'target':enemy['id']}
            p['path'] = [[enemy['x'],enemy['y']]]
            self.assertGreater(agent.dist(p, enemy), 1000)
        commands = policy.decide(later)
        reversals = [c for c in commands if c.get('unit') in relief_ids and c['type'] in ('move','stop','raid','siege')]
        self.assertEqual(reversals, [], commands)

    def test_existing_relief_force_counts_toward_late_reinforcement(self):
        obs, enemy, relief_ids = siege_fixture()
        first, late = relief_ids
        for u in obs['units']:
            if u['id']==first:
                u.update(x=enemy['x'], y=enemy['y'], battle='relief-test')
            if u['id']==enemy['id']:
                u.update(healthy=200, battle='relief-test')
        obs['relief_requests'][0].update(phase='relief_field', relief_battle='relief-test')
        obs['battles'][0]['relief_battle']='relief-test'
        obs['battles'].append(dict(id='relief-test', x=enemy['x'], y=enemy['y'], start=234, days=2, city=None, kind='relief_field', prepare_hours=24, relief_for='siege-test'))
        commands=agent.Policy().decide(obs)
        joins=[c for c in commands if c.get('unit')==late and
               ((c['type']=='attack' and c.get('target')==enemy['id']) or
                (c['type']=='move' and abs(c['x']-enemy['x'])<500 and abs(c['y']-enemy['y'])<500))]
        self.assertTrue(joins, {'message':'150 engaged + 150 arriving should reinforce against 200, rather than ignore the engaged force', 'commands':commands})

    def test_relief_forecast_respects_damage_time_windows(self):
        # Same forces and approach across three physical phases. A 246-man relief
        # force cannot rely on city damage during preparation or paused field relief;
        # after actual assault begins, the 400 city defenders can reduce the besieger.
        for phase in ('preparation', 'assault', 'paused_field'):
            with self.subTest(phase=phase):
                obs, enemy, relief_ids = siege_fixture()
                request=obs['relief_requests'][0]
                city=next(c for c in obs['cities'] if c['id']==request['city'])
                parent=obs['battles'][0]
                parent.update(days=3, start=obs['hour']-72)
                request.update(phase='combat',assault_at=obs['hour'])
                for u in obs['units']:
                    if u['id'] in relief_ids:
                        u.update(healthy=123, food=369000)
                    if u['id']==enemy['id']:
                        u['healthy']=125
                    if u['id']==city['garrison']:
                        u.update(healthy=300,battle=request['battle'])
                    if u['id']==city['militia']:
                        u.update(healthy=100,battle=request['battle'])
                second_enemy=copy.deepcopy(next(u for u in obs['units'] if u['id']==enemy['id']))
                second_enemy['id']='window-second-besieger'
                obs['units'].append(second_enemy)
                enemy_ids={enemy['id'],second_enemy['id']}
                if phase=='preparation':
                    parent['start']=obs['hour']
                    request.update(phase='siege',assault_at=obs['hour']+72)
                elif phase=='paused_field':
                    request.update(phase='relief_field',relief_battle='window-field')
                    parent['relief_battle']='window-field'
                    for u in obs['units']:
                        if u['id'] in enemy_ids:u['battle']='window-field'
                    engaged=copy.deepcopy(next(u for u in obs['units'] if u['id']==relief_ids[0]))
                    engaged.update(id='window-engaged',healthy=10,food=30000,x=enemy['x'],y=enemy['y'],battle='window-field')
                    obs['units'].append(engaged)
                    obs['battles'].append(dict(id='window-field',x=enemy['x'],y=enemy['y'],start=obs['hour']-6,days=1,city=None,kind='relief_field',prepare_hours=24,relief_for=request['battle']))
                commands=agent.Policy().decide(obs)
                attacks=[c for c in commands if c.get('unit') in relief_ids and c['type']=='attack' and c.get('target') in enemy_ids]
                if phase=='assault':
                    self.assertEqual(len(attacks),2,commands)
                else:
                    self.assertEqual(attacks,[],commands)

    def test_forecast_matches_frozen_engine_first_contact_strength(self):
        # The oracle is World.move_units/contacts/battle_tick, not a duplicate of
        # the strategy's ETA or damage formula. Force the hypothetical attack in
        # a copy, then compare the actual enemy health when external relief starts.
        diagnostics=[]
        for total,should_attack in ((200,False),(246,True)):
            with self.subTest(relief=total):
                world,enemy_ids,relief_ids=physical_siege_fixture(total//2)
                obs=world.observe(0)
                commands=agent.Policy().decide(obs)
                oracle=copy.deepcopy(world)
                before=oracle.hour
                for uid in relief_ids:
                    result=oracle.command(0,{'type':'attack','unit':uid,'target':enemy_ids[0]})
                    self.assertTrue(result['ok'],result)
                for _ in range(24):
                    oracle.step(1)
                    if any(b.get('relief_for') for b in oracle.battles.values()):break
                else:self.fail('Expected physical contact within 24 hours')
                at_contact=sum(oracle.units[uid]['healthy'] for uid in enemy_ids)
                diagnostics.append({'relief':total,'enemy_at_contact':at_contact,'contact_after_hours':oracle.hour-before})
                if should_attack:self.assertGreater(total,at_contact)
                else:self.assertLess(total,at_contact)
                attacks=[c for c in commands if c.get('unit') in relief_ids and c['type']=='attack' and c.get('target') in enemy_ids]
                self.assertEqual(bool(attacks),should_attack,{'physical_oracle':diagnostics[-1],'commands':commands})
        print('First-contact oracle:',diagnostics,flush=True)

    def test_food_budget_survives_automatic_city_service(self):
        world = World(5)
        obs = world.observe(0)
        own_cities = [c for c in obs['cities'] if c['nation']==0]
        city = world.cities[own_cities[0]['id']]
        parties = [u for u in world.units.values() if u['nation']==0 and u['kind']=='party']
        party = min(parties, key=lambda u: agent.dist(u, city))
        garrison = world.units[city['garrison']]
        militia = world.units[city['militia']]
        # Synthetic but legal late-game resource quantities, with actual baseline rules.
        garrison.update(healthy=300, wounded=0)
        militia.update(healthy=100, wounded=0)
        city['food'] = 300000
        party.update(healthy=30, wounded=0, food=90000, refill_target=150)
        policy = agent.Policy()
        policy.initialized = True
        # Existing four guards avoid introducing a different creation budget here.
        policy.guard = {u['id']:{'x':u['x'],'y':u['y']} for u in parties if u['id']!=party['id']}
        policy.guard = dict(list(policy.guard.items())[:4])
        commands = policy.decide(world.observe(0))
        outcomes = [world.command(0,c) for c in commands]
        self.assertTrue(all(o['ok'] for o in outcomes), (commands,outcomes))
        world.step(1)  # departures/arrivals invoke automatic service, before daily food.
        self.assertGreaterEqual(city['food'], 80000,
            {'message':'Auto service consumed the four-day resident food reserve despite budgeted transfer',
             'party_health':party['healthy'],'garrison_health':garrison['healthy'],
             'city_food':city['food'],'commands':commands})


if __name__ == '__main__':
    print('Agent under test:', AGENT, flush=True)
    unittest.main()
