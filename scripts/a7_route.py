#!/usr/bin/env python3
"""Deterministic grid router for the A7 controller staging board.

Input is the copper geometry that `a7_board.py build` reads back from pcbnew (geometry.json).
Output is routes.json (tracks and vias) for `a7_board.py apply`. Nothing here touches the repository;
the result is a routing proposal that the native DRC in the pinned KiCad image accepts or rejects.

Model: 0.1 mm grid; routing layers F.Cu, In2.Cu and B.Cu (In1.Cu is the solid GND plane); 45-degree
moves; vias only where the via disk clears every other net on every layer. Clearances are the board
rules (0.15 copper, 0.2 hole and edge) plus ROUTER_MARGIN for grid discretisation. GND SMD pads each get
a short stub to a via into the In1 plane; every other net is routed as a tree by repeated A* from the
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
HOLE_CLEAR = 0.2
EDGE_CLEAR = 0.2
ROUTER_MARGIN = 0.03
# A7 authorized rule delta: 0.5/0.2 mm vias (native_gate.json design_rule_delta)
VIA_D, VIA_DRILL = 0.5, 0.2
W_SIGNAL, W_POWER = 0.2, 0.3
POWER = {'/+5V', '/VLED', '/+12V_RAW', '/+12V_PROT', '/-12V_RAW', '/-12V_PROT', '/BUCK_SW', '/+3V3', '/GND'}
GND = '/GND'
PLANE = 'In1.Cu'
ROUTE_LAYERS = ['F.Cu', 'In2.Cu', 'B.Cu']
VIA_COST = 6.0
INNER_COST = 1.0
HARD = -1
# Fan-out reserves: around the fine-pitch parts, foreign nets pay ESCAPE_COST per cell, and the parts' own
# nets are routed first, so their escapes are not taken by through-traffic.
ESCAPE_PARTS = {'U1': 1.2, 'U5': 0.8}
ESCAPE_COST = 3.0
# Layout review (PR #30): no signal vias between the pads under U1's body (half-size of the via-free square around
# its centre; U1.4 GND may stitch to the plane there), and the ADC input stays out of U1's footprint on every layer
# except its own pad.
NO_VIA_UNDER = {'U1': 1.6}
KEEP_OUT_OF = {'/CV_ADC': ('U1', -0.2)}
# Buck hot-loop GND pads get more than one via into the In1 plane.
GND_VIAS = {('U2', '4'): 2, ('C1', '2'): 2, ('C2', '2'): 2}
PRES0, PRES_MULT, HIST_INC = 0.5, 1.6, 1.0
MAX_ITER = 60
MAX_POPS = 2000000
HOLE_TO_HOLE = 0.25  # KiCad default board rule, also between holes of one net


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
        self.classes = {'s': W_SIGNAL / 2, 'p': W_POWER / 2, 'v': VIA_D / 2}
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
        self.pads = geo['pads']
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
        self.keep_out = {}
        for net, (ref, m) in KEEP_OUT_OF.items():
            x1, y1, x2, y2 = geo['courtyards'][ref]
            self.keep_out[net] = (X > x1 - m) & (X < x2 + m) & (Y > y1 - m) & (Y < y2 + m)

    # -- base (hard) passability: pads, holes, edge
    def passable(self, cls, layer, nid):
        g = self.base[(cls, layer)]
        ok = (g == 0) | (g == nid)
        net = self.nid_net.get(nid)
        if net in self.keep_out:
            # own pad copper stays reachable (g == nid); everything else in the footprint is closed to this net
            ok &= ~self.keep_out[net] | (g == nid) & (layer == 'F.Cu')
        return ok

    def via_ok(self, nid):
        ok = np.ones((self.g.ny, self.g.nx), bool) if self.nid_net.get(nid) == GND else ~self.no_via
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

    def search(self, net, sources, targets, cls, fac, want_via_target=False, reuse_vias=True):
        """A* over (layer, j, i); step cost = length * congestion factor (>= 1, so the heuristic is admissible)."""
        nid = self.net_ids[net]
        nx, ny = self.g.nx, self.g.ny
        pas = [self.passable(cls, l, nid) for l in ROUTE_LAYERS]
        via = self.via_ok(nid) & ~self.own_hole_block(net)
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
            if want_via_target and via[j, i] and node not in srcset:
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
        nid = self.net_ids[net]
        fails = []
        facs = {}

        def fac(cls):
            if cls not in facs:
                facs[cls] = self.factors(net, cls)
            return facs[cls]
        classes = (('p', W_POWER), ('s', W_SIGNAL)) if net in POWER else (('s', W_SIGNAL),)
        if net == GND:
            for p in self.pads:
                if p['net'] != GND or p['drill']:
                    continue
                for k in range(GND_VIAS.get((p['ref'], p['pad']), 1)):
                    for cls, w in classes:
                        src = self.pad_cells(p, cls, nid)
                        path = self.search(GND, src, [], cls, fac(cls), want_via_target=True, reuse_vias=k == 0) if src else None
                        if path is not None:
                            self.commit(GND, path, w, cls, end_via=True)
                            break
                    else:
                        fails.append(f"{GND}: {p['ref']}.{p['pad']} has no via site ({k + 1})")
        else:
            pads = sorted((p for p in self.pads if p['net'] == net), key=lambda p: (p['at'][1], p['at'][0], p['ref'], p['pad']))
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
           'widths_mm': {'signal': W_SIGNAL, 'power': W_POWER}, 'via': {'size': VIA_D, 'drill': VIA_DRILL},
           'order': order, 'history': history, 'tracks': tracks, 'vias': vias, 'failures': failures}
    a.out.write_text(json.dumps(out, indent=0) + '\n')
    print(json.dumps({'tracks': len(tracks), 'vias': len(vias), 'failures': failures}, indent=1))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
