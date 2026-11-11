# Agent instructions

Read [circuit/WORKFLOW.md](circuit/WORKFLOW.md) first. It is the canonical workflow for this circuit project; this file only points to it.

- Exact-component evidence lives in the owner bundles under `.claude/skills/component-*/`, indexed by `.claude/skills/component-spec-audit/references/inventory.json`. Cross-component rules live in `.claude/skills/circuit-spec-integration/references/rules.json`.
- Run `pnpm circuit:check` before editing and again after.
- Never hand-edit the generated pages under `doc/src/content/docs/components/`; change the evidence and run `pnpm circuit:generate`.

## This project (Zudo LED Block / Light Block A5)

The framework workflow above is canonical for component evidence. These project rules sit beside it:

- `engineering/a5/` is an **immutable byte-for-byte import** of the A5 engineering checkpoint. Never edit, regenerate, reformat or "fix" files there; `python3 scripts/verify_seed.py --manifest provenance/seed-manifest.json --repo .` must stay PASS. New wrappers, checks and generators live in `scripts/`; provenance lives in `provenance/`.
- Never run `engineering/a5/firmware/tools/make_release.py` in place (it rewrites `dist/` and records); copy the firmware tree first. Run `check_schematic_interfaces.py` only with `--output` pointing outside the repository.
- A5 is **not released for manufacture**: the controller PCB is unrouted, harness routing/fit is unresolved, and no physical qualification exists. Keep that status visible; a green CI is not an electronics or manufacturing approval. Imported ERC/DRC/test results are historical and must stay labelled as such.
- The 30-type / 81-piece BOM is published from `engineering/a5/` by `scripts/a5_site.py` (`pnpm a5:generate`); do not hand-edit `doc/src/content/docs/architecture/bom.mdx`, `project/status.mdx`, `project/downloads.mdx`, `verification/historical-records.mdx` or `circuit/publication/assets.json`. The public file set is chosen in `scripts/a5_public_selection.json`.
- The component-evidence catalog holds exactly the 30 A5 fitted identities, reconciled by `scripts/a5_catalog.py reconcile` into `provenance/a5-catalog/reconciliation.json` (30 identities / 71 placements / 81 pieces; C5665 spelling mapped in `provenance/a5-catalog/identity-crosswalk.json`). `python3 scripts/a5_catalog.py check` must pass. Lines of a later revision are allowed beside the 30 only with a `line-a<N>-` line ID and a `component-a<N>-` owner bundle (e.g. `line-a7-…`); they never count toward or relax the A5 reconciliation. Pin maps and placements are historical A5 netlist projections; keep the placement facts `NEEDS BENCH`. Do not invent source locks, facts, reviewers, pin maps or VERIFIED flags; after evidence changes run `python3 scripts/a5_catalog.py sync-states` and `python3 scripts/a5_catalog.py selection`, then review the diff.
- Documentation is Japanese-first (`defaultLocale: "ja"`).
- Production hosting is off until the repository variable `CLOUDFLARE_DEPLOY_ENABLED` is exactly `true`. Do not set it, deploy, or touch Cloudflare resources unless the owner asks.

## 開発オーケストレーション

複数セッションまたは重い検証では、[circuit/ORCHESTRATION.md](circuit/ORCHESTRATION.md)、[作業・環境・モデルの対応表](circuit/orchestration/current-plan.md)、[bounded task template](circuit/templates/orchestration-task.md) も読んでください。A5 の不変条件、A6 の保留、A7 の現在の継続記録、部品根拠・実機検証・hosting の承認境界は変更しません。既知 DNS 障害の後回しは限定的な優先順位であり、検証免除ではありません。
