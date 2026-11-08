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


if __name__ == '__main__':
    unittest.main()
