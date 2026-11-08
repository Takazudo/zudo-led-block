"""Guard tests for the native-gate evaluator. Run normally and with `python3 -O`:

  python3 -m unittest discover -s scripts/tests -p 'test_native_*.py'
  python3 -O -m unittest discover -s scripts/tests -p 'test_native_*.py'

Ported from scripts/tests/test_a6_native_eval.py at PR #14 head 7e96380be4fbea2bfcc4a5bd1d5721272a5a141f.

Checks use explicit `self.assert*` methods (unaffected by -O); the evaluator itself
must not depend on `assert`, which test_no_assert_statements enforces.
"""
from __future__ import annotations

import ast
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'native_gate'))
import evaluate as ev  # noqa: E402

VERSION = '10.0.8'
IGNORED = [{'key': 'missing_courtyard', 'description': 'x'}]
SEV = ['error', 'warning', 'exclusion']

NETLIST = """<?xml version="1.0"?>
<export version="E"><components>
<comp ref="R1"><value>10k</value><footprint>LightBlock:R0402</footprint><fields><field name="MPN">X</field></fields></comp>
<comp ref="R2"><value>10k</value><footprint>LightBlock:R0402</footprint><fields><field name="MPN">X</field></fields></comp>
</components><nets>
<net code="1" name="/A"><node ref="R1" pin="1"/></net>
<net code="2" name="/B"><node ref="R1" pin="2"/><node ref="R2" pin="1"/></net>
<net code="3" name="/GND"><node ref="R2" pin="2"/></net>
</nets></export>
"""


def good_dir(d: Path) -> None:
    (d / 'erc.json').write_text(json.dumps({'kicad_version': VERSION, 'sheets': [{'violations': []}]}))
    (d / 'drc.json').write_text(json.dumps({'kicad_version': VERSION, 'violations': [], 'unconnected_items': [],
                                            'schematic_parity': [], 'ignored_checks': IGNORED, 'included_severities': SEV}))
    (d / 'netlist.xml').write_text(NETLIST)
    (d / 'board_facts.json').write_text(json.dumps({
        'unconnected_pcbnew': 0, 'board_only': ['H1'], 'geometry_sha256': 'g', 'zone_fill_sha256': 'z',
        'pad_nets': {'R1': {'1': '/A', '2': '/B'}, 'R2': {'1': '/B', '2': '/GND'}, 'H1': {}}}))
    (d / 'refill.json').write_text(json.dumps({'geometry_sha256': 'g', 'zone_fill_sha256': 'z', 'unconnected_pcbnew': 0}))


def op(code=0):
    return {'exit_code': code, 'timed_out': False, 'stdout_truncated': False, 'stderr_truncated': False}


REC = {'ops': {'erc': op(), 'netlist': op(), 'drc': op()}, 'deadline_exceeded': False,
       'stage_before': {'b.kicad_pcb': 'h1', 'b.kicad_sch': 'h2'},
       'stage_after': {'b.kicad_pcb': 'h1', 'b.kicad_sch': 'h2', 'b.kicad_prl': 'p'}}
INPUTS = {'b.kicad_pcb': 'h1', 'b.kicad_sch': 'h2'}
EXP = {'kicad_version': VERSION, 'included_severities': SEV, 'ignored_checks': IGNORED, 'board_only': ['H1'],
       'refill_check': True, 'drc_residuals': [], 'parity_dispositions': {}}


class EvalTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.d = Path(self.td.name)
        good_dir(self.d)

    def tearDown(self):
        self.td.cleanup()

    def run_eval(self, rec=None, exp=None, inputs=None):
        return ev.evaluate_design('t', exp or EXP, copy.deepcopy(rec or REC), self.d, INPUTS if inputs is None else inputs)

    def edit(self, name, fn):
        p = self.d / name
        j = json.loads(p.read_text()); fn(j); p.write_text(json.dumps(j))

    def test_positive(self):
        r = self.run_eval()
        self.assertTrue(r['ok'], r['failures'])

    def test_missing_report(self):
        for f in ('erc.json', 'drc.json', 'netlist.xml', 'board_facts.json', 'refill.json'):
            with self.subTest(f=f):
                good_dir(self.d); (self.d / f).unlink()
                self.assertFalse(self.run_eval()['ok'])

    def test_malformed_report(self):
        (self.d / 'drc.json').write_text('{"violations": [')
        self.assertFalse(self.run_eval()['ok'])
        good_dir(self.d); (self.d / 'drc.json').write_text('[]')
        self.assertFalse(self.run_eval()['ok'])

    def test_missing_drc_key(self):
        self.edit('drc.json', lambda j: j.pop('unconnected_items'))
        self.assertFalse(self.run_eval()['ok'])

    def test_wrong_input_hash(self):
        self.assertFalse(self.run_eval(inputs={'b.kicad_pcb': 'other', 'b.kicad_sch': 'h2'})['ok'])

    def test_version_mismatch(self):
        self.edit('drc.json', lambda j: j.update(kicad_version='9.0.7'))
        self.assertFalse(self.run_eval()['ok'])
        v = ev.check_versions({'pcbnew_version': '10.0.7', 'kicad_cli_version': {'exit_code': 0, 'stdout': '10.0.8'}}, VERSION)
        self.assertTrue(v)
        self.assertFalse(ev.check_versions({'pcbnew_version': VERSION, 'kicad_cli_version': {'exit_code': 0, 'stdout': '10.0.8\n'}}, VERSION))

    def test_timeout_and_unknown_exit(self):
        r = copy.deepcopy(REC); r['ops']['drc'] = {'exit_code': None, 'timed_out': True}
        self.assertFalse(self.run_eval(rec=r)['ok'])
        r = copy.deepcopy(REC); r['ops']['erc']['exit_code'] = 2
        self.assertFalse(self.run_eval(rec=r)['ok'])
        r = copy.deepcopy(REC); r['ops']['drc']['exit_code'] = True
        self.assertFalse(self.run_eval(rec=r)['ok'])
        r = copy.deepcopy(REC); del r['ops']['netlist']
        self.assertFalse(self.run_eval(rec=r)['ok'])
        r = copy.deepcopy(REC); r['deadline_exceeded'] = True
        self.assertFalse(self.run_eval(rec=r)['ok'])

    def test_truncated_log(self):
        r = copy.deepcopy(REC); r['ops']['drc']['stderr_truncated'] = True
        self.assertFalse(self.run_eval(rec=r)['ok'])

    def test_unexpected_write(self):
        r = copy.deepcopy(REC); r['stage_after']['b.kicad_pcb'] = 'changed'
        self.assertFalse(self.run_eval(rec=r)['ok'])
        r = copy.deepcopy(REC); r['stage_after']['new.kicad_pcb'] = 'x'
        self.assertFalse(self.run_eval(rec=r)['ok'])
        r = copy.deepcopy(REC); del r['stage_after']['b.kicad_sch']
        self.assertFalse(self.run_eval(rec=r)['ok'])
        r = copy.deepcopy(REC); r['stage_before']['stray.txt'] = 'x'; r['stage_after']['stray.txt'] = 'x'
        self.assertFalse(self.run_eval(rec=r)['ok'])

    def test_zero_exit_does_not_override_violations(self):
        self.edit('drc.json', lambda j: j['violations'].append({'type': 'clearance', 'description': 'c', 'items': [{'description': 'Pad 1 of R1'}]}))
        self.assertFalse(self.run_eval()['ok'])

    def test_unconnected_and_pcbnew_unconnected(self):
        self.edit('drc.json', lambda j: j['unconnected_items'].append({'items': []}))
        self.assertFalse(self.run_eval()['ok'])
        good_dir(self.d); self.edit('board_facts.json', lambda j: j.update(unconnected_pcbnew=1))
        self.assertFalse(self.run_eval()['ok'])

    def test_residual_must_match_exactly_and_stay_reported(self):
        viol = {'type': 'courtyards_overlap', 'description': 'Courtyards overlap', 'items': [{'description': 'Footprint J3'}, {'description': 'Footprint H1'}]}
        exp = dict(EXP, drc_residuals=[{'id': 'J3-H1', 'type': 'courtyards_overlap', 'refs': ['H1', 'J3']}])
        self.edit('drc.json', lambda j: j['violations'].append(viol))
        r = copy.deepcopy(REC); r['ops']['drc']['exit_code'] = 5
        self.assertTrue(self.run_eval(rec=r, exp=exp)['ok'], self.run_eval(rec=r, exp=exp)['failures'])
        self.assertFalse(self.run_eval(rec=r)['ok'])  # not dispositioned
        good_dir(self.d)
        self.assertFalse(self.run_eval(exp=exp)['ok'])  # stale disposition
        v2 = dict(viol, items=[{'description': 'Footprint J3'}, {'description': 'Footprint C7'}])
        self.edit('drc.json', lambda j: j['violations'].append(v2))
        self.assertFalse(self.run_eval(rec=r, exp=exp)['ok'])

    def test_ignored_checks_and_severity_recorded(self):
        self.edit('drc.json', lambda j: j['ignored_checks'].append({'key': 'clearance'}))
        self.assertFalse(self.run_eval()['ok'])
        good_dir(self.d); self.edit('drc.json', lambda j: j.update(included_severities=['error']))
        self.assertFalse(self.run_eval()['ok'])

    def test_parity_independent(self):
        self.edit('board_facts.json', lambda j: j['pad_nets']['R2'].update({'1': '/A'}))
        self.assertFalse(self.run_eval()['ok'])
        good_dir(self.d); self.edit('board_facts.json', lambda j: j['pad_nets'].pop('R2'))
        self.assertFalse(self.run_eval()['ok'])
        good_dir(self.d); self.edit('board_facts.json', lambda j: j['pad_nets'].update({'R9': {'1': ''}}))
        self.assertFalse(self.run_eval()['ok'])
        good_dir(self.d); self.edit('board_facts.json', lambda j: j.update(board_only=[]))
        self.assertFalse(self.run_eval()['ok'])

    def test_parity_dispositions(self):
        items = [{'type': 'net_conflict', 'description': "Pad net (A) doesn't match net given by schematic (/A)", 'items': [{'description': 'Pad 1 of R1'}]},
                 {'type': 'footprint_symbol_field_mismatch', 'description': "Missing symbol field 'MPN' in footprint", 'items': [{'description': 'Footprint R1'}]}]
        self.edit('drc.json', lambda j: j['schematic_parity'].extend(items))
        r = copy.deepcopy(REC); r['ops']['drc']['exit_code'] = 5
        self.assertFalse(self.run_eval(rec=r)['ok'])
        exp = dict(EXP, parity_dispositions={'net_prefix_only': True, 'missing_fields': ['MPN']},
                   parity_counts={'net_prefix_only': 1, 'missing_field': 1})
        self.assertTrue(self.run_eval(rec=r, exp=exp)['ok'])
        exp2 = dict(exp, parity_counts={'net_prefix_only': 2, 'missing_field': 1})
        self.assertFalse(self.run_eval(rec=r, exp=exp2)['ok'])
        bad = {'type': 'net_conflict', 'description': "Pad net (A) doesn't match net given by schematic (/B)", 'items': []}
        self.edit('drc.json', lambda j: j['schematic_parity'].append(bad))
        self.assertFalse(self.run_eval(rec=r, exp=exp)['ok'])

    def test_stale_zone_fill(self):
        self.edit('refill.json', lambda j: j.update(zone_fill_sha256='other'))
        self.assertFalse(self.run_eval()['ok'])
        good_dir(self.d); self.edit('refill.json', lambda j: j.update(error='boom'))
        self.assertFalse(self.run_eval()['ok'])

    def test_erc_violation(self):
        self.edit('erc.json', lambda j: j['sheets'][0]['violations'].append({'type': 'x'}))
        r = copy.deepcopy(REC); r['ops']['erc']['exit_code'] = 5
        self.assertFalse(self.run_eval(rec=r)['ok'])
        good_dir(self.d); self.edit('erc.json', lambda j: j.update(sheets=[]))
        self.assertFalse(self.run_eval()['ok'])

    def test_missing_record(self):
        self.assertFalse(ev.evaluate_design('t', EXP, None, self.d, INPUTS)['ok'])

    def test_expected_failure_control(self):
        viols = [{'type': 'courtyards_overlap', 'items': [{'description': 'Footprint J3'}, {'description': 'Footprint C7'}]},
                 {'type': 'courtyards_overlap', 'items': [{'description': 'Footprint J3'}, {'description': 'Footprint H1'}]}]
        exp = {'violations': [{'type': 'courtyards_overlap', 'refs': ['J3', 'C7']}, {'type': 'courtyards_overlap', 'refs': ['J3', 'H1']}], 'unconnected': 2}
        self.edit('drc.json', lambda j: (j['violations'].extend(viols), j['unconnected_items'].extend([{}, {}])))
        rec = {'ops': {'erc': op(), 'netlist': op(), 'drc': op(5)}}  # ERC/netlist ops are now checked too
        self.assertTrue(ev.evaluate_expected_failure(exp, rec, self.d)['ok'])
        self.assertFalse(ev.evaluate_expected_failure(dict(exp, unconnected=3), rec, self.d)['ok'])
        self.assertFalse(ev.evaluate_expected_failure(exp, {'ops': {'erc': op(), 'netlist': op(), 'drc': op(0)}}, self.d)['ok'])
        good_dir(self.d)
        self.assertFalse(ev.evaluate_expected_failure(exp, rec, self.d)['ok'])


class SourceGuards(unittest.TestCase):
    def test_no_assert_statements(self):
        for p in sorted((HERE.parent / 'native_gate').glob('*.py')):
            tree = ast.parse(p.read_text())
            self.assertFalse([n.lineno for n in ast.walk(tree) if isinstance(n, ast.Assert)], p.name)

    def test_optimize_flag_reported(self):
        print(f'\n[python optimize level {sys.flags.optimize}]', file=sys.stderr)


if __name__ == '__main__':
    unittest.main()
