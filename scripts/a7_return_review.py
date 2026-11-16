#!/usr/bin/env python3
"""Reproducible DC return-path screen of the actual native-derived route.

This is a resistor-network estimate, not AC/thermal or hardware qualification.
Run with the router's pinned numpy requirements. Native DRC/parity and exact
board/proposal equality remain independent prerequisites.
"""
import argparse
from collections import defaultdict
import hashlib
import heapq
import json
import math
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from a7_route import poly_dist
from a7_jlc_package import parse_sexp, kid, kids

LAYERS = ['F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu']
THICKNESS = [.035, .0152, .0152, .035]
RHO = 1.724e-5  # ohm mm at 20C, explicit material model


def polygon_contact(a,b):
    """Containment or edge intersection, including touching boundaries."""
    for p,q in ((a,b),(b,a)):
        pts = np.asarray(p)
        if np.any(poly_dist(pts[:,0],pts[:,1],q)<=1e-8): return True
    def cross(a,b,c): return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    for i,u in enumerate(a):
        v=a[(i+1)%len(a)]
        for j,x in enumerate(b):
            y=b[(j+1)%len(b)]
            if max(min(u[0],v[0]),min(x[0],y[0]))>min(max(u[0],v[0]),max(x[0],y[0]))+1e-8: continue
            if max(min(u[1],v[1]),min(x[1],y[1]))>min(max(u[1],v[1]),max(x[1],y[1]))+1e-8: continue
            if cross(u,v,x)*cross(u,v,y)<=1e-16 and cross(x,y,u)*cross(x,y,v)<=1e-16: return True
    return False


class Graph:
    def __init__(self, geometry, proposal, net='/GND'):
        self.geometry,self.proposal = geometry,proposal
        nodes, coords, edges = {}, [], []

        def node(layer, x, y):
            key = (layer, round(x*20000), round(y*20000))
            if key not in nodes:
                nodes[key] = len(coords)
                coords.append((layer, x, y))
            return nodes[key]

        for t in proposal['tracks']:
            if t['net'] != net:
                continue
            a, b = t['start'], t['end']
            layer = LAYERS.index(t['layer'])
            count = round(max(abs(a[0]-b[0]), abs(a[1]-b[1]))/.05)
            previous = node(layer, *a)
            for i in range(1, count+1):
                xy = [a[q]+(b[q]-a[q])*i/count for q in range(2)]
                current = node(layer, *xy)
                r = RHO*math.dist(a,b)/count/(t['width']*THICKNESS[layer])
                edges.append((previous,current,r))
                previous = current
        for via in proposal['vias']:
            if via['net'] != net:
                continue
            for layer, distance in enumerate([.1245,.5152,.1245]):
                edges.append((node(layer,*via['at']),node(layer+1,*via['at']),
                              RHO*distance/(math.pi*via['drill']*.018)))
        parent = list(range(len(coords)))

        def root(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        points = np.array([(p[1],p[2]) for p in coords])
        terms = {}
        for pad in geometry['pads']:
            if pad['net'] != net:
                continue
            hits = []
            for layer, polygons in pad['polys'].items():
                on_layer = np.array([p[0] == LAYERS.index(layer) for p in coords])
                for polygon in polygons:
                    hits += np.flatnonzero(on_layer & (poly_dist(points[:,0],points[:,1],polygon)<1e-6)).tolist()
            if not hits:
                raise ValueError(f'no centerline reaches {pad["ref"]}.{pad["pad"]}')
            for n in hits[1:]:
                parent[root(n)] = root(hits[0])
            terms[pad['ref']+'.'+pad['pad']] = hits[0]
        self.edges = [(root(a),root(b),r) for a,b,r in edges if root(a)!=root(b)]
        self.terms = {k:root(v) for k,v in terms.items()}
        self.coords = coords
        self.roots = [root(n) for n in range(len(coords))]
        self.adj = defaultdict(list)
        for a,b,r in self.edges:
            self.adj[a].append((b,r))
            self.adj[b].append((a,r))

    def shortest(self, start, finish):
        start, finish = self.terms[start], self.terms[finish]
        heap, best = [(0,start)], {start:0}
        while heap:
            d,n = heapq.heappop(heap)
            if d != best[n]:
                continue
            if n == finish:
                return d
            for m,r in self.adj[n]:
                if d+r < best.get(m,math.inf):
                    best[m] = d+r
                    heapq.heappush(heap,(d+r,m))
        raise ValueError('disconnected resistor model')

    def solve(self, injections, reference='J5.2'):
        ref = self.terms[reference]
        ids = {n:i for i,n in enumerate(n for n in sorted(self.adj) if n!=ref)}
        diagonal = np.zeros(len(ids))
        aa,bb,gg = [],[],[]
        for a,b,r in self.edges:
            if a!=ref: diagonal[ids[a]] += 1/r
            if b!=ref: diagonal[ids[b]] += 1/r
            if a!=ref and b!=ref:
                aa.append(ids[a]); bb.append(ids[b]); gg.append(1/r)
        aa,bb,gg = np.array(aa),np.array(bb),np.array(gg)
        rhs = np.zeros(len(ids))
        for name,current in injections.items(): rhs[ids[self.terms[name]]] += current

        def multiply(x):
            return diagonal*x - np.bincount(aa,gg*x[bb],minlength=len(x)) - np.bincount(bb,gg*x[aa],minlength=len(x))

        x = np.zeros(len(ids))
        residual = rhs.copy()
        direction = residual/diagonal
        old = float(residual @ direction)
        for iteration in range(20000):
            result = multiply(direction)
            alpha = old/float(direction @ result)
            x += alpha*direction
            residual -= alpha*result
            if np.linalg.norm(residual) < 1e-10:
                break
            z = residual/diagonal
            new = float(residual @ z)
            direction = z+(new/old)*direction
            old = new
        else:
            raise ValueError('DC solver failed to converge')
        return {name:0 if n==ref else float(x[ids[n]]) for name,n in self.terms.items()}

    def filled_star_audit(self, board):
        """Native filled copper cannot reconnect the branches outside J5.2."""
        star = self.terms['J5.2']
        components = {}
        for node in self.adj:
            if node==star or node in components:
                continue
            todo = [node]
            while todo:
                n = todo.pop()
                if n==star or n in components:
                    continue
                components[n] = node
                todo.extend(m for m,r in self.adj[n])
        power = {'C1','C2','C3','C11','C12','C15','R2','U2','U4','J3'}
        labels = defaultdict(set)
        terminals = defaultdict(list)
        for name,n in self.terms.items():
            if n==star:
                continue
            comp = components[n]
            labels[comp].add('power' if name.split('.')[0] in power else 'signal')
            terminals[comp].append(name)
        failures = [f'mixed branch component {terminals[c]}' for c,ls in labels.items() if len(ls)>1]
        points = np.array([(p[1],p[2]) for p in self.coords])
        fills = []
        for zone in kids(board,'zone'):
            net = kid(zone,'net_name') or kid(zone,'net')
            if net[1]!='/GND':
                continue
            polygons = kids(zone,'filled_polygon')
            if not polygons:
                failures.append('GND local zone has no actual native filled polygons')
            for filled in polygons:
                layer = LAYERS.index(kid(filled,'layer')[1])
                pts = [[float(p[1]),float(p[2])] for p in kids(kid(filled,'pts'),'xy')]
                on_layer = np.array([p[0]==layer for p in self.coords])
                # Conservative contact search uses the largest actual track
                # half-width; pads and via annuli are audited separately below.
                radius=max(t['width']/2 for t in self.proposal['tracks'] if t['net']=='/GND')
                hit = np.flatnonzero(on_layer & (poly_dist(points[:,0],points[:,1],pts)<=radius+1e-6))
                comps = {components[self.roots[i]] for i in hit if self.roots[i]!=star}
                pad_hits,via_hits = [],[]
                for pad in self.geometry['pads']:
                    if pad['net']!='/GND': continue
                    name=pad['ref']+'.'+pad['pad']
                    if any(polygon_contact(poly,pts) for poly in pad['polys'].get(LAYERS[layer],[])):
                        pad_hits.append(name)
                        if self.terms[name]!=star: comps.add(components[self.terms[name]])
                for via in self.proposal['vias']:
                    if via['net']!='/GND': continue
                    x,y=via['at']
                    if poly_dist(np.array([x]),np.array([y]),pts)[0] <= via['size']/2+1e-6:
                        via_hits.append(via['at'])
                        roots={self.roots[i] for i,p in enumerate(self.coords) if p[0]==layer and math.dist((x,y),p[1:])<1e-4}
                        comps |= {components[r] for r in roots if r!=star}
                joined = set().union(*(labels[c] for c in comps)) if comps else set()
                fills.append({'layer':LAYERS[layer],'contact_nodes':len(hit),'pad_contacts':pad_hits,
                              'via_contacts':via_hits,'branch_classes':sorted(joined)})
                if joined!={'power'}:
                    failures.append(f'local fill has unexpected branch contacts {sorted(joined)}')
        return {'scope':'actual native filled polygons + conservative track half-width; connector pad removed as star',
                'filled_polygons':fills,'failures':failures}


def verify_board_route(board, proposal):
    """Fail on a stale proposal even if its authored hash report looks current."""
    from collections import Counter
    def nm(value): return round(float(value)*1e6)
    # pcbnew.FromMM uses integer truncation of the binary float product;
    # decimal text in a saved board already represents integer nanometres.
    def proposal_nm(value): return int(float(value)*1e6)
    actual = []
    for track in kids(board,'segment'):
        a = tuple(nm(v) for v in kid(track,'start')[1:])
        b = tuple(nm(v) for v in kid(track,'end')[1:])
        actual.append((kid(track,'net')[1],kid(track,'layer')[1],*min(a,b),*max(a,b),nm(kid(track,'width')[1])))
    expected = []
    for track in proposal['tracks']:
        a,b = [tuple(proposal_nm(v) for v in track[k]) for k in ('start','end')]
        expected.append((track['net'],track['layer'],*min(a,b),*max(a,b),proposal_nm(track['width'])))
    if Counter(actual)!=Counter(expected): raise ValueError('PCB tracks do not match reviewed routing proposal')
    actual = [(kid(v,'net')[1],*(nm(x) for x in kid(v,'at')[1:]),nm(kid(v,'size')[1]),nm(kid(v,'drill')[1])) for v in kids(board,'via')]
    expected = [(v['net'],*(proposal_nm(x) for x in v['at']),proposal_nm(v['size']),proposal_nm(v['drill'])) for v in proposal['vias']]
    if Counter(actual)!=Counter(expected): raise ValueError('PCB vias do not match reviewed routing proposal')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--geometry',type=Path,required=True)
    parser.add_argument('--routes',type=Path,required=True)
    parser.add_argument('--board',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args()
    geometry,proposal = [json.loads(p.read_text()) for p in (args.geometry,args.routes)]
    board = parse_sexp(args.board.read_text())
    verify_board_route(board,proposal)
    graph = Graph(geometry,proposal)
    led = 22980/(68*.99)**.94/1000
    scenarios = {'led_only':{'J3.1':led},'led_logic_analog':{'J3.1':led,'U1.4':.020,'U7.2':.001}}
    pairs = [('C1.2','U2.4'),('C2.2','U2.4'),('J3.1','J5.2'),('U7.2','U1.4'),('U7.2','C17.2'),('U1.4','C8.2')]
    out = {'scope':'digital DC screen; not hardware/AC/thermal qualification',
           'inputs':{name+'_sha256':hashlib.sha256(p.read_bytes()).hexdigest()
                     for name,p in [('geometry',args.geometry),('routes',args.routes),('board',args.board)]},
           'model':{'copper_resistivity_ohm_mm':RHO,'temperature_C':20,'centerline_subdivision_mm':.05,
                    'copper_mm':dict(zip(LAYERS,THICKNESS)),'via_barrel_mm':.018,
                    'limits':['Via plating18um is an explicit nominal assumption, not guaranteed minimum.',
                              'Pad copper ideal internally in graph; finite connector pad bound reported separately.',
                              'Zone parallel conductivity omitted conservatively; centerline intersections only.',
                              'No bond, enclosure, temperature coefficient, inductance, capacitance, connector contact or harness model.']},
           'shortest_path_ohm':{a+' -> '+b:graph.shortest(a,b) for a,b in pairs},
           'scenarios':{name:{'injections_A':currents,'pad_voltage_V':graph.solve(currents)} for name,currents in scenarios.items()}}
    # Nominal finite connector pad screen: two outer faces, two annular routes
    # in parallel per face, plus .5mm barrel. Dimensions from actual J5.2.
    pad = next(p for p in geometry['pads'] if p['ref']=='J5' and p['pad']=='2')
    poly = pad['polys']['F.Cu'][0]
    width = max(p[0] for p in poly)-min(p[0] for p in poly)
    length = max(p[1] for p in poly)-min(p[1] for p in poly)
    drill = max(pad['drill']['size'])
    annulus = (width-drill)/2
    pad_r = 2*(RHO*length/(annulus*.035)/2)+RHO*.8/(math.pi*drill*.018)
    gain = 100/1064
    out['finite_star_pad_nominal_bound'] = {'width_mm':width,'length_mm':length,'hole_mm':drill,
        'assumed_full_annulus_width_mm':annulus,'resistance_ohm':pad_r,
        'LED_common_drop_V':led*pad_r,'ADC_input_reference_error_V':led*pad_r*gain,
        'note':'Conservative whole-pad travel at nominal geometry. Etch/drill/registration corner and contact/harness resistance remain manufacturing/physical review; not a certified worst-case.'}
    out['current_screen'] = {'led_bound_A':led,'source':'TI TPS2552 IOSmax formula;68k1% lowest resistor; retained component evidence',
        'outer_0_3mm_35um_capacity_at_10C_model_A':.048*10**.44*(.3*.035/.0254**2)**.725,
        'source_url':'https://jlcpcb.com/blog/pcb-trace-width-guide',
        'note':'Legacy empirical sizing screen only. Does not predict actual temperature or qualify the enclosed assembly.'}
    power_pairs = [('/+12V_PROT','C1.1','U2.3'),('/BUCK_SW','U2.5','L1.1'),
                   ('/+5V','L1.2','C2.1'),('/+5V','C2.1','U4.1'),('/VLED','U4.6','J3.2')]
    power_paths = {a+' -> '+b:Graph(geometry,proposal,net).shortest(a,b) for net,a,b in power_pairs}
    out['power_path_ohm'] = power_paths
    supply_drop = power_paths['C2.1 -> U4.1']*(led+.05)+power_paths['U4.6 -> J3.2']*led
    return_drop = graph.shortest('J3.1','J5.2')*led
    out['power_DC_screen'] = {'LED_supply_trace_drop_V':supply_drop,'LED_return_trace_drop_V':return_drop,
        'sum_V':supply_drop+return_drop,'extra_5V_logic_current_assumption_A':.05,
        'buck_input_local_loop_R_ohm':power_paths['C1.1 -> U2.3']+graph.shortest('C1.2','U2.4'),
        'buck_switch_net_vias':sum(v['net']=='/BUCK_SW' for v in proposal['vias']),
        'note':'Nominal centerline screen; excludes pad spreading, device Ron, contacts, harness and transient inductance. BUCK_SW via-free and local C1 loop are independently visible on native copper.'}
    led_v = out['scenarios']['led_only']['pad_voltage_V']
    adc_error = abs(led_v['U7.2']-led_v['U1.4'])+abs(led_v['R25.2']-led_v['U1.4'])+led*pad_r*gain
    out['incremental_LED_DC_budget'] = {'ADC_LSB_V':3.3/4095,'allocation_LSB':.5,
        'bound_V':adc_error,'pass':adc_error <= .5*3.3/4095,
        'rationale':'Allocate less than half one12-bitADCcode to incremental LED DC ground coupling, preserving VADC=(100/133)*(VDD/2+CV/8). Not total analogue accuracy.'}
    out['filled_star_audit'] = graph.filled_star_audit(board)
    combined_v = out['scenarios']['led_logic_analog']['pad_voltage_V']
    combined_error = abs(combined_v['U7.2']-combined_v['U1.4'])+abs(combined_v['R25.2']-combined_v['U1.4'])+led*pad_r*gain
    out['combined_DC_budget'] = {'bound_V':combined_error,'allocation_LSB':1,
        'pass':combined_error<=3.3/4095,
        'rationale':'One ADCcode total DC allocation for stated LED+20mA MCU+1mA analog scenario including finite nominal connector pad. Capacitive switching/EMI and manufacturing corners remain separate.'}
    args.out.write_text(json.dumps(out,indent=1)+'\n')
    print(json.dumps({'paths':out['shortest_path_ohm'],'budget':out['incremental_LED_DC_budget']},indent=1))
    return bool(not out['incremental_LED_DC_budget']['pass'] or not out['combined_DC_budget']['pass'] or out['filled_star_audit']['failures'])


if __name__=='__main__':
    raise SystemExit(main())
