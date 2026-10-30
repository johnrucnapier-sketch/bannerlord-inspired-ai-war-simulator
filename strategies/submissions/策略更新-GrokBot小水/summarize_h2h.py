"""Grok Bot (小水): aggregate runs/grokbot/h2h.jsonl -> h2h-vs-gptdot.{csv,json,md} (latest record per me/opp/side/seed)."""
import json, csv, statistics as st
from pathlib import Path
HERE = Path(__file__).resolve().parent; R = HERE.parents[2] / 'runs/grokbot/h2h.jsonl'
NAMES = {'c600': 'GPT dot Campaign600 v1', 'c600v4': 'GPT dot Campaign600 v4 Early Relief', 'c600v6': 'GPT dot Campaign600 v6 Feasible Relief', 'march': 'march (frozen default)', 'v20': 'Grok Bot v20'}
recs = {}
for line in open(R):
    try: r = json.loads(line)
    except ValueError: continue
    if 'error' in r: continue
    recs[(r['me'], r['opp'], r['side'], r['seed'])] = r
def faults(r):
    out = Path(r['out']); me = 0 if r['side'] == 'blue' else 1
    try: errs = json.load(open(out / 'match.json')).get('agent_errors', [0, 0])
    except Exception: errs = [0, 0]
    tb = []
    for k in (me, 1 - me):
        f = out / f'agent-{k}.stderr.log'
        tb.append(open(f, errors='replace').read().count('Traceback') if f.exists() else 0)
    return dict(proto_err_me=errs[me], proto_err_opp=errs[1 - me], tb_me=tb[0], tb_opp=tb[1])
for r in recs.values(): r.update(faults(r)); r['clean'] = r['proto_err_me'] == 0 and r['proto_err_opp'] == 0 and r['tb_me'] == 0 and r['tb_opp'] == 0
STD = set(json.load(open(HERE.parents[2] / 'benchmarks/data/direct-garrison-20261029/seed-selection.json'))['seeds'])
groups = {}
SELF = {20261030, 31415926, 27182818, 16180339, 14142135, 17320508}  # Grok self-chosen seeds (report 06)
for (me, opp, side, seed), r in recs.items(): groups.setdefault((me, opp, side, 'std' if seed in STD else 'self' if seed in SELF else 'gpt-v6-indep'), []).append(r)
rows = []
for (me, opp, side, seedset), rs in sorted(groups.items()):
    u = [r['hour'] / 24 for r in rs if r['reason'] == 'unification' and r['win']]
    ul = [r['hour'] / 24 for r in rs if r['reason'] == 'unification' and r['win'] is False]
    W = sum(r['win'] is True for r in rs); L = sum(r['win'] is False for r in rs)
    rows.append(dict(me=me, opp=opp, side=side, seed_set=seedset, games=len(rs), W=W, D=len(rs) - W - L, L=L, win_rate=round(W / len(rs), 3),
                     mean_cities=round(st.mean(r['cities_me'] for r in rs), 2), mean_pop=round(st.mean(r['pop_me'] for r in rs)),
                     mean_pop_opp=round(st.mean(r['pop_opp'] for r in rs)), unifications=len(u), mean_unif_day=round(st.mean(u), 1) if u else None,
                     fastest_unif=round(min(u), 1) if u else None, unified_against=len(ul),
                     faulty_games=sum(not r['clean'] for r in rs), W_clean=sum(r['win'] is True and r['clean'] for r in rs),
                     L_clean=sum(r['win'] is False and r['clean'] for r in rs),
                     seeds=' '.join(str(r['seed']) for r in sorted(rs, key=lambda r: r['seed']))))
out = HERE / 'results-h2h'; out.mkdir(exist_ok=True)
with open(out / 'h2h-vs-gptdot.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
json.dump(dict(aggregates=rows, games=sorted(recs.values(), key=lambda r: (r['me'], r['opp'], r['side'], r['seed']))),
          open(out / 'h2h-vs-gptdot.json', 'w'), ensure_ascii=False, indent=1)
md = ['# Head-to-head results (Grok Bot 小水 vs GPT dot Campaign600 v1, v4 and v6, plus baselines vs march)', '',
      'Full 1680-day matches, frozen rules v0.2.0, seeds from `benchmarks/data/direct-garrison-20261029/seed-selection.json`. ',
      'Campaign600 v1 = branch `gpt-dot/campaign600-v1-20261029`, commit `02966b3`, `strategies/submissions/cloud_campaign_v7_min600/policy.py` (unmodified, loaded via `gpt_adapter.py`). ',
      'Campaign600 v4 / v6 = `strategies/submissions/策略更新-GPTdot/v4/policy.py` (f8e10d6) / `v6/policy.py` (16e67a6, SHA256 f8e10fca...ae75) on main, unmodified, run in place. Seed set `std` = the benchmark seeds; `gpt-v6-indep` = the 12 independent seeds listed in GPT dot v6 results.json; `self` = Grok 6 self-chosen seeds 20261030, 31415926, 27182818, 16180339, 14142135, 17320508 (report 06). `vN@GB_EARLY=30` = Grok vN with that environment parameter.', '',
      '| me | opponent | my side | seed set | games | W-D-L | win rate | mean cities | mean pop (me/opp) | unifications (mean / fastest day) | unified against | games with runtime faults (W/L among clean games) |', '|---|---|---|---|---|---|---|---|---|---|---|---|']
for r in rows:
    md.append(f"| {NAMES.get(r['me'], 'Grok Bot ' + r['me'])} | {NAMES.get(r['opp'], r['opp'])} | {r['side']} | {r['seed_set']} | {r['games']} | {r['W']}-{r['D']}-{r['L']} | {r['win_rate']:.0%} | {r['mean_cities']} | {r['mean_pop']} / {r['mean_pop_opp']} | {r['unifications']} ({r['mean_unif_day']} / {r['fastest_unif']}) | {r['unified_against']} | {r['faulty_games']} ({r['W_clean']}/{r['L_clean']}) |")
(out / 'h2h-vs-gptdot.md').write_text('\n'.join(md) + '\n')
for r in rows: print({k: v for k, v in r.items() if k != 'seeds'})
