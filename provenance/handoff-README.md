# Zudo LED Block — Claude Code Cloud handoff

Prepared on 2026-11-07 JST for the initial repository, documentation, CI, and deferred hosting setup at https://github.com/Takazudo/zudo-led-block.

## Start the implementation

1. Transfer `zudo-led-block-claude-cloud-handoff-20261107.zip` into the Claude Code Cloud workspace associated with that repository. A link in another chat does not automatically transfer its bytes.
2. Unpack the ZIP outside the checkout. Read `claude-code-cloud-prompt.txt` and give its complete contents to the implementing agent.
3. From the unpacked handoff directory, run `python3 verify-seed.py`.
4. Follow the prompt: refresh repository state, create or reuse the epic and four linked implementation issues, then import the source and build the site and CI.
5. Merge only after the accepted work, review, repository policy, and checks at the current PR revision pass. Production deployment remains disabled until the user configures and enables it later.

The separate `zudo-led-block-claude-cloud-prompt-20261107.txt` download is identical to the prompt inside this ZIP.

## Bundle contents

| Path | Purpose |
| --- | --- |
| `claude-code-cloud-prompt.txt` | Complete execution prompt, authorization, task boundaries, verification, and conditional merge policy |
| `seed/engineering/a5/` | 786 original-byte files from the restored A5 checkpoint |
| `seed-manifest.json` | Included paths, sizes, hashes, intended repository paths, and five explicit omissions |
| `verify-seed.py` | Standard-library file identity verifier for the handoff or imported repository |
| `source-recovery-verification.json` | Original archive identity and completed recovery checks |
| `repository-evidence.json` | Inspected repository revisions, package versions, source links, and hosting decision |
| `plan-review.json` | Independent handoff review and addressed findings |

After import, a verifier copied into `scripts/` can be invoked with `--manifest provenance/seed-manifest.json --repo .`. Keep the original A5 checkpoint unchanged; new site generators, wrappers, and verification outputs belong outside it.

## Scope and engineering status

The implementation epic covers source import, Japanese project documentation using the published zudo-circuit-doc packages, credential-free GitHub Actions validation, and Cloudflare Workers Static Assets configuration for https://zudo-led-block.zudolab.dev/.

The website must show the real A5 design and its complete 30-type / 81-piece BOM. The framework component-evidence catalog starts honestly empty and is a separate migration task; it must not imply that the hardware design or BOM is empty.

**A5 is not released for manufacture.** The controller is unrouted; harness routing and installed fit remain unresolved; physical electrical, optical, thermal, print, and load qualification has not occurred. Preserve those distinctions in the site and follow-up issues. A successful documentation build or imported historical check does not close these engineering gates.

## Source preservation

Original archive: `light_block_A5_design_package.zip`, 67,187,342 bytes.

SHA-256: `94448c56521e868280076c0444c7d60339d75c6b128e6b4fde00e2b36533cf24`.

The original ZIP CRC and all 790 entries in its original manifest were checked successfully. The seed preserves 786 files totaling 83,093,114 uncompressed bytes without modifying their contents. It includes current editable electronics, firmware and SDK/licenses, CAD generators, STEP/STL/3MF files, previews, front artwork, PDFs, spreadsheets, procurement evidence, and historical verification records.

Only these original paths are omitted:

- `mechanical/exports/2hp/light_block_A5_2hp_assembled.json`
- `mechanical/exports/2hp/light_block_A5_2hp_exploded.json`
- `mechanical/exports/3hp/light_block_A5_3hp_assembled.json`
- `mechanical/exports/3hp/light_block_A5_3hp_exploded.json`
- `references/light_block_A3_design_package.zip`

The first four are large generated tessellation outputs. Regenerate them before rerunning the mechanical preview pipeline. The fifth is an older nested archive retained in the original full A5 download. The original A5 manifest and reports intentionally remain unchanged and describe the complete original archive. Restoring the five omitted files is necessary before claiming a complete archival package rebuild. The new seed verifier checks the explicitly smaller import.

## Research and validation boundary

The target repository was empty at `c96306efcafd1d5e479b1d2deeabef602359e87e`. The framework reference was inspected at `7d5e4cc67c4fd8d7bec6adbb0727bd8025714aca`, and the lamp reference at `f47fe4706d0e0ca4eb8759fdb402fcd712d2141f`. Refresh those observations before implementation; do not overwrite later user work.

The coherent published consumer scaffold uses initializer 0.2.0, runtime 0.3.0, Node 24, pnpm 11.5.2, zudo-doc 9.1.3, and ZFB family 5.2.2. Initialize in a separate empty directory because the initializer refuses an existing checkout containing `.git`.

Completed here: repository/reference inspection, original archive recovery and integrity checks, exact seed comparison, handoff review, and handoff archive integrity checks. Not performed here: target implementation, package install/build, GitHub tracker or PR creation, CI execution, new firmware/native CAD checks, hardware tests, or live deployment. The implementing session must report its own actual commands, revisions, and results.

## Cloudflare settings for later

| Setting | Kind | Later action |
| --- | --- | --- |
| `CLOUDFLARE_API_TOKEN` | Repository or selected environment secret | Supply a token with the verified permissions for initial Worker creation and custom-domain setup |
| `CLOUDFLARE_ACCOUNT_ID` | Repository or selected environment secret | Supply the account that owns the active `zudolab.dev` zone |
| `CLOUDFLARE_DEPLOY_ENABLED` | Repository variable | Set exactly `true` only when ready to activate production |

Use the current `cf` CLI and reviewed `cloudflare.config.ts` for this new project. The implementer must pin and validate the CLI and static build bridge, including a credential-free dry run; these are acceptance criteria, not claims that a target build already passed. Default validation requires no Cloudflare credentials. Main-branch production is gated separately and cannot run while the enable variable is unset or false.

Selected site downloads must satisfy Cloudflare's per-file and total asset limits. The full original archive, bulky mesh JSON, SDK, and toolchains do not belong in deployed assets. Real DNS, TLS, domain routing, and first-deploy checks remain for activation after the user provides settings.
