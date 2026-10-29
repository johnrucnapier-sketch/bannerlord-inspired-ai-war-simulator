"""Campaign600 v4 Early Relief — GPT dot. Observation-only military revision of v1.

World rules are never changed. The inherited economic bootstrap, growth, escort,
P5 patrol and replacement behavior are unchanged for non-mission parties.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import argparse
import json
import math
import sys

ROOT = next(parent for parent in Path(__file__).resolve().parents
            if (parent / 'game/aiwar').is_dir() and (parent / 'freeze/v0.2.0.json').is_file())
for path in (ROOT / 'game', ROOT / 'strategies/reference/v0.2.0'):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.escort_p5_defense_v2_policy import Controller as D2
from scripts.transport_growth_policy import distance
from aiwar.relief import staging_point
from aiwar.navigation import find_route, relief_terrain, travel_hours


@dataclass(frozen=True)
class Config:
    attack_ratio: float = 2.5
    attack_minimum: int = 600
    defense_ratio: float = 1.2
    roster_margin: float = 1.2
    launch_ratio: float = 1.0
    abort_ratio: float = 1.8
    min_party_health: int = 54
    refit_food_days: float = 24.0
    stage_food_days: float = 12.0
    refit_deadline: int = 96
    rally_deadline: int = 240
    tour_deadline: int = 1008
    cooldown_hours: int = 24
    require_switched: bool = True
    max_attack_parties: int = 10
    defense_radius: int = 10000
    siege_margin: float = 1.25
    fresh_siege_margin: float = 1.15
    reinforcement_radius: int = 12000
    guard_radius: int = 26000
    guard_reach: int = 35000
    guard_min_threat: int = 80
    guard_margin: float = 1.2
    guard_release_hours: int = 48
    guard_max_travel_hours: int = 96
    opening_guard: bool = False
    opening_guard_days: int = 25
    opening_guard_minimum: int = 180
    emergency_days: int = 30
    emergency_radius: int = 26000
    emergency_min_threat: int = 200
    emergency_economy_keepers: int = 2
    emergency_max_travel_hours: int = 120
    emergency_clear_hours: int = 24


class Controller(D2):
    def __init__(self, config=None, **overrides):
        super().__init__()
        base = asdict(config) if isinstance(config, Config) else dict(config or {})
        base.update(overrides)
        self.config = Config(**base)
        self.campaign = None
        self.missions = {}
        self.cooldown = 0
        self.serial = 0
        self.guards = {}
        self.guard_ids = set()
        self.guard_covered = set()
        self.opening_city = None

    def siege_strength(self, obs, target, include_nearby=True):
        """Observed defender H*P; no hidden units or engine objects.

        Frozen city defense coefficients are 4 for regulars, 2 for militia/cart
        crews; attackers have 2. Nearby free regulars are conservatively treated
        as if they enter before initiation, not as illegal late siege joiners.
        """
        regular = target.get('healthy', 50)
        light = target.get('militia_healthy', 100)
        radius = self.config.reinforcement_radius if include_nearby else 1000
        for u in obs['units']:
            # A stale friendly flag is not authoritative ownership: attack
            # targets come from frontier_targets minus full own-city records.
            if u['nation'] < 0 or u['nation'] == obs['nation'] or u.get('battle'):
                continue
            if u['kind'] in ('party', 'city_cart') and distance(u, target) <= radius:
                regular += u['healthy']
            elif u['kind'] == 'village_cart' and distance(u, target) <= 1000:
                light += u['healthy']
        return (regular + light) * (4 * regular + 2 * light)

    def attack_requirement(self, obs, target, fresh=False):
        cfg = self.config
        legacy = (cfg.abort_ratio if fresh else cfg.attack_ratio) * (
            target.get('healthy', 50) + target.get('militia_healthy', 100) / 2)
        margin = cfg.fresh_siege_margin if fresh else cfg.siege_margin
        observed = margin * math.sqrt(self.siege_strength(obs, target) / 2)
        return max(0 if fresh else cfg.attack_minimum, math.ceil(legacy), math.ceil(observed))

    @staticmethod
    def guard_requirement(garrison, militia, threat, margin):
        # Solve (G+D+M)*(4*(G+D)+2*M) >= 2*(margin*A)^2.
        threshold = 2 * (margin * threat) ** 2
        regular = max(0, math.ceil((-3 * militia + math.sqrt(militia ** 2 + 4 * threshold)) / 4))
        return max(0, regular - garrison)

    def plan_guards(self, obs):
        """Reserve a complete, timely city defense before battle begins.

        No replacements, population model, escort routine or growth method is
        changed. Existing D1 economy sees guard reservations through missions.
        Unaffected homes keep a free economic squad. Unreachable/late/underfed
        troops never count toward a promised defense, and partial reinforcements
        are not sent into an already initiated siege.
        """
        cfg = self.config
        n, hour = obs['nation'], obs['hour']
        cities = {c['id']: c for c in obs['cities'] if c['nation'] == n and 'recruits' in c}
        own = {u['id']: u for u in obs['units'] if u['nation'] == n}
        parties = {uid: u for uid, u in own.items() if u['kind'] == 'party'}
        blocked = {b.get('city') for b in obs.get('battles', []) if b.get('city')}
        blocked |= {r['city'] for r in obs.get('relief_requests', [])}
        homes = {uid: cid for (cid, _), uid in self.assigned.items() if uid in parties and cid in cities}
        for uid, u in parties.items():
            if uid not in homes and cities:
                homes[uid] = min(cities.values(), key=lambda c: (distance(u, c), c['id']))['id']
        homes.update({uid: r['home'] for uid, r in self.guards.items() if uid in parties and r['home'] in cities})
        threats = {}
        for u in obs['units']:
            if u['kind'] != 'party' or u['nation'] < 0 or u['nation'] == n or u['healthy'] <= 0 or u.get('battle') or not cities:
                continue
            # One visible force is assigned to its nearest own city, never
            # counted independently against several simultaneous guard plans.
            city = min(cities.values(), key=lambda c: (distance(u, c), c['id']))
            if distance(u, city) <= cfg.guard_radius:
                threats.setdefault(city['id'], []).append(u)
        threats = {cid: es for cid, es in threats.items() if sum(u['healthy'] for u in es) >= cfg.guard_min_threat}
        opening = None
        opening_homes = set()
        if cfg.opening_guard and hour < cfg.opening_guard_days * 24:
            if self.opening_city is None:
                frontier = set(obs.get('frontier_targets', []))
                exposed = [c for c in cities.values() if frontier.intersection(c.get('neighbors', []))]
                if exposed:
                    self.opening_city = min(exposed, key=lambda c: (
                        -sum(cid in cities for cid in c.get('neighbors', [])), c['id']))['id']
            opening = cities.get(self.opening_city)
            if opening and opening['id'] not in blocked:
                nearby = sorted([c for c in cities.values() if c['id'] != opening['id']
                                 and c['id'] in opening.get('neighbors', [])],
                                key=lambda c: (bool(set(c.get('neighbors', [])).intersection(obs.get('frontier_targets', []))), distance(c, opening), c['id']))[:3]
                opening_homes = {opening['id']} | {c['id'] for c in nearby}
            else:
                opening = None
        retargeted = bool(opening and threats and opening['id'] not in threats)
        opening_origin = opening['id'] if opening else None
        if retargeted:
            opening = None
        commands = []
        next_guards = {}
        self.guard_covered = set()

        def release(uid, record, reason):
            u = parties[uid]
            if u.get('battle'):
                next_guards[uid] = record
                return
            target = max(self.targets.get(uid, 27), record['restore_target'], u.get('reserve_refill_target', 0))
            if u.get('refill_target') != target:
                commands.append(dict(type='set_strength', unit=uid, target=target))
            if cities:
                home = record['home'] if record['home'] in cities else min(cities.values(), key=lambda c: (distance(u, c), c['id']))['id']
                self.missions[uid] = dict(home=home, phase='return', restore_economy_target=target)
            self.war_events.append(dict(hour=hour, event='guard_release', unit=uid, city=record['city'], reason=reason))

        # Keep a short fog/clear hysteresis; battle participants remain reserved
        # until the engine releases them, but no guard command can late-join.
        for uid, record in self.guards.items():
            if uid not in parties:
                continue
            cid = record['city']
            if cid in threats or (opening and cid == opening['id']):
                record['last_seen'] = hour
            if cid not in cities:
                release(uid, record, 'city_lost')
            elif retargeted and cid == opening_origin:
                release(uid, record, 'visible_threat_retargeted')
            elif parties[uid].get('battle'):
                next_guards[uid] = record
            elif cid in blocked:
                release(uid, record, 'siege_already_started')
            elif hour - record['last_seen'] >= cfg.guard_release_hours:
                release(uid, record, 'threat_clear')
            else:
                next_guards[uid] = record

        plans = []
        for cid, es in threats.items():
            if cid in blocked:
                continue
            city = cities[cid]
            g = own.get(city['garrison'], {})
            m = own.get(city.get('militia'), {})
            required = self.guard_requirement(g.get('healthy', 0), m.get('healthy', 0),
                sum(u['healthy'] for u in es), cfg.guard_margin)
            # Straight-line fastest travel is a conservative lower bound for the
            # enemy; own ETA uses the released terrain/pathfinding estimator.
            eta = min(max(0, distance(u, city) - 1000) / obs['speeds']['army' if u.get('army') else 'party'] for u in es)
            plans.append((eta, cid, required))
        if opening and opening['id'] not in threats:
            plans.append((cfg.guard_max_travel_hours + 12, opening['id'], cfg.opening_guard_minimum))
        for enemy_eta, cid, required in sorted(plans):
            city = cities[cid]
            existing = {uid for uid, r in next_guards.items() if r['city'] == cid and not parties[uid].get('battle')}
            candidates = []
            for uid, u in parties.items():
                if u.get('battle') or u.get('army') or u['healthy'] < 10 or distance(u, city) > cfg.guard_reach:
                    continue
                if opening and cid == opening['id'] and cid not in threats and homes.get(uid) not in opening_homes:
                    continue
                if uid in next_guards and uid not in existing:
                    continue
                mission = self.missions.get(uid)
                if mission and mission['phase'] not in ('return',) and not (
                        self.campaign and not self.campaign['launched'] and mission['phase'] in ('refit', 'stage')):
                    continue
                inside = distance(u, city) <= 500
                eta = 0 if inside else travel_hours(obs['terrain'], u, city, obs['speeds'], max_hours=cfg.guard_max_travel_hours)
                if eta is None or (not inside and eta + 6 >= enemy_eta):
                    continue
                food_days = u['food'] / max(1, (u['healthy'] + u['wounded']) * obs['limits']['field_ration'])
                if food_days < eta / 24 + 2 and not (inside and city.get('food', 0) >= 2 * (u['healthy'] + u['wounded']) * obs['limits']['field_ration']):
                    continue
                opening_priority = 0
                if opening and cid == opening['id'] and cid not in threats:
                    home = cities[homes[uid]]
                    opening_priority = 0 if home['id'] == cid else 1 + bool(set(home.get('neighbors', [])).intersection(obs.get('frontier_targets', [])))
                candidates.append((uid not in existing, opening_priority, eta, -u['healthy'], uid))
            selected = []
            total = 0
            for _, _, eta, _, uid in sorted(candidates):
                if total >= required:
                    break
                home = homes[uid]
                # Guards and existing campaigns share the same rear-coverage
                # budget. A currently threatened home's local troops may stay.
                if home not in threats:
                    free = [pid for pid in parties if homes.get(pid) == home and not parties[pid].get('battle')
                            and not parties[pid].get('army') and pid not in self.missions and pid not in next_guards and pid not in selected]
                    if uid not in existing and len(free) < (1 if uid in self.missions else 2):
                        continue
                selected.append(uid)
                total += parties[uid]['healthy']
                if total >= required:
                    break
            if total < required:
                # An already-present formation may win the actual battle even
                # when no extra troop can provide the preferred safety margin.
                # Do not abandon such a defense merely for missing that margin.
                present = sum(parties[uid]['healthy'] for uid in existing if distance(parties[uid], city) <= 1000)
                es = threats.get(cid, [])
                g = own.get(city['garrison'], {})
                m = own.get(city.get('militia'), {})
                actual_need = self.guard_requirement(g.get('healthy', 0), m.get('healthy', 0), sum(u['healthy'] for u in es), 1.05)
                if es and present >= actual_need:
                    self.guard_covered.add(cid)
                    continue
                # Do not feed a losing defense one small arrival at a time.
                for uid in existing:
                    record = next_guards.pop(uid)
                    release(uid, record, 'insufficient_timely_force')
                continue
            self.guard_covered.add(cid)
            for uid in selected:
                if uid not in next_guards:
                    next_guards[uid] = dict(city=cid, home=homes[uid], last_seen=hour,
                        restore_target=self.targets.get(uid, 27))
                    self.war_events.append(dict(hour=hour, event='guard_assign', unit=uid, city=cid,
                        required=required, committed_healthy=total, enemy_eta_hours=enemy_eta))
                # Reclaim an unlaunched/refitting campaign member rather than
                # letting both planners issue conflicting orders for it.
                self.missions.pop(uid, None)
        for uid, record in next_guards.items():
            u = parties[uid]
            if u.get('battle') or record['city'] not in cities or record['city'] in blocked:
                continue
            city = cities[record['city']]
            guard_refill = max(1, u.get('reserve_refill_target', 0))
            if u.get('refill_target') != guard_refill:
                commands.append(dict(type='set_strength', unit=uid, target=guard_refill))
            if distance(u, city) > 500:
                order = u.get('order') or {}
                if order.get('type') != 'move' or order.get('x') != city['x'] or order.get('y') != city['y']:
                    commands.append(dict(type='move', unit=uid, x=city['x'], y=city['y'], campaign_phase='city_guard'))
            elif u.get('path') or u.get('order'):
                commands.append(dict(type='stop', unit=uid))
        self.guards = next_guards
        self.guard_ids = set(next_guards)
        return commands

    def early_threats(self, obs):
        """Public early approaching/besieging forces; each approaches one city."""
        if obs['hour'] >= self.config.emergency_days * 24:
            return set()
        cities = {c['id']: c for c in obs['cities'] if c['nation'] == obs['nation'] and 'recruits' in c}
        by_battle = {r[b]: r['city'] for r in obs.get('relief_requests', [])
                     for b in ('battle', 'relief_battle') if r.get(b)}
        health = {}
        for u in obs['units']:
            if u['kind'] != 'party' or u['nation'] < 0 or u['nation'] == obs['nation'] or u['healthy'] <= 0 or not cities:
                continue
            cid = by_battle.get(u.get('battle'))
            if cid is None and not u.get('battle'):
                city = min(cities.values(), key=lambda c: (distance(u, c), c['id']))
                if distance(u, city) <= self.config.emergency_radius:
                    cid = city['id']
            if cid in cities:
                health[cid] = health.get(cid, 0) + u['healthy']
        return {cid for cid, h in health.items() if h >= self.config.emergency_min_threat}

    def military(self, obs):
        # The original campaign algorithm sees only its own phase vocabulary.
        # Guard reservations are restored afterwards for unchanged D1 economy.
        self.missions = {uid: m for uid, m in self.missions.items() if m.get('role') != 'guard'}
        self.emergency_targets = self.early_threats(obs)
        if self.emergency_targets:
            # Pool early mobile defense instead of splitting it between a small
            # city guard and a separate relief roster. Already engaged guards
            # cannot be detached; everybody else may be reclaimed below.
            own = {u['id']: u for u in obs['units'] if u['nation'] == obs['nation']}
            retained = {}
            guard_commands = []
            for uid, r in self.guards.items():
                if uid not in own:
                    continue
                if own[uid].get('battle'):
                    retained[uid] = r
                else:
                    self.missions[uid] = dict(home=r['home'], phase='return',
                        restore_economy_target=r['restore_target'])
            self.guards = retained
            self.guard_ids = set(retained)
            self.guard_covered = set()
        else:
            guard_commands = self.plan_guards(obs)
        commands = self.campaign_military(obs)
        for uid, r in self.guards.items():
            self.missions[uid] = dict(home=r['home'], phase='guard', role='guard', guard_city=r['city'])
        self.issued_military_commands = self.issued_military_commands or bool(guard_commands) or bool(self.guards)
        return guard_commands + commands

    def campaign_military(self, obs):
        released_mission = False
        cfg = self.config
        n, hour = obs['nation'], obs['hour']
        commands = []
        cities = {c['id']: c for c in obs['cities']
                  if c['nation'] == n and 'recruits' in c}
        own = {u['id']: u for u in obs['units'] if u['nation'] == n}
        parties = {uid: u for uid, u in own.items() if u['kind'] == 'party'}
        enemies = [u for u in obs['units']
                   if u['nation'] >= 0 and u['nation'] != n and u['kind'] == 'party']
        allcities = {c['id']: c for c in obs['cities']}
        alerts = {a['city']: a for a in obs.get('relief_requests', [])}
        blocked = set(alerts)
        ration = obs['limits']['field_ration']
        self.missions = {uid: m for uid, m in self.missions.items() if uid in parties}
        self.tasks = []  # Inherited D2 task manager is deliberately not used.
        emergency_targets = self.early_threats(obs)

        def food_days(u):
            return u['food'] / max(1, (u['healthy'] + u['wounded']) * ration)

        def move(u, point, **meta):
            if point is None:
                return
            cmd = dict(type='move', unit=u['id'], x=point['x'], y=point['y'], **meta)
            if cmd.get('relief_action') == 'wait':
                city = cities.get(cmd.get('relief_city'))
                if city and distance(u, city) < 2500 and find_route(
                        relief_terrain(obs['terrain'], city, u), u,
                        point['x'], point['y']) is None:
                    cmd.pop('relief_action')
            if any((u.get('order') or {}).get(k) != v for k, v in cmd.items()):
                commands.append(cmd)

        disbanded = set()

        def disband(u):
            if u.get('army') and not u['battle'] and u['army'] not in disbanded:
                commands.append(dict(type='disband', unit=u['id']))
                disbanded.add(u['army'])

        def finish(reason):
            if self.campaign:
                self.war_events.append(dict(hour=hour, event='campaign_end',
                    kind=self.campaign['kind'], task=self.campaign['serial'], reason=reason))
            for uid, m in self.missions.items():
                m['phase'] = 'return'
                disband(parties[uid])
            self.campaign = None
            self.cooldown = hour + cfg.cooldown_hours

        def threat_units(cid):
            c = cities.get(cid)
            if not c:
                return []
            alert = alerts.get(cid, {})
            bids = {alert.get('battle'), alert.get('relief_battle')} - {None}
            radius = cfg.emergency_radius if cid in emergency_targets else cfg.defense_radius
            return [u for u in enemies if u['healthy'] > 0 and
                    (u['battle'] in bids or (not u['battle'] and distance(u, c) <= radius))]

        def defense_need(cid):
            return max(60, math.ceil(sum(u['healthy'] for u in threat_units(cid)) * cfg.defense_ratio))

        def attack_need(target):
            return self.attack_requirement(obs, target)

        # One global force avoids reserving two independent defense rosters for
        # the same visible enemy army. Preserve an active campaign until a real
        # completion, resource failure or deadline rather than momentary fog.
        p = self.campaign
        if p and emergency_targets and not p.get('emergency') and not any(parties[uid]['battle'] for uid in self.missions):
            finish('early_relief_priority')
            self.cooldown = hour
            p = None
        if p:
            active = [parties[uid] for uid, m in self.missions.items() if m['phase'] != 'return']
            field = [u for u in active if self.missions[u['id']]['phase'] == 'field']
            target = allcities.get(p['target'])
            if p['kind'] == 'defense' and threat_units(p['target']):
                p['last_seen'] = hour
            # A stale remembered friendly flag is not current ownership. Only
            # the full own-city records certify possession; frontier_targets
            # remains the observation's authoritative siege-eligibility list.
            complete = (p['kind'] == 'attack' and p['target'] in cities)
            complete |= (p['kind'] == 'defense' and p['target'] not in cities)
            clear = (p['kind'] == 'defense' and p['target'] not in alerts
                     and hour - p['last_seen'] >= (cfg.emergency_clear_hours if p.get('emergency') else 96))
            out_of_food = field and min(food_days(u) for u in field) < 5
            expired = hour - p['start'] >= cfg.tour_deadline or (p.get('emergency') and hour >= cfg.emergency_days * 24)
            weak = field and sum(u['healthy'] for u in field) < max(40, p['required'] * .55)
            if not any(u['battle'] for u in active) and (
                    not active or complete or clear or out_of_food or expired or weak):
                finish('complete' if complete else 'clear' if clear else 'low_food'
                       if out_of_food else 'deadline' if expired else 'depleted')

        # Return to the nearest usable city, not necessarily a distant historical
        # hometown. A captured home must not strand a living party forever.
        for uid, m in list(self.missions.items()):
            u = parties[uid]
            if u['battle']:
                continue
            if m['home'] not in cities:
                safe = [c for c in cities.values() if c['id'] not in blocked]
                if safe:
                    m['home'] = min(safe, key=lambda c: (distance(u, c), c['id']))['id']
                if m['phase'] != 'field':
                    m['phase'] = 'return'
            if m['phase'] != 'return':
                continue
            disband(u)
            if u['army']:
                continue
            safe = [c for c in cities.values() if c['id'] not in blocked]
            if not safe:
                continue
            c = min(safe, key=lambda c: (distance(u, c), c['id']))
            m['home'] = c['id']
            if distance(u, c) > 500:
                move(u, c, campaign_phase='cloud_return')
            else:
                self.targets[uid] = max(m.get('restore_economy_target', 57), u.get('reserve_refill_target', 0))
                self.returning.pop(uid, None)
                self.away.pop(uid, None)
                del self.missions[uid]
                released_mission = True

        # Make a new roster only from genuinely unreserved, funded formations.
        if self.campaign is None and cities and hour >= self.cooldown:
            threats = [c for c in cities.values() if c['id'] not in self.guard_covered and threat_units(c['id'])]
            threats.sort(key=lambda c: (c['id'] not in alerts,
                alerts.get(c['id'], {}).get('assault_at', hour + 9999),
                -sum(u['healthy'] for u in threat_units(c['id'])), c['id']))
            kind, target, stage = None, None, None
            emergency = False
            if threats:
                target = threats[0]
                kind = 'defense'
                emergency = target['id'] in emergency_targets
                alert = alerts.get(target['id'])
                if emergency and alert is None:
                    alert = dict(city=target['id'], x=target['x'], y=target['y'])
                stage = staging_point(obs, alert, list(cities.values())) if alert else target
                required = defense_need(target['id'])
            else:
                options = [c for c in obs['cities'] if c['id'] not in cities
                           and c['id'] in obs.get('frontier_targets', [])]
                pairs = []
                for t in options:
                    bases = [c for c in cities.values() if t['id'] in c['neighbors']
                             and c['id'] not in blocked]
                    if bases:
                        base = min(bases, key=lambda c: (distance(c, t), c['id']))
                        pairs.append((attack_need(t), distance(base, t), t['id'], t, base))
                if pairs:
                    _, _, _, target, stage = min(pairs, key=lambda row: row[:3])
                    kind, required = 'attack', attack_need(target)
            if target and stage:
                candidates = []
                for c in sorted(cities.values(), key=lambda c: c['id']):
                    if c['id'] in blocked and not emergency:
                        continue
                    if kind == 'attack' and cfg.require_switched and c['id'] not in self.switched:
                        continue
                    ids = [uid for (cid, slot), uid in sorted(self.assigned.items())
                           if cid == c['id'] and uid in parties]
                    if len(ids) < (1 if emergency else 2):
                        continue
                    g = own.get(c['garrison'])
                    spare = g['healthy'] if g and not g['battle'] and distance(g, c) <= 500 else 0
                    spare -= sum(max(0, self.targets.get(uid, 27) - parties[uid]['healthy']) for uid in ids)
                    taken = sum(uid in self.guard_ids or uid in self.missions for uid in ids)
                    for uid in sorted(ids, key=lambda uid: (-parties[uid]['healthy'], uid)):
                        u = parties[uid]
                        occupied = uid in self.missions and not (emergency and self.missions[uid]['phase'] == 'return')
                        if occupied or uid in self.guard_ids or u['battle'] or u['army'] or (not emergency and taken >= len(ids) - 1):
                            continue
                        if u['healthy'] < (cfg.min_party_health if kind == 'attack' else 20):
                            continue
                        # Defense uses current field troops immediately. Offense
                        # can refill at home, but never counts imaginary soldiers.
                        extra = min(max(0, spare), max(0, 150 - u['healthy'] - u['wounded'])) if kind == 'attack' else 0
                        expected = u['healthy'] + extra
                        spare -= extra
                        taken += 1
                        distance_cost = (distance(u, c) + distance(c, stage)) if kind == 'attack' else distance(u, stage)
                        if emergency:
                            terrain = relief_terrain(obs['terrain'], target, u)
                            if distance(u, target) < 2500 and find_route(terrain, u, stage['x'], stage['y']) is None:
                                terrain = obs['terrain']  # Same safe-egress fallback as movement.
                            window = min(cfg.emergency_max_travel_hours, max(0, alerts[target['id']]['assault_at'] - hour) + 24) if target['id'] in alerts else cfg.emergency_max_travel_hours
                            eta = travel_hours(terrain, u, stage, obs['speeds'], max_hours=window)
                            if eta is None or food_days(u) < eta / 24 + cfg.stage_food_days:
                                continue
                            distance_cost = eta
                        candidates.append((distance_cost, uid, c['id'], expected))
                if emergency:
                    # Leave up to two global economic squads only when the
                    # remaining currently healthy force can still meet quorum.
                    available = sum(row[3] for row in candidates)
                    keepers = set()
                    for _, uid, _, healthy in sorted(candidates, reverse=True):
                        if len(keepers) >= cfg.emergency_economy_keepers:
                            break
                        if available - healthy >= required:
                            keepers.add(uid)
                            available -= healthy
                    candidates = [row for row in candidates if row[1] not in keepers]
                chosen, total = [], 0
                for _, uid, cid, expected in sorted(candidates):
                    if kind == 'attack' and len(chosen) >= cfg.max_attack_parties:
                        break
                    chosen.append((uid, cid, expected))
                    total += expected
                    if total >= required * (1.0 if emergency else cfg.roster_margin) and len(chosen) >= 2:
                        break
                if total >= required and chosen and (kind == 'defense' or len(chosen) >= 2):
                    self.serial += 1
                    self.campaign = dict(kind=kind, target=target['id'], stage=dict(x=stage['x'], y=stage['y']),
                        required=required, start=hour, last_seen=hour, serial=self.serial, launched=False, emergency=emergency)
                    for uid, cid, expected in chosen:
                        self.missions[uid] = dict(home=cid, phase='refit' if kind == 'attack' else 'stage',
                            expected=expected, selected=hour)
                        if emergency:
                            self.missions[uid]['restore_economy_target'] = self.targets.get(uid, 27)
                    self.war_events.append(dict(hour=hour, event='mobilize', kind=kind, target=target['id'],
                        units=[uid for uid, _, _ in chosen], required=required, task=self.serial))

        p = self.campaign
        if p:
            for uid, m in list(self.missions.items()):
                if m['phase'] != 'refit':
                    continue
                u, c = parties[uid], cities.get(m['home'])
                if u['battle'] or not c:
                    continue
                if c['id'] in blocked:
                    # Do not send independent refitters into a live siege.
                    m['phase'] = 'stage'
                    continue
                if distance(u, c) > 500:
                    move(u, c, campaign_phase='cloud_refit')
                    continue
                if u.get('refill_target') != 150:
                    commands.append(dict(type='set_strength', unit=uid, target=150))
                g = own[c['garrison']]
                if not g['battle'] and not g['army'] and distance(g, c) <= 500:
                    unload = min(u['wounded'], max(0, 500 - g['healthy'] - g['wounded']))
                    if unload and u['healthy']:
                        commands.append(dict(type='transfer', unit=uid, target=g['id'], count=unload, wounded=True))
                        g['wounded'] += unload
                    take = min(max(0, 150 - u['healthy'] - u['wounded'] + unload), g['healthy'])
                    if take and (u['healthy'] or u['wounded']):
                        commands.append(dict(type='transfer', unit=g['id'], target=uid, count=take))
                        g['healthy'] -= take
                # A useful currently-ready formation can depart without demanding
                # exactly 150 healthy and zero wounded from every roster member.
                ready = u['healthy'] >= min(cfg.min_party_health, m['expected']) and food_days(u) >= cfg.refit_food_days
                expired = hour - m['selected'] >= cfg.refit_deadline
                if ready or (expired and u['healthy'] >= 20 and food_days(u) >= cfg.stage_food_days):
                    m['phase'] = 'stage'
                elif expired:
                    m['phase'] = 'return'
                elif u.get('path') or u.get('order'):
                    commands.append(dict(type='stop', unit=uid))

            if p['kind'] == 'defense' and p['target'] in alerts:
                stage = staging_point(obs, alerts[p['target']], list(cities.values()))
                if stage:
                    p['stage'] = stage
                p['required'] = defense_need(p['target'])
            elif p['kind'] == 'attack' and not p['launched']:
                target = allcities.get(p['target'])
                if target:
                    p['required'] = attack_need(target)

            staged = []
            for uid, m in self.missions.items():
                if m['phase'] != 'stage':
                    continue
                u = parties[uid]
                if u['battle']:
                    continue
                if p['kind'] == 'defense' and p['target'] in alerts:
                    move(u, p['stage'], campaign_phase='cloud_stage', relief_city=p['target'], relief_action='wait')
                else:
                    move(u, p['stage'], campaign_phase='cloud_stage')
                if distance(u, p['stage']) <= 100 and food_days(u) >= cfg.stage_food_days:
                    staged.append(u)

            # Quorum is actual co-located healthy strength, not a promise that
            # every absent/refitting party will eventually arrive.
            quorum = sum(u['healthy'] for u in staged) >= p['required'] * cfg.launch_ratio
            if not p['launched'] and quorum and (len(staged) >= 2 or p['kind'] == 'defense'):
                leader = min(staged, key=lambda u: u['id'])
                if len(staged) > 1:
                    commands.append(dict(type='assemble', unit=leader['id'],
                        units=[u['id'] for u in staged if u != leader], campaign_target=p['target']))
                chosen_ids = {u['id'] for u in staged}
                for uid, m in self.missions.items():
                    if m['phase'] != 'return':
                        m['phase'] = 'field' if uid in chosen_ids else 'return'
                p['launched'] = True
                self.war_events.append(dict(hour=hour, event='launch', kind=p['kind'],
                    healthy=sum(u['healthy'] for u in staged), required=p['required'], task=p['serial']))
            elif not p['launched'] and hour - p['start'] >= cfg.rally_deadline:
                finish('rally_deadline')

            if self.campaign and p['launched']:
                field = [parties[uid] for uid, m in self.missions.items() if m['phase'] == 'field']
                if field and not any(u['battle'] for u in field):
                    leader = min(field, key=lambda u: u['id'])
                    co_located = all(distance(u, leader) <= 1000 for u in field)
                    assembled = bool(leader.get('army')) and all(u.get('army') == leader['army'] for u in field)
                    assembling = any(cmd['type'] == 'assemble' and cmd.get('unit') == leader['id']
                        and set(cmd.get('units', [])) >= {u['id'] for u in field if u['id'] != leader['id']} for cmd in commands)
                    disbanding = bool(leader.get('army')) and any(cmd['type'] == 'disband'
                        and parties[cmd['unit']].get('army') == leader['army'] for cmd in commands)
                    health = sum(u['healthy'] for u in field if distance(u, leader) <= 1000)
                    if not co_located or disbanding or (len(field) > 1 and not assembled and not assembling):
                        finish('formation_fragmented')
                    elif p['kind'] == 'attack':
                        target = allcities.get(p['target'])
                        if target and p['target'] not in cities and p['target'] in obs.get('frontier_targets', []):
                            if target.get('stale'):
                                move(leader, target, campaign_phase='cloud_approach')
                            elif health < self.attack_requirement(obs, target, fresh=True):
                                finish('fresh_target_too_strong')
                            elif (leader.get('order') or {}).get('type') != 'siege' or (leader.get('order') or {}).get('target') != p['target']:
                                commands.append(dict(type='siege', unit=leader['id'], target=p['target']))
                        elif not target or p['target'] not in cities:
                            finish('frontier_changed')
                    else:
                        es = threat_units(p['target'])
                        if es and health >= sum(u['healthy'] for u in es) * 1.1:
                            enemy = min(es, key=lambda u: (distance(leader, u), u['id']))
                            if (leader.get('order') or {}).get('type') != 'attack' or (leader.get('order') or {}).get('target') != enemy['id']:
                                commands.append(dict(type='attack', unit=leader['id'], target=enemy['id']))
                        else:
                            move(leader, p['stage'], campaign_phase='cloud_hold', relief_city=p['target'],
                                 **({'relief_action': 'wait'} if p['target'] in alerts else {}))
        self.issued_military_commands = bool(commands) or released_mission
        return commands


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='{}', help='JSON Config overrides')
    args = parser.parse_args()
    controller = Controller(json.loads(args.config))
    for line in sys.stdin:
        request = json.loads(line)
        commands = controller.decide(request['observation'])
        print(json.dumps(dict(protocol_version=1, request_id=request['request_id'], commands=commands)), flush=True)


if __name__ == '__main__':
    main()
