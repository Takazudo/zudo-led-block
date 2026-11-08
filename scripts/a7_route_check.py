#!/usr/bin/env python3
"""A7 controller router reproducibility check, optionally with a review-aid fabrication preview.

Runs fresh from the committed inputs, in an empty output directory outside the repository:
  1. `a7_board.py build` in the digest-pinned KiCad image: unrouted staging board and pad geometry
     from the committed placement and the committed schematic netlist;
  2. `a7_route.py --seed 0` on that geometry; the proposal must equal
     engineering/a7/verification/routing/route_proposal_seed0.json byte for byte;
  3. the committed authoritative board's tracks and vias must be exactly the proposal's
     (as multisets, compared at KiCad's 1 nm resolution), so the board carries the recorded route.

With --review-aid it also exports Gerbers, drill files and a component position file of the committed
board into <out>/review-aid/. Those files are a review aid only: they are not release outputs, were
not checked against a fabricator's DFM, and A7 is not released for manufacture.

Status words: PASS (exit 0) or FAIL (exit 1). PASS says only that the recorded route is reproducible
and is what the board carries; the board result itself comes from the native gate.

Usage: python3 scripts/a7_route_check.py --out DIR [--review-aid]
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
PROFILE = REPO / 'engineering/a7/verification/native_gate.json'
PROPOSAL = 'engineering/a7/verification/routing/route_proposal_seed0.json'
BOARD = 'engineering/a7/electronics/controller/controller.kicad_pcb'
NETLIST = 'engineering/a7/verification/schematic/netlist.xml'
LABEL = 'zudo-led-block.a7-route-check'
REVIEW_AID_NOTE = """REVIEW AID ONLY - NOT A RELEASE OUTPUT - DO NOT ORDER FROM THESE FILES

Exported by scripts/a7_route_check.py --review-aid from the committed A7 controller board
(board sha256 {sha}) with the pinned KiCad image, for a DFM preview by reviewers.

- A7 is not released for manufacture: physical gates in issue #19 are open (PJ-324M continuity,
  slots and axis height, PCM13SMTR fit, stock, pogo-jig).
- These files were not checked against any fabricator's DFM, and no fabrication notes, stackup
  drawing or panelization are included.
- The Gerber job file (.gbrjob) is removed on purpose, so the set cannot be imported for ordering in one step.
- They are regenerated on every CI run and are not tracked in the repository.
"""

# runs inside the KiCad image: board copper and the recorded proposal, both in KiCad internal units (integer nm).
# The proposal's mm values go through pcbnew.FromMM, the same conversion a7_board.py apply used to write the board.
COPPER_PY = r'''
import json, sys, pcbnew as p
b = p.LoadBoard(sys.argv[1])
tracks, vias = [], []
for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA':
        vias.append([t.GetNetname(), t.GetPosition().x, t.GetPosition().y, t.GetWidth(p.F_Cu), t.GetDrillValue()])
    elif t.GetClass() == 'PCB_TRACK':
        a, e = (t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y)
        tracks.append([t.GetNetname(), b.GetLayerName(t.GetLayer()), *min(a, e), *max(a, e), t.GetWidth()])
    else:
        raise SystemExit(f'unexpected track class {t.GetClass()}')
r = json.load(open(sys.argv[2]))
f = p.FromMM
pt = []
for t in r['tracks']:
    a, e = (f(t['start'][0]), f(t['start'][1])), (f(t['end'][0]), f(t['end'][1]))
    pt.append([t['net'], t['layer'], *min(a, e), *max(a, e), f(t['width'])])
pv = [[v['net'], f(v['at'][0]), f(v['at'][1]), f(v['size']), f(v['drill'])] for v in r['vias']]
json.dump({'board': {'tracks': tracks, 'vias': vias}, 'proposal': {'tracks': pt, 'vias': pv}}, open(sys.argv[3], 'w'))
'''


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def docker(image: str, out: Path, script: str, timeout: int) -> subprocess.CompletedProcess:
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '2', '--memory', '4g', '--cap-drop', 'ALL',
           '--security-opt', 'no-new-privileges', '--label', LABEL, '-u', f'{os.getuid()}:{os.getgid()}', '-e', 'HOME=/tmp',
           '-e', 'PYTHONDONTWRITEBYTECODE=1', '-v', f'{REPO}:/repo:ro', '-v', f'{out}:/out', image, 'bash', '-c', script]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def copper_diff(board: dict, proposal: dict) -> dict:
    """Exact multiset comparison of tracks and vias (net, layer, endpoints, width / position, size, drill in nm)."""
    out = {}
    for name in ('tracks', 'vias'):
        bc = collections.Counter(tuple(x) for x in board[name])
        pc = collections.Counter(tuple(x) for x in proposal[name])
        out[name] = {'board': sum(bc.values()), 'proposal': sum(pc.values()),
                     'only_on_board': [list(map(str, k)) for k in sorted((bc - pc).elements())][:10],
                     'only_in_proposal': [list(map(str, k)) for k in sorted((pc - bc).elements())][:10]}
        out[name]['equal'] = bc == pc
    return out


def nonempty_failures(proposal: dict, copper: dict) -> list[str]:
    """An empty or failed route must not pass as 'board equals proposal' (empty equals empty)."""
    fails = []
    if proposal.get('failures') != []:
        fails.append(f"recorded proposal has router failures: {proposal.get('failures')!r}")
    for side in ('board', 'proposal'):
        for name in ('tracks', 'vias'):
            if not copper.get(side, {}).get(name):
                fails.append(f'{side} has no {name}')
    return fails


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--review-aid', action='store_true')
    a = ap.parse_args()
    out = a.out.resolve()
    if out == REPO or REPO in out.parents:
        print('refusing: --out must be outside the repository', file=sys.stderr)
        return 2
    if out.exists() and any(out.iterdir()):
        print('refusing: --out must be empty or absent', file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    image = json.loads(PROFILE.read_text())['image']
    fails: list[str] = []
    s: dict = {'what': 'A7 router reproducibility (seed 0) and board copper vs. the recorded route; not a board result',
               'image': image, 'board_sha256': sha(REPO / BOARD), 'proposal_sha256': sha(REPO / PROPOSAL)}
    (out / 'copper.py').write_text(COPPER_PY)
    script = '\n'.join([
        'set -u',
        f'python3 -I /repo/scripts/a7_board.py build --out /out/stage --netlist /repo/{NETLIST} > /out/build.log 2>&1; echo $? > /out/build.code',
        f'python3 -I /out/copper.py /repo/{BOARD} /repo/{PROPOSAL} /out/copper_nm.json > /out/copper.log 2>&1; echo $? > /out/copper.code',
    ])
    if a.review_aid:
        ra = '/out/review-aid'
        script += '\n' + '\n'.join([
            f'mkdir -p {ra}/gerbers {ra}/drill',
            f'kicad-cli pcb export gerbers --output {ra}/gerbers/ /repo/{BOARD} > /out/review_aid.log 2>&1 &&'
            f' kicad-cli pcb export drill --output {ra}/drill/ /repo/{BOARD} >> /out/review_aid.log 2>&1 &&'
            f' kicad-cli pcb export pos --format csv --units mm --side both --output {ra}/positions.csv /repo/{BOARD}'
            ' >> /out/review_aid.log 2>&1; echo $? > /out/review_aid.code',
        ])
    p = docker(image, out, script, 900)
    codes = {k: (out / f'{k}.code').read_text().strip() if (out / f'{k}.code').is_file() else None
             for k in ('build', 'copper', 'review_aid')}
    s['native'] = {'docker_exit': p.returncode, 'codes': codes, 'stderr_tail': p.stderr[-1000:]}
    if p.returncode != 0 or codes['build'] != '0' or codes['copper'] != '0':
        fails.append(f'native steps failed: docker exit {p.returncode}, codes {codes}')
    geo = out / 'stage/geometry.json'
    routes = out / 'routes_seed0.json'
    if geo.is_file():
        r = subprocess.run([sys.executable, '-I', str(REPO / 'scripts/a7_route.py'), '--seed', '0', '--geometry', str(geo),
                            '--out', str(routes)], capture_output=True, text=True, timeout=1500)
        s['router'] = {'exit': r.returncode, 'stdout_tail': r.stdout[-500:]}
        (out / 'route.log').write_text(r.stderr)
        if r.returncode != 0:
            fails.append(f'router exit {r.returncode}')
        if not routes.is_file():
            fails.append('router wrote no proposal')
        else:
            s['fresh_proposal_sha256'] = sha(routes)
            s['proposal_reproduced'] = routes.read_bytes() == (REPO / PROPOSAL).read_bytes()
            if not s['proposal_reproduced']:
                fails.append(f'seed-0 route differs from {PROPOSAL} ({sha(routes)} != {s["proposal_sha256"]})')
    else:
        fails.append('no staging geometry from a7_board.py build')
    if not (out / 'copper_nm.json').is_file():
        fails.append('no copper_nm.json from the in-image copper export')
    else:
        c = json.loads((out / 'copper_nm.json').read_text())
        fails += nonempty_failures(json.loads((REPO / PROPOSAL).read_text()), c)
        d = copper_diff(c['board'], c['proposal'])
        s['board_copper_vs_proposal'] = d
        for k, v in d.items():
            if not v['equal']:
                fails.append(f'committed board {k} differ from the recorded route ({v["board"]} vs {v["proposal"]})')
    if a.review_aid:
        if codes['review_aid'] != '0':
            fails.append(f'review-aid export failed (code {codes["review_aid"]})')
        else:
            # a Gerber job file lets a fabricator's site import the set in one click; this aid is not for ordering
            for job in (out / 'review-aid').rglob('*.gbrjob'):
                job.unlink()
            (out / 'review-aid/README-REVIEW-AID-ONLY.txt').write_text(REVIEW_AID_NOTE.format(sha=s['board_sha256']))
            s['review_aid'] = sorted(str(q.relative_to(out / 'review-aid')) for q in (out / 'review-aid').rglob('*') if q.is_file())
    s['failures'] = fails
    s['status'] = 'FAIL' if fails else 'PASS'
    (out / 'summary.json').write_text(json.dumps(s, indent=1) + '\n')
    print(json.dumps({k: s[k] for k in ('status', 'failures', 'board_sha256', 'proposal_sha256')}, indent=1))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
