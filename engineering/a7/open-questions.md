# A7 R1 open questions and the external evidence needed next

Each item names what is missing, which result it decides and where it came from. None of these can be
answered inside the Cloud batch; they need a stronger document, a supplier answer or a physical part.

| # | Missing evidence | Decides | Current handling |
|---|---|---|---|
| Q0 | A SOFNG-hosted PJ-324M drawing and a C&K-hosted PCM13SMTR datasheet to compare with the LCSC-hosted copies | whether any drawing value can count as PASS | both maker hosts SOURCE UNAVAILABLE on 2026-11-08; all drawing facts UNVERIFIED / UNSOURCED, values retained, study inputs labelled MIRROR |
| Q1 | PJ-324M jack-axis height above the seating plane (dimensioned drawing, 3D model, or a measured part) | 2HP lead-side and body-side margins | INFERRED 3.0, band 2.6–3.4 (`fact-a7-pj-324m-axis-height`, `parameters.json`) |
| Q2 | PJ-324M pin functions (tip / ring / sleeve / normals) | CV_THRU vs GND mapping; a swap shorts CV to a TS plug sleeve | INFERRED 4=tip, 2=ring, 1=sleeve; NEEDS BENCH continuity test with TS and TRS plugs |
| Q3 | PJ-324M recommended PCB hole/slot sizes | footprint (R4) | not on the drawing; JLC/EasyEDA footprint not yet inspected |
| Q4 | Whether C22355739 ships with a nut, and which nut fits the SOFNG M6x0.5 barrel | front retention and appearance | Same Sky 3.5mm-nut-e and MJ-3502-nut are dimension references only; fit UNVERIFIED |
| Q5 | PJ-324M operating temperature | ratings domain | drawing field blank; JLC lists -25..+75 °C (distributor only) |
| Q6 | Lead trim length the assembler guarantees after wave soldering, and the fillet height | 2HP lead-side margin | ASSUMED 0.7 nominal, 0.5 min, 1.0 max |
| Q7 | Cast-PMMA sheet thickness tolerance and laser hole position tolerance from the fabricator | thread engagement, nut edge margin | ASSUMED ±0.2 and ±0.1 |
| Q8 | Rear pocket in cast PMMA: achievable depth tolerance, appearance through the clear front, strength beside a 6.2 mm hole | thread engagement option `rear-pocket` | PROJECT-CHOICE 0.5 ± 0.1 |
| Q9 | Clamp load the PMMA may take between nut and jack body without crazing, and the tightening torque | complete jack load path (R2) | not analysed; A5 rule "do not preload the acrylic" still applies |
| Q10 | PCM13SMTR supply (JLC stock 0 on 2026-11-08), or a per-position terminal table (or a bench continuity check) for an in-stock alternate: Alps Alpine SSSS812201 C160878, SHOU HAN MSK13C02 C2681567, Hroparts K3-1310S-E1 C145851, Nidec CSS-1310TB C2921714 | side switch sourcing | PCM13SMTR stays selected on its printed table; none of the alternates prints one; sourcing OPEN |
| Q11 | JLC answers on transparent PET FPC (see `pet-fpc.md`) | PET leaf feasibility | FR-4 leaf remains reference/fallback |
| Q11a | Supplier and process for laminating the clear PC carrier to the PET films with OCA after reflow, as factory assembly needs | whether the PET leaf can be built at all | no supplier or process identified; R2 PET study assumes the lamination (`mechanical/README.md`) |
| Q11b | SH plug unmating pull force, and the pad-to-film and film-to-OCA peel strength | PET leaf connector retention | not covered by the R2 buckling check (mating push only); force UNSOURCED; physical test with #10 |
| Q11c | PET leaf in the 2HP variant | 2HP with PET | PET built for 3HP only; X stack differs from FR-4 by 0.02 mm, so the 3HP result carries over; 2HP stays parked |
| Q11d | **Blocking for the PET variant only.** A 1-layer PET film cannot carry the A5 leaf copper: all five data nets (DATA_IN, DATA_1_2, DATA_2_3, DATA_3_4, DATA_OTHER) run on B.Cu through 11 vias | whether the 1-layer stack R2 modelled (1.28 mm) is usable | needs a new single-layer leaf layout or the 2-layer film (Q11e); R4 `verification/pet_leaf/` (`pet_1layer.copper` NOT_MET). The FR-4 default leaf is not affected |
| Q11e | **Blocking for the PET variant only.** Whether JLC offers plated vias on 2-layer transparent PET (the capabilities page gives 2-layer transparent 0.24 mm but does not say so) | whether the A5 copper can move to a 2-layer film; 2-layer stack 1.48 mm leaves about 0.06 mm per side in the cap slot on paper (R2 to re-check) | not stated by JLC; question not sent. On 2-layer rules the A5 copper otherwise passes (tracks, clearances, 0.6/0.3 vias, 0.3 mm copper to edge). The FR-4 default leaf is not affected |
| Q11f | **Blocking for the PET variant only.** WS2812B-2020 and SH4 pad gaps are 0.4 mm, so after JLC's 0.1 mm coverlay expansion the coverlay bridge is 0.2 mm, below the 0.5 mm minimum: the bridges are removed and adjacent pads share one opening | solder bridging risk at LED and connector pads on PET | ask JLC whether that is acceptable for SMT assembly on transparent PET, or whether a solder mask is offered; R4 `verification/pet_leaf/` (`coverlay_bridges` NOT_MET). The FR-4 default leaf is not affected |
| Q12 | Classification of LCSC-hosted SOFNG and C&K documents | which facts count as PASS | decided: MANUFACTURER_MIRROR (coordinator, 2026-11-08); see Q0 |

Physical measurements, printed fit, insertion loads and measured installed depth stay with #8 and #10.

## Width decision (R2, 2026-11-08)

3HP (14.9 mm, centred jack, 1.6 mm FR-4, untrimmed leads) is the working candidate and the default variant of
the generated artwork, supports and CAD. 2HP (0.6 mm body-side offset, 0.8 mm FR-4, trimmed leads) stays a
fully parameterized open candidate: its worst corner is −0.33 mm lead side and −0.15 mm body side, with the
axis height INFERRED and the trim unconfirmed. It reopens when Q1 or Q6 evidence makes every worst-case hard
margin positive; the break-even values are in `mechanical/layout.md`.
