# C1 (AP63205 input, +12V_PROT): drop-in substitution options

Status: **OPTION STUDY ONLY**. No BOM, schematic, PCB or catalog entry is changed. A substitution needs the owner's answer to the `criterion:effective-capacitance` decision. All capacitance figures below are typical manufacturer graph data, not guarantees.

## What the datasheet asks of the input capacitor

- AP63205 Table 3 lists C1 = 10 µF for the fixed 5 V part; Section 11 says a ceramic capacitor greater than 10 µF is sufficient for most applications, and does not say whether 10 µF is nominal or effective (`fact-ap63205wu-7-recommended-capacitors`).
- RMS current (Section 11, `src-ap63205wu-7-ds-p12`): "The RMS current rating of the input capacitor is a critical parameter and must be higher than the RMS input current. As a rule of thumb, select an input capacitor which has an RMS rating greater than half of the maximum load current." For the AP63205's 2 A rating that is about 1 A. The Samsung ripple-current graphs (typical, 25 °C) give a temperature rise of about 5 °C at 2.2 A (800 kHz) for the current part, and about 5 °C at 2.2–2.3 A (500–1000 kHz) for CL21A226MAYNNN; CL21A106KBYQNN rises about 0.6 °C at 1.04 A (1000 kHz). fSW is 1100 kHz typ. MLCC ripple current is not a limiting factor for any candidate here.

## Other capacitance on +12V_PROT

On the A7 controller (`engineering/a7/verification/schematic/netlist.xml`) the rail carries only C1 (10 µF CL21A106KAYNNNE) and C11 (100 nF X7R, OPA197 supply). The power adapter board (A5 `power_adapter` netlist: J1 Eurorack header, J2 cable header) has no capacitors. Any bulk capacitance on the rack's own +12 V bus is outside this design and not known. +12V_PROT sits behind the reverse-protection diode D1, so it runs a few tenths of a volt below the Eurorack +12 V (not measured); the figures below use the curve points nearest 11.5 V and 12.2 V.

## Candidates

Search: Samsung MLCC parametric search (`/mlcc/bSearch.do`, query "CL21", 1582 results, response SHA-256 `76df6c08…`, 2026-11-12T10:23Z), filtered to 0805, ≥ 10 µF, ≥ 25 V, mass production, general use. Every result has the same 2.0 × 1.25 mm 0805 body. Only parts with JLC stock and a DC-bias graph are listed.

| Part | JLC (2026-11-12T10:24Z) | Value | Thickness | Graph condition | Typical at ~11.5 V | Typical at ~12.2 V | With tolerance and X5R −15 % |
|---|---|---|---|---|---:|---:|---:|
| CL21A106KAYNNNE (current) | C15850, Basic, stock 8,513,342 | 10 µF ±10 % 25 V X5R | 1.25 ± 0.20 mm | 1 kHz, 1.0 Vrms | 1.95 µF (−80.48 % at 11.569 V) | 1.84 µF (−81.60 % at 12.208 V) | 1.49 / 1.41 µF |
| CL21A106KBYQNNE | C2932476, Extended, stock 384,053 | 10 µF ±10 % 50 V X5R | 1.25 ± 0.20 mm | 1 kHz, 1.0 Vrms | 2.98 µF (−70.16 % at 11.528 V) | 2.84 µF (−71.55 % at 12.018 V) | 2.28 / 2.18 µF |
| CL21A226MAYNNNE | C602037, Extended, stock 411,532 | 22 µF ±20 % 25 V X5R | 1.25 ± 0.20 mm | 120 Hz, 0.5 Vrms | 3.84 µF (−82.56 % at 11.569 V) | 3.62 µF (−83.55 % at 12.208 V) | 2.61 / 2.46 µF |

Not listed: CL21A106KLYQNNE (35 V; no JLC listing; its graph is identical to the 50 V part), CL21K106KAYQNNE (X7R; no JLC listing), CL21X106KAYNNNE (X6S, C307560, stock 2,056; −76.78 % at 11.968 V, about 2.3 µF, less gain than the 50 V part).

The 50 V part gains about 1.5× at the same measurement condition as the current part. The 22 µF part gains about 2× typical, but its graph uses a different measurement condition and its tolerance is ±20 %, so with tolerance the two candidates are close (2.2–2.6 µF). Neither reaches 10 µF effective; that would need more capacitor footprints, which is a layout change.

Retained observation hashes (live pages, not retained in the repository; bytes change on every fetch): Samsung pages CL21A106KAYNNN `6cd4bc2f…`, CL21A106KBYQNN `9595ad4b…`, CL21A226MAYNNN `835adb91…` (2026-11-12T10:23Z); JLC component-list API responses for CL21A106KAYNNNE `79cd9a27…`, CL21A106KBYQNNE `fbbbea10…`, CL21A226MAYNNNE `72cc7ce4…` (2026-11-12T10:24Z). Stock is a dated observation, not a reservation.

## Height and envelopes

C1 is on the component face (side F) of the controller. All candidates have the same 1.25 ± 0.20 mm thickness as the current part, so the component-face height budget in `engineering/a7/mechanical/placement-envelopes.json` and the fixture (which contacts the solder face) are unaffected.

## What a substitution would reopen

The MPN/LCSC identity is not only a BOM row in this repository:

- `engineering/a7/electronics/controller/controller.kicad_pcb` carries an `LCSC` property on C1 (and on C15/C16). Editing it changes the frozen PCB SHA-256 `4453f818…`, which every native ERC/DRC, geometry, fixture-geometry and readiness identity is bound to. Those would need a fresh native run and review even though copper does not change.
- The schematic and `verification/schematic/netlist.xml` carry the same fields; `scripts/a7_procurement.py` refuses a catalog identity that differs from the netlist. The 22 µF part also changes the value field from 10u to 22u.
- The component catalog holds the 30 A5 identities; a new part needs its own `line-a7-…` line and `component-a7-…` owner bundle with sourced facts, as PCM13SMTR has.
- `scripts/native_gate/delta.py` compares every symbol field against the A5 baseline and fails on an unlisted change, so `engineering/a7/verification/authorized_delta.json` would need reviewed `field_changed` entries for C1's MPN and LCSC fields (and the value field for the 22 µF part).
- The procurement ledger, population and readiness are regenerated; a Basic part becomes an Extended part at JLC.
