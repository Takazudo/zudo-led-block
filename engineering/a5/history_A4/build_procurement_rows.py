"""Assemble the A4 engineering BOM from already captured JLC observations.

No network access. Quantities are fitted components, not purchasing quantities.
This is a design-selection BOM, not an assembler upload BOM/CPL.
"""
import json
from pathlib import Path
from decimal import Decimal

ROOT = Path(__file__).resolve().parent
core = json.loads((ROOT / 'research_jlc_electronics.json').read_text())
io = json.loads((ROOT / 'io_service_audit.json').read_text())
rows = []

ROLE_JA = {
 'C5270180': 'MCU / U1', 'C52917434': 'RGB LED / LED1〜8',
 'C2071056': '5 V降圧 / U2', 'C404027': '3.3 V LDO / U3',
 'C140331': 'LED電源ラッチ / U4', 'C20526': 'EN反転NPN / Q1',
 'C15741': 'LED用2chレベル変換 / U5', 'C221351': 'CVバッファ / U6',
 'C50704': '±12 V逆接保護用 / D1,D2', 'C134375': 'ADCクランプ候補 / D3',
 'C2651179': '降圧インダクタ4.7 µH / L1',
 'C500090': 'CV IN・THRUジャック / J1,J2',
 'C908270': 'ON–OFF–ONトグル / SW1',
 'C160404': 'LED用SH4ヘッダ / 制御2＋LED2',
 'C122442': '電源用3pinヘッダ / 制御1＋変換1',
 'C5665': 'Eurorack IDC10 / 変換基板1',
}
NOTE = {
 'C5270180': '4×4 mm UFQFPN28。SWDパッドで書込み。基板の実配線は未完。',
 'C52917434': '4個/片面LED基板×2枚。Standard Only・High difficulty・MSL5。通常FR-4に変更してもEconomicにはならない。',
 'C2071056': '5 V用4.7 µHを主案として維持。実効容量と電流ループを最終基板で確認。',
 'C404027': '入力/出力を4.7 µFへ統一する設計変更。出力1 µF以上の実効容量確認は未完。',
 'C140331': '旧TPS2553DBVR-1は21個/先買い0。active-low TPS2552-1へ変更し、Q1と10k/100kを追加。ラッチオフ型の-1を維持。',
 'C20526': 'PA5→10k→B、B→100k→GND、E→GND、C→EN、EN→100k→常時5V。GPIO HighでLED有効。',
 'C15741': 'VCCA=3V3、VCCB=VLED。左/右DATA各1ch、電源OFF時Ioffを使用。',
 'C221351': 'CVの20 MΩ検出枝をバッファ。THRUは受動直結。±12 V保護電源。',
 'C50704': '2個を逆向きに±電源へ配置する主案。安価なB5819Wは漏れと形状が変わるため未採用。逆接時の全回路審査は未完。',
 'C134375': '在庫とメーカー型番は確認。低温の負側クランプ、電源OFF時の注入電流は回路審査を要する。',
 'C2651179': '在庫が最も少ない主案部品。高さ2 mmを維持。安価なSunlord2.2 µHは高さ3 mm/リップル変更を伴う別案。',
 'C500090': '6.1 mmをHP方向に配置。無ねじバレルにつきPETG受けで挿抜荷重を支える。旧ジャックの置換だけでは不可。',
 'C908270': '中央PROGRAM。前面穴Ø6.50、標準ナット7.92 AF/9.19 AC。大径付属座金を使わず後部で回り止め。工場ピントリムと微小電流接点を要確認。',
 'C160404': '同一型番4個。1GND/2VLED/3DATA/4NC案、ケーブル相手側の番号と照合。下端に移動/局所PETG逃げが必要。',
 'C122442': '純正Molex151340300ケーブルの相手。1.6 mm PCBのテール突出/挿入深さを要確認。JLCのWave Soldering表記は工場手はんだ。',
 'C5665': '受動電源変換PCB上。コントローラとの異種面付けは追加料金あり。完成ハーネス配置は未検証。',
}

for x in core['selected_bom_inputs']:
 code=x['code']
 snap=json.loads((ROOT/x['snapshot']).read_text())
 p=snap['product']
 rows.append({
  'id':code,'category':'IC・LED・電源','role_ja':ROLE_JA[code],
  'mpn':x['mpn'],'manufacturer':x['manufacturer'],'c_code':code,
  'qty_per_module':x['qty_per_module'],'stock':x['jlc_in_stock'],
  'prepurchase_qty':x['prepurchase_available_order_qty'],
  'library':x['library'],'pcba_type':x['pcba_type'],'assembly_type':x['assembly_type'],
  'package':x['package_as_listed'],'tiers':x['price_tiers_usd'],
  'url':x['url'],'observed_jst':x['observed_jst'],
  'status_ja':'調達確認／回路・実装未リリース', 'notes_ja':NOTE[code],
  'snapshot':x['snapshot'],'html_sha256':x['html_sha256'],
  'attrition_hint':p.get('lossNumber'),'least_patch_hint':p.get('leastPatchNumber'),
  'prepurchase_min_hint':p.get('preMinPurchaseNum'),
 })
for x in io['selected_jlc_parts']:
 code=x['jlc_code'];p=x['part']
 rows.append({
  'id':code,'category':'I/O・コネクタ','role_ja':ROLE_JA[code],
  'mpn':p['componentModelEn'],'manufacturer':p['componentBrandEn'],'c_code':code,
  'qty_per_module':x['quantity_per_module'],'stock':x['in_stock'],
  'prepurchase_qty':x['available_order_qty'],
  'library':'Basic' if p['componentLibraryType']=='base' else 'Extended',
  'pcba_type':p['pcba_type_visible'],'assembly_type':p['assembly_type_visible'],
  'package':p['componentSpecificationEn'],'tiers':x['usd_tiers'],
  'url':x['source_url'],'observed_jst':x['observed_jst'],
  'status_ja':'調達確認／機構・実装未リリース','notes_ja':NOTE[code],
  'snapshot':'mechanical_evidence/'+code+'.snapshot.json','html_sha256':x['html_sha256'],
  'attrition_hint':p.get('lossNumber'),'least_patch_hint':p.get('leastPatchNumber'),
  'prepurchase_min_hint':p.get('preMinPurchaseNum'),
 })

passives = [
 ('C7250',2,'10 MΩ 1% / R1,R2','CV検出枝20 MΩ。定格電圧、基板汚れ・漏れに注意。'),
 ('C23254',4,'82 kΩ 1% / R3〜R6','A3の0.1%推奨からBasic1%へ変更。抵抗誤差だけで±5 V範囲の最大換算誤差は約0.233 V。照明用・FW校正あり。'),
 ('C21190',2,'1 kΩ 1% / R7,R8','ADC直列1個、3V3放電1個。後者は公称3.3 mA。'),
 ('C25804',5,'10 kΩ 1% / R9,R10,R13,R21,R22','MODE2、FAULT、NRST、NPNベース直列。A3から1個追加。'),
 ('C23231',1,'68 kΩ 1% / R11','68.1kからBasic68k。ILIM計算343.3〜439.4 mA、公称388.1 mA。筐体の許容発熱を表す値ではない。'),
 ('C25803',6,'100 kΩ 1% / R12,R16〜R19,R23','R12をNPNベースプルダウンに流用。R23をEN→常時5Vに追加。'),
 ('C23138',2,'330 Ω 1% / R14,R15','左右DATAの直列ダンピング。遠端の波形を試作機で確認。'),
 ('C23162',1,'4.7 kΩ 1% / R20','VLED放電。5 V時公称1.06 mA。'),
 ('C14663',15,'100 nF 50 V X7R / 制御7＋LED8','Basic YAGEOへ統一。BST–SW1、制御デカップリング5、NRST1、LED局所8。LED用最大0.9 mm本体。'),
 ('C57112',1,'10 nF 50 V X7R / C13','ADC入力フィルタ。最大ADC取得時間とサンプリング条件をFWで反映。'),
 ('C15850',3,'10 µF 25 V X5R / C1,C15,C16','0805。12 V入力と5 V局所用。DCバイアス下の実効容量の確認が必要。X5Rへ変更。'),
 ('C12891',2,'22 µF 25 V X5R / C2,C3','1206。AP63205評価基板と同じ公称容量/定格の選択。実効容量・温度・実配置は別途確認。'),
 ('C19666',3,'4.7 µF 16 V X5R / C5,C6,C7','0603。LDO入出力C5/C6を1 µFから増量しMCUバルクと統一。LDOの1 µF以上実効容量を要確認。'),
]
for code,qty,role,note in passives:
 path='passive_evidence/'+code+'.snapshot.json'
 x=json.loads((ROOT/path).read_text());p=x['product']
 rows.append({
  'id':code,'category':'抵抗' if role.startswith(('10 M','82 k','1 k','10 k','68 k','100 k','330','4.7 k')) else 'コンデンサ',
  'role_ja':role,'mpn':p['componentModelEn'],'manufacturer':p['componentBrandEn'],
  'c_code':code,'qty_per_module':qty,'stock':p['overseasStockCount'],
  'prepurchase_qty':p['canPresaleNumber'],
  'library':'Basic' if p['componentLibraryType']=='base' else 'Extended',
  'pcba_type':p['pcba_type_visible'],'assembly_type':p['assembly_type_visible'],
  'package':p['componentSpecificationEn'],'tiers':x['tiers'],
  'url':x['url'],'observed_jst':x['observed_jst'],
  'status_ja':'調達確認／回路・実装未リリース','notes_ja':note,
  'snapshot':path,'html_sha256':x['html_sha256'],
  'attrition_hint':p.get('lossNumber'),'least_patch_hint':p.get('leastPatchNumber'),
  'prepurchase_min_hint':p.get('preMinPurchaseNum'),
 })

external = [
 {'id':'EXT-01','category':'外部ケーブル','role_ja':'LED基板用4線ケーブル×2',
  'mpn':'Adafruit 4399 / Kaweei CBH-100-04-050-A','qty_per_module':2,
  'stock':None,'prepurchase_qty':None,'library':'外部購入','pcba_type':'JLC部品供給の対象外',
  'assembly_type':'完成ケーブル','tiers':io['external_cables'][0]['usd_tiers'],
  'url':io['external_cables'][0]['url'],
  'observed_jst':'2026-11-06T05:34:42.288987+09:00',
  'status_ja':'In Stock表示／数量不明',
  'notes_ja':'50±5 mm、SH4両端。図面1→1/2→2/3→3/4→4。100台分200本を出荷できる数量は未確認。'},
 {'id':'EXT-02','category':'外部ケーブル','role_ja':'電源3線ケーブル×1',
  'mpn':'Molex 151340300','qty_per_module':1,'stock':None,'prepurchase_qty':None,
  'library':'外部購入','pcba_type':'JLC部品供給の対象外','assembly_type':'完成ケーブル',
  'tiers':[],'url':'https://www.molex.com/en-us/products/part-detail/151340300',
  'observed_jst':None,'status_ja':'寸法図確認／販売価格・在庫未確認',
  'notes_ja':'50±6 mm、1 A/接点。A1→B3/A2→B2/A3→B1。アダプタ側銅配線で1/3反転を補償。'},
 {'id':'EXT-03','category':'外部ケーブル','role_ja':'Eurorack電源リボン×1',
  'mpn':'既製16→10 pin IDC、長さ未確定','qty_per_module':1,
  'stock':None,'prepurchase_qty':None,'library':'外部購入','pcba_type':'JLC部品供給の対象外',
  'assembly_type':'完成ケーブル','tiers':[],'url':None,'observed_jst':None,
  'status_ja':'未選定','notes_ja':'切断・家庭ではんだ付けしない。リモート変換基板と曲げを30 mmケース制約に含める。'},
 {'id':'EXT-04','category':'前面','role_ja':'透明キャストPMMA前面×1',
  'mpn':'Elecrow、2 mm、2HPまたは3HP、文字抜き全面裏彫刻','qty_per_module':1,
  'stock':None,'prepurchase_qty':None,'library':'外注加工','pcba_type':'JLC PCBA以外',
  'assembly_type':'切断＋裏面ラスター彫刻','tiers':[],
  'url':'https://www.elecrow.com/acrylic-cutting.html','observed_jst':None,
  'status_ja':'図面作成済／加工見積り未依頼',
  'notes_ja':'透明材000系を希望。透明文字を残すため既製マット材を選ばない。切断許容差と彫刻仕上げは工場確認。'},
 {'id':'EXT-05','category':'後部','role_ja':'PETG拡散板・支持体一式',
  'mpn':'自宅プリント用、後部設計改版中','qty_per_module':1,
  'stock':None,'prepurchase_qty':None,'library':'自宅造形','pcba_type':'JLC PCBA以外',
  'assembly_type':'印刷とネジ組立','tiers':[],'url':None,'observed_jst':None,
  'status_ja':'A4後部のSTL/3MF未完成',
  'notes_ja':'ジャック受け、スイッチ回り止め、ケーブル逃げが必要。A3支持体をそのまま使用できる確認はない。'},
 {'id':'EXT-06','category':'機構小物','role_ja':'締結部品・接着層一式',
  'mpn':'M2/M3等、完成機構で確定','qty_per_module':1,
  'stock':None,'prepurchase_qty':None,'library':'外部購入','pcba_type':'JLC PCBA以外',
  'assembly_type':'機械組立','tiers':[],'url':None,'observed_jst':None,
  'status_ja':'正確な長さ・数量未確定','notes_ja':'前面2 mmPMMA、LED背中合わせの0.1 mm接着層を想定。推奨締付トルクは未確定。'},
]

# The separate cable follow-up closes the original power-cable price/stock gap.
# Keep external distributor stock explicitly separate from all JLC stock rows.
harness_path=ROOT/'harness_supply_followup.json'
if harness_path.exists():
 harness=json.loads(harness_path.read_text())
 led_offer=harness['lighting_cable']['DigiKey_offer']
 external[0].update({
  'stock':led_offer['stock_direct_capture'],
  'tiers':[{'min_qty':1,'max_qty':None,'unit_price_usd':0.95}],
  'url':led_offer['url'],'observed_jst':'2026-11-06T05:47:54.201245+09:00',
  'library':'外部購入 / DigiKey',
  'status_ja':'DigiKey12,957本／100台分200本の数量を確認',
  'notes_ja':'DigiKey1528-4399-ND。50±5 mm、SH4両端、1:1結線。直販Adafruitは100+で$0.76と安いが数量非公開。主価格は数値在庫のあるDigiKey$0.95を使用。',
 })
 offer=harness['power_cable']['distributor_offers'][0]
 ts=offer['tiers']
 external[1].update({
  'stock':offer['stock'],
  'tiers':[{'min_qty':t['min_qty'],
            'max_qty':ts[i+1]['min_qty']-1 if i+1<len(ts) else None,
            'unit_price_usd':t['unit_price']} for i,t in enumerate(ts)],
  'url':offer['url'], 'observed_jst':'2026-11-06T05:45:47.712906+09:00',
  'library':'外部購入 / DigiKey',
  'status_ja':'DigiKey17,783個／100台分の数量を確認',
  'notes_ja':'DigiKey WM15252-ND、表記0151340300はMolex151340300と同一。50±6 mm、1 A/接点。A1→B3/A2→B2/A3→B1。JLC在庫ではなく外部購入。',
 })

def unit_price(row,qty):
 return next(t['unit_price_usd'] for t in reversed(row['tiers']) if qty>=t['min_qty'])

costs={}
for n in (1,10,100):
 cats={}
 for r in rows:
  qty=n*r['qty_per_module'];price=unit_price(r,qty)
  cats[r['category']]=cats.get(r['category'],Decimal(0))+Decimal(str(price))*r['qty_per_module']
 costs[str(n)]={'fitted_component_cost_per_module_usd':float(sum(cats.values())),
  'categories_per_module_usd':{k:float(v) for k,v in cats.items()},
  'LED_external_cables_per_module_usd':2*unit_price(external[0],n*2),
  'power_external_cable_per_module_usd':unit_price(external[1],n) if external[1]['tiers'] else None,
  'excludes':'Attrition, pre-purchase minimums, board-job splitting, PCBs, assembly, fixtures, X-ray, programming, other cables, mechanical parts, shipping and taxes.'}

data={
 'revision':'A4','document_type':'Engineering selection and availability audit; not a released manufacturing BOM',
 'as_of_jst':'JLC: 2026-11-06 05:15–05:33 JST / external cables:05:45–05:47 JST; individual timestamps retained',
 'prototype_modules':10,'inventory_modules':100,
 'quantity_assumptions':'10 and 100 are editable planning comparisons, not user-confirmed order quantities. Fitted quantities only; inventory is not reserved.',
 'stock_fields':'stock is JLC international public In Stock; prepurchase_qty is Available Order Qty in the pre-purchase library. Neither is a reservation or final order acceptance.',
 'cost_method':'Public price tier at the fitted quantity across modules. Real PCBA jobs may split quantities. No attrition, MOQ, assembly or external unpriced items included.',
 'standard_price_source':'https://jlcpcb.com/help/article/pcb-assembly-price',
 'standard_price_note':'Observed live article updated2026-10-22: Standard feeder$1.53 for Basic and Extended. Setup/stencil/multi-design/panel fixtures/manual solder/programming are extra. Current LED C52917434 is Standard Only.',
 'components':rows,'external_items':external,
 'cost_checks':costs,
 'summary':{'unique_jlc_mpn_count':len(rows),'fitted_parts_per_module':sum(r['qty_per_module'] for r in rows),
   'all_stock_cover_100_fitted_modules':all(r['stock']>=100*r['qty_per_module'] for r in rows),
   'all_prepurchase_cover_100_fitted_modules':all(r['prepurchase_qty']>=100*r['qty_per_module'] for r in rows),
   'least_stock_coverage_code':min(rows,key=lambda r:r['stock']/r['qty_per_module'])['c_code'],
   'all_quantities_before_attrition':True,
   'release_status':'Native KiCad schematic/routing, ERC/DRC, final BOM/CPL, complete A4 rear CAD, cable fit and working firmware remain unfinished.'}
}
(ROOT/'procurement_rows.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'summary':data['summary'],'cost_checks':costs},ensure_ascii=False,indent=2))
