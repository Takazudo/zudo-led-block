"""Behavioral interface assertions, authorized-delta check, source-authority guards and profile rules.

Offline (no Docker/KiCad): uses the historical A5 netlists as the reviewed positive
reference and mutated copies as negative controls. Explicit self.assert* only, so
the results are the same under `python3 -O`.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / 'native_gate'))
import authority as au  # noqa: E402
import delta as dl  # noqa: E402
import interface as itf  # noqa: E402
import runner as nv  # noqa: E402

NL = REPO / 'engineering/a5/integration/native_schematic'
ROLES = REPO / 'engineering/a7/verification/interface_roles'
FX = 'scripts/tests/fixtures/native/profile.json'
A7 = 'engineering/a7/verification/native_gate.json'


def netlists(d: Path | None = None, controller: Path | None = None) -> dict:
    return {'controller': controller or NL / 'controller/netlist.xml', 'led_leaf': NL / 'led_leaf/netlist.xml',
            'power_adapter': NL / 'power_adapter/netlist.xml'}


def move_pin(src: Path, dst: Path, ref: str, pin: str, to_net_of: tuple[str, str] | None = None, alone: bool = False) -> None:
    root = ET.parse(src).getroot()
    nets = root.findall('./nets/net')
    node = net_from = None
    for n in nets:
        for nd in n.findall('node'):
            if nd.get('ref') == ref and nd.get('pin') == pin:
                node, net_from = nd, n
    net_from.remove(node)
    if alone:
        new = ET.SubElement(root.find('nets'), 'net', {'code': '9999', 'name': f'unconnected-({ref}-{pin})'})
        new.append(node)
    else:
        for n in nets:
            if any(nd.get('ref') == to_net_of[0] and nd.get('pin') == to_net_of[1] for nd in n.findall('node')):
                n.append(node)
    ET.ElementTree(root).write(dst)


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.d = Path(self.td.name)

    def tearDown(self):
        self.td.cleanup()

    def failed(self, res):
        return sorted(c['id'] for c in res['checks'] if not c['passed'])

    def roles_copy(self, edit) -> Path:
        r = json.loads((ROLES / 'a5_reference.json').read_text())
        edit(r)
        p = self.d / 'roles.json'
        p.write_text(json.dumps(r))
        return p

    def test_a5_reference_passes_on_a5_netlists(self):
        r = itf.check(netlists(), ROLES / 'a5_reference.json')
        self.assertTrue(r['all_passed'], self.failed(r))
        self.assertGreaterEqual(len(r['checks']), 40)

    def test_a7_draft_roles_cannot_pass(self):
        r = itf.check(netlists(), ROLES / 'a7_controller.json')
        self.assertFalse(r['all_passed'])
        for cid in ('cv.passive_thru', 'mode.truth_table', 'mode.common_gnd'):
            self.assertIn(cid, self.failed(r))

    def test_thru_tip_moved_off_cv_net(self):
        m = self.d / 'c.xml'
        move_pin(NL / 'controller/netlist.xml', m, 'J2', '6', to_net_of=('U1', '4'))
        r = itf.check(netlists(controller=m), ROLES / 'a5_reference.json')
        self.assertIn('cv.passive_thru', self.failed(r))

    def test_normal_contact_connected(self):
        m = self.d / 'c.xml'
        move_pin(NL / 'controller/netlist.xml', m, 'J1', '4', to_net_of=('U1', '4'))
        r = itf.check(netlists(controller=m), ROLES / 'a5_reference.json')
        self.assertEqual(self.failed(r), ['cv.normals_in_unused'])

    def test_c13_moved_after_r7(self):
        m = self.d / 'c.xml'
        move_pin(NL / 'controller/netlist.xml', m, 'C13', '1', to_net_of=('R7', '2'))
        r = itf.check(netlists(controller=m), ROLES / 'a5_reference.json')
        self.assertIn('cv.c13_before_r7', self.failed(r))

    def test_mode_truth_table_wrong_contact_arrangement(self):
        # a switch whose centre closes common to throw A would make the centre ON, not PROGRAM
        p = self.roles_copy(lambda r: r['controller'].update(switch_positions={'ON': ['2-1'], 'PGM': ['2-1'], 'CV': ['2-3']}))
        self.assertEqual(self.failed(itf.check(netlists(), p)), ['mode.truth_table'])
        p = self.roles_copy(lambda r: r['controller'].update(switch_positions={'ON': ['2-3'], 'PGM': [], 'CV': ['2-1']}))
        self.assertEqual(self.failed(itf.check(netlists(), p)), ['mode.truth_table'])
        p = self.roles_copy(lambda r: r['controller'].update(switch_positions={'ON': ['2-1'], 'CV': ['2-3']}))
        self.assertEqual(self.failed(itf.check(netlists(), p)), ['mode.truth_table'])

    def test_mode_pullup_missing(self):
        m = self.d / 'c.xml'
        move_pin(NL / 'controller/netlist.xml', m, 'R9', '1', alone=True)
        r = itf.check(netlists(controller=m), ROLES / 'a5_reference.json')
        self.assertIn('mode.pullups_to_vdd', self.failed(r))

    def test_common_not_grounded(self):
        m = self.d / 'c.xml'
        move_pin(NL / 'controller/netlist.xml', m, 'SW1', '2', alone=True)
        r = itf.check(netlists(controller=m), ROLES / 'a5_reference.json')
        self.assertIn('mode.common_gnd', self.failed(r))

    def test_led_streams_merged(self):
        m = self.d / 'c.xml'
        move_pin(NL / 'controller/netlist.xml', m, 'J3', '4', to_net_of=('R14', '2'))
        r = itf.check(netlists(controller=m), ROLES / 'a5_reference.json')
        self.assertIn('led.right_cable', self.failed(r))
        self.assertIn('led.two_streams', self.failed(r))

    def test_unresolved_role_and_missing_netlist_fail(self):
        p = self.roles_copy(lambda r: r['controller'].update({'mcu.adc': {'unresolved': 'x'}}))
        self.assertIn('cv.adc', self.failed(itf.check(netlists(), p)))
        nl = netlists(); nl.pop('led_leaf')
        r = itf.check(nl, ROLES / 'a5_reference.json')
        self.assertFalse(r['all_passed'])
        r = itf.check(netlists(controller=self.d / 'absent.xml'), ROLES / 'a5_reference.json')
        self.assertFalse(r['all_passed'])


class DeltaTests(unittest.TestCase):
    BASE = 'engineering/a5/integration/native_schematic/controller/netlist.xml'

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.d = Path(self.td.name)
        self.rec = json.loads((REPO / 'scripts/tests/fixtures/native/a5_identity_delta.json').read_text())

    def tearDown(self):
        self.td.cleanup()

    def run_check(self, rec, cand):
        p = self.d / 'rec.json'
        p.write_text(json.dumps(rec))
        return dl.check(p, cand, REPO)

    def test_identity_passes(self):
        r = self.run_check(self.rec, REPO / self.BASE)
        self.assertTrue(r['ok'], r['failures'])
        self.assertEqual(r['observed_delta'], [])

    def test_unauthorized_pin_move_fails_and_authorized_passes(self):
        m = self.d / 'c.xml'
        move_pin(REPO / self.BASE, m, 'R9', '1', alone=True)
        r = self.run_check(self.rec, m)
        self.assertFalse(r['ok'])
        rec = copy.deepcopy(self.rec)
        rec['entries'] = [{'kind': 'pin_moved', 'pin': 'R9.1', 'reason': 't', 'issue': '#18'}]
        r = self.run_check(rec, m)
        # moving R9.1 also changes the group of every former +3V3 neighbour: those must be authorized too
        self.assertFalse(r['ok'])
        rec['entries'] = [{'kind': 'component_replaced', 'ref': 'R9', 'reason': 't', 'issue': '#18'}]
        self.assertTrue(self.run_check(rec, m)['ok'])

    def test_stale_entry_fails(self):
        rec = copy.deepcopy(self.rec)
        rec['entries'] = [{'kind': 'field_changed', 'ref': 'J1', 'field': 'value', 'reason': 't', 'issue': '#18'}]
        r = self.run_check(rec, REPO / self.BASE)
        self.assertFalse(r['ok'])
        self.assertTrue(any('stale' in f for f in r['failures']))

    def test_field_change_needs_authorization(self):
        root = ET.parse(REPO / self.BASE).getroot()
        for c in root.iter('comp'):
            if c.get('ref') == 'J1':
                c.find('value').text = 'PJ-324M'
        m = self.d / 'c.xml'; ET.ElementTree(root).write(m)
        self.assertFalse(self.run_check(self.rec, m)['ok'])
        rec = copy.deepcopy(self.rec)
        rec['entries'] = [{'kind': 'field_changed', 'ref': 'J1', 'field': 'value', 'reason': 't', 'issue': '#18'}]
        self.assertTrue(self.run_check(rec, m)['ok'])

    def test_unreviewed_or_tampered_record_fails(self):
        rec = copy.deepcopy(self.rec); rec['review'] = None
        self.assertFalse(self.run_check(rec, REPO / self.BASE)['ok'])
        rec = copy.deepcopy(self.rec); rec['baseline']['sha256'] = '0' * 64
        self.assertFalse(self.run_check(rec, REPO / self.BASE)['ok'])
        rec = copy.deepcopy(self.rec); rec['entries'] = [{'kind': 'pin_moved', 'pin': 'R9.1'}]
        self.assertFalse(self.run_check(rec, REPO / self.BASE)['ok'])

    def test_a7_record_cannot_pass_yet(self):
        r = dl.check(REPO / 'engineering/a7/verification/authorized_delta.json', REPO / self.BASE, REPO)
        self.assertFalse(r['ok'])


class AuthorityTests(unittest.TestCase):
    def test_protected_paths_are_refused(self):
        for rel in ('engineering/a5/electronics/native/controller/controller.kicad_pcb',
                    'engineering/a7/electronics/controller/controller.kicad_pcb'):
            with self.subTest(rel=rel):
                with self.assertRaises(au.Refused):
                    au.check_writable(REPO / rel)
        board = REPO / 'scripts/tests/fixtures/native/led_leaf_zoned/fixture.kicad_pcb'
        with self.assertRaises(au.Refused):
            au.check_writable(board, [board])
        au.check_writable(REPO / 'scripts/tests/fixtures/native/led_leaf_zoned/placement.json', [board])

    def test_initial_board_staging_must_be_empty_and_outside_repo(self):
        with self.assertRaises(au.Refused):
            au.require_empty_staging(REPO / 'engineering/a7/electronics')
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / 'x').write_text('x')
            with self.assertRaises(au.Refused):
                au.require_empty_staging(Path(td))
            au.require_empty_staging(Path(td) / 'fresh')

    def test_export_rejects_inconsistent_facts(self):
        board = REPO / 'scripts/tests/fixtures/native/led_leaf_zoned/fixture.kicad_pcb'
        with self.assertRaises(au.Refused):
            au.placement(board, {'geometry_sha256': 'x'}, {'footprints': []})


class ProfileTests(unittest.TestCase):
    def test_locks_are_current(self):
        for prof in (FX, A7):
            with self.subTest(prof=prof):
                p = nv.load_profile(REPO, prof)
                self.assertEqual((REPO / p['lock']).read_bytes(), nv.lock_bytes(REPO, p, prof))

    def test_infrastructure_status_is_never_a_board_pass(self):
        p = nv.load_profile(REPO, FX)
        self.assertEqual(nv.final_status(p, []), 'INFRASTRUCTURE_PASS')
        self.assertEqual(nv.final_status(p, ['x']), 'FAIL')
        self.assertIsNone(p.get('candidate'))

    def test_infrastructure_profile_cannot_name_candidate(self):
        with tempfile.TemporaryDirectory() as td:
            p = json.loads((REPO / FX).read_text()); p['candidate'] = 'fixture_leaf'
            (Path(td) / 'p.json').write_text(json.dumps(p))
            with self.assertRaises(nv.ev.Fail):
                nv.load_profile(Path(td), 'p.json')

    def test_a7_profile_without_candidate_stops_with_no_candidate(self):
        with tempfile.TemporaryDirectory() as td:
            a = argparse.Namespace(profile=A7, repo=REPO, out=Path(td) / 'out', deadline_s=60)
            self.assertEqual(nv.cmd_run(a), 1)
            s = json.loads((Path(td) / 'out/summary.json').read_text())
            self.assertEqual(s['status'], 'NO_CANDIDATE')

    def test_run_refuses_output_in_repo_or_non_empty(self):
        a = argparse.Namespace(profile=FX, repo=REPO, out=REPO / 'tmp-native-out', deadline_s=60)
        self.assertEqual(nv.cmd_run(a), 2)
        self.assertFalse((REPO / 'tmp-native-out').exists())
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / 'x').write_text('x')
            self.assertEqual(nv.cmd_run(argparse.Namespace(profile=FX, repo=REPO, out=Path(td), deadline_s=60)), 2)

    def test_mutation_controls_need_routed_copper_and_a_zone(self):
        p = nv.load_profile(REPO, FX)
        kinds = {c['kind'] for c in p['controls']['mutations'].values()}
        self.assertEqual(kinds, {'route_break', 'wrong_connection', 'fill_shift'})
        board = (REPO / p['designs']['fixture_leaf']['dir'] / 'fixture.kicad_pcb').read_text()
        self.assertGreater(board.count('(segment'), 10)
        self.assertGreater(board.count('filled_polygon'), 0)

    def test_lock_detects_changed_input(self):
        p = nv.load_profile(REPO, FX)
        lk, errs = nv.verify_lock(REPO, p, FX)
        self.assertEqual(errs, [])
        tampered = copy.deepcopy(lk)
        tampered['files'][0]['sha256'] = '0' * 64
        with tempfile.TemporaryDirectory() as td:
            t = Path(td) / 'lock.json'
            t.write_text(json.dumps(tampered))
            _, errs = nv.verify_lock(REPO, dict(p, lock=str(t)), FX)
            self.assertTrue(any('sha256' in e for e in errs), errs)
            dropped = copy.deepcopy(lk); dropped['files'] = dropped['files'][1:]
            t.write_text(json.dumps(dropped))
            _, errs = nv.verify_lock(REPO, dict(p, lock=str(t)), FX)
            self.assertTrue(any('file set differs' in e for e in errs), errs)


if __name__ == '__main__':
    unittest.main()


class ReviewFindingTests(unittest.TestCase):
    """Regression tests for the independent review of PR #22."""

    BASE = DeltaTests.BASE

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.d = Path(self.td.name)
        self.rec = json.loads((REPO / 'scripts/tests/fixtures/native/a5_identity_delta.json').read_text())

    def tearDown(self):
        self.td.cleanup()

    def write(self, name, obj):
        p = self.d / name
        p.write_text(json.dumps(obj))
        return p

    def test_named_candidate_must_be_bound_to_every_check(self):
        p = json.loads((REPO / FX).read_text())
        p.update(kind='revision', candidate='TODO')
        self.write('p.json', p)
        with self.assertRaises(nv.ev.Fail):
            nv.load_profile(self.d, 'p.json')
        p['candidate'] = 'fixture_leaf'  # a real design, but not the protected board of every check
        p['delta']['candidate_design'] = 'a5_controller'
        self.write('p.json', p)
        with self.assertRaises(nv.ev.Fail):
            nv.load_profile(self.d, 'p.json')
        p['delta']['candidate_design'] = 'fixture_leaf'
        p['interface']['netlists']['controller'] = 'fixture_leaf'
        self.write('p.json', p)
        self.assertEqual(nv.load_profile(self.d, 'p.json')['candidate'], 'fixture_leaf')

    def test_empty_regeneration_command_fails_explicitly(self):
        g = nv.Gate(self.d, self.d, 10)
        nv.regeneration(g, {'regeneration': {'check_command': [], 'protected': ['x']}})
        self.assertTrue(any('no check_command' in f for f in g.failures))

    def test_harness_missing_nets_do_not_compare_equal(self):
        r = json.loads((ROLES / 'a5_reference.json').read_text())
        r['controller']['led.vled'] = 'U99.1'
        res = itf.check(netlists(), self.write('roles.json', r))
        failed = {c['id'] for c in res['checks'] if not c['passed']}
        self.assertIn('led.two_streams', failed)

    def test_unreviewed_role_map_cannot_pass(self):
        r = json.loads((ROLES / 'a5_reference.json').read_text())
        r['status'] = 'unresolved_draft'
        res = itf.check(netlists(), self.write('roles.json', r))
        self.assertFalse(res['all_passed'])
        self.assertEqual([c['id'] for c in res['checks'] if not c['passed']], ['roles.reviewed'])
        r['status'] = 'reviewed'; r['review'] = None
        self.assertFalse(itf.check(netlists(), self.write('roles.json', r))['all_passed'])

    def test_every_symbol_field_is_compared(self):
        root = ET.parse(REPO / self.BASE).getroot()
        comp = next(c for c in root.iter('comp') if c.get('ref') == 'R9')
        fields = comp.find('fields')
        ET.SubElement(fields, 'field', {'name': 'Rating'}).text = '1/16W'
        m = self.d / 'c.xml'; ET.ElementTree(root).write(m)
        r = dl.check(self.write('rec.json', self.rec), m, REPO)
        self.assertFalse(r['ok'])
        self.assertTrue(any(d.get('field') == 'field:Rating' for d in r['observed_delta']))

    def add_r99(self, joins: tuple[str, str]) -> Path:
        root = ET.parse(REPO / self.BASE).getroot()
        comps = root.find('components')
        c = ET.SubElement(comps, 'comp', {'ref': 'R99'})
        ET.SubElement(c, 'value').text = '1k'
        for pin, target in zip(('1', '2'), joins):
            for n in root.findall('./nets/net'):
                if any(f"{nd.get('ref')}.{nd.get('pin')}" == target for nd in n.findall('node')):
                    ET.SubElement(n, 'node', {'ref': 'R99', 'pin': pin})
        m = self.d / 'c.xml'; ET.ElementTree(root).write(m)
        return m

    def test_added_component_must_declare_its_connections(self):
        m = self.add_r99(('R9.1', 'U1.8'))  # +3V3 to MODE_A
        rec = copy.deepcopy(self.rec)
        rec['entries'] = [{'kind': 'component_added', 'ref': 'R99', 'reason': 't', 'issue': '#18'}]
        self.assertFalse(dl.check(self.write('rec.json', rec), m, REPO)['ok'])
        rec['entries'][0]['connections'] = {'1': 'R9.1', '2': 'R10.2'}  # wrong: pin 2 is on MODE_A, not MODE_B
        self.assertFalse(dl.check(self.write('rec.json', rec), m, REPO)['ok'])
        rec['entries'][0]['connections'] = {'1': 'R9.1', '2': 'U1.8'}
        r = dl.check(self.write('rec.json', rec), m, REPO)
        self.assertTrue(r['ok'], r['failures'])

    def test_duplicate_exported_pin_is_rejected_by_every_check(self):
        root = ET.parse(REPO / self.BASE).getroot()
        nets = root.findall('./nets/net')
        ET.SubElement(nets[1], 'node', {'ref': nets[0].find('node').get('ref'), 'pin': nets[0].find('node').get('pin')})
        m = self.d / 'c.xml'; ET.ElementTree(root).write(m)
        self.assertFalse(dl.check(self.write('rec.json', self.rec), m, REPO)['ok'])
        self.assertFalse(itf.check(netlists(controller=m), ROLES / 'a5_reference.json')['all_passed'])
        with self.assertRaises(nv.ev.Fail):
            nv.ev.parse_netlist(m)

    def test_expected_failure_control_checks_netlist_and_erc_ops(self):
        op = {'exit_code': 0, 'timed_out': False, 'stdout_truncated': False, 'stderr_truncated': False}
        drc = {'violations': [], 'unconnected_items': []}
        (self.d / 'drc.json').write_text(json.dumps(drc))
        exp = {'violations': [], 'unconnected': 0}
        rec = {'ops': {'erc': dict(op), 'netlist': dict(op, exit_code=1), 'drc': dict(op, exit_code=5)}}
        r = nv.ev.evaluate_expected_failure(exp, rec, self.d)
        self.assertTrue(any(f.startswith('netlist:') for f in r['failures']), r['failures'])
        rec['ops']['netlist'] = dict(op, timed_out=True)
        self.assertFalse(nv.ev.evaluate_expected_failure(exp, rec, self.d)['ok'])
