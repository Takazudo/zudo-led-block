"""Focused active-successor evaluation; not a PCB release or drop-in approval."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json

ROOT = Path(__file__).resolve().parent
PACKAGE_ROOT = ROOT.parents[1]
TDK_OBSERVATION = ROOT / 'inputs' / 'tdk_jlc_observation.json'
SELECTED_SOURCE = PACKAGE_ROOT / 'procurement_rows.json'
observed = json.loads(TDK_OBSERVATION.read_text())
selected_rows = json.loads(SELECTED_SOURCE.read_text())['components']
selected_tdk = next(r for r in selected_rows if r['c_code'] == 'C694586')
assert observed['mpn'] == selected_tdk['mpn'] == 'SPM4020T-4R7M-LR'
assert observed['stock'] == selected_tdk['stock'] == 726
assert observed['prepurchase_qty'] == selected_tdk['prepurchase_qty'] == 719
assert observed['tiers'] == selected_tdk['tiers']
assert [(t['min_qty'],t['unit_price_usd']) for t in observed['tiers']] == [(1,.3802),(50,.3024),(150,.2690),(500,.2197),(2500,.2011),(5000,.1901)]
assert observed['observed_jst'] == '2026-11-06T11:37:37.160+09:00'
vin, vout, fs, inductance = 12, 5, 1.1e6, 4.7e-6
ripple = vout * (1-vout/vin) / (fs*inductance)
scenarios = []
for current in (0.4,0.5):
    rms2 = current**2 + ripple**2/12
    scenarios.append({
        'load_current_A':current,
        'inductor_ripple_peak_to_peak_A':ripple,
        'inductor_peak_A':current+ripple/2,
        'inductor_RMS_A':rms2**.5,
        'TDK_copper_loss_at_max_DCR_reference_temperature_W':rms2*.1472,
        'Wurth_copper_loss_at_max_DCR_20C_W':rms2*.105,
        'extra_reference_temperature_copper_loss_W':rms2*(.1472-.105),
    })
sources = [
    {'id':'TDK-ACTIVE','url':'https://product.tdk.com/en/search/inductor/inductor/smd/info?part_no=SPM4020T-4R7M-LR',
     'tool_refs':['turn21view0','turn22view0'],'supports':'Production status; dimensions and typical electrical parameters.'},
    {'id':'TDK-DATASHEET','url':'https://product.tdk.com/ja/system/files/dam/doc/product/inductor/inductor/smd/catalog/inductor_commercial_power_spm4020-lr_ja.pdf',
     'revision_date':'2026-04-23','tool_refs':['turn21view2','turn26view0'],
     'supports':'4.7 uH ±20%; max DCR147.2mOhm; Isat3.5A typical at30% drop; Itemp2.5A typical at40C rise; height2mm max; recommended land pattern.'},
    {'id':'TDK-OBSOLETE','url':'https://product.tdk.com/en/search/inductor/inductor/smd/info?part_no=SPM4020T-4R7M',
     'tool_refs':['turn21view1','turn22view1'],'supports':'Old non-LR part obsolete; last shipment2024-03-31; LR recommended without guaranteed interchangeability.'},
    {'id':'JLC-LIVE','url':'https://jlcpcb.com/partdetail/C694586',
     'observer':'Parent task /root, rendered public browser DOM',
     'observed_utc':'2026-11-06T02:37:37.160Z',
     'supports':'Exact MPN and C-code, assembly/library classification, fresh stock/Available Order Qty and USD price tiers.'},
    {'id':'LCSC-ID','url':'https://www.lcsc.com/product-detail/power-inductors_tdk-spm4020t-4r7m-lr_C694586.html',
     'tool_refs':['turn20search0'],'supports':'Independent distributor identity mapping only; its inventory is not used as JLC PCBA inventory.'},
    {'id':'DIODES-BUCK','url':'https://www.diodes.com/assets/Datasheets/AP63200-AP63201-AP63203-AP63205.pdf',
     'revision':'DS41326 Rev3-2, November2024','tool_refs':['turn27view1','turn28view1'],
     'supports':'AP63205 recommends4.7uH; 1100kHz typical; ±6% FSS; 2.5/2.8/3.1A min/typ/max HS peak limit; cycle protection and hiccup; DCR<100mOhm for highest efficiency is a recommendation.'},
    {'id':'WURTH-BASELINE','url':'https://www.we-online.com/components/products/datasheet/74437324047.pdf',
     'revision':'003.000, 2024-12-27','tool_refs':['turn25view0','turn26view1'],
     'supports':'Original 4.7uH±20%,2mm max body,95mOhm typical/105mOhm maximum DCR,5.4A typical30% saturation and recommended land pattern.'},
]
result = {
    'project':'Light Block', 'revision':'A4.1 focused inductor cost-down recommendation',
    'frozen_observation_source':str(TDK_OBSERVATION.relative_to(PACKAGE_ROOT)),
    'selected_procurement_source':'procurement_rows.json',
    'created_jst':datetime.now(timezone(timedelta(hours=9))).isoformat(),
    'decision':'SELECT_FOR_INTEGRATED_PROTOTYPE_DESIGN_PENDING_LAYOUT_AND_HOT_FAULT_VALIDATION',
    'manufacturing_release':False, 'drop_in_approved':False,
    'recommendation':'Select the active LR successor for the A4.1 cost/availability target. Preserve the original Wurth as fallback. Do not use obsolete non-LR as a new baseline.',
    'selected_candidate':{
        'manufacturer':'TDK','mpn':'SPM4020T-4R7M-LR','c_code':'C694586','qty_per_module':1,
        'manufacturer_product_status':'Production',
        'library':'Extended','pcba_type':'Economic and Standard','assembly_type':'SMT Assembly',
        'stock':726,'available_order_qty':719,'observed_utc':'2026-11-06T02:37:37.160Z',
        'observed_jst':'2026-11-06T11:37:37.160+09:00',
        'stock_covers_100_fitted_modules':True,'available_order_qty_covers_100_fitted_modules':True,
        'tiers':[{'min_qty':q,'unit_price_usd':p} for q,p in [(1,.3802),(50,.3024),(150,.2690),(500,.2197),(2500,.2011),(5000,.1901)]],
        'inductance_uH':4.7,'inductance_tolerance_pct':20,
        'body_dimensions_mm':{'L_nominal':4.4,'L_tolerance':.2,'W_nominal':4.1,'W_tolerance':.2,'H_max':2.0},
        'DCR_typ_ohm':.128,'DCR_max_ohm':.1472,
        'saturation_current_A':{'typical':3.5,'criterion':'30% inductance reduction','guaranteed_hot_minimum':None},
        'thermal_current_A':{'typical':2.5,'criterion':'40 C rise','guaranteed_hot_minimum':None},
        'operating_temperature_C':[-40,125],'temperature_includes_self_rise':True,
    },
    'rejected_related_part':{
        'mpn':'SPM4020T-4R7M','manufacturer_status':'Obsolete',
        'discontinue_issue_date':'2022-06-03','last_purchase_order_date':'2023-09-30','last_shipment_date':'2024-03-31',
        'reason':'The exact non-LR related-product suggestion has ended production. Its price is not applied to the LR part.'},
    'normal_load_calculation':{
        'input_V':vin,'output_V':vout,'frequency_Hz_typical':fs,'inductance_H_nominal':inductance,
        'model':'Ideal continuous conduction buck; reference-temperature copper loss only. The 0.5A case adds planning headroom for logic to the approximate0.4A output regime; it is not a final verified total-current bound.',
        'scenarios':scenarios,
        'excluded':'Frequency tolerance/FSS corners, core loss, DCR temperature rise, inductance bias, efficiency, startup/transients and hot-short waveform.'},
    'fault_qualification':{
        'status':'OPEN',
        'buck_HS_current_limit_min_typ_max_A':[2.5,2.8,3.1],
        'finding':'Typical TDK Isat3.5A is above buck3.1A maximum, but a typical number is not a guaranteed minimum over temperature and lot. The paper review does not prove no significant saturation during upstream short/startup.',
        'protection_scope':'The downstream TPS2552-1 LED latch does not bound a fault on the unswitched buck rail. AP63205 cycle current limiting and hiccup reduce fault energy but do not independently validate this inductor and PCB.',
        'close_with':'Final power-loop/land-pattern review, startup and upstream/downstream short measurements at the selected input/ambient extremes, with current waveform and inductor/regulator temperature. Retain Wurth fallback if margin is inadequate.'},
    'layout_qualification':{
        'status':'OPEN','height_result':'2.0mm max body preserves the existing body-height target; solder height and placement clearance still apply.',
        'footprint_result':'Use the exact TDK recommended land pattern. Similar body size does not establish compatibility with the original Wurth footprint; the native layout has not been generated or compared.',
        'assembly_process_note':'TDK specifies no cleaning agents; the final PCBA process must comply.'},
    'cost_comparison_usd_per_module':[
        {'planned_modules':1,'fresh_A4_baseline':10.9847,'A4_1_with_TDK':9.6312,'savings':1.3535},
        {'planned_modules':10,'fresh_A4_baseline':9.82,'A4_1_with_TDK':8.6171,'savings':1.2029},
        {'planned_modules':100,'fresh_A4_baseline':7.5283,'A4_1_with_TDK':6.4997,'savings':1.0286}],
    'cost_scope':'Fitted components at displayed tiers only. Excludes attrition, MOQ/pre-purchase minimums, PCB, assembly/setup/extra processing, harness, enclosure, freight and taxes.',
    'sources':sources,
}
(ROOT/'TDK_SPM4020T_4R7M_LR_evaluation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')

md = '''# A4.1 inductor cost-down decision

**Select TDK SPM4020T-4R7M-LR / C694586 for the integrated prototype design, with final footprint and hot-fault qualification still open. Keep Würth 74437324047 as fallback.** This changes the design selection; it is not a drop-in substitution or a manufacturing release.

## Supply and cost

The parent task read the official [JLC product page](https://jlcpcb.com/partdetail/C694586) at **2026-11-06 11:37:37 JST**: 726 in stock, 719 Available Order Qty, Extended, SMT Assembly, Economic and Standard. Both quantity fields cover 100 fitted parts before attrition. Available Order Qty is a separate pre-purchase display, not reserved PCBA stock.

| Minimum quantity | USD each |
|---:|---:|
| 1 | 0.3802 |
| 50 | 0.3024 |
| 150 | 0.2690 |
| 500 | 0.2197 |
| 2500 | 0.2011 |
| 5000 | 0.1901 |

| Planned modules | Fresh A4 fitted-parts cost/module | With TDK | Saving/module |
|---:|---:|---:|---:|
| 1 | $10.9847 | $9.6312 | $1.3535 |
| 10 | $9.8200 | $8.6171 | $1.2029 |
| 100 | $7.5283 | $6.4997 | $1.0286 |

These calculations exclude minimum purchases, attrition, PCB/PCBA charges, harness, exterior, freight and taxes. They do not authorize an order.

## Electrical and mechanical basis

[TDK identifies the LR part as Production](https://product.tdk.com/en/search/inductor/inductor/smd/info?part_no=SPM4020T-4R7M-LR). Its [2026-04-23 datasheet](https://product.tdk.com/ja/system/files/dam/doc/product/inductor/inductor/smd/catalog/inductor_commercial_power_spm4020-lr_ja.pdf) specifies 4.7 µH ±20%, 4.4±0.2 × 4.1±0.2 mm body, 2.0 mm maximum height, and 147.2 mΩ maximum DCR. Saturation current is **3.5 A typical** at 30% inductance reduction; thermal current is **2.5 A typical** at 40°C rise. Neither is a guaranteed hot minimum. Use the exact TDK lands and its compatible assembly process; the datasheet prohibits cleaning agents.

The [AP63205 reference circuit](https://www.diodes.com/assets/Datasheets/AP63200-AP63201-AP63203-AP63205.pdf) recommends 4.7 µH. At 12 V → 5 V, 1.1 MHz, ideal continuous-conduction analysis gives 0.564 A peak-to-peak ripple. At 0.4 A output, peak/RMS inductor currents are 0.682/0.432 A; at a 0.5 A planning allowance they are 0.782/0.526 A. Normal-load margin is ample for prototype selection. These are calculated operating points, not all-corner qualification.

Against the [Würth maximum DCR of 105 mΩ](https://www.we-online.com/components/products/datasheet/74437324047.pdf), TDK adds approximately 8 mW copper loss at 0.4 A, or 12 mW at 0.5 A, at the reference resistance temperature. Core loss and temperature dependence are excluded. TDK exceeds the buck datasheet's recommendation of under 100 mΩ for highest efficiency; the small calculated load loss makes that a reasonable prototype tradeoff, not an efficiency guarantee.

## Required closure before release

The buck's high-side peak current limit can reach **3.1 A**, and it implements cycle limiting and hiccup. TDK's 3.5 A typical saturation figure does not prove a guaranteed hot-current margin. An upstream buck-rail short also bypasses the downstream LED latch. Confirm startup and upstream/downstream short waveforms and temperature on the integrated assembly, along with the exact power-loop layout and TDK lands. Similar body dimensions do not prove footprint interchangeability. The existing 2 mm body-height target is preserved, while solder height and final clearance remain part of mechanical verification.

The originally suggested [SPM4020T-4R7M without LR is obsolete](https://product.tdk.com/en/search/inductor/inductor/smd/info?part_no=SPM4020T-4R7M): last shipment was 2024-03-31. Do not use its displayed related-product price as evidence for the active LR part. TDK names LR as its successor but does not guarantee interchangeability.

The JSON companion retains exact sources, observation time, formulas, values and unclosed qualification items.
'''
(ROOT/'TDK_SPM4020T_4R7M_LR_evaluation.md').write_text(md)
print('Wrote focused TDK evaluation JSON and Markdown')
