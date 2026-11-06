# ZUDO_DEPS_PINS

Provenance for artifacts vendored or generated from first-party (Takazudo/zudolab) upstreams.
Updated by `/dev-bump-zudo-deps` on every sync — keep `pinned:` accurate.

## create-zudo-doc

- repo: zudolab/zudo-doc
- what: doc-site host scaffold, copied with the `doc/` host-glue lines (chrome bindings import,
  islands seed import, `@takazudo/zudo-circuit-doc/styles.css` import) layered on top — see
  `circuit/WORKFLOW.md` and this project's own `zfb.config.ts`/`chrome-bindings.tsx` for what was
  added beyond the scaffold
- files: `doc/pages/docs/[[...slug]].tsx`, `doc/pages/index.tsx`, `doc/tsconfig.json`,
  `doc/src/styles/global.css` (the Wind CSS import chain; the `:root` override slot is empty
  by design), `doc/scripts/check-links.js`
- source: `packages/create-zudo-doc/templates/base/{pages/docs/[[...slug]].tsx,pages/index.tsx,tsconfig.json,src/styles/global.css,scripts/check-links.js}`
  (the pinned `create-zudo-doc@9.1.3` output, generated from published bytes and re-derived by the zudo-circuit-doc monorepo's upstream-scaffold parity check)
- track: releases
- pinned: dee47852d9c12500b2dacf7a4d2a1d6bb0a8ecf5 (create-zudo-doc@9.1.3 npm gitHead)
- updated: 2026-11-06
- sync: run `create-zudo-doc@9.1.3` into a scratch dir and diff its project output against the
  files listed above; `/dev-bump-zudo-deps` performs the upstream-scaffold parity check (#24) the
  same way
- notes: `doc/scripts/check-links.js` is byte-identical to upstream — it resolves paths from
  `process.cwd()`, so this project's root `check:site` script invokes doc's own `check:links`
  script with pnpm's `--dir doc` flag (cwd becomes `doc/`) rather than pointing `node` at the
  script's path from the project root, to keep the vendored file unmodified.
  `doc/pages/docs/[[...slug]].tsx` carries one added line beyond the upstream docHistory-patched
  stub: `import "../lib/_circuit-doc-islands";` (ADR-016). `doc/src/styles/global.css` has one
  added `@import "@takazudo/zudo-circuit-doc/styles.css";` line after the upstream
  `@takazudo/zudo-doc/features.css` import (ADR-015). Re-apply both after any re-copy.

## zfb family (registry-pinned, not vendored)

- repo: Takazudo/zudo-front-builder
- what: `@takazudo/zfb`, `@takazudo/zfb-runtime`, `@takazudo/zfb-md-wasm` — exact-pinned
  `dependencies` in `doc/package.json` (ADR-003), not a file copy; `/dev-bump-zudo-deps`'s
  registry-dep resolver already tracks these. This entry exists only so a `ZUDO_DEPS_PINS.md`
  sweep surfaces the aligned engine family instead of silently skipping it.
- files: `doc/package.json`
- source: n/a (registry release, not a vendored file copy)
- track: releases
- pinned: 5.2.2
- updated: 2026-11-06
- sync: bump `doc/package.json` (registry dep edit), not a file sync
- notes: keep the three engine packages aligned. zudo-doc/history-server/create-zudo-doc are
  each published at 9.1.3. The prepared circuit runtime 0.3.0 / initializer 0.2.0 are not
  published. Runtime peers are ^9.1.3 / ^5.2.2; integration requires strict packed-consumer
  registration, unchanged LED publication scans and browser checks. Node 24 LTS
  (>=24 <25) is required by zudo-doc 7; keep pnpm 11.5.2 and TypeScript 5.9.
