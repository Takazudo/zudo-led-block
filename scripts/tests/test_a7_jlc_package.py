"""The JLC package dry run must follow the frozen boards and JLC's dated rules, and never pass as a release."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

PAD = '(pad "{n}" smd rect (at {x} {y} {a}) (size {w} {h}) (layers "F.Cu"))'

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
        for blocker in ('controller-repo-panel-acceptance', 'led_leaf-repo-panel-acceptance', 'power_adapter-repo-panel-acceptance',
                        'pcba-quantity-unit-with-panel-not-sourced'):
            self.assertIn(blocker, self.ids())
        # SW1 is now the in-stock HX MSK13C02, so no part is short at the order quantity
        self.assertFalse([i for i in self.ids() if i.startswith('part-')])
        # 0.6 mm is a JLC FR-4 option, so the leaf thickness is a note, not a blocker
        self.assertFalse(any('thickness' in i for i in self.ids()))
        self.assertIn('C52917434', ' '.join(self.board('led_leaf')['pcba_tier']['reasons']))

    def test_assembly_route_per_board(self):
        routes = {b['board']: b['assembly_route'] for b in self.report['boards']}
        self.assertEqual({n: r['route'] for n, r in routes.items()},
                         {'controller': 'PANEL_BY_JLCPCB_TO_CONFIRM', 'led_leaf': 'PANEL_BY_JLCPCB_TO_CONFIRM', 'power_adapter': 'PANEL_BY_JLCPCB_TO_CONFIRM'})
        self.assertEqual([q['id'] for q in routes['led_leaf']['open_questions']], ['outline'])
        self.assertEqual([q['id'] for q in routes['controller']['open_questions']], ['overhang'])
        self.assertEqual([q['id'] for q in routes['power_adapter']['open_questions']], ['economic-panel-separation'])
        # the adapter misses Economic single-board assembly on size alone
        self.assertEqual([c['criterion'] for c in routes['power_adapter']['economic_checks'] if not c['ok']], ['single board 10 × 10 mm or larger'])
        for r in routes.values():
            self.assertFalse(r['economic_single_board'])
            p = r['panel']
            self.assertTrue(p['within_250_mm'])
            self.assertGreaterEqual(min(p['size_without_rails_mm']), p['panel_minimum_mm'])
        self.assertEqual(self.board('led_leaf')['thickness_mm'], 0.6)
        self.assertIn('owner chose repo panels', ' '.join(b['text'] for b in self.report['blockers'] if b['id'] == 'controller-repo-panel-acceptance'))
        self.assertEqual(self.report['panel_route']['answer'], 'repo-panels')
        # while the owner's route is not recorded, each board carries the open route question instead
        with patch.object(J, 'panel_decision', return_value=None):
            report, _ = J.generate()
        ids = {b['id'] for b in report['blockers']}
        self.assertIn('controller-panel-route', ids)
        self.assertNotIn('controller-repo-panel-acceptance', ids)
        self.assertIn('Panel by JLCPCB', ' '.join(b['text'] for b in report['blockers'] if b['id'] == 'controller-panel-route'))

    def test_panel_comparison_counts_boards_and_parts(self):
        c = self.report['panel_comparison']
        self.assertEqual({n: (v['needed'], v['jlc_panel'], v['repo_panel'], v['recommended']) for n, v in c['boards'].items()},
                         {'controller': (2, 20, 2, 'REPO_PANEL'), 'led_leaf': (4, 16, 4, 'REPO_PANEL'), 'power_adapter': (2, 4, 2, 'REPO_PANEL')})
        sw = next(x for x in c['parts'] if x['lcsc'] == 'C5149819')
        self.assertEqual((sw['needed'], sw['jlc_panel'], sw['repo_panel']), (2, 20, 2))
        # the repo panel never asks for more parts than the 2 units need
        self.assertTrue(all(x['repo_panel'] == x['needed'] for x in c['parts']))

    def test_repo_panel_clears_overhanging_parts_and_meets_the_panel_minimum(self):
        jacks = {o['ref']: o for o in self.board('controller')['overhangs']}
        self.assertAlmostEqual(jacks['J1']['left'], 4.45)
        for name in ('controller', 'led_leaf', 'power_adapter'):
            rp = self.board(name)['repo_panel']
            self.assertGreaterEqual(min(rp['panel_mm']), rp['panel_minimum_mm'])
            self.assertTrue(rp['within_250_mm'])
        self.assertGreaterEqual(self.board('controller')['repo_panel']['edge_gap_mm']['left'], 4.45 + J.OVERHANG_MARGIN_MM)
        self.assertIn('carrier', ' '.join(self.board('led_leaf')['repo_panel']['notes']))

    def test_part_routes_follow_stock(self):
        self.assertNotIn('C221842', [l['lcsc'] for l in self.report['parts']])
        sw = next(l for l in self.report['parts'] if l['lcsc'] == 'C5149819')
        self.assertEqual(sw['route'], 'JLC_STOCK')
        sources = json.loads((ROOT / J.SOURCES).read_text())
        next(p for p in sources['parts'] if p['lcsc'] == 'C5149819').update(in_stock=0, preorder_available=0)
        report, _ = J.generate(sources=sources)
        self.assertNotEqual(next(l for l in report['parts'] if l['lcsc'] == 'C5149819')['route'], 'JLC_STOCK')
        self.assertEqual(len(self.report['parts']), 30)

    def test_stock_shortfall_becomes_a_named_blocker(self):
        sources = json.loads((ROOT / J.SOURCES).read_text())
        part = next(p for p in sources['parts'] if p['lcsc'] == 'C5270180')
        part.update(in_stock=1, preorder_available=0)
        report, _ = J.generate(sources=sources)
        self.assertIn('part-C5270180-not-in-stock', {b['id'] for b in report['blockers']})

    def test_a_part_without_a_recorded_pcba_type_is_refused(self):
        sources = json.loads((ROOT / J.SOURCES).read_text())
        del next(p for p in sources['parts'] if p['lcsc'] == 'C5665')['pcba_type']
        with self.assertRaisesRegex(ValueError, 'no recorded JLC PCBA type'):
            J.generate(sources=sources)

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

    def test_sourced_minimum_needs_a_quote_from_the_receipt(self):
        basis = copy.deepcopy(json.loads((ROOT / J.LEDGER).read_text())['order_plan']['pcba_minimum_boards'])
        cap = next(p for p in json.loads((ROOT / J.SOURCES).read_text())['pages'] if p['id'] == 'jlc-pcba-capabilities')
        J.check_pcba_basis(basis, cap)
        for quote in ('', '  ', None, 'Order Volume 1 - 50 pcs'):
            bad = copy.deepcopy(basis)
            bad['source']['quote'] = quote
            with self.assertRaisesRegex(ValueError, 'quote is empty or not in'):
                J.check_pcba_basis(bad, cap)
        # an owner-reported minimum has no source to check, and must not trip the quote guard
        J.check_pcba_basis({'status': 'OWNER_REPORTED', 'source': None}, cap)

    def test_export_refuses_a_directory_inside_the_repository(self):
        with self.assertRaises(SystemExit):
            J.export(ROOT / 'engineering')


def synthetic_board(footprints, thickness=1.6, extra=''):
    edge = ''.join(f'(gr_line (start {a}) (end {b}) (layer "Edge.Cuts"))' for a, b in (('0 0', '20 0'), ('20 0', '20 10'), ('20 10', '0 10'), ('0 10', '0 0')))
    return (f'(kicad_pcb (general (thickness {thickness})) (layers (0 "F.Cu" signal) (31 "B.Cu" signal)) (setup (pcbplotparams (useauxorigin no)))'
            f'{edge}{"".join(footprints)}{extra})')


def footprint(ref, name, at, pads, layer='F.Cu'):
    return f'(footprint "{name}" (layer "{layer}") (at {at}) (property "Reference" "{ref}") (property "Value" "v") {"".join(pads)})'


class SyntheticBoardTests(unittest.TestCase):
    def facts(self, text, **kw):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'b.kicad_pcb'
            path.write_text(synthetic_board(text, **kw))
            with patch.object(J, 'ROOT', Path(d)):
                return J.board_facts('b.kicad_pcb')

    def centre(self, f):
        return ((min(p[0] for p in f['pads']) + max(p[2] for p in f['pads'])) / 2, (min(p[1] for p in f['pads']) + max(p[3] for p in f['pads'])) / 2)

    def test_centroid_of_an_off_centre_anchor_follows_the_pads_under_rotation_and_side(self):
        # two 1 x 2 mm pads at x = 1 and x = 3 in the footprint frame: the pad centre is (2, 0) from the anchor
        for at, layer in (('5 5 0', 'F.Cu'), ('5 5 90', 'F.Cu'), ('5 5 180', 'B.Cu'), ('5 5 270', 'B.Cu')):
            angle = float(at.split()[2])
            pads = [PAD.format(n=n, x=x, y=0, a=angle, w=1, h=2) for n, x in ((1, 1), (2, 3))]
            f = self.facts([footprint('U1', 'lib:X', at, pads, layer)])['footprints'][0]
            cx, cy = self.centre(f)
            self.assertAlmostEqual(cx, 2.0)
            self.assertAlmostEqual(cy, 0.0)
            # the pad box keeps the 1 x 2 mm pad unrotated in the footprint frame whatever the footprint angle
            self.assertAlmostEqual(f['pads'][0][2] - f['pads'][0][0], 1.0)
            self.assertAlmostEqual(f['pads'][0][3] - f['pads'][0][1], 2.0)
            self.assertEqual(f['layer'], layer)

    def test_a_pad_turned_inside_its_footprint_swaps_its_box(self):
        f = self.facts([footprint('R1', 'lib:R', '0 0 90', [PAD.format(n=1, x=0, y=0, a=180, w=1, h=2)])])['footprints'][0]
        self.assertAlmostEqual(f['pads'][0][2] - f['pads'][0][0], 2.0)
        self.assertAlmostEqual(f['pads'][0][3] - f['pads'][0][1], 1.0)

    def tier(self, fps, sides=('Top',), thickness=1.6, layers=2, quantity=2, types=None):
        facts = self.facts(fps, thickness=thickness)
        fitted = {f['ref']: {'lcsc': 'C1', 'mount': 'SMD'} for f in facts['footprints']}
        parts = {'C1': {'pcba_type': types or 'Economic and Standard'}}
        return J.pcba_tier(facts, list(sides), layers, fitted, parts, quantity), facts

    def route(self, tier, facts):
        return J.assembly_route({'pcba_tier': tier, 'outline_mm': facts['outline_mm'], 'overhangs': []}, facts)

    def test_tier_criteria(self):
        ok = [footprint('U1', 'lib:SOT-23-6', '5 5 0', [PAD.format(n=n, x=x, y=0, a=0, w=0.3, h=1) for n, x in enumerate((0, 0.95, 1.9, 2.85))])]
        t, facts = self.tier(ok)
        self.assertEqual(t['tier'], 'ECONOMIC')
        self.assertTrue(all(c['ok'] for c in t['economic_checks']))
        self.assertEqual(self.route(t, facts)['route'], 'SINGLE_BOARDS')
        fine = [footprint('U1', 'lib:QFN', '5 5 0', [PAD.format(n=n, x=x, y=0, a=0, w=0.2, h=1) for n, x in enumerate((0, 0.35, 0.7, 1.05))])]
        small = [footprint('C1', 'lib:C_0201_0603Metric', '5 5 0', [PAD.format(n=1, x=0, y=0, a=0, w=0.3, h=0.3)])]
        cases = {'both sides': self.tier(ok, sides=('Bottom', 'Top')), 'thickness': self.tier(ok, thickness=0.6),
                 'layers': self.tier(ok, layers=1), 'quantity': self.tier(ok, quantity=51), 'pitch': self.tier(fine),
                 'package': self.tier(small), 'standard-only part': self.tier(ok, types='Standard Only')}
        for name, (t, facts) in cases.items():
            self.assertEqual(t['tier'], 'STANDARD', name)
            self.assertEqual(len(t['reasons']), 1, (name, t['reasons']))
            r = self.route(t, facts)
            # a 20 x 10 mm board under Standard needs a 70 x 70 mm JLC panel with rails
            self.assertEqual(r['route'], 'PANEL_BY_JLCPCB', name)
            self.assertEqual((r['panel']['columns_x'], r['panel']['rows_y']), (4, 7))
            self.assertTrue(r['panel']['edge_rails'])

    def test_outline_shape(self):
        box = ((0.0, 20.0), (0.0, 10.0))
        lines = [('gr_line', (0.0, 0.0), (20.0, 0.0)), ('gr_line', (20.0, 0.0), (20.0, 10.0)), ('gr_line', (20.0, 10.0), (0.0, 10.0)), ('gr_line', (0.0, 10.0), (0.0, 0.0))]
        self.assertTrue(J.is_rectangle(lines, *box))
        self.assertTrue(J.is_rectangle([('gr_rect', (0.0, 0.0), (20.0, 10.0))], *box))
        notched = lines[:3] + [('gr_line', (0.0, 10.0), (0.0, 6.0)), ('gr_line', (0.0, 6.0), (1.0, 6.0)), ('gr_line', (1.0, 6.0), (1.0, 4.0)),
                                ('gr_line', (1.0, 4.0), (0.0, 4.0)), ('gr_line', (0.0, 4.0), (0.0, 0.0))]
        self.assertFalse(J.is_rectangle(notched, *box))

    def test_small_economic_board_gets_a_jlc_panel_with_a_separation_question(self):
        ok = [footprint('J1', 'lib:Header', '4 4 0', [PAD.format(n=1, x=0, y=0, a=0, w=1, h=1)])]
        t, facts = self.tier(ok)
        facts['outline_mm'].update(width=8.0, height=30.0)
        r = self.route(t, facts)
        self.assertEqual(r['route'], 'PANEL_BY_JLCPCB_TO_CONFIRM')
        self.assertEqual((r['panel']['columns_x'], r['panel']['rows_y']), (2, 1))
        self.assertFalse(r['panel']['edge_rails'])
        self.assertEqual([q['id'] for q in r['open_questions']], ['economic-panel-separation'])

if __name__ == '__main__':
    unittest.main()
