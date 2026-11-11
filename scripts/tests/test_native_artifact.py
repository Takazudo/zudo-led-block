"""Retained A7 candidate evidence: only a consistent, correctly bound PASS is VALID_PASS."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

SPEC = importlib.util.spec_from_file_location('a7_native_artifact', Path(__file__).resolve().parents[1] / 'a7_native_artifact.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)

BOARD = 'b' * 64
IMAGE = 'kicad/kicad:10.0.8@sha256:' + 'c' * 64
HEAD, MERGE = '1' * 40, '2' * 40


def h(b):
    return hashlib.sha256(b).hexdigest()


def artifact(status='PASS', failures=(), **over):
    geom = {'outline': [[0, 0], [16.2, 0]], 'footprints': []}
    facts = {'board_sha256': BOARD, 'geometry_sha256': h(json.dumps(geom, sort_keys=True).encode())}
    fb, gb, pb = json.dumps(facts).encode(), json.dumps(geom).encode(), b'{"designs": []}'
    s = {'status': status, 'failures': list(failures), 'board_result': 'candidate: a7_controller',
         'profile': {'kind': 'revision', 'path': m.PROFILE, 'name': 'a7-controller'}, 'image': IMAGE,
         'tested_board_sha256': {'a7_controller': BOARD}, 'plan_sha256': h(pb),
         'identity': {'pr_head_sha': HEAD, 'checkout_head': MERGE, 'github_run_id': '7', 'github_run_attempt': '1',
                      'workflow_ref': 'x/ci.yml@refs/pull/1/merge', 'workflow_sha': MERGE, 'tool_sha256': {'ci': 'd'}},
         'evidence': {'files': {'a7_controller/board_facts.json': h(fb), 'a7_controller/board_geometry.json': h(gb)}}}
    for k, v in over.items():
        s[k] = v
    return {'summary.json': json.dumps(s).encode(), 'plan.json': pb,
            'evidence/a7_controller/board_facts.json': fb, 'evidence/a7_controller/board_geometry.json': gb}


def run(members, **kw):
    kw.setdefault('expect_revision', HEAD)
    kw.setdefault('expect_run_id', '7')
    kw.setdefault('expect_run_attempt', '1')
    return m.classify(members, board_sha=BOARD, image=IMAGE, **kw)


class NativeArtifactTests(unittest.TestCase):
    def test_consistent_pass(self):
        self.assertEqual(run(artifact())['status'], 'VALID_PASS')

    def test_missing_members_incomplete(self):
        for rel in m.REQUIRED[1:]:
            a = artifact(); del a[rel]
            with self.subTest(rel=rel):
                self.assertEqual(run(a)['status'], 'INCOMPLETE')
        self.assertEqual(run({})['status'], 'INCOMPLETE')

    def test_summary_only_artifact_is_incomplete(self):
        a = artifact()
        self.assertEqual(run({'summary.json': a['summary.json']})['status'], 'INCOMPLETE')

    def test_tampered_member_rejected(self):
        for rel in m.REQUIRED[1:]:
            a = artifact(); a[rel] = a[rel] + b' '
            with self.subTest(rel=rel):
                self.assertEqual(run(a)['status'], 'REJECTED')

    def test_wrong_board_rejected(self):
        self.assertEqual(run(artifact(tested_board_sha256={'a7_controller': 'e' * 64}))['status'], 'REJECTED')
        a = artifact()
        facts = json.loads(a['evidence/a7_controller/board_facts.json']); facts['board_sha256'] = 'e' * 64
        fb = json.dumps(facts).encode()
        s = json.loads(a['summary.json']); s['evidence']['files']['a7_controller/board_facts.json'] = h(fb)
        a['evidence/a7_controller/board_facts.json'] = fb; a['summary.json'] = json.dumps(s).encode()
        self.assertEqual(run(a)['status'], 'REJECTED')

    def test_wrong_revision_run_attempt_or_checkout_rejected(self):
        self.assertEqual(run(artifact(), expect_revision='9' * 40)['status'], 'REJECTED')
        self.assertEqual(run(artifact(), expect_run_id='8')['status'], 'REJECTED')
        self.assertEqual(run(artifact(), expect_run_attempt='2')['status'], 'REJECTED')
        self.assertEqual(run(artifact(), expect_checkout='9' * 40)['status'], 'REJECTED')

    def test_infrastructure_substitution_rejected(self):
        a = artifact(profile={'kind': 'infrastructure', 'path': 'scripts/tests/fixtures/native/profile.json'},
                     board_result='NONE: infrastructure run on fixtures; this is not an A7 (or any) board result',
                     status='INFRASTRUCTURE_PASS')
        self.assertEqual(run(a)['status'], 'REJECTED')

    def test_wrong_image_rejected(self):
        self.assertEqual(run(artifact(image='kicad/kicad:9.0.9'))['status'], 'REJECTED')

    def test_failure_evidence_is_never_success(self):
        r = run(artifact(status='FAIL', failures=['DRC violation']))
        self.assertEqual(r['status'], 'VALID_FAILURE_EVIDENCE')
        r = run(artifact(status='PASS', failures=['late failure']))
        self.assertEqual(r['status'], 'VALID_FAILURE_EVIDENCE')

    def test_inconsistent_facts_geometry_rejected(self):
        a = artifact()
        gb = b'{"outline": []}'
        s = json.loads(a['summary.json']); s['evidence']['files']['a7_controller/board_geometry.json'] = h(gb)
        a['evidence/a7_controller/board_geometry.json'] = gb; a['summary.json'] = json.dumps(s).encode()
        self.assertEqual(run(a)['status'], 'REJECTED')

    def test_unlisted_or_extra_member_rejected(self):
        a = artifact(); a['evidence/a7_controller/drc.json'] = b'{}'
        self.assertEqual(run(a)['status'], 'REJECTED')
        a = artifact(); s = json.loads(a['summary.json']); s['evidence']['files'] = {}
        a['summary.json'] = json.dumps(s).encode()
        self.assertEqual(run(a)['status'], 'REJECTED')

    def test_zip_reader_and_unsafe_names(self):
        with tempfile.TemporaryDirectory() as td:
            zp = Path(td) / 'a.zip'
            with zipfile.ZipFile(zp, 'w') as z:
                for k, v in artifact().items():
                    z.writestr('a7-gate/' + k, v)
                z.writestr('native/summary.json', b'{"status": "INFRASTRUCTURE_PASS"}')
            self.assertEqual(run(m.read_members(zip_path=zp))['status'], 'VALID_PASS')
            bad = Path(td) / 'b.zip'
            with zipfile.ZipFile(bad, 'w') as z:
                z.writestr('a7-gate/../x', b'1')
            with self.assertRaises(ValueError):
                m.read_members(zip_path=bad)

    def test_duplicate_or_aliased_zip_members_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            for alias in ('a7-gate/summary.json', 'a7-gate/./summary.json'):
                zp = Path(td) / 'd.zip'
                with zipfile.ZipFile(zp, 'w') as z:
                    for k, v in artifact(status='FAIL', failures=['x']).items():
                        z.writestr('a7-gate/' + k, v)
                    with self.assertWarns(UserWarning) if alias == 'a7-gate/summary.json' else contextlib.nullcontext():
                        z.writestr(alias, artifact()['summary.json'])
                with self.subTest(alias=alias), self.assertRaises(ValueError):
                    m.read_members(zip_path=zp)

    def test_unbound_classification_is_not_a_pass(self):
        r = m.classify(artifact(), board_sha=BOARD, image=IMAGE)
        self.assertEqual(r['status'], 'INCOMPLETE')

    def test_wrong_types_rejected_not_crashing(self):
        for key, value in (('identity', 'x'), ('profile', []), ('evidence', 'x'), ('tested_board_sha256', 'x')):
            with self.subTest(key=key):
                self.assertEqual(run(artifact(**{key: value}))['status'], 'REJECTED')
        for mutate in (lambda s: s['evidence'].update(files=[]), lambda s: s.update(failures='none')):
            a = artifact(); s = json.loads(a['summary.json']); mutate(s)
            a['summary.json'] = json.dumps(s).encode()
            self.assertEqual(run(a)['status'], 'REJECTED')

    def test_pass_requires_explicit_empty_failures(self):
        a = artifact(); s = json.loads(a['summary.json']); del s['failures']
        a['summary.json'] = json.dumps(s).encode()
        self.assertEqual(run(a)['status'], 'VALID_FAILURE_EVIDENCE')

    def test_dir_reader_matches_upload_layout(self):
        with tempfile.TemporaryDirectory() as td:
            for k, v in artifact().items():
                q = Path(td) / 'a7-gate' / k
                q.parent.mkdir(parents=True, exist_ok=True)
                q.write_bytes(v)
            (Path(td) / 'a7-gate/evidence/a7_controller/drc.json').write_bytes(b'{}')
            self.assertEqual(run(m.read_members(dir_path=Path(td)), strict_members=False)['status'], 'VALID_PASS')


if __name__ == '__main__':
    unittest.main()
