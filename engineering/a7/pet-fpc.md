# A7 transparent LED board: JLC PET FPC capability capture (R1)

Status: capability capture and open questions only. No PET process, stackup or material is approved,
and nothing has been ordered. The existing A5 FR-4 LED leaf design stays the reference and fallback
until the questions below are answered by JLC in writing. The transparent-LED objective stays open.

Scope reminder from the accepted brief: transparent PET FPC is evaluated for the **LED portions only**.
The controller, power electronics, jack loads and setting-switch loads stay on supported rigid FR-4.
Transparent PET circuit film, the clear cast-PMMA front and the translucent PETG diffuser have
different functions and are not interchangeable.

## What JLC states (retrieved 2026-11-08, hashes in `evidence/sources.json`)

| Item | JLC statement | Source |
|---|---|---|
| Material | Transparent PCB is high-transparency, high-temperature-resistant PET | `src-a7-jlc-transparent-fpc-news` |
| Layers | 1-layer and 2-layer transparent options; PET core 36 µm | `src-a7-jlc-flex-capabilities` (FPC Stack-Up) |
| Finished thickness | 1-layer 0.14 mm, 2-layer 0.24 mm, excluding stiffeners | `src-a7-jlc-flex-capabilities` (FPC Finished Thickness) |
| Coverlay | Transparent FPC: PET 25 µm + adhesive 25 µm | `src-a7-jlc-flex-capabilities` (Coverlay Thickness) |
| Copper | single-sided 18/35 µm; double-sided 12/18/35 µm (general FPC rows; not restated per material) | `src-a7-jlc-flex-capabilities` (Outer Layer Copper Weight) |
| Finish | ENIG 1u"/2u" | `src-a7-jlc-flex-capabilities` (Surface Finish) |
| Transmittance | up to 85% | news page and capability header |
| Temperature | "withstands temperatures up to 200°C" (no duration, no profile, no continuous rating) | news page |
| Assembly | "Fully supports surface-mount technology on transparent substrates" | news page |
| Rigid-flex | "Rigid-flex PCBs are not yet supported" | `src-a7-jlc-flex-capabilities` (Layer Count) |
| Stiffeners | PI 0.1-0.25, FR-4 0.1-1.6 (hot-press bonded), stainless 0.1-0.3, tapes 3M9077 / 3M468 / tesa8854. The page does not say which apply to PET | capabilities page; `src-a7-jlc-fpc-stiffener-guide` |
| Bend radius | ≥ 6× total thickness (1 layer), ≥ 10× (multi-layer) static | `src-a7-jlc-flex-capabilities` (Bend Radius) |
| Low-temperature paste | Standard PCBA only, HASL(lead-free) or ENIG; medium paste reflow 210 ± 5 °C, low paste 180 ± 5 °C; weaker, darker joints | `src-a7-jlc-low-temp-paste` |

## What those statements do not establish

- **Reflow compatibility of the assembled leaf.** A typical lead-free reflow peak (about 245 °C) is above
  the 200 °C PET claim, and the 210 ± 5 °C medium-temperature paste is also above it. Only the low-temperature
  paste (180 ± 5 °C) is below it, and the paste page does not say it applies to flex or PET orders.
- **Continuous operating temperature** of PET film near the LEDs. The 200 °C figure has no duration.
- **THT or wave soldering** on PET. Not stated; the leaf design must stay SMT-only.
- **Assembled-device transparency.** 85% is a film figure. Copper, ENIG pads, LEDs, connectors, adhesive and
  stiffeners all add opaque or tinted area.
- **One-piece rigid-flex.** Not offered. Any controller-to-film joint is a separate connector or cable.

## First electrical checks for a PET leaf (paper only)

These use the A5 leaf contract (four WS2812B-2020-V6 per side, one SH 4-pin link per end, shared limited VLED).
They are ranges for planning, not a design.

- **Supply drop.** 18 µm copper is about 0.98 mΩ/□ (ρ_Cu 1.72e-8 Ω·m / 17.5 µm). An 82.5 mm trace at 1.0 mm width
  is about 81 mΩ each way. Four pixels at full white would draw on the order of 0.15 A. That is about 12 mV each
  way, which is small. A 0.3 mm trace raises it to about 40 mV each way. R2/R4 must recheck it with the real
  current cap and layout.
- **Return path.** On a 1-layer film, VLED, GND and two data lines share one layer. A 2-layer film allows a ground
  return under the data line but doubles the finished thickness to 0.24 mm and adds copper area.
- **Heat.** PET is a poor heat spreader. The A5 51/255 brightness cap is not a thermal qualification on FR-4,
  and it is not one on PET either. Physical thermal testing belongs to #10.
- **Bending and support.** A 0.14 mm film cannot carry the SH connector mating force alone. Under JLC's 6×
  rule the static bend radius is at least about 0.84 mm. Any bend near the LEDs or the connector needs a
  stiffener or a bonded support.

## Questions to send to JLC (not sent; supplier messages are outside this authorization)

1. Which reflow profile and solder paste does JLC use for SMT assembly on transparent PET FPC, and is the
   low-temperature (180 °C) paste available for transparent FPC PCBA?
2. What is the PET film's continuous operating temperature, and for how long does the 200 °C figure apply?
3. Which stiffeners (PI, FR-4, stainless, tape) can be bonded to transparent PET, and do they keep the 0.14 / 0.24 mm
   finished thickness elsewhere?
4. Can a WS2812B-2020 (2.0 × 2.0 mm) and a JST SH SMT header be assembled on transparent FPC in a Standard PCBA
   order? Are any part classes excluded?
5. Is the adhesive in the 25 µm PET + 25 µm adhesive coverlay optically clear after reflow, and does it yellow?
6. Is a transparent (or no) solder mask/coverlay colour available that keeps the 85% figure over traces?
7. Can JLC quote a transparent leaf panel without a rigid-flex joint, with the controller on a separate FR-4 order?

## Decision held for the owner

Whether to keep pursuing PET once JLC answers is a product decision. The default stays: FR-4 leaf as reference
and fallback, PET objective visible and unresolved.
