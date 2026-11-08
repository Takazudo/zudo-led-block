import type { CircuitConfig } from "@takazudo/zudo-circuit-doc/config";

export default {
  configVersion: 1,
  project: {
    name: "zudo-led-block",
    title: "Zudo LED Block",
  },
  docs: {
    root: "doc",
    generatedContent: "doc/src/content/docs/components",
    preflight: "circuit/generated/preflight.json",
    publicRoot: "doc/public",
    dist: "doc/dist",
    agentResources: true,
  },
  evidence: {
    contractVersion: 1,
    bundlesRoot: ".claude/skills",
    ownerPrefix: "component-",
    auditSkill: "component-spec-audit",
    integrationSkill: "circuit-spec-integration",
    inventory: ".claude/skills/component-spec-audit/references/inventory.json",
    integrationRules: ".claude/skills/circuit-spec-integration/references/rules.json",
    directRouting: ".claude/skills/component-spec-audit/references/direct-routing.json",
    vendorQualifiers: ".claude/skills/component-spec-audit/references/external-vendor-qualifiers.json",
    sourceCache: ".circuit-cache/sources",
  },
  inventoryProvider: { kind: "manual" },
  publication: {
    selection: "circuit/publication/selection.json",
    assets: "circuit/publication/assets.json",
  },
  cad: { enabled: false, libraryName: "LightBlock" },
  validation: {},
  // Explicit representatives: with CAD disabled no record publishes a footprint, so the
  // framework cannot derive representatives (it would exit 4). These pages are still
  // navigated at every viewport/theme; their component-reference inspections are SKIP.
  browserSmoke: {
    representatives: [
      { kind: "primary-document", path: "/docs/components/records/tps2552dbvr-1/", slug: "tps2552dbvr-1", identity: "TPS2552DBVR-1" },
      { kind: "document-exception", path: "/docs/components/records/boomele-2-54-2x5p/", slug: "boomele-2-54-2x5p", identity: "2.54-2*5P" },
    ],
  },
} satisfies CircuitConfig;
