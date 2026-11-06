"""Generate the A4 front/PCBA design brief from the captured procurement data."""
from pathlib import Path
import json
import html
from decimal import Decimal
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT=Path(__file__).resolve().parent
OUT=ROOT.parent/'outputs'/'light_block_A4'
OUT.mkdir(parents=True,exist_ok=True)
D=json.loads((ROOT/'procurement_rows.json').read_text())
pdfmetrics.registerFont(TTFont('JP','/root/.local/share/fonts/NotoSansJP-Regular.ttf'))
pdfmetrics.registerFont(TTFont('JPB','/root/.local/share/fonts/NotoSansJP-SemiBold.ttf'))
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
def price(r,n):return next(t['unit_price_usd'] for t in reversed(r['tiers']) if n*r['qty_per_module']>=t['min_qty'])

story=[]
story += [p('LIGHT BLOCK / A4','title'),p('文字を透明に残す全面フロストと、JLCで組むための部品選定','subtitle')]
story += [p('2HPを主案、3HPを予備案。前面は2 mmの透明PMMA、側面は交換できるPETG拡散板。完成した統合試作機で光と温度を確認する方針を維持します。')]
im=Image(str(ROOT/'front_panel/exports/A4_full_frost_clear_letters_summary.png'),width=523,height=523*1970/2715)
story += [im,Spacer(1,9),p('今回の変更','h2')]
story += [p('前面の見える裏面を、文字線以外すべてフロスト彫刻。RGB LEDは左右4個ずつ。主BOMは29型番・76点/台で、全型番にJLC在庫があります。10台想定の実装部品代は約$9.81/台です。')]
story += [p('状態：前面加工データ・調達設計の改版です。A4全体の干渉確認、KiCad実配線、製造BOM/CPL、FWは未完了です。図は透明/フロストの位置説明であり、実物の透過率や点灯均一性の予測画像ではありません。','small')]

story += [PageBreak(),p('01 / IC・LED・I/Oの選定','h1')]
story += [p('2026-11-06 JSTの公開JLCページ観測。100台は必要数量を比べるための仮定で、発注数ではありません。下表の単価は10台分の実装数に当てた公開価格帯、USDです。')]
selected=D['components'][:16]
rows=[]
for r in selected:
 rows.append([r['role_ja']+'\n'+r['mpn']+' / '+r['c_code'],str(r['qty_per_module']),f"{r['stock']:,}",f"{r['prepurchase_qty']:,}",f"${price(r,10):.4f}"])
story += [table(['用途 / メーカー型番 / JLC番号','数/台','JLC在庫','先買い欄','単価'],rows,[275,35,72,72,69])]
story += [Spacer(1,8),p('JLC在庫＝In Stock。先買い欄＝パーツライブラリのAvailable Order Qty。両者は別の表示で、後者をPCBA注文全体の絶対上限とは扱いません。観測日時・全価格帯・元ページURL・ハッシュは部品表/JSONに記録しました。','small')]
story += [p('最少の在庫余裕はインダクタC2651179：438個（100台に100個使用）。部品の余剰要求や最低購入数は含めていません。LED C52917434はStandard Onlyで、筐体や基板材を変えてもEconomicの部品にはなりません。[S4]','small')]

story += [PageBreak(),p('02 / 抵抗・コンデンサと部品代','h1')]
story += [p('受動部品13型番はすべてJLC Basicで選定しました。Standard PCBAではBasicにもフィーダー費があるため、型番統一による実装工程の簡素化も狙います。[S5]')]
rows=[]
for r in D['components'][16:]:
 rows.append([r['role_ja']+'\n'+r['mpn']+' / '+r['c_code'],str(r['qty_per_module']),f"{r['stock']:,}",f"${price(r,10):.4f}"])
story += [table(['値・用途 / 型番 / JLC番号','数/台','JLC在庫','単価'],rows,[335,35,84,69])]
story += [p('公称値の変更','h2'),p('82 kΩは1%へ変更。抵抗だけの最悪組合せで±5 V入力の換算誤差は最大約0.233 Vとなる計算です。照明用としてFWのゼロ/ゲイン補正を使います。LDO入出力は1 µFから4.7 µFへ増量し、実効容量の確認を残します。')]
costrows=[]
for n in (1,10,100):
 c=D['cost_checks'][str(n)];costrows.append([f'{n}台',f"${c['fitted_component_cost_per_module_usd']:.4f}",f"${c['LED_external_cables_per_module_usd']:.2f}",f"${c['power_external_cable_per_module_usd']:.4f}"])
story += [table(['仮の台数','実装部品代 / 台','LEDケーブル2本 / 台','電源ケーブル1本 / 台'],costrows,[78,145,150,150])]
story += [Spacer(1,8),p('部品代は実装点数に価格帯を適用した算術です。余剰・最低購入数・複数基板への注文分割・PCB製造・実装・治具・X線・書込み・他のケーブル・外装・送料・税を含みません。完成品価格ではありません。','small')]

story += [PageBreak(),p('03 / 全面フロストの作り方','h1')]
story += [p('透明材を使い、裏面の「文字ではない領域」を浅くラスター彫刻します。キャストPMMAは白く見える彫刻に向き、裏彫りなら正面を平滑に保てます。文字線は元の透明面として残ります。[S1,S2]')]
story += [table(['項目','A4指定'],[
 ['材質と厚み','透明キャストPMMA、2 mm。Elecrow Transparent (000)を希望し材種を確認。'],
 ['フロスト領域','正面から見える裏面全体。O等の内側もフロスト。外周に広い透明縁を作らない。'],
 ['透明部分','文字線・モード記号。締結部品の下に隠れる最小限の座面。'],
 ['加工面','裏面のみ。正面は透明・光沢の原面を維持。'],
 ['切断と彫刻','CUTファイルとREAR_FULL_FROST_CLEAR_LETTERSファイルを分離。mm単位。'],
 ['ミラー','裏彫刻データは既に鏡像化。再ミラーや白黒反転をしない。'],
 ['2HP / 3HP','9.8 / 14.9 mm幅、128.5 mm高、厚み2 mm。'],
 ['選定部品の開口','トグルØ6.50、ジャックØ6.20。加工公差と組立位置の最終確認が必要。'],
 ],[125,398])]
story += [p('見え方と発注上の扱い','h2'),p('これは白い面に透明な窓を抜いた見え方です。点灯時は散乱の差で文字が見え、消灯時の読みやすさは背後の色に依存します。元から曇ったP422材では透明な文字線を取り戻せないため、今回は使いません。')]
story += [p('Elecrowの公開オンライン見積りは切断用で、彫刻は個別問い合わせ対象です。全面裏彫りの均一さ、細い文字線、材種、完成穴径は工場確認が必要です。加工の見積りや注文はまだ送っていません。[S1]')]
story += [p('作成済みデータの確認','h2'),p('両幅の切断SVG/DXF、裏彫刻SVG/DXF、2 mm STEP、正面/裏面プレビューを作成。文字と穴の除外、6つの彫刻領域、STEP往復、平面DXFとmm単位を検査しました。実物の曇り度・彫刻深さ・透過率を測ったものではありません。')]

story += [PageBreak(),p('04 / JLC優先の実装と機構','h1')]
story += [p('LEDは同じ片面基板を2枚','h2'),p('0.6 mm FR-4の片面にLED4個＋局所コンデンサ4個＋SH4ヘッダ1個。2枚を背中合わせにし、左右DATAを独立させます。透明PET FPCの専用実装条件を第一試作の必須条件から外す提案です。JLCのFPC実装自体は公開サービスにあります。[S3]')]
story += [table(['予約寸法 / 2HP横断面','値'],[
 ['FR-4板2枚＋接着層','0.6 + 0.6 + 0.1 = 1.3 mm'],
 ['両側のLED/コンデンサ予約','1.1 × 2 = 2.2 mm'],
 ['中心の実装積層の幅','3.5 mm'],
 ['PETG内面間 / 片側の公称隙間','6.4 mm / (6.4 − 3.5) / 2 = 1.45 mm'],
 ['対向SH4ヘッダの幅','約7.1 mm。上記6.4 mmに収まらず、局所逃げ/位置変更が必要。'],
 ],[290,233])]
story += [p('新ジャックとトグルの受けを作り直す','h2'),p('PJ-3582-Bは滑らかなねじ無しバレルです。前面にナットで締める構造ではなく、PETG支持体で本体の前後を保持し、挿抜荷重を基板のはんだだけに掛けない構造にします。幅6.1 mmをHP方向へ向けます。')]
story += [p('Dailywellトグルの標準ナットは7.92 mm対辺/9.19 mm対角。2HPで使用する案ですが、Ø10.80座金やØ11.99リングは使えません。後部で回り止めし、長いPC端子は工場でトリムする仕様が必要です。銀接点の微小電流動作は統合試作で確認します。')]
story += [p('30 mm条件の残り','h2'),p('制御PCB前面Z12.3/裏面Z13.9、Würthインダクタの接合込み端Z16.0を仮定し、LED板Z17〜27へ移す配置を提案しています。これは計算上の候補で、完成CADの合格値ではありません。相手コネクタ・線の曲げ・受動電源変換PCBを含めた奥行き確認が必要です。')]
story += [p('ケーブルは完成品を差し込む','h2'),p('LED用Adafruit4399を2本/台、電源用Molex151340300を1本/台。DigiKeyの直接観測で各12,957本と17,783本の在庫を確認。100台分を上回ります。Molexの1→3/2→2/3→1は受動変換PCBで補います。両者はJLCの部品納品とは別購入です。[S7,S8,S13,S14]')]

story += [PageBreak(),p('05 / 試作までの実装方針','h1')]
story += [p('実装費を部品代と分ける','h2'),p('LEDはStandard Onlyです。現行公式表のStandard段取り＋ステンシルは片面$33.77、両面$67.54。異種面付けは追加設計数あたり片面$25.56、両面$51.12、フィーダーはBasic/Extendedとも$1.53です。これ以外にも治具、工場手はんだ、検査等が必要です。[S5]')]
story += [p('制御＋受動変換PCBを1.6 mmパネルに、同じLED基板を0.6 mmパネルにまとめる案です。異種面付けが常に最安とは限らないため、分割した見積りと比較します。ジャック等のWave Soldering表記は工場側の手はんだ対象です。[S6]')]
story += [p('電源ラッチの変更','h2'),p('在庫のあるTPS2552DBVR-1に変更し、MMBT3904を追加。PA5→10k→ベース、ベース→100k→GND、エミッタ→GND、コレクタ→EN、EN→100k→常時5V。GPIO HighでLED有効、リセット時は無効にする構成です。末尾-1のラッチオフ型を維持します。[S9]')]
story += [p('今回完了した範囲','h2'),p('前面加工データ、29型番の在庫/PCBA種別/価格帯、部品数とコスト算術、メーカー図面を用いた置換条件、CV抵抗誤差の計算。別発注の光学テストPCBを先行させる計画は設けていません。')]
story += [p('製造データの完成に必要な作業','h2')]
story += [table(['対象','完了させる内容'],[
 ['機構','新ジャック受け、トグル座面、SH4逃げ、電源変換PCBと配線を含むA4全体CAD。'],
 ['回路','ネイティブKiCad回路図/実配線、クランプと電源OFF、逆接、実効容量、buckループ。'],
 ['製造','ERC/DRC、BOM/CPL、パネル/Gerber、書込みHEX/BIN、ピン回転と工場トリム指示。'],
 ['統合試作','完成状態で発注し、PETGの拡散、発熱、3モード、CV、THRU、挿抜、隣接Kumiko照射を確認。'],
 ],[95,428])]
story += [Spacer(1,8),p('2HPの主案を維持しながら、部品在庫を理由に機構を変更しています。A3の奥行き確認を、そのままA4の保証として扱わないことが重要です。発注・在庫予約・工場連絡は行っていません。','small')]

story += [PageBreak(),p('06 / 資料と出典','h1')]
story += [p('付属ファイル','h2'),p('light_block_A4_parts.xlsx：29型番と外部部品。台数を変更すると公開価格帯で再計算。<br/>front_panel/：SVG・DXF・STEP・生成コード・形状JSON・検証結果。<br/>procurement_rows.json：個別時刻、全価格帯、JLC在庫/先買い欄、出典。<br/>research_jlc_electronics / io_service_audit：選定と不採用理由。<br/>evidence/：配布用の事実抽出記録。元HTML全体は同梱しません。')]
story += [p('harness_supply_followup：完成ケーブルの数値在庫を追加確認した資料。先行I/O調査にあった在庫未確認の記載より、この追加調査と統合部品表を優先します。','small')]
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
 ('S10','Diodes / AP63205 datasheet','https://www.diodes.com/datasheet/download/AP63200-AP63201-AP63203-AP63205.pdf'),
 ('S11','JLC / XKB PJ-3582-B','https://jlcpcb.com/partdetail/XKBConnection-PJ_3582B/C500090'),
 ('S12','JLC / Dailywell toggle','https://jlcpcb.com/partdetail/Dailywell-1MS3T1B1M2QES5/C908270'),
 ('S13','DigiKey / Adafruit4399','https://www.digikey.com/en/products/detail/adafruit-industries-llc/4399/10824268'),
 ('S14','DigiKey / Molex0151340300','https://www.digikey.com/en/products/detail/molex/0151340300/6198142'),
]
for label,title,url in sources:story += [p('['+label+'] '+link(title,url),'small')]
story += [p('出典の読み方','h2'),p('在庫はJLC国際公開ページのIn Stock欄に対応する公開データを匿名取得した記録です。LCSCの別倉庫在庫や検索キャッシュの数量と置き換えていません。個別観測は2026-11-06 05:15〜05:34 JST頃で、現在庫を予約したものではありません。')]
story += [p('計算・設計上の仮定','h2'),p('部品代は実装数量に公開価格帯を当てたものです。機構の隙間は公称寸法の差であり、公差・全体配置の検証とは別です。光学外観図は透明文字の配置説明です。回路/機構の未完了点は各本文に記載しています。')]

def footer(c,doc):
 c.setStrokeColor(LINE);c.line(36,35,A4[0]-36,35)
 c.setFont('JP',7.3);c.setFillColor(MUTED)
 c.drawString(36,23,'TAKAZUDO / LIGHT BLOCK A4  •  DESIGN & PROCUREMENT REVIEW')
 c.drawRightString(A4[0]-36,23,f'{doc.page}  /  2026-11-06 JST')

path=OUT/'light_block_A4_front_and_procurement.pdf'
doc=SimpleDocTemplate(str(path),pagesize=A4,rightMargin=36,leftMargin=36,topMargin=36,bottomMargin=47,
 title='Light Block A4 — front panel and JLC procurement',author='Takazudo / OpenAI',subject='Full frost negative lettering and stock-first PCBA component selection')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(path)
