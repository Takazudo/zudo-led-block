# Actual Gerber inspection tooling

Gerbonara 1.6.3 parses the **exported Gerber files**, including aperture macros and ordered dark/clear primitives. Primary documentation: https://gerbolyze.gitlab.io/gerbonara . `requirements.lock` pins every resolved dependency and wheel SHA256 (Linux x86_64, Python 3.12). Install into a disposable environment, not globally:

```sh
python3 -m venv /tmp/a7-gerber-tools
/tmp/a7-gerber-tools/bin/pip install --require-hashes -r engineering/a7/verification/optical/tools/requirements.lock
/tmp/a7-gerber-tools/bin/python scripts/a7_gerber_review.py \
  engineering/a7/verification/optical/led_leaf/gerbers /tmp/a7-leaf-gerber-views \
  --bounds 0 -82.5 9 0 --render
```

`--render` requires Inkscape; omit it for SVG and parsed JSON only. The bounds are **Gerber coordinates**, with negative Y for this leaf. Dark shapes in normal mask views mean **openings**, despite the X2 `FilePolarity=Negative` material convention. The separate residual-mask views invert these openings on the specified rectangular viewport. Clear-polarity primitives remain in draw order. Copper views do not subtract separate Excellon drill holes.

The review JSON binds each actual Gerber hash, attributes, object counts and polarity. It is not an ERC/DRC result. The native board protection inventory remains a separate requirement. `led_leaf/export-receipt.json` records the PCB identity, fixed KiCad image, actual export command and rendering script/lock hashes. Its staging export is not the formal Actions native gate.

`scripts/a7_gerber_inspect.py` uses the same environment to **measure** instead of render. It takes the board
and a Gerber directory and tests the plotted primitives themselves: every via must keep `--web` mm (0.1 by
default, the JLC green 1 oz mask bridge) of mask beyond its copper on both mask files, every paste shape must
be a flash centred on a pad of that face with no drawn region or line, and it reports per-layer coverage and a
stdlib greyscale overview as inspection aids. A mask shape is an opening whether it came from a generated
rectangle or an ordinary component pad aperture, so a pad opening that overrides a via tent fails here. CI runs
it on both boards on every push, and `raster-inspection.json` records the result and the inspecting script's own
SHA-256.

```sh
/tmp/a7-gerber-tools/bin/python scripts/a7_gerber_inspect.py \
  --board engineering/a7/electronics/controller/controller.kicad_pcb \
  --gerbers engineering/a7/verification/optical/controller/gerbers \
  --out /tmp/a7-controller-inspection
```

It is a review of plotted geometry: not DRC, not a fabricator DFM result and not an optical measurement. The
controller's `raster-inspection.json` comes from this script; the leaf's retained file predates it and records
the earlier antialiased raster estimates described above.

Identity validation needs only the Python standard library, not Gerbonara or a renderer:

```sh
python3 scripts/a7_gerber_review.py --verify-receipt engineering/a7/verification/optical/led_leaf/export-receipt.json
python3 -m unittest discover -s scripts/tests -p test_a7_gerber_review.py
```

This checks current A7 PCB bytes, every retained Gerber, the renderer source, dependency lock, and review artifacts. Negative tests replace the leaf with A5 bytes or alter a Gerber and require rejection. The review-only directory deliberately omits `.gbrjob`; an extra unrecorded file is rejected. These checks detect stale evidence, not electrical or manufacturing suitability.
