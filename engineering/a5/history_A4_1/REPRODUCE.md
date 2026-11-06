# Source map and reproduction

The delivered PDF, XLSX, front STEP/SVG/DXF and PNG can be opened directly. Rebuilding is optional. This package is a front-panel and procurement review; it contains no released whole-module KiCad design or working firmware.

## Current sources

| Path | Purpose |
|---|---|
| `README_JA.md` | Current design decisions, prices and limitations |
| `continue-here.md` | Context and the next engineering work |
| `procurement_rows.json` | Current A4.1 selection used by both report and workbook |
| `procurement_inputs_A4_1.json` | Frozen dated observations and selection; current builder recalculates costs and coverage |
| `evidence_refresh/` | Compact observed supplier facts, URLs and timestamps |
| `front_panel/` | Unchanged A4 artwork, geometry and editable generator |
| `audits/` | Recovery, front, electronic desk analysis, workbook and report checks |
| `deliverables/` | Current verified PDF, workbook and unchanged front preview |
| `references/light_block_A3_design_package.zip` | Supplied A3 source package; starting point for rear CAD, not current clearance proof |
| `history_A4/` | Original overview, procurement data, aggregate verification and builders |

Original `research_jlc_electronics.*`, `io_service_audit.*`, `harness_supply_followup.*` and `*_evidence/` remain dated A4 references. Their original prices or design status must not override A4.1. The previous Würth inductor appears in current data only as a fallback; its old descriptive notes refer to the earlier selection.

## Python environment

Use Python 3.10 or later. The frozen procurement builder, package builder and electronics desk-analysis scripts use only the standard library. CAD and PDF tools need the packages listed in `requirements.txt`. Front artwork uses the DejaVu Sans font; the Japanese PDF needs Noto Sans JP regular and bold TrueType fonts. Set `LIGHT_BLOCK_FONT_DIR` to their directory if they are not discovered automatically.

From the extracted project directory:

```sh
python build_procurement_rows.py --check
python audits/front_panel/verify_recovered_front.py front_panel
python audits/electronics/build_recovery_audit.py
python audits/electronics/build_tdk_costdown_audit.py
```

The first command checks that the current selection matches the frozen inputs and their evidence hashes; it does not fetch current stock. The front verifier records a fresh read-back in `audits/front_panel/recheck/` and preserves the original audit.

To intentionally regenerate the procurement JSON after editing frozen inputs:

```sh
python build_procurement_rows.py
```

To regenerate the front exports or PDF:

```sh
python front_panel/build_front_artwork.py
python build_brief.py
```

The PDF defaults to `deliverables/light_block_A4_1_front_and_procurement.pdf`; `LIGHT_BLOCK_OUTPUT_DIR` overrides its destination. Regenerated exports must be visually reviewed and their audit hashes refreshed before packaging. PDF metadata can vary between builds without a visual change. Do not overwrite old passing audit hashes merely to suppress a meaningful discrepancy.

## Workbook environment

`spreadsheet/build_parts_workbook.mjs` uses the `@oai/artifact-tool` JavaScript package supplied by the ChatGPT/Codex spreadsheet runtime. It also works in an environment where a compatible package is already installed. No bundled third-party runtime is included in this source archive.

With that dependency available to Node's module resolver:

```sh
node spreadsheet/build_parts_workbook.mjs procurement_rows.json
```

The default output is `deliverables/light_block_A4_1_parts.xlsx`. `A4_PROJECT_DIR`, `A4_OUTPUT_DIR` and `A4_QA_DIR` can override the project, output and generated review directories. In the supplied runtime, a temporary copy of the script can resolve dependencies through a `node_modules` symlink to `CODEX_PRIMARY_RUNTIME_NODE_MODULES`; retain `A4_PROJECT_DIR` pointing to this project and execute with `CODEX_PRIMARY_RUNTIME_NODE`.

The delivered workbook was exported and reimported with Artifact Tool, recalculated at the comparison quantities and inspected visually. Native Excel/LibreOffice execution was not performed. Existing Excel table, frozen panes, validation and conditional formatting are preserved. Unpriced external items remain visibly incomplete rather than becoming a full manufacturing quote.

## Package verification

After the artifacts and their review records agree:

```sh
python build_package.py --output ../light_block_A4_1_design_package.zip
```

The builder checks current source/evidence consistency, compares reviewed artifact hashes, writes `verification_A4_1.json` and `package_manifest.json`, then verifies every archived hash and ZIP CRC. It never treats this as a whole-module release or performs an upload/order. A passing archive check does not replace any pending physical, electrical or supplier verification listed in the report.
