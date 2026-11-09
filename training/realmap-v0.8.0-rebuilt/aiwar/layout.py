"""Rotationally paired frontier, with irregular but comparable city spacing."""
import math
import random

LEGACY_CITIES = [(20000,14000),(47000,12000),(17000,39000),
                 (73000,41000),(22000,66000),(48000,68000)]
BASE_CITIES = [(20000,14000),(47000,12000),(17000,39000),
               (47000,39000),(22000,66000),(48000,68000)]


def cities(legacy=False):
    base=LEGACY_CITIES if legacy else BASE_CITIES
    return list(base)+[(120000-x,80000-y) for x,y in base]


def villages(seed,legacy=False):
    """Paired offsets; all villages beyond urban sight, without settlement overlap."""
    rng=random.Random(seed+41037)
    centers=cities(legacy)
    base=LEGACY_CITIES if legacy else BASE_CITIES
    placed=[]
    result={}
    for j,(x,y) in enumerate(base):
        chosen=[]
        for k in range(3):
            for _ in range(6000):
                radius=rng.randint(11000,16000)
                angle=rng.uniform(0,math.tau)
                a=(round(x+radius*math.cos(angle)),round(y+radius*math.sin(angle)))
                b=(120000-a[0],80000-a[1])
                if not (2500<a[0]<117500 and 2500<a[1]<77500):continue
                if min(math.dist(a,c) for c in centers)<10500:continue
                if any(math.dist(p,q)<2800 for p in (a,b) for q in placed):continue
                if any(abs(math.atan2(a[1]-y,a[0]-x)-math.atan2(q[1]-y,q[0]-x))<0.3 for q in chosen):continue
                # Keep the grid-route round trip below a week under normal terrain.
                if abs(a[0]-x)+abs(a[1]-y)>17000:continue
                chosen.append(a);placed.extend((a,b))
                result[(0,j,k)]=a;result[(1,j,k)]=b
                break
            else:raise ValueError('Cannot construct separated villages for this seed')
    return result
