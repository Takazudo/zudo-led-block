#!/usr/bin/env python3
"""Mutation tests for scripts/a5_catalog.py: each seeded defect must be reported.

Run: python3 -m unittest scripts/test_a5_catalog.py  (stdlib only; never writes to engineering/a5/)
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a5_catalog as cat  # noqa: E402

REAL_ROOT = cat.ROOT
A5_INPUTS = ("electronics/fitted_component_ledger.json", "procurement_rows.json", "integration/native_schematic",
             "ic_led_evidence", "passive_evidence", "mechanical_evidence", "integration/evidence", "evidence_refresh")


class ReconcileMutations(unittest.TestCase):
    """build_reconciliation() against a temporary copy of its inputs."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="a5-catalog-test-"))
        for item in A5_INPUTS:
            src = REAL_ROOT / "engineering" / "a5" / item
            dst = self.tmp / "engineering" / "a5" / item
            dst.parent.mkdir(parents=True, exist_ok=True)
            (shutil.copytree if src.is_dir() else shutil.copy2)(src, dst)
        shutil.copytree(REAL_ROOT / "provenance" / "a5-catalog", self.tmp / "provenance" / "a5-catalog")
        prov = self.tmp / "provenance" / "a5-catalog"
        self.patch = mock.patch.multiple(
            cat, ROOT=self.tmp, A5=self.tmp / "engineering" / "a5", CATALOG_PROV=prov,
            CROSSWALK=prov / "identity-crosswalk.json", LCSC_LISTINGS=prov / "lcsc-listings-2026-11-08.json",
            RECONCILIATION=prov / "reconciliation.json",
        )
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        shutil.rmtree(self.tmp)

    def edit(self, relpath, fn):
        path = self.tmp / relpath
        data = json.loads(path.read_text(encoding="utf-8"))
        fn(data)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def problems(self):
        return "\n".join(cat.build_reconciliation()[1])

    def test_baseline_is_clean_and_counts_hold(self):
        report, problems = cat.build_reconciliation()
        self.assertEqual(problems, [])
        self.assertEqual(report["totals"]["identities"], 30)
        self.assertEqual(report["totals"]["unique_placements"], 71)
        self.assertEqual(report["totals"]["unique_placements_by_board"], {"controller": 59, "led_leaf": 10, "power_adapter": 2})
        self.assertEqual(report["totals"]["physical_pieces"], 81)
        self.assertEqual(len(report["excluded_from_counts"]["netlist_items_without_identity"]), 5)

    def test_committed_reconciliation_is_current(self):
        report, _ = cat.build_reconciliation()
        committed = (REAL_ROOT / "provenance" / "a5-catalog" / "reconciliation.json").read_text(encoding="utf-8")
        # The temp copy hashes the same bytes, so the deterministic output must match byte for byte.
        self.assertEqual(cat.dump(report), committed)

    def test_unreviewed_c5665_spelling_fails(self):
        self.edit("provenance/a5-catalog/identity-crosswalk.json", lambda d: d.update(spelling_crosswalk=[]))
        self.assertIn("C5665", self.problems())
        self.assertIn("not in the reviewed crosswalk", self.problems())

    def test_crosswalk_spelling_only_valid_for_named_sources(self):
        def drop_procurement(d):
            for item in d["spelling_crosswalk"][0]["observed_spellings"]:
                item["sources"] = [s for s in item["sources"] if s != "engineering/a5/procurement_rows.json"]
        self.edit("provenance/a5-catalog/identity-crosswalk.json", drop_procurement)
        self.assertIn("procurement mpn", self.problems())

    def test_alternative_led_as_fitted_fails(self):
        def swap(d):
            for c in d["components"]:
                if c["c_code"] == "C52917434":
                    c["mpn"] = "WS2812B-MINI-V6"
        self.edit("engineering/a5/electronics/fitted_component_ledger.json", swap)
        out = self.problems()
        self.assertIn("C52917434", out)

    def test_duplicate_fitted_identity_fails(self):
        self.edit("engineering/a5/electronics/fitted_component_ledger.json", lambda d: d["components"].append(d["components"][0]))
        self.assertIn("duplicate C-codes", self.problems())

    def test_missing_identity_fails(self):
        self.edit("engineering/a5/electronics/fitted_component_ledger.json", lambda d: d.update(components=d["components"][1:]))
        out = self.problems()
        self.assertIn("identity sets differ", out)
        self.assertIn("identities = 29", out)

    def test_leaf_multiplier_change_fails(self):
        def single_leaf(d):
            for c in d["components"]:
                for inst in c["instances"]:
                    if inst["board"] == "led_leaf":
                        inst["board_copies"] = 1
        self.edit("engineering/a5/electronics/fitted_component_ledger.json", single_leaf)
        out = self.problems()
        self.assertIn("board_copies 1 != 2", out)
        self.assertIn("physical_pieces = 71", out)

    def test_manufacturer_mapping_change_fails(self):
        def rebrand(d):
            for c in d["components"]:
                if c["c_code"] == "C140331":
                    c["manufacturer"] = "Texas Instrument"
        self.edit("engineering/a5/procurement_rows.json", rebrand)
        self.assertIn("C140331: snapshot brand", self.problems())

    def test_supplier_code_mismatch_in_netlist_fails(self):
        path = self.tmp / "engineering/a5/integration/native_schematic/controller/netlist.xml"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace('<field name="LCSC">C140331</field>', '<field name="LCSC">C140330</field>', 1), encoding="utf-8")
        self.assertIn("C140331: controller/U4 netlist LCSC", self.problems())

    def test_lcsc_listing_mpn_drift_fails(self):
        self.edit("provenance/a5-catalog/lcsc-listings-2026-11-08.json",
                  lambda d: d["listings"]["C140331"]["jsonld_product"].update(mpn="TPS2553DBVR-1"))
        self.assertIn("LCSC listing JSON-LD mpn", self.problems())


class CatalogMutations(unittest.TestCase):
    """catalog_problems() against a temporary copy of the owner bundles and catalog index files."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="a5-catalog-skills-"))
        shutil.copytree(REAL_ROOT / ".claude" / "skills", self.tmp / "skills")
        shutil.copy2(REAL_ROOT / "circuit" / "publication" / "selection.json", self.tmp / "selection.json")
        skills = self.tmp / "skills"
        refs = skills / "component-spec-audit" / "references"
        self.patch = mock.patch.multiple(cat, SKILLS=skills, INVENTORY=refs / "inventory.json",
                                         DIRECT_ROUTING=refs / "direct-routing.json", SELECTION=self.tmp / "selection.json")
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        shutil.rmtree(self.tmp)

    def edit(self, path, fn):
        data = json.loads(path.read_text(encoding="utf-8"))
        fn(data)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def problems(self):
        return "\n".join(cat.catalog_problems()[0])

    def test_baseline_is_clean(self):
        self.assertEqual(cat.catalog_problems()[0], [])

    def test_missing_inventory_line_fails(self):
        self.edit(cat.INVENTORY, lambda d: d.update(lines=d["lines"][1:]))
        self.assertIn("inventory: missing fitted identity", self.problems())

    def test_alternative_inventory_line_fails(self):
        def add_alt(d):
            line = dict(d["lines"][0], line_id="line-alt", lcsc="C2651179", mpn="74437324047")
            d["lines"].append(line)
        self.edit(cat.INVENTORY, add_alt)
        self.assertIn("C2651179", self.problems())

    def test_tampered_pin_map_net_fails(self):
        path = cat.SKILLS / "component-tps2552dbvr-1" / "pin-map.json"
        self.edit(path, lambda d: d["pin_maps"][0]["pins"][0].update(function="power_in; A5 nets: controller/U4=/WRONG"))
        self.assertIn("pin map differs from the A5 netlist projection", self.problems())

    def test_placement_promoted_from_needs_bench_fails(self):
        path = cat.SKILLS / "component-tps2552dbvr-1" / "facts.json"
        def promote(d):
            for f in d["facts"]:
                if f["fact_id"].endswith("-a5-placements"):
                    f["verdict"] = "NOT APPLICABLE"
        self.edit(path, promote)
        self.assertIn("must stay NEEDS BENCH", self.problems())

    def test_unexpected_bundle_fails(self):
        shutil.copytree(cat.SKILLS / "component-tps2552dbvr-1", cat.SKILLS / "component-tps2553dbvr-1")
        self.assertIn("component-tps2553dbvr-1: not a reconciled fitted identity", self.problems())

    def add_later_revision_line(self, owner):
        shutil.copytree(cat.SKILLS / "component-tps2552dbvr-1", cat.SKILLS / owner)
        def add(d):
            line = dict(d["lines"][0], line_id="line-a7-tps2552dbvr-1", owner_skill=owner, placements=[{"board": "a7_controller", "refdes": "U4"}])
            d["lines"].append(line)
            d["assertions"]["orderable_lines"] += 1
            d["assertions"]["fitted_lines"] += 1
            d["assertions"]["fitted_placements"] += 1
        self.edit(cat.INVENTORY, add)
        self.edit(cat.DIRECT_ROUTING, lambda d: d["cases"].append(dict(d["cases"][0], line_id="line-a7-tps2552dbvr-1")))
        cat.SELECTION.write_text(cat.dump(cat.propose_selection(cat.load_json(cat.RECONCILIATION))), encoding="utf-8")

    def test_later_revision_line_is_accepted(self):
        self.add_later_revision_line("component-a7-tps2552dbvr-1")
        self.assertEqual(cat.catalog_problems()[0], [])

    def test_later_revision_line_needs_revision_owner(self):
        self.add_later_revision_line("component-tps2552dbvr-1-a7")
        self.assertIn("must start with component-a7-", self.problems())

    def test_later_revision_line_does_not_relax_a5_counts(self):
        self.add_later_revision_line("component-a7-tps2552dbvr-1")
        self.edit(cat.INVENTORY, lambda d: d.update(lines=[x for x in d["lines"] if x["line_id"] != "line-tps2552dbvr-1"]))
        self.assertIn("inventory: missing fitted identity C140331", self.problems())

    def test_selection_drift_fails(self):
        self.edit(cat.SELECTION, lambda d: d.update(recordIds=d["recordIds"][1:]))
        self.assertIn("differs from the evidence-derived selection", self.problems())


if __name__ == "__main__":
    unittest.main()
