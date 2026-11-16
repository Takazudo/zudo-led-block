import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('a7_preview', Path(__file__).parents[1] / 'a7_preview.py')
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)

class PreviewIdentity(unittest.TestCase):
    def test_manifest_binds_every_real_node_and_dimensions(self):
        m = p.make_manifest()
        self.assertEqual([v['variant'] for v in m['variants']], ['3hp', '2hp', '3hp_pet'])
        self.assertEqual([v['width_mm'] for v in m['variants']], [14.9, 9.8, 14.9])
        self.assertEqual((m['height_mm'],m['pmma_mm'],m['depth_target_mm']), (128.5,2,30))
        for v in m['variants']:
            self.assertGreater(len(v['nodes']), 60)
            self.assertEqual(set(x['group'] for x in v['nodes'].values()), set(m['groups']))
        self.assertIn('setting_switch_HX_MSK13C02',m['variants'][0]['nodes'])
        p.generate(True)

    def test_source_mutation_is_rejected(self):
        from unittest.mock import patch
        with patch.object(p, 'digest', return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'Source changed'):
                p.make_manifest()

    def test_publication_is_bounded(self):
        paths=[x['path'] for x in p.publication_assets()]
        self.assertEqual(len(paths),len(set(paths)))
        self.assertEqual(len(paths),10)
        self.assertTrue(all(x.startswith('a7-preview/') and '..' not in x and 'vendor' not in x for x in paths))
