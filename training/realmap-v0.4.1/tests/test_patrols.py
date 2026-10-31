import copy
import tempfile
import unittest
from pathlib import Path
from tests.legacy_world import LegacyWorld as World
from aiwar.policies import decide
from aiwar.patrols import PATROLS
from aiwar.replay import replay


class PatrolTests(unittest.TestCase):
    def test_six_clans_three_parties_cap(self):
        w=World(1,{'mode':'rural'})
        self.assertEqual(len(w.cities),12)
        self.assertEqual({c['clan'] for c in w.cities.values()},set(range(6)))
        for clan in range(6):
            cities=[c for c in w.cities.values() if c['clan']==clan]
            self.assertEqual(len(cities),2)
            self.assertEqual(sum(u['kind']=='party' and u['clan']==clan for u in w.units.values()),2)
            cities[0]['recruits']=60
            self.assertTrue(w.command(0,dict(type='create',city=cities[0]['id'],count=30))['ok'])
            self.assertFalse(w.command(0,dict(type='create',city=cities[1]['id'],count=30,source='garrison'))['ok'])
        self.assertEqual(sum(u['kind']=='party' for u in w.units.values()),18)
        self.assertFalse(w.command(0,dict(type='create',city='c00',clan=6,count=1))['ok'])
        w.check()

    def test_observation_only_deterministic_valid_orders(self):
        for style in PATROLS:
            w=World(3,{'mode':'rural'})
            for _ in range(56):
                obs=w.observe(0);before=copy.deepcopy(obs)
                commands=decide(obs,style)
                self.assertEqual(obs,before)
                self.assertEqual(commands,decide(obs,style))
                self.assertLessEqual(len(commands),100)
                for command in commands:
                    result=w.command(0,command)
                    self.assertTrue(result['ok'],(style,command,result))
                w.step(6);w.check()
            self.assertLessEqual(sum(u['kind']=='party' for u in w.units.values()),18)

    def test_patrol_replay_and_duel_unchanged(self):
        w=World(1,{'mode':'rural'})
        for _ in range(12):
            for command in decide(w.observe(0),'p4'):w.command(0,command)
            w.step(6)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'save.json';w.save(path)
            self.assertEqual(replay(path).physics_digest(),w.physics_digest())
        duel=World(1)
        self.assertEqual(len({c['clan'] for c in duel.cities.values()}),12)
        self.assertEqual({c['nation'] for c in duel.cities.values()},{0,1})
