#!/usr/bin/env python3
"""A7 controller schematic and A7-only footprints, derived from the immutable A5 design data.

The A5 design data (engineering/a5/electronics/design/design_data.py) is imported
read-only (no bytecode is written next to it). Exactly the A7 changes listed in
A7_CHANGES are applied; everything else is the A5 controller unchanged. The
schematic writer is a port of A5's make_schematic(); `reproduce-a5` proves the
port by regenerating the A5 controller schematic and comparing it byte-for-byte
with the committed A5 file.

Commands:
  generate [--check]          write (or compare) engineering/a7/electronics/{controller,footprints}
  reproduce-a5 --out DIR      regenerate the A5 controller schematic into an empty DIR outside the repo and compare
  init-board --out DIR --netlist N  (pinned KiCad image only) unrouted staging board for schematic-to-PCB parity,
                              written only into an empty DIR outside the repository; never the authoritative board
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import shutil
import sys
import uuid
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
A5_DESIGN = REPO / 'engineering/a5/electronics/design'
A5_FP = REPO / 'engineering/a5/electronics/footprints/LightBlock.pretty'
A5_CONTROLLER_SCH = REPO / 'engineering/a5/electronics/native/controller/controller.kicad_sch'
A7_EL = REPO / 'engineering/a7/electronics'
A7_CTRL = A7_EL / 'controller'
A7_FP = A7_EL / 'footprints/LightBlockA7.pretty'

sys.dont_write_bytecode = True
sys.path.insert(0, str(A5_DESIGN))
import design_data as a5  # noqa: E402  (read-only import of the immutable A5 checkpoint)
sys.path.pop(0)
sys.path.insert(0, str(Path(__file__).resolve().parent / 'native_gate'))
import authority  # noqa: E402
import evaluate as ev  # noqa: E402
sys.path.pop(0)

A5_NS = uuid.UUID('99c06823-a7e1-4d4e-a538-d1579ee671e1')
A7_NS = uuid.uuid5(A5_NS, 'light-block-a7-controller')

# ---------------------------------------------------------------- A7 changes
# Pin numbers are the exact parts' own (SOFNG PJ-324M drawing, C&K PCM13SMTR function
# table), never PJ-3582-B or 1MS3T1B1M2QES numbers. Status words follow the R1 bundles
# in .claude/skills/component-a7-*/ (PR #23).
PIN_DEFS_A7 = {
    'JACK_PJ324M': [('1', 'SLEEVE', 'passive'), ('2', 'RING', 'passive'), ('3', 'RING_NORMAL', 'passive'),
                    ('4', 'TIP', 'passive'), ('5', 'TIP_NORMAL', 'passive')],
    'SW_PCM13': [('1', 'THROW_1', 'passive'), ('2', 'THROW_2', 'passive'), ('3', 'COMMON', 'passive'),
                 ('4', 'THROW_4', 'passive')],
}
A7_CHANGES = {
    'J1': dict(type='JACK_PJ324M', key='JACK_A7', mpn='PJ-324M', c_code='C22355739', footprint='PJ324M',
               fp_lib='LightBlockA7', nets={'1': 'GND', '2': 'GND', '3': None, '4': 'CV_THRU', '5': None}),
    'J2': dict(type='JACK_PJ324M', key='JACK_A7', mpn='PJ-324M', c_code='C22355739', footprint='PJ324M',
               fp_lib='LightBlockA7', nets={'1': 'GND', '2': 'GND', '3': None, '4': 'CV_THRU', '5': None}),
    # POS.1 1-3 -> MODE_A low (ON); POS.2 2-3 with 2 open -> both high (PROGRAM); POS.3 3-4 -> MODE_B low (CV)
    'SW1': dict(type='SW_PCM13', key='SW_A7', mpn='PCM13SMTR', c_code='C221842', footprint='PCM13SMTR',
                fp_lib='LightBlockA7', nets={'1': 'MODE_A', '2': None, '3': 'GND', '4': 'MODE_B'}),
}
A7_NOTES = ('Identical net labels are connected. U6 senses through 20 Mohm; U7 buffers the ADC.\n'
            'ADC=(100/133)*(VDD/2+CV/8). TPS2552-1 uses active-low EN; PA5 HIGH enables via NPN.\n'
            'J1/J2 SOFNG PJ-324M (pin identities INFERRED, R1 #16): 1 sleeve + 2 ring = GND, 4 TIP = CV_THRU, normals 3/5 unused.\n'
            'SW1 C&K PCM13SMTR side switch: 3 common = GND. POS1 1-3 ON (A=0,B=1); POS2 open PROGRAM (1,1); POS3 3-4 CV (1,0).\n'
            'Power transients, MLCC bias, fault heat and connector continuity require hardware tests.')


def a7_controller() -> dict:
    b = a5.make_controller()
    b = copy.deepcopy(b)
    for c in b['components']:
        ch = A7_CHANGES.get(c['ref'])
        if ch:
            c.update(copy.deepcopy(ch))
    missing = set(A7_CHANGES) - {c['ref'] for c in b['components']}
    if missing:
        raise SystemExit(f'A5 controller lacks {sorted(missing)}')
    b['title'] = 'Light Block A7 controller'
    return b


# ------------------------------------------------------ schematic (A5 port)
def q(s):
    return json.dumps(str(s), ensure_ascii=False)


def symbol_definition(name, pins):
    passive = name in ('R', 'C', 'L', 'RECT')
    w = 5.08 if passive else 15.24
    count = math.ceil(len(pins) / 2)
    h = max(5.08, (count + 1) * 2.54)
    loc = []
    for i, (num, pn, pt) in enumerate(pins):
        left = i < count
        y = (count - 1) * 1.27 - (i if left else i - count) * 2.54
        x = -(w / 2 + 5.08) if left else (w / 2 + 5.08)
        loc.append((num, pn, pt, x, y, 0 if left else 180))
    a = [f'(symbol "LightBlock:{name}" (pin_names (offset 0.8)) (in_bom yes) (on_board yes)',
         f'(property "Reference" "{name[0]}" (at 0 {h/2+3} 0) (effects (font (size 1.27 1.27))))',
         f'(property "Value" "{name}" (at 0 {h/2+1} 0) (effects (font (size 1.27 1.27))))',
         f'(symbol "{name}_0_1" (rectangle (start {-w/2} {h/2}) (end {w/2} {-h/2}) (stroke (width 0.254) (type default)) (fill (type background))))',
         f'(symbol "{name}_1_1"']
    for num, pn, pt, x, y, ang in loc:
        a.append(f'(pin {pt} line (at {x} {y} {ang}) (length 5.08) (name {q(pn)} (effects (font (size 1.1 1.1)))) (number {q(num)} (effects (font (size 1.1 1.1)))))')
    a.append('))')
    return '\n'.join(a), loc, h


A5_STYLE = dict(ns=A5_NS, generator='light_block_a5', date='2026-11-06', rev='A5',
                comments=['Engineering draft. Controller is not routed. No hardware qualification claimed.'],
                notes=('Identical net labels are connected. U6 senses through 20 Mohm; U7 buffers the ADC.\n'
                       'ADC=(100/133)*(VDD/2+CV/8). TPS2552-1 uses active-low EN; PA5 HIGH enables via NPN.\n'
                       'PJ-3582 pins 4/5 detect insertion and are unused. Pin 6 TIP directly connects IN to THRU.\n'
                       'Power transients, MLCC bias, fault heat and connector continuity require hardware tests.'),
                lib_descr='Self-contained A5 symbols with manufacturer pin numbers',
                fp_tables=[('LightBlock', '${KIPRJMOD}/../../footprints/LightBlock.pretty', 'Self-contained A5 exact part footprints')])
A7_STYLE = dict(ns=A7_NS, generator='light_block_a7', date='2026-11-08', rev='A7',
                comments=['Engineering draft, schematic phase. Controller not placed or routed. No hardware qualification claimed.',
                          'PJ-324M pin identities INFERRED and PCM13SMTR/PJ-324M lands from mirror drawings: see engineering/a7/electronics/README.md.'],
                notes=A7_NOTES,
                lib_descr='A7 controller symbols with manufacturer pin numbers (A5 symbols plus PJ-324M and PCM13SMTR)',
                fp_tables=[('LightBlock', '${KIPRJMOD}/../../../a5/electronics/footprints/LightBlock.pretty', 'Immutable A5 exact part footprints (read-only)'),
                           ('LightBlockA7', '${KIPRJMOD}/../footprints/LightBlockA7.pretty', 'A7-only footprints generated by scripts/a7_electronics.py')])


def make_schematic(b: dict, style: dict) -> dict[str, str]:
    """Port of A5 make_schematic() for the controller; returns {filename: text}."""
    def uid(s):
        return str(uuid.uuid5(style['ns'], s))
    pin_defs = {**a5.PIN_DEFS, **PIN_DEFS_A7}
    name = b['name']
    root_id = uid(name + '/sheet')
    cs = [dict(c) for c in b['components']]
    for i, net in enumerate(b['power_flags'], 1):
        cs.append(dict(ref=f'#FLG{i:02}', type='PWR_FLAG', value='Power source declaration', mpn='', c_code='', footprint='',
                       nets={'1': net}, group='power', at=[0, 0], fitted=False))
    defs = {}
    for c in cs:
        typ = c['type']
        defs[typ] = symbol_definition(typ, pin_defs.get(typ, [('1', '1', 'passive'), ('2', '2', 'passive')]))
    comments = ' '.join(f'(comment {i} {q(t)})' for i, t in enumerate(style['comments'], 1))
    a = [f'(kicad_sch (version 20250114) (generator "{style["generator"]}") (uuid "{root_id}") (paper "A2")',
         f'(title_block (title {q(b["title"])}) (date "{style["date"]}") (rev "{style["rev"]}") (company "Light Block") {comments})',
         '(lib_symbols', *[x[0] for x in defs.values()], ')']
    offsets = {'power': (40, 52), 'logic': (230, 52), 'analog': (420, 52)}
    counts = defaultdict(int)
    for x, title in [(20, 'POWER / DEFAULT-OFF LED SWITCH'), (210, 'MCU / DUAL DATA / SERVICE'), (400, 'PASSIVE CV THRU / SENSING / ADC')]:
        a.append(f'(text {q(title)} (at {x} 20 0) (effects (font (size 2.2 2.2)) (justify left)) (uuid {q(uid(name+title))}))')
    a.append(f'(text {q(style["notes"])} (at 20 397 0) (effects (font (size 1.4 1.4)) (justify left)) (uuid {q(uid(name+"notes"))}))')
    for c in cs:
        group = c['group']
        j = counts[group]
        counts[group] += 1
        x0, y0 = offsets.get(group, (50, 65))
        row = j // 3
        x = x0 + (j % 3) * 58.42
        y = y0 if row == 0 else y0 + 46.99 + (row - 1) * 35.56
        x = round(x / 1.27) * 1.27
        y = round(y / 1.27) * 1.27
        typ = c['type']
        loc, h = defs[typ][1:]
        sid = uid(name + '/' + c['ref'])
        fp = f"{c.get('fp_lib', 'LightBlock')}:{c['footprint']}" if c['footprint'] else ''
        a.append(f'(symbol (lib_id "LightBlock:{typ}") (at {x} {y} 0) (unit 1) (in_bom {"yes" if c["fitted"] else "no"}) (on_board {"yes" if c["footprint"] else "no"}) (dnp no) (uuid "{sid}")')
        for pn, pv, py, hidden in [('Reference', c['ref'], y - h/2 - 5, False), ('Value', c['value'], y - h/2 - 2.5, False),
                                   ('Footprint', fp, y, True), ('MPN', c['mpn'], y, True), ('LCSC', c['c_code'], y, True)]:
            a.append(f'(property {q(pn)} {q(pv)} (at {x} {py} 0) (effects (font (size 1.15 1.15)) {"(hide yes)" if hidden else ""}))')
        for num, *_ in loc:
            a.append(f'(pin {q(num)} (uuid {q(uid(name+c["ref"]+"pin"+num))}))')
        a.append(f'(instances (project {q(name)} (path "/{root_id}" (reference {q(c["ref"])}) (unit 1)))))')
        for num, pn, pt, px, py, ang in loc:
            ax, ay = x + px, y - py
            net = c['nets'].get(num)
            if net is None:
                a.append(f'(no_connect (at {ax} {ay}) (uuid {q(uid(sid+num+"nc"))}))')
                continue
            ex = ax + (-6.35 if px < 0 else 6.35)
            a.append(f'(wire (pts (xy {ax} {ay}) (xy {ex} {ay})) (stroke (width 0) (type default)) (uuid {q(uid(sid+num+"wire"))}))')
            a.append(f'(label {q(net)} (at {ex} {ay} 0) (effects (font (size 1.15 1.15)) (justify {"right" if px < 0 else "left"} bottom)) (uuid {q(uid(sid+num+"label"))}))')
    a.append(')')
    lib = [d[0].replace('(symbol "LightBlock:', '(symbol "', 1) for d in defs.values()]
    pro = {'meta': {'filename': name + '.kicad_pro', 'version': 1},
           'board': {'design_settings': {'rules': {'min_clearance': .15, 'min_copper_edge_clearance': .2, 'min_hole_clearance': .2,
                                                   'min_through_hole_diameter': .3, 'min_track_width': .15, 'min_via_annular_width': .15,
                                                   'min_via_diameter': .6}}},
           'net_settings': {'classes': [{'name': 'Default', 'clearance': .15, 'track_width': .25, 'via_diameter': .6, 'via_drill': .3,
                                         'microvia_diameter': .3, 'microvia_drill': .1, 'diff_pair_width': .2, 'diff_pair_gap': .25,
                                         'diff_pair_via_gap': .25}], 'meta': {'version': 3}}}
    fpt = ' '.join(f'(lib (name "{n}") (type "KiCad") (uri "{u}") (options "") (descr "{d}"))' for n, u, d in style['fp_tables'])
    return {
        name + '.kicad_sch': '\n'.join(a) + '\n',
        'LightBlock.kicad_sym': f'(kicad_symbol_lib (version 20241209) (generator "{style["generator"]}")\n' + '\n'.join(lib) + '\n)\n',
        'sym-lib-table': f'(sym_lib_table (version 7) (lib (name "LightBlock") (type "KiCad") (uri "${{KIPRJMOD}}/LightBlock.kicad_sym") (options "") (descr "{style["lib_descr"]}")))\n',
        'fp-lib-table': f'(fp_lib_table (version 7) {fpt})\n',
        name + '.kicad_pro': json.dumps(pro, indent=2) + '\n',
    }


# ---------------------------------------------------------------- footprints
# Every dimension below is tagged in FOOTPRINT_SOURCES; nothing is promoted to
# manufacturer-confirmed. Coordinates: mm, KiCad Y down.
PJ324M = {
    # SOFNG drawing 'CIRCUIT BOARD SIZE': (across, along) from the jack axis / body front face.
    # Footprint X = across (+ toward the pin-4/5 side as drawn), Y = along (+ into the board).
    'pins': {'1': (0.0, 1.6), '5': (4.5, 5.6), '3': (-2.5, 8.6), '2': (-5.2, 9.6), '4': (4.0, 13.0)},
    # Slot orientation from the drawing: 1 and 4 run across the axis, 2, 3 and 5 along it.
    'slot_across': ('1', '4'), 'drill': (1.6, 0.8), 'pad': (2.3, 1.5),
    # Pin 1 sits 0.9 mm from the board front edge at R2's jack position: 1.3 along the axis keeps 0.25 mm edge clearance.
    'pad_overrides': {'1': (2.3, 1.3)},
    # 5.4 mm axis-to-edge on the pin-4/5 side, 6.1 on the pin-2/3 side (drawing; electrical review on #24).
    # Barrel projection 3.5 (fact-a7-pj-324m-barrel-projection; 14.2 + 3.5 = L17.7); 3.2 is the terminal projection.
    'body': (-6.1, 0.0, 5.4, 14.2), 'barrel': (-3.0, -3.5, 3.0, 0.0), 'height': 6.3,
}
PCM13 = {
    # C&K PCM13SMTR 'PC MOUNTING' page I-48, relative to the peg centre line: terminals 1-2 and 3-4 are
    # pairs at 1.5 with a 3.0 gap (chain .059/.118/.059, span .236 = 6.0); pads 0.7 x 1.5 from 1.0 (.039)
    # to 2.5 (.098) off the peg line; retention pads 1.0 x 0.8, 9.3 (.366) inner span, 1.13 (.045) gap.
    'signal_x': [-3.0, -1.5, 1.5, 3.0], 'signal_y': -1.75, 'signal_size': (0.7, 1.5),
    'peg_x': [-2.5, 2.5], 'peg_y': 0.0, 'peg_hole': 0.9,
    'mp': [(-5.15, -0.965), (5.15, -0.965), (-5.15, 0.965), (5.15, 0.965)], 'mp_size': (1.0, 0.8),
    'body': (-4.85, -1.3, 4.85, 1.3), 'actuator': (-0.65, 1.3, 0.65, 2.8), 'height': 1.4,
}
FOOTPRINT_SOURCES = {
    'PJ324M': {
        'part': 'SOFNG PJ-324M, LCSC C22355739',
        'terminal_positions': 'MIRROR: SOFNG drawing CIRCUIT BOARD SIZE via LCSC (R1 fact-a7-pj-324m-footprint-positions); across sign follows the drawing view and is UNVERIFIED against the component side',
        'holes': 'ASSUMED: oval plated slots 1.6 x 0.8 mm drill, 2.3 x 1.5 mm pads (pin 1: 2.3 x 1.3, 0.25 mm annular ring along the axis, for board-edge clearance at the R2 front-edge position), oriented as drawn (1 and 4 across the axis, 2, 3 and 5 along it), about 0.2 mm per side around a 1.2 x 0.40 mm blade; the drawing gives no hole/slot size (open question Q3)',
        'body_outline': 'MIRROR: 11.5 wide, axis 5.4 from the pin-4/5 edge and 6.1 from the pin-2/3 edge, 14.2 deep, barrel 3.5 projecting, 6.3 overall height; the across sign (view direction of the drawing) is UNVERIFIED',
        'pin_functions': 'INFERRED (R1 pinmap-a7-pj-324m): 1 sleeve, 2 ring, 3 ring normal, 4 tip, 5 tip normal; continuity test of incoming parts still required',
    },
    'PCM13SMTR': {
        'part': 'C&K PCM13SMTR, LCSC C221842',
        'signal_pads': 'MIRROR: 0.7 x 1.5 mm pads at x -3.0/-1.5/+1.5/+3.0 (1.5/3.0/1.5 chain, 6.0 span), 1.0 to 2.5 mm off the peg line, from PC MOUNTING (I-48, sha256 1c2ca483...); corrected after the electrical review on #24',
        'pegs': 'MIRROR: Ø0.8 pegs at 5.0 mm pitch, Ø0.9 land holes (typ.)',
        'mounting_pads': 'MIRROR: four unnumbered 1.0 x 0.8 mm retention pads, 9.3 mm inner span (centres x +/-5.15), 1.13 mm gap (centres y +/-0.965)',
        'body_position': 'ASSUMED: body centred on the peg line; the drawing does not dimension it',
        'body_outline': 'MIRROR: 9.7 x 2.6 x 1.4 mm, actuator 1.3 wide projecting 1.5 mm from the long edge opposite the terminals',
        'function': 'MIRROR: POS.1 1-3, POS.2 2-3, POS.3 3-4 (common 3)',
    },
}


def _uid(*parts):
    return str(uuid.uuid5(A7_NS, '/'.join(parts)))


def _f(v):
    s = f'{v:.4f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def _rect(name, x1, y1, x2, y2, layer, width):
    return (f'\t(fp_rect (start {_f(x1)} {_f(y1)}) (end {_f(x2)} {_f(y2)}) (stroke (width {width}) (type default)) (fill no) '
            f'(layer "{layer}") (uuid "{_uid(name, layer, _f(x1), _f(y1))}"))')


def _prop(name, key, val, layer='F.Fab'):
    return (f'\t(property "{key}" "{val}" (at 0 0 0) (layer "{layer}") (hide yes) (uuid "{_uid(name, "prop", key)}") '
            f'(effects (font (size 1.27 1.27))))')


def _footprint(name, attr, descr, items):
    head = [f'(footprint "{name}"', '\t(version 20260206)', '\t(generator "a7_electronics")', '\t(layer "F.Cu")',
            f'\t(descr "{descr}")', _prop(name, 'Reference', 'REF**'), _prop(name, 'Value', name),
            _prop(name, 'Datasheet', ''), _prop(name, 'Description', ''), f'\t(attr {attr})',
            '\t(duplicate_pad_numbers_are_jumpers no)']
    return '\n'.join(head + items + ['\t(embedded_fonts no)', ')']) + '\n'


def footprint_pj324m() -> str:
    d = PJ324M
    items = [_rect('PJ324M', *d['body'], 'F.Fab', 0.1), _rect('PJ324M', *d['barrel'], 'F.Fab', 0.1)]
    bx1, by1, bx2, by2 = d['body']
    items.append(_rect('PJ324M', bx1 - .25, d['barrel'][1] - .25, bx2 + .25, by2 + .25, 'F.CrtYd', 0.05))
    for num in sorted(d['pins']):
        x, y = d['pins'][num]
        pad = d['pad_overrides'].get(num, d['pad'])
        (px, py), (dx, dy) = (pad, d['drill']) if num in d['slot_across'] else (pad[::-1], d['drill'][::-1])
        items.append(f'\t(pad "{num}" thru_hole oval (at {_f(x)} {_f(y)}) (size {_f(px)} {_f(py)}) (drill oval {_f(dx)} {_f(dy)}) '
                     f'(layers "*.Cu" "*.Mask") (remove_unused_layers no) (uuid "{_uid("PJ324M", "pad", num)}"))')
    return _footprint('PJ324M', 'through_hole',
                      'SOFNG PJ-324M right-angle 3.5 mm jack; terminal positions MIRROR, holes ASSUMED, pin functions INFERRED', items)


def footprint_pcm13() -> str:
    d = PCM13
    items = [_rect('PCM13SMTR', *d['body'], 'F.Fab', 0.1), _rect('PCM13SMTR', *d['actuator'], 'F.Fab', 0.1)]
    mpx = max(abs(x) for x, _ in d['mp']) + d['mp_size'][0] / 2
    items.append(_rect('PCM13SMTR', -mpx - .25, d['signal_y'] - d['signal_size'][1] / 2 - .25, mpx + .25, d['actuator'][3] + .25,
                       'F.CrtYd', 0.05))
    sx, sy = d['signal_size']
    for i, x in enumerate(d['signal_x'], 1):
        items.append(f'\t(pad "{i}" smd roundrect (at {_f(x)} {_f(d["signal_y"])}) (size {_f(sx)} {_f(sy)}) '
                     f'(layers "F.Cu" "F.Mask" "F.Paste") (roundrect_rratio 0.1) (uuid "{_uid("PCM13SMTR", "pad", str(i))}"))')
    mx, my = d['mp_size']
    for k, (x, y) in enumerate(d['mp']):
        items.append(f'\t(pad "" smd roundrect (at {_f(x)} {_f(y)}) (size {_f(mx)} {_f(my)}) '
                     f'(layers "F.Cu" "F.Mask" "F.Paste") (roundrect_rratio 0.1) (uuid "{_uid("PCM13SMTR", "mp", str(k))}"))')
    for k, x in enumerate(d['peg_x']):
        h = d['peg_hole']
        items.append(f'\t(pad "" np_thru_hole circle (at {_f(x)} {_f(d["peg_y"])}) (size {h} {h}) (drill {h}) '
                     f'(layers "*.Cu" "*.Mask") (uuid "{_uid("PCM13SMTR", "peg", str(k))}"))')
    return _footprint('PCM13SMTR', 'smd',
                      'C&K PCM13SMTR SP3T side-actuated slide switch; land pattern read from the LCSC mirror drawing, unreviewed', items)


# ---------------------------------------------------------------- outputs
def outputs() -> dict[Path, str]:
    out = {A7_CTRL / k: v for k, v in make_schematic(a7_controller(), A7_STYLE).items()}
    out[A7_FP / 'PJ324M.kicad_mod'] = footprint_pj324m()
    out[A7_FP / 'PCM13SMTR.kicad_mod'] = footprint_pcm13()
    out[A7_EL / 'footprints/footprint_sources.json'] = json.dumps(
        {'generator': 'scripts/a7_electronics.py', 'footprints': FOOTPRINT_SOURCES,
         'geometry': {'PJ324M': PJ324M, 'PCM13SMTR': PCM13}}, indent=1, sort_keys=True) + '\n'
    return out


def cmd_generate(check: bool) -> int:
    stale = []
    for path, text in outputs().items():
        if check:
            if not path.is_file() or path.read_text() != text:
                stale.append(str(path.relative_to(REPO)))
            continue
        authority.check_writable(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        print(f'wrote {path.relative_to(REPO)}')
    if stale:
        print('stale derived A7 electronics: ' + ', '.join(stale), file=sys.stderr)
        return 1
    if check:
        print('A7 electronics current')
    return 0


def cmd_reproduce_a5(out: Path) -> int:
    o = authority.require_empty_staging(out)
    o.mkdir(parents=True, exist_ok=True)
    files = make_schematic(a5.make_controller(), A5_STYLE)
    (o / 'controller.kicad_sch').write_text(files['controller.kicad_sch'])
    same = A5_CONTROLLER_SCH.read_bytes() == files['controller.kicad_sch'].encode()
    print(json.dumps({'a5_controller_schematic_reproduced_byte_identical': same}))
    return 0 if same else 1


def cmd_init_board(out: Path, netlist: Path) -> int:
    """Unrouted staging board at A5 placements, for parity only. Mirrors the repo layout so library paths resolve."""
    import pcbnew as p
    o = authority.require_empty_staging(out)
    a5_lib = o / 'engineering/a5/electronics/footprints/LightBlock.pretty'
    ctrl = o / 'engineering/a7/electronics/controller'
    shutil.copytree(A5_FP, a5_lib)
    shutil.copytree(A7_FP, o / 'engineering/a7/electronics/footprints/LightBlockA7.pretty')
    shutil.copytree(A7_CTRL, ctrl)
    b = a7_controller()
    plugin = p.PCB_IO_MGR.FindPlugin(p.PCB_IO_MGR.KICAD_SEXP)
    board = p.BOARD()
    board.SetCopperLayerCount(b['layers'])
    board.GetDesignSettings().SetBoardThickness(p.FromMM(b['thickness']))
    # Net names and symbol fields come from the fresh schematic netlist, as KiCad's
    # update-from-schematic would assign them; placement is A5's (parity only).
    comps, pin_nets = ev.parse_netlist(netlist)
    nets = {}
    for n in sorted(set(pin_nets.values())):
        nets[n] = p.NETINFO_ITEM(board, n, len(nets) + 1)
        board.Add(nets[n])
    sheet = str(uuid.uuid5(A7_NS, 'controller/sheet'))
    for c in b['components']:
        lib = o / 'engineering/a7/electronics/footprints/LightBlockA7.pretty' if c.get('fp_lib') == 'LightBlockA7' else a5_lib
        fp = plugin.FootprintLoad(str(lib), c['footprint'])
        fp.SetReference(c['ref'])
        fp.SetValue(c['value'])
        fp.SetFPID(p.LIB_ID(c.get('fp_lib', 'LightBlock'), c['footprint']))
        path = p.KIID_PATH()
        path.push_back(p.KIID(sheet))
        path.push_back(p.KIID(str(uuid.uuid5(A7_NS, 'controller/' + c['ref']))))
        fp.SetPath(path)
        board.Add(fp)
        if c['side'] == 'B':
            fp.Flip(p.VECTOR2I(0, 0), True)
        fp.SetOrientationDegrees(c['angle'])
        fp.SetPosition(p.VECTOR2I(p.FromMM(c['at'][0]), p.FromMM(c['at'][1])))
        for k, v in comps[c['ref']]['fields'].items():
            if k in ('MPN', 'LCSC'):
                fp.SetField(k, v)
        for z in fp.Pads():
            net = pin_nets.get((c['ref'], z.GetNumber()))
            if net:
                z.SetNet(nets[net])
    board.BuildConnectivity()
    p.SaveBoard(str(ctrl / 'controller.kicad_pcb'), board)
    print(json.dumps({'staging_board': str(ctrl / 'controller.kicad_pcb'), 'note': 'unrouted, parity only, not authoritative'}))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    g = sp.add_parser('generate')
    g.add_argument('--check', action='store_true')
    sp.add_parser('reproduce-a5').add_argument('--out', type=Path, required=True)
    ib = sp.add_parser('init-board')
    ib.add_argument('--out', type=Path, required=True)
    ib.add_argument('--netlist', type=Path, required=True, help='fresh KiCad XML netlist of the A7 schematic')
    a = ap.parse_args()
    try:
        if a.cmd == 'generate':
            return cmd_generate(a.check)
        if a.cmd == 'reproduce-a5':
            return cmd_reproduce_a5(a.out)
        return cmd_init_board(a.out, a.netlist)
    except authority.Refused as r:
        print(f'refused: {r}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
