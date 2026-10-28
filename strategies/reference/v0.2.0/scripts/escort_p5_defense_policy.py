"""D1: resource-funded escort growth, P5 rear, defensive mobilization first."""
import copy,math
from collections import Counter
from scripts.transport_growth_policy import GrowthController, distance, LegacyController
from aiwar.relief import staging_point

class Controller(GrowthController):
    def __init__(self):
        super().__init__(57,18,'grow57')
        self.switched=set();self.phase_events=[];self.missions={};self.campaign=None
        self.war_events=[];self.cooldown=0

    def escort_order(self,obs,u,c,v,own,bandits,ready,commands,move):
        if c['id'] not in self.switched and not any(m['home']==c['id'] for m in self.missions.values()):
            old=self.style
            try:
                self.style='timed'
                return LegacyController.escort_order(self,obs,u,c,v,own,bandits,ready,commands,move)
            finally:self.style=old
        peers=[uid for (cid,slot),uid in sorted(self.assigned.items()) if cid==c['id'] and uid not in self.missions]
        villages=sorted([v for v in obs['villages'] if v['nation']==obs['nation'] and v['city']==c['id']],key=lambda v:(v['x'],v['y'],v['id']))
        if not peers or not villages:return
        index=peers.index(u['id'])
        sectors=([villages] if len(peers)==1 else [villages[:2],villages[2:]] if len(peers)==2 else [[v] for v in villages])
        sector=sectors[index%len(sectors)];center=dict(x=sum(v['x'] for v in sector)//len(sector),y=sum(v['y'] for v in sector)//len(sector))
        eligible=[b for b in bandits if min(ready,key=lambda pair:(distance(pair[0],b),pair[0]['id']))[0]['id']==u['id']]
        current=next((b for b in eligible if b['id']==(u.get('order') or {}).get('target')),None)
        if current and distance(u,current)<10000 and distance(current,center)<18000:return
        nearby=[b for b in eligible if distance(u,b)<8000]
        if nearby:
            b=min(nearby,key=lambda b:(distance(u,b),b['id']));commands.append(dict(type='attack',unit=u['id'],target=b['id']));return
        if u.get('path') and (u.get('order') or {}).get('strength_route'):return
        points=[point for v in sector for point in (v,c)];idx=self.route_index.get(u['id'],-1)
        for _ in points:
            idx=(idx+1)%len(points)
            if distance(u,points[idx])>500:break
        self.route_index[u['id']]=idx;move(u,points[idx],strength_route=True)

    def military(self,obs):
        """Only filtered observations. Mutate a private observation to reserve logistics."""
        n=obs['nation'];hour=obs['hour'];commands=[]
        cities={c['id']:c for c in obs['cities'] if c['nation']==n and 'recruits' in c}
        own={u['id']:u for u in obs['units'] if u['nation']==n}
        parties={uid:u for uid,u in own.items() if u['kind']=='party'}
        blocked={a['city'] for a in obs.get('relief_requests',[])}
        enemies=[u for u in obs['units'] if u['nation']>=0 and u['nation']!=n and u['kind']=='party']
        alerts={a['city']:a for a in obs.get('relief_requests',[])}
        threats=[]
        for c in cities.values():
            near=[u for u in enemies if (u['army'] and distance(u,c)<=24000) or distance(u,c)<=10000 or (c['id'] in alerts and u['battle'] in (alerts[c['id']]['battle'],alerts[c['id']].get('relief_battle')))]
            if near:threats.append((c,near))
        threats.sort(key=lambda pair:(pair[0]['id'] not in alerts,-sum(u['healthy'] for u in pair[1]),pair[0]['id']))
        self.missions={uid:m for uid,m in self.missions.items() if uid in parties}
        def move(u,p,**meta):
            cmd=dict(type='move',unit=u['id'],x=p['x'],y=p['y'],**meta)
            if any((u.get('order') or {}).get(k)!=v for k,v in cmd.items()):commands.append(cmd)
        def stop_campaign(reason):
            if self.campaign:self.war_events.append(dict(hour=hour,event='campaign_end',reason=reason,kind=self.campaign['kind']))
            seen=set()
            for uid,m in self.missions.items():
                u=parties[uid];m['phase']='return'
                if u['army'] and not u['battle'] and u['army'] not in seen:
                    commands.append(dict(type='disband',unit=uid));seen.add(u['army'])
            self.campaign=None;self.cooldown=hour+48
        if self.campaign:
            p=self.campaign;active=[parties[uid] for uid,m in self.missions.items() if m['phase']!='return']
            danger=threats and p['kind']=='attack'
            target=next((c for c in obs['cities'] if c['id']==p['target']),None)
            ended=(p['kind']=='defense' and not any(c['id']==p['target'] for c,es in threats)) or (p['kind']=='attack' and (not target or target['nation']==n))
            tired=any(hour-u['last_battle']<6 or (u['food']/max(1,(u['healthy']+u['wounded'])*obs['limits']['field_ration'])<5 and self.missions[u['id']]['phase']=='field') for u in active)
            if not active or danger or ended or tired or hour-p['start']>672:stop_campaign('defense_priority' if danger else 'complete_or_refit')
        # Orphaned parties from captured cities return and remain eligible for later assignment.
        for uid,m in list(self.missions.items()):
            if m['home'] not in cities:
                if cities:m['home']=min(cities.values(),key=lambda c:distance(parties[uid],c))['id']
                m['phase']='return'
        assigned_ids=set(self.assigned.values())
        valid_homes=set(cities)
        for uid,u in parties.items():
            orphan=(bool(self.assigned) and uid not in assigned_ids) or any(v==uid and cid not in valid_homes for (cid,slot),v in self.assigned.items())
            if orphan and uid not in self.missions and cities:
                home=min(cities.values(),key=lambda c:distance(u,c))
                if distance(u,home)>500 or u['army']:self.missions[uid]=dict(home=home['id'],phase='return')
        if not self.campaign and not self.missions and cities and (threats or hour>=self.cooldown):
            target=None;kind=None;required=0;stage=None
            if threats:
                c,es=threats[0];target=c;kind='defense';required=max(150,math.ceil(sum(u['healthy'] for u in es)*1.2))
                stage=staging_point(obs,alerts[c['id']],list(cities.values())) if c['id'] in alerts else c
            else:
                options=[c for c in obs['cities'] if c['nation']!=n and c['id'] in obs.get('frontier_targets',[])]
                if options:
                    target=min(options,key=lambda c:(c.get('healthy',50)+c.get('militia_healthy',100)/2,c['id']))
                    bases=[c for c in cities.values() if target['id'] in c['neighbors']]
                    if bases:
                        stage=min(bases,key=lambda c:(distance(c,target),c['id']));kind='attack'
                        required=max(300,math.ceil(2.5*(target.get('healthy',50)+target.get('militia_healthy',100)/2)))
            if target and stage and kind:
                candidates=[]
                for c in cities.values():
                    if c['id'] in blocked or (kind=='attack' and c['id'] not in self.switched):continue
                    ids=[uid for (cid,slot),uid in sorted(self.assigned.items()) if cid==c['id'] and uid in parties]
                    if len(ids)<2:continue
                    g=own.get(c['garrison']);reserve=c['recruits']+(g['healthy'] if g and not g['battle'] and not g['army'] and distance(g,c)<=500 else 0)
                    reserve-=sum(max(0,self.targets.get(uid,27)-parties[uid]['healthy']) for uid in ids)
                    local=[]
                    for uid in sorted(ids,key=lambda uid:(-parties[uid]['healthy'],uid)):
                        u=parties[uid]
                        if u['battle'] or u['army'] or len(local)>=min(2,len(ids)-1):continue
                        cost=max(0,150-max(u['healthy'],self.targets.get(uid,27)))
                        if reserve<cost:continue
                        reserve-=cost;local.append(uid)
                        candidates.append((distance(u,c)+distance(c,stage),uid,c['id']))
                chosen=[]
                for _,uid,cid in sorted(candidates):
                    chosen.append((uid,cid))
                    if len(chosen)*150>=required and (kind=='defense' or len(chosen)>=2):break
                if chosen and len(chosen)*150>=required:
                    self.campaign=dict(kind=kind,target=target['id'],stage=dict(x=stage['x'],y=stage['y']),required=required,start=hour)
                    for uid,cid in chosen:self.missions[uid]=dict(home=cid,phase='refit')
                    self.war_events.append(dict(hour=hour,event='mobilize',kind=kind,target=target['id'],units=[u for u,c in chosen],required=required))
        # Real return, transfer/recruit and provision. Never set a simulated unit's actual strength.
        for uid,m in list(self.missions.items()):
            u=parties[uid]
            if u['battle']:continue
            c=cities.get(m['home'])
            if not c:continue
            if m['phase'] in ('return','refit'):
                if u['army']:
                    # Disband command above applies this tick; individual travel follows next tick.
                    if not any(cmd['type']=='disband' and parties[cmd['unit']]['army']==u['army'] for cmd in commands):commands.append(dict(type='disband',unit=uid))
                    continue
                if distance(u,c)>500 or c['id'] in blocked:
                    safe=[v for v in cities.values() if v['id'] not in blocked]
                    if c['id'] in blocked and safe:c=min(safe,key=lambda v:distance(u,v));m['home']=c['id']
                    move(u,c,campaign_phase='d1_refit');continue
                if m['phase']=='return':
                    self.targets[uid]=57;self.returning.pop(uid,None);self.away.pop(uid,None)
                    del self.missions[uid];continue
                if u.get('refill_target')!=150:commands.append(dict(type='set_strength',unit=uid,target=150))
                g=own[c['garrison']];unload=0
                available=not g['battle'] and not g['army'] and distance(g,c)<=500
                if available:
                    unload=min(u['wounded'],max(0,500-g['healthy']-g['wounded']))
                    if unload:commands.append(dict(type='transfer',unit=uid,target=g['id'],count=unload,wounded=True));g['wounded']+=unload
                need=min(150-u['healthy'],150-u['healthy']-u['wounded']+unload)
                take=min(need,g['healthy']) if available else 0
                if take:commands.append(dict(type='transfer',unit=g['id'],target=uid,count=take));g['healthy']-=take
                rec=min(need-take,c['recruits'])
                if rec:commands.append(dict(type='recruit',city=c['id'],unit=uid,count=rec));c['recruits']-=rec
                if u['healthy']>=150 and not u['wounded'] and u['food']>=150*obs['limits']['field_ration']*obs['limits']['carry_days']:
                    m['phase']='stage'
                else:
                    if u.get('path') or u.get('order'):commands.append(dict(type='stop',unit=uid))
                    continue
        p=self.campaign
        if p:
            if p['kind']=='defense' and p['target'] in alerts:
                stage=staging_point(obs,alerts[p['target']],list(cities.values()))
                if stage:p['stage']=stage
            active=[parties[uid] for uid,m in self.missions.items() if m['phase']!='return']
            if not active:return commands
            if any(u['battle'] for u in active):return commands
            field=[u for u in active if self.missions[u['id']]['phase']=='field']
            for u in active:
                if self.missions[u['id']]['phase']=='stage':
                    if p['kind']=='defense' and p['target'] in alerts:move(u,p['stage'],campaign_phase='relief',relief_city=p['target'],relief_action='wait')
                    else:move(u,p['stage'],campaign_phase='d1_stage')
            arrived=[u for u in active if self.missions[u['id']]['phase']=='stage' and distance(u,p['stage'])<=100]
            if len(arrived)==len(active) and sum(u['healthy'] for u in arrived)>=p['required']:
                leader=min(arrived,key=lambda u:u['id'])
                if len(arrived)>1:commands.append(dict(type='assemble',unit=leader['id'],units=[u['id'] for u in arrived if u!=leader],campaign_target=p['target']))
                for u in arrived:self.missions[u['id']]['phase']='field'
                field=arrived
            if field:
                leader=min(field,key=lambda u:u['id'])
                if p['kind']=='attack':
                    target=next((c for c in obs['cities'] if c['id']==p['target']),None)
                    if target and p['target'] in obs.get('frontier_targets',[]):
                        if target.get('stale'):move(leader,target,campaign_phase='d1_approach')
                        else:commands.append(dict(type='siege',unit=leader['id'],target=p['target']))
                else:
                    es=next((es for c,es in threats if c['id']==p['target']),[])
                    if es and sum(u['healthy'] for u in field)>=sum(u['healthy'] for u in es)*1.1:
                        enemy=min(es,key=lambda u:distance(leader,u));commands.append(dict(type='attack',unit=leader['id'],target=enemy['id']))
        return commands

    def decide(self,obs):
        obs=copy.deepcopy(obs)
        warcommands=self.military(obs) if self.bootstrapped else []
        blocked={a['city'] for a in obs.get('relief_requests',[])}
        cities=sorted([c for c in obs['cities'] if c['nation']==obs['nation'] and 'recruits' in c],key=lambda c:c['id'])
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
        self.assigned={slot:uid for slot,uid in self.assigned.items() if uid in own and any(c['id']==slot[0] for c in cities)}
        used=set(self.assigned.values())
        slots=[(c,slot) for c in cities for slot in range(3)]
        for c,slot in slots:
            key=(c['id'],slot)
            if key in self.assigned:continue
            available=[u for u in parties if u['id'] not in used and u['id'] not in self.missions and not u['army'] and distance(u,c)<=500]
            if available:
                u=min(available,key=lambda u:(u['clan']!=c['clan'],distance(u,c),u['id']))
                self.assigned[key]=u['id'];used.add(u['id'])
        for uid in self.assigned.values():
            self.targets.setdefault(uid,27)
            if obs.get('direct_garrison_delivery'):self.targets[uid]=max(self.targets[uid],own[uid].get('reserve_refill_target',0))
            if own[uid]['healthy']>=self.threshold:self.qualified.add(uid)
        for c in cities:
            ids=[self.assigned.get((c['id'],i)) for i in range(3)]
            if c['id'] not in self.switched and all(uid in own and own[uid]['healthy']>=57 for uid in ids):
                self.switched.add(c['id']);self.phase_events.append(dict(hour=obs['hour'],city=c['id']))
        # Only buy an upgrade with currently available, real city resources.
        # Reserve all existing squads' deficits first; never strip another escort.
        for c in cities:
            ids=[self.assigned.get((c['id'],slot)) for slot in range(3)]
            if c['id'] in blocked or any(uid is None or uid in self.missions for uid in ids):continue
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
        commands=warcommands;ready=[]
        vacant=Counter(c['id'] for c,slot in slots if (c['id'],slot) not in self.assigned)
        def move(u,p,**meta):
            order=u.get('order') or {}
            cmd=dict(type='move',unit=u['id'],x=p['x'],y=p['y'],**meta)
            if any(order.get(k)!=v for k,v in cmd.items()):commands.append(cmd)
        for c,slot in sorted(slots,key=lambda pair:((pair[0]['id'],pair[1]) in self.assigned,pair[0]['id'],pair[1])):
            uid=self.assigned.get((c['id'],slot));g=garrisons[c['id']]
            if uid in self.missions:continue
            if c['id'] in blocked:continue
            if uid is None:
                if c['clan']//6!=obs['nation']:continue
                if clan_counts[c['clan']]>=obs['limits']['clan_party_cap']:continue
                if recruits[c['id']]>=self.floor:
                    count=min(27,recruits[c['id']]);recruits[c['id']]-=count;clan_counts[c['clan']]+=1
                    commands.append(dict(type='create',city=c['id'],count=count,source='recruits'));vacant[c['id']]-=1
                elif not g['battle'] and not g['army'] and distance(g,c)<=500 and g['healthy']>=self.floor:
                    count=min(27,g['healthy']);g['healthy']-=count;clan_counts[c['clan']]+=1
                    commands.append(dict(type='create',city=c['id'],count=count,source='garrison'));vacant[c['id']]-=1
                self.metrics['unfilled_party_slot_hours']+=6
                continue
            u=own[uid];target=self.targets[uid];floor=54 if (target>=57 if obs.get('direct_garrison_delivery') else target==57) else 18
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

