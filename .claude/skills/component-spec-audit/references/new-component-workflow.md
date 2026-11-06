# New component workflow

Run these steps from the project root, in order. This checklist owns a new or replacement component from its exact identity through the committed, published reference. It is the detailed form of Workflow B in [circuit/WORKFLOW.md](../../../../circuit/WORKFLOW.md). It does not authorize an unresolved electrical or firmware design change.

## Preconditions

Resolve before editing:

- manufacturer, complete MPN (suffix and package variant), supplier order codes;
- intended function, placements (board and reference designator) and population (fitted, not fitted, hand-fitted, external);
- the source that will establish identity and behavior;
- whether the part needs CAD assets on a board, and whether its page and previews will be published.

Do not invent a reference designator, pin, fact, order code or document kind to make the workflow progress. Stop and record the missing design or review decision in next actions instead.

Run `pnpm circuit:check` first and note what already fails.

## 1. Lock the identity

The configured inventory provider (`inventoryProvider` in `circuit.config.ts`) decides how identity is locked.

### Manual provider (the default)

Edit `.claude/skills/component-spec-audit/references/inventory.json`:

1. Add one line per orderable identity, with the same keys as existing lines (`line_id`, `mpn`, `manufacturer`, `lcsc`, `package`, `dnp`, `owner_skill`, `identity_state`, `source_state`, `function`, `placements`; `mounting` defaults to `pcb`). The validator names any key that is missing.
2. Identity is a unique `line_id` plus a unique (manufacturer, complete MPN) pair. Two manufacturers may share an MPN; each line then resolves only with its manufacturer qualifier.
3. `lcsc` must be present. Use `""` unless you read a C-number from the supplier's listing for this exact part. Never fabricate, guess or reuse a C-number from a similar part.
4. Optional `suppliers: [{ "supplier": "...", "order_code": "..." }]` records other order codes. They are display-only and create no routing aliases.
5. `placements` may be `[]`. Placements are **declared, not verified**: the manual provider does not bind them to a schematic, and the `SCOPE:` line printed by the validator says so. Repeat that limit in your report.
6. `identity_state` is `VERIFIED` or `UNRESOLVED`; `source_state` is `AVAILABLE` or `SOURCE UNAVAILABLE`. Keep them consistent with the owner bundle; the validator warns when the summary lags the evidence.
7. Update the reviewed `assertions` counts (`orderable_lines`, `fitted_lines`, `dnp_or_hand_fit_lines`) by hand. Do not change a count only to make a check pass.

### Generator provider (optional)

When the project configures a generator-based provider, the generator specification is the identity lock: add the exact part to the configured spec, regenerate the schematic with the project's generator, commit the spec and its output together, and then reconcile the inventory line against it. Do not hand-edit an inventory line to disagree with its generator.

## 2. Build the evidence owner

1. Create the bundle from the package template:

   ```sh
   pnpm exec zudo-circuit-doc new-component SUFFIX
   ```

   This creates `.claude/skills/component-SUFFIX/` and refuses an existing directory. Use a suffix derived from the exact part.
2. Replace **every** placeholder in all eight files. Fill `manifest.json`, `sources.json`, `facts.json`, `coverage.json`, `routing.json`, `interactions.json` and `pin-map.json` from audited sources (Workflow C for acquisition). Record units, conditions, provenance, verdicts, calculation dependencies, open domains with their `blocking_fact_ids`, routing cases and the real pin map. Retain short normalized extracts, not whole documents.
3. Keep the bundle `SKILL.md` frontmatter valid: `name` equals the directory name, and `description` is at least 80 characters and says when to use it.
4. The record's `mpn`, `manufacturer`, `lcsc` and `package` must equal the inventory line; `owner_skill` on the line names this bundle.
5. Add the line's positive and negative cases to `.claude/skills/component-spec-audit/references/direct-routing.json`. Add a vendor qualifier to `external-vendor-qualifiers.json` only when routing needs one.
6. When the part affects another component or domain, add or update a rule in `.claude/skills/circuit-spec-integration/references/rules.json` (see the circuit-spec-integration skill). Evidence-chain stages stay `OPEN` until real evidence exists.

Run `pnpm circuit:check` now; fix every failure the new bundle introduced.

## 3. CAD assets (optional)

Only when the part goes on a board and `cad.enabled` is `true` in `circuit.config.ts`. With CAD disabled, the pin-asset check is reported as SKIPPED; say so in the report rather than implying pins were checked.

1. Acquire the symbol, footprint and model (Workflow D): a pinned KiCad library release tag, the manufacturer, or `easyeda2kicad` for an LCSC-listed part. Import into `.circuit-cache/cad/` first, never straight into the libraries.
2. Merge only this part's symbol into the configured symbol library. Never overwrite a shared multi-symbol library with importer output.
3. Place the footprint in the configured footprint roots. If the config names both a master root and a library root, keep the two `.kicad_mod` copies byte-identical (`cmp -s`).
4. A footprint with no declared `(model ...)` reference is publishable as footprint-only; its page states that the 3D model is unavailable. When a footprint does declare a model, place a valid WRL at the referenced path inside the configured model root. The web viewer renders WRL only. A STEP file is optional; if present, it must share the WRL's basename. Review the declared model path and its offset, rotation and scale. A declared but missing, invalid or out-of-root WRL fails the check; do not convert a STEP file to hide that gap.
5. The pin map's `symbol` and `footprint` must exist in the configured libraries, and symbol pin numbers, footprint pad numbers and pin-map pins must be identical sets. Check them against the datasheet yourself; the validator checks only agreement.
6. Write the receipt `circuit/cad-receipts/ASSET_ID.receipt.json` from `circuit/templates/cad-asset-receipt.json`, with the fidelity class (`exact-vendor`, `family`, `derived`, `unavailable`) and the evidence for it.

## 4. Choose what becomes public

Edit `circuit/publication/selection.json` in the same change. Nothing is published unless it is listed.

1. Add the record to `recordIds`, every public source to `sourceIds`, and every approved outbound URL to `linkableSourceIds`.
2. Add exactly one document decision for the record: either one `documentSelections` entry with its audited `sourceId` and truthful `documentKind`, or one `documentExceptions` entry with `recordId` and an honest `reason` when no document is available to publish. The selected records must be partitioned between the two lists, with no overlap or gaps. Use `datasheet`, `specification` or `drawing` only for a reviewed PDF: inspect the bytes (`%PDF-`) and confirm the title and part list cover the exact MPN. Use `source-record` for a reviewed non-PDF source; it is labeled **Source record** and does not promote its authority or applicability. A product page, distributor listing or HTML denial remains non-PDF evidence even if its URL ends in `.pdf`.
   For an exception, say what sources were reviewed and what document remains unavailable. Do not relabel distributor evidence as a manufacturer document or invent a URL. Keep relevant source IDs in `sourceIds` so they remain listed under Sources; include outbound URLs in `linkableSourceIds` only when reviewed for publication. The reason is published as the document availability text under the existing `reference.document.availability` matrix key.
3. Update the reviewed `expect` locks: `records`, `sources`, `integrationRules` and `packages` (the number of selected footprint/model packages; `0` is valid). Keep them explicit; never infer them.
4. A file deliberately published under `doc/public/` (for example a redistributable drawing) needs an entry in `circuit/publication/assets.json` with its path and reason. Raw sources and CAD files otherwise stay out of `doc/public/`.

## 5. Regenerate, review, commit

1. If CAD previews were selected, regenerate and check them:

   ```sh
   pnpm previews:generate
   pnpm exec zudo-circuit-doc footprints check
   pnpm exec zudo-circuit-doc models
   pnpm exec zudo-circuit-doc models --check
   ```

   Restart a running dev server after adding public assets.
2. Regenerate and check:

   ```sh
   pnpm circuit:generate
   pnpm circuit:check
   pnpm check
   ```

3. Build and run the post-build checks:

   ```sh
   pnpm build
   pnpm check:site
   ```

4. Commit the evidence, inventory, routing, selection, receipts, generated pages, `circuit/generated/preflight.json` and previews together. Never hand-edit generated files. Review the generated diff with:

   ```sh
   git add --intent-to-add -A -- doc/src/content/docs/components circuit/generated doc/public/assets/component-previews
   git diff -- doc/src/content/docs/components circuit/generated doc/public/assets/component-previews
   ```

5. Open the new record page in the built site or dev server. A passing link check proves the route exists, not that it reads correctly.

## External (off-board) components

A purchased, hand-wired component that is not soldered to a PCB (a panel switch, a connector on a cable) is not a board part. Set inventory `mounting: external`, keep its footprint empty, and record its physical terminal numbers in the pin map's `footprint_pad`. Do not fabricate PCB pads or model geometry for it. Verify system wiring and its absence from the PCB assembly separately; both remain explicit checks.
