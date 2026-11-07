#!/usr/bin/env python3
"""A6 native checks, executed INSIDE the digest-pinned KiCad 10.0.8 container.

Invoked only by scripts/a6_native_verify.py. Reads staged copies under
--stage (never the repository), writes raw reports and a machine record
under --out. Every KiCad CLI call has its own deadline and a bounded log.
The record contains raw facts only; pass/fail is decided on the host by the
evaluator, which treats anything missing or unexpected as a failure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

LOG_CAP = 2 * 1024 * 1024


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def cap(text: str) -> tuple[str, bool]:
    raw = text.encode('utf-8', 'replace')
    if len(raw) <= LOG_CAP:
        return text, False
    return raw[:LOG_CAP].decode('utf-8', 'replace'), True


def run(args: list[str], cwd: Path, deadline: float) -> dict:
    t0 = time.monotonic()
    budget = max(0.05, deadline - t0)
    rec: dict = {'args': args, 'cwd': str(cwd)}
    try:
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=budget)
        rec['exit_code'] = p.returncode
        rec['stdout'], rec['stdout_truncated'] = cap(p.stdout)
        rec['stderr'], rec['stderr_truncated'] = cap('\n'.join(l for l in p.stderr.splitlines() if 'Debug:' not in l))
        rec['timed_out'] = False
    except subprocess.TimeoutExpired:
        rec['exit_code'] = None
        rec['timed_out'] = True
    rec['seconds'] = round(time.monotonic() - t0, 3)
    return rec


def board_facts(pcb: Path) -> dict:
    """Connectivity, pad nets and a canonical geometry digest from pcbnew."""
    import pcbnew as p
    b = p.LoadBoard(str(pcb))
    T = p.ToMM
    fps = []
    for fp in sorted(b.GetFootprints(), key=lambda f: f.GetReference()):
        pads = []
        for pd in fp.Pads():
            pads.append([pd.GetNumber(), pd.GetNetname(), round(T(pd.GetPosition().x), 4), round(T(pd.GetPosition().y), 4)])
        pads.sort()
        fps.append({'ref': fp.GetReference(), 'fpid': fp.GetFPIDAsString(),
                    'x': round(T(fp.GetPosition().x), 4), 'y': round(T(fp.GetPosition().y), 4),
                    'rot': round(fp.GetOrientationDegrees(), 3), 'side': 'B' if fp.IsFlipped() else 'F',
                    'board_only': bool(fp.GetAttributes() & p.FP_BOARD_ONLY), 'pads': pads})
    tracks, vias = [], []
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            vias.append([round(T(t.GetPosition().x), 4), round(T(t.GetPosition().y), 4), round(T(t.GetWidth(p.F_Cu)), 4), round(T(t.GetDrillValue()), 4), t.GetNetname()])
        elif t.GetClass() == 'PCB_ARC':
            tracks.append(['arc', b.GetLayerName(t.GetLayer()), round(T(t.GetStart().x), 4), round(T(t.GetStart().y), 4), round(T(t.GetMid().x), 4), round(T(t.GetMid().y), 4), round(T(t.GetEnd().x), 4), round(T(t.GetEnd().y), 4), round(T(t.GetWidth()), 4), t.GetNetname()])
        else:
            a = (round(T(t.GetStart().x), 4), round(T(t.GetStart().y), 4)); e = (round(T(t.GetEnd().x), 4), round(T(t.GetEnd().y), 4))
            a, e = sorted([a, e])
            tracks.append(['seg', b.GetLayerName(t.GetLayer()), *a, *e, round(T(t.GetWidth()), 4), t.GetNetname()])
    tracks.sort(); vias.sort()
    zones = []
    for z in b.Zones():
        ol = z.Outline()
        pts = [[round(T(ol.CVertex(i).x), 4), round(T(ol.CVertex(i).y), 4)] for i in range(ol.TotalVertices())]
        zones.append({'net': z.GetNetname(), 'layers': [b.GetLayerName(l) for l in z.GetLayerSet().Seq()],
                      'outline': pts, 'priority': z.GetAssignedPriority(), 'filled': z.IsFilled(),
                      'name': z.GetZoneName()})
    zones.sort(key=lambda z: json.dumps(z, sort_keys=True))
    edges = []
    for d in b.GetDrawings():
        if d.GetLayer() == p.Edge_Cuts:
            edges.append([round(T(d.GetStart().x), 4), round(T(d.GetStart().y), 4), round(T(d.GetEnd().x), 4), round(T(d.GetEnd().y), 4)])
    edges.sort()
    ds = b.GetDesignSettings()
    geom = {'footprints': fps, 'tracks': tracks, 'vias': vias, 'zones': zones, 'edges': edges,
            'copper_layers': b.GetCopperLayerCount(), 'thickness_mm': round(T(ds.GetBoardThickness()), 4)}
    digest = hashlib.sha256(json.dumps(geom, sort_keys=True).encode()).hexdigest()
    b.BuildConnectivity()
    conn = b.GetConnectivity()
    fill_digest = None
    fills = []
    for z in b.Zones():
        for l in z.GetLayerSet().Seq():
            if z.HasFilledPolysForLayer(l):
                fp_ = z.GetFilledPolysList(l)
                fills.append([z.GetZoneName(), b.GetLayerName(l), round(T(fp_.Area() ** 0.5) if hasattr(fp_, 'Area') else 0, 4), fp_.TotalVertices()])
    fills.sort()
    fill_digest = hashlib.sha256(json.dumps(fills).encode()).hexdigest()
    return {'geometry_sha256': digest, 'zone_fill_summary': fills, 'zone_fill_sha256': fill_digest,
            'unconnected_pcbnew': conn.GetUnconnectedCount(True), 'track_count': len(tracks), 'via_count': len(vias),
            'zone_count': len(zones), 'footprint_count': len(fps),
            'pad_nets': {f['ref']: {pd[0]: pd[1] for pd in f['pads'] if pd[0]} for f in fps},
            'board_only': sorted(f['ref'] for f in fps if f['board_only']), 'geometry': geom}


def refill_copy(src: Path, dst: Path) -> dict:
    import pcbnew as p
    b = p.LoadBoard(str(src))
    filler = p.ZONE_FILLER(b)
    filler.Fill(b.Zones())
    p.SaveBoard(str(dst), b)
    return {'refilled_board_sha256': sha(dst)}


def mutate(src: Path, dst: Path, kind: str) -> dict:
    """Negative controls on a staged copy: break one route or reassign one pad net."""
    import pcbnew as p
    b = p.LoadBoard(str(src))
    info = {'kind': kind}
    if kind == 'route_break':
        cands = [t for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK' and t.GetNetname() not in ('GND', '')]
        cands.sort(key=lambda t: (t.GetNetname(), t.GetStart().x, t.GetStart().y))
        victim = cands[len(cands) // 2]
        info['removed_track_net'] = victim.GetNetname()
        b.Remove(victim)
    elif kind == 'wrong_connection':
        fp = b.FindFootprintByReference('R14')
        pad = [pd for pd in fp.Pads() if pd.GetNumber() == '2'][0]
        info['pad'] = 'R14.2'; info['from_net'] = pad.GetNetname()
        target = [n for n in b.GetNetsByName().keys() if str(n).lstrip('/') == 'DATA_R'][0]
        pad.SetNet(b.FindNet(str(target)))
        info['to_net'] = str(target)
    p.SaveBoard(str(dst), b)
    return info


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--plan', type=Path, required=True)
    a = ap.parse_args()
    plan = json.loads(a.plan.read_text())
    a.out.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('HOME', '/tmp')
    rec: dict = {'started_monotonic': time.monotonic(), 'designs': {}, 'controls': {}}
    import pcbnew
    rec['pcbnew_version'] = pcbnew.GetBuildVersion()
    v = run(['kicad-cli', 'version'], a.stage, time.monotonic() + 60)
    rec['kicad_cli_version'] = v
    for d in plan['designs']:
        name = d['name']
        proj = a.stage / d['stage_dir']
        out = a.out / name
        out.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + d['deadline_s']
        before = {f.name: sha(f) for f in sorted(proj.iterdir()) if f.is_file()}
        ops = {}
        sch, pcb = proj / d['schematic'], proj / d['board']
        ops['erc'] = run(['kicad-cli', 'sch', 'erc', '--format', 'json', '--severity-all', '--exit-code-violations',
                          '-o', str(out / 'erc.json'), str(sch)], proj, deadline)
        ops['netlist'] = run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml',
                              '-o', str(out / 'netlist.xml'), str(sch)], proj, deadline)
        ops['drc'] = run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all', '--schematic-parity',
                          '--exit-code-violations', '-o', str(out / 'drc.json'), str(pcb)], proj, deadline)
        facts_ok = True
        try:
            facts = board_facts(pcb)
        except Exception as e:  # recorded; evaluator fails on missing facts
            facts = {'error': repr(e)}; facts_ok = False
        geom = facts.pop('geometry', None)
        (out / 'board_facts.json').write_text(json.dumps(facts, indent=1, sort_keys=True) + '\n')
        if geom is not None:
            (out / 'board_geometry.json').write_text(json.dumps(geom, sort_keys=True) + '\n')
        if d.get('refill_check') and facts_ok:
            tmp = proj / ('refill_' + d['board'])
            try:
                info = refill_copy(pcb, tmp)
                rf = board_facts(tmp); rf.pop('geometry', None)
                info.update({'geometry_sha256': rf['geometry_sha256'], 'zone_fill_sha256': rf['zone_fill_sha256'],
                             'unconnected_pcbnew': rf['unconnected_pcbnew']})
            except Exception as e:
                info = {'error': repr(e)}
            finally:
                if tmp.exists():
                    tmp.unlink()
                for extra in proj.glob('refill_*'):
                    extra.unlink()
            (out / 'refill.json').write_text(json.dumps(info, indent=1) + '\n')
        after = {f.name: sha(f) for f in sorted(proj.iterdir()) if f.is_file()}
        rec['designs'][name] = {'ops': ops, 'stage_before': before, 'stage_after': after,
                                'deadline_exceeded': time.monotonic() > deadline}
    for c in plan.get('mutations', []):
        name = c['name']
        proj = a.stage / c['stage_dir']
        out = a.out / name
        out.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + c['deadline_s']
        mut = proj / c['board']
        try:
            info = mutate(proj / c['source_board'], mut, c['kind'])
        except Exception as e:
            info = {'error': repr(e)}
        ops = {}
        if mut.exists():
            ops['drc'] = run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all', '--schematic-parity',
                              '--exit-code-violations', '-o', str(out / 'drc.json'), str(mut)], proj, deadline)
            try:
                mf = board_facts(mut); mf.pop('geometry', None)
            except Exception as e:
                mf = {'error': repr(e)}
            (out / 'board_facts.json').write_text(json.dumps(mf, indent=1, sort_keys=True) + '\n')
            mut.unlink()
            for extra in proj.glob(Path(c['board']).stem + '*'):
                extra.unlink()
        rec['controls'][name] = {'mutation': info, 'ops': ops}
    rec['finished_monotonic'] = time.monotonic()
    (a.out / 'inner_record.json').write_text(json.dumps(rec, indent=1, sort_keys=True) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
