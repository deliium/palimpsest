# Phase 3: Replay, Checkpoints, and Tick Transitions

Plan: [index.md](index.md)
Tasks: 7-9
Depends on: Phase 2 (Tasks 4-6)

## Objective

Make route conditions fully replayable and checkpointable under the V4-17
deepening pair `(27, "v25")`, and emit deterministic transition events once per
changed edge at the tick boundary before observation.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/world/_replay.py` | imports 58-61/92-101; `_prepare_events` 400-424; effect dispatch 590-755; infrastructure branch 746-753; `_project_infrastructure_event` 2859-2894 | Route transitions need the same replay fold pattern as infrastructure. |
| `src/simulation/persistence.py` | accepted events 115-140; accepted codecs 142-165; `WorldSnapshot` 623-659; infrastructure validation 766-781; `schema_projector_compatible` 451-481 | V27 and `"v25"` must be accepted; snapshot rows require exact codec/schema pairing. |
| `src/simulation/journal.py` | bind snapshot 520-568; encode 852-1077; v21 branch 1065-1077; decode 1211-1397; v21 keys 1359-1362; asset codec 2310-2396 | Codec v25 needs its own encode/decode branch and row codec. |
| `src/simulation/engine.py` | action/journey/production/infrastructure order 4177-4300; `apply_autonomous_physical_step` 4280; `select_checkpoint_schema` 6625-6705 | Route recomputation must run after physical evolution and before observation. |
| `src/simulation/runner.py` | `_engine_snapshot` 7132-7167; row assembly 7168-7334; snapshot draft 7352-7376 | Runner must pass `travel_network` rows and the activation flag. |
| `src/simulation/service.py` | `draft_checkpoint_from_candidate` 126-155 | Live service checkpoints must select `(27, "v25")`. |
| `src/simulation/versioning.py` | deepening pair from Task 1 | The pair is `(TRAVEL_NETWORK_WRITE_PAIR_EVENT, TRAVEL_NETWORK_WRITE_PAIR_CODEC)`. |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/world/_replay.py` | modify | Add V27 support and `_project_route_condition_changed`. |
| `src/simulation/persistence.py` | modify | Accept V27/`v25`; add snapshot rows; select the travel pair. |
| `src/simulation/journal.py` | modify | Add codec v25 encode/decode and `RouteCondition` row codec. |
| `src/simulation/engine.py` | modify | Add checkpoint branch, tick transition, and event emission. |
| `src/simulation/runner.py` | modify | Build and pass route-condition rows. |
| `src/simulation/service.py` | modify | Add v21/v25 cumulative rows and `travel_network` rows; pass both activation flags to checkpoint selection. |
| `tests/unit/test_travel_network_replay.py` | create | Replay fold tests. |
| `tests/unit/test_travel_network_checkpoint.py` | create | Codec/selection tests. |
| `tests/unit/test_travel_network_tick.py` | create | Transition emission tests. |

## Task 7: Project route conditions through replay

### Intent

Ensure a replayed run reconstructs the exact route-condition channel and never
re-derives a different state from ambient inputs.

### Implementation Steps

1. In `src/world/_replay.py`, import `EVENT_SCHEMA_REPLAY_V27`,
   `RouteConditionChanged`, and `RouteCondition`.
2. Add V27 to `_prepare_events` acceptance.
3. Add an `_apply_event_effect` branch for `route_condition_changed`.
4. Implement `_project_route_condition_changed(state, detail)`:
   - build a `RouteCondition` from detail fields, including
     `duration_ticks=detail.duration_ticks`, `fatigue_cost=detail.fatigue_cost`,
     and `as_of_tick=detail.as_of_tick`;
   - replace or insert by `edge_key`;
   - keep the channel sorted and capped;
   - rebuild via `rebuild_world_state(state, travel_network=next_rows)`.
5. If the event references a non-adjacent pair, raise
   `ValueError("route_condition_changed_non_adjacent")`.
6. Do not recompute weather/season/infrastructure during the event fold.
7. Preserve pre-V27 replay: no route events means the channel stays empty and
   behavior is byte-identical.

### Required Interfaces and Contracts

- Event details are the only replayed source of route transitions.
- `WorldState.travel_network` remains ordered by `edge_key`.
- A route event may change status, availability, capacity, risk, quality,
  blockage cause, and reasons; it may not change endpoints or identity.
- Replay of a V27 run must be identical whether the channel is restored from a
  checkpoint or folded from events.

### Requirement Evidence

- `src/world/_replay.py` 400-755/2859-2894; index write-pair and checkpoint rows.

### Error Handling and Logging

- Non-adjacent or duplicate endpoint state raises a stable `ValueError`.
- `DEBUG route_condition_replayed origin=<id> destination=<id> status=<s>`.
- No payload dumps.

### Tests

- `tests/unit/test_travel_network_replay.py`:
  - one transition folds;
  - repeated transition replaces the same edge;
  - multiple edges remain ordered;
  - non-adjacent rejection;
  - V23 runs without route events are unchanged;
  - event-fold state equals checkpoint-restored state.
- `uv run pytest tests/unit/test_travel_network_replay.py tests/unit/test_regional_travel_replay.py -q`

### Acceptance Criteria

- Replay reconstructs route conditions exactly.
- No route condition is derived from ambient state during replay.
- Legacy replay remains unchanged.

### Verification

- `uv run pytest tests/unit/test_travel_network_replay.py tests/unit/test_regional_travel_replay.py -q`
- Expected: all pass.

## Task 8: Add codec v25 checkpoints and journal support

### Intent

Persist the route-condition channel under an exact new codec while keeping v21,
v19, and earlier checkpoints decodable and byte-verifiable.

### Implementation Steps

1. In `src/simulation/persistence.py`:
   - import `EVENT_SCHEMA_REPLAY_V27` and `RouteCondition`;
   - add V27 to `ACCEPTED_EVENT_SCHEMA_VERSIONS`;
   - add `"v25"` to `ACCEPTED_PERSISTENCE_CODEC_VERSIONS`;
   - add `travel_network: Sequence[RouteCondition] | None = None` to
     `WorldSnapshot`;
   - validate: `"v25"` requires schema V27 and a non-`None` sequence; rows are
     `RouteCondition`, ordered, unique, and capped; any other codec rejects
     route rows (`travel_network_checkpoint_fields_require_codec_v25`);
   - make v25 cumulative: it accepts every v21 field (`infrastructure`,
     `regions_migration`, `journeys`) plus `travel_network`; v21 rejects route
     rows and v25 rejects `None` (an empty tuple is valid for an edgeless
     world);
   - add `travel_network_active: bool = False` to
     `checkpoint_schema_for_production`; make it the first branch returning
     `(TRAVEL_NETWORK_WRITE_PAIR_EVENT, TRAVEL_NETWORK_WRITE_PAIR_CODEC)`;
   - add V27 to `schema_projector_compatible` and codec/schema guards.
2. In `src/simulation/journal.py`:
   - import V27 and `RouteCondition`;
   - add a `"v25"` base-codec mapping and extra-key set equal to the v21 keys
     plus `travel_network`;
   - add `_encode_route_condition`/`_decode_route_condition` with exact keys:
     `origin_id`, `destination_id`, `status`, `seasonal_availability`,
     `blockage_cause`, `duration_ticks`, `fatigue_cost`, `capacity`, `risk`,
     `infrastructure_quality`, `reason_codes`, `as_of_tick`;
   - encode/decode `travel_network` rows;
   - update `bind_snapshot_commit_hash` and `_decode_world_event` upper bound to V27.
3. In `src/simulation/engine.py`:
   - add `travel_network_active` to `select_checkpoint_schema`;
   - add a branch above `infrastructure_networks_active`;
   - pass it at every call site (2087, 2332, 4593, and the detached restore path).
4. In `src/simulation/runner.py`, add
   `travel_network=snapshot.world.state.travel_network` to the checkpoint draft
   and include `"v25"` in every cumulative `codec_version in {...}` row set that
   already contains `"v21"`.
5. In `src/simulation/service.py`:
   - add `"v21"` and `"v25"` to the cumulative `production_rows` codec sets that
     currently stop at `"v20"`; include `infrastructure` and the v21
     `regions_migration`/`journeys` rows;
   - add `production_rows["travel_network"] = tuple(state.travel_network)` when
     `codec_version == "v25"`;
   - add `travel_network=draft.travel_network` to the final `WorldSnapshot`
     construction;
   - pass `travel_network_active` to checkpoint selection.
6. Keep `PERSISTENCE_CODEC_VERSION` and `EVENT_SCHEMA_VERSION` unchanged.
7. Add a mixed-schema test: a root containing both v21 and v25 checkpoints reads
   both without rewriting either, and a v25 checkpoint without a v21-era
   infrastructure row remains decodable.

### Required Interfaces and Contracts

- `checkpoint_schema_for_production(travel_network_active=True)` returns
  `(27, "v25")` before any other branch.
- `WorldSnapshot(persistence_codec_version="v25", event_schema_version=27, travel_network=(...))`
  validates; `v25` with V23 or `None` rejects; an empty tuple is valid for an
  edgeless world.
- Codec v25 is canonical and hash-stable.
- Prior codecs remain accepted; route rows are absent there.

### Requirement Evidence

- `src/simulation/persistence.py` 115-165/257-403; `src/simulation/journal.py`; `src/simulation/service.py` 126-355; index write-pair row.

### Error Handling and Logging

- Stable errors: `travel_network_checkpoint_fields_require_codec_v25`,
  `travel_network_checkpoint_requires_schema_v27`,
  `travel_network_checkpoint_invalid_rows`.
- `INFO checkpoint_schema_selected schema_version=27 codec=v25 reason=travel_network_active`.
- Never log route reason-code bodies; log counts.

### Tests

- `tests/unit/test_travel_network_checkpoint.py`:
  - selection priority for travel/infrastructure/regions/default;
  - v25 round-trip and hash stability;
  - v25/schema mismatch rejection;
  - v21/v19 checkpoints still decode;
  - mixed v21/v25 roots read both without rewriting;
  - service draft includes v21 infrastructure and v25 route rows;
  - journal encode/decode exact-key rejection.
- `uv run pytest tests/unit/test_travel_network_checkpoint.py tests/unit/test_infrastructure_replay.py tests/unit/test_regional_travel_checkpoint.py -q`

### Acceptance Criteria

- Travel-network runs write `(27, "v25")`.
- Infrastructure-only runs still write `(23, "v21")`; regions-only `(21, "v19")`.
- Legacy checkpoints decode unchanged.

### Verification

- `uv run pytest tests/unit/test_travel_network_checkpoint.py tests/unit/test_infrastructure_replay.py tests/unit/test_regional_travel_checkpoint.py -q`
- Expected: all pass.

## Task 9: Emit route-condition transitions at tick boundaries

### Intent

Turn derived changes into effect-complete events once per changed edge, after
weather/season/hazard/infrastructure changes and before the next observation.

### Implementation Steps

1. Add `advance_route_conditions(state, *, season, tick) ->
   tuple[WorldState, tuple[RouteConditionChanged, ...]]` to
   `src/world/_travel_network.py`.
2. Compute the next tuple over every current adjacency edge in sorted order,
   capped at `MAX_ROUTE_CONDITIONS`.
3. Compare each `RouteCondition` to the prior row by semantic fields: status,
   seasonal availability, duration, fatigue, capacity, risk, infrastructure
   quality, blockage cause, and reason codes. Any difference is a transition;
   endpoint identity and `as_of_tick` alone are not transitions.
4. For an unchanged edge, preserve the prior row byte-for-byte, including its
   `as_of_tick`. For a changed edge, create the next row with
   `as_of_tick=detail.as_of_tick` and emit one `RouteConditionChanged` in edge
   order, even when the status stays the same (for example, quality/risk
   changes while remaining open).
5. Return the next state with the full next tuple even when no event is emitted.
6. In `src/simulation/engine.py`, call it after
   `apply_autonomous_physical_step(...)` and before assembling `system_pending`.
   Pass the current season:
   `season = self._environmental_dynamics.season_at(snap.tick.value)` when the
   spec exists, else `None`.
7. Convert each detail into a `PendingEvent` with
   `SystemCause(effect_family=SystemEffectFamily.TRAVEL, ...)`. Continue the
   journey-event ordinal space or use deterministic ordinals starting after the
   journey count; never reuse an ordinal.
8. Ensure the state used for observation is the post-transition state.
9. Do not emit when the channel is inactive or when no field changed.
10. `WARN travel_network_transition_count tick=<t> count=<n>` only when count
    exceeds `MAX_ROUTE_CONDITIONS` (impossible after cap) or when an edge is
    missing from the derived tuple.
11. State the intra-tick rule explicitly: movement during the action phase reads
    the condition persisted at the previous tick boundary. Infrastructure,
    weather, season, and hazard changes become movement-visible at the next
    boundary. This keeps a tick's action resolution deterministic and avoids
    mutating route state mid-batch.

### Required Interfaces and Contracts

```python
def advance_route_conditions(
    state: WorldState, *, season: Season | None, tick: int
) -> tuple[WorldState, tuple[RouteConditionChanged, ...]]: ...
```

- Ordering: sorted by `(origin_id.value, destination_id.value)`.
- One event per changed edge; no aggregate event.
- No event when every semantic field is unchanged.
- State and events are consistent: applying the events to the prior state
  yields the returned state.

### Requirement Evidence

- `src/simulation/engine.py` 4177-4300; index season/weather/hazard combination rows.

### Error Handling and Logging

- Missing adjacency/route data logs `WARN travel_network_unresolved_edge` and
  leaves the edge absent rather than inventing a condition.
- `DEBUG travel_network_transition tick=<t> changed=<n>`.
- No endpoint payload dumps.

### Tests

- `tests/unit/test_travel_network_tick.py`:
  - season change closes/restricts routes and emits once;
  - weather change restricts/closes;
  - road construction/damage/destroy changes quality/status;
  - hazard start/end transitions;
  - repeated tick with no change emits nothing and preserves `as_of_tick`;
  - quality/risk-only change with unchanged status still emits;
  - event fold equals returned state;
  - inactive channel emits nothing.
- `uv run pytest tests/unit/test_travel_network_tick.py tests/unit/test_regional_travel_lifecycle.py -q`

### Acceptance Criteria

- Transitions are deterministic, ordered, and effect-complete.
- Observation sees the post-transition condition.
- No duplicate or spurious events.

### Verification

- `uv run pytest tests/unit/test_travel_network_tick.py tests/unit/test_regional_travel_lifecycle.py -q`
- Expected: all pass.

## Phase Risks and Mitigations

- Risk: route events are emitted before or after observation inconsistently.
  Mitigation: one call site after physical evolution; add an event-fold equality
  test.
- Risk: codec v25 widens v21 or v19.
  Mitigation: exact schema/codec pairing and rejection tests.
- Risk: system cause-ordinal collisions with journey events.
  Mitigation: deterministic ordinal offset after journey transitions and a test
  that all cause ids are unique.

## Phase Completion Checklist

- Every task above satisfies its acceptance criteria.
- `index.md` checkboxes for Tasks 7-9 are updated after verification.
- No phase file contains task checkboxes.
