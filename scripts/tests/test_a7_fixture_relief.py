"""B-side relief/support layout: derived from validated native geometry, sourced heights only."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
SPEC = importlib.util.spec_from_file_location('fixture_r', ROOT / 'scripts/a7_fixture.py')
f = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(f)
rl = f.relief_design
GEOM = json.loads(f.native_geom.RECORD.read_text())['geometry']


def probes():
    return f.probe_map(f.bound_r4_placement(), f.BOARD.read_text())


def inside(inner, outer):
    return outer[0] <= inner[0] and outer[1] <= inner[1] and inner[2] <= outer[2] and inner[3] <= outer[3]


class ReliefTests(unittest.TestCase):
    def setUp(self):
        self.d = rl.design(GEOM, probes())

    def test_every_b_side_part_and_tht_lead_in_the_carrier_is_relieved(self):
        refs = {r['ref'] for r in self.d['reliefs']}
        for fp in GEOM['footprints']:
            if fp['ref'].startswith('TP'):
                continue
            for pd in fp['pads']:
                if (fp['side'] == 'B' or pd['attribute'] == 'PTH') and rl._clip(pd['bbox_mm']):
                    ref = fp['ref'] if fp['side'] == 'B' else f"{fp['ref']}.{pd['number']}"
                    self.assertIn(ref, refs)
                    box = next(r['board_box_mm'] for r in self.d['reliefs'] if r['ref'] == ref)
                    self.assertTrue(inside(rl._clip(pd['bbox_mm']), box), ref)

    def test_heights_are_sourced_or_unknown_never_invented(self):
        for r in self.d['reliefs']:
            if r['kind'] == 'pocket':
                self.assertEqual(r['height_class'], 'SOURCE_DERIVED')
                self.assertEqual(r['body_height_max_mm'], 0.55)
                self.assertAlmostEqual(r['depth_mm'], 0.55 + rl.RULES['pocket_depth_clearance_mm'])
                self.assertIsNone(r['solder_envelope_height_mm'])
            else:
                self.assertEqual(r['depth_mm'], rl.CARRIER_THICKNESS)
        self.assertEqual(self.d['unknown_heights'], ['J5 (PicoBlade 530470310): lead tail below the B face'])
        self.assertIsNone(rl.SOURCES['PicoBlade 530470310']['tail_length_below_b_face_mm'])

    def test_unclassified_b_side_part_rejected(self):
        g = copy.deepcopy(GEOM)
        next(fp for fp in g['footprints'] if fp['ref'] == 'R9')['fpid'] = 'LightBlock:C0603'
        with self.assertRaisesRegex(ValueError, 'height source'):
            rl.design(g, probes())
        pop = rl.population(); pop['R9'] = dict(pop['R9'], mpn='RC0603FR-0710KL')
        with self.assertRaisesRegex(ValueError, 'height source'):
            rl.design(GEOM, probes(), pop)

    def test_unclassified_through_hole_part_rejected(self):
        g = copy.deepcopy(GEOM)
        next(fp for fp in g['footprints'] if fp['ref'] == 'J5')['fpid'] = 'LightBlock:OTHER'
        with self.assertRaisesRegex(ValueError, 'through-hole'):
            rl.design(g, probes())

    def test_web_conflicts_are_reported_as_blockers(self):
        self.assertTrue(self.d['web_conflicts'])
        r = f.report()
        self.assertTrue(any('web below' in b for b in r['blockers']))
        self.assertFalse(r['fresh_native_verified'])
        self.assertFalse(r['digital_fixture_complete'])

    def test_moving_a_probe_onto_a_relief_is_detected(self):
        p = probes(); r9 = next(x for x in self.d['reliefs'] if x['ref'] == 'R9')['board_box_mm']
        p[0]['board_xy_mm'] = [r9[2] + 0.1, (r9[1] + r9[3]) / 2]
        d = rl.design(GEOM, p)
        self.assertTrue(any(w['web_mm'] < 0 for w in d['bore_to_relief_webs_below_2mm']))

    def test_carrier_coordinates_are_mirrored(self):
        for r in self.d['reliefs']:
            b, c = r['board_box_mm'], r['carrier_box_mm']
            self.assertAlmostEqual(c[0], 16.2 - b[2]); self.assertAlmostEqual(c[2], 16.2 - b[0])
            self.assertEqual((c[1], c[3]), (b[1], b[3]))

    def test_relief_includes_clearance_and_r12_edge_sliver(self):
        m = rl.RULES['smd_outline_clearance_mm']
        for r in self.d['reliefs']:
            fp = next((x for x in GEOM['footprints'] if x['ref'] == r['ref']), None)
            if fp and r['kind'] == 'pocket':
                for pd in fp['pads']:
                    want = rl._clip(rl._expand(pd['bbox_mm'], m))
                    if want:
                        self.assertTrue(inside(want, r['board_box_mm']), r['ref'])
        r12 = next(r for r in self.d['reliefs'] if r['ref'] == 'R12')
        self.assertEqual(r12['board_box_mm'][3], rl.CARRIER_Y[1])

    def test_unclassified_npth_and_f_side_b_copper_rejected(self):
        for ref, mutate, msg in (('J3', lambda fp: fp['pads'][0].update(attribute='NPTH'), 'NPTH'),
                                 ('U2', lambda fp: fp['pads'][0]['layers'].append('B.Cu'), 'B.Cu')):
            g = copy.deepcopy(GEOM); mutate(next(fp for fp in g['footprints'] if fp['ref'] == ref))
            with self.subTest(ref=ref), self.assertRaisesRegex(ValueError, msg):
                rl.design(g, probes())

    def test_dnp_or_non_orthogonal_b_side_part_rejected(self):
        pop = rl.population(); pop['R9'] = dict(pop['R9'], population='DNP')
        with self.assertRaisesRegex(ValueError, 'height source'):
            rl.design(GEOM, probes(), pop)
        g = copy.deepcopy(GEOM); next(fp for fp in g['footprints'] if fp['ref'] == 'R9')['rotation_deg'] = 45.0
        with self.assertRaisesRegex(ValueError, 'non-orthogonal'):
            rl.design(g, probes())

    def test_thin_walls_between_reliefs_are_blockers(self):
        self.assertIn('R6/R7 wall 0.175 mm', self.d['relief_wall_conflicts'])
        self.assertTrue(any('wall below' in b for b in f.report()['blockers']))

    def test_support_fractions_are_bounded_and_overhang_listed(self):
        s = self.d['support']
        self.assertTrue(0 < s['land_fraction'] < 1)
        self.assertEqual(set(s['land_fraction_within_radius_of_probe']), {'TP1', 'TP2', 'TP3', 'TP4', 'TP5'})
        self.assertIn('J1', self.d['overhang_not_checked']['refs'])

    def test_union_area(self):
        self.assertAlmostEqual(f.union_area([[0, 0, 2, 2], [1, 1, 3, 3]]), 7.0)
        self.assertEqual(f.union_area([]), 0.0)


if __name__ == '__main__':
    unittest.main()
