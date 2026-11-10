# Phase 6: Experiment and End-to-End

Plan: [index.md](index.md)
Tasks: 16-18
Depends on: Phase 5 / Tasks 13-15

## Objective

Register the off-gate experiment, prove trade networks emerge from real
`WorldEngine` exchanges and journeys, and lock determinism, bounds, and leakage
guards.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/experiments/travel_network_scenario.py` | `travel_network_scenario` 49-97; `_with_regions` 29-46 | Control/treatment wrapper pattern. |
| `src/experiments/infrastructure_networks_scenario.py` | `_v56` 70-110; condition pattern 111-141 | v56 flag/config composition. |
| `src/experiments/catalog.py` | `OFF_GATE_MATRIX_EXPERIMENT_IDS` 2799-2832; `experiment_infrastructure_networks` 5610-5628; `experiment_travel_network` 5631-5647 | Registration point. |
| `src/experiments/models.py` | `ExperimentDefinition`, `ExperimentCondition`, `ExperimentSeedMatrix` | Scenario DTOs. |
| `src/simulation/runner_models.py` | `ResourceExchangeProfileSpec` 5270-5349; `SubjectiveValuationSpec` 5195-5267 | Exchange/valuation config. |
| `tests/unit/test_travel_network_end_to_end.py` | real engine 33-95; real move 111-140; journal round-trip | E2E harness pattern. |
| `src/world/actions.py` | `Move` 52-59; `Give` 92-102; `NegotiateExchange` 882-908 | Commands used by E2E. |
| `src/world/events.py` | `ExchangeCompleted` 2514-2564; `JourneyStarted/Arrived` 414-462 | Evidence produced by E2E. |
| `tests/unit/test_infrastructure_end_to_end.py` | publication and API path | End-to-end snapshot pattern. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/experiments/trade_network_scenario.py` | create | Deterministic off-gate scenario over existing flags. |
| `src/experiments/catalog.py` | modify | `experiment_trade_networks` builder and off-gate id. |
| `src/experiments/__init__.py` | modify | Optional public export of the scenario builder. |
| `tests/unit/test_trade_networks_experiment.py` | create | Registration, determinism, off-gate, config tests. |
| `tests/unit/test_trade_networks_end_to_end.py` | create | Real engine exchange/journey/corridor/media E2E. |
| `tests/unit/test_trade_networks_determinism.py` | create | Repeat-run equality and stable ids. |
| `tests/unit/test_trade_networks_bounds.py` | create | Caps, truncation, row ordering. |
| `tests/unit/test_trade_networks_leakage.py` | create | No objective/analytical leak and no forbidden vocabulary. |
| `tests/integration/test_trade_networks_store_api.py` | create | Non-scale filesystem store + API integration. |

## Task 16: Register off-gate `trade_networks@1` experiment

### Intent

Make the feature reproducible without claiming a V4 flag or a V1 gate slot.

### Implementation Steps

1. Create `src/experiments/trade_network_scenario.py`:
   - `TRADE_NETWORKS_EXPERIMENT_ID = "trade_networks@1"`.
   - `trade_network_scenario(base: SimulationRunnerConfig, *,
     seed_matrix: ExperimentSeedMatrix | None = None, max_ticks: int = 48) ->
     ExperimentDefinition`.
   - Require `base.regions_migration is not None`; otherwise raise
     `ValueError("trade_networks_requires_regions")`.
   - Reuse `travel_network_scenario` to obtain the control/treatment arms.
   - Add `ResourceExchangeProfileSpec(policy_id="resource-exchange-profile-v1",
     acceptance_window_ticks=8)` and
     `SubjectiveValuationSpec(policy_id="subjective-valuation-v1",
     horizon_ticks=8, max_bundle=2)` to both arms with `replace`.
   - Rename condition ids to `trade-networks-control` and
     `trade-networks-treatment`; labels `trade_networks_control` and
     `trade_networks_treatment`.
   - Keep the V4 flag set unchanged from the travel arms; do not add
     `supply_chains`, `markets_credit`, or any new flag.
   - Set `paired_world_group=f"{TRADE_NETWORKS_EXPERIMENT_ID}-world"`.
   - Log `INFO experiment_registered experiment_id=%s arms=%s off_gate=true`.
2. In `src/experiments/catalog.py` add
   `experiment_trade_networks(base, *, seed_matrix=None, max_ticks=48)` near the
   travel builder, delegating to the scenario. Add `"trade_networks@1"` to
   `OFF_GATE_MATRIX_EXPERIMENT_IDS`.
3. Re-export from `src/experiments/__init__.py` if the existing catalog export
   pattern requires it; do not add the experiment to the V1 gate builder list.
4. Ensure the scenario uses only accepted `runner-config-v56` and existing
   per-agent/run-level specs; no `runner-config-v57` string appears.
5. Do not add a runner result field; the experiment remains a composition
   preset.

### Required Interfaces and Contracts

- Off-gate only; `v1_regression_profile` unchanged.
- Deterministic seed matrix default `(base.seed,)`.
- Same base config produces identical conditions.
- No new capability flag, schema, command, or event.

### Error Handling and Logging

- Missing regions raises a safe `ValueError`.
- `INFO` registration only; no person or config payloads.

### Tests

- `tests/unit/test_trade_networks_experiment.py`:
  - `test_experiment_id_is_off_gate`
  - `test_scenario_has_control_and_treatment`
  - `test_scenario_adds_exchange_and_valuation_specs`
  - `test_scenario_is_deterministic`
  - `test_scenario_requires_regions`
  - `test_v1_gate_profile_does_not_include_trade`
  - `test_no_runner_config_v57`

### Acceptance Criteria

- `trade_networks@1` is registered off-gate and reproducible.
- No new V4 flag, runner schema, command, event, or write pair is added.
- The scenario exercises exchange and valuation over existing flags.

### Verification

- `uv run pytest tests/unit/test_trade_networks_experiment.py -q`
- Expected result: all tests pass; no V1-gate membership.

## Task 17: Add in-process trade-network end-to-end coverage

### Intent

Prove the analytics consume real engine admission, not hand-built event
dictionaries: exchange at A, carry the same item to B, exchange again, then
derive a corridor and durable-media flow.

### Implementation Steps

1. Create `tests/unit/test_trade_networks_end_to_end.py` following
   `test_travel_network_end_to_end.py`:
   - Build two adjacent locations A/B with a `RouteSpec(A, B, 2, 3.0)`.
   - Bootstrap three bodies: body-1 and body-2 at A, body-3 at B.
   - Give body-1 a `FOOD` item and a `GENERIC` item; body-2 a `MATERIAL` item;
     body-3 a `TOOL` item. All are `Item` values with `holder_id` set.
   - Register agents and start a real `WorldEngine` with
     `collective_projects_active=True`, `infrastructure_networks_active=True`,
     `travel_network_active=True`.
   - Tick 0: body-1 offers `NegotiateExchange(counterparty=body-2, act="offer",
     give=(food, generic), take=(material,))`; body-2 accepts with
     `act="accept"` and the mirrored bundles `give=(material,)`,
     `take=(food, generic)`. Assert `ExchangeCompleted` and holder changes.
   - Move body-2 to B through the real route and wait for `JourneyArrived`.
   - At B, body-2 exchanges the food/generic items with body-3 for the tool.
   - Export committed events and call
     `harvest_trade_networks_analysis(events, policy=default..., window_tick=...)`.
   - Assert: `food` and `durable_exchange_media` transfers exist; the generic
     item has `flow_class == DURABLE_EXCHANGE_MEDIA` and at least two distinct
     counterparties; a corridor between A and B exists; a reverse trajectory (if
     exercised) is a distinct corridor in the same network; the corridor row
     count is bounded; no `WorldState` read is needed.
2. Add a second test for a gift (`Give`) that produces `records` evidence using
   a portable `NOTE` artifact moved by `TransferArtifact`/`ArtifactMoved` and
   then carried by a journey; assert a `records` transfer or explicit
   `partial` coverage, never a fabricated record.
3. Add a third test for absent movement: exchange at A only yields local flow
   and no corridor.
4. Use real `ActionSubmission` and `engine.resolve_tick`; do not call private
   mutation helpers or construct `WorldEvent` values directly.
5. Log nothing from the test unless a failure needs a count summary.

### Required Interfaces and Contracts

- Real `WorldEngine` admission and real event emission.
- At least one actual journey between locations.
- No synthetic event or row construction in the E2E path.
- The analysis output is deterministic across two identical runs.

### Error Handling and Logging

- Test failures may print safe counts only; never item/person payload dumps.

### Tests

- The file itself is the test suite:
  - `test_real_exchange_and_journey_create_corridor_and_media`
  - `test_local_exchange_has_no_corridor`
  - `test_reverse_trajectory_is_distinct_corridor_same_network`
  - `test_empty_window_dissolves_then_reemerges`
  - `test_sustained_transition_is_counted`
  - `test_operational_trade_post_marks_venue`
  - `test_gift_or_artifact_evidence_is_not_fabricated`

### Acceptance Criteria

- The E2E proves corridor creation from real item movement.
- Durable-media classification is derived from real repeated transfers.
- No objective state is read by the analysis.

### Verification

- `uv run pytest tests/unit/test_trade_networks_end_to_end.py -q`
- Expected result: all tests pass.

## Task 18: Add determinism property bounds and leakage coverage

### Intent

Lock the non-functional contract: identical inputs produce identical outputs,
caps hold, layers stay separated, and no forbidden vocabulary reaches any
surface.

### Implementation Steps

1. Add `tests/unit/test_trade_networks_determinism.py`:
   - Build a fixed event fixture (exchange, gift, artifact move, craft/harvest,
     journey).
   - Run `harvest_trade_networks_analysis` twice and assert equality of every
     row tuple, ids, notices, per-family coverage, and counts.
   - Reverse a copy of the event sequence and assert canonical sorting restores
     equality (after rejecting duplicate tokens).
   - Exercise an empty gap window and assert `dissolved` then `emerged`, not
     `continued`.
   - Assert sustained counts are stable and never score-like.
   - Hypothesis `test_ids_are_stable_for_generated_corridor_pairs`.
2. Add `tests/unit/test_trade_networks_bounds.py`:
   - Generate more transfers/corridors/networks than each cap without building
     huge payloads (use repeated synthetic rows).
   - Assert deterministic prefixes, `coverage="partial"`, one notice per capped
     family, and no row beyond the cap.
   - Hypothesis `test_analysis_rows_never_exceed_declared_caps`.
3. Add `tests/unit/test_trade_networks_leakage.py`:
   - Assert objective layer contains no `trd-cor-`/`trd-net-`/`trd-pair-`.
   - Assert analytical layers contain no raw event/item/artifact tokens.
   - Assert snapshots, API schemas, UI strings, and Godot fixture contain no
     `price`, `money`, `currency`, `central_planner`, `route_plan`, `quota`,
     `allocation`, `score`, or `ranking`.
   - Assert no module in `analysis/trade_networks_*`, `simulation/trade_networks_*`,
     `api/routes/trade_networks.py`, or `experiments/trade_networks_*` imports
     `WorldState`, `WorldEngine`, `ActionSubmission`, or `simulation.engine`.
4. Add `tests/integration/test_trade_networks_store_api.py`:
   - Compose a deterministic snapshot, publish through the real filesystem
     store in `tmp_path`, read it back, and serve the summary/corridors through
     the real FastAPI app with the dual gate enabled.
   - Mark `@pytest.mark.integration` and use no database or Docker.
   - Assert 503 with the gate unset, 200 with both settings, and a
     `window_index` filter that rejects a cursor bound to another window.
   - Assert network lineage status, cross-society anchors, and trade-post fields
     survive the store/API round trip.
5. Add a scale smoke only if the existing benchmark harness supports a pure
   in-process analysis workload; otherwise record the benchmark lane as a
   regression run in Task 22 and do not add a new benchmark file.

### Required Interfaces and Contracts

- Determinism is row-level, not merely count-level.
- Caps are hard upper bounds; truncation is explicit.
- Leakage guards cover code, snapshots, API schemas, UI, and Godot fixtures.
- Integration tests remain non-scale and DB-free.

### Error Handling and Logging

- Tests may inspect safe counts; no payload dumps.

### Tests

- The three unit files plus the integration file above.
- Hypothesis profiles remain deterministic and bounded.

### Acceptance Criteria

- Two runs yield identical analysis objects.
- Every cap is enforced with deterministic truncation.
- No forbidden field or authority import reaches a trade-network surface.

### Verification

- `uv run pytest tests/unit/test_trade_networks_determinism.py tests/unit/test_trade_networks_bounds.py tests/unit/test_trade_networks_leakage.py -q`
- `uv run pytest tests/integration/test_trade_networks_store_api.py -q`
- Expected result: all tests pass.

## Phase Risks and Mitigations

- Risk: real exchange orchestration is sensitive to tick ordering.
  Mitigation: follow the travel E2E's ordered `ActionSubmission` pattern and
  assert intermediate events.
- Risk: a cap test could allocate enormous payloads.
  Mitigation: use repeated bounded rows and a small policy override for tests.
- Risk: benchmark infrastructure needs PostgreSQL.
  Mitigation: keep the new integration DB-free; record the pinned benchmark
  regression separately in Task 22.

## Phase Completion Checklist

- Every Task 16-18 acceptance criterion is satisfied.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
