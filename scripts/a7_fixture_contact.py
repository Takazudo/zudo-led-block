"""Unilateral plate-on-rigid-land contact solve for the A7 fixture study; a calculation, never an acceptance.

Model: Kirchhoff plate (a7_fixture_plate.Plate, Bogner-Fox-Schmit C1 elements) resting on a rigid flat
land that can only push up. Unknown u with w >= 0 at every land node, reaction r >= 0 there and w * r = 0
(Signorini conditions, node-wise). Positive w and positive force are up (towards the F face).

Two independent solvers are kept so one can check the other:

- ContactModel: flexibility form. Three w DOFs are pinned only to remove the rigid-body modes; the
  stiffness is factorised once per mesh and thickness. u = K_p^-1 (f + E_A r) + R a, with R the three
  rigid-body modes, r the land reactions on the contact set A and a chosen so that the pins carry no
  load (R^T (f + E_A r) = 0). The contact set is found by a primal active-set method: start from
  u = 0, move towards the solution of the current set, stop at the first land node that would be
  penetrated and add it, release the most tensile reaction when the set's solution is admissible.
  Every iterate is admissible, so the method is the textbook one for a convex quadratic programme.
- solve_reference: stiffness form. Sparse LU of the constrained stiffness for each trial contact set
  (primal-dual active set, falling back to Plate.solve). Slow; used on coarse meshes to cross-check.

Neither returns an unconverged result: the Signorini conditions are re-evaluated from K u - f, not from
the solver's own multipliers, and a violation raises.

With zero initial gap the problem is positively homogeneous: scaling the stiffness by c scales w by 1/c
and leaves the contact set and the reactions unchanged, so deflection scales with 1 / (E t^3) for a
fixed load set. Tests check this instead of assuming it.

Not modelled: board bow or warp (initial gap), transverse shear, orthotropy, copper, holes, component
stiffening, land or pin compliance, friction. See engineering/a7/fixture/condition-matrix.md.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.sparse.linalg import splu

GAP_TOL_MM = 1e-9
# relative to the total applied load (see load_scale); small enough that a node the solver keeps in contact stays inside
# the absolute -1e-6 N the condition matrix requires of every recorded case at these loads (about 22 N)
REACTION_TOL_N = 2e-8
VERIFY_SLACK = 10.0


def land_dofs(plate, land):
    """w DOF of every mesh node that carries material and lies on the land predicate."""
    return np.array([4 * n for n, xy in enumerate(plate.xy) if 4 * n in plate.used_dofs and land(*xy)], dtype=int)


def patch_load(plate, centre, radius, total, radial=6, angular=48):
    """Uniform pressure over a disc of the given radius, as a consistent nodal load vector.

    The disc is integrated in polar coordinates (Gauss in r with the r dr weight, uniform in theta),
    so the quadrature covers the disc itself rather than the cells that happen to meet it, and the
    load's resultant sits at the disc centre. Points are mapped into whichever element contains them,
    which keeps the rule valid across element boundaries. The vector is scaled so the total force is
    exact. A contact patch is closer to a pressed pin or probe tip than a point load and has no
    singular bending; `Plate.point_load` stays available for the conservative comparison.
    """
    from a7_fixture_plate import shape as shape_fn
    cx, cy = centre
    nodes, weights = np.polynomial.legendre.leggauss(radial)
    f = np.zeros(plate.size)
    mass = 0.0
    for rn, rw in zip(nodes, weights):
        r = radius * (rn + 1) / 2
        jac = rw * radius / 2 * r * (2 * math.pi / angular)
        for k in range(angular):
            theta = 2 * math.pi * (k + 0.5) / angular
            gx, gy = cx + r * math.cos(theta), cy + r * math.sin(theta)
            if not (0 <= gx <= plate.width and 0 <= gy <= plate.height):
                raise ValueError(f'load patch at {centre} (radius {radius} mm) leaves the plate domain')
            i = min(int(gx / plate.hx), plate.nx - 1)
            j = min(int(gy / plate.hy), plate.ny - 1)
            ids = plate.ids(i, j)
            if not set(ids.tolist()) <= plate.used_dofs:
                continue
            f[ids] += shape_fn(gx / plate.hx - i, gy / plate.hy - j, plate.hx, plate.hy) * jac
            mass += jac
    if mass <= 0:
        raise ValueError(f'mesh does not resolve the load patch at {centre} (radius {radius} mm)')
    return f * (total / mass)


def load_scale(force):
    """Total applied transverse load in N: the reference magnitude every force tolerance is relative to."""
    return max(1.0, float(np.abs(force[::4]).sum()))


def _verify(plate, force, candidates, u, method, iterations):
    """Signorini conditions and equilibrium from the stiffness matrix; raises instead of returning a bad result."""
    cand = np.asarray(candidates, dtype=int)
    reaction = plate.k @ u - force
    gap, rc = u[cand], reaction[cand]
    scale = load_scale(force)
    other = np.zeros(plate.size, dtype=bool)
    other[sorted(plate.used_dofs)] = True
    other[cand] = False
    residual = float(np.abs(reaction[other]).max()) if other.any() else 0.0
    comp = float(np.abs(gap * rc).max())
    # the verifier recomputes the reactions from the sparse stiffness product, so its round-off differs from the
    # solver's own release test; it must therefore allow more slack (VERIFY_SLACK) than that test, or a correct
    # solve can fail verification on arithmetic alone
    if (gap.min() < -GAP_TOL_MM or rc.min() < -VERIFY_SLACK * REACTION_TOL_N * scale
            or residual > VERIFY_SLACK * 1e-6 * scale or comp > VERIFY_SLACK * 1e-7 * scale):
        raise ArithmeticError(f'{method}: contact conditions violated (gap {gap.min():.3e} mm, reaction {rc.min():.3e} N, '
                              f'equilibrium {residual:.3e} N, complementarity {comp:.3e} N mm)')
    active = cand[rc > REACTION_TOL_N * scale]
    lo, hi = plate.displacement_bounds(u)
    xy = np.array(plate.xy)
    w_force = force[::4]
    return {'u': u, 'reaction': reaction, 'active': active.tolist(), 'iterations': iterations, 'method': method,
            'max_up_mm': hi, 'max_down_mm': -lo,
            'contact_nodes': int(len(active)), 'land_nodes': int(len(cand)),
            'land_reaction_total_N': float(rc.sum()),
            'min_gap_mm': float(gap.min()), 'min_reaction_N': float(rc.min()),
            'complementarity_max_N_mm': comp, 'equilibrium_residual_max_N': residual,
            'force_balance_N': float(rc.sum() + w_force.sum()),
            'moment_balance_N_mm': [float((xy[cand // 4, a] * rc).sum() + (xy[:, a] * w_force).sum() + force[1 + a::4].sum())
                                    for a in (0, 1)]}


class ContactModel:
    """One mesh and thickness; reusable for any number of load cases."""

    def __init__(self, plate, candidates):
        self.plate = plate
        self.cand = np.asarray(candidates, dtype=int)
        if len(set(self.cand.tolist())) < 3:
            raise ValueError('at least three land nodes are required')
        nx, ny = plate.nx, plate.ny
        # pins only remove the rigid-body modes; the solution does not depend on them (checked by a test)
        pins = [0, 4 * nx, 4 * (ny * (nx + 1))]
        if not all(p in plate.used_dofs for p in pins):
            raise ValueError('rigid-body pins must lie on material')
        self.pins = pins
        keep = np.array(sorted(plate.used_dofs - set(pins)), dtype=int)
        self.keep = keep
        self.lu = splu(plate.k[keep, :][:, keep].tocsc())
        xy = np.array(plate.xy)
        rigid = np.zeros((plate.size, 3))
        rigid[0::4, 0] = 1.0
        rigid[0::4, 1], rigid[1::4, 1] = xy[:, 0], 1.0
        rigid[0::4, 2], rigid[2::4, 2] = xy[:, 1], 1.0
        self.rigid = rigid
        self.rigid_c = rigid[self.cand]
        self.index = {int(d): i for i, d in enumerate(self.cand)}
        self.columns = {}

    def flexibility(self, load):
        u = np.zeros(self.plate.size)
        u[self.keep] = self.lu.solve(load[self.keep])
        return u

    def column(self, dof):
        if dof not in self.columns:
            e = np.zeros(self.plate.size)
            e[dof] = 1.0
            self.columns[dof] = self.flexibility(e)
        return self.columns[dof]

    def seed(self):
        """Three well separated land nodes: a starting contact set that fixes the rigid-body modes."""
        xy = np.array(self.plate.xy)[self.cand // 4]
        a = int(np.argmin(xy.sum(axis=1)))
        b = int(np.argmax(np.linalg.norm(xy - xy[a], axis=1)))
        v = xy[b] - xy[a]
        area = np.abs(v[0] * (xy[:, 1] - xy[a, 1]) - v[1] * (xy[:, 0] - xy[a, 0]))
        c = int(np.argmax(area))
        if area[c] < 1e-9:
            raise ValueError('land nodes are collinear')
        return [int(self.cand[i]) for i in (a, b, c)]

    def _set_solution(self, active, uf_c, moment):
        """Reactions and rigid motion for contact set `active`; returns (r, a, w at the land nodes)."""
        idx = [self.index[d] for d in active]
        cols = np.column_stack([self.column(d)[self.cand] for d in active])
        g = cols[idx, :]
        ra = self.rigid_c[idx, :]
        n = len(active)
        lhs = np.zeros((n + 3, n + 3))
        lhs[:n, :n], lhs[:n, n:], lhs[n:, :n] = g, ra, ra.T
        sol = np.linalg.solve(lhs, np.concatenate([-uf_c[idx], -moment]))
        r, a = sol[:n], sol[n:]
        w = uf_c + cols @ r + self.rigid_c @ a
        w[idx] = 0.0
        return r, a, w

    def solve(self, force, initial_active=None, max_iterations=4000):
        cand = self.cand
        uf = self.flexibility(force)
        uf_c = uf[cand]
        moment = self.rigid.T @ force
        scale = load_scale(force)
        active = [int(d) for d in (self.seed() if initial_active is None else initial_active)]
        if not set(active) <= set(self.index) or len(set(active)) != len(active):
            raise ValueError('initial contacts must be distinct land nodes')
        w = np.zeros(len(cand))  # admissible start: board flat on the land
        for iteration in range(1, max_iterations + 1):
            try:
                r, a, target = self._set_solution(active, uf_c, moment)
            except np.linalg.LinAlgError:
                raise ArithmeticError('contact set does not restrain the rigid-body modes') from None
            direction = target - w
            inactive = np.ones(len(cand), dtype=bool)
            inactive[[self.index[d] for d in active]] = False
            blocking = inactive & (direction < 0) & (target < -GAP_TOL_MM)
            if blocking.any():
                steps = np.where(blocking, -w / np.where(blocking, direction, -1.0), np.inf)
                hit = int(np.argmin(steps))
                alpha = min(1.0, max(0.0, float(steps[hit])))
                w = w + alpha * direction
                w[hit] = 0.0
                active.append(int(cand[hit]))
                continue
            w = target
            if r.min() >= -REACTION_TOL_N * scale:
                u = uf + self.rigid @ a
                for d, rj in zip(active, r):
                    u = u + rj * self.column(d)
                return _verify(self.plate, force, cand, u, 'flexibility primal active set', iteration)
            if len(active) <= 3:
                raise ArithmeticError('loads lift the board off every admissible three-point contact set')
            active.pop(int(np.argmin(r)))
        raise ArithmeticError('active-set iteration limit reached')


def solve_reference(plate, force, candidates, max_iterations=400):
    """Independent stiffness-form solve (slow): primal-dual active set, then Plate.solve when it cycles."""
    cand = np.asarray(candidates, dtype=int)
    cset = set(cand.tolist())
    used = np.array(sorted(plate.used_dofs), dtype=int)
    scale = load_scale(force)
    active, seen = set(cset), set()
    for iteration in range(1, max_iterations + 1):
        key = frozenset(active)
        if key in seen or len(active) < 3:
            break
        seen.add(key)
        mask = np.ones(plate.size, dtype=bool)
        mask[list(active)] = False
        free = used[mask[used]]
        u = np.zeros(plate.size)
        try:
            u[free] = splu(plate.k[free, :][:, free].tocsc()).solve(force[free])
        except RuntimeError:
            break
        reaction = plate.k @ u - force
        act = np.array(sorted(active), dtype=int)
        tensile = act[reaction[act] < -REACTION_TOL_N * scale]
        opened = np.array(sorted(cset - active), dtype=int)
        penetrating = opened[u[opened] < -GAP_TOL_MM] if len(opened) else opened
        if not len(tensile) and not len(penetrating):
            return _verify(plate, force, cand, u, 'stiffness primal-dual active set', iteration)
        active = (active - set(tensile.tolist())) | set(penetrating.tolist())
    points = {plate.xy[d // 4] for d in cset}
    support = lambda x, y: (x, y) in points  # noqa: E731
    res = plate.solve(force, support, unilateral=True, max_iterations=20000, initial_active=plate.seed_contacts(support))
    return _verify(plate, force, cand, res['u'], 'stiffness single-exchange active set', res['iterations'])
