# Light Block A5 — mechanical assembly study

This folder contains editable CadQuery source, the unchanged A4 acrylic artwork used as an assembly reference, dimensioned component envelopes, assembled/exploded STEP, seven printable support/optical parts per width, and explicit verification results. It is **not a manufacturing release or a passed installed-fit claim**. The fixed parts were checked against each other; the full-length flexible harness scenarios still have reported interference. The finished IDC connector, cable label and permitted wire bends require actual samples and final layout work.

## Rebuild and coordinates

From this directory, with CadQuery, NumPy and Pillow available:

```bash
python build_mechanical.py --variant all
python render_previews.py --variant all
```

`geometry.json` records design dimensions and decisions; `build_mechanical.py` constructs the solid geometry; `cad_kernel.py` supplies the geometry, export and checking methods. Component placements are read from `../electronics/placement_and_connectivity.json`. The native manifest SHA-256 is embedded in each assembly manifest. `manufacturer_source_metadata.json` records source URLs, hashes and interpreted facts. Downloaded drawing caches are not required to rebuild and are omitted from the deliverable archive.

Units are millimetres. X is panel width, Y runs downward, Z points into the rack. The rear surface of the 2.0 mm acrylic is Z=0; its front is Z=-2. The 2HP panel is 9.8 ×128.5 mm and the 3HP panel is 14.9 ×128.5 mm. Both retain the same A4 artwork, holes, slots and engraving topology. Rear rail-body allowance is Y17.1..111.4, inherited from the recovered project. Actual case rails, neighboring modules and rack screws are not specified or modeled.

## Assembly architecture

The shared controller is 8.8 ×62.9 ×1.6 mm, world Y48.5..111.4, frontZ12.6/back 14.2. It is retained atY65 and 97. The 3HP cradle includes inner rails supporting this same 8.8 mm PCB; it does not depend on outer walls that are too far apart. The adapter is 8.8 ×30 ×1.6 mm, Y18..48, frontZ17.4/back 19.0. Its IDC array is centeredY33.4, and its PicoBlade pin row isY46.7.

The two identical 82.5 ×9.0 ×0.6 mm LED leaves are bonded back to back around a 0.1 mm design bond-line reserve. They occupyY22.5..105 andZ19.4..28.4. Their exact symmetric front-edge notches are carried through from the native board outline. One board is flipped end for end; both emit outward. Adhesive selection, thickness control, component clearance and thermal behavior remain assembly checks.

The controller has **one** rear SH4 connector atY60.5, opening toward−Y. It carries both data streams. Each identical leaf has J1 atlocal v 16.5 and J2 atlocal v 66.0, both opening toward+local v. J1 receives GND/VLED/DATA_IN/DATA_OTHER; J2 swaps the two data streams. A cable connects controller→left J1, and another connects left J2→right J1. Right J2 remains unmated. This change removes the earlier controller J4 collision with the switch terminal and D3. It does not qualify the flexible cable routes by itself.

Seven current printable parts are provided per width:

1. Front cradle.
2. Upper controller clamp.
3. Lower controller clamp.
4. Top leaf/adapter cap.
5. Bottom leaf cap.
6. Left optical side with inward flange.
7. Right optical side with inward flange.

The draft middle optical guide was removed so the new link can leave the lower leaf connector. The top and bottom caps and L-shaped optical sides retain the bonded leaves. Stiffness, creep and temperature must be checked on the integrated prototype. Controller clamps independently carry jack insertion loads.

## Controls and load path

The PJ-3582-B jack is modeled with its nominal 6.10 ×10.00 ×12.00 mm body, Ø6 ×3 mm barrel, locator and five pins. The selected jack has no threaded panel retention. Its body front bears on a 0.6 mm PETG collar backed by the acrylic; its rear seats on the mechanically retained PCB. Jack insertion load therefore reaches the PCB substrate and cradle supports, rather than relying only on solder fillets. Withdrawal is restrained by the front collar. Actual axial tolerances, collar fit and panel thickness must be checked before finalizing the seat; neither the PMMA nor PCB should be preloaded or bowed.

The Dailywell 1MS3T1B1M2QES-5 body is 6.86 ×12.70 ×8.89 mm. The selected M2 terminals have 4.70 mm pitch and a 1.50 mm shoulder. At the current PCB plane, the switch body front/rear areZ2.21/11.10. Its terminal tails are modeled trimmed toZ15.2, at most 1.0 mm behind the PCB. The slots are 1.8 ×1.2 mm with the native land-pattern update. The front nut and cradle provide retention and antirotation. The larger washer/ring options do not fit the 2HP width and are not silently included.

Front M2 screws and small washers attach the cradle to the acrylic. The upper controller clamp is 1.2 mm thick, and its small front-face relief clears the J3 solder-pad projection. The rear nut is raised above the PCB, rather than sitting on solder pads. The lower clamp is separate from the optical structure. Supplier-specific hardware dimensions, solder heights and acrylic tightening torque remain assembly gates.

The keyed C5665 header is modeled from its maximum body dimensions:20.8 ×9.1 ×8.9 mm. Its conflicting source tail dimensions are not resolved by assumption; factory trimming to≤1.0 mm behind the adapter PCB is required by this assembly. The Molex 530470310 tails are retained at their nominal 2.3 mm length; the leaf notches clear the middle adapter pin. The Molex drawing recommends a thinner PCB than the 1.6 mm project board, so minimum protrusion and soldering access require factory confirmation.

## Optical and printed geometry

The general structural web target is 1.2 mm. The backed jack collar and local 2HP SH4 relief skins are 0.6 mm exceptions. The 2HP connector pockets leave the necessary mated housings visible and preserve a thin optical wall; they are not arbitrary cuts through hidden connector bodies. The 3HP relief follows the actual connector envelope and leaves an inward flange bridge around the right IDC access window. All seven intended parts are connected single CAD solids, and their final welded meshes are checked separately during 3MF packaging.

The fixed rear structure reachesZ29.8, leaving 0.2 mm against the 30 mm nominal target. This is a geometric allowance, not a tolerance budget or an installed-fit approval. Body tolerances, PMMA thickness, printed shrinkage and finished cable dimensions can consume it.

The nominal optical material is PETG, but no matching saved PETG printer template was available. The supplied 3MF uses the saved **H2D 0.6 PLA** settings unchanged and is labeled **PLA fit-check only**. It is unsliced; no Bambu Studio executable was available. It is useful for a dimensional review of parts, not a PETG optical, thermal or strength qualification. The geometry is also supplied as STEP/STL for a proper PETG profile and slice review.

## Flexible harnesses: unresolved, included in the model

The complete CAD includes three power wires and eight SH wires as full-length route scenarios. Their centerline lengths are around 50 mm, with the actual values recorded in `assembly_manifest.json`. These paths are not silently shortened to the direct connector distance. Their individual wire/side-wall intersections and minimum radii are recorded in `verification.json`; they are **not acceptable final physical routes**. A mathematically valid STEP solid does not prove that a real cable can take the depicted bend or that overlapping wires can be assembled.

The Molex 151340300 drawing defines a 50 ±6 mm free span between the wire-exit shoulders, and it includes a 12.7 ×35.5 mm flag label. The drawing does not define the assembled label fold or its storage pose. That required label is explicitly unmodeled rather than replaced by an invented tiny box. The selected SH cable's exact free-length datum, housing handles, insulation diameter and allowable bend radius also need confirmation. The current tube diameter reserve is 0.8 mm; reported curve radii are design geometry only, not a manufacturer rating.

The IDC ribbon exits the short side of its socket, along+X in this model. The visible R3 scenario uses 0.8 mm ribbon thickness and 12.7 mm width. The reference socket is Würth 61201023021, with 17.38 ±0.15 mm length,7.0 mm width and 6.9 mm main-body height. It is **not an identified component inside the finished Doepfer cable**. The model's 6 mm mating overlap and wire-exit plane are assumptions; the full strain-relief cap height remains unverified, and its reported header/ribbon conflict must be resolved from the real mating drawing/sample.

With those stated assumptions, the 2HP ribbon reachesX11.8, or 2.0 mm beyond the 9.8 mm panel envelope, while the corresponding 3HP envelope reachesX14.35 and leaves 0.55 mm to the 14.9 mm edge. This measures the required rear neighboring clearance in the scenario. It does not establish absolute 2HP impossibility, nor does it prove 3HP installation. The case and adjacent module must supply the clearance, and the actual cable bend may differ. Moving the adapter remotely would move this constraint outside the unit; it is not counted here as a solution to the installed 30 mm target.

## Verification interpretation and next gates

`exports/<width>/verification.json` includes every modeled part. Fixed-solid intersections use CAD Boolean volumes. Cable checks use exact CAD centerline-to-solid or centerline-to-centerline distances against the modeled 0.4 mm wire radius. Mated contact/end-face contacts are identified explicitly. No parts are silently excluded. Bounding boxes use analytic BRep bounds without triangulation, and STEP exports are imported again to check validity, solid counts, extents and total-volume differences. These checks concern the saved geometry only.

The next release gates are: finish controller routing and native electrical checks; correct the reported flexible-wire storage interference; establish the actual finished IDC mating/strain-relief envelope and neighboring clearance; fit the cable label; confirm pin/terminal trimming and solder clearances with the assembly house; review the exact acrylic and printed fit/torque stack; then slice and inspect the selected PETG material and print process. Build the integrated prototype after those gates are resolved. No separate optical test PCB or prototype quantity is prescribed by this folder.

SWD pads are on the controller rear row at world Y80.7. Production/service access requires removing the optical leaves and harness or using a qualified fixture; the geometry does not promise in-place probe access through installed optics.
