import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
from aiwar.engine import World
from aiwar.replay import replay
from aiwar.server import Session
from aiwar.sdk import Environment

class PlanATests(unittest.TestCase):
    def test_defaults_and_sdk(self):
        w=World(1,{'mode':'realmap'})
        self.assertEqual((w.cfg['days'],w.cfg['decision_hours']),(840,3))
        self.assertEqual(w.cfg['speeds'],dict(party=1000,army=500,village_cart=500,city_cart=500,bandit=750,militia=0))
        self.assertEqual(Environment(1,{'mode':'realmap'}).world.cfg['days'],840)
        self.assertEqual(World(1,{'mode':'realmap','days':7}).cfg['days'],7)
        self.assertEqual(World(1).cfg['days'],1680)
        self.assertEqual(World(1,{'mode':'rural'}).cfg['decision_hours'],6)

    def test_decisions_at_three_hour_boundaries(self):
        s=Session(4)
        with patch.object(s,'record_run'):
            s.reset(4,'realmap')
        seen=[]
        with patch('aiwar.server.decision_cycle',side_effect=lambda w,styles:seen.append(w.hour)):
            for _ in range(10):s.advance()
        self.assertEqual(seen,[0,3,6,9])
        self.assertFalse(s.faulted)
        self.assertEqual(s.snapshot(None)['run_settings']['days'],840)
        s.strategy_runtime.close()

    def test_ten_year_limit_and_29_city_unification(self):
        w=World(1,{'mode':'realmap'})
        w.hour=20159;w.finish();self.assertIsNone(w.result)
        w.hour=20160;w.finish();self.assertEqual(w.result['reason'],'time_limit')
        w=World(1,{'mode':'realmap'})
        for i,c in enumerate(w.cities.values()):c['nation']=0 if i<12 else 1
        w.finish();self.assertIsNone(w.result)
        for c in w.cities.values():c['nation']=0
        w.finish();self.assertEqual(w.result['reason'],'unification')

    def test_legacy_profile_and_new_replay(self):
        for legacy in [True,False]:
            w=World(13,{'mode':'realmap'})
            if legacy:
                cfg=dict(w.cfg,days=1680,decision_hours=6,local_baseline='v0.3.0-local-realmap')
                cfg.pop('realmap_profile');cfg.pop('unification_city_count')
                cfg.pop('castle_logistics',None);cfg.pop('supply_max_distance',None)
                cfg.update(city_crew=20,city_cargo=940000,city_reserve=60000)
                cfg['speeds']=dict(party=500,army=250,village_cart=250,city_cart=250,bandit=375,militia=0)
                w=World(13,cfg)
            w.step(24)
            with tempfile.TemporaryDirectory() as temp:
                p=Path(temp)/'save.json';w.save(p)
                loaded=World.load(p);restored=replay(p)
                self.assertEqual(loaded.cfg,w.cfg)
                self.assertEqual(restored.physics_digest(),w.physics_digest())
                self.assertEqual(loaded.cfg['days'],1680 if legacy else 840)

if __name__=='__main__':unittest.main()
