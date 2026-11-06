---
name: circuit-spec-integration
description: Audit behavior that spans more than one exact component, such as shared supplies, signal boundaries, startup and reset states, protection, sensing, thermal coupling, firmware assumptions and as-built state. Use whenever a question, substitution or design change involves several component records or a stage beyond a single datasheet.
---

# Circuit specification integration

Individually valid components do not prove the whole circuit. This skill handles the cross-component rules in `references/rules.json`. The canonical workflow is [circuit/WORKFLOW.md](../../../circuit/WORKFLOW.md).

1. Run `pnpm exec zudo-circuit-doc validate` (or `pnpm circuit:check`) and note pre-existing failures.
2. Read `references/rules.json` and load every exact owner bundle named by each matching rule, through the component-spec-audit skill. Resolve manufacturer, MPN and order codes independently; reject conflicts, same-name wrong-vendor parts and ambiguous bare names. Load subordinate records directly.
3. Use the listed fact IDs with their exact conditions and locators. An `UNSOURCED` fact cannot close a domain, and design connectivity cannot prove programmed, assembled or measured state.
4. For a substitution or design change, report the affected rule, the raw facts, recalculated margins with their dependencies, the evidence stages still missing, and one honest verdict. Do not change design files silently.
5. Recompute conditioned calculations from their inputs. The validator checks the arithmetic, not the units or the reading of the source table; check those yourself.

## Adding a rule

The rule list may be empty; `{ "schema_version": 1, "rules": [] }` is valid. Add a rule **only when a real interaction exists** between exact components. A rule names its `rule_id`, `domain`, `record_ids`, `fact_ids` (owned by those records), `conditions`, `verdict`, `refusal` text and any `conditioned_calculations`.

An evidence chain lists stages in order, from the official source and the conditioned requirement through the netlist, symbol and footprint, PCB orientation, BOM and placement, as-built and programmed state, to bench results. Every stage stays `OPEN` with empty `fact_ids` until real evidence exists. A completed early stage never implies a later one, and a generated netlist is never `CONFIRMED`.

After editing rules, update the integration count lock `expect.integrationRules` in `circuit/publication/selection.json`, then run `pnpm circuit:generate` and `pnpm check`.
