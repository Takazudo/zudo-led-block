#!/usr/bin/env python3
"""A7 SWD fixture assembly model and interference check (CadQuery 2.7.0); a digital check, never a fit approval.

Builds every fixture part, the hardware envelopes and the board (with F-side part boxes from the recorded heights and
B-face bodies and leads from the relief design) in board coordinates: x, y as on the PCB, z up from the board B face.
Threads are modelled at the major diameter and press fits line to line, so a designed joint touches without overlap.
Through-hole leads are modelled at their full sourced length below the seating plane (a bound for any board thickness).
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

TOL_MM3 = 1e-3  # common-volume threshold for an interference; OCC boolean noise on touching faces stays far below it


CADQUERY_VERSION = '2.7.0'
SHCS_HEAD_MAX = 5.68  # TR Fastenings SO12CS drawing (tr-so12cs), M3 head diameter max


def model_inputs(relief, geometry_sha256):
    """Everything the assembly model is built from: the design, this module's code, the native record and the CAD kernel."""
    return {'design_sha256': hashlib.sha256(json.dumps(relief, sort_keys=True).encode()).hexdigest(),
            'assembly_code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'native_geometry_sha256': geometry_sha256, 'cadquery': CADQUERY_VERSION}


def design_digest(relief, geometry_sha256):
    return hashlib.sha256(json.dumps(model_inputs(relief, geometry_sha256), sort_keys=True).encode()).hexdigest()


def _cq():
    import cadquery as cq
    if cq.__version__ != CADQUERY_VERSION:
        raise ValueError('CadQuery 2.7.0 required')
    return cq


def _box(cq, b, z0, z1):
    return cq.Workplane('XY').box(b[2] - b[0], b[3] - b[1], z1 - z0, centered=False).translate((b[0], b[1], z0)).val()


def _cyl(cq, xy, d, z0, z1):
    return cq.Workplane('XY').center(*xy).circle(d / 2).extrude(z1 - z0).translate((0, 0, z0)).val()


def _tube(cq, xy, od, idia, z0, z1):
    return cq.Workplane('XY').center(*xy).circle(od / 2).circle(idia / 2).extrude(z1 - z0).translate((0, 0, z0)).val()


def _hex(cq, xy, af, z0, z1, bore=None):
    w = cq.Workplane('XY').center(*xy).polygon(6, af / math.cos(math.pi / 6))
    if bore:
        w = w.circle(bore / 2)
    return w.extrude(z1 - z0).translate((0, 0, z0)).val()


def _cone(cq, xy, d_big, d_small, z_big, z_small):
    h = abs(z_small - z_big)
    s = cq.Solid.makeCone(d_big / 2, d_small / 2, h, cq.Vector(xy[0], xy[1], z_big), cq.Vector(0, 0, 1 if z_small > z_big else -1))
    return s


def _member(cq, b, r, rounded, z0, z1):
    """Member rectangle with the flagged corners rounded (BL, BR, TL, TR), extruded z0..z1."""
    s = _box(cq, b, z0, z1)
    for (cx, cy, sx, sy), flag in zip(((b[0], b[1], 1, 1), (b[2], b[1], -1, 1), (b[0], b[3], 1, -1), (b[2], b[3], -1, -1)), rounded):
        if not flag:
            continue
        sq = [min(cx, cx + sx * r), min(cy, cy + sy * r), max(cx, cx + sx * r), max(cy, cy + sy * r)]
        s = s.cut(_box(cq, sq, z0, z1)).fuse(_cyl(cq, (cx + sx * r, cy + sy * r), 2 * r, z0, z1))
    return s.clean()


def _window_cutter(cq, w, z0, z1):
    out = None
    for m in w['members']:
        s = _member(cq, m['box_board_mm'], w['corner_radius_mm'], m['rounded_corners'], z0, z1)
        out = s if out is None else out.fuse(s)
    return out.clean()


def _plate(cq, bounds, z0, z1, windows=(), holes=(), extra_cuts=()):
    s = _box(cq, bounds, z0, z1)
    for w in windows:
        s = s.cut(_window_cutter(cq, w, z0 - 1, z1 + 1))
    for xy, d in holes:
        s = s.cut(_cyl(cq, xy, d, z0 - 1, z1 + 1))
    for c in extra_cuts:
        s = s.cut(c)
    return s.clean()


def build(relief, pads, geometry, rl):
    """Return [(name, group, solid)] for the whole fixture with the board clamped in it."""
    cq = _cq()
    st = relief['stack_z_mm']
    R = relief['rules']
    sc, pp, pr = relief['support_carrier'], relief['probe_plate'], relief['pressure_plate']
    cb = sc['bounds_board_mm']
    fasteners, dowels = sc['fasteners_board_mm'], sc['alignment_dowels_board_mm']
    guides = sc['guides']
    m3c, dd, pin_d = R['m3_clearance_hole_mm'], R['alignment_dowel_diameter_mm'], R['datum_pin_diameter_mm']
    rec = relief['manufacturer_data']['receptacle']['facts']
    probe = relief['manufacturer_data']['probe']['facts']
    stroke = relief['stroke']
    parts = []

    def add(name, group, solid):
        parts.append((name, group, solid))

    c0, c1 = st['support_carrier']
    csk_d = R['m3_countersink_diameter_mm']
    add('support_carrier', 'plate', _plate(cq, cb, c0, c1, sc['windows'],
                                           [(q['board_xy_mm'], pin_d) for q in sc['datum_pins']] + [(xy, m3c) for xy in fasteners]
                                           + [(xy, dd) for xy in dowels] + [(g['board_xy_mm'], m3c) for g in guides],
                                           [_cone(cq, xy, csk_d, 3.0, c1, c1 - (csk_d - 3.0) / 2) for xy in fasteners]))
    p0, p1 = st['probe_plate']
    add('probe_plate', 'plate', _plate(cq, cb, p0, p1, pp['windows'],
                                       [(b['board_xy_mm'], b['diameter_mm']) for b in pp['bores']] + [(xy, m3c) for xy in fasteners]
                                       + [(xy, dd) for xy in dowels]))
    b0, b1 = st['base_plate']
    slot = relief['wiring']['tie_slot_board_mm']
    slot_w = {'members': [{'box_board_mm': slot, 'rounded_corners': [True] * 4}], 'corner_radius_mm': rl.corner_radius(b1 - b0)}
    csk = [_cone(cq, xy, 6.0, 3.0, b0, b0 + 1.5) for xy in fasteners]
    add('base_plate', 'plate', _plate(cq, cb, b0, b1, [slot_w], [(xy, m3c) for xy in fasteners], csk))
    q0, q1 = pr['z_mm']
    notch = list(pr['j5_notch_board_mm'])
    notch[3] += pr['corner_radius_mm']  # open through the plate edge
    notch_w = {'members': [{'box_board_mm': notch, 'rounded_corners': [True, True, False, False]}], 'corner_radius_mm': pr['corner_radius_mm']}
    contacts = relief['holddown']['contacts_board_mm']
    add('pressure_plate', 'plate', _plate(cq, pr['outline_board_mm'], q0, q1, [notch_w],
                                          [(g['board_xy_mm'], pr['guide_hole_diameter_mm']) for g in guides]
                                          + [(c, R['contact_diameter_mm']) for c in contacts]))

    # plate stack hardware (threads at major diameter)
    for i, xy in enumerate(fasteners, 1):
        add(f'F{i} M3x8 countersunk screw', 'hardware', _cone(cq, xy, csk_d, 3.0, c1, c1 - (csk_d - 3.0) / 2).fuse(_cyl(cq, xy, 3.0, c1 - 8, c1 - (csk_d - 3.0) / 2)))
        add(f'F{i} M3 F-F hex spacer 6', 'hardware', _hex(cq, xy, 5.5, st['plate_gap_spacers'][0], st['plate_gap_spacers'][1], 3.0))
        # set 4 mm into the base standoff and 2 mm into the spacer, leaving a 1 mm gap to the 8 mm countersunk screw above
        add(f'F{i} M3x12 stud', 'hardware', _cyl(cq, xy, 3.0, p0 - 4, p1 + 2))
        add(f'F{i} M3 F-F hex standoff 35', 'hardware', _hex(cq, xy, 5.5, st['base_standoffs'][0], st['base_standoffs'][1], 3.0))
        add(f'F{i} M3x8 countersunk screw (base)', 'hardware', _cone(cq, xy, 6.0, 3.0, b0, b0 + 1.5).fuse(_cyl(cq, xy, 3.0, b0 + 1.5, b0 + 8)))
    for i, xy in enumerate(dowels, 1):
        add(f'D{i} dowel 2x16', 'hardware', _cyl(cq, xy, dd, p0, p0 + 16.0))
    for q in sc['datum_pins']:
        add(f"{q['id']} datum pin 2x6", 'hardware', _cyl(cq, q['board_xy_mm'], pin_d, c0, c1 + R['datum_pin_height_above_carrier_mm']))
    g_top = st['guide_standoff_top']
    for g in guides:
        xy = g['board_xy_mm']
        add(f"{g['id']} M3x8 socket head screw", 'hardware', _cyl(cq, xy, 3.0, c0, c1 + 3).fuse(_cyl(cq, xy, SHCS_HEAD_MAX, c0 - 3, c0)))
        add(f"{g['id']} M3 F-F hex standoff {g_top - c1:g}", 'hardware', _hex(cq, xy, 5.5, c1, g_top, 3.0))
        add(f"{g['id']} M3 washer DIN 9021", 'hardware', _tube(cq, xy, 9.0, 3.2, g_top, g_top + 0.8))
        add(f"{g['id']} M3x6 socket head screw", 'hardware', _cyl(cq, xy, 3.0, g_top + 0.8 - 6, g_top + 0.8).fuse(_cyl(cq, xy, SHCS_HEAD_MAX, g_top + 0.8, g_top + 3.8)))
        add(f"{g['id']} compression spring envelope", 'hardware', _tube(cq, xy, R['spring_outer_diameter_max_mm'], 6.6, q1, g_top))
    for i, c in enumerate(contacts, 1):
        add(f'C{i} M2x8 nylon contact screw', 'hardware', _cyl(cq, c, 2.0, rl.BOARD_THICKNESS, rl.BOARD_THICKNESS + 8).fuse(
            _cyl(cq, c, 4.0, rl.BOARD_THICKNESS + 8, rl.BOARD_THICKNESS + 9.3)))
        add(f'C{i} M2 nylon nut', 'hardware', _hex(cq, c, 4.0, q1, q1 + 1.6, 2.0))

    # receptacles and probes (probes compressed to the working stroke against the B face)
    top, bottom = stroke['receptacle_top_z_mm'], stroke['receptacle_bottom_z_mm']
    ring = p1 - stroke['press_ring_depth_mm']
    for pad in pads:
        xy = pad['board_xy_mm']
        add(f"{pad['ref']} KS-050 receptacle", 'probe', _cyl(cq, xy, rec['collar_diameter_mm'], p1, top)
            .fuse(_cyl(cq, xy, pp['bores'][0]['diameter_mm'], ring, p1)).fuse(_cyl(cq, xy, rec['outer_diameter_mm'], bottom, ring)))
        add(f"{pad['ref']} GKS-050 probe (compressed envelope)", 'probe', _cyl(cq, xy, probe['barrel_diameter_mm'], top, 0.0))

    # board with F-side part boxes and B-face bodies/leads
    add('controller board', 'board', _box(cq, rl.BOARD, 0.0, rl.BOARD_THICKNESS))
    heights = relief['f_side_heights']
    for f in sorted(geometry['footprints'], key=lambda f: f['ref']):
        if f['side'] == 'F' and f['courtyard_bbox_mm'].get('F'):
            h = heights[f['ref']]['height_mm']
            add(f"{f['ref']} F-side body (courtyard x height)", 'board', _box(cq, f['courtyard_bbox_mm']['F'], rl.BOARD_THICKNESS, rl.BOARD_THICKNESS + h))
    for r in relief['reliefs']:
        depth = r['depth_below_b_face_mm']
        if depth is None:
            raise ValueError(f"{r['ref']}: B-face depth not sourced")
        z0 = -depth
        label = 'B-face body/lead'
        add(f"{r['ref']} {label}", 'board', _box(cq, r['body_board_mm'], z0, 0.0))
    return parts


CLEARANCE_PAIRS = [
    ('B-face bodies and leads to support carrier', lambda n, g: g == 'board' and 'B-face' in n, lambda n, g: n == 'support_carrier'),
    ('J5 leads at their full sourced tail length to carrier and probe plate', lambda n, g: n.startswith('J5.'), lambda n, g: n in ('support_carrier', 'probe_plate')),
    ('probes and receptacles to support carrier', lambda n, g: g == 'probe', lambda n, g: n == 'support_carrier'),
    ('receptacle tails to base plate', lambda n, g: 'receptacle' in n, lambda n, g: n == 'base_plate'),
    ('F-side bodies to pressure plate', lambda n, g: 'F-side' in n, lambda n, g: n == 'pressure_plate'),
    ('F-side bodies to contact screws', lambda n, g: 'F-side' in n, lambda n, g: 'contact screw' in n),
    ('board to guide standoffs and springs', lambda n, g: g == 'board', lambda n, g: 'G' in n.split()[0] and ('standoff' in n or 'spring' in n)),
    ('metal hardware to probes and receptacles', lambda n, g: g == 'hardware' and 'nylon' not in n, lambda n, g: g == 'probe'),
]


DESIGNED_CONTACTS = [
    ('board B face seats on the support carrier', lambda n: n == 'controller board', lambda n: n == 'support_carrier'),
    ('nylon contact on the F face', lambda n: n == 'controller board', lambda n: 'contact screw' in n),
    ('probe tip on its test pad (working stroke)', lambda n: n == 'controller board', lambda n: 'GKS-050' in n),
    ('board edge on a datum pin', lambda n: n == 'controller board', lambda n: 'datum pin' in n),
]


def check(parts):
    """Pairwise common volume between every two solids of different groups (and plate/hardware pairs within a group)."""
    cq = _cq()
    boxes = [s.BoundingBox() for _, _, s in parts]
    interferences, touching = [], 0
    for i in range(len(parts)):
        for j in range(i + 1, len(parts)):
            (ni, gi, si), (nj, gj, sj) = parts[i], parts[j]
            if gi == gj == 'board':
                continue  # courtyard boxes of neighbouring parts may overlap; the board itself is not checked here
            a, b = boxes[i], boxes[j]
            if a.xmin > b.xmax or b.xmin > a.xmax or a.ymin > b.ymax or b.ymin > a.ymax or a.zmin > b.zmax or b.zmin > a.zmax:
                continue
            v = si.intersect(sj).Volume()
            if v > TOL_MM3:
                interferences.append({'a': ni, 'b': nj, 'common_volume_mm3': round(v, 4)})
            else:
                touching += 1
    clear = []
    for label, fa, fb in CLEARANCE_PAIRS:
        A = [(n, s) for n, g, s in parts if fa(n, g)]
        B = [(n, s) for n, g, s in parts if fb(n, g)]
        best = min(((sa.distance(sb), na, nb) for na, sa in A for nb, sb in B), default=None)
        clear.append({'pair': label, 'minimum_mm': None if best is None else round(best[0], 4),
                      'between': None if best is None else [best[1], best[2]]})
    contacts = []
    for label, fa, fb in DESIGNED_CONTACTS:
        for na, ga, sa in parts:
            if not fa(na):
                continue
            for nb, gb, sb in parts:
                if fb(nb):
                    d = sa.distance(sb)
                    contacts.append({'contact': label, 'between': [na, nb], 'distance_mm': round(d, 6), 'touching': d < 1e-6})
    del cq
    return interferences, touching, clear, contacts


def export(parts, path):
    cq = _cq()
    asm = cq.Assembly(name='a7_swd_fixture')
    for name, group, solid in parts:
        asm.add(cq.Workplane('XY').add(solid), name=name.replace(' ', '_').replace('(', '').replace(')', '').replace('/', '_'))
    asm.export(str(path), 'STEP')


def summary(parts):
    return [{'name': n, 'group': g, 'volume_mm3': round(s.Volume(), 4)} for n, g, s in parts]
