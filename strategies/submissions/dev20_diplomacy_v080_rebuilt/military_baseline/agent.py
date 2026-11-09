"""Dev19's logistics/recovery policy adapted to independent clan formations.

Country-neutral, observation-only. A shared campaign is a rendezvous and target,
never a synthetic army or pooled food reserve. Protocol v1.
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dev19_base import WesternPlanner as Dev19Planner, PARAMS, distance, size
from aiwar.navigation import find_route, relief_terrain
from aiwar.organization_policy import augment_commands, attached_members, combat_strength

VERSION = 'dev20-cavalry-v070'
LOCAL_DUTY_HOURS = 48
STAGE_WAIT_HOURS = 72
CHASE_HOURS = 12


class WesternPlanner(Dev19Planner):
    def __init__(self, obs):
        super().__init__(obs)
        # Joined levy cohorts belong to the physical army and its food budget,
        # but are never regular parties for recruitment or assembly purposes.
        for aid, members in self.armies.items():
            joined = attached_members(obs, members)
            commander = obs.get('army_metadata', {}).get(aid, {}).get('commander')
            if commander:
                joined.sort(key=lambda u: u['id'] != commander)
            self.armies[aid] = joined
        hostile_ids = {u['id'] for u in self.hostiles}
        self.hostiles.extend(u for u in self.units.values()
                             if u.get('kind') == 'levy' and u['nation'] != self.n
                             and u['id'] not in hostile_ids)
        self.enemy_groups = {}
        for u in self.hostiles:
            self.enemy_groups.setdefault(u.get('army') or u['id'], []).append(u)

    @staticmethod
    def combat_strength(members):
        return combat_strength(members)

    def defence(self, city):
        # Keep Dev19's stale garrison estimate and conservative corridor radius,
        # correcting only the infantry-equivalent weight of visible field levy.
        raw = super().defence(city)
        correction = sum(u['healthy']*.5 for u in self.hostiles
                         if u.get('kind') == 'levy' and distance(u, city) < 12000)
        return max(100, raw-correction)

    def run(self):
        commands = super().run()
        # Shared support logic reads its standard campaign keys. Preserve the
        # Dev19 keys too; those remain the authoritative recovery/rally intent.
        for command in commands:
            if command.get('west_task') == 'clan_campaign':
                command.update(vanilla_task='clan_campaign', vanilla_target=command['west_target'])
        commands = augment_commands(self.o, commands)
        # set_composition may immediately recruit, unload wounded and refill.
        # Appending it AFTER every reserved dispatch/create/mobilize avoids
        # consuming a donor or its food before an earlier planned transaction.
        # Transfers may delete an emptied party, so defer that party's preference.
        donors = {c.get('unit') for c in commands if c.get('type') == 'transfer'}
        pending = [u for u in self.parties if not u.get('battle')
                   and u['id'] not in donors
                   and u.get('cavalry_target') != self.o['limits']['party_cap']]
        pending.sort(key=lambda u: (self.cavalry_priority([u]), u['id']))
        for u in pending[:max(0, 100-len(commands))]:
            commands.append(dict(type='set_composition', unit=u['id'],
                                 cavalry_target=self.o['limits']['party_cap']))
        for command in commands:
            uid = command.get('unit')
            if command.get('type') not in ('move', 'attack', 'siege', 'raid'):
                continue
            unit = self.units.get(uid, {})
            cooldown = getattr(self, 'cavalry_cooldowns', {}).get(uid,
                (unit.get('order') or {}).get('west_cavalry_after', 0))
            if cooldown:
                command['west_cavalry_after'] = cooldown
        return commands

    def formations(self):
        return list(self.armies.values()) + [[u] for u in self.parties if not u['army']]

    @staticmethod
    def cavalry_priority(members):
        """Use cavalry in mobile patrols first, then ready field formations.

        Automatic settlement patrols have neither a composition command nor
        the lord-party speed bonus. They are not rewritten or credited here.
        """
        task = (members[0].get('order') or {}).get('west_task')
        local = task in ('local_patrol', 'clear_bandits', 'escort', 'harass')
        regular = [u for u in members if u.get('kind') == 'party']
        healthy = sum(u['healthy'] for u in regular)
        cavalry = sum(u.get('cavalry', 0) for u in regular)
        return (not local, cavalry/max(1, healthy), members[0]['id'])

    def collect_cavalry(self, members):
        """A bounded physical refit, never a remote transfer or extra reward.

        A full party swaps its infantry with real local garrison cavalry via
        ordinary city service, preserving both rosters' headcounts. Partial
        parties may also recruit under the unchanged engine's service rules.
        """
        leader = members[0]
        order = leader.get('order') or {}
        previous = order.get('west_cavalry_city') if order.get('west_task') == 'cavalry_refit' else None
        prior_city = self.bycity.get(previous)
        if previous and (order.get('west_cavalry_until', 0) <= self.hour
                         or (prior_city and distance(leader, prior_city) <= 500)):
            self.cavalry_cooldowns[leader['id']] = self.hour+168
            return False
        regular = [u for u in members if u.get('kind') == 'party']
        need = sum(max(0, u['healthy']-u.get('cavalry', 0)) for u in regular)
        if need < 10 or self.needs_recovery(members):
            return False
        if (order.get('type') in ('attack', 'siege', 'raid')
                or order.get('campaign_phase') == 'relief'
                or order.get('west_task') in ('escort', 'clear_bandits', 'harass',
                    'food_refit', 'await_supply', 'local_return', 'recover')
                or order.get('vanilla_task') in ('mobilization_rally', 'mobilization_prepare')):
            return False
        if order.get('west_cavalry_after', 0) > self.hour:
            return False
        # Do not remove a force already at its siege rendezvous for a refit.
        target = self.targets.get(order.get('west_target') or leader.get('army_target'))
        if target and distance(leader, target) <= 2500:
            return False
        days = self.group_days(members)
        total = sum(size(u) for u in members)
        full_total = len(regular)*self.o['limits']['party_cap'] + sum(
            size(u) for u in members if u.get('kind') != 'party')
        full_rate = max(1, full_total*self.o['limits']['field_ration'])
        food = sum(u['food'] for u in members)
        choices = []
        for city in self.safe:
            garrison = self.units.get(city.get('garrison'), {})
            if garrison.get('battle') or not garrison.get('cavalry', 0):
                continue
            # Earlier dispatch/create reservations can consume cavalry. Use a
            # lower bound rather than assuming all those departures were foot.
            removed = max(0, garrison.get('healthy', 0)-self.garrison[city['id']])
            available = max(0, garrison['cavalry']-removed-
                            self.cavalry_claimed.get(city['id'], 0))
            gain = min(need, available)
            if gain < min(20, need) or distance(leader, city) <= 500:
                continue
            travel = self.eta(leader, city)
            if not math.isfinite(travel) or travel > 48 or days <= 2*travel/24+4:
                continue
            if previous and city['id'] != previous:
                continue
            # Avoid long diversions from the current operational destination.
            if target:
                at = dict(leader, x=city['x'], y=city['y'])
                detour = travel+self.eta(at, target)-self.eta(leader, target)
                if detour > 24:
                    continue
            if not self.safe_route(leader, city) or not self.safe_route(city, leader):
                continue
            danger = self.combat_strength([u for u in self.hostiles if distance(u, city) < 8000])
            if danger*1.65 > self.combat_strength(members):
                continue
            # Carrying capacity/refill is real, not an expected remote benefit.
            # Reserve enough stock for a full refit and seven departure days,
            # in addition to the settlement's existing supply floor.
            carry = self.o.get('logistics_limits', {}).get('army_carry_days', 60) if leader.get('army') else self.o['limits'].get('carry_days', 30)
            draw = max(0, full_rate*carry-max(0, food-total*self.o['limits']['field_ration']*travel/24))
            floor = getattr(self, 'floors', {}).get(city['id'], 300000)
            available_food = self.stock[city['id']]-self.cavalry_food_claimed.get(city['id'], 0)
            if available_food < floor+max(draw, full_rate*7):
                continue
            choices.append((gain/(1+travel), -travel, city['id'], city, gain, draw))
        if not choices:
            if previous:
                self.cavalry_cooldowns[leader['id']] = self.hour+168
            return False
        _, _, _, city, gain, draw = max(choices, key=lambda row: row[:3])
        self.cavalry_claimed[city['id']] = self.cavalry_claimed.get(city['id'], 0)+gain
        self.cavalry_food_claimed[city['id']] = self.cavalry_food_claimed.get(city['id'], 0)+draw
        metadata = {key: order[key] for key in ('west_target', 'vanilla_base', 'west_home') if key in order}
        self.move(leader, city, west_task='cavalry_refit', west_cavalry_city=city['id'],
                  west_cavalry_until=order.get('west_cavalry_until', self.hour+72) if previous else self.hour+72,
                  **metadata)
        self.done.update(u['id'] for u in members)
        return True

    def stage(self, base, target):
        route = find_route(self.o['terrain'], base, target['x'], target['y'])
        if route is None:
            return None
        points = [(base['x'], base['y'])] + list(route)
        remaining = 2000.
        for a, b in reversed(list(zip(points, points[1:]))):
            length = math.dist(a, b)
            if length >= remaining:
                fraction = remaining / max(1, length)
                return dict(x=round(b[0] + (a[0]-b[0])*fraction),
                            y=round(b[1] + (a[1]-b[1])*fraction))
            remaining -= length
        return dict(x=base['x'], y=base['y'])

    def rendezvous(self, target):
        # A target has one physical meeting point for the whole country, even
        # when clans retain different local supply bases and approach routes.
        # Ownership, safe cities and navigation all come from our observation.
        anchors = [(self.length(city, target), city['id'], city) for city in self.safe]
        anchors = [row for row in anchors if math.isfinite(row[0])]
        if not anchors:
            return None
        return self.stage(min(anchors, key=lambda row: row[:2])[-1], target)

    def campaign_budget(self, members, target, battle_days):
        # Dev19's outward + battle + stocked-return budget, without its obsolete
        # 28/29-city terminal-siege exception. Never borrow a different clan's food.
        return super().campaign_budget(members, target, battle_days)

    def needs_recovery(self, members):
        # Original 650-man recovery floor is impossible for capped clan armies.
        regulars = [u for u in members if u.get('kind') != 'levy']
        healthy = sum(u['healthy'] for u in regulars)
        wounded = sum(u['wounded'] for u in regulars)
        # Formation readiness must agree with rally(). A legal 30+100 clan
        # must not immediately return to an empty city because it is not 75% full.
        return healthy < PARAMS['ready_min']*len(regulars) or wounded > (healthy+wounded)*.35

    def recover_campaign(self, members):
        if not self.needs_recovery(members):
            return False
        leader = members[0]
        prior = (leader.get('order') or {}).get('west_recover')
        city = next((c for c in self.safe if c['id'] == prior), None)
        if city and self.group_days(members) > self.eta(leader, city)/24 + 2:
            self.move(leader, city, west_task='recover', west_recover=city['id'], vanilla_base=city['id'])
        else:
            self.army_refit(members)
            if self.cmd and self.cmd[-1].get('unit') == leader['id']:
                base = self.cmd[-1].get('vanilla_base')
                if base:
                    self.cmd[-1].update(west_task='recover', west_recover=base)
        return True

    def relief(self):
        # Same physical clan relief as Dev19, but candidate travel must use
        # the siege-avoidance terrain the engine actually uses for wait orders.
        # A stage reachable from the selected friendly anchor is not proof it
        # is reachable from every candidate party on the other side of a pass.
        groups = self.formations()
        for alert in sorted(self.o.get('relief_requests', []),
                            key=lambda a: (a['assault_at'], a['city'])):
            enemy = [u for u in self.hostiles if u.get('battle')
                     and u['battle'] in (alert['battle'], alert.get('relief_battle'))]
            if not enemy:
                continue
            stage = None
            for city in sorted(self.safe, key=lambda c: (distance(c, alert), c['id']))[:3]:
                for x, y in reversed(find_route(self.o['terrain'], city, alert['x'], alert['y']) or []):
                    point = dict(x=x, y=y)
                    if (distance(point, alert) > 3500 and
                            find_route(relief_terrain(self.o['terrain'], alert, city), city, x, y) is not None):
                        stage = point
                        break
                if stage:
                    break
            if stage is None:
                continue
            choices = []
            for group in groups:
                if any(u.get('battle') or u['id'] in self.done for u in group):
                    continue
                leader = group[0]
                path = find_route(relief_terrain(self.o['terrain'], alert, leader), leader,
                                  stage['x'], stage['y'])
                if path is None:
                    continue
                points = [(leader['x'], leader['y'])]+list(path)
                length = sum(math.dist(a, b) for a, b in zip(points, points[1:]))
                eta = length/max(1, leader.get('movement_speed', self.o['speeds']['party']))
                if eta <= 120 and min(self.days(u) for u in group) > eta/24+4:
                    choices.append((eta, leader['id'], group))
            chosen = []
            strength = 0
            required = math.ceil(self.combat_strength(enemy)*1.15)
            for _, _, group in sorted(choices):
                chosen.append(group)
                strength += self.combat_strength(group)
                if strength >= required:
                    break
            if strength < required:
                continue
            for group in chosen:
                self.done.update(u['id'] for u in group)
                if not all(distance(u, stage) <= 100 for u in group):
                    self.move(group[0], stage, vanilla_task='relief', relief_action='wait',
                              relief_city=alert['city'])
            arrived = [g for g in chosen if all(distance(u, stage) <= 100 for u in g)]
            if sum(self.combat_strength(g) for g in arrived) < required:
                continue
            for group in arrived:
                leader = group[0]
                target = min(enemy, key=lambda e: (distance(leader, e), e['id']))
                if (leader.get('order') or {}).get('target') != target['id']:
                    self.cmd.append(dict(type='attack', unit=leader['id'], target=target['id'],
                                         vanilla_task='relief'))

    def intercept(self, members):
        """Restore Dev19's nearby superior-force interception, at clan scale."""
        leader = members[0]
        strength = self.combat_strength(members)
        days = self.group_days(members)
        prey = []
        for enemy in self.hostiles:
            total = self.combat_strength([u for u in self.hostiles
                if (u.get('army') and u['army'] == enemy.get('army'))
                or u['id'] == enemy['id'] or distance(u, enemy) < 3500])
            small = total < 90
            if strength < total*1.65 or distance(leader, enemy) > (8000 if small else 24000):
                continue
            if any(c['nation'] != self.n and distance(enemy, c) <= 1000 for c in self.o['cities']):
                continue
            eta = self.eta(leader, enemy)
            if eta > (16 if small else 40) or days < eta/24+10:
                continue
            if enemy['battle'] and not any(b['id'] == enemy['battle'] and b.get('city') for b in self.o['battles']):
                continue
            if days < self.campaign_budget(members, enemy, 8):
                continue
            prey.append((not bool(enemy['battle']), eta, -total, enemy['id'], enemy))
        if not prey:
            return False
        enemy = min(prey, key=lambda row: row[:4])[-1]
        order = leader.get('order') or {}
        if order.get('type') != 'attack' or order.get('target') != enemy['id']:
            meta = {key: order[key] for key in ('west_target', 'vanilla_base') if key in order}
            self.cmd.append(dict(type='attack', unit=leader['id'], target=enemy['id'],
                                 west_task='intercept', **meta))
        self.done.update(u['id'] for u in members)
        return True

    def raid_for_food(self, members):
        before = len(self.cmd)
        result = super().raid_for_food(members)
        if result and len(self.cmd) > before:
            order = members[0].get('order') or {}
            self.cmd[-1].update(west_task='raid_supply', **{key: order[key]
                for key in ('west_target', 'vanilla_base') if key in order})
        return result

    def supply_leg(self, members, destination):
        """A reachable stocked stop that makes actual route progress."""
        leader = members[0]
        days = self.group_days(members)
        rate = max(1, sum(size(u) for u in members)*self.o['limits']['field_ration'])
        remaining = self.length(leader, destination)
        options = []
        for city in self.safe:
            if distance(leader, city) <= 500 or self.stock[city['id']] < rate*4:
                continue
            travel = self.eta(leader, city)/24
            onward = self.length(city, destination)
            if travel+3 >= days or onward >= remaining-500:
                continue
            options.append((onward, travel, city['id'], city))
        return min(options, key=lambda row: row[:3])[-1] if options else None

    def local_home(self, members):
        leader = members[0]
        rate = max(1, sum(size(u) for u in members)*self.o['limits']['field_ration'])
        options = [c for c in self.safe if self.stock[c['id']] >= rate*3
                   and not self.units.get(c.get('garrison'), {}).get('battle')
                   and math.isfinite(self.eta(leader, c))]
        options.sort(key=lambda c:(self.eta(leader, c), c['id']))
        return next((c for c in options if self.safe_route(leader, c)), None)

    def sortie_safe(self, members, point, home, battle_days=0):
        """Budget only this physical group's food and observed escape route."""
        if not home or self.needs_recovery(members):
            return False
        leader = members[0]
        healthy = sum(u['healthy'] for u in members)
        if sum(u['wounded'] for u in members) > healthy*.35:
            return False
        at = dict(leader, x=point['x'], y=point['y'])
        needed = self.eta(leader, point)/24+battle_days+self.eta(at, home)/24+3
        if not math.isfinite(needed) or self.group_days(members) < needed:
            return False
        danger = self.combat_strength([e for e in self.hostiles if distance(e, point) < 8000])
        if danger*1.65 > self.combat_strength(members):
            return False
        return self.safe_route(leader, point) and self.safe_route(at, home)

    def local_return(self, members, home):
        if not home:
            self.army_refit(members, food_first=True)
            return True
        leader = members[0]
        order = leader.get('order') or {}
        meta = {key: order[key] for key in ('west_target', 'vanilla_base') if key in order}
        self.move(leader, home, west_task='local_return', west_home=home['id'], **meta)
        self.done.update(u['id'] for u in members)
        return True

    def productive_local(self, members, target=None, patrol=True):
        """Bounded protection, bandit clearing and conservative cart harassment.

        Presence and attacks use normal commands. No income or saved-cargo
        reward is fabricated; only the engine can deliver cargo or award loot.
        """
        leader = members[0]
        order = leader.get('order') or {}
        home = self.bycity.get(order.get('west_home'))
        rate = max(1, sum(size(u) for u in members)*self.o['limits']['field_ration'])
        if (not home or home['id'] in self.sieged or self.stock[home['id']] < rate*3
                or self.units.get(home.get('garrison'), {}).get('battle')):
            home = self.local_home(members)
        if not home:
            return False
        if order.get('west_task') == 'local_return' and distance(leader, home) > 500:
            return self.local_return(members, home)
        if self.needs_recovery(members) or self.group_days(members) < self.eta(leader, home)/24+4:
            return self.local_return(members, home)
        until = order.get('west_local_until', self.hour+LOCAL_DUTY_HOURS)
        if until <= self.hour:
            return False
        meta = dict(west_local_until=until, west_home=home['id'])
        for key in ('west_target', 'vanilla_base'):
            if key in order:meta[key]=order[key]
        if target:meta['west_target']=target['id']
        meta.setdefault('vanilla_base', home['id'])
        claimed = getattr(self, 'local_claims', set())
        self.local_claims = claimed
        strength = self.combat_strength(members)
        speed = leader.get('movement_speed', self.o['speeds'].get('army' if leader['army'] else 'party', 500))
        bandits = [u for u in self.units.values() if u['kind']=='bandit' and u['nation'] < 0]
        carts = [u for u in self.units.values() if u['nation']==self.n
                 and u['kind'] in ('village_cart','city_cart') and u.get('phase')!='idle'
                 and (u.get('cargo_food',0)>0 or u.get('cargo_recruits',0)>0 or u.get('regular_healthy',0)>0)]
        previous = order.get('target')
        chase_start = order.get('west_chase_since', self.hour)
        expired = previous if order.get('west_task') in ('clear_bandits','harass') and self.hour-chase_start >= CHASE_HOURS else None
        if expired:
            return self.local_return(members, home)

        prey = []
        for enemy in bandits:
            if enemy['id'] in claimed or self.eta(leader, enemy) > CHASE_HOURS:
                continue
            nearby = [b for b in bandits if distance(b, enemy) < 3500]
            if strength < sum(b['healthy'] for b in nearby)*1.5:
                continue
            battle = next((b for b in self.o['battles'] if b['id']==enemy['battle']), None)
            if enemy['battle'] and (not battle or battle.get('city') or battle.get('kind') not in ('ambush','skirmish')):
                continue
            gap = max(0, distance(leader, enemy)-1000)
            closing = speed-enemy.get('movement_speed',self.o['speeds'].get('bandit',750))
            if not enemy['battle'] and gap and (closing <= 0 or gap/closing > CHASE_HOURS):
                continue
            protected = [c for c in carts if (c['battle']==enemy['battle'] and c['battle']) or distance(c, enemy)<6000]
            corridor = distance(enemy, home) <= 18000 or protected or any(
                v['nation']==self.n and v.get('city')==home['id'] and distance(v, enemy)<8000
                for v in self.o['villages'])
            if not corridor or not self.sortie_safe(members, enemy, home, 1):
                continue
            prey.append((not bool(protected), enemy['id']!=previous, self.eta(leader, enemy), enemy['id'], enemy))
        if prey:
            enemy = min(prey, key=lambda row: row[:4])[-1]
            self.cmd.append(dict(type='attack', unit=leader['id'], target=enemy['id'], west_task='clear_bandits',
                                 west_chase_since=chase_start if previous==enemy['id'] else self.hour, **meta))
            claimed.add(enemy['id']);self.done.update(u['id'] for u in members)
            return True

        escorts = []
        for cart in carts:
            if cart['id'] in claimed or cart['battle'] or self.eta(leader, cart) > 8:
                continue
            threats = [b for b in bandits if distance(b, cart)<6000]
            if strength < sum(b['healthy'] for b in threats)*1.5 or not self.sortie_safe(members, cart, home, 1):
                continue
            value = cart.get('cargo_food',0)+cart.get('cargo_recruits',0)*3000+cart.get('regular_healthy',0)*3000
            escorts.append((not bool(threats), cart['id']!=order.get('west_cart'), -value,
                            self.eta(leader, cart), cart['id'], cart))
        if escorts:
            cart = min(escorts, key=lambda row: row[:5])[-1]
            self.move(leader, cart, west_task='escort', west_cart=cart['id'], **meta)
            claimed.add(cart['id']);self.done.update(u['id'] for u in members)
            return True

        prey = []
        for enemy in self.units.values():
            if enemy['nation'] < 0 or enemy['nation']==self.n or enemy['kind'] not in ('village_cart','city_cart'):
                continue
            if enemy['id'] in claimed or enemy['battle'] or self.eta(leader, enemy) > 6:
                continue
            # Enemy phase/cargo are hidden. Do not infer a loaded cart or attack
            # a potentially protected idle farmer at its publicly known village.
            if any(v['nation']==enemy['nation'] and distance(v, enemy)<=500 for v in self.o['villages']):
                continue
            if any(c['nation']==enemy['nation'] and distance(c, enemy)<=1000 for c in self.o['cities']):
                continue
            gap = max(0, distance(leader, enemy)-1000)
            closing = speed-enemy.get('movement_speed',self.o['speeds'].get(enemy['kind'],500))
            if gap and (closing <= 0 or gap/closing > CHASE_HOURS):
                continue
            enemy_strength = (enemy['healthy']+enemy.get('regular_healthy',0))*.5
            if strength < enemy_strength*1.65 or not self.sortie_safe(members, enemy, home, 8):
                continue
            prey.append((enemy['id']!=previous, self.eta(leader, enemy), enemy['id'], enemy))
        if prey:
            enemy = min(prey, key=lambda row: row[:3])[-1]
            self.cmd.append(dict(type='attack', unit=leader['id'], target=enemy['id'], west_task='harass',
                                 west_chase_since=chase_start if previous==enemy['id'] else self.hour, **meta))
            claimed.add(enemy['id']);self.done.update(u['id'] for u in members)
            return True
        if not patrol:
            return False
        villages = sorted((v for v in self.o['villages'] if v['nation']==self.n and v.get('city')==home['id']
                           and v.get('disabled_until',0)<=self.hour), key=lambda v:v['id'])
        points = [point for village in villages for point in (village, home)] or [home]
        index = order.get('west_patrol_index', -1)
        if order.get('west_task')=='local_patrol' and leader.get('path'):
            point = dict(x=order['x'], y=order['y'])
        else:
            index = (index+1)%len(points);point = points[index]
        if self.eta(leader, point) > until-self.hour or not self.sortie_safe(members, point, home, 1):
            return self.local_return(members, home)
        self.move(leader, point, west_task='local_patrol', west_patrol_index=index, **meta)
        self.done.update(u['id'] for u in members)
        return True

    def campaigns(self):
        self.relief()
        plans = {}
        stages = {}
        self.local_claims = set()
        self.cavalry_claimed = {}
        self.cavalry_food_claimed = {}
        self.cavalry_cooldowns = {}
        for members in sorted(self.formations(), key=self.cavalry_priority):
            leader = members[0]
            order = leader.get('order') or {}
            if any(u['id'] in self.done for u in members) or any(u['battle'] for u in members):
                continue
            if order.get('west_task') == 'local_return':
                home = self.bycity.get(order.get('west_home'))
                if not home or home['id'] in self.sieged:
                    home = self.local_home(members)
                if home and distance(leader, home) > 500:
                    self.local_return(members, home)
                    continue
            # Ready independent parties can defend the supply corridor before
            # their clan has formed. The campaign override used to erase this.
            if self.intercept(members):
                continue
            if self.collect_cavalry(members):
                continue
            local_task = order.get('west_task') in ('clear_bandits','escort','harass','local_patrol')
            if local_task and order.get('west_local_until', 0) > self.hour:
                if self.productive_local(members):
                    continue
            campaigning = leader['army'] or local_task or order.get('west_task') in (
                'clan_campaign', 'intercept', 'raid_supply', 'recover', 'army_refit',
                'food_refit', 'supply_leg', 'await_supply', 'local_return', 'cavalry_refit')
            if not campaigning:
                if self.raid_for_food(members) or self.productive_local(members, patrol=False):
                    continue
                continue
            self.done.update(u['id'] for u in members)
            if self.recover_campaign(members):
                continue
            target = self.targets.get(order.get('west_target') or leader.get('army_target'))
            if not target:
                target = self.target_for(members, force=True)
            base = self.bycity.get(order.get('vanilla_base'))
            if not base or base['id'] in self.sieged:
                base = self.base(leader)
            if not target or not base:
                if not self.productive_local(members):
                    self.army_refit(members)
                continue
            if target['id'] not in stages:
                stages[target['id']] = self.rendezvous(target)
            stage = stages[target['id']]
            if stage is None:
                self.army_refit(members)
                continue
            at_stage = dict(leader, x=stage['x'], y=stage['y'])
            detour = max(0, (self.eta(leader, stage)+self.eta(at_stage, target)-self.eta(leader, target))/24)
            budget = self.campaign_budget(members, target, 10)+detour
            if self.group_days(members) < max(24, budget):
                # Food raiding must precede the <24-day refit branch; the
                # inherited raid helper only acts below 18 days of real rations.
                if self.raid_for_food(members):
                    continue
                supply = self.support.get(leader['army'])
                if supply and supply['eta']/24+2 < self.group_days(members):
                    self.move(leader, leader, west_task='await_supply',
                              west_target=target['id'], vanilla_base=base['id'])
                    continue
                stop = self.supply_leg(members, stage)
                if stop:
                    self.move(leader, stop, west_task='supply_leg',
                              west_target=target['id'], vanilla_base=base['id'])
                elif not self.productive_local(members, target):
                    self.army_refit(members, food_first=True)
                continue
            plans.setdefault(target['id'], []).append((members, base, stage))
        for tid, formations in sorted(plans.items()):
            target = self.targets[tid]
            # Arrived formations must be near the target AND one another.
            # Different approach routes or remotely promised reinforcements do
            # not make a small force locally superior.
            for members, base, stage in formations:
                leader = members[0]
                arrived = all(distance(u, stage) <= 100 or distance(u, target) <= 2100 for u in members)
                local = [g for g, _, s in formations
                         if all(distance(u, leader) <= 500 for u in g)
                         and all(distance(u, s) <= 100 or distance(u, target) <= 2100 for u in g)]
                strength = self.combat_strength([u for g in local for u in g])
                meta = dict(west_task='clan_campaign', west_target=tid, vanilla_base=base['id'])
                if arrived and not target.get('stale') and strength >= self.required(target):
                    order = leader.get('order') or {}
                    if order.get('type') != 'siege' or order.get('target') != tid:
                        self.cmd.append(dict(type='siege', unit=leader['id'], target=tid, **meta))
                else:
                    order = leader.get('order') or {}
                    if arrived:
                        waiting = order.get('west_wait_since', self.hour)
                        if self.hour-waiting >= STAGE_WAIT_HOURS and self.productive_local(members, target):
                            continue
                        meta['west_wait_since'] = waiting
                    self.move(leader, stage, **meta)

    def rally(self):
        available = [u for u in self.parties if not u['army'] and not u['battle'] and u['id'] not in self.done]
        if not available or not self.safe or not self.targets:
            return
        clans = {}
        for unit in available:
            clans.setdefault(unit['clan'], []).append(unit)
        army_clans = {meta['clan'] for meta in self.o.get('army_metadata', {}).values()}
        if not self.o.get('army_metadata'):
            army_clans = {members[0]['clan'] for members in self.armies.values() if members}
        for clan, group in sorted(clans.items()):
            # Persist this clan's objective, not the first remote national order.
            orders = [u.get('order') or {} for u in group]
            existing = next((o for o in orders if o.get('west_target') in self.targets
                             and o.get('vanilla_base') in self.bycity
                             and o['vanilla_base'] not in self.sieged), None)
            if existing:
                base = self.bycity[existing['vanilla_base']]
                target = self.targets[existing['west_target']]
            else:
                choices = []
                for target in self.targets.values():
                    for base in self.safe:
                        if target['id'] not in base['neighbors']:
                            continue
                        journey = self.length(base, target)/500/24
                        gathering = sum(self.eta(u, base)/24 for u in group)/len(group)
                        choices.append((journey + gathering*.45 + self.required(target)/500,
                                        base['id'], target['id'], base, target))
                if not choices:
                    continue
                _, _, _, base, target = min(choices, key=lambda row: row[:3])
            # Form at a local friendly city before the long frontier march.
            # Assembly increases only the army's real carrying capacity. It is
            # not permission to attack with the remote national 650-man roster.
            prior = next((self.bycity[o['west_rally']] for o in orders
                          if o.get('west_rally') in self.bycity and o['west_rally'] not in self.sieged), None)
            muster = prior or min(self.safe, key=lambda c:(
                sum(self.eta(u, c) for u in group), c['id']))
            arrived = [u for u in group if distance(u, muster) <= 250
                       and u['healthy'] >= PARAMS['ready_min']
                       and u['wounded'] <= size(u)*.35 and self.days(u) >= 14]
            expected = [u for u in group if self.eta(u, muster) <= PARAMS['muster_wait']]
            needed_parties = min(2, len(expected)) if clan not in army_clans else 1
            total = sum(u['healthy'] for u in arrived)
            if (arrived and len(arrived) >= needed_parties
                    and total >= sum(u['healthy'] for u in expected)*.65):
                leader = arrived[0]
                if len(arrived) > 1 and clan not in army_clans:
                    self.cmd.append(dict(type='assemble', unit=leader['id'], units=[u['id'] for u in arrived[1:]],
                                         campaign_target=target['id']))
                    army_clans.add(clan)
                    moving = [leader]
                else:
                    moving = arrived
                for leader in moving:
                    # Explicit because assemble clears the pre-command order.
                    self.cmd.append(dict(type='move', unit=leader['id'], x=muster['x'], y=muster['y'],
                                         west_task='clan_campaign', west_target=target['id'], vanilla_base=base['id']))
                self.done.update(u['id'] for u in arrived)
            for unit in group:
                if unit['id'] in self.done:
                    continue
                self.done.add(unit['id'])
                home = self.base(unit)
                if not home:
                    continue
                meta = dict(west_task='rally', west_target=target['id'],
                            vanilla_base=base['id'], west_rally=muster['id'])
                order = unit.get('order') or {}
                # Daily ration deductions are discrete. An already-started
                # journey keeps a two-day reserve rather than oscillating at
                # the original five-day departure threshold every three hours.
                reserve = 2 if unit.get('path') and order.get('west_task') == 'rally' else 5
                if unit['healthy'] < PARAMS['ready_min'] or unit['wounded'] > size(unit)*.35:
                    self.claimed[home['id']] = self.claimed.get(home['id'], 0)+max(0, 150-unit['healthy'])
                    self.move(unit, home, west_task='refit', vanilla_base=home['id'])
                elif self.days(unit) >= self.eta(unit, muster)/24+reserve:
                    self.move(unit, muster, **meta)
                else:
                    stop = self.supply_leg([unit], muster)
                    if stop:
                        self.move(unit, stop, **meta)
                    else:
                        self.move(unit, home, west_task='refit', west_target=target['id'],
                                  vanilla_base=base['id'], west_rally=muster['id'])


def decide(observation, previous_outcomes=None):
    if observation.get('mode') != 'realmap' or not observation.get('logistics_limits', {}).get('rations_separate'):
        return []
    return WesternPlanner(observation).run()


def main():
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')
    for line in sys.stdin:
        request = json.loads(line)
        commands = decide(request['observation'], request.get('previous_outcomes'))
        print(json.dumps(dict(protocol_version=1, request_id=request['request_id'], commands=commands)), flush=True)


if __name__ == '__main__':
    main()
