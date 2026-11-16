#!/usr/bin/env python3
"""Fail closed on optical-revision source identity, lamination and broad copper.

This is a source-contract check, not native ERC/DRC, factory DFM or optical testing.
"""
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from a7_jlc_package import parse_sexp, kid, kids
from a7_optical_pcb import spec, complement_rectangles


def check_board(path, kind, settings=None):
    settings = settings or spec()
    requirements = settings[kind]
    t = parse_sexp(Path(path).read_text())
    errors = []
    if float(kid(kid(t, 'general'), 'thickness')[1]) != .8:
        errors.append('nominal thickness must be 0.8mm')
    layer_names = [r[1] for r in kid(t, 'layers')[1:] if isinstance(r, list) and r[1].endswith('.Cu')]
    if layer_names != [r['layer'] for r in requirements['stackup'] if r['kind'] == 'copper']:
        errors.append('copper layer order differs from optical stackup')
    stack = kid(kid(t, 'setup'), 'stackup')
    if stack is None:
        errors.append('explicit native stackup missing')
    else:
        layers = [r for r in kids(stack, 'layer') if kid(r, 'thickness') and
                  (r[1].endswith('.Cu') or r[1].startswith('dielectric'))]
        actual = [(kid(r, 'type')[1], float(kid(r, 'thickness')[1])) for r in layers]
        expected = [(r['kind'], r['thickness_mm']) for r in requirements['stackup']]
        if actual != expected:
            errors.append(f'native lamination differs: {actual}')
        if kid(stack, 'copper_finish') != ['copper_finish', settings['surface_finish']]:
            errors.append('surface finish differs')
    allowed = {r['id']: r for r in requirements['local_copper']}
    zones = kids(t, 'zone')
    for z in zones:
        name = kid(z, 'name')
        name = name[1] if name else ''
        row = allowed.get(name)
        if row is None:
            errors.append(f'unjustified zone {name!r}')
            continue
        pts = kid(kid(z, 'polygon'), 'pts')
        xy = [(float(p[1]), float(p[2])) for p in kids(pts, 'xy')]
        bounds = [min(x for x,y in xy), min(y for x,y in xy), max(x for x,y in xy), max(y for x,y in xy)]
        if bounds != row['rect_mm'] or kid(z, 'layer')[1] != row['layer']:
            errors.append(f'local copper {name} extends outside reviewed layer/rectangle')
        netname = kid(z, 'net_name')
        if netname and netname[1] != row['net']:
            errors.append(f'local copper {name} wrong net')
    if len(zones) != len(allowed):
        errors.append('local copper count differs')
    mask_file = Path(path).with_name('optical-mask.json')
    if not mask_file.exists():
        errors.append('mask construction record missing')
    else:
        record = json.loads(mask_file.read_text())
        if record.get('board_sha256') != hashlib.sha256(Path(path).read_bytes()).hexdigest():
            errors.append('mask record is bound to different PCB bytes')
        for layer in ('F.Mask', 'B.Mask'):
            expected = sorted(tuple(r) for r in record['sides'][layer]['open_rectangles_nm'])
            actual = []
            for shape in kids(t, 'gr_rect'):
                if kid(shape, 'layer')[1] == layer:
                    a, b = kid(shape, 'start'), kid(shape, 'end')
                    actual.append(tuple(round(float(v)*1e6) for v in (*a[1:3], *b[1:3])))
                    if kid(shape, 'fill') != ['fill', 'solid']:
                        errors.append(f'{layer} opening not solid')
            if not actual or sorted(actual) != expected:
                errors.append(f'{layer} actual opening rectangles differ from protected-mask construction')
            for a,b,c,d in actual:
                for item in record['sides'][layer]['protected']:
                    e,f,g,h = item['rect_nm']
                    if a < g and c > e and b < h and d > f:
                        errors.append(f'{layer} opening overrides protected {item["id"]}')
                        break
        for shape in kids(t, 'gr_rect') + kids(t, 'gr_poly'):
            if kid(shape, 'layer')[1] in ('F.Paste', 'B.Paste'):
                errors.append('board-level paste opening unexpectedly added')
    return errors


def main():
    s = spec()
    failures = []
    for kind in ('controller', 'led_leaf'):
        p = ROOT / s[kind]['board']
        if not p.is_file():
            failures.append(f'{kind}: candidate missing at {p}')
        else:
            failures.extend(f'{kind}: {x}' for x in check_board(p, kind, s))
    profile = json.loads((ROOT / 'engineering/a7/verification/native_gate.json').read_text())
    if profile['interface']['netlists']['led_leaf'] != 'a7_led_leaf':
        failures.append('native interface still uses A5 leaf instead of optical candidate')
    print(json.dumps({'scope': 'optical source contracts only; native/factory/physical validation separate',
                      'failures': failures}, indent=1))
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
