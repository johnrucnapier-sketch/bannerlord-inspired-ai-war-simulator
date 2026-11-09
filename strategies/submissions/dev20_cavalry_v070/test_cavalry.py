"""Dev20 policy-only cavalry regression and physical-command tests."""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent import WesternPlanner, decide
from test_adapter import party, planner
from aiwar.engine import World


class CavalryTests(unittest.TestCase):
    def world_fixture(self, healthy=150, cavalry=0):
        w = World(77111, {'mode': 'realmap'})
        city = next(c for c in w.cities.values() if c['nation'] == 0 and c['settlement_type'] == 'castle')
        u = next(u for u in w.units.values() if u['kind'] == 'party' and u['nation'] == 0)
        u.update(x=city['x'], y=city['y'], healthy=healthy, wounded=0,
                 cavalry=cavalry, cavalry_wounded=0, refill_target=150,
                 cavalry_target=0, food=healthy*3000, path=[], order=None)
        g = w.units[city['garrison']]
        g.update(healthy=150, wounded=0, cavalry=100, cavalry_wounded=0)
        city['food'] = w.cfg['warehouse']
        w.update_known()
        return w, city, u, g

    @staticmethod
    def isolated_run(p):
        p.logistics=lambda:None;p.refill_and_raise=lambda:None
        p.campaigns=lambda:None;p.rally=lambda:None
        return p.run()

    def test_underfilled_local_party_gets_composition_without_full_roster_gate(self):
        w, c, u, g = self.world_fixture(healthy=30)
        commands = self.isolated_run(WesternPlanner(w.observe(0)))
        command = next(x for x in commands if x['type']=='set_composition' and x['unit']==u['id'])
        before = sum(x['healthy'] for x in w.units.values()), sum(x['cavalry'] for x in w.units.values())
        self.assertTrue(w.command(0, command)['ok'])
        self.assertGreater(u['cavalry'], 0)
        self.assertEqual(before, (sum(x['healthy'] for x in w.units.values()), sum(x['cavalry'] for x in w.units.values())))
        w.check()

    def test_full_swap_keeps_garrison_and_party_heads_and_food_conserved(self):
        w,c,u,g = self.world_fixture()
        totals=lambda:(sum(x['healthy']+x['wounded'] for x in w.units.values()),
                       sum(x['cavalry']+x['cavalry_wounded'] for x in w.units.values()),
                       sum(x['food'] for x in w.units.values())+sum(x['food'] for x in w.cities.values()))
        before=totals();heads=(u['healthy'],g['healthy'])
        cmd=next(x for x in self.isolated_run(WesternPlanner(w.observe(0))) if x.get('unit')==u['id'])
        self.assertTrue(w.command(0,cmd)['ok'])
        self.assertEqual((u['cavalry'],g['cavalry']),(100,0))
        self.assertEqual(heads,(u['healthy'],g['healthy']));self.assertEqual(before,totals());w.check()

    def test_offsite_preference_does_not_teleport_cavalry_or_troops(self):
        w,c,u,g = self.world_fixture(healthy=30)
        # A legal road waypoint outside every service radius.
        for owned in w.cities.values():
            if owned['nation']==0 and owned['id']!=c['id']:
                route=w.route(u,owned['x'],owned['y'])
                point=next((p for p in route if all((p[0]-a['x'])**2+(p[1]-a['y'])**2>500**2 for a in w.cities.values())),None)
                if point:break
        u['x'],u['y']=point;w.update_known()
        before=(u['healthy'],u['cavalry'],g['healthy'],g['cavalry'])
        cmd=next(x for x in self.isolated_run(WesternPlanner(w.observe(0))) if x.get('unit')==u['id'])
        self.assertTrue(w.command(0,cmd)['ok']);self.assertEqual(before,(u['healthy'],u['cavalry'],g['healthy'],g['cavalry']))
        self.assertEqual(u['cavalry_target'],150);w.check()

    def test_real_march_reaches_castle_before_cavalry_exchange(self):
        w,c,u,g = self.world_fixture()
        # Use a legal road point outside the castle service radius, nearby
        # enough to test every hourly step rather than pretending an arrival.
        owned = next(a for a in w.cities.values() if a['nation']==0 and a['id']!=c['id'])
        route = w.route(u, owned['x'], owned['y'])
        point = next(p for p in route if (p[0]-c['x'])**2+(p[1]-c['y'])**2>500**2)
        u['x'],u['y']=point;u['order']=None;w.update_known()
        p=WesternPlanner(w.observe(0));p.targets={};p.cavalry_claimed={};p.cavalry_food_claimed={};p.cavalry_cooldowns={}
        self.assertTrue(p.collect_cavalry([p.units[u['id']]]))
        self.assertEqual(p.cmd[-1]['west_cavalry_city'],c['id'])
        for cmd in p.cmd+[dict(type='set_composition',unit=u['id'],cavalry_target=150)]:
            self.assertTrue(w.command(0,cmd)['ok'])
        self.assertEqual(u['cavalry'],0)
        for _ in range(48):
            w.step();w.check()
            if u['cavalry']:
                break
        self.assertGreater(u['cavalry'],0)
        self.assertLessEqual((u['x']-c['x'])**2+(u['y']-c['y'])**2,500**2)

    def test_service_is_after_earlier_create_and_mobilization_reservations(self):
        w,c,u,g = self.world_fixture(healthy=30)
        p=WesternPlanner(w.observe(0));p.logistics=lambda:None;p.campaigns=lambda:None;p.rally=lambda:None
        clan=u['clan'];other=next(x for x in list(w.units.values()) if x['kind']=='party' and x['clan']==clan and x['id']!=u['id'])
        w.remove(other['id']);w.update_known();p=WesternPlanner(w.observe(0))
        p.logistics=lambda:None;p.campaigns=lambda:None;p.rally=lambda:None
        def create():p.cmd.append(dict(type='create',city=c['id'],clan=clan,count=120,source='garrison'))
        p.refill_and_raise=create
        commands=p.run();self.assertEqual(commands[0]['type'],'create')
        for cmd in commands:self.assertTrue(w.command(0,cmd)['ok'],cmd)
        self.assertGreater(u['cavalry'],0);w.check()

    def test_removed_transfer_donor_is_not_addressed_and_cap_respected(self):
        u=party('u',1);u['cavalry_target']=0;p=planner([u])
        p.logistics=lambda:None;p.refill_and_raise=lambda:None;p.campaigns=lambda:None;p.rally=lambda:None
        with patch('agent.augment_commands',return_value=[dict(type='transfer',unit='u',target='other',count=150)]):
            self.assertFalse(any(c['type']=='set_composition' for c in p.run()))
        with patch('agent.augment_commands',return_value=[dict(type='move',unit='other',x=0,y=0)]*100):
            self.assertEqual(len(p.run()),100)

    def collection_fixture(self):
        u=party('u',1,x=10000);u.update(cavalry=0,healthy=150,food=900000)
        u['order']={};p=planner([u]);c=p.bycity['base'];c['garrison']='g'
        p.units['g']=dict(id='g',kind='garrison',healthy=100,cavalry=100,battle=None)
        p.garrison['base']=100;p.stock['base']=9000000;p.floors={'base':300000}
        p.cavalry_claimed={};p.cavalry_food_claimed={};p.cavalry_cooldowns={}
        p.eta=lambda a,b:abs(a['x']-b['x'])/500;p.targets={}
        return p,u,c

    def test_collection_moves_physically_and_reserves_stock_only_once(self):
        p,u,c=self.collection_fixture();before=copy.deepcopy(p.units)
        self.assertTrue(p.collect_cavalry([u]));self.assertEqual(p.units,before)
        self.assertEqual(p.cmd[-1]['west_task'],'cavalry_refit');self.assertEqual(p.cmd[-1]['x'],c['x'])
        other=party('second',2,x=10000);other['order']={};other['cavalry']=0
        self.assertFalse(p.collect_cavalry([other]))
        self.assertEqual(p.cavalry_claimed['base'],100)

    def test_no_collection_when_unsafe_unfunded_unreachable_or_too_far(self):
        for change in ('unsafe','lowfood','lowstock','unreachable','far','battle','reserved','wounded'):
            with self.subTest(change=change):
                p,u,c=self.collection_fixture()
                if change=='unsafe':p.safe_route=lambda a,b:False
                if change=='lowfood':u['food']=15000
                if change=='lowstock':p.stock['base']=300000
                if change=='unreachable':p.eta=lambda a,b:float('inf')
                if change=='far':p.eta=lambda a,b:49
                if change=='battle':p.units['g']['battle']='battle'
                if change=='reserved':p.garrison['base']=0
                if change=='wounded':u.update(healthy=10,wounded=100)
                self.assertFalse(p.collect_cavalry([u]));self.assertEqual(p.cmd,[])

    def test_no_collection_over_combat_escort_relief_or_mobilization(self):
        for order in (dict(type='siege'),dict(type='attack'),dict(type='raid'),
                      dict(west_task='escort'),dict(west_task='clear_bandits'),
                      dict(campaign_phase='relief'),dict(vanilla_task='mobilization_rally'),dict(vanilla_task='mobilization_prepare')):
            p,u,c=self.collection_fixture();u['order']=order
            self.assertFalse(p.collect_cavalry([u]))

    def test_collection_deadline_arrival_cooldown_and_route_recheck(self):
        for arrival in (False,True):
            p,u,c=self.collection_fixture();u['order']=dict(west_task='cavalry_refit',west_cavalry_city='base',west_cavalry_until=100 if arrival else 0)
            if arrival:u.update(x=0,cavalry=150)
            self.assertFalse(p.collect_cavalry([u]));self.assertEqual(p.cavalry_cooldowns['u'],p.hour+168)
        p,u,c=self.collection_fixture();u['order']=dict(west_cavalry_after=999)
        self.assertFalse(p.collect_cavalry([u]))
        p,u,c=self.collection_fixture();u['order']=dict(west_task='cavalry_refit',west_cavalry_city='base',west_cavalry_until=100)
        p.safe_route=lambda a,b:False
        self.assertFalse(p.collect_cavalry([u]))

    def test_mobile_patrol_priority_and_no_automatic_patrol_commands(self):
        p,u,c=self.collection_fixture();v=party('v',2);v['order']=dict(west_task='local_patrol')
        self.assertLess(p.cavalry_priority([v]),p.cavalry_priority([u]))
        w,c,u,g=self.world_fixture();patrol=w.new_unit('patrol',0,c['clan'],30,c['x'],c['y'],home=c['id']);w.update_known()
        commands=self.isolated_run(WesternPlanner(w.observe(patrol['nation'])))
        self.assertFalse(any(x.get('unit')==patrol['id'] for x in commands))

    def test_all_eight_country_decisions_are_observation_only_and_legal(self):
        w=World(77117,{'mode':'realmap'})
        snapshots=[w.observe(n) for n in w.nation_ids()]
        original=copy.deepcopy(snapshots)
        batches=[decide(obs) for obs in snapshots]
        self.assertEqual(snapshots,original)
        for n,commands in enumerate(batches):
            self.assertLessEqual(len(commands),100)
            for cmd in commands:self.assertTrue(w.command(n,cmd)['ok'],(n,cmd))
        w.check()

    def test_relief_excludes_party_with_blocked_siege_avoidance_route(self):
        units=[party('blocked',1),party('available',2)]
        p=planner(units)
        p.o['relief_requests']=[dict(assault_at=10,city='home',battle='siege',x=5000,y=0)]
        enemy=party('hostile',3,x=5000);enemy.update(nation=2,battle='siege',healthy=100)
        p.hostiles=[enemy]
        def route(terrain,unit,x,y):
            if terrain.get('exclude') and unit['id']=='blocked':
                return None
            return [(0,0)]
        with patch('agent.find_route',side_effect=route):
            p.relief()
        self.assertEqual([c['unit'] for c in p.cmd],['available'])
        self.assertNotIn('blocked',p.done)


if __name__=='__main__':unittest.main()
