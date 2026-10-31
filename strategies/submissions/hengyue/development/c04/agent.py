#!/usr/bin/env python3
"""HengYue V1: observation-only campaign and resource allocator. MIT.
No simulator imports, filesystem reads, network, seeds or opponent identity.
"""
import heapq
import json
import math
import sys


def dist(a, b):
    return math.hypot(a['x']-b['x'], a['y']-b['y'])


def size(u):
    return u.get('healthy', 0)+u.get('wounded', 0)


def days(u):
    return u.get('food', 0)/max(1, size(u)*100)


class Policy:
    def __init__(self):
        self.guard = {}
        self.pending = {}
        self.cache = {}
        self.seen = {}
        self.task = None
        self.cohort = []
        self.cool = {}
        self.rest = {}
        self.previous_battle = set()
        self.initialized = False

    def route(self, a, b):
        s=(int(a['x'])//2000,int(a['y'])//2000)
        t=(int(b['x'])//2000,int(b['y'])//2000)
        key=(s,t)
        if key not in self.cache:
            q=[(0,s)]; cost={s:0}; parent={}
            while q:
                v,p=heapq.heappop(q)
                if v!=cost[p]: continue
                if p==t: break
                for dx,dy in ((0,1),(0,-1),(1,0),(-1,0)):
                    z=(p[0]+dx,p[1]+dy)
                    if not (0<=z[0]<60 and 0<=z[1]<40): continue
                    kind=self.terrain[z[1]][z[0]]
                    if kind==2: continue
                    nv=v+(4 if kind==1 else 3)
                    if nv<cost.get(z,10**9):
                        cost[z]=nv; parent[z]=p; heapq.heappush(q,(nv,z))
            if t not in cost:
                self.cache[key]=None
            else:
                z=t; cells=[]
                while z!=s:
                    cells.append({'x':z[0]*2000+1000,'y':z[1]*2000+1000});z=parent[z]
                self.cache[key]=list(reversed(cells))
        route=self.cache[key]
        return None if route is None else route+[{'x':b['x'],'y':b['y']}]

    def eta(self,a,b):
        route=self.route(a,b)
        if route is None: return 10**6
        pts=[a]+route
        return sum(dist(x,y) for x,y in zip(pts,pts[1:]))/375+2

    def point(self,a,b,r):
        route=self.route(a,b)
        if not route: return {'x':a['x'],'y':a['y']}
        previous=None
        for p in route:
            if dist(p,a)>r:
                if previous is not None:return previous
                # No grid waypoint fits: stay on the first reachable segment,
                # inside the requested radius. An unreachable route stays at a.
                fraction=max(0,min(1,r*.95/max(1,dist(p,a))))
                return {'x':round(a['x']+(p['x']-a['x'])*fraction),
                        'y':round(a['y']+(p['y']-a['y'])*fraction)}
            previous=p
        return previous or {'x':a['x'],'y':a['y']}

    def emit(self,cmd,role=None):
        if len(self.commands)>=96: return
        if role is not None: self.pending[len(self.commands)]=role
        self.commands.append(cmd)

    def order(self,u,kind,target=None,point=None,relief=None):
        if u.get('battle') or u['id'] in self.used: return
        old=u.get('order') or {}
        cmd={'type':kind,'unit':u['id']}
        if point is not None:
            cmd.update(x=int(point['x']),y=int(point['y']))
            if relief: cmd.update(relief_action='wait',relief_city=relief)
            if dist(u,point)<100 and not u.get('path'):
                self.used.add(u['id']);return
            same=old.get('type')==kind and abs(old.get('x',-999999)-point['x'])<60 and abs(old.get('y',-999999)-point['y'])<60 and old.get('relief_city')==relief
        else:
            if target is not None: cmd['target']=target['id']
            same=old.get('type')==kind and old.get('target')==cmd.get('target')
        if not same: self.emit(cmd)
        self.used.add(u['id'])

    def home(self,u,refill=False):
        # Hard feasibility: a close empty city is never a food depot.
        choices=[]
        for c in self.owned:
            if c['id'] in self.besieged: continue
            eta=self.eta(u,c)
            if eta>max(24,days(u)*24-12) and days(u)>0: continue
            resident=size(self.units.get(c['garrison'],{}))+size(self.units.get(c.get('militia'),{}))
            available=c['food']-self.food_book.get(c['id'],0)-resident*50*4
            if available<max(4000,size(u)*100*8): continue
            g=self.units.get(c['garrison'],{})
            score=eta-(min(g.get('healthy',0),max(0,150-size(u)))*.18 if refill else 0)
            choices.append((score,c))
        if not choices:
            # Emergency: maximize reachable sustenance; never intentionally wait at zero.
            for c in self.owned:
                if c['id'] not in self.besieged and c['food']>max(1000,size(u)*100):
                    choices.append((self.eta(u,c)+100,c))
        return min(choices,key=lambda x:(x[0],x[1]['id']))[1] if choices else None

    def send_home(self,u,refill=True):
        c=self.home(u,refill)
        if c:
            self.food_book[c['id']]=self.food_book.get(c['id'],0)+max(0,size(u)*2500-u.get('food',0))
            self.order(u,'move',point=c)
        return c

    def spots(self,count):
        vs=self.villages
        candidates=[{'x':v['x'],'y':v['y']} for v in vs]
        for a in vs:
            for b in vs:
                if a['id']<b['id'] and dist(a,b)<14000:
                    p={'x':(a['x']+b['x'])//2,'y':(a['y']+b['y'])//2}
                    if self.terrain[p['y']//2000][p['x']//2000]!=2: candidates.append(p)
        covered=set();chosen=[]
        for _ in range(count):
            if not candidates: break
            def score(p):
                return sum((.1 if v['id'] in covered else 1)*max(1,v.get('population',180))*max(0,1-dist(v,p)/11000) for v in vs)
            p=max(candidates,key=score);chosen.append(p);candidates.remove(p)
            covered.update(v['id'] for v in vs if dist(v,p)<7500)
        return chosen

    def logistics(self):
        # Budget each city once, with real crew, food and capacity accounting.
        count={cl:sum(p['clan']==cl for p in self.parties) for cl in range(self.n*6,self.n*6+6)}
        guards=set(self.guard)
        need_guard=max(0,min(4,len(self.owned))-len(guards))
        guard_city={min(self.owned,key=lambda c:dist(c,s))['id']:s for s in self.spots(4)} if self.owned else {}
        for c in sorted(self.owned,key=lambda x:x['id']):
            if c['id'] in self.besieged: continue
            g=self.units.get(c['garrison'])
            if not g or g.get('battle'): continue
            stock=g['healthy']; food=c['food']
            present=[p for p in self.parties if not p.get('battle') and dist(p,c)<=500]
            residents=size(g)+size(self.units.get(c.get('militia'),{}))
            reserve_food=residents*50*8
            free=[cl for cl in count if count[cl]<3]
            if need_guard and c['id'] in guard_city and stock>=20 and free and food>120000 and not any(dist(c,self.units[i])<13000 for i in guards if i in self.units):
                cl=min(free,key=lambda cl:(count[cl],cl!=c['clan'],cl))
                self.emit({'type':'create','city':c['id'],'clan':cl,'count':20},guard_city[c['id']])
                stock-=20;food-=60000;count[cl]+=1;need_guard-=1
            # Adjacent city relief is scheduled before troop mobilization.
            needy=[z for z in self.owned if z['id'] in c['neighbors'] and z['id'] not in self.besieged and z['food']<140000 and not any(u.get('destination')==z['id'] and u.get('phase')=='outbound' for u in self.own if u['kind']=='city_cart')]
            if needy and not c.get('convoy') and stock>=20 and food>800000:
                z=min(needy,key=lambda z:z['food']);cargo=min(940000,food-550000)
                self.emit({'type':'dispatch','city':c['id'],'destination':z['id'],'food':cargo})
                stock-=20;food-=cargo+60000
            # Transfer only affordable regulars; empty/poor cities keep healing casualties.
            for p in sorted(present,key=lambda u:(u['id'] in guards,-u['healthy'],u['id'])):
                target=20 if p['id'] in guards else 150
                missing_food=max(0,size(p)*2600-p.get('food',0))
                food-=min(max(0,food-reserve_food),missing_food)
                take=min(stock,max(0,target-size(p)),max(0,food-reserve_food)//3000)
                affordable=min(150,max(1,size(p)+take))
                if p.get('refill_target')!=max(affordable,p.get('reserve_refill_target',0)):
                    self.emit({'type':'set_strength','unit':p['id'],'target':affordable})
                if take:
                    self.emit({'type':'transfer','unit':g['id'],'target':p['id'],'count':take})
                    stock-=take;food-=take*3000
            free=[cl for cl in count if count[cl]<3]
            recruit=min(150,stock,max(0,food-reserve_food)//3000)
            if free and recruit>=45:
                cl=min(free,key=lambda cl:(count[cl],cl!=c['clan'],cl))
                self.emit({'type':'create','city':c['id'],'clan':cl,'count':recruit})
                count[cl]+=1
        for u in self.own:
            if u['kind']=='city_cart' and not u.get('battle') and u.get('cargo_food',0)>0:
                ps=[p for p in self.parties if not p.get('battle') and dist(p,u)<1000 and days(p)<18]
                if ps: self.emit({'type':'supply','unit':u['id'],'target':min(ps,key=days)['id']})

    def protect(self):
        for uid,spot in list(self.guard.items()):
            p=self.units.get(uid)
            if not p: self.guard.pop(uid);continue
            if p.get('battle'):continue
            home=self.home(p)
            danger=any(e['kind']=='party' and dist(p,e)<8500 and e['healthy']>p['healthy']*.8 for e in self.enemies)
            if danger or p['healthy']<18 or (home and days(p)<self.eta(p,home)/24+4):
                self.send_home(p);continue
            if not any(dist(spot,v)<10000 for v in self.villages):
                spots=self.spots(4)
                if spots: spot=max(spots,key=lambda s:min((dist(s,z) for i,z in self.guard.items() if i!=uid),default=10000));self.guard[uid]=spot
            self.order(p,'move',point=spot)

    def threat(self,p,radius=15000):
        return sum(e['healthy'] for e in self.enemies if e['kind']=='party' and dist(e,p)<radius)

    def defense(self,war):
        requests=self.o.get('relief_requests',[])
        if not requests:return False
        choices=[]
        for r in requests:
            es=[e for e in self.enemies if e['kind']=='party' and (e.get('battle') in {bid for bid in (r['battle'],r.get('relief_battle')) if bid is not None} or dist(e,r)<1300)]
            if es: choices.append((sum(e['healthy'] for e in es),r,es))
        if not choices:return False
        strength,r,es=min(choices,key=lambda z:z[0])
        other=[c for c in self.owned if c['id'] not in self.besieged]
        if not other:return False
        near=min(other,key=lambda c:dist(c,r))
        stage=self.point(r,near,4500)
        # Waiting for attrition is allowed; preserving the force beats piecemeal relief.
        committed=self.task and self.task['kind']=='relief' and self.task['id']==r['city']
        field=r.get('relief_battle')
        engaged=field and any(p.get('battle')==field for p in self.parties)
        if committed and engaged:
            # The committed force may arrive over several decisions. Already
            # fighting members must not make its remaining column fail a new
            # stand-alone strength check and turn back to the staging point.
            foe=max(es,key=lambda e:e['healthy'])
            for p in war:
                if p['id'] in self.cohort:self.order(p,'attack',target=foe)
            return True
        ready=[p for p in war if (dist(p,stage)<650 or (committed and p['id'] in self.cohort)) and days(p)>7]
        health=sum(p['healthy'] for p in ready)
        if health>strength*1.12+8:
            foe=max(es,key=lambda e:e['healthy'])
            for p in ready:self.order(p,'attack',target=foe)
            self.task={'kind':'relief','id':r['city'],'at':self.h}
            self.cohort=[p['id'] for p in ready]
        else:
            for p in war:
                if days(p)>self.eta(p,stage)/24+6:self.order(p,'move',point=stage,relief=r['city'])
                else:self.send_home(p)
        return True

    def siege_cost(self,c):
        g=c.get('healthy',50);m=c.get('militia_healthy',min(200,100+self.h//24))
        body=g+m;equiv=2*g+m
        inside=set()
        for e in self.enemies:
            if e['kind'] in ('garrison','militia') or dist(e,c)>1000 or e.get('battle'):continue
            body+=e['healthy'];equiv+=e['healthy']*(1 if e['kind']=='village_cart' else 2);inside.add(e['id'])
        # Only observed or recently observed reinforcements which could arrive matter.
        rein=0
        for uid,(at,e) in self.seen.items():
            if e['kind']!='party' or uid in inside:continue
            age=self.h-at
            if age>96:continue
            reach=dist(e,c)-age*500
            if reach<26000:rein+=e['healthy']*(1 if age<=24 else .7)
        return body,equiv,rein

    def can_siege(self,c,group):
        if c.get('stale',True):return False
        h=sum(p['healthy'] for p in group)
        body,equiv,rein=self.siege_cost(c)
        # Approximate conserved cached-power loss; retain a margin for integer allocation.
        loss=body*equiv/max(1,h)
        remaining=h-loss
        home=self.home(group[0]) if group else None
        duration=3+min(7,math.ceil((h+body)/300))*body/max(1,h)
        need=duration+(self.eta(c,home)/24 if home else 8)+4
        return h>math.sqrt(body*equiv)*1.45 and remaining>rein*1.18+35 and min((days(p) for p in group),default=0)>need

    def field_target(self,group):
        if not group:return None
        lead=group[0];h=sum(p['healthy'] for p in group)
        choices=[]
        for e in self.enemies:
            if e['kind'] not in ('party','village_cart','city_cart') or dist(e,lead)>10000:continue
            # Never let an attack on a city resident bypass the siege budget.
            if any(c['nation']!=self.n and dist(c,e)<1600 for c in self.o['cities']):continue
            nearby=sum(z['healthy']*(.5 if z['kind']=='village_cart' else 1) for z in self.enemies if z['kind'] not in ('garrison','militia') and dist(z,e)<10000)
            if h<nearby*1.40+15:continue
            score=(3 if e['kind']=='party' else 1)*e['healthy']/(dist(lead,e)+3000)
            choices.append((score,e))
        return max(choices,key=lambda z:z[0])[1] if choices else None

    def campaign(self,war):
        if not war:return
        if self.defense(war):return
        busy=[p for p in self.parties if p.get('battle') and p['id'] not in self.guard]
        # Reinforce ongoing friendly field action only when physically near; otherwise refit.
        if busy:
            for p in war:
                battle=self.battles.get(busy[0]['battle'])
                if battle and dist(p,battle)<8000 and days(p)>10:self.order(p,'move',point=battle)
                else:self.send_home(p)
            return
        if self.task and self.task['kind']=='relief':self.task=None
        # A postbattle refit is distributed by actual city food and recruits.
        fought=[p for p in war if (p['id'] in self.previous_battle and p.get('wounded',0)>2) or p.get('wounded',0)>size(p)*.22]
        if fought:
            for p in fought:self.rest[p['id']]=self.h+72
        ready=[]
        for p in war:
            home=self.home(p)
            if p['healthy']<25 or self.rest.get(p['id'],0)>self.h or (home and days(p)<self.eta(p,home)/24+5):
                self.send_home(p)
            else:ready.append(p)
        war=ready
        if not war:return
        if self.task:
            c=self.cities.get(self.task['id'])
            if not c or c['id'] in self.owned_ids or c['id'] not in self.o.get('frontier_targets',[]) or self.h-self.task['at']>480:
                self.task=None
        if not self.task:
            opts=[]
            for c in self.o['cities']:
                if c['id'] not in self.o.get('frontier_targets',[]) or self.cool.get(c['id'],0)>self.h:continue
                for base in self.owned:
                    if base['id'] in self.besieged or c['id'] not in base['neighbors'] or base['food']<80000:continue
                    travel=sum(self.eta(p,base)*p['healthy'] for p in war)/max(1,sum(p['healthy'] for p in war))
                    body,equiv,rein=self.siege_cost(c)
                    score=travel*.55+self.eta(base,c)+math.sqrt(body*equiv)*.08+rein*.04
                    opts.append((score,c,base))
            if not opts:
                for p in war:self.send_home(p)
                return
            _,c,base=min(opts,key=lambda z:(z[0],z[1]['id']))
            self.task={'kind':'rally','id':c['id'],'base':base['id'],'at':self.h}
            self.cohort=[]
        c=self.cities[self.task['id']];base=self.cities.get(self.task.get('base'))
        if not base or base['id'] not in self.owned_ids or base['id'] in self.besieged:
            self.task=None;return
        stage=self.point(c,base,7000)
        kind=self.task['kind']
        if kind=='rally':
            for p in war:self.order(p,'move',point=base)
            near=[p for p in war if dist(p,base)<450 and days(p)>self.eta(base,stage)/24+14]
            h=sum(p['healthy'] for p in near);total=sum(p['healthy'] for p in war)
            if h>=max(180,total*.82):
                self.task['kind']='probe';self.cohort=[p['id'] for p in near]
                self.replace_moves(near)
                for p in near:self.order(p,'move',point=stage)
            return
        group=[p for p in war if p['id'] in self.cohort]
        if not group:self.task=None;return
        center={'x':sum(p['x']*p['healthy'] for p in group)//max(1,sum(p['healthy'] for p in group)), 'y':sum(p['y']*p['healthy'] for p in group)//max(1,sum(p['healthy'] for p in group))}
        compact=[p for p in group if dist(p,center)<650]
        concentrated=sum(p['healthy'] for p in compact)>=sum(p['healthy'] for p in group)*.92
        # Reconsider every six hours until actual contact makes combat irreversible.
        if kind=='siege':
            if not self.can_siege(c,group):
                self.task=None;self.cool[c['id']]=self.h+72
                for p in group:self.send_home(p)
            else:
                for p in group:self.order(p,'siege',target=c)
            return
        target=self.field_target(compact) if concentrated else None
        if target:
            for p in compact:self.order(p,'attack',target=target)
            self.task['kind']='probe'
            return
        if concentrated and dist(center,stage)<800 and self.can_siege(c,compact):
            for p in compact:self.order(p,'siege',target=c)
            self.task['kind']='siege';return
        # If a defended city is uneconomic, attack its future production with the same
        # protected force. The opponent must either concede output or leave the walls.
        if concentrated and dist(center,stage)<900 or kind=='raid':
            villages=[v for v in self.o['villages'] if v['nation']!=self.n and v['city']==c['id'] and not v.get('stale',True) and v.get('disabled_until',0)<=self.h and self.threat(v)<sum(p['healthy'] for p in compact)/1.4]
            if villages and compact:
                v=min(villages,key=lambda v:dist(center,v))
                if all(days(p)>self.eta(p,base)/24+8 for p in compact):
                    for p in compact:self.order(p,'raid',target=v)
                    self.task['kind']='raid';return
            if kind=='raid' or self.h-self.task['at']>240:
                self.cool[c['id']]=self.h+96;self.task=None
                for p in group:self.send_home(p)
                return
        for p in war:self.order(p,'move',point=stage if p['id'] in self.cohort else base)

    def replace_moves(self,ps):
        ids={p['id'] for p in ps}
        # Keep all resource-command indices stable for create outcomes.
        self.commands=[c for c in self.commands if not (c['type'] in ('move','attack','raid','siege') and c.get('unit') in ids)]
        self.used.difference_update(ids)

    def decide(self,o,outcomes=()):
        for i,spot in self.pending.items():
            if i<len(outcomes) and outcomes[i].get('ok') and outcomes[i].get('unit'):self.guard[outcomes[i]['unit']]=spot
        self.pending={};self.commands=[];self.used=set();self.food_book={}
        self.o=o;self.n=o['nation'];self.h=o['hour'];self.terrain=o['terrain']
        self.units={u['id']:u for u in o['units']};self.cities={c['id']:c for c in o['cities']}
        self.own=[u for u in o['units'] if u['nation']==self.n]
        self.parties=[u for u in self.own if u['kind']=='party']
        self.enemies=[u for u in o['units'] if u['nation'] not in (self.n,-1)]
        self.battles={b['id']:b for b in o['battles']}
        self.owned=[c for c in o['cities'] if c['nation']==self.n and not c.get('stale',False) and 'garrison' in c and c['garrison'] in self.units and self.units[c['garrison']]['nation']==self.n]
        self.owned_ids={c['id'] for c in self.owned}
        self.villages=[v for v in o['villages'] if v['city'] in self.owned_ids and v['nation']==self.n and 'cart' in v]
        self.besieged={r['city'] for r in o.get('relief_requests',[])}
        self.guard={i:p for i,p in self.guard.items() if i in self.units and self.units[i]['nation']==self.n}
        # A forgotten visible unit cannot remain a phantom reinforcement at its old point.
        for uid,(at,e) in list(self.seen.items()):
            visible_here=any(dist(e,c)<9500 for c in self.owned) or any(dist(e,p)<7500 for p in self.parties)
            if self.h-at>96 or (uid not in self.units and visible_here):self.seen.pop(uid,None)
        for e in self.enemies:self.seen[e['id']]=(self.h,dict(e))
        if not self.initialized:
            # Restart-safe role reconstruction uses only our live unit attributes.
            if self.h>0:
                small=[p for p in self.parties if size(p)<=25 and p.get('refill_target',150)<=25]
                for spot in self.spots(min(4,len(small))):
                    p=min(small,key=lambda p:dist(p,spot));small.remove(p);self.guard[p['id']]=spot
            self.initialized=True
        self.logistics();self.protect()
        war=[p for p in self.parties if p['id'] not in self.guard and not p.get('battle') and p['id'] not in self.used]
        self.campaign(war)
        self.previous_battle={p['id'] for p in self.parties if p.get('battle')}
        return self.commands


def main():
    sys.stdin.reconfigure(encoding='utf-8');sys.stdout.reconfigure(encoding='utf-8')
    policy=Policy()
    for line in sys.stdin:
        r=json.loads(line)
        cmds=policy.decide(r['observation'],r.get('previous_outcomes',[]))
        print(json.dumps({'protocol_version':1,'request_id':r['request_id'],'commands':cmds}),flush=True)


if __name__=='__main__':main()
