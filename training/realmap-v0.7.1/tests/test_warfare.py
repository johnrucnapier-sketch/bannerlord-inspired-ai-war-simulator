import copy
import tempfile
import unittest
from pathlib import Path
from aiwar.engine import World
from aiwar import economy
from aiwar.policies import decide, decision_cycle
from aiwar.warfare import allocate, city_risks
from aiwar.replay import replay


def traffic(obs, city='c00', count=6, blocked=6):
    obs['hour']=700
    obs['economy'][city]=dict(nation=0,since=0,trips={},samples=[],events=[
        dict(hour=400+i*10,trip_start=400+i*10,kind=kind)
        for i in range(count) for kind in (['depart','intercept'] if i<blocked else ['depart','delivered'])])


class EconomyTests(unittest.TestCase):
    def test_transport_cohort_and_deduplication(self):
        w=World(1);u=next(u for u in w.units.values() if u['kind']=='village_cart' and u['nation']==0)
        w.hour=168;economy.transport(w,'depart',u)
        economy.transport(w,'intercept',u);economy.transport(w,'intercept',u)
        economy.transport(w,'delivered',u);economy.transport(w,'returned',u)
        row=w.economy[w.villages[u['home']]['city']]
        self.assertEqual([e['kind'] for e in row['events']],['depart','intercept','delivered','returned'])
        self.assertEqual(row['trips'],{})

    def test_owner_visibility_and_capture_resets_history(self):
        w=World(1);economy.sample(w)
        self.assertEqual(set(w.observe(0)['economy']),{c['id'] for c in w.cities.values() if c['nation']==0})
        w.cities['c00']['nation']=1;w.hour=24;economy.sample(w)
        self.assertNotIn('c00',w.observe(0)['economy'])
        self.assertEqual(w.economy['c00']['since'],24)
        self.assertEqual(w.economy['c00']['events'],[])

    def test_telemetry_does_not_change_physics_and_replay(self):
        w=World(9,{'bandit_cap':0})
        digest=w.physics_digest();economy.sample(w)
        self.assertEqual(digest,w.physics_digest())
        for _ in range(60):decision_cycle(w,['w2','march']);w.step(6)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'world.json';w.save(path)
            loaded=World.load(path)
            self.assertEqual(w.economy,loaded.economy)
            restored=replay(path)
            self.assertEqual(w.physics_digest(),restored.physics_digest())
            self.assertEqual(w.economy,restored.economy)


class AllocationTests(unittest.TestCase):
    def fixture(self):
        w=World(1,{'bandit_cap':0});c=w.cities['c00']
        for i in range(3):w.new_unit('bandit',-1,-1,80,c['x']+2000+i*100,c['y'])
        donor=w.cities['c01']
        for _ in range(2):w.new_unit('party',0,donor['clan'],100,donor['x'],donor['y'],food=1000000)
        o=w.observe(0);traffic(o)
        return w,o

    def test_small_sample_does_not_trigger_traffic_alarm(self):
        o=World(1).observe(0);traffic(o,count=1,blocked=1)
        self.assertEqual(city_risks(o)['c00']['state'],'normal')
        traffic(o)
        self.assertEqual(city_risks(o)['c00']['state'],'critical')

    def test_recovery_hysteresis_and_insufficient_local_strength(self):
        w,o=self.fixture();r=city_risks(o)['c00'];self.assertTrue(r['needs_help'])
        o['units']=[u for u in o['units'] if u['nation']!=-1]
        o['hour']=1050
        self.assertEqual(city_risks(o)['c00']['state'],'recovering')

    def test_rescue_stages_without_stripping_other_cities(self):
        w,o=self.fixture();before=copy.deepcopy(o);p=allocate(o,'w2')
        moves=[c for c in p['commands'] if c['type']=='move']
        self.assertTrue(moves)
        self.assertFalse(any(c['type']=='attack' for c in p['commands']))
        self.assertTrue(any(w.units[c['unit']]['clan']==1 for c in moves))
        for c in w.cities.values():
            if c['nation']==0 and c['id']!='c00':
                self.assertTrue(any(p['sectors'][uid]==c['id'] and uid not in p['handled'] for uid in p['protected']))
        for c in p['commands']:self.assertTrue(w.command(0,c)['ok'],c)
        city=w.cities['c00']
        for cmd in moves:w.units[cmd['unit']].update(x=city['x'],y=city['y'],path=[])
        o2=w.observe(0);traffic(o2)
        q=allocate(o2,'w2')
        self.assertTrue(any(c['type']=='assemble' for c in q['commands']))
        self.assertTrue(any(c['type']=='attack' for c in q['commands']))
        for c in q['commands']:self.assertTrue(w.command(0,c)['ok'],c)
        self.assertEqual(o,before)

    def test_wounded_and_empty_reserves_do_not_launch_suicide_rescue(self):
        w,o=self.fixture()
        for u in o['units']:
            if u['nation']==0 and u['kind']=='party':u.update(healthy=5,wounded=95)
        p=allocate(o,'w4')
        self.assertFalse(any(c.get('economy_city') for c in p['commands']))

    def test_collapsed_city_with_no_visible_bandits_gets_scouting(self):
        w,o=self.fixture()
        for v in w.villages.values():
            if v['city']=='c00':
                v['population']=0
                if v['cart']:w.remove(v['cart'])
        for uid in list(w.units):
            if w.units[uid]['nation']==-1:w.remove(uid)
        o=w.observe(0)
        risk=city_risks(o)['c00']
        self.assertEqual(risk['state'],'critical')
        self.assertTrue(risk['needs_help'])
        p=allocate(o,'w2')
        self.assertTrue(any(c.get('economy_city')=='c00' for c in p['commands']))
        self.assertFalse(any(c['type']=='attack' for c in p['commands']))
        for cmd in p['commands']:self.assertTrue(w.command(0,cmd)['ok'])
        c=w.cities['c00']
        for u in w.units.values():
            if (u.get('order') or {}).get('economy_city')=='c00':u.update(x=c['x'],y=c['y'],path=[])
        q=allocate(w.observe(0),'w2')
        villages={(v['x'],v['y']) for v in w.villages.values() if v['city']=='c00'}
        self.assertTrue(any(cmd['type']=='move' and (cmd['x'],cmd['y']) in villages for cmd in q['commands']))
        self.assertTrue(any(cmd['type']=='assemble' for cmd in q['commands']))
        for cmd in q['commands']:self.assertTrue(w.command(0,cmd)['ok'],cmd)

    def test_two_crises_never_double_assign_the_same_donor(self):
        w,o=self.fixture();traffic(o,'c02')
        c=w.cities['c02']
        o['units'].append(dict(id='visible-second-threat',kind='bandit',nation=-1,healthy=100,wounded=0,x=c['x']+2000,y=c['y'],battle=None,army=None))
        p=allocate(o,'w4')
        destinations={}
        for cmd in p['commands']:
            if cmd.get('economy_city'):
                self.assertIn(cmd['unit'],p['handled'])
                self.assertEqual(destinations.setdefault(cmd['unit'],cmd['economy_city']),cmd['economy_city'])

    def test_all_candidates_preserve_observations_and_legal_commands(self):
        for style in ('w1','w2','w3','w4'):
            w=World(12,{'bandit_cap':0})
            for _ in range(50):
                o=w.observe(0);before=copy.deepcopy(o)
                commands=decide(o,style)
                self.assertLessEqual(len(commands),100)
                for c in commands:self.assertTrue(w.command(0,c)['ok'],(style,c))
                self.assertEqual(before,o)
                w.step(6);w.check()
