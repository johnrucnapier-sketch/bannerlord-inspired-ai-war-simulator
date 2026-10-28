"""Pure pathfinding and arrival estimates using public map data."""
import heapq
import math

def passable(terrain,x,y):
    return 0<=x<60 and 0<=y<40 and terrain[y][x]!=2

def find_route(terrain, u, x, y):
    goal = (x//2000, y//2000)
    start = (u['x']//2000, u['y']//2000)
    if not passable(terrain,*goal):
        return None
    if start == goal:
        return [[x,y]]
    heap = [(0, start)]
    costs = {start: 0}
    parents = {}
    while heap:
        _, p = heapq.heappop(heap)
        if p == goal:
            cells = []
            while p != start:
                cells.append([p[0]*2000+1000, p[1]*2000+1000])
                p = parents[p]
            cells.reverse()
            cells.append([x,y])
            return cells
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            q = (p[0]+dx,p[1]+dy)
            if not passable(terrain,*q):
                continue
            cost = costs[p]+(4 if terrain[q[1]][q[0]] else 3)
            if cost < costs.get(q,10**9):
                costs[q] = cost
                parents[q] = p
                h = (abs(q[0]-goal[0])+abs(q[1]-goal[1]))*3
                heapq.heappush(heap,(cost+h,q))
    return None

def travel_hours(terrain,u,target,speeds,max_hours=72):
    path=find_route(terrain,u,target['x'],target['y'])
    if path is None:return None
    x,y=u['x'],u['y']
    for hour in range(max_hours+1):
        if math.isqrt((x-target['x'])**2+(y-target['y'])**2)<=1000:return hour
        if hour==max_hours:return None
        speed=speeds['army' if u.get('army') else u['kind']]
        if terrain[min(39,y//2000)][min(59,x//2000)]==1:speed=speed*3//4
        while path and speed>0:
            tx,ty=path[0];dx,dy=tx-x,ty-y;distance=math.isqrt(dx*dx+dy*dy)
            if distance<=speed:
                x,y=tx,ty;path.pop(0);speed-=distance
            else:
                x+=int(dx*speed/distance);y+=int(dy*speed/distance);speed=0
    return None


def relief_terrain(terrain,city,unit):
    """Waiting reinforcements route around the besieging/relief battlefield."""
    safe=[row[:] for row in terrain]
    start=(unit['x']//2000,unit['y']//2000)
    for y in range(max(0,city['y']//2000-2),min(40,city['y']//2000+3)):
        for x in range(max(0,city['x']//2000-2),min(60,city['x']//2000+3)):
            if (x,y)!=start and math.hypot(x*2000+1000-city['x'],y*2000+1000-city['y'])<2500:safe[y][x]=2
    return safe
