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

    def test_bites_lie_in_a_tab_and_outside_every_board(self):
        for n, lay in self.lay.items():
            r = P.BITE_D_MM / 2
            for x, y in lay['mouse_bites']['centres_mm']:
                self.assertTrue(any(t[0] - 1e-6 <= x <= t[2] + 1e-6 and t[1] - 1e-6 <= y <= t[3] + 1e-6 for t in (q['rect_mm'] for q in lay['tabs'])), (n, x, y))
                for c in lay['copies']:
                    x0, y0, x1, y1 = c['outline_mm']
                    self.assertFalse(x0 - r + 1e-6 < x < x1 + r - 1e-6 and y0 - r + 1e-6 < y < y1 + r - 1e-6, (n, x, y))

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
            g.write_text('T1C0.800\nT1\nX0.9Y-36.2G85X0.9Y-35.4\n')
            self.assertEqual(P.drill_holes(g), [(True, 0.8, 0.9, -36.2, 0.9, -35.4)])

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
        self.assertNotIn('まだ作っていない', text)
        self.assertNotIn('まだ作っていません', text)

    def test_receipt_covers_gerbers_and_drills_for_every_board(self):
        r = json.loads((ROOT / P.OUT / 'build-receipt.json').read_text())
        self.assertIn('NOT order files', r['what'])
        self.assertEqual(r['drc_waived'], {'controller': {}, 'led_leaf': {}, 'power_adapter': {'npth_inside_courtyard': 22}})
        for n in BOARDS:
            names = r['files'][n]
            for layer in ('F_Cu.gtl', 'B_Cu.gbl', 'Edge_Cuts.gm1', 'PTH.drl', 'NPTH.drl'):
                self.assertIn(f'{n}-panel-{layer}', names)
        self.assertIn('controller-panel-In1_Cu.g1', r['files']['controller'])



class VerifyNegativeControls(unittest.TestCase):
    """verify() must fail on each kind of panel defect; one consistent synthetic panel passes."""
    LAY = {'board': 'x', 'copies': [{'copy': 1, 'suffix': '', 'offset_mm': [10.0, 5.0]}, {'copy': 2, 'suffix': '_2', 'offset_mm': [30.0, 5.0]}],
           'mouse_bites': {'diameter_mm': 0.6, 'centres_mm': [[12.0, 4.7]]}, 'tooling_holes': {'diameter_mm': 2.0, 'centres_mm': [[3.5, 2.5]]},
           'fiducials': {'diameter_mm': 1.0, 'sides': ['F'], 'centres_mm': [[20.0, 3.85]]}, 'drc_waivers': {}}

    def fixture(self, d, mutate=None):
        items = {'pads': [['R1', '1', 'GND', 1000, 2000]], 'tracks': [['GND', 'F.Cu', 0, 0, 1000, 0, 200]]}
        pan = {'1': json.loads(json.dumps(items)), '2': json.loads(json.dumps(items))}
        check = {'outline': [{'copy': 1, 'xor_area_mm2': 0.0}, {'copy': 2, 'xor_area_mm2': 0.0}],
                 'features': [['MOUSEBITE', 'F', 12.0, 4.7, 0.6], ['TOOLING', 'F', 3.5, 2.5, 2.0], ['FIDUCIAL', 'F', 20.0, 3.85, 1.0]]}
        src_drl = 'T1C0.300\nT2C0.800\nT1\nX1Y-2\nT2\nX1Y-3G85X1Y-4\n'
        pan_drl = 'T1C0.300\nT2C0.800\nT1\nX11Y-7\nX31Y-7\nT2\nX11Y-8G85X11Y-9\nX31Y-8G85X31Y-9\n'
        npth = 'T1C0.600\nT2C2.000\nT1\nX12Y-4.7\nT2\nX3.5Y-2.5\n'
        drc_src, drc_pan = {'violations': [{'type': 'lib_footprint_issues'}]}, {'violations': [{'type': 'lib_footprint_issues'}] * 2}
        pos = 'Ref,Val,Package,PosX,PosY,Rot,Side\n"R1",a,b,11,-7,90,top\n"R1_2",a,b,31,-7,90,top\n'
        cpl = 'Designator,Mid X,Mid Y,Rotation,Layer\nR1,11,-7,90,Top\nR1_2,31,-7,90,Top\n'
        parts = {'pan': pan, 'check': check, 'pan_drl': pan_drl, 'npth': npth, 'drc_pan': drc_pan, 'pos': pos}
        if mutate:
            mutate(parts)
        (d / 'src/drill').mkdir(parents=True)
        (d / 'panel/drill').mkdir(parents=True)
        (d / 'src-items.json').write_text(json.dumps({'1': items}))
        (d / 'panel-items.json').write_text(json.dumps(parts['pan']))
        (d / 'panel-items.json.panel-check.json').write_text(json.dumps(parts['check']))
        (d / 'src/drill/s-PTH.drl').write_text(src_drl)
        (d / 'panel/drill/p-PTH.drl').write_text(parts['pan_drl'])
        (d / 'panel/drill/p-NPTH.drl').write_text(parts['npth'])
        (d / 'src-drc.json').write_text(json.dumps(drc_src))
        (d / 'panel-drc.json').write_text(json.dumps(parts['drc_pan']))
        (d / 'panel-pos.csv').write_text(parts['pos'])
        return P.verify(self.LAY, d, {'x-panel_CPL_DRYRUN.csv': cpl})['failures']

    def run_case(self, mutate=None):
        with tempfile.TemporaryDirectory() as t:
            return self.fixture(Path(t), mutate)

    def test_consistent_panel_passes(self):
        self.assertEqual(self.run_case(), [])

    def test_each_defect_fails(self):
        cases = {
            'shifted pad': lambda q: q['pan']['2']['pads'][0].__setitem__(3, 1001),
            'copy-2 net left on copy 1': lambda q: q['pan']['2']['tracks'][0].__setitem__(0, '!unsuffixed:GND'),
            'outline': lambda q: q['check']['outline'][1].__setitem__('xor_area_mm2', 0.01),
            'missing slot': lambda q: q.__setitem__('pan_drl', q['pan_drl'].replace('X31Y-8G85X31Y-9\n', '')),
            'moved slot end': lambda q: q.__setitem__('pan_drl', q['pan_drl'].replace('G85X31Y-9', 'G85X31Y-9.5')),
            'missing tooling hole': lambda q: q.__setitem__('npth', q['npth'].replace('X3.5Y-2.5\n', '')),
            'moved fiducial': lambda q: q['check']['features'][2].__setitem__(2, 20.5),
            'added DRC violation': lambda q: q['drc_pan']['violations'].append({'type': 'clearance'}),
            'lost DRC violation': lambda q: q['drc_pan']['violations'].pop(),
            'CPL off by 0.1 mm': lambda q: q.__setitem__('pos', q['pos'].replace('31,-7', '31.1,-7')),
            'item outside every copy': lambda q: q['pan'].__setitem__('3', {'tracks': []}),
        }
        for name, m in cases.items():
            with self.subTest(name):
                self.assertTrue(self.run_case(m), name)

    def test_unparsed_drill_line_is_an_error(self):
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / 'a-PTH.drl'
            f.write_text('T1C0.3\nT1\nX1Y1G00X2Y2\n')
            with self.assertRaises(ValueError):
                P.drill_holes(f)


if __name__ == '__main__':
    unittest.main()
