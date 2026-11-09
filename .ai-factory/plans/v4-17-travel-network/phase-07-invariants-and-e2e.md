# Phase 7: Invariants, End-to-End, and Experiment

Plan: [index.md](index.md)
Tasks: 21-23
Depends on: Phase 1 through Phase 6

## Objective

Lock every V4-17 pin with executable invariants, prove the whole route network
in process (construction, condition transition, movement, beliefs, checkpoint,
replay, publication), and register an off-gate `travel_network@1` experiment.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `tests/architecture/test_v4_architecture_invariants.py` | pins 122-148; contexts/flags 159-188; ownership 191-217; reservations 220-224; docs 317-334 | Primary architecture gate; hardcodes 14/12, 73 semantics, event 23, codec v21, no v57. |
| `tests/architecture/test_v3_baseline_inventory.py` | baseline 53-69; pins 77-93 | Hardcodes latest event/codec, metrics 188, observer 73, Alembic 0017. |
| `tests/architecture/test_infrastructure_boundaries.py` | 64-85 | Owned-set equality, event/codec pins, 73 semantics, 43 commands. |
| `tests/unit/test_observer_contracts.py` | 50-53 | Every alias target must exist; hardcodes 73. |
| `tests/unit/test_metric_specifications.py` | catalog count | Hardcodes 188; update to 192. |
| `tests/unit/test_infrastructure_end_to_end.py` | 256-271 | Existing construction -> travel-effect E2E pattern. |
| `src/experiments/catalog.py` | infrastructure experiment 2829/5609-5624 | Off-gate experiment registration pattern. |
| `src/experiments/infrastructure_networks_scenario.py` | id 49; control/treatment 65-126 | Scenario pattern for a flag-off/flag-on treatment. |
| `src/simulation/replay.py` | `_versions_compatible` 1333-1351 | Replay readiness follows accepted sets and projector compatibility. |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `tests/architecture/test_travel_network_boundaries.py` | modify | Add pin assertions for the deepening pair, 192 metrics, seven routes. |
| `tests/architecture/test_v4_architecture_invariants.py` | modify | Keep 14/12/6; assert no v57 and the travel pair metadata. |
| `tests/architecture/test_v3_baseline_inventory.py` | modify | Latest event 27, accepted codec v25, metrics 192, observer 73, 43 commands. |
| `tests/unit/test_observer_contracts.py` | modify | Route alias and 73 count. |
| `tests/unit/test_metric_specifications.py` | modify | Catalog 192 and four new ids. |
| `tests/unit/test_infrastructure_replay.py` | modify | Travel selection priority above infrastructure. |
| `tests/unit/test_formal_rule_regression.py` | modify | Reservation count stays four; deepening pair is separate. |
| `tests/architecture/test_organization_boundaries.py` | modify | Reservation count stays four and organizations ownership is unchanged. |
| `tests/unit/test_compatibility_matrix.py` | modify | Event/codec matrix text and accepted sets. |
| `tests/unit/test_infrastructure_docs.py` | modify | Catalog, route count, and pin sweep. |
| `tests/unit/test_domain_contract_evolution_policy.py` | modify | Observation freeze fields include the new exit route facts. |
| `tests/unit/test_infrastructure_metrics.py` | modify | Catalog 188 -> 192. |
| `tests/unit/test_travel_network_end_to_end.py` | create | Full in-process proof. |
| `src/experiments/catalog.py` | modify | Register off-gate `travel_network@1`. |
| `src/experiments/travel_network_scenario.py` | create | Control/treatment scenario. |
| `tests/unit/test_travel_network_experiment.py` | create | Catalog/scenario/gate tests. |

## Task 21: Enforce architecture invariants and pin sweeps

### Intent

Make every count and ownership claim mechanically enforced so later plans
cannot silently reallocate reservations, add a flag, widen v56, or drift the
catalog.

### Implementation Steps

1. Update `tests/architecture/test_v4_architecture_invariants.py`:
   - contexts 14, flags 12, owned six (`organizations`, `formal_rules`,
     `legal_disputes`, `diplomacy`, `organized_conflict`,
     `infrastructure_networks`);
   - `V4_CONTEXT_MAP_VERSION` unchanged (`v4-context-map-v2`);
   - no `runner-config-v57` accepted;
   - reserved pairs `[23,24,25,26]` / `["v21","v22","v23","v24"]`;
   - deepening pair `[27]` / `["v25"]`;
   - observer semantics 73;
   - commands 43;
   - Alembic 0017.
2. Update `tests/architecture/test_v3_baseline_inventory.py`:
   - latest accepted event schema is 27; infrastructure-only runs still select
     23 and regions-only runs still select 21;
   - `latest_codec="v25"`; `next_codec` advances past v25 (v26); accepted
     includes v21/v19 and earlier;
   - metric families 192; observer 73; commands 43; Alembic 0017.
3. Update `tests/architecture/test_infrastructure_boundaries.py` and
   `tests/architecture/test_travel_network_boundaries.py`:
   - owned frozensets equal;
   - no new V4 flag;
   - travel module import boundaries, including the private
     `world._travel_network` allowlist;
   - no cognition -> objective route imports.
4. Update `tests/unit/test_observer_contracts.py`:
   - `route_condition_changed` aliases `WEATHER_CHANGED`;
   - all alias targets exist;
   - exactly 73 semantic types.
5. Update `tests/unit/test_metric_specifications.py` and
   `tests/unit/test_infrastructure_metrics.py` to 192; keep prior 188
   ids/order/versions/value keys unchanged. Replace any negative catalog slice
   used by historical tests with an absolute index so future appends cannot
   shift it.
6. Update `tests/unit/test_infrastructure_replay.py`,
   `tests/unit/test_regional_travel_checkpoint.py`,
   `tests/unit/test_formal_rule_regression.py`, and
   `tests/architecture/test_organization_boundaries.py`:
   - travel -> `(27,"v25")`, infrastructure -> `(23,"v21")`, regions ->
     `(21,"v19")`;
   - reservation count stays four; deepening pair is separate.
7. Update `tests/unit/test_compatibility_matrix.py`,
   `tests/unit/test_infrastructure_docs.py`, and
   `tests/unit/test_domain_contract_evolution_policy.py` for the new matrix
   rows, route/snapshot pins, and observation freeze fields.
8. Add a pin sweep test that reads `docs/v4-architecture.md` only if the docs
   phase has landed; otherwise keep doc pins in the docs task to avoid ordering
   coupling.

### Required Interfaces and Contracts

- No new V4 context/flag; six owned / six unowned.
- Default runner/result stays v4/v2; latest feature runner v55; v56 accepted.
- Commands 43; observer 73; metrics 192; Alembic 0017.
- Reserved pairs unchanged; deepening pair appended.

### Requirement Evidence

- `tests/architecture/test_v4_architecture_invariants.py` 122-224; `tests/architecture/test_v3_baseline_inventory.py` 53-93; `tests/unit/test_formal_rule_regression.py` 51-52; `tests/architecture/test_organization_boundaries.py` 259-260; index pins row.

### Error Handling and Logging

- Architecture failures report the exact pin name and observed value.
- No payload dumps.

### Tests

- `uv run pytest tests/architecture -q`
- `uv run pytest tests/unit/test_observer_contracts.py tests/unit/test_metric_specifications.py tests/unit/test_infrastructure_metrics.py tests/unit/test_infrastructure_replay.py tests/unit/test_regional_travel_checkpoint.py tests/unit/test_formal_rule_regression.py tests/unit/test_compatibility_matrix.py tests/unit/test_infrastructure_docs.py tests/unit/test_domain_contract_evolution_policy.py -q`

### Acceptance Criteria

- Every pin is enforced and green.
- No accidental flag/context/schema drift.

### Verification

- `uv run pytest tests/architecture -q`
- Expected: all pass.

## Task 22: Add in-process travel-network end-to-end coverage

### Intent

Prove one complete run from route topology through construction, seasonal
blockage, movement rejection/acceptance, subjective belief, checkpoint, replay,
and detached publication.

### Implementation Steps

1. Create `tests/unit/test_travel_network_end_to_end.py` with a deterministic
   fixture:
   - three adjacent locations in two regions with `RouteSpec` duration/fatigue;
   - `EnvironmentalDynamicsSpec` with a short season length;
   - `infrastructure_networks` + `collective_projects` + `multi_polity_migration`
     + `regions_migration`;
   - a road/bridge collective project or direct completion helper.
2. Exercise through a real `WorldEngine` and real `ActionSubmission` admission,
   not synthetic `SimpleNamespace` state or direct helper calls:
   1. initial open/restricted condition and observations;
   2. admit a real `Move` and assert condition duration/fatigue in the
      committed `JourneyStarted`/`Moved` events;
   3. build/complete a road through the real collective-project pipeline and
      verify quality/capacity/duration relief;
   4. advance to winter and verify closure without relief or restriction with
      relief;
   5. drive real weather to storm and verify closure;
   6. admit a real move on the closed route and assert `ROUTE_CLOSED`;
   7. admit a real `Transport` whose 2 participants exceed capacity and assert
      `ROUTE_CAPACITY_EXCEEDED`;
   8. destroy/damage the road and verify quality/capacity loss;
   9. checkpoint at `(27,"v25")`, restore, and compare observations/state;
   10. replay the committed event stream and compare route conditions;
   11. publish the infrastructure snapshot v2 and read the summary and routes
        pages through the real API/local reader.
3. Assert the committed event stream contains real `RouteConditionChanged`
   events and that no `infra-`/route payload bodies appear in logs; use `caplog`
   with metadata-only expectations.
4. Assert the run remains deterministic across two identical seeds.
5. Keep the runtime bounded: no network, no Docker, no PostgreSQL.

### Required Interfaces and Contracts

- The E2E uses real `WorldEngine` admission and real public runner/API-local
  helpers; no synthetic state objects and no private state imports outside
  allowed test helpers.
- Checkpoint/replay equality includes route rows and observation exits.
- Publication is opt-in and uses the existing dual gate.

### Requirement Evidence

- index supported-combination matrix and definition of done; `tests/unit/test_infrastructure_end_to_end.py` pattern.

### Error Handling and Logging

- Fail closed on any missing prerequisite; do not skip silently.
- `INFO` milestones only; no route/owner bodies.

### Tests

- `uv run pytest tests/unit/test_travel_network_end_to_end.py -q`
- Expected: all pass.

### Acceptance Criteria

- One run proves construction, condition transition, movement, belief,
  checkpoint, replay, and publication.
- Deterministic repeat yields identical results.

### Verification

- `uv run pytest tests/unit/test_travel_network_end_to_end.py -q`
- Expected: all pass.

## Task 23: Register off-gate `travel_network@1` experiment

### Intent

Provide a trusted, reproducible comparison without adding it to the V1 gate or
claiming that travel networks cause civilization outcomes.

### Implementation Steps

1. In `src/experiments/catalog.py`, add off-gate
   `travel_network@1` following the `infrastructure_networks@1` pattern:
   - stable experiment id;
   - `v1_gate=False`;
   - description: objective route condition with subjective route beliefs;
   - composition of `infrastructure_networks`, `collective_projects`,
     `multi_polity_migration`, and `regions_migration`.
2. Create `src/experiments/travel_network_scenario.py`:
   - deterministic fixed seed/world;
   - control: regions + infrastructure but no seasonal/weather route changes
     (or a short horizon before the first season transition);
   - treatment: same run with a season transition and a road/bridge;
   - no scripted outcomes, no forced agent choices.
3. Ensure the experiment is not in the V1 A-E gate or any default matrix.
4. Add `tests/unit/test_travel_network_experiment.py`:
   - registration, off-gate status, deterministic build;
   - control/treatment differ only in declared factors;
   - no new command/event family beyond V27.
5. Do not add a report task or a summary artifact.

### Required Interfaces and Contracts

- Experiment id `travel_network@1`.
- Off the V1 gate; explicit opt-in only.
- No capability flag, context, command, or migration.
- Control/treatment share seed, stochastic identity, world layout, founder
  roster, and stop horizon.

### Requirement Evidence

- `src/experiments/catalog.py` infrastructure precedent; index experiment row.

### Error Handling and Logging

- Missing prerequisites fail closed with a stable code.
- `INFO travel_network_experiment_registered off_gate=true`.

### Tests

- `uv run pytest tests/unit/test_travel_network_experiment.py tests/unit/test_experiment_catalog.py -q`

### Acceptance Criteria

- Experiment is registered off-gate and reproducible.
- No default gate includes it.

### Verification

- `uv run pytest tests/unit/test_travel_network_experiment.py tests/unit/test_experiment_catalog.py -q`
- Expected: all pass.

## Phase Risks and Mitigations

- Risk: pin sweep misses a hard-coded 188/73/23.
  Mitigation: run the complete architecture and metric suites, then grep for
  stale literals in tests.
- Risk: E2E becomes an integration test requiring Docker.
  Mitigation: keep it unit-scoped with in-memory state and local temporary
  directories only.
- Risk: experiment claims causality.
  Mitigation: off-gate, descriptive, no causal claim.

## Phase Completion Checklist

- Every task above satisfies its acceptance criteria.
- `index.md` checkboxes for Tasks 21-23 are updated after verification.
- No phase file contains task checkboxes.
