"""Observation-only v0.6 logistics adapter; old configurations keep vanilla v1."""
import math
from .vanilla_policy import Planner, PARAMETERS, distance, size


class LogisticsPlanner(Planner):
    def __init__(self,obs):
        super().__init__(obs)
        self.convoys=[u for u in self.units.values() if u['nation']==self.n and u.get('militia_convoy')]
        self.dispatched=set()
        self.support={}
        self.raid_assignments={(u.get('order') or {}).get('target'):u['army'] or u['id'] for u in self.parties if (u.get('order') or {}).get('type')=='raid'}
        self.incoming_troops={c['id']:0 for c in self.cities}
        for u in self.convoys:
            if u['phase'] in ('outbound','waiting_supply') and u.get('mission')=='deliver' and u.get('destination') in self.incoming_troops:
                self.incoming_troops[u['destination']]+=u.get('regular_healthy',0)+u.get('regular_wounded',0)
        self.depth={c['id']:0 for c in self.cities if any(i in self.targets for i in c['neighbors'])}
        for level in range(len(self.cities)):
            for c in self.cities:
                if c['id'] not in self.depth and any(self.depth.get(i)==level for i in c['supply_neighbors']):self.depth[c['id']]=level+1

    def group_days(self,members):
        return sum(u['food'] for u in members)/max(1,sum(size(u) for u in members)*self.o['limits']['field_ration'])

    def convoy_eta(self,c,target):return self.length(c,target)/max(1,self.o['speeds']['city_cart'])

    def safe_route(self,a,b):
        # Only current visible hostiles are available; never consult World.
        from .navigation import find_route
        route=find_route(self.o['terrain'],a,b['x'],b['y'])
        if route is None:return False
        points=[(a['x'],a['y'])]+route
        for enemy in self.hostiles:
            if enemy['healthy']<30:continue
            for start,end in zip(points,points[1:]):
                dx=end[0]-start[0];dy=end[1]-start[1];den=dx*dx+dy*dy
                t=max(0,min(1,((enemy['x']-start[0])*dx+(enemy['y']-start[1])*dy)/den)) if den else 0
                if math.hypot(enemy['x']-start[0]-t*dx,enemy['y']-start[1]-t*dy)<2500:return False
        return True

    def supply_groups(self):
        groups=list(self.armies.values())
        for members in groups:
            leader=members[0];ids={u['id'] for u in members};aid=leader['army']
            rate=sum(size(u) for u in members)*self.o['limits']['field_ration']
            food=sum(u['food'] for u in members)
            cap=sum(u.get('food_capacity',size(u)*self.o['limits']['field_ration']*60) for u in members)
            # A friendly city can fill the army directly; do not create a convoy for a local hand-off.
            local=next((c for c in self.safe if distance(c,leader)<=500 and not any(u['battle'] for u in members) and self.stock[c['id']]>=cap-food),None)
            if local and food<min(cap,rate*24):
                self.move(leader,leader,vanilla_task='refill_army')
                self.stock[local['id']]-=max(0,cap-food)
                self.done.update(u['id'] for u in members)
                continue
            incoming=0;etas=[]
            for cart in self.convoys:
                if cart['mission']!='supply' or cart['phase'] not in ('outbound','waiting_supply') or cart['battle']:continue
                if cart.get('supply_target') not in ids and cart.get('supply_army')!=aid:continue
                eta=self.convoy_eta(cart,leader)
                if math.isfinite(eta) and eta/24+2<food/max(1,rate):
                    incoming+=cart['cargo_food'];etas.append(eta)
            if incoming:self.support[aid]=dict(food=incoming,eta=min(etas))
            if food+incoming>=min(cap,rate*24):continue
            candidates=[]
            for c in self.safe:
                m=self.units[c['militia']]
                if c['convoy'] or c['id'] in self.dispatched or m['battle'] or m['healthy']<50:continue
                eta=self.convoy_eta(c,leader)
                if not math.isfinite(eta) or eta>168 or eta/24+2>=food/max(1,rate):continue
                # A convoy cannot reliably catch an army marching away at the same speed.
                order=leader.get('order') or {}
                if leader.get('path'):
                    end={'x':leader['path'][-1][0],'y':leader['path'][-1][1]}
                    if self.length(c,end)>self.length(c,leader)+1000:continue
                if not self.safe_route(c,leader):continue
                reserve=50*self.o['limits']['field_ration']*self.o['limits']['carry_days']
                surplus=self.stock[c['id']]-self.floors[c['id']]-reserve
                amount=int(min(surplus,self.o['logistics_limits']['city_cargo'],cap-food-incoming))
                if amount>=rate*3:candidates.append((eta,c['id'],c,amount,reserve))
            if not candidates:continue
            eta,cid,c,amount,reserve=min(candidates,key=lambda x:x[:2])
            self.cmd.append(dict(type='dispatch',city=cid,destination=leader['id'],mission='supply',food=amount))
            self.dispatched.add(cid);self.stock[cid]-=amount+reserve
            self.support[aid]=dict(food=incoming+amount,eta=min(etas+[eta]))

    def logistics(self):
        limits=self.o['logistics_limits'];ration=self.o['limits']['field_ration'];crew=limits['city_crew']
        incoming={c['id']:0 for c in self.cities};needs={};self.floors={}
        for u in self.convoys:
            if u['phase']=='outbound' and u['mission']=='deliver':dest=u['destination']
            elif u['phase'] not in ('outbound','waiting_supply'):dest=u['home']
            elif u['mission']=='fetch':dest=u['home']
            else:continue
            if dest in incoming:incoming[dest]+=u['cargo_food'] if u['mission']!='fetch' or u['phase']!='outbound' else u.get('requested_food',0)
        for c in self.cities:
            residents=sum(size(u) for u in self.units.values() if u['nation']==self.n and u['kind'] in ('party','garrison','militia','patrol') and distance(u,c)<=500)
            self.floors[c['id']]=max(300000,residents*50*14)
            rallies=sum(size(u) for u in self.parties if (u.get('order') or {}).get('vanilla_base')==c['id'])
            needs[c['id']]=min(1800000,max(300000,residents*50*21+rallies*1500+(250000 if self.depth.get(c['id'])==0 else 0)))
        self.supply_groups()
        for c in sorted(self.safe,key=lambda c:c['id']):
            cid=c['id'];m=self.units[c['militia']]
            if cid in self.dispatched or c['convoy'] or m['battle'] or m['healthy']<crew:continue
            peers=[self.bycity[i] for i in c['supply_neighbors'] if i in self.bycity and i not in self.sieged and self.safe_route(c,self.bycity[i])]
            donors=max(0,self.garrison[cid]-75)  # Strategy preference, not an engine floor.
            troop_targets=[d for d in peers if self.depth.get(d['id'],999)<self.depth.get(cid,999) and self.garrison[d['id']]+self.incoming_troops[d['id']]<(200 if self.depth.get(d['id'],999)<=1 else 100)]
            needy=[d for d in peers if needs[d['id']]-self.stock[d['id']]-incoming[d['id']]>=100000]
            targets=troop_targets if donors>=10 and troop_targets else needy
            if targets:
                d=max(targets,key=lambda d:((d in troop_targets),needs[d['id']]-self.stock[d['id']]-incoming[d['id']],d['id']))
                troops=min(limits['transport_troops'],donors,max(0,200-self.garrison[d['id']]-self.incoming_troops[d['id']])) if d in troop_targets else 0
                reserve=(crew+troops)*ration*self.o['limits']['carry_days']
                surplus=self.stock[cid]-self.floors[cid]-reserve
                amount=int(max(0,min(surplus,needs[d['id']]-self.stock[d['id']]-incoming[d['id']],limits['city_cargo'])))
                if surplus>=0 and (troops or amount>=100000):
                    self.cmd.append(dict(type='dispatch',city=cid,destination=d['id'],mission='deliver',food=amount,troops=troops))
                    self.dispatched.add(cid);self.stock[cid]-=amount+reserve;self.garrison[cid]-=troops
                    incoming[d['id']]+=amount;self.incoming_troops[d['id']]+=troops
                    continue
            reserve=crew*ration*self.o['limits']['carry_days']
            if self.stock[cid]<reserve or self.stock[cid]+incoming[cid]>=needs[cid]:continue
            sources=[d for d in peers if self.stock[d['id']]-self.floors[d['id']]>=200000]
            if sources:
                d=max(sources,key=lambda d:(self.stock[d['id']]-self.floors[d['id']],d['id']))
                amount=int(min(self.stock[d['id']]-self.floors[d['id']],needs[cid]-self.stock[cid]-incoming[cid],limits['city_cargo']))
                if amount>=100000:
                    self.cmd.append(dict(type='dispatch',city=cid,destination=d['id'],mission='fetch',food=amount))
                    self.dispatched.add(cid);self.stock[cid]-=reserve;self.stock[d['id']]-=amount;incoming[cid]+=amount

    def raid_for_food(self,members):
        leader=members[0];days=self.group_days(members);base=self.base(leader)
        if not base or days>=18 or any(u['battle'] for u in members):return False
        order=leader.get('order') or {}
        candidates=[]
        for v in self.o['villages']:
            if self.raid_assignments.get(v['id'],leader['army'] or leader['id'])!=(leader['army'] or leader['id']):continue
            if v['nation']==self.n or v.get('stale') or v.get('disabled_until',0)>self.hour:continue
            eta=self.eta(leader,v)
            if not math.isfinite(eta) or eta>72 or days<=eta/24+2:continue
            if any(distance(e,v)<8000 and e['healthy']*1.5>=sum(u['healthy'] for u in members) for e in self.hostiles):continue
            gain=(v.get('population',0)-(v.get('population',0)*6//10))*self.o['logistics_limits']['raid_household_food']
            rate=sum(size(u) for u in members)*self.o['limits']['field_ration']
            net=gain-rate*(eta/24+1)
            if net<=0:continue
            after=min(self.o['logistics_limits']['army_carry_days'] if leader['army'] else self.o['limits']['carry_days'],days+net/max(1,rate))
            return_days=self.length(v,base)/max(1,leader.get('movement_speed',self.o['speeds']['party']))/24
            if after<=return_days+2:continue
            candidates.append((order.get('type')=='raid' and order.get('target')==v['id'],net/(1+eta),v['id'],v))
        if not candidates:return False
        v=max(candidates,key=lambda x:x[:3])[3]
        self.raid_assignments[v['id']]=leader['army'] or leader['id']
        self.done.update(u['id'] for u in members)
        if order.get('type')!='raid' or order.get('target')!=v['id']:self.cmd.append(dict(type='raid',unit=leader['id'],target=v['id'],vanilla_task='raid_supply'))
        return True

    def campaigns(self):
        for members in self.armies.values():
            if any(u['id'] in self.done for u in members):continue
            self.done.update(u['id'] for u in members)
            if any(u['battle'] for u in members):continue
            leader=members[0];target=self.targets.get(leader.get('army_target'))
            if not target or len(members)<2 or self.hour-leader.get('army_formed',self.hour)>PARAMETERS['campaign_hours']:
                self.release(members);continue
            days=self.group_days(members);travel=self.eta(leader,target)
            if sum(u['healthy'] for u in members)<self.required(target):self.release(members);continue
            if days<max(6,travel/24+6):
                supply=self.support.get(leader['army'])
                if supply and supply['eta']/24+2<days and supply['food']>sum(size(u) for u in members)*self.o['limits']['field_ration']*3:
                    # Hold position to let the slower convoy catch up; do not disband its target.
                    self.move(leader,leader,vanilla_task='await_supply');continue
                if self.raid_for_food(members):continue
                self.release(members);continue
            if target.get('stale'):self.move(leader,target,vanilla_task='approach')
            elif (leader.get('order') or {}).get('type')!='siege' or (leader.get('order') or {}).get('target')!=target['id']:
                self.cmd.append(dict(type='siege',unit=leader['id'],target=target['id'],vanilla_task='siege'))

    def independent(self):
        for u in self.parties:
            if u['id'] in self.done or u['battle'] or u['army'] or u['healthy']<50 or u['wounded']>size(u)*.25:continue
            self.raid_for_food([u])
        # Legacy patrol attack selection now sees visible enemy farmer carts as well.
        super().independent()

    def run(self):
        if not self.cities:return []
        self.logistics();self.refill_and_raise();self.relief();self.campaigns();self.musters();self.launch();self.independent()
        return self.cmd[:100]
