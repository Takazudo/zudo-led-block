#!/usr/bin/env python3
"""Revision-bound A7 SWD fixture design; never a fit, selection or fabrication approval.

Normal generation emits JSON/SVG only and checks them against the producer. --cad builds every part with CadQuery
2.7.0, writes the assembly STEP and the interference record (pairwise common volumes, critical clearances, designed
contacts) that criterion 4 binds by hash; --cad-check rebuilds the model and compares it with the STEP.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from a7_mechanical_layout import bound_r4_placement
import a7_fixture_geometry as native_geom
import a7_fixture_relief as relief_design
import a7_fixture_assembly as relief_assembly
OUT = ROOT / 'engineering/a7/fixture'
BOARD = ROOT / 'engineering/a7/electronics/controller/controller.kicad_pcb'
CANONICAL = BOARD.with_name('board_placement.json')
BOARD_SHA = 'd83691d6590e013b2a66957b61d76ba2f68bedaaec04789326e1215b2d1bdb2b'
PLACEMENT_SHA = '2d32b2ab76735dbf4ff7f2c959de4398b8215983be9a4fd33fde50c7015212f5'
ROLES = {'TP1': '+3V3', 'TP2': 'GND', 'TP3': 'SWDIO', 'TP4': 'SWCLK', 'TP5': 'NRST'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe_map(placement, board_text):
    result = []
    for ref, net in ROLES.items():
        matches = [c for c in placement['components'] if c['ref'] == ref]
        if len(matches) != 1:
            raise ValueError(f'{ref}: missing or duplicate pad')
        c = matches[0]
        if c['side'] != 'B' or set(c['pads']) != {'1'} or c['pads']['1']['net'] != '/' + net:
            raise ValueError(f'{ref}: side/net/pad identity mismatch')
        blocks = [b for b in board_text.split('\n\t(footprint ')[1:] if f'(property "Reference" "{ref}"' in b]
        if len(blocks) != 1 or not re.search(r'\(pad "1" smd circle\s+\(at 0 0\)\s+\(size 1 1\)\s+\(layers "B.Cu" "B.Mask"\)', blocks[0]):
            raise ValueError(f'{ref}: expected actual PCB 1mm round exposed B pad')
        x, y = c['pads']['1']['at_mm']
        result.append(dict(ref=ref, net=net, board_xy_mm=[x, y], carrier_xy_mm=[round(16.2-x, 6), y], pad_diameter_mm=1.0))
    return result


def native_probe_pads(pads):
    """Cross-check the probe pads against the validated native geometry record (CI-exported KiCad facts)."""
    path = native_geom.RECORD
    if not path.is_file():
        raise ValueError('native fixture geometry record missing; write it with a7_fixture_geometry.py --from-zip')
    rec = json.loads(path.read_text())
    errs = native_geom.check_record(rec)
    if errs:
        raise ValueError('native fixture geometry record invalid: ' + '; '.join(errs[:5]))
    by_ref = {f['ref']: f for f in rec['geometry']['footprints']}
    for pad in pads:
        f = by_ref.get(pad['ref'])
        npads = [q for q in (f or {}).get('pads', []) if q['number'] == '1']
        if f is None or f['side'] != 'B' or len(f['pads']) != 1 or len(npads) != 1:
            raise ValueError(f"{pad['ref']}: native footprint/pad identity mismatch")
        q = npads[0]
        d = pad['pad_diameter_mm']
        if (q['shape'] != 'CIRCLE' or q['attribute'] != 'SMD' or q['net'] != '/' + pad['net'] or sorted(q['layers']) != ['B.Cu', 'B.Mask']
                or any(abs(a - d) > native_geom.TOL_MM for a in q['size_mm'])
                or any(abs(a - b) > native_geom.TOL_MM for a, b in zip(q['at_mm'], pad['board_xy_mm']))):
            raise ValueError(f"{pad['ref']}: native pad differs from the fixture probe map")
    prov = rec['provenance']
    return {'record': str(path.relative_to(ROOT)), 'record_sha256': digest(path), 'status': rec['status'],
            'github_run_id': prov['identity']['github_run_id'], 'tested_revision': prov['identity'].get('pr_head_sha') or prov['identity'].get('checkout_head'),
            'provenance_class': prov['provenance_class'], 'ci_retained_artifact': prov['ci_retained_artifact'],
            'artifact_zip_sha256': prov.get('artifact_zip_sha256'), 'probe_pads_match': True,
            'scope': 'Native KiCad pad facts confirm the five probe pads (B side, round 1 mm, B.Cu/B.Mask, position, net). Native pad copper boxes set the carrier cuts and native F courtyards bound the clamp points (b_side_relief); body heights and solder envelopes are not native facts.'}


ASSEMBLY_STEP = OUT / 'fixture-assembly.step'
INTERFERENCE = OUT / 'assembly-interference.json'


def assembly_status(relief):
    """Criterion 4 from the interference record written by --cad: bound to this design and to the STEP bytes."""
    if not INTERFERENCE.is_file() or not ASSEMBLY_STEP.is_file():
        return False, 'no assembly STEP or interference record; run with --cad', None
    rec = json.loads(INTERFERENCE.read_text())
    problems = []
    if rec.get('model_inputs_sha256') != relief_assembly.design_digest(relief, digest(native_geom.RECORD)):
        problems.append('interference record is for a different design, assembly code or native record')
    if rec.get('step_sha256') != digest(ASSEMBLY_STEP):
        problems.append('assembly STEP bytes differ from the checked model')
    if rec.get('interferences'):
        problems.append(f"{len(rec['interferences'])} interferences")
    if any(c['minimum_mm'] is None or c['minimum_mm'] <= 0 for c in rec.get('clearances', [])):
        problems.append('a critical clearance is not positive')
    if any(not c['touching'] for c in rec.get('designed_contacts', [])):
        problems.append('a designed contact does not touch')
    summary = {'record': str(INTERFERENCE.relative_to(ROOT)), 'record_sha256': digest(INTERFERENCE),
               'step': str(ASSEMBLY_STEP.relative_to(ROOT)), 'step_sha256': rec.get('step_sha256'),
               'solids': len(rec.get('solids', [])), 'interferences': len(rec.get('interferences', [])),
               'clearances': rec.get('clearances'), 'designed_contacts': rec.get('designed_contacts')}
    return not problems, '; '.join(problems) or 'assembly STEP of every part, hardware envelope, probe and the board; no interference', summary


# Proposed replacement candidate: the condition matrix's adopted layout built beside, never in place of, the retained geometry.
CANDIDATE_LAYOUT = 'optical_stepped_tip'
CANDIDATE_RELIEF = 'optical_full_pin'  # a7_fixture_relief.design candidate: the diagonal pin sites and the revised J5 notch
CANDIDATE_STEP = OUT / 'candidate-assembly.step'
CANDIDATE_RECORD = OUT / 'candidate-assembly-interference.json'
CANDIDATE_DRAWING = OUT / 'candidate-drawing.svg'
CONDITION_MATRIX = OUT / 'condition-matrix.json'
CANDIDATE_THICKNESSES = (0.7, 0.8, 0.9)  # finished 0.8 +/-0.1 mm, as the condition matrix
CANDIDATE_STATUS = 'PROPOSED_REPLACEMENT_CANDIDATE: calculated and digitally modelled, not selected, not approved, not physically validated'
CANDIDATE_HOLDS = [
    'Owner approval of the candidate and of the modified (turned-tip) K0318.04 thrust pin: not given; the candidate is not selected.',
    'Machining availability of the 1.2 mm x 0.5 mm turned tip on the POM thrust pin, and fabricator/process for it and for the revised '
    'pressure plate: not established (no supplier asked).',
    'Material selection and approval: the POM grade of the KIPP pin is not printed; the 20 MPa contact allowable and the 2800 MPa '
    'modulus are ASSUMED class values; the plate laminate and the board laminate (18000 MPa) are ASSUMED.',
    'Fabrication suitability of the 1.0 mm worst-case thread webs to the J5 notch and the plate edge, and of the gauge requirements, '
    'is not confirmed by a fabricator.',
    'Pressure-plate location: the plate is located only by M3 screws in 3.4 mm clearance holes on stop standoffs that are themselves '
    'fixed through 3.4 mm clearance holes, so it can sit up to 0.4 mm off nominal; the recorded 0.10 mm pin-to-edge tolerance has no '
    'term for this (see registration). A locating feature or an owner-accepted gauge procedure is required before the edge margins hold.',
    'Wear, creep, abrasion of the turned tip and damage to the solder mask or board edge: not modelled; physical checks.',
    'Physical criterion 5 (contact, load, stroke, registration, damage with unit IDs, instruments and raw data): NOT_MEASURED.',
]


def candidate_design(geometry, pads):
    """The candidate's relief design (pin sites, notch, pressure plate) and one pin-tip entry per hold-down contact."""
    import a7_fixture_support as support
    rel = relief_design.design(geometry, pads, candidate=CANDIDATE_RELIEF)
    pin = rel['holddown']['plunger_candidate']['pin_diameter_mm']
    tips = [None if d >= pin else {'contact_diameter_max_mm': d, 'tip_length_mm': support.STEPPED_TIP['tip_length_mm']}
            for d in support.stepped_tip_contacts(pin)]
    return rel, tips


def candidate_inputs(rel, tips, geometry_sha256):
    import a7_fixture_support as support
    return dict(relief_assembly.model_inputs(rel, geometry_sha256), pin_tips=tips, thicknesses_mm=list(CANDIDATE_THICKNESSES),
                support_code_sha256=digest(Path(support.__file__).resolve()),
                relief_code_sha256=digest(Path(relief_design.__file__).resolve()))


def candidate_digest(rel, tips, geometry_sha256):
    return hashlib.sha256(json.dumps(candidate_inputs(rel, tips, geometry_sha256), sort_keys=True).encode()).hexdigest()


def candidate_matrix_correspondence(rec, matrix=None):
    """Problems where the candidate CAD record disagrees with the condition matrix's adopted candidate; [] when they agree."""
    m = json.loads(CONDITION_MATRIX.read_text()) if matrix is None else matrix
    a, g = m['adopted_candidate'], m['geometry']['candidate_geometry']
    c = rec['candidate']
    out = []
    if a['layout'] != CANDIDATE_LAYOUT or c['layout'] != CANDIDATE_LAYOUT:
        out.append('layout differs from the condition matrix adopted candidate')
    if [cl['centre_mm'] for cl in a['clamps']] != c['contacts_board_mm']:
        out.append('pin sites differ from the condition matrix')
    if [cl['contact_diameter_mm'] for cl in a['clamps']] != c['contact_diameters_mm']:
        out.append('contact diameters differ from the condition matrix')
    if a['stepped_tip']['tip_length_mm'] != c['stepped_tip_length_mm']:
        out.append('stepped-tip length differs from the condition matrix')
    if list(g['notch_mm']) != c['j5_notch_board_mm'] or g['notch_radius_mm'] != c['notch_corner_radius_mm']:
        out.append('J5 notch differs from the condition matrix')
    if list(g['pressure_plate_z_mm']) != c['pressure_plate_z_mm']:
        out.append('pressure-plate z differs from the condition matrix')
    if m['thicknesses_mm'] != [t['thickness_mm'] for t in rec['thickness_cases']]:
        out.append('board thicknesses differ from the condition matrix')
    bands = {b['thickness_mm']: b['compression_range_mm'] for b in m['layouts'][CANDIDATE_LAYOUT]['force_band_per_thickness']}
    for t in rec['thickness_cases']:
        lo, hi = t['compression_mm']['range']
        band = bands.get(t['thickness_mm'])
        if band is None or lo < band[0] - 1e-6 or hi > band[1] + 1e-6:
            out.append(f"{t['thickness_mm']} mm: CAD compression {t['compression_mm']['range']} outside the matrix band {band}")
    for row in rec['clamps']:
        mrow = next((cl for cl in a['clamps'] if cl['centre_mm'] == row['centre_mm']), None)
        if mrow is None or abs(mrow['contact_edge_margin_worst_mm'] - row['contact_edge_margin_recorded_budget_mm']) > 1e-6:
            out.append(f"{row['clamp']}: recorded-budget edge margin differs from the condition matrix")
    return out


def candidate_registration(rel, clamps, required):
    """Pin-to-board-edge margins: the recorded tolerance budget, and the same with the pressure-plate location the CAD carries."""
    import a7_fixture_support as support
    prop = support.diagonal_proposal(json.loads(native_geom.RECORD.read_text())['geometry'])
    R = rel['rules']
    float_joint = round((R['m3_clearance_hole_mm'] - 3.0) / 2, 6)  # M3 modelled at its 3.0 mm major diameter
    plate_float = round(2 * float_joint, 6)
    rel_tol, profile = prop['relative_pin_edge_tolerance_mm'], prop['opposite_edge_board_profile_allowance_mm']
    budget = prop['tolerance_budget_mm']
    rows = []
    for c in clamps:
        far = c['centre_mm'][0] < 8.1  # the x = 0 edge is not on the datum pins: board width tolerance applies
        extra = profile if far else 0.0
        row = {'clamp': c['clamp'], 'centre_mm': c['centre_mm'],
               'contact_edge_margin_nominal_mm': c['contact_edge_margin_nominal_mm'],
               'contact_edge_margin_recorded_budget_mm': round(c['contact_edge_margin_nominal_mm'] - rel_tol - extra, 6),
               'contact_edge_margin_with_plate_float_mm': round(c['contact_edge_margin_nominal_mm'] - plate_float
                                                                - budget['assembled_pin_axis_including_play_runout_tilt']
                                                                - budget['board_registration'] - extra, 6),
               'shank_edge_margin_with_plate_float_mm': round(c['shank_edge_margin_nominal_mm'] - plate_float
                                                              - budget['assembled_pin_axis_including_play_runout_tilt']
                                                              - budget['board_registration'] - extra, 6)}
        row['plate_location_error_allowed_mm'] = round(row['contact_edge_margin_recorded_budget_mm'] - required, 6)
        rows.append(row)
    return {'required_contact_edge_margin_worst_mm': required,
            'required_basis': 'condition-matrix.json adopted_candidate.pin_edge_margin_required_mm (unchanged)',
            'recorded_relative_pin_edge_tolerance_mm': rel_tol, 'recorded_tolerance_budget_mm': budget,
            'opposite_edge_board_profile_allowance_mm': profile,
            'pressure_plate_location': {
                'as_modelled': 'two M3 socket head screws through 3.4 mm clearance holes into the stop standoffs; each standoff is fixed '
                               'to the carrier by an M3 screw through a 3.4 mm clearance hole; no dowel, shoulder or fitted feature '
                               'locates the plate to the carrier or to the datum pins',
                'radial_float_per_joint_mm': float_joint, 'joints_in_series': 2, 'worst_plate_offset_mm': plate_float},
            'clamps': rows,
            'recorded_budget_closes': all(r['contact_edge_margin_recorded_budget_mm'] >= required - 1e-9 for r in rows),
            'closes_with_plate_float': all(r['contact_edge_margin_with_plate_float_mm'] >= required - 1e-9 for r in rows),
            'finding': 'The recorded 0.10 mm relative pin-to-edge tolerance (tap position, pin axis, board registration) has no term '
                       'for locating the pressure plate on the carrier, and the modelled plate is located only by clearance holes. '
                       'With that float the stepped-tip contact can reach past the board edge. Registration of the candidate is '
                       'therefore not closed until the plate is located to within plate_location_error_allowed_mm (or the owner '
                       'accepts a gauge-and-shim procedure that achieves it).'}


def candidate_status():
    """Binding of the candidate record, STEP and drawing; never feeds the retained completion criteria."""
    geometry = json.loads(native_geom.RECORD.read_text())['geometry']
    pads = probe_map(bound_r4_placement(), BOARD.read_text())
    rel, tips = candidate_design(geometry, pads)
    base = {'layout': CANDIDATE_LAYOUT, 'status': CANDIDATE_STATUS, 'replaces_retained_geometry': False,
            'record': str(CANDIDATE_RECORD.relative_to(ROOT)), 'step': str(CANDIDATE_STEP.relative_to(ROOT)),
            'drawing': str(CANDIDATE_DRAWING.relative_to(ROOT)), 'holds': CANDIDATE_HOLDS}
    if not CANDIDATE_RECORD.is_file() or not CANDIDATE_STEP.is_file():
        return dict(base, bound=False, problems=['no candidate record or STEP; run a7_fixture.py --cad'])
    rec = json.loads(CANDIDATE_RECORD.read_text())
    problems = []
    if rec.get('model_inputs_sha256') != candidate_digest(rel, tips, digest(native_geom.RECORD)):
        problems.append('candidate record is for a different design, pin tip, assembly code or native record')
    if rec.get('step_sha256') != digest(CANDIDATE_STEP):
        problems.append('candidate STEP bytes differ from the checked model')
    return dict(base, bound=not problems, problems=problems, record_sha256=digest(CANDIDATE_RECORD), step_sha256=rec.get('step_sha256'),
                candidate=rec.get('candidate'), checks=rec.get('checks'), all_digital_checks_met=rec.get('all_digital_checks_met'),
                interferences_per_thickness={str(t['thickness_mm']): len(t['interferences']) for t in rec.get('thickness_cases', [])},
                registration_finding=(rec.get('registration') or {}).get('finding'))


# One sourced candidate for every materials.json line: proposals awaiting owner approval, never selections.
HARDWARE_PROPOSAL = [
    ('probe', 'INGUN', 'GKS-050 214 050 A 1000', 'sources.json#probe'),
    ('receptacle', 'INGUN', 'KS-050 E08 V-30', 'sources.json#receptacle'),
    ('support-carrier', 'Von Roll', 'Vetronite EGS 619 sheet (EP GC 202 / FR-4), 5.0 mm, machined to fixture-assembly.step', 'sources.json#vetronite-egs-619'),
    ('probe-plate', 'Von Roll', 'Vetronite EGS 619 sheet (EP GC 202 / FR-4), 6.0 mm, machined to fixture-assembly.step', 'sources.json#vetronite-egs-619'),
    ('pressure-plate', 'Von Roll', 'Vetronite EGS 619 sheet (EP GC 202 / FR-4), 6.0 mm, machined to fixture-assembly.step', 'sources.json#vetronite-egs-619'),
    ('base-plate', 'Von Roll', 'Vetronite EGS 619 sheet (EP GC 202 / FR-4), 3.0 mm, machined to fixture-assembly.step', 'sources.json#vetronite-egs-619'),
    ('datum-pins', 'GANTER', 'DIN 6325-2M6-6-ST', 'sources.json#ganter-din-6325'),
    ('alignment-dowels', 'GANTER', 'DIN 6325-2M6-16-ST', 'sources.json#ganter-din-6325'),
    ('plate-stack-screws', 'TR Fastenings', 'M3 8 KH10MC Z100', 'sources.json#tr-kh10mc'),
    ('plate-stack-spacers', 'ETTINGER', '05.03.061', 'sources.json#ettinger-05-03-061'),
    ('plate-stack-studs', 'TR Fastenings', 'M3 12 HS45PC S100', 'sources.json#tr-hs45pc'),
    ('base-standoffs', 'ETTINGER', '05.03.351', 'sources.json#ettinger-05-03-351'),
    ('base-screws', 'TR Fastenings', 'M3 8 KH10MC Z100', 'sources.json#tr-kh10mc'),
    ('stop-standoffs', 'ETTINGER', '05.03.061', 'sources.json#ettinger-05-03-061'),
    ('stop-screws', 'TR Fastenings', 'M3 8 SO12CS Z100 (4: 2 under the carrier, 2 on the plate)', 'sources.json#tr-so12cs'),
    ('hold-down-plungers', 'KIPP', 'K0318.04', 'sources.json#kipp-k0318'),
    ('wire-retention', 'HellermannTyton', 'T18R-PA66-NA (111-00643)', 'sources.json#hellermanntyton-111-00643'),
    ('wire-retention', 'HellermannTyton', 'FTLS-PET-WH FlagTag (596-97004)', 'sources.json#hellermanntyton-596-97004'),
]
HARDWARE_PROPOSAL_STATUS = 'PROPOSED_AWAITING_OWNER_APPROVAL'


def hardware_proposal(relief):
    """The proposal list and whether it covers every materials.json line with an available source; never a selection."""
    items = json.loads((OUT/'materials.json').read_text())['items']
    sources = {x['id']: x for x in json.loads((OUT/'sources.json').read_text())['sources']}
    entries, problems = [], []
    for req, maker, mpn, src in HARDWARE_PROPOSAL:
        doc = sources.get(src.split('#', 1)[1])
        if doc is None or doc.get('availability') != 'AVAILABLE':
            problems.append(f'{req}: source {src} missing or unavailable')
        entries.append({'requirement_id': req, 'manufacturer': maker, 'mpn': mpn, 'source': src, 'status': HARDWARE_PROPOSAL_STATUS,
                        'source_authority': doc and doc['authority'], 'source_sha256': doc and doc.get('sha256')})
    wanted = {x['id'] for x in items}
    covered = {e['requirement_id'] for e in entries}
    problems += [f'{r}: no proposed candidate' for r in sorted(wanted - covered)]
    problems += [f'{r}: not a materials.json line' for r in sorted(covered - wanted)]
    if not relief['holddown']['plunger_candidate']['meets_requirement']:
        problems.append('hold-down-plungers: candidate does not meet the plunger requirement')
    return entries, not problems, problems


def report():
    p = bound_r4_placement()
    if digest(BOARD) != BOARD_SHA or digest(CANONICAL) != PLACEMENT_SHA:
        raise ValueError('Fixture revision invalidated; re-review geometry and update explicit identity locks')
    pads = probe_map(p, BOARD.read_text())
    native = native_probe_pads(pads)
    relief = relief_design.design(json.loads(native_geom.RECORD.read_text())['geometry'], pads)
    spacing = min(math.dist(a['carrier_xy_mm'], b['carrier_xy_mm']) for i,a in enumerate(pads) for b in pads[i+1:])
    criteria = dict(relief['fresh_native_criteria'], native_record_valid_and_probe_pads_confirmed=native['probe_pads_match'])
    fresh = all(criteria.values())
    hd = relief['holddown']
    c3 = relief['criterion_3_checks']
    asm_ok, asm_basis, asm = assembly_status(relief)
    proposal, proposal_complete, proposal_problems = hardware_proposal(relief)
    completion = {
        '1_native_support_and_relief': {'met': fresh, 'basis': 'fresh_native_criteria' + ('' if fresh else ' not all met: ' + ', '.join(k for k, v in criteria.items() if not v))},
        '2_keying_and_registration': {'met': relief['keying']['keyed'] and relief['registration']['worst_case_margin_mm'] >= 0,
                                      'basis': 'turned-pose blocking features and radial allocation closed by acceptance-measurement requirements'},
        '3_stroke_stop_guide_fixing_insulation_wiring': {'met': all(c3.values()), 'checks': c3,
                                                         'basis': 'stroke and installation height, carrier-land travel stop, rigid pressure plate on hard stops with spring plungers, '
                                                                  'plate stack on spacers/standoffs/base with dowel alignment, FR-4 plates with POM board contacts, wire bend space and tie slot'},
        '4_assembly_step_interference_check': {'met': asm_ok, 'basis': asm_basis},
        '5_physical_tests': {'met': False, 'basis': 'physical; tracked by the fixture-contact procedure, all observations NOT_MEASURED'},
    }
    digital = [k for k in completion if not k.startswith('5_')]
    blockers = [
        *([] if fresh else ['fresh_native_verified false: ' + '; '.join(
            [f'{u} is unsourced (the carrier and probe-plate windows and the base clearance do not depend on it up to the stated bound)' for u in relief['unknown_heights']]
            + [f'{k} not met' for k, v in criteria.items() if not v and k != 'every_b_face_protrusion_sourced'])]),
        *[f'criterion {k} not met: ' + (', '.join(c for c, ok in v['checks'].items() if not ok) + ' not met' if 'checks' in v else v['basis'])
          for k, v in completion.items() if k in digital[1:] and not v['met']],
    ]
    candidate_checks = candidate_reference_checks(relief)
    candidate = candidate_status()
    owner_items = [
        'Fabricator for the four FR-4 plates is an owner choice and not selected; JLCCNC guidance is a candidate reference only. '
        f"The probe-plate bores are drilled at the board test-point pitch, leaving {relief['probe_plate']['bore_webs_mm'][0]} mm between bores: "
        f"this meets the INGUN receptacle grid ({relief['rules']['probe_bore_web_minimum_mm']} mm) but not the 1.0 mm milled-wall guidance, "
        'so the chosen fabricator must confirm drilling it; the board pitch is fixed.',
        'Registration needs the bore positions within 0.05 mm of the datum pins, tighter than the +/-0.1 mm standard tolerance: an annotated 2D drawing is needed.',
        'Plate stock and every hardware line have one sourced candidate in hardware_proposal, awaiting owner approval; none is selected, '
        'and no price, stock or lead time was retrieved.',
        'Receptacle drawing diameter 0.96 mm versus PDF table 0.95 mm; the bore follows the 0.98-1.00 mm FR-4 mounting-hole data, resolve before selection.',
    ]
    physical_items = ['No physical fit, contact, insertion-force or measured stroke evidence; no prototype exists; every acceptance measurement in b_side_relief is a requirement, not a result.',
                      'The hold-down plunger forces are catalogue approximations without a tolerance: the design takes them +/-'
                      f"{round(relief['rules']['plunger_force_acceptance_band'] * 100)} % and each plunger must be measured against that band at both compression ends before use; "
                      'the plunger has no thread lock, so its pin-tip setting is gauged before each session.']
    digital_met = fresh and all(completion[k]['met'] for k in digital) and not blockers
    # the documented flag keeps every criterion, including the physical criterion 5
    complete = digital_met and all(c['met'] for c in completion.values())
    files = (BOARD, CANONICAL, Path(__file__).resolve(), Path(relief_design.__file__).resolve(), Path(relief_assembly.__file__).resolve(),
             relief_design.POPULATION, OUT/'sources.json', OUT/'materials.json', OUT/'candidate-references.json')
    return dict(
        schema=2, status='DIGITAL_DESIGN_VERIFIED' if complete else 'BLOCKED', digital_fixture_complete=complete,
        digital_fixture_complete_scope='README completion criteria 1-5, including the physical criterion 5',
        digital_criteria_1_to_4_met=digital_met,
        digital_criteria_1_to_4_met_scope='progress indicator only: README criteria 1-4 met digitally with no digital blocker; it is not '
                                          'digital_fixture_complete, not a fit result and not order eligibility',
        hardware_proposal_complete=proposal_complete,
        hardware_proposal_scope=f'one sourced candidate for every materials.json line, each {HARDWARE_PROPOSAL_STATUS}: a proposal, not a '
                                'selection, not an approval and not an order',
        hardware_proposal=proposal, hardware_proposal_problems=proposal_problems,
        scope='Digital fixture design: support carrier, probe plate, pressure plate, base plate and hardware envelopes with the assembly STEP and '
              'interference check; not a fit result, not a selection and not a fabrication approval',
        board_sha256=digest(BOARD), placement_sha256=digest(CANONICAL), geometry_sha256=p['geometry_sha256'],
        inputs_sha256={str(path.relative_to(ROOT)): digest(path) for path in files},
        geometry_roles={
            'retained': 'the fixture geometry this manifest judges: support carrier, probe plate, base plate and the pressure plate with the '
                        'plunger pair at b_side_relief.holddown.contacts_board_mm, bound by assembly / fixture-assembly.step. On the 0.7-0.9 mm '
                        'board its criterion 3 is NOT met (completion_criteria.3): clamp force margin, seating and bending fail; that '
                        'result stands and is not relaxed by the candidate',
            'proposed_replacement_candidate': 'the condition matrix adopted candidate (optical_stepped_tip): the same plates with a '
                                              'revised J5 notch and pin sites and a turned 1.2 mm tip on the second POM pin, modelled '
                                              'beside the retained geometry in candidate-assembly.step. It is not selected, not approved, '
                                              'not physically validated and does not change any completion criterion or flag'},
        assembly=asm,
        proposed_replacement_candidate=candidate,
        fresh_native_verified=fresh, fresh_native_criteria=criteria, completion_criteria=completion,
        native_geometry=native, b_side_relief=relief,
        native_ci_evidence={'observed_date_utc':'2026-11-11','run_url':'https://github.com/Takazudo/zudo-led-block/actions/runs/42596523199','head_sha':'f0b1d8aa37f3967ccc8c9a6bd6ca0e7b7fc7b3a0','base_sha':'af523f9abb74e206c27aaaa076b3b68a5c474940','result':'PASS','board_sha256':'89310d539b3c28096775cee821e46c14fdba42a87809c82f1fd7f0751704e727','applies_to_current_board':False,'scope':'HISTORICAL: pinned native CI of the PR #44 preparation head on the 1.6 mm board it names (CI log result); not verification of fixture geometry and NOT a result for the current 0.8 mm board. The current board\'s native result is native_geometry (provenance_class '+native['provenance_class']+(', GitHub run '+str(native['github_run_id'])+', retained artifact SHA-256 '+str(native['artifact_zip_sha256']) if native['ci_retained_artifact'] else ', no CI run id')+')','raw_facts_consumed':False,'artifact_access':'2026-11-09: download Forbidden (historical). 2026-11-11: native-infrastructure-evidence artifact 13663737750 downloaded (ZIP SHA-256 33f3d9121164f364b0325540b161e9546ddf73c8b723c9166fdcd8a19867cf0e), but it retains only a7-gate/summary.json; candidate board_facts/board_geometry were not uploaded, so raw candidate facts remain unavailable (historical, for that 1.6 mm board)'},
        transform={'description':'Board coordinates for every part: x, y as on the PCB, z up from the board B face (carrier top). The B-view carrier coordinates in b_side_relief are x_c = 16.2 - x_board.','matrix_xy_b_view':[[-1,0,16.2],[0,1,0],[0,0,1]]},
        pads=pads,
        calculations={'nominal_radial_budget_mm':(1.0-0.5)/2,'worst_case_registration_margin_mm':relief['registration']['worst_case_margin_mm'],'registration_equation':'0.25 - (board edge-to-pad + datum registration + bore position + probe lateral play/concentricity); all terms radial worst-case mm, each allocation closed by an acceptance measurement (b_side_relief.registration)','minimum_probe_pitch_mm':round(spacing,6),'manufacturer_nominal_grid_mm':1.27,'nominal_collar_edge_gap_mm':round(spacing-1.04,6),'recommended_working_stroke_mm':4.3,'maximum_stroke_mm':6.35,'nominal_total_force_at_working_stroke_N':5*1.0,'nominal_total_preload_N':5*0.44,'total_force_at_maximum_stroke_N':hd['probe_force_total_N']['maximum_stroke'],'required_total_hold_down_force_N':hd['required_total_force_N'],'hold_down_force_range_N':hd['total_force_N'],'clamp_force_margin_factor':hd['clamp_force_margin_factor'],'force_tolerance_N':None},
        candidate_reference_checks=candidate_checks,
        blockers=blockers, owner_and_supplier_items=owner_items, physical_items=physical_items)


def _min_window_wall(windows, bounds):
    gaps = []
    for i, a in enumerate(windows):
        for b in windows[i + 1:]:
            gaps.append(min(relief_design._box_gap(p['box_board_mm'], q['box_board_mm']) for p in a['members'] for q in b['members']))
        for m in a['members']:
            bx = m['box_board_mm']
            gaps += [g for g in (bx[0] - bounds[0], bx[1] - bounds[1], bounds[2] - bx[2], bounds[3] - bx[3]) if g > 0]
    return round(min(gaps), 6) if gaps else None


def candidate_reference_checks(relief):
    """Compare each plate with captured, NOT selected fabricator guidance; informational, never a gate or a selection."""
    out = []
    sc, pp, pr, bp = relief['support_carrier'], relief['probe_plate'], relief['pressure_plate'], relief['base_plate']
    slot = {'members': [{'box_board_mm': bp['tie_slot_board_mm']}]}
    notch = {'members': [{'box_board_mm': pr['j5_notch_board_mm']}]}
    plates = {
        'support_carrier': (sc['thickness_mm'], sc['corner_radius_mm'], sc['windows'], sc['smallest_webs'], sc['bounds_board_mm']),
        'probe_plate': (pp['thickness_mm'], pp['corner_radius_mm'], pp['windows'], pp['smallest_webs'], sc['bounds_board_mm']),
        'pressure_plate': (round(pr['z_mm'][1] - pr['z_mm'][0], 6), pr['corner_radius_mm'], [notch], pr['smallest_webs'], pr['outline_board_mm']),
        'base_plate': (round(bp['z_mm'][1] - bp['z_mm'][0], 6), bp['corner_radius_mm'], [slot], bp['smallest_webs'], sc['bounds_board_mm']),
    }
    for ref in json.loads((OUT/'candidate-references.json').read_text())['references']:
        rules = ref['rules_used']
        per_plate = {}
        for name, (t, r, windows, webs, bounds) in plates.items():
            need_r, tool = round(t / 10 + 0.5, 6), round(t / 5, 6)
            members = [m['box_board_mm'] for w in windows for m in w['members']]
            narrow = round(min(min(b[2] - b[0], b[3] - b[1]) for b in members), 6) if members else None
            wall = _min_window_wall(windows, bounds)
            web = min((w['web_mm'] for w in webs), default=None)
            checks = {'internal_corner_radius_mm': {'design': r, 'guidance': need_r, 'met': r >= need_r - 1e-9},
                      'narrowest_opening_mm': {'design': narrow, 'guidance_tool_diameter_mm': tool, 'met': None if narrow is None else narrow >= tool},
                      'minimum_milled_wall_mm': {'design': None if wall is None and web is None else min(v for v in (wall, web) if v is not None),
                                                 'guidance_absolute_minimum': rules['wall_absolute_minimum_mm'],
                                                 'met': None if wall is None and web is None else min(v for v in (wall, web) if v is not None) >= rules['wall_absolute_minimum_mm']}}
            if name == 'probe_plate':
                checks['drilled_bore_web_mm'] = {'design': pp['bore_webs_mm'][0], 'guidance_absolute_minimum': rules['wall_absolute_minimum_mm'],
                                                 'manufacturer_grid_minimum': relief['rules']['probe_bore_web_minimum_mm'],
                                                 'met': pp['bore_webs_mm'][0] >= rules['wall_absolute_minimum_mm'],
                                                 'note': 'drilled at the fixed board test-point pitch (1.4 mm); meets the INGUN grid, needs fabricator confirmation'}
            per_plate[name] = {'thickness_mm': t, 'checks': checks}
        reg = {'design': '0.05 bore position to datum pins', 'guidance_standard': rules['standard_tolerance_mm'], 'met': None,
               'note': 'tighter than standard; needs an annotated 2D drawing, availability not confirmed'}
        out.append({'id': ref['id'], 'selection_status': ref['selection_status'], 'plates': per_plate, 'registration_tolerance_mm': reg,
                    'satisfied': all(c['met'] for v in per_plate.values() for c in v['checks'].values() if c['met'] is not None)})
    return out


def validate_report(candidate, root=ROOT):
    """Reject fabricated flags/identity maps; only this producer's output is valid."""
    if Path(root).resolve() != ROOT.resolve():
        raise ValueError('fixture validation requires the actual checked-out producer root')
    if candidate != report():
        raise ValueError('fixture manifest differs from canonical producer output')
    return True


def _rrect(xy, b, r, rounded, k, fill, stroke='none'):
    """SVG path of a member rectangle with the flagged corners (BL, BR, TL, TR in board axes) rounded; y grows down in SVG."""
    x0, y0, x1, y1 = b
    bl, br, tl, tr = [r if f else 0.0 for f in rounded]
    pts = []
    def P(x, y):
        X, Y = xy(x, y)
        return f'{X:.2f} {Y:.2f}'
    d = [f'M {P(x0 + bl, y0)}', f'L {P(x1 - br, y0)}']
    if br: d.append(f'A {br*k:.2f} {br*k:.2f} 0 0 0 {P(x1, y0 + br)}')
    d.append(f'L {P(x1, y1 - tr)}')
    if tr: d.append(f'A {tr*k:.2f} {tr*k:.2f} 0 0 0 {P(x1 - tr, y1)}')
    d.append(f'L {P(x0 + tl, y1)}')
    if tl: d.append(f'A {tl*k:.2f} {tl*k:.2f} 0 0 0 {P(x0, y1 - tl)}')
    d.append(f'L {P(x0, y0 + bl)}')
    if bl: d.append(f'A {bl*k:.2f} {bl*k:.2f} 0 0 0 {P(x0 + bl, y0)}')
    return f'<path d="{" ".join(d)} Z" fill="{fill}" stroke="{stroke}"/>'


def drawing(r):
    """Dimensioned plan views (board coordinates, seen from the F side) of the four plates; NOT FOR FABRICATION."""
    rel = r['b_side_relief']; sc, pp, pr = rel['support_carrier'], rel['probe_plate'], rel['pressure_plate']
    x0c, y0c, x1c, y1c = sc['bounds_board_mm']; k = 7.0
    W, H = (x1c - x0c) * k, (y1c - y0c) * k
    panels = [('Support carrier', 20), ('Probe plate', 20 + W + 40), ('Pressure plate and base', 20 + 2 * (W + 40))]
    total_w = 20 + 3 * (W + 40)
    top = 120
    low = top + (y1c - min(0.0, y0c)) * k  # the board overhangs the plates
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_w:.0f} {low + 230:.0f}">', f'<rect width="{total_w:.0f}" height="{low + 230:.0f}" fill="white"/>',
         '<g font-family="sans-serif" fill="black" font-size="13">',
         f'<text x="20" y="30" font-size="16">A7 SWD fixture — digital design, {r["status"]} / NOT FOR FABRICATION</text>',
         f'<text x="20" y="52">Plan views in board coordinates seen from the F side (z up from the board B face). All dimensions mm; FR-4 plates {x1c - x0c:g} × {y1c - y0c:g}.</text>',
         '<text x="20" y="72">Grey dashed: board outline. Windows are through, corners rounded to the internal radius shown; sharp corners are re-entrant.</text>']
    def frame(ox):
        def xy(x, y):
            return ox + (x - x0c) * k, top + (y1c - y) * k
        return xy
    for title, ox in panels:
        xy = frame(ox)
        a, b = xy(x0c, y1c)
        s.append(f'<text x="{ox}" y="{top - 12}" font-size="14">{title}</text>')
        if title != 'Pressure plate and base':
            s.append(f'<rect x="{a:.2f}" y="{b:.2f}" width="{W:.2f}" height="{H:.2f}" fill="#e8efdf" stroke="black"/>')
    xy = frame(panels[0][1])
    for w in sc['windows']:
        for m in w['members']:
            s.append(_rrect(xy, m['box_board_mm'], w['corner_radius_mm'], m['rounded_corners'], k, 'white'))
    for q in sc['datum_pins']:
        X, Y = xy(*q['board_xy_mm']); s.append(f'<circle cx="{X:.2f}" cy="{Y:.2f}" r="{k:.2f}" fill="#1f5fa8"/><text x="{X + 9:.2f}" y="{Y + 4:.2f}" font-size="11">{q["id"]}</text>')
    for xy_ in sc['fasteners_board_mm']:
        X, Y = xy(*xy_); s.append(f'<circle cx="{X:.2f}" cy="{Y:.2f}" r="{3.0 * k:.2f}" fill="white" stroke="black"/><circle cx="{X:.2f}" cy="{Y:.2f}" r="{1.7 * k:.2f}" fill="none" stroke="black"/>')
    for xy_ in sc['alignment_dowels_board_mm']:
        X, Y = xy(*xy_); s.append(f'<circle cx="{X:.2f}" cy="{Y:.2f}" r="{k:.2f}" fill="white" stroke="#a33"/>')
    for g in sc['guides']:
        X, Y = xy(*g['board_xy_mm']); s.append(f'<circle cx="{X:.2f}" cy="{Y:.2f}" r="{1.7 * k:.2f}" fill="white" stroke="#2a7a2a"/><text x="{X - 8:.2f}" y="{Y - 26:.2f}" font-size="11">{g["id"]}</text>')
    xy = frame(panels[1][1])
    for w in pp['windows']:
        for m in w['members']:
            s.append(_rrect(xy, m['box_board_mm'], w['corner_radius_mm'], m['rounded_corners'], k, 'white'))
    for bo in pp['bores']:
        X, Y = xy(*bo['board_xy_mm']); s.append(f'<circle cx="{X:.2f}" cy="{Y:.2f}" r="{bo["diameter_mm"] / 2 * k:.2f}" fill="white" stroke="black"/>')
    for xy_ in sc['fasteners_board_mm']:
        X, Y = xy(*xy_); s.append(f'<circle cx="{X:.2f}" cy="{Y:.2f}" r="{1.7 * k:.2f}" fill="white" stroke="black"/>')
    for xy_ in sc['alignment_dowels_board_mm']:
        X, Y = xy(*xy_); s.append(f'<circle cx="{X:.2f}" cy="{Y:.2f}" r="{k:.2f}" fill="white" stroke="#a33"/>')
    xy = frame(panels[2][1])
    a, b = xy(x0c, y1c); s.append(f'<rect x="{a:.2f}" y="{b:.2f}" width="{W:.2f}" height="{H:.2f}" fill="#f2f2f2" stroke="#999"/>')
    ts = rel['wiring']['tie_slot_board_mm']
    s.append(_rrect(xy, ts, relief_design.corner_radius(3.0), [True] * 4, k, 'white', '#999'))
    o = pr['outline_board_mm']; a, b = xy(o[0], o[3]); c, d = xy(o[2], o[1])
    s.append(f'<rect x="{a:.2f}" y="{b:.2f}" width="{c - a:.2f}" height="{d - b:.2f}" fill="#f5e6c8" stroke="black"/>')
    n = pr['j5_notch_board_mm']
    s.append(_rrect(xy, [n[0], n[1], n[2], n[3] + 0.01], pr['corner_radius_mm'], [True, True, False, False], k, 'white'))
    for g in sc['guides']:
        X, Y = xy(*g['board_xy_mm']); s.append(f'<circle cx="{X:.2f}" cy="{Y:.2f}" r="{pr["guide_hole_diameter_mm"] / 2 * k:.2f}" fill="white" stroke="black"/>')
    for c_ in rel['holddown']['contacts_board_mm']:
        X, Y = xy(*c_); s.append(f'<circle cx="{X:.2f}" cy="{Y:.2f}" r="{k:.2f}" fill="#2a7a2a"/>')
    X, Y = xy(*rel['holddown']['probe_resultant_board_mm']); s.append(f'<path d="M {X - 5:.2f} {Y:.2f} H {X + 5:.2f} M {X:.2f} {Y - 5:.2f} V {Y + 5:.2f}" stroke="#c00" stroke-width="2"/>')
    for title, ox in panels:
        xy = frame(ox); a, b = xy(0, 62.9); c, d = xy(16.2, 0)
        s.append(f'<rect x="{a:.2f}" y="{b:.2f}" width="{c - a:.2f}" height="{d - b:.2f}" fill="none" stroke="#777" stroke-dasharray="4 3"/>')
    hd, st, reg = rel['holddown'], rel['stack_z_mm'], rel['registration']
    y = low + 30
    lines = [f'Support carrier: {sc["thickness_mm"]:g} thick, {len(sc["windows"])} windows, internal radius {sc["corner_radius_mm"]:g}; datum pins Ø2 (blue) X1, X2, Y1; '
             f'M3 countersunk Ø6 (6);',
             'dowels Ø2 (red) D1, D2; stop standoff holes Ø3.4 (green).',
             f'Probe plate: {pp["thickness_mm"]:g} thick, {len(pp["bores"])} bores Ø{pp["bores"][0]["diameter_mm"]} (finished 0.98-1.00), bore web {pp["bore_webs_mm"][0]} (drilled); '
             f'J5 window radius {pp["corner_radius_mm"]:g}; M3 Ø3.4 (6); dowels Ø2.',
             f'Pressure plate: {st["pressure_plate"][1] - st["pressure_plate"][0]:g} thick, notch radius {pr["corner_radius_mm"]:g}, stop screw holes Ø{pr["guide_hole_diameter_mm"]}, '
             f'plungers {pr["contact_thread"]} tapped (drill Ø{pr["contact_tap_hole_diameter_mm"]}, green dots).',
             f'Plungers at {hd["contacts_board_mm"]}; red cross: probe resultant; board net load point at least {hd["board_net_load_point_inside_land_hull_mm"]:.2f} inside the land.',
             f'Base plate (grey): 3 thick, M3 countersunk (6), tie slot {ts}.',
             f'Stack z: carrier {st["support_carrier"]}, spacers {st["plate_gap_spacers"]}, probe plate {st["probe_plate"]}, standoffs {st["base_standoffs"]}, base {st["base_plate"]},',
             f'pressure plate {st["pressure_plate"]}, stop top {st["stop_top"]}.',
             f'Hold-down: {len(hd["contacts_board_mm"])} x {hd["plunger_candidate"]["mpn"]}, compression {hd["plunger_compression_mm"]["range"]} mm, '
             f'total {hd["total_force_N"]} N >= {hd["required_total_force_N"]} N = {hd["clamp_force_margin_factor"]} x {hd["probe_force_total_N"]["maximum_stroke"]} N probe force at maximum stroke.',
             f'Registration: radial budget {reg["radial_budget_mm"]}, allocated worst-case margin {reg["worst_case_margin_mm"]} (acceptance measurements).']
    for i, line in enumerate(lines):
        s.append(f'<text x="20" y="{y + i * 22:.0f}">{line}</text>')
    s.append('</g></svg>')
    return '\n'.join(s) + '\n'


def cad(r, check=False):
    import a7_fixture_relief as rl
    geometry = json.loads(native_geom.RECORD.read_text())['geometry']
    rel = r['b_side_relief']
    parts = relief_assembly.build(rel, r['pads'], geometry, rl)
    bad = [n for n, _, s in parts if not s.isValid() or len(s.Solids()) != 1]
    if bad:
        raise ValueError('invalid or multi-solid parts: ' + ', '.join(bad))
    if not check:
        relief_assembly.export(parts, ASSEMBLY_STEP)
        inter, touching, clear, contacts = relief_assembly.check(parts)
        gsha = digest(native_geom.RECORD)
        rec = {'schema': 1, 'tool': 'CadQuery 2.7.0', 'model_inputs_sha256': relief_assembly.design_digest(rel, gsha),
               'model_inputs': relief_assembly.model_inputs(rel, gsha), 'step_sha256': digest(ASSEMBLY_STEP),
               'method': 'pairwise boolean common volume between every two solids whose bounding boxes meet (board part boxes are not checked '
                         'against each other); interference above the threshold; clearances by exact BRep distance',
               'interference_threshold_mm3': relief_assembly.TOL_MM3, 'modelling': relief_assembly.__doc__.strip().split('\n\n')[1],
               'solids': relief_assembly.summary(parts), 'interferences': inter, 'touching_or_zero_volume_pairs': touching,
               'clearances': clear, 'designed_contacts': contacts,
               'scope': 'digital interference check of the modelled envelopes; not a fit result'}
        INTERFERENCE.write_text(json.dumps(rec, indent=2) + '\n')
        print(f'assembly STEP written: {len(parts)} solids, {len(inter)} interferences, {touching} touching pairs')
    import cadquery as cq
    shape = cq.importers.importStep(str(ASSEMBLY_STEP)).val()
    solids = shape.Solids()
    want = sum(s.Volume() for _, _, s in parts)
    got = sum(s.Volume() for s in solids)
    if not shape.isValid() or len(solids) != len(parts) or abs(got - want) > 1e-3:
        raise ValueError(f'assembly STEP differs from the rebuilt model: {len(solids)} solids / {got:.4f} mm3 vs {len(parts)} / {want:.4f}')
    print(f'CadQuery 2.7.0 assembly STEP valid: {len(solids)} solids, total volume {got:.4f} mm3 matches the rebuilt model')


def _stop_joint_two_sided(clamps, f_band, ys, half_face):
    """Screw tension that keeps the plate on both stop-face edges for every plunger-force corner (re-derivation)."""
    import itertools
    near, far = ys - half_face, ys + half_face
    worst = 0.0
    for fs in itertools.product(f_band, repeat=len(clamps)):
        total = sum(fs)
        about_far = sum(f * (far - q[1]) for f, q in zip(fs, clamps)) / (far - ys)
        about_near = sum(f * (q[1] - near) for f, q in zip(fs, clamps)) / (ys - near)
        worst = max(worst, total, about_far, about_near)
    return round(worst, 6)


def cad_candidate(check=False):
    """Build the candidate at 0.7/0.8/0.9 mm, check it and write its STEP (0.8 mm) and record; --cad-check compares the STEP."""
    import a7_fixture_relief as rl
    import a7_fixture_support as support
    geometry = json.loads(native_geom.RECORD.read_text())['geometry']
    pads = probe_map(bound_r4_placement(), BOARD.read_text())
    rel, tips = candidate_design(geometry, pads)
    if check:
        parts = relief_assembly.build(rel, pads, geometry, rl, pin_tips=tips)
        import cadquery as cq
        shape = cq.importers.importStep(str(CANDIDATE_STEP)).val()
        solids = shape.Solids()
        want, got = sum(x.Volume() for _, _, x in parts), sum(x.Volume() for x in solids)
        if not shape.isValid() or len(solids) != len(parts) or abs(got - want) > 1e-3:
            raise ValueError(f'candidate STEP differs from the rebuilt model: {len(solids)} solids / {got:.4f} mm3 vs {len(parts)} / {want:.4f}')
        print(f'CadQuery 2.7.0 candidate STEP valid: {len(solids)} solids, total volume {got:.4f} mm3 matches the rebuilt model')
        return
    matrix = json.loads(CONDITION_MATRIX.read_text())
    adopted = matrix['adopted_candidate']
    bands = {b['thickness_mm']: b for b in matrix['layouts'][CANDIDATE_LAYOUT]['force_band_per_thickness']}
    prop = support.diagonal_proposal(geometry)
    R, hd, pr = rel['rules'], rel['holddown'], rel['pressure_plate']
    pl = hd['plunger_candidate']
    band = R['plunger_force_acceptance_band']
    contact_d = support.stepped_tip_contacts(pl['pin_diameter_mm'])
    local_notch = prop['local_notch_clearance_requirement_mm']

    def force(d):
        return pl['force_initial_N'] + (pl['force_final_N'] - pl['force_initial_N']) * d / pl['stroke_mm']
    cases, nominal_parts, nominal_plan = [], None, None
    for t in CANDIDATE_THICKNESSES:
        parts = relief_assembly.build(rel, pads, geometry, rl, pin_tips=tips, board_thickness=t)
        bad = [n for n, _, x in parts if not x.isValid() or len(x.Solids()) != 1]
        if bad:
            raise ValueError('invalid or multi-solid candidate parts: ' + ', '.join(bad))
        inter, touching, clear, contacts = relief_assembly.check(parts, relief_assembly.CANDIDATE_CLEARANCE_PAIRS)
        plan = relief_assembly.pin_plan(parts, rl.BOARD, t)
        exposed = min(p['sleeve_end_above_f_face_mm'] for p in plan)
        d_nom = round(pl['stroke_mm'] - exposed, 6)
        tol = R['plate_stack_acceptance_tolerance_mm'] + R['plunger_setting_tolerance_mm']
        sag = bands[t]['clamp_sag_at_maximum_force_mm']
        d_lo = round(d_nom - tol - hd['plunger_compression_mm']['plate_deflection_mm'] - sag, 6)
        d_hi = round(d_nom + tol, 6)
        f_lo, f_hi = round(force(d_lo) * (1 - band), 6), round(force(d_hi) * (1 + band), 6)
        corner = [c for c in matrix['layouts'][CANDIDATE_LAYOUT]['cases'] if c.get('thickness_mm') == t]
        clear_by = {c['pair']: c['minimum_mm'] for c in clear}
        case = {'thickness_mm': t, 'solids': len(parts), 'interferences': inter, 'touching_or_zero_volume_pairs': touching,
                'clearances': clear, 'designed_contacts': contacts, 'pins': plan,
                'compression_mm': {'nominal': d_nom, 'range': [d_lo, d_hi],
                                   'basis': 'stroke minus the pin length below the sleeve end in the CAD; +/- stop length and pin '
                                            'setting tolerances; the minimum also loses the plate deflection and the contact-model '
                                            'board sag at maximum force for this thickness (condition-matrix.json)'},
                'plunger_force_each_N': [f_lo, f_hi], 'total_force_min_N': round(len(plan) * f_lo, 6),
                'required_total_force_N': hd['required_total_force_N'],
                'contact_stress': [support.contact_stress(d, f_hi) for d in contact_d],
                'matrix_load_corners': len(corner),
                'matrix_worst_probe_displacement_mm': max((c['probe_displacement_max_abs_mm'] for c in corner), default=None),
                'matrix_worst_land_lift_mm': max((c['land_lift_max_mm'] for c in corner), default=None),
                'matrix_corners_within_limits': bool(corner) and all(c['probe_displacement_within_limit'] and c['land_lift_within_limit']
                                                                      for c in corner),
                'checks': {
                    'no_interference': not inter,
                    'critical_clearances_positive': all(c['minimum_mm'] is not None and c['minimum_mm'] > 0 for c in clear),
                    'designed_contacts_touch': all(c['touching'] for c in contacts),
                    'j5_notch_clearance_meets_local_requirement': clear_by['J5 body (courtyard x height) to the pressure-plate notch'] >= local_notch - 1e-9,
                    'f_side_bodies_to_plate_meet_local_requirement': clear_by['F-side bodies to pressure plate'] >= local_notch - 1e-9,
                    'board_contact_is_the_specified_diameter': [p['contact_diameter_mm'] for p in plan] == [round(d, 4) for d in contact_d],
                    'compression_positive': d_lo > 0,
                    'compression_within_stroke': d_hi <= pl['stroke_mm'] - R['plunger_stroke_end_margin_mm'] + 1e-9,
                    'sleeve_end_clear_of_f_face_at_maximum_compression': round(pl['stroke_mm'] - d_hi, 6) >= R['plunger_body_end_clearance_min_mm'] - 1e-9,
                    'clamp_force_min_meets_requirement': len(plan) * f_lo >= hd['required_total_force_N'] - 1e-9,
                    'contact_pressure_within_assumed_allowable': all(x['within_assumed_allowable'] for x in (support.contact_stress(d, f_hi) for d in contact_d)),
                    'matrix_load_corners_within_limits': bool(corner) and all(c['probe_displacement_within_limit'] and c['land_lift_within_limit'] for c in corner),
                }}
        cases.append(case)
        if abs(t - rl.BOARD_THICKNESS) < 1e-9:
            nominal_parts, nominal_plan = parts, plan
    relief_assembly.export(nominal_parts, CANDIDATE_STEP)
    # the shank shows below the sleeve only when the compression is small (thin board): take its worst exposed case
    clamps = [{'clamp': f'C{i + 1}', 'centre_mm': list(c), 'contact_diameter_mm': p['contact_diameter_mm'],
               'contact_edge_margin_nominal_mm': p['contact_edge_margin_nominal_mm'],
               'shank_edge_margin_nominal_mm': min(t['pins'][i]['shank_edge_margin_nominal_mm'] for t in cases)}
              for i, (c, p) in enumerate(zip(hd['contacts_board_mm'], nominal_plan))]
    notch_pair = 'J5 body (courtyard x height) to the pressure-plate notch'
    notch_nominal = min(next(c['minimum_mm'] for c in t['clearances'] if c['pair'] == notch_pair) for t in cases)
    registration = candidate_registration(rel, clamps, adopted['pin_edge_margin_required_mm'])
    plate_float = registration['pressure_plate_location']['worst_plate_offset_mm']
    registration['j5_notch_clearance'] = {
        'nominal_cad_mm': notch_nominal, 'local_requirement_mm': local_notch,
        'recorded_notch_edge_tolerance_mm': prop['tolerance_budget_mm']['notch_edge'],
        'with_plate_float_mm': round(notch_nominal - plate_float - prop['tolerance_budget_mm']['notch_edge'], 6),
        'meets_local_requirement_with_plate_float': notch_nominal - plate_float - prop['tolerance_budget_mm']['notch_edge'] >= local_notch - 1e-9}
    by_clamp = {r['clamp']: r for r in registration['clamps']}
    rows = [dict(c, **{k: v for k, v in by_clamp[c['clamp']].items() if k not in c}) for c in clamps]
    f_band = (min(c['plunger_force_each_N'][0] for c in cases), max(c['plunger_force_each_N'][1] for c in cases))
    stop = {'relief_strip_record': hd['stop_joint'],
            'two_sided_required_screw_tension_total_N': _stop_joint_two_sided(hd['contacts_board_mm'], f_band, hd['stop_line_y_mm'],
                                                                              R['m3_hex_across_flats_mm'] / 2),
            'basis': 'independent re-derivation: the pins now sit on both sides of the stop line, so the plate may tip about '
                     'either edge of the stop faces; the screws must also carry the whole plunger load'}
    stop['holds'] = hd['stop_joint']['preload_total_N'] >= R['clamp_force_margin_factor'] * stop['two_sided_required_screw_tension_total_N']
    gsha = digest(native_geom.RECORD)
    rec = {'schema': 1, 'tool': 'CadQuery 2.7.0', 'status': CANDIDATE_STATUS,
           'scope': 'digital CAD model and interference/clearance/stroke check of the proposed replacement candidate, built beside '
                    'the retained fixture geometry; not a fit result, not a selection and not a fabrication approval',
           'model_inputs_sha256': candidate_digest(rel, tips, gsha), 'model_inputs': candidate_inputs(rel, tips, gsha),
           'step_sha256': digest(CANDIDATE_STEP), 'step_board_thickness_mm': rl.BOARD_THICKNESS,
           'method': 'as assembly-interference.json for each finished board thickness; the board B face stays on the carrier and the '
                     'plunger sleeves stay where the plate and the pin setting put them (displacement control)',
           'interference_threshold_mm3': relief_assembly.TOL_MM3,
           'candidate': {'layout': CANDIDATE_LAYOUT, 'relief_candidate': CANDIDATE_RELIEF,
                         'contacts_board_mm': hd['contacts_board_mm'], 'contact_diameters_mm': contact_d,
                         'stepped_tip': support.STEPPED_TIP, 'stepped_tip_length_mm': support.STEPPED_TIP['tip_length_mm'],
                         'pin_shank_diameter_mm': pl['pin_diameter_mm'], 'plunger': pl['mpn'],
                         'j5_notch_board_mm': pr['j5_notch_board_mm'], 'notch_corner_radius_mm': pr['corner_radius_mm'],
                         'pressure_plate_outline_board_mm': pr['outline_board_mm'], 'pressure_plate_z_mm': pr['z_mm'],
                         'pin_setting_below_plate_underside_mm': hd['plunger_setting_mm'],
                         'local_notch_clearance_requirement_mm': local_notch,
                         'retained_notch_clearance_requirement_mm': R['pressure_plate_part_clearance_mm'],
                         'pressure_plate_webs': pr['smallest_webs'], 'pressure_plate_web_conflicts': pr['web_conflicts']},
           'thickness_cases': cases, 'clamps': rows, 'registration': registration, 'stop_joint': stop,
           'pressure_plate_deflection': {'strip_record_mm': hd['plunger_compression_mm']['plate_deflection_mm'],
                                         'notch_reduced_plate_depth_mm': round(pr['j5_notch_board_mm'][1] - pr['outline_board_mm'][1], 6),
                                         'strip_width_used_mm': R['board_strip_width_mm'],
                                         'note': 'the strip value takes the whole plunger load at mid-span of the 27.2 mm stop span on a '
                                                 '5 mm wide strip with the ASSUMED 18000 MPa modulus; the plate material left beside the '
                                                 'notch is deeper than that strip, so the value stays an upper bound for this plate'},
           'strip_model_diagnostic': {'criterion_3_checks': rel['criterion_3_checks'],
                                      'board_bending_mm': rel['holddown']['board_bending_across_window']['deflection_mm'],
                                      'note': 'the retained criterion-3 strip model applied to the candidate; it still fails board '
                                              'bending, which is why the candidate rests on the contact-model condition matrix. '
                                              'Changing the criterion-3 method is not done here.'}}
    rec['rule_changes_in_candidate'] = [
        {'rule': 'F-side part clearance at the J5 notch', 'retained_mm': R['pressure_plate_part_clearance_mm'],
         'candidate': f"local {local_notch} mm minimum plus an explicit tolerance budget (a7_fixture_support.diagonal_proposal)",
         'cad_nominal_mm': notch_nominal, 'meets_retained_rule': notch_nominal >= R['pressure_plate_part_clearance_mm'] - 1e-9,
         'status': 'method change carried by the candidate definition, not by this CAD check; needs owner/independent acceptance'},
        {'rule': 'board-edge margin of a hold-down pin', 'retained': 'taken at the catalogue 1.5 mm pin diameter',
         'candidate': adopted['edge_margin_basis'], 'required_mm': adopted['pin_edge_margin_required_mm'],
         'status': 'requirement value unchanged; applied to the board-contact diameter of the turned tip'},
        {'rule': 'criterion-3 board bending model', 'retained': 'conservative strip model (fails for both layouts on the 0.7 mm board)',
         'candidate': 'converged unilateral contact model (condition-matrix.json)',
         'status': 'not adopted for criterion 3; the retained criterion 3 still uses the strip model and stays not met'}]
    rec['matrix_correspondence_problems'] = candidate_matrix_correspondence(rec, matrix)
    checks = {k: all(c['checks'][k] for c in cases) for k in cases[0]['checks']}
    checks.update({'pressure_plate_webs_at_least_minimum': not pr['web_conflicts'],
                   'stop_joint_preload_holds_plate': stop['holds'],
                   'registration_closes_with_recorded_budget': registration['recorded_budget_closes'],
                   'registration_closes_with_modelled_plate_location': registration['closes_with_plate_float'],
                   'j5_notch_clearance_holds_with_modelled_plate_location': registration['j5_notch_clearance']['meets_local_requirement_with_plate_float'],
                   'matches_condition_matrix': not rec['matrix_correspondence_problems']})
    rec['checks'] = checks
    rec['all_digital_checks_met'] = all(checks.values())
    rec['holds'] = CANDIDATE_HOLDS
    CANDIDATE_RECORD.write_text(json.dumps(rec, indent=2) + '\n')
    print(f"candidate STEP written: {len(nominal_parts)} solids; interferences per thickness "
          f"{[len(c['interferences']) for c in cases]}; all digital checks met {rec['all_digital_checks_met']}")


def candidate_drawing(r):
    """Plan of the candidate pressure plate with the stepped-tip detail; NOT FOR FABRICATION, generated from the record."""
    cand = r['proposed_replacement_candidate']
    rec = json.loads(CANDIDATE_RECORD.read_text())
    c = rec['candidate']
    x0, y0, x1, y1 = c['pressure_plate_outline_board_mm']
    k, ox, top = 14.0, 40.0, 110.0
    W, H = (x1 - x0) * k, (y1 - y0) * k

    def xy(x, y):
        return ox + (x - x0) * k, top + (y1 - y) * k
    geometry = json.loads(native_geom.RECORD.read_text())['geometry']
    VW = 1500
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VW} {H + 470:.0f}">',
         f'<rect width="{VW}" height="{H + 470:.0f}" fill="white"/>', '<g font-family="sans-serif" fill="black" font-size="13">',
         '<text x="20" y="30" font-size="16">A7 SWD fixture — PROPOSED replacement candidate (optical_stepped_tip): NOT SELECTED / NOT FOR FABRICATION</text>',
         '<text x="20" y="52">Pressure plate seen from the F side, board coordinates (mm). The retained geometry is fixture-drawing.svg.</text>',
         f'<text x="20" y="72">All digital checks met: {rec["all_digital_checks_met"]} (registration with the modelled plate location: '
         f'{rec["checks"]["registration_closes_with_modelled_plate_location"]}).</text>']
    a, b = xy(x0, y1)
    s.append(f'<rect x="{a:.2f}" y="{b:.2f}" width="{W:.2f}" height="{H:.2f}" fill="#f5e6c8" stroke="black"/>')
    n = c['j5_notch_board_mm']
    s.append(_rrect(xy, [n[0], n[1], n[2], n[3] + 0.01], c['notch_corner_radius_mm'], [True, True, False, False], k, 'white', 'black'))
    for f in geometry['footprints']:
        cb = f['courtyard_bbox_mm'].get('F') if f['side'] == 'F' else None
        if not cb or cb[3] < y0 or cb[1] > y1:
            continue
        p, q = xy(max(cb[0], x0), min(cb[3], y1)), xy(min(cb[2], x1), max(cb[1], y0))
        colour = '#c00' if f['ref'] == 'J5' else '#888'
        s.append(f'<rect x="{p[0]:.2f}" y="{p[1]:.2f}" width="{q[0] - p[0]:.2f}" height="{q[1] - p[1]:.2f}" fill="none" stroke="{colour}" stroke-width="0.8"/>')
    p, q = xy(0, y1), xy(16.2, y0)
    s.append(f'<rect x="{p[0]:.2f}" y="{p[1]:.2f}" width="{q[0] - p[0]:.2f}" height="{q[1] - p[1]:.2f}" fill="none" stroke="#555" stroke-dasharray="5 3"/>')
    for g in r['b_side_relief']['holddown']['guides']:
        X, Y = xy(*g['board_xy_mm'])
        s.append(f'<circle cx="{X:.2f}" cy="{Y:.2f}" r="{3.4 / 2 * k:.2f}" fill="white" stroke="black"/><text x="{X - 8:.2f}" y="{Y - 30:.2f}" font-size="11">{g["id"]} Ø3.4</text>')
    for row, d in zip(rec['clamps'], c['contact_diameters_mm']):
        X, Y = xy(*row['centre_mm'])
        s.append(f'<circle cx="{X:.2f}" cy="{Y:.2f}" r="{3.3 / 2 * k:.2f}" fill="white" stroke="black"/>')
        s.append(f'<circle cx="{X:.2f}" cy="{Y:.2f}" r="{4.05 / 2 * k:.2f}" fill="none" stroke="#2a7a2a" stroke-dasharray="3 2"/>')
        s.append(f'<circle cx="{X:.2f}" cy="{Y:.2f}" r="{c["pin_shank_diameter_mm"] / 2 * k:.2f}" fill="none" stroke="#1f5fa8"/>')
        s.append(f'<circle cx="{X:.2f}" cy="{Y:.2f}" r="{d / 2 * k:.2f}" fill="#1f5fa8"/>')
        s.append(f'<text x="{X + 30:.2f}" y="{Y + 4:.2f}" font-size="11">{row["clamp"]} ({row["centre_mm"][0]:g}, {row["centre_mm"][1]:g}) contact Ø{d:g}</text>')
    # stepped-tip elevation detail (C2, 0.8 mm board, nominal compression), scale 40 px/mm
    case = next(t for t in rec['thickness_cases'] if abs(t['thickness_mm'] - rec['step_board_thickness_mm']) < 1e-9)
    pin = case['pins'][-1]
    e, ex, ey = 40.0, W + 120, top + 40
    tip, shank = c['contact_diameters_mm'][-1], c['pin_shank_diameter_mm']
    lt, sl = c['stepped_tip_length_mm'], pin['sleeve_end_above_f_face_mm']
    s.append(f'<text x="{ex - 60:.2f}" y="{ey - 20:.2f}" font-size="14">C2 stepped tip, 0.8 mm board (elevation)</text>')
    s.append(f'<rect x="{ex - 100:.2f}" y="{ey + 200:.2f}" width="200" height="{0.8 * e:.2f}" fill="#d9ead3" stroke="black"/>')
    s.append(f'<rect x="{ex - tip / 2 * e:.2f}" y="{ey + 200 - min(lt, sl) * e:.2f}" width="{tip * e:.2f}" height="{min(lt, sl) * e:.2f}" fill="#1f5fa8"/>')
    s.append(f'<rect x="{ex - 2.0 * e:.2f}" y="{ey + 200 - sl * e - 60:.2f}" width="{4.0 * e:.2f}" height="60" fill="#bbb" stroke="black"/>')
    s.append(f'<text x="{ex + 2.2 * e:.2f}" y="{ey + 200 - sl * e - 25:.2f}" font-size="11">steel sleeve Ø4 (end {sl:g} above F face)</text>')
    s.append(f'<text x="{ex + 2.2 * e:.2f}" y="{ey + 200 - lt * e / 2:.2f}" font-size="11">tip Ø{tip:g} x {lt:g} (shank Ø{shank:g} above, inside the sleeve)</text>')
    s.append(f'<text x="{ex + 2.2 * e:.2f}" y="{ey + 200 + 0.8 * e / 2 + 4:.2f}" font-size="11">board 0.8 (0.7-0.9)</text>')
    y = top + H + 60
    reg = rec['registration']
    lines = [f'Plate {x1 - x0:g} x {y1 - y0:g} x {c["pressure_plate_z_mm"][1] - c["pressure_plate_z_mm"][0]:g} FR-4 (z {c["pressure_plate_z_mm"]}); '
             f'J5 notch {n} open to the plate edge, inner radius {c["notch_corner_radius_mm"]:g};',
             'M4 tapped C1, C2 (drill Ø3.3, thread envelope Ø4.05 dashed); stop holes G1, G2 Ø3.4.',
             f'Pins: {c["plunger"]} POM, shank Ø{c["pin_shank_diameter_mm"]:g} (outline), board contact filled; C2 turned tip Ø{tip:g} max x {lt:g} (PROPOSED modification).',
             'Red: J5 courtyard; grey: other F courtyards; dashed: board outline.',
             'Per thickness 0.7 / 0.8 / 0.9 mm: interferences ' + ' / '.join(str(len(t['interferences'])) for t in rec['thickness_cases'])
             + '; compression ' + ' / '.join(str(t['compression_mm']['range']) for t in rec['thickness_cases']) + ' mm.',
             'Edge margins C1/C2 contact (nominal CAD): ' + ' / '.join(f"{r_['contact_edge_margin_nominal_mm']:g}" for r_ in rec['clamps'])
             + '; with the recorded 0.10 budget: ' + ' / '.join(f"{r_['contact_edge_margin_recorded_budget_mm']:g}" for r_ in rec['clamps'])
             + f" (required {reg['required_contact_edge_margin_worst_mm']:g}).",
             f"Plate located only by M3 in Ø3.4 clearance holes (up to {reg['pressure_plate_location']['worst_plate_offset_mm']:g} mm): "
             + 'margins then ' + ' / '.join(f"{r_['contact_edge_margin_with_plate_float_mm']:g}" for r_ in rec['clamps']) + ' — registration NOT closed.',
             'Status: PROPOSED replacement candidate; calculated and digitally modelled, not selected, not approved, not physically validated.']
    for i, line in enumerate(lines):
        s.append(f'<text x="20" y="{y + i * 22:.0f}">{line}</text>')
    s.append('</g></svg>')
    return '\n'.join(s) + '\n'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');ap.add_argument('--cad',action='store_true');ap.add_argument('--cad-check',action='store_true');args=ap.parse_args()
    if args.cad and not args.check:  # write the STEP and interference records first so the manifest binds them
        cad(report())
        cad_candidate()
    r=report()
    if args.check and r['proposed_replacement_candidate'].get('bound'):
        problems=candidate_matrix_correspondence(json.loads(CANDIDATE_RECORD.read_text()))
        if problems: raise ValueError('candidate record disagrees with condition-matrix.json: '+'; '.join(problems))
    outputs={'manifest.json':json.dumps(r,indent=2)+'\n','fixture-drawing.svg':drawing(r)}
    if CANDIDATE_RECORD.is_file(): outputs['candidate-drawing.svg']=candidate_drawing(r)
    for n,text in outputs.items():
        p=OUT/n
        if args.check:
            if not p.exists() or p.read_text()!=text: raise ValueError(f'stale fixture study: {p}')
        else:p.write_text(text)
    if args.cad_check: cad(r,True); cad_candidate(True)
    print(f"Fixture validation PASS; status {r['status']}, digital_fixture_complete {r['digital_fixture_complete']}")

if __name__=='__main__':main()
