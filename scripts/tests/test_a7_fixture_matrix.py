"""The condition matrix must stay bound to one PCB, keep its failures visible and claim nothing it has not computed.

The expensive level-0 re-run lives in the `a7_fixture_matrix.py --check` CI step. These tests cover the identity
binding, the self-consistency of every recorded verdict, the negative controls (a tampered record is rejected, the
historical layout stays failed, the known geometric shortfall stays visible) and the vocabulary limits.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import a7_fixture_matrix as matrix  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RECORD = json.loads(matrix.OUTPUT.read_text())


class Identity(unittest.TestCase):
    def test_record_is_bound_to_the_current_pcb_and_inputs(self):
        self.assertEqual(matrix.check(RECORD, matrix.LEVELS[:1], rerun=False), [])
        identity = RECORD['pcb_identity']
        self.assertEqual(identity['board_sha256'], hashlib.sha256(matrix.BOARD.read_bytes()).hexdigest())
        self.assertEqual(identity['native_geometry_sha256'], hashlib.sha256(matrix.NATIVE.read_bytes()).hexdigest())
        self.assertTrue(identity['board_identity_bound'])
        self.assertIn('--rebind', identity['rebind_command'])
        self.assertIn('a7_fixture_geometry.py --from-zip', identity['rebind_prerequisite'])

    def test_a_different_board_invalidates_the_record(self):
        tampered = copy.deepcopy(RECORD)
        tampered['pcb_identity']['board_sha256'] = '0' * 64
        problems = matrix.check(tampered, matrix.LEVELS[:1], rerun=False)
        self.assertTrue(any('board_sha256' in p for p in problems), problems)

    def test_rewritten_status_or_verdict_is_rejected(self):
        for mutate, expect in (
            (lambda r: r.__setitem__('status', 'ACCEPTED'), 'status rewritten'),
            (lambda r: r['layouts']['optical_full_pin']['cases'][0].__setitem__('probe_displacement_within_limit', True)
             if not r['layouts']['optical_full_pin']['cases'][0]['probe_displacement_within_limit'] else
             r['layouts']['historical_plunger_pair']['verdict'].__setitem__('all_recorded_limits_met', True),
             'verdict'),
            (lambda r: r['layouts']['optical_full_pin']['cases'][0].__setitem__('probe_displacement_margin_mm', 9.0),
             'margin'),
            (lambda r: r['layouts']['optical_full_pin']['force_band_per_thickness'][0].__setitem__('force_feasible', False),
             'force verdict'),
        ):
            tampered = copy.deepcopy(RECORD)
            mutate(tampered)
            problems = matrix.check(tampered, matrix.LEVELS[:1], rerun=False)
            self.assertTrue(any(expect in p for p in problems), (expect, problems))


class RecordedFailuresStayVisible(unittest.TestCase):
    def test_the_historical_layout_is_still_recorded_as_failing(self):
        layout = RECORD['layouts']['historical_plunger_pair']
        self.assertFalse(layout['verdict']['all_recorded_limits_met'])
        self.assertFalse(layout['verdict']['deflection_within_limit_every_corner'])
        self.assertGreater(layout['verdict']['worst_probe_displacement_mm'], RECORD['limits']['deflection_limit_mm'])
        self.assertGreater(layout['verdict']['worst_land_lift_mm'], RECORD['limits']['land_lift_limit_mm'])
        self.assertEqual(layout['relief_layout_status'], 'REJECTED_INSUFFICIENT_FORCE')

    def test_the_one_dimensional_strip_result_is_not_retracted(self):
        for layout in RECORD['layouts'].values():
            strip = layout['strip_model_comparison']
            self.assertGreater(strip['deflection_mm'], strip['limit_mm'])
            self.assertIn('not retracted', strip['relation'])

    def test_the_candidate_geometry_shortfall_stays_visible(self):
        geometry = RECORD['geometry']
        self.assertFalse(geometry['every_clamp_meets_recorded_site_rules'])
        self.assertLess(geometry['minimum_pin_edge_margin_worst_mm'], geometry['pin_edge_margin_required_mm'])
        self.assertIn('board-edge margin', RECORD['alternative_clamp_sites']['shortfall'])

    def test_no_alternative_is_presented_as_adopted(self):
        alternatives = RECORD['alternative_clamp_sites']
        self.assertIn('NOT ADOPTED', alternatives['status'])
        best = alternatives['best_solved_alternative']
        self.assertFalse(best['meets_recorded_limits_at_this_corner'])
        self.assertGreater(best['land_lift_max_mm'], RECORD['limits']['land_lift_limit_mm'])


class CurrentCandidate(unittest.TestCase):
    def test_every_thickness_and_force_corner_is_present(self):
        layout = RECORD['layouts']['optical_full_pin']
        self.assertEqual(RECORD['thicknesses_mm'], [0.7, 0.8, 0.9])
        for thickness in RECORD['thicknesses_mm']:
            rows = [r for r in layout['cases'] if r['thickness_mm'] == thickness]
            self.assertEqual(len(rows), 8, thickness)  # 2 clamps x {min, max} x probe {min, max}
            bands = {tuple(r['clamp_forces_N']) for r in rows}
            self.assertEqual(len(bands), 4, thickness)
            self.assertEqual({r['probe_force_each_N'] for r in rows},
                             {RECORD['force_inputs']['probe_force_each_N']['minimum_at_acceptance_stroke'],
                              RECORD['force_inputs']['probe_force_each_N']['maximum_stroke']})

    def test_contact_conditions_and_equilibrium_hold_in_every_recorded_case(self):
        for name, layout in RECORD['layouts'].items():
            for row in layout['cases']:
                self.assertGreaterEqual(row['min_gap_mm'], -1e-9, (name, row['thickness_mm']))
                self.assertGreaterEqual(row['min_reaction_N'], -1e-6, (name, row['thickness_mm']))
                self.assertLess(row['complementarity_max_N_mm'], 1e-6, (name, row['thickness_mm']))
                self.assertLess(abs(row['force_balance_N']), 1e-5, (name, row['thickness_mm']))
                self.assertLess(row['equilibrium_residual_max_N'], 1e-5, (name, row['thickness_mm']))
                self.assertGreaterEqual(row['contact_nodes'], 3, (name, row['thickness_mm']))

    def test_the_mesh_study_is_recorded_and_converged(self):
        for name, layout in RECORD['layouts'].items():
            self.assertEqual(len(layout['convergence']), len(RECORD['thicknesses_mm']), name)
            for entry in layout['convergence']:
                self.assertGreaterEqual(len(entry['series']), 2, (name, entry['thickness_mm']))
                meshes = [tuple(s['mesh']) for s in entry['series']]
                self.assertEqual(meshes, sorted(meshes), (name, 'mesh sequence must refine'))
                self.assertLessEqual(entry['final_relative_change'], RECORD['limits']['relative_convergence_limit'],
                                     (name, entry['thickness_mm']))
                self.assertTrue(entry['converged_within_recorded_limit'])

    def test_the_two_solvers_are_cross_checked(self):
        for name, layout in RECORD['layouts'].items():
            cross = layout['solver_cross_check']
            self.assertIsNotNone(cross, name)
            self.assertNotEqual(cross['flexibility_method'], cross['stiffness_method'])
            self.assertLess(cross['max_displacement_difference_mm'], 1e-7, name)
            self.assertEqual(cross['contact_node_difference'], 0, name)


class ClaimLimits(unittest.TestCase):
    def test_the_record_does_not_claim_acceptance_or_measurement(self):
        self.assertEqual(RECORD['status'], 'EXPERIMENTAL_CALCULATED_NOT_VALIDATED')
        text = json.dumps(RECORD)
        for word in ('VERIFIED', 'MEASURED', 'APPROVED', 'RELEASE_OK'):
            self.assertNotIn(word, text)
        for phrase in ('fixture acceptance or release', 'manufacturing or order approval'):
            self.assertIn(phrase, RECORD['not_evidence_for'])
        self.assertTrue(any('Physical contact and load validation' in item for item in RECORD['remaining']))
        self.assertTrue(any('final routed 0.8 mm controller' in item for item in RECORD['remaining']))

    def test_assumed_inputs_are_labelled(self):
        material = RECORD['model']['material']
        self.assertIn('ASSUMED', material['modulus_class'])
        self.assertIn('ASSUMED', material['poisson_class'])
        self.assertTrue(any('not yet placed' in a or 'no board has been measured' in a for a in RECORD['assumptions']))


if __name__ == '__main__':
    unittest.main()
