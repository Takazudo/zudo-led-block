"""Build and verify the Light Block A5 engineering checkpoint.

Checks recorded source/artifact identity and native results. Does not rerun
physical qualification, release manufacturing, upload, order, flash or print.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from build_procurement_rows import build

ROOT = Path(__file__).resolve().parent

def read_json(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))

def write_json(relative, value):
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def check_hash(relative, expected):
    path = ROOT / relative
    if not path.is_file():
        raise FileNotFoundError(relative)
    actual = digest(path)
    if actual != expected:
        raise ValueError(f"Changed since recorded verification: {relative}")
    return actual

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT.parent/"light_block_A5_design_package.zip")
    args = parser.parse_args()
    output = args.output.resolve()
    data = read_json("procurement_rows.json")
    if data["revision"] != "A5" or build() != data:
        raise ValueError("Current ledger differs from frozen A5 selection")
    status = read_json("integration/a5_status.json")
    if status["manufacturing_released"] is not False:
        raise ValueError("This builder is only for an unreleased A5 checkpoint")
    required = [
        "README_JA.md", "continue-here.md", "REPRODUCE.md",
        "deliverables/light_block_A5_engineering_update.pdf",
        "deliverables/light_block_A5_parts.xlsx",
        "deliverables/light_block_A4_front_preview.png",
        "references/light_block_A3_design_package.zip",
        "integration/independent_review/review.json",
        "integration/schematic_visual_review.json",
        "integration/artifact_review_index.json",
        *status["supporting_records"].values(),
    ]
    for relative in required:
        if not (ROOT/relative).is_file():
            raise FileNotFoundError(relative)
    pcb_qualification = read_json(status["supporting_records"]["electronics"])
    for board in pcb_qualification["boards"]:
        for path_key, hash_key in (("pcb","pcb_sha256"), ("project","project_sha256"),
                                   ("drc_report","drc_report_sha256")):
            check_hash("electronics/"+board[path_key], board[hash_key])
    for item in pcb_qualification["footprint_library"]+pcb_qualification["authoritative_inputs"]:
        check_hash("electronics/"+item["path"], item["sha256"])

    front = read_json("audits/front_panel/independent_front_validation.json")
    if not front["all_passed"]:
        raise ValueError("Retained front audit did not pass")
    for variant in front["variants"]:
        name = variant["variant"]
        check_hash(f"front_panel/exports/rear_A4_{name}_REAR_FULL_FROST_CLEAR_LETTERS.svg",
                   variant["source_svg_sha256"])
        check_hash(f"front_panel/exports/front_A4_{name}_2mm.step",
                   variant["source_step_sha256"])

    workbook = read_json("audits/workbook/workbook_review.json")
    if workbook["issues"] or not workbook["visual_review"]["all_passed"]:
        raise ValueError("Unresolved workbook review")
    check_hash("deliverables/light_block_A5_parts.xlsx", workbook["sourceSha256"])
    if not read_json("audits/workbook/native_features.json")["features_preserved"]:
        raise ValueError("Workbook features were not preserved")
    report = read_json("audits/report/report_verification.json")
    for relative, key in [
        ("deliverables/light_block_A5_engineering_update.pdf", "pdf_sha256"),
        ("procurement_rows.json", "procurement_data_sha256"),
        ("integration/a5_status.json", "status_data_sha256"),
    ]:
        check_hash(relative, report[key])
    if not report["visual_review"]["all_passed"]:
        raise ValueError("Unresolved report visual review")

    schematic = []
    boards = []
    for name in ("controller", "led_leaf", "power_adapter"):
        record = read_json(f"integration/native_schematic/{name}/native_run.json")
        check_hash(f"electronics/native/{name}/{name}.kicad_sch", record["schematic_sha256_after"])
        if not record["all_passed"] or record["erc_errors"] or record["erc_warnings"]:
            raise ValueError(f"Native schematic check failed: {name}")
        schematic.append(record)
        drc = read_json(f"electronics/reports/{name}_drc.json")
        counts = {"violations": len(drc.get("violations", [])),
                  "unconnected_items": len(drc.get("unconnected_items", [])),
                  "schematic_parity": len(drc.get("schematic_parity", []))}
        check_hash(f"electronics/native/{name}/{name}.kicad_pcb",
                   status["pcb_checkpoint"][name]["pcb_sha256"])
        check_hash(f"electronics/reports/{name}_drc.json",
                   status["pcb_checkpoint"][name]["drc_sha256"])
        if counts != status["pcb_checkpoint"][name]["counts"]:
            raise ValueError(f"DRC result differs from the documented checkpoint: {name}")
        if name != "controller" and any(counts.values()):
            raise ValueError(f"Small board no longer has the recorded clean DRC: {name}")
        boards.append({"board": name, **counts,
                       "types": dict(Counter(v["type"] for v in drc.get("violations", []))),
                       "status": "UNROUTED_CONTROLLER" if name == "controller" else "NATIVE_DRC_PASS",
                       "record": f"electronics/reports/{name}_drc.json"})
    interface = read_json("integration/schematic_interface_check.json")
    if not interface["all_passed"]:
        raise ValueError("Netlist interface mismatch")
    for item in interface["source_files"]:
        check_hash(item["path"], item["sha256"])
    for item in read_json("integration/schematic_visual_review.json")["files"]:
        check_hash(item["path"], item["sha256"])
    review = read_json("integration/independent_review/review.json")
    for relative, sha in review["review_input_sha256"].items():
        check_hash(relative, sha)
    artifact_index = read_json("integration/artifact_review_index.json")
    for item in artifact_index["files"]:
        check_hash(item["path"], item["sha256"])

    fw = read_json("firmware/dist/verification.json")
    if fw["tests"]["arm_compile_link"] != "PASS" or fw["tests"]["hardware_tested"]:
        raise ValueError("Unexpected firmware verification state")
    check_hash("firmware/dist/source_files.sha256", fw["source_manifest"]["sha256"])
    firmware_source_paths = set()
    for line in (ROOT/"firmware/dist/source_files.sha256").read_text().splitlines():
        sha, relative = line.split(None, 1)
        relative = relative.strip()
        check_hash("firmware/"+relative, sha)
        firmware_source_paths.add("firmware/"+relative)
    if len(firmware_source_paths) != fw["source_manifest"]["files"]:
        raise ValueError("Tested firmware source count differs from its release record")
    for item in fw["artifacts"]:
        check_hash("firmware/dist/"+item["file"], item["sha256"])

    verification = {
        "project": "Light Block", "revision": "A5", "manufacturing_released": False,
        "packaged_at_utc": datetime.now(timezone.utc).isoformat(),
        "front": {"status": "RETAINED_REVIEWED_A4", "source_hash_check": "PASS",
                  "record": "audits/front_panel/independent_front_validation.json"},
        "native_schematics": {"status": "PASS", "boards": [
            {k:r[k] for k in ("board","kicad_version","erc_errors","erc_warnings","ignored_checks")}
            for r in schematic]},
        "native_boards": boards,
        "interfaces": {"status": "PASS", "checks": len(interface["checks"]),
                       "record": "integration/schematic_interface_check.json"},
        "independent_review": {"record": "integration/independent_review/review.json",
                               "status": review["status"],
                               "open_findings": [v["id"] for v in review["findings"]
                                                 if v["status"] == "open_hardware_gate"]},
        "firmware": {"status": fw["status"], "source_manifest_entries": len(firmware_source_paths),
                     "source_and_artifact_hashes": "PASS", "tests": fw["tests"],
                     "memory": fw["memory"], "record": "firmware/dist/verification.json"},
        "mechanical": {"record": status["supporting_records"]["mechanical"],
                       "status": status["mechanical_status"]},
        "procurement": {"summary": data["summary"], "as_of_jst": data["as_of_jst"],
                        "cost_checks": data["cost_checks"]},
        "workbook": {"status": "PASS", "record": "audits/workbook/workbook_review.json",
                     "engine": workbook["engine"]},
        "report": {"status": "PASS", "record": "audits/report/report_verification.json"},
        "remaining": status["remaining_rows"],
        "history": "history_A4_1 and history_A4 contain prior decisions/values. Current contract is A5.",
    }
    write_json("verification_A5.json", verification)
    write_json("evidence/observation_index.json", {
        "revision": "A5", "purpose": "Dated public observations, not reservations or quotes",
        "primary_jlc_parts": [
            {k:r.get(k) for k in ("c_code","url","observed_jst","snapshot","snapshot_sha256","observation_method")}
            for r in data["components"]],
        "external_items": [
            {k:r.get(k) for k in ("id","url","observed_jst","stock","snapshot")}
            for r in data["external_items"]],
        "new_primary_document_sources": [
            "mechanical/manufacturer_source_metadata.json",
            "integration/independent_review/review.json",
            "firmware/sources.json",
            status["supporting_records"]["electronics"]],
        "historical_sources": "Dated A4/A4.1 compact observations retained as history.",
        "raw_supplier_pages_included": False,
    })

    ignored_dirs = {"__pycache__", "node_modules", ".git", ".pytest_cache", "spreadsheet_qa"}
    def include(path):
        relative = path.relative_to(ROOT).as_posix()
        if path == output or path == ROOT/"package_manifest.json":
            return False
        # Every file covered by the tested firmware source manifest is retained,
        # including licensed SDK release notes and supporting resources.
        if relative in firmware_source_paths:
            return True
        if any(part in ignored_dirs for part in path.relative_to(ROOT).parts):
            return False
        if relative.startswith("firmware/build/"):
            return False
        if relative.startswith("mechanical/build_") and path.suffix.lower() == ".log":
            return False
        if path.suffix.lower() in {".pyc", ".kicad_prl", ".lck", ".bak"}:
            return False
        if relative.startswith("electronics/references/"):
            return False
        if relative.startswith("mechanical/evidence/"):
            return path.suffix.lower() == ".json"
        if relative.startswith("integration/evidence/"):
            return path.name.endswith(".snapshot.json") or path.name.endswith("_index.json")
        if path.suffix.lower() == ".html":
            return False
        return True
    files = [p for p in sorted(ROOT.rglob("*")) if p.is_file() and include(p)]
    included = {p.relative_to(ROOT).as_posix() for p in files}
    if not firmware_source_paths.issubset(included):
        raise ValueError("Archive would omit tested firmware source")
    for item in fw["artifacts"]:
        if "firmware/dist/"+item["file"] not in included:
            raise ValueError("Archive would omit the actual firmware image")
    manifest = {
        "revision": "A5", "manufacturing_released": False,
        "part_source_of_truth": "procurement_rows.json",
        "front_geometry_revision": "A4 retained",
        "firmware_source_manifest_entries": len(firmware_source_paths),
        "entries": [{"path":p.relative_to(ROOT).as_posix(),"size_bytes":p.stat().st_size,
                     "sha256":digest(p)} for p in files],
    }
    write_json("package_manifest.json", manifest)
    files.append(ROOT/"package_manifest.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=7) as archive:
        for path in files:
            archive.write(path, "light_block_A5/"+path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(output) as archive:
        if archive.testzip():
            raise ValueError("ZIP CRC failed")
        for item in manifest["entries"]:
            contents = archive.read("light_block_A5/"+item["path"])
            if len(contents) != item["size_bytes"] or hashlib.sha256(contents).hexdigest() != item["sha256"]:
                raise ValueError("Archived hash mismatch: "+item["path"])
    print(json.dumps({"path":str(output),"size_bytes":output.stat().st_size,
                      "sha256":digest(output),"entries":len(files),
                      "firmware_source_entries_preserved":len(firmware_source_paths),
                      "crc":"PASS","manifest_hashes":"PASS","manufacturing_released":False}, indent=2))

if __name__ == "__main__":
    main()
