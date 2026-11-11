#!/usr/bin/env python3
"""Validate the retained A7 candidate evidence in a native-infrastructure-evidence artifact.

Reads either the downloaded artifact ZIP (--zip) or the staged directory that CI uploads
(--dir, the runner temp root). Classification, never promotion:

  VALID_PASS              candidate gate PASS and every retained member matches the summary,
                          the authoritative board and the expected revision
  VALID_FAILURE_EVIDENCE  members are consistent but the candidate gate did not pass
  INCOMPLETE              required candidate members or identity fields are absent
  REJECTED                stale, wrong-revision, wrong-board, tampered or substituted evidence

Only VALID_PASS exits 0 under --require-pass. The infrastructure receipt in the same artifact
is never an A7 candidate result. A valid artifact is a digital record only: no physical fit,
fixture completion or manufacturing approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PROFILE = 'engineering/a7/verification/native_gate.json'
BOARD = 'engineering/a7/electronics/controller/controller.kicad_pcb'
CANDIDATE = 'a7_controller'
PREFIX = 'a7-gate/'
REQUIRED = ('summary.json', 'plan.json', f'evidence/{CANDIDATE}/board_facts.json',
            f'evidence/{CANDIDATE}/board_geometry.json')
ALLOWED = set(REQUIRED)
MAX_MEMBER_BYTES = 8 * 1024 * 1024


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_members(zip_path: Path | None = None, dir_path: Path | None = None) -> dict[str, bytes]:
    """Return a7-gate/* members keyed by their path relative to a7-gate/."""
    out: dict[str, bytes] = {}
    if zip_path is not None:
        with zipfile.ZipFile(zip_path) as z:
            for info in z.infolist():
                name = info.filename
                if info.is_dir() or not name.startswith(PREFIX):
                    continue
                rel = PurePosixPath(name[len(PREFIX):])
                if rel.is_absolute() or '..' in rel.parts:
                    raise ValueError(f'unsafe member name {name}')
                if info.file_size > MAX_MEMBER_BYTES:
                    raise ValueError(f'member too large {name}')
                out[str(rel)] = z.read(info)
    else:
        base = Path(dir_path) / PREFIX.rstrip('/')
        for rel in REQUIRED:
            q = base / rel
            if q.is_file() and not q.is_symlink():
                out[rel] = q.read_bytes()
    return out


def classify(members: dict[str, bytes], *, board_sha: str, image: str, expect_revision: str | None = None,
             expect_checkout: str | None = None, expect_run_id: str | None = None,
             expect_run_attempt: str | None = None, strict_members: bool = True) -> dict:
    reasons: list[str] = []
    rejected: list[str] = []
    if 'summary.json' not in members:
        return {'status': 'INCOMPLETE', 'reasons': ['missing a7-gate/summary.json'], 'rejected': []}
    try:
        s = json.loads(members['summary.json'])
    except ValueError:
        return {'status': 'REJECTED', 'reasons': [], 'rejected': ['summary.json is not JSON']}
    if not isinstance(s, dict):
        return {'status': 'REJECTED', 'reasons': [], 'rejected': ['summary.json is not an object']}

    prof = s.get('profile') or {}
    if prof.get('kind') != 'revision' or prof.get('path') != PROFILE or s.get('board_result') != f'candidate: {CANDIDATE}':
        rejected.append('summary is not the A7 candidate revision gate (infrastructure or other profile substituted)')
    if (s.get('tested_board_sha256') or {}).get(CANDIDATE) != board_sha:
        rejected.append('tested board SHA-256 differs from the authoritative A7 PCB')
    if s.get('image') != image:
        rejected.append('KiCad image differs from the pinned profile image')
    ident = s.get('identity') or {}
    tested_rev = ident.get('pr_head_sha') or ident.get('checkout_head')
    if expect_revision and tested_rev != expect_revision:
        rejected.append(f'tested revision {tested_rev} != expected {expect_revision}')
    if expect_checkout and ident.get('checkout_head') != expect_checkout:
        rejected.append(f"checkout {ident.get('checkout_head')} != expected {expect_checkout}")
    if expect_run_id and str(ident.get('github_run_id')) != str(expect_run_id):
        rejected.append(f"run id {ident.get('github_run_id')} != expected {expect_run_id}")
    if expect_run_attempt:
        if ident.get('github_run_attempt') is None:
            reasons.append('run attempt not recorded by this summary')
        elif str(ident.get('github_run_attempt')) != str(expect_run_attempt):
            rejected.append(f"run attempt {ident.get('github_run_attempt')} != expected {expect_run_attempt}")
    for k in ('workflow_ref', 'workflow_sha', 'tool_sha256'):
        if not ident.get(k):
            reasons.append(f'identity field missing: {k}')

    extra = sorted(set(members) - ALLOWED)
    if extra and strict_members:
        rejected.append(f'unexpected a7-gate members: {extra[:5]}')
    for rel in REQUIRED[1:]:
        if rel not in members:
            reasons.append(f'missing a7-gate/{rel}')

    files = (s.get('evidence') or {}).get('files') or {}
    for rel in REQUIRED[2:]:
        if rel in members:
            want = files.get(rel[len('evidence/'):])
            if want is None:
                rejected.append(f'{rel} present but not listed in summary evidence')
            elif sha(members[rel]) != want:
                rejected.append(f'{rel} SHA-256 differs from summary')
    if 'plan.json' in members:
        if s.get('plan_sha256') is None:
            reasons.append('summary records no plan_sha256')
        elif sha(members['plan.json']) != s['plan_sha256']:
            rejected.append('plan.json SHA-256 differs from summary')

    facts_rel, geom_rel = REQUIRED[2], REQUIRED[3]
    if facts_rel in members and geom_rel in members:
        try:
            facts, geom = json.loads(members[facts_rel]), json.loads(members[geom_rel])
        except ValueError:
            rejected.append('board facts/geometry are not JSON')
        else:
            if not isinstance(facts, dict):
                rejected.append('board facts are not an object')
            else:
                if facts.get('board_sha256') != board_sha:
                    rejected.append('board_facts.board_sha256 differs from the authoritative A7 PCB')
                if facts.get('geometry_sha256') != sha(json.dumps(geom, sort_keys=True).encode()):
                    rejected.append('board facts/geometry pair inconsistent')

    if rejected:
        status = 'REJECTED'
    elif reasons:
        status = 'INCOMPLETE'
    elif s.get('status') == 'PASS' and not s.get('failures'):
        status = 'VALID_PASS'
    else:
        status = 'VALID_FAILURE_EVIDENCE'
    return {'status': status, 'gate_status': s.get('status'), 'reasons': reasons, 'rejected': rejected,
            'identity': {k: ident.get(k) for k in ('github_run_id', 'github_run_attempt', 'pr_head_sha', 'pr_base_sha',
                                                    'checkout_head', 'checkout_is_synthetic_merge', 'workflow_sha')},
            'tested_board_sha256': (s.get('tested_board_sha256') or {}).get(CANDIDATE),
            'members_sha256': {k: sha(v) for k, v in sorted(members.items())},
            'scope': 'Digital native-gate evidence record only; not fixture completion, physical fit or manufacturing approval.'}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument('--zip', type=Path)
    src.add_argument('--dir', type=Path, help='staged upload root (contains a7-gate/)')
    ap.add_argument('--expect-revision', help='PR head SHA (pull_request) or pushed SHA')
    ap.add_argument('--expect-checkout', help='actual checkout SHA (synthetic merge for pull_request)')
    ap.add_argument('--expect-run-id')
    ap.add_argument('--expect-run-attempt')
    ap.add_argument('--require-pass', action='store_true', help='exit 0 only for VALID_PASS')
    ap.add_argument('--out', type=Path)
    a = ap.parse_args(argv)
    board_sha = sha((ROOT / BOARD).read_bytes())
    image = json.loads((ROOT / PROFILE).read_text())['image']
    try:
        members = read_members(a.zip, a.dir)
        r = classify(members, board_sha=board_sha, image=image, expect_revision=a.expect_revision,
                     expect_checkout=a.expect_checkout, expect_run_id=a.expect_run_id,
                     expect_run_attempt=a.expect_run_attempt, strict_members=a.zip is not None)
    except (OSError, ValueError, zipfile.BadZipFile) as e:
        r = {'status': 'REJECTED', 'reasons': [], 'rejected': [f'{type(e).__name__}: {e}']}
    if a.zip is not None:
        r['zip_sha256'] = sha(a.zip.read_bytes())
    text = json.dumps(r, indent=1, sort_keys=True) + '\n'
    if a.out:
        a.out.write_text(text)
    print(text, end='')
    if a.require_pass:
        return 0 if r['status'] == 'VALID_PASS' else 1
    return 0 if r['status'] in ('VALID_PASS', 'VALID_FAILURE_EVIDENCE') else 1


if __name__ == '__main__':
    sys.exit(main())
