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
BOARD_SHA = '4453f818ede1e6d6c56e45ef43aa6faecb90990f3755f82c6d752258cd4d628e'
PLACEMENT_SHA = '1891af356ead303127c6b7a99b8934b08aa25f465b4b2c96872f5d5d24afdc01'
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
            'artifact_zip_sha256': prov['artifact_zip_sha256'], 'probe_pads_match': True,
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
    completion = {
        '1_native_support_and_relief': {'met': fresh, 'basis': 'fresh_native_criteria' + ('' if fresh else ' not all met: ' + ', '.join(k for k, v in criteria.items() if not v))},
        '2_keying_and_registration': {'met': relief['keying']['keyed'] and relief['registration']['worst_case_margin_mm'] >= 0,
                                      'basis': 'turned-pose blocking features and radial allocation closed by acceptance-measurement requirements'},
        '3_stroke_stop_guide_fixing_insulation_wiring': {'met': all(c3.values()), 'checks': c3,
                                                         'basis': 'stroke and installation height, carrier-land travel stop, screw-down spring pressure plate on guide standoffs, '
                                                                  'plate stack on spacers/standoffs/base with dowel alignment, FR-4 plates with nylon board contacts, wire bend space and tie slot'},
        '4_assembly_step_interference_check': {'met': asm_ok, 'basis': asm_basis},
        '5_physical_tests': {'met': False, 'basis': 'physical; tracked by the fixture-contact procedure, all observations NOT_MEASURED'},
    }
    digital = [k for k in completion if not k.startswith('5_')]
    blockers = [
        *([] if fresh else ['fresh_native_verified false: ' + '; '.join(
            [f'{u} is unsourced (the carrier and probe-plate windows and the base clearance do not depend on it up to the stated bound)' for u in relief['unknown_heights']]
            + [f'{k} not met' for k, v in criteria.items() if not v and k != 'every_b_face_protrusion_sourced'])]),
        *[f'criterion {k} not met: {v["basis"]}' for k, v in completion.items() if k in digital[1:] and not v['met']],
    ]
    candidate_checks = candidate_reference_checks(relief)
    owner_items = [
        'Fabricator for the four FR-4 plates is an owner choice and not selected; JLCCNC guidance is a candidate reference only. '
        f"The probe-plate bores are drilled at the board test-point pitch, leaving {relief['probe_plate']['bore_webs_mm'][0]} mm between bores: "
        f"this meets the INGUN receptacle grid ({relief['rules']['probe_bore_web_minimum_mm']} mm) but not the 1.0 mm milled-wall guidance, "
        'so the chosen fabricator must confirm drilling it; the board pitch is fixed.',
        'Registration needs the bore positions within 0.05 mm of the datum pins, tighter than the +/-0.1 mm standard tolerance: an annotated 2D drawing is needed.',
        'Springs, screws, spacers, standoffs, pins, dowels, washers and nylon contact screws are specified as requirements (materials.json); no part is selected.',
        'Receptacle drawing diameter 0.96 mm versus PDF table 0.95 mm; the bore follows the 0.98-1.00 mm FR-4 mounting-hole data, resolve before selection.',
    ]
    physical_items = ['No physical fit, contact, insertion-force or measured stroke evidence; no prototype exists; every acceptance measurement in b_side_relief is a requirement, not a result.']
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
        scope='Digital fixture design: support carrier, probe plate, pressure plate, base plate and hardware envelopes with the assembly STEP and '
              'interference check; not a fit result, not a selection and not a fabrication approval',
        board_sha256=digest(BOARD), placement_sha256=digest(CANONICAL), geometry_sha256=p['geometry_sha256'],
        inputs_sha256={str(path.relative_to(ROOT)): digest(path) for path in files},
        assembly=asm,
        fresh_native_verified=fresh, fresh_native_criteria=criteria, completion_criteria=completion,
        native_geometry=native, b_side_relief=relief,
        native_ci_evidence={'observed_date_utc':'2026-11-11','run_url':'https://github.com/Takazudo/zudo-led-block/actions/runs/42596523199','head_sha':'f0b1d8aa37f3967ccc8c9a6bd6ca0e7b7fc7b3a0','base_sha':'af523f9abb74e206c27aaaa076b3b68a5c474940','result':'PASS','board_sha256':BOARD_SHA,'scope':'Pinned native CI of the PR #44 preparation head on the unchanged board (CI log result); not verification of fixture geometry','raw_facts_consumed':False,'artifact_access':'2026-11-09: download Forbidden (historical). 2026-11-11: native-infrastructure-evidence artifact 13663737750 downloaded (ZIP SHA-256 33f3d9121164f364b0325540b161e9546ddf73c8b723c9166fdcd8a19867cf0e), but it retains only a7-gate/summary.json; candidate board_facts/board_geometry were not uploaded, so raw candidate facts remain unavailable'},
        transform={'description':'Board coordinates for every part: x, y as on the PCB, z up from the board B face (carrier top). The B-view carrier coordinates in b_side_relief are x_c = 16.2 - x_board.','matrix_xy_b_view':[[-1,0,16.2],[0,1,0],[0,0,1]]},
        pads=pads,
        calculations={'nominal_radial_budget_mm':(1.0-0.5)/2,'worst_case_registration_margin_mm':relief['registration']['worst_case_margin_mm'],'registration_equation':'0.25 - (board edge-to-pad + datum registration + bore position + probe lateral play/concentricity); all terms radial worst-case mm, each allocation closed by an acceptance measurement (b_side_relief.registration)','minimum_probe_pitch_mm':round(spacing,6),'manufacturer_nominal_grid_mm':1.27,'nominal_collar_edge_gap_mm':round(spacing-1.04,6),'recommended_working_stroke_mm':4.3,'maximum_stroke_mm':6.35,'nominal_total_force_at_working_stroke_N':5*1.0,'nominal_total_preload_N':5*0.44,'total_force_at_maximum_stroke_N':hd['probe_force_total_N']['maximum_stroke'],'required_total_spring_force_N':hd['required_total_spring_force_N'],'clamp_force_margin_factor':hd['clamp_force_margin_factor'],'force_tolerance_N':None},
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
             'dowels Ø2 (red) D1, D2; guide standoff holes Ø3.4 (green).',
             f'Probe plate: {pp["thickness_mm"]:g} thick, {len(pp["bores"])} bores Ø{pp["bores"][0]["diameter_mm"]} (finished 0.98-1.00), bore web {pp["bore_webs_mm"][0]} (drilled); '
             f'J5 window radius {pp["corner_radius_mm"]:g}; M3 Ø3.4 (6); dowels Ø2.',
             f'Pressure plate: 3 thick, notch radius {pr["corner_radius_mm"]:g}, guide holes Ø{pr["guide_hole_diameter_mm"]}, contacts M2 nylon tapped Ø{pr["contact_tap_hole_diameter_mm"]} (green dots).',
             f'Contacts at {hd["contacts_board_mm"]}; red cross: probe resultant, inside the contact triangle by {hd["probe_resultant_margin_mm"]:.2f}.',
             f'Base plate (grey): 3 thick, M3 countersunk (6), tie slot {ts}.',
             f'Stack z: carrier {st["support_carrier"]}, spacers {st["plate_gap_spacers"]}, probe plate {st["probe_plate"]}, standoffs {st["base_standoffs"]}, base {st["base_plate"]},',
             f'pressure plate {st["pressure_plate"]}, guide standoff top {st["guide_standoff_top"]}.',
             f'Clamp: two springs, each >= {hd["spring_requirement"]["force_min_over_range_N"]} N at {hd["spring_requirement"]["installed_length_range_mm"]} mm '
             f'(total {hd["required_total_spring_force_N"]} N = {hd["clamp_force_margin_factor"]} x {hd["probe_force_total_N"]["maximum_stroke"]} N probe force at maximum stroke).',
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


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');ap.add_argument('--cad',action='store_true');ap.add_argument('--cad-check',action='store_true');args=ap.parse_args()
    if args.cad and not args.check: cad(report())  # write the STEP and interference record first so the manifest binds them
    r=report()
    outputs={'manifest.json':json.dumps(r,indent=2)+'\n','fixture-drawing.svg':drawing(r)}
    for n,text in outputs.items():
        p=OUT/n
        if args.check:
            if not p.exists() or p.read_text()!=text: raise ValueError(f'stale fixture study: {p}')
        else:p.write_text(text)
    if args.cad_check: cad(r,True)
    print(f"Fixture validation PASS; status {r['status']}, digital_fixture_complete {r['digital_fixture_complete']}")

if __name__=='__main__':main()
