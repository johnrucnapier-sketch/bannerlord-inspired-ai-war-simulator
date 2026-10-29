"""Observation-only pooled campaigns above the frozen D2 rear economy.

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

ROOT = Path(__file__).resolve().parents[3]
for path in (ROOT / 'game', ROOT / 'strategies/reference/v0.2.0'):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.escort_p5_defense_v2_policy import Controller as D2
from scripts.transport_growth_policy import distance
from aiwar.relief import staging_point
from aiwar.navigation import find_route, relief_terrain


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

    def military(self, obs):
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
            return [u for u in enemies if u['healthy'] > 0 and
                    (u['battle'] in bids or distance(u, c) <= cfg.defense_radius)]

        def defense_need(cid):
            return max(60, math.ceil(sum(u['healthy'] for u in threat_units(cid)) * cfg.defense_ratio))

        def attack_need(target):
            return max(cfg.attack_minimum, math.ceil(cfg.attack_ratio *
                (target.get('healthy', 50) + target.get('militia_healthy', 100) / 2)))

        # One global force avoids reserving two independent defense rosters for
        # the same visible enemy army. Preserve an active campaign until a real
        # completion, resource failure or deadline rather than momentary fog.
        p = self.campaign
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
                     and hour - p['last_seen'] >= 96)
            out_of_food = field and min(food_days(u) for u in field) < 5
            expired = hour - p['start'] >= cfg.tour_deadline
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
                self.targets[uid] = max(57, u.get('reserve_refill_target', 0))
                self.returning.pop(uid, None)
                self.away.pop(uid, None)
                del self.missions[uid]
                released_mission = True

        # Make a new roster only from genuinely unreserved, funded formations.
        if self.campaign is None and cities and hour >= self.cooldown:
            threats = [c for c in cities.values() if threat_units(c['id'])]
            threats.sort(key=lambda c: (c['id'] not in alerts,
                alerts.get(c['id'], {}).get('assault_at', hour + 9999),
                -sum(u['healthy'] for u in threat_units(c['id'])), c['id']))
            kind, target, stage = None, None, None
            if threats:
                target = threats[0]
                kind = 'defense'
                stage = staging_point(obs, alerts[target['id']], list(cities.values())) \
                    if target['id'] in alerts else target
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
                    if c['id'] in blocked:
                        continue
                    if kind == 'attack' and cfg.require_switched and c['id'] not in self.switched:
                        continue
                    ids = [uid for (cid, slot), uid in sorted(self.assigned.items())
                           if cid == c['id'] and uid in parties]
                    if len(ids) < 2:
                        continue
                    g = own.get(c['garrison'])
                    spare = g['healthy'] if g and not g['battle'] and distance(g, c) <= 500 else 0
                    spare -= sum(max(0, self.targets.get(uid, 27) - parties[uid]['healthy']) for uid in ids)
                    taken = 0
                    for uid in sorted(ids, key=lambda uid: (-parties[uid]['healthy'], uid)):
                        u = parties[uid]
                        if uid in self.missions or u['battle'] or u['army'] or taken >= len(ids) - 1:
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
                        candidates.append((distance_cost, uid, c['id'], expected))
                chosen, total = [], 0
                for _, uid, cid, expected in sorted(candidates):
                    if kind == 'attack' and len(chosen) >= cfg.max_attack_parties:
                        break
                    chosen.append((uid, cid, expected))
                    total += expected
                    if total >= required * cfg.roster_margin and len(chosen) >= 2:
                        break
                if total >= required and chosen and (kind == 'defense' or len(chosen) >= 2):
                    self.serial += 1
                    self.campaign = dict(kind=kind, target=target['id'], stage=dict(x=stage['x'], y=stage['y']),
                        required=required, start=hour, last_seen=hour, serial=self.serial, launched=False)
                    for uid, cid, expected in chosen:
                        self.missions[uid] = dict(home=cid, phase='refit' if kind == 'attack' else 'stage',
                            expected=expected, selected=hour)
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
                    health = sum(u['healthy'] for u in field)
                    if p['kind'] == 'attack':
                        target = allcities.get(p['target'])
                        if target and p['target'] not in cities and p['target'] in obs.get('frontier_targets', []):
                            if target.get('stale'):
                                move(leader, target, campaign_phase='cloud_approach')
                            elif health < cfg.abort_ratio * (target.get('healthy', 0) + target.get('militia_healthy', 0) / 2):
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
