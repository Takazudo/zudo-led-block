# Electrical review of the 0.8 mm controller with no ground planes (#87)

Board under review: `engineering/a7/electronics/controller/controller.kicad_pcb`, SHA256
`d83691d6590e013b2a66957b61d76ba2f68bedaaec04789326e1215b2d1bdb2b` (2109 tracks, 116 vias, one local copper
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
| Same, with a patched CV cable sharing the supply return (fraction bound 0.51, ASSUMED) | 0.5 ADC LSB | **0.254 LSB** | 0.141 LSB | 2.2× of the fraction: 0.46 LSB even at fraction 1 |
| Combined static DC reference error | 1.0 ADC LSB | **0.369 LSB** (297.4 µV) | 0.1840 LSB | 5.4× |

The acceptance corner is `hot_85C_thin_copper`: 85 °C (the upper ambient rating of the fitted parts) with
copper thickness, track width and barrel plating all at 0.8× nominal. Those tolerances are explicit
**assumptions**; no fabricator tolerance row is retained. Resistance scales every voltage in the model, so
this corner is the acceptance case: at it the first and last rows sit 13.3× and 2.7× under their limits. The
last column is the separate question of how much every resistance on the board could grow from its nominal
value before the allocation is reached. The patched row is conditional on resistances outside the board and
is explained under **Patched ground loop** below.

Derivation of the two allocations:

- one 12-bit code at 3.3 V is 0.806 mV at the ADC pin, i.e. 8.57 mV of CV through the kept inverse
  `CV = 10.64*VADC - 4*VDD` (`engineering/a5/electronics/reports/electrical_margins.json`, `cv_transfer`);
- the firmware CV deadband is ±50 mV with ±5 V full scale (`engineering/a5/firmware/README.md` mode table,
  `LB_CV_DEADBAND_MV` in `engineering/a5/firmware/src/light_block.c`). Half a code is 8.6 % of the deadband
  and one code is 17 %, so neither can move a 0 V input out of the deadband;
- a static offset is removable by the firmware zero calibration (`lb_calibration_t`); an LED-dependent shift
  is not, which is why it gets the tighter half-code allocation.

Excluded from the budget, because they are layout-independent and belong to bench work (#10): power-cable and
connector contact resistance as error terms of their own, op-amp offset, ADC/reference error, resistor
tolerance and AC noise. Cable and contact resistances do decide how the supply return divides once a CV cable
is patched; that dependence is modelled below with ASSUMED ranges and is a bench item, not an approval.

## Return topology: one star pin, two faces, no plane

The two ground systems meet **only at the J5.2 power-connector pin**, and on opposite faces of that plated
pad, so even the pad copper is not shared: the power return owns the F.Cu face, the quiet returns own the
B.Cu face, and the only shared metal is the barrel plating.

The audit over the board's own copper (filled polygons plus a conservative track half-width, with J5.2
removed) finds three components, two of them power and one quiet, and no copper that joins a power pad to a
quiet pad anywhere but at the pin:

| Branch | Face at J5.2 | Pads | Members |
|---|---|---|---|
| power: buck, LED switch, LED connector | F.Cu | 11 | C1.2, C2.2, C11.2, C12.1, C15.2, C16.2, J3.1, R11.2, R20.2, U2.4, U4.2 |
| power: U5 level-shifter cluster | F.Cu | 8 | C3.2, C9.2, C10.2, R16.2, R17.2, R18.2, R19.2, U5.4 |
| quiet: MCU, analog island, LDO cluster, jack sleeves, mode switch, MCU bulk, CV clamp | B.Cu | 23 | C5.2, C6.2, C7.2, C8.2, C13.2, C14.2, C17.2, D3.1, J1.1, J1.2, J2.1, J2.2, Q1.2, R2.2, R6.2, R8.2, R12.2, R25.2, SW1.3, TP2.1, U1.4, U3.2, U7.2 |

The quiet system is one component in this revision because its three sub-branches (MCU/analog trunk, CV IN
sleeve spur, MCU-bulk spur) leave the B.Cu face of the pin through the same stub, about 0.7 mm of 0.6 mm track,
before they part. That shared stub is 0.27 mΩ nominal between the sleeve spur and the MCU trunk and 0.23 mΩ towards the
MCU-bulk spur. It is in the resistance network, so every number below already includes it; the earlier board
(`710ed801…`) happened to keep those three apart and is superseded.

Inside the quiet system a 0.6 mm B.Cu trunk runs from the J5.2 pin to the single MCU ground via under U1 at
(2.6, 27.0). The CV/ADC island (R25.2, R6.2, U7.2, C17.2, C13.2) is taken from that via as a Kelvin tap, and
the LDO/bleeder cluster (R8.2, U3.2, C6.2, C5.2, R2.2) hangs on its own spur off the trunk rather than through
the island, so the 3.3 mA bleeder and the LDO's own return current do not flow in the reference copper. The
result is the headline number, and its condition: **while the whole supply return leaves through J5.2, both
LED scenarios produce exactly 0 V of weighted reference error**, because the LED return shares no copper at
all with the reference chain. That condition holds with nothing patched, or with a CV source that has no other
connection to the supply ground. It does not hold once a patched cable closes a ground loop; see **Patched
ground loop**.

The only LED-dependent term left is the J5.2 barrel itself, taken conservatively as fully shared by both
branches: 0.731 mΩ at the corner × the 0.439 A TPS2552-1 current-limit bound = 321 µV of shift of the whole
board reference against the patched CV source, which the firmware weight (1/10.64 from CV volts to ADC volts)
turns into 30.2 µV at the ADC pin, i.e. 0.0375 LSB.

Selected measured-from-copper resistances at the acceptance corner (nominal in `return-review.json`):

| Path | Length | Resistance (corner) |
|---|---|---|
| U1.4 → J5.2 (B.Cu face) | 7.52 mm | 13.4 mΩ |
| R25.2 → U1.4 | 12.65 mm | 71.3 mΩ |
| U7.2 → U1.4 | 9.30 mm | 60.1 mΩ |
| C8.2 → U1.4 (MCU decoupling return) | 3.07 mm | 19.2 mΩ |
| C1.2 → J5.2 (F.Cu face, power trunk) | 27.94 mm | 88.7 mΩ |
| J1.1 (CV IN sleeve) → J5.2 (B.Cu face) | 11.71 mm | 17.9 mΩ (9.2 mΩ nominal) |
| J2.1 (CV THRU sleeve) → J5.2 (B.Cu face) | 41.47 mm | 204.7 mΩ (104.4 mΩ nominal) |

### Patched ground loop

A patched CV cable connects the board ground to the source's ground at the CV IN sleeve (J1.1, the terminal
the PJ-324M record infers as sleeve). Where the source shares the supply ground, as two modules on one rack
supply do, that sleeve path is in parallel with the power-cable ground, so a share of the J5.2 current returns
through J1.1 and the sleeve spur instead. The source then holds CV against the sleeve rather than against the
J5.2 pin, and the drop along the spur is a CV error that follows LED brightness. The earlier revision of this
record did not model it, and its 0.3 mm spur (24.9 mΩ nominal, 48.5 mΩ at the corner on B.Cu) reached the
0.5 LSB allocation at a sleeve share of 0.38.

This board routes the CV IN sleeve first, from the pin, as 0.6 mm outer copper only. The scenario
(`patched_ground_loop` in `return-review.json`) takes `led_physical_dc`, removes a fraction of the 0.215 A
J5.2 current at J1.1, credits the sleeve as the source reference, and keeps the whole J5.2 barrel bound on
top. At the acceptance corner the result is **0.0375 + 0.422 × fraction LSB** (1.96 LSB per ampere of sleeve
current; nominal 0.0239 + 0.216 × fraction):

| Sleeve share of the J5.2 current | 0 | 0.1 | 0.2 | 0.3 | 0.4 | 0.5 | 0.75 | 1.0 |
|---|---|---|---|---|---|---|---|---|
| LED-dependent error at the corner, LSB | 0.037 | 0.080 | 0.122 | 0.164 | 0.206 | 0.249 | 0.354 | 0.460 |

The share is a current divider between two returns, and almost none of its resistances are retained facts:

| Path | Element | Range | Basis |
|---|---|---|---|
| power return | power cable ground conductor | 11–13 mΩ | ASSUMED: 28 AWG, 50–60 mm; the A7 cable is not selected |
| power return | two 1.25 mm header contacts | 10–40 mΩ | ASSUMED: no contact resistance is retained for Molex 530470310 |
| power return | adapter copper, 2x5 header, rack bus cable | 5–30 mΩ | ASSUMED |
| sleeve return | CV IN sleeve contact | 5–50 mΩ | maximum from `fact-a7-pj-324m-contact-resistance` (initial, grade unidentified); minimum ASSUMED |
| sleeve return | patch cable shield | 30–200 mΩ | ASSUMED |
| sleeve return | far-end jack sleeve contact | 5–50 mΩ | ASSUMED |
| sleeve return | source module return to the rack ground | 20–80 mΩ | ASSUMED |
| sleeve return | sleeve spur on this board | 18.6 mΩ at the corner | this review |

Those ranges give a share between 0.06 and **0.51**, and at 0.51 the bound is **0.254 LSB** against the
0.5 LSB allocation (0.141 LSB nominal). The allocation is not relaxed, and on this copper it is not reached
even if the entire 0.215 A returned through the sleeve (0.460 LSB at share 1.0, which the divider cannot
produce). That last statement uses the 0.85 buck efficiency, which is ASSUMED.

What this does and does not show:

- It bounds the **board's** contribution. The same sleeve current also drops across the sleeve contacts and the
  patch-cable shield, outside the board: at the 0.51 share and the minimum external values above that is a
  further 0.52 LSB. That part is the same for any layout, is outside the allocation, and is the larger term.
- The share itself NEEDS BENCH (#10): measure the CV reading against LED brightness with a patched,
  ground-sharing source. No number here is a measurement.
- A downstream module patched to CV THRU can push its own return current into J2.1. The THRU sleeve is a long
  0.3 mm spur (104 mΩ nominal to the pin), and 8.9 mΩ nominal / 17.3 mΩ at the corner of it is shared with the
  CV IN sleeve, so that current shifts the CV IN reference by the same mechanism. It is recorded, not bounded:
  the current is another module's and is unknown here.

### Local copper areas: exactly one

| id | net | layer | rectangle (mm) | area | why |
|---|---|---|---|---|---|
| `buck-return-thermal` | `/GND` | B.Cu | (4.0, 0.4) – (8.8, 4.9) | 21.6 mm² | localized return/thermal spreading under U2/C1, tied to the buck ground by the two stitch vias at (5.0, 3.9) and (5.8, 3.9); AP63205 datasheet DS41326 Rev 3-2 p.15 asks for bottom ground copper. It is on the power branch only. |

The plotted Gerbers confirm this is the whole story: exactly one filled region object on any copper layer, and
it is this one. Dark copper coverage inside the 16.2 × 62.9 mm bounds is F.Cu 22.2 %, In1.Cu 10.0 %,
In2.Cu 10.7 %, B.Cu 18.8 % — the former inner planes are gone. The audit in `return-review.json`
(`filled_star_audit`) proves this area touches only power-branch copper (74 contact nodes, 2 vias, no pad and
not the J5.2 pad), so a native refill cannot bridge the two ground systems.

`+3V3` carries its own Kelvin rule: the affine divider taps R4.1 and R5.1 reach the rest of the net only
through C8.1, the MCU decoupling capacitor, so the MCU supply current is not in the reference. With that
topology the taps sit 3.8990 mV below U3.5 while the measured VDDA (U1.3) sits 3.9312 mV below it, and the
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
| C7, U1 bulk 4.7 µF | 28.89 mm | 28.9 nH |

The high-frequency parts (MCU 100 nF, op-amp, buck input) are short; the long ones are bulk reservoirs whose
job does not depend on loop inductance.

## Power drop and the thermal sizing screen

At the acceptance corner, with the 0.439 A TPS2552-1 limit as the LED bound and 0.215 A of 12 V input current
(0.85 efficiency assumed):

- LED supply + return trace drop: 13.3 mV + 4.6 mV = **17.9 mV**, 0.36 % of 5 V;
- 12 V input loop trace drop: **57.6 mV** (D1.1 → C1.1 is 46.1 mm because the protected rail crosses the
  board; it is outer-copper only);
- ground offset at the LED connector J3 against the power trunk, conservatively: **34.1 mV**;
- `+3V3` U3.5 → U1.3: 182 mΩ at 20 mA = 3.6 mV of supply drop, of which the Kelvin taps leave 32 µV in the
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
rule do cross on adjacent layers and run close on the same layer: `/CV_THRU` is within 0.5 mm of `/VLED` for
11.7 mm (0.25 mm same-layer gap at the closest), of `/SWDIO` for 3.8 mm and of `/SWCLK` for 3.2 mm. Those
runs are what the open-input estimate below covers.

Beyond `/CV_THRU`, the record lists every CV-chain pair with a same-layer gap under 0.6 mm or a track within
0.5 mm in plan (`coupling.close_pairs`, 21 pairs). The ones that matter:

| Pair | Same-layer gap | Track within 0.5 mm | Estimate | Node |
|---|---|---|---|---|
| `/CV_AFFINE` – `/DATA_L` | 0.25 mm | 6.9 mm | 0.83 pF | held by C13, 10 nF: 8.3e-5 of a 5 V edge = 0.41 mV at the node, 3.3 mV of CV |
| `/CV_AFFINE` – `/-12V_PROT` | 0.20 mm | 19.5 mm | 3.7 pF | same node; a supply rail, not an edge source |
| `/CV_AFFINE` – `/SWDIO` / `/SWCLK` | 0.20 / 0.25 mm | 2.3 / 1.6 mm | 1.1 / 0.6 pF | same node; debug only |
| `/CV_ADC` – `/DATA_L_3V3` / `/DATA_R_3V3` | 0.71 / 0.19 mm | 1.4 / 1.5 mm | 0.41 / 0.38 pF | driven through 250 Ω |
| `/CV_BUF` – `/DATA_L` | 1.45 mm (adjacent layer overlap) | 4.1 mm | 1.4 pF | op-amp output |
| `/CV_SENSE` – `/+12V_PROT` / `/-12V_PROT` | 0.40 / 0.35 mm | 0 mm | 0.05 / 0.06 pF | megohm node; rails |

So the statement the 1.6 mm review made, and the qualification plan still quotes — *no CV node runs within
0.6 mm of DATA_L/R or ±12V_PROT on the same layer* — **does not hold on this board**. Only `/CV_THRU`,
`/CV_SENSE` and `/CV_FILTER` carry separation rules here; the low-impedance nodes were left to the router. The
figures above are the same order-of-magnitude estimates as the rest of this section, and whether the reading
is disturbed NEEDS BENCH (#10).

An unshielded two-wire estimate of the worst ruled case, `/BUCK_SW` into `/CV_SENSE` across 3.07 mm, gives
40 fF. Treating `/CV_SENSE` as the open 10 MΩ divider node it is at switching frequencies, that puts 174 mV of
switching ripple on it but **31 µV at `/CV_AFFINE`** after the 776 Hz filter
(`engineering/a5/electronics/reports/electrical_margins.json`, `nominal_pole_Hz`), which is 0.004 LSB. These
are upper-side estimates with no plane and no intervening conductor credited, for comparing candidates — not a
field solution.

`/CV_THRU` is the jack-tip node itself (J1.4, J2.4, R1.1). With nothing patched it sits 20 MΩ from ground, and
the estimate of capacitive pickup there is the one item the plane removal genuinely worsened: 0.3–2.9 pF to the
data, SWD and VLED runs, i.e. 6–37 % of an aggressor edge appearing on the open tip against an assumed 5 pF tip
node (worst: `/VLED` at 2.9 pF and 37 %). That coupling has **no DC path**, so it carries no mean offset; the
776 Hz filter attenuates an 800 kHz data edge train by about three orders of magnitude; the firmware adds a 1/8
IIR (`light_block.c`, `cv_mv + (sample - cv_mv) / 8`); and the excursions stay inside the op-amp's rails, so no
rectification is expected. A patched source of 1 kΩ or less reduces all of it by more than 10⁴. The reading of
an **unpatched** input is therefore expected to stay inside the ±50 mV deadband, but that expectation is a
calculation: it NEEDS BENCH (#10). It is deliberately not an acceptance gate, since a floating input has no
defined value.

## Open items (not waived, not approved)

1. **Output-capacitor return, 15.71 mm / 2 vias.** Placement-forced. If a later revision may move parts, C2
   next to U2 (or a second stitch via pair) would shorten it. Ripple effect unmeasured.
2. **Unpatched `/CV_THRU` pickup, and the close runs of `/CV_AFFINE`, `/CV_ADC` and `/CV_BUF` to data and
   supply nets.** As above: NEEDS BENCH (#10). For the open tip the ideal fix is a buffer or series resistor
   at the jack, which would change the schematic and is out of scope here; for the close runs it is a
   separation rule on those nets in a later routing revision.
3. **Patched ground loop.** The LED-dependent CV error with a ground-sharing source depends on the share of the
   supply return that takes the sleeve path, which is set by cable and contact resistances that are ASSUMED
   here, and on the patch-cable drop, which no layout removes. NEEDS BENCH (#10). A CV THRU sleeve current
   from a downstream module is recorded but not bounded.
4. **Thermal behaviour of the local copper area and of 0.8 mm laminate.** Only a sizing screen exists.
5. **Every assumption marked ASSUMED above** (0.8× tolerances, 18 µm plating, 20 mA MCU, 0.85 efficiency,
   5 pF open-tip node, the patched-loop resistance ranges, the IPC chart) is an engineering bound, not
   vendor-guaranteed data.

## Reproducing this review

```sh
python3 scripts/a7_route_check.py --out <empty dir outside the repository>
```

That rebuilds the staging geometry in the pinned KiCad 10.0.8 image, re-runs the router at seed 0, requires the
proposal to equal `routing/route_proposal_seed0.json` byte for byte, requires the committed board's copper to
be exactly that proposal, and then re-runs this electrical review and requires it to pass. The committed
`controller/return-review.json` is bound to the board and proposal bytes by
`scripts/tests/test_a7_return_review.py`.
