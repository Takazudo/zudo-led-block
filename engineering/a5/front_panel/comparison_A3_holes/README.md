# A4 front artwork — full rear frost, transparent letters

**Appearance/mask revision on A3 hole geometry. Mechanical release is pending stock-first switch/jack selection. These files are review data, not an order-ready module release.**

The visible acrylic field is frosted from the rear, and the lettering is left as original clear acrylic. The front remains physically smooth and glossy. This produces the requested foggy plate appearance without requiring ink or paint. Clear cast PMMA is the requested starting material; a pre-matte stock does not become transparent where the laser skips a letter.

## Open first

- `exports/A4_full_frost_clear_letters_summary.png` compares A3 with A4 and shows how the letter counters work.
- `exports/appearance_A4_front_2hp.png` is the main 2HP appearance proposal.
- `exports/appearance_A4_rear_2hp.png` shows the mirrored rear process view, without hardware hiding the seating exclusions.
- Equivalent front and rear previews are included for 3HP.
- `sources/review.md` explains the process evidence, interpretation, and remaining limits.

Colored backgrounds in previews demonstrate transparency. They are not predictions of LED color, haze, brightness, uniformity, or actual sight lines through the module.

## Geometry held constant

| Feature | 2HP | 3HP |
|---|---:|---:|
| Nominal panel width | 9.80 mm | 14.90 mm |
| Panel height | 128.50 mm | 128.50 mm |
| Nominal thickness | 2.00 mm | 2.00 mm |
| Outer corner radius | 0.50 mm | 0.50 mm |
| Rack slots | 4.60 × 3.20 mm | 4.60 × 3.20 mm |
| Slot centers | X = W/2; Y = 3, 125.5 | X = W/2; Y = 3, 125.5 |
| M2 clearance holes | Ø2.20 at Y20.5, 60.8, 65 | Same |
| A3 toggle aperture | Ø4.95-derived D, 4.55 flat span, R0.25 transitions, Y74 | Same |
| A3 jack holes | Ø6.20 at Y90, 104 | Same |

All hole centers are on X = W/2. The current toggle/jack apertures and related seating masks are reference geometry; procurement may change them. No whole-module assembly has been regenerated in A4.

`CUT.svg`, `CUT.dxf`, and `2mm.step` are byte-identical snapshots of the corresponding A3 files. Their embedded A3 identifiers are intentionally retained. A4 only changes the surface operation. The generator independently recreates the panel from `geometry.json` and checks its volume difference against the STEP snapshot.

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

| A3 hardware reference | Clear seating mask | Why it stays hidden |
|---|---|---|
| Three M2 seats | Radius 1.85 mm | Inside a nominal Ø4.00 washer |
| Toggle seat | Radius 3.85 mm | Inside a nominal Ø8.00 washer |
| Two jack seats | Radius 4.10 mm | Inside nominal Ø8.50 washers |
| Each rack slot | Intersection of two radius 2.95 mm circles at X = W/2 ±0.70 mm | Common area inside a nominal Ø6.00 washer across the assumed slot adjustment travel |

The through-holes are also excluded because there is no acrylic there. Fixed-seat masks are 0.15 mm radially inside the current washer silhouette; rack circles have a 0.05 mm inset. The rack mask is deliberately the common overlap, not a large capsule that would leave visible clear halos beside an adjusted screw.

These are artwork and handling choices for the current hardware reference. They do not certify an acrylic bearing stress, thread stack, washer stock, or engraving process. They do not protect every possible rear bearing surface. Revise them with the final purchased hardware. If a fabricator needs a larger process margin at a cut edge, that should be agreed as a visible finish change, rather than silently adding a wide clear border.

## Editable source and regeneration

`build_front_artwork.py` and `geometry.json` define the artwork, dimensions, labels, seat masks, and output generation. `reference_A3/` contains the immutable reference CUT/STEP files and their source manifest. No imports from the separate A3 project are needed.

```bash
python build_front_artwork.py
```

Dependencies used here: Python 3.12, CadQuery 2.7, NumPy, Matplotlib 3.10, and ezdxf 1.4. DejaVu Sans Bold supplies the label outlines, which are converted to explicit polygons in production files. `mask_regions_A4_<width>.json` also stores the editable front-coordinate region geometry.

The 0.02 mm temporary extrusion in `geometry.json` is exclusively a computational device for reliable planar Boolean operations. It is not a proposed etch depth and is not exported as a physical part. Only the unchanged 2 mm panel STEP is provided.

## Verification included

`exports/validation_A4.json` records real BRep validity, exact A3 panel comparison, copied-file hashes, area partition, zero mask overlap with through-holes/letter strokes/seats, mirrored-area and double-reflection checks, counter retention, SVG outline checks, DXF units/elevation, and sampled polygon area error. The separate AO demonstration is also checked for two frosted counters. `exports/manifest_A4.json` maps the operation and preview files.

This validates the authored mask and its registration to the inherited hole pattern. It does not release the final stock-selected hardware, an electronic layout, or a laser/material process.
