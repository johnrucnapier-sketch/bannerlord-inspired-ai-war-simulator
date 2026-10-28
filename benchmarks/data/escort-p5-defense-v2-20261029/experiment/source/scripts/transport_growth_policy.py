"""Three resource-funded village squads; patrol and escort candidates."""
import math
from collections import Counter
from scripts.transport_triple_policy import Controller as LegacyController, predict_cart
from aiwar.navigation import travel_hours, find_route


def distance(a,b):return math.hypot(a['x']-b['x'],a['y']-b['y'])


class GrowthController:
    def __init__(self,target,floor,style="p5"):
        assert style in ("grow27","grow57")
        self.style=style
        self.threshold=27 if style=="grow27" else 57
        self.targets={};self.qualified=set();self.upgrade_events=[];self.patrol_index={}
        self.bootstrapped=False;self.commissioned=set();self.eta_cache={}
        assert floor in (18,54) and floor<=target<=150
        self.target=57;self.floor=18
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
                                 dict(type='set_strength',unit=u['id'],target=27)])
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
        for uid in self.assigned.values():
            self.targets.setdefault(uid,27)
            if own[uid]['healthy']>=self.threshold:self.qualified.add(uid)
        # Only buy an upgrade with currently available, real city resources.
        # Reserve all existing squads' deficits first; never strip another escort.
        for c in cities:
            ids=[self.assigned.get((c['id'],slot)) for slot in range(3)]
            if any(uid is None for uid in ids):continue
            g=own[c['garrison']]
            g_available=g['healthy'] if not g['battle'] and not g['army'] and distance(g,c)<=500 else 0
            deficits=sum(max(0,self.targets[uid]-own[uid]['healthy']) for uid in ids)
            spare=c['recruits']+g_available-deficits
            candidate=next((uid for uid in ids if self.targets[uid]==27),None)
            if candidate and spare>=30 and all(own[uid]['healthy']>=27 for uid in ids):
                u=own[candidate]
                if not u['battle'] and distance(u,c)<=500:
                    self.targets[candidate]=57
                    self.upgrade_events.append(dict(hour=obs['hour'],city=c['id'],unit=candidate,slot=ids.index(candidate)))
                    self.metrics['upgrades_to_57']+=1
        # Reserve shared resources within one decision; commands apply sequentially.
        garrisons={c['id']:dict(own[c['garrison']]) for c in cities}
        recruits={c['id']:c['recruits'] for c in cities}
        clan_counts=Counter(u['clan'] for u in parties)
        commands=[];ready=[]
        vacant=Counter(c['id'] for c,slot in slots if (c['id'],slot) not in self.assigned)
        def move(u,p,**meta):
            order=u.get('order') or {}
            cmd=dict(type='move',unit=u['id'],x=p['x'],y=p['y'],**meta)
            if any(order.get(k)!=v for k,v in cmd.items()):commands.append(cmd)
        for c,slot in sorted(slots,key=lambda pair:((pair[0]['id'],pair[1]) in self.assigned,pair[0]['id'],pair[1])):
            uid=self.assigned.get((c['id'],slot));g=garrisons[c['id']]
            if uid is None:
                if clan_counts[c['clan']]>=obs['limits']['clan_party_cap']:continue
                if recruits[c['id']]>=self.floor:
                    count=min(27,recruits[c['id']]);recruits[c['id']]-=count;clan_counts[c['clan']]+=1
                    commands.append(dict(type='create',city=c['id'],count=count,source='recruits'));vacant[c['id']]-=1
                elif not g['battle'] and not g['army'] and distance(g,c)<=500 and g['healthy']>=self.floor:
                    count=min(27,g['healthy']);g['healthy']-=count;clan_counts[c['clan']]+=1
                    commands.append(dict(type='create',city=c['id'],count=count,source='garrison'));vacant[c['id']]-=1
                self.metrics['unfilled_party_slot_hours']+=6
                continue
            u=own[uid];target=self.targets[uid];floor=54 if target==57 else 18
            if u['healthy']>=target:self.commissioned.add(uid)
            if u['battle']:continue
            assert not u['army']
            if u.get('refill_target',150)!=target:
                commands.append(dict(type='set_strength',unit=uid,target=target))
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
                surplus=min(max(0,u['healthy']-target),room)
                if surplus:commands.append(dict(type='transfer',unit=uid,target=g['id'],count=surplus));g['healthy']+=surplus
                missing=max(0,target-u['healthy'])
                take=min(missing,max(0,g['healthy']-18*vacant[c['id']]),max(0,150-u['healthy']-u['wounded']+unload)) if garrison_ready else 0
                if take and garrison_ready:
                    commands.append(dict(type='transfer',unit=g['id'],target=uid,count=take));g['healthy']-=take
                recruit=min(max(0,missing-take),max(0,recruits[c['id']]-18*vacant[c['id']]),max(0,150-u['healthy']-u['wounded']+unload-take))
                if recruit:
                    commands.append(dict(type='recruit',city=c['id'],unit=uid,count=recruit));recruits[c['id']]-=recruit
                full_food=(u['healthy']+u['wounded'])*obs['limits']['field_ration']*obs['limits']['carry_days']
                if unload or surplus or take or recruit or (u['healthy']<floor or (uid in self.commissioned and u['healthy']!=target)) or u['wounded'] or u['food']<full_food:
                    if u.get('path') or u.get('order'):commands.append(dict(type='stop',unit=uid))
                    self.metrics['refit_wait_party_hours']+=6
                    if u['healthy']<target:self.metrics['waiting_for_soldiers_hours']+=6
                    if u['food']<full_food:self.metrics['waiting_for_food_hours']+=6
                    continue
            else:
                self.metrics['away_party_hours']+=6
                days=u['food']/max(1,(u['healthy']+u['wounded'])*obs['limits']['field_ration'])
                return_days=math.ceil(distance(u,c)/250/24)+3
                reason='health' if u['healthy']<floor else 'food' if days<return_days else None
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
            self.escort_order(obs,u,c,villages[0],own,bandits,ready,commands,move)
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
        if cart is not None and (cart['phase']!='idle' or cart['battle']):
            point=predict_cart(cart,obs,3) if not cart['battle'] else cart
            move(u,point,escort_cart=cart['id']);self.metrics['escort_party_hours']+=6
            return
        until=168-obs['hour']%168
        back=travel_hours(obs['terrain'],u,v,obs['speeds'],max_hours=336)
        if back is None or until<=back+12:
            move(u,v,timed_guard=True);self.metrics['schedule_guard_party_hours']+=6
            return
        if u['id'] not in self.qualified:
            key=(c['id'],v['id'])
            if key not in self.eta_cache:
                self.eta_cache[key]=travel_hours(obs['terrain'],dict(c,kind='party',army=None),v,obs['speeds'],max_hours=336)
            eta=self.eta_cache[key]
            move(u,v if eta is None or until<=eta+12 else c,timed_rest=True)
            return
        self.metrics['clearance_available_party_hours']+=6
        # Only idle, qualified escorts can claim a visible target.
        idle=[]
        for peer,city in ready:
            if peer['id'] not in self.qualified:continue
            slot=next(i for (cid,i),uid in self.assigned.items() if uid==peer['id'])
            vs=sorted([x for x in obs['villages'] if x['city']==city['id']],key=lambda x:(x['x'],x['y'],x['id']))
            cv=own.get(vs[slot].get('cart'))
            if cv is None or (cv['phase']=='idle' and not cv['battle']):idle.append(peer)
        eligible=[b for b in bandits if distance(u,b)<12000 and distance(b,v)<18000
                  and min(idle,key=lambda p:(distance(p,b),p['id']))['id']==u['id']]
        current=(u.get('order') or {}).get('target')
        eligible.sort(key=lambda b:(b['id']!=current,distance(u,b),b['id']))
        for b in eligible[:3]:
            approach=travel_hours(obs['terrain'],u,b,obs['speeds'],max_hours=until)
            homeward=travel_hours(obs['terrain'],dict(b,kind='party',army=None),v,obs['speeds'],max_hours=until)
            if approach is not None and homeward is not None and approach+homeward+24<=until:
                commands.append(dict(type='attack',unit=u['id'],target=b['id']))
                self.metrics['clearance_attack_party_hours']+=6
                return
        # Search instead of standing still when no visible bandit can be intercepted.
        key=('route',v['id'])
        if key not in self.eta_cache:
            pts=[dict(x=(v['x']+c['x'])//2,y=(v['y']+c['y'])//2)]
            pts += [dict(x=v['x']+dx,y=v['y']+dy) for dx,dy in ((8000,0),(0,8000),(-8000,0),(0,-8000))]
            self.eta_cache[key]=[p for p in pts if 0<=p['x']<120000 and 0<=p['y']<80000 and obs['terrain'][p['y']//2000][p['x']//2000]!=2]
        points=self.eta_cache[key]
        if points:
            index=self.patrol_index.get(u['id'],0)%len(points)
            if distance(u,points[index])<=500:index=(index+1)%len(points)
            for shift in range(len(points)):
                j=(index+shift)%len(points);point=points[j]
                there=travel_hours(obs['terrain'],u,point,obs['speeds'],max_hours=until)
                back=travel_hours(obs['terrain'],dict(point,kind='party',army=None),v,obs['speeds'],max_hours=until)
                if there is not None and back is not None and there+back+12<=until:
                    self.patrol_index[u['id']]=j;move(u,point,clearance_route=True)
                    self.metrics['clearance_search_party_hours']+=6
                    return
        move(u,v,timed_guard=True);self.metrics['schedule_guard_party_hours']+=6


def Controller(target,floor,style):
    return GrowthController(target,floor,style) if style in ('grow27','grow57') else LegacyController(target,floor,style)
