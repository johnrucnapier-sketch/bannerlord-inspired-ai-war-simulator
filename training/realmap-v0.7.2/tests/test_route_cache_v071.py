"""Exact-output regression against the preserved v0.7.0 route algorithm."""
import importlib.util
import random
import unittest
from pathlib import Path
from aiwar.real_map import Mesh


class RouteCacheV071(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        old = Path(__file__).resolve().parents[2] / 'realmap-v0.7.0/aiwar/real_map.py'
        spec = importlib.util.spec_from_file_location('frozen_v070_real_map', old)
        cls.legacy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.legacy)
        cls.mesh = Mesh()

    def test_exact_ordered_paths_with_and_without_exclusions(self):
        rng = random.Random(701)
        ids = sorted(self.mesh.faces)
        cases = [(ids[0], ids[0], ())]
        for _ in range(80):
            start, goal = rng.sample(ids, 2)
            cases.append((start, goal, ()))
            x, y = self.mesh.centers[rng.choice(ids)]
            cases.append((start, goal, (x, y, 30000)))
        for start, goal, exclusion in cases:
            with self.subTest(start=start, goal=goal, exclusion=exclusion):
                expected = self.legacy.Mesh.face_route.__wrapped__(self.mesh, start, goal, exclusion)
                actual = Mesh.face_route.__wrapped__(self.mesh, start, goal, exclusion)
                self.assertEqual(actual, expected)

    def test_all_cached_edge_values_and_neighbor_order_are_exact(self):
        import math
        for i, face in self.mesh.faces.items():
            expected = tuple((j, math.dist(self.mesh.centers[i], self.mesh.portals[i, j]) +
                              math.dist(self.mesh.portals[i, j], self.mesh.centers[j]))
                             for j in face['neighbors'])
            self.assertEqual(self.mesh.route_edges[i], expected)


if __name__ == '__main__':
    unittest.main()
