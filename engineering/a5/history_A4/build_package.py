"""Package the A4 design review without raw supplier pages or credentials."""
from pathlib import Path
import json,hashlib,zipfile,shutil

ROOT=Path(__file__).resolve().parent
OUT=ROOT.parent/'outputs'/'light_block_A4'
OUT.mkdir(parents=True,exist_ok=True)
data=json.loads((ROOT/'procurement_rows.json').read_text())
entries={}
def add_file(path,rel=None):
 p=Path(path);assert p.is_file(),p
 entries[rel or p.relative_to(ROOT).as_posix()]=p.read_bytes()
def add_json(rel,obj):entries[rel]=(json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode()

for name in ['README_JA.md','requirements.txt','build_brief.py','build_procurement_rows.py','build_package.py',
             'procurement_rows.json','research_jlc_electronics.json','research_jlc_electronics.md',
             'io_service_audit.json','io_service_audit.md','harness_supply_followup.json','harness_supply_followup.md',
             'check_cv_resistor_tolerance.py','cv_resistor_tolerance.json']:
 add_file(ROOT/name)
for dirname in ['front_panel','spreadsheet']:
 for p in sorted((ROOT/dirname).rglob('*')):
  if p.is_file() and '__pycache__' not in p.parts and p.suffix not in {'.pyc','.html'}:
   add_file(p)

# Preserve public factual fields in the same relative locations so the unified
# procurement builder can be rerun. Exclude whole HTML/JS and serialized UI text.
snapshot_paths=[]
for dirname in ['ic_led_evidence','mechanical_evidence','passive_evidence']:
 for p in sorted((ROOT/dirname).glob('*.snapshot.json')):
  x=json.loads(p.read_text())
  clean={k:v for k,v in x.items() if k not in {'public_payload_objects','visible_text'}}
  add_json(p.relative_to(ROOT).as_posix(),clean)
  snapshot_paths.append(p.relative_to(ROOT).as_posix())
for r in data['components']:
 assert r['snapshot'] in entries,r['snapshot']

validation={
 'project':'Light Block','revision':'A4','manufacturing_released':False,
 'front_panel_geometry':json.loads((ROOT/'front_panel/exports/validation_A4.json').read_text()),
 'procurement':data['summary'],'cost_checks':data['cost_checks'],
 'workbook':json.loads((ROOT/'spreadsheet_qa/verification.json').read_text()),
 'workbook_XML':json.loads((ROOT/'spreadsheet_qa/xlsx_xml_verification.json').read_text()),
 'PDF_visual_review':'7 pages rendered and inspected after final update; tables, Japanese text, image and source links reviewed.',
 'not_verified':['Complete A4 rear CAD and installed 30mm depth','Native schematic/routing and ERC/DRC',
   'Production BOM/CPL and factory placement acceptance','Input protection and supply sequencing',
   'Working firmware','Assembled hardware, thermal and optical behavior'],
}
add_json('verification_A4.json',validation)
add_json('evidence/observation_index.json',{
 'purpose':'Compact public observations; not inventory reservations or order quotes',
 'jlc_parts':[{'code':r['c_code'],'url':r['url'],'observed_jst':r['observed_jst'],
               'snapshot':r['snapshot'],'html_sha256':r['html_sha256']} for r in data['components']],
 'snapshots_in_archive':snapshot_paths,
 'external_cables_followup':'harness_supply_followup.json',
 'raw_webpage_files_omitted':True,
 'linked_manufacturer_datasheets':'Use the stable product/manufacturer URLs in the audit files; raw vendor PDFs are not duplicated in this package.'})
for name in ['light_block_A4_front_and_procurement.pdf','light_block_A4_parts.xlsx']:
 add_file(OUT/name,'deliverables/'+name)
preview=OUT/'light_block_A4_front_preview.png'
shutil.copyfile(ROOT/'front_panel/exports/A4_full_frost_clear_letters_summary.png',preview)
add_file(preview,'deliverables/'+preview.name)

add_json('package_manifest.json',{
 'revision':'A4','purpose':'Front panel and stock-first procurement design review',
 'not_a_manufacturing_release':True,
 'primary_front_files':'front_panel/exports/*A4*; comparison_A3_holes is historical only',
 'file_count_excluding_manifest':len(entries),
 'files':[{'path':rel,'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()}
          for rel,content in sorted(entries.items())]})
dest=OUT/'light_block_A4_design_package.zip'
with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for rel,content in sorted(entries.items()):z.writestr('light_block_A4/'+rel,content)
with zipfile.ZipFile(dest) as z:
 assert z.testzip() is None
 assert not any(n.endswith(('.html','.js')) for n in z.namelist())
 assert not any('public_payload_objects' in v.decode(errors='ignore') for k,v in entries.items() if k.endswith('.snapshot.json'))
print(json.dumps({'zip':str(dest),'bytes':dest.stat().st_size,'files':len(entries),
 'pdf_bytes':(OUT/'light_block_A4_front_and_procurement.pdf').stat().st_size,
 'xlsx_bytes':(OUT/'light_block_A4_parts.xlsx').stat().st_size,
 'preview':str(preview)},ensure_ascii=False,indent=2))
