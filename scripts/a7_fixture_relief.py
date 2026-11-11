"""Digital design of the A7 B-side SWD carrier, derived from native geometry and recorded sources.

Inputs: the validated native fixture geometry record (KiCad pad copper and courtyard boxes of the
authoritative PCB), the engineering population list, the INGUN probe/receptacle documents recorded in
engineering/a7/fixture/sources.json, and component data already recorded in the component evidence.

Basis (coordinator decision, option B): the minimum FR-4 wall is derived from the receptacle and probe
manufacturer data (1.27 mm grid with 0.98-1.00 mm FR-4 mounting holes leaves 0.27 mm between two holes);
machining, board and probe position tolerances are closed by explicit acceptance-measurement
requirements, not by a selected fabricator. Every relief is a through-cut, so no clearance depends on
component body or solder-fillet height. Clearances and allocations marked PROJECT-CHOICE are design
values, not measured results. Nothing here is a fit, contact or manufacturing approval.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POPULATION = ROOT / 'engineering/a7/procurement/population.csv'

BOARD = (0.0, 0.0, 16.2, 62.9)
CARRIER_BOARD_X = (-4.4, 20.6)  # carrier footprint in board X (B view: carrier x = 16.2 - board x)
CARRIER_Y = (20.0, 66.0)        # extends past the 62.9 mm board edge to carry the Y datum stop
CARRIER_THICKNESS = 5.0
BORE_NOMINAL = 0.99
BORE_MAX = 1.00

INGUN = {
    'receptacle': {'id': 'sources.json#receptacle', 'mpn': 'KS-050 E08 V-30',
                   'sha256': 'bc016b5934c94f39c638c60416cca8d74e30e17870ae94d02f5022a8c42992b1',
                   'facts': {'mounting_hole_fr4_mm': [0.98, 1.0], 'outer_diameter_mm': 0.95, 'collar_diameter_mm': 1.04,
                             'collar_position_mm': 7.9, 'total_length_mm': 40.6, 'press_ring': True},
                   'locator': 'page 1/1: Mounting hole, General data, Mechanical data; linked drawing sources.json#receptacle-0.png '
                              '(Ø0.96 body, Ø1.04 collar 7.9 from the probe end, 40.64 overall)'},
    'probe': {'id': 'sources.json#probe', 'mpn': 'GKS-050 214 050 A 1000',
              'facts': {'grid_mm': 1.27, 'tip_diameter_mm': 0.5, 'spring_preload_N': 0.44, 'working_stroke_mm': 4.3,
                        'force_at_working_stroke_N': 1.0, 'maximum_stroke_mm': 6.35},
              'locator': 'page 1/2: General data (Grid), Mechanical data, Tip style data'},
    'force_graph': {'id': 'sources.json#probe-4.png', 'sha256': 'e3de0b0b503cd1c09102fcb2e740a53f50671acc5cb559a2b38051b1eb37396c',
                    'facts': {'force_at_maximum_stroke_N': 1.27},
                    'locator': 'linear force-stroke line, 0.44 N at 0 to 1.0 N at 4.3 mm; value at 6.35 mm read from the graph'},
}
MIN_WALL = round(INGUN['probe']['facts']['grid_mm'] - INGUN['receptacle']['facts']['mounting_hole_fr4_mm'][1], 6)

RULES = {
    'minimum_fr4_wall_mm': MIN_WALL,
    'minimum_fr4_wall_basis': 'SOURCE_DERIVED: INGUN 1.27 mm grid minus the 1.00 mm maximum FR-4 mounting hole; applied to every '
                              'carrier wall (bore-to-cut, cut-to-cut, cut-to-edge, pin-to-cut)',
    'smd_outline_clearance_mm': 0.2,
    'smd_outline_clearance_min_near_bore_mm': 0.15,
    'tht_copper_clearance_mm': 0.3,
    'datum_pin_diameter_mm': 2.0,
    'datum_pin_height_above_carrier_mm': 1.0,
    'holddown_pin_diameter_mm': 1.5,
    'holddown_f_side_clearance_mm': 0.3,
    'support_grid_mm': 0.1,
    'support_radius_around_probe_mm': 3.0,
    'confidence': 'PROJECT-CHOICE design values except the minimum wall; not machining tolerances, fit results or approvals',
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


def _box_gap(a, b):
    return math.hypot(max(b[0] - a[2], a[0] - b[2], 0.0), max(b[1] - a[3], a[1] - b[3], 0.0))


def _in_box(b, x, y):
    return b[0] <= x <= b[2] and b[1] <= y <= b[3]


def population(path=POPULATION):
    rows = [line for line in path.read_text().splitlines() if not line.startswith('ENGINEERING ONLY')]
    return {r['ref']: r for r in csv.DictReader(rows) if r['board'] == 'controller'}


def _smd_box(f, probes):
    """Outline (native pads + sourced max body) plus clearance; a side facing a bore may shrink to keep the minimum wall."""
    rot = round(f['rotation_deg']) % 180
    if abs(f['rotation_deg'] - round(f['rotation_deg'])) > 1e-6 or rot % 90:
        raise ValueError(f"{f['ref']}: non-orthogonal rotation; body outline box not derived")
    hl, hw = R0603['body_length_max_mm'] / 2, R0603['body_width_max_mm'] / 2
    dx, dy = (hl, hw) if rot == 0 else (hw, hl)
    cx, cy = f['at_mm']
    o = [cx - dx, cy - dy, cx + dx, cy + dy]
    for q in f['pads']:
        b = q['bbox_mm']
        o = [min(o[0], b[0]), min(o[1], b[1]), max(o[2], b[2]), max(o[3], b[3])]
    c = [RULES['smd_outline_clearance_mm']] * 4  # x0, y0, x1, y1 sides
    lo = RULES['smd_outline_clearance_min_near_bore_mm']
    for p in probes:
        px, py = p['board_xy_mm']
        for _ in range(4):
            box = [o[0] - c[0], o[1] - c[1], o[2] + c[2], o[3] + c[3]]
            short = MIN_WALL - (_box_point_dist(box, (px, py)) - BORE_MAX / 2)
            if short <= 1e-9:
                break
            side = 0 if px < box[0] else 2 if px > box[2] else None
            if side is None or (py < box[1] or py > box[3]):
                side = 1 if py < box[1] else 3 if py > box[3] else side
            if side is None:
                break
            c[side] = max(lo, round(c[side] - short, 6))
            if c[side] == lo:
                break
    return [o[0] - c[0], o[1] - c[1], o[2] + c[2], o[3] + c[3]], c


def _components(cuts):
    comp = list(range(len(cuts)))

    def find(i):
        while comp[i] != i:
            comp[i] = comp[comp[i]]
            i = comp[i]
        return i
    for i in range(len(cuts)):
        for j in range(i + 1, len(cuts)):
            if _box_gap(cuts[i]['board_box_mm'], cuts[j]['board_box_mm']) <= 0:
                comp[find(i)] = find(j)
    return [find(i) for i in range(len(cuts))]


def _bridges(cuts):
    """Join cut groups whose wall is under the minimum: a strip over the shared span, or the corner gap square."""
    added = []
    for _ in range(50):
        groups = _components(cuts + added)
        allc = cuts + added
        fix = None
        for i in range(len(allc)):
            for j in range(i + 1, len(allc)):
                if groups[i] == groups[j]:
                    continue
                a, b = allc[i]['board_box_mm'], allc[j]['board_box_mm']
                gap = _box_gap(a, b)
                if 0 < gap < MIN_WALL:
                    x0, x1 = (a[2], b[0]) if a[2] <= b[0] else (b[2], a[0]) if b[2] <= a[0] else (max(a[0], b[0]), min(a[2], b[2]))
                    y0, y1 = (a[3], b[1]) if a[3] <= b[1] else (b[3], a[1]) if b[3] <= a[1] else (max(a[1], b[1]), min(a[3], b[3]))
                    fix = {'ref': f"bridge {allc[i]['ref']}+{allc[j]['ref']}", 'kind': 'through', 'basis': f'merges a {gap:.3f} mm wall below the minimum',
                           'board_box_mm': [round(v, 6) for v in (x0, y0, x1, y1)]}
                    break
            if fix:
                break
        if not fix:
            return added
        fix['carrier_box_mm'] = _to_carrier(fix['board_box_mm'])
        fix['depth_mm'] = CARRIER_THICKNESS
        added.append(fix)
    raise ValueError('wall merging did not converge')


def design(geometry: dict, probes: list[dict], pop: dict | None = None) -> dict:
    """Carrier cuts, walls, datums, keying, support, hold-down, registration and stroke from native geometry and sources."""
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
            outline, clear = _smd_box(f, probes)
            box = _clip(outline)
            if box:
                reliefs.append({'ref': ref, 'kind': 'through', 'basis': 'native pad copper boxes united with the sourced maximum body outline '
                                '(solder wets only copper); through-cut, so body and fillet height do not constrain the carrier',
                                'board_box_mm': box, 'carrier_box_mm': _to_carrier(box), 'side_clearance_mm': clear,
                                'height_source': 'R0603', 'height_class': 'SOURCE_DERIVED', 'depth_mm': CARRIER_THICKNESS})
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

    for c in reliefs:
        b, opened = c['board_box_mm'], []
        for k, edge, gap in ((1, CARRIER_Y[0], b[1] - CARRIER_Y[0]), (3, CARRIER_Y[1], CARRIER_Y[1] - b[3]),
                             (0, CARRIER_BOARD_X[0], b[0] - CARRIER_BOARD_X[0]), (2, CARRIER_BOARD_X[1], CARRIER_BOARD_X[1] - b[2])):
            if 0 < gap < MIN_WALL:
                b[k] = edge
                opened.append(round(gap, 6))
        if opened:
            c['opened_to_carrier_edge'] = f'edge wall {min(opened):.3f} mm below the minimum: the cut is opened through the carrier edge'
            c['carrier_box_mm'] = _to_carrier(b)
    bridges = _bridges(reliefs)
    cuts = reliefs + bridges
    r = RULES['datum_pin_diameter_mm'] / 2
    pins = [{'id': 'X1', 'role': 'X datum on the board x = 16.2 edge', 'board_xy_mm': [round(BOARD[2] + r, 6), 24.0]},
            {'id': 'X2', 'role': 'X datum on the board x = 16.2 edge', 'board_xy_mm': [round(BOARD[2] + r, 6), 56.0]},
            {'id': 'Y1', 'role': 'Y datum on the board y = 62.9 edge', 'board_xy_mm': [8.1, round(BOARD[3] + r, 6)]}]
    for pin in pins:
        pin['carrier_xy_mm'] = [round(16.2 - pin['board_xy_mm'][0], 6), pin['board_xy_mm'][1]]

    webs, conflicts = [], []
    holes = [(p['ref'], p['board_xy_mm'], BORE_MAX / 2) for p in probes] + [(pin['id'], pin['board_xy_mm'], r) for pin in pins]
    for name, xy, rad in holes:
        for c in cuts:
            web = round(_box_point_dist(c['board_box_mm'], xy) - rad, 6)
            if web < 2.0:
                webs.append({'hole': name, 'cut': c['ref'], 'web_mm': web})
            if web < MIN_WALL:
                conflicts.append(f'{name} hole to {c["ref"]} web {web:.3f} mm < {MIN_WALL} mm')
        for edge in (xy[1] - rad - CARRIER_Y[0], CARRIER_Y[1] - xy[1] - rad, xy[0] - rad - CARRIER_BOARD_X[0], CARRIER_BOARD_X[1] - xy[0] - rad):
            if edge < MIN_WALL:
                conflicts.append(f'{name} hole to carrier edge web {edge:.3f} mm < {MIN_WALL} mm')
    for i, (n1, a, ra) in enumerate(holes):
        for n2, b, rb in holes[i + 1:]:
            if math.dist(a, b) - ra - rb < MIN_WALL:
                conflicts.append(f'{n1}/{n2} hole web {math.dist(a, b) - ra - rb:.3f} mm < {MIN_WALL} mm')
    groups = _components(cuts)
    walls = []
    for i in range(len(cuts)):
        for j in range(i + 1, len(cuts)):
            gap = _box_gap(cuts[i]['board_box_mm'], cuts[j]['board_box_mm'])
            if groups[i] != groups[j] and 0 < gap < MIN_WALL:
                walls.append(f"{cuts[i]['ref']}/{cuts[j]['ref']} wall {gap:.3f} mm")
        A = cuts[i]['board_box_mm']
        for edge in (A[1] - CARRIER_Y[0], CARRIER_Y[1] - A[3], A[0] - CARRIER_BOARD_X[0], CARRIER_BOARD_X[1] - A[2]):
            if 0 < edge < MIN_WALL:
                walls.append(f"{cuts[i]['ref']}/carrier edge wall {edge:.3f} mm")

    # keying: the board turned 180 degrees in plane (B face still down) must not seat on the carrier
    turned = []
    for c in reliefs:
        if c['height_source'] != 'PJ-324M':
            continue
        b = c['board_box_mm']
        tb = [16.2 - b[2], 62.9 - b[3], 16.2 - b[0], 62.9 - b[1]]
        cx, cy = (tb[0] + tb[2]) / 2, (tb[1] + tb[3]) / 2
        on_land = _in_box(_clip_strict(BOARD), cx, cy) and not any(_in_box(k['board_box_mm'], cx, cy) for k in cuts)
        turned.append({'lead': c['ref'], 'turned_centre_mm': [round(cx, 6), round(cy, 6)], 'lands_on_carrier': on_land})
    for f in sorted(geometry['footprints'], key=lambda f: f['ref']):
        if f['side'] != 'B' or f['ref'] in probe_refs:
            continue
        for pd in f['pads']:
            b = pd['bbox_mm']
            cx, cy = 16.2 - (b[0] + b[2]) / 2, 62.9 - (b[1] + b[3]) / 2
            on_land = _in_box(_clip_strict(BOARD), cx, cy) and not any(_in_box(k['board_box_mm'], cx, cy) for k in cuts)
            turned.append({'lead': f"{f['ref']}.{pd['number']}", 'turned_centre_mm': [round(cx, 6), round(cy, 6)],
                           'lands_on_carrier': on_land})
    blocking = [t['lead'] for t in turned if t['lands_on_carrier']]
    keying = {'method': 'B-face features stand proud of the B face: PJ-324M terminals (nominal 1.6 mm, MANUFACTURER_MIRROR) and the '
                        'soldered R0603 terminations (body up to 0.55 mm, SOURCE_DERIVED). In the correct pose all of them fall into '
                        'through-cuts; turned 180 degrees in plane, the listed centres land on solid carrier, hold the board off the '
                        'land and the datum pins, and the probes miss the test pads. Face-down insertion is excluded by the F-side jacks.',
              'turned_pose_features': turned, 'blocking_features': blocking, 'keyed': len(blocking) >= 3,
              'acceptance_requirement': 'trial-insert the board turned 180 degrees: it must not seat (visible gap at the datum pins)'}

    # support land and hold-down points over land, clear of F-side parts
    g = RULES['support_grid_mm']
    y_hi = min(CARRIER_Y[1], BOARD[3])
    nx, ny = round(16.2 / g), round((y_hi - CARRIER_Y[0]) / g)
    land = total = 0
    near = {p['ref']: [0, 0] for p in probes}

    def solid(x, y):
        return not any(_in_box(k['board_box_mm'], x, y) for k in cuts) and all(math.dist((x, y), p['board_xy_mm']) > BORE_MAX / 2 for p in probes)
    for i in range(nx):
        x = (i + 0.5) * g
        for j in range(ny):
            y = CARRIER_Y[0] + (j + 0.5) * g
            free = solid(x, y)
            total += 1
            land += free
            for p in probes:
                if math.dist((x, y), p['board_xy_mm']) <= RULES['support_radius_around_probe_mm']:
                    near[p['ref']][1] += 1
                    near[p['ref']][0] += free
    fside = [f['courtyard_bbox_mm']['F'] for f in geometry['footprints'] if f['side'] == 'F' and f['courtyard_bbox_mm'].get('F')]
    hr = RULES['holddown_pin_diameter_mm'] / 2
    cx = sum(p['board_xy_mm'][0] for p in probes) / len(probes)
    cy = sum(p['board_xy_mm'][1] for p in probes) / len(probes)
    cands = []
    step = 0.1
    for i in range(round(16.2 / step) + 1):
        x = round(i * step, 6)
        for j in range(round((y_hi - CARRIER_Y[0]) / step) + 1):
            y = round(CARRIER_Y[0] + j * step, 6)
            if x - hr < 0 or x + hr > 16.2:
                continue
            if any(_box_point_dist(b, (x, y)) < hr + RULES['holddown_f_side_clearance_mm'] for b in fside):
                continue
            ring = [(x + hr * math.cos(a * math.pi / 4), y + hr * math.sin(a * math.pi / 4)) for a in range(8)] + [(x, y)]
            if all(solid(px, py) for px, py in ring):
                cands.append((round(math.dist((x, y), (cx, cy)), 6), x, y))
    cands.sort()
    chosen = []
    for d, x, y in cands:
        if all(math.dist((x, y), c) >= 2.0 for c in chosen):
            chosen.append((x, y))
        if len(chosen) == 3:
            break
    f_max = INGUN['force_graph']['facts']['force_at_maximum_stroke_N']
    f_work = INGUN['probe']['facts']['force_at_working_stroke_N']
    n = len(probes)
    holddown = {'points_board_mm': [[x, y] for x, y in chosen],
                'pin_diameter_mm': RULES['holddown_pin_diameter_mm'],
                'rule': 'pressure pins on the F side, clear of every native F courtyard by 0.3 mm, each over solid carrier land so the '
                        'clamp load passes straight through the board into the carrier; nothing presses on jack bodies or solder joints',
                'probe_force_total_N': {'working_stroke': round(n * f_work, 6), 'maximum_stroke': round(n * f_max, 6)},
                'required_clamp_force_N': round(n * f_max, 6),
                'required_clamp_force_basis': 'all five probes at the 6.35 mm maximum stroke (graph value); the clamp must exceed it so the '
                                              'board stays on the carrier land at any stroke',
                'mechanism': None, 'mechanism_status': 'NOT_SELECTED (owner/supplier choice)'}
    support = {'method': f'grid {g} mm over the board outline inside the carrier (board X 0-16.2, Y {CARRIER_Y[0]}-{y_hi})',
               'land_fraction': round(land / total, 4),
               'land_fraction_within_radius_of_probe': {k: round(a / b, 4) for k, (a, b) in near.items()},
               'load_path': 'clamp pins (F side) -> board -> solid carrier land under each pin -> carrier; probe forces push the board '
                            'against the clamp only within the clamped, supported area',
               'scope': 'geometric layout only; no deflection analysis (the clamp points sit over land, so the board is not loaded in bending '
                        'between a clamp point and its support)'}

    alloc = {'board_edge_to_test_pad_mm': 0.10, 'datum_contact_mm': 0.0, 'carrier_pin_to_bore_position_mm': 0.05,
             'probe_tip_lateral_mm': 0.07}
    budget = round((1.0 - INGUN['probe']['facts']['tip_diameter_mm']) / 2, 6)
    registration = {
        'datums': 'board pushed by the clamp/bias against X1, X2 (x = 16.2 edge) and Y1 (y = 62.9 edge); spring bias makes the datum '
                  'contact clearance zero',
        'radial_budget_mm': budget,
        'allocation_mm': alloc, 'allocation_class': 'PROJECT-CHOICE, each closed by the acceptance measurement below',
        'worst_case_margin_mm': round(budget - sum(alloc.values()), 6),
        'acceptance_requirements': [
            'each board: TP1-TP5 pad centres measured from the x = 16.2 and y = 62.9 edges; radial deviation from the design '
            'position <= 0.10 mm, else the board is not tested in this fixture',
            'carrier: bore centres measured from the datum pin contact lines; radial deviation <= 0.05 mm; bores 0.98-1.00 mm; '
            'every cut edge within +/-0.05 mm of the design line; walls not below 0.27 mm',
            'installed probes: tip lateral offset from the bore axis at the working stroke <= 0.07 mm',
        ]}
    stroke = {
        'travel_stop': 'the board B face seats on the solid carrier land, which is independent of the probe installation height',
        'set_installation_height': 'press-ring receptacle pressed to the depth that leaves the probe tip 4.3 mm above the carrier top '
                                   '(recommended working stroke) with the board absent',
        'stroke_window_mm': [0.0, INGUN['probe']['facts']['maximum_stroke_mm']],
        'acceptance_requirement': 'each probe: free tip height above the carrier top 4.3 +/-0.3 mm (stroke 4.0-4.6 mm, inside 0-6.35 mm)',
        'force_per_probe_N': {'at_4.0_mm': round(0.44 + (1.0 - 0.44) / 4.3 * 4.0, 3), 'at_4.6_mm': round(0.44 + (1.0 - 0.44) / 4.3 * 4.6, 3)},
        'force_basis': 'linear INGUN force-stroke graph (0.44 N preload, 1.0 N at 4.3 mm)'}
    free_space = {'below_carrier': 'every relief is a through-cut, so nothing on the B face touches the carrier; a part longer than the '
                                   '5 mm carrier continues into the space below it, which the undesigned base must keep free',
                  'unsourced': [f'{u}: the carrier does not depend on it, the base below the carrier does' for u in unknown_heights]}
    relieved = all(any(_inside(want, c['board_box_mm']) for c in cuts)
                   for f in geometry['footprints'] if f['ref'] not in probe_refs for pd in f['pads']
                   if (f['side'] == 'B' or pd['attribute'] == 'PTH') for want in [_clip(pd['bbox_mm'])] if want)
    fresh_criteria = {
        'every_b_side_part_and_tht_lead_relieved_from_native_geometry': relieved,
        'clearance_independent_of_unsourced_heights': all(c['depth_mm'] == CARRIER_THICKNESS for c in cuts),
        'every_b_face_protrusion_sourced': not unknown_heights,
        'no_wall_below_sourced_minimum': not conflicts and not walls,
        'keyed_against_turned_insertion': keying['keyed'],
        'holddown_points_over_land_clear_of_f_parts': len(chosen) == 3,
    }
    return {'rules': RULES, 'manufacturer_data': INGUN, 'height_sources': SOURCES, 'reliefs': reliefs, 'bridges': bridges,
            'datum_pins': pins, 'hole_to_cut_webs_below_2mm': sorted(webs, key=lambda w: (w['web_mm'], w['hole'], w['cut'])),
            'web_conflicts': conflicts, 'relief_wall_conflicts': walls, 'unknown_heights': unknown_heights,
            'solder_envelope': 'not needed for clearance: every relief is a through-cut sized from native copper and the sourced body outline',
            'keying': keying, 'support': support, 'holddown': holddown, 'registration': registration, 'stroke': stroke,
            'free_space': free_space, 'fresh_native_criteria': fresh_criteria}


def _inside(inner, outer):
    return outer[0] <= inner[0] + 1e-9 and outer[1] <= inner[1] + 1e-9 and inner[2] <= outer[2] + 1e-9 and inner[3] <= outer[3] + 1e-9


def _clip_strict(box):
    return [box[0], max(box[1], CARRIER_Y[0]), box[2], min(box[3], CARRIER_Y[1])]
