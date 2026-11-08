#!/usr/bin/env python3
"""Deterministic grid router for the A7 controller staging board.

Input is the copper geometry that `a7_board.py build` reads back from pcbnew (geometry.json).
Output is routes.json (tracks and vias) for `a7_board.py apply`. Nothing here touches the repository;
the result is a routing proposal that the native DRC in the pinned KiCad image accepts or rejects.

Model: 0.1 mm grid; routing layers F.Cu, In2.Cu and B.Cu (In1.Cu is the solid GND plane); 45-degree
moves; vias only where the via disk clears every other net on every layer. Clearances are the board
rules (0.15 copper, 0.2 hole and edge) plus ROUTER_MARGIN for grid discretisation. GND SMD pads each get
a short stub to a via into the In1 plane; every other net is routed as a tree by repeated A* from the
connected part to the nearest unconnected pad, with rip-up and reroute when a connection is blocked.

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
VIA_D, VIA_DRILL = 0.6, 0.3
W_SIGNAL, W_POWER = 0.2, 0.3
POWER = {'/+5V', '/VLED', '/+12V_RAW', '/+12V_PROT', '/-12V_RAW', '/-12V_PROT', '/BUCK_SW', '/+3V3', '/GND'}
GND = '/GND'
PLANE = 'In1.Cu'
ROUTE_LAYERS = ['F.Cu', 'In2.Cu', 'B.Cu']
VIA_COST = 6.0
INNER_COST = 1.0
HARD = -1
SOFT_PENALTY = 8.0
MAX_POPS = 1500000
MAX_RIPS = 20


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


class Router:
    def __init__(self, geo):
        self.geo = geo
        self.g = Grid(geo)
        self.net_ids = {}
        for p in geo['pads']:
            if p['net'] and p['net'] not in self.net_ids:
                self.net_ids[p['net']] = len(self.net_ids) + 1
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
        self.base = {k: v.copy() for k, v in self.g.own.items()}
        self.tracks, self.vias = [], []
        self.item = None
        self.soft = None
        self._pas = {}

    # -- occupancy of routed copper
    def mark_track(self, t):
        a, b = t['start'], t['end']
        fn = lambda X, Y: seg_dist(X, Y, a[0], a[1], b[0], b[1])
        self.g.mark([t['layer']], (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])), fn, t['width'] / 2,
                    self.net_ids[t['net']])

    def mark_via(self, v):
        at = v['at']
        fn = lambda X, Y: np.hypot(X - at[0], Y - at[1])
        self.g.mark(self.g.layers, (at[0], at[1], at[0], at[1]), fn, VIA_D / 2, self.net_ids[v['net']])

    def add_track(self, net, layer, a, b, w):
        t = {'net': net, 'layer': layer, 'start': list(a), 'end': list(b), 'width': w, 'item': self.item}
        if self.soft is not None:
            self.soft.append(t)
            return
        self.mark_track(t)
        self.tracks.append(t)
        self._pas.clear()

    def add_via(self, net, at):
        v = {'net': net, 'at': list(at), 'size': VIA_D, 'drill': VIA_DRILL, 'item': self.item}
        if self.soft is not None:
            self.soft.append(v)
            return
        self.mark_via(v)
        self.vias.append(v)
        self._pas.clear()

    def remove(self, items):
        self.tracks = [t for t in self.tracks if t['item'] not in items]
        self.vias = [v for v in self.vias if v['item'] not in items]
        self.g.own = {k: v.copy() for k, v in self.base.items()}
        for t in self.tracks:
            self.mark_track(t)
        for v in self.vias:
            self.mark_via(v)
        self._pas.clear()

    def passable(self, cls, layer, nid, base=False):
        key = (cls, layer, nid, base)
        if key not in self._pas:
            g = (self.base if base else self.g.own)[(cls, layer)]
            self._pas[key] = (g == 0) | (g == nid)
        return self._pas[key]

    def via_ok(self, nid, base=False):
        key = ('via', nid, base)
        if key not in self._pas:
            ok = np.ones((self.g.ny, self.g.nx), bool)
            for l in self.g.layers:
                ok &= self.passable('v', l, nid, base)
            self._pas[key] = ok
        return self._pas[key]

    def pad_cells(self, pad, cls, nid):
        """Grid cells inside the pad copper, per routing layer, that a track of this net can occupy."""
        out = []
        for l, polys in pad['polys'].items():
            if l not in ROUTE_LAYERS:
                continue
            pas = self.passable(cls, l, nid, base=self.soft is not None)
            for poly in polys:
                sj, si = self.g.window(bbox_of(poly), 0)
                X, Y = np.meshgrid(self.g.xs[si], self.g.ys[sj])
                inside = poly_dist(X, Y, poly) <= 1e-9
                jj, ii = np.nonzero(inside & pas[sj, si])
                out += [(ROUTE_LAYERS.index(l), int(j + sj.start), int(i + si.start)) for j, i in zip(jj, ii)]
        return out

    def search(self, net, sources, targets, cls, want_via_target=False):
        """A* over (layer, j, i) from source cells to any target cell (or any via-legal cell).

        In soft mode (rip-up probing) only pads, holes and the edge are hard; cells occupied by other nets'
        routed copper cost SOFT_PENALTY each, so the path shows which nets block the connection."""
        nid = self.net_ids[net]
        nx, ny = self.g.nx, self.g.ny
        soft = self.soft is not None
        pas = [self.passable(cls, l, nid, base=soft) for l in ROUTE_LAYERS]
        via = self.via_ok(nid, base=soft)
        if soft:
            busy = [~self.passable(cls, l, nid) for l in ROUTE_LAYERS]
            vbusy = ~self.via_ok(nid)
        tset = set(targets)
        if want_via_target:
            tx = ty = None
        else:
            tc = np.array([(i, j) for _, j, i in targets], float)
            tx, ty = tc[:, 0], tc[:, 1]

        def h(j, i):
            if tx is None:
                return 0.0
            return float(np.min(np.hypot(tx - i, ty - j))) * 0.999

        best = {}
        prev = {}
        heap = []
        srcset = set(sources)
        for s_ in sources:
            best[s_] = 0.0
            prev[s_] = None
            heapq.heappush(heap, (h(s_[1], s_[2]), 0.0, s_))
        moves = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
                 (1, 1, math.sqrt(2)), (1, -1, math.sqrt(2)), (-1, 1, math.sqrt(2)), (-1, -1, math.sqrt(2))]
        lc = [1.0, INNER_COST, 1.0]
        found = None
        pops = 0
        while heap:
            f, gcost, node = heapq.heappop(heap)
            if gcost > best.get(node, math.inf) + 1e-9:
                continue
            pops += 1
            if pops > MAX_POPS:
                break
            l, j, i = node
            if (want_via_target and via[j, i] and node not in srcset and not (soft and vbusy[j, i])) or node in tset:
                found = node
                break
            for di, dj, c in moves:
                i2, j2 = i + di, j + dj
                if not (0 <= i2 < nx and 0 <= j2 < ny) or not pas[l][j2, i2]:
                    continue
                if di and dj and not (pas[l][j, i2] or pas[l][j2, i]):
                    continue
                n2 = (l, j2, i2)
                g2 = gcost + c * lc[l] + (SOFT_PENALTY if soft and busy[l][j2, i2] else 0.0)
                if g2 < best.get(n2, math.inf) - 1e-9:
                    best[n2] = g2
                    prev[n2] = node
                    heapq.heappush(heap, (g2 + h(j2, i2), g2, n2))
            if via[j, i]:
                for l2 in range(len(ROUTE_LAYERS)):
                    if l2 != l and pas[l2][j, i]:
                        n2 = (l2, j, i)
                        g2 = gcost + VIA_COST + (SOFT_PENALTY if soft and vbusy[j, i] else 0.0)
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

    def commit(self, net, path, w, end_via=False):
        """Turn a cell path into straight segments and vias; mark them as occupied."""
        segs = []
        start = path[0]
        for k in range(1, len(path)):
            a, b = path[k - 1], path[k]
            if a[0] != b[0]:
                if (a[1], a[2]) != (start[1], start[2]):
                    segs.append((start, a))
                self.add_via(net, self.g.xy(a[2], a[1]))
                start = b
                continue
            if k + 1 < len(path):
                c = path[k + 1]
                if c[0] == b[0] and (c[1] - b[1], c[2] - b[2]) == (b[1] - a[1], b[2] - a[2]):
                    continue
            segs.append((start, b))
            start = b
        for a, b in segs:
            if (a[1], a[2]) != (b[1], b[2]):
                self.add_track(net, ROUTE_LAYERS[a[0]], self.g.xy(a[2], a[1]), self.g.xy(b[2], b[1]), w)
        if end_via:
            e = path[-1]
            self.add_via(net, self.g.xy(e[2], e[1]))

    def route_stub(self, p):
        """GND SMD pad -> nearest legal via into the In1 plane (power width, signal width if that is blocked)."""
        nid = self.net_ids[GND]
        for cls, w in (('p', W_POWER), ('s', W_SIGNAL)):
            src = self.pad_cells(p, cls, nid)
            path = self.search(GND, src, [], cls, want_via_target=True) if src else None
            if path is not None:
                self.commit(GND, path, w, end_via=True)
                return []
        return [f"{GND}: {p['ref']}.{p['pad']} has no via site"]

    def route_net(self, net):
        nid = self.net_ids[net]
        pads = [p for p in self.pads if p['net'] == net]
        pads.sort(key=lambda p: (p['at'][1], p['at'][0], p['ref'], p['pad']))
        cells = {c: [self.pad_cells(p, c, nid) for p in pads] for c in ('p', 's')}
        tree = set(cells['s'][0])
        todo = list(range(1, len(pads)))
        fails = []
        while todo:
            path = None
            for cls, w in ((('p', W_POWER), ('s', W_SIGNAL)) if net in POWER else (('s', W_SIGNAL),)):
                targets = [c for k in todo for c in cells[cls][k]]
                pas = [self.passable(cls, l, nid, base=self.soft is not None) for l in ROUTE_LAYERS]
                src = sorted(c for c in tree if pas[c[0]][c[1], c[2]])
                if targets and src:
                    path = self.search(net, src, targets, cls)
                if path is not None:
                    break
            if path is None:
                fails.append(f"{net}: cannot reach {[pads[k]['ref'] + '.' + pads[k]['pad'] for k in todo]}")
                break
            self.commit(net, path, w)
            end = path[-1]
            hit = [k for k in todo if end in set(cells['s'][k]) or end in set(cells['p'][k])]
            for k in hit:
                todo.remove(k)
                tree |= set(cells['s'][k])
            tree |= set(path)
        return fails

    def route(self, item):
        self.item = item
        if item.startswith('stub:'):
            ref, pad = item[5:].split('.')
            return self.route_stub(next(p for p in self.pads if p['ref'] == ref and p['pad'] == pad))
        return self.route_net(item)

    def blockers(self, item):
        """Probe the item with other nets' copper made soft; return the items whose copper the probe crosses."""
        self.soft = []
        try:
            f = self.route(item)
            probe = self.soft
        finally:
            self.soft = None
        if f:
            return None
        net = item if not item.startswith('stub:') else GND
        hit = set()
        for t in self.tracks + self.vias:
            if t['net'] == net:
                continue
            for q in probe:
                if conflict(q, t):
                    hit.add(t['item'])
                    break
        return hit


def seg_seg(a, b, c, d):
    def pd(p, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = dx * dx + dy * dy
        t = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L))
        return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)

    def ccw(p, q, r):
        return (r[1] - p[1]) * (q[0] - p[0]) - (q[1] - p[1]) * (r[0] - p[0])
    if (ccw(a, c, d) > 0) != (ccw(b, c, d) > 0) and (ccw(a, b, c) > 0) != (ccw(a, b, d) > 0):
        return 0.0
    return min(pd(a, c, d), pd(b, c, d), pd(c, a, b), pd(d, a, b))


def shape(o):
    if 'layer' in o:
        return o['start'], o['end'], o['width'] / 2, {o['layer']}
    return o['at'], o['at'], o['size'] / 2, None


def conflict(p, q):
    a, b, rp, lp = shape(p)
    c, d, rq, lq = shape(q)
    if lp is not None and lq is not None and not (lp & lq):
        return False
    return seg_seg(a, b, c, d) < rp + rq + CLEAR + ROUTER_MARGIN


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--geometry', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--seed', type=int, default=0, help='0: nets by span; otherwise a seeded shuffle of the net order')
    a = ap.parse_args()
    geo = json.loads(a.geometry.read_text())
    counts = {}
    for p in geo['pads']:
        if p['net']:
            counts[p['net']] = counts.get(p['net'], 0) + 1
    stubs = [f"stub:{p['ref']}.{p['pad']}" for p in geo['pads'] if p['net'] == GND and not p['drill']]

    def span(n):
        pts = np.array([p['at'] for p in geo['pads'] if p['net'] == n])
        return float(np.ptp(pts[:, 0]) + np.ptp(pts[:, 1]))
    nets = sorted((n for n, c in counts.items() if c > 1 and n != GND), key=lambda n: (span(n), n))
    order = stubs + nets
    if a.seed:
        import random
        rnd = random.Random(a.seed)
        rnd.shuffle(nets)
        order = stubs + nets
    from collections import Counter, deque
    r = Router(geo)
    queue = deque(order)
    rips = Counter()
    log = []
    fails = []
    while queue:
        item = queue.popleft()
        f = r.route(item)
        if not f:
            continue
        r.remove({item})
        victims = r.blockers(item)
        if not victims or any(rips[v] >= MAX_RIPS for v in victims):
            fails += f
            log.append({'item': item, 'result': 'failed', 'blockers': sorted(victims or [])})
            print(f'FAIL {item}: {f} blockers {sorted(victims or [])}', file=sys.stderr)
            continue
        r.remove(victims)
        for v in sorted(victims):
            rips[v] += 1
        f = r.route(item)
        log.append({'item': item, 'result': 'ripped', 'victims': sorted(victims), 'rerouted': not f})
        print(f'rip {sorted(victims)} for {item}: {"ok" if not f else f}', file=sys.stderr)
        if f:
            r.remove({item})
            queue.append(item)
            rips[item] += 1
            if rips[item] > MAX_RIPS:
                fails += f
                queue.remove(item)
        queue.extend(sorted(victims))
    history = log
    out = {'generator': 'scripts/a7_route.py', 'seed': a.seed, 'pitch_mm': PITCH, 'router_margin_mm': ROUTER_MARGIN,
           'widths_mm': {'signal': W_SIGNAL, 'power': W_POWER}, 'via': {'size': VIA_D, 'drill': VIA_DRILL},
           'order': order, 'rip_log': history, 'tracks': r.tracks, 'vias': r.vias, 'failures': fails}
    a.out.write_text(json.dumps(out, indent=0) + '\n')
    print(json.dumps({'tracks': len(r.tracks), 'vias': len(r.vias), 'failures': fails}, indent=1))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
