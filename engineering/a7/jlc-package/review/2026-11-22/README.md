# A7 prototype-order review set, 2 modules (2026-11-22) — REVIEW_ONLY / NOT FOR ORDER

> **Do not upload or order from these files yet.** This set is bound to the current 0.8 mm FR-4 boards (PR #88) and
> is for review. It becomes an upload set only after the owner approves the prototype route for exactly the identity
> set below and the order-form checks in section 2 are done; that approval is then recorded in
> `engineering/a7/qualification/records.json` and the status in `../../package-sets.json` changes. It is never a
> manufacturing release. File names keep the tool's `DRYRUN` suffix. No order has been placed.

Tracked in #92 (T4) under epic #15. The superseded set `../../order/2026-11-13/` (1.6 mm controller / 0.6 mm leaf) is
history and is not an upload choice.

## Files

| Board | Gerber + drill (panel) | BOM | CPL | Boards per sheet |
|---|---|---|---|---:|
| controller | `controller/controller-panel-gerbers-DRYRUN.zip` | `controller/controller-panel_BOM_DRYRUN.csv` | `controller/controller-panel_CPL_DRYRUN.csv` | 1 |
| led_leaf | `led_leaf/led_leaf-panel-gerbers-DRYRUN.zip` | `led_leaf/led_leaf-panel_BOM_DRYRUN.csv` | `led_leaf/led_leaf-panel_CPL_DRYRUN.csv` | 2 |
| power_adapter | `power_adapter/power_adapter-panel-gerbers-DRYRUN.zip` | `power_adapter/power_adapter-panel_BOM_DRYRUN.csv` | `power_adapter/power_adapter-panel_CPL_DRYRUN.csv` | 1 |

Also: `identities.json` (frozen identity set), `panel-build-summary.json` and `single-board-export-summary.json`
(pinned-image build/export results), `gerber-comparison-vs-ci.json`, `order-form-checklist.json` (snapshot of
`../../order-form-checklist.json`), `images/*.png` (top/bottom panel renders) and `SHA256SUMS` (every file except this
README). Verify with `python3 scripts/a7_review_set.py verify engineering/a7/jlc-package/review/2026-11-22`.

## Frozen identities

Frozen from commit `86470126aa569cce026cd740c95a63181a921de3` (branch `claude/project-thread-y1zl4n`), tool image
`kicad/kicad:10.0.8@sha256:3f4a01786dfbe803a65f345c3342b765db9add913f5e9448f8356793714ddc34`.

| Identity | Path | SHA-256 |
|---|---|---|
| Controller board | `engineering/a7/electronics/controller/controller.kicad_pcb` | `d83691d6590e013b2a66957b61d76ba2f68bedaaec04789326e1215b2d1bdb2b` |
| Controller schematic | `engineering/a7/electronics/controller/controller.kicad_sch` | `b027715b278a17d9af9c5791f107cbaf07ee218647601622164d33b344015e1d` |
| Controller placement | `engineering/a7/electronics/controller/board_placement.json` | `2d32b2ab76735dbf4ff7f2c959de4398b8215983be9a4fd33fde50c7015212f5` |
| LED leaf board | `engineering/a7/electronics/led_leaf/led_leaf.kicad_pcb` | `bcf2e35d767221f5a9db0cd16769a2e503a672f522fd4f32f78012cdeb494cf9` |
| LED leaf schematic | `engineering/a7/electronics/led_leaf/led_leaf.kicad_sch` | `b3eaaf84ab1bc3a13c1dd1600cb6f5dca5ea61c403d0af4ea7c5b664b40c6599` |
| Power adapter board (A5, unchanged) | `engineering/a5/electronics/native/power_adapter/power_adapter.kicad_pcb` | `b0f071f2730afdfd3d29de2176b1cce5f90b0c0726d14fd15501e27f90d95187` |
| Optical fabrication spec | `engineering/a7/verification/fab/optical-fr4.json` | `d974daffc20c4aabaa1d754f4b7393315388246b93433bb77750a4100237c6e5` |
| Firmware image | `engineering/a5/firmware/dist/light_block_A5.bin` | `0446cb0acfa7efe86a5f6c02beb7afa482daa419ecfce204fe9169487599765e` |
| Firmware sources | `engineering/a5/firmware/dist/source_files.sha256` | `61155c23cc8f9c05f8d5712ecd8f009673c1929a34b8437b9869c202deb85c46` |
| Configuration | `engineering/a5/firmware/include/lb_config.h` | `195092c88e1b9270bae22d27f4a08f4a606f9be77008f3011f06d7a975b0f6a7` |
| Mechanical layout | `engineering/a7/mechanical/layout.json` | `8b24ec83fd805c4efcaba92f885e49531826f8945063b74fd5019bc1221e040e` |
| Fixture manifest | `engineering/a7/fixture/manifest.json` | `5d73050918e3d32bdf06cfadd687e126f0e035c83a155d1bb74bf5248404fd85` |
| Assembly manifest | `engineering/a7/procurement/assembly-manifest.json` | `b94ac5981de7eed846bf0c9eb0dae61c5cd1ea25d1fe4defb3b1369aada6c02d` |

## What was checked, and its limits

- `scripts/a7_panel.py build` (pinned KiCad 10.0.8, no network, read-only repo) PASS for all three panels: every
  footprint, pad, track, via, zone and drawing of each copy equals the frozen board apart from the move; the outline
  of each board region equals the frozen outline (XOR area 0); drills and slots equal the moved board drills plus
  mouse-bite and tooling holes (controller 158 incl. 10 slots, leaf 61, adapter 48); panel DRC adds nothing except the
  recorded adapter waiver (`npth_inside_courtyard` 22); panel CPL equals KiCad's own position export (MATCH).
- Layer sets: controller 4 copper (F, In1, In2, B), both masks, both pastes, both silks, Edge.Cuts, PTH and NPTH
  drills and the job file (14 files); leaf and adapter 2 copper with the same other layers (12 files each).
- `scripts/a7_jlc_package.py export` (single boards, reference) PASS with CPL vs KiCad MATCH.
- Gerber-to-Gerber: these panel Gerbers equal the CI-built panel artifact of run 44981535275 (head `6f6e8ea`)
  primitive for primitive (`gerber-comparison-vs-ci.json`, gerbonara 1.6.3). That compares two exports of the same
  panels; there is no comparison of panel Gerbers against single-board Gerbers.
- The `images/` renders are inspection aids from the Gerbers (white = mask opening), not DRC or optical results.
- Not checked: JLC's CAM interpretation of the minimal-mask openings, the authenticated placement preview, factory
  DFM, and anything physical.

Panel residual risks (unchanged dispositions from `../../panels/README.md`): tab positions are proposed, not
mechanically reviewed (controller 2 short left tabs + 2 right; leaf 3 per copy, no facing-edge tabs; adapter tab under
J1); mouse-bite nubs of up to about 0.3 mm remain after break-off; 0.8 mm sheets are thinner than the 1.6 mm boards the
tab layout was first drawn for, so support during reflow is a factory question; panels are mostly waste FR-4 to reach
the 70 mm Standard-PCBA minimum. The fixture review (#90) notes that mouse-bite nubs on the controller's x = 16.2 mm
datum edge are outside its registration budget.

## Decision sheet

### 1. Prototype route (owner decision, PCB_ORDER)

Approve, or not, a test-only prototype of exactly the identity set above, 2 modules: 2 controllers, 4 LED leaves,
2 power adapters, own repo panels (controller 1-up × 2 sheets, leaf 2-up × 2 sheets, adapter 1-up × 2 sheets), with the
PJ-324M tip-continuity check as a first-article test. Approval would not be a manufacturing release. The 2026-11-12/13
approvals do not carry over (they bind board `89310d53…e727` and manifest `557d5e48…502c`). `a7_jlc_package.py` refuses this set as current if any frozen identity or panel BOM/CPL changes.

### 2. Order-form and factory checks before upload (PCB_ORDER)

From `order-form-checklist.json`:

| Setting | controller | led_leaf | power_adapter |
|---|---|---|---|
| Layers / thickness | 4 / 0.8 mm ±0.1 | 2 / 0.8 mm ±0.1 | 2 / 1.6 mm |
| Stack-up | **JLC04081H-3313, select explicitly** (form default is 7628) | none published for 2-layer 0.8 mm | — |
| Surface finish | ENIG | ENIG | **HOLD** (not recorded) |
| Mask colour | green (0.10 mm bridge) | green | **HOLD** |
| Vias | Tented | Tented | — |
| Mask | openings as drawn | openings as drawn ("Do not modify original solder mask size") | — |
| Sheet / boards per sheet | 70 × 76.9 mm / 1 | 70 × 96.5 mm / 2 | 22.8 × 44 mm / 1 |
| PCBA qty | 2 sheets → 2 boards | 2 sheets → 4 boards | 2 sheets → 2 boards |
| PCB (bare) qty | **open**: JLC minimum not sourced; enter the minimum offered | same | same |
| Panel by JLCPCB | No | No | No |
| PCBA | Standard, Top + Bottom | Standard, Top | Economic, Top |

- Placement preview, centroids: controller J1 and J2 (anchor 7.358 mm off pad centre), J5 (1.25 mm), SW1 (0.568 mm);
  adapter J1 (5.236 mm), J2 (1.25 mm). Rotations are KiCad angles never checked against JLC's library, including the
  25 controller bottom-side resistors and the polarized parts listed in the checklist.
- Factory questions still unanswered: 3313 selectable without impedance control; leaf construction; ENIG exposed
  copper and mask openings kept as drawn; 0.10 mm tented-via web; thin 0.8 mm panel support and double-sided reflow;
  PCBA quantity unit and customer-panel acceptance (owner-stated, not JLC-confirmed).
- Parts: D3 BAS70-04-7-F (C134375) listed 1 in stock against 2 needed on 2026-11-22 (pre-order minimum 149). Needs an
  owner choice (pre-order / Global Sourcing, wait, or a separately reviewed alternate). No substitution was made.
  C160404 lists MOQ 43. Lead time, quote, reservation and assembly acceptance were not obtained for any line.

### 3. Bench-stage decisions (BENCH, not needed to prepare the PCB order)

- Power cable 55 ± 3 mm free span, order range 52–58 mm (±3 assumed), with the proposed 2.0 mm minimum bend radius
  from the 3HP route model; the 2026-11-12 acceptance (57 ± 3 mm) was for the old 1.6 mm design.
- CV noise: proposed limit 50 mV p-p under LED transmission, with an open CV input and with a patched ground-sharing
  source.
- Also open for the bench: rack hardware (case model), firmware-waveform T1L limits (#13), effective capacitance,
  materials appearance, fixture plate location and criterion 5.

### 4. First-article tests, then manufacturing release

First article: PJ-324M terminal 4/5 tip continuity before other jack-dependent tests, HX MSK13C02 truth table and land
fit, fixture contact (criterion 5), then the 19 procedures in `engineering/a7/qualification/plan.json` (#8, #10, #13).
A manufacturing release needs those results and a separate, revision-bound owner release decision.
