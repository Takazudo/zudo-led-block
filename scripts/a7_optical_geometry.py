#!/usr/bin/env python3
"""Export actual native Cu and residual-mask contours for optical display.

Use pinned KiCad Python. Mask is outline minus effective native openings,
including ordinary pad apertures. No optical property is measured here.
"""
import argparse
import hashlib
import json
from pathlib import Path


def polygons(poly):
    def ring(chain):
        return [[chain.CPoint(i).x / 1e6, chain.CPoint(i).y / 1e6]
                for i in range(chain.PointCount())]
    return [{'outer': ring(poly.COutline(i)),
             'holes': [ring(poly.CHole(i, j)) for j in range(poly.HoleCount(i))]}
            for i in range(poly.OutlineCount())]


def export(board_path, output):
    import pcbnew as p
    if not p.Version().startswith('10.0.8'):
        raise RuntimeError('Optical source export requires pinned KiCad 10.0.8')
    b = p.LoadBoard(str(board_path))
    outline = p.SHAPE_POLY_SET()
    if not b.GetBoardPolygonOutlines(outline):
        raise ValueError('Invalid native board outline')
    holes = p.SHAPE_POLY_SET()
    for footprint in b.GetFootprints():
        for pad in footprint.Pads():
            pad.TransformHoleToPolygon(holes, 0, 5000, p.ERROR_INSIDE)
    for track in b.GetTracks():
        if isinstance(track, p.PCB_VIA):
            track.GetEffectiveHoleShape().TransformToPolygon(holes, 5000, p.ERROR_INSIDE)
    layers = []
    for layer in list(b.GetEnabledLayers().CuStack()) + [p.F_Mask, p.B_Mask]:
        actual = p.SHAPE_POLY_SET()
        b.ConvertBrdLayerToPolygonalContours(layer, actual)
        if layer in (p.F_Mask, p.B_Mask):
            remaining = p.SHAPE_POLY_SET(outline)
            remaining.BooleanSubtract(actual)
            actual = remaining
        else:
            actual.BooleanIntersection(outline)
        actual.BooleanSubtract(holes)
        layers.append({'layer': b.GetLayerName(layer),
                       'material': 'mask' if layer in (p.F_Mask, p.B_Mask) else 'copper',
                       'polygons': polygons(actual)})
    result = {'schema_version': 1, 'native_version': p.Version(),
              'exporter_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'board_sha256': hashlib.sha256(board_path.read_bytes()).hexdigest(),
              'board_file': board_path.name, 'thickness_mm': b.GetDesignSettings().GetBoardThickness()/1e6,
              'units': 'mm', 'outline': polygons(outline), 'layers': layers,
              'status': 'Native geometry for display; FR4 optical properties unmeasured.'}
    output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--board', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    export(args.board, args.out)
