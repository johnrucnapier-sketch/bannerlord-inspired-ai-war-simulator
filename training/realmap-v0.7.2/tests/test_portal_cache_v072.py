"""Immutable portal caching must retain complete paths and fresh output lists."""
import importlib.util
import json
from pathlib import Path
import random
import unittest
from aiwar.real_map import Mesh

class PortalCacheV072(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=Path(__file__).resolve().parents[2]/'realmap-v0.7.1/aiwar/real_map.py'
        spec=importlib.util.spec_from_file_location('reference_v071_map',path)
        cls.old=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.old)
        cls.reference=cls.old.Mesh();cls.candidate=Mesh()

    def test_every_portal_transition_matches_original(self):
        m=self.candidate
        for current,face in m.faces.items():
            for previous in face['neighbors']:
                for following in face['neighbors']:
                    expected=self.old.local_path(m.polys[current],m.portals[previous,current],m.portals[current,following])
                    actual=m.portal_path(previous,current,following)
                    converted=None if actual is None else [list(point) for point in actual]
                    self.assertEqual(json.dumps(converted),json.dumps(expected))
                    if actual is not None:self.assertTrue(all(type(point) is tuple for point in actual))
        self.assertEqual(m.portal_path.cache_info().maxsize,8192)
        self.assertLessEqual(m.portal_path.cache_info().currsize,8192)

    def test_complete_routes_dynamic_coordinates_exclusions_and_output_mutation(self):
        rng=random.Random(702);ids=sorted(self.candidate.faces)
        for trial in range(120):
            start,goal=rng.sample(ids,2)
            sx,sy=self.candidate.centers[start];gx,gy=self.candidate.centers[goal]
            # Include non-integer dynamic endpoints: they are never cached.
            u={'x':sx+(0.25 if trial%2 else 0),'y':sy}
            x=gx+(0.5 if trial%3 else 0);y=gy
            cx,cy=self.candidate.centers[rng.choice(ids)]
            exclusion=(cx,cy,30000) if trial%2 else ()
            expected=self.reference.route(u,x,y,exclusion)
            actual=self.candidate.route(u,x,y,exclusion)
            self.assertEqual(json.dumps(actual),json.dumps(expected))
            if actual:
                actual[0][0]+=12345
                again=self.candidate.route(u,x,y,exclusion)
                self.assertEqual(json.dumps(again),json.dumps(expected))

if __name__=='__main__':unittest.main()
