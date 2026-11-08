#!/usr/bin/env python3
"""Fail-closed evaluator for the revision-agnostic native KiCad gate.

Ported from scripts/a6_native_eval.py at PR #14 head 7e96380be4fbea2bfcc4a5bd1d5721272a5a141f
(sha256 3e7ec0b1d99702aa4d6b6051384b24840f33a67ab773d139beca4619977f4b96); see
scripts/native_gate/PROVENANCE.md for what changed.

Pure functions over the raw files written by scripts/native_gate/inner.py. Every
check raises or records a failure explicitly; nothing relies on `assert`, so
`python3 -O` evaluates identically. Anything missing, malformed, unexpected or
outside the reviewed expectations is a failure. Raw reports are never edited;
dispositions live in the gate profile's expectations file.
"""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

# kicad-cli exit codes: 0 = clean, 5 = violations reported (--exit-code-violations).
KNOWN_EXIT = {'erc': {0, 5}, 'netlist': {0}, 'drc': {0, 5}}
REQUIRED_DRC_KEYS = ('violations', 'unconnected_items', 'schematic_parity', 'ignored_checks',
                     'included_severities', 'kicad_version')
NET_CONFLICT_RE = re.compile(r"^Pad net \((.*)\) doesn't match net given by schematic \((.*)\)$")
NC_RE = re.compile(r"^Pad missing net given by schematic \(unconnected-\(.*\)\)$")
FIELD_RE = re.compile(r"^Missing symbol field '([^']+)' in footprint$")
REF_RE = re.compile(r'(?:Footprint|of) ([A-Z]+[0-9]+)')
DESC_REF_RE = re.compile(r'\b([A-Z]{1,3}[0-9]{1,3})\b')
BYPRODUCT_SUFFIX = '.kicad_prl'  # kicad-cli writes local view settings next to the project


class Fail(Exception):
    pass


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_json(p: Path) -> dict:
    if not p.is_file() or p.is_symlink():
        raise Fail(f'missing report {p.name}')
    try:
        v = json.loads(p.read_text())
    except (ValueError, UnicodeDecodeError) as e:
        raise Fail(f'malformed report {p.name}: {e}') from None
    if not isinstance(v, dict):
        raise Fail(f'malformed report {p.name}: not an object')
    return v


def norm_net(n: str | None) -> str:
    if not n:
        return ''
    return n[1:] if n.startswith('/') else n


def check_op(name: str, op: dict | None, fails: list[str]) -> None:
    if not isinstance(op, dict):
        fails.append(f'{name}: no execution record'); return
    if op.get('timed_out') is not False:
        fails.append(f'{name}: timed out or timeout state unknown'); return
    code = op.get('exit_code')
    if type(code) is not int or code not in KNOWN_EXIT[name]:
        fails.append(f'{name}: unknown exit code {code!r}')
    if op.get('stdout_truncated') or op.get('stderr_truncated'):
        fails.append(f'{name}: log exceeded cap')


def erc_violations(erc: dict) -> list[dict]:
    sheets = erc.get('sheets')
    if not isinstance(sheets, list) or not sheets:
        raise Fail('erc.json: no sheets')
    out = []
    for s in sheets:
        v = s.get('violations')
        if not isinstance(v, list):
            raise Fail('erc.json: sheet without violations list')
        out += v
    return out


def parse_netlist(p: Path) -> tuple[dict, dict]:
    """Return ({ref: fields}, {(ref, pin): net}) from a KiCad XML netlist."""
    if not p.is_file() or p.is_symlink():
        raise Fail('missing netlist.xml')
    try:
        root = ET.parse(p).getroot()
    except ET.ParseError as e:
        raise Fail(f'malformed netlist.xml: {e}') from None
    comps = {}
    for c in root.iter('comp'):
        fields = {f.get('name'): (f.text or '') for f in c.iter('field')}
        comps[c.get('ref')] = {'footprint': (c.findtext('footprint') or ''), 'fields': fields,
                               'value': c.findtext('value') or ''}
    pins = {}
    for n in root.iter('net'):
        for node in n.iter('node'):
            key = (node.get('ref'), node.get('pin'))
            if key in pins:
                raise Fail(f'netlist.xml: pin {key[0]}.{key[1]} exported on more than one net')
            pins[key] = n.get('name')
    if not comps or not pins:
        raise Fail('netlist.xml: no components or nets')
    return comps, pins


def is_single_pin_net(net: str, pins: dict) -> bool:
    """KiCad names a no-connect pin's net 'unconnected-(...)'; a board may leave that pad unnamed."""
    return net.startswith('unconnected-(') and sum(1 for v in pins.values() if v == net) == 1


def independent_parity(comps: dict, pins: dict, facts: dict, extra_allowed: set[str]) -> list[str]:
    """Schematic/PCB correspondence computed without trusting KiCad's parity report."""
    errs = []
    pad_nets = facts.get('pad_nets')
    if not isinstance(pad_nets, dict) or not pad_nets:
        return ['board facts: no pad nets']
    board_only = set(facts.get('board_only', []))
    for ref in sorted(comps):
        if ref not in pad_nets:
            errs.append(f'{ref}: in schematic, not on board')
    for ref in sorted(pad_nets):
        if ref not in comps and ref not in board_only and ref not in extra_allowed:
            errs.append(f'{ref}: on board, not in schematic')
    for (ref, pin), net in sorted(pins.items()):
        bn = pad_nets.get(ref, {}).get(pin)
        if ref in pad_nets and bn is None:
            errs.append(f'{ref}.{pin}: schematic pin has no board pad')
        elif ref in pad_nets and norm_net(bn) != norm_net(net) and not (bn == '' and is_single_pin_net(net, pins)):
            errs.append(f'{ref}.{pin}: board net {bn!r} != schematic net {net!r}')
    for ref, pads in sorted(pad_nets.items()):
        if ref not in comps:
            continue
        for num, bn in sorted(pads.items()):
            if (ref, num) not in pins and bn:
                errs.append(f'{ref}.{num}: board net {bn!r} on a pin the schematic leaves unconnected')
    return errs


def item_refs(v: dict) -> list[str]:
    refs = []
    for it in v.get('items', []):
        refs += DESC_REF_RE.findall(it.get('description', ''))
    return sorted(set(refs))


def classify_parity(item: dict, allowed: dict) -> str | None:
    """Return the reviewed class an item belongs to, or None if not dispositioned."""
    t, d = item.get('type'), item.get('description', '')
    if t == 'net_conflict' and allowed.get('net_prefix_only'):
        m = NET_CONFLICT_RE.match(d)
        if m and m.group(2) == '/' + m.group(1):
            return 'net_prefix_only'
    if t == 'net_conflict' and allowed.get('no_connect_unnamed'):
        m = NC_RE.match(d)
        if m:
            return 'no_connect_unnamed'
    if t == 'footprint_symbol_field_mismatch':
        m = FIELD_RE.match(d)
        if m and m.group(1) in allowed.get('missing_fields', []):
            return 'missing_field'
    if t == 'extra_footprint':
        refs = item_refs(item)
        if refs and set(refs) <= set(allowed.get('extra_footprints', [])):
            return 'extra_footprint'
    return None


def match_residual(v: dict, residuals: list[dict]) -> dict | None:
    refs = item_refs(v)
    for r in residuals:
        if r.get('type') == v.get('type') and sorted(r.get('refs', [])) == refs:
            return r
    return None


def evaluate_design(name: str, exp: dict, rec: dict | None, out: Path, expected_inputs: dict) -> dict:
    """Evaluate one design. Returns {'ok': bool, 'failures': [...], 'facts': {...}}."""
    fails: list[str] = []
    facts: dict = {}
    if not isinstance(rec, dict):
        return {'ok': False, 'failures': [f'{name}: no inner record'], 'facts': facts}
    ops = rec.get('ops', {})
    for op in ('erc', 'netlist', 'drc'):
        check_op(op, ops.get(op), fails)
    if rec.get('deadline_exceeded') is not False:
        fails.append('design deadline exceeded or unknown')
    before, after = rec.get('stage_before'), rec.get('stage_after')
    if not isinstance(before, dict) or not isinstance(after, dict):
        fails.append('stage hashes missing')
    else:
        for fn, h in expected_inputs.items():
            if before.get(fn) != h:
                fails.append(f'staged input {fn} hash {before.get(fn)} != manifest {h}')
        for fn in sorted(set(before) | set(after)):
            if before.get(fn) == after.get(fn):
                continue
            if fn.endswith(BYPRODUCT_SUFFIX) and fn not in expected_inputs:
                continue
            fails.append(f'unexpected write to staged file {fn}')
        for fn in before:
            if fn not in expected_inputs and not fn.endswith(BYPRODUCT_SUFFIX):
                fails.append(f'unexpected staged file {fn}')
    try:
        erc = load_json(out / 'erc.json')
        ev = erc_violations(erc)
        facts['erc_violations'] = len(ev)
        if len(ev) > exp.get('erc_violations_max', 0):
            fails.append(f'ERC: {len(ev)} violations')
        if 'kicad_version' in erc and erc['kicad_version'] != exp['kicad_version']:
            fails.append(f"ERC kicad_version {erc['kicad_version']}")
        code = ops.get('erc', {}).get('exit_code')
        if (code == 0) != (len(ev) == 0):
            fails.append(f'ERC exit code {code} inconsistent with {len(ev)} violations')
    except Fail as e:
        fails.append(str(e))
    try:
        drc = load_json(out / 'drc.json')
        for k in REQUIRED_DRC_KEYS:
            if k not in drc:
                raise Fail(f'drc.json: missing key {k}')
        if drc['kicad_version'] != exp['kicad_version']:
            fails.append(f"DRC kicad_version {drc['kicad_version']} != {exp['kicad_version']}")
        if sorted(drc['included_severities']) != sorted(exp['included_severities']):
            fails.append(f"DRC severities {drc['included_severities']}")
        if sorted(drc['ignored_checks'], key=lambda x: x.get('key', '')) != sorted(exp['ignored_checks'], key=lambda x: x.get('key', '')):
            fails.append('DRC ignored-check set differs from the recorded expectation')
        residuals = exp.get('drc_residuals', [])
        matched = []
        for v in drc['violations']:
            r = match_residual(v, residuals)
            if r is None:
                fails.append(f"DRC {v.get('type')}: {v.get('description')} {item_refs(v)}")
            else:
                matched.append(r['id'])
        for r in residuals:
            if r['id'] not in matched:
                fails.append(f"expected residual {r['id']} not reported (stale disposition)")
        unc = len(drc['unconnected_items'])
        facts.update({'drc_violations': len(drc['violations']), 'drc_residuals_matched': sorted(matched),
                      'unconnected': unc, 'parity_items': len(drc['schematic_parity'])})
        if unc != 0:
            fails.append(f'DRC: {unc} unconnected items')
        classes: dict = {}
        for it in drc['schematic_parity']:
            c = classify_parity(it, exp.get('parity_dispositions', {}))
            if c is None:
                fails.append(f"parity {it.get('type')}: {it.get('description')} {item_refs(it)}")
            else:
                classes[c] = classes.get(c, 0) + 1
        facts['parity_classes'] = classes
        if exp.get('parity_counts') is not None and classes != exp['parity_counts']:
            fails.append(f"parity classes {classes} != reviewed {exp['parity_counts']}")
        code = ops.get('drc', {}).get('exit_code')
        clean = not drc['violations'] and not unc and not drc['schematic_parity']
        if (code == 0) != clean:
            fails.append(f'DRC exit code {code} inconsistent with report contents')
    except Fail as e:
        fails.append(str(e))
    try:
        bf = load_json(out / 'board_facts.json')
        if 'error' in bf:
            raise Fail(f"board facts error {bf['error']}")
        facts['unconnected_pcbnew'] = bf.get('unconnected_pcbnew')
        if bf.get('unconnected_pcbnew') != 0:
            fails.append(f"pcbnew connectivity: {bf.get('unconnected_pcbnew')} unconnected")
        if sorted(bf.get('board_only', [])) != sorted(exp.get('board_only', [])):
            fails.append(f"board-only footprints {bf.get('board_only')} != {exp.get('board_only', [])}")
        comps, pins = parse_netlist(out / 'netlist.xml')
        perr = independent_parity(comps, pins, bf, set(exp.get('parity_dispositions', {}).get('extra_footprints', [])))
        facts['independent_parity_errors'] = len(perr)
        fails += [f'parity(independent): {e}' for e in perr]
        facts['geometry_sha256'] = bf.get('geometry_sha256')
        facts['zone_fill_sha256'] = bf.get('zone_fill_sha256')
        if exp.get('refill_check'):
            rf = load_json(out / 'refill.json')
            if 'error' in rf:
                raise Fail(f"refill error {rf['error']}")
            if rf.get('geometry_sha256') != bf.get('geometry_sha256'):
                fails.append('zone refill changed board geometry')
            if rf.get('zone_fill_sha256') != bf.get('zone_fill_sha256'):
                fails.append('committed zone fills are stale (refill differs)')
            if rf.get('unconnected_pcbnew') != 0:
                fails.append('unconnected after refill')
    except Fail as e:
        fails.append(str(e))
    for k in ('erc.json', 'drc.json', 'netlist.xml', 'board_facts.json'):
        p = out / k
        if p.is_file():
            facts.setdefault('report_sha256', {})[k] = sha256(p)
    return {'ok': not fails, 'failures': fails, 'facts': facts}


def evaluate_expected_failure(exp: dict, rec: dict | None, out: Path) -> dict:
    """The untouched A5 controller must fail in exactly the recorded way."""
    fails = []
    if not isinstance(rec, dict):
        return {'ok': False, 'failures': ['no inner record']}
    # ERC/netlist ops are checked too: this design's fresh netlist feeds the interface and delta checks
    for op in ('erc', 'netlist', 'drc'):
        check_op(op, rec.get('ops', {}).get(op), fails)
    try:
        drc = load_json(out / 'drc.json')
        got = sorted([v.get('type'), item_refs(v)] for v in drc.get('violations', []))
        want = sorted([v['type'], sorted(v['refs'])] for v in exp['violations'])
        if got != want:
            fails.append(f'violations {got} != expected {want}')
        if len(drc.get('unconnected_items', [])) != exp['unconnected']:
            fails.append(f"unconnected {len(drc.get('unconnected_items', []))} != {exp['unconnected']}")
        if rec['ops']['drc'].get('exit_code') != 5:
            fails.append('expected-failure board did not return the violation exit code')
    except (Fail, KeyError, TypeError) as e:
        fails.append(str(e))
    return {'ok': not fails, 'failures': fails}


def check_versions(inner: dict, want: str) -> list[str]:
    f = []
    if inner.get('pcbnew_version') != want:
        f.append(f"pcbnew version {inner.get('pcbnew_version')!r} != {want}")
    v = inner.get('kicad_cli_version') or {}
    if v.get('exit_code') != 0 or (v.get('stdout') or '').strip() != want:
        f.append(f"kicad-cli version {(v.get('stdout') or '').strip()!r} != {want}")
    return f
