#!/usr/bin/env python3
"""Finite single-case screen of the full-pin fixture candidate; NOT acceptance.

Run under heavy-guard and an external finite timeout. Each invocation evaluates
one force corner and writes its identities/results separately from native evidence.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import sys
import time
import numpy as np
from a7_fixture_plate import Plate
import a7_fixture_relief as relief
from a7_fixture_support import diagonal_proposal

ROOT=Path(__file__).resolve().parents[1]


def run(nx,ny,case,max_iterations):
    native_path=ROOT/'engineering/a7/fixture/native-geometry.json'
    manifest_path=ROOT/'engineering/a7/fixture/manifest.json'
    native=json.loads(native_path.read_text())
    probes=json.loads(manifest_path.read_text())['pads']
    design=relief.design(native['geometry'],probes,candidate='optical_full_pin')
    candidate=diagonal_proposal(native['geometry'])
    sc=design['support_carrier']
    # These holes lie outside the nominal board but are retained in the predicate.
    holes=[(q['board_xy_mm'],1.0) for q in sc['datum_pins']]
    holes += [(q['board_xy_mm'],1.7) for q in sc['guides']]
    holes += [(q,3.0) for q in sc['fasteners_board_mm']]
    holes += [(q,1.0) for q in sc['alignment_dowels_board_mm']]
    def supported(x,y):
        return (relief._in_box(sc['bounds_board_mm'],x,y)
                and not any(relief._in_window(w,x,y) for w in sc['windows'])
                and all(np.hypot(x-q[0],y-q[1])>radius for q,radius in holes))
    # 7N is below the 7.0507N calculated minimum at .52mm compression.
    # The self-consistent displacement/setting prerequisites are not yet certified.
    corners=list(itertools.product((7.0,17.44),(7.0,17.44),*((.947907,1.27),)*5))
    f1,f2,*probe_forces=corners[case]
    plate=Plate(16.2,62.9,nx,ny,.7,18000,.3)
    force=np.zeros(plate.size)
    for q,f in zip(candidate['clamps'],(f1,f2)):
        force+=plate.point_load(*q['centre_mm'],-f)
    for q,f in zip(probes,probe_forces): force+=plate.point_load(*q['board_xy_mm'],f)
    start=time.monotonic()
    result=plate.solve(force,supported,unilateral=True,max_iterations=max_iterations,initial_active=plate.seed_contacts(supported))
    residual=result['reaction']+force
    moments=[sum(q[axis]*residual[4*n]+residual[4*n+1+axis] for n,q in enumerate(plate.xy)) for axis in (0,1)]
    candidates=[4*n for n,q in enumerate(plate.xy) if supported(*q)]
    summary={k:v for k,v in result.items() if k not in ('u','reaction','active')}
    summary.update({'active_contacts':len(result['active']),
                    'minimum_support_gap_mm':float(min(result['u'][candidates])),
                    'minimum_support_reaction_N':float(min(result['reaction'][candidates])),
                    'maximum_contact_complementarity_N_mm':float(max(abs(result['u'][candidates]*result['reaction'][candidates]))),
                    'moment_residuals_N_mm':[float(x) for x in moments],
                    'clamp_displacements_mm':[plate.value(*q['centre_mm'],result['u']) for q in candidate['clamps']],
                    'probe_displacements_mm':[plate.value(*q['board_xy_mm'],result['u']) for q in probes],
                    'elapsed_seconds':time.monotonic()-start})
    files=[native_path,manifest_path,Path(__file__),ROOT/'scripts/a7_fixture_plate.py',ROOT/'scripts/a7_fixture_relief.py',ROOT/'scripts/a7_fixture_support.py']
    return {'status':'EXPERIMENTAL_NOT_ACCEPTED','candidate':'optical_full_pin','mesh':[nx,ny],
            'force_corner':case,'forces_N':{'clamps':[f1,f2],'probes':probe_forces},
            'plate_assumptions':{'thickness_mm':.7,'E_MPa':18000,'poisson_ratio':.3,'holes_and_copper_stiffness':'omitted'},
            'force_lower_bound_prerequisite':'setting gauge +/-0.05mm, stack +/-0.20mm, |board w|<=0.10mm and |plate w|<=0.09mm, nominal compression0.91mm =>0.52..1.30mm; not yet certified',
            'native_scope':'historical geometry; NOT current optical PCB native verification',
            'native_board_sha256':native['board_sha256'],
            'inputs_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
            'geometry_candidate':candidate,'result':summary,
            'remaining':['current native binding','mesh convergence','all force corners','pressureplate compression bound',
                         'actual fabrication/registration tolerance qualification','independent review','CAD interference']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nx',type=int,default=20);parser.add_argument('--ny',type=int,default=78)
    parser.add_argument('--case',type=int,choices=range(128),default=127)
    parser.add_argument('--max-iterations',type=int,default=1200)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not 2<=args.nx<=40 or not 2<=args.ny<=160 or not 1<=args.max_iterations<=2500:
        parser.error('mesh/iteration budget outside finite supported range')
    output=run(args.nx,args.ny,args.case,args.max_iterations)
    args.output.write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps({'status':output['status'],'mesh':output['mesh'],'case':output['force_corner'],'result':output['result']}))

if __name__=='__main__':main()
