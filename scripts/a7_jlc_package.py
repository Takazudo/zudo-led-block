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
LEDGER = 'engineering/a7/procurement/assembly-manifest.json'
READINESS = 'engineering/a7/qualification/readiness.json'
PROFILE = 'engineering/a7/verification/native_gate.json'
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
    xs, ys = [], []
    for g in tree[1:]:
        if isinstance(g, list) and g and g[0] in ('gr_line', 'gr_rect', 'gr_arc', 'gr_poly', 'gr_circle') and kid(g, 'layer') and kid(g, 'layer')[1] == 'Edge.Cuts':
            for key in ('start', 'end', 'mid'):
                if kid(g, key):
                    x, y = nums(kid(g, key))[:2]
                    xs.append(x)
                    ys.append(y)
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
        footprints.append({'ref': props.get('Reference'), 'value': props.get('Value'), 'footprint': fp[1],
                           'lcsc': props.get('LCSC'), 'mpn': props.get('MPN'), 'layer': kid(fp, 'layer')[1],
                           'x': at[0], 'y': at[1], 'rot': at[2] if len(at) > 2 else 0.0, 'flags': sorted(flags),
                           'dnp': bool(kid(fp, 'dnp')) or 'dnp' in flags, 'pads': pads})
    for via in kids(tree, 'via'):
        d = nums(kid(via, 'drill'))
        if d:
            drills.append(d[0])
    return {'path': str(path), 'sha256': sha(ROOT / path), 'thickness_mm': nums(kid(general, 'thickness'))[0],
            'copper_layers': copper, 'copper_finish': finish[1] if finish else None,
            'outline_mm': {'x': [min(xs), max(xs)], 'y': [min(ys), max(ys)],
                           'width': round(max(xs) - min(xs), 3), 'height': round(max(ys) - min(ys), 3)},
            'gerber_uses_aux_origin': bool(plot and kid(plot, 'useauxorigin') and kid(plot, 'useauxorigin')[1] == 'yes'),
            'aux_axis_origin': nums(aux) if aux else None, 'min_drill_mm': min(drills) if drills else None,
            'fiducials': [f['ref'] for f in footprints if 'fiducial' in (f['footprint'] + str(f['value'])).lower()],
            'footprints': footprints}


def fmt(v):
    return f'{v:.4f}'.rstrip('0').rstrip('.') if v != int(v) else str(int(v))


def norm_rot(r):
    r = round(r % 360, 4)
    return 0.0 if r == 360 else r


# --- generate ------------------------------------------------------------------------------------
def generate(root=ROOT):
    proc = load_procurement()
    ledger = json.loads((root / LEDGER).read_text())
    if ledger != proc.generate(root):
        raise ValueError('procurement ledger is stale; run scripts/a7_procurement.py first')
    sources = json.loads((root / SOURCES).read_text())
    parts = {p['lcsc']: p for p in sources['parts']}
    pages = {p['id']: p for p in sources['pages']}
    plan = ledger['order_plan']
    modules = plan['modules']
    basis = plan['pcba_minimum_boards']
    if basis['status'] == 'SOURCED' and (basis['source']['sha256'], basis['source']['url']) != (pages['jlc-pcba-capabilities']['raw_sha256'], pages['jlc-pcba-capabilities']['url']):
        raise ValueError('PCBA minimum source differs from the dated capability receipt in sources.json')
    if not any(basis['source'] and basis['source'].get('quote', '') in e for e in pages['jlc-pcba-capabilities']['extracts']):
        raise ValueError('PCBA minimum quote is not in the capability receipt extracts')
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
            'pcba_tier': pcba_tier(facts, sides, layers, fitted, parts),
        })
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
    blockers = named_blockers(boards, lines, pages, ledger, root)
    readiness = json.loads((root / READINESS).read_text())
    report = {'schema': 1, 'status': 'DRY_RUN_NOT_RELEASED', 'order_eligibility': readiness['order_eligibility'],
              'modules': modules, 'decided_by': plan['decided_by'], 'sources': str(SOURCES),
              'ledger_sha256': sha(root / LEDGER), 'sources_sha256': sha(root / SOURCES),
              'boards': boards, 'parts': lines,
              'part_counts': {k: sum(1 for l in lines if l['library'] == k) for k in ('BASIC', 'EXTENDED')},
              'route_counts': {k: sum(1 for l in lines if l['route'] == k) for k in sorted({l['route'] for l in lines})},
              'blockers': blockers}
    files['package.json'] = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
    return report, files


def to_csv(header, rows):
    s = io.StringIO()
    w = csv.DictWriter(s, fieldnames=header, lineterminator='\n')
    w.writeheader()
    w.writerows(rows)
    return s.getvalue()


# The 2026-11-06 A5 JLC audit recorded each part's PCBA type; parts listed there as Standard only force Standard PCBA.
A5_AUDIT = 'engineering/a5/research_jlc_electronics.json'


def standard_only_parts(root=ROOT):
    audit = json.loads((root / A5_AUDIT).read_text())
    return {p['code'] for p in audit['parts_audited'] if p.get('pcba_type') == 'Standard Only'}


def pcba_tier(facts, sides, layers, fitted, parts):
    """Which JLC PCBA tier the board needs, from the 2026-11-12 capability table (sources.json)."""
    reasons, ja = [], []
    only = sorted({r['lcsc'] for r in fitted.values()} & standard_only_parts())
    if only:
        reasons.append(', '.join(only) + ' listed as Standard-only PCBA in the 2026-11-06 A5 JLC audit')
        ja.append(', '.join(only) + ' は 2026-11-06 の A5 JLC 調査で Standard のみ')
    if len(sides) > 1:
        reasons.append('parts on both sides (Economic is single-sided placement only)')
        ja.append('両面に部品がある（Economic は片面のみ）')
    if not 0.8 <= facts['thickness_mm'] <= 1.6:
        reasons.append(f"thickness {fmt(facts['thickness_mm'])} mm (Economic takes 0.8–1.6 mm)")
        ja.append(f"板厚 {fmt(facts['thickness_mm'])} mm（Economic は 0.8–1.6 mm）")
    if layers not in (2, 4, 6):
        reasons.append(f'{layers} copper layers (Economic takes 2, 4 or 6)')
        ja.append(f'銅層 {layers}（Economic は 2・4・6 層）')
    tier = 'STANDARD' if reasons else 'ECONOMIC'
    w, h = facts['outline_mm']['width'], facts['outline_mm']['height']
    minimum = 70 if tier == 'STANDARD' else 10
    return {'tier': tier, 'reasons': reasons, 'reasons_ja': ja, 'single_board_minimum_mm': minimum,
            'single_board_fits': w >= minimum and h >= minimum,
            'edge_rails_and_fiducials_required': tier == 'STANDARD'}


def named_blockers(boards, lines, pages, ledger, root):
    """Each mismatch between the frozen boards and JLC's published rules, in English (report) and Japanese (page)."""
    out = []

    def add(bid, board, text, ja):
        out.append({'id': bid, 'board': board, 'text': text, 'ja': ja})

    add('order-gate-blocked', None, 'Readiness order gate is BLOCKED; this package is a dry run and must not be uploaded or ordered.',
        'readiness の発注ゲートが BLOCKED。この一式は予行で、アップロード・発注しない。')
    for b in boards:
        t, n = b['pcba_tier'], b['board']
        size = f"{fmt(b['outline_mm']['width'])} × {fmt(b['outline_mm']['height'])} mm"
        if t['tier'] == 'STANDARD':
            add(f'{n}-needs-standard-pcba', n, 'Needs Standard PCBA: ' + '; '.join(t['reasons']) + '. Standard PCBA requires edge rails and fiducials.',
                'Standard PCBA が必要（' + '、'.join(t['reasons_ja']) + '）。Standard PCBA は捨て基板（レール）とフィデューシャルが必須。')
        if not t['single_board_fits']:
            m = t['single_board_minimum_mm']
            add(f'{n}-below-pcba-minimum-size', n,
                f"Board is {size}; {t['tier'].title()} PCBA takes single boards from {m} × {m} mm. A panel is needed"
                + (' with edge rails' if t['tier'] == 'STANDARD' else '') + ' and no panel exists in the repository.',
                f"基板は {size}。{t['tier'].title()} PCBA の単品は {m} × {m} mm から。面付け" + ('（レール付き）' if t['tier'] == 'STANDARD' else '')
                + 'が必要で、リポジトリに面付けデータはない。JLC に面付けを頼むか、面付けデータを作るかの判断が要る。')
        if t['edge_rails_and_fiducials_required'] and not b['fiducials']:
            add(f'{n}-no-fiducials', n, 'No fiducials on the board; Standard PCBA needs fiducials. JLC panel guidance places 1 mm fiducials on 5 mm tooling edges, so a panel can carry them without changing the frozen board.',
                '基板にフィデューシャルがない。Standard PCBA には必須。JLC の面付け指針では 5 mm の捨て基板に 1 mm のフィデューシャルを置くので、凍結した基板を変えずに面付け側で用意できる。')
        if not b['copper_finish_in_board_file']:
            eco = t['tier'] == 'ECONOMIC'
            add(f'{n}-finish-not-specified', n, 'Surface finish is not recorded in the board file; it must be chosen on the order form'
                + (' (the Economic table lists HASL or ENIG for 1.6 mm green).' if eco else ' (Standard PCBA does not limit the finish).'),
                '表面処理が基板ファイルに記録されていない。注文画面で選ぶ' + ('（Economic の 1.6 mm 緑は HASL か ENIG）。' if eco else '（Standard PCBA は制限なし）。'))
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
    leaf = next((b for b in boards if b['board'] == 'led_leaf'), None)
    if leaf and leaf['thickness_mm'] != 1.6:
        th = fmt(leaf['thickness_mm'])
        add('leaf-thickness-not-1.6', 'led_leaf', f'The LED leaf board file is {th} mm FR-4 (A5 geometry), not 1.6 mm; its JLC tolerance is ±0.1 mm, not ±10%.',
            f'LED リーフの基板ファイルは {th} mm の FR-4（A5 の寸法）で 1.6 mm ではない。JLC の公差は ±10% ではなく ±0.1 mm。')
    add('pcb-fabrication-quantity-not-sourced', None,
        'The minimum bare-PCB quantity JLC fabricates per design was not read; the PCBA quantity (2 controller, 4 leaf, 2 adapter) is entered separately.',
        'JLC が 1 設計あたり製造する基板の最小枚数は未取得。PCBA の数量（コントローラー 2・リーフ 4・電源アダプタ 2）とは別に入力する。')
    if any(x['id'] == 'jack-switch-qualification' for x in ledger['blockers']):
        add('physical-jack-switch-qualification', 'controller',
            'PJ-324M terminal 4/5 function must be confirmed by continuity on a received part before any PCB order (procurement blocker jack-switch-qualification).',
            'PJ-324M の端子 4/5 の機能は、PCB を発注する前に入荷した実物の導通で確かめる（調達台帳の jack-switch-qualification）。')
    return out


# --- page --------------------------------------------------------------------------------------
BOARD_JA = {'controller': 'コントローラー', 'led_leaf': 'LED リーフ', 'power_adapter': '電源アダプタ'}
ROUTE_JA = {'JLC_STOCK': 'JLC 在庫', 'JLC_PREORDER': 'JLC 予約注文', 'JLC_PREORDER_OR_GLOBAL_SOURCING_BLOCKED': '在庫なし・予約不可（Global Sourcing か待つ）', 'EXCEPTION': '例外'}


def page(report):
    L = ['---', '# GENERATED by scripts/a7_jlc_package.py — do not edit; run `python3 scripts/a7_jlc_package.py`',
         'title: "JLCPCB 発注パッケージ（予行・未リリース）"',
         'description: "最初の 2 台分を JLCPCB に発注するとき、基板ごとに何を入力し何をアップロードするかの予行。製造リリースではありません。"',
         'sidebar_position: 4.6', '---', '', ':::danger[予行です。アップロード・発注しないでください]',
         f"発注ゲートは **{report['order_eligibility']}** です。このページと `engineering/a7/jlc-package/` のファイルは、JLC の注文画面に何が必要かを確かめる予行で、"
         'リリースされた製造データではありません。下の「止めている項目」がすべて解消し、製造リリースが承認されるまで使いません。', ':::', '',
         f"数量はオーナーの判断で **{report['modules']} 台**です。JLC の PCBA は 2 枚から受け付けます（2026-11-12 取得の JLC 公開能力表: Economic 2–50 枚、Standard 2–80000 枚）。", '',
         '## 止めている項目', '']
    for b in report['blockers']:
        L.append(f"- `{b['id']}`" + (f"（{BOARD_JA[b['board']]}）" if b['board'] else '') + ': ' + esc(b['ja']))
    for b in report['boards']:
        t = b['pcba_tier']
        L += ['', f"## {BOARD_JA[b['board']]}（`{b['board']}`）", '',
              f"PCB 注文画面に入れる値（基板ファイル `{b['pcb']}` から読んだもの）:", '',
              '| 項目 | 値 |', '|---|---|',
              f"| Base Material | FR-4 |",
              f"| Layers | {b['copper_layers']} |",
              f"| Dimensions | {fmt(b['outline_mm']['width'])} × {fmt(b['outline_mm']['height'])} mm |",
              f"| PCB Thickness | {fmt(b['thickness_mm'])} mm（JLC 公差 {b['thickness_tolerance']}） |",
              f"| Surface Finish | {b['copper_finish_in_board_file'] or '基板ファイルに指定なし（注文時に選ぶ）'} |",
              f"| 最小穴径 | {fmt(b['min_drill_mm'])} mm |" if b['min_drill_mm'] else '| 最小穴径 | — |',
              f"| PCB Assembly | オン。PCBA Qty {b['pcba_quantity']}（{b['per_module']} 枚/台 × {report['modules']} 台） |",
              f"| PCBA Type | {t['tier'].title()}" + (f"（理由: {esc('、'.join(t['reasons_ja']))}）" if t['reasons_ja'] else '') + ' |',
              f"| Assembly Side | {'Top と Bottom（両面）' if len(b['assembly_sides']) > 1 else b['assembly_sides'][0]} |",
              f"| 実装点 | SMD {b['smd_count']}・THT {len(b['tht_refs'])}" + (f"（{', '.join(b['tht_refs'])}）" if b['tht_refs'] else '') + ' |', '',
              'アップロードするもの:', '',
              f"1. Gerber と drill の zip: `python3 scripts/a7_jlc_package.py export --out <リポジトリ外の空ディレクトリ>` で作る `{b['board']}-gerbers-DRYRUN.zip`（Gerber 原点: {b['gerber_origin']}）",
              f"2. BOM: `engineering/a7/jlc-package/{b['board']}_BOM_DRYRUN.csv`（{b['bom_lines']} 行、列 Comment / Designator / Footprint / JLCPCB Part #）",
              f"3. CPL: `engineering/a7/jlc-package/{b['board']}_CPL_DRYRUN.csv`（{b['cpl_rows']} 行、列 Designator / Mid X / Mid Y / Rotation / Layer、mm）", '']
        if b['centroid_offsets']:
            L += ['JLC の配置プレビューで中心を確かめる部品（フットプリント原点がパッド中心から離れているもの）:', '',
                  '| Ref | LCSC | 原点からパッド中心まで |', '|---|---|---:|']
            L += [f"| {c['ref']} | {c['lcsc']} | {fmt(c['anchor_to_pad_centre_mm'])} mm |" for c in b['centroid_offsets']]
    L += ['', '## 部品の区分（2026-11-12 の JLC 部品ページ）', '',
          f"Basic {report['part_counts']['BASIC']} 種・Extended {report['part_counts']['EXTENDED']} 種。必要数は 2 台分です。在庫数は観測時点の値で、確保ではありません。", '',
          '| LCSC | 型番 | 区分 | 必要数 | JLC 在庫 | 予約可能数 | 経路 |', '|---|---|---|---:|---:|---:|---|']
    L += [f"| {l['lcsc']} | {esc(l['mpn'])} | {l['library'].title()} | {l['pieces_required']} | {l['in_stock']} | {l['preorder_available']} | {ROUTE_JA[l['route']]} |" for l in report['parts']]
    L += ['', '区分と在庫は `engineering/a7/jlc-package/sources.json` の日付付き記録です（項目の意味はこちらの解釈で、JLC の定義ではありません）。'
          'Extended 部品は JLC で追加料金がかかる区分です（金額は未取得）。', '']
    return '\n'.join(L) + '\n'


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
    targets[ROOT / PAGE] = page(report)
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
