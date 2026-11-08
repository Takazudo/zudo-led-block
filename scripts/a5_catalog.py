#!/usr/bin/env python3
"""A5 fitted-identity reconciliation and component-catalog consistency checks (stdlib only).

Subcommands (paths resolve from the repository root):

  reconcile [--check]  Build provenance/a5-catalog/reconciliation.json from the immutable
                       A5 fitted ledger, procurement rows, identity snapshots and the three
                       native netlists, plus the reviewed identity crosswalk. With --check,
                       write nothing and fail when the committed file is missing or stale.
                       Fails on any count, identity or mapping discrepancy that the reviewed
                       crosswalk does not explain.
  check                Verify the component-evidence catalog against the reconciliation:
                       inventory lines and declared placements, owner bundles, pin maps
                       against the A5 netlists, distributor identity facts, direct routing,
                       publication selection and expected counts, and that no alternative
                       or rejected identity appears anywhere in the catalog.
  scaffold CODE...     Create owner bundles for the named LCSC codes from the reconciliation
                       (identity, retained distributor snapshot, project-state pin map).
                       Refuses to overwrite an existing bundle; evidence is then hand-edited.

Nothing here writes to engineering/a5/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
A5 = ROOT / "engineering" / "a5"
CATALOG_PROV = ROOT / "provenance" / "a5-catalog"
CROSSWALK = CATALOG_PROV / "identity-crosswalk.json"
LCSC_LISTINGS = CATALOG_PROV / "lcsc-listings-2026-11-08.json"
RECONCILIATION = CATALOG_PROV / "reconciliation.json"
SKILLS = ROOT / ".claude" / "skills"
INVENTORY = SKILLS / "component-spec-audit" / "references" / "inventory.json"
DIRECT_ROUTING = SKILLS / "component-spec-audit" / "references" / "direct-routing.json"
SELECTION = ROOT / "circuit" / "publication" / "selection.json"

LEDGER = "electronics/fitted_component_ledger.json"
PROCUREMENT = "procurement_rows.json"
BOARDS = ("controller", "led_leaf", "power_adapter")
NETLISTS = {board: f"integration/native_schematic/{board}/netlist.xml" for board in BOARDS}
IDENTITY_SNAPSHOT_DIRS = ("ic_led_evidence", "passive_evidence", "mechanical_evidence", "integration/evidence")
EXPECTED = {
    "identities": 30,
    "unique_placements": 71,
    "unique_placements_by_board": {"controller": 59, "led_leaf": 10, "power_adapter": 2},
    "physical_pieces": 81,
    "board_copies": {"controller": 1, "led_leaf": 2, "power_adapter": 1},
}
# Fitted identities the task contract names explicitly, with the alternatives that must never be fitted.
REQUIRED_FITTED = {"C52917434": "WS2812B-2020-V6", "C140331": "TPS2552DBVR-1"}
FORBIDDEN_FITTED_MPNS = ("WS2812B-MINI-V6", "TPS2553DBVR-1")
ZERO = "0" * 64


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class Inputs:
    """Every file the reconciliation reads, hashed once."""

    def __init__(self):
        self.hashes: dict[str, str] = {}

    def json(self, path: Path):
        self.hashes[rel(path)] = sha256_file(path)
        return load_json(path)

    def xml(self, path: Path):
        self.hashes[rel(path)] = sha256_file(path)
        return ET.parse(path).getroot()


def netlist_components(root):
    libparts = {}
    for part in root.find("libparts"):
        pins = {pin.get("num"): {"name": pin.get("name"), "type": pin.get("type")} for pin in part.find("pins")}
        libparts[(part.get("lib"), part.get("part"))] = pins
    nets = {}
    for net in root.find("nets"):
        for node in net:
            nets.setdefault(node.get("ref"), {})[node.get("pin")] = net.get("name")
    comps = {}
    for comp in root.find("components"):
        fields = {field.get("name"): (field.text or "") for field in comp.find("fields")}
        lib = comp.find("libsource")
        key = (lib.get("lib"), lib.get("part"))
        pin_nums = [pin.get("num") for unit in comp.find("units") for pin in unit.find("pins")]
        comps[comp.get("ref")] = {
            "value": comp.findtext("value"),
            "footprint": comp.findtext("footprint"),
            "mpn": fields.get("MPN", ""),
            "lcsc": fields.get("LCSC", ""),
            "symbol": f"{key[0]}:{key[1]}",
            "pins": [
                {"num": num, "name": libparts[key][num]["name"], "type": libparts[key][num]["type"], "net": nets.get(comp.get("ref"), {}).get(num, "")}
                for num in pin_nums
            ],
        }
    return comps


def find_identity_snapshot(inputs: Inputs, code: str):
    """The retained A5 JLCPCB product-props snapshot that carries structured identity, if any."""
    found = []
    for directory in IDENTITY_SNAPSHOT_DIRS:
        path = A5 / directory / f"{code}.snapshot.json"
        if not path.is_file():
            continue
        data = inputs.json(path)
        product = data.get("product", data)
        if all(product.get(key) for key in ("componentCode", "componentModelEn", "componentBrandEn")):
            found.append({
                "path": rel(path),
                "sha256": inputs.hashes[rel(path)],
                "componentCode": product["componentCode"],
                "componentModelEn": product["componentModelEn"],
                "componentBrandEn": product["componentBrandEn"],
                "componentSpecificationEn": product.get("componentSpecificationEn") or "",
                "observed_utc": data.get("observed_utc") or data.get("observed_jst", ""),
                "url": data.get("url", ""),
                "recorded_html_sha256": data.get("html_sha256") or data.get("source_html_sha256", ""),
            })
    return found


def build_reconciliation():
    inputs = Inputs()
    problems: list[str] = []
    ledger = inputs.json(A5 / LEDGER)
    procurement = inputs.json(A5 / PROCUREMENT)
    crosswalk = inputs.json(CROSSWALK)
    listings = inputs.json(LCSC_LISTINGS)["listings"]
    netlists = {board: netlist_components(inputs.xml(A5 / path)) for board, path in NETLISTS.items()}

    proc_rows = {row["c_code"]: row for row in procurement["components"]}
    lines = {entry["lcsc"]: entry for entry in crosswalk["lines"]}
    spelling = {entry["lcsc"]: entry for entry in crosswalk["spelling_crosswalk"]}
    ledger_rows = ledger["components"]
    codes = [row["c_code"] for row in ledger_rows]

    if len(codes) != len(set(codes)):
        problems.append(f"fitted ledger: duplicate C-codes {sorted(c for c, n in Counter(codes).items() if n > 1)}")
    if set(codes) != set(proc_rows):
        problems.append(f"ledger/procurement identity sets differ: ledger-only {sorted(set(codes) - set(proc_rows))}, procurement-only {sorted(set(proc_rows) - set(codes))}")
    if set(codes) != set(lines):
        problems.append(f"ledger/crosswalk identity sets differ: {sorted(set(codes) ^ set(lines))}")
    for key in ("owner_skill", "line_id", "record_id", "function"):
        values = [entry[key] for entry in crosswalk["lines"]]
        if len(values) != len(set(values)):
            problems.append(f"crosswalk: duplicate {key}")

    alternatives = sorted(row["c_code"] for row in procurement.get("alternative_components", []))
    external = sorted(item["id"] for item in procurement.get("external_items", []))

    def allowed_spelling(code, value, source):
        entry = spelling.get(code)
        if not entry:
            return False
        return any(item["spelling"] == value and source in item["sources"] for item in entry["observed_spellings"])

    netlist_refs_seen = {board: set() for board in BOARDS}
    identities = []
    for row in sorted(ledger_rows, key=lambda r: r["c_code"]):
        code = row["c_code"]
        proc = proc_rows.get(code, {})
        line = lines.get(code, {})
        canonical = line.get("canonical_mpn", row["mpn"])
        discrepancies = []

        def compare(label, source, value):
            if value == canonical:
                return
            if allowed_spelling(code, value, source):
                discrepancies.append({"field": label, "source": source, "observed": value, "canonical": canonical, "resolution": "reviewed crosswalk (provenance/a5-catalog/identity-crosswalk.json)"})
            else:
                problems.append(f"{code}: {label} {value!r} at {source} differs from canonical {canonical!r} and is not in the reviewed crosswalk")

        compare("fitted ledger mpn", f"engineering/a5/{LEDGER}", row["mpn"])
        compare("procurement mpn", f"engineering/a5/{PROCUREMENT}", proc.get("mpn", ""))

        snapshots = find_identity_snapshot(inputs, code)
        for snap in snapshots:
            if snap["componentCode"] != code:
                problems.append(f"{code}: snapshot {snap['path']} carries componentCode {snap['componentCode']}")
            compare("A5 JLCPCB snapshot componentModelEn", snap["path"], snap["componentModelEn"])
            if snap["componentBrandEn"] != proc.get("manufacturer"):
                problems.append(f"{code}: snapshot brand {snap['componentBrandEn']!r} differs from procurement manufacturer {proc.get('manufacturer')!r}")
        refresh = A5 / "evidence_refresh" / f"{code}.json"
        if refresh.is_file():
            compare("A5 evidence_refresh mpn", rel(refresh), inputs.json(refresh).get("mpn", ""))

        listing = listings.get(code)
        lcsc_obs = None
        if listing is None:
            problems.append(f"{code}: no LCSC listing observation")
        else:
            product = listing["jsonld_product"]
            if product["sku"] != code:
                problems.append(f"{code}: LCSC listing sku {product['sku']}")
            compare("LCSC listing JSON-LD mpn", rel(LCSC_LISTINGS), product["mpn"])
            lcsc_obs = {"sku": product["sku"], "mpn": product["mpn"], "brand": product["brand"], "html_sha256": listing["html_sha256"]}

        placements = []
        for inst in row["instances"]:
            board = inst["board"]
            comp = netlists.get(board, {}).get(inst["ref"])
            if comp is None:
                problems.append(f"{code}: ledger placement {board}/{inst['ref']} missing from netlist")
                continue
            netlist_refs_seen[board].add(inst["ref"])
            if comp["lcsc"] != code:
                problems.append(f"{code}: {board}/{inst['ref']} netlist LCSC {comp['lcsc']!r}")
            compare(f"netlist {board}/{inst['ref']} MPN", f"engineering/a5/{NETLISTS[board]}", comp["mpn"])
            if inst["board_copies"] != EXPECTED["board_copies"][board]:
                problems.append(f"{code}: {board}/{inst['ref']} board_copies {inst['board_copies']} != {EXPECTED['board_copies'][board]}")
            placements.append({
                "board": board, "refdes": inst["ref"], "board_copies": inst["board_copies"],
                "value": comp["value"], "footprint": comp["footprint"], "symbol": comp["symbol"],
                "pins": comp["pins"],
            })
        pieces = sum(p["board_copies"] for p in placements)
        if pieces != row["quantity_per_module"]:
            problems.append(f"{code}: placements x copies = {pieces} but ledger quantity_per_module = {row['quantity_per_module']}")
        if proc.get("qty_per_module") != row["quantity_per_module"]:
            problems.append(f"{code}: procurement qty_per_module {proc.get('qty_per_module')} != ledger {row['quantity_per_module']}")
        footprints = sorted({p["footprint"] for p in placements})
        symbols = sorted({p["symbol"] for p in placements})
        if len(symbols) != 1:
            problems.append(f"{code}: placements use more than one symbol {symbols}")
        identities.append({
            "lcsc": code,
            "manufacturer": proc.get("manufacturer", ""),
            "mpn": canonical,
            "package": proc.get("package", ""),
            "role_ja": proc.get("role_ja", ""),
            "function": line.get("function", ""),
            "owner_skill": line.get("owner_skill", ""),
            "line_id": line.get("line_id", ""),
            "record_id": line.get("record_id", ""),
            "supplier_url": proc.get("url", ""),
            "identity_snapshots": snapshots,
            "lcsc_listing": lcsc_obs,
            "spelling_discrepancies": discrepancies,
            "footprints": footprints,
            "symbol": symbols[0] if symbols else "",
            "unique_placements": len(placements),
            "physical_pieces": pieces,
            "placements": placements,
        })

    exclusions = []
    for board, comps in netlists.items():
        for ref, comp in sorted(comps.items()):
            if ref in netlist_refs_seen[board]:
                continue
            if comp["lcsc"] or comp["mpn"]:
                problems.append(f"netlist {board}/{ref} carries an orderable identity ({comp['lcsc']}/{comp['mpn']}) absent from the fitted ledger")
            exclusions.append({"board": board, "refdes": ref, "footprint": comp["footprint"], "reason": "bare-copper test pad: no orderable identity (MPN/LCSC fields empty); not a fitted piece"})

    by_board = Counter(p["board"] for ident in identities for p in ident["placements"])
    totals = {
        "identities": len(identities),
        "unique_placements": sum(i["unique_placements"] for i in identities),
        "unique_placements_by_board": {board: by_board.get(board, 0) for board in BOARDS},
        "physical_pieces": sum(i["physical_pieces"] for i in identities),
        "board_copies": EXPECTED["board_copies"],
    }
    for key, want in EXPECTED.items():
        if totals[key] != want:
            problems.append(f"totals: {key} = {totals[key]} but the contract expects {want}")
    if ledger.get("mpn_types") != EXPECTED["identities"] or ledger.get("fitted_pieces_per_module") != EXPECTED["physical_pieces"]:
        problems.append("fitted ledger header counts differ from the contract")
    summary = procurement.get("summary", {})
    if summary.get("unique_jlc_mpn_count") != EXPECTED["identities"] or summary.get("fitted_parts_per_module") != EXPECTED["physical_pieces"]:
        problems.append("procurement summary counts differ from the contract")
    fitted_mpns = {i["mpn"] for i in identities}
    for code, mpn in REQUIRED_FITTED.items():
        if not any(i["lcsc"] == code and i["mpn"] == mpn for i in identities):
            problems.append(f"required fitted identity {code}/{mpn} missing")
    for mpn in FORBIDDEN_FITTED_MPNS:
        if mpn in fitted_mpns:
            problems.append(f"alternative identity {mpn} appears as fitted")
    for code in alternatives:
        if code in {i["lcsc"] for i in identities}:
            problems.append(f"procurement alternative {code} appears as fitted")

    snapshot_codes = sorted({p.name.split(".")[0] for d in IDENTITY_SNAPSHOT_DIRS + ("evidence_refresh",) for p in (A5 / d).glob("C*.json")})
    not_fitted = sorted(set(snapshot_codes) - set(codes))
    report = {
        "schema_version": 1,
        "generated_by": "scripts/a5_catalog.py reconcile",
        "scope": "Historical A5 design evidence only. Placements, nets and pin assignments are read from the immutable A5 native netlists (KiCad 10.0.8 export, 2026-11-06) listed under inputs with their hashes. This is not fresh A6 design state, not a placement binding performed by the inventory provider, and not physical verification.",
        "inputs": [{"path": path, "sha256": digest} for path, digest in sorted(inputs.hashes.items())],
        "totals": totals,
        "excluded_from_counts": {
            "netlist_items_without_identity": exclusions,
            "external_items_not_on_pcb": external,
            "procurement_alternatives_not_fitted": alternatives,
            "evidence_snapshot_codes_not_fitted": not_fitted,
            "note": "Mounting holes, test pads, external cables/panels/enclosure items, historical alternatives and rejected candidates are not fitted orderable identities and are never counted.",
        },
        "identities": identities,
        "spelling_crosswalk_applied": [d for i in identities for d in [{"lcsc": i["lcsc"], **x} for x in i["spelling_discrepancies"]]],
    }
    return report, problems


def dump(data) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def cmd_reconcile(args) -> int:
    report, problems = build_reconciliation()
    for problem in problems:
        print(f"FAIL: {problem}", file=sys.stderr)
    text = dump(report)
    if args.check:
        current = RECONCILIATION.read_text(encoding="utf-8") if RECONCILIATION.is_file() else None
        if current != text:
            print(f"FAIL: {rel(RECONCILIATION)} is missing or stale; run `python3 scripts/a5_catalog.py reconcile`", file=sys.stderr)
            return 1
    elif not problems:
        RECONCILIATION.write_text(text, encoding="utf-8")
    t = report["totals"]
    status = "FAIL" if problems else "PASS"
    print(f"{status}: reconciliation {t['identities']} identities, {t['unique_placements']} unique placements "
          f"{t['unique_placements_by_board']}, {t['physical_pieces']} physical pieces; "
          f"{len(report['spelling_crosswalk_applied'])} reviewed spelling discrepancies; "
          f"{len(report['excluded_from_counts']['netlist_items_without_identity'])} netlist items excluded")
    return 1 if problems else 0


# --- scaffold -------------------------------------------------------------------------------

BASE_COMMIT = "d41cbb7fc61dc954b4affaf19527aa69f07013b6"  # main when the A5 netlists were first catalogued
REPO_BLOB = f"https://github.com/Takazudo/zudo-led-block/blob/{BASE_COMMIT}/"
PIN_MAP_REVIEW = "not independently reviewed: projected from the A5 native netlist by scripts/a5_catalog.py scaffold"
# Negative routing probes: a bare family/base name or a named alternative that must never resolve.
NEGATIVE_PROBES = {
    "C52917434": "check WS2812B-MINI-V6 pinout", "C140331": "check TPS2553DBVR-1 pinout",
    "C398363": "check TLV9061IDBVR pinout", "C694586": "check 74437324047 pinout",
}


def suffix_of(identity) -> str:
    return identity["owner_skill"][len("component-"):]


def date_of(stamp: str) -> str:
    return stamp[:10]


def distributor_source(identity, s):
    """The retained distributor observation used for the narrow identity lane."""
    code = identity["lcsc"]
    variant = identity["package"]
    value = {"lcsc": code, "manufacturer": identity["manufacturer"], "mpn": identity["mpn"], "variant": variant}
    extract_hash = sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())
    snaps = [snap for snap in identity["identity_snapshots"] if snap["componentModelEn"] == identity["mpn"]]
    sources = []
    if snaps:
        snap = snaps[0]
        sources.append({
            "source_id": f"src-{s}-a5-jlcpcb-snapshot",
            "record_id": identity["record_id"],
            "document_title": f"JLCPCB public product listing {code} (A5 retained product-props snapshot)",
            "document_number": code,
            "revision": f"A5 snapshot observed {snap['observed_utc']}",
            "document_date": date_of(snap["observed_utc"]),
            "authoritative_url": snap["url"],
            "alternate_authoritative_url": f"{REPO_BLOB}{snap['path']}",
            "retrieval_date": date_of(snap["observed_utc"]),
            "authority_class": "DISTRIBUTOR_IDENTITY",
            "sha256": snap["sha256"],
            "availability": "AVAILABLE",
            "physical_pdf_page_index": 0,
            "printed_page_label": "n/a (JSON snapshot of an HTML page)",
            "locator": f"{snap['path']}, product table fields componentCode, componentModelEn, componentBrandEn, componentSpecificationEn",
            "evidence_extract": (
                f"componentCode={snap['componentCode']}; componentModelEn={snap['componentModelEn']}; componentBrandEn={snap['componentBrandEn']}; "
                f"componentSpecificationEn={snap['componentSpecificationEn']}. sha256 above is the retained A5 snapshot JSON file (the bytes inspected). "
                f"The original page HTML digest recorded inside that snapshot is {snap['recorded_html_sha256']}; those HTML bytes are not retained and were not re-verified. "
                "Distributor identity only: no electrical, mechanical or availability claim."
            ),
            "refresh_policy": "VOLATILE-HTML",
            "refresh_note": "The listing URL serves live HTML whose bytes are not deterministic; the recorded hash is of the retained A5 snapshot JSON, so an online refresh cannot reproduce it.",
            "identity_extract_sha256": extract_hash,
        })
    else:
        listing = identity["lcsc_listing"]
        sources.append({
            "source_id": f"src-{s}-lcsc-listing",
            "record_id": identity["record_id"],
            "document_title": f"LCSC public product listing {code}",
            "document_number": code,
            "revision": "observed 2026-11-08T00:16Z",
            "document_date": "2026-11-08",
            "authoritative_url": f"https://www.lcsc.com/product-detail/{code}.html",
            "alternate_authoritative_url": "",
            "retrieval_date": "2026-11-08",
            "authority_class": "DISTRIBUTOR_IDENTITY",
            "sha256": listing["html_sha256"],
            "availability": "AVAILABLE",
            "physical_pdf_page_index": 0,
            "printed_page_label": "n/a (HTML page)",
            "locator": "schema.org Product JSON-LD section, fields sku, mpn, brand.name (extract retained in provenance/a5-catalog/lcsc-listings-2026-11-08.json)",
            "evidence_extract": (
                f"sku={listing['sku']}; mpn={listing['mpn']}; brand={listing['brand']}. sha256 above is the HTML bytes inspected on 2026-11-08; "
                "the HTML is not retained, only the JSON-LD extract. Distributor identity only: no electrical, mechanical or availability claim."
            ),
            "refresh_policy": "VOLATILE-HTML",
            "refresh_note": "The listing URL serves live HTML whose bytes are not deterministic; the recorded hash is of the bytes inspected once on 2026-11-08.",
            "identity_extract_sha256": extract_hash,
        })
        for snap in identity["identity_snapshots"]:
            sources.append({
                "source_id": f"src-{s}-a5-jlcpcb-snapshot-{Path(snap['path']).parts[2].replace('_', '-')}",
                "record_id": identity["record_id"],
                "document_title": f"JLCPCB public product listing {code} (A5 retained product-props snapshot, listing-title spelling)",
                "document_number": code,
                "revision": f"A5 snapshot observed {snap['observed_utc'] or 'date not recorded in snapshot'}",
                "document_date": date_of(snap["observed_utc"]) if snap["observed_utc"] else "2026-11-06",
                "authoritative_url": snap["url"] or f"https://jlcpcb.com/partdetail/{code}",
                "alternate_authoritative_url": f"{REPO_BLOB}{snap['path']}",
                "retrieval_date": date_of(snap["observed_utc"]) if snap["observed_utc"] else "2026-11-06",
                "authority_class": "DISTRIBUTOR_IDENTITY",
                "sha256": snap["sha256"],
                "availability": "AVAILABLE",
                "physical_pdf_page_index": 0,
                "printed_page_label": "n/a (JSON snapshot of an HTML page)",
                "locator": f"{snap['path']}, product table fields componentCode, componentModelEn, componentBrandEn",
                "evidence_extract": (
                    f"componentCode={snap['componentCode']}; componentModelEn={snap['componentModelEn']}; componentBrandEn={snap['componentBrandEn']}. "
                    "This listing-title spelling differs from the canonical MPN; the reviewed mapping is in provenance/a5-catalog/identity-crosswalk.json. "
                    f"sha256 above is the retained snapshot JSON; the HTML digest recorded inside it ({snap['recorded_html_sha256'] or 'none recorded'}) was not re-verified."
                ),
            })
    return sources, value


def netlist_sources(identity, s, inputs_by_path):
    sources = []
    for board in sorted({p["board"] for p in identity["placements"]}):
        path = f"engineering/a5/{NETLISTS[board]}"
        sources.append({
            "source_id": f"src-{s}-a5-netlist-{board.replace('_', '-')}",
            "record_id": identity["record_id"],
            "document_title": f"Light Block A5 {board} native netlist (KiCad 10.0.8 export, historical)",
            "document_number": path,
            "revision": "A5",
            "document_date": "2026-11-06",
            "authoritative_url": f"{REPO_BLOB}{path}",
            "alternate_authoritative_url": "",
            "retrieval_date": "2026-11-06",
            "authority_class": "PROJECT_GENERATOR",
            "sha256": inputs_by_path[path],
            "availability": "AVAILABLE",
            "physical_pdf_page_index": 0,
            "printed_page_label": "n/a (XML netlist)",
            "locator": f"{path}, components section rows for {', '.join(p['refdes'] for p in identity['placements'] if p['board'] == board)} and the matching nets section nodes",
            "evidence_extract": "; ".join(
                f"{p['refdes']}: value={p['value']}, footprint={p['footprint']}, symbol={p['symbol']}, "
                + ", ".join(f"pin {pin['num']} {pin['name']}={pin['net'] or 'unconnected'}" for pin in p["pins"])
                for p in identity["placements"] if p["board"] == board
            ) + ". Historical A5 design state only; not fresh A6 state and not as-built verification.",
        })
    return sources


def build_bundle(identity, inputs_by_path):
    s = suffix_of(identity)
    rid = identity["record_id"]
    dist_sources, identity_value = distributor_source(identity, s)
    net_sources = netlist_sources(identity, s, inputs_by_path)
    dist_id = dist_sources[0]["source_id"]
    first_net = net_sources[0]["source_id"]
    placements_text = ", ".join(f"{p['board']}/{p['refdes']} x{p['board_copies']}" for p in identity["placements"])
    facts = [
        {
            "fact_id": f"fact-{s}-manufacturer", "record_id": rid, "source_id": dist_id, "class": "PROJECT_STATE",
            "value": identity["manufacturer"], "unit": "NONE",
            "conditions": "exact orderable identity; distributor listing only, no manufacturer-primary document inspected yet",
            "locator": f"{dist_id}: product table row brand", "provenance": "UNVERIFIED", "verdict": "UNSOURCED",
            "depends_on": [], "expression": "",
        },
        {
            "fact_id": f"fact-{s}-distributor-identity", "record_id": rid, "source_id": dist_id, "class": "PROJECT_STATE",
            "value": identity_value, "unit": "NONE", "conditions": "order-code identity only; not performance evidence",
            "locator": f"{dist_id}: product table rows code, model, brand, specification", "provenance": "DISTRIBUTOR-IDENTITY",
            "verdict": "CONFIRMED - distributor identity only", "depends_on": [], "expression": "",
        },
        {
            "fact_id": f"fact-{s}-a5-placements", "record_id": rid, "source_id": first_net, "class": "PROJECT_STATE",
            "value": f"{placements_text} ({identity['unique_placements']} unique placements, {identity['physical_pieces']} fitted pieces per module)",
            "unit": "NONE",
            "conditions": "historical A5 native netlists; declared by the manual inventory provider, not bound to a schematic; as-built placement unverified",
            "locator": f"{first_net}: components section rows {', '.join(p['refdes'] for p in identity['placements'])}",
            "provenance": "PROJECT-CHOICE", "verdict": "NEEDS BENCH", "depends_on": [], "expression": "",
        },
        {
            "fact_id": f"fact-{s}-pinout", "record_id": rid, "source_id": first_net, "class": "PROJECT_STATE",
            "value": f"manufacturer pin numbering and pin functions for package {identity['package']}", "unit": "NONE",
            "conditions": "datasheet pin identity behind the project pin map; no manufacturer document inspected yet",
            "locator": f"{first_net}: libparts section pin rows for {identity['symbol']}",
            "provenance": "UNVERIFIED", "verdict": "UNSOURCED", "depends_on": [], "expression": "",
        },
        {
            "fact_id": f"fact-{s}-ratings", "record_id": rid, "source_id": dist_id, "class": "ABSOLUTE_MAXIMUM",
            "value": "manufacturer absolute-maximum and recommended operating limits", "unit": "NONE",
            "conditions": "no manufacturer document inspected yet; distributor listing is identity evidence only",
            "locator": f"{dist_id}: product table row specification (identity only)",
            "provenance": "UNVERIFIED", "verdict": "UNSOURCED", "depends_on": [], "expression": "",
        },
        {
            "fact_id": f"fact-{s}-cad-state", "record_id": rid, "source_id": first_net, "class": "PROJECT_STATE",
            "value": f"A5 footprint {', '.join(identity['footprints'])} and symbol {identity['symbol']} are not configured as catalog CAD assets (cad.enabled=false); pin-asset check not performed",
            "unit": "NONE", "conditions": "catalog CAD disabled for this batch; no footprint, model or receipt reviewed",
            "locator": f"{first_net}: components section footprint field", "provenance": "PROJECT-CHOICE", "verdict": "UNSOURCED",
            "depends_on": [], "expression": "",
        },
    ]
    coverage = [
        {"coverage_id": f"cov-{s}-identity", "record_id": rid, "domain": "identity", "status": "OPEN",
         "reason": f"fact-{s}-manufacturer remains UNSOURCED: only distributor identity is retained; no manufacturer-primary document inspected",
         "fact_ids": [f"fact-{s}-manufacturer", f"fact-{s}-distributor-identity"], "blocking_fact_ids": [f"fact-{s}-manufacturer"]},
        {"coverage_id": f"cov-{s}-pinout", "record_id": rid, "domain": "pinout", "status": "OPEN",
         "reason": f"fact-{s}-pinout remains UNSOURCED: the pin map is projected from the historical A5 netlist and has not been checked against a manufacturer document",
         "fact_ids": [f"fact-{s}-pinout"], "blocking_fact_ids": [f"fact-{s}-pinout"]},
        {"coverage_id": f"cov-{s}-ratings", "record_id": rid, "domain": "electrical-ratings", "status": "OPEN",
         "reason": f"fact-{s}-ratings remains UNSOURCED: no manufacturer limits retained",
         "fact_ids": [f"fact-{s}-ratings"], "blocking_fact_ids": [f"fact-{s}-ratings"]},
        {"coverage_id": f"cov-{s}-placement", "record_id": rid, "domain": "placement", "status": "OPEN",
         "reason": f"fact-{s}-a5-placements NEEDS BENCH: placements are declared from the historical A5 netlist only; the manual provider performs no schematic binding and no as-built check exists",
         "fact_ids": [f"fact-{s}-a5-placements"], "blocking_fact_ids": [f"fact-{s}-a5-placements"]},
        {"coverage_id": f"cov-{s}-cad", "record_id": rid, "domain": "cad-assets", "status": "OPEN",
         "reason": f"fact-{s}-cad-state remains UNSOURCED: catalog CAD is disabled, so no symbol, footprint or model was reviewed or validated",
         "fact_ids": [f"fact-{s}-cad-state"], "blocking_fact_ids": [f"fact-{s}-cad-state"]},
    ]
    sources = dist_sources + net_sources
    first = identity["placements"][0]
    pins = []
    for pin in first["pins"]:
        nets = "; ".join(
            f"{p['board']}/{p['refdes']}={next(x['net'] for x in p['pins'] if x['num'] == pin['num']) or 'unconnected'}"
            for p in identity["placements"]
        )
        pins.append({"symbol_pin": pin["num"], "name": pin["name"], "footprint_pad": pin["num"], "function": f"{pin['type']}; A5 nets: {nets}"})
    pin_map = {
        "pin_map_id": f"pinmap-{s}", "record_id": rid, "symbol": identity["symbol"], "footprint": first["footprint"],
        "pins": pins, "reviewed_by": PIN_MAP_REVIEW,
        "project_state_source": f"historical A5 native netlists ({', '.join(x['source_id'] for x in net_sources)}); pad numbers equal KiCad symbol pin numbers in that export",
    }
    record = {
        "record_id": rid, "line_id": identity["line_id"], "kind": "standalone", "parent_record_id": None,
        "mpn": identity["mpn"], "manufacturer": identity["manufacturer"], "lcsc": identity["lcsc"], "package": identity["package"],
        "source_ids": [x["source_id"] for x in sources], "fact_ids": [f["fact_id"] for f in facts], "interaction_ids": [],
        "open_domains": [c["domain"] for c in coverage],
    }
    mpn = identity["mpn"]
    route = {
        "route_id": f"route-{s}", "record_id": rid,
        "aliases": {"mpn": [mpn], "lcsc": [identity["lcsc"]], "manufacturer": [identity["manufacturer"]], "function": [identity["function"]]},
        "positive": [f"check {mpn} pinout", f"audit {identity['lcsc']}"],
        "negative": [NEGATIVE_PROBES.get(identity["lcsc"], f"check {identity['function']} from an unnamed vendor")],
    }
    skill = f"""---
name: {identity['owner_skill']}
description: Resolve exact {identity['manufacturer']} {mpn} ({identity['lcsc']}, {identity['package']}) evidence for the Zudo LED Block A5 {identity['function']}. Use whenever {mpn}, {identity['lcsc']}, its pins, package, placements ({placements_text}), limits, substitution or bring-up are relevant.
---

# Exact component record: {mpn}

Run `pnpm circuit:check`, read every JSON file in this bundle, and cite fact and source IDs
with their conditions and locators. Preserve `SOURCE UNAVAILABLE`, `UNSOURCED`, `NEEDS BENCH`
and every `OPEN` domain; never replace exact-orderable evidence with memory, a family
datasheet of another variant or same-name vendor data.

- Identity was reconciled by `scripts/a5_catalog.py reconcile`
  (`provenance/a5-catalog/reconciliation.json`). Distributor listings are identity evidence only.
- The pin map and placements are projected from the immutable historical A5 native netlists
  (`engineering/a5/integration/native_schematic/`). They are not fresh A6 design state, are not
  bound by the manual inventory provider, and are not as-built verification.
- Catalog CAD is disabled (`cad.enabled = false`); the pin-asset check is SKIPPED.
- A5 is not released for manufacture. Nothing here is hardware or manufacturing sign-off.

## Human component reference

Human projection of this bundle: [{rid}](/docs/components/records/{rid[len('rec-'):]}/).
See also the [component catalog](/docs/components/catalog/) and
[cross-component rules](/docs/components/integration/). These pages are generated from this
bundle's JSON files and add nothing to them.
"""
    return {
        "manifest.json": {"schema_version": 1, "skill": identity["owner_skill"], "records": [record]},
        "sources.json": {"schema_version": 1, "sources": sources},
        "facts.json": {"schema_version": 1, "facts": facts},
        "coverage.json": {"schema_version": 1, "coverage": coverage},
        "routing.json": {"schema_version": 1, "routes": [route]},
        "interactions.json": {"schema_version": 1, "interactions": []},
        "pin-map.json": {"schema_version": 1, "pin_maps": [pin_map]},
        "SKILL.md": skill,
    }


def write_bundle(directory: Path, files):
    directory.mkdir(parents=True)
    for name, content in files.items():
        text = content if isinstance(content, str) else json.dumps(content, indent=2, ensure_ascii=False) + "\n"
        (directory / name).write_text(text, encoding="utf-8")


def cmd_scaffold(args) -> int:
    report = load_json(RECONCILIATION)
    inputs_by_path = {item["path"]: item["sha256"] for item in report["inputs"]}
    by_code = {i["lcsc"]: i for i in report["identities"]}
    codes = sorted(by_code) if args.all else args.codes
    unknown = [code for code in codes if code not in by_code]
    if unknown:
        print(f"FAIL: not fitted A5 identities: {unknown}", file=sys.stderr)
        return 2
    for code in codes:
        identity = by_code[code]
        directory = SKILLS / identity["owner_skill"]
        if directory.exists():
            print(f"SKIP: {rel(directory)} exists (bundles are hand-maintained after scaffolding)")
            continue
        write_bundle(directory, build_bundle(identity, inputs_by_path))
        print(f"created {rel(directory)}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("reconcile")
    p.add_argument("--check", action="store_true")
    p.set_defaults(func=cmd_reconcile)
    p = sub.add_parser("scaffold")
    p.add_argument("codes", nargs="*")
    p.add_argument("--all", action="store_true")
    p.set_defaults(func=cmd_scaffold)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
