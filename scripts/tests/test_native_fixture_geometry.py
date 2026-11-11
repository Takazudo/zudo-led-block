"""Fixture geometry consumer: identity, completeness, face and transform conventions.

Synthetic geometry is derived from the committed canonical placement; it never stands in
for native evidence (only --from-zip on a VALID_PASS artifact writes the record).
"""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location('a7_fixture_geometry', Path(__file__).resolve().parents[1] / 'a7_fixture_geometry.py')
g = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(g)

PLACEMENT = json.loads(g.PLACEMENT.read_text())
BOARD_SHA = PLACEMENT['board_sha256']
IMAGE = json.loads((g.ROOT / g.art.PROFILE).read_text())['image']


def synthetic():
    fps = []
    for c in PLACEMENT['components']:
        pads = []
        for num, pd in sorted(c['pads'].items()):
            d = [pd['at_mm'][0] - c['at_mm'][0], pd['at_mm'][1] - c['at_mm'][1]]
            rel = [round(v, 6) for v in g.rotate(d, -c['angle_deg'])]
            x, y = pd['at_mm']
            pads.append({'number': num, 'net': pd['net'], 'at_mm': pd['at_mm'], 'fp_relative_mm': rel, 'shape': 'RECTANGLE',
                         'size_mm': [0.6, 0.6], 'bbox_mm': [x - 0.3, y - 0.3, x + 0.3, y + 0.3],
                         'rotation_deg': c['angle_deg'], 'layers': [g.CU[c['side']]],
                         'attribute': 'SMD', 'drill_mm': None})
        fps.append({'ref': c['ref'], 'fpid': c['fpid'], 'side': c['side'], 'at_mm': c['at_mm'], 'rotation_deg': c['angle_deg'],
                    'pads': pads, 'courtyard_bbox_mm': {'F': None, 'B': None, c['side']: [0, 0, 1, 1]},
                    'footprint_bbox_mm': [0, 0, 1, 1], 'models': [], 'body_height_mm': None})
    return {'schema': g.SCHEMA, 'board_sha256': BOARD_SHA, 'units': 'mm', 'axes': {'x': 'right', 'y': 'down'},
            'kicad_build_version': '10.0.8', 'footprints': fps, 'extraction_errors': []}


def fp(fx, ref):
    return next(f for f in fx['footprints'] if f['ref'] == ref)


class FixtureGeometryTests(unittest.TestCase):
    def check(self, fx, board=BOARD_SHA, placement=PLACEMENT):
        return g.check_geometry(fx, board, placement)

    def test_consistent_geometry_passes(self):
        errors, unknowns = self.check(synthetic())
        self.assertEqual(errors, [])
        self.assertEqual(unknowns, [])

    def test_representative_rotated_and_back_side_footprints_exist(self):
        rots = {c['angle_deg'] % 360 for c in PLACEMENT['components']}
        self.assertTrue(rots - {0.0}, 'need rotated footprints to exercise the transform')
        self.assertTrue(any(c['side'] == 'B' for c in PLACEMENT['components']))

    def test_wrong_board_or_stale_placement_rejected(self):
        self.assertTrue(self.check(synthetic(), board='a' * 64)[0])
        stale = dict(PLACEMENT, board_sha256='a' * 64)
        self.assertTrue(self.check(synthetic(), placement=stale)[0])

    def test_missing_required_fields_rejected(self):
        for field in ('shape', 'size_mm', 'bbox_mm', 'layers', 'fp_relative_mm', 'rotation_deg'):
            fx = synthetic()
            del fx['footprints'][0]['pads'][0][field]
            with self.subTest(field=field):
                self.assertTrue(self.check(fx)[0])
        fx = synthetic(); fx['footprints'][0]['pads'][0]['shape'] = 'UNKNOWN_9'
        self.assertTrue(self.check(fx)[0])
        fx = synthetic(); fx['footprints'].pop()
        self.assertTrue(self.check(fx)[0])

    def test_pad_box_must_contain_pad_and_layers_must_exist(self):
        fx = synthetic(); pd = fx['footprints'][0]['pads'][0]; pd['bbox_mm'] = [100, 100, 101, 101]
        self.assertTrue(self.check(fx)[0])
        fx = synthetic(); fx['footprints'][0]['pads'][0]['layers'].append('In30.Cu')
        self.assertTrue(any('copper layers' in e for e in self.check(fx)[0]))

    def test_extractor_errors_or_error_record_rejected(self):
        fx = synthetic(); fx['extraction_errors'] = ['C1.1 shape/size: TypeError']
        self.assertTrue(self.check(fx)[0])
        self.assertTrue(self.check({'schema': g.SCHEMA, 'error': 'RuntimeError()'})[0])

    def test_wrong_face_rejected(self):
        b = next(c['ref'] for c in PLACEMENT['components'] if c['side'] == 'B')
        fx = synthetic(); fp(fx, b)['side'] = 'F'
        self.assertTrue(self.check(fx)[0])
        fx = synthetic()
        for pd in fp(fx, b)['pads']:
            pd['layers'] = ['F.Cu']
        self.assertTrue(any('face' in e for e in self.check(fx)[0]))

    def test_mirrored_or_misrotated_transform_rejected(self):
        ref = next(c['ref'] for c in PLACEMENT['components'] if c['angle_deg'] % 180 and len(c['pads']) > 1)
        fx = synthetic()
        for pd in fp(fx, ref)['pads']:
            pd['fp_relative_mm'][0] = -pd['fp_relative_mm'][0]
        self.assertTrue(any('transform' in e for e in self.check(fx)[0]))
        fx = synthetic(); fp(fx, ref)['rotation_deg'] += 90
        self.assertTrue(self.check(fx)[0])

    def test_pad_moved_or_renetted_rejected(self):
        fx = synthetic(); pd = fx['footprints'][0]['pads'][0]
        pd['at_mm'] = [pd['at_mm'][0] + 0.01, pd['at_mm'][1]]
        self.assertTrue(self.check(fx)[0])
        fx = synthetic(); fx['footprints'][0]['pads'][0]['net'] = '/WRONG'
        self.assertTrue(self.check(fx)[0])

    def test_absent_courtyard_is_unknown_not_invented(self):
        fx = synthetic(); f = fx['footprints'][0]; f['courtyard_bbox_mm'] = {'F': None, 'B': None}; f['footprint_bbox_mm'] = None
        errors, unknowns = self.check(fx)
        self.assertEqual(errors, [])
        self.assertEqual(len(unknowns), 2)

    def test_body_height_must_not_be_asserted(self):
        fx = synthetic(); fx['footprints'][0]['body_height_mm'] = 1.2
        self.assertTrue(self.check(fx)[0])

    def test_record_binding_detects_edited_geometry(self):
        fx = synthetic()
        counts = {f['ref']: len(f['pads']) for f in fx['footprints']}  # synthetic omits unnumbered/mechanical pads
        patcher = mock.patch.object(g, 'board_pad_counts', return_value=counts)
        patcher.start(); self.addCleanup(patcher.stop)
        member = (json.dumps(fx, indent=1, sort_keys=True) + '\n').encode()
        rec = {'schema': g.RECORD_SCHEMA, 'status': 'NATIVE_GEOMETRY_VALIDATED', 'board_sha256': BOARD_SHA,
               'placement_sha256': g.sha(g.PLACEMENT.read_bytes()), 'unknowns': [], 'geometry': fx,
               'provenance': {'members_sha256': {g.MEMBER: g.sha(member)}, 'image': IMAGE}}
        self.assertEqual(g.check_record(rec), [])
        edited = copy.deepcopy(rec); edited['geometry']['footprints'][0]['pads'][0]['size_mm'] = [9, 9]
        self.assertTrue(g.check_record(edited))
        stale = dict(rec, board_sha256='a' * 64)
        self.assertTrue(g.check_record(stale))
        other = copy.deepcopy(rec); other['provenance']['image'] = 'kicad/kicad:9.0.9'
        self.assertTrue(g.check_record(other))

    def test_malformed_record_geometry_is_rejected_not_crashing(self):
        fx = synthetic(); fx['footprints'][0]['pads'][0]['number'] = ['1']
        self.assertTrue(self.check(fx)[0])
        fx = synthetic(); fx['footprints'][0]['pads'][0]['layers'] = [3]
        self.assertTrue(self.check(fx)[0])

    def test_pad_count_must_match_pcb(self):
        fx = synthetic()
        counts = {f['ref']: len(f['pads']) for f in fx['footprints']}
        self.assertEqual(g.check_geometry(fx, BOARD_SHA, PLACEMENT, counts)[0], [])
        extra = copy.deepcopy(fx['footprints'][0]['pads'][0]); fx['footprints'][0]['pads'].append(extra)
        self.assertTrue(any('pad count' in e for e in g.check_geometry(fx, BOARD_SHA, PLACEMENT, counts)[0]))
        real = g.board_pad_counts(g.BOARD.read_text())
        self.assertEqual(set(real), {c['ref'] for c in PLACEMENT['components']})

    def test_box_size_attribute_and_courtyard_shape_checked(self):
        fx = synthetic(); fx['footprints'][0]['pads'][0]['size_mm'] = [9, 9]
        self.assertTrue(any('disagrees with pad size' in e for e in self.check(fx)[0]))
        fx = synthetic(); fx['footprints'][0]['pads'][0]['attribute'] = None
        self.assertTrue(any('attribute' in e for e in self.check(fx)[0]))
        fx = synthetic(); fx['footprints'][0]['courtyard_bbox_mm'] = {'F': 'x', 'B': 'x'}
        self.assertTrue(any('courtyard boxes malformed' in e for e in self.check(fx)[0]))
        fx = synthetic(); fx['footprints'][0]['footprint_bbox_mm'] = [1, 1, 0, 0]
        self.assertTrue(any('footprint box malformed' in e for e in self.check(fx)[0]))


if __name__ == '__main__':
    unittest.main()
