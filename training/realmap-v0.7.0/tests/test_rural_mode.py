import tempfile
import unittest
from pathlib import Path
from aiwar.engine import World
from aiwar.sdk import Environment


class RuralModeTests(unittest.TestCase):
    def test_single_nation_and_fixed_calendar(self):
        w = World(7, {'mode': 'rural', 'days': 1})
        self.assertEqual(w.cfg['days'], 840)
        self.assertEqual(len(w.cities), 12)
        self.assertEqual({c['nation'] for c in w.cities.values()}, {0})
        self.assertEqual({u['nation'] for u in w.units.values()}, {0})
        w.step(24)
        self.assertIsNone(w.result)
        self.assertEqual(w.rural_score()['population'], 7236)
        self.assertFalse(w.command(1, {'type': 'stop', 'unit': 'none'})['ok'])
        w.check()

    def test_population_counts_transport_and_losses(self):
        w = World(7, {'mode': 'rural'})
        score = w.rural_score()
        self.assertEqual(score['population'], 7200)
        cart = next(u for u in w.units.values() if u['kind'] == 'village_cart')
        cart['healthy'] -= 5
        self.assertEqual(w.rural_score()['population_gain'], -5)
        self.assertLess(w.rural_score()['population_retention'], 1)

    def test_terminal_and_save_load(self):
        w = World(7, {'mode': 'rural'})
        w.hour = 840 * 24 - 1
        w.finish()
        self.assertIsNone(w.result)
        w.step()
        self.assertEqual(w.result['reason'], 'rural_time_limit')
        self.assertEqual(w.result['hour'], 20160)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'save.json'
            w.save(path)
            restored = World.load(path)
            self.assertEqual(w.digest(), restored.digest())
        w.step(20)
        self.assertEqual(w.hour, 20160)

    def test_duel_default_and_sdk(self):
        w = World(7)
        self.assertEqual({c['nation'] for c in w.cities.values()}, {0, 1})
        self.assertEqual(w.cfg['days'], 1680)
        e = Environment(7, {'mode': 'rural'})
        with self.assertRaises(ValueError):
            e.step([[], [{'type': 'stop'}]])
        self.assertEqual(e.world.hour, 0)
        self.assertFalse(e.step([[], []])['terminated'])

if __name__ == '__main__': unittest.main()
