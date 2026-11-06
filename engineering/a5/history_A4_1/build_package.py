"""Package the A4.1 continuation sources and verified deliverables.

This script validates the frozen procurement ledger and file evidence. It does
not rerun visual/hardware reviews or promote unfinished work to a release.
No network access, upload, vendor message or order occurs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from build_procurement_rows import build

ROOT = Path(__file__).resolve().parent


def read_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def write_json(relative: str, value: dict) -> None:
    target = ROOT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT.parent / "light_block_A4_1_design_package.zip")
    args = parser.parse_args()
    output = args.output.resolve()
    data = read_json("procurement_rows.json")
    if build() != data:
        raise ValueError("Procurement ledger differs from its frozen inputs; regenerate deliberately")
    required = [
        "README_JA.md", "continue-here.md", "REPRODUCE.md",
        "deliverables/light_block_A4_1_front_and_procurement.pdf",
        "deliverables/light_block_A4_1_parts.xlsx",
        "deliverables/light_block_A4_front_preview.png",
        "references/light_block_A3_design_package.zip",
        "audits/front_panel/independent_front_validation.json",
        "audits/electronics/A4_electronics_recovery_audit.json",
        "audits/electronics/TDK_SPM4020T_4R7M_LR_evaluation.json",
        "audits/workbook/workbook_review.json", "audits/workbook/native_features.json",
        "audits/report/report_verification.json", "audits/recovery/recovery_integrity.json",
    ]
    for relative in required:
        if not (ROOT / relative).is_file():
            raise FileNotFoundError(relative)
    front = read_json("audits/front_panel/independent_front_validation.json")
    if not front["all_passed"]:
        raise ValueError("Front review has unresolved failures")
    for variant in front["variants"]:
        name = variant["variant"]
        for relative, key in [
            (f"front_panel/exports/rear_A4_{name}_REAR_FULL_FROST_CLEAR_LETTERS.svg", "source_svg_sha256"),
            (f"front_panel/exports/front_A4_{name}_2mm.step", "source_step_sha256"),
        ]:
            if digest(ROOT / relative) != variant[key]:
                raise ValueError(f"Front changed since review: {relative}")
    workbook = read_json("audits/workbook/workbook_review.json")
    if workbook["issues"] or digest(ROOT / "deliverables/light_block_A4_1_parts.xlsx") != workbook["sourceSha256"]:
        raise ValueError("Workbook differs from the reviewed file, or review has issues")
    native = read_json("audits/workbook/native_features.json")
    if not native["features_preserved"]:
        raise ValueError("Workbook native features not preserved")
    report = read_json("audits/report/report_verification.json")
    if digest(ROOT / "deliverables/light_block_A4_1_front_and_procurement.pdf") != report["pdf_sha256"]:
        raise ValueError("Report differs from the visually reviewed PDF")
    if digest(ROOT / "procurement_rows.json") != report["procurement_data_sha256"]:
        raise ValueError("Procurement data changed after the report review")
    if not report["visual_review"]["all_passed"]:
        raise ValueError("Report visual review has unresolved issues")
    verification = {
        "project": "Light Block", "revision": "A4.1", "manufacturing_released": False,
        "packaged_at_utc": datetime.now(timezone.utc).isoformat(),
        "front_panel": {"status": "PASS", "scope": front["scope"],
                        "files_independently_verified": front["manifest_files_checked"],
                        "details": "audits/front_panel/independent_front_validation.json"},
        "procurement": {"status": "PASS", "as_of_jst": data["as_of_jst"],
                        "summary": data["summary"], "cost_checks": data["cost_checks"],
                        "limitations": data["quantity_assumptions"]},
        "workbook": {"status": "PASS", "details": "audits/workbook/workbook_review.json",
                     "native_features": "audits/workbook/native_features.json",
                     "engine": workbook["engine"]},
        "report": {"review_record": "audits/report/report_verification.json", "details": report},
        "electronic_review": {"scope": "Desk analysis; no built hardware tested",
                              "details": "audits/electronics/"},
        "not_verified": [
            "Complete rear CAD with installed connectors/cables and 30 mm depth",
            "Native schematic, routed boards, ERC/DRC, Gerber/drill and final BOM/CPL",
            "Power protection, ADC off-state injection, effective capacitance and startup/hot-short behavior",
            "Working firmware with explicit fault/reset recovery and factory programming",
            "Integrated hardware, thermal, optical and insertion/withdrawal load tests",
            "Order-specific supplier acceptance, final quote and reserved stock",
        ],
        "superseded_records": "history_A4/ and original research/evidence record the earlier A4 state; current selection is procurement_rows.json",
    }
    write_json("verification_A4_1.json", verification)
    write_json("evidence/observation_index.json", {
        "revision": "A4.1", "purpose": "Dated public observations, not stock reservations or quotes",
        "primary_jlc_parts": [
            {k: r.get(k) for k in ("c_code", "url", "observed_jst", "snapshot", "snapshot_sha256", "observation_method")}
            for r in data["components"]
        ],
        "fallback_jlc_parts": [
            {k: r.get(k) for k in ("c_code", "url", "observed_jst", "snapshot", "snapshot_sha256", "selection")}
            for r in data.get("alternative_components", [])
        ],
        "external_items": [
            {k: r.get(k) for k in ("id", "url", "observed_jst", "stock", "snapshot")}
            for r in data["external_items"]
        ],
        "historical_sources": "Original *_evidence/ files and research/io/harness records remain as dated A4 references.",
        "raw_supplier_pages_or_browser_screenshots_included": False,
    })
    # Include sources, compact facts and deliverables; omit caches and superseded QA previews.
    ignored_dirs = {"__pycache__", "node_modules", ".git", "dist", "spreadsheet_qa"}
    files = [p for p in sorted(ROOT.rglob("*")) if p.is_file()
             and p != output and p.name != "package_manifest.json"
             and not any(part in ignored_dirs for part in p.relative_to(ROOT).parts)
             and p.suffix.lower() not in {".pyc", ".html"}]
    manifest = {
        "revision": "A4.1", "manufacturing_released": False,
        "source_of_truth": "procurement_rows.json",
        "front_geometry_revision": "A4 unchanged; verified for A4.1",
        "history": "history_A4/ and dated original research/evidence are historical",
        "entries": [{"path": p.relative_to(ROOT).as_posix(), "size_bytes": p.stat().st_size,
                     "sha256": digest(p)} for p in files],
    }
    write_json("package_manifest.json", manifest)
    files.append(ROOT / "package_manifest.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=7) as archive:
        for path in files:
            archive.write(path, "light_block_A4_1/" + path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(output) as archive:
        error = archive.testzip()
        if error:
            raise ValueError(f"ZIP CRC failed: {error}")
        for entry in manifest["entries"]:
            contents = archive.read("light_block_A4_1/" + entry["path"])
            if hashlib.sha256(contents).hexdigest() != entry["sha256"] or len(contents) != entry["size_bytes"]:
                raise ValueError(f"ZIP content mismatch: {entry['path']}")
    print(json.dumps({"path": str(output), "size_bytes": output.stat().st_size,
                      "sha256": digest(output), "entries": len(files), "crc": "PASS",
                      "manifest_hashes": "PASS", "manufacturing_released": False}, indent=2))


if __name__ == "__main__":
    main()
