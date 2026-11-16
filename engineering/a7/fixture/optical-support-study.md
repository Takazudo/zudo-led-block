# 0.8 mm controller fixture: ongoing support redesign

Status: **NOT ACCEPTED**. This is a digital exploration, not fixture release or
physical contact verification. The saved native geometry and STEP retain their
historical identities; neither has been rebound to the optical controller.

The adopted board range is 0.7–0.9 mm (0.8 mm ±0.1 mm published JLCPCB finished
thickness tolerance). Using the historical carrier with the original conservative
strip model gives 0.267190 mm probe-load deflection against 0.1 mm maximum.
The best force-deficient plunger pair is (14.1,21.7), (14.2,16.5) mm in board
coordinates: minimum summed force 12.574228 N versus required 12.7 N, with
0.401124 mm sag deducted from compression. The resultant criterion also fails.
`a7_fixture_relief.design` exposes the rejected layout instead of borrowing old PASS.

Finite geometric trials did not resolve the failure: probe opening half-widths
0.8, 0.7, 0.6 mm; pressure-plate far edges Y32.5,35.5,38.5; near edges
Y10.5,7.5,4.5 mm. All retain only 270 legal F-face sites and no force-feasible pair.
None of these trial dimensions has been adopted in the fixture CAD.

A candidate additional insulating support arrangement is three Ø1.5 mm posts at
(14.1,21.7), (10.8,25.6), (14.8,28.5) mm. These are **exploratory contact locations**,
not floating supports accepted as a completed fixture. They require a mechanically
attached carrier/insert, actual native checks including solder envelopes and
probe clearance, manufacturing wall/cutter checks, and full CAD interference.
The longest-axis strip approximation cannot represent these diagonal supports.

`scripts/a7_fixture_plate.py` therefore explores a distinct rectangular C1 plate
model (Bogner–Fox–Schmit tensor cubic Hermite elements). It retains the assumed
18 GPa modulus; it does not promote typical laminate values to measured properties.
The separate test suite checks rigid-plane zero strain, total point force, and
convergence to the closed-form simply-supported sinusoidal-load plate solution.
Relative error decreases from 0.2899% at 4×4 elements to 0.01192% at 8×8.
These are solver benchmarks, **not a fixture PASS**. SciPy/numpy are experimental
requirements; missing dependencies skip this optional benchmark explicitly.

Actual fixture acceptance requires unilateral contact: the carrier can push up,
not pull the board down. Bilateral-support results are diagnostic only. The initial
250-iteration actual-geometry unilateral solve did not converge, so its low bilateral
deflections cannot justify acceptance. A bounded corrected active-set experiment
is being evaluated separately. Independent mechanical review, convergence checks,
force corners, native identity and CAD remain required before replacing any gate.
