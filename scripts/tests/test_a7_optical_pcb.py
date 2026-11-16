import importlib.util
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
SCRIPT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT))
from a7_optical_pcb import complement_rectangles, outside, spec, stackup_text
from a7_optical_check import check_board


class OpticalConstruction(unittest.TestCase):
    def test_opening_union_cannot_erase_overlapping_or_edge_protection(self):
        islands = [(2, 2, 4, 4), (3, 3, 6, 6), (-1, 7, 2, 11)]
        openings = complement_rectangles((0, 0, 10, 10), islands)
        self.assertEqual(sum((c-a)*(d-b) for a,b,c,d in openings), 82)
        for a,b,c,d in openings:
            for e,f,g,h in islands:
                self.assertFalse(a < g and c > e and b < h and d > f)
        for i, (a,b,c,d) in enumerate(openings):
            for e,f,g,h in openings[i+1:]:
                self.assertFalse(a < g and c > e and b < h and d > f)

    def test_empty_protection_opens_substrate_but_full_protection_does_not(self):
        self.assertEqual(complement_rectangles((0,0,10,10), []), [(0,0,10,10)])
        self.assertEqual(complement_rectangles((0,0,10,10), [(-1,-1,11,11)]), [])

    def test_no_canonical_board_write(self):
        with self.assertRaisesRegex(ValueError, 'staging'):
            outside(SCRIPT.parent / spec()['controller']['board'])
        with self.assertRaisesRegex(ValueError, 'staging'):
            outside(SCRIPT.parent / 'engineering/a5/electronics/native/led_leaf/led_leaf.kicad_pcb')

    def test_historical_leaf_cannot_pass_as_new_candidate(self):
        errors = check_board(SCRIPT.parent / 'engineering/a5/electronics/native/led_leaf/led_leaf.kicad_pcb', 'led_leaf')
        self.assertIn('nominal thickness must be 0.8mm', errors)
        self.assertIn('explicit native stackup missing', errors)
        self.assertIn('mask construction record missing', errors)

    def test_original_planes_are_detected(self):
        # This remains an independent immutable historical full-plane fixture: the
        # actual A5 controller has no routed planes, so use a minimally modified
        # source-contract specimen instead of assuming its geometry.
        import tempfile
        text = '''(kicad_pcb (general (thickness 0.8))
          (layers (0 "F.Cu" signal) (4 "In1.Cu" signal) (6 "In2.Cu" signal) (2 "B.Cu" signal))
          (setup %s)
          (zone (net 1) (net_name "/GND") (layer "In1.Cu")
          (polygon (pts (xy 0 0) (xy 16.2 0) (xy 16.2 62.9) (xy 0 62.9)))))''' % stackup_text('controller')
        with tempfile.TemporaryDirectory(prefix='a7-optical-negative-') as d:
            p = Path(d) / 'board.kicad_pcb'
            p.write_text(text)
            errors = check_board(p, 'controller')
            self.assertTrue(any('unjustified zone' in e for e in errors))

    def test_full_opening_cannot_override_via_tent_even_with_updated_hash(self):
        import hashlib
        import json
        import tempfile
        shapes = '\n'.join(f'(gr_rect (start 0 0) (end 10 10) (fill solid) (layer "{side}"))'
                           for side in ('F.Mask', 'B.Mask'))
        text = '''(kicad_pcb (general (thickness 0.8))
          (layers (0 "F.Cu" signal) (2 "B.Cu" signal)) (setup %s) %s
          (via (at 5 5) (size 0.5) (drill 0.2) (layers "F.Cu" "B.Cu") (uuid "actual-via")))''' % (stackup_text('led_leaf'), shapes)
        with tempfile.TemporaryDirectory(prefix='a7-mask-negative-') as d:
            p = Path(d) / 'board.kicad_pcb'
            p.write_text(text)
            side = {'protected': [{'id': 'via1', 'rect_nm': [4000000,4000000,6000000,6000000]}],
                    'open_rectangles_nm': [[0,0,10000000,10000000]]}
            (p.parent / 'optical-mask.json').write_text(json.dumps({
                'board_sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                'sides': {'F.Mask': side, 'B.Mask': side}}))
            errors = check_board(p, 'led_leaf')
            self.assertTrue(any('F.Mask opening overrides protected via1' in e for e in errors))
            self.assertTrue(any('B.Mask opening overrides protected via1' in e for e in errors))
            self.assertTrue(any('missing or altered native-derived protection actual-via' in e for e in errors))

    def test_graphical_mask_and_copper_cannot_bypass_zone_or_rectangle_checks(self):
        import tempfile
        additions = [('(gr_poly (pts (xy 0 0) (xy 10 0) (xy 10 10)) (fill yes) (layer "F.Mask"))',
                      'unsupported mask primitive gr_poly'),
                     ('(gr_circle (center 5 5) (end 10 5) (fill yes) (layer "B.Mask"))',
                      'unsupported mask primitive gr_circle'),
                     ('(gr_rect (start 0 0) (end 10 10) (fill yes) (layer "F.Cu"))',
                      'unsupported graphical copper gr_rect')]
        for extra, message in additions:
            with self.subTest(message=message), tempfile.TemporaryDirectory(prefix='a7-shape-negative-') as d:
                p = Path(d)/'board.kicad_pcb'
                p.write_text('(kicad_pcb (general (thickness 0.8)) '
                             '(layers (0 "F.Cu" signal) (2 "B.Cu" signal)) '
                             '(setup '+stackup_text('led_leaf')+') '+extra+')')
                self.assertTrue(any(message in e for e in check_board(p,'led_leaf')))

    def test_kicad10_zone_net_is_required(self):
        import tempfile
        with tempfile.TemporaryDirectory(prefix='a7-zone-net-negative-') as d:
            p = Path(d)/'board.kicad_pcb'
            p.write_text('(kicad_pcb (general (thickness 0.8)) '
                         '(layers (0 "F.Cu" signal) (4 "In1.Cu" signal) (6 "In2.Cu" signal) (2 "B.Cu" signal)) '
                         '(setup '+stackup_text('controller')+') '
                         '(zone (name "buck-return-thermal") (net "/VLED") (layer "B.Cu") '
                         '(polygon (pts (xy 4 0.4) (xy 8.8 0.4) (xy 8.8 4.9) (xy 4 4.9)))))')
            self.assertIn('local copper buck-return-thermal wrong net',check_board(p,'controller'))


if __name__ == '__main__':
    unittest.main()
