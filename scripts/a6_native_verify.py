#!/usr/bin/env python3
"""A6 native KiCad 10.0.8 gate: stage, run in a digest-pinned container, evaluate.

Usage (CI and local):
  python3 scripts/a6_native_verify.py --repo . --out "$RUNNER_TEMP/a6-native"

Steps, all fail-closed:
  1. write a small failure receipt before any long work;
  2. verify A5 integrity (seed manifest + tree hash) and the A6 input manifest;
  3. stage only manifest-listed regular files (symlinks / unexpected names rejected);
  4. run scripts/a6_native_inner.py in one owned container (2 CPUs, 4 GiB,
     256 PIDs, no network) with a hard deadline, then remove only that container
     and prove it is gone;
  5. evaluate raw reports with scripts/a6_native_eval.py against the reviewed
     expectations, run the A5 interface assertions on the fresh netlists, run
     the positive / expected-failure / negative controls;
  6. re-verify A5 integrity and that the routed controller board is unchanged;
  7. copy allowlisted evidence (<= 25 MiB) and write summary.json.
Exit status 0 only when every check and every control passed.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a6_native_eval as ev  # noqa: E402

MANIFEST = 'engineering/a6/manifest.json'
EXPECT = 'engineering/a6/verification/native_expectations.json'
INNER = 'scripts/a6_native_inner.py'
EVIDENCE_CAP = 25 * 1024 * 1024
LABEL = 'zudo-led-block.a6-native'


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tree_sha(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob('*')):
        if p.is_symlink():
            h.update(b'L' + str(p.relative_to(root)).encode() + os.readlink(p).encode())
        elif p.is_file():
            h.update(str(p.relative_to(root)).encode() + b'\0' + sha(p).encode() + b'\n')
    return h.hexdigest()


def git(repo: Path, *a: str) -> str | None:
    try:
        return subprocess.run(['git', *a], cwd=repo, capture_output=True, text=True, timeout=30, check=True).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return None


def identities(repo: Path) -> dict:
    ident = {'checkout_head': git(repo, 'rev-parse', 'HEAD'), 'github_sha': os.environ.get('GITHUB_SHA'),
             'github_event': os.environ.get('GITHUB_EVENT_NAME'), 'github_ref': os.environ.get('GITHUB_REF'),
             'github_run_id': os.environ.get('GITHUB_RUN_ID'), 'workflow_ref': os.environ.get('GITHUB_WORKFLOW_REF'),
             'workflow_sha': os.environ.get('GITHUB_WORKFLOW_SHA')}
    evp = os.environ.get('GITHUB_EVENT_PATH')
    if evp and Path(evp).is_file():
        try:
            e = json.loads(Path(evp).read_text())
            pr = e.get('pull_request') or {}
            ident['pr_head_sha'] = (pr.get('head') or {}).get('sha')
            ident['pr_base_sha'] = (pr.get('base') or {}).get('sha')
            ident['pr_number'] = pr.get('number')
        except ValueError:
            ident['event_payload'] = 'unreadable'
    if ident.get('pr_head_sha'):
        ident['checkout_is_synthetic_merge'] = ident['checkout_head'] != ident['pr_head_sha']
        parents = git(repo, 'rev-list', '--parents', '-n', '1', 'HEAD')
        ident['checkout_parents'] = parents.split()[1:] if parents else None
    for f in ('.github/workflows/ci.yml', INNER, 'scripts/a6_native_eval.py', 'scripts/a6_native_verify.py',
              'scripts/a6_controller.py', MANIFEST, EXPECT):
        p = repo / f
        ident.setdefault('tool_sha256', {})[f] = sha(p) if p.is_file() else None
    return ident


class Gate:
    def __init__(self, repo: Path, out: Path, deadline_s: float):
        self.repo, self.out = repo, out
        self.t0 = time.monotonic()
        self.deadline = self.t0 + deadline_s
        self.failures: list[str] = []
        self.summary: dict = {'status': 'RUNNING', 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
        self.container: str | None = None

    def fail(self, msg: str) -> None:
        self.failures.append(msg)

    def receipt(self, status: str) -> None:
        self.summary['status'] = status
        self.summary['failures'] = self.failures
        self.summary['elapsed_s'] = round(time.monotonic() - self.t0, 2)
        (self.out / 'summary.json').write_text(json.dumps(self.summary, indent=1, sort_keys=True) + '\n')


def load_manifest(repo: Path) -> dict:
    m = json.loads((repo / MANIFEST).read_text())
    for k in ('image', 'kicad_version', 'files', 'designs'):
        if k not in m:
            raise ev.Fail(f'manifest missing {k}')
    return m


def verify_inputs(repo: Path, m: dict) -> list[str]:
    errs = []
    for f in m['files']:
        p = repo / f['path']
        if p.is_symlink() or not p.is_file():
            errs.append(f"input {f['path']}: missing or not a regular file"); continue
        if sha(p) != f['sha256']:
            errs.append(f"input {f['path']}: sha256 {sha(p)} != manifest {f['sha256']}")
    return errs


def stage(repo: Path, stage_dir: Path, m: dict) -> None:
    allowed_suffix = {'.kicad_pcb', '.kicad_pro', '.kicad_sch', '.kicad_sym', '.kicad_mod'}
    allowed_names = {'fp-lib-table', 'sym-lib-table'}
    for f in m['files']:
        if not f.get('stage'):
            continue
        rel = Path(f['path'])
        if rel.is_absolute() or '..' in rel.parts:
            raise ev.Fail(f'unsafe staged path {rel}')
        if rel.suffix not in allowed_suffix and rel.name not in allowed_names:
            raise ev.Fail(f'unexpected staged name {rel}')
        src = repo / rel
        if src.is_symlink() or not src.is_file():
            raise ev.Fail(f'staged source {rel} not a regular file')
        dst = stage_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        if sha(dst) != f['sha256']:
            raise ev.Fail(f'staged copy {rel} hash mismatch')
    for p in stage_dir.rglob('*'):
        if p.is_symlink():
            raise ev.Fail(f'symlink in stage {p}')


def docker(*a: str, timeout: float = 60) -> subprocess.CompletedProcess:
    return subprocess.run(['docker', *a], capture_output=True, text=True, timeout=timeout)


def _left(deadline: float) -> float:
    t = deadline - time.monotonic()
    if t <= 0:
        raise ev.Fail('cleanup reserve exhausted')
    return t


def owned_containers(run_label: str, deadline: float, dk=docker) -> list[str]:
    p = dk('ps', '-aq', '--filter', f'label={LABEL}={run_label}', timeout=_left(deadline))
    if p.returncode != 0:
        raise ev.Fail(f'docker ps failed: {p.stderr.strip()[:300]}')
    return [x for x in p.stdout.split() if x]


def cleanup_owned(run_label: str, deadline: float, dk=docker) -> dict:
    """Remove only containers whose label carries this run's id, inside the fixed reserve, and prove none remain.

    Every outcome, including a docker error or timeout, ends in a receipt with verified False rather than an exception."""
    rec: dict = {'removed': [], 'refused': [], 'errors': [], 'verified': False}
    try:
        for cid in owned_containers(run_label, deadline, dk):
            p = dk('inspect', '--format', '{{json .Config.Labels}}', cid, timeout=_left(deadline))
            try:
                labels = json.loads(p.stdout) if p.returncode == 0 else None
            except ValueError:
                labels = None
            if not isinstance(labels, dict) or labels.get(LABEL) != run_label:
                rec['refused'].append(cid)
                continue
            r = dk('rm', '-f', cid, timeout=_left(deadline))
            (rec['removed'] if r.returncode == 0 else rec['errors']).append(cid if r.returncode == 0 else f'rm {cid}: {r.stderr.strip()[:200]}')
        remaining = owned_containers(run_label, deadline, dk)
        rec['remaining'] = remaining
        rec['verified'] = not remaining and not rec['refused'] and not rec['errors']
    except (ev.Fail, subprocess.SubprocessError, OSError) as e:
        rec['errors'].append(f'{type(e).__name__}: {e}')
    return rec


def cleanup_failures(info: dict) -> list[str]:
    c = info.get('cleanup')
    if not isinstance(c, dict) or c.get('verified') is not True:
        return [f"container cleanup not verified: {(c or {}).get('errors') or (c or {}).get('refused') or (c or {}).get('remaining')}"]
    return []


def run_container(g: Gate, image: str, stage_dir: Path, raw: Path, plan: Path, budget: float, cleanup_reserve: float,
                  dk=docker, run_label: str | None = None) -> dict:
    run_label = run_label or uuid.uuid4().hex
    name = f'a6-native-{run_label[:12]}'
    g.container = name
    uid = f'{os.getuid()}:{os.getgid()}'
    args = ['run', '--name', name, '--label', f'{LABEL}={run_label}', '--network', 'none',
            '--cpus', '2', '--memory', '4g', '--memory-swap', '4g', '--pids-limit', '256',
            '--security-opt', 'no-new-privileges', '--cap-drop', 'ALL', '-u', uid, '-e', 'HOME=/tmp',
            '-v', f'{stage_dir}:/stage', '-v', f'{raw}:/out', '-v', f'{plan.parent}:/plan:ro',
            '-w', '/stage', image, 'python3', '/plan/a6_native_inner.py', '--stage', '/stage', '--out', '/out',
            '--plan', f'/plan/{plan.name}']
    info: dict = {'container_name': name, 'label': f'{LABEL}={run_label}', 'docker_args': args, 'budget_s': budget,
                  'cleanup_reserve_s': cleanup_reserve, 'exit_code': None, 'timed_out': False}
    t = time.monotonic()
    run_deadline = t + max(0.0, budget)
    cleanup_deadline = run_deadline + cleanup_reserve  # fixed now; nothing below extends it
    try:
        if budget <= 0:
            raise ev.Fail('no native budget left before the run')
        p = dk(*args, timeout=budget)
        info['exit_code'] = p.returncode
        info['stderr_tail'] = '\n'.join(l for l in p.stderr.splitlines() if 'Debug:' not in l)[-4000:]
    except subprocess.TimeoutExpired:
        info['timed_out'] = True
    except (ev.Fail, subprocess.SubprocessError, OSError) as e:
        info['run_error'] = f'{type(e).__name__}: {e}'
    finally:
        info['seconds'] = round(time.monotonic() - t, 2)
        if info['timed_out'] or info.get('run_error'):
            try:
                k = dk('kill', name, timeout=_left(cleanup_deadline))
                info['kill'] = {'exit_code': k.returncode}
            except (ev.Fail, subprocess.SubprocessError, OSError) as e:
                info['kill'] = {'error': f'{type(e).__name__}: {e}'}
        info['cleanup'] = cleanup_owned(run_label, cleanup_deadline, dk)
        info['cleanup_verified'] = info['cleanup']['verified']
        g.summary['container'] = {k: v for k, v in info.items()}
        g.receipt('CLEANED_INCOMPLETE' if info['cleanup_verified'] else 'CLEANUP_FAILED_INCOMPLETE')
    return info


def build_plan(m: dict, x: dict) -> dict:
    designs = []
    for name, d in m['designs'].items():
        designs.append({'name': name, 'stage_dir': d['dir'], 'schematic': d['schematic'], 'board': d['board'],
                        'deadline_s': x['limits']['design_deadline_s'], 'refill_check': x['designs'][name].get('refill_check', False)})
    for name, c in x['controls']['expected_failure'].items():
        designs.append({'name': name, 'stage_dir': c['dir'], 'schematic': c['schematic'], 'board': c['board'],
                        'deadline_s': x['limits']['design_deadline_s']})
    t = x['controls']['timeout']
    designs.append({'name': 'control_timeout', 'stage_dir': m['designs'][t['design']]['dir'],
                    'schematic': m['designs'][t['design']]['schematic'], 'board': m['designs'][t['design']]['board'],
                    'deadline_s': t['deadline_s']})
    muts = []
    for name, c in x['controls']['mutations'].items():
        d = m['designs'][c['design']]
        muts.append({'name': name, 'stage_dir': d['dir'], 'source_board': d['board'],
                     'board': c['kind'] + '_mut.kicad_pcb', 'kind': c['kind'], 'deadline_s': x['limits']['design_deadline_s'],
                     'refill_check': bool(c.get('refill_check'))})
    return {'designs': designs, 'mutations': muts}


def design_inputs(m: dict, name: str) -> dict:
    d = m['designs'][name]
    return {Path(f['path']).name: f['sha256'] for f in m['files'] if f.get('stage') and str(Path(f['path']).parent) == d['dir']}


def interface_check(g: Gate, m: dict, raw: Path, tmp: Path) -> dict:
    script = g.repo / m['interface_check']['script']
    outp = tmp / 'interface_check.json'
    args = [sys.executable, str(script)] + [str(raw / n / 'netlist.xml') for n in m['interface_check']['designs']] + ['--output', str(outp)]
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=120, cwd=tmp)
    except subprocess.TimeoutExpired:
        return {'ok': False, 'failures': ['interface check timed out']}
    res: dict = {'exit_code': p.returncode, 'stdout_tail': p.stdout[-2000:], 'stderr_tail': p.stderr[-2000:]}
    fails = []
    if p.returncode != 0:
        fails.append(f'interface check exit {p.returncode}')
    try:
        rep = ev.load_json(outp)
        res['report_sha256'] = sha(outp)
        shutil.copyfile(outp, raw / 'interface_check.json')
        checks = rep.get('checks')
        if rep.get('all_passed') is not True or not isinstance(checks, list):
            fails.append('interface check did not report all_passed')
        else:
            bad = [c.get('check') for c in checks if c.get('passed') is not True]
            fails += [f'interface assertion failed: {b}' for b in bad]
            if len(checks) < m['interface_check']['min_checks']:
                fails.append(f"interface check ran {len(checks)} < {m['interface_check']['min_checks']} assertions")
            res['checks'] = len(checks)
    except ev.Fail as e:
        fails.append(str(e))
    res['ok'] = not fails
    res['failures'] = fails
    return res


def netlist_unchanged(raw: Path, a: str, b: str) -> list[str]:
    """A6 controller netlist must equal the frozen A5 controller netlist (components, fields, nets)."""
    try:
        ca, pa = ev.parse_netlist(raw / a / 'netlist.xml')
        cb, pb = ev.parse_netlist(raw / b / 'netlist.xml')
    except ev.Fail as e:
        return [str(e)]
    errs = []
    if ca != cb:
        errs.append('component set/fields differ from A5 controller netlist')
    if pa != pb:
        diff = sorted(set(pa.items()) ^ set(pb.items()))[:10]
        errs.append(f'net connectivity differs from A5 controller netlist: {diff}')
    return errs


def evaluate_all(g: Gate, m: dict, x: dict, raw: Path, info: dict) -> dict:
    res: dict = {'designs': {}, 'controls': {}}
    if info.get('timed_out') or info.get('exit_code') != 0:
        g.fail(f"inner run exit {info.get('exit_code')} timed_out={info.get('timed_out')}")
    g.failures += cleanup_failures(info)
    try:
        inner = ev.load_json(raw / 'inner_record.json')
    except ev.Fail as e:
        g.fail(str(e)); return res
    for f in ev.check_versions(inner, m['kicad_version']):
        g.fail(f)
    for name in m['designs']:
        e = dict(x['designs'][name]); e.update({k: x[k] for k in ('kicad_version', 'included_severities', 'ignored_checks')})
        r = ev.evaluate_design(name, e, inner.get('designs', {}).get(name), raw / name, design_inputs(m, name))
        res['designs'][name] = r
        g.failures += [f'{name}: {f}' for f in r['failures']]
    ctl = res['controls']
    for name, c in x['controls']['expected_failure'].items():
        r = ev.evaluate_expected_failure(c, inner.get('designs', {}).get(name), raw / name)
        ctl[name] = r
        if not r['ok']:
            g.fail(f'control {name}: {r["failures"]}')
    t = inner.get('designs', {}).get('control_timeout', {})
    timed = any(op.get('timed_out') for op in t.get('ops', {}).values())
    ctl['control_timeout'] = {'ok': timed, 'detail': {k: v.get('timed_out') for k, v in t.get('ops', {}).items()}}
    if not timed:
        g.fail('control_timeout: a too-short deadline did not time out')
    cand = x['controls']['mutations']
    for name, c in cand.items():
        mr = inner.get('controls', {}).get(name, {})
        e = dict(x['designs'][c['design']]); e.update({k: x[k] for k in ('kicad_version', 'included_severities', 'ignored_checks')})
        e['refill_check'] = bool(c.get('refill_check'))
        out = raw / name
        # a mutated board shares the candidate's schematic: reuse its fresh netlist and ERC
        for k in ('erc.json', 'netlist.xml'):
            if (raw / c['design'] / k).is_file() and not (out / k).exists():
                shutil.copyfile(raw / c['design'] / k, out / k)
        fake = {'ops': {'erc': inner['designs'][c['design']]['ops']['erc'], 'netlist': inner['designs'][c['design']]['ops']['netlist'],
                        'drc': mr.get('ops', {}).get('drc')}, 'deadline_exceeded': False,
                'stage_before': {}, 'stage_after': {}}
        r = ev.evaluate_design(name, e, fake, out, {})
        hit = [f for f in r['failures'] if any(s in f for s in c['must_report'])]
        ok = (not r['ok']) and bool(hit) and 'error' not in mr.get('mutation', {})
        if c['kind'] == 'fill_shift' and mr.get('mutation', {}).get('summary_unchanged') is not True:
            ok = False  # the control only proves something if area and vertex count stayed equal
        ctl[name] = {'ok': ok, 'mutation': mr.get('mutation'), 'detected_by': hit[:5]}
        if not ok:
            g.fail(f'negative control {name} was not detected as required ({c["must_report"]})')
    # evaluator-level negative controls on the real candidate record
    base = x['controls']['synthetic_design']
    ctl.update(synthetic_controls(m, x, inner, raw, base))
    for k, v in ctl.items():
        if k.startswith('synthetic_') and not v['ok']:
            g.fail(f'negative control {k} not detected')
    return res


class FakeDocker:
    """Stand-in docker CLI for exercising the production cleanup path without a daemon."""

    def __init__(self, label: str, rm_fails=False, run_timeout=False, kill_timeout=False, foreign=False, ps_fails=False):
        self.label, self.rm_fails, self.run_timeout, self.kill_timeout = label, rm_fails, run_timeout, kill_timeout
        self.foreign, self.ps_fails = foreign, ps_fails
        self.alive = {'c1'}
        self.calls: list[str] = []
        self.rm_calls = 0

    def __call__(self, *a: str, timeout: float = 60) -> subprocess.CompletedProcess:
        self.calls.append(a[0])
        ok = lambda out='': subprocess.CompletedProcess(a, 0, out, '')
        if a[0] == 'run':
            if self.run_timeout:
                raise subprocess.TimeoutExpired(a, timeout)
            return ok()
        if a[0] == 'kill':
            if self.kill_timeout:
                raise subprocess.TimeoutExpired(a, timeout)
            return ok()
        if a[0] == 'ps':
            if self.ps_fails:
                return subprocess.CompletedProcess(a, 1, '', 'daemon gone')
            return ok('\n'.join(sorted(self.alive)))
        if a[0] == 'inspect':
            return ok(json.dumps({LABEL: 'someone-else' if self.foreign else self.label}))
        if a[0] == 'rm':
            self.rm_calls += 1
            if self.rm_fails:
                return subprocess.CompletedProcess(a, 1, '', 'rm failed')
            self.alive.discard(a[-1])
            return ok()
        raise AssertionError(a)


def synthetic_controls(m: dict, x: dict, inner: dict, raw: Path, name: str) -> dict:
    """Corrupt copies of the real candidate record/reports; each must make the evaluator fail."""
    out: dict = {}
    e = dict(x['designs'][name]); e.update({k: x[k] for k in ('kicad_version', 'included_severities', 'ignored_checks')})
    inputs = design_inputs(m, name)
    rec0 = inner.get('designs', {}).get(name)
    if not isinstance(rec0, dict):
        return {'synthetic_missing_record': {'ok': False}}

    def run_case(key: str, rec: dict, mutate_dir=None, inputs_=None) -> None:
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / name
            shutil.copytree(raw / name, d)
            if mutate_dir:
                mutate_dir(d)
            r = ev.evaluate_design(name, e, rec, d, inputs if inputs_ is None else inputs_)
            out[f'synthetic_{key}'] = {'ok': not r['ok'], 'failures': r['failures'][:3]}

    run_case('missing_report', copy.deepcopy(rec0), lambda d: (d / 'drc.json').unlink())
    run_case('malformed_report', copy.deepcopy(rec0), lambda d: (d / 'drc.json').write_text('{"violations": ['))
    bad = dict(inputs); k0 = sorted(bad)[0]; bad[k0] = '0' * 64
    run_case('wrong_input_hash', copy.deepcopy(rec0), inputs_=bad)
    r = copy.deepcopy(rec0); r['ops']['drc']['timed_out'] = True; r['ops']['drc']['exit_code'] = None
    run_case('timeout', r)
    r = copy.deepcopy(rec0); r['ops']['drc']['exit_code'] = 3
    run_case('unknown_exit', r)
    r = copy.deepcopy(rec0); r['stage_after'] = dict(r['stage_after']); r['stage_after'][sorted(inputs)[0]] = 'f' * 64
    run_case('unexpected_write', r)
    r = copy.deepcopy(rec0); r['stage_after'] = dict(r['stage_after']); r['stage_after']['stray.kicad_pcb'] = 'e' * 64
    run_case('unexpected_new_file', r)

    def stale(d: Path) -> None:
        j = json.loads((d / 'drc.json').read_text()); j['kicad_version'] = '9.0.0'
        (d / 'drc.json').write_text(json.dumps(j))
    run_case('version_mismatch', copy.deepcopy(rec0), stale)

    def zero_exit_with_violation(d: Path) -> None:
        j = json.loads((d / 'drc.json').read_text())
        j['violations'].append({'type': 'clearance', 'description': 'Clearance violation', 'severity': 'error',
                                'items': [{'description': 'Pad 1 of U1'}, {'description': 'Track [GND]'}]})
        (d / 'drc.json').write_text(json.dumps(j))
    r = copy.deepcopy(rec0); r['ops']['drc']['exit_code'] = 0
    run_case('zero_exit_overridden_by_violation', r, zero_exit_with_violation)
    v = ev.check_versions(dict(inner, pcbnew_version='9.0.7'), m['kicad_version'])
    out['synthetic_tool_version_mismatch'] = {'ok': bool(v), 'failures': v}
    # cleanup failure: drive the production cleanup with a docker whose removal fails; the gate must refuse it
    lbl = 'synthetic-' + uuid.uuid4().hex
    fake = FakeDocker(lbl, rm_fails=True)
    c = cleanup_owned(lbl, time.monotonic() + 5, fake)
    out['synthetic_cleanup_failure'] = {'ok': bool(cleanup_failures({'cleanup': c})) and fake.rm_calls == 1,
                                        'failures': cleanup_failures({'cleanup': c})}
    return out


def a5_integrity(repo: Path) -> dict:
    p = subprocess.run([sys.executable, 'scripts/verify_seed.py', '--manifest', 'provenance/seed-manifest.json', '--repo', '.'],
                       cwd=repo, capture_output=True, text=True, timeout=300)
    return {'verify_seed_exit': p.returncode, 'verify_seed_tail': p.stdout[-300:], 'tree_sha256': tree_sha(repo / 'engineering/a5'),
            'git_status': git(repo, 'status', '--porcelain', '--', 'engineering/a5')}


def rebuild_preservation(g: Gate, m: dict) -> dict:
    """Normal A6 generation must leave the routed controller board byte-identical."""
    board = g.repo / m['designs']['controller']['dir'] / m['designs']['controller']['board']
    before = sha(board)
    p = subprocess.run([sys.executable, 'scripts/a6_controller.py', 'generate', '--check', '--facts',
                        str(g.out / 'raw' / 'controller' / 'board_facts.json'),
                        '--geometry', str(g.out / 'raw' / 'controller' / 'board_geometry.json')],
                       cwd=g.repo, capture_output=True, text=True, timeout=120)
    after = sha(board)
    res = {'board_sha256_before': before, 'board_sha256_after': after, 'generate_check_exit': p.returncode,
           'generate_output_tail': (p.stdout + p.stderr)[-3000:]}
    if before != after:
        g.fail('routed controller board changed during normal A6 generation')
    if p.returncode != 0:
        g.fail(f'A6 derived files are stale or generation failed (exit {p.returncode})')
    return res


def copy_evidence(g: Gate, raw: Path, x: dict) -> dict:
    ev_dir = g.out / 'evidence'
    ev_dir.mkdir(exist_ok=True)
    allowed = set(x['evidence']['allowed_names'])
    total = 0
    listing = {}
    for p in sorted(raw.rglob('*')):
        if not p.is_file() or p.is_symlink() or p.name not in allowed:
            continue
        rel = p.relative_to(raw)
        size = p.stat().st_size
        if total + size > EVIDENCE_CAP:
            g.fail(f'evidence cap exceeded at {rel}')
            break
        dst = ev_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dst)
        total += size
        listing[str(rel)] = sha(p)
    return {'bytes': total, 'files': listing}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', type=Path, default=Path('.'))
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--deadline-s', type=float, default=11 * 60, help='native run budget incl. 1 min cleanup reserve')
    a = ap.parse_args()
    repo = a.repo.resolve()
    out = a.out.resolve()
    if out == repo or repo in out.parents:
        print('refusing: --out must be outside the repository', file=sys.stderr)
        return 2
    if out.exists() and any(out.iterdir()):
        print('refusing: --out must be empty or absent', file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    g = Gate(repo, out, a.deadline_s)
    g.receipt('STARTED_INCOMPLETE')  # small receipt first: an interrupted run is never mistaken for a pass
    try:
        g.summary['identity'] = identities(repo)
        g.summary['a5_before'] = a5_integrity(repo)
        if g.summary['a5_before']['verify_seed_exit'] != 0 or g.summary['a5_before']['git_status']:
            g.fail('A5 checkpoint not intact before the run')
        m = load_manifest(repo)
        x = json.loads((repo / EXPECT).read_text())
        g.summary['image'] = m['image']
        errs = verify_inputs(repo, m)
        g.failures += errs
        g.summary['input_manifest'] = {f['path']: f['sha256'] for f in m['files']}
        tested = repo / m['designs']['controller']['dir'] / m['designs']['controller']['board']
        g.summary['tested_board_sha256'] = sha(tested)
        if errs:
            raise ev.Fail('input manifest mismatch; native run skipped')
        with tempfile.TemporaryDirectory(prefix='a6-native-') as td:
            td = Path(td)
            stage_dir, raw, plan_dir = td / 'stage', out / 'raw', td / 'plan'
            for d in (stage_dir, raw, plan_dir):
                d.mkdir()
            stage(repo, stage_dir, m)
            plan = plan_dir / 'plan.json'
            plan.write_text(json.dumps(build_plan(m, x), indent=1))
            shutil.copyfile(repo / INNER, plan_dir / 'a6_native_inner.py')
            g.receipt('STAGED_INCOMPLETE')
            reserve = x['limits']['cleanup_reserve_s']
            budget = min(x['limits']['native_deadline_s'], g.deadline - time.monotonic() - reserve)
            info = run_container(g, m['image'], stage_dir, raw, plan, budget, reserve)
            g.summary['container'] = {k: v for k, v in info.items() if k != 'docker_args'}
            g.summary['container']['docker_args'] = info['docker_args']
            res = evaluate_all(g, m, x, raw, info)
            g.summary['results'] = res
            g.summary['netlist_unchanged_vs_a5'] = netlist_unchanged(raw, 'controller', 'a5_controller_expected_failure')
            g.failures += [f'netlist: {e}' for e in g.summary['netlist_unchanged_vs_a5']]
            ic = interface_check(g, m, raw, td)
            g.summary['interface_check'] = ic
            g.failures += [f'interface: {f}' for f in ic['failures']]
            g.summary['rebuild_preservation'] = rebuild_preservation(g, m)
            g.summary['evidence'] = copy_evidence(g, raw, x)
            shutil.copyfile(plan, out / 'plan.json')
        if sha(tested) != g.summary['tested_board_sha256']:
            g.fail('tested board changed during the run')
    except (ev.Fail, KeyError, ValueError, OSError, subprocess.SubprocessError) as e:
        g.fail(f'gate aborted: {type(e).__name__}: {e}')
    try:
        g.summary['a5_after'] = a5_integrity(repo)
        b = g.summary.get('a5_before', {})
        if g.summary['a5_after']['tree_sha256'] != b.get('tree_sha256') or g.summary['a5_after']['verify_seed_exit'] != 0 \
                or g.summary['a5_after']['git_status']:
            g.fail('A5 checkpoint changed during the run')
    except (OSError, subprocess.SubprocessError) as e:
        g.fail(f'A5 after-check failed: {e}')
    g.receipt('PASS' if not g.failures else 'FAIL')
    print(json.dumps({'status': g.summary['status'], 'failures': g.failures[:50],
                      'tested_board_sha256': g.summary.get('tested_board_sha256')}, indent=1))
    return 0 if not g.failures else 1


if __name__ == '__main__':
    sys.exit(main())
