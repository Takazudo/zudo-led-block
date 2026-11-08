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
SWITCH_FACTS = A7 / "evidence" / "component-a7-pcm13smtr" / "facts.json"
JACK_FACTS = A7 / "evidence" / "component-a7-pj-324m" / "facts.json"


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


def led_route(xc, x1, cfg, leaf_exit_y, leaf_exit_z, yp_end, target, radius):
    xl = r(xc - 2.35)
    xp = r(x1 + 1.475)
    ro = cfg["led_route"]
    yd, zg, zr = ro["descent_y"], ro["gap_run_z"], ro["return_z"]

    def pts(yf):
        return [[xl, leaf_exit_y, leaf_exit_z], [xl, yd, leaf_exit_z], [xl, yd, zg], [xp, yd + 4.0, zg],
                [xp, yf, zg], [xp, yf, zr], [xp, yp_end, zr]]
    yf = solve(lambda v: fillet_path(pts(v), radius)[1], yp_end + 5.0, 110.0, target)
    P = pts(r(yf))
    segs, length, rmin = fillet_path(P, radius)
    return {"points": P, "radius": radius, "length": r(length), "min_radius": r(rmin), "fold_y": r(yf)}


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
            "end_bend_room": r(xl - (x1 + 5.2))}


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
    ok = [x for x in rows if x["nominal_min"] >= -1e-9 and x["nominal"]["nut_front"] >= pref - 1e-9 and x["lead_long_enough_for_trim"]]
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
    pins = fact(JACK_FACTS, "fact-a7-pj-324m-footprint-positions")

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
        "axial_option": ax_opt, "rear_pocket_depth": pocket, "jack_body_front_z": r(body_front_z),
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
    near, far = P["jack_axis_to_edge_near"]["nominal"], P["jack_axis_to_edge_far"]["nominal"]
    step = j["y_round_down_to"]
    y2 = math.floor((sw_body_y[0] - j["body_to_switch_gap"]["nominal"] - near) / step + 1e-9) * step
    pk_clr = d["axial_option"]["pocket_clearance_around_body"] if pocket > 0 else 0.0
    need = near + far + 2 * pk_clr + 2 * j["label_gap_to_body"]["nominal"] + j["label_cap_height"]["nominal"]
    pitch = max(j["pitch"]["minimum"], math.ceil(need / j["pitch"]["round_up_to"] - 1e-9) * j["pitch"]["round_up_to"])
    y1 = y2 - pitch
    jack_y = [r(y1), r(y2)]
    # +across on the drawing points toward the pin-4/pin-5 (far, 6.1) side; the near side faces +Y.
    pin_y_rel = {k: r(-v["across"]) for k, v in pins.items() if k.startswith("pin_")}
    body_y = [[r(y - far), r(y + near)] for y in jack_y]
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
    }
    lab_off = far + pk_clr + j["label_gap_to_body"]["nominal"] + j["label_cap_height"]["nominal"] / 2
    labels = [{"text": t, "y": r(y - lab_off), "cap_height": j["label_cap_height"]["nominal"]} for t, y in zip(j["labels"], jack_y)]
    sup = d["supports"]
    y_layout = {
        "rail_body_y": g5["rail_body_y"], "controller_pcb_y": [y_top, y_bottom], "jack_y": jack_y, "jack_function": j["functions"],
        "jack_body_y": body_y, "jack_pin_y_offset_from_axis": pin_y_rel, "body_gap": r(body_y[1][0] - body_y[0][1]),
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
        cab = d["cables"]
        lh, ph = c["led_header"], c["power_header"]
        routes = {
            "controller_to_left_leaf_sh4": led_route(w / 2, x_pcb[1], cab, r(l5["y"][0] + l5["header_origins_local_v"][0] + 4.575), r(l5["z"][0] + 4.5),
                                                     r(lh["y"] + 1.675 + 2.0), cab["sh_finished_length"]["nominal"], cab["preferred_bend_radius"]["nominal"]),
            "adapter_to_controller_power": power_route(w / 2, x_pcb[1], w, side, cab, [r(w / 2), g5["adapter"]["power_pinrow_y"], r(g5["adapter"]["front_z"] - 5.2)],
                                                       ph["y"], ph["z_centre"], cab["power_finished_free_span"]["nominal"], cab["preferred_bend_radius"]["nominal"], cab["power_bundle_radius"]["nominal"]),
        }
        routes["controller_to_left_leaf_sh4"]["bundle_radius"] = cab["sh_bundle_radius"]["nominal"]
        routes["adapter_to_controller_power"]["bundle_radius"] = cab["power_bundle_radius"]["nominal"]
        pw = routes["adapter_to_controller_power"]
        pw["within_finished_tolerance"] = abs(pw["length"] - cab["power_finished_free_span"]["nominal"]) <= cab["power_finished_free_span"]["tol"]
        routes["controller_to_left_leaf_sh4"]["status"] = "solved for the nominal finished length"
        checks["power_route_end_bend_room"] = routes["adapter_to_controller_power"]["end_bend_room"]
        checks["power_route_min_radius"] = routes["adapter_to_controller_power"]["min_radius"]
        checks["led_route_min_radius"] = routes["controller_to_left_leaf_sh4"]["min_radius"]
        variants[name] = {
            "routes": routes,
            "panel_width": w, "selection": row, "x_axis": x_axis,
            "jack_axis_height_used": {"value": h_nom, "confidence": "INFERRED", "band": [P["jack_axis_height"]["min"], P["jack_axis_height"]["max"]]},
            "jack_seat_x": seat, "controller_pcb_x": x_pcb, "pcb_thickness": t, "leads": row["leads"],
            "inner_envelope_x": inner, "front_screw_x": {"20.5": r(w / 2), "60.8": screw_x},
            "checks": checks,
        }

    # ---- keep-outs on the controller (handoff to R4) ------------------------------------
    sv = sup["controller_slot_y"]["values"]
    fy = sup["bottom_fork_y"]["values"]
    fork_z0 = r(pcb_z1 - sup["fork_engagement"]["nominal"])
    keepouts = [
        {"id": "spine-slot", "faces": ["+X", "-X"], "y": sv, "z": [pcb_z0, sup["controller_slot_height"]["nominal"]], "reason": "printed spine slot captures the PCB front edge"},
        {"id": "optical-fork", "faces": ["+X", "-X"], "y": fy, "z": [fork_z0, pcb_z1], "reason": "bottom optical cap tongue straddles the rear edge"},
        {"id": "setting-switch", "faces": ["+X"], "y": [sw_body_y[0], y_bottom], "z": switch["body_z"], "reason": "PCM13SMTR body and actuator at the bottom edge"},
        {"id": "switch-access", "faces": ["+X"], "y": [sw_body_y[1], y_bottom], "z": [r(switch["actuator_positions_z"][0] - sw["actuator_width"] / 2 - 0.5), r(switch["actuator_positions_z"][2] + sw["actuator_width"] / 2 + 0.5)], "reason": "actuator travel plus tool clearance; nothing taller than the switch between actuator and board edge"},
    ]
    lh = c["led_header"]
    fold = max(v["routes"]["controller_to_left_leaf_sh4"]["fold_y"] for v in variants.values())
    br = d["cables"]["sh_bundle_radius"]["nominal"]
    keepouts.append({"id": "led-cable-lane", "faces": ["+X"], "y": [r(lh["y"] - 2.575), r(fold + d["cables"]["preferred_bend_radius"]["nominal"] + br)],
                     "z": [r(d["cables"]["led_route"]["return_z"] - br - 0.2), pcb_z1], "reason": "SH4 header and the returning LED harness lie over the component face"})
    for i, y in enumerate(jack_y):
        keepouts.append({"id": f"jack-{j['functions'][i].split()[-1].lower()}", "faces": ["+X"], "y": body_y[i], "z": [pcb_z0, r(body_rear_max)], "reason": "PJ-324M body footprint"})
        keepouts.append({"id": f"jack-{j['functions'][i].split()[-1].lower()}-leads", "faces": ["-X"], "y": [r(y - 5.0), r(y + 5.7)], "z": [pcb_z0, r(max(pin_z.values()) + 1.0)], "reason": "terminal fillets only on the solder face (2HP lead-side margin)"})
    area_total = (y_bottom - y_top) * (pcb_z1 - pcb_z0)
    area_keep = sum((k["y"][1] - k["y"][0]) * (k["z"][1] - k["z"][0]) for k in keepouts if "+X" in k["faces"] and k["id"] != "switch-access")
    controller = {
        "outline_y": [y_top, y_bottom], "outline_z": [pcb_z0, pcb_z1],
        "outline_area_mm2": r(area_total), "component_face_free_area_mm2_approx": r(area_total - area_keep),
        "a5_controller_board_area_mm2": r(ctrl5["width"] * ctrl5["height"]),
        "a5_small_component_body_area_mm2": a5_area,
        "power_header": {**c["power_header"], "pin_row_axis": "Z", "mated_height_x": 5.2, "y_extent": [r(c["power_header"]["y"] - 2.05), r(c["power_header"]["y"] + 1.15)], "z_extent": [r(c["power_header"]["z_centre"] - 2.75), r(c["power_header"]["z_centre"] + 2.75)]},
        "led_header": {**c["led_header"], "pin_row_axis": "Z", "housing_y": [r(c["led_header"]["y"] - 2.575), r(c["led_header"]["y"] + 1.675)], "mated_handle_y_max": r(c["led_header"]["y"] + 1.675 + 2.0), "housing_z": [r(c["led_header"]["z_centre"] - 3.0), r(c["led_header"]["z_centre"] + 3.0)], "height_x": 2.95},
        "keepouts": keepouts,
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
        "inputs": ["engineering/a7/study/parameters.json", "engineering/a7/evidence/component-a7-pcm13smtr/facts.json",
                   "engineering/a7/evidence/component-a7-pj-324m/facts.json", "engineering/a7/mechanical/design-inputs.json",
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
        "z_stack": z_stack, "y_layout": y_layout, "switch": switch, "controller": controller,
        "variants": variants,
        "supports": {
            "front_screw_y": sup["front_screw_y"]["values"], "m2": m2,
            "spine": {"rib_width": sup["spine_rib_width"]["nominal"], "rib_height": sup["spine_rib_height"]["nominal"],
                      "slot_y": sv, "slot_height": sup["controller_slot_height"]["nominal"], "slot_clearance": sup["slot_clearance"]["nominal"],
                      "post_radius": sup["adapter_post_radius"]["nominal"], "post_top_z": g5["adapter"]["front_z"]},
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
        "solder_side_rule": c["solder_side_rule"],
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
    out += ["", "## Unresolved inputs", "", "| ID | Item | Decides |", "|---|---|---|"] + [f"| {u['id']} | {u['item']} | {u['decides']} |" for u in L["unresolved"]]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    L = build()
    text = json.dumps(L, indent=2, ensure_ascii=False) + "\n"
    rep = report(L)
    env = json.dumps(envelopes(L), indent=2, ensure_ascii=False) + "\n"
    if a.check:
        stale = [str(x.relative_to(REPO)) for x, want in ((LAYOUT, text), (REPORT, rep), (ENVELOPES, env)) if not x.exists() or x.read_text() != want]
        if stale:
            print("STALE: " + ", ".join(stale) + " (run python3 scripts/a7_mechanical_layout.py)")
            return 1
        print("PASS: A7 mechanical layout outputs are current")
        return 0
    LAYOUT.write_text(text)
    REPORT.write_text(rep)
    ENVELOPES.write_text(env)
    print("working:", L["decision"]["working_candidate"], L["decision"]["working_verdict"])
    print("open:", L["decision"]["open_candidate"], L["decision"]["open_verdict"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
