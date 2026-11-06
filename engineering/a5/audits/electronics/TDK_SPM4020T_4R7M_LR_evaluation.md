# A4.1 inductor cost-down decision

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
