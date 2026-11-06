# Light Block A4 — recovered front-panel audit

Reviewed 2026-11-06 (Asia/Tokyo).

## Result

The recovered A4 front-panel package is internally consistent and already
implements the requested visual change: clear acrylic with a rear frosted field
and transparent lettering. The generated front and rear artwork, cut geometry,
and panel STEP files can be retained. No geometry or artwork patch was necessary.

This is a front-interface design and fabrication-review package. It is not a
completed module assembly or a confirmed fabrication order. The parent package's
pending rear cradle, electronics layout, and final mechanical stack remain real
work items.

## Independent checks performed on the saved files

The audit reads the existing SVG, DXF, STEP, and coordinate JSON. It does not
regenerate the source package or rely only on its existing `passed` fields.

| Check | 2HP | 3HP |
|---|---:|---:|
| Imported STEP dimensions | 9.8 × 128.5 × 2.0 mm | 14.9 × 128.5 × 2.0 mm |
| Valid STEP solids | 1 | 1 |
| Through openings | 8 | 8 |
| Production SVG filled regions | 6 | 6 |
| Production DXF solid HATCH regions | 6 | 6 |
| Letter counter islands retained as engraving | 5 | 5 |
| Clear-stroke interior samples checked | 3,434 | 3,434 |
| Clear-stroke samples wrongly engraved | 0 | 0 |
| SVG vertex difference from mirrored coordinate snapshot | <0.00000069 mm | <0.00000069 mm |
| DXF vertex difference from mirrored coordinate snapshot | 0 mm | 0 mm |
| Sampled visible perimeter points receiving frost | 20 / 20 | 20 / 20 |

All 29 files covered by the supplied front-panel integrity manifest matched both
the recorded size and SHA-256 hash. DXF units are millimeters; engraving boundaries
are closed and lie at Z0. Production SVG uses explicit outlines and even-odd
filled paths without font-dependent text. The six engraving regions comprise the
main field and five enclosed counter islands. The mirrored rear files retain
TOP at TOP.

The saved summary image and 2HP rear image were visually inspected. Front labels
read normally, rear labels are reflected, and the A/O counter example accurately
illustrates the mask rule. No clipping was observed. The colored background is
explicitly an explanation of transparency, not an optical prediction.

See `independent_front_validation.json` for machine-readable evidence and
`verify_recovered_front.py` for the repeatable read-back audit. A 0.000005 mm
boundary exclusion prevents exact polygon-edge points from being treated as
unambiguous inside/outside samples; this is an audit convention, not a machining
tolerance.

## Meaning of “full frost”

The A4 artwork frosts the **full visible field**, with no clear perimeter border
and no broad unengraved rings around the nutless jacks. Letter strokes and mode
icons remain clear. Enclosed spaces inside O, D, and P are part of the background
and are frosted.

There is one explicitly documented practical exception: small unprocessed seats
under the nominal M2 washers, toggle nut, and rack washers. These total 47.661 mm²
per panel. They lie within the referenced hardware silhouettes under the assumed
registration, including ±0.70 mm nominal rack-screw travel. This is a proposal
based on nominal hardware; final tolerances and washer choices still need to be
reconciled. The front should not be described as literally every square
millimeter frosted except letters.

| Area partition, from saved A4 geometry | 2HP | 3HP |
|---|---:|---:|
| Acrylic remaining after through-cuts | 1,129.072 mm² | 1,784.422 mm² |
| Frosted area | 1,056.885 mm² | 1,712.235 mm² |
| Clear letters and icons | 24.526 mm² | 24.526 mm² |
| Hidden clear hardware seats | 47.661 mm² | 47.661 mm² |

The 0.02 mm extrusion used by the artwork source is only an intermediate Boolean
calculation device. It is not an engraving-depth instruction. The exported
physical panel remains nominally 2 mm thick.

## Process feasibility and evidence

**Material/process:** Trotec's official acrylic guide recommends cast acrylic for
white, high-contrast laser engraving, and describes shallow reverse engraving
with mirrored artwork. Leaving selected strokes outside the engraved region is
the design inference that creates the transparent lettering. The proposed
starting stock is clear cast PMMA; skipping the laser on a pre-matte sheet does
not restore clear letter strokes. Exact haze, minimum preserved stroke width,
finish uniformity, and laser settings remain fabricator-specific.[1]

**Supplier route:** Elecrow's official acrylic service listing includes
transparent 000 and a 2 mm thickness selection. Its notes direct engraving and
etching work to an individual inquiry. That supports the proposed inquiry route,
not a confirmed accepted job or an engraving price. The indexed official page
was available in web search during this audit; a direct page open returned HTTP
403. No account action or supplier message was sent.[2]

**Fastening:** PLEXIGLAS's screw-joint guide calls for stress-free assembly, evenly
distributed force, and avoiding excessive tightening. That supports reviewing
the rear load path and hardware seats, but does not establish a load rating for
this 2 mm panel.[3] ACRYLITE's general point-fastening guidance gives larger
edge-distance/clearance practices than this compact Eurorack layout can provide;
its dimensions are a comparison for prototype handling, not proof of failure or
a product-specific certification.[4]

## Mechanical limits preserved

- A4 changes the toggle hole from the earlier small D profile to a plain Ø6.50 mm
  opening for the selected Dailywell interface. Body anti-rotation must come
  from the rear cradle; the hole is not the manufacturer's keyed opening.
- The selected XKB PJ-3582-B jacks have no front nut. A positive rear cradle must
  take both insertion and withdrawal forces. Their switch/jack/PCB stack is not
  interchangeable with the old A3 assembly.
- Nominal 2HP side ligaments are 1.65 mm at the toggle and 1.80 mm at the jacks.
  Moving to 3HP increases those to 4.20 and 4.35 mm; it does not increase the
  1.40 mm material at the short ends of the rack slots.
- A3's 29.5 mm fixed-body depth and earlier interference checks do not certify
  the changed A4 assembly. No updated full-module fit or cable-bend result was
  inferred from the front STEP.
- A3's 0.4 mm retaining lips were a machined-PC concept. Those files are not a
  finished PETG print package. The user's home-PETG direction remains to be
  implemented in the integrated cradle.
- Final optical contrast and frontal illumination depend on the real LED,
  placement, material, background, and finish. The front artwork is not evidence
  of uniform illumination. The intended test is the completed integrated first
  prototype; this review adds no separate optical-coupon purchase requirement.

## Sources

1. Trotec, *Laser processing on acrylic*: <https://www.troteclaser.com/en-us/helpcenter/materials/material-usage-hints/material-handling-acrylic>.
2. Elecrow, *Acrylic laser cutting service*: <https://www.elecrow.com/acrylic-cutting.html>.
3. PLEXIGLAS, *Joining PLEXIGLAS*, section 6, Screw unions: <https://www.plexiglas.de/files/plexiglas-content/pdf/verarbeitungsrichtlinie/311-3-EN-joining-PLEXIGLAS.pdf>.
4. ACRYLITE, *How far in should I drill a hole from the edge of acrylic sheet?*: <https://www.acrylite.co/resources/knowledge-base/article/how-far-in-should-I-drill-a-hole-from-the-edge-of-acrylic-sheet?category=working-with-acrylite-r>.

Source access and claim scope are also recorded in `front_process_sources.json`.
