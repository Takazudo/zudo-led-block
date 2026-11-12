"""Fixture design: derived from validated native geometry, sourced heights only, checked against the 1.0 mm yardstick."""
import copy
import importlib.util
import json
import math
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
DESIGN = None


def probes():
    return f.probe_map(f.bound_r4_placement(), f.BOARD.read_text())


def design():
    global DESIGN
    if DESIGN is None:
        DESIGN = rl.design(GEOM, probes())
    return copy.deepcopy(DESIGN)


def inside(inner, outer):
    return outer[0] <= inner[0] + 1e-9 and outer[1] <= inner[1] + 1e-9 and inner[2] <= outer[2] + 1e-9 and inner[3] <= outer[3] + 1e-9


def members(windows):
    return [(m, w['corner_radius_mm']) for w in windows for m in w['members']]


def rounded_pieces(m, r):
    """A member with flagged rounded corners as three rectangles plus corner discs (exact union)."""
    x0, y0, x1, y1 = m['box_board_mm']
    bl, br, tl, tr = [r if q else 0.0 for q in m['rounded_corners']]
    rects = [[x0 + bl, y0, x1 - br, y0 + r], [x0, y0 + r, x1, y1 - r], [x0 + tl, y1 - r, x1 - tr, y1]]
    discs = [((cx, cy), r) for (cx, cy), q in zip(((x0 + r, y0 + r), (x1 - r, y0 + r), (x0 + r, y1 - r), (x1 - r, y1 - r)), m['rounded_corners']) if q]
    return rects, discs


class ReliefTests(unittest.TestCase):
    def setUp(self):
        self.d = design()

    def test_every_b_side_part_and_tht_lead_lies_in_a_carrier_window(self):
        boxes = [m['box_board_mm'] for m, _ in members(self.d['support_carrier']['windows'])]
        refs = {r['ref'] for r in self.d['reliefs']}
        for fp in GEOM['footprints']:
            if fp['ref'].startswith('TP'):
                continue
            for pd in fp['pads']:
                want = rl._clip(pd['bbox_mm'], self.d['support_carrier']['bounds_board_mm'])
                if (fp['side'] == 'B' or pd['attribute'] == 'PTH') and want:
                    ref = fp['ref'] if fp['side'] == 'B' else f"{fp['ref']}.{pd['number']}"
                    self.assertIn(ref, refs)
                    self.assertTrue(any(inside(want, b) for b in boxes), ref)
        for p in probes():
            box = rl._expand(list(p['board_xy_mm']) * 2, rl.RULES['probe_window_half_width_mm'])
            self.assertTrue(any(inside(box, b) for b in boxes), p['ref'])

    def test_j5_tail_follows_the_component_fact(self):
        bundle = ROOT / '.claude/skills/component-530470310'
        fact = next(x for x in json.loads((bundle / 'facts.json').read_text())['facts'] if x['fact_id'] == 'fact-530470310-tail-length')
        src = next(x for x in json.loads((bundle / 'sources.json').read_text())['sources'] if x['source_id'] == fact['source_id'])
        j5 = rl.SOURCES['PicoBlade 530470310']
        self.assertEqual(j5['tail_length_below_seating_plane_mm'], fact['value'])
        self.assertIn('+/-0.5', fact['conditions'])
        self.assertEqual(j5['tolerance_mm'], 0.5)
        self.assertEqual(j5['source']['fact_id'], fact['fact_id'])
        self.assertEqual(j5['source']['sha256'], src['sha256'])
        self.assertTrue(fact['verdict'].startswith('PASS'))

    def test_heights_all_sourced_and_tails_bounded(self):
        self.assertEqual(self.d['unknown_heights'], [])
        self.assertTrue(self.d['fresh_native_criteria']['every_b_face_protrusion_sourced'])
        self.assertTrue(self.d['fresh_native_criteria']['every_tht_lead_ends_inside_its_carrier_window'])
        j5 = [r for r in self.d['reliefs'] if r['ref'].startswith('J5.')]
        self.assertTrue(j5 and all(r['depth_below_b_face_mm'] == 2.8 for r in j5))
        tails = {t['source']: t for t in self.d['lead_tails']}
        t = tails['PicoBlade 530470310']
        self.assertEqual(t['protrusion_worst_case_at_nominal_board_mm'], 1.2)
        self.assertEqual(t['protrusion_bound_any_board_thickness_mm'], 2.8)
        self.assertAlmostEqual(t['margin_to_carrier_bottom_mm'], 2.2)
        self.assertTrue(all(x['ends_inside_carrier_window'] and x['margin_to_carrier_bottom_mm'] > 0 for x in tails.values()))
        self.assertEqual(tails['PJ-324M']['protrusion_bound_any_board_thickness_mm'], 3.4)

    def test_a_tail_longer_than_the_carrier_fails_criterion_1(self):
        with unittest.mock.patch.dict(rl.SOURCES['PicoBlade 530470310'], {'tail_length_below_seating_plane_mm': 4.6}):
            d = rl.design(GEOM, probes())
        self.assertFalse(d['fresh_native_criteria']['every_tht_lead_ends_inside_its_carrier_window'])

    def test_plunger_compression_covers_the_stack_and_board_extremes(self):
        h = self.d['holddown']
        pl, c = rl.PLUNGER_CANDIDATE, h['plunger_compression_mm']
        # board +/-0.16 (1.44-1.76 mm), stop length +/-0.05, plunger setting +/-0.1; 0.2 mm kept from the stroke end
        self.assertEqual(c['board_thickness_range_mm'], [1.44, 1.76])
        self.assertAlmostEqual(sum(c['stack_mm'].values()), 0.31)
        self.assertAlmostEqual(c['nominal'], pl['stroke_mm'] - 0.2 - 0.31)
        self.assertAlmostEqual(c['range'][1], c['nominal'] + 0.31)
        self.assertAlmostEqual(c['range'][0], c['nominal'] - 0.31 - c['plate_deflection_mm'] - c['board_sag_under_plungers_mm'])
        self.assertGreater(c['plate_deflection_mm'], 0)
        self.assertGreater(c['board_sag_under_plungers_mm'], 0)
        self.assertGreater(c['range'][0], 0)
        self.assertLessEqual(c['range'][1], pl['stroke_mm'] - 0.2 + 1e-9)
        # the setting puts the free pin tip at the nominal compression on the nominal board
        self.assertAlmostEqual(rl.STACK['pressure_plate'][0] - h['plunger_setting_mm']['free_pin_tip_below_plate_underside'], 1.6 - c['nominal'])

    def test_plunger_forces_are_bounded_at_every_worst_case(self):
        h = self.d['holddown']
        pl, (d_min, d_max) = rl.PLUNGER_CANDIDATE, h['plunger_compression_mm']['range']
        line = lambda d: pl['force_initial_N'] + (pl['force_final_N'] - pl['force_initial_N']) * d / pl['stroke_mm']
        band = rl.RULES['plunger_force_acceptance_band']
        self.assertAlmostEqual(h['plunger_force_each_N'][0], line(d_min) * (1 - band), places=5)
        self.assertAlmostEqual(h['plunger_force_each_N'][1], line(d_max) * (1 + band), places=5)
        k = len(h['contacts_board_mm'])
        self.assertEqual(h['total_force_N'], [round(k * x, 6) for x in h['plunger_force_each_N']])
        self.assertAlmostEqual(h['required_total_force_N'], 2 * 5 * 1.27)
        self.assertGreaterEqual(h['total_force_N'][0], h['required_total_force_N'])
        cand = h['plunger_candidate']
        self.assertTrue(cand['meets_requirement'], cand['checks'])
        self.assertIn('AWAITING_OWNER_APPROVAL', cand['status'])
        self.assertIn('POM', cand['description'])
        # the light-force series of the same leaf (2-7 N) cannot reach the required total on the free F-face area
        with unittest.mock.patch.dict(rl.PLUNGER_CANDIDATE, {'force_initial_N': 2.0, 'force_final_N': 7.0}):
            with self.assertRaisesRegex(ValueError, 'required total force'):
                rl.design(GEOM, probes())

    def test_a_short_body_end_clearance_fails_the_plunger_checks(self):
        with unittest.mock.patch.dict(rl.RULES, {'plunger_body_end_clearance_min_mm': 0.3}):
            d = rl.design(GEOM, probes())
        self.assertFalse(d['holddown']['plunger_candidate']['meets_requirement'])
        self.assertFalse(d['criterion_3_checks']['plungers_within_stroke'])

    def test_bending_is_checked_at_the_minimum_board_thickness_and_within_the_limit(self):
        b = self.d['holddown']['board_bending_across_window']
        self.assertAlmostEqual(b['board_thickness_minimum_mm'], 1.44)
        t, e, w = b['board_thickness_minimum_mm'], b['flexural_modulus_MPa'], b['strip_width_mm']
        defl = lambda f_, L: f_ * L ** 3 / (48 * e * w * t ** 3 / 12)
        # the plungers press over the window (real unsupported spans), so the bending check is not trivially zero
        self.assertTrue(any(L > 0 for L in b['plunger_spans_mm']))
        self.assertEqual(set(b['plunger_span_kinds'] + b['probe_span_kinds']) - {'on_land', 'simply_supported', 'cantilever'}, set())
        hi = self.d['holddown']['plunger_force_each_N'][1]
        self.assertAlmostEqual(b['plunger_load_N'], hi * sum(L > 0 for L in b['plunger_spans_mm']), places=5)
        self.assertAlmostEqual(b['deflection_under_plungers_mm'], defl(b['plunger_load_N'], max(b['plunger_spans_mm'])), places=5)
        self.assertAlmostEqual(b['deflection_under_probes_mm'], defl(b['probe_load_N'], max(b['probe_spans_mm'])), places=5)
        self.assertEqual(b['deflection_mm'], max(b['deflection_under_plungers_mm'], b['deflection_under_probes_mm']))
        self.assertLessEqual(b['deflection_mm'], b['limit_mm'])
        self.assertLessEqual(b['deflection_at_lowest_sourced_modulus_mm'], b['limit_mm'])
        self.assertIn('ASSUMED', b['flexural_modulus_class'])
        self.assertIn('do not bound', b['flexural_modulus_class'])
        self.assertTrue(self.d['criterion_3_checks']['board_bending_across_window_within_limit'])
        with unittest.mock.patch.dict(rl.RULES, {'board_deflection_limit_mm': 0.02}):
            self.assertFalse(rl.design(GEOM, probes())['criterion_3_checks']['board_bending_across_window_within_limit'])

    def test_span_is_the_unsupported_chord_not_the_window_box(self):
        b = self.d['holddown']['board_bending_across_window']
        for L in b['plunger_spans_mm'] + b['probe_spans_mm']:
            self.assertLess(L, 62.9)

    def test_board_span_handles_free_board_edges(self):
        # land everywhere except a hole x 4-12, y 20-30 (simply supported both ways)
        hole = lambda x, y: not (4 < x < 12 and 20 < y < 30)
        L, kind = rl.board_span(hole, (8.0, 25.0))
        self.assertEqual(kind, 'simply_supported')
        self.assertAlmostEqual(L, 10.0, delta=0.05)
        # the same hole opened to the x = 16.2 board edge: a cantilever of 4 mm from x = 4, taken as 16^(1/3) x 4
        edge = lambda x, y: not (4 < x and 20 < y < 30)
        L, kind = rl.board_span(edge, (8.0, 25.0))
        self.assertEqual(kind, 'cantilever')
        self.assertAlmostEqual(L, 16 ** (1 / 3) * 4.0, delta=0.1)
        self.assertEqual(rl.board_span(lambda x, y: False, (8.0, 25.0)), (math.inf, 'unsupported'))
        self.assertEqual(rl.board_span(lambda x, y: True, (8.0, 25.0)), (0.0, 'on_land'))

    def test_stop_screws_hold_the_plate_against_the_plunger_moment(self):
        h = self.d['holddown']
        sj, ys = h['stop_joint'], h['stop_line_y_mm']
        pivot = ys + rl.RULES['m3_hex_across_flats_mm'] / 2
        hi = h['plunger_force_each_N'][1]
        want = sum(hi * abs(pivot - q[1]) for q in h['contacts_board_mm']) / (pivot - ys)
        self.assertAlmostEqual(sj['required_screw_tension_total_N'], want, places=4)
        self.assertTrue(sj['holds'])
        self.assertIn(f"{rl.RULES['stop_screw_torque_N_m']} N m", h['operation'])
        with unittest.mock.patch.dict(rl.RULES, {'stop_screw_torque_N_m': 0.01}):
            self.assertFalse(rl.design(GEOM, probes())['criterion_3_checks']['stop_joint_preload_holds_plate'])

    def test_plunger_acceptance_measures_both_compression_ends(self):
        h = self.d['holddown']
        lo, hi = h['plunger_compression_mm']['range']
        self.assertIn(f'{lo} and {hi} mm', h['plunger_acceptance'])
        self.assertIn('protrusion', h['plunger_acceptance'])

    def test_tapped_hole_webs_are_measured_at_the_thread_major_diameter(self):
        h, pr = self.d['holddown'], self.d['pressure_plate']
        a, b = h['contacts_board_mm']
        self.assertGreaterEqual(math.dist(a, b) - h['plunger_body_diameter_mm'], rl.MIN_WALL - 1e-9)
        self.assertEqual(pr['web_conflicts'], [])
        self.assertTrue(all(w['web_mm'] >= rl.MIN_WALL - 1e-9 for w in pr['smallest_webs']))
    def test_yardstick_and_sourced_minimums(self):
        ref = json.loads((f.OUT / 'candidate-references.json').read_text())['references'][0]
        self.assertEqual(rl.MIN_WALL, ref['rules_used']['wall_absolute_minimum_mm'])
        self.assertEqual(rl.MIN_WALL, 1.0)
        self.assertAlmostEqual(rl.INGUN_HOLE_WEB, 1.27 - 1.00)
        self.assertEqual(self.d['support_carrier']['corner_radius_mm'], rl.CARRIER_THICKNESS / 10 + 0.5)
        self.assertEqual(self.d['probe_plate']['corner_radius_mm'], 6.0 / 10 + 0.5)
        self.assertEqual(self.d['yardstick']['selection_status'], 'NOT_SELECTED')

    def test_unclassified_b_side_part_rejected(self):
        g = copy.deepcopy(GEOM)
        next(fp for fp in g['footprints'] if fp['ref'] == 'R9')['fpid'] = 'LightBlock:C0603'
        with self.assertRaisesRegex(ValueError, 'height source'):
            rl.design(g, probes())
        pop = rl.population(); pop['R9'] = dict(pop['R9'], mpn='RC0603FR-0710KL')
        with self.assertRaisesRegex(ValueError, 'height source'):
            rl.design(GEOM, probes(), pop)

    def test_unclassified_through_hole_npth_and_b_copper_rejected(self):
        g = copy.deepcopy(GEOM)
        next(fp for fp in g['footprints'] if fp['ref'] == 'J5')['fpid'] = 'LightBlock:OTHER'
        with self.assertRaisesRegex(ValueError, 'through-hole'):
            rl.design(g, probes())
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

    def test_no_wall_or_web_below_the_minimum_on_any_plate(self):
        sc, pp, pr, bp = (self.d[k] for k in ('support_carrier', 'probe_plate', 'pressure_plate', 'base_plate'))
        self.assertEqual((sc['web_conflicts'], sc['wall_conflicts'], pp['conflicts'], pr['web_conflicts'], bp['web_conflicts']), ([], [], [], [], []))
        for webs in (sc['smallest_webs'], pp['smallest_webs'], pr['smallest_webs'], bp['smallest_webs']):
            self.assertTrue(all(w['web_mm'] >= rl.MIN_WALL - 1e-9 for w in webs))
        self.assertTrue(self.d['fresh_native_criteria']['no_wall_below_minimum'])

    def test_no_sharp_corner_is_left_against_a_rounded_neighbour(self):
        for w in self.d['support_carrier']['windows'] + self.d['probe_plate']['windows']:
            boxes = [m['box_board_mm'] for m in w['members']]
            self.assertEqual(rl._uncovered_sharp_corners(boxes, w['corner_radius_mm']), [])

    def test_raster_sees_a_flake_at_a_sharp_corner(self):
        with unittest.mock.patch.object(rl, '_uncovered_sharp_corners', return_value=[]):
            d = rl.design(GEOM, probes())
        win = next(w for w in d['support_carrier']['windows'] if 'R5' in w['parts'])
        self.assertTrue(rl._uncovered_sharp_corners([m['box_board_mm'] for m in win['members']], win['corner_radius_mm']))
        self.assertTrue(self.thin_points(d, only=win))

    def test_members_are_millable(self):
        for m, r in members(self.d['support_carrier']['windows']) + members(self.d['probe_plate']['windows']):
            b = m['box_board_mm']
            self.assertGreaterEqual(min(b[2] - b[0], b[3] - b[1]), 2 * r - 1e-9, m['ref'])

    def test_datum_pin_near_the_probe_window_is_detected(self):
        pins = [('X1', 'moved next to the probe window', (17.2, 26.0))] + rl.DATUM_PINS[1:]
        with unittest.mock.patch.object(rl, 'DATUM_PINS', pins):
            d = rl.design(GEOM, probes())
        self.assertTrue(any(c.startswith('X1') for c in d['support_carrier']['web_conflicts']))
        self.assertFalse(d['fresh_native_criteria']['no_wall_below_minimum'])

    def test_probe_bores_meet_the_ingun_grid_and_stay_off_the_j5_window(self):
        pp = self.d['probe_plate']
        self.assertEqual(pp['bore_webs_mm'][0], 0.4)
        self.assertGreaterEqual(pp['bore_webs_mm'][0], rl.INGUN_HOLE_WEB)
        p = probes(); p[0]['board_xy_mm'] = [11.6, 27.5]
        d = rl.design(GEOM, p)
        self.assertTrue(any('J5 window' in c for c in d['probe_plate']['conflicts']))

    def test_window_coordinates_are_mirrored(self):
        for m, _ in members(self.d['support_carrier']['windows']):
            b, c = m['box_board_mm'], m['box_carrier_mm']
            self.assertAlmostEqual(c[0], 16.2 - b[2]); self.assertAlmostEqual(c[2], 16.2 - b[0])
            self.assertEqual((c[1], c[3]), (b[1], b[3]))

    def test_independent_raster_finds_no_carrier_material_thinner_than_the_minimum(self):
        self.assertEqual(self.thin_points(self.d), [])

    def test_raster_sees_a_wall_left_by_a_missing_bridge(self):
        d = copy.deepcopy(self.d)
        win = next(w for w in d['support_carrier']['windows'] if any(m['ref'].startswith('bridge') for m in w['members']))
        bridges = [m for m in win['members'] if m['ref'].startswith('bridge')]
        win['members'] = [m for m in win['members'] if not m['ref'].startswith('bridge')]
        self.assertTrue(bridges)
        self.assertTrue(self.thin_points(d, only=win))

    def thin_points(self, d, only=None):
        """Grid opening near every window: each solid point must lie in a disc or an axis-aligned square of the minimum wall.

        The disc catches walls next to round holes and rounded corners; the square keeps the sharp re-entrant corners where
        members overlap, which a disc would round off. A wall thinner than the minimum fits neither. Every material grid point
        (0.05 mm) is tested, including those right at an opening, so flakes thinner than the grid are seen too; walls below
        about 0.9 mm are caught here and the exact 1.0 mm limit is the analytic wall/web check.
        """
        sc = d['support_carrier']
        x0, y0, x1, y1 = sc['bounds_board_mm']
        rects, discs = [], []
        for m, r in members(sc['windows']):
            a, b = rounded_pieces(m, r)
            rects += a; discs += b
        r_csk = rl.RULES['m3_countersink_diameter_mm'] / 2
        discs += [(q['board_xy_mm'], rl.RULES['datum_pin_diameter_mm'] / 2) for q in sc['datum_pins']]
        discs += [(xy, r_csk) for xy in sc['fasteners_board_mm']] + [(xy, 1.0) for xy in sc['alignment_dowels_board_mm']]
        discs += [(g['board_xy_mm'], rl.RULES['m3_clearance_hole_mm'] / 2) for g in sc['guides']]
        h, rad = 0.05, rl.MIN_WALL / 2 - 0.05
        cell = 1.0
        buckets = {}
        for b in rects:
            for cx in range(math.floor((b[0] - 2) / cell), math.floor((b[2] + 2) / cell) + 1):
                for cy in range(math.floor((b[1] - 2) / cell), math.floor((b[3] + 2) / cell) + 1):
                    buckets.setdefault((cx, cy), [[], []])[0].append(b)
        for c, rr in discs:
            for cx in range(math.floor((c[0] - rr - 2) / cell), math.floor((c[0] + rr + 2) / cell) + 1):
                for cy in range(math.floor((c[1] - rr - 2) / cell), math.floor((c[1] + rr + 2) / cell) + 1):
                    buckets.setdefault((cx, cy), [[], []])[1].append((c, rr))
        cache = {}

        def clear(i, j, square):
            """Disc mode: distance to the nearest opening or edge. Square mode: whether the square of half-side rad fits."""
            key = (i, j, square)
            if key in cache:
                return cache[key]
            x, y = i * h, j * h
            rs, ds = buckets.get((math.floor(x / cell), math.floor(y / cell)), ([], []))
            if square:
                s = rad
                ok = min(x - x0, x1 - x, y - y0, y1 - y) >= s
                ok = ok and all(max(b[0] - x, x - b[2]) >= s or max(b[1] - y, y - b[3]) >= s for b in rs)
                ok = ok and all(math.hypot(max(abs(c[0] - x) - s, 0.0), max(abs(c[1] - y) - s, 0.0)) >= rr for c, rr in ds)
                cache[key] = ok
                return ok
            dist = min(x - x0, x1 - x, y - y0, y1 - y)
            for b in rs:
                if b[0] < x < b[2] and b[1] < y < b[3]:
                    dist = -1.0
                    break
                dist = min(dist, math.hypot(max(b[0] - x, 0.0, x - b[2]), max(b[1] - y, 0.0, y - b[3])))
            else:
                for c, rr in ds:
                    dist = min(dist, math.dist((x, y), c) - rr)
            cache[key] = dist
            return dist
        k = math.ceil(rad / h) + 1
        disc = [(a, c, math.hypot(a * h, c * h)) for a in range(-k, k + 1) for c in range(-k, k + 1) if math.hypot(a * h, c * h) <= rad + h]
        sq = [(a, c) for a in range(-k, k + 1) for c in range(-k, k + 1) if max(abs(a), abs(c)) * h <= rad]
        thin = set()
        scan = [m for m, _ in members([only] if only else sc['windows'])]
        for m in scan:
            b = m['box_board_mm']
            for i in range(math.floor((b[0] - rl.MIN_WALL) / h), math.ceil((b[2] + rl.MIN_WALL) / h) + 1):
                for j in range(math.floor((b[1] - rl.MIN_WALL) / h), math.ceil((b[3] + rl.MIN_WALL) / h) + 1):
                    x, y = i * h, j * h
                    if not (x0 < x < x1 and y0 < y < y1) or clear(i, j, False) <= 0:
                        continue
                    # covered by a disc of radius >= rad that fits in the material, or by a fitting square of half-side rad
                    if not any(clear(i + a, j + c, False) >= max(rad, dd - h / 2) for a, c, dd in disc) and not any(clear(i + a, j + c, True) for a, c in sq):
                        thin.add((round(x, 3), round(y, 3)))
        return sorted(thin)

    def test_plungers_on_free_f_face_in_plate_material(self):
        h = self.d['holddown']
        self.assertEqual(len(h['contacts_board_mm']), 2)
        fside = [fp['courtyard_bbox_mm']['F'] for fp in GEOM['footprints'] if fp['side'] == 'F' and fp['courtyard_bbox_mm'].get('F')]
        r_body = r_tap = h['plunger_body_diameter_mm'] / 2  # webs at the M4 thread major diameter
        notch = self.d['pressure_plate']['j5_notch_board_mm']
        x0, y0, x1, y1 = rl.PRESSURE_PLATE
        for x, y in h['contacts_board_mm']:
            self.assertTrue(all(rl._box_point_dist(b, (x, y)) >= r_body + rl.RULES['contact_f_side_clearance_mm'] - 1e-9 for b in fside))
            self.assertTrue(r_body <= x <= 16.2 - r_body)
            self.assertTrue(y0 + r_tap + rl.MIN_WALL - 1e-9 <= y <= y1 - r_tap - rl.MIN_WALL + 1e-9)
            self.assertGreaterEqual(rl._box_point_dist(notch, (x, y)), r_tap + rl.MIN_WALL - 1e-9)
        a, b = h['contacts_board_mm']
        self.assertGreaterEqual(math.dist(a, b), 2 * r_tap + rl.MIN_WALL - 1e-9)
        self.assertTrue(self.d['fresh_native_criteria']['hold_down_plungers_on_free_f_face'])

    def test_statics_cover_every_force_extreme_without_spring_balance(self):
        h = self.d['holddown']
        cases = h['statics_cases']
        lo, hi = h['plunger_force_each_N']
        pf = h['probe_force_total_N']
        self.assertEqual(sorted((tuple(c['plunger_forces_N']), c['probe_force_total_N']) for c in cases),
                         sorted(((a, b), p) for a in (lo, hi) for b in (lo, hi) for p in (pf['minimum_at_acceptance_stroke'], pf['maximum_stroke'])))
        cx, cy = h['probe_resultant_board_mm']
        q = h['contacts_board_mm']
        for c in cases:
            fs, pp = c['plunger_forces_N'], c['probe_force_total_N']
            tot = sum(fs) - pp
            self.assertGreater(tot, 0)
            want = [(sum(f_ * p[0] for f_, p in zip(fs, q)) - pp * cx) / tot, (sum(f_ * p[1] for f_, p in zip(fs, q)) - pp * cy) / tot]
            self.assertAlmostEqual(c['board_net_load_point_mm'][0], want[0], places=4)
            self.assertAlmostEqual(c['board_net_load_point_mm'][1], want[1], places=4)
            # unequal plunger forces included: each plunger is displacement-set, so no case depends on a matched pair
            self.assertGreaterEqual(c['board_net_load_point_margin_mm'], rl.RULES['resultant_margin_mm'])
        self.assertEqual(h['board_net_load_point_inside_land_hull_mm'], min(c['board_net_load_point_margin_mm'] for c in cases))
        self.assertTrue(self.d['criterion_3_checks']['board_stays_on_land'])
        self.assertTrue(self.d['criterion_3_checks']['clamp_force_sized_with_margin'])

    def test_a_stricter_land_margin_fails_criterion_3(self):
        with unittest.mock.patch.dict(rl.RULES, {'resultant_margin_mm': 5.0}):
            d = rl.design(GEOM, probes())
        self.assertFalse(d['criterion_3_checks']['board_stays_on_land'])

    def test_hull_margin(self):
        hull = rl._hull([(0, 0), (4, 0), (4, 4), (0, 4), (2, 2)])
        self.assertEqual(len(hull), 4)
        self.assertAlmostEqual(rl._hull_margin(hull, (1, 2)), 1.0)
        self.assertLess(rl._hull_margin(hull, (5, 2)), 0)

    def test_keying_registration_and_stroke(self):
        k = self.d['keying']
        self.assertTrue(k['keyed'])
        self.assertGreaterEqual(len(k['blocking_features']), 3)
        reg = self.d['registration']
        self.assertAlmostEqual(reg['radial_budget_mm'], 0.25)
        self.assertGreaterEqual(reg['worst_case_margin_mm'], 0)
        self.assertEqual(len(reg['acceptance_requirements']), 4)
        st = self.d['stroke']
        self.assertEqual(st['stroke_window_mm'], [0.0, 6.35])
        lo, hi = st['accommodated_installation_height_mm']
        self.assertTrue(lo <= st['installation_height_mm'] <= hi)
        self.assertGreaterEqual(self.d['wiring']['wire_bend_space_mm'], self.d['wiring']['required_bend_space_mm'])

    def test_pressure_plate_clears_f_parts(self):
        pr = self.d['pressure_plate']
        self.assertEqual(pr['clearance_conflicts'], [])
        self.assertTrue(all(u['clearance_to_plate_mm'] >= rl.RULES['pressure_plate_part_clearance_mm'] for u in pr['parts_under_plate']))
        # the milled notch corners (radius r) still keep the clearance off the J5 courtyard corners
        j5 = next(fp for fp in GEOM['footprints'] if fp['fpid'] == 'LightBlock:PICO3')['courtyard_bbox_mm']['F']
        n, r = pr['j5_notch_board_mm'], pr['corner_radius_mm']
        for cx_, cy_, kx, ky in ((n[0] + r, n[1] + r, j5[0], j5[1]), (n[2] - r, n[1] + r, j5[2], j5[1])):
            self.assertGreaterEqual(r - math.dist((cx_, cy_), (kx, ky)), rl.RULES['pressure_plate_part_clearance_mm'] - 1e-6)

    def test_criterion_3_met_at_every_worst_case(self):
        self.assertEqual({k for k, v in self.d['criterion_3_checks'].items() if not v}, set())
        self.assertTrue(all(self.d['fresh_native_criteria'].values()), self.d['fresh_native_criteria'])

class CompletionTests(unittest.TestCase):
    def test_completion_flags_follow_criteria(self):
        r = f.report()
        cc = r['completion_criteria']
        for k in ('1_native_support_and_relief', '2_keying_and_registration', '3_stroke_stop_guide_fixing_insulation_wiring',
                  '4_assembly_step_interference_check'):
            self.assertTrue(cc[k]['met'], cc[k])
        self.assertFalse(cc['5_physical_tests']['met'])
        self.assertEqual(r['status'], 'BLOCKED')
        self.assertTrue(r['fresh_native_verified'])
        self.assertTrue(r['digital_criteria_1_to_4_met'])
        self.assertFalse(r['digital_fixture_complete'])
        self.assertEqual(r['blockers'], [])

    def test_a_failing_hold_down_case_clears_the_flags(self):
        with unittest.mock.patch.dict(rl.RULES, {'board_deflection_limit_mm': 0.02}):
            r = f.report()
        self.assertFalse(r['completion_criteria']['3_stroke_stop_guide_fixing_insulation_wiring']['met'])
        self.assertFalse(r['digital_criteria_1_to_4_met'])
        self.assertTrue(any('board_bending_across_window_within_limit' in b for b in r['blockers']), r['blockers'])

    def test_hardware_proposal_covers_every_materials_line(self):
        r = f.report()
        items = json.loads((f.OUT / 'materials.json').read_text())['items']
        self.assertTrue(r['hardware_proposal_complete'], r['hardware_proposal_problems'])
        self.assertEqual({e['requirement_id'] for e in r['hardware_proposal']}, {i['id'] for i in items})
        for e in r['hardware_proposal']:
            self.assertEqual(set(e) >= {'requirement_id', 'manufacturer', 'mpn', 'source'}, True)
            self.assertEqual(e['status'], 'PROPOSED_AWAITING_OWNER_APPROVAL')
            self.assertTrue(e['manufacturer'] and e['mpn'] and e['source_authority'])
        self.assertIn('not a selection', r['hardware_proposal_scope'])
        self.assertTrue(all('SELECTED' not in i['status'] or 'NOT_SELECTED' in i['status'] for i in items))

    def test_hardware_proposal_incomplete_without_a_line_or_a_source(self):
        short = [e for e in f.HARDWARE_PROPOSAL if e[0] != 'hold-down-plungers']
        with unittest.mock.patch.object(f, 'HARDWARE_PROPOSAL', short):
            r = f.report()
        self.assertFalse(r['hardware_proposal_complete'])
        self.assertIn('hold-down-plungers: no proposed candidate', r['hardware_proposal_problems'])
        bad = [e if e[0] != 'stop-screws' else (e[0], e[1], e[2], 'sources.json#absent') for e in f.HARDWARE_PROPOSAL]
        with unittest.mock.patch.object(f, 'HARDWARE_PROPOSAL', bad):
            self.assertFalse(f.report()['hardware_proposal_complete'])
        with unittest.mock.patch.dict(rl.RULES, {'plunger_body_end_clearance_min_mm': 0.3}):
            r = f.report()
        self.assertFalse(r['hardware_proposal_complete'])

    def test_criterion_5_keeps_gating_the_documented_flag(self):
        r = f.report()
        real = rl.design

        def all_met(*a, **k):
            d = real(*a, **k)
            return dict(d, fresh_native_criteria={c: True for c in d['fresh_native_criteria']},
                        criterion_3_checks={c: True for c in d['criterion_3_checks']})
        with unittest.mock.patch.object(f, 'assembly_status', return_value=(True, 'ok', None)), \
                unittest.mock.patch.object(f.relief_design, 'design', side_effect=all_met):
            r2 = f.report()
        self.assertTrue(r2['digital_criteria_1_to_4_met'])
        self.assertFalse(r2['completion_criteria']['5_physical_tests']['met'])
        self.assertFalse(r2['digital_fixture_complete'])
        self.assertEqual(r2['status'], 'BLOCKED')
        self.assertIn('not order eligibility', r['digital_criteria_1_to_4_met_scope'])

    def test_a_design_change_invalidates_the_assembly_check(self):
        with unittest.mock.patch.dict(rl.SOURCES['PicoBlade 530470310'], {'class': 'SOURCE_DERIVED'}):
            r = f.report()
        self.assertFalse(r['completion_criteria']['4_assembly_step_interference_check']['met'])
        self.assertIn('different design', r['completion_criteria']['4_assembly_step_interference_check']['basis'])
        self.assertFalse(r['digital_fixture_complete'])

    def test_candidate_fabricator_guidance_is_reference_only(self):
        r = f.report()
        ref = json.loads((f.OUT / 'candidate-references.json').read_text())
        self.assertEqual(ref['status'], 'CANDIDATE_REFERENCE_NOT_SELECTED')
        c = r['candidate_reference_checks'][0]
        self.assertEqual(c['selection_status'], 'NOT_SELECTED')
        for name, plate in c['plates'].items():
            for key, chk in plate['checks'].items():
                if key != 'drilled_bore_web_mm':
                    self.assertIn(chk['met'], (True, None), (name, key))
        self.assertFalse(c['plates']['probe_plate']['checks']['drilled_bore_web_mm']['met'])
        self.assertFalse(c['satisfied'])
        self.assertTrue(any('fabricator must confirm' in b for b in r['owner_and_supplier_items']))
        self.assertNotIn('JLCCNC', json.dumps(json.loads((f.OUT / 'materials.json').read_text())['items']))


if __name__ == '__main__':
    unittest.main()
