// Cloudflare project configuration for the static documentation site.
//
// Reviewed and committed so `cf` never runs automatic configuration (which can
// install packages and rewrite files) in CI. Validated against cf@1.0.0-beta.28
// (@cloudflare/config 0.30.2). The configuration format is beta: keep the CLI
// pinned and re-validate the fields below when upgrading.
//
// - Assets-only Worker: no `entrypoint`, so no server code is deployed.
// - `accountId` is intentionally omitted; CI supplies CLOUDFLARE_ACCOUNT_ID
//   only in the enabled production deploy job.
// - The static asset directory is not part of this schema. `cf build`
//   delegates to Wrangler, which reads `assetsDirectory` from
//   ./wrangler.config.ts (the "build bridge"). Run the docs build first; cf does
//   not run package.json build scripts.
import { defineConfig } from "cf/config";

export default defineConfig({
  worker: {
    name: "zudo-led-block",
    compatibilityDate: "2026-11-04",
    // A hostname (Custom Domain), not a wildcard route. Applied on the first
    // real deploy, which needs DNS/zone permissions — see project/hosting.mdx.
    domains: ["zudo-led-block.zudolab.dev"],
    workersDev: false,
    previewUrls: false,
    assets: {
      // Pages are emitted as <path>/index.html → served at <path>/.
      htmlHandling: "auto-trailing-slash",
      // Unknown routes get dist/404.html with HTTP 404 (no SPA fallback).
      notFoundHandling: "404-page",
    },
  },
});
