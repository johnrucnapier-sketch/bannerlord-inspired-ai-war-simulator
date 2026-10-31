import json, math, tempfile, unittest
from pathlib import Path
from aiwar.engine import World
from aiwar.real_map import mesh,within,ROOT
from aiwar.navigation import find_route
from aiwar.policies import decision_cycle
from aiwar.strategy_catalog import catalog

class RealMapTests(unittest.TestCase):
    def test_initial_and_ownership(self):
        w=World(7,{'mode':'realmap'});w.check()
        self.assertEqual((len(w.cities),len(w.villages),len(w.map_clans)),(29,63,18))
        for n,nc,nv in [(0,14,31),(1,15,32)]:
            self.assertEqual(sum(c['nation']==n for c in w.cities.values()),nc)
            self.assertEqual(sum(v['nation']==n for v in w.villages.values()),nv)
            self.assertEqual(sum(u['nation']==n and u['kind']=='party' for u in w.units.values()),27)
        sources={p['id']:p for p in json.loads((ROOT/'settlements.json').read_text())}
        for c in w.cities.values():
            self.assertEqual((c['map_x'],c['map_y']),(round(sources[c['id']]['x']*1000),round(sources[c['id']]['y']*1000)))
            self.assertEqual(w.clan_nation(c['clan']),c['nation'])
        for v in w.villages.values():self.assertEqual(v['city'],sources[v['id']]['parent_city'])
        self.assertTrue(any(c['nation']!=w.cities[j]['nation'] for c in w.cities.values() for j in c['neighbors']))

    def test_routes_preserve_bridges_and_block_water(self):
        w=World(7,{'mode':'realmap'});m=mesh()
        for v in w.villages.values():
            c=w.cities[v['city']];path=w.route(v,c['x'],c['y'])
            self.assertIsNotNone(path)
            old=(v['x'],v['y'])
            for q in path:
                # Sample every 0.25 game units, including both endpoints.
                count=max(1,math.ceil(math.dist(old,q)/250))
                for k in range(count+1):
                    x=round(old[0]+(q[0]-old[0])*k/count);y=round(old[1]+(q[1]-old[1])*k/count)
                    self.assertIsNotNone(m.face(x,y),(v['id'],old,q,x,y))
                old=q
        raw=json.loads((ROOT/'navigation.json').read_text())
        for f in raw['faces']:
            if f['bridge_overlay']:
                a,b=m.centers[f['id']],m.centers[m.faces[f['id']]['neighbors'][0]]
                self.assertIsNotNone(w.route(dict(x=a[0],y=a[1]),*b))
        self.assertIsNone(w.route(next(iter(w.cities.values())),500000,800000))
        # A real blocked polygon cannot become traversable merely because coordinates are in bounds.
        water=next(f for f in raw['faces'] if f['source_group']==19)
        p=[m.vertices[i] for i in water['vertices']]
        self.assertIsNone(m.face(round(sum(x for x,y in p)/len(p)),round(sum(y for x,y in p)/len(p))))

    def test_save_and_replay(self):
        w=World(23,{'mode':'realmap'})
        for _ in range(180):
            if w.hour%w.cfg['decision_hours']==0:decision_cycle(w,['march','march'])
            w.step();w.check()
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'state.json';w.save(p);loaded=World.load(p)
            self.assertEqual(w.physics_digest(),loaded.physics_digest())
            w.step(24);loaded.step(24);self.assertEqual(w.physics_digest(),loaded.physics_digest())
            replay=World(23,{'mode':'realmap'})
            for record in w.commands:
                if record['hour']<180:
                    while replay.hour<record['hour']:replay.step()
                    replay.command(record['nation'],record['command'])
            while replay.hour<180:replay.step()
            saved=World.load(p);self.assertEqual(saved.physics_digest(),replay.physics_digest())

    def test_clan_cap_and_capture(self):
        w=World(1,{'mode':'realmap'})
        c=next(c for c in w.cities.values() if c['nation']==0)
        self.assertGreaterEqual(c['clan'],9) # no hard-coded clan//6 nation mapping
        result=w.command(0,dict(type='create',city=c['id'],count=30,clan=0))
        self.assertFalse(result['ok'])
        target=next(c for c in w.cities.values() if c['nation']==1)
        clan=c['clan'];w.capture(target['id'],0,[clan],clan)
        self.assertEqual(w.cities[target['id']]['clan'],clan);w.check()
        self.assertFalse(any(r['external'] for r in catalog('realmap')))

if __name__=='__main__':unittest.main()
