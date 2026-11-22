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
        self.assertTrue(r['fresh_native_verified'])
        self.assertEqual(r['calculations']['worst_case_registration_margin_mm'],0.03)
        self.assertFalse(r['completion_criteria']['5_physical_tests']['met'])
        self.assertTrue(r['physical_items'])
        self.assertTrue(r['owner_and_supplier_items'])
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

class AssemblyBindingTests(unittest.TestCase):
    def test_assembly_step_and_interference_record_are_bound(self):
        r=f.report()
        self.assertEqual(r['assembly']['step_sha256'],f.digest(f.ASSEMBLY_STEP))
        self.assertEqual(r['assembly']['record_sha256'],f.digest(f.INTERFERENCE))
        self.assertTrue(r['completion_criteria']['4_assembly_step_interference_check']['met'])
        real=f.digest
        with patch.object(f,'digest',side_effect=lambda q:'c'*64 if Path(q).name=='fixture-assembly.step' else real(q)):
            self.assertFalse(f.report()['completion_criteria']['4_assembly_step_interference_check']['met'])
            with self.assertRaisesRegex(ValueError,'canonical producer'):
                f.validate_report(json.loads((f.OUT/'manifest.json').read_text()))

    def test_interference_record_has_no_interference_and_the_designed_contacts_touch(self):
        rec=json.loads(f.INTERFERENCE.read_text())
        self.assertEqual(rec['interferences'],[])
        self.assertTrue(all(c['minimum_mm']>0 for c in rec['clearances']))
        kinds={c['contact'] for c in rec['designed_contacts']}
        self.assertEqual(len(kinds),4)
        self.assertTrue(all(c['touching'] for c in rec['designed_contacts']))
        names={s['name'] for s in rec['solids']}
        for want in ('support_carrier','probe_plate','pressure_plate','base_plate','controller board'):
            self.assertIn(want,names)
        self.assertEqual(sum('GKS-050' in n for n in names),5)

    def test_record_is_bound_to_assembly_code_and_native_record(self):
        rec=json.loads(f.INTERFERENCE.read_text());mi=rec['model_inputs']
        self.assertEqual(mi['assembly_code_sha256'],f.digest(Path(f.relief_assembly.__file__)))
        self.assertEqual(mi['native_geometry_sha256'],f.digest(f.native_geom.RECORD))
        with patch.object(f.relief_assembly,'model_inputs',side_effect=lambda r,g:dict(mi,assembly_code_sha256='d'*64)):
            self.assertFalse(f.report()['completion_criteria']['4_assembly_step_interference_check']['met'])

    def test_a_recorded_interference_fails_criterion_4(self):
        rec=json.loads(f.INTERFERENCE.read_text());rec['interferences']=[{'a':'x','b':'y','common_volume_mm3':1.0}]
        real=f.json.loads
        with patch.object(f.json,'loads',side_effect=lambda t:rec if t==f.INTERFERENCE.read_text() else real(t)):
            ok,basis,_=f.assembly_status(f.report()['b_side_relief'])
        self.assertFalse(ok);self.assertIn('interference',basis)

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
        # the pads alone do not earn it: without the sourced J5 tail the flag falls back to false
        bare={k:v for k,v in f.relief_design.SOURCES['PicoBlade 530470310'].items() if k.startswith('mated_')};bare['class']='UNKNOWN'
        with patch.dict(f.relief_design.SOURCES['PicoBlade 530470310'],bare,clear=True):
            r=f.report()
        self.assertTrue(r['native_geometry']['probe_pads_match'])
        self.assertFalse(r['fresh_native_verified'])
        self.assertFalse(r['digital_criteria_1_to_4_met'])

class CandidateTests(unittest.TestCase):
    """The proposed replacement candidate sits beside the retained geometry and claims no more than its record shows."""
    def rec(self):
        return json.loads(f.CANDIDATE_RECORD.read_text())

    def test_candidate_is_bound_beside_the_retained_geometry_and_sets_no_flag(self):
        r=f.report();c=r['proposed_replacement_candidate']
        self.assertTrue(c['bound'],c.get('problems'))
        self.assertFalse(c['replaces_retained_geometry'])
        self.assertIn('not selected',c['status']);self.assertIn('not physically validated',c['status'])
        self.assertEqual(c['step_sha256'],f.digest(f.CANDIDATE_STEP));self.assertEqual(c['record_sha256'],f.digest(f.CANDIDATE_RECORD))
        # the retained result stands: criterion 3 rejected, nothing completed
        self.assertFalse(r['completion_criteria']['3_stroke_stop_guide_fixing_insulation_wiring']['met'])
        self.assertFalse(r['digital_criteria_1_to_4_met']);self.assertFalse(r['digital_fixture_complete']);self.assertEqual(r['status'],'BLOCKED')
        self.assertEqual(r['b_side_relief']['holddown']['layout_status'],'REJECTED_INSUFFICIENT_FORCE')
        self.assertNotEqual(r['b_side_relief']['holddown']['contacts_board_mm'],c['candidate']['contacts_board_mm'])
        for hold in ('Machining availability','Material selection','Fabrication suitability','Wear, creep','Physical criterion 5'):
            self.assertTrue(any(h.startswith(hold) for h in c['holds']),hold)

    def test_candidate_geometry_corresponds_to_the_condition_matrix(self):
        rec=self.rec();m=json.loads(f.CONDITION_MATRIX.read_text())
        self.assertEqual(f.candidate_matrix_correspondence(rec,m),[])
        self.assertEqual(rec['candidate']['contact_diameters_mm'],[1.5,1.2]);self.assertEqual(rec['candidate']['stepped_tip_length_mm'],0.5)
        self.assertEqual([t['thickness_mm'] for t in rec['thickness_cases']],[0.7,0.8,0.9])
        for mutate,why in ((lambda r,m:r['candidate']['contact_diameters_mm'].__setitem__(1,1.5),'contact diameters'),
                           (lambda r,m:r['candidate']['contacts_board_mm'].__setitem__(1,[15.3,26.5]),'pin sites'),
                           (lambda r,m:r['candidate'].__setitem__('stepped_tip_length_mm',0.4),'stepped-tip length'),
                           (lambda r,m:r['candidate']['j5_notch_board_mm'].__setitem__(1,24.2),'J5 notch'),
                           (lambda r,m:r['thickness_cases'][0]['compression_mm'].__setitem__('range',[0.5,1.1]),'outside the matrix band'),
                           (lambda r,m:m.__setitem__('thicknesses_mm',[0.8]),'thicknesses')):
            r2,m2=copy.deepcopy(rec),copy.deepcopy(m);mutate(r2,m2)
            with self.subTest(why=why):self.assertTrue(any(why in p for p in f.candidate_matrix_correspondence(r2,m2)))

    def test_wrong_tip_diameter_or_stale_native_record_unbinds_the_candidate(self):
        import a7_fixture_support as support
        with patch.object(support,'stepped_tip_contacts',return_value=[1.5,1.5]):
            self.assertFalse(f.candidate_status()['bound'])
        with patch.dict(support.STEPPED_TIP,{'tip_length_mm':0.6}):
            self.assertFalse(f.candidate_status()['bound'])
        real=f.digest
        with patch.object(f,'digest',side_effect=lambda q:'e'*64 if Path(q).name=='native-geometry.json' else real(q)):
            st=f.candidate_status()
        self.assertFalse(st['bound']);self.assertTrue(any('native record' in p for p in st['problems']))
        rec=self.rec()
        self.assertEqual(rec['model_inputs']['native_geometry_sha256'],f.digest(f.native_geom.RECORD))
        self.assertEqual(json.loads(f.native_geom.RECORD.read_text())['board_sha256'],f.BOARD_SHA)

    def test_tampered_candidate_record_or_step_is_rejected_by_the_producer(self):
        real=f.digest
        with patch.object(f,'digest',side_effect=lambda q:'c'*64 if Path(q).name=='candidate-assembly.step' else real(q)):
            self.assertFalse(f.candidate_status()['bound'])
            with self.assertRaisesRegex(ValueError,'canonical producer'):
                f.validate_report(json.loads((f.OUT/'manifest.json').read_text()))

    def test_candidate_cad_is_clean_at_every_thickness(self):
        rec=self.rec();prev=None
        for t in rec['thickness_cases']:
            with self.subTest(t=t['thickness_mm']):
                self.assertEqual(t['interferences'],[])
                self.assertTrue(all(c['touching'] for c in t['designed_contacts']))
                self.assertEqual(len({c['contact'] for c in t['designed_contacts']}),4)
                self.assertTrue(all(c['minimum_mm']>0 for c in t['clearances']))
                self.assertTrue(all(t['checks'].values()),t['checks'])
                lo,hi=t['compression_mm']['range'];self.assertGreater(lo,0);self.assertLessEqual(hi,1.3+1e-9)
                self.assertEqual([p['contact_diameter_mm'] for p in t['pins']],[1.5,1.2])
                if prev is not None:self.assertGreater(t['compression_mm']['nominal'],prev)  # thicker board, more compression
                prev=t['compression_mm']['nominal']

    def test_registration_finding_is_recorded_not_hidden(self):
        rec=self.rec();reg=rec['registration']
        self.assertTrue(rec['checks']['registration_closes_with_recorded_budget'])
        self.assertFalse(rec['checks']['registration_closes_with_modelled_plate_location'])
        self.assertFalse(rec['all_digital_checks_met'])
        self.assertEqual(reg['pressure_plate_location']['worst_plate_offset_mm'],0.4)
        m=json.loads(f.CONDITION_MATRIX.read_text())['adopted_candidate']
        self.assertEqual([r['contact_edge_margin_recorded_budget_mm'] for r in rec['clamps']],
                         [c['contact_edge_margin_worst_mm'] for c in m['clamps']])
        self.assertTrue(any(r['contact_edge_margin_with_plate_float_mm']<0 for r in rec['clamps']))
        self.assertIn('ASSUMED',json.dumps(rec['thickness_cases'][0]['contact_stress']))

    @unittest.skipUnless(importlib.util.find_spec('cadquery'),'CadQuery 2.7.0 not installed')
    def test_built_tip_follows_the_spec_and_a_full_size_tip_is_refused(self):
        import a7_fixture_relief as rl
        geometry=json.loads(f.native_geom.RECORD.read_text())['geometry']
        pads=f.probe_map(f.bound_r4_placement(),f.BOARD.read_text())
        rel,tips=f.candidate_design(geometry,pads)
        with self.assertRaisesRegex(ValueError,'thinner than the pin'):
            f.relief_assembly.build(rel,pads,geometry,rl,pin_tips=[None,{'contact_diameter_max_mm':1.5,'tip_length_mm':0.5}])
        wrong=f.relief_assembly.build(rel,pads,geometry,rl,pin_tips=[None,{'contact_diameter_max_mm':1.3,'tip_length_mm':0.5}])
        plan=f.relief_assembly.pin_plan(wrong,rl.BOARD,rl.BOARD_THICKNESS)
        self.assertEqual([p['contact_diameter_mm'] for p in plan],[1.5,1.3])
        self.assertLess(plan[1]['contact_edge_margin_nominal_mm'],0.275)

if __name__=='__main__':unittest.main()
