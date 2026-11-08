"""Production container-run and cleanup path of scripts/a6_native_verify.py, driven by a fake docker CLI.

These exercise run_container / cleanup_owned themselves (no stand-in lambdas) and use explicit
self.assert* methods, so they behave the same under python -O.
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import a6_native_verify as nv  # noqa: E402
import a6_native_inner as ni  # noqa: E402

LBL = 'test-run-label'


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.out = Path(self.td.name)
        self.g = nv.Gate(self.out, self.out, 60)
        self.g.receipt('STARTED_INCOMPLETE')

    def tearDown(self):
        self.td.cleanup()

    def run_with(self, fake, budget=5.0, reserve=5.0):
        p = self.out / 'plan.json'
        p.write_text('{}')
        return nv.run_container(self.g, 'img', self.out, self.out, p, budget, reserve, dk=fake, run_label=LBL)

    def receipt(self):
        return json.loads((self.out / 'summary.json').read_text())

    def test_normal_run_removes_owned_container(self):
        fake = nv.FakeDocker(LBL)
        info = self.run_with(fake)
        self.assertTrue(info['cleanup_verified'])
        self.assertEqual(info['cleanup']['removed'], ['c1'])
        self.assertEqual(nv.cleanup_failures(info), [])
        self.assertEqual(self.receipt()['status'], 'CLEANED_INCOMPLETE')

    def test_run_and_kill_both_time_out_still_cleans_up(self):
        fake = nv.FakeDocker(LBL, run_timeout=True, kill_timeout=True)
        info = self.run_with(fake)
        self.assertTrue(info['timed_out'])
        self.assertIn('error', info['kill'])
        self.assertIn('rm', fake.calls)
        self.assertTrue(info['cleanup_verified'])
        self.assertEqual(self.receipt()['container']['cleanup']['removed'], ['c1'])

    def test_rm_failure_gives_failure_receipt(self):
        fake = nv.FakeDocker(LBL, rm_fails=True)
        info = self.run_with(fake)
        self.assertFalse(info['cleanup_verified'])
        self.assertTrue(nv.cleanup_failures(info))
        self.assertEqual(self.receipt()['status'], 'CLEANUP_FAILED_INCOMPLETE')

    def test_status_failure_gives_failure_receipt(self):
        fake = nv.FakeDocker(LBL, ps_fails=True)
        info = self.run_with(fake)
        self.assertFalse(info['cleanup_verified'])
        self.assertTrue(info['cleanup']['errors'])
        self.assertEqual(self.receipt()['status'], 'CLEANUP_FAILED_INCOMPLETE')

    def test_foreign_container_is_never_removed(self):
        fake = nv.FakeDocker(LBL, foreign=True)
        info = self.run_with(fake)
        self.assertEqual(fake.rm_calls, 0)
        self.assertEqual(info['cleanup']['refused'], ['c1'])
        self.assertFalse(info['cleanup_verified'])

    def test_no_budget_refuses_to_run_but_still_checks_cleanup(self):
        fake = nv.FakeDocker(LBL)
        info = self.run_with(fake, budget=0)
        self.assertNotIn('run', fake.calls)
        self.assertIn('run_error', info)
        self.assertIn('ps', fake.calls)

    def test_exhausted_reserve_is_not_extended(self):
        fake = nv.FakeDocker(LBL)
        c = nv.cleanup_owned(LBL, time.monotonic() - 1, fake)
        self.assertFalse(c['verified'])
        self.assertEqual(fake.calls, [])
        self.assertIn('cleanup reserve exhausted', c['errors'][0])

    def test_missing_cleanup_record_fails(self):
        self.assertTrue(nv.cleanup_failures({}))
        self.assertTrue(nv.cleanup_failures({'cleanup': {'verified': 'yes'}}))



class _Pt:
    def __init__(self, x, y):
        self.x, self.y = x, y


class _Chain:
    def __init__(self, pts):
        self.pts = [_Pt(*q) for q in pts]

    def PointCount(self):
        return len(self.pts)

    def CPoint(self, i):
        return self.pts[i]


class FillFingerprintTests(unittest.TestCase):
    SQ = [(0, 0), (10, 0), (10, 10), (0, 10)]

    def test_rotation_and_direction_do_not_change_the_ring(self):
        a = ni.canonical_ring(_Chain(self.SQ))
        self.assertEqual(a, ni.canonical_ring(_Chain(self.SQ[2:] + self.SQ[:2])))
        self.assertEqual(a, ni.canonical_ring(_Chain(list(reversed(self.SQ)))))

    def test_shift_with_same_area_and_vertex_count_changes_the_ring(self):
        moved = [(x + 5, y) for x, y in self.SQ]
        self.assertEqual(len(moved), len(self.SQ))
        self.assertNotEqual(ni.canonical_ring(_Chain(self.SQ)), ni.canonical_ring(_Chain(moved)))


if __name__ == '__main__':
    unittest.main()
