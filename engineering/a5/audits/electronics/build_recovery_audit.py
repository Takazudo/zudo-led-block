"""Independent, non-mutating audit of the recovered Light Block A4 selection.

Reads the recovered A4 package. Writes an additive audit only. Catalog retrieval
is separate from the original quantity observations; this script never changes
stock timestamps or invents live inventory.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from itertools import product
import json
import shutil

ROOT = Path(__file__).resolve().parent
PACKAGE_ROOT = ROOT.parents[1]
SOURCE = ROOT / 'inputs' / 'a4_history'
LIVE_SOURCE = ROOT / 'inputs' / 'live_jlc_refresh.json'
SELECTED_SOURCE = PACKAGE_ROOT / 'procurement_rows.json'

CATALOG_REFS = {
    'C5270180': ('turn9view0', 'opened', 'today'),
    'C52917434': ('turn4view1', 'opened', 'today'),
    'C2071056': ('turn4view2', 'opened', 'today'),
    'C404027': ('turn9view1', 'opened', 'today'),
    'C140331': ('turn9view2', 'opened', '4 days ago'),
    'C20526': ('turn9view3', 'opened', 'today'),
    'C15741': ('turn10view0', 'opened', 'today'),
    'C221351': ('turn10view1', 'opened', 'today'),
    'C50704': ('turn10view2', 'opened', 'today'),
    'C134375': ('turn10view3', 'opened', 'today'),
    'C2651179': ('turn10view4', 'opened', 'today'),
    'C7250': ('turn11view0', 'opened', 'yesterday'),
    'C23254': ('turn12search0', 'indexed_primary_listing', 'last month'),
    'C21190': ('turn11view2', 'opened', 'today'),
    'C25804': ('turn11view3', 'opened', 'today'),
    'C23231': ('turn11view4', 'opened', 'today'),
    'C25803': ('turn12view0', 'opened', 'today'),
    'C23138': (None, 'unavailable_on_recheck', None),
    'C23162': ('turn12view2', 'opened', 'today'),
    'C14663': ('turn12view3', 'opened', 'today'),
    'C57112': ('turn13search0', 'indexed_primary_listing', '2 months ago'),
    'C15850': ('turn13view0', 'opened', 'today'),
    'C12891': ('turn14search1', 'indexed_primary_listing', '2 months ago'),
    'C19666': ('turn14search0', 'indexed_primary_listing', '2 months ago'),
}

MANUFACTURER_SOURCES = [
    {'id':'TI-TPS255X', 'url':'https://www.ti.com/lit/ds/symlink/tps2553.pdf',
     'tool_refs':['turn4view3','turn16view0','turn7view3'],
     'supports':'Active-low TPS2552-1 latch-off function, EN limits, EN/power reset of fault latch, ILIM equations.'},
    {'id':'TI-LVC2T45', 'url':'https://www.ti.com/lit/ds/symlink/sn74lvc2t45.pdf',
     'tool_refs':['turn15view1'],
     'supports':'Dual-rail supply range, VCCA-referenced DIR, Ioff and isolation when a supply is grounded.'},
    {'id':'TI-TLV755', 'url':'https://www.ti.com/lit/ds/symlink/tlv755p.pdf',
     'tool_refs':['turn15view0'],
     'supports':'3.3 V regulator choice and need to qualify output capacitance.'},
    {'id':'DIODES-AP63205', 'url':'https://www.diodes.com/assets/Datasheets/AP63200-AP63201-AP63203-AP63205.pdf',
     'tool_refs':['turn15view4','turn16view4','turn17view0'],
     'supports':'5 V/1.1 MHz buck; recommended 4.7 uH, 10 uF input, 2x22 uF output, 100 nF bootstrap; 3.1 A maximum high-side peak limit.'},
    {'id':'DIODES-BAS70', 'url':'https://www.diodes.com/_files/datasheets/ds11007.pdf',
     'tool_refs':['turn15view3'],
     'supports':'Exact BAS70-04-7-F order code; 0.41 V maximum at 1 mA/25 C is not a guaranteed -0.3 V clamp.'},
    {'id':'ST-G031', 'url':'https://www.st.com/resource/en/datasheet/stm32g031f8.pdf',
     'tool_refs':['turn15view2','turn16view2','turn17view4'],
     'supports':'G031 architecture, separate pin voltage and current injection constraints, UFQFPN28 package.'},
]

def atier(row, fitted_qty):
    return max((t for t in row['tiers'] if t['min_qty'] <= fitted_qty), key=lambda t:t['min_qty'])['unit_price_usd']

def cv_voltage(cv, vdd, err):
    rs = [v*(1+e) for v,e in zip([10e6,10e6,82e3,82e3,82e3,82e3],err)]
    vbuf = cv*rs[1]/(rs[0]+rs[1])
    return (vbuf/rs[2]+vdd/rs[3]+vdd/rs[4])/(1/rs[2]+1/rs[3]+1/rs[4]+1/rs[5])

def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    original = json.loads((SOURCE/'procurement_rows.json').read_text())
    rows = original['components']
    live_raw = json.loads(LIVE_SOURCE.read_text())
    live = {r[0]:dict(zip(live_raw['columns'],r)) for r in live_raw['rows']}
    assert len(live) == len(rows) == 29
    assert set(live) == {r['c_code'] for r in rows}
    live_rows = []
    for r in rows:
        lr = live[r['c_code']]
        observed = datetime.fromisoformat(lr['observed_utc'].replace('Z','+00:00'))
        tiers = lr['tiers_min_qty_and_unit_price_usd']
        fresh = {
            **r,
            'stock':lr['stock'], 'prepurchase_qty':lr['prepurchase_qty'],
            'observed_jst':observed.astimezone(timezone(timedelta(hours=9))).isoformat(),
            'tiers':[{'min_qty':t[0], 'max_qty':tiers[i+1][0]-1 if i+1<len(tiers) else None,
                      'unit_price_usd':t[1]} for i,t in enumerate(tiers)],
        }
        live_rows.append(fresh)
    fresh_by_code = {r['c_code']:r for r in live_rows}
    shutil.copyfile(LIVE_SOURCE,ROOT/'live_jlc_refresh_source.json')
    snapshots = []
    for r in rows:
        s = json.loads((SOURCE/r['snapshot']).read_text())
        compared = {
            'C-code':s['code'] == r['c_code'],
            'MPN':s['product']['componentModelEn'] == r['mpn'],
            'historical_stock':s['product']['overseasStockCount'] == r['stock'],
            'historical_prepurchase':s['product']['canPresaleNumber'] == r['prepurchase_qty'],
            'tiers':s['tiers'] == r['tiers'],
        }
        assert all(compared.values()), (r['c_code'], compared)
        snapshots.append({'c_code':r['c_code'], 'checks':compared})

    cv_original = json.loads((SOURCE/'cv_resistor_tolerance.json').read_text())
    cv_checks = []
    for c in cv_original['cases']:
        volts = [cv_voltage(c['CV_V'],v,e) for v in [3.3*.98,3.3*1.02]
                 for e in product([-.01,.01],repeat=6)]
        actual = [min(volts),max(volts)]
        expected = c['ADC_V_with_resistor_1pct_and_supply_2pct']
        difference = max(abs(a-b) for a,b in zip(actual,expected))
        assert difference < 1e-12
        cv_checks.append({'CV_V':c['CV_V'], 'independent_ADC_V_bounds':actual,
                          'max_difference_from_recovered_calculation_V':difference,'status':'PASS'})

    ledger = []
    for r in rows:
        if r['c_code'] not in CATALOG_REFS:
            continue
        ref,status,crawl = CATALOG_REFS[r['c_code']]
        ledger.append({
            'c_code':r['c_code'], 'mpn':r['mpn'], 'role':r['role_ja'],
            'qty_per_module':r['qty_per_module'], 'library':r['library'],
            'quantity_basis':'Recovered A4 reference-circuit allocation in role and procurement notes; not a native EDA netlist export.',
            'procurement_notes':r['notes_ja'],
            'pcba_type':r['pcba_type'], 'assembly_type':r['assembly_type'],
            'package':r['package'], 'url':r['url'],
            'historical_quantity_observation':{
                'observed_jst':r['observed_jst'], 'in_stock':r['stock'],
                'available_order_qty':r['prepurchase_qty'], 'snapshot':r['snapshot'],
                'in_stock_covers_100_fitted_modules':r['stock']>=100*r['qty_per_module'],
                'available_order_qty_covers_100_fitted_modules':r['prepurchase_qty']>=100*r['qty_per_module'],
            },
            'catalog_recheck':{
                'status':status, 'tool_ref':ref, 'retrieval_crawl_label':crawl,
                'identity_and_assembly_match':True if ref else None,
                'note':'This field records the child web-text identity/assembly check. The separate live observation records the parent public-page rendered-DOM refresh, including C23138.'
            },
            'live_quantity_and_price_observation':{
                'method':live_raw['method'], 'observer':'parent task /root',
                'evidence_file':'live_jlc_refresh_source.json',
                'observed_utc':live[r['c_code']]['observed_utc'],
                'observed_jst':fresh_by_code[r['c_code']]['observed_jst'],
                'in_stock':fresh_by_code[r['c_code']]['stock'],
                'available_order_qty':fresh_by_code[r['c_code']]['prepurchase_qty'],
                'tiers':fresh_by_code[r['c_code']]['tiers'],
                'in_stock_covers_100_fitted_modules':fresh_by_code[r['c_code']]['stock']>=100*r['qty_per_module'],
                'available_order_qty_covers_100_fitted_modules':fresh_by_code[r['c_code']]['prepurchase_qty']>=100*r['qty_per_module'],
                'delta_in_stock_from_history':fresh_by_code[r['c_code']]['stock']-r['stock'],
                'delta_available_order_qty_from_history':fresh_by_code[r['c_code']]['prepurchase_qty']-r['prepurchase_qty'],
            }
        })

    costs = []
    for n in [1,10,100]:
        per = sum(r['qty_per_module']*atier(r,n*r['qty_per_module']) for r in rows)
        core = sum(r['qty_per_module']*atier(r,n*r['qty_per_module']) for r in rows if r['c_code'] in CATALOG_REFS)
        costs.append({'planning_modules':n,'all_29_type_BOM_usd_per_module':round(per,4),
                      'electronic_24_type_subset_usd_per_module':round(core,4),
                      'basis':'Recovered observed tier schedule applied to fitted quantities; no new quote, attrition, MOQ, PCBA or exterior costs.'})
    live_costs = []
    for n in [1,10,100]:
        per = sum(r['qty_per_module']*atier(r,n*r['qty_per_module']) for r in live_rows)
        core = sum(r['qty_per_module']*atier(r,n*r['qty_per_module']) for r in live_rows if r['c_code'] in CATALOG_REFS)
        live_costs.append({'planning_modules':n,'all_29_type_BOM_usd_per_module':round(per,4),
                          'electronic_24_type_subset_usd_per_module':round(core,4),
                          'basis':'Rendered public-page tier schedule observed at '+live_raw['observed_window_jst']+' applied to fitted quantities. No reservation, order, attrition, MOQ, PCBA or exterior costs.'})
    bottleneck = min(live_rows,key=lambda r:r['prepurchase_qty']//r['qty_per_module'])
    selected = json.loads(SELECTED_SOURCE.read_text())
    selected_rows = selected['components']
    assert len(selected_rows)==29 and sum(r['qty_per_module'] for r in selected_rows)==76
    assert {r['c_code'] for r in selected_rows}-{r['c_code'] for r in rows}=={'C694586'}
    assert {r['c_code'] for r in rows}-{r['c_code'] for r in selected_rows}=={'C2651179'}
    selected_costs = [{'planning_modules':n,'all_29_type_BOM_usd_per_module':round(sum(
        r['qty_per_module']*atier(r,n*r['qty_per_module']) for r in selected_rows),4)} for n in [1,10,100]]
    assert [c['all_29_type_BOM_usd_per_module'] for c in selected_costs]==[9.6312,8.6171,6.4997]
    selected_bottleneck = min(selected_rows,key=lambda r:r['prepurchase_qty']//r['qty_per_module'])

    findings = [
        {'id':'A4-E01','severity':'CONFIRMED_SELECTION','title':'Latch-off survives the availability substitution',
         'detail':'TPS2552DBVR-1 is the active-low latch-off part. The NPN inverter and 100 kOhm pull-up to unswitched 5 V give a dark reset state without a 5 V pull-up on the MCU pin. The suffix -1 must be preserved.',
         'sources':['TI-TPS255X','turn9view2','turn9view3']},
        {'id':'A4-E02','severity':'FIRMWARE_REQUIREMENT_TO_CLOSE','title':'Reset also resets the current-limit latch',
         'detail':'The manufacturer states that toggling EN or cycling switch power clears the latch. Here MCU reset switches the NPN off and deasserts EN. A boot routine that always re-enables LEDs can therefore retry a previous fault. Specify no automatic retry within a running session, and keep watchdog/software-reset startup dark until the chosen deliberate recovery condition. A stronger cross-reset fault policy requires explicit retained state or a revised circuit; it is not established by selecting -1 alone.',
         'sources':['TI-TPS255X'], 'already_implemented':False},
        {'id':'A4-E03','severity':'RELEASE_GATE','title':'ADC fault clamp remains unqualified',
         'detail':'Diodes BAS70-04-7-F is the correct procured dual-series candidate. Its 0.41 V maximum drop at 1 mA/25 C does not prove the ADC pin stays above -0.3 V in all faults or at low temperature. Pin voltage, injection current, power-off backfeed and rail absorption need a completed schematic review. The independently reproduced normal DC corners do not close that gate.',
         'sources':['DIODES-BAS70','ST-G031']},
        {'id':'A4-E04','severity':'RELEASE_GATE','title':'Nominal capacitance is not effective capacitance',
         'detail':'The selected Basic 4.7 uF/16 V X5R capacitors provide nominal margin for the LDO, but DC bias, temperature, tolerance and ageing remain unqualified. The 10 uF/25 V 0805 input and 2x22 uF/25 V 1206 output likewise need operating-point capacitance and layout verification before manufacturing.',
         'sources':['TI-TLV755','DIODES-AP63205']},
        {'id':'A4-E05','severity':'CONFIRMED_SELECTION','title':'LED remains Standard Only on rigid boards',
         'detail':'C52917434 is listed as Standard Only, High assembly difficulty and MSL5. Changing transparent PET leaves to FR-4 does not make this LED an Economic assembly part. Confirm actual assembler charges on the final jobs.',
         'sources':['turn4view1']},
        {'id':'A4-E06','severity':'DESIGN_SELECTION_UPDATED_FOR_A4_1','title':'Active TDK LR inductor selected; Wurth retained as fallback',
         'detail':'Recovered A4 used Wurth74437324047. A4.1 selects active TDK SPM4020T-4R7M-LR/C694586: same4.7uH±20% and2mm maximum height, with lower price and726stock/719AvailableOrderQty observed2026-11-06 11:37:37JST. Normal0.4–0.5A design load has ample calculated current margin; exact lands and hot startup/upstream-short qualification remain open. Typical3.5A saturation is not a guaranteed hot minimum above the buck3.1A maximum peak limit. See TDK_SPM4020T_4R7M_LR_evaluation.json/md. The obsolete non-LR part is rejected.',
         'sources':['DIODES-AP63205','turn10view4']},
        {'id':'A4-E07','severity':'CONFIRMED_PROCUREMENT_OBSERVATION','title':'All 29 quantity and price fields were refreshed separately from history',
         'detail':'All 29 recovered MPN/code/quantity/price rows match their saved snapshots. The parent then read all 29 rendered official JLC product pages at 2026-11-06 11:30:39–11:33:52 JST; every stock, Available Order Qty and price tier is retained separately. All cover 100 fitted modules before attrition. The smallest Available Order Qty is 431 Würth inductors. These are point-in-time displays, not reserved parts or an assembly quote.',
         'sources':[]}
    ]
    result = {
        'project':'Light Block', 'revision':'A4 recovery audit',
        'audit_completed_jst':datetime.now(timezone(timedelta(hours=9))).isoformat(),
        'source_package':str(SOURCE.relative_to(PACKAGE_ROOT)),
        'scope':'Official C-code/MPN/assembly recheck, independent consistency/calculation audit, and parent rendered-page live quantity/price refresh. Additive evidence, not an electrical or manufacturing release.',
        'inventory_freshness':live_raw['observed_window_jst'],
        'quantity_basis':'Recovered A4 reference design and procurement allocation. This package does not contain a completed native schematic/netlist that independently proves the final fitted BOM.',
        'summary':{'whole_BOM_unique_parts':len(rows),'whole_BOM_fitted_pieces':sum(r['qty_per_module'] for r in rows),
                   'electronic_subset_unique_parts':len(ledger),'electronic_subset_fitted_pieces':sum(r['qty_per_module'] for r in ledger),
                   'snapshot_consistency':'PASS: all 29 rows, five field groups each',
                   'catalog_recheck_opened':sum(r['catalog_recheck']['status']=='opened' for r in ledger),
                   'catalog_recheck_indexed_only':sum(r['catalog_recheck']['status']=='indexed_primary_listing' for r in ledger),
                   'catalog_recheck_unavailable':sum(r['catalog_recheck']['status']=='unavailable_on_recheck' for r in ledger),
                   'live_quantity_and_price_rows':len(live_rows),
                   'all_current_stock_counts_cover_100_fitted_modules':all(r['stock']>=100*r['qty_per_module'] for r in live_rows),
                   'all_current_available_order_counts_cover_100_fitted_modules':all(r['prepurchase_qty']>=100*r['qty_per_module'] for r in live_rows),
                   'refreshed_A4_baseline_available_order_bottleneck':{'c_code':bottleneck['c_code'],'mpn':bottleneck['mpn'],
                                                'pieces':bottleneck['prepurchase_qty'],
                                                'fitted_module_equivalent_before_attrition':bottleneck['prepurchase_qty']//bottleneck['qty_per_module']},
                   'selected_A4_1_available_order_bottleneck':{'c_code':selected_bottleneck['c_code'],'pieces':selected_bottleneck['prepurchase_qty']}},
        'historical_cost_recalculation':costs,
        'live_A4_baseline_cost_recalculation':live_costs,
        'selected_A4_1':{
            'source':str(SELECTED_SOURCE.relative_to(PACKAGE_ROOT)),
            'only_part_selection_delta':{'replaced':'C2651179 / 74437324047','selected':'C694586 / SPM4020T-4R7M-LR'},
            'unique_parts':len(selected_rows),'fitted_pieces':sum(r['qty_per_module'] for r in selected_rows),
            'cost_recalculation':selected_costs,
            'all_available_order_counts_cover_100_fitted_modules':all(r['prepurchase_qty']>=100*r['qty_per_module'] for r in selected_rows),
            'available_order_bottleneck':{'c_code':selected_bottleneck['c_code'],'pieces':selected_bottleneck['prepurchase_qty']},
            'detailed_inductor_audit':'TDK_SPM4020T_4R7M_LR_evaluation.json',
            'inductor_manufacturing_release':False,
        },
        'ILIM_recalculation_mA':{'minimum':25230/(68*1.01)**1.016,'nominal':23950/68**.977,'maximum':22980/(68*.99)**.94,
                                'scope':'TI equations with 68 kOhm +/-1%; not an enclosure thermal limit.'},
        'cv_independent_corner_check':cv_checks,
        'ledger':ledger, 'findings':findings, 'manufacturer_sources':MANUFACTURER_SOURCES,
        'snapshot_consistency_checks':snapshots,
        'unperformed':['Native schematic ERC','PCB layout DRC','Firmware execution','Manufacturing quote/order','Physical fit','Powered/unpowered measurements','Temperature test'],
    }
    (ROOT/'A4_electronics_recovery_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    md = [
        '# Light Block A4 — electronics recovery audit',
        '',
        'The recovered A4 electronics selection is internally consistent. The A4.1 continuation makes one component substitution: active TDK SPM4020T-4R7M-LR / C694586 replaces the Würth inductor for the integrated prototype design, while Würth remains the fallback. This audit preserves the original A4 history and separates the A4.1 decision. It is an engineering selection, not a released PCB.',
        '',
        '## Verified results',
        '',
        '- 29 distinct JLC C-codes and 76 fitted parts per complete module, including the remote power adapter. The electronic subset audited here is 24 types / 66 parts.',
        '- All 29 MPNs, codes, saved stock counts, pre-purchase quantities and price-tier schedules match their recovered snapshots.',
        '- **Selected A4.1:** $9.6312 per module for one planned module, $8.6171 for ten, and $6.4997 for one hundred. The unchanged A4 list at fresh prices would be $10.9847 / $9.8200 / $7.5283; its recovered historical prices reproduce $10.9733 / $9.8095 / $7.5200. These are fitted-component calculations; PCB, assembly, attrition, minimum buys, cables, exterior, freight and taxes are additional.',
        '- Independent six-resistor CV corner calculation matches the recovered results within 1e-12 V. This calculation excludes amplifier/ADC errors, diode leakage, contamination, temperature drift and transients.',
        '- 68 kOhm +/-1% gives approximately 343.319–439.435 mA current limit, nominal 388.101 mA, using TI equations. It does not set a safe enclosure temperature.',
        '',
        '## Catalog and quantity dates',
        '',
        'The parent task read all 29 original A4 official JLC product pages in the browser at **2026-11-06 11:30:39–11:33:52 JST**, then the active TDK replacement at **11:37:37 JST**, including current stock, Available Order Qty and every displayed price tier. All selected A4.1 stock and Available Order Qty values cover 100 fitted modules before attrition. The selected list has a minimum Available Order Qty of 719 TDK inductors, followed by 987 toggles. The alternate Würth has 431. Neither field is reserved inventory or a promise of final PCBA allocation.',
        '',
        'The child separately reopened nineteen electronics catalog pages and confirmed four through indexed official listings. Its C23138 text extraction failed, but the parent successfully read that live product page. The ledger preserves both routes. Original observations from 2026-11-06 05:15–05:33 JST remain historical records; the new values have their own timestamps.',
        '',
        'The 76 fitted pieces come from the recovered reference-design allocation, with component roles and reference designators retained in the ledger. This is not a completed native schematic/netlist export; final design closure can change quantities.',
        '',
        '## Selected A4.1 decisions',
        '',
        '| Function | A4.1 choice | Reason |',
        '|---|---|---|',
        '| MCU | STM32G031G8U6TR / C5270180 | Keep the specified 4 mm controller, clock and pin plan. |',
        '| Eight RGB LEDs | WS2812B-2020-V6 / C52917434 | Standard Only, High difficulty, MSL5 remains true on FR-4. |',
        '| LED fault switch | TPS2552DBVR-1 / C140331 | Keeps latch-off; active-low EN is driven through MMBT3904 / C20526. |',
        '| Level conversion | SN74LVC2T45DCUR / C15741 | Retains Ioff and supply isolation for switched LED power. |',
        '| Buck inductor | SPM4020T-4R7M-LR / C694586 | Active 4.7 µH ±20%, maximum 4.6×4.3×2.0 mm envelope. Lower cost and sufficient observed stock; exact lands and hot fault checks remain. Würth retained as fallback. |',
        '| Passives | Recovered Basic 0603/0805/1206 list | Quantity and value changes are accounted for; MLCC effective-capacitance gates remain. |',
        '',
        '## One added firmware requirement',
        '',
        '**A reset can clear the power-switch fault latch.** TI specifies latch reset by toggling EN or cycling switch power. In the selected circuit, MCU reset deasserts EN through the NPN. A boot routine that always enables LEDs would therefore retry an earlier fault. The firmware specification should keep watchdog/software-reset startup dark until its deliberate recovery condition, and prohibit an automatic retry loop. A stronger promise that a fault persists across every MCU reset requires explicit retained-state handling or a revised circuit. That behavior has not been implemented or tested.',
        '',
        '## Electrical gates carried forward',
        '',
        '- Close the BAS70-04 ADC negative-voltage/injection and unpowered-backfeed review. A 0.41 V bound at 1 mA and 25 C does not prove a -0.3 V pin bound at every condition.',
        '- Check effective MLCC capacitance at 12 V, 5 V and 3.3 V, plus final buck current loops and heat. Nominal capacitance and catalog voltage ratings are insufficient alone.',
        '- Preserve passive IN-to-THRU continuity and the high-impedance sense branch. The normal DC transfer calculation is not proof of ESD or unpowered behavior.',
        '- Complete the native schematic, actual footprints and routing, ERC/DRC, firmware, final assembler acceptance, and integrated electrical/thermal measurements.',
        '- For the new TDK inductor, use its exact land pattern and check startup plus upstream/downstream shorts at operating extremes. At 12→5 V, 1.1 MHz, nominal 0.4 A load gives 0.682 A peak and 0.432 A RMS, but 3.5 A typical saturation does not establish a guaranteed hot margin above the buck 3.1 A maximum current limit. Full comparison and sources are in TDK_SPM4020T_4R7M_LR_evaluation.md/json.',
        '',
        '## Primary references',
        '',
    ]
    for s in MANUFACTURER_SOURCES:
        md.append(f"- [{s['id']}]({s['url']}): {s['supports']}")
    md.extend(['','The JSON companion contains the complete component ledger, exact preserved quantity timestamps, tool references, comparison results and derived numbers.',''])
    (ROOT/'A4_electronics_recovery_audit.md').write_text('\n'.join(md))
    print(json.dumps(result['summary'],ensure_ascii=False))
    print('Wrote',ROOT/'A4_electronics_recovery_audit.json')
    print('Wrote',ROOT/'A4_electronics_recovery_audit.md')

if __name__=='__main__':
    main()
