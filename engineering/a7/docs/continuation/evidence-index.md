# A7 evidence index

Every evidence set the A7 work relies on, sorted by what kind of evidence it is. The four classes are kept
apart on purpose: an A5 historical record is not an A7 result, held A6 work is not A7 progress, and no
digital result stands in for physical qualification.

Last synchronised with `main` at `5f6865b` (2026-11-08). Rows marked *not on main* describe open PRs and are
not integrated results.

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
| PJ-324M owner bundle | `.claude/skills/component-a7-pj-324m/` | R1 | facts `UNVERIFIED` / `UNSOURCED` with values kept; axis height `INFERRED`; pin functions inferred |
| PCM13SMTR owner bundle | `.claude/skills/component-a7-pcm13smtr/` | R1 | per-position table from mirror; JLC stock 0 (2026-11-08) |
| Catalog lines | `line-a7-pj-324m`, `line-a7-pcm13smtr` | R1 | outside the A5 reconciliation; published at `/docs/components/records/a7-pj-324m/` and `/docs/components/records/a7-pcm13smtr/` |
| Dimension study | `engineering/a7/study/parameters.json` (authored), `results.json`, `report.md` (generated) | R1 | paper study: 3HP feasible on paper across X; 2HP unresolved, not infeasible; thread engagement unresolved without a rear pocket. `python3 scripts/a7_dimension_study.py --check` |
| PET FPC capture | `engineering/a7/pet-fpc.md` | R1 | JLC public capability statements only; questions not sent |
| Open questions | `engineering/a7/open-questions.md` | R1 | Q0–Q12 |
| Controller schematic | `engineering/a7/electronics/` (derived by `scripts/a7_electronics.py generate`; `--check` keeps it current) | R4 #19 (PR #24) | `SCHEMATIC_REVIEWED`: J1 / J2 PJ-324M and SW1 PCM13SMTR replaced, nothing else changed. PJ-324M pin functions INFERRED, terminal positions MIRROR, hole sizes ASSUMED; PCM13SMTR land pattern MIRROR, body centring ASSUMED (`footprints/footprint_sources.json`) |
| Schematic verification | `engineering/a7/verification/schematic/` (`scripts/a7_schematic_check.py`) | R4 | fresh KiCad 10.0.8: ERC 0, schematic-to-PCB parity 0 against an unrouted staging board outside the repo, 51 behavioural assertions pass, delta 12 observed / 12 authorised. Staging-board DRC is not a board result |
| Native gate profile | `engineering/a7/verification/native_gate.json`, `.lock.json` | R3 #18 | `candidate: null`, gate stops `NO_CANDIDATE`; no A7 board result exists |
| Gate fixtures | `scripts/tests/fixtures/native/` | R3 | routed fixtures prove the gate detects faults (`INFRASTRUCTURE_PASS` at best); not an A7 board result |
| Interface roles | `engineering/a7/verification/interface_roles/` | R3, filled by R4 | A5 reference roles; A7 jack / switch roles reviewed for the schematic phase |
| Authorized delta | `engineering/a7/verification/authorized_delta.json` | R3, filled by R4 | reviewed `component_replaced` entries for J1 / J2 / SW1; lists the open physical gates |

### In flight (not on main)

A7 board placement and routing (R4): placement of all 64 parts done locally against the R2 envelopes, autorouting in progress, no PR yet. Nothing of it is on `main`.

| Evidence | PR | State when last checked |
|---|---|---|
| A7 mechanical model and artwork, 2HP / 3HP evaluation | [#25](https://github.com/Takazudo/zudo-led-block/pull/25) (R2) | draft; head includes the jack-orientation and switch-to-jack-gap correction; not merged |

## 4. Outstanding physical qualification

Nothing below has a result. Each needs a physical part, a prototype or a supplier answer.

| Item | Tracked in |
|---|---|
| Harness routing, IDC / strain-relief dimensions, tolerances, PETG fit, measured 30 mm installed depth | #8 |
| Power, CV, firmware, optical, thermal and load qualification; manufacturing files | #10 |
| WS2812B-2020-V6 T1L timing against datasheet V1.4 | #13 |
| PJ-324M pin functions (TS / TRS continuity), axis height, nut fit, lead trim | Q1, Q2, Q4, Q6 |
| PMMA thickness / hole tolerance, rear pocket appearance and strength, clamp load | Q7, Q8, Q9 |
| Transparent PET FPC reflow, continuous temperature, stiffener, clarity after assembly | Q11 |
