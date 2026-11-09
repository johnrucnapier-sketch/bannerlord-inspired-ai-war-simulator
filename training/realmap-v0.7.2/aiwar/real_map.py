"""War Sails-derived strategic map (bundled in the v0.6.0 source package). Coordinates are original game XY * 1000.
No third-party rendering assets or game binaries are needed at runtime.
"""
import json, math, heapq, hashlib, os
from pathlib import Path
from functools import lru_cache
from collections import defaultdict

ROOT=Path(os.environ['AIWAR_MAP_DIR']).expanduser() if os.environ.get('AIWAR_MAP_DIR') else Path(__file__).with_name('data')/'west_north'
DATA_FILES=('navigation.json','settlements.json','clans.json','clan_tiers.json')
def map_hashes():
    missing=[name for name in DATA_FILES if not (ROOT/name).is_file()]
    if missing:raise ValueError('真实地图数据未安装：请按 training/realmap-v0.7.0/README.md 导入地图包；缺少 '+', '.join(missing))
    return {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in DATA_FILES}

MAP_ID='calradia_eight_v1'
NATIONS = (
    ('empire_w','西帝国','empire'), ('empire','北帝国','empire'),
    ('empire_s','南帝国','empire'), ('khuzait','库赛特','khuzait'),
    ('battania','巴丹尼亚','battania'), ('vlandia','瓦兰迪亚','vlandia'),
    ('sturgia','斯特吉亚','sturgia'), ('aserai','阿塞莱','aserai'),
)

LAND={1,2,3,4,5,6,15,16,17,20}
def cross(a,b):return a[0]*b[1]-a[1]*b[0]
def contains(poly,x,y):
    hit=False
    for a,b in zip(poly,poly[1:]+poly[:1]):
        dx,dy=b[0]-a[0],b[1]-a[1]
        length=math.hypot(dx,dy)
        if abs(dx*(y-a[1])-dy*(x-a[0]))<=2*length and min(a[0],b[0])-2<=x<=max(a[0],b[0])+2 and min(a[1],b[1])-2<=y<=max(a[1],b[1])+2:return True
        if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:hit=not hit
    return hit

def segment_parameters(poly,a,b):
    ds=(b[0]-a[0],b[1]-a[1]);ts=[0.,1.]
    for c,d in zip(poly,poly[1:]+poly[:1]):
        de=(d[0]-c[0],d[1]-c[1]);den=cross(ds,de)
        if not den:continue
        ca=(c[0]-a[0],c[1]-a[1]);t=cross(ca,de)/den;u=cross(ca,ds)/den
        if 0<t<1 and 0<=u<=1:ts.append(t)
    return sorted(set(ts))

def within(poly,a,b):
    ts=segment_parameters(poly,a,b)
    return all(contains(poly,a[0]+(b[0]-a[0])*(l+r)/2,a[1]+(b[1]-a[1])*(l+r)/2) for l,r in zip(ts,ts[1:]))

def local_path(poly,a,b):
    if within(poly,a,b):return [list(b)]
    nodes=[a,b]+list(poly);heap=[(0,0)];cost={0:0};parent={}
    while heap:
        d,i=heapq.heappop(heap)
        if i==1:
            out=[list(b)]
            while parent[i]!=0:i=parent[i];out.append(list(nodes[i]))
            return list(reversed(out))
        for j,q in enumerate(nodes):
            if j==i or not within(poly,nodes[i],q):continue
            nd=d+math.dist(nodes[i],q)
            if nd<cost.get(j,math.inf):cost[j]=nd;parent[j]=i;heapq.heappush(heap,(nd,j))
    return None

class Mesh:
    def __init__(self):
        map_hashes()
        raw=(ROOT/'navigation.json').read_bytes()
        self.sha=hashlib.sha256(raw).hexdigest()
        data=json.loads(raw)
        self.vertices=[(round(x*1000),round(y*1000)) for x,y in data['vertices_xy']]
        self.faces={f['id']:f for f in data['faces'] if f['walkable']}
        self.polys={i:[self.vertices[v] for v in f['vertices']] for i,f in self.faces.items()}
        self.centers={i:(round(sum(p[0] for p in ps)/len(ps)),round(sum(p[1] for p in ps)/len(ps))) for i,ps in self.polys.items()}
        self.bins=defaultdict(list)
        for i,ps in self.polys.items():
            for x in range(min(p[0] for p in ps)//10000,max(p[0] for p in ps)//10000+1):
                for y in range(min(p[1] for p in ps)//10000,max(p[1] for p in ps)//10000+1):self.bins[x,y].append(i)
        self.portals={}
        for i,f in self.faces.items():
            for j in f['neighbors']:
                shared=set(f['vertices'])&set(self.faces[j]['vertices'])
                assert len(shared)==2,(i,j)
                a,b=[self.vertices[k] for k in sorted(shared)]
                self.portals[i,j]=((a[0]+b[0])//2,(a[1]+b[1])//2)
        # Immutable mesh geometry: preserve neighbor order and exact float arithmetic.
        self.route_edges={i:tuple((j,math.dist(self.centers[i],self.portals[i,j])+
                                  math.dist(self.portals[i,j],self.centers[j]))
                                 for j in f['neighbors']) for i,f in self.faces.items()}

    @lru_cache(maxsize=32768)
    def face(self,x,y):
        for i in self.bins.get((x//10000,y//10000),[]):
            if contains(self.polys[i],x,y):return i
        return None

    @lru_cache(maxsize=8192)
    def face_route(self,start,goal,exclusion):
        if start==goal:return (start,)
        costs={start:0};parents={};heap=[(0,start)];heuristic={}
        edges=self.route_edges;centers=self.centers;goal_center=centers[goal]
        pop=heapq.heappop;push=heapq.heappush;dist=math.dist
        get_cost=costs.get;infinity=math.inf
        while heap:
            _,i=pop(heap)
            if i==goal:
                out=[i]
                while i!=start:i=parents[i];out.append(i)
                return tuple(reversed(out))
            current_cost=costs[i]
            for j,step in edges[i]:
                if exclusion and j not in (start,goal) and dist(centers[j],exclusion[:2])<exclusion[2]:continue
                cost=current_cost+step
                if cost<get_cost(j,infinity):
                    costs[j]=cost;parents[j]=i
                    if j not in heuristic:heuristic[j]=dist(centers[j],goal_center)
                    push(heap,(cost+heuristic[j],j))
        return None

    @lru_cache(maxsize=8192)
    def portal_path(self,previous,current,following):
        # Only immutable portal endpoints are cached. Dynamic start/goal
        # coordinates retain the original calculation and numeric types.
        part=local_path(self.polys[current],self.portals[previous,current],
                        self.portals[current,following])
        return None if part is None else tuple(tuple(point) for point in part)

    def route(self,u,x,y,exclusion=()):
        start=self.face(u['x'],u['y']);goal=self.face(x,y)
        if start is None or goal is None:return None
        ids=self.face_route(start,goal,tuple(exclusion))
        if ids is None:return None
        out=[];at=(u['x'],u['y'])
        for index,(i,j) in enumerate(zip(ids,ids[1:])):
            target=self.portals[i,j]
            if index:
                cached=self.portal_path(ids[index-1],i,j)
                part=None if cached is None else [list(point) for point in cached]
            else:
                part=local_path(self.polys[i],at,target)
            if part is None:return None
            out.extend(part);at=target
        part=local_path(self.polys[ids[-1]],at,(x,y))
        return out+part if part is not None else None

    def clear_segment(self,a,b):
        start=(a['x'],a['y']);end=(b['x'],b['y'])
        ids=set()
        for x in range(min(start[0],end[0])//10000,max(start[0],end[0])//10000+1):
            for y in range(min(start[1],end[1])//10000,max(start[1],end[1])//10000+1):ids.update(self.bins.get((x,y),[]))
        ts=sorted(set(t for i in ids for t in segment_parameters(self.polys[i],start,end)))
        return all(any(contains(self.polys[i],start[0]+(end[0]-start[0])*(l+r)/2,start[1]+(end[1]-start[1])*(l+r)/2) for i in ids) for l,r in zip(ts,ts[1:]))

    def neighbors(self,cities):
        # Land-distance Voronoi adjacency replaces the synthetic map's fixed radius.
        owner={};cost={};heap=[]
        for c in sorted(cities.values(),key=lambda c:c['id']):
            i=self.face(c['x'],c['y'])
            owner[i]=c['id'];cost[i]=0;heapq.heappush(heap,(0,c['id'],i))
        while heap:
            d,cid,i=heapq.heappop(heap)
            if d!=cost[i] or cid!=owner[i]:continue
            for j in self.faces[i]['neighbors']:
                nd=d+math.dist(self.centers[i],self.centers[j])
                if nd<cost.get(j,math.inf):
                    cost[j]=nd;owner[j]=cid;heapq.heappush(heap,(nd,cid,j))
        links={k:set() for k in cities}
        for i,a in owner.items():
            for j in self.faces[i]['neighbors']:
                b=owner.get(j)
                if b and a!=b:links[a].add(b);links[b].add(a)
        return {k:sorted(v) for k,v in links.items()}

@lru_cache(maxsize=1)
def mesh():return Mesh()

def initialize(w):
    hashes=map_hashes();m=mesh()
    if m.sha!=hashes['navigation.json']:raise ValueError('地图数据已变更，请重启进程后使用')
    expected=w.cfg.get('map_data_hashes')
    if expected is not None and expected!=hashes:raise ValueError('真实地图数据版本不匹配')
    if w.cfg.get('local_baseline')=='v0.4.1-castles-cavalry' or w.cfg.get('realmap_rules_v6'):w.cfg['map_data_hashes']=hashes
    w.cfg.update(mode='realmap',map_id=MAP_ID,map_sha256=m.sha,clan_party_cap=3)
    w.cfg.setdefault('local_baseline','v0.3.0-local-realmap')
    w.terrain={'kind':'navmesh','map_id':MAP_ID,'sha256':m.sha,'bounds':[70000,15000,1010000,940000]}
    points=json.loads((ROOT/'settlements.json').read_text(encoding='utf-8'))
    clans=json.loads((ROOT/'clans.json').read_text(encoding='utf-8'))
    requested=w.cfg.get('nations',[row[0] for row in NATIONS])
    if not isinstance(requested,list) or len(requested)<2 or len(set(requested))!=len(requested) or any(k not in dict((r[0],r) for r in NATIONS) for k in requested):
        raise ValueError('nations must contain 2–8 distinct supported kingdom IDs')
    nations={k:i for i,k in enumerate(requested)}
    w.cfg['nations']=requested
    records={row[0]:row for row in NATIONS}
    w.nations={str(i):dict(id=i,kingdom=k,name=records[k][1],culture=records[k][2],region_index=next(j for j,r in enumerate(NATIONS) if r[0]==k)) for k,i in nations.items()}
    clans=[c for c in clans if c['kingdom'] in nations]
    # Four cultures have source owner IDs but not verified clan names/homes.
    # Preserve those IDs and disclose a deterministic scenario home, never a claimed canonical home.
    existing={c['id'] for c in clans}
    for owner in sorted({p['owner_clan'] for p in points if p['kingdom'] in nations and p['kind']=='city'}-existing):
        owned=sorted((p for p in points if p['kind']=='city' and p['owner_clan']==owner),key=lambda p:(p['original_kind']!='town',p['id']))
        clans.append(dict(id=owner,name=owner,kingdom=owned[0]['kingdom'],initial_home_settlement=owned[0]['id'],owned_city_ids=[p['id'] for p in owned],party_slots=3,provenance='owner_id_from_map; name_unverified; home_scenario_assigned'))
    tiers=json.loads((ROOT/'clan_tiers.json').read_text(encoding='utf-8'))['tiers']
    for c in clans:
        if c['id'] not in tiers:raise ValueError('Missing verified clan tier: '+c['id'])
        c['tier']=tiers[c['id']]
        c['party_slots']=1 if c['tier']<3 else 2 if c['tier']<5 else 3
        c['party_limit_model']='vanilla_npc_base_no_talent_magnet'
    clans.sort(key=lambda c:c['id'])
    w.map_clans={str(i):dict(c,nation=nations[c['kingdom']]) for i,c in enumerate(clans)}
    clan_ids={c['id']:i for i,c in enumerate(clans)}
    for n in w.nations.values():
        n['ruler_clan']=next(i for i,c in enumerate(clans) if c['kingdom']==n['kingdom'] and c['id'].endswith('_1'))
    selected=[p for p in points if p['kingdom'] in nations]
    def pos(p):
        return dict(x=round(p['gate_x']*1000),y=round(p['gate_y']*1000),
                    map_x=round(p['x']*1000),map_y=round(p['y']*1000),source_id=p['id'])
    for p in selected:
        if p['kind']!='city':continue
        n=nations[p['kingdom']];clan=clan_ids[p['owner_clan']];cid=p['id']
        c=dict(id=cid,name=p['name'],nation=n,origin_nation=n,clan=clan,food=w.cfg['initial_city_food'],recruits=0,
               garrison='g_'+cid,militia='m_'+cid,militia_reset_hour=-1,convoy=None,neighbors=[],**pos(p))
        if w.cfg.get('castle_logistics'):c.update(settlement_type=p['original_kind'],training_hours=0,supply_neighbors=[])
        w.cities[cid]=c
        w.new_unit('garrison',n,clan,w.cfg['initial_garrison'],c['x'],c['y'],uid=c['garrison'],home=cid)
        w.new_unit('militia',n,clan,w.cfg['militia_initial'],c['x'],c['y'],uid=c['militia'],home=cid)
    for i,clan in enumerate(clans):
        home=w.cities[clan['initial_home_settlement']]
        for _ in range(clan['party_slots']):
            w.new_unit('party',nations[clan['kingdom']],i,w.cfg['initial_soldiers'],home['x'],home['y'],
                       food=w.cfg['initial_soldiers']*w.cfg['field_ration']*w.cfg['carry_days'])
    for p in selected:
        if p['kind']!='village':continue
        c=w.cities[p['parent_city']];vid=p['id']
        v=dict(id=vid,name=p['name'],city=c['id'],nation=c['nation'],initial_nation=c['nation'],origin_nation=c['nation'],
               population=w.cfg['population']-w.cfg['village_crew'],food=0,recruits=0,disabled_until=0,
               cart=None,raid=None,**pos(p))
        w.villages[vid]=v
        u=w.new_unit('village_cart',c['nation'],c['clan'],w.cfg['village_crew'],v['x'],v['y'],home=vid)
        v['cart']=u['id']
    if w.cfg.get('realmap_profile')=='plan_a_10y_v1':w.cfg['unification_city_count']=len(w.cities)
    for k,links in m.neighbors(w.cities).items():w.cities[k]['neighbors']=links
    if w.cfg.get('castle_logistics'):
        for c in w.cities.values():
            for cid in c['neighbors']:
                d=w.cities[cid];path=m.route(c,d['x'],d['y']);last=(c['x'],c['y']);length=0
                for q in path or []:length+=math.dist(last,q);last=q
                if path is not None and length<=w.cfg['supply_max_distance']:c['supply_neighbors'].append(cid)
    w.map_info=dict(id=MAP_ID,nations=[w.nations[str(i)]['name'] for i in range(len(nations))],nation_registry=w.nations,clans=w.map_clans,
                    bounds=[min(p['x'] for p in selected)*1000-10000,min(p['y'] for p in selected)*1000-10000,max(p['x'] for p in selected)*1000+10000,max(p['y'] for p in selected)*1000+10000],units_per_game_coordinate=1000,
                    boundary_policy='selected_nations_free_for_all; no_unselected_units')
