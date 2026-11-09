"""Western Empire: concentrated, persistent campaigning on frozen realmap v0.6.0.

Only decide()'s observation and public navigation are used. No World or opponent
state. Policy does not mutate imported reference parameters. JSONL protocol v1.
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'training' / 'realmap-v0.7.0'))
from aiwar.vanilla_logistics import LogisticsPlanner
from aiwar.vanilla_policy import distance, size

VERSION = 'dev19-multinational-v070'
PARAMS = {'launch_min': 650, 'launch_margin': 2.0, 'attack_margin': 1.35,
          'ready_min': 25, 'refill_target': 150, 'campaign_food': 8,
          'merge_min': 160, 'muster_wait': 240, 'field_goal': 2400, 'main_goal': 2000}


class WesternPlanner(LogisticsPlanner):
    def __init__(self, obs):
        super().__init__(obs)
        self.claimed = {}
        # Frontier eligibility is current public information, even when cached ownership is stale.
        self.targets={c['id']:dict(c) for c in obs['cities'] if c['id'] in obs.get('frontier_targets',[])}
        self.main = max(self.armies.values(), key=lambda g:sum(u['healthy'] for u in g), default=[])
        self.main_ids = {u['id'] for u in self.main}
        self.recovery_anchor = None
        if self.main and sum(u['healthy'] for u in self.main)<650:
            prior=(self.main[0].get('order') or {}).get('west_recover')
            self.recovery_anchor=next((c for c in self.safe if c['id']==prior),None)
        self.enemy_groups = {}
        for u in self.hostiles:
            self.enemy_groups.setdefault(u['army'] or u['id'], []).append(u)

    def strength(self, u):
        if u.get('refill_target',150) != PARAMS['refill_target']:
            self.cmd.append(dict(type='set_strength',unit=u['id'],target=PARAMS['refill_target']))

    def needs_recovery(self, members):
        return sum(u['healthy'] for u in members)<650

    def logistics(self):
        super().logistics()
        # A logistics refill legitimately owns this decision, but must not erase
        # the shared recovery rendezvous while campaigns() skips a done army.
        for command in self.cmd:
            if command.get('type')!='move' or command.get('vanilla_task')!='refill_army':continue
            leader=self.units.get(command.get('unit'))
            if not leader or not leader.get('army'):continue
            members=self.armies.get(leader['army'],[])
            if not self.needs_recovery(members):continue
            prior=(leader.get('order') or {}).get('west_recover')
            city=next((c for c in self.safe if c['id']==prior),None)
            if not city:city=next((c for c in self.safe if distance(leader,c)<=500),None)
            if not city:continue
            command.update(west_task='recover',west_recover=city['id'],vanilla_base=city['id'])
            if self.main and leader['army']==self.main[0]['army']:
                self.recovery_anchor=city

    def refill_and_raise(self):
        # Replacements only; avoid converting every small reserve into a tiny party.
        for u in self.parties:
            if not u['battle']:
                self.strength(u)
                # set_composition immediately runs city service in this engine.
                # Only full healthy parties are safe before planned transfers/raises.
                if u.get('cavalry_target') != 150 and u['healthy']==150 and not u['wounded']:
                    city=next((c for c in self.safe if distance(u,c)<=500 and self.units[c['garrison']].get('cavalry',0)),None)
                    if city:
                        self.cmd.append(dict(type='set_composition',unit=u['id'],cavalry_target=150))
                        need=max(0,u.get('food_capacity',450000)-u['food'])
                        self.stock[city['id']]-=min(need,max(0,self.stock[city['id']]))
        caps=self.o['limits'].get('clan_party_caps',{})
        rebuilding=sum(u['healthy'] for u in self.parties)<PARAMS['field_goal']
        raise_threshold=50 if rebuilding else 80
        for clan, info in sorted(self.o.get('map_info',{}).get('clans',{}).items()):
            clan=int(clan)
            cap=caps.get(str(clan),info.get('party_slots',self.o['limits'].get('clan_party_cap',1)))
            if info['nation']!=self.n or sum(u['clan']==clan for u in self.parties)>=cap:continue
            candidates=[c for c in self.safe if self.garrison[c['id']]>=raise_threshold and self.stock[c['id']]>=500000]
            if not candidates:continue
            c=max(candidates,key=lambda c:(self.garrison[c['id']],-self.depth.get(c['id'],99),c['id']))
            count=min(150,max(30,self.garrison[c['id']]-25))
            self.cmd.append(dict(type='create',city=c['id'],clan=clan,count=count,source='garrison'))
            self.garrison[c['id']]-=count
            self.stock[c['id']]-=count*3000

    def enemy_strength(self, enemy):
        group=self.enemy_groups.get(enemy['army'] or enemy['id'],[enemy])
        return sum(e['healthy'] for e in self.hostiles if e in group or distance(e,enemy)<3500)

    def defence(self,c):
        g=c.get('healthy',50);m=c.get('militia_healthy',100)
        if c.get('stale'):
            age=max(0,self.hour-c.get('seen',self.hour))/24
            g=max(g,min(500,50+age*.8));m=max(m,min(200,100+age))
        # Conservative infantry-equivalent, with observed field reinforcements.
        field=sum(u['healthy'] for u in self.hostiles if distance(u,c)<12000)
        return max(100,2*g+m+field)

    def required(self,c):
        return max(220, math.ceil(PARAMS['attack_margin']*self.defence(c)))

    def base(self,u):
        options=sorted(self.safe,key=lambda c:(distance(u,c),c['id']))[:7]
        scored=[]
        for c in options:
            eta=self.eta(u,c)
            if not math.isfinite(eta):continue
            food=self.stock[c['id']]-self.claimed.get(c['id'],0)*3000
            troops=self.garrison[c['id']]-self.claimed.get(c['id'],0)
            score=(1+min(max(0,food)/300000,4)+min(max(0,troops)/50,4))/(1+eta/24)
            scored.append((score,c['id'],c))
        return max(scored,key=lambda a:a[:2])[2] if scored else None

    def target_for(self, group, force=False):
        leader=group[0];strength=sum(u['healthy'] for u in group)
        order=leader.get('order') or {}
        previous=self.targets.get(order.get('target') if order.get('type')=='siege' else order.get('west_target'))
        if previous and (force or strength>=self.required(previous)):
            return previous
        opts=[]
        for c in self.targets.values():
            eta=self.eta(leader,c)
            if not math.isfinite(eta):continue
            if not force and strength<self.required(c):continue
            # Capture nearby low-cost nodes first; count every castle toward 29/29.
            score=(1+.15*(c.get('settlement_type')=='town'))/(1+eta/24+self.required(c)/400)
            opts.append((score,c['id'],c))
        return max(opts,key=lambda a:a[:2])[2] if opts else None

    def army_refit(self,members,food_first=False):
        leader=members[0];healthy=sum(u['healthy'] for u in members)
        total=sum(size(u) for u in members)
        rate=max(1,total*self.o['limits']['field_ration'])
        regulars=[u for u in members if u.get('kind')!='levy']
        regular_capacity=len(regulars)*self.o['limits']['party_cap']
        deficit=max(0,min(PARAMS['main_goal'],regular_capacity)-sum(u['healthy'] for u in regulars))
        days=self.group_days(members)
        routes=[]
        for c in self.safe:
            eta=self.eta(leader,c)
            if math.isfinite(eta):routes.append((eta/24,c))
        if not routes:return
        # First preserve the army. A troop-rich base is not useful if its route
        # exhausts rations, or if it has no stock to fund the next departure.
        if days<24 or food_first:
            reachable=[(travel,c) for travel,c in routes if travel+1<days and self.stock[c['id']]>=rate*4]
            if reachable:
                travel,c=max(reachable,key=lambda x:((min(30,self.stock[x[1]['id']]/rate)-x[0])/(1+x[0]),x[1]['id']))
                self.move(leader,c,west_task='food_refit',vanilla_base=c['id'])
                return
            supply=self.support.get(leader['army'])
            if supply and supply['eta']/24+1<days:
                self.move(leader,leader,west_task='await_supply')
                return
        options=[]
        for travel,c in routes:
            if travel+2>=days:continue
            projected_total=total+min(deficit,self.garrison[c['id']])
            projected_rate=max(1,projected_total*self.o['limits']['field_ration'])
            if ((days-travel)*rate+self.stock[c['id']])/projected_rate<20:continue
            if days>24 and deficit>0 and self.garrison[c['id']]<10:continue
            reinforcement=min(deficit,self.garrison[c['id']])
            food=min(self.stock[c['id']]/max(1,total*2000),2)
            score=(1+reinforcement/45+food*.2)/(1+travel/2)
            options.append((score,c['id'],c))
        if options:
            c=max(options,key=lambda a:a[:2])[2]
        else:
            # If no base meets the desired reserve, take the earliest actual
            # food, not a distant warehouse with a tempting absolute stock.
            stocked=[(travel,c) for travel,c in routes if self.stock[c['id']]>rate]
            if stocked:c=min(stocked,key=lambda x:(x[0],-self.stock[x[1]['id']],x[1]['id']))[1]
            else:c=min(routes,key=lambda x:(x[0],x[1]['id']))[1]
        self.move(leader,c,west_task='army_refit',vanilla_base=c['id'])

    def consolidate(self,members,city):
        """Refit full parties and free clan slots for rear recruitment, legally."""
        if len(members)<3:return False
        leader=members[0]
        receivers=sorted(members,key=lambda u:(u['id']!=leader['id'],-u['healthy'],u['id']))
        donors=list(reversed(receivers))
        count={u['id']:u['healthy'] for u in members}
        moved=False
        for receiver in receivers:
            if count[receiver['id']]<=0:continue
            room=150-count[receiver['id']]-receiver['wounded']
            for donor in donors:
                if room<=0:break
                if donor['id']==receiver['id']:break
                if donor['id']==leader['id'] or count[donor['id']]<=0:continue
                amount=min(room,count[donor['id']])
                self.cmd.append(dict(type='transfer',unit=donor['id'],target=receiver['id'],count=amount))
                count[receiver['id']]+=amount;count[donor['id']]-=amount;room-=amount;moved=True
        if moved:self.move(leader,city,west_task='consolidate',vanilla_base=city['id'])
        return moved

    def recover_campaign(self,members):
        """Rally damaged armies and real reinforcements at one friendly city."""
        leader=members[0];healthy=sum(u['healthy'] for u in members)
        if healthy>=650:return False
        extras=[u for u in self.parties if not u['army'] and not u['battle'] and u['id'] not in self.done]
        # A full four-party force can finish a genuinely weak, observed target
        # when there is no available replacement. Never send a 250-man remnant
        # scouting merely because its tiny current roster is almost full.
        target=self.target_for(members)
        capacity=len(members)*self.o['limits']['party_cap']
        days=self.group_days(members)
        if (not extras and healthy>=500 and healthy>=capacity*.95 and target
                and not target.get('stale') and days>=self.eta(leader,target)/24+12):
            return False
        rate=max(1,sum(size(u) for u in members)*self.o['limits']['field_ration'])
        prior=(leader.get('order') or {}).get('west_recover')
        city=next((c for c in self.safe if c['id']==prior),None)
        if city and self.stock[city['id']]<rate*4 and days<24:city=None
        if not city:
            options=[]
            for c in self.safe:
                travel=self.eta(leader,c)/24
                if not math.isfinite(travel):continue
                if travel+2>=days:continue
                enemy=sum(u['healthy'] for u in self.hostiles if distance(u,c)<10000)
                food=self.stock[c['id']]/rate
                options.append(((food>=8,enemy<healthy, self.depth.get(c['id'],1)>0,-travel,c['id']),c))
            if not options:
                self.army_refit(members)
                return True
            city=max(options,key=lambda x:x[0])[1]
        if self.main and leader['army']==self.main[0]['army']:
            self.recovery_anchor=city
        metadata=dict(west_task='recover',west_recover=city['id'],vanilla_base=city['id'])
        if distance(leader,city)<=500:
            if self.consolidate(members,city):
                if self.cmd[-1].get('type')=='move' and self.cmd[-1].get('unit')==leader['id']:
                    self.cmd[-1].update(metadata)
                else:
                    self.cmd.append(dict(type='move',unit=leader['id'],x=city['x'],y=city['y'],**metadata))
                return True
            local=[u for u in extras if distance(u,leader)<=500]
            if local:
                self.cmd.append(dict(type='disband',unit=leader['id']))
                self.cmd.append(dict(type='assemble',unit=leader['id'],units=[u['id'] for u in members[1:]+local]))
                self.done.update(u['id'] for u in local)
                # Disband clears the old order; do not deduplicate against
                # that pre-command observation when restoring recovery intent.
                self.cmd.append(dict(type='move',unit=leader['id'],x=city['x'],y=city['y'],**metadata))
                return True
        self.move(leader,city,**metadata)
        return True

    def campaign_budget(self,members,target,battle_days):
        """Food for outward travel, combat, and reaching real friendly stocks."""
        leader=members[0]
        outbound=self.eta(leader,target)/24
        if not math.isfinite(outbound):return math.inf
        # Reserve for one additional relief wave during a siege. Combat has
        # no hard duration cutoff, so this is a margin, not a worst-case bound.
        battle_reserve=battle_days+(8 if battle_days==10 else 0)
        rate=max(1,sum(size(u) for u in members)*self.o['limits']['field_ration'])
        stocked=[c for c in self.safe if self.stock[c['id']]>=rate*4 and not self.units[c['garrison']].get('battle')]
        stocked=sorted(stocked,key=lambda c:(distance(target,c),c['id']))[:7]
        at=dict(leader,x=target['x'],y=target['y'])
        returning=min((self.eta(at,c)/24 for c in stocked),default=math.inf)
        return outbound+battle_reserve+returning+3

    def campaigns(self):
        for members in sorted(self.armies.values(),key=lambda g:-sum(u['healthy'] for u in g)):
            if any(u['id'] in self.done for u in members):continue
            self.done.update(u['id'] for u in members)
            if any(u['battle'] for u in members):continue
            leader=members[0];healthy=sum(u['healthy'] for u in members);wounded=sum(u['wounded'] for u in members)
            target=self.target_for(members)
            days=self.group_days(members)
            if self.recover_campaign(members):continue
            if days<24:
                self.army_refit(members)
                continue
            # Defeat nearby operational formations before they retake the supply corridor.
            prey=[]
            for enemy in self.hostiles:
                total=self.enemy_strength(enemy)
                if total<90 or healthy<total*1.65 or distance(leader,enemy)>24000:continue
                if any((c['nation']!=self.n or c['id'] in self.targets) and distance(enemy,c)<=1000 for c in self.o['cities']):continue
                eta=self.eta(leader,enemy)
                if eta>40 or days<eta/24+10:continue
                if enemy['battle'] and not any(b['id']==enemy['battle'] and b.get('city') for b in self.o['battles']):continue
                prey.append((not bool(enemy['battle']),eta,-total,enemy['id'],enemy))
            if prey:
                enemy=min(prey,key=lambda p:p[:4])[-1]
                if days<self.campaign_budget(members,enemy,8):
                    self.army_refit(members,food_first=True)
                    continue
                order=leader.get('order') or {}
                if order.get('type')!='attack' or order.get('target')!=enemy['id']:
                    self.cmd.append(dict(type='attack',unit=leader['id'],target=enemy['id'],west_task='intercept'))
                continue
            local=next((c for c in self.safe if distance(c,leader)<=500),None)
            if local:
                if self.consolidate(members,local):continue
                extras=[u for u in self.parties if not u['army'] and not u['battle'] and u['id'] not in self.done and distance(u,leader)<=500]
                if sum(u['healthy'] for u in extras)>=PARAMS['merge_min'] or (healthy<PARAMS['main_goal'] and extras):
                    self.cmd.append(dict(type='disband',unit=leader['id']))
                    self.cmd.append(dict(type='assemble',unit=leader['id'],units=[u['id'] for u in members[1:]+extras],campaign_target=target['id'] if target else ''))
                    self.done.update(u['id'] for u in extras)
                    self.move(leader,local,west_task='fill_merged',vanilla_base=local['id'])
                    continue
                rate=sum(size(u) for u in members)*100
                # One city-service tick after a capture unloads wounded and draws food.
                if (wounded>healthy*.12 or days<min(30,3+(self.eta(leader,target)/24 if target else 0)+8)) and self.stock[local['id']]>rate*3:
                    self.move(leader,local,west_task='fill_army',vanilla_base=local['id'])
                    continue
            # An unseen city's age is not proof that its garrison has grown.
            # Reconnoitre with the intact army; never issue a siege before the
            # normal observed-strength test passes. Previously a conservative
            # stale estimate could prevent obtaining the information to attack.
            if not target and healthy>=650:
                scouts=[];food_blocked=False
                for c in self.targets.values():
                    if not c.get('stale'):continue
                    last_known=2*c.get('healthy',50)+c.get('militia_healthy',100)
                    if healthy<last_known*1.35:continue
                    eta=self.eta(leader,c)
                    if not math.isfinite(eta):continue
                    if days<self.campaign_budget(members,c,0):
                        food_blocked=True
                        continue
                    scouts.append((eta,c['id'],c))
                if scouts:
                    c=min(scouts,key=lambda x:x[:2])[2]
                    self.move(leader,c,west_task='scout',west_target=c['id'])
                    continue
                if food_blocked:
                    self.army_refit(members,food_first=True)
                    continue
            minimum=min(650, math.floor(len(members)*150*.8))
            if not target or healthy<max(minimum, min(1200, math.floor(len(members)*150*.9), self.required(target)*1.25)) or wounded>healthy*.65:
                self.army_refit(members);continue
            travel=self.eta(leader,target)/24
            if days<self.campaign_budget(members,target,10):
                supply=self.support.get(leader['army'])
                if supply and supply['eta']/24+2<days:
                    self.move(leader,leader,west_task='await_supply');continue
                if self.raid_for_food(members):continue
                self.army_refit(members,food_first=True);continue
            order=leader.get('order') or {}
            # Approach unknown garrisons through legal public coordinates, then reassess.
            if target.get('stale'):
                self.move(leader,target,west_task='approach',west_target=target['id'])
            elif order.get('type')!='siege' or order.get('target')!=target['id']:
                self.cmd.append(dict(type='siege',unit=leader['id'],target=target['id'],west_task='conquer'))

    def rally(self):
        available=[u for u in self.parties if not u['army'] and not u['battle'] and u['id'] not in self.done]
        if not available:return
        # Reinforce the persistent army rather than launch undersized parallel attacks.
        if self.main:
            anchor=self.recovery_anchor or self.main[0]
            if anchor.get('battle'):
                # Do not feed a hopeless battle; join only when visible total is favourable.
                strength=sum(u['healthy'] for u in self.main)
                enemy=sum(u['healthy'] for u in self.hostiles if u['battle']==anchor['battle'])
                if strength<enemy*.8:
                    anchor=min(self.safe,key=lambda c:distance(c,anchor)) if self.safe else anchor
            base=None
        else:
            # Initial objective minimizes actual route distance from ready units and base.
            opts=[]
            for target in self.targets.values():
                for c in self.safe:
                    if target['id'] not in c['neighbors']:continue
                    journey=self.length(c,target)/500/24
                    gathering=sum(min(20,self.eta(u,c)/24) for u in available)/len(available)
                    opts.append((journey+gathering*.45+self.required(target)/500,c['id'],target['id'],c,target))
            if not opts:return
            _,_,_,base,target=min(opts,key=lambda a:a[:3]);anchor=base
            # Persist a muster point, unless captured. Avoid oscillating as units travel.
            existing=next((u.get('order') or {} for u in available if (u.get('order') or {}).get('west_task')=='rally'),{})
            if existing.get('vanilla_base') in self.bycity and existing.get('west_target') in self.targets:
                base=self.bycity[existing['vanilla_base']];anchor=base;target=self.targets[existing['west_target']]
            arrived=[u for u in available if distance(u,base)<=250 and u['healthy']>=PARAMS['ready_min'] and self.days(u)>=14]
            total=sum(u['healthy'] for u in arrived)
            expected=sum(u['healthy'] for u in available if self.eta(u,base)<=240)
            # Formation is not an attack. Stale estimated defenses must not
            # prevent assembling a replacement army capable of reconnaissance.
            need=PARAMS['launch_min']
            if len(arrived)>=2 and total>=need and total>=expected*.65:
                self.cmd.append(dict(type='assemble',unit=arrived[0]['id'],units=[u['id'] for u in arrived[1:]],campaign_target=target['id']))
                self.move(arrived[0],base,west_task='new_army',vanilla_base=base['id'])
                self.done.update(u['id'] for u in arrived)
        for u in available:
            if u['id'] in self.done:continue
            self.done.add(u['id'])
            eta=self.eta(u,anchor)
            home=self.base(u)
            if not home:continue
            if u['healthy']<PARAMS['ready_min'] or u['wounded']>size(u)*.35 or self.days(u)<eta/24+5:
                self.claimed[home['id']]=self.claimed.get(home['id'],0)+max(0,150-u['healthy'])
                self.move(u,home,west_task='refit',vanilla_base=home['id']);continue
            # Supply donor visits before a very long trek, without stalling already strong parties.
            if u['healthy']<60 and self.garrison[home['id']]>60 and self.eta(u,home)<36 and distance(u,anchor)>12000:
                self.claimed[home['id']]=self.claimed.get(home['id'],0)+90
                self.move(u,home,west_task='refit',vanilla_base=home['id']);continue
            meta=dict(west_task='follow') if self.main else dict(west_task='rally',west_target=target['id'],vanilla_base=base['id'])
            self.move(u,anchor,**meta)

    def run(self):
        if not self.cities:return []
        self.logistics()
        self.refill_and_raise()
        # Default relief can split/retask armies; use only immediate superior interception.
        self.campaigns()
        self.rally()
        commands=bounded_commands(self.cmd)
        # A garrison may join a nearby field battle even when its city is not
        # besieged. Recruitment and dispatch from that donor are then rejected
        # before any resource mutation. Filter those no-ops only AFTER budgeting
        # and truncation, preserving all other orders and their original order.
        result=[]
        for command in commands:
            if command['type'] in ('create','dispatch'):
                city=self.bycity.get(command.get('city'))
                source=command.get('source','garrison')
                donor=self.units.get(city['garrison'] if city and (command['type']=='dispatch' or source=='garrison') else source)
                if donor and donor.get('battle'):continue
            result.append(command)
        return result


def bounded_commands(commands, cap=100):
    """Keep disband/reassemble/move transactions intact at protocol limits."""
    groups=[];i=0
    while i<len(commands):
        group=[commands[i]];i+=1
        if group[0]['type']=='disband':
            while i<len(commands) and commands[i].get('unit')==group[0].get('unit') and commands[i]['type'] in ('assemble','move'):
                group.append(commands[i]);i+=1
        groups.append(group)
    # Earlier orders reserve real troops and food. Reordering a later move can
    # trigger city service and consume those reservations. Keep an exact prefix
    # of whole transactions; deferred orders will be replanned next decision.
    result=[]
    for group in groups:
        if len(result)+len(group)>cap:break
        result.extend(group)
    return result

