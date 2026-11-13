# A7: continue here

Durable hand-off for the A7 structural redesign ([#15](https://github.com/Takazudo/zudo-led-block/issues/15)).
Read this first, then [`evidence-index.md`](evidence-index.md). The Japanese status pages on the docs site
(`doc/src/content/docs/project/a7.mdx`, `next-actions.mdx`) say the same thing for readers.

**A7 is not released for manufacture.** The integrated digital result is on `main`: the reviewed controller schematic,
the routed controller board at revision 2 with SW1 = HX MSK13C02 / C5149819 (board `89310d53…e727`, native gate PASS,
independent layout/electrical re-review with no blocking findings), and a provisional digital mechanical model and front
artwork checked against that board. The first build is two modules (2 controllers, 4 FR-4 LED leaves, 2 power adapters)
on the 3HP working candidate. There is no prototype and no physical measurement. Nothing in A7 is a measured fit, part
approval, fit approval, electrical result or manufacturing approval, and a green CI is none of those either.

## Current pre-order state (2026-11-13)

Each stage below is taken from an existing record; this list does not add a gate or change `--gate`.

1. **Digital implementation: complete.** Schematic, routed board `89310d53…e727` (CI run 43294571723), mechanical model,
   and the fixture's digital criteria 1–4 with fresh native verification (`fixture/manifest.json`). #16–#19 are closed.
2. **Test-prototype route: approved by the owner, now held by its binding.** Approved 2026-11-12 and re-approved for the
   HX version on 2026-11-13 (PR #79, `qualification/approvals/2026-11-13-owner-prototype-route-hx-switch.md`). The approval
   binds the SHA-256 of board, population, schematic, firmware, configuration, mechanical layout, fixture manifest and
   assembly manifest (`qualification/records.json` → `owner_prototype_route.identities`). The sourcing reconciliation (#80)
   changed `procurement/assembly-manifest.json` from `c12c964a…e865` to `ea30c8a7…5755` (sourcing observation fields and the
   supply-blocker text only; no part, quantity, board or placement change), so readiness shows the `owner_prototype_route`
   gate again. The approval record is unchanged; re-approving the new identity set is an owner action.
3. **Panel exports: prepared and verified.** Own repo panels (owner decision `panel-route`). Dated set
   `jlc-package/order/2026-11-13/` exported from `db0ca95` with KiCad 10.0.8: one Gerber zip, BOM and CPL per board type and
   `SHA256SUMS`; `a7_panel.py build` and the single-board export check PASS (`panel-build-summary.json`,
   `single-board-export-summary.json`). Its BOM/CPL equal `jlc-package/panels/` byte for byte.
4. **Order-form review: not done.** From the dated README and `jlc-package/package.json`: placement-preview centroids and
   rotations of controller J1/J2/J5/SW1 and power_adapter J1/J2 (KiCad angles, never checked against JLC's library);
   whether the PCBA quantity counts sheets (2); whether JLC assembles the customer panels (the owner's acceptance in
   `jlc-questions` is not a JLC confirmation); power_adapter base material (FR-4 assumed, not recorded); surface finish;
   and the actual assembly terms (quote, attrition, lead time).
5. **Order: not submitted.** Upload, payment and order are the owner's; the repository has no order record
   (`readiness.json` → `order_submitted: NOT_ESTABLISHED`).
6. **First article and release: open.** PJ-324M terminal 4/5 (pre-order continuity test waived by the owner 2026-11-12,
   `jack-tip-test-waiver`; the waiver does not confirm the pin map), HX MSK13C02 truth table and land fit, fixture
   criterion 5, and the #8/#10/#13 qualification come after the boards exist. A manufacturing release is a separate owner
   approval. `readiness.json` stays BLOCKED because it counts every condition up to that release; it does not mean the
   first prototype boards need all release tests first.

Upload lifecycle: files directly under `jlc-package/` and in `jlc-package/panels/` are generator reference sets and are not
uploaded. The dated `order/<date>/` copy is what the owner uploads for the approved prototype route. Neither is a release.

Sourcing: all 30 fitted identities have dated 2026-11-12 JLC listing observations (`procurement/sourcing-projection.json`):
rendered part pages (10:35–19:56Z) and a later parts-API audit (19:09:52Z), separate reads that disagree on stock for 25
lines. Field meanings, currency and buy quantities are our inference. Lead time, confirmed quote, stock reservation and
assembly acceptance are not obtained for any line. PCM13SMTR (C221842) is retired evidence only.

Optional 2HP, transparent PET and hosting (#11/#12) do not block the FR-4 prototype order.

History: the 2026-11-09 preparation package (E1 board/export binding, E2 exact-part sources, E3 fixture study, at that
date carrier-only, E4 procurement ledger, E5 BLOCKED readiness and blank procedures) is integrated into main through PR #44 (2026-11-11).
Its working record is [`order-preparation-checkpoint.md`](order-preparation-checkpoint.md); integration does not
complete the fixture, any physical gate, order eligibility or a manufacturing release.

2026-11-11 (W3): the 19 physical procedures in `qualification/plan.json` now carry inputs, tools, preconditions,
steps, a per-kind record template and acceptance values that `scripts/a7_readiness.py` checks against their source
(fact, design record or quoted text; assumed and inferred values stay labelled). `readiness.json` splits the
blockers into gates classed CLOUD_DIGITAL / OWNER_DECISION / ACCESS_EVIDENCE_HOLD / PHYSICAL_ONLY, and the generated
site page `/docs/project/order-checklist/` lists what only the owner can do and which gate each item clears. Every
procedure is still NOT_MEASURED and the order gate still fails.

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
| R2 mechanical model and artwork | [#17](https://github.com/Takazudo/zudo-led-block/issues/17) | merged in PR [#25](https://github.com/Takazudo/zudo-led-block/pull/25) (`64bd3b7`), the harness follow-up PR [#27](https://github.com/Takazudo/zudo-led-block/pull/27) (`d27f578`), PR #29, and the placement checks against R4's board PRs #31–#33 (`dd45ed5`) and #38 (`2a76cae`, revision 2), and the PET versus FR-4 leaf comparison PR [#35](https://github.com/Takazudo/zudo-led-block/pull/35) (`1b9d02d`); provisional digital study; issue closed after the digital scope (2HP stays an optional separate decision) | `mechanical/`, `front_panel/`, `scripts/a7_mechanical_layout.py` |
| R3 native verification foundation | [#18](https://github.com/Takazudo/zudo-led-block/issues/18) | merged in PR #22 (`02992fa`), issue closed | `verification/`, `scripts/native_gate/` |
| R4 schematic, placement, routing | [#19](https://github.com/Takazudo/zudo-led-block/issues/19) | schematic merged in PR [#24](https://github.com/Takazudo/zudo-led-block/pull/24) (`5f6865b`); routed board merged in PR [#30](https://github.com/Takazudo/zudo-led-block/pull/30) (`eb8adeb`, revision 1, board `ec810aec…74f2`), revision 2 in PR [#37](https://github.com/Takazudo/zudo-led-block/pull/37) (`edf98c2`, board `4453f818…628e`, gate PASS, re-review with no blocking findings); SW1 part fields in #77 (board `89310d53…e727`); issue closed after the digital scope, physical gates continue in #8/#10/#13 | `electronics/`, `verification/`, `scripts/a7_electronics.py`, `scripts/a7_board.py`, `scripts/a7_route.py` |
| R5 docs, status, continuation | [#20](https://github.com/Takazudo/zudo-led-block/issues/20) | this document; reflects the integrated digital result and the 2026-11-13 pre-order state | `docs/continuation/`, Japanese site pages |
| Sourcing projection | [#80](https://github.com/Takazudo/zudo-led-block/issues/80) | dated observations for all 30 fitted identities | `procurement/sourcing-projection.json`, `scripts/a7_procurement.py` |

The A5 component catalog (30 identities) merged in PR #21 (`20b2f8f`); issue
[#9](https://github.com/Takazudo/zudo-led-block/issues/9) stays open for manufacturer sources that could not be
retrieved.

## Done (digital)

### Board revision history

| Revision | Board SHA-256 | Merged | What changed | Review |
|---|---|---|---|---|
| 1 | `ec810aecd9e67e2806f8886e43f3944bf35c1051dcc4a52f23332216025e74f2` | PR #30, `eb8adeb` | first placement and routing | requested changes on `493155e`, approved on `e2a2219`; four non-blocking polish items left |
| 2 | `4453f818ede1e6d6c56e45ef43aa6faecb90990f3755f82c6d752258cd4d628e` | PR #37, `edf98c2` (head `ae5aa3c`) | the four polish items, PTH-to-track 0.35 mm rule and control, 1 nm courtyard comparison | requested changes on `eb5d833` (no gate run on that head), no blocking findings on `ae5aa3c` |
| 2, SW1 part fields (current) | `89310d539b3c28096775cee821e46c14fdba42a87809c82f1fd7f0751704e727` | #77 | SW1 MPN / LCSC properties changed to HX MSK13C02 / C5149819; footprint, copper and placement unchanged | board gate PASS in CI run 43294571723 on `8e71317`; independent review on the #77 PR |

- **Current board (revision 2 + SW1 part fields).** `electronics/controller/controller.kicad_pcb` (`89310d53…e727`),
  16.2 × 62.9 mm, 4 layers, 1.6 mm, In1 solid GND. Fresh KiCad 10.0.8 gate PASS on it in CI run 43294571723 (`8e71317`).
  Historical: revision 2 as merged (`4453f818…628e`) passed in run 42503602665 on `ae5aa3c` (main runs 42503992506 on
  `edf98c2` and 42504705390 on `8bd064b`): ERC 0, parity 0, DRC 0, unconnected 0, zone refill identical, regeneration
  preserves the board, every negative control detected.
- **Polish items applied:** C11 1.53 mm from U6.5 (was 5.8); GND vias at U7.2 / C17.2 0.52 / 0.66 mm (was 1.5–2);
  C15 1.8 mm from U4.1 (nearest +5 V cap was C2 at 4.1); CV_FILTER all on F.Cu, nearest same-layer VLED 3.65 mm
  (was about 0.9). Dispositions in `verification/interface_review.md`.
- **Minor couplings from the `eb5d833` re-review (non-blocking, carried over on `ae5aa3c`):** CV_ADC beside SWCLK for 1.0 mm on one layer; CV_THRU on In2 beside
  DATA_L_3V3 and SWDIO. Watch DATA_L coupling in bench CV-noise tests (#10).
- **Rule delta:** vias 0.6/0.3 → 0.5/0.2 mm and the board-wide minimum through-hole diameter 0.3 → 0.2 mm (U1 QFN28 and
  U5 VSSOP-8 fan-out), recorded as `native_gate.json` → `design_rule_delta`, backed by
  `verification/fab/jlcpcb_capabilities.json` (URL, retrieval SHA-256, quoted rows: multilayer min 0.15 hole / 0.25 via,
  preferred min hole 0.2). Since revision 2 also the stricter-only custom rule `a7_pth_to_track` (0.35 mm PTH drill to
  another net's track, JLCPCB recommended; `controller.kicad_dru`), proved each run by `control_pth_to_track`; the
  board's closest is 0.386 mm. Track width, clearances, annular ring 0.15 mm and layer count are A5's.
- **Router reproducibility in CI (PR #39):** every native CI job runs `scripts/a7_route_check.py`. It rebuilds the
  staging board from the committed placement, re-runs `a7_route.py --seed 0` (numpy pinned with hashes in
  `scripts/requirements-router.txt`), requires a byte-identical `verification/routing/route_proposal_seed0.json`,
  and requires the authoritative board's tracks and vias to equal the proposal at 1 nm. The same PR makes the
  `rule_squeeze` control require its rule name and pad in the native report. The `--review-aid` Gerber / drill /
  position artifact is **not a release output** and must not be ordered from. First passed on main in run 42504705390 (`8bd064b`). PR #40 (`4b00448`) hardens it: a proposal with failed nets,
  or a board or proposal with no tracks or vias, now fails (no empty-equals-empty pass); the summary is kept in the
  `native-infrastructure-evidence` artifact; the review aid drops the Gerber job file so it cannot be bulk-uploaded.
- **R2 fit checks:** `mechanical/r4-placement-check.json` compares R4's routed export with the envelopes (revision 1
  in PR #33, revision 2 in PR #38): outline matches, fixed parts (J1 / J2 axis and all pins, J3, J5, SW1) in
  position, no origin or pad centre in a foreign keep-out, solder face only resistors and test pads (≤ 0.6 mm).
  Courtyards, pad extents, heights and copper are outside that check (they are R4's DRC). The board is 1.6 mm, i.e.
  the 3HP working candidate; 2HP would need a 0.8 mm board and new routing.
- **LED leaf comparison (PR #35, `1b9d02d`):** FR-4 stays the default and fallback. A clear PET leaf is feasible on
  paper only as two 0.14 mm films on OCA either side of a clear 0.8 mm PC carrier (1.28 mm, FR-4 1.30; positions move
  0.01 mm). It is 8–37× less stiff (worst-case buckling about 8 N under the SH push, FR-4 about 300 N); the film alone
  buckles at about 0.07 N. New open items Q11a (carrier lamination supplier), Q11b (unmating pull and peel), Q11c
  (2HP with PET). `mechanical/README.md`, `layout.md`, `layout.json` → `leaf_comparison`, `exports/3hp_pet/`.
- **PET leaf electrical profile and check (PR #42, `355999a`):** `verification/pet_leaf/` (`profile.json`, README) and
  `scripts/a7_pet_leaf_check.py`, run in every native CI job against a copy of the A5 leaf board (`6244280c…`).
  PASS: interface (J3 and both SH4 harnesses reach both four-pixel chains), mechanical (R2's PET export), all pads
  SMD on F.Cu, and on 2-layer film rules the tracks, clearances, 0.6/0.3 vias and 0.3 mm copper-to-edge. NOT_MET:
  1-layer copper (all five data nets use B.Cu and 11 vias, Q11d) and coverlay bridges (0.2 mm against JLC's 0.5 mm
  minimum, Q11f). Whether JLC plates vias on 2-layer clear PET is not stated (Q11e); a 2-layer stack is 1.48 mm with
  about 0.06 mm per side in the cap slot (R2 to re-check). The VLED + GND drop is an upper bound only (about 335 /
  224 / 115 mV at 12 / 18 / 35 µm copper with the TPS2552 worst-case 0.435 A in series through every segment).
  Q11d–Q11f block the PET variant only. `CHECKED` is not a PET approval; FR-4 stays the default.
- **R2 mechanical (PR #25, #27, #29):** 3HP FEASIBLE ON PAPER and the default; 2HP open (worst corner −0.33 / −0.15 mm).
  Jacks at Y 84.3 / 99.3 in 0.5 mm rear pockets; A5 adapter 2.0 mm forward with an M2x18 top-cap screw; power cable
  requirement from `mechanical/layout.json` → `power_cable_requirement` (currently 57 ± 3 mm, ±3 ASSUMED).
- **R4 schematic (PR #24):** J1, J2 and SW1 replaced; every other part and net unchanged from A5.

## Next actions, in order

The stage list at the top is the current state. `qualification/readiness.json` reports BLOCKED. Any later board change
re-runs the gate, independent review and R2 fit check.

1. **Owner actions before ordering:** re-approve the prototype route for the current identity set (stage 2), review the
   JLC order form (stage 4), then order. Choose the fabricator for the four fixture FR-4 plates (the proposed fixture
   hardware is already accepted).
2. **First-article and physical gates:** PJ-324M pin functions by TS / TRS continuity (Q2, waived before ordering, done on
   the assembled boards), slot sizes (Q3, the board still uses ASSUMED 1.6 × 0.8 mm slots), axis height (Q1, INFERRED),
   HX MSK13C02 truth table and land fit (Q10, switch-fit), fixture criterion 5. The optional 2HP and PET decisions do not
   block FR-4 preparation.
3. **External evidence** listed in `../../open-questions.md` (Q0–Q11 and Q11a–Q11f; Q12 is decided). The JLC PET questions 1–9 remain
   drafted (`../../pet-fpc.md`; 8 and 9 are Q11e and Q11f). Other questions are now drafted in
   `../../qualification/supplier-questions.md`; all are **not sent**. Sending supplier messages is
   outside the current authorisation.
4. **Physical qualification** with [#8](https://github.com/Takazudo/zudo-led-block/issues/8) (harness, power cable,
   fit, PETG), [#10](https://github.com/Takazudo/zudo-led-block/issues/10) (power / CV / firmware / optical / thermal /
   load, manufacturing files, CV noise with DATA_L coupling, and if PET is pursued the SH mating / unmating force
   and lit appearance) and [#13](https://github.com/Takazudo/zudo-led-block/issues/13) (WS2812B T1L timing).
5. **Manufacturing release** is a separate owner decision after qualification and outside the current authorisation.

## Blockers

| Blocker | Blocks | Needs | Tracked in |
|---|---|---|---|
| Prototype-route approval bound to the old assembly-manifest digest | readiness `owner_prototype_route` | owner re-approval of the current identities | records.json |
| Order-form checks not done (centroids / rotations, PCBA sheet unit, customer-panel acceptance, base material, finish, assembly terms) | ordering | owner review on the JLC form | `jlc-package/order/2026-11-13/README.md` |
| No manufacturing release package or approval | manufacturing | qualification, then an owner release decision (out of scope) | #10 |
| Board is 1.6 mm (3HP only) | an optional 2HP build | owner 2HP decision, then a 0.8 mm board and new routing | optional |
| 2HP unresolved at the worst corner | optional width choice | Q1 axis height or Q6 trim evidence (break-even values in `mechanical/layout.md`) | optional |
| A7 power cable 57 ± 3 mm (±3 ASSUMED), not routed or measured | power harness | cable sourcing and measurement | #8 |
| Adapter boss and M2x18 clamp load not analysed | adapter retention | analysis and printed part | #8 |
| PJ-324M axis height only inferred (≈3.0, band 2.6–3.4) | 2HP lead-side margin | dimensioned drawing, 3D model or measured part | Q1 |
| PJ-324M pin functions inferred | CV_THRU vs GND mapping | first-article continuity test with TS and TRS plugs (pre-order test waived 2026-11-12; the waiver is not a confirmation) | Q2, #10 |
| PJ-324M hole sizes not on the drawing | footprint (routed board uses ASSUMED slots) | supplier CAD inspected; maker slot/lead tolerances or measured part still needed | Q3 |
| Nut supply and fit unknown | front retention | supplier answer or part | Q4 |
| HX MSK13C02 truth table and land / peg fit unconfirmed (dated JLC stock 4561 on 2026-11-12, not reserved) | side switch fit | first-article switch-fit check | Q10 |
| SOFNG primary drawing unavailable; PCM primary recovered | unsupported jack drawing facts | exact SOFNG document or measured evidence | Q0 |
| PET FPC process answers missing | optional transparent LED leaf | JLC written answers (questions not sent) | Q11 |
| No supplier for laminating the PC carrier with OCA after reflow | building a PET leaf at all | supplier and process | Q11a |
| SH unmating pull and pad / OCA peel strength unsourced | PET leaf connector retention | force data and a physical test | Q11b, #10 |
| 1-layer PET film cannot carry the A5 leaf copper | PET variant only | a new single-layer leaf layout or the 2-layer film | Q11d |
| 2-layer clear PET plated vias not stated by JLC; PTH ring 0.18 mm may apply to vias (A5 vias have 0.15 mm) | PET variant only | JLC answer (not sent) | Q11e |
| Coverlay bridges 0.2 mm, JLC minimum 0.5 mm | PET variant only (SMT bridging risk) | JLC answer on bridge-less openings or a clear solder mask | Q11f |
| PET leaf built for 3HP only | 2HP with PET | 2HP decision first (X stack differs by 0.02 mm, so 3HP carries over) | Q11c |
| No physical prototype | every fit, electrical, optical, thermal result | the ordered prototype boards | #8, #10 |
| Agent-instruction pages on the site | publication scope | owner decision | #12 |

## Rules that do not change

- Never edit, regenerate or reformat `engineering/a5/`. Run
  `python3 scripts/verify_seed.py --manifest provenance/seed-manifest.json --repo .` before and after.
- Never hand-edit generated files: `doc/src/content/docs/components/`, the `scripts/a5_site.py` outputs,
  `engineering/a7/study/results.json` / `report.md`, and electronics paths explicitly classed derived in
  `verification/source_authority.json`. The routed controller PCB is authoritative; normal generation never writes it.
  Electronics README and reviewed records are authored, not generator output.
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

**Browser smoke startup (PR #67).** The docs job's "Framework check-browser" step used to fail about 0.4 s in with
`Error: Chrome page target was not available`, because `@takazudo/zudo-circuit-doc@0.3.0` `lib/browser-smoke/chrome.js`
read Chrome's page target once. PR #67 installed a pnpm patch (`patches/@takazudo__zudo-circuit-doc@0.3.0.patch`,
registered in `pnpm-workspace.yaml` → `patchedDependencies`) that polls `/json/list` for up to 10 s and fails at once if
Chrome exits. It is not a retry wrapper or `continue-on-error`. Maintenance: the patch is pinned to 0.3.0; when the
dependency is bumped, check that the patch still applies and drop it once an upstream release carries the fix
(`ZUDO_DEPS_PINS.md`).

ローカルKiCadへ進む際は [固定入力と実行手順](local-kicad-handoff.md) を使用してください。Cloudの成果と未取得native/物理証跡を分離しています。
