"""Run native KiCad ERC, XML netlist export and schematic PDF export.

Uses the installed kicad-cli by default. An extracted portable KiCad may be
specified with --prefix; only this child process's library/data paths change.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--prefix',type=Path)
    args=ap.parse_args()
    env=dict(os.environ)
    if args.prefix:
        prefix=args.prefix.resolve()
        cli=str(prefix/'usr/bin/kicad-cli')
        env.update({'LD_LIBRARY_PATH':str(prefix/'usr/lib/x86_64-linux-gnu')+':'+str(prefix/'usr/lib/kicad'),
                    'KICAD_STOCK_DATA_HOME':str(prefix/'usr/share/kicad')})
    else:
        cli=shutil.which('kicad-cli')
        if not cli:raise SystemExit('Install KiCad10 or provide its extracted --prefix')
    version=subprocess.run([cli,'version'],env=env,text=True,capture_output=True,check=True).stdout.strip()
    def check(name):
        src=ROOT/'electronics/native'/name/(name+'.kicad_sch')
        out=ROOT/'integration/native_schematic'/name;out.mkdir(parents=True,exist_ok=True)
        sha=hashlib.sha256(src.read_bytes()).hexdigest();records=[]
        commands=[['sch','erc','--format','json','--severity-all','--exit-code-violations','-o',str(out/'erc.json'),str(src)],
                  ['sch','export','netlist','--format','kicadxml','-o',str(out/'netlist.xml'),str(src)],
                  ['sch','export','pdf','-o',str(out/(name+'.pdf')),str(src)]]
        for command in commands:
            run=subprocess.run([cli]+command,env=env,text=True,capture_output=True,timeout=60)
            records.append({'args':[s.replace(str(ROOT),'$PROJECT') for s in command],
                            'returncode':run.returncode,'stdout':run.stdout.replace(str(ROOT),'$PROJECT'),'stderr':run.stderr})
        erc=json.loads((out/'erc.json').read_text())
        violations=[v for sheet in erc.get('sheets',[]) for v in sheet.get('violations',[])]
        rec={'board':name,'schematic_sha256_before':sha,'schematic_sha256_after':hashlib.sha256(src.read_bytes()).hexdigest(),
             'kicad_version':version,'operations':records,
             'erc_errors':sum(v['severity']=='error' for v in violations),
             'erc_warnings':sum(v['severity']=='warning' for v in violations),
             'ignored_checks':erc.get('ignored_checks',[])}
        rec['all_passed']=all(r['returncode']==0 for r in records) and rec['schematic_sha256_before']==rec['schematic_sha256_after']
        (out/'native_run.json').write_text(json.dumps(rec,indent=2)+'\n')
        return {k:rec[k] for k in ('board','all_passed','erc_errors','erc_warnings','ignored_checks')}
    with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(check,['controller','led_leaf','power_adapter']))
    print(json.dumps(results,indent=2))
    if not all(x['all_passed'] for x in results):raise SystemExit(1)

if __name__=='__main__':main()
