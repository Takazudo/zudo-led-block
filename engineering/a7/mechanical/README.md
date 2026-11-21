# engineering/a7/mechanical — A7 R2 digital mechanical model

## Current optical redesign #87 (2026-11-17 JST)

The current prototype selects **3HP, 0.8 mm rigid FR-4 controller and leaf**. The 2HP tolerance sweep did not establish fit; this is not proof that every physical 2HP construction is impossible. Both PCB faces minimize retained mask, and broad GND planes are removed on every layer. Transparent PET/FPC is withdrawn from current variants, default generation and next actions. Its supplier questions are not prerequisites.

See [the authored mechanical rationale](optical-redesign-review.md) and current `design-inputs.json` / generated `layout.json`. The leaf stack is 1.70 mm nominal, 1.45–1.95 mm including the assumed bond tolerance; its cap slot is 2.15 mm. Controller slot is 1.10 mm. Slot/bond tolerances are manufacturing acceptance requirements, not measured capabilities.

The unchanged 1.6 mm, two-layer A5 adapter has no copper zones. Its new shift −4 mm is relative to the **A5 front Z17.4 mm**, giving Z13.4–15.0 mm. It is not another −4 mm from the former A7 position. Current inputs use a 4 mm spacer and an M2x20 top-cap screw. The adapter remains outside the direct lateral leaf corridor; this is not a claim of zero shadowing or measured optical suitability.

Current **A7 power cable** requirement, copied from `layout.json` → `power_cable_requirement` (a test fails if these drift): a **55 ± 3 mm free span**, i.e. 52–58 mm, against an S-fold stowage of 49.0–76.1 mm across both widths, keeping 2 mm off the shortest fold. The ±3 mm is ASSUMED and the A5 50 ± 6 mm cable does not fit. No cable has been routed or measured (#8), so this is a digital requirement, not a verified length. The former 57 ± 3 mm figure belongs to the old adapter position and is historical.

The fastener offset is 3.4 mm. The current cap nut-access channel uses Z28.2–28.6 mm with a nominal 1.2 mm rear bridge; strength, tool use and fit are unmeasured. Final CAD export and verification must bind the final controller/leaf, builder and layout hashes. Interim digital results are not final-revision acceptance. Cable scenario contacts and installed routing remain physical work under #8; they must be reported separately from rigid-body intersections.

The final generated STEP/STL/GLB/verification and preview must be regenerated for the selected current inputs. Do not transfer old CAD PASS, fixture PASS or dated order approval to the new PCB identity. A5 is immutable and A6 remains held.

## R2 assertions after the #87 redesign: 3HP has one left open, 2HP is reported and not selected (2026-11-21)

The CAD exports were regenerated for the adopted 0.8 mm controller and the 1.70 mm FR-4 leaf stack, so
`exports/*/verification.json` is current (its `layout_sha256` and builder/front hashes match). The first
regeneration failed five assertions in
`scripts/tests/test_a7_r2_mechanical.py::Exports::test_cad_verification_current_and_clean`. `unittest` stops at
the first failing assertion of a method, so the table is the result of evaluating each assertion separately
against both widths. No assertion, threshold or corridor definition was changed.

| Assertion | 3HP (selected) now | How it was settled, or why it is open |
|---|---|---|
| Harness ≥ 1.0 mm from every emitter | met: leaf link 3.327 mm (left) / 2.863 mm (right), controller link 2.809 mm | **Geometry.** The leaf-to-leaf link is re-routed (`leaf_link_route` in `build_a7_mechanical.py`): it no longer rises through the right corridor past D2 (was 0.165 mm). The slack is stowed at Z 16.6 in front of the leaf front edge, with the hairpin under the bottom leaf cap, and the rise into the right header stays 2.9 mm below it |
| Ray-sampled shading ≤ 0.05 per LED | met: max 0.028 (`right_D1`); `right_D2` 0.011 (was 0.299) | **Geometry**, same re-route. The guard value is unchanged |
| Leaf-link wires overlapping each other (−0.436 … −0.784) | gone | **Bundle model.** The link is one SH4 assembly, so it is one bundle with the controller link's radius (1.0 mm, ASSUMED) and its own clearance check against every other part, not four wires posed on near-coincident centrelines. No exemption note was added; the unused "carried-over leaf-link" note branch was removed |
| Wire against diffuser (−0.196 / −0.200) | gone | **Geometry.** The bundle leaves each header at the wire-row centre (top Z 24.9), 0.7 mm in front of the diffuser flange (Z 25.6) |
| Cable centreline findings ≥ 0.05 mm | met: one finding left, `spine_PETG` / power cable at +0.100 mm | unchanged pre-existing finding |
| No A7 support in an emission corridor | **OPEN: 2 per side** — `top_leaf_adapter_cap` 31.5 mm² and `bottom_leaf_cap` 10.8 mm² of the 742.5 mm² corridor (4.2 % / 1.5 %), each 1.475 mm from the nearest emitter | **Not settled, and not reachable by reshaping the caps alone.** See below |
| No unexpected rigid intersection | met in 3HP | 2HP only, see below |

**Why the cap assertion stays open.** The corridor is the box from 0.6 mm outside each leaf face to the
diffuser skin over the *whole* leaf (Y 22.5–105.0, Z 19.4–28.4). The caps are inside it at the two leaf ends
for three reasons that are the A5 retention concept itself (`engineering/a5/mechanical/geometry.json`
`optical.mid_guide`: "top/bottom end caps and L-section diffuser flanges retain bonded leaves"):
the leaf-end slot (Y 22.3–26.1 and 103.7–105.2) whose walls hold the leaf pair; the clamp face at Z 27.0
that each diffuser flange is screwed against by the M1.6 leaf fasteners at Y 23.5 / 105.5; and the cap body
itself between Y 22.5 and 23.7. Cutting the corridor out of the caps would leave 0.375 mm slot walls
(slot half-width 1.075, corridor from 1.45) and move the diffuser clamp face to Z 28.4, 1.6 mm behind the
flange — the leaf would no longer be held and the diffuser no longer clamped. A zero count therefore needs
a different leaf-end retention and diffuser mount (or a shorter leaf), which is a design change beyond this
model, or a decision on how a retained A5-topology end support is counted. The cap geometry inside the
corridor is the A5 geometry (the A7 changes — the 2.15 mm slot and the 3HP nut-access lip — only remove
material, and outside the corridor); it counts as A7 since `480bd0c` classified re-dimensioned parts as A7.
That derivation is recorded here as input for the decision; it is **not** used to reclassify the parts or
to redefine the corridor.

**What the caps shade, as a number (3HP, 2026-11-21).** `optical_shading_estimate` now tests the same rays
against the CAD solid of every part that `optical_obstruction` lists in the corridor, and reports it beside
the unchanged harness figure. Fractions of 4000 rays per LED; the columns overlap and do not add up.

| LED | A7 harness (guard ≤ 0.05, unchanged) | A7 supports (`blocked_by_supports`) | A5 hardware (M1.6 leaf screw + nut) | Leaf-mounted (SH4 headers) | Any corridor solid or harness |
|---|---|---|---|---|---|
| `left_D1` | 0.001 | 0.245 (`top_leaf_adapter_cap` 0.245) | 0.109 | 0.003 | 0.264 |
| `left_D2` | 0.018 | 0.002 (`top_leaf_adapter_cap` 0.002) | 0.001 | 0.006 | 0.021 |
| `left_D3` | 0.004 | 0.001 (`top_leaf_adapter_cap` 0.001) | 0.001 | 0.003 | 0.006 |
| `left_D4` | 0.010 | 0.198 (`bottom_leaf_cap` 0.198) | 0.052 | 0.007 | 0.215 |
| `right_D1` | 0.028 | 0.202 (`bottom_leaf_cap` 0.201) | 0.051 | 0.002 | 0.239 |
| `right_D2` | 0.011 | 0.001 (`top_leaf_adapter_cap` 0.001) | 0.000 | 0.005 | 0.013 |
| `right_D3` | 0.000 | 0.002 (`top_leaf_adapter_cap` 0.002) | 0.001 | 0.004 | 0.004 |
| `right_D4` | 0.000 | 0.242 (`top_leaf_adapter_cap` 0.242) | 0.109 | 0.003 | 0.263 |

Ray model, all of it ASSUMED: Lambertian (cosine-weighted) emission from points uniform over the LED body's
outer face; a ray is delivered when it reaches the diffuser skin inner plane, taken as unbounded in Y and Z,
so a ray leaving past the leaf end still counts as delivered unless a solid stops it; no reflection,
scattering, transmission, diffuser behaviour or LED angular data. The end LEDs sit beside a cap (the top cap spans part of the top
LED's own Y range), so about a fifth to a quarter of their rays meet it; the inner LEDs are essentially unaffected. The solid
figures carry **no pass/fail threshold** and are input for the owner's decision on the caps, not an optical
result. The ray/solid test agrees with an analytic box on 20000 rays (0 mismatches).

**2HP (not selected).** 2HP keeps reporting: the 4 leaf-PCB / M1.6-nut overlaps (0.019 / 0.004 mm³ per
side), the same two caps per side, `left_diffuser` / controller link −0.150 mm, and — because 2HP has no
room for the stowage used in 3HP — the leaf-link bundle against the controller rear edge (−0.763 mm), the
bottom-cap fork (−0.833 mm), the solder-face zone (−0.052 mm) and both diffuser skins (0.000 mm). None of
that is tuned away; the test still requires both widths to be clean, so it fails on 2HP as long as 2HP is
generated and checked like a selected width.

Nothing above is a fit, optical or manufacturing approval, and `manufacturing_release` stays false in every
record. The leaf-link route is a PROJECT-CHOICE scenario: bend radius (2.4 mm centreline), the real bundle
section and the stowage are not qualified (#8), and the 50 mm finished length is the A5-sourced SH4 length.

## Historical R2 model and results (before #87)

Everything below describes the old 1.6 mm controller / 0.6 mm leaf model. Its dimensions, optical ray study, PET comparison, PASS claims, “current/default” labels and next actions are historical, not the present design contract. Consult the current inputs and #87 evidence for the new revision.

**Status: provisional digital study.** Nothing here is a measured fit, a part approval or a manufacturing
release. The PJ-324M jack-axis height is INFERRED (≈3.0, band 2.6–3.4); tolerances marked ASSUMED are
unsourced. Tracked in [#17](https://github.com/Takazudo/zudo-led-block/issues/17) (epic #15).

## Files

| File | What it is |
|---|---|
| `design-inputs.json` | R2's own choices (each with a confidence label). Jack, nut, panel, PCB and tolerance inputs come only from `../study/parameters.json` (R1); switch and jack facts from the R1 owner bundles `.claude/skills/component-a7-{pcm13smtr,pj-324m}/facts.json`. |
| `layout.json`, `layout.md` | Generated by `scripts/a7_mechanical_layout.py` (pure Python): width decision, candidate sweep and selection, break-even values, Z/Y stack, per-width X placement, controller outline and keep-outs, load path, cable routes, unresolved inputs. |
| `placement-envelopes.json` | Generated with the layout for R4 routing (#19): controller outline, keep-outs, jack bodies and pin positions, switch body/actuator/pegs and header housings, each in the assembly frame and in a KiCad board frame seen from the component face. No hole or pad sizes. |
| `inputs/r4-board-placement-routed.json`, `r4-placement-check.json` | R4's **routed-board revision 2** export (PR #37 head eb5d833, merged at edf98c2, `authority.py export-placement`, board SHA-256 4453f818…, copied unchanged and byte-identical to main's export. Revision 1 was PR #30, merged at eb8adeb with board ec810aec and checked in #33) and the generated comparison with the envelopes: outline, fixed parts (J1/J2 axis and all five pin pads, J3, J5, SW1) by position, every other part's origin and pad centres against foreign keep-outs, solder-face parts. Courtyards, pad extents, heights and copper are R4's DRC, not checked here. Rebound in #87 to the adopted routed 0.8 mm controller (board SHA-256 d83691d6…, `thickness_mm` 0.8); the retained snapshot is byte-identical to the canonical export. Geometry still needs an independent fresh native gate comparison. |
| `build_a7_mechanical.py` | CadQuery 2.7.0 assembly from `layout.json`. |
| `exports/<width>/zudo_led_block_A7_<width>_assembled.step` / `.glb` | Inspectable assembly (STEP for CAD, GLB for a browser viewer). |
| `exports/<width>/view_A7_<width>_{front,transverse,side}.png` | Dimensioned views generated from the solids. |
| `exports/<width>/verification.json` | Pairwise rigid intersections (expected contacts carry a volume limit), cable centreline clearances, envelope checks, optical-obstruction check by origin (A5 / A7), switch tool access, STEP round trip, and the hashes of its inputs. |

## Commands

```sh
python3 scripts/a7_mechanical_layout.py            # regenerate layout.json / layout.md / placement-envelopes.json
python3 scripts/a7_mechanical_layout.py --check    # fail if stale
python3 engineering/a7/front_panel/build_a7_front.py       # artwork (needs CadQuery 2.7.0, ezdxf, matplotlib)
python3 engineering/a7/mechanical/build_a7_mechanical.py   # assembly, views, verification (same)
python3 -m unittest scripts/tests/test_a7_r2_mechanical.py # geometry tests; fails if the CAD export is stale (CI job "A7 mechanical")
```

Run the front build before the mechanical build (the assembly imports the panel). Both read
`engineering/a5` only through imports and JSON reads; they never write there.

## Historical result: old 3HP candidate and 2HP study

- **3HP working candidate (default):** centred, 1.6 mm FR-4, untrimmed leads. **FEASIBLE ON PAPER** at the
  worst corner. The front artwork, supports, CAD build and placement envelopes all treat it as the default
  variant; every output is still generated for both widths.
- **Why (project decision, 2026-11-08):** the 2HP worst corner is −0.33 / −0.15 mm, the jack-axis height is
  INFERRED and the lead trim is unconfirmed. 2HP reopens when manufacturer axis-height evidence or confirmed
  trim data makes its worst-case margins positive (see the break-even values below and `layout.md`).
- **2HP open candidate:** jack offset 0.6 mm toward the body side, 0.8 mm FR-4, trimmed leads. Chosen by a
  stated rule over R1's own margin calculation swept at 0.05 mm steps. Every nominal margin is positive
  (lead side +0.70, body side +0.70, nut edge +0.30). At the worst corner it is **UNRESOLVED**, not infeasible:
  lead side −0.33, body side −0.15. No 2HP offset/thickness passes the worst corner.
- **What closes 2HP** (one input at a time, `layout.md`): axis height ≤ 3.07 on the lead side and ≥ 2.75 on the
  body side (R1 Q1), or guaranteed trimmed protrusion ≤ 0.67 (Q6) together with an overall-height tolerance
  ≤ 0.05. The hole position tolerance alone cannot close either margin.
- **The controller outline is common to both widths** (Y 48.5–111.4 × Z 0.2–16.4, 1019 mm² against the
  A5 board's 554 mm²). Only its X position and thickness change, so R4 can start before the width is frozen.

## Architecture

- **Frontward controller volume / rear optical volume.** The A5 optical stack is kept: cap 1.4 + leaf 9.0 +
  skin-to-leaf 2.0 = 12.4 mm, so the optical volume is Z 17.4–29.8 within the 30 mm target. The controller ends
  at Z 16.4, 1.0 mm in front of it. The jacks need Z ≥ 14.0, leaving 2.4 mm slack. No A7 controller or support
  part (including the bottom-cap fork and the M2 hardware) enters either leaf emission corridor. The A7 LED
  harness does, but only at the leaf SH4 plug mouth: it steps down there (R 2.5) into the gap behind the
  adapter and is 2.8 mm from LED D2. A ray-sampled estimate (`optical_shading_estimate` in
  `verification.json`) puts the share of D2's rays meeting the harness at about 2 % (3HP 0.019, 2HP 0.016).
  It is an estimate (no reflection, diffuser scattering or LED angular data), not an optical result. The other corridor items are
  A5 carry-overs (leaf connectors and capacitors, caps, hardware, the leaf link).
- **Jacks:** SOFNG PJ-324M, IN at Y 84.3 and THRU at Y 99.3, 15.0 mm pitch. Every Y clearance uses the body
  tolerance envelope about the axis (near 5.4 ± 0.2 MIRROR, far 6.1 ± 0.4 DERIVED-MIRROR). The A5 pitch was
  14.0; it grows so each label sits between the jack envelopes, because a label printed in front of an opaque
  body or a pocket would not light up. Pin 2 and the 6.1 mm edge face the switch (the 5.4 mm edge is the pin-4/5 side,
  per the #24 review reading); the drawing view's sign is still to be re-checked (R1 fact note), and the pin
  functions are INFERRED (Q2). Both jacks seat in 0.5 mm rear pockets, the only R1 option meeting the 1.0 mm
  thread-engagement criterion (1.25 worst case). The rectangular pocket also keys the body against nut
  torque. The pockets are sized across X for the whole INFERRED axis band and the overall-height tolerance
  (2HP X 1.9–9.6, a 0.2 mm wall to the panel edge). Same Sky 3.5mm-nut-e is the dimension reference, and its
  fit is UNVERIFIED.
- **Load path:** insertion goes through the nut to the PMMA front, withdrawal through the body to the pocket
  floor, and torque into the pocket walls. The controller hangs on the two clamped jacks and a printed spine
  slot (Y 50–72). The solder joints carry no primary load.
- **Setting switch:** hanxia HX MSK13C02 (C5149819; replaced C&K PCM13SMTR on 2026-11-12 by owner direction) at
  the bottom PCB edge, on the routed PCM13SMTR pegs. Its 2.7 mm body is 0.1 mm deeper than the 2.6 mm PCM13SMTR,
  so with the pegs fixed the actuator reaches Y 111.45, 0.05 mm past the board edge (recorded and accepted in
  `design-inputs.json`), and the body clears the lower jack by 1.45 mm worst case. The actuator slides along Z.
  The figures in the next lines are from the PCM13SMTR model and are kept for history:
  It is reached from below with the module out of the rack. The tool corridor (actuator root to the board
  edge and below) is clear of every modelled part in both widths; rails, case and neighbours are not modelled.
  The switch body clears the lower jack envelope by 1.5 mm worst case (1.9 nominal); with the corrected R4
  footprint (signal pads 2.5 from the peg line, retention pads Z 1.35–12.65) the pads clear it by 0.3.
- **Solder-face low-profile zone:** parts up to 0.6 mm (0603 resistors, R4) may sit on the −X face outside the
  spine-slot (Y 48.5–72, the full slot engagement), optical-fork, jack-lead and PicoBlade-tail keep-outs. At that height they never reach past the
  trimmed jack lead tips, so the binding 2HP lead-side margin is unchanged; the zone itself clears the side
  plane by +0.07 (2HP) and +1.14 (3HP) at the worst corner. The CAD build carries it as an envelope solid.
  ON / PGM / CV goes on the controller silkscreen (R4).
- **Power:** the A5 separate power adapter (keyed IDC10) is kept unchanged. A vertical IDC10 header needs 8.9 mm
  of X, but the 2HP component face offers 7.0 mm. A PicoBlade harness runs to a header on the controller
  component face. **The adapter sits 2.0 mm further forward than in A5** (front Z 15.4, rear 17.0), which
  opens a 2.4 mm gap to the leaf front edge for the SH4 harness (R2-C6). A printed 2.0 mm boss (R 2.75) on the top cap
  fills the gap at the Y 20.5 screw, and the post nut sits 2.0 mm lower, so the top-cap screw grows from the A5 M2x16
  to M2x18 to keep the A5 2.2 mm of thread past the nut. Clamp load and boss strength are not analysed. The whole
  adapter group (PCB, C5665 header, reference socket, ribbon scenario, nut, screw) counts as A7 in the checks, with
  the A5 reference-envelope overlaps bounded explicitly. The 30 mm datum is unchanged (the adapter stays in front of the leaf). The A5 IDC ribbon side-exit scenario still extends past the 2HP outline (carried over).
- **Harness routes (bundle model):** the controller-to-leaf SH4 route uses exactly the 50 mm finished length
  with R ≥ 2.5. It runs in the adapter/leaf gap, folds once at Y ≈ 75 and returns to J3, now at Z 12.8 (R4). The
  controller PicoBlade (J5) sits at Z centre 8.69 (R4's routed position) so the fold clears its housing.
  The stowage takes 38–120 mm. **A7 power cable (R2-C5, for #8):** the S-fold stowage takes 51.0–78.1 mm
  across both widths. The digital requirement is a 57 ± 3 mm free span (the ±3 is ASSUMED), so 54–60 mm,
  with 2 mm kept off the shortest fold. These figures are copied from `layout.json` →
  `power_cable_requirement` (a test fails if they drift); the value moves with the J5 position. The A5 50 ± 6 cable does not fit. The cable has not been routed or
  measured. In 2HP the last bend is 0.9 mm
  (below the preferred 2.0), the PicoBlade wires have only 0.9 mm of bend room above the mated plug, and the
  2.3 mm tails must be cut like the jack leads (R2-C1).

## Withdrawn PET comparison (historical)

`layout.md` → *LED leaf* and `layout.json` → `leaf_comparison` compare the A5 FR-4 leaf with a clear PET FPC
leaf. `exports/3hp_pet/` is the 3HP assembly built with the PET leaf (`--leaf pet`). FR-4 is not replaced.

- **Stack:** the JLC 1-layer transparent FPC is 0.14 mm (MANUFACTURER_PRIMARY, R1 `pet-fpc.md`). Two films sit on an
  optically clear adhesive (0.1 mm, INFERRED) either side of a clear 0.8 mm PC carrier (INFERRED). The total is
  1.28 mm against FR-4's 1.30, so the stack fits the A5 cap slots. LEDs, connectors, the emission corridors and the
  harness start move only 0.01 mm.
- **Stiffness:** the PET stack is 8–37× less stiff than FR-4. The range runs from fully bonded films to films
  carried by the carrier alone, with typical moduli (INFERRED). Its worst-case buckling load under the SH
  mating push is about 8 N, against about 300 N for FR-4. The film alone buckles at about 0.07 N, so it cannot
  stand without the carrier. The SH mating force itself is UNSOURCED.
- **Re-checks (3HP):** no unexpected intersections, no A7 part in either corridor, and the harness stays 2.8 mm
  from D2. The ray-sampled D2 estimate is 2.0 % (FR-4 1.9 %), and the STEP round trip is clean. The leaf Z range is
  unchanged, so the 0.5 mm jack pockets and the 30 mm depth budget are unaffected. The estimate does not model
  light passing through a clear leaf.
- **Recommendation:** keep FR-4 as the default and fallback. Pursue PET only after three things:
  - JLC answers on reflow/paste, PET-compatible stiffeners and OCA clarity (Q11);
  - a physical SH mating-force and lit-appearance test (#10);
  - R4's electrical PET leaf profile.
- **Open items from the evidence review:**
  - *Unmating pull:* buckling covers only the mating push. Pulling the SH plug loads the pad-to-film bond and the
    film-to-OCA peel, which the carrier does not help. That force is UNSOURCED and joins the physical test in #10.
  - *Carrier lamination:* no supplier or process is identified for laminating the PC carrier with OCA after reflow,
    as factory assembly needs. It is listed beside Q11.
  - *2HP:* the PET variant is built only for 3HP. The X stack differs from FR-4 by 0.02 mm (faces move 0.01 mm),
    the same margin the 3HP checks cleared, so the 2HP picture carries over; 2HP stays parked.

## Not modelled / still physical

PET reflow, adhesive and lit appearance (comparison above), actual cable insulation, bend ratings and labels, nut
torque and PMMA clamp load, pocket appearance and strength, switch actuation force, printed-part shrinkage. See
`layout.md` → *Unresolved inputs* and `../open-questions.md`.
