#!/usr/bin/env python3
"""Bounded high-density placement exploration. Does not route or release a board.

Uses native footprints, courtyard bounds, copper bounds and through-hole tail
keepouts. Result remains subject to native DRC and actual 3D assembly review.
"""
import json, math, random
from pathlib import Path
import pcbnew as p
from design_data import ROOT, make_controller

def mm(x):return p.FromMM(x)
def xy(x,y):return p.VECTOR2I(mm(x),mm(y))
def box(z):
    bb=z.GetBoundingBox();o=bb.GetOrigin()
    return (p.ToMM(o.x),p.ToMM(o.y),p.ToMM(o.x+bb.GetWidth()),p.ToMM(o.y+bb.GetHeight()))
def union(bs):return (min(z[0] for z in bs),min(z[1] for z in bs),max(z[2] for z in bs),max(z[3] for z in bs))
def shift(b,x,y):return (b[0]+x,b[1]+y,b[2]+x,b[3]+y)
def expand(b,n):return(b[0]-n,b[1]-n,b[2]+n,b[3]+n)
def overlaps(a,b):return min(a[2],b[2])-max(a[0],b[0])>1e-6 and min(a[3],b[3])-max(a[1],b[1])>1e-6
PLUGIN=p.PCB_IO_MGR.FindPlugin(p.PCB_IO_MGR.KICAD_SEXP)
def geometry(c,side,angle):
    board=p.BOARD()
    fp=PLUGIN.FootprintLoad(str(ROOT/'footprints'/'LightBlock.pretty'),c['footprint'])
    board.Add(fp)
    if side=='B':fp.Flip(xy(0,0),True)
    fp.SetOrientationDegrees(angle)
    cy=[box(z) for z in fp.GraphicalItems() if z.GetLayer()==(p.F_CrtYd if side=='F' else p.B_CrtYd)]
    pads=[(box(z),z.GetAttribute() in(p.PAD_ATTRIB_PTH,p.PAD_ATTRIB_NPTH)) for z in fp.Pads()]
    tails=[]
    for z in fp.Pads():
        if z.GetAttribute() in(p.PAD_ATTRIB_PTH,p.PAD_ATTRIB_NPTH):
            o=z.GetPosition();s=z.GetDrillSize();a=z.GetOrientationDegrees()%180
            sx,sy=p.ToMM(s.x),p.ToMM(s.y)
            if 45<a<135:sx,sy=sy,sx
            tails.append((p.ToMM(o.x)-sx/2-.12,p.ToMM(o.y)-sy/2-.12,p.ToMM(o.x)+sx/2+.12,p.ToMM(o.y)+sy/2+.12))
    return {'cy':union(cy) if cy else union([x[0] for x in pads]),'pads':pads,'tails':tails,'side':side,'angle':angle}
def placed(g,x,y,ref):return dict(ref=ref,side=g['side'],cy=shift(g['cy'],x,y),pads=[(shift(b,x,y),t) for b,t in g['pads']],tails=[shift(z,x,y) for z in g['tails']])
def fits(obj,obstacles):
    for b,t in obj['pads']:
        if b[0]<.2-1e-6 or b[1]<.2-1e-6 or b[2]>8.6+1e-6 or b[3]>62.7+1e-6:return False
    for o in obstacles:
        same=obj['side']==o['side']
        if same and overlaps(obj['cy'],o['cy']):return False
        if any(overlaps(obj['cy'],tail) for tail in o['tails']):return False
        for b,t in obj['pads']:
            for z,ot in o['pads']:
                if (same or t or ot) and overlaps(expand(b,.155),z):return False
    return True

def main():
    b=make_controller();cs={c['ref']:c for c in b['components']}
    fixed={'J1','J2','J3','J5','SW1','U1','U6','U7','U2','L1','C1','C2','C3','C4','TP1','TP2','TP3','TP4','TP5'}
    cs['U1']['at']=[5.1,11.5]
    cs['L1'].update(at=[6.1,2.7],side='B',angle=0)
    cs['U2'].update(at=[1.6,2.4],side='B',angle=90)
    cs['C1'].update(at=[2.0,1.5],side='F',angle=0)
    cs['C2'].update(at=[6.4,1.5],side='F',angle=0)
    cs['C3'].update(at=[1.2,11.5],side='F',angle=90)
    cs['C4'].update(at=[.8,5.71],side='B',angle=90)
    for i in range(1,6):cs[f'TP{i}'].update(at=[1.4+(i-1)*1.5,32.2],side='B',angle=0)
    cs['J3']['angle']=0
    obstacles=[];out={};geo={}
    for c in cs.values():
        for side in ['F','B']:
            for angle in [0,90,180,270]:geo[c['ref'],side,angle]=geometry(c,side,angle)
    for r in fixed:
        c=cs[r];g=geo[r,c['side'],c['angle']];obstacles.append(placed(g,*c['at'],r));out[r]={k:c[k] for k in('at','side','angle')}
    for x,y in b['holes']:
        for side in ['F','B']:obstacles.append(dict(ref='M2',side=side,cy=(x-2.1,y-2.1,x+2.1,y+2.1),pads=[],tails=[]))
    # Largest parts first, then put bypass and signal passives near their intended blocks.
    order=['U4','U3','U5','Q1','D3','D1','D2','C15','C16','C8','C7','C5','C6','C9','C10','C11','C12','C13','C17','C14','R1','R2']
    order += [r for r in cs if r not in fixed and r not in order]
    grid=[(round(.7+i*.2,3),round(.7+j*.2,3)) for j in range(308) for i in range(38)]
    failures=[]
    for r in order:
        c=cs[r];pref=c['at']
        if r=='L1':pref=[4.4,2.7]
        if r=='U2':pref=out.get('L1',{'at':[4.4,2.7]})['at']
        candidates=[]
        for side in ['F','B']:
            for angle in [0,90]:
                g=geo[r,side,angle]
                for x,y in grid:
                    # Runtime cost bound: sorted candidates prefer original side and local circuit region.
                    cost=abs(y-pref[1])+abs(x-pref[0])*.7+(0 if side==c['side'] else 3)+(0 if angle==c['angle']%180 else .3)
                    candidates.append((cost,x,y,side,angle))
        candidates.sort()
        found=None
        for _,x,y,s,a in candidates:
            obj=placed(geo[r,s,a],x,y,r)
            if fits(obj,obstacles):found=(obj,x,y,s,a);break
        if found:
            obj,x,y,s,a=found;obstacles.append(obj);out[r]={'at':[x,y],'side':s,'angle':a};print(r, out[r],flush=True)
        else:failures.append(r);print('UNPLACED',r,flush=True)
    result={'status':'provisional geometric placement; native DRC and 3D required','unplaced':failures,'placements':out}
    (ROOT/'design'/'controller_placement_experiment.json').write_text(json.dumps(result,indent=2)+'\n')
    print('FINISHED',len(out),'unplaced',failures)

if __name__=='__main__':main()
