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
exports. The A7 map (`interface_roles/a7_controller.json`, `status: reviewed`) fills the jack and switch roles from R1
evidence (#16). The independent electrical review of the schematic phase approved those pin identities
([PR #24 review 5818088400](https://github.com/Takazudo/zudo-led-block/pull/24#pullrequestreview-5818088400), head
`1a2f31a`). That approval covers the intended connectivity only. The PJ-324M pin functions stay INFERRED, and PCM13SMTR
centring is ASSUMED, until the physical gates listed in the map's `review.open_physical_gates` are passed.

## Controller board layout dispositions (R4 #19, layout review of PR #30, board revision 2)

Measured on the committed board (revision 2, sha256 `4453f818…628e`) with `scripts/a7_route.py`'s proposal
(`routing/route_proposal_seed0.json`). The native gate result is the authority for connectivity. Revision 2 applies
the four non-blocking polish items from the PR #30 re-review. It was re-reviewed on PR #37 (reviews 5818789798 and
5818812844, approving comment 6724516695, head `ae5aa3c`) and merged to main as `edf98c2`.

| Item | Disposition |
|---|---|
| Buck hot loops (U2 AP63205) | C1 sits across VIN (U2.3) and GND (U2.4), 1.7 mm pad to pad. C4 is across BST/SW under the IC (1.5 mm each). L1's SW pad is directly below, and BUCK_SW is 1.1 mm of F.Cu copper with no vias. The output cap C2 is at L1's +5 V pad. U2.4, C1.2 and C2.2 each stitch to the In1 plane with at least two vias. Unchanged from the reviewed board. |
| U6 rail decoupling (revision 2) | U6 moved left so its rail caps sit at their own pins. C12 is 1.63 mm from −12 V pin 2, and C11 is 1.53 mm from +12 V pin 5 (previously 5.8 mm) in the strip at the board edge. |
| U4 input (revision 2) | C15 (10 µF on +5 V) moved from the jack strip to directly above U4.1 IN, 1.8 mm centre to centre. The nearest +5 V cap was previously C2 at 4.1 mm. |
| CV analog chain | ADC-buffer island beside U4. D3 is at U7.3 (1.8 mm) and C17 at U7.5 (1.5 mm). CV_FILTER is 3.9 mm long, all on F.Cu. C13 and R4–R7 sit at the CV_AFFINE node (8.1 mm total). The long run between the U6 island and U7 carries U6's low-impedance output CV_BUF, not a filtered or high-impedance node. No CV node runs within 0.6 mm of DATA_L/R or ±12V_PROT on the same layer. |
| CV_FILTER vs VLED (revision 2) | The router keeps CV_FILTER and VLED copper 1.2 mm apart wherever the layers couple (`SEPARATE`/`COUPLED` in `a7_route.py`). F.Cu is shielded from In2/B by the In1 GND plane, but In2 and B have no plane between them. The result: CV_FILTER is F.Cu only, VLED's nearest same-layer copper is 3.65 mm away (previously about 0.9 mm), and VLED's nearest via is 2.7 mm away. VLED crosses under CV_FILTER on In2/B, with In1 GND between them. |
| U7 and C17 GND (revision 2) | U7.2 and C17.2 stitch to In1 within 0.9 mm (`GND_VIA_NEAR`). The vias are at 0.52 mm and 0.66 mm, previously 1.5–2 mm. The solder face under those sites is kept free of B-side resistors (`GND_STITCH_SITES` in `a7_board.py`). |
| MCU decoupling | C8 (100 n) sits directly under VDD (U1.3, 1.4 mm) and GND (U1.4). C7 (4.7 µ) and C14 (NRST) are at the MCU's upper right. The LDO output cap C6 is 2.5 mm from U3.5. The input cap C5 is 5.9 mm from U3.1; the +5 V rail also has C2, C3 and C15. |
| Under U1 (UFQFPN28, no exposed pad) | The router forbids signal vias inside the pad ring. It keeps CV_ADC out of U1's footprint, minus a 0.2 mm band at the courtyard edge, on every layer except its own pad. In revision 2, CV_ADC enters only that band, beside its own pad U1.6. One GND via (U1.4 to In1) sits under the body. Tented In2/B tracks still pass under the body for +3V3, DATA_L_3V3, DATA_R_3V3, LED_FAULT_N, MODE_A, MODE_B, NRST and SWCLK. These are digital or static nets, accepted with the solid In1 GND plane between them and the F-side pads. |
| PTH to track | Enforced by native DRC since revision 2. The custom rule `a7_pth_to_track` (`controller.kicad_dru`, 0.35 mm = JLCPCB recommended, minimum 0.28, `fab/jlcpcb_capabilities.json`) is proved on every gate run by `control_pth_to_track`. The closest PTH drill to another net's track is 0.386 mm (J5.3 to VLED on In2). |
| Q1 placement | Q1 (DC enable for U4) sits in the free corner beside SW1. LED_ENABLE and LED_EN_N are static levels, so their length is not critical. |
