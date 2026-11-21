"""Verification of the unilateral contact solver; solver checks, not a fixture result.

Each test states an independent truth about the model: exact patch loads, the Signorini conditions, the
contact set against brute-force enumeration, agreement between the two solvers, the scaling the zero-gap
problem must obey, and that a bilateral solve is not a conservative substitute.
"""
import itertools
import math
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from a7_fixture_contact import ContactModel, land_dofs, patch_load, solve_reference  # noqa: E402
from a7_fixture_plate import Plate  # noqa: E402


def square(n=4, thickness=0.7, modulus=18000.0, size=10.0):
    return Plate(size, size, n, n, thickness, modulus, 0.3)


class PatchLoads(unittest.TestCase):
    def test_total_force_and_position_are_exact(self):
        p = square(6)
        f = patch_load(p, (4.0, 6.0), 0.75, -3.0)
        xy = np.array(p.xy)
        self.assertAlmostEqual(f[::4].sum(), -3.0, places=9)
        # first moments of a consistent load vector include the rotational DOFs
        self.assertAlmostEqual((xy[:, 0] * f[::4]).sum() + f[1::4].sum(), -3.0 * 4.0, places=7)
        self.assertAlmostEqual((xy[:, 1] * f[::4]).sum() + f[2::4].sum(), -3.0 * 6.0, places=7)

    def test_patch_is_softer_than_a_point_load_and_converges_to_it(self):
        previous = None
        for n, radius in ((8, 2.0), (8, 0.5), (8, 0.125)):
            p = square(n)
            support = lambda x, y: x in (0, 10) or y in (0, 10)  # noqa: E731
            patch = p.solve(patch_load(p, (5.0, 5.0), radius, 1.0), support)['max_up_mm']
            point = p.solve(p.point_load(5.0, 5.0, 1.0), support)['max_up_mm']
            self.assertLess(patch, point)
            if previous is not None:
                self.assertGreater(patch, previous)  # shrinking the patch approaches the point load from below
            previous = patch

    def test_a_patch_outside_the_domain_or_off_the_material_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'leaves the plate domain'):
            patch_load(square(4), (0.5, 5.0), 1.0, 1.0)
        hole = Plate(10.0, 10.0, 4, 4, 0.7, 18000.0, 0.3,
                     cell_material=lambda box: not (box[0] >= 5.0 and box[1] >= 5.0))
        with self.assertRaisesRegex(ValueError, 'does not resolve the load patch'):
            patch_load(hole, (8.75, 8.75), 0.5, 1.0)


class ContactConditions(unittest.TestCase):
    def test_corner_supports_release_under_central_uplift(self):
        p = square(2)
        corners = ((0.0, 0.0), (10.0, 0.0), (0.0, 10.0), (10.0, 10.0))
        land = land_dofs(p, lambda x, y: (x, y) in corners or (x, y) == (5.0, 5.0))
        force = p.point_load(5.0, 5.0, 0.1)
        for q in corners:
            force = force + p.point_load(*q, -1.0)
        res = ContactModel(p, land).solve(force)
        middle = [d for d in land if p.xy[d // 4] == (5.0, 5.0)][0]
        self.assertNotIn(middle, res['active'])
        self.assertGreater(res['u'][middle], 0)
        self.assertAlmostEqual(res['force_balance_N'], 0, places=7)
        for axis in (0, 1):
            self.assertAlmostEqual(res['moment_balance_N_mm'][axis], 0, places=6)

    def test_contact_set_matches_brute_force_enumeration(self):
        p = square(2)
        land = land_dofs(p, lambda x, y: (x in (0.0, 10.0) and y in (0.0, 10.0)) or (x, y) == (5.0, 5.0))
        self.assertEqual(len(land), 5)
        force = p.point_load(2.5, 2.5, -2.0) + p.point_load(7.5, 7.5, 0.4)
        got = ContactModel(p, land).solve(force)
        admissible = []
        used = np.array(sorted(p.used_dofs), dtype=int)
        for size in range(3, 6):
            for subset in itertools.combinations(land.tolist(), size):
                mask = np.ones(p.size, dtype=bool)
                mask[list(subset)] = False
                free = used[mask[used]]
                u = np.zeros(p.size)
                try:
                    from scipy.sparse.linalg import spsolve
                    u[free] = spsolve(p.k[free, :][:, free], force[free])
                except Exception:
                    continue
                if not np.all(np.isfinite(u)):
                    continue
                reaction = p.k @ u - force
                if (u[land] >= -1e-9).all() and (reaction[list(subset)] >= -1e-7).all():
                    admissible.append((set(subset), u))
        self.assertTrue(admissible, 'brute force found no admissible contact set')
        matches = [u for subset, u in admissible if np.abs(u - got['u']).max() < 1e-8]
        self.assertTrue(matches, 'the solver returned a state no admissible contact set reproduces')

    def test_loads_that_lift_the_board_are_refused_instead_of_returned(self):
        p = square(2)
        land = land_dofs(p, lambda x, y: (x, y) in ((0.0, 0.0), (10.0, 0.0), (0.0, 10.0), (10.0, 10.0)))
        with self.assertRaises(ArithmeticError):
            ContactModel(p, land).solve(p.point_load(5.0, 5.0, 5.0))

    def test_rigid_body_pins_carry_no_load(self):
        p = square(4)
        land = land_dofs(p, lambda x, y: y == 0.0 or y == 10.0)
        model = ContactModel(p, land)
        res = model.solve(p.point_load(5.0, 5.0, -1.0))
        for pin in model.pins:
            if pin not in res['active']:
                self.assertLess(abs(res['reaction'][pin]), 1e-7)

    def test_both_solvers_agree(self):
        p = square(4)
        land = land_dofs(p, lambda x, y: x in (0.0, 10.0) or y in (0.0, 10.0))
        force = patch_load(p, (3.0, 7.0), 1.0, -4.0) + patch_load(p, (7.0, 3.0), 0.5, 1.0)
        own = ContactModel(p, land).solve(force)
        ref = solve_reference(p, force, land)
        self.assertLess(np.abs(own['u'] - ref['u']).max(), 1e-9)
        self.assertEqual(own['contact_nodes'], ref['contact_nodes'])


class Scaling(unittest.TestCase):
    def test_displacement_scales_with_one_over_e_t_cubed_and_keeps_the_contact_set(self):
        results = {}
        for thickness, modulus in ((0.7, 18000.0), (0.9, 18000.0), (0.7, 36000.0)):
            p = Plate(10.0, 10.0, 4, 4, thickness, modulus, 0.3)
            land = land_dofs(p, lambda x, y: x in (0.0, 10.0) or y in (0.0, 10.0))
            force = patch_load(p, (4.0, 4.0), 1.0, -2.0) + patch_load(p, (6.0, 6.0), 1.0, 0.5)
            res = ContactModel(p, land).solve(force)
            results[(thickness, modulus)] = (res['max_down_mm'], len(res['active']), res['land_reaction_total_N'])
        base = results[(0.7, 18000.0)]
        thicker, stiffer = results[(0.9, 18000.0)], results[(0.7, 36000.0)]
        self.assertAlmostEqual(thicker[0], base[0] * (0.7 / 0.9) ** 3, places=9)
        self.assertAlmostEqual(stiffer[0], base[0] / 2, places=9)
        self.assertEqual({base[1]}, {thicker[1], stiffer[1]})
        for other in (thicker, stiffer):
            self.assertAlmostEqual(other[2], base[2], places=7)


class BilateralIsNotConservative(unittest.TestCase):
    def test_bilateral_support_hides_the_lift_a_unilateral_land_allows(self):
        p = square(4)
        land_fn = lambda x, y: x in (0.0, 10.0) or y in (0.0, 10.0)  # noqa: E731
        force = patch_load(p, (5.0, 5.0), 1.0, -3.0) + patch_load(p, (7.5, 7.5), 1.0, 1.2)
        bilateral = p.solve(force, land_fn, unilateral=False)
        unilateral = ContactModel(p, land_dofs(p, land_fn)).solve(force)
        self.assertGreater(unilateral['max_down_mm'], bilateral['max_down_mm'])
        self.assertLess(min(bilateral['reaction'][land_dofs(p, land_fn)]), -1e-6)  # the bilateral land pulls down
        self.assertGreaterEqual(unilateral['min_reaction_N'], -1e-6)


if __name__ == '__main__':
    unittest.main()
