"""A7 router reproducibility check: the copper comparison is exact and the output location is guarded."""
from __future__ import annotations

import subprocess
import sys
import unittest
import tempfile
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(REPO / 'scripts'))
import a7_route_check as rc  # noqa: E402

T = ['/GND', 'F.Cu', 0, 0, 1000000, 0, 200000]
V = ['/GND', 500000, 500000, 500000, 200000]


class CopperDiffTests(unittest.TestCase):
    def test_identical_copper_is_equal(self):
        d = rc.copper_diff({'tracks': [T], 'vias': [V]}, {'tracks': [T], 'vias': [V]})
        self.assertTrue(d['tracks']['equal'] and d['vias']['equal'])

    def test_one_nanometre_moves_are_reported(self):
        moved = T[:4] + [T[4] + 1] + T[5:]
        d = rc.copper_diff({'tracks': [moved], 'vias': [V]}, {'tracks': [T], 'vias': [V]})
        self.assertFalse(d['tracks']['equal'])
        d = rc.copper_diff({'tracks': [T], 'vias': [V[:2] + [V[2] + 1] + V[3:]]}, {'tracks': [T], 'vias': [V]})
        self.assertFalse(d['vias']['equal'])

    def test_missing_or_duplicated_copper_is_reported(self):
        self.assertFalse(rc.copper_diff({'tracks': [T, T], 'vias': [V]}, {'tracks': [T], 'vias': [V]})['tracks']['equal'])
        self.assertFalse(rc.copper_diff({'tracks': [T], 'vias': []}, {'tracks': [T], 'vias': [V]})['vias']['equal'])
        other_net = ['/VLED'] + T[1:]
        self.assertFalse(rc.copper_diff({'tracks': [other_net], 'vias': [V]}, {'tracks': [T], 'vias': [V]})['tracks']['equal'])


class NonEmptyTests(unittest.TestCase):
    def test_empty_board_and_proposal_fail(self):
        empty = {'tracks': [], 'vias': []}
        f = rc.nonempty_failures({'failures': []}, {'board': empty, 'proposal': empty})
        self.assertEqual(len(f), 4)

    def test_router_failures_fail(self):
        full = {'tracks': [T], 'vias': [V]}
        self.assertTrue(rc.nonempty_failures({'failures': ['/VLED']}, {'board': full, 'proposal': full}))
        self.assertTrue(rc.nonempty_failures({}, {'board': full, 'proposal': full}))

    def test_routed_copper_passes(self):
        full = {'tracks': [T], 'vias': [V]}
        self.assertEqual(rc.nonempty_failures({'failures': []}, {'board': full, 'proposal': full}), [])


class OpticalComparisonTests(unittest.TestCase):
    def test_repinning_hash_without_new_contours_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            repo, out = Path(td) / 'repo', Path(td) / 'out'
            out.mkdir()
            for name in rc.OPTICAL_BOARDS:
                current = repo / f'engineering/a7/electronics/{name}/optical-geometry.json'
                current.parent.mkdir(parents=True)
                data = json.dumps({'board_sha256': 'a' * 64, 'polygons': [[0, 0], [1, 1]]})
                current.write_text(data)
                (out / f'optical-{name}.json').write_text(data)
                (out / f'optical-{name}.code').write_text('0')
            self.assertEqual(rc.optical_comparison(out, repo)[1], [])
            # A stale display with a copied current PCB hash must still fail.
            leaf = repo / 'engineering/a7/electronics/led_leaf/optical-geometry.json'
            leaf.write_text(json.dumps({'board_sha256': 'a' * 64, 'polygons': []}))
            self.assertFalse(rc.optical_comparison(out, repo)[0]['led_leaf']['equal'])
            self.assertEqual(len(rc.optical_comparison(out, repo)[1]), 1)


class GuardTests(unittest.TestCase):
    def test_output_inside_repo_is_refused(self):
        p = subprocess.run([sys.executable, str(REPO / 'scripts/a7_route_check.py'), '--out', str(REPO / 'tmp-route-check')],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)
        self.assertIn('outside the repository', p.stderr)
        self.assertFalse((REPO / 'tmp-route-check').exists())

    def test_router_dependency_is_hash_pinned(self):
        req = (REPO / 'scripts/requirements-router.txt').read_text()
        lines = [l for l in req.splitlines() if l and not l.startswith('#')]
        self.assertTrue(lines)
        for l in lines:
            self.assertRegex(l, r'^[a-z0-9_-]+==[0-9.]+ --hash=sha256:[0-9a-f]{64}$')

    def test_review_aid_is_labelled_not_a_release(self):
        self.assertIn('NOT A RELEASE OUTPUT', rc.REVIEW_AID_NOTE)
        ci = (REPO / '.github/workflows/ci.yml').read_text()
        self.assertIn('a7-controller-review-aid-NOT-A-RELEASE', ci)
        self.assertIn('.gbrjob', rc.REVIEW_AID_NOTE)

    def test_route_check_summary_is_kept_as_evidence(self):
        ci = (REPO / '.github/workflows/ci.yml').read_text()
        self.assertIn('${{ runner.temp }}/a7-route-check/summary.json', ci)


if __name__ == '__main__':
    unittest.main()
