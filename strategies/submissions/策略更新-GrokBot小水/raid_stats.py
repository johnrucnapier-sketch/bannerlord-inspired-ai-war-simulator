"""Raid statistics for report 08: W-D-L, mean days, completed raids by each side, raid starts/defense/ambush counts from agent logs.
usage: raid_stats.py <me> <opp> [seedspec-ignored]   (scans runs/grokbot/h2h/<me>-vs-<opp>-*)"""
import json, glob, os, sys, collections
H = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../runs/grokbot/h2h')
def stats(me, opp):
    r = collections.Counter(); days = []
    for d in sorted(glob.glob(f'{H}/{glob.escape(me)}-vs-{glob.escape(opp)}-*-d1680')):
        if not os.path.exists(d + '/result.json'): continue
        side = 'blue' if '-blue-s' in d else 'red'; n = 0 if side == 'blue' else 1
        res = json.load(open(d + '/result.json'))['result']; w = res.get('winner')
        r['W' if w == n else 'L' if w == 1 - n else 'D'] += 1
        if w == n and res.get('reason') == 'unification': days.append(res['hour'] / 24)
        ev = json.load(open(d + '/final.save.json'))['events']
        for e in ev:
            if e.get('kind') == 'raid': r['raid_me' if e.get('nation') == n else 'raid_opp'] += 1
        for k, f in ((n, 'me'), (1 - n, 'opp')):
            try: t = open(f'{d}/agent-{k}.stderr.log', errors='replace').read()
            except OSError: continue
            r[f'start_{f}'] += t.count('HUNT raid '); r[f'def_{f}'] += t.count('RAIDDEF u'); r[f'skip_{f}'] += t.count('RAIDDEF skip'); r[f'ambush_{f}'] += t.count('HUNT ambush')
    g = r['W'] + r['D'] + r['L']
    return g, r, (sum(days) / len(days) if days else 0)
if __name__ == '__main__':
    pairs = [a.split(':') for a in sys.argv[1:]]
    print('| me | opp | games | W-D-L | win days | raids done me/opp | raid starts me/opp | defense sent | defense skipped | ambush sprung |')
    print('|---|---|---|---|---|---|---|---|---|---|')
    for me, opp in pairs:
        g, r, dd = stats(me, opp)
        print(f"| {me} | {opp} | {g} | {r['W']}-{r['D']}-{r['L']} | {dd:.0f} | {r['raid_me']}/{r['raid_opp']} | {r['start_me']}/{r['start_opp']} | {r['def_me']} | {r['skip_me']} | {r['ambush_me']} |")
