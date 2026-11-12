#!/usr/bin/env python3
"""A7 Workflow F preparation: valid BLOCKED reports are not release eligibility."""
import argparse
import ast
import re
import xml.etree.ElementTree as ET
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
# CALCULATED: recomputed here from traced inputs that are all SOURCED or DESIGN.
# PROPOSED: a traced value offered for review; it never satisfies a criterion gate.
CONFIDENCES = ('SOURCED', 'MIRROR', 'UNVERIFIED', 'INFERRED', 'DESIGN', 'ASSUMED', 'CALCULATED', 'PROPOSED', 'UNRESOLVED')
BASIS = ('SOURCED', 'MIRROR', 'UNVERIFIED', 'INFERRED', 'DESIGN', 'ASSUMED', 'CALCULATED')
# A derived value is only as strong as its weakest input; earlier entries are weaker.
WEAKEST = ('UNVERIFIED', 'ASSUMED', 'INFERRED', 'MIRROR')
NETLIST = 'engineering/a7/verification/schematic/netlist.xml'
SI = {'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'µ': 1e-6, 'm': 1e-3, 'k': 1e3, 'M': 1e6, '': 1}
# Plain numbers a derivation may write itself: unit and percent conversions and the safety factor 10.
LITERALS = {1, 2, 10, 100, 1000}
SUPPLIED_BY = ('DOCUMENT', 'MEASUREMENT', 'DOCUMENT_AND_MEASUREMENT')
# Who accepted a reviewed criterion: the owner personally, or the project coordinator acting under
# the owner's delegated working style. The two stay distinguishable in every output.
ACCEPTED_BY = ('OWNER', 'PROJECT_COORDINATOR_DELEGATED')
ACCEPTED_JA = {'OWNER': 'オーナー本人', 'PROJECT_COORDINATOR_DELEGATED': 'プロジェクトのコーディネーター（オーナーが委ねた作業方針による）'}
BOUNDS = ('exact', 'min', 'min_exclusive', 'max', 'range', 'reference')
# Acceptance values may cite only design records and component facts, never this plan or generated outputs.
SOURCE_ROOTS = ('engineering/a7/mechanical/', 'engineering/a7/study/', 'engineering/a7/electronics/',
                'engineering/a7/verification/', 'engineering/a7/README.md', 'engineering/a5/')
# Confidence words that JSON design records write beside a value, mapped to the label an acceptance item must use.
STATED = {'ASSUMED': {'ASSUMED'}, 'INFERRED': {'INFERRED'}, 'MIRROR': {'MIRROR'}, 'DERIVED-MIRROR': {'MIRROR'},
          'UNSOURCED': {'UNVERIFIED'}, 'UNVERIFIED': {'UNVERIFIED'}, 'SOURCED': {'DESIGN'}, 'PROJECT-CHOICE': {'DESIGN'},
          'A5-GEOMETRY': {'DESIGN'}, 'MANUFACTURER_PRIMARY': {'DESIGN'}}
FACTS = re.compile(r'^\.claude/skills/component-[a-z0-9-]+/facts\.json$')
# A manufacturer-primary source extract that has not been audited into a fact: quotable, but only as UNVERIFIED.
SOURCES = re.compile(r'^\.claude/skills/component-[a-z0-9-]+/sources\.json$')
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
    conditions = fact.get('conditions', '')
    if re.search(r'\binferred\b', conditions, re.I):
        return 'INFERRED'
    provenance = fact.get('provenance')
    if provenance == 'PRIMARY-SPEC' and str(fact.get('verdict', '')).startswith('PASS'):
        return 'SOURCED'
    if provenance == 'PROJECT-CHOICE':
        return 'DESIGN'
    if provenance == 'UNVERIFIED' and re.search(r'MANUFACTURER_MIRROR|hosted mirror', conditions):
        return 'MIRROR'
    return 'UNVERIFIED'


def resolve(trace, root, roots=None):
    """Return (value, quote, stated confidence) a trace points at; raise ValueError when it does not resolve."""
    if not isinstance(trace, dict) or not isinstance(trace.get('path'), str):
        raise ValueError('trace needs a repository path')
    full = (root / trace['path']).resolve()
    if not full.is_relative_to(root.resolve()) or not full.is_file():
        raise ValueError('trace path missing: ' + trace['path'])
    rel = full.relative_to(root.resolve()).as_posix()
    if SOURCES.match(rel):
        if set(trace) != {'path', 'source_id', 'quote'} or not isinstance(trace['quote'], str) or not trace['quote']:
            raise ValueError('component sources are cited by source_id and a quote of its evidence_extract: ' + rel)
        entries = [x for x in json.loads(full.read_text()).get('sources', []) if x.get('source_id') == trace['source_id']]
        if len(entries) != 1 or entries[0].get('authority_class') != 'MANUFACTURER_PRIMARY':
            raise ValueError('source missing, duplicate or not manufacturer-primary: ' + str(trace['source_id']))
        extract = entries[0].get('evidence_extract')
        if not isinstance(extract, str) or not re.search(r'(?<![\w.])' + re.escape(trace['quote']) + r'(?![\w])', extract):
            raise ValueError('quote not found as whole words in the evidence_extract of ' + trace['source_id'])
        return trace['quote'], trace['quote'], ['UNVERIFIED']
    forms = [k for k in ('fact_id', 'pointer', 'quote', 'netlist_value') if k in trace]
    if len(forms) != 1 or set(trace) != {'path', forms[0]}:
        raise ValueError('trace needs exactly one of fact_id, pointer or quote: ' + trace['path'])
    if bool(FACTS.match(rel)) != ('fact_id' in trace):
        raise ValueError('component facts are cited only by fact_id, and fact_id only cites component facts: ' + rel)
    if not FACTS.match(rel) and not rel.startswith(roots or SOURCE_ROOTS):
        raise ValueError('not an allowed design source: ' + rel)
    if 'netlist_value' in trace:
        if rel != NETLIST:
            raise ValueError('netlist_value cites only ' + NETLIST)
        values = [c.findtext('value') for c in ET.parse(full).getroot().iter('comp') if c.get('ref') == trace['netlist_value']]
        if len(values) != 1 or not values[0]:
            raise ValueError('netlist component missing or duplicate: ' + str(trace['netlist_value']))
        return values[0], values[0], []
    if 'quote' in trace:
        text = full.read_text()
        quote = trace['quote']
        if not isinstance(quote, str) or not quote or quote not in text:
            raise ValueError('quote not found in ' + trace['path'])
        # A quote may not cut a word or number short ('...MS    25' out of '...MS    250u').
        edges = (r'(?<!\w)' if quote[0].isalnum() or quote[0] == '_' else '') + re.escape(quote) + (r'(?!\w)' if quote[-1].isalnum() or quote[-1] == '_' else '')
        if not re.search(edges, text):
            raise ValueError('quote cuts a word or number short in ' + trace['path'])
        line = next(l for l in text.splitlines() if trace['quote'] in l) if '\n' not in trace['quote'] else trace['quote']
        stated = [w for w in ('ASSUMED', 'INFERRED') if w in line]
        return trace['quote'], trace['quote'], stated
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


def token_number(token, c_literal=False):
    """'68k' -> 68000.0, '100n' -> 1e-07, '1%' -> 1.0; with c_literal an integer C literal whose 'u' means unsigned."""
    m = re.fullmatch(r'(\d+)(u|U)?' if c_literal else r'([+-]?\d+(?:\.\d+)?)([pnuµmkM]?)%?', token)
    if not m:
        raise ValueError('not a number token: ' + token)
    return float(m.group(1)) * (1 if c_literal else SI[m.group(2) or ''])


def whole_token(token, text):
    return re.findall(r'(?<![\w.])' + re.escape(token) + r'(?![\w.])', text)


def input_value(inp, root):
    """Return (number, confidence) for one derivation input, after binding its token to a labelled place in the source."""
    allowed = {'name', 'token', 'number', 'source', 'field', 'c_literal', 'context', 'part'}
    if not isinstance(inp, dict) or set(inp) - allowed:
        raise ValueError('derivation input keys: ' + ', '.join(sorted(allowed)))
    if not isinstance(inp.get('name'), str) or not inp['name'].isidentifier() or not isinstance(inp.get('token'), str):
        raise ValueError('derivation input needs an identifier name and a token string')
    trace = inp.get('source')
    got, quote, stated = resolve(trace, root)
    field = inp.get('field', 'value')
    c_literal = inp.get('c_literal', False)
    if c_literal is not False and (c_literal is not True or 'quote' not in trace or not trace['path'].endswith(('.h', '.c'))):
        raise ValueError(inp['name'] + ': c_literal applies only to quotes from C sources')
    if isinstance(got, dict) and 'fact_id' in trace:
        if field not in ('value', 'conditions'):
            raise ValueError('fact inputs read value or conditions')
        text, confidence = got.get(field), fact_confidence(got)
    else:
        if field != 'value':
            raise ValueError('field applies only to component facts')
        text = quote if quote is not None else got
        if isinstance(stated, list):
            confidence = stated[0] if len(stated) == 1 else ('DESIGN' if not stated else 'INFERRED')
        elif stated is not None:
            if stated not in STATED or len(STATED[stated]) != 1:
                raise ValueError('unknown stated confidence ' + str(stated))
            confidence = next(iter(STATED[stated]))
        else:
            confidence = 'DESIGN'
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        if {'context', 'part'} & set(inp) or float(text) != float(inp['token']):
            raise ValueError(inp['name'] + ': token differs from the cited number')
    elif not isinstance(text, str):
        raise ValueError(inp['name'] + ': the cited ' + field + ' is not text or a number')
    elif 'netlist_value' in trace:
        # A netlist value reads '<value> <tolerance>%': the part names which word is meant.
        words = text.split()
        part = inp.get('part')
        if 'context' in inp or part not in ('value', 'tolerance'):
            raise ValueError(inp['name'] + ': netlist inputs name part value or tolerance')
        if (part == 'value' and inp['token'] != words[0]) or (part == 'tolerance' and (inp['token'] not in words[1:] or not inp['token'].endswith('%'))):
            raise ValueError(inp['name'] + ': token is not the netlist ' + part)
    else:
        # The context is the labelled phrase the token comes from, e.g. 'VIL max 0.66 V'.
        context = inp.get('context')
        if 'part' in inp or not isinstance(context, str) or context not in text:
            raise ValueError(inp['name'] + ': context must be a phrase of the cited ' + field)
        if len(whole_token(inp['token'], context)) != 1 or not re.search(r'[A-Za-z]', context.replace(inp['token'], '')):
            raise ValueError(inp['name'] + ': context must hold the token once beside a label')
    number = token_number(inp['token'], c_literal)
    if type(inp.get('number')) not in (int, float) or abs(inp['number'] - number) > 1e-12 * max(1, abs(number)):
        raise ValueError(inp['name'] + ': number differs from the token')
    return number, confidence


def evaluate_expression(expression, names):
    """Arithmetic only: + - * / **, unary minus, min/max, input names and a few unit literals.

    Every input must be used and no operation may act on literals alone, so a value cannot be built from constants."""
    used = set()

    def has_name(node):
        return any(isinstance(n, ast.Name) for n in ast.walk(node))

    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
            if not has_name(node.left) and not has_name(node.right):
                raise ValueError('expression may not combine literals alone')
            a, b = walk(node.left), walk(node.right)
            if isinstance(node.op, ast.Div) and b == 0:
                raise ValueError('division by zero')
            if isinstance(node.op, ast.Pow) and (abs(b) > 4 or a < 0):
                raise ValueError('powers need a non-negative base and an exponent within 4')
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
            if isinstance(node.op, ast.Mult):
                return a * b
            return a / b if isinstance(node.op, ast.Div) else a ** b
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and has_name(node.operand):
            return -walk(node.operand)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('min', 'max') and node.args and not node.keywords:
            return (min if node.func.id == 'min' else max)(walk(x) for x in node.args)
        if isinstance(node, ast.Name) and node.id in names:
            used.add(node.id)
            return names[node.id]
        if isinstance(node, ast.Constant) and type(node.value) is int and node.value in LITERALS:
            return float(node.value)
        raise ValueError('expression may use only inputs, + - * / **, min/max and the literals ' + str(sorted(LITERALS)))
    if not isinstance(expression, str) or len(expression) > 600:
        raise ValueError('expression must be a string of at most 600 characters')
    try:
        result = walk(ast.parse(expression, mode='eval'))
    except (ArithmeticError, TypeError, SyntaxError, RecursionError) as e:
        raise ValueError('expression does not evaluate: ' + str(e))
    if set(names) - used:
        raise ValueError('unused derivation inputs: ' + ', '.join(sorted(set(names) - used)))
    if not isinstance(result, float) or result != result or result in (float('inf'), float('-inf')):
        raise ValueError('expression must give a finite real number')
    return result


def derive(derivation, root):
    """Recompute a derivation; return (rounded value, the confidence its inputs allow)."""
    if not isinstance(derivation, dict) or set(derivation) - {'expression', 'inputs', 'round', 'assumption'}:
        raise ValueError('derivation needs expression, inputs, round and optional assumption')
    inputs = derivation.get('inputs')
    if not isinstance(inputs, list) or not inputs:
        raise ValueError('derivation needs inputs')
    names, confidences = {}, set()
    for inp in inputs:
        number, confidence = input_value(inp, root)
        if inp['name'] in names:
            raise ValueError('duplicate derivation input ' + inp['name'])
        names[inp['name']] = number
        confidences.add(confidence)
    digits = derivation.get('round')
    if type(digits) is not int or not 0 <= digits <= 6:
        raise ValueError('derivation round must be 0..6 digits')
    exact = evaluate_expression(derivation['expression'], names)
    for name in names:
        # A value that does not move when an input moves was not derived from that input.
        nudged = evaluate_expression(derivation['expression'], dict(names, **{name: names[name] * 1.001 + 1e-9}))
        if abs(nudged - exact) <= 1e-12 * max(1.0, abs(exact)):
            raise ValueError('result does not depend on input ' + name)
    value = round(exact, digits)
    weak = [c for c in WEAKEST if c in confidences]
    if weak:
        confidence = weak[0]
    elif derivation.get('assumption') is not None:
        if not text_fields(derivation, ['assumption']):
            raise ValueError('assumption must be text')
        confidence = 'INFERRED'
    elif confidences <= {'SOURCED', 'DESIGN'}:
        confidence = 'CALCULATED'
    else:
        raise ValueError('unexpected input confidence ' + str(sorted(confidences)))
    return (int(value) if digits == 0 else value), confidence


def traced_errors(a, where, root):
    """Value and confidence checks for an item traced by source or derivation."""
    errors = []
    if a.get('bound') not in BOUNDS:
        errors.append(where + 'bound must be one of ' + ', '.join(BOUNDS))
    if ('source' in a) == ('derivation' in a):
        return errors + [where + 'needs exactly one of source or derivation']
    if 'derivation' in a:
        value, confidence = derive(a['derivation'], root)
        if type(a.get('value')) not in (int, float) or a.get('value') != value:
            errors.append(where + 'value differs from the recomputed derivation (' + str(value) + ')')
        if a['confidence'] != confidence:
            errors.append(where + 'derivation inputs allow only ' + confidence)
        return errors
    if a['confidence'] == 'CALCULATED':
        return errors + [where + 'CALCULATED needs a derivation']
    got, quote, stated = resolve(a.get('source'), root)
    if isinstance(stated, list):
        if stated and a['confidence'] not in stated:
            errors.append(where + 'the quoted line marks this value ' + '/'.join(stated))
    elif stated is not None:
        if stated not in STATED:
            errors.append(where + 'unknown stated confidence ' + stated)
        elif a['confidence'] not in STATED[stated]:
            errors.append(where + 'the cited record marks this value ' + stated)
    if isinstance(got, dict) and 'fact_id' in a['source']:
        if (got.get('value'), got.get('unit')) != (a.get('value'), a['unit']):
            errors.append(where + 'value/unit differs from the cited fact')
        if fact_confidence(got) != a['confidence']:
            errors.append(where + 'confidence differs from the cited fact (' + fact_confidence(got) + ')')
    else:
        if quote is not None:
            if not isinstance(a.get('value'), str) or not re.search(r'(?<![\w.])' + re.escape(a['value']) + r'(?![\w.])', quote):
                errors.append(where + 'value is not a whole token of the cited quote')
        elif got != a.get('value'):
            errors.append(where + 'value differs from the cited record')
        if a['confidence'] not in ('DESIGN', 'ASSUMED', 'INFERRED', 'MIRROR', 'UNVERIFIED'):
            errors.append(where + 'a design record cannot make a value SOURCED')
    if a['confidence'] in ('ASSUMED', 'INFERRED') and 'fact_id' not in a['source']:
        marker = resolve(a.get('confidence_trace'), root)[0]
        if a['confidence'] not in json.dumps(marker, ensure_ascii=False):
            errors.append(where + 'confidence_trace does not say ' + a['confidence'])
    return errors


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
        keys = {'id', 'criterion', 'value', 'unit', 'confidence'}
        if a['confidence'] == 'UNRESOLVED':
            keys |= {'decided_by', 'supplied_by'}
        else:
            keys |= {'bound', 'source', 'derivation', 'confidence_trace'}
            if a['confidence'] == 'PROPOSED':
                keys |= {'basis_confidence', 'rationale'}
        if set(a) - keys:
            errors.append(where + 'keys not valid for ' + a['confidence'] + ': ' + ', '.join(sorted(set(a) - keys)))
            continue
        if a['confidence'] == 'UNRESOLVED':
            if (a.get('value') is not None or not text_fields(a, ['decided_by'])
                    or {'source', 'derivation', 'bound'} & set(a)):
                errors.append(where + 'UNRESOLVED needs value null, decided_by and no source')
            supplied = a.get('supplied_by')
            if procedure.get('criterion_class') == 'ACCESS_EVIDENCE_HOLD' and supplied is None:
                errors.append(where + 'an evidence-hold criterion must say which document or measurement supplies it')
            if supplied is not None and (not isinstance(supplied, dict) or set(supplied) != {'kind', 'what'}
                                         or supplied.get('kind') not in SUPPLIED_BY or not text_fields(supplied, ['what'])):
                errors.append(where + 'supplied_by needs kind (' + '/'.join(SUPPLIED_BY) + ') and what')
            continue
        try:
            if a['confidence'] == 'PROPOSED':
                if not text_fields(a, ['rationale']) or a.get('basis_confidence') not in BASIS:
                    errors.append(where + 'PROPOSED needs a rationale and basis_confidence')
                    continue
                errors += traced_errors(dict(a, confidence=a['basis_confidence']), where, root)
            else:
                errors += traced_errors(a, where, root)
        except (ValueError, OSError, json.JSONDecodeError, ET.ParseError) as e:
            errors.append(where + str(e))
    return errors


def acceptance_digest(procedure):
    """The accepted values, units, bounds and traces; a review record binds to this, so a later edit re-blocks the gate."""
    return hashlib.sha256(json.dumps(procedure.get('acceptance'), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


STATE_ARTIFACTS = ('fixture',)
# Flags the order gate reads; any other registered flag is shown for progress only.
GATING_STATE_FLAGS = frozenset(['digital_fixture_complete', 'fresh_native_verified'])
STATE_TEXT = re.compile(r'\b([a-z][a-z0-9_]*)=(true|false)\b')


def state_flag_errors(plan):
    """A procedure may not wait on a state that only it, or a procedure waiting on it, can produce."""
    procedures = plan['procedures']
    ids = {p['id'] for p in procedures}
    flags = plan.get('state_flags')
    if not isinstance(flags, list) or not flags or any(not isinstance(x, dict) for x in flags):
        return ['state_flags must be a non-empty object list']
    errors = []
    closers = {}
    for x in flags:
        if set(x) != {'artifact', 'flag', 'closed_by', 'note'} or x['artifact'] not in STATE_ARTIFACTS or not text_fields(x, ['flag', 'note']):
            errors.append('state flag needs exactly artifact, flag, closed_by and note: ' + str(x.get('flag')))
            continue
        if not isinstance(x['closed_by'], list) or any(c not in ids for c in x['closed_by']):
            errors.append('state flag ' + x['flag'] + ' names an unknown closing procedure')
            continue
        key = (x['artifact'], x['flag'])
        if key in closers:
            errors.append('duplicate state flag ' + x['flag'])
        closers[key] = set(x['closed_by'])
    if ('fixture', 'digital_fixture_complete') not in closers:
        errors.append('state_flags must register the fixture completion flag digital_fixture_complete')
    names = {f for _, f in closers}
    edges = {p['id']: set() for p in procedures}
    for p in procedures:
        wanted = p.get('precondition_states')
        if not isinstance(wanted, list) or any(not isinstance(w, dict) or set(w) != {'artifact', 'flag', 'equals'} for w in wanted):
            errors.append(p['id'] + ': precondition_states must list {artifact, flag, equals}')
            continue
        declared = set()
        for w in wanted:
            key = (w['artifact'], w['flag'])
            if key not in closers or not isinstance(w['equals'], bool):
                errors.append(p['id'] + ': precondition on unregistered state ' + str(w['flag']))
                continue
            declared.add((w['flag'], 'true' if w['equals'] else 'false'))
            if p['id'] in closers[key]:
                errors.append(p['id'] + ': precondition ' + w['flag'] + ' can only be produced by this procedure')
            edges[p['id']] |= closers[key]
        written = {(f, v) for text in p['preconditions'] for f, v in STATE_TEXT.findall(text) if f in names}
        if written != declared:
            errors.append(p['id'] + ': precondition text and precondition_states disagree')
    # A wait cycle through several procedures is the same deadlock as a self-wait.
    state = {}
    def visit(node, path):
        state[node] = 'open'
        for nxt in sorted(edges[node]):
            if state.get(nxt) == 'open':
                errors.append('precondition cycle: ' + ' -> '.join(path[path.index(nxt):] + [nxt]))
            elif nxt not in state:
                visit(nxt, path + [nxt])
        state[node] = 'done'
    for node in sorted(edges):
        if node not in state:
            visit(node, [node])
    return errors


def state_closers_from_artifact(plan, artifact):
    """Procedures that the fixture manifest itself says close an unmet completion criterion."""
    criteria = artifact.get('completion_criteria')
    found = set()
    if isinstance(criteria, dict):
        for c in criteria.values():
            basis = c.get('basis') if isinstance(c, dict) else None
            if isinstance(basis, str):
                found |= {p['id'] for p in plan['procedures'] if re.search(r'(?<![\w-])' + re.escape(p['id']) + r'(?![\w-])', basis)}
    return found


# Owner-decision recommendations may also cite the procurement, fixture and continuation records they summarize.
DECISION_ROOTS = SOURCE_ROOTS + ('engineering/a7/procurement/', 'engineering/a7/fixture/', 'engineering/a7/docs/continuation/',
                                 'engineering/a7/qualification/supplier-questions.md')
# Owner answers are recorded here, in the owner's own words; a decision marked answered must match its record.
OWNER_ANSWERS = 'engineering/a7/procurement/owner-decisions.json'
STAGES = {'PCB_ORDER': 'PCB 発注の前', 'BENCH': '実機試験の前', 'RELEASE': '製造リリースのとき'}
ROUTES = {'OWNER_DOWNLOAD': 'オーナーがブラウザで保存', 'CLOUD_FETCH': 'クラウドで取得（オーナー作業なし）',
          'SUPPLIER_ANSWER': '供給元・加工先の回答', 'DATED_OBSERVATION': '日付付きの供給観測', 'MEASUREMENT': '実物の測定'}


def owner_page_errors(plan, root=ROOT):
    """Prepared owner decisions and evidence requests: well formed, traced, and never an acceptance."""
    errors = []
    decisions, requests = plan.get('owner_decisions'), plan.get('evidence_requests')
    if not isinstance(decisions, list) or not isinstance(requests, list):
        return ['owner_decisions and evidence_requests must be lists']
    keys = gate_keys(plan, root)
    for name, items in (('owner decision', decisions), ('evidence request', requests)):
        gates = [x.get('gate') if isinstance(x, dict) and isinstance(x.get('gate'), str) else None for x in items]
        answered = [isinstance(x, dict) and 'answer' in x for x in items]
        if len(gates) != len(set(gates)) or any(g not in keys and not a for g, a in zip(gates, answered)):
            errors.append(name + 's need unique, known gates')
    if [d.get('rank') for d in decisions if isinstance(d, dict)] != list(range(1, len(decisions) + 1)):
        errors.append('owner decisions must be ranked 1..n in list order')
    fields = {'gate', 'rank', 'stage', 'question', 'options', 'recommended', 'reason', 'sources'}
    for d in decisions:
        if (not isinstance(d, dict) or set(d) - {'answer'} != fields
                or not isinstance(d['gate'], str) or not isinstance(d['recommended'], str)):
            errors.append('owner decision needs exactly gate, rank, stage, question, options, recommended, reason, sources (and an optional answer)')
            continue
        where = d['gate'] + ': '
        if 'answer' in d:
            errors += [where + e for e in answer_errors(d, keys, root)]
        if d['stage'] not in STAGES or not text_fields(d, ['question', 'reason']):
            errors.append(where + 'stage, question and reason are required')
        options = d['options']
        if (not isinstance(options, list) or not 2 <= len(options) <= 4
                or any(not isinstance(o, dict) or set(o) != {'id', 'label', 'consequence'} or not text_fields(o, ['id', 'label', 'consequence']) for o in options)
                or len({o['id'] for o in options}) != len(options)):
            errors.append(where + '2-4 options, each with a unique id, a label and a consequence')
        elif d['recommended'] not in {o['id'] for o in options}:
            errors.append(where + 'the recommendation must be one of the options')
        if not isinstance(d['sources'], list) or not d['sources']:
            errors.append(where + 'a recommendation needs at least one source')
        else:
            for t in d['sources']:
                try:
                    resolve(t, root, DECISION_ROOTS)
                except (ValueError, OSError) as e:
                    errors.append(where + str(e))
    for r in requests:
        if not isinstance(r, dict) or set(r) != {'gate', 'routes', 'items'} or not isinstance(r['gate'], str):
            errors.append('evidence request needs exactly gate, routes, items')
            continue
        where = r['gate'] + ': '
        if not isinstance(r['routes'], list) or not r['routes'] or any(x not in ROUTES for x in r['routes']):
            errors.append(where + 'routes must name ' + ', '.join(ROUTES))
        items = r['items']
        if not isinstance(items, list) or not items or any(
                not isinstance(i, dict) or set(i) != {'what', 'value_needed', 'url', 'fallback_url', 'access'}
                or not text_fields(i, ['what', 'value_needed', 'access'])
                or any(i[k] is not None and not (isinstance(i[k], str) and re.fullmatch(r'https://[^\s()<>{}|`\[\]]+', i[k])) for k in ('url', 'fallback_url')) for i in items):
            errors.append(where + 'each item needs what, value_needed, access and https url / fallback_url (or null)')
        elif 'OWNER_DOWNLOAD' in r['routes'] and not all(i['url'] for i in items):
            errors.append(where + 'an owner download names its URL')
    return errors


def answer_errors(d, keys, root):
    """An answered decision names the owner's option, cites the owner's own recorded words, and its gate is closed."""
    a = d['answer']
    if not isinstance(a, dict) or set(a) != {'option', 'by', 'record'} or a['by'] != 'OWNER' or not isinstance(a['option'], str):
        return ['an answer needs exactly option, by (OWNER) and record']
    errors = []
    if not isinstance(d['options'], list) or a['option'] not in {o.get('id') for o in d['options'] if isinstance(o, dict)}:
        errors.append('the answer must be one of the options')
    record = a['record']
    if not isinstance(record, dict) or record.get('path') != OWNER_ANSWERS:
        return errors + ['an answer is recorded in ' + OWNER_ANSWERS]
    try:
        resolve(record, root, DECISION_ROOTS)
    except (ValueError, OSError) as e:
        return errors + [str(e)]
    entries = [x for x in json.loads((root / OWNER_ANSWERS).read_text()).get('decisions', [])
               if isinstance(x, dict) and 'assembly:' + str(x.get('id')) == d['gate']]
    if len(entries) != 1 or entries[0].get('decided_by') != 'OWNER' or entries[0].get('answer') != a['option'] or not entries[0].get('owner_words'):
        errors.append('the answer must match one owner-decided entry with the owner\'s words in ' + OWNER_ANSWERS)
    if d['gate'] in keys:
        errors.append('an answered decision\'s gate is still open')
    return errors


def gate_keys(plan, root=ROOT):
    manifest = root / IDENTITY_PATHS['assembly_manifest']
    pending = json.loads(manifest.read_text()).get('blockers', []) if manifest.is_file() else []
    keys = {'assembly:' + b['id'] for b in pending if isinstance(b, dict) and isinstance(b.get('id'), str)}
    keys |= {'artifact:fixture', 'artifact:assembly_manifest', 'owner_prototype_route', 'manufacturing_release',
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
        if (p['criterion_status'] == 'REVIEWED') != ('criterion_accepted_by' in p):
            raise ValueError('a REVIEWED criterion, and only one, names who accepted it: '+p['id'])
        if 'criterion_accepted_by' in p and p['criterion_accepted_by'] not in ACCEPTED_BY:
            raise ValueError('criterion_accepted_by must be one of '+', '.join(ACCEPTED_BY))
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
    errors = state_flag_errors(plan)
    if errors:
        raise ValueError('precondition states: ' + '; '.join(errors))
    errors = owner_page_errors(plan)
    if errors:
        raise ValueError('owner page: ' + '; '.join(errors))
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
            if not isinstance(g, str) or g not in keys:
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
    artifacts = {}
    for key in ['fixture', 'assembly_manifest']:
        path = root / IDENTITY_PATHS[key]
        if path.is_file():
            artifact = json.loads(path.read_text())
            if not isinstance(artifact, dict):
                raise ValueError(key+': artifact must be an object')
            gate = 'artifact:' + key
            for e in artifact_errors(key, artifact, root):
                block(gate, 'CLOUD_DIGITAL', e)
            if key == 'fixture':
                artifacts['fixture'] = artifact
                waited_on = {w['flag'] for q in plan['procedures'] for w in q['precondition_states'] if w['artifact'] == key}
                for x in plan['state_flags']:
                    # A progress-only flag that nothing waits on may be absent; it then shows as unknown.
                    if x['flag'] not in GATING_STATE_FLAGS | waited_on:
                        continue
                    if x['artifact'] == key and not isinstance(artifact.get(x['flag']), bool):
                        block(gate, 'CLOUD_DIGITAL', 'fixture: state flag '+x['flag']+' missing from the manifest')
                complete_closers = next(set(x['closed_by']) for x in plan['state_flags'] if x['flag'] == 'digital_fixture_complete')
                unlisted = state_closers_from_artifact(plan, artifact) - complete_closers
                if unlisted:
                    raise ValueError('fixture manifest names procedures that close digital_fixture_complete but state_flags does not: '+', '.join(sorted(unlisted)))
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
            if key == 'fixture' and (artifact.get('digital_fixture_complete') is not True or artifact.get('fresh_native_verified') is not True):
                # Still gated on completion; once only the physical criterion 5 is left, no cloud work can close it.
                physical_only = (gate not in gates and artifact.get('fresh_native_verified') is True
                                 and artifact.get('digital_criteria_1_to_4_met') is True)
                block(gate, 'PHYSICAL_ONLY' if physical_only else 'CLOUD_DIGITAL',
                      'fixture completion awaits the physical criterion 5 (fixture-contact)' if physical_only
                      else 'fixture digital design incomplete or unverified')
    # A file name or asserted digest is not evidence: retained bytes must match.
    plan_hash = hashlib.sha256(json.dumps(plan, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    outcomes = []
    for p in plan['procedures']:
        why = []
        if p['criterion_status'] != 'REVIEWED' or p.get('missing_criterion') != '' or not raw_ok(p.get('criterion_review'), root):
            why.append('criterion unresolved or review receipt missing')
        if p['criterion_status'] == 'REVIEWED':
            digest_now = acceptance_digest(p)
            receipt = p.get('criterion_review')
            receipt_path = (root / receipt['path']) if isinstance(receipt, dict) and isinstance(receipt.get('path'), str) else None
            # The retained review record itself must name this procedure's current acceptance digest.
            named = receipt_path is not None and receipt_path.is_file() and (p['id'] + ' ' + digest_now) in receipt_path.read_text(errors='replace')
            if p.get('criterion_acceptance_sha256') != digest_now or not named:
                why.append('criterion acceptance record does not match the current acceptance values')
        open_items = [a['id'] for a in p['acceptance'] if a.get('confidence') in ('PROPOSED', 'UNRESOLVED')]
        if open_items:
            # A proposal is offered for review; it never stands in for an accepted value.
            why.append('criterion has PROPOSED or UNRESOLVED acceptance values: ' + ', '.join(open_items))
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
            # The run binds the current artifact bytes, so the current flags are the flags it ran under.
            unmet = [w['flag'] for w in p['precondition_states'] if artifacts.get(w['artifact'], {}).get(w['flag']) is not w['equals']]
            if unmet:
                why.append('run precondition state not met: ' + ', '.join(unmet))
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
            'state_flags': [{'artifact': x['artifact'], 'flag': x['flag'], 'value': artifacts.get(x['artifact'], {}).get(x['flag']),
                             'role': 'GATE' if x['flag'] in GATING_STATE_FLAGS else 'INFORMATIONAL', 'note': x['note']} for x in plan['state_flags']],
            'optional_variants': plan['optional_variants'],
            'limit': 'Schema validation is not measurement authenticity, hardware approval, a release authorization or an order. No order is submitted by this command.'}


def show(value):
    return '—' if value is None else '`' + json.dumps(value, ensure_ascii=False).replace('`', "'") + '`'


def trace_text(trace):
    if not trace:
        return '—'
    if 'source_id' in trace:
        return '`' + trace['path'] + '` `' + trace['source_id'] + '` の抜粋（未監査）'
    form = next(k for k in ('fact_id', 'pointer', 'quote', 'netlist_value') if k in trace)
    detail = {'quote': '引用', 'netlist_value': trace.get('netlist_value', '') + ' の値'}.get(form, trace[form])
    return '`' + trace['path'] + '` ' + ('`' + detail + '`' if form in ('fact_id', 'pointer') else detail)


SUPPLIED_JA = {'DOCUMENT': '資料', 'MEASUREMENT': '測定', 'DOCUMENT_AND_MEASUREMENT': '資料と測定'}


def where_text(a):
    if a['confidence'] == 'UNRESOLVED':
        supplied = a.get('supplied_by')
        return a['decided_by'] + ('。入手先（' + SUPPLIED_JA[supplied['kind']] + '）: ' + supplied['what'] if supplied else '')
    if 'derivation' in a:
        return '計算 `' + a['derivation']['expression'] + '`（内訳は下）'
    return trace_text(a['source'])


def confidence_text(a):
    return 'PROPOSED（根拠 ' + a['basis_confidence'] + '）' if a['confidence'] == 'PROPOSED' else a['confidence']


def derivation_lines(a):
    d = a['derivation']
    lines = ['- `' + a['id'] + '`: `' + d['expression'] + '` = ' + show(a['value']) + ' ' + a['unit'] + '（小数 ' + str(d['round']) + ' 桁に丸め）']
    for i in d['inputs']:
        where = ('「' + i['context'] + '」' if 'context' in i else '') + ('の ' + i['part'] if 'part' in i else '')
        lines.append('  - `' + i['name'] + '` = ' + repr(i['number']) + '（`' + i['token'] + '`、' + trace_text(i['source'])
                     + ('、' + i['field'] if i.get('field') else '') + ('、' + where if where else '') + '）')
    if d.get('assumption'):
        lines.append('  - 推定: ' + d['assumption'])
    return lines


def markdown(plan, report):
    lines = ['# A7 物理評価の準備と readiness', '', '**未実施・製造リリースなし。** この文書は `scripts/a7_readiness.py` の生成物です。', '',
             'レポート検証: '+report['report_validation']+'。発注適格性: **'+report['order_eligibility']+'**。', '',
             '## 共通記録 (Workflow F)', '',
             '各実施は `run-templates/<手順ID>.json` をコピーし、unit、計器、条件、raw証跡（ファイルとSHA-256）、結果、次の行動を埋めて `records.json` の runs に追加します。'
             '雛形の identities と plan_sha256 は生成時点の値です。実施前に `python3 scripts/a7_readiness.py --check` が通ることを確認し、変わっていれば雛形を取り直します。'
             '失敗や再加工を上書きせず別 run として追加します。', '',
             '受入値の確度: SOURCED = メーカー一次資料、MIRROR = 販売店掲載の写し、UNVERIFIED = 出典が未確認の記録、INFERRED = 推定、DESIGN = このプロジェクトの設計記録、ASSUMED = 仮定、'
             'CALCULATED = 一次資料と設計記録だけを入力にした計算、PROPOSED = レビュー用の提案（採否前。ゲートを解除しない）、UNRESOLVED = 未決（決める主体と入手先を記載）。'
             '計算値は生成時に入力の出典を照合して再計算し、計算値の確度は最も弱い入力に合わせます。'
             '各値は出典の値と一致すること、確度が出典の記載（部品 fact の provenance、記録に並ぶ確度、引用行の ASSUMED / INFERRED）を超えないことを生成時に検査します。'
             '出典は部品 fact と設計記録だけで、この計画や生成物は引用できません。範囲（min/max 等）の向きは人が出典を読んで付けたもので、自動照合していません。', '',
             '## 状態フラグ', '',
             '手順の前提と発注ゲートが読む生成物のフラグです。「ゲート」は readiness が発注ゲートで読むもの、「参考のみ」は進捗の表示でゲートを解除しません。'
             'どの手順も、自分（または自分を待つ手順）しか満たせないフラグを前提にできません（生成時に検査）。', '',
             '| 生成物 | フラグ | 現在値 | 役割 | 満たす手順 | 説明 |', '|---|---|---|---|---|---|']
    closed = {(x['artifact'], x['flag']): x['closed_by'] for x in plan['state_flags']}
    for x in report['state_flags']:
        lines.append('| '+x['artifact']+' | `'+x['flag']+'` | '+show(x['value'])+' | '+('ゲート' if x['role'] == 'GATE' else '参考のみ')+' | '
                     +('、'.join(closed[(x['artifact'], x['flag'])]) or '—（デジタル生成物）')+' | '+x['note']+' |')
    lines += ['', '## 未実施の手順', '']
    for p in plan['procedures']:
        lines += ['### '+p['id']+' — '+p['title'], '', '- 関連: '+p['issues'], '- 概要: '+p['setup'],
                  '- 根拠: `'+p['basis']+'`', ('- 基準: 採用済み（'+ACCEPTED_JA[p['criterion_accepted_by']]+'、記録 `'+p['criterion_review']['path']+'`）' if p['criterion_status'] == 'REVIEWED'
                   else '- 未決: '+p['missing_criterion']+'（区分: '+CLASS_JA[p['criterion_class']]+'）'),
                  '- 観測: NOT_MEASURED。結果: NOT_RUN。', '- 次: '+p['next_action'], '', '準備するもの:', '']
        lines += ['- '+x for x in p['inputs']] + ['', '計器・道具:', ''] + ['- '+x for x in p['tools']]
        lines += ['', '実施前の条件:', ''] + ['- '+x for x in p['preconditions']]
        lines += ['', '手順:', ''] + [str(i)+'. '+x for i, x in enumerate(p['steps'], 1)]
        lines += ['', '記録する raw 証跡（種別ごとに別ファイル）:', '', '| 種別 | 内容 |', '|---|---|']
        lines += ['| `'+k+'` | '+p['record'][k]+' |' for k in p['required_evidence_kinds']]
        lines += ['', '受入値（範囲: exact = 一致、min / max = 下限 / 上限、min_exclusive = この値を超える、range = 範囲内、reference = 比較の参照値）:', '',
                  '| ID | 基準 | 値 | 範囲 | 単位 | 確度 | 出典 / 決める主体 |', '|---|---|---|---|---|---|---|']
        for a in p['acceptance']:
            lines.append('| '+a['id']+' | '+a['criterion']+' | '+show(a['value']).replace('|', '\\|')+' | '+a.get('bound', '—')+' | '+a['unit']+' | '+confidence_text(a)+' | '+where_text(a).replace('|', '\\|')+' |')
        lines.append('')
        derived = [a for a in p['acceptance'] if 'derivation' in a]
        if derived:
            lines += ['計算の内訳:', '']
            for a in derived:
                lines += derivation_lines(a)
            lines.append('')
        proposed = [a for a in p['acceptance'] if a['confidence'] == 'PROPOSED']
        if proposed:
            lines += ['提案の理由（PROPOSED は採否前で、この手順の基準ゲートを解除しません）:', '']
            lines += ['- `'+a['id']+'`: '+a['rationale'] for a in proposed]
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
                    acceptance_checklist=[{'id': a['id'], 'criterion': a['criterion'], 'expected': a['value'], 'bound': a.get('bound'), 'unit': a['unit'],
                                           'confidence': a['confidence'], 'proposed': a['confidence'] == 'PROPOSED',
                                           'observed': None, 'verdict': None} for a in procedure['acceptance']])
    return json.dumps(template, indent=2, ensure_ascii=False)+'\n'


def mdx(text):
    out, code = [], False
    for part in text.split('`'):
        out.append(part.replace('|', '\\|') if code else part.replace('{', '&#123;').replace('}', '&#125;').replace('<', '&lt;').replace('>', '&gt;').replace('|', '\\|'))
        code = not code
    return '`'.join(out)


def owner_page_gaps(plan, report):
    """Gates of each class that have no prepared entry; the page lists them rather than hiding them."""
    current = {c: {g['gate'] for g in report['gates'] if g['class'] == c} for c in ('OWNER_DECISION', 'ACCESS_EVIDENCE_HOLD')}
    return {'OWNER_DECISION': sorted(current['OWNER_DECISION'] - {d['gate'] for d in plan['owner_decisions']}),
            'ACCESS_EVIDENCE_HOLD': sorted(current['ACCESS_EVIDENCE_HOLD'] - {r['gate'] for r in plan['evidence_requests']})}


def link(url):
    return '[開く]('+url+')' if url else '—'


def owner_page_lines(plan, report):
    classes = {g['gate']: g['class'] for g in report['gates']}
    gaps = owner_page_gaps(plan, report)
    live = [d for d in plan['owner_decisions'] if classes.get(d['gate']) == 'OWNER_DECISION']
    lines = ['', '## まとめて答えられる判断（'+str(len(live))+' 件）', '',
             'オーナーの判断ゲートを、PCB 発注を先に止めるものから順に並べています。推奨は出典に基づく提案で、オーナーの回答ではありません。'
             '回答は記録（承認ファイルやレビュー記録）にしてから反映し、それまでゲートは閉じたままです。', '']
    for n, d in enumerate(live, 1):
        lines += ['### '+str(n)+'. '+mdx(d['question']), '', '- ゲート: `'+d['gate']+'`（'+STAGES[d['stage']]+'）']
        for o in d['options']:
            lines.append('- '+('**'+mdx(o['label'])+'（推奨）**' if o['id'] == d['recommended'] else mdx(o['label']))+': '+mdx(o['consequence']))
        lines += ['- 推奨の理由: '+mdx(d['reason']), '- 出典: '+'、'.join(trace_text(t)+('「'+mdx(t['quote'])+'」' if 'quote' in t else '') for t in d['sources']), '']
    answered = [d for d in plan['owner_decisions'] if 'answer' in d]
    if answered:
        lines += ['## 回答済みの判断（'+str(len(answered))+' 件）', '', 'オーナーが自分の言葉で答えたもの。記録ファイルに原文があり、ゲートは閉じています。', '']
        for d in answered:
            words = json.loads((ROOT / OWNER_ANSWERS).read_text())
            entry = next(x for x in words['decisions'] if 'assembly:' + x['id'] == d['gate'])
            label = next(o['label'] for o in d['options'] if o['id'] == d['answer']['option'])
            lines += ['- **'+mdx(d['question'])+'** → '+mdx(label)+'（オーナーの回答、`'+d['gate']+'`）。原文「'+mdx(' '.join(entry['owner_words']))+'」、記録 `'+OWNER_ANSWERS+'`', '']
    waiting = [d['gate'] for d in plan['owner_decisions'] if 'answer' not in d and classes.get(d['gate']) not in (None, 'OWNER_DECISION')]
    if waiting:
        lines += ['次の判断（ゲートがまだ別の区分にあるもの。区分が変わるとここに並びます）: '+'、'.join('`'+g+'`' for g in waiting), '']
    if gaps['OWNER_DECISION']:
        lines += ['判断の準備がまだないゲート: '+'、'.join('`'+g+'`' for g in gaps['OWNER_DECISION']), '']
    live = [r for r in plan['evidence_requests'] if classes.get(r['gate']) == 'ACCESS_EVIDENCE_HOLD']
    downloads = {i['url'] for r in live if 'OWNER_DOWNLOAD' in r['routes'] for i in r['items']}
    lines += ['## 資料・回答待ちのゲート（'+str(len(live))+' 件）', '',
              'ブラウザで保存してほしい資料は '+str(len(downloads))+' 件です。保存したファイルをそのまま渡してもらえれば、こちらで出典として記録します。'
              'それ以外は、クラウドで取得できるもの、供給元の回答、2 台分の日付付き供給観測、実物の測定です。', '',
              '| ゲート | 入手の方法 | 何を | 必要な値 | URL | 代替 URL | 補足 |', '|---|---|---|---|---|---|---|']
    for r in live:
        for i in r['items']:
            lines.append('| `'+r['gate']+'` | '+'、'.join(ROUTES[x] for x in r['routes'])+' | '+mdx(i['what'])+' | '+mdx(i['value_needed'])+' | '
                         +link(i['url'])+' | '+link(i['fallback_url'])+' | '+mdx(i['access'])+' |')
    if gaps['ACCESS_EVIDENCE_HOLD']:
        lines += ['', '入手方法の準備がまだないゲート: '+'、'.join('`'+g+'`' for g in gaps['ACCESS_EVIDENCE_HOLD'])]
    return lines


def checklist(plan, report):
    gates = {g['gate']: g for g in report['gates']}
    known = gate_keys(plan)
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
    lines += ['', '## 残っているオーナーの作業（この順に）', '',
              '上から順に進めると、後の作業の前提がそろいます。各作業の内容と、解除するゲートの状態は下の表にあります。', '']
    rows = []
    for n, a in enumerate(plan['owner_actions'], 1):
        names = []
        for pattern in a['unblocks']:
            hit = covers(pattern)
            if pattern not in known:
                raise ValueError('owner action '+a['id']+' names unknown gate '+pattern)
            if pattern == 'run:*':
                names.append('`run:*`（'+str(len(hit))+' 手順が未実施）')
            else:
                names.append('`'+pattern+'`（'+('BLOCKED' if hit else '解除済み')+'）')
        lines.append(str(n)+'. **'+a['id']+'** '+mdx(a['title']))
        rows.append('| '+a['id']+' | '+mdx(a['detail'])+' | '+'、'.join(names)+' |')
    proposals = [(p['id'], a) for p in plan['procedures'] for a in p['acceptance'] if a['confidence'] == 'PROPOSED']
    lines += owner_page_lines(plan, report)
    lines += ['', '## 採否を待つ提案値', '',
              'エージェントが出典から用意した提案です（'+str(len(proposals))+' 件）。採るまでは該当する基準ゲートを解除しません。理由と計算は procedures.md にあります。', '',
              '| 手順 | ID | 基準 | 提案値 | 単位 |', '|---|---|---|---|---|']
    lines += ['| '+pid+' | '+a['id']+' | '+mdx(a['criterion'])+' | '+mdx(show(a['value']))+' | '+a['unit']+' |' for pid, a in proposals]
    reviewed = [p for p in plan['procedures'] if p['criterion_status'] == 'REVIEWED']
    if reviewed:
        lines += ['', '## 採用済みの合否基準', '', '採用者を区別して示します。採用は基準の確定で、測定や合格ではありません。', '']
        lines += ['- '+p['id']+': '+ACCEPTED_JA[p['criterion_accepted_by']]+'（記録 `'+p['criterion_review']['path']+'`）' for p in reviewed]
    lines += ['', '## 各作業の詳細', '', '| # | 内容 | 解除するゲート（現在の状態） |', '|---|---|---|'] + rows
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
