# Trade Networks

[← Travel network](travel-network.md) · [Back to README](../README.md) · [Long-horizon scalability →](long-horizon-scalability.md)

## Overview

V4-18 deepens the owned `infrastructure_networks` V4 context, the V3
`regions_migration` / `multi_polity_migration` seam, and the V3
`resource_exchange_profile` / `subjective_valuation` exchange seam. It derives
bounded, event-sourced trade analytics from committed events: flows of food,
materials, tools, records, and durable exchange media; directed corridors;
observed exchange dependence; major exchange locations; cross-society flows;
and analytical trade networks that can emerge, disappear, reroute, split, or
merge.

The plan version is `trade-networks.v1`. The analysis is detached and
read-only. It never feeds cognition, prompts, memory, admission, stop selectors,
Observation, or presentation physics.

## Mechanics

Individual `NegotiateExchange` offer/accept and `Give` commands, artifact
custody transfer, inventory-carrying journeys, storage, and trade-post capacity
remain the only mechanics. Organizational exchange is a composition of ordinary
individual commands; no organization actor, treasury, quota, allocation, price,
or central route planner exists.

## Non-goals

- No centralized trade routing, route planner, quota, or automatic allocation.
- No price, money, currency, numeraire, store of value, or unit of account.
- No global trade registry and no authoritative trade-network entity.
- No new V4 context or flag: 14 contexts / 12 flags / six owned stay unchanged.
- No new command, event, observer semantic type, write pair, replay marker, or
  SQL migration. `NegotiateExchange`, `Give`, artifact custody, storage, and
  inventory-carrying journeys remain the only mechanics.

## Flow taxonomy

Evidence comes from committed events only: `ExchangeCompleted`, `Given`,
`ArtifactCreated/Moved/Copied`, `ResourceHarvested`, `ItemCrafted`, `Searched`,
consumption events, and journeys. No `WorldState` or final inventory is read.

| Flow class | Source |
| --- | --- |
| `food` | `FOOD` and `WATER` item kinds |
| `materials` | `MATERIAL` item kinds |
| `tools` | `TOOL` item kinds |
| `records` | Artifact custody/copy movement |
| `durable_exchange_media` | Generic item with at least two completed transfers across at least two distinct counterparties and no observed consumption |
| `other` | Unknown or non-media generic items |

A generic item becomes `durable_exchange_media` retrospectively over the
completed run. No currency object is created.

## Derivation

- A corridor is a directed edge between consecutive observed locations of the
  same item or artifact.
- A same-location transfer is local and never creates a corridor.
- Reverse trajectories mint distinct directed corridors; the network graph
  unions both directions into one undirected connected component.
- A network is a connected component with a content-addressed `trd-net-` id.
  It is never an authoritative entity.

### Dependence and major locations

For each location, 32-tick window, and flow class:

```text
dependence_milli = imported * 1000 // (imported + locally_originated)
```

The denominator is retained. Dependence is observed exchange dependence, never
a consumption, welfare, or scarcity claim. A location is major when its corridor
degree is at least 2 and its transfer count is at least 3 in one window.
Operational `TRADE_POST` infrastructure marks a venue-backed exchange location;
it never changes exchange admission. No score or ranking exists.

### Lineage and cross-society

Every consecutive policy window from the first to the last observed window is
compared, including empty windows. Corridor-set overlap of at least 500 milli
links networks forward, where overlap is `shared corridors / smaller corridor
set` in integer milli:

| Relation | Meaning |
| --- | --- |
| `emerged` | Current network has no predecessor |
| `continued` | Same corridor role set persists |
| `transformed` | Network rerouted (`rerouted=true`) |
| `split` | One predecessor has at least two successors |
| `merge` | One successor has at least two predecessors |
| `dissolved` | Previous network has no successor |

`continued` and `transformed` contribute sustained counts only; there is no
composite score. A gap window forces `dissolved` then `emerged`, never a silent
continuation.

### Cross-society flows

Cross-society rows join exchange participants to contemporaneous `msoc-`
candidates and keep a deterministic dominant exchange location for each society.
Overlapping membership is legal; no society is minted and no partition is
created. Missing candidates produce `missing` coverage for that family only.

## Bounds and coverage

Evidence, cross-society, and lineage track coverage separately. Deterministic
caps apply to transfers, corridors, networks, locations, windows, society pairs,
and lineage edges. Truncation sets `coverage="partial"` and records a bounded
notice; nothing is silently dropped.

## Read-only surfaces

`trade-networks-snapshot-v1` is a canonical sibling artifact with digest and
publication id. `trade-networks-store-v1` stores it atomically. Seven GET-only
routes require `SUBJECTIVE_DEBUG` and fail closed with
`trade_networks_disabled` unless both the root and cursor-key settings are set:

```text
/v1/simulations/{run_id}/trade-networks
/v1/simulations/{run_id}/trade-networks/corridors
/v1/simulations/{run_id}/trade-networks/flows
/v1/simulations/{run_id}/trade-networks/locations
/v1/simulations/{run_id}/trade-networks/dependence
/v1/simulations/{run_id}/trade-networks/cross-society
/v1/simulations/{run_id}/trade-networks/networks
```

Paged routes accept `window_index`; the filter is bound into the cursor
fingerprint. The Research UI adds a read-only panel and the Godot observer adds
four analytical overlay layers.

## Metrics

Six metric families append the catalog from 192 to **198**:

- `trade_corridor_structure@1`
- `trade_flow_composition@1`
- `trade_location_centrality@1`
- `trade_dependence@1`
- `cross_society_trade_flows@1`
- `trade_network_lineage@1`

V4-19 later appends six supply-chain families to **204**; the six trade families
stay at positions 193–198 and the first 198 families keep their IDs, order,
versions, and value keys. Trade networks are a sibling analytical surface, not a
dependency of supply chains.

Off-gate experiment `trade_networks@1` composes existing travel and exchange
seams. It is never on the V1 gate.

## Configuration

| Setting | Meaning |
| --- | --- |
| `PALIMPSEST_TRADE_NETWORKS_ROOT` | Snapshot store root |
| `PALIMPSEST_TRADE_NETWORKS_CURSOR_KEY` | Cursor HMAC key (at least 32 UTF-8 bytes) |

Both are required for reads; neither is required for analysis or collection.

## Read-only fields

Snapshot rows expose network `status`, `previous_network_ids`,
`next_network_ids`, `rerouted`, and `sustained`; cross-society anchor locations;
`trade_post_present`; `cross_location_count`; `sustained_network_count`; and
`window_index` filtering. They never expose raw events, item or person bodies,
prompts, or payload surrogates.

## Verification

```bash
uv run pytest tests/unit/test_trade_networks_*.py -q
uv run pytest tests/architecture/test_trade_networks_boundaries.py -q
uv run pytest tests/integration/test_trade_networks_store_api.py -q -m integration
```

Godot and Compose/browser lanes require their pinned binaries and harnesses;
record them as `unexecuted` with the exact prerequisite when unavailable.

Roadmap registration for V4-18 is owned by `$aif-roadmap`; this page and the
plan bundle do not edit `.ai-factory/ROADMAP.md`.

## See Also

- [Travel network](travel-network.md) — route conditions and movement enforcement
- [Infrastructure networks](infrastructure-networks.md) — objective `infra-` assets and trade posts
- [Analysis metrics](analysis-metrics.md) — catalog, documents, and availability
