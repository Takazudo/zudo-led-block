#!/usr/bin/env python3
"""Behavioral interface assertions over KiCad XML netlists, driven by a reviewed role map.

Replaces PR #14's "A6 controller netlist must equal A5" identity check and the
pin-number-hardcoded engineering/a5/integration/check_schematic_interfaces.py for
revisions whose jack/switch parts change. The *behavior* is fixed here in code;
the *pin identities* come from a role map JSON (exact-part evidence), so a new
jack or switch changes the role map, never the assertion.

Covered behavior: passive CV IN-to-THRU, jack returns and unused normals, the
CV pickup/buffer/affine/filter/ADC chain (C13 upstream of R7), mode encoding
(grounded common, two pulled-up inputs, ON/PGM/CV truth table from the switch's
contact table), LED power enable/fault, both independent LED streams through
the translator, cable and both leaves, and the power adapter polarity.

A role whose value is {"unresolved": "..."} makes every assertion that uses it
fail; an unresolved map can never pass. Reviewed A5 review of the old
assertions and what changed is in engineering/a7/verification/interface_review.md.

Usage:
  python3 scripts/native_gate/interface.py --roles ROLES.json \
      --netlist controller=C.xml --netlist led_leaf=L.xml --netlist power_adapter=P.xml --output OUT.json
Exit 0 only when every assertion passed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate as ev  # noqa: E402

MODE_TRUTH = {'ON': (0, 1), 'PGM': (1, 1), 'CV': (1, 0)}  # (MODE_A, MODE_B); 0 = pulled to GND by the switch
DESIGNS = ('controller', 'led_leaf', 'power_adapter')
REVIEWED_STATUS = {'reviewed', 'reviewed_reference'}


class RoleError(Exception):
    pass


def load_netlist(path: Path) -> dict:
    """{'REF.PIN': net} via the evaluator's single netlist parser (one duplicate-pin rule for all checks)."""
    _, pins = ev.parse_netlist(path)
    return {f'{r}.{p}': n for (r, p), n in pins.items()}


class Ctx:
    def __init__(self, nets: dict, roles: dict):
        self.nets, self.roles = nets, roles
        self.checks: list[dict] = []

    def pins(self, role: str) -> list[str]:
        design, _, _ = role.partition(':')
        v = self.roles.get(design, {}).get(role.partition(':')[2])
        if v is None:
            raise RoleError(f'role {role} missing from role map')
        if isinstance(v, dict):
            raise RoleError(f"role {role} unresolved: {v.get('unresolved', v)}")
        return [v] if isinstance(v, str) else list(v)

    def net(self, role: str) -> str | None:
        design = role.partition(':')[0]
        ps = self.pins(role)
        if len(ps) != 1:
            raise RoleError(f'role {role} names {len(ps)} pins where one is required')
        return self.nets[design].get(ps[0])

    def record(self, cid: str, label: str, fn) -> None:
        try:
            passed, detail = fn()
        except RoleError as e:
            passed, detail = False, {'error': str(e)}
        except KeyError as e:
            passed, detail = False, {'error': f'netlist for design {e} not supplied'}
        self.checks.append({'id': cid, 'check': label, 'passed': bool(passed), **detail})

    def same(self, cid: str, label: str, *roles: str) -> None:
        def fn():
            got = {}
            for r in roles:
                design = r.partition(':')[0]
                for p in self.pins(r):
                    got[f'{design}:{p}'] = self.nets[design].get(p)
            vals = list(got.values())
            return all(v is not None for v in vals) and len(set(vals)) == 1, {'exported_nets': got}
        self.record(cid, label, fn)

    def distinct(self, cid: str, label: str, a: str, b: str) -> None:
        def fn():
            na, nb = self.net(a), self.net(b)
            return na is not None and nb is not None and na != nb, {'nets': [na, nb]}
        self.record(cid, label, fn)

    def unused(self, cid: str, label: str, role: str) -> None:
        """Each pin exists in the netlist (KiCad exports a no-connect pin as a single-pin net) and is alone on its net."""
        def fn():
            design = role.partition(':')[0]
            bad, missing = {}, []
            for p in self.pins(role):
                n = self.nets[design].get(p)
                if n is None:
                    missing.append(p)
                elif sum(1 for v in self.nets[design].values() if v == n) > 1:
                    bad[p] = n
            return not bad and not missing, {'connected': bad, 'missing_from_netlist': missing}
        self.record(cid, label, fn)

    def covers(self, cid: str, label: str, *roles: str) -> None:
        """The roles name one component, and together name exactly every pin it has in the netlist."""
        def fn():
            design = roles[0].partition(':')[0]
            named = [p for r in roles for p in self.pins(r)]
            refs = {p.split('.')[0] for p in named}
            if len(refs) != 1:
                raise RoleError(f'roles {list(roles)} must name one component, got {sorted(refs)}')
            ref = refs.pop()
            have = {p for p in self.nets[design] if p.split('.')[0] == ref}
            dup = sorted({p for p in named if named.count(p) > 1})
            return set(named) == have and not dup, {'netlist_pins': sorted(have), 'role_pins': sorted(set(named)),
                                                    'unnamed': sorted(have - set(named)), 'not_in_netlist': sorted(set(named) - have),
                                                    'named_twice': dup}
        self.record(cid, label, fn)


def mode_truth(ctx: Ctx) -> tuple[bool, dict]:
    """Derive (MODE_A, MODE_B) per switch position from the part's contact table and the netlist."""
    table = ctx.roles.get('controller', {}).get('switch_positions')
    if isinstance(table, dict) and 'unresolved' in table:
        raise RoleError(f"role controller:switch_positions unresolved: {table['unresolved']}")
    if not isinstance(table, dict) or set(table) != set(MODE_TRUTH):
        raise RoleError(f'switch_positions must define exactly {sorted(MODE_TRUTH)}')
    sw = [ctx.pins(f'controller:{r}') for r in ('sw.common', 'sw.throw_a', 'sw.throw_b')]
    refs = {q.split('.')[0] for grp in sw for q in grp}
    if len(refs) != 1:
        raise RoleError(f'switch roles must name one component, got {sorted(refs)}')
    common, a_pins, b_pins = ({q.split('.')[1] for q in grp} for grp in sw)
    got = {}
    for pos, closed in table.items():
        pairs = {frozenset(x.split('-')) for x in closed}
        if any(len(pr) != 2 for pr in pairs):
            raise RoleError(f'switch position {pos}: contacts must be "PIN-PIN"')
        a = 0 if any(pr & common and pr & a_pins for pr in pairs) else 1
        bb = 0 if any(pr & common and pr & b_pins for pr in pairs) else 1
        got[pos] = (a, bb)
    ok = all(got[p] == MODE_TRUTH[p] for p in MODE_TRUTH)
    return ok, {'derived': {k: list(v) for k, v in got.items()}, 'required': {k: list(v) for k, v in MODE_TRUTH.items()}}


def harness(ctx: Ctx) -> tuple[bool, dict]:
    """Two straight 1:1 SH4 harnesses: controller J3 -> left leaf J1, left leaf J2 -> right leaf J1."""
    c, leaf = ctx.nets['controller'], ctx.nets['led_leaf']
    cj = ctx.pins('controller:harness.connector')
    lj1 = ctx.pins('led_leaf:harness.input')
    lj2 = ctx.pins('led_leaf:harness.bridge')
    if not (len(cj) == len(lj1) == len(lj2)):
        raise RoleError('harness connector pin lists differ in length')
    left_in = {leaf.get(lj1[i]): c.get(cj[i]) for i in range(len(cj))}
    left_x = [left_in.get(leaf.get(lj2[i])) for i in range(len(cj))]
    right_in = {leaf.get(lj1[i]): left_x[i] for i in range(len(cj))}
    din = leaf.get(ctx.pins('led_leaf:pixel.first_din')[0])
    vdd = leaf.get(ctx.pins('led_leaf:pixel.first_vdd')[0])
    gnd = leaf.get(ctx.pins('led_leaf:pixel.first_gnd')[0])
    dl, dr = ctx.net('controller:led.data_l_cable'), ctx.net('controller:led.data_r_cable')
    vled, cgnd = ctx.net('controller:led.vled'), ctx.net('controller:mcu.vss')
    need = {'din': din, 'vdd': vdd, 'gnd': gnd, 'data_l': dl, 'data_r': dr, 'vled': vled, 'gnd_controller': cgnd}
    missing = sorted(k for k, v in need.items() if v is None)
    if missing:
        return False, {'missing_nets': missing}
    det = {'left_first_pixel_net': left_in.get(din), 'right_first_pixel_net': right_in.get(din),
           'right_vdd_net': right_in.get(vdd), 'right_gnd_net': right_in.get(gnd)}
    ok = (dl is not None and dr is not None and dl != dr and left_in.get(din) == dl and right_in.get(din) == dr
          and left_in.get(vdd) == vled and right_in.get(vdd) == vled and left_in.get(gnd) == cgnd and right_in.get(gnd) == cgnd)
    return ok, det


def run(nets: dict, roles: dict) -> list[dict]:
    x = Ctx(nets, roles)
    C, L, P = 'controller:', 'led_leaf:', 'power_adapter:'
    # CV jacks: passive THRU, returns, normals
    x.same('cv.passive_thru', 'CV IN tip, CV THRU tip and the pickup input share one passive net',
           C + 'jack_in.tip', C + 'jack_thru.tip', C + 'cv.pickup_in')
    x.same('cv.jack_returns', 'Jack sleeve/ring returns and MCU VSS share ground',
           C + 'jack_in.returns', C + 'jack_thru.returns', C + 'mcu.vss')
    x.unused('cv.normals_in_unused', 'CV IN normal/switch contacts unused', C + 'jack_in.normals')
    x.unused('cv.normals_thru_unused', 'CV THRU normal/switch contacts unused', C + 'jack_thru.normals')
    x.covers('cv.jack_in_pins_covered', 'CV IN jack: tip, returns and normals name every pin of the part',
             C + 'jack_in.tip', C + 'jack_in.returns', C + 'jack_in.normals')
    x.covers('cv.jack_thru_pins_covered', 'CV THRU jack: tip, returns and normals name every pin of the part',
             C + 'jack_thru.tip', C + 'jack_thru.returns', C + 'jack_thru.normals')
    # CV conditioning chain (unchanged behavior; VADC=(100/133)*(VDD/2+CV/8) depends on these nodes)
    x.same('cv.pickup_mid', '20 Mohm pickup midpoint into follower', C + 'cv.pickup_mid')
    x.same('cv.follower', 'OPA197 voltage follower output', C + 'cv.follower')
    x.same('cv.affine_node', 'Four-resistor affine node with C13 upstream of R7', C + 'cv.affine_node')
    x.same('cv.affine_feeds', 'Affine VDD feeds share MCU VDD', C + 'cv.affine_feeds', C + 'mcu.vdd')
    x.same('cv.filter_node', 'Protected buffer input after R7', C + 'cv.filter_node')
    x.distinct('cv.c13_before_r7', 'C13 charge passes through R7 before the buffer input', C + 'cv.c13', C + 'cv.filter_in')
    x.same('cv.c13_on_r7_input', 'C13 sits on the R7 input side', C + 'cv.c13', C + 'cv.r7_in')
    x.same('cv.output_follower', 'Output follower into series resistor', C + 'cv.output_follower')
    x.same('cv.adc', 'ADC input after the 100/133 divider', C + 'cv.adc_node', C + 'mcu.adc')
    x.same('cv.grounds', 'Divider, buffer and pickup grounds share MCU VSS', C + 'cv.grounds', C + 'mcu.vss')
    # Mode setting switch
    x.same('mode.common_gnd', 'Mode switch common grounded', C + 'sw.common', C + 'mcu.vss')
    x.same('mode.a_input', 'MODE_A throw, MCU input and pull-up share one net', C + 'sw.throw_a', C + 'mcu.mode_a', C + 'mode.a_pullup_node')
    x.same('mode.b_input', 'MODE_B throw, MCU input and pull-up share one net', C + 'sw.throw_b', C + 'mcu.mode_b', C + 'mode.b_pullup_node')
    x.same('mode.pullups_to_vdd', 'Both mode pull-ups return to MCU VDD', C + 'mode.a_pullup_rail', C + 'mode.b_pullup_rail', C + 'mcu.vdd')
    x.covers('mode.switch_pins_covered', 'Mode switch: common, throws and spare contacts name every pin of the part',
             C + 'sw.common', C + 'sw.throw_a', C + 'sw.throw_b', C + 'sw.unused')
    x.unused('mode.spare_contacts_unused', 'Switch contacts outside the mode encoding are unconnected', C + 'sw.unused')
    x.distinct('mode.inputs_distinct', 'MODE_A and MODE_B are separate nets', C + 'mcu.mode_a', C + 'mcu.mode_b')
    x.record('mode.truth_table', 'Switch positions encode ON=01, PGM=11, CV=10 (centre/open = PROGRAM)', lambda: mode_truth(x))
    # LED power
    x.same('power.enable', 'LED enable MCU pin drives the NPN base resistor', C + 'mcu.led_enable', C + 'power.enable_base_r')
    x.same('power.base_pulldown', 'NPN default-off base pull-down', C + 'power.base_node')
    x.same('power.switch_enable', 'Active-low current-limit switch enable', C + 'power.switch_en')
    x.same('power.fault', 'FAULT output to MCU with pull-up', C + 'power.fault', C + 'mcu.fault')
    x.same('power.vled_shared', 'Shared current-limited VLED feeds translator and the LED harness', C + 'led.vled_nodes', C + 'led.vled')
    x.same('power.cable_pos', 'Controller power cable positive pin to its input diode', C + 'power.cable_pos')
    x.same('power.cable_neg', 'Controller power cable negative pin to its input diode', C + 'power.cable_neg')
    # LED streams
    x.same('led.left_mcu', 'Left stream MCU timer pin to translator', C + 'mcu.data_l', C + 'led.translator_in_l')
    x.same('led.right_mcu', 'Right stream MCU timer pin to translator', C + 'mcu.data_r', C + 'led.translator_in_r')
    x.same('led.translator_dir', 'Translator direction and VCCA tied to MCU VDD', C + 'led.translator_dir', C + 'mcu.vdd')
    x.same('led.left_damping', 'Left translator output through damping resistor', C + 'led.left_out')
    x.same('led.right_damping', 'Right translator output through damping resistor', C + 'led.right_out')
    x.same('led.left_cable', 'Left damped data on its cable pin', C + 'led.data_l_cable', C + 'led.data_l_cable_pin')
    x.same('led.right_cable', 'Right damped data on its cable pin', C + 'led.data_r_cable', C + 'led.data_r_cable_pin')
    x.distinct('led.streams_distinct', 'Left and right streams are electrically separate', C + 'led.data_l_cable', C + 'led.data_r_cable')
    x.same('leaf.this_stream', 'Leaf THIS stream to first pixel and bridge', L + 'leaf.this_stream')
    x.same('leaf.other_stream', 'Leaf OTHER stream passes to bridge', L + 'leaf.other_stream')
    x.distinct('leaf.streams_distinct', 'Leaf input streams stay separate', L + 'leaf.this_in', L + 'leaf.other_in')
    x.same('leaf.chain_1', 'Pixel chain 1 to 2', L + 'pixel.chain_1')
    x.same('leaf.chain_2', 'Pixel chain 2 to 3', L + 'pixel.chain_2')
    x.same('leaf.chain_3', 'Pixel chain 3 to 4', L + 'pixel.chain_3')
    x.same('leaf.power', 'Leaf and bridge VLED distribution', L + 'leaf.power')
    x.same('leaf.ground', 'Leaf and bridge ground distribution', L + 'leaf.ground')
    x.record('led.two_streams', 'Two 1:1 harnesses deliver independent left/right streams, VLED and GND to both four-pixel chains',
             lambda: harness(x))
    # Power adapter (cable reversal compensation)
    x.same('adapter.neg', 'IDC negative rail to reversed cable pin', P + 'adapter.neg')
    x.same('adapter.gnd', 'IDC ground to cable ground', P + 'adapter.gnd')
    x.same('adapter.pos', 'IDC positive rail to reversed cable pin', P + 'adapter.pos')
    return x.checks


def check(netlists: dict[str, Path], roles_path: Path) -> dict:
    roles = json.loads(roles_path.read_text())
    nets, errors = {}, []
    for d, p in netlists.items():
        try:
            nets[d] = load_netlist(p)
        except (OSError, ValueError, ET.ParseError, ev.Fail) as e:
            errors.append(f'{d}: {e}')
    checks = run(nets, roles) if not errors else []
    if roles.get('status') not in REVIEWED_STATUS or (roles.get('status') == 'reviewed' and not roles.get('review')):
        checks.append({'id': 'roles.reviewed', 'check': 'Role map is reviewed (status and review record)', 'passed': False,
                       'status': roles.get('status'), 'review': roles.get('review')})
    return {'method': 'Behavioral interface assertions on KiCad XML netlists via a reviewed role map',
            'roles': str(roles_path), 'roles_sha256': hashlib.sha256(roles_path.read_bytes()).hexdigest(),
            'role_map_status': roles.get('status'),
            'netlists': {d: {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None}
                         for d, p in netlists.items()},
            'errors': errors, 'checks': checks,
            'all_passed': not errors and bool(checks) and all(c['passed'] for c in checks),
            'limits': ['No hardware test', 'Does not prove analog behaviour, routing or switch lever direction',
                       'Harness composition assumes intact straight 1:1 manufacturer cables']}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--roles', type=Path, required=True)
    ap.add_argument('--netlist', action='append', required=True, help='design=path')
    ap.add_argument('--output', type=Path)
    a = ap.parse_args()
    nl = {}
    for item in a.netlist:
        d, _, p = item.partition('=')
        if d not in DESIGNS or not p:
            ap.error(f'bad --netlist {item!r}')
        nl[d] = Path(p)
    res = check(nl, a.roles)
    text = json.dumps(res, indent=1) + '\n'
    if a.output:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(text)
    print(json.dumps({'all_passed': res['all_passed'], 'checks': len(res['checks']), 'errors': res['errors'],
                      'failures': [c for c in res['checks'] if not c['passed']]}, indent=1))
    return 0 if res['all_passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
