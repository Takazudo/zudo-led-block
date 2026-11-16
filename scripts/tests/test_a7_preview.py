import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('a7_preview', Path(__file__).parents[1] / 'a7_preview.py')
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)

class PreviewIdentity(unittest.TestCase):
    def test_manifest_binds_every_real_node_and_dimensions(self):
        m = p.make_manifest()
        self.assertEqual([v['variant'] for v in m['variants']], ['3hp', '2hp'])
        self.assertEqual([v['width_mm'] for v in m['variants']], [14.9, 9.8])
        self.assertEqual((m['height_mm'],m['pmma_mm'],m['depth_target_mm']), (128.5,2,30))
        for v in m['variants']:
            self.assertGreater(len(v['nodes']), 60)
            self.assertEqual(len(v['optical_sources']), 2)
            self.assertTrue(any(n.endswith('_optical') for n in v['nodes']))
            self.assertIn('Opaque all-layer copper', v['optical_display'])
            self.assertEqual(set(x['group'] for x in v['nodes'].values()), set(m['groups']))
        self.assertIn('setting_switch_HX_MSK13C02',m['variants'][0]['nodes'])
        p.generate(True)

    def test_copper_and_mask_stay_opaque(self):
        import json
        import struct
        for entry in p.selection()['files']:
            if not entry['target'].endswith('.glb'):
                continue
            raw = (p.ROOT / entry['source']).read_bytes()
            length = struct.unpack_from('<I', raw, 12)[0]
            doc = json.loads(raw[20:20+length])
            optical_count = 0
            for node in doc['nodes']:
                if 'mesh' not in node:
                    continue
                name = node['name']
                if not (name.endswith('_optical') or name.endswith('_pcb_A7')):
                    continue
                for primitive in doc['meshes'][node['mesh']]['primitives']:
                    material = doc['materials'][primitive['material']]
                    alpha = material['pbrMetallicRoughness']['baseColorFactor'][3]
                    if name.endswith('_optical'):
                        optical_count += 1
                        self.assertEqual(alpha, 1, name)
                    else:
                        self.assertLess(alpha, 1, name)
            self.assertGreater(optical_count, 0)

    def test_source_mutation_is_rejected(self):
        from unittest.mock import patch
        with patch.object(p, 'digest', return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'Source changed'):
                p.make_manifest()

    def test_publication_is_bounded(self):
        paths=[x['path'] for x in p.publication_assets()]
        self.assertEqual(len(paths),len(set(paths)))
        self.assertEqual(len(paths),9)
        self.assertTrue(all(x.startswith('a7-preview/') and '..' not in x and 'vendor' not in x for x in paths))
