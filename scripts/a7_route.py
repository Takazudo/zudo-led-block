#!/usr/bin/env python3
"""Deterministic grid router for the A7 controller staging board.

Input is the copper geometry that `a7_board.py build` reads back from pcbnew (geometry.json).
Output is routes.json (tracks and vias) for `a7_board.py apply`. Nothing here touches the repository;
the result is a routing proposal that the native DRC in the pinned KiCad image accepts or rejects.

Model: 0.1 mm grid; routing layers F.Cu, In1.Cu, In2.Cu and B.Cu (no global planes); 45-degree
moves; vias only where the via disk clears every other net on every layer. Clearances are the board
rules (0.15 copper, 0.2 hole and edge) plus ROUTER_MARGIN for grid discretisation. All nets, including
every SMD and THT GND pad, are routed as a tree by repeated A* from the
connected part to the nearest unconnected pad.

Congestion is resolved by negotiation (PathFinder): pads, holes and the board edge are hard, but another
net's routed copper only costs (1 + history) * (1 + present * users). After each pass, cells where a net's
centre line or via lies inside another net's clearance region gain history cost and the conflicting nets
are rerouted with a higher present factor, until no conflict remains. A result is written only as a
proposal; native DRC decides.

Usage: python3 scripts/a7_route.py --geometry G --out routes.json
"""
from __future__ import annotations

import argparse
import heapq
import json
import math
import sys
from pathlib import Path

import numpy as np

PITCH = 0.1
CLEAR = 0.15
# board hole clearance is 0.2; tracks keep the stricter custom rule a7_pth_to_track (controller.kicad_dru) from plated holes
HOLE_CLEAR = 0.35
EDGE_CLEAR = 0.2
ROUTER_MARGIN = 0.03
# A7 authorized rule delta: 0.5/0.2 mm vias (native_gate.json design_rule_delta)
VIA_D, VIA_DRILL = 0.5, 0.2
W_SIGNAL, W_POWER = 0.2, 0.3
POWER = {'/+5V', '/VLED', '/+12V_RAW', '/+12V_PROT', '/-12V_RAW', '/-12V_PROT', '/BUCK_SW', '/+3V3', '/GND'}
GND = '/GND'
ROUTE_LAYERS = ['F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu']
VIA_COST = 6.0
INNER_COST = 1.0
HARD = -1
# Fan-out reserves: around the fine-pitch parts, foreign nets pay ESCAPE_COST per cell, and the parts' own
# nets are routed first, so their escapes are not taken by through-traffic.
ESCAPE_PARTS = {'U1': 1.2, 'U5': 0.8}
ESCAPE_COST = 3.0
# Layout review (PR #30): no signal vias between the pads under U1's body (half-size of the via-free square around
# its centre; U1.4 GND may connect locally there), and the ADC input stays out of U1's footprint on every layer
# except its own pad.
NO_VIA_UNDER = {'U1': 1.6}
KEEP_OUT_OF = {'/CV_ADC': ('U1', -0.2)}
# Without a shielding plane every copper layer couples in plan view. Preserve the
# reviewed 1.2mm separation also across layers; native connectivity is a separate gate.
SEPARATE = {('/CV_FILTER', '/VLED'): 1.2,
            # CV_THRU is the jack tip: 20 Mohm to ground when nothing is patched. Keep the LED data lines off it.
            ('/CV_THRU', '/DATA_L'): 1.2, ('/CV_THRU', '/DATA_R'): 1.2,
            ('/CV_THRU', '/DATA_L_3V3'): 0.9, ('/CV_THRU', '/DATA_R_3V3'): 0.9,
            # CV_SENSE is the 5 Mohm divider node at U6.3; with no plane it keeps distance from the
            # switch node and the LED data lines on every layer.
            ('/CV_SENSE', '/BUCK_SW'): 2.5, ('/CV_SENSE', '/DATA_L'): 1.5, ('/CV_SENSE', '/DATA_R'): 1.5}
COUPLED = {layer: set(ROUTE_LAYERS) for layer in ROUTE_LAYERS}
PRES0, PRES_MULT, HIST_INC = 0.5, 1.6, 1.0
MAX_ITER = 60
MAX_POPS = 2000000
HOLE_TO_HOLE = 0.25  # KiCad default board rule, also between holes of one net
# Separate the pulsed/LED return branch from CV/MCU returns, meeting only
# at the J5.2 connector pin. This is routing topology, not a new logical net.
# Power branch: buck, load switch, LED header, VLED/+5V/rail decoupling and the
# 5 V level shifter with its pull-downs (LED data edge return). Everything else,
# including the CV divider reference R2, is the quiet branch.
GND_POWER_REFS = {'C1','C2','C3','C9','C10','C11','C12','C15','C16','R11','R16','R17','R18','R19','R20',
                  'U2','U4','U5','J3','__BUCK_GND'}
# Real stitch vias from the buck ground into the local B.Cu copper; each clears
# every pad mask aperture (no via-in-pad, see MASK_WEB).
GND_LOCAL_STITCH = [(5.0, 3.9), (5.8, 3.9)]
# U1.4 is ring-locked on F.Cu: its one via under the body is the Kelvin point of
# the CV/ADC reference (trunk in, analog island out).
MCU_GND_VIA = (2.6, 27.0)
W_GND_STAR = 0.6
# The branches use opposite faces of the plated J5.2 pad, so neither shares
# annulus copper with the other: quiet branch B.Cu, power branch F.Cu.
STAR_LAYER = {False: 'B.Cu', True: 'F.Cu'}
# JLC minimum solder-mask bridge (fab/jlcpcb_capabilities.json). Via copper keeps
# this web from every pad mask aperture, also of its own net.
MASK_WEB = 0.1
# Continuous supply current (buck input 0.2 A, LED 0.44 A): 0.3 mm on the 35 um outer copper only.
HIGH_CURRENT = {'/+5V','/VLED','/BUCK_SW','/+12V_RAW','/+12V_PROT'}
# Reference taps that carry no load current are taken from one pad, apart from the rest of their net, so the
# supply drop of the load does not appear in the reference: the CV affine divider (R4, R5) senses +3V3 at the
# MCU supply decoupler C8.1, 0.5 mm from VDD/VDDA (U1.3), because the firmware measures that same VDDA.
KELVIN = {'/+3V3': {'source': 'C8.1', 'pads': ['R4.1', 'R5.1']}}


def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = np.clip(((px - ax) * dx + (py - ay) * dy) / L, 0, 1) if L > 0 else 0.0
    return np.hypot(px - (ax + t * dx), py - (ay + t * dy))


def poly_dist(px, py, poly):
    """Distance from points to a closed polygon (0 inside)."""
    pts = np.asarray(poly)
    d = np.full(px.shape, np.inf)
    inside = np.zeros(px.shape, bool)
    n = len(pts)
    for k in range(n):
        ax, ay = pts[k]
        bx, by = pts[(k + 1) % n]
        d = np.minimum(d, seg_dist(px, py, ax, ay, bx, by))
        cond = ((ay > py) != (by > py))
        with np.errstate(divide='ignore', invalid='ignore'):
            xint = ax + (py - ay) * (bx - ax) / (by - ay)
        inside ^= cond & (px < xint)
    d[inside] = 0.0
    return d


class Grid:
    def __init__(self, geo):
        x1, y1, x2, y2 = geo['outline']
        self.nx = int(round((x2 - x1) / PITCH)) + 1
        self.ny = int(round((y2 - y1) / PITCH)) + 1
        self.layers = geo['layers']
        self.xs = x1 + np.arange(self.nx) * PITCH
        self.ys = y1 + np.arange(self.ny) * PITCH
        self.outline = geo['outline']
        # owner grids per (class, layer): 0 free, HARD blocked, k>0 net id, -2 several nets
        self.classes = {'s': W_SIGNAL / 2, 'p': W_POWER / 2, 'g':W_GND_STAR/2, 'v': VIA_D / 2}
        self.own = {(c, l): np.zeros((self.ny, self.nx), np.int32) for c in self.classes for l in self.layers}
        X, Y = np.meshgrid(self.xs, self.ys)
        for c, h in self.classes.items():
            r = EDGE_CLEAR + h + ROUTER_MARGIN
            edge = (X < x1 + r) | (X > x2 - r) | (Y < y1 + r) | (Y > y2 - r)
            for l in self.layers:
                self.own[(c, l)][edge] = HARD

    def window(self, bbox, r):
        x1, y1, x2, y2 = bbox
        i1 = max(0, int(math.floor((x1 - r - self.outline[0]) / PITCH)))
        i2 = min(self.nx, int(math.ceil((x2 + r - self.outline[0]) / PITCH)) + 1)
        j1 = max(0, int(math.floor((y1 - r - self.outline[1]) / PITCH)))
        j2 = min(self.ny, int(math.ceil((y2 + r - self.outline[1]) / PITCH)) + 1)
        return slice(j1, j2), slice(i1, i2)

    def mark(self, layers, bbox, distfn, extra, net, clear=CLEAR):
        for c, h in self.classes.items():
            r = extra + clear + h + ROUTER_MARGIN
            sj, si = self.window(bbox, r)
            X, Y = np.meshgrid(self.xs[si], self.ys[sj])
            hit = distfn(X, Y) < r
            for l in layers:
                g = self.own[(c, l)][sj, si]
                if net == HARD:
                    g[hit] = HARD
                else:
                    free = hit & (g == 0)
                    other = hit & (g != 0) & (g != net)
                    g[free] = net
                    g[other] = np.where(g[other] == HARD, HARD, -2)

    def cell(self, x, y):
        return (int(round((x - self.outline[0]) / PITCH)), int(round((y - self.outline[1]) / PITCH)))

    def xy(self, i, j):
        return (round(self.outline[0] + i * PITCH, 4), round(self.outline[1] + j * PITCH, 4))


def bbox_of(pts, r=0.0):
    a = np.asarray(pts)
    return (a[:, 0].min() - r, a[:, 1].min() - r, a[:, 0].max() + r, a[:, 1].max() + r)


MOVES = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
         (1, 1, math.sqrt(2)), (1, -1, math.sqrt(2)), (-1, 1, math.sqrt(2)), (-1, -1, math.sqrt(2))]


class Router:
    def __init__(self, geo):
        self.geo = geo
        self.g = Grid(geo)
        self.net_ids = {}
        for p in geo['pads']:
            if p['net'] and p['net'] not in self.net_ids:
                self.net_ids[p['net']] = len(self.net_ids) + 1
        self.nid_net = {v: k for k, v in self.net_ids.items()}
        self.pads = list(geo['pads'])
        # Routing terminals for real vias, not extra schematic pads.
        guides = [('__BUCK_GND', str(k + 1), xy) for k, xy in enumerate(GND_LOCAL_STITCH)] + [('__MCU_GND', '1', MCU_GND_VIA)]
        self.guide_vias = {ref + '.' + pad: xy for ref, pad, xy in guides}
        for ref, pad, (x, y) in guides:
            poly = [[x+VIA_D/2*math.cos(k*math.pi/16), y+VIA_D/2*math.sin(k*math.pi/16)] for k in range(32)]
            self.pads.append({'ref':ref,'pad':pad,'net':GND,'at':[x,y],
                              'polys':{l:[poly] for l in ROUTE_LAYERS},'smd_layer':None,
                              'drill':{'at':[x,y],'size':[VIA_DRILL,VIA_DRILL],'angle':0,'plated':True}})
        self.branch_forbidden = None
        self.branch_net = GND
        self.power_ground = False
        for p in self.pads:
            nid = self.net_ids.get(p['net'], HARD)
            for l, polys in p['polys'].items():
                for poly in polys:
                    self.g.mark([l], bbox_of(poly), lambda X, Y, poly=poly: poly_dist(X, Y, poly), 0.0, nid)
            d = p['drill']
            if d:
                hx, hy = d['size'][0] / 2, d['size'][1] / 2
                a = math.radians(d['angle'])
                # oval hole as a capsule along its long axis (KiCad orientation is counter-clockwise, Y down)
                L = max(hx, hy) - min(hx, hy)
                ux, uy = (math.cos(a), -math.sin(a)) if hx >= hy else (math.sin(a), math.cos(a))
                ax, ay = d['at'][0] - ux * L, d['at'][1] - uy * L
                bx, by = d['at'][0] + ux * L, d['at'][1] + uy * L
                rad = min(hx, hy)
                fn = lambda X, Y, ax=ax, ay=ay, bx=bx, by=by, rad=rad: seg_dist(X, Y, ax, ay, bx, by) - rad
                bb = (min(ax, bx) - rad, min(ay, by) - rad, max(ax, bx) + rad, max(ay, by) + rad)
                # hole clearance applies to every other net; NPTH holes block everything
                self.g.mark(self.g.layers, bb, fn, 0.0, nid if d['plated'] else HARD, clear=HOLE_CLEAR)
        self.base = self.g.own
        shape = (self.g.ny, self.g.nx)
        self.keys = list(self.base)
        self.cnt = {k: np.zeros(shape, np.int16) for k in self.keys}
        self.hist = {l: np.zeros(shape, np.float32) for l in ROUTE_LAYERS}
        self.hist_via = np.zeros(shape, np.float32)
        self.pres = PRES0
        self.mask = {}            # net -> {key: bool array} union of its clearance regions
        self.tracks, self.vias, self.cells = {}, {}, {}
        self.reserve = np.zeros(shape, bool)
        self.reserve_nets = set()
        X, Y = np.meshgrid(self.g.xs, self.g.ys)
        for ref, m in ESCAPE_PARTS.items():
            x1, y1, x2, y2 = geo['courtyards'][ref]
            self.reserve |= (X > x1 - m) & (X < x2 + m) & (Y > y1 - m) & (Y < y2 + m)
            self.reserve_nets |= {p['net'] for p in self.pads if p['ref'] == ref and p['net']}
        self.no_via = np.zeros(shape, bool)
        for ref, h in NO_VIA_UNDER.items():
            x1, y1, x2, y2 = geo['courtyards'][ref]
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            self.no_via |= (np.abs(X - cx) < h) & (np.abs(Y - cy) < h)
        # Pad mask apertures are pad copper (pad_to_mask_clearance 0). A via whose
        # copper came within MASK_WEB of one would lose its tent to that aperture.
        self.pad_via_block = np.zeros(shape, bool)
        r = VIA_D / 2 + MASK_WEB + ROUTER_MARGIN
        for p in geo['pads']:
            for l in ('F.Cu', 'B.Cu'):
                for poly in p['polys'].get(l, []):
                    sj, si = self.g.window(bbox_of(poly), r)
                    PX, PY = np.meshgrid(self.g.xs[si], self.g.ys[sj])
                    self.pad_via_block[sj, si] |= poly_dist(PX, PY, poly) < r
        self.keep_out = {}
        for net, (ref, m) in KEEP_OUT_OF.items():
            x1, y1, x2, y2 = geo['courtyards'][ref]
            self.keep_out[net] = (X > x1 - m) & (X < x2 + m) & (Y > y1 - m) & (Y < y2 + m)

    # -- base (hard) passability: pads, holes, edge
    def passable(self, cls, layer, nid):
        g = self.base[(cls, layer)]
        ok = (g == 0) | (g == nid)
        net = self.nid_net.get(nid)
        # 15.2um inner copper is not used for the LED supply/return current.
        # Vias may span all layers, but continuous high-current tracks remain
        # on the 35um outer copper at 0.3mm width.
        if cls != 'v' and layer not in ('F.Cu','B.Cu') and (net in HIGH_CURRENT or (net==GND and self.power_ground)):
            return np.zeros_like(ok)
        if net in self.keep_out:
            # own pad copper stays reachable (g == nid); everything else in the footprint is closed to this net
            ok &= ~self.keep_out[net] | (g == nid) & (layer == 'F.Cu')
        if net == self.branch_net and self.branch_forbidden is not None:
            ok &= ~self.branch_forbidden[(cls,layer)]
        return ok

    def via_ok(self, nid):
        ok = np.ones((self.g.ny, self.g.nx), bool) if self.nid_net.get(nid) == GND else ~self.no_via
        ok &= ~self.pad_via_block
        for l in self.g.layers:
            ok &= self.passable('v', l, nid)
        return ok

    # -- occupancy of routed copper
    def region(self, m, layers, bbox, distfn, extra):
        for c, h in self.g.classes.items():
            r = extra + CLEAR + h + ROUTER_MARGIN
            sj, si = self.g.window(bbox, r)
            X, Y = np.meshgrid(self.g.xs[si], self.g.ys[sj])
            hit = distfn(X, Y) < r
            for l in layers:
                m[(c, l)][sj, si] |= hit

    def rip(self, net):
        if net in self.mask:
            for k in self.keys:
                self.cnt[k] -= self.mask[net][k]
            del self.mask[net]
        self.tracks[net], self.vias[net], self.cells[net] = [], [], []

    def place(self, net):
        shape = (self.g.ny, self.g.nx)
        m = {k: np.zeros(shape, bool) for k in self.keys}
        for t in self.tracks[net]:
            a, b = t['start'], t['end']
            self.region(m, [t['layer']], (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])),
                        lambda X, Y: seg_dist(X, Y, a[0], a[1], b[0], b[1]), t['width'] / 2)
        for v in self.vias[net]:
            at = v['at']
            self.region(m, self.g.layers, (at[0], at[1], at[0], at[1]), lambda X, Y: np.hypot(X - at[0], Y - at[1]), VIA_D / 2)
        self.mask[net] = m
        for k in self.keys:
            self.cnt[k] += m[k]

    def factors(self, net, cls):
        foreign = net not in self.reserve_nets
        f = []
        for l in ROUTE_LAYERS:
            a = (1.0 + self.hist[l]) * (1.0 + self.pres * self.cnt[(cls, l)])
            if foreign:
                a = np.where(self.reserve, a * ESCAPE_COST, a)
            f.append(a.astype(np.float32))
        busy = sum(self.cnt[('v', l)].astype(np.float32) for l in self.g.layers)
        fv = (1.0 + self.hist_via) * (1.0 + self.pres * busy)
        return f, fv

    def pad_cells(self, pad, cls, nid):
        """Grid cells inside the pad copper, per routing layer, that a track of this net can occupy."""
        out = []
        for l, polys in pad['polys'].items():
            if l not in ROUTE_LAYERS:
                continue
            pas = self.passable(cls, l, nid)
            for poly in polys:
                sj, si = self.g.window(bbox_of(poly), 0)
                X, Y = np.meshgrid(self.g.xs[si], self.g.ys[sj])
                inside = poly_dist(X, Y, poly) <= 1e-9
                jj, ii = np.nonzero(inside & pas[sj, si])
                out += [(ROUTE_LAYERS.index(l), int(j + sj.start), int(i + si.start)) for j, i in zip(jj, ii)]
        return out

    def separation_block(self, net, cls, layer=None):
        """Cells closer than the SEPARATE distance to partner-net copper that couples to this layer (None: any layer)."""
        X, Y = np.meshgrid(self.g.xs, self.g.ys)
        blk = np.zeros((self.g.ny, self.g.nx), bool)
        h = self.g.classes[cls]
        for pair, d in SEPARATE.items():
            if net not in pair:
                continue
            other = pair[1] if pair[0] == net else pair[0]
            for t in self.tracks.get(other, []):
                if layer is not None and t['layer'] not in COUPLED[layer]:
                    continue
                (ax, ay), (bx, by) = t['start'], t['end']
                blk |= seg_dist(X, Y, ax, ay, bx, by) < d + t['width'] / 2 + h
            for v in self.vias.get(other, []):
                blk |= np.hypot(X - v['at'][0], Y - v['at'][1]) < d + v['size'] / 2 + h
            # A pad is opaque/aggressor copper even before its net is routed.
            # Include all coupled pad layers; the old shielded check omitted it.
            for pad in self.pads:
                if pad['net'] != other:
                    continue
                for pad_layer, polygons in pad['polys'].items():
                    if layer is not None and pad_layer not in COUPLED[layer]:
                        continue
                    for polygon in polygons:
                        blk |= poly_dist(X, Y, polygon) < d + h
        return blk

    def search(self, net, sources, targets, cls, fac, want_via_target=False, reuse_vias=True, via_target=None):
        """A* over (layer, j, i); step cost = length * congestion factor (>= 1, so the heuristic is admissible)."""
        nid = self.net_ids[net]
        nx, ny = self.g.nx, self.g.ny
        pas = [self.passable(cls, l, nid) for l in ROUTE_LAYERS]
        if any(net in pair for pair in SEPARATE):
            pas = [a & ~self.separation_block(net, cls, l) for a, l in zip(pas, ROUTE_LAYERS)]
        via = self.via_ok(nid) & ~self.own_hole_block(net)
        if any(net in pair for pair in SEPARATE):
            via &= ~self.separation_block(net, 'v')
        reuse = {(round(v['at'][0], 4), round(v['at'][1], 4)) for v in self.vias[net]} if reuse_vias else set()
        for x, y in reuse:
            i, j = self.g.cell(x, y)
            via[j, i] = True
        f, fv = fac
        tset = set(targets)
        if want_via_target:
            tx = None
        else:
            tc = np.array([(i, j) for _, j, i in targets], float)
            tx, ty = tc[:, 0], tc[:, 1]

        def h(j, i):
            return 0.0 if tx is None else float(np.min(np.hypot(tx - i, ty - j))) * 0.999

        best, prev, heap = {}, {}, []
        srcset = set(sources)
        for s_ in sources:
            best[s_] = 0.0
            prev[s_] = None
            heapq.heappush(heap, (h(s_[1], s_[2]), 0.0, s_))
        found = None
        pops = 0
        while heap:
            _, gcost, node = heapq.heappop(heap)
            if gcost > best.get(node, math.inf) + 1e-9:
                continue
            pops += 1
            if pops > MAX_POPS:
                break
            if node[0] == -1:
                found = node[1:]
                break
            l, j, i = node
            if node in tset:
                found = node
                break
            if want_via_target and via[j, i] and node not in srcset and (via_target is None or via_target[j, i]):
                g2 = gcost + VIA_COST * float(fv[j, i])
                gn = (-1,) + node
                if g2 < best.get(gn, math.inf):
                    best[gn] = g2
                    heapq.heappush(heap, (g2, g2, gn))
            fl = f[l]
            for di, dj, c in MOVES:
                i2, j2 = i + di, j + dj
                if not (0 <= i2 < nx and 0 <= j2 < ny) or not pas[l][j2, i2]:
                    continue
                if di and dj and not (pas[l][j, i2] or pas[l][j2, i]):
                    continue
                n2 = (l, j2, i2)
                g2 = gcost + c * INNER_COST ** (l == 1) * float(fl[j2, i2])
                if g2 < best.get(n2, math.inf) - 1e-9:
                    best[n2] = g2
                    prev[n2] = node
                    heapq.heappush(heap, (g2 + h(j2, i2), g2, n2))
            if via[j, i]:
                for l2 in range(len(ROUTE_LAYERS)):
                    if l2 != l and pas[l2][j, i]:
                        n2 = (l2, j, i)
                        g2 = gcost + VIA_COST * float(fv[j, i])
                        if g2 < best.get(n2, math.inf) - 1e-9:
                            best[n2] = g2
                            prev[n2] = node
                            heapq.heappush(heap, (g2 + h(j, i), g2, n2))
        if found is None:
            return None
        path = [found]
        while prev[path[-1]] is not None:
            path.append(prev[path[-1]])
        return path[::-1]

    def own_hole_block(self, net):
        """Cells where a new via would come within HOLE_TO_HOLE of a hole of the same net."""
        X, Y = np.meshgrid(self.g.xs, self.g.ys)
        blk = np.zeros((self.g.ny, self.g.nx), bool)
        holes = [(v['at'], VIA_DRILL / 2) for v in self.vias[net]]
        holes += [(p['drill']['at'], max(p['drill']['size']) / 2) for p in self.pads if p['net'] == net and p['drill']]
        for (x, y), r in holes:
            blk |= np.hypot(X - x, Y - y) < r + VIA_DRILL / 2 + HOLE_TO_HOLE + ROUTER_MARGIN
        return blk

    def commit(self, net, path, w, cls, end_via=False):
        """Turn a cell path into straight segments and vias (recorded, not yet counted)."""
        segs = []
        start = path[0]
        vias = []
        for k in range(1, len(path)):
            a, b = path[k - 1], path[k]
            if a[0] != b[0]:
                if (a[1], a[2]) != (start[1], start[2]):
                    segs.append((start, a))
                vias.append((a[1], a[2]))
                start = b
                continue
            if k + 1 < len(path):
                c = path[k + 1]
                if c[0] == b[0] and (c[1] - b[1], c[2] - b[2]) == (b[1] - a[1], b[2] - a[2]):
                    continue
            segs.append((start, b))
            start = b
        if end_via:
            vias.append((path[-1][1], path[-1][2]))
        for a, b in segs:
            if (a[1], a[2]) != (b[1], b[2]):
                self.tracks[net].append({'net': net, 'layer': ROUTE_LAYERS[a[0]], 'start': list(self.g.xy(a[2], a[1])),
                                         'end': list(self.g.xy(b[2], b[1])), 'width': w})
        have = {tuple(v['at']) for v in self.vias[net]}
        for j, i in vias:
            at = self.g.xy(i, j)
            if tuple(at) not in have:
                have.add(tuple(at))
                self.vias[net].append({'net': net, 'at': list(at), 'size': VIA_D, 'drill': VIA_DRILL})
        self.cells[net] += [(cls, n[0], n[1], n[2]) for n in path]
        self.cells[net] += [('v', None, j, i) for j, i in vias]

    def route(self, net):
        """Rip up and reroute one net under the current congestion costs."""
        self.rip(net)
        if net == GND:
            return self.route_ground()
        nid = self.net_ids[net]
        fails = []
        facs = {}

        def fac(cls):
            if cls not in facs:
                facs[cls] = self.factors(net, cls)
            return facs[cls]
        classes = (('p', W_POWER),) if net in HIGH_CURRENT else ((('p', W_POWER), ('s', W_SIGNAL)) if net in POWER else (('s', W_SIGNAL),))
        kelvin = KELVIN.get(net, {'source': None, 'pads': []})
        every = sorted((p for p in self.pads if p['net'] == net), key=lambda p: (p['at'][1], p['at'][0], p['ref'], p['pad']))
        pads = [p for p in every if p['ref'] + '.' + p['pad'] not in kelvin['pads']]
        cells = {c: [self.pad_cells(p, c, nid) for p in pads] for c in ('p', 's')}
        tree = set(cells['s'][0]) | set(cells['p'][0])
        todo = list(range(1, len(pads)))
        while todo:
            path = None
            for cls, w in classes:
                targets = [c for k in todo for c in cells[cls][k]]
                pas = [self.passable(cls, l, nid) for l in ROUTE_LAYERS]
                src = sorted(c for c in tree if pas[c[0]][c[1], c[2]])
                if targets and src:
                    path = self.search(net, src, targets, cls, fac(cls))
                if path is not None:
                    break
            if path is None:
                fails.append(f"{net}: cannot reach {[pads[k]['ref'] + '.' + pads[k]['pad'] for k in todo]}")
                break
            self.commit(net, path, w, cls)
            end = path[-1]
            for k in [k for k in todo if end in set(cells['s'][k]) or end in set(cells['p'][k])]:
                todo.remove(k)
                tree |= set(cells['s'][k]) | set(cells['p'][k])
            tree |= set(path)
        if kelvin['pads'] and not fails:
            fails += self.route_kelvin(net, every, kelvin, classes)
        self.place(net)
        return fails

    def route_kelvin(self, net, every, kelvin, classes):
        """Connect the reference taps to their source pad only, clear of the rest of the net's copper."""
        nid = self.net_ids[net]
        name = lambda p: p['ref'] + '.' + p['pad']
        self.place(net)
        blocked = {k: v.copy() for k, v in self.mask[net].items()}
        X, Y = np.meshgrid(self.g.xs, self.g.ys)
        for p in every:
            for l, polys in p['polys'].items():
                for poly in polys:
                    if name(p) == kelvin['source'] or name(p) in kelvin['pads']:
                        inside = poly_dist(X, Y, poly) <= 1e-9
                        for cls in self.g.classes:
                            blocked[(cls, l)][inside] = False
                    else:
                        self.region(blocked, [l], bbox_of(poly), lambda X, Y, poly=poly: poly_dist(X, Y, poly), 0)
        for k in self.keys:
            self.cnt[k] -= self.mask[net][k]
        del self.mask[net]
        self.branch_net, self.branch_forbidden = net, blocked
        fails = []
        by = {name(p): p for p in every}
        tree = set(self.pad_cells(by[kelvin['source']], 'p', nid)) | set(self.pad_cells(by[kelvin['source']], 's', nid))
        # vias of the main tree stay closed to the taps: reuse would join the two again
        for ref in kelvin['pads']:
            path = None
            for cls, w in classes[::-1]:
                targets = self.pad_cells(by[ref], cls, nid)
                pas = [self.passable(cls, l, nid) for l in ROUTE_LAYERS]
                src = sorted(c for c in tree if pas[c[0]][c[1], c[2]])
                if targets and src:
                    path = self.search(net, src, targets, cls, self.factors(net, cls), reuse_vias=False)
                if path is not None:
                    break
            if path is None:
                fails.append(f'{net}: reference tap {ref} cannot reach {kelvin["source"]}')
                break
            self.commit(net, path, w, cls)
            tree |= set(path) | set(self.pad_cells(by[ref], 'p', nid)) | set(self.pad_cells(by[ref], 's', nid))
        self.branch_net, self.branch_forbidden = GND, None
        return fails

    def route_ground(self):
        """Two return branches that meet only at the J5.2 pin, on opposite pad faces.

        Quiet branch (B.Cu at the pin): 0.6 mm trunk to the MCU ground via, the CV/ADC
        island taken from that via (Kelvin), the CV IN sleeve on its own 0.6 mm spur from the pin.
        Power branch (F.Cu at the pin): trunk to the buck input capacitor, stitch vias,
        then the remaining power pads by nearest-first tree growth.
        """
        net,nid = GND,self.net_ids[GND]
        self.branch_net, self.branch_forbidden = GND, None
        pads = {p['ref']+'.'+p['pad']:p for p in self.pads if p['net']==GND}
        star = pads['J5.2']
        fails = []
        X,Y = np.meshgrid(self.g.xs,self.g.ys)

        def pad_region(blocked, p):
            for l,polys in p['polys'].items():
                for poly in polys:
                    self.region(blocked,[l],bbox_of(poly),lambda X,Y,poly=poly:poly_dist(X,Y,poly),0)

        for power in (False,True):
            self.power_ground = power
            members = {k:p for k,p in pads.items() if k!='J5.2' and (p['ref'] in GND_POWER_REFS)==power}
            if not power:
                blocked = {k:np.zeros((self.g.ny,self.g.nx),bool) for k in self.keys}
                for p in pads.values():
                    if p['ref'] in GND_POWER_REFS:
                        pad_region(blocked, p)
                optical = json.loads((Path(__file__).resolve().parents[1] /
                                      'engineering/a7/verification/fab/optical-fr4.json').read_text())
                for zone in optical['controller']['local_copper']:
                    if zone['net'] != GND:
                        continue
                    x1,y1,x2,y2 = zone['rect_mm']
                    poly = [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
                    # Reserve future same-net fill before routing: otherwise
                    # it could silently bridge the two return branches during
                    # native refill. via_ok checks this on every layer too.
                    self.region(blocked,[zone['layer']],bbox_of(poly),
                                lambda X,Y,poly=poly:poly_dist(X,Y,poly),0)
            else:
                # Use the same conservative trace/via clearance model between
                # branches. Foreign ground copper cannot become an accidental
                # shared high-current return outside the connector pin.
                self.place(net)
                blocked = {k:v.copy() for k,v in self.mask[net].items()}
                for p in pads.values():
                    if p['ref'] not in GND_POWER_REFS and p is not star:
                        pad_region(blocked, p)
                for k in self.keys:self.cnt[k]-=self.mask[net][k]
                del self.mask[net]
            own = STAR_LAYER[power]
            for l,polys in star['polys'].items():
                if l == own:
                    inside = np.zeros(X.shape,bool)
                    for poly in polys:inside |= poly_dist(X,Y,poly)<=1e-9
                    for cls in self.g.classes:blocked[(cls,l)][inside]=False
                else:
                    for poly in polys:
                        self.region(blocked,[l],bbox_of(poly),lambda X,Y,poly=poly:poly_dist(X,Y,poly),0)
            self.branch_forbidden = blocked
            for name,(x,y) in sorted(self.guide_vias.items()):
                if name in members:
                    self.vias[net].append({'net':GND,'at':[x,y],'size':VIA_D,'drill':VIA_DRILL})
                    i,j = self.g.cell(x,y)
                    self.cells[net].append(('v',None,j,i))
            cells = {k:set(self.pad_cells(p,'p',nid)) for k,p in pads.items()}
            tree = {c for c in cells['J5.2'] if ROUTE_LAYERS[c[0]]==own}
            groups = {'star':set(tree)}
            pending = set(members)
            # (target, source group, class, outer copper only, groups the new copper joins)
            if power:
                priority = [('C1.2','star','p',True,['trunk']),('U2.4','C1.2','p',True,[]),
                            ('__BUCK_GND.1','C1.2','p',True,[]),('__BUCK_GND.2','U2.4','p',True,[])]
            else:
                priority = [('__MCU_GND.1','star','g',True,['trunk']),('U1.4','__MCU_GND.1','p',True,[]),
                            ('C8.2','__MCU_GND.1','p',False,[]),('R25.2','__MCU_GND.1','p',False,['island']),
                            ('R6.2','island','p',False,['island']),('U7.2','island','p',False,['island']),
                            ('C17.2','island','p',False,['island']),('C13.2','island','p',False,['island']),
                            ('D3.1','island','p',False,['island']),
                            # the 3.3 mA bleeder and the LDO cluster return on their own spur, not through the island
                            ('R8.2','trunk','p',False,['top']),('U3.2','top','p',False,['top']),
                            ('C6.2','top','p',False,['top']),('C5.2','top','p',False,['top']),
                            ('R2.2','top','p',False,['top']),
                            # a patched CV cable returns part of the supply current through the CV IN
                            # sleeve (electrical_review.md, patched ground loop): wide outer copper from the pin
                            ('J1.1','star','g',True,['jack']),('J1.2','jack','p',False,['jack']),
                            ('J2.2','jack','p',False,['jack']),('J2.1','jack','p',False,['jack'])]
            while pending:
                target,source,cls,outer,joins = priority.pop(0) if priority else (None,None,'p',power,[])
                wanted = [target] if target else sorted(pending)
                width = W_GND_STAR if cls=='g' else W_POWER
                targets = set().union(*(cells[k] for k in wanted))
                sources = tree if source is None else groups[source] if source in groups else cells[source]
                self.power_ground = outer
                pas = [self.passable(cls,l,nid) for l in ROUTE_LAYERS]
                targets = sorted(c for c in targets if pas[c[0]][c[1],c[2]])
                sources = sorted(c for c in sources if pas[c[0]][c[1],c[2]])
                path = self.search(net,sources,targets,cls,self.factors(net,cls)) if sources and targets else None
                self.power_ground = power
                if path is None:
                    fails.append(f'GND {"power" if power else "signal"} branch cannot reach {wanted}')
                    break
                self.commit(net,path,width,cls)
                for k in sorted(pending):
                    if path[-1] in cells[k]:
                        pending.remove(k);tree |= cells[k]
                        for name in joins:groups.setdefault(name,set()).update(cells[k])
                for name in joins:groups.setdefault(name,set()).update(path)
                tree |= set(path)
        self.branch_forbidden = None
        self.power_ground = False
        self.place(net)
        return fails

    def conflicts(self):
        """Cells where a net's centre line or via sits inside another net's clearance region."""
        bad = {}
        for net, cells in self.cells.items():
            own = self.mask.get(net)
            if own is None:
                continue
            for cls, l, j, i in cells:
                if cls == 'v':
                    if any(self.cnt[('v', L)][j, i] - own[('v', L)][j, i] > 0 for L in self.g.layers):
                        bad.setdefault(net, []).append(('v', j, i))
                else:
                    L = ROUTE_LAYERS[l]
                    if self.cnt[(cls, L)][j, i] - own[(cls, L)][j, i] > 0:
                        bad.setdefault(net, []).append((L, j, i))
        return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--geometry', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--seed', type=int, default=0, help='0: nets by span; otherwise a seeded shuffle of the first-pass order')
    a = ap.parse_args()
    geo = json.loads(a.geometry.read_text())
    counts = {}
    for p in geo['pads']:
        if p['net']:
            counts[p['net']] = counts.get(p['net'], 0) + 1

    def span(n):
        pts = np.array([p['at'] for p in geo['pads'] if p['net'] == n])
        return float(np.ptp(pts[:, 0]) + np.ptp(pts[:, 1]))
    nets = sorted((n for n, c in counts.items() if c > 1 and n != GND), key=lambda n: (span(n), n))
    if a.seed:
        import random
        random.Random(a.seed).shuffle(nets)
    esc = {p['net'] for p in geo['pads'] if p['ref'] in ESCAPE_PARTS}
    order = [n for n in nets if n in esc] + [GND] + [n for n in nets if n not in esc]
    r = Router(geo)
    history = []
    todo = list(order)
    fails_by_net = {}
    for it in range(MAX_ITER):
        for n in todo:
            fails_by_net[n] = r.route(n)
        fails = [f for n in order for f in fails_by_net.get(n, [])]
        bad = r.conflicts()
        ncells = sum(len(v) for v in bad.values())
        history.append({'iteration': it, 'present': round(r.pres, 3), 'conflict_cells': ncells,
                        'conflict_nets': sorted(bad), 'unroutable': fails})
        print(f'iter {it}: pres {r.pres:.2f} conflicts {ncells} in {sorted(bad)} fails {fails}', file=sys.stderr, flush=True)
        if not bad and not fails:
            break
        # Negotiation only resolves congestion. With no conflict left, an unreachable pad stays
        # unreachable: stop and report the failure instead of repeating the same pass.
        if not bad and len(history) > 1 and history[-2]['conflict_cells'] == 0 and history[-2]['unroutable'] == fails:
            break
        for net, cells in bad.items():
            for L, j, i in cells:
                if L == 'v':
                    r.hist_via[j, i] += HIST_INC
                else:
                    r.hist[L][j, i] += HIST_INC
        r.pres *= PRES_MULT
        todo = [n for n in order if n in bad or fails_by_net.get(n)] or list(order)
    bad = r.conflicts()
    tracks = [t for n in order for t in r.tracks.get(n, [])]
    vias = [v for n in order for v in r.vias.get(n, [])]
    failures = fails + [f'{n}: {len(c)} cells in conflict' for n, c in sorted(bad.items())]
    out = {'generator': 'scripts/a7_route.py', 'seed': a.seed, 'pitch_mm': PITCH, 'router_margin_mm': ROUTER_MARGIN,
           'widths_mm': {'signal': W_SIGNAL, 'power': W_POWER, 'ground_star_trunk': W_GND_STAR}, 'via': {'size': VIA_D, 'drill': VIA_DRILL},
           'order': order, 'history': history, 'tracks': tracks, 'vias': vias, 'failures': failures}
    a.out.write_text(json.dumps(out, indent=0) + '\n')
    print(json.dumps({'tracks': len(tracks), 'vias': len(vias), 'failures': failures}, indent=1))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
