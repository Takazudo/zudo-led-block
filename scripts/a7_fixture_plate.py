"""Experimental Kirchhoff plate calculation; not a native fixture acceptance result.

Bogner-Fox-Schmit rectangular C1 elements: tensor cubic Hermite interpolation,
4 DOFs per vertex (w, dw/dx, dw/dy, d2w/dxdy). Units mm, N, MPa.
The caller owns support geometry, material assumptions and load cases. Positive
w/force is up. Unilateral supports may push up only. No thermal/contact test.
"""
from __future__ import annotations
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve


def hermite(t, h, order=0):
    polys = ([1, 0, -3, 2], [0, h, -2*h, h], [0, 0, 3, -2], [0, 0, -h, h])
    return np.array([np.polynomial.polynomial.polyval(t, np.polynomial.polynomial.polyder(p, order)) / h**order for p in polys])


def shape(x, y, hx, hy, dx=0, dy=0):
    a, b = hermite(x, hx, dx), hermite(y, hy, dy)
    return np.array([a[2*i+di] * b[2*j+dj] for j in (0, 1) for i in (0, 1)
                     for di, dj in ((0, 0), (1, 0), (0, 1), (1, 1))])


def matrix(hx, hy, thickness, modulus, poisson):
    d = modulus * thickness**3 / (12 * (1-poisson**2))
    c = d * np.array([[1, poisson, 0], [poisson, 1, 0], [0, 0, 2*(1-poisson)]])
    k = np.zeros((16, 16))
    # 4 points integrate the tensor polynomial exactly (degree <=6).
    points, weights = np.polynomial.legendre.leggauss(4)
    for px, wx in zip(points, weights):
        for py, wy in zip(points, weights):
            x, y = (px+1)/2, (py+1)/2
            b = np.array([shape(x,y,hx,hy,2,0), shape(x,y,hx,hy,0,2), shape(x,y,hx,hy,1,1)])
            k += b.T @ c @ b * wx * wy * hx * hy / 4
    return k


class Plate:
    def __init__(self, width, height, nx, ny, thickness, modulus, poisson=0.3, material=None, cell_material=None):
        self.width, self.height, self.nx, self.ny = width, height, nx, ny
        self.hx, self.hy = width/nx, height/ny
        self.xy = [(i*self.hx,j*self.hy) for j in range(ny+1) for i in range(nx+1)]
        self.size = 4*len(self.xy)
        self.cells = []
        rows, cols, vals = [], [], []
        ke = matrix(self.hx,self.hy,thickness,modulus,poisson)
        for j in range(ny):
            for i in range(nx):
                ids = self.ids(i,j)
                if cell_material is not None and not cell_material((i*self.hx,j*self.hy,(i+1)*self.hx,(j+1)*self.hy)):
                    continue
                if material is not None and not all(material((i+di)*self.hx,(j+dj)*self.hy)
                                                    for di,dj in ((0,0),(1,0),(0,1),(1,1))):
                    continue
                self.cells.append((i,j,ids))
                rows.extend(np.repeat(ids,16));cols.extend(np.tile(ids,16));vals.extend(ke.ravel())
        self.bezier=np.zeros((16,16))
        for n,(i,j) in enumerate(((0,0),(1,0),(0,1),(1,1))):
            a,b=(1-2*i)*self.hx/3,(1-2*j)*self.hy/3
            for r,coeff in enumerate(((1,0,0,0),(1,a,0,0),(1,0,b,0),(1,a,b,a*b))):
                self.bezier[4*n+r,4*n:4*n+4]=coeff
        self.used_dofs = set(rows)
        self.k = coo_matrix((vals,(rows,cols)),shape=(self.size,self.size)).tocsr()

    def ids(self,i,j):
        return np.array([4*((j+dj)*(self.nx+1)+i+di)+d for dj in (0,1) for di in (0,1) for d in range(4)])

    def point_load(self,x,y,force):
        i,j = min(int(x/self.hx),self.nx-1),min(int(y/self.hy),self.ny-1)
        f=np.zeros(self.size)
        f[self.ids(i,j)] = force*shape(x/self.hx-i,y/self.hy-j,self.hx,self.hy)
        return f

    def distributed_load(self,fn):
        f=np.zeros(self.size)
        points,weights=np.polynomial.legendre.leggauss(4)
        for i,j,ids in self.cells:
            for px,wx in zip(points,weights):
                for py,wy in zip(points,weights):
                    x,y=(px+1)/2,(py+1)/2
                    f[ids]+=shape(x,y,self.hx,self.hy)*fn((i+x)*self.hx,(j+y)*self.hy)*wx*wy*self.hx*self.hy/4
        return f

    def value(self,x,y,u):
        i,j=min(int(x/self.hx),self.nx-1),min(int(y/self.hy),self.ny-1)
        return float(shape(x/self.hx-i,y/self.hy-j,self.hx,self.hy)@u[self.ids(i,j)])

    def seed_contacts(self,support):
        candidates=[4*n for n,xy in enumerate(self.xy) if 4*n in self.used_dofs and support(*xy)]
        if len(candidates)<3: raise ValueError('at least three supports required for rigid plane restraint')
        xy=lambda n:np.array(self.xy[n//4])
        a=min(candidates,key=lambda n:sum(xy(n)))
        b=max(candidates,key=lambda n:np.linalg.norm(xy(n)-xy(a)))
        v=xy(b)-xy(a)
        area=lambda n:abs(v[0]*(xy(n)-xy(a))[1]-v[1]*(xy(n)-xy(a))[0])
        c=max(candidates,key=area)
        if area(c)<1e-9: raise ValueError('supports are collinear')
        return [a,b,c]

    def displacement_bounds(self,u):
        """Conservative extrema: bicubic Bezier control-net convex hull, not only nodes."""
        controls=np.array([u[ids] for _,_,ids in self.cells])@self.bezier.T
        return float(np.min(controls)),float(np.max(controls))

    def solve(self,force,support,unilateral=False,max_iterations=250,initial_active=None):
        candidates=np.array([4*n for n,xy in enumerate(self.xy) if 4*n in self.used_dofs and support(*xy)],dtype=int)
        active=set(candidates.tolist()) if initial_active is None else set(initial_active)
        if not active.issubset(set(candidates.tolist())):
            raise ValueError('initial contacts must belong to material/support candidates')
        if any(abs(force[n])>1e-12 for n in set(range(self.size))-self.used_dofs):
            raise ValueError('load applied to a removed material DOF')
        u=np.zeros(self.size)
        for iteration in range(max_iterations):
            free=np.array(sorted(self.used_dofs-active),dtype=int)
            target=np.zeros(self.size);target[free]=spsolve(self.k[free,:][:,free],force[free])
            if not np.all(np.isfinite(target)):
                raise ValueError('singular support configuration')
            if not unilateral:
                u=target;reaction=self.k@u-force
                break
            direction=target-u
            crossings=[(-u[n]/direction[n],n) for n in candidates if n not in active
                       and direction[n]<-1e-10 and target[n]<-1e-9]
            if crossings:
                alpha,node=min(crossings)
                u+=max(0.0,min(1.0,alpha))*direction
                u[node]=0.0;active.add(node)
                continue
            u=target;reaction=self.k@u-force
            tensile=[n for n in active if reaction[n]<-1e-6]
            if not tensile:
                break
            active.remove(min(tensile,key=lambda n:reaction[n]))
        else:
            raise ValueError('unilateral support solver did not converge within finite iteration limit')
        lo,hi=self.displacement_bounds(u)
        return {'u':u,'reaction':reaction,'active':sorted(active),'iterations':iteration+1,
                'max_up_mm':hi, 'max_down_mm':-lo,
                'bound_basis':'bicubic Bezier control-net convex hull; conservative over every element interior',
                'nodal_max_up_mm':float(max(u[::4])), 'nodal_max_down_mm':float(-min(u[::4])),
                'force_balance_N':float(sum(reaction[::4])+sum(force[::4]))}
