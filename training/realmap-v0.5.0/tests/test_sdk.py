import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from aiwar.sdk import Environment
from aiwar.match import JsonAgent, run_match
from aiwar.replay import replay


class SDKTests(unittest.TestCase):
    def test_snapshot_and_rejection(self):
        env = Environment(1, {'days': 1})
        obs = env.observations()
        self.assertEqual([o['hour'] for o in obs], [0, 0])
        enemy = next(u for u in obs[0]['units'] if u['nation'] == 0)
        own_id = enemy['id']
        result = env.step([[{'type': 'attack', 'unit': own_id, 'target': []}], []])
        self.assertFalse(result['outcomes'][0][0]['ok'])
        self.assertEqual(env.world.hour, 6)
        self.assertEqual(env.last_transition['observations'], obs)
        for nation, view in enumerate(result['observations']):
            self.assertEqual(view['events'], [])
            for unit in view['units']:
                if unit['nation'] != nation:
                    self.assertNotIn('food', unit)
                    self.assertNotIn('order', unit)

    def test_invalid_envelope_is_atomic(self):
        env = Environment()
        before = env.world.physics_digest()
        with self.assertRaises(ValueError): env.step([[], {}])
        self.assertEqual(env.world.physics_digest(), before)

    def test_action_and_reset(self):
        env = Environment(1, {'days': 1})
        result = env.step([[{'type': 'create', 'city': 'c00', 'count': 10, 'source': 'garrison'}], []])
        self.assertTrue(result['outcomes'][0][0]['ok'])
        self.assertEqual(env.world.units['g00']['healthy'], 30)  # Ten more soldiers auto-refill the resident party.
        env.reset(2)
        self.assertEqual(env.world.hour, 0)
        self.assertEqual(env.world.units['g00']['healthy'], 50)

    def test_dataset_and_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'match'
            argv = [sys.executable, '-m', 'aiwar.agent_example']
            report = run_match([argv, argv], out, days=1)
            self.assertEqual(report['hour'], 24)
            self.assertEqual(replay(out / 'final.save.json').physics_digest(), report['physics_digest'])
            rows = [json.loads(s) for s in (out / 'nation-0.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len(rows), 5)
            self.assertEqual(rows[-1]['type'], 'terminal')
            self.assertEqual(rows[1]['request']['request_id'], '0:6')
            self.assertEqual(json.loads((out / 'match.json').read_text(encoding='utf-8'))['agent_errors'], [0, 0])
            with self.assertRaises(FileExistsError): run_match([argv, argv], out, days=1)

    def test_timeout_and_malformed(self):
        with tempfile.TemporaryFile() as err:
            for code in ('import time; time.sleep(5)', 'print("bad", flush=True)'):
                agent = JsonAgent([sys.executable, '-c', code], err, timeout=.2)
                commands, error = agent.decide({'request_id': '0:0'})
                self.assertEqual(commands, [])
                self.assertIsNotNone(error)
                self.assertIsNone(agent.process)
                agent.close()

    def test_terminal_and_rewards(self):
        env = Environment(1, {'days': 1})
        for _ in range(4): result = env.step([[], []])
        self.assertTrue(result['terminated'])
        self.assertEqual(result['rewards'], [0, 0])
        with self.assertRaises(ValueError): env.step([[], []])
