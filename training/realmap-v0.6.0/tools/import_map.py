"""Optionally validate or import an alternative map; v0.5.0 already bundles its default map. Never reads DLLs or network services."""
import argparse,hashlib,json,math,os,shutil,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
FILES=('navigation.json','settlements.json','clans.json')

def validate(source):
    data={name:json.loads((source/name).read_text(encoding='utf-8')) for name in FILES}
    nav=data['navigation.json'];vertices=nav['vertices_xy'];faces=nav['faces']
    if not vertices or not faces:raise ValueError('empty navigation mesh')
    if any(len(v)!=2 or any(type(x) not in (int,float) or not math.isfinite(x) for x in v) for v in vertices):raise ValueError('invalid vertex')
    byid={f['id']:f for f in faces}
    if len(byid)!=len(faces):raise ValueError('duplicate face IDs')
    for f in faces:
        if type(f['walkable']) is not bool or len(set(f['vertices']))<3 or any(type(i) is not int or not 0<=i<len(vertices) for i in f['vertices']):raise ValueError('invalid face')
        for n in f['neighbors']:
            if n not in byid or (f['walkable'] and (not byid[n]['walkable'] or f['id'] not in byid[n]['neighbors'] or len(set(f['vertices'])&set(byid[n]['vertices']))!=2)):raise ValueError('invalid shared-edge adjacency')
    points=data['settlements.json'];clans=data['clans.json'];nations=('empire_w','empire')
    if len({p['id'] for p in points})!=len(points) or len({c['id'] for c in clans})!=len(clans):raise ValueError('duplicate settlement/clan IDs')
    for n,nc,nv,nt in [('empire_w',14,31,6),('empire',15,32,6)]:
        ps=[p for p in points if p['kingdom']==n];cs=[c for c in clans if c['kingdom']==n]
        if (sum(p['kind']=='city' for p in ps),sum(p['kind']=='village' for p in ps),len(cs),sum(p.get('original_kind')=='town' for p in ps))!=(nc,nv,9,nt):raise ValueError('unexpected West/North settlement or clan counts')
        own={c['id'] for c in cs};towns={p['id']:p for p in ps if p['kind']=='city'}
        for p in ps:
            for key in ('x','y','gate_x','gate_y'):
                if type(p[key]) not in (int,float) or not math.isfinite(p[key]):raise ValueError('invalid coordinates')
            if p['kind']=='city':
                if p['owner_clan'] not in own or p['original_kind'] not in ('town','castle'):raise ValueError('invalid fief owner/type')
            elif p['kind']!='village' or p['parent_city'] not in towns:raise ValueError('invalid village binding')
        if any(c['initial_home_settlement'] not in towns for c in cs):raise ValueError('invalid clan home')
    # Exercise the same geometry and initialization used by the training environment.
    from aiwar import real_map
    from aiwar.engine import World
    old=real_map.ROOT
    try:
        real_map.ROOT=source;real_map.mesh.cache_clear()
        w=World(1,{'mode':'realmap'});w.check()
        for p in [*w.cities.values(),*w.villages.values()]:
            if real_map.mesh().face(p['x'],p['y']) is None:raise ValueError('gate is outside walkable land')
        for v in w.villages.values():
            c=w.cities[v['city']]
            if w.route(v,c['x'],c['y']) is None:raise ValueError('village cannot reach its bound fief')
    finally:real_map.ROOT=old;real_map.mesh.cache_clear()
    return data

def render(nav,folder):
    from PIL import Image,ImageDraw
    folder.mkdir(parents=True,exist_ok=True)
    colors={'land':'#3a5049','water':'#182e3c','mountain':'#68766c','blocked':'#68766c'}
    for name,b in [('focus',[313554.25,269185.,832429.75,615102.]),('world',[-153750.,15000.,1233750.,940000.])]:
        image=Image.new('RGB',(1584,1056),colors['water']);draw=ImageDraw.Draw(image)
        for f in sorted(nav['faces'],key=lambda f:f['walkable']):
            points=[((nav['vertices_xy'][i][0]*1000-b[0])*1584/(b[2]-b[0]),(b[3]-nav['vertices_xy'][i][1]*1000)*1056/(b[3]-b[1])) for i in f['vertices']]
            draw.polygon(points,fill=colors.get(f.get('category'),colors['land'] if f['walkable'] else colors['blocked']))
        image.save(folder/f'realmap_{name}.png')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--render',action='store_true',help='generate local viewer PNGs (requires Pillow)');p.add_argument('--check-only',action='store_true');a=p.parse_args()
    source=a.source.resolve();data=validate(source)
    hashes={n:hashlib.sha256((source/n).read_bytes()).hexdigest() for n in FILES}
    dest=ROOT/'aiwar/data/west_north'
    if not a.check_only:
        dest.mkdir(parents=True,exist_ok=True)
        existing=[n for n in FILES if (dest/n).exists() and hashlib.sha256((dest/n).read_bytes()).hexdigest()!=hashes[n]]
        if existing:raise SystemExit('Different map already installed; preserve it and use a separate checkout or AIWAR_MAP_DIR. Refusing overwrite.')
        with tempfile.TemporaryDirectory(dir=dest.parent) as td:
            for n in FILES:shutil.copyfile(source/n,Path(td)/n)
            if a.render:render(data['navigation.json'],Path(td)/'assets')
            for n in FILES:os.replace(Path(td)/n,dest/n)
            if a.render:
                target=ROOT/'godot/assets';target.mkdir(parents=True,exist_ok=True)
                for f in (Path(td)/'assets').glob('*.png'):os.replace(f,target/f.name)
    print(json.dumps({'status':'validated' if a.check_only else 'installed','map_data_sha256':hashes,'rendered':a.render and not a.check_only},indent=2))
if __name__=='__main__':main()
