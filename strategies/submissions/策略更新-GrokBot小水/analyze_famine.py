"""Grok Bot (小水): famine / death-spiral evidence from both sides' own-view JSONL (post-hoc, report 07).
Per game dir runs/grokbot/h2h/<me>-vs-<opp>-<side>-s<seed>-d1680 and per nation (me / opp), sampled daily:
  starve_city_days : own city-days whose garrison or militia is hungry (city food ran out -> 10%/day die)
  starve_field     : party-days hungry outside cities
  starve_dead_est  : sum over hungry units of ceil(size/10) per day (engine rule)
  zero_food_days   : own city-days with food == 0
  risk_days        : own city-days with food-days < RISK (food / (50 * eaters within 500))
  cart_lost        : own village carts that vanished between daily samples while the village stayed ours
  dead_cities      : starvation episodes (>=3 consecutive hungry days) followed by losing the city within 60 days
  bandit_near      : mean number of bandits within 10000 of own cities
plus a list of starvation episodes (city, first/last day, garrison before/after, lost day) with a cause at onset:
  stack  = >= 400 own party troops inside the city at some daily sample in the 10 days before onset (rally / hold /
           hunter refit: they eat 50/soldier/day from the city and auto-refill to 30 days of field food),
  bandit = otherwise >= 2 village carts of that city lost in the last 10 days or >= 2 bandits within 10000,
  other  = neither (e.g. freshly captured city with no villages delivering yet).
Only units with members count as hungry (a 0-man garrison keeps its flag).
Usage: python analyze_famine.py <pattern> [<pattern> ...] [-j N]   (pattern = '<me>-vs-<opp>', writes results-famine/<pattern>.json)"""
import argparse, gzip, json, math, glob, os, re
from multiprocessing import Pool
from pathlib import Path
HERE = Path(__file__).resolve().parent; H2H = HERE.parents[2] / 'runs/grokbot/h2h'
RISK = 15
def sz(u): return u['healthy'] + u['wounded']
def side_stats(path):
    S = dict(starve_city_days=0, starve_field=0, starve_dead_est=0, zero_food_days=0, risk_days=0, cart_lost=0, city_days=0, bandit_near=0.0)
    episodes = {}; open_ep = {}; carts_prev = {}; owner_prev = {}; ndays = 0; lost_log = []; hist = {}
    for line in (gzip.open(path, 'rt') if str(path).endswith('.gz') else open(path)):
        r = json.loads(line); o = (r.get('request') or {}).get('observation')
        if not o or o['hour'] % 24: continue
        day = o['hour'] // 24; n = o['nation']; ndays += 1
        own = [c for c in o['cities'] if c.get('nation') == n and 'food' in c]
        units = {u['id']: u for u in o['units']}
        mine = [u for u in o['units'] if u.get('nation') == n]
        bandits = [u for u in o['units'] if u['kind'] == 'bandit']
        owner = {c['id']: c.get('nation') for c in o['cities']}
        for c in own:
            S['city_days'] += 1
            eaters = [u for u in mine if u['kind'] in ('party', 'garrison', 'militia') and math.hypot(u['x'] - c['x'], u['y'] - c['y']) <= 500]
            cons = 50 * sum(sz(u) for u in eaters)
            if c['food'] == 0: S['zero_food_days'] += 1
            if cons and c['food'] / cons < RISK: S['risk_days'] += 1
            S['bandit_near'] += sum(math.hypot(b['x'] - c['x'], b['y'] - c['y']) <= 10000 for b in bandits)
            hungry = [u for u in eaters if u.get('hungry') and sz(u) > 0]
            hh = hist.setdefault(c['id'], []); hh.append((day, sum(sz(u) for u in eaters if u['kind'] == 'party'))); del hh[:-11]
            g = units.get(c['garrison']) or {}
            if hungry:
                S['starve_city_days'] += 1
                ep = open_ep.get(c['id'])
                if not ep or ep['last'] < day - 2:
                    ps = [u for u in eaters if u['kind'] == 'party']; pt = sum(sz(u) for u in ps)
                    nb = sum(math.hypot(b['x'] - c['x'], b['y'] - c['y']) <= 10000 for b in bandits)
                    cl = sum(1 for dd, cc in lost_log if cc == c['id'] and day - dd <= 10)
                    tags = {}
                    for u in ps: t = (u.get('order') or {}).get('gb') or 'none'; tags[t] = tags.get(t, 0) + 1
                    pmax = max(t for dd, t in hh if day - dd <= 10)
                    cause = 'stack' if pmax >= 400 else 'bandit' if cl >= 2 or nb >= 2 else 'other'
                    ep = dict(city=c['id'], first=day, last=day, garrison0=sz(g) if g else 0, days=0, parties=len(ps), party_troops=pt, party_max10=pmax, tags=tags, bandits=nb, carts_lost10=cl, cause=cause); episodes.setdefault(c['id'], []).append(ep); open_ep[c['id']] = ep
                ep['last'] = day; ep['days'] += 1; ep['garrison1'] = sz(g) if g else 0
        for u in mine:
            if u['kind'] == 'party' and u.get('hungry') and not any(math.hypot(u['x'] - c['x'], u['y'] - c['y']) <= 500 for c in own): S['starve_field'] += 1
            if u.get('hungry') and u['kind'] in ('party', 'garrison', 'militia'): S['starve_dead_est'] += (sz(u) + 9) // 10
        vill = {v['id']: v for v in o['villages']}
        carts = {u['home']: u['id'] for u in mine if u['kind'] == 'village_cart'}
        for vid, cid in carts_prev.items():
            v = vill.get(vid)
            if v and v.get('nation') == n and carts.get(vid) != cid: S['cart_lost'] += 1; lost_log.append((day, v.get('city')))
        carts_prev = carts
        for cid, nat in owner_prev.items():
            if nat == n and owner.get(cid) != n:
                for ep in episodes.get(cid, []):
                    if 'lost' not in ep and ep['first'] <= day <= ep['last'] + 60: ep['lost'] = day
        owner_prev = owner
    eps = [e for es in episodes.values() for e in es if e['days'] >= 3]
    S['bandit_near'] = round(S['bandit_near'] / max(1, S['city_days']), 2)
    for k in ('stack', 'bandit', 'other'): S['ep_' + k] = sum(e['cause'] == k for e in eps)
    S['episodes'] = len(eps); S['dead_cities'] = sum('lost' in e for e in eps); S['episode_list'] = eps
    return S
def game(dirp):
    m = re.search(r'-(blue|red)-s(\d+)-d', dirp.name); side, seed = m[1], int(m[2]); me = 0 if side == 'blue' else 1
    res = json.load(open(dirp / 'result.json')); rr = res['result'] or {}
    out = dict(seed=seed, side=side, win=None if rr.get('winner') is None else rr['winner'] == me, day=round(res['hour'] / 24, 1))
    for who, k in (('me', me), ('opp', 1 - me)):
        f = dirp / f'nation-{k}.jsonl.gz'
        if not f.exists(): f = dirp / f'nation-{k}.jsonl'
        out[who] = side_stats(f) if f.exists() else None
    try: out['engine_starved_total'] = json.load(open(dirp / 'final.save.json'))['stats']['starved']
    except Exception: pass
    return out
if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('patterns', nargs='+'); ap.add_argument('-j', type=int, default=4); a = ap.parse_args()
    (HERE / 'results-famine').mkdir(exist_ok=True)
    with Pool(a.j) as pool:
        for pat in a.patterns:
            dirs = sorted(d for d in H2H.glob(pat + '-*-d1680') if (d / 'result.json').exists() and re.fullmatch(re.escape(pat) + r'-(blue|red)-s\d+-d1680', d.name))
            games = pool.map(game, dirs)
            json.dump(games, open(HERE / 'results-famine' / f'{pat}.json', 'w'), indent=1)
            tot = lambda who, k: sum((g[who] or {}).get(k, 0) for g in games)
            print(pat, len(games), {who: {k: tot(who, k) for k in ('starve_city_days', 'starve_field', 'starve_dead_est', 'zero_food_days', 'risk_days', 'cart_lost', 'episodes', 'ep_stack', 'ep_bandit', 'ep_other', 'dead_cities')} for who in ('me', 'opp')}, flush=True)
