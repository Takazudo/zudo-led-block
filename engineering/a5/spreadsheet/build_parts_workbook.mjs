import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

// Execute with the bundled Codex primary Node runtime, from a writable OS tmp
// directory whose node_modules symlink points to CODEX_PRIMARY_RUNTIME_NODE_MODULES.
const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const projectDir = process.env.LB_PROJECT_DIR || (path.basename(scriptDir) === 'spreadsheet' ? path.dirname(scriptDir) : scriptDir);
const inputPath = process.argv[2] || path.join(projectDir, 'procurement_rows.json');
const outputDir = process.env.LB_OUTPUT_DIR || path.join(projectDir, 'deliverables');
const qaDir = process.env.LB_QA_DIR || path.join(projectDir, 'spreadsheet_qa');
const source = JSON.parse(await fs.readFile(inputPath, 'utf8'));
const revision = source.revision || 'A4';
const revisionFileTag = revision.replace(/[^A-Za-z0-9_]+/g, '_');
const outputPath = path.join(outputDir, `light_block_${revisionFileTag}_parts.xlsx`);
const font = 'Noto Sans JP';
const C = { navy:'#253C56', ink:'#253544', muted:'#586B7B', rule:'#CAD3DB', light:'#F1F4F7', amber:'#FFF2CC', red:'#FCE4D6', redInk:'#9C2D20' };
const fmtInt = '#,##0';
const fmtPrice = '"$"0.0000##';
const fmtCost = '"$"#,##0.0000';
const fmtTotal = '"$"#,##0.00';
const fmtDate = 'yyyy/mm/dd hh:mm:ss';
const proto = source.prototype_modules;
const comparison = source.inventory_modules;
const parts = source.components;
const external = source.external_items || [];
if (!Array.isArray(parts) || !parts.length) throw new Error('components must contain real procurement rows');
if (![proto,comparison].every(n => Number.isInteger(n) && n >= 0)) throw new Error('Module counts must be nonnegative integers');
if (!source.as_of_jst) throw new Error('Missing as_of_jst');
const seen = new Set();
for (const item of parts) {
  if (!item.id || seen.has(item.id)) throw new Error(`Missing or duplicate component ID: ${item.id}`);
  seen.add(item.id);
  if (!Number.isFinite(item.qty_per_module) || item.qty_per_module < 0) throw new Error(`Invalid qty_per_module: ${item.id}`);
  for (const key of ['stock','prepurchase_qty']) if (item[key]!=null && typeof item[key]!=='number') throw new Error(`Expected numeric source ${key}: ${item.id}`);
  item._tiers = [...(item.tiers || [])].sort((a,b)=>a.min_qty-b.min_qty);
  for (let i=0;i<item._tiers.length;i++) {
    const t=item._tiers[i];
    if (!Number.isFinite(t.min_qty) || !Number.isFinite(t.unit_price_usd)) throw new Error(`Non-numeric price tier: ${item.id}`);
    if (i && t.min_qty===item._tiers[i-1].min_qty) throw new Error(`Duplicate price threshold: ${item.id}`);
    if (i && item._tiers[i-1].max_qty!=null && item._tiers[i-1].max_qty+1!==t.min_qty) throw new Error(`Gapped/overlapping tier range: ${item.id}`);
  }
}

await fs.mkdir(outputDir,{recursive:true});
await fs.mkdir(qaDir,{recursive:true});
const wb=Workbook.create();
const main=wb.worksheets.add('部品表');
const prices=wb.worksheets.add('価格帯');
const ext=wb.worksheets.add('外部品');
main.tabColor=C.navy;prices.tabColor='#8293A5';ext.tabColor='#607C69';

function set(sheet,cell,value){sheet.getRange(cell).values=[[value]];}
function formula(sheet,cell,value){sheet.getRange(cell).formulas=[[value]];}
function colName(n){let s='';for(;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;}
function bounds(sheet,lastRow,lastCol){
  sheet.showGridLines=false;
  const r=sheet.getRange(`A1:${lastCol}${lastRow}`);
  r.format.font={name:font,size:10,color:C.ink};
  r.format.verticalAlignment='center';r.format.rowHeight=22;
  sheet.getRange(`A1:${lastCol}1`).format.rowHeight=10;
}
function widths(sheet,values,lastRow){values.forEach((px,i)=>sheet.getRange(`${colName(i+1)}1:${colName(i+1)}${lastRow}`).format.columnWidthPx=px);}
function title(sheet,text,lastCol){
  set(sheet,'A2',text);sheet.getRange('A2').format.font={name:font,size:15,bold:true,color:C.navy};
  sheet.getRange(`A2:${lastCol}2`).format.rowHeight=30;
  sheet.getRange(`A3:${lastCol}3`).format.borders={bottom:{style:'thin',color:C.rule}};
}
function header(sheet,range,labels){
  const r=sheet.getRange(range);r.values=[labels];r.format.fill=C.navy;
  r.format.font={name:font,size:10,bold:true,color:'#FFFFFF'};
  r.format.horizontalAlignment='center';r.format.verticalAlignment='center';r.format.wrapText=true;
  r.format.rowHeight=38;r.format.borders={insideVertical:{style:'thin',color:'#FFFFFF'}};
}
function dateJst(raw){
  if(!raw)return null;
  const d=new Date(raw);if(Number.isNaN(d.valueOf()))throw new Error(`Invalid timestamp: ${raw}`);
  // Excel dates have no timezone. Store the JST wall-clock numerically and label it.
  return (d.valueOf()+9*3600*1000)/86400000+25569;
}
function numberOrNull(value){return typeof value==='number' && Number.isFinite(value)?value:null;}
function lookupPrice(item,qty){
  if(qty===0)return 0;
  const match=item._tiers.filter(t=>t.min_qty<=qty).at(-1);
  return match && (match.max_qty==null || qty<=match.max_qty) ? match.unit_price_usd : null;
}
function sumKnown(values){return values.every(Number.isFinite)?values.reduce((a,b)=>a+b,0):null;}

// Source price bands: one bounded ascending range per component. Metadata is
// written once at the first tier row, beside that component's price bands.
const bandRows=new Map();
let priceRow=7;
for(const item of parts){
  const count=Math.max(1,item._tiers.length);
  bandRows.set(item.id,{start:priceRow,end:priceRow+count-1});priceRow+=count+1;
}
bounds(prices,priceRow+2,'R');
widths(prices,[84,100,115,100,260,105,22,22,22,100,115,95,150,145,180,610,310,680],priceRow+2);
title(prices,'確認した価格帯と調達条件','R');
set(prices,'A3','単価は USD/個。各部品の min_qty 昇順の範囲を VLOOKUP 近似一致で参照します。');
set(prices,'A4','価格表の範囲は部品ごとに固定です。範囲内の順序を保って価格・数量境界を更新してください。');
set(prices,'A5','実際の PCBA が基板別の発注になると、適用される価格帯が変わる場合があります。');
set(prices,'J4','InStock と AvailableOrderQty は別の項目です。空欄は未確認、数値 0 は取得値を保持します。');
set(prices,'J5','Standard の Basic / Extended フィーダー費の出典: https://jlcpcb.com/help/article/pcb-assembly-price');
header(prices,'A6:F6',['ID','min_qty','USD/個','max_qty','型番','LCSC']);
header(prices,'J6:R6',['InStock','Available\nOrderQty','Library','PCBA 種別','実装方式','確認日時 JST','出典 URL','採用・設計状況','注記']);
for(let i=0;i<parts.length;i++){
  const item=parts[i],b=bandRows.get(item.id);
  const data=item._tiers.length?item._tiers.map(t=>[item.id,t.min_qty,t.unit_price_usd,t.max_qty??null,null,null]):[[item.id,null,null,null,null,null]];
  data[0][4]=item.mpn??'';data[0][5]=item.c_code??'';
  prices.getRange(`A${b.start}:F${b.end}`).values=data;
  prices.getRange(`A${b.start}:F${b.end}`).format.fill=i%2?C.light:'#FFFFFF';
  prices.getRange(`B${b.start}:D${b.end}`).format.horizontalAlignment='right';
  prices.getRange(`E${b.start}`).format.horizontalAlignment='center';
  if(item.id==='C5665')prices.getRange(`E${b.start}`).format.wrapText=true;
  prices.getRange(`B${b.start}:B${b.end}`).setNumberFormat(fmtInt);
  prices.getRange(`C${b.start}:C${b.end}`).setNumberFormat(fmtPrice);
  prices.getRange(`D${b.start}:D${b.end}`).setNumberFormat(fmtInt);
  prices.getRange(`J${b.start}:R${b.start}`).values=[[
    numberOrNull(item.stock),numberOrNull(item.prepurchase_qty),item.library??'',item.pcba_type??'',item.assembly_type??'',
    dateJst(item.observed_jst),item.url??'',item.status_ja??'',item.notes_ja??''
  ]];
  prices.getRange(`J${b.start}:K${b.start}`).setNumberFormat(fmtInt);
  prices.getRange(`O${b.start}`).setNumberFormat(fmtDate);
  prices.getRange(`P${b.start}`).format.font={name:font,size:10,color:'#285B8E'};
  prices.getRange(`P${b.start}`).format.wrapText=true;
  prices.getRange(`M${b.start}`).format.wrapText=true;
  prices.getRange(`L${b.start}`).format.horizontalAlignment='center';
  prices.getRange(`Q${b.start}:R${b.start}`).format.wrapText=true;
  prices.getRange(`Q${b.start}:R${b.start}`).format.verticalAlignment='top';
  const noteLines=Math.max(1,Math.ceil(String(item.notes_ja??'').length/62),Math.ceil(String(item.status_ja??'').length/28));
  prices.getRange(`A${b.start}:R${b.start}`).format.rowHeight=Math.max(40,noteLines*16+8);
}
prices.freezePanes.freezeRows(6);prices.freezePanes.freezeColumns(1);

const first=15,last=first+parts.length-1;
bounds(main,last+3,'P');
widths(main,[95,130,240,260,105,65,88,98,105,88,98,105,100,115,105,290],last+3);
title(main,`Light Block ${revision} 部品在庫・価格`,'P');
set(main,'A3','確認期間 JST');set(main,'D3',source.as_of_jst);
set(main,'E5','試作台数');set(main,'G5',proto);set(main,'I5','比較台数');set(main,'K5',comparison);
set(main,'E6','部品計 USD');set(main,'I6','部品計 USD');
set(main,'E7','USD / 台');set(main,'I7','USD / 台');
main.getRange('G5').format.fill=C.amber;main.getRange('K5').format.fill=C.amber;
main.getRange('G5').format.font={name:font,size:12,bold:true,color:C.ink};main.getRange('K5').format.font={name:font,size:12,bold:true,color:C.ink};
main.getRange('G5').setNumberFormat(fmtInt);main.getRange('K5').setNumberFormat(fmtInt);
main.dataValidations.add({range:'G5',rule:{type:'whole',operator:'between',formula1:0,formula2:1000000}});
main.dataValidations.add({range:'K5',rule:{type:'whole',operator:'between',formula1:0,formula2:1000000}});
set(main,'A9','黄色セルは試算用の数量です。試作・比較の台数は発注数量ではありません。');
set(main,'A10','InStock は在庫、AvailableOrderQty は先行購入上限。上限が 0 でも PCBA 不可能とは断定しません。');
set(main,'A11','部品費のみ。調達ロス・MOQ・実装費・治具・送料・税を含みません。外部品は別シートです。');
set(main,'A12','Standard 実装では Basic 部品もフィーダー費の対象です。A5は設計開発版です。製造リリース・実機検証は未完です。');
main.getRange('A9:P12').format.font={name:font,size:10,color:C.muted};
main.getRange('A4:P4').format.rowHeight=8;main.getRange('A8:P8').format.rowHeight=8;main.getRange('A13:P13').format.rowHeight=8;
header(main,'A14:P14',['ID','区分','用途','型番','LCSC','個/台','必要数\n試作','試作単価\nUSD/個','試作金額\nUSD','必要数\n比較','比較単価\nUSD/個','比較金額\nUSD','InStock','先行購入\n上限','Library','採用・設計状況']);
const mainRows=[];
for(let i=0;i<parts.length;i++){
  const item=parts[i],r=first+i,b=bandRows.get(item.id);
  mainRows.push([item.id,item.category??'',item.role_ja??'',null,null,item.qty_per_module,null,null,null,null,null,null,null,null,null,null]);
  formula(main,`D${r}`,`='価格帯'!E${b.start}`);
  formula(main,`E${r}`,`='価格帯'!F${b.start}`);
}
main.getRange(`A${first}:P${last}`).values=mainRows;
// Write formulas after values, so source-link cells remain formulas.
for(let i=0;i<parts.length;i++){
  const item=parts[i],r=first+i,b=bandRows.get(item.id);
  formula(main,`D${r}`,`='価格帯'!E${b.start}`);formula(main,`E${r}`,`='価格帯'!F${b.start}`);
  formula(main,`G${r}`,`=IF(OR(ISBLANK($G$5),ISBLANK($F${r})),"",$F${r}*$G$5)`);
  formula(main,`J${r}`,`=IF(OR(ISBLANK($K$5),ISBLANK($F${r})),"",$F${r}*$K$5)`);
  for(const [qtyCol,priceCol,costCol] of [['G','H','I'],['J','K','L']]){
    const band=`'価格帯'!$B$${b.start}:$C$${b.end}`;
    const lookup=item._tiers.length?`VLOOKUP(${qtyCol}${r},${band},2,TRUE)`:'"未確認"';
    formula(main,`${priceCol}${r}`,`=IF(ISNUMBER(${qtyCol}${r}),IF(${qtyCol}${r}=0,0,${lookup}),"")`);
    formula(main,`${costCol}${r}`,`=IF(ISNUMBER(${qtyCol}${r}),IF(ISNUMBER(${priceCol}${r}),${qtyCol}${r}*${priceCol}${r},"未確認"),"")`);
  }
  formula(main,`M${r}`,`=IF(ISBLANK('価格帯'!J${b.start}),"",'価格帯'!J${b.start})`);
  formula(main,`N${r}`,`=IF(ISBLANK('価格帯'!K${b.start}),"",'価格帯'!K${b.start})`);
  formula(main,`O${r}`,`='価格帯'!L${b.start}`);formula(main,`P${r}`,`='価格帯'!Q${b.start}`);
  if(i%2)main.getRange(`A${r}:P${r}`).format.fill=C.light;
  main.getRange(`F${r}`).format.fill='#FFF8E3';
  main.getRange(`C${r}`).format.wrapText=true;main.getRange(`P${r}`).format.wrapText=true;
  if(item.id==='C5665')main.getRange(`D${r}`).format.wrapText=true;
  main.getRange(`A${r}:P${r}`).format.rowHeight=Math.max(40,Math.ceil(String(item.status_ja??'').length/27)*16+8,Math.ceil(String(item.role_ja??'').length/17)*16+8);
}
formula(main,'G6',`=IF(ISBLANK(G5),"",IF(COUNT(I${first}:I${last})<${parts.length},"未確認あり",SUM(I${first}:I${last})))`);
formula(main,'K6',`=IF(ISBLANK(K5),"",IF(COUNT(L${first}:L${last})<${parts.length},"未確認あり",SUM(L${first}:L${last})))`);
formula(main,'G7','=IF(ISBLANK(G5),"",IF(G5=0,"n.a.",IF(ISNUMBER(G6),G6/G5,"未確認あり")))');
formula(main,'K7','=IF(ISBLANK(K5),"",IF(K5=0,"n.a.",IF(ISNUMBER(K6),K6/K5,"未確認あり")))');
main.getRange(`F${first}:N${last}`).format.horizontalAlignment='right';
for(const c of ['F','G','J','M','N'])main.getRange(`${c}${first}:${c}${last}`).setNumberFormat(fmtInt);
for(const c of ['H','K'])main.getRange(`${c}${first}:${c}${last}`).setNumberFormat(fmtPrice);
for(const c of ['I','L'])main.getRange(`${c}${first}:${c}${last}`).setNumberFormat(fmtCost);
for(const c of ['G6','K6'])main.getRange(c).setNumberFormat(fmtTotal);
for(const c of ['G7','K7'])main.getRange(c).setNumberFormat(fmtCost);
main.getRange('G6').format.font={name:font,size:12,bold:true,color:C.navy};main.getRange('K6').format.font={name:font,size:12,bold:true,color:C.navy};
main.getRange(`M${first}:M${last}`).conditionalFormats.addCustom(`AND(ISNUMBER(M${first}),M${first}<J${first})`,{fill:C.red,font:{color:C.redInk,bold:true}});
main.getRange(`H${first}:H${last}`).conditionalFormats.add('containsText',{text:'未確認',format:{fill:C.red,font:{color:C.redInk}}});
main.getRange(`K${first}:K${last}`).conditionalFormats.add('containsText',{text:'未確認',format:{fill:C.red,font:{color:C.redInk}}});
const table=main.tables.add(`A14:P${last}`,true,'A4Parts');table.showFilterButton=true;table.style='TableStyleLight1';
main.getRange(`O${first}:O${last}`).format.horizontalAlignment='center';
main.freezePanes.freezeRows(14);main.freezePanes.freezeColumns(5);

// External products are deliberately separate from JLC PCBA component totals.
const extFirst=9,extLast=Math.max(extFirst,extFirst+external.length-1);
let extTierRow=extLast+6;
const extBandRows=new Map();
for(const item of external){
  item._tiers=[...(item.tiers||[])].sort((a,b)=>a.min_qty-b.min_qty);
  if(item._tiers.length){extBandRows.set(item.id,{start:extTierRow,end:extTierRow+item._tiers.length-1});extTierRow+=item._tiers.length+1;}
}
bounds(ext,extTierRow+2,'Q');
widths(ext,[95,210,520,75,100,105,115,100,105,115,100,160,310,180,620,22,700],extTierRow+2);
title(ext,'外部購入品とケーブル','Q');
set(ext,'A3','JLC PCBA 部品計には含めません。既製ケーブルは別調達です。');
set(ext,'A4','在庫が「あり」のみの場合は数量を推定しません。単価未確認は金額も未確認として残します。');
set(ext,'A5','必要数は部品表の台数に連動します。記載額は送料・税・追加加工費を含みません。');
set(ext,'A6','価格確認済み小計 USD（未確認品は含めません）');
set(ext,'A7','同上 USD / 台');
header(ext,'A8:O8',['ID','用途','型番・商品名','個/台','必要数\n試作','試作単価\nUSD/個','試作金額\nUSD','必要数\n比較','比較単価\nUSD/個','比較金額\nUSD','在庫数','在庫表示','採用・設計状況','確認日時 JST','出典 URL']);
header(ext,'Q8:Q8',['注記']);
if(extBandRows.size){
  set(ext,`A${extLast+3}`,'外部品の価格帯（USD/個）');
  header(ext,`A${extLast+5}:E${extLast+5}`,['ID','min_qty','USD/個','max_qty','商品名']);
  for(const item of external){
    const b=extBandRows.get(item.id);if(!b)continue;
    ext.getRange(`A${b.start}:E${b.end}`).values=item._tiers.map((t,i)=>[item.id,t.min_qty,t.unit_price_usd,t.max_qty??null,i===0?item.mpn:null]);
    ext.getRange(`B${b.start}:B${b.end}`).setNumberFormat(fmtInt);
    ext.getRange(`C${b.start}:C${b.end}`).setNumberFormat(fmtPrice);
    ext.getRange(`D${b.start}:D${b.end}`).setNumberFormat(fmtInt);
  }
}
if(!external.length)set(ext,'A9','外部品データなし');
const externalExpect=[];
for(let i=0;i<external.length;i++){
  const item=external[i],r=extFirst+i;
  const qty=numberOrNull(item.qty_per_module);
  const price=numberOrNull(item.unit_price_usd ?? item.price_usd);
  const stock=numberOrNull(item.stock);
  const stockText=typeof item.stock==='string'?item.stock:(item.stock_text??item.stock_status??(String(item.status_ja??'').startsWith('In Stock')?'In Stock（数量不明）':''));
  ext.getRange(`A${r}:O${r}`).values=[[
    item.id??'',item.role_ja??item.category??'',item.mpn??item.name??'',qty,null,price,null,null,price,null,stock,
    stockText,item.status_ja??'',dateJst(item.observed_jst),item.url??''
  ]];
  set(ext,`Q${r}`,item.notes_ja??'');
  formula(ext,`E${r}`,`=IF(OR(ISBLANK('部品表'!$G$5),ISBLANK(D${r})),"",D${r}*'部品表'!$G$5)`);
  formula(ext,`H${r}`,`=IF(OR(ISBLANK('部品表'!$K$5),ISBLANK(D${r})),"",D${r}*'部品表'!$K$5)`);
  for(const [qtyCol,priceCol,costCol] of [['E','F','G'],['H','I','J']]){
    const b=extBandRows.get(item.id);
    if(b)formula(ext,`${priceCol}${r}`,`=IF(ISNUMBER(${qtyCol}${r}),IF(${qtyCol}${r}=0,0,VLOOKUP(${qtyCol}${r},$B$${b.start}:$C$${b.end},2,TRUE)),"")`);
    formula(ext,`${costCol}${r}`,`=IF(ISNUMBER(${qtyCol}${r}),IF(${qtyCol}${r}=0,0,IF(ISNUMBER(${priceCol}${r}),${qtyCol}${r}*${priceCol}${r},"未確認")),"")`);
    ext.getRange(`${priceCol}${r}`).setNumberFormat(fmtPrice);ext.getRange(`${costCol}${r}`).setNumberFormat(fmtCost);
  }
  ext.getRange(`D${r}:E${r}`).setNumberFormat(fmtInt);ext.getRange(`H${r}`).setNumberFormat(fmtInt);ext.getRange(`K${r}`).setNumberFormat(fmtInt);
  ext.getRange(`N${r}`).setNumberFormat(fmtDate);
  ext.getRange(`O${r}`).format.wrapText=true;
  ext.getRange(`O${r}`).format.font={name:font,size:10,color:'#285B8E'};
  ext.getRange(`B${r}:C${r}`).format.wrapText=true;ext.getRange(`L${r}:M${r}`).format.wrapText=true;ext.getRange(`Q${r}`).format.wrapText=true;
  const lines=Math.max(Math.ceil(String(item.notes_ja??'').length/65),Math.ceil(String(item.status_ja??'').length/28),Math.ceil(String(item.role_ja??'').length/19));
  ext.getRange(`A${r}:Q${r}`).format.rowHeight=Math.max(46,lines*16+8);
  if(i%2){ext.getRange(`A${r}:O${r}`).format.fill=C.light;ext.getRange(`Q${r}`).format.fill=C.light;}
  ext.getRange(`D${r}`).format.fill='#FFF8E3';
  externalExpect.push({id:item.id,qty_per_module:qty,unit_price_usd:price,stock_numeric:stock,stock_text:stockText});
}
formula(ext,'G6',`=IF(ISBLANK('部品表'!G5),"",SUM(G${extFirst}:G${extLast}))`);
formula(ext,'J6',`=IF(ISBLANK('部品表'!K5),"",SUM(J${extFirst}:J${extLast}))`);
formula(ext,'G7','=IF(OR(ISBLANK(\'部品表\'!G5),\'部品表\'!G5=0),"n.a.",G6/\'部品表\'!G5)');
formula(ext,'J7','=IF(OR(ISBLANK(\'部品表\'!K5),\'部品表\'!K5=0),"n.a.",J6/\'部品表\'!K5)');
for(const cell of ['G6','J6'])ext.getRange(cell).setNumberFormat(fmtTotal);
for(const cell of ['G7','J7'])ext.getRange(cell).setNumberFormat(fmtCost);
ext.freezePanes.freezeRows(8);ext.freezePanes.freezeColumns(3);

// Independent JS checks exercise actual workbook recalculation, not cached
// manually authored totals. Temporary inputs are restored before export.
const checks=[];
function near(actual,expected,label){
  if(typeof actual!=='number' || Math.abs(actual-expected)>1e-8)throw new Error(`${label}: got ${JSON.stringify(actual)}, expected ${expected}`);
}
function verifyScenario(count,label){
  set(main,'G5',count);wb.recalculate();
  const costs=[];
  for(let i=0;i<parts.length;i++){
    const item=parts[i],r=first+i,q=item.qty_per_module*count,pr=lookupPrice(item,q);
    near(main.getRange(`G${r}`).values[0][0],q,`${label}/${item.id}/quantity`);
    if(pr!==null){near(main.getRange(`H${r}`).values[0][0],pr,`${label}/${item.id}/price`);near(main.getRange(`I${r}`).values[0][0],q*pr,`${label}/${item.id}/amount`);costs.push(q*pr);}
    else costs.push(null);
  }
  const expected=sumKnown(costs),actual=main.getRange('G6').values[0][0];
  if(expected!==null)near(actual,expected,`${label}/total`);
  else if(actual!=='未確認あり')throw new Error(`${label}: missing price was hidden`);
  checks.push({test:label,module_count:count,expected_total_usd:expected,actual_total_usd:actual});
}
verifyScenario(proto,'requested prototype quantity');
verifyScenario(comparison,'comparison quantity through active input');
verifyScenario(1,'single module');
verifyScenario(0,'zero modules');
set(main,'G5',null);wb.recalculate();
if(main.getRange('G6').values[0][0]!=='' || main.getRange(`G${first}`).values[0][0]!=='')throw new Error('Blank quantity became numeric zero');
checks.push({test:'blank quantity',result:'dependent quantities and totals remain blank'});
// Price boundary test on the first actual price table, temporarily using one part/module.
const firstPart=parts.find(x=>x._tiers.length>1);
if(firstPart){
  const ix=parts.indexOf(firstPart),r=first+ix,originalQty=firstPart.qty_per_module;
  set(main,`F${r}`,1);
  for(const t of firstPart._tiers.slice(0,3))for(const q of [Math.max(1,t.min_qty-1),t.min_qty]){
    set(main,'G5',q);wb.recalculate();
    const expected=lookupPrice(firstPart,q);
    if(expected!==null)near(main.getRange(`H${r}`).values[0][0],expected,`price threshold ${q}`);
    checks.push({test:'VLOOKUP tier boundary',component:firstPart.id,required_units:q,unit_price_usd:expected});
  }
  set(main,`F${r}`,originalQty);
}
set(main,'G5',proto);set(main,'K5',comparison);wb.recalculate();
const editedQty=parts[0].qty_per_module*2;
set(main,`F${first}`,editedQty);wb.recalculate();
near(main.getRange(`G${first}`).values[0][0],editedQty*proto,'edited quantity/module updates prototype');
near(main.getRange(`J${first}`).values[0][0],editedQty*comparison,'edited quantity/module updates comparison');
checks.push({test:'quantity per module edit',component:parts[0].id,temporary_qty_per_module:editedQty,result:'both required quantities recalculate'});
set(main,`F${first}`,parts[0].qty_per_module);wb.recalculate();
for(let i=0;i<parts.length;i++){
  const item=parts[i],r=first+i,q=item.qty_per_module*comparison,pr=lookupPrice(item,q);
  near(main.getRange(`J${r}`).values[0][0],q,`comparison/${item.id}/quantity`);
  if(pr!==null){near(main.getRange(`K${r}`).values[0][0],pr,`comparison/${item.id}/price`);near(main.getRange(`L${r}`).values[0][0],q*pr,`comparison/${item.id}/amount`);}
  if(typeof item.stock==='number')near(main.getRange(`M${r}`).values[0][0],item.stock,`source/${item.id}/stock`);
  if(typeof item.prepurchase_qty==='number')near(main.getRange(`N${r}`).values[0][0],item.prepurchase_qty,`source/${item.id}/prepurchase`);
}
for(const [count,col,costCol] of [[proto,'G6','I'],[comparison,'K6','L']]){
  const control=source.cost_checks?.[String(count)];
  if(control){
    near(main.getRange(col).values[0][0]/count,control.fitted_component_cost_per_module_usd,`source reconciliation/${count}/module cost`);
    for(const [category,perModule] of Object.entries(control.categories_per_module_usd||{})){
      const subtotal=parts.reduce((sum,item,i)=>sum+(item.category===category?main.getRange(`${costCol}${first+i}`).values[0][0]:0),0);
      near(subtotal/count,perModule,`source reconciliation/${count}/${category}`);
    }
    checks.push({test:'supplied cost control reconciliation',modules:count,per_module_usd:control.fitted_component_cost_per_module_usd,categories_match:true});
  }
}
for(let i=0;i<external.length;i++){
  const item=external[i],r=extFirst+i;
  for(const [count,qtyCol,priceCol,costCol] of [[proto,'E','F','G'],[comparison,'H','I','J']]){
    if(typeof item.qty_per_module!=='number')continue;
    const q=item.qty_per_module*count,pr=item._tiers.length?lookupPrice(item,q):numberOrNull(item.unit_price_usd??item.price_usd);
    near(ext.getRange(`${qtyCol}${r}`).values[0][0],q,`external/${item.id}/quantity`);
    if(pr!==null){near(ext.getRange(`${priceCol}${r}`).values[0][0],pr,`external/${item.id}/price`);near(ext.getRange(`${costCol}${r}`).values[0][0],q*pr,`external/${item.id}/cost`);}
    else if(ext.getRange(`${costCol}${r}`).values[0][0]!=='未確認')throw new Error(`Missing external price hidden: ${item.id}`);
  }
}
for(const [externalId,controlKey] of [['EXT-01','LED_external_cables_per_module_usd'],['EXT-02','power_external_cable_per_module_usd']]){
  const itemIndex=external.findIndex(item=>item.id===externalId);
  if(itemIndex<0)continue;
  const itemRow=extFirst+itemIndex;
  for(const [count,col] of [[proto,'G'],[comparison,'J']]){
    const expected=source.cost_checks?.[String(count)]?.[controlKey];
    if(typeof expected==='number' && count>0)near(ext.getRange(`${col}${itemRow}`).values[0][0]/count,expected,`external cable control/${externalId}/${count}`);
  }
}
const inspection=await wb.inspect({kind:'table',range:`'部品表'!E5:P${Math.min(last,20)}`,include:'values,formulas',tableMaxRows:18,tableMaxCols:12,maxChars:6000});
await fs.writeFile(path.join(qaDir,'formula_inspection.ndjson'),inspection.ndjson);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:100},summary:'final formula error scan'});
await fs.writeFile(path.join(qaDir,'formula_error_scan.ndjson'),errors.ndjson);
const summary={as_of_jst:source.as_of_jst,component_rows:parts.length,external_rows:external.length,
 prototype_modules:proto,comparison_modules:comparison,prototype_parts_usd:main.getRange('G6').values[0][0],comparison_parts_usd:main.getRange('K6').values[0][0],
 prototype_usd_per_module:main.getRange('G7').values[0][0],comparison_usd_per_module:main.getRange('K7').values[0][0],
 known_external_prototype_usd_per_module:ext.getRange('G7').values[0][0],known_external_comparison_usd_per_module:ext.getRange('J7').values[0][0],
 external_inputs:externalExpect,dynamic_checks:checks,
 calculation_engine:'Artifact Tool. Native Excel application execution was not performed.',
 source_rows_path:inputPath,output_path:outputPath};
await fs.writeFile(path.join(qaDir,'verification.json'),JSON.stringify(summary,null,2));

const views=[
 ['部品表',`A1:P${Math.min(last,23)}`,'parts_overview.png'],
 ['部品表',`A${Math.max(first,last-8)}:P${last}`,'parts_last_rows.png'],
 ['価格帯',`A1:I${Math.min(priceRow,24)}`,'price_tiers.png'],
 ['価格帯',`J6:R${Math.min(priceRow,20)}`,'source_details.png'],
 ['外部品',`A1:O${extLast}`,'external_items.png'],
 ['外部品',`Q8:Q${extLast}`,'external_notes.png'],
 ['外部品',`A${extLast+3}:I${extTierRow}`,'external_price_tiers.png'],
];
for(const [sheetName,range,name] of views){
  const preview=await wb.render({sheetName,range,scale:1.5,format:'png'});
  await fs.writeFile(path.join(qaDir,name),new Uint8Array(await preview.arrayBuffer()));
}
const output=await SpreadsheetFile.exportXlsx(wb);await output.save(outputPath);
console.log(JSON.stringify(summary));
