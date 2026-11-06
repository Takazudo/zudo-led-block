#!/usr/bin/env python3
"""Add native pad details/body bounds without modifying any KiCad board file."""
import json,math
from pathlib import Path
import pcbnew as p
ROOT=Path(__file__).resolve().parents[1]
def vec(v):return [round(p.ToMM(v.x),6),round(p.ToMM(v.y),6)]
def bbox(item):
    b=item.GetBoundingBox();o=b.GetOrigin()
    return [round(p.ToMM(o.x),6),round(p.ToMM(o.y),6),round(p.ToMM(o.x+b.GetWidth()),6),round(p.ToMM(o.y+b.GetHeight()),6)]
def enrich():
    path=ROOT/'placement_and_connectivity.json';m=json.loads(path.read_text())
    m['coordinate_note']='Controller/adapter world coordinates refer to the2HP datum. The centered3HP variant shifts X by+2.55mm. Leaf localX maps to world+Z; left localY maps to+Y, right localY to-Y. See mechanical geometry for normal-axis placement and mated plugs.'
    for b in m['boards']:
        board=p.LoadBoard(str(ROOT/'native'/b['name']/(b['name']+'.kicad_pcb')))
        fps={f.GetReference():f for f in board.GetFootprints()}
        for c in b['components']:
            fp=fps[c['ref']];details=[]
            for z in fp.Pads():
                details.append({'number':z.GetNumber(),'net':z.GetNetname(),'center_mm':vec(z.GetPosition()),'size_mm':vec(z.GetSize()),'drill_size_mm':vec(z.GetDrillSize()),'orientation_deg':z.GetOrientationDegrees(),'copper_bbox_mm':bbox(z),'attribute':str(z.GetAttribute())})
            c['all_pad_details']=details
            w,h=c['body_size_mm'];cx,cy=c['body_center_mm'];angle=math.radians(c['angle'])
            if c['side']=='B':cy=-cy
            dcx=cx*math.cos(angle)+cy*math.sin(angle);dcy=-cx*math.sin(angle)+cy*math.cos(angle)
            hx=abs(math.cos(angle))*w/2+abs(math.sin(angle))*h/2;hy=abs(math.sin(angle))*w/2+abs(math.cos(angle))*h/2
            x,y=c['at'];c['body_bounds_local_mm']=[x+dcx-hx,y+dcy-hy,x+dcx+hx,y+dcy+hy]
            cyboxes=[bbox(z) for z in fp.GraphicalItems() if z.GetLayer()==(p.F_CrtYd if c['side']=='F' else p.B_CrtYd)]
            if cyboxes:c['courtyard_bounds_local_mm']=[min(v[0] for v in cyboxes),min(v[1] for v in cyboxes),max(v[2] for v in cyboxes),max(v[3] for v in cyboxes)]
            c['body_envelope_scope']='Unmated board component envelope. Mated plugs, terminal tails, wire bends and control-specific barrel/lever solids are defined in mechanical design; do not replace them with this bounding box.'
    path.write_text(json.dumps(m,indent=2,ensure_ascii=False)+'\n')
if __name__=='__main__':enrich()
