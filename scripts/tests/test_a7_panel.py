"""Repo panels must follow JLC's published panel rules, keep every frozen board intact and stay a prepared route."""
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('panel', ROOT / 'scripts/a7_panel.py')
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)
BOARDS = ('controller', 'led_leaf', 'power_adapter')


def rows(text):
    return list(csv.DictReader(text.splitlines()))


class PanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = P.plan()
        cls.lay = {n: json.loads(cls.files[f'{n}-panel.json']) for n in BOARDS}

    def test_committed_files_are_current(self):
        for name, text in self.files.items():
            self.assertEqual((ROOT / P.OUT / name).read_text(), text, name)

    def test_panel_sizes_and_copies_as_proposed(self):
        got = {n: (self.lay[n]['panel_mm'], len(self.lay[n]['copies'])) for n in BOARDS}
        self.assertEqual(got, {'controller': ([70, 76.9], 1), 'led_leaf': ([70, 96.5], 2), 'power_adapter': ([22.8, 44.0], 1)})

    def test_mouse_bites_follow_jlc_rules(self):
        self.assertTrue(0.5 <= P.BITE_D_MM <= 0.8)
        self.assertTrue(0.2 <= P.BITE_GAP_MM <= 0.3)
        b = P.bites(10)
        self.assertTrue(all(abs((y - x) - (P.BITE_D_MM + P.BITE_GAP_MM)) < 1e-9 for x, y in zip(b, b[1:])))
        self.assertLessEqual(b[-1] - b[0] + P.BITE_D_MM, P.TAB_MM)
        self.assertAlmostEqual(b[0] + b[-1], 0)

    def test_rails_fiducials_and_tooling_holes(self):
        for n, lay in self.lay.items():
            W, H = lay['panel_mm']
            self.assertEqual(lay['rules']['rail_mm'], 5.0)
            self.assertEqual(lay['tooling_holes']['diameter_mm'], 2.0)
            self.assertEqual(lay['fiducials']['diameter_mm'], 1.0)
            for x, y in lay['fiducials']['centres_mm']:
                self.assertIn(round(min(y, H - y), 3), (3.85,), n)
            for x, y in lay['tooling_holes']['centres_mm'] + lay['fiducials']['centres_mm']:
                self.assertTrue(min(y, H - y) < 5 and 0 < x < W, (n, x, y))
        self.assertEqual(self.lay['controller']['fiducials']['sides'], ['B', 'F'])
        self.assertEqual(self.lay['led_leaf']['fiducials']['sides'], ['F'])

    def test_boards_sit_inside_the_panel_at_least_2_mm_from_rails_and_each_other(self):
        for n, lay in self.lay.items():
            W, H = lay['panel_mm']
            outs = [c['outline_mm'] for c in lay['copies']]
            for x0, y0, x1, y1 in outs:
                self.assertGreaterEqual(min(x0, y0, W - x1, H - y1), 5 + 2 - 1e-9, n)
            for a, b in zip(outs, outs[1:]):
                self.assertGreaterEqual(b[0] - a[2], 2 - 1e-9, n)

    def test_every_copy_has_at_least_two_tabs_of_jlc_width(self):
        for n, lay in self.lay.items():
            self.assertTrue(all(v >= 2 for v in lay['tabs_per_copy'].values()), n)
            for t in lay['tabs']:
                x0, y0, x1, y1 = t['rect_mm']
                along = (x1 - x0) if t['edge'] in ('top', 'bottom') else (y1 - y0)
                self.assertAlmostEqual(along, P.TAB_MM, places=3)

    def test_tabs_keep_clear_of_courtyards_unless_waived(self):
        self.assertEqual(self.lay['controller']['drc_waivers'], {})
        self.assertEqual(self.lay['led_leaf']['drc_waivers'], {})
        self.assertEqual(list(self.lay['power_adapter']['drc_waivers']), ['npth_inside_courtyard'])

    def test_place_tabs_avoids_blocked_spans(self):
        self.assertEqual(P.free_spans(10, [(2, 4), (3, 6)]), [(0.0, 2), (6, 10)])
        tabs = P.place_tabs(30, [(10, 20)], [0.5])
        self.assertEqual(len(tabs), 1)
        self.assertTrue(tabs[0] + P.TAB_MM / 2 <= 10 or tabs[0] - P.TAB_MM / 2 >= 20)
        self.assertEqual(P.place_tabs(8, [(1, 7)], [0.5]), [])

    def test_cpl_is_the_single_board_cpl_shifted_per_copy(self):
        for n, lay in self.lay.items():
            single = rows((ROOT / f'engineering/a7/jlc-package/{n}_CPL_DRYRUN.csv').read_text())
            panel = {r['Designator']: r for r in rows(self.files[f'{n}-panel_CPL_DRYRUN.csv'])}
            self.assertEqual(len(panel), len(single) * len(lay['copies']), n)
            for c in lay['copies']:
                ox, oy = c['outline_mm'][:2]
                for r in single:
                    p = panel[r['Designator'] + c['suffix']]
                    self.assertAlmostEqual(float(p['Mid X']), float(r['Mid X']) + ox, places=3)
                    self.assertAlmostEqual(float(p['Mid Y']), float(r['Mid Y']) - oy, places=3)
                    self.assertEqual((p['Rotation'], p['Layer']), (r['Rotation'], r['Layer']))

    def test_bom_lists_every_panel_designator_once(self):
        for n in BOARDS:
            refs = [d for r in rows(self.files[f'{n}-panel_BOM_DRYRUN.csv']) for d in r['Designator'].split(',')]
            self.assertEqual(sorted(refs), sorted(r['Designator'] for r in rows(self.files[f'{n}-panel_CPL_DRYRUN.csv'])))
            self.assertEqual(len(refs), len(set(refs)))

    def test_layout_records_the_frozen_source(self):
        for n, lay in self.lay.items():
            self.assertTrue((ROOT / lay['pcb']).is_file())
            self.assertEqual(len(lay['pcb_sha256']), 64)

    def test_excellon_parser(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 'x-NPTH.drl'
            f.write_text('M48\nMETRIC\nT1C0.600\nT2C2.000\n%\nG90\nT1\nX1.5Y-2.25\nX2.35Y-2.25\nT2\nX3.5Y-2.5\nM30\n')
            self.assertEqual(P.drill_holes(f), [(False, 0.6, 1.5, -2.25), (False, 0.6, 2.35, -2.25), (False, 2.0, 3.5, -2.5)])
            g = Path(d) / 'x-PTH.drl'
            g.write_text('T1C0.300\nT1\nX1Y1\n')
            self.assertEqual(P.drill_holes(g), [(True, 0.3, 1.0, 1.0)])

    def test_build_refuses_output_inside_the_repository(self):
        with self.assertRaises(SystemExit):
            P.build(ROOT / 'engineering/a7/jlc-package/panels/tmp-out')
        self.assertFalse((ROOT / 'engineering/a7/jlc-package/panels/tmp-out').exists())

    def test_page_shows_both_routes_and_keeps_the_decision_open(self):
        text = (ROOT / 'doc/src/content/docs/project/jlc-order-package.mdx').read_text()
        for n in BOARDS:
            self.assertIn(f'{n}-gerbers-DRYRUN.zip', text)
            self.assertIn(f'{n}-panel-gerbers-DRYRUN.zip', text)
        self.assertIn('リポジトリで面付け（準備済み・未リリース）', text)
        self.assertIn('`assembly:panel-route`', text)

    def test_receipt_covers_gerbers_and_drills_for_every_board(self):
        r = json.loads((ROOT / P.OUT / 'build-receipt.json').read_text())
        self.assertIn('NOT order files', r['what'])
        for n in BOARDS:
            names = r['files'][n]
            for layer in ('F_Cu.gtl', 'B_Cu.gbl', 'Edge_Cuts.gm1', 'PTH.drl', 'NPTH.drl'):
                self.assertIn(f'{n}-panel-{layer}', names)
        self.assertIn('controller-panel-In1_Cu.g1', r['files']['controller'])


if __name__ == '__main__':
    unittest.main()
