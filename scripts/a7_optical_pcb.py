#!/usr/bin/env python3
"""Issue #87 optical PCB construction. Writes staging files only, never canonical PCBs.

The mask layers contain OPENINGS. Rectangle subtraction keeps explicit islands around
pads, vias and assembly silk; it never paints an opening over a protected island.
The rectangles are an exact union complement, not a raster approximation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import sys

REPO = Path(__file__).resolve().parents[1]
SPEC = REPO / 'engineering/a7/verification/fab/optical-fr4.json'


def spec():
    return json.loads(SPEC.read_text())


def outside(path):
    path = path.resolve()
    if path == REPO or REPO in path.parents:
        raise ValueError('optical construction writes only staging paths outside the repository')
    return path


def complement_rectangles(bounds, protected):
    """Disjoint rectangles covering bounds minus the union of axis-aligned islands."""
    x0, y0, x1, y1 = bounds
    islands = [(max(x0, a), max(y0, b), min(x1, c), min(y1, d))
               for a, b, c, d in protected if a < x1 and c > x0 and b < y1 and d > y0]
    xs = sorted({x0, x1, *(x for a, b, c, d in islands for x in (a, c))})
    active, result = {}, []
    for a, c in zip(xs, xs[1:]):
        intervals = sorted((b, d) for l, b, r, d in islands if l < c and r > a)
        gaps, end = [], y0
        for b, d in intervals:
            if b > end:
                gaps.append((end, b))
            end = max(end, d)
        if end < y1:
            gaps.append((end, y1))
        now = {}
        for key in gaps:
            old = active.pop(key, None)
            now[key] = (old[0] if old else a, key[0], c, key[1])
        result.extend(active.values())
        active = now
    return sorted(result + list(active.values()))


def trace_corridors(start, end, width, margin, step):
    """Conservative narrow mask around real surface copper, in integer nm.

    Cardinal traces need one rectangle; subdividing diagonals avoids masking the
    empty corners of one large diagonal bounding box. Copper plus 0.10mm margin
    prevents a substrate aperture exposing/bridging tracks of different nets.
    """
    x,y = start
    u,v = end
    count = math.ceil(max(abs(u-x),abs(v-y))/step) if x != u and y != v else 1
    half = width/2 + margin
    for i in range(max(1,count)):
        a,b = x+(u-x)*i/count, y+(v-y)*i/count
        c,d = x+(u-x)*(i+1)/count, y+(v-y)*(i+1)/count
        yield [math.floor(min(a,c)-half), math.floor(min(b,d)-half),
               math.ceil(max(a,c)+half), math.ceil(max(b,d)+half)]


def stackup_text(kind):
    s = spec()[kind]
    entries = ['(stackup', '(layer "F.SilkS" (type "Top Silk Screen"))',
               '(layer "F.Paste" (type "Top Solder Paste"))',
               '(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))']
    dielectric = 0
    for row in s['stackup']:
        if row['kind'] == 'copper':
            entries.append(f'(layer "{row["layer"]}" (type "copper") (thickness {row["thickness_mm"]}))')
        else:
            dielectric += 1
            entries.append(f'(layer "dielectric {dielectric}" (type "{row["kind"]}") '
                           f'(thickness {row["thickness_mm"]}) (material "{row["material"]}") '
                           f'(epsilon_r {row["epsilon_r"]}) (loss_tangent 0.02))')
    entries += ['(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))',
                '(layer "B.Paste" (type "Bottom Solder Paste"))',
                '(layer "B.SilkS" (type "Bottom Silk Screen"))',
                '(copper_finish "ENIG") (dielectric_constraints no))']
    return '\n'.join(entries)


def install_stackup(path, kind):
    """Add the sourced lamination after pcbnew save (SWIG has no stackup editor)."""
    outside(path)
    text = path.read_text()
    if '(stackup' in text:
        start = text.index('(stackup')
        depth, quoted, escaped = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if quoted:
                if escaped:
                    escaped = False
                elif ch == '\\':
                    escaped = True
                elif ch == '"':
                    quoted = False
            elif ch == '"':
                quoted = True
            elif ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0:
                    text = text[:start] + text[i + 1:]
                    break
    text = re.sub(r'(\(general\s*\(thickness )[^)]+', r'\g<1>0.8', text, count=1)
    text = text.replace('(setup', '(setup\n' + stackup_text(kind), 1)
    path.write_text(text)


def apply_mask(board, kind):
    import pcbnew as p
    settings = spec()['mask']
    edge = board.GetBoardEdgesBoundingBox()
    bounds = [edge.GetLeft(), edge.GetTop(), edge.GetRight(), edge.GetBottom()]
    record = {'policy': settings, 'sides': {}}
    def bbox(item, margin):
        b = item.GetBoundingBox()
        return [b.GetLeft() - margin, b.GetTop() - margin, b.GetRight() + margin, b.GetBottom() + margin]
    for name, layer in [('F.Mask', p.F_Mask), ('B.Mask', p.B_Mask)]:
        front = name == 'F.Mask'
        copper, silk = (p.F_Cu, p.F_SilkS) if front else (p.B_Cu, p.B_SilkS)
        protected = []
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                if pad.IsOnLayer(copper):
                    protected.append({'id': f'{fp.GetReference()}.{pad.GetNumber()}',
                                      'reason': 'pad perimeter/dam and solder wicking control; normal pad aperture remains',
                                      'rect_nm': bbox(pad, p.FromMM(settings['pad_margin_mm']))})
            for item in list(fp.GraphicalItems()) + [fp.Reference(), fp.Value()]:
                if item.GetLayer() == silk and (not hasattr(item, 'IsVisible') or item.IsVisible()):
                    protected.append({'id': fp.GetReference() + '.silk', 'reason': 'retain polarity/assembly legend backing',
                                      'rect_nm': bbox(item, p.FromMM(settings['silk_margin_mm']))})
        for t in board.GetTracks():
            if t.GetClass() == 'PCB_VIA':
                protected.append({'id': str(t.m_Uuid.AsString()), 'reason': 'via tenting; opening must not expose hole',
                                  'rect_nm': bbox(t, p.FromMM(settings['via_margin_mm']))})
            elif t.GetLayer() == copper:
                if t.GetClass() != 'PCB_TRACK':
                    raise ValueError('optical mask needs a reviewed corridor rule for nonstraight tracks')
                a,b = t.GetStart(),t.GetEnd()
                for i, rect in enumerate(trace_corridors((a.x,a.y),(b.x,b.y),t.GetWidth(),
                                                        p.FromMM(settings['trace_margin_mm']),
                                                        p.FromMM(settings['diagonal_step_mm']))):
                    protected.append({'id': t.m_Uuid.AsString()+f'.trace.{i}',
                                      'net': t.GetNetname(), 'reason': 'narrow solder isolation over opaque copper; prevents different-net aperture bridges',
                                      'rect_nm': rect})
        for z in board.Zones():
            if z.IsOnLayer(copper):
                protected.append({'id': z.GetZoneName()+'.local-copper', 'net': z.GetNetname(),
                                  'reason': 'solder isolation on justified local copper',
                                  'rect_nm': bbox(z,p.FromMM(settings['trace_margin_mm']))})
        for item in board.GetDrawings():
            if item.GetLayer() == silk:
                protected.append({'id': 'board.silk', 'reason': 'retain board polarity/assembly legend backing',
                                  'rect_nm': bbox(item, p.FromMM(settings['silk_margin_mm']))})
        openings = complement_rectangles(bounds, [x['rect_nm'] for x in protected])
        for a, b, c, d in openings:
            shape = p.PCB_SHAPE(board)
            shape.SetShape(p.SHAPE_T_RECT)
            shape.SetStart(p.VECTOR2I(a, b))
            shape.SetEnd(p.VECTOR2I(c, d))
            shape.SetLayer(layer)
            shape.SetWidth(0)
            shape.SetFilled(True)
            board.Add(shape)
        area = sum((c-a)*(d-b) for a,b,c,d in openings) / 1e12
        record['sides'][name] = {'protected': protected, 'open_rectangles_nm': openings,
                                 'additional_open_area_mm2': round(area, 6),
                                 'note': 'pad apertures are additional openings; this is not optical transmittance'}
    return record


def leaf(out):
    import pcbnew as p
    out = outside(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError('leaf staging must be empty')
    src = REPO / 'engineering/a5/electronics/native/led_leaf'
    shutil.copytree(src, out, dirs_exist_ok=True)
    board_path = out / 'led_leaf.kicad_pcb'
    b = p.LoadBoard(str(board_path))
    b.GetDesignSettings().SetBoardThickness(p.FromMM(0.8))
    record = apply_mask(b, 'led_leaf')
    p.SaveBoard(str(board_path), b)
    install_stackup(board_path, 'led_leaf')
    record.update({'source_a5_sha256': hashlib.sha256((src / board_path.name).read_bytes()).hexdigest(),
                   'board_sha256': hashlib.sha256(board_path.read_bytes()).hexdigest()})
    (out / 'optical-mask.json').write_text(json.dumps(record, indent=1) + '\n')
    # The adopted A7 directory is one level shallower than A5/native/led_leaf.
    (out / 'fp-lib-table').write_text('(fp_lib_table (version 7) (lib (name "LightBlock") (type "KiCad") '
                                    '(uri "${KIPRJMOD}/../../../a5/electronics/footprints/LightBlock.pretty") '
                                    '(options "") (descr "Immutable A5 exact component footprints")))\n')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--leaf-out', type=Path, required=True)
    leaf(ap.parse_args().leaf_out)
