"""Negative controls for the explicitly incomplete fixture study."""
import copy
import json
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

SPEC=importlib.util.spec_from_file_location('fixture',Path(__file__).resolve().parents[1]/'a7_fixture.py')
f=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(f)

class FixtureStudyTests(unittest.TestCase):
    def test_blocked_is_not_completion(self):
        r=f.report()
        self.assertEqual(r['status'],'BLOCKED')
        self.assertFalse(r['digital_fixture_complete'])
        self.assertFalse(r['fresh_native_verified'])
        self.assertIsNone(r['calculations']['worst_case_registration_margin_mm'])
        self.assertEqual(r['calculations']['nominal_total_force_at_working_stroke_N'],5)

    def test_false_completion_rejected_by_producer(self):
        r=f.report();r['digital_fixture_complete']=True;r['fresh_native_verified']=True
        with self.assertRaisesRegex(ValueError,'canonical producer'):f.validate_report(r)

    def test_board_change_invalidates_study(self):
        with patch.object(f,'digest',return_value='a'*64):
            with self.assertRaisesRegex(ValueError,'invalidated'):f.report()

    def test_canonical_change_invalidates_even_with_claimed_board_hash(self):
        with patch.object(f,'digest',side_effect=[f.BOARD_SHA,'b'*64]):
            with self.assertRaisesRegex(ValueError,'invalidated'):f.report()

    def test_wrong_net_side_and_missing_pad_rejected(self):
        original=f.bound_r4_placement()
        for mutation in ('side','net','missing'):
            p=copy.deepcopy(original)
            tp=next(c for c in p['components'] if c['ref']=='TP1')
            if mutation=='side':tp['side']='F'
            elif mutation=='net':tp['pads']['1']['net']='/GND'
            else:p['components'].remove(tp)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):f.probe_map(p,f.BOARD.read_text())

    def test_actual_pad_size_required(self):
        text=f.BOARD.read_text().replace('(size 1 1)','(size 0.9 0.9)')
        with self.assertRaisesRegex(ValueError,'actual PCB'):f.probe_map(f.bound_r4_placement(),text)

    def test_b_side_transform_is_mirrored_and_invertible(self):
        for pad in f.report()['pads']:
            bx,by=pad['board_xy_mm'];fx,fy=pad['carrier_xy_mm']
            self.assertAlmostEqual(16.2-fx,bx);self.assertEqual(fy,by)

class StepBindingTests(unittest.TestCase):
    def test_step_bytes_are_bound(self):
        self.assertEqual(f.report()['study_step_sha256'],f.digest(f.OUT/'carrier-study.step'))
        real=f.digest
        with patch.object(f,'digest',side_effect=lambda q:'c'*64 if Path(q).name=='carrier-study.step' else real(q)):
            with self.assertRaisesRegex(ValueError,'canonical producer'):
                f.validate_report(json.loads((f.OUT/'manifest.json').read_text()))

class NativeGeometryBindingTests(unittest.TestCase):
    def pads(self):
        return f.probe_map(f.bound_r4_placement(),f.BOARD.read_text())

    def test_probe_pads_confirmed_by_native_record(self):
        n=f.report()['native_geometry']
        self.assertTrue(n['probe_pads_match'])
        self.assertEqual(n['record_sha256'],f.digest(f.native_geom.RECORD))

    def test_probe_pad_disagreement_rejected(self):
        for key,value in (('board_xy_mm',[0.0,0.0]),('pad_diameter_mm',0.9),('net','GND')):
            pads=self.pads();pads[0][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'native'):f.native_probe_pads(pads)

    def test_invalid_or_missing_record_rejected(self):
        with patch.object(f.native_geom,'check_record',return_value=['record is stale']):
            with self.assertRaisesRegex(ValueError,'record invalid'):f.native_probe_pads(self.pads())
        with patch.object(f.native_geom,'RECORD',f.OUT/'absent.json'):
            with self.assertRaisesRegex(ValueError,'record missing'):f.native_probe_pads(self.pads())

    def test_native_pads_do_not_set_fresh_native_verified(self):
        self.assertFalse(f.report()['fresh_native_verified'])

if __name__=='__main__':unittest.main()
