#!/usr/bin/env python3
"""Fail closed on optical-revision source identity, lamination and broad copper.

This is a source-contract check, not native ERC/DRC, factory DFM or optical testing.
"""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from a7_jlc_package import parse_sexp, kid, kids
from a7_optical_pcb import spec, trace_corridors


def pad_signature(pad):
    def canonical(v):
        if v is None:
            return None
        if isinstance(v, list):
            return tuple(canonical(x) for x in v)
        try:
            return float(v)
        except ValueError:
            return v
    def field(name):
        row = kid(pad, name)
        if row is None:
            return None
        def value(v):
            try:
                return float(v)
            except ValueError:
                return v
        return tuple(value(v) for v in row[1:] if not isinstance(v,list))
    return (pad[1],pad[2],pad[3],field('size'),field('drill'),field('roundrect_rratio'),
            field('solder_mask_margin'),field('solder_paste_margin'),field('solder_paste_margin_ratio'),
            canonical(kid(pad, 'options')), canonical(kid(pad, 'primitives')))


def protection_inventory(tree, layer, settings):
    """Derive pad/via islands from PCB geometry, independently of the producer record."""
    required = []
    copper = layer.replace('Mask', 'Cu')
    for fp in kids(tree, 'footprint'):
        ref = next(r[2] for r in kids(fp, 'property') if r[1] == 'Reference')
        at = kid(fp, 'at')
        x, y = map(float, at[1:3])
        angle = math.radians(float(at[3]) if len(at) > 3 else 0)
        c, s = math.cos(angle), math.sin(angle)
        for pad in kids(fp, 'pad'):
            if not {copper, '*.Cu'} & set(kid(pad, 'layers')[1:]):
                continue
            at = kid(pad, 'at')
            u, v = map(float, at[1:3])
            px, py = x+c*u+s*v, y-s*u+c*v
            a = math.radians(float(at[3]) if len(at) > 3 else 0)
            w, h = map(float, kid(pad, 'size')[1:3])
            # Every present pad uses cardinal rotation; reject unreviewed rotated
            # shapes instead of overstating an independently computed bbox.
            if abs(math.sin(2*a)) > 1e-7 or pad[3] not in ('rect', 'roundrect', 'oval', 'circle', 'custom'):
                raise ValueError(f'unsupported pad protection geometry {ref}.{pad[1]}')
            dx = (abs(math.cos(a))*w + abs(math.sin(a))*h)/2 + settings['pad_margin_mm']
            dy = (abs(math.sin(a))*w + abs(math.cos(a))*h)/2 + settings['pad_margin_mm']
            bounds = [px-dx,py-dy,px+dx,py+dy]
            if pad[3] == 'custom':
                # Existing QFN28 copper consists of a circular anchor and stroked,
                # filled polygons. No arbitrary custom primitive is silently accepted.
                for primitive in kid(pad, 'primitives')[1:]:
                    if primitive[0] != 'gr_poly' or kid(primitive,'fill') not in (['fill','yes'],['fill','solid']):
                        raise ValueError(f'unsupported custom pad primitive {ref}.{pad[1]}')
                    pts = [(float(p[1]),float(p[2])) for p in kids(kid(primitive,'pts'),'xy')]
                    pts = [(px+math.cos(a)*u+math.sin(a)*v,py-math.sin(a)*u+math.cos(a)*v) for u,v in pts]
                    margin = float(kid(primitive,'width')[1])/2 + settings['pad_margin_mm']
                    bounds = [min(bounds[0],min(p[0] for p in pts)-margin),
                              min(bounds[1],min(p[1] for p in pts)-margin),
                              max(bounds[2],max(p[0] for p in pts)+margin),
                              max(bounds[3],max(p[1] for p in pts)+margin)]
            required.append((f'{ref}.{pad[1]}', [round(z*1e6) for z in bounds]))
    for via in kids(tree, 'via'):
        x,y = map(float, kid(via, 'at')[1:3])
        half = float(kid(via, 'size')[1])/2 + settings['via_margin_mm']
        required.append((kid(via, 'uuid')[1], [round(z*1e6) for z in (x-half,y-half,x+half,y+half)]))
    for track in kids(tree, 'segment'):
        if kid(track,'layer')[1] != copper:
            continue
        a,b = kid(track,'start'),kid(track,'end')
        start = [round(float(v)*1e6) for v in a[1:3]]
        end = [round(float(v)*1e6) for v in b[1:3]]
        width = round(float(kid(track,'width')[1])*1e6)
        for i,rect in enumerate(trace_corridors(start,end,width,round(settings['trace_margin_mm']*1e6),
                                               round(settings['diagonal_step_mm']*1e6))):
            required.append((kid(track,'uuid')[1]+f'.trace.{i}',rect))
    for zone in kids(tree,'zone'):
        if kid(zone,'layer')[1] != copper:
            continue
        pts = kids(kid(kid(zone,'polygon'),'pts'),'xy')
        xs,ys = [float(p[1]) for p in pts],[float(p[2]) for p in pts]
        margin = settings['trace_margin_mm']
        required.append((kid(zone,'name')[1]+'.local-copper',
                         [round(v*1e6) for v in (min(xs)-margin,min(ys)-margin,max(xs)+margin,max(ys)+margin)]))
    return required


def check_board(path, kind, settings=None):
    settings = settings or spec()
    requirements = settings[kind]
    t = parse_sexp(Path(path).read_text())
    errors = []
    tenting = kid(kid(t,'setup'),'tenting')
    if tenting is None or kid(tenting,'front') != ['front','yes'] or kid(tenting,'back') != ['back','yes']:
        errors.append('both native global via tenting settings must be explicit yes')
    for via in kids(t,'via'):
        # Inherit the explicit global setting; per-via overrides need a separate
        # reviewed policy rather than silently defeating the protected island.
        if any(kid(via,key) is not None for key in ('tenting','solder_mask_margin','remove_unused_layers','keep_end_layers')):
            errors.append('unreviewed per-via mask/tenting override')
    for fp in kids(t,'footprint'):
        lib,name = fp[1].split(':',1)
        libpath = {'LightBlock': ROOT/'engineering/a5/electronics/footprints/LightBlock.pretty',
                   'LightBlockA7': ROOT/'engineering/a7/electronics/footprints/LightBlockA7.pretty'}.get(lib)
        if libpath is None or not (libpath/(name+'.kicad_mod')).is_file():
            errors.append(f'unreviewed footprint copper source {fp[1]}')
        else:
            original = parse_sexp((libpath/(name+'.kicad_mod')).read_text())
            if Counter(pad_signature(p) for p in kids(fp,'pad')) != Counter(pad_signature(p) for p in kids(original,'pad')):
                errors.append(f'pad copper/aperture geometry differs from exact footprint {fp[1]}')
        if any(kid(fp,key) is not None for key in ('solder_mask_margin','solder_paste_margin','solder_paste_ratio')):
            errors.append(f'unreviewed footprint aperture override {fp[1]}')
    for segment in kids(t,'segment') + kids(t,'arc'):
        if float(kid(segment,'width')[1]) > requirements['max_trace_width_mm']:
            errors.append('copper trace wider than reviewed optical policy')
    if kids(t,'arc'):
        errors.append('unreviewed copper arc: mask corridor construction supports straight segments')
    # All graphical copper is forbidden, including footprint graphics. Copper
    # must be electrical pads/tracks/vias or the explicitly named local zones.
    # Mask graphics are exclusively the generated board-level solid rectangles.
    for container in [t, *kids(t, 'footprint')]:
        for item in container[1:]:
            if not isinstance(item, list) or not item:
                continue
            layer = kid(item, 'layer')
            if not layer or item[0] in ('footprint', 'pad', 'segment', 'arc', 'via', 'zone'):
                continue
            if layer[1].endswith('.Cu'):
                errors.append(f'unsupported graphical copper {item[0]} on {layer[1]}')
            if layer[1] in ('F.Mask', 'B.Mask') and not (container is t and item[0] == 'gr_rect'):
                errors.append(f'unsupported mask primitive {item[0]} on {layer[1]}')
            if layer[1] in ('F.Paste', 'B.Paste'):
                errors.append(f'unsupported graphical paste {item[0]} on {layer[1]}')
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
        netname = kid(z, 'net_name') or kid(z, 'net')
        if not netname or netname[1] != row['net']:
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
            inventory = record['sides'][layer]['protected']
            required = protection_inventory(t, layer, settings['mask'])
            available = Counter((r['id'], tuple(r['rect_nm'])) for r in inventory)
            for identity, rect in required:
                # Native KiCad rounds transformed bounds at nm resolution.
                matches = [k for k,n in available.items() if n and k[0] == identity and
                           all(abs(a-b) <= 2 for a,b in zip(k[1],rect))]
                if not matches:
                    errors.append(f'{layer} missing or altered native-derived protection {identity}')
                else:
                    available[matches[0]] -= 1
            expected = sorted(tuple(r) for r in record['sides'][layer]['open_rectangles_nm'])
            actual = []
            for shape in kids(t, 'gr_rect'):
                if kid(shape, 'layer')[1] == layer:
                    a, b = kid(shape, 'start'), kid(shape, 'end')
                    actual.append(tuple(round(float(v)*1e6) for v in (*a[1:3], *b[1:3])))
                    if kid(shape, 'fill') not in (['fill', 'solid'], ['fill', 'yes']):
                        errors.append(f'{layer} opening not solid')
                    stroke = kid(shape, 'stroke')
                    width = kid(stroke, 'width') if stroke else None
                    if width is None or float(width[1]) != 0:
                        errors.append(f'{layer} opening has unaccounted stroke width')
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


def effective_via_tent_errors(path, settings=None, geometry=None):
    """Every via stays tented in the EFFECTIVE native mask, on both faces.

    optical-geometry.json holds the residual mask (outline minus every native opening, generated
    rectangles and ordinary pad apertures alike) of exactly these PCB bytes. A via passes when the disk
    of its copper plus the mask web lies inside one residual polygon, so a component pad aperture that
    overrides a via tent fails here even though the generated rectangles respect their islands.
    """
    settings = settings or spec()
    web = settings['mask']['via_web_mm']
    path = Path(path)
    geometry = geometry or path.with_name('optical-geometry.json')
    if not Path(geometry).is_file():
        return ['effective mask geometry (optical-geometry.json) missing']
    g = json.loads(Path(geometry).read_text())
    if g.get('board_sha256') != hashlib.sha256(path.read_bytes()).hexdigest():
        return ['effective mask geometry is bound to different PCB bytes']
    tree = parse_sexp(path.read_text())
    vias = [(kid(v, 'uuid')[1], float(kid(v, 'at')[1]), float(kid(v, 'at')[2]), float(kid(v, 'size')[1]))
            for v in kids(tree, 'via')]
    errors = []

    def edge_distance(px, py, ring):
        best = math.inf
        for (ax, ay), (bx, by) in zip(ring, ring[1:] + ring[:1]):
            dx, dy = bx - ax, by - ay
            length = dx * dx + dy * dy
            t = 0.0 if length == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length))
            best = min(best, math.hypot(px - ax - t * dx, py - ay - t * dy))
        return best

    def inside(px, py, ring):
        hit = False
        for (ax, ay), (bx, by) in zip(ring, ring[1:] + ring[:1]):
            if (ay > py) != (by > py) and px < ax + (py - ay) * (bx - ax) / (by - ay):
                hit = not hit
        return hit

    for name in ('F.Mask', 'B.Mask'):
        layers = [l for l in g['layers'] if l['layer'] == name and l['material'] == 'mask']
        if len(layers) != 1:
            errors.append(f'{name} residual mask missing from effective geometry')
            continue
        polygons = []
        for polygon in layers[0]['polygons']:
            xs, ys = [p[0] for p in polygon['outer']], [p[1] for p in polygon['outer']]
            polygons.append((min(xs), min(ys), max(xs), max(ys), polygon))
        for uuid, x, y, size in vias:
            need = size / 2 + web
            # The exporter also cuts drilled holes out of the contour. The via's own drill is not a
            # mask opening, so probe on its copper ring and ignore that one hole.
            probe = (x + size / 2 - 1e-4, y)
            home = [p for a, b, c, d, p in polygons if a <= probe[0] <= c and b <= probe[1] <= d
                    and inside(*probe, p['outer']) and not any(inside(*probe, h) for h in p['holes'])]
            if not home:
                errors.append(f'{name} effective opening exposes via {uuid} at ({x}, {y})')
                continue
            rings = [home[0]['outer']] + [h for h in home[0]['holes']
                                          if max(math.hypot(q[0] - x, q[1] - y) for q in h) > size / 2]
            gap = min(edge_distance(x, y, ring) for ring in rings) - size / 2
            if gap < web - 1e-6:
                errors.append(f'{name} effective opening leaves {gap:.4f} mm of mask at via {uuid} at ({x}, {y}); need {web}')
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
            failures.extend(f'{kind}: {x}' for x in effective_via_tent_errors(p, s))
    profile = json.loads((ROOT / 'engineering/a7/verification/native_gate.json').read_text())
    if profile['interface']['netlists']['led_leaf'] != 'a7_led_leaf':
        failures.append('native interface still uses A5 leaf instead of optical candidate')
    print(json.dumps({'scope': 'optical source contracts only; native/factory/physical validation separate',
                      'failures': failures}, indent=1))
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
