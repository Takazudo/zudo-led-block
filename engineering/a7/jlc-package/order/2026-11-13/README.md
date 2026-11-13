# JLCPCB order files: A7 test prototype, 2 units (2026-11-13)

Exported from `main` at `db0ca95` (after PR #79, HX MSK13C02 switch version) with the pinned
KiCad 10.0.8 image. Route: **our own repo panels**, one Gerber zip per board type, PCBA qty 2 each.
No order has been placed.

> Status: the owner approved this prototype route (2026-11-13, `engineering/a7/qualification/records.json`).
> This is **not a manufacturing release**: the repo readiness gate is still `BLOCKED` (bench
> measurements only happen after the boards exist), and the tool-generated file names keep their
> `DRYRUN` suffix. Upload them as they are; JLC does not care about the names.

## What to upload, per board type (three separate orders/cart items)

| Board | Gerber upload (PCB page) | BOM upload (PCBA page) | CPL upload (PCBA page) |
|---|---|---|---|
| controller | `controller/controller-panel-gerbers-DRYRUN.zip` | `controller/controller-panel_BOM_DRYRUN.csv` | `controller/controller-panel_CPL_DRYRUN.csv` |
| led_leaf | `led_leaf/led_leaf-panel-gerbers-DRYRUN.zip` | `led_leaf/led_leaf-panel_BOM_DRYRUN.csv` | `led_leaf/led_leaf-panel_CPL_DRYRUN.csv` |
| power_adapter | `power_adapter/power_adapter-panel-gerbers-DRYRUN.zip` | `power_adapter/power_adapter-panel_BOM_DRYRUN.csv` | `power_adapter/power_adapter-panel_CPL_DRYRUN.csv` |

## Order settings

| Setting | controller | led_leaf | power_adapter |
|---|---|---|---|
| Base material | FR-4 | FR-4 | FR-4 (not recorded in the repo; FR-4 assumed) |
| Layers | 4 | 2 | 2 |
| Dimensions (panel sheet) | 70 × 76.9 mm | 70 × 96.5 mm | 22.8 × 44 mm |
| Boards on one sheet | 1 | 2 | 1 |
| Delivery format | Panel by Customer | Panel by Customer | Panel by Customer |
| Panel by JLCPCB | No | No | No |
| PCB thickness | 1.6 mm | **0.6 mm** | 1.6 mm |
| Surface finish | your choice (not in board file) | your choice | your choice (HASL or ENIG) |
| PCB qty | JLC minimum offered | JLC minimum offered | JLC minimum offered |
| PCB Assembly | On | On | On |
| PCBA type | Standard (parts on both sides) | Standard (C52917434 is Standard only; 0.6 mm) | Economic |
| Assembly side | Both (Top + Bottom) | Top | Top |
| PCBA qty | 2 sheets → 2 boards | 2 sheets → 4 boards | 2 sheets → 2 boards |
| Placements | SMD 56, THT 3 (J1, J2, J5) | SMD 10 per board | THT 2 (J1, J2) |

Sheets have 5 mm rails, mouse-bite tabs (0.6 mm holes), three 1 mm fiducials and three 2 mm tooling holes.
BOM/CPL designators on the 2nd led_leaf copy carry a `_2` suffix; CPL origin is the sheet's top-left corner (mm).

## Check on the JLC order form before paying

- **Placement preview, centroids:** controller J1, J2 (PJ-324M, anchor 7.36 mm off pad centre), J5, SW1; power_adapter J1, J2. JLC places by part centre.
- **Placement preview, rotations:** angles are KiCad footprint angles, never checked against JLC's library (including controller bottom side).
- **PCBA qty unit:** confirm the form counts sheets (2) and that one sheet meets the 2-pcs minimum.
- **Customer panel acceptance:** whether JLC assembles these repo panels is the owner's call (O12), not JLC-confirmed.
- **Known accepted risk:** PJ-324M terminal 4/5 function is unconfirmed (continuity test waived 2026-11-12); check on first article.

## Verification of this export

- `scripts/a7_panel.py build`: PASS (`panel-build-summary.json`): parts, pads, tracks, vias, zones, outline, drills match the frozen boards; panel DRC adds nothing; CPL matches KiCad's own position export; file set matches `panels/build-receipt.json`.
- `scripts/a7_jlc_package.py export` (single boards, reference only): PASS (`single-board-export-summary.json`).
- Hashes in `SHA256SUMS`.

Regenerate: `python3 scripts/a7_panel.py build --out <empty dir outside the repo>` (needs Docker).

## Later note (2026-11-13, after #80; the export above is unchanged)

The files and hashes above are unchanged. The sourcing reconciliation (#80) changed
`engineering/a7/procurement/assembly-manifest.json` from `c12c964a…e865` to `557d5e48…502c` (sourcing fields only: order_plan line fields
and attrition text, population sourcing pointers, the supply-blocker text and three added input hashes; no part, quantity, board or placement change; the panel BOM/CPL here still equal
`engineering/a7/jlc-package/panels/` byte for byte). The owner's prototype-route approval is bound to the old manifest
digest, so `readiness.json` shows the `owner_prototype_route` gate again until the owner re-approves the current identity
set. The approval record itself is unchanged. The stage-by-stage state is at the top of
`engineering/a7/docs/continuation/continue-here.md`.

Later note (2026-11-13, after the re-approval): the owner re-approved the prototype route for the current identity set
(reply "approve", 2026-11-13T19:44:23Z; `engineering/a7/qualification/approvals/2026-11-13-owner-prototype-route-sourcing-manifest.md`).
`records.json` now binds `557d5e48…502c`, and readiness no longer shows the `owner_prototype_route` gate. The order-form
checks above still apply. This is not an order or a manufacturing release.
