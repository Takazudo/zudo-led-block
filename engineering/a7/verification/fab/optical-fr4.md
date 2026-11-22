# Optical R3: 0.8 mm rigid FR-4 manufacturing inputs

Issue #87 records the owner's 2026-11-17 JST direction. This is a rigid FR-4
prototype for observing its unmeasured, dull translucency. The former thin PET
flex candidate is withdrawn. A5 source bytes and historical order approvals are
not changed or inherited as approval of this revision.

`optical-fr4.json` owns the adopted lamination and local copper/mask policy.
Controller stackup `JLC04081H-3313` was obtained from the public JLC impedance
selector's read-only API. It specifies 35 / 15.2 / 15.2 / 35 µm copper,
99.4 µm 3313 prepreg on each side and a 500 µm core: 799.2 µm compressed total,
ordered as nominal 0.8 mm. Finished thickness tolerance is ±0.1 mm; it is not
±10%. The two-layer leaf's 730 µm core is a calculated target with 35 µm copper
on each side, not a manufacturer-confirmed core SKU. Final fabrication DFM must
reconcile the selected construction and finish with these inputs.

Both boards specify ENIG as the project choice for exposed copper and fine-pitch
assembly. Supplier acceptance of the unusual mask coverage, local dams, tented
vias, edge handling and 0.8 mm assembly support is still required before release.
The PCBA service is not qualified merely by changing the thickness field.

F.Mask and B.Mask graphics are **positive openings**. The construction helper
opens the complement of individually recorded protection rectangles on each
side. Protection is limited to pad solder dams/wicking barriers, narrow surface
track corridors, via tents and retained polarity/assembly silk backing.
Surface track corridors were necessary: the first leaf proposal produced 29
native `solder_mask_bridge` violations. The corrected leaf has zero DRC findings;
its effective remaining mask is about 25.35% front and 13.07% back, as exported
from the actual native aperture geometry. These are geometric coverage numbers,
not optical transmittance. Paste remains the original footprint apertures.

Global front/back via tenting is explicit in each native board. The source gate
rejects per-via overrides and any opening that intersects a protected via island.
Actual plotted Gerbers are reviewed separately: source rectangles alone cannot
prove that normal pad apertures or plotting settings preserve the intended mask.
The board-bound `optical-mask.json` inventories every retained island and reason.

`mask.via_web_mm` adds the rule that was missing from that chain: every via keeps
at least 0.10 mm of mask between its copper and **any** effective opening, a
generated rectangle and an ordinary component pad aperture alike (the same JLC
green 1 oz mask-bridge row). The router therefore keeps via copper that far from
every pad aperture, so no via sits in or against a pad. Two independent checks
enforce it on the adopted bytes: `scripts/a7_optical_check.py` on the native
residual-mask geometry of `optical-geometry.json`, and
`scripts/a7_gerber_inspect.py` on the plotted Gerber primitives. The controller's
measured worst case is 0.135 mm front and 0.139 mm back over all 116 vias
(`verification/optical/controller/`).

The leaf has no zones. The controller permits only the named, bounded bottom
`buck-return-thermal` GND patch below U2/C1; its location and maximum area are in
the specification. It provides local return and heat spreading requested by the
AP63205 layout guidance. No broad plane is allowed on any copper layer. GND is
real routed copper; the local patch must be physically connected and must not
bridge the independent power and signal return branches outside J5.2.

The AP63205 manufacturer's layout guidance recommends bottom ground copper and
short capacitor connections. Removing the old broad plane invalidates its former
shielding and thermal assumptions. The new digital review therefore checks real
return paths, supply loss, local decoupling, the buck loops and the all-layer
separation of every CV net from the switching and data nets; its result and
margins for the adopted controller are in `../electrical_review.md`. A legacy current-sizing equation is an engineering screen only;
enclosure temperature, switching interference, light transmission and assembly
remain physical work under issues #8/#10/#13. No measured thermal or optical PASS
is implied by native DRC or by the preview.

Sources and retrieval identities are in `optical-fr4.json`. Reviewed PCB bytes
are authoritative; construction helpers write staging outside the repository.
Final native gate, route reproduction, actual Gerber review and downstream
hash checks must refer to those same bytes before this design can be integrated.
