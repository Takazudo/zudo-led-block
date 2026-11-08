# A7 R1 open questions and the external evidence needed next

Each item names what is missing, which result it decides and where it came from. None of these can be
answered inside the Cloud batch; they need a stronger document, a supplier answer or a physical part.

| # | Missing evidence | Decides | Current handling |
|---|---|---|---|
| Q1 | PJ-324M jack-axis height above the seating plane (dimensioned drawing, 3D model, or a measured part) | 2HP lead-side and body-side margins | INFERRED 3.0, band 2.6–3.4 (`fact-a7-pj-324m-axis-height`, `parameters.json`) |
| Q2 | PJ-324M pin functions (tip / ring / sleeve / normals) | CV_THRU vs GND mapping; a swap shorts CV to a TS plug sleeve | INFERRED 4=tip, 2=ring, 1=sleeve; NEEDS BENCH continuity test with TS and TRS plugs |
| Q3 | PJ-324M recommended PCB hole/slot sizes | footprint (R4) | not on the drawing; JLC/EasyEDA footprint not yet inspected |
| Q4 | Whether C22355739 ships with a nut, and which nut fits the SOFNG M6x0.5 barrel | front retention and appearance | Same Sky 3.5mm-nut-e and MJ-3502-nut are dimension references only; fit UNVERIFIED |
| Q5 | PJ-324M operating temperature | ratings domain | drawing field blank; JLC lists -25..+75 °C (distributor only) |
| Q6 | Lead trim length the assembler guarantees after wave soldering, and the fillet height | 2HP lead-side margin | ASSUMED 0.7 nominal, 1.0 max |
| Q7 | Cast-PMMA sheet thickness tolerance and laser hole position tolerance from the fabricator | thread engagement, nut edge margin | ASSUMED ±0.2 and ±0.1 |
| Q8 | Rear pocket in cast PMMA: achievable depth tolerance, appearance through the clear front, strength beside a 6.2 mm hole | thread engagement option `rear-pocket` | PROJECT-CHOICE 0.5 ± 0.1 |
| Q9 | Clamp load the PMMA may take between nut and jack body without crazing, and the tightening torque | complete jack load path (R2) | not analysed; A5 rule "do not preload the acrylic" still applies |
| Q10 | PCM13SMTR supply (JLC stock 0 on 2026-11-08) or a confirmed position-to-terminal table for Nidec CSS-1310TB | side switch sourcing | PCM13SMTR selected on function evidence; sourcing OPEN |
| Q11 | JLC answers on transparent PET FPC (see `pet-fpc.md`) | PET leaf feasibility | FR-4 leaf remains reference/fallback |
| Q12 | Classification of LCSC-hosted SOFNG and C&K documents (MANUFACTURER_PRIMARY vs MANUFACTURER_MIRROR) | which facts count as PASS | classed primary with an `authority_note`; reviewer decision |

Physical measurements, printed fit, insertion loads and measured installed depth stay with #8 and #10.
