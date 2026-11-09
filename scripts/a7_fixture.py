#!/usr/bin/env python3
"""Revision-bound, BLOCKED A7 fixture carrier study; never an assembly approval.

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


def report():
    p = bound_r4_placement()
    if digest(BOARD) != BOARD_SHA or digest(CANONICAL) != PLACEMENT_SHA:
        raise ValueError('Fixture revision invalidated; re-review geometry and update explicit identity locks')
    pads = probe_map(p, BOARD.read_text())
    spacing = min(math.dist(a['carrier_xy_mm'], b['carrier_xy_mm']) for i,a in enumerate(pads) for b in pads[i+1:])
    return dict(schema=1,status='BLOCKED',digital_fixture_complete=False,scope='Carrier-only dimensional study, not complete fixture or fabrication approval',board_sha256=digest(BOARD),placement_sha256=digest(CANONICAL),geometry_sha256=p['geometry_sha256'],inputs_sha256={str(path.relative_to(ROOT)):digest(path) for path in (BOARD,CANONICAL,Path(__file__).resolve(),OUT/'sources.json',OUT/'materials.json')},fresh_native_verified=False,native_ci_evidence={'observed_date_utc':'2026-11-09','run_url':'https://github.com/Takazudo/zudo-led-block/actions/runs/42594178172','head_sha':'4894a6f6f21b30419d039bd6427e89553f8dee55','result':'PASS','board_sha256':BOARD_SHA,'scope':'E1 pinned native CI on the stated head and unchanged board; not verification of the uncommitted integration or fixture geometry','raw_facts_consumed':False,'artifact_access':'Forbidden, including escalated download; raw facts unavailable'},transform={'description':'B side view: x_f = 16.2 - x_board; y_f = y_board. Carrier local Z is not an installed height.','matrix_xy':[[-1,0,16.2],[0,1,0],[0,0,1]]},pads=pads,calculations={'nominal_radial_budget_mm':(1.0-0.5)/2,'worst_case_registration_margin_mm':None,'registration_equation':'0.25 - (board edge-to-pad + datum registration + carrier bore position + probe lateral play/concentricity); all terms radial worst-case mm','minimum_probe_pitch_mm':round(spacing,6),'manufacturer_nominal_grid_mm':1.27,'nominal_collar_edge_gap_mm':round(spacing-1.04,6),'recommended_working_stroke_mm':4.3,'maximum_stroke_mm':6.35,'nominal_total_force_at_working_stroke_N':5*1.0,'nominal_total_preload_N':5*0.44,'force_tolerance_N':None},carrier={'bounds_mm':[-4.4,20,0,20.6,60,5],'receptacle_bore_diameter_mm':0.99,'bore_acceptance_requirement_mm':[0.98,1.0],'bore_material':'FR4, machined; not a printed plastic tolerance claim','mounting_holes_mm':[],'mounting_diameter_mm':3.2},blockers=['No complete keyed outline registration, board support, load path or travel stop designed/verified.','No source-backed board edge-to-pad tolerance or probe lateral play/concentricity tolerance; worst-case margin NOT_ESTABLISHED.','Actual fresh-native F/B component extents and solder envelopes have not been obtained for clearance/support design.','Receptacle drawing diameter 0.96mm versus PDF table 0.95mm; use 0.96mm envelope only as conservative study input, resolve before selection.','No physical fit, contact, insertion-force or measured stroke evidence; no prototype exists.','E1 pinned native CI passed at 4894a6f6f21b30419d039bd6427e89553f8dee55 for this unchanged board; artifact download was Forbidden. Fixture has not consumed fresh native facts and the uncommitted integration is not covered by that run.'])


def validate_report(candidate, root=ROOT):
    """Reject fabricated flags/identity maps; only this producer's output is valid."""
    if Path(root).resolve() != ROOT.resolve():
        raise ValueError('fixture validation requires the actual checked-out producer root')
    if candidate != report():
        raise ValueError('fixture manifest differs from canonical producer output')
    return True


def drawing(r):
    # Dimensioned top view of the carrier only, with board outline for orientation.
    s=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 760">','<rect width="720" height="760" fill="white"/>','<g font-family="sans-serif" fill="black"><text x="25" y="30">A7 B-side carrier study — BLOCKED / NOT FOR FABRICATION</text>','<text x="25" y="55">All dimensions mm. FR4 25 × 40 × 5. No board support or travel stop.</text>']
    def xy(x,y): return 130+(x+4.4)*12, 110+(y-20)*12
    x,y=xy(-4.4,20)
    s.append(f'<rect x="{x}" y="{y}" width="300" height="480" fill="#e8efdf" stroke="black"/>')
    for px,py in r['carrier']['mounting_holes_mm']:
        x,y=xy(px,py);s.append(f'<circle cx="{x}" cy="{y}" r="19.2" fill="white" stroke="black"/>')
    for pad in r['pads']:
        px,py=pad['carrier_xy_mm'];x,y=xy(px,py)
        s.append(f'<circle cx="{x}" cy="{y}" r="5.94" fill="white" stroke="black"/>')
    for i,pad in enumerate(r['pads']):
        s.append(f'<text x="460" y="{145+i*28}">{pad["ref"]} {pad["net"]}: {pad["carrier_xy_mm"]}</text>')
    s.extend(['<text x="130" y="625">X: −4.4 to 20.6; Y: 20 to 60; thickness 5</text>','<text x="25" y="655">5 receptacle bores Ø0.99 (required finished Ø0.98–1.00 in FR4).</text>','<text x="25" y="680">Mounting interface intentionally unresolved; no mounting holes.</text>','<text x="25" y="705">B view transform: X = 16.2 − board X; Y = board Y.</text>','<text x="25" y="730">Nominal contact radial budget 0.25; worst-case margin unknown.</text></g></svg>'])
    return '\n'.join(s)+'\n'


def cad(r, check=False):
    import cadquery as cq
    if cq.__version__ != '2.7.0':
        raise ValueError('CadQuery 2.7.0 required')
    path=OUT/'carrier-study.step'
    expected=25*40*5 - 5*math.pi*(0.99/2)**2*5 - len(r['carrier']['mounting_holes_mm'])*math.pi*(3.2/2)**2*5
    part=cq.Workplane('XY').box(25,40,5,centered=(False,False,False)).translate((-4.4,20,0))
    for x,y in [p['carrier_xy_mm'] for p in r['pads']]:
        part=part.cut(cq.Workplane('XY').center(x,y).circle(0.99/2).extrude(5))
    for x,y in r['carrier']['mounting_holes_mm']:
        part=part.cut(cq.Workplane('XY').center(x,y).circle(3.2/2).extrude(5))
    if not check:
        cq.exporters.export(part,str(path))
    shape=cq.importers.importStep(str(path)).val()
    box=shape.BoundingBox()
    if not shape.isValid() or len(shape.Solids())!=1 or abs(shape.Volume()-expected)>1e-5 or any(abs(a-b)>1e-6 for a,b in zip([box.xlen,box.ylen,box.zlen],[25,40,5])):
        raise ValueError('Carrier STEP geometry mismatch')
    if shape.cut(part.val()).Volume() + part.val().cut(shape).Volume() > 1e-5:
        raise ValueError('Carrier STEP differs from actual probe-hole positions')
    print(f'CadQuery 2.7.0 STEP valid: one solid, volume {shape.Volume():.6f} mm3, bounds 25x40x5mm; carrier study only')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');ap.add_argument('--cad',action='store_true');ap.add_argument('--cad-check',action='store_true');args=ap.parse_args()
    r=report()
    outputs={'manifest.json':json.dumps(r,indent=2)+'\n','carrier-study.svg':drawing(r)}
    for n,text in outputs.items():
        p=OUT/n
        if args.check:
            if not p.exists() or p.read_text()!=text: raise ValueError(f'stale fixture study: {p}')
        else:p.write_text(text)
    if args.cad or args.cad_check: cad(r,args.cad_check)
    print('Fixture study validation PASS; complete fixture remains BLOCKED')

if __name__=='__main__':main()
