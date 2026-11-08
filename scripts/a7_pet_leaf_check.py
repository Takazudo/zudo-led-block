#!/usr/bin/env python3
"""A7 bonded PET LED leaf: electrical profile and interface check (R4 item 5).

Checks the A5 leaf circuit and copper against engineering/a7/verification/pet_leaf/profile.json:
  1. interface: the reviewed role map assertions for controller J3, both SH4 harnesses and the leaf
     (scripts/native_gate/interface.py) on the committed A7 controller and A5 leaf/adapter netlists;
  2. mechanical: R2's 3HP PET export carries the PET leaf with no envelope or rigid-intersection finding;
  3. copper, in the digest-pinned KiCad image on a copy of the A5 leaf board in --out: pad types and layers,
     tracks per layer, vias, pad gaps per footprint, and a native DRC run with the JLC flex copper-to-edge
     rule added (plus a control run whose impossible edge rule must be reported, so a dropped rule fails);
  4. VLED/GND drop bound at the TPS2552 worst-case current limit on film copper.

Each verdict is PASS or NOT_MET; NOT_MET is a finding about the PET variant, not a failure of this check.
Status words: CHECKED (exit 0) when every step ran and every verdict equals the profile's recorded
'expected'; FAIL (exit 1) otherwise. CHECKED is not a PET approval and A7 is not released for manufacture.

Usage: python3 scripts/a7_pet_leaf_check.py --out DIR
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(REPO / 'scripts/native_gate'))
import interface  # noqa: E402

PROFILE = REPO / 'engineering/a7/verification/pet_leaf/profile.json'
GATE = REPO / 'engineering/a7/verification/native_gate.json'
LABEL = 'zudo-led-block.a7-pet-leaf-check'
CONTROL_EDGE_MM = 5.0  # wider than half the 9.0 mm leaf, so every copper item must be reported

PROBE_PY = r'''
import itertools, json, sys, pcbnew as p
b = p.LoadBoard(sys.argv[1]); mm = p.ToMM
tracks, vias, pads, gaps = [], [], [], {}
for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA':
        vias.append({'net': t.GetNetname(), 'diameter': mm(t.GetWidth(p.F_Cu)), 'drill': mm(t.GetDrillValue())})
    elif t.GetClass() == 'PCB_TRACK':
        tracks.append({'net': t.GetNetname(), 'layer': b.GetLayerName(t.GetLayer()), 'width': mm(t.GetWidth()),
                       'length': mm(t.GetLength())})
    else:
        raise SystemExit(f'unexpected track class {t.GetClass()}')
for f in b.GetFootprints():
    box = []
    for pd in f.Pads():
        bb = pd.GetBoundingBox()
        pads.append({'ref': f.GetReference(), 'pad': pd.GetNumber(), 'net': pd.GetNetname(),
                     'smd': pd.GetAttribute() == p.PAD_ATTRIB_SMD,
                     'layers': [b.GetLayerName(l) for l in pd.GetLayerSet().CuStack()]})
        box.append((pd.GetNumber(), mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())))
    g = []
    for a, c in itertools.combinations(box, 2):
        dx = max(0.0, max(a[1], c[1]) - min(a[3], c[3])); dy = max(0.0, max(a[2], c[2]) - min(a[4], c[4]))
        g.append([round((dx * dx + dy * dy) ** 0.5, 4), a[0], c[0]])
    gaps[f.GetReference()] = {'footprint': f.GetFPID().GetLibItemName().wx_str(), 'min_pad_gap': min(g) if g else None}
json.dump({'tracks': tracks, 'vias': vias, 'pads': pads, 'pad_gaps': gaps}, open(sys.argv[2], 'w'))
'''


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def dru(name: str, edge_mm: float) -> str:
    return f'(version 1)\n(rule "{name}"\n  (constraint edge_clearance (min {edge_mm}mm)))\n'


def docker(image: str, out: Path, script: str, timeout: int) -> subprocess.CompletedProcess:
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '2', '--memory', '4g', '--cap-drop', 'ALL',
           '--security-opt', 'no-new-privileges', '--label', LABEL, '-u', f'{os.getuid()}:{os.getgid()}', '-e', 'HOME=/tmp',
           '-e', 'PYTHONDONTWRITEBYTECODE=1', '-v', f'{REPO}:/repo:ro', '-v', f'{out}:/out', image, 'bash', '-c', script]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def drc_violations(path: Path) -> list[dict]:
    d = json.loads(path.read_text())
    return list(d.get('violations', [])) + list(d.get('unconnected_items', [])) + list(d.get('schematic_parity', []))


def rule_hits(violations: list[dict], rule: str) -> list[dict]:
    return [v for v in violations if f"rule '{rule}'" in v.get('description', '')]


def rilim_value(netlist: Path, ref: str) -> str | None:
    for c in ET.parse(netlist).getroot().iter('comp'):
        if c.get('ref') == ref:
            return (c.findtext('value') or '').strip()
    return None


def drop_bound(tracks: list[dict], nets: tuple[str, ...], current_a: float, copper_um: float, rho: float) -> float:
    """Series sum over every segment of the power and return nets: an upper bound on the leaf drop in volts."""
    rs = rho / (copper_um * 1e-6)
    return current_a * sum(rs * t['length'] / t['width'] for t in tracks if t['net'] in nets)


def verdicts(prof: dict, probe: dict, drc: dict) -> tuple[dict, dict]:
    r, facts, v = prof['rules'], {}, {}
    pads, tracks, vias = probe['pads'], probe['tracks'], probe['vias']
    if not pads or not tracks:
        raise ValueError('leaf copper probe is empty')
    facts['pads'] = len(pads)
    facts['non_smd_pads'] = [f"{p['ref']}.{p['pad']}" for p in pads if not p['smd']]
    facts['pad_layers'] = sorted({l for p in pads for l in p['layers']})
    v['smt_only'] = 'PASS' if not facts['non_smd_pads'] and facts['pad_layers'] == ['F.Cu'] else 'NOT_MET'
    by_layer: dict[str, int] = {}
    for t in tracks:
        by_layer[t['layer']] = by_layer.get(t['layer'], 0) + 1
    facts['tracks_per_layer'] = dict(sorted(by_layer.items()))
    facts['nets_off_f_cu'] = sorted({t['net'] for t in tracks if t['layer'] != 'F.Cu'})
    facts['vias'] = len(vias)
    one = prof['variants']['pet_1layer']['copper_layers']
    v['pet_1layer.copper'] = 'PASS' if not vias and set(by_layer) <= set(one) else 'NOT_MET'
    facts['min_track_mm'] = min(t['width'] for t in tracks)
    facts['board_min_clearance_mm'] = drc['board_min_clearance_mm']
    ok = facts['min_track_mm'] >= r['min_track_mm']['value'] and drc['board_min_clearance_mm'] >= max(
        r['min_clearance_mm']['value'], r['exposed_pad_to_track_mm'], r['via_ring_to_track_mm'])
    v['pet_2layer.track_and_clearance'] = 'PASS' if ok and drc['clean_under_board_rules'] else 'NOT_MET'
    facts['via_sizes'] = sorted({(x['diameter'], x['drill']) for x in vias})
    v['pet_2layer.vias'] = 'PASS' if all(d >= r['via_min_diameter_mm'] and h >= r['via_min_drill_mm'] and d - h >= 0.2 - 1e-9
                                         for d, h in facts['via_sizes']) else 'NOT_MET'
    facts['copper_to_edge_hits'] = drc['edge_hits']
    v['pet_2layer.copper_to_edge'] = 'PASS' if not drc['edge_hits'] else 'NOT_MET'
    dam = {}
    for ref, g in probe['pad_gaps'].items():
        if g['min_pad_gap'] is not None:
            bridge = round(g['min_pad_gap'][0] - 2 * r['coverlay_expansion_mm'], 4)
            if bridge < r['min_coverlay_bridge_mm']:
                dam[ref] = {'footprint': g['footprint'], 'min_pad_gap_mm': g['min_pad_gap'][0], 'coverlay_bridge_mm': bridge,
                            'pads': g['min_pad_gap'][1:]}
    facts['coverlay_bridges_removed'] = dam
    v['coverlay_bridges'] = 'PASS' if not dam else 'NOT_MET'
    return v, facts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    out = a.out.resolve()
    if out == REPO or REPO in out.parents:
        print('refusing: --out must be outside the repository', file=sys.stderr)
        return 2
    if out.exists() and any(out.iterdir()):
        print('refusing: --out must be empty or absent', file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    prof = json.loads(PROFILE.read_text())
    image = json.loads(GATE.read_text())['image']
    board = REPO / prof['reference']['board']
    fails: list[str] = []
    s: dict = {'what': 'A7 bonded PET leaf profile and interface check on the A5 leaf circuit and copper; not a PET '
                       'approval, not a leaf design, not a manufacturing release',
               'image': image, 'profile_sha256': sha(PROFILE), 'board_sha256': sha(board)}

    nl = {k: REPO / p for k, p in prof['interface']['netlists'].items()}
    r = interface.check(nl, REPO / prof['interface']['roles'])
    by_id = {c['id']: c['passed'] for c in r['checks']}
    missing = [i for i in prof['interface']['required_checks'] if by_id.get(i) is not True]
    s['interface'] = {'checks': len(r['checks']), 'required': prof['interface']['required_checks'], 'not_passed': missing,
                      'errors': r['errors'], 'netlist_sha256': {k: v['sha256'] for k, v in r['netlists'].items()}}
    found: dict = {'interface': 'PASS' if not missing and not r['errors'] else 'NOT_MET'}

    mv = json.loads((REPO / prof['mechanical']['verification']).read_text())
    bad = {k: mv.get(k) for k, want in prof['mechanical']['require'].items() if mv.get(k) != want}
    s['mechanical'] = {'verification': prof['mechanical']['verification'], 'mismatched': bad, 'status': mv.get('status'),
                       'selection': mv.get('selection')}
    found['mechanical'] = 'PASS' if not bad else 'NOT_MET'

    stem = board.stem
    rel = prof['reference']['board']
    root = prof['reference']['copy_root']
    if not rel.startswith(root + '/'):
        print('refusing: reference board is not under reference.copy_root', file=sys.stderr)
        return 2
    sub = str(Path(Path(root).name) / Path(rel).parent.relative_to(root))
    (out / 'probe.py').write_text(PROBE_PY)
    for d, rule, edge in (('leaf', 'pet_copper_edge', prof['rules']['copper_to_edge_mm']),
                          ('control', 'pet_copper_edge_control', CONTROL_EDGE_MM)):
        (out / d / sub).mkdir(parents=True)
        (out / d / sub / f'{stem}.kicad_dru').write_text(dru(rule, edge))
    pro = rel[:-len('.kicad_pcb')] + '.kicad_pro'
    script = ['set -u']
    for d in ('leaf', 'control'):
        # the whole A5 electronics tree is copied so the board's ${KIPRJMOD}-relative footprint library resolves
        script.append(f'cp -r /repo/{root} /out/{d}/ && kicad-cli pcb drc --format json --severity-all --units mm'
                      f' --output /out/{d}/drc.json /out/{d}/{sub}/{stem}.kicad_pcb > /out/{d}.log 2>&1; echo $? > /out/{d}.code')
    script.append(f'python3 -I /out/probe.py /repo/{rel} /out/probe.json > /out/probe.log 2>&1; echo $? > /out/probe.code')
    p = docker(image, out, '\n'.join(script), 600)
    codes = {k: (out / f'{k}.code').read_text().strip() if (out / f'{k}.code').is_file() else None
             for k in ('leaf', 'control', 'probe')}
    s['native'] = {'docker_exit': p.returncode, 'codes': codes, 'stderr_tail': p.stderr[-1000:]}
    if p.returncode != 0 or any(c != '0' for c in codes.values()):
        fails.append(f'native steps failed: docker exit {p.returncode}, codes {codes}')
    for d in ('leaf', 'control'):
        if not (out / d / 'drc.json').is_file():
            fails.append(f'no DRC report for {d}')
    if not (out / 'probe.json').is_file():
        fails.append('no copper probe from the KiCad image')

    if not fails:
        leaf_v = drc_violations(out / 'leaf/drc.json')
        ctrl_v = drc_violations(out / 'control/drc.json')
        edge = rule_hits(leaf_v, 'pet_copper_edge')
        other = [x for x in leaf_v if x not in edge]
        ctrl = rule_hits(ctrl_v, 'pet_copper_edge_control')
        s['drc'] = {'pet_copper_edge_hits': len(edge), 'other_violations': len(other),
                    'other_examples': [x.get('description') for x in other[:5]],
                    'control_hits': len(ctrl)}
        if not ctrl:
            fails.append('control: an impossible pet_copper_edge_control rule was not reported, so the custom rule file '
                         'is not applied')
        rules = json.loads((REPO / pro).read_text())['board']['design_settings']['rules']
        probe = json.loads((out / 'probe.json').read_text())
        try:
            v, facts = verdicts(prof, probe, {'board_min_clearance_mm': rules['min_clearance'],
                                              'clean_under_board_rules': not other,
                                              'edge_hits': [re.sub(r'\s+', ' ', x.get('description', '')) for x in edge][:10]})
        except (KeyError, ValueError) as e:
            fails.append(f'copper evaluation: {e}')
            v, facts = {}, {}
        found.update(v)
        s['copper'] = facts
        cb = prof['current_bound']
        current = 22980 / cb['rilim_kohm'] ** 0.94 / 1000
        rho = prof['copper_resistivity_ohm_m']['value']
        power = tuple(n for n in ('VLED', 'GND') if any(t['net'] == n for t in probe['tracks']))
        if power != ('VLED', 'GND'):
            fails.append(f'leaf power nets not found on copper: {power}')
        s['vled_drop_bound'] = {
            'current_bound_a': round(current, 4), 'nets': list(power),
            'mv_by_copper_um': {str(c): round(drop_bound(probe['tracks'], power, current, c, rho) * 1000, 1)
                                for c in (12, 18, 35)},
            'note': 'series sum of every VLED and GND segment on the leaf at the TPS2552 IOSmax bound: an upper bound, '
                    'not a layout result; connector contact and harness resistance not included'}
        val = rilim_value(nl['controller'], cb['rilim_ref'])
        s['vled_drop_bound']['rilim_value'] = val
        if not (val or '').startswith(f"{cb['rilim_kohm']}k"):
            fails.append(f"{cb['rilim_ref']} is {val!r} in the controller netlist, not {cb['rilim_kohm']}k")

    s['verdicts'] = found
    exp = {k: v for k, v in prof['expected'].items() if k != 'note'}
    drift = {k: {'expected': exp.get(k), 'found': found.get(k)} for k in sorted(set(exp) | set(found)) if exp.get(k) != found.get(k)}
    s['drift_from_profile'] = drift
    if drift and not fails:
        fails.append(f'verdicts differ from the profile expected values: {drift}')
    s['open'] = prof['open']
    s['failures'] = fails
    s['status'] = 'FAIL' if fails else 'CHECKED'
    (out / 'summary.json').write_text(json.dumps(s, indent=1) + '\n')
    print(json.dumps({k: s[k] for k in ('status', 'failures', 'verdicts')}, indent=1))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
