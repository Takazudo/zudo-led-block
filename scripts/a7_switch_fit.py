#!/usr/bin/env python3
"""Compare the routed SW1 land (LightBlockA7:PCM13SMTR) with the fitted switch's recommended land and leads.

Inputs: the A7 footprint file and the HX MSK13C02 owner-bundle facts (recommended-land, outline).
Output: engineering/a7/electronics/switch-land-fit.json. A digital comparison of nominal,
untoleranced drawing values; it is not a fit approval (switch-fit stays a physical check).

  python3 scripts/a7_switch_fit.py            write the report
  python3 scripts/a7_switch_fit.py --check    fail if the committed report is stale or a criterion fails
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FOOTPRINT = REPO / 'engineering/a7/electronics/footprints/LightBlockA7.pretty/PCM13SMTR.kicad_mod'
FACTS = REPO / '.claude/skills/component-a7-hx-msk13c02/facts.json'
OUT = REPO / 'engineering/a7/electronics/switch-land-fit.json'
PREFIX = 'fact-a7-hx-msk13c02-'


def fact(facts, name):
    return next(f['value'] for f in facts if f['fact_id'] == PREFIX + name)


def pads(text):
    out = []
    for m in re.finditer(r'\(pad "([^"]*)" (smd|np_thru_hole) \w+ \(at ([-\d.]+) ([-\d.]+)\) \(size ([-\d.]+) ([-\d.]+)\)', text):
        num, kind, x, y, w, h = m.groups()
        out.append({'pad': num, 'kind': kind, 'x': float(x), 'y': float(y), 'w': float(w), 'h': float(h)})
    return out


def span(c, size):
    return (round(c - size / 2, 4), round(c + size / 2, 4))


def overlap(a, b):
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def r(v):
    return round(v, 4)


def build():
    fp_text = FOOTPRINT.read_text()
    facts = json.loads(FACTS.read_text())['facts']
    land, outline = fact(facts, 'recommended-land'), fact(facts, 'outline')
    P = pads(fp_text)
    holes = [p for p in P if p['kind'] == 'np_thru_hole']
    signal = {p['pad']: p for p in P if p['kind'] == 'smd' and p['pad']}
    retention = [p for p in P if p['kind'] == 'smd' and not p['pad']]
    if len(holes) != 2 or sorted(signal) != ['1', '2', '3', '4'] or len(retention) != 4:
        raise ValueError('footprint pads not read: need 2 holes, signal pads 1-4 and 4 retention pads')
    peg_y = holes[0]['y']
    side = -1 if signal['1']['y'] < peg_y else 1  # signal pads lie on this side of the peg line
    rows, ok = [], True

    def check(what, value, passed, note):
        nonlocal ok
        ok = ok and passed
        rows.append({'check': what, 'value': value, 'pass': passed, 'note': note})

    check('hole positions and diameter', {'a7': sorted([r(h['x']) for h in holes]) + [holes[0]['w']],
                                          'maker': [-land['hole_pitch'] / 2, land['hole_pitch'] / 2, land['hole_diameter']]},
          sorted(r(h['x']) for h in holes) == [-land['hole_pitch'] / 2, land['hole_pitch'] / 2]
          and all(h['w'] == land['hole_diameter'] for h in holes) and all(h['y'] == peg_y for h in holes),
          'pegs dia %.2f in dia %.2f holes' % (outline['peg_diameter'], land['hole_diameter']))
    mk_sig = [land['signal_pad_near_edge_from_peg_line'], land['signal_pad_far_edge_from_peg_line']]
    for num in '1234':
        x = land[f'signal_pad_{num}_x']
        p = signal[num]
        a7 = tuple(sorted(side * (v - peg_y) for v in span(p['y'], p['h'])))
        cover_y = overlap(a7, mk_sig) / (mk_sig[1] - mk_sig[0])
        cover_x = overlap(span(p['x'], p['w']), span(x, land['signal_pad_width'])) / land['signal_pad_width']
        centre = (mk_sig[0] + mk_sig[1]) / 2
        lead = (outline['peg_line_to_body_edges'], outline['peg_line_to_body_edges'] + outline['terminal_protrusion_beyond_body'])
        lead_x = span(x, outline['terminal_width'])
        on_pad = a7[0] <= lead[0] and lead[1] <= a7[1] and span(p['x'], p['w'])[0] <= lead_x[0] and lead_x[1] <= span(p['x'], p['w'])[1]
        check(f'signal pad {num}', {'a7_from_peg_line': [r(v) for v in a7], 'maker_from_peg_line': mk_sig,
                                    'maker_area_covered': r(cover_x * cover_y), 'toe': r(a7[1] - lead[1]), 'heel': r(lead[0] - a7[0])},
              a7[0] <= centre <= a7[1] and abs(p['x'] - x) < 1e-6 and on_pad,
              'maker pad centre inside the A7 pad; terminal %.2f..%.2f off the peg line wholly on the pad' % lead)
    cy = land['retention_pad_centre_y']
    mk_ret_y = span(cy, land['retention_pad_height_y'])
    for p in sorted(retention, key=lambda q: (q['x'], q['y'])):
        a7 = tuple(sorted(abs(v - peg_y) for v in span(p['y'], p['h'])))
        mk_x = span(land['retention_pad_centre_x'] * (1 if p['x'] > 0 else -1), land['retention_pad_width_x'])
        cover = overlap(a7, mk_ret_y) / land['retention_pad_height_y'] * overlap(span(p['x'], p['w']), mk_x) / land['retention_pad_width_x']
        check(f'retention pad at x {r(p["x"])} y {r(p["y"])}', {'a7_abs_from_peg_line': [r(v) for v in a7], 'maker_abs_from_peg_line': list(mk_ret_y),
                                                              'maker_area_covered': r(cover)},
              a7[0] <= cy <= a7[1] and abs(abs(p['x']) - land['retention_pad_centre_x']) < 1e-6,
              'maker pad centre inside the A7 pad')
    actuator_tip = r(outline['peg_line_to_body_edges'] + outline['actuator_projection_beyond_body'])
    return {
        'schema': 'a7-switch-land-fit/1',
        'status': 'DIGITAL_COMPARISON_ONLY',
        'meaning': 'Nominal, untoleranced drawing values compared with the routed land. Not a fit approval; switch-fit (physical) stays NOT_RUN.',
        'part': 'hanxia HX MSK13C02 (C5149819)',
        'land': 'LightBlockA7:PCM13SMTR (routed SW1 land, unchanged)',
        'inputs': {str(FOOTPRINT.relative_to(REPO)): hashlib.sha256(FOOTPRINT.read_bytes()).hexdigest(),
                   str(FACTS.relative_to(REPO)): hashlib.sha256(FACTS.read_bytes()).hexdigest()},
        'checks': rows,
        'all_pass': ok,
        'actuator_tip_from_peg_line': actuator_tip,
        'pcm13smtr_actuator_tip_from_peg_line': 2.8,
        'actuator_tip_change_toward_board_edge': r(actuator_tip - 2.8),
        'pad_numbering': 'INFERRED: the Hanxia drawing does not number the land; terminal 1 at x -3.0 comes from the EasyEDA supplier CAD only. '
                         'A mirrored part would put common terminal 3 on NC pad 2 (SW1 reads PROGRAM in every position); checked on the first assembled boards (switch-fit).',
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    report = build()
    text = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
    if a.check:
        if not OUT.is_file() or OUT.read_text() != text:
            print('FAIL: switch-land-fit.json is stale; run python3 scripts/a7_switch_fit.py')
            return 1
        if not report['all_pass']:
            print('FAIL: a land-fit criterion fails')
            return 1
        print('PASS: switch land fit (digital comparison only)')
        return 0
    OUT.write_text(text)
    print('WROTE', OUT.relative_to(REPO), 'all_pass', report['all_pass'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
