# Phase 1: Contract and Activation

Plan: [index.md](index.md)
Tasks: 1-3
Depends on: none

## Objective

Lock V4-17 as a deepening of the owned `infrastructure_networks` context and the
V3 `regions_migration` seam, register the new objective write pair without
stealing the reserved 23-26 / `v21`-`v24` slots, and make the travel-network
channel explicit in the engine without adding a V4 capability flag, a runner
schema, or a command.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/simulation/versioning.py` | `WritePairReservation` 27-36; `V4_WRITE_PAIR_RESERVATIONS` 39-75; `validate_write_pair_reservations` 104-150 | Reserved pairs are 23/`v21` infrastructure, 24/`v22` epidemics, 25/`v23` ecological, 26/`v24` disasters; validation requires contiguous reservations and full context coverage. |
| `src/simulation/v4_architecture.py` | `INFRASTRUCTURE_NETWORKS` spec 184-197; `_REQUIRED_CONTEXT_COUNT` 56; `V4_CONTEXT_MAP_VERSION` 38; `V4_CAPABILITY_FLAGS` 330-332 | V4-17 must not add a context or flag: the registry stays 14 contexts / 12 flags / six owned. |
| `src/simulation/compatibility.py` | `V4_OWNED_CAPABILITY_FLAGS` 155-164; v56 prose 534-541; `v4_capability_flags` row 768-789 | The owned-flag frozenset is mirrored in `runner_models` and must remain equal; no v57 exists. |
| `src/simulation/runner_models.py` | `_V4_OWNED_CAPABILITY_FLAGS` 325-334; `V4CapabilityFlags` 1123-1174; v56 gate 8065-8096; infrastructure gate 8097-8128 | Reuse accepted `runner-config-v56`; do not add a flag field or root key. |
| `src/simulation/persistence.py` | `checkpoint_schema_for_production` 257-403; infrastructure branch 288-296 | The travel-network channel needs a higher-priority branch than `(23, "v21")`. |
| `src/simulation/engine.py` | `select_checkpoint_schema` 6625-6705; infrastructure bind 392-405; constructor 821-849 | The engine owns activation, restore, and checkpoint selection. |
| `src/simulation/runner.py` | infrastructure/regions inputs 2661; `_engine_snapshot` 7132-7167; snapshot draft 7352-7376 | The runner passes flags and builds checkpoint rows. |
| `src/simulation/service.py` | `draft_checkpoint_from_candidate` 126-155 | This path currently omits `infrastructure_networks_active`; V4-17 must thread both flags. |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/simulation/versioning.py` | modify | Add a separately validated deepening write pair `(27, "v25")` for the `infrastructure_networks` context; keep reserved pairs untouched. |
| `src/simulation/__init__.py` | modify | Export the deepening pair constants and `validate_deepening_write_pairs` through the public simulation facade. |
| `src/simulation/compatibility.py` | modify | Document V4-17 as a deepening, the travel-network pair, and update the `event_schema` / `persistence_codec` / `runner_config` matrix rows. |
| `src/simulation/runner.py` | modify | Compute `travel_network_active`; pass it to the engine and checkpoint selection. |
| `src/simulation/engine.py` | modify | Accept, validate, expose, bind, and restore `travel_network_active`; add checkpoint-selection branch. |
| `src/simulation/runner_models.py` | modify | Add prerequisite logging/validation only; no new flag or root field. |
| `src/simulation/service.py` | modify | Pass `infrastructure_networks_active` and `travel_network_active` to checkpoint selection. |
| `pyproject.toml` | modify | Allow the private `world._travel_network` module in the import-linter simulation-only contract. |
| `tests/architecture/boundary_checker.py` | modify | Allow `world._travel_network` in the AST private-world allowlist. |
| `tests/unit/test_v4_versioning_reservations.py` | modify | Pin the deepening pair and prove reservations 23-26 are unchanged. |
| `tests/unit/test_compatibility_matrix.py` | modify | Pin the event/codec matrix text and accepted sets. |
| `tests/architecture/test_v4_architecture_invariants.py` | modify | Keep 14 contexts / 12 flags / six owned; assert no v57 and no new context. |
| `tests/unit/test_travel_network_activation.py` | create | Cover every activation combination. |

## Task 1: Register travel-network deepening write pair and pins

### Intent

Give V4-17 an explicit, testable write pair that does not reallocate the
reserved `epidemics` (`24`/`v22`), `ecological_feedback` (`25`/`v23`), or
`disasters` (`26`/`v24`) slots. The pair is metadata for a deepening of an
already-owned context, not a new capability.

### Implementation Steps

1. In `src/simulation/versioning.py`, add:
   - `TRAVEL_NETWORK_WRITE_PAIR_EVENT: Final[int] = 27`
   - `TRAVEL_NETWORK_WRITE_PAIR_CODEC: Final[str] = "v25"`
   - `V4_DEEPENING_WRITE_PAIRS: Final[tuple[DeepeningWritePair, ...]]` with one row:
     `context_id=V4ContextId.INFRASTRUCTURE_NETWORKS`,
     `event_schema=27`, `codec_version="v25"`,
     `reason="derived route conditions and their transitions must replay"`.
2. Define `DeepeningWritePair` as a frozen dataclass with the same validation
   style as `WritePairReservation`.
3. In `validate_write_pair_reservations`, do **not** append the deepening pair
   to `V4_WRITE_PAIR_RESERVATIONS`. Add a separate
   `validate_deepening_write_pairs(...)` that asserts:
   - every event is strictly greater than `max(reserved.event_schema)`;
   - every codec number is strictly greater than `max(codec_number(reserved))`;
   - events and codecs are unique and contiguous within the deepening tuple;
   - the context exists, is not analysis-only, and is already owned.
4. Export both validators and the three deepening constants from
   `simulation/versioning.py` and `src/simulation/__init__.py`; call both
   validators from `tests/architecture/test_v4_architecture_invariants.py`.
5. Keep `V4_EVENT_REUSING_CONTEXTS` and the 14-context registry unchanged.
6. In `src/simulation/compatibility.py`:
   - extend the v56 ownership paragraph: V4-17 is a deepening of
     `infrastructure_networks`; it adds no flag, context, or v57, and activates
     `(27, "v25")` only when the travel-network channel is active;
   - update the `event_schema` `bump_trigger` / `v1_fixture_impact` text to name
     replay-v27 and the unchanged replay-v23 infrastructure write;
   - update the `persistence_codec` text to name codec v25 and the unchanged
     v21/v19 restores;
   - keep `_MATRIX` accepted sets derived from the accepted constants, not
     hand-written lists.
7. In `pyproject.toml` and `tests/architecture/boundary_checker.py`, add
   `world._travel_network` to the private-world authority allowlists. The module
   is private, so only `simulation.engine`, `simulation.bootstrap`, and private
   world modules may import it. Do not add it to `world.__all__`.
8. Update `tests/unit/test_v4_versioning_reservations.py` to assert:
   reserved events are exactly `[23, 24, 25, 26]`, reserved codecs exactly
   `["v21", "v22", "v23", "v24"]`, deepening events exactly `[27]`, deepening
   codecs exactly `["v25"]`, and no overlap.
9. Update `tests/unit/test_compatibility_matrix.py` for the new event/codec
   matrix text, accepted restore sets, and unchanged runner v4/v55/v56 rows.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class DeepeningWritePair:
    context_id: V4ContextId
    event_schema: int
    codec_version: str
    reason: str

V4_DEEPENING_WRITE_PAIRS: Final[tuple[DeepeningWritePair, ...]] = (
    DeepeningWritePair(
        context_id=V4ContextId.INFRASTRUCTURE_NETWORKS,
        event_schema=27,
        codec_version="v25",
        reason="derived route conditions and their transitions must replay",
    ),
)

def validate_deepening_write_pairs(
    pairs: Sequence[DeepeningWritePair] = V4_DEEPENING_WRITE_PAIRS,
    *,
    reservations: Sequence[WritePairReservation] = V4_WRITE_PAIR_RESERVATIONS,
) -> None: ...
```

- `simulation.__all__` adds `DeepeningWritePair`,
  `TRAVEL_NETWORK_WRITE_PAIR_EVENT`, `TRAVEL_NETWORK_WRITE_PAIR_CODEC`,
  `V4_DEEPENING_WRITE_PAIRS`, and `validate_deepening_write_pairs`.
- Failure codes: `v4_deepening_pair_noncontiguous_event`,
  `v4_deepening_pair_noncontiguous_codec`, `v4_deepening_pair_overlap`,
  `v4_deepening_pair_unknown_context`, `v4_deepening_pair_unowned_context`.
- `V4_OWNED_CAPABILITY_FLAGS` stays exactly six names.

### Requirement Evidence

- `src/simulation/versioning.py` 39-75/104-150; `src/simulation/compatibility.py` 155-164; index decisions 1-2 and the activation matrix.

### Error Handling and Logging

- `INFO [aif-plan] travel_network_pair event=27 codec=v25 context=infrastructure_networks`.
- Invalid metadata raises `ValueError` with a stable code; never log payloads.
- No runtime behavior is gated in this task; validation is import-time metadata.

### Tests

- `tests/unit/test_v4_versioning_reservations.py` — reserved span, deepening span,
  overlap rejection, unowned-context rejection.
- `tests/unit/test_compatibility_matrix.py` — matrix text and accepted sets.
- `tests/architecture/test_v4_architecture_invariants.py` — call both validators;
  assert 14 contexts, 12 flags, six owned, no v57.
- `tests/architecture/test_travel_network_boundaries.py` — `world._travel_network`
  is private, allowlisted for simulation/private-world imports only, and absent
  from `world.__all__`.
- `uv run pytest tests/unit/test_v4_versioning_reservations.py tests/unit/test_compatibility_matrix.py tests/architecture/test_v4_architecture_invariants.py -q`

### Acceptance Criteria

- Reserved write pairs are byte-identical to V4-16.
- A separately validated `(27, "v25")` deepening pair exists.
- No V4 context, flag, runner schema, or command changes.

### Verification

- `uv run pytest tests/unit/test_v4_versioning_reservations.py tests/unit/test_compatibility_matrix.py tests/architecture/test_v4_architecture_invariants.py -q`
- Expected: all pass; no `v4_pair_*` or `v4_deepening_pair_*` failures.

## Task 2: Lock `travel-network.v1` route-condition contract

### Intent

Define one closed, immutable route-condition vocabulary before any engine or
cognition code consumes it. All later phases use these exact enums, fields,
constants, and validation codes.

### Implementation Steps

1. Create `src/world/travel_network.py` with module docstring:
   "Locked travel-network policy contracts (objective, location-based)."
2. Add module-level locked constants (no mutable policy object): all values in
   step 7 plus `TRAVEL_NETWORK_POLICY_ID: Final[str] = "travel-network.v1"`.
   Derivation functions read these constants directly so no caller can inject a
   different policy.
3. Add closed enums:
   - `RouteStatus`: `OPEN`, `RESTRICTED`, `CLOSED`
   - `SeasonalAvailability`: `OPEN`, `RESTRICTED`, `CLOSED`
   - `RouteBlockageCause`: `NONE`, `WEATHER`, `SEASONAL`, `HAZARD`
4. Add `RouteCondition` frozen dataclass with exact fields:
   `origin_id: EntityId`, `destination_id: EntityId`,
   `status: RouteStatus`, `seasonal_availability: SeasonalAvailability`,
   `blockage_cause: RouteBlockageCause`, `duration_ticks: int`,
   `fatigue_cost: float`, `capacity: int`, `risk: float`,
   `infrastructure_quality: float`, `reason_codes: tuple[str, ...]`,
   `as_of_tick: int`.
5. Validate:
   - endpoints are `EntityId`, distinct, and ordered by `value`;
   - enum types are exact;
   - `duration_ticks >= 1`; `fatigue_cost` finite and non-negative;
   - `1 <= capacity <= ROUTE_MAX_CAPACITY`;
   - `0.0 <= risk <= 1.0`; `0.0 <= infrastructure_quality <= 1.0`;
   - `reason_codes` is an ordered tuple of non-empty stable tokens, max 8;
   - `as_of_tick >= 0`.
6. Add `edge_key` property `tuple[str, str]` sorted by location value.
7. Add locked constants:
   - `MAX_ROUTE_CONDITIONS = 512`
   - `ROUTE_BASE_CAPACITY = 8`, `ROUTE_MIN_CAPACITY = 1`,
     `ROUTE_MAX_CAPACITY = 24`
   - `ROUTE_MAX_RISK = 1.0`, `ROUTE_RISK_FATIGUE_FACTOR = 2.0`
   - `ROAD_CAPACITY_BONUS = 2`, `BRIDGE_CAPACITY_BONUS = 1`
   - `INFRASTRUCTURE_QUALITY_RELIEF_THRESHOLD = 0.5`
   - `SEASON_DURATION_DELTA = {SPRING: 0, SUMMER: 0, AUTUMN: 1, WINTER: 2}`
   - `SEASON_CAPACITY_DELTA = {SPRING: 0, SUMMER: 0, AUTUMN: -1, WINTER: -2}`
   - `SEASON_RISK_DELTA = {SPRING: 0.0, SUMMER: 0.0, AUTUMN: 0.1, WINTER: 0.2}`
   - `WEATHER_DURATION_DELTA = {CLEAR: 0, CLOUDY: 0, RAIN: 1, STORM: 2}`
   - `WEATHER_RISK_DELTA = {CLEAR: 0.0, CLOUDY: 0.0, RAIN: 0.15, STORM: 0.5}`
   - `HAZARD_RISK_DELTA = 0.3`, `HAZARD_CAPACITY_DELTA = -2`
   - `MAX_ROUTE_REASON_CODES = 8`
8. Add `RouteCondition.canonical()` returning the exact detached wire shape.
9. Add `require_route_condition(value, *, field_name)` and
   `require_route_conditions(sequence, *, max_items=MAX_ROUTE_CONDITIONS)`.
10. Add `TRAVEL_NETWORK_FORBIDDEN_FIELDS` including `score`, `route_score`,
    `civilization_score`, `planner`, `omniscient`, `owner_id`, `crew`,
    `nation_id`, `grid`, `coordinate`; reject them in `__post_init__` via the
    same presentation-field pattern used by `world.infrastructure`.
11. Export the public facade from `src/world/__init__.py` only if the package
    already re-exports sibling infrastructure contracts; otherwise keep
    explicit module imports.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class RouteCondition:
    origin_id: EntityId
    destination_id: EntityId
    status: RouteStatus
    seasonal_availability: SeasonalAvailability
    blockage_cause: RouteBlockageCause
    duration_ticks: int
    fatigue_cost: float
    capacity: int
    risk: float
    infrastructure_quality: float
    reason_codes: tuple[str, ...]
    as_of_tick: int

    @property
    def edge_key(self) -> tuple[str, str]: ...
    def canonical(self) -> dict[str, object]: ...
```

- No route condition stores an actor, owner, crew, planner, score, grid,
  coordinate, or remote topology.
- `reason_codes` are diagnostic tokens only: `weather_storm`, `weather_rain`,
  `season_winter`, `season_autumn`, `hazard_active`, `route_closed`,
  `route_restricted`, `infrastructure_relief`, `infrastructure_absent`.
- Default/no-channel behavior is untouched because this task only adds a
  contract and tests.

### Requirement Evidence

- `src/world/regions.py` 64-99; `src/world/infrastructure.py` 46-288; `src/world/environment.py` 56-104; index locked route-condition summary.

### Error Handling and Logging

- Validation logs `travel_network_validation_failed field=<name> reason_code=<code>`
  at ERROR and raises `ValueError` with the code.
- No actor ids beyond the two endpoint ids; no payload dumps.
- `DEBUG travel_network_contract_loaded policy_version=travel-network.v1`.

### Tests

- `tests/unit/test_travel_network_contract.py`:
  - valid open/restricted/closed rows round-trip `canonical()`;
  - endpoint ordering and self-edge rejection;
  - bad enum, duration, fatigue, capacity, risk, quality, reason-code, tick;
  - forbidden-field rejection;
  - max route count enforcement;
  - deterministic equality/order.
- `uv run pytest tests/unit/test_travel_network_contract.py -q`

### Acceptance Criteria

- The exact contract above exists and rejects invalid rows fail-closed.
- No runtime engine behavior changes yet.
- No V4 flag/context/command/event/codec is added in this task.

### Verification

- `uv run pytest tests/unit/test_travel_network_contract.py -q`
- Expected: all pass.

## Task 3: Activate the travel-network channel

### Intent

Make activation explicit and testable: the objective channel is active only
when both `infrastructure_networks` and `regions_migration` are active. No new
runner flag or root key is introduced.

### Implementation Steps

1. In `src/simulation/runner.py`, compute once per run:
   `travel_network_active = config.v4_capability_flags.infrastructure_networks and config.regions_migration is not None`.
2. Pass `travel_network_active` into `WorldEngine(...)` at the construction site
   near line 2661.
3. In `src/simulation/engine.py`:
   - add `travel_network_active: bool = False` to `__init__`;
   - validate exact `bool`;
   - store `_travel_network_active`;
   - expose `@property travel_network_active`;
   - include it in `__slots__` and the restore bind at line 1345 near
     `_infrastructure_networks_active`;
   - reject `travel_network_active` when `infrastructure_networks_active` is
     false or `regions_migration` is absent (`travel_network_requires_infrastructure`
     and `travel_network_requires_regions`);
   - pass the flag to every `select_checkpoint_schema` call site (2087, 2332,
     4593) and to every `PerceptionService` construction site (837, 1339, 1660).
4. In `src/simulation/service.py`, add both
   `infrastructure_networks_active=self._engine.infrastructure_networks_active`
   and `travel_network_active=self._engine.travel_network_active` to the
   `checkpoint_schema_for_production` call in
   `draft_checkpoint_from_candidate` (lines 140-155).
5. In `src/simulation/runner_models.py`, do not add a field. In
   `SimulationRunnerConfig.__post_init__`, emit
   `INFO travel_network_inactive reason=missing_regions` when infrastructure is
   active without a regions spec, and `INFO travel_network_inactive
   reason=infrastructure_off` when regions are active without the flag.
6. In `src/simulation/compatibility.py`, document the activation rule.
7. Add a single helper on `WorldEngine`:
   `def travel_network_active(self) -> bool` returns the stored bool; no dynamic
   recomputation after construction.
8. In the engine restore path, bind `_travel_network_active` from the restored
   snapshot/codec before constructing `PerceptionService` and before any
   observation or checkpoint call; a restored engine must not infer activation
   from ambient config.

### Required Interfaces and Contracts

- `WorldEngine.travel_network_active: bool` is immutable for a run.
- Activation matrix:
  - `infrastructure_networks=False`, `regions_migration=None` → false;
  - `False`, regions present → false;
  - `True`, `None` → false with INFO;
  - `True`, regions present → true.
- No `runner-config-v57`; no `v4_capability_flags` key changes.
- No new command; command count remains 43.

### Requirement Evidence

- `src/simulation/runner_models.py` v56 gate; `src/simulation/engine.py` 6625-6705; index activation matrix.

### Error Handling and Logging

- Invalid constructor type raises `TypeError`.
- Activation without prerequisites raises `ValueError` with stable codes.
- `INFO travel_network_active enabled=true infrastructure=true regions=true`.
- `INFO travel_network_active enabled=false reason=<missing_regions|infrastructure_off>`.
- Never log region labels or route payloads.

### Tests

- `tests/unit/test_travel_network_activation.py`:
  - four activation combinations;
  - engine property immutability;
  - checkpoint selection prefers travel network over infrastructure;
  - service draft uses the same pair;
  - no v57 accepted.
- `uv run pytest tests/unit/test_travel_network_activation.py tests/unit/test_runner_config_v56.py -q`

### Acceptance Criteria

- Activation is deterministic and prerequisite-checked.
- No new V4 flag, context, runner schema, command, event, or codec.
- Existing infrastructure-only and regions-only runs keep their prior selection.

### Verification

- `uv run pytest tests/unit/test_travel_network_activation.py tests/unit/test_runner_config_v56.py -q`
- Expected: all pass.

## Phase Risks and Mitigations

- Risk: registering event 27 without a context breaks the reservation invariant.
  Mitigation: keep it in a separate deepening tuple and validate non-overlap
  explicitly.
- Risk: a hidden v57 requirement appears for route config.
  Mitigation: V4-17 derives route conditions from existing `RouteSpec`,
  environment, and infrastructure facts; it adds no root config.
- Risk: activation changes V4-16 checkpoint selection for infra+regions runs.
  Mitigation: this is intentional and pinned; old v21/v19 checkpoints remain
  decodable.

## Phase Completion Checklist

- Every task above satisfies its acceptance criteria.
- `index.md` checkboxes for Tasks 1-3 are updated after verification.
- No phase file contains task checkboxes.
