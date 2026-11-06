# A4 front artwork — full rear frost, transparent letters

**Primary A4 uses the selected Dailywell toggle and XKB nutless jack front interfaces. Rear cradle, PCB stack, and whole-module integration remain pending. These are concrete front-panel review files, not an order-ready module release.**

The visible acrylic field is frosted from the rear, and the lettering is left as original clear acrylic. The front remains physically smooth and glossy. This produces the requested foggy plate appearance without requiring ink or paint. Clear cast PMMA is the requested starting material; a pre-matte stock does not become transparent where the laser skips a letter.

## Open first

- `exports/A4_full_frost_clear_letters_summary.png` compares A3 with A4 and shows how the letter counters work.
- `exports/appearance_A4_front_2hp.png` is the main 2HP appearance proposal.
- `exports/appearance_A4_rear_2hp.png` shows the mirrored rear process view, without hardware hiding the seating exclusions.
- Equivalent front and rear previews are included for 3HP.
- `sources/review.md` explains the process evidence, interpretation, and remaining limits.

Colored backgrounds in previews demonstrate transparency. They are not predictions of LED color, haze, brightness, uniformity, or actual sight lines through the module.

## Current front geometry

| Feature | 2HP | 3HP |
|---|---:|---:|
| Nominal panel width | 9.80 mm | 14.90 mm |
| Panel height | 128.50 mm | 128.50 mm |
| Nominal thickness | 2.00 mm | 2.00 mm |
| Outer corner radius | 0.50 mm | 0.50 mm |
| Rack slots | 4.60 × 3.20 mm | 4.60 × 3.20 mm |
| Slot centers | X = W/2; Y = 3, 125.5 | X = W/2; Y = 3, 125.5 |
| M2 clearance holes | Ø2.20 at Y20.5, 60.8, 65 | Same |
| Dailywell toggle aperture | Plain Ø6.50 at Y74 | Same |
| XKB jack holes | Ø6.20 at Y90, 104 | Same |
| Nominal toggle side ligament | 1.65 mm | 4.20 mm |
| Nominal jack side ligament | 1.80 mm | 4.35 mm |

All hole centers are on X = W/2. No whole-module assembly has been regenerated in A4.

Compared with A3, the only through-cut change is the toggle aperture: its small D profile becomes a plain Ø6.50 circle. The outer outline, rack slots, M2 holes, jack holes, and nominal 2 mm thickness are unchanged. The new CUT and STEP are generated together. The validation checks the whole panel against the A3 STEP with exactly that one additional circular cut.

The first A4 appearance mask, still on the A3 hole geometry, is preserved under `comparison_A3_holes/`. Its own CUT/STEP snapshots are byte-identical to A3. Treat it as a comparison, not the primary hardware interface.

### Selected front hardware

The toggle is **Dailywell 1MS3T1B1M2QES-5 / C908270**, using the B1 1/4-40 bushing. The manufacturer shows a nominal Ø6.35 panel opening with a keyway/tab for the B1 variant. A4 instead specifies a plain **Ø6.50 nominal finished hole**, our clearance design choice, and omits the small fragile acrylic key tab. The rear PETG cradle must provide body anti-rotation. This is not a manufacturer-prescribed substitute mounting method.

The standard MNU-1M01A hex nut is nominally 7.92 mm across flats, 9.19 mm across corners, and 1.57 mm thick. Its circumscribed envelope leaves 0.305 mm per side in the 9.8 mm panel width. The catalog Ø10.80 lockwasher and Ø11.99 locking ring do not fit 2HP; neither is included in the proposed 2HP stack. The front nut contact/thread stack and rear load support still require integrated design review. No countersink is introduced.

The jacks are **XKB PJ-3582-B / C500090**, with nominal Ø6 mm smooth barrels through the retained Ø6.20 holes. There is **no front jack nut or broad washer**. A positive rear cradle must capture the body for both insertion and withdrawal forces. The new jack body and axial PCB stack differ from A3, so the old whole-module collision/depth results do not transfer to this revision.

## Operation files

For each width, use the matched pair:

1. `front_A4_<width>_CUT.dxf` or `.svg`: through-cut outline and holes.
2. `rear_A4_<width>_REAR_FULL_FROST_CLEAR_LETTERS.svg` or `.dxf`: rear surface engraving mask.

**Black filled areas mean ENGRAVE. Clear omissions mean LEAVE CLEAR.** The letter strokes and mode arrows/dot are omitted from the filled field. Enclosed counters inside O, D, and P belong to the background, so they remain filled and are engraved. There are five such counter islands in the actual labels. The A/O example in the summary demonstrates the same rule; it is not additional panel lettering.

The production SVG has real Boolean holes and separate counter-island paths, with no white cover shapes and no font-dependent text objects. The DXF has six solid HATCH regions on `ENGRAVE_REAR_FULL_FROST`; a compatible importer must preserve holes and the separate islands. Inspect its import preview against the supplied appearance/process view. The SVG gives the clearest explicit filled-area representation if a supplier's DXF importer discards hatches.

No laser power, speed, number of passes, kerf compensation, haze specification, or engraving depth is assigned. Colors identify intended operations; the fabricator must assign the process explicitly. Surface engraving is not a through-cut operation.

### Coordinates and orientation

- Front design coordinates: X right, Y down, upper-left panel corner at (0, 0).
- Rear artwork: `Xrear = W − Xfront`, with TOP still at TOP.
- Rear files are **already mirrored**. Do not mirror or invert them again.
- SVG retains the full panel-size artboard in millimeters.
- DXF uses X right/Y up, with the panel top at Y128.5 and all HATCH elevations at Z0.
- Keep the common panel datum and scale 1:1. Do not crop or independently fit the engraving mask.
- Physical STEP rear face is Z0, front is Z−2. It retains the full nominal thickness.

## Small practical exclusions

There is **no clear perimeter band** and no A3-style upper-only frosting patch. The only unprocessed material outside the letter/icon strokes is the following small mask under current hardware silhouettes:

| Hardware reference | Clear seating mask | Why it stays hidden |
|---|---|---|
| Three M2 seats | Radius 1.85 mm | Inside a nominal Ø4.00 washer |
| Dailywell toggle nut seat | Radius 3.85 mm | Inside the standard nut's nominal 7.92 mm across-flats outline at any orientation |
| Two XKB jack seats | No extra mask | There is no front washer to hide a clear ring |
| Each rack slot | Intersection of two radius 2.95 mm circles at X = W/2 ±0.70 mm | Common area inside a nominal Ø6.00 washer across the assumed slot adjustment travel |

The through-holes are also excluded because there is no acrylic there. M2 masks are 0.15 mm radially inside the washer silhouette; the toggle mask is 0.11 mm radially inside the nut's inscribed circle; rack circles have a 0.05 mm inset. The rack mask is deliberately the common overlap, not a large capsule that would leave visible clear halos beside an adjusted screw.

These are artwork and handling choices for the current hardware reference. They do not certify an acrylic bearing stress, thread stack, washer stock, or engraving process. They do not protect every possible rear bearing surface. Revise them with the final purchased hardware. If a fabricator needs a larger process margin at a cut edge, that should be agreed as a visible finish change, rather than silently adding a wide clear border.

## Editable source and regeneration

`build_front_artwork.py` and `geometry.json` define the artwork, dimensions, labels, seat masks, and output generation. `reference_A3/` contains the immutable reference CUT/STEP files and their source manifest. No imports from the separate A3 project are needed.

```bash
python build_front_artwork.py
```

Dependencies used here: Python 3.12, CadQuery 2.7, NumPy, Matplotlib 3.10, and ezdxf 1.4. DejaVu Sans Bold supplies the label outlines, which are converted to explicit polygons in production files. `mask_regions_A4_<width>.json` also stores the editable front-coordinate region geometry.

The 0.02 mm temporary extrusion in `geometry.json` is exclusively a computational device for reliable planar Boolean operations. It is not a proposed etch depth and is not exported as a physical part. The panel STEP contains only full-thickness through-cuts in nominal 2 mm acrylic.

## Verification included

`exports/validation_A4.json` records real BRep validity, the expected single-hole change from A3, STEP round trip, file hashes, area partition, zero BRep-mask overlap with through-holes/letter strokes/seats, mirrored-area and double-reflection checks, counter retention, SVG outline checks, DXF units/elevation, and sampled polygon area error. Engraving curves are sampled at 0.001 mm deflection; this small vector approximation is separately quantified. The separate AO demonstration is also checked for two frosted counters. `exports/manifest_A4.json` maps the operation and preview files.

This validates the authored mask and its registration to the proposed front interfaces. It does not release the integrated rear carrier/PCB assembly, an electronic layout, or a laser/material process.
