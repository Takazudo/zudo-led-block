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

 def test_fixture_materials_class_follows_the_fixture_manifest(self):
  def cls(**flags):
   with self.mutate_json(P.FIXTURE_MANIFEST,lambda d:d.update(flags)):
    return next(b for b in P.generate()['blockers'] if b['id']=='fixture-materials')
  # Digital design or the hardware proposal still open: cloud work.
  self.assertEqual(cls(digital_criteria_1_to_4_met=False,hardware_proposal_complete=True)['class'],'CLOUD_DIGITAL')
  self.assertEqual(cls(digital_criteria_1_to_4_met=True,hardware_proposal_complete=False)['class'],'CLOUD_DIGITAL')
  self.assertIn('hardware_proposal_complete not true',cls(digital_criteria_1_to_4_met=True,hardware_proposal_complete=False)['text'])
  # Both met: only the fabricator choice and hardware approval remain, which are the owner's.
  self.assertEqual(cls(digital_criteria_1_to_4_met=True,hardware_proposal_complete=True)['class'],'OWNER_DECISION')
  self.assertIn(P.FIXTURE_MANIFEST,self.report['inputs_sha256'])

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

 def test_assembly_process_from_native_pads(self):
  process={b['board']:b['assembly_process_per_board'] for b in self.report['boards']}
  self.assertEqual(process['controller'],{'SMD_F':31,'SMD_B':25,'THT_F':3,'THT_B':0})
  self.assertEqual(process['led_leaf'],{'SMD_F':10,'SMD_B':0,'THT_F':0,'THT_B':0})
  self.assertEqual(process['power_adapter'],{'SMD_F':0,'SMD_B':0,'THT_F':2,'THT_B':0})
  rows={(r['board'],r['ref']):r for r in self.report['population']}
  self.assertEqual({k[1] for k,r in rows.items() if r['mount']=='THT' and k[0]=='controller'},{'J1','J2','J5'})
  self.assertEqual(rows[('controller','SW1')]['mount'],'SMD')
  self.assertEqual(self.report['unique_fitted_identities'],30)

 def test_native_geometry_bound_to_board(self):
  with self.mutate_json(P.NATIVE_GEOMETRY,lambda d:d.update(board_sha256='0'*64)):
   with self.assertRaisesRegex(ValueError,'stale native geometry'):P.generate()
  def flip(d):
   f=next(f for f in d['geometry']['footprints'] if f['ref']=='R1');f['side']='F'
  with self.mutate_json(P.NATIVE_GEOMETRY,flip):
   with self.assertRaisesRegex(ValueError,'side/mount'):P.generate()
  def drop(d):
   d['geometry']['footprints']=[f for f in d['geometry']['footprints'] if f['ref']!='U1']
  with self.mutate_json(P.NATIVE_GEOMETRY,drop):
   with self.assertRaisesRegex(ValueError,'side/mount'):P.generate()

 def test_cable_pin_maps_follow_netlists(self):
  ext={x['id']:x for x in self.report['external_materials']}
  self.assertEqual([(r['a_pin'],r['b_pin'],r['a_net']) for r in ext['finished-power-cable']['pin_map']],
                   [(1,3,'+12V_RAW'),(2,2,'GND'),(3,1,'-12V_RAW')])
  sh4=ext['finished-sh4']['pin_maps']['controller J3 -> left leaf J1']
  self.assertEqual([(r['a_net'],r['b_net']) for r in sh4],[('GND','GND'),('VLED','VLED'),('DATA_L','DATA_IN'),('DATA_R','DATA_OTHER')])
  link=ext['finished-sh4']['pin_maps']['left leaf J2 -> right leaf J1']
  self.assertEqual([(r['a_pin'],r['b_pin'],r['a_net'],r['b_net']) for r in link],
                   [(1,1,'GND','GND'),(2,2,'VLED','VLED'),(3,3,'DATA_OTHER','DATA_IN'),(4,4,'DATA_IN','DATA_OTHER')])
  real=P.pin_nets
  def reversed_adapter(root,netlist,ref):
   nets=real(root,netlist,ref)
   return {'1':nets['3'],'2':nets['2'],'3':nets['1']} if netlist==P.BOARDS['power_adapter'][1] and ref=='J2' else nets
  with patch.object(P,'pin_nets',side_effect=reversed_adapter):
   with self.assertRaisesRegex(ValueError,'net'):P.generate()

 def test_blockers_are_classified(self):
  self.assertTrue(self.report['blockers'])
  for b in self.report['blockers']:
   self.assertIn(b['class'],P.CLASSES)
  self.assertEqual(len({b['id'] for b in self.report['blockers']}),len(self.report['blockers']))

if __name__=='__main__':unittest.main()
