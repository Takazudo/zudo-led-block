---
name: component-pmeg4010cej-115
description: Resolve exact Nexperia PMEG4010CEJ,115 (C50704, SOD-323F) evidence for the Zudo LED Block A5 eurorack rail reverse-polarity schottky diode. Use whenever PMEG4010CEJ,115, C50704, its pins, package, placements (controller/D1 x1, controller/D2 x1), limits, substitution or bring-up are relevant.
---

# Exact component record: PMEG4010CEJ,115

Run `pnpm circuit:check`, read every JSON file in this bundle, and cite fact and source IDs
with their conditions and locators. Preserve `SOURCE UNAVAILABLE`, `UNSOURCED`, `NEEDS BENCH`
and every `OPEN` domain; never replace exact-orderable evidence with memory, a family
datasheet of another variant or same-name vendor data.

- Identity was reconciled by `scripts/a5_catalog.py reconcile`
  (`provenance/a5-catalog/reconciliation.json`). Distributor listings are identity evidence only.
- The pin map and placements are projected from the immutable historical A5 native netlists
  (`engineering/a5/integration/native_schematic/`). They are not fresh A6 design state, are not
  bound by the manual inventory provider, and are not as-built verification.
- Manufacturer document: Nexperia PMEG4010CEJ product data sheet v.3 (2022-10-01), acquired 2026-11-11 through the owner's built-in browser. Pinout and ratings are primary-source confirmed; v.3 removed packing information, so the `,115` packing variant stays UNSOURCED (distributor identity only).
- Catalog CAD is disabled (`cad.enabled = false`); the pin-asset check is SKIPPED.
- A5 is not released for manufacture. Nothing here is hardware or manufacturing sign-off.

## Human component reference

Human projection of this bundle: [rec-pmeg4010cej-115](/docs/components/records/pmeg4010cej-115/).
See also the [component catalog](/docs/components/catalog/) and
[cross-component rules](/docs/components/integration/). These pages are generated from this
bundle's JSON files and add nothing to them.
