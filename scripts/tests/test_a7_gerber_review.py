"""Review identity checks must reject stale A5 leaf and changed export bytes."""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('gerber_review', ROOT / 'scripts/a7_gerber_review.py')
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)


class ReviewIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        optical = Path('engineering/a7/verification/optical')
        shutil.copytree(ROOT / optical, self.root / optical)
        for name in ['scripts/a7_gerber_review.py',
                     'engineering/a7/electronics/led_leaf/led_leaf.kicad_pcb']:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        self.receipt = self.root / optical / 'led_leaf/export-receipt.json'

    def test_current_identity(self):
        self.assertGreater(REVIEW.verify_receipt(self.receipt, self.root), 0)

    def test_a5_leaf_copied_over_current_leaf(self):
        shutil.copy2(ROOT / 'engineering/a5/electronics/native/led_leaf/led_leaf.kicad_pcb',
                     self.root / 'engineering/a7/electronics/led_leaf/led_leaf.kicad_pcb')
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            REVIEW.verify_receipt(self.receipt, self.root)

    def test_modified_gerber_and_extra_job(self):
        gerbers = self.receipt.parent / 'gerbers'
        target = next(gerbers.glob('*.gts'))
        target.write_bytes(target.read_bytes() + b'\nG04 changed*\n')
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            REVIEW.verify_receipt(self.receipt, self.root)
        (gerbers / 'unexpected.gbrjob').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            REVIEW.verify_receipt(self.receipt, self.root)


if __name__ == '__main__':
    unittest.main()
