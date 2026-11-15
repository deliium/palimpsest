# Phase 5: Experiment and Certification Paths

Plan: [index.md](index.md)
Tasks: 15-17
Depends on: Phase 3 and Phase 4 (Tasks 9-14)

## Objective

Register an off-gate `economic_cascades@1` experiment with three arms, prove the
feature end to end in-process with real admission and a real API read, and lock
determinism, cap bounds, and leakage behavior. The V1 A–E gate and the default
runner write stay unchanged.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/experiments/social_mobility_scenario.py` | id/arms (50, 146-190), `max_ticks >= 96` | Newest three-arm scenario template |
| `src/experiments/economic_inequality_scenario.py` | v56 pin (49), arms (46-127) | Three-arm template |
| `src/experiments/catalog.py` | `experiment_social_mobility` (5756-5772), `experiment_economic_inequality` (5735-5753) | Registration pattern |
| `src/experiments/supply_chain_scenario.py` | v56/catalog wiring (85) | Supply-chain arm setup |
| `src/experiments/infrastructure_networks_scenario.py` | v56 setup (82) | Infrastructure arm setup |
| `tests/unit/test_social_mobility_end_to_end.py` | in-process path | E2E template |
| `tests/unit/test_social_mobility_determinism.py` | hash-seed determinism | Determinism template |
| `tests/architecture/test_social_mobility_boundaries.py` | import/authority boundaries | Boundary template |
| `tests/unit/test_v1_regression_gate.py` | V1 A–E gate | Proves the new experiment stays off it |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/experiments/economic_cascades_scenario.py` | create | Off-gate three-arm scenario |
| `src/experiments/catalog.py` | modify | Register `economic_cascades@1` |
| `src/experiments/__init__.py` | modify | Export the experiment |
| `tests/unit/test_economic_cascades_experiment.py` | create | Arms, pins, off-gate |
| `tests/unit/test_economic_cascades_end_to_end.py` | create | Real in-process path |
| `tests/unit/test_economic_cascades_determinism.py` | create | Hash-seed determinism |
| `tests/unit/test_economic_cascades_leakage.py` | create | No objective/owner leakage |
| `tests/architecture/test_economic_cascades_boundaries.py` | create | Import and authority boundaries |

## Task 15: Register off-gate `economic_cascades@1`

### Intent
Make the feature reproducible without touching the V1 gate. The baseline arm has
no `supply_chains` seam and must be provably inert.

### Implementation Steps
1. Create `src/experiments/economic_cascades_scenario.py`:
   - `ECONOMIC_CASCADES_EXPERIMENT_ID = "economic_cascades@1"`.
   - Three arms selected from existing scenario builders; never treat an
     `ExperimentDefinition` return value as a runner config and never rely on a
     builder's default `max_ticks` (24 or 48):
     - `baseline`: the `supply-chain-off` condition from
       `supply_chain_scenario(base, max_ticks=96)` — flag off, legacy catalog,
       provably inert.
     - `production`: the `supply-chain-on` condition from the same builder —
       flag on, chain catalog. That builder sets `mortality_mode=DISABLED`,
       which is correct for an arm that does not study population loss.
     - `full`: the `travel-network-treatment` condition from
       `travel_network_scenario(base_with_regions, max_ticks=96)` —
       infrastructure networks, multi-polity migration, and routes already
       composed. Then
       `replace(v4_capability_flags=replace(config.v4_capability_flags,
       supply_chains=True))` and install `supply_chain_production_catalog()` on
       every agent with the same `dataclasses.replace` shape as
       `src/experiments/supply_chain_scenario.py:_with_catalog`. Build
       `base_with_regions` as a two-location/one-route `RegionsMigrationSpec`
       with the shape used by
       `src/experiments/regional_migration_scenario.py:278`, and assert the
       resolved full-arm config has `mortality_mode` not `DISABLED` so
       population-loss evidence remains possible.
   - Reject `max_ticks < 96` with `economic_cascades_min_ticks`.
   - Never enable `science`, `epidemics`, `ecological_feedback`, or `disasters`.
   - No scripted downstream outcome: the scenario never injects a disruption,
     never schedules a command, and never asserts an expected chain.
2. Register `experiment_economic_cascades` in `src/experiments/catalog.py` with
   a lazy scenario import and `_LOG.info("experiment_registered", id=...)`,
   following the social-mobility entry.
3. Export the experiment from `src/experiments/__init__.py`.
4. Do not add the experiment to the V1 A–E gate, the benchmark suite, or the
   matrix defaults.

### Required Interfaces and Contracts
- Three arms exactly; ids are stable and lower-snake.
- `baseline` has no supply-chain evidence and therefore no cascade analysis.
- No arm claims a new capability flag; owned flags stay eight.
- No arm changes runner/result schema beyond the accepted V56 seam.

### Requirement Evidence
- Original Request "Do not script downstream outcomes".
- `.ai-factory/ARCHITECTURE.md` requirement 3 (feature experiments stay off the
  V1 gate) and V4-01 accepted V56 seam.
- `src/experiments/social_mobility_scenario.py:50,146-190`.

### Error Handling and Logging
- INFO `economic_cascades_experiment_registered arms=3`.
- ERROR `economic_cascades_min_ticks` with the limit only.
- Never log arm configuration payloads or catalogs.

### Tests
- `tests/unit/test_economic_cascades_experiment.py`: three arm ids, baseline has
  no flags, production/full flag sets, `max_ticks` rejection, catalog
  registration, absence from the V1 gate list, no unowned flag.

### Acceptance Criteria
- `economic_cascades@1` is registered and reproducible.
- Baseline is inert: its analysis is empty and no metric document emits.
- No V1-gate or default-write change exists.

### Verification
- `uv run pytest tests/unit/test_economic_cascades_experiment.py tests/unit/test_v1_regression_gate.py -q`
- Expected result: pass.

## Task 16: Add in-process end-to-end coverage

### Intent
Prove the whole seam with real admission, real commands, real committed events, a
real snapshot, a real store, and a real API read — not mocks.

### Implementation Steps
1. Create `tests/unit/test_economic_cascades_end_to_end.py`:
   - Build a deterministic V56 run with the supply-chain catalog, one resource
     node per chain root, a production actor, and enough ticks for two windows.
   - Drive ordinary commands only: harvest the node until
     `ResourceNodeDepleted`, craft tool stages, drop a tool to create a tool
     absence, and let an agent die through ordinary needs. Where a route closure
     or infrastructure destruction is needed, use the existing environmental
     and public-good paths; never call a private mutation.
   - Run the runner to completion, then call
     `build_completed_run_economic_cascades_analysis` with the committed events.
   - Compose the snapshot, publish through the filesystem store into a
     `tmp_path`, attach the reader through the app factory, and read all seven
     routes with `TestClient`.
   - Assert: at least one disruption kind, at least one `linked` or `unlinked`
     chain, canonical round-trip, paging across two windows, cumulative
     publication bytes below the quota, and a clean 200 on every route.
2. Add cases: dual gate unset → 503 on all seven; corrupt `state.json` → 500;
   cursor for another window → 400.
3. Use a real `runner-config-v56` config and the real collector path; do not
   bypass `assemble_arm_metric_bundle`.

### Required Interfaces and Contracts
- No mock of `WorldEngine`, the event history, the codec, or the store.
- Fixtures are deterministic and seed-derived.
- Assertions are on counts/states, never on narrative text.

### Requirement Evidence
- `.ai-factory/ARCHITECTURE.md` requirement 3 and the in-process E2E convention
  used by V4-24/V4-25.
- `tests/unit/test_social_mobility_end_to_end.py`.

### Error Handling and Logging
- Test-only logging is captured with `caplog`; assert WARN presence for corrupt
  store and partial coverage, and absence of tokens in logs.

### Tests
- `tests/unit/test_economic_cascades_end_to_end.py` as above.

### Acceptance Criteria
- The full path runs without mocks and produces seven readable responses.
- Dual-gate, corruption, and cross-window cursor failures behave as specified.

### Verification
- `uv run pytest tests/unit/test_economic_cascades_end_to_end.py -q`
- Expected result: pass.

## Task 17: Add determinism, property bounds, and leakage coverage

### Intent
Guarantee that hash seeds, input order, caps, and layer boundaries cannot change
results or leak owner/objective state.

### Implementation Steps
1. Create `tests/unit/test_economic_cascades_determinism.py`:
   - Run the harvest/detect/link/compose pipeline in two subprocesses with
     `PYTHONHASHSEED=0` and `PYTHONHASHSEED=1`; compare the digest and encoded
     snapshot bytes exactly.
   - Repeat with shuffled-but-tick-sorted input to prove order independence.
2. Create `tests/unit/test_economic_cascades_leakage.py`:
   - Assert no objective disruption or dependency row exposes a
     `chain_token`, `state`, `linked_chain_count`, or any forbidden key.
   - Assert no analytical row exposes an owner token, a body token, a location
     token, or a magnitude tied to a named agent.
   - Assert the snapshot and route responses contain none of the forbidden
     vocabulary from `CASCADE_FORBIDDEN_KEYS`.
3. Extend `tests/unit/test_economic_cascades_bounds.py` or add property cases
   for: chain count ≤ `max_chains`, depth ≤ `max_chain_depth`, lag ≤
   `max_propagation_lag_windows`, notices ≤ `max_notices`, and every share in
   `0..1000`.
4. Create `tests/architecture/test_economic_cascades_boundaries.py`:
   - `analysis.economic_cascades_*` imports no `simulation`, `experiments`,
     `persistence`, `api`, or `world._*`.
   - `simulation.economic_cascades_*` imports no `api`, `analysis`,
     `experiments`, `persistence`, or `infrastructure`.
   - `experiments.economic_cascades_*` imports no API or concrete persistence.
   - No module exposes a helper that returns or submits an `AgentCommand`.

### Required Interfaces and Contracts
- Determinism covers hash seed, input order, and repeated publication.
- Property tests are deterministic and bounded (Hypothesis `max_examples=50`).
- Boundary tests use the same AST/import-linter style as existing architecture
  tests.

### Requirement Evidence
- `.ai-factory/ARCHITECTURE.md` Key Principles 2 and 1, and dependency rules.
- `tests/architecture/test_social_mobility_boundaries.py`.

### Error Handling and Logging
- No production logging change; tests assert that logged fields exclude tokens
  and payload surrogates.

### Tests
- The four files above; each must run without network, Docker, or PostgreSQL.

### Acceptance Criteria
- Byte-identical output across hash seeds.
- Every cap and share bound holds under generated input.
- Boundary tests fail if any forbidden import or command helper is added.

### Verification
- `uv run pytest tests/unit/test_economic_cascades_determinism.py tests/unit/test_economic_cascades_leakage.py tests/unit/test_economic_cascades_bounds.py tests/architecture/test_economic_cascades_boundaries.py -q`
- Expected result: pass.

## Phase Risks and Mitigations
- Risk: the E2E becomes a scripted outcome test.
  Mitigation: only ordinary commands and environment paths; assertions are on
  counts/states, and the scenario never asserts a specific chain.
- Risk: determinism tests are flaky under Hypothesis.
  Mitigation: fixed seed and bounded examples; compare canonical bytes only.
- Risk: a boundary test passes because the module is empty.
  Mitigation: assert the expected public symbols exist before import checks.

## Phase Completion Checklist
- `economic_cascades@1` is registered with three arms and stays off the V1 gate.
- The in-process E2E exercises the real store and API.
- Determinism, bounds, leakage, and boundary tests pass.
- `index.md` Tasks 15-17 checkboxes are updated after verification.
