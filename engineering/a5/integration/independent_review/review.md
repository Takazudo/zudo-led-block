# Independent A5 CV and reset review

**Status:** C13 relocation verified in XML. Review is analytical and based on the actual exported controller XML; no hardware or firmware tests were rerun.

## Findings

1. **C13 discharge path:** The original XML puts10nF C13 directly on U7IN+, downstream of R7. Its initial stored charge therefore bypasses R7. The approved fix moves C13 toCV_AFFINE upstream of R7, with D3/U7IN+ remaining atCV_FILTER. DC gain stays unchanged; nominal pole changes from740 to776Hz. Current XML relocation verified: **True**. For the defined normal precharge envelope (CV±5V, VDD3.0–3.6V, six front-end resistors±1%), C13≤2.44335V. With R7≥990Ω and CV_FILTER≥−0.5V, that path is bounded to2.974mA, below TI's10mA overdrive limit. This is a conditional path bound, not arbitrary transient qualification.

2. **Powered-off claim:** Under explicit discharged-capacitor/inactive-rail assumptions, a forced CV_BUF disturbance of±20V gives20/81.18kΩ=246.37µA. If all of it flows through a1010Ω shunt, its voltage is≤0.24883V. An additional conservative20V/9.9MΩ allowance gives0.25087V. The ordinary R1 path is upstream of R3, so this extra allowance is not a predicted independent current. Do not describe this as an unpowered-output specification for TLV9001 or proof of every U7/MCU terminal limit. U7 operation below1.8V, differential-input voltage, supply absorption and negative ADC transients remain physical/vendor qualification gates.

3. **Partial supply loss:** TLV755P§7.1.4 warns about reverse current when its charged output exceeds input by0.3V. The XML contains no explicit reverse-current bypass/protector. Measure or resolve a rapid5V collapse separately from the low-current CV argument. Supply-capacitor energy is outside that DC calculation.

4. **Reset claim:** Firmware/electrical mapping and retained-domain lockout match. However, the TPS2552-1 can clear its hardware latch on its own supply cycle; its overcurrent FAULT has7.5ms typical deglitch. A5 has no independent5V-valid monitor. A5 therefore cannot claim that every5V-only sag/recovery is inhibited before software observes a fault, even if the MCU backup domain survives. Keep the documented deep-collapse limitation and add this partial-rail test case. Check factory boot/SWD/NRST and BOR option bytes without silently changing them.

## Normal CV mapping verified

The XML implements VADC=(100/133)×(VDD/2+CV/8), matching firmware. Resistor-only corners at VDD=3.3V are:

| CV | Nominal ADC | Minimum ADC | Maximum ADC |
|---:|---:|---:|---:|
| -5V | 0.770677V | 0.745090V | 0.796347V |
| +0V | 1.240602V | 1.222070V | 1.259194V |
| +5V | 1.710526V | 1.688790V | 1.732270V |

These corners independently vary R1,R2,R3–R6,R24,R25 by±1% and assume ideal followers. The worst endpoint error under nominal firmware inversion is approximately0.273V input-equivalent before calibration; the inherited A4.1≈0.233V figure is not an A5 bound. Opamp, ADC, reference, temperature and dynamic errors are excluded.

## Physical pixel orientation

The electronics integration reports that the right identical leaf is mounted end-for-end. Its wire indices D1–D4 therefore run opposite the left leaf in physical vertical space. Current defaults are uniform within each chain, so no source change is needed. Future patterns that align vertical positions should map right index = 3 − left index.

## Evidence

- [TI TLV9001, SBOS833R](https://www.ti.com/lit/ds/symlink/tlv9001.pdf): 7.1 absolute maximum input limits; 10.1 input/ESD protection:current limited to10mA; 10 supply range1.8..5.5V.
- [TI TLV755P, SBVS320D](https://www.ti.com/lit/ds/symlink/tlv755p.pdf): 7.1.4 reverse current; VOUT>VIN+0.3V.
- [TI TPS255x, SLVS841G](https://www.ti.com/lit/ds/symlink/tps2552-1.pdf): 8.3.1 overcurrent/latch; 8.3.3 FAULT deglitch and latch clearing; 8.3.4 UVLO.
- [ST DS12992 Rev4](https://www.st.com/resource/en/datasheet/stm32g031g8.pdf): Table18 input minimum-0.3V; Table19 injection current; 3.7.1 VBAT bonding; pin/AF table.
- [TI SN74LVC2T45, SCES516N](https://www.ti.com/lit/ds/symlink/sn74lvc2t45.pdf): 7.3.5 glitch-free sequencing; 7.3.6 isolation when either supply isGND.

Exact input/document hashes, calculations and finding status are in`review.json`. No electronics or firmware source was modified by this review.

## Earlier placement followup (superseded by bridge revision)

Controller J3 moved from (4.4, 10.5) to (4.4, 12.0) mm, remaining on B at 0°. Reversing only that XY literal reproduces the exact previously reviewed design_data.py SHA-256, proving all other source bytes are unchanged. The active placement override agrees, contains only placement/note fields, and leaves J4 at (4.4, 34.0) mm. The reviewed controller XML, procurement data, and firmware source/document hashes remain unchanged. That earlier placement-only design_data.py SHA-256: `d413a55f1ec31b09c6d79f11ab7cd79923a962221f89b063db300b2ec2878fb2`. This is a change-scope check; it does not qualify physical clearance or routing. No firmware test suite was rerun.

## Final bridge architecture followup

The later connector revision deliberately supersedes the earlier placement-only state. Review of the final exported controller, leaf, and power-adapter XML found no wiring or firmware mismatch. Controller J4 is removed. Controller J3 pins 1/2/3/4 are GND/VLED/DATA_L/DATA_R. The two existing 1:1 SH4 cables connect controller J3 → left J1 and left J2 → right J1; right J2 remains unused.

| Stream | Path to the first LED | Final LED output |
|---|---|---|
| Left | PA6/TIM3_CH1 → U5 A1/B1 → R14 → controller J3.3 → left J1.3 → left D1 DIN | Left D4 DOUT unconnected |
| Right | PA7/TIM3_CH2 → U5 A2/B2 → R15 → controller J3.4 → left J1.4 → left J2.3 → right J1.3 → right D1 DIN | Right D4 DOUT unconnected |

Instantiating the identical leaf twice and joining only the specified cable pins gives distinct left/right DIN nets. Each local chain remains four LEDs; the bridge does not use left D4 DOUT. Cable 2 pin 4 returns the left input stream to right J1.4/right J2.3 as an intentionally unloaded branch. Right J2.4 is a local branch of the right input stream. Use the specified INPUT/BRIDGE ports, verify purchased cable pin continuity, and leave right J2 unconnected. Waveform quality on the actual longer right path and left-data stub remains a hardware check.

VLED and GND trace from U4 through both cables to all eight LEDs. Cable 1 carries the aggregate load of both leaves; cable 2 carries the right leaf. The common limiter and fault response blank both chains. With R11=68kΩ±1%, the cached TI equations give a DC current-limit threshold range of approximately **343–439mA**. This is not an instantaneous-current bound: stored VLED capacitance and protection response can produce separate transients. [TI TPS255x](https://www.ti.com/lit/ds/symlink/tps2552-1.pdf), §8.5.1 and §9.2.1.2.3.

[JST SH](https://www.jst-mfg.com/product/pdf/eng/eSH.pdf) specifies **1.0A with AWG28**. This does not certify the exact third-party harness, its crimps, bend life, or voltage drop. Qualify the actual assembly at both-leaf load and during startup/short-circuit tests. The 20% command-code cap is not a measured load-current guarantee.

The exported fitted count is **59 controller + 10×2 leaf + 2 adapter = 81**, including five SH4 headers and 30 procurement types. C13 remains at CV_AFFINE upstream of R7; the buffered A5 ADC gain and all previous partial-power/reset qualifications are unchanged. MCU PA0/PA2/PA3/PA4/PA5/PA6/PA7 and SWD/testpad net identities remain consistent. Existing firmware documents have no obsolete controller-J4 or pin4-NC wording. The finalized ELF/HEX/BIN/MAP hashes and firmware source-manifest hash still match their recorded release identities. No firmware tests were rerun, and no firmware code or binary was modified.

Current input hashes, all joined stream endpoints, cable pin maps, and the preceding review identities are recorded in `review.json`.

## Schematic presentation followup

The final native re-export moves the leaf power flags from Y220 to Y240 to clear the new J2 label. Root integration compared all pin memberships and component ref/value/footprint identities to its captured pre-layout graphs: all three boards are equivalent, as recorded in `integration/leaf_layout_equivalence.json`. The review input hashes now identify those regenerated XML files, and their bytes match the equivalence report. All other reviewed source, procurement, and firmware inputs remain unchanged.

## Final harness routing status

The authoritative `mechanical/verification_summary.json` reports **rejected current cable/ribbon routing scenarios** for both variants. Complete harness routing remains open, and installed assembly fit is not approved. The retained rigid-part CAD has zero modeled intersections; each variant still has **16 conditional cable/ribbon interferences**.

| Saved route group | Sampled minimum bend-radius range, both variants |
|---|---:|
| Controller → left leaf | approximately 1.07–1.53 mm |
| Left → right leaf bridge | approximately 0.20–0.28 mm |
| Power cable | approximately 1.05 mm |

These are measurements of the rejected saved scenarios. The electrical bridge connectivity and the structural checks of the seven-part 3MF plates remain valid within their stated scopes. No feasible full harness route, installed fit, PETG process, or manufacturing release is established. CAD, firmware and 3MF artifacts were not changed for this documentation update.
