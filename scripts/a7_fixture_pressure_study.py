#!/usr/bin/env python3
"""Experimental pressure-plate deformation screen; finite masked-domain linear solve."""
import argparse
import json
import math
from pathlib import Path
import numpy as np
from scipy.sparse.linalg import splu
from a7_fixture_plate import Plate
from a7_fixture_support import diagonal_proposal
import a7_fixture_relief as relief
ROOT=Path(__file__).resolve().parents[1]


def run(nx,ny):
    native=json.loads((ROOT/'engineering/a7/fixture/native-geometry.json').read_text())
    proposal=diagonal_proposal(native['geometry'])
    x0,y0,x1,y1=relief.PRESSURE_PLATE
    notch=proposal['notch_mm'];radius=proposal['notch_radius_mm']
    guides=[(x,relief.STOP_Y) for x in relief.GUIDE_X]
    contacts=[q['centre_mm'] for q in proposal['clamps']]
    holes=[(q,1.7) for q in guides]+[(q,2.025) for q in contacts]
    def cell_material(box):
        b=(box[0]+x0,box[1]+y0,box[2]+x0,box[3]+y0)
        # Remove entire cells touching any circular hole. Four outside corners
        # alone do not establish absence of a circular intersection.
        if any(relief._box_point_dist(b,c)<=r for c,r in holes): return False
        # Oversize the rounded opening to its rectangle for this screening mesh.
        return relief._clip(b,notch) is None
    # 5.9mm is a required minimum accepted plate thickness, not a measured sheet.
    p=Plate(x1-x0,y1-y0,nx,ny,5.9,18000,.3,cell_material=cell_material)
    supported=lambda x,y:any(1.7<math.dist((x+x0,y+y0),q)<=2.75 for q in guides)
    fixed={4*n for n,q in enumerate(p.xy) if 4*n in p.used_dofs and supported(*q)}
    free=np.array(sorted(p.used_dofs-fixed),dtype=int)
    if len(fixed)<6: raise ValueError('mesh does not resolve the preloaded support annuli')
    lu=splu(p.k[free,:][:,free].tocsc())
    load_vectors={}
    for i,j,ids in p.cells:
        b=(i*p.hx+x0,j*p.hy+y0,(i+1)*p.hx+x0,(j+1)*p.hy+y0)
        if not any(relief._box_point_dist(b,c)<3.1 for c in contacts): continue
        # A continuous Hermite shape-load vector is a convex combination of
        # these sixteen Bernstein control functionals, including slope DOFs.
        for row in p.bezier:
            terms=tuple((int(d),round(float(v),12)) for d,v in zip(ids,row) if v)
            load_vectors[terms]=True
    if not load_vectors: raise ValueError('mesh does not resolve modeled loading patches')
    worst=0.0
    for terms in load_vectors:
        f=np.zeros(p.size)
        for dof,value in terms: f[dof]=value
        u=np.zeros(p.size);u[free]=lu.solve(f[free])
        lo,hi=p.displacement_bounds(u)
        worst=max(worst,abs(lo),abs(hi))
    total_force=34.88
    bending=total_force*worst
    # Deliberately conservative screening allowance: entire force traversing a
    # 40mm-long, 1mm-wide, 5.9mm-thick strip; kappa=5/6, G=E/[2(1+nu)].
    shear=total_force*40/((5/6)*(18000/(2*1.3))*1*5.9)
    return {'status':'EXPERIMENTAL_NOT_ACCEPTED','mesh':[nx,ny],'retained_elements':len(p.cells),
            'support_nodes':len(fixed),'continuous_load_control_vectors':len(load_vectors),
            'minimum_required_plate_thickness_mm':5.9,'E_assumed_MPa':18000,'nu_assumed':.3,
            'ring_load_total_upper_N':total_force,'bending_envelope_mm':bending,
            'load_mapping':'continuous retained-material patches within3.1mm of thread axes; exact threaded interface is not resolved','shear_strip_allowance_mm':shear,
            'combined_screen_mm':bending+shear,'target_bound_mm':.09,
            'conditions':['minimum accepted plate thickness and modulus','preloaded screw/stop annuli remain seated',
                          '40mm by1mm continuous load-path shear allowance review','mesh/load-interface approximation convergence',
                          'actual native CAD notch/thread interference','independent model review']}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nx',type=int,default=74);parser.add_argument('--ny',type=int,default=32)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not 20<=args.nx<=120 or not 10<=args.ny<=52: parser.error('outside finite mesh budget')
    result=run(args.nx,args.ny);args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
