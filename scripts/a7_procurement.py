#!/usr/bin/env python3
"""Generate preparation data, never supplier-upload or hardware release data."""
import argparse
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = Path('engineering/a7/procurement')
INV = '.claude/skills/component-spec-audit/references/inventory.json'
PLACEMENT = 'engineering/a7/electronics/controller/board_placement.json'
LEAF_PLACEMENT = 'engineering/a7/electronics/led_leaf/board_placement.json'
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
 'led_leaf': (2, 'engineering/a7/verification/led_leaf/netlist.xml', 'engineering/a7/electronics/led_leaf/led_leaf.kicad_pcb'),
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
# Authored dated evidence for the sourcing projection. Never the generated jlc-package/package.json: it reads this ledger.
LISTING_PAGES = 'engineering/a7/jlc-package/sources.json'
# The newest dated parts-API audit; older audits stay unchanged as history and are never shown as the latest.
PRICE_AUDIT = 'engineering/a7/procurement/price-audit/2026-11-22.json'
PRICE_AUDIT_HISTORY = ['engineering/a7/procurement/price-audit/2026-11-12.json']
PRIVATE_REPOSITORY = 'Takazudo/circuit-dev-resources'
CROSSWALK = 'provenance/a5-catalog/identity-crosswalk.json'
PROJECTION = 'engineering/a7/procurement/sourcing-projection.json'
# Parts with saved evidence that are no longer fitted; anything else outside the active population is rejected.
RETIRED = {'C221842': {'mpn': 'PCM13SMTR', 'reason': 'SW1 replaced by HX MSK13C02 (C5149819) on 2026-11-12 (owner decision switch-supply); historical evidence only'}}
NOT_OBTAINED = ('lead_time', 'confirmed_quote', 'stock_reservation', 'assembly_acceptance')


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


def leaf_positions(root):
 # Native placement is authoritative; pad mount types are parsed from matching PCB bytes.
 placement = read(root, LEAF_PLACEMENT)
 if placement['board'] != BOARDS['led_leaf'][2] or placement['board_sha256'] != sha(root, BOARDS['led_leaf'][2]):
  raise ValueError('stale leaf placement identity')
 facts_path = 'engineering/a7/verification/led_leaf/board_facts.json'
 geometry_path = 'engineering/a7/verification/led_leaf/board_geometry.json'
 facts, geometry = read(root, facts_path), read(root, geometry_path)
 if facts['board_sha256'] != placement['board_sha256'] or facts['geometry_sha256'] != hashlib.sha256(json.dumps(geometry, sort_keys=True).encode()).hexdigest() or placement['geometry_sha256'] != facts['geometry_sha256']:
  raise ValueError('leaf placement/native geometry provenance mismatch')
 native = unique(placement['components'], 'ref')
 expected = unique(geometry['footprints'], 'ref')
 for ref, pos in native.items():
  fp = expected[ref]
  if (pos['at_mm'],pos['angle_deg'],pos['side'],pos['fpid']) != ([fp['x'],fp['y']],fp['rot'],fp['side'],fp['fpid']):
   raise ValueError('leaf placement differs from native geometry')
 spec = importlib.util.spec_from_file_location('a7_leaf_facts', ROOT/'scripts/a7_jlc_package.py')
 module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 module.ROOT = root
 facts = module.board_facts(BOARDS['led_leaf'][2])
 result = {}
 for fp in facts['footprints']:
  kinds = {pad[4] for pad in fp['pads']}
  if not kinds <= {'smd','thru_hole','np_thru_hole'} or not kinds-{'np_thru_hole'}:
   raise ValueError(f"led_leaf/{fp['ref']}: unsupported pad mount attributes {kinds}")
  pos = native[fp['ref']]
  if pos['fpid'] != fp['footprint'] or pos['side'] != ('B' if fp['layer']=='B.Cu' else 'F'):
   raise ValueError('leaf native placement/PCB footprint mismatch')
  result[fp['ref']] = dict(pos, mount='THT' if 'thru_hole' in kinds else 'SMD')
 if set(result) != set(native):
  raise ValueError('leaf native placement population mismatch')
 return result


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
 return build(root)[0]


def build(root=ROOT):
 """(assembly manifest, sourcing projection). The projection is a separate output so a later re-observation does not rewrite approval-bound bytes beyond the summary it changes."""
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
 inputs = [LEAF_PLACEMENT, 'engineering/a7/verification/led_leaf/board_facts.json', 'engineering/a7/verification/led_leaf/board_geometry.json', 'engineering/a7/verification/fab/optical-fr4.json', 'engineering/a7/electronics/led_leaf/led_leaf.kicad_sch', SWITCH_SOURCES, INV, PLACEMENT, LAYOUT, MECH, A5POS, 'engineering/a7/electronics/controller/controller.kicad_sch',
           HARNESS, 'engineering/a7/mechanical/build_a7_mechanical.py', NATIVE_GEOMETRY, OWNER_DECISIONS, SUPPLY_OBSERVATIONS,
           LISTING_PAGES, PRICE_AUDIT, *PRICE_AUDIT_HISTORY, CROSSWALK]
 switch_observation(root)
 decision, listing = owner_order(root), switch_listing(root)
 modules = decision['modules']
 rows, excluded, boards = [], [], []
 for name, (mult, netlist, pcb) in BOARDS.items():
  inputs += [netlist, pcb]
  byref = unique([{'ref': c.attrib['ref'], 'xml': c} for c in ET.parse(root/netlist).getroot().findall('components/comp')], 'ref')
  testpads = {'TP1','TP2','TP3','TP4','TP5'} if name == 'controller' else set()
  if set(byref) != set(assigned[name]) | testpads:
   raise ValueError(f'{name} omitted/unexpected population')
  positions = pmap if name == 'controller' else leaf_positions(root) if name == 'led_leaf' else unique(inherited[name]['components'], 'ref')
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
   elif name == 'led_leaf':
    if pos['fpid'] != c.findtext('footprint'):
     raise ValueError(f'{name}/{ref}: PCB footprint differs from fresh netlist')
    mount = pos['mount']
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
     'source':PLACEMENT if name=='controller' else LEAF_PLACEMENT if name=='led_leaf' else A5POS,
     'authority':'native export; independent fresh gate required' if name=='controller' else 'fresh native placement; mount attributes from matching adopted PCB bytes' if name=='led_leaf' else 'immutable historical A5 KiCad export; not fresh placement proof'},
    'quantity_for_order':(0 if dnp else mult)*modules,
    'sourcing_evidence':None if dnp else PROJECTION+'#'+line['lcsc'],
    'supply_status':'NOT_PURCHASED: DNP' if dnp else 'DATED_OBSERVATIONS_ONLY: see the order_plan line and '+PROJECTION+'; not current stock, a quote, a reservation or assembly acceptance'})
  fitted = [r for r in rows if r['board']==name and r['population']=='FITTED']
  process = {f'{m}_{side}': sum(1 for r in fitted if (r['mount'], r['placement']['side'])==(m, side))
             for m in ('SMD', 'THT') for side in ('F', 'B')}
  boards.append({'board':name,'multiplicity':mult,'assembly_process_per_board':process,'pcb':pcb,'pcb_sha256':sha(root,pcb),'netlist':netlist,'netlist_sha256':sha(root,netlist),
   'fitted_per_board':sum(r['quantity_per_board'] for r in rows if r['board']==name),
   'inheritance':'A7 optical R3 authority; historical approvals do not transfer' if name in ('controller', 'led_leaf') else 'unchanged immutable A5 FR-4 adapter design'})
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
  if e['id']=='top_leaf_adapter_cap':
   e['integral_features']=['top_cap_spacer_A7 (not a separate purchased part)']
   e['adapter_spacer_z_mm']=layout['supports']['adapter']['cap_spacer_z']
   e['adapter_spacer_height_mm']=round(e['adapter_spacer_z_mm'][1]-e['adapter_spacer_z_mm'][0],6)
   e['adapter_position_basis']=layout['supports']['adapter']
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
  fixture = dict(fixture, text='Fixture digital criteria 1-4 met for the current generated identity only. The 2026-11-12 hardware decision is historical and does not approve optical R3 revised supports, shims or preload. Fabricator and physical contact/load qualification remain outstanding.')
 pc=layout['power_cable_requirement']
 open_blockers=[dict(b,text=f"Finished A7 power cable ({pc['finished_free_span_nominal']:g} +/-{pc['tolerance']:g} mm free span, tolerance {pc['tolerance_confidence']}, order band {pc['band'][0]:g}-{pc['band'][1]:g} mm, {LAYOUT}), SH4 cables and IDC ribbon not selected; supplier answers and the owner choice of assembly are needed before physical routing checks.") if b['id']=='finished-cables' else b for b in open_blockers]
 blockers=open_blockers[:-1]+[fixture]+open_blockers[-1:]
 projection = sourcing_projection(root, rows, modules)
 blockers = [dict(b, text=supply_text(projection)) if b['id'] == 'supply-observations' else b for b in blockers]
 return {'schema':1,'revision':'A7-optical-R3-3HP-FR4-0.8mm','status':'ENGINEERING_PREPARATION_NOT_SUPPLIER_UPLOAD',
  'manufacturing_released':False,'order_submitted':False,'agreed_order_quantity':modules,
  'order_plan':order_plan(root, decision, boards, rows, projection),
  'inputs_sha256':{p:sha(root,p) for p in sorted(set(inputs))},'boards':boards,'population':rows,'excluded':excluded,
  'fitted_unique_placements':sum(r['quantity_per_board'] for r in rows),'fitted_pieces_per_module':sum(r['quantity_per_module'] for r in rows),
  'external_materials':external,'fixture_materials_per_fixture_not_per_module':fixture,
  'unique_fitted_identities':len({(r['mpn'],r['lcsc']) for r in rows if r['population']=='FITTED'}),
  'services':[{'id':'pcba','status':'UNCONFIRMED','process_per_board':{b['board']:b['assembly_process_per_board'] for b in boards},
    'requirement':'Factory assembly. Controller: SMD on both sides (F and B) plus through-hole jacks and power header on F, from native pad attributes. Leaf: one-side SMD. Adapter: through-hole only. Quote, attrition, minimums, orientation, side order and process not approved'},
   {'id':'program-calibrate','status':'UNCONFIRMED','firmware':firmware,'sha256':sha(root,firmware),'requirement':'SWD programming identity and measured calibration; +3V3 voltage reference; exact LED-lot timing discrepancy #13 open'}],
  'blockers':blockers}, projection


def order_plan(root, decision, boards, rows, projection):
 modules, minimum = decision['modules'], decision['basis']['pcba_minimum_boards']
 order_lines = []
 for l in projection['lines']:
  observed = [k for k in ('listing_page', 'parts_api') if l[k]['status'] == 'OBSERVED']
  short = l['listing_shortfall']
  if short:
   # Our reading of the owner's sourcing order: below the listed stock the next route is a JLC pre-order or Global Sourcing; no substitute is chosen here.
   sourcing = {'route':'JLC_PREORDER_OR_GLOBAL_SOURCING','status':f"LISTED_STOCK_SHORTFALL: JLC stock {short['jlc_stock']} for {short['pieces_required']} needed at {short['observed_at']} (page pre-order available {short.get('preorder_available')}, pre-order minimum {short.get('preorder_minimum')}; meanings inferred); "
     'a JLC pre-order or Global Sourcing quote, waiting, or a separately reviewed alternate is needed (not a quote, a reservation or assembly acceptance)','exception':None}
  else:
   sourcing = {'route':'JLC_STOCK','status':('DATED_LISTING_OBSERVED: preferred route; '+' and '.join(observed)+' observations dated '+projection['observation_date']
     +' (not current stock, a quote, a reservation or assembly acceptance; refresh before ordering)') if observed else
     'NO_DATED_OBSERVATION: preferred route; no saved listing evidence for this identity','exception':None}
  order_lines.append({'lcsc':l['lcsc'],'mpn':l['mpn'],'manufacturer':l['manufacturer'],'pieces_per_module':l['pieces_per_module'],
   'pieces_required':l['pieces_required'],'sourcing':sourcing,'evidence':PROJECTION+'#'+l['lcsc']})
 return {'modules':modules,'decision':OWNER_DECISIONS,'decided_by':decision['decided_by'],'owner_words':decision['owner_words'],
  'pcba_minimum_boards':{'value':minimum,'status':decision['basis']['status'],'check':decision['basis']['check'],'source':decision['basis'].get('source')},
  'boards':[{'board':b['board'],'boards_needed':b['multiplicity']*modules,'meets_reported_pcba_minimum':b['multiplicity']*modules>=minimum} for b in boards],
  'pcb_fabrication_minimum':'NOT_SOURCED',
  'attrition':'NOT_SOURCED as a JLC rule: pieces_required adds none. The dated parts-API audits calculate pieces_to_buy from loss_number / least_patch_number / min_purchase, whose meanings are our inference ('+PROJECTION+', confidence INFERRED).',
  'sourcing_preference':{'owner_words':read(root, OWNER_DECISIONS)['sourcing_preference']['owner_words'],'our_reading':list(SOURCING_ROUTES),'status':'PENDING_OWNER_CONFIRMATION'},
  'lines':order_lines,
  'outside_pcba':'External materials, cables, mechanical parts and fixture items are outside the JLC parts library and not yet routed under the preference.'}


def spellings(root, lcsc, source):
 """Observed spellings the reviewed crosswalk allows for this LCSC code in this exact source file; no other equivalence is guessed."""
 out = set()
 for entry in read(root, CROSSWALK).get('spelling_crosswalk', []):
  if entry['lcsc'] == lcsc:
   out |= {o['spelling'] for o in entry['observed_spellings'] if source in o['sources']}
 return out


def by_lcsc(items, source):
 result = {}
 for item in items:
  if item['lcsc'] in result:
   raise ValueError(f"ambiguous evidence: {item['lcsc']} appears twice in {source}")
  result[item['lcsc']] = item
 return result


def check_identity(root, lcsc, ident, mpn, manufacturer, source):
 if mpn != ident['mpn'] and mpn not in spellings(root, lcsc, source):
  raise ValueError(f'{lcsc}: {source} names MPN {mpn!r}, the fitted identity is {ident["mpn"]!r}')
 if manufacturer is not None and manufacturer != ident['manufacturer']:
  raise ValueError(f'{lcsc}: {source} names manufacturer {manufacturer!r}, the fitted identity is {ident["manufacturer"]!r}')


def audit_lines(audit):
 """Rows of a dated parts-API audit: 2026-11-12 kept them under after.lines (before/after the SW1 change); later audits use lines."""
 return audit['lines'] if 'lines' in audit else audit['after']['lines']


def listed_spelling(root, lcsc, ident, listed, source):
 """A distributor's verbatim listing title may only be the fitted MPN or a spelling the reviewed crosswalk already records for this LCSC code."""
 known = {o['spelling'] for e in read(root, CROSSWALK).get('spelling_crosswalk', []) if e['lcsc'] == lcsc for o in e['observed_spellings']}
 if listed != ident['mpn'] and listed not in known:
  raise ValueError(f'{lcsc}: {source} lists model {listed!r}, which is neither the fitted MPN {ident["mpn"]!r} nor a reviewed crosswalk spelling')


def page_block(root, lcsc, ident, page, source, recency):
 check_identity(root, lcsc, ident, page['model'], None, source)
 if 'model_as_listed' in page:
  listed_spelling(root, lcsc, ident, page['model_as_listed'], source)
 stored = page.get('stored')
 return {'status': 'OBSERVED', 'recency': recency, 'source': source, 'url': page['url'], 'observed_at': page['retrieved_at'],
  'raw_sha256': page['raw_sha256'], 'raw_stored': bool(stored), **({'stored_private': dict(stored, repository=PRIVATE_REPOSITORY)} if stored else {}),
  'identity_matched': 'LCSC code and MPN (the receipt carries no manufacturer field)',
  'observed': {k: page[k] for k in ('library', 'in_stock', 'preorder_available', 'preorder_minimum', 'packaging_quantity', 'loss_number', 'least_patch_number', 'buyable')},
  'displayed_labels': {'pcba_type': page['pcba_type'], 'assembly_type': page['assembly_type']},
  'field_meanings': 'INFERRED (sources.listing_pages.field_meanings)'}


def api_block(root, lcsc, ident, row, required, audit, path, receipts, recency):
 check_identity(root, lcsc, ident, row['mpn'], row['manufacturer'], path)
 if 'model_as_listed' in row:
  listed_spelling(root, lcsc, ident, row['model_as_listed'], path)
 if row['pieces_required'] != required:
  raise ValueError(f'{lcsc}: audit pieces_required {row["pieces_required"]} differs from the ledger {required} (quantity semantics changed)')
 # The audit's own stated rule, recomputed so a copied buy quantity or cost cannot drift from it.
 if row['pieces_to_buy'] != max(required + row['loss_number'], row['least_patch_number'], row['min_purchase']) \
    or abs(row['line_cost'] - row['pieces_to_buy'] * row['unit_price']) > 1e-6:
  raise ValueError(f'{lcsc}: audit pieces_to_buy or line_cost does not follow its cost_rule')
 api_time = audit['sources']['parts_api'].get('retrieved_at')
 if row.get('raw_sha256'):
  # Per-row reads: each row carries its own served-bytes digest and a private stored copy, read on the audit date.
  if not row['retrieved_at'].startswith(audit['date'] + 'T') or not (row.get('stored') or {}).get('path') or not re.fullmatch('[0-9a-f]{64}', row['raw_sha256']):
   raise ValueError(f'{lcsc}: audit row time, digest or stored copy does not match its {audit["date"]} audit')
  origin, raw, reused = 'parts-API read ' + row['retrieved_at'], row['raw_sha256'], None
 else:
  # A row is either from the audit's own API read (no raw digest) or reused from a hash-bound supply receipt of the same time.
  reused = [o for o in receipts.get(lcsc, []) if o['retrieved_at'] == row['retrieved_at'] and o.get('raw_sha256')]
  if row['retrieved_at'] != api_time and len(reused) != 1:
   raise ValueError(f'{lcsc}: audit row time matches neither the parts-API read nor one hash-bound supply receipt')
  origin = SUPPLY_OBSERVATIONS + '#' + reused[0]['id'] if row['retrieved_at'] != api_time else 'parts-API read ' + api_time
  raw = reused[0]['raw_sha256'] if row['retrieved_at'] != api_time else None
 block = {'status': 'OBSERVED', 'recency': recency, 'source': path + ('#lines' if 'lines' in audit else '#after.lines'), 'url': audit['sources']['parts_api']['url'], 'observed_at': row['retrieved_at'],
  'raw_sha256': raw, 'raw_stored': bool(row.get('stored')), 'identity_matched': 'LCSC code, MPN and manufacturer', 'row_origin': origin,
  'observed': {k: row[k] for k in ('library', 'jlc_stock', 'min_purchase', 'least_patch_number', 'loss_number', 'unit_price')},
  'currency': {'value': 'USD', 'status': 'INFERRED', 'basis': audit['currency_note']},
  'calculated': {'pieces_to_buy': row['pieces_to_buy'], 'line_cost': row['line_cost'], 'rule': audit['cost_rule'], 'confidence': 'INFERRED'},
  'field_meanings': 'INFERRED: undocumented API fields read as JLC stock, minimum purchase, minimum patch and attrition'}
 if row.get('stored'):
  block['stored_private'] = dict(row['stored'])
  block['observed'].update({k: row[k] for k in ('presale_available', 'preorder_minimum', 'packaging_quantity', 'buyable', 'estimate_date')})
 return block


def dated_audits(root):
 """(latest, history): the newest dated parts-API audit first, older ones kept unchanged as history. File name, date and row times must agree."""
 audits = []
 for path in [PRICE_AUDIT] + PRICE_AUDIT_HISTORY:
  a = read(root, path)
  if Path(path).stem != a.get('date'):
   raise ValueError(f'{path}: file name and audit date differ')
  audits.append((path, a))
 latest, history = audits[0], audits[1:]
 if any(h[1]['date'] >= latest[1]['date'] for h in history):
  raise ValueError(f'stale observation presented as latest: {PRICE_AUDIT} is not newer than every history audit')
 return latest, history


def sourcing_projection(root, rows, modules):
 """Per fitted identity: the latest dated observation, the older ones as history, our inference, and what was never obtained."""
 active = {}
 for r in rows:
  if r['population'] != 'FITTED':
   continue
  ident = {'manufacturer': r['manufacturer'], 'mpn': r['mpn']}
  if active.setdefault(r['lcsc'], dict(ident, pieces_per_module=0))['mpn'] != r['mpn'] or active[r['lcsc']]['manufacturer'] != r['manufacturer']:
   raise ValueError(f"{r['lcsc']}: two fitted identities share one LCSC code")
  active[r['lcsc']]['pieces_per_module'] += r['quantity_per_module']
 retired_active = set(active) & set(RETIRED)
 if retired_active:
  raise ValueError(f'retired part fitted again: {sorted(retired_active)}; review RETIRED')
 pages_doc, supply = read(root, LISTING_PAGES), read(root, SUPPLY_OBSERVATIONS)
 (audit_path, audit), audit_history = dated_audits(root)
 pages = by_lcsc(pages_doc['parts'], LISTING_PAGES)
 page_history = []
 for h in pages_doc.get('parts_history', []):
  if h['date'] >= pages_doc.get('parts_date', ''):
   raise ValueError(f'stale observation presented as latest: {LISTING_PAGES} parts_date is not newer than parts_history {h["date"]}')
  page_history.append((h['date'], by_lcsc(h['parts'], LISTING_PAGES + '#parts_history')))
 if any(not p['retrieved_at'].startswith(pages_doc.get('parts_date', '') + 'T') for p in pages.values()):
  raise ValueError(f'{LISTING_PAGES}: a "parts" receipt is not from parts_date {pages_doc.get("parts_date")}')
 api = by_lcsc(audit_lines(audit), audit_path)
 api_history = [(h['date'], p, h, by_lcsc(audit_lines(h), p)) for p, h in audit_history]
 receipts = {}
 for o in supply['observations']:
  receipts.setdefault(o['lcsc'], []).append(o)
 for source, codes in ((LISTING_PAGES, pages), (audit_path, api), (SUPPLY_OBSERVATIONS, receipts)) \
   + tuple((LISTING_PAGES + '#parts_history', c) for _, c in page_history) + tuple((p, c) for _, p, _, c in api_history):
  unknown = sorted(set(codes) - set(active) - set(RETIRED))
  if unknown:
   raise ValueError(f'{source}: evidence for parts outside the fitted population and the retired list: {unknown}')
 if set(api) & set(RETIRED) or any(set(c) & set(RETIRED) for _, _, _, c in api_history) or set(pages) & set(RETIRED):
  raise ValueError(f'{audit_path}: lines must hold only the current fitted identities')
 lines = []
 for lcsc, ident in sorted(active.items()):
  required = ident['pieces_per_module'] * modules
  page, row = pages.get(lcsc), api.get(lcsc)
  line = {'lcsc': lcsc, 'mpn': ident['mpn'], 'manufacturer': ident['manufacturer'], 'pieces_per_module': ident['pieces_per_module'], 'pieces_required': required}
  line['listing_page'] = page_block(root, lcsc, ident, page, LISTING_PAGES, 'LATEST_DATED') if page else {'status': 'GAP', 'reason': 'no dated rendered-page receipt for this identity'}
  line['parts_api'] = api_block(root, lcsc, ident, row, required, audit, audit_path, receipts, 'LATEST_DATED') if row else {'status': 'GAP', 'reason': 'no row in the latest dated parts-API audit for this identity'}
  history = []
  for date, codes in page_history:
   if lcsc in codes:
    history.append(dict(page_block(root, lcsc, ident, codes[lcsc], LISTING_PAGES + '#parts_history', 'HISTORY'), kind='listing_page', date=date))
  for date, path, h, codes in api_history:
   if lcsc in codes:
    history.append(dict(api_block(root, lcsc, ident, codes[lcsc], required, h, path, receipts, 'HISTORY'), kind='parts_api', date=date))
  # No older read may be shown as the latest: every LATEST_DATED block must be at least as new as each history block and each supply receipt.
  latest_times = [b['observed_at'] for b in (line['listing_page'], line['parts_api']) if b['status'] == 'OBSERVED']
  older = [b['observed_at'] for b in history] + [o['retrieved_at'] for o in receipts.get(lcsc, [])]
  if latest_times and older and min(latest_times) <= max(older):
   raise ValueError(f'{lcsc}: stale observation presented as latest ({min(latest_times)} is not newer than {max(older)})')
  line['history'] = history
  hashed = []
  for o in receipts.get(lcsc, []):
   check_identity(root, lcsc, ident, o['mpn'], None, SUPPLY_OBSERVATIONS)
   hashed.append({'id': o['id'], 'observed_at': o['retrieved_at'], 'raw_sha256': o['raw_sha256'], 'raw_stored': o['raw_stored'], 'source': o.get('source'), 'recency': 'HISTORY'})
  line['supply_receipts'] = hashed
  stock = [b['observed'][k] for b, k in ((line['listing_page'], 'in_stock'), (line['parts_api'], 'jlc_stock')) if b['status'] == 'OBSERVED']
  line['listing_shortfall'] = ({'status': 'SHORTFALL_AT_LATEST_OBSERVATION', 'jlc_stock': min(stock), 'pieces_required': required,
                               'observed_at': max(latest_times),
                               **({k: line['listing_page']['observed'][k] for k in ('preorder_available', 'preorder_minimum')} if line['listing_page']['status'] == 'OBSERVED' else {}),
                               'field_meanings': 'INFERRED'} if stock and min(stock) < required else None)
  line['raw_bytes'] = ('PRIVATE_SANITIZED_COPY: served-bytes SHA-256 here, sanitized copy in ' + PRIVATE_REPOSITORY if line['parts_api'].get('raw_stored')
                       else 'NOT_COMMITTED: receipts keep only their SHA-256') + '; 2026-11-12 history rows keep only digests (the parts-API audit rows were re-serialised without a raw digest)'
  line['not_obtained'] = list(NOT_OBTAINED)
  lines.append(line)
 if sum(l['pieces_required'] for l in lines) != modules * sum(l['pieces_per_module'] for l in lines):
  raise ValueError('pieces_required total is not modules x fitted pieces per module')
 api_total = round(sum(l['parts_api']['calculated']['line_cost'] for l in lines if l['parts_api']['status'] == 'OBSERVED'), 2)
 if all(l['parts_api']['status'] == 'OBSERVED' for l in lines) and api_total != audit['parts_total']:
  raise ValueError('audit parts_total differs from the sum of its lines')
 retired = []
 for lcsc, info in sorted(RETIRED.items()):
  evidence = []
  for date, codes in page_history:
   if lcsc in codes:
    check_identity(root, lcsc, info, codes[lcsc]['model'], None, LISTING_PAGES)
    evidence.append(f'{LISTING_PAGES}#parts_history[{date}]/{lcsc}')
  retired.append({'lcsc': lcsc, 'mpn': info['mpn'], 'reason': info['reason'],
   'evidence': evidence + [SUPPLY_OBSERVATIONS+'#'+o['id'] for o in receipts.get(lcsc, [])]})
 counts = lambda k: {lib: sum(1 for l in lines if l[k]['status'] == 'OBSERVED' and l[k]['observed']['library'] == lib) for lib in ('BASIC', 'EXTENDED')}
 page_times = sorted(l['listing_page']['observed_at'] for l in lines if l['listing_page']['status'] == 'OBSERVED')
 api_times = sorted(l['parts_api']['observed_at'] for l in lines if l['parts_api']['status'] == 'OBSERVED')
 differs = sorted(l['lcsc'] for l in lines if l['listing_page']['status'] == l['parts_api']['status'] == 'OBSERVED'
                  and l['listing_page']['observed']['in_stock'] != l['parts_api']['observed']['jlc_stock'])
 return {'schema': 1, 'status': 'DATED_OBSERVATIONS_NOT_CURRENT_STOCK_OR_QUOTE', 'revision': 'A7-r2-3HP-FR4', 'modules': modules,
  'observation_date': audit['date'],
  'history_dates': sorted({h['date'] for l in lines for h in l['history']}, reverse=True),
  'scope': 'Latest dated JLC listing observations for the active fitted identities, with older reads kept as history. A dated listing is not current stock, a quote, a reservation, a lead time or assembly acceptance; refresh before ordering. Quantities are fitted pieces x modules before attrition.',
  'sources': {'listing_pages': {'path': LISTING_PAGES, 'sha256': sha(root, LISTING_PAGES), 'observed_between': [page_times[0], page_times[-1]] if page_times else None,
                                'field_meanings': {'status': pages_doc['part_field_meanings']['status'], 'note': pages_doc['part_field_meanings']['note']}},
              'parts_api': {'path': audit_path, 'sha256': sha(root, audit_path), 'observed_between': [api_times[0], api_times[-1]] if api_times else None},
              'history': [{'path': p, 'sha256': sha(root, p), 'date': h['date']} for p, h in audit_history] + [{'path': LISTING_PAGES + '#parts_history', 'date': d} for d, _ in page_history],
              'supply_observations': {'path': SUPPLY_OBSERVATIONS, 'sha256': sha(root, SUPPLY_OBSERVATIONS)}},
  'not_one_snapshot': 'Rendered part pages and the parts-API rows are separate reads at different times; their stock figures differ for '+str(len(differs))+' identities and neither is a simultaneous supplier snapshot.',
  'stock_differs_between_reads': differs,
  'active_identities': len(lines), 'pieces_required_total': sum(l['pieces_required'] for l in lines),
  'library_counts': {'listing_page': counts('listing_page'), 'parts_api': counts('parts_api')},
  'listing_shortfalls': [l['lcsc'] for l in lines if l['listing_shortfall']],
  'minimum_purchase_above_need': sorted(l['lcsc'] for l in lines if l['parts_api']['status'] == 'OBSERVED' and l['parts_api']['observed']['min_purchase'] > l['pieces_required']),
  'parts_api_calculated_total': {'value': api_total, 'currency': 'USD (INFERRED)', 'confidence': 'INFERRED', 'excludes': audit['not_included']},
  'gaps': {k: sorted(l['lcsc'] for l in lines if l[k]['status'] == 'GAP') for k in ('listing_page', 'parts_api')},
  'not_obtained_for_any_line': list(NOT_OBTAINED),
  'retired': retired, 'lines': lines}


def supply_text(projection):
 n, gaps = projection['active_identities'], projection['gaps']
 both = n - len(set(gaps['listing_page']) | set(gaps['parts_api']))
 text = (f"Order quantity is {projection['modules']} modules (owner decision), {projection['pieces_required_total']} fitted pieces before attrition. "
         f"{both} of {n} fitted identities have dated {projection['observation_date']} JLC listing observations from both the rendered part pages and the parts API "
         f"(separate reads, field meanings and currency inferred; {', '.join(projection['history_dates'])} reads kept as history; {PROJECTION}).")
 for k, label in (('listing_page', 'rendered-page receipt'), ('parts_api', 'parts-API row')):
  if gaps[k]:
   text += f" No {label}: {', '.join(gaps[k])}."
 short = [l for l in projection['lines'] if l['listing_shortfall']]
 if short:
  text += ' Listed JLC stock below the 2-module need at ' + projection['observation_date'] + ': ' + '; '.join(
   f"{l['mpn']} ({l['lcsc']}) stock {l['listing_shortfall']['jlc_stock']} for {l['pieces_required']}" for l in short) + ' (no substitute chosen).'
 if projection['minimum_purchase_above_need']:
  text += ' Listed minimum purchase above the need: ' + ', '.join(projection['minimum_purchase_above_need']) + '.'
 return text + (' Not obtained for any line: lead time, confirmed quote, stock reservation and assembly acceptance. '
                'JLC attrition is not sourced as a rule; the audit\'s buy quantities are our inference. Refresh before ordering.')


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
 {'id':'supply-observations','class':'ACCESS_EVIDENCE_HOLD','text':'(generated from the sourcing projection)'},
 {'id':'switch-supply','class':'OWNER_DECISION','text':'PCM13SMTR (C221842): 2 needed for 2 modules. JLC stock 0 at 2026-11-09; at 2026-11-12 JLC lists it buyable (Extended) with pre-order minimum 3 and presale 0 (field meanings inferred), tier prices without currency, no lead time. The owner wants to complete on JLC: on our reading, a pre-order (presale 0 may mean none can be placed now; fill depends on LCSC stock, not observed) or a Global Sourcing quote; otherwise wait, or accept a reviewed alternate with its own contact table and fit review. At 2026-11-12T18:55Z the owner relayed a live check by their browsing assistant (not a first-hand capture): JLC stock 0, Extended, pre-order offered at minimum 3 with an estimated 31 days; Global Sourcing for 3 via DigiKey JPY 826 total (8-15 business days) or Element JPY 865 (8-18); parts stay in the JLC parts library. The owner accepted JLC sourcing with all recommendations, then asked to consider another switch because of the price, so this stays open until the owner picks.'},
 {'id':'panel-route','class':'OWNER_DECISION','text':'None of the three boards meets JLC single-board PCBA size; the panel route is not chosen. Panel by JLCPCB puts 10 controllers, 8 leaves or 2 adapters on each panel (20 SW1 switches for a 2-panel minimum if the PCBA quantity counts panels, not sourced); a repo-built panel holding 1 controller, 2 leaves or 1 adapter gives exactly 2 modules; it is prepared (not released) in engineering/a7/jlc-package/panels/. Comparison in engineering/a7/jlc-package/package.json.'},
 {'id':'jack-switch-qualification','class':'PHYSICAL_ONLY','text':'PJ-324M pin function (which of terminals 4/5 is the tip contact and which its normal; the supplier symbol contradicts the inferred 4 = tip, so this continuity test must precede any PCB order), slot, axis height and nut fit, and the HX MSK13C02 truth table and land/peg fit, need received parts (jack-continuity, jack-dimensions, switch-fit).'},
 {'id':'exact-part-evidence','class':'ACCESS_EVIDENCE_HOLD','text':'Exact-part gaps after the 2026-11-11 source recovery (the PMEG4010CEJ ,115 packing is since sourced: SOD323F on a 7-inch reel, fact-pmeg4010cej-115-orderable): SM04B-SRSS-TB per-circuit numbering not printed beyond the No. 1 end; PJ-324M recommended hole/slot sizes, axis height and whether a nut ships with C22355739 not sourced.'},
 {'id':'finished-cables','class':'OWNER_DECISION','text':'(generated from mechanical/layout.json power_cable_requirement)'},
 {'id':'mechanical-materials','class':'ACCESS_EVIDENCE_HOLD','text':'PMMA sheet and pocket tolerances, PETG process and orderable fastener part numbers are not sourced; the model carries designations from the current mechanical layout and envelopes only; exact orderable hardware and assembly fit remain unqualified.'},
 {'id':'rack-hardware','class':'OWNER_DECISION','text':'Owner rack rail/thread interface and fasteners not specified.'},
 {'id':'prototype-and-release','class':'OWNER_DECISION','text':'No reviewed manufacturing package and no manufacturing release approval. A prototype route, when the owner approves one, is recorded in engineering/a7/qualification/records.json and is not a release.'},
]


def supplier_requests(report):
 """Prepared, unsent requests for the parts outside the JLC parts library. Values come from the manifest; supplier answers stay null until received."""
 modules = report['agreed_order_quantity']
 ext = {e['id']: e for e in report['external_materials']}
 pc = ext['finished-power-cable']
 req = pc['requirement']
 crossed = ', '.join(f"J5.{r['a_pin']}->J2.{r['b_pin']} ({r['a_net']})" for r in pc['pin_map'])
 def base(i, to, qty, spec, ask, **extra):
  return dict({'id': i, 'to': to, 'quantity_for_order': qty, 'specification': spec, 'ask': ask}, **extra, supplier_answer=None, status='PREPARED_NOT_SENT')
 out = [base('finished-power-cable', 'cable assembler (owner decision finished-cables: assembler); no assembler selected', pc['quantity_per_module'] * modules,
   {'free_span_nominal_mm': req['finished_free_span_nominal'], 'tolerance_mm': req['tolerance'], 'tolerance_confidence': req['tolerance_confidence'],
    'order_band_mm': req['band'], 'stowage': req['stowage'], 'ends': 'controller J5 and power adapter J2, both MOLEX 530470310 (C122442) 3-pin headers',
    'pin_map': crossed, 'source': LAYOUT + '#power_cable_requirement'},
   ['the finished length and tolerance the assembler will guarantee against the order band, and the measurement datum',
    'mating housing and crimp terminal part numbers for the 530470310 header', 'wire gauge, insulation and minimum bend radius',
    'polarity marking and the inspection performed'],
   not_a_substitute='historical A5 Molex 151340300 (50 ±6 mm) does not fit the A7 band')]
 sh4 = ext['finished-sh4']
 out.append(base('finished-sh4', 'cable supplier; candidate not confirmed', sh4['quantity_per_module'] * modules,
   {'requirement': sh4['requirement'], 'candidate': sh4['candidate'], 'pin_maps': {k: ', '.join(f"{r['a_pin']}->{r['b_pin']}" for r in v) for k, v in sh4['pin_maps'].items()}, 'source': sh4['source']},
   ['finished length and tolerance', 'conductor order end to end (1:1) and housing orientation', 'wire gauge']))
 idc = ext['eurorack-idc-ribbon']
 out.append(base('eurorack-idc-ribbon', 'cable supplier; not selected', idc['quantity_per_module'] * modules, {'requirement': idc['requirement']},
   ['keyed 16-to-10 construction and stripe position', 'finished length', 'strain relief']))
 hw = sorted(e['id'] for e in report['external_materials'] if e.get('kind') == 'standard_hardware_envelope')
 out.append(base('standard-hardware', 'fastener supplier; not selected', {i: ext[i]['quantity_per_module'] * modules for i in hw},
   {'designations': {i: ext[i]['description'] for i in hw if ext[i]['description'] != i}, 'envelopes': {i: ext[i]['bbox_mm'] for i in hw}, 'source': ext[hw[0]]['source']},
   ['orderable part numbers matching each envelope and designation (envelopes are not order codes)', 'material and finish',
    'whether a nut ships with PJ-324M (C22355739) or an M6x0.5 nut must be bought (engineering/a7/qualification/supplier-questions.md)']))
 made = sorted(e['id'] for e in report['external_materials'] if e.get('kind') in ('printable_design', 'manufacturing_artwork'))
 out.append(base('printed-and-cut-parts', 'PMMA cutter and PETG printing (supplier or own printer); not selected', {i: ext[i]['quantity_per_module'] * modules for i in made},
   {'kinds': {i: ext[i]['kind'] for i in made}, 'source': ext[made[0]]['source']},
   ['guaranteed tolerances for thickness, holes and pockets', 'material grade and finish', 'process settings for the PETG parts']))
 for i in ('leaf-bond-line', 'right-leaf-unused-J2-cover', 'rack-mount-hardware'):
  e = ext[i]
  out.append(base(i, 'owner' if i == 'rack-mount-hardware' else 'material supplier; not selected',
   None if e['quantity_per_module'] is None else e['quantity_per_module'] * modules, {'requirement': e['requirement']},
   ['the case model (rail and thread interface)'] if i == 'rack-mount-hardware' else ['material identity and thickness', 'datasheet values for the use']))
 return {'schema': 1, 'status': 'PREPARED_NOT_SENT', 'modules': modules,
  'note': 'Requests prepared for parts outside the JLC parts library. Nothing here was sent, and no supplier answer or guarantee is recorded; each supplier_answer stays null until a dated reply is saved. Quantities are per-module counts from assembly-manifest.json times the owner-decided modules, without spares.',
  'requests': out}


def outputs(report, projection):
 raw=json.dumps(report,indent=2,ensure_ascii=False)+'\n'
 stream=io.StringIO();writer=csv.writer(stream,lineterminator="\n");writer.writerow(['ENGINEERING ONLY - NOT SUPPLIER UPLOAD'])
 writer.writerow(['board','ref','manufacturer','mpn','lcsc','population','mount','per_board','board_multiplicity','per_module','side'])
 for r in report['population']:
  writer.writerow([r[k] for k in ['board','ref','manufacturer','mpn','lcsc','population','mount','quantity_per_board','board_multiplicity','quantity_per_module']]+[r['placement']['side']])
 op,pj=report['order_plan'],projection
 lib=pj['library_counts']['listing_page']
 md='# A7 調達・組立の準備台帳\n\n自動生成。**製造承認・発注用ファイルではありません。** SW1 はオーナーの方針（動けばよい・安く・JLC 在庫あり）により 2026-11-12 に PCM13SMTR（C221842）から HX MSK13C02（C5149819）へ変更しました。PCM13SMTR は現在の実装部品ではなく、その観測は履歴として残すだけです。\n\n'
 hist=', '.join(pj['history_dates'])
 md+=(f"実装する {pj['active_identities']} 型番すべてについて、{pj['observation_date']} に JLC の部品ページと部品 API を匿名で読み直しました（`{PROJECTION}`）。"
      f"部品ページ（{pj['sources']['listing_pages']['observed_between'][0]}〜{pj['sources']['listing_pages']['observed_between'][1]}）と部品 API（{pj['sources']['parts_api']['observed_between'][0]}〜{pj['sources']['parts_api']['observed_between'][1]}）は別々の読み取りで、"
      f"取得時刻・受信バイトの SHA-256 をここに、匿名化した写しを非公開リポジトリに保存しています（在庫の数字が異なる型番 {len(pj['stock_differs_between_reads'])}）。Basic {lib['BASIC']} / Extended {lib['EXTENDED']}。"
      f"{hist} の観測は履歴としてそのまま残し、最新としては扱いません。項目の意味と通貨（USD）はこちらの解釈です。**日付付きの掲載観測であり、現在の在庫・見積・在庫確保・実装受入ではありません。** 納期・確定見積・在庫確保・実装受入はどの型番も未取得です。発注前に取り直してください。\n\n")
 md+=f"台帳 SHA-256: `{hashlib.sha256(raw.encode()).hexdigest()}`。{report['fitted_unique_placements']} 配置 / {report['fitted_pieces_per_module']} 実装点 / 台。\n\n"
 md+=f"## 最初の発注数量: {op['modules']} 台（オーナーの判断）\n\nオーナーの言葉: 「{' '.join(op['owner_words'])}」（`{op['decision']}`）。JLC の PCBA 最小 {op['pcba_minimum_boards']['value']} 枚は {op['pcba_minimum_boards']['status']}（{'JLC の公開能力表で確認済み' if op['pcba_minimum_boards']['status']=='SOURCED' else 'JLC の公開条件では未確認'}）。この数量は発注・試作ルート・製造リリースの承認ではありません。\n\n"
 md+="必要枚数: "+'、'.join(f"{b['board']} {b['boards_needed']} 枚" for b in op['boards'])+f"。必要数は実装点数 × {op['modules']} 台で計 {pj['pieces_required_total']} 個（ロス分を含まない）。PCB 製造の最小枚数と JLC のロス分（attrition）の規則は未取得です。下の「購入数（推定）」は価格点検が API の項目（loss_number / least_patch_number / min_purchase、意味はこちらの解釈）から計算した値です。\n\n"
 md+=f"オーナーの方針（原文）: 「{' '.join(op['sourcing_preference']['owner_words'])}」。こちらの解釈（オーナー未確認）: JLC 在庫 → JLC 予約注文または Global Sourcing → それ以外は例外として行ごとに明示。\n\n"
 hd=pj['history_dates'][0] if pj['history_dates'] else None
 md+=f"| LCSC | 型番 | 区分 | 必要数 | ページ在庫 | API 在庫 | 最小購入 | 購入数（推定） | 単価（USD と推定） | 在庫 {hd}（履歴） | 経路 |\n|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|\n"
 routes={o['lcsc']:o['sourcing']['route'] for o in op['lines']}
 for l in pj['lines']:
  pg,ap=l['listing_page'],l['parts_api']
  cell=lambda o,k:o['observed'][k] if o['status']=='OBSERVED' else '未取得'
  old=next((h['observed']['jlc_stock'] for h in l['history'] if h['kind']=='parts_api' and h['date']==hd),'—')
  flag=' **不足**' if l['listing_shortfall'] else ''
  md+=f"| {l['lcsc']} | {l['mpn']} | {cell(pg,'library') if pg['status']=='OBSERVED' else cell(ap,'library')} | {l['pieces_required']} | {cell(pg,'in_stock')}{flag} | {cell(ap,'jlc_stock')} | {cell(ap,'min_purchase')} | {ap['calculated']['pieces_to_buy'] if ap['status']=='OBSERVED' else '未取得'} | {cell(ap,'unit_price')} | {old} | {routes[l['lcsc']]} |\n"
 if pj['listing_shortfalls']:
  md+="\n**掲載在庫が 2 台分に足りない型番**: "+'、'.join(f"{l['mpn']}（{l['lcsc']}）在庫 {l['listing_shortfall']['jlc_stock']} / 必要 {l['pieces_required']}" for l in pj['lines'] if l['listing_shortfall'])+"。代替品は選んでいません（オーナー方針の優先順で、JLC 予約注文・Global Sourcing・待つ・別途レビューした代替のいずれか）。\n"
 if pj['minimum_purchase_above_need']:
  md+="\n最小購入数が必要数を上回る型番: "+'、'.join(pj['minimum_purchase_above_need'])+"（購入数の推定に反映）。\n"
 md+=f"\n部品代の計算値（推定、USD と推定）: {pj['parts_api_calculated_total']['value']}。段取り料金・PCB 製造・送料・税などは含みません。外された PCM13SMTR（C221842）は `retired` に履歴として残し、必要数に含めません。\n\n"
 md+=f"| 基板 | 枚数/台 | 実装点/枚 | SMD F/B | THT F/B | PCB SHA-256 |\n|---|---:|---:|---|---|---|\n"
 for b in report['boards']:
  pr=b['assembly_process_per_board']
  md+=f"| {b['board']} | {b['multiplicity']} | {b['fitted_per_board']} | {pr['SMD_F']}/{pr['SMD_B']} | {pr['THT_F']}/{pr['THT_B']} | `{b['pcb_sha256']}` |\n"
 md+=f"\n実装する型番は {report['unique_fitted_identities']} 種類。SMD / THT の区別はコントローラーが native geometry のパッド属性、リーフが採用した A7 PCB のパッド属性、アダプタが不変 A5 の配置データのパッド属性から生成しています。コントローラーは両面 SMD と F 面 THT の組合せで、実装サービスの受入は未確認です。\n\n## 未解決事項\n\n| ID | 区分 | 内容 |\n|---|---|---|\n"
 for b in report['blockers']:md+=f"| {b['id']} | {b['class']} | {b['text']} |\n"
 md+='\n外部部材・ケーブル・治具・サービスの詳細は `assembly-manifest.json` を参照してください。TP1–TP5 は購入部品に数えません。治具数量は台数に掛けません。B面・角度・位置は元の KiCad 出力とハッシュに追跡できますが、この台帳だけでは新規 native 検証や実装方向の承認になりません。\n'
 return {'assembly-manifest.json':raw,'population.csv':stream.getvalue(),'ledger.md':md,
         'sourcing-projection.json':json.dumps(projection,indent=2,ensure_ascii=False)+'\n',
         'supplier-requests.json':json.dumps(supplier_requests(report),indent=2,ensure_ascii=False)+'\n'}


def validate_report(report, root=ROOT):
 if report != generate(root):
  raise ValueError("ledger differs from exact current population, multiplicity or input identities")


def main():
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args()
 for name,contents in outputs(*build()).items():
  path=ROOT/OUT/name
  if args.check:
   if not path.exists() or path.read_text()!=contents:raise ValueError(f'stale ledger: {path}')
  else:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(contents)
 print('PASS: A7 engineering ledger and sourcing projection accounted; dated observations only; NOT order/release eligibility')

if __name__=='__main__':main()
