# A4 process review: full rear frost with clear negative lettering

Review date: 2026-11-06 Asia/Tokyo (2026-11-05 UTC retrieval session).

## Conclusion

The proposed appearance is feasible as a laser artwork strategy: start with clear cast acrylic, engrave the background on the rear, and omit the letter strokes. Rear frosting appears through the smooth front face. The full-area negative mask is an engineering inference from established acrylic engraving behavior and filled-area processing; the sources below do not certify this exact 2HP panel or its final visibility under the planned LEDs.

The A4 files implement this strategy directly. They do not substitute pre-matte stock, a dark ink print, or positive engraved letters. Pre-matte acrylic would remain matte in the skipped letters, so omission alone would not create the requested clear lettering. The untouched front surface remains glossy even though the plate looks foggy through its frosted rear.

## Primary evidence

### 1. Trotec: acrylic material and processing guidance

Source: [Tips and tricks for processing acrylic](https://www.troteclaser.com/en-us/helpcenter/materials/material-usage-hints/material-handling-acrylic).

The official guidance prefers cast acrylic for white, high-contrast engraving. It describes light surface engraving as producing a white result, recommends processing from the rear for appearance/durability, and instructs mirroring the artwork. It also states that settings depend on the material and desired finish. This supports a shallow rear-frosting operation and the mirror convention; it does not supply Elecrow stock identity, laser settings, a defined haze value, or a guaranteed panel strength.

Retrieval references for the parent report: `turn180search0`, `turn193view1`. Relevant sections: “Cast acrylic (GS)” and “Parameters for laser engraving acrylic.”

### 2. Epilog: black-filled artwork defines raster processing

Source: [Epilog EXT manual, 2010](https://www.epiloglaser.com/downloads/pdf/ext_4.22.10.pdf), Section 8, Basic raster mode, printed pages 108–109.

The manufacturer describes black-and-white processing in which black areas fire the laser. This establishes why the supplied negative mask fills the background and leaves the letter strokes empty. It is a process explanation, not an assumption that Elecrow uses this machine or its import conventions. The supplier must assign the engraving operation and preserve filled regions on import.

Retrieval reference: `turn181view1`, lines 2134–2147.

### 3. Gravotech: negative engraving when acrylic lightens

Source: [Master the art of photo engraving](https://www.gravotech.us/articles/master-art-photo-engraving), “Negative etching.”

The official article explains that engraving lightens acrylic and discusses negative artwork. Its context is photograph reproduction, so it supports the general inversion principle; it is not a demonstration of this particular panel. The same article mentions mirroring for acrylic work.

Retrieval references: `turn181view0`, `turn193view0`, especially lines 74–75 and 135–142.

## Exact design inference

Let M be the acrylic material face, L the letter/icon strokes, and S the small hidden seating masks. The engraved region is:

`ENGRAVE = M − L − S`

M already excludes all through-holes. A letter such as O is a ring-shaped stroke L, not a filled disk. Subtracting that ring leaves its center connected to the engraved process as a separate island. The generator preserves each island in both SVG and DXF.

The physical panel remains nominally 2 mm. The 0.02 mm BRep extrusion used to calculate Boolean regions is a software aid, not a laser depth requirement. No reverse/negative option should be applied a second time in the machine software: the delivered rear file is already inverted in region selection and mirrored geometrically.

## Scope and practical limits

Only appearance and masks change in A4. A3 through-cut files and panel STEP remain byte-identical snapshots. The current nut/washer silhouettes and apertures are references while stock-first switch/jack selection is under review; therefore the package is explicitly not order-ready mechanical data.

Small seat exclusions preserve the present smooth seating regions without introducing broad clear borders. Their exact dimensions and visibility assumptions are in the README and JSON. They are not a strength analysis. The panel has no countersink changes or assigned engraving depth.

Clear-letter contrast will depend on what is behind the letters and on lighting. The previews use a colored background solely to show transparency; they do not guarantee dark or bright labels in operation. Full frosting also does not by itself establish uniform front illumination. The integrated module's light paths remain a separate design question.

Elecrow's exact cast stock, filled-area engraving import, finish target, and final hardware registration need to be confirmed as part of the integrated-prototype manufacturing review. No standalone optical-coupon testing is introduced as a prerequisite, and no order has been placed.
