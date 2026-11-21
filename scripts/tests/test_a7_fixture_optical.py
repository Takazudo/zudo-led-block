"""Thin-board regression: original support must not inherit old stiffness PASS."""
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import a7_fixture_relief as relief


class ThinFixtureRegression(unittest.TestCase):
    def test_original_support_fails_new_stack(self):
        geometry=json.loads((ROOT/'engineering/a7/fixture/native-geometry.json').read_text())['geometry']
        pads=json.loads((ROOT/'engineering/a7/fixture/manifest.json').read_text())['pads']
        design=relief.design(geometry,pads)
        hold=design['holddown']
        self.assertEqual(hold['plunger_compression_mm']['board_thickness_range_mm'],[.7,.9])
        self.assertEqual(hold['layout_status'],'REJECTED_INSUFFICIENT_FORCE')
        self.assertFalse(design['criterion_3_checks']['clamp_force_sized_with_margin'])
        self.assertFalse(design['criterion_3_checks']['board_bending_across_window_within_limit'])
        self.assertGreater(hold['board_bending_across_window']['deflection_mm'],.1)

if __name__=='__main__': unittest.main()
