# New 0.8 mm leaf: actual exported mask/copper review

PCB SHA256: `bcf2e35d767221f5a9db0cd16769a2e503a672f522fd4f32f78012cdeb494cf9`.

KiCad 10.0.8 exported these actual Gerbers without refill or board mutation. See `export-receipt.json` and `gerbers/`; `overview.png` shows, left to right, F.Cu, B.Cu, retained F.Mask, retained B.Mask and F.Paste. Both policy_docs and the integration agent visually inspected this image.

- Copper is localized tracks and pads: F.Cu 47 flashes + 47 lines, B.Cu 11 flashes + 15 lines; no filled copper region objects. This is a two-layer board.
- Both mask files declare negative material polarity. Their drawn shapes are openings. The inverse views show the retained trace isolation corridors, solder dams and via protection instead of interpreting openings as retained coating.
- F.Paste has 36 pad flashes; B.Paste is empty. No blanket paste aperture was introduced.
- Eleven via centers on each face, plus four offsets of 0.1 mm around each center, remain covered in the rendered mask. These **samples do not prove the entire protection inventory**; use the separate native geometry/protection checks as well.

`raster-inspection.json` contains antialiased 40 pixel/mm estimates in the **9 × 82.5 mm rectangular viewport**. It does not clip out the two outline notches and is not exact board-area geometry. Approximate mask openings are F 74.53% / B 86.77%; these numbers are not transmittance or optical measurements. Native clipped contour areas use a different denominator (738.5 mm²) and must not be substituted for these raster estimates. Gerber pad flashes include drill locations; separate drill files must be used when actual holes matter.

A retained mask corridor over already opaque copper limits solder wicking and accidental bridges. Pad-perimeter dams, via tents and polarity legend backing are recorded in `engineering/a7/electronics/led_leaf/optical-mask.json`. Manufacturability, exposed copper finish, local coating tolerances, optical appearance and physical soldering remain unmeasured/unreleased.

This is a **review-only subset**, not an ordering package. The exported `.gbrjob` is deliberately omitted. Run the stdlib receipt verification command in `../tools/README.md` before using this evidence; it rejects changed PCB/Gerber/script/tool-lock/artifact identities, including an old A5 leaf copied into the current path.
