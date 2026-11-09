# Phase 2: Objective Route Channel

Plan: [index.md](index.md)
Tasks: 4-6
Depends on: Phase 1 (Tasks 1-3)

## Objective

Persist a bounded, deterministic objective route-condition channel in
`WorldState`, derive every condition from already-authoritative facts, and add
the replay-v27 `RouteConditionChanged` event contract. No route condition is
created from agent belief, and no objective planner exists.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/world/_state.py` | `WorldState` 321-474; infrastructure slot 331/363; `rebuild_world_state` 37-160; properties 525-574 | The new channel must be added to the immutable state, rebuild path, validation, and property surface. |
| `src/world/regions.py` | `RouteSpec` 64-99; `RegionsMigrationSpec.validate_topology` 181-195; `canonical` 197-224 | `RouteSpec` supplies base duration/fatigue; routes must remain existing graph edges. |
| `src/world/infrastructure.py` | `InfrastructureKind` 46-54; `effects_active` 270-288; `InfrastructureAsset` 350-443 | Road/bridge topology, status, and integrity drive quality and capacity relief. |
| `src/world/_infrastructure.py` | `operational_edge_assets` 176-201; `effective_travel_duration` 221-237; `effective_travel_fatigue` 240-262 | V4-16 already owns infrastructure travel deltas; V4-17 layers condition on top without double counting. |
| `src/world/environment.py` | `Season` 56-62; `ActiveHazard` 74-104; `HazardRule` 249-285; `EnvironmentalDynamicsSpec.season_at` 431 | Season, weather, and hazards are existing derived facts; no new environment config. |
| `src/world/models.py` | `WeatherCondition` 96-100; `Location.adjacent` 82-111 | Route endpoints are adjacent locations; weather is per location. |
| `src/world/events.py` | schema constants 67-90; supported sets 91-168; infrastructure details 2766-2906; schema guards 3865-3873 | V27 must join every channel set and a new detail class must be registered. |
| `src/simulation/serialization.py` | detail encode 4676-4848; detail decode 6225-6513 | Every existing detail kind must accept schema V27 in a travel-network run. |
| `src/observer/version.py` | `SEMANTIC_EVENT_TYPES` 11-85; `SEMANTIC_TYPE_BY_KIND` 87-166 | Alias the new kind to an existing semantic type; keep 73. |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/world/travel_network.py` | modify | Add derivation functions and initial seeding contract. |
| `src/world/_travel_network.py` | create | Private derivation, transition, ordering, and event-detail helpers. |
| `src/world/_state.py` | modify | Add `travel_network` slot, constructor field, validation, property, rebuild support. |
| `src/world/_replay.py` | modify | Carry route conditions through rebuilds; full event projection lands in Phase 3. |
| `src/simulation/engine.py` | modify | Seed initial route conditions at bootstrap when the channel is active. |
| `src/world/events.py` | modify | Add `EVENT_SCHEMA_REPLAY_V27` and `RouteConditionChanged`. |
| `src/simulation/serialization.py` | modify | Encode/decode route details and accept V27 across existing kinds. |
| `src/observer/version.py` | modify | Alias `route_condition_changed` to `WEATHER_CHANGED`. |
| `tests/unit/test_travel_network_state.py` | create | State/channel and derivation tests. |
| `tests/unit/test_travel_network_events.py` | create | Event contract and wire tests. |

## Task 4: Add `WorldState` route-condition channel and bootstrap seeding

### Intent

Make route conditions first-class objective facts so movement, perception,
replay, checkpoints, and analysis all read the same authoritative values.

### Implementation Steps

1. In `src/world/_state.py`, add `_travel_network` to `WorldState.__slots__`.
2. Add constructor keyword
   `travel_network: Sequence[RouteCondition] | Mapping[tuple[str, str], RouteCondition] | None = None`.
3. Validate:
   - accept only `RouteCondition` rows;
   - reject duplicates by `edge_key`;
   - reject endpoints that are not adjacent in `_locations`;
   - reject more than `MAX_ROUTE_CONDITIONS` rows with
     `travel_network_route_cap_exceeded`;
   - sort by `edge_key` and freeze.
4. Add `WorldState.travel_network` property returning the ordered tuple and
   `WorldState.route_condition(origin, destination)` returning the matching row
   or `None`.
5. Extend `rebuild_world_state` with `travel_network=None` meaning "preserve
   existing"; an explicit sequence replaces it. Update every internal call that
   must preserve the channel.
6. In `src/simulation/engine.py`, when `travel_network_active` is true, seed the
   initial channel after locations, infrastructure, regions, weather, and
   hazards are available:
   `initial = derive_initial_route_conditions(state, season=current_season, tick=0)`;
   pass it into `WorldState`.
7. If the channel is inactive, leave `travel_network=None`/empty and preserve
   byte-identical behavior.
8. In `src/world/_replay.py`, ensure `rebuild_world_state` calls preserve
   `travel_network`; event projection is Task 7.

### Required Interfaces and Contracts

```python
WorldState(..., travel_network: Sequence[RouteCondition] | None = None)

@property
def travel_network(self) -> tuple[RouteCondition, ...]: ...

def route_condition(
    self, origin_id: EntityId, destination_id: EntityId
) -> RouteCondition | None: ...
```

- Every row is ordered by `(origin_id.value, destination_id.value)`.
- An absent channel is `None`/empty and never an implicit open condition.
- No route condition may reference a non-adjacent pair.
- Cap `MAX_ROUTE_CONDITIONS = 512`; overflow fails closed at construction.

### Requirement Evidence

- `src/world/_state.py` 321-474; `src/simulation/bootstrap.py`; index decision 3.

### Error Handling and Logging

- Invalid rows raise `ValueError` with codes:
  `travel_network_non_adjacent`, `travel_network_duplicate_route`,
  `travel_network_route_cap_exceeded`, `travel_network_invalid_condition`.
- `DEBUG world_state_route_conditions count=<n> channel=on|off`.
- Never log endpoint payload sets; only counts.

### Tests

- `tests/unit/test_travel_network_state.py`:
  - construction with ordered/unordered rows;
  - mapping input;
  - duplicate/non-adjacent/cap rejection;
  - `rebuild_world_state` preserve/replace;
  - inactive channel is empty;
  - property order and lookup.
- `uv run pytest tests/unit/test_travel_network_state.py tests/unit/test_world_state.py -q`

### Acceptance Criteria

- `WorldState` owns an immutable, ordered route-condition channel.
- Bootstrap seeds it only when the travel-network channel is active.
- Inactive runs remain unchanged.

### Verification

- `uv run pytest tests/unit/test_travel_network_state.py tests/unit/test_world_state.py -q`
- Expected: all pass.

## Task 5: Derive deterministic route conditions from objective facts

### Intent

Implement the locked `travel-network.v1` derivation. Every value must be a pure
function of route spec, adjacent topology, season, weather, active hazards, and
operational infrastructure. No RNG, wall clock, planner, or owner state.

### Implementation Steps

1. In `src/world/travel_network.py`, add:
   - `default_route_condition(origin_id, destination_id)` for no regions spec
     (duration 1, fatigue 0, capacity 8, risk 0, quality 0, open);
   - `derive_route_condition(state, origin_id, destination_id, *, season, tick)`;
   - `derive_initial_route_conditions(state, *, season, tick)`;
   - `effective_route_condition(state, origin_id, destination_id, *, season, tick)`
     which reads `state.route_condition(...)` first and derives only if absent.
2. In `src/world/_travel_network.py`, implement private helpers:
   - `_base_route(state, origin, destination)` using `RouteSpec` or defaults;
   - `_weather_for(state, location_id)`;
   - `_hazard_at(state, location_id, tick)`;
   - `_operational_edge_road(state, origin, destination)`;
   - `_operational_bridge_at(state, location_id)`;
   - `_infrastructure_quality(...)`;
   - `_status_and_cause(...)`.
3. Status precedence (first match wins):
   1. `STORM` at either endpoint and quality `< 0.5` → `CLOSED`,
      `blockage_cause=WEATHER`, reasons `weather_storm`, `route_closed`;
   2. `WINTER` and quality `< 0.5` → `CLOSED`, `blockage_cause=SEASONAL`,
      reasons `season_winter`, `route_closed`;
   3. active hazard at either endpoint → `RESTRICTED`,
      `blockage_cause=HAZARD`, reasons `hazard_active`, `route_restricted`;
   4. `STORM` with quality `>= 0.5` → `RESTRICTED`,
      `blockage_cause=WEATHER`, reason `infrastructure_relief`;
   5. `WINTER` with quality `>= 0.5` → `RESTRICTED`,
      `blockage_cause=SEASONAL`, reason `infrastructure_relief`;
   6. `RAIN` or `AUTUMN` → `RESTRICTED`, `blockage_cause=WEATHER` or
      `SEASONAL`, reason `route_restricted`;
   7. otherwise `OPEN`, `blockage_cause=NONE`.
4. `seasonal_availability` is season-only:
   - `CLOSED` for winter without infrastructure relief;
   - `RESTRICTED` for winter with relief or for autumn;
   - `OPEN` for spring and summer. Weather affects `status`, not
     `seasonal_availability`.
5. `infrastructure_quality`:
   - operational edge `ROAD` contributes its integrity;
   - operational `BRIDGE` at either endpoint contributes its integrity;
   - quality is the arithmetic mean of contributing rows, `0.0` if none, capped
     at `1.0`;
   - damaged/destroyed/below-floor assets never contribute.
6. `capacity`:
   - base is `min(ROUTE_BASE_CAPACITY, origin.body_capacity.value, destination.body_capacity.value)`
   - `+ ROAD_CAPACITY_BONUS` if an operational road exists on the edge
   - `+ BRIDGE_CAPACITY_BONUS` if an operational bridge exists at either endpoint
   - `+ SEASON_CAPACITY_DELTA[season]`
   - `+ HAZARD_CAPACITY_DELTA` if a hazard is active
   - clamp `ROUTE_MIN_CAPACITY..ROUTE_MAX_CAPACITY`.
7. `duration_ticks`:
   - start from V4-16 `effective_travel_duration(...)` when infrastructure is
     present, else base duration;
   - add `WEATHER_DURATION_DELTA[worst endpoint weather]` and
     `SEASON_DURATION_DELTA[season]` when a season exists;
   - clamp `>= 1`.
8. `risk`:
   - `0.1 * (1 - min(origin.visibility_factor.value, destination.visibility_factor.value))`
   - `+ WEATHER_RISK_DELTA[worst endpoint weather]`
   - `+ SEASON_RISK_DELTA[season]` when a season exists
   - `+ HAZARD_RISK_DELTA` if hazard active
   - `+ 0.02 * duration_ticks`
   - `- 0.3 * infrastructure_quality`
   - clamp `0.0..ROUTE_MAX_RISK`.
9. `fatigue_cost`:
   - start from V4-16 `effective_travel_fatigue(...)` when infrastructure is
     present, else base fatigue;
   - add `risk * ROUTE_RISK_FATIGUE_FACTOR`;
   - clamp `>= 0.0`.
10. `reason_codes` are deduplicated in locked order:
    `weather_storm`, `weather_rain`, `season_winter`, `season_autumn`,
    `hazard_active`, `route_closed`, `route_restricted`,
    `infrastructure_relief`, `infrastructure_absent`; cap 8.
11. `derive_initial_route_conditions` iterates every adjacent edge in sorted
    order, caps at `MAX_ROUTE_CONDITIONS`, and returns a tuple.
12. When no environment spec exists, callers pass `season=None`; seasonal deltas
    and seasonal availability are then open and absent.

### Required Interfaces and Contracts

```python
def derive_route_condition(
    state: WorldState,
    origin_id: EntityId,
    destination_id: EntityId,
    *,
    season: Season | None,
    tick: int,
) -> RouteCondition: ...

def derive_initial_route_conditions(
    state: WorldState, *, season: Season | None, tick: int
) -> tuple[RouteCondition, ...]: ...

def effective_route_condition(
    state: WorldState,
    origin_id: EntityId,
    destination_id: EntityId,
    *,
    season: Season | None,
    tick: int,
) -> RouteCondition: ...
```

- Pure function; no mutation, no logging of endpoint payload sets.
- Infrastructure deltas come only from `world._infrastructure` public helpers.
- `None` season means "calendar unavailable"; it does not mean summer.

### Requirement Evidence

- `src/world/regions.py` 64-99; `src/world/environment.py` 56-104/249-285/431; `src/world/_infrastructure.py` 176-262; index locked route-condition summary.

### Error Handling and Logging

- Missing/non-adjacent endpoints raise `ValueError` with
  `travel_network_invalid_endpoints`.
- `DEBUG travel_network_derived route_key=<origin>:<destination> status=<s> quality=<q> risk=<r>` is allowed at most once per derived row when `PALIMPSEST_LOG_LEVEL=DEBUG`; counts only at INFO.
- `WARN travel_network_route_cap_exceeded count=<n> cap=512` and fail closed.

### Tests

- `tests/unit/test_travel_network_state.py` (derivation half):
  - no regions/default route;
  - road reduces duration/fatigue and raises quality/capacity;
  - bridge relief at either endpoint;
  - damaged/destroyed infrastructure stops contributing;
  - winter closure without infrastructure and restricted with relief;
  - storm closure/relief, rain restriction, autumn restriction;
  - hazard restriction and risk/capacity deltas;
  - endpoint visibility raises risk and endpoint body capacity caps route capacity;
  - risk/fatigue/capacity clamps;
  - all edges seeded deterministically.
- `uv run pytest tests/unit/test_travel_network_state.py tests/unit/test_infrastructure_effects.py -q`

### Acceptance Criteria

- Every property is derived from listed facts only.
- Identical state/tick/season yields identical conditions.
- No RNG, wall clock, owner, or planner input.

### Verification

- `uv run pytest tests/unit/test_travel_network_state.py tests/unit/test_infrastructure_effects.py -q`
- Expected: all pass.

## Task 6: Add replay-v27 event contract and observer alias

### Intent

Make route-condition transitions effect-complete and replayable without
changing the reserved context pairs or the observer semantic count.

### Implementation Steps

1. In `src/world/events.py`:
   - add `EVENT_SCHEMA_REPLAY_V27: Final[int] = 27`;
   - add V27 to `SUPPORTED_EVENT_SCHEMA_VERSIONS`,
     `REPLAYABLE_EVENT_SCHEMA_VERSIONS`, `PHYSICAL_REPLAY_EVENT_SCHEMA_VERSIONS`;
   - add V27 to every existing channel schema frozenset (production,
     environment, artifact, lifecycle, new-agent, kinship, dependency care,
     knowledge repositories, experiment, possession, commitments, exchange,
     projects, public goods, journeys, contact, durable records, infrastructure).
2. Add `RouteConditionChanged` frozen detail class:
   `origin_location_id`, `destination_location_id`, `previous_status`,
   `current_status`, `previous_seasonal_availability`,
   `current_seasonal_availability`, `duration_ticks`, `fatigue_cost`,
   `capacity`, `risk`, `infrastructure_quality`, `blockage_cause`,
   `reason_codes`, `season`, `as_of_tick`, `kind="route_condition_changed"`.
3. Validate:
   - endpoints are `EntityId`, distinct, ordered;
   - status/availability/blockage/season strings are members of the closed
     enums (stored as `str` in the event layer);
   - the pair must differ in at least one semantic field: status, seasonal
     availability, capacity, risk, infrastructure quality, blockage cause, or
     reason codes; a status-only change is not required;
   - duration/fatigue/capacity/risk/quality ranges match `RouteCondition`;
   - reason codes are an ordered tuple of at most 8 stable tokens;
   - tick is non-negative.
4. Add to `EventDetails`, `_DETAIL_TYPES`,
   `_TRAVEL_NETWORK_DETAIL_TYPES`, and
   `_TRAVEL_NETWORK_EVENT_SCHEMAS = frozenset({EVENT_SCHEMA_REPLAY_V27})`.
5. Add `_payload_effect_complete`, `target_id_for_details`,
   `WorldEvent.__post_init__`, and `build_occurrence_context` branches. The
   route event has no actor and no target entity; occurrence exposes both
   endpoint locations and affected entity ids as the two endpoints.
6. In `src/simulation/serialization.py`:
   - add encode/decode cases for `route_condition_changed`;
   - add V27 to every existing detail/event allowlist;
   - reject V27 rows for the new kind under any other schema.
7. In `src/observer/version.py`, add
   `"route_condition_changed": "WEATHER_CHANGED"`. Do not add a semantic type;
   `len(SEMANTIC_EVENT_TYPES) == 73`.
8. Add a schema guard: `RouteConditionChanged` requires
   `EVENT_SCHEMA_REPLAY_V27`; existing infrastructure events still require V23
   and remain valid in V27 runs.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class RouteConditionChanged:
    origin_location_id: EntityId
    destination_location_id: EntityId
    previous_status: str
    current_status: str
    previous_seasonal_availability: str
    current_seasonal_availability: str
    duration_ticks: int
    fatigue_cost: float
    capacity: int
    risk: float
    infrastructure_quality: float
    blockage_cause: str
    reason_codes: tuple[str, ...]
    season: str | None
    as_of_tick: int
    kind: Literal["route_condition_changed"] = field(
        default="route_condition_changed", init=False
    )
```

- `EventDetails` union includes the new class.
- No new observer semantic type.
- No new command; command count stays 43.

### Requirement Evidence

- `src/world/events.py` 67-168/2766-2906; `src/observer/version.py` 11-166; index observer-semantics row.

### Error Handling and Logging

- Validation raises `ValueError` with
  `route_condition_changed_<field>` codes.
- `DEBUG route_condition_event_encoded origin=<id> destination=<id> status=<s>`.
- Never log reason-code payloads beyond safe counts at INFO.

### Tests

- `tests/unit/test_travel_network_events.py`:
  - detail construction/validation, including quality/risk-only transitions;
  - V27 membership for new and legacy kinds;
  - serialization round-trip for every existing kind under V27;
  - observer alias exists and semantic count is 73;
  - V26/V23 rejection for the new kind.
- `uv run pytest tests/unit/test_travel_network_events.py tests/unit/test_observer_contracts.py -q`

### Acceptance Criteria

- `RouteConditionChanged` is replayable only under V27.
- All existing detail kinds remain valid under V27.
- Observer semantics remain 73.

### Verification

- `uv run pytest tests/unit/test_travel_network_events.py tests/unit/test_observer_contracts.py -q`
- Expected: all pass.

## Phase Risks and Mitigations

- Risk: V27 holes (24-26 reserved) confuse schema readers.
  Mitigation: keep V27 explicit in every set; do not synthesize V24-V26.
- Risk: derivation double-counts V4-16 road/bridge deltas.
  Mitigation: start from `effective_travel_*` once, then apply only
  season/weather/risk adjustments; quality/capacity are additive metadata.
- Risk: route cap excludes large scenarios.
  Mitigation: cap 512 with fail-closed bootstrap and a bounded WARN; no silent
  truncation.

## Phase Completion Checklist

- Every task above satisfies its acceptance criteria.
- `index.md` checkboxes for Tasks 4-6 are updated after verification.
- No phase file contains task checkboxes.
