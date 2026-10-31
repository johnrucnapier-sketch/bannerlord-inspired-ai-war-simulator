#!/usr/bin/env python3
"""Batch original tools/play.py JSONL matches, with lossless streaming gzip logs.

The frozen host and JsonAgent are executed unchanged. An in-memory Path subclass
only redirects its nation-*.jsonl write streams to .jsonl.gz. It does not alter
requests, replies, command ordering, game logic, timeout or process restarts.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import redirect_stderr, redirect_stdout
import gzip
import json
import multiprocessing
import os
from pathlib import Path
import platform
import runpy
import shutil
import subprocess
import sys
import time
import traceback

sys.dont_write_bytecode = True
from run_dev import parse_seeds, score, sha, summarize, write_json


class StreamingLogPath(type(Path())):
    def open(self, mode='r', buffering=-1, encoding=None, errors=None, newline=None):
        if mode == 'w' and self.name in ('nation-0.jsonl', 'nation-1.jsonl'):
            return gzip.open(str(self) + '.gz', 'wt', encoding=encoding or 'utf-8',
                             errors=errors, newline=newline, compresslevel=1)
        return super().open(mode, buffering, encoding, errors, newline)


def run_job(job):
    started = time.monotonic()
    destination = Path(job['destination'])
    row = {k: job[k] for k in ('job_id', 'seed', 'side', 'days')}
    row.update(status='failed', agent_errors=[0, 0], command_rejections=[0, 0],
               slow_decisions=[0, 0], timeouts=[0, 0], stderr_tracebacks=[0, 0],
               stderr_policy_exceptions=[0, 0], faults=[], source_sha256=job['source_sha256'])
    try:
        for key in tuple(os.environ):
            if key.startswith('GB_'):
                del os.environ[key]
        os.environ['PYTHONUTF8'] = '1'
        os.environ['PYTHONHASHSEED'] = '0'
        os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
        for name in ('agent', 'opponent'):
            spec = job[name]
            if sha(spec['path']) != spec['sha256']:
                raise RuntimeError(name + ' source changed after registration')
        root = Path(job['root'])
        sys.path.insert(0, str(root/'game'))
        import aiwar.match as match
        original_path = match.Path
        match.Path = StreamingLogPath
        own = 0 if job['side'] == 'blue' else 1
        agents = [None, None]
        agents[own], agents[1-own] = job['agent']['argv'], job['opponent']['argv']
        argv = [str(root/'tools/play.py'), '--seed', str(job['seed']), '--days', str(job['days']),
                '--timeout', str(job['timeout']), '--output', str(destination),
                '--blue-command', json.dumps(agents[0]), '--red-command', json.dumps(agents[1])]
        old_argv = sys.argv
        sys.argv = argv
        try:
            with Path(job['runner_log']).open('w') as log, redirect_stdout(log), redirect_stderr(log):
                runpy.run_path(str(root/'tools/play.py'), run_name='__main__')
        finally:
            sys.argv = old_argv
            match.Path = original_path
        report = json.loads((destination/'result.json').read_text())
        manifest = json.loads((destination/'match.json').read_text())
        challenge = json.loads((destination/'challenge.json').read_text())
        expected_core = {Path(p).name: h for p, h in job['source_sha256'].items() if p.startswith('game/aiwar/')}
        assert manifest['source_sha256'] == expected_core, 'Core source hashes drifted'
        assert manifest['timeout_seconds'] == job['timeout']
        assert challenge['baseline_manifest_sha256'] == job['source_sha256']['freeze/v0.2.0.json']
        assert manifest['status'] == 'completed'
        row.update(status='completed', result=report['result'], physics_digest=report['physics_digest'],
                   config_sha256=report['config_sha256'], totals=report['totals'], captures=report['captures'],
                   agent_errors=manifest['agent_errors'], score_agent=score(report, own),
                   score_opponent=score(report, 1-own), development_run=challenge['development_run'],
                   win=None if report['result']['winner'] is None else report['result']['winner'] == own,
                   agents=agents)
    except BaseException as exc:
        row['fatal_error'] = repr(exc)
        destination.mkdir(parents=True, exist_ok=True)
        (destination/'fatal-error.log').write_text(traceback.format_exc())
    # Audit any available logs even when the host failed partway through a game.
    for n in (0, 1):
        stderr = destination/f'agent-{n}.stderr.log'
        if stderr.exists():
            content = stderr.read_text(errors='replace')
            row['stderr_tracebacks'][n] = content.count('Traceback (most recent call last):')
            row['stderr_policy_exceptions'][n] = content.count('policy exception:')
        trace = destination/f'nation-{n}.jsonl.gz'
        if trace.exists():
            try:
                with gzip.open(trace, 'rt', encoding='utf-8') as logs:
                    for line in logs:
                        record = json.loads(line)
                        error = record.get('agent_error')
                        if error:
                            row['faults'].append({'nation': n, 'request_id': record['request']['request_id'], 'error': error})
                            row['timeouts'][n] += 'timeout' in error
                        row['command_rejections'][n] += sum(not out.get('ok', True) for out in record.get('outcomes', []))
            except Exception as exc:
                row.setdefault('log_audit_errors', []).append({'nation': n, 'error': repr(exc)})
                row['status'] = 'failed'
    row['elapsed_seconds'] = time.monotonic()-started
    row['raw_log_sha256'] = {p.name: sha(p) for p in sorted(destination.iterdir())
                             if p.is_file() and p.name != 'summary.json'}
    write_json(destination/'summary.json', row)
    return row


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True)
    p.add_argument('--agent', required=True)
    p.add_argument('--opponent', default='march')
    p.add_argument('--seeds', nargs='+', required=True)
    p.add_argument('--sides', nargs='+', default=['blue', 'red'])
    p.add_argument('--days', type=int, default=1680)
    p.add_argument('--workers', type=int, default=1)
    p.add_argument('--timeout', type=float, default=2.)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    if min(a.days, a.workers) <= 0 or a.timeout <= 0:
        p.error('days, workers and timeout must be positive')
    root, output = Path(a.root).resolve(), Path(a.output).resolve()
    sides = [s for item in a.sides for s in item.split(',')]
    if sides == ['both']:
        sides = ['blue', 'red']
    if not sides or len(set(sides)) != len(sides) or any(s not in ('blue', 'red') for s in sides):
        p.error('--sides must select blue and/or red once each')
    seeds = parse_seeds(a.seeds)
    for prefix in ('game', 'freeze', 'benchmarks/data', 'benchmarks/reports', 'strategies/reference'):
        if output.is_relative_to(root/prefix):
            p.error('Output must be outside frozen directories')
    verified = subprocess.run([sys.executable, str(root/'tools/verify_release.py'), '--root', str(root)],
                              capture_output=True, text=True)
    if verified.returncode:
        raise RuntimeError('Frozen release verification failed: '+verified.stdout+verified.stderr)
    output.mkdir(parents=True, exist_ok=False)
    (output/'verify-release.log').write_text(verified.stdout+verified.stderr)
    specs = {}
    for name, source in (('agent', a.agent), ('opponent', a.opponent)):
        path = root/'strategies/agent.py' if source == 'march' else Path(source).resolve()
        specs[name] = {'path': str(path), 'sha256': sha(path),
                       'argv': [sys.executable, '-S', str(path)] + (['--policy', 'march'] if source == 'march' else [])}
        shutil.copyfile(path, output/f'{name}.source.py')
    source_hashes = {str(f.relative_to(root)): sha(f) for f in sorted((root/'game/aiwar').glob('*.py'))}
    source_hashes.update({path: sha(root/path) for path in ('freeze/v0.2.0.json', 'tools/play.py')})
    source_hashes.update({name: spec['sha256'] for name, spec in specs.items()})
    for script in (Path(__file__), Path(__file__).with_name('run_dev.py')):
        source_hashes[script.name] = sha(script)
        shutil.copyfile(script, output/(script.stem+'.source.py'))
    jobs = [{'job_id': f'i{i:03d}-{side}-s{seed}', 'seed': seed, 'side': side, 'days': a.days,
             'root': str(root), 'destination': str(output/f'i{i:03d}-{side}-s{seed}'),
             'runner_log': str(output/f'i{i:03d}-{side}-s{seed}.runner.log'),
             'agent': specs['agent'], 'opponent': specs['opponent'], 'timeout': a.timeout,
             'source_sha256': source_hashes}
            for i, seed in enumerate(seeds) for side in sides]
    manifest = {'baseline': 'v0.2.0', 'created_unix': time.time(), 'root': str(root),
                'seeds': seeds, 'sides': sides, 'days': a.days, 'timeout_seconds': a.timeout,
                'workers': a.workers, 'python': sys.version, 'platform': platform.platform(),
                'agents': specs, 'source_sha256': source_hashes,
                'development_run': a.days != 1680,
                'planned_jobs': [{k: j[k] for k in ('job_id', 'seed', 'side')} for j in jobs],
                'host': 'original tools/play.py and aiwar.match, JSONL subprocesses',
                'io_adapter': 'Only nation-*.jsonl writes become lossless streaming gzip; raw record content preserved.',
                'gb_environment_override_keys_removed': sorted(k for k in os.environ if k.startswith('GB_'))}
    write_json(output/'experiment.json', manifest)
    started, rows = time.monotonic(), []
    with ProcessPoolExecutor(max_workers=a.workers, mp_context=multiprocessing.get_context('spawn')) as pool:
        futures = {pool.submit(run_job, job): job for job in jobs}
        for future in as_completed(futures):
            job = futures[future]
            try:
                row = future.result()
            except BaseException as exc:
                row = {k: job[k] for k in ('job_id', 'seed', 'side', 'days')}
                row.update(status='failed', fatal_error=repr(exc), agent_errors=[0, 0],
                           command_rejections=[0, 0], slow_decisions=[0, 0])
                dest = Path(job['destination'])
                dest.mkdir(exist_ok=True)
                write_json(dest/'summary.json', row)
            rows.append(row)
            rows.sort(key=lambda r: r['job_id'])
            write_json(output/'results.json', {'summary': summarize(rows), 'rows': rows,
                                              'completed_jobs': len(rows), 'planned_jobs': len(jobs),
                                              'elapsed_seconds': time.monotonic()-started})
            print(json.dumps({k: row.get(k) for k in ('job_id', 'status', 'win', 'result', 'elapsed_seconds',
                                                     'agent_errors', 'timeouts', 'stderr_tracebacks',
                                                     'stderr_policy_exceptions', 'command_rejections')}, ensure_ascii=False), flush=True)
    changed = [name for name, digest in source_hashes.items()
               if name.startswith(('game/', 'freeze/', 'tools/')) and sha(root/name) != digest]
    changed.extend(name for name, spec in specs.items() if sha(spec['path']) != spec['sha256'])
    summary = summarize(rows)
    summary.update(timeouts=sum(sum(r.get('timeouts', [])) for r in rows),
                   internal_exception_events=sum(sum(r.get('stderr_tracebacks', [])) +
                                                 sum(r.get('stderr_policy_exceptions', [])) for r in rows))
    final = {'summary': summary, 'rows': rows, 'planned_jobs': len(jobs), 'completed_jobs': len(rows),
             'source_files_changed_during_run': changed, 'elapsed_seconds': time.monotonic()-started}
    write_json(output/'results.json', final)
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 1 if summary['failed'] or changed else 0


if __name__ == '__main__':
    raise SystemExit(main())
