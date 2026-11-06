# Light Block A4 — IC/LED procurement audit

**Observed 2026-11-06 JST. Engineering selection inputs; no purchase, reservation or manufacturing release. A3 remains unchanged.**

## Recommended component baseline

Keep the G031 MCU, 2020 V6 LEDs, AP63205 buck, TLV75533 LDO, LVC2T45 translator, OPA197 and low-profile Würth inductor. Replace the thin-stock active-high TPS2553-1 with the stocked active-low TPS2552-1 plus a Basic MMBT3904 inverter. Specify Diodes BAS70-04-7-F as the exact clamp candidate; its remaining electrical qualification is stated below.

Prices are USD component prices at the observed quantity tier. The 10-module example uses 80 LEDs and 20 rail diodes, not the first-unit tier for every row. Stock screening uses 100 modules; neither quantity is an authorized order.

| Function / MPN | JLC code | Qty/module | In stock / pre-purchase qty | Library; PCBA | First tier | Unit price for 10 modules |
|---|---|---:|---:|---|---:|---:|
| MCU: STM32G031G8U6TR | [C5270180](https://jlcpcb.com/partdetail/STMicroelectronics-STM32G031G8U6TR/C5270180) | 1 | 4,522 / 3,751 | Extended; Economic and Standard | $1.7450 | $1.4702 |
| RGB LED: WS2812B-2020-V6 | [C52917434](https://jlcpcb.com/partdetail/Worldsemi-LED/C52917434) | 8 | 771,294 / 749,286 | Extended; Standard Only | $0.0915 | $0.0736 |
| 5 V buck: AP63205WU-7 | [C2071056](https://jlcpcb.com/partdetail/AP63205WU-7/C2071056) | 1 | 20,691 / 17,987 | Extended; Economic and Standard | $0.4612 | $0.3647 |
| 3.3 V LDO: TLV75533PDBVR | [C404027](https://jlcpcb.com/partdetail/TexasInstruments-TLV75533PDBVR/C404027) | 1 | 95,151 / 93,956 | Extended; Economic and Standard | $0.1216 | $0.1216 |
| Active-low LED latch: TPS2552DBVR-1 | [C140331](https://jlcpcb.com/partdetail/TexasInstruments-TPS2552DBVR1/C140331) | 1 | 2,336 / 2,329 | Extended; Economic and Standard | $0.5741 | $0.4579 |
| Reset-safe latch enable inverter: MMBT3904(RANGE:100-300) | [C20526](https://jlcpcb.com/partdetail/21237-MMBT3904/C20526) | 1 | 2,740,706 / 2,620,840 | Basic; Economic and Standard | $0.0116 | $0.0116 |
| Two-channel LED level translator: SN74LVC2T45DCUR | [C15741](https://jlcpcb.com/partdetail/TexasInstruments-SN74LVC2T45DCUR/C15741) | 1 | 91,323 / 90,009 | Extended; Economic and Standard | $0.2079 | $0.2079 |
| CV input amplifier: OPA197IDBVR | [C221351](https://jlcpcb.com/partdetail/TexasInstruments-OPA197IDBVR/C221351) | 1 | 80,652 / 80,360 | Extended; Economic and Standard | $0.8422 | $0.6983 |
| Reverse-polarity rail diode: PMEG4010CEJ,115 | [C50704](https://jlcpcb.com/partdetail/PMEG4010CEJ%2C115/C50704) | 2 | 14,151 / 14,038 | Extended; Economic and Standard | $0.3678 | $0.3678 |
| ADC clamp, exact manufacturer choice: BAS70-04-7-F | [C134375](https://jlcpcb.com/partdetail/DiodesIncorporated-BAS70_04_7F/C134375) | 1 | 6,783 / 6,654 | Extended; Economic and Standard | $0.0723 | $0.0723 |
| 4.7 uH low-profile buck inductor: 74437324047 | [C2651179](https://jlcpcb.com/partdetail/WurthElektronik-74437324047/C2651179) | 1 | 438 / 431 | Extended; Economic and Standard | $1.7319 | $1.5814 |

The listed core components total **$6.3103 per module** in the 10-module example ($63.1030 for ten), before every resistor/capacitor, connector, switch, jack, cable and manufacturing charge. This is not an assembled-module quotation.

All baseline parts cover 100 modules at their observed stock and pre-purchase counts, before attrition. The smallest baseline inventory is the Würth inductor: 438 stock /431 pre-purchase, for 100 fitted units. Original TPS2553DBVR-1 C111738 had **21 stock /0 pre-purchase**, which fails this supply screen. Zero pre-purchase quantity alone does not mean no parts could be allocated to an SMT order.

**The 2020 LED is explicitly Standard Only, High assembly difficulty, MSL5.** An otherwise Economic-compatible FR4 board does not remove those product-specific flags. The larger MINI-V6 is also Standard Only. Exact processing charges require an actual reviewed quote.

## Reset-safe latch enable: exact change

Use TPS2552DBVR-1 C140331, retaining the latch-off suffix. DBV pins: 1=IN, 2=GND, 3=active-low EN, 4=active-low open-drain FAULT, 5=ILIM, 6=OUT. Use MMBT3904(RANGE:100-300) C20526: 1=base, 2=emitter, 3=collector. Connect MCU PA5 through 10kΩ to base; base through 100kΩ to GND; emitter to GND; collector to EN; EN through 100kΩ to unswitched5V. MCU high then enables LEDs. Reset or loss of MCU power leaves the transistor off and EN high, keeping LEDs off without a direct5V pull-up on a MCU pin.

The enable network needs **one10kΩ C25804 and two100kΩ C25803**. Reuse A3 R12 as the base pull-down: the net addition versus A3 is **one10kΩ and one100kΩ**, plus the transistor. At3.3V and assumed VBE=.7V, series base current is260µA, approximately253µA after the base pull-down; EN pull-up requires at most50µA plus its0.5µA leakage. The NPN has ample overdrive. Manufacturer VCE(sat) is .3V maximum at50mA/5mA, below TI’s .66V minimum enable transition; this is design reasoning, not a measured cold-corner result. [TI TPS255xx](https://www.ti.com/lit/ds/symlink/tps2553.pdf), [JSCJ MMBT3904](https://www.jscj-elec.com/gallery/file/MMBT3904%20SOT-23V2.pdf).

Use68kΩ±1% C23231 for ILIM. TI equations give approximately343.3mA minimum,388.1mA nominal and439.4mA maximum including resistor corners. This retains the A3 intent with a Basic value. Keep FAULT handling latched rather than automatically retrying. This current limit cannot substitute for enclosure-temperature testing.

2N7002 C8545 is Basic, plentiful and cheap, but its JSCJ RDS(on) limits are specified at5V/10V. A threshold-voltage specification is insufficient to claim a guaranteed3.3V low-resistance switch. The NPN is the clearer choice for this tiny enable current.

## Alternatives and why they are not automatic substitutions

| Alternative | Stock / pre-purchase | First unit | Assessment |
|---|---:|---:|---|
| [STM32C031G6U6TR /C7324966](https://jlcpcb.com/partdetail/STMicroelectronics-STM32C031G6U6TR/C7324966) | 847 / 729 | $1.1628 | 32KB/12KB,48MHz versus G03164KB/8KB,64MHz; lower cost, but explicit clock/ADC/pin/firmware review and smaller inventory. |
| [WS2812B-MINI-V6 /C52941386](https://jlcpcb.com/partdetail/Worldsemi-LED/C52941386) | 4,962 / 3,844 | $0.1067 | Thicker1.9mm package and higher LED unit price; still Standard Only. |
| [MWSA0402S-4R7MT /C408337](https://jlcpcb.com/partdetail/Sunlord-MWSA0402S_4R7MT/C408337) | 39,714 / 38,019 | $0.1498 | 2mm high4.7µH, but listed3A saturation leaves weak margin against3.1A buck peak limit; exact manufacturer limits not fully retrieved. |
| [SWPA4030S4R7MT /C57269](https://jlcpcb.com/partdetail/Sunlord-SWPA4030S4R7MT/C57269) | 33,947 / 33,101 | $0.0570 | 3mm high4.7µH;2.9A minimum saturation, not3.2A guaranteed. Geometry and hot fault review required. |
| [SWPA4030S2R2NT /C279948](https://jlcpcb.com/partdetail/Sunlord-SWPA4030S2R2NT/C279948) | 12,069 / 11,920 | $0.0589 | 3mm high2.2µH;4.9A minimum saturation is promising, but changes inductance, ripple and placement. |
| [B5819W SL /C8598](https://jlcpcb.com/partdetail/9093-B5819WSL/C8598) | 792,668 / 664,296 | $0.0262 | Basic40V/1A Schottky; larger SOD123 and1mA maximum reverse leakage at40V/25°C change the protection review. |
| [TLV171IDBVR /C2864299](https://jlcpcb.com/partdetail/TexasInstruments-TLV171IDBVR/C2864299) | 303 / 249 | $1.2315 | Costs more than OPA197 and only303 stock; reject for stock/cost goal. |
| [BAS70-04-QR /C7507542](https://jlcpcb.com/partdetail/Nexperia-BAS70_04QR/C7507542) | 0 / 0 | $0.1250 | Zero stock/zero pre-purchase. Price is only a displayed estimate, not stocked availability. |
| [WS2812B-MINI-V3/W /C527089](https://jlcpcb.com/partdetail/Worldsemi-WS2812B_MINI_V3W/C527089) | 0 / 12 | $0.1242 | Zero stock with12 pre-purchase field: inconsistent; do not rely on it. |

### Inductor tradeoff and corrected geometry

The A3 inductor reservation is2.0mm body +.1mm solder, not3.4mm free height. Keep Würth74437324047 in the baseline: its observed price is$1.5814 at10 or$1.3296 at100. A3’s low-profile fit is useful; the actual layout remains unverified.

Sunlord SWPA4030S2R2NT is a meaningful cost alternative at$.0589 first tier. The manufacturer lists2.2µH±30%,39mΩ maximum DCR,4.9A minimum/5.8A typical saturation and2.95A minimum heat rating, at20°C reference conditions; saturation means approximately30% inductance loss. AP63205 permits nominal2.2–10µH. At12V→5V,1.1MHz, ideal CCM ripple is1.205A for2.2µH versus.564A for4.7µH; at.5A load the corresponding nominal peaks are1.103A and.782A. These calculations do not establish startup, EMI, hot-short or DCM performance. [Sunlord primary table, PDFp8](https://www.sunlordinc.com/uploads/files/20221122/SWPA%20series%20of%20SMD%20Power%20Inductor.pdf), [Diodes AP63205](https://www.diodes.com/assets/Datasheets/AP63200-AP63201-AP63203-AP63205.pdf).

Both SWPA4030 candidates have4.0±.2mm square bodies and3.0mm maximum height. The proposed A4 controllerfrontZ12.3 and1.6mm board put its back atZ13.9. Retained Würth plus solder reachesZ16.0; root proposes moving the LED board fromZ16…26 toZ17…27, providing1mm nominal separation. Full A4 CAD is unverified. A3.1mm mounted SWPA instead reachesZ17.0 and would need a further change such as LEDboardZ18…28. Neither cheap alternative is a mechanical drop-in. The cheaper4.7µH SWPA also has only2.9A minimum saturation, below the buck’s3.1A maximum peak-current limit. Würth is the confirmed main-BOM choice;2.2µH remains a separate cost/placement/power alternative.

### LEDs, level translation and optical board construction

Keep8×WS2812B-2020-V6. The official2020 body is2.20×2.00×.84mm nominal, with general±.15mm tolerance; mounted outward reservation remains1.10mm. Worldsemi MINI-V6 V1.3 p2 instead calls out3.46±.5mm and1.9mm (+0/−.1) height, with3.5mm pad span. Its thinner-looking product photographs do not make it a fit replacement. [2020 official datasheet](https://www.world-semi.com/downloads/datasheets/en/ws2812b-2020-v6-1.0.pdf), [MINI official datasheet](https://www.world-semi.com/downloads/datasheets/en/ws2812b-mini-v6-1.0.pdf).

Keep the two-channel SN74LVC2T45: VCCA=3V3, VCCB=switchedVLED, DIR=A→B. It supports two4-pixel leaves, or one8-pixel chain with the unused input tied to GND and unused output unconnected. Its specified rail isolation/Ioff matters during LED power shutdown. The reviewed single-supply SN74LV1T34 did not supply a clear Ioff guarantee; it is not selected merely to save a small amount. [TI LVC2T45](https://www.ti.com/lit/ds/symlink/sn74lvc2t45.pdf).

One double-sided rigid strip versus two identical single-sided rigid leaves remains a mechanical/assembly choice outside this IC audit. Rigid FR4 avoids the uncertain international transparentPET assembly route; it does not alter the selected LED’s Standard-only flag. Keep the same electronics across2HP/3HP where the final placement allows. Build the complete integrated module first; no separate optical PCB order is required.

Eight LEDs at the12mA/channel reference imply288mA and1.44W of LED-rail input at full white, not a guaranteed current maximum. A20%firmware ceiling gives approximately57.6mA of that reference and only0…51 codes per8bit channel. Retain full-white fault-temperature and low-fade checks on the assembled module; do not promise the firmware ceiling alone controls heat.

## Protection and remaining electrical work

Final main-BOM selection is2×PMEG4010CEJ,115 C50704. Its14,151 observed JLC stock and14,038 pre-purchase quantity comfortably cover200 fitted diodes in100 modules. Nexperia specifies50µA maximum leakage at40V/25°C and570mV maximum forward drop at1A/25°C. The cheaper Basic B5819W SL C8598 is40V/1A, but specifies1mA maximum leakage at40V/25°C and a larger SOD123 package, up to3.85×1.70×1.25mm. It stays outside the main BOM. Reverse-rail/fuse/surge behavior still needs a completed circuit review for either choice. [Nexperia PMEG4010CEJ](https://assets.nexperia.com/documents/data-sheet/PMEG4010CEJ.pdf), [JSCJ B5819W](https://www.jscj-elec.com/gallery/file/B5819W%20SOD-123%20V2.0.pdf).

Diodes BAS70-04-7-F C134375 resolves the exact clamp procurement part. Its100nA maximum reverse current at50V/25°C and410mV maximum forward voltage at1mA/25°C are confirmed. Neither value guarantees the MCU ADC remains above−.3V under a cold fault. Final diode pin-symbol mapping, negative injection, power-off backfeed and rail absorption still need closure. Keep the passive THRU and20MΩ nominal pickup, with the A3 mapping VADC=V3V3/2+CV/8. Root’s Basic1% resistor/capacitor audit supplies the exact passive selection and calibration analysis. [Diodes BAS70 family](https://www.diodes.com/_files/datasheets/ds11007.pdf).

Mechanical audit selects Dailywell1MS3T1B1M2QES-5 C908270. Its Q suffix denotes silver contacts; no guaranteed minimum dry-circuit load has been established for the existing10kΩ MCU pull-ups. Keep the stocked selection, but include contact-state reliability and debounce in the integrated prototype evaluation. Factory solder-tail trimming must follow the final board clearance. No extra optical-board order is required by this note.

## Evidence and release status

The JSON contains every audited price tier, timestamps,100-module stock coverage, selected-code list, enable-passive delta, source URLs and file hashes. `ic_led_evidence` retains raw public HTML and sanitized snapshots; `manufacturer_evidence` contains the successfully retrieved primary PDFs and package images. Some manufacturer-download endpoints returned403; these failures are not treated as successful reads. Manufacturer facts used above came from accessible primary content, with unresolved values labeled.

In JLC’s public page code, overseasStockCount maps to “In Stock”, while canPresaleNumber maps to “Available Order Qty” for pre-purchase. These are different because some parts are reserved for SMT allocation. No logged-in cart, vendor contact, reservation or order was performed. All counts are dynamic.

Before manufacturing, finish the native schematic, actual footprints and routed boards; runERC/DRC; close the stated protection and power checks; and verify exact JLC BOM/CPL matching, placement rotations, attrition and the Standard assembly quote. This audit does not imply those steps have occurred.
