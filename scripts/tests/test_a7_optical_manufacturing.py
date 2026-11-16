"""Reject old PCB inputs and changed native dielectric construction before packaging."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

J, P, R, O = map(load, ['a7_jlc_package', 'a7_procurement', 'a7_readiness', 'a7_optical_pcb'])

class OpticalManufacturingTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads((ROOT / J.OPTICAL_FAB).read_text())
        self.facts = {'path': self.spec['led_leaf']['board'], 'thickness_mm': .8,
                      'copper_layers': ['F.Cu', 'B.Cu'], 'copper_finish': 'ENIG',
                      'stackup': J.parse_sexp(O.stackup_text('led_leaf'))}

    def test_current_leaf_and_approval_identity(self):
        self.assertEqual(P.BOARDS['led_leaf'][1], 'engineering/a7/verification/led_leaf/netlist.xml')
        self.assertEqual(P.BOARDS['led_leaf'][2], self.spec['led_leaf']['board'])
        self.assertEqual(R.IDENTITY_PATHS['led_leaf_board'], self.spec['led_leaf']['board'])
        self.assertEqual(R.IDENTITY_PATHS['optical_fabrication'], J.OPTICAL_FAB)

    def test_neither_pcba_nor_old_approval_is_inferred(self):
        result = J.optical_manufacturing('led_leaf', self.facts)
        self.assertIn('NOT_FACTORY_ACCEPTED', result['acceptance'])
        self.assertIn('not this revision', result['historical_approvals'])
        self.assertEqual(result['finished_thickness_tolerance_mm'], .1)

    def test_old_leaf_and_incomplete_construction_rejected(self):
        for key, value in [('path', 'engineering/a5/electronics/native/led_leaf/led_leaf.kicad_pcb'),
                           ('thickness_mm', .6), ('copper_layers', ['F.Cu']),
                           ('copper_finish', None), ('stackup', None)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                J.optical_manufacturing('led_leaf', dict(self.facts, **{key: value}))

    def test_native_dielectric_changes_cannot_hide_behind_point_eight_label(self):
        for field, value in [('thickness', '1.53'), ('material', 'PET'), ('epsilon_r', '1.0')]:
            facts = copy.deepcopy(self.facts)
            core = next(x for x in J.kids(facts['stackup'], 'layer') if x[1].startswith('dielectric'))
            J.kid(core, field)[1] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'stackup differs'):
                J.optical_manufacturing('led_leaf', facts)

    def test_controller_sourced_lamination(self):
        facts = dict(self.facts, path=self.spec['controller']['board'],
                     copper_layers=['F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu'],
                     stackup=J.parse_sexp(O.stackup_text('controller')))
        result = J.optical_manufacturing('controller', facts)
        self.assertEqual(result['construction_target']['stackup_name'], 'JLC04081H-3313')
        self.assertAlmostEqual(sum(x['thickness_mm'] for x in self.spec['controller']['stackup']), .7992)
        facts['stackup'] = J.parse_sexp(O.stackup_text('led_leaf'))
        with self.assertRaisesRegex(ValueError, 'stackup differs'):
            J.optical_manufacturing('controller', facts)

if __name__ == '__main__':
    unittest.main()
