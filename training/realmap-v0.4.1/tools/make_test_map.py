"""Generate an original rectangular CI fixture, NOT the Bannerlord map or a benchmark."""
import argparse,json
from pathlib import Path

def generate(out):
    out.mkdir(parents=True,exist_ok=False)
    vertices=[[320+x*32,280+y*100] for y in range(3) for x in range(16)]
    faces=[]
    for y in range(2):
        for x in range(15):
            i=y*15+x;v=y*16+x
            faces.append(dict(id=i,vertices=[v,v+1,v+17,v+16],walkable=True,category='land',source_group=1,bridge_overlay=i==0,neighbors=[yy*15+xx for xx,yy in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)) if 0<=xx<15 and 0<=yy<2]))
    i=len(vertices);vertices.extend([[900,800],[910,800],[900,810]])
    faces.append(dict(id=30,vertices=[i,i+1,i+2],walkable=False,category='water',source_group=19,bridge_overlay=False,neighbors=[]))
    points=[];clans=[]
    for row,(nation,count,nv) in enumerate([('empire_w',14,31),('empire',15,32)]):
        for j in range(count):
            x=330+j*32;y=300+row*100;cid=f'fixture_city_{row}_{j}';owner=f'fixture_clan_{row}_{j%9}'
            points.append(dict(id=cid,name=f'Test {row}-{j}',kind='city',original_kind='town' if j<6 else 'castle',kingdom=nation,owner_clan=owner,x=x,y=y,gate_x=x,gate_y=y))
        for j in range(nv):
            x=334+(j%count)*32;y=310+row*100+(j//count)*10
            points.append(dict(id=f'fixture_village_{row}_{j}',name=f'Village {row}-{j}',kind='village',original_kind='village',kingdom=nation,parent_city=f'fixture_city_{row}_{j%count}',x=x,y=y,gate_x=x,gate_y=y))
        for j in range(9):clans.append(dict(id=f'fixture_clan_{row}_{j}',name=f'Clan {row}-{j}',kingdom=nation,initial_home_settlement=f'fixture_city_{row}_{j}',owned_city_ids=[f'fixture_city_{row}_{k}' for k in range(count) if k%9==j]))
    clans.sort(key=lambda c:c['kingdom'])
    for name,data in [('navigation.json',dict(vertices_xy=vertices,faces=faces)),('settlements.json',points),('clans.json',clans)]:
        (out/name).write_text(json.dumps(data,ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);generate(p.parse_args().output)
