#!/usr/bin/env python3
"""Regenerate A5 native KiCad designs with the installed KiCad Python module.

Run with KiCad 10's Python `pcbnew` available. No internet, PDF parser, or
external recovered package is required. Board placement is a design draft;
only the LED leaf and power adapter are routed by this script.
"""
import json, math, re, shutil, uuid, hashlib
from collections import Counter, defaultdict
from pathlib import Path
import pcbnew as p
from design_data import ROOT, PARTS, PIN_DEFS, all_boards

NS=uuid.UUID('99c06823-a7e1-4d4e-a538-d1579ee671e1')
def uid(s): return str(uuid.uuid5(NS,s))
def q(s): return json.dumps(str(s),ensure_ascii=False)
def mm(v): return p.FromMM(v)
def xy(x,y): return p.VECTOR2I(mm(x),mm(y))
def fnum(x): return f'{x:.6f}'.rstrip('0').rstrip('.') or '0'
def vmm(v): return [round(p.ToMM(v.x),6),round(p.ToMM(v.y),6)]
def layers(*nums):
    out=p.LSET()
    for n in nums:out.AddLayer(n)
    return out

FPDIR=ROOT/'footprints'/'LightBlock.pretty'
NATIVE=ROOT/'native'
SOURCE=ROOT/'footprints'/'upstream'
PLUGIN=p.PCB_IO_MGR.FindPlugin(p.PCB_IO_MGR.KICAD_SEXP)
for d in(FPDIR,NATIVE,SOURCE,ROOT/'reports'): d.mkdir(parents=True,exist_ok=True)
UPSTREAM={
 'QFN28':'QFN-28_4x4mm_P0.5mm.kicad_mod',
 'JST_SH4':'JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal.kicad_mod',
 'PICO3':'Molex_PicoBlade_53047-0310_1x03_P1.25mm_Vertical.kicad_mod',
 'IDC10':'IDC-Header_2x05_P2.54mm_Vertical.kicad_mod',
}
# Initial source staging only: subsequent portable runs use footprints/upstream.
for fn in [*UPSTREAM.values(),'LICENSE.md']:
    src=ROOT/'references'/'kicad_upstream'/fn
    if not (SOURCE/fn).exists() and src.exists(): shutil.copy2(src,SOURCE/fn)

FP_META={}
def drawrect(fp,w,h,layer,x=0,y=0):
    z=p.PCB_SHAPE(fp); z.SetShape(p.SHAPE_T_RECT); z.SetStart(xy(x-w/2,y-h/2)); z.SetEnd(xy(x+w/2,y+h/2)); z.SetWidth(mm(.05 if layer==p.F_CrtYd else .1)); z.SetLayer(layer); fp.Add(z)

def pad(fp,num,x,y,sx,sy,drill=None,npth=False,oval=False):
    z=p.PAD(fp); z.SetNumber(str(num)); z.SetPosition(xy(x,y)); z.SetSize(xy(sx,sy))
    if drill is None:
        z.SetAttribute(p.PAD_ATTRIB_SMD); z.SetShape(p.PAD_SHAPE_ROUNDRECT); z.SetRoundRectRadiusRatio(.1)
        z.SetLayerSet(layers(p.F_Cu,p.F_Mask,p.F_Paste))
    else:
        z.SetAttribute(p.PAD_ATTRIB_NPTH if npth else p.PAD_ATTRIB_PTH)
        z.SetShape(p.PAD_SHAPE_OVAL if oval else p.PAD_SHAPE_CIRCLE)
        ds=(drill,drill) if isinstance(drill,(int,float)) else drill
        z.SetDrillSize(xy(*ds)); z.SetDrillShape(p.PAD_DRILL_SHAPE_OBLONG if ds[0]!=ds[1] else p.PAD_DRILL_SHAPE_CIRCLE)
        ls=p.LSET.AllCuMask(); ls.AddLayer(p.F_Mask); ls.AddLayer(p.B_Mask); z.SetLayerSet(ls)
    fp.Add(z); return z

def footprint(name,body,height,courtyard=None,attrs=p.FP_SMD):
    fp=p.FOOTPRINT(None); fp.SetFPID(p.LIB_ID('LightBlock',name)); fp.SetValue(name); fp.SetReference('REF**'); fp.SetAttributes(attrs)
    drawrect(fp,*body,p.F_Fab)
    cy=courtyard or (body[0]+.5,body[1]+.5)
    drawrect(fp,*cy,p.F_CrtYd)
    FP_META[name]=dict(body_size_mm=list(body),body_center_mm=[0,0],height_max_mm=height,courtyard_size_mm=list(cy),source='A5 manufacturer-derived land pattern')
    return fp

def save_fp(name,fp):
    for field in (fp.Reference(),fp.Value()): field.SetLayer(p.F_Fab); field.SetVisible(False)
    PLUGIN.FootprintSave(str(FPDIR),fp)

def generate_footprints():
    upstream_meta={
     'QFN28':([4,4],[0,0],.6,[5.24,5.24]),
     'JST_SH4':([6,4.25],[0,.45],2.95,[7.8,6.56]),
     'PICO3':([5.5,3.2],[1.25,-.45],4.2,[6.5,4.2]),
     'IDC10':([9.1,20.8],[1.27,5.08],8.9,[9.9,21.36]),
    }
    for name,fn in UPSTREAM.items():
        fp=PLUGIN.FootprintLoad(str(SOURCE),Path(fn).stem)
        if fp is None: raise RuntimeError(f'Cannot load licensed footprint {fn}')
        fp.SetFPID(p.LIB_ID('LightBlock',name)); fp.SetValue(name)
        if name in ('IDC10','PICO3'):
            # The exact C5665 housing is wider than the board; its outline belongs
            # on Fab, not an impossible clipped silkscreen. Copper pins are exact.
            for item in list(fp.GraphicalItems()):
                if item.GetLayer()==p.F_SilkS and item.GetClass()=='PCB_SHAPE':item.SetLayer(p.F_Fab)
            if name=='IDC10':drawrect(fp,9.1,20.8,p.F_Fab,1.27,5.08)
        b,c,h,cy=upstream_meta[name]
        FP_META[name]=dict(body_size_mm=b,body_center_mm=c,height_max_mm=h,courtyard_size_mm=cy,source='KiCad official footprint; dimensions checked against exact manufacturer drawing',upstream_file='footprints/upstream/'+fn)
        save_fp(name,fp)
    for name,body,ph,pc,ps in [('R0603',(1.6,.8),.55,.8,(.9,.95)),('C0603',(1.6,.8),.9,.8,(.9,.95)),('C0805',(2,1.25),1.35,1.0,(1,1.4)),('C1206',(3.2,1.6),1.8,1.45,(1.2,1.9))]:
        fp=footprint(name,body,ph,(2*pc+ps[0]+.4,ps[1]+.4))
        for i,x in enumerate([-pc,pc],1): pad(fp,i,x,0,*ps)
        save_fp(name,fp)
    for name,n in [('DBV5',5),('DBV6',6),('TSOT26',6)]:
        xp,sx,sy=(1.1,1.0,.7) if name=='TSOT26' else (1.3,1.1,.6)
        fp=footprint(name,(1.7,3.0),1.0 if name=='TSOT26' else 1.45,(2*xp+sx+.4,3.4))
        loc=[(-xp,-.95),(-xp,0),(-xp,.95),(xp,.95)]
        loc += [(xp,-.95)] if n==5 else [(xp,0),(xp,-.95)]
        for i,(x,y) in enumerate(loc,1): pad(fp,i,x,y,sx,sy)
        save_fp(name,fp)
    fp=footprint('SOT23',(1.4,3.04),1.1,(3.4,3.44))
    for i,x,y in [(1,-1,-.95),(2,-1,.95),(3,1,0)]: pad(fp,i,x,y,1,.7)
    save_fp('SOT23',fp)
    fp=footprint('DCU8',(2.1,2.4),.9,(4.35,2.8))
    for i in range(1,9): pad(fp,i,-1.55 if i<=4 else 1.55,(-.75+(i-1)*.5) if i<=4 else (.75-(i-5)*.5),.85,.3)
    save_fp('DCU8',fp)
    fp=footprint('SOD323F',(1.7,1.25),.7,(3.4,1.65))
    pad(fp,1,-1.1,0,.8,1);pad(fp,2,1.1,0,.8,1);save_fp('SOD323F',fp)
    fp=footprint('SPM4020_LR',(4.6,4.3),2.0,(5.45,4.8))
    pad(fp,1,-1.65,0,1.65,2.3);pad(fp,2,1.65,0,1.65,2.3);save_fp('SPM4020_LR',fp)
    fp=footprint('WS2812B_2020_V6',(2.35,2.15),.99,(3.03,2.65))
    for i,x,y in [(3,-.915,-.55),(2,.915,-.55),(4,-.915,.55),(1,.915,.55)]:pad(fp,i,x,y,.7,.7)
    save_fp('WS2812B_2020_V6',fp)
    fp=footprint('PJ3582_ROT90',(6.3,10.2),15.4,(6.8,10.7),p.FP_THROUGH_HOLE)
    FP_META['PJ3582_ROT90']['body_axial_nominal_mm']=12
    FP_META['PJ3582_ROT90']['barrel_projection_nominal_mm']=3
    # Drawing top view transformed X=manufacturerY, Y=-manufacturerX.
    for i,x,y in [(2,2.5,0),(3,1.75,-3.9),(4,-1.75,-2.5),(5,-1.75,2.5),(6,1.75,3.9)]:
        if i==2: pad(fp,i,x,y,1.0,1.9,(.6,1.5),oval=True)
        else: pad(fp,i,x,y,1.9,1.0,(1.5,.6),oval=True)
    pad(fp,'',-2.5,0,1.2,1.2,1.2,npth=True)
    save_fp('PJ3582_ROT90',fp)
    fp=footprint('DAILYWELL_M2_SP',(6.86,12.7),19.28,(7.36,13.2),p.FP_THROUGH_HOLE)
    # Body shoulder seats1.50mm in front of PCB. Height includes lever to tip.
    FP_META['DAILYWELL_M2_SP']['notes']='Terminal pitch4.70mm;1.27x0.76mm rectangular blade. Finished oval1.8x1.2mm engineering clearance; pad2.3x1.7mm provides0.25mm nominal annulus. A1.6x1.0 capsule did not contain the terminal corners with tolerance. General tail trim1.0mm behind1.6mmPCB; J4 mated-plug tail conflict is still unresolved.'
    for i,y in [(1,-4.7),(2,0),(3,4.7)]: pad(fp,i,0,y,2.3,1.7,(1.8,1.2),oval=True)
    save_fp('DAILYWELL_M2_SP',fp)
    fp=footprint('TESTPAD',(1,1),0,(1.2,1.2),p.FP_EXCLUDE_FROM_BOM|p.FP_EXCLUDE_FROM_POS_FILES)
    z=pad(fp,1,0,0,1,1);z.SetShape(p.PAD_SHAPE_CIRCLE);z.SetLayerSet(layers(p.F_Cu,p.F_Mask));save_fp('TESTPAD',fp)

def symbol_definition(name,pins):
    # Physical pin number is always shown. Multi-pin devices are blocks; passives use IEC rectangles.
    passive=name in ('R','C','L','RECT')
    w=5.08 if passive else 15.24
    count=math.ceil(len(pins)/2)
    h=max(5.08,(count+1)*2.54)
    loc=[]
    for i,(num,pn,pt) in enumerate(pins):
        left=i<count
        y=(count-1)*1.27-(i if left else i-count)*2.54
        x=-(w/2+5.08) if left else (w/2+5.08)
        loc.append((num,pn,pt,x,y,0 if left else 180))
    a=[f'(symbol "LightBlock:{name}" (pin_names (offset 0.8)) (in_bom yes) (on_board yes)',f'(property "Reference" "{name[0]}" (at 0 {h/2+3} 0) (effects (font (size 1.27 1.27))))',f'(property "Value" "{name}" (at 0 {h/2+1} 0) (effects (font (size 1.27 1.27))))',f'(symbol "{name}_0_1" (rectangle (start {-w/2} {h/2}) (end {w/2} {-h/2}) (stroke (width 0.254) (type default)) (fill (type background))))',f'(symbol "{name}_1_1"']
    for num,pn,pt,x,y,ang in loc:
        a.append(f'(pin {pt} line (at {x} {y} {ang}) (length 5.08) (name {q(pn)} (effects (font (size 1.1 1.1)))) (number {q(num)} (effects (font (size 1.1 1.1)))))')
    a.append('))')
    return '\n'.join(a),loc,h

def make_schematic(b):
    name=b['name']; root_id=uid(name+'/sheet'); bd=NATIVE/name;bd.mkdir(parents=True,exist_ok=True)
    cs=[dict(c) for c in b['components']]
    for i,net in enumerate(b['power_flags'],1): cs.append(dict(ref=f'#FLG{i:02}',type='PWR_FLAG',value='Power source declaration',mpn='',c_code='',footprint='',nets={'1':net},group='power' if name=='controller' else name,at=[0,0],fitted=False))
    defs={}
    for c in cs:
        typ=c['type']; pins=PIN_DEFS.get(typ,[('1','1','passive'),('2','2','passive')])
        defs[typ]=symbol_definition(typ,pins)
    paper='A2' if name=='controller' else 'A3'
    a=[f'(kicad_sch (version 20250114) (generator "light_block_a5") (uuid "{root_id}") (paper "{paper}")',f'(title_block (title {q(b["title"])}) (date "2026-11-06") (rev "A5") (company "Light Block") (comment 1 "Engineering draft. Controller is not routed. No hardware qualification claimed."))', '(lib_symbols',*[x[0] for x in defs.values()],')']
    offsets={'power':(40,52),'logic':(230,52),'analog':(420,52),'leaf':(50,65),'led_leaf':(50,240),'adapter':(60,70),'power_adapter':(60,200)}
    counts=defaultdict(int)
    if name=='controller':
        for x,title in [(20,'POWER / DEFAULT-OFF LED SWITCH'),(210,'MCU / DUAL DATA / SERVICE'),(400,'PASSIVE CV THRU / SENSING / ADC')]:
            a.append(f'(text {q(title)} (at {x} 20 0) (effects (font (size 2.2 2.2)) (justify left)) (uuid {q(uid(name+title))}))')
        notes='Identical net labels are connected. U6 senses through 20 Mohm; U7 buffers the ADC.\nADC=(100/133)*(VDD/2+CV/8). TPS2552-1 uses active-low EN; PA5 HIGH enables via NPN.\nPJ-3582 pins 4/5 detect insertion and are unused. Pin 6 TIP directly connects IN to THRU.\nPower transients, MLCC bias, fault heat and connector continuity require hardware tests.'
    else: notes='Two identical LED leaves. J1: GND/VLED/THIS/OTHER. J2: GND/VLED/OTHER/THIS.\nController J3 carries independent left/right streams. Cable1 to left J1; cable2 from left J2 to right J1.\nThe final right J2 remains unused. Both completed SH4 cables are straight1:1.' if name=='led_leaf' else 'Molex151340300 is 1↔3 reversed: adapter1=-12V,2=GND,3=+12V; controller1=+12V,2=GND,3=-12V.\nIDCpins1/2=-12V(red stripe),3..8=GND,9/10=+12V. No active components on this board.'
    a.append(f'(text {q(notes)} (at 20 {397 if name=="controller" else 260} 0) (effects (font (size 1.4 1.4)) (justify left)) (uuid {q(uid(name+"notes"))}))')
    for c in cs:
        group=c['group']; j=counts[group];counts[group]+=1
        x0,y0=offsets.get(group,(50,65)); x=x0+(j%3)*85; y=y0+(j//3)*52
        if name=='controller':
            row=j//3
            x=x0+(j%3)*58.42
            y=y0 if row==0 else y0+46.99+(row-1)*35.56
        if name=='power_adapter': x=80+j*160;y=100
        # Keep every electrical endpoint on the standard 50 mil connection grid.
        x=round(x/1.27)*1.27; y=round(y/1.27)*1.27
        typ=c['type']; loc,h=defs[typ][1:]; sid=uid(name+'/'+c['ref']);fp='LightBlock:'+c['footprint'] if c['footprint'] else ''
        a.append(f'(symbol (lib_id "LightBlock:{typ}") (at {x} {y} 0) (unit 1) (in_bom {"yes" if c["fitted"] else "no"}) (on_board {"yes" if c["footprint"] else "no"}) (dnp no) (uuid "{sid}")')
        for pn,pv,py,hidden in [('Reference',c['ref'],y-h/2-5,False),('Value',c['value'],y-h/2-2.5,False),('Footprint',fp,y,True),('MPN',c['mpn'],y,True),('LCSC',c['c_code'],y,True)]:
            a.append(f'(property {q(pn)} {q(pv)} (at {x} {py} 0) (effects (font (size 1.15 1.15)) {"(hide yes)" if hidden else ""}))')
        for num,*_ in loc:a.append(f'(pin {q(num)} (uuid {q(uid(name+c["ref"]+"pin"+num))}))')
        a.append(f'(instances (project {q(name)} (path "/{root_id}" (reference {q(c["ref"])}) (unit 1)))))')
        for num,pn,pt,px,py,ang in loc:
            ax,ay=x+px,y-py; net=c['nets'].get(num)
            if net is None:
                a.append(f'(no_connect (at {ax} {ay}) (uuid {q(uid(sid+num+"nc"))}))');continue
            ex=ax+(-6.35 if px<0 else 6.35)
            a.append(f'(wire (pts (xy {ax} {ay}) (xy {ex} {ay})) (stroke (width 0) (type default)) (uuid {q(uid(sid+num+"wire"))}))')
            a.append(f'(label {q(net)} (at {ex} {ay} 0) (effects (font (size 1.15 1.15)) (justify {"right" if px<0 else "left"} bottom)) (uuid {q(uid(sid+num+"label"))}))')
    a.append(')')
    (bd/(name+'.kicad_sch')).write_text('\n'.join(a)+'\n')
    library_defs=[definition[0].replace('(symbol "LightBlock:', '(symbol "', 1)
                  for definition in defs.values()]
    (bd/'LightBlock.kicad_sym').write_text(
        '(kicad_symbol_lib (version 20241209) (generator "light_block_a5")\n'
        +'\n'.join(library_defs)+'\n)\n')
    (bd/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "LightBlock") (type "KiCad") (uri "${KIPRJMOD}/LightBlock.kicad_sym") (options "") (descr "Self-contained A5 symbols with manufacturer pin numbers")))\n')
    (bd/'fp-lib-table').write_text('(fp_lib_table (version 7) (lib (name "LightBlock") (type "KiCad") (uri "${KIPRJMOD}/../../footprints/LightBlock.pretty") (options "") (descr "Self-contained A5 exact part footprints")))\n')
    pro={'meta':{'filename':name+'.kicad_pro','version':1},'board':{'design_settings':{'rules':{'min_clearance':.15,'min_copper_edge_clearance':.2,'min_hole_clearance':.2,'min_through_hole_diameter':.3,'min_track_width':.15,'min_via_annular_width':.15,'min_via_diameter':.6}}},'net_settings':{'classes':[{'name':'Default','clearance':.15,'track_width':.25,'via_diameter':.6,'via_drill':.3,'microvia_diameter':.3,'microvia_drill':.1,'diff_pair_width':.2,'diff_pair_gap':.25,'diff_pair_via_gap':.25}],'meta':{'version':3}}}
    (bd/(name+'.kicad_pro')).write_text(json.dumps(pro,indent=2)+'\n')

def add_track(board,net,nets,pts,width=.25,layer='F.Cu'):
    for a,b in zip(pts,pts[1:]):
        if a==b:continue
        z=p.PCB_TRACK(board); z.SetStart(xy(*a));z.SetEnd(xy(*b));z.SetWidth(mm(width));z.SetLayer(p.F_Cu if layer=='F.Cu' else p.B_Cu);z.SetNet(nets[net]);board.Add(z)
def via(board,net,nets,point):
    z=p.PCB_VIA(board);z.SetPosition(xy(*point));z.SetWidth(mm(.6));z.SetDrill(mm(.3));z.SetViaType(p.VIATYPE_THROUGH);z.SetLayerPair(p.F_Cu,p.B_Cu);z.SetNet(nets[net]);board.Add(z)

def route_leaf(board,nets,pads):
    def t(net,pts,w=.25,l='F.Cu'):add_track(board,net,nets,pts,w,l)
    t('VLED',[(.55,4.3),(.55,21.7),(1.65,22.8),(1.65,25.6),(.55,26.7),(.55,55.8),(1.65,56.9),(1.65,59.7),(.55,60.8),(.55,80.95)],.5);t('GND',[(8.45,3.2),(8.45,80.95)],.5)
    for i in range(1,5):
        pp=pads[f'D{i}']; cc=pads[f'C{i}']
        t('VLED',[(.55,pp['4'][1]),pp['4']],.35)
        t('GND',[pp['2'],(8.45,pp['2'][1])],.35)
        t('VLED',[(.55,cc['1'][1]),cc['1']],.3)
        t('GND',[cc['2'],(8.45,cc['2'][1])],.3)
        if i<4:
            net=f'DATA_{i}_{i+1}';src=pp['1'];dst=pads[f'D{i+1}']['3'];v1=(6.3,src[1]);v2=(dst[0],dst[1]-.9)
            t(net,[src,v1]);via(board,net,nets,v1)
            t(net,[v1,(6.8,v1[1]),(6.8,v2[1]),v2],.25,'B.Cu');via(board,net,nets,v2);t(net,[v2,dst])
    jp=pads['J1'];t('GND',[jp['1'],(jp['1'][0],12.4),(8.45,12.4)],.35)
    t('VLED',[jp['2'],(jp['2'][0],16),(.55,16)],.35)
    v1=(jp['3'][0],13.2);v2=(pads['D1']['3'][0],pads['D1']['3'][1]-.9)
    t('DATA_IN',[jp['3'],v1]);via(board,'DATA_IN',nets,v1)
    t('DATA_IN',[v1,(2.2,13.2),(2.2,v2[1]),v2],.25,'B.Cu');via(board,'DATA_IN',nets,v2);t('DATA_IN',[v2,pads['D1']['3']])
    # J2 swaps the two independent streams. It does not serialize the two leaves.
    jp2=pads['J2']
    t('GND',[jp2['1'],(jp2['1'][0],61.9),(8.45,61.9)],.35)
    t('VLED',[jp2['2'],(jp2['2'][0],65.5),(.55,65.5)],.35)
    vo1=(7.6,15.9);vo2=(7.6,62.6)
    t('DATA_OTHER',[jp['4'],(jp['4'][0],15.9),vo1]);via(board,'DATA_OTHER',nets,vo1)
    t('DATA_OTHER',[vo1,vo2],.25,'B.Cu');via(board,'DATA_OTHER',nets,vo2)
    t('DATA_OTHER',[vo2,(jp2['3'][0],62.6),jp2['3']])
    vi2=(jp2['4'][0],65.4)
    t('DATA_IN',[(2.2,13.2),(2.2,65.4),vi2],.25,'B.Cu');via(board,'DATA_IN',nets,vi2);t('DATA_IN',[vi2,jp2['4']])

def route_adapter(board,nets,pads):
    def t(net,pts,w=.6,l='F.Cu'):add_track(board,net,nets,pts,w,l)
    a,b=pads['J1'],pads['J2']
    t('-12V_RAW',[a['1'],a['2']]);t('-12V_RAW',[a['2'],(7.4,a['2'][1]),(7.4,26.7),(b['1'][0],26.7),b['1']],.5,'B.Cu')
    t('+12V_RAW',[a['9'],a['10'],(b['3'][0],a['10'][1]),b['3']])
    for i in [3,5,7]:t('GND',[a[str(i)],a[str(i+1)]],.5,'B.Cu')
    t('GND',[a['3'],a['5'],a['7']],.5,'B.Cu')
    t('GND',[a['4'],a['6'],a['8']],.5,'B.Cu')
    t('GND',[a['3'],(1.4,a['3'][1]),(1.4,26.3)],.5,'B.Cu')
    via(board,'GND',nets,(1.4,26.3))
    t('GND',[(1.4,26.3),(b['2'][0],26.3),b['2']],.5,'F.Cu')

def board_file(b):
    board=p.BOARD();ds=board.GetDesignSettings();ds.SetBoardThickness(mm(b['thickness']));board.SetCopperLayerCount(b['layers']);ds.m_MinClearance=mm(.15);ds.m_CopperEdgeClearance=mm(.2);ds.m_HoleClearance=mm(.2)
    nets={}
    for name in sorted({n for c in b['components'] for n in c['nets'].values() if n}):
        nn=p.NETINFO_ITEM(board,name,len(nets)+1);board.Add(nn);nets[name]=nn
    outline=[(0,0),(b['width'],0),(b['width'],b['height']),(0,b['height'])]
    if b.get('front_edge_notches_mm'):
        for x1,y1,x2,y2 in reversed(b['front_edge_notches_mm']):outline += [(x1,y2),(x2,y2),(x2,y1),(x1,y1)]
    for a,z in zip(outline,outline[1:]+outline[:1]):
        edge=p.PCB_SHAPE();edge.SetShape(p.SHAPE_T_SEGMENT);edge.SetStart(xy(*a));edge.SetEnd(xy(*z));edge.SetWidth(mm(.05));edge.SetLayer(p.Edge_Cuts);board.Add(edge)
    pads={};placements=[]
    for c in b['components']:
        fp=PLUGIN.FootprintLoad(str(FPDIR),c['footprint']);fp.SetReference(c['ref']);fp.SetValue(c['value']);fp.SetFPID(p.LIB_ID('LightBlock',c['footprint']))
        fp.SetUuid(p.KIID(uid(b['name']+'/'+c['ref'])))
        path=p.KIID_PATH();path.push_back(p.KIID(uid(b['name']+'/sheet')));path.push_back(p.KIID(uid(b['name']+'/'+c['ref'])));fp.SetPath(path)
        board.Add(fp)
        if c['side']=='B':fp.Flip(xy(0,0),True)
        fp.SetOrientationDegrees(c['angle']);fp.SetPosition(xy(*c['at']))
        for field in(fp.Reference(),fp.Value()):field.SetVisible(False)
        cp={}
        for z in fp.Pads():
            n=z.GetNumber();net=c['nets'].get(n)
            if net:z.SetNet(nets[net])
            if n:cp[n]=vmm(z.GetPosition())
        pads[c['ref']]=cp
        pm=dict(c);pm['pad_centers_mm']=cp;pm.update(FP_META[c['footprint']]);pm['native_orientation_deg']=fp.GetOrientationDegrees()
        bb=fp.GetBoundingBox(False,False);pm['native_bbox_mm']=[vmm(bb.GetOrigin()),[round(p.ToMM(bb.GetWidth()),6),round(p.ToMM(bb.GetHeight()),6)]]
        if b['world_origin']:pm['world_origin_mm']=[round(c['at'][0]+b['world_origin'][0],6),round(c['at'][1]+b['world_origin'][1],6),b['world_origin'][2] if c['side']=='F' else round(b['world_origin'][2]+b['thickness'],6)]
        placements.append(pm)
    for i,(x,y) in enumerate(b['holes'],1):
        fp=p.FOOTPRINT(board);fp.SetReference('H'+str(i));fp.SetValue('M2 NPTH');fp.SetAttributes(p.FP_EXCLUDE_FROM_BOM|p.FP_EXCLUDE_FROM_POS_FILES);pad(fp,'',0,0,2.2,2.2,2.2,True);board.Add(fp);fp.SetPosition(xy(x,y));fp.Reference().SetVisible(False);fp.Value().SetVisible(False)
        # The retaining screw head is behind the controller. Front is only the
        # clearance hole; do not invent a front head colliding with the jacks.
        drawrect(fp,2.6 if b['name']=='controller' else 4.2,2.6 if b['name']=='controller' else 4.2,p.F_CrtYd,x,y)
        drawrect(fp,4.2,4.2,p.B_CrtYd,x,y)
    if b['name']=='led_leaf':route_leaf(board,nets,pads)
    elif b['name']=='power_adapter':route_adapter(board,nets,pads)
    board.BuildConnectivity()
    out=NATIVE/b['name']/(b['name']+'.kicad_pcb');p.SaveBoard(str(out),board)
    return placements

def main():
    generate_footprints();boards=all_boards();manifest={'revision':'A5','generator':'design/generate_electronics.py','kicad_version':p.GetBuildVersion(),'status':'Engineering draft; no hardware tested; controller not routed','boards':[]}
    ledger=defaultdict(lambda:{'quantity_per_module':0,'instances':[]})
    for b in boards:
        make_schematic(b);pl=board_file(b);entry={k:v for k,v in b.items() if k!='components'};entry['components']=pl;manifest['boards'].append(entry)
        for c in b['components']:
            if c['fitted']:
                row=ledger[c['c_code']];row.update(mpn=c['mpn']);row['quantity_per_module']+=b['quantity_per_module'];row['instances'].append({'board':b['name'],'ref':c['ref'],'board_copies':b['quantity_per_module']})
    (ROOT/'placement_and_connectivity.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    from enrich_placement_metadata import enrich
    enrich()
    result={'revision':'A5','fitted_pieces_per_module':sum(x['quantity_per_module'] for x in ledger.values()),'mpn_types':len(ledger),'components':[dict(c_code=k,**v) for k,v in sorted(ledger.items())]}
    (ROOT/'fitted_component_ledger.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    (ROOT/'footprints'/'footprint_geometry.json').write_text(json.dumps(FP_META,indent=2)+'\n')
    print(json.dumps({'native_boards':len(boards),'pieces':result['fitted_pieces_per_module'],'types':result['mpn_types'],'kicad':p.GetBuildVersion()}))

if __name__=='__main__':main()
