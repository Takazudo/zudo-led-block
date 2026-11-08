#!/usr/bin/env python3
"""A7 digital mechanical assembly: perpendicular controller, PJ-324M jacks, side setting switch.

Builds one assembly per width (3HP working candidate and default, 2HP open candidate) from layout.json, which
scripts/a7_mechanical_layout.py derives from the R1 inputs and A5 geometry. Exports an
assembled STEP and GLB, three dimensioned views, and verification.json with pairwise
rigid-collision volumes, cable centreline clearances, envelope checks, the optical-
obstruction check of the A5 leaf emission corridors, and the switch tool-access check.

Optical parts, leaves, the power adapter, its IDC header/socket/ribbon scenario and the
leaf-link harness follow the A5 build (engineering/a5/mechanical/build_mechanical.py); A5
helpers are imported read-only. Provisional digital study: not measured fit approval.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
A5M = REPO / "engineering" / "a5" / "mechanical"
sys.path.insert(0, str(A5M))
from cad_kernel import Part, box, cylinder, ring, hexagon, union, bounds, transformed, tube_from_path  # noqa: E402
sys.path.pop(0)
sys.path.insert(0, str(REPO / "engineering" / "a7" / "front_panel"))
import build_a7_front as FRONT  # noqa: E402
sys.path.pop(0)

import cadquery as cq  # noqa: E402
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import PolyCollection  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


LAYM = _load("a7_mechanical_layout", REPO / "scripts" / "a7_mechanical_layout.py")
L = json.loads((HERE / "layout.json").read_text())
G5 = json.loads((A5M / "geometry.json").read_text())
F5 = json.loads((REPO / "engineering" / "a5" / "front_panel" / "geometry.json").read_text())
E5 = json.loads((REPO / "engineering" / "a5" / "electronics" / "placement_and_connectivity.json").read_text())
P1 = json.loads((REPO / "engineering" / "a7" / "study" / "parameters.json").read_text())["parameters"]
BOARDS = {b["name"]: b for b in E5["boards"]}
COL = {"frame": (.20, .23, .28, 1), "diffuser": (.78, .89, .94, .58), "pcb": (.06, .39, .24, 1), "led": (.97, .83, .28, 1),
       "body": (.17, .18, .2, 1), "connector": (.89, .85, .73, 1), "metal": (.64, .68, .72, 1), "wire": (.72, .24, .13, 1),
       "ribbon": (.74, .40, .68, .8), "acrylic": (.75, .88, .96, .42), "switch": (.15, .35, .75, 1), "pcb_a7": (.10, .45, .30, 1)}
CABLE_KINDS = ("cable_route_scenario", "conditional_cable_scenario")
# Scopes allowed outside the panel width / rail-body envelope only as reported conditions.
CONDITIONAL = ("conditional_harness", "conditional_socket", "conditional_ribbon")
STALE_INPUTS = ("engineering/a7/mechanical/layout.json", "engineering/a7/mechanical/build_a7_mechanical.py", "engineering/a7/front_panel/build_a7_front.py")
CABLE_ENTRY_LIMIT_MM = 4.0  # tube length allowed inside its own mated connector envelope
# Expected rigid contacts and the most overlap each may have (mm3); any other value is a collision.
CONTACT_LIMITS_MM3 = {frozenset(k): v for k, v in {
    ("jack_in_PJ-324M", "jack_in_solder_fillets"): 1.5, ("jack_thru_PJ-324M", "jack_thru_solder_fillets"): 1.5,
    ("nut_in_M6x0.5", "jack_in_PJ-324M"): 0.0, ("nut_thru_M6x0.5", "jack_thru_PJ-324M"): 0.0,
    ("setting_switch_PCM13SMTR", "controller_pcb_A7"): 0.0,
    ("controller_PicoBlade_mated", "controller_pcb_A7"): 0.7,  # three THT tails through the board (no holes cut)
    ("adapter_C5665_keyed_header", "power_adapter_pcb_A5"): 7.0, ("adapter_PicoBlade_mated", "power_adapter_pcb_A5"): 0.7,
    # A5 reference socket / ribbon scenario envelopes, moved unchanged with the adapter; their A5 overlaps stay bounded here
    ("adapter_C5665_keyed_header", "IDC_socket_REFERENCE_overlap6"): 0.3, ("IDC_socket_REFERENCE_overlap6", "IDC_ribbon_R3_side_exit_SCENARIO"): 0.3,
    ("adapter_C5665_keyed_header", "IDC_ribbon_R3_side_exit_SCENARIO"): 0.3,
    ("bottom_cap_fork_A7", "bottom_leaf_cap"): 0.0, ("top_cap_spacer_A7", "top_leaf_adapter_cap"): 0.0, ("top_cap_spacer_A7", "power_adapter_pcb_A5"): 0.0,
}.items()}


def r3(v):
    return round(float(v) + 0.0, 3)


def edges_from(points, radius):
    segs, length, rmin = LAYM.fillet_path(points, radius)
    edges = []
    for s in segs:
        if s[0] == "line":
            edges.append(cq.Edge.makeLine(cq.Vector(*s[1]), cq.Vector(*s[2])))
        else:
            edges.append(cq.Edge.makeThreePointArc(cq.Vector(*s[1]), cq.Vector(*s[2]), cq.Vector(*s[3])))
    return cq.Wire.assembleEdges(edges), length, rmin


def build(name, out, leaf="fr4"):
    V = L["variants"][name]
    w = V["panel_width"]
    xc = w / 2
    xa, seat = V["x_axis"], V["jack_seat_x"]
    x0, x1 = V["controller_pcb_x"]
    t = V["pcb_thickness"]
    Z, Y, C, SW, S = L["z_stack"], L["y_layout"], L["controller"], L["switch"], L["supports"]
    side = P1["side_clearance_required"]["nominal"]
    parts, contacts = [], []

    def add(pname, shape, color, kind="design_geometry", note="", source=None, scope="retained_module", group="module", printed=False, meta=None):
        p = Part(pname, shape, COL.get(color, color), kind, note, source, scope, printed, None, group, meta or {})
        parts.append(p)
        return p

    # ---- front ---------------------------------------------------------------------------
    fg = FRONT.front_geometry(L, F5)
    add("front_pmma_A7", FRONT.panel_shape(fg, name), "acrylic", "manufacturing_artwork",
        "A7 artwork: IN/THRU only, no switch aperture; rear jack pockets per layout.", "../front_panel", "front_panel", "front")

    # ---- jacks, nuts ---------------------------------------------------------------------
    bf = Z["jack_body_front_z"]
    overall = P1["jack_overall_height"]["nominal"]
    depth = P1["jack_body_depth"]["nominal"]
    lead_below = (t + P1["lead_protrusion_trimmed"]["nominal"]) if V["leads"] == "trimmed" else P1["jack_terminal_projection"]["nominal"]
    pin_y = Y["jack_pin_y_offset_from_axis"]
    pins_rel = {k: v for k, v in Z["terminal_z"].items()}
    nut = L["candidates"]["selected_2hp"]  # nut identity is common; dimensions below
    nut_z = Z["nut_z"]
    for fn, y, (by0, by1) in zip(Y["jack_function"], Y["jack_y"], Y["jack_body_y_nominal"]):
        tag = fn.split()[-1].lower()
        body = box(seat, seat + overall, by0, by1, bf, bf + depth)
        barrel = cylinder(3.0, bf - P1["jack_barrel_projection"]["nominal"], bf, xa, y).cut(cylinder(1.8, bf - 4, bf + 0.1, xa, y))
        sh = union(body, barrel)
        for pk, zz in pins_rel.items():
            yy = y + pin_y[pk]
            sh = sh.fuse(box(seat - lead_below, seat, yy - 0.25, yy + 0.25, zz - 0.4, zz + 0.4))
        add(f"jack_{tag}_PJ-324M", sh.clean(), "body", "manufacturer_dimensioned_envelope",
            "Body 6.3 (headline) x 11.5 x 14.2, M6x0.5 barrel 3.5; axis height 3.0 INFERRED; terminal blades 0.5x0.8 ASSUMED section; leads cut to " + V["leads"],
            "src-a7-pj-324m-sofng-drawing", group="controls", meta={"axis_height": "INFERRED"})
        fillet = None
        for pk, zz in pins_rel.items():
            yy = y + pin_y[pk]
            f = cylinder(0.75, 0, 0.6).rotate((0, 0, 0), (0, 1, 0), -90).translate((x0, yy, zz))
            fillet = f if fillet is None else fillet.fuse(f)
        add(f"jack_{tag}_solder_fillets", fillet.clean(), "metal", "assembly_allowance",
            "0.6 mm x R0.75 solder-fillet allowance on the solder face; actual fillet height not sourced (R1 Q6)", group="controls")
        contacts.append((f"jack_{tag}_solder_fillets", f"jack_{tag}_PJ-324M"))
        nd = P1  # noqa: F841
        add(f"nut_{tag}_M6x0.5", ring(4.0, 3.0, nut_z[0], nut_z[1], xa, y), "metal", "standard_hardware_envelope",
            "Same Sky 3.5mm-nut-e reference (OD 8.0 x 1.5); fit on the SOFNG barrel UNVERIFIED (R1 Q4)", group="controls")
        contacts.append((f"nut_{tag}_M6x0.5", f"jack_{tag}_PJ-324M"))

    # ---- controller PCB ------------------------------------------------------------------
    cy0, cy1 = C["outline_y"]
    cz0, cz1 = C["outline_z"]
    pcb = box(x0, x1, cy0, cy1, cz0, cz1)
    for y in Y["jack_y"]:
        for pk, zz in pins_rel.items():
            pcb = pcb.cut(box(x0 - 0.1, x1 + 0.1, y + pin_y[pk] - 0.45, y + pin_y[pk] + 0.45, zz - 0.65, zz + 0.65))
    swz = SW["body_z"]
    swyc = (SW["body_y"][0] + SW["body_y"][1]) / 2
    for zz in ((swz[0] + swz[1]) / 2 - SW["peg_pitch"] / 2, (swz[0] + swz[1]) / 2 + SW["peg_pitch"] / 2):
        pcb = pcb.cut(cylinder(0.45, 0, x1 - x0 + 0.2).rotate((0, 0, 0), (0, 1, 0), 90).translate((x0 - 0.1, swyc, zz)))
    add("controller_pcb_A7", pcb, "pcb_a7", "design_geometry",
        f"{t} mm FR-4, Y{cy0}-{cy1} x Z{cz0}-{cz1}; unrouted outline for R4; THT slots 0.9 x 1.3 ASSUMED (R1 Q3)", group="controller")
    # solder-face low-profile zone (R4 0603 resistors): an envelope so the rigid checks cover it
    zc = C["solder_face_low_profile_zone"]
    zone = box(x0 - zc["max_height"], x0, cy0, cy1, cz0, cz1)
    for k in C["keepouts"]:
        if "-X" in k["faces"]:
            zone = zone.cut(box(x0 - zc["max_height"] - 0.1, x0 + 0.1, k["y"][0], k["y"][1], k["z"][0] - 0.1 if k["z"][0] <= cz0 else k["z"][0], k["z"][1] + 0.1 if k["z"][1] >= cz1 else k["z"][1]))
    add("solder_face_low_profile_zone", zone.clean(), "metal", "assembly_allowance",
        f"R4 solder-face zone, parts <= {zc['max_height']} mm outside every -X keep-out (envelope, not parts)", group="controller")
    # setting switch
    sw = box(x1, x1 + SW["height_above_pcb"], SW["body_y"][0], SW["body_y"][1], swz[0], swz[1])
    za = SW["actuator_positions_z"][1]
    act = box(x1 + 0.1, x1 + SW["height_above_pcb"] - 0.1, SW["actuator_y"][0], SW["actuator_y"][1], za - SW["actuator_width_z"] / 2, za + SW["actuator_width_z"] / 2)
    for zz in ((swz[0] + swz[1]) / 2 - SW["peg_pitch"] / 2, (swz[0] + swz[1]) / 2 + SW["peg_pitch"] / 2):
        sw = sw.fuse(cylinder(0.4, 0, 0.5).rotate((0, 0, 0), (0, 1, 0), -90).translate((x1, swyc, zz)))
    add("setting_switch_PCM13SMTR", union(sw, act), "switch", "manufacturer_dimensioned_envelope",
        "C&K PCM13SMTR body 9.7 x 2.6 x 1.4, actuator 1.3 wide projecting 1.5 to the board edge, centre (PGM) position shown", "src-a7-pcm13smtr-ck-datasheet", group="controller")
    contacts.append(("setting_switch_PCM13SMTR", "controller_pcb_A7"))
    # controller connectors (A5-sourced envelopes, rotated onto the Y-Z board)
    ph, lh = C["power_header"], C["led_header"]
    pico = box(x1, x1 + 5.2, ph["y_extent"][0], ph["y_extent"][1], ph["z_extent"][0], ph["z_extent"][1])
    tail = (t + P1["lead_protrusion_trimmed"]["nominal"]) if V["leads"] == "trimmed" else 2.3
    for k in (-1, 0, 1):
        pico = pico.fuse(cylinder(0.2, 0, tail).rotate((0, 0, 0), (0, 1, 0), -90).translate((x1, ph["y"], ph["z_centre"] + 1.25 * k)))
    add("controller_PicoBlade_mated", pico.clean(), "connector", "manufacturer_dimensioned_envelope",
        "Molex 530470310 mated 5.2 (A5 reference) on the component face; tails 2.3 nominal, cut to the jack trim rule in 2HP; wires leave along +X", "Molex_530470310", group="controller")
    contacts.append(("controller_PicoBlade_mated", "controller_pcb_A7"))
    sh4 = union(box(x1, x1 + 2.95, lh["housing_y"][0], lh["housing_y"][1], lh["housing_z"][0], lh["housing_z"][1]),
                box(x1 + 0.15, x1 + 2.95, lh["housing_y"][1], lh["mated_handle_y_max"], lh["housing_z"][0] - 0.5, lh["housing_z"][1] + 0.5))
    add("controller_SH4_mated", sh4, "connector", "manufacturer_dimensioned_envelope",
        "JST SM04B-SRSS-TB side entry, opening +Y, mated handle envelope as A5", "JST_SH", group="controller")

    # ---- spine (printed) -----------------------------------------------------------------
    sp = S["spine"]
    m2 = S["m2"]
    sx = V["front_screw_x"]
    post = cylinder(sp["post_radius"], 0, sp["post_top_z"], xc, 20.5).intersect(box(side, w - side, 18, 23, -0.1, sp["post_top_z"] + 0.1))
    rib = box(xc - sp["rib_width"] / 2, xc + sp["rib_width"] / 2, 18, sp["slot_y"][0] - 3.0 + 0.5, 0, sp["rib_height"])
    block = box(side, w - side, sp["slot_y"][0] - 3.0, sp["slot_y"][1], 0, sp["slot_height"])
    block = block.cut(box(x0 - sp["slot_clearance"], x1 + sp["slot_clearance"], cy0 - 0.1, sp["slot_y"][1] + 0.1, -0.1, sp["slot_height"] + 0.1))
    spine = union(post, rib, block)
    y61 = S["front_screw_y"][1]
    spine = spine.cut(cylinder(m2["clearance_hole"] / 2, -0.1, sp["post_top_z"] + 0.2, xc, 20.5))
    spine = spine.cut(cylinder(m2["clearance_hole"] / 2, -0.1, sp["slot_height"] + 0.1, sx[str(y61)], y61))
    for (xx, yy, z0_) in ((xc, 20.5, 3.0), (xc, 20.5, sp["post_nut_z"][0]), (sx[str(y61)], y61, sp["rib_height"])):
        spine = spine.cut(hexagon(m2["nut_af"] + 0.25, z0_, z0_ + 1.8, xx, yy))
        spine = spine.cut(box(xx, w + 0.1, yy - (m2["nut_af"] + 0.25) / 2, yy + (m2["nut_af"] + 0.25) / 2, z0_, z0_ + 1.8))
    add("spine_PETG", spine.clean(), "frame", "printable_design",
        "Front-referenced PETG spine: adapter/top-cap post at Y20.5, rib, controller slot block Y" + f"{sp['slot_y'][0]}-{sp['slot_y'][1]}; M2 side-loaded nuts",
        printed=True, group="carrier")

    # M2 hardware
    for y in S["front_screw_y"]:
        xx = sx[str(y)]
        add(f"M2_front_washer_{y}", ring(m2["washer_od"] / 2, 1.1, -2.0 - m2["washer_t"], -2.0, xx, y), "metal", "standard_hardware_envelope", group="hardware")
        shank_end = 5.7 if y == 20.5 else sp["rib_height"] + 1.8 + 0.4
        add(f"M2_front_screw_{y}", union(cylinder(1.0, -2.3, shank_end, xx, y), cylinder(m2["head_d"] / 2, -2.3 - m2["head_h"], -2.3, xx, y)),
            "metal", "standard_hardware_envelope", "Nominal M2 pan head reserve; supplier not selected", group="hardware")
        nz = 3.0 if y == 20.5 else sp["rib_height"]
        add(f"M2_nut_{y}", hexagon(m2["nut_af"], nz, nz + m2["nut_t"], xx, y, 2.0), "metal", "standard_hardware_envelope", group="hardware")
    tcs = S["top_cap_screw"]
    add("top_cap_screw_A7", union(cylinder(1.0, tcs["tip_z"], tcs["head_seat_z"], xc, 20.5), cylinder(1.9, tcs["head_seat_z"], 29.1, xc, 20.5)), "metal", "standard_hardware_envelope",
        f"{tcs['designation']} top-cap screw (A5 M2x16 lengthened by the adapter move)", group="hardware")
    add("M2_post_nut_top", hexagon(4.0, sp["post_nut_z"][0], sp["post_nut_z"][1], xc, 20.5, 2.0), "metal", "standard_hardware_envelope", group="hardware")

    # ---- A5 power adapter (retained) ------------------------------------------------------
    ad = G5["adapter"]  # A5 geometry; the whole adapter group is then moved by the A7 z_shift
    adz = S["adapter"]["z_shift"]
    n_before = len(parts)
    apcb = box(xc - 4.4, xc + 4.4, ad["y"][0], ad["y"][1], ad["front_z"], ad["front_z"] + ad["thickness"]).cut(cylinder(1.1, ad["front_z"] - 0.1, ad["front_z"] + 2, xc, 20.5))
    add("power_adapter_pcb_A5", apcb, "pcb", "native_pcb_envelope", "A5 power adapter retained (8.8 x 30 x 1.6)", group="power_adapter")
    idc = box(xc - 4.55, xc + 4.55, 23, 43.8, 8.5, 17.4).cut(box(xc - 3.65, xc + 3.65, 24.4, 42.4, 8.4, 15.8))
    for xx in (xc - 1.27, xc + 1.27):
        for yy in (28.32, 30.86, 33.4, 35.94, 38.48):
            idc = idc.fuse(box(xx - .32, xx + .32, yy - .32, yy + .32, 11, 20))
    add("adapter_C5665_keyed_header", idc.clean(), "body", "manufacturer_dimensioned_envelope", "A5 C5665 max envelope; tails <=1.0 behind adapter", "C5665_header", group="power_adapter")
    contacts.append(("adapter_C5665_keyed_header", "power_adapter_pcb_A5"))
    sock = box(xc - 3.5, xc + 3.5, 33.4 - 8.69, 33.4 + 8.69, 7.6, 14.5).cut(box(xc - 1.7, xc + 1.7, 27.5, 39.3, 10.8, 14.6))
    add("IDC_socket_REFERENCE_overlap6", sock, "connector", "conditional_reference_envelope", "Wurth 61201023021 reference only (A5)", scope="conditional_socket", group="power_adapter")
    contacts.append(("adapter_C5665_keyed_header", "IDC_socket_REFERENCE_overlap6"))
    apico = box(xc - 2.75, xc + 2.75, 46.7 - 2.05, 46.7 + 1.15, ad["front_z"] - 5.2, ad["front_z"])
    for px in (xc - 1.25, xc, xc + 1.25):
        apico = apico.fuse(cylinder(.20, ad["front_z"], ad["front_z"] + 2.3, px, 46.7))
    add("adapter_PicoBlade_mated", apico.clean(), "connector", "manufacturer_dimensioned_envelope", "A5 adapter J2", "Molex_530470310", group="power_adapter")
    contacts.append(("adapter_PicoBlade_mated", "power_adapter_pcb_A5"))
    Rr, tt, start, zz = 3.0, .8, xc + 3.5, 10.5
    pts = []
    for k in range(33):
        a = (math.pi / 2) * k / 32
        pts.append((start + (Rr + tt / 2) * math.sin(a), zz + (Rr + tt / 2) * (1 - math.cos(a))))
    pts += [(start + Rr + tt / 2, 29.8), (start + Rr - tt / 2, 29.8)]
    for k in range(32, -1, -1):
        a = (math.pi / 2) * k / 32
        pts.append((start + (Rr - tt / 2) * math.sin(a), zz + (Rr - tt / 2) * (1 - math.cos(a))))
    ribbon = transformed(cq.Workplane("XY").polyline(pts).close().extrude(12.7).val(), (0, 39.75, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0))
    add("IDC_ribbon_R3_side_exit_SCENARIO", ribbon, "ribbon", "conditional_cable_scenario", "A5 R3 side-exit scenario carried over; not qualified", scope="conditional_ribbon", group="cables")
    contacts.append(("IDC_socket_REFERENCE_overlap6", "IDC_ribbon_R3_side_exit_SCENARIO"))
    contacts.append(("adapter_C5665_keyed_header", "IDC_ribbon_R3_side_exit_SCENARIO"))
    for p_ in parts[n_before:]:
        p_.shape = p_.shape.translate(cq.Vector(0, 0, adz))
        p_.note += f"; moved {adz} mm in Z with the adapter (A7)"

    # ---- A5 leaves, leaf parts, leaf connectors (retained) ---------------------------------
    LC = L["leaf_comparison"]
    half = LC[leaf]["outer_face_offset_from_centre"]

    def notched(t):
        sheet = box(0, 9, 0, 82.5, -t, 0)
        for u0, v0, u1, v1 in BOARDS["led_leaf"]["front_edge_notches_mm"]:
            sheet = sheet.cut(box(u0 - .1, u1, v0, v1, -t - .1, .1))
        return sheet

    poses = {"left": ((xc - half, 22.5, 19.4), (0, 0, 1), (0, 1, 0), (-1, 0, 0)), "right": ((xc + half, 105, 19.4), (0, 0, 1), (0, -1, 0), (1, 0, 0))}
    if leaf == "fr4":
        for s_, pose in poses.items():
            add(f"{s_}_leaf_pcb_A5", transformed(notched(.6), *pose), "pcb", "native_pcb_envelope", "A5 FR-4 leaf (default; reference/fallback)", group=f"{s_}_leaf")
        bond = box(xc - .05, xc + .05, 22.5, 105, 19.4, 28.4)
        for ny in (46.7, 80.8):
            bond = bond.cut(box(xc - .1, xc + .1, ny - 1, ny + 1, 19.3, 20.4))
        add("leaf_bond_line_reserve", bond, "frame", "assembly_allowance", "A5 0.1 mm bond-line reserve", group="leaves")
    else:
        pe = LC["inputs"]["pet"]
        tf, ta, tc = pe["film"]["finished_thickness"]["nominal"], pe["adhesive"]["thickness"]["nominal"], pe["carrier"]["thickness"]["nominal"]
        for s_, pose in poses.items():
            add(f"{s_}_leaf_film_PET", transformed(notched(tf), *pose), "pcb", "design_geometry", "clear PET FPC leaf film, 1 layer 0.14 mm (JLC); comparison variant", group=f"{s_}_leaf")
            add(f"{s_}_leaf_OCA", transformed(notched(ta).translate((0, 0, -tf)), *pose), "frame", "assembly_allowance", "optically clear adhesive film (thickness INFERRED)", group="leaves")
        carrier = box(xc - tc / 2, xc + tc / 2, 22.5, 105, 19.4, 28.4)
        for ny in (46.7, 80.8):
            carrier = carrier.cut(box(xc - tc / 2 - .01, xc + tc / 2 + .01, ny - 1, ny + 1, 19.3, 20.4))
        add("leaf_carrier_PC", carrier, "frame", "design_geometry", "clear PC carrier between the two films (thickness and modulus INFERRED)", group="leaves")
    jst_local = union(box(-3, 3, -1.675, 2.575, 0, 2.95), box(-3.5, 3.5, 2.575, 4.575, .15, 2.95))
    jst = {"left": [], "right": []}
    for s_, pose in poses.items():
        for ref, vv in (("J1", 16.5), ("J2", 66.0)):
            mated = not (s_ == "right" and ref == "J2")
            loc = jst_local if mated else box(-3, 3, -1.675, 2.575, 0, 2.95)
            shp = transformed(loc.translate((4.5, vv, 0)), *pose)
            add(f"{s_}_{ref}_SH4_{'mated' if mated else 'unmated'}", shp, "connector", "manufacturer_dimensioned_envelope", "A5 leaf connector", "JST_SH", group=f"{s_}_leaf")
            jst[s_].append(shp)
    small = []
    for c in BOARDS["led_leaf"]["components"]:
        if not c.get("fitted") or c["type"] in ("SH4",):
            continue
        sx_, sy_ = c["body_size_mm"]
        h = c["height_max_mm"]
        cx, cy = c.get("body_center_mm", [0, 0])
        a = math.radians(-c["angle"])
        px = c["at"][0] + cx * math.cos(a) - cy * math.sin(a)
        py = c["at"][1] + cx * math.sin(a) + cy * math.cos(a)
        shp = box(-sx_ / 2, sx_ / 2, -sy_ / 2, sy_ / 2, 0, h).rotate((0, 0, 0), (0, 0, 1), -c["angle"]).translate((px, py, 0))
        for s_, pose in poses.items():
            small.append(add(f"{s_}_{c['ref']}", transformed(shp, *pose), "led" if c["type"] == "LED" else "body",
                             "native_component_max_envelope", "A5 leaf part max envelope", c.get("c_code"), group=f"{s_}_leaf"))

    # ---- optical supports (A5 topology, 0.3 mm side inset) -----------------------------------
    o5 = G5["optical"]
    top = union(box(side, w - side, 18, 23.7, 19, 29.8), box(side, w - side, 23.7, 26, 25.4, 29.8))
    top = top.cut(box(xc - .8, xc + .8, 22.3, 26.1, 18.8, 28.6)).cut(cylinder(1.1, 18.9, 29.9, xc, 20.5)).cut(cylinder(2.1, 27.8, 29.9, xc, 20.5))
    bottom = box(side, w - side, 103.8, 107, 18, 29.8).cut(box(xc - .8, xc + .8, 103.7, 105.2, 19.2, 28.6))
    supports = {"top_leaf_adapter_cap": top, "bottom_leaf_cap": bottom}
    for nm, shp in list(supports.items()):
        for a_, b_ in ((side, 1.7), (w - 1.7, w - side)):
            shp = shp.cut(box(a_, b_, 21.8, 107.2, 16.8, 28.2))
        for a_, b_ in ((side, xc - .9), (xc + .9, w - side)):
            shp = shp.cut(box(a_, b_, 21.8, 107.2, 25.4, 27))
        for yy in (23.5, 105.5):
            for xx in (xc - 2.4, xc + 2.4):
                shp = shp.cut(cylinder(.9, 24, 30, xx, yy)).cut(hexagon(3.4, 28.2, 30, xx, yy, rotation=30)).cut(cylinder(1.72, 24.2, 25.6, xx, yy))
        for p_ in small:
            pb = p_.shape.BoundingBox()
            pocket = box(pb.xmin - .2, pb.xmax + .2, pb.ymin - .2, pb.ymax + .2, pb.zmin - .2, pb.zmax + .2)
            if shp.intersect(pocket).Volume() > 1e-5:
                shp = shp.cut(pocket)
        supports[nm] = shp.clean()
    # A7: bottom-cap fork on the controller rear edge (locates the optical stack, no jack load)
    fk = S["bottom_fork"]
    clr = sp["slot_clearance"]
    fz0, fz1 = fk["z"][0], o5["skin_z"][0] - 0.2
    fork = union(box(x0 - clr - fk["wall"], x0 - clr, fk["y"][0], fk["y"][1], fz0, fz1),
                 box(x1 + clr, x1 + clr + fk["wall"], fk["y"][0], fk["y"][1], fz0, 18.2),
                 box(x0 - clr - fk["wall"], x1 + clr + fk["wall"], fk["y"][0], fk["y"][1], cz1 + clr, fz1))
    spz = S["adapter"]["cap_spacer_z"]
    spacer = cylinder(S["adapter"]["cap_spacer_radius"], spz[0], spz[1], xc, 20.5).cut(cylinder(1.1, spz[0] - 0.1, spz[1] + 0.2, xc, 20.5))
    add("top_cap_spacer_A7", spacer.clean(), "frame", "printable_design", "A7 boss on the top cap filling the gap left by moving the adapter forward (printed with the cap)", printed=True, group="carrier")
    contacts.append(("top_cap_spacer_A7", "top_leaf_adapter_cap"))
    contacts.append(("top_cap_spacer_A7", "power_adapter_pcb_A5"))
    for nm, shp in supports.items():
        add(nm, shp.cut(fork).clean() if nm.startswith("bottom") else shp, "frame", "printable_design", "PETG optical support (A5 topology)", printed=True, group="carrier")
    add("bottom_cap_fork_A7", fork.clean(), "frame", "printable_design", "A7 fork on the bottom cap; straddles the controller rear edge (printed as one part with the cap)", printed=True, group="carrier")
    contacts.append(("bottom_cap_fork_A7", "bottom_leaf_cap"))
    for s_ in ("left", "right"):
        if s_ == "left":
            a_, b_, f0, f1 = .3, 1.5, .3, xc - .9
        else:
            a_, b_, f0, f1 = w - 1.5, w - .3, xc + .9, w - .3
        skin = union(box(a_, b_, 22, 107, 17.4, 28), box(f0, f1, 22, 107, 25.6, 26.8))
        skin = skin.cut(box(a_ - .1, b_ + .1, 21.8, 48.4, 17.3, 19.2)).cut(box(a_ - .1, b_ + .1, 46.8, 49.4, 17.3, 20.6))
        for shp in jst[s_]:
            sb = shp.BoundingBox()
            if s_ == "left":
                pocket = box(.9 if name == "2hp" else sb.xmin - .2, xc, sb.ymin - .2, sb.ymax + .2, sb.zmin - .2, sb.zmax + .2)
            else:
                pocket = box(xc, w - .9 if name == "2hp" else sb.xmax + .2, sb.ymin - .2, sb.ymax + .2, sb.zmin - .2, sb.zmax + .2)
            skin = skin.cut(pocket)
        if s_ == "right" and name == "3hp":
            skin = skin.cut(box(xc + 5.85, w + .1, 26.7, 40.1, 16.9, 28.6))
        for yy in (23.5, 105.5):
            xx = xc + (-2.4 if s_ == "left" else 2.4)
            skin = skin.cut(cylinder(.9, 25.5, 26.9, xx, yy)).cut(cylinder(1.6, 24.2, 25.6, xx, yy))
        add(f"{s_}_diffuser", skin.clean(), "diffuser", "printable_design", "PETG L-section diffuser (A5)", printed=True, group="optics")
    for sg in (-1, 1):
        xx = xc + sg * 2.4
        for yy in (23.5, 105.5):
            add(f"M1_6x4_{sg}_{yy}", union(cylinder(.8, 25.6, 29.6, xx, yy), cylinder(1.5, 24.3, 25.6, xx, yy)), "metal", "standard_hardware_envelope", group="hardware")
            add(f"M1_6_nut_{sg}_{yy}", hexagon(3.2, 28.2, 29.5, xx, yy, 1.6, 30), "metal", "standard_hardware_envelope", group="hardware")

    # ---- cables -----------------------------------------------------------------------------
    cable_rows = []

    def cable(cname, path, radius, endparts, meta, scope="conditional_harness"):
        shp, stats = tube_from_path(path, radius)
        stats = {k: v for k, v in stats.items() if k != "control_points"}
        stats.update(meta, name=cname, tube_radius_mm=radius)
        p_ = add(cname, shp, "wire", "cable_route_scenario", "Route scenario; bend radius, insulation, slack storage and label are not qualified (#8)", scope=scope, group="cables", meta=stats)
        p_.cable_path = path
        p_.cable_radius = radius
        for o in endparts:
            contacts.append((cname, o))
        cable_rows.append(stats)
    for key, ends in (("controller_to_left_leaf_sh4", ("left_J1_SH4_mated", "controller_SH4_mated")),
                      ("adapter_to_controller_power", ("adapter_PicoBlade_mated", "controller_PicoBlade_mated"))):
        rt = V["routes"][key]
        path, length, rmin = edges_from(rt["points"], rt["radius"])
        cable(key, path, rt["bundle_radius"], ends, {"layout_length_mm": rt["length"], "fillet_min_radius_mm": r3(rmin), "bundle_model": True})
    # A5 leaf-to-leaf link, carried over unchanged (four separate wires)
    def lin(a, b):
        return cq.Edge.makeLine(cq.Vector(*a), cq.Vector(*b))

    def arc(a, b, c):
        return cq.Edge.makeThreePointArc(cq.Vector(*a), cq.Vector(*b), cq.Vector(*c))
    for i in range(4):
        xl_, xr_ = xc - 2.2, xc + 2.2
        zl = zr = 22.4 + i
        ra = 1.75 + i
        ybend = 93.075 + ra
        zturn = 20.65
        zb = 17.9 if i < 2 else 18.8
        xb = xc + (1.5 if i % 2 == 0 else 2.5)
        rb = 1.5
        rc = (zr - zb) / 2
        constant = math.pi * ra / 2 + (zturn - zb - rb) + math.pi * rb + (xb - xl_ - 2 * rb) + (ybend - rb) + math.pi * rc + 83.925
        yu = (constant - 50) / 2
        a = (xl_, 93.075, zl); b = (xl_, ybend, zturn); c = (xl_, ybend, zb + rb)
        d = (xl_ + rb, ybend, zb); e = (xb - rb, ybend, zb); f = (xb, ybend - rb, zb); h = (xb, yu, zb); j = (xr_, yu, zr); k = (xr_, 83.925, zr)
        q = math.sqrt(.5)
        edges = [arc(a, (xl_, 93.075 + ra * q, zturn + ra * q), b), lin(b, c), arc(c, (xl_ + rb - rb * q, ybend, zb + rb - rb * q), d), lin(d, e),
                 arc(e, (xb - rb + rb * q, ybend - rb + rb * q, zb), f), lin(f, h)]
        pts_ = []
        for n in range(25):
            tt_ = n / 24
            aa = math.pi * tt_
            pts_.append(cq.Vector(xb + (xr_ - xb) * (3 * tt_ * tt_ - 2 * tt_ ** 3), yu - rc * math.sin(aa), zb + rc * (1 - math.cos(aa))))
        edges += [cq.Edge.makeSpline(pts_, tangents=(cq.Vector(0, -1, 0), cq.Vector(0, 1, 0))), lin(j, k)]
        cable(f"leaf_link_pin_{i + 1}_A5", cq.Wire.assembleEdges(edges), 0.4, ("left_J2_SH4_mated", "right_J1_SH4_mated"), {"carried_over_from": "A5"})

    # ---- checks -----------------------------------------------------------------------------
    return parts, contacts, cable_rows


def validate(parts, contacts, name):
    V = L["variants"][name]
    w = V["panel_width"]
    expected = {frozenset(c) for c in contacts}
    rows, collisions, permitted, cable_findings, env = [], [], [], [], []
    side = P1["side_clearance_required"]["nominal"]
    for p in parts:
        bb = bounds(p.shape)
        rows.append({"part": p.name, "valid": p.shape.isValid(), "solids": len(p.shape.Solids()), "volume_mm3": r3(p.shape.Volume()),
                     "bbox_min": [r3(v) for v in bb["min"]], "bbox_max": [r3(v) for v in bb["max"]], "scope": p.scope, "kind": p.kind})
        probs = []
        if bb["min"][0] < -1e-4 or bb["max"][0] > w + 1e-4:
            probs.append("panel_width")
        elif p.scope != "front_panel" and bb["max"][2] > 0 and (bb["min"][0] < side - 1e-4 or bb["max"][0] > w - side + 1e-4):
            probs.append("side_clearance_0.3")
        if bb["max"][2] > L["z_stack"]["installed_depth_target"] + 1e-4:
            probs.append("rear_depth_30")
        if p.scope != "front_panel" and bb["max"][2] > 0 and p.group != "hardware" and (bb["min"][1] < 17.1 - 1e-4 or bb["max"][1] > 111.4 + 1e-4):
            probs.append("rail_body_y")
        if probs:
            env.append({"part": p.name, "scope": p.scope, "checks": probs, "x": [r3(bb["min"][0]), r3(bb["max"][0])], "z_max": r3(bb["max"][2])})
    bbs = {p.name: p.shape.BoundingBox() for p in parts}
    for i, a in enumerate(parts):
        ba = bbs[a.name]
        for b in parts[i + 1:]:
            bb = bbs[b.name]
            g = 0.5 if (hasattr(a, "cable_path") or hasattr(b, "cable_path")) else 0.0
            if any(v <= 1e-5 - g for v in (min(ba.xmax, bb.xmax) - max(ba.xmin, bb.xmin), min(ba.ymax, bb.ymax) - max(ba.ymin, bb.ymin), min(ba.zmax, bb.zmax) - max(ba.zmin, bb.zmin))):
                continue
            pair = frozenset((a.name, b.name))
            carried = origin(a) == "a5" and origin(b) == "a5"
            if pair in expected and (hasattr(a, "cable_path") or hasattr(b, "cable_path")):
                # a cable may enter its own end connector, but only by a short plug-length of tube
                tube = a if hasattr(a, "cable_path") else b
                other = b if tube is a else a
                vol = tube.shape.intersect(other.shape).Volume()
                lim = math.pi * tube.cable_radius ** 2 * CABLE_ENTRY_LIMIT_MM
                row = {"a": a.name, "b": b.name, "volume_mm3": r3(vol), "limit_mm3": r3(lim)}
                (permitted if vol <= lim else collisions).append(row)
                continue
            if hasattr(a, "cable_path") or hasattr(b, "cable_path"):
                ca = getattr(a, "cable_path", a.shape)
                cb = getattr(b, "cable_path", b.shape)
                need = getattr(a, "cable_radius", 0) + getattr(b, "cable_radius", 0)
                dist = ca.distance(cb)
                if dist < need + 0.1:
                    row = {"a": a.name, "b": b.name, "centreline_distance_mm": r3(dist), "required_mm": r3(need), "clearance_mm": r3(dist - need)}
                    if pair in expected:
                        permitted.append(row)
                    elif (a.name.startswith("leaf_link") or b.name.startswith("leaf_link")) and carried:
                        cable_findings.append(dict(row, note="A5 leaf-link wires: carried-over scenario"))
                    else:
                        cable_findings.append(row)
                continue
            vol = a.shape.intersect(b.shape).Volume()
            if vol > 1e-4:
                row = {"a": a.name, "b": b.name, "volume_mm3": r3(vol)}
                lim = CONTACT_LIMITS_MM3.get(pair)
                if pair in expected and lim is None and carried:
                    cable_findings.append(dict(row, note="conditional A5 reference envelopes overlap by construction; carried over"))
                elif pair in expected and lim is not None and vol <= lim:
                    permitted.append(dict(row, limit_mm3=lim))
                elif pair in expected:
                    collisions.append(dict(row, limit_mm3=lim, note="expected contact exceeds its stated limit"))
                elif (a.scope in CONDITIONAL or b.scope in CONDITIONAL) and carried:
                    cable_findings.append(dict(row, note="conditional A5 scenario part (reference socket / ribbon); carried over"))
                else:
                    collisions.append(row)
    return rows, collisions, permitted, cable_findings, env


A5_GROUPS = ("left_leaf", "right_leaf", "leaves", "optics")  # the power adapter group and its post nut / screw moved in A7
A5_NAMES = ("top_leaf_adapter_cap", "bottom_leaf_cap")


def origin(p):
    """'a5' for parts carried over from the A5 build, 'a7' for parts this model adds or moves."""
    if p.group in A5_GROUPS or p.name in A5_NAMES or p.name.startswith(("leaf_link", "M1_6")):
        return "a5"
    return "a7"


def optical(parts, name):
    """A5 leaf emission corridors: between each leaf's emitting face and its diffuser skin."""
    V = L["variants"][name]
    xc = V["panel_width"] / 2
    leaf_y, leaf_z = G5["leaf"]["y"], G5["leaf"]["z"]
    corridors = {"left": box(1.5, xc - 1.25, leaf_y[0], leaf_y[1], leaf_z[0], leaf_z[1]),
                 "right": box(xc + 1.25, V["panel_width"] - 1.5, leaf_y[0], leaf_y[1], leaf_z[0], leaf_z[1])}
    area = (leaf_y[1] - leaf_y[0]) * (leaf_z[1] - leaf_z[0])
    emitters = {s_: [p for p in parts if p.name.startswith(s_ + "_D")] for s_ in corridors}
    out = {}
    for s_, cor in corridors.items():
        rows = []
        for p in parts:
            if p.group == "optics" or p.name.endswith(("_leaf_pcb_A5", "_leaf_film_PET", "_leaf_OCA")) or p.name in ("leaf_bond_line_reserve", "leaf_carrier_PC"):
                continue
            if p.name.startswith(s_ + "_D"):
                continue  # the emitters themselves
            v = p.shape.intersect(cor)
            if v.Volume() > 1e-4:
                b = v.BoundingBox()
                if origin(p) == "a5":
                    org = ("a5_leaf_mounted" if p.group.endswith("_leaf") else "a5_power_adapter" if p.group == "power_adapter" else
                           "a5_leaf_link_harness" if p.name.startswith("leaf_link") else "a5_hardware" if p.group == "hardware" else "a5_optical_support")
                else:
                    org = "a7_harness" if p.group == "cables" else "a7_controller_or_support"
                row = {"part": p.name, "origin": org, "volume_mm3": r3(v.Volume()), "projected_yz_bbox_mm2": r3(b.ylen * b.zlen),
                       "y": [r3(b.ymin), r3(b.ymax)], "z": [r3(b.zmin), r3(b.zmax)]}
                if org.startswith("a7"):
                    row["min_distance_to_emitter_mm"] = r3(min(p.shape.distance(e.shape) for e in emitters[s_]))
                rows.append(row)
        a7 = [x for x in rows if x["origin"] == "a7_controller_or_support"]
        out[s_] = {"corridor_x": [r3(cor.BoundingBox().xmin), r3(cor.BoundingBox().xmax)], "corridor_area_yz_mm2": r3(area), "obstructions": rows,
                   "a7_controller_or_support_obstructions": len(a7),
                   "a7_harness_obstructions": [x for x in rows if x["origin"] == "a7_harness"],
                   "projected_bbox_upper_bound_fraction": r3(sum(x["projected_yz_bbox_mm2"] for x in rows) / area)}
    return out


def _ray_sphere(o, d, c, rad):
    oc = [o[i] - c[i] for i in range(3)]
    bq = sum(oc[i] * d[i] for i in range(3))
    cq_ = sum(v * v for v in oc) - rad * rad
    disc = bq * bq - cq_
    if disc < 0:
        return None
    t = -bq - math.sqrt(disc)
    return t if t > 0 else None


def optical_estimate(parts, name, opt, n=4000, seed=7):
    """First-order shading estimate: cosine-weighted rays from each leaf LED's emitting face to the diffuser plane.

    A7 harnesses are sampled as spheres along their whole centreline (exact bundle radius). A5 carry-over
    items are not counted here (see optical_obstruction). Not a light simulation (no reflection, no diffuser
    scattering, no LED angular data)."""
    import random
    rng = random.Random(seed)
    out = {}
    by_name = {p.name: p for p in parts}
    for s_ in ("left", "right"):
        cx = opt[s_]["corridor_x"]
        sgn = -1 if s_ == "left" else 1
        plane = cx[0] if s_ == "left" else cx[1]
        harness = []
        for row in opt[s_]["obstructions"]:
            p = by_name[row["part"]]
            if row["origin"] == "a7_harness":
                w_ = p.cable_path
                L_ = w_.Length()
                k = max(8, int(L_ / (p.cable_radius * 0.5)))
                harness += [((lambda v: (v.x, v.y, v.z))(w_.positionAt(i / k)), p.cable_radius) for i in range(k + 1)]
        rows = []
        for e in sorted((p for p in parts if p.name.startswith(s_ + "_D")), key=lambda p: p.shape.BoundingBox().ymin):
            bb = e.shape.BoundingBox()
            fx = bb.xmin if s_ == "left" else bb.xmax
            hit_h = 0
            for _ in range(n):
                o = (fx, bb.ymin + rng.random() * bb.ylen, bb.zmin + rng.random() * bb.zlen)
                u, v = rng.random(), rng.random()
                rr, ph = math.sqrt(u), 2 * math.pi * v
                d = (sgn * math.sqrt(1 - u), rr * math.cos(ph), rr * math.sin(ph))
                tp = (plane - o[0]) / d[0]
                hit_h += any((t := _ray_sphere(o, d, c, rad)) is not None and t < tp for c, rad in harness)
            rows.append({"led": e.name, "y": [r3(bb.ymin), r3(bb.ymax)], "blocked_by_a7_harness": r3(hit_h / n)})
        out[s_] = rows
    return {"method": "cosine-weighted rays from each LED face to the diffuser inner plane; " + str(n) + " rays per LED, fixed seed; fraction of rays meeting an A7 harness; not a light simulation",
            "per_side": out}


def tool_access(parts, name):
    V = L["variants"][name]
    SW = L["switch"]
    x1 = V["controller_pcb_x"][1]
    z = SW["actuator_positions_z"]
    corridor = box(x1, x1 + SW["height_above_pcb"] + 0.5, SW["actuator_y"][0], 140.0, z[0] - SW["actuator_width_z"] / 2 - 1.0, z[2] + SW["actuator_width_z"] / 2 + 1.0)
    hits = []
    for p in parts:
        if p.name == "setting_switch_PCM13SMTR":
            continue
        v = p.shape.intersect(corridor).Volume()
        if v > 1e-4:
            hits.append({"part": p.name, "volume_mm3": r3(v)})
    return {"corridor": f"actuator travel from its root (Y {SW['actuator_y'][0]}) to the board edge and the probe space below it to Y 140, across all three positions plus 1.0 mm; every modelled part except the switch is tested. Rails, case and neighbouring modules are not modelled",
            "x": [r3(x1), r3(x1 + SW["height_above_pcb"] + 0.5)], "z": [r3(z[0] - SW["actuator_width_z"] / 2 - 1.0), r3(z[2] + SW["actuator_width_z"] / 2 + 1.0)],
            "blocking_parts": hits, "clear": not hits}


# ---- views ---------------------------------------------------------------------------------
def project(ax, parts, axes, depth_axis, near_is_high=False, section=None):
    cols, polys, order = [], [], []
    for p in parts:
        shp = p.shape
        if section is not None:
            shp = shp.intersect(section)
            if shp.Volume() < 1e-6:
                continue
        try:
            verts, tris = shp.tessellate(0.05, 0.3)
        except Exception:
            continue
        if not tris:
            continue
        V = [(v.x, v.y, v.z) for v in verts]
        for tri in tris:
            pts = [(V[i][axes[0]], V[i][axes[1]]) for i in tri]
            polys.append(pts)
            c = list(p.color)
            c[3] = min(c[3], 0.9)
            cols.append(c)
            order.append(sum(V[i][depth_axis] for i in tri) / 3)
    idx = sorted(range(len(polys)), key=lambda i: order[i] if near_is_high else -order[i])
    ax.add_collection(PolyCollection([polys[i] for i in idx], facecolors=[cols[i] for i in idx], edgecolors="none", linewidths=0))


def dim(ax, a, b, off, text, vertical=False, color="#7a1d1d", fs=6.5):
    if vertical:
        ax.annotate("", xy=(off, a), xytext=(off, b), arrowprops=dict(arrowstyle="<->", lw=.6, color=color, shrinkA=0, shrinkB=0))
        ax.text(off, (a + b) / 2, " " + text, fontsize=fs, color=color, va="center", ha="left", rotation=90 if abs(b - a) > 8 else 0)
    else:
        ax.annotate("", xy=(a, off), xytext=(b, off), arrowprops=dict(arrowstyle="<->", lw=.6, color=color, shrinkA=0, shrinkB=0))
        ax.text((a + b) / 2, off, text, fontsize=fs, color=color, va="bottom", ha="center")


def views(parts, name, out):
    V = L["variants"][name]
    w = V["panel_width"]
    Z, Y, C, SW = L["z_stack"], L["y_layout"], L["controller"], L["switch"]
    files = {}
    title = f"A7 / {name.upper()} / {V['selection']['verdict']} - provisional digital study"
    # transverse section (X-Z) through the lower (THRU) jack
    yj = Y["jack_y"][1]
    fig, ax = plt.subplots(figsize=(8, 11), dpi=170)
    project(ax, parts, (0, 2), 1, section=box(-5, w + 25, yj - 0.05, yj + 0.05, -10, 40))
    ax.axvline(0, color="#555", lw=.5, ls=":")
    ax.axvline(w, color="#555", lw=.5, ls=":")
    ax.axhline(30, color="#a00", lw=.6, ls="--")
    ax.text(w + .3, 30.2, "30 mm installed-depth target", fontsize=6, color="#a00")
    dim(ax, 0, w, -6.2, f"panel {w}")
    dim(ax, 0, V["x_axis"], -5.0, f"jack axis X {V['x_axis']}")
    x0, x1 = V["controller_pcb_x"]
    dim(ax, x0, x1, 16.9, f"PCB {V['pcb_thickness']}")
    dim(ax, 0, V["checks"]["lead_tip_x_nominal"], 4.0, f"lead tip {V['checks']['lead_tip_x_nominal']} (margin {V['checks']['lead_side_nominal_margin']} after 0.3)")
    dim(ax, V["checks"]["body_top_x_nominal"], w, 8.0, f"body side {round(w - V['checks']['body_top_x_nominal'], 2)} (margin {V['checks']['body_side_nominal_margin']} after 0.3)")
    dim(ax, Z["jack_body_front_z"], Z["jack_body_rear_z_nominal"], w + 1.0, f"jack body {Z['jack_body_front_z']}..{Z['jack_body_rear_z_nominal']}", vertical=True)
    dim(ax, Z["controller_pcb_z"][0], Z["controller_pcb_z"][1], -2.0, f"controller Z {Z['controller_pcb_z'][0]}..{Z['controller_pcb_z'][1]}", vertical=True)
    dim(ax, Z["optical_volume_z"][0], Z["optical_volume_z"][1], w + 3.0, f"optical {Z['optical_volume_z'][0]}..{Z['optical_volume_z'][1]}", vertical=True)
    dim(ax, Z["pmma_front_z"], 0, w + 5.0, "PMMA 2.0", vertical=True)
    ax.set_xlim(-8, w + 12)
    ax.set_ylim(31.5, -8.5)
    ax.set_aspect("equal")
    ax.set_xlabel("X (mm, 0 = left panel edge)")
    ax.set_ylabel("Z (mm, 0 = PMMA rear, into the rack)")
    ax.set_title(f"{title}\nTransverse section at THRU jack Y{yj} (nominal; axis height 3.0 INFERRED)", fontsize=8)
    f = out / f"view_A7_{name}_transverse.png"
    fig.savefig(f, bbox_inches="tight", metadata={"Software": None})
    plt.close(fig)
    files["transverse"] = f.name
    # side view (Y-Z) from +X
    fig, ax = plt.subplots(figsize=(14, 6), dpi=170)
    project(ax, parts, (1, 2), 0, near_is_high=True)
    for k in C["keepouts"]:
        ax.add_patch(plt.Rectangle((k["y"][0], k["z"][0]), k["y"][1] - k["y"][0], k["z"][1] - k["z"][0], fill=False, ec="#d07000", lw=.5, ls="--"))
    ax.axhline(30, color="#a00", lw=.6, ls="--")
    ax.axhline(Z["optical_volume_z"][0], color="#3070c0", lw=.5, ls=":")
    ax.text(18, Z["optical_volume_z"][0] - .3, "optical volume front", fontsize=6, color="#3070c0")
    dim(ax, C["outline_y"][0], C["outline_y"][1], -7.5, f"controller Y {C['outline_y'][0]}..{C['outline_y'][1]}")
    for fn, yy in zip(Y["jack_function"], Y["jack_y"]):
        ax.text(yy, -5.6, f"{fn} Y{yy}", fontsize=6, ha="center", color="#222")
    dim(ax, SW["body_y"][0], SW["actuator_y"][1], 13.0, "switch", fs=6)
    ax.annotate("setting switch: reach from below\n(module out of rack)", xy=(111.4, SW["actuator_positions_z"][1]), xytext=(114, 4), fontsize=6, arrowprops=dict(arrowstyle="->", lw=.6))
    ax.set_xlim(10, 125)
    ax.set_ylim(31.5, -9)
    ax.set_aspect("equal")
    ax.set_xlabel("Y (mm, down the panel)")
    ax.set_ylabel("Z (mm)")
    ax.set_title(f"{title}\nSide view from +X (component face); dashed orange = controller keep-outs for R4", fontsize=8)
    f = out / f"view_A7_{name}_side.png"
    fig.savefig(f, bbox_inches="tight", metadata={"Software": None})
    plt.close(fig)
    files["side"] = f.name
    # front view (X-Y) seen from the front (-Z), all parts
    fig, ax = plt.subplots(figsize=(5, 13), dpi=170)
    project(ax, [p for p in parts if p.group != "front"], (0, 1), 2)
    project(ax, [p for p in parts if p.group == "front"], (0, 1), 2)
    for q in Y["labels"]:
        ax.text(V["x_axis"], q["y"], q["text"], fontsize=6, ha="center", va="center", color="#103050", fontweight="bold")
    dim(ax, 0, w, -2.0, f"{w}")
    for yy in Y["jack_y"]:
        ax.plot([V["x_axis"]], [yy], "+", color="#7a1d1d", ms=5)
        ax.text(w + .4, yy, f"Y{yy}", fontsize=6, va="center", color="#7a1d1d")
    ax.text(w + .4, L["supports"]["front_screw_y"][0], "M2", fontsize=6, va="center")
    ax.text(w + .4, L["supports"]["front_screw_y"][1], "M2", fontsize=6, va="center")
    ax.set_xlim(-2, w + 6)
    ax.set_ylim(130, -4)
    ax.set_aspect("equal")
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.set_title(f"A7 / {name.upper()} front view\n(no switch aperture; IN / THRU only)", fontsize=8)
    f = out / f"view_A7_{name}_front.png"
    fig.savefig(f, bbox_inches="tight", metadata={"Software": None})
    plt.close(fig)
    files["front"] = f.name
    return files


def export(parts, out, name):
    assy = cq.Assembly(name=f"zudo_led_block_A7_{name}")
    for p in parts:
        assy.add(p.shape, name=p.name, color=cq.Color(*p.color))
    step = out / f"zudo_led_block_A7_{name}_assembled.step"
    assy.export(str(step))
    glb = out / f"zudo_led_block_A7_{name}_assembled.glb"
    assy.export(str(glb), tolerance=0.08, angularTolerance=0.4)
    imported = cq.importers.importStep(str(step)).val()
    original = cq.Compound.makeCompound([p.shape for p in parts])
    return {"step": step.name, "glb": glb.name, "valid": imported.isValid(), "source_solids": len(original.Solids()),
            "imported_solids": len(imported.Solids()), "volume_difference_mm3": r3(abs(original.Volume() - imported.Volume()))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["2hp", "3hp", "all"], default="all")
    ap.add_argument("--no-export", action="store_true", help="skip STEP/GLB/views (checks only)")
    ap.add_argument("--leaf", choices=["fr4", "pet", "all"], default="all", help="pet builds the PET leaf comparison on the default variant only")
    a = ap.parse_args()
    default = L["decision"]["default_variant"]
    names = [default] + [v for v in L["decision"]["variants_generated"] if v != default] if a.variant == "all" else [a.variant]
    jobs = ([(n, "fr4") for n in names] if a.leaf in ("fr4", "all") else []) + ([(default, "pet")] if a.leaf in ("pet", "all") else [])
    for name, leaf in jobs:
        label = name if leaf == "fr4" else f"{name}_pet"
        out = HERE / "exports" / label
        out.mkdir(parents=True, exist_ok=True)
        print(f"Building {label}", flush=True)
        parts, contacts, cables = build(name, out, leaf)
        rows, collisions, permitted, cable_findings, env = validate(parts, contacts, name)
        opt = optical(parts, name)
        opt_est = optical_estimate(parts, name, opt)
        acc = tool_access(parts, name)
        res = {
            "revision": "A7", "variant": name, "leaf": leaf, "status": "PROVISIONAL_DIGITAL_STUDY_NOT_FIT_APPROVAL",
            "selection": L["variants"][name]["selection"]["verdict"],
            "default_variant": name == default,
            "layout_sha256": hashlib.sha256((HERE / "layout.json").read_bytes()).hexdigest(),
            "input_sha256": {f: hashlib.sha256((REPO / f).read_bytes()).hexdigest() for f in STALE_INPUTS},
            "part_count": len(parts), "all_shapes_valid": all(x["valid"] for x in rows),
            "unexpected_rigid_intersections": collisions, "explicitly_expected_contacts": permitted,
            "cable_findings": cable_findings, "cables": cables,
            "envelope_findings": env,
            "retained_envelope_findings": [x for x in env if x["scope"] not in CONDITIONAL],
            "optical_obstruction": opt, "optical_shading_estimate": opt_est, "switch_tool_access": acc,
            "parts": rows,
            "manufacturing_release": False,
        }
        if not a.no_export:
            res["export"] = export(parts, out, label)
            res["views"] = views(parts, name, out) if leaf == "fr4" else {}
        (out / "verification.json").write_text(json.dumps(res, indent=2) + "\n")
        print(json.dumps({"variant": label, "parts": len(parts), "collisions": collisions, "cable_findings": len(cable_findings),
                          "retained_envelope": res["retained_envelope_findings"],
                          "a7_optical": {k: v["a7_controller_or_support_obstructions"] for k, v in opt.items()}, "tool_access_clear": acc["clear"]}, indent=1), flush=True)


if __name__ == "__main__":
    main()
