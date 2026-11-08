"""Geometry checks for the A7 R2 mechanical layout, front artwork and CAD verification (stdlib unittest).

Run: python3 -m unittest scripts/tests/test_a7_r2_mechanical.py

The layout calculations are re-derived here from the R1 study functions; the committed CAD and
artwork results are checked against the current layout.json (a stale CAD export fails).
CadQuery is not needed.
"""
import copy
import hashlib
import importlib.util
import json
import math
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
A7 = REPO / "engineering" / "a7"
MECH = A7 / "mechanical"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


LAY = load("a7_mechanical_layout", REPO / "scripts" / "a7_mechanical_layout.py")
STUDY = LAY.S
L = json.loads((MECH / "layout.json").read_text())
PARAMS = json.loads((A7 / "study" / "parameters.json").read_text())
P = PARAMS["parameters"]
G5 = json.loads((REPO / "engineering" / "a5" / "mechanical" / "geometry.json").read_text())


class LayoutCurrent(unittest.TestCase):
    def test_outputs_current(self):
        built = LAY.build()
        self.assertEqual(json.dumps(built, indent=2, ensure_ascii=False) + "\n", (MECH / "layout.json").read_text(), "run python3 scripts/a7_mechanical_layout.py")
        self.assertEqual(LAY.report(built), (MECH / "layout.md").read_text())

    def test_inferred_axis_height_stays_inferred(self):
        self.assertEqual(P["jack_axis_height"]["confidence"], "INFERRED")
        for v in L["variants"].values():
            self.assertEqual(v["jack_axis_height_used"]["confidence"], "INFERRED")
            self.assertEqual(v["jack_axis_height_used"]["value"], P["jack_axis_height"]["nominal"])
        self.assertIn("INFERRED", L["status"])


class Candidates(unittest.TestCase):
    def test_selected_rows_match_r1_calculation(self):
        for name, key in (("2hp", "panel_width_2hp"), ("3hp", "panel_width_3hp")):
            s = L["variants"][name]["selection"]
            for case in ("worst", "nominal"):
                m = STUDY.transverse_case(PARAMS, key, s["offset"], s["pcb_thickness"], s["leads"], case)["margins"]
                for k in ("lead_side", "body_side", "nut_front"):
                    self.assertAlmostEqual(m[k], s[case][k], places=6)

    def test_r1_offsets_reproduced_by_sweep(self):
        for row in STUDY.transverse(PARAMS):
            if not row["arrangement"].startswith("2hp") or row["leads"] != "trimmed":
                continue
            sw = [x for x in L["candidates"]["sweep_2hp"] if abs(x["offset"] - row["offset"]) < 1e-9 and x["pcb_thickness"] == row["pcb_thickness"]]
            self.assertEqual(len(sw), 1)
            self.assertEqual(sw[0]["verdict"], row["verdict"])

    def test_2hp_selection_is_rule_optimum(self):
        pref = P["nut_edge_margin_required"]["preferred"]
        ok = [x for x in L["candidates"]["sweep_2hp"] if x["nominal_min"] >= -1e-9 and x["nominal"]["nut_front"] >= pref - 1e-9 and x["lead_long_enough_for_trim"]]
        best = max(ok, key=lambda x: (x["worst_min"], x["nominal_min"], x["pcb_thickness"]))
        sel = L["candidates"]["selected_2hp"]
        self.assertEqual((best["offset"], best["pcb_thickness"]), (sel["offset"], sel["pcb_thickness"]))
        self.assertGreaterEqual(sel["nominal"]["nut_front"], pref - 1e-9)

    def test_2hp_not_declared_infeasible_and_3hp_feasible(self):
        d = L["decision"]
        self.assertEqual(d["primary_verdict"], STUDY.UNRESOLVED)
        self.assertEqual(d["fallback_verdict"], STUDY.FEASIBLE)
        self.assertNotIn("INFEASIBLE", d["primary_verdict"])
        self.assertTrue(all(v >= 0 for v in L["variants"]["2hp"]["selection"]["nominal"].values()))
        self.assertTrue(all(v >= 0 for v in L["variants"]["3hp"]["selection"]["worst"].values()))

    def test_break_even_values_close_their_margin(self):
        sel = L["candidates"]["selected_2hp"]
        setters = {
            "jack_axis_height.max": lambda q, v: q["parameters"]["jack_axis_height"].__setitem__("max", v),
            "jack_axis_height.min": lambda q, v: q["parameters"]["jack_axis_height"].__setitem__("min", v),
            "lead_protrusion_trimmed.max": lambda q, v: q["parameters"]["lead_protrusion_trimmed"].__setitem__("max", v),
            "jack_overall_height.tol": lambda q, v: q["parameters"]["jack_overall_height"].__setitem__("tol", v),
        }
        checked = 0
        for b in L["candidates"]["break_even_2hp"]:
            key = b["input"].split()[0]
            if not b["closes_within_search"] or key not in setters:
                continue
            q = copy.deepcopy(PARAMS)
            setters[key](q, b["break_even_value"])
            m = STUDY.transverse_case(q, sel["width_key"], sel["offset"], sel["pcb_thickness"], sel["leads"], "worst")["margins"][b["margin"]]
            self.assertAlmostEqual(m, 0.0, delta=0.002)
            checked += 1
        self.assertGreaterEqual(checked, 3)


class Stack(unittest.TestCase):
    def test_depth_stack(self):
        z = L["z_stack"]
        o = z["optical_stack"]
        self.assertAlmostEqual(z["optical_depth_required"], o["cap_behind_leaf"] + o["leaf_depth"] + o["front_allowance_skin_to_leaf"], places=6)
        self.assertAlmostEqual(z["optical_volume_z"][0], G5["optical"]["skin_z"][0], places=6)
        self.assertLessEqual(z["optical_volume_z"][1], z["installed_depth_target"])
        self.assertGreaterEqual(z["controller_pcb_z"][1], z["controller_rear_edge_minimum_from_jack"])
        self.assertLess(z["controller_pcb_z"][1], z["optical_volume_z"][0])
        self.assertLess(z["controller_pcb_z"][1], G5["leaf"]["z"][0])
        self.assertGreater(z["controller_pcb_z"][0], 0)
        self.assertGreaterEqual(z["thread_engagement_selected"]["worst_engaged"], P["min_engagement_required"]["nominal"])

    def test_y_layout(self):
        y, sw = L["y_layout"], L["switch"]
        self.assertEqual(sw["actuator_y"][1], G5["rail_body_y"][1])
        self.assertGreaterEqual(sw["gap_to_lower_jack_body"], 0.5 - 1e-9)
        (a0, a1), (b0, b1) = y["jack_body_y"]
        self.assertGreater(b0, a1)
        self.assertGreaterEqual(a0, L["supports"]["spine"]["slot_y"][1])
        self.assertGreaterEqual(min(y["jack_y"]) - 6.1, L["controller"]["outline_y"][0])
        self.assertGreaterEqual(y["pitch"], 14.0)
        for i, q in enumerate(y["labels"]):
            top, bot = q["y"] - q["cap_height"] / 2, q["y"] + q["cap_height"] / 2
            for yb in y["jack_body_y"]:
                self.assertTrue(bot < yb[0] - 0.2 or top > yb[1] + 0.2, (q, yb))
        self.assertEqual([q["text"] for q in y["labels"]], ["IN", "THRU"])

    def test_x_checks_both_widths(self):
        for name, v in L["variants"].items():
            c = v["checks"]
            self.assertTrue(c["pcb_x_within_inner"], name)
            self.assertTrue(c["component_reserve_fits"], name)
            self.assertTrue(c["sh4_fits"], name)
            self.assertTrue(c["fork_wall_fits_solder_side"], name)
            self.assertGreater(c["spine_screw_nut_clear_of_pcb"], 0, name)
            self.assertGreater(c["spine_screw_nut_clear_of_side"], 0, name)
            self.assertGreaterEqual(c["lead_side_nominal_margin"], 0, name)
            self.assertGreaterEqual(c["body_side_nominal_margin"], 0, name)
            x0, x1 = v["controller_pcb_x"]
            self.assertAlmostEqual(x1 - x0, v["pcb_thickness"], places=6)
            self.assertAlmostEqual(x1, v["x_axis"] - P["jack_axis_height"]["nominal"], places=6)

    def test_keepouts_inside_outline(self):
        c = L["controller"]
        for k in c["keepouts"]:
            self.assertGreaterEqual(k["y"][0], c["outline_y"][0] - 1e-9, k["id"])
            self.assertLessEqual(k["y"][1], c["outline_y"][1] + 1e-9, k["id"])
            self.assertGreaterEqual(k["z"][0], c["outline_z"][0] - 1e-9, k["id"])
            self.assertLessEqual(k["z"][1], c["outline_z"][1] + 1e-9, k["id"])


class Routes(unittest.TestCase):
    def test_fillet_path_right_angle(self):
        segs, length, rmin = LAY.fillet_path([[0, 0, 0], [10, 0, 0], [10, 10, 0]], 2.0)
        self.assertAlmostEqual(length, 8 + 8 + math.pi, places=9)
        self.assertAlmostEqual(rmin, 2.0, places=9)
        self.assertEqual([s[0] for s in segs], ["line", "arc", "line"])

    def test_route_lengths(self):
        for name, v in L["variants"].items():
            sh = v["routes"]["controller_to_left_leaf_sh4"]
            self.assertAlmostEqual(LAY.fillet_path(sh["points"], sh["radius"])[1], sh["length"], places=2)
            self.assertAlmostEqual(sh["length"], 50.0, delta=0.01)
            pw = v["routes"]["adapter_to_controller_power"]
            self.assertAlmostEqual(LAY.fillet_path(pw["points"], pw["radius"])[1], pw["length"], places=2)
            self.assertTrue(pw["within_finished_tolerance"], name)


class Exports(unittest.TestCase):
    def test_cad_verification_current_and_clean(self):
        sha = hashlib.sha256((MECH / "layout.json").read_bytes()).hexdigest()
        for name in ("2hp", "3hp"):
            v = json.loads((MECH / "exports" / name / "verification.json").read_text())
            self.assertEqual(v["layout_sha256"], sha, f"{name}: CAD export is stale; run build_a7_mechanical.py")
            self.assertTrue(v["all_shapes_valid"])
            self.assertEqual(v["unexpected_rigid_intersections"], [])
            self.assertEqual(v["retained_envelope_findings"], [])
            for s_, o in v["optical_obstruction"].items():
                self.assertEqual(o["a7_controller_or_support_obstructions"], 0, (name, s_))
            self.assertTrue(v["switch_tool_access"]["clear"])
            self.assertTrue(v["export"]["valid"])
            self.assertEqual(v["export"]["source_solids"], v["export"]["imported_solids"])
            for f in v["views"].values():
                self.assertTrue((MECH / "exports" / name / f).exists(), f)
            new_findings = [f for f in v["cable_findings"] if "note" not in f]
            self.assertTrue(all(f["clearance_mm"] >= 0 for f in new_findings), new_findings)
            for c in v["cables"]:
                if "layout_length_mm" in c:
                    self.assertAlmostEqual(c["centerline_length_mm"], c["layout_length_mm"], delta=0.01)
            self.assertFalse(v["manufacturing_release"])

    def test_front_artwork(self):
        g = json.loads((A7 / "front_panel" / "geometry.json").read_text())
        val = json.loads((A7 / "front_panel" / "exports" / "validation_A7.json").read_text())
        self.assertTrue(val["all_passed"])
        for name, fv in g["variants"].items():
            lv = L["variants"][name]
            self.assertEqual(fv["jack_holes"], [[lv["x_axis"], y] for y in L["y_layout"]["jack_y"]])
            self.assertEqual([q["text"] for q in fv["labels"]], ["IN", "THRU"])
            self.assertEqual([h[1] for h in fv["m2_holes"]], L["supports"]["front_screw_y"])
            self.assertNotIn("switch_hole", json.dumps(fv))
        for row in val["variants"]:
            self.assertFalse(row["switch_aperture_present"])
            self.assertTrue({"MODE", "ON", "PGM", "CV"} <= set(row["labels_removed_from_a5"]))
            self.assertTrue(row["labels_clear_of_pockets"])


if __name__ == "__main__":
    unittest.main()
