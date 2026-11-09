# Phase 4: Movement and Observation

Plan: [index.md](index.md)
Tasks: 10-13
Depends on: Phase 3 (Tasks 7-9)

## Objective

Make `WorldEngine` movement admit, reject, and charge travel exactly according
to the authoritative route condition, and expose only local adjacent route
facts to the observing agent. Closed routes reject; restricted routes cost more;
capacity and risk are enforced; flee and transport stop bypassing the same
pipeline.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/world/_rules.py` | `find_eligible_flee_destinations` 1126-1149; `_route_spec_for_edge` 1152-1162; `_travel_duration` 1171-1183; `_evaluate_move` 1212-1242; `_evaluate_transport` 1574-1617; `_evaluate_flee` 1669-1721; `_apply_regional_travel_command` 3222-3392; `_mutate_move` 3947-3969; `_mutate_transport` 4154-4170; `_mutate_flee` 4173-4186 | The sole admission/application pipeline; all paths must read one route condition. |
| `src/world/_infrastructure.py` | `effective_travel_duration` 221-237; `effective_travel_fatigue` 240-262; `effective_exposure_scale` 355-371 | Infrastructure deltas are already applied inside derivation; rules must not apply them twice. |
| `src/world/observations.py` | `VisibleExit` 284-325; `PERCEPTION_FIELD_ACCESS` 135-163; `Observation` 1365-1395 | Local exit facts are always self-visible; remote topology is omitted. |
| `src/world/_perception.py` | `_project_one` 280-437; `_sorted_exits` 576-622; `_present_environment` 440-478 | Perception already has the tick and environmental spec needed for route facts. |
| `src/simulation/serialization.py` | `_encode_visible_exit` 4040-4049; `_decode_visible_exit` 4052-4090 | Observation wire must retain legacy decode and add optional route fields. |
| `src/simulation/inspection.py` | `project_agent_visible` 876-938 | Historical inspection must return the same route facts as live observation. |
| `src/world/models.py` | `PhysicalRules.move_fatigue` 284; `transport_fatigue` 289 | Default/base costs remain the no-route fallback. |
| `src/world/regions.py` | `Journey` 227-297 | Journey shape stays unchanged; departure facts are charged and frozen at start. |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/world/_rules.py` | modify | Central route-condition lookup; admission reasons; duration/fatigue/capacity/risk. |
| `src/world/_travel_network.py` | modify | Add rule-facing lookup and reason helpers. |
| `src/world/_operations.py` | modify | Add `season`/`travel_network_active` to `prepare_action_batch` and all rule calls. |
| `src/world/observations.py` | modify | Add optional route fields to `VisibleExit`. |
| `src/world/_perception.py` | modify | Populate route facts for adjacent exits only. |
| `src/simulation/serialization.py` | modify | Encode/decode new optional exit fields. |
| `src/simulation/engine.py` | modify | Pass season and travel-network activation into rule application. |
| `src/world/_infrastructure.py` | modify | Add bounded quality/capacity helpers; no second travel delta. |
| `tests/unit/test_travel_network_movement.py` | create | Admission/application matrix. |
| `tests/unit/test_travel_network_perception.py` | create | Observation and parity tests. |

## Task 10: Enforce route conditions in movement rules

### Intent

One route condition governs `Move`, `Transport`, and `Flee`. Closed routes are
impossible, restricted routes carry explicit costs, and capacity is checked
before a journey starts.

### Implementation Steps

1. In `src/world/_travel_network.py`, add:
   - `condition_for_command(state, origin, destination, *, season, active)`
     returning `RouteCondition | None`;
   - `route_rejection_reason(condition, participant_count)` returning a
     `RuleReason | None`.
2. In `src/world/_rules.py`, add `season: Season | None = None` and
   `travel_network_active: bool = False` to `evaluate_operation`,
   `apply_operation`, `_apply_regional_travel_command`,
   `_evaluate_move`, `_evaluate_transport`, `_evaluate_flee`,
   `find_eligible_flee_destinations`, `_flee_structural_reject`, and
   `_travel_duration`.
3. Add `RuleReason` members:
   - `ROUTE_CLOSED`
   - `ROUTE_BLOCKED`
   - `ROUTE_CAPACITY_EXCEEDED`
   Keep existing reasons as fallback.
4. In `_evaluate_move`:
   - when active, read `condition_for_command`;
   - `CLOSED` rejects with `ROUTE_CLOSED` (or `ROUTE_BLOCKED` when a blockage
     cause is present);
   - participant count is 1; capacity check still runs.
5. In `_evaluate_transport`:
   - participant count is 2 (actor + target);
   - reject when `2 > capacity` with `ROUTE_CAPACITY_EXCEEDED`;
   - closed/blocked as above.
6. In `_evaluate_flee` and `find_eligible_flee_destinations`:
   - replace the raw `duration_ticks != 1` rule with the effective condition;
   - eligible only when `status != CLOSED`, `duration_ticks == 1`, and
     `1 <= capacity`;
   - keep the destination body-capacity check.
7. In `_apply_regional_travel_command`:
   - use the same effective condition for duration, fatigue, and capacity;
   - duration is `condition.duration_ticks` (already includes infrastructure,
     season, weather, and risk) — do not call `effective_travel_*` again;
   - fatigue is `condition.fatigue_cost` (risk surcharge included);
   - transport adds the existing `rules.transport_fatigue` delta exactly once;
   - apply skill multiplier after the condition cost;
   - `Journey.due_tick = tick + duration - 1` and
     `charged_fatigue_cost` stay unchanged in shape.
8. In `_mutate_move`, `_mutate_transport`, `_mutate_flee`:
   - when no regions spec or channel inactive, preserve current behavior;
   - when active, use the same condition helper; do not silently bypass.
9. In `src/world/_operations.py`:
   - add `season: Season | None = None` and
     `travel_network_active: bool = False` to `prepare_action_batch` (signature
     at 1316-1347);
   - pass both into the `evaluate_operation` calls at 1528 and 1625 and the
     `apply_operation` call at 1713.
10. In `src/simulation/engine.py`, compute `season` once per tick from
    `self._environmental_dynamics.season_at(tick)` (or `None`) and pass
    `season`/`travel_network_active` into `prepare_action_batch` at 4079 and any
    other rule-application call. Do not recompute season per action.
11. Do not change `Move`/`Transport`/`Flee` command shapes.

### Required Interfaces and Contracts

```python
def condition_for_command(
    state: WorldState,
    origin_id: EntityId,
    destination_id: EntityId,
    *,
    season: Season | None,
    active: bool,
) -> RouteCondition | None: ...

def route_rejection_reason(
    condition: RouteCondition, participant_count: int
) -> RuleReason | None: ...
```

- Closed → `ROUTE_CLOSED`; blocked cause → `ROUTE_BLOCKED`; capacity overflow →
  `ROUTE_CAPACITY_EXCEEDED`.
- Capacity for `Move`/`Flee` is 1 participant; for `Transport` it is 2.
- No route condition means legacy behavior, never an implicit open route.
- No new command; command count remains 43.

### Requirement Evidence

- `src/world/_rules.py` 1126-1786/3222-3392/3947-4186; `src/world/_operations.py` 1316-1713; index movement rows.

### Error Handling and Logging

- Rejections produce the existing outcome/reason plumbing; no exception.
- `DEBUG move_route_rejected actor_id=<id> reason=<code> status=<s>`.
- Never log endpoint sets or route payload bodies.

### Tests

- `tests/unit/test_travel_network_movement.py`:
  - open move uses condition duration/fatigue;
  - restricted move adds duration/fatigue/risk;
  - closed move rejects; blocked cause uses `ROUTE_BLOCKED`;
  - transport capacity 1 rejects with `ROUTE_CAPACITY_EXCEEDED`;
  - transport at capacity 2 succeeds;
  - flee uses effective condition and rejects closed;
  - road/bridge benefits are not double-counted;
  - no-region and channel-inactive paths unchanged.
- `uv run pytest tests/unit/test_travel_network_movement.py tests/unit/test_regional_travel_actions.py -q`

### Acceptance Criteria

- One condition drives all three movement commands.
- Capacity and risk are enforced deterministically.
- Existing infrastructure-only behavior is unchanged when the channel is off.

### Verification

- `uv run pytest tests/unit/test_travel_network_movement.py tests/unit/test_regional_travel_actions.py -q`
- Expected: all pass.

## Task 11: Expose route facts on `VisibleExit`

### Intent

Agents see the current objective condition only for adjacent exits. They never
receive remote topology, a global route table, or an omniscient path.

### Implementation Steps

1. Extend `VisibleExit` with optional fields:
   - `route_status: str | None`
   - `route_seasonal_availability: str | None`
   - `route_blockage_cause: str | None`
   - `route_capacity: int | None`
   - `route_risk: float | None`
   - `route_infrastructure_quality: float | None`
2. Validation:
   - all route fields are either all `None` or all present;
   - if present, `travel_duration_ticks` and `fatigue_cost` must be present;
   - status/availability/blockage values must be members of the closed sets;
   - capacity is `1..ROUTE_MAX_CAPACITY`; risk/quality are `0.0..1.0`.
3. In `_perception._sorted_exits`:
   - accept `environmental_dynamics`, `season`, and `travel_network_active`;
   - when active and a regions spec exists, read
     `effective_route_condition(state, origin, destination, season=..., tick=...)`;
   - populate duration/fatigue from the condition and the new route fields;
   - when inactive, preserve the existing raw `RouteSpec` projection.
4. Pass the activation flag through `PerceptionService.__init__` (derive from
   `infrastructure_networks_active and state.regions_migration is not None`) and
   `_project_one`. Update all engine construction sites:
   `src/simulation/engine.py` 837, 1339, and 1660; and the `_project_one` call
   at `src/world/_perception.py:232`. A restored engine must construct the
   service with the restored activation flag, not ambient config.
5. Keep `PERCEPTION_FIELD_ACCESS["exits"] = ALWAYS_SELF`; add no field for
   remote topology.
6. Do not expose `RouteCondition.reason_codes` in `VisibleExit` (diagnostic
   tokens remain objective/research-only).

### Required Interfaces and Contracts

- `VisibleExit` route fields are local and adjacent-only.
- Legacy payloads without route fields decode unchanged.
- `Observation.regional_context` and `ObservedJourney` remain unchanged.
- No new observation schema version; additive optional fields.

### Requirement Evidence

- `src/world/observations.py` 135-163/284-325; `src/world/_perception.py` 232/576-622; `src/simulation/engine.py` 837/1339/1660; index observation row.

### Error Handling and Logging

- Invalid partial route fields raise `ValueError` with
  `VisibleExit route fields must be all present or all absent`.
- `DEBUG exit_projected destination=<id> status=<s> capacity=<n> risk=<r>`.
- No route reason-code or endpoint set logging.

### Tests

- `tests/unit/test_travel_network_perception.py`:
  - active exits carry all route facts;
  - inactive exits preserve legacy shape;
  - partial field rejection;
  - only adjacent exits appear;
  - deterministic order;
  - no remote location/edge leakage.
- `uv run pytest tests/unit/test_travel_network_perception.py tests/unit/test_regional_travel_perception.py -q`

### Acceptance Criteria

- Agents receive local route facts only.
- Inactive behavior is byte-identical.
- No omniscient graph surface exists.

### Verification

- `uv run pytest tests/unit/test_travel_network_perception.py tests/unit/test_regional_travel_perception.py -q`
- Expected: all pass.

## Task 12: Serialize and parity-check route observations

### Intent

Keep live, restored, and inspection observations identical after adding route
fields.

### Implementation Steps

1. In `src/simulation/serialization.py`, extend `_encode_visible_exit`:
   only when all route fields are present, emit
   `route_status`, `route_seasonal_availability`, `route_blockage_cause`,
   `route_capacity`, `route_risk`, `route_infrastructure_quality`.
2. Extend `_decode_visible_exit`:
   - accept the six keys as an optional group;
   - reject partial groups;
   - validate string enums/ranges through `VisibleExit`;
   - preserve legacy payload decode.
3. Update `tests/unit/test_world_perception.py` or the observation round-trip
   fixture to include the new fields when present.
4. In `src/simulation/inspection.py`, verify `project_agent_visible` returns the
   same `VisibleExit` values without reading engine state; no code change
   expected.
5. Add a canonical observation parity test: live observation at tick T equals
   restored/checkpoint observation at tick T, including route fields.

### Required Interfaces and Contracts

- Domain serialization remains schema-version 1; route fields are additive
  optional fields.
- Unknown/partial keys fail closed.
- No objective route reason codes appear in observation payloads.

### Requirement Evidence

- `src/simulation/serialization.py` 4040-4090; `src/simulation/inspection.py` 876-938; index observation row.

### Error Handling and Logging

- `DomainSerializationError("invalid_fields", path)` for partial groups.
- `DEBUG visible_exit_encoded destination=<id> route_fields=<n>`.
- No payload dumps.

### Tests

- `tests/unit/test_travel_network_perception.py` (serialization half).
- `tests/unit/test_simulation_inspection.py` parity extension.
- `uv run pytest tests/unit/test_travel_network_perception.py tests/unit/test_simulation_inspection.py tests/unit/test_world_perception.py -q`

### Acceptance Criteria

- Live/restored/inspection observations match.
- Legacy observation payloads still decode.
- No new observation version or API route.

### Verification

- `uv run pytest tests/unit/test_travel_network_perception.py tests/unit/test_simulation_inspection.py tests/unit/test_world_perception.py -q`
- Expected: all pass.

## Task 13: Integrate infrastructure quality and fix movement inconsistencies

### Intent

Make infrastructure quality a first-class input to route condition without
double-counting V4-16 effects, and close the known flee/transport bypasses.

### Implementation Steps

1. In `src/world/_infrastructure.py`, add bounded helpers:
   - `edge_road_quality(assets, origin, destination) -> float`
   - `node_bridge_quality(assets, location_id) -> float`
   - `operational_road_capacity_bonus(assets, origin, destination) -> int`
   - `operational_bridge_capacity_bonus(assets, location_id) -> int`
   Use `effects_active(...)` and `MAX_INFRA_*` caps.
2. In `world/travel_network.py`, use those helpers only; do not inspect asset
   kinds directly outside `_infrastructure`.
3. Verify no double application:
   - `effective_travel_duration/fatigue` called once in derivation;
   - rules read `condition.duration_ticks/fatigue_cost` directly;
   - flee and non-regional transport use the same helper when active.
4. Add regression tests for:
   - a road that reduces duration from 2 to 1 and then winter adds 2;
   - a destroyed road no longer contributes quality/capacity but also no longer
     applies its delta;
   - a bridge at the destination endpoint relieves quality but does not alter a
     different edge;
   - transport fatigue includes the condition once, not twice.
5. Document the bridge semantics: a bridge is a node asset that contributes to
   `infrastructure_quality` and capacity for every incident edge; it does not
   create or remove graph edges.

### Required Interfaces and Contracts

```python
def edge_road_quality(
    assets: Sequence[InfrastructureAsset],
    origin_id: EntityId,
    destination_id: EntityId,
) -> float: ...

def node_bridge_quality(
    assets: Sequence[InfrastructureAsset], location_id: EntityId
) -> float: ...
```

- Only `OPERATIONAL` assets at or above catalog integrity contribute.
- Return `0.0` when none qualify.
- No owner/score/planner fields.

### Requirement Evidence

- `src/world/_infrastructure.py` 176-262; `src/world/_rules.py` movement paths; index infrastructure rows.

### Error Handling and Logging

- Invalid asset sequences raise `TypeError`/`ValueError` with stable codes.
- `DEBUG infrastructure_route_quality edge=<origin>:<destination> quality=<q>`.
- No asset payload dumps.

### Tests

- `tests/unit/test_travel_network_infrastructure.py`:
  - road/bridge quality and capacity;
  - damaged/destroyed exclusion;
  - edge isolation;
  - no double count in duration/fatigue;
  - flee/transport parity.
- `uv run pytest tests/unit/test_travel_network_infrastructure.py tests/unit/test_infrastructure_effects.py tests/unit/test_infrastructure_contract.py -q`

### Acceptance Criteria

- Infrastructure alters route quality/capacity/condition exactly once.
- Flee and transport use the same condition pipeline.
- Existing V4-16 effect tests remain green.

### Verification

- `uv run pytest tests/unit/test_travel_network_infrastructure.py tests/unit/test_infrastructure_effects.py tests/unit/test_infrastructure_contract.py -q`
- Expected: all pass.

## Phase Risks and Mitigations

- Risk: double-counting infrastructure deltas changes travel times.
  Mitigation: one derivation point and explicit no-double-count tests.
- Risk: observation leaks remote topology.
  Mitigation: only `state.locations[origin].adjacent` is iterated; no global
  route table in `VisibleExit`.
- Risk: flee/transport parity regressions.
  Mitigation: shared condition helper and cross-command tests.

## Phase Completion Checklist

- Every task above satisfies its acceptance criteria.
- `index.md` checkboxes for Tasks 10-13 are updated after verification.
- No phase file contains task checkboxes.
