"""Independent electrical-interface checks on KiCad's exported XML netlists.

Pass the three native exports in this order: controller, LED leaf, power adapter.
The assertions encode manufacturer pin numbers and the external cable pin maps,
not the schematic generator's data. They do not replace ERC, DRC or bench tests.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]

def netlist(path):
    root = ET.parse(path).getroot()
    pins = {}
    components = {}
    for net in root.findall('./nets/net'):
        for node in net.findall('node'):
            key = (node.attrib['ref'], node.attrib['pin'])
            if key in pins:
                raise ValueError(f'Duplicate exported pin: {key}')
            pins[key] = net.attrib['name']
    for comp in root.findall('./components/comp'):
        ref = comp.attrib['ref']
        fields = {f.attrib.get('name',''): f.text or '' for f in comp.findall('./fields/field')}
        codes = set(re.findall(r'\bC\d{3,}\b',fields.get('LCSC','')))
        components[ref] = {'fields': fields, 'c_codes': sorted(codes)}
    return pins, components

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('controller', type=Path)
    ap.add_argument('led_leaf', type=Path)
    ap.add_argument('power_adapter', type=Path)
    ap.add_argument('--output', type=Path, default=ROOT/'integration/schematic_interface_check.json')
    args = ap.parse_args()
    paths = {name:getattr(args,name) for name in ('controller','led_leaf','power_adapter')}
    lists = {name:netlist(p) for name,p in paths.items()}
    c,leaf,adapter = (lists[n][0] for n in paths)
    checks=[]
    def same(board, label, *nodes):
        values=[board.get((ref,str(pin))) for ref,pin in nodes]
        passed=all(v is not None for v in values) and len(set(values))==1
        checks.append({'check':label,'pins':[f'{r}.{p}' for r,p in nodes],
                       'exported_nets':values,'passed':passed})
    same(c,'Passive CV IN to THRU',('J1',6),('J2',6),('R1',1))
    same(c,'Jack grounds and MCU VSS',('J1',2),('J1',3),('J2',2),('J2',3),('U1',4))
    same(c,'20 Mohm pickup midpoint',('R1',2),('R2',1),('U6',3))
    same(c,'OPA197 voltage follower',('U6',1),('U6',4),('R3',1))
    same(c,'Four-resistor affine node with C13 upstream of R7',('R3',2),('R4',2),('R5',2),('R6',1),('R7',1),('C13',1))
    same(c,'Affine 3V3 feeds',('R4',1),('R5',1),('U1',3),('U7',5))
    same(c,'A5 protected buffer input after R7',('R7',2),('U7',3),('D3',3))
    checks.append({'check':'C13 stored charge must pass through R7 before reaching U7 input',
                   'passed':c.get(('C13','1'))==c.get(('R7','1')) and c.get(('R7','1'))!=c.get(('U7','3'))})
    same(c,'A5 output follower and series resistor',('U7',1),('U7',4),('R24',1))
    same(c,'A5 ADC PA0 after output divider',('R24',2),('R25',1),('U1',6))
    same(c,'A5 divider and buffer grounds',('R25',2),('U7',2),('U1',4),('R6',2),('R2',2))
    same(c,'LED enable PA5 to NPN base resistor',('U1',11),('R22',1))
    same(c,'NPN default-off base pull-down',('R22',2),('Q1',1),('R12',1))
    same(c,'Active-low power switch enable',('Q1',3),('U4',3),('R23',2))
    same(c,'FAULT PA4 and pull-up',('U4',4),('U1',10),('R13',2))
    same(c,'Mode A PA2',('U1',8),('SW1',1),('R9',2))
    same(c,'Mode B PA3',('U1',9),('SW1',3),('R10',2))
    same(c,'Mode center common to GND',('SW1',2),('U1',4))
    same(c,'Left TIM3 CH1 PA6',('U1',12),('U5',2))
    same(c,'Right TIM3 CH2 PA7',('U1',13),('U5',3))
    same(c,'Translator direction A to B',('U5',5),('U5',1),('U1',3))
    same(c,'Translator and combined LED harness supply',('U5',8),('U4',6),('J3',2))
    same(c,'Left data to cable',('U5',7),('R14',1))
    same(c,'Left damped data',('R14',2),('J3',3))
    same(c,'Right data to cable',('U5',6),('R15',1))
    same(c,'Right damped data shares controller connector pin4',('R15',2),('J3',4))
    same(leaf,'Leaf THIS stream to first pixel and crosslink pin4',('J1',3),('D1',3),('J2',4))
    same(leaf,'Leaf OTHER stream passes directly to crosslink pin3',('J1',4),('J2',3))
    checks.append({'check':'Leaf two input streams remain electrically separate',
                   'passed':leaf.get(('J1','3')) is not None and leaf.get(('J1','4')) is not None and leaf[('J1','3')]!=leaf[('J1','4')]})
    for i in range(1,4):same(leaf,f'Pixel chain {i} to {i+1}',(f'D{i}',1),(f'D{i+1}',3))
    same(leaf,'Leaf and crosslink power distribution',('J1',2),('J2',2),*((f'D{i}',4) for i in range(1,5)),*((f'C{i}',1) for i in range(1,5)))
    same(leaf,'Leaf and crosslink ground distribution',('J1',1),('J2',1),*((f'D{i}',2) for i in range(1,5)),*((f'C{i}',2) for i in range(1,5)))
    left_inputs={leaf.get(('J1',str(pin))):c.get(('J3',str(pin))) for pin in range(1,5)}
    left_crosslink={pin:left_inputs.get(leaf.get(('J2',str(pin)))) for pin in range(1,5)}
    right_inputs={leaf.get(('J1',str(pin))):left_crosslink[pin] for pin in range(1,5)}
    checks.append({'check':'Two 1:1 harnesses deliver independent PA6 and PA7 streams to four-pixel chains',
                   'passed':left_inputs.get(leaf.get(('D1','3')))==c.get(('R14','2')) and right_inputs.get(leaf.get(('D1','3')))==c.get(('R15','2')) and c.get(('R14','2'))!=c.get(('R15','2')),
                   'left_first_pixel_net':left_inputs.get(leaf.get(('D1','3'))),
                   'right_first_pixel_net':right_inputs.get(leaf.get(('D1','3')))})
    checks.append({'check':'Both 1:1 harnesses preserve VLED and GND to the second leaf',
                   'passed':right_inputs.get(leaf.get(('D1','4')))==c.get(('U4','6')) and right_inputs.get(leaf.get(('D1','2')))==c.get(('U1','4'))})
    same(adapter,'IDC negative rail to reversed cable pin1',('J1',1),('J1',2),('J2',1))
    same(adapter,'IDC ground',*(( 'J1',i) for i in range(3,9)),('J2',2))
    same(adapter,'IDC positive rail to reversed cable pin3',('J1',9),('J1',10),('J2',3))
    same(c,'Controller positive cable pin1',('J5',1),('D1',2))
    same(c,'Controller negative cable pin3',('J5',3),('D2',1))
    expected=Counter({r['c_code']:r['qty_per_module'] for r in json.loads((ROOT/'procurement_rows.json').read_text())['components']})
    actual=Counter(); fitted={}
    for name,(_,comps) in lists.items():
        fitted[name]=0
        for ref,item in comps.items():
            if not item['c_codes']:
                if not(ref.startswith('TP') or ref.startswith('#') or ref.startswith('H')):
                    checks.append({'check':f'{name}/{ref} procurement code','passed':False,'fields':item['fields']})
                continue
            if len(item['c_codes'])!=1:raise ValueError(f'Ambiguous C code: {name}/{ref}')
            actual[item['c_codes'][0]]+=2 if name=='led_leaf' else 1
            fitted[name]+=1
    checks.append({'check':'Exported schematic fitted quantities match current procurement ledger',
                   'passed':actual==expected,'expected':dict(expected),'actual':dict(actual),'per_board':fitted})
    result={'revision':'A5','method':'Independent pin-interface assertions on KiCad XML exports',
            'all_passed':all(x['passed'] for x in checks),'checks':checks,
            'source_files':[{ 'path':str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p),
                              'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths.values()],
            'limits':['No hardware test','Does not prove analog behavior or PCB routing','Harness pin maps assume intact manufacturer cable assemblies']}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'all_passed':result['all_passed'],'checks':len(checks),'fitted_by_board':fitted,
                      'failures':[x for x in checks if not x['passed']]},indent=2))
    if not result['all_passed']:raise SystemExit(1)

if __name__=='__main__':main()
