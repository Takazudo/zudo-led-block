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
- The component-evidence catalog is intentionally empty until the 30 parts are migrated through Workflow B. Do not invent source locks, facts, reviewers, pin maps or VERIFIED flags.
- Documentation is Japanese-first (`defaultLocale: "ja"`).
- Production hosting is off until the repository variable `CLOUDFLARE_DEPLOY_ENABLED` is exactly `true`. Do not set it, deploy, or touch Cloudflare resources unless the owner asks.
