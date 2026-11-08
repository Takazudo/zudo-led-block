"""Focused checks for the A7 R1 evidence bundles and dimension study (stdlib unittest).

Run: python3 -m unittest scripts/tests/test_a7_r1_study.py
"""
import copy
import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
A7 = REPO / "engineering" / "a7"
SKILLS = REPO / ".claude" / "skills"
HEX64 = re.compile(r"[0-9a-f]{64}")


def load_study():
    spec = importlib.util.spec_from_file_location("a7_dimension_study", REPO / "scripts" / "a7_dimension_study.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STUDY = load_study()
PARAMS = json.loads((A7 / "study" / "parameters.json").read_text())


def bundle(name, kind):
    return json.loads((SKILLS / f"component-a7-{name}" / f"{kind}.json").read_text())


class StudyOutputs(unittest.TestCase):
    def test_committed_outputs_are_current(self):
        result = subprocess.run([sys.executable, str(REPO / "scripts" / "a7_dimension_study.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_every_parameter_has_confidence_and_source(self):
        for key, value in PARAMS["parameters"].items():
            self.assertIn(value.get("confidence"), PARAMS["confidence_levels"], key)
            self.assertTrue(value.get("source"), key)

    def test_axis_height_stays_inferred(self):
        axis = PARAMS["parameters"]["jack_axis_height"]
        self.assertEqual(axis["confidence"], "INFERRED")
        self.assertLess(axis["min"], axis["nominal"])
        self.assertGreater(axis["max"], axis["nominal"])
        fact = next(f for f in bundle("pj-324m", "facts")["facts"] if f["fact_id"] == "fact-a7-pj-324m-axis-height")
        self.assertNotEqual(fact["verdict"], "PASS - primary-source confirmed")
        self.assertEqual(fact["provenance"], "UNVERIFIED")

    def test_jack_dimensions_are_labelled_mirror_not_sourced(self):
        for key, value in PARAMS["parameters"].items():
            if value["source"].startswith("fact-a7-pj-324m-"):
                self.assertIn(value["confidence"], ("MIRROR", "INFERRED"), key)

    def test_nut_fit_is_not_assumed(self):
        for nut in PARAMS["nuts"].values():
            self.assertTrue(nut["fit_to_pj_324m"].startswith("UNVERIFIED"))


class TransverseModel(unittest.TestCase):
    def case(self, width="panel_width_2hp", offset=0.0, t=1.6, leads="untrimmed", corner="nominal", band=None):
        return STUDY.transverse_case(PARAMS, width, offset, t, leads, corner, band)

    def test_terminal_projection_is_not_added_to_pcb_thickness(self):
        thin = self.case(t=0.8)["lead_tip_x"]
        thick = self.case(t=1.6)["lead_tip_x"]
        self.assertAlmostEqual(thin, thick)
        seat = 9.8 / 2 - PARAMS["parameters"]["jack_axis_height"]["nominal"]
        self.assertAlmostEqual(thin, seat - PARAMS["parameters"]["jack_terminal_projection"]["nominal"])

    def test_higher_axis_reduces_lead_side_and_grows_body_side(self):
        low = self.case(band=(2.8, 2.8, 2.8), leads="trimmed")["margins"]
        high = self.case(band=(3.2, 3.2, 3.2), leads="trimmed")["margins"]
        self.assertGreater(low["lead_side"], high["lead_side"])
        self.assertLess(low["body_side"], high["body_side"])

    def test_offset_trades_nut_margin_for_lead_margin(self):
        centred = self.case(leads="trimmed", t=1.0)["margins"]
        offset = self.case(leads="trimmed", t=1.0, offset=0.6)["margins"]
        self.assertGreater(offset["lead_side"], centred["lead_side"])
        self.assertLess(offset["nut_front"], centred["nut_front"])
        self.assertLess(offset["body_side"], centred["body_side"])

    def test_three_hp_is_checked_independently_and_passes_on_paper(self):
        summary = STUDY.build()["transverse_summary"]
        self.assertEqual(summary["3hp-centred"]["verdict"], STUDY.FEASIBLE)
        worst = self.case(width="panel_width_3hp", corner="worst")
        self.assertTrue(all(v >= 0 for k, v in worst["margins"].items() if k != "pcb_hole_web"))

    def test_two_hp_is_not_declared_feasible_or_infeasible_from_missing_evidence(self):
        summary = STUDY.build()["transverse_summary"]
        for key, row in summary.items():
            if key.startswith("2hp"):
                self.assertEqual(row["verdict"], STUDY.UNRESOLVED, key)

    def test_classify_marks_best_corner_failures_infeasible(self):
        worst = {"margins": {"a": -1.0}, "lead_long_enough_for_trim": True}
        best = {"margins": {"a": -0.1}, "lead_long_enough_for_trim": True}
        self.assertEqual(STUDY.classify(worst, best, ["a"])[0], STUDY.INFEASIBLE)
        best["margins"]["a"] = 0.1
        self.assertEqual(STUDY.classify(worst, best, ["a"])[0], STUDY.UNRESOLVED)


class AxialModel(unittest.TestCase):
    def test_old_collar_reduces_exposed_thread_to_0_9_nominal(self):
        row = next(r for r in STUDY.axial(PARAMS) if r["option"] == "a5-collar")
        self.assertAlmostEqual(row["cases"]["nominal"]["exposed_thread"], 0.9)

    def test_plain_mount_leaves_1_5_nominal(self):
        row = next(r for r in STUDY.axial(PARAMS) if r["option"] == "plain")
        self.assertAlmostEqual(row["cases"]["nominal"]["exposed_thread"], 1.5)

    def test_engagement_never_exceeds_nut_thickness(self):
        for row in STUDY.axial(PARAMS):
            for case in row["cases"].values():
                self.assertLessEqual(case["engaged"], case["nut_thickness"] + 1e-9)


class EvidenceBundles(unittest.TestCase):
    def test_hashes_are_real_or_zero_sentinel(self):
        for name in ("pj-324m", "pcm13smtr"):
            for source in bundle(name, "sources")["sources"]:
                self.assertRegex(source["sha256"], HEX64)
                if source["availability"] == "SOURCE UNAVAILABLE":
                    self.assertEqual(source["sha256"], "0" * 64)

    def test_jack_pin_functions_are_not_claimed_as_sourced(self):
        facts = {f["fact_id"]: f for f in bundle("pj-324m", "facts")["facts"]}
        self.assertEqual(facts["fact-a7-pj-324m-pin-function"]["verdict"], "UNSOURCED")
        self.assertEqual(facts["fact-a7-pj-324m-pin-function-inference"]["verdict"], "NEEDS BENCH")
        pins = bundle("pj-324m", "pin-map")["pin_maps"][0]["pins"]
        self.assertTrue(all("(inferred)" in pin["name"] for pin in pins))

    def test_switch_positions_keep_the_mode_encoding(self):
        function = next(f for f in bundle("pcm13smtr", "facts")["facts"] if f["fact_id"] == "fact-a7-pcm13smtr-function")["value"]
        pins = {p["symbol_pin"]: p["function"] for p in bundle("pcm13smtr", "pin-map")["pin_maps"][0]["pins"]}
        nets = {"1": "MODE_A", "2": None, "3": "GND", "4": "MODE_B"}
        for pin, net in nets.items():
            self.assertIn(net or "unconnected", pins[pin])
        encoding = {}
        for position, pair in (("POS.1", function["POS.1"]), ("POS.2", function["POS.2"]), ("POS.3", function["POS.3"])):
            grounded = {nets[p] for p in pair.split("-") if nets[p] not in ("GND", None)}
            encoding[position] = (0 if "MODE_A" in grounded else 1, 0 if "MODE_B" in grounded else 1)
        self.assertEqual(encoding, {"POS.1": (0, 1), "POS.2": (1, 1), "POS.3": (1, 0)})

    def test_no_reviewer_or_verified_claims(self):
        for name in ("pj-324m", "pcm13smtr"):
            for pin_map in bundle(name, "pin-map")["pin_maps"]:
                self.assertTrue(pin_map["reviewed_by"].startswith("not independently reviewed"))

    def test_lcsc_hosted_documents_are_mirrors_and_back_no_pass(self):
        for name in ("pj-324m", "pcm13smtr"):
            sources = {s["source_id"]: s for s in bundle(name, "sources")["sources"]}
            for source in sources.values():
                if "datasheet.lcsc.com" in source["authoritative_url"]:
                    self.assertEqual(source["authority_class"], "MANUFACTURER_MIRROR", source["source_id"])
            for fact in bundle(name, "facts")["facts"]:
                if fact["verdict"] == "PASS - primary-source confirmed":
                    source = sources[fact["source_id"]]
                    self.assertEqual((source["authority_class"], source["availability"]), ("MANUFACTURER_PRIMARY", "AVAILABLE"), fact["fact_id"])

    def test_maker_hosted_attempts_stay_visible(self):
        for name, sid in (("pj-324m", "src-a7-pj-324m-sofng-site"), ("pcm13smtr", "src-a7-pcm13smtr-ck-site")):
            source = next(s for s in bundle(name, "sources")["sources"] if s["source_id"] == sid)
            self.assertEqual(source["availability"], "SOURCE UNAVAILABLE")
            self.assertEqual(source["sha256"], "0" * 64)

    def test_every_open_coverage_names_its_blockers(self):
        for name in ("pj-324m", "pcm13smtr"):
            facts = {f["fact_id"]: f for f in bundle(name, "facts")["facts"]}
            for entry in bundle(name, "coverage")["coverage"]:
                blocking = [i for i in entry["fact_ids"] if facts[i]["verdict"] not in ("PASS - primary-source confirmed", "CONFIRMED - distributor identity only")]
                self.assertEqual(entry["blocking_fact_ids"], blocking, entry["coverage_id"])
                self.assertEqual(entry["status"], "OPEN" if blocking else "COVERED", entry["coverage_id"])

    def test_a7_lines_are_registered_outside_the_a5_reconciliation(self):
        inventory = json.loads((SKILLS / "component-spec-audit" / "references" / "inventory.json").read_text())
        lines = {line["line_id"]: line for line in inventory["lines"]}
        for name in ("pj-324m", "pcm13smtr"):
            line = lines[f"line-a7-{name}"]
            self.assertEqual(line["owner_skill"], f"component-a7-{name}")
            self.assertEqual(line["identity_state"], "UNRESOLVED")

if __name__ == "__main__":
    unittest.main()
