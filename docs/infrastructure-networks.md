# Infrastructure Networks

[← Inter-society relations](inter-society-relations.md) · [Back to README](../README.md) · [Physical simulation →](physical-simulation.md)

## What it is

V4-16 owns the reserved objective-world context `infrastructure_networks` as the
first reserved write-pair activation (event **23** / codec **`v21`**). Collective
projects become persistent, location-based infrastructure that can objectively
modify travel, capacity, production, storage, and risk while the asset stays
`operational` and above the catalog integrity floor.

Assets are content-addressed `infra-` ids. Topology is **node** or **edge** only
(`Location.adjacent`); there is no grid, coordinate, polygon, or planner.

V4-17 deepens this contract with route-level travel conditions and snapshot v2
route rows; see [travel network](travel-network.md).

## Ownership and activation

| Surface | Pin |
| --- | --- |
| Capability flag | `v4_capability_flags.infrastructure_networks` |
| Runner schema | accepted `runner-config-v56` only (no `runner-config-v57`) |
| Prerequisite | `collective_projects` must be configured |
| Owned frozensets | both `runner_models` and `compatibility` include the flag (size **6**) |
| Write pair | event schema **23** / codec **`v21`** when the channel is active |
| Alembic | head stays **`0017`** |
| Commands | **43** |
| Observer semantics | **73** types (new event kinds alias existing semantic strings) |
| Metrics | **188** families at V4-16 landing; **192** with the V4-17 travel-network append |

Fail closed:

- `infrastructure_requires_collective_projects` when the flag is on without
  collective projects;
- `infrastructure_networks_disabled` (HTTP 503) when the dual-gate research
  reader is unset;
- unowned V4 flags still fail with `capability_unimplemented`.

Infrastructure supplies venue and capacity evidence; V4-19 owns
`supply_chains`. Remaining reservations 24–26 / `v22`–`v24`
stay reserved; epidemic codec string `v22` stays unaccepted.

## Locked catalog (`infrastructure-networks.v1`)

Eight kinds with locked labor, materials, decay, operational floor, and effects:

| Kind | Topology | Collective kind | StructureKind | Key effects |
| --- | --- | --- | --- | --- |
| `road` | edge | `road` | `ROAD` (anchor) | travel duration −1; fatigue −1.0 |
| `bridge` | node | `bridge` | `BRIDGE` | fatigue −2.0 from location |
| `storage` | node | `storage` | `STORE` | store capacity +3 |
| `well` | node | `well` | `WELL` | public-good draw unchanged |
| `irrigation` | node | `irrigation` | `IRRIGATION` | regen +0.05 |
| `communication_marker` | node | `warning_post` | `WARNING_POST` | exposure relief 0.5 |
| `trade_post` | node | `trade_post` | `TRADE_POST` | item cap +2; store cap +2 |
| `large_shelter` | node | `large_shelter` | `SHELTER` | body cap +2; exposure relief 0.25 |

Caps: `MAX_INFRASTRUCTURE_ASSETS = 64`, `MAX_INFRA_BODY_BONUS = 8`,
`MAX_INFRA_ITEM_BONUS = 8`, `REPAIR_INTEGRITY_DELTA = 0.15`.

Statuses are `operational` / `damaged` / `destroyed` only. There is no
`under_construction` asset row; construction lives on the collective project
until completion registers the asset as `operational`.

## Construction bridge

Construction reuses `StartCollectiveProject` / `ContributeCollectiveProject`
end-to-end (action → op → serialize → mutate → events → cognition). Command count
stays 43.

- `road` requires an adjacent `target_location_id`; other kinds forbid a target.
- Cognition focus codes cover the new kinds; `collective_project:start:road`
  selects a visible adjacent exit.
- Completion registers `infra-` assets; `road` also places an anchor
  `StructureKind.ROAD` for `Repair`.
- `PUBLIC_GOOD_KINDS` / `DRAW_PUBLIC_KINDS` / `PRESENCE_PUBLIC_KINDS` are
  **explicit** frozensets. Infra-only kinds (`road`, `irrigation`, `trade_post`,
  `large_shelter`) are excluded from Use/Maintain/Oppose/presence sets.
- `well` / `communication_marker` (`warning_post`) still require `public_goods`
  to **start**; other infra kinds need only the infrastructure flag plus
  `collective_projects`.

## Lifecycle and effects

Lifecycle: operational → damaged → destroyed. Tick decay never auto-repairs.
Maintain/Oppose sync integrity for public-good kinds when that channel is
active; `Repair` restores linked structures (including ROAD anchors) when
production-linked. Destroyed is terminal for modifiers.

Objective modifiers apply only while `operational` and integrity ≥ catalog
minimum: travel duration/fatigue, body/item/store capacity, resource regen,
exposure relief. No automatic maintenance policy, infrastructure actor, nation,
or civilization infrastructure score.

## Observation and replay

New event detail kinds alias existing observer semantics (pin 73):

| Event detail kind | Semantic alias |
| --- | --- |
| `infrastructure_constructed` | `STRUCTURE_BUILT` |
| `infrastructure_repaired` | `STRUCTURE_REPAIRED` |
| `infrastructure_damaged` | `PUBLIC_GOOD_OPPOSED` |
| `infrastructure_decayed` | `ARTIFACT_DAMAGED` |
| `infrastructure_destroyed` | `ARTIFACT_DESTROYED` |

## Metrics and research surfaces

Four detached families raise the catalog 184 → **188** at V4-16 landing:

- `infrastructure_network_structure@1`
- `infrastructure_condition_lifecycle@1`
- `infrastructure_effect_coverage@1`
- `infrastructure_maintenance_burden@1`

V4-17 appends four travel-network families (catalog **192**); see
[travel network](travel-network.md).

Emit only when `MetricComputationInputs.infrastructure_networks_analysis` is
supplied. Value keys are counts, availability, and quantized ratios — never a
composite score.

Dual-gate research surfaces:

- env `PALIMPSEST_INFRASTRUCTURE_NETWORKS_ROOT` /
  `PALIMPSEST_INFRASTRUCTURE_NETWORKS_CURSOR_KEY` (≥32 UTF-8 bytes);
- snapshot `infrastructure-networks-snapshot-v2` / store-v1 (v1 remains
  decodable); v2 carries bounded objective route rows;
- seven SUBJECTIVE_DEBUG GET routes under
  `/v1/simulations/{run_id}/infrastructure-networks`
  (summary, assets, edges, condition, effects, maintenance, routes);
- Research UI view `infrastructure-networks`;
- Godot overlays for node / edge / damaged / destroyed (objective only).

Safe reason codes include `infrastructure_networks_disabled`,
`infrastructure_networks_size_limit`,
`infrastructure_networks_publication_exists`, and
`infrastructure_networks_store_corrupt`.

## Experiment

Off-gate experiment `infrastructure_networks@1` (control flag off vs treatment
flag on) is registered in `OFF_GATE_MATRIX_EXPERIMENT_IDS` and is **not** on the
V1 A–E gate.

## Non-goals

No automatic maintenance, grid planner, infra actor/crew/owner, nation,
civilization infrastructure score, `/v2` API, `runner-config-v57`, or Alembic
`0018`. V4-19 owns `supply_chains`.

## See Also

- [V4 architecture](v4-architecture.md)
- [Physical simulation](physical-simulation.md)
- [Configuration](configuration.md)
- [Analysis metrics](analysis-metrics.md)
- [Research API](research-api.md)

Current catalog: 216 metric families; 43 commands; 73 observer semantic types; Alembic `0017`.
