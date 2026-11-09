import copy
import json
import unittest
from types import SimpleNamespace
from aiwar import succession


def world(seed=9):
    w = SimpleNamespace(seed=seed, hour=42,
        nations={str(i):dict(id=i,kingdom=k) for i,k in enumerate(('west','north','south','east'))},
        cities={str(i):dict(nation=i,settlement_type='castle') for i in (2,3)},
        map_clans={str(i):dict(id='clan_'+str(i),nation=i//3,kingdom=('west','north')[i//3],tier=4,party_slots=3) for i in range(6)},
        units={},armies={},army_metadata={},battles={},mobilizations={},map_info={},known={'0':{'secret':1},'2':{}},events=[])
    for i in range(6):
        w.units[str(i)] = dict(id=str(i),clan=i,nation=i//3,kind='party',army=None,battle=None,order={'type':'move'},path=[1],healthy=30,wounded=4,food=500,x=40,y=80,cargo_recruits=3)
    return w


class SuccessionTests(unittest.TestCase):
    def test_simultaneous_extinction_conserves_assets_and_vision(self):
        w=world(); before=copy.deepcopy(w.units);known=copy.deepcopy(w.known)
        events=succession.resolve(w)
        self.assertEqual(w.extinct_nations,[0,1]);self.assertEqual(len(events),6)
        for uid,u in w.units.items():
            self.assertIn(u['nation'],(2,3))
            for field in ('healthy','wounded','food','x','y','cargo_recruits'):
                self.assertEqual(u[field],before[uid][field])
            clan=w.map_clans[str(u['clan'])]
            self.assertEqual(clan['nation'],u['nation']);self.assertEqual(clan['party_slots'],3)
            self.assertEqual(clan['origin_nation'],before[uid]['nation'])
        self.assertEqual(w.known,known)
        self.assertEqual(succession.resolve(w),[])
        self.assertIs(w.map_info['clans'],w.map_clans)

    def test_one_survivor_and_zero_survivor(self):
        w=world();del w.cities['2'];succession.resolve(w)
        self.assertTrue(all(u['nation']==3 for u in w.units.values()))
        w=world();w.cities.clear()
        with self.assertRaisesRegex(ValueError,'no surviving'):succession.resolve(w)
        self.assertEqual(w.extinct_nations,[])

    def test_seeded_and_resume_determinism(self):
        a=world();b=SimpleNamespace(**json.loads(json.dumps(a.__dict__)))
        self.assertEqual(succession.resolve(a),succession.resolve(b))
        restored=SimpleNamespace(**json.loads(json.dumps(a.__dict__)))
        self.assertEqual(succession.resolve(restored),[])
        self.assertEqual(a.clan_migrations,restored.clan_migrations)
        patterns=set()
        for seed in range(30):
            w=world(seed);patterns.add(tuple(e['to_nation'] for e in succession.resolve(w)))
        self.assertGreater(len(patterns),10)

    def test_registry_order_does_not_change_draw(self):
        a=world();b=world();b.nations=dict(reversed(list(b.nations.items())))
        b.map_clans=dict(reversed(list(b.map_clans.items())))
        self.assertEqual(succession.resolve(a),succession.resolve(b))

    def test_army_battle_and_remote_mobilization_cleanup(self):
        w=world();w.armies={'a':['0','3']};w.army_metadata={'a':{'clan':0}}
        w.units['0'].update(army='a',battle='field');w.units['3'].update(army='a')
        w.units['enemy']=dict(id='enemy',nation=2,clan=99,kind='party',battle='siege',army=None)
        w.battles={'field':dict(sides={'0':['0']},relief_for='siege'),
                   'siege':dict(sides={'2':['enemy']},relief_battle='field')}
        w.units['1'].update(kind='levy',phase='joining',mobilization='m')
        w.mobilizations={'m':dict(clan=1,nation=0,army='a',status='active',cohorts={'1':{'source':'original_village'}},last_known_leader={'x':100,'y':200})}
        original=copy.deepcopy(w.mobilizations['m']);succession.resolve(w)
        self.assertEqual(w.armies,{});self.assertEqual(w.army_metadata,{});self.assertEqual(w.battles,{})
        self.assertIsNone(w.units['enemy']['battle'])
        self.assertEqual(w.mobilizations['m']['nation'],w.units['1']['nation'])
        self.assertEqual(w.mobilizations['m']['cohorts'],original['cohorts'])
        self.assertEqual(w.units['1']['phase'],'joining');self.assertEqual(w.units['1']['path'],[1])


if __name__=='__main__':unittest.main()

class EngineSuccessionIntegration(unittest.TestCase):
    def test_save_before_future_extinction_is_identical(self):
        import tempfile
        from pathlib import Path
        from aiwar.engine import World
        w=World(8321,{'mode':'realmap','nations':['empire_w','empire','empire_s'],'bandit_cap':0})
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'before-extinction.json';w.save(path);restored=World.load(path)
        self.assertEqual(w.digest(),restored.digest())
        self.assertIs(restored.map_info['clans'],restored.map_clans)
        self.assertIs(restored.map_info['nation_registry'],restored.nations)
        for state in (w,restored):
            for city in list(state.cities.values()):
                if city['nation']==0:state.capture(city['id'],1,[])
            state.step();state.check()
            self.assertEqual(state.map_info['nation_registry']['0']['extinct_hour'],1)
        self.assertEqual(w.digest(),restored.digest())
        self.assertEqual(w.physics_digest(),restored.physics_digest())
        for nation in w.nation_ids():self.assertEqual(w.observe(nation),restored.observe(nation))
        w.step(24);restored.step(24)
        self.assertEqual(w.digest(),restored.digest())

    def test_end_hour_migration_and_resume(self):
        import tempfile
        from pathlib import Path
        from aiwar.engine import World
        w=World(811,{'mode':'realmap','nations':['empire_w','empire','empire_s'],'bandit_cap':0})
        target_clan=next(int(k) for k,c in w.map_clans.items() if c['nation']==1)
        for c in list(w.cities.values()):
            if c['nation']==0:w.capture(c['id'],1,[target_clan])
        w.step();w.check()
        self.assertEqual(w.extinct_nations,[0])
        self.assertEqual(len(w.clan_migrations),9)
        self.assertTrue(all(c['nation']!=0 for c in w.map_clans.values()))
        self.assertTrue(all(u['nation']!=0 for u in w.units.values()))
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'save.json';w.save(path);b=World.load(path)
            w.step(2);b.step(2)
            self.assertEqual(w.physics_digest(),b.physics_digest())
