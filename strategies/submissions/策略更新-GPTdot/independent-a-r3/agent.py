#!/usr/bin/env python3
"""Initiative Columns, independent observation-only policy for frozen v0.2.0.
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


class Policy:
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
        dispatched = {}
        for needy in sorted(self.owned, key=lambda c: c.get('food', 0)):
            g = self.units.get(needy['garrison'], {})
            m = self.units.get(needy.get('militia'), {})
            resident = size(g) + size(m)
            if needy['id'] in self.besieged or needy.get('food', 0) >= resident * 50 * 14:
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
            available = g['healthy'] - (20 if c['id'] in dispatched else 0)
            budget = max(0, c.get('food', 0) - 50000 - dispatched.get(c['id'], 0))
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
            near = [p for p in self.parties if not p.get('battle') and distance(p, cart) <= 1000 and food_days(p) < 20]
            if near:
                self.emit({'type': 'supply', 'unit': cart['id'], 'target': min(near, key=food_days)['id']})

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
            if self.cooldown.get(target['id'], 0) > self.hour:
                continue
            for depot in self.owned:
                if depot['id'] in self.besieged or target['id'] not in depot.get('neighbors', []):
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
            field_enemies = [e for e in self.enemies if e['kind'] == 'party' and distance(e, target) < 23000 and not any(distance(e, c) < 1500 for c in self.o['cities'] if c['nation'] == e['nation'])]
            relief_strength = sum(e['healthy'] for e in field_enemies)
            combat_days = min(7, math.ceil((health + body) / 300)) * body / max(1, health)
            need = 3 + combat_days + self.eta(stage, depot) / 24 + 4
            success = health >= ratio * math.sqrt(body * power) and health - expected_loss >= relief_strength * 1.35 and min((food_days(p) for p in ready), default=0) >= need
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
            return self.commands[:100]
        for p in self.parties:
            self.roles.setdefault(p['id'], 'war')
        if not self.initialized:
            self.initialize()
            return self.commands
        # Recover safely from any externally-created assembled state, without permanent half speed.
        armies = set()
        for p in self.parties:
            if p.get('army') and not p.get('battle') and p['army'] not in armies:
                self.emit({'type': 'disband', 'unit': p['id']})
                armies.add(p['army'])
        self.logistics()
        self.guards()
        self.campaign()
        return self.commands[:100]


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
