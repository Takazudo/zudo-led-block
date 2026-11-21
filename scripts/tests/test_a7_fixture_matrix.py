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
        self.assertIn('--from-dir', identity['rebind_prerequisite'])
        # the record names the provenance class of the native geometry it is bound to, so a local run cannot read as CI
        native = json.loads(matrix.NATIVE.read_text())['provenance']
        self.assertEqual(identity['native_geometry_provenance_class'], native['provenance_class'])
        self.assertIn(native['provenance_class'], ('CI_RETAINED_ARTIFACT', 'LOCAL_PINNED_IMAGE_RUN'))

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
    def test_the_required_clamp_force_is_the_probe_force_times_the_margin_factor(self):
        fi = RECORD['force_inputs']
        self.assertAlmostEqual(RECORD['limits']['required_total_clamp_force_N'],
                               fi['clamp_force_margin_factor'] * fi['probe_force_each_N']['maximum_stroke'] * fi['probe_count'],
                               places=6)
        self.assertEqual(fi['probe_count'], 5)

    def test_every_thickness_and_force_corner_is_present(self):
        self.assertEqual(RECORD['thicknesses_mm'], [0.7, 0.8, 0.9])
        for name in ('optical_full_pin', matrix.ADOPTED_LAYOUT):
            self._corners_present(RECORD['layouts'][name])

    def _corners_present(self, layout):
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


class AdoptedCandidate(unittest.TestCase):
    """The stepped-tip candidate must meet every recorded rule with the recorded limits, and claim no more than that."""
    A = RECORD['adopted_candidate']

    def test_no_recorded_limit_was_moved_to_adopt_it(self):
        self.assertEqual(self.A['pin_edge_margin_required_mm'], 0.15)
        self.assertEqual(matrix.PIN_EDGE_MARGIN_REQUIRED_MM, 0.15)
        self.assertEqual(RECORD['limits']['deflection_limit_mm'], 0.1)
        self.assertEqual(RECORD['limits']['land_lift_limit_mm'], 0.1)
        self.assertAlmostEqual(RECORD['limits']['required_total_clamp_force_N'], 12.7, places=6)

    def test_same_sites_and_plungers_only_the_second_contact_is_smaller(self):
        layout = RECORD['layouts'][matrix.ADOPTED_LAYOUT]
        self.assertEqual(self.A['layout'], matrix.ADOPTED_LAYOUT)
        self.assertEqual(layout['clamps_board_mm'], RECORD['layouts']['optical_full_pin']['clamps_board_mm'])
        self.assertEqual(layout['clamp_contact_diameters_mm'], [1.5, 1.2])
        self.assertEqual(RECORD['layouts']['optical_full_pin']['clamp_contact_diameters_mm'], [1.5, 1.5])
        self.assertEqual([c['stepped_tip'] for c in self.A['clamps']], [False, True])

    def test_every_contact_keeps_the_required_edge_margin(self):
        for clamp in self.A['clamps']:
            x = clamp['centre_mm'][0]
            # independent re-derivation: nearer long edge, minus the contact radius, the 0.10 mm relative pin tolerance
            # and, on the low-x side only, the 0.20 mm board-profile allowance
            expected = min(x, 16.2 - x) - clamp['contact_diameter_mm'] / 2 - 0.10 - (0.20 if x < 8.1 else 0.0)
            self.assertAlmostEqual(clamp['contact_edge_margin_worst_mm'], expected, places=6)
            self.assertGreaterEqual(clamp['contact_edge_margin_worst_mm'], 0.15 - 1e-9)
            self.assertTrue(clamp['meets_recorded_site_rules'])
            self.assertTrue(clamp['shank_inside_board_outline_worst_case'])
        # the shank of the stepped pin is still the 0.025 mm case: reported, not hidden
        self.assertAlmostEqual(self.A['clamps'][1]['shank_edge_margin_worst_mm'], 0.025, places=6)

    def test_every_load_corner_meets_the_recorded_limits(self):
        layout = RECORD['layouts'][matrix.ADOPTED_LAYOUT]
        self.assertEqual(len(layout['cases']), 24)
        for row in layout['cases']:
            self.assertLessEqual(row['probe_displacement_max_abs_mm'], RECORD['limits']['deflection_limit_mm'])
            self.assertLessEqual(row['land_lift_max_mm'], RECORD['limits']['land_lift_limit_mm'])
        for band in layout['force_band_per_thickness']:
            self.assertGreaterEqual(band['total_minimum_N'], RECORD['limits']['required_total_clamp_force_N'])
            self.assertTrue(band['within_stroke'] and band['compression_positive'])
        self.assertTrue(layout['verdict']['all_recorded_limits_met'])
        self.assertTrue(self.A['all_recorded_rules_met'])

    def test_contact_pressure_is_checked_against_an_allowable_labelled_assumed(self):
        self.assertEqual(self.A['contact_allowable']['class'], 'ASSUMED')
        self.assertIn('NOT sourced', self.A['contact_allowable']['basis'])
        for clamp in self.A['clamps']:
            stress = clamp['contact_stress']
            area = 3.141592653589793 * (clamp['contact_diameter_mm'] / 2) ** 2
            self.assertAlmostEqual(stress['mean_contact_pressure_MPa'], stress['force_max_N'] / area, places=4)
            self.assertEqual(stress['force_max_N'], max(b['clamp_force_each_N'][1] for b in
                                                        RECORD['layouts'][matrix.ADOPTED_LAYOUT]['force_band_per_thickness']))
            self.assertLessEqual(stress['mean_contact_pressure_MPa'], self.A['contact_allowable']['value_MPa'])

    def test_it_is_a_candidate_not_an_acceptance(self):
        self.assertIn('NOT ACCEPTED', self.A['status'])
        self.assertIn('PROPOSED', self.A['stepped_tip']['status'])
        self.assertIn('that the modified pin can be made or bought', self.A['not_shown_by_this'])
        self.assertEqual([o['option'] for o in self.A['options_considered']], ['a', 'b', 'c'])

    def test_a_tampered_adopted_block_is_rejected(self):
        for mutate in (
            lambda a: a['clamps'][1].__setitem__('contact_edge_margin_worst_mm', 0.3),
            lambda a: a['clamps'][1]['contact_stress'].__setitem__('mean_contact_pressure_MPa', 1.0),
            lambda a: a['contact_allowable'].__setitem__('value_MPa', 200.0),
            lambda a: a.__setitem__('pin_edge_margin_required_mm', 0.02),
            lambda a: a.__setitem__('layout', 'optical_full_pin'),
        ):
            tampered = copy.deepcopy(RECORD)
            mutate(tampered['adopted_candidate'])
            problems = matrix.check(tampered, matrix.LEVELS[:1], rerun=False)
            self.assertTrue(any('adopted candidate' in p for p in problems), problems)

    def test_a_contact_wider_than_the_margin_allows_would_fail_the_site_rule(self):
        # sensitivity control on the rule itself: the catalogue 1.5 mm end at the second site is the recorded failure
        native, geometry, probes = matrix.geometry_and_probes()
        rules = matrix.SiteRules(geometry, probes)
        centre = tuple(self.A['clamps'][1]['centre_mm'])
        self.assertFalse(rules.row(centre, 1.5)['meets_recorded_site_rules'])
        self.assertFalse(rules.row(centre, 1.3)['meets_recorded_site_rules'])
        self.assertTrue(rules.row(centre, 1.2)['meets_recorded_site_rules'])


class ClaimLimits(unittest.TestCase):
    def test_the_record_does_not_claim_acceptance_or_measurement(self):
        self.assertEqual(RECORD['status'], 'EXPERIMENTAL_CALCULATED_NOT_VALIDATED')
        text = json.dumps(RECORD)
        for word in ('VERIFIED', 'MEASURED', 'APPROVED', 'RELEASE_OK'):
            self.assertNotIn(word, text)
        for phrase in ('fixture acceptance or release', 'manufacturing or order approval'):
            self.assertIn(phrase, RECORD['not_evidence_for'])
        self.assertTrue(any('Physical contact and load validation' in item for item in RECORD['remaining']))
        # the native geometry is now taken from the adopted routed 0.8 mm board, so the open item is its provenance:
        # a local gate run must keep asking for a CI-retained artifact, and only a CI-bound record may drop that item
        names_ci_retake = any('CI-retained artifact' in item for item in RECORD['remaining'])
        if RECORD['pcb_identity']['native_geometry_provenance_class'] == 'LOCAL_PINNED_IMAGE_RUN':
            self.assertTrue(names_ci_retake)
        else:
            self.assertEqual(RECORD['pcb_identity']['native_geometry_provenance_class'], 'CI_RETAINED_ARTIFACT')
            self.assertFalse(names_ci_retake)

    def test_assumed_inputs_are_labelled(self):
        material = RECORD['model']['material']
        self.assertIn('ASSUMED', material['modulus_class'])
        self.assertIn('ASSUMED', material['poisson_class'])
        self.assertTrue(any('not yet placed' in a or 'no board has been measured' in a for a in RECORD['assumptions']))


if __name__ == '__main__':
    unittest.main()
