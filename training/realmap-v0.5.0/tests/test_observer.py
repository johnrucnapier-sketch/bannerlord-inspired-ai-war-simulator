import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tests.legacy_world import LegacyWorld as World
from aiwar.server import Session
from aiwar.replay import replay

class Observer(unittest.TestCase):
    def test_initial_totals(self):
        w=World(1)
        for t in w.observer_totals():
            self.assertEqual(t['population'],3600)
            self.assertEqual(t['village_population'],3240)
            self.assertEqual(t['transport_population'],360)
            self.assertEqual(t['military'],1080)
            self.assertEqual(t['militia'],600)
            self.assertEqual(t['garrison'],300)
            self.assertEqual(t['field'],180)
            self.assertEqual(t['wounded'],0)

    def test_convoy_and_army_do_not_double_count(self):
        w=World(1);before=w.observer_totals()[0]['military']
        result=w.command(0,{'type':'dispatch','city':'c00','destination':'c01'})
        self.assertTrue(result['ok'])
        t=w.observer_totals()[0]
        self.assertEqual(t['military'],before);self.assertEqual(t['logistics'],20)
        a=next(u for u in w.units.values() if u['kind']=='party' and u['clan']==0)
        w.cities['c00']['recruits']=30
        made=w.command(0,{'type':'create','city':'c00','count':30})
        b=w.units[made['unit']];a['healthy']-=7;a['wounded']+=7
        assembled=w.command(0,{'type':'assemble','unit':a['id'],'units':[b['id']]})
        self.assertTrue(assembled['ok'])
        t=w.observer_totals()[0]
        self.assertEqual(t['military'],before+30)
        self.assertEqual(t['wounded'],7)
        self.assertEqual(t['healthy'],t['military']-7)
        self.assertEqual(t['armies'],1)

    def test_population_tracks_actual_transport_deaths_not_recruiting(self):
        w=World(1);v=w.villages['v000']
        w.remove(v['cart'],'defeated')
        self.assertEqual(w.observer_totals()[0]['population'],3580)
        w.hour=24;w.daily()
        self.assertEqual(w.observer_totals()[0]['population'],3598)
        w.cities['c00']['recruits']=10
        self.assertTrue(w.command(0,{'type':'recruit','city':'c00','count':10})['ok'])
        self.assertEqual(w.observer_totals()[0]['population'],3598)

    def test_named_events_and_noise_filter(self):
        w=World(1)
        u=next(u for u in w.units.values() if u['kind']=='party' and u['clan']==0)
        w.cities['c00']['recruits']=30
        r=w.command(0,{'type':'create','city':'c00','count':30})
        group=w.command(0,{'type':'assemble','unit':u['id'],'units':[r['unit']]})
        event=next(e for e in w.observer_events() if e['kind']=='army_assembled')
        self.assertIn('蓝1城',event['text']);self.assertIn(group['army'],event['text'])
        self.assertIn('2支部队',event['text'])
        w.remove(u['id'],'defeated')
        event=next(e for e in w.observer_events() if e['kind']=='unit_destroyed')
        self.assertIn(u['id'],event['text']);self.assertIn('家族1',event['text'])
        for _ in range(3000):w.emit('bandit_spawn','乡野出现劫匪')
        self.assertFalse(any(e['kind']=='bandit_spawn' for e in w.observer_events()))
        self.assertTrue(any(e['kind']=='unit_destroyed' for e in w.observer_events()))

    def test_observer_totals_do_not_leak_to_policies(self):
        s=Session(1)
        self.assertEqual(len(s.snapshot(0)['observer_totals']),2)
        observation=s.world.observe(0)
        self.assertNotIn('observer_totals',observation)
        self.assertNotIn('observer_events',observation)
        self.assertEqual(observation['events'],[])

    def test_random_reset_and_explicit_replay_seed(self):
        with tempfile.TemporaryDirectory() as temp,patch('aiwar.server.ROOT',Path(temp)):
            s=Session(1);old=s.run_id
            with patch('aiwar.server.secrets.randbelow',side_effect=[0,1]):s.reset()
            self.assertEqual(s.world.seed,2);self.assertNotEqual(old,s.run_id)
            self.assertTrue(s.paused)
            s.reset(7);digest=s.world.physics_digest()
            s.reset(7);self.assertEqual(s.world.physics_digest(),digest)
            records=[json.loads(x) for x in (Path(temp)/'artifacts/run-history.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual([x['seed'] for x in records],[1,2,7])

    @unittest.skipUnless((Path(__file__).parent/'fixtures/legacy-v011.save.json').exists(), 'Private legacy save is not distributed; checked in the local full suite')
    def test_legacy_save_can_load_and_replay_unchanged_rules(self):
        path=Path(__file__).parent/'fixtures/legacy-v011.save.json'
        raw=json.loads(path.read_text(encoding='utf-8'))
        self.assertNotIn('event_seq',raw)
        loaded=World.load(path)
        self.assertGreater(loaded.event_seq,0)
        replayed=replay(path)
        self.assertEqual(replayed.physics_digest(),loaded.physics_digest())
        before=loaded.physics_digest();loaded.emit('ui_note','只改变观察日志')
        self.assertEqual(loaded.physics_digest(),before)

    def test_adding_army_logs_does_not_advance_unit_ids(self):
        w=World();seq=w.seq
        w.emit('army_assembled','展示事件',important=True)
        self.assertEqual(w.seq,seq)

if __name__=='__main__':unittest.main()
