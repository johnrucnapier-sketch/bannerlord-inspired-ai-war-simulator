"""D2 military-only revision; inherits D1 economy methods unchanged."""
import math
from scripts.escort_p5_defense_policy import Controller as D1
from scripts.transport_growth_policy import distance
from aiwar.relief import staging_point

class Task(D1):
    def __init__(self,parent,kind,city,serial):
        super().__init__()
        self.allowed_kind=kind;self.defense_city=city;self.serial=serial;self.reserved=set()
        for name in ('assigned','targets','switched','returning','away','war_events'):
            setattr(self,name,getattr(parent,name))
    def military(self,obs):
        """Only filtered observations. Mutate a private observation to reserve logistics."""
        n=obs['nation'];hour=obs['hour'];commands=[]
        cities={c['id']:c for c in obs['cities'] if c['nation']==n and 'recruits' in c}
        own={u['id']:u for u in obs['units'] if u['nation']==n}
        parties={uid:u for uid,u in own.items() if u['kind']=='party' and uid not in self.reserved}
        blocked={a['city'] for a in obs.get('relief_requests',[])}
        enemies=[u for u in obs['units'] if u['nation']>=0 and u['nation']!=n and u['kind']=='party']
        alerts={a['city']:a for a in obs.get('relief_requests',[])}
        threats=[]
        for c in cities.values():
            near=[u for u in enemies if (u['army'] and distance(u,c)<=24000) or distance(u,c)<=10000 or (c['id'] in alerts and u['battle'] in (alerts[c['id']]['battle'],alerts[c['id']].get('relief_battle')))]
            if near:threats.append((c,near))
        if self.allowed_kind=='attack':threats=[]
        else:threats=[(c,es) for c,es in threats if c['id']==self.defense_city]
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
            if threats:p['last_seen']=hour
            target=next((c for c in obs['cities'] if c['id']==p['target']),None)
            in_battle=any(u['battle'] for u in active)
            ended=(p['kind']=='defense' and (p['target'] not in cities or hour-p.get('last_seen',p['start'])>=168)) or (p['kind']=='attack' and target and target['nation']==n and not target.get('stale'))
            low_food=any(u['food']/max(1,(u['healthy']+u['wounded'])*obs['limits']['field_ration'])<5 and self.missions[u['id']]['phase']=='field' for u in active)
            exhausted=bool(active) and all(self.missions[u['id']]['phase']=='field' for u in active) and sum(u['healthy'] for u in active)<p['required']*.6
            if not in_battle and (not active or ended or low_food or exhausted or hour-p['start']>1344):
                reason='no_force' if not active else 'target_complete_or_threat_clear_168h' if ended else 'low_food' if low_food else 'strength_depleted' if exhausted else 'tour_timeout'
                stop_campaign(reason)
        # Orphaned parties from captured cities return and remain eligible for later assignment.
        for uid,m in list(self.missions.items()):
            if m['home'] not in cities:
                if cities:m['home']=min(cities.values(),key=lambda c:distance(parties[uid],c))['id']
                m['phase']='return'
        assigned_ids=set(self.assigned.values())
        valid_homes=set(cities)
        for uid,u in parties.items():
            orphan=(bool(self.assigned) and uid not in assigned_ids) or any(v==uid and cid not in valid_homes for (cid,slot),v in self.assigned.items())
            if self.allowed_kind=='attack' and orphan and uid not in self.missions and cities:
                home=min(cities.values(),key=lambda c:distance(u,c))
                if distance(u,home)>500 or u['army']:self.missions[uid]=dict(home=home['id'],phase='return')
        if not self.campaign and not self.missions and cities and hour>=self.cooldown and (threats or self.allowed_kind=='attack'):
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
                    self.campaign=dict(kind=kind,target=target['id'],stage=dict(x=stage['x'],y=stage['y']),required=required,start=hour,last_seen=hour)
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
                    elif not es:move(leader,p['stage'],campaign_phase='d2_hold')
        return commands


class Controller(D1):
    def __init__(self):
        super().__init__();self.tasks=[];self.task_serial=0;self.task_cooldowns={}
    def decide(self,obs):
        commands=super().decide(obs)
        # A party with no healthy soldiers would be deleted by transferring its
        # last wounded soldier. Let normal city service handle it next hour.
        zero={u['id'] for u in obs['units'] if u['nation']==obs['nation'] and u['kind']=='party' and u['healthy']==0 and any(c['nation']==obs['nation'] and 'recruits' in c and distance(u,c)<=500 for c in obs['cities'])}
        commands=[cmd for cmd in commands if not (cmd['type'] in ('transfer','recruit') and (cmd.get('unit') in zero or cmd.get('target') in zero))]
        if not getattr(self,'issued_military_commands',False):return commands
        # Movement automatically services troops at a city. Execute all explicitly
        # reserved troop allocations first so automatic service cannot steal them.
        resources={'transfer','recruit','create','set_strength'}
        return [c for c in commands if c['type'] in resources]+[c for c in commands if c['type'] not in resources]
    def military(self,obs):
        commands=[];remaining=[]
        def execute(task):
            # Refresh references: the unchanged economic controller replaces assigned each turn.
            for name in ('assigned','targets','switched','returning','away','war_events'):
                setattr(task,name,getattr(self,name))
            task.reserved={uid for other in self.tasks if other is not task for uid in other.missions}
            before=len(self.war_events);cmds=task.military(obs)
            for event in self.war_events[before:]:event['task']=task.serial
            commands.extend(cmds)
        for task in list(self.tasks):
            execute(task)
            if task.campaign or task.missions:remaining.append(task)
            else:self.task_cooldowns[(task.allowed_kind,task.defense_city)]=obs['hour']+48
        self.tasks=remaining
        n=obs['nation'];cities=[c for c in obs['cities'] if c['nation']==n and 'recruits' in c]
        alerts={a['city'] for a in obs.get('relief_requests',[])}
        enemies=[u for u in obs['units'] if u['nation']>=0 and u['nation']!=n and u['kind']=='party']
        threatened=[c for c in cities if c['id'] in alerts or any((u['army'] and distance(u,c)<=24000) or distance(u,c)<=10000 for u in enemies)]
        threatened.sort(key=lambda c:(c['id'] not in alerts,c['id']))
        plans=[('defense',c['id']) for c in threatened]+[('attack',None)]
        for kind,city in plans:
            if any(t.allowed_kind==kind and (kind=='attack' or t.defense_city==city) for t in self.tasks):continue
            if kind=='defense' and sum(t.allowed_kind=='defense' for t in self.tasks)>=2:continue
            if obs['hour']<self.task_cooldowns.get((kind,city),0):continue
            self.task_serial+=1;task=Task(self,kind,city,self.task_serial);self.tasks.append(task);execute(task)
            if not task.campaign and not task.missions:self.tasks.remove(task)
        self.missions={uid:m for task in self.tasks for uid,m in task.missions.items()}
        self.issued_military_commands=bool(commands)
        assert len(self.missions)==sum(len(t.missions) for t in self.tasks)
        return commands
