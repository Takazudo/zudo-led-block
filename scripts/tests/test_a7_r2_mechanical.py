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
        self.assertEqual(json.dumps(LAY.envelopes(built), indent=2, ensure_ascii=False) + "\n", (MECH / "placement-envelopes.json").read_text())

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
        self.assertEqual(d["default_variant"], "3hp")
        self.assertEqual(d["working_verdict"], STUDY.FEASIBLE)
        self.assertEqual(d["open_verdict"], STUDY.UNRESOLVED)
        self.assertNotIn("INFEASIBLE", d["open_verdict"])
        self.assertEqual(sorted(d["variants_generated"]), ["2hp", "3hp"])
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
        D = json.loads((MECH / "design-inputs.json").read_text())
        self.assertGreaterEqual(sw["gap_to_lower_jack_body"], D["jacks"]["body_to_switch_gap"]["nominal"] - 1e-9)
        tn, tf = P["jack_axis_to_edge_near"].get("tol", 0), P["jack_axis_to_edge_far"].get("tol", 0)
        for yc, (e0, e1), (n0, n1) in zip(y["jack_y"], y["jack_body_y"], y["jack_body_y_nominal"]):
            # pin 2 faces +Y; the 6.1 (far) edge is the pin-2 side (#24 review reading)
            self.assertAlmostEqual(e1 - yc, P["jack_axis_to_edge_far"]["nominal"] + tf, places=6)
            self.assertAlmostEqual(yc - e0, P["jack_axis_to_edge_near"]["nominal"] + tn, places=6)
            self.assertTrue(e0 <= n0 and n1 <= e1)
        self.assertGreater(y["jack_pin_y_offset_from_axis"]["pin_2"], 0, "pin 2 faces +Y (switch)")
        self.assertLess(y["jack_pin_y_offset_from_axis"]["pin_4"], 0)
        self.assertGreaterEqual(sw["pad_gap_to_lower_jack_body"], 0)
        for k in L["controller"]["keepouts"]:
            if k["id"].endswith("-leads"):
                yc = L["y_layout"]["jack_y"][0 if "-in-" in k["id"] else 1]
                for dy in y["jack_pin_y_offset_from_axis"].values():
                    self.assertTrue(k["y"][0] + 0.75 <= yc + dy <= k["y"][1] - 0.75, (k["id"], dy))
        (a0, a1), (b0, b1) = y["jack_body_y"]
        self.assertGreater(b0, a1)
        self.assertGreaterEqual(a0, L["supports"]["spine"]["slot_y"][1])
        self.assertGreaterEqual(y["jack_body_y"][0][0], L["controller"]["outline_y"][0])
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
            self.assertTrue(c["solder_face_zone_below_lead_tips"], name)
            self.assertGreaterEqual(c["solder_face_zone_margin_worst"], 0, name)
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


class Harness(unittest.TestCase):
    def test_adapter_gap_takes_the_sh_bundle(self):
        ad = L["supports"]["adapter"]
        br = L["variants"]["3hp"]["routes"]["controller_to_left_leaf_sh4"]["bundle_radius"]
        zg = json.loads((MECH / "design-inputs.json").read_text())["cables"]["led_route"]["gap_run_z"]
        self.assertAlmostEqual(ad["front_z"], ad["a5_front_z"] + ad["z_shift"], places=6)
        self.assertGreaterEqual(zg - br, ad["rear_z"] + 0.2 - 1e-9)
        self.assertLessEqual(zg + br, L["z_stack"]["a5_leaf_z"][0] - 0.2 + 1e-9)
        self.assertGreater(zg - br, L["z_stack"]["controller_pcb_z"][1])
        for v in L["variants"].values():
            sh = v["routes"]["controller_to_left_leaf_sh4"]
            self.assertLess(sh["descent_y"], ad["y"][1], "the step down happens over the adapter, away from LED D2")
            self.assertGreaterEqual(sh["min_radius"], json.loads((MECH / "design-inputs.json").read_text())["cables"]["led_route"]["step_radius"] - 1e-9)
        self.assertAlmostEqual(L["controller"]["led_header"]["z_centre"], 12.8)

    def test_pet_leaf_comparison(self):
        lc = L["leaf_comparison"]
        self.assertEqual(lc["default"], "fr4")
        self.assertEqual(lc["inputs"]["pet"]["film"]["finished_thickness"]["confidence"], "MANUFACTURER_PRIMARY")
        for k in ("adhesive", "carrier"):
            self.assertEqual(lc["inputs"]["pet"][k]["thickness"]["confidence"], "INFERRED")
        self.assertIsNone(lc["inputs"]["sh_mating_force_n"]["nominal"], "SH mating force stays UNSOURCED")
        self.assertLess(lc["pet"]["total_thickness"], lc["inputs"]["cap_slot_width"])
        self.assertLessEqual(abs(lc["outer_face_shift_pet_minus_fr4"]), 0.05)
        self.assertGreaterEqual(lc["pet"]["rigidity_per_mm_bonded_nmm"], lc["pet"]["rigidity_per_mm_lower_bound_nmm"])
        self.assertLess(lc["pet_film_alone_buckling_load_fixed_free_n"], lc["pet"]["buckling_load_lower_bound_n"]["fixed_free_K2"])
        self.assertTrue(lc["recommendation"].startswith("Keep FR-4 as the default"))
        v = json.loads((MECH / "exports" / "3hp_pet" / "verification.json").read_text())
        self.assertEqual(v["leaf"], "pet")
        self.assertEqual(v["layout_sha256"], hashlib.sha256((MECH / "layout.json").read_bytes()).hexdigest(), "3hp_pet CAD export is stale")
        for f, h in v["input_sha256"].items():
            self.assertEqual(hashlib.sha256((REPO / f).read_bytes()).hexdigest(), h, f"3hp_pet: {f} changed")
        self.assertEqual(v["unexpected_rigid_intersections"], [])
        self.assertTrue(v["all_shapes_valid"])
        self.assertIn("leaf_carrier_PC", {p["part"] for p in v["parts"]})
        for o in v["optical_obstruction"].values():
            self.assertEqual(o["a7_controller_or_support_obstructions"], 0)
            for h in o["a7_harness_obstructions"]:
                self.assertGreaterEqual(h["min_distance_to_emitter_mm"], 1.0)
        self.assertTrue(all(f["clearance_mm"] >= 0.05 - 1e-9 for f in v["cable_findings"] if "note" not in f))
        self.assertTrue(v["export"]["valid"])
        self.assertEqual(v["export"]["source_solids"], v["export"]["imported_solids"])

    def test_r4_routed_placement_matches_envelopes(self):
        chk = json.loads((MECH / "r4-placement-check.json").read_text())
        self.assertTrue(chk["status"].startswith("ROUTED EXPORT"))
        self.assertTrue(chk["outline_matches"], chk["board_outline"])
        self.assertTrue(chk["fixed_parts_ok"], [f for f in chk["fixed_parts"] if not f["ok"]])
        self.assertEqual(chk["origins_inside_foreign_keepouts"], [])
        self.assertEqual(chk["pad_centres_inside_foreign_keepouts"], [])
        self.assertTrue(chk["solder_face_parts_are_resistors_or_test_pads"])
        self.assertEqual(chk["source"]["board_thickness"], L["variants"][L["decision"]["default_variant"]]["pcb_thickness"])
        self.assertEqual(chk["source"]["sha256"], hashlib.sha256((MECH / "inputs" / "r4-board-placement-routed.json").read_bytes()).hexdigest())

    def test_hand_written_cable_figures_match_layout(self):
        req = L["power_cable_requirement"]
        n, t = req["finished_free_span_nominal"], req["tolerance"]
        lo, hi = req["stowage_length_range_both_widths"]
        readme = " ".join((MECH / "README.md").read_text().split())
        self.assertIn(f"{n:g} ± {t:g} mm free span", readme)
        self.assertIn(f"{n - t:g}–{n + t:g} mm", readme)
        self.assertIn(f"{lo:.1f}–{hi:.1f} mm", readme)
        decisions = (REPO / "doc/src/content/docs/decisions/index.mdx").read_text()
        self.assertIn(f"自由長 {n:g} ± {t:g} mm ({n - t:g}–{n + t:g} mm", decisions)

    def test_moved_adapter_keeps_screw_and_boss(self):
        sp, ad, scr = L["supports"]["spine"], L["supports"]["adapter"], L["supports"]["top_cap_screw"]
        self.assertAlmostEqual(ad["cap_spacer_z"][1] - ad["cap_spacer_z"][0], -ad["z_shift"], places=6)
        self.assertAlmostEqual(ad["cap_spacer_z"][0], ad["rear_z"], places=6)
        self.assertAlmostEqual(sp["post_nut_z"][0] - scr["tip_z"], 2.2, places=6, msg="A5 thread protrusion past the post nut")
        self.assertEqual(scr["designation"], "M2x18")
        self.assertGreaterEqual(ad["cap_spacer_radius"] - 1.1, 1.5, "printed boss wall")


class Envelopes(unittest.TestCase):
    E = json.loads((MECH / "placement-envelopes.json").read_text())

    def _board(self, item):
        y0, z0 = L["controller"]["outline_y"][0], L["controller"]["outline_z"][0]
        for a, b, o in (("assembly_y", "board_y", y0), ("assembly_z", "board_x", z0)):
            for p_, q in zip(item[a], item[b]):
                self.assertAlmostEqual(q, p_ - o, places=6)

    def test_board_frame_matches_assembly_frame(self):
        e = self.E
        self._board(e["outline"])
        for k in e["keepouts"] + [j["body"] for j in e["jacks"]] + [e["setting_switch"]["body"], e["setting_switch"]["actuator"]] + list(e["headers"].values()):
            self._board(k)
        w, h = e["outline"]["board_x"][1], e["outline"]["board_y"][1]
        for j in e["jacks"]:
            for p_ in j["pins"]:
                self.assertTrue(0 <= p_["board_x"] <= w and 0 <= p_["board_y"] <= h, p_)

    def test_envelopes_carry_decision_and_all_keepouts(self):
        e = self.E
        self.assertEqual(e["default_variant"], L["decision"]["default_variant"])
        self.assertEqual({k["id"] for k in e["keepouts"]}, {k["id"] for k in L["controller"]["keepouts"]})
        self.assertEqual(set(e["variants"]), {"2hp", "3hp"})
        self.assertIn("INFERRED", e["jack_notes"])


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
            # the route is solved for the derived A7 cable and both band ends still fit the S-fold stowage
            req = L["power_cable_requirement"]
            self.assertAlmostEqual(pw["length"], req["finished_free_span_nominal"], delta=0.01)
            for got, want in zip(pw["cable_band_lengths"], req["band"]):
                self.assertAlmostEqual(got, want, delta=0.01)
            lo, hi = pw["length_range_of_this_stowage"]
            self.assertGreaterEqual(req["band"][0], lo + req["short_side_margin"] - 1e-9)
            self.assertLessEqual(req["band"][1], hi + 1e-9)
            self.assertFalse(req["a5_cable"]["fits"])
            self.assertIn("MISSING", req["physical_measurement"])
            self.assertEqual(v["checks"]["power_route_bend_at_least_preferred"], pw["min_radius"] >= 2.0 - 1e-9)
        self.assertTrue(L["variants"]["3hp"]["checks"]["power_route_bend_at_least_preferred"])


class Exports(unittest.TestCase):
    def test_cad_verification_current_and_clean(self):
        sha = hashlib.sha256((MECH / "layout.json").read_bytes()).hexdigest()
        for name in ("2hp", "3hp"):
            v = json.loads((MECH / "exports" / name / "verification.json").read_text())
            self.assertEqual(v["layout_sha256"], sha, f"{name}: CAD export is stale; run build_a7_mechanical.py")
            for f, h in v["input_sha256"].items():
                self.assertEqual(hashlib.sha256((REPO / f).read_bytes()).hexdigest(), h, f"{name}: {f} changed; rerun the front and CAD builds")
            self.assertEqual(set(v["input_sha256"]), {"engineering/a7/mechanical/layout.json", "engineering/a7/mechanical/build_a7_mechanical.py", "engineering/a7/front_panel/build_a7_front.py"})
            for row in v["explicitly_expected_contacts"]:
                self.assertLessEqual(row["volume_mm3"], row["limit_mm3"] + 1e-9, row)
            self.assertIn("bottom_cap_fork_A7", {p["part"] for p in v["parts"]})
            self.assertTrue(v["all_shapes_valid"])
            self.assertEqual(v["unexpected_rigid_intersections"], [])
            self.assertEqual(v["retained_envelope_findings"], [])
            for s_, o in v["optical_obstruction"].items():
                self.assertEqual(o["a7_controller_or_support_obstructions"], 0, (name, s_))
                for h in o["a7_harness_obstructions"]:
                    self.assertGreaterEqual(h["min_distance_to_emitter_mm"], 1.0, (name, s_, h))
                origins = {x["part"]: x["origin"] for x in o["obstructions"]}
                for part, org in origins.items():
                    if part.startswith(("controller_", "adapter_to_controller", "bottom_cap_fork_A7", "top_cap_spacer_A7", "spine", "M2_front", "M2_nut")):
                        self.assertTrue(org.startswith("a7"), (part, org))
            for s_, rows in v["optical_shading_estimate"]["per_side"].items():
                self.assertEqual(len(rows), 4)
                for row in rows:
                    # regression guard on a ray-sampled estimate (about 0.02 today), not an optical acceptance limit
                    self.assertLessEqual(row["blocked_by_a7_harness"], 0.05, (name, row))
            self.assertIn("top_cap_spacer_A7", {p["part"] for p in v["parts"]})
            self.assertTrue(v["switch_tool_access"]["clear"])
            self.assertTrue(v["export"]["valid"])
            self.assertEqual(v["export"]["source_solids"], v["export"]["imported_solids"])
            for f in v["views"].values():
                self.assertTrue((MECH / "exports" / name / f).exists(), f)
            new_findings = [f for f in v["cable_findings"] if "note" not in f]
            self.assertTrue(all(f["clearance_mm"] >= 0.05 - 1e-9 for f in new_findings), new_findings)
            self.assertFalse(any("PicoBlade" in f["a"] + f["b"] and "sh4" in f["a"] + f["b"] for f in v["cable_findings"]), "SH4 fold must clear the controller PicoBlade by >= 0.1")
            self.assertIn("top_cap_screw_A7", {p["part"] for p in v["parts"]})
            for c in v["cables"]:
                if "layout_length_mm" in c:
                    self.assertAlmostEqual(c["centerline_length_mm"], c["layout_length_mm"], delta=0.01)
            self.assertFalse(v["manufacturing_release"])
            self.assertEqual(v["default_variant"], name == L["decision"]["default_variant"])

    def test_front_artwork(self):
        g = json.loads((A7 / "front_panel" / "geometry.json").read_text())
        val = json.loads((A7 / "front_panel" / "exports" / "validation_A7.json").read_text())
        self.assertTrue(val["all_passed"])
        for f, h in val["input_sha256"].items():
            self.assertEqual(hashlib.sha256((REPO / f).read_bytes()).hexdigest(), h, f"{f} changed; rerun build_a7_front.py")
        for name, fv in g["variants"].items():
            for pk in fv["rear_pockets"]:
                self.assertEqual(pk["x"], L["variants"][name]["rear_pocket_x"])
                self.assertIn("INFERRED", pk["x_basis"])
            self.assertGreater(L["variants"][name]["checks"]["rear_pocket_wall_to_panel_edge"], 0)
        self.assertEqual(g["default_variant"], L["decision"]["default_variant"])
        self.assertEqual(next(iter(g["variants"])), g["default_variant"])
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
