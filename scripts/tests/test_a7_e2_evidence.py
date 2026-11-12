"""Guard source recovery boundaries: evidence acquisition cannot qualify hardware."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
BUNDLES = ROOT / '.claude/skills'


def bundle(name, filename):
    return json.loads((BUNDLES / ('component-' + name) / filename).read_text())


class E2EvidenceTests(unittest.TestCase):
    def test_primary_acquisition_receipts_are_exact_and_located(self):
        expected = {
            'a7-pcm13smtr': ('src-a7-pcm13smtr-ck-site', '6a758d151b7eee7f8cd59594bd92cfec4c9b1470e0743094f185f19e7ac2a868'),
            'stm32g031g8u6tr': ('src-stm32g031g8u6tr-ds', '0e25cbbf2cd173845545b61b91a9a7011724b4e5bd7b00498176129d48684e99'),
            'spm4020t-4r7m-lr': ('src-spm4020t-4r7m-lr-catalog', 'ccd41133d18978b389e68067fb9abf4c4229f78910a6c5e074600bcd78889c1f'),
            '530470310': ('src-530470310-sd', '76d2a5817a01b47f4b35c0b4078d874834f1f9c233bde42d9a819ead173929c7'),
        }
        for name, (sid, digest) in expected.items():
            with self.subTest(name=name):
                source = next(s for s in bundle(name, 'sources.json')['sources'] if s['source_id'] == sid)
                self.assertEqual(source['sha256'], digest)
                self.assertEqual(source['authority_class'], 'MANUFACTURER_PRIMARY')
                self.assertEqual(source['availability'], 'AVAILABLE')
                self.assertNotIn('not acquired', source['revision'])
                self.assertRegex(source['locator'], r'printed|sheet')
                self.assertIn('not redistributed', source['retained_bytes'])

    def test_supplier_conflict_does_not_promote_or_rewrite_mapping(self):
        facts = bundle('a7-pj-324m', 'facts.json')['facts']
        conflict = next(f for f in facts if f['fact_id'].endswith('supplier-cad-conflict'))
        self.assertEqual(conflict['provenance'], 'UNVERIFIED')
        self.assertEqual(conflict['verdict'], 'NEEDS BENCH')
        coverage = next(c for c in bundle('a7-pj-324m', 'coverage.json')['coverage'] if c['domain'] == 'pinout')
        self.assertEqual(coverage['status'], 'OPEN')
        self.assertIn(conflict['fact_id'], coverage['blocking_fact_ids'])
        pins = {p['symbol_pin']: p['name'] for p in bundle('a7-pj-324m', 'pin-map.json')['pin_maps'][0]['pins']}
        self.assertEqual(pins['4'], 'TIP (inferred)')
        self.assertEqual(pins['5'], 'TIP normal (inferred)')
        receipt = bundle('a7-pj-324m', 'references/easyeda-c22355739-receipt.json')
        source = next(s for s in bundle('a7-pj-324m', 'sources.json')['sources'] if s['source_id'] == conflict['source_id'])
        self.assertEqual(receipt['acquisition']['sha256']['easyeda-C22355739.json'], source['sha256'])
        self.assertFalse(receipt['publication']['preview_selected'])
        self.assertFalse(receipt['publication']['download_published'])
        self.assertIsNone(receipt['cad_use']['footprint'])

    def test_open_pcm_qualification_has_explicit_blocking_facts(self):
        facts = {f['fact_id']: f for f in bundle('a7-pcm13smtr', 'facts.json')['facts']}
        for coverage in bundle('a7-pcm13smtr', 'coverage.json')['coverage']:
            if coverage['status'] == 'OPEN':
                self.assertTrue(coverage['blocking_fact_ids'], coverage['domain'])
                for fid in coverage['blocking_fact_ids']:
                    self.assertIn(facts[fid]['verdict'], ('NEEDS BENCH', 'UNSOURCED'))
        receipt = bundle('a7-pj-324m', 'references/easyeda-c22355739-receipt.json')
        self.assertIsNone(receipt['fidelity']['class'])
        self.assertIn('Q2 TS/TRS continuity and manufacturer pin map', receipt['checks']['remaining_physical_checks'])
        self.assertIn('Q3 lead dimensions and finished-hole/slot fit', receipt['checks']['remaining_physical_checks'])

    def test_recovered_drawing_does_not_claim_electrical_ratings(self):
        facts = bundle('530470310', 'facts.json')['facts']
        sources = {s['source_id']: s for s in bundle('530470310', 'sources.json')['sources']}
        ratings = next(f for f in facts if f['fact_id'].endswith('-ratings'))
        self.assertNotEqual(ratings['source_id'], 'src-530470310-sd')
        self.assertEqual(sources[ratings['source_id']]['document_number'], '510211110-PS')
        self.assertEqual(ratings['verdict'], 'PASS - primary-source confirmed')


if __name__ == '__main__':
    unittest.main()
