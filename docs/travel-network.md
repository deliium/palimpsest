# Travel Network

[← Infrastructure networks](infrastructure-networks.md) · [Back to README](../README.md) · [Regions and migration →](regions-migration.md)

## Ownership and authority

V4-17 deepens two already-owned seams rather than adding a V4 context or flag:

- the objective `infrastructure_networks` context (event **27** / codec **`v25`**);
- the V3 `multi_polity_migration` / `regions_migration` seam.

The authority is `OBJECTIVE_WORLD`, owned by `world` and `simulation`. Route
conditions are derived objective facts. There is no abstract planner, grid,
coordinate, owner, crew, nation, or route/civilization score. Agents never read
`WorldState` or a global route table.

Counts stay **14 V4 contexts / 12 V4 flags / six owned**. `runner-config-v56`
stays accepted; there is no `runner-config-v57`.

## Activation

The travel-network channel is active only when both prerequisites are present:

| `infrastructure_networks` | `regions_migration` | Result |
| --- | --- | --- |
| off | absent | no channel; default write pair |
| off | present | no channel; regions pair `(21, "v19")` |
| on | absent | no channel; infrastructure pair `(23, "v21")`; INFO `travel_network_inactive` |
| on | present | active; pair `(27, "v25")` |

## Locked policy `travel-network.v1`

| Dimension | Behavior |
| --- | --- |
| Base route | `RouteSpec` duration/fatigue, else duration 1 / fatigue 0 |
| Infrastructure | V4-16 effective duration/fatigue applied once; operational road/bridge contribute quality and capacity |
| Season | spring/summer 0; autumn +1 duration, −1 capacity, +0.1 risk; winter +2 duration, −2 capacity, +0.2 risk |
| Weather | clear/cloudy 0; rain +1 duration, +0.15 risk; storm +2 duration, +0.5 risk |
| Hazard | +0.3 risk, −2 capacity; status restricted |
| Risk | endpoint visibility + weather + season + hazard + 0.02·duration − 0.3·quality, clamped 0..1 |
| Fatigue | infrastructure-effective fatigue + risk·2.0, clamped ≥ 0 |
| Capacity | min(8, origin body capacity, destination body capacity) + road 2 + bridge 1 + season/hazard deltas, clamped 1..24 |
| Quality | mean integrity of operational road/bridge contributors, 0 if none |
| Cap | `MAX_ROUTE_CONDITIONS = 512`; overflow fails closed |

Status precedence: storm without relief → closed `weather`; winter without
relief → closed `seasonal`; active hazard → restricted `hazard`; storm with
relief → restricted `weather`; winter with relief → restricted `seasonal`;
rain/autumn → restricted; otherwise open.

## Write pair and replay

Travel-network runs write replay **v27** / codec **`v25`**. Reserved pairs
23–26 / `v21`–`v24` are unchanged. Infrastructure-only runs keep
`(23, "v21")`; regions-only runs keep `(21, "v19")`. Codec `v25` is cumulative
over `v21` and preserves canonical hashing. Old checkpoints remain decodable.
Alembic stays **`0017`**.

## Movement and observation

`Move`, `Transport`, and `Flee` read one effective condition. Closed routes
reject with `ROUTE_CLOSED` or `ROUTE_BLOCKED`; restricted routes carry explicit
duration/fatigue/risk; capacity is checked before a journey starts. Intra-tick
movement reads the condition persisted at the previous tick boundary.

Adjacent `VisibleExit` rows expose route status, availability, blockage,
capacity, risk, quality, duration, and fatigue. `remote_topology` stays omitted;
reason codes are research/objective only.

## Subjective route beliefs

Route-quality evidence is owner-scoped in destination memories and reused by the
existing `regional_migration` biases. Beliefs are fallible: stale, unknown, and
incorrect beliefs are legal. Bounded planning biases only the first visible hop.
Admission remains authoritative.

## Metrics and surfaces

Four detached families append **188 → 192**: `travel_route_structure@1`,
`travel_route_condition@1`, `travel_route_blockage@1`, and
`travel_route_belief_alignment@1`. No composite route score exists.

`infrastructure-networks-snapshot-v2` carries bounded route rows; v1 remains
readable. Seven GET-only routes are served under the existing
`SUBJECTIVE_DEBUG` dual gate:

- `GET /v1/simulations/{run_id}/infrastructure-networks`
- `GET .../assets`
- `GET .../edges`
- `GET .../condition`
- `GET .../effects`
- `GET .../maintenance`
- `GET .../routes`

The Research UI renders an objective routes table; the Godot observer maps route
status onto the existing objective infrastructure layer. Neither client writes.

## Experiment

`travel_network@1` is off-gate and reproducible. It compares an inert control
with a treatment that enables the travel-network channel. It makes no causal or
civilization-capacity claim.

## Pins

Runner v4/v55/v56; result v2/v3; **43** commands; **73** observer semantic types;
**192** metric families; 14 V4 contexts / 12 V4 flags / six owned; replay-v27 /
codec `v25` when active; `/v1`; `observer-protocol-v1`; Alembic `0017`.

## Verification

Python unit/architecture, static, snapshot, movement, perception, cognition,
checkpoint/replay, metric, and end-to-end lanes are exercised by the plan bundle.
Env-gated Compose/browser, PostgreSQL integration, Godot, and benchmark lanes are
recorded in the plan's verification receipt as pass or explicitly `unexecuted`.
