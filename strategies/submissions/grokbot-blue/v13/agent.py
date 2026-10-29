"""Grok Bot v13, approach: v12 + whole-empire mobilisation for the doom-stack (no idle keepers, garrison-aware potential, top-up detours).

Changes vs v12: on seed 1072134541 v12 never launched again after day 526 although it had 1855
troops in parties and ~4400 in garrisons vs a requirement of ~1140: one keeper party was reserved per
own city (10 of 18 parties) and launch potential only counted garrison surplus at the base.  v13 keeps
keepers only for cities bordering an enemy city, counts garrison surplus of own cities within 40000
of the base (capped at 150 per roster party), and lets an under-strength rallying party detour to the
nearest own city with spare garrison to fill up before joining the stack.

v12 header: v10 + capacity-aware campaign roster (late-game doom-stack grows past 3-5 parties).

Changes vs v10: slow unifications came from the LAST red city (garrison+militia ~520, need ~1050):
the roster stopped adding parties once current healthy >= req, but parties cap at 150, so a
5-party roster topped out at 750 and the rally aborted for hundreds of days while 2000+ troops
sat in patrols.  v12 (1) sizes the roster so that sum(min(150, healthy + garrison share)) covers
1.15*req+60, and (2) during a rally, when every rostered party is full but hp < req, pulls the
nearest free parties into the roster (2 per tick, max 16).

v10 header: v9 + pre-emptive city guard (fill threatened cities before the siege).

Changes vs v9: when visible enemy parties gather within 20000 of an own city, nearby
non-campaign parties walk INTO that city until garrison+militia+parties would beat 1.3x the
threat in a siege (parties x4, militia x2 per head).  march judges targets only by
garrison+militia/2, so its expeditions hit a reinforced city and are wiped out; a lost siege
removes the whole attacking stack.  Guards are released 48h after the threat disappears.

v9 header: v8 + relief-aware sieges (remember enemy field parties).

Changes vs v8: the bot remembers every enemy party it has seen in the last `foe_days` days.
march relieves a besieged city with 1.1x the besiegers, and a lost relief battle annihilates the
whole stack, so a campaign only launches / sieges when the stack is also >= `guard` x the
remembered enemy field strength within 35000 of the target.

v8 header: v7 (rush + patrol economy + holding doom-stack) with bug fixes.

Changes vs v7: a frontier city whose stale record still shows our flag is treated as enemy
(v7 could relaunch/"win" the same lost city every tick and park the stack in a hold it did not
own); success is judged by actually owning the city; one transfer per source per tick.

v7 header: early rush + patrol-army economy + doom-stack that HOLDS each conquest.

Changes vs v6: after a successful siege the surviving stack stays inside the captured city for
`hold_days` (refill target 1, so it does not drain the garrison).  march judges a city only by
garrison+militia/2, so its counter-sieges run into the hidden stack (parties fight x4 in a
siege); the stack is also already at the base for the next campaign.

v6 header: early rush + patrol-army economy + campaign doom-stack + strong relief.

Changes vs v5: (1) early rush - in the first 20 days no patrol keepers are held back and roster
parties top up from the garrison of whatever own city they stand in before walking to the base;
(2) a less pessimistic estimate for stale targets plus a scouting march when the rally is full
(final go/no-go is decided on fresh information at the forward point with siege_margin);
(3) launch margin (1.5) and fresh go/no-go siege margin (1.4) are separate parameters;
(4) no new parties are created during the rush window (garrison is kept for the rush top-up).

v5 header: patrol-army economy + campaign doom-stack + strong relief.

Every party that is not on a campaign patrols village sectors (sector logic reused from the
frozen observation-only library aiwar.patrols, style 'p5'), so bandits are killed and carts
arrive -> population and recruits grow.  When the parties near the best frontier target can
reach `margin` x the siege threshold sqrt(H_D*P_D/2), a campaign calls them (refilled to 150 from
garrisons) to the adjacent own city, marches to a point 6000 short of the target and sieges.
Relief: all parties within reach stage 4000 from a besieged own city and attack at 1.3x.
"""
import json, math, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', 'game'))
from aiwar.patrols import decide as patrol_decide

def d(a, b): return math.hypot(a['x'] - b['x'], a['y'] - b['y'])
P = dict(margin=float(os.environ.get('GB_MARGIN', 1.5)), siege_margin=float(os.environ.get('GB_SMARGIN', 1.4)), rush_days=20, extra=20, keep=20, patrol=40, keep_new=60, fwd=6000,
         relief=1.3, rally_hours=240, guard_radius=20000, guard_min=80, guard_ratio=1.3, guard_reach=35000, guard_release=48, foe_days=8, guard=float(os.environ.get('GB_GUARD', 1.0)), hold_days=int(os.environ.get('GB_HOLD', 60)), min_food=10, early_day=int(os.environ.get('GB_EARLY', 0)))

class Brain:
    def __init__(self):
        self.camp = None; self.seen = {}; self.hold = {}; self.hold_t = {}; self.foe = {}; self.guard = {}; self.threat_t = {}

    def defense(self, c, o, hour):
        g = c.get('healthy', 50); m = c.get('militia_healthy', 100); e4 = 0; e2 = 0
        if c.get('stale'):
            age = max(0, (hour - c.get('seen', hour)) // 24)
            m = min(200, m + age); g = c.get('healthy', 30); e4 = 20
        else:
            for u in o['units']:
                if u['nation'] == c['nation'] and d(u, c) <= 1000:
                    if u['kind'] == 'party': e4 += u['healthy']
                    elif u['kind'] == 'village_cart': e2 += u['healthy']
        HD = g + m + e4 + e2; PD = 4 * (g + e4) + 2 * (m + e2)
        return HD * PD

    def need(self, c, o, hour, margin=None):
        base = int(math.sqrt(self.defense(c, o, hour) / 2) * (margin or P['margin'])) + P['extra']
        field = sum(h for (h, x, y, t) in self.foe.values() if 1000 < math.hypot(x - c['x'], y - c['y']) < 35000)
        return max(base, int(P['guard'] * field))

    def go(self, cmds, u, p, tag, **kw):
        od = u.get('order') or {}
        if od.get('type') == 'move' and abs(od.get('x', -1) - p['x']) < 50 and abs(od.get('y', -1) - p['y']) < 50: return
        if d(u, p) <= 300 and not u['path']: return
        cmds.append(dict(type='move', unit=u['id'], x=int(p['x']), y=int(p['y']), gb=tag, **kw))

    def strength(self, cmds, u, t):
        if u.get('refill_target') != t: cmds.append(dict(type='set_strength', unit=u['id'], target=t))

    def decide(self, o):
        n = o['nation']; hour = o['hour']; cmds = []; self.hour = hour
        for u in o['units']:
            if u['nation'] not in (n, -1) and u['kind'] == 'party':
                self.foe[u['id']] = (u['healthy'], u['x'], u['y'], hour)
        self.foe = {k: v for k, v in self.foe.items() if hour - v[3] < P['foe_days'] * 24}
        units = {u['id']: u for u in o['units']}
        mine = sorted([c for c in o['cities'] if c.get('nation') == n and 'garrison' in c], key=lambda c: c['id'])
        if not mine: return []
        cmap = {c['id']: c for c in o['cities']}
        parties = sorted([u for u in o['units'] if u['nation'] == n and u['kind'] == 'party'], key=lambda u: u['id'])
        ration = o['limits']['field_ration']; cap = o['limits']['clan_party_cap']
        def fdays(u): return u['food'] / max(1, (u['healthy'] + u['wounded']) * ration)
        besieged = {b.get('city') for b in o['battles'] if b.get('city')}
        clan_count = {}
        for u in parties: clan_count[u['clan']] = clan_count.get(u['clan'], 0) + 1
        clans = list(range(6 * n, 6 * n + 6))
        frontier = [c for c in o.get('frontier_targets', []) if c in cmap]
        pids = {u['id'] for u in parties}
        myids = {c['id'] for c in mine}; self.myids = myids
        frontier = [c for c in frontier if c not in myids]
        self.hold = {p: c for p, c in self.hold.items() if p in pids and c in myids and hour - self.hold_t.get(c, 0) < P['hold_days'] * 24}
        # ---- party creation from garrison surplus (any own clan with a free slot)
        for c in mine:
            if c['id'] in besieged or hour < P['rush_days'] * 24: continue
            g = units[c['garrison']]
            if g['battle'] or g.get('army'): continue
            src = 'recruits' if c.get('recruits', 0) >= 30 else ('garrison' if g['healthy'] >= P['keep'] + 30 else None)
            if not src: continue
            fc = [k for k in clans if clan_count.get(k, 0) < cap]
            if not fc: break
            k = min(fc, key=lambda k: (k != c['clan'], clan_count.get(k, 0), k))
            cmds.append(dict(type='create', city=c['id'], count=30, clan=k, source=src))
            clan_count[k] = clan_count.get(k, 0) + 1
        # ---- campaign bookkeeping
        camp = self.camp
        if camp:
            camp['roster'] = [i for i in camp['roster'] if i in pids]
            T = cmap.get(camp['target'])
            sieging = any(b.get('city') == camp['target'] for b in o['battles'])
            if not T or T['id'] in myids or camp['target'] not in frontier and not sieging or not camp['roster']:
                self.finish(cmds, units, cmap, mine, n)
                camp = None
        busy = set(camp['roster']) if camp else set()
        # ---- relief (any non-campaign party; campaign parties only if still rallying)
        handled = set()
        for rq in sorted(o.get('relief_requests', []), key=lambda r: r['assault_at']):
            bids = {rq['battle'], rq.get('relief_battle')}
            foes = [u for u in o['units'] if u['nation'] not in (n, -1) and u.get('battle') in bids and u['healthy'] > 0]
            if not foes: continue
            B = sum(u['healthy'] for u in foes); city = cmap[rq['city']]
            engaged = sum(u['healthy'] for u in parties if rq.get('relief_battle') and u['battle'] == rq['relief_battle'])
            pool = [u for u in parties if not u['battle'] and u['id'] not in handled and u['healthy'] >= 15 and fdays(u) >= 4
                    and (u['id'] not in busy or camp['phase'] == 'rally') and d(u, city) < 45000]
            pool.sort(key=lambda u: d(u, city))
            if engaged + sum(u['healthy'] for u in pool) < P['relief'] * B: continue
            team = []; s = engaged
            for u in pool:
                if s >= P['relief'] * B + 30: break
                team.append(u); s += u['healthy']
            others = [m for m in mine if m['id'] != city['id']] or mine
            anc = min(others, key=lambda m: d(m, city)); L = d(anc, city) or 1
            stage = {'x': int(city['x'] + (anc['x'] - city['x']) / L * 4000), 'y': int(city['y'] + (anc['y'] - city['y']) / L * 4000)}
            at = [u for u in team if d(u, stage) <= 1500]
            tgt = max(foes, key=lambda u: u['healthy'])
            handled.update(u['id'] for u in team)
            if engaged + sum(u['healthy'] for u in at) >= P['relief'] * B:
                for u in at:
                    if (u.get('order') or {}).get('target') != tgt['id']:
                        cmds.append(dict(type='attack', unit=u['id'], target=tgt['id'], gb='relief'))
                for u in team:
                    if u not in at: self.go(cmds, u, stage, 'rstage')
            else:
                for u in team: self.go(cmds, u, stage, 'rstage')
            for u in team: self.strength(cmds, u, 150 if u['id'] in busy else P['patrol'])
        # ---- pre-emptive guard of threatened cities
        busy0 = set(camp['roster']) if camp else set()
        foes_vis = [u for u in o['units'] if u['nation'] not in (n, -1) and u['kind'] == 'party' and not u['battle']]
        self.guard = {p: c for p, c in self.guard.items() if p in pids and c in myids and p not in busy0 and p not in handled
                      and hour - self.threat_t.get(c, -999) < P['guard_release']}
        for c in mine:
            if c['id'] in besieged: continue
            thr = sum(u['healthy'] for u in foes_vis if d(u, c) < P['guard_radius'])
            if thr < P['guard_min']: continue
            self.threat_t[c['id']] = hour
            g = units[c['garrison']]['healthy']; m = units.get(c.get('militia'), {}).get('healthy', 0)
            inside = sum(u['healthy'] for u in parties if (d(u, c) <= 1000 and u['id'] not in busy0) or self.guard.get(u['id']) == c['id'])
            def safe(x): return (g + m + x) * (4 * (g + x) + 2 * m) >= 2 * (P['guard_ratio'] * thr) ** 2
            if safe(inside): continue
            cand = sorted([u for u in parties if not u['battle'] and u['id'] not in busy0 and u['id'] not in handled and u['id'] not in self.guard
                           and u['healthy'] >= 10 and d(u, c) < P['guard_reach'] and fdays(u) >= 3], key=lambda u: d(u, c))
            for u in cand:
                if safe(inside): break
                self.guard[u['id']] = c['id']; inside += u['healthy']
        for p, cid in self.guard.items():
            u = units[p]; handled.add(p)
            if u['battle']: continue
            self.strength(cmds, u, 1)
            if d(u, cmap[cid]) > 300: self.go(cmds, u, cmap[cid], 'guard')
        if self.guard and hour % 24 == 0:
            print(f"d{hour//24} GUARD {sorted(set(self.guard.values()))} n={len(self.guard)}", file=sys.stderr)
        # ---- campaign launch
        if not camp and frontier and hour >= P['early_day'] * 24:
            avail = [u for u in parties if not u['battle'] and not u['army'] and u['id'] not in handled and fdays(u) >= 6]
            best = None
            for cid in frontier:
                T = cmap[cid]
                bases = [m for m in mine if m['id'] not in besieged and cid in m.get('neighbors', [])] or [m for m in mine if m['id'] not in besieged]
                if not bases: continue
                base = min(bases, key=lambda m: d(m, T))
                req = self.need(T, o, hour)
                near = sorted([u for u in avail if d(u, base) < 40000], key=lambda u: d(u, base))
                # keep one patrol per own city out of the campaign (the nearest party to each other city)
                keepers = set()
                for m in mine:
                    if m['id'] == base['id'] or hour < P['rush_days'] * 24: continue
                    if not any(cmap.get(x, {}).get('nation') not in (n, None) for x in m.get('neighbors', [])): continue
                    cands = [u for u in avail if d(u, m) < 15000 and u['id'] not in keepers]
                    if cands: keepers.add(min(cands, key=lambda u: d(u, m))['id'])
                near = [u for u in near if u['id'] not in keepers][:14]
                surplus = sum(max(0, units[m['garrison']]['healthy'] - P['keep']) for m in mine if m['id'] not in besieged
                              and (m['id'] == base['id'] or d(m, base) < 40000))
                pot = min(sum(u['healthy'] for u in near) + surplus, 150 * len(near))
                score = (pot >= req, -req - d(base, T) / 500)
                if pot >= req and (best is None or score > best[0]):
                    best = (score, cid, base['id'], near, req, surplus)
            if best:
                _, cid, bid, near, req, surplus = best
                roster = []; s = 0; capx = 0
                for u in near:
                    roster.append(u['id']); s += u['healthy']; capx += 150
                    if min(s + surplus, capx) >= req * 1.15 + 60: break
                self.camp = camp = dict(target=cid, base=bid, roster=roster, phase='rally', start=hour, req=req)
                busy = set(roster)
                print(f"d{hour//24} LAUNCH {cid} from {bid} req={req} roster={len(roster)} hp={s}", file=sys.stderr)
        # ---- campaign execution
        if camp:
            T = cmap[camp['target']]; base = cmap[camp['base']]
            ros = [units[i] for i in camp['roster'] if i in units]
            dx, dy = base['x'] - T['x'], base['y'] - T['y']; L = math.hypot(dx, dy) or 1
            fwd = {'x': int(T['x'] + dx / L * P['fwd']), 'y': int(T['y'] + dy / L * P['fwd'])}
            req = self.need(T, o, hour)
            free_ros = [u for u in ros if not u['battle'] and u['id'] not in handled]
            for u in ros:
                if u['army']: cmds.append(dict(type='disband', unit=u['id']))
            if camp['phase'] == 'rally':
                for u in free_ros:
                    self.strength(cmds, u, 150)
                    here = [m for m in mine if d(u, m) <= 500 and m['id'] != base['id'] and m['id'] not in besieged]
                    if here and not u['path'] and (u.get('order') or {}).get('gb') != 'rally':
                        g = units[here[0]['garrison']]; k = min(g['healthy'] - P['keep'], 150 - u['healthy'] - u['wounded'])
                        if k > 0 and not g['battle']:
                            cmds.append(dict(type='transfer', unit=g['id'], target=u['id'], count=k)); g['healthy'] -= k
                    sup = None
                    if u['healthy'] + u['wounded'] < 130 and units[base['garrison']]['healthy'] <= P['keep'] + 20:
                        sc = [m for m in mine if m['id'] not in besieged and m['id'] != base['id'] and units[m['garrison']]['healthy'] - P['keep'] >= 40
                              and not units[m['garrison']]['battle'] and d(m, u) < 30000]
                        if sc: sup = min(sc, key=lambda m: d(m, u))
                    if sup is not None and d(u, sup) > 500: self.go(cmds, u, sup, 'supply')
                    elif sup is None: self.go(cmds, u, base, 'rally')
                # pull extra garrison into roster at the base (auto-service also refills to 150)
                at = [u for u in free_ros if d(u, base) <= 500 and not u['path']]
                hp = sum(u['healthy'] for u in at)
                if hour % 48 == 0:
                    print(f"d{hour//24} rally {camp['target']} at={hp}/{len(at)} of {len(ros)} req={req} stale={T.get('stale')}", file=sys.stderr)
                if (len(at) == len(free_ros) or hour - camp['start'] > P['rally_hours']) and at:
                    full = len(at) == len(free_ros) and all(u['healthy'] + u['wounded'] >= 140 or units[base['garrison']]['healthy'] <= P['keep'] for u in at)
                    if full and hp < req and len(ros) < 16:
                        extra = sorted([u for u in parties if u['id'] not in camp['roster'] and u['id'] not in handled and not u['battle']
                                        and not u['army'] and u['id'] not in self.hold and u['id'] not in self.guard and fdays(u) >= 6
                                        and d(u, base) < 45000], key=lambda u: d(u, base))[:2]
                        if extra:
                            camp['roster'] += [u['id'] for u in extra]
                            for u in extra: self.strength(cmds, u, 150); self.go(cmds, u, base, 'rally')
                            print(f"d{hour//24} GROW {camp['target']} +{len(extra)} hp={hp} req={req}", file=sys.stderr)
                            full = False; camp['start'] = max(camp['start'], hour - P['rally_hours'])
                    if hp >= req or (full and T.get('stale') and hp >= 0.8 * req):
                        camp['phase'] = 'march'; camp['roster'] = [u['id'] for u in at]
                        for u in [x for x in ros if x not in at]: self.strength(cmds, u, P['patrol'])
                        for u in at: self.go(cmds, u, fwd, 'march')
                    elif hour - camp['start'] > P['rally_hours'] * 2:
                        print(f"d{hour//24} ABORT rally {camp['target']} hp={hp} req={req}", file=sys.stderr)
                        self.finish(cmds, units, cmap, mine, n); self.camp = camp = None
            elif camp['phase'] == 'march':
                arrived = [u for u in free_ros if d(u, fwd) <= 1500 and not u['path']]
                for u in free_ros:
                    if u not in arrived: self.go(cmds, u, fwd, 'march')
                if len(arrived) == len(free_ros) and not T.get('stale'):
                    hp = sum(u['healthy'] for u in arrived)
                    if hp >= self.need(T, o, hour, P['siege_margin']):
                        camp['phase'] = 'siege'
                        print(f"d{hour//24} SIEGE {camp['target']} hp={hp} req={req}", file=sys.stderr)
                        for u in arrived: cmds.append(dict(type='siege', unit=u['id'], target=T['id'], gb='siege'))
                    else:
                        print(f"d{hour//24} ABORT march {camp['target']} hp={hp} req={req}", file=sys.stderr)
                        self.finish(cmds, units, cmap, mine, n); self.camp = camp = None
                elif len(arrived) == len(free_ros) and hour - camp['start'] > P['rally_hours'] * 3:
                    self.finish(cmds, units, cmap, mine, n); self.camp = camp = None
            elif camp['phase'] == 'siege':
                sieging = any(b.get('city') == T['id'] for b in o['battles'])
                if not sieging and all(not u['battle'] for u in ros):
                    if hour - camp.get('siege_t', hour) > 12:
                        self.finish(cmds, units, cmap, mine, n); self.camp = camp = None
                    camp and camp.setdefault('siege_t', hour)
        busy = set(self.camp['roster']) if self.camp else set()
        for p in list(self.hold):
            if p in busy or p in handled: del self.hold[p]
        for p, cid in self.hold.items():
            u = units[p]
            if u['battle']: continue
            self.strength(cmds, u, 1)
            if d(u, cmap[cid]) > 300: self.go(cmds, u, cmap[cid], 'hold')
        busy |= set(self.hold)
        # ---- garrison newly captured / weak frontier cities from idle parties standing in them
        for c in mine:
            if c['id'] in besieged: continue
            g = units[c['garrison']]
            needg = P['keep_new'] - g['healthy'] - g['wounded']
            if needg <= 0 or units.get(c.get('militia'), {}).get('healthy', 0) >= 150: continue
            for u in sorted([u for u in parties if d(u, c) <= 500 and not u['battle'] and u['id'] not in busy and u['healthy'] > 25], key=lambda u: -u['healthy']):
                if needg <= 0: break
                k = min(needg, u['healthy'] - 20)
                if k > 0:
                    cmds.append(dict(type='transfer', unit=u['id'], target=g['id'], count=k)); needg -= k; u['healthy'] -= k
        # ---- everyone else patrols
        avail = {u['id'] for u in parties if u['id'] not in busy and u['id'] not in handled and not u['battle']}
        for c in patrol_decide(o, 'p5', available_ids=avail, allow_create=False):
            cmds.append(c)
        out = []; used = set()
        for c in cmds:
            if c['type'] == 'transfer':
                if c['unit'] in used or c['target'] in used: continue
                used.add(c['unit'])
            out.append(c)
        return out[:100]

    def finish(self, cmds, units, cmap, mine, n):
        camp = self.camp
        if not camp: return
        T = cmap.get(camp['target'])
        print(f"d{(camp.get('start',0))//24}.. END {camp['target']} won={bool(T) and T['id'] in self.myids}", file=sys.stderr)
        if T and T['id'] in self.myids and P['hold_days'] > 0:
            for p in camp['roster']:
                if p in units: self.hold[p] = T['id']
            self.hold_t[T['id']] = self.hour
        self.camp = None

def main():
    sys.stdin.reconfigure(encoding='utf-8'); sys.stdout.reconfigure(encoding='utf-8')
    b = Brain()
    for line in sys.stdin:
        req = json.loads(line)
        try: cmds = b.decide(req['observation'])[:100]
        except Exception:
            import traceback; traceback.print_exc(file=sys.stderr); cmds = []
        print(json.dumps({'protocol_version': 1, 'request_id': req['request_id'], 'commands': cmds}), flush=True)

if __name__ == '__main__': main()
