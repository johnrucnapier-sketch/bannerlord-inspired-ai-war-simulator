#!/usr/bin/env python3
"""Focused identity, dependency and invocation tests; no games/network by default."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
import run_match

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


class SubmissionTests(unittest.TestCase):
    def test_frozen_identity(self):
        run_match.verify_identity()

    def test_dependency_closure_present(self):
        dependencies = json.loads((HERE / 'DEPENDENCIES.json').read_text())
        self.assertEqual(dependencies['nonstdlib_import_roots'], [])
        for relative in dependencies['local_python_files']:
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_policy_import_and_default(self):
        # Import the exact selected policy without altering its module globals.
        spec = importlib.util.spec_from_file_location('campaign600_v1_tested', HERE / 'policy.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        self.assertEqual(module.Config().attack_minimum, 600)
        self.assertIsNotNone(module.Controller())

    def test_swapped_colors(self):
        for side, opposite in [('blue', 'red'), ('red', 'blue')]:
            args = run_match.parse_args(['--side', side, '--opponent', 'd2', '--output', 'runs/unit-unused'])
            command = run_match.build_command(args)
            self.assertIn('--' + side + '-command', command)
            self.assertIn('--' + opposite, command)
            self.assertEqual(command[command.index('--' + opposite) + 1], 'd2')
            self.assertEqual(args.days, 1680)

    def test_custom_opponent_argv(self):
        custom = json.dumps([sys.executable, 'agent with spaces.py', '--flag'])
        args = run_match.parse_args(['--side', 'red', '--opponent-command', custom, '--output', 'runs/unit-unused'])
        command = run_match.build_command(args)
        self.assertEqual(json.loads(command[command.index('--blue-command') + 1]), json.loads(custom))

    def test_no_input_clean_exit(self):
        completed = subprocess.run([sys.executable, '-S', str(HERE / 'policy.py')], input='', text=True,
                                   capture_output=True, cwd=ROOT, timeout=10)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout, '')


if __name__ == '__main__':
    unittest.main()
