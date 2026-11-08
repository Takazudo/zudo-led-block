---
name: component-530470310
description: Resolve exact MOLEX 530470310 (C122442, Plugin,P=1.25mm) evidence for the Zudo LED Block A5 three-pin power cable header. Use whenever 530470310, C122442, its pins, package, placements (controller/J5 x1, power_adapter/J2 x1), limits, substitution or bring-up are relevant.
---

# Exact component record: 530470310

Run `pnpm circuit:check`, read every JSON file in this bundle, and cite fact and source IDs
with their conditions and locators. Preserve `SOURCE UNAVAILABLE`, `UNSOURCED`, `NEEDS BENCH`
and every `OPEN` domain; never replace exact-orderable evidence with memory, a family
datasheet of another variant or same-name vendor data.

- Identity was reconciled by `scripts/a5_catalog.py reconcile`
  (`provenance/a5-catalog/reconciliation.json`). Distributor listings are identity evidence only.
- The pin map and placements are projected from the immutable historical A5 native netlists
  (`engineering/a5/integration/native_schematic/`). They are not fresh A6 design state, are not
  bound by the manual inventory provider, and are not as-built verification.
- Manufacturer document: Molex 530470310 sales drawing is SOURCE UNAVAILABLE (connection closed on 2026-11-08).
- Catalog CAD is disabled (`cad.enabled = false`); the pin-asset check is SKIPPED.
- A5 is not released for manufacture. Nothing here is hardware or manufacturing sign-off.

## Human component reference

Human projection of this bundle: [rec-molex-530470310](/docs/components/records/molex-530470310/).
See also the [component catalog](/docs/components/catalog/) and
[cross-component rules](/docs/components/integration/). These pages are generated from this
bundle's JSON files and add nothing to them.
