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
NATIVE_GEOMETRY = 'engineering/a7/fixture/native-geometry.json'
HARNESS = 'engineering/a5/integration/harness_contract_A5.md'
# Gate classes shared with scripts/a7_readiness.py (what can resolve a blocker).
# Harness contract: controller J3 DATA_L/DATA_R arrive on the left leaf's J1 as its own and the other leaf's data.
SH4_NET_ROLES = {'DATA_L': 'DATA_IN', 'DATA_R': 'DATA_OTHER'}
# Harness contract: each leaf swaps the data lines in copper (J1.4 -> J2.3, J1.3 -> J2.4), so a 1:1 cable
# carries the left leaf's DATA_OTHER to the right leaf's DATA_IN.
LEAF_LINK_NET_ROLES = {'DATA_OTHER': 'DATA_IN', 'DATA_IN': 'DATA_OTHER'}
CLASSES = ('CLOUD_DIGITAL', 'OWNER_DECISION', 'ACCESS_EVIDENCE_HOLD', 'PHYSICAL_ONLY')
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


SWITCH_SOURCES = '.claude/skills/component-a7-hx-msk13c02/sources.json'
OWNER_DECISIONS = 'engineering/a7/procurement/owner-decisions.json'
SUPPLY_OBSERVATIONS = 'engineering/a7/procurement/supply-observations.json'
# Our reading (pending owner confirmation) of the owner's sourcing words in owner-decisions.json; anything else is an exception named per line.
SOURCING_ROUTES = ('JLC_STOCK', 'JLC_PREORDER_OR_GLOBAL_SOURCING', 'EXCEPTION')


def owner_order(root):
 record = read(root, OWNER_DECISIONS)
 found = [d for d in record.get('decisions', []) if isinstance(d, dict) and d.get('id') == 'order-quantity']
 if len(found) != 1:
  raise ValueError('owner order-quantity decision missing or duplicated')
 d = found[0]
 modules, basis = d.get('modules'), d.get('basis') or {}
 sourced = basis.get('status') != 'SOURCED' or all(isinstance((basis.get('source') or {}).get(k), str) and basis['source'][k] for k in ('url', 'retrieved_at', 'sha256'))
 if (d.get('decided_by') != 'OWNER' or not owner_messages(d) or type(modules) is not int or modules < 1
     or d.get('answer') != str(modules) or str(modules) not in ' '.join(d['owner_words']).split()
     or basis.get('status') not in ('OWNER_REPORTED', 'SOURCED') or not sourced or not basis.get('check')
     or type(basis.get('pcba_minimum_boards')) is not int or basis['pcba_minimum_boards'] < 1):
  raise ValueError('owner order-quantity decision must be the owner\'s own dated messages naming a whole module count, with a labelled PCBA minimum')
 pref = record.get('sourcing_preference') or {}
 reading = pref.get('interpretation') or {}
 if (pref.get('decided_by') != 'OWNER' or not owner_messages(pref) or (reading.get('interpreted_by'), reading.get('status')) != ('AGENT', 'PENDING_OWNER_CONFIRMATION')
     or [o.get('route') for o in reading.get('order', [])] != list(SOURCING_ROUTES)):
  raise ValueError('sourcing preference must be the owner\'s messages plus our reading, ordered ' + ' > '.join(SOURCING_ROUTES) + ', pending owner confirmation')
 return d


# Owner decisions that retire a ledger blocker, and the answers each may carry.
RETIRED_BY_OWNER = {'panel-route': ('repo-panels', 'jlc-panels'), 'finished-cables': ('assembler', 'diy'), 'switch-supply': ('alternate',)}
# Blockers that stay open after the owner accepted the recommended plan, with what is still missing.
ACCEPTED_TEXT = {'rack-hardware': 'The owner accepted naming the case (2026-11-12, accept all recommendations); the case model, and so the rail/thread interface and fasteners, is not given yet.'}
JACK_WAIVED_TEXT = ('PJ-324M pin function (which of terminals 4/5 is the tip contact; the supplier symbol contradicts the inferred 4 = tip) is not confirmed: '
                    'the owner waived the pre-order continuity test on 2026-11-12 and accepted the risk, so it is a first-article check on the assembled boards. '
                    'Slot, axis height and nut fit, and the HX MSK13C02 truth table and land/peg fit, also need received parts (jack-continuity, jack-dimensions, switch-fit).')


def owner_entries(root):
 entries = [d for d in read(root, OWNER_DECISIONS).get('decisions', []) if isinstance(d, dict)]
 ids = [d.get('id') for d in entries]
 if len(ids) != len(set(ids)):
  raise ValueError('duplicate owner decision id')
 for d in entries:
  if d.get('decided_by') != 'OWNER' or not owner_messages(d):
   raise ValueError('owner decision '+str(d.get('id'))+' must be owner-decided with the owner\'s own dated messages')
 return {d['id']: d for d in entries}


def owner_answered(root):
 """Ledger blocker ids the owner's recorded answers retire."""
 out = set()
 for i, d in owner_entries(root).items():
  if i in RETIRED_BY_OWNER:
   if d.get('answer') not in RETIRED_BY_OWNER[i]:
    raise ValueError('owner decision '+i+' has an answer outside '+', '.join(RETIRED_BY_OWNER[i]))
   out.add(i)
 return out


def owner_accepted(root):
 """Gate -> option for each recommendation the owner accepted as a whole ('accept all')."""
 d = owner_entries(root).get('accept-all-recommendations')
 return {a['gate']: a['option'] for a in d.get('accepted', [])} if d else {}


def owner_jack_waiver(root):
 d = owner_entries(root).get('jack-tip-test-waiver')
 return bool(d) and d.get('answer') == 'waive-pre-order-test'


def owner_messages(entry):
 msgs = entry.get('owner_messages')
 return (isinstance(msgs, list) and msgs and all(isinstance(m, dict) and str(m.get('message_id', '')).startswith('cmsg_') and m.get('at') and m.get('text') for m in msgs)
         and entry.get('owner_words') == [m['text'] for m in msgs])


def switch_listing(root):
 found = [o for o in read(root, SUPPLY_OBSERVATIONS)['observations'] if o.get('id') == 'jlc-c5149819-2026-11-12']
 if len(found) != 1:
  raise ValueError('C5149819 2026-11-12 listing observation missing or duplicated')
 o = found[0]
 v = o['values']
 if (o['lcsc'], o['supplier'], o['retrieved_at'], o['raw_sha256']) != ('C5149819', 'JLCPCB', '2026-11-12T19:35:14Z', 'f6e3f19ec6c129eb50209701f98ea079945f5eb4dbe17b9c711ab6d5006d1ab9') \
   or (v['buyable'], v['jlc_stock'], v['minimum_purchase'], v['least_patch'], v['attrition_pieces'], v['currency'], v['lead_time']) != (True, 4561, 1, 0, 0, None, None):
  raise ValueError('switch listing observation changed; re-review the switch-supply decision')
 return o


def controller_mounts(root, pcb_sha):
 geo = read(root, NATIVE_GEOMETRY)
 if geo.get('board_sha256') != pcb_sha or geo['geometry'].get('board_sha256') != pcb_sha:
  raise ValueError('stale native geometry: not bound to the authoritative controller PCB')
 mounts = {}
 for f in geo['geometry']['footprints']:
  kinds = {p['attribute'] for p in f['pads']}
  if not kinds <= {'SMD', 'PTH', 'NPTH'} or not kinds - {'NPTH'}:
   raise ValueError(f"controller/{f['ref']}: unknown native pad attributes {sorted(kinds)}")
  if f['ref'] in mounts:
   raise ValueError(f"duplicate native geometry footprint: {f['ref']}")
  mounts[f['ref']] = ('THT' if 'PTH' in kinds else 'SMD', f['side'])
 return mounts


def a5_mount(component):
 # KiCad PAD_ATTRIB numbering as exported by A5: 0 PTH, 1 SMD, 2 CONN, 3 NPTH.
 kinds = {p['attribute'] for p in component['all_pad_details']}
 if not kinds <= {'0', '1', '3'} or not kinds - {'3'}:
  raise ValueError(f"{component['ref']}: unknown A5 pad attributes {sorted(kinds)}")
 return 'THT' if '0' in kinds else 'SMD'


def pin_nets(root, netlist, ref):
 nets = {}
 for net in ET.parse(root/netlist).getroot().findall('nets/net'):
  for node in net.findall('node'):
   if node.attrib['ref'] == ref:
    nets[node.attrib['pin']] = net.attrib['name'].lstrip('/')
 return nets


def cable_pin_map(root, a_net, a_ref, b_net, b_ref, crossed, aliases=None):
 aliases = aliases or {}
 a, b = pin_nets(root, a_net, a_ref), pin_nets(root, b_net, b_ref)
 n = len(a)
 if not n or set(a) != {str(i) for i in range(1, n+1)} or set(b) != set(a):
  raise ValueError(f'{a_ref}/{b_ref}: cable end pin sets differ')
 rows = []
 for i in range(1, n+1):
  j = n+1-i if crossed else i
  if aliases.get(a[str(i)], a[str(i)]) != b[str(j)]:
   raise ValueError(f'{a_ref}.{i} -> {b_ref}.{j}: net {a[str(i)]} != {b[str(j)]}')
  rows.append({'a_pin': i, 'b_pin': j, 'a_net': a[str(i)], 'b_net': b[str(j)]})
 return rows


def switch_observation(root):
 sources = read(root, SWITCH_SOURCES)['sources']
 source = next(s for s in sources if s['source_id']=='src-a7-hx-msk13c02-jlc-api-2026-11-12')
 if source['sha256']!='f6e3f19ec6c129eb50209701f98ea079945f5eb4dbe17b9c711ab6d5006d1ab9' or source['retrieved_at']!='2026-11-12T19:35:14Z' or source['availability']!='AVAILABLE':
  raise ValueError('switch supply receipt changed; re-review observation')
 for term in ("C5149819 'HX MSK13C02' hanxia", 'stockCount 4561', 'canPresaleNumber 4552', 'minPurchaseNum 1', 'encapsulationNumber 3000', 'tier 1-49 0.1069'):
  if term not in source['evidence_extract']:
   raise ValueError('switch supply extract changed; re-review observation')
 return {'source_bundle':SWITCH_SOURCES,'source_id':source['source_id'],'url':source['authoritative_url'],
  'raw_sha256':source['sha256'],'observed_at':source['retrieved_at'],'supplier':'JLCPCB',
  'stock_count':4561,'presale_count':4552,'minimum_purchase_quantity':1,'packaging_quantity':3000,
  'price':0.1069,'currency':None,'lead_time':None,'assembly_acceptance':None,'reserved':False,
  'scope':'Dated exact C5149819 listing observation only; refresh before procurement. Price is the 1-49 tier with no currency field; no assembly acceptance.'}


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
 native_mounts = controller_mounts(root, placement['board_sha256'])
 inherited = {b['name']: b for b in read(root, A5POS)['boards']}
 inputs = [SWITCH_SOURCES, INV, PLACEMENT, LAYOUT, MECH, A5POS, 'engineering/a7/electronics/controller/controller.kicad_sch',
           HARNESS, 'engineering/a7/mechanical/build_a7_mechanical.py', NATIVE_GEOMETRY, OWNER_DECISIONS, SUPPLY_OBSERVATIONS]
 observation = switch_observation(root)
 decision, listing = owner_order(root), switch_listing(root)
 modules = decision['modules']
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
   if name == 'controller':
    if ref not in native_mounts or native_mounts[ref][1] != pos['side']:
     raise ValueError(f'{name}/{ref}: native geometry side/mount missing or differs from placement')
    mount = native_mounts[ref][0]
   else:
    mount = a5_mount(pos)
   dnp = line['dnp']
   if not isinstance(dnp,bool):
    raise ValueError('DNP must be boolean')
   native_dnp = any(p.attrib.get('name') == 'dnp' for p in c.findall('property'))
   if dnp != native_dnp:
    raise ValueError(f'{name}/{ref}: DNP differs between netlist and catalog')
   rows.append({'board':name,'ref':ref,'manufacturer':line['manufacturer'],'mpn':line['mpn'],'lcsc':line['lcsc'],
    'package':line['package'],'line_id':line['line_id'],'owner_skill':line['owner_skill'],'footprint':c.findtext('footprint'),
    'population':'DNP' if dnp else 'FITTED','mount':mount,'quantity_per_board':0 if dnp else 1,'board_multiplicity':mult,'quantity_per_module':0 if dnp else mult,
    'placement':{'side':pos['side'],'at_mm':pos.get('at_mm',pos.get('at')),'angle_deg':pos.get('angle_deg',pos.get('angle')),
     'source':PLACEMENT if name=='controller' else A5POS,
     'authority':'native export; independent fresh gate required' if name=='controller' else 'immutable historical A5 KiCad export; not fresh placement proof'},
    'quantity_for_order':(0 if dnp else mult)*modules,
    'commercial_observation':observation if line['lcsc']=='C5149819' else None,'supply_status':('OBSERVED: JLC stock 4561 at 2026-11-12T19:35:14Z (Extended, not reserved); 1-49 tier 0.1069 without currency; lead time and assembly acceptance unknown' if line['lcsc']=='C5149819' else 'NOT_OBTAINED: current stock, price, lead time, MOQ, packaging and assembly applicability require dated exact-part evidence')})
  fitted = [r for r in rows if r['board']==name and r['population']=='FITTED']
  process = {f'{m}_{side}': sum(1 for r in fitted if (r['mount'], r['placement']['side'])==(m, side))
             for m in ('SMD', 'THT') for side in ('F', 'B')}
  boards.append({'board':name,'multiplicity':mult,'assembly_process_per_board':process,'pcb':pcb,'pcb_sha256':sha(root,pcb),'netlist':netlist,'netlist_sha256':sha(root,netlist),
   'fitted_per_board':sum(r['quantity_per_board'] for r in rows if r['board']==name),
   'inheritance':'A7 revision 2 authority' if name=='controller' else 'unchanged immutable A5 FR-4 design'})
 controller_process = boards[0]['assembly_process_per_board']
 if controller_process['THT_B'] or not (controller_process['SMD_F'] and controller_process['SMD_B']):
  raise ValueError('controller assembly sides changed; review the PCBA service requirement wording')
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
  {'id':'finished-sh4','quantity_per_module':2,'pin_maps':{
    'controller J3 -> left leaf J1':cable_pin_map(root,BOARDS['controller'][1],'J3',BOARDS['led_leaf'][1],'J1',False,SH4_NET_ROLES),
    'left leaf J2 -> right leaf J1':cable_pin_map(root,BOARDS['led_leaf'][1],'J2',BOARDS['led_leaf'][1],'J1',False,LEAF_LINK_NET_ROLES)},'candidate':'Adafruit 4399 / Kaweei CBH-100-04-050-A','requirement':'Finished 50 mm SH4 AWG28 1:1; controller J3 to left J1, left J2 to right J1. Incoming construction/length and real route unqualified.','source':'engineering/a5/integration/harness_contract_A5.md','commercial_observation':None},
  {'id':'finished-power-cable','quantity_per_module':1,'exact_orderable':None,'requirement':layout['power_cable_requirement'],'source':LAYOUT,
   'pin_map':cable_pin_map(root,BOARDS['controller'][1],'J5',BOARDS['power_adapter'][1],'J2',True),
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
 decided = owner_answered(root)
 accepted = owner_accepted(root)
 open_blockers = [dict(b, text=ACCEPTED_TEXT[b['id']]) if b['id'] in ACCEPTED_TEXT and accepted.get('assembly:' + b['id']) else b
                  for b in BLOCKERS if b['id'] not in decided]
 if owner_jack_waiver(root):
  open_blockers = [dict(b, text=JACK_WAIVED_TEXT) if b['id'] == 'jack-switch-qualification' else b for b in open_blockers]
 fixture = fixture_blocker(root,inputs)
 if fixture['class'] == 'OWNER_DECISION' and accepted.get('assembly:fixture-materials') == 'approve':
  fixture = dict(fixture, text='Fixture digital criteria 1-4 met; the owner approved the proposed hardware on 2026-11-12 (accept all recommendations). The fabricator for the four FR-4 plates is not chosen. Physical contact/load tests (criterion 5) follow.')
 blockers=open_blockers[:-1]+[fixture]+open_blockers[-1:]
 return {'schema':1,'revision':'A7-r2-3HP-FR4','status':'ENGINEERING_PREPARATION_NOT_SUPPLIER_UPLOAD',
  'manufacturing_released':False,'order_submitted':False,'agreed_order_quantity':modules,
  'order_plan':order_plan(root, decision, listing, boards, rows),
  'inputs_sha256':{p:sha(root,p) for p in sorted(set(inputs))},'boards':boards,'population':rows,'excluded':excluded,
  'fitted_unique_placements':sum(r['quantity_per_board'] for r in rows),'fitted_pieces_per_module':sum(r['quantity_per_module'] for r in rows),
  'external_materials':external,'fixture_materials_per_fixture_not_per_module':fixture,
  'unique_fitted_identities':len({(r['mpn'],r['lcsc']) for r in rows if r['population']=='FITTED'}),
  'services':[{'id':'pcba','status':'UNCONFIRMED','process_per_board':{b['board']:b['assembly_process_per_board'] for b in boards},
    'requirement':'Factory assembly. Controller: SMD on both sides (F and B) plus through-hole jacks and power header on F, from native pad attributes. Leaf: one-side SMD. Adapter: through-hole only. Quote, attrition, minimums, orientation, side order and process not approved'},
   {'id':'program-calibrate','status':'UNCONFIRMED','firmware':firmware,'sha256':sha(root,firmware),'requirement':'SWD programming identity and measured calibration; +3V3 voltage reference; exact LED-lot timing discrepancy #13 open'}],
  'blockers':blockers}


def order_plan(root, decision, listing, boards, rows):
 modules, minimum = decision['modules'], decision['basis']['pcba_minimum_boards']
 lines = {}
 for r in rows:
  if r['population'] != 'FITTED':
   continue
  line = lines.setdefault((r['mpn'], r['lcsc']), {'lcsc':r['lcsc'],'mpn':r['mpn'],'manufacturer':r['manufacturer'],'pieces_per_module':0})
  line['pieces_per_module'] += r['quantity_per_module']
 order_lines = []
 for (mpn, lcsc), line in sorted(lines.items(), key=lambda kv: kv[0][1]):
  required = line['pieces_per_module'] * modules
  if lcsc == listing['lcsc']:
   least = listing['values']['minimum_purchase']
   line.update({'pieces_required':required,'supplier_minimum':least,'minimum_source':SUPPLY_OBSERVATIONS+'#'+listing['id'],'pieces_to_buy':max(required, least),
    'sourcing':{'route':'JLC_STOCK','status':'JLC stock 4561 at 2026-11-12T19:35:14Z (Extended part, point-in-time, not reserved; field meanings inferred). Refresh before ordering.','exception':None}})
  else:
   line.update({'pieces_required':required,'supplier_minimum':None,'minimum_source':None,'pieces_to_buy':None,
    'sourcing':{'route':'JLC_STOCK','status':'NOT_OBSERVED: preferred route; JLC stock and minimum at the order quantity not observed','exception':None}})
  order_lines.append(line)
 return {'modules':modules,'decision':OWNER_DECISIONS,'decided_by':decision['decided_by'],'owner_words':decision['owner_words'],
  'pcba_minimum_boards':{'value':minimum,'status':decision['basis']['status'],'check':decision['basis']['check'],'source':decision['basis'].get('source')},
  'boards':[{'board':b['board'],'boards_needed':b['multiplicity']*modules,'meets_reported_pcba_minimum':b['multiplicity']*modules>=minimum} for b in boards],
  'pcb_fabrication_minimum':'NOT_SOURCED','attrition':'NOT_SOURCED: JLC extra-piece (attrition) rule not obtained; pieces_required and pieces_to_buy add none',
  'sourcing_preference':{'owner_words':read(root, OWNER_DECISIONS)['sourcing_preference']['owner_words'],'our_reading':list(SOURCING_ROUTES),'status':'PENDING_OWNER_CONFIRMATION'},
  'lines':order_lines,
  'outside_pcba':'External materials, cables, mechanical parts and fixture items are outside the JLC parts library and not yet routed under the preference.'}


FIXTURE_MANIFEST = 'engineering/a7/fixture/manifest.json'


def fixture_blocker(root, inputs):
 # The fixture manifest decides who can act next: digital design work, or the owner's choice of fabricator and hardware.
 manifest = read(root, FIXTURE_MANIFEST) if (root/FIXTURE_MANIFEST).is_file() else {}
 if (root/FIXTURE_MANIFEST).is_file():
  inputs.append(FIXTURE_MANIFEST)
 if manifest.get('digital_criteria_1_to_4_met') is True and manifest.get('hardware_proposal_complete') is True:
  return {'id':'fixture-materials','class':'OWNER_DECISION','text':'Fixture digital criteria 1-4 met and a sourced hardware proposal recorded; the fabricator choice and approval of the proposed hardware are owner decisions. Physical contact/load tests (criterion 5) follow.'}
 missing = [k for k in ('digital_criteria_1_to_4_met','hardware_proposal_complete') if manifest.get(k) is not True]
 return {'id':'fixture-materials','class':'CLOUD_DIGITAL','text':'Fixture design and materials incomplete (fixture manifest: '+', '.join(k+' not true' for k in missing)+'); physical contact/load tests follow.'}


# Each ledger blocker names what can resolve it; readiness reports these as separate gates.
BLOCKERS = [
 {'id':'supply-observations','class':'ACCESS_EVIDENCE_HOLD','text':'Order quantity is 2 modules (owner decision). JLC stock, price, minimum, packaging, lead time and assembly applicability at that quantity are not observed for any line except the C5149819 switch (stock 4561 at 2026-11-12); JLC attrition is not sourced; stock never reserved.'},
 {'id':'switch-supply','class':'OWNER_DECISION','text':'PCM13SMTR (C221842): 2 needed for 2 modules. JLC stock 0 at 2026-11-09; at 2026-11-12 JLC lists it buyable (Extended) with pre-order minimum 3 and presale 0 (field meanings inferred), tier prices without currency, no lead time. The owner wants to complete on JLC: on our reading, a pre-order (presale 0 may mean none can be placed now; fill depends on LCSC stock, not observed) or a Global Sourcing quote; otherwise wait, or accept a reviewed alternate with its own contact table and fit review. At 2026-11-12T18:55Z the owner relayed a live check by their browsing assistant (not a first-hand capture): JLC stock 0, Extended, pre-order offered at minimum 3 with an estimated 31 days; Global Sourcing for 3 via DigiKey JPY 826 total (8-15 business days) or Element JPY 865 (8-18); parts stay in the JLC parts library. The owner accepted JLC sourcing with all recommendations, then asked to consider another switch because of the price, so this stays open until the owner picks.'},
 {'id':'panel-route','class':'OWNER_DECISION','text':'None of the three boards meets JLC single-board PCBA size; the panel route is not chosen. Panel by JLCPCB puts 10 controllers, 8 leaves or 2 adapters on each panel (20 SW1 switches for a 2-panel minimum if the PCBA quantity counts panels, not sourced); a repo-built panel holding 1 controller, 2 leaves or 1 adapter gives exactly 2 modules; it is prepared (not released) in engineering/a7/jlc-package/panels/. Comparison in engineering/a7/jlc-package/package.json.'},
 {'id':'jack-switch-qualification','class':'PHYSICAL_ONLY','text':'PJ-324M pin function (which of terminals 4/5 is the tip contact and which its normal; the supplier symbol contradicts the inferred 4 = tip, so this continuity test must precede any PCB order), slot, axis height and nut fit, and the HX MSK13C02 truth table and land/peg fit, need received parts (jack-continuity, jack-dimensions, switch-fit).'},
 {'id':'exact-part-evidence','class':'ACCESS_EVIDENCE_HOLD','text':'Exact-part gaps after the 2026-11-11 source recovery (the PMEG4010CEJ ,115 packing is since sourced: SOD323F on a 7-inch reel, fact-pmeg4010cej-115-orderable): SM04B-SRSS-TB per-circuit numbering not printed beyond the No. 1 end; PJ-324M recommended hole/slot sizes, axis height and whether a nut ships with C22355739 not sourced.'},
 {'id':'finished-cables','class':'OWNER_DECISION','text':'Finished A7 power cable (57 mm, +/-3 ASSUMED), SH4 cables and IDC ribbon not selected; supplier answers and the owner choice of assembly are needed before physical routing checks.'},
 {'id':'mechanical-materials','class':'ACCESS_EVIDENCE_HOLD','text':'PMMA sheet and pocket tolerances, PETG process and orderable fastener part numbers are not sourced; the model carries designations (M2x18, M1.6x4) and envelopes only.'},
 {'id':'rack-hardware','class':'OWNER_DECISION','text':'Owner rack rail/thread interface and fasteners not specified.'},
 {'id':'prototype-and-release','class':'OWNER_DECISION','text':'No reviewed manufacturing package and no manufacturing release approval. A prototype route, when the owner approves one, is recorded in engineering/a7/qualification/records.json and is not a release.'},
]


def outputs(report):
 raw=json.dumps(report,indent=2,ensure_ascii=False)+'\n'
 stream=io.StringIO();writer=csv.writer(stream,lineterminator="\n");writer.writerow(['ENGINEERING ONLY - NOT SUPPLIER UPLOAD'])
 writer.writerow(['board','ref','manufacturer','mpn','lcsc','population','mount','per_board','board_multiplicity','per_module','side'])
 for r in report['population']:
  writer.writerow([r[k] for k in ['board','ref','manufacturer','mpn','lcsc','population','mount','quantity_per_board','board_multiplicity','quantity_per_module']]+[r['placement']['side']])
 op=report['order_plan']
 md='# A7 調達・組立の準備台帳\n\n自動生成。**製造承認・発注用ファイルではありません。** SW1 はオーナーの方針（動けばよい・安く・JLC 在庫あり）により 2026-11-12 に PCM13SMTR（C221842、JLC 在庫 0）から HX MSK13C02（C5149819）へ変更しました。C5149819 は 2026-11-12T19:35:14Z の JLC 観測で在庫 4561（Extended）・最小購入 1・包装数 3000、1〜49 個の段階価格 0.1069（通貨の項目なし）です（項目の意味はこちらの解釈）。確保済み在庫ではなく、納期・実装受入は未取得です。他の部品の現在の商取引条件も未取得で、過去の A5 価格を現在値として再掲しません。\n\n'
 md+=f"台帳 SHA-256: `{hashlib.sha256(raw.encode()).hexdigest()}`。{report['fitted_unique_placements']} 配置 / {report['fitted_pieces_per_module']} 実装点 / 台。\n\n"
 md+=f"## 最初の発注数量: {op['modules']} 台（オーナーの判断）\n\nオーナーの言葉: 「{' '.join(op['owner_words'])}」（`{op['decision']}`）。JLC の PCBA 最小 {op['pcba_minimum_boards']['value']} 枚は {op['pcba_minimum_boards']['status']}（{'JLC の公開能力表で確認済み' if op['pcba_minimum_boards']['status']=='SOURCED' else 'JLC の公開条件では未確認'}）。この数量は発注・試作ルート・製造リリースの承認ではありません。\n\n"
 md+="必要枚数: "+'、'.join(f"{b['board']} {b['boards_needed']} 枚" for b in op['boards'])+"。PCB 製造の最小枚数と JLC のロス分（attrition）は未取得で、下の数に上乗せしていません。\n\n"
 md+=f"オーナーの方針（原文）: 「{' '.join(op['sourcing_preference']['owner_words'])}」。こちらの解釈（オーナー未確認）: JLC 在庫 → JLC 予約注文または Global Sourcing → それ以外は例外として行ごとに明示。\n\n| LCSC | 型番 | 必要数 | 最小購入 | 購入数 | 経路 |\n|---|---|---:|---:|---:|---|\n"
 for l in op['lines']:
  if l['supplier_minimum'] is not None or l['sourcing']['exception']:
   md+=f"| {l['lcsc']} | {l['mpn']} | {l['pieces_required']} | {l['supplier_minimum']} | {l['pieces_to_buy']} | {l['sourcing']['route']} |\n"
 md+=f"\nほかの {sum(1 for l in op['lines'] if l['supplier_minimum'] is None and not l['sourcing']['exception'])} 型番は JLC 在庫を第一候補とし、在庫と最小購入数は未観測です（行ごとの必要数は `assembly-manifest.json` の `order_plan.lines`）。\n\n"
 md+=f"| 基板 | 枚数/台 | 実装点/枚 | SMD F/B | THT F/B | PCB SHA-256 |\n|---|---:|---:|---|---|---|\n"
 for b in report['boards']:
  pr=b['assembly_process_per_board']
  md+=f"| {b['board']} | {b['multiplicity']} | {b['fitted_per_board']} | {pr['SMD_F']}/{pr['SMD_B']} | {pr['THT_F']}/{pr['THT_B']} | `{b['pcb_sha256']}` |\n"
 md+=f"\n実装する型番は {report['unique_fitted_identities']} 種類。SMD / THT の区別はコントローラーが native geometry のパッド属性、リーフとアダプタが不変 A5 の配置データのパッド属性から生成しています。コントローラーは両面 SMD と F 面 THT の組合せで、実装サービスの受入は未確認です。\n\n## 未解決事項\n\n| ID | 区分 | 内容 |\n|---|---|---|\n"
 for b in report['blockers']:md+=f"| {b['id']} | {b['class']} | {b['text']} |\n"
 md+='\n外部部材・ケーブル・治具・サービスの詳細は `assembly-manifest.json` を参照してください。TP1–TP5 は購入部品に数えません。治具数量は台数に掛けません。B面・角度・位置は元の KiCad 出力とハッシュに追跡できますが、この台帳だけでは新規 native 検証や実装方向の承認になりません。\n'
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
