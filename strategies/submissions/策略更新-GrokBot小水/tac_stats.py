"""Tactic statistics for report 09: per matchup W-D-L plus how often each v24 tactic fired (TAC lines in our agent log)
and our win rate in games where it fired vs. did not.
usage: tac_stats.py me:opp[:k] ...   (k = only the first k standard seeds; scans runs/grokbot/h2h/<me>-vs-<opp>-*)"""
import json, glob, os, sys, collections
H = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../runs/grokbot/h2h')
SEL = json.load(open(os.path.join(H, '../../../benchmarks/data/direct-garrison-20261029/seed-selection.json')))
STD = [str(x) for x in (SEL['seeds'] if isinstance(SEL, dict) else SEL)][:12]
TAC = ['intercept', 'intercept-skip', 'feint', 'bait', 'way', 'state']
STATES = ['ahead', 'even', 'behind']
def stats(me, opp, k=None):
    r = collections.Counter(); fired = collections.defaultdict(lambda: [0, 0]); days = []
    for d in sorted(glob.glob(f'{H}/{glob.escape(me)}-vs-{glob.escape(opp)}-*-d1680')):
        if k and d.rsplit('-s', 1)[1].split('-')[0] not in STD[:k]: continue
        if not os.path.exists(d + '/result.json'): continue
        n = 0 if '-blue-s' in d else 1
        res = json.load(open(d + '/result.json'))['result']; w = res.get('winner')
        r['W' if w == n else 'L' if w == 1 - n else 'D'] += 1
        if w == n and res.get('reason') == 'unification': days.append(res['hour'] / 24)
        for e in json.load(open(d + '/final.save.json'))['events']:
            if e.get('kind') == 'raid': r['raid_me' if e.get('nation') == n else 'raid_opp'] += 1
        try: t = open(f'{d}/agent-{n}.stderr.log', errors='replace').read()
        except OSError: t = ''
        st = [l for l in t.splitlines() if ' STAT ' in l]
        if st:
            j = json.loads(st[-1].split(' STAT ', 1)[1])
            for kk, vv in j.items():
                if kk.startswith(('s_', 'days_')): r[kk] += vv
        for x in TAC:
            c = t.count(f'TAC {x} '); r[x] += c
            if x != 'intercept-skip' and c: fired[x][0] += 1; fired[x][1] += (w == n)
    return r, fired, (sum(days) / len(days) if days else 0)
if __name__ == '__main__':
    print('| me | opp | W-D-L | win days | raids me/opp | ' + ' | '.join(TAC) + ' | games fired (wins): int / feint / bait / way |')
    print('|---|---|---|---|---|' + '---|' * len(TAC) + '---|')
    for a in sys.argv[1:]:
        p = a.split(':'); r, f, dd = stats(p[0], p[1], int(p[2]) if len(p) > 2 else None)
        print(f"| {p[0]} | {p[1]} | {r['W']}-{r['D']}-{r['L']} | {dd:.0f} | {r['raid_me']}/{r['raid_opp']} | " + ' | '.join(str(r[x]) for x in TAC)
              + ' | ' + ' / '.join(f"{f[x][0]}({f[x][1]})" for x in ('intercept', 'feint', 'bait', 'way')) + ' |')
    print()
    print('| me | opp | days ahead/even/behind | raid a/e/b | bait a/e/b | feint a/e/b | intercept a/e/b | way a/e/b |')
    print('|---|---|---|---|---|---|---|---|')
    for a in sys.argv[1:]:
        p = a.split(':'); r, f, dd = stats(p[0], p[1], int(p[2]) if len(p) > 2 else None)
        print(f"| {p[0]} | {p[1]} | " + '/'.join(str(r['days_' + s]) for s in STATES) + ' | '
              + ' | '.join('/'.join(str(r[f's_{t}_{s}']) for s in STATES) for t in ('raid', 'bait', 'feint', 'intercept', 'way')) + ' |')
    print()
    print('| me | opp | dominant state: games W-D-L (ahead / even / behind) | ever behind W-D-L | never behind W-D-L | state changes per game |')
    print('|---|---|---|---|---|---|')
    for a in sys.argv[1:]:
        p = a.split(':'); k = int(p[2]) if len(p) > 2 else None
        dom = {s: collections.Counter() for s in STATES}; eb = collections.Counter(); nb = collections.Counter(); ch = []
        for d in sorted(glob.glob(f'{H}/{glob.escape(p[0])}-vs-{glob.escape(p[1])}-*-d1680')):
            if k and d.rsplit('-s', 1)[1].split('-')[0] not in STD[:k]: continue
            if not os.path.exists(d + '/result.json'): continue
            n = 0 if '-blue-s' in d else 1; w = json.load(open(d + '/result.json'))['result'].get('winner')
            o = 'W' if w == n else 'L' if w == 1 - n else 'D'
            try: t = open(f'{d}/agent-{n}.stderr.log', errors='replace').read()
            except OSError: continue
            st = [l for l in t.splitlines() if ' STAT ' in l]
            if not st: continue
            j = json.loads(st[-1].split(' STAT ', 1)[1])
            dd = {s: j.get('days_' + s, 0) for s in STATES}
            if sum(dd.values()): dom[max(dd, key=dd.get)][o] += 1
            (eb if dd['behind'] else nb)[o] += 1; ch.append(t.count('TAC state '))
        f = lambda c: f"{c['W']}-{c['D']}-{c['L']}"
        print(f"| {p[0]} | {p[1]} | " + ' / '.join(f(dom[s]) for s in STATES) + f" | {f(eb)} | {f(nb)} | {sum(ch)/max(1,len(ch)):.1f} |")
