# Electrical review of the 0.8 mm controller with no ground planes (#87)

Board under review: `engineering/a7/electronics/controller/controller.kicad_pcb`, SHA256
`710ed8019126944272a52fe0b162826c09088d70e363fce3cc184df93e7bab5e` (2158 tracks, 115 vias, one local copper
area, nominal 0.8 mm, JLC04081H-3313 four-layer stackup).

This record replaces the return-path, coupling and shielding conclusions of `interface_review.md`, which were
reached on the old 1.6 mm board with a solid In1 ground plane. No component, pin, firmware or schematic
function changed: the netlist and the authorized delta are the ones already reviewed, and the CV transfer
`VADC = (100/133)*(VDD/2 + CV/8)` is untouched.

Every number below is a **digital DC and geometry screen** of the routed copper
(`scripts/a7_return_review.py`, record in `controller/return-review.json`). It is not a measurement, not an
AC or thermal qualification, and not a manufacturing approval. A7 remains unreleased for manufacture.

## Acceptance margin, and where it comes from

| Allocation | Limit | Acceptance corner | Nominal 20 °C | Resistance headroom from nominal |
|---|---|---|---|---|
| LED-brightness-dependent reference shift | 0.5 ADC LSB | **0.0375 LSB** (30.2 µV) | 0.0239 LSB | 20.9× |
| Combined static DC reference error | 1.0 ADC LSB | **0.265 LSB** (213.8 µV) | 0.1312 LSB | 7.6× |

The acceptance corner is `hot_85C_thin_copper`: 85 °C (the upper ambient rating of the fitted parts) with
copper thickness, track width and barrel plating all at 0.8× nominal. Those tolerances are explicit
**assumptions**; no fabricator tolerance row is retained. Resistance scales every voltage in the model, so
this corner is the acceptance case: at it the two results sit 13.3× and 3.8× under their limits. The last
column is the separate question of how much every resistance on the board could grow from its nominal value
before the allocation is reached.

Derivation of the two allocations:

- one 12-bit code at 3.3 V is 0.806 mV at the ADC pin, i.e. 8.57 mV of CV through the kept inverse
  `CV = 10.64*VADC - 4*VDD` (`engineering/a5/electronics/reports/electrical_margins.json`, `cv_transfer`);
- the firmware CV deadband is ±50 mV with ±5 V full scale (`engineering/a5/firmware/README.md` mode table,
  `LB_CV_DEADBAND_MV` in `engineering/a5/firmware/src/light_block.c`). Half a code is 8.6 % of the deadband
  and one code is 17 %, so neither can move a 0 V input out of the deadband;
- a static offset is removable by the firmware zero calibration (`lb_calibration_t`); an LED-dependent shift
  is not, which is why it gets the tighter half-code allocation.

Excluded from the budget, because they are layout-independent and belong to bench work (#10): power-cable and
connector contact resistance, op-amp offset, ADC/reference error, resistor tolerance and AC noise.

## Return topology: one star pin, four branches, no plane

The two ground systems meet **only at the J5.2 power-connector pin**, and on opposite faces of that plated
pad, so even the pad copper is not shared: the power return owns the F.Cu face, the quiet returns own the
B.Cu face, and the only shared metal is the barrel plating.

The audit over the board's own copper (filled polygons plus a conservative track half-width, with J5.2
removed) finds exactly four components, one of them the whole power system:

| Branch | Face at J5.2 | Pads | Members |
|---|---|---|---|
| power | F.Cu | 19 | C1.2, C2.2, C3.2, C9.2, C10.2, C11.2, C12.1, C15.2, C16.2, J3.1, R11.2, R16.2, R17.2, R18.2, R19.2, R20.2, U2.4, U4.2, U5.4 |
| quiet: MCU, analog island, LDO cluster | B.Cu | 12 | C13.2, C17.2, C5.2, C6.2, C8.2, R2.2, R25.2, R6.2, R8.2, U1.4, U3.2, U7.2 |
| quiet: jack sleeves and mode switch | B.Cu | 7 | J1.1, J1.2, J2.1, J2.2, Q1.2, R12.2, SW1.3 |
| quiet: MCU bulk, CV clamp, test point | B.Cu | 4 | C7.2, C14.2, D3.1, TP2.1 |

Inside the quiet system a 0.6 mm B.Cu trunk runs from the J5.2 pin to the single MCU ground via under U1 at
(2.6, 27.0). The CV/ADC island (R25.2, R6.2, U7.2, C17.2, C13.2) is taken from that via as a Kelvin tap, and
the LDO/bleeder cluster (R8.2, U3.2, C6.2, C5.2, R2.2) hangs on its own spur off the trunk rather than through
the island, so the 3.3 mA bleeder and the LDO's own return current do not flow in the reference copper. The
result is the headline number: **both LED scenarios produce exactly 0 V of weighted reference error**, because
the LED return shares no copper at all with the reference chain.

The only LED-dependent term left is the J5.2 barrel itself, taken conservatively as fully shared by both
branches: 0.731 mΩ at the corner × the 0.439 A TPS2552-1 current-limit bound = 321 µV of shift of the whole
board reference against the patched CV source, which the firmware weight (1/10.64 from CV volts to ADC volts)
turns into 30.2 µV at the ADC pin, i.e. 0.0375 LSB.

Selected measured-from-copper resistances at the acceptance corner (nominal in `return-review.json`):

| Path | Length | Resistance (corner) |
|---|---|---|
| U1.4 → J5.2 (B.Cu face) | 7.66 mm | 13.6 mΩ |
| R25.2 → U1.4 | 12.22 mm | 68.1 mΩ |
| U7.2 → U1.4 | 8.88 mm | 56.9 mΩ |
| C8.2 → U1.4 (MCU decoupling return) | 3.07 mm | 19.2 mΩ |
| C1.2 → J5.2 (F.Cu face, power trunk) | 27.65 mm | 87.8 mΩ |

### Local copper areas: exactly one

| id | net | layer | rectangle (mm) | area | why |
|---|---|---|---|---|---|
| `buck-return-thermal` | `/GND` | B.Cu | (4.0, 0.4) – (8.8, 4.9) | 21.6 mm² | localized return/thermal spreading under U2/C1, tied to the buck ground by the two stitch vias at (5.0, 3.9) and (5.8, 3.9); AP63205 datasheet DS41326 Rev 3-2 p.15 asks for bottom ground copper. It is on the power branch only. |

The plotted Gerbers confirm this is the whole story: exactly one filled region object on any copper layer, and
it is this one. Dark copper coverage inside the 16.2 × 62.9 mm bounds is F.Cu 21.6 %, In1.Cu 10.5 %,
In2.Cu 10.8 %, B.Cu 19.4 % — the former inner planes are gone. The audit in `return-review.json`
(`filled_star_audit`) proves this area touches only power-branch copper (74 contact nodes, 2 vias, no pad and
not the J5.2 pad), so a native refill cannot bridge the two ground systems.

`+3V3` carries its own Kelvin rule: the affine divider taps R4.1 and R5.1 reach the rest of the net only
through C8.1, the MCU decoupling capacitor, so the MCU supply current is not in the reference. With that
topology the taps sit 4.7248 mV below U3.5 while the measured VDDA (U1.3) sits 4.7570 mV below it, and the
firmware weights turn that 32 µV difference into 0.129 mV of CV, i.e. 12.1 µV at the ADC pin. Without the
rule this term alone was 0.42 LSB nominal / 0.83 LSB at the corner in the previous candidate.

## Buck converter loops

| Loop | Pad-centre area | Routed legs | Vias |
|---|---|---|---|
| input (the only discontinuous-current loop) | 3.57 mm² | 0.65 mm VIN + 0.65 mm GND | 0 |
| bootstrap | 1.85 mm² | 0.50 mm + 0.50 mm | 0 |
| output (inductor ripple only) | 7.00 mm² | 1.10 mm SW + 0.55 mm 5 V + 15.71 mm GND | 2 |

`/BUCK_SW` is 1.1 mm of 0.3 mm track with **no vias**, so the switching node never passes through a barrel.
C1 sits directly across U2's VIN/GND pins (1.3 mm loop, 0.51 nH partial-inductance estimate).

The weakest item is the output capacitor's return: C2.2 → U2.4 is 15.71 mm with two through vias
(49.3 mΩ at the corner) instead of the 8.9 mm straight line, because L1 and the parts between C2 and U2 block
the direct corridor and the placement is authoritative. This leg carries only the triangular inductor ripple
and the IC's quiescent current — the LED load current closes locally at C2 — so it adds ripple at U2's ground
reference rather than a DC regulation error. It is recorded, not waived: see **Open items**.

## Decoupling loops (actual copper, partial-inductance estimates)

| Capacitor | Loop length | Estimate |
|---|---|---|
| C8, U1 VDD 100 nF | 3.57 mm | 2.3 nH |
| C17, U7 | 4.10 mm | 2.7 nH |
| C1, U2 input | 1.30 mm | 0.5 nH |
| C6, U3 output | 6.07 mm | 4.3 nH |
| C15/C16, U4 in/out | 8.58 / 11.57 mm | 7.1 / 10.6 nH |
| C7, U1 bulk 4.7 µF | 34.48 mm | 35.5 nH |

The high-frequency parts (MCU 100 nF, op-amp, buck input) are short; the long ones are bulk reservoirs whose
job does not depend on loop inductance.

## Power drop and the thermal sizing screen

At the acceptance corner, with the 0.439 A TPS2552-1 limit as the LED bound and 0.215 A of 12 V input current
(0.85 efficiency assumed):

- LED supply + return trace drop: 13.3 mV + 4.6 mV = **17.9 mV**, 0.36 % of 5 V;
- 12 V input loop trace drop: **57.4 mV** (D1.1 → C1.1 is 46.1 mm because the protected rail crosses the
  board; it is outer-copper only);
- ground offset at the LED connector J3 against the power trunk, conservatively: **33.6 mV**;
- `+3V3` U3.5 → U1.3: 221 mΩ at 20 mA = 4.4 mV of supply drop, of which the Kelvin taps leave 32 µV in the
  CV reference.

No high-current net uses inner copper (`inner_layer_high_current_track_mm = 0`): the 15 µm inner layers carry
signals only. High-current widths are 0.3 mm and 0.6 mm. The IPC-2221 external-conductor equation as published
by JLCPCB gives 1.00 A for 0.3 mm of 35 µm outer copper at a 10 K rise, against the 0.439 A bound — a 2.3×
sizing margin, and a sizing screen only: it does not predict the temperature of the enclosed assembly, which
needs bench work.

## CV and data coupling

With no plane there is no shield, so the router enforces 3D separation rules between the CV chain and every
switching or data net. All are met on the adopted board:

| Pair | Required | Actual (any layer) |
|---|---|---|
| `/CV_SENSE` – `/BUCK_SW` | 2.5 mm | 3.07 mm |
| `/CV_SENSE` – `/DATA_L` / `/DATA_R` | 1.5 mm | 3.36 / 3.35 mm |
| `/CV_THRU` – `/DATA_L` / `/DATA_R` | 1.2 mm | 1.72 / 1.20 mm |
| `/CV_THRU` – `/DATA_L_3V3` / `/DATA_R_3V3` | 0.9 mm | 1.03 / 1.03 mm |
| `/CV_FILTER` – `/VLED` | 1.2 mm | 1.60 mm |

No CV track runs within 0.5 mm of any aggressor in that table anywhere on any layer. The pairs that carry no
rule do cross on adjacent layers: `/CV_THRU` runs within 0.5 mm of `/VLED` for 9.4 mm, of `/SWDIO` for 3.8 mm
and of `/SWCLK` for 3.3 mm. Those crossings are what the open-input estimate below covers.

An unshielded two-wire estimate of the worst ruled case, `/BUCK_SW` into `/CV_SENSE` across 3.07 mm, gives
40 fF. Treating `/CV_SENSE` as the open 10 MΩ divider node it is at switching frequencies, that puts 174 mV of
switching ripple on it but **31 µV at `/CV_AFFINE`** after the 776 Hz filter
(`engineering/a5/electronics/reports/electrical_margins.json`, `nominal_pole_Hz`), which is 0.004 LSB. These
are upper-side estimates with no plane and no intervening conductor credited, for comparing candidates — not a
field solution.

`/CV_THRU` is the jack-tip node itself (J1.4, J2.4, R1.1). With nothing patched it sits 20 MΩ from ground, and
the estimate of capacitive pickup there is the one item the plane removal genuinely worsened: 0.3–3.8 pF to the
data, SWD and VLED runs, i.e. 6–43 % of an aggressor edge appearing on the open tip against an assumed 5 pF tip
node (worst: `/VLED` at 3.8 pF and 43 %). That coupling has **no DC path**, so it carries no mean offset; the
776 Hz filter attenuates an 800 kHz data edge train by about three orders of magnitude; the firmware adds a 1/8
IIR (`light_block.c`, `cv_mv + (sample - cv_mv) / 8`); and the excursions stay inside the op-amp's rails, so no
rectification is expected. A patched source of 1 kΩ or less reduces all of it by more than 10⁴. The reading of
an **unpatched** input is therefore expected to stay inside the ±50 mV deadband, but that expectation is a
calculation: it NEEDS BENCH (#10). It is deliberately not an acceptance gate, since a floating input has no
defined value.

## Open items (not waived, not approved)

1. **Output-capacitor return, 15.71 mm / 2 vias.** Placement-forced. If a later revision may move parts, C2
   next to U2 (or a second stitch via pair) would shorten it. Ripple effect unmeasured.
2. **Unpatched `/CV_THRU` pickup.** As above: NEEDS BENCH (#10). The ideal fix is a buffer or series resistor
   at the jack, which would change the schematic and is out of scope here.
3. **Thermal behaviour of the local copper area and of 0.8 mm laminate.** Only a sizing screen exists.
4. **Every assumption marked ASSUMED above** (0.8× tolerances, 18 µm plating, 20 mA MCU, 0.85 efficiency,
   5 pF open-tip node, the IPC chart) is an engineering bound, not vendor-guaranteed data.

## Reproducing this review

```sh
python3 scripts/a7_route_check.py --out <empty dir outside the repository>
```

That rebuilds the staging geometry in the pinned KiCad 10.0.8 image, re-runs the router at seed 0, requires the
proposal to equal `routing/route_proposal_seed0.json` byte for byte, requires the committed board's copper to
be exactly that proposal, and then re-runs this electrical review and requires it to pass. The committed
`controller/return-review.json` is bound to the board and proposal bytes by
`scripts/tests/test_a7_return_review.py`.
