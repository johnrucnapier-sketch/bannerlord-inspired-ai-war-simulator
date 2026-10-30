"""Grok Bot (小水): markdown table of results-famine/*.json (report 07). Usage: python fam_table.py <pattern> ..."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
K = ('starve_city_days', 'starve_dead_est', 'zero_food_days', 'episodes', 'ep_stack', 'ep_bandit', 'ep_other', 'dead_cities')
print('| 对局（我方 vs 对手） | 局数 | 统计方 | 城市日 | 断粮城市日 | 每千城市日 | 估计饿死 | 存粮为 0 城市日 | 断粮事件 | 其中 部队堆积/匪患/其他 | 断粮后 60 天内失城 |')
print('|---|---|---|---|---|---|---|---|---|---|---|')
for pat in sys.argv[1:]:
    g = json.load(open(HERE / 'results-famine' / f'{pat}.json'))
    me, opp = pat.split('-vs-')
    for who, name in (('me', me), ('opp', opp)):
        t = {k: sum((x[who] or {}).get(k, 0) for x in g) for k in K + ('city_days',)}
        print(f"| {pat} | {len(g)} | {name} | {t['city_days']} | {t['starve_city_days']} | {1000 * t['starve_city_days'] / max(1, t['city_days']):.1f} | {t['starve_dead_est']} | {t['zero_food_days']} | {t['episodes']} | {t['ep_stack']}/{t['ep_bandit']}/{t['ep_other']} | {t['dead_cities']} |")
