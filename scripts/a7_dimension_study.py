#!/usr/bin/env python3
"""A7 R1 dimension study: PJ-324M jack, M6x0.5 nut, PMMA front and a perpendicular controller PCB.

Reads engineering/a7/study/parameters.json and writes results.json and report.md beside it.
`--check` recomputes and fails if the committed outputs differ (no files are written).

Every result is a paper calculation from the stated inputs. The jack-axis height is an
INFERRED value carried as a band; tolerances marked ASSUMED are not sourced. A FEASIBLE
verdict here is "passes on paper over the stated input ranges", never a fit approval.
"""
import argparse
import itertools
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STUDY = REPO / "engineering" / "a7" / "study"
PARAMS = STUDY / "parameters.json"
RESULTS = STUDY / "results.json"
REPORT = STUDY / "report.md"

FEASIBLE = "FEASIBLE ON PAPER"
INFEASIBLE = "INFEASIBLE WITHIN STATED RANGES"
UNRESOLVED = "UNRESOLVED"


def r(value):
    return round(value + 0.0, 3)


def transverse_case(p, width_key, offset, pcb_t, lead_mode, case, axis_band=None):
    """Margins (mm, positive = clear) for one arrangement at the 'worst', 'nominal' or 'best' corner.

    axis_band overrides the INFERRED jack-axis band (min, nominal, max) for what-if rows.
    """
    P = p["parameters"]
    worst = case == "worst"
    sign = {"worst": 1, "nominal": 0, "best": -1}[case]
    a = P["jack_axis_height"]
    h_min, h_nom, h_max = axis_band or (a["min"], a["nominal"], a["max"])
    width = P[width_key]["nominal"]
    edge_shift = P[width_key]["tol"] / 2 if worst else 0.0
    pos = P["panel_hole_position_tol"]["nominal"] + P["panel_hole_radial_float"]["nominal"] if worst else 0.0
    x_axis = width / 2 + offset
    h_lead = {1: h_max, 0: h_nom, -1: h_min}[sign]
    h_body = {1: h_min, 0: h_nom, -1: h_max}[sign]
    rel = P["pcb_thickness_options"]["rel_tol"]
    t = pcb_t * (1 + sign * rel)
    term = P["jack_terminal_projection"]
    term_len = term["nominal"] + sign * term["tol"]
    if lead_mode == "trimmed":
        prot = P["lead_protrusion_trimmed"]["max"] if worst else P["lead_protrusion_trimmed"]["nominal"]
        lead_below_seat = t + prot
    else:
        lead_below_seat = term_len
    lead_tip_x = (x_axis - pos) - h_lead - lead_below_seat
    side_req = P["side_clearance_required"]["nominal"]
    overall = P["jack_overall_height"]["nominal"] + sign * P["jack_overall_height"]["tol"]
    body_top_x = (x_axis + pos) + (overall - h_body)
    margins = {
        "lead_side": r(lead_tip_x - edge_shift - side_req),
        "body_side": r((width - edge_shift) - body_top_x - side_req),
    }
    nut_od = max(n["od"] + sign * n["od_tol"] for n in p["nuts"].values())
    nut_edge = width / 2 - abs(offset) - nut_od / 2 - pos - edge_shift
    margins["nut_front"] = r(nut_edge - P["nut_edge_margin_required"]["nominal"])
    margins["pcb_hole_web"] = r(width / 2 - abs(offset) - 3.1 - pos - edge_shift)
    feasible_leads = lead_mode == "untrimmed" or term_len >= t
    if lead_mode == "trimmed":
        feasible_leads = (P["jack_terminal_projection"]["nominal"] - term["tol"]) >= pcb_t * (1 + rel) + P["lead_protrusion_trimmed"]["nominal"] if worst else True
    return {
        "x_axis": r(x_axis),
        "axis_height_used": {"lead_side": h_lead, "body_side": h_body},
        "pcb_thickness_used": r(t),
        "lead_tip_x": r(lead_tip_x),
        "body_top_x": r(body_top_x),
        "nut_edge_margin": r(nut_edge),
        "lead_long_enough_for_trim": feasible_leads,
        "margins": margins,
    }


def classify(worst, best, hard_keys):
    worst_fail = [k for k in hard_keys if worst["margins"][k] < 0] + ([] if worst["lead_long_enough_for_trim"] else ["lead_length"])
    best_fail = [k for k in hard_keys if best["margins"][k] < 0]
    if not worst_fail:
        return FEASIBLE, []
    if best_fail:
        return INFEASIBLE, best_fail
    return UNRESOLVED, worst_fail


def transverse(p):
    P = p["parameters"]
    hard = ["lead_side", "body_side", "nut_front"]
    rows = []
    for arr, pcb_t, lead in itertools.product(p["transverse_arrangements"], P["pcb_thickness_options"]["values"], ("untrimmed", "trimmed")):
        worst = transverse_case(p, arr["width"], arr["offset"], pcb_t, lead, "worst")
        nominal = transverse_case(p, arr["width"], arr["offset"], pcb_t, lead, "nominal")
        best = transverse_case(p, arr["width"], arr["offset"], pcb_t, lead, "best")
        verdict, drivers = classify(worst, best, hard)
        nut_pref = worst["nut_edge_margin"] >= P["nut_edge_margin_required"]["preferred"]
        reasons = []
        if verdict == UNRESOLVED:
            reasons.append("passes at the best corner but fails at the worst corner on: " + ", ".join(drivers))
            if "lead_side" in drivers:
                reasons.append("lead side depends on the INFERRED axis height (2.6-3.4) and the ASSUMED lead trim/PCB tolerance")
            if "body_side" in drivers:
                reasons.append("body side depends on the INFERRED axis height and the overall-height tolerance")
            if "nut_front" in drivers:
                reasons.append("nut edge depends on the ASSUMED hole position tolerance and nut OD tolerance")
            if "lead_length" in drivers:
                reasons.append("minimum terminal length cannot pass the thickest PCB plus the nominal trim protrusion")
        elif verdict == INFEASIBLE:
            reasons.append("fails even at the best corner on: " + ", ".join(drivers))
        rows.append({
            "arrangement": arr["id"], "panel_width": P[arr["width"]]["nominal"], "offset": arr["offset"],
            "pcb_thickness": pcb_t, "leads": lead, "verdict": verdict, "reasons": reasons,
            "nut_preferred_margin_met": nut_pref, "worst": worst, "nominal": nominal, "best": best,
        })
    return rows


def what_if_axis_confirmed(p, half_band=0.1):
    """2HP rows re-evaluated as if the axis height were confirmed at 3.0 +/- half_band.

    This is a sensitivity, not a result: 3.0 is still the INFERRED nominal. It shows which
    2HP variants the missing dimension decides.
    """
    P = p["parameters"]
    nom = P["jack_axis_height"]["nominal"]
    band = (nom - half_band, nom, nom + half_band)
    hard = ["lead_side", "body_side", "nut_front"]
    out = []
    for arr, pcb_t in itertools.product(p["transverse_arrangements"], P["pcb_thickness_options"]["values"]):
        if not arr["id"].startswith("2hp"):
            continue
        worst = transverse_case(p, arr["width"], arr["offset"], pcb_t, "trimmed", "worst", band)
        best = transverse_case(p, arr["width"], arr["offset"], pcb_t, "trimmed", "best", band)
        verdict, drivers = classify(worst, best, hard)
        out.append({"arrangement": arr["id"], "pcb_thickness": pcb_t, "leads": "trimmed", "assumed_axis_band": list(band),
                    "verdict": verdict, "failing_at_worst": drivers, "worst_margins": worst["margins"]})
    return out


def axial(p):
    P = p["parameters"]
    out = []
    req = P["min_engagement_required"]["nominal"]
    for opt, (nut_id, nut) in itertools.product(p["axial_options"], p["nuts"].items()):
        res = {}
        for case in ("worst", "nominal", "best"):
            sign = {"worst": -1, "nominal": 0, "best": 1}[case]
            barrel = P["jack_barrel_projection"]["nominal"] + sign * P["jack_barrel_projection"]["tol"]
            panel = P["panel_thickness"]["nominal"] - sign * P["panel_thickness"]["tol"]
            if opt["rear_pocket"]:
                panel -= P["rear_pocket_depth"]["nominal"] + sign * P["rear_pocket_depth"]["tol"]
            spacer = P[opt["rear_spacer"]]["nominal"] if isinstance(opt["rear_spacer"], str) else opt["rear_spacer"]
            washer = P["front_washer_thickness"]["nominal"] if opt["front_washer"] else 0.0
            exposed = barrel - panel - spacer - washer - P["front_body_gap"]["nominal"]
            usable = exposed - P["thread_lead_in_loss"]["nominal"]
            nut_t = nut["thickness"] - sign * nut["thickness_tol"]
            engaged = max(0.0, min(usable, nut_t))
            res[case] = {"barrel": r(barrel), "clamped_pmma": r(panel), "exposed_thread": r(exposed), "usable_thread": r(usable),
                         "nut_thickness": r(nut_t), "engaged": r(engaged), "full_nut_engaged": usable >= nut_t}
        if res["worst"]["engaged"] >= req:
            verdict = FEASIBLE
        elif res["best"]["engaged"] < req:
            verdict = INFEASIBLE
        else:
            verdict = UNRESOLVED
        out.append({"option": opt["id"], "description": opt["description"], "nut": nut_id, "verdict": verdict,
                    "full_nut_engaged_worst_case": res["worst"]["full_nut_engaged"], "cases": res})
    return out


def depth_and_y(p):
    P = p["parameters"]
    body_rear_max = P["jack_body_depth"]["nominal"] + P["jack_body_depth"]["tol"]
    pocket = P["rear_pocket_depth"]["nominal"]
    results = {}
    for name, z0 in (("seated-on-pmma-rear", 0.0), ("seated-in-rear-pocket", -pocket), ("on-a5-collar", P["old_collar_thickness"]["nominal"])):
        z_rear = z0 + body_rear_max
        results[name] = {"jack_body_rear_z_max": r(z_rear),
                         "margin_to_a5_optical_skin_front": r(P["a5_optical_skin_front_z"]["nominal"] - z_rear),
                         "margin_to_a5_leaf_front": r(P["a5_leaf_front_z"]["nominal"] - z_rear)}
    y0, y1 = P["a5_jack_y"]["values"]
    near, far = P["jack_axis_to_edge_near"]["nominal"], P["jack_axis_to_edge_far"]["nominal"]
    pitch = y1 - y0
    rail = P["rail_body_y"]["values"]
    y = {
        "jack_pitch": r(pitch),
        "body_gap_same_orientation": r(pitch - near - far),
        "nut_gap": r(pitch - max(n["od"] for n in p["nuts"].values())),
        "lower_body_edge_y_worst_orientation": r(y1 + far),
        "margin_to_rail_body_limit": r(rail[1] - (y1 + far)),
        "upper_body_edge_y_worst_orientation": r(y0 - far),
    }
    return {"axial_depth": results, "y_layout_at_a5_positions": y}


def summarise(tr):
    summary = {}
    for arr in sorted({row["arrangement"] for row in tr}, key=lambda a: [row["arrangement"] for row in tr].index(a)):
        rows = [row for row in tr if row["arrangement"] == arr]
        feasible = [f"{row['pcb_thickness']} mm {row['leads']}" for row in rows if row["verdict"] == FEASIBLE]
        unresolved = [f"{row['pcb_thickness']} mm {row['leads']}" for row in rows if row["verdict"] == UNRESOLVED]
        if feasible:
            verdict = FEASIBLE
        elif unresolved:
            verdict = UNRESOLVED
        else:
            verdict = INFEASIBLE
        summary[arr] = {"verdict": verdict, "feasible_variants": feasible, "unresolved_variants": unresolved,
                        "nut_preferred_margin_met": rows[0]["nut_preferred_margin_met"]}
    return summary


def build():
    p = json.loads(PARAMS.read_text())
    tr = transverse(p)
    ax = axial(p)
    return {
        "schema_version": 1,
        "generator": "scripts/a7_dimension_study.py",
        "inputs": "engineering/a7/study/parameters.json",
        "status": "Paper study. Jack-axis height is INFERRED; jack dimensions marked MIRROR come from the LCSC-hosted copy of the SOFNG drawing and are not primary-source confirmed; tolerances marked ASSUMED are unsourced. Not a fit approval or part approval.",
        "verdict_meaning": {FEASIBLE: "every hard margin is non-negative at the worst corner of the stated input ranges",
                            UNRESOLVED: "passes at the best corner, fails at the worst; needs stronger evidence for the named inputs",
                            INFEASIBLE: "fails even at the best corner of the stated input ranges"},
        "transverse_summary": summarise(tr),
        "transverse": tr,
        "what_if_axis_height_confirmed_3.0_pm_0.1": what_if_axis_confirmed(p),
        "axial": ax,
        "depth_and_y": depth_and_y(p),
        "input_confidence": {k: {f: v[f] for f in ("nominal", "values", "min", "max", "tol", "rel_tol", "confidence", "tol_confidence", "source") if f in v}
                             for k, v in p["parameters"].items()},
    }


def fmt(v):
    return f"{v:+.2f}" if isinstance(v, float) else str(v)


def report(res):
    L = ["# A7 R1 dimension study (generated)", "",
         "Generated by `scripts/a7_dimension_study.py` from `parameters.json`. Do not edit by hand.", "",
         res["status"], "",
         "Datum: X across the panel (0 = left edge), Z into the rack from the PMMA rear. PCB on the -X side of the jack body; terminals point to -X.", "",
         "## Transverse (X) summary", "",
         "| Arrangement | Verdict | Variants that pass at the worst corner | Variants that need evidence | Nut 0.3 mm preferred margin |",
         "|---|---|---|---|---|"]
    for arr, s in res["transverse_summary"].items():
        L.append(f"| {arr} | {s['verdict']} | {', '.join(s['feasible_variants']) or '-'} | {', '.join(s['unresolved_variants']) or '-'} | {'yes' if s['nut_preferred_margin_met'] else 'no'} |")
    L += ["", "## Transverse (X) detail, worst corner", "",
          "Margins in mm after the 0.3 mm side clearance (negative = interference). Worst corner: axis height 3.4 on the lead side and 2.6 on the body side, PCB +10%, terminal +0.2, trim protrusion 1.0, hole position + float 0.2, panel width -0.1.", "",
          "| Arrangement | PCB | Leads | Lead side | Body side | Nut edge | Hole web | Verdict |", "|---|---|---|---|---|---|---|---|"]
    for row in res["transverse"]:
        m = row["worst"]["margins"]
        L.append(f"| {row['arrangement']} | {row['pcb_thickness']} | {row['leads']} | {fmt(m['lead_side'])} | {fmt(m['body_side'])} | {fmt(m['nut_front'])} | {fmt(m['pcb_hole_web'])} | {row['verdict']} |")
    L += ["", "## Transverse (X) nominal corner, trimmed leads", "",
          "Nominal inputs (axis height 3.0 INFERRED, no tolerances). A positive row is plausible, not proven.", "",
          "| Arrangement | PCB | Lead side | Body side | Nut edge |", "|---|---|---|---|---|"]
    for row in res["transverse"]:
        if row["leads"] == "trimmed":
            m = row["nominal"]["margins"]
            L.append(f"| {row['arrangement']} | {row['pcb_thickness']} | {fmt(m['lead_side'])} | {fmt(m['body_side'])} | {fmt(m['nut_front'])} |")
    L += ["", "## What the missing axis-height dimension decides (sensitivity, not a result)", "",
          "2HP rows with trimmed leads, re-run as if the axis height were confirmed at 3.0 +/- 0.1 mm. All other worst-corner tolerances unchanged.", "",
          "| Arrangement | PCB | Lead side | Body side | Nut edge | Verdict under that assumption |", "|---|---|---|---|---|---|"]
    for row in res["what_if_axis_height_confirmed_3.0_pm_0.1"]:
        m = row["worst_margins"]
        L.append(f"| {row['arrangement']} | {row['pcb_thickness']} | {fmt(m['lead_side'])} | {fmt(m['body_side'])} | {fmt(m['nut_front'])} | {row['verdict']} |")
    L += ["", "## Axial (Z) thread engagement", "",
          "Usable thread = barrel projection - clamped PMMA - spacer - washer - 0.25 lead-in. Requirement: at least 1.0 mm engaged at the worst corner.", "",
          "| Option | Nut | Worst exposed | Worst engaged | Nominal engaged | Full nut at worst | Verdict |", "|---|---|---|---|---|---|---|"]
    for row in res["axial"]:
        c = row["cases"]
        L.append(f"| {row['option']} | {row['nut']} | {fmt(c['worst']['exposed_thread'])} | {fmt(c['worst']['engaged'])} | {fmt(c['nominal']['engaged'])} | {'yes' if row['full_nut_engaged_worst_case'] else 'no'} | {row['verdict']} |")
    d = res["depth_and_y"]
    L += ["", "## Depth and Y layout", "", "| Jack seating | Body rear Z (max) | Margin to A5 optical skin front (17.4) | Margin to A5 leaf front (19.4) |", "|---|---|---|---|"]
    for k, v in d["axial_depth"].items():
        L.append(f"| {k} | {fmt(v['jack_body_rear_z_max'])} | {fmt(v['margin_to_a5_optical_skin_front'])} | {fmt(v['margin_to_a5_leaf_front'])} |")
    y = d["y_layout_at_a5_positions"]
    L += ["", f"At the A5 jack positions (Y 90 / 104): body gap {y['body_gap_same_orientation']} mm, nut gap {y['nut_gap']} mm, lower body edge Y {y['lower_body_edge_y_worst_orientation']} (rail-body limit 111.4, margin {y['margin_to_rail_body_limit']}).", ""]
    L += ["## Inputs", "", "| Parameter | Nominal | Range or tol | Confidence | Source |", "|---|---|---|---|---|"]
    for key, v in res["input_confidence"].items():
        if "tol" in v:
            span = f"+/-{v['tol']} ({v.get('tol_confidence', v['confidence'])})"
        elif "rel_tol" in v:
            span = f"+/-{v['rel_tol'] * 100:.0f}%"
        else:
            span = f"{v.get('min', v.get('nominal'))}..{v['max']}" if "max" in v else "-"
        nominal = v["nominal"] if "nominal" in v else " / ".join(str(x) for x in v["values"])
        L.append(f"| {key} | {nominal} | {span} | {v['confidence']} | {v['source']} |")
    L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="fail if committed outputs differ")
    args = ap.parse_args()
    res = build()
    text = json.dumps(res, indent=2, ensure_ascii=False) + "\n"
    rep = report(res)
    if args.check:
        stale = [str(path.relative_to(REPO)) for path, want in ((RESULTS, text), (REPORT, rep)) if not path.exists() or path.read_text() != want]
        if stale:
            print("STALE: " + ", ".join(stale) + " (run python3 scripts/a7_dimension_study.py)")
            return 1
        print("PASS: A7 dimension study outputs are current")
        return 0
    RESULTS.write_text(text)
    REPORT.write_text(rep)
    for arr, s in res["transverse_summary"].items():
        print(f"{arr}: {s['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
