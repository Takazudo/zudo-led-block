# A5 harness and independent LED streams

This is the final A5 two-stream wiring contract. The actual KiCad XML netlists are checked by check_schematic_interfaces.py and independently reviewed in independent_review/review.json. The controller has one LED header, J3. There is no controller J4.

## Finished LED harnesses

Use two identical straight 1:1 four-wire assemblies. Both LED PCBs are identical and have both J1 and J2 populated.

| Physical cable | Pin 1 | Pin 2 | Pin 3 | Pin 4 |
|---|---|---|---|---|
| Controller J3 → left leaf J1 | GND | VLED | Left data | Right data |
| Left leaf J2 → right leaf J1 | GND | VLED | Right data | Left data, unused by right pixels |

On each leaf, J1 pin3 feeds that board's first pixel. J1 pin4 goes directly to J2 pin3. J1 pin3 is also connected to J2 pin4. This exchange happens in the PCB copper, so the purchased cables remain 1:1. The fourth pixel's DOUT is unused; it does not feed the other leaf. There are two independent four-pixel streams rather than one serial eight-pixel stream.

The right leaf's J2 is externally unconnected. It still contains VLED, GND and data; retain the insulating cover/clearance and do not connect an unrelated device. These project-specific SH4 ports do not use the Qwiic signal assignment.

PA6/TIM3_CH1 drives the left stream through the level translator and R14. PA7/TIM3_CH2 drives the right stream through the translator and R15. These MCU pins and the A5 firmware binary are unchanged by the connector revision. The right identical leaf is mounted end-for-end, so future patterns aligned by vertical position must reverse its pixel index. Current defaults use a uniform color within each side and are unaffected.

The first harness and the left leaf's power/ground distribution carry both leaves. The common TPS2552-1 current-limit calculation is approximately 343–439 mA, distinct from the software brightness cap. JST's SH rating depends on wire gauge; the selected finished harness drawing specifies AWG28. Confirm the actual incoming assemblies. No cable temperature or voltage-drop measurement is claimed.

## Power harness

The Molex 151340300 assembly reverses pins 1 and3.

| Location | Pin 1 | Pin 2 | Pin 3 |
|---|---|---|---|
| Controller power header J5 | +12 V | GND | −12 V |
| Adapter power header J2 | −12 V | GND | +12 V |

The adapter IDC10 has pins 1/2=−12 V,3–8=GND,9/10=+12 V. Its wiring compensates the finished Molex cable's reversal. Verify connector orientation against the actual assembly and polarity markings, not wire color alone.

## Mechanical qualification

The two-stream arrangement removes the controller J4-to-switch-terminal clash and frees the former J4 region for accessible service pads and resistors. It does not establish cable bend-life, connector retention or thermal qualification.

The CAD retains full-length rejected routing scenarios. Each variant has 12 wire-to-wire findings, three wire-to-diffuser contacts and one reference IDC/ribbon intersection. The leaf-link local curvature radii of approximately 0.20–0.28 mm are smaller than the modeled wire radius; those saved paths are not acceptable final physical routing. Reroute using the actual cable construction and bend behavior. The IDC ribbon exits sideways; required neighbor clearance and the strict 2HP/3HP envelope results are recorded in the mechanical checks. The Molex cable's 50±6 mm free span and undimensioned folded flag label also require confirmation.

Primary connector sources are indexed in mechanical/manufacturer_source_metadata.json and electronics/reports/. Exact final netlist hashes are retained in schematic_interface_check.json and independent_review/review.json.
