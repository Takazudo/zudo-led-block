#!/usr/bin/env python3
"""A7 fixture condition matrix for the 0.7-0.9 mm controller: a calculation bound to one PCB identity.

What this is: every load corner of the SWD fixture hold-down solved on the real native board outline
and pad positions with a converged unilateral contact model (scripts/a7_fixture_contact.py over the
Kirchhoff plate of scripts/a7_fixture_plate.py), at the three finished thicknesses the published
0.8 +/-0.1 mm tolerance admits, on a mesh sequence that shows the discretisation error.

What this is NOT: a fixture acceptance, an optical or manufacturing release, a measured contact,
force, stroke or positioning result, or a transfer of the old 1.6 mm PASS. The record carries
`status` EXPERIMENTAL_CALCULATED_NOT_VALIDATED and every physical item stays listed in `remaining`.

Identity: the record binds the controller PCB bytes, the native geometry record derived from them and
the probe-pad manifest. `--check` fails as soon as any of them changes, so the matrix cannot be read
as evidence for a different board. One command re-runs it on the final routed controller:

    python3 scripts/a7_fixture_matrix.py --rebind

(which is `--levels all --output engineering/a7/fixture/condition-matrix.json` with the identity read
from the current bytes; the native geometry record itself must first be refreshed from a fresh native
gate with `python3 scripts/a7_fixture_geometry.py --from-zip <artifact.zip>`, otherwise the command
fails closed because the record and the board bytes disagree).
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import a7_fixture_relief as relief  # noqa: E402
from a7_fixture_contact import ContactModel, land_dofs, patch_load, solve_reference  # noqa: E402
from a7_fixture_plate import Plate  # noqa: E402
from a7_fixture_support import diagonal_proposal  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / 'engineering/a7/electronics/controller/controller.kicad_pcb'
PLACEMENT = ROOT / 'engineering/a7/electronics/controller/board_placement.json'
NATIVE = ROOT / 'engineering/a7/fixture/native-geometry.json'
MANIFEST = ROOT / 'engineering/a7/fixture/manifest.json'
OUTPUT = ROOT / 'engineering/a7/fixture/condition-matrix.json'
INPUT_FILES = ('scripts/a7_fixture_matrix.py', 'scripts/a7_fixture_contact.py', 'scripts/a7_fixture_plate.py',
               'scripts/a7_fixture_relief.py', 'scripts/a7_fixture_support.py')

# Mesh sequence for the convergence study. Level 0 is cheap enough to be re-run by --check in CI.
LEVELS = ((20, 78), (40, 156), (60, 234))
THICKNESSES = (0.7, 0.8, 0.9)
POISSON = 0.3  # ASSUMED: the laminate is not sourced, and no Poisson ratio is measured
# Layouts evaluated at every corner. The historical pair must stay in the record: a redesign may not
# silently drop the layout whose failure started it.
LAYOUTS = {
    'historical_plunger_pair': {'candidate': None,
                                'role': 'layout carried from the 1.6 mm fixture; REJECTED_INSUFFICIENT_FORCE in a7_fixture_relief'},
    'optical_full_pin': {'candidate': 'optical_full_pin',
                         'role': 'current candidate: full-diameter POM pins on opposite corners of the probe field, no support insert'},
}
RELATIVE_CONVERGENCE_LIMIT = 0.05  # recorded requirement on the finest mesh step of the governing quantity


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def r9(v):
    return round(float(v), 9)


def geometry_and_probes():
    native = json.loads(NATIVE.read_text())
    probes = json.loads(MANIFEST.read_text())['pads']
    return native, native['geometry'], probes


def land_predicate(design):
    """Carrier land under the board: inside the carrier, outside every window and every hole."""
    sc = design['support_carrier']
    holes = [(tuple(q['board_xy_mm']), relief.RULES['datum_pin_diameter_mm'] / 2) for q in sc['datum_pins']]
    holes += [(tuple(q['board_xy_mm']), relief.RULES['m3_clearance_hole_mm'] / 2) for q in sc['guides']]
    holes += [(tuple(q), relief.RULES['m3_countersink_diameter_mm'] / 2) for q in sc['fasteners_board_mm']]
    holes += [(tuple(q), relief.RULES['alignment_dowel_diameter_mm'] / 2) for q in sc['alignment_dowels_board_mm']]
    bounds = sc['bounds_board_mm']
    windows = sc['windows']

    def land(x, y):
        return (relief._in_box(bounds, x, y)
                and not any(relief._in_window(w, x, y) for w in windows)
                and all(math.hypot(x - q[0], y - q[1]) > r for q, r in holes))
    return land, holes


def force_inputs(design):
    """Probe and plunger force bands exactly as a7_fixture_relief derives them, with their sources."""
    pf = relief.INGUN['probe']['facts']
    f_work = pf['force_at_working_stroke_N']
    probe_min = pf['spring_preload_N'] + (f_work - pf['spring_preload_N']) / pf['working_stroke_mm'] * (pf['working_stroke_mm'] - 0.3)
    probe_max = relief.INGUN['force_graph']['facts']['force_at_maximum_stroke_N']
    hd = design['holddown']
    comp = hd['plunger_compression_mm']
    pl = relief.PLUNGER_CANDIDATE
    return {'probe_force_each_N': {'minimum_at_acceptance_stroke': r9(probe_min), 'maximum_stroke': r9(probe_max),
                                   'source': 'INGUN GKS-050 214 050 A 1000 datasheet and force graph (a7_fixture_relief.INGUN)'},
            'probe_count': len(json.loads(MANIFEST.read_text())['pads']),
            'required_total_clamp_force_N': r9(relief.RULES['clamp_force_margin_factor'] * probe_max
                                               * len(json.loads(MANIFEST.read_text())['pads'])),
            'clamp_force_margin_factor': relief.RULES['clamp_force_margin_factor'],
            'plunger': {'mpn': pl['mpn'], 'stroke_mm': pl['stroke_mm'], 'force_initial_N': pl['force_initial_N'],
                        'force_final_N': pl['force_final_N'], 'acceptance_band': relief.RULES['plunger_force_acceptance_band'],
                        'pin_diameter_mm': pl['pin_diameter_mm'],
                        'force_class': pl['force_class']},
            'compression': {'nominal_mm': comp['nominal'], 'tolerance_stack_mm': comp['stack_mm'],
                            'pressure_plate_deflection_mm': comp['plate_deflection_mm'],
                            'stroke_end_margin_mm': relief.RULES['plunger_stroke_end_margin_mm'],
                            'basis': 'displacement control: stop height, board thickness and plunger setting fix each '
                                     'compression (a7_fixture_relief.design -> holddown)'}}


def plunger_force(d):
    pl = relief.PLUNGER_CANDIDATE
    return pl['force_initial_N'] + (pl['force_final_N'] - pl['force_initial_N']) * d / pl['stroke_mm']


def compression_band(sag_mm, plate_deflection_mm):
    """Compression range of one plunger for a board that sags `sag_mm` away from the pin."""
    pl = relief.PLUNGER_CANDIDATE
    stack = (relief.RULES['board_thickness_tolerance_mm'] + relief.RULES['plate_stack_acceptance_tolerance_mm']
             + relief.RULES['plunger_setting_tolerance_mm'])
    d_nom = pl['stroke_mm'] - relief.RULES['plunger_stroke_end_margin_mm'] - stack
    return d_nom - stack - plate_deflection_mm - sag_mm, d_nom + stack


class Case:
    """One mesh and thickness; solves any force corner of one clamp layout."""

    def __init__(self, nx, ny, thickness, land, probes, clamps, modulus):
        self.plate = Plate(16.2, 62.9, nx, ny, thickness, modulus, POISSON)
        self.land = land_dofs(self.plate, land)
        self.model = ContactModel(self.plate, self.land)
        self.probes = probes
        self.clamps = clamps
        self.probe_radius = relief.INGUN['probe']['facts']['tip_diameter_mm'] / 2
        self.clamp_radius = relief.PLUNGER_CANDIDATE['pin_diameter_mm'] / 2
        self.probe_vectors = [patch_load(self.plate, tuple(p['board_xy_mm']), self.probe_radius, 1.0) for p in probes]
        self.clamp_vectors = [patch_load(self.plate, tuple(q), self.clamp_radius, -1.0) for q in clamps]

    def solve(self, clamp_forces, probe_force):
        force = np.zeros(self.plate.size)
        for v, f in zip(self.clamp_vectors, clamp_forces):
            force = force + v * f
        for v in self.probe_vectors:
            force = force + v * probe_force
        started = time.monotonic()
        res = self.model.solve(force)
        u = res['u']
        probe_w = [self.plate.value(*p['board_xy_mm'], u) for p in self.probes]
        clamp_w = [self.plate.value(*q, u) for q in self.clamps]
        land_w = u[self.land]
        return {'probe_displacement_mm': [r9(v) for v in probe_w],
                'clamp_displacement_mm': [r9(v) for v in clamp_w],
                'probe_displacement_max_abs_mm': r9(max(abs(v) for v in probe_w)),
                'clamp_sag_max_mm': r9(max(0.0, max(-v for v in clamp_w))),
                'board_max_up_mm': r9(res['max_up_mm']), 'board_max_down_mm': r9(res['max_down_mm']),
                'land_lift_max_mm': r9(land_w.max()),
                'contact_nodes': res['contact_nodes'], 'land_nodes': res['land_nodes'],
                'iterations': res['iterations'], 'method': res['method'],
                'min_gap_mm': r9(res['min_gap_mm']), 'min_reaction_N': r9(res['min_reaction_N']),
                'complementarity_max_N_mm': r9(res['complementarity_max_N_mm']),
                'equilibrium_residual_max_N': r9(res['equilibrium_residual_max_N']),
                'force_balance_N': r9(res['force_balance_N']),
                'moment_balance_N_mm': [r9(v) for v in res['moment_balance_N_mm']],
                'land_reaction_total_N': r9(res['land_reaction_total_N']),
                'seconds': round(time.monotonic() - started, 3)}


def corners(clamp_band, probe_band, n_clamps):
    for cf in itertools.product(clamp_band, repeat=n_clamps):
        for pf in probe_band:
            yield list(cf), pf


def evaluate_layout(name, spec, geometry, probes, levels, modulus, limits, cross_check=False):
    design = relief.design(geometry, probes, candidate=spec['candidate'])
    land, _ = land_predicate(design)
    clamps = [list(q) for q in design['holddown']['contacts_board_mm']]
    plate_deflection = design['holddown']['plunger_compression_mm']['plate_deflection_mm']
    probe_min = design['holddown']['probe_force_total_N']['minimum_at_acceptance_stroke'] / len(probes)
    probe_max = relief.INGUN['force_graph']['facts']['force_at_maximum_stroke_N']
    required = limits['required_total_clamp_force_N']
    rows, thickness_rows, cross = [], [], None
    for thickness in THICKNESSES:
        case = Case(*levels[0], thickness, land, probes, clamps, modulus)
        # the sag that is lost from the plunger compression is largest at the maximum plunger force
        # and the minimum probe force; the force band therefore follows from one bounding solve
        probe_sag = case.solve([relief.PLUNGER_CANDIDATE['force_final_N'] * (1 + limits['plunger_band'])] * len(clamps), probe_min)
        sag = probe_sag['clamp_sag_max_mm']
        d_min, d_max = compression_band(sag, plate_deflection)
        f_min = plunger_force(d_min) * (1 - limits['plunger_band'])
        f_max = plunger_force(d_max) * (1 + limits['plunger_band'])
        band = (r9(f_min), r9(f_max))
        thickness_rows.append({'thickness_mm': thickness, 'clamp_sag_at_maximum_force_mm': sag,
                               'compression_range_mm': [r9(d_min), r9(d_max)],
                               'clamp_force_each_N': list(band),
                               'total_minimum_N': r9(len(clamps) * f_min), 'required_total_N': required,
                               'force_margin_N': r9(len(clamps) * f_min - required),
                               'force_feasible': len(clamps) * f_min >= required,
                               'compression_positive': d_min > 0,
                               'within_stroke': d_max <= relief.PLUNGER_CANDIDATE['stroke_mm'] - relief.RULES['plunger_stroke_end_margin_mm'] + 1e-9})
        for cf, pf in corners(band, (r9(probe_min), r9(probe_max)), len(clamps)):
            res = case.solve(cf, pf)
            rows.append({'layout': name, 'thickness_mm': thickness, 'mesh': list(levels[0]), 'level': 0,
                         'clamp_forces_N': cf, 'probe_force_each_N': pf, **res,
                         'probe_displacement_margin_mm': r9(limits['deflection_limit_mm'] - res['probe_displacement_max_abs_mm']),
                         'probe_displacement_within_limit': res['probe_displacement_max_abs_mm'] <= limits['deflection_limit_mm'] + 1e-12,
                         'land_lift_margin_mm': r9(limits['land_lift_limit_mm'] - res['land_lift_max_mm']),
                         'land_lift_within_limit': res['land_lift_max_mm'] <= limits['land_lift_limit_mm'] + 1e-12})
        if cross_check and thickness == THICKNESSES[0]:
            worst = max((r for r in rows if r['thickness_mm'] == thickness), key=lambda r: r['probe_displacement_max_abs_mm'])
            force = np.zeros(case.plate.size)
            for v, f in zip(case.clamp_vectors, worst['clamp_forces_N']):
                force = force + v * f
            for v in case.probe_vectors:
                force = force + v * worst['probe_force_each_N']
            ref = solve_reference(case.plate, force, case.land)
            own = case.model.solve(force)
            cross = {'case': {k: worst[k] for k in ('thickness_mm', 'clamp_forces_N', 'probe_force_each_N', 'mesh')},
                     'flexibility_method': own['method'], 'stiffness_method': ref['method'],
                     'max_displacement_difference_mm': r9(np.abs(ref['u'][::4] - own['u'][::4]).max()),
                     'contact_node_difference': int(ref['contact_nodes'] - own['contact_nodes']),
                     'note': 'two independent solvers (flexibility active set, stiffness active set) on the same case'}
    # convergence: the governing corner of each thickness on the finer meshes
    convergence = []
    for thickness in THICKNESSES:
        governing = max((r for r in rows if r['thickness_mm'] == thickness), key=lambda r: r['probe_displacement_max_abs_mm'])
        series = [{'level': 0, 'mesh': list(levels[0]), 'probe_displacement_max_abs_mm': governing['probe_displacement_max_abs_mm'],
                   'clamp_sag_max_mm': governing['clamp_sag_max_mm'], 'contact_nodes': governing['contact_nodes'],
                   'min_gap_mm': governing['min_gap_mm'], 'equilibrium_residual_max_N': governing['equilibrium_residual_max_N']}]
        wanted = levels[1:] if thickness == THICKNESSES[0] else levels[1:2]
        for index, mesh in enumerate(wanted, start=1):
            case = Case(*mesh, thickness, land, probes, clamps, modulus)
            res = case.solve(governing['clamp_forces_N'], governing['probe_force_each_N'])
            series.append({'level': index, 'mesh': list(mesh), 'probe_displacement_max_abs_mm': res['probe_displacement_max_abs_mm'],
                           'clamp_sag_max_mm': res['clamp_sag_max_mm'], 'contact_nodes': res['contact_nodes'],
                           'min_gap_mm': res['min_gap_mm'], 'equilibrium_residual_max_N': res['equilibrium_residual_max_N']})
        steps = [r9(abs(b['probe_displacement_max_abs_mm'] - a['probe_displacement_max_abs_mm'])
                    / max(abs(b['probe_displacement_max_abs_mm']), 1e-12))
                 for a, b in zip(series, series[1:])]
        convergence.append({'thickness_mm': thickness, 'governing_corner': {'clamp_forces_N': governing['clamp_forces_N'],
                                                                           'probe_force_each_N': governing['probe_force_each_N']},
                            'series': series, 'relative_change_per_step': steps,
                            'final_relative_change': steps[-1] if steps else None,
                            'converged_within_recorded_limit': bool(steps and steps[-1] <= RELATIVE_CONVERGENCE_LIMIT)})
    worst_probe = max(rows, key=lambda r: r['probe_displacement_max_abs_mm'])
    worst_lift = max(rows, key=lambda r: r['land_lift_max_mm'])
    verdict = {
        'force_feasible_every_thickness': all(t['force_feasible'] for t in thickness_rows),
        'deflection_within_limit_every_corner': all(r['probe_displacement_within_limit'] for r in rows),
        'land_lift_within_limit_every_corner': all(r['land_lift_within_limit'] for r in rows),
        'compression_positive_every_thickness': all(t['compression_positive'] for t in thickness_rows),
        'within_stroke_every_thickness': all(t['within_stroke'] for t in thickness_rows),
        'contact_conditions_satisfied_every_corner': all(r['min_gap_mm'] >= -1e-9 and r['min_reaction_N'] >= -1e-6 for r in rows),
        'mesh_converged_within_recorded_limit': all(c['converged_within_recorded_limit'] for c in convergence),
        'worst_probe_displacement_mm': worst_probe['probe_displacement_max_abs_mm'],
        'worst_probe_corner': {k: worst_probe[k] for k in ('thickness_mm', 'clamp_forces_N', 'probe_force_each_N')},
        'worst_land_lift_mm': worst_lift['land_lift_max_mm'],
        'worst_land_lift_corner': {k: worst_lift[k] for k in ('thickness_mm', 'clamp_forces_N', 'probe_force_each_N')},
        'minimum_force_margin_N': min(t['force_margin_N'] for t in thickness_rows),
    }
    verdict['all_recorded_limits_met'] = all(v is True for k, v in verdict.items() if isinstance(v, bool))
    return {'role': spec['role'], 'relief_layout_status': design['holddown']['layout_status'],
            'clamps_board_mm': clamps, 'clamp_pin_diameter_mm': relief.PLUNGER_CANDIDATE['pin_diameter_mm'],
            'pressure_plate_deflection_mm': plate_deflection,
            'strip_model_comparison': {'deflection_mm': design['holddown']['board_bending_across_window']['deflection_mm'],
                                       'limit_mm': design['holddown']['board_bending_across_window']['limit_mm'],
                                       'model': design['holddown']['board_bending_across_window']['model'],
                                       'relation': 'one-dimensional screening bound kept visible beside the plate result; the '
                                                   'plate model carries the margins, the strip model is not retracted'},
            'force_band_per_thickness': thickness_rows, 'cases': rows, 'convergence': convergence,
            'solver_cross_check': cross, 'verdict': verdict}


PIN_EDGE_MARGIN_REQUIRED_MM = 0.15  # recorded requirement for a new site; the current candidate's 0.025 is below it


class SiteRules:
    """The planar rules a clamp site must satisfy, with the native data they are measured against.

    The pressed POM pin must stay wholly on the board; the Ø4 body may overhang the board edge above the F face
    (recorded sleeve-overhang allowance) but must clear every F-side courtyard; the tapped hole's finished
    thread-cut envelope must keep a wall to the J5 notch and to the pressure-plate edges.
    """

    def __init__(self, geometry, probes, edge_margin_required=None, body_diameter=None):
        self.edge_required = PIN_EDGE_MARGIN_REQUIRED_MM if edge_margin_required is None else edge_margin_required
        self.body_diameter = relief.PLUNGER_CANDIDATE['body_diameter_mm'] if body_diameter is None else body_diameter
        self.proposal = diagonal_proposal(geometry)
        self.notch = self.proposal['notch_mm']
        self.front = [(f['ref'], f['courtyard_bbox_mm']['F']) for f in geometry['footprints']
                      if f['side'] == 'F' and f['courtyard_bbox_mm'].get('F')]
        self.probes = probes
        self.pin_r = relief.PLUNGER_CANDIDATE['pin_diameter_mm'] / 2
        self.body_r = self.body_diameter / 2
        self.thread_r = self.proposal['finished_thread_cut_envelope_max_mm'] / 2
        self.pos_tol = self.proposal['relative_pin_edge_tolerance_mm']
        self.profile = self.proposal['opposite_edge_board_profile_allowance_mm']
        self.plate = relief.PRESSURE_PLATE

    def row(self, centre):
        x, y = centre
        body_gap, body_ref = min((relief._box_point_dist(b, centre) - self.body_r, ref) for ref, b in self.front)
        edge = min(x, 16.2 - x) - self.pin_r
        edge_worst = edge - self.pos_tol - (self.profile if x < 8.1 else 0.0)
        notch_web = relief._box_point_dist(self.notch, centre) - self.thread_r - self.pos_tol
        plate_web = min(x - self.plate[0], self.plate[2] - x, y - self.plate[1], self.plate[3] - y) - self.thread_r - self.pos_tol
        probe_offset, probe_ref = min((math.dist(centre, p['board_xy_mm']), p['ref']) for p in self.probes)
        return {
            'centre_mm': [r9(x), r9(y)],
            'pin_edge_margin_mm': r9(edge), 'pin_edge_margin_worst_mm': r9(edge_worst),
            'nearest_f_courtyard': body_ref, 'plunger_body_to_courtyard_mm': r9(body_gap),
            'thread_web_to_notch_worst_mm': r9(notch_web), 'plate_edge_thread_web_worst_mm': r9(plate_web),
            'nearest_probe': probe_ref, 'offset_to_nearest_probe_axis_mm': r9(probe_offset),
            'probe_note': 'the probe pads are on the B face and the pin presses the F face: this offset is a load-path '
                          'figure, not a clearance',
            'meets_recorded_site_rules': bool(edge_worst >= self.edge_required - 1e-9
                                              and body_gap >= relief.RULES['contact_f_side_clearance_mm'] - 1e-9
                                              and notch_web >= relief.MIN_WALL - 1e-9 and plate_web >= relief.MIN_WALL - 1e-9),
            'rules': {'pin_edge_margin_worst_required_mm': self.edge_required,
                      'plunger_body_diameter_mm': self.body_diameter,
                      'body_to_courtyard_required_mm': relief.RULES['contact_f_side_clearance_mm'],
                      'thread_web_required_mm': relief.MIN_WALL},
        }


def legal_sites(rules, step=0.05):
    """Clamp sites that satisfy every recorded planar rule, thinned to a 1 mm grid for the pair search."""
    sites = []
    y0, y1 = rules.plate[1] + relief.MIN_WALL, rules.plate[3] - relief.MIN_WALL
    for i in range(int(round(16.2 / step)) + 1):
        for j in range(int(round((y1 - y0) / step)) + 1):
            row = rules.row((round(i * step, 6), round(y0 + j * step, 6)))
            if row['meets_recorded_site_rules']:
                sites.append(row)
    thinned = []
    for row in sorted(sites, key=lambda r: (-r['pin_edge_margin_worst_mm'], r['centre_mm'])):
        if all(math.dist(row['centre_mm'], o['centre_mm']) >= 1.0 for o in thinned):
            thinned.append(row)
    return sites, thinned


def geometric_checks(geometry, probes):
    """Planar requirements of the current candidate clamp pair, recomputed from native geometry."""
    rules = SiteRules(geometry, probes)
    proposal = rules.proposal
    rows = [rules.row(tuple(c['centre_mm'])) for c in proposal['clamps']]
    return {'candidate_geometry': proposal, 'clamp_clearances': rows,
            'pin_edge_margin_required_mm': PIN_EDGE_MARGIN_REQUIRED_MM,
            'minimum_pin_edge_margin_worst_mm': r9(min(r['pin_edge_margin_worst_mm'] for r in rows)),
            'minimum_plunger_body_to_courtyard_mm': r9(min(r['plunger_body_to_courtyard_mm'] for r in rows)),
            'minimum_thread_web_worst_mm': r9(min(min(r['thread_web_to_notch_worst_mm'], r['plate_edge_thread_web_worst_mm']) for r in rows)),
            'every_clamp_meets_recorded_site_rules': all(r['meets_recorded_site_rules'] for r in rows),
            'scope': 'planar requirements from the native pad/courtyard record and the recorded tolerance budget; not a CAD '
                     'interference run, not a measured fit, and not a component height or solder envelope check'}


def net_load_point(clamps, clamp_forces, probes, probe_force):
    """Rigid-body application point of the net downward load (plungers minus probes)."""
    total = sum(clamp_forces) - probe_force * len(probes)
    px = sum(f * q[0] for f, q in zip(clamp_forces, clamps)) - probe_force * sum(p['board_xy_mm'][0] for p in probes)
    py = sum(f * q[1] for f, q in zip(clamp_forces, clamps)) - probe_force * sum(p['board_xy_mm'][1] for p in probes)
    return [px / total, py / total]


def _pair_rows(rules, thinned, probes, hull, band, probe_band):
    rows = []
    for a, b in itertools.combinations(thinned, 2):
        qa, qb = tuple(a['centre_mm']), tuple(b['centre_mm'])
        if math.dist(qa, qb) < 2 * rules.thread_r + relief.MIN_WALL:
            continue
        margins = [relief._hull_margin(hull, net_load_point([qa, qb], list(cf), probes, pf))
                   for cf, pf in corners(band, probe_band, 2)]
        rows.append({'clamps_board_mm': [list(qa), list(qb)],
                     'span_mm': r9(math.dist(qa, qb)), 'y_spread_mm': r9(abs(qa[1] - qb[1])),
                     'minimum_pin_edge_margin_worst_mm': r9(min(a['pin_edge_margin_worst_mm'], b['pin_edge_margin_worst_mm'])),
                     'minimum_body_to_courtyard_mm': r9(min(a['plunger_body_to_courtyard_mm'], b['plunger_body_to_courtyard_mm'])),
                     'minimum_thread_web_worst_mm': r9(min(min(s['thread_web_to_notch_worst_mm'], s['plate_edge_thread_web_worst_mm'])
                                                           for s in (a, b))),
                     'rigid_net_load_point_margin_worst_mm': r9(min(margins)),
                     'rigid_statics_pass': bool(min(margins) >= relief.RULES['resultant_margin_mm'])})
    rows.sort(key=lambda r: (-r['rigid_net_load_point_margin_worst_mm'], -r['minimum_pin_edge_margin_worst_mm']))
    return rows


def search_alternatives(geometry, probes, design, land, levels, modulus, limits, top=5):
    """Can the clamp pair be moved off the 0.025 mm board-edge margin the current candidate keeps?

    The scan is over the pressure plate with the recorded planar rules (pin wholly on the board with the required
    worst-case margin, Ø4 plunger body 0.3 mm off every F courtyard, thread-cut envelope 1.0 mm off the J5 notch and
    the plate edges) and the rigid-body requirement that the net load point stay 0.5 mm inside the carrier land hull.
    Two bounded relaxations are scanned as well, so the shortfall is reported with the input that would close it.
    Nothing here adopts a layout: new clamp sites change the pressure-plate taps and need the fixture CAD, the
    manifest identity locks, a sourced plunger and owner review.
    """
    probe_min = design['holddown']['probe_force_total_N']['minimum_at_acceptance_stroke'] / len(probes)
    probe_max = relief.INGUN['force_graph']['facts']['force_at_maximum_stroke_N']
    probe_band = (r9(probe_min), r9(probe_max))
    plate_deflection = design['holddown']['plunger_compression_mm']['plate_deflection_mm']
    base = Case(*levels[0], THICKNESSES[0], land, probes, [tuple(design['holddown']['contacts_board_mm'][0])], modulus)
    hull = relief._hull([tuple(base.plate.xy[d // 4]) for d in base.land])
    # ranking band: a bounding compression loss of 0.05 mm, well above anything the solves show, so one band can rank
    # every pair. Each shortlisted pair is then re-solved with its own sag-dependent band. The catalogue F1 itself is
    # never used as the lower end: at 4 N the net load would nearly vanish and the load point would run off the board.
    d_min_bound, d_max_bound = compression_band(0.05, plate_deflection)
    band = (r9(plunger_force(d_min_bound) * (1 - limits['plunger_band'])),
            r9(plunger_force(d_max_bound) * (1 + limits['plunger_band'])))

    def solve_pair(clamps):
        trial = Case(*levels[0], THICKNESSES[0], land, probes, [tuple(q) for q in clamps], modulus)
        sag = trial.solve([band[1]] * 2, probe_min)['clamp_sag_max_mm']
        d_min, _ = compression_band(sag, plate_deflection)
        f_min = plunger_force(d_min) * (1 - limits['plunger_band'])
        res = trial.solve([f_min, f_min], probe_max)
        return {'thickness_mm': THICKNESSES[0], 'mesh': list(levels[0]), 'clamp_force_each_minimum_N': r9(f_min),
                'total_minimum_N': r9(2 * f_min), 'force_margin_N': r9(2 * f_min - limits['required_total_clamp_force_N']),
                'probe_displacement_max_abs_mm': res['probe_displacement_max_abs_mm'],
                'land_lift_max_mm': res['land_lift_max_mm'], 'board_max_down_mm': res['board_max_down_mm'],
                'contact_nodes': res['contact_nodes'],
                'meets_recorded_limits_at_this_corner': bool(
                    res['probe_displacement_max_abs_mm'] <= limits['deflection_limit_mm']
                    and res['land_lift_max_mm'] <= limits['land_lift_limit_mm']
                    and 2 * f_min >= limits['required_total_clamp_force_N'])}

    scans = []
    variants = [
        ('recorded_rules', {}, 'pin edge margin >= 0.15 mm worst case, catalogue Ø4 plunger body'),
        ('edge_margin_relaxed_to_0.05mm', {'edge_margin_required': 0.05},
         'what a 0.05 mm worst-case pin-edge margin would open up; an acceptance requirement the owner would have to take on'),
        ('smaller_body_diameter_3.0mm', {'body_diameter': 3.0},
         'what a hypothetical M3-size plunger body would open up; no such part is sourced or selected'),
    ]
    for name, override, note in variants:
        rules = SiteRules(geometry, probes, **override)
        sites, thinned = legal_sites(rules)
        thinned = thinned[:60]
        pairs = _pair_rows(rules, thinned, probes, hull, band, probe_band)
        passing = [p for p in pairs if p['rigid_statics_pass']]
        pool = passing or pairs
        shortlist = pool[:top]
        # a pair only holds the board flat if it straddles the probe field, so the widest y spreads are solved too
        for row in sorted(pool, key=lambda r: -r['y_spread_mm'])[:3]:
            if row not in shortlist:
                shortlist.append(row)
        for row in shortlist:
            row.update(solve_pair(row['clamps_board_mm']))
        probe_y = [p['board_xy_mm'][1] for p in probes]
        centroid_y = sum(probe_y) / len(probe_y)
        scans.append({'variant': name, 'note': note, 'overrides': override,
                      'legal_site_count': len(sites), 'thinned_site_count': len(thinned),
                      'pairs_considered': len(pairs), 'pairs_passing_rigid_statics': len(passing),
                      'probe_field_y_mm': [r9(min(probe_y)), r9(max(probe_y))], 'probe_centroid_y_mm': r9(centroid_y),
                      'legal_sites_beyond_probe_centroid_y': sum(1 for s in sites if s['centre_mm'][1] > centroid_y),
                      'legal_region_board_mm': ([r9(min(s['centre_mm'][0] for s in sites)), r9(min(s['centre_mm'][1] for s in sites)),
                                                 r9(max(s['centre_mm'][0] for s in sites)), r9(max(s['centre_mm'][1] for s in sites))]
                                                if sites else None),
                      'best_pairs': shortlist})
    current = [list(q) for q in design['holddown']['contacts_board_mm']]
    rules = SiteRules(geometry, probes)
    current_rows = [rules.row(tuple(q)) for q in current]
    current_row = {'clamps_board_mm': current, 'span_mm': r9(math.dist(*[tuple(q) for q in current])),
                   'y_spread_mm': r9(abs(current[0][1] - current[1][1])),
                   'minimum_pin_edge_margin_worst_mm': r9(min(r['pin_edge_margin_worst_mm'] for r in current_rows)),
                   'meets_recorded_site_rules': all(r['meets_recorded_site_rules'] for r in current_rows),
                   'rigid_net_load_point_margin_worst_mm': design['holddown']['board_net_load_point_inside_land_hull_mm'],
                   **solve_pair(current)}
    solved = [row for scan in scans for row in scan['best_pairs'] if 'land_lift_max_mm' in row]
    best_alternative = min(solved, key=lambda r: r['land_lift_max_mm']) if solved else None
    shortfall = (
        f"The current candidate pair meets every recorded load limit at this corner but keeps "
        f"{current_row['minimum_pin_edge_margin_worst_mm']} mm worst-case board-edge margin on its second pin, below the "
        f"{PIN_EDGE_MARGIN_REQUIRED_MM} mm recorded requirement. Of the pairs that satisfy every planar rule, "
        f"{sum(s['pairs_passing_rigid_statics'] for s in scans[:1])} pass rigid statics, and none of the solved ones meets "
        f"the contact-model limits: the best solved alternative lifts the board "
        f"{best_alternative['land_lift_max_mm'] if best_alternative else 'n/a'} mm off the land against the "
        f"{limits['land_lift_limit_mm']} mm limit. The reason is geometric: the planar rules confine every rule-satisfying "
        f"site to y <= {scans[0]['legal_region_board_mm'][3]} mm against a probe field at y "
        f"{scans[0]['probe_field_y_mm']}, so no admissible pair straddles it and the board tips. Closing the shortfall "
        f"needs an input this "
        f"calculation cannot supply: a smaller sourced plunger body, a narrower J5 notch, a larger pressure plate, or an "
        f"owner decision to accept a smaller edge margin as a gauged incoming-acceptance requirement.")
    return {'current_candidate': current_row, 'scans': scans,
            'ranking_force_band_N': list(band),
            'ranking': 'planar rules, then the rigid-body net-load-point margin over every force corner of the ranking '
                       'band, plus the widest clamp y spreads; the shortlisted pairs are solved with the contact model at '
                       'the governing corner (thinnest board, both plungers at the minimum of their own band, probes at '
                       'maximum stroke force)',
            'best_solved_alternative': best_alternative,
            'shortfall': shortfall,
            'status': 'CALCULATED ALTERNATIVES, NOT ADOPTED: new clamp sites change the pressure-plate taps and need the '
                      'fixture CAD, manifest identity locks, a sourced plunger and owner review'}


def build(levels, cross_check=True, alternatives=True):
    native, geometry, probes = geometry_and_probes()
    placement = json.loads(PLACEMENT.read_text())
    modulus = relief.RULES['board_flexural_modulus_MPa']
    design = relief.design(geometry, probes, candidate='optical_full_pin')
    limits = {'deflection_limit_mm': relief.RULES['board_deflection_limit_mm'],
              'deflection_limit_basis': 'PROJECT-CHOICE carried from a7_fixture_relief.RULES; small against the 2.05 mm between '
                                        'the 4.3 mm working stroke and the 6.35 mm maximum stroke',
              'deflection_measured_at': 'probe pad centres (the displacement that changes probe compression) and, separately, '
                                        'the conservative whole-board bounds from the Bezier control net',
              'land_lift_limit_mm': relief.RULES['board_deflection_limit_mm'],
              'land_lift_limit_basis': 'PROJECT-CHOICE, same value: how far the board may rise off the carrier land anywhere. '
                                       'The board seats on the land and the datum pins, so a lift is both lost probe '
                                       'compression and lost seating. This quantity exists only in the contact model; the '
                                       'earlier strip model could not express it.',
              'required_total_clamp_force_N': force_inputs(design)['required_total_clamp_force_N'],
              'plunger_band': relief.RULES['plunger_force_acceptance_band'],
              'relative_convergence_limit': RELATIVE_CONVERGENCE_LIMIT}
    layouts = {name: evaluate_layout(name, spec, geometry, probes, levels, modulus, limits, cross_check=cross_check)
               for name, spec in LAYOUTS.items()}
    land, _ = land_predicate(design)
    alternative_sites = (search_alternatives(geometry, probes, design, land, levels, modulus, limits) if alternatives
                         else {'skipped': 'alternative-site scan not re-run; the recorded scan is checked for '
                                          'self-consistency only'})
    record = {
        'schema': 'zudo-led-block/a7-fixture-condition-matrix/1',
        'status': 'EXPERIMENTAL_CALCULATED_NOT_VALIDATED',
        'scope': 'Unilateral-contact plate calculation of every hold-down load corner at 0.7/0.8/0.9 mm finished board '
                 'thickness, on the native outline and pad positions of the bound PCB. Not a fixture acceptance, not a '
                 'measured contact/force/stroke result, not a manufacturing release, and not a transfer of the 1.6 mm PASS.',
        'pcb_identity': {
            'board': str(BOARD.relative_to(ROOT)), 'board_sha256': sha(BOARD),
            'board_thickness_in_pcb_file_mm': placement['thickness_mm'],
            'canonical_placement': str(PLACEMENT.relative_to(ROOT)), 'placement_sha256': sha(PLACEMENT),
            'native_geometry_record': str(NATIVE.relative_to(ROOT)), 'native_geometry_sha256': sha(NATIVE),
            'native_geometry_board_sha256': native['board_sha256'],
            'native_geometry_placement_sha256': native['placement_sha256'],
            'board_identity_bound': native['board_sha256'] == sha(BOARD),
            'geometry_revision_note': 'outline, pads and courtyards come from the native record of this PCB revision. The '
                                      'stackup field of those bytes is still the historical 1.6 mm value; the finished '
                                      'thickness used by the plate model is the ordered 0.8 +/-0.1 mm, which is an order '
                                      'specification, not a measured board. Re-run on the final routed 0.8 mm controller.',
            'rebind_command': 'python3 scripts/a7_fixture_matrix.py --rebind',
            'rebind_prerequisite': 'python3 scripts/a7_fixture_geometry.py --from-zip <native-gate artifact.zip> (fresh native '
                                   'geometry for the new board bytes) then the command above; --check fails until both agree',
        },
        'inputs_sha256': {f: sha(ROOT / f) for f in INPUT_FILES},
        'manifest_sha256': sha(MANIFEST),
        'model': {
            'plate': 'Kirchhoff plate, Bogner-Fox-Schmit rectangular C1 elements (tensor cubic Hermite, 4 DOF per node)',
            'domain': 'board rectangle 16.2 x 62.9 mm; holes, copper, component stiffening and the board bow are not modelled',
            'contact': 'node-wise Signorini conditions against the rigid carrier land (w >= 0, reaction >= 0, w * reaction = 0); '
                       'the land can only push up. No bilateral result is used.',
            'solvers': 'flexibility-form primal active set (scripts/a7_fixture_contact.ContactModel) with an independent '
                       'stiffness-form active set used as a cross-check; both verify the contact conditions and the '
                       'equilibrium residual from K u - f after the solve and raise instead of returning a violated state',
            'loads': 'uniform pressure patches: probe tip 0.5 mm diameter (INGUN tip style), clamp pin 1.5 mm diameter (POM '
                     'thrust pin); total force exact per patch',
            'material': {'flexural_modulus_MPa': modulus, 'modulus_class': 'ASSUMED (laminate not sourced)',
                         'poisson_ratio': POISSON, 'poisson_class': 'ASSUMED',
                         'sourced_comparison': relief.MODULUS_REFERENCES},
            'review': 'method is intended to be re-derived independently: the element matrix, the contact conditions and the '
                      'mesh study are each checked by scripts/tests/test_a7_fixture_contact.py and '
                      'scripts/tests/test_a7_fixture_plate.py against closed-form or analytic results',
        },
        'limits': limits,
        'force_inputs': force_inputs(design),
        'thicknesses_mm': list(THICKNESSES),
        'mesh_levels': [list(m) for m in levels],
        'geometry': geometric_checks(geometry, probes),
        'layouts': layouts,
        'alternative_clamp_sites': alternative_sites,
        'assumptions': [
            'Finished thickness 0.8 +/-0.1 mm is the JLCPCB published tolerance for boards below 1.0 mm '
            '(https://jlcpcb.com/capabilities/Capabilities, read 2026-11-16 UTC); the ordered specification is not yet placed '
            'and no board has been measured.',
            'Flexural modulus 18000 MPa and Poisson ratio 0.3 are ASSUMED; sourced FR-4 class values are recorded for '
            'comparison only and do not bound this laminate.',
            'The carrier land is treated as rigid and flat; land flatness, plate stack flatness and pin tip coplanarity are '
            'acceptance requirements, not measured values.',
            'Board bow and warp are not modelled (zero initial gap). A bowed board changes the contact set.',
            'Plunger forces follow the catalogue line between F1 and F2 with a +/-20 % acceptance band; the catalogue prints '
            'no tolerance, so the band is a PROJECT-CHOICE acceptance requirement.',
            'Probe forces follow the datasheet linear force-stroke line; the value at maximum stroke is read off the graph.',
            'Holes, copper, solder mask and component stiffening are omitted from the plate; omitting copper is not '
            'conservative in every direction and remains an open modelling item.',
            'Component heights, solder envelopes and the pressure-plate CAD interference are outside this record.',
        ],
        'remaining': [
            'Re-run bound to the final routed 0.8 mm controller bytes and a fresh native geometry record (rebind_command).',
            'Physical contact and load validation: measured plunger force at both compression ends, measured probe force, '
            'stroke, seating against the datum pins, positioning, and inspection for board damage, with fixture and board '
            'unit IDs, instruments and raw data (fixture criterion 5).',
            'Measured finished board thickness and laminate flexural properties of the ordered boards.',
            'Board flatness/bow acceptance and its effect on the contact set.',
            'CAD interference of the revised pressure plate, pin sleeves and the J5 notch against the mounted assembly.',
            'Independent mechanical review of this model and its inputs.',
            'Fabricator selection and machining capability for the plates and the tapped pin holes.',
        ],
        'not_evidence_for': ['fixture acceptance or release', 'manufacturing or order approval', 'optical performance',
                             'the A5 fixture or any 1.6 mm result', 'component or solder envelope clearance'],
    }
    return record


def check(record, levels, rerun=True):
    """Re-derive the identity and every recorded margin, and (with rerun) the cheap mesh level; list every mismatch."""
    problems = []
    native, geometry, probes = geometry_and_probes()
    identity = record.get('pcb_identity', {})
    for key, got in (('board_sha256', sha(BOARD)), ('placement_sha256', sha(PLACEMENT)),
                     ('native_geometry_sha256', sha(NATIVE)), ('native_geometry_board_sha256', native['board_sha256']),
                     ('native_geometry_placement_sha256', native['placement_sha256'])):
        if identity.get(key) != got:
            problems.append(f'identity {key}: record {identity.get(key)} != current {got}')
    if record.get('manifest_sha256') != sha(MANIFEST):
        problems.append('probe-pad manifest changed')
    for f, want in record.get('inputs_sha256', {}).items():
        if sha(ROOT / f) != want:
            problems.append(f'{f} changed since the record was written')
    if identity.get('board_identity_bound') is not (native['board_sha256'] == sha(BOARD)):
        problems.append('board_identity_bound does not match the current bytes')
    if record.get('status') != 'EXPERIMENTAL_CALCULATED_NOT_VALIDATED':
        problems.append('status rewritten')
    limit = record['limits']['deflection_limit_mm']
    lift_limit = record['limits']['land_lift_limit_mm']
    required = record['limits']['required_total_clamp_force_N']
    for name, layout in record['layouts'].items():
        for row in layout['cases']:
            if row['probe_displacement_within_limit'] is not (row['probe_displacement_max_abs_mm'] <= limit + 1e-12):
                problems.append(f'{name}: recorded deflection verdict disagrees with the recorded value')
            if abs(row['probe_displacement_margin_mm'] - (limit - row['probe_displacement_max_abs_mm'])) > 1e-9:
                problems.append(f'{name}: recorded deflection margin disagrees with the recorded value')
            if row['land_lift_within_limit'] is not (row['land_lift_max_mm'] <= lift_limit + 1e-12):
                problems.append(f'{name}: recorded land-lift verdict disagrees with the recorded value')
            if row['min_gap_mm'] < -1e-9 or row['min_reaction_N'] < -1e-6:
                problems.append(f'{name}: recorded case violates the contact conditions')
        for t in layout['force_band_per_thickness']:
            if t['force_feasible'] is not (t['total_minimum_N'] >= required):
                problems.append(f"{name}: force verdict at {t['thickness_mm']} mm disagrees with the recorded total")
        verdict = layout['verdict']
        if verdict['all_recorded_limits_met'] is not all(v is True for k, v in verdict.items() if isinstance(v, bool)
                                                         and k != 'all_recorded_limits_met'):
            problems.append(f'{name}: verdict summary disagrees with its own flags')
    if not rerun:
        return problems
    for row in [record['alternative_clamp_sites'].get('current_candidate')] + \
               [r for scan in record['alternative_clamp_sites'].get('scans', []) for r in scan['best_pairs']]:
        if not row or 'land_lift_max_mm' not in row:
            continue
        met = (row['probe_displacement_max_abs_mm'] <= limit and row['land_lift_max_mm'] <= lift_limit
               and row['total_minimum_N'] >= required)
        if row['meets_recorded_limits_at_this_corner'] is not met:
            problems.append(f"alternative {row['clamps_board_mm']}: recorded verdict disagrees with its own values")
    # recompute level 0 and compare: the one part of the matrix cheap enough for CI
    rebuilt = build(levels, cross_check=False, alternatives=False)
    for name, layout in rebuilt['layouts'].items():
        got = {(r['thickness_mm'], tuple(r['clamp_forces_N']), r['probe_force_each_N']): r for r in layout['cases']}
        want = {(r['thickness_mm'], tuple(r['clamp_forces_N']), r['probe_force_each_N']): r for r in record['layouts'][name]['cases']
                if r['level'] == 0}
        if set(got) != set(want):
            problems.append(f'{name}: recorded level-0 corners differ from the regenerated set')
            continue
        for key, row in got.items():
            for field in ('probe_displacement_max_abs_mm', 'clamp_sag_max_mm', 'board_max_up_mm', 'board_max_down_mm'):
                a, b = row[field], want[key][field]
                if abs(a - b) > 1e-6 * max(1.0, abs(b)):
                    problems.append(f'{name} {key} {field}: {b} != {a} (regenerated)')
    return problems


def summary(record):
    lines = [f"status {record['status']}; board_identity_bound {record['pcb_identity']['board_identity_bound']}"]
    for name, layout in record['layouts'].items():
        v = layout['verdict']
        lines.append(f"{name}: limits met {v['all_recorded_limits_met']}; worst probe displacement "
                     f"{v['worst_probe_displacement_mm']} mm (limit {record['limits']['deflection_limit_mm']}); "
                     f"minimum force margin {v['minimum_force_margin_N']} N; "
                     f"mesh converged {v['mesh_converged_within_recorded_limit']}")
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--levels', choices=['coarse', 'all'], default='all',
                    help='coarse: level 0 only (fast, no convergence study). all: the recorded mesh sequence')
    ap.add_argument('--output', type=Path, default=OUTPUT)
    ap.add_argument('--check', action='store_true', help='verify the record: identity, self-consistency and a level-0 re-run')
    ap.add_argument('--rebind', action='store_true', help='regenerate the record from the current PCB bytes (= --levels all --output the record)')
    ap.add_argument('--require-board-sha256', help='fail unless the bound PCB has this SHA-256')
    args = ap.parse_args()
    levels = LEVELS if args.levels == 'all' or args.rebind else LEVELS[:1]
    if args.require_board_sha256 and sha(BOARD) != args.require_board_sha256:
        raise SystemExit(f'board SHA-256 is {sha(BOARD)}, not {args.require_board_sha256}')
    if args.check:
        record = json.loads(args.output.read_text())
        problems = check(record, LEVELS[:1])
        if problems:
            raise SystemExit('STALE or INVALID condition matrix:\n  ' + '\n  '.join(problems))
        print('PASS: condition matrix is current, identity-bound and self-consistent (level 0 re-run)')
        print(summary(record))
        return
    record = build(levels)
    native = json.loads(NATIVE.read_text())
    if not record['pcb_identity']['board_identity_bound']:
        print('WARNING: the native geometry record and the controller bytes disagree; the matrix is not bound to the current PCB',
              file=sys.stderr)
    args.output.write_text(json.dumps(record, indent=2) + '\n')
    print(f"written {args.output.relative_to(ROOT) if args.output.is_relative_to(ROOT) else args.output}")
    print(summary(record))
    assert native['board_sha256'] == record['pcb_identity']['native_geometry_board_sha256']


if __name__ == '__main__':
    main()
