---
name: component-ws2812b-2020-v6
description: Resolve exact Worldsemi WS2812B-2020-V6 (C52917434, SMD2020-4P) evidence for the Zudo LED Block A5 addressable rgb led. Use whenever WS2812B-2020-V6, C52917434, its pins, package, placements (led_leaf/D1 x2, led_leaf/D2 x2, led_leaf/D3 x2, led_leaf/D4 x2), limits, substitution or bring-up are relevant.
---

# Exact component record: WS2812B-2020-V6

Run `pnpm circuit:check`, read every JSON file in this bundle, and cite fact and source IDs
with their conditions and locators. Preserve `SOURCE UNAVAILABLE`, `UNSOURCED`, `NEEDS BENCH`
and every `OPEN` domain; never replace exact-orderable evidence with memory, a family
datasheet of another variant or same-name vendor data.

- Identity was reconciled by `scripts/a5_catalog.py reconcile`
  (`provenance/a5-catalog/reconciliation.json`). Distributor listings are identity evidence only.
- The pin map and placements are projected from the immutable historical A5 native netlists
  (`engineering/a5/integration/native_schematic/`). They are not fresh A6 design state, are not
  bound by the manual inventory provider, and are not as-built verification.
- Catalog CAD is disabled (`cad.enabled = false`); the pin-asset check is SKIPPED.
- A5 is not released for manufacture. Nothing here is hardware or manufacturing sign-off.

## Human component reference

Human projection of this bundle: [rec-ws2812b-2020-v6](/docs/components/records/ws2812b-2020-v6/).
See also the [component catalog](/docs/components/catalog/) and
[cross-component rules](/docs/components/integration/). These pages are generated from this
bundle's JSON files and add nothing to them.
