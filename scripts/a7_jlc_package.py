#!/usr/bin/env python3
"""JLCPCB order-package dry run for the owner's 2-unit first build. NOT a release and NOT for upload.

generate (default) reads the frozen board files, the procurement ledger and the dated JLC receipts in
engineering/a7/jlc-package/sources.json, and writes JLC-format BOM / CPL dry-run files, a package report
and the owner page. It never writes a board file. --check compares every output with the committed one.

export --out DIR runs the pinned KiCad image on read-only copies of the three boards, writes Gerber, drill
and KiCad position files into DIR (outside the repository), zips the Gerber set per board, and checks the
committed CPL against KiCad's own position export. The files are a dry run, not order files.
"""
import argparse
import csv
import hashlib
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
OUT = Path('engineering/a7/jlc-package')
SOURCES = OUT / 'sources.json'
PAGE = Path('doc/src/content/docs/project/jlc-order-package.mdx')
PANELS = OUT / 'panels'
LEDGER = 'engineering/a7/procurement/assembly-manifest.json'
OWNER_DECISIONS = Path('engineering/a7/procurement/owner-decisions.json')
READINESS = 'engineering/a7/qualification/readiness.json'
PROFILE = 'engineering/a7/verification/native_gate.json'
LAYOUT = 'engineering/a7/mechanical/layout.json'
LABEL = 'zudo-led-block.a7-jlc-package'
# Gerber layers JLC needs for a board; KiCad names. Inner layers are added for 4-layer boards.
FAB_LAYERS = ['F.Cu', 'B.Cu', 'F.Paste', 'B.Paste', 'F.SilkS', 'B.SilkS', 'F.Mask', 'B.Mask', 'Edge.Cuts']
CENTROID_TOLERANCE_MM = 0.05


def load_procurement():
    spec = importlib.util.spec_from_file_location('a7_procurement', ROOT / 'scripts/a7_procurement.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --- minimal KiCad s-expression reader -------------------------------------------------------------
TOKEN = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')


def parse_sexp(text):
    stack, cur = [], []
    for tok in TOKEN.findall(text):
        if tok == '(':
            stack.append(cur)
            cur = []
        elif tok == ')':
            done, cur = cur, stack.pop()
            cur.append(done)
        else:
            cur.append(json.loads(tok) if tok.startswith('"') else tok)
    return cur[0]


def kids(node, name):
    return [c for c in node[1:] if isinstance(c, list) and c and c[0] == name]


def kid(node, name):
    found = kids(node, name)
    return found[0] if found else None


def nums(node):
    return [float(x) for x in node[1:] if isinstance(x, str) and re.fullmatch(r'-?\d+(\.\d+)?', x)]


def board_facts(path):
    tree = parse_sexp((ROOT / path).read_text())
    general = kid(tree, 'general')
    layers = kid(tree, 'layers')
    copper = [l[1] for l in layers[1:] if isinstance(l, list) and len(l) > 2 and str(l[1]).endswith('.Cu')]
    setup = kid(tree, 'setup')
    stackup = kid(setup, 'stackup') if setup else None
    finish = kid(stackup, 'copper_finish') if stackup else None
    plot = kid(setup, 'pcbplotparams') if setup else None
    aux = kid(setup, 'aux_axis_origin') if setup else None
    xs, ys, edges = [], [], []
    for g in tree[1:]:
        if isinstance(g, list) and g and g[0] in ('gr_line', 'gr_rect', 'gr_arc', 'gr_poly', 'gr_circle') and kid(g, 'layer') and kid(g, 'layer')[1] == 'Edge.Cuts':
            for key in ('start', 'end', 'mid'):
                if kid(g, key):
                    x, y = nums(kid(g, key))[:2]
                    xs.append(x)
                    ys.append(y)
            edges.append((g[0], tuple(nums(kid(g, 'start'))[:2]) if kid(g, 'start') else None, tuple(nums(kid(g, 'end'))[:2]) if kid(g, 'end') else None))
            if kid(g, 'pts'):
                for xy in kids(kid(g, 'pts'), 'xy'):
                    x, y = nums(xy)[:2]
                    xs.append(x)
                    ys.append(y)
    footprints, drills = [], []
    for fp in kids(tree, 'footprint'):
        props = {p[1]: p[2] for p in kids(fp, 'property') if len(p) > 2}
        at = nums(kid(fp, 'at'))
        attr = kid(fp, 'attr')
        flags = set(attr[1:]) if attr else set()
        pads = []
        for pad in kids(fp, 'pad'):
            pat = nums(kid(pad, 'at'))
            size = nums(kid(pad, 'size'))
            if kid(pad, 'drill'):
                d = [x for x in nums(kid(pad, 'drill'))]
                if d:
                    drills.append(min(d))
            # Pad positions are in the footprint frame; the pad angle includes the footprint angle.
            rel = (pat[2] if len(pat) > 2 else 0.0) - (at[2] if len(at) > 2 else 0.0)
            w, h = (size + [0, 0])[:2]
            c, s = abs(math.cos(math.radians(rel))), abs(math.sin(math.radians(rel)))
            hw, hh = (w * c + h * s) / 2, (w * s + h * c) / 2
            pads.append((pat[0] - hw, pat[1] - hh, pat[0] + hw, pat[1] + hh, pad[2]))
        crt = []
        for g in fp[1:]:
            if isinstance(g, list) and g and g[0] in ('fp_line', 'fp_rect', 'fp_poly', 'fp_circle', 'fp_arc') and kid(g, 'layer') and str(kid(g, 'layer')[1]).endswith('CrtYd'):
                crt += [nums(kid(g, k))[:2] for k in ('start', 'end', 'mid', 'center') if kid(g, k)]
                if kid(g, 'pts'):
                    crt += [nums(xy)[:2] for xy in kids(kid(g, 'pts'), 'xy')]
        footprints.append({'ref': props.get('Reference'), 'value': props.get('Value'), 'footprint': fp[1], 'courtyard': [to_board(at, x, y) for x, y in crt],
                           'lcsc': props.get('LCSC'), 'mpn': props.get('MPN'), 'layer': kid(fp, 'layer')[1],
                           'x': at[0], 'y': at[1], 'rot': at[2] if len(at) > 2 else 0.0, 'flags': sorted(flags),
                           'dnp': bool(kid(fp, 'dnp')) or 'dnp' in flags, 'pads': pads})
    xr, yr = (min(xs), max(xs)), (min(ys), max(ys))
    for f in footprints:
        if f['courtyard']:
            cx, cy = [c[0] for c in f['courtyard']], [c[1] for c in f['courtyard']]
            f['overhang_mm'] = {'left': round(xr[0] - min(cx), 3), 'right': round(max(cx) - xr[1], 3), 'top': round(yr[0] - min(cy), 3), 'bottom': round(max(cy) - yr[1], 3)}
    for via in kids(tree, 'via'):
        d = nums(kid(via, 'drill'))
        if d:
            drills.append(d[0])
    return {'path': str(path), 'sha256': sha(ROOT / path), 'thickness_mm': nums(kid(general, 'thickness'))[0],
            'copper_layers': copper, 'copper_finish': finish[1] if finish else None,
            'outline_mm': {'x': [min(xs), max(xs)], 'y': [min(ys), max(ys)],
                           'width': round(max(xs) - min(xs), 3), 'height': round(max(ys) - min(ys), 3)},
            'outline_is_rectangle': is_rectangle(edges, (min(xs), max(xs)), (min(ys), max(ys))), 'outline_edges': len(edges),
            'gerber_uses_aux_origin': bool(plot and kid(plot, 'useauxorigin') and kid(plot, 'useauxorigin')[1] == 'yes'),
            'aux_axis_origin': nums(aux) if aux else None, 'min_drill_mm': min(drills) if drills else None,
            'fiducials': [f['ref'] for f in footprints if 'fiducial' in (f['footprint'] + str(f['value'])).lower()],
            'footprints': footprints}


def to_board(at, x, y):
    """Footprint-local point to board coordinates (KiCad: Y down, angle counter-clockwise; B-side graphics are stored already flipped)."""
    a = math.radians(at[2] if len(at) > 2 else 0.0)
    return (at[0] + x * math.cos(a) + y * math.sin(a), at[1] - x * math.sin(a) + y * math.cos(a))


def overhangs(facts, fitted):
    """Fitted parts whose courtyard reaches past the board outline, per edge (mm)."""
    out = []
    for f in facts['footprints']:
        o = f.get('overhang_mm')
        if f['ref'] in fitted and o and max(o.values()) > 0.01:
            out.append({'ref': f['ref'], **{k: v for k, v in o.items() if v > 0.01}})
    return out


def is_rectangle(edges, xr, yr):
    """True when Edge.Cuts is one rectangle: a gr_rect, or four axis-aligned lines lying on the bounding box."""
    if len(edges) == 1 and edges[0][0] == 'gr_rect':
        return True
    if len(edges) != 4 or any(e[0] != 'gr_line' or e[1] is None or e[2] is None for e in edges):
        return False
    on_box = all((a[0] == b[0] and a[0] in xr) or (a[1] == b[1] and a[1] in yr) for _, a, b in edges)
    return on_box and {tuple(sorted((a, b))) for _, a, b in edges} == {
        ((xr[0], yr[0]), (xr[1], yr[0])), ((xr[0], yr[0]), (xr[0], yr[1])), ((xr[1], yr[0]), (xr[1], yr[1])), ((xr[0], yr[1]), (xr[1], yr[1]))}


def fmt(v):
    return f'{v:.4f}'.rstrip('0').rstrip('.') if v != int(v) else str(int(v))


def norm_rot(r):
    r = round(r % 360, 4)
    return 0.0 if r == 360 else r


# --- generate ------------------------------------------------------------------------------------
def generate(root=ROOT, sources=None):
    """sources: an already-loaded sources.json (tests pass a modified copy); read from the repository when None."""
    proc = load_procurement()
    ledger = json.loads((root / LEDGER).read_text())
    if ledger != proc.generate(root):
        raise ValueError('procurement ledger is stale; run scripts/a7_procurement.py first')
    if sources is None:
        sources = json.loads((root / SOURCES).read_text())
    layout = json.loads((root / LAYOUT).read_text())
    parts = {p['lcsc']: p for p in sources['parts']}
    pages = {p['id']: p for p in sources['pages']}
    plan = ledger['order_plan']
    modules = plan['modules']
    basis = plan['pcba_minimum_boards']
    check_pcba_basis(basis, pages['jlc-pcba-capabilities'])
    rows_by_board = {}
    for r in ledger['population']:
        rows_by_board.setdefault(r['board'], {})[r['ref']] = r
    boards, files, blockers = [], {}, []
    for b in ledger['boards']:
        name = b['board']
        facts = board_facts(b['pcb'])
        if facts['sha256'] != b['pcb_sha256']:
            raise ValueError(f'{name}: board file differs from the ledger identity')
        rows = rows_by_board[name]
        fitted = {ref: r for ref, r in rows.items() if r['population'] == 'FITTED'}
        placed = {f['ref']: f for f in facts['footprints'] if f['ref'] in fitted}
        board_only = sorted(f['ref'] or '(unnamed)' for f in facts['footprints'] if f['ref'] not in rows
                            and f['ref'] not in {e['ref'] for e in ledger['excluded'] if e['board'] == name})
        if set(placed) != set(fitted):
            raise ValueError(f'{name}: fitted references differ between the ledger and the board file')
        # A5 boards carry the identity in the netlist only (checked by the procurement ledger); compare where the board has fields.
        mismatched = sorted(ref for ref, f in placed.items() if f['lcsc'] is not None and (f['lcsc'], f['mpn']) != (fitted[ref]['lcsc'], fitted[ref]['mpn']))
        if mismatched:
            raise ValueError(f'{name}: board LCSC/MPN fields differ from the ledger for {mismatched}')
        bom, cpl, centroid = {}, [], []
        for ref in sorted(placed, key=lambda r: (re.sub(r'\d+', '', r), int(re.sub(r'\D', '', r) or 0))):
            f, r = placed[ref], fitted[ref]
            key = (r['lcsc'], f['footprint'].split(':')[-1])
            line = bom.setdefault(key, {'Comment': f['value'], 'Designator': [], 'Footprint': key[1], 'JLCPCB Part #': r['lcsc']})
            line['Designator'].append(ref)
            side = 'Top' if f['layer'] == 'F.Cu' else 'Bottom'
            cpl.append({'Designator': ref, 'Mid X': fmt(f['x']), 'Mid Y': fmt(-f['y']), 'Rotation': fmt(norm_rot(f['rot'])), 'Layer': side})
            if f['pads']:
                cx = (min(p[0] for p in f['pads']) + max(p[2] for p in f['pads'])) / 2
                cy = (min(p[1] for p in f['pads']) + max(p[3] for p in f['pads'])) / 2
                off = math.hypot(cx, cy)
                if off > CENTROID_TOLERANCE_MM:
                    centroid.append({'ref': ref, 'lcsc': r['lcsc'], 'anchor_to_pad_centre_mm': round(off, 3),
                                     'pad_centre_in_footprint_mm': [round(cx, 3), round(-cy, 3)]})
        bom_rows = [dict(v, Designator=','.join(v['Designator'])) for v in bom.values()]
        files[f'{name}_BOM_DRYRUN.csv'] = to_csv(['Comment', 'Designator', 'Footprint', 'JLCPCB Part #'], bom_rows)
        files[f'{name}_CPL_DRYRUN.csv'] = to_csv(['Designator', 'Mid X', 'Mid Y', 'Rotation', 'Layer'], cpl)
        sides = sorted({c['Layer'] for c in cpl})
        tht = sorted(ref for ref, r in fitted.items() if r['mount'] == 'THT')
        layers = len(facts['copper_layers'])
        needed = b['multiplicity'] * modules
        boards.append({
            'board': name, 'pcb': b['pcb'], 'pcb_sha256': facts['sha256'], 'per_module': b['multiplicity'], 'pcba_quantity': needed,
            'copper_layers': layers, 'thickness_mm': facts['thickness_mm'],
            'thickness_tolerance': '±10%' if facts['thickness_mm'] >= 1.0 else '±0.1 mm',
            'outline_mm': facts['outline_mm'], 'copper_finish_in_board_file': facts['copper_finish'],
            'gerber_origin': 'aux origin' if facts['gerber_uses_aux_origin'] else 'absolute (page) coordinates',
            'min_drill_mm': facts['min_drill_mm'], 'fiducials': facts['fiducials'], 'board_only_footprints': board_only,
            'assembly_sides': sides, 'tht_refs': tht, 'smd_count': sum(1 for r in fitted.values() if r['mount'] == 'SMD'),
            'bom_lines': len(bom_rows), 'cpl_rows': len(cpl), 'centroid_offsets': centroid,
            'files': [f'{name}_BOM_DRYRUN.csv', f'{name}_CPL_DRYRUN.csv'],
            'base_material': base_material(name, layout), 'overhangs': overhangs(facts, fitted),
            'pcba_tier': pcba_tier(facts, sides, layers, fitted, parts, needed),
        })
        boards[-1]['assembly_route'] = assembly_route(boards[-1], facts)
        boards[-1]['repo_panel'] = repo_panel(boards[-1], basis['value'])
    lines = []
    for l in plan['lines']:
        p = parts.get(l['lcsc'])
        if p is None:
            raise ValueError(f"{l['lcsc']}: no dated JLC part observation in {SOURCES}")
        need = l['pieces_required']
        if p['in_stock'] >= need:
            route = 'JLC_STOCK'
        elif p['buyable'] and p['preorder_available'] >= max(need, p['preorder_minimum']):
            route = 'JLC_PREORDER'
        elif p['buyable']:
            route = 'JLC_PREORDER_OR_GLOBAL_SOURCING_BLOCKED'
        else:
            route = 'EXCEPTION'
        lines.append({'lcsc': l['lcsc'], 'mpn': l['mpn'], 'pieces_required': need, 'library': p['library'],
                      'in_stock': p['in_stock'], 'preorder_available': p['preorder_available'], 'route': route,
                      'observed_at': p['retrieved_at']})
    comparison = compare_routes(boards, ledger, lines, basis['value'])
    blockers = named_blockers(boards, lines, pages, ledger, root)
    readiness = json.loads((root / READINESS).read_text())
    gates = {g['gate'] for g in readiness.get('gates', [])}
    order_dir = root / OUT / 'order'
    report = {'schema': 1, 'status': 'DRY_RUN_NOT_RELEASED', 'order_eligibility': readiness['order_eligibility'],
              'prototype_route_binding': 'HOLD: readiness gate owner_prototype_route (the recorded approval does not match the current identities)'
                                         if 'owner_prototype_route' in gates else 'MATCHES the current readiness identities',
              'dated_order_exports': sorted(str(OUT / 'order' / d.name) for d in order_dir.iterdir() if d.is_dir()) if order_dir.is_dir() else [],
              'modules': modules, 'decided_by': plan['decided_by'], 'sources': str(SOURCES),
              'ledger_sha256': sha(root / LEDGER), 'sources_sha256': sha(root / SOURCES),
              'boards': boards, 'parts': lines, 'panel_comparison': comparison, 'panel_route': panel_decision(root),
              'part_counts': {k: sum(1 for l in lines if l['library'] == k) for k in ('BASIC', 'EXTENDED')},
              'route_counts': {k: sum(1 for l in lines if l['route'] == k) for k in sorted({l['route'] for l in lines})},
              'blockers': blockers}
    files['package.json'] = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
    return report, files


def check_pcba_basis(basis, cap):
    """A SOURCED PCBA minimum must cite the dated capability receipt and quote one of its extracts."""
    if basis['status'] != 'SOURCED':
        return
    src = basis.get('source') or {}
    if (src.get('sha256'), src.get('url')) != (cap['raw_sha256'], cap['url']):
        raise ValueError('PCBA minimum source differs from the dated capability receipt in sources.json')
    quote = (src.get('quote') or '').strip()
    if not quote or not any(quote in e for e in cap['extracts']):
        raise ValueError('PCBA minimum quote is empty or not in the capability receipt extracts')


def to_csv(header, rows):
    s = io.StringIO()
    w = csv.DictWriter(s, fieldnames=header, lineterminator='\n')
    w.writeheader()
    w.writerows(rows)
    return s.getvalue()


# Economic PCBA limits from the 2026-11-12 capability table extracts in sources.json.
ECONOMIC_MAX_ORDER = 50
ECONOMIC_MIN_PITCH_MM = 0.4
SMALLER_THAN_0402 = re.compile(r'(?<!\d)(0201|01005|008004)(?!\d)')


def base_material(name, layout):
    """Laminate as recorded in the A7 mechanical layout; the board files carry no stackup material."""
    if name == 'led_leaf' and layout['leaf_comparison']['default'] == 'fr4':
        return {'value': 'FR-4', 'source': f'{LAYOUT} leaf_comparison.default'}
    if name == 'controller' and 'FR-4' in layout['decision']['working_candidate']:
        return {'value': 'FR-4', 'source': f'{LAYOUT} decision.working_candidate'}
    return {'value': None, 'source': None}


def min_pad_pitch(footprint):
    """Smallest pad-centre spacing in a footprint with four or more pads (the IC pin-spacing proxy), in mm."""
    centres = [((p[0] + p[2]) / 2, (p[1] + p[3]) / 2) for p in footprint['pads']]
    if len(centres) < 4:
        return None
    gaps = [math.dist(a, b) for i, a in enumerate(centres) for b in centres[i + 1:]]
    gaps = [g for g in gaps if g > 1e-6]
    return min(gaps) if gaps else None


def pcba_tier(facts, sides, layers, fitted, parts, quantity):
    """Which JLC PCBA tier the board needs, from the 2026-11-12 capability table and part pages (sources.json).

    economic_checks lists every Economic constraint evaluated except single-board size, which assembly_route adds;
    the panel-size limit is checked there against the panel it proposes."""
    missing = sorted({r['lcsc'] for r in fitted.values() if not parts.get(r['lcsc'], {}).get('pcba_type')})
    if missing:
        raise ValueError(f'no recorded JLC PCBA type for {missing}')
    only = sorted({r['lcsc'] for r in fitted.values() if parts[r['lcsc']]['pcba_type'] == 'Standard Only'})
    small = sorted(f['ref'] for f in facts['footprints'] if f['ref'] in fitted and SMALLER_THAN_0402.search(f['footprint']))
    pitches = {f['ref']: min_pad_pitch(f) for f in facts['footprints'] if f['ref'] in fitted and fitted[f['ref']]['mount'] == 'SMD'}
    fine = sorted(ref for ref, g in pitches.items() if g is not None and g < ECONOMIC_MIN_PITCH_MM - 1e-6)
    th = fmt(facts['thickness_mm'])
    checks = [
        {'criterion': 'every part allowed for Economic on its JLC part page', 'ja': '全部品が JLC 部品ページで Economic 可',
         'ok': not only, 'value': ('"Standard Only": ' + ', '.join(only)) if only else 'all "Economic and Standard"',
         'reason': ', '.join(only) + ' is "Standard Only" on its 2026-11-12 JLC part page', 'reason_ja': ', '.join(only) + ' は 2026-11-12 の JLC 部品ページで Standard のみ'},
        {'criterion': 'single-sided placement', 'ja': '片面実装', 'ok': len(sides) == 1, 'value': ' + '.join(sides),
         'reason': 'parts on both sides (Economic is single-sided placement only)', 'reason_ja': '両面に部品がある（Economic は片面のみ）'},
        {'criterion': 'thickness 0.8–1.6 mm', 'ja': '板厚 0.8–1.6 mm', 'ok': 0.8 <= facts['thickness_mm'] <= 1.6, 'value': f'{th} mm',
         'reason': f'thickness {th} mm (Economic takes 0.8–1.6 mm)', 'reason_ja': f'板厚 {th} mm（Economic は 0.8–1.6 mm）'},
        {'criterion': '2, 4 or 6 copper layers', 'ja': '銅層 2・4・6', 'ok': layers in (2, 4, 6), 'value': str(layers),
         'reason': f'{layers} copper layers (Economic takes 2, 4 or 6)', 'reason_ja': f'銅層 {layers}（Economic は 2・4・6 層）'},
        {'criterion': 'no package smaller than 0402 (footprint name)', 'ja': '0402 より小さい部品なし（フットプリント名）', 'ok': not small, 'value': ', '.join(small) or 'none',
         'reason': f"packages smaller than 0402 ({', '.join(small)}; Economic minimum package 0402)", 'reason_ja': f"0402 より小さい部品（{', '.join(small)}。Economic の最小は 0402）"},
        {'criterion': 'pad-centre spacing 0.4 mm or more (SMD footprints with 4+ pads)', 'ja': 'パッド中心間隔 0.4 mm 以上（4 パッド以上の SMD）', 'ok': not fine,
         'value': fmt(min([g for g in pitches.values() if g] or [0])) + ' mm min' if any(pitches.values()) else 'no SMD footprint with 4+ pads',
         'reason': f"pad spacing below 0.4 mm ({', '.join(fine)}; Economic minimum IC pin spacing 0.4 mm)", 'reason_ja': f"パッド間隔 0.4 mm 未満（{', '.join(fine)}。Economic の IC ピン間隔は 0.4 mm から）"},
        {'criterion': 'quantity 2–50', 'ja': '数量 2–50', 'ok': quantity <= ECONOMIC_MAX_ORDER, 'value': str(quantity),
         'reason': f'quantity {quantity} (Economic takes 2–50)', 'reason_ja': f'数量 {quantity}（Economic は 2–50）'},
    ]
    failed = [c for c in checks if not c['ok']]
    tier = 'STANDARD' if failed else 'ECONOMIC'
    return {'tier': tier, 'reasons': [c['reason'] for c in failed], 'reasons_ja': [c['reason_ja'] for c in failed],
            'economic_checks': [{k: c[k] for k in ('criterion', 'ja', 'ok', 'value')} for c in checks]}


PCBA_UNIT_QUESTION = ('"With Panel by JLCPCB, does the PCBA Qty count panels or single boards, and does one panel holding 2 or more boards '
                      'meet the 2-pcs PCBA minimum, or must 2 panels be assembled?"')
JLC_RAIL_MM = 5          # jlc-order-a-panel: "By default, we will add a 5mm board edge"
VCUT_EXTRA_COST_BELOW_MM = 15  # jlc-order-a-panel: extra V-cut cost if either side is within 15 mm


def assembly_route(b, facts):
    """Per board: single boards under Economic when every Economic constraint holds; otherwise Panel by JLCPCB;
    a panel built in the repository only where JLC's panel cannot take the board (decision order set by the coordinator)."""
    t = b['pcba_tier']
    w, h = b['outline_mm']['width'], b['outline_mm']['height']
    eco_size = w >= 10 and h >= 10
    checks = [dict(c) for c in t['economic_checks']] + [{'criterion': 'single board 10 × 10 mm or larger', 'ja': '単品 10 × 10 mm 以上',
                                                       'ok': eco_size, 'value': f'{fmt(w)} × {fmt(h)} mm'}]
    economic_single = all(c['ok'] for c in checks)
    standard_single = t['tier'] == 'STANDARD' and w >= 70 and h >= 70
    out = {'economic_checks': checks, 'economic_single_board': economic_single}
    if economic_single or standard_single:
        out.update(route='SINGLE_BOARDS', tier=t['tier'], panel=None, open_questions=[])
        return out
    minimum = 70 if t['tier'] == 'STANDARD' else 10
    cols, rows = max(1, math.ceil(minimum / w)), max(1, math.ceil(minimum / h))
    panel = {'columns_x': cols, 'rows_y': rows, 'boards_per_panel': cols * rows,
             'size_without_rails_mm': [round(cols * w, 3), round(rows * h, 3)], 'panel_minimum_mm': minimum,
             'within_250_mm': max(cols * w, rows * h) <= 250, 'edge_rails': t['tier'] == 'STANDARD', 'vcut_extra_cost': t['tier'] == 'STANDARD' and min(w, h) < VCUT_EXTRA_COST_BELOW_MM,
             'separation': 'mouse bites (V-cut is not supported with Economic assembly)' if t['tier'] == 'ECONOMIC' else 'V-cut or mouse bites',
             'fiducials': 'added to the edge rails by JLC (Panel by JLCPCB with Edge Rails)' if t['tier'] == 'STANDARD' else 'not required (Economic)'}
    questions = []
    if not facts['outline_is_rectangle']:
        questions.append({'id': 'outline', 'text': f"The outline is not a plain rectangle ({facts['outline_edges']} Edge.Cuts segments). JLC asks for a simple outline for Panel by JLCPCB and says complex outlines must be panelised by the customer: does JLC accept this outline for Panel by JLCPCB?",
                          'ja': f"外形が単純な長方形ではない（Edge.Cuts {facts['outline_edges']} 本）。JLC は Panel by JLCPCB には単純な外形を求め、複雑な外形は自分で面付けするよう書いている。この外形で Panel by JLCPCB を受けてもらえるか。"})
    over = [o for o in b['overhangs'] if max(v for k, v in o.items() if k != 'ref') > PANEL_GAP_MM]
    if over:
        txt = ', '.join(f"{o['ref']} {max(v for k, v in o.items() if k != 'ref'):g} mm" for o in over)
        questions.append({'id': 'overhang', 'text': f'Courtyards reach past the outline by more than the {PANEL_GAP_MM:g} mm board spacing ({txt}); a JLC panel must leave room for them, which the order form does not let us specify.',
                          'ja': f'部品のコートヤードが基板外形から {PANEL_GAP_MM:g} mm の基板間隔より大きくはみ出す（{txt}）。JLC の面付けでその逃げを確保できるかは注文画面では指定できない。'})
    if t['tier'] == 'ECONOMIC':
        sc, sr = math.ceil(70 / w), math.ceil(70 / h)
        questions.append({'id': 'economic-panel-separation', 'text': 'JLC describes Panel by JLCPCB with V-cut, and V-cut is not supported with Economic assembly: can Panel by JLCPCB use mouse bites so the board stays on Economic assembly?'
                          f' If not, Standard needs a 70 × 70 mm panel ({sc} × {sr} = {sc * sr} boards before rails).',
                          'ja': 'JLC は Panel by JLCPCB を V-cut で説明しており、V-cut は Economic 実装では使えない。Economic のまま Panel by JLCPCB をマウスバイトで作れるか。'
                          f'できなければ Standard で 70 × 70 mm の面付け（レールなしで {sc} × {sr} = {sc * sr} 枚）になる。'})
    out.update(route='PANEL_BY_JLCPCB' if not questions else 'PANEL_BY_JLCPCB_TO_CONFIRM', tier=t['tier'], panel=panel, open_questions=questions,
               repo_panel_needed_if=[q['id'] for q in questions])
    return out


PANEL_GAP_MM = 2.0         # jlc-pcb-capabilities: spacing between boards should be >= 2 mm
PANEL_RAIL_MM = 5.0        # jlc-pcb-capabilities: use 5 mm tooling edges for SMT assembly (minimum 3 mm)
TAB_MIN_MM = 5.0           # jlc-pcb-capabilities: breakaway with mouse-bites, minimum width 5 mm
OVERHANG_MARGIN_MM = 1.0   # PROPOSED clearance past a courtyard that leaves the outline; not a JLC rule


def repo_panel(b, minimum_pcs):
    """A customer panel holding only the boards the owner needs, sized to the tier's panel minimum. Evaluated, not built."""
    t = b['pcba_tier']
    w, h = b['outline_mm']['width'], b['outline_mm']['height']
    copies = math.ceil(b['pcba_quantity'] / minimum_pcs)
    edge = {e: max([o.get(e, 0) for o in b['overhangs']] or [0]) for e in ('left', 'right', 'top', 'bottom')}
    gap = {e: max(PANEL_GAP_MM, round(v + OVERHANG_MARGIN_MM, 3) if v > 0 else 0) for e, v in edge.items()}
    between = max(PANEL_GAP_MM, round(edge['left'] + edge['right'] + OVERHANG_MARGIN_MM, 3) if edge['left'] + edge['right'] > 0 else 0)
    content = (copies * w + (copies - 1) * between + gap['left'] + gap['right'], h + gap['top'] + gap['bottom'])
    minimum = 70 if t['tier'] == 'STANDARD' else 10
    size = [round(max(minimum, c + 2 * PANEL_RAIL_MM), 3) for c in content]
    notes, notes_ja = [], []
    if b['thickness_mm'] < 0.8:
        notes.append(f"{fmt(b['thickness_mm'])} mm board: JLC uses a carrier for 0.4 and 0.6 mm boards in printing, placement and reflow; keep the waste area solid FR-4, not an open window.")
        notes_ja.append(f"板厚 {fmt(b['thickness_mm'])} mm: JLC は 0.4・0.6 mm の基板に印刷・実装・リフローでキャリアを使う。捨て基板の部分は抜かずに FR-4 のまま残す。")
    if b['overhangs']:
        refs = ', '.join(o['ref'] for o in b['overhangs'])
        notes.append(f'Frame cut back by the courtyard overhang plus {OVERHANG_MARGIN_MM:g} mm (proposed) at {refs}; tabs away from those parts where at least 2 tabs fit, otherwise kept clear of pads only (see the panel notes).')
        notes_ja.append(f'{refs} のはみ出しに {OVERHANG_MARGIN_MM:g} mm（提案値）を足して枠を逃がす。タブは 2 か所以上置ける限りその部品から離し、置けない場合はパッドからだけ離す（面付けの注記を参照）。')
    return {'copies': copies, 'tier': t['tier'], 'panel_mm': size, 'panel_minimum_mm': minimum, 'within_250_mm': max(size) <= 250,
            'rail_mm': PANEL_RAIL_MM, 'edge_gap_mm': gap, 'between_copies_mm': between if copies > 1 else None,
            'fiducials': '1 mm fiducials centred 3.85 mm from the panel edges, 2 mm tooling holes, on the rails (JLC SMT guidance)',
            'separation': f'mouse bites; tabs at least {TAB_MIN_MM:g} mm wide', 'assembled_at_minimum_order': copies * minimum_pcs,
            'notes': notes, 'notes_ja': notes_ja}


def compare_routes(boards, ledger, lines, minimum_pcs):
    """Assembled boards and part quantities for the minimum PCBA order (2 panels if the PCBA quantity counts panels) per route."""
    per_board = {}
    for r in ledger['population']:
        if r['population'] == 'FITTED':
            per_board.setdefault(r['board'], {}).setdefault(r['lcsc'], 0)
            per_board[r['board']][r['lcsc']] += r['quantity_per_board']
    routes = {}
    for b in boards:
        jlc = b['assembly_route']['panel']
        routes[b['board']] = {'needed': b['pcba_quantity'],
                              'jlc_panel': jlc['boards_per_panel'] * minimum_pcs if jlc else b['pcba_quantity'],
                              'repo_panel': b['repo_panel']['assembled_at_minimum_order']}
        r = routes[b['board']]
        r['recommended'] = 'REPO_PANEL' if r['repo_panel'] < r['jlc_panel'] else 'JLC_PANEL'
    def totals(key):
        out = {}
        for board, parts in per_board.items():
            for lcsc, n in parts.items():
                out[lcsc] = out.get(lcsc, 0) + n * routes[board][key]
        return out
    jt, rt = totals('jlc_panel'), totals('repo_panel')
    parts = [{'lcsc': l['lcsc'], 'mpn': l['mpn'], 'needed': l['pieces_required'], 'jlc_panel': jt[l['lcsc']], 'repo_panel': rt[l['lcsc']],
              'in_stock': l['in_stock'], 'preorder_available': l['preorder_available'],
              'jlc_panel_short': jt[l['lcsc']] > l['in_stock'], 'repo_panel_short': rt[l['lcsc']] > l['in_stock']} for l in lines]
    return {'assumption': f'The PCBA quantity counts panels and the minimum is {minimum_pcs}; not sourced (pcba-quantity-unit-with-panel-not-sourced).',
            'assumption_ja': f'PCBA 数量はシート数で、最小 {minimum_pcs} シートと仮定。未確認（`pcba-quantity-unit-with-panel-not-sourced`）',
            'boards': routes, 'parts': parts}


def named_blockers(boards, lines, pages, ledger, root):
    """Each mismatch between the frozen boards and JLC's published rules, in English (report) and Japanese (page)."""
    out = []

    def add(bid, board, text, ja):
        out.append({'id': bid, 'board': board, 'text': text, 'ja': ja})

    panels = load_panels(root)
    chosen = (panel_decision(root) or {}).get('answer')
    stated = owner_entry('jlc-questions', root)
    jlc_en = ('owner-stated, not JLC-confirmed (the owner closed O12 without asking JLC, '
              f"{stated['decided_on']}, jlc-questions)") if stated else 'not confirmed (O12)'
    jlc_ja = (f"オーナーの知識による判断で、JLC の確認ではない（オーナーは JLC に聞かずに O12 を閉じた。{stated['decided_on']}、jlc-questions）") if stated else '未確認（O12）'

    add('order-gate-blocked', None, 'Readiness order gate is BLOCKED (it counts every condition up to a manufacturing release). These generator reference files are not uploaded directly; '
        'an owner uploads only a dated copy under engineering/a7/jlc-package/order/ for an owner-approved prototype route, after the order-form checks in its README. None of this is a manufacturing release.',
        'readiness の発注ゲートが BLOCKED（製造リリースまでの全条件を数えている）。この基準セットからは直接アップロードしない。オーナーが試作ルートでアップロードするのは `engineering/a7/jlc-package/order/` の日付付きの写しで、その README の注文画面の確認の後。どれも製造リリースではない。')
    for b in boards:
        t, n, r = b['pcba_tier'], b['board'], b['assembly_route']
        if r['panel']:
            pn, rp = r['panel'], b['repo_panel']
            prepared = n in panels
            jlc_n, repo_n = pn['boards_per_panel'] * 2, rp['assembled_at_minimum_order']
            q = ' '.join(x['text'] for x in r['open_questions'])
            qj = ''.join(x['ja'] for x in r['open_questions'])
            if chosen == 'repo-panels':
                add(f'{n}-repo-panel-acceptance', n,
                    f"The owner chose repo panels (assembly:panel-route): {rp['copies']} board(s) on a {fmt(rp['panel_mm'][0])} × {fmt(rp['panel_mm'][1])} mm panel, "
                    f"PCBA quantity 2, giving {repo_n} for the {b['pcba_quantity']} needed. Whether JLC assembles this customer panel is {jlc_en}; "
                    'the panel files are prepared in engineering/a7/jlc-package/panels/ and not released.',
                    f"オーナーはリポジトリ面付けを選んだ（`assembly:panel-route`）。{rp['copies']} 枚入りの面付け（{fmt(rp['panel_mm'][0])} × {fmt(rp['panel_mm'][1])} mm）を PCBA 数量 2 で注文し、"
                    f"必要な {b['pcba_quantity']} 枚に対し {repo_n} 枚。JLC がこの面付けを実装するかは{jlc_ja}。面付けデータは `engineering/a7/jlc-package/panels/` に準備済み（未リリース）。")
            else:
                add(f'{n}-panel-route', n,
                    f"Not orderable as single boards ({'; '.join(c['criterion'] + ' fails' for c in r['economic_checks'] if not c['ok'])}). "
                    f"Panel by JLCPCB ({pn['columns_x']} × {pn['rows_y']}) gives {jlc_n} assembled boards at a 2-panel minimum{(' and has open questions: ' + q) if q else ''}. "
                    f"A repo-built panel with {rp['copies']} board(s), {fmt(rp['panel_mm'][0])} × {fmt(rp['panel_mm'][1])} mm, gives {repo_n} for the {b['pcba_quantity']} needed. "
                    'The owner decides the route (assembly:panel-route); ' + ('the repo panel is prepared in engineering/a7/jlc-package/panels/, not released.' if prepared else 'the panel is not built.'),
                    f"単品では発注できない（Economic で満たさない条件: {'、'.join(c['ja'] for c in r['economic_checks'] if not c['ok'])}）。"
                    f"Panel by JLCPCB（{pn['columns_x']} × {pn['rows_y']}）は 2 シート最小で {jlc_n} 枚が実装される{('。未確認: ' + qj) if qj else '。'}"
                    f"リポジトリで {rp['copies']} 枚入りの面付け（{fmt(rp['panel_mm'][0])} × {fmt(rp['panel_mm'][1])} mm）を作れば、必要な {b['pcba_quantity']} 枚に対し {repo_n} 枚。"
                    'どちらにするかはオーナーの判断（`assembly:panel-route`）。' + ('リポジトリ面付けのデータは `engineering/a7/jlc-package/panels/` に準備した（未リリース）。' if prepared else '面付けデータはまだ作っていない。'))
        if not b['copper_finish_in_board_file']:
            eco = t['tier'] == 'ECONOMIC'
            add(f'{n}-finish-not-specified', n, 'Surface finish is not recorded in the board file; it must be chosen on the order form'
                + (' (the Economic table lists HASL or ENIG for 1.6 mm green).' if eco else '.'),
                '表面処理が基板ファイルに記録されていない。注文画面で選ぶ' + ('（Economic の 1.6 mm 緑は HASL か ENIG）。' if eco else '。'))
        if b['centroid_offsets']:
            refs = ', '.join(c['ref'] for c in b['centroid_offsets'])
            add(f'{n}-centroid-offsets', n, f"{len(b['centroid_offsets'])} parts have a footprint anchor more than {CENTROID_TOLERANCE_MM} mm from their pad centre ({refs}); "
                'JLC places by component centroid, so check each in the JLC placement preview.',
                f"{refs} はフットプリント原点がパッド中心から {CENTROID_TOLERANCE_MM} mm 以上離れている。JLC は部品中心で置くので、JLC の配置プレビューで 1 点ずつ確かめる。")
        bottom = 'Bottom' in b['assembly_sides']
        add(f'{n}-rotation-unverified', n, 'Rotations are KiCad footprint angles; JLC library orientation offsets have not been checked in the JLC placement preview'
            + (' (including bottom-side parts)' if bottom else '') + '.',
            '回転角は KiCad のフットプリント角度のまま。JLC ライブラリとの向きの差は JLC の配置プレビューで未確認' + ('（B 面の部品を含む）' if bottom else '') + '。')
    for l in lines:
        if l['route'] != 'JLC_STOCK':
            add(f"part-{l['lcsc']}-not-in-stock", None,
                f"{l['mpn']} ({l['lcsc']}): need {l['pieces_required']}, JLC in-stock {l['in_stock']}, pre-order available {l['preorder_available']} at {l['observed_at']}.",
                f"{l['mpn']}（{l['lcsc']}）: 必要 {l['pieces_required']} 個に対し、{l['observed_at']} の JLC 在庫 {l['in_stock']}・予約可能数 {l['preorder_available']}。")
    add('pcba-quantity-unit-with-panel-not-sourced', None,
        'The PCBA minimum is "2 pcs" in the capability table. With Panel by JLCPCB the PCB quantity counts panels (JLC: 10 pcs ordered gives 10 panels);'
        ' whether the PCBA quantity also counts panels, and whether one panel holding 2 or more boards meets the 2-pcs minimum, is not sourced. '
        'Question for the JLC order form or support: ' + PCBA_UNIT_QUESTION
        + (' The owner stated, without asking JLC, that each Gerber is ordered at PCBA quantity 2 or more (jlc-questions); this is owner-stated, not JLC-confirmed.' if stated else ''),
        'JLC 能力表の PCBA 最小は「2 pcs」。Panel by JLCPCB では PCB の数量は面付けシートの枚数（JLC の説明: 10 pcs 注文で 10 シート）。'
        'PCBA の数量もシート数か、2 枚以上載った 1 シートで最小 2 pcs を満たすかは未取得。JLC の注文画面かサポートで確かめる質問: ' + PCBA_UNIT_QUESTION
        + ('。オーナーは JLC に聞かずに、Gerber ごとに PCBA 数量 2 以上で注文すると述べた（jlc-questions）。オーナーの知識による判断で、JLC の確認ではない。' if stated else ''))
    add('pcb-fabrication-quantity-not-sourced', None,
        'The minimum bare-PCB quantity JLC fabricates per design was not read; the PCBA quantity (2 controller, 4 leaf, 2 adapter) is entered separately.',
        'JLC が 1 設計あたり製造する基板の最小枚数は未取得。PCBA の数量（コントローラー 2・リーフ 4・電源アダプタ 2）とは別に入力する。')
    waiver = owner_entry('jack-tip-test-waiver', root)
    if any(x['id'] == 'jack-switch-qualification' for x in ledger['blockers']) and waiver:
        add('physical-jack-switch-qualification', 'controller',
            f"PJ-324M terminal 4/5 function is not confirmed. The owner waived the pre-order continuity test and accepted the risk ({waiver['decided_on']}, jack-tip-test-waiver): "
            'if terminal 5 is the tip, both jacks fail and the controller needs a revision. The check stays as a first-article check on the assembled boards.',
            f"PJ-324M の端子 4/5 の機能は未確認。オーナーは発注前の導通試験を見送り、リスクを受け入れた（{waiver['decided_on']}、jack-tip-test-waiver）。"
            '端子 5 が tip なら両方のジャックが働かず、制御基板の改版が要る。確認は組み立て済み基板の初品検査として残る。')
    elif any(x['id'] == 'jack-switch-qualification' for x in ledger['blockers']):
        add('physical-jack-switch-qualification', 'controller',
            'PJ-324M terminal 4/5 function must be confirmed by continuity on a received part before any PCB order (procurement blocker jack-switch-qualification).',
            'PJ-324M の端子 4/5 の機能は、PCB を発注する前に入荷した実物の導通で確かめる（調達台帳の jack-switch-qualification）。')
    return out


# --- page --------------------------------------------------------------------------------------
BOARD_JA = {'controller': 'コントローラー', 'led_leaf': 'LED リーフ', 'power_adapter': '電源アダプタ'}
ROUTE_JA = {'JLC_STOCK': 'JLC 在庫', 'JLC_PREORDER': 'JLC 予約注文', 'JLC_PREORDER_OR_GLOBAL_SOURCING_BLOCKED': '在庫なし・予約不可（Global Sourcing か待つ）', 'EXCEPTION': '例外'}


def owner_entry(entry_id, root=ROOT):
    """One owner-decided entry of owner-decisions.json by id, or None."""
    found = [d for d in json.loads((root / OWNER_DECISIONS).read_text()).get('decisions', []) if d.get('id') == entry_id and d.get('decided_by') == 'OWNER']
    return found[0] if len(found) == 1 else None


def panel_decision(root=ROOT):
    """The owner's recorded panel route (owner-decisions.json, id panel-route), or None while it is open."""
    found = [d for d in json.loads((root / OWNER_DECISIONS).read_text()).get('decisions', []) if d.get('id') == 'panel-route' and d.get('decided_by') == 'OWNER']
    return {'answer': found[0]['answer'], 'decided_by': 'OWNER', 'decided_on': found[0]['decided_on'], 'record': str(OWNER_DECISIONS)} if found else None


def load_panels(root=ROOT):
    """Committed repo-panel layouts (scripts/a7_panel.py) by board; empty when none are prepared."""
    d = root / PANELS
    return {p.name[:-len('-panel.json')]: json.loads(p.read_text()) for p in sorted(d.glob('*-panel.json'))} if d.is_dir() else {}


def page(report, panels=None):
    panels = load_panels() if panels is None else panels
    L = ['---', '# GENERATED by scripts/a7_jlc_package.py — do not edit; run `python3 scripts/a7_jlc_package.py`',
         'title: "JLCPCB 発注パッケージ（試作用・製造リリースではない）"',
         'description: "最初の 2 台分を JLCPCB に発注するとき、基板ごとに何を入力し何をアップロードするか。試験用試作のためで、製造リリースではありません。"',
         'sidebar_position: 4.6', '---', '', ':::danger[製造リリースではありません]',
         f"発注ゲートは **{report['order_eligibility']}** です（製造リリースまでの全条件を数えています）。このページと `engineering/a7/jlc-package/` 直下・`panels/` のファイルは生成器の基準セットで、"
         'ここから直接アップロードしません。オーナーが試験用試作ルートでアップロードするのは日付付きの写し'
         + ('（' + '、'.join(f'`{d}/`' for d in report['dated_order_exports']) + '）' if report['dated_order_exports'] else '（まだ無い）')
         + 'で、その README にある注文画面での確認（配置プレビューの中心・回転、PCBA 数量の単位、自前パネルの受入、基材・表面処理）の後です。'
         + ('試作ルートの承認は現在の識別に結び付いていません（readiness の `owner_prototype_route`）。新しい識別での再承認はオーナーの判断です。' if report['prototype_route_binding'].startswith('HOLD') else
            '試作ルートのオーナー承認は現在の識別に結び付いています（`engineering/a7/qualification/records.json`）。')
         + '発注・支払いはオーナーが行い、リポジトリに発注記録はありません。', ':::', '',
         f"数量はオーナーの判断で **{report['modules']} 台**です。JLC の PCBA 最小は 2 pcs です（2026-11-12 取得の JLC 公開能力表: Economic 2–50 pcs、Standard 2–80000 pcs。"
         '面付けした場合に pcs が単品か面付けシートかは未確認）。', '',
         '## 止めている項目', '']
    for b in report['blockers']:
        L.append(f"- `{b['id']}`" + (f"（{BOARD_JA[b['board']]}）" if b['board'] else '') + ': ' + esc(b['ja']))
    for b in report['boards']:
        t = b['pcba_tier']
        L += ['', f"## {BOARD_JA[b['board']]}（`{b['board']}`）", '',
              f"PCB 注文画面に入れる値（材料以外は基板ファイル `{b['pcb']}` から読んだもの）:", '',
              '| 項目 | 値 |', '|---|---|',
              f"| Base Material | {base_row(b['base_material'])} |",
              f"| Layers | {b['copper_layers']} |",
              f"| Dimensions | {fmt(b['outline_mm']['width'])} × {fmt(b['outline_mm']['height'])} mm |",
              f"| PCB Thickness | {fmt(b['thickness_mm'])} mm（JLC 公差 {b['thickness_tolerance']}" + ('。A5 の寸法を引き継いだ凍結値で、1.6 mm ではない。0.6 mm は JLC の FR-4 の選択肢にある' if b['board'] == 'led_leaf' and b['thickness_mm'] < 1.0 else '') + '） |',
              f"| Surface Finish | {b['copper_finish_in_board_file'] or '基板ファイルに指定なし（注文時に選ぶ）'} |",
              f"| 最小穴径 | {fmt(b['min_drill_mm'])} mm |" if b['min_drill_mm'] else '| 最小穴径 | — |',
              f"| PCB Assembly | オン。必要な完成品は単品 {b['pcba_quantity']} 枚（{b['per_module']} 枚/台 × {report['modules']} 台）。面付け時に PCBA Qty をシート数で入れるかは未確認（`pcba-quantity-unit-with-panel-not-sourced`） |",
              f"| PCBA Type | {t['tier'].title()}" + (f"（理由: {esc('、'.join(t['reasons_ja']))}）" if t['reasons_ja'] else '') + ' |',
              f"| Assembly Side | {'Top と Bottom（両面）' if len(b['assembly_sides']) > 1 else b['assembly_sides'][0]} |",
              f"| Panel By JLCPCB | {panel_cell(b, report['panel_comparison'], report['panel_route'])} |",
              f"| 実装点 | SMD {b['smd_count']}・THT {len(b['tht_refs'])}" + (f"（{', '.join(b['tht_refs'])}）" if b['tht_refs'] else '') + ' |', '',
              *route_lines(b, report['panel_comparison'], panels.get(b['board']), report['panel_route']),
              'アップロードするもの' + (('（使わない経路: JLC 面付け。参考に残す）' if (report['panel_route'] or {}).get('answer') == 'repo-panels' else '（JLC 面付けの経路、または単品）') if b['board'] in panels else '') + ':', '',
              f"1. Gerber と drill の zip: `python3 scripts/a7_jlc_package.py export --out <リポジトリ外の空ディレクトリ>` で作る `{b['board']}-gerbers-DRYRUN.zip`（Gerber 原点: {b['gerber_origin']}）",
              f"2. BOM: `engineering/a7/jlc-package/{b['board']}_BOM_DRYRUN.csv`（{b['bom_lines']} 行、列 Comment / Designator / Footprint / JLCPCB Part #）",
              f"3. CPL: `engineering/a7/jlc-package/{b['board']}_CPL_DRYRUN.csv`（{b['cpl_rows']} 行、列 Designator / Mid X / Mid Y / Rotation / Layer、mm）", '',
              *repo_panel_upload(b, panels.get(b['board']), report['panel_route'])]
        if b['centroid_offsets']:
            L += ['JLC の配置プレビューで中心を確かめる部品（フットプリント原点がパッド中心から離れているもの）:', '',
                  '| Ref | LCSC | 原点からパッド中心まで |', '|---|---|---:|']
            L += [f"| {c['ref']} | {c['lcsc']} | {fmt(c['anchor_to_pad_centre_mm'])} mm |" for c in b['centroid_offsets']]
    c = report['panel_comparison']
    L += ['', '## 面付けの経路と部品数（2 台分を最小の余りで）', '',
          f"JLC が面付けすると 1 シートに何枚も載り、最小 2 シートを実装すると必要数を大きく超えます（{c['assumption_ja']}）。"
          'リポジトリで必要枚数だけを載せた面付けを作ると、2 シートでちょうど 2 台分です。', '',
          '| 基板 | 必要 | JLC 面付け 2 シート | リポジトリ面付け 2 シート | 推奨 |', '|---|---:|---:|---:|---|']
    L += [f"| {BOARD_JA[n]} | {v['needed']} | {v['jlc_panel']} | {v['repo_panel']} | {'リポジトリ面付け' if v['recommended'] == 'REPO_PANEL' else 'JLC 面付け'} |" for n, v in c['boards'].items()]
    short = [x for x in c['parts'] if x['jlc_panel_short'] or x['repo_panel_short']]
    L += ['', '部品ごとの数（JLC 在庫は 2026-11-12 の観測値）:', '', '| LCSC | 型番 | 2 台分 | JLC 面付け | リポジトリ面付け | JLC 在庫 | 予約可能数 |', '|---|---|---:|---:|---:|---:|---:|']
    L += [f"| {x['lcsc']} | {esc(x['mpn'])} | {x['needed']} | {('**' + str(x['jlc_panel']) + '**') if x['jlc_panel_short'] else x['jlc_panel']} | "
          f"{('**' + str(x['repo_panel']) + '**') if x['repo_panel_short'] else x['repo_panel']} | {x['in_stock']} | {x['preorder_available']} |" for x in c['parts']]
    L += ['', 'JLC の部品照合で Do Not Place を選んだ designator は実装されません（JLC の部品照合ガイド）。ただし JLC 面付けで余る基板だけを未実装にできるかは取得していないので、上の表は全数実装で数えています。'
          'JLC の FAQ では、フィデューシャルは JLC が SMT 用に付けるので自分で付けなくてよいとされています。', '']
    L += ['太字は JLC 在庫を超える数です。' + (f"{'、'.join(x['mpn'] for x in short)} はどちらの経路でも在庫が足りず、JLC 面付けでは "
          + '、'.join(f"{x['jlc_panel']} 個" for x in short) + ' が必要になります。' if short else ''), '']
    L += ['', '## 部品の区分（2026-11-12 の JLC 部品ページ）', '',
          f"Basic {report['part_counts']['BASIC']} 種・Extended {report['part_counts']['EXTENDED']} 種。必要数は 2 台分です。在庫数は観測時点の値で、確保ではありません。", '',
          '| LCSC | 型番 | 区分 | 必要数 | JLC 在庫 | 予約可能数 | 経路 |', '|---|---|---|---:|---:|---:|---|']
    L += [f"| {l['lcsc']} | {esc(l['mpn'])} | {l['library'].title()} | {l['pieces_required']} | {l['in_stock']} | {l['preorder_available']} | {ROUTE_JA[l['route']]} |" for l in report['parts']]
    L += ['', '区分と在庫は `engineering/a7/jlc-package/sources.json` の日付付き記録です（項目の意味はこちらの解釈で、JLC の定義ではありません）。', '']
    return '\n'.join(L) + '\n'


def panel_cell(b, comparison, decision=None):
    r = b['assembly_route']
    if not r['panel']:
        return 'No（単品）'
    if (decision or {}).get('answer') == 'repo-panels':
        return 'No（オーナーの判断でリポジトリ面付け。面付けは Gerber 側）'
    p = r['panel']
    jlc = f"JLC 面付けなら Yes・列 (X) {p['columns_x']}・行 (Y) {p['rows_y']}" + ('・Edge Rails あり' if p['edge_rails'] else '')
    repo = 'リポジトリ面付けなら No（面付けは Gerber 側）'
    rec = comparison['boards'][b['board']]['recommended']
    return f"経路の判断待ち。{jlc}。{repo}。推奨は{'リポジトリ面付け' if rec == 'REPO_PANEL' else 'JLC 面付け'}"


def route_lines(b, comparison, prepared=None, decision=None):
    r, rp, c = b['assembly_route'], b['repo_panel'], comparison['boards'][b['board']]
    L = ['Economic で単品実装できるか（2026-11-12 の JLC 能力表と部品ページで判定）:', '', '| 条件 | この基板 | 判定 |', '|---|---|---|']
    L += [f"| {esc(x['ja'])} | {esc(x['value'])} | {'満たす' if x['ok'] else '**満たさない**'} |" for x in r['economic_checks']]
    L.append('')
    if not r['panel']:
        L += [f"結論: **単品で {r['tier'].title()} PCBA**。", '']
        return L
    p = r['panel']
    jlc_cut = ('マウスバイト（Economic では V-cut 不可）' if r['tier'] == 'ECONOMIC' else 'V-cut かマウスバイト') + ('。辺が 15 mm 未満なので V-cut は追加料金' if p['vcut_extra_cost'] else '')
    L += [f"結論: 単品では受けてもらえません。{r['tier'].title()} PCBA で、面付けの経路を 2 つ比べました（PCBA 数量がシート数で最小 2 シートと仮定。未確認）。", '',
          f"| | JLC が面付け（Panel by JLCPCB） | リポジトリで面付け（{'準備済み・未リリース' if prepared else '未作成'}） |", '|---|---|---|',
          f"| 1 シート | {p['columns_x']} 列 × {p['rows_y']} 行 = {p['boards_per_panel']} 枚（レールなしで {fmt(p['size_without_rails_mm'][0])} × {fmt(p['size_without_rails_mm'][1])} mm。JLC は既定で {JLC_RAIL_MM} mm の縁を足す） | "
          f"{rp['copies']} 枚、{fmt(rp['panel_mm'][0])} × {fmt(rp['panel_mm'][1])} mm（{fmt(rp['rail_mm'])} mm レール込み、最小 {rp['panel_minimum_mm']} × {rp['panel_minimum_mm']} mm） |",
          f"| 2 シートで実装される枚数（必要 {c['needed']}） | {c['jlc_panel']} | {c['repo_panel']} |",
          f"| 分割 | {jlc_cut} | マウスバイト、タブ幅 {fmt(TAB_MIN_MM)} mm 以上 |",
          f"| フィデューシャル | {'Edge Rails をオンにすると JLC がレールに付ける' if p['edge_rails'] else '不要（Economic）'} | レールに 1 mm（縁から 3.85 mm）と 2 mm の治具穴（JLC の SMT 指針） |",
          f"| 未確認・注意 | {esc(''.join(q['ja'] for q in r['open_questions'])) or 'JLC の注文画面のプレビュー'} | {esc(''.join(rp['notes_ja']))}JLC が{' 1 枚だけの' if rp['copies'] == 1 else 'この'}面付けを受けるかは注文時に確認。 |", '',
          f"推奨: **{'リポジトリで面付け' if c['recommended'] == 'REPO_PANEL' else 'JLC が面付け'}**（余る実装基板が最も少ない）。" + (f"**オーナーの判断: リポジトリ面付け**（{decision['decided_on']}、`assembly:panel-route`、記録 `{decision['record']}`）。種類ごとに 1 つの Gerber を PCBA 数量 2 で注文します。JLC がこの面付けを実装するかは" + ('オーナーの知識による判断で、JLC の確認ではない（オーナーは JLC に聞かずに O12 を閉じた。jlc-questions）。' if owner_entry('jlc-questions') else '未確認（O12）。')
          if (decision or {}).get('answer') == 'repo-panels' else 'オーナーの判断待ち（`assembly:panel-route`）です。')
          + ('リポジトリ面付けのデータは準備済みですが、リリースではありません（下の「リポジトリ面付けでアップロードするもの」）。' if prepared else '面付けデータはまだ作っていません。'), '']
    return L


def repo_panel_upload(b, lay, decision=None):
    if not lay:
        return []
    n, W, H = b['board'], lay['panel_mm'][0], lay['panel_mm'][1]
    tabs = '・'.join(f"{k} 枚目 {v} か所" for k, v in lay['tabs_per_copy'].items())
    chosen = (decision or {}).get('answer') == 'repo-panels'
    L = ['リポジトリ面付けでアップロードするもの' + ('（オーナーが選んだ経路。基準セットで、アップロードは日付付きの写しから。製造リリースではない）:' if chosen else '（準備済みの経路。オーナーが `assembly:panel-route` でこの経路を選ぶまで使いません）:'), '',
         f"1. Gerber と drill の zip: `python3 scripts/a7_panel.py build --out <リポジトリ外の空ディレクトリ>` で作る `{n}-panel-gerbers-DRYRUN.zip`"
         f"（{fmt(W)} × {fmt(H)} mm、{len(lay['copies'])} 枚載せ。注文画面の Dimensions はこのシート寸法、Panel By JLCPCB は No）",
         f"2. BOM: `engineering/a7/jlc-package/panels/{n}-panel_BOM_DRYRUN.csv`（2 枚目以降の designator は `_2` などの接尾辞）",
         f"3. CPL: `engineering/a7/jlc-package/panels/{n}-panel_CPL_DRYRUN.csv`（シート左上の外形角が原点、mm）", '',
         f"シートの作り: {fmt(lay['rules']['rail_mm'])} mm のレール、基板まわり {fmt(min(lay['rules']['edge_gap_mm'].values()))} mm 以上の切り溝、"
         f"{fmt(lay['rules']['tab_mm'])} mm のマウスバイトタブ（{tabs}、穴 {fmt(lay['mouse_bites']['diameter_mm'])} mm・間隔 {fmt(lay['mouse_bites']['gap_mm'])} mm）、"
         f"{fmt(lay['fiducials']['diameter_mm'])} mm フィデューシャル 3 個（{'両面' if len(lay['fiducials']['sides']) > 1 else '表面'}）、"
         f"{fmt(lay['tooling_holes']['diameter_mm'])} mm 治具穴 3 個。"
         'フィデューシャルの横位置（シート幅の 30 %・70 %）とタブの位置・数は提案で、JLC の規則ではありません。'
         '`a7_panel.py build`（CI の native ジョブで毎回実行）が、保存した面付け基板を読み直して次を確かめます: 各基板の部品・パッド（各層の寸法・形・マスク/ペースト余白）・配線・ビア・ゾーン（塗りつぶし形状）・図形・文字が凍結ファイルと移動量を除いて一致すること、'
         '面付けの Edge.Cuts から求めた各基板の外形が凍結ファイルの外形と一致すること、穴（長穴を含む）が凍結ファイルの穴＋マウスバイト穴＋治具穴と一致すること、フィデューシャルが計画どおりの位置にあること、'
         '面付け DRC の違反数が元の基板の違反数（×枚数）と種類ごとに一致すること（記録した例外は件数も固定）、CPL が KiCad の位置出力と一致すること。'
         'Gerber どうしの比較はしていません。マウスバイト穴は基板の縁の外に置くので、分割後は各タブの位置に最大約 0.3 mm の突起が残り、実物の外形は凍結ファイルの外形より少し出ます。']
    if lay['drc_waivers']:
        L.append('面付け DRC の例外: ' + '、'.join(f"`{k}`" for k in lay['drc_waivers']) + '（コートヤードの外に 2 か所のタブを置けないので、タブをはみ出した部品の下に置いた。基板の外にあるマウスバイト穴がその部品の外形枠の内側に入る。件数は `build-receipt.json` に固定）。')
    L.append('')
    return L


def base_row(m):
    return f"{m['value']}（`{m['source']}`。基板ファイルには材料の記録なし）" if m['value'] else '基板ファイルにもレイアウト記録にも材料の記録なし（注文画面で選ぶ）'


def esc(text):
    return str(text).replace('{', '&#123;').replace('}', '&#125;').replace('<', '&lt;').replace('>', '&gt;').replace('|', '\\|')


# --- export (pinned KiCad image) --------------------------------------------------------------------
def export(out, write_receipt=False):
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise SystemExit('refusing: --out must be outside the repository')
    if out.exists() and any(out.iterdir()):
        raise SystemExit('refusing: --out must be empty or absent')
    out.mkdir(parents=True, exist_ok=True)
    report, _ = generate()
    image = json.loads((ROOT / PROFILE).read_text())['image']
    lines = ['set -u']
    for b in report['boards']:
        n = b['board']
        layers = FAB_LAYERS + (['In1.Cu', 'In2.Cu'] if b['copper_layers'] == 4 else [])
        lines.append(f"mkdir -p /out/{n}/gerbers && kicad-cli pcb export gerbers --layers {','.join(layers)} --output /out/{n}/gerbers/ /repo/{b['pcb']} > /out/{n}.log 2>&1"
                     f" && kicad-cli pcb export drill --format excellon --excellon-separate-th --output /out/{n}/gerbers/ /repo/{b['pcb']} >> /out/{n}.log 2>&1"
                     f" && kicad-cli pcb export pos --format csv --units mm --side both --output /out/{n}/kicad-pos.csv /repo/{b['pcb']} >> /out/{n}.log 2>&1; echo $? > /out/{n}.code")
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '2', '--memory', '4g', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
           '--label', LABEL, '-u', f'{os.getuid()}:{os.getgid()}', '-e', 'HOME=/tmp', '-v', f'{ROOT}:/repo:ro', '-v', f'{out}:/out', image, 'bash', '-c', '\n'.join(lines)]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    summary = {'what': 'JLC order-package dry-run export; NOT order files', 'image': image, 'docker_exit': p.returncode, 'boards': {}}
    fails = []
    for b in report['boards']:
        n = b['board']
        code = (out / f'{n}.code').read_text().strip() if (out / f'{n}.code').is_file() else None
        gdir = out / n / 'gerbers'
        names = sorted(q.name for q in gdir.iterdir()) if gdir.is_dir() else []
        z = out / f'{n}-gerbers-DRYRUN.zip'
        with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
            for q in names:
                zf.write(gdir / q, q)
        diffs = compare_pos(out / n / 'kicad-pos.csv', ROOT / OUT / f'{n}_CPL_DRYRUN.csv') if code == '0' else ['export failed']
        summary['boards'][n] = {'code': code, 'files': names, 'zip': z.name, 'cpl_vs_kicad': diffs or 'MATCH'}
        if code != '0' or diffs:
            fails.append(f'{n}: export code {code}, CPL differences {diffs[:5]}')
        want = {f'{n}-{l.replace(".", "_").replace("SilkS", "Silkscreen")}' for l in FAB_LAYERS + (['In1.Cu', 'In2.Cu'] if b['copper_layers'] == 4 else [])}
        have = {q.rsplit('.', 1)[0] for q in names}
        if want - have or not {f'{n}-PTH.drl', f'{n}-NPTH.drl'} <= set(names):
            fails.append(f'{n}: Gerber/drill set incomplete: missing {sorted(want - have)} or drill files in {names}')
    receipt = ROOT / OUT / 'export-receipt.json'
    recorded = {n: v['files'] for n, v in summary['boards'].items()}
    if write_receipt:
        receipt.write_text(json.dumps({'what': 'File names from the last dry-run export (pinned KiCad image); CPL matched KiCad position export. NOT order files.',
                                       'image': image, 'files': recorded}, indent=2) + '\n')
    elif not receipt.is_file() or json.loads(receipt.read_text())['files'] != recorded or json.loads(receipt.read_text())['image'] != image:
        fails.append('export file set differs from engineering/a7/jlc-package/export-receipt.json')
    summary['status'] = 'FAIL' if fails else 'PASS'
    summary['failures'] = fails
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    (out / 'README-DRY-RUN-NOT-FOR-ORDER.txt').write_text('DRY RUN - NOT RELEASED - DO NOT UPLOAD OR ORDER FROM THESE FILES\n'
                                                         'The readiness order gate is BLOCKED; see doc/src/content/docs/project/jlc-order-package.mdx.\n')
    print(json.dumps(summary, indent=2))
    return 1 if fails else 0


def compare_pos(kicad_csv, cpl_csv):
    k = {r['Ref']: r for r in csv.DictReader(kicad_csv.read_text().splitlines())}
    c = {r['Designator']: r for r in csv.DictReader(cpl_csv.read_text().splitlines())}
    diffs = []
    if set(k) != set(c):
        diffs.append(f'references differ: only KiCad {sorted(set(k) - set(c))}, only CPL {sorted(set(c) - set(k))}')
    for ref in sorted(set(k) & set(c)):
        a, b = k[ref], c[ref]
        if abs(float(a['PosX']) - float(b['Mid X'])) > 1e-4 or abs(float(a['PosY']) - float(b['Mid Y'])) > 1e-4:
            diffs.append(f"{ref}: position KiCad ({a['PosX']}, {a['PosY']}) vs CPL ({b['Mid X']}, {b['Mid Y']})")
        if abs(norm_rot(float(a['Rot'])) - float(b['Rotation'])) > 1e-4:
            diffs.append(f"{ref}: rotation KiCad {a['Rot']} vs CPL {b['Rotation']}")
        if {'top': 'Top', 'bottom': 'Bottom'}.get(a['Side']) != b['Layer']:
            diffs.append(f"{ref}: side KiCad {a['Side']} vs CPL {b['Layer']}")
    return diffs


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command', nargs='?', default='generate', choices=['generate', 'export'])
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--out', type=Path)
    ap.add_argument('--write-receipt', action='store_true', help='record the export file set (after a reviewed change)')
    a = ap.parse_args()
    if a.command == 'export':
        if not a.out:
            ap.error('export needs --out')
        return export(a.out, a.write_receipt)
    report, files = generate()
    targets = {ROOT / OUT / k: v for k, v in files.items()}
    targets[ROOT / PAGE] = page(report, load_panels())
    for path, text in targets.items():
        if a.check:
            if not path.is_file() or path.read_text() != text:
                raise SystemExit(f'stale: {path.relative_to(ROOT)}; run scripts/a7_jlc_package.py')
        else:
            path.write_text(text)
    print(f"{'PASS' if a.check else 'WROTE'}: JLC package dry run ({report['status']}, order gate {report['order_eligibility']}, {len(report['blockers'])} blockers)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
