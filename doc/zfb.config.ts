import { defineConfig } from "zfb/config";
import { zudoDoc } from "@takazudo/zudo-doc/config";

// The one config file for this project's doc site (@takazudo/zudo-doc). It
// must stay free of `node:*` imports and must not import `circuit.config.ts`
// (epic #1 Config contract, item 4): `zfb.config.ts` is evaluated through
// esbuild with `--platform=neutral`, a graph the circuit config never joins.
const site = zudoDoc({
  siteName: "Zudo LED Block",
  siteDescription:
    "Zudo LED Block (Light Block A5): Kumiko の横に置く細い Eurorack 用ライトの設計資料。A5 は開発チェックポイントで、製造リリースではありません。",
  // Canonical production origin (sitemap / canonical / og:url). Served from
  // Cloudflare Workers Static Assets once production is activated (see
  // doc/src/content/docs/project/hosting.mdx); the site itself is static.
  siteUrl: "https://zudo-led-block.zudolab.dev",
  // No sitemap: zudo-circuit-doc's publication policy treats enabling one as a
  // separate publication decision (`zudo-circuit-doc scan` fails otherwise).
  // Every page is emitted as <path>/index.html; trailing-slash hrefs match
  // Cloudflare's htmlHandling "auto-trailing-slash" without a redirect hop.
  trailingSlash: true,
  githubUrl: "https://github.com/Takazudo/zudo-led-block",
  // Required by the v1 asset URLs (FOOTPRINT_ASSET_BASE / MODEL_ASSET_BASE
  // in the package are root-absolute) — this already is the default, kept
  // explicit so it is never accidentally changed.
  base: "/",
  // ADR-020: templates set the locale explicitly.
  // Japanese is the primary project-documentation language.
  defaultLocale: "ja",
  // zudo-doc 9 resolves an omitted themePack to Graphite; keep the Classic look.
  themePack: "default",
  themePacks: ["default"],
  llmsTxt: true,
  cjkFriendly: true,
  dynamicPageTransition: true,
  docHistory: true,
  // The generated component catalog is regenerated from evidence, not
  // hand-edited, so it carries no useful edit history of its own.
  docHistoryExclude: ["components", "components/**"],
  assetViewer: true,
  strictContentBridge: true,
  // ADR-016: ingest this project's `.claude/` tree (one level up from this
  // zfb project) so `/docs/claude/` and `/docs/claude-skills/<owner>/`
  // render the raw agent resources the generated pages link back to.
  claudeResources: { claudeDir: "../.claude", scanRoot: ".." },
  // These routes exist only for the default docsDir and never inside an
  // archived version directory; this project has no `versions` config, but
  // the prefixes stay explicit so a later version addition does not 404 them.
  defaultLocaleOnlyPrefixes: [
    "/docs/components/",
    "/docs/claude/",
    "/docs/claude-md/",
    "/docs/claude-skills/",
    "/docs/claude-agents/",
    "/docs/claude-commands/",
  ],
  chromeBindingsModule: "./src/chrome-bindings.tsx",
  headerNav: [
    { label: "プロジェクト", path: "/docs/project", categoryMatch: "project" },
    { label: "設計", path: "/docs/architecture", categoryMatch: "architecture" },
    { label: "調査", path: "/docs/research", categoryMatch: "research" },
    { label: "判断", path: "/docs/decisions", categoryMatch: "decisions" },
    { label: "検証", path: "/docs/verification", categoryMatch: "verification" },
    {
      label: "Components",
      path: "/docs/components",
      categoryMatch: "components",
      children: [
        { label: "Catalog & Records", path: "/docs/components", categoryMatch: "components" },
        { label: "Raw agent resources", path: "/docs/claude", categoryMatch: "claude", versioned: false },
      ],
    },
  ],
  headerRightItems: [
    { type: "component", component: "theme-toggle" },
    { type: "component", component: "search" },
  ],
  footer: {
    links: [],
    copyright: "Built with zudo-circuit-doc on zudo-doc.",
  },
});

// zfb's source-level `linkValidation` (which zudoDoc() switches on) only sees
// anchor ids written as a literal `id` on an intrinsic element, never the id a
// component such as the generated pages' `<EvidenceAnchor>` renders — so it
// warned "broken link: #fact-…" / "#src-…" for every in-page evidence link
// (#52, #68). The built-HTML scan in `pnpm check:site` (`check:links
// --strict-anchors --strict-broken`) sees rendered ids and checks every page,
// and `resolveMarkdownLinks` still warns on unresolvable `.md` links, so the
// source-level check adds nothing but noise here.
delete site.markdown?.features?.linkValidation;

export default defineConfig(site);
