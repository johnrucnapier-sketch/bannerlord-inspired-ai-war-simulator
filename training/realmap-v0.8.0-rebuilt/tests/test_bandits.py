import math
import unittest
from aiwar.engine import World,dist

class Bandits(unittest.TestCase):
    def arena(self):
        w=World(1,{'bandit_cap':0})
        w.units.clear();w.cities.clear()
        cart=w.new_unit('village_cart',0,0,20,60000,40000,home='v000')
        bandit=w.new_unit('bandit',-1,-1,20,60000,40000)
        cart['cargo_food']=180000;cart['cargo_recruits']=1;cart['phase']='return'
        return w,cart,bandit

    def test_far_villages_and_rotational_cities(self):
        w=World()
        for j in range(6):
            a,b=w.cities[f'c0{j}'],w.cities[f'c1{j}']
            self.assertEqual(a['x']+b['x'],120000)
            self.assertEqual(a['y']+b['y'],80000)
        distances=[]
        for v in w.villages.values():
            self.assertGreater(min(dist(v,c) for c in w.cities.values()),10500)
            distances.append(dist(v,w.cities[v['city']]))
        self.assertGreater(max(distances)-min(distances),3000)
        near=[min(dist(c,d) for d in w.cities.values() if c!=d) for c in w.cities.values()]
        self.assertGreater(min(near),23000)
        self.assertLess(max(near),31000)
        self.assertTrue(all(c['x']<60000 for c in w.cities.values() if c['nation']==0))
        self.assertTrue(all(c['x']>60000 for c in w.cities.values() if c['nation']==1))

    def test_travel_times_are_staggered(self):
        w=World(1,{'bandit_cap':0})
        times=[]
        for v in w.villages.values():
            u=w.units[v['cart']];c=w.cities[v['city']]
            w.go(u,c['x'],c['y']);hours=0
            while u['path'] and hours<200:w.move_units();hours+=1
            times.append(hours)
        self.assertGreater(len(set(times)),8)
        self.assertGreater(min(times),40)
        self.assertLessEqual(max(times),84)

    def test_spawn_independent_of_week_and_outside_city_sight(self):
        w=World(1,{'bandit_spawn_min':1,'bandit_spawn_max':1})
        w.step()
        bandits=[u for u in w.units.values() if u['kind']=='bandit']
        self.assertEqual(len(bandits),2)
        for b in bandits:
            self.assertGreater(min(dist(b,c) for c in w.cities.values()),10000)
        self.assertTrue(all(u['phase']=='idle' for u in w.units.values() if u['kind']=='village_cart'))

    def test_flee_overrides_transport_attack(self):
        w,cart,b=self.arena()
        cart['y']+=3000
        p=w.new_unit('party',0,0,30,64000,40000)
        before=dist(p,b)
        w.bandits()
        self.assertEqual(b['order']['type'],'flee')
        self.assertNotEqual(b['order'].get('target'),cart['id'])
        w.move_units()
        self.assertGreater(dist(p,b),before)

    def test_ambush_finishes_in_five_hours(self):
        w,cart,b=self.arena();w.start_battle(b,cart)
        battle=w.battles[b['battle']]
        self.assertEqual(battle['kind'],'ambush')
        w.battle_tick();self.assertEqual(cart['healthy'],20)
        for h in range(1,6):w.hour=h;w.battle_tick()
        self.assertNotIn(cart['id'],w.units)
        self.assertIn(b['id'],w.units)
        self.assertEqual(w.stats['bandit_cart_losses'],1)
        self.assertEqual(w.stats['bandit_food_lost'],180000)

    def test_nearby_patrol_rescues(self):
        w,cart,b=self.arena();w.start_battle(b,cart)
        w.hour=1;w.battle_tick()
        patrol=w.new_unit('party',0,0,40,60500,40000)
        w.contacts({})
        self.assertEqual(patrol['battle'],b['battle'])
        for h in range(2,7):w.hour=h;w.battle_tick()
        self.assertIn(cart['id'],w.units)
        self.assertNotIn(b['id'],w.units)
        self.assertEqual(w.stats['bandit_cart_losses'],0)

    def test_distant_city_force_too_late(self):
        w,cart,b=self.arena();w.start_battle(b,cart)
        patrol=w.new_unit('party',0,0,40,72000,40000)
        w.go(patrol,b['x'],b['y'],{'type':'attack','target':b['id']})
        w.step(5)
        self.assertNotIn(cart['id'],w.units)
        self.assertGreater(dist(patrol,b),1000)

    def test_normal_war_keeps_full_preparation(self):
        w=World(1,{'bandit_cap':0});w.units.clear()
        a=w.new_unit('party',0,0,150,60000,40000)
        b=w.new_unit('party',1,6,150,60000,40000)
        w.start_battle(a,b)
        self.assertEqual(w.battles[a['battle']]['prepare_hours'],24)
        self.assertEqual(w.battles[a['battle']]['combat_hours'],24)

    def test_observer_has_no_player_commands(self):
        from pathlib import Path
        s=(Path(__file__).resolve().parents[1]/'godot/main.gd').read_text(encoding='utf-8')
        for removed in ('MOUSE_BUTTON_RIGHT','func unit_command','TextEdit','驻军 +10','新部队 30'):
            self.assertNotIn(removed,s)

if __name__=='__main__':unittest.main()
