import unittest
from aiwar.engine import World,dist
from aiwar.policies import decide

class FrontierAndShelter(unittest.TestCase):
    def world(self):return World(1,{'bandit_cap':0})
    def party(self,w):return next(u for u in w.units.values() if u['kind']=='party' and u['clan']==0)

    def test_initial_frontier_is_only_neighboring_enemy_cities(self):
        w=self.world()
        self.assertEqual([c for c in w.cities if w.can_siege(0,c)],['c11','c13','c15'])
        self.assertEqual([c for c in w.cities if w.can_siege(1,c)],['c01','c03','c05'])
        self.assertEqual(w.observe(0)['frontier_targets'],['c11','c13','c15'])

    def test_back_city_cannot_be_sieged_or_bypassed_by_attacking_garrison(self):
        w=self.world();u=self.party(w);c=w.cities['c10'];g=w.units[c['garrison']]
        u.update(x=c['x'],y=c['y']);w.update_known()
        self.assertFalse(w.command(0,{'type':'siege','unit':u['id'],'target':c['id']})['ok'])
        self.assertFalse(w.command(0,{'type':'attack','unit':u['id'],'target':g['id']})['ok'])
        w.start_battle(u,g,c['id']);self.assertFalse(w.battles)
        u['order']={'type':'attack','target':g['id']};w.contacts({})
        self.assertFalse(w.battles);self.assertIsNone(u['order'])

    def test_capture_opens_next_layer_and_losing_front_cancels_pending_siege(self):
        w=self.world();u=self.party(w);back=w.cities['c10']
        w.capture('c11',0,[0]);self.assertTrue(w.can_siege(0,'c10'))
        u.update(x=back['x']-1000,y=back['y']);w.update_known()
        self.assertTrue(w.command(0,{'type':'siege','unit':u['id'],'target':'c10'})['ok'])
        w.capture('c11',1,[7]);w.move_units()
        self.assertFalse(w.can_siege(0,'c10'));self.assertIsNone(u['order'])

    def test_demo_controller_selects_only_front_targets(self):
        w=self.world()
        for u in w.units.values():
            if u['kind']=='party':u['healthy']=100
        for n in (0,1):
            obs=w.observe(n);front=set(obs['frontier_targets'])
            commands=decide(obs)
            enemy={c['id']:c for c in obs['cities'] if c['nation']!=n}
            for c in commands:
                if c['type']=='siege':self.assertIn(c['target'],front)
                if c['type']=='move':
                    destinations=[k for k,v in enemy.items() if (v['x'],v['y'])==(c['x'],c['y'])]
                    for target in destinations:self.assertIn(target,front)

    def test_idle_home_transport_cannot_be_targeted_or_directly_attacked(self):
        w=self.world();v=w.villages['v000'];u=w.units[v['cart']]
        b=w.new_unit('bandit',-1,-1,20,v['x']+1500,v['y'])
        self.assertFalse(w.bandit_can_target(u));w.bandits()
        self.assertNotEqual((b['order'] or {}).get('target'),u['id'])
        w.start_battle(b,u);self.assertFalse(w.battles)
        ids={v['cart'] for v in w.villages.values()}
        w.step(120)
        self.assertTrue(ids.issubset(w.units))
        self.assertEqual(w.observer_totals()[0]['population'],3690)

    def test_outbound_is_protected_until_physically_outside_home(self):
        w=self.world();v=w.villages['v000'];u=w.units[v['cart']]
        u['phase']='outbound'
        self.assertFalse(w.bandit_can_target(u))
        u['x']=v['x']+500;self.assertFalse(w.bandit_can_target(u))
        u['x']=v['x']+501;self.assertTrue(w.bandit_can_target(u))

    def test_returning_inside_home_cancels_a_chase_before_contact(self):
        w=self.world();v=w.villages['v000'];u=w.units[v['cart']]
        u.update(phase='return',x=v['x']+600,y=v['y'],path=[[v['x'],v['y']]])
        b=w.new_unit('bandit',-1,-1,20,v['x']+1000,v['y'],uid='a-bandit')
        w.go(b,u['x'],u['y'],{'type':'attack','target':u['id']})
        self.assertTrue(w.bandit_can_target(u))
        w.step()
        self.assertLessEqual(dist(u,v),500)
        self.assertIsNone(u['battle']);self.assertIsNone(b['battle'])
        self.assertNotEqual((b['order'] or {}).get('target'),u['id'])
        w.step(3);self.assertEqual(u['phase'],'idle')

    def test_safe_village_transport_not_pulled_into_neighboring_bandit_fight(self):
        w=self.world();v=w.villages['v000'];u=w.units[v['cart']]
        p=w.new_unit('party',0,0,30,v['x']+750,v['y'])
        b=w.new_unit('bandit',-1,-1,20,p['x'],p['y'])
        w.start_battle(p,b)
        self.assertIsNotNone(p['battle']);self.assertIsNone(u['battle'])
        w.contacts({});self.assertIsNone(u['battle'])
        # The protection is against bandits, not immunity from enemy armies.
        w.battles.clear();p['battle']=None;b['battle']=None
        enemy=w.new_unit('party',1,6,30,v['x'],v['y'])
        w.start_battle(enemy,u);self.assertIsNotNone(u['battle'])

if __name__=='__main__':unittest.main()
