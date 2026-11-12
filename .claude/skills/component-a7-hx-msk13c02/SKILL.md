---
name: component-a7-hx-msk13c02
description: Resolve exact hanxia HX MSK13C02 (C5149819, SMD) evidence for the Zudo LED Block A7 PCB-side ON / PGM / CV mode setting switch (SW1). Use whenever HX MSK13C02, C5149819, its switch positions, pins, land fit, actuator, ratings, sourcing, substitution or bring-up are relevant.
---

# hanxia HX MSK13C02 (C5149819) — A7 owner bundle

Route here only for the exact identity hanxia HX MSK13C02 / C5149819 (JLC Extended, in stock on
2026-11-12). Not for the C&K PCM13SMTR it replaced on SW1, the SHOU HAN MSK13C02 (C2681567) or
the A5 front toggle.

The only datasheet is a Hanxia "specification for approval" served by JLC/LCSC for C5149819. Its
Part No. field is blank, so every value is a mirror reading (UNVERIFIED) and the binding to this
order code rests on the distributor. The drawing gives the same contact table as PCM13SMTR
(A 1-3, B 2-3, C 3-4, common 3), a 9.7 x 2.7 x 1.4 mm body and a recommended land that the
supplier CAD repeats. The ratings are lower than PCM13SMTR: DC 12 V 0.1 A, -25..+70 C,
10,000 cycles, reflow 250 C max.

SW1 keeps the routed LightBlockA7:PCM13SMTR land; `engineering/a7/electronics/switch-land-fit.json`
compares it with the Hanxia land. The actuator tip sits 0.05 mm past the board edge. Physical
function, contact at 0.33 mA, land fit and reflow survival stay NEEDS BENCH (switch-fit).
A7 line `line-a7-hx-msk13c02` remains outside the immutable A5 reconciliation.
