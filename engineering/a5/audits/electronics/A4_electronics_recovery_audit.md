# Light Block A4 — electronics recovery audit

The recovered A4 electronics selection is internally consistent. The A4.1 continuation makes one component substitution: active TDK SPM4020T-4R7M-LR / C694586 replaces the Würth inductor for the integrated prototype design, while Würth remains the fallback. This audit preserves the original A4 history and separates the A4.1 decision. It is an engineering selection, not a released PCB.

## Verified results

- 29 distinct JLC C-codes and 76 fitted parts per complete module, including the remote power adapter. The electronic subset audited here is 24 types / 66 parts.
- All 29 MPNs, codes, saved stock counts, pre-purchase quantities and price-tier schedules match their recovered snapshots.
- **Selected A4.1:** $9.6312 per module for one planned module, $8.6171 for ten, and $6.4997 for one hundred. The unchanged A4 list at fresh prices would be $10.9847 / $9.8200 / $7.5283; its recovered historical prices reproduce $10.9733 / $9.8095 / $7.5200. These are fitted-component calculations; PCB, assembly, attrition, minimum buys, cables, exterior, freight and taxes are additional.
- Independent six-resistor CV corner calculation matches the recovered results within 1e-12 V. This calculation excludes amplifier/ADC errors, diode leakage, contamination, temperature drift and transients.
- 68 kOhm +/-1% gives approximately 343.319–439.435 mA current limit, nominal 388.101 mA, using TI equations. It does not set a safe enclosure temperature.

## Catalog and quantity dates

The parent task read all 29 original A4 official JLC product pages in the browser at **2026-11-06 11:30:39–11:33:52 JST**, then the active TDK replacement at **11:37:37 JST**, including current stock, Available Order Qty and every displayed price tier. All selected A4.1 stock and Available Order Qty values cover 100 fitted modules before attrition. The selected list has a minimum Available Order Qty of 719 TDK inductors, followed by 987 toggles. The alternate Würth has 431. Neither field is reserved inventory or a promise of final PCBA allocation.

The child separately reopened nineteen electronics catalog pages and confirmed four through indexed official listings. Its C23138 text extraction failed, but the parent successfully read that live product page. The ledger preserves both routes. Original observations from 2026-11-06 05:15–05:33 JST remain historical records; the new values have their own timestamps.

The 76 fitted pieces come from the recovered reference-design allocation, with component roles and reference designators retained in the ledger. This is not a completed native schematic/netlist export; final design closure can change quantities.

## Selected A4.1 decisions

| Function | A4.1 choice | Reason |
|---|---|---|
| MCU | STM32G031G8U6TR / C5270180 | Keep the specified 4 mm controller, clock and pin plan. |
| Eight RGB LEDs | WS2812B-2020-V6 / C52917434 | Standard Only, High difficulty, MSL5 remains true on FR-4. |
| LED fault switch | TPS2552DBVR-1 / C140331 | Keeps latch-off; active-low EN is driven through MMBT3904 / C20526. |
| Level conversion | SN74LVC2T45DCUR / C15741 | Retains Ioff and supply isolation for switched LED power. |
| Buck inductor | SPM4020T-4R7M-LR / C694586 | Active 4.7 µH ±20%, maximum 4.6×4.3×2.0 mm envelope. Lower cost and sufficient observed stock; exact lands and hot fault checks remain. Würth retained as fallback. |
| Passives | Recovered Basic 0603/0805/1206 list | Quantity and value changes are accounted for; MLCC effective-capacitance gates remain. |

## One added firmware requirement

**A reset can clear the power-switch fault latch.** TI specifies latch reset by toggling EN or cycling switch power. In the selected circuit, MCU reset deasserts EN through the NPN. A boot routine that always enables LEDs would therefore retry an earlier fault. The firmware specification should keep watchdog/software-reset startup dark until its deliberate recovery condition, and prohibit an automatic retry loop. A stronger promise that a fault persists across every MCU reset requires explicit retained-state handling or a revised circuit. That behavior has not been implemented or tested.

## Electrical gates carried forward

- Close the BAS70-04 ADC negative-voltage/injection and unpowered-backfeed review. A 0.41 V bound at 1 mA and 25 C does not prove a -0.3 V pin bound at every condition.
- Check effective MLCC capacitance at 12 V, 5 V and 3.3 V, plus final buck current loops and heat. Nominal capacitance and catalog voltage ratings are insufficient alone.
- Preserve passive IN-to-THRU continuity and the high-impedance sense branch. The normal DC transfer calculation is not proof of ESD or unpowered behavior.
- Complete the native schematic, actual footprints and routing, ERC/DRC, firmware, final assembler acceptance, and integrated electrical/thermal measurements.
- For the new TDK inductor, use its exact land pattern and check startup plus upstream/downstream shorts at operating extremes. At 12→5 V, 1.1 MHz, nominal 0.4 A load gives 0.682 A peak and 0.432 A RMS, but 3.5 A typical saturation does not establish a guaranteed hot margin above the buck 3.1 A maximum current limit. Full comparison and sources are in TDK_SPM4020T_4R7M_LR_evaluation.md/json.

## Primary references

- [TI-TPS255X](https://www.ti.com/lit/ds/symlink/tps2553.pdf): Active-low TPS2552-1 latch-off function, EN limits, EN/power reset of fault latch, ILIM equations.
- [TI-LVC2T45](https://www.ti.com/lit/ds/symlink/sn74lvc2t45.pdf): Dual-rail supply range, VCCA-referenced DIR, Ioff and isolation when a supply is grounded.
- [TI-TLV755](https://www.ti.com/lit/ds/symlink/tlv755p.pdf): 3.3 V regulator choice and need to qualify output capacitance.
- [DIODES-AP63205](https://www.diodes.com/assets/Datasheets/AP63200-AP63201-AP63203-AP63205.pdf): 5 V/1.1 MHz buck; recommended 4.7 uH, 10 uF input, 2x22 uF output, 100 nF bootstrap; 3.1 A maximum high-side peak limit.
- [DIODES-BAS70](https://www.diodes.com/_files/datasheets/ds11007.pdf): Exact BAS70-04-7-F order code; 0.41 V maximum at 1 mA/25 C is not a guaranteed -0.3 V clamp.
- [ST-G031](https://www.st.com/resource/en/datasheet/stm32g031f8.pdf): G031 architecture, separate pin voltage and current injection constraints, UFQFPN28 package.

The JSON companion contains the complete component ledger, exact preserved quantity timestamps, tool references, comparison results and derived numbers.
