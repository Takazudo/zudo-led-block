#!/usr/bin/env python3
"""Revision-bound A7 fixture carrier design; never an assembly, fit or fabrication approval.

Normal generation emits JSON/SVG only. --cad creates the carrier study STEP using
CadQuery 2.7.0; --cad-check imports it and checks volume/bounds/validity.
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
    completion = {
        '1_native_support_and_relief': {'met': fresh, 'basis': 'fresh_native_criteria' + ('' if fresh else ' not all met: ' + ', '.join(k for k, v in criteria.items() if not v))},
        '2_keying_and_registration': {'met': relief['keying']['keyed'] and relief['registration']['worst_case_margin_mm'] >= 0,
                                      'basis': 'turned-pose blocking features and radial allocation closed by acceptance-measurement requirements'},
        '3_stroke_stop_guide_fixing_insulation_wiring': {'met': False, 'basis': 'stroke, travel stop and clamp points/force are designed; the hold-down/bias mechanism, probe guide plate, base fixing, insulation and wire retention are not selected or designed'},
        '4_assembly_step_interference_check': {'met': False, 'basis': 'only the carrier STEP exists; no complete assembly STEP or interference check'},
        '5_physical_tests': {'met': False, 'basis': 'physical; tracked by the fixture-contact procedure, all observations NOT_MEASURED'},
    }
    blockers = [
        *([] if fresh else ['fresh_native_verified false: ' + '; '.join(
            [f'{u} is unsourced (the carrier through-cut does not depend on it; the base below the carrier does)' for u in relief['unknown_heights']]
            + [f'{k} not met' for k, v in criteria.items() if not v and k != 'every_b_face_protrusion_sourced'])]),
        f"Hold-down/bias mechanism not selected (owner/supplier choice): it must press the three listed F-side points with more than {hd['required_clamp_force_N']} N in total and bias the board against X1, X2 and Y1; probe guide, base fixing, insulation and wire retention are not designed.",
        'No complete assembly STEP/drawing with an interference check; the carrier STEP alone is not a finished fixture.',
        'Receptacle drawing diameter 0.96mm versus PDF table 0.95mm; use 0.96mm envelope only as conservative study input, resolve before selection.',
        'No physical fit, contact, insertion-force or measured stroke evidence; no prototype exists; the acceptance measurements in b_side_relief are requirements, not results.',
        *(['Hole to cut web below the 0.27 mm sourced minimum: ' + '; '.join(relief['web_conflicts'])] if relief['web_conflicts'] else []),
        *(['Cut wall below the 0.27 mm sourced minimum: ' + '; '.join(relief['relief_wall_conflicts'])] if relief['relief_wall_conflicts'] else []),
    ]
    candidate_checks = candidate_reference_checks(relief)
    narrow = candidate_checks[0]['checks']['narrowest_cut_rectangle_mm']['design'] if candidate_checks else None
    blockers.append(f'Carrier manufacturability not confirmed: the narrowest cut rectangle is {narrow} mm, merge bridges are 0.025-0.25 mm wide and every internal corner is sharp, so the process must cut the merged shapes as drawn (or widen the bridges) and hold the 0.27 mm walls; no fabricator is selected and the captured JLCCNC guidance (candidate reference only) is not satisfied.')
    complete = all(c['met'] for c in completion.values()) and not blockers
    files = (BOARD, CANONICAL, Path(__file__).resolve(), Path(relief_design.__file__).resolve(), relief_design.POPULATION, OUT/'sources.json', OUT/'materials.json', OUT/'candidate-references.json')
    return dict(
        schema=1, status='DIGITAL_DESIGN_VERIFIED' if complete else 'BLOCKED', digital_fixture_complete=complete,
        scope='Digital carrier design (reliefs, datums, keying, support, clamp points, registration and stroke allocation); not a complete fixture, fit result or fabrication approval',
        board_sha256=digest(BOARD), placement_sha256=digest(CANONICAL), geometry_sha256=p['geometry_sha256'],
        inputs_sha256={str(path.relative_to(ROOT)): digest(path) for path in files},
        study_step_sha256=digest(OUT/'carrier-study.step') if (OUT/'carrier-study.step').is_file() else None,
        fresh_native_verified=fresh, fresh_native_criteria=criteria, completion_criteria=completion,
        native_geometry=native, b_side_relief=relief,
        native_ci_evidence={'observed_date_utc':'2026-11-11','run_url':'https://github.com/Takazudo/zudo-led-block/actions/runs/42596523199','head_sha':'f0b1d8aa37f3967ccc8c9a6bd6ca0e7b7fc7b3a0','base_sha':'af523f9abb74e206c27aaaa076b3b68a5c474940','result':'PASS','board_sha256':BOARD_SHA,'scope':'Pinned native CI of the PR #44 preparation head on the unchanged board (CI log result); not verification of fixture geometry','raw_facts_consumed':False,'artifact_access':'2026-11-09: download Forbidden (historical). 2026-11-11: native-infrastructure-evidence artifact 13663737750 downloaded (ZIP SHA-256 33f3d9121164f364b0325540b161e9546ddf73c8b723c9166fdcd8a19867cf0e), but it retains only a7-gate/summary.json; candidate board_facts/board_geometry were not uploaded, so raw candidate facts remain unavailable'},
        transform={'description':'B side view: x_f = 16.2 - x_board; y_f = y_board. Carrier local Z is not an installed height.','matrix_xy':[[-1,0,16.2],[0,1,0],[0,0,1]]},
        pads=pads,
        calculations={'nominal_radial_budget_mm':(1.0-0.5)/2,'worst_case_registration_margin_mm':relief['registration']['worst_case_margin_mm'],'registration_equation':'0.25 - (board edge-to-pad + datum registration + carrier bore position + probe lateral play/concentricity); all terms radial worst-case mm, each allocation closed by an acceptance measurement (b_side_relief.registration)','minimum_probe_pitch_mm':round(spacing,6),'manufacturer_nominal_grid_mm':1.27,'nominal_collar_edge_gap_mm':round(spacing-1.04,6),'recommended_working_stroke_mm':4.3,'maximum_stroke_mm':6.35,'nominal_total_force_at_working_stroke_N':5*1.0,'nominal_total_preload_N':5*0.44,'total_force_at_maximum_stroke_N':hd['probe_force_total_N']['maximum_stroke'],'force_tolerance_N':None},
        carrier={'bounds_mm':[relief_design.CARRIER_BOARD_X[0],relief_design.CARRIER_Y[0],0,relief_design.CARRIER_BOARD_X[1],relief_design.CARRIER_Y[1],relief_design.CARRIER_THICKNESS],'receptacle_bore_diameter_mm':0.99,'bore_acceptance_requirement_mm':[0.98,1.0],'bore_material':'FR4, machined; not a printed plastic tolerance claim','minimum_wall_mm':relief_design.MIN_WALL,'datum_pin_holes':[{'id':q['id'],'carrier_xy_mm':q['carrier_xy_mm'],'diameter_mm':relief_design.RULES['datum_pin_diameter_mm']} for q in relief['datum_pins']],'mounting_holes_mm':[],'mounting_diameter_mm':3.2},
        candidate_reference_checks=candidate_checks,
        blockers=blockers)


def candidate_reference_checks(relief):
    """Compare the carrier with captured, NOT selected fabricator guidance; informational, never a gate or a selection."""
    out = []
    t = relief_design.CARRIER_THICKNESS
    cuts = [q['board_box_mm'] for q in relief['reliefs'] + relief['bridges']]
    narrowest = round(min(min(b[2] - b[0], b[3] - b[1]) for b in cuts), 6)
    for ref in json.loads((OUT/'candidate-references.json').read_text())['references']:
        rules = ref['rules_used']
        radius, tool = round(t / 10 + 0.5, 6), round(t / 5, 6)
        checks = {'minimum_wall_mm': {'design': relief_design.MIN_WALL, 'guidance_absolute_minimum': rules['wall_absolute_minimum_mm'],
                                      'met': relief_design.MIN_WALL >= rules['wall_absolute_minimum_mm']},
                  'through_cut_internal_corners': {'design': 'sharp rectangular corners', 'guidance_radius_mm': radius, 'guidance_tool_diameter_mm': tool,
                                                   'met': False},
                  'narrowest_cut_rectangle_mm': {'design': narrowest, 'guidance_tool_diameter_mm': tool, 'met': narrowest >= tool,
                                                 'note': 'rectangles merge into larger openings; several bridges between parts (0.15-0.25 mm) are genuine narrow slots'},
                  'registration_tolerances_mm': {'design': '0.05 carrier allocation, cut edges +/-0.05', 'guidance_standard': rules['standard_tolerance_mm'],
                                                 'met': None, 'note': 'tighter than standard; needs an annotated 2D drawing, availability not confirmed'}}
        out.append({'id': ref['id'], 'selection_status': ref['selection_status'], 'checks': checks,
                    'satisfied': all(c['met'] for c in checks.values() if c['met'] is not None)})
    return out


def validate_report(candidate, root=ROOT):
    """Reject fabricated flags/identity maps; only this producer's output is valid."""
    if Path(root).resolve() != ROOT.resolve():
        raise ValueError('fixture validation requires the actual checked-out producer root')
    if candidate != report():
        raise ValueError('fixture manifest differs from canonical producer output')
    return True


def drawing(r):
    # Dimensioned top view (B view) of the carrier only, with board outline for orientation.
    x0c,y0c,_,x1c,y1c,t=r['carrier']['bounds_mm'];k=12
    def xy(x,y): return 130+(x-x0c)*k, 110+(y-y0c)*k
    w,h=(x1c-x0c)*k,(y1c-y0c)*k
    s=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 860">','<rect width="720" height="860" fill="white"/>','<g font-family="sans-serif" fill="black">',
       f'<text x="25" y="30">A7 B-side carrier — digital design, {r["status"]} / NOT FOR FABRICATION</text>',
       f'<text x="25" y="55">All dimensions mm. FR4 {x1c-x0c:g} × {y1c-y0c:g} × {t:g}. Every cut is through; minimum wall {r["carrier"]["minimum_wall_mm"]}.</text>']
    x,y=xy(x0c,y0c)
    s.append(f'<rect x="{x}" y="{y}" width="{w:g}" height="{h:g}" fill="#e8efdf" stroke="black"/>')
    a,b=xy(0,0);c,d=xy(16.2,62.9)
    s.append(f'<rect x="{a:.2f}" y="{max(b,110):.2f}" width="{c-a:.2f}" height="{d-max(b,110):.2f}" fill="none" stroke="#777" stroke-dasharray="4 3"/>')
    for q in r['b_side_relief']['reliefs']+r['b_side_relief']['bridges']:
        x0,y0,x1,y1=q['carrier_box_mm'];a,b=xy(x0,y0);c,d=xy(x1,y1)
        s.append(f'<rect x="{a:.2f}" y="{b:.2f}" width="{c-a:.2f}" height="{d-b:.2f}" fill="{"#e8a19a" if q["ref"].startswith("bridge") else "#f4c7c3"}" stroke="black" stroke-width="0.5"/>')
    for q in r['carrier']['datum_pin_holes']:
        x,y=xy(*q['carrier_xy_mm']);s.append(f'<circle cx="{x}" cy="{y}" r="{q["diameter_mm"]/2*k:g}" fill="white" stroke="#1f5fa8" stroke-width="1.5"/><text x="{x+14}" y="{y+4}" font-size="11">{q["id"]}</text>')
    for px,py in r['b_side_relief']['holddown']['points_board_mm']:
        x,y=xy(16.2-px,py);s.append(f'<circle cx="{x}" cy="{y}" r="{0.75*k:g}" fill="none" stroke="#2a7a2a" stroke-dasharray="3 2"/>')
    for pad in r['pads']:
        px,py=pad['carrier_xy_mm'];x,y=xy(px,py)
        s.append(f'<circle cx="{x}" cy="{y}" r="5.94" fill="white" stroke="black"/>')
    for i,pad in enumerate(r['pads']):
        s.append(f'<text x="460" y="{145+i*28}">{pad["ref"]} {pad["net"]}: {pad["carrier_xy_mm"]}</text>')
    reg=r['b_side_relief']['registration']
    s.extend([f'<text x="25" y="{140+h:g}">X: {x0c:g} to {x1c:g}; Y: {y0c:g} to {y1c:g}; thickness {t:g}. Dashed grey: board outline.</text>',
              f'<text x="25" y="{165+h:g}">Red: through-cuts (dark: merge bridges). Blue: datum pins Ø2. Green: F-side clamp points.</text>',
              f'<text x="25" y="{190+h:g}">5 bores Ø0.99 (finished Ø0.98–1.00 in FR4). No mounting holes; base not designed.</text>',
              f'<text x="25" y="{215+h:g}">B view transform: X = 16.2 − board X; Y = board Y.</text>',
              f'<text x="25" y="{240+h:g}">Radial budget {reg["radial_budget_mm"]}; allocated worst-case margin {reg["worst_case_margin_mm"]} (acceptance measurements).</text></g></svg>'])
    return '\n'.join(s)+'\n'


def union_area(boxes):
    xs=sorted({v for b in boxes for v in (b[0],b[2])});ys=sorted({v for b in boxes for v in (b[1],b[3])});a=0.0
    for i in range(len(xs)-1):
        for j in range(len(ys)-1):
            cx,cy=(xs[i]+xs[i+1])/2,(ys[j]+ys[j+1])/2
            if any(b[0]<=cx<=b[2] and b[1]<=cy<=b[3] for b in boxes):a+=(xs[i+1]-xs[i])*(ys[j+1]-ys[j])
    return a


def cad(r, check=False):
    import cadquery as cq
    if cq.__version__ != '2.7.0':
        raise ValueError('CadQuery 2.7.0 required')
    path=OUT/'carrier-study.step'
    rel=r['b_side_relief'];x0c,y0c,_,x1c,y1c,t=r['carrier']['bounds_mm'];W,H=x1c-x0c,y1c-y0c
    cuts=[q['carrier_box_mm'] for q in rel['reliefs']+rel['bridges']]
    if any(q['depth_mm']!=t for q in rel['reliefs']+rel['bridges']) or any(w['web_mm']<=0 for w in rel['hole_to_cut_webs_below_2mm']):
        raise ValueError('cut layout not representable by the independent volume check')
    pins=r['carrier']['datum_pin_holes']
    expected=W*H*t - 5*math.pi*(0.99/2)**2*t - sum(math.pi*(q['diameter_mm']/2)**2*t for q in pins) - union_area(cuts)*t
    part=cq.Workplane('XY').box(W,H,t,centered=(False,False,False)).translate((x0c,y0c,0))
    for x0,y0,x1,y1 in cuts:
        part=part.cut(cq.Workplane('XY').box(x1-x0,y1-y0,t,centered=(False,False,False)).translate((x0,y0,0)))
    for x,y in [p['carrier_xy_mm'] for p in r['pads']]:
        part=part.cut(cq.Workplane('XY').center(x,y).circle(0.99/2).extrude(t))
    for q in pins:
        part=part.cut(cq.Workplane('XY').center(*q['carrier_xy_mm']).circle(q['diameter_mm']/2).extrude(t))
    if not check:
        cq.exporters.export(part,str(path))
    shape=cq.importers.importStep(str(path)).val()
    box=shape.BoundingBox()
    if not shape.isValid() or len(shape.Solids())!=1 or abs(shape.Volume()-expected)>1e-5 or any(abs(a-b)>1e-6 for a,b in zip([box.xlen,box.ylen,box.zlen],[W,H,t])):
        raise ValueError('Carrier STEP geometry mismatch')
    if shape.cut(part.val()).Volume() + part.val().cut(shape).Volume() > 1e-5:
        raise ValueError('Carrier STEP differs from actual probe-hole, datum-pin and cut positions')
    print(f'CadQuery 2.7.0 STEP valid: one solid, volume {shape.Volume():.6f} mm3, bounds {W:g}x{H:g}x{t:g}mm, {len(rel["reliefs"])} part through-cuts, {len(rel["bridges"])} merge bridges, {len(pins)} datum pin holes; carrier only')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');ap.add_argument('--cad',action='store_true');ap.add_argument('--cad-check',action='store_true');args=ap.parse_args()
    if args.cad and not args.check: cad(report())  # write the STEP first so the manifest binds its bytes
    r=report()
    outputs={'manifest.json':json.dumps(r,indent=2)+'\n','carrier-study.svg':drawing(r)}
    for n,text in outputs.items():
        p=OUT/n
        if args.check:
            if not p.exists() or p.read_text()!=text: raise ValueError(f'stale fixture study: {p}')
        else:p.write_text(text)
    if args.cad_check: cad(r,True)
    print('Fixture study validation PASS; complete fixture remains BLOCKED')

if __name__=='__main__':main()
