#!/usr/bin/env python3
"""Source-ownership guards and derived exports for native-gate profiles.

Ownership is declared in engineering/a7/verification/source_authority.json (A7) and
in each fixture's provenance (infrastructure). Rules enforced here:

  * No derived write may target a path classed "authoritative" or "inherited".
    Normal generation therefore cannot overwrite routed copper or the A5 checkpoint.
  * The placement/connectivity export is derived only from fresh native board facts
    (scripts/native_gate/inner.py) of the authoritative board, and records that
    board's SHA-256; --check compares instead of writing.
  * Initial-board generation writes only into an EMPTY directory outside the
    repository. It can never target engineering/.

Commands:
  export-placement --board B --facts F --geometry G --out O [--check]
  init-board --out DIR [--from engineering/a5/electronics]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AUTHORITY = REPO / 'engineering/a7/verification/source_authority.json'
PROTECTED_CLASSES = {'authoritative', 'inherited'}


class Refused(Exception):
    pass


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def protected_paths(authority: Path = AUTHORITY) -> dict[str, str]:
    a = json.loads(authority.read_text())
    out = {}
    for e in a['entries']:
        if e['class'] in PROTECTED_CLASSES:
            out[e['path'].rstrip('/')] = e['class']
    return out


def check_writable(target: Path, extra_protected: list[Path] = (), authority: Path = AUTHORITY) -> None:
    t = target.resolve()
    for q in extra_protected:
        if t == q.resolve():
            raise Refused(f'refusing to write protected file {q}')
    try:
        rel = t.relative_to(REPO)
    except ValueError:
        return
    if rel.parts[:2] == ('engineering', 'a5'):
        raise Refused('refusing to write inside the immutable A5 checkpoint')
    for path, cls in protected_paths(authority).items():
        if str(rel) == path or str(rel).startswith(path + '/'):
            raise Refused(f'refusing to write {rel}: classed {cls} in {authority.relative_to(REPO)}')


def placement(board: Path, facts: dict, geom: dict) -> bytes:
    if facts.get('geometry_sha256') != hashlib.sha256(json.dumps(geom, sort_keys=True).encode()).hexdigest():
        raise Refused('facts/geometry pair inconsistent')
    if 'error' in facts:
        raise Refused(f"board facts carry an error: {facts['error']}")
    comps = []
    for f in geom['footprints']:
        comps.append({'ref': f['ref'], 'fpid': f['fpid'], 'at_mm': [f['x'], f['y']], 'angle_deg': f['rot'], 'side': f['side'],
                      'board_only': f['board_only'],
                      'pads': {pd[0]: {'at_mm': [pd[2], pd[3]], 'net': pd[1]} for pd in f['pads'] if pd[0]}})
    out = {'generator': 'scripts/native_gate/authority.py export-placement (from fresh native board facts)',
           'board': str(board.resolve().relative_to(REPO)) if board.resolve().is_relative_to(REPO) else str(board),
           'board_sha256': sha(board), 'geometry_sha256': facts['geometry_sha256'],
           'zone_fill_sha256': facts.get('zone_fill_sha256'), 'unconnected_pcbnew': facts.get('unconnected_pcbnew'),
           'copper_layers': geom['copper_layers'], 'thickness_mm': geom['thickness_mm'], 'edges_mm': geom['edges'],
           'track_count': facts.get('track_count'), 'via_count': facts.get('via_count'), 'zone_count': facts.get('zone_count'),
           'components': comps}
    return (json.dumps(out, indent=1, sort_keys=True) + '\n').encode()


def cmd_export(a: argparse.Namespace) -> int:
    board, outp = Path(a.board), Path(a.out)
    before = sha(board)
    data = placement(board, json.loads(Path(a.facts).read_text()), json.loads(Path(a.geometry).read_text()))
    if a.check:
        if not outp.is_file() or outp.read_bytes() != data:
            print(f'stale derived export {outp}', file=sys.stderr); return 1
    else:
        check_writable(outp, [board])
        outp.write_bytes(data)
        print(f'wrote {outp}')
    if sha(board) != before:
        print('authoritative board changed during export', file=sys.stderr); return 1
    print(json.dumps({'board_sha256': before, 'export': str(outp), 'mode': 'check' if a.check else 'write'}))
    return 0


def require_empty_staging(out: Path) -> Path:
    o = out.resolve()
    if o == REPO or REPO in o.parents:
        raise Refused('initial-board output must be outside the repository')
    if o.exists() and (not o.is_dir() or any(o.iterdir())):
        raise Refused('initial-board output directory must be empty')
    return o


def cmd_init_board(a: argparse.Namespace) -> int:
    out = require_empty_staging(Path(a.out))
    src = (REPO / a.source).resolve()
    out.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, out / 'electronics', symlinks=True)
    gen = out / 'electronics/design/generate_electronics.py'
    try:
        import pcbnew  # noqa: F401
    except ImportError:
        print(f'copied {a.source} to {out}; run the generator inside the pinned KiCad image:\n  python3 {gen}')
        return 0
    return subprocess.run([sys.executable, str(gen)], cwd=out).returncode


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    e = sp.add_parser('export-placement')
    for k in ('--board', '--facts', '--geometry', '--out'):
        e.add_argument(k, required=True)
    e.add_argument('--check', action='store_true')
    i = sp.add_parser('init-board'); i.add_argument('--out', required=True)
    i.add_argument('--from', dest='source', default='engineering/a5/electronics')
    a = ap.parse_args()
    try:
        return cmd_export(a) if a.cmd == 'export-placement' else cmd_init_board(a)
    except Refused as r:
        print(f'refused: {r}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
