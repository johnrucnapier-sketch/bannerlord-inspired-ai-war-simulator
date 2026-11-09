"""No world advancement: compare all eight initial private decisions exactly."""
import json
from pathlib import Path
import subprocess
import sys
import unittest


class DecisionEquivalenceV071(unittest.TestCase):
    def test_initial_private_commands_match_original_for_all_eight_nations(self):
        package = Path(__file__).resolve().parents[1]
        repository = package.parents[1]
        source = repository / 'strategies/submissions/dev19_multinational_v070'
        outputs = []
        for version in ('realmap-v0.7.0', 'realmap-v0.7.1', package.name):
            program = (
                'import sys,json;'
                f'sys.path.insert(0,{str(package.parent / version)!r});import aiwar;'
                f'sys.path.insert(0,{str(source)!r});'
                'from aiwar.server import Session;from agent import decide;'
                's=Session(1);'
                'print(json.dumps([decide(s.world.observe(n)) for n in s.world.nation_ids()],sort_keys=True));'
                's.strategy_runtime.close()'
            )
            # Subprocess bound is for the comparison tool, not an agent deadline.
            result = subprocess.run([sys.executable, '-I', '-c', program], check=True,
                                    capture_output=True, text=True, encoding='utf-8', timeout=60)
            outputs.append(json.loads(result.stdout))
        self.assertEqual(len(outputs[0]), 8)
        for output in outputs[1:]:self.assertEqual(output, outputs[0])


if __name__ == '__main__':
    unittest.main()
