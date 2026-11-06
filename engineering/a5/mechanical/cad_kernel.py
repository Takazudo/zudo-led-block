"""Small CadQuery utilities for the A5 mechanical integration study.

Units are millimetres. These functions operate on actual saved solids; no part
is silently omitted from collision checks. Internal contact inside a mated
connector is represented by one conservative exterior envelope.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import math
import cadquery as cq
import numpy as np
from OCP.gp import gp_Trsf
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib


@dataclass
class Part:
    name: str
    shape: cq.Shape
    color: tuple = (0.6, 0.7, 0.8, 1.0)
    kind: str = "design_geometry"
    note: str = ""
    source: str | None = None
    scope: str = "retained_module"
    printed: bool = False
    print_rotation: tuple | None = None
    group: str = "module"
    metadata: dict = field(default_factory=dict)


def box(x0, x1, y0, y1, z0, z1):
    assert x1 > x0 and y1 > y0 and z1 > z0, (x0, x1, y0, y1, z0, z1)
    return cq.Solid.makeBox(x1-x0, y1-y0, z1-z0, cq.Vector(x0, y0, z0))


def cylinder(radius, z0, z1, x=0, y=0):
    return cq.Solid.makeCylinder(radius, z1-z0, cq.Vector(x, y, z0))


def ring(ro, ri, z0, z1, x, y):
    return cylinder(ro, z0, z1, x, y).cut(cylinder(ri, z0-.01, z1+.01, x, y))


def hexagon(across_flats, z0, z1, x, y, hole=0, rotation=0):
    sh = cq.Workplane("XY").polygon(6, 2*across_flats/math.sqrt(3)).extrude(z1-z0).val()
    if rotation:
        sh = sh.rotate((0,0,0), (0,0,1), rotation)
    sh = sh.translate((x, y, z0))
    if hole:
        sh = sh.cut(cylinder(hole/2, z0-.01, z1+.01, x, y))
    return sh


def union(*shapes):
    shapes = [s for s in shapes if s is not None]
    if not shapes:
        raise ValueError("No shapes")
    out = shapes[0]
    for sh in shapes[1:]:
        out = out.fuse(sh)
    return out.clean()


def bounds(shape):
    raw=Bnd_Box();BRepBndLib.AddOptimal_s(shape.wrapped,raw,False,False)
    b=cq.BoundBox(raw)
    return {"min":[b.xmin,b.ymin,b.zmin], "max":[b.xmax,b.ymax,b.zmax],
            "size":[b.xlen,b.ylen,b.zlen]}


def transformed(shape, origin, u=(1,0,0), v=(0,1,0), n=(0,0,1)):
    # gp_Trsf.SetValues classifies the orthogonal transform; a raw gp_GTrsf
    # populated through Matrix.SetValue can retain the wrong form metadata.
    tr=gp_Trsf()
    tr.SetValues(u[0],v[0],n[0],origin[0],u[1],v[1],n[1],origin[1],u[2],v[2],n[2],origin[2])
    return shape.transformShape(cq.Matrix(tr))


def point_transform(p, origin, u, v, n):
    return tuple(origin[j]+p[0]*u[j]+p[1]*v[j]+p[2]*n[j] for j in range(3))


def smooth_wire(points, radius, tangents=None):
    pts = [cq.Vector(*p) for p in points]
    tangents = tuple(cq.Vector(*v) for v in tangents) if tangents else None
    edge = cq.Edge.makeSpline(pts, tangents=tangents)
    shape,stats=tube_from_path(edge,radius)
    stats['control_points']=points
    return shape,stats,edge


def tube_from_path(edge,radius):
    start = edge.positionAt(0)
    profile = cq.Wire.makeCircle(radius, start, edge.tangentAt(0))
    try:
        shape = cq.Solid.sweep(profile, [], edge, makeSolid=True, isFrenet=False)
    except Exception:
        shape = cq.Solid.sweep(profile, [], edge, makeSolid=True, isFrenet=True)
    sample = np.array([[p.x,p.y,p.z] for p in (edge.positionAt(i/500) for i in range(501))])
    radii=[]
    for a,b,c in zip(sample[:-2], sample[1:-1], sample[2:]):
        ab,bc,ac = np.linalg.norm(b-a),np.linalg.norm(c-b),np.linalg.norm(c-a)
        cross = np.linalg.norm(np.cross(b-a,c-a))
        if cross > 1e-9:
            radii.append(ab*bc*ac/(2*cross))
    return shape, {"centerline_length_mm":edge.Length(),
                   "sampled_minimum_centerline_radius_mm":min(radii) if radii else None,
                   "minimum_radius_is_manufacturer_qualified":False}


def mesh(part, tolerance=.07):
    verts, tris = part.shape.tessellate(tolerance, .13)
    return {"name":part.name,"kind":part.kind,"color":list(part.color),
            "note":part.note,"source":part.source,"scope":part.scope,
            "printed":part.printed,"group":part.group,"metadata":part.metadata,
            "bbox_mm":bounds(part.shape),
            "vertices":[[float(v.x),float(v.y),float(v.z)] for v in verts],
            "triangles":[list(t) for t in tris]}


def export_assembly(parts, destination, metadata, mesh_json=True):
    path=Path(destination)
    path.parent.mkdir(parents=True,exist_ok=True)
    assy=cq.Assembly(name=path.stem)
    for part in parts:
        assy.add(part.shape,name=part.name,color=cq.Color(*part.color))
    assy.export(str(path.with_suffix('.step')))
    if mesh_json:
        path.with_suffix('.json').write_text(json.dumps({"units":"mm","metadata":metadata,
            "parts":[mesh(p) for p in parts]},separators=(',',':')))
    original=cq.Compound.makeCompound([p.shape for p in parts])
    imported=cq.importers.importStep(str(path.with_suffix('.step'))).val()
    return {"valid":imported.isValid(),"source_solids":len(original.Solids()),
            "imported_solids":len(imported.Solids()),
            "volume_difference_mm3":abs(original.Volume()-imported.Volume()),
            "source_bbox_mm":bounds(original),"imported_bbox_mm":bounds(imported)}


def validate(parts, width, depth_limit=30, expected_contacts=()):
    expected={frozenset(pair) for pair in expected_contacts}
    rows=[]; overlaps=[]; permitted=[]; envelopes=[]
    for p in parts:
        bb=bounds(p.shape)
        rows.append({"part":p.name,"valid":p.shape.isValid(),"solids":len(p.shape.Solids()),
                     "volume_mm3":p.shape.Volume(),"bbox_mm":bb,"scope":p.scope})
        problems=[]
        if bb['min'][0]<-1e-4 or bb['max'][0]>width+1e-4:problems.append("width")
        if bb['max'][2]>depth_limit+1e-4:problems.append("rear_depth")
        if p.scope!='front_panel' and bb['max'][2]>0 and (bb['min'][1]<17.1-1e-4 or bb['max'][1]>111.4+1e-4):
            problems.append("rail_body_y")
        if problems:envelopes.append({"part":p.name,"scope":p.scope,"checks":problems,"bbox_mm":bb})
    bbs={p.name:p.shape.BoundingBox() for p in parts}
    for i,a in enumerate(parts):
        ba=bbs[a.name]
        for b in parts[i+1:]:
            bb=bbs[b.name]
            if any(v<=1e-5 for v in [min(ba.xmax,bb.xmax)-max(ba.xmin,bb.xmin),
                min(ba.ymax,bb.ymax)-max(ba.ymin,bb.ymin),min(ba.zmax,bb.zmax)-max(ba.zmin,bb.zmin)]):continue
            if hasattr(a,'cable_path') or hasattr(b,'cable_path'):
                ca=getattr(a,'cable_path',a.shape);cb=getattr(b,'cable_path',b.shape)
                threshold=(.4 if hasattr(a,'cable_path') else 0)+(.4 if hasattr(b,'cable_path') else 0)
                distance=ca.distance(cb)
                if distance<threshold-1e-4:
                    row={"a":a.name,"b":b.name,"centerline_minimum_distance_mm":distance,
                         "required_radius_sum_mm":threshold,"clearance_mm":distance-threshold,
                         "method":"exact CAD centerline-to-solid/centerline distance; round tube radius0.4",
                         "a_scope":a.scope,"b_scope":b.scope}
                    (permitted if frozenset((a.name,b.name)) in expected else overlaps).append(row)
                continue
            vol=a.shape.intersect(b.shape).Volume()
            if vol>1e-4:
                row={"a":a.name,"b":b.name,"volume_mm3":vol,"a_scope":a.scope,"b_scope":b.scope}
                (permitted if frozenset((a.name,b.name)) in expected else overlaps).append(row)
    return {"all_shapes_valid":all(r['valid'] for r in rows),"part_checks":rows,
            "unexpected_intersections":overlaps,"explicitly_expected_intersections":permitted,
            "envelope_failures":envelopes,"excluded_parts":[],
            "contact_tolerance_mm3":1e-4}


def export_print(part, path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    shape=part.shape
    if part.print_rotation:
        axis,angle=part.print_rotation
        shape=shape.rotate((0,0,0),axis,angle)
    b=shape.BoundingBox();shape=shape.translate((-b.xmin,-b.ymin,-b.zmin))
    cq.exporters.export(shape,str(path.with_suffix('.step')))
    cq.exporters.export(shape,str(path.with_suffix('.stl')),tolerance=.03,angularTolerance=.1)
    return {"name":part.name,"stl":path.name+'.stl',"step":path.name+'.step',
            "bbox_mm":bounds(shape),"valid":shape.isValid(),"solids":len(shape.Solids()),
            "volume_mm3":shape.Volume(),"rotation":part.print_rotation,
            "nominal_material":"PETG","slicing_status":"NOT_SLICED"}
