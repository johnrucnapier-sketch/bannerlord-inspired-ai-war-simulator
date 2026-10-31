#!/usr/bin/env python3
"""Observation-only, in-process DEVELOPMENT evaluator for frozen AI War v0.2.0.

This is a trusted-code development tool, not a security sandbox or a JSONL
leaderboard result. Final candidates must also be run through tools/play.py.
Every planned job is retained, including exceptions and rejected commands.
"""
from __future__ import annotations

import argparse
import ast
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import redirect_stderr, redirect_stdout
import gzip
import hashlib
import importlib.util
import inspect
import json
import multiprocessing
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import time
import traceback

sys.dont_write_bytecode = True


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def wire_copy(value):
    """Match JSONL's data types and ensure no host-owned reference escapes."""
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


def audit_agent(path, requested='auto'):
    if path == 'march':
        return {'path': 'march', 'api': 'builtin_march', 'truncate': False}
    path = Path(path).resolve()
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    classes = [n.name for n in tree.body if isinstance(n, ast.ClassDef)
               and any(isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name == 'decide'
                       for m in n.body)]
    functions = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
    if requested == 'auto':
        preferred = [n for n in ('Policy', 'Brain', 'Agent') if n in classes]
        if preferred:
            api = preferred[0]
        elif 'decide' in functions:
            api = 'decide'
        elif len(classes) == 1:
            api = classes[0]
        else:
            raise ValueError(f'Cannot identify observation API in {path}; use --agent-api/--opponent-api')
    else:
        api = requested
    if api != 'decide' and api not in classes:
        raise ValueError(f'{path}: class {api} has no directly defined decide method')
    if api == 'decide' and 'decide' not in functions:
        raise ValueError(f'{path}: no module-level decide')
    # Grok v20-v24's actual JSONL wrappers call b.decide(obs)[:100]. Preserve
    # that behavior rather than penalizing a method that the wrapper truncates.
    main_nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main']
    truncate = any(isinstance(n, ast.Subscript) and isinstance(n.value, ast.Call)
                   and isinstance(n.value.func, ast.Attribute) and n.value.func.attr == 'decide'
                   and isinstance(n.slice, ast.Slice) and n.slice.lower is None
                   and isinstance(n.slice.upper, ast.Constant) and n.slice.upper.value == 100
                   and n.slice.step is None
                   for main in main_nodes for n in ast.walk(main))
    imports = [ast.unparse(n) for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    owner = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == api), None)
    definition = next(n for n in (owner.body if owner else tree.body)
                      if isinstance(n, ast.FunctionDef) and n.name == 'decide')
    parameter_names = [n.arg for n in definition.args.args + definition.args.kwonlyargs]
    outcomes_argument = next((n for n in ('outcomes', 'previous_outcomes') if n in parameter_names), None)
    return {'path': str(path), 'sha256': sha(path), 'api': api, 'truncate': truncate,
            'outcomes_argument': outcomes_argument, 'imports': imports,
            'security_boundary': 'trusted code; AST API audit is not a security review'}


class Adapter:
    def __init__(self, spec, unique):
        self.spec = spec
        if spec['api'] == 'builtin_march':
            from aiwar.policies import decide
            self.function = decide
        else:
            if sha(spec['path']) != spec['sha256']:
                raise RuntimeError('Agent source changed after experiment registration')
            module_spec = importlib.util.spec_from_file_location('dev_agent_' + unique, spec['path'])
            module = importlib.util.module_from_spec(module_spec)
            sys.modules[module_spec.name] = module
            module_spec.loader.exec_module(module)
            self.function = (getattr(module, spec['api'])().decide
                             if spec['api'] != 'decide' else module.decide)
        parameters = inspect.signature(self.function).parameters
        self.outcomes_key = next((k for k in ('outcomes', 'previous_outcomes') if k in parameters), None)
        self.call_signature = str(inspect.signature(self.function))

    def decide(self, observation, previous):
        # Deliberately never pass Environment, World, seed, or spectator state.
        obs = wire_copy(observation)
        kwargs = {self.outcomes_key: wire_copy(previous)} if self.outcomes_key else {}
        result = self.function(obs, **kwargs)
        if self.spec['truncate']:
            result = result[:100]
        if type(result) is not list or len(result) > 100:
            raise ValueError('commands must be a list of at most 100 commands')
        return wire_copy(result)


def score(report, nation):
    result = report['result']
    horizon = 1680 * 24
    if result['reason'] == 'unification':
        return 1500 - 500 * result['hour'] / horizon if result['winner'] == nation else 250 * result['hour'] / horizon
    totals = {v['nation']: v for v in report['totals']}
    cities = result['cities']
    count = cities.get(str(nation), cities.get(nation, 0))
    return 250 + 400 * count / max(1, sum(cities.values())) + 50 * sum(
        totals[nation][k] / max(1, totals[0][k] + totals[1][k]) for k in ('military', 'population'))


def snapshot(world):
    return {'hour': world.hour, 'day': world.hour / 24, 'totals': world.observer_totals(),
            'captures': len(world.history), 'result': world.result}


def run_job(job):
    started = time.monotonic()
    dest = Path(job['destination'])
    dest.mkdir()
    row = {k: job[k] for k in ('job_id', 'seed', 'side', 'days')}
    row.update(status='failed', development_run=True, agent_errors=[0, 0],
               command_rejections=[0, 0], slow_decisions=[0, 0], max_decision_seconds=[0., 0.])
    try:
        for key in tuple(os.environ):
            if key.startswith('GB_'):
                del os.environ[key]
        sys.path.insert(0, str(Path(job['root']) / 'game'))
        from aiwar.sdk import Environment
        env = Environment(job['seed'], {'days': job['days'], 'mode': 'duel'})
        own = 0 if job['side'] == 'blue' else 1
        specs = [None, None]
        specs[own], specs[1-own] = job['agent'], job['opponent']
        with (dest/'agent-0.stderr.log').open('w') as err0, (dest/'agent-1.stderr.log').open('w') as err1, \
                (dest/'agent-0.stdout.log').open('w') as out0, (dest/'agent-1.stdout.log').open('w') as out1, \
                gzip.open(dest/'faults-and-rejections.jsonl.gz', 'wt', encoding='utf-8', compresslevel=1) as faults, \
                (dest/'timeline.jsonl').open('w', encoding='utf-8') as timeline:
            errors, outputs = [err0, err1], [out0, out1]
            agents = []
            for n in (0, 1):
                with redirect_stderr(errors[n]), redirect_stdout(outputs[n]):
                    agents.append(Adapter(specs[n], f"{job['job_id']}_{n}"))
            row['adapters'] = [{'api': s['api'], 'signature': a.call_signature, 'truncate': s['truncate'],
                                'outcomes_argument': a.outcomes_key}
                               for s, a in zip(specs, agents)]
            previous = [[], []]
            next_sample = 0
            last_capture_count = 0
            decisions = 0
            timeline.write(json.dumps(snapshot(env.world)) + '\n')
            while not env.world.result:
                observations = env.observations()
                hour = env.world.hour
                actions = []
                for n in (0, 1):
                    t = time.monotonic()
                    try:
                        with redirect_stderr(errors[n]), redirect_stdout(outputs[n]):
                            commands = agents[n].decide(observations[n], previous[n])
                    except Exception as exc:
                        commands = []
                        row['agent_errors'][n] += 1
                        event = {'hour': hour, 'nation': n, 'kind': 'agent_exception',
                                 'error': repr(exc), 'traceback': traceback.format_exc()}
                        faults.write(json.dumps(event, ensure_ascii=False) + '\n')
                    elapsed = time.monotonic() - t
                    row['max_decision_seconds'][n] = max(row['max_decision_seconds'][n], elapsed)
                    if elapsed > job['slow_seconds']:
                        row['slow_decisions'][n] += 1
                        faults.write(json.dumps({'hour': hour, 'nation': n, 'kind': 'slow_decision',
                                                 'seconds': elapsed}) + '\n')
                    actions.append(commands)
                transition = env.step(actions)
                previous = transition['outcomes']
                for n in (0, 1):
                    for command, outcome in zip(actions[n], previous[n]):
                        if not outcome.get('ok', True):
                            row['command_rejections'][n] += 1
                            faults.write(json.dumps({'hour': hour, 'nation': n, 'kind': 'command_rejection',
                                                     'command': command, 'outcome': outcome}, ensure_ascii=False) + '\n')
                env.world.check()
                decisions += 1
                if env.world.hour >= next_sample or len(env.world.history) != last_capture_count or env.world.result:
                    snap = snapshot(env.world)
                    snap['new_captures'] = env.world.history[last_capture_count:]
                    snap['decisions'] = decisions
                    snap['command_rejections'] = row['command_rejections'][:]
                    timeline.write(json.dumps(snap, ensure_ascii=False) + '\n')
                    next_sample = env.world.hour + job['timeline_days'] * 24
                    last_capture_count = len(env.world.history)
            report = env.export(dest)
            row.update(status='completed', result=report['result'], physics_digest=report['physics_digest'],
                       config_sha256=report['config_sha256'], decisions=decisions, totals=report['totals'],
                       captures=report['captures'], score_agent=score(report, own), score_opponent=score(report, 1-own),
                       win=None if report['result']['winner'] is None else report['result']['winner'] == own)
        row['stderr_tracebacks'] = [(dest/f'agent-{n}.stderr.log').read_text().count('Traceback (most recent call last):')
                                    for n in (0, 1)]
    except BaseException as exc:
        row['fatal_error'] = repr(exc)
        (dest/'fatal-error.log').write_text(traceback.format_exc())
    row['elapsed_seconds'] = time.monotonic() - started
    row['source_sha256'] = job['source_sha256']
    write_json(dest/'summary.json', row)
    return row


def summarize(rows):
    ok = [r for r in rows if r['status'] == 'completed']
    result = {'planned': len(rows), 'completed': len(ok), 'failed': len(rows)-len(ok),
              'wins': sum(r['win'] is True for r in ok), 'draws': sum(r['win'] is None for r in ok),
              'losses': sum(r['win'] is False for r in ok),
              'agent_error_events': sum(sum(r['agent_errors']) for r in rows),
              'command_rejections': sum(sum(r['command_rejections']) for r in rows),
              'slow_decisions': sum(sum(r['slow_decisions']) for r in rows),
              'score_agent': statistics.mean(r['score_agent'] for r in ok) if ok else None,
              'sides': {}}
    for side in ('blue', 'red'):
        selected = [r for r in ok if r['side'] == side]
        result['sides'][side] = {'wins': sum(r['win'] is True for r in selected),
                                'draws': sum(r['win'] is None for r in selected),
                                'losses': sum(r['win'] is False for r in selected)}
    return result


def parse_seeds(values):
    seeds = []
    for item in values:
        path = Path(item)
        if path.is_file():
            data = json.loads(path.read_text())
            seeds.extend(data['seeds'] if isinstance(data, dict) else data)
        else:
            for part in item.split(','):
                if ':' in part:
                    lo, hi = map(int, part.split(':'))
                    seeds.extend(range(lo, hi))
                else:
                    seeds.append(int(part))
    if not seeds or len(set(seeds)) != len(seeds) or any(type(s) is not int for s in seeds):
        raise ValueError('Seeds must be nonempty, unique integers')
    return seeds


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, help='Public repository root containing game/ and freeze/')
    p.add_argument('--agent', required=True)
    p.add_argument('--opponent', default='march')
    p.add_argument('--agent-api', default='auto')
    p.add_argument('--opponent-api', default='auto')
    p.add_argument('--seeds', nargs='+', required=True, help='Integers, comma lists, start:stop, or JSON list/{seeds:[]} file')
    p.add_argument('--sides', nargs='+', default=['blue', 'red'], help='Candidate sides: blue red, blue,red, or both')
    p.add_argument('--days', type=int, default=1680)
    p.add_argument('--workers', type=int, default=1)
    p.add_argument('--output', required=True, help='Must not exist')
    p.add_argument('--timeline-days', type=int, default=84)
    p.add_argument('--slow-seconds', type=float, default=2.)
    args = p.parse_args()
    root, output = Path(args.root).resolve(), Path(args.output).resolve()
    seeds = parse_seeds(args.seeds)
    sides = [s for value in args.sides for s in value.split(',')]
    if sides == ['both']:
        sides = ['blue', 'red']
    if not sides or len(set(sides)) != len(sides) or any(s not in ('blue', 'red') for s in sides):
        p.error('--sides must select blue and/or red once each')
    if min(args.days, args.workers, args.timeline_days) <= 0 or args.slow_seconds <= 0:
        p.error('days, workers, timeline-days, slow-seconds must be positive')
    for prefix in ('game', 'freeze', 'benchmarks/data', 'benchmarks/reports', 'strategies/reference'):
        if output.is_relative_to(root / prefix):
            p.error('Output must not be in frozen directories')
    agent, opponent = audit_agent(args.agent, args.agent_api), audit_agent(args.opponent, args.opponent_api)
    # Verify all published files once; do not silently evaluate modified physics.
    verified = subprocess.run([sys.executable, str(root/'tools/verify_release.py'), '--root', str(root)],
                              capture_output=True, text=True)
    if verified.returncode:
        raise RuntimeError('Frozen release verification failed: ' + verified.stdout + verified.stderr)
    output.mkdir(parents=True, exist_ok=False)
    (output/'verify-release.log').write_text(verified.stdout + verified.stderr)
    source_hashes = {str(f.relative_to(root)): sha(f) for f in sorted((root/'game/aiwar').glob('*.py'))}
    source_hashes['freeze/v0.2.0.json'] = sha(root/'freeze/v0.2.0.json')
    for name, spec in (('agent', agent), ('opponent', opponent)):
        if spec['path'] != 'march':
            shutil.copyfile(spec['path'], output/f'{name}.source.py')
            source_hashes[name] = spec['sha256']
    source_hashes['run_dev.py'] = sha(__file__)
    shutil.copyfile(__file__, output/'run_dev.source.py')
    jobs = [{'job_id': f'i{i:03d}-{side}-s{seed}', 'seed': seed, 'side': side, 'days': args.days,
             'root': str(root), 'destination': str(output/f'i{i:03d}-{side}-s{seed}'),
             'agent': agent, 'opponent': opponent, 'source_sha256': source_hashes,
             'timeline_days': args.timeline_days, 'slow_seconds': args.slow_seconds}
            for i, seed in enumerate(seeds) for side in sides]
    manifest = {'baseline': 'v0.2.0', 'development_run': True, 'created_unix': time.time(),
                'root': str(root), 'agent': agent, 'opponent': opponent, 'days': args.days,
                'seeds': seeds, 'sides': sides, 'workers': args.workers,
                'python': sys.version, 'platform': platform.platform(), 'source_sha256': source_hashes,
                'planned_jobs': [{k: j[k] for k in ('job_id', 'seed', 'side')} for j in jobs],
                'protocol': 'in-process observation API, JSON round-trip at policy boundary',
                'limitations': ['No isolation against malicious imported code.',
                               'No enforced 2-second timeout; slow calls are recorded and applied.',
                               'Exceptions produce empty commands; instance remains alive.',
                               'Development scores require independent original JSONL validation.',
                               'Scores use 1680-day reference horizon even in short development runs.'],
                'gb_environment_override_keys_removed': sorted(k for k in os.environ if k.startswith('GB_'))}
    write_json(output/'experiment.json', manifest)
    started, rows = time.monotonic(), []
    with ProcessPoolExecutor(max_workers=args.workers, mp_context=multiprocessing.get_context('spawn')) as pool:
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
                                                     'agent_errors', 'command_rejections')}, ensure_ascii=False), flush=True)
    changed = [name for name, digest in source_hashes.items()
               if name.startswith(('game/', 'freeze/')) and sha(root/name) != digest]
    changed.extend(name for name, spec in (('agent', agent), ('opponent', opponent))
                   if spec['path'] != 'march' and sha(spec['path']) != spec['sha256'])
    summary = summarize(rows)
    final = {'summary': summary, 'rows': rows, 'planned_jobs': len(jobs), 'completed_jobs': len(rows),
             'source_files_changed_during_run': changed, 'elapsed_seconds': time.monotonic()-started}
    write_json(output/'results.json', final)
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 1 if summary['failed'] or changed else 0


if __name__ == '__main__':
    raise SystemExit(main())
