#!/usr/bin/env python3
"""A7 Workflow F preparation: valid BLOCKED reports are not release eligibility."""
import argparse
import datetime as dt
import hashlib
import json
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUAL = Path('engineering/a7/qualification')
REQUIRED = frozenset('jack-continuity jack-dimensions switch-fit harness-depth pmma-supports fixture-contact firmware-waveforms power-current cv-thru-calibration startup-reset rail-collapse partial-rails u7-stress ldo-reverse load-short effective-capacitance thermal-optical cv-noise service-envelope'.split())
IDENTITY_PATHS = {
    'board': 'engineering/a7/electronics/controller/controller.kicad_pcb',
    'population': 'engineering/a7/electronics/controller/board_placement.json',
    'schematic': 'engineering/a7/electronics/controller/controller.kicad_sch',
    'firmware': 'engineering/a5/firmware/dist/light_block_A5.bin',
    'firmware_sources': 'engineering/a5/firmware/dist/source_files.sha256',
    'configuration': 'engineering/a5/firmware/include/lb_config.h',
    'mechanical': 'engineering/a7/mechanical/layout.json',
    'fixture': 'engineering/a7/fixture/manifest.json',
    'assembly_manifest': 'engineering/a7/procurement/assembly-manifest.json',
}
REQUIRED_EVIDENCE = {'jack-continuity': ['terminal_matrix', 'ts_plug_identity', 'trs_plug_identity', 'jack_lot', 'contact_photos'], 'jack-dimensions': ['axis_measurements', 'slot_lead_measurements', 'nut_washer_fit', 'instrument_identity'], 'switch-fit': ['contact_truth_table', 'land_peg_measurements', 'setup_access', 'switch_lot'], 'harness-depth': ['polarity_matrix', 'full_length_routing', 'bend_measurements', 'installed_depth', 'cable_identity'], 'pmma-supports': ['material_identity', 'pocket_tolerances', 'tightening_log', 'retention_load', 'print_settings'], 'fixture-contact': ['registration_measurements', 'contact_short_matrix', 'stroke_force', 'support_photos'], 'firmware-waveforms': ['programming_readback', 'stored_configuration', 'led_lot', 'left_waveform', 'right_waveform', 'timebase_setup'], 'power-current': ['supply_setup', 'rail_waveforms', 'current_log', 'load_matrix'], 'cv-thru-calibration': ['cv_sweep', 'vdd_adc_thru_data', 'calibration_coefficients', 'residuals'], 'startup-reset': ['reset_fault_enable_waveforms', 'rail_waveforms', 'configuration_readback'], 'rail-collapse': ['rail_enable_waveforms', 'collapse_load_conditions'], 'partial-rails': ['rail_combination_matrix', 'injection_reverse_current', 'rail_waveforms'], 'u7-stress': ['input_supply_waveforms', 'differential_stress_calculation', 'probe_identity'], 'ldo-reverse': ['rail_waveforms', 'reverse_current', 'temperature', 'sequence_conditions'], 'load-short': ['short_recovery_waveforms', 'current_temperature', 'fault_log', 'load_conditions'], 'effective-capacitance': ['component_lot', 'bias_temperature', 'capacitance', 'ripple_waveforms'], 'thermal-optical': ['temperature_series', 'ir_corrections', 'material_lot', 'optical_photos', 'ambient_conditions'], 'cv-noise': ['synchronous_waveforms', 'noise_statistics', 'probe_wiring', 'data_patterns'], 'service-envelope': ['envelope_dimensions', 'insertion_extraction_force', 'replacement_record', 'before_after_photos', 'part_identity']}
MATERIALS = frozenset(['jack', 'switch', 'finished_cables', 'pmma_petg_hardware', 'fixture', 'assembly_service'])
# What can resolve a gate: digital work in the cloud project, an owner choice, access to
# outside evidence (supplier answers, documents), or work that needs real hardware.
CLASSES = ('CLOUD_DIGITAL', 'OWNER_DECISION', 'ACCESS_EVIDENCE_HOLD', 'PHYSICAL_ONLY')
CLASS_JA = {'CLOUD_DIGITAL': 'クラウドで進められるデジタル作業', 'OWNER_DECISION': 'オーナーの判断',
            'ACCESS_EVIDENCE_HOLD': '外部の証跡・アクセス待ち', 'PHYSICAL_ONLY': '実機が必要'}
# DESIGN: a project design record; SOURCED/MIRROR/UNVERIFIED/INFERRED: derived from the cited fact.
CONFIDENCES = ('SOURCED', 'MIRROR', 'UNVERIFIED', 'INFERRED', 'DESIGN', 'ASSUMED', 'UNRESOLVED')
RUN_TEMPLATES = QUAL / 'run-templates'
CHECKLIST = Path('doc/src/content/docs/project/order-checklist.mdx')
PROCEDURE_LISTS = ('inputs', 'tools', 'preconditions', 'steps')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identities(root):
    return {key: {'path': path, 'sha256': digest(root / path) if (root / path).is_file() else None}
            for key, path in IDENTITY_PATHS.items()}


def raw_ok(item, root):
    if not isinstance(item, dict) or set(item) != {'path', 'sha256'}:
        return False
    path = item['path']
    if not isinstance(path, str) or not isinstance(item['sha256'], str):
        return False
    full = (root / path).resolve()
    return full.is_relative_to(root.resolve()) and full.is_file() and digest(full) == item['sha256']


def text_fields(record, names):
    return all(isinstance(record.get(n), str) and record[n].strip() and
               record[n] not in ('NOT_MEASURED', 'NOT_RUN', 'TBD') for n in names)


def artifact_errors(key, artifact, root):
    errors = []
    try:
        sys.path.insert(0, str(ROOT / 'scripts'))
        name = 'a7_fixture' if key == 'fixture' else 'a7_procurement'
        spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
        producer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(producer)
        producer.validate_report(artifact, root)
    except (ValueError, KeyError, TypeError, OSError) as e:
        errors.append(key + ': producer validation failed: ' + str(e))
    return errors


def fact_confidence(fact):
    if 'INFERRED' in fact.get('conditions', ''):
        return 'INFERRED'
    if fact.get('provenance') == 'PRIMARY-SPEC':
        return 'SOURCED'
    return 'MIRROR' if 'mirror' in fact.get('conditions', '').lower() else 'UNVERIFIED'


def resolve(trace, root):
    """Return (value, quote, stated confidence) a trace points at; raise ValueError when it does not resolve."""
    if not isinstance(trace, dict) or not isinstance(trace.get('path'), str):
        raise ValueError('trace needs a repository path')
    full = (root / trace['path']).resolve()
    if not full.is_relative_to(root.resolve()) or not full.is_file():
        raise ValueError('trace path missing: ' + trace['path'])
    forms = [k for k in ('fact_id', 'pointer', 'quote') if k in trace]
    if len(forms) != 1 or set(trace) != {'path', forms[0]}:
        raise ValueError('trace needs exactly one of fact_id, pointer or quote: ' + trace['path'])
    if 'quote' in trace:
        text = full.read_text()
        if not isinstance(trace['quote'], str) or not trace['quote'] or trace['quote'] not in text:
            raise ValueError('quote not found in ' + trace['path'])
        return trace['quote'], trace['quote'], None
    data = json.loads(full.read_text())
    if 'fact_id' in trace:
        facts = [f for f in data.get('facts', []) if f.get('fact_id') == trace['fact_id']]
        if len(facts) != 1:
            raise ValueError('fact missing or duplicate: ' + str(trace['fact_id']))
        return facts[0], None, None
    pointer = trace['pointer']
    if not isinstance(pointer, str) or not pointer.startswith('/'):
        raise ValueError('pointer must be a JSON pointer')
    node, parent = data, None
    parts = pointer[1:].split('/')
    for part in parts:
        parent = node
        if isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        elif isinstance(node, dict) and part in node:
            node = node[part]
        else:
            raise ValueError('pointer does not resolve: ' + trace['path'] + pointer)
    return node, None, sibling_confidence(parent, parts[-1])


def sibling_confidence(parent, key):
    """The confidence a JSON record states next to a value, e.g. tolerance -> tolerance_confidence."""
    if not isinstance(parent, dict):
        return None
    names = {'tolerance': 'tolerance_confidence', 'tol': 'tol_confidence'}
    for name in (key + '_confidence', names.get(key), 'confidence' if key in ('nominal', 'value', 'band') else None):
        if name and isinstance(parent.get(name), str):
            return parent[name]
    return None


def acceptance_errors(procedure, root):
    """Every acceptance value must equal what its source says; confidence must match the source."""
    errors = []
    items = procedure.get('acceptance')
    if not isinstance(items, list) or not items or any(not isinstance(a, dict) for a in items):
        return [procedure['id'] + ': acceptance must be a non-empty object list']
    ids = [a.get('id') for a in items]
    if len(ids) != len(set(ids)) or not all(isinstance(i, str) and i for i in ids):
        errors.append(procedure['id'] + ': acceptance ids must be unique')
    for a in items:
        where = procedure['id'] + '/' + str(a.get('id')) + ': '
        if a.get('confidence') not in CONFIDENCES or not text_fields(a, ['criterion', 'unit']):
            errors.append(where + 'invalid confidence, criterion or unit')
            continue
        if a['confidence'] == 'UNRESOLVED':
            if a.get('value') is not None or not text_fields(a, ['decided_by']) or 'source' in a:
                errors.append(where + 'UNRESOLVED needs value null, decided_by and no source')
            continue
        try:
            got, quote, stated = resolve(a.get('source'), root)
            if stated in ('ASSUMED', 'INFERRED') and a['confidence'] != stated:
                errors.append(where + 'the cited record marks this value ' + stated)
            if isinstance(got, dict) and 'fact_id' in a['source']:
                if (got.get('value'), got.get('unit')) != (a.get('value'), a['unit']):
                    errors.append(where + 'value/unit differs from the cited fact')
                if fact_confidence(got) != a['confidence']:
                    errors.append(where + 'confidence differs from the cited fact (' + fact_confidence(got) + ')')
            else:
                if quote is not None:
                    if not isinstance(a.get('value'), str) or a['value'] not in quote:
                        errors.append(where + 'value is not in the cited quote')
                elif got != a.get('value'):
                    errors.append(where + 'value differs from the cited record')
                if a['confidence'] not in ('DESIGN', 'ASSUMED', 'INFERRED'):
                    errors.append(where + 'record citations are DESIGN, ASSUMED or INFERRED')
            if a['confidence'] in ('ASSUMED', 'INFERRED') and 'fact_id' not in a['source']:
                marker = resolve(a.get('confidence_trace'), root)[0]
                if a['confidence'] not in json.dumps(marker, ensure_ascii=False):
                    errors.append(where + 'confidence_trace does not say ' + a['confidence'])
        except (ValueError, OSError, json.JSONDecodeError) as e:
            errors.append(where + str(e))
    return errors


def gate_keys(plan):
    keys = {'artifact:fixture', 'artifact:assembly_manifest', 'owner_prototype_route', 'manufacturing_release',
            'records:receipt-reuse', 'run:*'}
    keys |= {'material:' + k for k in MATERIALS}
    for p in plan['procedures']:
        keys |= {'criterion:' + p['id'], 'run:' + p['id']}
    return keys


def schema(plan, records):
    if not isinstance(plan, dict) or not isinstance(records, dict):
        raise ValueError('plan and records must be objects')
    if plan.get('schema') != 1 or plan.get('variant') != 'fr4-3hp' or records.get('schema') != 1:
        raise ValueError('unsupported plan/record schema or baseline variant')
    procedures = plan.get('procedures')
    if not isinstance(procedures, list) or any(not isinstance(p, dict) for p in procedures):
        raise ValueError('procedures must be objects')
    ids = [p.get('id') for p in procedures]
    if len(ids) != len(REQUIRED) or set(ids) != REQUIRED:
        raise ValueError('missing/duplicate/unexpected mandatory procedure')
    for p in procedures:
        if not text_fields(p, ['title', 'setup', 'expected', 'basis', 'raw_evidence_required', 'next_action']):
            raise ValueError('incomplete procedure '+p['id'])
        if p.get('variant') != 'fr4-3hp' or p.get('observation') != 'NOT_MEASURED' or p.get('result') != 'NOT_RUN':
            raise ValueError('plans cannot contain physical observations')
        if p.get('required_evidence_kinds') != REQUIRED_EVIDENCE[p['id']]:
            raise ValueError('missing or changed required evidence kinds '+p['id'])
        if p.get('criterion_status') not in ['UNRESOLVED', 'REVIEWED']:
            raise ValueError('invalid criterion status')
        if p.get('criterion_class') not in CLASSES:
            raise ValueError('invalid criterion class '+p['id'])
        for key in PROCEDURE_LISTS:
            items = p.get(key)
            if not isinstance(items, list) or not items or not all(isinstance(x, str) and x.strip() for x in items):
                raise ValueError('procedure '+p['id']+' needs non-empty '+key)
        record = p.get('record')
        if (not isinstance(record, dict) or set(record) != set(REQUIRED_EVIDENCE[p['id']])
                or not all(isinstance(v, str) and v.strip() for v in record.values())):
            raise ValueError('record template must describe exactly the required evidence kinds '+p['id'])
        errors = acceptance_errors(p, ROOT)
        if errors:
            raise ValueError('untraceable acceptance: ' + '; '.join(errors))
    actions = plan.get('owner_actions')
    if not isinstance(actions, list) or not actions or any(not isinstance(a, dict) for a in actions):
        raise ValueError('owner_actions must be a non-empty object list')
    if len({a.get('id') for a in actions}) != len(actions):
        raise ValueError('duplicate owner action')
    keys = gate_keys(plan)
    for a in actions:
        if not text_fields(a, ['id', 'title', 'detail']) or not isinstance(a.get('unblocks'), list) or not a['unblocks']:
            raise ValueError('incomplete owner action')
        for g in a['unblocks']:
            if not isinstance(g, str) or (g not in keys and not g.startswith('assembly:')):
                raise ValueError('owner action '+a['id']+' names unknown gate '+str(g))
    for key in ['runs', 'material_observations']:
        if not isinstance(records.get(key), list) or any(not isinstance(r, dict) for r in records[key]):
            raise ValueError(key+' must be an object list')
    run_ids = [r.get('run_id') for r in records['runs']]
    if any(not isinstance(i, str) or not i.strip() for i in run_ids) or len(run_ids) != len(set(run_ids)):
        raise ValueError('run IDs must be unique, nonempty strings')
    if any(r.get('procedure') not in REQUIRED for r in records['runs']):
        raise ValueError('unknown procedure in run')


def evaluate(root, plan, records, today=None):
    schema(plan, records)
    today = today or dt.datetime.now(dt.timezone.utc).date()
    ids = identities(root)
    gates = {}
    reasons = []

    def block(gate, cls, reason):
        gates.setdefault(gate, {'gate': gate, 'class': cls, 'reasons': []})['reasons'].append(reason)
        reasons.append(reason)
    for k, v in ids.items():
        if v['sha256'] is None:
            block('artifact:' + k, 'CLOUD_DIGITAL', 'missing artifact: '+k)
    binding = {k: v['sha256'] for k, v in ids.items()}
    for key in ['fixture', 'assembly_manifest']:
        path = root / IDENTITY_PATHS[key]
        if path.is_file():
            artifact = json.loads(path.read_text())
            if not isinstance(artifact, dict):
                raise ValueError(key+': artifact must be an object')
            gate = 'artifact:' + key
            for e in artifact_errors(key, artifact, root):
                block(gate, 'CLOUD_DIGITAL', e)
            if key == 'fixture' and (artifact.get('digital_fixture_complete') is not True or artifact.get('fresh_native_verified') is not True):
                block(gate, 'CLOUD_DIGITAL', 'fixture digital design incomplete or unverified')
            pending = artifact.get('blockers')
            if key == 'assembly_manifest' and isinstance(pending, list) and all(
                    isinstance(b, dict) and b.get('class') in CLASSES and text_fields(b, ['id', 'text']) for b in pending):
                for b in pending:
                    block('assembly:' + b['id'], b['class'], 'assembly_manifest: ' + b['id'] + ': ' + b['text'])
            elif pending:
                block(gate, 'CLOUD_DIGITAL', key+': unresolved preparation blockers')
            inputs = artifact.get('inputs_sha256')
            if not isinstance(inputs, dict) or not inputs:
                block(gate, 'CLOUD_DIGITAL', key+': input identity binding missing')
            elif not all(raw_ok({'path': p, 'sha256': h}, root) for p, h in inputs.items()):
                block(gate, 'CLOUD_DIGITAL', key+': stale input identity binding')
    # A file name or asserted digest is not evidence: retained bytes must match.
    plan_hash = hashlib.sha256(json.dumps(plan, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    outcomes = []
    for p in plan['procedures']:
        why = []
        if p['criterion_status'] != 'REVIEWED' or p.get('missing_criterion') != '' or not raw_ok(p.get('criterion_review'), root):
            why.append('criterion unresolved or review receipt missing')
        runs = [r for r in records['runs'] if r.get('procedure') == p['id']]
        if not runs:
            why.append('NOT_MEASURED: no run')
        else:
            dated = []
            for run in runs:
                try:
                    stamp = dt.datetime.fromisoformat(run['performed_at'].replace('Z', '+00:00'))
                    if stamp.tzinfo is None or stamp.date() > today:
                        raise ValueError('invalid/future time')
                    dated.append((stamp, run))
                except (KeyError, TypeError, ValueError, AttributeError):
                    why.append('history has missing/invalid/future execution time')
            if len({stamp for stamp, _ in dated}) != len(dated):
                why.append('ambiguous duplicate execution times')
            # List reordering cannot hide a newer failed/reworked run.
            r = max(dated, key=lambda item: item[0])[1] if dated else runs[-1]
            if r.get('result') != 'PASS' or r.get('evidence_kind') != 'BENCH_RECORD' or r.get('synthetic') is not False:
                why.append('latest run is not an actual passing BENCH_RECORD')
            if r.get('identities') != binding or r.get('plan_sha256') != plan_hash:
                why.append('wrong/stale board, population, firmware, configuration or plan')
            if not text_fields(r, ['unit_id', 'operator', 'performed_at', 'instruments', 'setup', 'conditions',
                                   'observations', 'criterion_comparison', 'next_action', 'assembly_deviations']):
                why.append('incomplete Workflow F execution record')
            raw = r.get('raw_evidence')
            if not isinstance(raw, list) or not raw or any(not isinstance(x, dict) for x in raw):
                why.append('raw evidence missing, incomplete or changed')
            else:
                kinds = [x.get('kind') for x in raw]
                paths = [x.get('path') for x in raw]
                if (any(not isinstance(k, str) for k in kinds) or len(kinds) != len(set(kinds))
                        or not set(REQUIRED_EVIDENCE[p['id']]).issubset(kinds)
                        or any(not isinstance(path, str) for path in paths) or len(paths) != len(set(paths))
                        or not all(set(x) == {'kind', 'path', 'sha256'} and
                                   raw_ok({'path': x['path'], 'sha256': x['sha256']}, root) for x in raw)):
                    why.append('required raw evidence kinds missing, duplicate, incomplete or changed')
            try:
                performed = dt.datetime.fromisoformat(r['performed_at'].replace('Z', '+00:00'))
                if performed.tzinfo is None or performed.date() > today:
                    raise ValueError('invalid/future execution time')
            except (KeyError, TypeError, ValueError, AttributeError):
                why.append('missing/invalid/future execution time')
            if not raw_ok(r.get('review'), root):
                why.append('independent execution review absent')
        outcomes.append({'id': p['id'], 'status': 'BLOCKED' if why else 'PASS', 'reasons': why})
        for w in why:
            if w.startswith('criterion'):
                block('criterion:' + p['id'], p['criterion_class'], p['id']+': '+w)
            else:
                block('run:' + p['id'], 'PHYSICAL_ONLY', p['id']+': '+w)
    observations = records['material_observations']
    for key in sorted(MATERIALS):
        matches = [m for m in observations if m.get('material') == key]
        if len(matches) != 1:
            block('material:'+key, 'ACCESS_EVIDENCE_HOLD', 'material '+key+': missing or ambiguous dated observation')
            continue
        m = matches[0]
        try:
            seen = dt.date.fromisoformat(m['observed_on'])
            expires = dt.date.fromisoformat(m['valid_until'])
            current = seen <= today <= expires
        except (KeyError, TypeError, ValueError):
            current = False
        if not current or m.get('identities') != binding or m.get('available_for_proposed_order') is not True or not raw_ok(m.get('source'), root):
            block('material:'+key, 'ACCESS_EVIDENCE_HOLD', 'material '+key+': stale/unavailable/unbound source observation')
    route = records.get('owner_prototype_route')
    if not isinstance(route, dict) or route.get('identities') != binding or not text_fields(route, ['scope', 'quantity', 'constraints']) or not raw_ok(route.get('approval'), root):
        block('owner_prototype_route', 'OWNER_DECISION', 'owner-approved sample/prototype route absent for this revision and quantity')
    release = records.get('manufacturing_release')
    if not isinstance(release, dict) or release.get('identities') != binding or not raw_ok(release.get('approval'), root) or not raw_ok(release.get('reviewed_order_files'), root):
        block('manufacturing_release', 'OWNER_DECISION', 'reviewed manufacturing files and explicit revision-bound owner release absent')
    # One retained file cannot stand in for several approval roles, nor raw evidence for two procedures.
    # Keyed on the resolved file and on its bytes, so '..' spellings or byte-identical copies cannot evade it.
    roles = {}
    def use(item, role):
        if isinstance(item, dict) and isinstance(item.get('path'), str):
            full = (root / item['path']).resolve()
            roles.setdefault('file ' + str(full.relative_to(root.resolve()) if full.is_relative_to(root.resolve()) else full), set()).add(role)
            content = digest(full) if full.is_file() else item.get('sha256')
            if isinstance(content, str):
                roles.setdefault('bytes ' + content, set()).add(role)
    for p in plan['procedures']:
        use(p.get('criterion_review'), 'criterion_review')
    for run in records['runs']:
        if isinstance(run, dict):
            use(run.get('review'), 'execution_review')
            raw_items = run.get('raw_evidence')
            for x in raw_items if isinstance(raw_items, list) else []:
                use(x, 'raw:' + str(run.get('procedure')))
    for m in observations:
        if isinstance(m, dict):
            use(m.get('source'), 'material_source')
    if isinstance(route, dict):
        use(route.get('approval'), 'prototype_approval')
    if isinstance(release, dict):
        use(release.get('approval'), 'release_approval')
        use(release.get('reviewed_order_files'), 'reviewed_order_files')
    for path in sorted(q for q, r in roles.items() if len(r) > 1):
        block('records:receipt-reuse', 'ACCESS_EVIDENCE_HOLD', 'receipt reused across roles: ' + path + ' (' + ', '.join(sorted(roles[path])) + ')')
    return {'schema': 1, 'variant': 'fr4-3hp', 'report_validation': 'VALID',
            'order_eligibility': 'BLOCKED' if reasons else 'ELIGIBLE_FOR_RECORDED_SCOPE',
            'manufacturing_release': 'NOT_ESTABLISHED' if reasons else 'RECORDED_APPROVAL_REQUIRES_HUMAN_VERIFICATION',
            'order_submitted': 'NOT_ESTABLISHED', 'identities': ids, 'plan_sha256': plan_hash,
            'procedures': outcomes, 'blockers': reasons, 'gates': list(gates.values()),
            'gate_counts': {c: sum(1 for g in gates.values() if g['class'] == c) for c in CLASSES},
            'optional_variants': plan['optional_variants'],
            'limit': 'Schema validation is not measurement authenticity, hardware approval, a release authorization or an order. No order is submitted by this command.'}


def show(value):
    return '—' if value is None else '`' + json.dumps(value, ensure_ascii=False).replace('`', "'") + '`'


def trace_text(trace):
    if not trace:
        return '—'
    form = next(k for k in ('fact_id', 'pointer', 'quote') if k in trace)
    detail = trace[form] if form != 'quote' else '引用'
    return '`' + trace['path'] + '` ' + ('`' + detail + '`' if form != 'quote' else detail)


def markdown(plan, report):
    lines = ['# A7 物理評価の準備と readiness', '', '**未実施・製造リリースなし。** この文書は `scripts/a7_readiness.py` の生成物です。', '',
             'レポート検証: '+report['report_validation']+'。発注適格性: **'+report['order_eligibility']+'**。', '',
             '## 共通記録 (Workflow F)', '',
             '各実施は `run-templates/<手順ID>.json` をコピーし、unit、計器、条件、raw証跡（ファイルとSHA-256）、結果、次の行動を埋めて `records.json` の runs に追加します。'
             '雛形の identities と plan_sha256 は生成時点の値です。実施前に `python3 scripts/a7_readiness.py --check` が通ることを確認し、変わっていれば雛形を取り直します。'
             '失敗や再加工を上書きせず別 run として追加します。', '',
             '受入値の確度: SOURCED = メーカー一次資料、MIRROR = 販売店掲載の写し、UNVERIFIED = 出典が未確認の記録、INFERRED = 推定、DESIGN = このプロジェクトの設計記録、ASSUMED = 仮定、UNRESOLVED = 未決（決める主体を記載）。'
             '値はすべて出典と照合済みで、照合できない値は生成時にエラーになります。', '',
             '## 未実施の手順', '']
    for p in plan['procedures']:
        lines += ['### '+p['id']+' — '+p['title'], '', '- 関連: '+p['issues'], '- 概要: '+p['setup'],
                  '- 根拠: `'+p['basis']+'`', '- 未決: '+p['missing_criterion']+'（区分: '+CLASS_JA[p['criterion_class']]+'）',
                  '- 観測: NOT_MEASURED。結果: NOT_RUN。', '- 次: '+p['next_action'], '', '準備するもの:', '']
        lines += ['- '+x for x in p['inputs']] + ['', '計器・道具:', ''] + ['- '+x for x in p['tools']]
        lines += ['', '実施前の条件:', ''] + ['- '+x for x in p['preconditions']]
        lines += ['', '手順:', ''] + [str(i)+'. '+x for i, x in enumerate(p['steps'], 1)]
        lines += ['', '記録する raw 証跡（種別ごとに別ファイル）:', '', '| 種別 | 内容 |', '|---|---|']
        lines += ['| `'+k+'` | '+p['record'][k]+' |' for k in p['required_evidence_kinds']]
        lines += ['', '受入値:', '', '| ID | 基準 | 値 | 単位 | 確度 | 出典 / 決める主体 |', '|---|---|---|---|---|---|']
        for a in p['acceptance']:
            where = a['decided_by'] if a['confidence'] == 'UNRESOLVED' else trace_text(a['source'])
            lines.append('| '+a['id']+' | '+a['criterion']+' | '+show(a['value']).replace('|', '\\|')+' | '+a['unit']+' | '+a['confidence']+' | '+where.replace('|', '\\|')+' |')
        lines.append('')
    lines += ['## ゲートの区分', '', '| 区分 | ゲート数 |', '|---|---:|']
    lines += ['| '+c+'（'+CLASS_JA[c]+'） | '+str(report['gate_counts'][c])+' |' for c in CLASSES]
    lines += ['', '## 現在のブロッカー', '']+['- '+r for r in report['blockers']]
    lines += ['', '## 別案', '', '- PET: '+plan['optional_variants']['pet'], '- 2HP: '+plan['optional_variants']['2hp'], '']
    return '\n'.join(lines)


def run_template(plan, report, procedure):
    template = json.loads((ROOT / QUAL / 'run-template.json').read_text())
    template.update(procedure=procedure['id'], identities={k: v['sha256'] for k, v in report['identities'].items()},
                    plan_sha256=report['plan_sha256'],
                    raw_evidence=[{'kind': k, 'path': None, 'sha256': None} for k in procedure['required_evidence_kinds']],
                    acceptance_checklist=[{'id': a['id'], 'criterion': a['criterion'], 'expected': a['value'], 'unit': a['unit'],
                                           'confidence': a['confidence'], 'observed': None, 'verdict': None} for a in procedure['acceptance']])
    return json.dumps(template, indent=2, ensure_ascii=False)+'\n'


def mdx(text):
    out, code = [], False
    for part in text.split('`'):
        out.append(part if code else part.replace('{', '&#123;').replace('}', '&#125;').replace('<', '&lt;').replace('>', '&gt;'))
        code = not code
    return '`'.join(out)


def checklist(plan, report):
    gates = {g['gate']: g for g in report['gates']}
    def covers(pattern):
        return [g for k, g in gates.items() if k == pattern or (pattern == 'run:*' and k.startswith('run:'))]
    lines = ['---', '# GENERATED by scripts/a7_readiness.py from engineering/a7/qualification/ — do not edit; run `python3 scripts/a7_readiness.py`',
             'title: "発注前にオーナーが行うこと"', 'description: "A7 (3HP / 1.6 mm / FR-4) の発注準備で、オーナーにしかできない作業と、それぞれが解除する readiness のゲート。"',
             'sidebar_position: 4.5', '---', '', ':::danger[発注・製造リリースではありません]',
             '発注ゲートは **'+report['order_eligibility']+'** です。このページは準備の一覧で、発注・供給元への連絡・製造承認・通電を許可するものではありません。',
             ':::', '',
             'readiness（`engineering/a7/qualification/readiness.json`）は不足を '+str(len(report['gates']))+' 個のゲートに分け、何で解除できるかで分類しています。',
             'ゲート名は readiness のものと同じです。', '', '| 区分 | ゲート数 |', '|---|---:|']
    lines += ['| '+CLASS_JA[c]+' | '+str(report['gate_counts'][c])+' |' for c in CLASSES]
    lines += ['', '## オーナーにしかできないこと', '', '| # | やること | 内容 | 解除するゲート（現在の状態） |', '|---|---|---|---|']
    for a in plan['owner_actions']:
        names = []
        for pattern in a['unblocks']:
            hit = covers(pattern)
            if pattern == 'run:*':
                names.append('`run:*`（'+str(len(hit))+' 手順が未実施）')
            else:
                names.append('`'+pattern+'`（'+('BLOCKED' if hit else '解除済み')+'）')
        lines.append('| '+a['id']+' | '+mdx(a['title'])+' | '+mdx(a['detail'])+' | '+'、'.join(names)+' |')
    owned = set()
    for a in plan['owner_actions']:
        for pattern in a['unblocks']:
            owned |= {g['gate'] for g in covers(pattern)}
    lines += ['', '## オーナーの作業を待たずに進められるもの', '', 'クラウドで進められるデジタル作業として分類したゲートです。', '']
    lines += ['- `'+g['gate']+'`: '+mdx(g['reasons'][0]) for g in report['gates'] if g['class'] == 'CLOUD_DIGITAL']
    lines += ['', '## 物理手順', '',
              '19 手順の準備物・計器・手順・記録項目・受入値は [procedures.md](https://github.com/Takazudo/zudo-led-block/blob/main/engineering/a7/qualification/procedures.md) にあります。'
              '受入値はすべて出典（部品資料の fact、設計記録、仮定の記録）と照合しています。仮定の値（例: 電源ケーブル公差 ±3 mm）と推定の値（例: ジャック軸高さ）は区別して表示します。'
              '実施後の記録は `run-templates/` の雛形を使います。すべて NOT_MEASURED のままです。', '']
    unowned = [g['gate'] for g in report['gates'] if g['class'] in ('OWNER_DECISION',) and g['gate'] not in owned]
    if unowned:
        raise ValueError('owner-decision gates without an owner action: ' + ', '.join(unowned))
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--gate', action='store_true', help='fail while order/release evidence is blocked')
    args = ap.parse_args()
    try:
        plan = json.loads((ROOT / QUAL / 'plan.json').read_text())
        records = json.loads((ROOT / QUAL / 'records.json').read_text())
        report = evaluate(ROOT, plan, records)
        outputs = {QUAL/'readiness.json': json.dumps(report, indent=2, ensure_ascii=False)+'\n',
                   QUAL/'procedures.md': markdown(plan, report), CHECKLIST: checklist(plan, report)}
        for procedure in plan['procedures']:
            outputs[RUN_TEMPLATES/(procedure['id']+'.json')] = run_template(plan, report, procedure)
        if args.gate:
            print(report['order_eligibility'])
            return 1 if report['blockers'] else 0
        expected = {ROOT / name for name in outputs}
        extra = sorted(str(f) for f in (ROOT / RUN_TEMPLATES).glob('*') if f not in expected) if (ROOT / RUN_TEMPLATES).is_dir() else []
        for name, content in outputs.items():
            path = ROOT / name
            if args.check:
                if not path.is_file() or path.read_text() != content:
                    raise ValueError('stale generated '+str(path))
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
        if args.check and extra:
            raise ValueError('unexpected run templates: '+', '.join(extra))
        print('VALID report; order eligibility: '+report['order_eligibility'])
        return 0
    except (ValueError, KeyError, TypeError, OSError) as e:
        print('INVALID readiness: '+str(e))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
