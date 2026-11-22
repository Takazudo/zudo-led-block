#!/usr/bin/env python3
"""Reproducible DC return-path, power and coupling screen of the actual routed A7 controller.

A resistor-network and plan-view geometry estimate from the routed proposal that the board carries
(checked here at 1 nm) and the pad copper read back from pcbnew. It is not an AC, thermal or hardware
qualification. Native DRC/parity and the board/proposal identity stay independent prerequisites.

Acceptance (see ACCEPTANCE below for the sources): the LED-current-dependent shift of the CV/ADC
reference must stay within half a 12-bit ADC code, and the total DC reference shift within one code,
at the hot/thin-copper corner, not only at nominal 20 C.

Usage: python3 scripts/a7_return_review.py --geometry G --routes R --board B --out O
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

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from a7_route import poly_dist, seg_dist, GND_POWER_REFS, STAR_LAYER, SEPARATE, KELVIN
from a7_jlc_package import parse_sexp, kid, kids

ROOT = Path(__file__).resolve().parents[1]
STACK = json.loads((ROOT / 'engineering/a7/verification/fab/optical-fr4.json').read_text())['controller']['stackup']
LAYERS = [r['layer'] for r in STACK if r['kind'] == 'copper']
THICKNESS = [r['thickness_mm'] for r in STACK if r['kind'] == 'copper']
# centre-to-centre copper spacing along a barrel: dielectric plus half of each adjacent foil
SPANS = []
for _i, _row in enumerate(STACK):
    if _row['kind'] != 'copper':
        SPANS.append(_row['thickness_mm'] + (STACK[_i - 1]['thickness_mm'] + STACK[_i + 1]['thickness_mm']) / 2)
RHO = 1.724e-5      # ohm mm, annealed copper at 20 C (IACS)
ALPHA = 0.00393     # 1/K, copper temperature coefficient of resistance at 20 C (IACS)
PLATING = 0.018     # mm, barrel plating, explicit nominal assumption
STAR = 'J5.2'

# Corners of the resistance model. Voltages scale with every resistance, so the hot/thin corner is the
# acceptance case. The tolerances are explicit ASSUMED bounds (no fabricator tolerance row is retained in
# fab/jlcpcb_capabilities.json); 85 C is the upper ambient rating of the fitted -40..85 C parts.
CORNERS = {
    'nominal_20C': {'temp_C': 20, 'copper_scale': 1.0, 'width_scale': 1.0, 'plating_scale': 1.0},
    'hot_85C': {'temp_C': 85, 'copper_scale': 1.0, 'width_scale': 1.0, 'plating_scale': 1.0},
    'thin_copper_20C': {'temp_C': 20, 'copper_scale': 0.8, 'width_scale': 0.8, 'plating_scale': 0.8},
    'hot_85C_thin_copper': {'temp_C': 85, 'copper_scale': 0.8, 'width_scale': 0.8, 'plating_scale': 0.8},
}
ACCEPTANCE_CORNER = 'hot_85C_thin_copper'
ADC_LSB = 3.3 / 4095
GAIN = 100 / 133                 # VADC = GAIN * (VDD/2 + CV/8)
CV_PER_ADC_V = 8 / GAIN          # firmware inverse: CV = 10.64 * VADC - 4 * VDD
ACCEPTANCE = {
    'led_incremental_LSB': 0.5,
    'combined_LSB': 1.0,
    'corner': ACCEPTANCE_CORNER,
    'derivation': [
        'Transfer VADC=(100/133)*(VDD/2+CV/8) and inverse CV=10.64*VADC-4*VDD: '
        'engineering/a5/electronics/reports/electrical_margins.json cv_transfer (kept unchanged).',
        'One 12-bit code at 3.3 V is 0.806 mV at the ADC pin, 8.57 mV of CV.',
        'Firmware CV deadband is +/-50 mV and full scale +/-5 V (engineering/a5/firmware/README.md mode table, '
        'LB_CV_DEADBAND_MV in src/light_block.c). Half a code (4.3 mV CV) is under 9 % of the deadband, so an '
        'LED-brightness-dependent reference shift of that size cannot move a 0 V input out of the deadband or '
        'feed back visibly; one code total (8.6 mV CV) is 17 %.',
        'A static offset is removable by the firmware zero calibration (lb_calibration_t); the LED-dependent '
        'part is not, hence the tighter half-code allocation for it.',
        'The same allocations were already the screen of this script; this revision requires them at the '
        'hot/thin-copper corner instead of nominal 20 C (the earlier Route2 candidate failed that).',
    ],
    'excluded': 'Power-cable and connector contact resistance, op-amp offset, ADC/reference error, resistor '
                'tolerance, AC noise. Those are the same for any layout and belong to bench work (#10).',
}
# Weights of a ground-reference shift e_x (V, relative to the J5.2 pin) in the firmware CV estimate, from the
# kept schematic: CV_SENSE=(CV+e_R2)/2, CV_AFFINE=(CV_SENSE+2*V3V3+e_R6)/4, VADC=GAIN*CV_AFFINE+(1-GAIN)*e_R25,
# both ADC readings are taken against U1.4, and the LDO reference cancels ratiometrically.
# These four sum to -1, not 0: the patched source is taken to hold CV against the J5.2 pin (the model
# reference), so its own return shift is not credited. Crediting the CV IN sleeve, weight CV_SLEEVE_WEIGHT,
# completes the set to zero -- a shift common to the whole board and to the external source is no error.
CV_WEIGHTS = {'R2.2': 1.0, 'R6.2': 2.0, 'R25.2': CV_PER_ADC_V * (1 - GAIN), 'U1.4': -(CV_PER_ADC_V - 4)}
CV_SLEEVE_WEIGHT = 1.0

# Patched ground loop. A patched CV cable joins the board ground to the source ground at the CV IN sleeve, in
# parallel with the power-cable ground, so a share of the J5.2 current returns through J1.1 and the sleeve spur.
# The source then holds CV against the sleeve, not against the J5.2 pin. Only the PJ-324M contact maximum is a
# retained fact; every other resistance is an ASSUMED range (nothing in the repository measures it), so the
# derived fraction is ASSUMED and the result is also reported as a function of the fraction.
PATCH_LOOP = {
    'sleeve': 'J1.1',
    'thru_sleeve': 'J2.1',
    'power_return_ohm': {
        'power cable ground conductor': {'min': 0.011, 'max': 0.013, 'basis': 'ASSUMED 28 AWG, 0.213 ohm/m, 50-60 mm '
                                         '(A7 length is 57 mm with an assumed tolerance; the finished cable is not selected)'},
        'two 1.25 mm header contacts': {'min': 0.010, 'max': 0.040, 'basis': 'ASSUMED 5-20 mohm each; no contact resistance '
                                        'is retained for Molex 530470310 or the cable housing'},
        'adapter copper, 2x5 header and rack bus cable': {'min': 0.005, 'max': 0.030, 'basis': 'ASSUMED'},
    },
    'sleeve_return_ohm': {
        'CV IN sleeve contact': {'min': 0.005, 'max': 0.050, 'basis': 'maximum is fact-a7-pj-324m-contact-resistance '
                                 '(50 mohm initial, grade unidentified); minimum ASSUMED'},
        'patch cable shield': {'min': 0.030, 'max': 0.200, 'basis': 'ASSUMED'},
        'far-end jack sleeve contact': {'min': 0.005, 'max': 0.050, 'basis': 'ASSUMED'},
        'source module return to the rack ground': {'min': 0.020, 'max': 0.080, 'basis': 'ASSUMED'},
    },
    'fractions': [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.75, 1.0],
}


def polygon_contact(a, b):
    """Containment or edge intersection, including touching boundaries."""
    for p, q in ((a, b), (b, a)):
        pts = np.asarray(p)
        if np.any(poly_dist(pts[:, 0], pts[:, 1], q) <= 1e-8):
            return True

    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    for i, u in enumerate(a):
        v = a[(i + 1) % len(a)]
        for j, x in enumerate(b):
            y = b[(j + 1) % len(b)]
            if max(min(u[0], v[0]), min(x[0], y[0])) > min(max(u[0], v[0]), max(x[0], y[0])) + 1e-8:
                continue
            if max(min(u[1], v[1]), min(x[1], y[1])) > min(max(u[1], v[1]), max(x[1], y[1])) + 1e-8:
                continue
            if cross(u, v, x) * cross(u, v, y) <= 1e-16 and cross(x, y, u) * cross(x, y, v) <= 1e-16:
                return True
    return False


class Graph:
    """Centre-line resistor network of one net.

    SMD pad copper is one ideal node. A plated through-hole pad is one node per copper layer joined by its
    barrel plating, so current entering on one face does not vanish into an ideal pad: `name` is its F.Cu
    node and `name@Layer` each layer's node.
    """

    def __init__(self, geometry, proposal, net='/GND', corner=None):
        self.geometry, self.proposal, self.net = geometry, proposal, net
        c = corner or CORNERS['nominal_20C']
        rho = RHO * (1 + ALPHA * (c['temp_C'] - 20))
        nodes, coords, edges = {}, [], []

        def node(layer, x, y):
            key = (layer, round(x * 20000), round(y * 20000))
            if key not in nodes:
                nodes[key] = len(coords)
                coords.append((layer, x, y))
            return nodes[key]

        for t in proposal['tracks']:
            if t['net'] != net:
                continue
            a, b = t['start'], t['end']
            layer = LAYERS.index(t['layer'])
            count = max(1, round(max(abs(a[0] - b[0]), abs(a[1] - b[1])) / .05))
            previous = node(layer, *a)
            for i in range(1, count + 1):
                xy = [a[q] + (b[q] - a[q]) * i / count for q in range(2)]
                current = node(layer, *xy)
                r = rho * math.dist(a, b) / count / (t['width'] * c['width_scale'] * THICKNESS[layer] * c['copper_scale'])
                edges.append((previous, current, r, math.dist(a, b) / count))
                previous = current
        for via in proposal['vias']:
            if via['net'] != net:
                continue
            for layer, distance in enumerate(SPANS):
                edges.append((node(layer, *via['at']), node(layer + 1, *via['at']),
                              rho * distance / (math.pi * via['drill'] * PLATING * c['plating_scale']), distance))
        tht = {}
        for pad in geometry['pads']:
            if pad['net'] == net and pad.get('drill') and all(l in pad['polys'] for l in LAYERS):
                name = pad['ref'] + '.' + pad['pad']
                lo, hi = sorted(pad['drill']['size'])
                perimeter = math.pi * lo + 2 * (hi - lo)
                x, y = pad['drill']['at']
                # a private node per layer: never shared with a track centre line by accident
                ids = []
                for layer in range(len(LAYERS)):
                    nodes[('tht', name, layer)] = len(coords)
                    coords.append((layer, x, y))
                    ids.append(nodes[('tht', name, layer)])
                for layer, distance in enumerate(SPANS):
                    edges.append((ids[layer], ids[layer + 1],
                                  rho * distance / (perimeter * PLATING * c['plating_scale']), distance))
                tht[name] = ids
        parent = list(range(len(coords)))

        def root(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        points = np.array([(p[1], p[2]) for p in coords]) if coords else np.zeros((0, 2))
        layer_of = np.array([p[0] for p in coords])
        # A track may end anywhere on a via's annulus, not only on its centre: the annulus is one node.
        for via in proposal['vias']:
            if via['net'] != net:
                continue
            x, y = via['at']
            close = np.hypot(points[:, 0] - x, points[:, 1] - y) <= via['size'] / 2 + 1e-6
            for layer in range(len(LAYERS)):
                centre = node(layer, x, y)
                for n in np.flatnonzero(close & (layer_of == layer)).tolist():
                    parent[root(n)] = root(centre)
        terms = {}
        for pad in geometry['pads']:
            if pad['net'] != net:
                continue
            name = pad['ref'] + '.' + pad['pad']
            hits = []
            for layer, polygons in pad['polys'].items():
                index = LAYERS.index(layer)
                found = []
                for polygon in polygons:
                    found += np.flatnonzero((layer_of == index) & (poly_dist(points[:, 0], points[:, 1], polygon) < 1e-6)).tolist()
                if name in tht:
                    for n in found:
                        parent[root(n)] = root(tht[name][index])
                else:
                    hits += found
            if name in tht:
                terms[name] = tht[name][0]
                for index, layer in enumerate(LAYERS):
                    terms[name + '@' + layer] = tht[name][index]
                continue
            if not hits:
                raise ValueError(f'no centerline reaches {name}')
            for n in hits[1:]:
                parent[root(n)] = root(hits[0])
            terms[name] = hits[0]
        self.edges = [(root(a), root(b), r, d) for a, b, r, d in edges if root(a) != root(b)]
        self.terms = {k: root(v) for k, v in terms.items()}
        self.coords = coords
        self.roots = [root(n) for n in range(len(coords))]
        self.adj = defaultdict(list)
        for a, b, r, d in self.edges:
            self.adj[a].append((b, r, d))
            self.adj[b].append((a, r, d))

    def shortest(self, start, finish, weight='ohm'):
        """Least-resistance path; returns ohms, or (ohms, mm, layer changes) with weight='detail'."""
        start, finish = self.terms[start], self.terms[finish]
        heap, best = [(0, 0, 0, start)], {start: 0}
        while heap:
            d, length, hops, n = heapq.heappop(heap)
            if d != best[n]:
                continue
            if n == finish:
                return d if weight == 'ohm' else (d, length, hops)
            for m, r, mm in self.adj[n]:
                if d + r < best.get(m, math.inf):
                    best[m] = d + r
                    change = self.coords[m][0] != self.coords[n][0]
                    heapq.heappush(heap, (d + r, length + mm, hops + change, m))
        raise ValueError('disconnected resistor model')

    def solve(self, injections, reference=STAR):
        ref = self.terms[reference]
        ids = {n: i for i, n in enumerate(n for n in sorted(self.adj) if n != ref)}
        diagonal = np.zeros(len(ids))
        aa, bb, gg = [], [], []
        for a, b, r, _ in self.edges:
            if a != ref:
                diagonal[ids[a]] += 1 / r
            if b != ref:
                diagonal[ids[b]] += 1 / r
            if a != ref and b != ref:
                aa.append(ids[a]); bb.append(ids[b]); gg.append(1 / r)
        aa, bb, gg = np.array(aa, int), np.array(bb, int), np.array(gg, float)
        rhs = np.zeros(len(ids))
        for name, current in injections.items():
            if self.terms[name] != ref:
                rhs[ids[self.terms[name]]] += current

        def multiply(x):
            return diagonal * x - np.bincount(aa, gg * x[bb], minlength=len(x)) - np.bincount(bb, gg * x[aa], minlength=len(x))

        x = np.zeros(len(ids))
        residual = rhs.copy()
        if np.linalg.norm(residual) > 0:
            direction = residual / diagonal
            old = float(residual @ direction)
            for iteration in range(40000):
                result = multiply(direction)
                alpha = old / float(direction @ result)
                x += alpha * direction
                residual -= alpha * result
                if np.linalg.norm(residual) < 1e-12:
                    break
                z = residual / diagonal
                new = float(residual @ z)
                direction = z + (new / old) * direction
                old = new
            else:
                raise ValueError('DC solver failed to converge')
        return {name: 0 if n == ref else float(x[ids[n]]) for name, n in self.terms.items()}

    def star_nodes(self):
        return {self.terms[k] for k in self.terms if k == STAR or k.startswith(STAR + '@')}

    def branches(self):
        """Connected components of the net with every J5.2 node removed, labelled power / signal."""
        star = self.star_nodes()
        components = {}
        for start in self.adj:
            if start in star or start in components:
                continue
            todo = [start]
            while todo:
                n = todo.pop()
                if n in star or n in components:
                    continue
                components[n] = start
                todo.extend(m for m, _, _ in self.adj[n])
        labels, terminals = defaultdict(set), defaultdict(list)
        for name, n in self.terms.items():
            if n in star or '@' in name:
                continue
            comp = components.get(n)
            labels[comp].add('power' if name.split('.')[0] in GND_POWER_REFS else 'signal')
            terminals[comp].append(name)
        return components, labels, terminals

    def filled_star_audit(self, board):
        """Branches are separate outside the J5.2 pin, use their own pad face, and no native fill rejoins them."""
        star = self.star_nodes()
        components, labels, terminals = self.branches()
        failures = [f'mixed branch component {sorted(terminals[c])}' for c, ls in labels.items() if len(ls) > 1]
        faces = {}
        for index, layer in enumerate(LAYERS):
            key = STAR + '@' + layer
            if key not in self.terms:
                continue
            node = self.terms[key]
            attached = set()
            for m, _, _ in self.adj[node]:
                if m not in star:
                    attached |= labels[components[m]]
            faces[layer] = sorted(attached)
            expected = {STAR_LAYER[True]: {'power'}, STAR_LAYER[False]: {'signal'}}.get(layer, set())
            if attached != expected:
                failures.append(f'{STAR} {layer} carries {sorted(attached)}, expected {sorted(expected)}')
        points = np.array([(p[1], p[2]) for p in self.coords]) if self.coords else np.zeros((0, 2))
        fills = []
        for zone in kids(board, 'zone'):
            net = kid(zone, 'net_name') or kid(zone, 'net')
            if net[1] != self.net:
                continue
            polygons = kids(zone, 'filled_polygon')
            if not polygons:
                failures.append('GND local zone has no actual native filled polygons')
            for filled in polygons:
                layer = LAYERS.index(kid(filled, 'layer')[1])
                pts = [[float(p[1]), float(p[2])] for p in kids(kid(filled, 'pts'), 'xy')]
                on_layer = np.array([p[0] == layer for p in self.coords])
                # Conservative contact search uses the largest actual track
                # half-width; pads and via annuli are audited separately below.
                radius = max(t['width'] / 2 for t in self.proposal['tracks'] if t['net'] == self.net)
                hit = np.flatnonzero(on_layer & (poly_dist(points[:, 0], points[:, 1], pts) <= radius + 1e-6))
                comps = {components[self.roots[i]] for i in hit if self.roots[i] not in star}
                star_touch = any(self.roots[i] in star for i in hit)
                pad_hits, via_hits = [], []
                for pad in self.geometry['pads']:
                    if pad['net'] != self.net:
                        continue
                    name = pad['ref'] + '.' + pad['pad']
                    if any(polygon_contact(poly, pts) for poly in pad['polys'].get(LAYERS[layer], [])):
                        pad_hits.append(name)
                        if name == STAR:
                            star_touch = True
                        elif self.terms[name] not in star:
                            comps.add(components[self.terms[name]])
                for via in self.proposal['vias']:
                    if via['net'] != self.net:
                        continue
                    x, y = via['at']
                    if poly_dist(np.array([x]), np.array([y]), pts)[0] <= via['size'] / 2 + 1e-6:
                        via_hits.append(via['at'])
                        roots = {self.roots[i] for i, p in enumerate(self.coords) if p[0] == layer and math.dist((x, y), p[1:]) < 1e-4}
                        comps |= {components[r] for r in roots if r not in star}
                joined = set().union(*(labels[c] for c in comps)) if comps else set()
                fills.append({'layer': LAYERS[layer], 'contact_nodes': len(hit), 'pad_contacts': pad_hits,
                              'via_contacts': via_hits, 'branch_classes': sorted(joined), 'touches_star_pad': star_touch})
                if joined != {'power'} or star_touch:
                    failures.append(f'local fill has unexpected branch contacts {sorted(joined)}' +
                                    (' and touches the star pad' if star_touch else ''))
        return {'scope': 'actual native filled polygons + conservative track half-width; J5.2 removed as the star',
                'branch_terminals': {('+'.join(sorted(labels[c])) or 'none') + ':' + sorted(t)[0]: sorted(t)
                                     for c, t in terminals.items()},
                'star_pad_faces': faces, 'filled_polygons': fills, 'failures': failures}


def verify_board_route(board, proposal):
    """Fail on a stale proposal even if its authored hash report looks current."""
    from collections import Counter

    def nm(value):
        return round(float(value) * 1e6)

    # pcbnew.FromMM uses integer truncation of the binary float product;
    # decimal text in a saved board already represents integer nanometres.
    def proposal_nm(value):
        return int(float(value) * 1e6)
    actual = []
    for track in kids(board, 'segment'):
        a = tuple(nm(v) for v in kid(track, 'start')[1:])
        b = tuple(nm(v) for v in kid(track, 'end')[1:])
        actual.append((kid(track, 'net')[1], kid(track, 'layer')[1], *min(a, b), *max(a, b), nm(kid(track, 'width')[1])))
    expected = []
    for track in proposal['tracks']:
        a, b = [tuple(proposal_nm(v) for v in track[k]) for k in ('start', 'end')]
        expected.append((track['net'], track['layer'], *min(a, b), *max(a, b), proposal_nm(track['width'])))
    if Counter(actual) != Counter(expected):
        raise ValueError('PCB tracks do not match reviewed routing proposal')
    actual = [(kid(v, 'net')[1], *(nm(x) for x in kid(v, 'at')[1:]), nm(kid(v, 'size')[1]), nm(kid(v, 'drill')[1])) for v in kids(board, 'via')]
    expected = [(v['net'], *(proposal_nm(x) for x in v['at']), proposal_nm(v['size']), proposal_nm(v['drill'])) for v in proposal['vias']]
    if Counter(actual) != Counter(expected):
        raise ValueError('PCB vias do not match reviewed routing proposal')


def led_bound_A():
    """TPS2552-1 maximum current limit with the 68k 1 % resistor at its low corner (A5 electrical_margins.json)."""
    return 22980 / (68 * .99) ** .94 / 1000


def reference_errors(graph, injections):
    """ADC-pin reference error (V) for one current scenario, worst over where the pin is actually bonded."""
    worst = {'screen_V': 0.0, 'weighted_V': 0.0}
    cases = {}
    for face in (STAR_LAYER[False], STAR_LAYER[True]):
        v = graph.solve(injections, reference=STAR + '@' + face)
        screen = abs(v['U7.2'] - v['U1.4']) + abs(v['R25.2'] - v['U1.4'])
        weighted = abs(sum(w * v[k] for k, w in CV_WEIGHTS.items())) / CV_PER_ADC_V
        cases['pin_bonded_at_' + face] = {'screen_V': screen, 'weighted_V': weighted,
                                          'node_V': {k: v[k] for k in ('U1.4', 'U7.2', 'R25.2', 'R6.2', 'R2.2', 'C13.2', 'J3.1', 'U2.4', 'J1.1')
                                                     if k in v}}
        worst = {k: max(worst[k], cases['pin_bonded_at_' + face][k]) for k in worst}
    return worst, cases


def patched_fraction_bounds(spur_ohm):
    """Share of the J5.2 current taken by the sleeve: two parallel returns to one rack ground (current divider)."""
    ra = {k: sum(r[k] for r in PATCH_LOOP['power_return_ohm'].values()) for k in ('min', 'max')}
    rb = {k: spur_ohm + sum(r[k] for r in PATCH_LOOP['sleeve_return_ohm'].values()) for k in ('min', 'max')}
    return {'power_return_ohm': ra, 'sleeve_return_ohm_with_spur': rb,
            'min': ra['min'] / (ra['min'] + rb['max']), 'max': ra['max'] / (ra['max'] + rb['min'])}


def patched_loop_error(graph, injections, sleeve_A):
    """ADC-pin error (V) with sleeve_A leaving through the CV IN sleeve and the source referenced to that sleeve."""
    sleeve = PATCH_LOOP['sleeve']
    currents = dict(injections)
    currents[sleeve] = currents.get(sleeve, 0.0) - sleeve_A
    worst = 0.0
    for face in (STAR_LAYER[False], STAR_LAYER[True]):
        v = graph.solve(currents, reference=STAR + '@' + face)
        worst = max(worst, abs(sum(w * v[k] for k, w in CV_WEIGHTS.items()) + CV_SLEEVE_WEIGHT * v[sleeve]))
    return worst / CV_PER_ADC_V


def patched_ground_loop(geometry, proposal, injections, total_A, shared_pin_V):
    """LED-dependent error of the patched ground loop per corner, per fraction, and at the derived fraction bound."""
    sleeve, thru = PATCH_LOOP['sleeve'], PATCH_LOOP['thru_sleeve']
    rows = {}
    for cname, corner in CORNERS.items():
        g = Graph(geometry, proposal, corner=corner)
        spur = max(g.shortest(sleeve, STAR + '@' + face) for face in (STAR_LAYER[False], STAR_LAYER[True]))
        v = g.solve({thru: 1.0}, reference=STAR + '@' + STAR_LAYER[False])
        bounds = patched_fraction_bounds(spur)
        external = sum(PATCH_LOOP['sleeve_return_ohm'][k]['min'] for k in
                       ('CV IN sleeve contact', 'patch cable shield', 'far-end jack sleeve contact'))

        def lsb(fraction):
            return (patched_loop_error(g, injections, fraction * total_A) + shared_pin_V[cname]) / ADC_LSB
        slope = lsb(1.0) - lsb(0.0)
        rows[cname] = {
            'sleeve_to_star_ohm': spur,
            'thru_sleeve_to_star_ohm': g.shortest(thru, STAR + '@' + STAR_LAYER[False]),
            'thru_to_cv_in_sleeve_transfer_ohm': v[sleeve],
            'LSB_by_fraction': {f'{f:g}': lsb(f) for f in PATCH_LOOP['fractions']},
            'LSB_per_unit_fraction': slope,
            'LSB_per_A_of_sleeve_current': slope / total_A,
            'fraction_at_allocation': ((ACCEPTANCE['led_incremental_LSB'] - lsb(0.0)) / slope) if slope > 0 else None,
            'fraction_bounds_ASSUMED': bounds,
            'LSB_at_fraction_bound': lsb(bounds['max']),
            'external_share_LSB_at_fraction_bound_not_in_allocation':
                bounds['max'] * total_A * external / CV_PER_ADC_V / ADC_LSB}
    return rows


def star_pin_bound(geometry, corner):
    """Whole J5.2 barrel plating taken as shared by the LED return and the CV reference (conservative)."""
    pad = next(p for p in geometry['pads'] if p['ref'] + '.' + p['pad'] == STAR)
    lo, hi = sorted(pad['drill']['size'])
    rho = RHO * (1 + ALPHA * (corner['temp_C'] - 20))
    r = rho * sum(SPANS) / ((math.pi * lo + 2 * (hi - lo)) * PLATING * corner['plating_scale'])
    return r


def supply_reference_error(geometry, proposal, corner):
    """+3V3 drop between the affine divider taps (R4.1, R5.1) and the measured VDDA (U1.3), as ADC volts.

    CV_est = 8*CV_AFFINE - 4*VDD with CV_AFFINE = (CV_SENSE + V(R4.1) + V(R5.1) + e_R6)/4, so a drop d_x below the
    regulator output enters as -2*(d_R4 + d_R5) + 4*d_U1 volts of CV. Load currents are ASSUMED upper bounds.
    """
    g = Graph(geometry, proposal, '/+3V3', corner)
    loads = {'U1.3': -.020, 'U7.5': -.001, 'R8.1': -.0033, 'U5.1': -.001}
    v = g.solve(loads, reference='U3.5')
    d = {k: -v[k] for k in ('U1.3', 'R4.1', 'R5.1', 'C8.1')}
    cv = -2 * (d['R4.1'] + d['R5.1']) + 4 * d['U1.3']
    return abs(cv) / CV_PER_ADC_V, {'loads_A': loads, 'drop_below_U3.5_V': d, 'CV_error_V': cv}


def kelvin_audit(geometry, proposal):
    """Each reference tap reaches the rest of its net only through its source pad."""
    out, failures = {}, []
    for net, spec in KELVIN.items():
        g = Graph(geometry, proposal, net)
        source = g.terms[spec['source']]
        seen, todo = set(), [g.terms[spec['pads'][0]]]
        while todo:
            n = todo.pop()
            if n in seen or n == source:
                continue
            seen.add(n)
            todo.extend(m for m, _, _ in g.adj[n])
        island = sorted(k for k, n in g.terms.items() if n in seen)
        reached = any(source == m for n in seen for m, _, _ in g.adj[n])
        out[net] = {'source': spec['source'], 'taps': spec['pads'], 'pads_on_the_tap_side_of_the_source': island}
        if island != sorted(spec['pads']) or not reached:
            failures.append(f'{net}: reference taps {spec["pads"]} are not a separate branch from {spec["source"]}: {island}')
    return {'nets': out, 'failures': failures}


def coupling_capacitance_fF(geometry, proposal, victim, aggressor, reach=5.0):
    """Unshielded two-wire estimate of the capacitance between the tracks of `victim` and the copper of `aggressor`.

    Each 0.05 mm of victim track contributes pi*eps/acosh(D/2a) with D the centre distance to the nearest
    aggressor copper on any layer, while that copper is within `reach` mm. No plane and no intervening conductor
    is credited, so this is an upper-side estimate for comparing candidates, not a field solution.
    """
    eps = 8.854e-15 * (1 + 4.4) / 2          # F/mm, half FR-4 half air
    agg = copper_items(geometry, proposal, aggressor)
    total, length = 0.0, 0.0
    for t in proposal['tracks']:
        if t['net'] != victim:
            continue
        (x1, y1), (x2, y2) = t['start'], t['end']
        n = max(1, int(math.ceil(math.dist((x1, y1), (x2, y2)) / .05)))
        step = math.dist((x1, y1), (x2, y2)) / n
        pts = np.array([[x1 + (x2 - x1) * (i + .5) / n, y1 + (y2 - y1) * (i + .5) / n] for i in range(n)])
        nearest = np.full(len(pts), math.inf)
        for kind, layer, geo, half in agg:
            if kind == 'pad':
                d = poly_dist(pts[:, 0], pts[:, 1], geo)
            else:
                (u1, v1), (u2, v2) = geo
                d = seg_dist(pts[:, 0], pts[:, 1], u1, v1, u2, v2)
            nearest = np.minimum(nearest, d)
        radius = (t['width'] + .035) / 4
        near = nearest[nearest < reach]
        total += float(np.sum(math.pi * eps * step / np.arccosh(np.maximum(near, 2.02 * radius) / (2 * radius))))
        length += step * len(near)
    return round(total * 1e15, 1), round(length, 2)


def copper_items(geometry, proposal, net):
    """Plan-view copper of one net: (kind, layer or None, geometry, half width)."""
    items = []
    for t in proposal['tracks']:
        if t['net'] == net:
            items.append(('track', t['layer'], (t['start'], t['end']), t['width'] / 2))
    for v in proposal['vias']:
        if v['net'] == net:
            items.append(('via', None, (v['at'], v['at']), v['size'] / 2))
    for p in geometry['pads']:
        if p['net'] == net:
            for layer, polys in p['polys'].items():
                for poly in polys:
                    items.append(('pad', layer, poly, 0.0))
    return items


def separation(geometry, proposal, a, b, near=0.5):
    """Smallest plan-view copper gap between two nets on any layer pair and on one layer, and the track length of
    `a` that runs within `near` mm of `b` (all layers: nothing shields one layer from another any more)."""
    ia, ib = copper_items(geometry, proposal, a), copper_items(geometry, proposal, b)
    best = {'any_layer_mm': math.inf, 'same_layer_mm': math.inf}
    coupled = 0.0
    for kind, layer, geo, half in ia:
        if kind == 'pad':
            pts = np.asarray(geo, float)
            step = None
        else:
            (x1, y1), (x2, y2) = geo
            n = max(1, int(math.ceil(math.dist((x1, y1), (x2, y2)) / .05)))
            pts = np.array([[x1 + (x2 - x1) * i / n, y1 + (y2 - y1) * i / n] for i in range(n + 1)])
            step = math.dist((x1, y1), (x2, y2)) / n
        nearest = np.full(len(pts), math.inf)
        for kind2, layer2, geo2, half2 in ib:
            if kind2 == 'pad':
                d = poly_dist(pts[:, 0], pts[:, 1], geo2) - half
            else:
                (u1, v1), (u2, v2) = geo2
                d = seg_dist(pts[:, 0], pts[:, 1], u1, v1, u2, v2) - half - half2
            d = np.maximum(d, 0)
            nearest = np.minimum(nearest, d)
            best['any_layer_mm'] = min(best['any_layer_mm'], float(d.min()))
            if layer is None or layer2 is None or layer == layer2:
                best['same_layer_mm'] = min(best['same_layer_mm'], float(d.min()))
        if kind == 'track' and len(ib):
            coupled += step * float(np.count_nonzero(nearest[:-1] < near))
    return {**{k: (None if math.isinf(v) else round(v, 4)) for k, v in best.items()},
            f'track_mm_of_first_within_{near}mm': round(coupled, 3)}


def trace_inductance_nH(length_mm, width_mm, thickness_mm=.035):
    """Partial self-inductance of a straight flat conductor (Rosa/Grover), nH."""
    if length_mm <= 0:
        return 0.0
    wt = width_mm + thickness_mm
    return 0.2 * length_mm * (math.log(2 * length_mm / wt) + .5 + .2235 * wt / length_mm)


def review(geometry, proposal, board):
    verify_board_route(board, proposal)
    led = led_bound_A()
    nominal = Graph(geometry, proposal)
    out = {'scope': 'digital DC/geometry screen of the routed board; not hardware, AC or thermal qualification',
           'acceptance': ACCEPTANCE,
           'model': {'copper_resistivity_ohm_mm_20C': RHO, 'temperature_coefficient_per_K': ALPHA,
                     'copper_mm': dict(zip(LAYERS, THICKNESS)), 'barrel_plating_mm': PLATING,
                     'barrel_spans_mm': SPANS, 'centerline_subdivision_mm': .05, 'corners': CORNERS,
                     'limits': ['Barrel plating 18 um and the corner tolerances are explicit assumptions, not guaranteed minima.',
                                'SMD pad copper is ideal; through-hole pads are one node per layer joined by barrel plating only '
                                '(solder and pin ignored).',
                                'Local zone conductivity omitted conservatively; centre-line intersections only.',
                                'No harness, connector contact, enclosure, inductance or capacitance in the DC network.']}}
    pairs = [('C1.2', 'U2.4'), ('C2.2', 'U2.4'), ('J3.1', STAR + '@' + STAR_LAYER[True]),
             ('U1.4', STAR + '@' + STAR_LAYER[False]), ('R25.2', 'U1.4'), ('R6.2', 'U1.4'), ('U7.2', 'U1.4'),
             ('R2.2', 'U1.4'), ('C8.2', 'U1.4'), ('C17.2', 'U7.2')]
    out['ground_paths'] = {a + ' -> ' + b: dict(zip(('ohm', 'mm', 'layer_changes'), nominal.shortest(a, b, 'detail')))
                           for a, b in pairs}
    out['filled_star_audit'] = nominal.filled_star_audit(board)

    # -- CV/ADC reference error
    buck_eff = 0.85
    input_current = led * 5 / (12 * buck_eff)
    scenarios = {
        'led_conservative': {'J3.1': led},
        'led_physical_dc': {'J3.1': led, 'U2.4': -(led - input_current)},
        'logic_analog': {'U1.4': .020, 'U7.2': .001, 'R25.2': .0018, 'R8.2': .0033},
    }
    scenario_notes = {
        'led_conservative': 'whole TPS2552 limit current from J3.1 to the J5.2 pin (kept from the earlier screen)',
        'led_physical_dc': f'LED current returns to the buck ground; only the 12 V input current '
                           f'{input_current:.3f} A (efficiency {buck_eff} ASSUMED) leaves through J5.2',
        'logic_analog': '20 mA MCU (ASSUMED upper bound), 1 mA U7, 1.8 mA R25 at +5 V CV, 3.3 mA R8 bleeder',
    }
    budget = {}
    for cname, corner in CORNERS.items():
        g = Graph(geometry, proposal, corner=corner)
        row = {}
        pin = star_pin_bound(geometry, corner)
        shared = led * pin / CV_PER_ADC_V
        for sname, currents in scenarios.items():
            worst, cases = reference_errors(g, currents)
            row[sname] = {'worst': worst, **({'cases': cases} if cname in ('nominal_20C', ACCEPTANCE_CORNER) else {})}
        led_error = max(row['led_conservative']['worst'].values()) + shared
        supply, detail = supply_reference_error(geometry, proposal, corner)
        row['supply_3V3_reference'] = {'ADC_V': supply, **(detail if cname in ('nominal_20C', ACCEPTANCE_CORNER) else {})}
        combined = led_error + max(row['logic_analog']['worst'].values()) + supply
        row['star_pin_barrel_ohm'] = pin
        row['star_pin_shared_bound_V'] = shared
        row['led_incremental'] = {'bound_V': led_error, 'LSB': led_error / ADC_LSB}
        row['combined'] = {'bound_V': combined, 'LSB': combined / ADC_LSB}
        budget[cname] = row
    out['reference_error'] = {
        'scenarios': scenario_notes,
        'metric': {'screen_V': '|U7.2-U1.4| + |R25.2-U1.4| (kept from the earlier screen)',
                   'weighted_V': 'firmware-weighted |sum(w*e)|/10.64 with CV weights ' + json.dumps(CV_WEIGHTS),
                   'star_pin_shared_bound_V': 'LED limit current times the whole J5.2 barrel plating, as a shift of the board '
                                              'reference against the CV source (weight 1/10.64)',
                   'supply_3V3_reference': '+3V3 drop between the affine divider taps and the measured VDDA, '
                                           '|-2*(d_R4.1+d_R5.1)+4*d_U1.3|/10.64',
                   'bound': 'max(screen, weighted) + star pin bound; combined adds max(screen, weighted) of logic_analog '
                            'and the +3V3 reference term'},
        'corners': budget}
    acc = budget[ACCEPTANCE_CORNER]
    nom = budget['nominal_20C']
    out['kelvin_audit'] = kelvin_audit(geometry, proposal)
    out['incremental_LED_DC_budget'] = {
        'ADC_LSB_V': ADC_LSB, 'allocation_LSB': ACCEPTANCE['led_incremental_LSB'], 'corner': ACCEPTANCE_CORNER,
        'bound_V': acc['led_incremental']['bound_V'], 'bound_LSB': acc['led_incremental']['LSB'],
        'nominal_bound_LSB': nom['led_incremental']['LSB'],
        'resistance_scale_margin': (ACCEPTANCE['led_incremental_LSB'] / nom['led_incremental']['LSB']
                                    if nom['led_incremental']['LSB'] else None),
        'pass': acc['led_incremental']['LSB'] <= ACCEPTANCE['led_incremental_LSB']}
    out['combined_DC_budget'] = {
        'allocation_LSB': ACCEPTANCE['combined_LSB'], 'corner': ACCEPTANCE_CORNER,
        'bound_V': acc['combined']['bound_V'], 'bound_LSB': acc['combined']['LSB'],
        'nominal_bound_LSB': nom['combined']['LSB'],
        'resistance_scale_margin': ACCEPTANCE['combined_LSB'] / nom['combined']['LSB'] if nom['combined']['LSB'] else None,
        'pass': acc['combined']['LSB'] <= ACCEPTANCE['combined_LSB']}

    patched = patched_ground_loop(geometry, proposal, scenarios['led_physical_dc'], input_current,
                                  {c: budget[c]['star_pin_shared_bound_V'] for c in CORNERS})
    out['patched_ground_loop'] = {
        'scenario': f'led_physical_dc with a fraction of the {input_current:.3f} A J5.2 current leaving through '
                    f"{PATCH_LOOP['sleeve']} instead; CV source referenced to that sleeve (weight {CV_SLEEVE_WEIGHT}); "
                    'the whole J5.2 barrel bound is kept on top',
        'loop_model': PATCH_LOOP, 'J5.2_current_A': input_current,
        'allocation_LSB': ACCEPTANCE['led_incremental_LSB'], 'corner': ACCEPTANCE_CORNER,
        'corners': patched,
        'bound_LSB': patched[ACCEPTANCE_CORNER]['LSB_at_fraction_bound'],
        'nominal_bound_LSB': patched['nominal_20C']['LSB_at_fraction_bound'],
        'fraction_bound_ASSUMED': patched[ACCEPTANCE_CORNER]['fraction_bounds_ASSUMED']['max'],
        'fraction_at_allocation': patched[ACCEPTANCE_CORNER]['fraction_at_allocation'],
        'pass': patched[ACCEPTANCE_CORNER]['LSB_at_fraction_bound'] <= ACCEPTANCE['led_incremental_LSB'],
        'note': 'Board copper only. The fraction is set by cable and contact resistances outside the board, all ASSUMED '
                'except the PJ-324M contact maximum; the pass is conditional on that range and NEEDS BENCH (#10). The '
                'patch-cable shield and contact drop of the same current is a larger, layout-independent CV error '
                '(external_share, sleeve contact + shield + far contact at their minima) and is outside the allocation. '
                'A current entering the THRU sleeve from a downstream module shifts the CV IN sleeve by the transfer '
                'resistance.'}

    # -- power paths, drops, loops
    hot = CORNERS[ACCEPTANCE_CORNER]
    graphs = {}

    def net_graph(net, corner=None):
        key = (net, json.dumps(corner, sort_keys=True))
        if key not in graphs:
            graphs[key] = Graph(geometry, proposal, net, corner)
        return graphs[key]

    def path(net, a, b):
        ohm, mm, hops = net_graph(net).shortest(a, b, 'detail')
        return {'net': net, 'ohm': ohm, 'ohm_' + ACCEPTANCE_CORNER: net_graph(net, hot).shortest(a, b),
                'mm': round(mm, 3), 'layer_changes': hops}
    power = {'+12V_RAW J5.1 -> D1.2': path('/+12V_RAW', 'J5.1', 'D1.2'),
             '+12V_PROT D1.1 -> C1.1': path('/+12V_PROT', 'D1.1', 'C1.1'),
             '+12V_PROT C1.1 -> U2.3': path('/+12V_PROT', 'C1.1', 'U2.3'),
             'BUCK_SW U2.5 -> L1.1': path('/BUCK_SW', 'U2.5', 'L1.1'),
             '+5V L1.2 -> C2.1': path('/+5V', 'L1.2', 'C2.1'),
             '+5V C2.1 -> U4.1': path('/+5V', 'C2.1', 'U4.1'),
             '+5V C2.1 -> U3.1': path('/+5V', 'C2.1', 'U3.1'),
             'VLED U4.6 -> J3.2': path('/VLED', 'U4.6', 'J3.2'),
             '+3V3 U3.5 -> U1.3': path('/+3V3', 'U3.5', 'U1.3'),
             'GND J3.1 -> C2.2': path('/GND', 'J3.1', 'C2.2'),
             'GND C2.2 -> U2.4': path('/GND', 'C2.2', 'U2.4'),
             'GND C1.2 -> J5.2': path('/GND', 'C1.2', STAR + '@' + STAR_LAYER[True]),
             'GND J3.1 -> J5.2': path('/GND', 'J3.1', STAR + '@' + STAR_LAYER[True])}
    out['power_paths'] = power
    key = 'ohm_' + ACCEPTANCE_CORNER
    supply = (power['+5V C2.1 -> U4.1'][key] * (led + .05) + power['VLED U4.6 -> J3.2'][key] * led)
    ret = power['GND J3.1 -> C2.2'][key] * led
    in_drop = (power['+12V_RAW J5.1 -> D1.2'][key] + power['+12V_PROT D1.1 -> C1.1'][key] + power['GND C1.2 -> J5.2'][key]) * input_current
    widths = sorted({t['width'] for t in proposal['tracks'] if t['net'] in ('/VLED', '/+5V', '/GND', '/BUCK_SW')})
    out['power_DC_screen'] = {
        'corner': ACCEPTANCE_CORNER, 'led_bound_A': led, 'buck_input_current_A': input_current,
        'LED_supply_trace_drop_V': supply, 'LED_return_trace_drop_V': ret, 'LED_loop_sum_V': supply + ret,
        'LED_loop_fraction_of_5V': (supply + ret) / 5,
        '12V_input_loop_trace_drop_V': in_drop,
        'power_ground_offset_at_J3_conservative_V': power['GND J3.1 -> J5.2'][key] * led,
        'buck_switch_net_vias': sum(v['net'] == '/BUCK_SW' for v in proposal['vias']),
        'high_current_track_widths_mm': widths,
        'inner_layer_high_current_track_mm': round(sum(math.dist(t['start'], t['end']) for t in proposal['tracks']
                                                       if t['net'] in ('/VLED', '/+5V', '/BUCK_SW') and t['layer'] not in (LAYERS[0], LAYERS[-1])), 3),
        'outer_0_3mm_35um_capacity_at_10C_rise_A': .048 * 10 ** .44 * (.3 * .035 / .0254 ** 2) ** .725,
        'capacity_source': 'IPC-2221 external-conductor chart equation as given at https://jlcpcb.com/blog/pcb-trace-width-guide; '
                           'a sizing screen only, it does not predict the temperature of the enclosed assembly',
        'note': 'Excludes pad spreading, device Ron, D1 forward drop, contacts and harness. LED loop drop is supply plus the '
                'return to the buck output capacitor, where the LED current actually closes.'}
    centre = {p['ref'] + '.' + p['pad']: p['at'] for p in geometry['pads'] if p['pad']}

    def loop(points, legs):
        xy = [centre[k] for k in points]
        area = abs(sum(a[0] * b[1] - a[1] * b[0] for a, b in zip(xy, xy[1:] + xy[:1]))) / 2
        rows = {name: path(net, a, b) for name, (net, a, b) in legs.items()}
        return {'pad_centres': points, 'pad_centre_polygon_area_mm2': round(area, 3), 'routed_legs': rows,
                'routed_leg_length_mm': round(sum(r['mm'] for r in rows.values()), 3),
                'layer_changes': sum(r['layer_changes'] for r in rows.values())}
    out['buck_loops'] = {
        'input_hot_loop': loop(['C1.1', 'U2.3', 'U2.4', 'C1.2'],
                               {'VIN': ('/+12V_PROT', 'C1.1', 'U2.3'), 'GND': ('/GND', 'U2.4', 'C1.2')}),
        'bootstrap': loop(['U2.6', 'C4.1', 'C4.2', 'U2.5'],
                          {'BST': ('/BUCK_BST', 'U2.6', 'C4.1'), 'SW': ('/BUCK_SW', 'C4.2', 'U2.5')}),
        'output_loop': loop(['U2.5', 'L1.1', 'L1.2', 'C2.1', 'C2.2', 'U2.4'],
                            {'SW': ('/BUCK_SW', 'U2.5', 'L1.1'), '5V': ('/+5V', 'L1.2', 'C2.1'), 'GND': ('/GND', 'C2.2', 'U2.4')}),
        'note': 'Pad-centre polygon area and routed leg lengths of the actual copper. The input loop is the only '
                'discontinuous-current loop; the output loop carries the inductor ripple only.'}
    decoupling = {'U1 VDD 100n C8': ('/+3V3', 'C8.1', 'U1.3', 'C8.2', 'U1.4'),
                  'U1 VDD 4.7u C7': ('/+3V3', 'C7.1', 'U1.3', 'C7.2', 'U1.4'),
                  'U7 C17': ('/+3V3', 'C17.1', 'U7.5', 'C17.2', 'U7.2'),
                  'U5 3V3 C9': ('/+3V3', 'C9.1', 'U5.1', 'C9.2', 'U5.4'),
                  'U5 VLED C10': ('/VLED', 'C10.1', 'U5.8', 'C10.2', 'U5.4'),
                  'U4 in C15': ('/+5V', 'C15.1', 'U4.1', 'C15.2', 'U4.2'),
                  'U4 out C16': ('/VLED', 'C16.1', 'U4.6', 'C16.2', 'U4.2'),
                  'U3 in C5': ('/+5V', 'C5.1', 'U3.1', 'C5.2', 'U3.2'),
                  'U3 out C6': ('/+3V3', 'C6.1', 'U3.5', 'C6.2', 'U3.2'),
                  'U2 in C1': ('/+12V_PROT', 'C1.1', 'U2.3', 'C1.2', 'U2.4'),
                  'U2 out C2': ('/+5V', 'C2.1', 'U2.1', 'C2.2', 'U2.4')}
    rows = {}
    for name, (net, cap, pin, gcap, gpin) in decoupling.items():
        a, b = path(net, cap, pin), path('/GND', gcap, gpin)
        rows[name] = {'supply_leg_mm': a['mm'], 'ground_leg_mm': b['mm'], 'loop_trace_mm': round(a['mm'] + b['mm'], 3),
                      'layer_changes': a['layer_changes'] + b['layer_changes'], 'loop_ohm': a['ohm'] + b['ohm'],
                      'loop_partial_inductance_nH_estimate': round(trace_inductance_nH(a['mm'], .3) + trace_inductance_nH(b['mm'], .3), 2)}
    for name, (net, cap, pin) in {'U6 +12V C11': ('/+12V_PROT', 'C11.1', 'U6.5'), 'U6 -12V C12': ('/-12V_PROT', 'C12.2', 'U6.2')}.items():
        a = path(net, cap, pin)
        rows[name] = {'supply_leg_mm': a['mm'], 'layer_changes': a['layer_changes'],
                      'note': 'U6 has no ground pin; the capacitor ground is on the power branch on purpose'}
    out['decoupling'] = {'rows': rows, 'note': 'Routed centre-line lengths between pad copper; the inductance is a straight-conductor '
                                               'partial estimate at 0.3 mm width, for comparison only.'}

    # -- coupling
    victims = ['/CV_SENSE', '/CV_THRU', '/CV_BUF', '/CV_AFFINE', '/CV_FILTER', '/CV_DRIVE', '/CV_ADC']
    aggressors = ['/BUCK_SW', '/BUCK_BST', '/DATA_L', '/DATA_R', '/DATA_L_5V', '/DATA_R_5V', '/DATA_L_3V3', '/DATA_R_3V3',
                  '/VLED', '/SWCLK', '/SWDIO', '/+12V_PROT', '/-12V_PROT']
    table = {v: {a: separation(geometry, proposal, v, a) for a in aggressors} for v in victims}
    failures = []
    for (a, b), need in SEPARATE.items():
        got = separation(geometry, proposal, a, b)['any_layer_mm']
        if got is None or got < need - 1e-6:
            failures.append(f'{a} to {b} is {got} mm on some layer pair, required {need}')
    # Capacitance of the closest CV_SENSE aggressor: two coplanar strips in a half-FR-4 half-air medium.
    eps = 8.854e-15 * (1 + 4.4) / 2     # F/mm
    estimates = {}
    for agg, swing, f_hz in (('/BUCK_SW', 13.2, 1.1e6), ('/DATA_L', 5.0, 8e5), ('/DATA_R', 5.0, 8e5)):
        gap = table['/CV_SENSE'][agg]['any_layer_mm']
        if gap:
            # 2 mm of facing edge taken as the coupled length of these short nets (ASSUMED)
            c = math.pi * eps * 2.0 / math.log(math.pi * gap / (.2 + .035) + 1)
            node_c = 3e-12   # ASSUMED op-amp input plus node capacitance
            estimates[agg] = {'gap_mm': gap, 'coupling_fF_estimate': round(c * 1e15, 2),
                              'ripple_at_CV_SENSE_mV_estimate': round(swing * c / (c + node_c) * 1e3, 2),
                              'after_776Hz_filter_uV_at_CV_AFFINE_estimate': round(swing * c / (c + node_c) * 776 / f_hz * 1e6 / 4, 3)}
    node_c = 5e-12    # ASSUMED open jack tip node: jack, 45 mm of trace, R1
    open_input = {}
    for agg in ('/DATA_L', '/DATA_R', '/DATA_L_3V3', '/DATA_R_3V3', '/DATA_L_5V', '/DATA_R_5V', '/BUCK_SW', '/SWCLK', '/SWDIO', '/VLED'):
        fF, mm = coupling_capacitance_fF(geometry, proposal, '/CV_THRU', agg)
        open_input[agg] = {'coupling_fF_estimate': fF, 'victim_track_mm_within_5mm': mm,
                           'fraction_of_aggressor_swing_on_open_tip': round(fF * 1e-15 / (fF * 1e-15 + node_c), 4)}
    held_F = {'/CV_AFFINE': 10e-9}    # C13 in the kept schematic
    close = {}
    for v in victims:
        for agg in aggressors:
            row = table[v][agg]
            if row['track_mm_of_first_within_0.5mm'] or (row['same_layer_mm'] is not None and row['same_layer_mm'] < 0.6):
                fF, _ = coupling_capacitance_fF(geometry, proposal, v, agg)
                close[v + ' / ' + agg] = {**row, 'coupling_fF_estimate': fF,
                                          **({'fraction_of_aggressor_swing_on_held_node': fF * 1e-15 / (fF * 1e-15 + held_F[v])}
                                             if v in held_F else {})}
    out['coupling'] = {
        'CV_THRU_open_input': {
            'rows': open_input, 'assumed_open_node_pF': node_c * 1e12,
            'note': 'With nothing patched the jack tip is 20 Mohm to ground, so data edges couple by the capacitive divider '
                    'shown (zero mean, decays with about 0.1 ms, then the 776 Hz filter and the firmware 1/8 IIR). A patched '
                    'source of 1 kohm or less reduces it by more than 1e4. The former In1 plane no longer shields this run; '
                    'whether the unpatched reading stays inside the +/-50 mV deadband NEEDS BENCH (#10). Not an acceptance gate.'},
        'close_pairs': {
            'rows': close,
            'note': 'Every CV-chain / aggressor pair with a same-layer gap under 0.6 mm or any track within 0.5 mm in plan. '
                    'Only the pairs under required carry a routing rule; the old 1.6 mm statement that no CV node runs '
                    'within 0.6 mm of DATA_L/R or +/-12V_PROT on the same layer does not hold on this board. CV_AFFINE is held '
                    'by C13 (10 nF), CV_ADC is driven through 250 ohm, CV_BUF and CV_DRIVE are op-amp outputs; the effect '
                    'on the reading NEEDS BENCH (#10).'},
        'separation_mm': table, 'required': {a + ' / ' + b: d for (a, b), d in SEPARATE.items()}, 'failures': failures,
        'CV_SENSE_capacitive_estimate': estimates,
        'note': 'Plan-view copper gaps over all layers (no plane shields one layer from another). CV_SENSE is the only '
                'megohm node; CV_AFFINE is held by C13 (10 nF) and CV_ADC by 250 ohm. The capacitance figures are order-of-'
                'magnitude estimates with ASSUMED coupled length and node capacitance; bench CV-noise work stays in #10.'}
    out['status'] = {'pass': bool(out['incremental_LED_DC_budget']['pass'] and out['combined_DC_budget']['pass']
                                  and out['patched_ground_loop']['pass']
                                  and not out['filled_star_audit']['failures'] and not failures
                                  and not out['kelvin_audit']['failures']
                                  and out['power_DC_screen']['buck_switch_net_vias'] == 0
                                  and out['power_DC_screen']['inner_layer_high_current_track_mm'] == 0)}
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--geometry', type=Path, required=True)
    parser.add_argument('--routes', type=Path, required=True)
    parser.add_argument('--board', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    geometry, proposal = [json.loads(p.read_text()) for p in (args.geometry, args.routes)]
    board = parse_sexp(args.board.read_text())
    out = review(geometry, proposal, board)
    out['inputs'] = {name + '_sha256': hashlib.sha256(p.read_bytes()).hexdigest()
                     for name, p in [('geometry', args.geometry), ('routes', args.routes), ('board', args.board)]}
    args.out.write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps({'incremental_LED': out['incremental_LED_DC_budget'], 'combined': out['combined_DC_budget'],
'patched_ground_loop': {k: out['patched_ground_loop'][k] for k in
                                              ('bound_LSB', 'nominal_bound_LSB', 'fraction_bound_ASSUMED',
                                               'fraction_at_allocation', 'pass')},
                      'star_audit_failures': out['filled_star_audit']['failures'],
                      'coupling_failures': out['coupling']['failures'],
                      'kelvin_failures': out['kelvin_audit']['failures'], 'status': out['status']}, indent=1))
    return 0 if out['status']['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
