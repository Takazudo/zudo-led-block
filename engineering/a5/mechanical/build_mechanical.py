#!/usr/bin/env python3
"""Build editable A5 integration solids from declared dimensions and native PCB poses.

This is an engineering assembly study, not a production release. Mated connector
exteriors are conservative dimensioned envelopes. Cable curves are design routes;
the supplied cable's allowable bend radius and label storage still need a sample.
"""
from __future__ import annotations
import argparse, copy, hashlib, json, math
from pathlib import Path
import cadquery as cq
from cad_kernel import *

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
G=json.loads((HERE/'geometry.json').read_text())
E=json.loads((ROOT/'electronics/placement_and_connectivity.json').read_text())
BOARDS={b['name']:b for b in E['boards']}
COL={'frame':(.20,.23,.28,1),'diffuser':(.78,.89,.94,.58),
     'pcb':(.06,.39,.24,1),'led':(.97,.83,.28,1),'body':(.17,.18,.2,1),
     'connector':(.89,.85,.73,1),'metal':(.64,.68,.72,1),'wire':(.72,.24,.13,1),
     'ribbon':(.74,.40,.68,.8),'acrylic':(.75,.88,.96,.42)}

def oval_hole(cx,cy,sx,sy,z0,z1):
    if abs(sx-sy)<1e-9:return cylinder(sx/2,z0,z1,cx,cy)
    if sx>=sy:
        return cq.Workplane('XY').center(cx,cy).slot2D(sx,sy,0).extrude(z1-z0).val().translate((0,0,z0))
    return cq.Workplane('XY').center(cx,cy).slot2D(sy,sx,90).extrude(z1-z0).val().translate((0,0,z0))

def expanded_box(shape,amount=.2):
    b=shape.BoundingBox()
    return box(b.xmin-amount,b.xmax+amount,b.ymin-amount,b.ymax+amount,b.zmin-amount,b.zmax+amount)

def build(variant):
    w=G['variants'][variant]['width']; xc=w/2; dx=xc-4.9
    out=HERE/'exports'/variant; out.mkdir(parents=True,exist_ok=True)
    parts=[]; contacts=[]; cable_stats=[]
    def add(name,shape,color,kind='design_geometry',note='',source=None,
            scope='retained_module',printed=False,rot=None,group='module',metadata=None):
        p=Part(name,shape,COL.get(color,color),kind,note,source,scope,printed,rot,group,metadata or {})
        parts.append(p);return p
    def printpart(name,shape,rot=None,note=''):
        return add(name,shape,'diffuser' if 'diffuser' in name else 'frame','printable_design',note,
                   printed=True,rot=rot,group='carrier')
    front=cq.importers.importStep(str(ROOT/'front_panel/exports'/f'front_A4_{variant}_2mm.step')).val()
    add('front_acrylic_A4_unchanged',front,'acrylic','manufacturing_artwork',
        'A4 exact artwork retained; rear frost except clear strokes and declared hidden seating masks.',
        '../front_panel','front_panel',group='front')

    # PCB solids with actual PTH positions. Copper/solder are not disguised as FR4.
    for key in ['controller','power_adapter']:
        b=BOARDS[key]; x0=xc-b['width']/2;y0=b['world_origin'][1];z0=b['world_origin'][2]
        sh=box(x0,x0+b['width'],y0,y0+b['height'],z0,z0+b['thickness'])
        for hx,hy in b['holes']:sh=sh.cut(cylinder(1.1,z0-.1,z0+b['thickness']+.1,x0+hx,y0+hy))
        for c in b['components']:
            t=c['type']
            for num,(px,py) in c['pad_centers_mm'].items():
                if t=='JACK':
                    sx,sy=((.6,1.5) if num=='2' else (1.5,.6))
                elif t=='SW':sx,sy=1.8,1.2
                elif t=='PWR3':sx=sy=.5
                elif t=='IDC':sx=sy=1.0
                else:continue
                sh=sh.cut(oval_hole(x0+px,y0+py,sx,sy,z0-.1,z0+b['thickness']+.1))
            if t=='JACK':sh=sh.cut(cylinder(.6,z0-.1,z0+b['thickness']+.1,xc-2.5,y0+c['at'][1]))
        add(key+'_pcb',sh,'pcb','native_pcb_envelope',
            b['route_status']+'; native source ../electronics',group=key)
    leaf_local=box(0,9,0,82.5,-.6,0)
    for u0,v0,u1,v1 in BOARDS['led_leaf']['front_edge_notches_mm']:
        leaf_local=leaf_local.cut(box(u0-.1,u1,v0,v1,-.7,.1))
    leaf_poses={
        'left':((xc-.65,22.5,19.4),(0,0,1),(0,1,0),(-1,0,0)),
        'right':((xc+.65,105,19.4),(0,0,1),(0,-1,0),(1,0,0))}
    # The local front is n=0, with the FR4 extending to n=-0.6.
    for side,pose in leaf_poses.items():
        add(side+'_leaf_pcb',transformed(leaf_local,*pose),'pcb','native_pcb_envelope',
            'Same 82.5 x9.0 x0.6 board; one end-for-end. R<=0.5 internal notch corner requested.',group=side+'_leaf')
    bond=box(xc-.05,xc+.05,22.5,105,19.4,28.4)
    for ny in [46.7,80.8]:bond=bond.cut(box(xc-.1,xc+.1,ny-1,ny+1,19.3,20.4))
    add('leaf_bond_line_design_reserve',bond,'frame','assembly_allowance',
        '0.1 mm bond-line reserve; adhesive and clamping process not selected.',group='leaves')

    # Dimensioned controls, tails included in the same part as their body.
    for y in G['jack']['y']:
        sh=union(box(xc-3.05,xc+3.05,y-5,y+5,.6,12.6),
                 ring(3,1.8,-2.4,.6,xc,y))
        for p in G['jack']['world_relative_pads']:
            px,py=p['xy'];sx,sy=p['slot'];sx=max(.25,sx-.22);sy=max(.25,sy-.22)
            sh=sh.fuse(box(xc+px-sx/2,xc+px+sx/2,y+py-sy/2,y+py+sy/2,12.6,15.6))
        sh=sh.fuse(cylinder(.45,12.6,13.5,xc-2.5,y)).clean()
        add(f'jack_{int(y)}_PJ3582',sh,'body','manufacturer_dimensioned_envelope',
            'Nominal body; general 2-decimal tolerance +/-0.2. Pin rectangles are clearance approximations.',
            'XKB_PJ_3582_B',group='controls')
    sw=union(box(xc-3.43,xc+3.43,67.65,80.35,2.21,11.10),
             cylinder(3.175,-6.68,2.21,xc,74),cylinder(1.46,-17.09,-6.68,xc,74))
    for y in [69.3,74,78.7]:sw=sw.fuse(box(xc-.635,xc+.635,y-.38,y+.38,11.1,15.2))
    add('toggle_Dailywell_trimmed',sw.clean(),'metal','manufacturer_dimensioned_envelope',
        'M2 4.70 mm terminal pitch; factory trim to <=1 mm behind controller PCB; central lever pose only.',
        'Dailywell_1M_C908270_new',group='controls')
    add('toggle_front_nut',hexagon(7.92,-3.57,-2,xc,74,6.35),'metal','standard_hardware_envelope',
        'Large 10.8/11.99 mm lockwasher/ring omitted; body cradle supplies antirotation.',group='controls')

    # JST SH mated exterior: actual manufacturer housing plus conservative handle envelope.
    jst_local=union(box(-3,3,-1.675,2.575,0,2.95),box(-3.5,3.5,2.575,4.575,.15,2.95))
    jst_shapes={'left':[],'right':[]}
    for side,pose in leaf_poses.items():
        for ref,vv in [('J1',16.5),('J2',66.0)]:
            mated=not(side=='right' and ref=='J2')
            local=jst_local if mated else box(-3,3,-1.675,2.575,0,2.95)
            sh=transformed(local.translate((4.5,vv,0)),*pose)
            add(side+'_'+ref+'_SH4_'+('mated' if mated else 'unmated'),sh,'connector','manufacturer_dimensioned_envelope',
                'Same two-header leaf; J1 input/J2 stream-swapped link. Mated handle width7 is conservative.',
                'JST_SH',group=side+'_leaf');jst_shapes[side].append(sh)
    for i,y in enumerate([60.5],3):
        sh=transformed(jst_local,(xc,y,14.2),(1,0,0),(0,-1,0),(0,0,1))
        add(f'controller_J{i}_SH4_mated',sh,'connector','manufacturer_dimensioned_envelope',
            'Rear side; opening -Y, verified from actual native pad centers.', 'JST_SH',group='controller')
    # PicoBlade headers plus mated receptacles. Pin row offset is from the exact footprint.
    for key,y,z in [('adapter',46.7,17.4),('controller',54,12.6)]:
        sh=box(xc-2.75,xc+2.75,y-2.05,y+1.15,z-5.2,z)
        for px in [xc-1.25,xc,xc+1.25]:sh=sh.fuse(cylinder(.20,z,z+2.3,px,y))
        add(key+'_PicoBlade_mated',sh.clean(),'connector','manufacturer_dimensioned_envelope',
            'Mated height5.2 reference; native pin row. Header tails2.3 +/-0.5, not flush trimmed.',
            'Molex_530470310',group='power_adapter' if key=='adapter' else 'controller')
    # Shrouded IDC maximum exterior, with real cavity and trimmed tails.
    idc=box(xc-4.55,xc+4.55,23,43.8,8.5,17.4)
    idc=idc.cut(box(xc-3.65,xc+3.65,24.4,42.4,8.4,15.8))
    for xx in [xc-1.27,xc+1.27]:
        for yy in [28.32,30.86,33.4,35.94,38.48]:
            idc=idc.fuse(box(xx-.32,xx+.32,yy-.32,yy+.32,11,20))
    add('adapter_C5665_keyed_header_trimmed',idc.clean(),'body','manufacturer_dimensioned_envelope',
        'Max body9.1 x20.8 x8.9. Tails must be <=1.0 behind PCB. Shrouded/keyed; cavity simplified.',
        'C5665_header',group='power_adapter')
    # Reference socket uses a declared 6 mm overlap scenario; combined with its header contact region
    # is an explicitly identified expected intersection, never silently filtered.
    socket=box(xc-3.5,xc+3.5,33.4-8.69,33.4+8.69,7.6,14.5)
    socket=socket.cut(box(xc-1.7,xc+1.7,27.5,39.3,10.8,14.6))
    add('IDC_socket_REFERENCE_overlap6',socket,'connector','conditional_reference_envelope',
        'Wurth61201023021 reference ONLY. Mated overlap6 is an assumption; strain-relief cap height unresolved.',
        'Wurth_61201023021','conditional_socket',group='power_adapter')
    contacts.append(('adapter_C5665_keyed_header_trimmed','IDC_socket_REFERENCE_overlap6'))

    # All other components from current native placement, with declared maximum body envelopes.
    small=[]
    for b in E['boards']:
        for c in b['components']:
            if not c.get('fitted') or c['type'] in ['JACK','SW','SH4','PWR3','IDC','TP']:continue
            sx,sy=c['body_size_mm'];h=c['height_max_mm']
            if h<=0:continue
            cx,cy=c.get('body_center_mm',[0,0]);a=math.radians(-c['angle'])
            if c['side']=='B':cy=-cy
            px=c['at'][0]+cx*math.cos(a)-cy*math.sin(a)
            py=c['at'][1]+cx*math.sin(a)+cy*math.cos(a)
            sh=box(-sx/2,sx/2,-sy/2,sy/2,0,h).rotate((0,0,0),(0,0,1),-c['angle']).translate((px,py,0))
            color='led' if c['type']=='LED' else 'body'
            if b['name']=='led_leaf':
                for side,pose in leaf_poses.items():
                    p=add(side+'_'+c['ref'],transformed(sh,*pose),color,'native_component_max_envelope',
                          'Maximum body envelope, not vendor detailed 3D.',c.get('c_code'),group=side+'_leaf')
                    small.append(p)
            else:
                x0=xc-b['width']/2;y0=b['world_origin'][1];z0=b['world_origin'][2]
                normal=(0,0,-1) if c['side']=='F' else (0,0,1)
                sh=transformed(sh,(x0,y0,z0 if c['side']=='F' else z0+b['thickness']),(1,0,0),(0,1,0),normal)
                p=add(b['name']+'_'+c['ref'],sh,color,'native_component_max_envelope',
                      'Current native draft placement; controller routing is incomplete.',c.get('c_code'),group=b['name'])
                p.metadata={'native_ref':c['ref'],'side':c['side'],'source_at':c['at'],'source_angle':c['angle']}
                small.append(p)

    # Printable front cradle. Retains controls through body/substrate; solder is not sole restraint.
    bars=[box(.1,1.3,18,111.4,0,2.4),box(w-1.3,w-.1,18,111.4,0,2.4),
          box(.1,1.3,63,111.4,2.4,12.6),box(w-1.3,w-.1,63,111.4,2.4,12.6)]
    if variant=='3hp':
        # Electronics remain 8.8 mm wide: retain their edges with inner rails,
        # and connect the adapter forks instead of widening the shared PCB.
        for lo,hi in [(xc-4.8,xc-3.6),(xc+3.6,xc+4.8)]:
            bars.extend([box(lo,hi,18,111.4,0,2.4),box(lo,hi,63,111.4,2.4,12.6)])
    for y in [20.5,60.8,65,97]:
        half=1.8 if y==97 else 2.2
        bars.append(box(.1,w-.1,y-half,y+half,0,2.4))
    for y in [90,104]:bars.append(box(.1,w-.1,y-5.2,y+5.2,0,.6).cut(cylinder(3.2,-.1,.7,xc,y)))
    bars.append(box(.1,w-.1,67.45,80.55,0,2.21).cut(cylinder(3.25,-.1,2.3,xc,74)))
    bars.append(cylinder(2.5,0,17.4,xc,20.5).intersect(box(.1,w-.1,18,22.6,-.1,17.5)))
    for y in [60.8,65,97]:
        post=cylinder(2.5,2.3,12.6 if y!=60.8 else 5.5,xc,y)
        if y==97:post=post.intersect(box(.1,w-.1,95.2,98.8,2.2,12.7))
        bars.append(post)
    # Split edge forks around the adapter's lower end, outside the power housing.
    for lo,hi in [(xc-4.3,xc-3.05),(xc+3.05,xc+4.3)]:
        bars.extend([box(lo,hi,47,48.3,2.3,17.2),box(lo,hi,47,49.2,19.2,20.4),
                     box(lo,hi,48.2,49.2,17.2,19.2)])
    cradle=union(*bars)
    for y in [20.5,60.8,65,97]:cradle=cradle.cut(cylinder(1.1,-.1,18,xc,y))
    for y,z in [(20.5,3),(60.8,3),(20.5,14),(97,3.5)]:
        cradle=cradle.cut(hexagon(4.25,z,z+1.8,xc,y))
        cradle=cradle.cut(box(xc,w+.1,y-2.15,y+2.15,z,z+1.8))
    # Visible pockets derived from actual native front-side components. Record each subtraction.
    relief=[]
    for p in small:
        if p.group=='controller' and p.metadata.get('side')=='F':
            pocket=expanded_box(p.shape,.2)
            if cradle.intersect(pocket).Volume()>1e-5:
                cradle=cradle.cut(pocket);relief.append(p.name)
    printpart('front_cradle',cradle.clean(),note='PETG design. 1.2 mm general webs; 0.6 mm acrylic-backed jack collars. Native front-part relief: '+','.join(relief))
    retainer=box(xc-2.3,xc+2.3,63.2,66.8,14.2,15.4).cut(cylinder(1.1,14.1,15.5,xc,65))
    retainer=retainer.cut(box(xc-2.31,xc+2.31,63.19,63.5,14.19,14.6))
    printpart('controller_upper_clamp',retainer)
    lower_clamp=box(xc-2.3,xc+2.3,95.2,98.8,14.2,15.4).cut(cylinder(1.1,14.1,15.5,xc,97))
    printpart('controller_lower_clamp',lower_clamp)

    # Optical end supports and lower portal. Printed end-on, not as unsupported deep U overhangs.
    top=union(box(.1,w-.1,18,23.7,19,29.8),box(.1,w-.1,23.7,26,25.4,29.8))
    top=top.cut(box(xc-.8,xc+.8,22.3,26.1,18.8,28.6))
    top=top.cut(cylinder(1.1,18.9,29.9,xc,20.5)).cut(cylinder(2.1,27.8,29.9,xc,20.5))
    bottom=box(.1,w-.1,103.8,107,18,29.8).cut(box(xc-.8,xc+.8,103.7,105.2,19.2,28.6))
    portal=box(.1,w-.1,95.2,98.8,27,29.8).cut(box(xc-.8,xc+.8,95.1,98.9,26.9,28.6))
    supports={'top_leaf_adapter_cap':top,'bottom_leaf_cap':bottom}
    # Optical flange seats; 0.2 gap is intentional and is taken up gently by screw assembly.
    for name,sh in list(supports.items()):
        for x0,x1 in [(.1,1.7),(w-1.7,w-.1)]:
            sh=sh.cut(box(x0,x1,21.8,107.2,16.8,28.2))
        for x0,x1 in [(.2,xc-.9),(xc+.9,w-.2)]:
            sh=sh.cut(box(x0,x1,21.8,107.2,25.4,27))
        for yy in [23.5,105.5]:
            for xx in [xc-2.4,xc+2.4]:
                sh=sh.cut(cylinder(.9,24,30,xx,yy)).cut(hexagon(3.4,28.2,30,xx,yy,rotation=30))
                sh=sh.cut(cylinder(1.72,24.2,25.6,xx,yy))
        for p in small:
            if p.group in ['left_leaf','right_leaf']:
                pocket=expanded_box(p.shape,.2)
                if sh.intersect(pocket).Volume()>1e-5:sh=sh.cut(pocket)
        supports[name]=sh.clean()
        printpart(name,sh.clean(),((1,0,0),90),'PETG optical support; print on Y end face.')

    # Independent side diffusers. Local connector relief is dimensioned and visible.
    for side in ['left','right']:
        if side=='left':a,b=.3,1.5;f0,f1=.3,xc-.9
        else:a,b=w-1.5,w-.3;f0,f1=xc+.9,w-.3
        skin=union(box(a,b,22,107,17.4,28),box(f0,f1,22,107,25.6,26.8))
        skin=skin.cut(box(a-.1,b+.1,21.8,48.4,17.3,19.2))
        skin=skin.cut(box(a-.1,b+.1,46.8,49.4,17.3,20.6))
        for sh in jst_shapes[side]:
            sb=sh.BoundingBox()
            # Keep 0.6 mm skin in 2HP, full wall in 3HP where no normal conflict exists.
            if side=='left':
                pocket=box(.9 if variant=='2hp' else sb.xmin-.2,xc,
                           sb.ymin-.2,sb.ymax+.2,sb.zmin-.2,sb.zmax+.2)
            else:
                pocket=box(xc,w-.9 if variant=='2hp' else sb.xmax+.2,
                           sb.ymin-.2,sb.ymax+.2,sb.zmin-.2,sb.zmax+.2)
            skin=skin.cut(pocket)
        # Side-exit IDC ribbon access window. Conditional cable may project past 2HP outline.
        if side=='right' and variant=='3hp':skin=skin.cut(box(xc+5.85,w+.1,26.7,40.1,16.9,28.6))
        for yy in [23.5,105.5]:
            xx=xc+(-2.4 if side=='left' else 2.4)
            skin=skin.cut(cylinder(.9,25.5,26.9,xx,yy)).cut(cylinder(1.6,24.2,25.6,xx,yy))
        # End caps overlap only nominally with the skin: carve actual seating envelope with .2 clearance.
        for support in supports.values():
            # Diffuser pockets are already in supports; cut the skin only at cap external body regions.
            pass
        printpart(side+'_diffuser',skin.clean(),((0,1,0),-90 if side=='left' else 90),
                  'PETG optical geometry. Inner SH4 relief leaves0.6 mm local 2HP wall; right IDC side window is explicit.')

    # Standard fastener design envelopes. Supplier dimensions and PMMA torque remain assembly gates.
    def screw(name,x,y,z0,z1,head_z0,head_z1,r=1,hr=1.9,group='hardware'):
        add(name,union(cylinder(r,z0,z1,x,y),cylinder(hr,head_z0,head_z1,x,y)),
            'metal','standard_hardware_envelope','Nominal hardware reserve; exact supplier not selected.',group=group)
    for y in [20.5,60.8]:
        add(f'M2_front_washer_{y}',ring(2,1.1,-2.3,-2,xc,y),'metal','standard_hardware_envelope',group='hardware')
        screw(f'M2x8_front_{y}',xc,y,-2.3,5.7,-3.5,-2.3)
        add(f'M2_front_nut_{y}',hexagon(4,3,4.6,xc,y,2),'metal','standard_hardware_envelope',group='hardware')
    add('M2_front_washer_65',ring(2,1.1,-2.3,-2,xc,65),'metal','standard_hardware_envelope',group='hardware')
    screw('M2x20_front_65',xc,65,-2.3,17.7,-3.5,-2.3)
    add('M2_rear_nut_65',hexagon(4,15.4,17,xc,65,2),'metal','standard_hardware_envelope',group='hardware')
    screw('M2x12_rear_97',xc,97,3.4,15.4,15.4,16.7)
    add('M2_captive_nut_97',hexagon(4,3.5,5.1,xc,97,2),'metal','standard_hardware_envelope',group='hardware')
    screw('M2x16_top_cap',xc,20.5,11.8,27.8,27.8,29.1)
    add('M2_top_post_nut',hexagon(4,14,15.6,xc,20.5,2),'metal','standard_hardware_envelope',group='hardware')
    for side in [-1,1]:
        xx=xc+side*2.4
        for yy in [23.5,105.5]:
            screw(f'M1_6x4_{side}_{yy}',xx,yy,25.6,29.6,24.3,25.6,.8,1.5)
            add(f'M1_6_nut_{side}_{yy}',hexagon(3.2,28.2,29.5,xx,yy,1.6,30),'metal','standard_hardware_envelope',group='hardware')

    # Smooth individual wires; routing lengths/radii are measured, not just rectangular reserves.
    def cable(name,points=None,tangents=None,color='wire',path=None,endparts=()):
        print('Routing '+name,flush=True)
        if path is None:sh,stats,path=smooth_wire(points,.4,tangents)
        else:sh,stats=tube_from_path(path,.4)
        stats.update({'name':name,'wire_outer_diameter_design_reserve_mm':.8})
        cable_stats.append(stats)
        p=add(name,sh,color,'cable_route_scenario','Smooth route; actual free length, allowed bend radius and retention need qualification.',
            scope='conditional_harness',group='cables',metadata=stats)
        p.cable_path=path
        for other in endparts:contacts.append((name,other))
    def lin(a,b):return cq.Edge.makeLine(cq.Vector(*a),cq.Vector(*b))
    def arc(a,b,c):return cq.Edge.makeThreePointArc(cq.Vector(*a),cq.Vector(*b),cq.Vector(*c))
    # Analytic U-shaped route samples avoid unconstrained splines with sub-wire-radius cusps.
    def line(points,target,n=4):
        a=points[-1]
        points.extend([tuple(a[j]+(target[j]-a[j])*k/n for j in range(3)) for k in range(1,n+1)])
    def arc_yz(points,x,cy,cz,r,a0,a1,n=16,xfinish=None):
        for k in range(1,n+1):
            t=k/n;a=a0+(a1-a0)*t
            xx=x if xfinish is None else x+(xfinish-x)*(3*t*t-2*t*t*t)
            points.append((xx,cy+r*math.cos(a),cz+r*math.sin(a)))
    # Full nominal 50 mm SH routes. Exact line/circular sections retain physical tangent continuity.
    for i in range(4):
        x=xc-1.5+i; z=22.4+i;xs=xc-2.2;mid=18.8;end=55.925;yb=end-.2
        r1=(z-mid)/2;r2=(mid-15.75)/2
        ya=(50+43.575+yb-(end-yb)-math.pi*(r1+r2))/2
        a=(xs,43.575,z);b=(xs,ya,z);c=(xs,ya,mid);d=(x,yb,mid);e=(x,yb,15.75);f=(x,end,15.75)
        pts=[]
        for k in range(13):
            t=k/12;pts.append(cq.Vector(xs+(x-xs)*(3*t*t-2*t*t*t),ya+(yb-ya)*t,mid))
        bend=cq.Edge.makeSpline(pts,tangents=(cq.Vector(0,-1,0),cq.Vector(0,-1,0)))
        path=cq.Wire.assembleEdges([lin(a,b),arc(b,(xs,ya+r1,z-r1),c),bend,
                                  arc(d,(x,yb-r2,mid-r2),e),lin(e,f)])
        cable('controller_to_left_pin_'+str(i+1),path=path,
              endparts=('left_J1_SH4_mated','controller_J3_SH4_mated'))

        # Leaf-to-leaf link: four conductors fan into a 2x2 bundle in front of the leaf edge.
        xl=xc-2.2;xr=xc+2.2;zl=22.4+i;zr=22.4+i
        ra=1.75+i;ybend=93.075+ra;zturn=20.65
        zb=17.9 if i<2 else 18.8;xb=xc+(1.5 if i%2==0 else 2.5);rb=1.5
        rc=(zr-zb)/2
        constant=math.pi*ra/2+(zturn-zb-rb)+math.pi*rb+(xb-xl-2*rb)+(ybend-rb)+math.pi*rc+83.925
        yu=(constant-50)/2
        a=(xl,93.075,zl);b=(xl,ybend,zturn);c=(xl,ybend,zb+rb)
        d=(xl+rb,ybend,zb);e=(xb-rb,ybend,zb);f=(xb,ybend-rb,zb);h=(xb,yu,zb);j=(xr,yu,zr);k=(xr,83.925,zr)
        q=math.sqrt(.5)
        edges=[arc(a,(xl,93.075+ra*q,zturn+ra*q),b),lin(b,c),
               arc(c,(xl+rb-rb*q,ybend,zb+rb-rb*q),d),lin(d,e),
               arc(e,(xb-rb+rb*q,ybend-rb+rb*q,zb),f),lin(f,h)]
        pts=[]
        for n in range(25):
            t=n/24;aa=math.pi*t;xx=xb+(xr-xb)*(3*t*t-2*t*t*t)
            pts.append(cq.Vector(xx,yu-rc*math.sin(aa),zb+rc*(1-math.cos(aa))))
        edges.extend([cq.Edge.makeSpline(pts,tangents=(cq.Vector(0,-1,0),cq.Vector(0,1,0))),lin(j,k)])
        cable('leaf_link_pin_'+str(i+1),path=cq.Wire.assembleEdges(edges),
              endparts=('left_J2_SH4_mated','right_J1_SH4_mated'))
    for i in range(3):
        x=xc+(i-1)*1.25
        ym=(5.2+math.pi+44.7+math.pi*1.2+52.5+math.pi*.75+3.3-50)/2
        pts=[(x,46.7,12.2)];line(pts,(x,46.7,7),6)
        arc_yz(pts,x,44.7,7,2,0,-math.pi/2)
        line(pts,(x,ym,5),8);arc_yz(pts,x,ym,3.8,1.2,math.pi/2,3*math.pi/2)
        line(pts,(x,52.5,2.6),10);arc_yz(pts,x,52.5,4.1,1.5,-math.pi/2,0)
        line(pts,(x,54,7.4),5)
        cable('power_50mm_wire_'+str(i+1),pts,((0,0,-1),(0,0,1)),
              endparts=('adapter_PicoBlade_mated','controller_PicoBlade_mated'))
    # Correct short-side exit: quarter-circle sheet extruded across Y. R is a visible scenario only.
    R=3.0;t=.8;start=xc+3.5;z=10.5
    pts=[]
    for k in range(33):
        a=(math.pi/2)*k/32;pts.append((start+(R+t/2)*math.sin(a),z+(R+t/2)*(1-math.cos(a))))
    pts.extend([(start+R+t/2,29.8),(start+R-t/2,29.8)])
    for k in range(32,-1,-1):
        a=(math.pi/2)*k/32;pts.append((start+(R-t/2)*math.sin(a),z+(R-t/2)*(1-math.cos(a))))
    # PlaneXZ normal-Y; extrusion is transformed into Y width.
    poly=cq.Workplane('XY').polyline(pts).close().extrude(12.7).val()
    ribbon=transformed(poly,(0,39.75,0),(1,0,0),(0,0,1),(0,-1,0))
    add('IDC_ribbon_R3_side_exit_SCENARIO',ribbon,'ribbon','conditional_cable_scenario',
        'R3 radius,0.8 thick,12.7 wide are study assumptions. Actual finished-cable socket and bend are unqualified.',
        scope='conditional_ribbon',group='cables',metadata={'radius_mm':3,'qualified':False})
    contacts.append(('IDC_socket_REFERENCE_overlap6','IDC_ribbon_R3_side_exit_SCENARIO'))
    # The 50 mm harness has a manufacturer flag label, retained as explicit unresolved requirement.
    # No invented tiny label volume is substituted for its unqualified folded geometry.
    metadata={'revision':'A5','variant':variant,'width_mm':w,'rear_limit_mm':30,
       'status':'ENGINEERING_INTEGRATION_STUDY_NOT_RELEASED','native_manifest_sha256':hashlib.sha256((ROOT/'electronics/placement_and_connectivity.json').read_bytes()).hexdigest(),
       'unmodeled_required_items':[{'item':'Molex151340300 flag label','drawing_blank_mm':[12.7,35.5],
        'reason':'Final fold and storage pose not dimensioned; full installed fit remains unproven.'},
        {'item':'Actual finished IDC socket strain relief','reason':'Premade Doepfer cable socket maker not identified; reference body is shown only.'}],
       'contact_model':'Mated SH/Pico exteriors combined; reference IDC interpenetration explicit.',
       'cable_length_and_radius_mm':cable_stats}
    (out/'assembly_manifest.json').write_text(json.dumps(metadata,indent=2))
    # Save independent printable parts and the exact assembled / exploded solids.
    print_rows=[]
    for p in parts:
        if p.printed:print_rows.append(export_print(p,out/'printable'/p.name))
    (out/'printable/print_manifest.json').write_text(json.dumps(print_rows,indent=2))
    print('Exporting assembled solids',flush=True)
    step_check=export_assembly(parts,out/f'light_block_A5_{variant}_assembled',metadata)
    print('Checking every saved solid pair',flush=True)
    checks=validate(parts,w,30,contacts)
    checks['step_roundtrip']=step_check
    exploded=[]
    for p in parts:
        q=copy.copy(p)
        if p.group=='front':shift=(0,0,-16)
        elif p.name=='left_diffuser':shift=(-20,0,0)
        elif p.name=='right_diffuser':shift=(20,0,0)
        elif p.group=='left_leaf':shift=(-8,0,10)
        elif p.group=='right_leaf':shift=(8,0,10)
        elif p.name in ['top_leaf_adapter_cap','lower_optical_portal','bottom_leaf_cap']:shift=(0,0,24)
        elif p.group=='power_adapter':shift=(0,-10,7)
        elif p.group=='controller':shift=(0,5,7)
        elif p.group=='controls':shift=(0,0,-7)
        elif p.group=='hardware':shift=(0,0,8)
        else:shift=(0,0,0)
        q.shape=q.shape.translate(shift);q.metadata=dict(q.metadata,exploded_shift_mm=shift);exploded.append(q)
    checks['exploded_step_roundtrip']=export_assembly(exploded,out/f'light_block_A5_{variant}_exploded',dict(metadata,exploded=True))
    checks['retained_only_envelope_failures']=[x for x in checks['envelope_failures'] if x['scope'] not in ['conditional_harness','conditional_socket','conditional_ribbon']]
    checks['manufacturing_release']=False
    (out/'verification.json').write_text(json.dumps(checks,indent=2))
    print(json.dumps({'variant':variant,'parts':len(parts),'invalid':[p['part'] for p in checks['part_checks'] if not p['valid']],
        'intersections':checks['unexpected_intersections'],'envelope_failures':checks['envelope_failures'],
        'print_parts':[(r['name'],r['solids']) for r in print_rows],'step':checks['step_roundtrip']},indent=2),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--variant',choices=['2hp','3hp','all'],default='all');args=ap.parse_args()
    for v in (G['variants'] if args.variant=='all' else [args.variant]):build(v)
