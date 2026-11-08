#!/usr/bin/env python3
"""A7 schematic-phase check in the digest-pinned KiCad image.

Runs, fresh, on the committed A7 controller schematic:
  * native ERC (all severities; zero violations required),
  * KiCad XML netlist export,
  * schematic-to-PCB parity against an unrouted staging board generated into the
    (empty, outside-repo) output directory by `a7_electronics.py init-board`,
  * the behavioral interface assertions (A7 role map) and the authorized-delta
    check against the hash-pinned A5 baseline netlist.

Status words:
  FAIL                    any mechanical check, behavioral assertion or delta entry fails
  SCHEMATIC_UNREVIEWED    everything passes except the review gates (role map and delta
                          record have no independent review yet); exit 0
  SCHEMATIC_REVIEWED      everything passes including review records; exit 0

None of these is a board result: the board result comes only from the A7 revision
gate (native_gate.json) run on the committed candidate board.

Usage: python3 scripts/a7_schematic_check.py --out DIR [--evidence-dir engineering/a7/verification/schematic]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(REPO / 'scripts/native_gate'))
import authority  # noqa: E402
import delta  # noqa: E402
import interface  # noqa: E402

PROFILE = REPO / 'engineering/a7/verification/native_gate.json'
SCH = 'engineering/a7/electronics/controller/controller.kicad_sch'
STAGE_PCB = 'stage/engineering/a7/electronics/controller/controller.kicad_pcb'
A5_NL = REPO / 'engineering/a5/integration/native_schematic'
LABEL = 'zudo-led-block.a7-schematic'
EVIDENCE = 'engineering/a7/verification/schematic'
REVIEW_ONLY = {'interface': {'roles.reviewed'},
               'delta': {'authorized-delta record has no review entry; an unreviewed record cannot authorize anything'}}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def native(out: Path, image: str) -> dict:
    script = '\n'.join([
        'set -u',
        'kicad-cli version > /out/kicad_version.txt',
        f'kicad-cli sch erc --format json --severity-all --exit-code-violations -o /out/erc.json /repo/{SCH}; echo $? > /out/erc.code',
        f'kicad-cli sch export netlist --format kicadxml -o /out/netlist.xml /repo/{SCH}; echo $? > /out/netlist.code',
        'python3 -I /repo/scripts/a7_electronics.py init-board --out /out/stage --netlist /out/netlist.xml > /out/init_board.log 2>&1; echo $? > /out/init.code',
        f'kicad-cli pcb drc --schematic-parity --format json --severity-all -o /out/parity_drc.json /out/{STAGE_PCB}; echo $? > /out/drc.code',
    ])
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '2', '--memory', '4g', '--cap-drop', 'ALL',
           '--security-opt', 'no-new-privileges', '--label', LABEL, '-u', f'{os.getuid()}:{os.getgid()}', '-e', 'HOME=/tmp',
           '-e', 'PYTHONDONTWRITEBYTECODE=1', '-v', f'{REPO}:/repo:ro', '-v', f'{out}:/out', image, 'bash', '-c', script]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    codes = {k: (out / f'{k}.code').read_text().strip() if (out / f'{k}.code').is_file() else None
             for k in ('erc', 'netlist', 'init', 'drc')}
    return {'docker_exit': p.returncode, 'codes': codes, 'stderr_tail': p.stderr[-2000:]}


def evaluate(out: Path) -> dict:
    fails: list[str] = []
    review_pending: list[str] = []
    res: dict = {}
    try:
        erc = json.loads((out / 'erc.json').read_text())
        viol = [v for s in erc['sheets'] for v in s['violations']]
        res['erc_violations'] = len(viol)
        if viol:
            fails.append(f'ERC: {len(viol)} violations: {[v["type"] for v in viol][:10]}')
    except (OSError, ValueError, KeyError) as e:
        fails.append(f'ERC report unreadable: {e}')
    try:
        drc = json.loads((out / 'parity_drc.json').read_text())
        parity = drc.get('schematic_parity')
        if parity is None:
            fails.append('parity report has no schematic_parity section')
        else:
            res['parity_issues'] = len(parity)
            if parity:
                fails.append(f'schematic parity: {len(parity)} issues: {[v["description"] for v in parity][:5]}')
        res['staging_board_note'] = ('unrouted staging board at A5 placements; its DRC and unconnected counts are not '
                                     'a board result and are not evaluated')
    except (OSError, ValueError) as e:
        fails.append(f'parity report unreadable: {e}')
    nl = out / 'netlist.xml'
    if nl.is_file():
        roles = REPO / 'engineering/a7/verification/interface_roles/a7_controller.json'
        r = interface.check({'controller': nl, 'led_leaf': A5_NL / 'led_leaf/netlist.xml',
                             'power_adapter': A5_NL / 'power_adapter/netlist.xml'}, roles)
        (out / 'interface_check.json').write_text(json.dumps(r, indent=1) + '\n')
        bad = [c['id'] for c in r['checks'] if not c['passed']]
        res['interface'] = {'checks': len(r['checks']), 'failed': bad, 'errors': r['errors']}
        fails += [f'interface: {i}' for i in bad if i not in REVIEW_ONLY['interface']] + [f'interface: {e}' for e in r['errors']]
        review_pending += [f'interface: {i}' for i in bad if i in REVIEW_ONLY['interface']]
        committed = REPO / EVIDENCE / 'netlist.xml'
        if not committed.is_file() or delta.parse(committed) != delta.parse(nl):
            fails.append(f'committed evidence {EVIDENCE}/netlist.xml differs from the fresh export (re-run with --evidence-dir)')
        d = delta.check(REPO / 'engineering/a7/verification/authorized_delta.json', nl, REPO)
        (out / 'delta_check.json').write_text(json.dumps(d, indent=1) + '\n')
        res['delta'] = {'failures': d['failures'], 'observed': len(d.get('observed_delta', [])),
                        'replaced_refs': d.get('replaced_refs')}
        fails += [f'delta: {f}' for f in d['failures'] if f not in REVIEW_ONLY['delta']]
        review_pending += [f'delta: {f}' for f in d['failures'] if f in REVIEW_ONLY['delta']]
    else:
        fails.append('netlist.xml was not exported')
    status = 'FAIL' if fails else ('SCHEMATIC_UNREVIEWED' if review_pending else 'SCHEMATIC_REVIEWED')
    return {'status': status, 'failures': fails, 'review_pending': review_pending, **res}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--evidence-dir', type=Path)
    a = ap.parse_args()
    try:
        out = authority.require_empty_staging(a.out)
    except authority.Refused as r:
        print(f'refused: {r}', file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    prof = json.loads(PROFILE.read_text())
    gen = subprocess.run([sys.executable, 'scripts/a7_electronics.py', 'generate', '--check'], cwd=REPO,
                         capture_output=True, text=True)
    run = native(out, prof['image'])
    ev = evaluate(out)
    if gen.returncode != 0:
        ev['failures'].insert(0, f'derived A7 electronics stale: {gen.stderr.strip()}')
        ev['status'] = 'FAIL'
    if any(c != '0' for k, c in run['codes'].items() if k != 'drc') or run['codes'].get('drc') not in ('0', '5'):
        ev['failures'].insert(0, f'native step exit codes {run["codes"]}, docker exit {run["docker_exit"]}: {run["stderr_tail"][-500:]}')
        ev['status'] = 'FAIL'
    summary = {'status': ev.pop('status'), 'board_result': 'NONE (schematic phase; the board result comes from the A7 revision gate)',
               'image': prof['image'], 'kicad_version': (out / 'kicad_version.txt').read_text().strip()
               if (out / 'kicad_version.txt').is_file() else None,
               'schematic': SCH, 'schematic_sha256': sha(REPO / SCH), 'native': run, **ev}
    (out / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    if a.evidence_dir:
        dst = a.evidence_dir if a.evidence_dir.is_absolute() else REPO / a.evidence_dir
        for name in ('summary.json', 'erc.json', 'netlist.xml', 'interface_check.json', 'delta_check.json'):
            authority.check_writable(dst / name)
        dst.mkdir(parents=True, exist_ok=True)
        for name in ('summary.json', 'erc.json', 'netlist.xml', 'interface_check.json', 'delta_check.json'):
            if (out / name).is_file():
                shutil.copyfile(out / name, dst / name)
        parity = json.loads((out / 'parity_drc.json').read_text()) if (out / 'parity_drc.json').is_file() else {}
        (dst / 'parity.json').write_text(json.dumps({'source': 'kicad-cli pcb drc --schematic-parity on the unrouted staging board',
                                                     'kicad_version': parity.get('kicad_version'),
                                                     'schematic_parity': parity.get('schematic_parity')}, indent=1) + '\n')
    print(json.dumps({k: summary[k] for k in ('status', 'failures', 'review_pending')}, indent=1))
    return 1 if summary['status'] == 'FAIL' else 0


if __name__ == '__main__':
    sys.exit(main())
