"""Grok Bot v23, approach: v22 + famine grace period, staged-rally refills, fresh-capture bandit detail.

Made by GrokBot (小水) for 博 李.  Changes vs v22 (report 08):
  A. GB_FAMDAY (60): no famine risk flags / rescue / convoys before that day unless a city really is at food 0.
     v22 flagged frontier cities on day 6-9 (300k start food < 20 days), sent its new 30-man parties after bandits and
     delayed the first siege; 9 of v22's 10 losses vs v21 had the later first siege (the mirror is a race).
  B. staged rally refill: a roster party with < GB_SREF (15) days of food goes into the base city to refill when the
     city has its refill + 200k to spare, then returns to the staging point (v22: 91 siege party-days hungry vs march).
  C. fresh-capture detail: for GB_FRESH (60) days after a capture, the city's garrison is not drawn for rally top-up or
     new parties, and one free party (GB_FRESHN) clears bandits around it / shadows its village carts.

v22 header: Grok Bot v22, approach: v21 (v20 + 协同清剿) + 断粮预案 (famine / death-spiral contingency).

Made by GrokBot (小水) from 博 李's observation: a city drained by military use stops suppressing bandits, its village
carts die, its food hits 0 and the garrison starves (10%/day).  In practice (reports/07) the main food sink was
different: parties parked in a food-poor city (hunters waiting to refit, p5 patrols coming home empty, hold stacks
after a conquest) each refill up to 30 days of field food (150 x 100 x 30 = 450k) and swallow every cart delivery.
v22 adds (all behind GB_FAM=1, default on):
  1. food watch: per own city, eaters (garrison+militia+parties within 500) x 50/day, pending party refills, bandits /
     enemy parties nearby and village-cart losses (economy events); AT RISK when food - refills/2 < GB_FRISK (20)
     days of consumption or food == 0 (recovers above 2x that).
  2. rescue: (a) food convoys (`dispatch`, up to 940k) from the richest adjacent own city with spare food, escorted
     by the nearest free party; (b) evacuation of free parties with < 5 days of food out of an at-risk city to the
     nearest own city that can feed them; p5 patrols coming home are redirected away from at-risk cities;
     (c) up to GB_FRESC (2) free parties clear bandits around the city and its villages / shadow its carts.
  3. protection: no party creation and no campaign garrison top-up from at-risk cities, rally bases and hunter
     homes avoid them, hold stacks leave an at-risk city whose food is 0.
  4. food-aware hunter home / refit city (needs food for the group's refill, GB_HFOOD 1.2M).
  5. rally staging (GB_STAGE): the observed main killer was a campaign rally of ~15 parties (2300 troops) inside the
     base city: they eat 50/soldier/day from it, auto-refill to 450k each and drain the garrison into the roster, so
     food hits 0 in a day and the militia starves.  Bases prefer cities with >= GB_RFOOD (1.5M) food; if the base
     cannot cover half the roster's refill + 10 days of eating, the rally assembles 700 outside the city instead.
Instrumentation on stderr: FAM risk/ok/convoy/evac/rescue/starve lines and fam counters in STAT.

v21 header: Grok Bot v21 (main version), approach: v20 + 协同清剿 (coordinated patrol hunting) = v21b-hunt promoted.

Made by GrokBot (小水) from 博 李's idea.  Identical logic to v21b-hunt (= ../v21a-feint/agent.py with GB_FEINT=0,
GB_HUNT=1), made standalone with those defaults.  vs v20: 33-0-3 on 18 seeds x 2 colours (std + self-chosen);
3 hunter parties (150 cap each) killed ~29 enemy parties (~1440 troops) and ~133 village carts per game for ~97
own losses.  The feint module (声东击西) is still in the code but off: it pulled v20's guards to the bait city in
70/72 feints yet did not raise the campaign success rate (see reports/06).

v21a header: Grok Bot v21a/v21b (shared code), approach: v20 + two special-operations modules from 博 李's ideas, each behind a flag.

Made by GrokBot (小水).
  GB_FEINT=1  声东击西 (feint): when a campaign rally against target T is complete, the whole stack first marches to a
              bait point GB_BAITD (9000) outside a DIFFERENT enemy city F (12000-40000 from T), stays visible for
              GB_BAITH (36) hours so the opponent's city-guard logic pulls its parties into F, then leaves a screen
              (>= GB_SCREEN 120 troops, max 2 parties) at the bait point to keep the threat alive and strikes T
              with the rest (normal v20 go/no-go at the forward point).  If F itself turns out weak enough, it
              sieges F instead (FEINT->REAL).
  GB_HUNT=1   协同清剿 (patrol hunting): from day GB_HUNTD (40), once we own >= GB_HUNTMIN (9) parties, GB_HUNTK (3)
              parties refilled to 150 form a hunter group at the frontier city closest to the enemy, enter enemy
              territory together and attack visible enemy parties / village carts outside enemy cities when the
              local enemy strength within 6000 is <= GB_HUNTR (0.6) x the group, sweep enemy villages otherwise,
              and return to refit (food / losses / big enemy stack).  Released to the normal logic in the endgame.
Both modules log their decisions to stderr (FEINT ..., HUNT ..., HB ... = one hunter battle result).
v21a-feint = GB_FEINT=1 GB_HUNT=0 (this file's defaults); v21b-hunt = GB_FEINT=0 GB_HUNT=1 (wrapper in ../v21b-hunt).

v20 header: Grok Bot v20, approach: v19 + relief-proof sieges (long enemy-army memory) + early party creation.

Made by GrokBot (小水).  GPT dot's v6 ("Feasible Relief") relieves any besieged city all game long whenever its
reachable field parties reach 1.2x the besiegers; v19 kept sending 300-650-troop stacks that v6's 460-820-troop
relief armies wiped out, then lost the war of attrition.  v20 (1) remembers every enemy party seen in the last
GB_FOEMEM (40) days by id and refuses to launch / siege unless the stack is >= GB_FIELDK (1.0) x that whole
remembered enemy field army (v6 then cannot find a 1.2x relief and does not even try), and (2) creates new
parties from day 0 (the no-creation window only existed for the old day-0 rush).

v19 header: Grok Bot v19, approach: v18 with the opening siege rush disabled (no campaign launches before day 30).

Made by GrokBot (小水).  Against GPT dot's Campaign600 v4 ("Early Relief"), v18's day-0 rush (about 6 parties /
~350 troops besieging the nearest enemy city on day ~6) was always destroyed by v4's opening emergency relief,
and v18 lost 19 of 24 games.  With campaigns held back until day 30 (GB_EARLY=30) the same code went 11-0-1 on
6 seeds x 2 colors.  v19 makes early_day=30 the default; everything else is v18.

v18 header: Grok Bot v18, approach: v17 + lost-rally-base fix (re-base the campaign instead of crashing with KeyError 'garrison').

Made by GrokBot (小水).  GPT dot's Campaign600 v4 report found that Grok v10 raised KeyError('garrison') for 159
consecutive decisions on seed 2009186702 after its rally base c03 was captured (own-city-only fields vanish from
the observation).  The same bug existed in v12-v17.  v18 moves the campaign base to the nearest own,
non-besieged city (preferring cities adjacent to the target) when the base is lost, and aborts if none exists.

v17 header: Grok Bot v17, approach: v16 + endgame doom-stack calls the whole army (no 40000 radius, roster takes every free party up to 18).

Made by GrokBot (小水).  v16 still stalled 11-1 on 2 of 12 blue seeds vs Campaign600: with the enemy down to one
city, most of v16's parties were patrolling more than 40000 from the rally base, so the launch potential never
reached the requirement (or a stale low estimate sized a too-small roster that then aborted at the forward point).
In the endgame (enemy <=3 cities) v17 counts every free party on the map and puts all of them (max 18) in the roster.

v16 header: Grok Bot v16, approach: v14 conservative siege estimate in the opening/midgame + v15 engine-accurate estimate only in the endgame (enemy <=3 cities).

Made by GrokBot (小水).  v15 unified 10 of 11 won games vs Campaign600 by day ~430-580, but on seed 2013042981 its
lower estimate sent a 361-troop stack at c12 on day 75, Campaign600's relief wiped it out, and the empire collapsed.
v16 keeps v10-v14's pessimistic estimate (enemy parties counted at x4 inside the siege) while the enemy still holds
more than 3 cities, and switches to v15's relief-battle model for the last cities.

v15 header: Grok Bot v15, approach: v14 + engine-accurate siege requirement (defender field parties fight a separate relief battle, not the siege).

Made by GrokBot (小水).  v14 still stalled 11-1 vs Campaign600: its last city had garrison 500 + militia 200 and
~1050 field troops parked inside, and v10-v14 counted those parties at x4 inside the siege, asking for 2700-3400
troops (more than 18 parties x 150).  In engine v0.2.0 defender parties do not join a siege; they trigger a relief
field battle at x2.  v15 sizes the stack as H = (S + sqrt(S^2 + 4R^2))/2 (S = siege need of garrison+militia,
R = nearby/remembered enemy field troops) -> about 1900 x margin for that city.

v14 header: Grok Bot v14, approach: v12 + endgame-only whole-empire mobilisation (v13 rules only when the enemy holds <=3 cities) + stale-target floor.

Made by GrokBot (小水) to beat GPT dot's Campaign600 v1 head-to-head.  vs Campaign600, v10 won 22/24 but
unified only 13/24: Campaign600 keeps a full 500 garrison + ~750 field troops around its last city, so
v10/v12 never assembled a big enough stack (keepers per own city, base-only garrison potential).  v13's
mobilisation fixed that but collapsed in the early game.  v14 enables v13's rules (keepers only on
enemy-bordering cities, empire-wide garrison potential, top-up detours, roster up to 18) only in the
endgame, and floors the requirement for stale (fogged) targets at 300 so tiny under-informed rosters
do not launch, abort and leave home cities open to Campaign600's 600-troop campaigns.

v13 header: Grok Bot v13, approach: v12 + whole-empire mobilisation for the doom-stack (no idle keepers, garrison-aware potential, top-up detours).

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
         relief=1.3, rally_hours=240, guard_radius=20000, guard_min=80, guard_ratio=1.3, guard_reach=35000, guard_release=48, foe_days=8, guard=float(os.environ.get('GB_GUARD', 1.0)), hold_days=int(os.environ.get('GB_HOLD', 60)), min_food=10, early_day=int(os.environ.get('GB_EARLY', 30)), endgame_cities=int(os.environ.get('GB_ENDGAME', 3)), stale_floor=int(os.environ.get('GB_SFLOOR', 300)), foe_mem=int(os.environ.get('GB_FOEMEM', 40)), field_k=float(os.environ.get('GB_FIELDK', 1.0)), create_day=int(os.environ.get('GB_CREATE', 0)),
         feint=int(os.environ.get('GB_FEINT', 0)), screen=int(os.environ.get('GB_SCREEN', 120)), bait_dist=int(os.environ.get('GB_BAITD', 9000)),
         bait_hours=int(os.environ.get('GB_BAITH', 36)), feint_min=12000, feint_max=40000, opportunist=int(os.environ.get('GB_OPP', 1)),
         hunt=int(os.environ.get('GB_HUNT', 1)), hunt_k=int(os.environ.get('GB_HUNTK', 3)), hunt_day=int(os.environ.get('GB_HUNTD', 40)),
         hunt_min=int(os.environ.get('GB_HUNTMIN', 9)), hunt_ratio=float(os.environ.get('GB_HUNTR', 0.6)), hunt_carts=int(os.environ.get('GB_HUNTC', 1)), raid=int(os.environ.get('GB_RAID', 0)), rdef=int(os.environ.get('GB_RDEF', 1)),
         fam=int(os.environ.get('GB_FAM', 1)), frisk=float(os.environ.get('GB_FRISK', 20)), fresc=int(os.environ.get('GB_FRESC', 2)), hfood=int(os.environ.get('GB_HFOOD', 1200000)), fconv=int(os.environ.get('GB_FCONV', 1)), stage=int(os.environ.get('GB_STAGE', 1)), rfood=int(os.environ.get('GB_RFOOD', 1500000)), famday=int(os.environ.get('GB_FAMDAY', 60)), sref=float(os.environ.get('GB_SREF', 15)), fresh=int(os.environ.get('GB_FRESH', 60)), freshn=int(os.environ.get('GB_FRESHN', 1)))

class Brain:
    def __init__(self):
        self.endgame = False; self.camp = None; self.seen = {}; self.hold = {}; self.hold_t = {}; self.foe = {}; self.guard = {}; self.threat_t = {}; self.army = {}
        self.ops = {}; self.hunt = None; self.screen = None; self.hb = {}; self.prev = {}; self.visited = {}
        self.risk = {}; self.risk_t = {}; self.conv = {}; self.evac = {}; self.resc = {}; self.escort = {}; self.starve = set(); self.owned = {}; self.freshd = {}; self.fresh = set(); self.finfo = {}
        self.rdef = {}
        self.st = dict(raids=0, raid_def=0, fam_risk=0, fam_convoy=0, fam_evac=0, fam_rescue=0, fam_redirect=0, fam_starve_days=0, fam_srefill=0, fam_fresh=0, missions=0, hb=0, kill_party=0, kill_party_hp=0, kill_cart=0, kill_cart_hp=0, own_loss=0, own_dead=0, lost_battles=0, feints=0, switches=0, opp=0)

    def parts(self, c, o, hour):
        g = c.get('healthy', 50); m = c.get('militia_healthy', 100); e4 = 0; e2 = 0
        if c.get('stale'):
            age = max(0, (hour - c.get('seen', hour)) // 24)
            m = min(200, m + age); g = c.get('healthy', 30); e4 = 20
        else:
            for u in o['units']:
                if u['nation'] == c['nation'] and d(u, c) <= 1000:
                    if u['kind'] == 'party': e4 += u['healthy']
                    elif u['kind'] == 'village_cart': e2 += u['healthy']
        return g, m, e4, e2

    def need(self, c, o, hour, margin=None):
        if not self.endgame:
            g, m, e4, e2 = self.parts(c, o, hour)
            base = int(math.sqrt((g + m + e4 + e2) * (4 * (g + e4) + 2 * (m + e2)) / 2) * (margin or P['margin'])) + P['extra']
            field = sum(h for (h, x, y, t) in self.foe.values() if 1000 < math.hypot(x - c['x'], y - c['y']) < 35000)
            base = max(base, int(P['guard'] * field))
            if c.get('stale'): base = max(base, P['stale_floor'])
            return max(base, self.army_floor())
        # Engine v0.2.0 (external_relief): defender PARTIES never join a siege; they fight a separate relief
        # field battle (x2 both sides, no wall bonus) against the besiegers first.  Garrison x4, militia/carts x2.
        # Win condition per battle ~ H_A*P_A > H_D*P_D.  Siege need S = sqrt(HD*PD/2); relief R costs ~R^2/H,
        # so need H with H - R^2/H >= S  ->  H = (S + sqrt(S^2 + 4R^2)) / 2.
        g, m, e4, e2 = self.parts(c, o, hour)
        S = math.sqrt((g + m + e2) * (4 * g + 2 * m + 2 * e2) / 2)
        field = sum(h for (h, x, y, t) in self.foe.values() if 1000 < math.hypot(x - c['x'], y - c['y']) < 35000)
        R = e4 + P['guard'] * field
        H = (S + math.sqrt(S * S + 4 * R * R)) / 2
        base = int(H * (margin or P['margin'])) + P['extra']
        if c.get('stale'): base = max(base, P['stale_floor'])
        return max(base, self.army_floor())

    def army_floor(self):
        # whole remembered enemy field army (by party id, last GB_FOEMEM days) x GB_FIELDK
        return int(P['field_k'] * sum(v[0] for v in self.army.values()))

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
                self.foe[u['id']] = (u['healthy'], u['x'], u['y'], hour); self.army[u['id']] = (u['healthy'], hour)
        self.foe = {k: v for k, v in self.foe.items() if hour - v[3] < P['foe_days'] * 24}
        self.army = {k: v for k, v in self.army.items() if hour - v[1] < P['foe_mem'] * 24}
        units = {u['id']: u for u in o['units']}
        mine = sorted([c for c in o['cities'] if c.get('nation') == n and 'garrison' in c], key=lambda c: c['id'])
        if not mine: return []
        cmap = {c['id']: c for c in o['cities']}
        if P['fam']: self.food_watch(o, units, mine, hour)
        parties = sorted([u for u in o['units'] if u['nation'] == n and u['kind'] == 'party'], key=lambda u: u['id'])
        ration = o['limits']['field_ration']; cap = o['limits']['clan_party_cap']
        def fdays(u): return u['food'] / max(1, (u['healthy'] + u['wounded']) * ration)
        besieged = {b.get('city') for b in o['battles'] if b.get('city')}
        clan_count = {}
        for u in parties: clan_count[u['clan']] = clan_count.get(u['clan'], 0) + 1
        allp = parties
        self.special(o, cmds, units, allp, mine, cmap, n, hour)
        parties = [u for u in allp if u['id'] not in self.ops]
        clans = list(range(6 * n, 6 * n + 6))
        frontier = [c for c in o.get('frontier_targets', []) if c in cmap]
        pids = {u['id'] for u in parties}
        myids = {c['id'] for c in mine}; self.myids = myids
        frontier = [c for c in frontier if c not in myids]
        enemy_cities = sum(1 for c in o['cities'] if c.get('nation') not in (n, None, -1))
        endgame = enemy_cities <= P['endgame_cities']; self.endgame = endgame
        self.hold = {p: c for p, c in self.hold.items() if p in pids and c in myids and hour - self.hold_t.get(c, 0) < P['hold_days'] * 24}
        # ---- party creation from garrison surplus (any own clan with a free slot)
        for c in mine:
            if c['id'] in besieged or hour < P['create_day'] * 24 or c['id'] in self.risk or c['id'] in getattr(self, 'fresh', ()): continue
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
                base = min(bases, key=lambda m: (m['id'] in self.risk, P['fam'] and m['food'] < P['rfood'], d(m, T)))
                req = self.need(T, o, hour)
                near = sorted([u for u in avail if endgame or d(u, base) < 40000], key=lambda u: d(u, base))
                # keep one patrol per own city out of the campaign (the nearest party to each other city)
                keepers = set()
                for m in mine:
                    if m['id'] == base['id'] or hour < P['rush_days'] * 24: continue
                    if endgame and not any(cmap.get(x, {}).get('nation') not in (n, None) for x in m.get('neighbors', [])): continue
                    cands = [u for u in avail if d(u, m) < 15000 and u['id'] not in keepers]
                    if cands: keepers.add(min(cands, key=lambda u: d(u, m))['id'])
                near = [u for u in near if u['id'] not in keepers][:(18 if endgame else 14)]
                surplus = sum(max(0, units[m['garrison']]['healthy'] - P['keep']) for m in mine if m['id'] not in besieged
                              and (m['id'] == base['id'] or (endgame and d(m, base) < 40000) or (not endgame and any(d(u, m) <= 500 and not u['path'] for u in near))))
                pot = min(sum(u['healthy'] for u in near) + surplus, 150 * len(near)) if endgame else sum(u['healthy'] for u in near) + surplus
                score = (pot >= req, -req - d(base, T) / 500)
                if pot >= req and (best is None or score > best[0]):
                    best = (score, cid, base['id'], near, req, surplus)
            if best:
                _, cid, bid, near, req, surplus = best
                roster = []; s = 0; capx = 0
                for u in near:
                    roster.append(u['id']); s += u['healthy']; capx += 150
                    if not endgame and min(s + surplus, capx) >= req * 1.15 + 60: break
                self.camp = camp = dict(target=cid, base=bid, roster=roster, phase='rally', start=hour, req=req, feint=self.pick_feint(o, cmap, cid, n) if P['feint'] and not endgame else None)
                busy = set(roster)
                print(f"d{hour//24} LAUNCH {cid} from {bid} req={req} roster={len(roster)} hp={s}", file=sys.stderr)
        # ---- campaign execution
        if camp:
            if camp['base'] not in myids:
                cand = [m for m in mine if m['id'] not in besieged] or mine
                adj = [m for m in cand if camp['target'] in m.get('neighbors', [])] or cand
                nb = min(adj, key=lambda m: (d(m, cmap[camp['target']]), m['id']))
                print(f"d{hour//24} REBASE {camp['target']} {camp['base']}->{nb['id']}", file=sys.stderr)
                camp['base'] = nb['id']
            T = cmap[camp['target']]; base = cmap[camp['base']]
            ros = [units[i] for i in camp['roster'] if i in units]
            dx, dy = base['x'] - T['x'], base['y'] - T['y']; L = math.hypot(dx, dy) or 1
            cbase = base  # the city (garrison top-up checks)
            if P['fam'] and P['stage'] and camp['phase'] == 'rally' and not camp.get('stage'):
                f = self.finfo.get(base['id'], {}); troops = sum(u['healthy'] + u['wounded'] for u in ros)
                need = sum(max(0, 150 * 100 * 30 - u['food']) for u in ros) / 2 + 10 * 50 * troops
                if base['id'] in self.risk or base['food'] - f.get('pend', 0) < need:
                    camp['stage'] = {'x': int(base['x'] - dx / L * 700), 'y': int(base['y'] - dy / L * 700)}
                    self.st['fam_stage'] = self.st.get('fam_stage', 0) + 1
                    print(f"d{hour//24} FAM stage rally {camp['target']} outside {base['id']} food={base['food']} need={int(need)}", file=sys.stderr)
            if camp.get('stage') and camp['phase'] == 'rally': base = dict(base, x=camp['stage']['x'], y=camp['stage']['y'])
            fwd = {'x': int(T['x'] + dx / L * P['fwd']), 'y': int(T['y'] + dy / L * P['fwd'])}
            req = self.need(T, o, hour)
            free_ros = [u for u in ros if not u['battle'] and u['id'] not in handled]
            for u in ros:
                if u['army']: cmds.append(dict(type='disband', unit=u['id']))
            if camp['phase'] == 'rally':
                for u in free_ros:
                    self.strength(cmds, u, 150)
                    here = [m for m in mine if d(u, m) <= 500 and m['id'] != base['id'] and m['id'] not in besieged and m['id'] not in self.risk and m['id'] not in self.fresh]
                    if here and not u['path'] and (u.get('order') or {}).get('gb') != 'rally':
                        g = units[here[0]['garrison']]; k = min(g['healthy'] - P['keep'], 150 - u['healthy'] - u['wounded'])
                        if k > 0 and not g['battle']:
                            cmds.append(dict(type='transfer', unit=g['id'], target=u['id'], count=k)); g['healthy'] -= k
                    sup = None
                    if endgame and u['healthy'] + u['wounded'] < 130 and units[base['garrison']]['healthy'] <= P['keep'] + 20:
                        sc = [m for m in mine if m['id'] not in besieged and m['id'] != base['id'] and m['id'] not in self.risk and units[m['garrison']]['healthy'] - P['keep'] >= 40
                              and not units[m['garrison']]['battle'] and d(m, u) < 30000]
                        if sc: sup = min(sc, key=lambda m: d(m, u))
                    if sup is not None and d(u, sup) > 500: self.go(cmds, u, sup, 'supply')
                    elif sup is None and camp.get('stage') and self.stage_refill(u, cbase, camp): self.go(cmds, u, cbase, 'stage_refill')
                    elif sup is None: self.go(cmds, u, base, 'rally')
                # pull extra garrison into roster at the base (auto-service also refills to 150)
                at = [u for u in free_ros if d(u, base) <= 500 and not u['path'] and u['id'] not in camp.get('refill', {})]
                hp = sum(u['healthy'] for u in at)
                if hour % 48 == 0:
                    print(f"d{hour//24} rally {camp['target']} at={hp}/{len(at)} of {len(ros)} req={req} stale={T.get('stale')}", file=sys.stderr)
                if (len(at) == len(free_ros) or hour - camp['start'] > P['rally_hours']) and at:
                    full = len(at) == len(free_ros) and all(u['healthy'] + u['wounded'] >= 140 or units[base['garrison']]['healthy'] <= P['keep'] or camp.get('stage') for u in at)
                    if full and hp < req and len(ros) < (18 if endgame else 16):
                        extra = sorted([u for u in parties if u['id'] not in camp['roster'] and u['id'] not in handled and not u['battle']
                                        and not u['army'] and u['id'] not in self.hold and u['id'] not in self.guard and fdays(u) >= 6
                                        and d(u, base) < 45000], key=lambda u: d(u, base))[:2]
                        if extra:
                            camp['roster'] += [u['id'] for u in extra]
                            for u in extra: self.strength(cmds, u, 150); self.go(cmds, u, base, 'rally')
                            print(f"d{hour//24} GROW {camp['target']} +{len(extra)} hp={hp} req={req}", file=sys.stderr)
                            full = False; camp['start'] = max(camp['start'], hour - P['rally_hours'])
                    if camp.get('feint') and not camp.get('baited') and hp >= req + P['screen'] and all(fdays(u) >= 12 for u in at):
                        camp['phase'] = 'bait'; camp['baited'] = True; camp['roster'] = [u['id'] for u in at]; camp['bait_start'] = hour; camp['bait_t'] = None
                        for u in [x for x in ros if x not in at]: self.strength(cmds, u, P['patrol'])
                        self.st['feints'] += 1
                        print(f"d{hour//24} FEINT start bait={camp['feint']} real={camp['target']} hp={hp} req={req}", file=sys.stderr)
                    elif hp >= req or (full and T.get('stale') and hp >= 0.8 * req):
                        if camp.get('feint') and not camp.get('baited'):
                            print(f"d{hour//24} FEINT skip bait={camp['feint']} real={camp['target']} hp={hp} req={req}", file=sys.stderr)
                        camp['phase'] = 'march'; camp['roster'] = [u['id'] for u in at]
                        for u in [x for x in ros if x not in at]: self.strength(cmds, u, P['patrol'])
                        for u in at: self.go(cmds, u, fwd, 'march')
                    elif hour - camp['start'] > P['rally_hours'] * 2:
                        print(f"d{hour//24} ABORT rally {camp['target']} hp={hp} req={req}", file=sys.stderr)
                        self.finish(cmds, units, cmap, mine, n); self.camp = camp = None
            elif camp['phase'] == 'bait':
                self.bait(o, cmds, camp, ros, free_ros, cmap, mine, T, base, fwd, frontier, hour)
            elif camp['phase'] == 'march':
                arrived = [u for u in free_ros if d(u, fwd) <= 1500 and not u['path']]
                for u in free_ros:
                    if u not in arrived: self.go(cmds, u, fwd, 'march')
                if len(arrived) == len(free_ros) and not T.get('stale'):
                    hp = sum(u['healthy'] for u in arrived)
                    if hp >= self.need(T, o, hour, P['siege_margin']):
                        camp['phase'] = 'siege'
                        print(f"d{hour//24} SIEGE {camp['target']} hp={hp} req={req} e4={self.parts(T, o, hour)[2]} feint={camp.get('feint') if camp.get('baited') else None}", file=sys.stderr)
                        for u in arrived: cmds.append(dict(type='siege', unit=u['id'], target=T['id'], gb='siege'))
                    else:
                        print(f"d{hour//24} ABORT march {camp['target']} hp={hp} req={req} e4={self.parts(T, o, hour)[2]} feint={camp.get('feint') if camp.get('baited') else None}", file=sys.stderr)
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
        if P['fam']:
            for p in [p for p, cid in self.hold.items() if cid in self.risk and cmap[cid]['food'] == 0 and units[p]['food'] < 5 * 100 * max(1, units[p]['healthy'])]:
                print(f"d{hour//24} FAM hold-release {p} {self.hold[p]}", file=sys.stderr); del self.hold[p]
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
        if P['fam']: avail = self.famine_ops(o, cmds, units, parties, avail, mine, cmap, besieged, hour)
        for c in patrol_decide(o, 'p5', available_ids=avail, allow_create=False):
            if P['fam']: c = self.redirect(c, units, mine)
            if c: cmds.append(c)
        out = []; used = set()
        for c in cmds:
            if c['type'] == 'transfer':
                if c['unit'] in used or c['target'] in used: continue
                used.add(c['unit'])
            out.append(c)
        return out[:100]

    # ------------------------------------------------------------------ 声东击西 (feint)
    def pick_feint(self, o, cmap, cid, n):
        T = cmap[cid]
        c = [x for x in o['cities'] if x.get('nation') not in (n, None, -1) and x['id'] != cid
             and P['feint_min'] <= d(x, T) <= P['feint_max'] and min(d(x, m) for m in cmap.values() if m['id'] in self.myids) < 45000]
        if not c: return None
        fr = set(o.get('frontier_targets', []))
        # prefer frontier cities (credible threat, and a possible real target), then the one closest to T
        return min(c, key=lambda x: (x['id'] not in fr, d(x, T)))['id']

    def bait_point(self, F, mine):
        anc = min(mine, key=lambda m: d(m, F)); L = d(anc, F) or 1
        k = min(P['bait_dist'], L * 0.6)
        return {'x': int(F['x'] + (anc['x'] - F['x']) / L * k), 'y': int(F['y'] + (anc['y'] - F['y']) / L * k)}

    def enemy_at(self, o, c, r=1000):
        return sum(u['healthy'] for u in o['units'] if u['nation'] not in (o['nation'], -1) and u['kind'] == 'party' and d(u, c) <= r)

    def bait(self, o, cmds, camp, ros, free_ros, cmap, mine, T, base, fwd, frontier, hour):
        F = cmap.get(camp['feint'])
        if not F or F['id'] in self.myids:
            camp['phase'] = 'march'; return
        bp = self.bait_point(F, mine); camp['bait_xy'] = bp
        arrived = [u for u in free_ros if d(u, bp) <= 1500 and not u['path']]
        for u in free_ros:
            if u not in arrived: self.go(cmds, u, bp, 'bait')
        if camp['bait_t'] is None and (len(arrived) == len(free_ros) or hour - camp['bait_start'] > 120) and arrived:
            camp['bait_t'] = hour; camp['bait_in0'] = self.enemy_at(o, F)
            print(f"d{hour//24} FEINT arrive bait={F['id']} real={T['id']} enemy_in_bait={camp['bait_in0']} near_bait={self.enemy_at(o, F, 20000)}", file=sys.stderr)
        if camp['bait_t'] is None or hour - camp['bait_t'] < P['bait_hours']: return
        hp = sum(u['healthy'] for u in free_ros)
        inF = self.enemy_at(o, F)
        if P['opportunist'] and F['id'] in frontier and not F.get('stale') and hp >= self.need(F, o, hour, P['siege_margin']) and d(F, bp) < 12000:
            self.st['opp'] += 1
            print(f"d{hour//24} FEINT->REAL siege bait city {F['id']} hp={hp} need={self.need(F, o, hour, P['siege_margin'])} enemy_in={inF}", file=sys.stderr)
            camp['target'] = F['id']; camp['phase'] = 'siege'; camp['baited'] = 'real'
            for u in free_ros: cmds.append(dict(type='siege', unit=u['id'], target=F['id'], gb='siege'))
            return
        # screen = the cheapest single party (or pair) that still reaches GB_SCREEN visible troops
        fs = sorted(free_ros, key=lambda u: u['healthy'])
        one = [[u] for u in fs if u['healthy'] >= P['screen']]
        two = sorted([[a, b] for i, a in enumerate(fs) for b in fs[i + 1:] if a['healthy'] + b['healthy'] >= P['screen']], key=lambda p: sum(u['healthy'] for u in p))
        opts = sorted(one[:1] + two[:1], key=lambda p: sum(u['healthy'] for u in p))
        scr = opts[0] if opts and len(fs) > len(opts[0]) else []
        s = sum(u['healthy'] for u in scr)
        rest = [u for u in free_ros if u not in scr]
        if not rest: scr = []; rest = free_ros
        for u in scr: self.ops[u['id']] = 'screen'
        if scr: self.screen = dict(ids=[u['id'] for u in scr], xy=bp, F=F['id'], t=hour)
        camp['roster'] = [u['id'] for u in rest] + [i for i in camp['roster'] if i not in {x['id'] for x in free_ros}]
        camp['phase'] = 'march'; self.st['switches'] += 1
        print(f"d{hour//24} FEINT switch bait={F['id']} real={T['id']} enemy_in_bait={camp.get('bait_in0')}->{inF} near_bait={self.enemy_at(o, F, 20000)} screen={s}/{len(scr)} strike={sum(u['healthy'] for u in rest)}", file=sys.stderr)
        for u in rest: self.go(cmds, u, fwd, 'march')

    # ------------------------------------------------------------------ special ops: screen + 协同清剿 + battle bookkeeping
    def special(self, o, cmds, units, allp, mine, cmap, n, hour):
        pids = {u['id'] for u in allp}
        self.ops = {k: v for k, v in self.ops.items() if k in pids}
        enemy_cities = [c for c in o['cities'] if c.get('nation') not in (n, None, -1)]
        endgame = len(enemy_cities) <= P['endgame_cities']
        ration = o['limits']['field_ration']
        def fdays(u): return u['food'] / max(1, (u['healthy'] + u['wounded']) * ration)
        foes = [u for u in o['units'] if u['nation'] not in (n, -1) and u['kind'] in ('party', 'village_cart')]
        # screen keeps the bait threat alive (visible >= guard_min within 20000 of the bait city)
        if self.screen:
            sc = self.screen; ids = [i for i in sc['ids'] if i in units]
            if not ids or hour - sc['t'] > 15 * 24:
                for i in sc['ids']: self.ops.pop(i, None)
                self.screen = None
            else:
                xy = sc['xy']
                big = sum(u['healthy'] for u in foes if u['kind'] == 'party' and d(u, xy) < 9000)
                my = sum(units[i]['healthy'] for i in ids)
                safe_c = min(mine, key=lambda m: d(m, xy))
                for i in ids:
                    u = units[i]
                    if u['battle']: continue
                    if big > 0.8 * my: self.go(cmds, u, safe_c, 'screen_back')
                    else: self.go(cmds, u, xy, 'screen')
        self.track(o, units, foes, hour)
        if not P['hunt']: return
        H = self.hunt
        if H:
            H['ids'] = [i for i in H['ids'] if i in units]
        if endgame or hour < P['hunt_day'] * 24:
            if H:
                for i in H['ids']: self.ops.pop(i, None)
                print(f"d{hour//24} HUNT release endgame={endgame}", file=sys.stderr); self.hunt = None
            return
        busy = set(self.camp['roster']) if self.camp else set()
        busy |= set(self.guard) | set(self.hold) | set(k for k, v in self.ops.items() if v != 'hunt')
        if not H or not H['ids']:
            if len(allp) < P['hunt_min']: return
            ec = enemy_cities
            if not ec: return
            ok = [m for m in mine if not any(b.get('city') == m['id'] for b in o['battles'])] or mine
            S = self.hunt_home(ok, ec, units)
            cand = sorted([u for u in allp if u['id'] not in busy and not u['battle'] and not u['army']], key=lambda u: (-min(150, u['healthy'] + 0), d(u, S)))[:P['hunt_k']]
            if len(cand) < P['hunt_k']: return
            self.hunt = H = dict(ids=[u['id'] for u in cand], state='form', t=hour, home=S['id'], target=None, wp=None)
            print(f"d{hour//24} HUNT form at {S['id']} ids={len(cand)} hp={sum(u['healthy'] for u in cand)}", file=sys.stderr)
        for i in H['ids']: self.ops[i] = 'hunt'
        hs = [units[i] for i in H['ids']]
        free = [u for u in hs if not u['battle'] and not u['army']]
        for u in hs:
            if u['army'] and not u['battle']: cmds.append(dict(type='disband', unit=u['id']))
            if u.get('refill_target') != 150: cmds.append(dict(type='set_strength', unit=u['id'], target=150))
        home = cmap.get(H['home'])
        if not home or home['id'] not in self.myids or any(b.get('city') == home['id'] for b in o['battles']):
            ok = [m for m in mine if not any(b.get('city') == m['id'] for b in o['battles'])] or mine
            home = self.hunt_home(ok, enemy_cities, units); H['home'] = home['id']
        if P['fam'] and H['state'] in ('form', 'refit') and home['id'] in self.risk:
            ok = [m for m in mine if not any(b.get('city') == m['id'] for b in o['battles'])] or mine
            nh = self.hunt_home(ok, enemy_cities, units)
            if nh['id'] != home['id']:
                print(f"d{hour//24} FAM hunt-home {home['id']}->{nh['id']} food={home['food']}", file=sys.stderr); home = nh; H['home'] = nh['id']
        tot = sum(u['healthy'] for u in hs)
        if H['state'] in ('form', 'refit'):
            # top up the group with free parties if members died
            if len(hs) < P['hunt_k']:
                extra = sorted([u for u in allp if u['id'] not in busy and u['id'] not in H['ids'] and not u['battle'] and not u['army'] and d(u, home) < 40000],
                               key=lambda u: d(u, home))[:P['hunt_k'] - len(hs)]
                for u in extra: H['ids'].append(u['id']); self.ops[u['id']] = 'hunt'
                hs = [units[i] for i in H['ids']]; free = [u for u in hs if not u['battle'] and not u['army']]
            at = [u for u in free if d(u, home) <= 500 and not u['path']]
            for u in free:
                if u not in at: self.go(cmds, u, home, 'hunt_' + H['state'])
            g = units[home['garrison']]
            ready = len(at) == len(hs) and hs and all(fdays(u) >= 20 for u in at) and (all(u['healthy'] >= 130 for u in at) or g['healthy'] <= P['keep'] + 10 or hour - H['t'] > 96)
            if ready and sum(u['healthy'] for u in at) >= 0.45 * 150 * P['hunt_k']:
                H['state'] = 'hunt'; H['t'] = hour; H['target'] = None; self.st['missions'] += 1; H['hp0'] = sum(u['healthy'] for u in at)
                print(f"d{hour//24} HUNT sortie #{self.st['missions']} from {home['id']} hp={sum(u['healthy'] for u in at)}/{len(at)}", file=sys.stderr)
            elif hour - H['t'] > 240 and len(at) == len(hs) and hs:  # garrison can never fill us: go anyway or disband
                if sum(u['healthy'] for u in at) >= 200:
                    H['state'] = 'hunt'; H['t'] = hour; H['target'] = None; self.st['missions'] += 1; H['hp0'] = sum(u['healthy'] for u in at)
                    print(f"d{hour//24} HUNT sortie #{self.st['missions']} (late) hp={sum(u['healthy'] for u in at)}", file=sys.stderr)
                else:
                    for i in H['ids']: self.ops.pop(i, None)
                    self.hunt = None; print(f"d{hour//24} HUNT disband weak hp={sum(u['healthy'] for u in at)}", file=sys.stderr)
            return
        # ---- state hunt
        if not free:
            return
        cx = sum(u['x'] for u in free) / len(free); cy = sum(u['y'] for u in free) / len(free); C = {'x': cx, 'y': cy}
        inb = [u for u in hs if u['battle']]
        if inb:  # pile into the battle
            b = inb[0]
            for u in free:
                if d(u, b) > 800: self.go(cmds, u, b, 'hunt_join')
            return
        back = min(mine, key=lambda m: d(m, C))
        if P['fam']:
            fed = [m for m in mine if m['id'] not in self.risk and m['food'] >= P['hfood'] and not any(b.get('city') == m['id'] for b in o['battles'])]
            if fed and d(min(fed, key=lambda m: d(m, C)), C) < d(back, C) + 25000: back = min(fed, key=lambda m: d(m, C))
        need_days = d(C, back) / (500 * 24) + 4
        danger = sum(u['healthy'] for u in foes if u['kind'] == 'party' and d(u, C) < 10000)
        if min(fdays(u) for u in free) < need_days or tot < 0.6 * H.get('hp0', tot) or danger > 0.8 * tot or hour - H['t'] > 40 * 24:
            H['state'] = 'refit'; H['t'] = hour; H['home'] = back['id'] if back['id'] in self.myids else H['home']
            print(f"d{hour//24} HUNT refit hp={tot} food={min(fdays(u) for u in free):.1f} danger={danger}", file=sys.stderr)
            for u in free: self.go(cmds, u, back, 'hunt_refit')
            return
        def ok_target(t):
            if t['battle'] or t['healthy'] <= 0: return False
            if t['kind'] == 'village_cart' and not P['hunt_carts']: return False
            if any(d(t, c) < 2500 for c in o['cities']): return False
            loc = sum(u['healthy'] for u in foes if u['kind'] == 'party' and d(u, t) < 6000)
            return loc <= P['hunt_ratio'] * tot and d(t, C) < 20000
        rv = H.get('raid')
        if P['raid'] and rv and hour - rv[1] < 30 and not any(t['kind'] == 'party' and not t['battle'] and d(t, C) < 3000 for t in foes):
            v = next((v for v in o['villages'] if v['id'] == rv[0]), None)
            if v and v.get('nation') not in (n, None, -1):
                for u in free:
                    if (u.get('order') or {}).get('type') != 'raid': cmds.append(dict(type='raid', unit=u['id'], target=v['id'], gb='hunt_raid'))
                return
        H['raid'] = None
        cur = next((t for t in foes if t['id'] == H.get('target')), None)
        if not cur or not ok_target(cur):
            ts = [t for t in foes if ok_target(t)]
            cur = min(ts, key=lambda t: (t['kind'] != 'party', d(t, C) - 60 * t['healthy'])) if ts else None
            if cur:
                H['target'] = cur['id']
                print(f"d{hour//24} HUNT chase {cur['kind']} {cur['id']} hp={cur['healthy']} dist={int(d(cur, C))} our={tot}", file=sys.stderr)
        if cur:
            for u in free:
                if (u.get('order') or {}).get('target') != cur['id']:
                    cmds.append(dict(type='attack', unit=u['id'], target=cur['id'], gb='hunt'))
            return
        H['target'] = None
        # sweep enemy villages (patrol routes run village <-> city), nearest unvisited first
        vs = [v for v in o['villages'] if v.get('nation') not in (n, None, -1)]
        if not vs: return
        for v in vs:
            if d(v, C) < 2500: self.visited[v['id']] = hour
        if P['raid'] and danger <= 0.5 * tot:
            rv = [v for v in vs if not v.get('stale') and d(v, C) < 1500 and v.get('disabled_until', 0) <= hour and hour - self.visited.get('raid:' + v['id'], -10**6) > 8 * 24
                  and not any(d(v, c) < 2500 for c in o['cities'])]
            if rv:
                v = min(rv, key=lambda v: d(v, C)); H['raid'] = (v['id'], hour); self.visited['raid:' + v['id']] = hour; self.st['raids'] += 1
                print(f"d{hour//24} HUNT raid {v['id']} pop={v.get('population')} hp={tot}", file=sys.stderr)
                for u in free: cmds.append(dict(type='raid', unit=u['id'], target=v['id'], gb='hunt_raid'))
                return
        wp = cmap.get(H.get('wp')) if False else None
        cand = sorted(vs, key=lambda v: (hour - self.visited.get(v['id'], -10**6) < 10 * 24, d(v, C)))
        v = cand[0]
        if not any(d(v, c) < 2500 for c in o['cities']):
            for u in free: self.go(cmds, u, v, 'hunt_sweep')

    def track(self, o, units, foes, hour):
        """Bookkeeping of battles fought by hunters/screens: enemy units seen in the same battle and our losses."""
        mine_ops = [units[i] for i in self.ops if i in units]
        live = set()
        vis = {u['id']: u for u in o['units'] if u['nation'] not in (o['nation'], -1)}
        for u in mine_ops:
            b = u['battle']
            if not b: continue
            live.add(b)
            rec = self.hb.setdefault(b, dict(start=hour, our={}, foe={}, role=self.ops[u['id']]))
            rec['our'].setdefault(u['id'], self.prev.get(u['id'], u['healthy'] + u['wounded']))
            for e in vis.values():
                if e.get('battle') == b: rec['foe'][e['id']] = (e['kind'], e['healthy'] + e['wounded'])
        for b in [b for b in self.hb if b not in live]:
            rec = self.hb.pop(b)
            alive_foe = {k for k in rec['foe'] if k in vis}
            kp = [v for k, v in rec['foe'].items() if k not in alive_foe and v[0] == 'party']
            kc = [v for k, v in rec['foe'].items() if k not in alive_foe and v[0] == 'village_cart']
            loss = sum(h0 - (units[i]['healthy'] + units[i]['wounded'] if i in units else 0) for i, h0 in rec['our'].items())
            dead = sum(1 for i in rec['our'] if i not in units)
            self.st['hb'] += 1; self.st['kill_party'] += len(kp); self.st['kill_party_hp'] += sum(v[1] for v in kp)
            self.st['kill_cart'] += len(kc); self.st['kill_cart_hp'] += sum(v[1] for v in kc); self.st['own_loss'] += max(0, loss); self.st['own_dead'] += dead
            if dead == len(rec['our']): self.st['lost_battles'] += 1
            print(f"d{hour//24} HB {rec['role']} foes={len(rec['foe'])} killed_party={len(kp)}/{sum(v[1] for v in kp)} killed_cart={len(kc)}/{sum(v[1] for v in kc)} our_loss={loss} our_dead={dead}/{len(rec['our'])}", file=sys.stderr)
        self.prev = {u['id']: u['healthy'] + u['wounded'] for u in o['units'] if u['nation'] == o['nation'] and u['kind'] == 'party'}
        if hour % (24 * 60) == 0:
            print(f"d{hour//24} STAT {json.dumps(self.st)}", file=sys.stderr)

    # ------------------------------------------------------------------ 断粮预案 (famine contingency)
    def city_eaters(self, c, own_units):
        return [u for u in own_units if u['kind'] in ('party', 'garrison', 'militia') and d(u, c) <= 500]

    def food_watch(self, o, units, mine, hour):
        n = o['nation']; own = [u for u in o['units'] if u['nation'] == n]
        bandits = [u for u in o['units'] if u['kind'] == 'bandit']
        econ = o.get('economy') or {}
        self.finfo = {}
        for c in mine:
            eat = self.city_eaters(c, own)
            cons = 50 * sum(u['healthy'] + u['wounded'] for u in eat)
            pend = sum(max(0, (u['healthy'] + u['wounded']) * 100 * 30 - u['food']) for u in eat if u['kind'] == 'party')
            lost = sum(1 for e in (econ.get(c['id']) or {}).get('events', []) if e.get('kind') == 'lost' and hour - e.get('hour', -10**6) < 7 * 24)
            band = sum(1 for b in bandits if d(b, c) < 12000)
            eff = c['food'] - pend / 2
            fd = eff / max(1, cons)
            self.finfo[c['id']] = dict(food=c['food'], cons=cons, pend=pend, lost=lost, band=band, fd=fd)
            was = c['id'] in self.risk
            early = hour < P['famday'] * 24
            if not was and (c['food'] == 0 and cons > 0 or (fd < P['frisk'] and not early)):
                self.risk[c['id']] = hour; self.st['fam_risk'] += 1
                print(f"d{hour//24} FAM risk {c['id']} food={c['food']} cons={cons} pend={pend} fd={fd:.1f} carts_lost7d={lost} bandits={band}", file=sys.stderr)
            elif was and fd >= 2 * P['frisk'] and c['food'] > 0:
                print(f"d{hour//24} FAM ok {c['id']} food={c['food']} fd={fd:.1f} after={(hour - self.risk[c['id']])//24}d", file=sys.stderr)
                del self.risk[c['id']]
            hungry = any(u.get('hungry') and u['healthy'] + u['wounded'] > 0 for u in eat if u['kind'] in ('garrison', 'militia'))
            if hungry and hour % 24 == 0:
                self.st['fam_starve_days'] += 1
                print(f"d{hour//24} FAM starve {c['id']} garrison={units[c['garrison']]['healthy']} food={c['food']}", file=sys.stderr)
        myids = {c['id'] for c in mine}
        for k in [k for k in self.risk if k not in myids]: del self.risk[k]
        for c in mine:
            if c['id'] not in self.owned: self.owned[c['id']] = hour if hour > 0 else -10**6
        for k in [k for k in self.owned if k not in myids]: del self.owned[k]
        self.fresh = {k for k, t in self.owned.items() if hour - t < P['fresh'] * 24}

    def hunt_home(self, ok, ec, units):
        if not P['fam'] or not ec: return min(ok, key=lambda m: min([d(m, e) for e in ec] or [0]))
        def key(m):
            f = self.finfo.get(m['id'], {})
            poor = m['id'] in self.risk or m['food'] < P['hfood']
            return (poor, min(d(m, e) for e in ec) + (0 if not poor else 0))
        best = min(ok, key=key)
        near = min(ok, key=lambda m: min(d(m, e) for e in ec))
        # do not walk more than 30000 further from the front just for food
        if min(d(best, e) for e in ec) > min(d(near, e) for e in ec) + 30000 and near['id'] not in self.risk: return near
        return best

    def can_feed(self, m, need):
        f = self.finfo.get(m['id'])
        return f and m['id'] not in self.risk and m['food'] - f['pend'] - 30 * f['cons'] >= need

    def famine_ops(self, o, cmds, units, parties, avail, mine, cmap, besieged, hour):
        n = o['nation']; avail = set(avail)
        ration = o['limits']['field_ration']
        def fdays(u): return u['food'] / max(1, (u['healthy'] + u['wounded']) * ration)
        risk = [cmap[c] for c in self.risk if c in cmap and c not in besieged]
        # keep earlier assignments alive for a while
        for tab, ttl in ((self.evac, 4 * 24), (self.resc, 3 * 24), (self.escort, 6 * 24)):
            for k in [k for k, v in tab.items() if k not in units or hour - v[1] > ttl or units[k]['battle']]: del tab[k]
        # (a) food convoys from rich adjacent cities
        if P['fconv']:
            carts = {u['id']: u for u in o['units'] if u['nation'] == n and u['kind'] == 'city_cart'}
            for c in sorted(risk, key=lambda c: self.finfo[c['id']]['fd']):
                cv = self.conv.get(c['id'])
                if cv and hour - cv['t'] < 5 * 24: continue
                f = self.finfo[c['id']]
                want = int(min(940000, max(200000, f['pend'] / 2 + 40 * f['cons'] - c['food'])))
                dons = [m for m in mine if m['id'] in c.get('neighbors', []) and m['id'] not in besieged and m['id'] not in self.risk and not m.get('convoy')
                        and units[m['garrison']]['healthy'] >= 20 + P['keep'] and not units[m['garrison']]['battle']]
                dons = [(m, m['food'] - 60000 - self.finfo[m['id']]['pend'] - 40 * self.finfo[m['id']]['cons']) for m in dons]
                dons = [(m, s) for m, s in dons if s >= 200000]
                if not dons: continue
                m, spare = max(dons, key=lambda x: x[1])
                amt = int(min(want, spare, 940000))
                cmds.append(dict(type='dispatch', city=m['id'], destination=c['id'], food=amt))
                self.conv[c['id']] = dict(t=hour, src=m['id'], food=amt); self.st['fam_convoy'] += 1
                print(f"d{hour//24} FAM convoy {m['id']}->{c['id']} food={amt} target_food={c['food']} fd={f['fd']:.1f}", file=sys.stderr)
            # escort: nearest free party shadows each of our city carts heading to an at-risk city
            for cu in carts.values():
                if cu.get('destination') not in self.risk or cu.get('phase') != 'outbound': continue
                if any(v[0] == cu['id'] for v in self.escort.values()): pass
                else:
                    cand = [u for u in parties if u['id'] in avail and u['healthy'] >= 30 and fdays(u) >= 4 and d(u, cu) < 25000]
                    if cand:
                        e = min(cand, key=lambda u: d(u, cu)); self.escort[e['id']] = (cu['id'], hour)
                        print(f"d{hour//24} FAM escort {e['id']} -> cart {cu['id']} to {cu.get('destination')}", file=sys.stderr)
            for pid, (cid, t) in list(self.escort.items()):
                cu = carts.get(cid)
                if not cu or cu.get('phase') != 'outbound': del self.escort[pid]; continue
                avail.discard(pid); u = units[pid]
                bs = [b for b in o['units'] if b['kind'] == 'bandit' and not b['battle'] and d(b, cu) < 5000]
                if bs:
                    b = min(bs, key=lambda b: d(b, cu))
                    if (u.get('order') or {}).get('target') != b['id']: cmds.append(dict(type='attack', unit=pid, target=b['id'], gb='fam_escort'))
                else: self.go(cmds, u, cu, 'fam_escort')
        # (v23) raid defense: an own village with an active enemy raid (v['raid']) -> nearest free parties attack the raider
        if P['rdef']:
            for k in [k for k, v in self.rdef.items() if k not in units or hour - v[1] > 36 or units[k]['battle']]: del self.rdef[k]
            vis = {u['id']: u for u in o['units'] if u['nation'] not in (n, -1)}
            for v in o['villages']:
                r = v.get('raid')
                if v.get('nation') != n or not r: continue
                e = vis.get(r.get('unit'))
                if not e: continue
                have = [k for k, x in self.rdef.items() if x[0] == e['id']]
                hp = sum(units[k]['healthy'] for k in have)
                cand = sorted([u for u in parties if u['id'] in avail and u['id'] not in self.rdef and u['healthy'] >= 20 and d(u, e) < 12000], key=lambda u: d(u, e))
                for u in cand:
                    if hp >= 1.3 * e['healthy'] + 10: break
                    self.rdef[u['id']] = (e['id'], hour); hp += u['healthy']; self.st['raid_def'] += 1
                    print(f"d{hour//24} RAIDDEF {u['id']} hp={u['healthy']} -> raider {e['id']} hp={e['healthy']} at {v['id']} since={r.get('start')}", file=sys.stderr)
            for pid, (eid, t) in list(self.rdef.items()):
                e = vis.get(eid)
                if not e: del self.rdef[pid]; continue
                avail.discard(pid)
                if (units[pid].get('order') or {}).get('target') != eid: cmds.append(dict(type='attack', unit=pid, target=eid, gb='raid_def'))
        # (b) evacuate hungry / empty free parties out of at-risk cities
        for c in risk:
            if self.finfo[c['id']]['food'] > self.finfo[c['id']]['pend'] / 3: continue
            for u in [u for u in parties if u['id'] in avail and d(u, c) <= 500 and fdays(u) < 5 and u['id'] not in self.evac]:
                need = (u['healthy'] + u['wounded']) * 100 * 30
                reach = max(fdays(u), 1.5) * 500 * 24 * 0.9
                dest = [m for m in mine if m['id'] != c['id'] and m['id'] not in besieged and d(m, u) <= reach and self.can_feed(m, need)]
                if not dest: continue
                m = min(dest, key=lambda m: d(m, u)); self.evac[u['id']] = (m['id'], hour); self.st['fam_evac'] += 1
                print(f"d{hour//24} FAM evac {u['id']} hp={u['healthy']} food={fdays(u):.1f}d {c['id']}->{m['id']}", file=sys.stderr)
        for pid, (mid, t) in list(self.evac.items()):
            m = cmap.get(mid)
            if not m or m.get('nation') != n or d(units[pid], m) <= 300: del self.evac[pid]; continue
            avail.discard(pid); self.go(cmds, units[pid], m, 'fam_evac')
        # (c) bandit clearing / cart cover around at-risk cities (+ v23: freshly captured cities, GB_FRESHN parties)
        vil = [v for v in o['villages'] if v.get('nation') == n]
        bandits = [b for b in o['units'] if b['kind'] == 'bandit' and not b['battle']]
        fresh = [cmap[c] for c in self.fresh if c in cmap and c not in besieged and c not in self.risk and self.owned.get(c, 0) > 0]
        for c in risk + fresh:
            if c['id'] not in self.risk and P['freshn'] <= 0: continue
            vs = [v for v in vil if v.get('city') == c['id']]
            pts = [c] + vs
            bs = [b for b in bandits if min(d(b, p) for p in pts) < 8000]
            mycarts = [u for u in o['units'] if u['nation'] == n and u['kind'] == 'village_cart' and u.get('home') in {v['id'] for v in vs} and u.get('phase') != 'idle']
            have = [k for k, v in self.resc.items() if v[0] == c['id']]
            if not bs and not mycarts: continue
            while len(have) < (P['fresc'] if c['id'] in self.risk else P['freshn']):
                cand = [u for u in parties if u['id'] in avail and u['id'] not in self.resc and u['healthy'] >= 30 and fdays(u) >= 5 and d(u, c) < 30000 and d(u, c) > 500]
                if not cand: break
                u = min(cand, key=lambda u: d(u, c)); self.resc[u['id']] = (c['id'], hour); have.append(u['id']); self.st['fam_rescue' if c['id'] in self.risk else 'fam_fresh'] += 1
                print(f"d{hour//24} FAM {'rescue' if c['id'] in self.risk else 'fresh'} {u['id']} hp={u['healthy']} -> {c['id']} bandits={len(bs)} carts={len(mycarts)}", file=sys.stderr)
        for pid, (cid, t) in list(self.resc.items()):
            c = cmap.get(cid)
            if (cid not in self.risk and cid not in self.fresh) or not c or c.get('nation') != n: del self.resc[pid]; continue
            u = units[pid]; avail.discard(pid)
            if fdays(u) < 3: del self.resc[pid]; avail.add(pid); continue
            vs = [v for v in vil if v.get('city') == cid]; pts = [c] + vs
            bs = [b for b in bandits if min(d(b, p) for p in pts) < 8000]
            if bs:
                b = min(bs, key=lambda b: d(b, u))
                if (u.get('order') or {}).get('target') != b['id']: cmds.append(dict(type='attack', unit=pid, target=b['id'], gb='fam_rescue'))
                continue
            mycarts = [x for x in o['units'] if x['nation'] == n and x['kind'] == 'village_cart' and x.get('home') in {v['id'] for v in vs} and x.get('phase') != 'idle']
            if mycarts:
                x = min(mycarts, key=lambda x: d(x, u))
                self.go(cmds, u, x, 'fam_cover')
            else:
                v = min(vs, key=lambda v: d(v, u)) if vs else None
                if v: self.go(cmds, u, v, 'fam_cover')
        return avail

    def stage_refill(self, u, city, camp):
        """v23: a staged-rally party low on food refills inside the base city if the city can spare it."""
        R = camp.setdefault('refill', {})
        cap = (u['healthy'] + u['wounded']) * 100 * 30
        fd = u['food'] / max(1, (u['healthy'] + u['wounded']) * 100)
        if u['id'] in R:
            if u['food'] >= 0.9 * cap or city['food'] < 100000 or d(u, city) <= 500 and fd >= P['sref'] * 1.5: del R[u['id']]; return False
            return True
        if fd >= P['sref']: return False
        f = self.finfo.get(city['id'], {})
        if city['food'] - f.get('pend', 0) - (cap - u['food']) < 200000: return False
        R[u['id']] = 1; self.st['fam_srefill'] += 1
        print(f"d{self.hour//24} FAM srefill {u['id']} food={fd:.1f}d city={city['id']} cfood={city['food']}", file=sys.stderr)
        return True

    def redirect(self, cmd, units, mine):
        """p5 sends a patrol home to its nearest city; if that city is at risk and the patrol needs food, send it to one that can feed it."""
        if cmd.get('type') != 'move' or not cmd.get('patrol_return') or not self.risk: return cmd
        tgt = next((m for m in mine if m['id'] in self.risk and abs(m['x'] - cmd['x']) < 50 and abs(m['y'] - cmd['y']) < 50), None)
        if not tgt: return cmd
        f = self.finfo.get(tgt['id'], {})
        if tgt['food'] - f.get('pend', 0) > 30 * f.get('cons', 0) + 200000: return cmd
        u = units.get(cmd['unit'])
        if not u: return cmd
        fd = u['food'] / max(1, (u['healthy'] + u['wounded']) * 100)
        need = (u['healthy'] + u['wounded']) * 100 * 30
        reach = max(fd, 1.0) * 500 * 24 * 0.9
        alt = [m for m in mine if m['id'] != tgt['id'] and d(m, u) <= reach and self.can_feed(m, need)]
        if not alt: return cmd
        m = min(alt, key=lambda m: d(m, u))
        od = u.get('order') or {}
        self.st['fam_redirect'] += 1
        if od.get('type') == 'move' and abs(od.get('x', -1) - m['x']) < 50 and abs(od.get('y', -1) - m['y']) < 50: return None
        return dict(type='move', unit=u['id'], x=int(m['x']), y=int(m['y']), patrol_return=True, gb='fam_redirect')

    def finish(self, cmds, units, cmap, mine, n):
        camp = self.camp
        if not camp: return
        T = cmap.get(camp['target'])
        print(f"d{(camp.get('start',0))//24}.. END {camp['target']} won={bool(T) and T['id'] in self.myids} feint={camp.get('feint') if camp.get('baited') else None} phase={camp['phase']} d{self.hour//24}", file=sys.stderr)
        if self.screen:
            for i in self.screen['ids']: self.ops.pop(i, None)
            print(f"d{self.hour//24} FEINT screen released", file=sys.stderr); self.screen = None
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
