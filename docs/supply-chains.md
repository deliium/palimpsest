# Supply Chains

[← Trade networks](trade-networks.md) · [Back to README](../README.md) · [Long-horizon scalability](long-horizon-scalability.md)

## Overview

V4-19 owns the declared `supply_chains` V4 context and extends V3 crafting into
bounded multi-stage production chains. Dependencies cover resources, skills,
tools, locations, infrastructure, and organizations. Agents and organizations
plan locally; there is no central planner, optimizer, quota, price, money, or
automatic allocation. Counts are 14 contexts / 12 flags / eight owned / five
unowned. `runner-config-v56` is the only V4 runner schema and supply_chains
adds no write pair.

## Mechanics

The legacy six-recipe `example_production_catalog()` and its digest are
byte-identical. Chain recipes are a separate closed tuple applied by
`supply_chain_production_catalog()`, preserving base order then append order.
The engine validates the catalog when `supply_chains` is active and fails closed
with `supply_chain_catalog_missing`, `supply_chain_catalog_empty`,
`supply_chain_catalog_no_chain`, or `supply_chain_catalog_cycle`.

A held `STRIKE` tool adds `0.10` to harvest success probability, clamped to
`1.0`, without consuming the tool. Cognition orders believed recipe ids by a
one-step stage-readiness order (`harvest → craft → build → repair → store`) and
compiles at most one existing command. Organizations remain compositions of
member commands plus owner `org_op_v1` procedure claims; no organization actor
or executor exists.

## Non-goals

No central planner, optimizer, quota, automatic allocation, price, money,
currency, score, ranking, severity, recommendation, or Godot overlay exists.
Dependency graphs and bottleneck rows are non-spatial analytical structures.

## Chain recipe set

`harvest_grain`, `mill_grain`, `bake_bread`, `craft_plank`, `craft_tool_head`,
and `assemble_tool`. The locked item edges are `grain→flour`, `flour→bread`,
`wood→plank`, `stone→tool_head`, `plank→fine_tool`, and
`tool_head→fine_tool`.

## Dependency dimensions

Resources, items, structures, storage, transport, locations, infrastructure,
organizations, tools, and skills appear as `resource`, `item`, `structure`,
`storage`, `location`, `infrastructure`, `organization`, `tool`, and `skill`
nodes. The ten closed edge kinds are `resource_to_item`, `item_to_item`,
`item_to_structure`, `item_to_storage`, `transport`, `location_to_stage`,
`infrastructure_to_stage`, `organization_to_stage`, `tool_to_stage`, and
`skill_to_stage`. Missing optional inputs produce `missing` coverage and never
fabricate an edge.

## Derivation

Committed `ResourceHarvested`, `CraftStarted`, `ItemCrafted`,
`StructureBuilt`, `StructureRepaired`, `ItemStored`, and movement events are the
only stage evidence. Multi-tick craft starts pair with a later completion;
one-tick completions carry `unresolved_craft_inputs`. Recipe structure, objective
skill levels, operational infrastructure, and owner organization claims arrive
as detached inputs. Windows are 32 ticks, index `tick // 32`, at most 512
windows.

Chains are observed dependency paths of depth 2-8 with content-addressed
`sc-chain-` ids. Lineage compares consecutive windows, including empty windows,
and yields `emerged`, `continued`, `transformed`, `split`, `merge`, or
`dissolved`; parents are never rewritten.

### Bottlenecks

Seven closed kinds: `upstream_shortfall`, `single_location_concentration`,
`transport_dependency`, `tool_dependency`, `infrastructure_dependency`,
`organization_dependency`, and `skill_constraint`. Thresholds are at least 3
events, 750 milli share, 250 milli shortfall, demand at least 3, and low skill
at most 0.125. Rows carry counts and integer ratios only.

## Bounds and coverage

Evidence caps at 200,000 rows; stages 4,096; edges 16,384; chains 4,096;
bottlenecks 4,096; locations 4,096; organizations 2,048; lineage 16,384.
Truncation uses a deterministic prefix, `coverage="partial"`, and one bounded
notice.

## Read-only surfaces

Seven GET-only routes under `/v1/simulations/{run_id}/supply-chains`: summary,
`/stages`, `/dependencies`, `/chains`, `/bottlenecks`, `/locations`, and
`/organizations`. They require `SUBJECTIVE_DEBUG`, default limit 100,
`window_index` at most 511, and fail closed with `supply_chains_disabled` when
the dual gate is unset. Cursors bind `window_index`; a cursor for another window
is rejected. Errors: `supply_chains_cursor_expired`,
`supply_chains_cursor_invalid`, `supply_chains_run_not_found`, and
`supply_chains_store_corrupt`. No Godot overlay is added.

## Metrics

Six families append the catalog from 198 to **204**:
`supply_chain_structure@1`, `supply_dependency_graph@1`,
`supply_bottleneck_pressure@1`, `supply_resource_tool_dependency@1`,
`supply_location_infrastructure_reliance@1`, and
`supply_organization_coordination@1`.

## Configuration

`runner-config-v56` with `v4_capability_flags.supply_chains`.
`PALIMPSEST_SUPPLY_CHAINS_ROOT` and
`PALIMPSEST_SUPPLY_CHAINS_CURSOR_KEY` (at least 32 UTF-8 bytes) form the dual
gate; a partial gate leaves the reader disabled without a startup error.
supply_chains itself activates no write pair: infrastructure-channel runs keep
23/`v21` and travel-channel runs keep 27/`v25`.

## Read-only fields

Snapshots are canonical `supply-chains-snapshot-v1`; the store is
`supply-chains-store-v1`. Records expose counts, tokens, coverage, and bounded
ratios only. No claim body, wallet, price, score, rank, or recommendation field
exists.

## Verification

Pins: 43 commands, 73 observer semantic types, 212 metric families,
`EVENT_SCHEMA_REPLAY_V27`, codec `v25`, Alembic `0017`, `/v1`, and
`observer-protocol-v1`. The off-gate experiment `supply_chains@1` compares a
legacy-catalog control with an extended-catalog treatment.

## See Also

- [Trade networks](trade-networks.md) — sibling analytical network, not a dependency
- [Infrastructure networks](infrastructure-networks.md) — venue and capacity evidence
- [Analysis metrics](analysis-metrics.md)
- [Configuration](configuration.md)

Current catalog: 216 metric families; 43 commands; 73 observer semantic types; Alembic `0017`.
