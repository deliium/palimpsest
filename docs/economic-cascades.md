# Economic Cascades

V4-26 adds the seventeenth V4 context, `economic_cascades`, as analysis-only. It
measures how already-committed objective disruptions propagate through observable
production dependencies. It never runs a cascade engine, never adds a world rule,
and never asserts an objective cause. Policy: `economic-cascades.v1`.

## Purpose and non-goals

- **Purpose:** measure resource loss, route closure, infrastructure destruction,
  population loss, and tool-production decline from committed evidence, then link
  them to downstream stage shortfalls along real dependency edges.
- **Non-goals:** no cascade engine in `WorldEngine`; no new command, event, write
  pair, runner schema, API version, migration, or Godot overlay; no severity,
  impact, priority, risk, class, merit, or composite cascade score; no scripted
  downstream outcome.

The requested chain — mine loss → material shortage → tool shortage → food
productivity decline — already propagates through existing mechanics: missing
recipe inputs reject with `materials_unavailable`, missing tools reduce craft
duration and harvest probability, closed routes gate movement, destroyed
infrastructure drops its services, and dead actors issue no commands. V4-26
observes that propagation instead of scripting it.

## Five disruption classes

| Class | Committed evidence | Subject |
| --- | --- | --- |
| `resource_loss` | `ResourceNodeDepleted` zero crossing | most recent preceding harvest recipe, or `resource:<node>` when unknown |
| `route_closure` | `RouteConditionChanged` transition into `closed` | `route:<origin>-><destination>` |
| `infrastructure_destruction` | `InfrastructureDestroyed` | destroyed asset token |
| `population_loss` | `Died` | objective body token, joined to that actor's completed recipes |
| `tool_shortage` | documented tool-production decline proxy | tool-output recipe whose adjacent-window completions fell |

A resource node emits one row per zero crossing; recovery allows a later crossing.
Repeated closed windows do not duplicate a row. `tool_shortage` is not an
objective stock measure: it is synthesized from adjacent-window completion
declines and is unavailable when no tool-output stage exists.

## Dependency structure

Edges come only from detached `SupplyRecipeSpec` facts plus observable topology:

| Kind | Upstream | Downstream |
| --- | --- | --- |
| `resource_input` | producer recipe | consumer naming that resource |
| `item_input` | producer recipe | consumer naming that item |
| `tool_dependency` | tool-output recipe | recipe declaring a tool role |
| `infrastructure_dependency` | `asset:<kind>@<location>` | stage at that location matching the locked infrastructure map |
| `transport_dependency` | `route:<origin>-><destination>` | stage at either endpoint when the route is not open |

Labor participation is an explicit actor→recipe join used only by chain linking.
It is never an edge row and is never serialized. Depth is bounded at six; deeper
edges are dropped with a bounded notice rather than clamped.

## Chain semantics

A chain row is `linked` only when an observed disruption reaches an observed
downstream stage shortfall along an emitted dependency edge within the depth and
lag bounds. It is `unlinked` when the stage is observable but not in shortfall,
`unresolved` when the edge exists but the downstream row or labor join is missing,
and `unavailable` where no observation exists. A shortfall observed before the
disruption is never linked or back-dated.

This is a dependency-conditioned observation, not proof of cause. Objective
disruptions and stage facts, dependency edges, and analytical chains are three
strictly separated layers with a hard leakage guard.

## Quantitative outputs

- Stage shortfall is an integer-milli share of demand minus completions over
  demand; the threshold is 250 milli. Demand is attempts plus downstream attempts
  whose recipe names this stage's output.
- Per-kind propagation reports chain counts, linked/unlinked/unresolved counts,
  mean depth and lag in milli, and the number of downstream stages.
- Availability requires at least three linked chains for that kind; fewer sampled
  links remain `insufficient_samples`.
- Windows are 32 ticks, at most 512 windows; lag is capped at two windows.

## Metric families

Eight families append positions 236–243, raising the catalog from 236 to **244**:

`resource_loss_cascade@1`, `route_closure_cascade@1`,
`infrastructure_destruction_cascade@1`, `population_loss_cascade@1`,
`tool_shortage_cascade@1`, `cascade_dependency_structure@1`,
`cascade_propagation@1`, and `cascade_coverage@1`.

The first 236 families keep their ids, order, versions, and value keys.

## Snapshot and store

`economic-cascades-snapshot-v1` is canonical, digest-addressed, and wall-clock
free. `economic-cascades-store-v1` writes atomically under a lock with
publication-count and cumulative byte quotas. Publication is programmatic after
scientific completion; there is no CLI producer and no runner flag.

## Read surface

Seven GET-only routes require `SUBJECTIVE_DEBUG` and both settings
`PALIMPSEST_ECONOMIC_CASCADES_ROOT` and `PALIMPSEST_ECONOMIC_CASCADES_CURSOR_KEY`
(at least 32 UTF-8 bytes):

- `GET /v1/simulations/{run_id}/economic-cascades`
- `GET .../disruptions`
- `GET .../dependencies`
- `GET .../chains`
- `GET .../propagation`
- `GET .../windows`
- `GET .../coverage`

Each paged route defaults to 100 rows and accepts at most 500; `window_index` is
bounded to 511. Cursors are bound to the snapshot, purpose, window, and limit.
Unconfigured reads fail closed with `economic_cascades_disabled`; a corrupt store
returns `economic_cascades_store_corrupt`. The Research UI adds a read-only panel;
Godot adds no overlay.

## Experiment

Off-gate `economic_cascades@1` has three arms: `cascade-baseline` (supply-chain
channel off, legacy catalog), `cascade-production` (chain catalog), and
`cascade-full` (chain catalog plus infrastructure, regional routes, and mortality
enabled). It is absent from the V1 A–E gate and injects no disruption.

## Interpretation limits

Blocked attempts are not committed today, so a shortfall is inferred from a
demand/completion gap rather than a rejection event. Tool shortage is a
production-decline proxy. Population loss links only when the dead actor's
objective token matches observed stage participation; no identity map is invented.
No row claims severity, blame, root cause, or economic damage.

## See Also

- [Supply chains](supply-chains.md)
- [Trade networks](trade-networks.md)
- [Economic inequality](economic-inequality.md)
- [Social mobility](social-mobility.md)
- [Infrastructure networks](infrastructure-networks.md)
- [V4 architecture](v4-architecture.md)
- [Analysis metrics](analysis-metrics.md)
- [Research API](research-api.md)
- [Research UI](research-ui.md)
