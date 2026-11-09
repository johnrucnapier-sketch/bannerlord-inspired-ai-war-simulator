"""Independent rebuilt-diplomacy regressions; no frozen baseline modifications."""
import copy
import json
import unittest
from aiwar import diplomacy as d, realmap_rules
from aiwar.engine import World

class SmallWorld:
    def __init__(self):
        self.cfg={'diplomacy_enabled':True};self.hour=0;self.extinct_nations=[]
        self.relations={str(a):{str(b):'self' if a==b else 'peace' for b in range(5)} for a in range(5)}
        self.cities={};self.units={};self.villages={};self.battles={};self.events=[]
        d.initialize(self)
    def nation_ids(self):return tuple(range(5))
    def hostile(self,a,b):return a!=b and (-1 in (a,b) or self.relations[str(a)][str(b)]=='war')
    def emit(self,*args,**kwargs):self.events.append((args,kwargs))

def relation(w,a,b,kind,expires=99999):
    w.relations[str(a)][str(b)]=w.relations[str(b)][str(a)]=kind
    if kind in ('nap','alliance'):d.state(w)['treaties'][d.pair(a,b)]={'kind':kind,'expires_hour':expires}

def submit(w,n,action,**kwargs):return d.submit(w,n,dict(type='diplomacy',action=action,**kwargs))

def treaty(w,a,b,kind):
    w.hour+=168;submit(w,a,'propose_'+kind,target=b);d.resolve(w)
    p=next(p for p in d.state(w)['proposals'].values() if p['from_nation']==a and p['to_nation']==b)
    submit(w,b,'accept',proposal_id=p['id']);d.resolve(w)

class ReviewTests(unittest.TestCase):
    def test_coalition_spoils_preserve_allied_food(self):
        w=SmallWorld();relation(w,0,1,'alliance');relation(w,0,2,'war');relation(w,1,2,'war')
        w.stats={'food_lost':0};w.food_cap=lambda u:1000000
        w.units={str(n):dict(id=str(n),nation=n,kind='party',healthy=100 if n<2 else 0,food=1000,cargo_food=200) for n in range(3)}
        b=dict(id='b',surviving_nations=[0,1],sides={str(n):[str(n)] for n in range(3)})
        realmap_rules.spoils(w,b,0)
        self.assertEqual((w.units['1']['food'],w.units['1']['cargo_food']),(1000,200))
        self.assertEqual((w.units['2']['food'],w.units['2']['cargo_food']),(0,0))

    def test_realmap_coalition_battle_completes(self):
        w=World(31,dict(mode='realmap',diplomacy_enabled=True));relation(w,0,1,'alliance')
        units=[]
        for n in (0,1,2):
            clan=next(int(k) for k,c in w.map_clans.items() if c['nation']==n)
            u=w.new_unit('party',n,clan,100 if n<2 else 0,0,0,food=1000)
            u['battle']='review';units.append(u)
        b=dict(id='review',x=0,y=0,city=None,start=0,prepare_hours=0,combat_hours=24,attacker=0,defender=2,
               sides={str(n):[u['id']] for n,u in enumerate(units)},power={u['id']:u['healthy']*2 for u in units},remainders={})
        w.battles['review']=b;w.battle_tick()
        self.assertNotIn('review',w.battles);self.assertEqual(units[1]['food'],1000)
        self.assertIsNone(units[1]['battle']);self.assertEqual(set(b['surviving_nations']),{0,1})

    def test_all_relief_coalition_survivors_return(self):
        w=SmallWorld();relation(w,0,1,'alliance');relation(w,0,2,'war');relation(w,1,2,'war')
        w.cities={'c':{'name':'City'}};w.can_siege=lambda n,c:True
        w.units={str(n):dict(id=str(n),nation=n,kind='party',healthy=100,battle=None) for n in (0,1)}
        parent=dict(id='parent',city='c',defender=2,sides={'0':[],'1':[],'2':[]},relief_battle='child',suspended_losses={'0':3,'1':4})
        field=dict(id='child',relief_for='parent',surviving_nations=[0,1],sides={'0':['0'],'1':['1'],'2':[]})
        w.battles={'parent':parent}
        def join(b,u):b['sides'][str(u['nation'])].append(u['id']);u['battle']=b['id']
        w.join=join;World.finish_relief_battle(w,field,0)
        for n,loss in ((0,3),(1,4)):
            self.assertEqual(w.units[str(n)]['battle'],'parent');self.assertEqual(w.units[str(n)]['war_losses'],loss)

    def test_peace_cleans_linked_battles_raid_and_orders(self):
        w=SmallWorld();relation(w,0,1,'war')
        w.units={'u':dict(nation=0,battle='relief',order={'type':'raid','target':'v'},path=[1]),'g':dict(nation=1,battle='siege',order=None,path=[])}
        w.villages={'v':dict(nation=1,raid={'unit':'u'})}
        w.battles={'siege':dict(sides={'0':[],'1':['g']},relief_battle='relief'),'relief':dict(sides={'0':['u'],'1':[]},relief_for='siege')}
        treaty(w,0,1,'peace');self.assertFalse(w.battles);self.assertIsNone(w.villages['v']['raid'])
        self.assertTrue(all(u['battle'] is None and u['order'] is None and u['path']==[] for u in w.units.values()))

    def test_alliance_imports_existing_wars_and_new_declarations(self):
        w=SmallWorld();relation(w,0,2,'war');relation(w,2,3,'alliance');relation(w,0,3,'war')
        treaty(w,0,1,'alliance')
        for a in (0,1):
            for b in (2,3):self.assertTrue(w.hostile(a,b))
        w.hour+=168;submit(w,4,'declare_war',target=0);d.resolve(w)
        self.assertTrue(w.hostile(4,0));self.assertTrue(w.hostile(4,1));d.check(w)

    def test_nap_blocks_alliance_import_atomically(self):
        w=SmallWorld();relation(w,0,2,'war');relation(w,1,2,'nap');before=copy.deepcopy(w.relations)
        submit(w,0,'propose_alliance',target=1);d.resolve(w)
        self.assertEqual(before,w.relations);self.assertFalse(d.state(w)['proposals'])

    def test_nap_expiry_is_peace_not_war(self):
        w=SmallWorld();treaty(w,0,1,'nap');submit(w,1,'declare_war',target=0);d.resolve(w)
        self.assertEqual(w.relations['0']['1'],'nap')
        w.hour+=w.cfg['diplomacy_nap_hours'];d.tick(w);self.assertEqual(w.relations['0']['1'],'peace')

    def test_simultaneous_alliance_and_war_conflict(self):
        w=SmallWorld();submit(w,0,'propose_alliance',target=1);d.resolve(w)
        submit(w,1,'accept',proposal_id=d.observe(w,1)['incoming'][0]['id']);submit(w,2,'declare_war',target=0)
        d.resolve(w);d.check(w)
        self.assertEqual(w.relations['0']['1'],'peace');self.assertEqual(w.relations['0']['2'],'peace')

    def test_crossed_identical_offers_do_not_deadlock(self):
        w=SmallWorld();submit(w,0,'propose_alliance',target=1);submit(w,1,'propose_alliance',target=0);d.resolve(w)
        for n in (0,1):submit(w,n,'accept',proposal_id=d.observe(w,n)['incoming'][0]['id'])
        d.resolve(w);d.check(w);self.assertEqual(w.relations['0']['1'],'alliance')

    def test_proposals_private_and_defensive_copies(self):
        w=SmallWorld();submit(w,0,'propose_peace',target=1,reason={'own_food_days':2});d.resolve(w)
        observer=d.observe(w,2);self.assertFalse(observer['incoming'] or observer['outgoing'] or observer['events'])
        own=d.observe(w,0);own['outgoing'][0]['kind']='alliance';self.assertEqual(d.observe(w,1)['incoming'][0]['kind'],'peace')

    def test_extinction_drops_treaties_and_proposals(self):
        w=SmallWorld();treaty(w,0,1,'alliance');w.hour+=168;submit(w,0,'propose_nap',target=2);d.resolve(w)
        w.extinct_nations=[0];d.tick(w)
        self.assertFalse(d.state(w)['treaties']);self.assertFalse(d.state(w)['proposals'])
        self.assertNotIn(0,sum(d.components(w),[]));self.assertEqual(w.relations['1']['2'],'peace')

    def test_weekly_hold_event_and_serialized_clock(self):
        w=SmallWorld();submit(w,0,'hold');d.resolve(w);self.assertFalse(d.decision_due(w,0))
        w.hour=168;self.assertTrue(d.decision_due(w,0));submit(w,0,'hold');d.resolve(w)
        w.cities['new']={'id':'new','nation':0};w.hour+=max(1,w.cfg.get('diplomacy_event_cooldown_hours',0))
        self.assertTrue(d.decision_due(w,0))
        restored=copy.deepcopy(w);restored.diplomacy_state=json.loads(json.dumps(w.diplomacy_state))
        self.assertEqual(d.decision_due(w,0),d.decision_due(restored,0))

    def test_real_extinction_migrates_assets_without_treaties_or_vision(self):
        from aiwar import succession
        w=World(8321,dict(mode='realmap',nations=['empire_w','empire','empire_s'],diplomacy_enabled=True,bandit_cap=0))
        relation(w,0,1,'alliance');relation(w,0,2,'nap');relation(w,1,2,'peace')
        parties={u['id']:copy.deepcopy(u) for u in w.units.values() if u['nation']==0 and u['kind']=='party'}
        known=copy.deepcopy(w.known)
        for c in list(w.cities.values()):
            if c['nation']==0:w.capture(c['id'],2,[])
        succession.resolve(w);d.check(w)
        self.assertIn(0,w.extinct_nations);self.assertFalse(d.state(w)['treaties'])
        self.assertEqual(w.relations['1']['2'],'peace');self.assertEqual(known,w.known)
        for uid,before in parties.items():
            after=w.units[uid];self.assertIn(after['nation'],(1,2))
            for key in ('healthy','wounded','food','x','y'):self.assertEqual(after[key],before[key])
            self.assertIsNone(after['order']);self.assertIsNone(after['battle'])

    def test_10000_random_diplomatic_batches_preserve_invariants(self):
        import random
        rng=random.Random(20261109);coverage={}
        actions=('hold','propose_peace','propose_nap','propose_alliance','declare_war','leave_alliance')
        for episode in range(100):
            w=SmallWorld()
            for turn in range(100):
                w.hour+=rng.choice((1,24,168,672));d.tick(w)
                if turn==70 and episode%2==0:
                    w.extinct_nations=[rng.randrange(5)];d.tick(w)
                for n in sorted(d.live(w)):
                    incoming=d.observe(w,n)['incoming']
                    for proposal in incoming:
                        if rng.random()<.8:submit(w,n,rng.choice(('accept','accept','reject')),proposal_id=proposal['id'])
                    if d.decision_due(w,n):
                        target=rng.choice(sorted(d.live(w)-{n}))
                        submit(w,n,rng.choice(actions),target=target)
                if turn==50:
                    reversed_world=copy.deepcopy(w)
                    reversed_world.diplomacy_state['queue'].reverse()
                    d.resolve(reversed_world)
                for result in d.resolve(w):
                    key=result['action']+':'+result['status'];coverage[key]=coverage.get(key,0)+1
                d.check(w)
                if turn==50:
                    self.assertEqual(w.relations,reversed_world.relations)
                    self.assertEqual(w.diplomacy_state,reversed_world.diplomacy_state)
                for key,t in d.state(w)['treaties'].items():
                    a,b=d.unpair(key)
                    self.assertEqual(w.relations[str(a)][str(b)],t['kind'])
                    self.assertGreater(t['expires_hour'],w.hour)
                    self.assertTrue({a,b}<=d.live(w))
                for n in d.live(w):
                    obs=d.observe(w,n)
                    self.assertTrue(all(p['to_nation']==n for p in obs['incoming']))
                    self.assertTrue(all(p['from_nation']==n for p in obs['outgoing']))
                    self.assertTrue(all(e['nation']==n for e in obs['events']))
                if turn%20==0:w.diplomacy_state=json.loads(json.dumps(w.diplomacy_state))
        for key in ('alliance:accepted','nap:accepted','peace:accepted','declare_war:accepted','leave_alliance:accepted'):
            self.assertGreater(coverage.get(key,0),0)
        print('Random review coverage: '+json.dumps(coverage,sort_keys=True))

if __name__=='__main__':unittest.main()
