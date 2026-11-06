#!/usr/bin/env python3
"""Fresh, credential-free checks of the imported A5 records (standard library only).

Run from anywhere; paths resolve from the repository root. Writes nothing inside
engineering/a5/ (the interface checker's output goes to a temporary file).

Checks:
  1. BOM reconciliation: 30 types / 81 fitted pieces = controller 59 + 2 x leaf 10
     + adapter 2, against procurement_rows.json AND the native XML netlists.
  2. Dated cost figures still equal the documented contract values.
  3. Input identity of the HISTORICAL native KiCad records: PCB / project / DRC
     report SHA-256 recorded in pcb_qualification.json and a5_status.json match
     the files; DRC counts still show the controller as UNROUTED.
  4. Re-run integration/check_schematic_interfaces.py on the three netlists (temp
     output) and require the result to equal the historical record apart from
     the repository path prefix.
  5. firmware/dist/source_files.sha256 still matches the firmware sources.

This does not re-run KiCad, CAD, or any hardware test. Exit 0 = PASS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
A5 = ROOT / "engineering" / "a5"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import a5_site  # noqa: E402

COST_CONTRACT = {"1": (9.9396, 15.3496), "10": (8.7205, 13.6055), "100": (6.6386, 11.0751)}
NETLISTS = [f"engineering/a5/integration/native_schematic/{b}/netlist.xml" for b in a5_site.BOARDS]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, help="Optional JSON report path (outside engineering/a5/)")
    args = parser.parse_args()
    results: list[dict] = []

    def record(name: str, ok: bool, **detail):
        results.append({"check": name, "status": "PASS" if ok else "FAIL", **detail})

    # 1. reconciliation
    try:
        data = a5_site.reconcile()
        record("BOM reconciliation (ledger vs native netlists)", True, types=len(data["rows"]["components"]),
               fitted=data["fitted_total"], per_board=data["per_board"], unique_placements=data["unique_placements"])
    except SystemExit as exc:
        record("BOM reconciliation (ledger vs native netlists)", False, error=str(exc))
        data = None

    # 2. cost contract
    rows = json.loads((A5 / "procurement_rows.json").read_text(encoding="utf-8"))
    cost_problems = []
    for qty, (fitted, subtotal) in COST_CONTRACT.items():
        c = rows["cost_checks"][qty]
        got_sub = round(c["fitted_component_cost_per_module_usd"] + c["LED_external_cables_per_module_usd"]
                        + c["power_external_cable_per_module_usd"], 4)
        if c["fitted_component_cost_per_module_usd"] != fitted or got_sub != subtotal:
            cost_problems.append(f"qty {qty}: fitted {c['fitted_component_cost_per_module_usd']} subtotal {got_sub}")
    record("Dated cost figures (2026-11-06 observations)", not cost_problems, problems=cost_problems)

    # 3. historical native record identities
    qual = json.loads((A5 / "electronics/reports/pcb_qualification.json").read_text(encoding="utf-8"))
    status = json.loads((A5 / "integration/a5_status.json").read_text(encoding="utf-8"))
    ident_problems = []
    for board in qual["boards"]:
        base = A5 / "electronics"
        for key, rel in (("pcb_sha256", board["pcb"]), ("project_sha256", board["project"]),
                         ("drc_report_sha256", board["drc_report"])):
            if sha(base / rel) != board[key]:
                ident_problems.append(f"{board['name']} {rel}: {key} mismatch")
        checkpoint = status["pcb_checkpoint"][board["name"]]
        if checkpoint["pcb_sha256"] != board["pcb_sha256"] or checkpoint["drc_sha256"] != board["drc_report_sha256"]:
            ident_problems.append(f"{board['name']}: a5_status checkpoint disagrees with pcb_qualification")
        drc = json.loads((base / board["drc_report"]).read_text(encoding="utf-8"))
        if len(drc["violations"]) != board["violation_count"] or len(drc["unconnected_items"]) != board["unconnected_count"]:
            ident_problems.append(f"{board['name']}: DRC report counts differ from qualification record")
    controller = status["pcb_checkpoint"]["controller"]["counts"]
    unrouted = controller["unconnected_items"] == 130 and controller["violations"] == 2
    record("Historical KiCad 10.0.8 ERC/DRC record input identities (not re-run)", not ident_problems and unrouted,
           problems=ident_problems, controller_status="UNROUTED" if unrouted else "CHANGED - review",
           controller_counts=controller, kicad=qual["native_tool"])

    # 4. fresh netlist interface check vs historical record
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "a5-interface-check.json"
        proc = subprocess.run([sys.executable, "engineering/a5/integration/check_schematic_interfaces.py", *NETLISTS,
                               "--output", str(out)], cwd=ROOT, text=True, capture_output=True)
        fresh = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
    historical = json.loads((A5 / "integration/schematic_interface_check.json").read_text(encoding="utf-8"))
    same = False
    if fresh is not None:
        for row in fresh["source_files"]:
            row["path"] = row["path"].removeprefix("engineering/a5/")
        same = fresh == historical
    record("Netlist interface check re-run (temp output) equals historical record",
           proc.returncode == 0 and bool(fresh and fresh["all_passed"]) and same,
           checks=len(fresh["checks"]) if fresh else 0, exit_code=proc.returncode, identical_to_record=same)

    # 5. firmware source manifest
    fw_problems = []
    lines = (A5 / "firmware/dist/source_files.sha256").read_text(encoding="utf-8").splitlines()
    for line in lines:
        digest, rel = line.split(maxsplit=1)
        path = A5 / "firmware" / rel.strip()
        if not path.is_file() or sha(path) != digest:
            fw_problems.append(rel)
    record("Firmware source manifest (dist/source_files.sha256)", not fw_problems, entries=len(lines), problems=fw_problems)

    report = {"status": "PASS" if all(r["status"] == "PASS" for r in results) else "FAIL",
              "scope": "Fresh data/record identity checks; historical ERC/DRC not re-run; no hardware qualification",
              "manufacturing_released": False, "checks": results}
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
