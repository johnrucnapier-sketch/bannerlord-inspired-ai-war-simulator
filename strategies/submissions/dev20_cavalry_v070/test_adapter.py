import sys
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from agent import WesternPlanner


def party(i, clan, x=0, army=None):
    return dict(id=i,clan=clan,nation=7,kind='party',x=x,y=0,healthy=150,wounded=0,
                food=900000,food_capacity=900000,army=army,battle=None,army_target='enemy',
                refill_target=150,cavalry_target=150,
                order=dict(type='move',west_task='clan_campaign',west_target='enemy',vanilla_base='base'))


def planner(units):
    p=WesternPlanner.__new__(WesternPlanner)
    p.o={'limits':{'party_cap':150,'field_ration':100,'carry_days':30},
         'logistics_limits':{'raid_household_food':1000,'army_carry_days':60},
         'speeds':{'party':500},'map_info':{'clans':{}},'terrain':{},
         'cities':[],'villages':[],'battles':[],'relief_requests':[]}
    p.parties=units;p.units={u['id']:u for u in units};p.cmd=[];p.done=set();p.hour=1;p.n=7
    p.sieged=set();p.claimed={};p.hostiles=[];p.armies={};p.support={};p.raid_assignments={}
    for u in units:
        if u['army']:p.armies.setdefault(u['army'],[]).append(u)
    p.bycity={'base':dict(id='base',x=0,y=0,neighbors=['enemy'])}
    p.safe=list(p.bycity.values());p.cities=p.safe;p.o['cities']=p.safe
    p.bycity['base']['nation']=7
    p.targets={'enemy':dict(id='enemy',nation=2,x=4000,y=0,healthy=100,militia_healthy=0)}
    p.stock={'base':9000000};p.garrison={'base':500};p.depth={'base':0}
    p.eta=lambda u,c:1;p.length=lambda u,c:4000;p.stage=lambda base,target:dict(x=2000,y=0)
    p.base=lambda u:p.bycity['base'];p.campaign_budget=lambda *args:24
    p.safe_route=lambda a,b:True
    return p


class AdapterTests(unittest.TestCase):
    def test_original_snapshot_identical(self):
        import hashlib
        here=Path(__file__).resolve().parent
        self.assertEqual(hashlib.sha256((here/'dev19_original.py').read_bytes()).hexdigest(),
                         '92549e49a7be8f721411048c549c3a804ff9249865902d300b46cdeec5f8b1b3')

    def test_clans_assemble_separately_and_singletons_campaign(self):
        units=[party('a',1),party('b',1),party('c',2),party('d',2),party('e',3)]
        p=planner(units);p.rally()
        assemblies=[c for c in p.cmd if c['type']=='assemble']
        self.assertEqual(len(assemblies),2)
        byid={u['id']:u for u in units}
        for c in assemblies:
            self.assertEqual(len({byid[i]['clan'] for i in [c['unit']]+c['units']}),1)
        self.assertEqual({c['unit'] for c in p.cmd if c['type']=='move'},{'a','c','e'})

    def test_rebuilt_parties_do_not_create_second_clan_army(self):
        from aiwar.engine import World
        w=World(1,{'mode':'realmap'})
        clan=int(next(k for k,v in w.map_clans.items() if v['party_slots']==3))
        nation=w.clan_nation(clan)
        base=next(c for c in w.cities.values() if c['clan']==clan)
        units=[u for u in w.units.values() if u['kind']=='party' and u['clan']==clan]
        for u in units:u.update(x=base['x'],y=base['y'],healthy=150,wounded=0,food=900000)
        result=w.command(nation,dict(type='assemble',unit=units[0]['id'],units=[units[1]['id']]))
        self.assertTrue(result['ok']);aid=result['army']
        w.remove(units[1]['id'],'removed')
        new=w.new_unit('party',nation,clan,150,base['x'],base['y'],home=base['id'],food=900000)
        target=w.observe(nation)['frontier_targets'][0]
        for u in (units[0],units[2],new):
            u['order']=dict(type='move',west_task='clan_campaign' if u['army'] else 'rally',west_target=target,vanilla_base=base['id'])
        w.update_known();p=WesternPlanner(w.observe(nation));p.rally()
        self.assertFalse(any(c['type']=='assemble' and w.units[c['unit']]['clan']==clan for c in p.cmd))
        moved={c['unit'] for c in p.cmd if c['type']=='move'}
        self.assertTrue({units[2]['id'],new['id']}<=moved)
        for cmd in p.cmd:self.assertTrue(w.command(nation,cmd)['ok'],cmd)
        self.assertEqual(w.armies[aid],[units[0]['id']]);w.check()

    def test_remote_force_cannot_authorize_siege(self):
        units=[party('a',1,2000),party('b',2,0)]
        p=planner(units);p.campaigns()
        self.assertFalse(any(c['type']=='siege' for c in p.cmd))
        units[1]['x']=2000
        p=planner(units);p.campaigns()
        self.assertEqual({c['unit'] for c in p.cmd if c['type']=='siege'},{'a','b'})
        self.assertFalse(any(c['type'] in ('assemble','disband') for c in p.cmd))

    def test_far_side_near_target_is_not_local_strength(self):
        units=[party('a',1,2000),party('b',2,6000)]
        p=planner(units);p.campaigns()
        self.assertFalse(any(c['type']=='siege' for c in p.cmd))

    def test_different_supply_bases_share_one_physical_rendezvous(self):
        units=[party('a',1,0),party('b',2,8000)]
        units[1]['order']['vanilla_base']='east'
        p=planner(units)
        east=dict(id='east',nation=7,x=8000,y=0,neighbors=['enemy'])
        p.bycity['east']=east;p.safe.append(east);p.stock['east']=9000000
        p.length=lambda a,b:abs(a['x']-b['x'])
        del p.stage  # Exercise the actual route-derived staging calculation.
        with patch('agent.find_route',side_effect=lambda terrain,at,x,y:[(x,y)]):
            p.campaigns()
            self.assertFalse(any(c['type']=='siege' for c in p.cmd))
            moves=[c for c in p.cmd if c['type']=='move']
            self.assertEqual({c['unit'] for c in moves},{'a','b'})
            self.assertEqual({(c['x'],c['y']) for c in moves},{(2000,0)})
            self.assertEqual({c['vanilla_base'] for c in moves},{'base','east'})
            # Merely issuing both moves did not contribute remote strength.
            # Only after their real arrival may both independent clans siege.
            for u in units:u['x']=2000
            p.cmd=[];p.done=set();p.safe.reverse()
            p.campaigns()
            self.assertEqual({c['unit'] for c in p.cmd if c['type']=='siege'},{'a','b'})
            self.assertFalse(any(c['type'] in ('assemble','disband') for c in p.cmd))

    def test_shared_rendezvous_detour_is_paid_by_each_formation(self):
        u=party('a',1,x=6000);u['food']=150*100*25
        p=planner([u])
        p.eta=lambda a,b:abs(a['x']-b['x'])/100
        p.length=lambda a,b:abs(a['x']-b['x'])
        # Direct target budget fits, but crossing to the common stage first
        # adds 4000/(100*24) days and cannot borrow another clan's rations.
        p.campaigns()
        self.assertTrue(any(c.get('west_task') in ('supply_leg','food_refit') for c in p.cmd),p.cmd)
        self.assertFalse(any(c.get('west_task')=='clan_campaign' for c in p.cmd))

    def test_no_cross_clan_food_pooling(self):
        units=[party('a',1,2000),party('b',2,2000)]
        units[0]['food']=1000
        p=planner(units);p.campaigns()
        self.assertFalse(any(c['type']=='siege' for c in p.cmd))
        self.assertTrue(any(c['unit']=='a' and c['type']=='move' for c in p.cmd))

    def test_full_small_clan_not_trapped_in_650_recovery(self):
        p=planner([party('a',1,2000)])
        self.assertFalse(p.recover_campaign(p.parties))

    def test_stale_target_not_sieged(self):
        p=planner([party('a',1,2000),party('b',2,2000)])
        p.targets['enemy']['stale']=True;p.campaigns()
        self.assertFalse(any(c['type']=='siege' for c in p.cmd))

    def test_partial_clan_forms_without_113_or_national_650_gate(self):
        units=[party('a',1),party('b',1)]
        for u in units:
            u.update(healthy=30,food=30*100*14,order=None)
        p=planner(units);p.rally()
        self.assertEqual([c['units'] for c in p.cmd if c['type']=='assemble'],[['b']])
        self.assertTrue(any(c.get('west_task')=='clan_campaign' for c in p.cmd))
        for u in units:u['army']='formed'
        p=planner(units)
        self.assertFalse(p.recover_campaign(units))
        # Low readiness and excessive wounds still require genuine recovery.
        units[0]['healthy']=10;units[1]['healthy']=10
        self.assertTrue(p.recover_campaign(units))

    def test_logistics_refill_does_not_reapply_650_recovery_to_ready_clan(self):
        from aiwar.engine import World
        w=World(1,{'mode':'realmap','auto_city_service':False})
        obs=w.observe(0)
        units=[u for u in obs['units'] if u['nation']==0 and u['kind']=='party'][:2]
        home=next(c for c in obs['cities'] if c['nation']==0 and 'food' in c)
        for unit in units:
            unit.update(army='host',healthy=30,wounded=0,food=1000,x=home['x'],y=home['y'])
            unit['order']=dict(west_task='recover',west_recover=home['id'])
        home['food']=10000000
        p=WesternPlanner(obs);p.logistics()
        refill=next(c for c in p.cmd if c.get('unit')==units[0]['id'] and c.get('vanilla_task')=='refill_army')
        self.assertNotIn('west_recover',refill)

    def test_clans_form_locally_before_remote_frontier_march(self):
        units=[party('a',1,x=100000),party('b',1,x=100000)]
        for u in units:u['order']=None
        p=planner(units)
        home=dict(id='home',nation=7,x=100000,y=0,neighbors=[])
        p.bycity['home']=home;p.safe.append(home);p.stock['home']=9000000
        p.eta=lambda u,c:abs(u['x']-c['x'])/100
        p.rally()
        self.assertTrue(any(c['type']=='assemble' for c in p.cmd))
        self.assertEqual(next(c for c in p.cmd if c['type']=='move')['x'],100000)
        self.assertFalse(any(c['type']=='siege' for c in p.cmd))

    def test_supply_stop_is_reachable_progress_and_not_remote_food(self):
        u=party('a',1);u['food']=150*100*30
        p=planner([u]);destination=dict(x=100000,y=0)
        stop=dict(id='stop',nation=7,x=50000,y=0,neighbors=[])
        p.safe.append(stop);p.stock['stop']=9000000
        p.eta=lambda u,c:abs(u['x']-c['x'])/100
        p.length=lambda u,c:abs(u['x']-c['x'])
        self.assertGreater(p.eta(u,destination)/24,30)
        self.assertEqual(p.supply_leg([u],destination),stop)
        p.stock['stop']=0
        self.assertIsNone(p.supply_leg([u],destination))

    def test_rally_daily_ration_tick_does_not_reverse_started_journey(self):
        u=party('a',1,x=10000);other=party('b',1,x=10000)
        for unit in (u,other):
            unit.update(healthy=30,food=30*100*29,path=[[0,0]])
            unit['order']=dict(type='move',west_task='rally',west_target='enemy',
                               vanilla_base='base',west_rally='base')
        p=planner([u,other]);p.eta=lambda a,b:24.8*24
        p.rally()
        self.assertTrue(p.cmd)
        self.assertTrue(all(c.get('west_task')=='rally' for c in p.cmd))

    @staticmethod
    def run_without_logistics(p):
        # Exercise the actual inherited run order, not just isolated helpers.
        # Resource generation is irrelevant to these tactical fixtures.
        p.logistics=lambda:None;p.refill_and_raise=lambda:None
        with patch('agent.augment_commands',side_effect=lambda obs,commands:commands):
            return p.run()

    def test_run_restores_operational_interception_and_independent_defence(self):
        for army,enemy_health in [('host',100),(None,60)]:
            with self.subTest(army=army):
                units=[party('a',1,army=army)]
                if army:units.append(party('b',1,army=army))
                for unit in units:unit['order']=None
                p=planner(units)
                enemy=party('enemy-party',2,x=6000);enemy.update(nation=2,healthy=enemy_health)
                p.hostiles=[enemy];p.o['units']=units+[enemy]
                commands=self.run_without_logistics(p)
                self.assertTrue(any(c['type']=='attack' and c['target']==enemy['id'] for c in commands),commands)
                self.assertFalse(any(c['type'] in ('assemble','disband') for c in commands))

    def test_run_raids_before_low_food_refit_and_consumes_real_food(self):
        units=[party('a',1,x=2000,army='host'),party('b',1,x=2000,army='host')]
        for u in units:u['food']=150*100*12
        p=planner(units)
        p.o['villages']=[dict(id='village',nation=2,x=3000,y=0,population=100)]
        commands=self.run_without_logistics(p)
        self.assertTrue(any(c['type']=='raid' and c['target']=='village' for c in commands),commands)
        self.assertFalse(any(c.get('west_task')=='food_refit' for c in commands))
        for u in units:u['food']=150*100 # Too little to raid and survive.
        p=planner(units);p.o['villages']=[dict(id='village',nation=2,x=3000,y=0,population=100)]
        self.assertFalse(any(c['type']=='raid' for c in self.run_without_logistics(p)))

    def test_run_relief_attacks_only_physically_arrived_independent_clans(self):
        for second_x,should_attack in [(0,True),(1000,False)]:
            with self.subTest(second_x=second_x):
                units=[party('a',1),party('b',2,x=second_x)]
                for unit in units:unit['healthy']=100
                p=planner(units)
                p.o['relief_requests']=[dict(assault_at=10,city='home',battle='siege',x=5000,y=0)]
                enemy=party('hostile',3,x=5000);enemy.update(nation=2,battle='siege')
                p.hostiles=[enemy]
                with patch('agent.find_route',return_value=[(0,0)]),patch('agent.relief_terrain',return_value={}):
                    commands=self.run_without_logistics(p)
                self.assertEqual({c['unit'] for c in commands if c['type']=='attack'},
                                 {'a','b'} if should_attack else set())
                self.assertFalse(any(c['type'] in ('assemble','disband') for c in commands))

    def test_interception_counts_enemy_levy_as_half_strength(self):
        p=planner([party('a',1)])
        enemy=party('enemy',2,x=6000);enemy.update(nation=2,kind='levy',healthy=150)
        p.hostiles=[enemy]
        self.assertTrue(p.intercept(p.parties))
        p=planner([party('a',1)]);enemy['kind']='party';p.hostiles=[enemy]
        self.assertFalse(p.intercept(p.parties))

    def test_small_party_clears_catchable_visible_bandit(self):
        u=party('a',1);u.update(healthy=30,movement_speed=1000,food=90000)
        p=planner([u]);bandit=party('bandit',-1,x=2000)
        bandit.update(nation=-1,kind='bandit',healthy=20)
        p.units[bandit['id']]=bandit
        self.assertTrue(p.productive_local([u],patrol=False))
        self.assertEqual(p.cmd[-1]['west_task'],'clear_bandits')
        self.assertEqual(p.cmd[-1]['target'],'bandit')
        self.assertEqual(u['healthy'],30)  # A decision does not fabricate rewards.

    def test_slow_army_escorts_actual_loaded_cart_instead_of_chasing_bandit(self):
        units=[party('a',1,army='host'),party('b',1,army='host')]
        for u in units:u.update(healthy=30,movement_speed=500)
        p=planner(units)
        bandit=party('bandit',-1,x=3000);bandit.update(nation=-1,kind='bandit',healthy=20)
        cart=party('cart',1,x=2000);cart.update(kind='village_cart',phase='outbound',cargo_food=10000)
        p.units.update({u['id']:u for u in [bandit,cart]})
        self.assertTrue(p.productive_local(units))
        self.assertEqual(p.cmd[-1]['west_task'],'escort')
        self.assertEqual(p.cmd[-1]['west_cart'],'cart')
        self.assertFalse(any(c['type']=='attack' for c in p.cmd))
        # No phantom escort of an empty or idle transporter.
        cart.update(phase='idle',cargo_food=0);p.cmd=[];p.local_claims=set()
        self.assertFalse(p.productive_local(units,patrol=False))

    def test_slow_army_can_rescue_cart_already_attacked_by_bandit(self):
        units=[party('a',1,army='host'),party('b',1,army='host')]
        for u in units:u.update(healthy=30,movement_speed=500)
        p=planner(units)
        bandit=party('bandit',-1,x=3000);bandit.update(nation=-1,kind='bandit',healthy=20,battle='ambush')
        cart=party('cart',1,x=3000);cart.update(kind='village_cart',phase='outbound',cargo_food=10000,battle='ambush')
        p.units.update({u['id']:u for u in [bandit,cart]})
        p.o['battles']=[dict(id='ambush',kind='ambush',city=None)]
        self.assertTrue(p.productive_local(units))
        self.assertEqual(p.cmd[-1]['west_task'],'clear_bandits')

    def test_local_sortie_rejects_visible_superior_enemy_and_inadequate_return_food(self):
        u=party('a',1);u.update(healthy=30,movement_speed=1000,food=90000)
        p=planner([u]);bandit=party('bandit',-1,x=2000)
        bandit.update(nation=-1,kind='bandit',healthy=20)
        enemy=party('enemy-party',2,x=3000);enemy['nation']=2
        p.units[bandit['id']]=bandit;p.hostiles=[enemy]
        self.assertFalse(p.productive_local([u],patrol=False))
        self.assertFalse(any(c['type']=='attack' for c in p.cmd))
        p.hostiles=[];u['food']=100;p.cmd=[]
        self.assertTrue(p.productive_local([u],patrol=False))
        self.assertEqual(p.cmd[-1]['west_task'],'local_return')

    def test_cart_harassment_rejects_possible_protected_idle_farmer(self):
        u=party('a',1);u.update(healthy=100,movement_speed=1000)
        p=planner([u]);cart=party('enemy-cart',2,x=1500)
        cart.update(nation=2,kind='village_cart',healthy=20)
        p.units[cart['id']]=cart
        p.o['villages']=[dict(id='enemy-village',nation=2,x=1500,y=0)]
        self.assertFalse(p.productive_local([u],patrol=False))
        cart['x']=2500
        self.assertTrue(p.productive_local([u],patrol=False))
        self.assertEqual(p.cmd[-1]['west_task'],'harass')
        self.assertEqual(p.cmd[-1]['target'],'enemy-cart')
        self.assertNotIn('cargo_food',cart)  # Cargo stays hidden from the planner.

    def test_staging_timeout_starts_bounded_local_patrol_then_rechecks_campaign(self):
        u=party('a',1,x=2000,army='host');u['healthy']=100
        u['order']['west_wait_since']=0
        p=planner([u]);p.hour=73
        p.o['villages']=[dict(id='friendly-village',nation=7,city='base',x=1000,y=0)]
        p.campaigns()
        self.assertEqual(p.cmd[-1]['west_task'],'local_patrol')
        self.assertEqual(p.cmd[-1]['west_local_until'],121)
        u['order']=p.cmd[-1];p.hour=121;p.cmd=[];p.done=set()
        p.campaigns()
        self.assertEqual(p.cmd[-1]['west_task'],'clan_campaign')
        self.assertEqual(p.cmd[-1]['west_wait_since'],121)

    def test_local_chase_expires_without_reacquiring_and_return_is_sticky(self):
        u=party('a',1,x=2000);u.update(healthy=30,movement_speed=1000)
        u['order']=dict(type='attack',target='bandit',west_task='clear_bandits',west_chase_since=0,
                        west_local_until=48,west_home='base',west_target='enemy',vanilla_base='base')
        p=planner([u]);p.hour=12
        bandit=party('bandit',-1,x=3000);bandit.update(nation=-1,kind='bandit',healthy=20)
        p.units[bandit['id']]=bandit
        p.campaigns()
        self.assertEqual(p.cmd[-1]['west_task'],'local_return')
        u['order']=p.cmd[-1];p.hour=15;p.cmd=[];p.done=set()
        p.campaigns()
        self.assertEqual(u['order']['west_task'],'local_return')
        self.assertFalse(any(c['type']=='attack' for c in p.cmd))

    def test_sufficient_actual_campaign_force_does_not_take_patrol_fallback(self):
        units=[party('a',1,x=2000),party('b',2,x=2000)]
        for u in units:u['order']['west_wait_since']=0
        p=planner(units);p.hour=100;p.campaigns()
        self.assertEqual({c['unit'] for c in p.cmd if c['type']=='siege'},{'a','b'})
        self.assertFalse(any(c.get('west_task')=='local_patrol' for c in p.cmd))

    def test_local_patrol_keeps_destination_and_timer_while_marching(self):
        u=party('a',1)
        u.update(path=[[3000,0]],order=dict(type='move',x=3000,y=0,west_task='local_patrol',
                 west_local_until=48,west_home='base',west_patrol_index=0))
        p=planner([u]);p.hour=10;p.productive_local([u])
        self.assertEqual((p.cmd[-1]['x'],p.cmd[-1]['west_local_until']),(3000,48))

    def test_only_one_formation_claims_each_loaded_cart(self):
        units=[party('a',1),party('b',2)]
        p=planner(units)
        cart=party('cart',1,x=2000);cart.update(kind='village_cart',phase='outbound',cargo_food=10000)
        p.units[cart['id']]=cart
        p.productive_local([units[0]],patrol=False)
        p.productive_local([units[1]],patrol=False)
        self.assertEqual(sum(c.get('west_task')=='escort' for c in p.cmd),1)

    def test_campaign_march_does_not_restart_wait_clock_each_decision(self):
        u=party('a',1,x=0,army='host');p=planner([u]);p.campaigns()
        self.assertNotIn('west_wait_since',p.cmd[-1])
        u['order']=p.cmd[-1];p.hour+=3;p.cmd=[];p.done=set()
        p.campaigns()
        self.assertEqual(p.cmd,[])

    def test_harassment_respects_observed_transport_speed(self):
        u=party('a',1);u['movement_speed']=550
        p=planner([u]);cart=party('enemy-cart',2,x=1200)
        cart.update(nation=2,kind='city_cart',healthy=20,movement_speed=550)
        p.units[cart['id']]=cart
        self.assertFalse(p.productive_local([u],patrol=False))
        cart['movement_speed']=500
        self.assertTrue(p.productive_local([u],patrol=False))
        self.assertEqual(p.cmd[-1]['west_task'],'harass')

    def test_real_engine_small_party_clears_bandit_without_artificial_reward(self):
        from aiwar.engine import World
        w=World(73110111,{'mode':'realmap','bandit_cap':0,'auto_city_service':False})
        home=next(c for c in w.cities.values() if c['nation']==0
                  and all(w.cities[i]['nation']==0 for i in c['neighbors']))
        village=next(v for v in w.villages.values() if v['city']==home['id'])
        unit=next(u for u in w.units.values() if u['nation']==0 and u['kind']=='party')
        unit.update(x=village['x'],y=village['y'],healthy=30,wounded=0,food=90000,cavalry=0,cavalry_wounded=0)
        bandit=w.new_unit('bandit',-1,-1,20,unit['x'],unit['y'])
        p=WesternPlanner(w.observe(0))
        self.assertTrue(p.productive_local([p.units[unit['id']]],patrol=False))
        command=next(c for c in p.cmd if c['type']=='attack')
        self.assertEqual(command['target'],bandit['id'])
        self.assertTrue(w.command(0,command)['ok'])
        before=w.stats['bandits_killed']
        for _ in range(24):
            w.step();w.check()
            if bandit['id'] not in w.units:break
        self.assertNotIn(bandit['id'],w.units)
        self.assertEqual(w.stats['bandits_killed'],before+1)
        self.assertGreater(unit['healthy'],0)
        self.assertEqual(w.stats.get('food_looted',0),0)  # Bandits grant no invented income.

    def test_all_eight_private_observations_and_initial_commands(self):
        import copy
        from agent import decide
        from aiwar.engine import World
        w=World(seed=1,config={'mode':'realmap'})
        self.assertEqual(len(w.nations),8)
        for n in w.nation_ids():
            obs=w.observe(n);before=copy.deepcopy(obs)
            commands=decide(obs)
            self.assertEqual(obs,before)
            self.assertLessEqual(len(commands),100)
            for command in commands:
                result=w.command(n,command)
                self.assertTrue(result['ok'],(n,command,result))

    def test_levy_strength_half_and_food_not_discounted(self):
        regular=party('a',1,2000,army='one')
        levy=party('levy',1,2000,army='one');levy['kind']='levy'
        p=planner([regular,levy])
        p.parties=[regular]
        self.assertEqual(p.combat_strength([regular,levy]),225)
        self.assertEqual(p.group_days([regular,levy]),60)
        levy['food']=0
        self.assertEqual(p.group_days([regular,levy]),30)
        p.campaigns()
        # Raw 300 would clear defence 200 * 1.35; weighted 225 must wait.
        self.assertFalse(any(c['type']=='siege' for c in p.cmd))

    def test_joined_levy_in_army_not_party_and_mixed_army_preserved(self):
        from aiwar.engine import World
        obs=World(seed=1,config={'mode':'realmap'}).observe(0)
        own=[u for u in obs['units'] if u['nation']==0 and u['kind']=='party']
        own[0]['army']='host';own[1]['army']='host'
        own[1]['clan']=own[0]['clan']+1000  # An already authorized mixed host.
        levy=dict(own[0],id='test-levy',kind='levy',healthy=200)
        remote=dict(levy,id='test-remote',army=None,x=levy['x']+10000)
        obs['units'].extend([levy,remote])
        p=WesternPlanner(obs)
        self.assertEqual({u['id'] for u in p.armies['host']},{own[0]['id'],own[1]['id'],'test-levy'})
        self.assertFalse(any(u['kind']=='levy' for u in p.parties))
        self.assertEqual(len(p.parties),len(own))

    def test_adapter_augments_new_castle_army_and_legal_mobilization(self):
        from agent import decide
        from aiwar.engine import World
        w=World(1,{'mode':'realmap','bandit_cap':0,'auto_city_service':False})
        clan=w.nations['0']['ruler_clan']
        leader=next(u for u in w.units.values() if u['kind']=='party' and u['clan']==clan)
        city=next(c for c in w.cities.values() if c['nation']==0 and c['clan']==clan and c.get('settlement_type')=='castle')
        support=next(u for u in w.units.values() if u['nation']==0 and u['kind']=='party' and w.clan_party_limit(u['clan'])==1)
        target=next(c['id'] for c in w.cities.values() if c['nation']!=0 and w.can_siege(0,c['id']))
        for u in (leader,support):
            u.update(x=city['x'],y=city['y'],healthy=150,wounded=0,food=900000)
            u['order']=dict(type='move',west_task='rally',west_target=target,vanilla_base=city['id'])
        # Enough local regulars for Dev19's real initial muster threshold.
        for u in [u for u in w.units.values() if u['nation']==0 and u['kind']=='party' and u not in (leader,support)][:3]:
            u.update(x=city['x'],y=city['y'],healthy=150,wounded=0,food=900000)
        for u in w.units.values():
            if u['kind']=='party' and u['nation'] in (1,2):
                u.update(x=city['x'],y=city['y'],healthy=150)
        w.update_known()
        commands=decide(w.observe(0))
        self.assertTrue(any(c['type']=='mobilize' for c in commands),commands)
        self.assertTrue(any(c['type']=='assemble' and c['unit']==leader['id'] and support['id'] in c['units'] for c in commands),commands)
        for c in commands:
            result=w.command(0,c)
            self.assertTrue(result['ok'],(c,result))
        self.assertEqual(leader['army'],support['army'])
        obs=w.observe(0);p=WesternPlanner(obs)
        for members in p.armies.values():
            self.assertEqual(len(members),len({u['id'] for u in members}))

    def test_newly_joined_clan_uses_current_ownership_and_caps(self):
        p=planner([party('joined',9)])
        p.o['limits']['clan_party_caps']={'9':2,'10':3}
        p.o['map_info']['clans']={'9':{'nation':7,'initial_nation':2,'party_slots':2},
                                '10':{'nation':2,'initial_nation':7,'party_slots':3}}
        p.refill_and_raise()
        self.assertEqual([c['clan'] for c in p.cmd if c['type']=='create'],[9])

    def test_clan_caps_are_per_clan(self):
        p=planner([party('a',1)])
        p.o['limits']['clan_party_caps']={'1':1,'2':2,'3':3}
        p.o['map_info']['clans']={str(i):{'nation':7,'party_slots':cap} for i,cap in [(1,1),(2,2),(3,3)]}
        p.refill_and_raise()
        self.assertEqual([c['clan'] for c in p.cmd if c['type']=='create'],[2,3])


if __name__=='__main__':unittest.main()
