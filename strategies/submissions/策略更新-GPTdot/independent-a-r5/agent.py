#!/usr/bin/env python3
"""A-R5 Adaptive Columns, experimental successor to exact A-R3. Frozen v0.2.0.
MIT. No game imports, file reads, network, seed access, or opponent code.
"""
import heapq
import json
import math
import sys


def distance(a, b):
    return math.hypot(a['x'] - b['x'], a['y'] - b['y'])


def size(u):
    return u.get('healthy', 0) + u.get('wounded', 0)


def food_days(u):
    return u.get('food', 0) / max(1, size(u) * 100)


class ColumnsCore:
    def __init__(self):
        self.roles = {}
        self.guard_spots = {}
        self.pending = {}
        self.phase = 'rally'
        self.phase_at = 0
        self.target = None
        self.depot = None
        self.cohort = []
        self.sortie_strength = 0
        self.cooldown = {}
        self.routes = {}
        self.initialized = False
        self.defend = None
        self.evacuating = set()
        self.supply_posts = {}

    def route(self, a, b):
        start = (a['x'] // 2000, a['y'] // 2000)
        end = (b['x'] // 2000, b['y'] // 2000)
        key = start, end
        if key not in self.routes:
            q = [(0, 0, start)]
            best = {start: 0}
            prev = {}
            found = False
            while q:
                _, cost, p = heapq.heappop(q)
                if cost != best.get(p):
                    continue
                if p == end:
                    found = True
                    break
                for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
                    n = p[0] + dx, p[1] + dy
                    if not (0 <= n[0] < 60 and 0 <= n[1] < 40) or self.terrain[n[1]][n[0]] == 2:
                        continue
                    nc = cost + (4 if self.terrain[n[1]][n[0]] else 3)
                    if nc < best.get(n, 10**9):
                        best[n] = nc
                        prev[n] = p
                        h = 3 * (abs(n[0] - end[0]) + abs(n[1] - end[1]))
                        heapq.heappush(q, (nc + h, nc, n))
            cells = []
            if found:
                p = end
                while p != start:
                    cells.append({'x': p[0] * 2000 + 1000, 'y': p[1] * 2000 + 1000})
                    p = prev[p]
                cells.reverse()
            self.routes[key] = cells if found else None
        cells = self.routes[key]
        if cells is None:
            return []
        return cells + [{'x': b['x'], 'y': b['y']}]

    def eta(self, a, b):
        # Conservative travel/food budget: all segments priced at slow-terrain speed.
        pts = [a] + self.route(a, b)
        return math.ceil(sum(distance(x, y) for x, y in zip(pts, pts[1:])) / 375) + 2

    def emit(self, cmd, role=None):
        if len(self.commands) >= 96:
            return
        if role:
            self.pending[len(self.commands)] = role
        self.commands.append(cmd)

    def move(self, u, p, relief=None):
        if u.get('battle') or u['id'] in self.ordered:
            return
        if distance(u, p) < 180 and not u.get('path'):
            return
        old = u.get('order') or {}
        if old.get('type') == 'move' and abs(old.get('x', -999999) - p['x']) < 100 and abs(old.get('y', -999999) - p['y']) < 100:
            return
        c = {'type': 'move', 'unit': u['id'], 'x': int(p['x']), 'y': int(p['y'])}
        if relief:
            c.update(relief_action='wait', relief_city=relief)
        self.emit(c)
        self.ordered.add(u['id'])

    def safe_city(self, u, require_food=False):
        cs = [c for c in self.owned if c['id'] not in self.besieged]
        if not cs:
            return None
        return min(cs, key=lambda c: self.eta(u, c) + (80 if require_food and c.get('food', 0) < max(60000, size(u) * 1500) else 0))

    def city_here(self, u):
        return next((c for c in self.owned if distance(u, c) <= 500 and c['id'] not in self.besieged), None)

    def point_toward(self, source, toward, radius):
        d = max(1, distance(source, toward))
        x = max(1000, min(119000, round(source['x'] + (toward['x'] - source['x']) * radius / d)))
        y = max(1000, min(79000, round(source['y'] + (toward['y'] - source['y']) * radius / d)))
        if self.terrain[y // 2000][x // 2000] == 2:
            return dict(toward)
        return {'x': x, 'y': y}

    def coverage_points(self, number):
        villages = self.owned_villages
        candidates = [dict(x=v['x'], y=v['y']) for v in villages]
        for i, v in enumerate(villages):
            for z in villages[i + 1:]:
                if distance(v, z) < 12500:
                    candidates.append({'x': (v['x'] + z['x']) // 2, 'y': (v['y'] + z['y']) // 2})
        weights = {v['id']: max(1, v.get('population', 180)) for v in villages}
        chosen = []
        for _ in range(number):
            if not candidates:
                break
            def value(p):
                return sum(weights[v['id']] * max(0, 1 - (distance(p, v) / 8500)**2) for v in villages)
            best = max(candidates, key=value)
            chosen.append(best)
            candidates.remove(best)
            for v in villages:
                if distance(v, best) < 6500:
                    weights[v['id']] *= .12
        return chosen

    def initialize(self):
        if self.hour != 0:
            # A process restart is not an opening position: retain legal current forces.
            small = [p for p in self.parties if not p.get('battle') and not p.get('army') and p['healthy'] >= 20 and size(p) <= 35 and p.get('refill_target', 150) <= 25]
            for spot in self.coverage_points(min(4, len(small))):
                p = min(small, key=lambda u: self.eta(u, spot))
                small.remove(p)
                self.roles[p['id']] = 'guard'
                self.guard_spots[p['id']] = spot
            fighting = [p for p in self.parties if p.get('battle')]
            if fighting:
                self.phase = 'engaged'
                self.phase_at = self.hour
                self.cohort = [p['id'] for p in fighting]
                ids = {p['battle'] for p in fighting}
                battle = next((b for b in self.o['battles'] if b['id'] in ids and b.get('city')), None)
                self.target = battle['city'] if battle else None
                city = self.safe_city(fighting[0], True)
                self.depot = city['id'] if city else None
                self.sortie_strength = sum(p['healthy'] for p in fighting)
            self.initialized = True
            return
        # Four sentries cost80 of the480 initial regulars; all other regulars mobilize.
        available = list(self.parties)
        for spot in self.coverage_points(min(4, max(0, len(available) - 1))):
            p = min(available, key=lambda u: self.eta(u, spot))
            available.remove(p)
            self.roles[p['id']] = 'guard'
            self.guard_spots[p['id']] = spot
        for p in self.parties:
            if p['id'] not in self.roles:
                self.roles[p['id']] = 'war'
            c = self.city_here(p)
            if not c:
                continue
            g = self.units.get(c['garrison'])
            if not g:
                continue
            if self.roles[p['id']] == 'guard':
                self.emit({'type': 'set_strength', 'unit': p['id'], 'target': 20})
                extra = max(0, p['healthy'] - 20)
                if extra:
                    self.emit({'type': 'transfer', 'unit': p['id'], 'target': g['id'], 'count': extra})
                count = min(150, g['healthy'] + extra)
                if count >= 20:
                    self.emit({'type': 'create', 'city': c['id'], 'count': count, 'clan': p['clan']}, 'war')
            else:
                self.emit({'type': 'set_strength', 'unit': p['id'], 'target': 150})
                count = min(g['healthy'], 150 - size(p))
                if count:
                    self.emit({'type': 'transfer', 'unit': g['id'], 'target': p['id'], 'count': count})
        self.initialized = True

    def logistics(self):
        # Emergency food moves precede recruitment so the20-person convoy crew is reserved.
        dispatched = self.emergency_dispatch()
        for needy in sorted(self.owned, key=lambda c: c.get('food', 0)):
            g = self.units.get(needy['garrison'], {})
            m = self.units.get(needy.get('militia'), {})
            resident = size(g) + size(m) + sum(size(p) for p in self.parties if distance(p, needy) <= 500)
            if needy['id'] in dispatched or needy['id'] in self.besieged or needy.get('food', 0) >= resident * 50 * 14:
                continue
            inbound = any(u['kind'] == 'city_cart' and u.get('destination') == needy['id'] and u.get('phase') == 'outbound' for u in self.own_units)
            if inbound:
                continue
            donors = [c for c in self.owned if needy['id'] in c.get('neighbors', []) and c['id'] not in self.besieged and c['id'] not in dispatched and not c.get('convoy') and c.get('food', 0) > 650000 and self.units.get(c['garrison'], {}).get('healthy', 0) >= 20]
            if donors:
                donor = max(donors, key=lambda c: c['food'])
                cargo = min(940000, donor['food'] - 400000)
                self.emit({'type': 'dispatch', 'city': donor['id'], 'destination': needy['id'], 'food': cargo})
                dispatched[donor['id']] = cargo + 60000
        clan_counts = {c: sum(p['clan'] == c for p in self.parties) for c in range(self.n * 6, self.n * 6 + 6)}
        for c in self.owned:
            if c['id'] in self.besieged:
                continue
            g = self.units.get(c['garrison'])
            if not g or g.get('battle'):
                continue
            available = max(0, g['healthy'] - (20 if c['id'] in dispatched else 0) - self.defense_floor(c))
            budget = max(0, c.get('food', 0) - self.mobilization_floor(c) - dispatched.get(c['id'], 0))
            present = [p for p in self.parties if not p.get('battle') and not p.get('army') and distance(p, c) <= 500]
            # Bridge an empty captured city's first daily ticks with a real supplied resident.
            # Its personal food is shared with militia/garrison while physically in this city.
            residents = size(g) + size(self.units.get(c.get('militia'), {}))
            if c.get('food', 0) < max(10000, residents * 50 * 14):
                supplied = [p for p in present if self.roles.get(p['id']) != 'guard' and p['id'] not in self.evacuating and p.get('food', 0) >= (size(p) + residents) * 50 * 10]
                if supplied:
                    old = self.supply_posts.get(c['id'])
                    holder = next((p for p in supplied if p['id'] == old), None) or max(supplied, key=lambda p: p['food'] / max(1, size(p) + residents))
                    self.supply_posts[c['id']] = holder['id']
                    self.holding.add(holder['id'])
                    if holder.get('path'):
                        self.emit({'type': 'stop', 'unit': holder['id']})
                    self.ordered.add(holder['id'])
            else:
                self.supply_posts.pop(c['id'], None)
            # Move first, THEN load wounded: otherwise automatic city service puts them back.
            wounded_available = g.get('wounded', 0)
            militia = self.units.get(c.get('militia'), {})
            poor = c.get('food', 0) < (size(g) + size(militia)) * 50 * 14
            if poor and wounded_available:
                destinations = [z for z in self.owned if z['id'] != c['id'] and z['id'] not in self.besieged and z.get('food', 0) > 200000]
                if destinations:
                    destination = min(destinations, key=lambda z: self.eta(c, z))
                    travel_days = self.eta(c, destination) / 24 + 3
                    for p in sorted(present, key=lambda u: -u.get('food', 0)):
                        if self.roles.get(p['id']) == 'guard' or p['id'] in self.holding:
                            continue
                        load = min(wounded_available, 150 - size(p), max(0, int(p.get('food', 0) / (100 * travel_days)) - size(p)))
                        if load > 0:
                            self.move(p, destination)
                            self.emit({'type': 'transfer', 'unit': g['id'], 'target': p['id'], 'count': load, 'wounded': True})
                            self.evacuating.add(p['id'])
                            wounded_available -= load
            for p in sorted(present, key=lambda u: -u['healthy']):
                if p['id'] in self.evacuating or p['id'] in self.holding:
                    continue
                desired = 20 if self.roles.get(p['id']) == 'guard' else 150
                if p.get('refill_target') != desired:
                    self.emit({'type': 'set_strength', 'unit': p['id'], 'target': desired})
                # Manual transfer bypasses the unused-slot30-person auto-service reserve.
                take = min(available, max(0, desired - size(p)), budget // 3000)
                if take:
                    self.emit({'type': 'transfer', 'unit': g['id'], 'target': p['id'], 'count': take})
                    available -= take
                    budget -= take * 3000
            free = [cl for cl, count in clan_counts.items() if count < 3]
            count = min(150, available, budget // 3500)
            if free and count >= 30:
                clan = min(free, key=lambda cl: (clan_counts[cl], cl != c['clan'], cl))
                self.emit({'type': 'create', 'city': c['id'], 'count': count, 'clan': clan}, 'war')
                clan_counts[clan] += 1
                available -= count
        # Send real surplus to the current depot, only along a legal adjacent edge.
        depot = self.owned_cities.get(self.depot)
        if depot and depot['nation'] == self.n and depot['id'] not in self.besieged and depot.get('food', 0) < 650000:
            donors = [c for c in self.owned if depot['id'] in c.get('neighbors', []) and c['id'] not in self.besieged and not c.get('convoy') and c.get('food', 0) > 1600000 and self.units.get(c['garrison'], {}).get('healthy', 0) >= 20]
            if donors:
                c = max(donors, key=lambda c: c['food'])
                # Only dispatch from a city where no same-turn transfer/create spends troops.
                spent = any(cmd.get('city') == c['id'] or cmd.get('unit') == c['garrison'] for cmd in self.commands)
                if not spent:
                    self.emit({'type': 'dispatch', 'city': c['id'], 'destination': depot['id'], 'food': min(940000, c['food'] - 1100000)})
        for cart in self.own_units:
            if cart['kind'] != 'city_cart' or cart.get('battle') or cart.get('cargo_food', 0) <= 0:
                continue
            near = [p for p in self.parties if not p.get('battle') and p['id'] not in self.supplied_now and distance(p, cart) <= 1000 and food_days(p) < 20]
            if near:
                receiver = min(near, key=food_days)
                self.emit({'type': 'supply', 'unit': cart['id'], 'target': receiver['id']})
                self.supplied_now.add(receiver['id'])

    def guards(self):
        for p in self.parties:
            if self.roles.get(p['id']) != 'guard' or p.get('battle'):
                continue
            c = self.safe_city(p, True)
            if not c:
                continue
            enemies = [e for e in self.enemies if e['kind'] == 'party' and distance(e, p) < 6500]
            # Guards never chase. Return for food/healing or retreat from national armies.
            return_hours = self.eta(p, c)
            need_home = p['healthy'] < 20 or food_days(p) < return_hours / 24 + 4 or enemies
            if need_home:
                self.move(p, c)
                continue
            spot = self.guard_spots.get(p['id'])
            if spot is None or not any(distance(spot, v) < 9000 for v in self.owned_villages):
                options = self.coverage_points(6)
                used = list(self.guard_spots.values())
                spot = max(options, key=lambda s: min((distance(s, z) for z in used), default=10000)) if options else c
                self.guard_spots[p['id']] = spot
            self.move(p, spot)

    def defenders(self, city):
        g = city.get('healthy', 50)
        m = city.get('militia_healthy', min(200, 100 + self.hour // 24))
        body = g + m
        equivalent = 2 * g + m
        # Initially present parties and carts join and receive city defense too.
        for e in self.enemies:
            if distance(e, city) > 1100 or e['kind'] in ('garrison', 'militia'):
                continue
            body += e['healthy']
            equivalent += e['healthy'] * (1 if e['kind'] == 'village_cart' else 2)
        return max(1, body), max(1, equivalent)

    def choose_campaign(self, war):
        options = []
        for target in self.o['cities']:
            if target['id'] in self.owned_cities or target['id'] not in self.o.get('frontier_targets', []):
                continue
            if self.target_blocked(target, war):
                continue
            for depot in self.owned:
                if depot['id'] in self.besieged or target['id'] not in depot.get('neighbors', []) or not self.depot_funded(depot, war):
                    continue
                body, power = self.defenders(target)
                gathering = sum(self.eta(p, depot) * p['healthy'] for p in war) / max(1, sum(p['healthy'] for p in war))
                score = self.eta(depot, target) + gathering * .65 + math.sqrt(body * power) * .12
                if depot.get('food', 0) < 120000:
                    score += 70
                options.append((score, target['id'], depot['id']))
        if not options:
            return False
        _, self.target, self.depot = min(options)
        self.phase = 'rally'
        self.phase_at = self.hour
        self.cohort = []
        return True

    def regroup(self, war, city=None):
        if city is None:
            center = {'x': sum(p['x'] for p in war) // max(1, len(war)), 'y': sum(p['y'] for p in war) // max(1, len(war))}
            city = self.safe_city(center, True)
        if city:
            self.depot = city['id']
            for p in war:
                self.move(p, city)
        self.phase = 'recover'
        self.phase_at = self.hour

    def relief(self, war):
        requests = self.o.get('relief_requests', [])
        if not requests:
            if self.phase == 'relief':
                self.target = None
                self.phase = 'rally'
                self.defend = None
            return False
        if any(p.get('battle') for p in self.parties if p['id'] in self.cohort):
            return False
        choices = []
        for r in requests:
            enemies = [e for e in self.enemies if e['kind'] not in ('garrison', 'militia', 'village_cart') and (e.get('battle') in (r['battle'], r.get('relief_battle')) or distance(e, r) < 1200)]
            enemy_strength = sum(e['healthy'] for e in enemies)
            if not enemies or not enemy_strength:
                continue
            choices.append((enemy_strength, r, enemies))
        if not choices:
            return False
        strength, r, enemies = min(choices, key=lambda x: x[0])
        total = sum(p['healthy'] for p in war)
        if total < strength * 1.5:
            return False  # Do not feed unwinnable relief; preserve force for another city.
        other = [c for c in self.owned if c['id'] != r['city'] and c['id'] not in self.besieged]
        if not other:
            return False
        toward = min(other, key=lambda c: distance(c, r))
        stage = self.point_toward(r, toward, 4000)
        self.phase = 'relief'
        self.defend = r['city']
        ready = [p for p in war if distance(p, stage) < 700 and food_days(p) >= 8]
        health = sum(p['healthy'] for p in ready)
        if health >= strength * 1.55 and health >= total * .85:
            foe = max(enemies, key=lambda e: e['healthy'])
            self.cohort = [p['id'] for p in ready]
            self.sortie_strength = health
            for p in ready:
                self.emit({'type': 'attack', 'unit': p['id'], 'target': foe['id']})
                self.ordered.add(p['id'])
            self.phase = 'engaged'
            self.target = None
        else:
            for p in war:
                self.move(p, stage, r['city'])
        return True

    def campaign(self):
        war_all = [p for p in self.parties if self.roles.get(p['id'], 'war') == 'war']
        free = [p for p in war_all if not p.get('battle') and p['id'] not in self.evacuating and p['id'] not in self.holding]
        war = []
        for p in free:
            c = self.safe_city(p, True)
            return_need = self.eta(p, c) / 24 + 3 if c else 8
            if p['healthy'] < 20 or p['healthy'] < size(p) * .55 or food_days(p) < return_need:
                if c:
                    self.move(p, c)
            else:
                war.append(p)
        if not war and self.phase != 'engaged':
            return
        if self.relief(war):
            return
        if self.phase == 'engaged':
            fighting = any(p.get('battle') for p in war_all if p['id'] in self.cohort)
            if fighting:
                depot = self.owned_cities.get(self.depot)
                if depot and depot['nation'] == self.n and depot['id'] not in self.besieged:
                    for p in war:
                        if p['id'] not in self.cohort:
                            self.move(p, depot)
                return
            # A committed attack can take several decisions to reach contact.
            # Do not mistake marching-but-not-yet-fighting for a completed battle.
            approaching = [p for p in free if p['id'] in self.cohort and p.get('path') and (p.get('order') or {}).get('type') in ('siege', 'attack')]
            if approaching and self.hour - self.phase_at < 192:
                return
            won_city = self.owned_cities.get(self.target)
            safe = won_city if won_city and won_city['nation'] == self.n and won_city['id'] not in self.besieged and won_city.get('food', 0) >= 150000 else None
            self.regroup(free, safe)
            self.target = None
            return
        if self.phase == 'recover':
            depot = self.owned_cities.get(self.depot)
            if not depot or depot['nation'] != self.n or depot['id'] in self.besieged:
                self.regroup(war)
                return
            for p in war:
                self.move(p, depot)
            present = [p for p in war if distance(p, depot) <= 500]
            health = sum(p['healthy'] for p in present)
            ready = self.hour - self.phase_at >= 144 and health >= max(250, self.sortie_strength * .86)
            if ready or self.hour - self.phase_at > 504:
                self.target = None
                self.phase = 'rally'
            else:
                return
        target = self.cities.get(self.target)
        depot = self.owned_cities.get(self.depot)
        if not target or target['id'] in self.owned_cities or target['id'] not in self.o.get('frontier_targets', []) or not depot or depot['id'] in self.besieged:
            if not self.choose_campaign(war):
                for p in war:
                    c = self.safe_city(p, True)
                    if c:
                        self.move(p, c)
                return
            target = self.cities[self.target]
            depot = self.cities[self.depot]
        stage = self.point_toward(target, depot, 6500)
        if self.phase == 'rally':
            for p in war:
                self.move(p, depot)
            ready = [p for p in war if distance(p, depot) <= 500]
            total = sum(p['healthy'] for p in war)
            health = sum(p['healthy'] for p in ready)
            needed = self.eta(depot, stage) / 24 + 11
            supplied = [p for p in ready if food_days(p) >= needed]
            if sum(p['healthy'] for p in supplied) >= max(300, total * .90):
                # At a common point, identical paths keep the columns within one join radius.
                self.cohort = [p['id'] for p in supplied]
                self.sortie_strength = sum(p['healthy'] for p in supplied)
                self.phase = 'scout'
                self.phase_at = self.hour
                self.ordered.difference_update(self.cohort)
                # Replace same-turn depot moves rather than emit conflicting orders.
                self.commands = [cmd for cmd in self.commands if not (cmd['type'] == 'move' and cmd.get('unit') in self.cohort)]
                for p in supplied:
                    self.move(p, stage)
            return
        if self.phase == 'scout':
            members = [p for p in war if p['id'] in self.cohort]
            for p in war:
                self.move(p, stage if p['id'] in self.cohort else depot)
            ready = [p for p in members if distance(p, stage) <= 650]
            health = sum(p['healthy'] for p in ready)
            total = sum(p['healthy'] for p in members)
            if health < max(250, total * .95) or target.get('stale', True):
                if self.hour - self.phase_at > 192:
                    self.cooldown[self.target] = self.hour + 168
                    self.regroup(war, depot)
                    self.target = None
                return
            body, power = self.defenders(target)
            # Constant cached power means expected losses scale approximately defender^2/attacker.
            expected_loss = body * power / max(1, health)
            behind = len(self.owned) < 6
            ratio = 1.35 if self.hour >= 1650 * 24 and behind else 1.70
            field_enemies = [e for e in self.enemies if e['kind'] == 'party' and 1100 < distance(e, target) < 23000]
            relief_strength = sum(e['healthy'] for e in field_enemies)
            combat_days = min(7, math.ceil((health + body) / 300)) * body / max(1, health)
            need = 3 + combat_days + self.eta(stage, depot) / 24 + 4
            success = self.assault_feasible(target, ready, depot)
            if success:
                self.commands = [cmd for cmd in self.commands if not (cmd['type'] == 'move' and cmd.get('unit') in self.cohort)]
                for p in ready:
                    self.emit({'type': 'siege', 'unit': p['id'], 'target': target['id']})
                    self.ordered.add(p['id'])
                self.phase = 'engaged'
                self.phase_at = self.hour
            elif self.hour - self.phase_at > self.eta(depot, stage) + 24:
                self.cooldown[self.target] = self.hour + 168
                self.regroup(war, depot)
                self.target = None

    def decide(self, o, outcomes=()):
        for index, role in self.pending.items():
            if index < len(outcomes) and outcomes[index].get('ok') and outcomes[index].get('unit'):
                self.roles[outcomes[index]['unit']] = role
        self.pending = {}
        self.commands = []
        self.ordered = set()
        self.holding = set()
        self.o = o
        self.n = o['nation']
        self.hour = o['hour']
        self.terrain = o['terrain']
        self.cities = {c['id']: c for c in o['cities']}
        self.units = {u['id']: u for u in o['units']}
        self.own_units = [u for u in o['units'] if u['nation'] == self.n]
        # Owned entities are full current records, never remembered nation labels.
        # A lost out-of-sight city/village can retain our old nation in its stale record.
        self.owned = [c for c in o['cities']
                      if c['nation'] == self.n and not c.get('stale', False)
                      and {'garrison', 'clan', 'food', 'neighbors'} <= c.keys()
                      and c['garrison'] in self.units
                      and self.units[c['garrison']]['nation'] == self.n]
        self.owned_cities = {c['id']: c for c in self.owned}
        self.owned_villages = [v for v in o['villages']
                              if v['nation'] == self.n and not v.get('stale', False)
                              and 'cart' in v and v['city'] in self.owned_cities]
        if self.depot not in self.owned_cities:
            self.depot = None
        self.supply_posts = {cid: uid for cid, uid in self.supply_posts.items()
                             if cid in self.owned_cities and uid in self.units
                             and self.units[uid]['nation'] == self.n}
        self.parties = [u for u in self.own_units if u['kind'] == 'party']
        self.enemies = [u for u in o['units'] if u['nation'] not in (self.n, -1)]
        self.evacuating = {uid for uid in self.evacuating if self.units.get(uid, {}).get('wounded', 0) > 0}
        self.besieged = {r['city'] for r in o.get('relief_requests', [])}
        if not self.owned:
            return []
        if not self.parties:
            # A wiped mobile force must still rebuild from actual safe-city resources.
            self.logistics()
            return self.finalize_commands()
        for p in self.parties:
            self.roles.setdefault(p['id'], 'war')
        if not self.initialized:
            self.initialize()
            return self.finalize_commands()
        # Recover safely from any externally-created assembled state, without permanent half speed.
        armies = set()
        for p in self.parties:
            if p.get('army') and not p.get('battle') and p['army'] not in armies:
                self.emit({'type': 'disband', 'unit': p['id']})
                armies.add(p['army'])
        self.logistics()
        self.guards()
        self.campaign()
        return self.finalize_commands()


class Policy(ColumnsCore):
    """Preserve initiative, but price irreversible commitments and future capacity.

    Only current/remembered observations enter the policy. Economic operations are
    finite commitments, not a guarantee of advantage or a substitute for validation.
    """
    def __init__(self):
        super().__init__()
        self.failures = {}
        self.last_enemies = {}
        self.economic_until = 0
        self.operation = None
        self.home_claims = {}
        self.supplied_now = set()
        self.stranded = set()
        self.decisions = []

    def decide(self, o, outcomes=()):
        self.home_claims = {}
        self.supplied_now = set()
        self.stranded = set()
        # Preserve sightings for a short uncertainty window, never infer unseen kills.
        now, nation = o['hour'], o['nation']
        self.last_enemies = {k: v for k, v in self.last_enemies.items() if now - v['at'] <= 48}
        for u in o['units']:
            if u['nation'] not in (nation, -1) and u['kind'] == 'party':
                self.last_enemies[u['id']] = {'at': now, 'unit': dict(u)}
        return super().decide(o, outcomes)

    def initialize(self):
        super().initialize()
        if self.hour == 0:
            return
        approaching = [p for p in self.parties if not p.get('battle') and (p.get('order') or {}).get('type') == 'siege']
        if approaching and not any(p.get('battle') for p in self.parties):
            self.cohort = [p['id'] for p in approaching]
            self.target = approaching[0]['order']['target']
            home = self.safe_city(approaching[0], True)
            self.depot = home['id'] if home else None
            self.phase = 'engaged'; self.phase_at = self.hour
            self.sortie_strength = sum(p['healthy'] for p in approaching)
            self.campaign()
            self.logistics()
        else:
            self.logistics()
            self.guards()
            self.campaign()

    def note(self, action, reason, **details):
        self.decisions.append(dict(hour=self.hour, action=action, reason=reason, **details))
        self.decisions = self.decisions[-32:]

    def reachable(self, a, b):
        return bool(self.route(a, b))

    def corridor_threat(self, a, b, radius=3500):
        route = [a] + self.route(a, b)
        total = 0
        for e in self.enemies:
            if e['kind'] != 'party' or e.get('battle'):
                continue
            if any(distance(e, p) <= radius for p in route):
                total += e['healthy']
        return total

    def city_demand(self, c):
        # Seven days of actual local mouths: all units at own city eat city ration.
        local = size(self.units.get(c['garrison'], {})) + size(self.units.get(c.get('militia'), {}))
        local += sum(size(p) for p in self.parties if distance(p, c) <= 500)
        return local * 50 * 7

    def mobilization_floor(self, c):
        # Existing low-food residents refill before a new sortie is affordable.
        # Keep seven days of city demand separately from personal carry capacity.
        deficit = sum(self.refit_claim(p, c)
                      for p in self.parties if distance(p, c) <= 500 and not p.get('battle'))
        return max(50000, self.city_demand(c)) + deficit

    def refit_claim(self, p, city):
        # City service fills to full 30-day capacity, not a requested partial load.
        # Include possible automatic troop replenishment and food spent en route.
        target = min(150, max(size(p), p.get('refill_target', 150), p.get('reserve_refill_target', 0)))
        g = self.units.get(city.get('garrison'), {})
        projected = min(target, size(p) + g.get('healthy', 0))
        travel_food = size(p) * 100 * self.eta(p, city) / 24 if distance(p, city) > 500 else 0
        return math.ceil(max(0, projected * 3000 - p.get('food', 0) + travel_food))

    def depot_funded(self, c, parties=()):
        claim = sum(self.refit_claim(p, c) for p in parties)
        return c.get('food', 0) >= self.city_demand(c) + 60000 + claim

    def safe_city(self, u, require_food=False):
        choices = []
        for c in self.owned:
            if c['id'] in self.besieged or not self.reachable(u, c):
                continue
            travel = self.eta(u, c)
            if self.corridor_threat(u, c) > max(20, u.get('healthy', 0)) * .7:
                continue
            if require_food:
                claim = self.refit_claim(u, c)
                promised = sum(v[1] for k, v in self.home_claims.items() if k != u.get('id') and v[0] == c['id'])
                if c.get('food', 0) < self.city_demand(c) + 60000 + claim + promised:
                    continue
                # An at-city party can receive immediate service. Otherwise do not
                # send a hungry party on a trip it cannot survive without food.
                if u.get('kind') == 'party' and distance(u, c) > 500 and food_days(u) < travel / 24 + 1:
                    continue
            choices.append((travel, c['id'], c))
        return min(choices, key=lambda x: x[:2])[2] if choices else None

    def move(self, u, p, relief=None):
        if p.get('id') in self.owned_cities and u.get('id'):
            promised = sum(v[1] for k, v in self.home_claims.items() if k != u['id'] and v[0] == p['id'])
            claim = self.refit_claim(u, p)
            survives = distance(u, p) <= 500 or food_days(u) >= self.eta(u, p) / 24 + 1
            funded = p.get('food', 0) >= self.city_demand(p) + 60000 + promised + claim
            if not survives or not funded:
                alternative = self.safe_city(u, True)
                if alternative is None:
                    if u.get('path') and not u.get('battle') and u['id'] not in self.ordered:
                        self.emit({'type': 'stop', 'unit': u['id']})
                        self.ordered.add(u['id'])
                    self.note('stranded', 'no_feasible_refit_destination', unit=u['id'])
                    return
                p = alternative
            claim = self.refit_claim(u, p)
            self.home_claims[u['id']] = (p['id'], claim)
        # Ordinary paths only: no mismatch with special relief-wait terrain.
        escort = sum(z['healthy'] for z in self.parties if not z.get('battle') and distance(z, u) <= 1000)
        if not self.reachable(u, p) or self.corridor_threat(u, p) > max(20, escort) * .7:
            old = [dict(x=z[0], y=z[1]) for z in u.get('path', [])]
            old_risk = sum(e['healthy'] for e in self.enemies if e['kind'] == 'party' and not e.get('battle')
                           and any(distance(e, z) <= 3500 for z in [u] + old))
            if old and old_risk > max(20, escort) * .7 and not u.get('battle') and u['id'] not in self.ordered:
                self.emit({'type': 'stop', 'unit': u['id']})
                self.ordered.add(u['id'])
                self.note('stop', 'newly_unsafe_existing_route', unit=u['id'])
            return
        return super().move(u, p, None)

    def defense_floor(self, city):
        # Reserve actual local threat shortfall, not a national fixed fraction.
        threats = sum(e['healthy'] for e in self.enemies if e['kind'] == 'party'
                      and not e.get('battle') and distance(e, city) < 18000)
        nearby = sum(p['healthy'] for p in self.parties if distance(p, city) <= 1000 and not p.get('battle'))
        militia = self.units.get(city.get('militia'), {}).get('healthy', 0) * .5
        shortfall = max(0, math.ceil(threats * 1.15 - nearby - militia))
        return min(self.units.get(city['garrison'], {}).get('healthy', 0), shortfall)

    def emergency_dispatch(self):
        dispatched = {}
        needy = []
        for c in self.owned:
            if c['id'] in self.besieged:
                continue
            present = [p for p in self.parties if not p.get('battle') and distance(p, c) <= 500]
            required = self.city_demand(c) + 60000 + sum(self.refit_claim(p, c) for p in present)
            if present and c.get('food', 0) < required:
                needy.append((min(food_days(p) for p in present), c, required))
        for _, destination, required in sorted(needy, key=lambda x: x[0]):
            if any(u['kind'] == 'city_cart' and u.get('destination') == destination['id']
                   and u.get('phase') == 'outbound' for u in self.own_units):
                continue
            options = []
            for donor in self.owned:
                if donor['id'] in dispatched or donor.get('convoy') or donor['id'] in self.besieged:
                    continue
                g = self.units.get(donor['garrison'], {})
                surplus = donor.get('food', 0) - self.mobilization_floor(donor) - 120000
                if donor['id'] == destination['id'] or g.get('healthy', 0) < 20 + self.defense_floor(donor) or surplus < 60000:
                    continue
                # BFS on actual owned adjacency; only dispatch the first legal hop.
                queue, seen = [(donor['id'], [])], {donor['id']}
                first = None
                for cid, path in queue:
                    if cid == destination['id']:
                        first = path[0] if path else None
                        break
                    for nxt in self.owned_cities[cid].get('neighbors', []):
                        if nxt in self.owned_cities and nxt not in seen and nxt not in self.besieged:
                            seen.add(nxt); queue.append((nxt, path + [nxt]))
                if first is None:
                    continue
                hop = self.owned_cities[first]
                if not self.reachable(donor, hop) or self.corridor_threat(donor, hop) >= 20:
                    continue
                # Intermediate store must be below the final demand: do not flood
                # already rich relay cities while a farther edge is blocked.
                if first != destination['id'] and hop.get('food', 0) >= required + 120000:
                    continue
                options.append((len(seen), self.eta(donor, destination), donor['id'], first, surplus))
            if not options:
                continue
            _, _, origin, first, surplus = min(options)
            cargo = int(min(940000, surplus, max(60000, required - destination.get('food', 0))))
            self.emit({'type': 'dispatch', 'city': origin, 'destination': first, 'food': cargo})
            dispatched[origin] = cargo + 60000
            self.note('dispatch', 'restore_delivered_capacity', origin=origin, destination=first, final_destination=destination['id'], food=cargo)
        return dispatched

    def logistics(self):
        super().logistics()
        self.stranded_recovery()

    def stranded_recovery(self):
        for p in self.parties:
            if p.get('battle') or p.get('army') or p['id'] in self.supplied_now or food_days(p) >= 3:
                continue
            if self.safe_city(p, True):
                continue
            carts = [c for c in self.own_units if c['kind'] == 'city_cart' and not c.get('battle') and c.get('cargo_food', 0) > 0
                     and self.reachable(p, c) and self.corridor_threat(p, c) < max(20, p['healthy']) * .7
                     and food_days(p) >= self.eta(p, c) / 24 + .5]
            if carts:
                cart = min(carts, key=lambda c: self.eta(p, c))
                self.move(p, cart)
                self.stranded.add(p['id'])
                self.note('rendezvous', 'survivable_visible_food_cart', unit=p['id'], cart=cart['id'])
                continue
            if p.get('path'):
                self.emit({'type': 'stop', 'unit': p['id']})
            self.note('stranded', 'no_survivable_food_route_or_cart', unit=p['id'])
            # Stopping a doomed prior march is not a claim that it creates food.
            self.stranded.add(p['id'])
            self.ordered.add(p['id'])

    def finalize_commands(self):
        # Sequential command accounting protects dispatch crews and party/garrison
        # capacities. Actions are still engine-validated; no optimistic same-turn
        # newborn unit or food arrival is assumed.
        health = {uid: u.get('healthy', 0) for uid, u in self.units.items()}
        wound = {uid: u.get('wounded', 0) for uid, u in self.units.items()}
        food = {c['id']: c.get('food', 0) for c in self.owned}
        kept, new_pending, dispatched = [], {}, set()
        for i, cmd in enumerate(self.commands):
            kind = cmd['type']
            ok = True
            if kind == 'dispatch':
                c = self.owned_cities.get(cmd['city'])
                if c:
                    gid = c['garrison']; amount = min(940000, cmd.get('food', 940000), max(0, food[c['id']] - 60000))
                    ok = (health.get(gid, 0) >= 20 + self.defense_floor(c) and food[c['id']] >= 60000
                          and c['id'] not in dispatched and not c.get('convoy')
                          and cmd['destination'] in c.get('neighbors', [])
                          and self.corridor_threat(c, self.owned_cities.get(cmd['destination'], c)) < 20)
                    if ok:
                        cmd = dict(cmd, food=amount)
                        dispatched.add(c['id'])
                        health[gid] -= 20; food[c['id']] -= amount + 60000
            elif kind == 'transfer':
                source, dest = cmd['unit'], cmd['target']; field = wound if cmd.get('wounded') else health
                cap = 500 if self.units.get(dest, {}).get('kind') == 'garrison' else 150
                count = min(cmd['count'], field.get(source, 0), max(0, cap - health.get(dest, 0) - wound.get(dest, 0)))
                ok = count > 0
                if ok:
                    cmd = dict(cmd, count=count); field[source] -= count; field[dest] = field.get(dest, 0) + count
            elif kind == 'create':
                c = self.owned_cities.get(cmd['city'])
                if c:
                    gid = c['garrison']; count = min(cmd['count'], health.get(gid, 0))
                    ok = count > 0
                    if ok:
                        cmd = dict(cmd, count=count); health[gid] -= count
                        food[c['id']] -= min(food[c['id']], count * 100 * 30)
            if ok:
                if i in self.pending:
                    new_pending[len(kept)] = self.pending[i]
                kept.append(cmd)
        # Auto city service must not silently undo a funded/manual mobilization
        # decision. Lower targets only in genuinely constrained cities. The engine
        # may retain reserve_refill_target; report rather than claim it can be reset.
        prefix = []
        for p in self.parties:
            city = self.city_here(p)
            if not city or p.get('battle') or p.get('army'):
                continue
            if self.defense_floor(city) <= 0 and city.get('food', 0) > self.mobilization_floor(city):
                continue
            target = max(1, health.get(p['id'], 0))
            existing = [c for c in kept if c['type'] == 'set_strength' and c['unit'] == p['id']]
            if existing:
                for c in existing: c['target'] = target
            elif p.get('refill_target', 150) != target:
                prefix.append(dict(type='set_strength', unit=p['id'], target=target))
            if p.get('reserve_refill_target', 0) > target:
                self.note('service_constraint', 'engine_retains_reserve_refill_floor', unit=p['id'])
        if prefix:
            new_pending = {i + len(prefix): role for i, role in new_pending.items()}
            kept = prefix + kept
        self.pending = new_pending
        return kept[:96]

    def target_blocked(self, target, war):
        body, power = self.defenders(target)
        if not target.get('stale', True) and sum(p['healthy'] for p in war) < 1.70 * math.sqrt(body * power):
            return True
        fail = self.failures.get(target['id'])
        if not fail:
            return self.cooldown.get(target['id'], 0) > self.hour
        strength = sum(p['healthy'] for p in war)
        body, power = self.defenders(target)
        defense = math.sqrt(body * power)
        improved = strength >= fail['strength'] * 1.20 or (not target.get('stale', True) and defense <= fail['defense'] * .80)
        # Expiry permits a new scouting observation, never bypasses the force gate.
        return not improved and self.hour < fail['until']

    def remember_failure(self, target, war, reason):
        if target:
            body, power = self.defenders(target)
            old = self.failures.get(target['id'], {})
            attempts = min(3, old.get('attempts', 0) + 1)
            self.failures[target['id']] = dict(strength=sum(p['healthy'] for p in war), defense=math.sqrt(body * power),
                                               until=self.hour + 168 * attempts, attempts=attempts, at=self.hour)
            self.note('defer_siege', reason, target=target['id'], strength=sum(p['healthy'] for p in war))
        self.economic_until = max(self.economic_until, self.hour + 168)

    def assault_feasible(self, target, members, depot):
        if not members or target.get('stale', True) or not depot or not self.depot_funded(depot, members):
            return False
        health = sum(p['healthy'] for p in members)
        body, power = self.defenders(target)
        field = sum(e['healthy'] for e in self.enemies if e['kind'] == 'party' and 1100 < distance(e, target) < 23000)
        unseen = sum(x['unit']['healthy'] for uid, x in self.last_enemies.items()
                     if uid not in self.units and distance(x['unit'], target) < 15000 and self.hour - x['at'] <= 24)
        expected_loss = body * power / max(1, health)
        combat_days = min(7, math.ceil((health + body) / 300)) * body / max(1, health)
        need = 3 + combat_days + max(self.eta(p, depot) for p in members) / 24 + 4
        return (health >= 1.70 * math.sqrt(body * power)
                and health - expected_loss >= (field + unseen) * 1.35
                and min(food_days(p) for p in members) >= need)

    def cancel_cohort(self, members, reason):
        ids = {p['id'] for p in members if not p.get('battle')}
        self.commands = [c for c in self.commands if not (c.get('unit') in ids and c['type'] in ('move', 'attack', 'siege', 'raid'))]
        self.ordered.difference_update(ids)
        for p in members:
            if p['id'] in ids:
                self.emit({'type': 'stop', 'unit': p['id']})
        self.note('cancel', reason, units=sorted(ids))

    def regroup(self, war, city=None):
        was_blocked = self.phase == 'scout' and self.target not in self.owned_cities
        if was_blocked:
            self.remember_failure(self.cities.get(self.target), war, 'fresh_scout_rejected')
        # Do not concentrate a whole cohort in a city unable to support it.
        if city and not self.depot_funded(city, war):
            city = None
        chosen = city
        for p in sorted(war, key=lambda p: -size(p)):
            home = chosen if chosen and food_days(p) >= self.eta(p, chosen) / 24 + 1 else self.safe_city(p, True)
            if home:
                self.move(p, home)
                if chosen is None:
                    self.depot = home['id']
        if chosen:
            self.depot = chosen['id']
        self.phase = 'economic' if self.economic_until > self.hour else 'recover'
        self.phase_at = self.hour

    def field_risk(self, point):
        visible = {e['id']: e for e in self.enemies if e['kind'] not in ('garrison', 'militia') and distance(e, point) <= 12000}
        risk = sum(e['healthy'] for e in visible.values())
        risk += sum(x['unit']['healthy'] for uid, x in self.last_enemies.items()
                    if uid not in self.units and distance(x['unit'], point) < 18000 and self.hour - x['at'] <= 24)
        return risk

    def field_feasible(self, point, members, depot, duration=24):
        if not members or not depot or not self.depot_funded(depot, members):
            return False
        health = sum(p['healthy'] for p in members)
        if health < sum(size(p) for p in members) * .85:
            return False  # Funded convalescence takes precedence over optional raids.
        if health < max(120, self.field_risk(point) * 1.70):
            return False
        if any(not self.reachable(p, point) or self.corridor_threat(p, point) > health * .55 for p in members):
            return False
        if not self.reachable(point, depot) or self.corridor_threat(point, depot) > health * .55:
            return False
        return all(food_days(p) >= (self.eta(p, point) + duration + self.eta(point, depot)) / 24 + 3 for p in members)

    def finish_operation(self, members, reason):
        self.cancel_cohort(members, reason)
        self.operation = None
        self.regroup(members)
        self.phase = 'economic'
        self.phase_at = self.hour

    def economic_campaign(self, free):
        depot = self.owned_cities.get(self.depot)
        if not depot or depot['id'] in self.besieged or not self.depot_funded(depot, free):
            center = {'x': sum(p['x'] for p in free) // max(1, len(free)), 'y': sum(p['y'] for p in free) // max(1, len(free))}
            choices = [c for c in self.owned if c['id'] not in self.besieged and self.depot_funded(c, free) and self.reachable(center, c)]
            depot = min(choices, key=lambda c: self.eta(center, c)) if choices else None
            self.depot = depot['id'] if depot else None
        if self.operation:
            op = self.operation
            members = [p for p in free if p['id'] in op['cohort']]
            if any(p.get('battle') for p in self.parties if p['id'] in op['cohort']):
                return
            obj = self.units.get(op['target']) if op['type'] == 'attack' else next((v for v in self.o['villages'] if v['id'] == op['target']), None)
            completed = not obj or obj.get('stale', False) or obj.get('nation') == self.n or (op['type'] == 'raid' and obj.get('disabled_until', 0) > self.hour)
            if completed or self.hour >= op['until'] or not self.field_feasible(obj or op['point'], members, depot, 24):
                self.finish_operation(members, 'economic_objective_completed_or_unsafe')
                return
            if distance(obj, op['point']) > 5000:
                self.finish_operation(members, 'pursuit_budget_exceeded')
                return
            # Cohesive escort at the objective; only the lead party starts a raid.
            if op['type'] == 'raid':
                leader = max(members, key=lambda p: p['healthy'])
                for p in members:
                    if p['id'] == leader['id']:
                        if (p.get('order') or {}).get('type') != 'raid' or (p.get('order') or {}).get('target') != obj['id']:
                            self.emit({'type': 'raid', 'unit': p['id'], 'target': obj['id']})
                    else:
                        self.move(p, obj)
            else:
                for p in members:
                    old = p.get('order') or {}
                    if old.get('type') != 'attack' or old.get('target') != obj['id']:
                        self.emit({'type': 'attack', 'unit': p['id'], 'target': obj['id']})
            return
        # A fresh affordable frontier objective outranks discretionary raids.
        # Unknown targets are not re-scouted on every economic decision.
        alternatives = [c for c in self.o['cities'] if c.get('id') in self.o.get('frontier_targets', [])
                        and c['id'] not in self.owned_cities and not c.get('stale', True)
                        and not self.target_blocked(c, free)]
        for target in alternatives:
            bases = [c for c in self.owned if target['id'] in c.get('neighbors', [])
                     and c['id'] not in self.besieged and self.assault_feasible(target, free, c)]
            if bases:
                base = min(bases, key=lambda c: sum(self.eta(p, c) for p in free))
                self.target, self.depot = target['id'], base['id']
                self.phase, self.phase_at = 'rally', self.hour
                self.cohort = []
                self.note('alternate_siege', 'fresh_affordable_frontier', target=target['id'])
                return
        # Improved enemy defense/own force can reopen a different affordable siege.
        if self.hour >= self.economic_until:
            self.phase = 'rally'; self.target = None
            return
        if not depot:
            # emergency_dispatch already issued feasible food movements. Parties
            # with no survivable route do not march blindly to a distant depot.
            self.note('sustain', 'no_funded_reachable_group_depot')
            return
        members = [p for p in free if distance(p, depot) <= 600 and p['healthy'] >= 20]
        total = sum(p['healthy'] for p in free)
        for p in free:
            home = self.safe_city(p, True)
            if (home and self.reachable(p, depot) and self.corridor_threat(p, depot) <= max(20, sum(z['healthy'] for z in free if distance(z, p) <= 1000)) * .7
                    and food_days(p) >= self.eta(p, depot) / 24 + 3
                    and self.depot_funded(depot, free)):
                self.move(p, depot)
        if sum(p['healthy'] for p in members) < max(120, total * .80):
            return
        candidates = []
        for e in self.enemies:
            if e['kind'] not in ('party', 'city_cart', 'village_cart') or e.get('battle'):
                continue
            if any(c['nation'] == e['nation'] and distance(e, c) < 1800 for c in self.o['cities']):
                continue
            protected = [v for v in self.owned_villages if distance(e, v) < 8500]
            carts = [u for u in self.own_units if u['kind'] in ('village_cart', 'city_cart') and distance(e, u) < 6000]
            value = sum(v.get('population', 0) for v in protected) + sum(u.get('cargo_recruits', 0) * 50 + u.get('cargo_food', 0) / 1000 for u in carts)
            if value > 0 and distance(depot, e) < 22000 and self.field_feasible(e, members, depot):
                candidates.append((value / (12 + self.eta(depot, e)), 'attack', e, 'protect_observed_delivery_capacity'))
        for v in self.o['villages']:
            if v['nation'] in (self.n, -1) or v.get('stale', True) or v.get('population', 0) < 100:
                continue
            if v.get('disabled_until', 0) > self.hour or v.get('raid') or distance(depot, v) > 22000:
                continue
            if any(c['nation'] == v['nation'] and distance(v, c) < 5000 for c in self.o['cities']):
                continue
            if self.field_feasible(v, members, depot):
                candidates.append((v['population'] * .40 / (24 + self.eta(depot, v)), 'raid', v, 'reduce_visible_enemy_production'))
        if not candidates:
            self.note('sustain', 'funded_recovery_no_profitable_visible_operation', depot=depot['id'])
            return
        score, kind, obj, reason = max(candidates, key=lambda x: x[0])
        self.operation = dict(type=kind, target=obj['id'], point=dict(x=obj['x'], y=obj['y']), cohort=[p['id'] for p in members],
                              until=self.hour + min(168, self.eta(depot, obj) + 48), score=score)
        self.note('economic_operation', reason, target=obj['id'], operation=kind, benefit_per_hour=round(score, 3))
        ids = {p['id'] for p in members}
        self.commands = [c for c in self.commands if not (c.get('unit') in ids and c['type'] == 'move')]
        self.ordered.difference_update(ids)
        self.economic_campaign(free)

    def campaign(self):
        war = [p for p in self.parties if self.roles.get(p['id'], 'war') == 'war']
        free = [p for p in war if not p.get('battle') and p['id'] not in self.evacuating and p['id'] not in self.holding and p['id'] not in self.stranded]
        if self.phase == 'engaged':
            fighting = any(p.get('battle') for p in war if p['id'] in self.cohort)
            approaching = [p for p in free if p['id'] in self.cohort and (p.get('order') or {}).get('type') == 'siege']
            target, depot = self.cities.get(self.target), self.owned_cities.get(self.depot)
            if approaching and not fighting and (not target or not self.assault_feasible(target, approaching, depot)):
                self.cancel_cohort(approaching, 'precontact_viability_changed')
                self.remember_failure(target, approaching, 'precontact_viability_changed')
                self.regroup(free)
                self.target = None
                return
        if self.phase == 'economic':
            if self.relief(free):
                self.operation = None
                return
            self.economic_campaign(free)
            return
        depot = self.owned_cities.get(self.depot)
        if self.phase in ('recover', 'rally') and depot and not self.depot_funded(depot, free):
            self.depot = None
            self.regroup(free)
            return
        if self.phase == 'rally' and (not self.target or self.target in self.owned_cities) and free:
            if not self.choose_campaign(free):
                # No affordable city is a strategic condition, not a permanent
                # terminal rally. Reconsider current productive opportunities.
                self.phase = 'economic'
                self.economic_until = self.hour + 168
                self.economic_campaign(free)
                return
        before = self.phase
        super().campaign()
        if before == 'engaged' and self.phase in ('recover', 'economic'):
            survivors = sum(p['healthy'] for p in free)
            if self.sortie_strength and survivors < self.sortie_strength * .60:
                self.economic_until = self.hour + 168
                self.phase = 'economic'
                self.note('recover_capacity', 'major_sortie_loss', survivors=survivors)


def main():
    policy = Policy()
    for line in sys.stdin:
        try:
            message = json.loads(line)
            commands = policy.decide(message['observation'], message.get('previous_outcomes', []))
            reply = {'protocol_version': 1, 'request_id': message['request_id'], 'commands': commands}
        except Exception as exc:
            print('policy exception: ' + repr(exc), file=sys.stderr, flush=True)
            reply = {'protocol_version': 1, 'request_id': message.get('request_id', ''), 'commands': []}
        print(json.dumps(reply, ensure_ascii=False, separators=(',', ':')), flush=True)


if __name__ == '__main__':
    main()
