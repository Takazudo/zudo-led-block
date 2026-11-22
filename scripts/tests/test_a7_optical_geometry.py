"""Optical export keeps polygon holes and nm-to-mm units (no envelope fallback)."""
import importlib.util
from pathlib import Path
import unittest
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location('optical', Path(__file__).parents[1] / 'a7_optical_geometry.py')
optical = importlib.util.module_from_spec(spec)
spec.loader.exec_module(optical)


class Chain:
    def __init__(self, points): self.points = points
    def PointCount(self): return len(self.points)
    def CPoint(self, i): return SimpleNamespace(x=self.points[i][0], y=self.points[i][1])


class Polygons:
    def OutlineCount(self): return 1
    def COutline(self, i): return Chain([(0, 0), (2000000, 0), (2000000, 3000000)])
    def HoleCount(self, i): return 1
    def CHole(self, i, j): return Chain([(200000, 200000), (400000, 200000), (400000, 400000)])


class OpticalGeometryTest(unittest.TestCase):
    def test_holes_and_units_preserved(self):
        result = optical.polygons(Polygons())
        self.assertEqual(result[0]['outer'], [[0, 0], [2, 0], [2, 3]])
        self.assertEqual(result[0]['holes'], [[[.2, .2], [.4, .2], [.4, .4]]])
        self.assertAlmostEqual(optical.area_mm2(result), 2.98)


if __name__ == '__main__': unittest.main()
