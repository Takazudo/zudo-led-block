#!/usr/bin/env python3
"""Profile-driven native KiCad 10.0.8 gate: stage, run in a digest-pinned container, evaluate.

Ported from scripts/a6_native_verify.py at PR #14 head 7e96380be4fbea2bfcc4a5bd1d5721272a5a141f
(sha256 f762696e7a80bec765a9f3ed80e7f83c656fc3bc8aff24ba9b7dbe44c12542f3). The A6 paths,
the A6 generator call and the "controller netlist must equal A5" identity condition
are replaced by a profile (JSON) that names its designs, controls, behavioral role
map, authorized-delta record and regeneration command. See scripts/native_gate/PROVENANCE.md.

Profiles:
  kind "infrastructure"  fixtures only. The best possible result is INFRASTRUCTURE_PASS,
                         which says the gate machinery detects what it must; it is
                         never a board result.
  kind "revision"        an authoritative board. With "candidate": null the gate stops
                         with NO_CANDIDATE (exit 1) before any native work.

Usage:
  python3 scripts/native_gate/runner.py lock  --profile P [--check]
  python3 scripts/native_gate/runner.py run   --profile P --repo . --out DIR [--deadline-s N]

Steps of `run`, all fail-closed:
  1. small receipt before any long work;
  2. A5 integrity (seed manifest + tree hash), profile lock hashes;
  3. stage only lock-listed regular files (symlinks / unexpected names rejected);
  4. one owned container (2 CPUs, 4 GiB, 256 PIDs, no network, no caps) with a hard
     deadline; remove only that container and prove it is gone (cleanup receipt);
  5. evaluate raw reports against the profile expectations; behavioral interface
     assertions and the authorized-delta check on the fresh netlists; positive,
     expected-failure, timeout, mutation and synthetic controls;
  6. regeneration-preservation: run the profile's regeneration --check and prove the
     authoritative board is byte-identical before and after;
  7. A5 integrity again; allowlisted evidence (<= 25 MiB) and summary.json.
Exit 0 only when every check and every control passed.
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
import evaluate as ev  # noqa: E402
import interface as itf  # noqa: E402
import delta as dl  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
INNER = 'scripts/native_gate/inner.py'
TOOLS = ('scripts/native_gate/runner.py', 'scripts/native_gate/inner.py', 'scripts/native_gate/evaluate.py',
         'scripts/native_gate/interface.py', 'scripts/native_gate/delta.py', 'scripts/native_gate/authority.py')
EVIDENCE_CAP = 25 * 1024 * 1024
LABEL = 'zudo-led-block.native-gate'
STAGE_SUFFIX = {'.kicad_pcb', '.kicad_pro', '.kicad_dru', '.kicad_sch', '.kicad_sym', '.kicad_mod'}
STAGE_NAMES = {'fp-lib-table', 'sym-lib-table'}
FOOTPRINT_DIR = 'engineering/a5/electronics/footprints/LightBlock.pretty'
BOARD_NOTE = 'A green native gate is not an electronics or manufacturing approval.'


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


# ---------------------------------------------------------------- profile and lock

def load_profile(repo: Path, rel: str) -> dict:
    p = json.loads((repo / rel).read_text())
    for k in ('schema', 'profile', 'kind', 'image', 'kicad_version', 'lock', 'designs'):
        if k not in p:
            raise ev.Fail(f'profile missing {k}')
    if p['kind'] not in ('infrastructure', 'revision'):
        raise ev.Fail(f"profile kind {p['kind']!r}")
    if p['kind'] == 'revision' and 'candidate' not in p:
        raise ev.Fail('revision profile must state candidate (a design name or null)')
    if p['kind'] == 'infrastructure' and p.get('candidate'):
        raise ev.Fail('an infrastructure profile cannot name a candidate board')
    if p['kind'] == 'revision' and p.get('candidate'):
        errs = candidate_binding(p)
        if errs:
            raise ev.Fail('candidate binding: ' + '; '.join(errs))
    return p


def candidate_binding(p: dict) -> list[str]:
    """A named candidate must be the board every revision check is actually computed on."""
    c = p['candidate']
    d = p['designs'].get(c)
    if not isinstance(d, dict):
        return [f'candidate {c!r} is not a design in the profile']
    errs = []
    board = f"{d['dir']}/{d['board']}"
    if board not in (p.get('regeneration') or {}).get('protected', []):
        errs.append(f'candidate board {board} is not the protected authoritative board in regeneration.protected')
    if (p.get('delta') or {}).get('candidate_design') != c:
        errs.append(f'delta.candidate_design must be the candidate {c!r}')
    if ((p.get('interface') or {}).get('netlists') or {}).get('controller') != c:
        errs.append(f'interface.netlists.controller must be the candidate {c!r}')
    muts = (p.get('controls') or {}).get('mutations') or {}
    kinds = {m.get('kind') for m in muts.values() if m.get('design') == c}
    need = {'route_break', 'wrong_connection', 'fill_shift'}
    if not need <= kinds:
        errs.append('route_break, wrong_connection and fill_shift controls must run on the candidate')
    rules = (p.get('design_rule_delta') or {}).get('custom_rules') or []
    if rules or d.get('custom_rules'):
        if not d.get('custom_rules') or not rules:
            errs.append('custom rules must be named both on the candidate design and in design_rule_delta.custom_rules')
        proved = {r for m in muts.values() if m.get('design') == c and m.get('kind') == 'rule_squeeze' for r in m.get('must_report', [])}
        for r in rules:
            if r.get('direction') != 'stricter':
                errs.append(f"custom rule {r.get('name')} must be recorded as stricter-only")
            if r.get('name') not in proved:
                errs.append(f"custom rule {r.get('name')} has no rule_squeeze control on the candidate")
    if (p.get('controls') or {}).get('synthetic_design') != c:
        errs.append('synthetic controls must run on the candidate')
    if not p.get('expected_failure'):
        errs.append('the immutable A5 controller expected-failure control is required')
    return errs


def design_dirs(p: dict) -> list[str]:
    dirs = [d['dir'] for d in p['designs'].values()]
    dirs += [c['dir'] for c in p.get('expected_failure', {}).values()]
    return sorted(set(dirs))


def lock_entries(repo: Path, p: dict, profile_rel: str) -> list[dict]:
    files = []
    for d in design_dirs(p):
        for f in sorted((repo / d).iterdir()):
            if f.is_file() and not f.is_symlink() and (f.suffix in STAGE_SUFFIX or f.name in STAGE_NAMES):
                files.append({'path': str(f.relative_to(repo)), 'stage': True})
    for fd in [FOOTPRINT_DIR, *p.get('footprint_dirs', [])]:
        for f in sorted((repo / fd).iterdir()):
            if f.is_file() and not f.is_symlink() and f.suffix == '.kicad_mod':
                files.append({'path': str(f.relative_to(repo)), 'stage': True})
    reads = [profile_rel, *TOOLS, *p.get('read_inputs', [])]
    if p.get('interface'):
        reads.append(p['interface']['roles'])
    if p.get('delta'):
        reads.append(p['delta']['record'])
        rec = json.loads((repo / p['delta']['record']).read_text())
        if rec.get('baseline', {}).get('netlist'):
            reads.append(rec['baseline']['netlist'])
    for r in sorted(set(reads)):
        files.append({'path': r, 'stage': False})
    for f in files:
        f['sha256'] = sha(repo / f['path'])
    return files


def lock_bytes(repo: Path, p: dict, profile_rel: str) -> bytes:
    lk = {'schema': 1, 'note': 'Generated by scripts/native_gate/runner.py lock. Do not edit by hand.',
          'profile': profile_rel, 'image': p['image'], 'kicad_version': p['kicad_version'],
          'files': lock_entries(repo, p, profile_rel)}
    return (json.dumps(lk, indent=1) + '\n').encode()


def cmd_lock(a: argparse.Namespace) -> int:
    repo = a.repo.resolve()
    p = load_profile(repo, a.profile)
    data = lock_bytes(repo, p, a.profile)
    target = repo / p['lock']
    if a.check:
        if not target.is_file() or target.read_bytes() != data:
            print(f"stale lock {p['lock']}; run: python3 scripts/native_gate/runner.py lock --profile {a.profile}", file=sys.stderr)
            return 1
        print(f"lock current: {p['lock']}")
        return 0
    target.write_bytes(data)
    print(f"wrote {p['lock']}")
    return 0


def verify_lock(repo: Path, p: dict, profile_rel: str) -> tuple[dict, list[str]]:
    lk = json.loads((repo / p['lock']).read_text())
    errs = []
    if lk.get('image') != p['image'] or lk.get('kicad_version') != p['kicad_version'] or lk.get('profile') != profile_rel:
        errs.append('lock image/version/profile differ from the profile')
    want = {f['path'] for f in lock_entries(repo, p, profile_rel)}
    have = {f['path'] for f in lk.get('files', [])}
    if want != have:
        errs.append(f'lock file set differs: missing {sorted(want - have)[:5]} extra {sorted(have - want)[:5]}')
    for f in lk.get('files', []):
        q = repo / f['path']
        if q.is_symlink() or not q.is_file():
            errs.append(f"input {f['path']}: missing or not a regular file"); continue
        if sha(q) != f['sha256']:
            errs.append(f"input {f['path']}: sha256 {sha(q)} != lock {f['sha256']}")
    return lk, errs


def stage(repo: Path, stage_dir: Path, lk: dict) -> None:
    for f in lk['files']:
        if not f.get('stage'):
            continue
        rel = Path(f['path'])
        if rel.is_absolute() or '..' in rel.parts:
            raise ev.Fail(f'unsafe staged path {rel}')
        if rel.suffix not in STAGE_SUFFIX and rel.name not in STAGE_NAMES:
            raise ev.Fail(f'unexpected staged name {rel}')
        src = repo / rel
        if src.is_symlink() or not src.is_file():
            raise ev.Fail(f'staged source {rel} not a regular file')
        dst = stage_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        if sha(dst) != f['sha256']:
            raise ev.Fail(f'staged copy {rel} hash mismatch')
    for q in stage_dir.rglob('*'):
        if q.is_symlink():
            raise ev.Fail(f'symlink in stage {q}')


def design_inputs(lk: dict, d: dict) -> dict:
    return {Path(f['path']).name: f['sha256'] for f in lk['files'] if f.get('stage') and str(Path(f['path']).parent) == d['dir']}


# ---------------------------------------------------------------- identity and receipts

def identities(repo: Path, profile_rel: str, p: dict) -> dict:
    ident = {'checkout_head': git(repo, 'rev-parse', 'HEAD'), 'github_sha': os.environ.get('GITHUB_SHA'),
             'github_event': os.environ.get('GITHUB_EVENT_NAME'), 'github_ref': os.environ.get('GITHUB_REF'),
             'github_run_id': os.environ.get('GITHUB_RUN_ID'),
             'github_run_attempt': os.environ.get('GITHUB_RUN_ATTEMPT'), 'workflow_ref': os.environ.get('GITHUB_WORKFLOW_REF'),
             'workflow_sha': os.environ.get('GITHUB_WORKFLOW_SHA'), 'profile': profile_rel}
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
    for f in ('.github/workflows/ci.yml', *TOOLS, profile_rel, p['lock']):
        q = repo / f
        ident.setdefault('tool_sha256', {})[f] = sha(q) if q.is_file() else None
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


# ---------------------------------------------------------------- container (unchanged from PR #14 apart from names)

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
    name = f'native-gate-{run_label[:12]}'
    g.container = name
    uid = f'{os.getuid()}:{os.getgid()}'
    args = ['run', '--name', name, '--label', f'{LABEL}={run_label}', '--network', 'none',
            '--cpus', '2', '--memory', '4g', '--memory-swap', '4g', '--pids-limit', '256',
            '--security-opt', 'no-new-privileges', '--cap-drop', 'ALL', '-u', uid, '-e', 'HOME=/tmp',
            '-v', f'{stage_dir}:/stage', '-v', f'{raw}:/out', '-v', f'{plan.parent}:/plan:ro',
            '-w', '/stage', image, 'python3', '/plan/inner.py', '--stage', '/stage', '--out', '/out',
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
        g.summary['container'] = dict(info)
        g.receipt('CLEANED_INCOMPLETE' if info['cleanup_verified'] else 'CLEANUP_FAILED_INCOMPLETE')
    return info


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
        raise ev.Fail(f'unexpected fake docker call {a}')


# ---------------------------------------------------------------- plan and evaluation

def build_plan(p: dict) -> dict:
    lim = p['limits']
    designs = []
    for name, d in p['designs'].items():
        designs.append({'name': name, 'stage_dir': d['dir'], 'schematic': d['schematic'], 'board': d['board'],
                        'deadline_s': lim['design_deadline_s'], 'refill_check': bool(d.get('refill_check'))})
    for name, c in p.get('expected_failure', {}).items():
        designs.append({'name': name, 'stage_dir': c['dir'], 'schematic': c['schematic'], 'board': c['board'],
                        'deadline_s': lim['design_deadline_s']})
    t = p['controls']['timeout']
    td = p['designs'][t['design']]
    designs.append({'name': 'control_timeout', 'stage_dir': td['dir'], 'schematic': td['schematic'], 'board': td['board'],
                    'deadline_s': t['deadline_s']})
    muts = []
    for name, c in p['controls']['mutations'].items():
        d = p['designs'][c['design']]
        muts.append({'name': name, 'stage_dir': d['dir'], 'source_board': d['board'],
                     'board': c['kind'] + '_mut.kicad_pcb', 'kind': c['kind'], 'spec': c.get('spec', {}),
                     'deadline_s': lim['design_deadline_s'], 'refill_check': bool(c.get('refill_check'))})
    return {'designs': designs, 'mutations': muts}


def custom_rules_text(rules: list[dict]) -> str:
    # must render exactly as scripts/a7_electronics.py custom_rules_text does
    out = ['(version 1)', '# Generated by scripts/a7_electronics.py from A7_STYLE custom_rules; recorded in',
           '# engineering/a7/verification/native_gate.json design_rule_delta.custom_rules. Do not edit by hand.']
    for r in rules:
        out.append(f'(rule "{r["name"]}"\n  (constraint {r["constraint"]} (min {r["min_mm"]}mm))\n  (condition "{r["condition"]}"))')
    return '\n'.join(out) + '\n'


def custom_rules_failures(repo: Path, p: dict) -> list[str]:
    errs = []
    rules = (p.get('design_rule_delta') or {}).get('custom_rules') or []
    for name, d in p['designs'].items():
        if not d.get('custom_rules'):
            continue
        f = repo / d['dir'] / d['custom_rules']
        if Path(d['custom_rules']).stem != Path(d['board']).stem:
            errs.append(f'{name}: custom rules file {d["custom_rules"]} is not the board\'s project rules file, KiCad would not load it')
        elif not f.is_file():
            errs.append(f'{name}: custom rules file {d["custom_rules"]} missing')
        elif f.read_text() != custom_rules_text(rules):
            errs.append(f'{name}: {d["custom_rules"]} differs from design_rule_delta.custom_rules')
    return errs


def rule_squeeze_reported(violations: list[dict], rules: list[str], pad: str) -> bool:
    """Every named custom rule appears in a native hole_clearance violation whose items include the squeezed pad."""
    ref, _, num = pad.partition('.')
    if not ref or not num or not rules:
        return False
    tag = f'pad {num} '
    return all(any(v.get('type') == 'hole_clearance' and f"rule '{rule}'" in v.get('description', '')
                   and any(tag in i.get('description', '') and i.get('description', '').endswith(f' of {ref}')
                           for i in v.get('items', []))
                   for v in violations) for rule in rules)


def design_expect(p: dict, name: str) -> dict:
    e = dict(p['designs'][name])
    e.update({k: p['drc'][k] for k in ('included_severities', 'ignored_checks')})
    e['kicad_version'] = p['kicad_version']
    return e


def evaluate_all(g: Gate, p: dict, lk: dict, raw: Path, info: dict) -> dict:
    res: dict = {'designs': {}, 'controls': {}}
    if info.get('timed_out') or info.get('exit_code') != 0:
        g.fail(f"inner run exit {info.get('exit_code')} timed_out={info.get('timed_out')}")
    g.failures += cleanup_failures(info)
    try:
        inner = ev.load_json(raw / 'inner_record.json')
    except ev.Fail as e:
        g.fail(str(e)); return res
    for f in ev.check_versions(inner, p['kicad_version']):
        g.fail(f)
    for name, d in p['designs'].items():
        r = ev.evaluate_design(name, design_expect(p, name), inner.get('designs', {}).get(name), raw / name, design_inputs(lk, d))
        res['designs'][name] = r
        g.failures += [f'{name}: {f}' for f in r['failures']]
    ctl = res['controls']
    for name, c in p.get('expected_failure', {}).items():
        r = ev.evaluate_expected_failure(c, inner.get('designs', {}).get(name), raw / name)
        ctl[name] = r
        if not r['ok']:
            g.fail(f'control {name}: {r["failures"]}')
    t = inner.get('designs', {}).get('control_timeout', {})
    timed = any(op.get('timed_out') for op in t.get('ops', {}).values())
    ctl['control_timeout'] = {'ok': timed, 'detail': {k: v.get('timed_out') for k, v in t.get('ops', {}).items()}}
    if not timed:
        g.fail('control_timeout: a too-short deadline did not time out')
    for name, c in p['controls']['mutations'].items():
        mr = inner.get('controls', {}).get(name, {})
        base = res['designs'].get(c['design'], {})
        e = design_expect(p, c['design'])
        e['refill_check'] = bool(c.get('refill_check'))
        out = raw / name
        out.mkdir(parents=True, exist_ok=True)
        for k in ('erc.json', 'netlist.xml'):
            if (raw / c['design'] / k).is_file() and not (out / k).exists():
                shutil.copyfile(raw / c['design'] / k, out / k)
        base_ops = inner.get('designs', {}).get(c['design'], {}).get('ops', {})
        fake = {'ops': {'erc': base_ops.get('erc'), 'netlist': base_ops.get('netlist'), 'drc': mr.get('ops', {}).get('drc')},
                'deadline_exceeded': False, 'stage_before': {}, 'stage_after': {}}
        r = ev.evaluate_design(name, e, fake, out, {})
        hit = [f for f in r['failures'] if any(s in f for s in c['must_report'])]
        # A mutation only proves detection if the unmutated design passed: a route break on an
        # unrouted board (PR #14 / A6) or a fill shift on a board with stale fills shows nothing.
        base_ok = base.get('ok') is True
        ok = base_ok and (not r['ok']) and bool(hit) and 'error' not in (mr.get('mutation') or {'error': 'missing'})
        if c['kind'] == 'fill_shift' and (mr.get('mutation') or {}).get('summary_unchanged') is not True:
            ok = False  # the control only proves something if area and vertex count stayed equal
        if c['kind'] == 'rule_squeeze':
            # the squeeze must sit between the board's own hole clearance and the custom minimum, so only the rule sees it
            gap = (mr.get('mutation') or {}).get('hole_gap_mm')
            base_min = (mr.get('mutation') or {}).get('project_min_hole_clearance_mm')
            mins = [r['min_mm'] for r in (p.get('design_rule_delta') or {}).get('custom_rules', []) if r['name'] in c['must_report']]
            if gap is None or base_min is None or not mins or not (base_min < gap < min(mins)):
                ok = False
            if any(f'DRC clearance' in f or 'shorting' in f for f in r['failures']):
                ok = False  # the added track must not also be caught by plain copper clearance
            # the native report itself must carry a hole_clearance violation that names the rule and the squeezed pad
            try:
                viol = json.loads((out / 'drc.json').read_text()).get('violations', [])
            except (OSError, ValueError):
                viol = []
            if not rule_squeeze_reported(viol, c['must_report'], str((c.get('spec') or {}).get('pad', ''))):
                ok = False
        if c['kind'] == 'route_break':
            # the reported break must be on the net whose segment was removed, not some unrelated one
            net = (mr.get('mutation') or {}).get('removed_track_net')
            try:
                items = json.loads((out / 'drc.json').read_text()).get('unconnected_items', [])
            except (OSError, ValueError):
                items = []
            if not net or not any(f'[{net}]' in i.get('description', '') for u in items for i in u.get('items', [])):
                ok = False
        ctl[name] = {'ok': ok, 'base_design_passed': base_ok, 'mutation': mr.get('mutation'), 'detected_by': hit[:5]}
        if not ok:
            g.fail(f'negative control {name} was not demonstrated (base passed={base_ok}, must report {c["must_report"]})')
    ctl.update(synthetic_controls(p, lk, inner, raw, p['controls']['synthetic_design']))
    for k, v in ctl.items():
        if k.startswith('synthetic_') and not v['ok']:
            g.fail(f'negative control {k} not detected')
    return res


def synthetic_controls(p: dict, lk: dict, inner: dict, raw: Path, name: str) -> dict:
    """Corrupt copies of the real record/reports; each must make the evaluator fail."""
    out: dict = {}
    e = design_expect(p, name)
    inputs = design_inputs(lk, p['designs'][name])
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
    v = ev.check_versions(dict(inner, pcbnew_version='9.0.7'), p['kicad_version'])
    out['synthetic_tool_version_mismatch'] = {'ok': bool(v), 'failures': v}
    lbl = 'synthetic-' + uuid.uuid4().hex
    fake = FakeDocker(lbl, rm_fails=True)
    c = cleanup_owned(lbl, time.monotonic() + 5, fake)
    out['synthetic_cleanup_failure'] = {'ok': bool(cleanup_failures({'cleanup': c})) and fake.rm_calls == 1,
                                        'failures': cleanup_failures({'cleanup': c})}
    return out


# ---------------------------------------------------------------- behavioral interface and authorized delta

def interface_and_delta(g: Gate, p: dict, raw: Path, td: Path) -> dict:
    out: dict = {}
    spec = p.get('interface')
    if spec:
        nl = {role: raw / design / 'netlist.xml' for role, design in spec['netlists'].items()}
        r = itf.check(nl, g.repo / spec['roles'])
        (raw / 'interface_check.json').write_text(json.dumps(r, indent=1) + '\n')
        bad = [c['id'] for c in r['checks'] if not c['passed']]
        out['interface'] = {'all_passed': r['all_passed'], 'checks': len(r['checks']), 'failed': bad, 'errors': r['errors'],
                            'roles_sha256': r['roles_sha256']}
        if not r['all_passed']:
            g.fail(f"behavioral interface assertions failed: {bad or r['errors']}")
        if len(r['checks']) < spec.get('min_checks', 1):
            g.fail(f"interface ran {len(r['checks'])} < {spec['min_checks']} assertions")
        # negative control: an unresolved role must make the same run fail
        roles = json.loads((g.repo / spec['roles']).read_text())
        roles.setdefault('controller', {})['jack_in.tip'] = {'unresolved': 'synthetic control'}
        tmp = td / 'roles_unresolved.json'; tmp.write_text(json.dumps(roles))
        rr = itf.check(nl, tmp)
        out['control_interface_unresolved_role'] = {'ok': rr['all_passed'] is False}
        if rr['all_passed'] is not False:
            g.fail('negative control: an unresolved role did not fail the interface assertions')
    dspec = p.get('delta')
    if dspec:
        cand = raw / dspec['candidate_design'] / 'netlist.xml'
        r = dl.check(g.repo / dspec['record'], cand, g.repo)
        (raw / 'delta_check.json').write_text(json.dumps(r, indent=1) + '\n')
        out['delta'] = {'ok': r['ok'], 'failures': r['failures'][:20], 'observed': len(r.get('observed_delta', []))}
        if not r['ok']:
            g.fail(f"authorized-delta check failed: {r['failures'][:5]}")
        # negative control: one moved pin in an otherwise identical netlist must be refused
        if cand.is_file():
            mut = td / 'delta_mut.xml'
            text = cand.read_text()
            mut.write_text(mutate_netlist(text))
            rm = dl.check(g.repo / dspec['record'], mut, g.repo)
            out['control_delta_unauthorized_pin'] = {'ok': rm['ok'] is False, 'failures': rm['failures'][:3]}
            if rm['ok'] is not False:
                g.fail('negative control: an unauthorized pin move passed the delta check')
    return out


def mutate_netlist(text: str) -> str:
    """Move the last node of the first multi-node net to the next net (an unauthorized connectivity change)."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(text)
    nets = [n for n in root.findall('./nets/net') if len(n.findall('node')) > 1]
    if len(nets) < 2:
        raise ev.Fail('netlist too small for the delta control')
    node = nets[0].findall('node')[-1]
    nets[0].remove(node)
    nets[1].append(node)
    return ET.tostring(root, encoding='unicode')


# ---------------------------------------------------------------- regeneration preservation, A5, evidence

def regeneration(g: Gate, p: dict) -> dict:
    spec = p.get('regeneration')
    if not spec:
        g.fail('profile defines no regeneration-preservation step')
        return {}
    if not spec.get('check_command') or not spec.get('protected'):
        g.fail('profile regeneration step has no check_command or no protected board')
        return {'spec': spec}
    protected = [g.repo / q for q in spec['protected']]
    before = {str(q.relative_to(g.repo)): sha(q) for q in protected}
    raw = g.out / 'raw'
    cmd = [a.replace('{raw}', str(raw)).replace('{python}', sys.executable) for a in spec['check_command']]
    try:
        pr = subprocess.run(cmd, cwd=g.repo, capture_output=True, text=True, timeout=120)
        code, tail = pr.returncode, (pr.stdout + pr.stderr)[-3000:]
    except subprocess.TimeoutExpired:
        code, tail = None, 'timed out'
    after = {str(q.relative_to(g.repo)): sha(q) for q in protected}
    res = {'command': cmd, 'exit_code': code, 'output_tail': tail, 'protected_before': before, 'protected_after': after}
    if before != after:
        g.fail('authoritative board changed during normal regeneration')
    if code != 0:
        g.fail(f'derived files are stale or regeneration failed (exit {code})')
    return res


def a5_integrity(repo: Path) -> dict:
    p = subprocess.run([sys.executable, 'scripts/verify_seed.py', '--manifest', 'provenance/seed-manifest.json', '--repo', '.'],
                       cwd=repo, capture_output=True, text=True, timeout=300)
    return {'verify_seed_exit': p.returncode, 'verify_seed_tail': p.stdout[-300:], 'tree_sha256': tree_sha(repo / 'engineering/a5'),
            'git_status': git(repo, 'status', '--porcelain', '--', 'engineering/a5')}


def copy_evidence(g: Gate, raw: Path, p: dict) -> dict:
    ev_dir = g.out / 'evidence'
    ev_dir.mkdir(exist_ok=True)
    allowed = set(p['evidence']['allowed_names'])
    total = 0
    listing = {}
    for q in sorted(raw.rglob('*')):
        if not q.is_file() or q.is_symlink() or q.name not in allowed:
            continue
        rel = q.relative_to(raw)
        size = q.stat().st_size
        if total + size > EVIDENCE_CAP:
            g.fail(f'evidence cap exceeded at {rel}')
            break
        dst = ev_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(q, dst)
        total += size
        listing[str(rel)] = sha(q)
    return {'bytes': total, 'files': listing}


def final_status(p: dict, failures: list[str]) -> str:
    if failures:
        return 'FAIL'
    return 'INFRASTRUCTURE_PASS' if p['kind'] == 'infrastructure' else 'PASS'


def cmd_run(a: argparse.Namespace) -> int:
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
    p: dict = {'kind': 'unknown'}
    try:
        p = load_profile(repo, a.profile)
        g.summary['profile'] = {'path': a.profile, 'name': p['profile'], 'kind': p['kind']}
        g.summary['board_result'] = (
            'NONE: infrastructure run on fixtures; this is not an A7 (or any) board result'
            if p['kind'] == 'infrastructure' else 'candidate: ' + str(p.get('candidate')))
        g.summary['note'] = BOARD_NOTE
        if p['kind'] == 'revision' and not p.get('candidate'):
            g.fail(f"NO_CANDIDATE: profile {a.profile} names no authoritative board ({p.get('candidate_note', 'none yet')})")
            g.receipt('NO_CANDIDATE')
            print(json.dumps({'status': 'NO_CANDIDATE', 'failures': g.failures}, indent=1))
            return 1
        g.summary['identity'] = identities(repo, a.profile, p)
        g.summary['a5_before'] = a5_integrity(repo)
        if g.summary['a5_before']['verify_seed_exit'] != 0 or g.summary['a5_before']['git_status'] != '':
            g.fail('A5 checkpoint not intact before the run')
        g.summary['image'] = p['image']
        lk, errs = verify_lock(repo, p, a.profile)
        g.failures += errs
        g.failures += custom_rules_failures(repo, p)
        g.summary['input_lock'] = {f['path']: f['sha256'] for f in lk.get('files', [])}
        tested = {n: sha(repo / d['dir'] / d['board']) for n, d in p['designs'].items()}
        g.summary['tested_board_sha256'] = tested
        if errs:
            raise ev.Fail('input lock mismatch; native run skipped')
        with tempfile.TemporaryDirectory(prefix='native-gate-') as td:
            td = Path(td)
            stage_dir, raw, plan_dir = td / 'stage', out / 'raw', td / 'plan'
            for d in (stage_dir, raw, plan_dir):
                d.mkdir()
            stage(repo, stage_dir, lk)
            plan = plan_dir / 'plan.json'
            plan.write_text(json.dumps(build_plan(p), indent=1))
            shutil.copyfile(repo / INNER, plan_dir / 'inner.py')
            for q in (stage_dir, raw, plan_dir):
                q.chmod(0o777 if q != plan_dir else 0o755)
            g.receipt('STAGED_INCOMPLETE')
            reserve = p['limits']['cleanup_reserve_s']
            budget = min(p['limits']['native_deadline_s'], g.deadline - time.monotonic() - reserve)
            info = run_container(g, p['image'], stage_dir, raw, plan, budget, reserve)
            res = evaluate_all(g, p, lk, raw, info)
            g.summary['results'] = res
            g.summary['interface_and_delta'] = interface_and_delta(g, p, raw, td)
            g.summary['regeneration'] = regeneration(g, p)
            g.summary['evidence'] = copy_evidence(g, raw, p)
            shutil.copyfile(plan, out / 'plan.json')
            g.summary['plan_sha256'] = sha(out / 'plan.json')
        for n, d in p['designs'].items():
            if sha(repo / d['dir'] / d['board']) != tested[n]:
                g.fail(f'tested board {n} changed during the run')
    except (ev.Fail, KeyError, ValueError, OSError, subprocess.SubprocessError) as e:
        g.fail(f'gate aborted: {type(e).__name__}: {e}')
    try:
        g.summary['a5_after'] = a5_integrity(repo)
        b = g.summary.get('a5_before', {})
        if g.summary['a5_after']['tree_sha256'] != b.get('tree_sha256') or g.summary['a5_after']['verify_seed_exit'] != 0 \
                or g.summary['a5_after']['git_status'] != '':
            g.fail('A5 checkpoint changed during the run')
    except (OSError, subprocess.SubprocessError) as e:
        g.fail(f'A5 after-check failed: {e}')
    g.receipt(final_status(p, g.failures))
    print(json.dumps({'status': g.summary['status'], 'board_result': g.summary.get('board_result'),
                      'failures': g.failures[:50]}, indent=1))
    return 0 if not g.failures else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    lk = sp.add_parser('lock'); lk.add_argument('--profile', required=True); lk.add_argument('--check', action='store_true')
    lk.add_argument('--repo', type=Path, default=REPO)
    r = sp.add_parser('run'); r.add_argument('--profile', required=True); r.add_argument('--repo', type=Path, default=REPO)
    r.add_argument('--out', type=Path, required=True)
    r.add_argument('--deadline-s', type=float, default=11 * 60, help='native run budget incl. cleanup reserve')
    a = ap.parse_args()
    return cmd_lock(a) if a.cmd == 'lock' else cmd_run(a)


if __name__ == '__main__':
    sys.exit(main())
