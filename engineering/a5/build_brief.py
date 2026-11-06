"""Generate the A5 engineering update from frozen procurement and integration results.

Run: python build_brief.py
Writes deliverables/light_block_<revision>_engineering_update.pdf beside this
script; punctuation in the revision becomes underscores.
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
from io import BytesIO
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

S=json.loads((ROOT/'integration/a5_status.json').read_text())
def figure(relative,max_width=523,max_height=235):
 path=ROOT/relative
 with PILImage.open(path) as pic:w,h=pic.size
 scale=min(max_width/w,max_height/h)
 return Image(str(path),width=w*scale,height=h*scale)

def cad_view(relative,max_height=242):
 # Lay out only the authored CAD drawing region; full labelled previews remain
 # in the package. The source renderer places geometry inside these bounds.
 with PILImage.open(ROOT/relative) as source:
  crop=source.crop((350,180,1050,1428))
  data=BytesIO();crop.save(data,format='PNG');data.seek(0)
  width,height=crop.size
 return Image(data,width=width*max_height/height,height=max_height)

story=[p('LIGHT BLOCK / '+REV,'title'),p('回路・機構・ファームウェアの実装と検証','subtitle')]
story += [p('A4.1の前面と調達設計から、編集可能なネイティブ設計、実行できるSTM32ファームウェア、背面機構へ進めた開発版です。2HP優先・3HP代替、全面フロストと透明文字、左右各4個のRGB LEDという方針を維持します。')]
story += [figure('front_panel/exports/A4_full_frost_clear_letters_summary.png',max_height=214),Spacer(1,8)]
story += [table(['分野','A5の到達点'],S['overview_rows'],[88,435])]
story += [Spacer(1,10),p('今回の重要な変更','h2')]
story += [p('CV検出の後段にU7と330 Ω / 1 kΩ分圧を追加し、FWの係数を合わせました。左右2つのLEDデータを1本の4線へまとめ、同一LED板の追加ヘッダから他側へ渡すことで、制御J4とスイッチ端子の干渉を解消する構成へ変更。A4.1から差引き1型番・5部品増え、30型番・81点/台です。')]
story += [p('製造リリースではありません。制御基板の配線状況、全ケーブルを含む外形、電源過渡・温度・光の実機確認を、後続ページと検証記録で区別します。フロスト図は加工領域の説明で、光の均一性を予測した画像ではありません。','small')]

story += [PageBreak(),p('01 / 実部品に合わせた背面機構','h1')]
story += [p('寸法の原点はアクリル板の裏面 z=0。前面板は z=-2〜0 mmです。コネクタは基板上のヘッダだけでなく、相手ハウジング、配線出口、端子、保持部の外形を含めます。')]
if S.get('mechanical_views'):
 views=S['mechanical_views']
 t=Table([[cad_view(v['path']) for v in views],
          [p(esc(v['caption']),'small') for v in views]],colWidths=[174,174,175])
 t.setStyle(TableStyle([('ALIGN',(0,0),(-1,0),'CENTER'),('VALIGN',(0,0),(-1,-1),'TOP'),
                       ('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3)]))
 story += [t,Spacer(1,4)]
elif S.get('mechanical_preview'):
 story += [figure(S['mechanical_preview'],max_height=242),Spacer(1,7)]
story += [table(['部品 / 条件','配置・寸法'],S['mechanical_rows'],[138,385])]
story += [p('IDCケーブルの横向き出口が残る制約','h2'),p(S['cable_fit_ja'])]
story += [p('ジャックとスイッチを樹脂で支える','h2'),p('PJ-3582-Bはねじ無しバレルです。前の保持カラーと後ろの支持体で、抜き差しの荷重を受けます。Dailywellスイッチには裏側の回り止めを設け、2HPに入らない大径座金は使いません。端子の工場トリムとPMMA締付荷重は組立条件として残します。')]
story += [p(S['print_settings_ja'],'small')]

story += [PageBreak(),p('02 / KiCad回路とCV保護','h1')]
story += [table(['ネイティブ設計','部品数 / 基板構成','実行した確認'],S['board_rows'],[125,156,242])]
story += [p('LED線は制御J3→左板J1、左板J2→右板J1。4線に左右の独立データを載せ、LED板内でピン3/4を入れ替えます。4画素ずつの独立制御を維持し、ケーブルは既製1:1を2本。最初の線が左右の電源電流を合計して受けます。','small')]
story += [p('THRUを受動直結したまま電圧を読む','h2'),p('INとOUTの信号・GNDは銅箔で直接接続します。検出用の別枝は10 MΩ + 10 MΩで、公称入力抵抗20 MΩ。OPA197が分圧点をバッファし、82 kΩの加算回路がCVを3.3 V系の中央へ移します。U7はその後段に追加したTLV9001IDBVRです。[S1,S2]')]
story += [table(['A5の変換','式 / 公称値'],[
 ['U7入力','Vnode = VDD / 2 + CV / 8'],
 ['U7出力からADC','R24=330 Ω、R25=1 kΩ。VADC = (100/133) × Vnode'],
 ['FWの逆変換','CV = 10.64 × VADC - 4 × VDD。VREFINTでVDDを推定。'],
 ['CV=-5 / 0 / +5 V、VDD=3.3 V','ADC電圧は約0.771 / 1.241 / 1.711 V。ゼロ/ゲイン補正係数あり。実測校正は未実施。'],
 ],[160,363])]
story += [p('保護の確認範囲','h2'),p(S['cv_protection_ja'])]
story += [p('電源・電流制限','h2'),p('AP63205で5 V、TLV75533で3.3 Vを生成。TDK SPM4020T-4R7M-LRは独自のランドを使用します。LED電源にはTPS2552DBVR-1のラッチ遮断とEN反転用NPNを置き、MCUリセット時は消灯。68 kΩのILIMは公称約388 mA、抵抗公差を含むデータシート式で約343〜439 mAです。FWの20%輝度上限とは別の保護です。[S3,S4,S5]')]
story += [p('高温でのインダクタ飽和、MLCC実効容量、起動、上流短絡、部分的な電源低下は、机上計算と実機での確認を分けます。LED側の電流制限だけでは上流回路を保護できません。','small')]

story += [PageBreak(),p('03 / STM32でビルドできるFW','h1')]
story += [p(S['firmware_build_ja'])]
story += [table(['スイッチ位置','現在の試作用動作'],[
 ['ON','左右のLEDを白色で点灯。各色チャンネルは51/255以下。'],
 ['PROGRAM','左右で位相を反転した8秒の呼吸アニメーション。色は暖色 / 寒色の仮設定。'],
 ['CV','±5 Vの絶対値で明るさを制御し、符号で暖色 / 寒色を切替。0 V付近50 mVは消灯。'],
 ],[95,428])]
story += [p('中央の物理OFF接点がPROGRAMです。電源OFFの位置ではありません。色、8秒周期、CV応答は変更できる試作用初期値で、最終的な光の演出として確定していません。','small')]
story += [p('検出した故障とリセット後の消灯方針','h2'),p('FAULT入力、ADC異常、古いADC値、DMA異常・タイムアウトで電源ENを下げ、データ線をLowへ戻します。バックアップ領域に起動・点灯・故障の状態を保持し、WDT、ソフトリセット、保持状態を伴うBOR後は暗いままにします。通常の完全な電源断後は選択モードへ自動で進むため、毎回の特別なスイッチ操作は不要です。[S6]')]
story += [p('バックアップ領域まで失う電源障害は、意図的な電源断と区別できず、復電後に再試行し得ます。また5 V正常状態の独立監視はありません。FAULT通知前にTPS2552の電源だけが低下・復帰する場合は、MCUリセットの保持方針では捕捉できません。任意の部分電源障害に対する再試行ゼロの保証ではありません。[S3]','small')]
story += [p('LED信号を現行データシートに合わせる','h2'),p('HSI/PLLを60 MHz、TIM3を78 tick/cellに設定し、0/1のHighを21/57 tickにします。公称1.300 µs/cell、High 350/950 ns。左右を同じタイマのDMAバーストで並列に出し、リセットLowを320 µs以上確保します。ソフトウェア上の±3%クロック境界確認を行い、実物の波形・電源・温度での確認は試作後に実施します。[S7]')]
story += [table(['実行済み','結果'],S['firmware_check_rows'],[170,353])]

story += [PageBreak(),p('04 / 調達と費用の更新','h1')]
story += [p('主案は30型番・81点。A4.1の29型番は11:30〜11:37 JSTの観測を引継ぎ、U7を14:37、IDC10を14:39 JSTに確認しました。全型番の在庫は比較用100台分の実装数を上回ります。100台は発注数量ではありません。各行の観測時刻とURLはXLSX / JSONに残しています。')]
key_codes=['C5270180','C52917434','C2071056','C140331','C398363','C694586','C500090','C908270','C160404','C122442','C5665']
rows=[]
for code in key_codes:
 r=next(x for x in D['components'] if x['c_code']==code)
 rows.append([r['mpn']+'\n'+r['c_code'],str(r['qty_per_module']),f'{r["stock"]:,}',f'{r["prepurchase_qty"]:,}',f'${price(r,10):.4f}'])
story += [table(['主要部品 / JLC番号','数/台','In Stock','Available\nOrder Qty','10台比較単価'],rows,[245,38,75,80,85])]
story += [p('A5の追加とLED配線の整理','h2'),p('U7 TLV9001IDBVR / C398363、330 Ω、1 kΩ、100 nFを各1個追加。制御J4を外し、各LED板にSH4のJ2を追加して、ヘッダは差引き1個増えます。合計の増分はA4.1比で1台$0.3084、10台$0.1034、100台$0.1389/台。10台ではSH4合計50個の価格帯を使う比較で、基板別発注の価格は別確認です。')]
story += [p('LED C52917434はStandard Only。JLCの実装区分は基板材をFR-4へ変更しても同じです。Wave Soldering表記の部品は工場での手はんだ対応を確認します。U7の先行購入最小数138はPCBAの実装点数とは異なる条件です。[S8,S9]','small')]

story += [PageBreak(),p('05 / 統合試作へ渡す条件','h1')]
costrows=[]
for n in (1,10,100):
 parts_cost=fitted_cost(n);led=price(led_cable,n)*2;power=price(power_cable,n)
 costrows.append([f'{n}台',f'${parts_cost:.4f}',f'${led:.4f}',f'${power:.4f}',f'${parts_cost+led+power:.4f}'])
story += [table(['比較台数','実装部品 / 台','LED線2本 / 台','電源線1本 / 台','ここまで / 台'],costrows,[75,112,112,112,112])]
story += [Spacer(1,7),p('実装点数に公開価格帯を適用した比較です。PCB、実装、段取り、余剰、最低購入数、書込み、IDCリボン、PMMA、PETG、金具、送料、税を含みません。基板別発注では価格帯も変わる場合があります。完成品価格ではありません。','small')]
story += [p('前面加工の指定はA4から継続','h2'),p('透明キャストPMMA 2 mm。見える裏面全体をフロスト彫刻し、文字線とモード記号を透明に残します。O / D / Pの内側もフロスト。正面は原面のまま平滑です。CUTと彫刻データは分離し、裏面彫刻データは既に鏡像化しているため再ミラーしません。小さな締結座面のみ、部品の下で透明に残します。[S10,S11]')]
story += [p('残る作業と、その完了条件','h2')]
story += [table(['対象','製造・試作前に閉じる内容'],S['remaining_rows'],[102,421])]
story += [p('光学専用PCBの先行発注は行いません。完成する回路・機構・FWをまとめた統合試作機で、Kumikoへの照射、PETGの拡散、温度、CV、THRU、スイッチ、挿抜荷重を確認します。','small')]

story += [PageBreak(),p('06 / 検証記録とソース','h1')]
story += [table(['確認','今回の結果と範囲'],S['check_rows'],[140,383])]
story += [p('編集元と再開位置','h2'),p('mechanical/：背面CAD生成コード、STEP、STL、3MF、外形・干渉記録。<br/>electronics/：ネイティブKiCad、部品/ネット対応、基板別の確認記録。<br/>firmware/：Cソース、固定したSDK、Makefile、ELF/HEX/BIN、テスト。<br/>procurement_rows.json / parts.xlsx：30型番の数量・価格・在庫。<br/>integration/：A5の照合結果。continue-here.md：次の担当者が再開する順序。<br/>history_A4_1/以前：過去の設計・価格。現在の値と混同しない。','small')]
story += [p('一次資料','h2')]
sources=[
 ('S1','TI TLV9001 / RRIO buffer','https://www.ti.com/lit/ds/symlink/tlv9001.pdf'),
 ('S2','TI OPA197 / input buffer','https://www.ti.com/lit/ds/symlink/opa197.pdf'),
 ('S3','TI TPS2552/3 / latch-off variants','https://www.ti.com/lit/ds/symlink/tps2553.pdf'),
 ('S4','Diodes AP63205 / buck regulator','https://www.diodes.com/assets/Datasheets/AP63200-AP63201-AP63203-AP63205.pdf'),
 ('S5','TDK SPM4020T-4R7M-LR','https://product.tdk.com/en/search/inductor/inductor/smd/info?part_no=SPM4020T-4R7M-LR'),
 ('S6','ST STM32G031 reference manual RM0444','https://www.st.com/resource/en/reference_manual/rm0444-stm32g0x1-advanced-armbased-32bit-mcus-stmicroelectronics.pdf'),
 ('S7','Worldsemi WS2812B-2020-V6 / exact PDF pinned in firmware evidence',S['led_datasheet_url']),
 ('S8','JLC WS2812B-2020-V6 / C52917434','https://jlcpcb.com/partdetail/C52917434'),
 ('S9','JLC PCBA FAQs','https://jlcpcb.com/help/article/pcb-assembly-faqs'),
 ('S10','Elecrow acrylic cutting','https://www.elecrow.com/acrylic-cutting.html'),
 ('S11','Trotec acrylic material handling','https://www.troteclaser.com/en-us/helpcenter/materials/material-usage-hints/material-handling-acrylic'),
 ('S12','JLC BOOMELE IDC10 / C5665','https://jlcpcb.com/partdetail/C5665'),
 ('S13','TI TLV755P / reverse-current conditions','https://www.ti.com/lit/ds/symlink/tlv755p.pdf'),
]
for label,title,url in sources:story += [p('['+label+'] '+link(title,url),'small')]

def footer(c,doc):
 c.setStrokeColor(LINE);c.line(36,35,A4[0]-36,35)
 c.setFont('JP',7.3);c.setFillColor(MUTED)
 c.drawString(36,23,'TAKAZUDO / LIGHT BLOCK '+REV+'  |  ENGINEERING DEVELOPMENT')
 c.drawRightString(A4[0]-36,23,f'{doc.page}  /  {day} JST')

path=OUT/f'light_block_{REV_FILENAME}_engineering_update.pdf'
doc=SimpleDocTemplate(str(path),pagesize=A4,rightMargin=36,leftMargin=36,topMargin=36,bottomMargin=47,
 title='Light Block '+REV+' - engineering development',author='Takazudo / OpenAI',
 subject='Native electronics, rear mechanics, compiled firmware, procurement and remaining release conditions')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(path)

