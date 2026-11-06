---
name: component-spec-audit
description: Audit exact electronic-component identities and evidence, and run the end-to-end workflow for adding or replacing a component. Use whenever circuit, schematic, PCB, BOM, firmware, bring-up, substitution or documentation work could depend on a component rating, pin, package, source, CAD asset, publication or interaction.
---

# Component spec audit

Protect the design from plausible-looking but wrong component claims. Manufacturer documents are the authority for component behavior; the inventory is the list of orderable identities; each owner bundle is the evidence for one exact component. The canonical workflow is [circuit/WORKFLOW.md](../../../circuit/WORKFLOW.md); this skill is its entry for component work.

## Audit existing components

1. Run the validator before relying on any record:

   ```sh
   pnpm exec zudo-circuit-doc validate
   ```

   (`pnpm circuit:check` runs the same command.) Note pre-existing failures before editing, and read the `SCOPE:` line: with the manual inventory provider, placements are declared, not bound to a schematic.
2. Resolve the component through `references/inventory.json` by exact manufacturer and complete MPN, supplier order code, function or placement, then load the owner bundle named by the line's `owner_skill`. A bare base name is not an identity. Load subordinate records directly; never answer a subordinate query from its parent.
3. Read the owner's `manifest.json`, `sources.json`, `facts.json`, `coverage.json`, `routing.json`, `interactions.json` and `pin-map.json`. Standalone and subordinate records get the same rigor.
4. Keep the contract's distinctions: source authority versus availability, fact class, provenance, conditions, calculation dependencies and the six verdicts, spelled exactly. The frozen prose is the package's [contract.md](../../../node_modules/@takazudo/zudo-circuit-doc/contract/contract.md).
5. Cross-check claims against the pin map and the current design state. For effects that span components, also load [circuit-spec-integration](../circuit-spec-integration/SKILL.md).
6. If an authoritative source cannot be retrieved, or its retained extract does not support the claim, report `SOURCE UNAVAILABLE` and `UNSOURCED`. Never reconstruct a fact from memory or from a same-name or family part.
7. Report exact fact IDs, source IDs, locators, conditions, calculations and one allowed verdict. Keep proposed design changes separate from the audit result.

## Add or replace a component

Follow [the new-component workflow](references/new-component-workflow.md) in order. It covers identity, the owner bundle, the manual inventory profile, optional CAD, the publication selection, regeneration and checks, and it is the only onboarding procedure; do not create a separate catalog-update skill.

Start a new owner bundle with:

```sh
pnpm exec zudo-circuit-doc new-component SUFFIX
```

Replace every placeholder value the template contains; the validator fails on any that remain. Keep downloads in the ignored `.circuit-cache/sources/` directory, retain short normalized extracts in `sources.json`, and use `pnpm exec zudo-circuit-doc validate --online` or `--refresh-source SOURCE_ID` only for an explicit source refresh.
