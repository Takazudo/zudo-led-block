#!/usr/bin/env python3
"""Consume fixture-specific native geometry of the authoritative A7 controller board.

Source: the `fixture_geometry.json` member that the pinned KiCad 10.0.8 gate writes for
`a7_controller` and CI retains in `native-infrastructure-evidence`. `--from-zip` accepts it
only from an artifact that scripts/a7_native_artifact.py classifies VALID_PASS for the
expected revision and run, checks it, and writes the versioned record
engineering/a7/fixture/native-geometry.json. `--check` re-validates that record offline
against the current PCB bytes and the canonical placement export.

Conventions (from the extractor): KiCad absolute board coordinates in mm, +X right, +Y down,
rotation in degrees counter-clockwise as displayed by KiCad, back-side items reported in
board coordinates as seen from the front. The consumer proves the transform pad = footprint
origin + R(rotation) * fp_relative for every pad and the face/layer agreement, so a wrong face
or mirrored transform fails.

Courtyard and footprint boxes are CAD extents; they are not body height, solder envelope,
manufacturing tolerance or measured fit. Absent geometry stays null and is listed as unknown.
Passing this check does not complete the fixture or any physical gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import a7_native_artifact as art  # noqa: E402

SCHEMA = 'zudo-led-block/a7-fixture-geometry/1'
RECORD_SCHEMA = 'zudo-led-block/a7-fixture-native-geometry-record/1'
BOARD = ROOT / 'engineering/a7/electronics/controller/controller.kicad_pcb'
PLACEMENT = BOARD.with_name('board_placement.json')
RECORD = ROOT / 'engineering/a7/fixture/native-geometry.json'
MEMBER = 'evidence/a7_controller/fixture_geometry.json'
TOL_MM = 2e-4
PAD_FIELDS = ('number', 'net', 'at_mm', 'fp_relative_mm', 'shape', 'size_mm', 'rotation_deg', 'layers', 'attribute')
CU = {'F': 'F.Cu', 'B': 'B.Cu'}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def rotate(v, deg):
    """KiCad RotatePoint convention (Y down, positive = counter-clockwise on screen)."""
    a = math.radians(deg)
    x, y = v
    return [x * math.cos(a) + y * math.sin(a), -x * math.sin(a) + y * math.cos(a)]


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _pt(v) -> bool:
    return isinstance(v, list) and len(v) == 2 and all(_num(c) for c in v)


def check_geometry(fx: dict, board_sha: str, placement: dict) -> tuple[list[str], list[str]]:
    """Return (errors, unknowns). Errors mean wrong, stale or incomplete evidence."""
    errors: list[str] = []
    unknowns: list[str] = []
    if not isinstance(fx, dict) or fx.get('schema') != SCHEMA:
        return ['fixture geometry schema missing or wrong'], unknowns
    if 'error' in fx:
        return [f"extractor error: {fx['error']}"], unknowns
    if fx.get('board_sha256') != board_sha:
        errors.append('fixture geometry board_sha256 differs from the authoritative A7 PCB')
    if placement.get('board_sha256') != board_sha:
        errors.append('canonical placement is stale for the authoritative A7 PCB')
    if fx.get('units') != 'mm' or fx.get('axes') != {'x': 'right', 'y': 'down'}:
        errors.append('unexpected units/axes convention')
    if fx.get('extraction_errors') != []:
        errors.append(f"extraction errors recorded: {str(fx.get('extraction_errors'))[:300]}")
    fps = fx.get('footprints')
    if not isinstance(fps, list):
        return errors + ['footprints missing'], unknowns
    by_ref = {}
    for f in fps:
        if not isinstance(f, dict) or not isinstance(f.get('ref'), str) or f['ref'] in by_ref:
            errors.append('footprint entry malformed or duplicated')
            continue
        by_ref[f['ref']] = f
    canon = {c['ref']: c for c in placement.get('components', [])}
    if set(by_ref) != set(canon):
        errors.append(f'footprint set differs from canonical placement: missing {sorted(set(canon) - set(by_ref))[:5]} '
                      f'extra {sorted(set(by_ref) - set(canon))[:5]}')
    for ref in sorted(set(by_ref) & set(canon)):
        f, c = by_ref[ref], canon[ref]
        if f.get('side') not in CU or f.get('side') != c['side']:
            errors.append(f'{ref}: side differs from canonical placement')
            continue
        if not _pt(f.get('at_mm')) or not _num(f.get('rotation_deg')):
            errors.append(f'{ref}: origin/rotation missing')
            continue
        if math.dist(f['at_mm'], c['at_mm']) > TOL_MM or abs(((f['rotation_deg'] - c['angle_deg']) + 180) % 360 - 180) > 1e-3:
            errors.append(f'{ref}: origin/rotation differs from canonical placement')
        pads = f.get('pads')
        if not isinstance(pads, list) or not pads:
            errors.append(f'{ref}: pads missing')
            continue
        seen = {}
        for pd in pads:
            if not isinstance(pd, dict) or any(k not in pd for k in PAD_FIELDS):
                errors.append(f'{ref}: pad record missing required fields')
                continue
            tag = f"{ref}.{pd['number']}"
            if not _pt(pd['at_mm']) or not _pt(pd['fp_relative_mm']) or not _num(pd['rotation_deg']):
                errors.append(f'{tag}: position/rotation missing')
                continue
            if not isinstance(pd['shape'], str) or pd['shape'].startswith('UNKNOWN') or not _pt(pd['size_mm']) \
                    or min(pd['size_mm']) <= 0:
                errors.append(f'{tag}: pad shape/size missing')
            layers = pd['layers']
            if not isinstance(layers, list) or not layers:
                errors.append(f'{tag}: pad layers missing')
                continue
            want = [a + b for a, b in zip(f['at_mm'], rotate(pd['fp_relative_mm'], f['rotation_deg']))]
            if math.dist(want, pd['at_mm']) > TOL_MM:
                errors.append(f'{tag}: pad position is not origin + R(rotation) * fp_relative (transform/mirroring error)')
            if pd['attribute'] == 'SMD' and CU[f['side']] not in layers:
                errors.append(f'{tag}: SMD pad copper is not on the footprint face ({f["side"]})')
            if pd['number']:
                seen.setdefault(pd['number'], []).append(pd)
        for num, cp in (c.get('pads') or {}).items():
            cands = seen.get(num, [])
            if not any(math.dist(p['at_mm'], cp['at_mm']) <= TOL_MM and p['net'] == cp['net'] for p in cands):
                errors.append(f'{ref}.{num}: pad position/net differs from canonical placement')
        if set(seen) != set(c.get('pads') or {}):
            errors.append(f'{ref}: numbered pad set differs from canonical placement')
        crt = f.get('courtyard_bbox_mm')
        if not isinstance(crt, dict) or crt.get(f['side']) is None:
            unknowns.append(f'{ref}: courtyard on its face not available')
        if f.get('footprint_bbox_mm') is None:
            unknowns.append(f'{ref}: footprint extents not available')
        if f.get('body_height_mm') is not None:
            errors.append(f'{ref}: body height must not be asserted from CAD extraction')
    return errors, unknowns


def from_zip(zip_path: Path, expect_revision: str, expect_run_id: str, expect_run_attempt: str | None) -> dict:
    board_sha = sha(BOARD.read_bytes())
    image = json.loads((ROOT / art.PROFILE).read_text())['image']
    members = art.read_members(zip_path)
    cls = art.classify(members, board_sha=board_sha, image=image, expect_revision=expect_revision,
                       expect_run_id=expect_run_id, expect_run_attempt=expect_run_attempt)
    if cls['status'] != 'VALID_PASS':
        raise ValueError(f"artifact is {cls['status']}: {cls.get('rejected') or cls.get('reasons')}")
    if MEMBER not in members:
        raise ValueError(f'artifact lacks a7-gate/{MEMBER}')
    fx = json.loads(members[MEMBER])
    placement = json.loads(PLACEMENT.read_text())
    errors, unknowns = check_geometry(fx, board_sha, placement)
    if errors:
        raise ValueError('fixture geometry rejected: ' + '; '.join(errors[:10]))
    return {'schema': RECORD_SCHEMA, 'status': 'NATIVE_GEOMETRY_VALIDATED', 'board_sha256': board_sha,
            'placement_sha256': sha(PLACEMENT.read_bytes()),
            'provenance': {'artifact_zip_sha256': sha(zip_path.read_bytes()), 'identity': cls['identity'],
                           'members_sha256': cls['members_sha256'], 'image': image},
            'unknowns': unknowns,
            'scope': 'Native CAD pad/footprint geometry for fixture design only. Not body height, solder envelope, '
                     'tolerance, measured fit, a completed fixture or a manufacturing approval.',
            'geometry': fx}


def check_record(rec: dict) -> list[str]:
    board_sha = sha(BOARD.read_bytes())
    placement_bytes = PLACEMENT.read_bytes()
    errs = []
    if not isinstance(rec, dict) or rec.get('schema') != RECORD_SCHEMA or rec.get('status') != 'NATIVE_GEOMETRY_VALIDATED':
        return ['record schema/status wrong']
    if rec.get('board_sha256') != board_sha:
        errs.append('record is stale: authoritative PCB bytes changed')
    if rec.get('placement_sha256') != sha(placement_bytes):
        errs.append('record is stale: canonical placement changed')
    prov = rec.get('provenance') or {}
    fx = rec.get('geometry')
    if (prov.get('members_sha256') or {}).get(MEMBER) != sha((json.dumps(fx, indent=1, sort_keys=True) + '\n').encode()):
        errs.append('record geometry differs from the retained artifact member')
    e, unknowns = check_geometry(fx, board_sha, json.loads(placement_bytes))
    errs += e
    if rec.get('unknowns') != unknowns:
        errs.append('record unknowns list differs from the geometry')
    return errs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--from-zip', type=Path)
    ap.add_argument('--expect-revision')
    ap.add_argument('--expect-run-id')
    ap.add_argument('--expect-run-attempt')
    ap.add_argument('--write', action='store_true', help='write the validated record (with --from-zip)')
    ap.add_argument('--check', action='store_true', help='re-validate the committed record offline')
    a = ap.parse_args(argv)
    try:
        if a.from_zip:
            if not (a.expect_revision and a.expect_run_id):
                raise ValueError('--expect-revision and --expect-run-id are required')
            rec = from_zip(a.from_zip, a.expect_revision, a.expect_run_id, a.expect_run_attempt)
            if a.write:
                RECORD.write_text(json.dumps(rec, indent=1, sort_keys=True) + '\n')
            print(f"VALIDATED: {len(rec['geometry']['footprints'])} footprints; {len(rec['unknowns'])} unknown extents")
            return 0
        if a.check:
            errs = check_record(json.loads(RECORD.read_text()))
            if errs:
                print('REJECTED: ' + '; '.join(errs[:10]), file=sys.stderr)
                return 1
            print('PASS: native fixture geometry record current; fixture completion is a separate gate')
            return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        print(f'REJECTED: {type(e).__name__}: {e}', file=sys.stderr)
        return 1
    ap.error('use --from-zip or --check')


if __name__ == '__main__':
    sys.exit(main())
