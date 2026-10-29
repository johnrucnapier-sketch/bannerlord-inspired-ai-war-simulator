"""Grok Bot (小水) head-to-head runner: <me> vs <opponent>, full matches, both colours.
Agents: 'march'/'d2'/... (built-in), 'c600' (GPT dot Campaign600 v1, loaded unmodified via gpt_adapter.py),
or a version dir name in this folder (e.g. v10). Results -> runs/grokbot/h2h.jsonl.
Usage: python batch_h2h.py v10 c600 --sides blue,red --seeds 0:24 -j 8"""
import argparse, json, subprocess, time, gzip
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]; PY = str(ROOT / '.venv/bin/python')
SEEDS = json.load(open(ROOT / 'benchmarks/data/direct-garrison-20261029/seed-selection.json'))['seeds']
BUILTIN = ('march', 'd2', 'p5', 'p3', 'idle')
def agent_args(name, colour):
    if name in BUILTIN: return ['--' + colour, name]
    if name == 'c600v4':
        cmd = [PY, str(ROOT / 'strategies/submissions/策略更新-GPTdot/v4/policy.py')]
    elif name == 'c600':
        import gpt_adapter; cmd = [PY, str(gpt_adapter.policy_path())]
    else: cmd = [PY, str(HERE / name / 'agent.py')]
    return ['--' + colour + '-command', json.dumps(cmd)]
def summarize(out, me_name, opp_name, side, seed, days):
    r = json.load(open(out / 'result.json')); res = r['result'] or {}
    me = 0 if side == 'blue' else 1
    tot = {t['nation']: t for t in r['totals']}
    caps = r.get('captures', [])
    return dict(me=me_name, opp=opp_name, side=side, seed=seed, days=days, winner=res.get('winner'),
                win=None if res.get('winner') is None else res['winner'] == me, reason=res.get('reason'), hour=res.get('hour'),
                cities_me=res.get('cities', {}).get(str(me)), cities_opp=res.get('cities', {}).get(str(1 - me)),
                pop_me=tot[me]['population'], pop_opp=tot[1 - me]['population'], mil_me=tot[me]['military'], mil_opp=tot[1 - me]['military'],
                first_loss=next((c['hour'] for c in caps if c['from'] == me), None), captures_me=sum(c['to'] == me for c in caps), out=str(out))
def run(job):
    me_name, opp_name, side, seed, days = job
    out = ROOT / 'runs/grokbot/h2h' / f'{me_name}-vs-{opp_name}-{side}-s{seed}-d{days}'
    if (out / 'result.json').exists(): return summarize(out, me_name, opp_name, side, seed, days)
    if out.exists(): subprocess.run(['rm', '-rf', str(out)])  # incomplete previous attempt (scratch run dir only)
    other = 'red' if side == 'blue' else 'blue'
    args = [PY, str(ROOT / 'tools/play.py'), '--seed', str(seed), '--days', str(days), '--output', str(out)] + agent_args(me_name, side) + agent_args(opp_name, other)
    p = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if p.returncode: return dict(me=me_name, opp=opp_name, side=side, seed=seed, error=p.stderr[-800:])
    subprocess.run(f'gzip -1 {out}/nation-*.jsonl', shell=True)
    return summarize(out, me_name, opp_name, side, seed, days)
if __name__ == '__main__':
    a = argparse.ArgumentParser(); a.add_argument('me'); a.add_argument('opp'); a.add_argument('--seeds', default='0:12')
    a.add_argument('--days', type=int, default=1680); a.add_argument('--sides', default='blue,red'); a.add_argument('-j', type=int, default=8); x = a.parse_args()
    i, j = map(int, x.seeds.split(':'))
    jobs = [(x.me, x.opp, s, seed, x.days) for s in x.sides.split(',') for seed in SEEDS[i:j]]
    t = time.time()
    with ThreadPoolExecutor(x.j) as ex: res = list(ex.map(run, jobs))
    (ROOT / 'runs/grokbot').mkdir(exist_ok=True)
    with open(ROOT / 'runs/grokbot/h2h.jsonl', 'a') as f:
        for r in res: f.write(json.dumps(r) + '\n')
    ok = [r for r in res if 'error' not in r]
    for s in x.sides.split(','):
        rs = [r for r in ok if r['side'] == s]
        if not rs: continue
        w = sum(r['win'] is True for r in rs); l = sum(r['win'] is False for r in rs)
        u = [r['hour'] / 24 for r in rs if r['reason'] == 'unification' and r['win']]
        print(f"{x.me} vs {x.opp} [{s}] d{x.days}: W{w} D{len(rs)-w-l} L{l} cities={sum(r['cities_me'] for r in rs)/len(rs):.2f} "
              f"pop={sum(r['pop_me'] for r in rs)/len(rs):.0f}/{sum(r['pop_opp'] for r in rs)/len(rs):.0f} unif={len(u)} mean={sum(u)/len(u) if u else 0:.0f}")
    for r in res:
        if 'error' in r: print('ERROR', r)
    print('elapsed', round(time.time() - t))
