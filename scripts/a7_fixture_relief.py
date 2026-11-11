"""Digital design of the A7 SWD fixture, derived from native geometry and recorded sources.

Architecture (coordinator decision W8): the probe plate and the board support are separate parts.
- The probe plate holds the INGUN receptacles at their datasheet bore in solid FR-4; it has no component pockets.
- The support carrier above it carries the board B face on lands and datum pins. Over the probe field and every
  B-face feature it has open windows (merged rounded rectangles), not individual pockets, so milled walls meet the
  captured JLCCNC guidance (1.0 mm absolute minimum wall; internal radius H/10 + 0.5 mm) used as the
  manufacturability yardstick. No fabricator is selected.
- A screw-down FR-4 pressure plate presses three nylon screw tips onto free F-face area; two of them sit over the
  probe field and oppose the probe forces directly. Two compression springs on guide standoffs, compressed to a length
  fixed by the standoff tops, set the clamp force.

Inputs: the validated native fixture geometry record (KiCad pad copper and courtyard boxes of the authoritative PCB),
the population list, the INGUN documents in engineering/a7/fixture/sources.json, the candidate fabricator guidance in
engineering/a7/fixture/candidate-references.json, the A5 seed component envelopes for F-side heights and the A7
component evidence. Values marked PROJECT-CHOICE are design values, not measured results. Nothing here is a fit,
contact or manufacturing approval.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POPULATION = ROOT / 'engineering/a7/procurement/population.csv'
CANDIDATES = ROOT / 'engineering/a7/fixture/candidate-references.json'
A5_ENVELOPES = ROOT / 'engineering/a5/electronics/placement_and_connectivity.json'

BOARD = (0.0, 0.0, 16.2, 62.9)
BOARD_THICKNESS = 1.6
CARRIER_BOARD_X = (-10.2, 26.4)  # plate footprint in board X (B view: carrier x = 16.2 - board x)
CARRIER_Y = (13.0, 67.0)
CARRIER_THICKNESS = 5.0
BORE_NOMINAL = 0.99
BORE_MAX = 1.00

# Z levels, board B face = 0, up towards the F face.
STACK = {
    'support_carrier': (-5.0, 0.0),
    'plate_gap_spacers': (-11.0, -5.0),     # M3 F-F hex spacers, 6 mm
    'probe_plate': (-17.0, -11.0),
    'base_standoffs': (-52.0, -17.0),       # M3 M-F standoffs, 35 mm
    'base_plate': (-55.0, -52.0),
    'pressure_plate': (BOARD_THICKNESS + 2.5, BOARD_THICKNESS + 2.5 + 3.0),
    'guide_standoff_top': 12.0,             # M3 F-F hex standoff, 12 mm, on the carrier top
}

INGUN = {
    'receptacle': {'id': 'sources.json#receptacle', 'mpn': 'KS-050 E08 V-30',
                   'sha256': 'bc016b5934c94f39c638c60416cca8d74e30e17870ae94d02f5022a8c42992b1',
                   'facts': {'mounting_hole_fr4_mm': [0.98, 1.0], 'outer_diameter_mm': 0.95, 'collar_diameter_mm': 1.04,
                             'collar_height_mm': 7.9, 'total_length_mm': 40.6, 'press_ring': True, 'wire_outer_diameter_mm': 0.55},
                   'locator': 'page 1/1: Mounting hole, Mechanical data (collar height 7.9), Wiring data; press ring pressed to a '
                              'defined depth adjusts the installation height'},
    'probe': {'id': 'sources.json#probe', 'mpn': 'GKS-050 214 050 A 1000',
              'facts': {'grid_mm': 1.27, 'tip_diameter_mm': 0.5, 'spring_preload_N': 0.44, 'working_stroke_mm': 4.3,
                        'force_at_working_stroke_N': 1.0, 'maximum_stroke_mm': 6.35, 'total_length_mm': 43.2,
                        'barrel_diameter_mm': 0.78},
              'locator': 'page 1/2: General data (Grid), Mechanical data (total length, barrel diameter, strokes, forces), Tip style data'},
    'force_graph': {'id': 'sources.json#probe-4.png', 'sha256': 'e3de0b0b503cd1c09102fcb2e740a53f50671acc5cb559a2b38051b1eb37396c',
                    'facts': {'force_at_maximum_stroke_N': 1.27},
                    'locator': 'linear force-stroke line, 0.44 N at 0 to 1.0 N at 4.3 mm; value at 6.35 mm read from the graph'},
    'catalogue': {'id': 'sources.json#gks-050-catalogue', 'sha256': 'b7c14728d593de96d9e0929cf661eee483311c67e6d7d7822ae7bebd653f035d',
                  'facts': {'installation_height_with_ks_mm': 16.0},
                  'class': 'MANUFACTURER_MIRROR', 'locator': 'GKS-050 catalogue page header: "Installation height with KS: 16,0 / 18,0 mm / '
                                                             'variable" (16.0 for GKS-050..., collar stop at the press ring)'},
}
INGUN_HOLE_WEB = round(INGUN['probe']['facts']['grid_mm'] - INGUN['receptacle']['facts']['mounting_hole_fr4_mm'][1], 6)


def _yardstick():
    ref = json.loads(CANDIDATES.read_text())['references'][0]
    return {'id': ref['id'], 'selection_status': ref['selection_status'],
            'wall_absolute_minimum_mm': ref['rules_used']['wall_absolute_minimum_mm'],
            'standard_tolerance_mm': ref['rules_used']['standard_tolerance_mm']}


YARDSTICK = _yardstick()
MIN_WALL = YARDSTICK['wall_absolute_minimum_mm']


def corner_radius(depth):
    """JLCCNC guidance (candidate reference): minimum internal radius R = H/10 + 0.5 mm for a cavity of depth H."""
    return round(depth / 10 + 0.5, 6)


def tool_diameter(depth):
    return round(depth / 5, 6)


RULES = {
    'minimum_milled_wall_mm': MIN_WALL,
    'minimum_milled_wall_basis': 'captured JLCCNC guidance (candidate reference, NOT selected): absolute minimum 1.0 mm for plastic '
                                 'parts; applied to every milled wall and to every web around a milled hole',
    'probe_bore_web_minimum_mm': INGUN_HOLE_WEB,
    'probe_bore_web_basis': 'INGUN grid >= 1.27 mm with 0.98-1.00 mm FR-4 mounting holes; drilled bores at the board test-point pitch',
    'smd_outline_clearance_mm': 0.2,
    'tht_copper_clearance_mm': 0.3,
    'probe_window_half_width_mm': 1.0,
    'datum_pin_diameter_mm': 2.0,
    'datum_pin_height_above_carrier_mm': 1.0,
    'alignment_dowel_diameter_mm': 2.0,
    'm3_clearance_hole_mm': 3.4,
    'm3_screw_head_diameter_mm': 5.5,
    'm3_countersink_diameter_mm': 6.0,
    'spring_outer_diameter_max_mm': 9.0,
    'contact_nut_across_corners_mm': 4.62,
    'm3_hex_across_corners_mm': 6.35,
    'contact_screw': 'M2 nylon (PA66) screw, tip diameter 2.0 mm, protruding 2.5 mm below the pressure plate',
    'contact_diameter_mm': 2.0,
    'contact_f_side_clearance_mm': 0.3,
    'contact_land_margin_mm': 0.5,
    'pressure_plate_edge_margin_mm': 1.5,
    'pressure_plate_part_clearance_mm': 0.5,
    'resultant_margin_mm': 0.5,
    'clamp_force_margin_factor': 2.0,
    'wire_bend_space_factor_of_od': 10,
    'support_grid_mm': 0.1,
    'support_radius_around_probe_mm': 3.0,
    'board_flexural_modulus_MPa': 18000.0,
    'board_strip_width_mm': 5.0,
    'board_deflection_limit_mm': 0.1,
    'confidence': 'PROJECT-CHOICE design values except the sourced minimums; not machining tolerances, fit results or approvals',
}

R0603 = {
    'body_length_max_mm': 1.75, 'body_width_max_mm': 0.9, 'body_height_max_mm': 0.55, 'class': 'SOURCE_DERIVED',
    'source': {'document': 'UNI-ROYAL Thick Film Chip Resistors (Chip Series) datasheet SMD-SP-001 V.11, 2026-03-17',
               'sha256': 'd27e4cdcdf8fdb4c066ff6030cfc1f46b99efe2a38fe5673fa18a2ee4c7220d3',
               'evidence_source_ids': 'src-0603waf*-ds-p1 (component-0603waf* bundles, MANUFACTURER_PRIMARY)',
               'locator': 'physical page index 3 (printed Page 4/12), section 5 Dimension, row 0603: L 1.60±0.15, W 0.80±0.10, H 0.45±0.10 mm'},
}
SOURCES = {
    'R0603': R0603,
    'PJ-324M': {
        'terminal_projection_below_seating_plane_mm': 3.2, 'tolerance_mm': 0.2, 'class': 'SOURCE_DERIVED (MANUFACTURER_MIRROR)',
        'source': {'fact_id': 'fact-a7-pj-324m-terminal-projection', 'source_id': 'src-a7-pj-324m-sofng-drawing',
                   'sha256': 'c5f2f104e73244a32ed024f7a6577d260678a9b3f3cc3d496531fb930b3c7049',
                   'locator': 'page 0 front view vertical 3.2; tolerance as engineering/a7/study/parameters.json jack_terminal_projection'},
        'protrusion_below_b_face_mm': {'nominal': 1.6, 'basis': '3.2 - 1.6 mm board; the board-thickness tolerance is not sourced'},
        'body_height_mm': 6.3, 'body_height_source': 'fact-a7-pj-324m-overall-height (component-a7-pj-324m)',
    },
    'PCM13SMTR': {
        'peg_length_mm': 0.5, 'class': 'SOURCE_DERIVED (MANUFACTURER_PRIMARY)',
        'source': {'fact_id': 'fact-a7-pcm13smtr-outline', 'source_id': 'src-a7-pcm13smtr-ck-site',
                   'sha256': '6a758d151b7eee7f8cd59594bd92cfec4c9b1470e0743094f185f19e7ac2a868', 'locator': 'page index 2 outline and PC MOUNTING'},
        'protrusion_below_b_face': 'none: 0.5 mm pegs are shorter than the 1.6 mm board',
        'body_height_mm': 1.4, 'body_height_source': 'fact-a7-pcm13smtr-outline height_above_pcb (component-a7-pcm13smtr)',
    },
    'PicoBlade 530470310': {
        'tail_length_below_b_face_mm': None, 'class': 'UNKNOWN',
        'reason': 'no traceable tail length in the recorded evidence: the sales-drawing extract gives only A/B/C/D row dimensions; the 2.3 mm in '
                  'the mechanical layout is unsourced; the KiCad library 3D model is not supplier CAD',
        'mated_height_above_f_face_mm': 5.2, 'mated_height_source': 'A5-sourced mated height used by scripts/a7_mechanical_layout.py',
    },
}

FASTENERS = [(-6.0, 17.0), (22.2, 17.0), (-6.0, 43.6), (22.2, 43.6), (-6.0, 63.0), (22.2, 63.0)]
ALIGNMENT_DOWELS = [(-6.0, 30.0), (22.2, 52.0)]
DATUM_PINS = [('X1', 'X datum on the board x = 16.2 edge', (17.2, 34.0)),
              ('X2', 'X datum on the board x = 16.2 edge', (17.2, 56.0)),
              ('Y1', 'Y datum on the board y = 62.9 edge', (8.1, 63.9))]
GUIDE_X = (-5.5, 21.7)
PRESSURE_PLATE = (-10.5, 19.0, 26.7, 29.5)
TIE_SLOT = (6.1, 15.5, 10.1, 17.5)  # base-plate cable-tie slot, board coordinates


def _expand(box, m):
    return [box[0] - m, box[1] - m, box[2] + m, box[3] + m]


def _clip(box, bounds=None):
    bx = bounds or (CARRIER_BOARD_X[0], CARRIER_Y[0], CARRIER_BOARD_X[1], CARRIER_Y[1])
    x0, y0, x1, y1 = max(box[0], bx[0]), max(box[1], bx[1]), min(box[2], bx[2]), min(box[3], bx[3])
    return [round(v, 6) for v in (x0, y0, x1, y1)] if x0 < x1 and y0 < y1 else None


def _to_carrier(box):
    return [round(16.2 - box[2], 6), box[1], round(16.2 - box[0], 6), box[3]]


def _to_carrier_xy(xy):
    return [round(16.2 - xy[0], 6), xy[1]]


def _box_point_dist(box, pt):
    dx = max(box[0] - pt[0], 0.0, pt[0] - box[2])
    dy = max(box[1] - pt[1], 0.0, pt[1] - box[3])
    return math.hypot(dx, dy)


def _box_gap(a, b):
    return math.hypot(max(b[0] - a[2], a[0] - b[2], 0.0), max(b[1] - a[3], a[1] - b[3], 0.0))


def _in_box(b, x, y):
    return b[0] <= x <= b[2] and b[1] <= y <= b[3]


def _inside(inner, outer):
    return outer[0] <= inner[0] + 1e-9 and outer[1] <= inner[1] + 1e-9 and inner[2] <= outer[2] + 1e-9 and inner[3] <= outer[3] + 1e-9


def _rounded_contains(box, r, pt):
    """Point inside a rectangle whose four corners are rounded with radius r."""
    x, y = pt
    if not _in_box(box, x, y):
        return False
    cx = min(max(x, box[0] + r), box[2] - r)
    cy = min(max(y, box[1] + r), box[3] - r)
    return math.dist((x, y), (cx, cy)) <= r + 1e-9


def population(path=POPULATION):
    rows = [line for line in path.read_text().splitlines() if not line.startswith('ENGINEERING ONLY')]
    return {r['ref']: r for r in csv.DictReader(rows) if r['board'] == 'controller'}


def f_side_heights(geometry, pop):
    """Height above the F face of every F-side part: A7 evidence where the part changed from A5, else the A5 seed envelope."""
    a5 = next(b for b in json.loads(A5_ENVELOPES.read_text())['boards'] if b['name'] == 'controller')
    a5_by_ref = {c['ref']: c for c in a5['components']}
    out = {}
    for f in geometry['footprints']:
        if f['side'] != 'F':
            continue
        row, ref = pop.get(f['ref']), f['ref']
        if f['fpid'] == 'LightBlockA7:PJ324M':
            out[ref] = {'height_mm': SOURCES['PJ-324M']['body_height_mm'], 'source': SOURCES['PJ-324M']['body_height_source']}
        elif f['fpid'] == 'LightBlockA7:PCM13SMTR':
            out[ref] = {'height_mm': SOURCES['PCM13SMTR']['body_height_mm'], 'source': SOURCES['PCM13SMTR']['body_height_source']}
        elif f['fpid'] == 'LightBlock:PICO3':
            out[ref] = {'height_mm': SOURCES['PicoBlade 530470310']['mated_height_above_f_face_mm'],
                        'source': SOURCES['PicoBlade 530470310']['mated_height_source'] + ' (mated; the cable leaves through the plate notch)'}
        elif row and ref in a5_by_ref and a5_by_ref[ref].get('mpn') == row['mpn'] and a5_by_ref[ref].get('height_max_mm') is not None:
            out[ref] = {'height_mm': a5_by_ref[ref]['height_max_mm'],
                        'source': f'A5 seed envelope (engineering/a5/electronics/placement_and_connectivity.json, {ref}, same MPN {row["mpn"]})'}
        else:
            out[ref] = {'height_mm': None, 'source': 'UNKNOWN'}
    return out


def _strip(a, b):
    """Material between two boxes, as the rectangle to remove. Side by side: the strip over the shared span. Diagonal: a strip
    across the narrower gap spanning both boxes, so the joined opening meets each box along an edge, not at a point."""
    xg = (a[2], b[0]) if a[2] <= b[0] else (b[2], a[0]) if b[2] <= a[0] else None
    yg = (a[3], b[1]) if a[3] <= b[1] else (b[3], a[1]) if b[3] <= a[1] else None
    if xg and not yg:
        return [xg[0], max(a[1], b[1]), xg[1], min(a[3], b[3])], 'x'
    if yg and not xg:
        return [max(a[0], b[0]), yg[0], min(a[2], b[2]), yg[1]], 'y'
    if xg[1] - xg[0] <= yg[1] - yg[0]:
        return [xg[0], min(a[1], b[1]), xg[1], max(a[3], b[3])], 'x'
    return [min(a[0], b[0]), yg[0], max(a[2], b[2]), yg[1]], 'y'


def _union_area(boxes):
    xs = sorted({v for q in boxes for v in (q[0], q[2])}); ys = sorted({v for q in boxes for v in (q[1], q[3])}); area = 0.0
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
            if any(q[0] <= cx <= q[2] and q[1] <= cy <= q[3] for q in boxes):
                area += (xs[i + 1] - xs[i]) * (ys[j + 1] - ys[j])
    return area


def _covered(strip, boxes):
    clipped = [[max(q[0], strip[0]), max(q[1], strip[1]), min(q[2], strip[2]), min(q[3], strip[3])] for q in boxes]
    clipped = [q for q in clipped if q[0] < q[2] and q[1] < q[3]]
    return _union_area(clipped) >= (strip[2] - strip[0]) * (strip[3] - strip[1]) - 1e-9


def _min_size(box, size):
    b = list(box)
    for lo, hi in ((0, 2), (1, 3)):
        short = size - (b[hi] - b[lo])
        if short > 0:
            b[lo] -= short / 2
            b[hi] += short / 2
    return b


def _windows(contents, bounds, wall, radius):
    """Windows as unions of member rectangles whose exposed corners are rounded with the internal radius.

    Every member grows by the corner allowance r(1 - 1/sqrt2) so a rounded corner never cuts into its content, and is at
    least 2r wide. Wherever two members (of any window, including members already joined elsewhere) leave material
    thinner than the wall that other members do not already remove, a bridge member removes it; a member closer than the
    wall to the plate edge opens through it. Each member corner is rounded unless the union also occupies a neighbouring
    quadrant there (then it is a straight or re-entrant edge, which needs no radius). A union of rounded rectangles of
    radius r can be milled by a tool of radius r; the remaining thin-material question is checked independently by raster.
    """
    allowance = math.ceil(radius * (1 - 1 / math.sqrt(2)) * 1000) / 1000
    mem = [{'ref': c['ref'], 'box': _min_size(_expand(c['box'], allowance), 2 * radius)} for c in contents]
    for _ in range(400):
        boxes = [m['box'] for m in mem]
        fix = None
        for m in mem:
            b = m['box']
            for k, edge, gap in ((0, bounds[0], b[0] - bounds[0]), (1, bounds[1], b[1] - bounds[1]),
                                 (2, bounds[2], bounds[2] - b[2]), (3, bounds[3], bounds[3] - b[3])):
                if gap < wall and abs(gap + radius) > 1e-9 and gap > -radius:
                    b[k] = edge - radius if k < 2 else edge + radius
                    fix = True
        if fix:
            continue
        for i in range(len(mem)):
            for j in range(i + 1, len(mem)):
                a, b = boxes[i], boxes[j]
                g = _box_gap(a, b)
                diag_touch = g == 0 and (min(a[2], b[2]) - max(a[0], b[0]) <= 0 or min(a[3], b[3]) - max(a[1], b[1]) <= 0) \
                    and not (min(a[2], b[2]) - max(a[0], b[0]) <= 0 and min(a[3], b[3]) - max(a[1], b[1]) > 0) \
                    and not (min(a[3], b[3]) - max(a[1], b[1]) <= 0 and min(a[2], b[2]) - max(a[0], b[0]) > 0)
                if not (0 < g < wall or diag_touch):
                    continue
                st, axis = _strip(a, b)
                if st[2] - st[0] > 1e-9 and st[3] - st[1] > 1e-9 and _covered(st, boxes):
                    continue
                br = list(st)
                if axis == 'x':
                    br[0] -= radius; br[2] += radius
                else:
                    br[1] -= radius; br[3] += radius
                fix = {'ref': f"bridge {mem[i]['ref']}+{mem[j]['ref']}", 'box': _min_size(br, 2 * radius)}
                break
            if fix:
                break
        if not fix:
            break
        mem.append(fix)
    else:
        raise ValueError('window merging did not converge')
    # connected components (overlap or touch)
    comp = list(range(len(mem)))

    def find(i):
        while comp[i] != i:
            comp[i] = comp[comp[i]]
            i = comp[i]
        return i
    for i in range(len(mem)):
        for j in range(i + 1, len(mem)):
            if _box_gap(mem[i]['box'], mem[j]['box']) <= 0:
                comp[find(i)] = find(j)
    groups = {}
    for i, m in enumerate(mem):
        groups.setdefault(find(i), []).append(m)
    out = []
    eps = 1e-6
    for ms in groups.values():
        boxes = [m['box'] for m in ms]
        members = []
        for m in ms:
            b = [round(v, 6) for v in m['box']]
            rounded = []
            for cxv, cyv, sx, sy in ((b[0], b[1], -1, -1), (b[2], b[1], 1, -1), (b[0], b[3], -1, 1), (b[2], b[3], 1, 1)):
                probes_q = [(cxv + sx * eps, cyv + sy * eps), (cxv - sx * eps, cyv + sy * eps), (cxv + sx * eps, cyv - sy * eps)]
                occupied = [any(_in_box(o, *q) for o in boxes) for q in probes_q]
                rounded.append(not any(occupied))
            members.append({'ref': m['ref'], 'box_board_mm': b, 'box_carrier_mm': _to_carrier(b), 'rounded_corners': rounded})
        bb = [round(min(q[0] for q in boxes), 6), round(min(q[1] for q in boxes), 6), round(max(q[2] for q in boxes), 6), round(max(q[3] for q in boxes), 6)]
        out.append({'members': sorted(members, key=lambda m: m['ref']), 'parts': sorted(m['ref'] for m in ms if not m['ref'].startswith('bridge')),
                    'board_box_mm': bb, 'carrier_box_mm': _to_carrier(bb), 'corner_radius_mm': radius})
    return sorted(out, key=lambda w: (w['board_box_mm'][1], w['board_box_mm'][0])), allowance


def _window_dist(w, xy):
    return min(_box_point_dist(m['box_board_mm'], xy) for m in w['members'])


def _in_window(w, x, y):
    return any(_in_box(m['box_board_mm'], x, y) for m in w['members'])


def _webs(holes, windows, bounds, wall):
    """Every hole-to-window, hole-to-edge and hole-to-hole web; conflicts below the wall."""
    webs, conflicts = [], []
    for name, xy, rad in holes:
        for w in windows:
            d = round(_window_dist(w, xy) - rad, 6)
            webs.append({'hole': name, 'to': '+'.join(w['parts'][:3]) + ('...' if len(w['parts']) > 3 else ''), 'web_mm': d})
            if d < wall:
                conflicts.append(f'{name} to window {webs[-1]["to"]} web {d:.3f} mm < {wall} mm')
        e = round(min(xy[0] - rad - bounds[0], bounds[2] - xy[0] - rad, xy[1] - rad - bounds[1], bounds[3] - xy[1] - rad), 6)
        webs.append({'hole': name, 'to': 'plate edge', 'web_mm': e})
        if e < wall:
            conflicts.append(f'{name} to plate edge web {e:.3f} mm < {wall} mm')
    for i, (n1, a, ra) in enumerate(holes):
        for n2, b, rb in holes[i + 1:]:
            d = round(math.dist(a, b) - ra - rb, 6)
            webs.append({'hole': n1, 'to': n2, 'web_mm': d})
            if d < wall:
                conflicts.append(f'{n1}/{n2} web {d:.3f} mm < {wall} mm')
    return sorted(webs, key=lambda w: w['web_mm'])[:12], conflicts


def _walls(windows, bounds, wall):
    """Walls between different windows and to the plate edge (member boxes; rounding only widens them)."""
    out = []
    for i, a in enumerate(windows):
        for b in windows[i + 1:]:
            g = min(_box_gap(p['box_board_mm'], q['box_board_mm']) for p in a['members'] for q in b['members'])
            if g < wall:
                out.append(f"window {'+'.join(a['parts'][:2])}/{'+'.join(b['parts'][:2])} wall {g:.3f} mm")
        for m in a['members']:
            bx = m['box_board_mm']
            for gap in (bx[0] - bounds[0], bx[1] - bounds[1], bounds[2] - bx[2], bounds[3] - bx[3]):
                if 0 < gap < wall:
                    out.append(f"window {'+'.join(a['parts'][:2])}/plate edge wall {gap:.3f} mm")
    return out


def _tri_margin(tri, pt):
    (x1, y1), (x2, y2), (x3, y3) = tri
    area2 = (x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)
    if abs(area2) < 1e-9:
        return -1.0
    out = []
    for (ax, ay), (bx, by) in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
        cross = (bx - ax) * (pt[1] - ay) - (by - ay) * (pt[0] - ax)
        out.append(cross / math.hypot(bx - ax, by - ay) * (1 if area2 > 0 else -1))
    return min(out)


def _hull(points):
    pts = sorted(set(points))

    def turn(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and turn(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and turn(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _hull_margin(hull, pt):
    """Signed distance from pt to the nearest edge of a counter-clockwise hull (positive inside)."""
    m = math.inf
    for i, a in enumerate(hull):
        b = hull[(i + 1) % len(hull)]
        m = min(m, ((b[0] - a[0]) * (pt[1] - a[1]) - (b[1] - a[1]) * (pt[0] - a[0])) / math.dist(a, b))
    return m


def _barycentric(tri, pt):
    (x1, y1), (x2, y2), (x3, y3) = tri
    det = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
    a = ((y2 - y3) * (pt[0] - x3) + (x3 - x2) * (pt[1] - y3)) / det
    b = ((y3 - y1) * (pt[0] - x3) + (x1 - x3) * (pt[1] - y3)) / det
    return [a, b, 1 - a - b]


def lead_depth(key):
    """Lead or body depth below the B face; None where unsourced (the J5 tail)."""
    if key == 'PJ-324M':
        src = SOURCES[key]
        return round(src['terminal_projection_below_seating_plane_mm'] + src['tolerance_mm'] - BOARD_THICKNESS, 6)
    return None


def design(geometry: dict, probes: list[dict], pop: dict | None = None) -> dict:
    """Probe plate, support carrier with windows, datums, keying, support, pressure plate, stack and wiring from native geometry."""
    pop = population() if pop is None else pop
    probe_refs = {p['ref'] for p in probes}
    cbounds = (CARRIER_BOARD_X[0], CARRIER_Y[0], CARRIER_BOARD_X[1], CARRIER_Y[1])
    reliefs, unknown_heights, j5_pads = [], [], []
    for f in sorted(geometry['footprints'], key=lambda f: f['ref']):
        ref = f['ref']
        if ref in probe_refs:
            continue
        if f['side'] == 'B':
            row = pop.get(ref)
            if f['fpid'] != 'LightBlock:R0603' or row is None or row['population'] != 'FITTED' or not row['mpn'].startswith('0603WAF'):
                raise ValueError(f'{ref}: B-side part without a classified height source')
            rot = f['rotation_deg']
            if abs(rot - round(rot)) > 1e-6 or round(rot) % 90:
                raise ValueError(f'{ref}: non-orthogonal rotation; body outline box not derived')
            hl, hw = R0603['body_length_max_mm'] / 2, R0603['body_width_max_mm'] / 2
            dx, dy = (hl, hw) if round(rot) % 180 == 0 else (hw, hl)
            cx, cy = f['at_mm']
            o = [cx - dx, cy - dy, cx + dx, cy + dy]
            for q in f['pads']:
                b = q['bbox_mm']
                o = [min(o[0], b[0]), min(o[1], b[1]), max(o[2], b[2]), max(o[3], b[3])]
            box = _clip(_expand(o, RULES['smd_outline_clearance_mm']), cbounds)
            if box:
                reliefs.append({'ref': ref, 'box': box, 'height_source': 'R0603', 'height_class': 'SOURCE_DERIVED',
                                'body_board_mm': [round(v, 6) for v in o], 'depth_below_b_face_mm': R0603['body_height_max_mm']})
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
            box = _clip(_expand(p['bbox_mm'], RULES['tht_copper_clearance_mm']), cbounds)
            if box:
                reliefs.append({'ref': f'{ref}.{p["number"]}', 'box': box, 'height_source': key, 'height_class': SOURCES[key]['class'],
                                'body_board_mm': [round(v, 6) for v in p['bbox_mm']], 'depth_below_b_face_mm': lead_depth(key)})
                if key == 'PicoBlade 530470310':
                    j5_pads.append(box)
        if SOURCES[key]['class'] == 'UNKNOWN':
            unknown_heights.append(f'{ref} ({key}): lead tail below the B face')
    hw = RULES['probe_window_half_width_mm']
    probe_boxes = [{'ref': p['ref'], 'box': _expand(list(p['board_xy_mm']) * 2, hw)} for p in probes]

    # ---- support carrier: windows over every B-face feature and the probe field --------------------------------
    rc = corner_radius(CARRIER_THICKNESS)
    windows, allowance = _windows(reliefs + probe_boxes, cbounds, MIN_WALL, rc)
    r_pin, r_m3, r_dowel = RULES['datum_pin_diameter_mm'] / 2, RULES['m3_clearance_hole_mm'] / 2, RULES['alignment_dowel_diameter_mm'] / 2
    pins = [{'id': i, 'role': role, 'board_xy_mm': list(xy), 'carrier_xy_mm': _to_carrier_xy(xy)} for i, role, xy in DATUM_PINS]

    # ---- pressure plate contacts on free F-face area, enclosing the probe resultant and the spring resultant -------------
    fside = [f['courtyard_bbox_mm']['F'] for f in geometry['footprints'] if f['side'] == 'F' and f['courtyard_bbox_mm'].get('F')]
    j5 = next(f for f in geometry['footprints'] if f['fpid'] == 'LightBlock:PICO3')
    notch = [round(v, 6) for v in _expand(j5['courtyard_bbox_mm']['F'], RULES['pressure_plate_part_clearance_mm'])]
    notch[3] = PRESSURE_PLATE[3]
    rcon = RULES['contact_diameter_mm'] / 2
    em = RULES['pressure_plate_edge_margin_mm']
    hole_list = ([(p['ref'], p['board_xy_mm'], hw) for p in probes] + [(q['id'], q['board_xy_mm'], r_pin) for q in pins]
                 + [(f'F{i + 1}', xy, r_m3) for i, xy in enumerate(FASTENERS)] + [(f'D{i + 1}', xy, r_dowel) for i, xy in enumerate(ALIGNMENT_DOWELS)])
    cx = sum(p['board_xy_mm'][0] for p in probes) / len(probes)
    cy = sum(p['board_xy_mm'][1] for p in probes) / len(probes)
    cands = []
    for i in range(round(16.2 / 0.1) + 1):
        x = round(i * 0.1, 6)
        for j in range(round((PRESSURE_PLATE[3] - PRESSURE_PLATE[1]) / 0.1) + 1):
            y = round(PRESSURE_PLATE[1] + j * 0.1, 6)
            if x - rcon < 0 or x + rcon > 16.2 or y - rcon < CARRIER_Y[0]:
                continue
            if not (PRESSURE_PLATE[1] + em <= y <= PRESSURE_PLATE[3] - em) or _box_point_dist(notch, (x, y)) < em:
                continue
            if any(_box_point_dist(b, (x, y)) < rcon + RULES['contact_f_side_clearance_mm'] for b in fside):
                continue
            cands.append((x, y))
    thinned = []
    for x, y in sorted(cands, key=lambda q: math.dist(q, (cx, cy))):
        if all(math.dist((x, y), q) >= 1.0 for q in thinned):
            thinned.append((x, y))
    ys_range = (PRESSURE_PLATE[1] + RULES['m3_hex_across_corners_mm'] / 2 + 0.125 + MIN_WALL,
                PRESSURE_PLATE[3] - RULES['m3_hex_across_corners_mm'] / 2 - 0.125 - MIN_WALL)
    ys_grid = [round(ys_range[0] + 0.1 * k, 6) for k in range(int((ys_range[1] - ys_range[0]) / 0.1) + 1)]
    gx_mid = (GUIDE_X[0] + GUIDE_X[1]) / 2
    # above the plate, a contact nut must clear the spring and washer on each guide
    spring_keep = RULES['spring_outer_diameter_max_mm'] / 2 + RULES['contact_nut_across_corners_mm'] / 2 + RULES['pressure_plate_part_clearance_mm']
    best = None
    need = RULES['resultant_margin_mm']
    for a in range(len(thinned)):
        for b in range(a + 1, len(thinned)):
            for c in range(b + 1, len(thinned)):
                tri = (thinned[a], thinned[b], thinned[c])
                ok = [v for v in ys_grid if all(math.dist(t, (gx, v)) >= spring_keep for t in tri for gx in GUIDE_X)]
                if not ok:
                    continue
                ys = max(ok, key=lambda v: _tri_margin(tri, (gx_mid, v)))
                mq = _tri_margin(tri, (gx_mid, ys))
                if mq < need:
                    continue
                mr = _tri_margin(tri, (cx, cy))
                if mr < need:
                    continue
                score = min(mr, mq)
                if best is None or score > best[0] + 1e-9:
                    best = (score, tri, ys, mr, mq)
    if best is None:
        raise ValueError(f'no pressure-plate contact triangle over land encloses both the probe and the spring resultants ({len(cands)} candidates, {len(thinned)} thinned)')
    _, tri, ys, mr, mq = best
    guides = [{'id': f'G{i + 1}', 'board_xy_mm': [gx, ys], 'carrier_xy_mm': _to_carrier_xy((gx, ys))} for i, gx in enumerate(GUIDE_X)]
    hole_list += [(g['id'], g['board_xy_mm'], r_m3) for g in guides]

    # ---- walls and webs (support carrier) ----------------------------------------------------------------------
    r_csk = RULES['m3_countersink_diameter_mm'] / 2  # carrier fasteners are countersunk flush: the jack bodies overhang the board edge
    c_holes = [(q['id'], q['board_xy_mm'], r_pin) for q in pins] + [(f'F{i + 1}', xy, r_csk) for i, xy in enumerate(FASTENERS)] \
        + [(f'D{i + 1}', xy, r_dowel) for i, xy in enumerate(ALIGNMENT_DOWELS)] + [(g['id'], g['board_xy_mm'], r_m3) for g in guides]
    c_webs, c_conf = _webs(c_holes, windows, cbounds, MIN_WALL)
    c_walls = _walls(windows, cbounds, MIN_WALL)
    for g in guides:  # the guide standoff stands on land
        foot = RULES['m3_hex_across_corners_mm'] / 2
        for w in windows:
            if _window_dist(w, g['board_xy_mm']) < foot:
                c_conf.append(f"{g['id']} standoff footprint over window {'+'.join(w['parts'][:2])}")

    # ---- probe plate: bores in solid material, one window under the J5 leads ----------------------------------
    tp = STACK['probe_plate'][1] - STACK['probe_plate'][0]
    rp = corner_radius(tp)
    pwin, _ = _windows([{'ref': 'J5 leads', 'box': [min(b[0] for b in j5_pads), min(b[1] for b in j5_pads),
                                                      max(b[2] for b in j5_pads), max(b[3] for b in j5_pads)]}], cbounds, MIN_WALL, rp) \
        if j5_pads else ([], 0)
    p_holes = [(f'F{i + 1}', xy, r_m3) for i, xy in enumerate(FASTENERS)] + [(f'D{i + 1}', xy, r_dowel) for i, xy in enumerate(ALIGNMENT_DOWELS)]
    p_webs, p_conf = _webs(p_holes, pwin, cbounds, MIN_WALL)
    bore_webs = sorted(round(math.dist(a['board_xy_mm'], b['board_xy_mm']) - BORE_MAX, 6) for i, a in enumerate(probes) for b in probes[i + 1:])
    for p in probes:
        for name, xy, rr in p_holes:
            d = math.dist(p['board_xy_mm'], xy) - rr - BORE_MAX / 2
            if d < MIN_WALL:
                p_conf.append(f"{p['ref']} bore to {name} web {d:.3f} mm < {MIN_WALL} mm")
        for w in pwin:
            d = _window_dist(w, p['board_xy_mm']) - BORE_MAX / 2
            if d < MIN_WALL:
                p_conf.append(f"{p['ref']} bore to J5 window web {d:.3f} mm < {MIN_WALL} mm")
    if bore_webs[0] < INGUN_HOLE_WEB:
        p_conf.append(f'probe bore web {bore_webs[0]:.3f} mm < INGUN {INGUN_HOLE_WEB} mm')

    # ---- keying: the board turned 180 degrees in plane must not seat ------------------------------------------
    def land(x, y):
        return (_in_box(cbounds, x, y) and not any(_in_window(w, x, y) for w in windows)
                and all(math.dist((x, y), xy) > rr for _, xy, rr in c_holes))
    turned = []
    for f in sorted(geometry['footprints'], key=lambda f: f['ref']):
        if f['ref'] in probe_refs:
            continue
        for pd in f['pads']:
            if not (f['side'] == 'B' or (pd['attribute'] == 'PTH' and f['fpid'] == 'LightBlockA7:PJ324M')):
                continue
            b = pd['bbox_mm']
            tx, ty = 16.2 - (b[0] + b[2]) / 2, 62.9 - (b[1] + b[3]) / 2
            turned.append({'feature': f"{f['ref']}.{pd['number']}", 'turned_centre_mm': [round(tx, 6), round(ty, 6)],
                           'lands_on_carrier': land(tx, ty) and _in_box(BOARD, tx, ty)})
    blocking = [t['feature'] for t in turned if t['lands_on_carrier']]
    keying = {'method': 'B-face features stand proud of the B face: PJ-324M terminals (nominal 1.6 mm, MANUFACTURER_MIRROR) and the '
                        'soldered R0603 terminations (body up to 0.55 mm, SOURCE_DERIVED). In the correct pose all of them fall into '
                        'carrier windows; turned 180 degrees in plane, the listed centres land on solid carrier, hold the board off the '
                        'land and the datum pins, and the probes miss the test pads. Face-down insertion is excluded by the F-side jacks.',
              'turned_pose_features': turned, 'blocking_features': blocking, 'keyed': len(blocking) >= 3,
              'acceptance_requirement': 'trial-insert the board turned 180 degrees: it must not seat (visible gap at the datum pins)'}

    # ---- support land ------------------------------------------------------------------------------------------
    g = RULES['support_grid_mm']
    y_lo, y_hi = max(CARRIER_Y[0], 0.0), min(CARRIER_Y[1], BOARD[3])
    near = {p['ref']: [0, 0] for p in probes}
    land_n = total = 0
    land_pts = []
    for i in range(round(16.2 / g)):
        x = (i + 0.5) * g
        for j in range(round((y_hi - y_lo) / g)):
            y = y_lo + (j + 0.5) * g
            free = land(x, y)
            if free:
                land_pts.append((x, y))
            total += 1
            land_n += free
            for p in probes:
                if math.dist((x, y), p['board_xy_mm']) <= RULES['support_radius_around_probe_mm']:
                    near[p['ref']][1] += 1
                    near[p['ref']][0] += free
    support = {'method': f'grid {g} mm over the board outline inside the carrier (board X 0-16.2, Y {y_lo}-{y_hi})',
               'land_fraction': round(land_n / total, 4),
               'land_fraction_within_radius_of_probe': {k: round(a / b, 4) for k, (a, b) in near.items()},
               'load_path': 'springs -> pressure plate -> three nylon contacts on the F face; two contacts sit over the probe field and '
                            'oppose the probe forces through the board locally; the remaining load goes through the board to the carrier '
                            'land around the windows -> spacers -> probe plate -> standoffs -> base',
               'scope': 'rigid-body statics plus a conservative beam estimate for the board across the window (below); plate '
                        'deflection not analysed'}

    # ---- clamp force, springs and statics ----------------------------------------------------------------------
    f_max = INGUN['force_graph']['facts']['force_at_maximum_stroke_N']
    f_work = INGUN['probe']['facts']['force_at_working_stroke_N']
    n = len(probes)
    p_max = round(n * f_max, 6)
    s_total = round(RULES['clamp_force_margin_factor'] * p_max, 6)
    q = (gx_mid, ys)
    react = [round(v * s_total, 6) for v in _barycentric(tri, q)]
    net = [round((s_total * q[0] - p_max * cx) / (s_total - p_max), 6), round((s_total * q[1] - p_max * cy) / (s_total - p_max), 6)]
    land_hull = _hull(land_pts)
    net_margin = _hull_margin(land_hull, net)
    # board across the probe-field window: every window-borne contact load taken as one unbalanced point load at mid-span of a
    # simply supported strip spanning the window's longest side (conservative: probe forces would reduce it)
    contact_windows = [w for w in windows if any(_in_window(w, *pr['board_xy_mm']) for pr in probes)
                       or any(_window_dist(w, c) < rcon for c in tri)]
    span = max((max(w['board_box_mm'][2] - w['board_box_mm'][0], w['board_box_mm'][3] - w['board_box_mm'][1]) for w in contact_windows), default=0.0)
    f_win = round(max(p_max, sum(r for r, c in zip(react, tri) if any(_window_dist(w, c) < rcon for w in contact_windows))), 6)
    e_mod, strip = RULES['board_flexural_modulus_MPa'], RULES['board_strip_width_mm']
    inertia = strip * BOARD_THICKNESS ** 3 / 12
    defl = round(f_win * span ** 3 / (48 * e_mod * inertia), 6)
    bending = {'model': 'simply supported strip, point load at mid-span: d = F L^3 / (48 E I), I = b t^3 / 12',
               'span_mm': round(span, 6), 'strip_width_mm': strip, 'board_thickness_mm': BOARD_THICKNESS,
               'flexural_modulus_MPa': e_mod, 'flexural_modulus_class': 'ASSUMED (typical FR-4 flexural modulus; the board laminate is not sourced)',
               'load_N': f_win, 'load_basis': 'larger of the total probe force at maximum stroke and the summed reactions of the contacts '
                                              'over the window, taken as wholly unbalanced',
               'deflection_mm': defl, 'limit_mm': RULES['board_deflection_limit_mm'],
               'limit_basis': 'PROJECT-CHOICE: small against the 2.05 mm between the 4.3 mm working stroke and the 6.35 mm maximum'}
    pp_bottom, pp_top = STACK['pressure_plate']
    l_nom = round(STACK['guide_standoff_top'] - pp_top, 6)
    holddown = {
        'type': 'screw-down FR-4 pressure plate, 3 mm, guided on two M3 hex standoffs (12 mm) standing on the carrier; a compression '
                'spring on each standoff is held by an M3 screw and washer on the standoff top; three M2 nylon screws in the plate are '
                'the contacts',
        'contacts_board_mm': [list(t) for t in tri], 'contact_diameter_mm': RULES['contact_diameter_mm'],
        'probe_resultant_board_mm': [round(cx, 6), round(cy, 6)], 'probe_resultant_margin_mm': round(mr, 6),
        'guides': guides, 'spring_resultant_board_mm': [gx_mid, ys], 'spring_resultant_margin_mm': round(mq, 6),
        'probe_force_total_N': {'working_stroke': round(n * f_work, 6), 'maximum_stroke': p_max},
        'clamp_force_margin_factor': RULES['clamp_force_margin_factor'],
        'required_total_spring_force_N': s_total,
        'contact_reactions_N': react,
        'board_net_load_point_mm': net,
        'board_net_load_point_inside_land_hull_mm': round(net_margin, 6),
        'board_bending_across_window': bending,
        'statics': 'plate: equal spring forces at G1 and G2 act at their midpoint, inside the contact triangle, so all three contacts '
                   'carry load (barycentric shares); board: contact loads minus the probe load at maximum stroke leave a net downward '
                   'load whose point lies inside the convex hull of the carrier land under the board, so the board stays on the land '
                   '(rigid bodies)',
        'spring_requirement': {'quantity': 2, 'inner_diameter_min_mm': 6.6, 'outer_diameter_max_mm': 9.0,
                               'installed_length_nominal_mm': l_nom, 'installed_length_range_mm': [round(l_nom - 0.3, 6), round(l_nom + 0.3, 6)],
                               'force_min_over_range_N': round(s_total / 2, 6), 'solid_length_max_mm': round(l_nom - 0.6, 6),
                               'free_length_max_mm': round(l_nom + 6.0 - 1.5, 6),
                               'free_length_basis': 'the M3 x 6 top screw engages at least 1.5 mm of standoff thread before it starts to compress '
                                                    'the spring (PROJECT-CHOICE)',
                               'basis': 'each spring carries half of the required total over the installed-length range, which covers board '
                                        'thickness and contact-screw setting variation of +/-0.3 mm (PROJECT-CHOICE envelope)',
                               'status': 'REQUIRED_NOT_SELECTED (standard compression spring; part not chosen)'},
        'contact_setting': 'each M2 nylon screw protrudes 2.5 +/-0.1 mm below the plate (acceptance measurement before use)',
        'operation': 'remove the two M3 x 6 top screws with their washers and springs and lift the plate off; insert the board and push it '
                     'against X1, X2 and Y1; refit plate, springs and washers and screw down until each screw head seats on its standoff '
                     '(hard stop). The spring length at the hard stop, not the screw torque, sets the clamp force',
    }

    # ---- registration --------------------------------------------------------------------------------------------
    alloc = {'board_edge_to_test_pad_mm': 0.10, 'datum_contact_mm': 0.0, 'datum_pin_to_bore_assembled_mm': 0.05,
             'probe_tip_lateral_mm': 0.07}
    budget = round((1.0 - INGUN['probe']['facts']['tip_diameter_mm']) / 2, 6)
    registration = {
        'datums': 'board pushed by hand against X1, X2 (x = 16.2 edge) and Y1 (y = 62.9 edge) before the pressure plate is screwed down; '
                  'friction under the contacts then holds it. Datum contact clearance zero is an acceptance check, not a spring',
        'plate_alignment': 'two 2 mm dowels (D1, D2) through carrier and probe plate align the bores to the datum pins; the M3 fasteners '
                           'only clamp',
        'radial_budget_mm': budget,
        'allocation_mm': alloc, 'allocation_class': 'PROJECT-CHOICE, each closed by the acceptance measurement below',
        'worst_case_margin_mm': round(budget - sum(alloc.values()), 6),
        'acceptance_requirements': [
            'each board: TP1-TP5 pad centres measured from the x = 16.2 and y = 62.9 edges; radial deviation from the design '
            'position <= 0.10 mm, else the board is not tested in this fixture',
            'assembled carrier and probe plate: bore centres measured through the probe window from the datum pin contact lines; '
            'radial deviation <= 0.05 mm; bores 0.98-1.00 mm; windows and walls as drawn, walls not below 1.0 mm',
            'installed probes: tip lateral offset from the bore axis at the working stroke <= 0.07 mm',
            'clamped board: a 0.02 mm feeler does not enter between the board edge and X1, X2 or Y1',
        ]}

    # ---- installation height and stroke ------------------------------------------------------------------------
    h_inst = INGUN['catalogue']['facts']['installation_height_with_ks_mm']
    pp_top_z = STACK['probe_plate'][1]
    d_press = round(h_inst - INGUN['probe']['facts']['working_stroke_mm'] + pp_top_z, 6)
    rec_top = round(pp_top_z + INGUN['receptacle']['facts']['collar_height_mm'] - d_press, 6)
    rec_bottom = round(rec_top - INGUN['receptacle']['facts']['total_length_mm'], 6)
    stroke = {
        'travel_stop': 'the board B face seats on the solid carrier land, which is independent of the receptacle press depth',
        'installation_height_mm': h_inst, 'installation_height_class': INGUN['catalogue']['class'],
        'press_ring_depth_mm': d_press,
        'set_installation_height': f'receptacle press ring pressed {d_press} mm into the probe-plate bore so the free probe tip stands '
                                   f"{INGUN['probe']['facts']['working_stroke_mm']} mm above the carrier top",
        'accommodated_installation_height_mm': [round(INGUN['probe']['facts']['working_stroke_mm'] - pp_top_z, 6),
                                                round(INGUN['probe']['facts']['working_stroke_mm'] - pp_top_z + tp, 6)],
        'receptacle_top_z_mm': rec_top, 'receptacle_bottom_z_mm': rec_bottom,
        'stroke_window_mm': [0.0, INGUN['probe']['facts']['maximum_stroke_mm']],
        'acceptance_requirement': 'each probe: free tip height above the carrier top 4.3 +/-0.3 mm (stroke 4.0-4.6 mm, inside 0-6.35 mm)',
        'force_per_probe_N': {'at_4.0_mm': round(0.44 + (1.0 - 0.44) / 4.3 * 4.0, 3), 'at_4.6_mm': round(0.44 + (1.0 - 0.44) / 4.3 * 4.6, 3)},
        'force_basis': 'linear INGUN force-stroke graph (0.44 N preload, 1.0 N at 4.3 mm)'}

    # ---- pressure plate clearance to F-side parts ----------------------------------------------------------------
    heights = f_side_heights(geometry, pop)
    under = []
    plate_conf = []
    for f in geometry['footprints']:
        cb = f['courtyard_bbox_mm'].get('F') if f['side'] == 'F' else None
        if not cb or f['fpid'] == 'LightBlock:PICO3':
            continue
        ov = _clip(cb, PRESSURE_PLATE)
        if not ov or _inside(ov, notch):
            continue
        h = heights[f['ref']]['height_mm']
        gap = None if h is None else round(pp_bottom - BOARD_THICKNESS - h, 6)
        under.append({'ref': f['ref'], 'height_mm': h, 'clearance_to_plate_mm': gap, 'source': heights[f['ref']]['source']})
        if gap is None or gap < RULES['pressure_plate_part_clearance_mm']:
            plate_conf.append(f"{f['ref']} under the pressure plate: clearance {gap}")
    guide_hole, tap_hole = 6.6, 1.6
    notch_win = [{'parts': ['J5 notch'], 'members': [{'box_board_mm': notch}]}]
    q_webs, q_conf = _webs([(g['id'], g['board_xy_mm'], guide_hole / 2) for g in guides]
                           + [(f'C{i + 1}', list(t), tap_hole / 2) for i, t in enumerate(tri)], notch_win, PRESSURE_PLATE, MIN_WALL)
    pressure_plate = {'outline_board_mm': list(PRESSURE_PLATE), 'z_mm': [pp_bottom, pp_top], 'j5_notch_board_mm': notch,
                      'corner_radius_mm': corner_radius(pp_top - pp_bottom), 'guide_hole_diameter_mm': guide_hole,
                      'contact_tap_hole_diameter_mm': tap_hole, 'parts_under_plate': sorted(under, key=lambda u: u['ref']),
                      'smallest_webs': q_webs, 'web_conflicts': q_conf, 'clearance_conflicts': plate_conf}

    # ---- wiring, insulation, base ------------------------------------------------------------------------------
    base_top = STACK['base_plate'][1]
    b_webs, b_conf = _webs([(f'F{i + 1}', xy, r_csk) for i, xy in enumerate(FASTENERS)],
                           [{'parts': ['tie slot'], 'members': [{'box_board_mm': list(TIE_SLOT)}]}], cbounds, MIN_WALL)
    base_plate = {'z_mm': list(STACK['base_plate']), 'corner_radius_mm': corner_radius(STACK['base_plate'][1] - STACK['base_plate'][0]),
                  'tie_slot_board_mm': list(TIE_SLOT), 'smallest_webs': b_webs, 'web_conflicts': b_conf}
    bend = round(rec_bottom - base_top, 6)
    need_bend = RULES['wire_bend_space_factor_of_od'] * INGUN['receptacle']['facts']['wire_outer_diameter_mm']
    metal = [(f'F{i + 1}', xy, RULES['m3_hex_across_corners_mm'] / 2) for i, xy in enumerate(FASTENERS)] \
        + [(g['id'], g['board_xy_mm'], 9.0 / 2) for g in guides] + [(q['id'], q['board_xy_mm'], r_pin) for q in pins] \
        + [(f'D{i + 1}', xy, r_dowel) for i, xy in enumerate(ALIGNMENT_DOWELS)]
    probe_r = INGUN['receptacle']['facts']['collar_diameter_mm'] / 2
    metal_gap = min((round(math.dist(xy, p['board_xy_mm']) - rr - probe_r, 6), name, p['ref']) for name, xy, rr in metal for p in probes)
    copper = [(pd['bbox_mm'], f['ref']) for f in geometry['footprints'] for pd in f['pads']]
    datum_cu = {}
    for q in pins:
        contact = (16.2, q['board_xy_mm'][1]) if q['id'].startswith('X') else (q['board_xy_mm'][0], 62.9)
        datum_cu[q['id']] = round(min(_box_point_dist(b, contact) for b, _ in copper), 6)
    wiring = {'receptacle_bottom_z_mm': rec_bottom, 'base_plate_top_z_mm': base_top, 'wire_bend_space_mm': bend,
              'required_bend_space_mm': need_bend,
              'basis': f"{RULES['wire_bend_space_factor_of_od']} x the 0.55 mm Tefzel wire outer diameter (PROJECT-CHOICE bend allowance)",
              'retention': 'the five prewired leads leave the receptacle tails, are sleeved with TP1-TP5 labels and tied through the base-plate '
                           'slot (cable tie); no solder joint on the receptacle (INGUN note: crimp points must not be soldered)',
              'tie_slot_board_mm': list(TIE_SLOT)}
    insulation = {'plates': 'support carrier, probe plate, pressure plate and base plate are FR-4 (insulating)',
                  'board_contacts': 'nylon M2 contacts on the F face; datum pins touch only the board edge',
                  'metal_to_probe_min_gap_mm': {'gap': metal_gap[0], 'between': [metal_gap[1], metal_gap[2]]},
                  'datum_contact_to_nearest_copper_mm': datum_cu}

    # ---- criteria ---------------------------------------------------------------------------------------------
    relieved = all(any(_inside(want, m['box_board_mm']) for w in windows for m in w['members'])
                   for f in geometry['footprints'] if f['ref'] not in probe_refs for pd in f['pads']
                   if (f['side'] == 'B' or pd['attribute'] == 'PTH') for want in [_clip(pd['bbox_mm'], cbounds)] if want)
    fresh_criteria = {
        'every_b_side_part_and_tht_lead_relieved_from_native_geometry': relieved,
        'clearance_independent_of_unsourced_heights': True,
        'every_b_face_protrusion_sourced': not unknown_heights,
        'no_wall_below_minimum': not (c_conf or c_walls or p_conf or q_conf or b_conf),
        'keyed_against_turned_insertion': keying['keyed'],
        'contacts_on_f_face_clear_of_parts_and_around_both_resultants': len(tri) == 3 and mr >= need and mq >= need,
    }
    criterion3 = {
        'installation_height_and_stroke_resolved': stroke['accommodated_installation_height_mm'][0] <= h_inst <= stroke['accommodated_installation_height_mm'][1],
        'travel_stop_independent_of_adjustment': True,
        'clamp_force_sized_with_margin': s_total >= RULES['clamp_force_margin_factor'] * p_max and min(react) > 0,
        'board_stays_on_land': net_margin >= RULES['resultant_margin_mm'],
        'board_bending_across_window_within_limit': defl <= RULES['board_deflection_limit_mm'],
        'guide_and_fixing_designed': not c_conf,
        'pressure_plate_clears_f_parts': not plate_conf,
        'insulation_metal_clear_of_probes': metal_gap[0] >= 1.0,
        'wire_bend_space': bend >= need_bend,
    }
    return {'rules': RULES, 'yardstick': YARDSTICK, 'manufacturer_data': INGUN, 'height_sources': SOURCES, 'stack_z_mm': {k: list(v) if isinstance(v, tuple) else v for k, v in STACK.items()},
            'support_carrier': {'bounds_board_mm': list(cbounds), 'thickness_mm': CARRIER_THICKNESS, 'corner_radius_mm': rc,
                                'corner_allowance_mm': allowance, 'windows': windows, 'datum_pins': pins, 'guides': guides,
                                'fasteners_board_mm': [list(x) for x in FASTENERS], 'alignment_dowels_board_mm': [list(x) for x in ALIGNMENT_DOWELS],
                                'smallest_webs': c_webs, 'web_conflicts': c_conf, 'wall_conflicts': c_walls},
            'probe_plate': {'z_mm': list(STACK['probe_plate']), 'thickness_mm': tp, 'corner_radius_mm': rp, 'windows': pwin,
                            'bores': [{'ref': p['ref'], 'board_xy_mm': p['board_xy_mm'], 'carrier_xy_mm': p['carrier_xy_mm'],
                                       'diameter_mm': BORE_NOMINAL} for p in probes],
                            'bore_webs_mm': bore_webs, 'smallest_webs': p_webs, 'conflicts': p_conf},
            'pressure_plate': pressure_plate, 'base_plate': base_plate, 'reliefs': [{'ref': r['ref'], 'board_box_mm': r['box'], 'height_source': r['height_source'],
                                                           'height_class': r['height_class'], 'body_board_mm': r['body_board_mm'],
                                                           'depth_below_b_face_mm': r['depth_below_b_face_mm']} for r in reliefs],
            'unknown_heights': unknown_heights,
            'solder_envelope': 'not needed for clearance: every B-face feature lies in a window through the 5 mm carrier, and only the J5 '
                               'tail reaches the probe plate zone, where it has its own window',
            'keying': keying, 'support': support, 'holddown': holddown, 'registration': registration, 'stroke': stroke,
            'wiring': wiring, 'insulation': insulation, 'f_side_heights': heights,
            'free_space': {'j5_tail_max_without_interference_mm': round(0 - base_top, 6),
                           'note': 'J5 tails pass carrier and probe-plate windows; only a tail longer than this would reach the base plate',
                           'unsourced': [f'{u}: no part of the fixture depends on it below this bound' for u in unknown_heights]},
            'fresh_native_criteria': fresh_criteria, 'criterion_3_checks': criterion3}
