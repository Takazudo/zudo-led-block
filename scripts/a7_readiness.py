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
    reasons = ['missing artifact: '+k for k, v in ids.items() if v['sha256'] is None]
    binding = {k: v['sha256'] for k, v in ids.items()}
    for key in ['fixture', 'assembly_manifest']:
        path = root / IDENTITY_PATHS[key]
        if path.is_file():
            artifact = json.loads(path.read_text())
            if not isinstance(artifact, dict):
                raise ValueError(key+': artifact must be an object')
            reasons.extend(artifact_errors(key, artifact, root))
            if key == 'fixture' and (artifact.get('digital_fixture_complete') is not True or artifact.get('fresh_native_verified') is not True):
                reasons.append('fixture digital design incomplete or unverified')
            if artifact.get('blockers'):
                reasons.append(key+': unresolved preparation blockers')
            inputs = artifact.get('inputs_sha256')
            if not isinstance(inputs, dict) or not inputs:
                reasons.append(key+': input identity binding missing')
            elif not all(raw_ok({'path': p, 'sha256': h}, root) for p, h in inputs.items()):
                reasons.append(key+': stale input identity binding')
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
        reasons.extend(p['id']+': '+w for w in why)
    observations = records['material_observations']
    for key in sorted(MATERIALS):
        matches = [m for m in observations if m.get('material') == key]
        if len(matches) != 1:
            reasons.append('material '+key+': missing or ambiguous dated observation')
            continue
        m = matches[0]
        try:
            seen = dt.date.fromisoformat(m['observed_on'])
            expires = dt.date.fromisoformat(m['valid_until'])
            current = seen <= today <= expires
        except (KeyError, TypeError, ValueError):
            current = False
        if not current or m.get('identities') != binding or m.get('available_for_proposed_order') is not True or not raw_ok(m.get('source'), root):
            reasons.append('material '+key+': stale/unavailable/unbound source observation')
    route = records.get('owner_prototype_route')
    if not isinstance(route, dict) or route.get('identities') != binding or not text_fields(route, ['scope', 'quantity', 'constraints']) or not raw_ok(route.get('approval'), root):
        reasons.append('owner-approved sample/prototype route absent for this revision and quantity')
    release = records.get('manufacturing_release')
    if not isinstance(release, dict) or release.get('identities') != binding or not raw_ok(release.get('approval'), root) or not raw_ok(release.get('reviewed_order_files'), root):
        reasons.append('reviewed manufacturing files and explicit revision-bound owner release absent')
    # One retained file cannot stand in for several approval roles, nor raw evidence for two procedures.
    roles = {}
    def use(item, role):
        if isinstance(item, dict) and isinstance(item.get('path'), str):
            roles.setdefault(str(Path(item['path'])), set()).add(role)
    for p in plan['procedures']:
        use(p.get('criterion_review'), 'criterion_review')
    for run in records['runs']:
        if isinstance(run, dict):
            use(run.get('review'), 'execution_review')
            for x in run.get('raw_evidence') or []:
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
        reasons.append('receipt reused across roles: ' + path + ' (' + ', '.join(sorted(roles[path])) + ')')
    return {'schema': 1, 'variant': 'fr4-3hp', 'report_validation': 'VALID',
            'order_eligibility': 'BLOCKED' if reasons else 'ELIGIBLE_FOR_RECORDED_SCOPE',
            'manufacturing_release': 'NOT_ESTABLISHED' if reasons else 'RECORDED_APPROVAL_REQUIRES_HUMAN_VERIFICATION',
            'order_submitted': 'NOT_ESTABLISHED', 'identities': ids, 'plan_sha256': plan_hash,
            'procedures': outcomes, 'blockers': reasons, 'optional_variants': plan['optional_variants'],
            'limit': 'Schema validation is not measurement authenticity, hardware approval, a release authorization or an order. No order is submitted by this command.'}


def markdown(plan, report):
    lines = ['# A7 物理評価の準備と readiness', '', '**未実施・製造リリースなし。** この文書は `scripts/a7_readiness.py` の生成物です。', '',
             'レポート検証: '+report['report_validation']+'。発注適格性: **'+report['order_eligibility']+'**。', '',
             '## 共通記録 (Workflow F)', '',
             '各実施は `run-template.json` のコピーを使い、unit、基板/実装/FW/設定ハッシュ、計器、条件、期待基準、raw証跡、結果、次の行動を記録します。失敗や再加工を上書きせず別 run として追加します。', '',
             '## 未実施の手順', '']
    for p in plan['procedures']:
        lines += ['### '+p['id']+' — '+p['title'], '', '- 関連: '+p['issues'], '- セットアップ/操作: '+p['setup'],
                  '- 期待基準: '+p['expected'], '- 根拠: `'+p['basis']+'`', '- 未決: '+p['missing_criterion'],
                  '- 必須raw証跡: '+p['raw_evidence_required'], '- 機械検証する証跡種別: '+', '.join(p['required_evidence_kinds']), '- 観測: NOT_MEASURED。結果: NOT_RUN。', '- 次: '+p['next_action'], '']
    lines += ['## 現在のブロッカー', '']+['- '+r for r in report['blockers']]
    lines += ['', '## 別案', '', '- PET: '+plan['optional_variants']['pet'], '- 2HP: '+plan['optional_variants']['2hp'], '']
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
        outputs = {'readiness.json': json.dumps(report, indent=2, ensure_ascii=False)+'\n',
                   'procedures.md': markdown(plan, report)}
        if args.gate:
            print(report['order_eligibility'])
            return 1 if report['blockers'] else 0
        for name, content in outputs.items():
            path = ROOT / QUAL / name
            if args.check:
                if not path.is_file() or path.read_text() != content:
                    raise ValueError('stale generated '+str(path))
            else:
                path.write_text(content)
        print('VALID report; order eligibility: '+report['order_eligibility'])
        return 0
    except (ValueError, KeyError, TypeError, OSError) as e:
        print('INVALID readiness: '+str(e))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
