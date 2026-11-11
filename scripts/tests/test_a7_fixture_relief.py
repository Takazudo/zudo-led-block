"""B-side relief/support layout: derived from validated native geometry, sourced heights only."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
import unittest.mock

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

    def test_every_cut_is_through_and_heights_stay_sourced_or_unknown(self):
        for r in self.d['reliefs'] + self.d['bridges']:
            self.assertEqual(r['kind'], 'through')
            self.assertEqual(r['depth_mm'], rl.CARRIER_THICKNESS)
        self.assertEqual(self.d['unknown_heights'], ['J5 (PicoBlade 530470310): lead tail below the B face'])
        self.assertIsNone(rl.SOURCES['PicoBlade 530470310']['tail_length_below_b_face_mm'])
        self.assertFalse(self.d['fresh_native_criteria']['every_b_face_protrusion_sourced'])
        self.assertFalse(f.report()['fresh_native_verified'])

    def test_minimum_wall_is_derived_from_the_ingun_grid_and_hole(self):
        self.assertAlmostEqual(rl.MIN_WALL, 1.27 - 1.00)
        self.assertEqual(rl.RULES['minimum_fr4_wall_mm'], rl.MIN_WALL)

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

    def test_no_web_or_wall_below_the_minimum_and_none_in_blockers(self):
        self.assertEqual(self.d['web_conflicts'], [])
        self.assertEqual(self.d['relief_wall_conflicts'], [])
        self.assertTrue(all(w['web_mm'] >= rl.MIN_WALL for w in self.d['hole_to_cut_webs_below_2mm']))
        r = f.report()
        self.assertFalse(any('below the 0.27' in b for b in r['blockers']))
        self.assertFalse(r['digital_fixture_complete'])

    def test_moving_a_probe_onto_a_relief_is_detected(self):
        p = probes(); r9 = next(x for x in self.d['reliefs'] if x['ref'] == 'R9')['board_box_mm']
        p[0]['board_xy_mm'] = [r9[2] + 0.1, (r9[1] + r9[3]) / 2]
        d = rl.design(GEOM, p)
        self.assertTrue(any(w['web_mm'] < 0 for w in d['hole_to_cut_webs_below_2mm']))
        self.assertTrue(d['web_conflicts'])
        self.assertFalse(d['fresh_native_criteria']['no_wall_below_sourced_minimum'])

    def test_carrier_coordinates_are_mirrored(self):
        for r in self.d['reliefs']:
            b, c = r['board_box_mm'], r['carrier_box_mm']
            self.assertAlmostEqual(c[0], 16.2 - b[2]); self.assertAlmostEqual(c[2], 16.2 - b[0])
            self.assertEqual((c[1], c[3]), (b[1], b[3]))

    def test_relief_includes_clearance_and_thin_edge_walls_are_opened(self):
        lo = rl.RULES['smd_outline_clearance_min_near_bore_mm']
        for r in self.d['reliefs']:
            fp = next((x for x in GEOM['footprints'] if x['ref'] == r['ref']), None)
            if fp:
                for pd in fp['pads']:
                    want = rl._clip(rl._expand(pd['bbox_mm'], lo))
                    if want:
                        self.assertTrue(inside(want, r['board_box_mm']), r['ref'])
        r10 = next(r for r in self.d['reliefs'] if r['ref'] == 'R10')
        self.assertEqual(r10['board_box_mm'][1], rl.CARRIER_Y[0])
        self.assertIn('opened through the carrier edge', r10['opened_to_carrier_edge'])

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

    def test_thin_walls_between_reliefs_are_bridged(self):
        cuts = self.d['reliefs'] + self.d['bridges']
        groups = rl._components(cuts)
        idx = {c['ref']: i for i, c in enumerate(cuts)}
        self.assertEqual(groups[idx['R6']], groups[idx['R7']])
        for i in range(len(cuts)):
            for j in range(i + 1, len(cuts)):
                if groups[i] != groups[j]:
                    self.assertGreaterEqual(rl._box_gap(cuts[i]['board_box_mm'], cuts[j]['board_box_mm']), rl.MIN_WALL - 1e-9)

    def test_bridging_is_detected_when_removed(self):
        with unittest.mock.patch.object(rl, '_bridges', return_value=[]):
            d = rl.design(GEOM, probes())
        self.assertTrue(any('R6/R7 wall' in w for w in d['relief_wall_conflicts']))
        self.assertFalse(d['fresh_native_criteria']['no_wall_below_sourced_minimum'])

    def test_support_holddown_and_load_path(self):
        s = self.d['support']
        self.assertTrue(0 < s['land_fraction'] < 1)
        self.assertEqual(set(s['land_fraction_within_radius_of_probe']), {'TP1', 'TP2', 'TP3', 'TP4', 'TP5'})
        h = self.d['holddown']
        self.assertEqual(len(h['points_board_mm']), 3)
        self.assertAlmostEqual(h['required_clamp_force_N'], 5 * 1.27)
        self.assertIsNone(h['mechanism'])
        fside = [fp['courtyard_bbox_mm']['F'] for fp in GEOM['footprints'] if fp['side'] == 'F' and fp['courtyard_bbox_mm'].get('F')]
        cuts = self.d['reliefs'] + self.d['bridges']
        for x, y in h['points_board_mm']:
            self.assertTrue(all(rl._box_point_dist(b, (x, y)) >= 0.75 + 0.3 - 1e-9 for b in fside))
            self.assertTrue(all(rl._box_point_dist(c['board_box_mm'], (x, y)) >= 0.75 - 1e-9 for c in cuts))

    def test_keying_registration_and_stroke(self):
        k = self.d['keying']
        self.assertTrue(k['keyed'])
        self.assertIn('J1.1', k['blocking_features'])
        reg = self.d['registration']
        self.assertAlmostEqual(reg['radial_budget_mm'], 0.25)
        self.assertGreaterEqual(reg['worst_case_margin_mm'], 0)
        self.assertEqual(len(reg['acceptance_requirements']), 3)
        self.assertEqual(self.d['stroke']['stroke_window_mm'], [0.0, 6.35])
        for pin in self.d['datum_pins']:
            self.assertAlmostEqual(pin['carrier_xy_mm'][0], 16.2 - pin['board_xy_mm'][0])

    def test_completion_flags_follow_criteria(self):
        r = f.report()
        self.assertTrue(r['completion_criteria']['2_keying_and_registration']['met'])
        for k in ('1_native_support_and_relief', '3_stroke_stop_guide_fixing_insulation_wiring', '4_assembly_step_interference_check', '5_physical_tests'):
            self.assertFalse(r['completion_criteria'][k]['met'], k)
        self.assertEqual(r['status'], 'BLOCKED')
        with unittest.mock.patch.dict(rl.SOURCES['PicoBlade 530470310'], {'class': 'SOURCE_DERIVED'}):
            r2 = f.report()
        self.assertTrue(r2['fresh_native_verified'])
        self.assertFalse(r2['digital_fixture_complete'])

    def test_union_area(self):
        self.assertAlmostEqual(f.union_area([[0, 0, 2, 2], [1, 1, 3, 3]]), 7.0)
        self.assertEqual(f.union_area([]), 0.0)


if __name__ == '__main__':
    unittest.main()
