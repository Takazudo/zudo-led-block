# Review of the A5 interface assertions for A7

`engineering/a5/integration/check_schematic_interfaces.py` hardcodes A5 pin numbers. For A7 its *behavior* is kept in
`scripts/native_gate/interface.py` and its pin identities move to role maps in `interface_roles/`.

| A5 assertion | A7 disposition |
|---|---|
| Passive CV IN to THRU (`J1.6`, `J2.6`, `R1.1`) | kept as `cv.passive_thru`; tip pins come from PJ-324M evidence (R1 #16), never from PJ-3582 numbering |
| Jack grounds (`J1/J2` pins 2, 3) | kept as `cv.jack_returns`; sleeve and ring only where the selected TRS part requires it |
| (implicit) normals 4/5 unused | made explicit: `cv.normals_*_unused` |
| CV pickup, followers, affine node, C13 before R7, divider, ADC, grounds | kept unchanged (`cv.*`); these refs are not redesigned |
| Mode A/B to PA2/PA3 with pull-ups, common to GND | kept (`mode.*`) and extended with `mode.truth_table`: ON=01, PGM=11 (centre/open), CV=10 derived from the part's contact table |
| LED enable/base pull-down/switch enable/FAULT | kept (`power.*`) |
| Translator, damping, cable pins, two-harness composition, leaf chains | kept (`led.*`, `leaf.*`) |
| Adapter rails and cable reversal, controller J5 polarity | kept (`adapter.*`, `power.cable_*`) |
| Fitted quantities vs procurement ledger | **removed from the interface gate**: A7 changes the BOM; quantity reconciliation belongs to the BOM/catalog work (#9) |

The A5 role map (`interface_roles/a5_reference.json`) passes on both the historical A5 netlists and fresh KiCad 10.0.8
exports. The A7 map (`interface_roles/a7_controller.json`) leaves jack and switch roles `unresolved`, so it fails until
R1/R4 evidence fills them.

## Controller board layout dispositions (R4 #19, layout review of PR #30)

Measured on the committed board with `scripts/a7_route.py`'s proposal (`routing/route_proposal_seed0.json`); the native
gate result is the authority for connectivity.

| Item | Disposition |
|---|---|
| Buck hot loops (U2 AP63205) | C1 sits across VIN (U2.3) and GND (U2.4), 1.7 mm pad to pad; C4 across BST/SW under the IC (1.5 mm each); L1's SW pad directly below, BUCK_SW 1.1 mm of F.Cu copper, no vias; output cap C2 at L1's +5 V pad. U2.4, C1.2 and C2.2 each stitch to the In1 plane with at least two vias. |
| CV analog chain | ADC-buffer island beside U4: D3 at U7.3 (1.8 mm, CV_FILTER 2.4 mm total), C17 at U7.5 (1.5 mm), C13 and R4–R7 at the CV_AFFINE node (9.8 mm total). The long run between the U6 island and U7 carries U6's low-impedance output CV_BUF, not a filtered or high-impedance node. No CV node runs within 0.6 mm of DATA_L/R or ±12V_PROT on the same layer. |
| MCU decoupling | C8 (100 n) directly under VDD (U1.3, 1.4 mm) and GND (U1.4); C7 (4.7 µ) and C14 (NRST) at the MCU's upper right. LDO output cap C6 2.9 mm from U3.5; input cap C5 6.1 mm from U3.1 (the +5 V rail also has C2/C3/C15). |
| Under U1 (UFQFPN28, no exposed pad) | The router forbids signal vias inside the pad ring and keeps CV_ADC out of U1's footprint on every layer. One GND via (U1.4 to In1) sits under the body. Tented In2/B tracks still pass under the body for +3V3, DATA_L_3V3, DATA_R_3V3, LED_ENABLE, MODE_A, MODE_B, SWCLK and SWDIO; these are digital or static nets, accepted with the solid In1 GND plane between them and the F-side pads. |
| PTH to track | The A5 rules have no PTH-to-track rule; the closest PTH drill to another net's track is 0.41 mm (JLCPCB minimum 0.28, recommended 0.35, `fab/jlcpcb_capabilities.json`). |
| Q1 placement | Q1 (DC enable for U4) sits in the free corner beside SW1; LED_ENABLE and LED_EN_N are static levels, so their length is not critical. |
