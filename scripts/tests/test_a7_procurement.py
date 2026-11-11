"""Population failures must be caught, not hidden by aggregate totals."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('procurement',ROOT/'scripts/a7_procurement.py')
P=importlib.util.module_from_spec(spec);spec.loader.exec_module(P)


class LedgerTests(unittest.TestCase):
 def setUp(self):
  self.report=P.generate()

 def mutate_json(self,path,fn):
  original=P.read
  def changed(root,p):
   data=original(root,p)
   if p==path:fn(data)
   return data
  return patch.object(P,'read',side_effect=changed)

 def test_accounting_and_baseline(self):
  self.assertEqual(self.report['fitted_unique_placements'],71)
  self.assertEqual(self.report['fitted_pieces_per_module'],81)
  self.assertEqual([(b['multiplicity'],b['fitted_per_board']) for b in self.report['boards']],[(1,59),(2,10),(1,2)])
  self.assertEqual(len(self.report['excluded']),5)
  self.assertFalse(self.report['manufacturing_released'])
  self.assertIsNone(self.report['agreed_order_quantity'])
  self.assertFalse(any(r['lcsc'] in ('C500090','C908270') for r in self.report['population']))

 def test_dated_switch_observation(self):
  row=next(r for r in self.report['population'] if r['lcsc']=='C221842')
  obs=row['commercial_observation']
  self.assertEqual((obs['stock_count'],obs['minimum_purchase_quantity'],obs['packaging_quantity']),(0,3,3500))
  self.assertIsNone(obs['price'])
  self.assertIsNone(obs['assembly_acceptance'])
  with self.mutate_json(P.SWITCH_SOURCES,lambda d:d['sources'][-1].update(sha256='0'*64)):
   with self.assertRaisesRegex(ValueError,'receipt changed'):P.generate()

 def test_omitted_inventory_reference(self):
  with self.mutate_json(P.INV,lambda d:d['lines'][0]['placements'].pop(0)):
   with self.assertRaisesRegex(ValueError,'population'):P.generate()

 def test_duplicate_inventory_reference(self):
  with self.mutate_json(P.INV,lambda d:d['lines'][0]['placements'].append(d['lines'][0]['placements'][0])):
   with self.assertRaisesRegex(ValueError,'duplicate'):P.generate()

 def test_unbacked_dnp_exclusion(self):
  with self.mutate_json(P.INV,lambda d:d["lines"][0].update(dnp=True)):
   with self.assertRaisesRegex(ValueError,"DNP"):P.generate()

 def test_stale_identity(self):
  with self.mutate_json(P.INV,lambda d:d['lines'][0].update(mpn='wrong-part')):
   with self.assertRaisesRegex(ValueError,'identity'):P.generate()

 def test_stale_board_export(self):
  with self.mutate_json(P.PLACEMENT,lambda d:d.update(board_sha256='0'*64)):
   with self.assertRaisesRegex(ValueError,'stale'):P.generate()

 def test_missing_or_duplicate_native_placement(self):
  for change in [lambda d:d['components'].pop(),lambda d:d['components'].append(d['components'][0])]:
   with self.mutate_json(P.PLACEMENT,change):
    with self.assertRaises(ValueError):P.generate()

 def test_wrong_native_footprint(self):
  def change(d):
   next(c for c in d['components'] if c['ref']=='J1')['fpid']='LightBlock:PJ3582B'
  with self.mutate_json(P.PLACEMENT,change):
   with self.assertRaisesRegex(ValueError,'footprint'):P.generate()

 def test_wrong_mechanical_variant(self):
  with self.mutate_json(P.MECH,lambda d:d.update(leaf='pet')):
   with self.assertRaisesRegex(ValueError,'variant'):P.generate()

 def test_ledger_mutation_changes_expected_output(self):
  P.validate_report(self.report)
  for change in [lambda d:d['population'].pop(),
                 lambda d:d['population'].append(copy.deepcopy(d['population'][0])),
                 lambda d:d['population'][0].update(mpn='PJ-3582-B'),
                 lambda d:next(r for r in d['population'] if r['board']=='led_leaf').update(board_multiplicity=1,quantity_per_module=1),
                 lambda d:d['inputs_sha256'].update({P.PLACEMENT:'0'*64})]:
   damaged=copy.deepcopy(self.report);change(damaged)
   with self.assertRaisesRegex(ValueError,"population, multiplicity or input identities"):
    P.validate_report(damaged)

 def test_power_cable_and_hardware_from_current_model(self):
  ext={x['id']:x for x in self.report['external_materials']}
  self.assertEqual(ext['finished-power-cable']['requirement'],P.read(ROOT,P.LAYOUT)['power_cable_requirement'])
  self.assertEqual(ext['finished-power-cable']['requirement']['tolerance_confidence'],'ASSUMED')
  self.assertEqual(ext['top_cap_screw_A7']['description'],'M2x18')
  self.assertEqual(ext['finished-sh4']['quantity_per_module'],2)
  self.assertNotIn('top_cap_spacer_A7',ext)
  self.assertNotIn('bottom_cap_fork_A7',ext)

if __name__=='__main__':unittest.main()
