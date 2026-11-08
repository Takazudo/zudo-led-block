#!/usr/bin/env python3
"""A7 controller board: placement against the R2 mechanical model, staging build, routing hand-off.

The controller lies in the assembly Y-Z plane. Board frame and every envelope follow R2's
engineering/a7/mechanical/placement-envelopes.json (PR #27, f58180a): KiCad top view from the
component face (+X), board_x = assembly Z - 0.2 (0 = front edge at the PMMA), board_y = assembly
Y - 48.5 (0 = top edge). Outline 16.2 x 62.9. F = component face, B = solder face.

Commands:
  place [--check]                 deterministic courtyard packer -> engineering/a7/electronics/controller/placement.json
  check                           courtyard overlap, keep-out and side rules for the committed placement
  build --out DIR --netlist N     (pinned KiCad image) unrouted staging board + Specctra DSN, in an empty DIR outside the repo
  apply --board B --routes R      (pinned KiCad image) add a7_route.py tracks/vias and GND pours to a staging board, refill
  regen-check --raw RAW           normal regeneration --check (schematic, footprints, seed placement) plus the
                                  board placement export --check against fresh native facts in RAW/a7_controller

Board flow (all outside the repository until the result passes DRC): build -> scripts/a7_route.py -> apply,
then the reviewed staging board is copied to the authoritative controller.kicad_pcb.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(REPO / 'scripts'))
import a7_electronics as a7  # noqa: E402
sys.path.pop(0)

PLACEMENT = a7.A7_CTRL / 'placement.json'
BOARD = a7.A7_CTRL / 'controller.kicad_pcb'
BOARD_EXPORT = a7.A7_CTRL / 'board_placement.json'
W, H = 16.2, 62.9
GATE_PROFILE = REPO / 'engineering/a7/verification/native_gate.json'
ENVELOPES = 'engineering/a7/mechanical/placement-envelopes.json (R2, merged in #27)'

ENVELOPE_FILE = REPO / 'engineering/a7/mechanical/placement-envelopes.json'
KEEPOUT_OWNER = {'setting-switch': 'SW1', 'switch-access': 'SW1', 'sh4-header': 'J3', 'led-cable-lane': 'J3',
                 'picoblade-header': 'J5', 'picoblade-tails': 'J5', 'jack-in': 'J1', 'jack-in-leads': 'J1',
                 'jack-thru': 'J2', 'jack-thru-leads': 'J2'}
# Agreed with R2 after its envelopes merged; R2 adopts these from the routed placement export.
KEEPOUT_OVERRIDE = {'picoblade-header': (5.65, 25.45, 11.24, 28.65), 'picoblade-tails': (5.65, 25.45, 11.24, 28.65)}


def load_keepouts() -> list[dict]:
    """R2 keep-outs in board coordinates (x1, y1, x2, y2), read from the mechanical model."""
    out = []
    for k in json.loads(ENVELOPE_FILE.read_text())['keepouts']:
        faces = ''.join('F' if f.startswith('component') else 'B' for f in k['faces'])
        rect = KEEPOUT_OVERRIDE.get(k['id'], (k['board_x'][0], k['board_y'][0], k['board_x'][1], k['board_y'][1]))
        out.append(dict(id=k['id'], faces=faces, rect=tuple(rect), owner=KEEPOUT_OWNER.get(k['id'])))
    return out


KEEPOUTS = load_keepouts()

# Fixed parts at R2's positions. Jack footprint (across, along) maps to board (axis_y - across, along - 0.7):
# body front face at assembly Z -0.5 (rear pocket), so pin 1 lands at board_x 0.9 as R2 lists.
FIXED = {
    'J1': dict(at=[-0.7, 35.8], rot=90, side='F', src='R2 jacks[CV IN] axis board_y 35.8, pin 1 at (0.9, 35.8)'),
    'J2': dict(at=[-0.7, 50.8], rot=90, side='F', src='R2 jacks[CV THRU] axis board_y 50.8'),
    'SW1': dict(at=[6.8, 60.1], rot=0, side='F', src='R2 setting_switch pegs (4.3, 60.1) and (9.3, 60.1), actuator toward +y'),
    'J3': dict(at=[12.6, 10.6], rot=0, side='F', src='R2 headers.led_header board_y 8.925..13.175, opening +y; moved 0.6 toward the front from R2 board_x 10.2..16.2 so the MP pad (to x+3.4) keeps 0.2 mm copper-to-edge clearance; body 9.6..15.6'),
    'J5': dict(at=[7.24, 27.5], rot=0, side='F', src='R2 headers.power_header board_y 25.45..28.65 (PR #27 f58180a); body board_x 5.74..11.24, 0.09 behind R2 5.65..11.15 because the MCU courtyard (edge to 5.24) abuts its courtyard'),
}
CONNECTOR_REFS = set(FIXED)

# Solder face: only 0603 resistors (0.55 mm) and flat test pads, inside R2's 0.6 mm low-profile zone.
B_ALLOWED = {'R0603', 'TESTPAD'}
VIA_FIELDS = ('U1', 'U5')
GAP = 0.15

# Component-face placement, hand-packed by function into the regions R2's keep-outs leave free (layout review of
# PR #30: hot loops at the IC, analog parts at the pins they serve).
# Buck (top left): C1 across U2 VIN (pin 3) and GND (pin 4); C4 across BST/SW right under the IC; L1's SW pad
# straight below; output cap C2 at L1's +5V pad. Top right, above the J3 courtyard: U6 with C11/C12 and LDO U3
# with C5/C6 (C6 at the output pin). Beside the spine slot: U4 with C16 at VLED, then the ADC buffer island U7 with
# D3 at U7.3 (CV_FILTER), C13 on CV_AFFINE beside R7 and C17 at U7.5, so the long CV run is U6's low-impedance
# output. MCU 100 n (C8) right under VDD (U1.3/U1.4), C7/C14 at the MCU's upper right. Q1 (DC enable for U4) in
# the free corner beside the switch; 1206/SOD323 bulk parts in the strip behind the jack bodies; U5 between jacks.
MANUAL_F = {
    'C1': (4.75, 1.9, 270), 'U2': (7.4, 1.9, 270), 'C4': (7.7, 4.45, 180), 'L1': (6.3, 7.93, 270), 'C2': (6.3, 11.9, 0),
    'U6': (14.15, 1.75, 0), 'U3': (14.15, 5.2, 180),
    'C11': (9.84, 1.5, 90), 'C12': (11.38, 1.5, 90), 'C5': (9.84, 4.45, 270), 'C6': (11.38, 4.45, 270),
    'U4': (5.9, 16.9, 0), 'C16': (9.68, 16.1, 0), 'C13': (9.53, 17.73, 0),
    'U7': (5.9, 20.35, 180), 'D3': (9.68, 20.4, 180), 'C17': (5.3, 22.78, 0),
    'C7': (9.43, 22.84, 0), 'C14': (9.43, 24.24, 0),
    'U1': (2.62, 26.13, 90), 'C8': (1.5, 29.46, 180),
    'C3': (14.95, 31.95, 90), 'D1': (14.95, 36.0, 90), 'D2': (14.95, 39.5, 90), 'C15': (14.95, 49.0, 90),
    'U5': (3.6, 43.75, 0), 'C9': (7.3, 43.75, 0), 'C10': (10.25, 43.75, 0),
    'Q1': (14.45, 60.7, 0),
}
# Fixed-part courtyards that R2 placed into a keep-out on purpose (reason recorded, checked by name).
ACCEPTED = {('J5', 'led-cable-lane'): 'courtyard margin only: J5 body ends at board_x 11.15, the lane starts at 11.4 (R2 PR #27 f58180a)'}
# Solder-face anchors for the packer (resistors and test pads), near the parts they serve.
ANCHORS = {
    'R1': (13.0, 4.0), 'R2': (13.0, 4.0), 'R8': (10.0, 3.0),
    'R3': (8.0, 19.0), 'R4': (9.0, 18.0), 'R5': (9.0, 18.0), 'R6': (9.0, 18.0), 'R7': (8.4, 19.6),
    'R24': (6.5, 22.5), 'R25': (6.5, 22.5),
    'R11': (6.5, 17.0), 'R13': (6.5, 18.0), 'R20': (9.0, 16.0), 'R23': (5.0, 18.0),
    'R12': (14.0, 60.5), 'R22': (14.0, 60.5),
    'R9': (3.0, 26.0), 'R10': (3.0, 26.0), 'R21': (3.0, 26.0),
    'R14': (6.0, 43.7), 'R15': (6.0, 43.7), 'R16': (6.0, 43.7), 'R17': (6.0, 43.7), 'R18': (6.0, 43.7), 'R19': (6.0, 43.7),
    'TP1': (3.0, 26.0), 'TP2': (3.0, 26.0), 'TP3': (3.0, 26.0), 'TP4': (3.0, 26.0), 'TP5': (3.0, 26.0),
}


def courtyard(fp_name: str, lib: str) -> tuple[float, float, float, float]:
    d = a7.A7_FP if lib == 'LightBlockA7' else a7.A5_FP
    s = (d / f'{fp_name}.kicad_mod').read_text()
    pts = []
    for chunk in re.split(r'\(fp_', s)[1:]:
        m = re.match(r'(?:rect|line)\s*\(start ([-\d.]+) ([-\d.]+)\)\s*\(end ([-\d.]+) ([-\d.]+)\)', chunk)
        if m and re.search(r'\(layer "F\.CrtYd"\)', chunk.split('(pad ')[0]):
            x1, y1, x2, y2 = map(float, m.groups())
            pts += [(x1, y1), (x2, y2)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def transform(rect, at, rot, side):
    """KiCad placement of a footprint-local rect: flip (B) mirrors local x, then rotate, then translate."""
    x1, y1, x2, y2 = rect
    corners = [(x1, y1), (x1, y2), (x2, y1), (x2, y2)]
    if side == 'B':
        corners = [(-x, y) for x, y in corners]
    t = math.radians(rot)
    c, s_ = round(math.cos(t), 9), round(math.sin(t), 9)
    pts = [(at[0] + x * c + y * s_, at[1] - x * s_ + y * c) for x, y in corners]
    return (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))


def overlap(a, b, gap=0.0):
    return a[0] < b[2] + gap and b[0] < a[2] + gap and a[1] < b[3] + gap and b[1] < a[3] + gap


def placement_rule() -> tuple[int, int]:
    """(resolution, minimum gap) in nanometres, from the gate profile."""
    r = json.loads(GATE_PROFILE.read_text())['placement']
    return int(r['resolution_nm']), round(r['min_courtyard_gap_mm'] * 1e6)


def to_nm(rect, res: int) -> tuple[int, ...]:
    return tuple(round(v * 1e6 / res) * res for v in rect)


def components() -> dict:
    return {c['ref']: c for c in a7.a7_controller()['components'] if c['footprint']}


def footprint_rect(c, p):
    return transform(courtyard(c['footprint'], c.get('fp_lib', 'LightBlock')), p['at'], p['rot'], p['side'])


def violations(placement: dict) -> list[str]:
    comps = components()
    out = []
    missing = sorted(set(comps) - set(placement))
    if missing:
        out.append(f'unplaced: {missing}')
    res, tol = placement_rule()
    rects = {r: (placement[r]['side'], to_nm(footprint_rect(comps[r], placement[r]), res)) for r in placement if r in comps}
    edge = to_nm((0, 0, W, H), res)
    for r, (side, rc) in rects.items():
        fp = comps[r]['footprint']
        if side == 'B' and fp not in B_ALLOWED and r not in CONNECTOR_REFS:
            out.append(f'{r}: {fp} not allowed on the solder face')
        if r not in CONNECTOR_REFS and not (rc[0] >= edge[0] + tol and rc[1] >= edge[1] + tol and rc[2] <= edge[2] - tol
                                            and rc[3] <= edge[3] - tol):
            out.append(f'{r}: courtyard {tuple(round(v / 1e6, 3) for v in rc)} outside the board')
        for k in KEEPOUTS:
            if side in k['faces'] and k.get('owner') != r and (r, k['id']) not in ACCEPTED and overlap(rc, to_nm(k['rect'], res), tol):
                out.append(f'{r}: courtyard in keep-out {k["id"]}')
    refs = sorted(rects)
    for i, a in enumerate(refs):
        for b in refs[i + 1:]:
            # THT connectors occupy both faces for courtyard purposes only on their own side
            if rects[a][0] == rects[b][0] and overlap(rects[a][1], rects[b][1], tol):
                out.append(f'courtyard overlap {a} / {b}')
    return out


def pack() -> dict:
    comps = components()
    placement = {r: dict(at=f['at'], rot=f['rot'], side=f['side']) for r, f in FIXED.items()}
    placement.update({r: dict(at=[x, y], rot=rot, side='F') for r, (x, y, rot) in MANUAL_F.items()})
    occupied = {'F': [], 'B': []}
    for r in placement:
        occupied[placement[r]['side']].append(footprint_rect(comps[r], placement[r]))
    blocks = {'F': [k['rect'] for k in KEEPOUTS if 'F' in k['faces']],
              'B': [k['rect'] for k in KEEPOUTS if 'B' in k['faces']]}
    # THT pads of the jacks and J5 pass through: block a small square on the back around each
    for r in ('J1', 'J2', 'J5'):
        occupied['B'].append(footprint_rect(comps[r], placement[r]))
    # keep the solder face under the fine-pitch parts free: their fan-out vias need that area
    for r in VIA_FIELDS:
        x1, y1, x2, y2 = footprint_rect(comps[r], placement[r])
        blocks['B'].append((x1 - 0.3, y1 - 0.3, x2 + 0.3, y2 + 0.3))
    todo = [r for r in comps if r not in placement]
    size = {r: (lambda q: (q[2] - q[0]) * (q[3] - q[1]))(courtyard(comps[r]['footprint'], comps[r].get('fp_lib', 'LightBlock')))
            for r in todo}
    todo.sort(key=lambda r: (-size[r], r))
    step = 0.1
    for r in todo:
        side = 'B' if comps[r]['footprint'] in B_ALLOWED else 'F'
        ax, ay = ANCHORS.get(r, (W / 2, H / 2))
        best = None
        for rot in (0, 90):
            local = courtyard(comps[r]['footprint'], comps[r].get('fp_lib', 'LightBlock'))
            for i in range(int(W / step) + 1):
                x = round(i * step, 4)
                for j in range(int(H / step) + 1):
                    y = round(j * step, 4)
                    d = (x - ax) ** 2 + (y - ay) ** 2
                    if best is not None and d >= best[0]:
                        continue
                    rc = transform(local, [x, y], rot, side)
                    if rc[0] < 0 or rc[1] < 0 or rc[2] > W or rc[3] > H:
                        continue
                    if any(overlap(rc, k) for k in blocks[side]) or any(overlap(rc, o, GAP) for o in occupied[side]):
                        continue
                    best = (d, x, y, rot, rc)
        if best is None:
            raise SystemExit(f'no legal position for {r} ({comps[r]["footprint"]}, {side})')
        _, x, y, rot, rc = best
        placement[r] = dict(at=[x, y], rot=rot, side=side)
        occupied[side].append(rc)
    return placement


def placement_doc(pl: dict) -> str:
    doc = {'generator': 'scripts/a7_board.py place',
           'frame': 'R2 board frame: board_x = assembly Z - 0.2, board_y = assembly Y - 48.5, seen from the component face (+X)',
           'mechanical_source': ENVELOPES,
           'solder_face_rule': 'B side carries only 0603 resistors and flat test pads besides THT terminals, inside R2 solder_face_low_profile_zone (max 0.6 mm)',
           'fixed': {r: f['src'] for r, f in FIXED.items()},
           'placements': {r: pl[r] for r in sorted(pl, key=lambda s: (re.sub(r'\d', '', s), int(re.sub(r'\D', '', s) or 0)))}}
    return json.dumps(doc, indent=1) + '\n'


# ------------------------------------------------------------- staging board (pinned KiCad image)
GND_PLANE = 'In1.Cu'


def stage_tree(o: Path) -> Path:
    """Mirror the repo layout into the staging dir so the project's library tables resolve."""
    import shutil
    shutil.copytree(a7.A5_FP, o / 'engineering/a5/electronics/footprints/LightBlock.pretty')
    shutil.copytree(a7.A7_FP, o / 'engineering/a7/electronics/footprints/LightBlockA7.pretty')
    ctrl = o / 'engineering/a7/electronics/controller'
    shutil.copytree(a7.A7_CTRL, ctrl, ignore=shutil.ignore_patterns('controller.kicad_pcb'))
    return ctrl


def mm(v):
    return round(v / 1e6, 6)


def pad_geometry(board) -> dict:
    """Copper geometry the router needs, read back from pcbnew (board coordinates, mm)."""
    import pcbnew as p
    layers = [board.GetLayerName(l) for l in board.GetEnabledLayers().CuStack()]
    out = {'layers': layers, 'outline': [0.0, 0.0, W, H], 'pads': [], 'courtyards': {}}
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        cy = fp.GetCourtyard(p.F_CrtYd if not fp.IsFlipped() else p.B_CrtYd).BBox()
        out['courtyards'][ref] = [mm(cy.GetLeft()), mm(cy.GetTop()), mm(cy.GetRight()), mm(cy.GetBottom())]
        for pad in fp.Pads():
            polys = {}
            for l in board.GetEnabledLayers().CuStack():
                if not pad.IsOnLayer(l):
                    continue
                buf = p.SHAPE_POLY_SET()
                pad.TransformShapeToPolygon(buf, l, 0, p.FromMM(0.002), p.ERROR_INSIDE)
                pts = []
                for i in range(buf.OutlineCount()):
                    ol = buf.Outline(i)
                    pts.append([[mm(ol.CPoint(k).x), mm(ol.CPoint(k).y)] for k in range(ol.PointCount())])
                if pts:
                    polys[board.GetLayerName(l)] = pts
            drill = None
            if pad.HasHole():
                ds = pad.GetDrillSize()
                drill = {'at': [mm(pad.GetPosition().x), mm(pad.GetPosition().y)], 'size': [mm(ds.x), mm(ds.y)],
                         'angle': pad.GetOrientation().AsDegrees(), 'plated': pad.GetAttribute() != p.PAD_ATTRIB_NPTH}
            out['pads'].append({'ref': ref, 'pad': pad.GetNumber(), 'net': pad.GetNetname(),
                                'at': [mm(pad.GetPosition().x), mm(pad.GetPosition().y)],
                                'smd_layer': None if pad.HasHole() else board.GetLayerName(pad.GetPrincipalLayer()),
                                'polys': polys, 'drill': drill})
    return out


def cmd_build(out: Path, netlist: Path) -> int:
    import pcbnew as p
    o = a7.authority.require_empty_staging(out)
    ctrl = stage_tree(o)
    pl = json.loads(PLACEMENT.read_text())['placements']
    comps_nl, pin_nets = a7.ev.parse_netlist(netlist)
    b = a7.a7_controller()
    board = p.BOARD()
    board.SetCopperLayerCount(4)
    board.GetDesignSettings().SetBoardThickness(p.FromMM(1.6))
    board.SetLayerType(p.In1_Cu, p.LT_POWER)
    for (x1, y1), (x2, y2) in (((0, 0), (W, 0)), ((W, 0), (W, H)), ((W, H), (0, H)), ((0, H), (0, 0))):
        e = p.PCB_SHAPE(board)
        e.SetShape(p.SHAPE_T_SEGMENT)
        e.SetLayer(p.Edge_Cuts)
        e.SetWidth(p.FromMM(0.05))
        e.SetStart(p.VECTOR2I(p.FromMM(x1), p.FromMM(y1)))
        e.SetEnd(p.VECTOR2I(p.FromMM(x2), p.FromMM(y2)))
        board.Add(e)
    nets = {}
    for n in sorted(set(pin_nets.values())):
        nets[n] = p.NETINFO_ITEM(board, n, len(nets) + 1)
        board.Add(nets[n])
    plugin = p.PCB_IO_MGR.FindPlugin(p.PCB_IO_MGR.KICAD_SEXP)
    sheet = str(a7.uuid.uuid5(a7.A7_NS, 'controller/sheet'))
    libs = {'LightBlockA7': o / 'engineering/a7/electronics/footprints/LightBlockA7.pretty',
            'LightBlock': o / 'engineering/a5/electronics/footprints/LightBlock.pretty'}
    for c in b['components']:
        if not c['footprint']:
            continue
        lib = c.get('fp_lib', 'LightBlock')
        fp = plugin.FootprintLoad(str(libs[lib]), c['footprint'])
        fp.SetReference(c['ref'])
        fp.SetValue(c['value'])
        fp.SetFPID(p.LIB_ID(lib, c['footprint']))
        path = p.KIID_PATH()
        path.push_back(p.KIID(sheet))
        path.push_back(p.KIID(str(a7.uuid.uuid5(a7.A7_NS, 'controller/' + c['ref']))))
        fp.SetPath(path)
        board.Add(fp)
        q = pl[c['ref']]
        if q['side'] == 'B':
            fp.Flip(p.VECTOR2I(0, 0), p.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetOrientationDegrees(q['rot'])
        fp.SetPosition(p.VECTOR2I(p.FromMM(q['at'][0]), p.FromMM(q['at'][1])))
        for k, v in comps_nl[c['ref']]['fields'].items():
            if k in ('MPN', 'LCSC'):
                fp.SetField(k, v)
                f = fp.GetField(k)
                f.SetVisible(False)
                f.SetLayer(p.B_Fab if q['side'] == 'B' else p.F_Fab)
        # 0.6 mm-pitch packing leaves no room for designators on silk; they go to the fab drawing layer
        for t in (fp.Reference(), fp.Value()):
            t.SetLayer(p.B_Fab if q['side'] == 'B' else p.F_Fab)
        for z in fp.Pads():
            net = pin_nets.get((c['ref'], z.GetNumber()))
            if net:
                z.SetNet(nets[net])
    z = p.ZONE(board)
    z.SetLayer(p.In1_Cu)
    z.SetNet(nets['/GND'])
    z.SetIsRuleArea(False)
    z.SetMinThickness(p.FromMM(0.2))
    z.SetLocalClearance(p.FromMM(0.2))
    z.SetPadConnection(p.ZONE_CONNECTION_THERMAL)
    z.SetAssignedPriority(0)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in ((0, 0), (W, 0), (W, H), (0, H)):
        ol.Append(p.FromMM(x), p.FromMM(y))
    board.Add(z)
    board.BuildConnectivity()
    pcb = ctrl / 'controller.kicad_pcb'
    p.SaveBoard(str(pcb), board)
    geo = pad_geometry(board)
    (o / 'geometry.json').write_text(json.dumps(geo, indent=0) + '\n')
    print(json.dumps({'staging_board': str(pcb), 'geometry': str(o / 'geometry.json'), 'pads': len(geo['pads'])}))
    return 0


def add_zone(board, p, layer, net, priority):
    z = p.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(net)
    z.SetMinThickness(p.FromMM(0.2))
    z.SetLocalClearance(p.FromMM(0.2))
    z.SetPadConnection(p.ZONE_CONNECTION_FULL)
    z.SetAssignedPriority(priority)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in ((0, 0), (W, 0), (W, H), (0, H)):
        ol.Append(p.FromMM(x), p.FromMM(y))
    board.Add(z)
    return z


def cmd_apply(pcb: Path, routes: Path) -> int:
    """Add a router proposal (tracks, vias) and the GND pours to a staging board, refill, save in place."""
    import pcbnew as p
    if a7.REPO in pcb.resolve().parents:
        raise a7.authority.Refused('apply works on a staging board outside the repository')
    board = p.LoadBoard(str(pcb))
    nets = {n.GetNetname(): n for n in board.GetNetsByName().values()}
    r = json.loads(routes.read_text())
    lid = {board.GetLayerName(l): l for l in board.GetEnabledLayers().CuStack()}
    for t in r['tracks']:
        tr = p.PCB_TRACK(board)
        tr.SetStart(p.VECTOR2I(p.FromMM(t['start'][0]), p.FromMM(t['start'][1])))
        tr.SetEnd(p.VECTOR2I(p.FromMM(t['end'][0]), p.FromMM(t['end'][1])))
        tr.SetWidth(p.FromMM(t['width']))
        tr.SetLayer(lid[t['layer']])
        tr.SetNet(nets[t['net']])
        board.Add(tr)
    for v in r['vias']:
        via = p.PCB_VIA(board)
        via.SetPosition(p.VECTOR2I(p.FromMM(v['at'][0]), p.FromMM(v['at'][1])))
        via.SetWidth(p.FromMM(v['size']))
        via.SetDrill(p.FromMM(v['drill']))
        via.SetLayerPair(p.F_Cu, p.B_Cu)
        via.SetNet(nets[v['net']])
        board.Add(via)
    for z in list(board.Zones()):
        z.SetPadConnection(p.ZONE_CONNECTION_FULL)
    gnd = nets['/GND']
    for layer in (p.F_Cu, p.In2_Cu, p.B_Cu):
        add_zone(board, p, layer, gnd, 0)
    board.BuildConnectivity()
    p.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    p.SaveBoard(str(pcb), board)
    # a fill computed before the first save differs from a load-then-refill by a few vertices; settle it
    board = p.LoadBoard(str(pcb))
    p.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    p.SaveBoard(str(pcb), board)
    print(json.dumps({'board': str(pcb), 'tracks': len(r['tracks']), 'vias': len(r['vias']),
                      'unconnected_pcbnew': board.GetConnectivity().GetUnconnectedCount(True)}))
    return 0


def cmd_regen_check(raw: Path) -> int:
    import subprocess
    py = sys.executable
    facts = raw / 'a7_controller'
    steps = [[py, 'scripts/a7_electronics.py', 'generate', '--check'],
             [py, 'scripts/a7_board.py', 'place', '--check'],
             [py, 'scripts/native_gate/authority.py', 'export-placement', '--check', '--board', str(BOARD.relative_to(REPO)),
              '--facts', str(facts / 'board_facts.json'), '--geometry', str(facts / 'board_geometry.json'),
              '--out', str(BOARD_EXPORT.relative_to(REPO))]]
    code = 0
    for c in steps:
        r = subprocess.run(c, cwd=REPO, capture_output=True, text=True)
        print(f"{' '.join(c[1:3])}: exit {r.returncode} {(r.stdout + r.stderr).strip()[-300:]}")
        code = code or r.returncode
    return code


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    sp.add_parser('place').add_argument('--check', action='store_true')
    sp.add_parser('check')
    bd = sp.add_parser('build')
    bd.add_argument('--out', type=Path, required=True)
    bd.add_argument('--netlist', type=Path, required=True)
    ac = sp.add_parser('apply')
    ac.add_argument('--board', type=Path, required=True)
    ac.add_argument('--routes', type=Path, required=True)
    sp.add_parser('regen-check').add_argument('--raw', type=Path, required=True)
    a = ap.parse_args()
    if a.cmd == 'regen-check':
        return cmd_regen_check(a.raw)
    if a.cmd in ('build', 'apply'):
        try:
            return cmd_build(a.out, a.netlist) if a.cmd == 'build' else cmd_apply(a.board, a.routes)
        except a7.authority.Refused as r:
            print(f'refused: {r}', file=sys.stderr)
            return 2
    if a.cmd == 'place':
        text = placement_doc(pack())
        if a.check:
            ok = PLACEMENT.is_file() and PLACEMENT.read_text() == text
            print('placement current' if ok else 'placement stale', file=sys.stdout if ok else sys.stderr)
            return 0 if ok else 1
        a7.authority.check_writable(PLACEMENT)
        PLACEMENT.write_text(text)
        print(f'wrote {PLACEMENT.relative_to(REPO)}')
    pl = json.loads(PLACEMENT.read_text())['placements']
    v = violations(pl)
    print(json.dumps({'placed': len(pl), 'violations': v}, indent=1))
    return 1 if v else 0


if __name__ == '__main__':
    sys.exit(main())
