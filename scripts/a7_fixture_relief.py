"""B-side relief and support layout of the A7 SWD carrier study, derived from native geometry.

Inputs: the validated native fixture geometry record (KiCad pad copper and courtyard boxes of the
authoritative PCB), the canonical placement, the engineering population list, and component
heights taken only from sources already recorded in the component evidence. Heights are
SOURCE_DERIVED (never measured); a part without a traceable value stays null and is listed.
Clearances and the minimum web are PROJECT-CHOICE study values, not tolerances or fit results.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POPULATION = ROOT / 'engineering/a7/procurement/population.csv'

CARRIER_BOARD_X = (-4.4, 20.6)  # carrier footprint in board X (the carrier is symmetric about the 16.2 mm board)
CARRIER_Y = (20.0, 60.0)
CARRIER_THICKNESS = 5.0
BORE_RADIUS = 0.99 / 2
RULES = {
    'smd_outline_clearance_mm': 0.2,
    'tht_copper_clearance_mm': 0.3,
    'pocket_depth_clearance_mm': 0.25,
    'minimum_web_bore_to_relief_mm': 0.5,
    'support_grid_mm': 0.1,
    'support_radius_around_probe_mm': 3.0,
    'confidence': 'PROJECT-CHOICE study values; not machining tolerances, fit results or approvals',
}

R0603_HEIGHT = {
    'nominal_mm': 0.45, 'tolerance_mm': 0.10, 'max_mm': 0.55, 'class': 'SOURCE_DERIVED',
    'body_length_max_mm': 1.75, 'body_width_max_mm': 0.9,
    'source': {'document': 'UNI-ROYAL Thick Film Chip Resistors (Chip Series) datasheet SMD-SP-001 V.11, 2026-03-17',
               'sha256': 'd27e4cdcdf8fdb4c066ff6030cfc1f46b99efe2a38fe5673fa18a2ee4c7220d3',
               'evidence_source_ids': 'src-0603waf*-ds-p1 (component-0603waf* bundles, MANUFACTURER_PRIMARY)',
               'locator': 'physical page index 3 (printed Page 4/12), section 5 Dimension, row 0603: L 1.60±0.15, W 0.80±0.10, H 0.45±0.10 mm'},
    'applies_to': 'body height of every 0603WAF*T5E resistor (Chip Series); solder fillet height is not given by the source',
}
SOURCES = {
    'R0603': R0603_HEIGHT,
    'PJ-324M': {
        'terminal_projection_below_seating_plane_mm': 3.2, 'tolerance_mm': 0.2, 'class': 'SOURCE_DERIVED (MANUFACTURER_MIRROR)',
        'source': {'fact_id': 'fact-a7-pj-324m-terminal-projection', 'source_id': 'src-a7-pj-324m-sofng-drawing',
                   'sha256': 'c5f2f104e73244a32ed024f7a6577d260678a9b3f3cc3d496531fb930b3c7049',
                   'locator': 'page 0 front view vertical 3.2; tolerance as engineering/a7/study/parameters.json jack_terminal_projection'},
        'protrusion_below_b_face': 'projection minus board thickness: nominal 3.2 - 1.6 = 1.6 mm; the maximum also needs the board '
                                   'thickness tolerance, which is not sourced, and the fillet height, which is not sourced',
    },
    'PCM13SMTR': {
        'peg_length_mm': 0.5, 'class': 'SOURCE_DERIVED (MANUFACTURER_PRIMARY)',
        'source': {'fact_id': 'fact-a7-pcm13smtr-outline', 'source_id': 'src-a7-pcm13smtr-ck-site',
                   'sha256': '6a758d151b7eee7f8cd59594bd92cfec4c9b1470e0743094f185f19e7ac2a868', 'locator': 'page index 2 outline and PC MOUNTING'},
        'protrusion_below_b_face': 'none: 0.5 mm pegs are shorter than the 1.6 mm board',
    },
    'PicoBlade 530470310': {
        'tail_length_below_b_face_mm': None, 'class': 'UNKNOWN',
        'reason': 'no traceable tail length in the recorded evidence: the sales-drawing extract gives only A/B/C/D row dimensions; the 2.3 mm in '
                  'the mechanical layout is unsourced; the KiCad library 3D model is not supplier CAD',
    },
}


def _expand(box, m):
    return [box[0] - m, box[1] - m, box[2] + m, box[3] + m]


def _clip(box):
    x0, y0, x1, y1 = max(box[0], CARRIER_BOARD_X[0]), max(box[1], CARRIER_Y[0]), min(box[2], CARRIER_BOARD_X[1]), min(box[3], CARRIER_Y[1])
    return [round(v, 6) for v in (x0, y0, x1, y1)] if x0 < x1 and y0 < y1 else None


def _to_carrier(box):
    return [round(16.2 - box[2], 6), box[1], round(16.2 - box[0], 6), box[3]]


def _box_point_dist(box, pt):
    dx = max(box[0] - pt[0], 0.0, pt[0] - box[2])
    dy = max(box[1] - pt[1], 0.0, pt[1] - box[3])
    return math.hypot(dx, dy)


def population(path=POPULATION):
    rows = [line for line in path.read_text().splitlines() if not line.startswith('ENGINEERING ONLY')]
    return {r['ref']: r for r in csv.DictReader(rows) if r['board'] == 'controller'}


def design(geometry: dict, probes: list[dict], pop: dict | None = None) -> dict:
    """Relief, web and support layout from validated native geometry; raises on unclassified B-side items."""
    pop = population() if pop is None else pop
    probe_refs = {p['ref'] for p in probes}
    reliefs, unknown_heights = [], []
    for f in sorted(geometry['footprints'], key=lambda f: f['ref']):
        ref = f['ref']
        if ref in probe_refs:
            continue
        if f['side'] == 'B':
            row = pop.get(ref)
            if f['fpid'] != 'LightBlock:R0603' or row is None or row['population'] != 'FITTED' or not row['mpn'].startswith('0603WAF'):
                raise ValueError(f'{ref}: B-side part without a classified height source')
            rot = round(f['rotation_deg']) % 180
            if abs(f['rotation_deg'] - round(f['rotation_deg'])) > 1e-6 or rot % 90:
                raise ValueError(f'{ref}: non-orthogonal rotation; body outline box not derived')
            hl, hw = R0603_HEIGHT['body_length_max_mm'] / 2, R0603_HEIGHT['body_width_max_mm'] / 2
            dx, dy = (hl, hw) if rot == 0 else (hw, hl)
            cx, cy = f['at_mm']
            outline = [cx - dx, cy - dy, cx + dx, cy + dy]
            for q in f['pads']:
                b = q['bbox_mm']
                outline = [min(outline[0], b[0]), min(outline[1], b[1]), max(outline[2], b[2]), max(outline[3], b[3])]
            box = _clip(_expand(outline, RULES['smd_outline_clearance_mm']))
            if box:
                reliefs.append({'ref': ref, 'kind': 'pocket', 'basis': 'native pad copper boxes united with the sourced maximum body outline (solder wets only copper)', 'board_box_mm': box,
                                'carrier_box_mm': _to_carrier(box), 'body_height_max_mm': R0603_HEIGHT['max_mm'],
                                'height_class': 'SOURCE_DERIVED', 'height_source': 'R0603',
                                'depth_mm': round(R0603_HEIGHT['max_mm'] + RULES['pocket_depth_clearance_mm'], 6),
                                'solder_envelope_height_mm': None})
            continue
        tht = [p for p in f['pads'] if p['attribute'] == 'PTH']
        npth = [p for p in f['pads'] if p['attribute'] == 'NPTH']
        if any('B.Cu' in p['layers'] for p in f['pads'] if p['attribute'] not in ('PTH', 'NPTH')):
            raise ValueError(f'{ref}: F-side pad with B.Cu copper is not classified for relief')
        if npth and f['fpid'] != 'LightBlockA7:PCM13SMTR':
            raise ValueError(f'{ref}: NPTH feature without a classified protrusion source')
        if not tht:
            continue
        key = {'LightBlockA7:PJ324M': 'PJ-324M', 'LightBlock:PICO3': 'PicoBlade 530470310'}.get(f['fpid'])
        if key is None:
            raise ValueError(f'{ref}: through-hole leads without a classified protrusion source')
        for p in tht:
            box = _clip(_expand(p['bbox_mm'], RULES['tht_copper_clearance_mm']))
            if box:
                reliefs.append({'ref': f'{ref}.{p["number"]}', 'kind': 'through', 'basis': 'native pad copper box (solder wets only copper)',
                                'board_box_mm': box, 'carrier_box_mm': _to_carrier(box), 'height_source': key,
                                'height_class': SOURCES[key]['class'], 'depth_mm': CARRIER_THICKNESS})
        if SOURCES[key]['class'] == 'UNKNOWN':
            unknown_heights.append(f'{ref} ({key}): lead tail below the B face')

    webs, conflicts = [], []
    for p in probes:
        for rl in reliefs:
            web = round(_box_point_dist(rl['board_box_mm'], p['board_xy_mm']) - BORE_RADIUS, 6)
            if web < 2.0:
                webs.append({'probe': p['ref'], 'relief': rl['ref'], 'web_mm': web})
            if web < RULES['minimum_web_bore_to_relief_mm']:
                conflicts.append(f"{p['ref']} bore to {rl['ref']} relief web {web:.3f} mm < {RULES['minimum_web_bore_to_relief_mm']} mm")

    minimum = RULES['minimum_web_bore_to_relief_mm']
    walls = []
    for i, a in enumerate(reliefs):
        for b in reliefs[i + 1:]:
            A, B = a['board_box_mm'], b['board_box_mm']
            gap = math.hypot(max(B[0] - A[2], A[0] - B[2], 0.0), max(B[1] - A[3], A[1] - B[3], 0.0))
            if 0 < gap < minimum:
                walls.append(f"{a['ref']}/{b['ref']} wall {gap:.3f} mm")
        A = a['board_box_mm']
        for edge in (A[1] - CARRIER_Y[0], CARRIER_Y[1] - A[3], A[0] - CARRIER_BOARD_X[0], CARRIER_BOARD_X[1] - A[2]):
            if 0 < edge < minimum:
                walls.append(f"{a['ref']}/carrier edge wall {edge:.3f} mm")
    overhang = sorted(f['ref'] for f in geometry['footprints'] if f['side'] == 'F' and f['courtyard_bbox_mm'].get('F')
                      and (f['courtyard_bbox_mm']['F'][0] < 0 or f['courtyard_bbox_mm']['F'][2] > 16.2)
                      and f['courtyard_bbox_mm']['F'][1] < CARRIER_Y[1] and f['courtyard_bbox_mm']['F'][3] > CARRIER_Y[0])

    g = RULES['support_grid_mm']
    nx, ny = round(16.2 / g), round((CARRIER_Y[1] - CARRIER_Y[0]) / g)
    land = total = 0
    near = {p['ref']: [0, 0] for p in probes}
    for i in range(nx):
        x = (i + 0.5) * g
        for j in range(ny):
            y = CARRIER_Y[0] + (j + 0.5) * g
            free = not any(b['board_box_mm'][0] <= x <= b['board_box_mm'][2] and b['board_box_mm'][1] <= y <= b['board_box_mm'][3] for b in reliefs) \
                and all(math.dist((x, y), p['board_xy_mm']) > BORE_RADIUS for p in probes)
            total += 1
            land += free
            for p in probes:
                if math.dist((x, y), p['board_xy_mm']) <= RULES['support_radius_around_probe_mm']:
                    near[p['ref']][1] += 1
                    near[p['ref']][0] += free
    support = {'method': f'grid {g} mm over the board outline inside the carrier (board X 0-16.2, Y {CARRIER_Y[0]}-{CARRIER_Y[1]})',
               'land_fraction': round(land / total, 4),
               'land_fraction_within_radius_of_probe': {k: round(a / b, 4) for k, (a, b) in near.items()},
               'scope': 'geometric contact area of the carrier top on the B face only; no load path, deflection or hold-down analysis'}
    return {'rules': RULES, 'height_sources': SOURCES, 'reliefs': reliefs, 'bore_to_relief_webs_below_2mm': sorted(webs, key=lambda w: (w['web_mm'], w['probe'], w['relief'])),
            'web_conflicts': conflicts, 'relief_wall_conflicts': walls, 'unknown_heights': unknown_heights,
            'overhang_not_checked': {'refs': overhang, 'note': 'F-side courtyards extending past the board edge over the carrier overhang '
                                     '(board X -4.4..0 / 16.2..20.6); their bodies sit on the F side above the B plane, so the carrier top '
                                     'is assumed clear; no body-below-B-plane check is made'},
            'solder_envelope': 'fillet heights are not given by any recorded source for any B-side item; SMD pockets cover the sourced body height only',
            'support': support}
