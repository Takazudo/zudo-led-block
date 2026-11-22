# 0.8 mm controller: actual exported copper, mask, paste and legend review

PCB SHA256: `d83691d6590e013b2a66957b61d76ba2f68bedaaec04789326e1215b2d1bdb2b`.

KiCad 10.0.8 exported these actual Gerbers from the adopted board without refill or board mutation. See `export-receipt.json` and `gerbers/`. The review subset keeps all four copper layers, both mask and paste layers, both silkscreens and the outline; the Gerber job file is deliberately omitted.

`scripts/a7_gerber_inspect.py` measured the plotted primitives themselves (Gerbonara, `../tools/`), with nothing taken from the mask construction record. Results in `raster-inspection.json`:

- **Via tents hold on both faces.** All 116 vias keep mask beyond their copper: smallest web 0.1350 mm on F.Mask and 0.1394 mm on B.Mask against the 0.100 mm rule (`fab/optical-fr4.json` `mask.via_web_mm`, JLC green 1 oz bridge). A mask shape is an opening whether it is a generated rectangle or an ordinary component pad aperture, so a pad opening that overrode a tent would be reported here; none does.
- **Paste is pad apertures only.** 123 flashes on F.Paste and 50 on B.Paste, every one centred on a pad of that face, and no drawn line or region object on either layer.
- **Copper is localized tracks and pads, with exactly one filled region.** F.Cu 252 flashes + 768 drawn objects, In1.Cu 129 + 375, In2.Cu 129 + 355, B.Cu 184 + 612. The only Gerber region object on any copper layer is the single local B.Cu area `buck-return-thermal` recorded in `fab/optical-fr4.json`. The former In1/In2 ground planes are gone: dark coverage inside the rectangular bounds is F.Cu 22.2 %, In1.Cu 10.0 %, In2.Cu 10.7 %, B.Cu 18.8 %.
- **Markings survive.** F.Silkscreen carries 13 drawn objects, the same 13 silk items the board holds; B.Silkscreen is empty, as it is on the board. The minimum-mask construction touches neither.
- Mask openings cover 68.76 % (F) and 70.91 % (B) of the rectangular bounds, so 31.24 % / 29.09 % of that rectangle keeps coating (`residual_mask_fraction_of_bounds`).

`overview.png` shows eight panels left to right: B.Cu, retained B.Mask, B.Paste, F.Cu, retained F.Mask, F.Paste, In1.Cu, In2.Cu. Mask panels are inverted, so black is **retained** coating there and black is copper or paste elsewhere.

The coverage percentages are 20 sample/mm grid estimates over the **16.2 × 62.9 mm rectangular outline bounds**. They are not transmittance, not clipped board area, and not an optical measurement; holes are not subtracted. Native clipped contour geometry lives in `engineering/a7/electronics/controller/optical-geometry.json` and uses a different denominator.

This is a **review-only subset, not an ordering or manufacturing package**, and A7 is not released for manufacture. The plotted geometry was not checked against any fabricator's DFM. Run the stdlib receipt verification before using this evidence:

```sh
python3 scripts/a7_gerber_review.py --verify-receipt engineering/a7/verification/optical/controller/export-receipt.json
```

It rejects changed PCB, Gerber, renderer, tool-lock or review-artifact bytes. The native-side checks (`scripts/a7_optical_check.py`, which proves the same via-web rule on the exported residual mask geometry) and the native gate remain separate and mandatory.
