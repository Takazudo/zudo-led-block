# A7 structural preview

Standalone `/a7-preview/`; authored embed `/docs/project/a7-preview/`.
Run `pnpm dev` or `pnpm build && pnpm --dir doc preview`.

- `scripts/a7_public_selection.json`: reviewed source revision, exact file hashes, groups. A5 selection stays separate.
- `scripts/a7_preview.py`: verifies pinned source bytes, parses real GLB node identities, derives dimensions and manifest from layout/front data, selectively copies assets and rejects unexpected published files.
- `manifest.json`: generated, committed; `pnpm preview:generate` regenerates it and the publication allowlist through its producer. `pnpm preview:check` detects drift. Source changes require explicit review/repinning; never silently bless changed geometry.
- `index.html`, `boot.js`, `viewer.css`, `scene.js`: authored viewer. No runtime CDN or iframe messaging. An ordinary lazy same-origin iframe isolates lifecycle; renderer starts only on demand. Close/pagehide abort fetches, cancels scheduled drawing, disconnects resize observation and disposes scene/controls/renderer. Static scenes have no animation loop. Variant loads are serialized.
- `scripts/build-a7-preview.mjs`: esbuild 0.28.2 bundles Three.js 0.180.0 plus OrbitControls and GLTFLoader into ignored `doc/public/a7-preview/scene.js`; copies the upstream MIT licence. Versions and integrity are in pnpm-lock.yaml. Bundle is rebuilt offline during dev/build/check.
- `scripts/a7-preview-browser.mjs`: rendered browser acceptance; screenshots in `test-results/screenshots/a7-*` (CI artifact retention 3 days).

Coordinates: source CAD X right, Y down, Z rear; PMMA rear is Z=0. GLB root has -90° X export rotation and numeric mm geometry (not glTF metres). Viewer applies an additional -90° X, giving display (X,-Y,-Z). Positive display Z looks at the front, +Y is up. No engineering transform is rewritten. Explosion changes only object translations, saved assembled translations are restored exactly. Front width/height/thickness and rear-depth **target** come from checked data, never a raw model bounding box.

All mechanical bodies are project-owned provisional geometry, with `verification.json` kinds retained for inspection (envelopes, allowances and cable scenarios included). No copper, optical or thermal simulation, measured dimensions or disassembly-sequence claim.

Interaction ideas reviewed (no source code copied): zzmod `ddb0367d` static viewer/embed (poster, lifecycle), zudo-case `b7a9e3c` preview-links (standalone + embed), zudo-osc-hole-field `690366a` workbench three.js (inspection and demand rendering). Only Third-party runtime code is the bundled Three.js code under its retained MIT licence.
