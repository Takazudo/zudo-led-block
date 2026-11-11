"""Synthetic records stay in temporary test roots; never real qualification evidence."""
import copy
import datetime as dt
import hashlib
import importlib.util
import json
import re
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('readiness', REPO/'scripts/a7_readiness.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        # Isolate Workflow F evidence logic from the separately tested real producers.
        self.producer_patch = patch.object(m, 'artifact_errors', return_value=[])
        self.producer_patch.start()
        self.addCleanup(self.producer_patch.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.plan = json.loads((REPO/m.QUAL/'plan.json').read_text())
        self.records = {'schema': 1, 'runs': [], 'material_observations': [],
                        'owner_prototype_route': None, 'manufacturing_release': None}
        for key, path in m.IDENTITY_PATHS.items():
            f = self.root/path
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text('synthetic '+key)
        self.raw = self.root/'raw.txt'
        self.raw.write_text('SYNTHETIC TEST DATA ONLY')
        self.receipt = {'path': 'raw.txt', 'sha256': m.digest(self.raw)}
        self.receipts = {}
        for role in ['criterion', 'review', 'material', 'route', 'release', 'order_files']:
            f = self.root/(role+'-receipt.txt')
            f.write_text('SYNTHETIC '+role)
            self.receipts[role] = {'path': f.name, 'sha256': m.digest(f)}
        for key in ['fixture', 'assembly_manifest']:
            (self.root/m.IDENTITY_PATHS[key]).write_text(json.dumps({
                'status': 'DIGITAL_DESIGN_VERIFIED', 'digital_fixture_complete': True, 'fresh_native_verified': True, 'inputs_sha256': {'raw.txt': m.digest(self.raw)}, 'blockers': []}))
        self.today = dt.date(2026, 11, 9)

    def evaluate(self):
        return m.evaluate(self.root, self.plan, self.records, self.today)

    def fully_recorded_synthetic_case(self):
        for p in self.plan['procedures']:
            p['criterion_status'] = 'REVIEWED'
            p['missing_criterion'] = ''
            p['criterion_review'] = self.receipts['criterion']
            # Synthetic acceptance review: proposals adopted at their traced basis, open items dropped.
            p['acceptance'] = [a for a in p['acceptance'] if a['confidence'] != 'UNRESOLVED']
            for a in p['acceptance']:
                if a['confidence'] == 'PROPOSED':
                    a['confidence'] = a.pop('basis_confidence')
                    a.pop('rationale')
        ids = {k: v['sha256'] for k, v in m.identities(self.root).items()}
        ph = hashlib.sha256(json.dumps(self.plan, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        for p in self.plan['procedures']:
            run = {k: 'synthetic context' for k in ['unit_id','operator','instruments','setup','conditions',
                   'observations','criterion_comparison','next_action','assembly_deviations']}
            raw = []
            for kind in m.REQUIRED_EVIDENCE[p['id']]:
                f = self.root/(p['id']+'-'+kind+'.txt')
                f.write_text('SYNTHETIC '+p['id']+' '+kind)
                raw.append({'kind':kind, 'path':f.name, 'sha256':m.digest(f)})
            run.update(run_id=p['id']+'-synthetic', procedure=p['id'], evidence_kind='BENCH_RECORD',
                       synthetic=False, result='PASS', identities=ids, plan_sha256=ph,
                       performed_at='2026-11-08T12:00:00Z', raw_evidence=raw, review=self.receipts['review'])
            self.records['runs'].append(run)
        self.records['material_observations'] = [dict(material=k, observed_on='2026-11-08',
            valid_until='2026-11-10', identities=ids, available_for_proposed_order=True, source=self.receipts['material']) for k in m.MATERIALS]
        self.records['owner_prototype_route'] = dict(identities=ids, scope='synthetic', quantity='1', constraints='synthetic', approval=self.receipts['route'])
        self.records['manufacturing_release'] = dict(identities=ids, approval=self.receipts['release'], reviewed_order_files=self.receipts['order_files'])

    def copy_of(self, role):
        src = self.root/self.receipts[role]['path']
        dst = self.root/('copy-of-'+src.name)
        dst.write_bytes(src.read_bytes())
        return {'path': dst.name, 'sha256': m.digest(dst)}

    def test_non_list_raw_evidence_blocks(self):
        self.fully_recorded_synthetic_case()
        self.records['runs'][0]['raw_evidence'] = 7
        r = self.evaluate()
        self.assertEqual(r['order_eligibility'], 'BLOCKED')

    def test_one_receipt_cannot_serve_several_roles(self):
        self.fully_recorded_synthetic_case()
        self.assertEqual(self.evaluate()['blockers'], [])
        cases = {
            'release approval reused as order files': lambda: self.records['manufacturing_release'].update(reviewed_order_files=self.receipts['release']),
            'execution review reused as owner route approval': lambda: self.records['owner_prototype_route'].update(approval=self.receipts['review']),
            'raw evidence reused by another procedure': lambda: self.records['runs'][1]['raw_evidence'].append(
                dict(self.records['runs'][0]['raw_evidence'][0], kind='extra_kind')),
            'criterion review reused as raw evidence': lambda: self.records['runs'][0]['raw_evidence'].append(
                dict(self.receipts['criterion'], kind='extra_kind')),
            'dot-dot spelling of the execution review as route approval': lambda: self.records['owner_prototype_route'].update(
                approval=dict(self.receipts['review'], path='sub/../'+self.receipts['review']['path'])),
            'byte-identical copy of the release approval as order files': lambda: self.records['manufacturing_release'].update(
                reviewed_order_files=self.copy_of('release')),
        }
        base = copy.deepcopy(self.records)
        for name, mutate in cases.items():
            with self.subTest(name):
                self.records = copy.deepcopy(base)
                mutate()
                r = self.evaluate()
                self.assertEqual(r['order_eligibility'], 'BLOCKED')
                self.assertTrue(any('receipt reused across roles' in b for b in r['blockers']), r['blockers'])

    def test_valid_blocked_report(self):
        r = self.evaluate()
        self.assertEqual(r['report_validation'], 'VALID')
        self.assertEqual(r['order_eligibility'], 'BLOCKED')
        self.assertEqual(len(r['procedures']), 19)

    def test_omitted_and_duplicate_procedure_rejected(self):
        self.plan['procedures'].pop()
        with self.assertRaises(ValueError): self.evaluate()
        self.plan['procedures'].append(self.plan['procedures'][0])
        with self.assertRaises(ValueError): self.evaluate()

    def test_false_completion_cannot_replace_observation(self):
        self.plan['procedures'][0]['result'] = 'PASS'
        with self.assertRaises(ValueError): self.evaluate()

    def test_complete_synthetic_case_only_in_temp_root(self):
        self.fully_recorded_synthetic_case()
        self.assertFalse(self.evaluate()['blockers'])

    def test_revision_firmware_configuration_and_population_changes_block(self):
        self.fully_recorded_synthetic_case()
        for key in ['board', 'firmware', 'configuration', 'population']:
            with self.subTest(key=key):
                p = self.root/m.IDENTITY_PATHS[key]
                old = p.read_bytes()
                p.write_bytes(old+b'changed')
                self.assertEqual(self.evaluate()['order_eligibility'], 'BLOCKED')
                p.write_bytes(old)

    def test_raw_missing_changed_incomplete_and_synthetic_flag_block(self):
        self.fully_recorded_synthetic_case()
        run = self.records['runs'][0]
        for field, value in [('raw_evidence', []), ('raw_evidence', [{'path':'raw.txt'}]),
                             ('synthetic', True), ('observations', 'NOT_MEASURED'), ('performed_at','2099-01-01T00:00:00Z')]:
            with self.subTest(field=field, value=value):
                old = run[field]
                run[field] = value
                self.assertEqual(self.evaluate()['order_eligibility'], 'BLOCKED')
                run[field] = old
        self.raw.write_text('changed')
        self.assertEqual(self.evaluate()['order_eligibility'], 'BLOCKED')

    def test_stale_materials_and_wrong_revision_block(self):
        self.fully_recorded_synthetic_case()
        obs = self.records['material_observations'][0]
        obs['valid_until'] = '2026-11-08'
        self.assertEqual(self.evaluate()['order_eligibility'], 'BLOCKED')
        obs['valid_until'] = '2026-11-10'
        obs['identities'] = {}
        self.assertEqual(self.evaluate()['order_eligibility'], 'BLOCKED')

    def test_later_failed_run_not_hidden_by_prior_pass(self):
        self.fully_recorded_synthetic_case()
        failed = copy.deepcopy(self.records['runs'][0])
        failed.update(run_id='later-failed-run', result='FAIL', performed_at='2026-11-09T00:00:00Z')
        self.records['runs'].append(failed)
        self.assertEqual(self.evaluate()['order_eligibility'], 'BLOCKED')
        self.assertEqual(len(self.records['runs']), 20)

    def test_reordered_newer_failure_cannot_hide_behind_older_pass(self):
        self.fully_recorded_synthetic_case()
        failed = copy.deepcopy(self.records['runs'][0])
        failed.update(run_id='newer-fail', result='FAIL', performed_at='2026-11-09T00:00:00Z')
        self.records['runs'].insert(0, failed)
        self.assertEqual(self.evaluate()['order_eligibility'], 'BLOCKED')

    def test_ambiguous_duplicate_run_times_block(self):
        self.fully_recorded_synthetic_case()
        r = copy.deepcopy(self.records['runs'][0]); r['run_id']='duplicate-time'
        self.records['runs'].append(r)
        self.assertEqual(self.evaluate()['order_eligibility'], 'BLOCKED')

    def test_required_evidence_kind_cannot_be_omitted_or_substituted(self):
        self.fully_recorded_synthetic_case()
        r = next(r for r in self.records['runs'] if r['procedure']=='firmware-waveforms')
        for kind in ['led_lot','programming_readback','left_waveform','right_waveform']:
            old = r['raw_evidence']
            r['raw_evidence'] = [x for x in old if x['kind'] != kind]
            self.assertEqual(self.evaluate()['order_eligibility'], 'BLOCKED')
            r['raw_evidence'] = old
        r['raw_evidence'] = [dict(self.receipt,kind=k) for k in m.REQUIRED_EVIDENCE[r['procedure']]]
        self.assertEqual(self.evaluate()['order_eligibility'], 'BLOCKED')

    def test_approval_cannot_be_boolean_or_unbound(self):
        self.fully_recorded_synthetic_case()
        self.records['manufacturing_release'] = True
        self.assertEqual(self.evaluate()['order_eligibility'], 'BLOCKED')

    def test_review_label_does_not_erase_unresolved_criterion(self):
        self.fully_recorded_synthetic_case()
        self.plan['procedures'][0]['missing_criterion'] = 'unresolved resistance limit'
        self.assertEqual(self.evaluate()['order_eligibility'], 'BLOCKED')

    def test_stale_artifact_input_binding_blocks(self):
        self.fully_recorded_synthetic_case()
        p = self.root/m.IDENTITY_PATHS['fixture']
        a = json.loads(p.read_text())
        a['inputs_sha256']['raw.txt'] = '0'*64
        p.write_text(json.dumps(a))
        self.assertTrue(any('stale input' in s for s in self.evaluate()['blockers']))

    def test_blocked_fixture_is_not_complete(self):
        p = self.root/m.IDENTITY_PATHS['fixture']
        a = json.loads(p.read_text()); a['status']='BLOCKED'; a['digital_fixture_complete']=False
        p.write_text(json.dumps(a))
        self.assertTrue(any('fixture digital design incomplete' in s for s in self.evaluate()['blockers']))


    def test_proposal_never_satisfies_a_reviewed_criterion(self):
        self.fully_recorded_synthetic_case()
        a = next(a for p in self.plan['procedures'] if p['id'] == 'cv-noise' for a in p['acceptance'] if a['id'] == 'noise-max')
        a.update(basis_confidence=a['confidence'], confidence='PROPOSED', rationale='synthetic proposal')
        gates = {g['gate']: g for g in self.evaluate()['gates']}
        self.assertIn('criterion:cv-noise', gates)
        self.assertTrue(any('PROPOSED' in r for r in gates['criterion:cv-noise']['reasons']))


class ExecutableProcedureTests(unittest.TestCase):
    """Acceptance values must trace to the repository; nothing here records a measurement."""
    def setUp(self):
        self.plan = json.loads((REPO/m.QUAL/'plan.json').read_text())

    def proc(self, pid):
        return next(p for p in self.plan['procedures'] if p['id'] == pid)

    def item(self, pid, aid):
        return next(a for a in self.proc(pid)['acceptance'] if a['id'] == aid)

    def assertUntraceable(self, pattern):
        with self.assertRaisesRegex(ValueError, pattern):
            m.schema(self.plan, {'schema': 1, 'runs': [], 'material_observations': []})

    def test_real_plan_is_traceable_and_keeps_every_procedure_unmeasured(self):
        m.schema(self.plan, {'schema': 1, 'runs': [], 'material_observations': []})
        for p in self.plan['procedures']:
            self.assertEqual((p['observation'], p['result']), ('NOT_MEASURED', 'NOT_RUN'))
            self.assertEqual(set(p['record']), set(m.REQUIRED_EVIDENCE[p['id']]))

    def test_assumed_and_inferred_values_stay_labelled(self):
        self.assertEqual(self.item('harness-depth', 'power-tolerance')['confidence'], 'ASSUMED')
        self.assertEqual(self.item('harness-depth', 'power-tolerance')['value'], 3.0)
        self.assertEqual(self.item('jack-dimensions', 'axis-height')['confidence'], 'INFERRED')
        self.assertEqual(self.item('harness-depth', 'power-band')['confidence'], 'ASSUMED')
        self.item('harness-depth', 'power-tolerance')['confidence'] = 'DESIGN'
        self.assertUntraceable('marks this value ASSUMED')

    def test_changed_fact_value_is_rejected(self):
        self.item('switch-fit', 'contact-rating')['value'] = '1 A @ 12 VDC'
        self.assertUntraceable('differs from the cited fact')

    def test_mirror_fact_cannot_be_promoted(self):
        self.item('pmma-supports', 'plug-force')['confidence'] = 'SOURCED'
        self.assertUntraceable('confidence differs from the cited fact')

    def test_changed_record_value_is_rejected(self):
        self.item('harness-depth', 'power-free-span')['value'] = 50.0
        self.assertUntraceable('differs from the cited record')

    def test_invented_quote_is_rejected(self):
        a = self.item('cv-thru-calibration', 'transfer')
        a['value'] = a['source']['quote'] = 'VADC=CV'
        self.assertUntraceable('quote not found')

    def test_missing_source_and_valued_unresolved_are_rejected(self):
        self.item('harness-depth', 'depth-target').pop('source')
        self.assertUntraceable('source or derivation')
        self.plan = json.loads((REPO/m.QUAL/'plan.json').read_text())
        self.item('jack-dimensions', 'tolerances')['value'] = 1.0
        self.assertUntraceable('UNRESOLVED')

    def test_plan_and_generated_files_cannot_be_cited(self):
        a = self.item('harness-depth', 'depth-target')
        a['source'] = {'path': str(m.QUAL/'plan.json'), 'quote': '30'}
        a['value'] = '30'
        self.assertUntraceable('not an allowed design source')

    def test_component_facts_only_by_fact_id(self):
        a = self.item('jack-dimensions', 'axis-height')
        a['source'] = {'path': a['source']['path'], 'pointer': '/facts/0/value'}
        a['confidence'] = 'DESIGN'
        self.assertUntraceable('only by fact_id')

    def test_any_stated_confidence_is_enforced(self):
        a = self.item('jack-dimensions', 'axis-band')
        a['confidence'] = 'DESIGN'
        a.pop('confidence_trace')
        self.assertUntraceable('marks this value INFERRED')

    def test_quoted_assumption_cannot_become_design(self):
        a = self.item('jack-dimensions', 'slot-drill')
        a['confidence'] = 'DESIGN'
        a.pop('confidence_trace')
        self.assertUntraceable('quoted line marks this value ASSUMED')

    def test_quote_value_must_be_a_whole_token(self):
        self.item('jack-dimensions', 'slot-drill')['value'] = '1'
        self.assertUntraceable('whole token')

    def test_bound_is_required(self):
        self.item('firmware-waveforms', 'reset').pop('bound')
        self.assertUntraceable('bound must be')

    def test_record_template_must_match_evidence_kinds(self):
        self.proc('switch-fit')['record'].pop('switch_lot')
        self.assertUntraceable('record template')

    def test_owner_action_must_name_real_gates(self):
        self.plan['owner_actions'][0]['unblocks'].append('criterion:no-such-procedure')
        self.assertUntraceable('unknown gate')
        self.plan = json.loads((REPO/m.QUAL/'plan.json').read_text())
        self.plan['owner_actions'][0]['unblocks'].append('assembly:no-such-blocker')
        self.assertUntraceable('unknown gate')

    def test_gates_partition_blockers_and_owner_gates_have_actions(self):
        report = m.evaluate(REPO, self.plan, json.loads((REPO/m.QUAL/'records.json').read_text()))
        self.assertEqual(sum(len(g['reasons']) for g in report['gates']), len(report['blockers']))
        self.assertTrue(all(g['class'] in m.CLASSES for g in report['gates']))
        self.assertEqual(sum(report['gate_counts'].values()), len(report['gates']))
        self.assertTrue(any(g['gate'].startswith('assembly:') for g in report['gates']))
        m.checklist(self.plan, report)
        for a in self.plan['owner_actions']:
            a['unblocks'] = [g for g in a['unblocks'] if g != 'owner_prototype_route']
        with self.assertRaisesRegex(ValueError, 'without an owner action'):
            m.checklist(self.plan, report)

    def test_unfilled_run_template_does_not_pass(self):
        report = m.evaluate(REPO, self.plan, json.loads((REPO/m.QUAL/'records.json').read_text()))
        proc = self.proc('jack-continuity')
        run = json.loads(m.run_template(self.plan, report, proc))
        run['run_id'] = 'template-as-is'
        self.assertEqual(run['identities'], {k: v['sha256'] for k, v in report['identities'].items()})
        records = {'schema': 1, 'runs': [run], 'material_observations': []}
        outcome = next(o for o in m.evaluate(REPO, self.plan, records)['procedures'] if o['id'] == 'jack-continuity')
        self.assertEqual(outcome['status'], 'BLOCKED')
        self.assertIn('latest run is not an actual passing BENCH_RECORD', outcome['reasons'])


    def test_derived_value_is_recomputed(self):
        self.item('power-current', 'ilim-min')['value'] = 350.0
        self.assertUntraceable('recomputed derivation')

    def test_cloud_criteria_match_the_historical_a5_calculation(self):
        margins = json.loads((REPO/'engineering/a5/electronics/reports/electrical_margins.json').read_text())['TPS2552_1_RILIM_68k_1percent']
        self.assertEqual(self.item('power-current', 'ilim-min')['value'], round(margins['min_mA'], 1))
        self.assertEqual(self.item('power-current', 'ilim-max')['value'], round(margins['max_mA'], 1))
        for pid in ('power-current', 'startup-reset', 'u7-stress'):
            self.assertFalse([a['id'] for a in self.proc(pid)['acceptance'] if a['confidence'] in ('UNRESOLVED', 'PROPOSED')])

    def test_derivation_token_and_number_must_match_the_source(self):
        inp = self.item('power-current', 'ilim-min')['derivation']['inputs'][0]
        inp['token'], inp['number'] = '25231', 25231.0
        self.assertUntraceable('not a whole token')
        self.plan = json.loads((REPO/m.QUAL/'plan.json').read_text())
        self.item('power-current', 'ilim-min')['derivation']['inputs'][0]['number'] = 25000.0
        self.assertUntraceable('number differs from the token')

    def test_derivation_allows_only_arithmetic_on_inputs(self):
        self.item('power-current', 'ilim-min')['derivation']['expression'] = 'A / 3'
        self.assertUntraceable('expression may use only')
        self.plan = json.loads((REPO/m.QUAL/'plan.json').read_text())
        self.item('power-current', 'ilim-min')['derivation']['expression'] = '__import__("os")'
        self.assertUntraceable('expression may use only')

    def test_derived_confidence_follows_the_weakest_input(self):
        self.item('u7-stress', 'in-current-bound')['confidence'] = 'CALCULATED'
        self.assertUntraceable('allow only INFERRED')
        self.plan = json.loads((REPO/m.QUAL/'plan.json').read_text())
        self.item('service-envelope', 'retention-force')['basis_confidence'] = 'CALCULATED'
        self.assertUntraceable('allow only MIRROR')
        self.plan = json.loads((REPO/m.QUAL/'plan.json').read_text())
        self.item('u7-stress', 'in-current-bound')['derivation'].pop('assumption')
        self.item('u7-stress', 'in-current-bound')['confidence'] = 'CALCULATED'
        m.schema(self.plan, {'schema': 1, 'runs': [], 'material_observations': []})

    def test_calculated_needs_a_derivation(self):
        self.item('startup-reset', 'no-retry')['confidence'] = 'CALCULATED'
        self.assertUntraceable('CALCULATED needs a derivation')

    def test_netlist_value_must_name_a_real_component(self):
        self.item('power-current', 'rilim')['value'] = '67k'
        self.assertUntraceable('whole token')
        self.plan = json.loads((REPO/m.QUAL/'plan.json').read_text())
        self.item('power-current', 'rilim')['source']['netlist_value'] = 'R999'
        self.assertUntraceable('netlist component missing')
        self.plan = json.loads((REPO/m.QUAL/'plan.json').read_text())
        self.item('power-current', 'rilim')['source']['path'] = 'engineering/a7/README.md'
        self.assertUntraceable('netlist_value cites only')

    def test_proposal_needs_rationale_and_its_true_basis(self):
        self.item('harness-depth', 'bend-radius').pop('rationale')
        self.assertUntraceable('PROPOSED needs a rationale')
        self.plan = json.loads((REPO/m.QUAL/'plan.json').read_text())
        self.item('harness-depth', 'bend-radius')['basis_confidence'] = 'SOURCED'
        self.assertUntraceable('cannot make a value SOURCED')
        self.plan = json.loads((REPO/m.QUAL/'plan.json').read_text())
        self.item('harness-depth', 'depth-target')['rationale'] = 'not a proposal'
        self.assertUntraceable('only PROPOSED items')

    def test_evidence_hold_criteria_say_what_supplies_them(self):
        holds = [p for p in self.plan['procedures'] if p['criterion_class'] == 'ACCESS_EVIDENCE_HOLD']
        self.assertEqual(len(holds), 7)
        for p in holds:
            self.assertTrue(all(a['supplied_by']['what'] for a in p['acceptance'] if a['confidence'] == 'UNRESOLVED'))
        self.item('ldo-reverse', 'reverse').pop('supplied_by')
        self.assertUntraceable('which document or measurement')
        self.plan = json.loads((REPO/m.QUAL/'plan.json').read_text())
        self.item('ldo-reverse', 'reverse')['supplied_by']['kind'] = 'GUESS'
        self.assertUntraceable('supplied_by needs kind')

    def test_checklist_is_one_ordered_list_with_proposals(self):
        report = m.evaluate(REPO, self.plan, json.loads((REPO/m.QUAL/'records.json').read_text()))
        page = m.checklist(self.plan, report)
        numbered = [line for line in page.splitlines() if re.match(r'^\d+\. ', line)]
        self.assertEqual([line.split('**')[1] for line in numbered], [a['id'] for a in self.plan['owner_actions']])
        proposals = [a for p in self.plan['procedures'] for a in p['acceptance'] if a['confidence'] == 'PROPOSED']
        self.assertIn('（' + str(len(proposals)) + ' 件）', page)


class ProducerBindingTests(unittest.TestCase):
    def test_fake_artifact_even_with_rebound_hash_is_rejected_by_real_producer(self):
        for key in ['fixture','assembly_manifest']:
            with self.subTest(key=key):
                candidate = {'inputs_sha256': {'AGENTS.md':m.digest(REPO/'AGENTS.md')},
                             'digital_fixture_complete':True, 'fresh_native_verified':True, 'blockers':[]}
                self.assertTrue(m.artifact_errors(key, candidate, REPO))

    def test_population_deletion_and_fixture_completion_tampering_rejected(self):
        for key in ['fixture','assembly_manifest']:
            candidate = json.loads((REPO/m.IDENTITY_PATHS[key]).read_text())
            if key == 'assembly_manifest': candidate['population'].pop()
            else: candidate['digital_fixture_complete']=True
            self.assertTrue(m.artifact_errors(key, candidate, REPO))


if __name__ == '__main__':
    unittest.main()
