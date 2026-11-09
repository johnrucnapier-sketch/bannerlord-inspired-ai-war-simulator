"""Conservative clan-army baseline, not an exact reconstruction of any Mod AI.

Reuse vanilla_v1 readiness and logistics. Campaign rosters are plans, not armies:
only co-located members of the same clan assemble. Different formations travel
and fight independently. Offensive commitment counts only physically arrived,
visible friendly troops, never a remote roster's promised strength.
"""
import math
from .navigation import find_route, relief_terrain
from .vanilla_policy import Planner, PARAMETERS, distance
from .vanilla_logistics import LogisticsPlanner
from .organization_policy import attached_members, combat_strength, augment_commands


class ClanCoordination:
    def __init__(self,obs):
        super().__init__(obs)
        self.hostiles.extend(u for u in obs['units'] if u['kind']=='levy'
                             and u['nation']>=0 and u['nation']!=self.n)
        for aid,members in list(self.armies.items()):
            commander=obs.get('army_metadata',{}).get(aid,{}).get('commander')
            members.sort(key=lambda u:(u['id']!=commander,u['id']))
            self.armies[aid]=attached_members(obs,members)

    def defence(self,city):
        g=city.get('healthy',50);m=city.get('militia_healthy',100)
        if city.get('stale'):g=max(g,50);m=max(m,100)
        field=combat_strength([u for u in self.hostiles if distance(u,city)<8000])
        return max(40,2*g+m+field)

    def release(self,members):
        if members[0]['army']:self.cmd.append(dict(type='disband',unit=members[0]['id']))
        for u in members:
            if u['kind']=='party':self.refit(u)
            else:self.done.add(u['id'])

    def run(self):
        return augment_commands(self.o,super().run())

    def stage(self, base, target):
        path=find_route(self.o['terrain'],base,target['x'],target['y'])
        if path is None:return None
        points=[(base['x'],base['y'])]+list(path)
        # Stop outside automatic contact range, along the actual navigable route.
        remaining=2000.
        for a,b in reversed(list(zip(points,points[1:]))):
            length=math.dist(a,b)
            if length>=remaining:
                ratio=remaining/max(1,length)
                return dict(x=round(b[0]+(a[0]-b[0])*ratio),y=round(b[1]+(a[1]-b[1])*ratio))
            remaining-=length
        return dict(x=base['x'],y=base['y'])

    def musters(self):
        # Reserve existing and newly planned armies across every muster in this
        # decision. Other parties keep their own physical orders and identities.
        army_clans={u['clan'] for u in self.parties if u['army']}
        plans={}
        for u in self.parties:
            order=u.get('order') or {}
            if not u['army'] and order.get('vanilla_task')=='muster':
                plans.setdefault((order['vanilla_target'],order['vanilla_started']),[]).append(u)
        for (tid,start),members in sorted(plans.items()):
            usable=[u for u in members if u['id'] not in self.done and not u['battle']]
            if not usable:continue
            self.done.update(u['id'] for u in usable)
            plan=usable[0]['order'];base=self.bycity.get(plan['vanilla_base']);target=self.targets.get(tid)
            if not base or base['id'] in self.sieged or not target or self.hour-start>PARAMETERS['muster_timeout']:
                for u in usable:self.refit(u)
                continue
            arrived=[u for u in usable if distance(u,base)<=100 and self.days(u)>12]
            stage=self.stage(base,target)
            if stage and len(arrived)>=2 and sum(u['healthy'] for u in arrived)>=self.required(target):
                clans={}
                for u in arrived:clans.setdefault(u['clan'],[]).append(u)
                for clan,group in sorted(clans.items()):
                    leader=group[0]
                    if len(group)>1 and clan not in army_clans:
                        self.cmd.append(dict(type='assemble',unit=leader['id'],units=[u['id'] for u in group[1:]],campaign_target=tid))
                        army_clans.add(clan)
                        leaders=[leader]
                    else:
                        # Do not create a second army or remotely merge with the
                        # existing one. Leftovers coordinate as individual parties.
                        leaders=group
                    for leader in leaders:
                        self.move(leader,stage,vanilla_task='clan_campaign',vanilla_target=tid,
                                  vanilla_started=self.hour,vanilla_base=base['id'])
                for u in usable:
                    if u not in arrived:self.refit(u)
            else:
                for u in usable:
                    if self.days(u)<self.eta(u,base)/24+3:self.refit(u);continue
                    self.move(u,base,vanilla_task='muster',vanilla_target=tid,vanilla_started=start,
                              vanilla_base=base['id'],vanilla_expected=plan['vanilla_expected'],vanilla_wait_since=plan.get('vanilla_wait_since',-1))

    def campaigns(self):
        groups=list(self.armies.values())+[[u] for u in self.parties if not u['army'] and (u.get('order') or {}).get('vanilla_task')=='clan_campaign']
        plans={}
        for members in groups:
            if any(u['id'] in self.done for u in members):continue
            self.done.update(u['id'] for u in members)
            if any(u['battle'] for u in members):continue
            leader=members[0];order=leader.get('order') or {}
            tid=order.get('vanilla_target') or leader.get('army_target');target=self.targets.get(tid)
            start=order.get('vanilla_started',leader.get('army_formed',self.hour))
            base=self.bycity.get(order.get('vanilla_base'))
            if not base:base=self.base(leader)
            if not target or not base or self.hour-start>PARAMETERS['campaign_hours']:
                self.release(members);continue
            days=self.group_days(members) if hasattr(self,'group_days') else min(self.days(u) for u in members)
            if days<max(6,self.eta(leader,target)/24+6):
                supply=getattr(self,'support',{}).get(leader.get('army'))
                rate=sum(u['healthy']+u['wounded'] for u in members)*self.o['limits']['field_ration']
                if supply and supply['eta']/24+2<days and supply['food']>rate*3:
                    self.move(leader,leader,vanilla_task='await_supply',vanilla_target=tid,
                              vanilla_started=start,vanilla_base=base['id'])
                    continue
                if hasattr(self,'raid_for_food') and self.raid_for_food(members):continue
                self.release(members);continue
            stage=self.stage(base,target)
            if stage is None:self.release(members);continue
            plans.setdefault(tid,[]).append((members,stage,base,start))
        for tid,formations in sorted(plans.items()):
            target=self.targets[tid]
            # Only nearby formations can contribute to this decision. Orders and
            # distant groups are not counted as present military strength.
            arrived=[f for f in formations if all(distance(u,f[1])<=100 or distance(u,target)<=2100 for u in f[0])]
            for members,stage,base,start in formations:
                leader=members[0];order=leader.get('order') or {}
                local=[f for f in arrived if all(distance(u,leader)<=500 for u in f[0])]
                strength=sum(combat_strength(f[0]) for f in local)
                commit=not target.get('stale') and strength>=self.required(target)
                meta=dict(vanilla_task='clan_campaign',vanilla_target=tid,vanilla_started=start,vanilla_base=base['id'])
                if commit and any(f[0] is members for f in arrived):
                    if order.get('type')!='siege' or order.get('target')!=tid:
                        self.cmd.append(dict(type='siege',unit=leader['id'],target=tid,**meta))
                else:self.move(leader,stage,**meta)

    def relief(self):
        groups=list(self.armies.values())+[[u] for u in self.parties if not u['army']]
        for alert in sorted(self.o.get('relief_requests',[]),key=lambda a:(a['assault_at'],a['city'])):
            enemy=[u for u in self.hostiles if u['battle'] and u['battle'] in (alert['battle'],alert.get('relief_battle'))]
            if not enemy:continue
            stage=None
            for c in sorted(self.safe,key=lambda c:(distance(c,alert),c['id']))[:3]:
                for x,y in reversed(find_route(self.o['terrain'],c,alert['x'],alert['y']) or []):
                    p=dict(x=x,y=y)
                    if distance(p,alert)>3500 and find_route(relief_terrain(self.o['terrain'],alert,c),c,x,y) is not None:
                        stage=p;break
                if stage:break
            if stage is None:continue
            choices=[]
            for group in groups:
                if any(u['battle'] or u['id'] in self.done for u in group):continue
                eta=self.eta(group[0],stage)
                if eta<=120 and min(self.days(u) for u in group)>eta/24+4:choices.append((eta,group[0]['id'],group))
            chosen=[];expected=0;need=math.ceil(combat_strength(enemy)*1.15)
            for _,_,group in sorted(choices):
                chosen.append(group);expected+=combat_strength(group)
                if expected>=need:break
            if expected<need:continue
            for group in chosen:
                self.done.update(u['id'] for u in group)
                if not all(distance(u,stage)<=100 for u in group):
                    self.move(group[0],stage,vanilla_task='relief',relief_action='wait',relief_city=alert['city'])
            arrived=[g for g in chosen if all(distance(u,stage)<=100 for u in g)]
            if sum(combat_strength(g) for g in arrived)<need:continue
            # Each clan formation receives its own attack. No disband/merge step.
            for group in arrived:
                leader=group[0];target=min(enemy,key=lambda e:(distance(leader,e),e['id']))
                if (leader.get('order') or {}).get('target')!=target['id']:
                    self.cmd.append(dict(type='attack',unit=leader['id'],target=target['id'],vanilla_task='relief'))


class ClanPlanner(ClanCoordination,Planner):pass
class ClanLogisticsPlanner(ClanCoordination,LogisticsPlanner):pass


def decide(obs):
    planner=ClanLogisticsPlanner if obs.get('logistics_limits',{}).get('rations_separate') else ClanPlanner
    return planner(obs).run()
