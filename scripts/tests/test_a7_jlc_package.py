"""The JLC package dry run must follow the frozen boards and JLC's dated rules, and never pass as a release."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('jlc', ROOT / 'scripts/a7_jlc_package.py')
J = importlib.util.module_from_spec(spec)
spec.loader.exec_module(J)


class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report, cls.files = J.generate()

    def board(self, name):
        return next(b for b in self.report['boards'] if b['board'] == name)

    def ids(self):
        return {b['id'] for b in self.report['blockers']}

    def test_never_released_while_the_order_gate_is_blocked(self):
        self.assertEqual(self.report['status'], 'DRY_RUN_NOT_RELEASED')
        self.assertEqual(self.report['order_eligibility'], 'BLOCKED')
        self.assertIn('order-gate-blocked', self.ids())

    def test_quantities_follow_the_owner_decision(self):
        self.assertEqual(self.report['modules'], 2)
        self.assertEqual([(b['board'], b['pcba_quantity']) for b in self.report['boards']], [('controller', 2), ('led_leaf', 4), ('power_adapter', 2)])

    def test_jlc_column_formats(self):
        for name in ('controller', 'led_leaf', 'power_adapter'):
            self.assertTrue(self.files[f'{name}_BOM_DRYRUN.csv'].startswith('Comment,Designator,Footprint,JLCPCB Part #\n'))
            self.assertTrue(self.files[f'{name}_CPL_DRYRUN.csv'].startswith('Designator,Mid X,Mid Y,Rotation,Layer\n'))

    def test_every_fitted_placement_is_in_the_cpl_once_and_test_pads_are_not(self):
        cpl = self.files['controller_CPL_DRYRUN.csv']
        refs = [line.split(',')[0] for line in cpl.splitlines()[1:]]
        self.assertEqual(len(refs), len(set(refs)))
        self.assertEqual(len(refs), 59)
        self.assertFalse(any(r.startswith('TP') for r in refs))
        self.assertEqual(sum(b['cpl_rows'] * b['per_module'] for b in self.report['boards']), 81)

    def test_tiers_follow_the_capability_table(self):
        self.assertEqual(self.board('controller')['pcba_tier']['tier'], 'STANDARD')
        self.assertEqual(self.board('led_leaf')['pcba_tier']['tier'], 'STANDARD')
        self.assertEqual(self.board('power_adapter')['pcba_tier']['tier'], 'ECONOMIC')
        for blocker in ('controller-below-pcba-minimum-size', 'led_leaf-below-pcba-minimum-size', 'power_adapter-below-pcba-minimum-size',
                        'controller-no-fiducials', 'led_leaf-no-fiducials', 'leaf-thickness-not-1.6', 'part-C221842-not-in-stock'):
            self.assertIn(blocker, self.ids())

    def test_part_routes_follow_stock(self):
        sw = next(l for l in self.report['parts'] if l['lcsc'] == 'C221842')
        self.assertNotEqual(sw['route'], 'JLC_STOCK')
        self.assertEqual(len(self.report['parts']), 30)

    def test_stock_shortfall_becomes_a_named_blocker(self):
        original = J.json.loads

        def low_stock(text, *a, **k):
            data = original(text, *a, **k)
            if isinstance(data, dict) and 'parts' in data and 'pages' in data:
                for p in data['parts']:
                    if p['lcsc'] == 'C5270180':
                        p['in_stock'] = 1
                        p['preorder_available'] = 0
            return data
        with patch.object(J.json, 'loads', side_effect=low_stock):
            report, _ = J.generate()
        self.assertIn('part-C5270180-not-in-stock', {b['id'] for b in report['blockers']})

    def test_changed_board_is_rejected(self):
        original = J.sha
        with patch.object(J, 'sha', side_effect=lambda p: '0' * 64 if str(p).endswith('controller.kicad_pcb') else original(p)):
            with self.assertRaisesRegex(ValueError, 'differs from the ledger'):
                J.generate()

    def test_cpl_comparison_detects_position_rotation_and_side(self):
        with tempfile.TemporaryDirectory() as d:
            k = Path(d) / 'k.csv'
            c = Path(d) / 'c.csv'
            k.write_text('Ref,Val,Package,PosX,PosY,Rot,Side\n"R1","1k","R0603",1.0,-2.0,90.0,bottom\n')
            c.write_text('Designator,Mid X,Mid Y,Rotation,Layer\nR1,1,-2,90,Bottom\n')
            self.assertEqual(J.compare_pos(k, c), [])
            for bad in ('R1,1.1,-2,90,Bottom', 'R1,1,-2,0,Bottom', 'R1,1,-2,90,Top'):
                c.write_text('Designator,Mid X,Mid Y,Rotation,Layer\n' + bad + '\n')
                self.assertTrue(J.compare_pos(k, c), bad)

    def test_committed_outputs_are_current(self):
        for name, text in self.files.items():
            self.assertEqual((ROOT / J.OUT / name).read_text(), text, name)
        self.assertEqual((ROOT / J.PAGE).read_text(), J.page(self.report))

    def test_export_refuses_a_directory_inside_the_repository(self):
        with self.assertRaises(SystemExit):
            J.export(ROOT / 'engineering')


if __name__ == '__main__':
    unittest.main()
