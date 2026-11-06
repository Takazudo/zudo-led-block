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
} satisfies CircuitConfig;
