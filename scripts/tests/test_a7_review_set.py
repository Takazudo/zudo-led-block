"""A recorded review set must stay byte-identical, labelled REVIEW_ONLY and bound to one board identity set."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('review_set', ROOT / 'scripts/a7_review_set.py')
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
CURRENT = json.loads((ROOT / R.PKG / 'package-sets.json').read_text())['current']


@unittest.skipIf(CURRENT is None, 'no current review set')
class ReviewSetTests(unittest.TestCase):
    def copy(self, d):
        root = Path(d)
        shutil.copytree(ROOT / CURRENT, root / CURRENT)
        return root

    def test_current_set_verifies(self):
        self.assertEqual(R.verify(CURRENT), [])

    def test_changed_gerber_bytes_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.copy(d)
            z = root / CURRENT / 'controller/controller-panel-gerbers-DRYRUN.zip'
            z.write_bytes(z.read_bytes() + b'\0')
            self.assertTrue(any('SHA256SUMS' in e for e in R.verify(CURRENT, root)))

    def test_relabelled_or_rebound_identities_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.copy(d)
            f = root / CURRENT / 'identities.json'
            ident = json.loads(f.read_text())
            ident['label'] = 'PROTOTYPE_UPLOAD_APPROVED'
            ident['identities']['board']['sha256'] = '0' * 64
            f.write_text(json.dumps(ident))
            errors = R.verify(CURRENT, root)
            self.assertTrue(any('label' in e for e in errors))
            self.assertTrue(any('different boards' in e for e in errors))

    def test_package_index_binds_the_same_boards(self):
        index = json.loads((ROOT / R.PKG / 'package-sets.json').read_text())
        entry = next(s for s in index['sets'] if s['path'] == CURRENT)
        lay = json.loads((ROOT / CURRENT / 'identities.json').read_text())['panel_layouts']
        self.assertEqual(entry['boards'], {b: lay[b]['board_sha256'] for b in R.BOARDS})


if __name__ == '__main__':
    unittest.main()
