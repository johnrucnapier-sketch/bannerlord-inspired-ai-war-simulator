#!/usr/bin/env python3
"""Run Campaign600 v1 through the unchanged official JSONL host (stdlib only)."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
POLICY_SHA256 = '1aed9815302f846238d4756c378b7161ba2170869008205a20662b1a96ba6c44'
FREEZE_SHA256 = 'a6d56cb4875804770bf82fa176d08cfc30f5af892763fc10f92e3c826e8274a5'


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_identity():
    for path, expected in ((HERE / 'policy.py', POLICY_SHA256),
                           (ROOT / 'freeze/v0.2.0.json', FREEZE_SHA256)):
        if sha256(path) != expected:
            raise ValueError(f'Identity mismatch: {path.name}; do not label changed code as Campaign600 v1')
    manifest = json.loads((ROOT / 'freeze/v0.2.0.json').read_text())
    # Full baseline integrity is checked by tools/verify_release.py in a checkout.
    # In a portable subset, verify every included frozen file against its record.
    records = manifest['files']
    if isinstance(records, list):
        records = {entry['path']: entry for entry in records}
    for relative, entry in records.items():
        path = ROOT / relative
        if path.is_file():
            expected = entry if isinstance(entry, str) else entry['sha256']
            if sha256(path) != expected:
                raise ValueError(f'Frozen dependency mismatch: {relative}')


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--side', choices=['blue', 'red'], default='blue')
    opponent = parser.add_mutually_exclusive_group()
    opponent.add_argument('--opponent', choices=['march', 'p3', 'p5', 'd2', 'idle'], default='march')
    opponent.add_argument('--opponent-command', help='JSON argv array; executed without a shell from repository root')
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--days', type=int, default=1680)
    parser.add_argument('--timeout', type=float, default=2.0)
    parser.add_argument('--output', required=True, help='new directory; existing outputs are never overwritten')
    args = parser.parse_args(argv)
    if args.days <= 0 or not (0 < args.timeout < float('inf')):
        parser.error('days and timeout must be positive and timeout finite')
    if args.opponent_command:
        try:
            custom = json.loads(args.opponent_command)
        except (ValueError, TypeError):
            parser.error('--opponent-command must be a JSON argv array')
        if not isinstance(custom, list) or not custom or not all(isinstance(x, str) and x for x in custom):
            parser.error('--opponent-command needs a nonempty array of nonempty strings')
    return args


def build_command(args):
    other = 'red' if args.side == 'blue' else 'blue'
    command = [sys.executable, '-S', str(ROOT / 'tools/play.py'),
               '--' + args.side + '-command', json.dumps([sys.executable, '-S', str(HERE / 'policy.py')]),
               '--seed', str(args.seed), '--days', str(args.days), '--timeout', str(args.timeout),
               '--output', str(Path(args.output).expanduser().resolve())]
    command += ['--' + other + '-command', args.opponent_command] if args.opponent_command else ['--' + other, args.opponent]
    return command


def main():
    args = parse_args()
    output = Path(args.output).expanduser().resolve()
    if output.exists():
        raise SystemExit('Output already exists; use a new directory.')
    verify_identity()
    subprocess.run(build_command(args), cwd=ROOT, check=True)
    # Do not record absolute executable paths or custom argv in this public-friendly summary.
    record = dict(name='Campaign600 v1', version='1.0.0', author='GPT dot', baseline='v0.2.0',
                  policy_sha256=POLICY_SHA256, freeze_manifest_sha256=FREEZE_SHA256,
                  seed=args.seed, side=args.side, days=args.days, decision_hours=6,
                  timeout_seconds=args.timeout,
                  opponent='custom JSONL agent' if args.opponent_command else args.opponent,
                  official_host='tools/play.py')
    (output / 'campaign600-run.json').write_text(json.dumps(record, indent=2) + '\n')


if __name__ == '__main__':
    main()
