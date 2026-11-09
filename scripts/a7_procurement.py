#!/usr/bin/env python3
"""Generate preparation data, never supplier-upload or hardware release data."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = Path('engineering/a7/procurement')
INV = '.claude/skills/component-spec-audit/references/inventory.json'
PLACEMENT = 'engineering/a7/electronics/controller/board_placement.json'
LAYOUT = 'engineering/a7/mechanical/layout.json'
MECH = 'engineering/a7/mechanical/exports/3hp/verification.json'
A5POS = 'engineering/a5/electronics/placement_and_connectivity.json'
BOARDS = {
 'controller': (1, 'engineering/a7/verification/schematic/netlist.xml', 'engineering/a7/electronics/controller/controller.kicad_pcb'),
 'led_leaf': (2, 'engineering/a5/integration/native_schematic/led_leaf/netlist.xml', 'engineering/a5/electronics/native/led_leaf/led_leaf.kicad_pcb'),
 'power_adapter': (1, 'engineering/a5/integration/native_schematic/power_adapter/netlist.xml', 'engineering/a5/electronics/native/power_adapter/power_adapter.kicad_pcb'),
}


def read(root, path):
 return json.loads((root/path).read_text())


def sha(root, path):
 return hashlib.sha256((root/path).read_bytes()).hexdigest()


def unique(rows, key):
 result = {}
 for row in rows:
  if row[key] in result:
   raise ValueError(f'duplicate {key}: {row[key]}')
  result[row[key]] = row
 return result


SWITCH_SOURCES = '.claude/skills/component-a7-pcm13smtr/sources.json'


def switch_observation(root):
 sources = read(root, SWITCH_SOURCES)['sources']
 source = next(s for s in sources if s['source_id']=='src-a7-pcm13smtr-jlc-stock-2026-11-09')
 if source['sha256']!='317f74ac9caf4556aef05b61c78dde4c6ae9b89974bf03a51cee9db51b71aa17' or source['retrieved_at']!='2026-11-09T09:18:55Z' or source['availability']!='AVAILABLE':
  raise ValueError('switch supply receipt changed; re-review observation')
 for term in ('C221842 PCM13SMTR C&K', 'stockCount0', 'canPresaleNumber0', 'minPurchaseNum3', 'encapsulationNumber3500', 'estimateDate null'):
  if term not in source['evidence_extract']:
   raise ValueError('switch supply extract changed; re-review observation')
 return {'source_bundle':SWITCH_SOURCES,'source_id':source['source_id'],'url':source['authoritative_url'],
  'raw_sha256':source['sha256'],'observed_at':source['retrieved_at'],'supplier':'JLCPCB',
  'stock_count':0,'presale_count':0,'minimum_purchase_quantity':3,'packaging_quantity':3500,
  'price':None,'currency':None,'lead_time':None,'assembly_acceptance':None,'reserved':False,
  'scope':'Dated exact C221842 listing observation only; refresh before procurement. No currency-backed price or assembly acceptance.'}


def generate(root=ROOT):
 inv = read(root, INV)
 unique(inv['lines'], 'line_id')
 assigned = {b: {} for b in BOARDS}
 for line in inv['lines']:
  for p in line['placements']:
   b, ref = p['board'], p['refdes']
   if b == 'controller' and ref in ('J1', 'J2', 'SW1'):
    continue
   if b == 'a7-controller':
    b = 'controller'
   if b not in assigned:
    continue
   if ref in assigned[b]:
    raise ValueError(f'duplicate inventory placement: {b}/{ref}')
   assigned[b][ref] = line
 placement = read(root, PLACEMENT)
 if placement['board'] != BOARDS['controller'][2] or placement['board_sha256'] != sha(root, BOARDS['controller'][2]):
  raise ValueError('stale controller placement identity')
 pmap = unique(placement['components'], 'ref')
 inherited = {b['name']: b for b in read(root, A5POS)['boards']}
 inputs = [SWITCH_SOURCES, INV, PLACEMENT, LAYOUT, MECH, A5POS, 'engineering/a7/electronics/controller/controller.kicad_sch',
           'engineering/a5/integration/harness_contract_A5.md', 'engineering/a7/mechanical/build_a7_mechanical.py']
 observation = switch_observation(root)
 rows, excluded, boards = [], [], []
 for name, (mult, netlist, pcb) in BOARDS.items():
  inputs += [netlist, pcb]
  byref = unique([{'ref': c.attrib['ref'], 'xml': c} for c in ET.parse(root/netlist).getroot().findall('components/comp')], 'ref')
  testpads = {'TP1','TP2','TP3','TP4','TP5'} if name == 'controller' else set()
  if set(byref) != set(assigned[name]) | testpads:
   raise ValueError(f'{name} omitted/unexpected population')
  positions = pmap if name == 'controller' else unique(inherited[name]['components'], 'ref')
  if {r for r,p in positions.items() if not p.get('board_only',False)} != set(byref):
   raise ValueError(f'{name} placement/netlist population mismatch')
  for ref,obj in sorted(byref.items()):
   c = obj['xml']
   if ref in testpads:
    if c.findtext('footprint') != 'LightBlock:TESTPAD':
     raise ValueError('testpad exclusion has changed footprint')
    excluded.append({'board':name,'ref':ref,'reason':'bare copper test pad, no purchased component'})
    continue
   fields = {f.attrib['name']:f.text or '' for f in c.findall('fields/field')}
   line = assigned[name][ref]
   if (fields.get('MPN'),fields.get('LCSC')) != (line['mpn'],line['lcsc']):
    raise ValueError(f'{name}/{ref}: exact identity differs between netlist and catalog')
   if name == 'controller' and line['lcsc'] in ('C500090','C908270'):
    raise ValueError('obsolete A5 controller part')
   pos = positions[ref]
   if name == 'controller' and pos['fpid'] != c.findtext('footprint'):
    raise ValueError(f'{name}/{ref}: native footprint mismatch')
   dnp = line['dnp']
   if not isinstance(dnp,bool):
    raise ValueError('DNP must be boolean')
   native_dnp = any(p.attrib.get('name') == 'dnp' for p in c.findall('property'))
   if dnp != native_dnp:
    raise ValueError(f'{name}/{ref}: DNP differs between netlist and catalog')
   rows.append({'board':name,'ref':ref,'manufacturer':line['manufacturer'],'mpn':line['mpn'],'lcsc':line['lcsc'],
    'package':line['package'],'line_id':line['line_id'],'owner_skill':line['owner_skill'],'footprint':c.findtext('footprint'),
    'population':'DNP' if dnp else 'FITTED','quantity_per_board':0 if dnp else 1,'board_multiplicity':mult,'quantity_per_module':0 if dnp else mult,
    'placement':{'side':pos['side'],'at_mm':pos.get('at_mm',pos.get('at')),'angle_deg':pos.get('angle_deg',pos.get('angle')),
     'source':PLACEMENT if name=='controller' else A5POS,
     'authority':'native export; independent fresh gate required' if name=='controller' else 'immutable historical A5 KiCad export; not fresh placement proof'},
    'commercial_observation':observation if line['lcsc']=='C221842' else None,'supply_status':('BLOCKED: dated JLC stock 0 / presale 0; price, lead time and assembly acceptance unknown' if line['lcsc']=='C221842' else 'NOT_OBTAINED: current stock, price, lead time, MOQ, packaging and assembly applicability require dated exact-part evidence')})
  boards.append({'board':name,'multiplicity':mult,'pcb':pcb,'pcb_sha256':sha(root,pcb),'netlist':netlist,'netlist_sha256':sha(root,netlist),
   'fitted_per_board':sum(r['quantity_per_board'] for r in rows if r['board']==name),
   'inheritance':'A7 revision 2 authority' if name=='controller' else 'unchanged immutable A5 FR-4 design'})
 layout,mech = read(root,LAYOUT),read(root,MECH)
 if mech['variant']!='3hp' or mech['leaf']!='fr4' or mech['layout_sha256']!=sha(root,LAYOUT):
  raise ValueError('stale or wrong mechanical variant')
 external=[]
 for p in mech['parts']:
  if p['kind'] not in ('standard_hardware_envelope','printable_design','manufacturing_artwork') or p['part'] in ('top_cap_spacer_A7','bottom_cap_fork_A7'):
   continue
  external.append({'id':p['part'],'quantity_per_module':1,'source':MECH,'description':p['part'],'kind':p['kind'],
   'bbox_mm':[p['bbox_min'],p['bbox_max']],'exact_orderable':None,'commercial_observation':None,'status':'NEEDS SUPPLIER / PHYSICAL QUALIFICATION'})
 for e in external:
  if e['id']=='top_cap_screw_A7':e['description']=layout['supports']['top_cap_screw']['designation']
  if e['id']=='top_leaf_adapter_cap':e['integral_features']=['top_cap_spacer_A7 (not a separate purchased part)']
  if e['id']=='bottom_leaf_cap':e['integral_features']=['bottom_cap_fork_A7 (not a separate purchased part)']
 external += [
  {'id':'finished-sh4','quantity_per_module':2,'candidate':'Adafruit 4399 / Kaweei CBH-100-04-050-A','requirement':'Finished 50 mm SH4 AWG28 1:1; controller J3 to left J1, left J2 to right J1. Incoming construction/length and real route unqualified.','source':'engineering/a5/integration/harness_contract_A5.md','commercial_observation':None},
  {'id':'finished-power-cable','quantity_per_module':1,'exact_orderable':None,'requirement':layout['power_cable_requirement'],'source':LAYOUT,
   'pin_map':'A1→B3, A2→B2, A3→B1; controller J5 +12V/GND/-12V, adapter J2 -12V/GND/+12V',
   'status':'BLOCKED: exact finished assembly not selected; historical Molex 151340300 50±6 mm is not the A7 cable','commercial_observation':None},
  {'id':'eurorack-idc-ribbon','quantity_per_module':1,'exact_orderable':None,'requirement':'Finished 16→10 pin keyed IDC; socket, strain relief, length, routing and 30 mm envelope unqualified','commercial_observation':None},
  {'id':'leaf-bond-line','quantity_per_module':1,'exact_orderable':None,'requirement':'FR-4 leaf bond-line material; 0.1 mm design reserve is not a selected adhesive','commercial_observation':None},
  {'id':'rack-mount-hardware','quantity_per_module':None,'exact_orderable':None,'requirement':'Owner rack rail/thread interface and fasteners not specified','commercial_observation':None},
  {'id':'right-leaf-unused-J2-cover','quantity_per_module':1,'exact_orderable':None,'requirement':'Insulating cover/clearance for live unused SH4 connector; material unresolved','commercial_observation':None}]
 fixture_path='engineering/a7/fixture/materials.json'
 fixture={'status':'BLOCKED: E3 material selection not yet available','items':[]}
 if (root/fixture_path).is_file():
  fixture=read(root,fixture_path);inputs.append(fixture_path)
 firmware='engineering/a5/firmware/dist/light_block_A5.bin';inputs.append(firmware)
 return {'schema':1,'revision':'A7-r2-3HP-FR4','status':'ENGINEERING_PREPARATION_NOT_SUPPLIER_UPLOAD',
  'manufacturing_released':False,'order_submitted':False,'agreed_order_quantity':None,'quantity_scenarios_only':[1,10,100],
  'inputs_sha256':{p:sha(root,p) for p in sorted(set(inputs))},'boards':boards,'population':rows,'excluded':excluded,
  'fitted_unique_placements':sum(r['quantity_per_board'] for r in rows),'fitted_pieces_per_module':sum(r['quantity_per_module'] for r in rows),
  'external_materials':external,'fixture_materials_per_fixture_not_per_module':fixture,
  'services':[{'id':'pcba','status':'UNCONFIRMED','requirement':'Factory SMT and through-hole assembly; quote, attrition, minimums, orientation and process not approved'},
   {'id':'program-calibrate','status':'UNCONFIRMED','firmware':firmware,'sha256':sha(root,firmware),'requirement':'SWD programming identity and measured calibration; +3V3 voltage reference; exact LED-lot timing discrepancy #13 open'}],
  'blockers':['Current supply and assembly eligibility not obtained for every line; stock never reserved.',
   'PJ-324M pin/slot/axis/nut qualification and PCM13SMTR supply/land fit open.',
   'Finished A7 power cable, PMMA pockets/tolerances, PETG and hardware qualification unresolved.',
   'Fixture materials need E3 review and physical contact/load tests.',
   'No physical prototype, release approval, final manufacturing package or agreed order quantity.']}


def outputs(report):
 raw=json.dumps(report,indent=2,ensure_ascii=False)+'\n'
 stream=io.StringIO();writer=csv.writer(stream,lineterminator="\n");writer.writerow(['ENGINEERING ONLY - NOT SUPPLIER UPLOAD'])
 writer.writerow(['board','ref','manufacturer','mpn','lcsc','population','per_board','board_multiplicity','per_module','side'])
 for r in report['population']:
  writer.writerow([r[k] for k in ['board','ref','manufacturer','mpn','lcsc','population','quantity_per_board','board_multiplicity','quantity_per_module']]+[r['placement']['side']])
 md='# A7 調達・組立の準備台帳\n\n自動生成。**製造承認・発注用ファイルではありません。** C221842 は 2026-11-09T09:18:55Z の JLC 観測で在庫 0・予約可能数 0・MOQ 3・包装数 3500。確保済み在庫ではなく、価格・納期・実装受入は未取得です。他の部品の現在の商取引条件も未取得で、過去の A5 価格を現在値として再掲しません。\n\n'
 md+=f"台帳 SHA-256: `{hashlib.sha256(raw.encode()).hexdigest()}`。{report['fitted_unique_placements']} 配置 / {report['fitted_pieces_per_module']} 実装点 / 台。数量 1・10・100 は比較条件だけです。\n\n| 基板 | 枚数/台 | 実装点/枚 | PCB SHA-256 |\n|---|---:|---:|---|\n"
 for b in report['boards']:md+=f"| {b['board']} | {b['multiplicity']} | {b['fitted_per_board']} | `{b['pcb_sha256']}` |\n"
 md+='\n外部部材・ケーブル・治具・サービスと未解決事項は `assembly-manifest.json` を参照してください。TP1–TP5 は購入部品に数えません。治具数量は台数に掛けません。B面・角度・位置は元の KiCad 出力とハッシュに追跡できますが、この台帳だけでは新規 native 検証や実装方向の承認になりません。\n'
 return {'assembly-manifest.json':raw,'population.csv':stream.getvalue(),'ledger.md':md}


def validate_report(report, root=ROOT):
 if report != generate(root):
  raise ValueError("ledger differs from exact current population, multiplicity or input identities")


def main():
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args()
 for name,contents in outputs(generate()).items():
  path=ROOT/OUT/name
  if args.check:
   if not path.exists() or path.read_text()!=contents:raise ValueError(f'stale ledger: {path}')
  else:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(contents)
 print('PASS: A7 engineering ledger accounted; NOT order/release eligibility')

if __name__=='__main__':main()
