"""Three timed escorts grow into two P5 protectors plus one dedicated hunter per city."""
from scripts.transport_growth_policy import GrowthController, distance, travel_hours
from scripts.transport_triple_policy import Controller as LegacyController

class Controller(GrowthController):
    def __init__(self,target,floor,style):
        assert style in ('h0','h1','h2','h3','h4')
        super().__init__(target,floor,'grow57')
        self.hunt_style=style;self.hunter_slots={};self.hunter_ids=set();self.role_events=[]
        self.locks={};self.sightings={};self.previous_sightings={};self.visited={};self.hunt_routes={}

    def decide(self,obs):
        self.previous_sightings=dict(self.sightings)
        for b in obs['units']:
            if b['nation']==-1:self.sightings[b['id']]=dict(x=b['x'],y=b['y'],hour=obs['hour'])
        commands=super().decide(obs)
        self.hunter_ids={self.assigned[(cid,slot)] for cid,slot in self.hunter_slots.items() if (cid,slot) in self.assigned}
        self.metrics['hunter_role_hours']+=6*len(self.hunter_slots)
        self.metrics['hunter_filled_role_hours']+=6*len(self.hunter_ids)
        own={u['id']:u for u in obs['units'] if u['nation']==obs['nation']}
        self.metrics['hunter_battle_hours']+=6*sum(bool(own[uid]['battle']) for uid in self.hunter_ids if uid in own)
        self.locks={uid:bid for uid,bid in self.locks.items() if uid in own}
        return commands

    def escort_order(self,obs,u,c,v,own,bandits,ready,commands,move):
        cid=c['id']
        if cid not in self.hunter_slots:
            full=[(slot,uid) for (city,slot),uid in self.assigned.items() if city==cid and own[uid]['healthy']>=57]
            if full:
                slot,uid=min(full);self.hunter_slots[cid]=slot
                self.role_events.append(dict(hour=obs['hour'],city=cid,unit=uid,slot=slot))
        if cid not in self.hunter_slots:
            saved=self.style;self.style='timed'
            try:LegacyController.escort_order(self,obs,u,c,v,own,bandits,ready,commands,move)
            finally:self.style=saved
            return
        hunter=self.assigned.get((cid,self.hunter_slots[cid]))
        if u['id']==hunter:
            if self.hunt_style=='h0':move(u,c,hunter_rest=True);return
            if u['healthy']<54:move(u,c,hunter_rebuild=True);return
            self.hunt(obs,u,c,bandits,commands,move)
            return
        self.protect(obs,u,c,own,bandits,ready,commands,move)

    def protect(self,obs,u,c,own,bandits,ready,commands,move):
        # Exact previous two-P5 routing and target ownership, excluding dedicated hunters.
        defenders=[self.assigned[(c['id'],s)] for s in range(3) if s!=self.hunter_slots[c['id']] and (c['id'],s) in self.assigned]
        villages=sorted([v for v in obs['villages'] if v['city']==c['id']],key=lambda v:(v['x'],v['y'],v['id']))
        if len(defenders)==2:villages=villages[:2] if u['id']==defenders[0] else villages[2:]
        if not villages:return
        center=dict(x=sum(v['x'] for v in villages)//len(villages),y=sum(v['y'] for v in villages)//len(villages))
        peers=[p for p,city in ready if city['id'] in self.hunter_slots and p['id']!=self.assigned.get((city['id'],self.hunter_slots[city['id']]))]
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

    def hunt(self,obs,u,c,bandits,commands,move):
        uid=u['id'];bid=self.locks.get(uid);target=next((b for b in bandits if b['id']==bid),None)
        if self.hunt_style=='h3' and target and distance(target,c)>24000:target=None;self.locks.pop(uid,None)
        if target is None and bid in self.sightings:
            last=self.sightings[bid]
            if obs['hour']-last['hour']<=48 and distance(u,last)>1000 and (self.hunt_style!='h3' or distance(last,c)<=24000):
                move(u,last,hunter_search_last=bid);self.metrics['hunter_last_seen_hours']+=6;return
            self.locks.pop(uid,None)
        if target is None:
            choices=list(bandits)
            if self.hunt_style in ('h2','h4'):
                claimed={b for owner,b in self.locks.items() if owner!=uid}
                choices=[b for b in choices if b['id'] not in claimed and not b['battle']]
            elif self.hunt_style=='h3':
                cities=[x for x in obs['cities'] if x['nation']==obs['nation']]
                choices=[b for b in choices if not b['battle'] and min(cities,key=lambda x:(distance(x,b),x['id']))['id']==c['id']]
            choices.sort(key=lambda b:(distance(u,b),b['id']))
            if self.hunt_style in ('h2','h4'):
                estimates=[(travel_hours(obs['terrain'],u,b,obs['speeds'],max_hours=168),b) for b in choices[:5]]
                feasible=[(eta,b['id'],b) for eta,b in estimates if eta is not None]
                if feasible:target=min(feasible,key=lambda t:t[:2])[2]
            elif choices:target=choices[0]
            if target:self.locks[uid]=target['id'];self.metrics['hunter_new_targets']+=1
        if target:
            if self.hunt_style=='h4' and distance(u,target)>3500:
                prev=self.previous_sightings.get(target['id'])
                if prev and 0<obs['hour']-prev['hour']<=12:
                    dt=obs['hour']-prev['hour'];lead=min(12,max(3,distance(u,target)/500))
                    x=round(target['x']+(target['x']-prev['x'])/dt*lead);y=round(target['y']+(target['y']-prev['y'])/dt*lead)
                    if 0<=x<120000 and 0<=y<80000 and obs['terrain'][y//2000][x//2000]!=2:
                        move(u,dict(x=x,y=y),hunter_intercept=target['id']);self.metrics['hunter_intercept_hours']+=6;return
            commands.append(dict(type='attack',unit=uid,target=target['id']));self.metrics['hunter_attack_hours']+=6
            return
        self.metrics['hunter_search_hours']+=6
        if u.get('path') and (u.get('order') or {}).get('hunter_sweep'):return
        if c['id'] not in self.hunt_routes:
            points=[]
            for v in sorted([v for v in obs['villages'] if v['city']==c['id']],key=lambda v:v['id']):
                points += [dict(x=v['x']+dx,y=v['y']+dy) for dx,dy in ((6000,0),(0,6000),(-6000,0),(0,-6000))]
            self.hunt_routes[c['id']]=[p for p in points if 0<=p['x']<120000 and 0<=p['y']<80000 and obs['terrain'][p['y']//2000][p['x']//2000]!=2]
        points=self.hunt_routes[c['id']]
        if not points:move(u,c,hunter_sweep=True);return
        if self.hunt_style=='h3':
            for i,p in enumerate(points):
                if distance(u,p)<=1000:self.visited[(uid,i)]=obs['hour']
            i=min(range(len(points)),key=lambda i:(self.visited.get((uid,i),-1),distance(u,points[i]),i))
        else:i=(self.patrol_index.get(uid,-1)+1)%len(points);self.patrol_index[uid]=i
        move(u,points[i],hunter_sweep=True)
