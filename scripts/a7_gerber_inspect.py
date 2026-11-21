#!/usr/bin/env python3
"""Check the EFFECTIVE mask and paste geometry of actually exported Gerbers against the board.

Reads the plotted Gerber primitives (Gerbonara, see engineering/a7/verification/optical/tools/) and the
board's vias and pads, with nothing taken from the mask construction record:

  * via tent: on both mask files every via keeps `--web` mm of mask beyond its copper. A mask shape is an
    opening, whether it is a generated board rectangle or a component pad aperture, so a pad opening that
    overrides a via tent fails here;
  * paste: every paste shape is a flash centred on a pad of that face, and no drawn region or line exists;
  * a coarse coverage grid per layer and a greyscale overview image, as inspection aids only.

This is a review of plotted geometry. It is not DRC, a fabricator DFM result or an optical measurement.

Usage: a7_gerber_inspect.py --board B --gerbers DIR --out DIR [--web 0.1] [--pixels-per-mm 20]
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import zlib

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from a7_jlc_package import parse_sexp, kid, kids


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seg_distance(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    length = dx * dx + dy * dy
    t = 0.0 if length == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def inside_polygon(px, py, pts):
    hit = False
    for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
        if (ay > py) != (by > py) and px < ax + (py - ay) * (bx - ax) / (by - ay):
            hit = not hit
    return hit


class Shape:
    """One dark plotted primitive with a signed distance (negative inside)."""

    def __init__(self, primitive):
        name = type(primitive).__name__
        self.kind = name
        if name == 'Circle':
            self.data = (primitive.x, primitive.y, primitive.r)
            self.box = (primitive.x - primitive.r, primitive.y - primitive.r, primitive.x + primitive.r, primitive.y + primitive.r)
        elif name == 'Rectangle':
            c, s = math.cos(primitive.rotation), math.sin(primitive.rotation)
            w, h = primitive.w / 2, primitive.h / 2
            pts = [(primitive.x + c * u - s * v, primitive.y + s * u + c * v) for u, v in ((-w, -h), (w, -h), (w, h), (-w, h))]
            self.kind, self.data = 'Polygon', pts
        elif name == 'ArcPoly':
            if any(a is not None for a in primitive.arc_centers):
                raise ValueError('plotted region with arcs is not supported by this review')
            pts = [tuple(p) for p in primitive.outline]
            if pts and pts[0] == pts[-1]:
                pts = pts[:-1]
            self.kind, self.data = 'Polygon', pts
        elif name == 'Line':
            self.data = (primitive.x1, primitive.y1, primitive.x2, primitive.y2, primitive.width / 2)
            r = primitive.width / 2
            self.box = (min(primitive.x1, primitive.x2) - r, min(primitive.y1, primitive.y2) - r,
                        max(primitive.x1, primitive.x2) + r, max(primitive.y1, primitive.y2) + r)
        else:
            raise ValueError(f'unsupported plotted primitive {name}')
        if self.kind == 'Polygon':
            xs, ys = [p[0] for p in self.data], [p[1] for p in self.data]
            self.box = (min(xs), min(ys), max(xs), max(ys))

    def distance(self, px, py):
        if self.kind == 'Circle':
            x, y, r = self.data
            return math.hypot(px - x, py - y) - r
        if self.kind == 'Line':
            x1, y1, x2, y2, r = self.data
            return seg_distance(px, py, x1, y1, x2, y2) - r
        pts = self.data
        d = min(seg_distance(px, py, ax, ay, bx, by) for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]))
        return -d if inside_polygon(px, py, pts) else d


def load(path):
    from gerbonara import GerberFile
    from gerbonara.utils import MM
    gerber = GerberFile.open(path)
    shapes, flashes, others = [], [], 0
    for obj in gerber.objects:
        if not obj.polarity_dark:
            raise ValueError(f'{path.name}: clear-polarity object; this review assumes dark-only plots')
        own = [Shape(p) for p in obj.to_primitives(MM)]
        shapes += own
        if type(obj).__name__ == 'Flash':
            flashes.append((MM.convert_from(obj.unit, obj.x), MM.convert_from(obj.unit, obj.y)))
        else:
            others += 1
    return gerber, shapes, flashes, others


class Buckets:
    def __init__(self, shapes, cell=1.0):
        self.cell, self.map = cell, {}
        for s in shapes:
            for i in range(math.floor(s.box[0] / cell), math.floor(s.box[2] / cell) + 1):
                for j in range(math.floor(s.box[1] / cell), math.floor(s.box[3] / cell) + 1):
                    self.map.setdefault((i, j), []).append(s)

    def near(self, x, y, r):
        seen, out = set(), []
        for i in range(math.floor((x - r) / self.cell), math.floor((x + r) / self.cell) + 1):
            for j in range(math.floor((y - r) / self.cell), math.floor((y + r) / self.cell) + 1):
                for s in self.map.get((i, j), []):
                    if id(s) not in seen:
                        seen.add(id(s))
                        out.append(s)
        return out

    def covered(self, x, y):
        return any(s.box[0] <= x <= s.box[2] and s.box[1] <= y <= s.box[3] and s.distance(x, y) <= 0
                   for s in self.map.get((math.floor(x / self.cell), math.floor(y / self.cell)), []))


def board_items(path):
    tree = parse_sexp(path.read_text())
    vias = [{'uuid': kid(v, 'uuid')[1], 'net': (kid(v, 'net') or [None, None])[1],
             'x': float(kid(v, 'at')[1]), 'y': float(kid(v, 'at')[2]), 'size': float(kid(v, 'size')[1]),
             'drill': float(kid(v, 'drill')[1])} for v in kids(tree, 'via')]
    pads = []
    for fp in kids(tree, 'footprint'):
        ref = next(r[2] for r in kids(fp, 'property') if r[1] == 'Reference')
        at = kid(fp, 'at')
        x, y = float(at[1]), float(at[2])
        angle = math.radians(float(at[3]) if len(at) > 3 else 0)
        c, s = math.cos(angle), math.sin(angle)
        for pad in kids(fp, 'pad'):
            u, v = map(float, kid(pad, 'at')[1:3])
            pads.append({'id': f'{ref}.{pad[1]}', 'x': x + c * u + s * v, 'y': y - s * u + c * v,
                         'layers': kid(pad, 'layers')[1:]})
    xs, ys = [], []
    for kind in ('gr_line', 'gr_rect'):
        for item in kids(tree, kind):
            if kid(item, 'layer')[1] == 'Edge.Cuts':
                for key in ('start', 'end'):
                    xs.append(float(kid(item, key)[1]))
                    ys.append(float(kid(item, key)[2]))
    return vias, pads, (min(xs), min(ys), max(xs), max(ys))


def png(path, rows):
    """8-bit greyscale PNG from rows of bytes (stdlib only)."""
    raw = b''.join(b'\x00' + bytes(r) for r in rows)

    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', len(rows[0]), len(rows), 8, 0, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def inspect(board, gerbers, out, web, ppm):
    vias, pads, (x0, y0, x1, y1) = board_items(board)
    files = sorted(p for p in gerbers.iterdir() if p.is_file())
    report = {'method': 'Gerbonara primitives of the actual plotted files; exact via-disk and paste-flash tests; '
                        f'{ppm} sample/mm coverage grid over the rectangular outline bounds as an inspection aid',
              'inspect_script': 'scripts/a7_gerber_inspect.py', 'inspect_script_sha256': sha256(Path(__file__)),
              'board': board.name, 'board_sha256': sha256(board), 'outline_bounds_mm': [x0, y0, x1, y1],
              'via_count': len(vias), 'via_web_mm': web, 'layers': {}, 'failures': []}
    nx, ny = round((x1 - x0) * ppm), round((y1 - y0) * ppm)
    panels, order = {}, []
    for path in files:
        gerber, shapes, flashes, others = load(path)
        function = gerber.file_attrs.get('.FileFunction', ('',))
        buckets = Buckets(shapes)
        row = {'sha256': sha256(path), 'function': list(function), 'primitives': len(shapes), 'flashes': len(flashes),
               'non_flash_objects': others}
        if function[0] == 'Profile':
            report['layers'][path.name] = row
            continue
        grid = [[buckets.covered(x0 + (i + .5) / ppm, -(y0 + (j + .5) / ppm)) for i in range(nx)] for j in range(ny)]
        row['dark_coverage_fraction_of_bounds'] = sum(map(sum, grid)) / (nx * ny)
        if function[0] == 'Soldermask':
            face = 'F.Cu' if function[1] == 'Top' else 'B.Cu'
            worst, exposed = math.inf, []
            for via in vias:
                need = via['size'] / 2 + web
                near = buckets.near(via['x'], -via['y'], need + .01)
                gap = min((s.distance(via['x'], -via['y']) for s in near), default=math.inf) - via['size'] / 2
                worst = min(worst, gap)
                if gap < web - 1e-6:
                    exposed.append({'via': via['uuid'], 'net': via['net'], 'xy_mm': [via['x'], via['y']],
                                    'mask_web_to_via_copper_mm': round(gap, 4)})
            row.update({'opening_coverage_note': 'dark shapes are OPENINGS; residual mask is the complement',
                        'residual_mask_fraction_of_bounds': 1 - row['dark_coverage_fraction_of_bounds'],
                        'via_tent': {'face': face, 'checked': len(vias), 'smallest_mask_web_to_via_copper_mm':
                                     None if math.isinf(worst) else round(worst, 4), 'exposed_or_under_web': exposed}})
            if exposed:
                report['failures'].append(f'{path.name}: {len(exposed)} via tents overridden or closer than {web} mm to an opening')
            grid = [[not v for v in r] for r in grid]   # show retained mask
        if function[0] == 'Paste':
            face = 'F.Paste' if function[1] == 'Top' else 'B.Paste'
            allowed = {(round(p['x'], 4), round(-p['y'], 4)) for p in pads if face in p['layers']}
            stray = [xy for xy in flashes if (round(xy[0], 4), round(xy[1], 4)) not in allowed]
            row['paste'] = {'pads_with_paste_on_face': len(allowed), 'flashes_off_pad_centres': len(stray)}
            if others or stray:
                report['failures'].append(f'{path.name}: paste is not pad flashes only ({others} drawn objects, {len(stray)} stray flashes)')
        if function[0] == 'Copper':
            row['drawn_region_objects'] = sum(1 for o in gerber.objects if type(o).__name__ == 'Region')
        report['layers'][path.name] = row
        if function[0] in ('Copper', 'Soldermask', 'Paste'):
            panels[path.name] = grid
            order.append(path.name)
    if panels:
        gap = 6
        rows = []
        for j in range(ny):
            line = []
            for name in order:
                line += [0 if v else 255 for v in panels[name][j]] + [128] * gap
            rows.append(line[:-gap])
        out.mkdir(parents=True, exist_ok=True)
        png(out / 'overview.png', rows)
        report['overview'] = {'file': 'overview.png', 'left_to_right': order,
                              'legend': 'black = copper, paste, or RETAINED mask (mask panels are inverted openings); '
                                        'white = no copper / paste, or mask opening; rectangular bounds, holes not subtracted'}
    out.mkdir(parents=True, exist_ok=True)
    (out / 'raster-inspection.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--board', type=Path, required=True)
    parser.add_argument('--gerbers', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--web', type=float, default=0.1)
    parser.add_argument('--pixels-per-mm', type=int, default=20)
    args = parser.parse_args()
    report = inspect(args.board, args.gerbers, args.out, args.web, args.pixels_per_mm)
    print(json.dumps({'failures': report['failures'],
                      'via_tent': {k: v['via_tent'] | {'exposed_or_under_web': len(v['via_tent']['exposed_or_under_web'])}
                                   for k, v in report['layers'].items() if 'via_tent' in v},
                      'paste': {k: v['paste'] for k, v in report['layers'].items() if 'paste' in v}}, indent=1))
    return 1 if report['failures'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
