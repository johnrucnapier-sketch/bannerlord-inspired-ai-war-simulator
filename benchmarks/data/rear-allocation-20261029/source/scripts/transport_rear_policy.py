"""Identical three-escort development, then four rear-force resource allocations."""
from collections import Counter
import math
from scripts.transport_hunter_policy import Controller as HunterController
from scripts.transport_growth_policy import distance
from scripts.transport_triple_policy import Controller as LegacyController

class Controller(HunterController):
    def __init__(self,target,floor,style):
        assert style in ('hp','h','p','pp')
        super().__init__(target,floor,'h3')
        self.mix=style;self.phases={};self.phase_events=[];self.retiring={};self.active_ids=set()

    def allowed_slots(self,cid):
        return self.phases[cid]['active'] if cid in self.phases else [0,1,2]

    def decide(self,obs):
        self.previous_sightings=dict(self.sightings)
        for b in obs['units']:
            if b['nation']==-1:self.sightings[b['id']]=dict(x=b['x'],y=b['y'],hour=obs['hour'])
        cmds=self.decide_allocation(obs)
        self.hunter_ids={self.assigned[(cid,slot)] for cid,slot in self.hunter_slots.items() if (cid,slot) in self.assigned}
        self.active_ids=set(self.assigned.values())
        self.metrics['hunter_role_hours']+=6*len(self.hunter_slots)
        self.metrics['active_role_hours']+=6*sum(len(self.allowed_slots(c['id'])) for c in obs['cities'] if c['nation']==obs['nation'])
        own={u['id']:u for u in obs['units'] if u['nation']==obs['nation']}
        self.locks={uid:bid for uid,bid in self.locks.items() if uid in own}
        return cmds

    def decide_allocation(self,obs):
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
        used=set(self.assigned.values())|set(self.retiring)
        slots=[(c,slot) for c in cities for slot in self.allowed_slots(c['id'])]
        for c,slot in slots:
            key=(c['id'],slot)
            if key in self.assigned:continue
            available=[u for u in parties if u['id'] not in used and u['clan']==c['clan'] and distance(u,c)<=500]
            if available:
                u=min(available,key=lambda u:(distance(u,c),u['id']))
                self.assigned[key]=u['id'];used.add(u['id'])
        for c in cities:
            if c['id'] in self.phases:continue
            full=[(slot,uid) for (cid,slot),uid in self.assigned.items() if cid==c['id'] and own[uid]['healthy']>=57]
            if full:
                first,uid=min(full);other=[s for s in range(3) if s!=first]
                hunter=first if self.mix in ('hp','h') else None
                protectors=([other[0]] if self.mix=='hp' else [] if self.mix=='h' else [first] if self.mix=='p' else [first,other[0]])
                active=([hunter] if hunter is not None else [])+protectors
                self.phases[c['id']]=dict(active=active,hunter=hunter,protectors=protectors)
                event=dict(hour=obs['hour'],city=c['id'],unit=uid,active=active,hunter=hunter,protectors=protectors)
                self.phase_events.append(event)
                if hunter is not None:self.hunter_slots[c['id']]=hunter;self.role_events.append(event)
                for slot in range(3):
                    if slot not in active:
                        old=self.assigned.pop((c['id'],slot),None)
                        if old:self.retiring[old]=c['id']
        slots=[(c,slot) for c in cities for slot in self.allowed_slots(c['id'])]
        for uid in self.assigned.values():
            self.targets.setdefault(uid,27)
            if own[uid]['healthy']>=self.threshold:self.qualified.add(uid)
        # Only buy an upgrade with currently available, real city resources.
        # Reserve all existing squads' deficits first; never strip another escort.
        for c in cities:
            ids=[self.assigned.get((c['id'],slot)) for slot in self.allowed_slots(c['id'])]
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
                    self.upgrade_events.append(dict(hour=obs['hour'],city=c['id'],unit=candidate,slot=self.allowed_slots(c['id'])[ids.index(candidate)]))
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
        # Retire unused squads using legal transfers. Do not demobilize soldiers into civilians.
        for uid,cid in list(self.retiring.items()):
            u=own.get(uid)
            if u is None:self.retiring.pop(uid,None);continue
            c=next(c for c in cities if c['id']==cid);g=garrisons[cid]
            if u['battle']:continue
            if u.get('refill_target',150)!=1:commands.append(dict(type='set_strength',unit=uid,target=1))
            if distance(u,c)>500:move(u,c,retire_home=True);continue
            if u.get('path') or u.get('order'):commands.append(dict(type='stop',unit=uid))
            if g['battle'] or g['army'] or distance(g,c)>500:
                self.metrics['retirement_blocked_party_hours']+=6;continue
            room=max(0,500-g['healthy']-g['wounded'])
            wounded=min(room,u['wounded']);room-=wounded
            healthy=min(room,u['healthy'])
            if wounded:commands.append(dict(type='transfer',unit=uid,target=g['id'],count=wounded,wounded=True));g['wounded']+=wounded
            if healthy:commands.append(dict(type='transfer',unit=uid,target=g['id'],count=healthy));g['healthy']+=healthy
            self.metrics['retired_soldiers']+=healthy+wounded
            if room<u['healthy']:self.metrics['retirement_blocked_party_hours']+=6
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
        phase=self.phases.get(c['id'])
        if phase is None:
            saved=self.style;self.style='timed'
            try:LegacyController.escort_order(self,obs,u,c,v,own,bandits,ready,commands,move)
            finally:self.style=saved
            return
        if phase['hunter'] is not None and u['id']==self.assigned.get((c['id'],phase['hunter'])):
            if u['healthy']<54:move(u,c,hunter_rebuild=True);return
            self.hunt(obs,u,c,bandits,commands,move)
        else:self.protect(obs,u,c,own,bandits,ready,commands,move)

    def protect(self,obs,u,c,own,bandits,ready,commands,move):
        defenders=[self.assigned[(c['id'],s)] for s in self.phases[c['id']]['protectors'] if (c['id'],s) in self.assigned]
        villages=sorted([v for v in obs['villages'] if v['city']==c['id']],key=lambda v:(v['x'],v['y'],v['id']))
        if len(defenders)==2:villages=villages[:2] if u['id']==defenders[0] else villages[2:]
        center=dict(x=sum(v['x'] for v in villages)//len(villages),y=sum(v['y'] for v in villages)//len(villages))
        protect_ids={self.assigned[(cid,s)] for cid,p in self.phases.items() for s in p['protectors'] if (cid,s) in self.assigned}
        peers=[p for p,city in ready if p['id'] in protect_ids]
        eligible=[b for b in bandits if min(peers,key=lambda p:(distance(p,b),p['id']))['id']==u['id']]
        current=next((b for b in eligible if b['id']==(u.get('order') or {}).get('target')),None)
        if current and distance(u,current)<10000 and distance(current,center)<18000:return
        nearby=[b for b in eligible if distance(u,b)<8000]
        if nearby:
            b=min(nearby,key=lambda b:(distance(u,b),b['id']));commands.append(dict(type='attack',unit=u['id'],target=b['id']));return
        if u.get('path') and (u.get('order') or {}).get('strength_route'):return
        points=[p for v in villages for p in (v,c)];index=self.route_index.get(u['id'],-1)
        for _ in points:
            index=(index+1)%len(points)
            if distance(u,points[index])>500:break
        self.route_index[u['id']]=index;move(u,points[index],strength_route=True)
