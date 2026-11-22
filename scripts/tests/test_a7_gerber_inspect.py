"""Plotted-geometry review: signed distances, pad mapping, and a real Gerber via-tent override.

The Gerbonara path only runs where the pinned export tool chain is installed
(engineering/a7/verification/optical/tools/requirements.lock); everything else is stdlib.
"""
import importlib.util
import math
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('gerber_inspect', ROOT / 'scripts/a7_gerber_inspect.py')
INSPECT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSPECT)
HAVE_GERBONARA = importlib.util.find_spec('gerbonara') is not None


class Circle:
    def __init__(self, x, y, r):
        self.x, self.y, self.r = x, y, r


class Rectangle:
    def __init__(self, x, y, w, h, rotation=0.0):
        self.x, self.y, self.w, self.h, self.rotation = x, y, w, h, rotation


class Line:
    def __init__(self, x1, y1, x2, y2, width):
        self.x1, self.y1, self.x2, self.y2, self.width = x1, y1, x2, y2, width


class ArcPoly:
    def __init__(self, outline, arcs=None):
        self.outline = outline
        self.arc_centers = arcs if arcs is not None else [None] * len(outline)


class Cross:
    pass


class SignedDistance(unittest.TestCase):
    def test_each_supported_primitive_is_negative_inside_and_exact_outside(self):
        circle = INSPECT.Shape(Circle(5, 5, .25))
        self.assertAlmostEqual(circle.distance(5, 5), -.25, places=12)
        self.assertAlmostEqual(circle.distance(5.5, 5), .25, places=12)
        line = INSPECT.Shape(Line(0, 0, 4, 0, .3))
        self.assertAlmostEqual(line.distance(2, .4), .25, places=12)
        self.assertAlmostEqual(line.distance(2, 0), -.15, places=12)
        self.assertAlmostEqual(line.distance(5, 0), .85, places=12)
        rect = INSPECT.Shape(Rectangle(0, 0, 2, 1))
        self.assertAlmostEqual(rect.distance(1.5, 0), .5, places=12)
        self.assertAlmostEqual(rect.distance(0, 0), -.5, places=12)
        turned = INSPECT.Shape(Rectangle(0, 0, 2, 2, math.pi / 4))      # diagonal corner at sqrt(2)
        self.assertAlmostEqual(turned.distance(math.sqrt(2) + 1, 0), 1, places=12)
        poly = INSPECT.Shape(ArcPoly([(0, 0), (3, 0), (3, 3), (0, 3), (0, 0)]))
        self.assertAlmostEqual(poly.distance(1.5, 1.5), -1.5, places=12)
        self.assertAlmostEqual(poly.distance(4, 1.5), 1, places=12)

    def test_unreviewable_primitives_are_refused_rather_than_approximated(self):
        with self.assertRaisesRegex(ValueError, 'arcs is not supported'):
            INSPECT.Shape(ArcPoly([(0, 0), (3, 0), (3, 3)], [None, (1, 1), None]))
        with self.assertRaisesRegex(ValueError, 'unsupported plotted primitive Cross'):
            INSPECT.Shape(Cross())

    def test_mask_opening_edge_gives_the_same_web_as_the_review_arithmetic(self):
        # a 0.5 mm via and an opening edge 0.3 mm away leaves 0.05 mm of web, under the 0.1 mm rule
        opening = INSPECT.Shape(Rectangle(5.65, 5, .7, 1))
        buckets = INSPECT.Buckets([opening])
        gap = min(s.distance(5, 5) for s in buckets.near(5, 5, .36)) - .25
        self.assertAlmostEqual(gap, .05, places=12)
        self.assertLess(gap, .1)
        self.assertTrue(buckets.covered(5.65, 5))
        self.assertFalse(buckets.covered(5, 5))
        self.assertEqual(buckets.near(0, 0, .5), [])


BOARD = '''(kicad_pcb (general (thickness 0.8))
  (layers (0 "F.Cu" signal) (2 "B.Cu" signal))
  (gr_line (start 0 0) (end 12 0) (layer "Edge.Cuts"))
  (gr_line (start 12 0) (end 12 9) (layer "Edge.Cuts"))
  (gr_line (start 0 0) (end 0 9) (layer "Edge.Cuts"))
  (gr_line (start 0 9) (end 12 9) (layer "Edge.Cuts"))
  (gr_line (start 1 1) (end 2 2) (layer "F.SilkS"))
  (footprint "R_0603" (at 8 4 90) (property "Reference" "R7")
    (pad "1" smd roundrect (at -0.7875 0.25) (size 0.9 0.95) (layers "F.Cu" "F.Paste" "F.Mask"))
    (pad "2" smd roundrect (at 0.7875 0.25) (size 0.9 0.95) (layers "F.Cu" "F.Paste" "F.Mask")))
  (via (at 5 5) (size 0.5) (drill 0.2) (net 1) (layers "F.Cu" "B.Cu") (uuid "v1"))
)'''


class BoardItems(unittest.TestCase):
    def board(self, directory):
        path = Path(directory) / 'board.kicad_pcb'
        path.write_text(BOARD)
        return path

    def test_pads_follow_the_footprint_rotation_and_outline_ignores_silkscreen(self):
        with tempfile.TemporaryDirectory(prefix='a7-inspect-board-') as d:
            vias, pads, bounds = INSPECT.board_items(self.board(d))
            self.assertEqual(bounds, (0, 0, 12, 9))
            self.assertEqual([v['uuid'] for v in vias], ['v1'])
            self.assertEqual((vias[0]['x'], vias[0]['y'], vias[0]['size'], vias[0]['net']), (5, 5, .5, '1'))
            # at 90 degrees KiCad maps a local (u, v) to (x + v, y - u)
            self.assertEqual({p['id']: (round(p['x'], 4), round(p['y'], 4)) for p in pads},
                             {'R7.1': (8.25, 4.7875), 'R7.2': (8.25, 3.2125)})
            self.assertEqual(pads[0]['layers'], ['F.Cu', 'F.Paste', 'F.Mask'])


GERBER = '''%FSLAX46Y46*%
%MOMM*%
%TF.FileFunction,Soldermask,Top*%
%TF.FilePolarity,Negative*%
%ADD10C,{diameter:f}*%
D10*
X{x:d}Y{y:d}D03*
M02*
'''


@unittest.skipUnless(HAVE_GERBONARA, 'gerbonara (optical export tool chain) not installed')
class PlottedFiles(unittest.TestCase):
    def run_case(self, offset_mm):
        temp = tempfile.TemporaryDirectory(prefix='a7-inspect-gerber-')
        self.addCleanup(temp.cleanup)
        d = Path(temp.name)
        (d / 'board.kicad_pcb').write_text(BOARD)
        (d / 'gerbers').mkdir()
        # Gerber Y is the board Y mirrored, so the via at (5, 5) sits at (5, -5) here.
        (d / 'gerbers/board-F_Mask.gts').write_text(GERBER.format(
            diameter=.4, x=round((5 + offset_mm) * 1e6), y=round(-5 * 1e6)))
        return INSPECT.inspect(d / 'board.kicad_pcb', d / 'gerbers', d / 'out', .1, 10), d / 'out'

    def test_pad_opening_over_a_via_is_caught_in_the_plotted_mask(self):
        report, out = self.run_case(0)
        row = report['layers']['board-F_Mask.gts']['via_tent']
        self.assertEqual(row['checked'], 1)
        self.assertAlmostEqual(row['smallest_mask_web_to_via_copper_mm'], -.45, places=4)
        self.assertEqual([e['via'] for e in row['exposed_or_under_web']], ['v1'])
        self.assertEqual(report['failures'], ['board-F_Mask.gts: 1 via tents overridden or closer than 0.1 mm to an opening'])
        self.assertTrue((out / 'overview.png').is_file())
        self.assertEqual((report['board'], report['via_count'], report['via_web_mm']), ('board.kicad_pcb', 1, .1))

    def test_opening_clear_of_the_via_passes(self):
        report, _ = self.run_case(.6)
        row = report['layers']['board-F_Mask.gts']['via_tent']
        self.assertAlmostEqual(row['smallest_mask_web_to_via_copper_mm'], .15, places=4)
        self.assertEqual(row['exposed_or_under_web'], [])
        self.assertEqual(report['failures'], [])


if __name__ == '__main__':
    unittest.main()
