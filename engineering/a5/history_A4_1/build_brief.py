"""Generate the A4.1 brief from procurement_rows.json; retain A4 front geometry.

Run: python build_brief.py
Writes deliverables/light_block_<revision>_front_and_procurement.pdf beside this
script; punctuation in the revision becomes underscores (A4.1 -> A4_1).
Set LIGHT_BLOCK_OUTPUT_DIR to override the output directory (relative paths are
resolved from the invocation's working directory). Use LIGHT_BLOCK_FONT_DIR
for portable NotoSansJP TTF discovery if necessary.
"""
from pathlib import Path
import json
import html
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from decimal import Decimal
from PIL import Image as PILImage
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT=Path(__file__).resolve().parent
D=json.loads((ROOT/'procurement_rows.json').read_text())
REV=D['revision']
REV_FILENAME=re.sub(r'[^A-Za-z0-9]+','_',str(REV)).strip('_')
if not REV_FILENAME:raise ValueError('Revision must contain a letter or digit for the report filename')
OUT=Path(os.environ.get('LIGHT_BLOCK_OUTPUT_DIR',ROOT/'deliverables')).expanduser().resolve()
OUT.mkdir(parents=True,exist_ok=True)
def find_font(names):
 roots=[ROOT/'assets/fonts',ROOT/'fonts',Path.home()/'.local/share/fonts',Path('/usr/share/fonts/truetype/noto'),Path('/usr/local/share/fonts'),Path('/Library/Fonts'),Path.home()/'Library/Fonts']
 if os.environ.get('LIGHT_BLOCK_FONT_DIR'):roots.insert(0,Path(os.environ['LIGHT_BLOCK_FONT_DIR']))
 for folder in roots:
  for name in names:
   if (folder/name).is_file():return str(folder/name)
 raise FileNotFoundError('Supply NotoSansJP-Regular.ttf and NotoSansJP-SemiBold.ttf using LIGHT_BLOCK_FONT_DIR or assets/fonts/.')
pdfmetrics.registerFont(TTFont('JP',find_font(['NotoSansJP-Regular.ttf'])))
pdfmetrics.registerFont(TTFont('JPB',find_font(['NotoSansJP-SemiBold.ttf','NotoSansJP-Bold.ttf','NotoSansJP-Regular.ttf'])))
pdfmetrics.registerFontFamily('JP',normal='JP',bold='JPB',italic='JP',boldItalic='JPB')
INK=colors.HexColor('#203d4d');TEAL=colors.HexColor('#1a777b');MUTED=colors.HexColor('#566c77')
PALE=colors.HexColor('#eef3f5');LINE=colors.HexColor('#ccd8de');GOLD=colors.HexColor('#8b6339')
styles={
 'title':ParagraphStyle('title',fontName='JPB',fontSize=23,leading=31,textColor=INK,spaceAfter=10,wordWrap='CJK'),
 'subtitle':ParagraphStyle('subtitle',fontName='JP',fontSize=11,leading=17,textColor=MUTED,spaceAfter=13,wordWrap='CJK'),
 'h1':ParagraphStyle('h1',fontName='JPB',fontSize=17,leading=24,textColor=INK,spaceAfter=12,wordWrap='CJK'),
 'h2':ParagraphStyle('h2',fontName='JPB',fontSize=11.5,leading=18,textColor=TEAL,spaceBefore=10,spaceAfter=6,wordWrap='CJK'),
 'p':ParagraphStyle('p',fontName='JP',fontSize=9.5,leading=15.4,textColor=INK,spaceAfter=8,wordWrap='CJK'),
 'small':ParagraphStyle('small',fontName='JP',fontSize=8,leading=12.3,textColor=MUTED,spaceAfter=6,wordWrap='CJK'),
 'cell':ParagraphStyle('cell',fontName='JP',fontSize=8.3,leading=11.4,textColor=INK,wordWrap='CJK'),
 'head':ParagraphStyle('head',fontName='JPB',fontSize=7.7,leading=10.8,textColor=colors.white,wordWrap='CJK'),
}
def p(text,style='p'):return Paragraph(text,styles[style])
def esc(x):return html.escape(str(x),quote=True)
def link(label,url):return '<link href="'+esc(url)+'" color="#1a777b">'+esc(label)+'</link>'
def table(headers,rows,widths):
 data=[[p(h,'head') for h in headers]]+[[p(esc(v).replace('\n','<br/>'),'cell') for v in row] for row in rows]
 t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
 t.setStyle(TableStyle([
  ('BACKGROUND',(0,0),(-1,0),INK),('VALIGN',(0,0),(-1,-1),'TOP'),
  ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
  ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
  ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,PALE]),
  ('LINEBELOW',(0,-1),(-1,-1),.6,LINE),
 ]));return t
def price(r,n):return Decimal(str(next(t['unit_price_usd'] for t in reversed(r['tiers']) if n*r['qty_per_module']>=t['min_qty'])))
def fitted_cost(n):
 calculated=sum((price(r,n)*r['qty_per_module'] for r in D['components']),Decimal('0'))
 stored=Decimal(str(D['cost_checks'][str(n)]['fitted_component_cost_per_module_usd']))
 if abs(calculated-stored)>Decimal('0.0000001'):raise ValueError(f'Cost mismatch at {n} modules')
 return calculated
main_parts=[r for r in D['components'] if r['category'] not in ['抵抗','コンデンサ']]
passives=[r for r in D['components'] if r['category'] in ['抵抗','コンデンサ']]
l1=next(r for r in D['components'] if r['c_code']=='C694586')
fallback_l1=next(r for r in D['alternative_components'] if r['c_code']=='C2651179')
ext={r['id']:r for r in D['external_items']}
led_cable,power_cable=ext['EXT-01'],ext['EXT-02']
qty_per_module=sum(r['qty_per_module'] for r in D['components'])
inventory_target=int(D['inventory_modules'])
if not all(r['stock']>=inventory_target*r['qty_per_module'] and r['prepurchase_qty']>=inventory_target*r['qty_per_module'] for r in D['components']):raise ValueError('Planning inventory coverage no longer holds')
jst=ZoneInfo('Asia/Tokyo')
times=[datetime.fromisoformat(r['observed_jst']).astimezone(jst) for r in D['components'] if r['c_code']!=l1['c_code']]
day=min(times).strftime('%Y-%m-%d')
window=min(times).strftime('%H:%M')+'-'+max(times).strftime('%H:%M')
l1_time=datetime.fromisoformat(l1['observed_jst']).astimezone(jst).strftime('%H:%M')
cable_time=datetime.fromisoformat(led_cable['observed_jst']).astimezone(jst).strftime('%H:%M')
observation_label=f'{day} {window} JST、L1再選定 {l1_time} JST'

story=[]
story += [p('LIGHT BLOCK / '+REV,'title'),p('文字を透明に残す全面フロストと、JLCで組むための部品選定','subtitle')]
story += [p('2HPを主案、3HPを予備案。前面は2 mmの透明PMMA、側面は交換できるPETG拡散板。完成した統合試作機で光と温度を確認する方針を維持します。')]
preview=ROOT/'front_panel/exports/A4_full_frost_clear_letters_summary.png'
with PILImage.open(preview) as pic:iw,ih=pic.size
im=Image(str(preview),width=523,height=523*ih/iw)
story += [im,Spacer(1,9),p('今回の更新','h2')]
story += [p(f'中断前のA4を復旧し、前面図面を独立検証。在庫・価格を再確認し、L1を生産中のTDK品へ変更しました。主案は{len(D["components"])}型番・{qty_per_module}点/台。10台比較の実装部品代は約${fitted_cost(10):.2f}/台です。')]
story += [p('状態：前面加工・調達設計の改版です。全体CAD、30 mmへの実装、KiCad実配線、製造BOM/CPL、FWは未完成です。図は透明/フロスト位置の説明で、点灯の均一性を予測したものではありません。','small')]

story += [PageBreak(),p('01 / IC・LED・I/Oの選定','h1')]
story += [p(f'{observation_label}の公開JLCページ観測。{inventory_target}台は在庫余裕を比べる仮定で、発注数ではありません。単価は10台分の実装数に当てた公開価格帯、USDです。')]
selected=main_parts
rows=[]
for r in selected:
 rows.append([r['role_ja']+'\n'+r['mpn']+' / '+r['c_code'],str(r['qty_per_module']),f"{r['stock']:,}",f"{r['prepurchase_qty']:,}",f"${price(r,10):.4f}"])
story += [table(['用途 / メーカー型番 / JLC番号','数/台','JLC在庫','先買い欄','単価'],rows,[275,35,72,72,69])]
story += [Spacer(1,8),p('JLC在庫＝In Stock、先買い欄＝Available Order Qty。いずれも在庫予約や最終PCBA引当の保証ではありません。余剰数・最低購入数を加える前の比較です。LED C52917434はStandard Onlyです。[S4]','small')]
story += [p(f'L1はTDK {l1["mpn"]}。4.7 µH・高さ最大2 mmを維持し、10台比較で約${price(fallback_l1,10)-price(l1,10):.2f}/台を削減。{l1["stock"]:,}個 / 先買い欄{l1["prepurchase_qty"]:,}個を確認。Würthは代替候補に保存。ランド、起動・短絡・高温時の検証は残ります。[S15]','small')]

story += [PageBreak(),p('02 / 抵抗・コンデンサと部品代','h1')]
story += [p(f'受動部品{len(passives)}型番はJLC Basicで選定。Standard PCBAではBasicにもフィーダー費があるため、型番統一で実装工程も整理します。[S5]')]
rows=[]
for r in passives:
 rows.append([r['role_ja']+'\n'+r['mpn']+' / '+r['c_code'],str(r['qty_per_module']),f"{r['stock']:,}",f"${price(r,10):.4f}"])
story += [table(['値・用途 / 型番 / JLC番号','数/台','JLC在庫','単価'],rows,[335,35,84,69])]
story += [p('公称値と計算の範囲','h2'),p('82 kΩは1%品。抵抗だけの最悪組合せで±5 V入力の換算誤差は最大約0.233 Vです。FWのゼロ/ゲイン補正を使う方針です。LDO入出力は4.7 µF。実効容量、ADCクランプ、電源OFF時の逆流は別途確認します。')]
costrows=[]
for n in (1,10,100):
 costrows.append([f'{n}台',f'${fitted_cost(n):.4f}',f'${price(led_cable,n)*led_cable["qty_per_module"]:.2f}',f'${price(power_cable,n)*power_cable["qty_per_module"]:.4f}'])
story += [table(['仮の台数','実装部品代 / 台','LEDケーブル2本 / 台','電源ケーブル1本 / 台'],costrows,[78,145,150,150])]
story += [Spacer(1,8),p('部品代は実装点数に価格帯を適用した算術です。余剰・最低購入数・複数基板への注文分割・PCB製造・実装・治具・X線・書込み・他のケーブル・外装・送料・税を含みません。完成品価格ではありません。','small')]

story += [PageBreak(),p('03 / 全面フロストの作り方','h1')]
story += [p('透明材の裏面を、文字線を残して浅く彫刻します。キャストPMMAは白く見える彫刻に向き、裏彫りで正面を平滑に保てます。文字線は元の透明面として残します。[S1,S2]')]
story += [table(['項目','A4から継続する指定'],[
 ['材質と厚み','透明キャストPMMA、2 mm。Elecrow Transparent (000)を希望し材種を確認。'],
 ['フロスト領域','正面から見える裏面全体。O・D・Pの内側もフロスト。広い透明縁は設けない。'],
 ['透明部分','文字線・モード記号。M2、トグル、ラック締結部の下に隠れる小さな座面。'],
 ['加工面','裏面のみ。正面は透明・光沢の原面を維持。'],
 ['切断と彫刻','CUTファイルとREAR_FULL_FROST_CLEAR_LETTERSファイルを分離。mm単位。'],
 ['ミラー','裏彫刻データは既に鏡像化。再ミラーや白黒反転をしない。'],
 ['2HP / 3HP','9.8 / 14.9 mm幅、128.5 mm高、厚み2 mm。'],
 ['選定部品の開口','トグルØ6.50、ジャックØ6.20。加工公差と組立位置の最終確認が必要。'],
 ],[125,398])]
story += [p('「全面」の範囲と見え方','h2'),p('見える面を全面フロストにする指定です。締結部の下に隠れる約47.66 mm²/枚は平滑な座面として残します。ジャックに広い透明リングは設けません。正面の手触りは滑らかで、読みやすさは背後の色や照明に依存します。P422等の既製マット材は使いません。')]
story += [p('復旧後の検証','h2'),p('前面関連29ファイルのハッシュ一致、両幅のSTEP寸法、SVG/DXFの鏡像登録、6つの彫刻領域と5つの文字内側を再確認。各幅3,434点の文字線内部で彫刻の混入はありません。A4の形状・加工データは変更せず継続します。')]
story += [p('Elecrowの彫刻は個別問い合わせ対象です。均一さ、細い透明線、材種、完成穴径を工場と確認します。0.02 mmの計算用押出しは彫刻深さではありません。見積依頼・注文は未実施です。[S1]','small')]

story += [PageBreak(),p('04 / JLC優先の実装と機構','h1')]
story += [p('LEDは同じ片面基板を2枚','h2'),p('0.6 mm FR-4にLED4個＋局所コンデンサ4個＋SH4ヘッダ1個を配置し、2枚を背中合わせにします。左右DATAは独立。透明PET FPCの専用実装条件を第一試作の必須条件から外す案です。[S3]')]
story += [table(['予約寸法 / 2HP横断面','値'],[
 ['FR-4板2枚＋接着層','0.6 + 0.6 + 0.1 = 1.3 mm'],
 ['両側のLED/コンデンサ予約','1.1 × 2 = 2.2 mm'],
 ['中心の実装積層の幅','3.5 mm'],
 ['PETG内面間 / 片側の公称隙間','6.4 mm / (6.4 - 3.5) / 2 = 1.45 mm'],
 ['対向SH4ヘッダの幅','約7.1 mm。上記6.4 mmに収まらず、局所逃げ/位置変更が必要。'],
 ],[290,233])]
story += [p('新ジャックとトグルの荷重を受ける','h2'),p('PJ-3582-Bはねじ無しバレル。PETG支持体で本体の前後を保持し、挿抜荷重をはんだだけに掛けない構造にします。幅6.1 mmをHP方向へ向けます。Dailywellのナットは7.92 mm対辺/9.19 mm対角。2HPに入らないØ10.80座金とØ11.99リングは使わず、後部で回り止めします。長い端子は工場トリムが必要です。')]
story += [p('30 mmへの収まりは未判定','h2'),p('TDK L1の最大外形は4.6 × 4.3 × 2.0 mm。高さは維持できますが、旧部品のランドをそのまま流用できるという意味ではありません。相手コネクタ、線の曲げ、受動電源変換PCB、新支持体まで含む全体CADで奥行きを閉じます。A3の29.5 mm確認はA4.1の合格値に流用しません。[S15]')]
story += [p('家庭ではんだ付けせず、完成ケーブルを差し込む','h2'),p(f'LED用Adafruit 4399を2本/台、電源用Molex 151340300を1本/台。{day} {cable_time} JSTのDigiKey表示は各{led_cable["stock"]:,}本、{power_cable["stock"]:,}本。{inventory_target}台分を上回ります。Molexの1→3 / 2→2 / 3→1は受動変換PCBで補います。JLCの部品供給とは別購入です。[S7,S8,S13,S14]')]

story += [PageBreak(),p('05 / 統合試作へ進む条件','h1')]
story += [p('実装費を部品代と分ける','h2'),p('LEDはStandard Onlyです。現行公式表のStandard段取り＋ステンシルは片面$33.77、両面$67.54。異種面付けは追加設計数あたり片面$25.56、両面$51.12、フィーダーはBasic/Extendedとも$1.53です。これ以外にも治具、工場手はんだ、検査等が必要です。[S5]')]
story += [p('制御＋受動変換PCBを1.6 mmパネルに、同じLED基板を0.6 mmパネルにまとめる案です。異種面付けが常に最安とは限らないため、分割した見積りと比較します。ジャック等のWave Soldering表記は工場側の手はんだ対象です。[S6]')]
story += [p('故障ラッチの復帰をFWで管理する','h2'),p('TPS2552DBVR-1のENはMMBT3904で反転し、GPIO HighでLED有効、MCUリセット時は無効にします。ただしENの切替で故障ラッチも解除されます。WDT/ソフトリセット後に無条件でLEDを再有効化せず、復帰条件と状態保持を設計し、自動再試行ループを防ぐ必要があります。この動作は未実装です。[S9]')]
story += [p('発注前に閉じる項目','h2')]
story += [table(['対象','完了させる内容'],[
 ['機構','新ジャック保持、トグル座面と回り止め、SH4逃げ、全ケーブルを含む30 mm奥行き。'],
 ['電源・CV','TDKランド、起動/高温/短絡時の飽和、MLCC実効容量、ADCクランプと電源OFF時の逆流。通常負荷計算だけで異常時を合格扱いにしない。'],
 ['回路・FW','ネイティブKiCad回路図/実配線、ERC/DRC、受動IN→THRU、3モード、輝度上限、故障復帰。'],
 ['製造','ERC/DRC、BOM/CPL、パネル/Gerber、書込みHEX/BIN、ピン回転と工場トリム指示。'],
 ['統合試作','完成状態で発注し、PETGの拡散、発熱、3モード、CV、THRU、挿抜、隣接Kumiko照射を確認。'],
 ],[95,428])]
story += [Spacer(1,8),p('復旧・調達監査・前面加工データまでは完了。モジュール全体は未リリースです。別発注の光学テストPCBは先行させません。発注・在庫予約・工場連絡は行っていません。','small')]

story += [PageBreak(),p('06 / 資料と出典','h1')]
story += [p('付属データ','h2'),p('部品表XLSX：主案29型番、外部部品、比較台数を変更する計算欄。<br/>front_panel/：A4から継続するSVG・DXF・STEP、生成コード、形状JSON。<br/>procurement_rows.json / evidence_refresh/：今回の在庫・価格・確認時刻。<br/>history_A4/：中断前の履歴。現在の採用品・価格は更新済み部品表を優先。<br/>復旧監査：前面の独立検証、回路監査、TDK選定条件と未完了項目。','small')]
sources=[
 ('S1','Elecrow / Acrylic Cutting','https://www.elecrow.com/acrylic-cutting.html'),
 ('S2','Trotec / Acrylic material handling','https://www.troteclaser.com/en-us/helpcenter/materials/material-usage-hints/material-handling-acrylic'),
 ('S3','JLC / PCBA capabilities','https://jlcpcb.com/capabilities/pcb-assembly-capabilities'),
 ('S4','JLC / C52917434 WS2812B-2020-V6','https://jlcpcb.com/partdetail/Worldsemi-LED/C52917434'),
 ('S5','JLC / PCBA price, updated 2026-10-22','https://jlcpcb.com/help/article/pcb-assembly-price'),
 ('S6','JLC / PCBA FAQs','https://jlcpcb.com/help/article/pcb-assembly-faqs'),
 ('S7','Adafruit / 4399 50 mm SH4 cable','https://www.adafruit.com/product/4399'),
 ('S8','Molex / 151340300 cable','https://www.molex.com/en-us/products/part-detail/151340300'),
 ('S9','TI / TPS2552/3 and latch-off variants','https://www.ti.com/lit/ds/symlink/tps2553.pdf'),
 ('S10','Diodes / AP63205 datasheet','https://www.diodes.com/assets/Datasheets/AP63200-AP63201-AP63203-AP63205.pdf'),
 ('S11','JLC / XKB PJ-3582-B','https://jlcpcb.com/partdetail/XKBConnection-PJ_3582B/C500090'),
 ('S12','JLC / Dailywell toggle','https://jlcpcb.com/partdetail/Dailywell-1MS3T1B1M2QES5/C908270'),
 ('S13','DigiKey / Adafruit 4399',led_cable['url']),
 ('S14','DigiKey / Molex 0151340300',power_cable['url']),
 ('S15','TDK / SPM4020T-4R7M-LR (Production)',l1['manufacturer_source']),
]
for label,title,url in sources:story += [p('['+label+'] '+link(title,url),'small')]
story += [p('確認時刻と読み方','h2'),p(f'JLC主要データ：{observation_label}。外部ケーブル：{cable_time} JST。在庫は国際公開ページの表示値で、LCSC別倉庫や検索キャッシュの数量へ置き換えていません。個別時刻をJSONに残し、旧A4の05時台の記録と区別しています。','small')]
story += [p('計算・設計上の前提','h2'),p('公開在庫は予約されていません。部品代は実装数量に価格帯を当てた算術で、製造費は別です。隙間は公称寸法の差であり、実機の公差・荷重・温度の合格値ではありません。TDKの飽和/温度上昇電流は代表値で、高温短絡余裕の保証に使っていません。','small')]

def footer(c,doc):
 c.setStrokeColor(LINE);c.line(36,35,A4[0]-36,35)
 c.setFont('JP',7.3);c.setFillColor(MUTED)
 c.drawString(36,23,'TAKAZUDO / LIGHT BLOCK '+REV+'  |  DESIGN & PROCUREMENT REVIEW')
 c.drawRightString(A4[0]-36,23,f'{doc.page}  /  {day} JST')

path=OUT/f'light_block_{REV_FILENAME}_front_and_procurement.pdf'
doc=SimpleDocTemplate(str(path),pagesize=A4,rightMargin=36,leftMargin=36,topMargin=36,bottomMargin=47,
 title='Light Block '+REV+' - front panel and JLC procurement',author='Takazudo / OpenAI',subject='Recovered artwork, refreshed inventory, TDK inductor and integrated-prototype gates')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(path)
