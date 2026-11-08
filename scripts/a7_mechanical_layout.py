#!/usr/bin/env python3
"""A7 R2 mechanical layout: candidate selection, transverse/axial/depth stack and placements.

Reads the R1 inputs (engineering/a7/study/parameters.json and the PCM13SMTR facts), the A5
mechanical and front-panel geometry (read-only), and R2's own choices in
engineering/a7/mechanical/design-inputs.json. Writes layout.json and layout.md beside the
design inputs. `--check` recomputes and fails if the committed outputs differ.

The transverse margins are R1's own calculation (scripts/a7_dimension_study.py, imported, not
copied). R2 adds a finer offset sweep, a selection rule, break-even values for the inputs that
decide 2HP, and the Y/Z placement that the CAD model (build_a7_mechanical.py) and the front
artwork (build_a7_front.py) consume. Pure Python: no CadQuery needed.

Everything here is a paper calculation. INFERRED and ASSUMED inputs stay labelled as such.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
A5 = REPO / "engineering" / "a5"
A7 = REPO / "engineering" / "a7"
MECH = A7 / "mechanical"
INPUTS = MECH / "design-inputs.json"
LAYOUT = MECH / "layout.json"
REPORT = MECH / "layout.md"
ENVELOPES = MECH / "placement-envelopes.json"
R4_PLACEMENT = MECH / "inputs" / "r4-board-placement-routed.json"
R4_CHECK = MECH / "r4-placement-check.json"
# Vendored unchanged from R4 (#19) PR #30 (merged at eb8adeb), head e2a2219: routed-board export after layout review (authority.py export-placement).
R4_PLACEMENT_SOURCE = {"pr": 30, "branch": "claude/project-thread-rhjln2", "head": "e2a221936bc39321f4054ac3a44b3176a1bb2705",
                       "path": "engineering/a7/electronics/controller/board_placement.json", "status": "ROUTED, PR #30 merged at eb8adeb (board ec810aec); fit check merged in #33"}
SKILLS = REPO / ".claude" / "skills"
SWITCH_FACTS = SKILLS / "component-a7-pcm13smtr" / "facts.json"
JACK_FACTS = SKILLS / "component-a7-pj-324m" / "facts.json"


def load_study():
    spec = importlib.util.spec_from_file_location("a7_dimension_study", REPO / "scripts" / "a7_dimension_study.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S = load_study()


def r(v):
    return round(v + 0.0, 3)


def fact(path, fact_id):
    for f in json.loads(path.read_text())["facts"]:
        if f["fact_id"] == fact_id:
            return f["value"]
    raise KeyError(fact_id)


def union_area(rects, step=0.05):
    """Area of the union of axis-aligned (y, z) rectangles, by exact sweep over the distinct y breaks."""
    ys = sorted({v for (y, _) in rects for v in y})
    total = 0.0
    for y0, y1 in zip(ys, ys[1:]):
        spans = sorted((z[0], z[1]) for (y, z) in rects if y[0] <= y0 and y[1] >= y1)
        cover, cur = 0.0, None
        for a, b in spans:
            if cur is None or a > cur[1]:
                if cur:
                    cover += cur[1] - cur[0]
                cur = [a, b]
            else:
                cur[1] = max(cur[1], b)
        if cur:
            cover += cur[1] - cur[0]
        total += cover * (y1 - y0)
    return total


def frange(a, b, step):
    n = int(round((b - a) / step))
    return [r(a + i * step) for i in range(n + 1)]



# ---- cable route geometry (shared with the CAD build) -----------------------------------
def _sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def _norm(a):
    n = math.sqrt(sum(x * x for x in a))
    if n < 1e-12:
        return [0.0, 0.0, 0.0], 0.0
    return [x / n for x in a], n


def fillet_path(points, radius):
    """Polyline with every interior corner rounded by an arc (radius clamped to fit).

    Returns segments [("line", a, b) | ("arc", t1, mid, t2, r, angle)] and the total length.
    The same function feeds the CAD sweep, so the CAD length check is independent of it.
    """
    segs, length, cur, radii = [], 0.0, list(points[0]), []
    for i in range(1, len(points) - 1):
        a, p_, b = points[i - 1], points[i], points[i + 1]
        u1, l1 = _norm(_sub(p_, a))
        u2, l2 = _norm(_sub(b, p_))
        cosang = max(-1.0, min(1.0, sum(u1[k] * u2[k] for k in range(3))))
        theta = math.acos(cosang)
        if theta < 1e-9:
            continue
        half1 = l1 / 2 if i > 1 else l1
        half2 = l2 / 2 if i < len(points) - 2 else l2
        rr = min(radius, min(half1, half2) / math.tan(theta / 2))
        d = rr * math.tan(theta / 2)
        t1 = [p_[k] - u1[k] * d for k in range(3)]
        t2 = [p_[k] + u2[k] * d for k in range(3)]
        m, _ = _norm([u2[k] - u1[k] for k in range(3)])
        cdist = rr / math.cos(theta / 2)
        centre = [p_[k] + m[k] * cdist for k in range(3)]
        mid = [centre[k] - m[k] * rr for k in range(3)]
        if _norm(_sub(t1, cur))[1] > 1e-9:
            segs.append(("line", cur, t1))
            length += _norm(_sub(t1, cur))[1]
        segs.append(("arc", t1, mid, t2, rr, theta))
        length += rr * theta
        radii.append(rr)
        cur = t2
    if _norm(_sub(points[-1], cur))[1] > 1e-9:
        segs.append(("line", cur, list(points[-1])))
        length += _norm(_sub(points[-1], cur))[1]
    return segs, length, (min(radii) if radii else None)


def solve(fn, lo, hi, target, n=80):
    flo = fn(lo) - target
    fhi = fn(hi) - target
    if flo * fhi > 0:
        return None
    for _ in range(n):
        mid = (lo + hi) / 2
        fm = fn(mid) - target
        if (fm < 0) == (flo < 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return (lo + hi) / 2


def leaf_comparison(d, l5, z_stack):
    """FR-4 (A5) leaf versus a clear PET FPC leaf on a clear carrier: stack, stiffness, buckling under the SH mating push, fit in the A5 caps."""
    lv = d["leaf_variants"]
    f4, pe = lv["fr4"], lv["pet"]
    depth = l5["depth"]
    span = lv["sh_header_span_to_cap"]["nominal"]
    slot_width = 1.6  # A5 cap slot cut xc +/- 0.8 (build_mechanical.py, kept in A7)

    def layers_fr4():
        t, b, e = f4["board_thickness"]["nominal"], f4["bond_line"]["nominal"], f4["flexural_modulus_mpa"]["nominal"]
        return [(b / 2, b / 2 + t, e, "FR-4")], b / 2 + t

    def layers_pet():
        tc, ec = pe["carrier"]["thickness"]["nominal"], pe["carrier"]["modulus_mpa"]["nominal"]
        ta, tf, ef = pe["adhesive"]["thickness"]["nominal"], pe["film"]["finished_thickness"]["nominal"], pe["film"]["modulus_mpa"]["nominal"]
        z0 = tc / 2 + ta
        return [(0.0, tc / 2, ec, "carrier"), (z0, z0 + tf, ef, "PET film")], z0 + tf

    def stack(layers, half, composite_layers):
        # flexural rigidity per mm of leaf depth (N mm), symmetric about the bond/carrier mid-plane
        bonded = sum(2 * e * (z1 ** 3 - z0 ** 3) / 3 for z0, z1, e, _ in layers)
        loose = sum((2 if z0 > 0 else 1) * e * ((z1 - z0) * (2 if z0 == 0 else 1)) ** 3 / 12 for z0, z1, e, _ in layers)
        d_low = bonded if composite_layers else loose
        out = {"total_thickness": r(2 * half), "outer_face_offset_from_centre": r(half),
               "rigidity_per_mm_bonded_nmm": r(bonded), "rigidity_per_mm_lower_bound_nmm": r(d_low)}
        for tag, dd in (("lower_bound", d_low), ("bonded", bonded)):
            ei = dd * depth
            out[f"buckling_load_{tag}_n"] = {"fixed_free_K2": r(math.pi ** 2 * ei / (2 * span) ** 2), "fixed_pinned_K0.7": r(math.pi ** 2 * ei / (0.7 * span) ** 2)}
        out["cap_slot_clearance_per_side"] = r((slot_width - 2 * half) / 2)
        return out

    lf, hf = layers_fr4()
    lp, hp = layers_pet()
    fr4 = stack(lf, hf, True)  # the A5 FR-4 boards are bonded rigidly enough to count as one section
    pet = stack(lp, hp, False)
    tf, ef = pe["film"]["finished_thickness"]["nominal"], pe["film"]["modulus_mpa"]["nominal"]
    film_alone = math.pi ** 2 * ef * depth * tf ** 3 / 12 / (2 * span) ** 2
    shift = r(hp - hf)
    return {
        "status": "Digital comparison only; FR-4 stays the default leaf. Values marked INFERRED are typical material figures, not supplier data.",
        "default": lv["default"],
        "inputs": {"fr4": f4, "pet": pe, "sh_header_span_to_cap": span, "sh_mating_force_n": lv["sh_mating_force_n"], "leaf_depth": depth,
                   "cap_slot_width": slot_width},
        "fr4": fr4, "pet": pet,
        "pet_film_alone_buckling_load_fixed_free_n": r(film_alone),
        "rigidity_ratio_fr4_to_pet": {"lower_bound": r(fr4["rigidity_per_mm_bonded_nmm"] / pet["rigidity_per_mm_lower_bound_nmm"]),
                                      "bonded": r(fr4["rigidity_per_mm_bonded_nmm"] / pet["rigidity_per_mm_bonded_nmm"])},
        "outer_face_shift_pet_minus_fr4": shift,
        "optical": {"leaf_outline_unchanged": True, "leaf_z": l5["z"], "led_and_connector_shift_toward_centre": r(-shift),
                    "corridor_unchanged": "A5 corridor X limits (xc +/- 1.25 to the diffuser) are kept; the LED emitting faces move by the face shift",
                    "transmittance": pe["film"]["transmittance"]},
        "rear_pocket": {"pmma_rear_z": z_stack["pmma_rear_z"], "rear_pocket_depth": z_stack["rear_pocket_depth"], "leaf_front_z": l5["z"][0],
                        "z_gap_leaf_to_pmma_rear": r(l5["z"][0] - z_stack["pmma_rear_z"]),
                        "interaction": "none: the leaf variant changes only the X stack, not the leaf Z range, so the 0.5 mm jack pockets and the 30 mm depth budget are unchanged"},
        "harness": {"sh4_plug_shift_toward_centre": r(-shift), "note": "the SH4 plug sits on the film outer face, so the R2-C6 route start moves by the face shift; the CAD re-check is in exports/3hp_pet/verification.json"},
        "min_static_bend_radius_mm": r(pe["film"]["min_static_bend_radius_factor"]["nominal"] * tf),
        "recommendation": ("Keep FR-4 as the default and fallback. A clear PET leaf is mechanically feasible only as film laminated to a clear carrier: "
                           f"the film alone buckles at about {film_alone:.2f} N under the SH mating push, so it cannot stand on its own. "
                           f"With a {pe['carrier']['thickness']['nominal']} mm PC carrier the stack is {2 * hp:.2f} mm (FR-4 {2 * hf:.2f} mm), fits the A5 cap slots and keeps every LED, connector, corridor and harness position within {abs(shift):.2f} mm, "
                           f"but it is {fr4['rigidity_per_mm_bonded_nmm'] / pet['rigidity_per_mm_bonded_nmm']:.0f}-{fr4['rigidity_per_mm_bonded_nmm'] / pet['rigidity_per_mm_lower_bound_nmm']:.0f}x less stiff: "
                           f"its worst-case buckling load under the SH push is about {pet['buckling_load_lower_bound_n']['fixed_free_K2']:.0f} N (FR-4 {fr4['buckling_load_lower_bound_n']['fixed_free_K2']:.0f} N), and the SH mating force is unsourced. "
                           "Pursue PET only after JLC answers reflow/paste, PET-compatible stiffeners and OCA clarity (Q11), and after a physical mating-force and lit-appearance test (#10)."),
    }


def led_route(xc, x1, cfg, leaf_exit_y, leaf_exit_z, yp_end, target):
    """Leaf J1 plug mouth -> S-step down into the adapter/leaf gap -> run +Y -> one fold -> back to the controller SH4."""
    xl = r(xc - 2.35)
    xp = r(x1 + 1.475)
    ro = cfg["led_route"]
    radius = ro["step_radius"]
    zg, zr = ro["gap_run_z"], ro["return_z"]
    yd = r(leaf_exit_y + ro["exit_straight"] + radius)

    def pts(yf):
        return [[xl, leaf_exit_y, leaf_exit_z], [xl, yd, leaf_exit_z], [xl, yd, zg], [xp, r(yd + 2 * radius + 1.0), zg],
                [xp, yf, zg], [xp, yf, zr], [xp, yp_end, zr]]
    lo, hi = yp_end + 2 * radius + 0.5, 110.0
    yf = solve(lambda v: fillet_path(pts(v), radius)[1], lo, hi, target)
    P = pts(r(yf))
    segs, length, rmin = fillet_path(P, radius)
    return {"points": P, "radius": radius, "length": r(length), "min_radius": r(rmin), "fold_y": r(yf), "descent_y": yd,
            "length_range_of_this_stowage": [r(fillet_path(pts(lo), radius)[1]), r(fillet_path(pts(hi), radius)[1])]}


def power_route(xc, x1, w, side, cfg, start, yp, zc, target, radius, bundle_r):
    """Adapter PicoBlade (wires leave along -Z) to the controller PicoBlade (wires arrive along -X).

    The bundle drops in front of the adapter, crosses to a lane above the controller component
    reserve and takes up the finished length in one S-fold (three layers in Z) above the spine
    block. The fold span is solved for the finished length.
    """
    ro = cfg["power_route"]
    xl = r(min(w - side - bundle_r, x1 + 5.2 + radius))
    z0, z1, z2 = ro["layers_z"]
    ys, ye = ro["fold_start_y"], ro["fold_end_y"]

    def pts(span):
        return [list(start), [start[0], start[1], z0], [xl, ro["lane_entry_y"], z0], [xl, ys + span, z0], [xl, ys + span, z1],
                [xl, ys, z1], [xl, ys, z2], [xl, ye, z2], [xl, yp, zc], [r(x1 + 5.2), yp, zc]]
    lo, hi = 2 * radius, ye - ys - radius
    span = solve(lambda v: fillet_path(pts(v), radius)[1], lo, hi, target)
    status = "solved for the nominal finished length"
    if span is None:
        short = fillet_path(pts(lo), radius)[1] > target
        span = lo if short else hi
        status = ("shortest fold at the preferred radius is longer than nominal; compare with the finished-length tolerance" if short
                  else "longest fold reached; cable longer than the route")
    P = pts(r(span))
    segs, length, rmin = fillet_path(P, radius)
    return {"points": P, "radius": radius, "length": r(length), "min_radius": r(rmin), "fold_span": r(span), "status": status,
            "end_bend_room": r(xl - (x1 + 5.2)), "length_range_of_this_stowage": [r(fillet_path(pts(lo), radius)[1]), r(fillet_path(pts(hi), radius)[1])]}


HARD = ["lead_side", "body_side", "nut_front"]


def row_for(p, width_key, offset, t, leads):
    cases = {c: S.transverse_case(p, width_key, offset, t, leads, c) for c in ("worst", "nominal", "best")}
    verdict, drivers = S.classify(cases["worst"], cases["best"], HARD)
    return {
        "width_key": width_key, "panel_width": p["parameters"][width_key]["nominal"], "offset": offset,
        "pcb_thickness": t, "leads": leads, "verdict": verdict, "failing_at_worst": drivers,
        "worst_min": r(min(cases["worst"]["margins"][k] for k in HARD)),
        "nominal_min": r(min(cases["nominal"]["margins"][k] for k in HARD)),
        "worst": cases["worst"]["margins"], "nominal": cases["nominal"]["margins"],
        "lead_long_enough_for_trim": cases["worst"]["lead_long_enough_for_trim"],
    }


def sweep_2hp(p, d):
    sw = d["candidate_selection"]["offset_sweep"]
    rows = []
    for t in p["parameters"]["pcb_thickness_options"]["values"]:
        for off in frange(sw["start"], sw["stop"], sw["step"]):
            rows.append(row_for(p, "panel_width_2hp", off, t, "trimmed"))
    return rows


def select_2hp(p, rows):
    pref = p["parameters"]["nut_edge_margin_required"]["preferred"]
    req = p["parameters"]["nut_edge_margin_required"]["nominal"]
    ok = [x for x in rows if x["nominal_min"] >= -1e-9 and x["nominal"]["nut_front"] + req >= pref - 1e-9 and x["lead_long_enough_for_trim"]]
    for x in ok:
        x["nut_preference_met_at_worst"] = x["worst"]["nut_front"] + req >= pref - 1e-9
    ok.sort(key=lambda x: (x["worst_min"], x["nominal_min"], x["pcb_thickness"]), reverse=True)
    return ok[0], len(ok)


def select_3hp(p):
    out = []
    for t in sorted(p["parameters"]["pcb_thickness_options"]["values"], reverse=True):
        row = row_for(p, "panel_width_3hp", 0.0, t, "untrimmed")
        out.append(row)
        if row["verdict"] == S.FEASIBLE:
            return row, out
    raise RuntimeError("no 3HP row feasible")


def break_even(p, row):
    """Single-input values at which each failing worst-corner margin reaches zero (others unchanged).

    A sensitivity for the evidence still needed, not a result: each value is what one input
    would have to be, alone, for that margin to close.
    """
    out = []

    def margin(q, key):
        return S.transverse_case(q, row["width_key"], row["offset"], row["pcb_thickness"], row["leads"], "worst")["margins"][key]

    def solve(key, setter, lo, hi, label, unit_note):
        base = margin(p, key)
        if base >= 0:
            return
        f = lambda v: margin(setter(copy.deepcopy(p), v), key)
        flo, fhi = f(lo), f(hi)
        if (flo >= 0) == (fhi >= 0):
            out.append({"margin": key, "input": label, "worst_margin_now": r(base), "closes_within_search": False, "search": [lo, hi], "note": unit_note})
            return
        for _ in range(60):
            mid = (lo + hi) / 2
            if (f(mid) >= 0) == (flo >= 0):
                lo, flo = mid, f(mid)
            else:
                hi = mid
        out.append({"margin": key, "input": label, "worst_margin_now": r(base), "break_even_value": r((lo + hi) / 2), "closes_within_search": True, "note": unit_note})

    def set_axis_max(q, v):
        q["parameters"]["jack_axis_height"]["max"] = v
        return q

    def set_axis_min(q, v):
        q["parameters"]["jack_axis_height"]["min"] = v
        return q

    def set_trim(q, v):
        q["parameters"]["lead_protrusion_trimmed"]["max"] = v
        return q

    def set_hole(q, v):
        q["parameters"]["panel_hole_position_tol"]["nominal"] = v
        return q

    def set_overall_tol(q, v):
        q["parameters"]["jack_overall_height"]["tol"] = v
        return q

    solve("lead_side", set_axis_max, 2.0, 3.4, "jack_axis_height.max (INFERRED, R1 Q1)", "largest axis height that still clears the lead side")
    solve("lead_side", set_trim, 0.0, 1.0, "lead_protrusion_trimmed.max (ASSUMED, R1 Q6)", "largest guaranteed trimmed protrusion")
    solve("lead_side", set_hole, 0.0, 0.1, "panel_hole_position_tol (ASSUMED, R1 Q7)", "largest hole position tolerance")
    solve("body_side", set_axis_min, 2.6, 3.4, "jack_axis_height.min (INFERRED, R1 Q1)", "smallest axis height that still clears the body side")
    solve("body_side", set_overall_tol, 0.0, 0.2, "jack_overall_height.tol (ASSUMED tol band)", "largest overall-height tolerance")
    solve("body_side", set_hole, 0.0, 0.1, "panel_hole_position_tol (ASSUMED, R1 Q7)", "largest hole position tolerance")
    solve("nut_front", set_hole, 0.0, 0.1, "panel_hole_position_tol (ASSUMED, R1 Q7)", "largest hole position tolerance")
    return out


def build():
    p = json.loads((A7 / "study" / "parameters.json").read_text())
    d = json.loads(INPUTS.read_text())
    P = p["parameters"]
    g5 = json.loads((A5 / "mechanical" / "geometry.json").read_text())
    f5 = json.loads((A5 / "front_panel" / "geometry.json").read_text())
    e5 = json.loads((A5 / "electronics" / "placement_and_connectivity.json").read_text())
    sw = fact(SWITCH_FACTS, "fact-a7-pcm13smtr-outline")
    raw = fact(JACK_FACTS, "fact-a7-pj-324m-footprint-positions")
    pins = {f"pin_{n}": {"along": raw[f"pin_{n}_along"], "across": raw[f"pin_{n}_across"]}
            for n in sorted({k.split("_")[1] for k in raw if k.startswith("pin_") and k.endswith("_along")})}

    # ---- candidates -------------------------------------------------------------------
    rows = sweep_2hp(p, d)
    sel2, n_ok = select_2hp(p, rows)
    sel3, rows3 = select_3hp(p)
    r1_rows = {f"{x['arrangement']}|{x['pcb_thickness']}|{x['leads']}": x["verdict"] for x in S.transverse(p)}
    best_worst_any = max(rows, key=lambda x: x["worst_min"])

    # ---- axial (Z) stack --------------------------------------------------------------
    ax_opt = d["axial_option"]["selected"]
    nut_id = d["nut"]["selected"]
    axial_rows = {(x["option"], x["nut"]): x for x in S.axial(p)}
    ax_sel = axial_rows[(ax_opt, nut_id)]
    ax_alt = axial_rows[(d["axial_option"]["alternate"], nut_id)]
    opt = next(o for o in p["axial_options"] if o["id"] == ax_opt)
    pocket = P["rear_pocket_depth"]["nominal"] if opt["rear_pocket"] else 0.0
    body_front_z = -pocket + P["front_body_gap"]["nominal"]
    body_rear_nom = body_front_z + P["jack_body_depth"]["nominal"]
    body_rear_max = body_rear_nom + P["jack_body_depth"]["tol"]
    pin_z = {k: r(body_front_z + v["along"]) for k, v in pins.items() if k.startswith("pin_")}
    c = d["controller"]
    pcb_z0 = c["front_gap_to_pmma"]["nominal"]
    pcb_rear_min = max(max(pin_z.values()) + c["terminal_to_rear_edge"]["nominal"], body_rear_max)

    o5, l5 = g5["optical"], g5["leaf"]
    optical_stack = {
        "rear_limit": g5["rear_limit"],
        "rear_allowance_a5": r(g5["rear_limit"] - o5["rear_max"]),
        "cap_behind_leaf": r(o5["rear_max"] - l5["z"][1]),
        "leaf_depth": l5["depth"],
        "front_allowance_skin_to_leaf": r(l5["z"][0] - o5["skin_z"][0]),
    }
    optical_depth = r(optical_stack["cap_behind_leaf"] + optical_stack["leaf_depth"] + optical_stack["front_allowance_skin_to_leaf"])
    optical_front = r(g5["rear_limit"] - optical_stack["rear_allowance_a5"] - optical_depth)
    pcb_z1 = r(optical_front - c["rear_gap_to_optical_volume"]["nominal"])
    z_stack = {
        "pmma_front_z": -P["panel_thickness"]["nominal"], "pmma_rear_z": 0.0,
        "axial_option": ax_opt, "rear_pocket_depth": pocket, "rear_pocket_clearance": d["axial_option"]["pocket_clearance_around_body"], "jack_body_front_z": r(body_front_z),
        "jack_body_rear_z_nominal": r(body_rear_nom), "jack_body_rear_z_max": r(body_rear_max),
        "barrel_tip_z_nominal": r(body_front_z - P["jack_barrel_projection"]["nominal"]),
        "nut_z": [r(-P["panel_thickness"]["nominal"] - p["nuts"][nut_id]["thickness"]), -P["panel_thickness"]["nominal"]],
        "terminal_z": pin_z,
        "controller_pcb_z": [pcb_z0, pcb_z1],
        "controller_rear_edge_minimum_from_jack": r(pcb_rear_min),
        "controller_rear_edge_slack": r(pcb_z1 - pcb_rear_min),
        "front_pin_to_pcb_front_edge": r(min(pin_z.values()) - pcb_z0),
        "optical_stack": optical_stack, "optical_depth_required": optical_depth,
        "optical_volume_z": [optical_front, o5["rear_max"]], "controller_volume_z": [0.0, pcb_z1],
        "gap_controller_to_optical": c["rear_gap_to_optical_volume"]["nominal"],
        "a5_leaf_z": l5["z"], "installed_depth_target": g5["rear_limit"],
        "thread_engagement_selected": {"option": ax_opt, "nut": nut_id, "verdict": ax_sel["verdict"],
                                       "worst_engaged": ax_sel["cases"]["worst"]["engaged"], "nominal_engaged": ax_sel["cases"]["nominal"]["engaged"]},
        "thread_engagement_alternate": {"option": ax_alt["option"], "nut": nut_id, "verdict": ax_alt["verdict"],
                                        "worst_engaged": ax_alt["cases"]["worst"]["engaged"], "nominal_engaged": ax_alt["cases"]["nominal"]["engaged"]},
    }

    # ---- Y layout ------------------------------------------------------------------------
    y_bottom = g5["rail_body_y"][1]
    y_top = c["y_top"]["nominal"]
    sw_body_y = [r(y_bottom - sw["actuator_projection_beyond_body"] - sw["body_depth"]), r(y_bottom - sw["actuator_projection_beyond_body"])]
    j = d["jacks"]
    near_nom, far_nom = P["jack_axis_to_edge_near"]["nominal"], P["jack_axis_to_edge_far"]["nominal"]
    # Y clearances use the body tolerance envelope about the axis (R1: near 5.4 +/-0.2 MIRROR, far 6.1 +/-0.4 DERIVED-MIRROR).
    near = near_nom + P["jack_axis_to_edge_near"].get("tol", 0.0)
    far = far_nom + P["jack_axis_to_edge_far"].get("tol", 0.0)
    step = j["y_round_down_to"]
    # +across on the drawing points toward the pin-4/pin-5 side, which is the 5.4 (near) side (#24 review reading).
    # Pins are placed at Y = axis - across, so pin 2 faces +Y (the switch) and the far (6.1) edge is the one toward +Y.
    pin_y_rel = {k: r(-v["across"]) for k, v in pins.items() if k.startswith("pin_")}
    near_toward_plus_y = (pin_y_rel["pin_4"] > 0) == (j["near_edge_side_pins"] == "pin_4/pin_5")
    lo, hi = (far, near) if near_toward_plus_y else (near, far)
    lo_nom, hi_nom = (far_nom, near_nom) if near_toward_plus_y else (near_nom, far_nom)
    sfp = d["setting_switch"]["footprint"]
    peg_line = (sw_body_y[0] + sw_body_y[1]) / 2
    pad_y0 = r(peg_line - sfp["signal_pad_reach_from_peg_line"]["nominal"])
    y2 = math.floor((sw_body_y[0] - j["body_to_switch_gap"]["nominal"] - hi) / step + 1e-9) * step
    pk_clr = d["axial_option"]["pocket_clearance_around_body"] if pocket > 0 else 0.0
    need = near + far + 2 * pk_clr + 2 * j["label_gap_to_body"]["nominal"] + j["label_cap_height"]["nominal"]
    pitch = max(j["pitch"]["minimum"], math.ceil(need / j["pitch"]["round_up_to"] - 1e-9) * j["pitch"]["round_up_to"])
    y1 = y2 - pitch
    jack_y = [r(y1), r(y2)]
    body_y = [[r(y - lo), r(y + hi)] for y in jack_y]
    body_y_nom = [[r(y - lo_nom), r(y + hi_nom)] for y in jack_y]
    sw_zc = d["setting_switch"]["z_centre"]["nominal"]
    switch = {
        "part": d["setting_switch"]["part"], "body_y": sw_body_y,
        "body_z": [r(sw_zc - sw["body_length"] / 2), r(sw_zc + sw["body_length"] / 2)],
        "height_above_pcb": sw["height_above_pcb"], "actuator_width_z": sw["actuator_width"],
        "actuator_y": [sw_body_y[1], r(y_bottom)], "actuator_travel_per_position": sw["travel_per_position"],
        "actuator_positions_z": [r(sw_zc - sw["travel_per_position"]), r(sw_zc), r(sw_zc + sw["travel_per_position"])],
        "peg_pitch": sw["peg_pitch"], "peg_diameter": sw["peg_diameter"],
        "access_from": "+Y (below the module), module out of the rack", "label": d["setting_switch"]["label"],
        "gap_to_lower_jack_body": r(sw_body_y[0] - body_y[1][1]),
        "gap_to_lower_jack_body_nominal": r(sw_body_y[0] - body_y_nom[1][1]),
        "footprint_y": [pad_y0, r(y_bottom)], "footprint_z": [r(sw_zc - sfp["retention_pad_half_span"]["nominal"]), r(sw_zc + sfp["retention_pad_half_span"]["nominal"])],
        "footprint_source": sfp["source"],
        "pad_gap_to_lower_jack_body": r(pad_y0 - body_y[1][1]),
        "gap_basis": "worst value uses the jack body tolerance envelope; required gap is design-inputs jacks.body_to_switch_gap",
    }
    lab_off = lo + pk_clr + j["label_gap_to_body"]["nominal"] + j["label_cap_height"]["nominal"] / 2
    labels = [{"text": t, "y": r(y - lab_off), "cap_height": j["label_cap_height"]["nominal"]} for t, y in zip(j["labels"], jack_y)]
    sup = d["supports"]
    y_layout = {
        "rail_body_y": g5["rail_body_y"], "controller_pcb_y": [y_top, y_bottom], "jack_y": jack_y, "jack_function": j["functions"],
        "jack_body_y": body_y, "jack_body_y_basis": f"tolerance envelope about the axis: far {r(far)} / near {r(near)} (nominal {far_nom} / {near_nom}; MIRROR / DERIVED-MIRROR)",
        "jack_body_y_nominal": body_y_nom, "jack_pin_y_offset_from_axis": pin_y_rel,
        "jack_orientation": ("pin 2 and the 6.1 mm (far) edge face +Y toward the switch; pins 4/5 and the 5.4 mm (near) edge face -Y" if near_toward_plus_y is False else "pin 4/5 and the 5.4 mm edge face +Y")
                            + ". Which side is near follows the #24 review reading of the drawing; the 'across' sign is read from the drawing view and must be re-checked against the component side (fact-a7-pj-324m-footprint-positions); pin functions INFERRED (R1 Q2)", "body_gap": r(body_y[1][0] - body_y[0][1]),
        "nut_gap": r(pitch - p["nuts"][nut_id]["od"]), "pitch": r(pitch), "pitch_required_for_labels": r(need),
        "label_clearance_to_bodies": [r((y - lab_off - j["label_cap_height"]["nominal"] / 2) - (yb[1] + pk_clr)) if i else None for i, (y, yb) in enumerate(zip(jack_y, [[0, 0]] + body_y[:-1]))],
        "upper_body_to_controller_slot": r(body_y[0][0] - sup["controller_slot_y"]["values"][1]),
        "a5_jack_y": f5["controls"]["jack_y"], "shift_from_a5": [r(a - b) for a, b in zip(jack_y, f5["controls"]["jack_y"])],
        "labels": labels,
    }

    # ---- A5 controller component reference (capacity, not a placement) -----------------
    ctrl5 = next(b for b in e5["boards"] if b["name"] == "controller")
    small = [cc for cc in ctrl5["components"] if cc.get("fitted") and cc["type"] not in ("JACK", "SW", "SH4", "PWR3", "IDC", "TP")]
    reserve_h = r(max(cc["height_max_mm"] for cc in small) + c["component_reserve_margin"]["nominal"])
    a5_area = r(sum(cc["body_size_mm"][0] * cc["body_size_mm"][1] for cc in small))

    # ---- per-variant X placement ---------------------------------------------------------
    side = P["side_clearance_required"]["nominal"]
    ar = d["adapter_relocation"]
    dz = ar["z_shift"]["nominal"]
    assert abs(ar["cap_spacer"]["height"] + dz) < 1e-9, "cap_spacer.height must equal -adapter_relocation.z_shift (the boss fills exactly the gap the move opens)"
    adapter = {"y": g5["adapter"]["y"], "width": g5["adapter"]["width"], "thickness": g5["adapter"]["thickness"], "power_pinrow_y": g5["adapter"]["power_pinrow_y"],
               "a5_front_z": g5["adapter"]["front_z"], "z_shift": dz, "front_z": r(g5["adapter"]["front_z"] + dz),
               "rear_z": r(g5["adapter"]["front_z"] + dz + g5["adapter"]["thickness"]),
               "gap_rear_to_leaf_front": r(l5["z"][0] - (g5["adapter"]["front_z"] + dz + g5["adapter"]["thickness"])),
               "cap_spacer_z": [r(g5["adapter"]["front_z"] + dz + g5["adapter"]["thickness"]), r(g5["adapter"]["front_z"] + g5["adapter"]["thickness"])],
               "cap_spacer_radius": ar["cap_spacer"]["radius"], "reason": ar["reason"], "confidence": ar["z_shift"]["confidence"]}
    h_nom = P["jack_axis_height"]["nominal"]
    m2 = sup["m2"]
    variants = {}
    for name, row in (("2hp", sel2), ("3hp", sel3)):
        w = row["panel_width"]
        x_axis = r(w / 2 + row["offset"])
        seat = r(x_axis - h_nom)
        t = row["pcb_thickness"]
        lead_below = t + P["lead_protrusion_trimmed"]["nominal"] if row["leads"] == "trimmed" else P["jack_terminal_projection"]["nominal"]
        x_pcb = [r(seat - t), seat]
        clr = sup["slot_clearance"]["nominal"]
        inner = [side, r(w - side)]
        screw_x = r((x_pcb[1] + clr + inner[1]) / 2)
        sh_h, pico_h = 2.95, 5.2  # A5-sourced mated heights (A5 build_mechanical jst_local / PicoBlade 5.2)
        checks = {
            "lead_tip_x_nominal": r(seat - lead_below), "lead_side_nominal_margin": r(seat - lead_below - side),
            "body_top_x_nominal": r(seat + P["jack_overall_height"]["nominal"]),
            "body_side_nominal_margin": r(inner[1] - seat - P["jack_overall_height"]["nominal"]),
            "component_face_height_budget": r(inner[1] - x_pcb[1]),
            "component_reserve_height": reserve_h,
            "component_reserve_fits": inner[1] - x_pcb[1] >= reserve_h,
            "sh4_mated_height": sh_h, "sh4_fits": inner[1] - x_pcb[1] >= sh_h,
            "picoblade_mated_height": pico_h,
            "picoblade_wire_bend_room": r(inner[1] - x_pcb[1] - pico_h),
            "picoblade_untrimmed_tail_margin": r(x_pcb[1] - 2.3 - side),
            "picoblade_tail_needs_trim": x_pcb[1] - 2.3 < side,
            "spine_screw_nut_clear_of_pcb": r(screw_x - m2["nut_af"] / math.sqrt(3) - x_pcb[1] - clr),
            "spine_screw_nut_clear_of_side": r(inner[1] - screw_x - m2["nut_af"] / math.sqrt(3)),
            "solder_side_room_for_fork_wall": r(x_pcb[0] - clr - side),
            "fork_wall_fits_solder_side": x_pcb[0] - clr - side >= sup["fork_wall"]["nominal"],
            "nut_edge_nominal": r(w / 2 - abs(row["offset"]) - p["nuts"][nut_id]["od"] / 2),
            "pcb_x_within_inner": x_pcb[0] >= side,
        }
        hz = c["solder_face_low_profile_zone"]["max_height"]
        qz = copy.deepcopy(p)
        qz["parameters"]["lead_protrusion_trimmed"].update(nominal=hz, max=hz, min=hz)
        zone = {k: S.transverse_case(qz, row["width_key"], row["offset"], t, "trimmed", k)["margins"]["lead_side"] for k in ("worst", "nominal")}
        lead = {k: row[k]["lead_side"] for k in ("worst", "nominal")}
        checks["solder_face_zone_height"] = hz
        checks["solder_face_zone_margin_worst"] = zone["worst"]
        checks["solder_face_zone_margin_nominal"] = zone["nominal"]
        checks["solder_face_zone_below_lead_tips"] = all(zone[k] >= lead[k] - 1e-9 for k in zone)
        cab = d["cables"]
        lh, ph = c["led_header"], c["power_header"]
        power_args = (w / 2, x_pcb[1], w, side, cab, [r(w / 2), g5["adapter"]["power_pinrow_y"], r(adapter["front_z"] - 5.2)], ph["y"], ph["z_centre"])
        routes = {
            "controller_to_left_leaf_sh4": led_route(w / 2, x_pcb[1], cab, r(l5["y"][0] + l5["header_origins_local_v"][0] + 4.575), r(l5["z"][0] + 4.5),
                                                     r(lh["y"] + 1.675 + 2.0), cab["sh_finished_length"]["nominal"]),
            "adapter_to_controller_power": power_route(w / 2, x_pcb[1], w, side, cab, [r(w / 2), g5["adapter"]["power_pinrow_y"], r(adapter["front_z"] - 5.2)],
                                                       ph["y"], ph["z_centre"], cab["power_finished_free_span"]["nominal"], cab["preferred_bend_radius"]["nominal"], cab["power_bundle_radius"]["nominal"]),
        }
        routes["controller_to_left_leaf_sh4"]["bundle_radius"] = cab["sh_bundle_radius"]["nominal"]
        routes["adapter_to_controller_power"]["bundle_radius"] = cab["power_bundle_radius"]["nominal"]
        pw = routes["adapter_to_controller_power"]
        fl = cab["power_finished_free_span"]
        pw["a5_cable_nominal_reaches"] = pw["length_range_of_this_stowage"][0] <= fl["nominal"] + 1e-9
        pw["a5_cable_band_fits"] = pw["length_range_of_this_stowage"][0] <= fl["nominal"] - fl["tol"] + 1e-9 and fl["nominal"] + fl["tol"] <= pw["length_range_of_this_stowage"][1]
        routes["controller_to_left_leaf_sh4"]["status"] = "solved for the nominal finished length"
        checks["power_route_end_bend_room"] = routes["adapter_to_controller_power"]["end_bend_room"]
        checks["power_route_min_radius"] = routes["adapter_to_controller_power"]["min_radius"]
        checks["power_route_bend_at_least_preferred"] = routes["adapter_to_controller_power"]["min_radius"] >= cab["preferred_bend_radius"]["nominal"] - 1e-9
        checks["power_route_a5_cable_nominal_reaches"] = routes["adapter_to_controller_power"]["a5_cable_nominal_reaches"]
        checks["led_route_min_radius"] = routes["controller_to_left_leaf_sh4"]["min_radius"]
        # rear pocket across X must take the body over the INFERRED axis band and the overall-height tolerance
        pclr = d["axial_option"]["pocket_clearance_around_body"]
        a_ = P["jack_axis_height"]
        pocket_x = [r(x_axis - a_["max"] - pclr), r(x_axis - a_["min"] + P["jack_overall_height"]["nominal"] + P["jack_overall_height"]["tol"] + pclr)]
        checks["rear_pocket_wall_to_panel_edge"] = r(min(pocket_x[0], w - pocket_x[1]))
        variants[name] = {
            "_power_args": power_args,
            "rear_pocket_x": pocket_x,
            "rear_pocket_x_basis": f"axis band {a_['min']}-{a_['max']} (INFERRED) and overall height {P['jack_overall_height']['nominal']} +/- {P['jack_overall_height']['tol']}, plus {pclr} clearance",
            "routes": routes,
            "panel_width": w, "selection": row, "x_axis": x_axis,
            "jack_axis_height_used": {"value": h_nom, "confidence": "INFERRED", "band": [P["jack_axis_height"]["min"], P["jack_axis_height"]["max"]]},
            "jack_seat_x": seat, "controller_pcb_x": x_pcb, "pcb_thickness": t, "leads": row["leads"],
            "inner_envelope_x": inner, "front_screw_x": {"20.5": r(w / 2), "60.8": screw_x},
            "checks": checks,
        }

    # ---- A7 power-cable length requirement (R2-C5, for #8) --------------------------------
    pcr = d["cables"]["power_cable_requirement"]
    tol, margin = pcr["harness_tolerance"]["nominal"], pcr["short_side_margin"]["nominal"]
    lo_all = max(v["routes"]["adapter_to_controller_power"]["length_range_of_this_stowage"][0] for v in variants.values())
    hi_all = min(v["routes"]["adapter_to_controller_power"]["length_range_of_this_stowage"][1] for v in variants.values())
    n_req = float(math.ceil(lo_all + margin + tol))
    power_cable = {
        "finished_free_span_nominal": n_req, "tolerance": tol, "tolerance_confidence": pcr["harness_tolerance"]["confidence"],
        "band": [r(n_req - tol), r(n_req + tol)], "stowage": "one S-fold above the spine block, fold span solved per width",
        "stowage_length_range_both_widths": [lo_all, hi_all], "short_side_margin": margin,
        "fits_both_widths": n_req - tol >= lo_all + margin - 1e-9 and n_req + tol <= hi_all + 1e-9,
        "a5_cable": {"nominal": cab["power_finished_free_span"]["nominal"], "tol": cab["power_finished_free_span"]["tol"],
                     "fits": (cab["power_finished_free_span"]["nominal"] - cab["power_finished_free_span"]["tol"] >= lo_all + margin - 1e-9
                              and cab["power_finished_free_span"]["nominal"] + cab["power_finished_free_span"]["tol"] <= hi_all + 1e-9),
                     "rule": "same as fits_both_widths: band low end >= shortest stowage + short_side_margin, band high end <= longest stowage"},
        "taut_reference": "shortest S-fold the route allows (fold span = two bend radii); the cable is never pulled tighter",
        "physical_measurement": "MISSING: no cable has been routed or measured; plug strain relief, wire stiffness and the real fold shape are not known (#8)",
    }
    for v in variants.values():
        args = v.pop("_power_args")
        rt = power_route(*args, n_req, cab["preferred_bend_radius"]["nominal"], cab["power_bundle_radius"]["nominal"])
        old = v["routes"]["adapter_to_controller_power"]
        for k in ("bundle_radius", "a5_cable_nominal_reaches", "a5_cable_band_fits"):
            rt[k] = old[k]
        rt["cable_band_lengths"] = [r(fillet_path(power_route(*args, n_req + s_ * tol, cab["preferred_bend_radius"]["nominal"], cab["power_bundle_radius"]["nominal"])["points"], cab["preferred_bend_radius"]["nominal"])[1]) for s_ in (-1, 1)]
        v["routes"]["adapter_to_controller_power"] = rt
        v["checks"]["power_route_end_bend_room"] = rt["end_bend_room"]
        v["checks"]["power_route_min_radius"] = rt["min_radius"]
        v["checks"]["power_route_bend_at_least_preferred"] = rt["min_radius"] >= cab["preferred_bend_radius"]["nominal"] - 1e-9

    # ---- keep-outs on the controller (handoff to R4) ------------------------------------
    sv = sup["controller_slot_y"]["values"]
    fy = sup["bottom_fork_y"]["values"]
    fork_z0 = r(pcb_z1 - sup["fork_engagement"]["nominal"])
    keepouts = [
        {"id": "spine-slot", "faces": ["+X", "-X"], "y": [y_top, sv[1]], "z": [pcb_z0, sup["controller_slot_height"]["nominal"]], "reason": "printed spine slot captures the PCB front edge"},
        {"id": "optical-fork", "faces": ["+X", "-X"], "y": fy, "z": [fork_z0, pcb_z1], "reason": "bottom optical cap tongue straddles the rear edge"},
        {"id": "setting-switch", "faces": ["+X"], "y": switch["footprint_y"], "z": switch["footprint_z"], "reason": "PCM13SMTR body, actuator and its signal/retention pads at the bottom edge"},
        {"id": "switch-access", "faces": ["+X"], "y": [sw_body_y[1], y_bottom], "z": [r(switch["actuator_positions_z"][0] - sw["actuator_width"] / 2 - 0.5), r(switch["actuator_positions_z"][2] + sw["actuator_width"] / 2 + 0.5)], "reason": "actuator travel plus tool clearance; nothing taller than the switch between actuator and board edge"},
    ]
    lhd = c["led_header"]
    keepouts.append({"id": "sh4-header", "faces": ["+X"], "y": [r(lhd["y"] - 2.575), r(lhd["y"] + 1.675 + 2.0)], "z": [r(lhd["z_centre"] - 3.0 - 0.5), pcb_z1],
                     "reason": "SH4 side-entry housing and its mated plug handle"})
    ph = c["power_header"]
    keepouts.append({"id": "picoblade-header", "faces": ["+X"], "y": [r(ph["y"] - 2.05), r(ph["y"] + 1.15)], "z": [r(ph["z_centre"] - 2.75), r(ph["z_centre"] + 2.75)],
                     "reason": "PicoBlade vertical header and mated plug"})
    keepouts.append({"id": "picoblade-tails", "faces": ["-X"], "y": [r(ph["y"] - 2.05), r(ph["y"] + 1.15)], "z": [r(ph["z_centre"] - 2.75), r(ph["z_centre"] + 2.75)],
                     "reason": "PicoBlade THT tails and fillets on the solder face (cut to the jack trim rule in 2HP)"})
    lh = c["led_header"]
    fold = max(v["routes"]["controller_to_left_leaf_sh4"]["fold_y"] for v in variants.values())
    br = d["cables"]["sh_bundle_radius"]["nominal"]
    keepouts.append({"id": "led-cable-lane", "faces": ["+X"], "y": [r(lh["y"] - 2.575), r(fold + d["cables"]["preferred_bend_radius"]["nominal"] + br)],
                     "z": [r(d["cables"]["led_route"]["return_z"] - br - 0.2), pcb_z1], "reason": "SH4 header and the returning LED harness lie over the component face"})
    for i, y in enumerate(jack_y):
        keepouts.append({"id": f"jack-{j['functions'][i].split()[-1].lower()}", "faces": ["+X"], "y": body_y[i], "z": [pcb_z0, r(body_rear_max)], "reason": "PJ-324M body footprint"})
        fr = 1.0  # CAD solder-fillet allowance radius 0.75 plus 0.25
        keepouts.append({"id": f"jack-{j['functions'][i].split()[-1].lower()}-leads", "faces": ["-X"], "y": [r(y + min(pin_y_rel.values()) - fr), r(y + max(pin_y_rel.values()) + fr)],
                         "z": [pcb_z0, r(max(pin_z.values()) + fr)], "reason": "terminal fillets only on the solder face (2HP lead-side margin)"})
    area_total = (y_bottom - y_top) * (pcb_z1 - pcb_z0)
    area_keep = union_area([(k["y"], k["z"]) for k in keepouts if "+X" in k["faces"]])
    controller = {
        "outline_y": [y_top, y_bottom], "outline_z": [pcb_z0, pcb_z1],
        "outline_area_mm2": r(area_total), "component_face_free_area_mm2_approx": r(area_total - area_keep),
        "a5_controller_board_area_mm2": r(ctrl5["width"] * ctrl5["height"]),
        "a5_small_component_body_area_mm2": a5_area,
        "power_header": {**c["power_header"], "pin_row_axis": "Z", "mated_height_x": 5.2, "y_extent": [r(c["power_header"]["y"] - 2.05), r(c["power_header"]["y"] + 1.15)], "z_extent": [r(c["power_header"]["z_centre"] - 2.75), r(c["power_header"]["z_centre"] + 2.75)]},
        "led_header": {**c["led_header"], "pin_row_axis": "Z", "housing_y": [r(c["led_header"]["y"] - 2.575), r(c["led_header"]["y"] + 1.675)], "mated_handle_y_max": r(c["led_header"]["y"] + 1.675 + 2.0), "housing_z": [r(c["led_header"]["z_centre"] - 3.0), r(c["led_header"]["z_centre"] + 3.0)], "height_x": 2.95},
        "keepouts": keepouts,
        "solder_face_low_profile_zone": {**c["solder_face_low_profile_zone"], "face": "-X",
                                         "allowed_region": "controller outline minus every keep-out that lists the -X face",
                                         "excluded_keepouts": [k["id"] for k in keepouts if "-X" in k["faces"]],
                                         "margins": {n: {"worst": v["checks"]["solder_face_zone_margin_worst"], "nominal": v["checks"]["solder_face_zone_margin_nominal"],
                                                         "jack_lead_worst": v["selection"]["worst"]["lead_side"], "never_beyond_jack_lead_tips": v["checks"]["solder_face_zone_below_lead_tips"]}
                                                     for n, v in variants.items()},
                                         "rule": "parts on the solder face must stay within max_height of the board; the zone is computed with R1's lead-side margin, replacing the trimmed lead protrusion by max_height"},
        "solder_side_rule": c["solder_side_rule"],
        "power_input_on_controller": "3-wire PicoBlade from the A5-style separate power adapter (keyed IDC10 stays on the adapter)",
        "why_separate_adapter": f"a vertical keyed IDC10 header body is 8.9 mm tall (A5 C5665 maximum envelope); on the perpendicular board it would need {8.9} mm of X but the 2HP component face offers {variants['2hp']['checks']['component_face_height_budget']} mm",
    }

    # ---- verdicts -----------------------------------------------------------------------
    wd = d["width_decision"]
    working, open_ = wd["working_candidate"], wd["open_candidate"]
    sel_by = {"2hp": sel2, "3hp": sel3}
    describe = {"2hp": f"2hp offset {sel2['offset']} mm toward the body side, {sel2['pcb_thickness']} mm FR-4, trimmed leads",
                "3hp": f"3hp centred, {sel3['pcb_thickness']} mm FR-4, untrimmed leads"}
    decision = {
        "default_variant": working,
        "variants_generated": ["3hp", "2hp"],
        "working_candidate": describe[working],
        "working_verdict": sel_by[working]["verdict"],
        "open_candidate": describe[open_],
        "open_verdict": sel_by[open_]["verdict"],
        "open_failing_at_worst": sel_by[open_]["failing_at_worst"],
        "open_worst_margins": {k: sel_by[open_]["worst"][k] for k in ("lead_side", "body_side", "nut_front")},
        "confidence": wd["confidence"], "source": wd["source"], "reasons": wd["reasons"], "reopen_2hp_when": wd["reopen_2hp_when"],
        "no_2hp_row_passes_worst_corner": best_worst_any["worst_min"] < 0,
        "best_2hp_worst_min_any_row": {"offset": best_worst_any["offset"], "pcb_thickness": best_worst_any["pcb_thickness"], "worst_min": best_worst_any["worst_min"]},
        "statement": ("3HP is the working candidate and the default for the generated artwork, supports and CAD. "
                      "2HP is not declared infeasible: the selected 2HP arrangement clears every nominal transverse margin, "
                      "but its worst-corner margins stay negative, driven by the INFERRED jack-axis height and the ASSUMED lead trim and hole tolerances. "
                      "It stays a fully parameterized open candidate and reopens on the evidence in the break-even table. "
                      "The controller outline in Y-Z is common to both widths."),
    }
    return {
        "schema_version": 1, "generator": "scripts/a7_mechanical_layout.py",
        "inputs": ["engineering/a7/study/parameters.json", ".claude/skills/component-a7-pcm13smtr/facts.json",
                   ".claude/skills/component-a7-pj-324m/facts.json", "engineering/a7/mechanical/design-inputs.json",
                   "engineering/a5/mechanical/geometry.json", "engineering/a5/front_panel/geometry.json",
                   "engineering/a5/electronics/placement_and_connectivity.json"],
        "status": "Provisional digital study. Jack-axis height INFERRED; tolerances marked ASSUMED are unsourced. Not a fit approval, part approval or manufacturing release.",
        "datum": d["datum"],
        "decision": decision,
        "candidates": {
            "selection_rule_2hp": d["candidate_selection"]["rule_2hp"], "selection_rule_3hp": d["candidate_selection"]["rule_3hp"],
            "rows_meeting_2hp_filter": n_ok, "selected_2hp": sel2, "selected_3hp": sel3, "3hp_rows_tried": rows3,
            "sweep_2hp": rows, "r1_verdicts": r1_rows,
            "break_even_2hp": break_even(p, sel2),
        },
        "z_stack": z_stack, "y_layout": y_layout, "switch": switch, "controller": controller, "power_cable_requirement": power_cable,
        "leaf_comparison": leaf_comparison(d, l5, z_stack),
        "variants": variants,
        "supports": {
            "front_screw_y": sup["front_screw_y"]["values"], "m2": m2,
            "spine": {"rib_width": sup["spine_rib_width"]["nominal"], "rib_height": sup["spine_rib_height"]["nominal"],
                      "slot_y": sv, "slot_height": sup["controller_slot_height"]["nominal"], "slot_clearance": sup["slot_clearance"]["nominal"],
                      "post_radius": sup["adapter_post_radius"]["nominal"], "post_top_z": adapter["front_z"], "post_nut_z": [r(adapter["front_z"] - 3.4), r(adapter["front_z"] - 1.8)]},
            # A5 seats the top-cap screw head at Z 27.8 and leaves 2.2 mm of thread past the post nut; A7 keeps both.
            "top_cap_screw": {"head_seat_z": 27.8, "tip_z": r(adapter["front_z"] - 3.4 - 2.2), "length": r(27.8 - (adapter["front_z"] - 3.4 - 2.2)),
                              "designation": f"M2x{27.8 - (adapter['front_z'] - 3.4 - 2.2):.0f}", "protrusion_past_nut": 2.2,
                              "note": "A5 used M2x16 with the nut at Z 14.0; the nut moves with the adapter, so the screw grows by -z_shift"},
            "adapter": adapter,
            "bottom_fork": {"y": fy, "z": [fork_z0, r(o5["skin_z"][0] + 0.6)], "wall": sup["fork_wall"]["nominal"], "engagement": sup["fork_engagement"]["nominal"]},
            "load_path": [
                "Plug insertion (+Z, R1 5-10 N): barrel -> front nut -> PMMA front face -> rack screws.",
                "Plug withdrawal (-Z): body front face -> PMMA pocket floor (rear-pocket) or PMMA rear (plain).",
                "Nut torque: rectangular body in the rear pocket keys rotation (plain alternate: PCB + spine slot, i.e. through the solder joints).",
                "Lateral plug load: barrel in the 6.2 mm hole, clamped by the nut; PCB solder joints only see the residual.",
                "Controller PCB: held by the two clamped jacks at the bottom and the spine slot (Y50-72) at the front edge; Z retention by the jacks.",
                "Setting switch: actuation force along Z into the SMD body and its two pegs -> PCB; force not sourced.",
                "Optical stack: top cap -> M2 into the spine post at Y20.5 (A5 topology); bottom cap located by its fork on the controller rear edge; no jack load enters the optics.",
            ],
        },
        "unresolved": [
            {"id": "Q1", "item": "PJ-324M axis height (INFERRED 3.0, band 2.6-3.4)", "decides": "2HP lead/body margins"},
            {"id": "Q6", "item": "guaranteed trimmed lead protrusion (ASSUMED 0.7/1.0)", "decides": "2HP lead margin"},
            {"id": "Q7", "item": "PMMA thickness and hole position tolerance (ASSUMED)", "decides": "2HP margins, thread engagement"},
            {"id": "Q3", "item": "PJ-324M hole/slot sizes", "decides": f"pin-1 to PCB front edge distance ({z_stack['front_pin_to_pcb_front_edge']} mm centre-to-edge with the rear pocket)"},
            {"id": "Q4", "item": "nut fit on the SOFNG barrel", "decides": "front retention"},
            {"id": "Q8", "item": "rear pocket depth tolerance, appearance and strength", "decides": "selected axial option"},
            {"id": "Q9", "item": "PMMA clamp load / nut torque", "decides": "jack load path"},
            {"id": "Q10", "item": "PCM13SMTR sourcing", "decides": "setting switch part"},
            {"id": "R2-C1", "item": "PicoBlade on the perpendicular board in 2HP: wires leave the mated plug along +X with only the end-bend room shown per variant, and the 2.3 mm tails must be cut like the jack leads", "decides": "power connector choice (R4) and 2HP power route"},
            {"id": "R2-C5", "item": f"A7 power cable: digital requirement {power_cable['finished_free_span_nominal']} +/- {power_cable['tolerance']} mm free span (tolerance {power_cable['tolerance_confidence']}) for the S-fold stowage ({power_cable['stowage_length_range_both_widths'][0]}-{power_cable['stowage_length_range_both_widths'][1]} mm across both widths); the A5 {power_cable['a5_cable']['nominal']:g} +/- {power_cable['a5_cable']['tol']:g} cable {'fits' if power_cable['a5_cable']['fits'] else 'does not fit'}. No cable has been routed or measured", "decides": "power harness part and its length (#8)"},
            {"id": "R2-C6", "item": f"controller-to-leaf SH4 harness: route B moves the unchanged A5 adapter {adapter['z_shift']} mm in Z so the harness S-steps at the leaf plug mouth into a {adapter['gap_rear_to_leaf_front']} mm gap behind the adapter; ray-sampled shading per LED is in verification.json (optical_shading_estimate). Real bend radius, insulation diameter and the lit appearance are not checked", "decides": "harness and adapter mounting (#8), optics"},
            {"id": "R2-C2", "item": "finished SH/PicoBlade cable bend radius, insulation, slack storage and label", "decides": "harness route scenarios (#8)"},
            {"id": "R2-C3", "item": "IDC ribbon side exit beyond the 2HP outline (carried over from A5)", "decides": "2HP neighbour clearance"},
            {"id": "R2-C4", "item": "switch actuation force and tool access with real parts", "decides": "setting switch support"},
        ],
    }


def envelopes(L):
    """Placement envelopes for the controller PCB, in the assembly frame and in a board-local frame for R4."""
    c, z, y, sw = L["controller"], L["z_stack"], L["y_layout"], L["switch"]
    y0, z0 = c["outline_y"][0], c["outline_z"][0]

    def bx(zz):
        return r(zz - z0)

    def by(yy):
        return r(yy - y0)

    def rect(ys, zs):
        return {"assembly_y": ys, "assembly_z": zs, "board_x": [bx(zs[0]), bx(zs[1])], "board_y": [by(ys[0]), by(ys[1])]}

    layer = {"+X": "component face (KiCad F)", "-X": "solder face (KiCad B)"}
    jacks = []
    for i, ay in enumerate(y["jack_y"]):
        pins = [{"pin": k[4:], "assembly_y": r(ay + dy), "assembly_z": z["terminal_z"][k], "board_x": bx(z["terminal_z"][k]), "board_y": by(ay + dy)}
                for k, dy in sorted(y["jack_pin_y_offset_from_axis"].items())]
        jacks.append({"function": y["jack_function"][i], "label": y["labels"][i]["text"], "axis_assembly_y": ay, "axis_board_y": by(ay),
                      "body": rect(y["jack_body_y"][i], [z0, z["jack_body_rear_z_max"]]), "pins": pins})
    swyc = r((sw["body_y"][0] + sw["body_y"][1]) / 2)
    swzc = r((sw["body_z"][0] + sw["body_z"][1]) / 2)
    hdr = {}
    for key in ("power_header", "led_header"):
        h = c[key]
        ys, zs = (h["y_extent"], h["z_extent"]) if key == "power_header" else (h["housing_y"], h["housing_z"])
        hdr[key] = {"part": h["part"], "confidence": h["confidence"], "face": layer["+X"], "pin_row_axis": "board X (assembly Z)", **rect(ys, zs),
                    "height_above_board": h.get("mated_height_x", h.get("height_x"))}
    hdr["led_header"]["opening"] = "toward board +Y (assembly +Y, toward the bottom edge)"
    return {
        "schema_version": 1, "generator": "scripts/a7_mechanical_layout.py", "derived_from": "engineering/a7/mechanical/layout.json",
        "status": L["status"] + " Placement envelopes for routing (R4, #19); hole and pad sizes are not given here.",
        "frames": {
            "assembly": L["datum"],
            "board": "KiCad top view of the controller seen from its component face (+X): board_x = assembly Z - " + str(z0) + " (0 = front edge at the PMMA, + toward the rear), board_y = assembly Y - " + str(y0) + " (0 = top edge, + toward the bottom edge). Solder-face (B) items use the same coordinates.",
        },
        "default_variant": L["decision"]["default_variant"],
        "width_decision": {k: L["decision"][k] for k in ("working_candidate", "working_verdict", "open_candidate", "open_verdict", "confidence")},
        "outline": {**rect(c["outline_y"], c["outline_z"]), "area_mm2": c["outline_area_mm2"], "common_to_both_widths": True},
        "variants": {name: {"panel_width": v["panel_width"], "pcb_thickness": v["pcb_thickness"], "leads": v["leads"], "pcb_assembly_x": v["controller_pcb_x"],
                            "component_face_height_budget": v["checks"]["component_face_height_budget"],
                            "lead_side_nominal_margin": v["checks"]["lead_side_nominal_margin"], "verdict": v["selection"]["verdict"]}
                     for name, v in L["variants"].items()},
        "keepouts": [{"id": k["id"], "faces": [layer[f] for f in k["faces"]], **rect(k["y"], k["z"]), "reason": k["reason"]} for k in c["keepouts"]],
        "jacks": jacks,
        "jack_notes": "Pin positions follow the R1 drawing reading; pin functions are INFERRED (R1 Q2) and hole/slot sizes are not sourced (R1 Q3). The jack body seats on the component face; the axis height above that face is INFERRED " + str(L["variants"]["3hp"]["jack_axis_height_used"]["value"]) + " (band " + str(L["variants"]["3hp"]["jack_axis_height_used"]["band"]) + ").",
        "setting_switch": {"part": sw["part"], "face": layer["+X"], "body": rect(sw["body_y"], sw["body_z"]), "actuator": rect(sw["actuator_y"], [r(sw["actuator_positions_z"][0] - sw["actuator_width_z"] / 2), r(sw["actuator_positions_z"][2] + sw["actuator_width_z"] / 2)]),
                           "pegs": [{"assembly_y": swyc, "assembly_z": r(swzc + s_ * sw["peg_pitch"] / 2), "board_x": bx(swzc + s_ * sw["peg_pitch"] / 2), "board_y": by(swyc), "diameter": sw["peg_diameter"]} for s_ in (-1, 1)],
                           "rule": "actuator flush with the bottom board edge; pads from the C&K land pattern, not given here", "label": sw["label"]},
        "headers": hdr,
        "solder_face_low_profile_zone": c["solder_face_low_profile_zone"],
        "solder_side_rule": c["solder_side_rule"],
    }


def r4_placement_check(E):
    """Compare R4's pre-routing placement with these envelopes: fixed parts by position, every other part by its origin only."""
    P = json.loads(R4_PLACEMENT.read_text())
    pl = {c["ref"]: {"at": c["at_mm"], "rot": c["angle_deg"], "side": c["side"], "pads": c["pads"]} for c in P["components"] if not c["board_only"]}
    face = {"F": "component face (KiCad F)", "B": "solder face (KiCad B)"}
    hd = E["headers"]
    fixed = []

    def row(ref, what, r4, r2, tol=0.011):
        fixed.append({"ref": ref, "what": what, "r4": r4, "r2": r2, "delta": r(r4 - r2), "ok": abs(r4 - r2) <= tol})

    for ref, jk in (("J1", E["jacks"][0]), ("J2", E["jacks"][1])):
        row(ref, "jack axis board_y", pl[ref]["at"][1], jk["axis_board_y"])
        for pin in jk["pins"]:
            pad = pl[ref]["pads"][pin["pin"]]["at_mm"]
            row(ref, f"pin {pin['pin']} board_x", pad[0], pin["board_x"])
            row(ref, f"pin {pin['pin']} board_y", pad[1], pin["board_y"])
    row("J3", "SH4 housing centre board_x", pl["J3"]["at"][0], r(sum(hd["led_header"]["board_x"]) / 2))
    ph = hd["power_header"]
    row("J5", "PicoBlade housing centre (pin 2) board_x", pl["J5"]["pads"]["2"]["at_mm"][0], r(sum(ph["board_x"]) / 2))
    row("J5", "PicoBlade pin row board_y", pl["J5"]["at"][1], r(ph["board_y"][0] + 2.05))
    row("SW1", "switch peg centre board_x", pl["SW1"]["at"][0], r(sum(p["board_x"] for p in E["setting_switch"]["pegs"]) / 2))
    row("SW1", "switch peg line board_y", pl["SW1"]["at"][1], E["setting_switch"]["pegs"][0]["board_y"])
    own = {"J1": ("jack-in", "jack-in-leads"), "J2": ("jack-thru", "jack-thru-leads"), "J3": ("sh4-header", "led-cable-lane"),
           "J5": ("picoblade-header", "picoblade-tails"), "SW1": ("setting-switch", "switch-access")}
    origin_hits, pad_hits = [], []
    for ref, p in sorted(pl.items()):
        for k in E["keepouts"]:
            if face[p["side"]] not in k["faces"] or k["id"] in own.get(ref, ()):
                continue
            def inside(xy, k=k):
                return k["board_x"][0] <= xy[0] <= k["board_x"][1] and k["board_y"][0] <= xy[1] <= k["board_y"][1]
            if inside(p["at"]):
                origin_hits.append({"ref": ref, "side": p["side"], "at": p["at"], "keepout": k["id"]})
            for num, pad in sorted(p["pads"].items()):
                if inside(pad["at_mm"]):
                    pad_hits.append({"ref": ref, "pad": num, "side": p["side"], "at": pad["at_mm"], "keepout": k["id"]})
    edges = P["edges_mm"]
    outline = [min(min(e[0], e[2]) for e in edges), max(max(e[0], e[2]) for e in edges), min(min(e[1], e[3]) for e in edges), max(max(e[1], e[3]) for e in edges)]
    zone = E["solder_face_low_profile_zone"]
    b_side = sorted(ref for ref, p in pl.items() if p["side"] == "B")
    return {
        "status": "ROUTED EXPORT: R4's routed board (PR #30 merged at eb8adeb, board ec810aec; this fit check merged in #33). A later board change needs a new export and SHA",
        "source": dict(R4_PLACEMENT_SOURCE, sha256=hashlib.sha256(R4_PLACEMENT.read_bytes()).hexdigest(), board_sha256=P["board_sha256"],
                       board_thickness=P["thickness_mm"], unconnected=P["unconnected_pcbnew"]),
        "board_outline": outline, "outline_matches": outline == [0.0, E["outline"]["board_x"][1], 0.0, E["outline"]["board_y"][1]],
        "parts": len(pl), "pad_centres_inside_foreign_keepouts": pad_hits,
        "fixed_parts": fixed, "fixed_parts_ok": all(f["ok"] for f in fixed),
        "origins_inside_foreign_keepouts": origin_hits,
        "solder_face_parts": b_side, "solder_face_parts_are_resistors_or_test_pads": all(ref.startswith(("R", "TP")) for ref in b_side),
        "solder_face_max_height": zone["max_height"],
        "not_checked": "footprint courtyards, pad extents and part heights (the export gives origins and pad centres); copper, tracks and vias (#19 DRC)",
    }


def fmt(v):
    return f"{v:+.2f}" if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v)


def report(L):
    d, z, y, sw, c = L["decision"], L["z_stack"], L["y_layout"], L["switch"], L["controller"]
    out = ["# A7 R2 mechanical layout (generated)", "",
           "Generated by `scripts/a7_mechanical_layout.py`. Do not edit by hand.", "", L["status"], "",
           "## Width decision: 3HP is the working candidate, 2HP stays open", "",
           f"- Working candidate (default variant): **{d['working_candidate']}**, verdict **{d['working_verdict']}**.",
           f"- Open candidate: **{d['open_candidate']}**, verdict **{d['open_verdict']}** (worst corner: " + ", ".join(f"{k} {fmt(v)}" for k, v in d["open_worst_margins"].items()) + ").",
           f"- Decision ({d['confidence']}): {d['source']} Reasons: " + "; ".join(d["reasons"]) + ".",
           "- 2HP reopens when: " + "; ".join(d["reopen_2hp_when"]) + ".",
           f"- No 2HP row in the sweep passes the worst corner (best worst-corner minimum {fmt(d['best_2hp_worst_min_any_row']['worst_min'])} at offset {d['best_2hp_worst_min_any_row']['offset']}, {d['best_2hp_worst_min_any_row']['pcb_thickness']} mm).",
           "", d["statement"], "",
           "## What would close 2HP (one input at a time, sensitivity only)", "",
           "| Margin | Input | Worst margin now | Break-even value |", "|---|---|---|---|"]
    for b in L["candidates"]["break_even_2hp"]:
        out.append(f"| {b['margin']} | {b['input']} | {fmt(b.get('worst_margin_now', '-'))} | {b.get('break_even_value', 'does not close alone')} |")
    out += ["", "## Selected rows", "", "| Variant | Offset | PCB | Leads | Lead side (worst / nominal) | Body side (worst / nominal) | Nut edge (worst / nominal) | Verdict |", "|---|---|---|---|---|---|---|---|"]
    for name in ("2hp", "3hp"):
        s = L["variants"][name]["selection"]
        out.append(f"| {name} | {s['offset']} | {s['pcb_thickness']} | {s['leads']} | {fmt(s['worst']['lead_side'])} / {fmt(s['nominal']['lead_side'])} | {fmt(s['worst']['body_side'])} / {fmt(s['nominal']['body_side'])} | {fmt(s['worst']['nut_front'])} / {fmt(s['nominal']['nut_front'])} | {s['verdict']} |")
    out += ["", "## 2HP offset sweep (trimmed leads, worst-corner minimum hard margin)", "", "| Offset | " + " | ".join(f"{t} mm" for t in sorted({x['pcb_thickness'] for x in L['candidates']['sweep_2hp']})) + " |",
            "|---|" + "---|" * len({x['pcb_thickness'] for x in L['candidates']['sweep_2hp']})]
    offs = sorted({x["offset"] for x in L["candidates"]["sweep_2hp"]})
    for o in offs:
        cells = [fmt(x["worst_min"]) for x in sorted([x for x in L["candidates"]["sweep_2hp"] if x["offset"] == o], key=lambda x: x["pcb_thickness"])]
        out.append(f"| {o} | " + " | ".join(cells) + " |")
    out += ["", "## Depth stack (Z, from the PMMA rear)", "",
            f"- Axial option **{z['axial_option']}**: jack body Z {z['jack_body_front_z']}..{z['jack_body_rear_z_nominal']} (max {z['jack_body_rear_z_max']}); thread engagement {z['thread_engagement_selected']['verdict']} ({z['thread_engagement_selected']['worst_engaged']} worst / {z['thread_engagement_selected']['nominal_engaged']} nominal). Alternate {z['thread_engagement_alternate']['option']}: {z['thread_engagement_alternate']['verdict']} ({z['thread_engagement_alternate']['worst_engaged']} worst).",
            f"- Optical stack (A5 retained): cap behind leaf {z['optical_stack']['cap_behind_leaf']} + leaf {z['optical_stack']['leaf_depth']} + skin-to-leaf {z['optical_stack']['front_allowance_skin_to_leaf']} = **{z['optical_depth_required']} mm**, so the rear optical volume is Z {z['optical_volume_z'][0]}..{z['optical_volume_z'][1]} against the {z['installed_depth_target']} mm target.",
            f"- Frontward controller volume Z 0..{z['controller_volume_z'][1]}: PCB Z {z['controller_pcb_z'][0]}..{z['controller_pcb_z'][1]}, {z['gap_controller_to_optical']} mm in front of the optical volume. The jacks need the rear edge at Z >= {z['controller_rear_edge_minimum_from_jack']} (slack {z['controller_rear_edge_slack']}).",
            f"- Front jack terminal (pin 1) is {z['front_pin_to_pcb_front_edge']} mm from the PCB front edge (centre to edge; hole size not sourced, R1 Q3).",
            "", "## Y layout", "",
            f"- Jacks IN / THRU at Y {y['jack_y'][0]} / {y['jack_y'][1]} (A5: {y['a5_jack_y'][0]} / {y['a5_jack_y'][1]}), pitch {y['jack_y'][1]-y['jack_y'][0]}; body gap {y['body_gap']}, nut gap {y['nut_gap']}.",
            f"- Labels: " + ", ".join(f"{q['text']} at Y {q['y']}" for q in y["labels"]) + ". MODE and ON/PGM/CV are removed from the front.",
            f"- Setting switch body Y {sw['body_y'][0]}..{sw['body_y'][1]}, Z {sw['body_z'][0]}..{sw['body_z'][1]}; actuator reaches the controller bottom edge Y {sw['actuator_y'][1]} and is reached from below with the module out of the rack. Gap to the lower jack body {sw['gap_to_lower_jack_body']}.",
            "", "## Controller (Y-Z board, common to both widths)", "",
            f"- Outline Y {c['outline_y'][0]}..{c['outline_y'][1]} x Z {c['outline_z'][0]}..{c['outline_z'][1]} = {c['outline_area_mm2']} mm2 (A5 board {c['a5_controller_board_area_mm2']} mm2; A5 small-part body area {c['a5_small_component_body_area_mm2']} mm2). Free component-face area after keep-outs about {c['component_face_free_area_mm2_approx']} mm2.",
            f"- {c['why_separate_adapter']}.",
            "", "| Keep-out | Faces | Y | Z | Reason |", "|---|---|---|---|---|"]
    for k in c["keepouts"]:
        out.append(f"| {k['id']} | {', '.join(k['faces'])} | {k['y'][0]}..{k['y'][1]} | {k['z'][0]}..{k['z'][1]} | {k['reason']} |")
    out += ["", "## Per-variant X placement (nominal)", "", "| Check | 2HP | 3HP |", "|---|---|---|"]
    for k in L["variants"]["2hp"]["checks"]:
        out.append(f"| {k} | {fmt(L['variants']['2hp']['checks'][k])} | {fmt(L['variants']['3hp']['checks'][k])} |")
    for k in ("x_axis", "jack_seat_x", "controller_pcb_x", "front_screw_x"):
        out.append(f"| {k} | {L['variants']['2hp'][k]} | {L['variants']['3hp'][k]} |")
    out += ["", "## Load path", ""] + [f"- {x}" for x in L["supports"]["load_path"]]
    lc = L["leaf_comparison"]

    def num(v):
        return f"{v:g}"
    out += ["", "## LED leaf: FR-4 (default) versus clear PET FPC on a clear carrier", "", lc["status"], "",
            "| | FR-4 (A5) | PET film + OCA + PC carrier |", "|---|---|---|",
            f"| Stack thickness (mm) | {num(lc['fr4']['total_thickness'])} | {num(lc['pet']['total_thickness'])} |",
            f"| Outer face from centre (mm) | {num(lc['fr4']['outer_face_offset_from_centre'])} | {num(lc['pet']['outer_face_offset_from_centre'])} |",
            f"| Flexural rigidity per mm, bonded / lower bound (N mm) | {num(lc['fr4']['rigidity_per_mm_bonded_nmm'])} | {num(lc['pet']['rigidity_per_mm_bonded_nmm'])} / {num(lc['pet']['rigidity_per_mm_lower_bound_nmm'])} |",
            f"| Buckling under the SH push, fixed-free, lower bound (N) | {num(lc['fr4']['buckling_load_lower_bound_n']['fixed_free_K2'])} | {num(lc['pet']['buckling_load_lower_bound_n']['fixed_free_K2'])} |",
            f"| Cap slot clearance per side (mm) | {num(lc['fr4']['cap_slot_clearance_per_side'])} | {num(lc['pet']['cap_slot_clearance_per_side'])} |",
            "", f"- PET film alone buckles at {num(lc['pet_film_alone_buckling_load_fixed_free_n'])} N; minimum static bend radius {num(lc['min_static_bend_radius_mm'])} mm (JLC 6x rule).",
            f"- LED, connector and harness start move {num(lc['optical']['led_and_connector_shift_toward_centre'])} mm toward the centre; leaf Z {lc['optical']['leaf_z']} unchanged; rear pocket: {lc['rear_pocket']['interaction']}.",
            "", "**Recommendation.** " + lc["recommendation"]]
    out += ["", "## Unresolved inputs", "", "| ID | Item | Decides |", "|---|---|---|"] + [f"| {u['id']} | {u['item']} | {u['decides']} |" for u in L["unresolved"]]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    L = build()
    text = json.dumps(L, indent=2, ensure_ascii=False) + "\n"
    rep = report(L)
    E = envelopes(L)
    env = json.dumps(E, indent=2, ensure_ascii=False) + "\n"
    chk = json.dumps(r4_placement_check(E), indent=2, ensure_ascii=False) + "\n"
    if a.check:
        stale = [str(x.relative_to(REPO)) for x, want in ((LAYOUT, text), (REPORT, rep), (ENVELOPES, env), (R4_CHECK, chk)) if not x.exists() or x.read_text() != want]
        if stale:
            print("STALE: " + ", ".join(stale) + " (run python3 scripts/a7_mechanical_layout.py)")
            return 1
        print("PASS: A7 mechanical layout outputs are current")
        return 0
    LAYOUT.write_text(text)
    REPORT.write_text(rep)
    ENVELOPES.write_text(env)
    R4_CHECK.write_text(chk)
    print("working:", L["decision"]["working_candidate"], L["decision"]["working_verdict"])
    print("open:", L["decision"]["open_candidate"], L["decision"]["open_verdict"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
