"""Write results.md = narrative + aggregate table from results.csv (run summarize.py first)."""
import csv
from pathlib import Path
H = Path(__file__).parent
rows = list(csv.DictReader(open(H / 'results.csv')))
NAMES = {
 'base-march': 'Baseline: march (frozen default) as blue',
 'v3': 'Grok Bot v3, approach: early rush + doom-stack + per-city anti-bandit patrols',
 'v5': 'Grok Bot v5, approach: patrol-army economy + campaign doom-stack + strong relief',
 'v6': 'Grok Bot v6, approach: early rush + patrol-army economy + campaign doom-stack + strong relief',
 'v7': 'Grok Bot v7, approach: early rush + patrol economy + doom-stack that HOLDS each conquest (hold 60d)',
 'v7-hold30': 'Grok Bot v7 (param sweep GB_HOLD=30)', 'v7-hold120': 'Grok Bot v7 (param sweep GB_HOLD=120)',
 'v8': 'Grok Bot v8, approach: v7 + bug fixes (stale-flag frontier relaunch loop)',
 'v9': 'Grok Bot v9, approach: v8 + relief-aware sieges (remember enemy field parties)',
 'v9-guard13': 'Grok Bot v9 (param sweep GB_GUARD=1.3)', 'v9-margin17': 'Grok Bot v9 (param sweep margin 1.7 / siege 1.55)',
 'v10': 'Grok Bot v10, approach: v9 + pre-emptive city guard (fill threatened cities before the siege)',
 'v11': 'Grok Bot v11, approach: v10 + margins 1.7/1.55 + lost-rally-base fix',
 'v13': 'Grok Bot v13, approach: v12 + whole-empire mobilisation for the doom-stack (frontier-only keepers, garrison-aware potential, top-up detours)',
 'v12': 'Grok Bot v12, approach: v10 + capacity-aware doom-stack roster (grows past 3-5 parties for the last cities)',
}
NAMES.update({k: v for k, v in [l.split('=', 1) for l in open(H / 'labels.txt').read().splitlines() if '=' in l]} if (H / 'labels.txt').exists() else {})
t = ['| run | side | games | W-L-D | mean cities | mean pop (me/opp) | unifications (mean / fastest day) | unified against | invalid cmds | errors |',
     '|---|---|---|---|---|---|---|---|---|---|']
for r in rows:
    t.append(f"| {NAMES.get(r['label'], r['label'])} | {r['side']} | {r['games']} | {r['W']}-{r['L']}-{r['D']} | {r['mean_cities']} | {r['mean_pop']} / {r['mean_pop_opp']} | {r['unifications']} ({r['mean_unif_day'] or '-'} / {(r['fastest_unif'] or '-')[:5]}) | {r['unified_against']} | {r['invalid_cmds']} | {r['agent_errors']} |")
body = open(H / 'notes.md').read().replace('{{TABLE}}', '\n'.join(t)).replace('{{LOGFILE}}', open(H / 'log.md').read())
open(H / 'results.md', 'w').write(body)
print('ok')
