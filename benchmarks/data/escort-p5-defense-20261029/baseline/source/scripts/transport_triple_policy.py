"""Three resource-funded village squads; patrol and escort candidates."""
import math
from collections import Counter


def distance(a,b):return math.hypot(a['x']-b['x'],a['y']-b['y'])


class Controller:
    def __init__(self,target,floor,style="p5"):
        assert style in ("p3","p5","timed","escort","hybrid")
        self.style=style
        self.bootstrapped=False;self.commissioned=set();self.eta_cache={}
        assert floor in (18,54) and floor<=target<=150
        self.target=target;self.floor=floor
        self.assigned={};self.returning={};self.route_index={};self.away={}
        self.metrics=Counter();self.departure_health=Counter()

    def decide(self,obs):
        cities=sorted([c for c in obs['cities'] if c['nation']==obs['nation']],key=lambda c:c['id'])
        own={u['id']:u for u in obs['units'] if u['nation']==obs['nation']}
        parties=[u for u in own.values() if u['kind']=='party']
        if not self.bootstrapped:
            assert obs['hour']==0
            commands=[]
            for c in cities:
                u=next(u for u in parties if u['clan']==c['clan'] and distance(u,c)<=500)
                assert u['healthy']==30 and own[c['garrison']]['healthy']==50
                commands.extend([dict(type='transfer',unit=u['id'],target=c['garrison'],count=3),
                                 dict(type='create',city=c['id'],count=27,source='garrison'),
                                 dict(type='create',city=c['id'],count=26,source='garrison'),
                                 dict(type='set_strength',unit=u['id'],target=30)])
            self.bootstrapped=True
            return commands
        self.assigned={slot:uid for slot,uid in self.assigned.items() if uid in own}
        used=set(self.assigned.values())
        slots=[(c,slot) for c in cities for slot in range(3)]
        for c,slot in slots:
            key=(c['id'],slot)
            if key in self.assigned:continue
            available=[u for u in parties if u['id'] not in used and u['clan']==c['clan'] and distance(u,c)<=500]
            if available:
                u=min(available,key=lambda u:(distance(u,c),u['id']))
                self.assigned[key]=u['id'];used.add(u['id'])
        # Reserve shared resources within one decision; commands apply sequentially.
        garrisons={c['id']:dict(own[c['garrison']]) for c in cities}
        recruits={c['id']:c['recruits'] for c in cities}
        clan_counts=Counter(u['clan'] for u in parties)
        commands=[];ready=[]
        def move(u,p,**meta):
            order=u.get('order') or {}
            cmd=dict(type='move',unit=u['id'],x=p['x'],y=p['y'],**meta)
            if any(order.get(k)!=v for k,v in cmd.items()):commands.append(cmd)
        for c,slot in slots:
            uid=self.assigned.get((c['id'],slot));g=garrisons[c['id']]
            if uid is None:
                if clan_counts[c['clan']]>=obs['limits']['clan_party_cap']:continue
                if recruits[c['id']]>=self.floor:
                    count=min(self.target,recruits[c['id']]);recruits[c['id']]-=count;clan_counts[c['clan']]+=1
                    commands.append(dict(type='create',city=c['id'],count=count,source='recruits'))
                elif not g['battle'] and not g['army'] and distance(g,c)<=500 and g['healthy']>=self.floor:
                    count=min(self.target,g['healthy']);g['healthy']-=count;clan_counts[c['clan']]+=1
                    commands.append(dict(type='create',city=c['id'],count=count,source='garrison'))
                self.metrics['unfilled_party_slot_hours']+=6
                continue
            u=own[uid]
            if u['healthy']>=self.target:self.commissioned.add(uid)
            if u['battle']:continue
            assert not u['army']
            if u.get('refill_target',150)!=self.target:
                commands.append(dict(type='set_strength',unit=uid,target=self.target))
            at_home=distance(u,c)<=500
            if at_home:
                if uid in self.away:
                    self.metrics['completed_outings']+=1
                    self.metrics['outing_hours']+=obs['hour']-self.away.pop(uid)
                self.returning.pop(uid,None)
                garrison_ready=not g['battle'] and not g['army'] and distance(g,c)<=500
                room=max(0,500-g['healthy']-g['wounded']) if garrison_ready else 0
                unload=min(u['wounded'],room)
                if unload:commands.append(dict(type='transfer',unit=uid,target=g['id'],count=unload,wounded=True));room-=unload;g['wounded']+=unload
                surplus=min(max(0,u['healthy']-self.target),room)
                if surplus:commands.append(dict(type='transfer',unit=uid,target=g['id'],count=surplus));g['healthy']+=surplus
                missing=max(0,self.target-u['healthy'])
                take=min(missing,max(0,g['healthy']),max(0,150-u['healthy']-u['wounded']+unload)) if garrison_ready else 0
                if take and garrison_ready:
                    commands.append(dict(type='transfer',unit=g['id'],target=uid,count=take));g['healthy']-=take
                full_food=(u['healthy']+u['wounded'])*obs['limits']['field_ration']*obs['limits']['carry_days']
                if unload or surplus or take or (u['healthy']<self.floor or (uid in self.commissioned and u['healthy']!=self.target)) or u['wounded'] or u['food']<full_food:
                    if u.get('path') or u.get('order'):commands.append(dict(type='stop',unit=uid))
                    self.metrics['refit_wait_party_hours']+=6
                    if u['healthy']<self.target:self.metrics['waiting_for_soldiers_hours']+=6
                    if u['food']<full_food:self.metrics['waiting_for_food_hours']+=6
                    continue
            else:
                self.metrics['away_party_hours']+=6
                days=u['food']/max(1,(u['healthy']+u['wounded'])*obs['limits']['field_ration'])
                return_days=math.ceil(distance(u,c)/250/24)+3
                reason='health' if u['healthy']<self.floor else 'food' if days<return_days else None
                if reason and uid not in self.returning:
                    self.returning[uid]=reason;self.metrics['forced_return_'+reason]+=1
                if uid in self.returning:
                    move(u,c,strength_return=True)
                    continue
            ready.append((u,c))
        bandits=[b for b in obs['units'] if b['nation']==-1]
        for u,c in ready:
            uid=u['id']
            villages=sorted([v for v in obs['villages'] if v['nation']==obs['nation'] and v['city']==c['id']],key=lambda v:(v['x'],v['y'],v['id']))
            slot=next(slot for (cid,slot),assigned in self.assigned.items() if assigned==uid)
            villages= villages[slot:slot+1]
            if not villages:continue
            if self.style in ('timed','escort','hybrid'):
                self.escort_order(obs,u,c,villages[0],own,bandits,ready,commands,move)
                continue
            center=dict(x=sum(v['x'] for v in villages)//len(villages),y=sum(v['y'] for v in villages)//len(villages))
            eligible=bandits if self.style=="p3" else [b for b in bandits if min(ready,key=lambda pair:(distance(pair[0],b),pair[0]['id']))[0]['id']==uid]
            current=next((b for b in eligible if b['id']==(u.get('order') or {}).get('target')),None)
            if current and distance(u,current)<10000 and distance(current,center)<18000:continue
            nearby=[b for b in eligible if distance(u,b)<8000]
            if nearby:
                b=min(nearby,key=lambda b:(distance(u,b),b['id']))
                commands.append(dict(type='attack',unit=uid,target=b['id']))
                continue
            if u.get('path') and (u.get('order') or {}).get('strength_route'):continue
            points=[p for v in villages for p in ((v,dict(x=(v["x"]+c["x"])//2,y=(v["y"]+c["y"])//2),c) if self.style=="p3" else (v,c))]
            index=self.route_index.get(uid,-1)
            for _ in points:
                index=(index+1)%len(points)
                if distance(u,points[index])>500:break
            self.route_index[uid]=index
            move(u,points[index],strength_route=True)
        homes={uid:next(c for c in cities if c['id']==cid) for (cid,slot),uid in self.assigned.items()}
        for cmd in commands[:100]:
            uid=cmd.get('unit');u=own.get(uid);c=homes.get(uid)
            if not u or not c or uid in self.away or distance(u,c)>500:continue
            point=cmd if cmd['type']=='move' else next((b for b in bandits if b['id']==cmd.get('target')),None) if cmd['type']=='attack' else None
            if point and distance(point,c)>500:
                self.away[uid]=obs['hour'];self.metrics['departures']+=1;self.departure_health[str(u['healthy'])]+=1
        assert len(set(self.assigned.values()))==len(self.assigned)
        if len(commands)>100:self.metrics["command_budget_deferrals"]+=len(commands)-100
        return commands[:100]

    def escort_order(self,obs,u,c,v,own,bandits,ready,commands,move):
        cart=own.get(v.get('cart'))
        active=cart is not None and (cart['phase']!='idle' or cart['battle'])
        if active:
            point=predict_cart(cart,obs,3) if not cart['battle'] else cart
            move(u,point,escort_cart=cart['id'])
            self.metrics['escort_party_hours']+=6
            return
        if self.style=='timed':
            from aiwar.navigation import travel_hours
            key=(c['id'],v['id'])
            if key not in self.eta_cache:
                start=dict(c,kind='party',army=None)
                self.eta_cache[key]=travel_hours(obs['terrain'],start,v,obs['speeds'],max_hours=336)
            eta=self.eta_cache[key]
            until=168-obs['hour']%168
            if eta is None or until<=eta+12:move(u,v,timed_guard=True)
            else:move(u,c,timed_rest=True)
            return
        if self.style=='hybrid':
            # No chase when the next scheduled convoy departure is close.
            from aiwar.navigation import travel_hours
            until=168-obs['hour']%168
            local=[b for b in bandits if distance(b,v)<6000 and distance(u,b)<8000
                   and min(ready,key=lambda pair:(distance(pair[0],b),pair[0]['id']))[0]['id']==u['id']]
            if local and until>48:
                b=min(local,key=lambda b:(distance(u,b),b['id']))
                commands.append(dict(type='attack',unit=u['id'],target=b['id']))
                self.metrics['idle_clear_party_hours']+=6
                return
        move(u,v,village_guard=True)
        self.metrics['village_guard_party_hours']+=6


def predict_cart(cart,obs,hours):
    # Public current path only; no knowledge of future contacts or orders.
    x,y=cart['x'],cart['y'];path=[list(p) for p in cart.get('path',[])]
    for _ in range(hours):
        speed=obs['speeds']['village_cart']
        if obs['terrain'][min(39,y//2000)][min(59,x//2000)]==1:speed=speed*3//4
        while path and speed>0:
            tx,ty=path[0];dx,dy=tx-x,ty-y;d=math.isqrt(dx*dx+dy*dy)
            if d<=speed:x,y=tx,ty;path.pop(0);speed-=d
            else:x+=int(dx*speed/d);y+=int(dy*speed/d);speed=0
    return dict(x=x,y=y)
