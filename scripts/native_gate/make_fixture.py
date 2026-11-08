#!/usr/bin/env python3
"""Build the routed, zoned infrastructure fixture from the immutable A5 LED leaf.

Runs INSIDE the digest-pinned KiCad 10.0.8 image and writes ONLY into an empty
--out directory (never into the repository). The result is committed under
scripts/tests/fixtures/native/led_leaf_zoned/ after review, together with
provenance.json written by this script.

The fixture is test infrastructure for the native gate. It is NOT an A7 board,
not an A5 revision and not a manufacturing file.

Transformation (deterministic, from the A5 leaf):
  * copy led_leaf.kicad_sch, LightBlock.kicad_sym, sym-lib-table, led_leaf.kicad_pro
    byte-for-byte (renamed to fixture.*);
  * load led_leaf.kicad_pcb, add one GND copper zone on F.Cu (the layer carrying every GND pad) over the board
    outline bounding box inset by 0.5 mm, fill all zones, save as fixture.kicad_pcb;
  * write an fp-lib-table that resolves to the A5 footprint library at its
    repository path (staged at the same relative path by the gate).
Routed copper (tracks/vias) is copied unchanged from the A5 leaf.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

SRC_DIR = 'engineering/a5/electronics/native/led_leaf'
FIXTURE_DIR = 'scripts/tests/fixtures/native/led_leaf_zoned'
FP_LIB = ('(fp_lib_table (version 7) (lib (name "LightBlock") (type "KiCad") '
          '(uri "${KIPRJMOD}/../../../../../engineering/a5/electronics/footprints/LightBlock.pretty") (options "") '
          '(descr "A5 exact part footprints, referenced in place")))\n')
COPIES = {'led_leaf.kicad_sch': 'fixture.kicad_sch', 'LightBlock.kicad_sym': 'LightBlock.kicad_sym',
          'sym-lib-table': 'sym-lib-table', 'led_leaf.kicad_pro': 'fixture.kicad_pro'}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--repo', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    repo, out = a.repo.resolve(), a.out.resolve()
    if out == repo or repo in out.parents:
        print('refusing: --out must be outside the repository', file=sys.stderr); return 2
    if out.exists() and any(out.iterdir()):
        print('refusing: --out must be empty or absent', file=sys.stderr); return 2
    out.mkdir(parents=True, exist_ok=True)
    import pcbnew as p
    src = repo / SRC_DIR
    for s, d in COPIES.items():
        shutil.copyfile(src / s, out / d)
    (out / 'fp-lib-table').write_text(FP_LIB)
    b = p.LoadBoard(str(src / 'led_leaf.kicad_pcb'))
    bb = b.GetBoardEdgesBoundingBox()
    inset = p.FromMM(0.5)
    x0, y0, x1, y1 = bb.GetLeft() + inset, bb.GetTop() + inset, bb.GetRight() - inset, bb.GetBottom() - inset
    z = p.ZONE(b)
    z.SetLayer(p.F_Cu)
    z.SetNet(b.FindNet('GND'))
    z.SetZoneName('FIXTURE_GND_F')
    z.SetLocalClearance(p.FromMM(0.25))
    z.SetMinThickness(p.FromMM(0.2))
    z.SetPadConnection(p.ZONE_CONNECTION_THERMAL)
    z.SetIslandRemovalMode(p.ISLAND_REMOVAL_MODE_ALWAYS)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        ol.Append(x, y)
    b.Add(z)
    b.BuildConnectivity()
    p.ZONE_FILLER(b).Fill(b.Zones())
    p.SaveBoard(str(out / 'fixture.kicad_pcb'), b)
    for extra in out.glob('*.kicad_prl'):
        extra.unlink()
    prov = {
        'what': 'Native-gate infrastructure fixture: A5 LED leaf routing plus one filled GND zone. Not an A7 or A5 board result.',
        'generator': 'scripts/native_gate/make_fixture.py',
        'generator_sha256': sha(Path(__file__).resolve()),
        'kicad_build_version': p.GetBuildVersion(),
        'source_dir': SRC_DIR,
        'source_sha256': {n: sha(src / n) for n in sorted(list(COPIES) + ['led_leaf.kicad_pcb'])},
        'zone': {'name': 'FIXTURE_GND_F', 'net': 'GND', 'layer': 'F.Cu', 'outline_inset_mm': 0.5,
                 'clearance_mm': 0.25, 'min_thickness_mm': 0.2},
        'output_sha256': {f.name: sha(f) for f in sorted(out.iterdir()) if f.is_file()},
    }
    (out / 'provenance.json').write_text(json.dumps(prov, indent=1, sort_keys=True) + '\n')
    print(json.dumps(prov['output_sha256'], indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
