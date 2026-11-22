#!/usr/bin/env python3
"""Assemble or verify a dated A7 review set (REVIEW_ONLY / NOT FOR ORDER).

assemble copies the panel Gerber zips from a passing `a7_panel.py build --out` directory and the committed
panel BOM / CPL, records the export/build summaries, the frozen identity set (readiness IDENTITY_PATHS),
optional comparison and review-image files, and writes SHA256SUMS. It refuses a failing build, a target
that already exists, and boards that differ from the committed panel layouts.

verify checks a recorded set: SHA256SUMS, the expected file set per board, and that identities.json names the
panel layouts' board hashes. Whether the set is current is decided by package-sets.json in a7_jlc_package.py.
"""
import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
PKG = Path('engineering/a7/jlc-package')
BOARDS = ('controller', 'led_leaf', 'power_adapter')
LABEL = 'REVIEW_ONLY_NOT_FOR_ORDER'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def readiness_identities(root):
    spec = importlib.util.spec_from_file_location('a7_readiness', ROOT / 'scripts/a7_readiness.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.identities(root)


def board_files(board):
    return [f'{board}/{board}-panel-gerbers-DRYRUN.zip', f'{board}/{board}-panel_BOM_DRYRUN.csv', f'{board}/{board}-panel_CPL_DRYRUN.csv']


def layouts(root):
    return {b: json.loads((root / PKG / 'panels' / f'{b}-panel.json').read_text()) for b in BOARDS}


def assemble(args, root=ROOT):
    out = (root / args.out).resolve() if not args.out.is_absolute() else args.out.resolve()
    if out.exists():
        raise SystemExit(f'refusing: {out} exists (a recorded set is immutable)')
    build = json.loads((args.panels / 'summary.json').read_text())
    single = json.loads((args.export / 'summary.json').read_text())
    if build.get('status') != 'PASS' or single.get('status') != 'PASS':
        raise SystemExit('refusing: the panel build or single-board export did not PASS')
    lay = layouts(root)
    for b, l in lay.items():
        if sha(root / l['pcb']) != l['pcb_sha256']:
            raise SystemExit(f'refusing: {b} board differs from its committed panel layout')
    out.mkdir(parents=True)
    for b in BOARDS:
        (out / b).mkdir()
        shutil.copyfile(args.panels / f'{b}-panel-gerbers-DRYRUN.zip', out / b / f'{b}-panel-gerbers-DRYRUN.zip')
        for kind in ('BOM', 'CPL'):
            shutil.copyfile(root / PKG / 'panels' / f'{b}-panel_{kind}_DRYRUN.csv', out / b / f'{b}-panel_{kind}_DRYRUN.csv')
    (out / 'panel-build-summary.json').write_text(json.dumps(build, indent=2) + '\n')
    (out / 'single-board-export-summary.json').write_text(json.dumps(single, indent=2) + '\n')
    ident = {'label': LABEL, 'frozen_from_commit': args.commit, 'tool_image': build['image'],
             'panel_layouts': {b: {'path': str(PKG / 'panels' / f'{b}-panel.json'), 'sha256': sha(root / PKG / 'panels' / f'{b}-panel.json'),
                                   'board': l['pcb'], 'board_sha256': l['pcb_sha256'], 'copies_per_sheet': len(l['copies'])}
                               for b, l in lay.items()},
             'identities': readiness_identities(root)}
    (out / 'identities.json').write_text(json.dumps(ident, indent=2) + '\n')
    for extra in args.extra or []:
        src, dest = extra.split('=', 1)
        (out / dest).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, out / dest)
    files = sorted(str(p.relative_to(out)) for p in out.rglob('*') if p.is_file() and p.name not in ('SHA256SUMS', 'README.md'))
    (out / 'SHA256SUMS').write_text(''.join(f'{sha(out / f)}  {f}\n' for f in files))
    print(f'WROTE {out} ({len(files)} files)')
    return 0


def verify(path, root=ROOT):
    d = root / path
    errors = []
    sums = {line.split(maxsplit=1)[1]: line.split(maxsplit=1)[0] for line in (d / 'SHA256SUMS').read_text().splitlines()}
    for name, digest in sums.items():
        if not (d / name).is_file() or sha(d / name) != digest:
            errors.append(f'{name}: missing or differs from SHA256SUMS')
    for b in BOARDS:
        errors += [f'{f}: not recorded' for f in board_files(b) if f not in sums]
    ident = json.loads((d / 'identities.json').read_text())
    if ident.get('label') != LABEL:
        errors.append('identities.json label must be ' + LABEL)
    build = json.loads((d / 'panel-build-summary.json').read_text())
    if build.get('status') != 'PASS' or any(build['boards'][b].get('cpl_vs_kicad') != 'MATCH' for b in BOARDS):
        errors.append('panel build summary is not a PASS with native CPL correspondence')
    lay = ident['panel_layouts']
    if ident['identities']['board']['sha256'] != lay['controller']['board_sha256'] or \
            ident['identities']['led_leaf_board']['sha256'] != lay['led_leaf']['board_sha256']:
        errors.append('frozen identities and panel layouts name different boards')
    return errors


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('assemble')
    a.add_argument('--panels', type=Path, required=True)
    a.add_argument('--export', type=Path, required=True)
    a.add_argument('--out', type=Path, required=True)
    a.add_argument('--commit', required=True)
    a.add_argument('--extra', action='append', help='SRC=DEST inside the set (comparison records, review images)')
    v = sub.add_parser('verify')
    v.add_argument('path', nargs='?', help='default: the current set named in package-sets.json')
    args = ap.parse_args()
    if args.cmd == 'assemble':
        return assemble(args)
    if args.path is None:
        args.path = json.loads((ROOT / PKG / 'package-sets.json').read_text())['current']
        if args.path is None:
            print('SKIP: package-sets.json names no current set')
            return 0
    errors = verify(args.path)
    print('\n'.join(errors) or f'PASS: {args.path} ({LABEL})')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
