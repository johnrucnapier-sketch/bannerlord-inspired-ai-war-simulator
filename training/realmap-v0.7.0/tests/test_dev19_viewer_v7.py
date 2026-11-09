import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aiwar import strategy_catalog as catalog_module
from aiwar.match import JsonAgent
from aiwar.server import Session
from aiwar.strategy_catalog import ADAPTED_SOURCE, DEV19_SOURCE_SHA256, catalog, verify_source


SOURCE_PRESENT = all((ADAPTED_SOURCE/name).is_file() for name in DEV19_SOURCE_SHA256)


class Dev19ViewerV7(unittest.TestCase):
    def test_missing_companion_omits_only_adapted_entry(self):
        duel_before = catalog('duel')
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            with patch.object(catalog_module, 'ADAPTED_SOURCE', source):
                self.assertNotIn('dev19_v070', [r['id'] for r in catalog('realmap')])
                (source/'agent.py').write_text('# incomplete companion\n')
                self.assertNotIn('dev19_v070', [r['id'] for r in catalog('realmap')])
                self.assertEqual(catalog('duel'), duel_before)
                self.assertEqual(catalog('realmap')[0]['id'], 'vanilla_v1')
                with self.assertRaisesRegex(ValueError, '源码'):
                    verify_source('dev19_v070')

    @unittest.skipUnless(SOURCE_PRESENT, 'optional Dev19 adaptation is not bundled')
    def test_pinned_two_file_verification_rejects_each_mutation(self):
        self.assertEqual(len(verify_source('dev19_v070')), 64)
        self.assertEqual(set(DEV19_SOURCE_SHA256), {'agent.py', 'dev19_base.py'})
        for name, expected in DEV19_SOURCE_SHA256.items():
            self.assertEqual(hashlib.sha256((ADAPTED_SOURCE/name).read_bytes()).hexdigest(), expected)
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                source = Path(tmp)
                for original in DEV19_SOURCE_SHA256:
                    shutil.copyfile(ADAPTED_SOURCE/original, source/original)
                with (source/name).open('a') as changed:
                    changed.write('\n# mutation must not execute\n')
                with patch.object(catalog_module, 'ADAPTED_SOURCE', source):
                    with self.assertRaisesRegex(ValueError, '源码校验失败'):
                        verify_source('dev19_v070')
                    session = Session(1)
                    try:
                        session.set_style(0, 'dev19_v070')
                        with patch.object(JsonAgent, 'decide') as execute:
                            with self.assertRaisesRegex(ValueError, '源码校验失败'):
                                session.strategy_runtime.cycle(session.world, session.styles, 'tampered-test')
                            execute.assert_not_called()
                    finally:
                        session.strategy_runtime.close()

    @unittest.skipUnless(SOURCE_PRESENT, 'optional Dev19 adaptation is not bundled')
    def test_all_eight_select_private_independent_jsonl_agents(self):
        session = Session(1)
        runtime = session.strategy_runtime
        real_decide = JsonAgent.decide
        seen = {}
        private = {n: session.world.observe(n) for n in session.world.nation_ids()}

        def record(agent, request):
            observation = request['observation']
            n = observation['nation']
            self.assertEqual(observation, private[n])
            self.assertNotIn('observer_totals', observation)
            self.assertNotIn('observer_events', observation)
            self.assertEqual(observation['events'], [])
            seen[n] = request
            return real_decide(agent, request)

        try:
            entry = next(r for r in catalog('realmap') if r['id'] == 'dev19_v070')
            self.assertEqual(entry['label'], 'Dev19 家族军团适配版')
            self.assertTrue(entry['external'])
            self.assertNotIn('dev19_v070', [r['id'] for r in catalog('duel')])
            self.assertNotIn('dev19_v070', [r['id'] for r in catalog('rural')])
            for n in session.world.nation_ids():
                session.set_style(n, 'dev19_v070')
            with patch.object(JsonAgent, 'decide', record):
                outcomes = runtime.cycle(session.world, session.styles, session.run_id)
            self.assertEqual(set(seen), set(range(8)))
            self.assertEqual(len({a.process.pid for a in runtime.agents.values()}), 8)
            self.assertEqual(set(runtime.previous), set(range(8)))
            self.assertTrue(all(runtime.previous[n] for n in range(8)))
            self.assertTrue(outcomes)
            self.assertTrue(all(r['ok'] for r in outcomes), outcomes)
            self.assertTrue(all(a.process.poll() is None for a in runtime.agents.values()))
            for agent in runtime.agents.values():
                self.assertIn('dev19_multinational_v070', agent.argv[-1])
                self.assertNotIn('viewer_strategy_agent.py', agent.argv[-1])
            for log in runtime.logs.values():
                log.flush()
                self.assertEqual(Path(log.name).read_bytes(), b'')
            session.world.check()
        finally:
            runtime.close()


if __name__ == '__main__':
    unittest.main()
