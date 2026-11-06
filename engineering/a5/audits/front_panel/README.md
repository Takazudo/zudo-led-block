# Front panel recovery audit

This folder contains the independent audit of the recovered A4 front panel files. A4.1 preserves the front geometry and engraving artwork. The historical report's absolute source path identifies the original recovered files; it is retained as provenance and is not a runtime dependency.

## Contents

- `front_panel_recovery_review.md`: interpretation, observed geometry, hidden hardware seat masks, process evidence, and remaining mechanical work.
- `independent_front_validation.json`: original saved recovery audit record, retained byte for byte.
- `front_process_sources.json`: official process and acrylic joining references.
- `verify_recovered_front.py`: portable SVG, DXF, STEP, topology, mirror, and integrity verifier. Its default output folder was changed during packaging so a new run does not overwrite the original audit record.

## Repeat the saved-file checks

Run from the project root, using a Python environment with `cadquery`, `ezdxf`, and `numpy` installed:

```sh
python audits/front_panel/verify_recovered_front.py front_panel
```

The command reads the project's relative `front_panel/` directory and writes `audits/front_panel/recheck/independent_front_validation.json`. To choose another output directory, supply it as a second argument:

```sh
python audits/front_panel/verify_recovered_front.py front_panel path/to/new_audit
```

The verifier returns a nonzero exit status if its numeric or file integrity checks fail. It does not modify front panel files or regenerate them. The `visual_inspection` statement in its JSON records the original recovery review of the existing A4 summary and rear-view PNG; it does not claim that a new execution performs a new human visual inspection. Production acceptance still requires material and laser-process agreement, integrated rear support and connector CAD, fastener/load assessment, and confirmation of the 30 mm assembly depth.
