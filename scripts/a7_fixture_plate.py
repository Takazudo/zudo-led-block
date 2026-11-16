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
    def __init__(self, width, height, nx, ny, thickness, modulus, poisson=0.3):
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
                self.cells.append((i,j,ids))
                rows.extend(np.repeat(ids,16));cols.extend(np.tile(ids,16));vals.extend(ke.ravel())
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

    def solve(self,force,support,unilateral=False,max_iterations=30):
        candidates=np.array([4*n for n,xy in enumerate(self.xy) if support(*xy)],dtype=int)
        active=set(candidates.tolist())
        for iteration in range(max_iterations):
            free=np.array(sorted(set(range(self.size))-active),dtype=int)
            u=np.zeros(self.size);u[free]=spsolve(self.k[free,:][:,free],force[free])
            reaction=self.k@u-force
            if not np.all(np.isfinite(u)):
                raise ValueError('singular support configuration')
            if not unilateral:
                break
            # Primal-dual active set: remove tensile reactions, restore penetrated support nodes.
            remove={n for n in active if reaction[n] - self.k[n,n]*u[n] < -1e-7}
            add={n for n in candidates if n not in active and reaction[n] - self.k[n,n]*u[n] > 1e-7}
            if not remove and not add:
                break
            active=(active-remove)|add
        else:
            raise ValueError('unilateral support solver did not converge within finite iteration limit')
        return {'u':u,'reaction':reaction,'active':sorted(active),'iterations':iteration+1,
                'max_up_mm':float(max(u[::4])), 'max_down_mm':float(-min(u[::4])),
                'force_balance_N':float(sum(reaction[::4])+sum(force[::4]))}
