"""Aggregate runs/grokbot/results.jsonl -> results.csv / results.json (latest record per label/side/seed/days)."""
import json, csv, statistics as st
from pathlib import Path
R = Path('/workspace/aiwar/runs/grokbot/results.jsonl'); OUT = Path(__file__).parent
recs = {}
for line in open(R):
    try: r = json.loads(line)
    except ValueError: continue  # truncated line (disk-full incident 2026-10-29 ~11:45)
    if 'error' in r: continue
    recs[(r['label'], r['side'], r['seed'], r['days'])] = r
groups = {}
for (lab, side, seed, days), r in recs.items(): groups.setdefault((lab, side, days), []).append(r)
rows = []
for (lab, side, days), rs in sorted(groups.items()):
    unif = [r['hour'] / 24 for r in rs if r['reason'] == 'unification' and r['win']]
    lost_unif = [r['hour'] / 24 for r in rs if r['reason'] == 'unification' and r['win'] is False]
    rows.append(dict(label=lab, side=side, days=days, games=len(rs), W=sum(r['win'] is True for r in rs), L=sum(r['win'] is False for r in rs),
                     D=sum(r['win'] is None for r in rs), mean_cities=round(st.mean(r['cities_me'] for r in rs), 2),
                     mean_pop=round(st.mean(r['pop_me'] for r in rs)), mean_pop_opp=round(st.mean(r['pop_opp'] for r in rs)),
                     unifications=len(unif), mean_unif_day=round(st.mean(unif), 1) if unif else None, fastest_unif=min(unif) if unif else None,
                     unified_against=len(lost_unif), invalid_cmds=sum(r['invalid_cmds'] for r in rs), agent_errors=sum(r['agent_errors'] for r in rs),
                     seeds=' '.join(str(r['seed']) for r in sorted(rs, key=lambda r: r['seed']))))
with open(OUT / 'results.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
json.dump(dict(aggregates=rows, games=list(recs.values())), open(OUT / 'results.json', 'w'), ensure_ascii=False, indent=1)
for r in rows: print({k: v for k, v in r.items() if k != 'seeds'})
