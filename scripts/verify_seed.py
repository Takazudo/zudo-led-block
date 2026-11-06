#!/usr/bin/env python3
"""Verify the imported Light Block A5 checkpoint against provenance/seed-manifest.json.

Adapted from the handoff's verify-seed.py. It checks *file identity only*
(size + SHA-256 of all 786 seed files, no symlinks, no unexpected extra files
under engineering/a5/). It does not run firmware, KiCad, CAD, or physical
qualification and does not certify a manufacturing release.

Usage (from the repository root):

    python3 scripts/verify_seed.py --manifest provenance/seed-manifest.json --repo .

Standard library only. Exit 0 = PASS, 1 = FAIL.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath

SEED_ROOT = PurePosixPath("engineering/a5")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, required=True, help="Path to seed-manifest.json")
    parser.add_argument("--repo", type=Path, required=True, help="Repository root containing engineering/a5/")
    parser.add_argument("--output", type=Path, help="Optional JSON report path (keep it outside engineering/a5/)")
    parser.add_argument("--allow-extra", action="store_true",
                        help="Do not fail on files under engineering/a5/ that are absent from the manifest")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    repo = args.repo.resolve()
    failures: list[dict[str, str]] = []
    seen: set[str] = set()
    total_bytes = 0
    for row in manifest["files"]:
        relative = row["repo_path"]
        path = PurePosixPath(relative)
        if path.is_absolute() or ".." in path.parts or relative in seen:
            raise ValueError(f"Unsafe or duplicated manifest path: {relative}")
        if path.parts[:2] != SEED_ROOT.parts:
            raise ValueError(f"Manifest path outside {SEED_ROOT}: {relative}")
        seen.add(relative)
        source = repo.joinpath(*path.parts)
        if source.is_symlink() or not source.is_file():
            failures.append({"path": relative, "reason": "missing or symlink"})
            continue
        size = source.stat().st_size
        total_bytes += size
        if size != row["bytes"] or sha256_file(source) != row["sha256"]:
            failures.append({"path": relative, "reason": "size or SHA-256 mismatch"})
    if len(seen) != manifest["included_file_count"]:
        raise ValueError("Manifest file count does not match its entries")

    omitted = {f"{SEED_ROOT}/{row['original_path']}" for row in manifest["omitted_files"]}
    extra: list[str] = []
    present_omitted: list[str] = []
    seed_dir = repo.joinpath(*SEED_ROOT.parts)
    if seed_dir.is_dir():
        for candidate in sorted(seed_dir.rglob("*")):
            if candidate.is_dir() and not candidate.is_symlink():
                continue
            rel = candidate.relative_to(repo).as_posix()
            if rel in seen:
                continue
            if rel in omitted:
                present_omitted.append(rel)  # locally regenerated derived output; git-ignored
                continue
            # Ignore generated firmware build products and Python caches created by checks.
            parts = PurePosixPath(rel).parts
            if "__pycache__" in parts or rel.startswith(f"{SEED_ROOT}/firmware/build/"):
                continue
            extra.append(rel)
    if extra and not args.allow_extra:
        failures.extend({"path": rel, "reason": "unexpected file not in seed manifest"} for rel in extra)

    report = {
        "status": "PASS" if not failures else "FAIL",
        "checked_files": len(seen),
        "checked_bytes": total_bytes,
        "expected_bytes": manifest["included_bytes"],
        "failures": failures,
        "unexpected_files": extra,
        "omitted_files_present_locally": present_omitted,
        "declared_omitted_files": [row["original_path"] for row in manifest["omitted_files"]],
        "source_archive_sha256": manifest["source_archive"]["sha256"],
        "scope": "Exact original A5 seed file identity; no hardware qualification",
        "manufacturing_released": False,
    }
    if total_bytes != manifest["included_bytes"] and not failures:
        report["status"] = "FAIL"
        report["failures"].append({"path": str(SEED_ROOT), "reason": "total byte count mismatch"})
    text = json.dumps(report, indent=2)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
