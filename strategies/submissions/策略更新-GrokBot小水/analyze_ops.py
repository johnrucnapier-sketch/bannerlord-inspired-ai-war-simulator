"""Grok Bot (小水): trigger evidence for v21a-feint / v21b-hunt runs (post-hoc, reads both sides' own JSONL + stderr).
For every game dir runs/grokbot/h2h/<me>-vs-<opp>-<side>-s<seed>-d1680:
  feint:  each FEINT start/arrive/switch -> opponent (own-view) parties inside / guarding the bait city F and the real target T
          on the start, switch and siege days, campaign outcome;
  hunt:   HB lines summed (enemy parties/carts killed, own losses), sorties, opponent GUARD days;
  both:   own vs opponent total military (parties+garrison+militia, healthy+wounded) every 100 days.
Usage: python analyze_ops.py <me> <opp> [--out results-ops/<name>.json]"""
import argparse, gzip, json, math, re, statistics as st
from pathlib import Path
HERE = Path(__file__).resolve().parent; H2H = HERE.parents[2] / 'runs/grokbot/h2h'
def d(a, b): return math.hypot(a['x'] - b['x'], a['y'] - b['y'])
def own_view(path, days):
    """day -> (military, parties hp, party list [(x,y,hp,order)], cities{id:(x,y,nation)})"""
    out = {}; want = set(days)
    for line in gzip.open(path, 'rt'):
        r = json.loads(line); o = (r.get('request') or {}).get('observation')
        if not o or o['hour'] % 24: continue
        day = o['hour'] // 24
        if day not in want or day in out: continue
        n = o['nation']; own = [u for u in o['units'] if u['nation'] == n]
        mil = sum(u['healthy'] + u['wounded'] for u in own if u['kind'] in ('party', 'garrison', 'militia'))
        ps = [(u['x'], u['y'], u['healthy'], (u.get('order') or {})) for u in own if u['kind'] == 'party']
        out[day] = dict(mil=mil, field=sum(p[2] for p in ps), nparty=len(ps), parties=ps,
                        cities={c['id']: (c['x'], c['y'], c.get('nation')) for c in o['cities']}, ncity=sum(c.get('nation') == n for c in o['cities']))
    return out
def at_city(view, cid, r=1500):
    if not view: return None, None
    cx, cy, _ = view['cities'][cid]
    inside = sum(p[2] for p in view['parties'] if math.hypot(p[0] - cx, p[1] - cy) <= r)
    guard = sum(p[2] for p in view['parties'] if p[3].get('gb') == 'guard' and abs(p[3].get('x', -9e9) - cx) < 50 and abs(p[3].get('y', -9e9) - cy) < 50)
    return inside, guard
def game(dirp, side):
    me = 0 if side == 'blue' else 1
    log = (dirp / f'agent-{me}.stderr.log').read_text(errors='replace').splitlines()
    olog = (dirp / f'agent-{1 - me}.stderr.log').read_text(errors='replace').splitlines()
    res = json.load(open(dirp / 'result.json')); rr = res['result'] or {}
    g = dict(seed=res['seed'], side=side, win=None if rr.get('winner') is None else rr['winner'] == me, reason=rr.get('reason'), day=res['hour'] / 24)
    # feints
    fe = []; cur = None
    for ln in log:
        m = re.match(r'd(\d+) FEINT start bait=(\w+) real=(\w+) hp=(\d+)', ln)
        if m: cur = dict(start=int(m[1]), F=m[2], T=m[3], hp=int(m[4])); fe.append(cur); continue
        m = re.match(r'd(\d+) FEINT arrive', ln)
        if m and cur: cur['arrive'] = int(m[1]); continue
        m = re.match(r'd(\d+) FEINT switch .* screen=(\d+)/(\d+) strike=(\d+)', ln)
        if m and cur: cur.update(switch=int(m[1]), screen=int(m[2]), strike=int(m[4])); continue
        m = re.match(r'd(\d+) FEINT->REAL siege bait city (\w+)', ln)
        if m and cur: cur.update(real_switch=int(m[1])); continue
        m = re.match(r'd(\d+) (SIEGE|ABORT march) (\w+)', ln)
        if m and cur and 'outcome' not in cur and m[3] in (cur['T'], cur['F']): cur['siege' if m[2] == 'SIEGE' else 'abort'] = int(m[1]); continue
        m = re.match(r'd\d+\.\. END (\w+) won=(\w+) feint=(\w+)', ln)
        if m and cur and 'outcome' not in cur and m[1] in (cur['T'], cur['F']): cur['outcome'] = m[2] == 'True'; cur['taken'] = m[1]; cur = None
    camp = [re.match(r'd\d+\.\. END (\w+) won=(\w+)', ln) for ln in log]; camp = [m for m in camp if m]
    g['campaigns'] = len(camp); g['campaign_wins'] = sum(m[2] == 'True' for m in camp)
    g['sieges'] = sum(' SIEGE ' in ln for ln in log); g['aborts'] = sum(' ABORT ' in ln for ln in log)
    g['opp_guard_days'] = sum(' GUARD ' in ln for ln in olog)
    gd = {}
    for ln in olog:
        m = re.match(r'd(\d+) GUARD (\[.*\])', ln)
        if m: gd[int(m[1])] = eval(m[2])
    days = set(range(0, int(g['day']) + 1, 100))
    for f in fe:
        for k in ('start', 'switch', 'siege', 'abort'):
            if k in f: days.add(f[k])
    ov = own_view(dirp / f'nation-{1 - me}.jsonl.gz', days); mv = own_view(dirp / f'nation-{me}.jsonl.gz', [x for x in days if x % 100 == 0])
    for f in fe:
        f['opp_guard_bait_days'] = sum(f['F'] in gd.get(x, []) for x in range(f['start'], f.get('switch', f['start']) + 4))
        f['opp_guard_real_days'] = sum(f['T'] in gd.get(x, []) for x in range(f['start'], f.get('siege', f.get('abort', f.get('switch', f['start']))) + 1))
        for k in ('start', 'switch', 'siege', 'abort'):
            if k in f and f[k] in ov:
                f[f'F_in@{k}'], f[f'F_guard@{k}'] = at_city(ov[f[k]], f['F']); f[f'T_in@{k}'], f[f'T_guard@{k}'] = at_city(ov[f[k]], f['T'])
    g['feints'] = fe
    # hunting
    hb = [re.match(r'd(\d+) HB (\w+) foes=(\d+) killed_party=(\d+)/(\d+) killed_cart=(\d+)/(\d+) our_loss=(-?\d+) our_dead=(\d+)/(\d+)', ln) for ln in log]
    hb = [m for m in hb if m]
    g['hunt'] = dict(sorties=sum(' HUNT sortie' in ln for ln in log), battles=sum(m[2] == 'hunt' for m in hb),
                     kill_party=sum(int(m[4]) for m in hb if m[2] == 'hunt'), kill_party_hp=sum(int(m[5]) for m in hb if m[2] == 'hunt'),
                     kill_cart=sum(int(m[6]) for m in hb if m[2] == 'hunt'), kill_cart_hp=sum(int(m[7]) for m in hb if m[2] == 'hunt'),
                     own_loss=sum(max(0, int(m[8])) for m in hb if m[2] == 'hunt'), own_dead=sum(int(m[9]) for m in hb if m[2] == 'hunt'),
                     first_sortie=next((int(re.match(r'd(\d+)', ln)[1]) for ln in log if ' HUNT sortie' in ln), None))
    g['mil'] = {x: [mv.get(x, {}).get('mil'), ov.get(x, {}).get('mil'), mv.get(x, {}).get('ncity'), ov.get(x, {}).get('ncity')] for x in sorted(days) if x % 100 == 0}
    return g
if __name__ == '__main__':
    a = argparse.ArgumentParser(); a.add_argument('me'); a.add_argument('opp'); a.add_argument('--out'); x = a.parse_args()
    gs = []
    for p in sorted(H2H.glob(f'{x.me}-vs-{x.opp}-*-d1680')):
        if not (p / 'result.json').exists(): continue
        side = 'blue' if '-blue-' in p.name[len(x.me):] else 'red'
        try: gs.append(game(p, side))
        except Exception as e: print('skip', p.name, e)
    out = Path(x.out) if x.out else HERE / 'results-ops' / f'{x.me}-vs-{x.opp}.json'
    out.parent.mkdir(exist_ok=True); json.dump(gs, open(out, 'w'), ensure_ascii=False, indent=1)
    fe = [f for g in gs for f in g['feints']]
    sw = [f for f in fe if 'switch' in f]
    print(f"games={len(gs)} W={sum(g['win'] is True for g in gs)} L={sum(g['win'] is False for g in gs)} campaigns={sum(g['campaigns'] for g in gs)} won={sum(g['campaign_wins'] for g in gs)} aborts={sum(g['aborts'] for g in gs)} opp_guard_days={sum(g['opp_guard_days'] for g in gs)}")
    if fe:
        print(f"feints started={len(fe)} switched={len(sw)} real_on_bait={sum('real_switch' in f for f in fe)} outcome_won={sum(f.get('outcome') is True for f in fe)} lost={sum(f.get('outcome') is False for f in fe)}")
        print(f"  bait city guarded (opp GUARD log) in {sum(f['opp_guard_bait_days'] > 0 for f in fe)}/{len(fe)};  real target guarded in {sum(f['opp_guard_real_days'] > 0 for f in fe)}/{len(fe)}")
        for k in ('F_in@start', 'F_in@switch', 'F_guard@switch', 'T_in@start', 'T_in@switch', 'T_in@siege'):
            v = [f[k] for f in fe if f.get(k) is not None]
            if v: print(f"  {k}: mean={st.mean(v):.0f} n={len(v)}")
    hs = [g['hunt'] for g in gs if g['hunt']['sorties']]
    if hs:
        print('hunt totals', {k: sum(h[k] or 0 for h in hs) for k in hs[0] if k != 'first_sortie'})
    for day in (100, 200, 300, 400, 600):
        v = [g['mil'][day] for g in gs if day in g['mil'] and None not in g['mil'][day][:2]]
        if v: print(f"  day{day}: my_mil={st.mean(a for a, b, c, e in v):.0f} opp_mil={st.mean(b for a, b, c, e in v):.0f} my_cities={st.mean(c for a, b, c, e in v):.1f} n={len(v)}")
