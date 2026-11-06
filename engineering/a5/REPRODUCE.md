# Light Block A5: source map and reproduction

Supplied PDF, workbook, KiCad files, CAD and firmware images can be inspected directly. Rebuilding is optional and does not create a manufacturing release.

## Current sources

| Path | Purpose |
|---|---|
| README_JA.md / continue-here.md | Decisions and remaining work |
| integration/a5_status.json | Actual result summary used by the report |
| procurement_inputs_A5.json | Frozen selection and dated observations |
| procurement_rows.json | Recalculated BOM, quantities, costs and coverage |
| mechanical/ | Geometry, CAD generators, exports and fit checks; read local instructions |
| electronics/design/ | Pins, components, placement and native design generators |
| electronics/native/ | Three editable KiCad projects |
| electronics/footprints/ | Self-contained footprints and licensed upstream originals |
| firmware/ | C source, fixed SDK, Makefile, tests and compiled images |
| front_panel/ | Unchanged A4 artwork and generator |
| integration/ / audits/ | Checks, independent review and artifact QA |
| deliverables/ | Current PDF, workbook and front illustration |
| history_A4_1/, history_A4/, references/ | Earlier sources, deliverables and recovery packages |

Old research_jlc_electronics, io_service_audit, harness_supply_followup and historical evidence are dated research. Their old prices/status/ADC formula do not override A5.

## Dependencies

Use Python 3.11+ and compatible packages from requirements.txt. CAD uses CadQuery 2.7.0. PDF generation uses ReportLab and NotoSansJP regular/semibold TTF; set LIGHT_BLOCK_FONT_DIR if necessary. Native checks used KiCad 10.0.8. PCB generation also requires KiCad's pcbnew Python module.

Firmware used ARM GCC 13.2.1 and STM32CubeG0 v1.6.3. Exact SDK/device/HAL commits and licenses are in firmware/sources.json and firmware/dist/verification.json. Follow firmware/README.md for tests and builds. Actual ELF/HEX/BIN are included; no device was flashed. Toolchain executables are not bundled.

## Procurement

From the project directory:

    python3 build_procurement_rows.py --check

This recalculates frozen observations and checks evidence hashes, without refreshing stock. After deliberately changing the input, run without --check, then rebuild and review dependent artifacts.

## Native electronics

Generation overwrites generated designs. Preserve any manual board edits first. Read the electronics instructions and generator scope: controller routing is unfinished in this checkpoint.

With kicad-cli on PATH:

    python3 integration/run_native_schematic_checks.py
    python3 integration/check_schematic_interfaces.py integration/native_schematic/controller/netlist.xml integration/native_schematic/led_leaf/netlist.xml integration/native_schematic/power_adapter/netlist.xml

The first script runs native ERC and XML/PDF exports for all three. Default ignored categories are retained in the record. The second independently checks actual exported pins and quantities. Neither proves analog behavior or routing. Assess DRC reports separately.

The native-check script accepts --prefix /path/to/extracted/kicad for the portable development toolchain used here. It modifies only child-process paths. integration/toolchain_receipt.json records acquired packages and versions.

## CAD and front

Follow the mechanical README for assembly generation and STEP/STL/3MF checks. Assumed cable scenarios and unresolved dimensions are identified explicitly.

The front artwork stays A4. Its independent audit is in audits/front_panel/. To deliberately regenerate:

    python3 front_panel/build_front_artwork.py

Recheck dimensions, registration, mirror direction, counters and appearance after changes. A new hash does not prove geometric equivalence.

## Workbook

spreadsheet/build_parts_workbook.mjs uses @oai/artifact-tool. With the package in Node's module resolution path:

    node spreadsheet/build_parts_workbook.mjs procurement_rows.json

Default output: deliverables/light_block_A5_parts.xlsx. LB_PROJECT_DIR, LB_OUTPUT_DIR and LB_QA_DIR override directories. In the supplied runtime, use CODEX_PRIMARY_RUNTIME_NODE and dependencies from CODEX_PRIMARY_RUNTIME_NODE_MODULES in a temporary execution directory, retaining LB_PROJECT_DIR.

The builder checks quantity edits, tier boundaries, zero/blank inputs, totals and source reconciliation, then renders views. Delivered files were checked in Artifact Tool and through exported OOXML features. Native Excel/LibreOffice execution was not performed. Inspect changed rows visually.

## Engineering report

    python3 build_brief.py

Reads procurement_rows.json and integration/a5_status.json, writes deliverables/light_block_A5_engineering_update.pdf. LIGHT_BLOCK_OUTPUT_DIR overrides the destination. Render every page, inspect text/layout and only then update audits/report/report_verification.json. PDF metadata may vary across rebuilds.

## Archive

After sources and review records agree:

    python3 build_package.py --output ../light_block_A5_design_package.zip

Checks reviewed front/workbook/report hashes, current native schematic provenance, firmware source/binary identity and procurement consistency. Writes verification_A5.json and package_manifest.json, then verifies each archived SHA-256 and ZIP CRC.

Includes authored design/source and licensed dependencies. Excludes toolchains, firmware intermediates, Git metadata, temporary render caches and newly retrieved manufacturer PDF/page caches. Compact observations and hashes remain.

No upload, supplier message, purchase, flashing or printing occurs. A passing archive check proves file integrity, not hardware qualification.
