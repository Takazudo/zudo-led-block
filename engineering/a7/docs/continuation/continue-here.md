# A7: continue here

Durable hand-off for the A7 structural redesign ([#15](https://github.com/Takazudo/zudo-led-block/issues/15)).
Read this first, then [`evidence-index.md`](evidence-index.md). The Japanese status pages on the docs site
(`doc/src/content/docs/project/a7.mdx`, `next-actions.mdx`) say the same thing for readers.

**A7 is a design study. It is not released for manufacture.** The integrated digital result is on `main`: the
reviewed controller schematic, the routed controller board (native gate PASS, independent layout/electrical review
approved), and a provisional digital mechanical model and front artwork checked against that board. There is no
prototype and no physical measurement. Nothing in A7 is a measured fit, part approval, fit approval, electrical result or
manufacturing approval, and a green CI is none of those either.

Last synchronised with `main` at `a9709b3` (2026-11-08 UTC).

## What A7 is

Accepted direction from the owner (2026-11-08):

- Front: the existing illuminated artwork on clear 2 mm cast PMMA (128.5 mm high), plus two front-facing
  3.5 mm CV jacks, IN and THRU. The front switch aperture, MODE label and ON / PGM / CV legends go away;
  the rear-frosted / front-smooth look and the illuminated lettering stay.
- Mode selection moves to a small PCB-side setting switch, used before installation or with the module out.
- Right-angle threaded jack SOFNG PJ-324M (LCSC C22355739), mono CV only, with the controller PCB
  perpendicular to the front so enclosure depth becomes routing area.
- Width: 2HP (9.8 mm) preferred, 3HP (14.9 mm) accepted fallback. Coordinator working decision: 3HP is the
  working candidate, and R2 made it the default of the generated artwork, supports and CAD; the 2HP 0.6 mm-offset
  arrangement stays parameterised and open (worst corner −0.33 / −0.15 mm, reopens on Q1 or Q6 evidence).
- Kept from A5: 30 mm installed depth from the PMMA rear, two independent four-pixel RGB streams, shared
  current-limited LED power, passive CV IN-to-THRU, MCU pin assignments, CV transfer, power/startup
  behaviour, factory assembly with finished plug-in cables.
- Transparent PET FPC is evaluated for the LED leaves only. Controller, power and all jack/switch loads stay
  on rigid FR-4. The A5 FR-4 leaf stays the reference and fallback while PET suitability is open.

## Where each revision stands

| Revision | Location | Status | Use it for |
|---|---|---|---|
| A5 | `engineering/a5/` | Immutable byte-for-byte checkpoint (2026-11-06 JST). Controller placed, unrouted. All ERC/DRC/test results are historical records | the reference netlist, pin assignments, firmware, BOM and evidence A7 builds on |
| A6 | branch `claude/project-thread-391rx3` @ `7e96380`, draft PR [#14](https://github.com/Takazudo/zudo-led-block/pull/14), issue [#7](https://github.com/Takazudo/zudo-led-block/issues/7) | **Held, not merged.** Fixed 8.8 mm controller, placed but unrouted (125 unconnected); automated routing never reached zero | routing-attempt records only. A7 does not complete A6, and A6 work is not counted as A7 progress |
| A7 | `engineering/a7/` | Study, verification foundation, reviewed schematic, routed and reviewed controller board, and provisional digital mechanical model merged; no physical qualification | everything new |

## Task map (epic #15)

| Task | Issue | State on `main` | Where |
|---|---|---|---|
| R1 parts and dimension study | [#16](https://github.com/Takazudo/zudo-led-block/issues/16) | merged in PR #23 (`54bda11`), issue closed | `study/`, `evidence/`, `pet-fpc.md`, `open-questions.md`, `.claude/skills/component-a7-*` |
| R2 mechanical model and artwork | [#17](https://github.com/Takazudo/zudo-led-block/issues/17) | merged in PR [#25](https://github.com/Takazudo/zudo-led-block/pull/25) (`64bd3b7`), the harness follow-up PR [#27](https://github.com/Takazudo/zudo-led-block/pull/27) (`d27f578`), PR #29, and the placement checks against R4's board PRs #31–#33 (`dd45ed5`); provisional digital study, issue open | `mechanical/`, `front_panel/`, `scripts/a7_mechanical_layout.py` |
| R3 native verification foundation | [#18](https://github.com/Takazudo/zudo-led-block/issues/18) | merged in PR #22 (`02992fa`), issue closed | `verification/`, `scripts/native_gate/` |
| R4 schematic, placement, routing | [#19](https://github.com/Takazudo/zudo-led-block/issues/19) | schematic merged in PR [#24](https://github.com/Takazudo/zudo-led-block/pull/24) (`5f6865b`); routed board merged in PR [#30](https://github.com/Takazudo/zudo-led-block/pull/30) (`eb8adeb`, board `ec810aec…74f2`, gate PASS, review approved); issue open for the physical gates | `electronics/`, `verification/`, `scripts/a7_electronics.py`, `scripts/a7_board.py`, `scripts/a7_route.py` |
| R5 docs, status, continuation | [#20](https://github.com/Takazudo/zudo-led-block/issues/20) | this document; reflects the integrated digital result | `docs/continuation/`, Japanese site pages |

The A5 component catalog (30 identities) merged in PR #21 (`20b2f8f`); issue
[#9](https://github.com/Takazudo/zudo-led-block/issues/9) stays open for manufacturer sources that could not be
retrieved.

## Done (digital)

- **R4 board (PR #30, `eb8adeb`).** `electronics/controller/controller.kicad_pcb`, SHA-256
  `ec810aecd9e67e2806f8886e43f3944bf35c1051dcc4a52f23332216025e74f2`, 16.2 × 62.9 mm, 4 layers, 1.6 mm, In1 solid GND.
  Fresh KiCad 10.0.8 gate PASS on the committed board: ERC 0, parity 0 (independent pad parity 0), DRC 0, unconnected 0,
  zone refill identical, regeneration preserves the board, 51 interface checks, every negative control detected
  (runs 42499745759 on `e2a2219`, 42500103564 on `main`).
- **Rule delta:** vias 0.6/0.3 → 0.5/0.2 mm and the board-wide minimum through-hole diameter 0.3 → 0.2 mm (U1 QFN28 and U5 VSSOP-8 fan-out), recorded as `native_gate.json` → `design_rule_delta`, backed by
  `verification/fab/jlcpcb_capabilities.json` (URL, retrieval SHA-256, quoted rows: multilayer min 0.15 hole / 0.25 via,
  preferred min hole 0.2). Track width, clearances, annular ring 0.15 mm and layer count are A5's.
- **Independent review:** first pass on `493155e` requested changes (B1 buck hot loops, B2 CV analog placement;
  S1 decoupling, S2 under-QFN routing). Re-review on `e2a2219` approved the digital board. Non-blocking polish left:
  C11 5.8 mm from U6.5; one more GND stitch via near C17 / U7; nearest +5 V cap to U4.1 is C2 at 4.1 mm; CV_FILTER
  runs about 0.9 mm beside VLED. Changing any of them changes the board hash and needs the gate, review and R2 check again.
- **R2 fit check (PR #33):** `mechanical/r4-placement-check.json` compares R4's routed export with the envelopes:
  outline matches, 64 parts, fixed parts (J1 / J2 axis and all pins, J3, J5, SW1) in position, no origin or pad centre
  in a foreign keep-out, solder face only resistors and test pads (≤ 0.6 mm). Courtyards, pad extents, heights and
  copper are outside that check (they are R4's DRC). The board is 1.6 mm, i.e. the 3HP working candidate; 2HP would
  need a 0.8 mm board and new routing.
- **R2 mechanical (PR #25, #27, #29):** 3HP FEASIBLE ON PAPER and the default; 2HP open (worst corner −0.33 / −0.15 mm).
  Jacks at Y 84.3 / 99.3 in 0.5 mm rear pockets; A5 adapter 2.0 mm forward with an M2x18 top-cap screw; power cable
  requirement from `mechanical/layout.json` → `power_cable_requirement` (currently 57 ± 3 mm, ±3 ASSUMED).
- **R4 schematic (PR #24):** J1, J2 and SW1 replaced; every other part and net unchanged from A5.


## In progress (no result on `main`)

- **Board revision 2:** the four non-blocking polish items plus a stricter PTH-to-track rule. A new board hash means
  re-running the gate, a new independent review and a new R2 fit check.
- **PET FPC leaf evaluation** (`engineering/a7/pet-fpc.md`): LED leaves only; the A5 FR-4 leaf stays reference and
  fallback. The JLC questions are drafted, not sent.

## Next actions, in order

Most remaining work needs parts, a prototype or an owner decision.

1. **Physical and owner gates:** PJ-324M pin functions by TS / TRS continuity test (Q2), slot sizes (Q3, the board
   still uses ASSUMED 1.6 × 0.8 mm slots), axis height (Q1, INFERRED), PCM13SMTR stock and fit (Q10, body centring
   ASSUMED), and the owner's 2HP decision.
2. **External evidence** listed in `../../open-questions.md` (Q0–Q11; Q12 is decided). Only the JLC PET questions are
   drafted (`../../pet-fpc.md`), and they are **not sent**; the others are not drafted. Sending supplier messages is
   outside the current authorisation.
3. **Optional board polish** (the four non-blocking items above), with gate, review and R2 check re-run.
4. **Physical qualification** with [#8](https://github.com/Takazudo/zudo-led-block/issues/8) (harness, power cable,
   fit, PETG), [#10](https://github.com/Takazudo/zudo-led-block/issues/10) (power / CV / firmware / optical / thermal /
   load, manufacturing files) and [#13](https://github.com/Takazudo/zudo-led-block/issues/13) (WS2812B T1L timing).
5. **Manufacturing files and release** are an owner decision and outside the current authorisation.

## Blockers

| Blocker | Blocks | Needs | Tracked in |
|---|---|---|---|
| No manufacturing files (Gerber, drill, per-board BOM / CPL) | prototype order | physical gates and an owner release decision (out of scope) | #10 |
| Board is 1.6 mm (3HP only) | a 2HP build | owner 2HP decision, then a 0.8 mm board and new routing | #17, #19 |
| 2HP unresolved at the worst corner | width choice | Q1 axis height or Q6 trim evidence (break-even values in `mechanical/layout.md`) | #17 |
| A7 power cable 57 ± 3 mm (±3 ASSUMED), not routed or measured | power harness | cable sourcing and measurement | #8 |
| Adapter boss and M2x18 clamp load not analysed | adapter retention | analysis and printed part | #8 |
| PJ-324M axis height only inferred (≈3.0, band 2.6–3.4) | 2HP lead-side margin | dimensioned drawing, 3D model or measured part | Q1 |
| PJ-324M pin functions inferred | CV_THRU vs GND mapping | bench continuity test with TS and TRS plugs | Q2, #10 |
| PJ-324M hole sizes not on the drawing | footprint (routed board uses ASSUMED slots) | JLC/EasyEDA footprint inspection, maker answer or part | Q3 |
| Nut supply and fit unknown | front retention | supplier answer or part | Q4 |
| PCM13SMTR JLC stock 0; land fit and body centring unconfirmed | side switch sourcing and fit | stock, or a printed per-position table / bench check for an alternate | Q10 |
| Maker-hosted drawings unavailable | any drawing fact counting as PASS | SOFNG / C&K documents | Q0 |
| PET FPC process answers missing | transparent LED leaf | JLC written answers (questions not sent) | Q11 |
| No physical prototype | every fit, electrical, optical, thermal result | owner-approved build | #8, #10 |
| Agent-instruction pages on the site | publication scope | owner decision | #12 |

## Rules that do not change

- Never edit, regenerate or reformat `engineering/a5/`. Run
  `python3 scripts/verify_seed.py --manifest provenance/seed-manifest.json --repo .` before and after.
- Never hand-edit generated files: `doc/src/content/docs/components/`, the `scripts/a5_site.py` outputs,
  `engineering/a7/study/results.json` / `report.md`, and everything under `engineering/a7/electronics/`
  (derived by `scripts/a7_electronics.py generate`; see `verification/source_authority.json`).
- A7 catalog lines use `line-a7-` IDs and `component-a7-` owner bundles; they never count toward the A5
  30 / 71 / 81 reconciliation.
- Keep facts that were not verified at their real state (`UNVERIFIED`, `UNSOURCED`, `NEEDS BENCH`, `INFERRED`,
  `ASSUMED`). Missing evidence is not proof of infeasibility; record it as open.
- Production hosting stays off (`CLOUDFLARE_DEPLOY_ENABLED` is not set). Manufacturing release, purchasing,
  supplier messages, printing and flashing are outside the current authorisation.

## Checks to run

```sh
python3 scripts/verify_seed.py --manifest provenance/seed-manifest.json --repo .
pnpm circuit:check && pnpm a5:check
python3 scripts/a7_dimension_study.py --check
python3 scripts/a7_electronics.py generate --check
python3 -m unittest scripts/tests/test_a7_r1_study.py
python3 scripts/a7_schematic_check.py --out <empty dir outside the repo>   # needs Docker
python3 -m unittest discover -s scripts/tests -p 'test_native_*.py'
pnpm build && pnpm check && pnpm check:site && pnpm test:browser
```
