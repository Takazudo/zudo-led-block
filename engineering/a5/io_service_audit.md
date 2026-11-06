# A4 electromechanical parts and international PCBA service audit

**Status:** procurement/design audit, not manufacturing release. Observations were collected on **2026-11-05 UTC** (2026-11-06 JST). A2 and A3 files remain unchanged. No vendor contact, quotation submission, reservation or purchase was made.

## Recommended A4 route

Use two **XKB PJ-3582-B / C500090** jacks and a **Dailywell 1MS3T1B1M2QES-5 / C908270** maintained ON–OFF–ON toggle. Both have actual JLC inventory and published through-hole assembly support. The jacks need a new structural cradle because their barrels have **no threads**. The toggle needs a larger front hole than the A3 C&K part.

For lighting, the current cost-oriented choice is **two identical 0.6 mm FR-4 LED boards, populated on one side and mounted back to back**, with four RGB LEDs and four local capacitors on each. This keeps two independently driven channels and avoids a second populated side on the lighting PCBA job. The frosted acrylic front remains separate; this FR-4 is internal. The selected WS2812B-2020-V6 **C52917434 is Standard Only**, so an Economic-capable board outline or a change to 0.8 mm thickness does not make this BOM Economic-compatible. The electronic BOM audit owns the LED's live stock and exact assembly eligibility.

Use **four C160404 JST SH four-pin SMT headers**: two on the controller and one on each identical LED board. Two preassembled **Adafruit4399 50 mm cables** provide plug-in connections; SparkFun PRT-17260 is a more expensive flexible-insulation alternative. Both identical leaves use **GND/VLED/DATA/NC**, with separate DATA outputs at the controller. This is one connector SKU repeated four times. These are the cables/connectors used by Qwiic; the proposed module connection is a custom LED interface, not an I²C/Qwiic port. Position the leaf connectors near the lower end, outside the useful luminous sheet area, with a local PETG relief still to be designed. Do not place an unmodeled connector in the optical gap.

For power, use a **passive remote adapter**, with **C5665 keyed 2×5 IDC** and **C122442 Molex PicoBlade three-pin header**, connected to the controller's second C122442 by a ready-made **Molex 151340300** cable. Put the adapter into the same 1.6 mm fabrication/assembly panel as the controller, subject to the multi-design charge and placement review. A normal unmodified 16-to-10 Eurorack ribbon connects the adapter to the case. This eliminates the A3 proposal to cut a ribbon and solder its fanout at home.

The controller/adapter panel and the 0.6 mm LED panel are **two PCBA jobs**. Final connector coordinates, cable routing, exact panel tabs, native footprints and complete board layout are still unfinished. This audit establishes a credible assembly route; it does not claim that the existing A3 rear CAD accepts these replacements unchanged.

## Live JLC inventory and component prices

These are anonymous public JLC product-page observations, not cached search snippets. `overseasStockCount` corresponds to the UI **In Stock**; `canPresaleNumber` corresponds to **Available Order Qty** in the pre-purchase parts library. The latter is not a separate promise of total PCBA availability. All selected rows show source **JLCPCB**, not distributor/global-source inventory. Full sanitized records, timestamps, price breaks and HTML hashes are in `io_service_audit.json` and `mechanical_evidence/*.snapshot.json`.

| Function | Exact part / JLC code | In Stock | Available Order Qty | First USD tier | Assembly shown | Observed UTC |
|---|---|---:|---:|---:|---|---|
| CV IN and THRU, 2/module | XKB PJ-3582-B / **C500090** | 2,891 | 2,862 | **$0.2660**, 1–49 | Wave Soldering; Economic and Standard | 20:18 |
| Three-mode switch | Dailywell 1MS3T1B1M2QES-5 / **C908270** | 1,134 | 1,058 | **$1.4146**, 1–9 | Wave Soldering; Economic and Standard | 20:24:44 |
| LED connections, 4/module | JST SM04B-SRSS-TB(LF)(SN) / **C160404** | 57,558 | 50,828 | **$0.2146**, 1–49 | SMT Assembly; Economic and Standard | 20:26:12 |
| Power connection, 2/module | Molex 530470310 / **C122442** | 22,499 | 21,852 | **$0.1314**, 1–49 | Wave Soldering; Economic and Standard | 20:28:17 |
| Remote Eurorack adapter | BOOMELE 2.54-2*5P IDC / **C5665** | 143,581 | 137,022 | **$0.1041**, 1–49 | Wave Soldering; Economic and Standard | 20:29:01 |

Selected I/O component arithmetic at the first displayed tiers is **$3.1719/module**: two jacks, one toggle, four SH headers, two PicoBlade headers and one IDC header. This excludes assembly, attrition, minimum pre-purchase quantities, the LED/electronic BOM, cables, hardware, PCBs, taxes and shipping. It is not an order quote. The two primary Adafruit cables add **$1.90** at1–9 units before shipping/tax; the Molex power cable and Eurorack ribbon have no verified live retail price in this audit. The cables are an external purchase, not loose items supplied by JLC with the assembled boards.

For a **100-module evaluation**, the selected I/O quantities are200jacks,100toggles,400SHheaders,200PicoBladeheaders and100IDCheaders. Applying the displayed tier for each exact quantity gives **$214.75 total/$2.1475 per module**, excluding attrition and all costs above. Of that,400C160404 headers at$0.1536 cost$61.44. The required200Adafruit4399 cables are$0.76 each at the100+ tier, or$152.00; SparkFun's100+ tier is$1.35, or$270.00 for200. Both cable pages show **In stock**, but neither retrieved page publishes a numeric quantity: this does **not** establish that200cables can ship immediately. No inventory was reserved.

The toggle is the lowest-stock selected row. Current stock is ample for a small integrated prototype batch, but nothing has been reserved and inventory must be rechecked at BOM upload.

### Rejected or secondary candidates

| Candidate | Finding | Consequence |
|---|---|---|
| Original WQP-WQP518MA placeholder **C9900079089** | 0 stock / 0 available; this JLC entry says no longer manufactured | Not a stocked primary. This is a statement about that JLC catalog entry, not proof the WQP manufacturer's part is globally discontinued. |
| C&K T103MH9AVBE **C2799370** | 5 stock / 5 available; $23.0959 at1–9; a different H9/AV configuration | Cost/stock poor and not the A3 T103SHCBE geometry. |
| XKB PJ-301M-2-B **C381126** | 779/777, $0.2218; manufacturer drawing has two rear terminals plus a sleeve solder eyelet near the front | Not a drop-in all-terminals-to-parallel-PCB replacement. Would need an additional connection. |
| XKB PJ-301C **C692433** | 226/176, $0.2635; 8.47 mm cross width and smooth Ø6 barrel | Lower inventory and wider than PJ-3582-B; no demonstrated threaded panel retention. |
| SHOUHAN SS13D07VG4 **C2681578** | 22,576/22,388, $0.0370; maintained SP3T; 12.8×4.4 mm body,4.7 mm body height,4 mm stem | Excellent electrical cost, but the stem ends3.6 mm behind the panel rear when seated on a PCB atz12.3. It requires a guided extension. Retain only as a cost-down alternative. |
| JST three-pin SH **C160403** | Current direct snapshot0/0; old search snippet showed11,580 | Do not use cached stock to select it. Four-pin C160404 avoids this shortage. |
| SHOUHAN PicoBlade-style **C393944** | 29,867/28,807, $0.0411; inexpensive SMT3-pin | Not selected: same-family marketing alone does not establish the exact cable/header mating qualification. Genuine Molex power pair has an explicit manufacturer drawing. |

## Jack geometry: C500090

The downloaded XKB manufacturer drawing identifies the PJ-358X family and shows the PJ-3582 circuit separately from PJ-3583. The body's front view is **10.0×6.1 mm**; axial plastic depth is **12.0 mm**. Rotate it so **6.1 mm is across the HP width and10.0 mm is vertical**. The smooth barrel is **Ø6.0×3.0 mm**, without a thread specification. The rear uses five PTH contacts and a locating feature; use the exact rotated footprint and pin assignment from this drawing, not a WQP footprint.

The drawing states0.1 mm general tolerance and insertion/actuation force3–30 N. A first envelope uses bodyfrontz0.3, bodyback/PCBfront approximatelyz12.3, giving barrelfrontz−2.7 against a2 mm front panel. These coordinates are design assumptions, not a qualified seating stack. Keep the proposed **Ø6.2 front opening** as a prototype clearance choice and verify the supplier's finished hole tolerance. With9.8 mm panel width, nominal body clearance is1.85 mm on each side before carrier tolerances.

The carrier must react both insertion and extraction and prevent body rotation. It must retain the plastic body positively in both axial directions; solder joints must not be the only load path. Do not add a decorative nut proxy. New PCB setback also changes rear component, solder-tail, sheet and LED-board clearances. Retain y90 and104 only after checking the exact rotated footprint and body capture.

Source: [JLC C500090 product page](https://jlcpcb.com/partdetail/XKBConnection-PJ_3582B/C500090), downloaded manufacturer PDF `mechanical_evidence/C500090.pdf`. The observed public Datasheet link used an expiring query on the stable object path `https://jlc-prod-smt.oss-eu-central-1.aliyuncs.com/smtDataManualFile/8588896380064837632-C500090.pdf`; use the product page and file hash for durable provenance.

## Toggle geometry and three-state logic: C908270

Dailywell's1M manufacturer catalog confirms **1MS3 = maintained ON–OFF–ON**: common2 connects to3, then neither, then1. Two pulled-up MCU inputs and grounded common therefore preserve the A3 three-mode logic. The center position is PROGRAM; it is not a power-off instruction. Verify physical throw direction after footprint orientation.

The selected **Q contact finish is silver**. The catalog's initial contact-resistance test is at100 mA; this is not a guaranteed minimum-load specification for the MCU pull-up current. Low-current contact reliability remains an electrical qualification item; do not infer it from the switch's ampere rating.

The family drawing gives **6.86 mm cross width ×12.70 mm vertical ×8.89 mm case depth**, **B1 threaded bushing8.89 mm long,1/4-40 UNS-2A**, and **T1 lever10.41 mm**. M2 means PC through-hole. Its terminal drawing shows **6.60 mm from the base reference,5.10 mm beyond the epoxy seat**, with1.27×0.76 mm terminal cross-section. This is a long-tail part: specify factory trimming and a maximum finished solder-tail envelope before locating the rear LED boards. Untrimmed pins cannot be assumed to stay in the old rear-component zone.

The official mounting drawing is **Ø6.35 with an inward key tab0.55 wide×0.85 deep**. B1 has a keyway; it is not the D-flat used by A3. For the2 mm laser-cut PMMA prototype, A4 instead proposes a **plainØ6.50 finished hole** and antirotation from the rear carrier. The clearance and supplier kerf compensation still require qualification. This avoids asking a tiny acrylic tab to react toggle torque.

Standard hardware from the catalog:

| Item | Dimensions | 2HP consequence |
|---|---|---|
| **MNU-1M01A standard hex nut** | **7.92 mm across flats;9.19 mm across corners;1.57 mm thick** | Fits9.8 mm nominal width narrowly; allow orientation/adjacent-panel clearance. |
| MNU-1M03 lockwasher | Ø10.80×0.46 mm | Does not fit2HP; omit or replace with specifically dimensioned smaller hardware. |
| Standard locking ring | Ø11.99 mm | Does not fit2HP; carrier supplies antirotation. |
| Optional MNU-1M29 dress nut | Ø9.45 envelope,3 mm thick | Different item; do not confuse with the standard nut. |

A rear engraving exclusion **Ø7.70** remains hidden under the standard nut at any hex orientation, subject to registration. The axial case/barrel positions cannot be frozen merely by subtracting8.89 from the PCB plane: the M2 epoxy seat/standoff must be included. The simple zero-standoff calculation gives casefrontz3.41 and threadtipz−5.48 forPCBz12.3; a1.5 mm seat allowance would move both1.5 mm forward. These are alternative envelope calculations, not simultaneous manufacturing dimensions. Establish one assembly datum and factory fixture before rear CAD release. The stock-specific supplied hardware and the meaning of the supplier's“-5” suffix also remain receiving/quote checks.

Source: [C908270 product page](https://jlcpcb.com/partdetail/Dailywell-1MS3T1B1M2QES5/C908270), [linked manufacturer catalog](https://www.lcsc.com/datasheet/lcsc_datasheet_2304140030_Dailywell-1MS3T1B1M2QES-5_C908270.pdf), saved as `C908270.pdf`. Relevant pages:2function,3case,6bushing,7panel,8M2terminals,10–11hardware.

## Cable and connector geometry

**LED harness.** C160404's JLC-listed envelope is6.0×4.32×2.9 mm, with1 mm pitch and1 A contact rating. The linked JST manufacturer drawing gives a6.0 mm body width,4.25 mm body depth plus terminal projection, and a side-entry **mated** outline approximately6.25 mm deep×2.95 mm high. Its mounting land pattern is larger than the plastic body. Use the exact drawing for the footprint.

Primary **Adafruit4399** is50±5 mm, two female SH4 ends, UL1571 28AWG with0.8 mm wire OD. Its linked Kaweei drawing explicitly maps **P1.1→P2.1 black;2→2 red;3→3 blue;4→4 yellow**. Intended module net assignment is1GND/2VLED/3DATA/4NC, after reconciling the drawing's mating view with the actual JST header/footprint numbering. The public page and fresh anonymous HTML both showInStock, with$0.95/$0.86/$0.76 at1–9/10–99/100+; numeric available quantity is not provided. Source observation20:34:42UTC. Both ends are interchangeable electrically under that1:1 map.

Alternative **SparkFun PRT-17260** is50 mm, four-conductor, flexible-insulated, terminated cable, currently listedIn stock at$1.50 and$1.35 at100+. Its linked ACCA-1571 drawing also maps1→1,2→2,3→3,4→4, but labels its cavities in the opposite color order (1yellow…4black). Do not transfer those cavity labels blindly onto a PCB symbol. This2017 drawing specifies a PVC jacket while the newer product description advertises flexible insulation, so treat its old wire-OD claim as unqualified for the current cable. Buy/use either harness intact; the cheaper factory-direct-wire alternative requires a specific soldering/harness quote and is not the first prototype's assumed assembly service.

For two0.6 mm boards plus0.1 mm bond line, the laminate stack is1.3 mm. Adding1.1 mm component reservation on each outward side gives3.5 mm. Inside the A2 sheet inner faces (6.4 mm spacing), the calculated LED-side gap is **1.45 mm per side**, before PCB thickness, adhesive and placement tolerances. This does **not** prove the connector fits: a2.9 mm header above the laminate surface reaches a7.1 mm total transverse envelope if opposing headers coincide, exceeding the6.4 mm skin cavity. Stagger/relocate headers and add local replaceable-sheet relief, or move to3HP. Also model the mated housing and wire bend; do not substitute bare-header height.

**Power harness.** Molex530470310 has an official5.5×3.2 mm envelope,4.2 mm height above PCB, approximately5.2 mm mated height, and2.3±0.5 mm tails. Its drawing recommends0.5±0.05 mm holes on1.25±0.1 pitch for0.8 mm PCB; final1.6 mm board insertion/tail allowance must be checked. The mating housing is510210300, exactly the housing in the151340300 cable assembly. Cable rating is1 A/contact,28AWG UL1061,50±6 mm. The official map is **A1→B3,A2→B2,A3→B1**. Route the adapter deliberately to deliver+12 V/GND/−12 V to the controller's chosen pins. Do not infer pin mapping from wire color or connector facing.

The passive IDC adapter's copper must explicitly join the appropriate Eurorack rails/grounds. Adapter location, insulation, mating direction and strain relief remain to be drawn. A remote adapter is part of the installed system; its position and the wire/ribbon bend must be included when assessing the user's30 mm case clearance. No total-depth claim can currently include this unfinished harness.

Sources: [JLC C160404](https://jlcpcb.com/partdetail/Jst-SM04B_SRSS_TB_LF_SN/C160404), [Adafruit4399](https://www.adafruit.com/product/4399), [Adafruit cable manufacturer drawing](https://cdn-shop.adafruit.com/product-files/4399/C14172-001_Kaweei_CBH-100-04-050-A.pdf), [SparkFun PRT-17260](https://www.sparkfun.com/flexible-qwiic-cable-50mm.html), [SparkFun linked drawing](https://cdn.sparkfun.com/assets/b/8/b/8/d/ACCA-1571_Model.pdf), [Molex530470310 drawing](https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/salesdrawingpdf/530/53047/530470310_sd.pdf), [Molex151340300 product](https://www.molex.com/en-us/products/part-detail/151340300), [Molex cable drawing/table](https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/salesdrawingpdf/151/15134/151340303_sd.pdf).

## International JLCPCB service and panelization

The **international jlcpcb.com capability table** lists Standard single/double-sided SMT/THT,1–32 copper layers, no thickness limit, and **70×70 mm minimum single board or panel**. Economic is single-sided,2/4/6layers,0.8–1.6 mm and10×10 mm minimum. Standard needs rails/fiducials. Mixed SMT/THT is supported, with THT usually wave-soldered. The FAQ explicitly supports soldering library wire to an assembly order after review and added charge. It does not establish automatic inter-board harness construction, cable sourcing, chassis assembly or fully tested finished modules.

The8.8×48.4 mm controller cannot be submitted as a standalone Standard board. A panel combining controller and passive adapter keeps both1.6 mm and avoids an additional fabrication job, but it is a quote-comparison proposal rather than a guaranteed saving. Their different designs incur the published Standard multi-design fee: **$25.56×(designs−1) for single-sided assembly or$51.12×(designs−1) for double-sided assembly**. A3's controller-side arrangement and mixed front THT/rear SMT lead to Standard assembly regardless of whether the module is2HP or3HP.

Each82.5×10 mm LED leaf also needs a Standard panel. An initial **six-up geometric envelope** with2 mm routing gaps and5 mm surrounding rails is80×92.5 mm. This is a dimensioned panel proposal, not an approved router/tab design. It yields six identical leaves, or three modules' lighting, per panel. Final quantities in the order may be counted by panels or delivered boards; verify at quote. Keep breakout tabs away from required carrier mating edges, or require factory depanelization and edge finishing. Do not hand-break a thin assembled board beside LEDs.

A0.8 mm, two-layer, single-sided board could satisfy Economic's geometric table, but **the selected LED's Standard Only restriction prevents that cost claim**. The chosen0.6 mm version is also below Economic's thickness range.

Source: [international assembly capabilities](https://jlcpcb.com/capabilities/pcb-assembly-capabilities). Claims here do not rely on domestic `jlc-smt.com` capabilities or LCSC stock.

## Why transparent PET remains an option rather than the default

International JLC's transparent-PET launch page explicitly says SMT assembly compatible, and its current capability FAQ explicitly supports FPC assembly with fixtures. The flexible-PCB capability page lists single-layer transparent0.14 mm material. The older indexed quote-page sentence“Flex PCBs are not available for PCB assembly” was **not found in the fresh public quote HTML** obtained20:19:10UTC. Therefore it is not evidence of a current blanket prohibition.

Nevertheless, the exact0.14 mm transparent stack, the selected LED package, local stiffeners, fixtures and soldering profile have not been accepted through an order/engineering review. The launch page's200°C material statement and the assembly table's240±5°C Standard reflow figure need process-specific clarification; they alone neither prove incompatibility nor qualify the process. Transparent PET has no automatic claim to the same handling cost as rigid FR-4.

For a future FPC option, its published panel rules specify5 mm rails on all four sides,2 mm board separation (3 mm with metal stiffeners),0.7–1 mm support tabs,1 mm fiducials and2 mm tooling holes. Use bridge/tab connections; do not assume rigid-board V-cut or mouse-bite practice is allowed. The six-up80×92.5 mm envelope also clears the Standard minimum. Exact stiffener and component keepouts need the FPC design review.

Sources: [transparent PET launch](https://jlcpcb.com/news/launch-transparent-fpc), [flex capabilities](https://jlcpcb.com/capabilities/flex-pcb-capabilities), [FPC panel guide](https://jlcpcb.com/blog/design-guidelines-flex-pcb-panels), [public quote page](https://cart.jlcpcb.com/quote?plateType=7). Fresh HTML/hash evidence is in `service_evidence`.

## Fixed cost comparison, not a full quotation

JLC's international [PCBA price guide](https://jlcpcb.com/help/article/pcb-assembly-price), updated **2026-10-22**, lists Standard setup$25.56 single/$51.12 double and stencil$8.21 single/$16.42 double. Thus the lighting job's setup+stencil comparison is **$33.77 for identical single-sided leaves versus$67.54 for one double-sided strip**, before any other charges. Standard feeder loading applies to **both Basic and Extended**, listed$1.53 per loaded part type. Identical repeated leaves are one design; different controller/adapter designs are not.

The same newer price guide lists rigid fixtures$8.21 each (1–29:2fixtures, listed$16.42) and FPC fixtures$24.63 each (1–29:2fixtures, listed$49.25). Whether a particular rigid panel requires fixtures is an order-review question: **FR-4 does not imply zero fixture fees**. The capabilities FAQ still says$23.57/FPCfixture; use the newer dated price guide for planning and the actual quote for payment. Hand-solder labor is listed$3.58/order plus applicable joints. Board manufacture, multi-design charges, feeding, parts, losses, special processes, packaging and shipping remain outside the simple setup comparison.

## 2HP versus3HP and release gates

2HP remains the primary envelope to attempt. It now uses a6.1 mm jack body and6.86 mm toggle body, both narrower than the original9 mm jack. However,2HP requires an axial jack cradle, toggle antirotation without oversized standard washers, careful thin-sheet retaining features, local connector relief, and a routed/strained harness. A3's front and rear files are not a release package for these new parts.

3HP adds5.1 mm panel width. With the same sheet offset/thickness, the inner transverse gap becomes11.5 mm and the two0.6 mm LED-board stack leaves4.0 mm nominal per side. It also fits the catalog toggle washer/ring envelopes and makes connector capture and panel ligaments easier. It does not remove the Standard Only LED restriction or automatically lower PCBA fixed charges. Choose3HP if the actual routed controller, pin-trim process, connector envelopes or carrier tolerance stack cannot meet2HP reliably.

Before release: create exact native symbols/footprints; resolve jack TRS contact mapping for TS cables and THRU; finish both native PCB layouts; locate every mated connector and wire bend; define factory lead trimming; complete positive body capture and torque paths; qualify laser-cut hole size; panelize with actual support/tab rules; prepare assembly/CPL/BOM and harness pin maps; obtain the supplier's specific engineering acceptance; and recheck current stock. User assembly should then consist of screws, plug-in cables and covers, with no soldering operation.
