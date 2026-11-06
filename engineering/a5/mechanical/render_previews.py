#!/usr/bin/env python3
"""Deterministic engineering previews from exported CAD triangles, not generated imagery."""
from pathlib import Path
import json, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import argparse

HERE=Path(__file__).resolve().parent
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
def font(n):return ImageFont.truetype(FONT,n)

def render(source,dest,title,subtitle):
    d=json.loads(source.read_text());parts=d['parts'];S=2;W,H=1400,1600
    im=Image.new('RGB',(W*S,H*S),'#f5f7fa');dr=ImageDraw.Draw(im,'RGBA')
    h=np.array([.80,0,.60]);v=np.array([.15,1,-.20]);v=v/np.linalg.norm(v)
    normal=-np.cross(h,v);normal/=np.linalg.norm(normal)
    arrays=[np.array(p['vertices']) for p in parts]
    allp=np.concatenate(arrays);pr=np.array([allp@h,allp@v]).T
    lo=pr.min(0);hi=pr.max(0);scale=min(1120/(hi[0]-lo[0]),1190/(hi[1]-lo[1]))
    offset=np.array([W/2,830])-(lo+hi)*scale/2
    polys=[];light=np.array([-.6,-.5,1]);light/=np.linalg.norm(light)
    for p,xyz in zip(parts,arrays):
        xy=(np.array([xyz@h,xyz@v]).T*scale+offset)*S
        col=np.array(p['color'][:3])*255;alpha=p['color'][3]
        # Opaque CAD-envelope previews; acrylic remains translucent and cable scenario is visibly purple.
        for t in p['triangles']:
            a,b,c=xyz[t];n=np.cross(b-a,c-a);mag=np.linalg.norm(n)
            if mag<1e-10:continue
            n/=mag;shade=.70+.30*abs(n@light)
            fill=tuple(np.clip(col*shade,0,255).astype(int))+(int(alpha*255),)
            polys.append((float(((a+b+c)/3)@normal),[tuple(z) for z in xy[t]],fill))
    polys.sort(key=lambda r:r[0])
    for _,poly,fill in polys:dr.polygon(poly,fill=fill)
    dr.rectangle((0,0,W*S,172*S),fill='#152b40')
    dr.text((64*S,35*S),title,font=font(38*S),fill='white')
    dr.text((64*S,96*S),subtitle,font=font(21*S),fill='#c7d6e4')
    dr.rounded_rectangle((45*S,1430*S,1355*S,1552*S),radius=12*S,fill='#ffffff',outline='#c6d2dd',width=1*S)
    notes=['CAD integration study | 30 mm target is conditional on cables and assembly tolerances.',
           'Purple: IDC ribbon R3 scenario. Ivory: dimensioned mated connector exteriors.',
           'Controller routing, finished cable/label storage, PETG slice and physical fit remain open.']
    for i,t in enumerate(notes):dr.text((66*S,(1450+31*i)*S),t,font=font(18*S),fill='#243c52')
    im.resize((W,H),Image.Resampling.LANCZOS).save(dest)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--variant',choices=['2hp','3hp','all'],default='all');args=ap.parse_args()
    for variant in (['2hp','3hp'] if args.variant=='all' else [args.variant]):
        folder=HERE/'exports'/variant
        for state in ['assembled','exploded']:
            p=folder/f'light_block_A5_{variant}_{state}.json'
            if p.exists():
                render(p,folder/f'light_block_A5_{variant}_{state}.png',
                       f'LIGHT BLOCK A5 | {variant.upper()} {state.upper()}',
                       'Editable CAD solids with declared manufacturer envelopes | not a production release')
                print(folder/f'light_block_A5_{variant}_{state}.png')

if __name__=='__main__':main()
