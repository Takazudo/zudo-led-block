"""A7 board placement: committed placement is current, legal, and the checker catches what it must."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(REPO / 'scripts'))
import a7_board as ab  # noqa: E402


def committed():
    return json.loads(ab.PLACEMENT.read_text())['placements']


class PlacementTests(unittest.TestCase):
    def test_committed_placement_is_current(self):
        self.assertEqual(ab.placement_doc(ab.pack()), ab.PLACEMENT.read_text())

    def test_committed_placement_has_no_violations(self):
        pl = committed()
        self.assertEqual(set(pl), set(ab.components()))
        self.assertEqual(ab.violations(pl), [])

    def test_fixed_parts_at_their_declared_positions(self):
        pl = committed()
        for ref, f in ab.FIXED.items():
            self.assertEqual((pl[ref]['at'], pl[ref]['rot'], pl[ref]['side']), (f['at'], f['rot'], f['side']), ref)

    def test_solder_face_only_low_profile_parts(self):
        comps = ab.components()
        for ref, q in committed().items():
            if q['side'] == 'B':
                self.assertIn(comps[ref]['footprint'], ab.B_ALLOWED, ref)

    def test_j3_retention_pads_keep_edge_clearance(self):
        # SH4 MP pads reach x +/-3.4 (A5 JST_SH4 footprint); KiCad board-edge rule 0.2 mm
        self.assertLessEqual(ab.FIXED['J3']['at'][0] + 3.4, ab.W - 0.2)

    def test_overlap_is_reported(self):
        pl = copy.deepcopy(committed())
        pl['C5'] = copy.deepcopy(pl['C4'])
        self.assertIn('courtyard overlap C4 / C5', ab.violations(pl))

    def test_courtyard_comparison_is_exact_at_kicad_resolution(self):
        # exact abutment is clear (as in native DRC), float noise cannot flip it, 1 nm of overlap is reported
        self.assertEqual(ab.placement_rule(), (1, 0))
        comps = ab.components()
        base = copy.deepcopy(committed())
        x1, _, x2, _ = ab.footprint_rect(comps['C9'], base['C9'])
        cases = {0.0: False, 1e-12: False, -1e-12: False, -1e-6: True}
        for shift, reported in cases.items():
            pl = copy.deepcopy(base)
            pl['C10'] = copy.deepcopy(pl['C9'])
            pl['C10']['at'] = [pl['C9']['at'][0] + (x2 - x1) + shift, pl['C9']['at'][1]]
            self.assertEqual('courtyard overlap C10 / C9' in ab.violations(pl), reported, shift)

    def test_courtyard_past_board_edge_is_reported(self):
        pl = copy.deepcopy(committed())
        comps = ab.components()
        x1, _, _, _ = ab.footprint_rect(comps['C8'], pl['C8'])
        pl['C8']['at'] = [pl['C8']['at'][0] - x1 - 1e-6, pl['C8']['at'][1]]
        self.assertTrue(any(v.startswith('C8: courtyard') and 'outside the board' in v for v in ab.violations(pl)))
        pl['C8']['at'][0] += 1e-6
        self.assertFalse(any(v.startswith('C8: courtyard') and 'outside the board' in v for v in ab.violations(pl)))

    def test_keepout_intrusion_is_reported(self):
        pl = copy.deepcopy(committed())
        pl['C9'] = {'at': [6.0, 36.0], 'rot': 0, 'side': 'F'}
        self.assertIn('C9: courtyard in keep-out jack-in', ab.violations(pl))

    def test_tall_part_on_solder_face_is_reported(self):
        pl = copy.deepcopy(committed())
        pl['C9']['side'] = 'B'
        self.assertIn('C9: C0603 not allowed on the solder face', ab.violations(pl))

    def test_unplaced_part_is_reported(self):
        pl = copy.deepcopy(committed())
        del pl['R1']
        self.assertTrue(any(v.startswith('unplaced') for v in ab.violations(pl)))


class RuleDeltaTests(unittest.TestCase):
    def test_project_rules_are_a5_plus_recorded_delta(self):
        a5 = json.loads((REPO / 'engineering/a5/electronics/native/controller/controller.kicad_pro').read_text())
        a7 = json.loads((ab.a7.A7_CTRL / 'controller.kicad_pro').read_text())
        delta = json.loads((REPO / 'engineering/a7/verification/native_gate.json').read_text())['design_rule_delta']
        rules = dict(a5['board']['design_settings']['rules'])
        for k, v in delta['rules'].items():
            self.assertEqual(rules[k], v['from'], k)
            rules[k] = v['to']
        self.assertEqual(a7['board']['design_settings']['rules'], rules)
        cls = dict(a5['net_settings']['classes'][0])
        for k, v in delta['netclass'].items():
            self.assertEqual(cls[k], v['from'], k)
            cls[k] = v['to']
        self.assertEqual(a7['net_settings']['classes'][0], cls)

    def test_custom_rules_only_tighten_and_match_the_profile(self):
        sys.path.insert(0, str(REPO / 'scripts/native_gate'))
        import runner
        prof = json.loads((REPO / 'engineering/a7/verification/native_gate.json').read_text())
        rules = prof['design_rule_delta']['custom_rules']
        self.assertEqual(ab.a7.A7_STYLE['custom_rules'], [{k: r[k] for k in ('name', 'constraint', 'min_mm', 'condition')} for r in rules])
        dru = (ab.a7.A7_CTRL / 'controller.kicad_dru').read_text()
        self.assertEqual(dru, ab.a7.custom_rules_text(ab.a7.A7_STYLE['custom_rules']))
        self.assertEqual(dru, runner.custom_rules_text(rules))
        self.assertEqual(runner.custom_rules_failures(REPO, prof), [])
        pro = json.loads((ab.a7.A7_CTRL / 'controller.kicad_pro').read_text())['board']['design_settings']['rules']
        for r in rules:
            self.assertEqual(r['direction'], 'stricter')
            self.assertEqual(r['constraint'], 'hole_clearance')
            self.assertGreater(r['min_mm'], pro['min_hole_clearance'])
        ev = json.loads((REPO / prof['design_rule_delta']['evidence']).read_text())
        self.assertIn('PTH to Track', json.dumps(ev))

    def test_edited_custom_rules_file_is_refused(self):
        import shutil
        import tempfile
        sys.path.insert(0, str(REPO / 'scripts/native_gate'))
        import runner
        prof = json.loads((REPO / 'engineering/a7/verification/native_gate.json').read_text())
        d = prof['designs']['a7_controller']
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / d['dir']).mkdir(parents=True)
            src = REPO / d['dir'] / d['custom_rules']
            shutil.copyfile(src, repo / d['dir'] / d['custom_rules'])
            self.assertEqual(runner.custom_rules_failures(repo, prof), [])
            (repo / d['dir'] / d['custom_rules']).write_text(src.read_text().replace('0.35mm', '0.2mm'))
            self.assertTrue(runner.custom_rules_failures(repo, prof))
            (repo / d['dir'] / d['custom_rules']).unlink()
            self.assertTrue(any('missing' in f for f in runner.custom_rules_failures(repo, prof)))
        weak = copy.deepcopy(prof)
        weak['controls']['mutations'].pop('control_pth_to_track')
        self.assertTrue(any('no rule_squeeze control' in e for e in runner.candidate_binding(weak)))

    def test_rule_squeeze_needs_the_rule_name_and_pad_in_the_native_report(self):
        sys.path.insert(0, str(REPO / 'scripts/native_gate'))
        import runner
        hit = {'type': 'hole_clearance',
               'description': "Hole clearance violation (rule 'a7_pth_to_track' clearance 0.3500 mm; actual 0.3200 mm)",
               'items': [{'description': 'Track [/GND] on In1.Cu, length 1.0000 mm'},
                         {'description': 'PTH pad 1 [/+12V_RAW] of J5'}]}
        self.assertTrue(runner.rule_squeeze_reported([hit], ['a7_pth_to_track'], 'J5.1'))
        base_rule = dict(hit, description='Hole clearance violation (board setup constraints clearance 0.2000 mm; actual 0.1500 mm)')
        self.assertFalse(runner.rule_squeeze_reported([base_rule], ['a7_pth_to_track'], 'J5.1'))
        self.assertFalse(runner.rule_squeeze_reported([dict(hit, type='clearance')], ['a7_pth_to_track'], 'J5.1'))
        self.assertFalse(runner.rule_squeeze_reported([hit], ['a7_pth_to_track'], 'J5.3'))
        self.assertFalse(runner.rule_squeeze_reported([hit], ['a7_pth_to_track'], 'J1.1'))
        self.assertFalse(runner.rule_squeeze_reported([], ['a7_pth_to_track'], 'J5.1'))
        self.assertFalse(runner.rule_squeeze_reported([hit], [], 'J5.1'))

    def test_delta_is_backed_by_fabricator_evidence(self):
        delta = json.loads((REPO / 'engineering/a7/verification/native_gate.json').read_text())['design_rule_delta']
        ev = json.loads((REPO / delta['evidence']).read_text())
        self.assertRegex(ev['source']['retrieved_sha256'], '^[0-9a-f]{64}$')
        r = delta['rules']
        self.assertGreaterEqual((r['min_via_diameter']['to'] - r['min_through_hole_diameter']['to']) / 2, 0.15)


if __name__ == '__main__':
    unittest.main()
