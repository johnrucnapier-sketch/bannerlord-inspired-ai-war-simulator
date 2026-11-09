import copy
import json
import unittest
from aiwar import mobilization as m


class World:
    def __init__(self):
        self.cfg = dict(militia_mobilization=True, field_ration=100, warehouse=1000000, garrison_cap=500)
        self.hour=0;self.seq=0;self.units={};self.armies={'a':['p']}
        self.cities={'c':dict(id='c',nation=0,clan=1,settlement_type='castle',x=0,y=0,food=500000,militia='mil',garrison='g')}
        self.villages={'v':dict(id='v',nation=0,city='c',x=10000,y=0,population=200,food=50000)}
        self.new_unit('militia',0,1,100,0,0,uid='mil')
        self.new_unit('garrison',0,1,100,0,0,uid='g')
        self.new_unit('party',0,1,100,0,0,uid='p')['army']='a'
    def ident(self,p):self.seq+=1;return p+str(self.seq)
    def new_unit(self,kind,nation,clan,healthy,x,y,uid=None,home=None,food=0):
        u=dict(id=uid or self.ident('u'),kind=kind,nation=nation,clan=clan,healthy=healthy,wounded=0,x=x,y=y,home=home,food=food,battle=None,army=None,path=[],order=None)
        self.units[u['id']]=u;return u
    def size(self,u):return u['healthy']+u['wounded']
    def besieged(self,c):return False
    def route(self,u,x,y):return [(x,y)]
    def go(self,u,x,y):u.update(path=[(x,y)],order=dict(type='move',x=x,y=y))
    def remove(self,uid,reason='removed'):
        m.on_remove(self,self.units[uid],reason);del self.units[uid]
    def advance(self):
        self.hour+=1
        for u in list(self.units.values()):
            if u['path']:u['x'],u['y']=u['path'][-1];u['path']=[]
        m.tick(self)


class MobilizationTests(unittest.TestCase):
    def start(self, w=None):
        w=w or World()
        result=m.command(w,0,dict(type='mobilize',city='c',army='a'))
        return w,w.mobilizations[result['mobilization']]
    def advance(self,w,n=10):
        for _ in range(n):w.advance()
    def test_courier_tree_and_receipt_rally_clock(self):
        w,r=self.start();self.assertIsNone(r['rally_until'])
        self.assertEqual(w.units['mil']['healthy'],100)
        self.assertEqual(w.villages['v']['population'],200)
        w.advance() # leader receipt, same courier now takes rally leg
        self.assertIsNone(r['rally_until'])
        w.advance()
        self.assertEqual(r['rally_until'],w.hour+72)
        self.assertEqual(w.units['mil']['healthy'],30)
        self.assertEqual(w.villages['v']['population'],200)
        self.assertEqual(len(r['messengers']),2) # separate bound-village messenger
        village_order=r['dispatches']['source:v']
        self.assertEqual(w.units[village_order['unit']]['home'],'c')
        self.advance(w)
        self.assertEqual(w.villages['v']['population'],160)
        self.assertEqual(sorted(w.size(w.units[i]) for i in r['cohorts']),[40,70])
        self.assertEqual(m.away_militia(w,w.cities['c']),70)
        with self.assertRaises(ValueError):m.command(w,0,dict(type='mobilize',city='c',army='a'))
    def test_rally_is_family_home_not_issuer(self):
        w=World();c=dict(w.cities['c'],id='d',x=5000,militia='md',garrison='gd')
        w.cities['d']=c;w.map_clans={'1':{'initial_home_settlement':'d'}}
        w.new_unit('militia',0,1,100,5000,0,uid='md');w.new_unit('garrison',0,1,100,5000,0,uid='gd')
        w,r=self.start(w);self.assertEqual((r['issuer'],r['rally']),('c','d'))
        self.advance(w,3)
        self.assertEqual(w.units['md']['healthy'],30)
        self.assertEqual(r['dispatches']['source:c']['sender'],'d')
        self.advance(w,3)
        self.assertEqual(r['dispatches']['source:v']['sender'],'c')
    def test_pending_dispatch_retries_without_free_soldier_or_food(self):
        w=World();w.cities['c']['food']=0;w.units['g']['healthy']=0
        w,r=self.start(w)
        self.assertEqual(r['messengers'],[])
        self.advance(w);self.assertEqual(w.units['mil']['healthy'],100)
        w.cities['c']['food']=1000;w.units['g']['healthy']=1
        w.advance();self.assertEqual(len(r['messengers']),1)
        self.assertEqual(w.cities['c']['food'],0);self.assertEqual(w.units['g']['healthy'],0)
    def test_pending_source_reserves_real_grain(self):
        w=World();w.villages['v']['food']=0
        w,r=self.start(w);self.advance(w)
        self.assertIn('v',r['pending_sources']);self.assertEqual(w.villages['v']['population'],200)
        w.villages['v']['food']=10000
        self.assertEqual(m.pre_departure(w,w.villages['v']),10000)
        self.assertEqual(w.villages['v']['food'],10000)
        w.villages['v']['food']+=10000
        self.assertEqual(m.pre_departure(w,w.villages['v']),0)
        self.assertEqual(w.villages['v']['food'],0);self.assertEqual(w.villages['v']['population'],160)
        self.assertNotIn('v',r['pending_sources'])
    def test_disabled_and_no_pending_reserve_nothing(self):
        w=World();self.assertEqual(m.pre_departure(w,w.villages['v']),0)
        w.cfg['militia_mobilization']=False
        self.assertEqual(m.pre_departure(w,w.villages['v']),0)
    def test_engine_contact_radius_boundary(self):
        self.assertTrue(m._near(dict(x=0,y=0),dict(x=300,y=400)))
        self.assertFalse(m._near(dict(x=0,y=0),dict(x=301,y=400)))
    def test_formula_and_odd_rounding(self):
        w=World();self.assertEqual(m.levy_food_required(w,41),21000)
        self.assertEqual(m.levy_food_required(w,40),20000)
        w.cfg['levy_food_per_two']=2000;self.assertEqual(m.levy_food_required(w,41),42000)
    def test_invalid_command_does_not_allocate_ids(self):
        w=World();before=w.seq;w.units['p']['x']=20000
        with self.assertRaises(ValueError):m.command(w,0,dict(type='mobilize',city='c',army='a'))
        self.assertEqual(w.seq,before)
    def test_missing_commander_cannot_receive_initial_order(self):
        w,r=self.start();w.armies.pop('a');w.remove('p','defeated')
        self.advance(w,8)
        self.assertEqual(w.units['mil']['healthy'],100)
        self.assertEqual(w.villages['v']['population'],200)
        self.assertIsNone(r['rally_until']);self.assertFalse(r['cohorts'])
        self.assertEqual(r['dispatches']['leader:c']['status'],'failed')
        self.assertEqual(r['status'],'completed')
    def test_dissolution_requires_physical_discovery(self):
        w,r=self.start();self.advance(w,10)
        w.units['p']['x']=20000;m.tick(w);w.armies.pop('a');w.units['p']['army']=None
        m.tick(w)
        self.assertTrue(all(w.units[i]['phase']=='rally' for i in r['cohorts']))
        w.hour=r['rally_until'];m.tick(w)
        self.assertTrue(all(w.units[i]['phase']=='joining' for i in r['cohorts']))
        w.advance();self.assertTrue(all(w.units[i]['phase']=='return' for i in r['cohorts']))
    def test_survivors_return_losses_and_reserve_decay(self):
        w,r=self.start();self.advance(w,80)
        self.assertEqual(len(w.armies['a']),3)
        village=next(w.units[i] for i,p in r['cohorts'].items() if p['village'])
        village['healthy']-=8;village['wounded']=3
        settlement=next(w.units[i] for i,p in r['cohorts'].items() if not p['village'])
        settlement['healthy']-=10
        w.units['p']['x']=20000
        for i in w.armies['a']:w.units[i]['x']=20000
        m.command(w,0,dict(type='demobilize',army='a'))
        self.assertEqual(village['phase'],'serving')
        self.advance(w,30)
        self.assertEqual(w.villages['v']['population'],195);self.assertEqual(w.units['mil']['healthy'],90)
        self.assertEqual(m.away_militia(w,w.cities['c']),10)
        w.hour+=m.RECOVERY_HOURS;m.tick(w);self.assertEqual(r['status'],'completed')
    def test_cancel_pending_source_only_on_receipt(self):
        w=World();w.villages['v']['food']=0;w,r=self.start(w);self.advance(w)
        self.assertIn('v',r['pending_sources'])
        m.command(w,0,dict(type='demobilize',army='a'))
        self.assertIn('v',r['pending_sources'])
        self.assertNotIn('v',r['cancelled_sources'])
        self.advance(w,30)
        self.assertNotIn('v',r['pending_sources']);self.assertIn('v',r['cancelled_sources'])
        self.assertEqual(w.villages['v']['population'],200)
    def test_dead_order_courier_retries_and_no_duplicate_extraction(self):
        w,r=self.start();uid=r['messengers'][0];w.remove(uid,'defeated')
        self.assertEqual(len(r['pending_dispatches']),1)
        self.advance(w,15)
        self.assertEqual(w.villages['v']['population'],160)
        self.assertEqual(len(r['cohorts']),2)
    def test_destroyed_cohort_never_returns(self):
        w,r=self.start();self.advance(w,10)
        uid=next(i for i,p in r['cohorts'].items() if p['village']);w.remove(uid,'defeated')
        m.command(w,0,dict(type='demobilize',army='a'));self.advance(w,30)
        self.assertEqual(w.villages['v']['population'],160)
    def test_capture_blocks_raising_and_population_return(self):
        w,r=self.start();w.villages['v']['nation']=1;self.advance(w,10)
        self.assertEqual(w.villages['v']['population'],200)
        self.assertEqual(len(r['cohorts']),1)
    def test_remote_capture_discovered_at_bound_or_rally_arrival(self):
        for phase in ('bound','rally'):
            with self.subTest(phase=phase):
                w,r=self.start();self.advance(w,10)
                uid=next(i for i,p in r['cohorts'].items() if p['village'])
                u=w.units[uid];u.update(phase=phase,x=10000,y=0)
                w.go(u,0,0);path=copy.deepcopy(u['path']);order=copy.deepcopy(u['order'])
                w.cities['c']['nation']=1
                m.tick(w)
                self.assertEqual(u['phase'],phase);self.assertEqual(u['path'],path);self.assertEqual(u['order'],order)
                w.advance();self.assertEqual(u['phase'],'return')
    def test_extinction_migration_does_not_remote_cancel_bound_or_rally(self):
        for phase in ('bound','rally'):
            with self.subTest(phase=phase):
                w,r=self.start();self.advance(w,10)
                uid=next(i for i,p in r['cohorts'].items() if p['village'])
                u=w.units[uid];u.update(phase=phase,x=10000,y=0)
                w.go(u,0,0);path=copy.deepcopy(u['path'])
                # Match succession.resolve's actual migration contract: rec/unit
                # nation changes; destroyed army disappears; physical orders stay.
                r['nation']=2
                for unit in w.units.values():
                    if unit['kind'] in ('levy','mobilization_messenger'):unit['nation']=2
                w.armies.clear();w.units['p']['army']=None
                m.tick(w)
                self.assertEqual(u['phase'],phase);self.assertEqual(u['path'],path)
                w.advance();self.assertEqual(u['phase'],'return')
    def test_pending_captured_source_waits_without_deduction_and_blocks_repeat(self):
        w=World();w.villages['v']['food']=0;w,r=self.start(w);self.advance(w,10)
        self.assertIn('v',r['pending_sources'])
        w.villages['v']['nation']=1;w.villages['v']['food']=30000
        self.advance(w,5)
        self.assertIn('v',r['pending_sources']);self.assertEqual(w.villages['v']['population'],200)
        self.assertEqual(m.pre_departure(w,w.villages['v']),0)
        with self.assertRaises(ValueError):m.command(w,0,dict(type='mobilize',city='c',army='a'))
        w.villages['v']['nation']=0;w.advance()
        self.assertNotIn('v',r['pending_sources']);self.assertEqual(w.villages['v']['population'],160)
    def test_loss_reservation_rounds_once_per_source(self):
        w,r=self.start();c=w.cities['c']
        w.hour=m.RECOVERY_HOURS//2
        r['losses']=[dict(source='c',count=50,hour=0)]
        self.assertEqual(m.away_militia(w,c),25)
        r['losses']=[dict(source='c',count=1,hour=0) for _ in range(50)]
        self.assertEqual(m.away_militia(w,c),25)
        r['losses']=[dict(source='c',count=1,hour=h) for h in range(50)]
        self.assertEqual(m.away_militia(w,c),26)
        # A source-wide aggregate also rounds once across historical records.
        other=copy.deepcopy(r);other['id']='historical';other['losses']=r['losses'][25:]
        r['losses']=r['losses'][:25];w.mobilizations[other['id']]=other
        self.assertEqual(m.away_militia(w,c),26)
        w.hour=m.RECOVERY_HOURS+49
        self.assertEqual(m.away_militia(w,c),0)
    def test_fog_and_determinism(self):
        w,r=self.start();self.assertEqual(m.observe(w,1),[])
        self.advance(w,5);saved=copy.deepcopy(w)
        self.advance(w,80);self.advance(saved,80);self.assertEqual(w.__dict__,saved.__dict__)
    def test_cancel_idempotence_no_remote_changes(self):
        w,r=self.start();m.command(w,0,dict(type='demobilize',army='a'));n=len(w.units)
        m.command(w,0,dict(type='demobilize',army='a'));self.assertEqual(len(w.units),n)
        self.advance(w,30)
        self.assertEqual(w.villages['v']['population'],200);self.assertEqual(w.units['mil']['healthy'],100)
        self.assertEqual(w.units['g']['healthy'],100);self.assertEqual(r['status'],'completed')

class PhantomCancellationTests(unittest.TestCase):
    def fixture(self):
        """Portable reconstruction of mob14949's closed tree, not its save file."""
        w=World();w.units={};w.cities={};w.villages={};w.armies={'new-army':['leader']}
        w.hour=13089
        def city(cid,x=0,nation=3,clan=48,kind='town'):
            c=dict(id=cid,nation=nation,clan=clan,settlement_type=kind,x=x,y=0,
                   food=500000,militia='m_'+cid,garrison='g_'+cid)
            w.cities[cid]=c
            for unit_kind,key in (('militia','militia'),('garrison','garrison')):
                w.new_unit(unit_kind,nation,clan,100,x,0,uid=c[key])
        city('castle_K2',50000,7,99,'castle')
        city('safe_new_castle',kind='castle')
        for index,cid in enumerate(('town_ES6','town_EW5'),1):
            city(cid,index*10000)
            for suffix in (1,2):
                sid='village_'+cid[5:]+'_'+str(suffix)
                w.villages[sid]=dict(id=sid,nation=3,city=cid,x=index*10000+1000,
                                    y=0,population=200,food=50000)
        w.new_unit('party',3,48,100,0,0,uid='leader')['army']='new-army'
        received=['castle_K2','castle_village_K2_1','castle_village_K2_2',
                  'castle_EN4','castle_village_EN4_1','town_A2',
                  'castle_village_EN4_2','village_A2_3','village_A2_2']
        raised=['castle_K2','castle_EN4','castle_village_EN4_1','town_A2','castle_village_EN4_2']
        r=dict(id='mob14949',nation=3,clan=48,issuer='castle_K2',rally='castle_K2',
               army='a11473',started=9264,rally_until=9338,status='demobilizing',
               demobilize_requested=True,last_known_leader=dict(x=844832,y=381642),
               cohorts={f'old-cohort-{i}':dict(source=s,village='village' in s,
                        last_size=0,returned=False,removed=True) for i,s in enumerate(raised)},
               messengers=[],dispatches={},pending_dispatches=[],pending_sources=[],
               received_sources=received,raised_sources=raised,cancelled_sources=list(received),
               losses=[dict(source='town_A2',count=7,hour=9879)])
        # town_ES6's original courier finished without actual local receipt.
        for i,sid in enumerate(received+['town_ES6']):
            mission='leader' if sid=='castle_K2' else 'source';key=mission+':'+sid
            uid='old-messenger-'+str(i);r['messengers'].append(uid)
            r['dispatches'][key]=dict(sender='castle_K2',target=sid,mission=mission,
                                      status='delivered',unit=uid)
        for i,sid in enumerate(received):
            uid='old-cancel-'+str(i);r['messengers'].append(uid)
            r['dispatches']['cancel_source:'+sid]=dict(sender='castle_K2',target=sid,
                mission='cancel_source',status='delivered',unit=uid)
        for sid in ('town_ES6','village_ES6_1','village_ES6_2',
                    'town_EW5','village_EW5_1','village_EW5_2'):
            m._queue(r,'castle_K2',sid,'cancel_source')
        w.mobilizations={r['id']:r}
        return w,r

    def resources(self,w):
        return copy.deepcopy((w.units,w.cities,w.villages,w.armies))

    def request_new(self,w):
        return m.command(w,3,dict(type='mobilize',city='safe_new_castle',army='new-army'))

    def test_old_phantom_record_clears_only_after_loss_expiry(self):
        w,r=self.fixture();pending=list(r['pending_dispatches'])
        resources=self.resources(w);receipts=copy.deepcopy(r['cancelled_sources'])
        delivered={k:copy.deepcopy(t) for k,t in r['dispatches'].items() if t['status']=='delivered'}
        losses=copy.deepcopy(r['losses'])
        m.tick(w)
        self.assertEqual(self.resources(w),resources)
        self.assertEqual(r['cancelled_sources'],receipts)
        self.assertEqual(r['losses'],losses)
        self.assertFalse(r['pending_dispatches'])
        self.assertTrue(all(r['dispatches'][k]['status']=='obsolete' for k in pending))
        self.assertTrue(all(r['dispatches'][k]==task for k,task in delivered.items()))
        self.assertEqual(r['status'],'demobilizing')
        with self.assertRaisesRegex(ValueError,'仍有动员'):self.request_new(w)
        w.hour=9879+m.RECOVERY_HOURS-1;m.tick(w)
        with self.assertRaisesRegex(ValueError,'仍有动员'):self.request_new(w)
        w.hour+=1;m.tick(w)
        self.assertEqual(r['status'],'completed');self.assertFalse(r['losses'])
        self.assertEqual(self.resources(w),resources)
        before_food=sum(c['food'] for c in w.cities.values())+sum(u['food'] for u in w.units.values())
        before_men=sum(w.size(u) for u in w.units.values())
        self.assertTrue(self.request_new(w)['ok'])
        self.assertEqual(sum(w.size(u) for u in w.units.values()),before_men)
        self.assertEqual(sum(c['food'] for c in w.cities.values())+sum(u['food'] for u in w.units.values()),before_food)
        self.assertEqual(w.units['g_safe_new_castle']['healthy'],99)
        self.assertEqual(w.cities['safe_new_castle']['food'],499000)

    def test_closed_tree_does_not_add_later_fief_cancellations(self):
        w,r=self.fixture();m.tick(w);before=copy.deepcopy(r['dispatches'])
        w.cities['later_fief']=dict(w.cities['safe_new_castle'],id='later_fief',x=30000,
                                   militia='later-militia',garrison='later-garrison')
        w.new_unit('militia',3,48,100,30000,0,uid='later-militia')
        w.new_unit('garrison',3,48,100,30000,0,uid='later-garrison')
        resources=self.resources(w)
        for _ in range(3):w.advance()
        self.assertEqual(r['dispatches'],before)
        self.assertNotIn('cancel_source:safe_new_castle',r['dispatches'])
        self.assertNotIn('cancel_source:later_fief',r['dispatches'])
        self.assertEqual(self.resources(w),resources)
        self.assertEqual(r['status'],'demobilizing')

    def test_real_work_prevents_cleanup_and_repeat_mobilization(self):
        cases=('original_pending','original_enroute','local_raising','live_cohort',
               'live_messenger','receipt_not_cancelled','real_cancel_pending',
               'cancel_enroute','pending_with_unit')
        for case in cases:
            with self.subTest(case=case):
                w,r=self.fixture();w.hour=9879+m.RECOVERY_HOURS;r['losses']=[]
                if case.startswith('original_'):
                    r['dispatches']['source:town_ES6']['status']=case.split('_')[1]
                elif case=='local_raising':r['pending_sources'].append('town_ES6')
                elif case=='live_cohort':
                    uid=next(iter(r['cohorts']));w.new_unit('levy',3,48,10,30000,0,uid=uid)
                elif case=='live_messenger':
                    w.new_unit('mobilization_messenger',3,48,1,30000,0,uid=r['messengers'][0])
                elif case=='receipt_not_cancelled':r['cancelled_sources'].remove('castle_EN4')
                elif case=='real_cancel_pending':
                    key='cancel_source:castle_EN4'
                    r['dispatches'][key].update(status='pending',unit=None)
                    r['pending_dispatches'].append(key)
                elif case=='cancel_enroute':
                    r['dispatches']['cancel_source:town_ES6']['status']='enroute'
                elif case=='pending_with_unit':
                    r['dispatches']['cancel_source:town_ES6']['unit']='not-confirmed-gone'
                before=copy.deepcopy(w.__dict__)
                self.assertFalse(m._retire_phantom_cancellations(w,r))
                self.assertEqual(w.__dict__,before)
                with self.assertRaisesRegex(ValueError,'仍有动员'):self.request_new(w)

    def test_already_dispatched_cancellation_keeps_physical_courier(self):
        w,r=self.fixture();key='cancel_source:town_ES6';task=r['dispatches'][key]
        courier=w.new_unit('mobilization_messenger',3,48,1,0,0,uid='live-cancel',home='castle_K2',food=1000)
        courier.update(mobilization=r['id'],mission='cancel_source',dispatch_key=key,
                       target=task['target'],phase='orders',courier_cavalry=0)
        r['messengers'].append(courier['id']);task.update(status='enroute',unit=courier['id'])
        r['pending_dispatches'].remove(key)
        pending=list(r['pending_dispatches']);resources=self.resources(w)
        m._cancel_orders(w,r)
        self.assertEqual(self.resources(w),resources)
        self.assertEqual(task['status'],'enroute');self.assertEqual(courier['x'],0)
        self.assertTrue(all(r['dispatches'][k]['status']=='pending' for k in pending))
        m._messenger_tick(w,courier,r)
        self.assertEqual(task['status'],'enroute');self.assertEqual(courier['phase'],'orders')
        self.assertNotIn('town_ES6',r['cancelled_sources'])
        # Only actual movement to contact permits delivery; return is separate.
        w.advance()
        self.assertEqual(task['status'],'delivered');self.assertEqual(courier['phase'],'return')
        self.assertEqual(courier['x'],w.cities['town_ES6']['x'])
        self.assertIn(courier['id'],w.units)

    def test_cleanup_has_no_remote_ownership_or_observation_dependency(self):
        a,ra=self.fixture();b=copy.deepcopy(a);rb=b.mobilizations[ra['id']]
        # Worlds have identical own order history but different unseen owners.
        b.cities['castle_K2'].update(nation=6,clan=70)
        b.cities['town_ES6'].update(nation=7,clan=71)
        b.villages['village_ES6_1']['nation']=7
        before_a=self.resources(a);before_b=self.resources(b)
        m.tick(a);m.tick(b)
        self.assertEqual(m.observe(a,3),m.observe(b,3))
        self.assertEqual(m.observe(a,7),[]);self.assertEqual(m.observe(b,7),[])
        self.assertEqual(self.resources(a),before_a);self.assertEqual(self.resources(b),before_b)
        self.assertEqual(ra,rb)

    def test_old_json_roundtrip_and_cleanup_are_deterministic(self):
        a,ra=self.fixture();b=World.__new__(World)
        b.__dict__.update(json.loads(json.dumps(a.__dict__)))
        m.tick(a);m.tick(b);self.assertEqual(a.__dict__,b.__dict__)
        a.hour=b.hour=9879+m.RECOVERY_HOURS
        m.tick(a);m.tick(b);self.assertEqual(a.__dict__,b.__dict__)
        self.assertEqual(ra['status'],'completed')


class EngineMobilizationIntegration(unittest.TestCase):
    def test_pending_and_inflight_roundtrip(self):
        import tempfile
        from pathlib import Path
        from aiwar.engine import World as EngineWorld
        w=EngineWorld(7,dict(mode='realmap',auto_city_service=False,bandit_cap=0))
        c=w.cities['castle_K5']
        parties=[u for u in w.units.values() if u['kind']=='party' and u['clan']==c['clan']][:2]
        for u in parties:u.update(x=c['x'],y=c['y'],path=[],order=None)
        aid=w.command(c['nation'],dict(type='assemble',unit=parties[0]['id'],units=[u['id'] for u in parties]))['army']
        c['food']=0
        result=w.command(c['nation'],dict(type='mobilize',city=c['id'],army=aid))
        rec=w.mobilizations[result['mobilization']]
        self.assertTrue(rec['pending_dispatches']);self.assertFalse(rec['messengers'])
        def restored():
            with tempfile.TemporaryDirectory() as d:
                path=Path(d)/'state.json';w.save(path);return EngineWorld.load(path)
        other=restored();self.assertEqual(w.digest(),other.digest())
        c['food']=500000;other.cities[c['id']]['food']=500000
        for _ in range(4):w.step(1);other.step(1)
        self.assertEqual(w.digest(),other.digest())
        self.assertTrue(any(w.units[i]['phase']=='orders' and w.units[i]['path'] for i in rec['messengers'] if i in w.units))
        other=restored()
        for _ in range(4):w.step(1);other.step(1)
        self.assertEqual(w.digest(),other.digest())
    def test_distant_village_weekly_grain_physical_join_and_return(self):
        import tempfile
        from pathlib import Path
        from aiwar.engine import World as EngineWorld
        w=EngineWorld(7,dict(mode='realmap',auto_city_service=False,bandit_cap=0,growth=0,militia_growth=0))
        c=w.cities['castle_K5'];v=w.villages['castle_village_K5_2']
        self.assertGreater((v['x']-c['x'])**2+(v['y']-c['y'])**2,10000**2)
        parties=[u for u in w.units.values() if u['kind']=='party' and u['clan']==c['clan']][:2]
        for u in parties:u.update(x=c['x'],y=c['y'],path=[],order=None)
        for city in w.cities.values():
            if city['clan']==c['clan']:city['food']=w.cfg['warehouse']
        initial_population=v['population'];v['food']=0
        result=w.command(c['nation'],dict(type='assemble',unit=parties[0]['id'],units=[u['id'] for u in parties]))
        self.assertTrue(result['ok'],result);aid=result['army']
        stock=lambda:sum(s['food'] for s in list(w.cities.values())+list(w.villages.values()))+sum(u['food']+u['cargo_food'] for u in w.units.values())
        before=stock();result=w.command(c['nation'],dict(type='mobilize',city=c['id'],army=aid))
        self.assertTrue(result['ok'],result);self.assertEqual(stock(),before)
        rec=w.mobilizations[result['mobilization']]
        # After fixture setup all movement is real EngineWorld navigation, no relocation.
        traveled=False
        for _ in range(100):
            w.step(1)
            for uid in rec['messengers']:
                u=w.units.get(uid)
                if u and u.get('target')==v['id'] and not m._near(u,c) and not m._near(u,v):traveled=True
            if v['id'] in rec['pending_sources']:break
        self.assertTrue(traveled)
        self.assertIn(v['id'],rec['pending_sources'])
        self.assertEqual(v['population'],initial_population)
        # Receipt is persisted across a real engine save/reload.
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'world.json';w.save(path);other=EngineWorld.load(path)
            self.assertEqual(w.digest(),other.digest());other.step(2);w.step(2)
            self.assertEqual(w.digest(),other.digest())
        levy=None
        for _ in range(250):
            w.step(1)
            levy=next((w.units[i] for i,p in rec['cohorts'].items() if p['source']==v['id'] and i in w.units),None)
            if levy and levy['phase']=='serving':break
        self.assertIsNotNone(levy)
        self.assertEqual(levy['phase'],'serving')
        self.assertEqual(levy['army'],aid)
        self.assertEqual(v['population'],initial_population-initial_population//5)
        self.assertGreaterEqual(w.hour,168)
        w.check()
        result=w.command(c['nation'],dict(type='demobilize',army=aid));self.assertTrue(result['ok'],result)
        self.assertEqual(levy['phase'],'serving')
        # No command-time population restoration; the cohort must march home.
        self.assertNotEqual(v['population'],initial_population)
        for _ in range(250):
            w.step(1)
            if levy['id'] not in w.units:break
        self.assertNotIn(levy['id'],w.units)
        self.assertEqual(v['population'],initial_population)
        self.assertTrue(rec['cohorts'][levy['id']]['returned'])
        w.check()

if __name__ == '__main__':unittest.main()
