"""Fixed one-hour simulation. Positions: millimap units; food: millirations.
No wall-clock, renderer, network or policy dependency lives here.
"""
from __future__ import annotations
import copy
import hashlib
import heapq
import json
import math
import random
from fractions import Fraction
from pathlib import Path
from .navigation import find_route,relief_terrain
from . import economy, military
from .layout import cities as city_positions, villages as village_positions

CONFIG = Path(__file__).with_name('config.json')


def dist(a, b):
    return math.isqrt((a['x']-b['x'])**2 + (a['y']-b['y'])**2)


def allocate(total, weights):
    """Integer proportional allocation, largest remainder, stable ID tie break."""
    weights = {str(k): int(v) for k, v in weights.items() if v > 0}
    s = sum(weights.values())
    if not s or total <= 0:
        return {k: 0 for k in weights}
    total = min(total, s)
    result = {k: total*v//s for k, v in weights.items()}
    order = sorted(weights, key=lambda k: (-(total*weights[k] % s), k))
    for k in order[:total-sum(result.values())]:
        result[k] += 1
    return result


class World:
    def __init__(self, seed=1, config=None):
        self.cfg = json.loads(CONFIG.read_text())
        if config and config.get('version') in ('0.1.1','0.1.2','0.1.3','0.1.4','0.1.5'):
            self.cfg=copy.deepcopy(config)  # Preserve complete legacy rules for replay.
        elif config:
            self.cfg.update(config)
        if config and 'version' in config and 'direct_garrison_delivery' not in config:
            self.cfg.pop('direct_garrison_delivery',None)  # Exact legacy replays keep their original rules.
            self.cfg.pop('garrison_expansion_threshold',None)
        mode = self.cfg.get('mode', 'duel')
        if mode not in ('duel', 'rural', 'realmap'):
            raise ValueError('未知游戏模式')
        if mode == 'realmap' and not (config and 'version' in config):
            # New games only: full save/replay configurations retain their own profile.
            overrides = config or {}
            self.cfg.update(days=overrides.get('days', 840),
                            decision_hours=overrides.get('decision_hours', 3),
                            local_baseline='v0.4.1-castles-cavalry',
                            castle_logistics=True,city_crew=50,city_cargo=2000000,city_reserve=150000,
                            supply_max_distance=120000,
                            realmap_profile='plan_a_10y_v1')
            self.cfg['speeds'] = {**self.cfg['speeds'], 'party': 1000, 'army': 500,
                                  'village_cart': 500, 'city_cart': 500, 'bandit': 750,
                                  **overrides.get('speeds', {})}
        if mode == 'rural':
            self.cfg['mode'] = mode
            if not config or 'version' not in config:
                self.cfg['rural_clans'] = 6
            if self.cfg.get('rural_clans') == 6:
                cap = self.cfg['clan_party_cap']
                if type(cap) is not int or cap not in (2, 3, 4):
                    raise ValueError('单国六家族模式的部队上限须为2、3或4')
            self.cfg['days'] = 840  # Existing calendar: 84 days/year, fixed ten-year challenge.
        self.seed = seed
        self.rng = random.Random(seed)
        self.hour = 0
        self.seq = 0
        self.cities = {}
        self.villages = {}
        self.units = {}
        self.battles = {}
        self.armies = {}
        self.events = []
        self.event_seq = 0
        self.history = []
        self.commands = []
        self.known = {'0': {}, '1': {}}
        self.result = None
        self.next_bandits={str(n):self.rng.randint(self.cfg['bandit_spawn_min'],self.cfg['bandit_spawn_max']) for n in (0,1)}
        self.stats = {'war_dead': 0, 'starved': 0, 'defeated_removed': 0,
                      'food_lost': 0, 'recruits_lost': 0, 'bandit_spawns':0, 'bandits_killed':0,
                      'bandit_cart_losses':0,'bandit_food_lost':0,'bandit_recruits_lost':0,
                      'delivered_food':0,'delivered_recruits':0,'bandit_flights':0}
        if military.enabled(self):self.stats.update(cavalry_trained=0,supply_dispatches=0,supply_delivered_food=0,supply_fetched_food=0)
        if mode == 'realmap':
            from .real_map import initialize
            initialize(self)
        else:
            # Grid is only for terrain/pathfinding, not a road graph.
            self.terrain = []
            for y in range(40):
                row = []
                for x in range(60):
                    # Rotation symmetry; no central empty corridor or separating wall.
                    mx,my=(x,y) if x<30 else (59-x,39-y)
                    row.append(1 if (mx*7+my*3)%23<2 else 0)
                self.terrain.append(row)
            positions=city_positions(legacy=self.cfg['version']=='0.1.1')
            homes=village_positions(seed,legacy=self.cfg['version']=='0.1.1')
            for n in range(2):
                for j in range(6):
                    x,y=positions[n*6+j]
                    cid = f'c{n}{j}'
                    clan = n*6+j
                    city = dict(id=cid, name=f'{"蓝" if n == 0 else "赤"}{j+1}城',
                                nation=n, clan=clan, x=x, y=y, food=self.cfg['initial_city_food'],
                                recruits=0, garrison=f'g{n}{j}', convoy=None, neighbors=[])
                    self.cities[cid] = city
                    self.terrain[y//2000][x//2000] = 0
                    self.terrain[39-y//2000][59-x//2000] = 0
                    self.new_unit('garrison', n, clan, self.cfg['initial_garrison'], x, y,
                                  uid=city['garrison'], home=cid)
                    if self.cfg.get('militia_cap'):
                        city.update(militia=f'm{n}{j}',militia_reset_hour=-1)
                        self.new_unit('militia',n,clan,self.cfg['militia_initial'],x,y,uid=city['militia'],home=cid)
                    self.new_unit('party', n, clan, self.cfg['initial_soldiers'], x, y,
                                  food=self.cfg['initial_soldiers']*self.cfg['field_ration']*self.cfg['carry_days'])
                    for k in range(3):
                        vx,vy=homes[(n,j,k)]
                        vid = f'v{n}{j}{k}'
                        v = dict(id=vid, name=f'{city["name"]}·村{k+1}', city=cid, nation=n,
                                 x=vx, y=vy, population=self.cfg['population']-self.cfg['village_crew'],
                                 food=0, recruits=0, disabled_until=0, cart=None, raid=None)
                        self.villages[vid] = v
                        self.terrain[v['y']//2000][v['x']//2000] = 0
                        self.terrain[39-v['y']//2000][59-v['x']//2000] = 0
                        u = self.new_unit('village_cart', n, clan, self.cfg['village_crew'],
                                          v['x'], v['y'], home=vid)
                        v['cart'] = u['id']
            if self.cfg.get('mode') == 'rural':
                for obj in list(self.cities.values()) + list(self.villages.values()) + list(self.units.values()):
                    obj['nation'] = 0
                    if self.cfg.get('rural_clans') == 6 and 'clan' in obj:
                        obj['clan'] //= 2
                    if 'name' in obj:
                        obj['name'] = obj['name'].replace('赤', '东').replace('蓝', '西')
            for c in self.cities.values():
                c['neighbors'] = sorted(d['id'] for d in self.cities.values() if d != c and
                    dist(c,d)<=33000)
        self.update_known()
        self.emit('start', '世界初始化', seed=seed)
        economy.sample(self)

    def clan_nation(self, clan):
        if self.cfg.get('mode')=='realmap':return self.map_clans.get(str(clan),{}).get('nation',-1)
        return clan//6

    def position_passable(self,x,y):
        if self.cfg.get('mode')=='realmap':
            from .real_map import mesh
            return mesh().face(x,y) is not None
        return self.passable(x//2000,y//2000)

    def ident(self, prefix):
        self.seq += 1
        return f'{prefix}{self.seq:05d}'

    def new_unit(self, kind, nation, clan, healthy, x, y, uid=None, home=None, food=0):
        uid = uid or self.ident('u')
        u = dict(id=uid, kind=kind, nation=nation, clan=clan, healthy=healthy, wounded=0,
                 x=x, y=y, food=food, cargo_food=0, cargo_recruits=0, home=home,
                 order=None, path=[], battle=None, army=None, born=self.hour,
                 last_battle=-1000, hungry=False, phase='idle', war_losses=0, origin_x=x, origin_y=y)
        if military.enabled(self):u.update(cavalry=0,cavalry_wounded=0)
        self.units[uid] = u
        return u

    def emit(self, kind, text, **extra):
        self.event_seq += 1
        self.events.append(dict(id=self.event_seq,hour=self.hour,kind=kind,text=text,**extra))
        # Operational noise must not evict military events from the observer log.
        if len(self.events)>2400:
            major=[e for e in self.events if e.get('important')][-1000:]
            recent=self.events[-600:]
            self.events=sorted({e['id']:e for e in major+recent}.values(),key=lambda e:e['id'])

    def nation_name(self,nation):
        if self.cfg.get('mode')=='realmap' and nation in (0,1):return ('西帝国','北帝国')[nation]
        return '蓝国' if nation==0 else '赤国' if nation==1 else '劫匪'

    def unit_name(self,u):
        if u['kind']=='militia':return self.nation_name(u['nation'])+'·'+self.cities[u['home']]['name']+'民兵'
        if u['kind']=='garrison':
            return self.nation_name(u['nation'])+'·'+self.cities[u['home']]['name']+'驻军'
        if u['kind']=='village_cart':
            return self.nation_name(u['nation'])+'·'+self.villages[u['home']]['name']+'运输队'
        if u['kind']=='bandit':return '劫匪'+u['id']
        kind='部队' if u['kind']=='party' else '运粮队'
        clan_name=self.map_clans[str(u["clan"])]["name"] if self.cfg.get("mode")=="realmap" else f"家族{u['clan']%6+1}"
        return f"{self.nation_name(u['nation'])}·{clan_name}·{kind}{u['id']}"

    def location_name(self,o):
        places=list(self.cities.values())+list(self.villages.values())
        if not places:return '野外'
        p=min(places,key=lambda p:(dist(p,o),p['id']))
        distance=dist(p,o)/1000
        return p['name'] if distance<=1 else f"{p['name']}附近（{distance:.1f}单位）"

    def observer_totals(self):
        """Privileged spectator-only data. Never included in policy observations."""
        totals=[]
        for n in (0,1):
            own=[u for u in self.units.values() if u['nation']==n]
            military=[u for u in own if u['kind'] in ('party','garrison','city_cart','militia')]
            village_population=sum(v['population'] for v in self.villages.values() if v['nation']==n)
            transport_population=sum(self.size(u) for u in own if u['kind']=='village_cart')
            totals.append(dict(nation=n,population=village_population+transport_population,
                village_population=village_population,transport_population=transport_population,
                military=sum(self.size(u) for u in military),healthy=sum(u['healthy'] for u in military),
                wounded=sum(u['wounded'] for u in military),
                militia=sum(self.size(u) for u in military if u['kind']=='militia'),
                garrison=sum(self.size(u) for u in military if u['kind']=='garrison'),
                field=sum(self.size(u) for u in military if u['kind']=='party'),
                parties=sum(u['kind']=='party' for u in military),
                logistics=sum(self.size(u) for u in military if u['kind']=='city_cart'),
                cities=sum(c['nation']==n for c in self.cities.values()),
                armies=sum(any(self.units[i]['nation']==n for i in ids if i in self.units) for ids in self.armies.values())))
        return totals

    def observer_events(self):
        return copy.deepcopy([e for e in self.events if e.get('important') or e['kind']=='transport_lost'][-400:])

    def size(self, u):
        return u['healthy']+u['wounded']

    def food_cap(self, u):
        return self.size(u)*self.cfg['field_ration']*self.cfg['carry_days']

    def city_at(self, u):
        return next((c for c in self.cities.values() if c['nation'] == u['nation'] and dist(c,u)<=500), None)

    def can_siege(self,nation,cid):
        target=self.cities.get(cid)
        if not target or target['nation']==nation:return False
        if not self.cfg.get('frontier_only',False):return True
        return any(c['nation']==nation and cid in c['neighbors'] for c in self.cities.values())

    def bandit_can_target(self,u):
        if u['kind']!='village_cart':return False
        if not self.cfg.get('protect_village_carts',False):return True
        home=self.villages.get(u['home'])
        return bool(home and u['phase'] in ('outbound','return') and dist(u,home)>500)

    def besieged(self, cid):
        return any(b['city'] == cid for b in self.battles.values())

    def trim_food(self, u):
        if u['kind'] not in ('party',):
            return
        excess = max(0, u['food']-self.food_cap(u))
        if excess:
            c = self.city_at(u)
            put = min(excess, self.cfg['warehouse']-c['food']) if c else 0
            if c:
                c['food'] += put
            u['food'] -= excess
            self.stats['food_lost'] += excess-put

    def remove(self, uid, reason='removed'):
        u = self.units.get(uid)
        if not u:
            return
        if reason in ('defeated','starved'):
            economy.transport(self,'lost',u)
            cause='战败覆灭' if reason=='defeated' else '因断粮耗尽兵员'
            if u['kind'] in ('party','garrison','city_cart') and (u['kind']!='garrison' or self.size(u)>0 or reason=='starved'):
                self.emit('unit_destroyed',f"{self.unit_name(u)}在{self.location_name(u)}{cause}",important=True,nation=u['nation'],unit=uid,x=u['x'],y=u['y'])
            elif u['kind']=='village_cart':
                self.emit('transport_lost',f"{self.unit_name(u)}在{self.location_name(u)}被消灭",nation=u['nation'],unit=uid,x=u['x'],y=u['y'])
        if reason == 'defeated':
            if u['kind']=='bandit':self.stats['bandits_killed']+=1
            if u['kind']=='village_cart' and '-1' in self.battles.get(u['battle'],{}).get('sides',{}):
                self.stats['bandit_cart_losses']+=1
                self.stats['bandit_food_lost']+=u['cargo_food']
                self.stats['bandit_recruits_lost']+=u['cargo_recruits']
            self.stats['defeated_removed'] += self.size(u)+u['cargo_recruits']
            self.stats['recruits_lost'] += u['cargo_recruits']
        self.stats['food_lost'] += u['food']+u['cargo_food']
        if u['kind'] in ('garrison','militia'):
            if military.enabled(self):u.update(cavalry=0,cavalry_wounded=0)
            u.update(healthy=0, wounded=0, food=0, cargo_food=0, cargo_recruits=0, battle=None)
            return
        for v in self.villages.values():
            if v['cart'] == uid:
                v['cart'] = None
        for c in self.cities.values():
            if c['convoy'] == uid:
                c['convoy'] = None
        aid = u['army']
        del self.units[uid]
        if aid in self.armies:
            self.armies[aid] = [i for i in self.armies[aid] if i != uid]
            if not self.armies[aid]:
                destroyed=reason in ('defeated','starved')
                self.emit('army_destroyed' if destroyed else 'army_disbanded',f"{self.nation_name(u['nation'])}军团{aid}在{self.location_name(u)}"+('全部覆灭' if destroyed else '撤编'),important=True,nation=u['nation'],army=aid)
                del self.armies[aid]

    def passable(self, x, y):
        if self.cfg.get('mode')=='realmap':return self.position_passable(x*2000+1000,y*2000+1000)
        return 0 <= x < 60 and 0 <= y < 40 and self.terrain[y][x] != 2

    def route(self, u, x, y):
        return find_route(self.terrain,u,x,y)

    def go(self, u, x, y, order=None):
        path = self.route(u,x,y)
        if path is None:
            raise ValueError('目的地不可达')
        u['path'] = path
        u['order'] = order or {'type':'move','x':x,'y':y}

    def members(self, u):
        return [self.units[i] for i in self.armies.get(u['army'], [u['id']]) if i in self.units]

    def command(self, nation, cmd, record=True):
        """Validate on own state/observation. No enemy hidden-state feedback."""
        if record:
            self.commands.append({'hour':self.hour,'nation':nation,'command':copy.deepcopy(cmd)})
        try:
            if self.result:
                raise ValueError('对局已结束')
            if nation not in ((0,) if self.cfg.get('mode') == 'rural' else (0,1)) or not isinstance(cmd,dict):
                raise ValueError('非法命令')
            op = cmd.get('type')
            if op=='recruit' and self.cfg.get('direct_garrison_delivery'):
                raise ValueError('新规则已取消招募，请从驻军调拨人员')
            if op in ('recruit','create','dispatch'):
                c = self.cities.get(cmd.get('city'))
                if not c or c['nation'] != nation or self.besieged(c['id']):
                    raise ValueError('城市不可用')
                count = cmd.get('count',0)
                if op in ('recruit','create') and (type(count) is not int or count <= 0):
                    raise ValueError('人数必须是正整数')
                if op == 'create':
                    clan = cmd.get('clan',c['clan'])
                    if type(clan) is not int or self.clan_nation(clan) != nation:
                        raise ValueError('家族无效')
                    if sum(u['kind']=='party' and u['clan']==clan for u in self.units.values())>=self.cfg['clan_party_cap']:
                        raise ValueError('家族部队名额已满')
                    source=cmd.get('source','garrison' if self.cfg.get('direct_garrison_delivery') else 'recruits')
                    if source=='recruits' and self.cfg.get('direct_garrison_delivery'):raise ValueError('新规则没有待招募兵源，请从驻军建队')
                    donor=None
                    if source!='recruits':
                        if self.cfg['version'] not in ('0.1.4','0.1.5','0.1.6'):raise ValueError('旧规则不支持从驻军/部队新建')
                        donor=self.units.get(c['garrison'] if source=='garrison' else source)
                        if not donor or donor['kind'] not in ('party','garrison') or donor['nation']!=nation or donor['battle'] or donor['army'] or dist(donor,c)>500:
                            raise ValueError('兵力来源不可用')
                        if donor['kind']=='party' and self.size(donor)<=count:raise ValueError('拆分后原部队须保留人员')
                    available=donor['healthy'] if donor else c['recruits']
                    if count > self.cfg['party_cap'] or count > available:
                        raise ValueError('兵源或容量不足')
                    cavalry=0
                    if donor:
                        if military.enabled(self):cavalry=military.take_cavalry(donor,count,troop_type=cmd.get('troop_type'))
                        donor['healthy']-=count
                        self.trim_food(donor)
                    else:c['recruits'] -= count
                    u = self.new_unit('party',nation,clan,count,c['x'],c['y'])
                    if military.enabled(self):u['cavalry']=cavalry
                    self.refill(u,c)
                    self.emit('party_created',f"{self.unit_name(u)}在{c['name']}组建：{count}人",nation=nation,unit=u['id'],important=True)
                    return {'ok':True,'unit':u['id']}
                if op == 'recruit':
                    u = self.units.get(cmd.get('unit',c['garrison']))
                    if not u or u['nation'] != nation or dist(u,c)>500 or u['battle'] or u['kind'] not in ('party','garrison'):
                        raise ValueError('接收部队不可用')
                    cap = self.cfg['garrison_cap'] if u['kind']=='garrison' else self.cfg['party_cap']
                    if count > c['recruits'] or self.size(u)+count>cap:
                        raise ValueError('兵源或容量不足')
                    c['recruits'] -= count
                    u['healthy'] += count
                    return {'ok':True}
                if military.enabled(self):return military.dispatch(self,nation,c,cmd)
                dst = self.cities.get(cmd.get('destination'))
                if not dst or dst['nation'] != nation or dst['id'] not in c['neighbors'] or c['convoy']:
                    raise ValueError('运粮目的地或名额不可用')
                g = self.units[c['garrison']]
                reserve = self.cfg['city_reserve']
                if g['healthy']<self.cfg['city_crew'] or c['food']<reserve:
                    raise ValueError('驻军或粮食不足')
                amount = cmd.get('food', self.cfg['city_cargo'])
                if type(amount) is not int or amount<0:
                    raise ValueError('粮食数量无效')
                cargo = min(amount,self.cfg['city_cargo'],c['food']-reserve)
                path = self.route(g,dst['x'],dst['y'])
                if path is None:
                    raise ValueError('目的地不可达')
                u = self.new_unit('city_cart',nation,c['clan'],self.cfg['city_crew'],c['x'],c['y'],home=c['id'],food=reserve)
                g['healthy'] -= self.cfg['city_crew']
                c['food'] -= reserve+cargo
                u.update(cargo_food=cargo, phase='outbound', destination=dst['id'])
                c['convoy'] = u['id']
                self.go(u,dst['x'],dst['y'])
                return {'ok':True,'unit':u['id']}
            u = self.units.get(cmd.get('unit'))
            if not u or u['nation'] != nation or u['battle']:
                raise ValueError('部队不可用')
            if op == 'discard':
                amount=cmd.get('food',0)
                if u['kind']!='city_cart' or type(amount) is not int or amount<=0 or amount>u['cargo_food']:
                    raise ValueError('只能丢弃已有货粮')
                u['cargo_food']-=amount
                self.stats['food_lost']+=amount
                return {'ok':True}
            if op == 'supply':
                target = self.units.get(cmd.get('target'))
                if u['kind']!='city_cart' or not target or target['kind']!='party' or target['nation']!=nation or target['battle'] or dist(u,target)>1000:
                    raise ValueError('不能交接补给')
                for m in self.members(target):
                    amount = min(u['cargo_food'],max(0,self.food_cap(m)-m['food']))
                    u['cargo_food'] -= amount
                    m['food'] += amount
                return {'ok':True}
            if op == 'transfer':
                v = self.units.get(cmd.get('target'))
                count = cmd.get('count',0)
                c = self.city_at(u)
                if not c or self.besieged(c['id']) or not v or v['nation']!=nation or v['battle'] or dist(v,c)>500 or u['kind'] not in ('party','garrison') or v['kind'] not in ('party','garrison') or u==v:
                    raise ValueError('不能转移人员')
                cap = self.cfg['garrison_cap'] if v['kind']=='garrison' else self.cfg['party_cap']
                wounded = bool(cmd.get('wounded',False))
                field = 'wounded' if wounded else 'healthy'
                if type(count) is not int or count<=0 or count>u[field] or self.size(v)+count>cap:
                    raise ValueError('人数或容量无效')
                if military.enabled(self):military.transfer(u,v,count,field,cmd.get('troop_type'))
                else:
                    u[field] -= count
                    v[field] += count
                self.trim_food(u)
                if not self.size(u) and u['kind']=='party':
                    # Return its remaining food rather than creating it twice.
                    self.remove(u['id'])
                return {'ok':True}
            if u['kind'] != 'party':
                raise ValueError('此命令需要领主部队')
            if op == 'set_composition':
                target=cmd.get('cavalry_target')
                if not military.enabled(self) or type(target) is not int or not 0<=target<=self.cfg['party_cap']:raise ValueError('骑兵目标须在部队容量以内')
                u['cavalry_target']=target
                c=self.city_at(u)
                if c:self.service_party(u,c)
                return {'ok':True}
            if op == 'set_strength':
                target=cmd.get('target')
                if self.cfg['version'] not in ('0.1.4','0.1.5','0.1.6') or type(target) is not int or not 1<=target<=self.cfg['party_cap']:
                    raise ValueError('整补目标须在部队容量以内')
                if self.cfg.get('direct_garrison_delivery'):target=max(target,u.get('reserve_refill_target',0))
                u['refill_target']=target
                return {'ok':True}
            if op == 'assemble':
                ids = sorted(set(cmd.get('units',[])+[u['id']]))
                members = [self.units.get(i) for i in ids]
                if len(ids)<2 or any(not m or m['kind']!='party' or m['nation']!=nation or m['battle'] or m['army'] or dist(m,u)>500 for m in members):
                    raise ValueError('军团成员不可用')
                aid = self.ident('a')
                self.armies[aid] = ids
                for m in members:
                    m.update(army=aid,x=u['x'],y=u['y'],path=[],order=None)
                    if self.cfg['version'] in ('0.1.4','0.1.5','0.1.6'):m.update(army_formed=self.hour,army_target=cmd.get('campaign_target'))
                self.emit('army_assembled',f"{self.nation_name(nation)}在{self.location_name(u)}集结军团{aid}：{len(ids)}支部队、{sum(self.size(m) for m in members)}人",important=True,nation=nation,army=aid,members=ids,x=u['x'],y=u['y'])
                return {'ok':True,'army':aid}
            if op == 'disband':
                members = self.members(u)
                aid = u['army']
                if not aid:
                    raise ValueError('未组成军团')
                total = sum(m['food'] for m in members)
                caps = {m['id']: self.food_cap(m) for m in members}
                shares = allocate(min(total,sum(caps.values())),caps)
                self.stats['food_lost'] += max(0,total-sum(caps.values()))
                for m in members:
                    m.update(army=None,food=shares.get(m['id'],0),path=[],order=None)
                del self.armies[aid]
                self.emit('army_disbanded',f"{self.nation_name(nation)}军团{aid}在{self.location_name(u)}解散",important=True,nation=nation,army=aid)
                return {'ok':True}
            members = self.members(u)
            if any(m['battle'] for m in members):
                raise ValueError('军团交战中')
            if op == 'stop':
                for m in members:
                    m.update(path=[],order=None)
                return {'ok':True}
            if op not in ('move','attack','siege','raid'):
                raise ValueError('未知命令')
            order = copy.deepcopy(cmd)
            if op=='siege' and 'award_clan' in cmd:
                clan=cmd['award_clan']
                if type(clan) is not int or self.clan_nation(clan)!=nation:
                    raise ValueError('受封家族无效')
            if op == 'move':
                x,y = cmd.get('x'),cmd.get('y')
                if type(x) is not int or type(y) is not int or not (0<=x<(1010000 if self.cfg.get('mode')=='realmap' else 120000) and 0<=y<(940000 if self.cfg.get('mode')=='realmap' else 80000)):
                    raise ValueError('坐标无效')
            else:
                if not u['healthy']:
                    raise ValueError('没有健康士兵')
                obs = self.observe(nation)
                items = obs['units'] if op=='attack' else obs['cities'] if op=='siege' else obs['villages']
                t = next((i for i in items if i['id']==cmd.get('target') and not i.get('stale')),None)
                if not t or t['nation']==nation:
                    raise ValueError('目标不可见或不是敌方')
                if op=='siege' and not self.can_siege(nation,t['id']):
                    raise ValueError('不能跳城：目标须与己方控制的城市相邻')
                if op=='attack' and t.get('kind') in ('party','garrison','militia'):
                    city=self.city_at(self.units[t['id']])
                    if city and not self.can_siege(nation,city['id']):
                        raise ValueError('目标驻于非前沿敌城，须先夺取相邻城市')
                x,y = t['x'],t['y']
                order['last_x'],order['last_y'] = x,y
            path = self.route(u,x,y)
            if self.cfg.get('external_relief') and op=='move' and order.get('relief_action')=='wait':
                relief_city=self.cities.get(order.get('relief_city'))
                if relief_city and relief_city['nation']==nation:path=find_route(relief_terrain(self.terrain,relief_city,u),u,x,y)
            if path is None:
                raise ValueError('目的地不可达')
            for m in members:
                if m['kind']=='party':
                    c = self.city_at(m)
                    if c and not self.besieged(c['id']):
                        self.service_party(m,c)
                        self.refill(m,c)
                m['order'] = copy.deepcopy(order)
                m['path'] = copy.deepcopy(path)
            if op=='move' and order.get('campaign_phase')=='relief':
                cid=order.get('relief_city')
                if cid in self.cities:self.emit('relief_departed',f"{self.unit_name(u)}"+('前往' + self.cities[cid]['name']+'城外会合' if self.cfg.get('external_relief') else '赶往'+self.cities[cid]['name']+'支援'),nation=nation,city=cid,unit=u['id'],important=True)
            return {'ok':True}
        except (ValueError,TypeError,KeyError) as exc:
            return {'ok':False,'error':str(exc)}

    def service_party(self,u,c):
        """Transfer existing soldiers, then recruit and load from actual city stocks."""
        if not self.cfg.get('auto_city_service',False) or u['kind']!='party' or u['battle'] or c['nation']!=u['nation'] or self.besieged(c['id']):return
        if military.enabled(self):return military.service(self,u,c)
        g=self.units[c['garrison']]
        direct=self.cfg.get('direct_garrison_delivery',False)
        if direct and (g['battle'] or g['army'] or dist(g,c)>500):return
        moved=min(u['wounded'],max(0,self.cfg['garrison_cap']-self.size(g)))
        u['wounded']-=moved;g['wounded']+=moved
        if moved:g['last_battle']=max(g['last_battle'],u['last_battle'])
        reserve=self.cfg.get('expansion_reserve',0) if sum(p['kind']=='party' and p['clan']==c['clan'] for p in self.units.values())<self.cfg['clan_party_cap'] else 0
        target=min(self.cfg['party_cap'],max(u.get('refill_target',self.cfg['party_cap']),u.get('reserve_refill_target',0) if direct else 0))
        if direct:
            taken=min(max(0,g['healthy']-reserve),max(0,target-self.size(u)))
            g['healthy']-=taken;u['healthy']+=taken
            extra=min(max(0,g['healthy']-self.cfg.get('garrison_expansion_threshold',400)),max(0,self.cfg['party_cap']-self.size(u)))
            if extra:
                g['healthy']-=extra;u['healthy']+=extra
                u['reserve_refill_target']=max(u.get('reserve_refill_target',0),u['healthy'])
                u['refill_target']=max(u.get('refill_target',150),u['reserve_refill_target'])
        else:
            recruited=min(max(0,c['recruits']-reserve),max(0,target-self.size(u)))
            c['recruits']-=recruited;u['healthy']+=recruited
        self.trim_food(u)
        self.refill(u,c)

    def refill(self, u, c):
        amount = min(c['food'],max(0,self.food_cap(u)-u['food']))
        c['food'] -= amount
        u['food'] += amount

    def visible(self, nation, target):
        for c in self.cities.values():
            if c['nation']==nation and dist(c,target)<=10000:
                return True
        for v in self.villages.values():
            if v['nation']==nation and dist(v,target)<=6000:
                return True
        return any(u['nation']==nation and self.size(u)>0 and dist(u,target)<=self.cfg['vision'][u['kind']]
                   for u in self.units.values() if u['kind']!='garrison')

    def update_known(self):
        for n in (0,1):
            for category, items in (('cities',self.cities),('villages',self.villages)):
                for obj in items.values():
                    visible = obj['nation']==n or self.visible(n,obj)
                    key = obj['id']
                    if visible or self.hour==0:
                        v = {k:obj[k] for k in ('id','name','x','y','nation')}
                        if self.cfg.get('mode')=='realmap':v.update(map_x=obj['map_x'],map_y=obj['map_y'],source_id=obj['source_id'])
                        if military.enabled(self) and category=='cities':v.update(settlement_type=obj['settlement_type'],supply_neighbors=obj['supply_neighbors'])
                        v.update(category=category,seen=self.hour)
                        if category=='villages':
                            v['city']=obj['city']
                        if visible:
                            if category=='cities':
                                g=self.units[obj['garrison']]
                                v.update(healthy=g['healthy'],wounded=g['wounded'])
                                if military.enabled(self):v.update(cavalry=g['cavalry'],cavalry_wounded=g['cavalry_wounded'])
                                if obj.get('militia'):
                                    militia=self.units[obj['militia']]
                                    v.update(militia_healthy=militia['healthy'],militia_wounded=militia['wounded'])
                            else:
                                v.update(population=obj['population'],disabled_until=obj['disabled_until'])
                        self.known[str(n)][key]=v

    def observe(self, nation=None):
        obs=self._observe(nation)
        if military.enabled(self):
            obs['castle_logistics']=True
            obs['logistics_limits']={k:self.cfg[k] for k in ('city_crew','city_cargo','city_reserve','supply_max_distance')}
            for u in obs['units']:
                actual=self.units[u['id']]
                u['cavalry']=actual['cavalry'];u['cavalry_wounded']=actual['cavalry_wounded']
                u['movement_speed']=military.speed(actual,self.cfg['speeds'],self.members(actual))
        return obs

    def _observe(self, nation=None):
        if nation is None:
            return {'hour':self.hour,'seed':self.seed,'result':copy.deepcopy(self.result),
                    'mode':self.cfg.get('mode','duel'),'rural_score':self.rural_score() if self.cfg.get('mode')=='rural' else None,
                    'direct_garrison_delivery':self.cfg.get('direct_garrison_delivery',False),
                    'cities':copy.deepcopy(list(self.cities.values())),
                    'villages':copy.deepcopy(list(self.villages.values())),
                    'units':copy.deepcopy(list(self.units.values())),
                    'battles':copy.deepcopy(list(self.battles.values())),
                    'events':copy.deepcopy(self.events[-14:]),'terrain':self.terrain,
                    'armies':copy.deepcopy(self.armies),
                    **({'map_info':copy.deepcopy(self.map_info)} if self.cfg.get('mode')=='realmap' else {})}
        out={'hour':self.hour,'nation':nation,'result':copy.deepcopy(self.result),
             'cities':[],'villages':[],'units':[],'terrain':copy.deepcopy(self.terrain),'battles':[],'events':[]}
        if self.cfg.get('mode')=='realmap':out['map_info']=copy.deepcopy(self.map_info)
        out['economy']=economy.reports(self,nation)
        out['mode']=self.cfg.get('mode','duel')
        out['rule_version']=self.cfg['version']
        out['direct_garrison_delivery']=self.cfg.get('direct_garrison_delivery',False)
        out['limits']={k:self.cfg[k] for k in ('clan_party_cap','party_cap','field_ration','carry_days')}
        if self.cfg.get('siege_prepare_hours'):
            out['speeds']=copy.deepcopy(self.cfg['speeds'])
            out['relief_requests']=[dict(city=b['city'],battle=b['id'],x=b['x'],y=b['y'],start=b['start'],assault_at=b['start']+b['prepare_hours']+b.get('paused_hours',0),phase='relief_field' if b.get('relief_battle') else 'siege' if self.hour<b['start']+b['prepare_hours']+b.get('paused_hours',0) else 'combat',relief_battle=b.get('relief_battle')) for b in self.battles.values() if b['city'] and b['defender']==nation]
        if self.cfg.get('frontier_only',False):out['frontier_targets']=sorted(c['id'] for c in self.cities.values() if self.can_siege(nation,c['id']))
        for category,items in (('cities',self.cities),('villages',self.villages)):
            for obj in items.values():
                if obj['nation']==nation:
                    out[category].append(copy.deepcopy(obj))
                else:
                    known=copy.deepcopy(self.known[str(nation)].get(obj['id'],{}))
                    if known:
                        known['stale']=not self.visible(nation,obj)
                        out[category].append(known)
        for u in self.units.values():
            if u['nation']==nation:
                out['units'].append(copy.deepcopy(u))
            elif self.visible(nation,u):
                out['units'].append({k:u[k] for k in ('id','kind','nation','clan','x','y','healthy','wounded','battle','army')})
        for b in self.battles.values():
            if self.visible(nation,b):
                out['battles'].append({k:b[k] for k in ('id','x','y','start','days','city','kind','prepare_hours')})
                for k in ('paused_hours','relief_battle','relief_for'):
                    if k in b:out['battles'][-1][k]=b[k]
        return out

    def move_units(self):
        before = {i:(u['x'],u['y']) for i,u in self.units.items()}
        army_speeds={aid:military.speed(self.units[ids[0]],self.cfg['speeds'],[self.units[i] for i in ids]) for aid,ids in self.armies.items()} if military.enabled(self) else {}
        for uid in sorted(self.units):
            u=self.units[uid]
            if u['battle'] or u['kind'] in ('garrison','militia'):
                continue
            order=u['order'] or {}
            if order.get('type') in ('siege','raid'):
                targets=self.cities if order['type']=='siege' else self.villages
                target=targets.get(order.get('target'))
                if target and (target['nation']==u['nation'] or (order['type']=='siege' and not self.can_siege(u['nation'],target['id']))):
                    u.update(order=None,path=[])
                    continue
            if order.get('type')=='attack':
                target=self.units.get(order.get('target'))
                if u['kind']=='bandit' and target and not self.bandit_can_target(target):
                    u.update(order=None,path=[])
                    continue
                if not u['path'] and (not target or not (dist(u,target)<=6000 if u['kind']=='bandit' else self.visible(u['nation'],target))):
                    u['order']=None
                if target and (dist(u,target)<=6000 if u['kind']=='bandit' else self.visible(u['nation'],target)):
                    if (target['x'],target['y']) != (order.get('last_x'),order.get('last_y')):
                        order.update(last_x=target['x'],last_y=target['y'])
                        u['path']=self.route(u,target['x'],target['y']) or []
            if not u['path']:
                continue
            speed=(army_speeds[u['army']] if u['army'] else military.speed(u,self.cfg['speeds'])) if military.enabled(self) else self.cfg['speeds']['army' if u['army'] else u['kind']]
            if self.cfg.get('mode')!='realmap' and self.terrain[min(39,u['y']//2000)][min(59,u['x']//2000)]==1:
                speed=speed*3//4
            while u['path'] and speed>0:
                x,y=u['path'][0]
                dx,dy=x-u['x'],y-u['y']
                d=math.isqrt(dx*dx+dy*dy)
                if d<=speed:
                    u.update(x=x,y=y)
                    u['path'].pop(0)
                    speed-=d
                else:
                    u['x']+=int(dx*speed/d)
                    u['y']+=int(dy*speed/d)
                    speed=0
        return before

    @staticmethod
    def swept(a,b,old):
        ax,ay=old.get(a['id'],(a['x'],a['y']))
        bx,by=old.get(b['id'],(b['x'],b['y']))
        rx,ry=ax-bx,ay-by
        vx,vy=(a['x']-ax)-(b['x']-bx),(a['y']-ay)-(b['y']-by)
        den=vx*vx+vy*vy
        t=max(0,min(1,-(rx*vx+ry*vy)/den)) if den else 0
        return (rx+t*vx)**2+(ry+t*vy)**2<=1000**2

    def start_battle(self, a, b, city=None, relief_for=None):
        if military.enabled(self) and ((a['kind']=='bandit' and b.get('militia_convoy')) or (b['kind']=='bandit' and a.get('militia_convoy'))):return
        if self.cfg.get('mode')=='realmap':
            from .real_map import mesh
            if not mesh().clear_segment(a,b):return
        if city and not self.can_siege(a['nation'],city):return
        if a['kind']=='bandit' and b['kind']=='village_cart' and not self.bandit_can_target(b):return
        if b['kind']=='bandit' and a['kind']=='village_cart' and not self.bandit_can_target(a):return
        if a['nation']==b['nation']:
            return
        if self.cfg.get('external_relief') and not relief_for:
            for besieger,reliever in ((b,a),(a,b)):
                parent=self.battles.get(besieger['battle'])
                if parent and parent['city'] and besieger['nation']!=parent['defender'] and reliever['nation']==parent['defender'] and not reliever['battle'] and reliever['kind']=='party':
                    return self.start_relief_battle(reliever,parent)
        if self.cfg.get('external_relief') and city:
            parent=next((battle for battle in self.battles.values() if battle['city']==city),None)
            if parent:
                for u in (a,b):
                    if not u['battle']:self.join(parent,u)
                return parent['id']
        for existing in (a['battle'],b['battle']):
            if existing and existing in self.battles:
                battle=self.battles[existing]
                for u in (a,b):
                    if not u['battle'] and str(u['nation']) in battle['sides']:
                        self.join(battle,u)
                return
        if {a['kind'],b['kind']}=={'bandit','village_cart'}:
            economy.transport(self,'intercept',a if a['kind']=='village_cart' else b)
        bid=self.ident('b')
        battle=dict(id=bid,x=b['x'],y=b['y'],start=self.hour,days=1,city=city,
                    defender=b['nation'],award_clan=(a['order'] or {}).get('award_clan'),sides={str(a['nation']):[],str(b['nation']):[]},
                    power={},remainders={str(a['nation']):[0,1],str(b['nation']):[0,1]})
        if city and self.cfg.get('siege_prepare_hours'):
            battle.update(x=self.cities[city]['x'],y=self.cities[city]['y'])
        if relief_for:
            battle.update(relief_for=relief_for,x=a['x'],y=a['y'])
        if city and self.cfg.get('external_relief'):battle['paused_hours']=0
        self.battles[bid]=battle
        self.join(battle,a)
        self.join(battle,b)
        # All physically present troops of either side take part; no remote joining.
        for u in list(self.units.values()):
            if not u['battle'] and str(u['nation']) in battle['sides'] and dist(u,battle)<=1000 and self.size(u)>0:
                self.join(battle,u)
        s=sum(self.units[i]['healthy'] for ids in battle['sides'].values() for i in ids)
        battle['days']=min(self.cfg['battle_max_days'],max(1,math.ceil(s/self.cfg['battle_scale'])))
        ambush=not city and {a['kind'],b['kind']}=={'bandit','village_cart'}
        skirmish=not city and 'bandit' in {a['kind'],b['kind']} and not ambush
        battle['prepare_hours']=self.cfg['bandit_ambush_prepare'] if ambush else self.cfg['bandit_skirmish_prepare'] if skirmish else self.cfg['battle_prepare']
        if city:battle['prepare_hours']=self.cfg.get('siege_prepare_hours',self.cfg['battle_prepare'])
        battle['combat_hours']=self.cfg['bandit_ambush_hours'] if ambush else self.cfg['bandit_skirmish_hours'] if skirmish else 24*battle['days']
        battle['kind']='relief_field' if relief_for else 'ambush' if ambush else 'skirmish' if skirmish else 'siege' if city else 'field'
        if city and self.cfg.get('siege_prepare_hours'):
            self.emit('siege_alert',f"{self.cities[city]['name']}遭围城，{self.nation_name(b['nation'])}发出求援；72小时后开始攻城",city=city,nation=b['nation'],battle=bid,important=True)
        self.emit('battle','运输队遭劫匪袭击' if ambush else '发生攻城战' if city else '发生城外解围野战' if relief_for else '发生野战',battle=bid)
        return bid

    def start_relief_battle(self,reliever,parent):
        """Detach the besiegers into one external battle; the city fight is suspended."""
        existing=self.battles.get(parent.get('relief_battle'))
        if existing:
            if dist(reliever,existing)<=1000:self.join(existing,reliever)
            return existing['id']
        attack_nation=next(int(n) for n in parent['sides'] if int(n)!=parent['defender'])
        attackers=[self.units[i] for i in parent['sides'][str(attack_nation)] if i in self.units]
        leader=next((u for u in attackers if u['healthy']>0),None)
        if not leader:return
        parent['suspended_losses']={u['id']:u['war_losses'] for u in attackers}
        parent['sides'][str(attack_nation)]=[]
        for u in attackers:
            parent['power'].pop(u['id'],None)
            u['battle']=None
        child_id=self.start_battle(reliever,leader,relief_for=parent['id'])
        child=self.battles[child_id]
        for u in attackers:
            if not u['battle']:self.join(child,u)
        parent['relief_battle']=child_id
        self.emit('relief_field_started',f"{self.cities[parent['city']]['name']}城外发生解围野战，围城与攻城暂停",city=parent['city'],battle=child_id,important=True)
        return child_id

    def finish_relief_battle(self,field,winner):
        parent=self.battles.get(field['relief_for'])
        if not parent:return
        city=parent['city']
        attack_nation=next(int(n) for n in parent['sides'] if int(n)!=parent['defender'])
        survivors=[self.units[i] for i in field['sides'].get(str(attack_nation),[]) if i in self.units]
        parent.pop('relief_battle',None)
        if winner==attack_nation and any(u['healthy'] for u in survivors):
            losses=parent.pop('suspended_losses',{})
            for u in survivors:
                self.join(parent,u)
                u['war_losses']=losses.get(u['id'],0)
                u['order']={'type':'siege','unit':u['id'],'target':city}
            self.emit('siege_resumed',f"{self.cities[city]['name']}围城方击退援军，按原进度继续围城/攻城",city=city,important=True)
        else:
            for ids in parent['sides'].values():
                for uid in ids:
                    u=self.units.get(uid)
                    if u and u['battle']==parent['id']:u.update(battle=None,last_battle=self.hour,order=None,path=[])
            del self.battles[parent['id']]
            self.emit('siege_lifted',f"{self.cities[city]['name']}的围城部队失去战斗能力，围城解除",city=city,nation=parent['defender'],important=True)

    def join(self,b,u):
        if military.enabled(self) and u.get('militia_convoy') and '-1' in b['sides']:return
        if self.cfg.get('mode')=='realmap':
            from .real_map import mesh
            if not mesh().clear_segment(u,b):return
        n=str(u['nation'])
        if n not in b['sides'] or u['battle']:
            return
        if self.cfg.get('external_relief'):
            if b.get('relief_for') and u['kind'] in ('garrison','militia'):return
            if b['city'] and b.get('kind')=='siege' and u['nation']==b['defender'] and u['kind']=='party':return
            child=self.battles.get(b.get('relief_battle'))
            if child:
                if u['nation']!=b['defender'] and dist(u,child)<=1000:self.join(child,u)
                return
        if u['kind']=='militia' and b['city']!=u['home']:return
        if '-1' in b['sides'] and u['kind']=='village_cart' and not self.bandit_can_target(u):return
        if '-1' in b['sides'] and u['kind']=='village_cart':economy.transport(self,'intercept',u)
        if u['id'] not in b['sides'][n]:b['sides'][n].append(u['id'])
        coef=1 if u['kind'] in ('village_cart','militia') or (military.enabled(self) and u.get('militia_convoy')) else 2
        if '-1' in b['sides'] and u['kind']=='party':
            coef*=self.cfg.get('regular_vs_bandit',1)
        if b['city'] and u['nation']==b['defender']:
            coef*=2
        b['power'][u['id']]=u['healthy']*coef
        if b['city'] and u['kind']=='party' and (u['order'] or {}).get('campaign_phase')=='relief':
            self.emit('relief_arrived',f"{self.unit_name(u)}抵达{self.cities[b['city']]['name']}，加入守方",nation=u['nation'],city=b['city'],unit=u['id'],important=True)
        u.update(battle=b['id'],x=b['x'],y=b['y'],path=[],war_losses=0)
        # Raiding is interrupted by any actual battle.
        for v in self.villages.values():
            if v['raid'] and v['raid']['unit']==u['id']:
                v['raid']=None

    def contacts(self,old):
        for a in list(self.units.values()):
            if a['id'] not in self.units or a['battle'] or not a['healthy']:
                continue
            order=a['order'] or {}
            op=order.get('type')
            if op=='siege':
                c=self.cities.get(order.get('target'))
                if c and c['nation']!=a['nation'] and dist(a,c)<=1000:
                    self.start_battle(a,self.units[c['garrison']],c['id'])
            elif op=='attack':
                b=self.units.get(order.get('target'))
                if b and b['nation']!=a['nation'] and self.swept(a,b,old):
                    if a['kind']=='bandit' and not self.bandit_can_target(b):
                        a.update(order=None,path=[]);continue
                    c=self.city_at(b)
                    siege=c['id'] if c and b['kind'] in ('party','garrison','militia') else None
                    if siege and not self.can_siege(a['nation'],siege):
                        a.update(order=None,path=[]);continue
                    self.start_battle(a,b,siege)
        # Reinforcements of the same two participants join on contact.
        for b in list(self.battles.values()):
            for u in list(self.units.values()):
                if not u['battle'] and str(u['nation']) in b['sides'] and self.size(u)>0 and dist(u,b)<=1000:
                    self.join(b,u)

    def battle_tick(self):
        for bid,b in list(self.battles.items()):
            if bid not in self.battles:continue
            if b.get('relief_battle') in self.battles:
                b['paused_hours']=b.get('paused_hours',0)+1
                continue
            if self.hour-b['start']-b.get('paused_hours',0)<b['prepare_hours']:
                continue
            nations=list(b['sides'])
            plans=[]
            for n in nations:
                enemy=next(k for k in nations if k!=n)
                targets={i:self.units[i]['healthy'] for i in b['sides'][enemy] if i in self.units}
                power=sum(b['power'].get(i,0) for i in b['sides'][n] if i in self.units and self.units[i]['healthy']>0)
                acc=Fraction(*b['remainders'][n])+Fraction(power,2*b['combat_hours'])
                loss=min(sum(targets.values()),int(acc))
                acc-=int(acc)
                b['remainders'][n]=[acc.numerator,acc.denominator]
                plans.append(allocate(loss,targets))
            for plan in plans:
                for uid,loss in plan.items():
                    u=self.units[uid]
                    dead=(u['war_losses']+loss)//4-u['war_losses']//4
                    u['war_losses']+=loss
                    if military.enabled(self):military.casualties(u,loss,dead)
                    u['healthy']-=loss
                    u['wounded']+=loss-dead
                    self.stats['war_dead']+=dead
                    self.trim_food(u)
            alive={n:sum(self.units[i]['healthy'] for i in ids if i in self.units) for n,ids in b['sides'].items()}
            winners=[int(n) for n,h in alive.items() if h>0]
            if len(winners)==2:
                continue
            winner=winners[0] if winners else None
            winner_clans=[]
            for n,ids in b['sides'].items():
                for uid in list(ids):
                    if uid not in self.units:
                        continue
                    u=self.units[uid]
                    if int(n)!=winner:
                        self.remove(uid,'defeated')
                    else:
                        if u['kind']=='party':
                            winner_clans.append(u['clan'])
                        u.update(battle=None,last_battle=self.hour)
                        if u['kind'] in ('city_cart','village_cart'):
                            self.resume_cart(u)
                        else:
                            u.update(order=None,path=[])
            del self.battles[bid]
            text=(self.nation_name(winner)+'获胜') if winner is not None else '双方均失去战斗能力'
            self.emit('battle_end',f"{self.location_name(b)}战斗结束：{text}",battle=bid,winner=winner,nation=winner,important=('-1' not in b['sides']))
            if b.get('relief_for'):self.finish_relief_battle(b,winner)
            if b['city'] and winner is not None and winner!=b['defender']:
                self.capture(b['city'],winner,winner_clans,b.get('award_clan'))

    def capture(self,cid,nation,clans,award_clan=None):
        c=self.cities[cid]
        old=c['nation']
        candidates=set(clans) or ({int(k) for k,v in self.map_clans.items() if v['nation']==nation} if self.cfg.get('mode')=='realmap' else {nation*6})
        clan=award_clan if award_clan is not None and self.clan_nation(award_clan)==nation else min(candidates,key=lambda k:(sum(x['clan']==k for x in self.cities.values()),k))
        c.update(nation=nation,clan=clan,convoy=None)
        g=self.units[c['garrison']]
        g.update(nation=nation,clan=clan,healthy=0,wounded=0,battle=None)
        if military.enabled(self):g.update(cavalry=0,cavalry_wounded=0);c['training_hours']=0
        if c.get('militia'):
            m=self.units[c['militia']]
            m.update(nation=nation,clan=clan,healthy=0,wounded=0,battle=None,x=c['x'],y=c['y'],hungry=False,last_battle=self.hour)
            c['militia_reset_hour']=self.hour
        for v in self.villages.values():
            if v['city']==cid:
                v.update(nation=nation,raid=None)
                u=self.units.get(v['cart'])
                if u:
                    # Remove it from any old combat; ownership change is atomic.
                    if u['battle'] in self.battles:
                        b=self.battles[u['battle']]
                        for ids in b['sides'].values():
                            if u['id'] in ids:
                                ids.remove(u['id'])
                    u.update(nation=nation,clan=clan,battle=None)
                    self.resume_cart(u)
        for u in list(self.units.values()):
            if u['kind']=='city_cart' and (u['home']==cid or u.get('destination')==cid):
                if not u['battle']:
                    u['phase']='return'
                    self.resume_cart(u)
        self.history.append({'hour':self.hour,'city':cid,'from':old,'to':nation})
        self.emit('capture',f"{self.nation_name(nation)}攻占{c['name']}，归家族{clan%6+1}",city=cid,nation=nation,previous_nation=old,important=True)

    def resume_cart(self,u):
        if military.enabled(self) and u.get('militia_convoy'):return military.resume(self,u)
        if u['kind']=='village_cart':
            v=self.villages[u['home']]
            target=self.cities[v['city']] if u['phase']=='outbound' else v
        else:
            target=self.cities.get(u.get('destination') if u['phase']=='outbound' else u['home'])
            if not target or target['nation']!=u['nation']:
                options=[c for c in self.cities.values() if c['nation']==u['nation']]
                if not options:
                    u.update(path=[],order=None)
                    return
                target=min(options,key=lambda c:(dist(c,u),c['id']))
                u.update(home=target['id'],phase='orphan_return')
        self.go(u,target['x'],target['y'])

    def arrivals(self):
        if self.cfg.get('direct_garrison_delivery'):
            for c in self.cities.values():
                g=self.units[c['garrison']]
                if not g['battle']:g.update(x=c['x'],y=c['y'])
        for u in list(self.units.values()):
            if u['battle'] or u['path']:
                continue
            if u['kind']=='party':
                c=self.city_at(u)
                if c:self.service_party(u,c)
                order=u['order'] or {}
                if self.cfg.get('external_relief') and order.get('relief_action')=='wait' and not order.get('waiting_reported'):
                    order['waiting_reported']=True
                    self.emit('relief_waiting',f"{self.unit_name(u)}在城外会合点等待战机",nation=u['nation'],unit=u['id'],important=True)
            elif u['kind']=='village_cart':
                v=self.villages[u['home']]
                if u['phase']=='outbound':
                    c=self.cities[v['city']]
                    if dist(u,c)>500 or self.besieged(c['id']):
                        continue
                    put=min(u['cargo_food'],self.cfg['warehouse']-c['food'])
                    c['food']+=put
                    u['cargo_food']-=put
                    admitted=u['cargo_recruits']
                    if self.cfg.get('direct_garrison_delivery'):
                        g=self.units[c['garrison']]
                        admitted=min(admitted,max(0,self.cfg['garrison_cap']-self.size(g))) if not g['battle'] else 0
                        g['healthy']+=admitted
                    else:c['recruits']+=admitted
                    self.stats['delivered_food']+=put
                    self.stats['delivered_recruits']+=admitted
                    u['cargo_recruits']-=admitted
                    economy.transport(self,'delivered',u)
                    u['phase']='return'
                    self.resume_cart(u)
                    self.emit('delivery',f'{v["name"]}运输抵达',city=c['id'])
                elif u['phase']=='return' and dist(u,v)<=500:
                    v['food']+=u['cargo_food']
                    v['recruits']+=u['cargo_recruits']
                    economy.transport(self,'returned',u)
                    u.update(cargo_food=0,cargo_recruits=0,phase='idle',order=None)
            elif u['kind']=='city_cart':
                if military.enabled(self) and u.get('militia_convoy'):
                    military.arrival(self,u)
                    continue
                if u['phase']=='outbound':
                    c=self.cities[u['destination']]
                    if c['nation']!=u['nation']:
                        u['phase']='return'
                        self.resume_cart(u)
                    elif dist(u,c)<=500 and not self.besieged(c['id']):
                        put=min(u['cargo_food'],self.cfg['warehouse']-c['food'])
                        c['food']+=put
                        u['cargo_food']-=put
                        u['phase']='return'
                        self.resume_cart(u)
                else:
                    c=self.cities[u['home']]
                    if c['nation']!=u['nation']:
                        self.resume_cart(u)
                        continue
                    g=self.units[c['garrison']]
                    if dist(u,c)>500 or self.besieged(c['id']):
                        continue
                    put=min(u['food']+u['cargo_food'],self.cfg['warehouse']-c['food'])
                    c['food']+=put
                    take=min(put,u['cargo_food'])
                    u['cargo_food']-=take
                    u['food']-=put-take
                    room=self.cfg['garrison_cap']-self.size(g)
                    if room>=self.size(u) and u['food']+u['cargo_food']==0:
                        g['healthy']+=u['healthy']
                        g['wounded']+=u['wounded']
                        u.update(healthy=0,wounded=0)
                        self.remove(u['id'])

    def raids(self):
        for v in self.villages.values():
            if v['raid']:
                u=self.units.get(v['raid']['unit'])
                if not u or u['battle'] or not u['healthy'] or dist(u,v)>1000 or (u['order'] or {}).get('type')!='raid':
                    v['raid']=None
                elif self.hour-v['raid']['start']>=self.cfg['raid_hours']:
                    v['population']=v['population']*6//10
                    self.stats['food_lost']+=v['food']
                    self.stats['recruits_lost']+=v['recruits']
                    v.update(food=0,recruits=0,disabled_until=self.hour+self.cfg['raid_shutdown'],raid=None)
                    self.emit('raid',f"{self.nation_name(u['nation'])}劫掠{v['name']}，该村停产一周",village=v['id'],nation=u['nation'],important=True)
                    u.update(order=None,path=[])
            if not v['raid'] and self.hour>=v['disabled_until']:
                for u in self.units.values():
                    order=u['order'] or {}
                    if u['kind']=='party' and not u['battle'] and u['healthy'] and order.get('type')=='raid' and order.get('target')==v['id'] and u['nation']!=v['nation'] and dist(u,v)<=1000:
                        v['raid']={'unit':u['id'],'start':self.hour}
                        break

    def eat(self, members, rate, city=None):
        members=[u for u in members if self.size(u)>0]
        count=sum(self.size(u) for u in members)
        if not count:
            return
        needed=count*rate
        stores=[]
        if city:
            stores.append((city,'food'))
        for u in sorted(members,key=lambda u:u['id']):
            stores.append((u,'food'))
            if u['kind']=='city_cart':
                stores.append((u,'cargo_food'))
        available=sum(o[k] for o,k in stores)
        left=min(available,needed)
        for o,k in stores:
            take=min(left,o[k]);o[k]-=take;left-=take
        hungry=available<needed
        for u in members:
            u['hungry']=hungry
        if not hungry:
            return
        deaths=(count+9)//10
        shares=allocate(deaths,{u['id']:self.size(u) for u in members})
        for u in members:
            d=shares.get(u['id'],0)
            parts=allocate(d,{'healthy':u['healthy'],'wounded':u['wounded']})
            for k,v in parts.items():
                if military.enabled(self):military.take_cavalry(u,v,k)
                u[k]-=v
            self.stats['starved']+=d
            self.trim_food(u)
            if not self.size(u):
                self.remove(u['id'],'starved')
        self.emit('hunger','军队缺粮减员',deaths=deaths)

    def daily(self):
        for c in self.cities.values():
            if c.get('militia') and c['militia_reset_hour']!=self.hour:
                m=self.units[c['militia']]
                count=min(self.cfg['militia_growth'],max(0,self.cfg['militia_cap']-self.size(m)-(military.away_militia(self,c) if military.enabled(self) else 0)))
                m['healthy']+=count
                if m['battle'] in self.battles:
                    battle=self.battles[m['battle']]
                    battle['power'][m['id']]=battle['power'].get(m['id'],0)+count*2
        for v in self.villages.values():
            if self.hour<v['disabled_until']:
                continue
            v['population']+=self.cfg['growth']
            u=self.units.get(v['cart'])
            if not u and v['population']>=self.cfg['village_crew']:
                v['population']-=self.cfg['village_crew']
                c=self.cities[v['city']]
                u=self.new_unit('village_cart',v['nation'],c['clan'],self.cfg['village_crew'],v['x'],v['y'],home=v['id'])
                v['cart']=u['id']
            elif u and not u['battle'] and u['phase']=='idle' and dist(u,v)<=500:
                missing=self.cfg['village_crew']-self.size(u)
                if missing>0 and v['population']>=missing:
                    v['population']-=missing
                    u['healthy']+=missing
        used=set()
        for c in self.cities.values():
            members=[u for u in self.units.values() if u['nation']==c['nation'] and u['kind'] in ('party','garrison','militia') and dist(u,c)<=500 and not self.battles.get(u['battle'],{}).get('relief_for')]
            used.update(u['id'] for u in members)
            self.eat(members,self.cfg['city_ration'],c)
        groups={}
        for u in list(self.units.values()):
            if u['id'] not in used and u['kind'] in ('party','city_cart'):
                key=u['army'] or u['id']
                groups.setdefault(key,[]).append(u)
        for members in groups.values():
            self.eat(members,self.cfg['field_ration'])
        for u in self.units.values():
            if u['battle'] or self.hour-u['last_battle']<24 or u['hungry']:
                continue
            heal=min(u['wounded'],(u['wounded']+9)//10)
            if military.enabled(self):military.heal(u,heal)
            u['wounded']-=heal
            u['healthy']+=heal

    def weekly(self):
        for v in self.villages.values():
            if self.hour<v['disabled_until']:
                continue
            v['food']+=v['population']*1000
            v['recruits']+=v['population']//100
            u=self.units.get(v['cart'])
            if u and not u['battle'] and u['phase']=='idle' and u['healthy']==self.cfg['village_crew'] and not u['wounded']:
                u.update(cargo_food=v['food'],cargo_recruits=v['recruits'],phase='outbound')
                v.update(food=0,recruits=0)
                economy.transport(self,'depart',u)
                self.resume_cart(u)
    def spawn_bandits(self):
        """Independent daily-ish clocks, unrelated to weekly food departures."""
        for n in (0,1):
            if self.hour<self.next_bandits[str(n)]:continue
            # Exogenous schedule/candidate draws independent of policy RNG usage.
            rng=random.Random(self.seed*1000003+self.hour*37+n*911)
            self.next_bandits[str(n)]=self.hour+rng.randint(self.cfg['bandit_spawn_min'],self.cfg['bandit_spawn_max'])
            if sum(u['kind']=='bandit' for u in self.units.values())>=self.cfg['bandit_cap']:continue
            options=[v for v in self.villages.values() if (v.get('initial_nation')==n if self.cfg.get('mode')=='realmap' else v['id'].startswith(f'v{n}'))]
            rng.shuffle(options)
            spawned=False
            for v in options:
                for _ in range(12):
                    angle=rng.uniform(0,math.tau);radius=rng.randint(2500,6000)
                    p={'x':round(v['x']+math.cos(angle)*radius),'y':round(v['y']+math.sin(angle)*radius)}
                    if not self.position_passable(p['x'],p['y']):continue
                    if any(dist(p,c)<=10500 for c in self.cities.values()):continue
                    if any(dist(p,u)<(8000 if u['kind']=='party' else 3500 if u['kind']=='village_cart' else 1500) for u in self.units.values() if self.size(u)>0):continue
                    self.new_unit('bandit',-1,-1,self.cfg['bandit_size'],p['x'],p['y'])
                    self.stats['bandit_spawns']+=1
                    self.emit('bandit_spawn','乡野出现劫匪')
                    spawned=True;break
                if spawned:break

    def bandits(self):
        for u in list(self.units.values()):
            if u['kind']!='bandit' or u['battle']:continue
            if self.hour-u['born']>=self.cfg['bandit_lifetime']:
                self.remove(u['id']);continue
            threats=[p for p in self.units.values() if p['kind']=='party' and not p['battle'] and p['healthy']>0 and dist(p,u)<=6000 and (p['healthy']>=u['healthy'] or (p['order'] or {}).get('target')==u['id'])]
            if threats:
                # Choose a reachable escape direction. Only locally seen pursuers count.
                candidates=[]
                for dx,dy in ((4000,0),(-4000,0),(0,4000),(0,-4000),(2800,2800),(2800,-2800),(-2800,2800),(-2800,-2800)):
                    p={'x':u['x']+dx,'y':u['y']+dy}
                    if not self.position_passable(p['x'],p['y']):continue
                    if any(dist(p,c)<4000 for c in self.cities.values()):continue
                    if self.cfg.get('mode')=='realmap' and self.route(u,p['x'],p['y']) is None:continue
                    candidates.append((min(dist(p,t) for t in threats),p['x'],p['y']))
                if candidates:
                    _,x,y=max(candidates)
                    if (u['order'] or {}).get('type')!='flee':self.stats['bandit_flights']+=1
                    self.go(u,x,y,{'type':'flee'})
                continue
            # No information from other bandits or a hidden transport schedule.
            targets=[v for v in self.units.values() if self.bandit_can_target(v) and not v['battle'] and dist(v,u)<=6000]
            if targets:
                t=min(targets,key=lambda v:(dist(v,u),v['id']))
                if (u['order'] or {}).get('target')!=t['id']:
                    if self.route(u,t['x'],t['y']) is not None:self.go(u,t['x'],t['y'],{'type':'attack','target':t['id'],'last_x':t['x'],'last_y':t['y']})
            elif not u['path'] or (u['order'] or {}).get('type') in ('attack','flee'):
                x=max(1000,min(1009000 if self.cfg.get('mode')=='realmap' else 119000,u['origin_x']+self.rng.choice([-6000,-3000,0,3000,6000])))
                y=max(1000,min(939000 if self.cfg.get('mode')=='realmap' else 79000,u['origin_y']+self.rng.choice([-6000,-3000,0,3000,6000])))
                if self.position_passable(x,y) and self.route(u,x,y) is not None:self.go(u,x,y,{'type':'roam'})

    def rural_score(self):
        population = sum(v['population'] for v in self.villages.values()) + sum(
            self.size(u) for u in self.units.values() if u['kind'] == 'village_cart')
        initial = len(self.villages) * self.cfg['population']
        ceiling = initial + len(self.villages) * self.cfg['growth'] * (self.hour // 24)
        return dict(population=population, initial_population=initial,
                    population_gain=population-initial, no_loss_population=ceiling,
                    population_retention=population/ceiling if ceiling else 1,
                    population_growth=(population-initial)/initial if initial else 0,
                    bandit_cart_losses=self.stats['bandit_cart_losses'],
                    bandit_food_lost=self.stats['bandit_food_lost'])

    def finish(self):
        if self.cfg.get('mode') == 'rural':
            if self.hour >= self.cfg['days'] * 24:
                self.result = dict(winner=None, reason='rural_time_limit', hour=self.hour,
                                   mode='rural', score=self.rural_score())
                self.emit('end', f"十年护农挑战结束：农村人口 {self.result['score']['population']}",
                          result=self.result, important=True)
            return
        counts={n:sum(c['nation']==n for c in self.cities.values()) for n in (0,1)}
        unified=next((n for n,c in counts.items() if c==self.cfg.get('unification_city_count',12)),None)
        if unified is not None or self.hour>=self.cfg['days']*24:
            winner=unified if unified is not None else (None if counts[0]==counts[1] else max(counts,key=counts.get))
            self.result={'winner':winner,'reason':'unification' if unified is not None else 'time_limit','cities':counts,'hour':self.hour}
            self.emit('end',('对局结束：平局' if winner is None else f"对局结束：{self.nation_name(winner)}"+('统一大陆' if unified is not None else '领土领先获胜')),result=self.result,nation=winner,important=True)

    def step(self, count=1):
        for _ in range(count):
            if self.result:
                break
            self.hour+=1
            if military.enabled(self):military.train(self)
            self.spawn_bandits()
            self.bandits()
            before=self.move_units()
            self.contacts(before)
            self.arrivals()
            self.battle_tick()
            self.raids()
            if self.hour%24==0:
                self.daily()
                economy.sample(self)
            if self.hour%168==0:
                self.weekly()
            self.update_known()
            self.finish()

    def check(self):
        if military.enabled(self):military.check(self)
        for c in self.cities.values():
            assert 0<=c['food']<=self.cfg['warehouse'],c
            if c.get('militia'):assert self.size(self.units[c['militia']])<=self.cfg['militia_cap']
            assert c['recruits']>=0
            if self.cfg.get('direct_garrison_delivery'):assert c['recruits']==0, '新机制不得积累城市待招募兵源'
            assert self.size(self.units[c['garrison']])<=self.cfg['garrison_cap']
        for v in self.villages.values():
            assert v['population']>=0 and v['food']>=0 and v['recruits']>=0
            assert v['cart'] is None or v['cart'] in self.units
        for u in self.units.values():
            assert all(u[k]>=0 for k in ('healthy','wounded','food','cargo_food','cargo_recruits')),u
            if u['kind']=='party':
                assert self.size(u)<=self.cfg['party_cap']
            assert u['battle'] is None or u['battle'] in self.battles,u
            assert self.position_passable(u['x'],u['y']),u
        if self.cfg.get('external_relief'):
            membership={}
            for b in self.battles.values():
                for ids in b['sides'].values():
                    for uid in ids:
                        if uid in self.units:
                            assert uid not in membership,(uid,membership.get(uid),b['id'])
                            membership[uid]=b['id']
                if b.get('relief_battle'):
                    assert self.battles[b['relief_battle']]['relief_for']==b['id']
        for clan in (map(int,self.map_clans) if self.cfg.get('mode')=='realmap' else range(12)):
            assert sum(u['kind']=='party' and u['clan']==clan for u in self.units.values())<=self.cfg['clan_party_cap']

    def state(self):
        data={k:copy.deepcopy(v) for k,v in self.__dict__.items() if k!='rng'}
        data['rng_state']=self.rng.getstate()
        data['schema']=2
        return data

    def save(self,path):
        p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
        temp=p.with_suffix(p.suffix+'.tmp')
        temp.write_text(json.dumps(self.state(),ensure_ascii=False),encoding='utf-8')
        temp.replace(p)

    @classmethod
    def load(cls,path):
        data=json.loads(Path(path).read_text(encoding='utf-8'))
        if data.pop('schema')!=2 or data.get('cfg',{}).get('version') not in ('0.1.1','0.1.2','0.1.3','0.1.4','0.1.5','0.1.6'):
            raise ValueError('此存档属于旧版规则/地图，请用对应旧版本读取；新版请开新局')
        rng_state=data.pop('rng_state')
        w=cls.__new__(cls)
        w.__dict__.update(data)
        if 'event_seq' not in data:
            for i,e in enumerate(w.events,1):e['id']=i
            w.event_seq=len(w.events)
        def tuples(v):
            return tuple(tuples(x) for x in v) if isinstance(v,list) else v
        w.rng=random.Random()
        w.rng.setstate(tuples(rng_state))
        if w.cfg.get('mode')=='realmap':
            from .real_map import mesh, MAP_ID, map_hashes
            if w.cfg.get('map_id')!=MAP_ID or w.cfg.get('map_sha256')!=mesh().sha:raise ValueError('真实地图版本不匹配')
            if w.cfg.get('map_data_hashes') is not None and w.cfg['map_data_hashes']!=map_hashes():raise ValueError('真实地图数据版本不匹配')
        return w

    def digest(self):
        return hashlib.sha256(json.dumps(self.state(),sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

    def physics_digest(self):
        """Rule-state checksum; observer text/sequence changes cannot change a match."""
        state=self.state()
        state.pop('events',None);state.pop('event_seq',None)
        state.pop('economy',None)  # Observational telemetry is not physical rule state.
        return hashlib.sha256(json.dumps(state,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
