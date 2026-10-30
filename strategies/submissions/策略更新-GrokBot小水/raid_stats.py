"""Raid statistics for report 08: W-D-L, mean days, completed raids by each side, raid starts/defense/ambush counts from agent logs.
usage: raid_stats.py <me> <opp> [seedspec-ignored]   (scans runs/grokbot/h2h/<me>-vs-<opp>-*)"""
import json, glob, os, sys, collections
H = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../runs/grokbot/h2h')
SEL = json.load(open(os.path.join(H, '../../../benchmarks/data/direct-garrison-20261029/seed-selection.json')))
STD = [str(x) for x in (SEL['seeds'] if isinstance(SEL, dict) else SEL)][:12]
def stats(me, opp, k=None):
    r = collections.Counter(); days = []
    for d in sorted(glob.glob(f'{H}/{glob.escape(me)}-vs-{glob.escape(opp)}-*-d1680')):
        if k and d.rsplit('-s', 1)[1].split('-')[0] not in STD[:k]: continue
        if not os.path.exists(d + '/result.json'): continue
        side = 'blue' if '-blue-s' in d else 'red'; n = 0 if side == 'blue' else 1
        res = json.load(open(d + '/result.json'))['result']; w = res.get('winner')
        r['W' if w == n else 'L' if w == 1 - n else 'D'] += 1
        if w == n and res.get('reason') == 'unification': days.append(res['hour'] / 24)
        ev = json.load(open(d + '/final.save.json'))['events']
        for e in ev:
            if e.get('kind') == 'raid': r['raid_me' if e.get('nation') == n else 'raid_opp'] += 1
        for nk, f in ((n, 'me'), (1 - n, 'opp')):
            try: t = open(f'{d}/agent-{nk}.stderr.log', errors='replace').read()
            except OSError: continue
            r[f'start_{f}'] += t.count('HUNT raid '); r[f'def_{f}'] += t.count('RAIDDEF u'); r[f'skip_{f}'] += t.count('RAIDDEF skip'); r[f'ambush_{f}'] += t.count('HUNT ambush')
    g = r['W'] + r['D'] + r['L']
    return g, r, (sum(days) / len(days) if days else 0)
if __name__ == '__main__':
    pairs = [a.split(':') for a in sys.argv[1:]]  # me:opp[:k]  (k = only the first k standard seeds)
    print('| me | opp | games | W-D-L | win days | raids done me/opp | raid starts me/opp | defense sent | defense skipped | ambush sprung |')
    print('|---|---|---|---|---|---|---|---|---|---|')
    for pr in pairs:
        me, opp = pr[0], pr[1]; g, r, dd = stats(me, opp, int(pr[2]) if len(pr) > 2 else None)
        print(f"| {me} | {opp} | {g} | {r['W']}-{r['D']}-{r['L']} | {dd:.0f} | {r['raid_me']}/{r['raid_opp']} | {r['start_me']}/{r['start_opp']} | {r['def_me']} | {r['skip_me']} | {r['ambush_me']} |")
