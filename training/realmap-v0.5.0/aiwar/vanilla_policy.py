"""Vanilla-flavour v1: independent, observation-only baseline for realmap.

Inspired by Bannerlord's readiness / utility / muster cycle, not copied game AI.
No policy RNG or private World state. Intent is serialized in ordinary orders.
"""
import math
from .navigation import find_route, relief_terrain

STYLE = 'vanilla_v1'
PARAMETERS = dict(ready_ratio=.60, join_food_days=15, army_fraction=.70,
                  attack_margin=1.20, muster_hours=72, muster_timeout=240,
                  campaign_hours=336, max_armies=2, refit_target=110)


def distance(a,b):return math.hypot(a['x']-b['x'],a['y']-b['y'])
def size(u):return u['healthy']+u['wounded']


class Planner:
    def __init__(self,obs):
        self.o=obs;self.n=obs['nation'];self.hour=obs['hour'];self.cmd=[];self.done=set();self.routes={}
        self.units={u['id']:u for u in obs['units']}
        self.parties=sorted((u for u in obs['units'] if u['nation']==self.n and u['kind']=='party'),key=lambda u:u['id'])
        self.cities=sorted((c for c in obs['cities'] if c['nation']==self.n and 'food' in c),key=lambda c:c['id'])
        self.bycity={c['id']:c for c in self.cities}
        self.targets={c['id']:c for c in obs['cities'] if c['nation']!=self.n and c['id'] in obs.get('frontier_targets',[])}
        self.sieged={b['city'] for b in obs['battles'] if b.get('city')}
        self.safe=[c for c in self.cities if c['id'] not in self.sieged]
        self.hostiles=[u for u in obs['units'] if u['nation']>=0 and u['nation']!=self.n and u['kind']=='party']
        self.armies={}
        for u in self.parties:
            if u['army']:self.armies.setdefault(u['army'],[]).append(u)
        self.stock={c['id']:c['food'] for c in self.cities}
        self.garrison={c['id']:self.units[c['garrison']]['healthy'] for c in self.cities}

    def days(self,u):return u['food']/max(1,size(u)*self.o['limits']['field_ration'])

    def length(self,a,b):
        key=(a['x'],a['y'],b['x'],b['y'])
        if key not in self.routes:
            path=find_route(self.o['terrain'],a,b['x'],b['y']);at=(a['x'],a['y']);length=0
            for p in path or []:length+=math.dist(at,p);at=p
            self.routes[key]=length if path is not None else math.inf
        return self.routes[key]

    def eta(self,u,c,army=False):
        speed=self.o['speeds']['army'] if army else u.get('movement_speed',self.o['speeds']['party'])
        return self.length(u,c)/max(1,speed)

    def move(self,u,c,**meta):
        command=dict(type='move',unit=u['id'],x=c['x'],y=c['y'],**meta)
        order=u.get('order') or {}
        if any(order.get(k)!=v for k,v in command.items()):self.cmd.append(command)

    def strength(self,u):
        target=max(PARAMETERS['refit_target'],u.get('reserve_refill_target',0))
        if u.get('refill_target',150)!=target:self.cmd.append(dict(type='set_strength',unit=u['id'],target=target))

    def base(self,u):
        order=u.get('order') or {}
        if order.get('vanilla_task')=='refit' and u.get('path'):
            previous=next((c for c in self.safe if (c['x'],c['y'])==(order.get('x'),order.get('y'))),None)
            if previous and self.stock[previous['id']]>10000:return previous
        options=sorted(self.safe,key=lambda c:(distance(u,c),c['id']))[:5]
        scored=[]
        for c in options:
            hours=self.eta(u,c)
            if not math.isfinite(hours):continue
            need=max(0,PARAMETERS['refit_target']-u['healthy'])
            stock=self.stock[c['id']];g=self.garrison[c['id']]
            # Prefer useful, reachable refit bases; own fiefs are a preference, not a restriction.
            benefit=1+min(stock/150000,3)+min(g/max(1,need),2)+(c['clan']==u['clan'])*.3
            scored.append((benefit/(1+hours/24),c['id'],c))
        return max(scored,key=lambda x:(x[0],x[1]))[2] if scored else None

    def refit(self,u):
        self.done.add(u['id']);self.strength(u)
        c=self.base(u)
        if c:self.move(u,c,vanilla_task='refit')

    def release(self,members):
        if members[0]['army']:self.cmd.append(dict(type='disband',unit=members[0]['id']))
        for u in members:self.refit(u)

    def defence(self,c):
        # Units are infantry-equivalent: defending garrison x2, militia x1.
        g=c.get('healthy',50);m=c.get('militia_healthy',100)
        if c.get('stale'):g=max(g,50);m=max(m,100)
        field=sum(u['healthy'] for u in self.hostiles if distance(u,c)<8000)
        return max(40,2*g+m+field)

    def required(self,c):return max(180,math.ceil(PARAMETERS['attack_margin']*self.defence(c)))

    def ready(self,u):
        return (not u['battle'] and not u['army'] and u['id'] not in self.done
                and u['healthy']>self.o['limits']['party_cap']*PARAMETERS['ready_ratio']
                and u['wounded']<=size(u)*.2 and self.days(u)>PARAMETERS['join_food_days'])

    def refill_and_raise(self):
        cap=self.o['limits']['clan_party_cap']
        clans=sorted({int(k) for k,v in self.o.get('map_info',{}).get('clans',{}).items() if v['nation']==self.n})
        for clan in clans:
            if sum(u['clan']==clan for u in self.parties)>=cap:continue
            options=[c for c in self.safe if self.garrison[c['id']]>=60 and self.garrison[c['id']]-self.units[c['garrison']].get('cavalry',0)>=30 and self.stock[c['id']]>=240000]
            if options:
                c=min(options,key=lambda c:(c['clan']!=clan,-self.garrison[c['id']],c['id']))
                self.cmd.append(dict(type='create',city=c['id'],clan=clan,count=30,source='garrison',troop_type='infantry'))
                # Only infantry may be raised here; a cavalry-only garrison is not an eligible donor.
                self.garrison[c['id']]-=30;self.stock[c['id']]-=90000
        for u in self.parties:
            if u['battle']:continue
            self.strength(u)
            if not u['army'] and u.get('cavalry_target')!=self.o['limits']['party_cap']:
                c=next((c for c in self.safe if distance(u,c)<=500 and self.units[c['garrison']].get('cavalry',0)),None)
                if c:self.cmd.append(dict(type='set_composition',unit=u['id'],cavalry_target=self.o['limits']['party_cap']))

    def logistics(self):
        limits=self.o['logistics_limits'];reserve=limits['city_reserve'];incoming={c['id']:0 for c in self.cities}
        for u in self.units.values():
            if u['nation']!=self.n or not u.get('militia_convoy'):continue
            dest=u.get('destination') if u['phase']=='outbound' and u['mission']=='deliver' else u['home'] if u['phase']!='outbound' else None
            if dest in incoming:incoming[dest]+=u['cargo_food']
        floors={};needs={}
        for c in self.cities:
            residents=sum(size(u) for u in self.units.values() if u['nation']==self.n and u['kind'] in ('party','garrison','militia') and distance(u,c)<=500)
            daily=residents*50
            rallies=sum(size(u) for u in self.parties if (u.get('order') or {}).get('vanilla_base')==c['id'])
            forward=any(i in self.targets for i in c['neighbors'])
            floors[c['id']]=max(300000,daily*14)
            needs[c['id']]=min(1800000,max(300000,daily*21+rallies*1500+(250000 if forward else 0)))
        for c in self.safe:
            cid=c['id'];m=self.units[c['militia']]
            if c['convoy'] or m['battle'] or m['healthy']<50 or self.stock[cid]<reserve:continue
            peers=[self.bycity[k] for k in c['supply_neighbors'] if k in self.bycity and k not in self.sieged]
            needy=[d for d in peers if needs[d['id']]-self.stock[d['id']]-incoming[d['id']]>=100000]
            surplus=self.stock[cid]-floors[cid]-reserve
            if needy and surplus>=100000:
                d=max(needy,key=lambda d:((needs[d['id']]-self.stock[d['id']]-incoming[d['id']])/(1+self.length(c,d)/10000),d['id']))
                amount=int(min(surplus,needs[d['id']]-self.stock[d['id']]-incoming[d['id']],limits['city_cargo']-reserve))
                self.cmd.append(dict(type='dispatch',city=cid,destination=d['id'],food=amount,mission='deliver'))
                self.stock[cid]-=amount+reserve;incoming[d['id']]+=amount
            elif self.stock[cid]+incoming[cid]<needs[cid]:
                donors=[d for d in peers if self.stock[d['id']]-floors[d['id']]>=200000]
                if donors:
                    d=max(donors,key=lambda d:((self.stock[d['id']]-floors[d['id']])/(1+self.length(c,d)/10000),d['id']))
                    amount=int(min(self.stock[d['id']]-floors[d['id']],needs[cid]-self.stock[cid]-incoming[cid],limits['city_cargo']-reserve))
                    if amount>=100000:
                        self.cmd.append(dict(type='dispatch',city=cid,destination=d['id'],food=amount,mission='fetch'))
                        self.stock[cid]-=reserve;self.stock[d['id']]-=amount;incoming[cid]+=amount

    def relief(self):
        groups=list(self.armies.values())+[[u] for u in self.parties if not u['army']]
        for alert in sorted(self.o.get('relief_requests',[]),key=lambda a:(a['assault_at'],a['city'])):
            enemy=[u for u in self.hostiles if u['battle'] in (alert['battle'],alert.get('relief_battle')) and u['battle']]
            if not enemy:continue
            anchors=sorted(self.safe,key=lambda c:(distance(c,alert),c['id']))
            stage=None
            for c in anchors[:3]:
                path=find_route(self.o['terrain'],c,alert['x'],alert['y'])
                for x,y in reversed(path or []):
                    p=dict(x=x,y=y)
                    if distance(p,alert)>3500 and find_route(relief_terrain(self.o['terrain'],alert,c),c,x,y) is not None:stage=p;break
                if stage:break
            if stage is None:continue
            choices=[]
            for g in groups:
                if any(u['battle'] or u['id'] in self.done for u in g):continue
                eta=self.eta(g[0],stage)
                if eta<=120 and min(self.days(u) for u in g)>eta/24+4:choices.append((eta,g[0]['id'],g))
            chosen=[];total=0;need=math.ceil(sum(u['healthy'] for u in enemy)*1.15)
            for _,_,g in sorted(choices):
                chosen.append(g);total+=sum(u['healthy'] for u in g)
                if total>=need:break
            if total<need:continue
            for g in chosen:
                self.done.update(u['id'] for u in g)
                if distance(g[0],stage)>100:self.move(g[0],stage,vanilla_task='relief',relief_action='wait',relief_city=alert['city'])
            arrived=[g for g in chosen if all(distance(u,stage)<=100 for u in g)]
            if sum(u['healthy'] for g in arrived for u in g)<need:continue
            members=[u for g in arrived for u in g];leader=members[0]
            if len(arrived)>1:
                for g in arrived:
                    if g[0]['army']:self.cmd.append(dict(type='disband',unit=g[0]['id']))
                self.cmd.append(dict(type='assemble',unit=leader['id'],units=[u['id'] for u in members[1:]]))
            target=min(enemy,key=lambda e:(distance(leader,e),e['id']))
            if len(arrived)>1 or (leader.get('order') or {}).get('target')!=target['id']:
                self.cmd.append(dict(type='attack',unit=leader['id'],target=target['id'],vanilla_task='relief'))

    def campaigns(self):
        for members in self.armies.values():
            if any(u['id'] in self.done for u in members):continue
            self.done.update(u['id'] for u in members)
            if any(u['battle'] for u in members):continue
            leader=members[0];target=self.targets.get(leader.get('army_target'))
            if not target or len(members)<2 or self.hour-leader.get('army_formed',self.hour)>PARAMETERS['campaign_hours']:
                self.release(members);continue
            travel=self.eta(leader,target)
            if min(self.days(u) for u in members)<max(6,travel/24+6) or sum(u['healthy'] for u in members)<self.required(target):
                self.release(members);continue
            order=leader.get('order') or {}
            if target.get('stale'):
                self.move(leader,target,vanilla_task='approach')
            elif order.get('type')!='siege' or order.get('target')!=target['id']:
                self.cmd.append(dict(type='siege',unit=leader['id'],target=target['id'],vanilla_task='siege'))

    def musters(self):
        plans={}
        for u in self.parties:
            order=u.get('order') or {}
            if not u['army'] and order.get('vanilla_task')=='muster':plans.setdefault((order['vanilla_target'],order['vanilla_started']),[]).append(u)
        for (tid,start),members in sorted(plans.items()):
            usable=[u for u in members if u['id'] not in self.done and not u['battle']]
            if not usable:continue
            self.done.update(u['id'] for u in usable)
            plan=usable[0]['order'];base=self.bycity.get(plan['vanilla_base']);target=self.targets.get(tid)
            if not base or base['id'] in self.sieged or not target or self.hour-start>PARAMETERS['muster_timeout']:
                for u in usable:self.refit(u)
                continue
            arrived=[u for u in usable if distance(u,base)<=100 and self.days(u)>12]
            wait=plan.get('vanilla_wait_since',-1)
            if arrived and wait<0:wait=self.hour
            elapsed=max(0,self.hour-wait) if wait>=0 else 0
            fraction=.9 if elapsed<72 else max(.5,.75-(elapsed-72)*.01)
            actual=sum(u['healthy'] for u in arrived)
            if len(arrived)>=2 and actual>=self.required(target) and actual>plan['vanilla_expected']*fraction:
                self.cmd.append(dict(type='assemble',unit=arrived[0]['id'],units=[u['id'] for u in arrived[1:]],campaign_target=tid))
                for u in usable:
                    if u not in arrived:self.refit(u)
            else:
                for u in usable:
                    if self.days(u)<self.eta(u,base)/24+3:self.refit(u);continue
                    self.move(u,base,vanilla_task='muster',vanilla_target=tid,vanilla_started=start,vanilla_base=base['id'],vanilla_expected=plan['vanilla_expected'],vanilla_wait_since=wait)

    def launch(self):
        committed=sum(bool(u['army']) or (u.get('order') or {}).get('vanilla_task')=='muster' for u in self.parties)
        slots=max(0,math.floor(len(self.parties)*PARAMETERS['army_fraction'])-committed)
        pending={(u.get('order') or {}).get('vanilla_target') for u in self.parties if (u.get('order') or {}).get('vanilla_task')=='muster'}
        if len(self.armies)+len(pending)>=PARAMETERS['max_armies'] or slots<2:return
        ready=[u for u in self.parties if self.ready(u)]
        if len(ready)<2:return
        active={u.get('army_target') for u in self.parties if u['army']}|pending
        options=[]
        for target in self.targets.values():
            if target['id'] in active:continue
            bases=[c for c in self.safe if target['id'] in c['neighbors']]
            for base in bases:
                journey=self.length(base,target)/self.o['speeds']['army']/24
                if journey+6>=24:continue
                candidates=sorted((u for u in ready if self.days(u)>self.eta(u,base)/24+15 and self.eta(u,base)<=168),key=lambda u:(self.eta(u,base),u['id']))[:slots]
                roster=[];strength=0
                for u in candidates:
                    roster.append(u);strength+=u['healthy']
                    if len(roster)>=2 and strength>=self.required(target):break
                if len(roster)<2 or strength<self.required(target):continue
                villages=sum(v.get('city')==target['id'] for v in self.o['villages'])
                value=1+villages*.15+(target.get('settlement_type')=='town')*.3
                score=value/(1+journey+sum(self.eta(u,base) for u in roster)/len(roster)/24)*min(2,strength/self.required(target))
                options.append((score,target['id'],base['id'],base,target,roster,strength))
        if options:
            _,_,_,base,target,roster,total=max(options,key=lambda x:x[:3])
            for u in roster:
                self.done.add(u['id'])
                self.move(u,base,vanilla_task='muster',vanilla_target=target['id'],vanilla_started=self.hour,vanilla_base=base['id'],vanilla_expected=total,vanilla_wait_since=-1)

    def independent(self):
        assigned=set()
        for u in self.parties:
            if u['id'] in self.done or u['battle'] or u['army']:continue
            order=u.get('order') or {};base=self.base(u)
            if not base:continue
            returning=order.get('vanilla_task')=='refit'
            needy=self.days(u)<self.eta(u,base)/24+5 or u['healthy']<35 or u['wounded']>size(u)*.25
            if needy or (returning and distance(u,base)>500):self.refit(u);continue
            threats=[e for e in self.o['units'] if e['nation']!=self.n and e['kind'] in ('bandit','party','city_cart') and e['id'] not in assigned and distance(u,e)<8000 and not e['battle']]
            threats=[e for e in threats if u['healthy']>e['healthy']*(.7 if e['kind']=='bandit' else 1.3) and not any(c['nation']!=self.n and distance(e,c)<=500 for c in self.o['cities']) and math.isfinite(self.eta(u,e)) and self.eta(u,e)<16]
            if threats:
                e=min(threats,key=lambda e:(self.eta(u,e),e['id']));assigned.add(e['id'])
                if order.get('type')!='attack' or order.get('target')!=e['id']:self.cmd.append(dict(type='attack',unit=u['id'],target=e['id'],vanilla_task='patrol'))
                continue
            if u['healthy']<=self.o['limits']['party_cap']*.6 and self.garrison[base['id']]>20:
                self.refit(u);continue
            # Keep a sensible current patrol; replace vanished-target attacks instead of stalling.
            if u.get('path') and order.get('vanilla_task')=='patrol' and order.get('type')=='move':continue
            homes=[c for c in self.safe if c['clan']==u['clan']] or [base]
            home=min(homes,key=lambda c:(self.eta(u,c),c['id']))
            villages=sorted((v for v in self.o['villages'] if v['nation']==self.n and v.get('city')==home['id'] and self.hour>=v.get('disabled_until',0)),key=lambda v:v['id'])
            points=[home]+villages
            index=(order.get('vanilla_patrol_index',-1)+1)%len(points);dest=points[index]
            if self.days(u)<self.eta(u,dest)/24+self.length(dest,home)/max(1,u.get('movement_speed',1000))/24+5:self.refit(u)
            elif math.isfinite(self.length(u,dest)):self.move(u,dest,vanilla_task='patrol',vanilla_patrol_index=index)

    def run(self):
        if not self.cities:return []
        self.refill_and_raise();self.logistics();self.relief();self.campaigns();self.musters();self.launch();self.independent()
        return self.cmd[:100]


def decide(obs):
    if obs.get('mode')!='realmap' or not obs.get('castle_logistics'):return []
    return Planner(obs).run()
