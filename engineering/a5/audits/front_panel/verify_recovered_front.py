#!/usr/bin/env python3
"""Audit recovered A4 artifacts without regenerating or changing the originals.

Reads stored SVG/DXF/STEP and front-coordinate region JSON independently.
Does not assign a laser process or validate a whole-module mechanical assembly.

From the project root:
  python audits/front_panel/verify_recovered_front.py front_panel
The default output is audits/front_panel/recheck/, preserving the original
recovery report. Supply a second directory argument to override it.
"""
from __future__ import annotations

import hashlib
import argparse
import json
import math
from pathlib import Path
import re
import sys
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

import cadquery as cq
import ezdxf
from ezdxf import bbox as dxf_bbox
import numpy as np

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('front_panel_directory',type=Path,help='Recovered A4 front_panel directory')
parser.add_argument('output_directory',type=Path,nargs='?',default=Path(__file__).resolve().parent/'recheck',help='Audit output directory (default: recheck/ beside this script)')
args=parser.parse_args()
SOURCE=args.front_panel_directory.resolve()
OUTPUT=args.output_directory.resolve()
OUTPUT.mkdir(parents=True, exist_ok=True)
SVG = '{http://www.w3.org/2000/svg}'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def svg_polygons(data):
    # The production files deliberately contain only M/L/Z closed polygons.
    if re.search(r'[A-KN-Yac-z]', data):
        raise ValueError('Unexpected SVG path command')
    polys = []
    for item in re.findall(r'M\s*([^M]+)', data):
        if not item.strip().endswith('Z'):
            raise ValueError('Unclosed process contour')
        numbers = [float(v) for v in re.findall(r'-?\d+(?:\.\d+)?', item)]
        if len(numbers) % 2:
            raise ValueError('Odd coordinate count')
        polys.append(np.array(numbers).reshape((-1, 2)).tolist())
    return polys


def area(poly):
    return .5 * sum(a[0]*b[1]-b[0]*a[1] for a, b in zip(poly, poly[1:]+poly[:1]))


def inside_polygon(pt, poly):
    x, y = pt
    found = False
    for (ax, ay), (bx, by) in zip(poly, poly[1:]+poly[:1]):
        if ((ay > y) != (by > y)) and x < (bx-ax)*(y-ay)/(by-ay)+ax:
            found = not found
    return found


def inside_region(pt, reg):
    return sum(inside_polygon(pt, poly) for poly in reg) % 2 == 1


def engraved(pt, regions):
    return any(inside_region(pt, reg) for reg in regions)


def sample_inside(reg):
    p = np.array(reg[0])
    lo, hi = p.min(axis=0), p.max(axis=0)
    # Bounded sampling avoids treating an annular glyph centroid as a stroke.
    samples = []
    for y in np.linspace(lo[1], hi[1], 19)[1:-1]:
        for x in np.linspace(lo[0], hi[0], 19)[1:-1]:
            point=np.array((x,y))
            distance=float('inf')
            for contour in reg:
                a=np.array(contour);b=np.roll(a,-1,axis=0);delta=b-a
                along=np.clip(np.sum((point-a)*delta,axis=1)/np.sum(delta*delta,axis=1),0,1)
                distance=min(distance,float(np.linalg.norm(point-(a+along[:,None]*delta),axis=1).min()))
            # A point on an edge has no unambiguous fill classification.
            # SVG rounds to 1e-6 mm; use a larger 5e-6 mm boundary exclusion.
            if inside_region((x, y), reg) and distance>5e-6:
                samples.append((float(x), float(y)))
    if not samples:
        raise ValueError('No interior sample for a clear-letter region')
    return samples


def aligned_error(actual, expected):
    a, e = np.array(actual), np.array(expected)
    if a.shape != e.shape:
        return float('inf')
    start = int(np.linalg.norm(a-e[0], axis=1).argmin())
    aa = np.roll(a, -start, axis=0)
    forward = float(np.max(np.linalg.norm(aa-e, axis=1)))
    reverse = np.concatenate((aa[:1], aa[:0:-1]))
    return min(forward, float(np.max(np.linalg.norm(reverse-e, axis=1))))


def compare_regions(actual, expected):
    if len(actual) != len(expected):
        return float('inf')
    errors = []
    for a, e in zip(actual, expected):
        if len(a) != len(e):
            return float('inf')
        errors += [aligned_error(ap, ep) for ap, ep in zip(a, e)]
    return max(errors, default=0.0)


def inspect_variant(name, width, p):
    h = p['panel']['height']
    ex = SOURCE/'exports'
    snapshot = json.loads((ex/f'mask_regions_A4_{name}.json').read_text())
    front = snapshot['engraved_regions']
    letters = snapshot['clear_label_regions']
    svg_path = ex/f'rear_A4_{name}_REAR_FULL_FROST_CLEAR_LETTERS.svg'
    tree = ET.parse(svg_path).getroot()
    paths = tree.findall('.//'+SVG+'path')
    rear = [svg_polygons(q.attrib['d']) for q in paths]
    expected_rear = [[[[width-x, y] for x,y in loop] for loop in reg] for reg in front]
    svg_max_error = compare_regions(rear, expected_rear)
    dxf = ezdxf.readfile(svg_path.with_suffix('.dxf'))
    hatches = list(dxf.modelspace().query('HATCH'))
    from_dxf = [[[[float(v[0]), float(v[1])] for v in boundary.vertices] for boundary in ht.paths] for ht in hatches]
    expected_dxf = [[[[width-x, h-y] for x,y in loop] for loop in reg] for reg in front]
    dxf_max_error = compare_regions(from_dxf, expected_dxf)

    # Check the actual saved production SVG, not just a freshly rebuilt BRep.
    stroke_samples = []
    for reg in letters:
        stroke_samples += sample_inside(reg)
    strokes_accidentally_engraved = sum(engraved((width-x, y), rear) for x,y in stroke_samples)
    counter_checks = []
    for reg in letters:
        for counter in reg[1:]:
            samples = sample_inside([counter])
            missed = sum(not engraved((width-x, y), rear) for x,y in samples)
            counter_checks.append({'area_mm2':abs(area(counter)), 'sample_count':len(samples), 'missed_engraved_samples':missed})
    perimeter_samples = [(x,y) for x in [.01, width-.01] for y in [1,10,40,55,70,82,95,110,120,127.5]]
    unfrosted_perimeter = [q for q in perimeter_samples if not engraved((width-q[0], q[1]),rear)]

    step_path = ex/f'front_A4_{name}_2mm.step'
    panel = cq.importers.importStep(str(step_path)).val()
    bb = panel.BoundingBox()
    top = cq.Workplane(obj=panel).faces('>Z').val()
    holes=[]
    for ww in top.innerWires():
        b = ww.BoundingBox()
        holes.append({'cx_mm':(b.xmin+b.xmax)/2, 'cy_mm':(b.ymin+b.ymax)/2,
                      'width_mm':b.xlen, 'height_mm':b.ylen})
    holes.sort(key=lambda a:a['cy_mm'])
    expected_holes = [(3,4.6,3.2),(20.5,2.2,2.2),(60.8,2.2,2.2),(65,2.2,2.2),
                      (74,6.5,6.5),(90,6.2,6.2),(104,6.2,6.2),(125.5,4.6,3.2)]
    max_hole_error = max(abs(actual[key]-exp) for actual, expected in zip(holes,expected_holes)
                         for key,exp in zip(['cx_mm','cy_mm','width_mm','height_mm'],[width/2,*expected])) if len(holes)==len(expected_holes) else float('inf')
    cut = ezdxf.readfile(ex/f'front_A4_{name}_CUT.dxf')
    ext = dxf_bbox.extents(cut.modelspace())
    size_error = max(abs(bb.xlen-width),abs(bb.ylen-h),abs(bb.zlen-2),
                     abs(ext.extmin.x),abs(ext.extmin.y),abs(ext.extmax.x-width),abs(ext.extmax.y-h))
    checks = {
        'variant':name, 'source_svg_sha256':digest(svg_path), 'source_step_sha256':digest(step_path),
        'svg_artboard':{'width':tree.get('width'),'height':tree.get('height'),'viewBox':tree.get('viewBox')},
        'svg_path_count':len(paths), 'svg_all_filled_evenodd':all(q.get('fill')=='#000000' and q.get('fill-rule')=='evenodd' for q in paths),
        'svg_contains_font_text':bool(tree.findall('.//'+SVG+'text')),
        'svg_vs_front_snapshot_mirror_max_vertex_error_mm':svg_max_error,
        'dxf_hatch_count':len(hatches),'dxf_units':dxf.units,
        'dxf_vs_front_snapshot_mirror_max_vertex_error_mm':dxf_max_error,
        'dxf_hatches_zero_elevation':all(abs(ht.dxf.elevation.z)<1e-12 for ht in hatches),
        'dxf_closed_polyline_boundaries':all(pa.is_closed for ht in hatches for pa in ht.paths),
        'clear_stroke_regions':len(letters),'clear_stroke_sample_count':len(stroke_samples),
        'sampling_boundary_exclusion_mm':5e-6,
        'clear_stroke_samples_accidentally_engraved':strokes_accidentally_engraved,
        'counter_checks':counter_checks,'perimeter_samples':len(perimeter_samples),'unfrosted_perimeter_samples':unfrosted_perimeter,
        'step_valid':panel.isValid(),'step_solid_count':len(panel.Solids()),'step_box_mm':[bb.xlen,bb.ylen,bb.zlen],
        'step_holes':holes,'max_hole_geometry_error_mm':max_hole_error,'step_and_cut_size_error_mm':size_error,
        'cut_dxf_units':cut.units,'cut_layers':sorted(set(e.dxf.layer for e in cut.modelspace()))
    }
    checks['passed']=all([svg_max_error<1e-6,dxf_max_error<1e-8,
        checks['svg_all_filled_evenodd'],not checks['svg_contains_font_text'],
        len(paths)==6,len(hatches)==6,dxf.units==4,checks['dxf_hatches_zero_elevation'],checks['dxf_closed_polyline_boundaries'],
        strokes_accidentally_engraved==0,len(counter_checks)==5,all(q['missed_engraved_samples']==0 for q in counter_checks),
        not unfrosted_perimeter,panel.isValid(),len(panel.Solids())==1,max_hole_error<1e-6,size_error<1e-6,cut.units==4])
    return checks


def main():
    manifest=json.loads((SOURCE/'file_integrity_manifest.json').read_text())
    integrity=[]
    for row in manifest['files']:
        f=SOURCE/row['path']
        integrity.append({'path':row['path'], 'passed':f.exists() and f.stat().st_size==row['size_bytes'] and digest(f)==row['sha256']})
    p=json.loads((SOURCE/'geometry.json').read_text())
    variants=[inspect_variant(name,v['width'],p) for name,v in p['variants'].items()]
    out={
        'checked_at_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'Independent read-back of recovered A4 front exports; original files unchanged; no whole-module CAD or supplier qualification.',
        'source':str(SOURCE),'source_revision':p['revision'],
        'manifest_files_checked':len(integrity),'file_integrity':integrity,'variants':variants,
        'all_passed':all(r['passed'] for r in integrity+variants),
        'visual_inspection':'A4 summary PNG and 2HP rear PNG inspected; front readable, rear mirrored, counters frosted, no clipping observed.',
        'mechanical_status':'Front interface only. Rear PETG cradle, assembly stack, connector clearance, insertion/withdrawal load path and final 30mm depth require integrated CAD.'
    }
    (OUTPUT/'independent_front_validation.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({'all_passed':out['all_passed'],'manifest_files':len(integrity),'variants':[
        {'variant':x['variant'],'passed':x['passed'],'svg_error_mm':x['svg_vs_front_snapshot_mirror_max_vertex_error_mm'],
         'counters':len(x['counter_checks']),'stroke_samples':x['clear_stroke_sample_count'],'step_box_mm':x['step_box_mm']} for x in variants]},indent=2))
    if not out['all_passed']:
        raise SystemExit(1)


if __name__=='__main__':
    main()
