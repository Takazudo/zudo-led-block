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
  self.assertEqual(self.report['agreed_order_quantity'],2)
  self.assertFalse(any(r['lcsc'] in ('C500090','C908270') for r in self.report['population']))

 def test_dated_switch_observation(self):
  line=next(l for l in P.build()[1]['lines'] if l['lcsc']=='C5149819')
  api=line['parts_api']
  self.assertEqual((api['observed']['jlc_stock'],api['observed']['min_purchase'],api['calculated']['pieces_to_buy']),(4561,1,2))
  self.assertEqual(api['raw_sha256'],'f6e3f19ec6c129eb50209701f98ea079945f5eb4dbe17b9c711ab6d5006d1ab9')
  self.assertEqual(line['listing_page']['observed']['packaging_quantity'],3000)
  self.assertEqual(api['currency']['status'],'INFERRED')
  self.assertIn('assembly_acceptance',line['not_obtained'])
  with self.mutate_json(P.SWITCH_SOURCES,lambda d:next(s for s in d['sources'] if s['source_id'].endswith('jlc-api-2026-11-12')).update(sha256='0'*64)):
   with self.assertRaisesRegex(ValueError,'receipt changed'):P.generate()

 def test_owner_order_quantity_drives_the_order_plan(self):
  plan=self.report['order_plan']
  self.assertEqual((plan['modules'],plan['decided_by']),(2,'OWNER'))
  self.assertEqual(plan['pcba_minimum_boards']['status'],'SOURCED')
  self.assertEqual(plan['sourcing_preference']['status'],'PENDING_OWNER_CONFIRMATION')
  self.assertEqual([(b['board'],b['boards_needed']) for b in plan['boards']],[('controller',2),('led_leaf',4),('power_adapter',2)])
  self.assertTrue(plan['attrition'].startswith('NOT_SOURCED'))
  self.assertEqual(sum(l['pieces_required'] for l in plan['lines']),2*self.report['fitted_pieces_per_module'])
  self.assertEqual(sum(l['pieces_required'] for l in plan['lines']),162)
  self.assertNotIn('C221842',[l['lcsc'] for l in plan['lines']])
  self.assertTrue(all(l['sourcing']['route']=='JLC_STOCK' and l['sourcing']['status'].startswith('DATED_LISTING_OBSERVED') for l in plan['lines']))
  self.assertNotIn('order-quantity',[b['id'] for b in self.report['blockers']])


class SourcingProjectionTests(unittest.TestCase):
 """Every active fitted identity reconciles to dated evidence or an explicit gap; nothing is promoted to a quote or current stock."""
 def setUp(self):
  self.report,self.projection=P.build()

 mutate_json=LedgerTests.mutate_json

 def test_active_population_is_the_30_fitted_identities(self):
  pj=self.projection
  self.assertEqual(pj['active_identities'],30)
  self.assertEqual(len({l['lcsc'] for l in pj['lines']}),30)
  self.assertEqual({l['lcsc'] for l in pj['lines']},{r['lcsc'] for r in self.report['population'] if r['population']=='FITTED'})
  self.assertEqual(pj['gaps'],{'listing_page':[],'parts_api':[]})
  self.assertEqual(pj['library_counts']['listing_page'],{'BASIC':14,'EXTENDED':16})
  self.assertEqual(pj['pieces_required_total'],162)

 def test_retired_switch_is_evidence_only(self):
  pj=self.projection
  self.assertNotIn('C221842',[l['lcsc'] for l in pj['lines']])
  self.assertEqual([r['lcsc'] for r in pj['retired']],['C221842'])
  self.assertTrue(all('C221842' not in l['lcsc'] for l in self.report['order_plan']['lines']))
  # The retired part cannot come back into the price audit's current lines.
  def add_retired(d):
   d['after']['lines'].append(dict(d['before']['lines'][0],lcsc='C221842',mpn='PCM13SMTR',manufacturer='C&K'))
  with self.mutate_json(P.PRICE_AUDIT,add_retired):
   with self.assertRaisesRegex(ValueError,'only the current fitted identities'):P.build()

 def test_unknown_or_ambiguous_evidence_is_rejected(self):
  with self.mutate_json(P.LISTING_PAGES,lambda d:d['parts'].append(dict(d['parts'][0]))):
   with self.assertRaisesRegex(ValueError,'ambiguous evidence'):P.build()
  with self.mutate_json(P.LISTING_PAGES,lambda d:d['parts'].append(dict(d['parts'][0],lcsc='C999999'))):
   with self.assertRaisesRegex(ValueError,'outside the fitted population'):P.build()
  with self.mutate_json(P.PRICE_AUDIT,lambda d:d['after']['lines'].append(dict(d['after']['lines'][1]))):
   with self.assertRaisesRegex(ValueError,'ambiguous evidence'):P.build()

 def test_identity_must_match_exactly(self):
  def mpn(d):next(p for p in d['parts'] if p['lcsc']=='C7250')['model']='0603WAF1005T5'
  with self.mutate_json(P.LISTING_PAGES,mpn):
   with self.assertRaisesRegex(ValueError,'names MPN'):P.build()
  def maker(d):next(l for l in d['after']['lines'] if l['lcsc']=='C7250')['manufacturer']='UNI-ROYAL'
  with self.mutate_json(P.PRICE_AUDIT,maker):
   with self.assertRaisesRegex(ValueError,'names manufacturer'):P.build()
  # The reviewed crosswalk spelling is allowed only for the sources it names, not for this receipt file.
  def long_form(d):next(p for p in d['parts'] if p['lcsc']=='C5665')['model']='2.54-2*5P2.54 mm pitch 2×5 pin IDC box header'
  with self.mutate_json(P.LISTING_PAGES,long_form):
   with self.assertRaisesRegex(ValueError,'names MPN'):P.build()

 def test_missing_evidence_becomes_an_explicit_gap(self):
  with self.mutate_json(P.LISTING_PAGES,lambda d:d.update(parts=[p for p in d['parts'] if p['lcsc']!='C7250'])):
   report,pj=P.build()
  line=next(l for l in pj['lines'] if l['lcsc']=='C7250')
  self.assertEqual(line['listing_page']['status'],'GAP')
  self.assertEqual(line['parts_api']['status'],'OBSERVED')
  self.assertEqual(pj['gaps']['listing_page'],['C7250'])
  supply=next(b for b in report['blockers'] if b['id']=='supply-observations')
  self.assertIn('No rendered-page receipt: C7250',supply['text'])
  self.assertEqual(supply['class'],'ACCESS_EVIDENCE_HOLD')
  def no_api(d):d['after']['lines']=[l for l in d['after']['lines'] if l['lcsc']!='C7250']
  with self.mutate_json(P.PRICE_AUDIT,no_api):
   _,pj=P.build()
  self.assertEqual(pj['gaps']['parts_api'],['C7250'])
  self.assertEqual(next(l for l in P.build()[0]['order_plan']['lines'] if l['lcsc']=='C7250')['sourcing']['route'],'JLC_STOCK')

 def test_quantity_semantics_are_not_multiplied_twice(self):
  # The audit's pieces_required must equal fitted pieces x modules; a doubled leaf count is rejected.
  def doubled(d):
   l=next(l for l in d['after']['lines'] if l['lcsc']=='C52917434');l['pieces_required']*=2
  with self.mutate_json(P.PRICE_AUDIT,doubled):
   with self.assertRaisesRegex(ValueError,'quantity semantics'):P.build()
  ws=next(l for l in self.projection['lines'] if l['lcsc']=='C52917434')
  self.assertEqual((ws['pieces_per_module'],ws['pieces_required']),(8,16))

 def test_provenance_and_times_are_kept_per_source(self):
  for l in self.projection['lines']:
   pg,api=l['listing_page'],l['parts_api']
   self.assertRegex(pg['raw_sha256'],'^[0-9a-f]{64}$')
   self.assertFalse(pg['raw_stored'])
   self.assertTrue(pg['observed_at'].startswith('2026-11-12T'))
   self.assertTrue(pg['field_meanings'].startswith('INFERRED'))
   self.assertEqual(api['calculated']['confidence'],'INFERRED')
   self.assertEqual(api['currency']['status'],'INFERRED')
   if l['lcsc']!='C5149819':
    self.assertIsNone(api['raw_sha256'])
    self.assertEqual(api['observed_at'],'2026-11-12T19:09:52Z')
   self.assertEqual(l['not_obtained'],['lead_time','confirmed_quote','stock_reservation','assembly_acceptance'])
  self.assertTrue(self.projection['stock_differs_between_reads'])
  # An audit row time that matches neither the API read nor a hash-bound receipt is rejected.
  def moved(d):next(l for l in d['after']['lines'] if l['lcsc']=='C7250')['retrieved_at']='2026-11-12T23:00:00Z'
  with self.mutate_json(P.PRICE_AUDIT,moved):
   with self.assertRaisesRegex(ValueError,'audit row time'):P.build()

 def test_reports_never_claim_current_stock_quote_or_release(self):
  text=json.dumps(self.report,ensure_ascii=False)
  self.assertNotIn('NOT_OBSERVED',text)
  self.assertNotIn('not observed for any line except',text)
  supply=next(b for b in self.report['blockers'] if b['id']=='supply-observations')
  self.assertEqual(supply['class'],'ACCESS_EVIDENCE_HOLD')
  self.assertIn('30 of 30',supply['text'])
  self.assertIn('lead time, confirmed quote, stock reservation and assembly acceptance',supply['text'])
  self.assertEqual(self.projection['status'],'DATED_OBSERVATIONS_NOT_CURRENT_STOCK_OR_QUOTE')
  self.assertFalse(self.report['manufacturing_released'])
  self.assertFalse(self.report['order_submitted'])
  for name in (P.LISTING_PAGES,P.PRICE_AUDIT,P.SUPPLY_OBSERVATIONS):
   self.assertIn(name,self.report['inputs_sha256'])
  self.assertNotIn('engineering/a7/jlc-package/package.json',self.report['inputs_sha256'])

 def test_outputs_are_reproducible(self):
  a=P.outputs(*P.build());b=P.outputs(*P.build())
  self.assertEqual(a,b)
  for name,contents in a.items():
   self.assertEqual((ROOT/P.OUT/name).read_text(),contents,name)


 def test_order_quantity_must_be_the_owners_own_record(self):
  cases=({'decided_by':'AGENT'},{'owner_words':[]},{'owner_words':['we will make 3 units']},{'owner_messages':[]},
   {'modules':3,'answer':'3'},{'modules':0,'answer':'0'},{'answer':'3'},{'basis':{'claim':'x','pcba_minimum_boards':2,'status':'SOURCED','check':'x','source':None}})
  for change in cases:
   with self.subTest(change):
    with self.mutate_json(P.OWNER_DECISIONS,lambda d:d['decisions'][0].update(change)):
     with self.assertRaisesRegex(ValueError,'order-quantity decision'):P.generate()
  for name,fn in {'reordered':lambda d:d['sourcing_preference']['interpretation']['order'].reverse(),
                  'reading claimed as the owner':lambda d:d['sourcing_preference']['interpretation'].update(interpreted_by='OWNER'),
                  'reading marked confirmed':lambda d:d['sourcing_preference']['interpretation'].update(status='CONFIRMED')}.items():
   with self.subTest(name):
    with self.mutate_json(P.OWNER_DECISIONS,fn):
     with self.assertRaisesRegex(ValueError,'sourcing preference'):P.generate()

 def test_changed_switch_listing_is_rejected(self):
  with self.mutate_json(P.SUPPLY_OBSERVATIONS,lambda d:next(o for o in d['observations'] if o['lcsc']=='C5149819')['values'].update(jlc_stock=5)):
   with self.assertRaisesRegex(ValueError,'switch listing observation changed'):P.generate()

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

 def test_owner_decisions_retire_only_their_own_blockers(self):
  ids={b['id'] for b in self.report['blockers']}
  self.assertNotIn('panel-route',ids)
  self.assertNotIn('finished-cables',ids)
  # The owner directed a working, low-price, in-stock switch, which retires the switch supply decision.
  self.assertNotIn('switch-supply',ids)
  with self.mutate_json(P.OWNER_DECISIONS,lambda d:next(x for x in d['decisions'] if x['id']=='switch-supply').update(answer='wait')):
   with self.assertRaisesRegex(ValueError,'answer outside'):P.generate()
  jack=next(b for b in self.report['blockers'] if b['id']=='jack-switch-qualification')
  self.assertIn('waived the pre-order continuity test',jack['text'])
  self.assertIn('first-article',jack['text'])
  self.assertNotIn('must precede any PCB order',jack['text'])
  rack=next(b for b in self.report['blockers'] if b['id']=='rack-hardware')
  self.assertIn('case model',rack['text'])

 def test_owner_decision_without_owner_messages_is_rejected(self):
  def strip(d):
   for x in d['decisions']:
    if x['id']=='jack-tip-test-waiver':x['owner_words']=['paraphrase']
  with self.mutate_json(P.OWNER_DECISIONS,strip):
   with self.assertRaisesRegex(ValueError,'own dated messages'):
    P.generate()

 def test_retired_answer_must_be_a_known_option(self):
  def bad(d):
   for x in d['decisions']:
    if x['id']=='finished-cables':x['answer']='whatever'
  with self.mutate_json(P.OWNER_DECISIONS,bad):
   with self.assertRaisesRegex(ValueError,'answer outside'):
    P.generate()

if __name__=='__main__':unittest.main()
