# Continue Light Block from A4.1

## Recovered task

Conversation `6aecb1dd-85e0-8321-8771-3d66e1ecdf9c` ended during final A4 checking. Its source ZIP, report, workbook and preview were preserved. The supplied A3 package and transcript established the task. A4.1 finishes the front artwork and component selection round, with current stock observations and a TDK cost reduction. No additional user files are needed for design continuation.

Current decisions and exact source data are in `README_JA.md` and `procurement_rows.json`. Keep old A4 evidence historical. The primary list has 29 types / 76 pieces; TDK SPM4020T-4R7M-LR / C694586 is L1. Würth is a fallback and is excluded from primary totals. Stock is not reserved.

## Preserve the user's requirements and current direction

The intended module is 2HP first, with 3HP as a fallback; 128.5 mm high; a 30 mm installed rear-depth target; clear 2 mm acrylic with full visible rear frosting and clear letter strokes; replaceable translucent PETG sides; side light into Kumiko; eight independent RGB LEDs; ON / PROGRAM / CV modes; direct passive THRU; and nominal ±5 V sensing. Parts may remain visible. Do not use exposed bare FR-4 as the front.

The user's explicit procurement priorities are JLC PCBA compatibility, low cost and sufficient stock. The current implementation targets all PCB soldering at JLC, including factory hand soldering where supported, and home assembly using screws and ready-made cables. Avoiding home soldering is an implementation target; do not represent it as a separately confirmed immutable user requirement.

Prepare an integrated prototype order after design completion, then evaluate its optics and replaceable PETG. Do not reintroduce an optical-only PCB order. No purchase quantity has been agreed: the 1 / 10 / 100 module calculations are planning comparisons, not authorized orders.

## Next implementation sequence

### 1. Integrate the actual mechanical stack

Start from the editable A3 CAD in `references/light_block_A3_design_package.zip` and the verified A4 front in `front_panel/exports/`. Do not reuse A3 depth or interference results after changing controls.

- Model the exact PJ-3582-B contacts and locating features; orient 6.1 mm across HP. Positively capture its nutless plastic body against both insertion and withdrawal. Solder joints must not be the only load path.
- Model the selected Dailywell switch, epoxy/PCB seating datum, standard nut and factory-trimmed terminal envelope. The plain Ø6.50 mm front hole requires rear antirotation. Large standard lockwashers do not fit 2HP.
- Include all mated SH4 housings and wire exits. Offset connector zones near leaf ends and provide PETG relief; do not place an unmodeled housing inside the 1.45 mm optical gap.
- Use the TDK maximum 4.6 × 4.3 × 2.0 mm body and its own land pattern. Verify controller-back parts against both LED leaves.
- Include PicoBlade mating pairs, 50 mm completed cables, the IDC adapter, screw tips, strain relief, assembly order and SWD access.
- Deliver editable CAD, assembled/exploded STEP and a full-assembly clearance report. Verify the installed 30 mm target or state precisely which part exceeds it.

### 2. Build native KiCad circuit and layout

Create the native schematic, exact footprints and routed boards. Use manufacturer pin maps, not package-name assumptions. Keep controller/adapter and identical LED-leaf PCBA jobs explicit; compare mixed-panel charges against separate jobs.

Close direct THRU/loading, ±5 V mapping, ADC negative clamp, powered-off injection, reverse connection of both rails, 3.3 V sequencing/discharge, level-shifter Ioff/DIR, default-off reset, MLCC effective capacitance and buck current loops. TDK has normal-load margin by nominal calculation; hot minimum saturation and upstream-short/startup behavior remain unqualified. The downstream LED switch does not protect upstream faults.

### 3. Implement firmware and factory test

Implement the three modes, independent channels, calibration and initial 20% PWM cap. Keep the approximately 343–439 mA hardware current limit distinct from thermal brightness control.

Define FAULT handling and reset recovery explicitly. TPS2552-1 clears its latch when EN is toggled. A watchdog/software reset must not blindly re-enable an unresolved fault. Specify reset reasons, fault retention, intentional power-cycle/service recovery and failure behavior; change the circuit if the intended policy cannot be guaranteed.

Provide reproducible builds, HEX/BIN, SWD pads and factory checks for passive THRU, CV −5/0/+5 V, switch mapping, both chains, fault handling and reset behavior. Hardware, thermal and optical tests remain NOT_RUN before the prototype exists.

### 4. Prepare a reviewable integrated prototype order

Run ERC/DRC and inspect manufacturing plots. Export Gerber/drills, board-specific BOM/CPL, panel drawings, firmware and factory notes including PTH trim. Reconcile every populated-board and harness envelope with CAD.

Prepare Elecrow's specification using matching CUT and already mirrored rear engraving. Confirm cast clear 2 mm material, shallow frost, narrow transparent letters, registration, finished holes and concealed seats. Refresh stock and obtain actual manufacturing/assembly costs including attrition, MOQ and split jobs. Preparing the files is authorized; this recovery request does not authorize vendor messages or purchases.

## Release boundary

A manufacturing release requires native sources, applicable passing checks, complete installed-depth evidence, a documented assembly process, matching BOM/CPL/Gerber data, reproducible firmware and order-specific supplier acceptance. Stock-positive parts or a front-only STEP do not meet this boundary. Preserve the audit trail and report PASS / FAIL / NOT_RUN / supplier-confirmation-pending accurately.
