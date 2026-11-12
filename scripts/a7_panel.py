#!/usr/bin/env python3
"""Repo-built JLC assembly panels for the 2-unit first build. A prepared route, NOT a release.

plan (default) reads the JLC package report (scripts/a7_jlc_package.py) and writes, for each board, a panel layout
(engineering/a7/jlc-package/panels/<board>-panel.json) and the panel BOM / CPL in JLC's columns. --check compares them.

build --out DIR runs the pinned KiCad image on read-only frozen boards. It builds each panel from its layout, then
checks it: every embedded board matches its frozen source (pads, tracks, vias, zones, drills, outline), panel DRC adds
no violation to the source's own, KiCad's position export matches the panel CPL. It writes panel boards, Gerber and
drill zips and a summary into DIR (outside the repository). The frozen board files are never written.

Which route the owner takes (repo panels or Panel by JLCPCB) is the owner decision assembly:panel-route.
"""
import argparse
import collections
import csv
import importlib.util
import io
import json
import math
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
OUT = Path('engineering/a7/jlc-package/panels')
PROFILE = 'engineering/a7/verification/native_gate.json'
LABEL = 'zudo-led-block.a7-panel'
# JLC rules (engineering/a7/jlc-package/sources.json, jlc-pcb-capabilities): 5 mm tooling edges, 2 mm tooling holes,
# 1 mm fiducials centred 3.85 mm from the panel edges, >= 2 mm board spacing, mouse-bite tabs >= 5 mm wide,
# mouse-bite holes 0.5-0.8 mm with 0.2-0.3 mm between holes.
TAB_MM = 5.0
BITE_D_MM = 0.6
BITE_GAP_MM = 0.25
FIDUCIAL_MM = 1.0
FIDUCIAL_INSET_MM = 3.85
TOOLING_HOLE_MM = 2.0
# PROPOSED, not JLC values: fiducial mask opening, tooling-hole inset (rail centre), keep tabs this far from parts.
FIDUCIAL_MASK_MM = 2.0
TOOLING_INSET_MM = 2.5
TAB_PART_CLEARANCE_MM = 1.0
# Mouse-bite holes sit tangent to the board edge on the tab side, so no hole cuts into the frozen board (nubs remain, as
# JLC notes: "Serrated edges will remain after depanelization").
BITE_OFFSET_MM = BITE_D_MM / 2


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fmt(v):
    v = round(v, 4)
    return f'{v:.4f}'.rstrip('0').rstrip('.') if v != int(v) else str(int(v))


# --- layout (pure Python, deterministic) ----------------------------------------------------------------
def free_spans(length, blocked):
    """Intervals of [0, length] not covered by the blocked intervals."""
    spans, at = [], 0.0
    for a, b in sorted(blocked):
        if a > at:
            spans.append((at, min(a, length)))
        at = max(at, b)
    if at < length:
        spans.append((at, length))
    return [(a, b) for a, b in spans if b - a > 1e-9]


def place_tabs(length, blocked, wanted):
    """Tab centres along an edge: as close as allowed to the wanted fractions, each tab fully inside a free span."""
    spans = [(a + TAB_MM / 2, b - TAB_MM / 2) for a, b in free_spans(length, blocked) if b - a >= TAB_MM]
    out = []
    for f in wanted:
        target = f * length
        best = None
        for a, b in spans:
            c = min(max(target, a), b)
            if best is None or abs(c - target) < abs(best - target):
                best = c
        if best is not None and all(abs(best - o) >= TAB_MM + 2 for o in out):
            out.append(round(best, 3))
    return sorted(out)


def edge_blocks(b, facts, fitted, courtyards=True):
    """Per edge of the board outline, the spans a tab must avoid: parts (courtyards, or pads only) within the clearance of
    that edge, and outline notches."""
    w, h = b['outline_mm']['width'], b['outline_mm']['height']
    x0, y0 = facts['outline_mm']['x'][0], facts['outline_mm']['y'][0]
    blocks = {'top': [], 'bottom': [], 'left': [], 'right': []}
    c = TAB_PART_CLEARANCE_MM
    for f in facts['footprints']:
        pads = [pad_to_board(f, (q[0], q[1])) for q in f['pads']] + [pad_to_board(f, (q[2], q[3])) for q in f['pads']]
        pts = (f['courtyard'] if courtyards else None) or pads
        if f['ref'] not in fitted or not pts:
            continue
        xs, ys = [p[0] - x0 for p in pts], [p[1] - y0 for p in pts]
        if min(ys) < c:
            blocks['top'].append((min(xs) - c, max(xs) + c))
        if max(ys) > h - c:
            blocks['bottom'].append((min(xs) - c, max(xs) + c))
        if min(xs) < c:
            blocks['left'].append((min(ys) - c, max(ys) + c))
        if max(xs) > w - c:
            blocks['right'].append((min(ys) - c, max(ys) + c))
    # outline points off the bounding box (notches) block the edge they cut into
    for kind, a, e in facts.get('edges', []):
        for x, y in (a, e):
            x, y = x - x0, y - y0
            if 1e-6 < x < w - 1e-6 and 1e-6 < y < h - 1e-6:
                side = min((('left', x), ('right', w - x), ('top', y), ('bottom', h - y)), key=lambda t: t[1])[0]
                along = y if side in ('left', 'right') else x
                blocks[side].append((along - c, along + c))
    return blocks


def pad_to_board(f, xy):
    """A pad-box corner (footprint frame) in board coordinates; the box is axis-aligned in the footprint frame."""
    a = math.radians(f['rot'])
    return (f['x'] + xy[0] * math.cos(a) + xy[1] * math.sin(a), f['y'] - xy[0] * math.sin(a) + xy[1] * math.cos(a))


def tab_plan(c, n, w, h, blocks):
    """(edge, centre along the edge, edge length) for one copy; edges facing another copy get no tab."""
    out = []
    for edge in ('top', 'bottom', 'left', 'right'):
        if (edge == 'right' and c['copy'] < n) or (edge == 'left' and c['copy'] > 1):
            continue
        length = w if edge in ('top', 'bottom') else h
        out += [(edge, t, length) for t in place_tabs(length, blocks[edge], [0.5] if length < 25 else [0.2, 0.8])]
    return out


def bites(length):
    pitch = BITE_D_MM + BITE_GAP_MM
    n = int((TAB_MM - BITE_D_MM) // pitch) + 1
    start = -(n - 1) * pitch / 2
    return [round(start + i * pitch, 4) for i in range(n)]


def layout(b, facts, fitted):
    rp = b['repo_panel']
    w, h = b['outline_mm']['width'], b['outline_mm']['height']
    x0, y0 = facts['outline_mm']['x'][0], facts['outline_mm']['y'][0]
    g, rail = rp['edge_gap_mm'], rp['rail_mm']
    W, H = rp['panel_mm']
    between = rp['between_copies_mm'] or 0.0
    copies = []
    for k in range(rp['copies']):
        ox = rail + g['left'] + k * (w + between)
        oy = rail + g['top']
        copies.append({'copy': k + 1, 'suffix': '' if k == 0 else f'_{k + 1}', 'offset_mm': [round(ox - x0, 4), round(oy - y0, 4)],
                       'outline_mm': [round(ox, 4), round(oy, 4), round(ox + w, 4), round(oy + h, 4)],
                       'slot_mm': [round(ox - (g['left'] if k == 0 else between / 2), 4), round(oy - g['top'], 4),
                                   round(ox + w + (g['right'] if k == rp['copies'] - 1 else between / 2), 4), round(oy + h + g['bottom'], 4)]})
    strict, relaxed = edge_blocks(b, facts, fitted), edge_blocks(b, facts, fitted, courtyards=False)
    tabs, holes, notes, waivers = [], [], list(rp['notes']), {}
    for c in copies:
        bx0, by0, bx1, by1 = c['outline_mm']
        sx0, sy0, sx1, sy1 = c['slot_mm']
        blocks = strict
        if len(tab_plan(c, len(copies), w, h, strict)) < 2:
            blocks = relaxed
            waivers['npth_inside_courtyard'] = ('mouse-bite holes of a pad-placed tab lie inside the courtyard of a part body that overhangs '
                                                'the board edge; the holes are outside the frozen board outline')
            notes.append(f"Copy {c['copy']}: fewer than 2 tabs fit outside the part courtyards, so its tabs keep {TAB_PART_CLEARANCE_MM:g} mm from pads only "
                         'and may sit under a part body that overhangs the edge.')
        for edge, t, length in tab_plan(c, len(copies), w, h, blocks):
            if edge in ('top', 'bottom'):
                cx = bx0 + t
                y_edge = by0 if edge == 'top' else by1
                rect = [cx - TAB_MM / 2, sy0 if edge == 'top' else by1, cx + TAB_MM / 2, by0 if edge == 'top' else sy1]
                out = -BITE_OFFSET_MM if edge == 'top' else BITE_OFFSET_MM
                holes += [[round(cx + d, 4), round(y_edge + out, 4)] for d in bites(length)]
            else:
                cy = by0 + t
                x_edge = bx0 if edge == 'left' else bx1
                rect = [sx0 if edge == 'left' else bx1, cy - TAB_MM / 2, bx0 if edge == 'left' else sx1, cy + TAB_MM / 2]
                out = -BITE_OFFSET_MM if edge == 'left' else BITE_OFFSET_MM
                holes += [[round(x_edge + out, 4), round(cy + d, 4)] for d in bites(length)]
            tabs.append({'copy': c['copy'], 'edge': edge, 'rect_mm': [round(v, 4) for v in rect]})
    fiducials = [[round(W * 0.3, 3), FIDUCIAL_INSET_MM], [round(W * 0.7, 3), FIDUCIAL_INSET_MM], [round(W * 0.3, 3), round(H - FIDUCIAL_INSET_MM, 3)]]
    tooling = [[TOOLING_INSET_MM + 1, TOOLING_INSET_MM], [round(W - TOOLING_INSET_MM - 1, 3), TOOLING_INSET_MM],
               [TOOLING_INSET_MM + 1, round(H - TOOLING_INSET_MM, 3)]]
    per_edge = collections.Counter((t['copy'], t['edge']) for t in tabs)
    return {'board': b['board'], 'pcb': b['pcb'], 'pcb_sha256': b['pcb_sha256'], 'tier': rp['tier'], 'panel_mm': [W, H],
            'copies': copies, 'tabs': tabs, 'tabs_per_copy': {str(c['copy']): sum(v for (k, _), v in per_edge.items() if k == c['copy']) for c in copies},
            'mouse_bites': {'diameter_mm': BITE_D_MM, 'gap_mm': BITE_GAP_MM, 'centres_mm': holes},
            'fiducials': {'diameter_mm': FIDUCIAL_MM, 'mask_opening_mm': FIDUCIAL_MASK_MM, 'sides': sorted({'F', 'B'} if 'Bottom' in b['assembly_sides'] else {'F'}), 'centres_mm': fiducials},
            'tooling_holes': {'diameter_mm': TOOLING_HOLE_MM, 'centres_mm': tooling},
            'rules': {'rail_mm': rail, 'edge_gap_mm': g, 'between_copies_mm': rp['between_copies_mm'], 'tab_mm': TAB_MM,
                      'tab_part_clearance_mm': TAB_PART_CLEARANCE_MM, 'proposed': ['fiducial mask opening', 'tooling-hole inset', 'tab part clearance', 'overhang margin']},
            'drc_waivers': waivers, 'notes': notes}


def plan(root=ROOT):
    jlc = load('a7_jlc_package', 'scripts/a7_jlc_package.py')
    report, _ = jlc.generate(root)
    ledger = json.loads((root / jlc.LEDGER).read_text())
    files = {}
    for b in report['boards']:
        facts = jlc.board_facts(b['pcb'])
        facts['edges'] = edges_of(jlc, b['pcb'])
        fitted = {r['ref']: r for r in ledger['population'] if r['board'] == b['board'] and r['population'] == 'FITTED'}
        lay = layout(b, facts, fitted)
        n = b['board']
        files[f'{n}-panel.json'] = json.dumps(lay, indent=2) + '\n'
        cpl, bom = [], {}
        for c in lay['copies']:
            dx, dy = c['offset_mm']
            for f in sorted((f for f in facts['footprints'] if f['ref'] in fitted), key=lambda f: ref_key(f['ref'])):
                ref = f['ref'] + c['suffix']
                cpl.append({'Designator': ref, 'Mid X': fmt(f['x'] + dx), 'Mid Y': fmt(-(f['y'] + dy)), 'Rotation': fmt(jlc.norm_rot(f['rot'])),
                            'Layer': 'Top' if f['layer'] == 'F.Cu' else 'Bottom'})
                key = (fitted[f['ref']]['lcsc'], f['footprint'].split(':')[-1])
                bom.setdefault(key, {'Comment': f['value'], 'Designator': [], 'Footprint': key[1], 'JLCPCB Part #': key[0]})['Designator'].append(ref)
        files[f'{n}-panel_CPL_DRYRUN.csv'] = jlc.to_csv(['Designator', 'Mid X', 'Mid Y', 'Rotation', 'Layer'], cpl)
        files[f'{n}-panel_BOM_DRYRUN.csv'] = jlc.to_csv(['Comment', 'Designator', 'Footprint', 'JLCPCB Part #'],
                                                         [dict(v, Designator=','.join(v['Designator'])) for v in bom.values()])
    return files


def edges_of(jlc, pcb):
    tree = jlc.parse_sexp((ROOT / pcb).read_text())
    out = []
    for g in tree[1:]:
        if isinstance(g, list) and g and str(g[0]).startswith('gr_') and jlc.kid(g, 'layer') and jlc.kid(g, 'layer')[1] == 'Edge.Cuts':
            if jlc.kid(g, 'start') and jlc.kid(g, 'end'):
                out.append((g[0], tuple(jlc.nums(jlc.kid(g, 'start'))[:2]), tuple(jlc.nums(jlc.kid(g, 'end'))[:2])))
    return out


def ref_key(r):
    return (re.sub(r'\d+', '', r), int(re.sub(r'\D', '', r) or 0))


# --- native build and verification (pinned KiCad image) ----------------------------------------------------
BUILD_PY = r'''
import json, sys, pcbnew as p
spec = json.load(open(sys.argv[1])); out = sys.argv[2]
mm = p.FromMM
def V(x, y): return p.VECTOR2I(mm(x), mm(y))
def rect_poly(r):
    s = p.SHAPE_POLY_SET(); s.NewOutline()
    for x, y in ((r[0], r[1]), (r[2], r[1]), (r[2], r[3]), (r[0], r[3])): s.Append(mm(x), mm(y))
    return s
def outline(board):
    s = p.SHAPE_POLY_SET(); board.GetBoardPolygonOutlines(s, False); return s
src = p.LoadBoard('/repo/' + spec['pcb'])
src_outline = outline(src)
b = p.LoadBoard('/repo/' + spec['pcb'])
base_items = list(b.GetFootprints()) + list(b.GetTracks()) + list(b.Zones()) + [d for d in b.GetDrawings() if d.GetLayer() != p.Edge_Cuts]
for d in [d for d in b.GetDrawings() if d.GetLayer() == p.Edge_Cuts]:
    b.Delete(d)
copies = spec['copies']
def dup(it):
    try:
        n = it.Duplicate(False)
    except TypeError:
        n = it.Duplicate()
    return n.Cast()
made = []
for c in copies[1:]:
    # each further copy gets its own nets (name + suffix), so DRC does not join the copies into one net
    nets = {}
    def renet(item):
        old = item.GetNet()
        if old is None or old.GetNetCode() == 0:
            return
        if old.GetNetCode() not in nets:
            ni = p.NETINFO_ITEM(b, old.GetNetname() + c['suffix']); b.Add(ni); nets[old.GetNetCode()] = ni
        item.SetNet(nets[old.GetNetCode()])
    for it in base_items:  # duplicated while the originals still sit at their frozen positions
        n = dup(it)
        n.Move(V(*c['offset_mm']))
        for x in (n.Pads() if isinstance(n, p.FOOTPRINT) else [n] if hasattr(n, 'SetNet') else []):
            renet(x)
        if isinstance(n, p.FOOTPRINT):
            n.SetReference(it.GetReference() + c['suffix'])
        made.append(n)
for n in made:
    b.Add(n)
for it in base_items:
    it.Move(V(*copies[0]['offset_mm']))
W, H = spec['panel_mm']
slots = p.SHAPE_POLY_SET()
for c in copies:
    slots.BooleanAdd(rect_poly(c['slot_mm']))
for c in copies:
    o = p.SHAPE_POLY_SET(src_outline); o.Move(V(*c['offset_mm'])); slots.BooleanSubtract(o)
for t in spec['tabs']:
    slots.BooleanSubtract(rect_poly(t['rect_mm']))
frame = p.PCB_SHAPE(b, p.SHAPE_T_RECTANGLE); frame.SetLayer(p.Edge_Cuts); frame.SetStart(V(0, 0)); frame.SetEnd(V(W, H)); frame.SetWidth(mm(0.05)); b.Add(frame)
for i in range(slots.OutlineCount()):
    if slots.HoleCount(i):
        raise SystemExit('slot with a hole: a copy is not held by any tab')
    sh = p.PCB_SHAPE(b, p.SHAPE_T_POLY); sh.SetLayer(p.Edge_Cuts); sh.SetWidth(mm(0.05)); sh.SetFilled(False)
    poly = p.SHAPE_POLY_SET(); poly.AddOutline(slots.Outline(i)); sh.SetPolyShape(poly); b.Add(sh)
def feature(ref, x, y, kind, d, mask=None, side=p.F_Cu):
    fp = p.FOOTPRINT(b); fp.SetReference(ref); fp.SetValue(kind)
    for f in (p.FIELD_T_REFERENCE, p.FIELD_T_VALUE): fp.GetField(f).SetVisible(False)
    fp.SetAttributes(p.FP_EXCLUDE_FROM_POS_FILES | p.FP_EXCLUDE_FROM_BOM | p.FP_BOARD_ONLY)
    pad = p.PAD(fp); pad.SetShape(p.PAD_SHAPE_CIRCLE); pad.SetSize(V(d, d)); pad.SetNumber('')
    if kind == 'FIDUCIAL':
        pad.SetAttribute(p.PAD_ATTRIB_SMD); ls = p.LSET(); ls.AddLayer(p.F_Cu); ls.AddLayer(p.F_Mask); pad.SetLayerSet(ls)
        pad.SetLocalSolderMaskMargin(mm((mask - d) / 2))
    else:
        pad.SetAttribute(p.PAD_ATTRIB_NPTH); pad.SetDrillSize(V(d, d)); pad.SetLayerSet(pad.UnplatedHoleMask())
    fp.Add(pad); b.Add(fp)
    if side == p.B_Cu: fp.Flip(fp.GetPosition(), p.FLIP_DIRECTION_TOP_BOTTOM)
    fp.SetPosition(V(x, y))
k = 0
for x, y in spec['mouse_bites']['centres_mm']:
    k += 1; feature(f'MB{k}', x, y, 'MOUSEBITE', spec['mouse_bites']['diameter_mm'])
for i, (x, y) in enumerate(spec['tooling_holes']['centres_mm'], 1):
    feature(f'TH{i}', x, y, 'TOOLING', spec['tooling_holes']['diameter_mm'])
for side in spec['fiducials']['sides']:
    for i, (x, y) in enumerate(spec['fiducials']['centres_mm'], 1):
        feature(f'FID{side}{i}', x, y, 'FIDUCIAL', spec['fiducials']['diameter_mm'], spec['fiducials']['mask_opening_mm'], p.F_Cu if side == 'F' else p.B_Cu)
p.SaveBoard(out, b)

# Panel-material outline check: (slot rect - slots - tabs) must equal each shifted source outline.
res = {'outline': []}
for c in copies:
    o = p.SHAPE_POLY_SET(src_outline); o.Move(V(*c['offset_mm']))
    m = rect_poly(c['slot_mm']); m.BooleanSubtract(slots)
    for t in spec['tabs']: m.BooleanSubtract(rect_poly(t['rect_mm']))
    x = p.SHAPE_POLY_SET(m); x.BooleanXor(o)
    res['outline'].append({'copy': c['copy'], 'xor_area_mm2': x.Area() / 1e12, 'source_area_mm2': o.Area() / 1e12})
json.dump(res, open(out + '.outline.json', 'w'))
'''

# Items of one board, relative to a copy offset, in integer nm: what must be identical between the frozen board and each copy.
ITEMS_PY = r'''
import json, sys, pcbnew as p
b = p.LoadBoard(sys.argv[1]); spec = json.load(open(sys.argv[2])) if sys.argv[2] != '-' else None
copies = spec['copies'] if spec else [{'copy': 1, 'suffix': '', 'offset_mm': [0, 0], 'slot_mm': None}]
def which(x, y):
    for c in copies:
        if c['slot_mm'] is None: return c
        r = [p.FromMM(v) for v in c['slot_mm']]
        if r[0] <= x <= r[2] and r[1] <= y <= r[3]: return c
    return None
out = {}
def net(item, c):
    n = item.GetNetname()
    return n[:-len(c['suffix'])] if c['suffix'] and n.endswith(c['suffix']) else n
def put(c, kind, row):
    dx, dy = p.FromMM(c['offset_mm'][0]), p.FromMM(c['offset_mm'][1])
    out.setdefault(str(c['copy']), {}).setdefault(kind, []).append(row(dx, dy))
for fp in b.GetFootprints():
    ref = fp.GetReference()
    if fp.GetValue() in ('MOUSEBITE', 'TOOLING', 'FIDUCIAL') and spec: continue
    c = next((c for c in sorted(copies, key=lambda c: -len(c['suffix'])) if not c['suffix'] or ref.endswith(c['suffix'])), None) if spec else copies[0]
    base = ref[:-len(c['suffix'])] if c['suffix'] else ref
    put(c, 'footprints', lambda dx, dy: [base, fp.GetFPIDAsString(), fp.GetLayerName(), fp.GetPosition().x - dx, fp.GetPosition().y - dy, fp.GetOrientationDegrees()])
    for pad in fp.Pads():
        put(c, 'pads', lambda dx, dy: [base, pad.GetNumber(), net(pad, c), pad.GetPosition().x - dx, pad.GetPosition().y - dy, pad.GetSize(p.F_Cu).x, pad.GetSize(p.F_Cu).y,
                                       pad.GetOrientationDegrees(), int(pad.GetShape(p.F_Cu)), int(pad.GetAttribute()), pad.GetDrillSize().x, pad.GetDrillSize().y, pad.GetLayerSet().FmtHex()])
for t in b.GetTracks():
    c = which(t.GetStart().x, t.GetStart().y)
    if t.GetClass() == 'PCB_VIA':
        put(c, 'vias', lambda dx, dy: [net(t, c), t.GetPosition().x - dx, t.GetPosition().y - dy, t.GetWidth(p.F_Cu), t.GetDrillValue()])
    else:
        put(c, 'tracks', lambda dx, dy: [net(t, c), t.GetLayerName(), t.GetStart().x - dx, t.GetStart().y - dy, t.GetEnd().x - dx, t.GetEnd().y - dy, t.GetWidth()])
for z in b.Zones():
    bb = z.GetBoundingBox(); c = which(bb.GetX(), bb.GetY())
    def zrow(dx, dy):
        pts = [[z.Outline().CVertex(i).x - dx, z.Outline().CVertex(i).y - dy] for i in range(z.Outline().TotalVertices())]
        fill = sum(z.GetFilledPolysList(l).Area() for l in z.GetLayerSet().Seq())
        return [net(z, c), z.GetLayerSet().FmtHex(), pts, fill]
    put(c, 'zones', zrow)
for d in b.GetDrawings():
    if d.GetLayer() == p.Edge_Cuts: continue
    bb = d.GetBoundingBox(); c = which(bb.GetX(), bb.GetY())
    put(c, 'drawings', lambda dx, dy: [d.GetClass(), d.GetLayerName(), bb.GetX() - dx, bb.GetY() - dy, bb.GetWidth(), bb.GetHeight()])
json.dump(out, open(sys.argv[3], 'w'))
'''


def docker(image, out, script, timeout=1200):
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '2', '--memory', '4g', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
           '--label', LABEL, '-u', f'{os.getuid()}:{os.getgid()}', '-e', 'HOME=/tmp', '-e', 'PYTHONDONTWRITEBYTECODE=1',
           '-v', f'{ROOT}:/repo:ro', '-v', f'{out}:/out', image, 'bash', '-c', script]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def drill_holes(path):
    """(plated, diameter_mm, x_mm, y_mm) for every hole in an Excellon file in metric units (KiCad export)."""
    tools, holes, cur, plated = {}, [], None, 'NPTH' not in path.name
    for line in path.read_text().splitlines():
        m = re.fullmatch(r'T(\d+)C([\d.]+)', line.strip())
        if m:
            tools[m.group(1)] = float(m.group(2))
            continue
        m = re.fullmatch(r'T(\d+)', line.strip())
        if m:
            cur = m.group(1)
            continue
        m = re.fullmatch(r'X(-?[\d.]+)Y(-?[\d.]+)', line.strip())
        if m and cur:
            holes.append((plated, round(tools[cur], 4), round(float(m.group(1)), 4), round(float(m.group(2)), 4)))
    return holes


def drc_counts(path):
    d = json.loads(path.read_text())
    c = collections.Counter(v['type'] for v in d.get('violations', []))
    c.update('unconnected_items' for _ in d.get('unconnected_items', []))
    c.update('schematic_parity' for _ in d.get('schematic_parity', []))
    return c


def multiset_diff(a, b):
    ca, cb = collections.Counter(json.dumps(x) for x in a), collections.Counter(json.dumps(x) for x in b)
    return sorted((ca - cb).elements())[:5], sorted((cb - ca).elements())[:5]


def build(out, write_receipt=False):
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise SystemExit('refusing: --out must be outside the repository')
    if out.exists() and any(out.iterdir()):
        raise SystemExit('refusing: --out must be empty or absent')
    out.mkdir(parents=True, exist_ok=True)
    files = plan()
    for name, text in files.items():
        if (ROOT / OUT / name).read_text() != text:
            raise SystemExit(f'stale: {OUT / name}; run scripts/a7_panel.py')
    image = json.loads((ROOT / PROFILE).read_text())['image']
    (out / 'build.py').write_text(BUILD_PY)
    (out / 'items.py').write_text(ITEMS_PY)
    lines = ['set -u']
    boards = [json.loads((ROOT / OUT / n).read_text()) for n in sorted(files) if n.endswith('-panel.json')]
    for lay in boards:
        n, src = lay['board'], lay['pcb']
        stem = src.rsplit('.', 1)[0]
        d = f'/out/{n}'
        lines += [f'mkdir -p {d}/src {d}/panel/gerbers {d}/src/drill {d}/panel/drill',
                  # the panel takes the source project's rules (and custom rules where the source has them)
                  f'cp /repo/{stem}.kicad_pro {d}/panel/{n}-panel.kicad_pro; [ -f /repo/{stem}.kicad_dru ] && cp /repo/{stem}.kicad_dru {d}/panel/{n}-panel.kicad_dru; '
                  f'cp /repo/{stem}.kicad_pro {d}/src/src.kicad_pro; cp /repo/{src} {d}/src/src.kicad_pcb; [ -f /repo/{stem}.kicad_dru ] && cp /repo/{stem}.kicad_dru {d}/src/src.kicad_dru; true',
                  f'(python3 -I /out/build.py /repo/{OUT}/{n}-panel.json {d}/panel/{n}-panel.kicad_pcb'
                  f' && python3 -I /out/items.py {d}/panel/{n}-panel.kicad_pcb /repo/{OUT}/{n}-panel.json {d}/panel-items.json'
                  f' && python3 -I /out/items.py /repo/{src} - {d}/src-items.json'
                  f' && kicad-cli pcb drc --format json --severity-error --severity-warning --output {d}/panel-drc.json {d}/panel/{n}-panel.kicad_pcb'
                  f' && kicad-cli pcb drc --format json --severity-error --severity-warning --output {d}/src-drc.json {d}/src/src.kicad_pcb'
                  f' && kicad-cli pcb export drill --format excellon --excellon-units mm --excellon-separate-th --output {d}/src/drill/ {d}/src/src.kicad_pcb'
                  f' && kicad-cli pcb export drill --format excellon --excellon-units mm --excellon-separate-th --output {d}/panel/drill/ {d}/panel/{n}-panel.kicad_pcb'
                  f' && kicad-cli pcb export gerbers --layers {",".join(layers(lay))} --output {d}/panel/gerbers/ {d}/panel/{n}-panel.kicad_pcb'
                  f' && kicad-cli pcb export drill --format excellon --excellon-separate-th --output {d}/panel/gerbers/ {d}/panel/{n}-panel.kicad_pcb'
                  f' && kicad-cli pcb export pos --format csv --units mm --side both --output {d}/panel-pos.csv {d}/panel/{n}-panel.kicad_pcb'
                  f') > {d}.log 2>&1; echo $? > {d}.code']
    p = docker(image, out, '\n'.join(lines))
    summary = {'what': 'Repo-built JLC assembly panels: prepared route, NOT released, NOT order files', 'image': image, 'docker_exit': p.returncode,
               'stderr_tail': p.stderr[-800:], 'boards': {}}
    fails = []
    for lay in boards:
        n = lay['board']
        d = out / n
        code = (out / f'{n}.code').read_text().strip() if (out / f'{n}.code').is_file() else None
        r = {'code': code}
        summary['boards'][n] = r
        if code != '0':
            fails.append(f'{n}: native steps failed (code {code}); see {n}.log')
            continue
        r.update(verify(lay, d, files))
        fails += [f'{n}: {f}' for f in r['failures']]
        gdir = d / 'panel/gerbers'
        names = sorted(q.name for q in gdir.iterdir())
        with zipfile.ZipFile(out / f'{n}-panel-gerbers-DRYRUN.zip', 'w', zipfile.ZIP_DEFLATED) as zf:
            for q in names:
                zf.write(gdir / q, q)
        r['files'] = names
    receipt = ROOT / OUT / 'build-receipt.json'
    recorded = {n: v.get('files') for n, v in summary['boards'].items()}
    if write_receipt and not fails:
        receipt.write_text(json.dumps({'what': 'File names from the last panel build (pinned KiCad image) after every check passed. NOT order files.',
                                       'image': image, 'files': recorded}, indent=2) + '\n')
    elif not receipt.is_file() or json.loads(receipt.read_text()) != {**json.loads(receipt.read_text()), 'image': image, 'files': recorded}:
        fails.append('panel file set differs from engineering/a7/jlc-package/panels/build-receipt.json')
    summary['failures'] = fails
    summary['status'] = 'FAIL' if fails else 'PASS'
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    (out / 'README-PREPARED-ROUTE-NOT-FOR-ORDER.txt').write_text(
        'PREPARED ROUTE - NOT RELEASED - DO NOT UPLOAD OR ORDER FROM THESE FILES\n'
        'The readiness order gate is BLOCKED and the panel route is an open owner decision (assembly:panel-route).\n'
        'See doc/src/content/docs/project/jlc-order-package.mdx.\n')
    print(json.dumps({k: summary[k] for k in ('status', 'failures')}, indent=2))
    return 1 if fails else 0


def layers(lay):
    four = lay['board'] == 'controller'
    return ['F.Cu', 'B.Cu', 'F.Paste', 'B.Paste', 'F.SilkS', 'B.SilkS', 'F.Mask', 'B.Mask', 'Edge.Cuts'] + (['In1.Cu', 'In2.Cu'] if four else [])


def verify(lay, d, files):
    fails, r = [], {}
    src = json.loads((d / 'src-items.json').read_text())['1']
    pan = json.loads((d / 'panel-items.json').read_text())
    r['copies'] = {}
    for c in lay['copies']:
        got = pan.get(str(c['copy']), {})
        res = {}
        for kind in sorted(set(src) | set(got)):
            only_src, only_panel = multiset_diff(src.get(kind, []), got.get(kind, []))
            res[kind] = {'source': len(src.get(kind, [])), 'panel': len(got.get(kind, [])), 'equal': not only_src and not only_panel}
            if not res[kind]['equal']:
                fails.append(f"copy {c['copy']} {kind} differ: only source {only_src[:2]}, only panel {only_panel[:2]}")
        r['copies'][c['copy']] = res
    extra = sorted(set(pan) - {str(c['copy']) for c in lay['copies']})
    if extra:
        fails.append(f'items outside every copy: {extra}')
    outline = json.loads((d / 'panel' / f"{lay['board']}-panel.kicad_pcb.outline.json").read_text())['outline']
    r['outline'] = outline
    for o in outline:
        if o['xor_area_mm2'] > 1e-6:
            fails.append(f"copy {o['copy']} outline differs from the frozen board by {o['xor_area_mm2']} mm2")
    # drills: panel holes = shifted source holes per copy + mouse bites + tooling holes (mm, Y up in Excellon)
    src_holes = [h for f in sorted((d / 'src/drill').glob('*.drl')) for h in drill_holes(f)]
    pan_holes = collections.Counter(h for f in sorted((d / 'panel/drill').glob('*.drl')) for h in drill_holes(f))
    want = collections.Counter()
    for c in lay['copies']:
        dx, dy = c['offset_mm']
        want.update((pl, dia, round(x + dx, 4), round(y - dy, 4)) for pl, dia, x, y in src_holes)
    want.update((False, lay['mouse_bites']['diameter_mm'], round(x, 4), round(-y, 4)) for x, y in lay['mouse_bites']['centres_mm'])
    want.update((False, lay['tooling_holes']['diameter_mm'], round(x, 4), round(-y, 4)) for x, y in lay['tooling_holes']['centres_mm'])
    r['drills'] = {'panel': sum(pan_holes.values()), 'expected': sum(want.values()), 'equal': pan_holes == want}
    if pan_holes != want:
        fails.append(f'drills differ: only panel {sorted((pan_holes - want).elements())[:3]}, missing {sorted((want - pan_holes).elements())[:3]}')
    # DRC: the panel may only repeat the source's own violations, once per copy
    sc, pc = drc_counts(d / 'src-drc.json'), drc_counts(d / 'panel-drc.json')
    n = len(lay['copies'])
    added = {k: pc[k] - n * sc[k] for k in set(sc) | set(pc) if pc[k] != n * sc[k]}
    r['drc'] = {'source': dict(sc), 'panel': dict(pc), 'added_by_panel': added}
    unwaived = {k: v for k, v in added.items() if v > 0 and k not in lay['drc_waivers']}
    r['drc']['waived'] = {k: v for k, v in added.items() if k in lay['drc_waivers']}
    if unwaived:
        fails.append(f'panel DRC adds violations: {unwaived}')
    # CPL vs KiCad's position export of the panel
    k = {row['Ref']: row for row in csv.DictReader((d / 'panel-pos.csv').read_text().splitlines())}
    cpl = {row['Designator']: row for row in csv.DictReader(files[f"{lay['board']}-panel_CPL_DRYRUN.csv"].splitlines())}
    diffs = []
    if set(k) != set(cpl):
        diffs.append(f'references differ: only KiCad {sorted(set(k) - set(cpl))[:5]}, only CPL {sorted(set(cpl) - set(k))[:5]}')
    for ref in sorted(set(k) & set(cpl)):
        a, b = k[ref], cpl[ref]
        if abs(float(a['PosX']) - float(b['Mid X'])) > 1e-4 or abs(float(a['PosY']) - float(b['Mid Y'])) > 1e-4 or \
                abs(float(a['Rot']) % 360 - float(b['Rotation'])) > 1e-4 or {'top': 'Top', 'bottom': 'Bottom'}.get(a['Side']) != b['Layer']:
            diffs.append(f"{ref}: KiCad ({a['PosX']}, {a['PosY']}, {a['Rot']}, {a['Side']}) vs CPL ({b['Mid X']}, {b['Mid Y']}, {b['Rotation']}, {b['Layer']})")
    r['cpl_vs_kicad'] = diffs or 'MATCH'
    if diffs:
        fails.append(f'CPL differs from KiCad position export: {diffs[:3]}')
    r['failures'] = fails
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command', nargs='?', default='plan', choices=['plan', 'build'])
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--out', type=Path)
    ap.add_argument('--write-receipt', action='store_true')
    a = ap.parse_args()
    if a.command == 'build':
        if not a.out:
            ap.error('build needs --out')
        return build(a.out, a.write_receipt)
    files = plan()
    (ROOT / OUT).mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        path = ROOT / OUT / name
        if a.check:
            if not path.is_file() or path.read_text() != text:
                raise SystemExit(f'stale: {path.relative_to(ROOT)}; run scripts/a7_panel.py')
        else:
            path.write_text(text)
    print(f"{'PASS' if a.check else 'WROTE'}: {len(files) // 3} panel layouts (prepared route, NOT released)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
