import tempfile
import unittest
from pathlib import Path
from tests.legacy_world import LegacyWorld as World
from aiwar.policies import decide
from aiwar.replay import replay

class RuralPartyCapTests(unittest.TestCase):
    def test_two_party_cap_rejects_third_and_allows_replacement(self):
        w=World(1,{'mode':'rural','clan_party_cap':2})
        self.assertEqual(w.cfg['clan_party_cap'],2)
        self.assertEqual(len({c['clan'] for c in w.cities.values()}),6)
        for clan in range(6):
            c=next(c for c in w.cities.values() if c['clan']==clan)
            self.assertFalse(w.command(0,dict(type='create',city=c['id'],count=30,source='garrison'))['ok'])
        party=next(u for u in w.units.values() if u['kind']=='party' and u['clan']==0)
        w.remove(party['id'])
        self.assertTrue(w.command(0,dict(type='create',city='c00',count=30,source='garrison'))['ok'])
        self.assertEqual(sum(u['kind']=='party' for u in w.units.values()),12)
        w.check()

    def test_default_and_replay(self):
        self.assertEqual(World(1,{'mode':'rural'}).cfg['clan_party_cap'],3)
        for invalid in (1,5,True):
            with self.assertRaises(ValueError):World(1,{'mode':'rural','clan_party_cap':invalid})
        w=World(1,{'mode':'rural','clan_party_cap':2})
        for _ in range(32):
            obs=w.observe(0)
            self.assertEqual(obs['limits']['clan_party_cap'],2)
            for cmd in decide(obs,'p5'):self.assertTrue(w.command(0,cmd)['ok'])
            w.step(6)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'save.json';w.save(path)
            loaded=World.load(path)
            self.assertEqual(loaded.cfg['clan_party_cap'],2)
            self.assertEqual(replay(path).physics_digest(),w.physics_digest())

    def test_four_party_cap_and_replay(self):
        w=World(1,{'mode':'rural','clan_party_cap':4})
        for clan in range(6):
            c=next(c for c in w.cities.values() if c['clan']==clan)
            c['recruits']=90
            for _ in range(2):
                self.assertTrue(w.command(0,dict(type='create',city=c['id'],count=30))['ok'])
            self.assertFalse(w.command(0,dict(type='create',city=c['id'],count=30))['ok'])
        self.assertEqual(sum(u['kind']=='party' for u in w.units.values()),24)
        w.check()
        # Replay a natural episode without unjournalled fixture stock changes.
        w=World(1,{'mode':'rural','clan_party_cap':4})
        for _ in range(112):
            obs=w.observe(0)
            self.assertEqual(obs['limits']['clan_party_cap'],4)
            for cmd in decide(obs,'p5'):self.assertTrue(w.command(0,cmd)['ok'])
            w.step(6)
        w.check()
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'save.json';w.save(path)
            self.assertEqual(World.load(path).cfg['clan_party_cap'],4)
            self.assertEqual(replay(path).physics_digest(),w.physics_digest())
