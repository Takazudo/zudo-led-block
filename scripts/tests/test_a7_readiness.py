"""Synthetic records stay in temporary test roots; never real qualification evidence."""
import copy
import datetime as dt
import hashlib
import importlib.util
import json
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
            p['criterion_review'] = self.receipt
        ids = {k: v['sha256'] for k, v in m.identities(self.root).items()}
        ph = hashlib.sha256(json.dumps(self.plan, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        for p in self.plan['procedures']:
            run = {k: 'synthetic context' for k in ['unit_id','operator','instruments','setup','conditions',
                   'observations','criterion_comparison','next_action','assembly_deviations']}
            raw = []
            for kind in m.REQUIRED_EVIDENCE[p['id']]:
                f = self.root/(p['id']+'-'+kind+'.txt')
                f.write_text('SYNTHETIC '+kind)
                raw.append({'kind':kind, 'path':f.name, 'sha256':m.digest(f)})
            run.update(run_id=p['id']+'-synthetic', procedure=p['id'], evidence_kind='BENCH_RECORD',
                       synthetic=False, result='PASS', identities=ids, plan_sha256=ph,
                       performed_at='2026-11-08T12:00:00Z', raw_evidence=raw, review=self.receipt)
            self.records['runs'].append(run)
        self.records['material_observations'] = [dict(material=k, observed_on='2026-11-08',
            valid_until='2026-11-10', identities=ids, available_for_proposed_order=True, source=self.receipt) for k in m.MATERIALS]
        self.records['owner_prototype_route'] = dict(identities=ids, scope='synthetic', quantity='1', constraints='synthetic', approval=self.receipt)
        self.records['manufacturing_release'] = dict(identities=ids, approval=self.receipt, reviewed_order_files=self.receipt)

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
