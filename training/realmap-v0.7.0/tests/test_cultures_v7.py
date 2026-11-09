"""Paired deterministic checks for all six culture traits and owner changes."""
import copy
import unittest
from types import SimpleNamespace

from aiwar import cultures


NAMES = ('empire', 'khuzait', 'vlandia', 'battania', 'sturgia', 'aserai')


def world(enabled=True):
    return SimpleNamespace(
        cfg={'culture_traits': enabled, 'militia_cap': 200},
        nations={str(i): {'culture': name} for i, name in enumerate(NAMES)},
        cities={'castle': {'settlement_type': 'castle'}, 'town': {'settlement_type': 'town'}},
        size=lambda u: u['healthy'] + u['wounded'])


def village(nation, city='castle', population=200):
    return {'nation': nation, 'city': city, 'population': population}


class CultureRules(unittest.TestCase):
    def test_default_enabled_and_unknown_owner(self):
        w = world()
        del w.cfg['culture_traits']
        self.assertTrue(cultures.enabled(w))
        self.assertEqual(cultures.militia_cap(w, {'nation': 3}), 250)
        self.assertIsNone(cultures.culture(w, 'missing'))
        self.assertEqual(cultures.militia_cap(w, {'nation': 'missing'}), 200)

    def test_world_culture_method_supported(self):
        w = world()
        w.culture = lambda n: 'battania' if n == 'new-owner' else None
        self.assertEqual(cultures.militia_cap(w, {'nation': 'new-owner'}), 250)
        self.assertEqual(cultures.militia_cap(w, {'nation': 3}), 200)

    def test_empire_garrison_only_and_no_other_nation(self):
        for n in range(6):
            for kind in ('garrison', 'militia', 'party', 'patrol', 'city_cart', 'village_cart', 'caravan'):
                u = {'nation': n, 'kind': kind, 'healthy': 90, 'wounded': 10}
                expected = 4500 if n == 0 and kind == 'garrison' else 5000
                self.assertEqual(cultures.city_food_need(world(), u, 50), expected)
                self.assertEqual(cultures.city_food_need(world(False), u, 50), 5000)

    def test_food_rounding_does_not_overdiscount(self):
        u = {'nation': 0, 'kind': 'garrison', 'healthy': 1, 'wounded': 0}
        self.assertEqual(cultures.city_food_need(world(), u, 1), 1)

    def test_training_seven_days_except_khuzait_castle(self):
        for n in range(6):
            for kind in ('castle', 'town'):
                c = {'nation': n, 'settlement_type': kind}
                self.assertEqual(cultures.training_hours(world(), c), 144 if n == 1 and kind == 'castle' else 168)
                self.assertEqual(cultures.training_hours(world(False), c), 168)

    def test_battania_cap_only(self):
        for n in range(6):
            self.assertEqual(cultures.militia_cap(world(), {'nation': n}), 250 if n == 3 else 200)
            self.assertEqual(cultures.militia_cap(world(False), {'nation': n}), 200)

    def test_village_food_scope_and_disabled_pair(self):
        for n in range(6):
            for city in ('castle', 'town'):
                v = village(n, city)
                boosted = n == 4 or (n == 2 and city == 'castle')
                self.assertEqual(cultures.weekly_yields(world(), v), (220000 if boosted else 200000, 2))
                self.assertEqual(cultures.weekly_yields(world(False), v), (200000, 2))

    def test_recruit_fraction_is_exact_and_deterministic(self):
        w = world()
        a, b = village(2), village(2)
        series_a = [cultures.weekly_yields(w, a)[1] for _ in range(10)]
        series_b = [cultures.weekly_yields(w, b)[1] for _ in range(10)]
        self.assertEqual(series_a, [2, 2, 2, 2, 3, 2, 2, 2, 2, 3])
        self.assertEqual(series_a, series_b)
        self.assertEqual(sum(series_a), 22)
        self.assertEqual(a['culture_recruit_remainder'], 0)
        for n in (0, 1, 3, 4, 5):
            v = village(n)
            self.assertEqual(sum(cultures.weekly_yields(w, v)[1] for _ in range(10)), 20)
            self.assertNotIn('culture_recruit_remainder', v)

    def test_fraction_can_be_serialized_and_disabled_does_not_advance(self):
        w = world()
        v = village(2)
        for _ in range(4):
            cultures.weekly_yields(w, v)
        saved = copy.deepcopy(v)
        self.assertEqual(cultures.weekly_yields(world(False), v), (200000, 2))
        self.assertEqual(v, saved)
        self.assertEqual(cultures.weekly_yields(w, v), cultures.weekly_yields(w, saved))
        self.assertEqual(v['culture_recruit_remainder'], 0)

    def test_aserai_only_supply_transport(self):
        for n in range(6):
            for kind in ('city_cart', 'village_cart', 'caravan', 'merchant_caravan', 'party'):
                u = {'nation': n, 'kind': kind}
                self.assertEqual(cultures.transport_speed(world(), u, 250), 275 if n == 5 and kind == 'city_cart' else 250)
                self.assertEqual(cultures.transport_speed(world(False), u, 250), 250)

    def test_origin_mode_changes_all_trait_owners(self):
        w = world()
        w.cfg['culture_basis'] = 'origin'
        c = {'nation': 0, 'origin_nation': 3, 'settlement_type': 'castle'}
        self.assertEqual(cultures.militia_cap(w, c), 250)
        c['origin_nation'] = 1
        self.assertEqual(cultures.training_hours(w, c), 144)
        u = {'nation': 3, 'origin_nation': 0, 'kind': 'garrison', 'healthy': 100, 'wounded': 0}
        self.assertEqual(cultures.city_food_need(w, u, 50), 4500)
        u.update(kind='city_cart', origin_nation=5)
        self.assertEqual(cultures.transport_speed(w, u, 250), 275)
        v = village(0)
        v['origin_nation'] = 2
        self.assertEqual(sum(cultures.weekly_yields(w, v)[1] for _ in range(10)), 22)
        v.update(city='town', origin_nation=4)
        self.assertEqual(cultures.weekly_yields(w, v), (220000, 2))
        v['nation'] = 5
        self.assertEqual(cultures.weekly_yields(w, v), (220000, 2))

    def test_origin_missing_metadata_fallback_and_invalid_basis(self):
        w = world()
        w.cfg['culture_basis'] = 'origin'
        self.assertEqual(cultures.militia_cap(w, {'nation': 3}), 250)
        w.cfg['culture_basis'] = 'unconfirmed'
        with self.assertRaisesRegex(ValueError, 'culture_basis'):
            cultures.militia_cap(w, {'nation': 3})

    def test_traits_follow_current_owner_not_initial_owner(self):
        w = world()
        c = {'nation': 3, 'initial_nation': 0, 'settlement_type': 'castle'}
        self.assertEqual(cultures.militia_cap(w, c), 250)
        c['nation'] = 0
        self.assertEqual(cultures.militia_cap(w, c), 200)
        v = village(4, 'town')
        v['initial_nation'] = 4
        self.assertEqual(cultures.weekly_yields(w, v)[0], 220000)
        v['nation'] = 0
        self.assertEqual(cultures.weekly_yields(w, v)[0], 200000)


if __name__ == '__main__':
    unittest.main()
