# HISTORICAL — withdrawn clear-PET leaf export (do not read as current)

These files are the 3HP assembly built with the **clear PET/FPC leaf comparison**, on the **old 1.6 mm
controller and 0.6 mm leaf** model. The owner withdrew PET/FPC on 2026-11-17 JST (#87); the current
revision is a 0.8 mm rigid FR-4 leaf pair and a 0.8 mm controller.

- **Status: historical record, retained on purpose.** It is kept so the comparison, its reasoning and the
  supplier questions it raised stay auditable. Nothing here is current evidence, a current variant, or a
  fit, optical or manufacturing approval, and its PASS/clean-intersection figures belong to the old board
  identity and the old layout hash.
- **Not regenerated.** `build_a7_mechanical.py` has no leaf option any more: current routine generation
  produces `exports/3hp/` and `exports/2hp/` only. Running the builder will not refresh this directory,
  and its `verification.json` will not match the current `layout.json` hash.
- Written-up history: `../../README.md` → *Withdrawn PET comparison (historical)*, `../../layout.json` →
  `leaf_comparison.withdrawn_variants`, and `engineering/a7/verification/pet_leaf/`.
- Still referenced as if current by files this directory does not own: `preview/a7/manifest.json` and
  `circuit/publication/assets.json` publish `3hp_pet.glb` as a preview variant, and
  `scripts/a7_preview.py` lists it as a selectable target. Those are the preview/docs owner's to relabel
  or drop; see the #87 hand-over notes.
