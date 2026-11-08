# A7: continue here

Durable hand-off for the A7 structural redesign ([#15](https://github.com/Takazudo/zudo-led-block/issues/15)).
Read this first, then [`evidence-index.md`](evidence-index.md). The Japanese status pages on the docs site
(`doc/src/content/docs/project/a7.mdx`, `next-actions.mdx`) say the same thing for readers.

**A7 is a design study. It is not released for manufacture.** The A7 controller schematic is on `main`
(reviewed, schematic phase only). There is no A7 board, mechanical model or artwork on `main` yet. Nothing in A7 is a part approval, fit approval, electrical result or
manufacturing approval, and a green CI is none of those either.

Last synchronised with `main` at `5f6865b` (2026-11-08).

## What A7 is

Accepted direction from the owner (2026-11-08):

- Front: the existing illuminated artwork on clear 2 mm cast PMMA (128.5 mm high), plus two front-facing
  3.5 mm CV jacks, IN and THRU. The front switch aperture, MODE label and ON / PGM / CV legends go away;
  the rear-frosted / front-smooth look and the illuminated lettering stay.
- Mode selection moves to a small PCB-side setting switch, used before installation or with the module out.
- Right-angle threaded jack SOFNG PJ-324M (LCSC C22355739), mono CV only, with the controller PCB
  perpendicular to the front so enclosure depth becomes routing area.
- Width: 2HP (9.8 mm) preferred, 3HP (14.9 mm) accepted fallback. Coordinator working decision: 3HP is the
  working candidate for R2; the 2HP 0.6 mm-offset arrangement stays parameterised and open.
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
| A7 | `engineering/a7/` | Study, verification foundation and reviewed controller schematic merged; mechanical model in draft PR #25; board placement done locally, autorouting in progress, no PR yet | everything new |

## Task map (epic #15)

| Task | Issue | State on `main` | Where |
|---|---|---|---|
| R1 parts and dimension study | [#16](https://github.com/Takazudo/zudo-led-block/issues/16) | merged in PR #23 (`54bda11`), issue closed | `study/`, `evidence/`, `pet-fpc.md`, `open-questions.md`, `.claude/skills/component-a7-*` |
| R2 mechanical model and artwork | [#17](https://github.com/Takazudo/zudo-led-block/issues/17) | **not merged**; draft PR [#25](https://github.com/Takazudo/zudo-led-block/pull/25) | will add `mechanical/`, `front_panel/` |
| R3 native verification foundation | [#18](https://github.com/Takazudo/zudo-led-block/issues/18) | merged in PR #22 (`02992fa`), issue closed | `verification/`, `scripts/native_gate/` |
| R4 schematic, placement, routing | [#19](https://github.com/Takazudo/zudo-led-block/issues/19) | schematic phase merged in PR [#24](https://github.com/Takazudo/zudo-led-block/pull/24) (`5f6865b`, `SCHEMATIC_REVIEWED`); **board not placed or routed**, issue open | `electronics/`, `verification/schematic/`, `scripts/a7_electronics.py`, `scripts/a7_schematic_check.py` |
| R5 docs, status, continuation | [#20](https://github.com/Takazudo/zudo-led-block/issues/20) | this document; updated as R2 / R4 merge | `docs/continuation/`, Japanese site pages |

The A5 component catalog (30 identities) merged in PR #21 (`20b2f8f`); issue
[#9](https://github.com/Takazudo/zudo-led-block/issues/9) stays open for manufacturer sources that could not be
retrieved.

## Next actions, in order

1. **R4 schematic (PR #24): done.** J1, J2 and SW1 replaced, every other part and net unchanged from A5;
   ERC 0, parity 0, 51 behavioural assertions pass, authorised delta covers all 12 observed deltas. The native
   gate profile stays `candidate: null` until a board lands with it.
2. **R2 mechanical (PR #25, draft).** Finish review of the jack-orientation and switch-to-jack-gap correction, build the 3HP
   model, keep 2HP 0.6 mm offset parameterised. Decide the rear PMMA pocket (Q8) for thread engagement.
3. **R4 placement and routing.** Place on the perpendicular outline from R2, route, and make the board the
   gate `candidate` in the same PR. The gate must pass with no relaxed rules, exclusions or success wrappers.
4. **R5 re-sync** after each of those merges: this file, `evidence-index.md`, the A7 status page, the
   decision and blocker registers, and the A7 BOM delta.
5. **External evidence** listed in `../../open-questions.md` (Q0–Q11; Q12 is decided): maker-hosted drawings, axis height,
   pin functions, hole sizes, nut fit, lead trim, PMMA tolerances, switch supply, JLC PET answers.
   Only the JLC PET questions are drafted (`../../pet-fpc.md`), and they are **not sent**; the others are not
   drafted. Sending supplier messages is outside the current authorisation.
6. **Physical qualification** stays with [#8](https://github.com/Takazudo/zudo-led-block/issues/8)
   (harness, fit, PETG) and [#10](https://github.com/Takazudo/zudo-led-block/issues/10) (power / CV / firmware /
   optical / thermal / load), and [#13](https://github.com/Takazudo/zudo-led-block/issues/13) (WS2812B T1L timing
   against the datasheet). None of these can be closed digitally.

## Blockers

| Blocker | Blocks | Needs | Tracked in |
|---|---|---|---|
| No A7 board on `main` (placement local only, not routed) | A7 gate, A7 BOM, placement export | R2 merge, then the R4 routing PR | #19 |
| Mechanical model not on `main` | board outline, jack/switch positions, depth check | PR #25 corrections and merge | #17 |
| PJ-324M axis height only inferred (≈3.0, band 2.6–3.4) | 2HP lead-side margin | dimensioned drawing, 3D model or measured part | Q1 |
| PJ-324M pin functions inferred | CV_THRU vs GND mapping | bench continuity test with TS and TRS plugs | Q2, #10 |
| PJ-324M hole sizes not on the drawing | footprint | JLC/EasyEDA footprint inspection or maker answer | Q3 |
| Nut supply and fit unknown | front retention | supplier answer or part | Q4 |
| PCM13SMTR JLC stock 0 | side switch sourcing | stock, or a printed per-position table / bench check for an alternate | Q10 |
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
