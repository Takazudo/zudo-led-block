#!/usr/bin/env python3
"""Selective A7 preview publication; no engineering file is written."""
import argparse
import hashlib
import json
import shutil
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELECTION = ROOT / 'scripts/a7_public_selection.json'
MANIFEST = ROOT / 'preview/a7/manifest.json'
PUBLIC = ROOT / 'doc/public/a7-preview'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def selection():
    return json.loads(SELECTION.read_text())

def glb_nodes(path):
    raw = path.read_bytes()
    magic, version, size = struct.unpack_from('<III', raw)
    if (magic, version, size) != (0x46546c67, 2, len(raw)):
        raise ValueError('Invalid GLB: ' + str(path))
    length, kind = struct.unpack_from('<II', raw, 12)
    if kind != 0x4e4f534a:
        raise ValueError('Missing GLB JSON')
    return json.loads(raw[20:20 + length])['nodes']

def make_manifest():
    s = selection()
    for entry in s['inputs'] + s['files']:
        path = ROOT / entry['source']
        if digest(path) != entry['sha256'] or path.stat().st_size != entry['bytes']:
            raise ValueError('Source changed; review and repin selection: ' + entry['source'])
    front = json.loads((ROOT / 'engineering/a7/front_panel/geometry.json').read_text())
    layout = json.loads((ROOT / 'engineering/a7/mechanical/layout.json').read_text())
    variants = []
    for entry in s['files']:
        if not entry['target'].endswith('.glb'):
            continue
        variant = entry['variant']
        nodes = glb_nodes(ROOT / entry['source'])
        report = json.loads((ROOT / Path(entry['source']).parent / 'verification.json').read_text())
        required_boards = {'engineering/a7/electronics/controller/controller.kicad_pcb', 'engineering/a7/electronics/led_leaf/led_leaf.kicad_pcb'}
        if {x['board'] for x in report.get('optical_sources', [])} != required_boards:
            raise ValueError('Current preview requires new A7 controller and leaf optical geometry')
        if not report.get('display_parts'):
            raise ValueError('Current preview lacks opaque copper/mask meshes')
        parts = {p['part']: p for p in report['parts'] + report.get('display_parts', [])}
        for source in report.get('optical_sources', []):
            if digest(ROOT / source['source']) != source['sha256'] or digest(ROOT / source['board']) != source['board_sha256']:
                raise ValueError('Stale optical source: ' + source['source'])
        names = [n['name'] for n in nodes if 'mesh' in n]
        if set(names) != set(parts) or len(names) != len(set(names)):
            raise ValueError('GLB / verification node mismatch')
        mapped = {}
        for name in names:
            group = parts[name].get('group') or s['node_groups'][name]
            mapped[name] = {'group': group, 'role': s['groups'][group]['role'], 'kind': parts[name]['kind']}
        variants.append({**entry, 'width_mm': front['variants']['2hp' if variant == '2hp' else '3hp']['width'], 'nodes': mapped, 'optical_display': report.get('optical_display'), 'optical_sources': report.get('optical_sources', [])})
    return {'schema_version': 1, 'source_revision': s['source_revision'],
            'status': 'Provisional digital study; no manufacturing release or measured qualification.',
            'units': 'mm (GLB numeric coordinates are millimetres, not glTF metre convention)',
            'cad_datum': layout['datum'],
            'display_transform': 'GLB root rotates CAD -90 degrees about X. Viewer parent rotates another -90 degrees: CAD (X,Y,Z) -> display (X,-Y,-Z). Front camera is +display Z; up is -CAD Y.',
            'height_mm': front['panel']['height'], 'pmma_mm': front['panel']['thickness'],
            'depth_target_mm': layout['z_stack']['installed_depth_target'],
            'depth_datum': 'PMMA rear Z=0; target, not measured installed bounding box',
            'groups': s['groups'], 'variants': variants}

def publication_assets():
    names = [f['target'] for f in selection()['files']] + ['manifest.json','index.html','viewer.css','boot.js','scene.js','THREE-LICENSE.txt']
    return [{'path': 'a7-preview/' + name, 'reason': 'A7 project-owned provisional assembly preview; selected source hashes in scripts/a7_public_selection.json; bundled Three.js MIT notice retained.'} for name in names]

def generate(check=False):
    text = json.dumps(make_manifest(), ensure_ascii=False, indent=2) + '\n'
    if check:
        if not MANIFEST.exists() or MANIFEST.read_text() != text:
            raise ValueError('Preview manifest drift; run pnpm preview:generate')
    else:
        MANIFEST.write_text(text)

def sync():
    generate(True)
    PUBLIC.mkdir(parents=True, exist_ok=True)
    for f in selection()['files']:
        shutil.copyfile(ROOT / f['source'], PUBLIC / f['target'])
    for name in ['manifest.json','index.html','viewer.css','boot.js']:
        shutil.copyfile(ROOT / 'preview/a7' / name, PUBLIC / name)

def check_dist(dist):
    generate(True)
    folder = dist / 'a7-preview'
    expected = {x['path'].split('/',1)[1] for x in publication_assets()}
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
    if expected != actual:
        raise ValueError(f'Unselected or missing preview assets: {expected ^ actual}')
    for f in selection()['files']:
        if digest(folder / f['target']) != f['sha256']:
            raise ValueError('Published source mismatch: ' + f['target'])
    for name in ['manifest.json','index.html','viewer.css','boot.js']:
        if digest(folder / name) != digest(ROOT / 'preview/a7' / name):
            raise ValueError('Published viewer mismatch: ' + name)
    for name in ['scene.js','THREE-LICENSE.txt']:
        if digest(folder / name) != digest(PUBLIC / name):
            raise ValueError('Published bundle mismatch: ' + name)

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('command', choices=['generate','check','sync','check-dist']);p.add_argument('dist', nargs='?', default='doc/dist'); a=p.parse_args()
    if a.command in ('generate','check'): generate(a.command == 'check')
    elif a.command == 'sync': sync()
    else: check_dist(ROOT / a.dist)
    print('PASS A7 preview ' + a.command)
