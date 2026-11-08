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
