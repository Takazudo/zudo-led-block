# A7 evidence index

Every evidence set the A7 work relies on, sorted by what kind of evidence it is. The four classes are kept
apart on purpose: an A5 historical record is not an A7 result, held A6 work is not A7 progress, and no
digital result stands in for physical qualification.

Last synchronised with `main` at `355999a` (2026-11-08 UTC). At that point every A7 engineering PR named here is merged (#22–#42);
check the open PRs before starting new work.

## 1. A5 historical evidence (immutable)

Recorded when the A5 checkpoint was made (2026-11-06 JST). This repository checks the input hashes; it does not
re-run KiCad or CadQuery for these records.

| Evidence | Path | What it is | Check |
|---|---|---|---|
| Seed manifest | `provenance/seed-manifest.json` | 786 files, SHA-256 per file | `python3 scripts/verify_seed.py --manifest provenance/seed-manifest.json --repo .` |
| A5 status | `engineering/a5/integration/a5_status.json` | per-discipline status; controller unrouted (130 unconnected) | `pnpm a5:check` |
| Native schematics / netlists | `engineering/a5/integration/native_schematic/` | KiCad 10.0.8 netlists, the A7 reference netlist | `check_schematic_interfaces.py --output <outside repo>` |
| Harness contract | `engineering/a5/integration/harness_contract_A5.md` | connector pinouts and cables | read-only |
| Mechanical model | `engineering/a5/mechanical/geometry.json` | A5 2HP / 3HP CAD inputs, Z datum = PMMA rear | read-only |
| Front artwork | `engineering/a5/front_panel/` | A4 frosted / clear-lettering design, mirrored rear engraving | read-only |
| Firmware | `engineering/a5/firmware/` | STM32G031 source, host tests, release records | CI firmware jobs (copy before `make_release.py`) |
| BOM | `engineering/a5/procurement_*.json` | 30 types / 81 pieces, prices dated 2026-11-06 | `python3 engineering/a5/build_procurement_rows.py --check` |
| Component catalog | `.claude/skills/component-*/` (30 A5 bundles), `provenance/a5-catalog/` | A5 identities reconciled 30 / 71 / 81 (PR #21); pin maps are historical netlist projections, placements `NEEDS BENCH` | `python3 scripts/a5_catalog.py check`, `pnpm circuit:check` |

## 2. A6 held work (not integrated)

| Evidence | Where | Status |
|---|---|---|
| A6 controller board, gate and routing attempts | branch `claude/project-thread-391rx3` @ `7e96380`, draft PR #14, issue #7 | Held. Placed, unrouted, 125 unconnected; `a6-native` gate fails by design. Routing records `engineering/a6/verification/routing_attempts.json` and `routing_status.md` exist **only on that branch** |
| Verification helpers ported from A6 | `scripts/native_gate/PROVENANCE.md` | merged with R3 (PR #22) with provenance; the A6 scaffold itself was not merged |

## 3. New A7 evidence (digital, on `main`)

| Evidence | Path | Owner | Class of result |
|---|---|---|---|
| Source inventory with hashes | `engineering/a7/evidence/sources.json` | R1 #16 | every inspected source; SOFNG / C&K documents are `MANUFACTURER_MIRROR` (LCSC-hosted) |
| PJ-324M owner bundle | `.claude/skills/component-a7-pj-324m/` | R1, W2 | since 2026-11-11 identity, body/barrel/thread/bore and contact rating are primary PASS from the SOFNG-hosted drawing; board-layout/force/soldering facts stay `UNVERIFIED` / `UNSOURCED` (mirror only); axis height `INFERRED`; pin functions inferred |
| PCM13SMTR owner bundle | `.claude/skills/component-a7-pcm13smtr/` | R1 | per-position table from mirror; JLC stock 0 (2026-11-08) |
| Catalog lines | `line-a7-pj-324m`, `line-a7-pcm13smtr` | R1 | outside the A5 reconciliation; published at `/docs/components/records/a7-pj-324m/` and `/docs/components/records/a7-pcm13smtr/` |
| Dimension study | `engineering/a7/study/parameters.json` (authored), `results.json`, `report.md` (generated) | R1 | paper study: 3HP feasible on paper across X; 2HP unresolved, not infeasible; thread engagement unresolved without a rear pocket. `python3 scripts/a7_dimension_study.py --check` |
| PET FPC capture | `engineering/a7/pet-fpc.md` | R1 | JLC public capability statements only; questions 1–9 drafted, not sent (8 and 9 are Q11e / Q11f). The old supply-drop estimate is marked superseded by the PR #42 upper bound |
| Open questions | `engineering/a7/open-questions.md` | R1 | Q0–Q12 |
| Controller schematic | `engineering/a7/electronics/` (derived by `scripts/a7_electronics.py generate`; `--check` keeps it current) | R4 #19 (PR #24) | `SCHEMATIC_REVIEWED`: J1 / J2 PJ-324M and SW1 PCM13SMTR replaced, nothing else changed. PJ-324M pin functions INFERRED, terminal positions MIRROR, hole sizes ASSUMED; PCM13SMTR land pattern MIRROR, body centring ASSUMED (`footprints/footprint_sources.json`) |
| Schematic verification | `engineering/a7/verification/schematic/` (`scripts/a7_schematic_check.py`) | R4 | fresh KiCad 10.0.8: ERC 0, schematic-to-PCB parity 0 against an unrouted staging board outside the repo, 51 behavioural assertions pass, delta 12 observed / 12 authorised. Staging-board DRC is not a board result |
| Mechanical layout | `engineering/a7/mechanical/design-inputs.json` (authored); `layout.json`, `layout.md`, `placement-envelopes.json` (generated by `scripts/a7_mechanical_layout.py`, `--check`) | R2 #17 (PR #25, #27) | provisional digital study: 3HP FEASIBLE ON PAPER (default), 2HP UNRESOLVED (−0.33 / −0.15 mm worst corner); break-even values for Q1 / Q6; power cable 57.0 ± 3.0 mm requirement (54–60 mm, ±3 ASSUMED; cite `layout.json` → `power_cable_requirement`, not a fixed number) |
| Mechanical CAD | `engineering/a7/mechanical/build_a7_mechanical.py`, `exports/<width>/` (STEP, GLB, views, `verification.json`) | R2 | CadQuery 2.7.0 solids: pairwise intersections, cable clearances, optical-obstruction check, switch tool access. The ~2 % LED D2 shading figure is a ray-sampled estimate, not an optical result. `python3 -m unittest scripts/tests/test_a7_r2_mechanical.py` |
| Front artwork | `engineering/a7/front_panel/` (`build_a7_front.py`, `geometry.json`, `exports/`) | R2 | switch aperture, MODE and ON / PGM / CV legends removed, IN / THRU added, rear frost mask mirrored, 0.5 mm jack pockets. Not an order file; pocket appearance and strength open (Q8) |
| LED leaf comparison (FR-4 vs clear PET) | `engineering/a7/mechanical/layout.json` → `leaf_comparison`, `layout.md` → *LED leaf*, `exports/3hp_pet/` (STEP, GLB, `verification.json`) | R2 (PR #35, `1b9d02d`) | FR-4 stays default and fallback; PET feasible on paper only on a clear 0.8 mm PC carrier (1.28 mm stack, 8–37× less stiff, worst buckling about 8 N vs FR-4 about 300 N). Carrier and OCA values INFERRED; SH mating force UNSOURCED |
| PET leaf electrical profile and check | `engineering/a7/verification/pet_leaf/` (`profile.json`, `README.md`), `scripts/a7_pet_leaf_check.py` | R4 (PR #42, `355999a`) | runs in every native CI job on a copy of the A5 leaf board. PASS: interface, mechanical, SMD-only, 2-layer track / clearance / via / copper-to-edge. NOT_MET (PET variant only): 1-layer copper (Q11d), coverlay bridges (Q11f); plated vias on 2-layer clear PET unstated (Q11e). Voltage drop is an upper bound, not a layout result. Not a PET approval |
| Native gate profile | `engineering/a7/verification/native_gate.json`, `.lock.json` | R3 #18, R4 #19 | `candidate: a7_controller`; fresh run on the committed board: PASS (ERC 0, parity 0, DRC 0, unconnected 0, refill identical, regeneration preserves the board, every negative control detected). CI runs 42499745759 (`e2a2219`) and 42500103564 (`main`) for revision 1; 42503602665 (`ae5aa3c`) for revision 2, whose summary's `tested_board_sha256` matches the committed board, then 42503992506 (`edf98c2`) and 42504705390 (`8bd064b`) on `main`. The stricter-only custom rule `a7_pth_to_track` (0.35 mm, `controller.kicad_dru`) is proved each run by `control_pth_to_track`. Courtyards are compared at 1 nm (`placement`). Digital only |
| Design-rule delta evidence | `engineering/a7/verification/fab/jlcpcb_capabilities.json`, `native_gate.json` → `design_rule_delta` | R4 | vias 0.5/0.2 mm (was 0.6/0.3) and minimum through-hole diameter 0.2 mm (was 0.3), for the U1 / U5 fan-out; plus the stricter-only PTH-to-track 0.35 mm (`custom_rules`, JLCPCB recommended value). JLCPCB capability page URL, retrieval SHA-256 and quoted rows. Order-time pricing and quote conditions are not checked |
| Independent board review | PR #30 reviews [5818547003](https://github.com/Takazudo/zudo-led-block/pull/30#pullrequestreview-5818547003) (changes requested) and [5818654886](https://github.com/Takazudo/zudo-led-block/pull/30#pullrequestreview-5818654886) (approved), dispositions in `engineering/a7/verification/interface_review.md` | R4 | revision 1 digital board approved with four non-blocking polish items. Revision 2: PR #37 reviews [5818789798](https://github.com/Takazudo/zudo-led-block/pull/37#pullrequestreview-5818789798) (changes requested on `eb5d833`, no gate run on that head) and [5818812844](https://github.com/Takazudo/zudo-led-block/pull/37#pullrequestreview-5818812844) (no blocking findings on `ae5aa3c`). The minor CV_ADC / CV_THRU couplings for the bench are in the `eb5d833` review. Not a physical, fit or manufacturing approval |
| Controller board | `engineering/a7/electronics/controller/controller.kicad_pcb` (authoritative, revision 2, SHA-256 `4453f818…628e`; revision 1 was `ec810aec…74f2`), `placement.json`, `board_placement.json` (derived), `engineering/a7/verification/routing/` (router record) | R4 #19 (PR #30 `eb8adeb`, PR #37 `edf98c2`) | 16.2 × 62.9 mm, 4 layers, 1.6 mm (3HP), In1 solid GND, GND pours on F / In2 / B; seeded by `scripts/a7_board.py` + `scripts/a7_route.py` in empty staging outside the repo. PJ-324M slots and PCM13SMTR body position still ASSUMED. Not released for manufacture |
| Mechanical fit check of the routed board | `engineering/a7/mechanical/inputs/r4-board-placement-routed.json` (copied export), `r4-placement-check.json` (generated) | R2 (PR #33, PR #38 `2a76cae`) | revision 1 (PR #33) and revision 2 (PR #38): outline matches, fixed parts in position, no pad centre or origin in a foreign keep-out, solder face resistors / test pads only. Courtyards, pad extents, heights and copper not checked there |
| Router reproducibility | `scripts/a7_route_check.py`, `engineering/a7/verification/routing/README.md`, `scripts/requirements-router.txt` | R4 (PR #39, `8bd064b`; first main run 42504705390; hardened in PR #40, `4b00448`) | each native CI run: fresh seed-0 route equals `route_proposal_seed0.json` byte for byte, and the board's tracks and vias equal it at 1 nm; failed nets or empty copper on either side fail. The `a7-controller-review-aid-NOT-A-RELEASE` artifact (Gerber, drill, positions) is a review aid, not a release output |
| Gate fixtures | `scripts/tests/fixtures/native/` | R3 | routed fixtures prove the gate detects faults (`INFRASTRUCTURE_PASS` at best); not an A7 board result |
| Interface roles | `engineering/a7/verification/interface_roles/` | R3, filled by R4 | A5 reference roles; A7 jack / switch roles reviewed for the schematic phase |
| Authorized delta | `engineering/a7/verification/authorized_delta.json` | R3, filled by R4 | reviewed `component_replaced` entries for J1 / J2 / SW1; lists the open physical gates |

## 2026-11-09 preparation (not a release; on main via PR #44)

- `procurement/assembly-manifest.json`: generated current controller plus two FR-4 leaves and adapter; external hardware/cables/fixture candidates. Engineering only, not supplier upload.
- `fixture/`: exact INGUN receipts and current B-side pad map; generated carrier-only STEP/SVG. Full registration/support/stop and tolerance qualification BLOCKED.
- `qualification/`: blank Workflow F procedures, unsent supplier questions, revision-bound BLOCKED readiness. Report validation is separate from order/release eligibility.
- Native CI evidence retention (2026-11-11): `native-infrastructure-evidence` also keeps the A7 candidate `a7-gate/plan.json`, `evidence/a7_controller/board_facts.json` and `board_geometry.json`. `scripts/a7_native_artifact.py` classifies the staged set in CI (`native-receipt/a7-candidate-evidence.json`) and a downloaded ZIP as VALID_PASS / VALID_FAILURE_EVIDENCE / INCOMPLETE / REJECTED against the summary hashes, the authoritative PCB, the pinned image and the expected revision/run/attempt. Artifacts before this change (e.g. run 42596523199) are INCOMPLETE. A valid record is digital evidence only; it does not set `fresh_native_verified` or complete the fixture.
- Native fixture geometry (2026-11-11, PR #46): the A7 native gate also exports `evidence/a7_controller/fixture_geometry.json` (pad shape/size/copper bbox/rotation/enabled layers/net; footprint origin/side/courtyard and outline boxes; units, axes and back-side conventions). `fixture/native-geometry.json` records it from the VALID_PASS artifact of run 43077448786 (ZIP SHA-256 `db6d6fe1…74c4`) after checking it against the canonical placement; `scripts/a7_fixture_geometry.py --check` runs in CI. The fixture manifest uses it to confirm the five probe pads and, since W5 (2026-11-11), to derive the whole carrier design (through-cuts, 0.27 mm INGUN-derived minimum wall, datums, keying, clamp points, registration allocation closed by acceptance measurements). Body heights and solder envelopes are not native facts; the through-cuts remove the carrier's dependence on them. `fresh_native_verified` stays false on the unsourced J5 tail and `digital_fixture_complete` on README criteria 1, 3, 4 and 5.
- `docs/continuation/order-preparation-checkpoint.md`: working state, access/verification blockers and proposed child tracking. No physical results.
- Component owner bundles: acquired PCM/ST/TDK/Molex primary documents and PJ-324M supplier CAD discrepancy. Original R1 table below/above remains a dated history, not current acquisition status.
- Temperature and pass-criteria evidence (2026-11-11, W7): operating and storage temperature facts added to the TPS2552, SN74LVC2T45, OPA197, TLV9001, TLV755P, AP63205, three Samsung X5R MLCC, WS2812B-2020, SPM4020T, STM32G031, SM04B and PJ-324M bundles, plus a storage fact for BAS70 (its junction-temperature fact already existed). The lowest sourced operating upper limit is +85 C, shared by WS2812B-2020 (Topt), AP63205 and SN74LVC2T45 (TA), STM32G031 (code 6), PCM13SMTR, SM04B and the X5R characteristic span; PJ-324M prints only storage -25..+75 C with operating blank. No temperature fact: 530470310, BOOMELE C5665 and PJ-3582-B; 1MS3T1B1M2QES-5 has only an UNSOURCED mirror fact (-40..85 C). TI served new bytes for tlv755p.pdf (43ff53fb..., same SBVS320D revision), recorded as a second observation; INGUN now serves different GKS-050 probe sheet bytes (6534467c..., PDF CreationDate 2026-11-09, same 11/26_GB values), with the earlier hash kept in `fixture/sources.json` observations.
- CV_BUF bound survey (2026-11-11, W7): OPA197 output can approach each rail to 25 mV (no load, 25 C, `fact-opa197idbvr-output-swing`); that is not a guarantee it never exceeds a rail, so CV_BUF bounded by +12V_PROT / -12V_PROT is an engineering inference. The rail upper limit comes from the rack; Doepfer's A-100 technical page (https://doepfer.de/a100_man/a100t_e.htm, HTML SHA-256 fe61a443b436ea7181c48d502a6f03e41b7cf1b3d2b59a2f1bb9732fcb4b1ea7, Last-Modified 2019-07-01, ecosystem reference, not a limit) gives only nominal +12 V / -12 V with no tolerance or maximum. The D3/U7 current split is in neither datasheet (BAS70 VF 410 mV max at 1 mA, 25 C only; TLV9001 only requires inputs more than 0.5 V beyond a rail to be limited to 10 mA); it does not matter while the total R7 current is below 10 mA. The +/-20 V figure is a design assumption, not a sourced rail limit.
- Molex 530470310 J5 tail (2026-11-12): the owner downloaded the sales drawing (SHA-256 76d2a581..., identical to the 2026-11-09 record); SECTION X-X gives the tail 2.3 +/-0.5 mm below the housing seating face (`fact-530470310-tail-length`). Protrusion below the A7 controller B face is a calculation, not a sourced value: 2.3 - 1.6 = 0.7 mm nominal (0.2 to 1.2 mm with the tail tolerance), assuming flush seating and an exactly 1.6 mm board, whose thickness tolerance is not sourced. `fixture/manifest.json` and `scripts/a7_fixture_relief.py` still mark the J5 tail UNKNOWN (so `fresh_native_verified` stays false) until the fixture thread consumes this fact in its own PR.
- Not reachable from the cloud VM on 2026-11-11 and no desktop browser connected: Nexperia SOD323F packing document (HTTP 403), so the PMEG ,115 packing identity stays UNSOURCED; the SOFNG board-layout page was not retried.

## 4. Outstanding physical qualification

Nothing below has a result. Each needs a physical part, a prototype or a supplier answer.

| Item | Tracked in |
|---|---|
| Harness routing, IDC / strain-relief dimensions, tolerances, PETG fit, measured 30 mm installed depth; the A7 power cable (57 ± 3 mm requirement), adapter boss and M2x18 clamp load | #8 |
| Power, CV, firmware, optical, thermal and load qualification; manufacturing files | #10 |
| WS2812B-2020-V6 T1L timing against datasheet V1.4 | #13 |
| PJ-324M pin functions (TS / TRS continuity), axis height, nut fit, lead trim | Q1, Q2, Q4, Q6 |
| PMMA thickness / hole tolerance, rear pocket appearance and strength, clamp load | Q7, Q8, Q9 |
| Transparent PET FPC reflow, continuous temperature, stiffener, clarity after assembly | Q11 |
| PC carrier lamination with OCA after reflow (supplier and process) | Q11a |
| SH plug unmating pull, pad-to-film and film-to-OCA peel strength | Q11b, #10 |
| PET leaf in the 2HP variant | Q11c |
| PET leaf: 1-layer copper, 2-layer clear PET plated vias, coverlay bridges (PET variant only) | Q11d, Q11e, Q11f |
