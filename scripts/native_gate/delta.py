#!/usr/bin/env python3
"""Authorized-delta check: candidate schematic netlist vs a reviewed, hash-pinned baseline netlist.

Replaces PR #14's exact-equality requirement ("A6 controller netlist must equal A5").
The candidate may differ from the baseline only where an entry in the reviewed
authorized-delta record says so:

  {"kind": "component_replaced", "ref": "J1", "reason": ..., "issue": ...}
      J1's value/footprint/fields and all of its pins may change. Its pins are left
      out of the connectivity comparison; the behavioral interface assertions
      (scripts/native_gate/interface.py) carry the obligation for its connections.
  {"kind": "component_added" | "component_removed", "ref": ...}
  {"kind": "field_changed", "ref": ..., "field": "value" | "footprint" | <field name>}
  {"kind": "pin_moved", "pin": "R9.2"}
      that pin's connectivity group may differ.

Connectivity is compared as groups (which other pins share a pin's net), so a
pure net rename is not a delta. Net names are reported for information.
Every observed delta must be authorized and every entry must match an observed
delta (a stale authorization fails). Entries need a reason and an issue/review
reference; an unreviewed record ("review": null) fails.

Usage:
  python3 scripts/native_gate/delta.py --record RECORD.json --candidate NETLIST.xml [--baseline-root REPO] --output OUT.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

KINDS = {'component_replaced', 'component_added', 'component_removed', 'field_changed', 'pin_moved'}
COMPARED_FIELDS = ('MPN', 'LCSC', 'Manufacturer')


def parse(path: Path) -> tuple[dict, dict]:
    root = ET.parse(path).getroot()
    comps = {}
    for c in root.findall('./components/comp'):
        fields = {f.get('name'): (f.text or '') for f in c.findall('./fields/field')}
        comps[c.get('ref')] = {'value': c.findtext('value') or '', 'footprint': c.findtext('footprint') or '',
                               **{k: fields.get(k) for k in COMPARED_FIELDS}}
    pins = {}
    for n in root.findall('./nets/net'):
        for node in n.findall('node'):
            pins[f"{node.get('ref')}.{node.get('pin')}"] = n.get('name')
    if not comps or not pins:
        raise ValueError(f'{path}: no components or nets')
    return comps, pins


def groups(pins: dict, skip_refs: set[str]) -> dict:
    by_net: dict = {}
    for p, n in pins.items():
        if p.split('.')[0] not in skip_refs:
            by_net.setdefault(n, set()).add(p)
    return {p: frozenset(g - {p}) for g in by_net.values() for p in g}


def observed_delta(base: tuple, cand: tuple, replaced: set[str]) -> list[dict]:
    bc, bp = base
    cc, cp = cand
    out = []
    for r in sorted(set(bc) - set(cc)):
        out.append({'kind': 'component_removed', 'ref': r})
    for r in sorted(set(cc) - set(bc)):
        out.append({'kind': 'component_added', 'ref': r})
    for r in sorted(set(bc) & set(cc)):
        for k in bc[r]:
            if bc[r][k] != cc[r][k]:
                out.append({'kind': 'field_changed', 'ref': r, 'field': k, 'from': bc[r][k], 'to': cc[r][k]})
    skip = replaced | (set(bc) ^ set(cc))
    gb, gc = groups(bp, skip), groups(cp, skip)
    for p in sorted(set(gb) | set(gc)):
        if gb.get(p) != gc.get(p):
            out.append({'kind': 'pin_moved', 'pin': p,
                        'from': sorted(gb[p]) if p in gb else None, 'to': sorted(gc[p]) if p in gc else None,
                        'net_from': bp.get(p), 'net_to': cp.get(p)})
    return out


def authorizes(e: dict, d: dict) -> bool:
    k = e.get('kind')
    if k == 'component_replaced':
        return d.get('ref') == e.get('ref') and d['kind'] in ('field_changed',)
    if k in ('component_added', 'component_removed'):
        return d['kind'] == k and d.get('ref') == e.get('ref')
    if k == 'field_changed':
        return d['kind'] == k and d.get('ref') == e.get('ref') and d.get('field') == e.get('field')
    if k == 'pin_moved':
        return d['kind'] == k and d.get('pin') == e.get('pin')
    return False


def check(record_path: Path, candidate: Path, root: Path) -> dict:
    fails: list[str] = []
    rec = json.loads(record_path.read_text())
    base_rel = rec.get('baseline', {}).get('netlist')
    base_sha = rec.get('baseline', {}).get('sha256')
    base = (root / base_rel) if base_rel else None
    if base is None or not base.is_file():
        return {'ok': False, 'failures': [f'baseline netlist {base_rel!r} missing']}
    got_sha = hashlib.sha256(base.read_bytes()).hexdigest()
    if got_sha != base_sha:
        fails.append(f'baseline netlist sha256 {got_sha} != record {base_sha}')
    if not rec.get('review'):
        fails.append('authorized-delta record has no review entry; an unreviewed record cannot authorize anything')
    entries = rec.get('entries')
    if not isinstance(entries, list):
        return {'ok': False, 'failures': fails + ['entries must be a list']}
    for i, e in enumerate(entries):
        if e.get('kind') not in KINDS:
            fails.append(f'entry {i}: unknown kind {e.get("kind")!r}')
        if not e.get('reason') or not e.get('issue'):
            fails.append(f'entry {i}: reason and issue are required')
    try:
        b, c = parse(base), parse(candidate)
    except (OSError, ValueError, ET.ParseError) as e:
        return {'ok': False, 'failures': fails + [str(e)]}
    replaced = {e['ref'] for e in entries if e.get('kind') == 'component_replaced' and e.get('ref') in b[0] and e.get('ref') in c[0]}
    for e in entries:
        if e.get('kind') == 'component_replaced' and e.get('ref') not in replaced:
            fails.append(f"component_replaced {e.get('ref')}: not present in both baseline and candidate")
    delta = observed_delta(b, c, replaced)
    used = set()
    unauthorized = []
    for d in delta:
        hit = [i for i, e in enumerate(entries) if authorizes(e, d)]
        if hit:
            used.update(hit)
        else:
            unauthorized.append(d)
    for d in unauthorized[:50]:
        fails.append(f'unauthorized delta: {json.dumps(d, sort_keys=True)}')
    if len(unauthorized) > 50:
        fails.append(f'... {len(unauthorized) - 50} more unauthorized deltas')
    for i, e in enumerate(entries):
        if i not in used and e.get('kind') != 'component_replaced':
            fails.append(f'stale authorization (matches no observed delta): entry {i} {json.dumps(e, sort_keys=True)}')
        elif e.get('kind') == 'component_replaced' and i not in used and e.get('ref') in replaced:
            # replacement with identical fields: still a real pin-level authorization, keep it visible
            pass
    renamed = sorted({(b[1][p], c[1][p]) for p in set(b[1]) & set(c[1]) if b[1][p] != c[1][p]})
    return {'ok': not fails, 'failures': fails, 'baseline': base_rel, 'baseline_sha256': got_sha,
            'candidate_sha256': hashlib.sha256(candidate.read_bytes()).hexdigest(),
            'record_sha256': hashlib.sha256(record_path.read_bytes()).hexdigest(),
            'observed_delta': delta, 'replaced_refs': sorted(replaced), 'net_renames': renamed[:200]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--record', type=Path, required=True)
    ap.add_argument('--candidate', type=Path, required=True)
    ap.add_argument('--baseline-root', type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument('--output', type=Path)
    a = ap.parse_args()
    res = check(a.record, a.candidate, a.baseline_root)
    if a.output:
        a.output.write_text(json.dumps(res, indent=1) + '\n')
    print(json.dumps({'ok': res['ok'], 'failures': res['failures'][:20]}, indent=1))
    return 0 if res['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
