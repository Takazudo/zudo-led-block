#!/usr/bin/env python3
"""A6 controller revision tooling: derived files, manifest and initial-board staging.

File ownership (also recorded in engineering/a6/manifest.json):
  authoritative  engineering/a6/electronics/controller/controller.kicad_pcb
                 Routed board. Placement and copper come only from here. No command in
                 this script writes it; `generate` hashes it before and after and fails
                 if it changed.
  derived        controller.kicad_sch (A5 schematic, title block only), LightBlock.kicad_sym,
                 sym-lib-table, controller.kicad_pro (A5 rules, byte copies), fp-lib-table,
                 engineering/a6/electronics/placement_and_connectivity.json (exported from the
                 routed board's native facts), engineering/a6/manifest.json.
  inherited      A5 files listed in the manifest by path + SHA-256 (never copied or edited).

Commands:
  generate [--check] [--facts F --geometry G]
      Rewrite (or with --check, compare) every derived file. The placement export
      needs native board facts from scripts/a6_native_inner.py; without them the
      committed export is only hash-checked through the manifest.
  init-board --out DIR
      Recreate the initial unrouted A5-generated board in an EMPTY directory outside
      the repository (runs a temporary copy of the A5 generator; needs pcbnew). It
      can never target engineering/a6.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
A5E = REPO / 'engineering/a5/electronics'
A5C = A5E / 'native/controller'
A6 = REPO / 'engineering/a6'
A6C = A6 / 'electronics/controller'
BOARD = A6C / 'controller.kicad_pcb'
EXPORT = A6 / 'electronics/placement_and_connectivity.json'
MANIFEST = A6 / 'manifest.json'
IMAGE = 'kicad/kicad:10.0.8@sha256:3f4a01786dfbe803a65f345c3342b765db9add913f5e9448f8356793714ddc34'

A5_TITLE = ('(title_block (title "Light Block A5 controller") (date "2026-11-06") (rev "A5") (company "Light Block") '
            '(comment 1 "Engineering draft. Controller is not routed. No hardware qualification claimed."))')
A6_TITLE = ('(title_block (title "Light Block A6 controller") (date "2026-11-07") (rev "A6") (company "Light Block") '
            '(comment 1 "Engineering draft. A6 routed candidate; not released for manufacture. No hardware qualification claimed."))')
FP_LIB = ('(fp_lib_table (version 7) (lib (name "LightBlock") (type "KiCad") '
          '(uri "${KIPRJMOD}/../../../a5/electronics/footprints/LightBlock.pretty") (options "") '
          '(descr "A5 exact part footprints, inherited unchanged")))\n')

# Inherited A5 inputs the A6 gate stages or reads. Each is pinned by SHA-256 in the manifest.
INHERITED_STAGED = [
    'engineering/a5/electronics/native/controller/controller.kicad_sch',
    'engineering/a5/electronics/native/controller/controller.kicad_pcb',
    'engineering/a5/electronics/native/controller/controller.kicad_pro',
    'engineering/a5/electronics/native/controller/LightBlock.kicad_sym',
    'engineering/a5/electronics/native/controller/fp-lib-table',
    'engineering/a5/electronics/native/controller/sym-lib-table',
    'engineering/a5/electronics/native/led_leaf/led_leaf.kicad_sch',
    'engineering/a5/electronics/native/led_leaf/led_leaf.kicad_pcb',
    'engineering/a5/electronics/native/led_leaf/led_leaf.kicad_pro',
    'engineering/a5/electronics/native/led_leaf/LightBlock.kicad_sym',
    'engineering/a5/electronics/native/led_leaf/fp-lib-table',
    'engineering/a5/electronics/native/led_leaf/sym-lib-table',
    'engineering/a5/electronics/native/power_adapter/power_adapter.kicad_sch',
    'engineering/a5/electronics/native/power_adapter/power_adapter.kicad_pcb',
    'engineering/a5/electronics/native/power_adapter/power_adapter.kicad_pro',
    'engineering/a5/electronics/native/power_adapter/LightBlock.kicad_sym',
    'engineering/a5/electronics/native/power_adapter/fp-lib-table',
    'engineering/a5/electronics/native/power_adapter/sym-lib-table',
]
INHERITED_READ = [
    'engineering/a5/electronics/placement_and_connectivity.json',
    'engineering/a5/electronics/design/design_data.py',
    'engineering/a5/electronics/design/generate_electronics.py',
    'engineering/a5/integration/check_schematic_interfaces.py',
    'engineering/a5/procurement_rows.json',
    'engineering/a5/mechanical/build_mechanical.py',
    'engineering/a5/mechanical/geometry.json',
    'engineering/a5/integration/independent_review/review.md',
]
A6_OWNED = [
    ('engineering/a6/electronics/controller/controller.kicad_pcb', 'authoritative', True),
    ('engineering/a6/electronics/controller/controller.kicad_sch', 'derived', True),
    ('engineering/a6/electronics/controller/controller.kicad_pro', 'derived', True),
    ('engineering/a6/electronics/controller/LightBlock.kicad_sym', 'derived', True),
    ('engineering/a6/electronics/controller/fp-lib-table', 'derived', True),
    ('engineering/a6/electronics/controller/sym-lib-table', 'derived', True),
    ('engineering/a6/electronics/placement_and_connectivity.json', 'derived', False),
    ('engineering/a6/electronics/routing_constraints.json', 'authored', False),
    ('engineering/a6/verification/native_expectations.json', 'authored', False),
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def derived_texts() -> dict[Path, bytes]:
    sch = (A5C / 'controller.kicad_sch').read_text()
    if sch.count(A5_TITLE) != 1:
        raise SystemExit('A5 schematic title block not found exactly once; refusing to derive')
    return {
        A6C / 'controller.kicad_sch': sch.replace(A5_TITLE, A6_TITLE).encode(),
        A6C / 'controller.kicad_pro': (A5C / 'controller.kicad_pro').read_bytes(),
        A6C / 'LightBlock.kicad_sym': (A5C / 'LightBlock.kicad_sym').read_bytes(),
        A6C / 'sym-lib-table': (A5C / 'sym-lib-table').read_bytes(),
        A6C / 'fp-lib-table': FP_LIB.encode(),
    }


def export_placement(facts: dict, geom: dict) -> bytes:
    a5 = json.loads((A5E / 'placement_and_connectivity.json').read_text())
    fps = {f['ref']: f for f in geom['footprints']}
    out = {'revision': 'A6', 'generator': 'scripts/a6_controller.py generate (from routed controller.kicad_pcb)',
           'kicad_version': '10.0.8', 'controller_board_sha256': sha(BOARD),
           'status': 'Engineering draft; controller routed (A6 candidate); no hardware tested; not released for manufacture',
           'boards': [], 'coordinate_note': a5['coordinate_note'],
           'inherited_from': 'engineering/a5/electronics/placement_and_connectivity.json (led_leaf and power_adapter unchanged)'}
    for b in a5['boards']:
        if b['name'] != 'controller':
            out['boards'].append(b); continue
        nb = dict(b)
        nb['title'] = 'Light Block A6 controller'
        nb['route_status'] = 'routed_4_layer'
        nb['track_count'] = facts['track_count']; nb['via_count'] = facts['via_count']
        comps = []
        for c in b['components']:
            f = fps[c['ref']]
            nc = dict(c)
            nc['at'] = [f['x'], f['y']]; nc['side'] = f['side']; nc['angle'] = f['rot']
            pads = {pd[0]: [pd[2], pd[3]] for pd in f['pads'] if pd[0]}
            if 'pad_centers_mm' in c:
                if set(pads) != set(c['pad_centers_mm']):
                    raise SystemExit(f"{c['ref']}: pad set differs from A5 export")
                nc['pad_centers_mm'] = {k: pads[k] for k in c['pad_centers_mm']}
            nets = {pd[0]: (None if not pd[1] or pd[1].startswith('unconnected-(') else pd[1][1:] if pd[1].startswith('/') else pd[1])
                    for pd in f['pads'] if pd[0]}
            if any(nets.get(k) != v for k, v in c['nets'].items()):
                raise SystemExit(f"{c['ref']}: pad nets differ from A5 connectivity")
            comps.append(nc)
        extra = set(fps) - {c['ref'] for c in b['components']}
        if extra != set(facts.get('board_only', [])):
            raise SystemExit(f'unexpected board footprints {sorted(extra)}')
        nb['components'] = comps
        out['boards'].append(nb)
    return (json.dumps(out, indent=2, ensure_ascii=False) + '\n').encode()


def manifest_bytes(texts: dict[Path, bytes]) -> bytes:
    def h(rel: str) -> str:
        p = REPO / rel
        return hashlib.sha256(texts[p]).hexdigest() if p in texts else sha(p)
    files = []
    for rel in INHERITED_STAGED:
        files.append({'path': rel, 'sha256': h(rel), 'ownership': 'inherited_a5', 'stage': True})
    for p in sorted((A5E / 'footprints/LightBlock.pretty').iterdir()):
        if p.is_file() and not p.is_symlink() and p.suffix == '.kicad_mod':
            rel = str(p.relative_to(REPO))
            files.append({'path': rel, 'sha256': sha(p), 'ownership': 'inherited_a5', 'stage': True})
    for rel in INHERITED_READ:
        files.append({'path': rel, 'sha256': h(rel), 'ownership': 'inherited_a5', 'stage': False})
    for rel, own, st in A6_OWNED:
        files.append({'path': rel, 'sha256': h(rel), 'ownership': own, 'stage': st})
    m = {
        'revision': 'A6',
        'schema': 1,
        'note': 'Generated by scripts/a6_controller.py generate. Do not edit by hand.',
        'image': IMAGE,
        'kicad_version': '10.0.8',
        'authoritative_board': 'engineering/a6/electronics/controller/controller.kicad_pcb',
        'designs': {
            'controller': {'dir': 'engineering/a6/electronics/controller', 'schematic': 'controller.kicad_sch',
                           'board': 'controller.kicad_pcb', 'status': 'A6 routed candidate'},
            'led_leaf': {'dir': 'engineering/a5/electronics/native/led_leaf', 'schematic': 'led_leaf.kicad_sch',
                         'board': 'led_leaf.kicad_pcb', 'status': 'frozen A5, freshly checked'},
            'power_adapter': {'dir': 'engineering/a5/electronics/native/power_adapter', 'schematic': 'power_adapter.kicad_sch',
                              'board': 'power_adapter.kicad_pcb', 'status': 'frozen A5, freshly checked'},
        },
        'interface_check': {'script': 'engineering/a5/integration/check_schematic_interfaces.py',
                            'designs': ['controller', 'led_leaf', 'power_adapter'], 'min_checks': 20},
        'files': files,
    }
    return (json.dumps(m, indent=1) + '\n').encode()


def write_or_check(path: Path, data: bytes, check: bool, drift: list[str]) -> None:
    if path == BOARD:
        raise SystemExit('refusing to write the authoritative routed board')
    if check:
        if not path.is_file() or path.read_bytes() != data:
            drift.append(str(path.relative_to(REPO)))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file() or path.read_bytes() != data:
        path.write_bytes(data)
        print(f'wrote {path.relative_to(REPO)}')


def cmd_generate(a: argparse.Namespace) -> int:
    if not BOARD.is_file():
        print('authoritative board missing', file=sys.stderr); return 1
    before = sha(BOARD)
    drift: list[str] = []
    texts = derived_texts()
    if a.facts:
        facts = json.loads(Path(a.facts).read_text()); geom = json.loads(Path(a.geometry).read_text())
        if facts.get('geometry_sha256') != hashlib.sha256(json.dumps(geom, sort_keys=True).encode()).hexdigest():
            print('facts/geometry pair inconsistent', file=sys.stderr); return 1
        texts[EXPORT] = export_placement(facts, geom)
    for p, data in texts.items():
        write_or_check(p, data, a.check, drift)
    write_or_check(MANIFEST, manifest_bytes(texts), a.check, drift)
    if sha(BOARD) != before:
        print('authoritative board changed during generation', file=sys.stderr); return 1
    if drift:
        print('stale derived files: ' + ', '.join(drift), file=sys.stderr); return 1
    print(json.dumps({'board_sha256': before, 'checked' if a.check else 'generated': len(texts) + 1,
                      'placement_export': 'from facts' if a.facts else 'hash-checked only'}))
    return 0


def cmd_init_board(a: argparse.Namespace) -> int:
    out = Path(a.out).resolve()
    if out == REPO or REPO in out.parents:
        print('refusing: initial-board output must be outside the repository', file=sys.stderr); return 2
    if out.exists() and any(out.iterdir()):
        print('refusing: output directory must be empty', file=sys.stderr); return 2
    out.mkdir(parents=True, exist_ok=True)
    shutil.copytree(A5E, out / 'electronics', symlinks=True)
    try:
        import pcbnew  # noqa: F401
    except ImportError:
        print(f'copied A5 electronics to {out}; run inside {IMAGE}:\n'
              f'  python3 {out}/electronics/design/generate_electronics.py')
        return 0
    return subprocess.run([sys.executable, str(out / 'electronics/design/generate_electronics.py')], cwd=out).returncode


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    g = sp.add_parser('generate'); g.add_argument('--check', action='store_true')
    g.add_argument('--facts'); g.add_argument('--geometry')
    i = sp.add_parser('init-board'); i.add_argument('--out', required=True)
    a = ap.parse_args()
    if a.cmd == 'generate':
        if bool(a.facts) != bool(a.geometry):
            ap.error('--facts and --geometry go together')
        return cmd_generate(a)
    return cmd_init_board(a)


if __name__ == '__main__':
    sys.exit(main())
