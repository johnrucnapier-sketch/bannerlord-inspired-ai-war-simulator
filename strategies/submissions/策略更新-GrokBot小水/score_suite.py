"""Grok Bot (小水) standardized score suite (report 10).
Every entrant plays the same 4 general-purpose anchors (Grok v20, v22; GPT dot c600v4, c600v6) on the first 6 standard seeds x 2 colours
= 48 games. Per-game score (tiers never overlap):
  unification win at hour h      : 1000 + 500 * (1 - h/H)                  -> 1000..1500 (earlier = more)
  no unification by H (1680 days): 250 + 400 * city_share + 100 * (mil_share + pop_share)/2   -> 250..750
  unified by the opponent at h   : 250 * h/H                               -> 0..250 (survive longer = more)
Version score = mean of the 48 game scores; error bar = standard error (sd / sqrt(n)).
Existing games are reused in either orientation (A-vs-B-blue-sS == B-vs-A as red); missing ones are run with batch_h2h.
usage: score_suite.py ENTRANT [ENTRANT ...] [--run -j 4] [--md out.md] [--csv out.csv]"""
import argparse, json, math, os, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[2]; RUNS = ROOT / 'runs/grokbot/h2h'
sys.path.insert(0, str(HERE)); import batch_h2h
ANCHORS = ['v20', 'v22', 'c600v4', 'c600v6']
SEEDS = batch_h2h.SEEDS[:6]; H = 1680 * 24; DAYS = 1680
ALIAS = {'v23': 'v23@GB_RAID=2'}  # run-dir name of the released v23 (identical to its defaults; plain v23-* dirs predate them)
def nm(x): return ALIAS.get(x, x)
def game_score(r, me):
    res = r['result'] or {}; w = res.get('winner'); h = res.get('hour', H)
    if res.get('reason') == 'unification':
        return 1000 + 500 * (1 - h / H) if w == me else 250 * h / H
    cs = res.get('cities', {}); c0, c1 = cs.get(str(me), 0), cs.get(str(1 - me), 0)
    tot = {t['nation']: t for t in r['totals']}
    sh = lambda k: tot[me][k] / max(1, tot[me][k] + tot[1 - me][k])
    return 250 + 400 * c0 / max(1, c0 + c1) + 100 * (sh('military') + sh('population')) / 2
def locate(e, a, side, seed):
    """(dir, our nation index) of an existing finished game, or None"""
    E, A = nm(e), nm(a); me = 0 if side == 'blue' else 1; other = 'red' if side == 'blue' else 'blue'
    for d, n in ((f'{E}-vs-{A}-{side}-s{seed}-d{DAYS}', me), (f'{A}-vs-{E}-{other}-s{seed}-d{DAYS}', me)):
        if (RUNS / d / 'result.json').exists(): return RUNS / d, n
    if E == A:  # mirror: one game gives both colours
        for s2 in ('blue', 'red'):
            d = RUNS / f'{E}-vs-{E}-{s2}-s{seed}-d{DAYS}'
            if (d / 'result.json').exists(): return d, me
    return None
def jobs_for(e):
    out = []
    for a in ANCHORS:
        for seed in SEEDS:
            for side in ('blue', 'red'):
                if locate(e, a, side, seed): continue
                if nm(e) == nm(a) and side == 'red': continue  # mirror red comes from the blue game
                out.append((nm(e), nm(a), side, seed, DAYS))
    return out
def score(e):
    rows = []
    for a in ANCHORS:
        for seed in SEEDS:
            for side in ('blue', 'red'):
                L = locate(e, a, side, seed)
                if L: rows.append((a, side, seed, game_score(json.load(open(L[0] / 'result.json')), L[1])))
    return rows
H2H_EXTRA = {('v24', 'v23'): ('v24', 'v23')}  # v24-vs-v23-* dirs were played against the released v23 code (plain name, valid)
def h2h(e, f):
    """all finished direct games e vs f (any seed, either orientation): (W, D, L) for e; unification wins only count as W/L"""
    E, F = nm(e), nm(f); w = dr = l = 0
    pairs = [(E, F, False), (F, E, True)]
    if (e, f) in H2H_EXTRA: pairs.append(H2H_EXTRA[(e, f)] + (False,))
    if (f, e) in H2H_EXTRA: pairs.append(H2H_EXTRA[(f, e)] + (True,))
    for d in RUNS.glob(f'*-d{DAYS}'):
        name = d.name
        for X, Y, flip in pairs:
            pre = f'{X}-vs-{Y}-'
            if not name.startswith(pre) or not (d / 'result.json').exists(): continue
            rest = name[len(pre):]
            if rest.split('-')[0] not in ('blue', 'red') or rest.count('-') != 2: continue
            n = 0 if rest.startswith('blue') else 1
            if flip: n = 1 - n
            if E == F: continue
            res = json.load(open(d / 'result.json'))['result'] or {}
            if res.get('reason') != 'unification': dr += 1
            elif res.get('winner') == n: w += 1
            else: l += 1
    return w, dr, l
def check(board):
    """does the score order agree with direct head-to-head results?"""
    names = [b[0] for b in board]; sc = {b[0]: (b[2], b[3]) for b in board}
    out = ['| 高分方 | 低分方 | 分差 | 直接对局（高分方 W-D-L） | 一致? |', '|---|---|---|---|---|']
    agree = dis = 0; cope = {e: 0.0 for e in names}; cnt = {e: 0 for e in names}
    for i, e in enumerate(names):
        for f in names[i + 1:]:
            w, dr, l = h2h(e, f)
            if w + dr + l < 6: continue
            p = (w + dr / 2) / (w + dr + l); cope[e] += p - 0.5; cope[f] += 0.5 - p; cnt[e] += 1; cnt[f] += 1
            ok = 'tie' if abs(p - 0.5) < 1e-9 else ('yes' if p > 0.5 else 'NO')
            agree += ok == 'yes'; dis += ok == 'NO'
            diff = sc[e][0] - sc[f][0]; sig = diff / math.hypot(sc[e][1], sc[f][1]) if sc[e][1] or sc[f][1] else 0
            out.append(f'| {e} | {f} | {diff:.0f}（{sig:.1f}σ） | {w}-{dr}-{l} | {ok} |')
    cope = {e: cope[e] / max(1, cnt[e]) for e in names}
    # Kendall tau between score order and Copeland (head-to-head) order
    co = sorted(names, key=lambda e: -cope[e]); pos = {e: i for i, e in enumerate(co)}
    c = d_ = 0
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if cope[names[i]] == cope[names[j]]: continue
            if pos[names[i]] < pos[names[j]]: c += 1
            else: d_ += 1
    tau = (c - d_) / max(1, c + d_)
    out.append(''); out.append(f'一致 {agree} 对，不一致 {dis} 对；Kendall τ（总分排名 vs 直接对局 Copeland 排名）= {tau:.2f}；Copeland 排名：' + ' > '.join(co))
    return '\n'.join(out)

def stats(xs):
    n = len(xs); m = sum(xs) / n if n else 0
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1)) if n > 1 else 0
    return n, m, sd / math.sqrt(n) if n else 0
if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('entrants', nargs='+'); ap.add_argument('--run', action='store_true'); ap.add_argument('-j', type=int, default=4)
    ap.add_argument('--md'); ap.add_argument('--csv'); ap.add_argument('--check', action='store_true'); x = ap.parse_args()
    if x.run:
        jobs, seen = [], set()
        for e in x.entrants:
            for j in jobs_for(e):  # the same game can be missing for two entrants (A vs anchor B, B vs anchor A)
                me, opp, side, seed, _ = j; k = (me, opp, side, seed) if me <= opp else (opp, me, 'red' if side == 'blue' else 'blue', seed)
                if k not in seen: seen.add(k); jobs.append(j)
        print(f'running {len(jobs)} missing games', flush=True)
        with ThreadPoolExecutor(x.j) as ex:
            for r in ex.map(batch_h2h.run, jobs): print(r.get('me'), r.get('opp'), r.get('side'), r.get('seed'), r.get('winner', r.get('error', '')[:200]), flush=True)
    board = []
    for e in x.entrants:
        rows = score(e); n, m, se = stats([r[3] for r in rows])
        per = {a: stats([r[3] for r in rows if r[0] == a]) for a in ANCHORS}
        wdl = [0, 0, 0]
        for r in rows: wdl[0 if r[3] >= 1000 else 1 if r[3] >= 250 else 2] += 1
        board.append((e, n, m, se, per, wdl))
    board.sort(key=lambda b: -b[2])
    lines = ['| 排名 | 版本 | 局数 | 总分（均值） | 标准误 | 统一胜-未统一-被统一 | ' + ' | '.join(f'vs {a}' for a in ANCHORS) + ' |', '|---|---|---|---|---|---|' + '---|' * len(ANCHORS)]
    for i, (e, n, m, se, per, wdl) in enumerate(board, 1):
        lines.append(f'| {i} | {e} | {n}{"" if n == 48 else " (不全)"} | **{m:.0f}** | ±{se:.0f} | {wdl[0]}-{wdl[1]}-{wdl[2]} | ' + ' | '.join(f'{per[a][1]:.0f}±{per[a][2]:.0f} ({per[a][0]})' for a in ANCHORS) + ' |')
    print('\n'.join(lines))
    if x.check:
        ck = check(board); print(); print(ck); lines += ['', ck]
    if x.md: open(x.md, 'w').write('\n'.join(lines) + '\n')
    if x.csv:
        with open(x.csv, 'w') as f:
            f.write('version,games,score,se,' + ','.join(f'vs_{a},se_{a}' for a in ANCHORS) + ',unif_win,no_unif,unified\n')
            for e, n, m, se, per, wdl in board:
                f.write(f'{e},{n},{m:.1f},{se:.1f},' + ','.join(f'{per[a][1]:.1f},{per[a][2]:.1f}' for a in ANCHORS) + f',{wdl[0]},{wdl[1]},{wdl[2]}\n')
