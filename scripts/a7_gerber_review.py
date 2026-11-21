#!/usr/bin/env python3
"""Inspect actual Gerbers, or verify retained review identities using stdlib only.

Mask shapes are openings; inverse views show residual mask. Raster views are
inspection aids, never DRC results or optical measurements.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_receipt(path, root=ROOT):
    """Reject stale board, Gerber, renderer, tool lock or review artifact bytes."""
    receipt = json.loads(path.read_text())
    errors = []
    board = Path(receipt['board'])
    if board.is_absolute() or '..' in board.parts or not str(board).startswith('engineering/a7/electronics/'):
        errors.append('review must identify the current A7 board, never the A5 baseline')
    expected = [(root / board, receipt['board_sha256']),
                (root / 'scripts/a7_gerber_review.py', receipt['render_script_sha256']),
                (root / 'engineering/a7/verification/optical/tools/requirements.lock', receipt['tool_lock_sha256'])]
    gerbers = path.parent / 'gerbers'
    names = receipt['gerber_sha256']
    if any(Path(name).name != name or name.endswith('.gbrjob') for name in names):
        errors.append('review Gerber list contains a path or manufacturing job file')
    actual = {p.name for p in gerbers.iterdir() if p.is_file()}
    if actual != set(names):
        errors.append('retained Gerber files differ from the receipt inventory')
    expected.extend((gerbers / name, digest) for name, digest in names.items())
    expected.extend((path.parent / name, digest)
                    for name, digest in receipt.get('review_artifact_sha256', {}).items())
    for source, digest in expected:
        if not source.is_file() or sha256(source) != digest:
            errors.append(f'identity mismatch: {source}')
    review = json.loads((path.parent / 'review.json').read_text())
    if {layer['file']: layer['sha256'] for layer in review['layers']} != names:
        errors.append('parsed Gerber review is not bound to the retained Gerbers')
    raster = json.loads((path.parent / 'raster-inspection.json').read_text())
    if raster['board_sha256'] != receipt['board_sha256']:
        errors.append('raster inspection belongs to another board')
    if errors:
        raise ValueError('\n'.join(errors))
    return len(expected)


def render(args):
    from gerbonara import GerberFile

    args.output.mkdir(parents=True, exist_ok=True)
    bounds = (tuple(args.bounds[:2]), tuple(args.bounds[2:]))
    report = {'bounds_mm': bounds, 'gerbonara_version': '1.6.3', 'notes': [
        'Black = copper/paste or mask OPENING on normal views.',
        'Mask residual views invert openings within rectangular board bounds.',
        'Ordered dark/clear aperture primitives retained; SVG rasterization is visual evidence, not exact area proof.'
    ], 'layers': []}
    for source in sorted(args.input.iterdir()):
        # KiCad export suffixes: outer/inner copper, mask, paste, silkscreen (markings) and outline.
        if source.suffix not in {'.gbr', '.gtl', '.gbl', '.g1', '.g2', '.g3', '.g4', '.gts', '.gbs',
                                 '.gtp', '.gbp', '.gto', '.gbo', '.gm1'}:
            continue
        gerber = GerberFile.open(source)
        mask = gerber.file_attrs.get('.FileFunction', ('',))[0] == 'Soldermask'
        item = {'file': source.name, 'sha256': sha256(source),
                'attrs': gerber.file_attrs, 'objects': len(gerber.objects),
                'dark_objects': sum(o.polarity_dark for o in gerber.objects),
                'clear_objects': sum(not o.polarity_dark for o in gerber.objects),
                'types': dict(collections.Counter(type(o).__name__ for o in gerber.objects))}
        for residual in ([False, True] if mask else [False]):
            name = source.name + ('.residual-mask' if residual else '.shapes')
            svg, png = args.output / (name + '.svg'), args.output / (name + '.png')
            background, foreground = ('black', 'white') if residual else ('white', 'black')
            svg.write_text(str(gerber.to_svg(force_bounds=bounds, fg=foreground, bg=background)))
            if args.render:
                subprocess.run(['inkscape', str(svg), '--export-type=png',
                                '--export-filename=' + str(png), '--export-width=360',
                                '--export-background=' + background, '--export-background-opacity=1'],
                               check=True, timeout=30, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        report['layers'].append(item)
    (args.output / 'review.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, nargs='?')
    parser.add_argument('output', type=Path, nargs='?')
    parser.add_argument('--bounds', type=float, nargs=4)
    parser.add_argument('--render', action='store_true')
    parser.add_argument('--verify-receipt', type=Path)
    args = parser.parse_args()
    if args.verify_receipt:
        count = verify_receipt(args.verify_receipt)
        print(f'PASS: {count} retained identities verified; review only, not manufacturing release')
    else:
        if args.input is None or args.output is None or args.bounds is None:
            parser.error('rendering requires input, output and --bounds')
        render(args)


if __name__ == '__main__':
    main()
