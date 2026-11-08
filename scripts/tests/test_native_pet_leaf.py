"""A7 bonded PET leaf profile check: verdict rules, drop bound and guards (no KiCad needed)."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(REPO / 'scripts'))
import a7_pet_leaf_check as pc  # noqa: E402

PROF = json.loads(pc.PROFILE.read_text())


def probe(layer='F.Cu', vias=(), gap=0.8, smd=True):
    return {'pads': [{'ref': 'D1', 'pad': '1', 'net': 'VLED', 'smd': smd, 'layers': ['F.Cu']}],
            'tracks': [{'net': 'VLED', 'layer': 'F.Cu', 'width': 0.3, 'length': 10.0},
                       {'net': 'DATA', 'layer': layer, 'width': 0.25, 'length': 5.0}],
            'vias': [{'net': 'DATA', 'diameter': d, 'drill': h} for d, h in vias],
            'pad_gaps': {'D1': {'footprint': 'X', 'min_pad_gap': [gap, '1', '2']}}}


DRC = {'board_min_clearance_mm': 0.15, 'clean_under_board_rules': True, 'edge_hits': []}


class VerdictTests(unittest.TestCase):
    def test_single_layer_copper_passes_one_layer(self):
        v, _ = pc.verdicts(PROF, probe(), DRC)
        self.assertEqual(v['pet_1layer.copper'], 'PASS')
        self.assertEqual(v['coverlay_bridges'], 'PASS')
        self.assertEqual(v['smt_only'], 'PASS')

    def test_back_copper_or_vias_fail_one_layer(self):
        self.assertEqual(pc.verdicts(PROF, probe(layer='B.Cu'), DRC)[0]['pet_1layer.copper'], 'NOT_MET')
        self.assertEqual(pc.verdicts(PROF, probe(vias=[(0.6, 0.3)]), DRC)[0]['pet_1layer.copper'], 'NOT_MET')

    def test_small_vias_fail_two_layer(self):
        self.assertEqual(pc.verdicts(PROF, probe(vias=[(0.6, 0.3)]), DRC)[0]['pet_2layer.vias'], 'PASS')
        self.assertEqual(pc.verdicts(PROF, probe(vias=[(0.5, 0.2)]), DRC)[0]['pet_2layer.vias'], 'NOT_MET')
        self.assertEqual(pc.verdicts(PROF, probe(vias=[(0.55, 0.4)]), DRC)[0]['pet_2layer.vias'], 'NOT_MET')

    def test_narrow_coverlay_bridge_is_reported(self):
        v, f = pc.verdicts(PROF, probe(gap=0.4), DRC)
        self.assertEqual(v['coverlay_bridges'], 'NOT_MET')
        self.assertAlmostEqual(f['coverlay_bridges_removed']['D1']['coverlay_bridge_mm'], 0.2)

    def test_edge_hits_or_board_rule_violations_fail(self):
        self.assertEqual(pc.verdicts(PROF, probe(), dict(DRC, edge_hits=['x']))[0]['pet_2layer.copper_to_edge'], 'NOT_MET')
        self.assertEqual(pc.verdicts(PROF, probe(), dict(DRC, clean_under_board_rules=False))[0]
                         ['pet_2layer.track_and_clearance'], 'NOT_MET')

    def test_tht_pad_fails_smt_only(self):
        self.assertEqual(pc.verdicts(PROF, probe(smd=False), DRC)[0]['smt_only'], 'NOT_MET')

    def test_empty_probe_is_an_error(self):
        with self.assertRaises(ValueError):
            pc.verdicts(PROF, {'pads': [], 'tracks': [], 'vias': [], 'pad_gaps': {}}, DRC)


class ProfileTests(unittest.TestCase):
    def test_expected_names_every_verdict(self):
        v, _ = pc.verdicts(PROF, probe(), DRC)
        exp = set(PROF['expected']) - {'note'}
        self.assertEqual(exp, set(v) | {'interface', 'mechanical'})

    def test_profile_keeps_fr4_default_and_no_release(self):
        self.assertEqual(PROF['default_leaf'], 'fr4')
        self.assertEqual(PROF['status'], 'PROFILE_ONLY_NOT_A_DESIGN')
        self.assertIs(PROF['mechanical']['require']['manufacturing_release'], False)

    def test_rules_cite_a_hashed_source(self):
        ids = {x['source_id']: x for x in PROF['sources']}
        self.assertIn(PROF['rules']['source'], ids)
        self.assertRegex(ids[PROF['rules']['source']]['sha256'], r'^[0-9a-f]{64}$')

    def test_rilim_in_netlist_matches_profile(self):
        nl = REPO / PROF['interface']['netlists']['controller']
        self.assertTrue(pc.rilim_value(nl, 'R11').startswith('68k'))


class HelperTests(unittest.TestCase):
    def test_drop_bound_is_series_sum(self):
        t = [{'net': 'VLED', 'width': 1.0, 'length': 100.0}, {'net': 'X', 'width': 0.1, 'length': 100.0}]
        v = pc.drop_bound(t, ('VLED',), 1.0, 17.2, 1.72e-8)
        self.assertAlmostEqual(v, 0.1, places=6)

    def test_rule_hits_need_the_rule_name(self):
        v = [{'description': "Board edge clearance violation (rule 'pet_copper_edge' clearance 0.3000 mm)"},
             {'description': "Board edge clearance violation (board setup constraints)"}]
        self.assertEqual(len(pc.rule_hits(v, 'pet_copper_edge')), 1)
        self.assertEqual(pc.rule_hits(v, 'pet_copper_edge_control'), [])

    def test_output_inside_repo_is_refused(self):
        p = subprocess.run([sys.executable, str(REPO / 'scripts/a7_pet_leaf_check.py'), '--out', str(REPO / 'tmp-pet-leaf')],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)
        self.assertFalse((REPO / 'tmp-pet-leaf').exists())


if __name__ == '__main__':
    unittest.main()
