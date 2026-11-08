#!/usr/bin/env python3
"""A7 front artwork: clear 2 mm cast PMMA, rear full frost with clear IN / THRU lettering.

Removed from the A5/A4 artwork: the Dailywell switch aperture, the MODE label, the ON / PGM / CV
legends and their arrow/dot icons, and the A5 Y65 controller hole. Kept: outline, rack slots,
the two front M2 screw positions (moved in X to the A7 spine), the rear-frost / front-smooth
finish, the A4 lettering font and cap height, and the hidden seating masks. Jack holes, labels
and the optional rear jack pockets follow engineering/a7/mechanical/layout.json.

The 2D Boolean helpers are imported from the A5 generator (read-only; no bytecode is written
into engineering/a5). The temporary 0.02 mm extrusion is a calculation aid, not an engraving
depth. Provisional design study; not an order file.
"""
from __future__ import annotations

import hashlib
import html
import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "engineering" / "a5" / "front_panel"))
import build_front_artwork as A4  # noqa: E402  (A5 checkpoint helpers, imported read-only)
sys.path.pop(0)

import cadquery as cq  # noqa: E402
import ezdxf  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, Rectangle  # noqa: E402

OUT = HERE / "exports"
LAYOUT = REPO / "engineering" / "a7" / "mechanical" / "layout.json"
F5 = REPO / "engineering" / "a5" / "front_panel" / "geometry.json"
STATUS = "A7 provisional front artwork for the digital study; not an order file, not a fit approval."
DEFL = 0.001
D = 0.02


def front_geometry(L, f5):
    """The A7 front description derived from the layout (also written as geometry.json)."""
    out = {"revision": "A7", "status": STATUS, "units": "mm",
           "datum": "Front design coordinates: X right, Y down, upper-left corner (0,0); rear artwork X_rear = W - X_front.",
           "source": ["engineering/a7/mechanical/layout.json", "engineering/a5/front_panel/geometry.json (outline, slots, finish, font, seat rules)"],
           "panel": f5["panel"], "finish": f5["engraving"]["finish"],
           "removed_from_a5": ["switch aperture (6.50 mm, Y74)", "MODE label", "ON / PGM / CV legends and their arrow/dot icons", "A5 controller M2 hole at Y65"],
           "variants": {}}
    for name, v in L["variants"].items():
        w = v["panel_width"]
        xa = v["x_axis"]
        seat = v["jack_seat_x"]
        clr = 0.2
        pockets = []
        if L["z_stack"]["rear_pocket_depth"] > 0:
            for (y0, y1) in L["y_layout"]["jack_body_y"]:
                pockets.append({"x": [round(seat - clr, 3), round(seat + 6.3 + clr, 3)], "y": [round(y0 - clr, 3), round(y1 + clr, 3)], "depth": L["z_stack"]["rear_pocket_depth"]})
        out["variants"][name] = {
            "width": w, "slot_length": f5["variants"][name]["slot_length"], "mounts": f5["variants"][name]["mounts"],
            "m2_holes": [[v["front_screw_x"][str(y)], y] for y in L["supports"]["front_screw_y"]],
            "m2_hole_diameter": L["supports"]["m2"]["clearance_hole"],
            "jack_holes": [[xa, y] for y in L["y_layout"]["jack_y"]], "jack_hole_diameter": f5["controls"]["jack_hole"],
            "jack_functions": L["y_layout"]["jack_function"],
            "labels": [{"text": q["text"], "x": xa, "y": q["y"], "cap_height": q["cap_height"]} for q in L["y_layout"]["labels"]],
            "rear_pockets": pockets,
            "front_nut_od": 8.0,
        }
    return out


def panel_shape(fg, name):
    v = fg["variants"][name]
    p = fg["panel"]
    w, t = v["width"], p["thickness"]
    sh = cq.Workplane(obj=A4.box(0, w, 0, p["height"], -t, 0)).edges("|Z").fillet(p["outer_corner_radius"]).val()
    for x, y in v["mounts"]:
        sh = sh.cut(A4.slot(x, y, v["slot_length"], p["mount_slot_width"], -t - 1, 1))
    for x, y in v["m2_holes"]:
        sh = sh.cut(A4.cyl(v["m2_hole_diameter"] / 2, t + 2, (x, y, -t - 1)))
    for x, y in v["jack_holes"]:
        sh = sh.cut(A4.cyl(v["jack_hole_diameter"] / 2, t + 2, (x, y, -t - 1)))
    for q in v["rear_pockets"]:
        sh = sh.cut(A4.box(q["x"][0], q["x"][1], q["y"][0], q["y"][1], -q["depth"], 0.5))
    return sh


def through_shape(fg, name):
    """Through-cut profile only (pockets are a separate rear operation)."""
    g = json.loads(json.dumps(fg))
    g["variants"][name]["rear_pockets"] = []
    return panel_shape(g, name)


def label_regions(v):
    regions, counters, desc = [], [], []
    for q in v["labels"]:
        regs = A4.nested_regions(A4.glyph_polys(q["text"], q["x"], q["y"], q["cap_height"]))
        regions += regs
        for reg in regs:
            counters += reg[1:]
        desc.append({**q, "stroke_regions": len(regs), "counters": sum(len(x) - 1 for x in regs)})
    return regions, counters, desc


def seating_masks(f5, v):
    q = f5["engraving"]
    shapes, desc = [], []
    r = f5["front_washers"]["m2"]["od"] / 2 - q["fixed_seat_inset_from_washer_radius_mm"]
    for x, y in v["m2_holes"]:
        shapes.append(A4.cyl(r, D, (x, y, 0)))
        desc.append({"kind": "m2", "center": [x, y], "radius_mm": r, "hidden_inside_nominal_washer_silhouette": True})
    travel = q["rack_nominal_center_travel_mm"]
    rr = f5["front_washers"]["rack"]["od"] / 2 - q["rack_seat_inset_from_washer_radius_mm"]
    for x, y in v["mounts"]:
        shapes.append(A4.cyl(rr, D, (x - travel, y, 0)).intersect(A4.cyl(rr, D, (x + travel, y, 0))))
        desc.append({"kind": "rack", "center": [x, y], "circle_radius_mm": rr, "circle_center_offset_mm": travel})
    return A4.compound(shapes), desc


def pocket_solids(v):
    return [A4.box(q["x"][0], q["x"][1], q["y"][0], q["y"][1], 0, D) for q in v["rear_pockets"]]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_svg(path, regions, w, h, layer, desc, fill="#000000", stroke="none"):
    paths = "\n".join(f'  <path id="{layer.lower()}_{i:02d}" d="{A4.svg_path(reg)}" fill="{fill}" stroke="{stroke}" stroke-width="0.025" fill-rule="evenodd"/>'
                      for i, reg in enumerate(regions))
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" viewBox="0 0 {w} {h}">\n'
                    f'<title>{html.escape(path.stem)}</title>\n<desc>{html.escape(desc)}</desc>\n'
                    f'<g id="{layer}">\n{paths}\n</g>\n</svg>\n')


def write_cut(fg, name, through, out):
    w, h, t = fg["variants"][name]["width"], fg["panel"]["height"], fg["panel"]["thickness"]
    cut = A4.shape_regions(through, 0.0005)[0]
    svg = out / f"front_A7_{name}_CUT.svg"
    write_svg(svg, [cut], w, h, "CUT_THROUGH", STATUS + " Nominal finished-size through-cut; no kerf compensation. Rear frost and rear pockets are separate files.", fill="none", stroke="#ff0000")
    flipped = through.rotate((0, 0, 0), (1, 0, 0), 180).translate((0, h, -t))
    dxf = out / f"front_A7_{name}_CUT.dxf"
    cq.exporters.export(cq.Workplane(obj=flipped).faces(">Z").wires(), str(dxf))
    doc = ezdxf.readfile(dxf)
    doc.units = 4
    doc.header["$MEASUREMENT"] = 1
    doc.layers.new("CUT_THROUGH", dxfattribs={"color": 1})
    for e in doc.modelspace():
        e.dxf.layer = "CUT_THROUGH"
    doc.saveas(dxf)
    return cut


def write_pockets(fg, name, out):
    v = fg["variants"][name]
    w, h = v["width"], fg["panel"]["height"]
    regs = [[[[w - q["x"][1], q["y"][0]], [w - q["x"][0], q["y"][0]], [w - q["x"][0], q["y"][1]], [w - q["x"][1], q["y"][1]]]] for q in v["rear_pockets"]]
    if not regs:
        return None
    svg = out / f"rear_A7_{name}_JACK_POCKETS.svg"
    write_svg(svg, regs, w, h, "REAR_POCKET_0P5", STATUS + f" Rear face up, already mirrored. Rectangular rear pockets, nominal depth {v['rear_pockets'][0]['depth']} mm (R1 option rear-pocket; depth tolerance, appearance and strength are open, R1 Q8).", fill="#0050ff")
    return svg.name


def render(fg, name, material_regs, mask_regs, out, rear=False):
    v = fg["variants"][name]
    w, h = v["width"], fg["panel"]["height"]
    fig, ax = plt.subplots(figsize=(3.5, 11.8), dpi=200)
    fig.patch.set_facecolor("#edf1f3")
    mat = A4.map_regions(material_regs, w, h, rear=rear)
    fr = A4.map_regions(mask_regs, w, h, rear=rear)
    A4.backdrop(ax, mat, w, h)
    ax.add_patch(A4.patch(fr, "#f4f6f6", alpha=.94))
    ax.add_patch(A4.patch(mat, "none", "#40596a", 1, .6))
    if not rear:
        for x, y in v["m2_holes"]:
            ax.add_patch(Circle((x, y), 2.0, facecolor="#c3cad0", edgecolor="#6e7c88", lw=.45))
            ax.add_patch(Circle((x, y), 1.1, facecolor="#34434f", edgecolor="none"))
        for x, y in v["mounts"]:
            ax.add_patch(Circle((x, y), 3.0, facecolor="#c3cad0", edgecolor="#6e7c88", lw=.45))
            ax.add_patch(Circle((x, y), 1.6, facecolor="#34434f", edgecolor="none"))
        for x, y in v["jack_holes"]:
            ax.add_patch(Circle((x, y), v["front_nut_od"] / 2, facecolor="#c3cad0", edgecolor="#6e7c88", lw=.45))
            ax.add_patch(Circle((x, y), 3.0, facecolor="#66747f", edgecolor="#405260", lw=.45))
            ax.add_patch(Circle((x, y), 1.8, facecolor="#34434f", edgecolor="none"))
    else:
        for q in v["rear_pockets"]:
            ax.add_patch(Rectangle((w - q["x"][1], q["y"][0]), q["x"][1] - q["x"][0], q["y"][1] - q["y"][0], fill=False, edgecolor="#0050ff", lw=.6, ls="--"))
    ax.set_xlim(-1.4, w + 1.4)
    ax.set_ylim(h + 1.5, -1.5)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.suptitle(f"A7 / {name.upper()} / " + ("REAR" if rear else "FRONT"), fontsize=13, fontweight="bold", y=.985, color="#263f50")
    fig.text(.5, .952, "Already mirrored; dashed = 0.5 mm jack pockets (frosted floor)" if rear else "Frosted field + clear IN / THRU", ha="center", fontsize=8.3, color="#48616e")
    fig.text(.5, .021, "Provisional digital study; nut/jack positions from layout.json\nProcess-area illustration, not a light-output simulation", ha="center", fontsize=7.4, color="#536a77")
    dest = out / f"appearance_A7_{'rear' if rear else 'front'}_{name}.png"
    fig.savefig(dest, bbox_inches="tight", pad_inches=.13, metadata={"Software": None})
    plt.close(fig)
    return dest.name


def build_variant(fg, f5, name, out):
    v = fg["variants"][name]
    w, h = v["width"], fg["panel"]["height"]
    panel = panel_shape(fg, name)
    through = through_shape(fg, name)
    material = A4.thin_panel(through, D)
    lab, counters, ldesc = label_regions(v)
    letters = A4.compound([A4.extrude_region(x, D) for x in lab])
    seats, sdesc = seating_masks(f5, v)
    pockets = pocket_solids(v)
    # Pocket floors stay in the frost field (frosted after pocketing) so the front keeps one uniform
    # field; whether the pocket walls still read through the clear front is open (R1 Q8).
    mask = material.cut(letters).cut(seats).clean()
    material_regs = A4.shape_regions(material, DEFL)
    mask_regs = A4.shape_regions(mask, DEFL)
    write_cut(fg, name, through, out)
    rear_svg = out / f"rear_A7_{name}_REAR_FULL_FROST_CLEAR_LETTERS.svg"
    write_svg(rear_svg, A4.map_regions(mask_regs, w, h, rear=True), w, h, "ENGRAVE_REAR_FULL_FROST",
              STATUS + " Rear face up; keep TOP at TOP. Already mirrored X=W-X. Black filled regions are ENGRAVE (frost). Clear omissions: IN/THRU letter strokes, hidden M2/rack seats and through-holes. Jack pocket floors are frosted too (frost after pocketing). Do not mirror again. No engraving depth or laser settings assigned.")
    rear_dxf = rear_svg.with_suffix(".dxf")
    A4.write_engrave_dxf(rear_dxf, mask_regs, w, h)
    pocket_file = write_pockets(fg, name, out)
    step = out / f"front_A7_{name}_2mm.step"
    cq.exporters.export(panel, str(step))
    imported = cq.importers.importStep(str(step)).val()
    front_png = render(fg, name, material_regs, mask_regs, out)
    rear_png = render(fg, name, material_regs, mask_regs, out, rear=True)
    clear_letters = material.intersect(letters)
    ddoc = ezdxf.readfile(rear_dxf)
    hatches = list(ddoc.modelspace().query("HATCH"))
    dxf_regions = [[[[float(x), float(y)] for x, y, *_ in pa.vertices] for pa in ht.paths] for ht in hatches]
    outer = cq.Workplane(obj=A4.box(0, w, 0, h, 0, D)).edges("|Z").fillet(fg["panel"]["outer_corner_radius"]).val()
    voids = outer.cut(material)
    counter_checks = []
    for i, q in enumerate(counters):
        cs = A4.extrude_region([q], D)
        counter_checks.append({"index": i, "area_mm2": round(cs.Volume() / D, 4), "unengraved_area_mm2": round(cs.cut(mask).Volume() / D, 6)})
    a5_labels = [q["text"] for q in f5["engraving"]["labels"]]
    removed = [t for t in a5_labels if t not in [q["text"] for q in v["labels"]]]
    m = {
        "variant": name, "width_mm": w, "height_mm": h, "panel_thickness_mm": round(imported.BoundingBox().zlen, 6),
        "labels": ldesc, "labels_removed_from_a5": removed,
        "switch_aperture_present": False,
        "through_profile_loops": len(material_regs[0]),
        "expected_through_profile_loops": 1 + len(v["mounts"]) + len(v["m2_holes"]) + len(v["jack_holes"]),
        "engraved_area_mm2": round(mask.Volume() / D, 3), "clear_letter_area_mm2": round(clear_letters.Volume() / D, 3),
        "engraved_fraction_of_material": round(mask.Volume() / material.Volume(), 5),
        "engraved_connected_regions": len(mask.Solids()), "label_counter_islands": len(counters),
        "counter_checks": counter_checks,
        "mask_intersection_through_holes_mm2": round(mask.intersect(voids).Volume() / D, 9),
        "mask_intersection_clear_letters_mm2": round(mask.intersect(letters).Volume() / D, 9),
        "pocket_floor_frosted_mm2": round(sum(mask.intersect(pk).Volume() for pk in pockets) / D, 6),
        "pocket_floor_area_mm2": round(sum(pk.cut(voids).cut(letters).Volume() for pk in pockets) / D, 6),
        "letters_inside_material": round(letters.cut(material).Volume() / D, 9) < 1e-6,
        "letters_clear_of_nut_and_holes": all(math.dist((q["x"], q["y"]), (x, y)) - q["cap_height"] / 2 > v["front_nut_od"] / 2 for q in v["labels"] for x, y in v["jack_holes"]),
        "labels_clear_of_pockets": all(not (q["y"] + q["cap_height"] / 2 > pk["y"][0] and q["y"] - q["cap_height"] / 2 < pk["y"][1]) for q in v["labels"] for pk in v["rear_pockets"]),
        "dxf_hatch_area_delta_mm2": round(abs(A4.area_of_regions(dxf_regions) - A4.area_of_regions(mask_regs)), 9),
        "svg_contains_font_text": bool(ET.parse(rear_svg).findall(".//{http://www.w3.org/2000/svg}text")),
        "step_roundtrip_valid": imported.isValid(),
        "step_roundtrip_difference_mm3": round(panel.cut(imported).Volume() + imported.cut(panel).Volume(), 9),
        "jack_pocket_count": len(v["rear_pockets"]),
        "files": {"cut_svg": f"front_A7_{name}_CUT.svg", "cut_dxf": f"front_A7_{name}_CUT.dxf", "step": step.name,
                  "rear_frost_svg": rear_svg.name, "rear_frost_dxf": rear_dxf.name, "rear_pockets_svg": pocket_file,
                  "front_preview": front_png, "rear_preview": rear_png},
    }
    m["passed"] = all([
        m["through_profile_loops"] == m["expected_through_profile_loops"], not m["switch_aperture_present"],
        set(removed) >= {"MODE", "ON", "PGM", "CV"}, m["mask_intersection_through_holes_mm2"] < 1e-6,
        m["mask_intersection_clear_letters_mm2"] < 1e-6, abs(m["pocket_floor_frosted_mm2"] - m["pocket_floor_area_mm2"]) < 1e-6,
        m["letters_inside_material"], m["letters_clear_of_nut_and_holes"], m["labels_clear_of_pockets"], m["dxf_hatch_area_delta_mm2"] < 1e-6,
        not m["svg_contains_font_text"], m["step_roundtrip_valid"], m["step_roundtrip_difference_mm3"] < 1e-6,
        all(c["unengraved_area_mm2"] < 1e-6 for c in counter_checks)])
    return m


def main():
    L = json.loads(LAYOUT.read_text())
    f5 = json.loads(F5.read_text())
    fg = front_geometry(L, f5)
    OUT.mkdir(exist_ok=True)
    (HERE / "geometry.json").write_text(json.dumps(fg, indent=2) + "\n")
    rows = [build_variant(fg, f5, name, OUT) for name in fg["variants"]]
    for m in rows:
        print(json.dumps({"variant": m["variant"], "passed": m["passed"], "loops": m["through_profile_loops"], "regions": m["engraved_connected_regions"]}))
    (OUT / "validation_A7.json").write_text(json.dumps({"revision": "A7", "status": STATUS, "variants": rows, "all_passed": all(m["passed"] for m in rows)}, indent=2) + "\n")
    if not all(m["passed"] for m in rows):
        raise SystemExit("A7 front validation failed; see exports/validation_A7.json")


if __name__ == "__main__":
    main()
