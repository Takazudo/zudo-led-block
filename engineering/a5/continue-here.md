# Continue Light Block from A5

Engineering checkpoint: 2026-11-06 JST. Start with README_JA.md, verification_A5.json, the engineering PDF and the current mechanical/electronics reports. This contains actual source and generated deliverables, but it is not a manufacturing release.

## Preserved intent

Build a narrow Eurorack art light beside Kumiko blanks. Prefer 2HP (9.8 mm panel); retain 3HP (14.9 mm) using the same electronics. The front is 128.5 mm high and 2 mm clear cast PMMA. Its visible rear is frosted except clear letter strokes and mode symbols. Letter counters remain frosted; only small concealed hardware seats remain clear. The front stays smooth. Rear engraving artwork is already mirrored.

Use replaceable translucent PETG sides, four independently controlled RGB LEDs per side, ON / PROGRAM / CV, passive IN-to-OUT THRU and nominal±5 V sensing. The 30 mm installed depth starts at the panel rear, z=0, and includes mating connectors, pins and cable bends. Complete the design before an integrated prototype; do not make a separate optical-only PCB order.

Factory soldering, finished cables and home screw/plug assembly are the implementation target, not a newly inferred immutable user rule. No order quantity is agreed. Workbook 1/10/100-module figures are comparisons. No vendor message or purchase has been made.

## Completed work

- Recovered A4.1 and verified 247 archive entries. Original A3 and earlier material remain historical.
- Retained the independently checked A4 panel. Its previous audit covers 29 files; current packaging checks unchanged reviewed hashes.
- Created three native KiCad schematic/board projects with self-contained libraries. Read actual DRC reports: a clean schematic ERC does not mean the controller is routed.
- Exported all schematics through KiCad 10.0.8 and independently checked XML netlists against MCU pins, THRU, cable reversal, LED order, enable/fault and procurement quantities.
- Implemented and compiled STM32G031 firmware. firmware/dist/verification.json and source_files.sha256 identify tests, pinned SDK and ELF/HEX/BIN/MAP.
- Added TLV9001 and a 330 Ω/1kΩ ADC divider. Moved C13 before R7 so its stored-charge path to U7 includes the existing series resistor. Independent review states the conditional bounds and transient limitations.
- Developed rear geometry for both widths with real connector envelopes and explicit cable scenarios. Consult the fit records; do not infer installed fit from fixed-body depth.
- Updated the workbook and ledger to 30 part numbers and 81 fitted pieces.

## Electrical and firmware contract

STM32G031G8U6TR is UFQFPN28. PA0=CV ADC; PA2/PA3=switch; PA4=active-low FAULT; PA5=LED enable through NPN inverter; PA6/PA7=independent TIM3 streams. PA13/PA14 and NRST are service pads.

Switch bits:01 = ON, 11 = PROGRAM, 10 = CV, 00 = invalid/dark. Center physicalOFF meansPROGRAM. ON is capped white; PROGRAM is an 8-second opposed breathing pattern; CV uses magnitude for brightness and sign for warm/cool color. These are provisional. The 51/255 cap is not thermal qualification.

A5 conversion: VADC=(100/133)*(VDD/2+CV/8); CV=10.64*VADC-4*VDD. VREFINT estimatesVDD; calibration hooks exist. The A5 image is incompatible with the older A4.1 analog circuit. Moving C13 before R7 changes the dominant pole from about 740 Hz to 776 Hz, without changing the DC transfer or binary.

LED timing:60 MHz,78 ticks/cell,21/57 high ticks for zero/one. Reset is at least 320 µs under the analyzed +3% clock limit. Use the exact pinned Worldsemi WS2812B-2020-V6 source in firmware/sources.json. Older generic WS2812 timings are not interchangeable. Software analysis is not an oscilloscope measurement.

FAULT, stale/invalid ADC and DMA failure drop enable and force data low. Retained boot/armed/fault markers and reset reasons keep LEDs dark after unsafe warm resets. A normal complete power cycle starts without a hidden service gesture. A fault that removes backup power can erase the marker and allow restart. There is no independent 5 V-valid monitor: a 5 V-only sag/recovery before FAULT is observed also falls outside the warm-reset guarantee.

Controller J3 uses SH4 pins 1=GND, 2=VLED, 3=left DATA, 4=right DATA. Each identical leaf has J1 pins3/4=THIS/OTHER and J2 pins3/4=OTHER/THIS. Two unchanged 1:1 cables connect controller J3→left J1 and left J2→right J1. Each leaf consumes its own four-pixel stream; the right leaf J2 remains externally unused. Both streams remain independent. Controller J4 was removed to resolve the switch-tail collision. This is a project-specific pin map, not Qwiic signaling. The first harness carries both leaves under the shared LED current limit.

The Molex power cable reverses pins1↔3: controller1/2/3=+12/GND/−12; adapter1/2/3=−12/GND/+12. Confirm physical orientation with the assembled cable.

## Next work in order

1. **Finish controller layout.** Read electronics/reports/. Preserve mechanical/geometry.json and the agreed coordinates in electronics/design/design_data.py. Finish placement/routing, buck hot loop, analog isolation, ground return, decoupling and service access. Run native DRC including unconnected items. Assess actual results without global exclusions.

2. **Resolve the installed power cable.** The full-length individual wire models still have recorded crossings/diffuser contacts; the current assembly is a study with those unresolved paths. IDC ribbon exits sideways. The R3 scenario is an explicit design assumption, not a supplier rating. Identify/measure the actual socket and strain relief, ribbon thickness, permissible radius and free length. Check 2HP first and use 3HP if required. A remote adapter moves part of the assembly outside the envelope; it is not automatically a 30 mm solution. The Molex 50±6 mm dimension is between wire exits, and its flag label also needs physical accommodation.

3. **Finish mechanical tolerances and printing.** Check jack collars, toggle anti-rotation, axial seating, terminal trims, board support and tool access. Do not rely solely on solder joints for plug loads or preload the acrylic. Verify PETG walls, holes and retention with a matching slice profile. The saved H2D0.6 template is PLA; its unsliced fit project is not PETG-qualified toolpath. A saved H2D0.6 PETG project from the user can provide established material settings.

4. **Recheck protection on the finished circuit.** Follow integration/independent_review/. DC current budgets rely on stated assumptions. Test fast rail collapse, partial rails, back-power, U7 differential stress, LDO reverse current, CV while unpowered, startup, load/short behavior, MLCC effective capacitance and inductor temperature. LED-side limiting does not protect every upstream short. Decide whether the desired partial-rail recovery behavior needs a 5 V-valid monitor or other hardware change.

5. **Prepare the integrated prototype release.** After layout and fit agree, generate/review Gerber, drill, board-specific BOM/CPL, stackups, assembly notes, harness mapping and programming/calibration instructions. Confirm JLC Standard Only LED route, factory hand soldering/trimming and flashing. Refresh current price/stock and obtain the order-specific quote before committing funds.

6. **Evaluate actual hardware.** Measure LED waveforms, power/current, CV and THRU, fault/recovery, startup/reset, hot spots, illumination of Kumiko, PETG temperature, insertion/extraction and side replacement. Measure the 30 mm envelope with every cable installed. Tune visual behavior after these tests.

## Evidence and cost

procurement_rows.json is rebuilt from procurement_inputs_A5.json. Each row retains its actual observation time and primary URL. Baseline observations are 11:30–11:37 JST; U7 is 14:37 and IDC10 is 14:39. These are not stock reservations. At 10 modules, fitted parts are$8.7205/module; two LED harnesses and one power harness produce a partial subtotal of$13.6055. PCB/assembly/attrition/setup/ribbon/mechanics/shipping/tax are excluded.

Current native checks and reviewed hashes are in integration/ and audits/. A4/A4.1 records remain historical and must not override A5. Newly retrieved manufacturer document/page caches are excluded from the package; compact source URLs, hashes and engineering facts are retained. Licensed footprints and SDK retain their notices.

Read REPRODUCE.md for rebuild instructions. Compiler/KiCad executables are not bundled; versions are recorded. Never update a passing audit hash merely to conceal an unreviewed change.
