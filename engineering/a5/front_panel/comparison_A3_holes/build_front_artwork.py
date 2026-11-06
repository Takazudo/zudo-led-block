#!/usr/bin/env python3
"""A4 rear frosting: full visible field with transparent negative lettering.

This is an appearance/mask revision on A3 hardware geometry, not a mechanical
release.  Real 2D Boolean regions are represented by thin BReps for calculation;
the temporary 0.02 mm extrusion is NOT a specified laser engraving depth.
The physical STEP panel remains the unchanged, full 2.00 mm A3 solid.
"""
from __future__ import annotations

import hashlib
import html
import json
import math
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

import cadquery as cq
import ezdxf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.path import Path as MPath
from matplotlib.patches import Circle, PathPatch
from matplotlib.textpath import TextPath
import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / 'exports'
REF = HERE / 'reference_A3'
FONT = FontProperties(family='DejaVu Sans', weight='bold')
STATUS = 'Appearance/mask revision on A3 hole geometry; mechanical release pending stocked switch/jack selection.'


def box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1-x0, y1-y0, z1-z0, cq.Vector(x0, y0, z0))


def cyl(r, h, origin):
    return cq.Solid.makeCylinder(r, h, cq.Vector(*origin))


def slot(x, y, length, width, z0, z1):
    return cq.Workplane('XY', origin=(x, y, z0)).slot2D(length, width).extrude(z1-z0).val()


def panel_shape(p, v):
    w, t, c = v['width'], p['panel']['thickness'], p['controls']
    xc = w/2
    sh = cq.Workplane(obj=box(0, w, 0, p['panel']['height'], -t, 0)).edges('|Z').fillet(p['panel']['outer_corner_radius']).val()
    for x, y in v['mounts']:
        sh = sh.cut(slot(x, y, v['slot_length'], p['panel']['mount_slot_width'], -t-1, 1))
    for y in p['carrier']['front_screws_y'] + [p['pcb']['top_mount_y']]:
        sh = sh.cut(cyl(1.1, t+2, (xc, y, -t-1)))
    for y in c['jack_y']:
        sh = sh.cut(cyl(c['jack_hole']/2, t+2, (xc, y, -t-1)))
    r = c['switch_hole']/2
    hole = cyl(r, t+2, (xc, c['switch_y'], -t-1))
    hole = hole.intersect(box(xc-r, xc-r+c['switch_flat_span'], c['switch_y']-r-1, c['switch_y']+r+1, -t-2, 2))
    hole = cq.Workplane(obj=hole).edges('|Z').fillet(c['switch_corner_blend_radius']).val()
    return sh.cut(hole)


def signed_area(poly):
    return .5 * sum(a[0]*b[1]-b[0]*a[1] for a, b in zip(poly, poly[1:]+poly[:1]))


def clean_poly(poly):
    out = []
    for xy in poly:
        xy = [float(xy[0]), float(xy[1])]
        if not out or math.dist(xy, out[-1]) > 1e-9:
            out.append(xy)
    if len(out) > 2 and math.dist(out[0], out[-1]) < 1e-9:
        out.pop()
    return out


def contains(poly, pt):
    verts = np.array(poly + [poly[0]])
    codes = [MPath.MOVETO] + [MPath.LINETO]*(len(poly)-1) + [MPath.CLOSEPOLY]
    return MPath(verts, codes).contains_point(pt, radius=-1e-9)


def nested_regions(polys):
    """Closed outer loops with their direct holes, independent of source winding."""
    polys = [clean_poly(q) for q in polys]
    parents = []
    for i, q in enumerate(polys):
        enclosing = [j for j, other in enumerate(polys) if i != j and contains(other, q[0])]
        parents.append(min(enclosing, key=lambda j: abs(signed_area(polys[j]))) if enclosing else None)
    depths = []
    for i in range(len(polys)):
        d, j = 0, parents[i]
        while j is not None:
            d += 1
            j = parents[j]
        depths.append(d)
    return [[q] + [polys[j] for j in range(len(polys)) if parents[j] == i and depths[j] % 2]
            for i, q in enumerate(polys) if depths[i] % 2 == 0]


def wire(poly, z=0):
    return cq.Wire.makePolygon([cq.Vector(x, y, z) for x, y in clean_poly(poly)], close=True)


def extrude_region(region, d):
    return cq.Solid.extrudeLinear(wire(region[0]), [wire(q) for q in region[1:]], (0, 0, d))


def compound(shapes):
    return cq.Compound.makeCompound(shapes)


def thin_panel(panel, d):
    face = cq.Workplane(obj=panel).faces('>Z').val()
    return cq.Solid.extrudeLinear(face.outerWire(), face.innerWires(), (0, 0, d))


def glyph_polys(text, cx, cy, cap_height):
    # Flatten curves at a large source scale, then reduce to millimeters. This
    # prevents unit-size font flattening from visibly faceting enlarged O/C.
    raw = TextPath((0, 0), text, size=100, prop=FONT).to_polygons()
    allpts = np.vstack(raw)
    xmin, ymin = allpts.min(axis=0)
    xmax, ymax = allpts.max(axis=0)
    scale = cap_height/(ymax-ymin)
    return [clean_poly([[cx+(float(x)-(xmin+xmax)/2)*scale,
                         cy-(float(y)-(ymin+ymax)/2)*scale] for x, y in poly]) for poly in raw]


def label_regions(p, w):
    regions, counters, description = [], [], []
    for q in p['engraving']['labels']:
        regs = nested_regions(glyph_polys(q['text'], w/2+q['x_offset'], q['y'], q['cap_height']))
        regions += regs
        for reg in regs:
            counters += reg[1:]
        description.append({**q, 'center_x': w/2+q['x_offset'], 'stroke_regions': len(regs),
                            'counters': sum(len(r)-1 for r in regs)})
    x = w/2-2.7
    regions.append([[[x,112.25],[x+.6,113.4],[x-.6,113.4]]])
    regions.append([[[x+.3*math.cos(a),116+.3*math.sin(a)] for a in np.linspace(0,2*math.pi,65)[:-1]]])
    regions.append([[[x-.6,118.6],[x+.6,118.6],[x,119.75]]])
    return regions, counters, description


def seating_masks(p, v, d):
    xc, q = v['width']/2, p['engraving']
    shapes, description = [], []
    locations = [('m2', y) for y in p['carrier']['front_screws_y'] + [p['pcb']['top_mount_y']]]
    locations += [('toggle', p['controls']['switch_y'])] + [('jack', y) for y in p['controls']['jack_y']]
    for kind, y in locations:
        r = p['front_washers'][kind]['od']/2-q['fixed_seat_inset_from_washer_radius_mm']
        shapes.append(cyl(r, d, (xc, y, 0)))
        description.append({'kind': kind, 'center':[xc,y], 'shape':'circle', 'radius_mm':r,
                            'hidden_inside_nominal_washer_silhouette':True})
    travel = q['rack_nominal_center_travel_mm']
    r = p['front_washers']['rack']['od']/2-q['rack_seat_inset_from_washer_radius_mm']
    for x, y in v['mounts']:
        lens = cyl(r, d, (x-travel, y, 0)).intersect(cyl(r, d, (x+travel, y, 0)))
        shapes.append(lens)
        description.append({'kind':'rack', 'center':[x,y], 'shape':'intersection of endpoint washer circles',
                            'circle_radius_mm':r, 'circle_center_offset_mm':travel,
                            'hidden_across_nominal_slot_travel':True})
    return compound(shapes), description


def shape_regions(shape, deflection):
    """Export ALL top faces, including separate engraved letter-counter islands."""
    faces = sorted(cq.Workplane(obj=shape).faces('>Z').vals(), key=lambda f: f.Area(), reverse=True)
    result = []
    for f in faces:
        reg = []
        for ww in [f.outerWire()] + f.innerWires():
            pts, _ = ww.sample(deflection)
            reg.append(clean_poly([[v.x, v.y] for v in pts]))
        result.append(reg)
    return result


def map_regions(regions, w, h, rear=False, dxf=False):
    return [[[[w-x if rear else x, h-y if dxf else y] for x, y in poly] for poly in reg] for reg in regions]


def svg_path(region):
    return ' '.join('M '+' L '.join(f'{x:.6f},{y:.6f}' for x,y in q)+' Z' for q in region)


def write_engrave_svg(path, regions, w, h):
    desc = (STATUS+' Rear face up; keep TOP at TOP. Already mirrored X=W-X. Black filled regions are ENGRAVE. '
            'Transparent omissions are clear letter strokes, hidden seating exclusions, and through-holes. '
            'Counter islands in O/D/P remain black and must be engraved. Do not mirror or invert again. '
            'Full 1:1 mm artboard; no cropping, no etch depth, no laser parameters.')
    paths = '\n'.join(f'  <path id="engraved_region_{i:02d}" d="{svg_path(reg)}" fill="#000000" stroke="none" fill-rule="evenodd"/>'
                      for i,reg in enumerate(regions))
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" viewBox="0 0 {w} {h}">\n'
                    f'<title>{html.escape(path.stem)}</title>\n<desc>{html.escape(desc)}</desc>\n'
                    f'<g id="ENGRAVE_REAR_FULL_FROST">\n{paths}\n</g>\n</svg>\n')


def write_engrave_dxf(path, regions, w, h):
    doc = ezdxf.new('R2010')
    doc.units = 4
    doc.header['$MEASUREMENT'] = 1
    doc.layers.new('ENGRAVE_REAR_FULL_FROST', dxfattribs={'color':7})
    for reg in map_regions(regions,w,h,rear=True,dxf=True):
        hatch = doc.modelspace().add_hatch(color=7, dxfattribs={'layer':'ENGRAVE_REAR_FULL_FROST'})
        hatch.set_solid_fill(color=7)
        hatch.dxf.hatch_style = 0
        for i, poly in enumerate(reg):
            if (signed_area(poly)>0) != (i==0):
                poly = poly[::-1]
            hatch.paths.add_polyline_path(poly,is_closed=True,flags=1 if i==0 else 0)
    doc.set_modelspace_vport(height=h,center=(w/2,h/2))
    doc.saveas(path)


def patch(regions, face='none', edge='none', alpha=1, lw=.6):
    verts, codes = [], []
    for reg in regions:
        for i, poly in enumerate(reg):
            q = poly if (signed_area(poly)>0) == (i==0) else poly[::-1]
            verts += q + [q[0]]
            codes += [MPath.MOVETO] + [MPath.LINETO]*(len(q)-1) + [MPath.CLOSEPOLY]
    return PathPatch(MPath(np.array(verts),codes),facecolor=face,edgecolor=edge,alpha=alpha,linewidth=lw)


def backdrop(ax, material, w, h):
    yy, xx = np.mgrid[0:1:1200j,0:1:160j]
    img = np.empty((1200,160,3))
    img[:,:,0] = .26+.23*(np.sin(yy*10+xx*2)+1)/2
    img[:,:,1] = .39+.21*(np.cos(yy*9-xx*2)+1)/2
    img[:,:,2] = .55+.16*(np.sin(yy*8+xx*3)+1)/2
    stripes = ((xx*5+yy*25)%1 < .13)
    img[stripes] *= .81
    im=ax.imshow(img,extent=(0,w,h,0),origin='upper',interpolation='bilinear',zorder=0)
    clip=patch(material)
    clip.set_transform(ax.transData)
    im.set_clip_path(clip)
    ax.add_patch(patch(material,'#d7edf0',alpha=.10))


def hardware(ax,p,v):
    xc=v['width']/2
    loc=[('m2',y) for y in p['carrier']['front_screws_y']+[p['pcb']['top_mount_y']]]
    loc += [('jack',y) for y in p['controls']['jack_y']]+[('toggle',p['controls']['switch_y'])]
    loc += [('rack',y) for x,y in v['mounts']]
    for kind,y in loc:
        q=p['front_washers'][kind]
        ax.add_patch(Circle((xc,y),q['od']/2,facecolor='#c3cad0',edgecolor='#6e7c88',linewidth=.45))
        ax.add_patch(Circle((xc,y),q['id']/2,facecolor='#34434f',edgecolor='none'))
    ax.add_patch(Circle((xc,p['controls']['switch_y']),1.27,facecolor='#e5ebef',edgecolor='#647582',linewidth=.5))


def draw_panel(ax,p,name,material,frost,rear=False,show_hardware=True):
    v=p['variants'][name]; w=v['width']; h=p['panel']['height']
    mat=map_regions(material,w,h,rear=rear)
    fr=map_regions(frost,w,h,rear=rear)
    backdrop(ax,mat,w,h)
    ax.add_patch(patch(fr,'#f4f6f6',alpha=.94))
    ax.add_patch(patch(mat,'none','#40596a',1,.6))
    if show_hardware:
        hardware(ax,p,v)
    ax.set_xlim(-1.4,w+1.4);ax.set_ylim(h+1.5,-1.5);ax.set_aspect('equal');ax.axis('off')


def render_preview(p,name,material,frost,rear=False):
    fig,ax=plt.subplots(figsize=(3.5,11.8),dpi=220)
    fig.patch.set_facecolor('#edf1f3')
    draw_panel(ax,p,name,material,frost,rear,not rear)
    fig.suptitle(f'A4 / {name.upper()} / '+('REAR' if rear else 'FRONT'),fontsize=13,fontweight='bold',y=.985,color='#263f50')
    fig.text(.5,.952,'Already mirrored for engraving' if rear else 'Frosted field + transparent letters',ha='center',fontsize=8.3,color='#48616e')
    fig.text(.5,.021,'A3 holes shown; hardware selection pending\nProcess-area illustration, not a light-output simulation',ha='center',fontsize=7.4,color='#536a77')
    dest=OUT/f'appearance_A4_{"rear" if rear else "front"}_{name}'
    fig.savefig(dest.with_suffix('.png'),bbox_inches='tight',pad_inches=.13)
    fig.savefig(dest.with_suffix('.svg'),bbox_inches='tight',pad_inches=.13)
    plt.close(fig)


def area_of_regions(regions):
    return sum(abs(signed_area(r[0]))-sum(abs(signed_area(q)) for q in r[1:]) for r in regions)


def old_A3_frost(p,w,letter_regions):
    d=p['engraving']['mask_boolean_thickness_mm']
    sh=cq.Workplane(obj=box(1,w-1,8,58,0,d)).edges('|Z').fillet(1).val()
    for y in p['carrier']['front_screws_y']+[p['pcb']['top_mount_y']]:
        sh=sh.cut(cyl(3,d,(w/2,y,0)))
    return shape_regions(sh,.002)+letter_regions


def render_summary(p,models):
    fig=plt.figure(figsize=(13,9),dpi=220,facecolor='#edf1f3')
    gs=fig.add_gridspec(2,4,width_ratios=[.85,.85,1.1,3.2],height_ratios=[1.08,1],left=.045,right=.97,bottom=.155,top=.86,wspace=.20,hspace=.15)
    a3=fig.add_subplot(gs[:,0]);a4=fig.add_subplot(gs[:,1]);a43=fig.add_subplot(gs[:,2])
    m=models['2hp'];m3=models['3hp']
    draw_panel(a3,p,'2hp',m['material_regions'],old_A3_frost(p,9.8,m['label_regions']))
    draw_panel(a4,p,'2hp',m['material_regions'],m['engrave_regions'])
    draw_panel(a43,p,'3hp',m3['material_regions'],m3['engrave_regions'])
    for ax,title,sub in [(a3,'A3 / previous','Partial upper frost\nFrosted letter strokes'),(a4,'A4 / 2HP','Full visible frost\nClear letter strokes'),(a43,'A4 / 3HP','Same finish\nWider front')]:
        ax.set_title(title,fontsize=10.5,color='#263f50',fontweight='bold',pad=13)
        ax.text(.5,-.045,sub,transform=ax.transAxes,ha='center',va='top',fontsize=8.5,color='#48616e')
    zoom=fig.add_subplot(gs[0,3]);zoom.set_facecolor('#edf1f3')
    demo_regs=nested_regions(glyph_polys('AO',16,9,9))
    d=p['engraving']['mask_boolean_thickness_mm']
    demo_mat=box(0,32,0,18,0,d)
    demo_letters=compound([extrude_region(r,d) for r in demo_regs])
    demo_mask=demo_mat.cut(demo_letters)
    mat_regs=shape_regions(demo_mat,.001)
    demo_mask_regs=shape_regions(demo_mask,.001)
    backdrop(zoom,mat_regs,32,18)
    zoom.add_patch(patch(demo_mask_regs,'#f4f6f6',alpha=.94))
    zoom.add_patch(patch(mat_regs,'none','#8a9aa4',1,.5))
    zoom.set_xlim(-.5,32.5);zoom.set_ylim(18.5,-.5);zoom.set_aspect('equal');zoom.axis('off')
    zoom.set_title('Negative lettering: the letter strokes stay clear',loc='left',fontsize=11,fontweight='bold',color='#263f50',pad=12)
    zoom.annotate('Background is engraved / frosted',xy=(4,4.0),xytext=(1,1.4),fontsize=8.3,color='#344f60',arrowprops=dict(arrowstyle='-',lw=.8,color='#647c8a'))
    # A counter is a separate engraved island, never a transparent hole.
    counters=[q for r in demo_regs for q in r[1:]]
    center=np.mean(np.array(counters[-1]),axis=0)
    zoom.annotate('Counters are frosted too',xy=center,xytext=(16,20),ha='center',fontsize=8.8,color='#344f60',arrowprops=dict(arrowstyle='->',lw=.8,color='#647c8a'))
    notes=fig.add_subplot(gs[1,3]);notes.axis('off')
    notes.text(0,.97,'What the laser file means',fontsize=12,fontweight='bold',color='#263f50',va='top')
    rows=[('BLACK FILLED MASK','Engrave the rear surface to create frosting.'),
          ('OMITTED LETTER STROKES','Leave original clear acrylic. No ink or paint.'),
          ('NO WIDE CLEAR BORDER','Frosting reaches the visible panel perimeter.'),
          ('SMALL HIDDEN EXCLUSIONS','Current washer seating areas stay unengraved.'),
          ('REAR FILES ALREADY MIRRORED','Keep TOP at TOP. Do not mirror or invert again.')]
    y=.83
    for head,body in rows:
        notes.text(0,y,head,fontsize=8.7,fontweight='bold',color='#3c5968',va='top')
        notes.text(0,y-.057,body,fontsize=9,color='#536b78',va='top')
        y-=.16
    fig.text(.045,.952,'A4 / foggy plate, transparent negative letters',fontsize=21,fontweight='bold',color='#203c50')
    fig.text(.045,.912,'Clear 2 mm PMMA + rear surface frosting. The front surface stays smooth and glossy.',fontsize=11,color='#496574')
    fig.text(.045,.046,'APPEARANCE REVISION ON A3 HOLES  |  Mechanical release pending stock-first switch/jack selection.',fontsize=9,fontweight='bold',color='#745a3d')
    fig.text(.045,.020,'Colored background only demonstrates transparency; haze, illumination uniformity, laser settings and engraving depth are not specified.',fontsize=8.5,color='#627581')
    dest=OUT/'A4_full_frost_clear_letters_summary'
    fig.savefig(dest.with_suffix('.png'),bbox_inches='tight',pad_inches=.16)
    fig.savefig(dest.with_suffix('.svg'),bbox_inches='tight',pad_inches=.16)
    plt.close(fig)
    return {'demo_text':'AO','counter_islands':len(counters),'engraved_connected_regions':len(demo_mask_regs),
            'mask_valid':demo_mask.isValid(),'letter_intersection_volume_mm3':demo_mask.intersect(demo_letters).Volume()}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_cut_and_step(name):
    copied={}
    for ext in ['dxf','svg']:
        source=REF/f'front_A3_{name}_CUT.{ext}'
        target=OUT/f'front_A4_{name}_CUT.{ext}'
        shutil.copyfile(source,target)
        copied[ext]={'reference_sha256':sha(source),'output_sha256':sha(target),'byte_identical_to_A3':sha(source)==sha(target)}
    source=REF/f'front_A3_{name}_2mm.step';target=OUT/f'front_A4_{name}_2mm.step'
    shutil.copyfile(source,target)
    copied['step']={'reference_sha256':sha(source),'output_sha256':sha(target),'byte_identical_to_A3':sha(source)==sha(target)}
    return copied


def main():
    p=json.loads((HERE/'geometry.json').read_text())
    OUT.mkdir(exist_ok=True)
    models={};validation=[];manifest=[]
    for name,v in p['variants'].items():
        w,h=v['width'],p['panel']['height'];d=p['engraving']['mask_boolean_thickness_mm']
        panel=panel_shape(p,v);material=thin_panel(panel,d)
        label_regs,counter_polys,label_desc=label_regions(p,w)
        letters=compound([extrude_region(r,d) for r in label_regs])
        seats,seat_desc=seating_masks(p,v,d)
        mask=material.cut(letters).cut(seats).clean()
        defl=p['engraving']['curve_sampling_deflection_mm']
        material_regs=shape_regions(material,defl)
        mask_regs=shape_regions(mask,defl)
        copied=copy_cut_and_step(name)
        rear_svg=OUT/f'rear_A4_{name}_REAR_FULL_FROST_CLEAR_LETTERS.svg'
        rear_dxf=rear_svg.with_suffix('.dxf')
        write_engrave_svg(rear_svg,map_regions(mask_regs,w,h,rear=True),w,h)
        write_engrave_dxf(rear_dxf,mask_regs,w,h)
        render_preview(p,name,material_regs,mask_regs)
        render_preview(p,name,material_regs,mask_regs,True)
        reference=cq.importers.importStep(str(REF/f'front_A3_{name}_2mm.step')).val()
        outer=cq.Workplane(obj=box(0,w,0,h,0,d)).edges('|Z').fillet(p['panel']['outer_corner_radius']).val()
        voids=outer.cut(material)
        mirror=mask.mirror('YZ',(w/2,0,0))
        twice=mirror.mirror('YZ',(w/2,0,0))
        counter_checks=[]
        for i,q in enumerate(counter_polys):
            cs=extrude_region([q],d)
            counter_checks.append({'index':i,'area_mm2':cs.Volume()/d,'unengraved_area_mm2':cs.cut(mask).Volume()/d})
        clear_letters=material.intersect(letters)
        clear_seats=material.intersect(seats).cut(letters)
        ddoc=ezdxf.readfile(rear_dxf)
        hatches=list(ddoc.modelspace().query('HATCH'))
        dxf_regions=[]
        for ht in hatches:
            dxf_regions.append([[[float(x),float(y)] for x,y,*_ in pa.vertices] for pa in ht.paths])
        metrics={
          'variant':name,'width_mm':w,'height_mm':h,'panel_thickness_mm':panel.BoundingBox().zlen,
          'status':p['status'],'material_area_mm2':material.Volume()/d,'engraved_area_mm2':mask.Volume()/d,
          'clear_letter_and_icon_area_mm2':clear_letters.Volume()/d,'hidden_clear_seat_area_mm2':clear_seats.Volume()/d,
          'engraved_fraction_of_material':mask.Volume()/material.Volume(),
          'engraved_connected_regions':len(mask.Solids()),'label_counter_islands':len(counter_polys),
          'all_BReps_valid':all(s.isValid() for s in [panel,material,letters,seats,mask]),
          'through_profile_loops':len(material_regs[0]),
          'panel_difference_from_A3_mm3':panel.cut(reference).Volume()+reference.cut(panel).Volume(),
          'unchanged_cut_and_step_files':copied,
          'no_assigned_engraving_depth':True,'temporary_boolean_extrusion_mm':d,
          'mask_intersection_through_holes_mm2':mask.intersect(voids).Volume()/d,
          'mask_intersection_clear_letters_mm2':mask.intersect(letters).Volume()/d,
          'mask_intersection_clear_seats_mm2':mask.intersect(seats).Volume()/d,
          'partition_residual_mm2':abs(material.Volume()-mask.Volume()-clear_letters.Volume()-clear_seats.Volume())/d,
          'mirror_area_delta_mm2':abs(mask.Volume()-mirror.Volume())/d,
          'double_mirror_difference_mm2':(mask.cut(twice).Volume()+twice.cut(mask).Volume())/d,
          'polygon_area_delta_mm2':abs(area_of_regions(mask_regs)-mask.Volume()/d),
          'dxf_hatch_area_delta_mm2':abs(area_of_regions(dxf_regions)-area_of_regions(mask_regs)),
          'dxf_units_code':ddoc.units,'dxf_hatch_count':len(hatches),
          'dxf_all_elevation_zero':all(abs(ht.dxf.elevation.z)<1e-12 for ht in hatches),
          'svg_contains_font_text':bool(ET.parse(rear_svg).findall('.//{http://www.w3.org/2000/svg}text')),
          'counter_checks':counter_checks,'labels':label_desc,'clear_seating_exclusions':seat_desc,
          'clear_perimeter_border_mm':0.0,'mirror_rule':'x_rear=W-x_front; TOP stays TOP; do not mirror or invert again'
        }
        metrics['passed']=all([
          metrics['all_BReps_valid'],metrics['through_profile_loops']==9,
          metrics['panel_difference_from_A3_mm3']<1e-7,
          metrics['mask_intersection_through_holes_mm2']<1e-8,
          metrics['mask_intersection_clear_letters_mm2']<1e-8,
          metrics['mask_intersection_clear_seats_mm2']<1e-8,
          metrics['partition_residual_mm2']<1e-7,
          metrics['double_mirror_difference_mm2']<1e-7,
          metrics['polygon_area_delta_mm2']<.15,
          metrics['dxf_hatch_area_delta_mm2']<1e-7,
          metrics['label_counter_islands']==5,
          metrics['engraved_connected_regions']==6,
          not metrics['svg_contains_font_text'],
          all(q['unengraved_area_mm2']<1e-8 for q in counter_checks),
          all(q['byte_identical_to_A3'] for q in copied.values())])
        validation.append(metrics)
        models[name]={'material_regions':material_regs,'engrave_regions':mask_regs,'label_regions':label_regs}
        (OUT/f'mask_regions_A4_{name}.json').write_text(json.dumps({'units':'mm','coordinates':'FRONT Xright Ydown',
          'mirror_for_rear':'x=W-x','engraved_regions':mask_regs,'clear_label_regions':label_regs,
          'status':p['status']},indent=2))
        manifest.append({'variant':name,'cut_dxf':f'front_A4_{name}_CUT.dxf','cut_svg':f'front_A4_{name}_CUT.svg',
          'full_thickness_step':f'front_A4_{name}_2mm.step','rear_engrave_svg':rear_svg.name,'rear_engrave_dxf':rear_dxf.name,
          'front_preview':f'appearance_A4_front_{name}.png','rear_preview':f'appearance_A4_rear_{name}.png'})
        print(json.dumps({'variant':name,'passed':metrics['passed'],'engraved_area_mm2':metrics['engraved_area_mm2'],
                          'mask_regions':metrics['engraved_connected_regions'],'counter_islands':metrics['label_counter_islands']}),flush=True)
    demo=render_summary(p,models)
    (OUT/'validation_A4.json').write_text(json.dumps({'revision':p['revision'],'status':p['status'],'units':'mm',
       'variants':validation,'AO_counter_demo':demo,'all_passed':all(x['passed'] for x in validation)},indent=2))
    (OUT/'manifest_A4.json').write_text(json.dumps({'revision':p['revision'],'status':p['status'],'units':'mm',
      'material_request':'Clear cast PMMA, nominal2mm; supplier confirms stock and process. Not pre-matteP422.',
      'operation':'Rear surface frosting; black filled mask is processed; letter strokes are unprocessed clear PMMA.',
      'mirror':'Already mirroredX=W-X, TOP remains TOP. Do not mirror or invert again.',
      'shared_registration':'SVG full panel artboard; DXF XrightYup topY128.5. Keep scale1:1mm and shared datum.',
      'cut_snapshot_note':'CUT/STEP are byte-identical A3 snapshots, including embedded A3 titles. This is deliberate; hole geometry is not released for procurement.',
      'no_order_placed':True,'whole_module_regenerated':False,'engraving_depth_assigned':False,
      'variants':manifest,'summary_preview':'A4_full_frost_clear_letters_summary.png'},indent=2))
    if not all(x['passed'] for x in validation):
        raise RuntimeError('A4 mask validation failed; inspect exports/validation_A4.json')


if __name__=='__main__':
    main()
