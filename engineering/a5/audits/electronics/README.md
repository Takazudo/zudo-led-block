# Electronics audit collateral

The current **A4.1 prototype design selects TDK SPM4020T-4R7M-LR / C694586**. Würth 74437324047 / C2651179 is retained as the fallback. The original A4 selection and its quantity observations remain preserved as history. These documents contain research and calculations; they do not report tested hardware or a manufacturing release.

## Files

- `A4_electronics_recovery_audit.md` and `.json`: original snapshot consistency, CV tolerance calculations, current-limit calculation, fresh quantity observations, and the A4.1 selection comparison.
- `TDK_SPM4020T_4R7M_LR_evaluation.md` and `.json`: active versus obsolete TDK decision, dimensional and normal-current comparison, fitted-cost change, and unresolved layout/hot-fault checks.
- `live_jlc_refresh_source.json`: preserved 29-row rendered-page refresh for the original A4 list.
- `inputs/a4_history/`: recovered original A4 procurement list, CV tolerance data and the 29 exact component snapshots used by the consistency check.
- `inputs/live_jlc_refresh.json`: frozen source of the original-list refresh.
- `inputs/tdk_jlc_observation.json`: frozen observation of the active TDK replacement.

The package-root `procurement_rows.json` is the authoritative current A4.1 selection. Both scripts read it. Every other input needed by these audit scripts is inside this directory; no external recovery tree or workspace path is required.

## Regenerate

Use Python 3.9 or later. Only the standard library is required. From the package root:

```sh
python3 audits/electronics/build_recovery_audit.py
python3 audits/electronics/build_tdk_costdown_audit.py
```

The scripts locate inputs relative to their own files, so invocation from another working directory also works. They overwrite only their audit outputs in this directory. They do not change the authoritative procurement list, fetch current inventory, modify the design or place orders. If the authoritative selection or frozen observations change, the fixed A4.1 consistency assertions may fail; review the audit assumptions before regenerating a new revision.

## Observation chronology

| Stage | Observation time | Interpretation |
|---|---|---|
| Recovered A4 | 2026-11-06 05:15–05:33 JST | Original 29-part selection and snapshots, including Würth as primary. |
| Original-list refresh | 2026-11-06 11:30:39–11:33:52 JST | Fresh displayed stock, Available Order Qty and price tiers for all 29 original rows. |
| A4.1 TDK selection | 2026-11-06 11:37:37 JST | Active LR product observation; TDK becomes primary and Würth becomes fallback. |

Output generation timestamps describe when the local calculations were regenerated. They do not replace these inventory observation times. Browser tool references and relative crawl labels are historical provenance; source URLs are included for later checks. Stock and Available Order Qty are different fields and neither reserves inventory.

The copied snapshots include the recovered evidence metadata. Referenced manufacturer documents and raw HTML are not downloaded by these regeneration scripts. Electrical release gates remain explicit, especially ADC/unpowered protection, effective MLCC capacitance, reset behavior of the LED fault latch, exact TDK lands and hot startup/short-circuit performance.
