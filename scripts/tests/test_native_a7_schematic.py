"""A7 schematic phase: generator faithfulness, derived-file freshness, and the review gates staying closed."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(REPO / 'scripts'))
sys.path.insert(0, str(REPO / 'scripts/native_gate'))
import a7_electronics as a7  # noqa: E402
import delta as dl  # noqa: E402
import interface as itf  # noqa: E402
from test_native_behavior import move_pin  # noqa: E402

EV = REPO / 'engineering/a7/verification'
A7_NL = EV / 'schematic/netlist.xml'
A5_NL = REPO / 'engineering/a5/integration/native_schematic'
REVIEW_FAIL = 'authorized-delta record has no review entry; an unreviewed record cannot authorize anything'


def netlists(controller=A7_NL):
    return {'controller': controller, 'led_leaf': A5_NL / 'led_leaf/netlist.xml',
            'power_adapter': A5_NL / 'power_adapter/netlist.xml'}


def failed(r):
    return sorted(c['id'] for c in r['checks'] if not c['passed'])


class GeneratorTests(unittest.TestCase):
    def test_port_reproduces_a5_schematic_byte_identical(self):
        files = a7.make_schematic(a7.a5.make_controller(), a7.A5_STYLE)
        self.assertEqual(files['controller.kicad_sch'].encode(), a7.A5_CONTROLLER_SCH.read_bytes())

    def test_derived_files_current(self):
        p = subprocess.run([sys.executable, 'scripts/a7_electronics.py', 'generate', '--check'], cwd=REPO,
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_only_j1_j2_sw1_change(self):
        a5c = {c['ref']: c for c in a7.a5.make_controller()['components']}
        a7c = {c['ref']: c for c in a7.a7_controller()['components']}
        self.assertEqual(set(a5c), set(a7c))
        changed = {r for r in a5c if a5c[r] != a7c[r]}
        self.assertEqual(changed, {'J1', 'J2', 'SW1'})

    def test_footprint_pads_match_symbol_pins(self):
        for typ, fp in (('JACK_PJ324M', a7.footprint_pj324m()), ('SW_PCM13', a7.footprint_pcm13())):
            pads = {line.split('"')[1] for line in fp.splitlines() if line.strip().startswith('(pad "') and not line.strip().startswith('(pad ""')}
            self.assertEqual(pads, {n for n, *_ in a7.PIN_DEFS_A7[typ]}, typ)

    def test_pcm13smtr_land_pattern_pins_drawing_dimensions(self):
        # C&K PC MOUNTING I-48: chain 1.5/3.0/1.5 (span 6.0), pads 0.7 x 1.5 from 1.0 to 2.5 off the peg
        # line, retention pads 1.0 x 0.8 with 9.3 inner span and 1.13 gap, pegs 5.0 apart.
        d = a7.PCM13
        xs = d['signal_x']
        self.assertEqual([round(b - a, 3) for a, b in zip(xs, xs[1:])], [1.5, 3.0, 1.5])
        self.assertEqual(round(xs[-1] - xs[0], 3), 6.0)
        w, h = d['signal_size']
        self.assertEqual((w, h), (0.7, 1.5))
        self.assertEqual((round(-d['signal_y'] - h / 2, 3), round(-d['signal_y'] + h / 2, 3)), (1.0, 2.5))
        mw, mh = d['mp_size']
        mx = sorted({abs(x) for x, _ in d['mp']}); my = sorted({abs(y) for _, y in d['mp']})
        self.assertEqual(round(2 * (mx[0] - mw / 2), 3), 9.3)
        self.assertEqual(round(2 * (my[0] - mh / 2), 3), 1.13)
        self.assertEqual(round(d['peg_x'][1] - d['peg_x'][0], 3), 5.0)

    def test_pj324m_drawing_dimensions(self):
        d = a7.PJ324M
        self.assertEqual(d['pins'], {'1': (0.0, 1.6), '5': (4.5, 5.6), '3': (-2.5, 8.6), '2': (-5.2, 9.6), '4': (4.0, 13.0)})
        x1, y1, x2, y2 = d['body']
        self.assertEqual((x1, x2, y2), (-6.1, 5.4, 14.2))  # 5.4 on the pin-4/5 side
        self.assertEqual(d['barrel'][1], -3.5)

    def test_generate_refuses_a5_and_authoritative_board(self):
        for target in (REPO / 'engineering/a5/electronics/native/controller/x.kicad_sch',
                       REPO / 'engineering/a7/electronics/controller/controller.kicad_pcb'):
            with self.assertRaises(a7.authority.Refused):
                a7.authority.check_writable(target)

    def test_init_board_refuses_repo_and_nonempty(self):
        with self.assertRaises(a7.authority.Refused):
            a7.authority.require_empty_staging(REPO / 'engineering/a7/electronics/stage')
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / 'x').write_text('x')
            with self.assertRaises(a7.authority.Refused):
                a7.authority.require_empty_staging(Path(td))


class ReviewGateTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.d = Path(self.td.name)

    def tearDown(self):
        self.td.cleanup()

    def test_a7_behavior_passes_but_unreviewed_roles_fail(self):
        r = itf.check(netlists(), EV / 'interface_roles/a7_controller.json')
        self.assertEqual(failed(r), ['roles.reviewed'])
        truth = [c for c in r['checks'] if c['id'] == 'mode.truth_table'][0]
        self.assertEqual(truth['derived'], {'ON': [0, 1], 'PGM': [1, 1], 'CV': [1, 0]})

    def test_a7_roles_fail_on_a5_netlist(self):
        r = itf.check(netlists(A5_NL / 'controller/netlist.xml'), EV / 'interface_roles/a7_controller.json')
        for cid in ('cv.passive_thru', 'mode.common_gnd', 'mode.b_input', 'roles.reviewed'):
            self.assertIn(cid, failed(r))

    def test_spare_switch_contact_connected_is_caught(self):
        m = self.d / 'c.xml'
        move_pin(A7_NL, m, 'SW1', '2', to_net_of=('U1', '8'))
        r = itf.check(netlists(m), EV / 'interface_roles/a7_controller.json')
        self.assertIn('mode.spare_contacts_unused', failed(r))

    def test_inferred_jack_tip_moved_is_caught(self):
        m = self.d / 'c.xml'
        move_pin(A7_NL, m, 'J2', '4', to_net_of=('U1', '4'))
        r = itf.check(netlists(m), EV / 'interface_roles/a7_controller.json')
        self.assertIn('cv.passive_thru', failed(r))

    def roles_with(self, **edits):
        r = json.loads((EV / 'interface_roles/a7_controller.json').read_text())
        r['controller'].update(edits)
        p = self.d / 'roles.json'
        p.write_text(json.dumps(r))
        return p

    def test_unused_and_coverage_do_not_pass_vacuously(self):
        cases = {
            'sw.unused': (['SW1.9'], {'mode.spare_contacts_unused', 'mode.switch_pins_covered'}),
            'jack_thru.normals': ([], {'cv.jack_thru_pins_covered'}),
            'jack_in.normals': (['J1.7', 'J1.8'], {'cv.normals_in_unused', 'cv.jack_in_pins_covered'}),
        }
        for role, (val, expect) in cases.items():
            r = itf.check(netlists(), self.roles_with(**{role: val}))
            self.assertTrue(expect <= set(failed(r)), (role, failed(r)))
        r = itf.check(netlists(), self.roles_with(**{'sw.unused': []}))
        self.assertIn('mode.switch_pins_covered', failed(r))

    def test_delta_fails_only_on_missing_review(self):
        r = dl.check(EV / 'authorized_delta.json', A7_NL, REPO)
        self.assertEqual(r['failures'], [REVIEW_FAIL])
        self.assertEqual(r['replaced_refs'], ['J1', 'J2', 'SW1'])

    def test_delta_with_review_passes_and_rejects_other_moves(self):
        rec = json.loads((EV / 'authorized_delta.json').read_text())
        rec['review'] = {'by': 'synthetic test reviewer', 'ref': 'test'}
        p = self.d / 'rec.json'
        p.write_text(json.dumps(rec))
        self.assertTrue(dl.check(p, A7_NL, REPO)['ok'])
        m = self.d / 'c.xml'
        move_pin(A7_NL, m, 'R9', '2', to_net_of=('U1', '9'))
        self.assertFalse(dl.check(p, m, REPO)['ok'])
        rec2 = copy.deepcopy(rec)
        rec2['entries'] = [e for e in rec2['entries'] if e['ref'] != 'SW1']
        p.write_text(json.dumps(rec2))
        self.assertFalse(dl.check(p, A7_NL, REPO)['ok'])


if __name__ == '__main__':
    unittest.main()
