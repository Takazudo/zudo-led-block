#!/usr/bin/env python3
"""Validate the A7 staging evidence bundles with the real catalog validator, in a temporary copy.

The bundles under engineering/a7/evidence/ are not registered in the shared inventory yet (the #9
catalog migration owns those files). This script copies the catalog inputs to a temporary
directory, applies engineering/a7/evidence/registration.json there, runs
`zudo-circuit-doc validate`, and reports the result. It never writes inside the repository.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EVIDENCE = REPO / "engineering" / "a7" / "evidence"
INVENTORY = Path(".claude/skills/component-spec-audit/references/inventory.json")
ROUTING = Path(".claude/skills/component-spec-audit/references/direct-routing.json")


def stage(tmp: Path) -> None:
    for name in ("package.json", "circuit.config.ts"):
        shutil.copy2(REPO / name, tmp / name)
    shutil.copytree(REPO / "circuit", tmp / "circuit")
    shutil.copytree(REPO / ".claude", tmp / ".claude")
    (tmp / "doc").mkdir()
    shutil.copytree(REPO / "doc" / "src", tmp / "doc" / "src")
    os.symlink(REPO / "node_modules", tmp / "node_modules")
    registration = json.loads((EVIDENCE / "registration.json").read_text())
    for line in registration["inventory_lines"]:
        skill = line["owner_skill"]
        target = tmp / ".claude" / "skills" / skill
        if target.exists():
            raise SystemExit(f"{skill} already exists in the shared catalog; register it there instead")
        shutil.copytree(EVIDENCE / skill, target)
    inventory = json.loads((tmp / INVENTORY).read_text())
    known = {line["line_id"] for line in inventory["lines"]}
    for line in registration["inventory_lines"]:
        if line["line_id"] in known:
            raise SystemExit(f"{line['line_id']} already in the shared inventory")
        inventory["lines"].append(line)
    inventory["assertions"]["orderable_lines"] += len(registration["inventory_lines"])
    inventory["assertions"]["fitted_lines"] += len(registration["inventory_lines"])
    (tmp / INVENTORY).write_text(json.dumps(inventory, indent=2) + "\n")
    routing = json.loads((tmp / ROUTING).read_text())
    routing["cases"].extend(registration["direct_routing_cases"])
    (tmp / ROUTING).write_text(json.dumps(routing, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args()
    cli = REPO / "node_modules" / ".bin" / "zudo-circuit-doc"
    if not cli.exists():
        print("NOT RUN: node_modules missing; run pnpm install --frozen-lockfile", file=sys.stderr)
        return 4
    with tempfile.TemporaryDirectory(prefix="a7-stage-validate-") as directory:
        tmp = Path(directory)
        stage(tmp)
        result = subprocess.run([str(cli), "validate"], cwd=tmp, capture_output=True, text=True)
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
    print(f"A7 staging validation exit={result.returncode} (temporary copy; repository untouched)")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
