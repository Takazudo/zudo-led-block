#!/usr/bin/env python3
"""Validate the Cloudflare Build Output produced by `pnpm cf:build` (no network, no credentials).

Usage: python3 scripts/check_cf_output.py doc/.cloudflare/output/v0 [--dist doc/dist] [--print-mode]

Checks that the default Worker is the reviewed assets-only configuration
(name, custom domain, workers.dev/preview URLs off, auto-trailing-slash, real
404 page, no server entrypoint), that its asset tree is byte-identical to the
built docs (doc/dist), and reports buildContext.mode. With --print-mode only the
recorded mode (or an empty line when none is recorded) is printed, for use by a
later `cf deploy --prebuilt [--mode <mode>]`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

EXPECTED_WORKER = {
    "name": "zudo-led-block",
    "domains": ["zudo-led-block.zudolab.dev"],
    "workersDev": False,
    "previewUrls": False,
    "assets": {"htmlHandling": "auto-trailing-slash", "notFoundHandling": "404-page"},
}
ALLOWED_WORKER_KEYS = set(EXPECTED_WORKER) | {"compatibilityDate"}


def tree(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("output", type=Path)
    parser.add_argument("--dist", type=Path, default=Path(__file__).resolve().parents[1] / "doc" / "dist")
    parser.add_argument("--print-mode", action="store_true")
    args = parser.parse_args()
    root = args.output
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    mode = config.get("buildContext", {}).get("mode")
    if args.print_mode:
        print(mode or "")
        return 0
    problems = []
    if config.get("buildContext", {}).get("isPreview") is not False:
        problems.append("buildContext.isPreview is not false")
    workers = sorted(p.name for p in (root / "workers").iterdir() if p.is_dir())
    if workers != ["default"]:
        problems.append(f"unexpected workers in Build Output: {workers}")
    worker_dir = root / "workers" / "default"
    worker = json.loads((worker_dir / "worker.config.json").read_text(encoding="utf-8"))
    for key, value in EXPECTED_WORKER.items():
        if worker.get(key) != value:
            problems.append(f"worker.{key} = {worker.get(key)!r}, expected {value!r}")
    extra = sorted(set(worker) - ALLOWED_WORKER_KEYS)
    if extra:
        problems.append(f"unexpected worker fields (entrypoint/bindings/account must not be committed): {extra}")
    code = [p.relative_to(worker_dir).as_posix() for p in worker_dir.iterdir() if p.name not in ("assets", "worker.config.json")]
    if code:
        problems.append(f"assets-only Worker has extra build files: {code}")
    assets, dist = tree(worker_dir / "assets"), tree(args.dist)
    if assets != dist:
        missing = sorted(set(dist) - set(assets))[:10]
        added = sorted(set(assets) - set(dist))[:10]
        changed = sorted(k for k in set(assets) & set(dist) if assets[k] != dist[k])[:10]
        problems.append(f"assets differ from doc/dist: missing={missing} added={added} changed={changed}")
    if "404.html" not in assets:
        problems.append("404.html missing from assets")
    report = {"status": "PASS" if not problems else "FAIL", "build_context_mode": mode,
              "prebuilt_mode_flag": f"--mode {mode}" if mode else "(omit --mode)", "asset_files": len(assets),
              "worker": worker, "problems": problems}
    print(json.dumps(report, indent=2))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
