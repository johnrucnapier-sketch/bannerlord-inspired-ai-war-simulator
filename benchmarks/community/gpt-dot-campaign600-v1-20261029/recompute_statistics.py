#!/usr/bin/env python3
"""Recompute completed v1 primary/supplemental statistics from portable summaries.

Python standard library only. No simulation, original repository, observations,
commands, saves, network, or exploratory selection analysis. Optional fresh24-cluster confirmation is
checked only when its final summary and all96 completed rows exist. Default is read-only.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random

PRIMARY = {'baseline': 'heldout-baseline-48-paired', 'candidate': 'heldout-candidate-48-paired'}
SECONDARY = {'v7_vs_d2': 'supplemental-v7-vs-d2-16-paired',
             'v7_vs_w4': 'supplemental-v7-vs-w4-16-paired',
             'd2_vs_w4': 'supplemental-d2-vs-w4-16-paired'}
SELECTED_SHA = '1aed9815302f846238d4756c378b7161ba2170869008205a20662b1a96ba6c44'


def score(row):
    if row['status'] != 'completed':
        return None
    winner = row['winner']
    if winner not in (None, 0, 1):
        raise ValueError('Invalid winner')
    return .5 if winner is None else int(winner == row['side'])


def tally(rows):
    outcomes = Counter()
    for row in rows:
        value = score(row)
        if value is not None:
            outcomes[{0:'losses', .5:'draws', 1:'wins'}[value]] += 1
    n = sum(outcomes.values())
    return {'planned': len(rows), 'completed': n,
            **{k: outcomes[k] for k in ('wins', 'draws', 'losses')},
            'score_mean': (outcomes['wins'] + .5*outcomes['draws'])/n if n else None}


def percentile(ordered, probability):
    if not ordered:
        return None
    pos = (len(ordered)-1)*probability
    lower, upper = math.floor(pos), math.ceil(pos)
    return ordered[lower]*(upper-pos) + ordered[upper]*(pos-lower) if lower != upper else ordered[lower]


def bootstrap(columns, repetitions, random_seed):
    """One seed-frequency draw shared across endpoints, not per-game draws."""
    lengths = {len(v) for v in columns.values()}
    if len(lengths) != 1:
        raise ValueError('Cluster column lengths differ')
    n = lengths.pop()
    if any(v is None for col in columns.values() for v in col):
        raise ValueError('This portable recomputation requires all planned outcomes; no silent complete-case substitution')
    result = {name: {'estimate': sum(values)/n if n else None, 'ci95': None} for name, values in columns.items()}
    if n < 2:
        return result
    rng = random.Random(random_seed)
    distributions = {name: [] for name in columns}
    for _ in range(repetitions):
        frequencies = Counter(rng.randrange(n) for _ in range(n))
        for name, values in columns.items():
            distributions[name].append(sum(values[i]*count for i,count in frequencies.items())/n)
    for name, values in distributions.items():
        ordered = sorted(values)
        result[name]['ci95'] = [percentile(ordered,.025), percentile(ordered,.975)]
    return result


def paired_primary(baseline, candidate, seeds):
    values = {'score_delta': [], 'city_margin_delta': [], 'win_rate_delta': []}
    for seed in sorted(seeds):
        pair = [(baseline[(seed,s)], candidate[(seed,s)]) for s in (0,1)]
        values['score_delta'].append(sum(score(c)-score(b) for b,c in pair)/2)
        values['city_margin_delta'].append(sum((c['own_cities']-c['opponent_cities'])-(b['own_cities']-b['opponent_cities']) for b,c in pair)/2)
        values['win_rate_delta'].append(sum(int(score(c)==1)-int(score(b)==1) for b,c in pair)/2)
    return bootstrap(values, 10000, 20261029)


def paired_secondary(groups, seeds):
    columns = {'direct_score': [], 'common_opponent_delta': []}
    for seed in seeds:  # Prespecified plan order determines reproducible RNG indexing.
        columns['direct_score'].append(sum(score(groups['v7_vs_d2'][(seed,s)]) for s in (0,1))/2)
        columns['common_opponent_delta'].append(sum(score(groups['v7_vs_w4'][(seed,s)])-score(groups['d2_vs_w4'][(seed,s)]) for s in (0,1))/2)
    return bootstrap(columns, 20000, 949650764)


def index_rows(rows, batch, seeds, phase):
    result = {}
    for row in rows:
        if row['batch'] != batch:
            continue
        key = (row['seed'], row['side'])
        if key in result:
            raise ValueError('Duplicate planned key: ' + batch)
        if row['phase'] != phase or row['days_planned'] != 1680 or row['decision_hours'] != 6:
            raise ValueError('Unexpected study role/horizon/cadence: ' + batch)
        if row['status'] != 'completed':
            raise ValueError('Incomplete planned outcome; refusal is intentional: ' + batch)
        if score(row) != row['score'] or {0:'L',.5:'D',1:'W'}[score(row)] != row['outcome']:
            raise ValueError('Exported score/outcome disagrees with winner/side: ' + batch)
        result[key] = row
    expected = {(seed,s) for seed in seeds for s in (0,1)}
    if set(result) != expected:
        raise ValueError('Planned seed/side coverage differs: ' + batch)
    return result



def recompute(root):
    rows = json.loads((root/'data/all-planned-games.json').read_text())
    seeds = json.loads((root/'seeds.json').read_text())
    expected = json.loads((root/'expected-results.json').read_text())
    groups = {}
    for label, batches, seed_key, phase in [
        ('primary', PRIMARY, 'primary_heldout', 'primary-heldout'),
        ('supplemental', SECONDARY, 'supplemental', 'supplemental-secondary')]:
        groups[label] = {name:index_rows(rows,batch,seeds[seed_key],phase) for name,batch in batches.items()}
    assert len(seeds['primary_heldout']) == 48 and len(seeds['supplemental']) == 16
    assert not set(seeds['primary_heldout']) & set(seeds['supplemental'])
    scientific = [r for g in groups.values() for arm in g.values() for r in arm.values()]
    for field in ('baseline','git_commit','freeze_manifest_sha256','config_file_sha256','config_sha256'):
        if len({r[field] for r in scientific}) != 1 or any(r[field] is None for r in scientific):
            raise ValueError('World/config identity mismatch: '+field)
    for row in scientific:
        if row['policy'].endswith('cloud_campaign_v7_min600/policy.py') and row['policy_sha256'] != SELECTED_SHA:
            raise ValueError('Campaign600 v1 identity mismatch')
    report = {}
    for label, arms in groups.items():
        report[label] = {}
        for name, indexed in arms.items():
            arm = list(indexed.values())
            report[label][name] = dict(tally(arm), by_side={str(s):tally([r for r in arm if r['side']==s]) for s in (0,1)})
    report['primary']['effects'] = paired_primary(groups['primary']['baseline'],groups['primary']['candidate'],seeds['primary_heldout'])
    report['supplemental']['effects'] = paired_secondary(groups['supplemental'],seeds['supplemental'])
    # Resolve the explicitly recorded logical identifiers, retaining original interruption rows.
    attempts = [r for r in rows if r['phase']=='post-confirmatory-exploratory-confirmation']
    logical = {}
    for row in attempts:
        logical.setdefault(row['logical_job_id'],[]).append(row)
    resolved = []
    for key, trial in logical.items():
        complete = [r for r in trial if r['status']=='completed']
        if len(complete) != 1:
            raise ValueError('Missing or duplicate completed logical game: '+key)
        for field in ('seed','side','policy_sha256','opponent_sha256','config_file_sha256','logical_batch'):
            if len({r[field] for r in trial}) != 1:
                raise ValueError('Retry changed assignment: '+field)
        resolved.append(dict(complete[0],batch=complete[0]['logical_batch']))
    fresh_batches = {'baseline':'recovery-confirmation-v1-24-paired','candidate':'recovery-confirmation-candidate-24-paired'}
    fresh = {name:index_rows(resolved,batch,seeds['later_exploratory_confirmation'],'post-confirmatory-exploratory-confirmation') for name,batch in fresh_batches.items()}
    if len(attempts)!=98 or len(resolved)!=96 or sum(r['status']=='infrastructure_interrupted' for r in attempts)!=2:
        raise ValueError('Unexpected retry/attempt accounting')
    report['fresh'] = {name:tally(list(arm.values())) for name,arm in fresh.items()}
    report['fresh']['effects'] = paired_primary(fresh['baseline'],fresh['candidate'],seeds['later_exploratory_confirmation'])
    def equal(a,b):
        if isinstance(a,dict) and isinstance(b,dict):
            return set(a)==set(b) and all(equal(a[k],b[k]) for k in a)
        if isinstance(a,list) and isinstance(b,list):
            return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
        if isinstance(a,(int,float)) and isinstance(b,(int,float)):
            return math.isclose(a,b,rel_tol=0,abs_tol=1e-12)
        return a==b
    passed = equal(report,expected)
    return dict(passed=passed, results=report, recorded_attempts=len(rows), exploratory_attempts=len(attempts),
                exploratory_logical_games=len(resolved), infrastructure_interrupted_attempts=2,
                input_sha256=hashlib.sha256((root/'data/all-planned-games.json').read_bytes()).hexdigest(),
                scope='Read-only arithmetic over the complete sanitized attempt dataset. No simulation or original-log verification. Primary/supplemental/fresh seed clusters remain separate; interrupted originals remain present; only registered logical games are scored. Bootstrap indices and seeds follow the original plans.')

if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    report = recompute(root)
    print(json.dumps(report,indent=2))
    raise SystemExit(0 if report['passed'] else 1)
