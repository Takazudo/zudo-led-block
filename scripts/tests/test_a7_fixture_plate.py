"""Analytical benchmarks for an EXPERIMENTAL plate model, not fixture approval."""
import math
from pathlib import Path
import sys
import unittest
import numpy as np
import scipy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from a7_fixture_plate import Plate, matrix, shape


class PlateBenchmarks(unittest.TestCase):
    def test_rigid_plane_has_no_bending_energy(self):
        k=matrix(2,3,.7,18000,.3)
        q=np.array([v for y in (0,3) for x in (0,2) for v in (1+2*x-3*y,2,-3,0)])
        self.assertAlmostEqual(float(q@k@q),0,places=8)
        self.assertTrue(np.allclose(k,k.T))

    def test_simply_supported_sinusoidal_plate_converges_to_closed_form(self):
        errors=[]
        for n in (4,8):
            p=Plate(10,10,n,n,.7,18000)
            f=p.distributed_load(lambda x,y:math.sin(math.pi*x/10)*math.sin(math.pi*y/10))
            result=p.solve(f,lambda x,y:x==0 or y==0 or x==10 or y==10)
            exact=1/(18000*.7**3/(12*(1-.3**2))*math.pi**4*(2/100)**2)
            errors.append(abs(result['max_up_mm']/exact-1))
            self.assertAlmostEqual(result['force_balance_N'],0,places=7)
        self.assertLess(errors[1],errors[0]/10)
        self.assertLess(errors[1],.001)

    def test_interior_bulge_is_not_hidden_by_zero_nodal_displacements(self):
        p=Plate(1,1,1,1,.7,18000)
        u=np.zeros(p.size)
        for n,(x,y) in enumerate(p.xy): u[4*n+1]=1 if x==0 else -1
        lo,hi=p.displacement_bounds(u)
        self.assertEqual(max(u[::4]),0)
        self.assertGreaterEqual(hi,.25)  # w=x*(1-x), max at x=.5

    def test_unilateral_contact_releases_tensile_middle_support(self):
        p=Plate(10,10,2,2,.7,18000)
        force=p.point_load(5,5,.1)
        corners=((0,0),(10,0),(0,10),(10,10))
        for q in corners: force+=p.point_load(*q,-1)
        support=lambda x,y:(x,y) in corners or (x,y)==(5,5)
        result=p.solve(force,support,unilateral=True)
        for n,xy in enumerate(p.xy):
            if not support(*xy): continue
            self.assertGreaterEqual(result['u'][4*n],-1e-9)
            self.assertGreaterEqual(result['reaction'][4*n],-1e-7)
            self.assertAlmostEqual(result['u'][4*n]*result['reaction'][4*n],0,places=8)
        self.assertGreater(result['u'][4*4],0)
        self.assertNotIn(4*4,result['active'])
        residual=result['reaction']+force
        self.assertAlmostEqual(sum(residual[::4]),0,places=8)
        self.assertAlmostEqual(sum(q[0]*residual[4*n]+residual[4*n+1] for n,q in enumerate(p.xy)),0,places=8)
        self.assertAlmostEqual(sum(q[1]*residual[4*n]+residual[4*n+2] for n,q in enumerate(p.xy)),0,places=8)

    def test_sparse_contact_seed_matches_all_contacts(self):
        p=Plate(10,10,4,4,.7,18000)
        f=p.distributed_load(lambda x,y:-1)
        support=lambda x,y:x in (0,10) or y in (0,10)
        all_contacts=p.solve(f,support,unilateral=True)
        seeded=p.solve(f,support,unilateral=True,initial_active=p.seed_contacts(support))
        self.assertTrue(np.allclose(all_contacts['u'],seeded['u'],atol=1e-10))
        self.assertTrue(np.allclose(all_contacts['reaction'],seeded['reaction'],atol=1e-8))

    def test_removed_material_rejects_load(self):
        p=Plate(10,10,2,2,.7,18000,material=lambda x,y:x<=5)
        with self.assertRaisesRegex(ValueError,'removed material'):
            p.solve(p.point_load(10,10,1),lambda x,y:x==0)

    def test_continuous_shape_load_is_convex_combination_of_control_loads(self):
        p=Plate(2,3,1,1,.7,18000)
        bern=lambda t:((1-t)**3,3*t*(1-t)**2,3*t*t*(1-t),t**3)
        for x in (0,.13,.5,.93,1):
            for y in (0,.17,.5,.87,1):
                bx,by=bern(x),bern(y)
                weights=[]
                for i,j in ((0,0),(1,0),(0,1),(1,1)):
                    a,b=3*i,3*j;di,dj=1-2*i,1-2*j
                    weights.extend((bx[a]*by[b],bx[a+di]*by[b],bx[a]*by[b+dj],bx[a+di]*by[b+dj]))
                self.assertAlmostEqual(sum(weights),1)
                self.assertTrue(all(w>=0 for w in weights))
                self.assertTrue(np.allclose(np.array(weights)@p.bezier,shape(x,y,2,3)))

    def test_cell_intersection_detects_hole_with_all_corners_outside(self):
        circle=(2.5,2.5)
        def intersects(b):
            dx=max(b[0]-circle[0],0,circle[0]-b[2])
            dy=max(b[1]-circle[1],0,circle[1]-b[3])
            return math.hypot(dx,dy)<=1
        corners_only=Plate(10,10,2,2,.7,18000,material=lambda x,y:math.dist((x,y),circle)>1)
        whole_cell=Plate(10,10,2,2,.7,18000,cell_material=lambda b:not intersects(b))
        self.assertEqual(len(corners_only.cells),4)
        self.assertEqual(len(whole_cell.cells),3)

    def test_point_load_preserves_total_force(self):
        p=Plate(10,10,4,4,.7,18000)
        f=p.point_load(3.1,5.7,6.35)
        self.assertAlmostEqual(sum(f[::4]),6.35)

if __name__=='__main__': unittest.main()
