# Phase 6: Experiment and End-to-End

Plan: [index.md](index.md)
Tasks: 19-21
Depends on: Phase 5 / Tasks 17-18, plus Phase 3 / Task 11

## Objective

Register the off-gate `emergent_prices@1` experiment, prove the full path with a
real in-process `WorldEngine` run (commands → events → owner ledgers → analysis →
snapshot → API), and lock determinism, cap bounds, and leakage guards.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/experiments/catalog.py` | `_definition` 189-210, `OFF_GATE_MATRIX_EXPERIMENT_IDS` 2800-2835, `experiment_market_institutions` 5671-5687 | Registration pattern |
| `src/experiments/market_institution_scenario.py` | 28-111 | Scenario/flag/exchange pattern |
| `src/experiments/collectors.py` | 340-377 | Completed-run analysis injection |
| `src/experiments/market_institutions_publication.py` | 344-411 | Programmatic publication |
| `src/api/routes/market_institutions.py` | 223-458 | Real API read in E2E |
| `tests/unit/test_market_institutions_end_to_end.py` | existing E2E | Real engine/commands/events/snapshot/`httpx.ASGITransport` API pattern |
| `tests/unit/test_market_institutions_determinism.py` | existing determinism | Hash-seed and cap property pattern |
| `tests/unit/test_market_institutions_leakage.py` | existing leakage | Forbidden-key/AST guard pattern |
| `src/simulation/runner_models.py` | `RUNNER_SCHEMA_VERSION_V56` 152, `SubjectiveValuationSpec` 5213-5265, `ResourceExchangeProfileSpec` 5296-5352 | Scenario config seam |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/experiments/emergent_prices_scenario.py` | create | `emergent_prices@1` scenario and arms |
| `src/experiments/catalog.py` | modify | Register off-gate experiment |
| `src/experiments/__init__.py` | modify | Export the scenario factory |
| `tests/unit/test_emergent_prices_experiment.py` | create | Registration/arms/off-gate tests |
| `tests/unit/test_emergent_prices_end_to_end.py` | create | Real in-process E2E |
| `tests/unit/test_emergent_prices_determinism.py` | create | Hash-seed determinism/caps |
| `tests/unit/test_emergent_prices_leakage.py` | extend | Forbidden fields/AST/log guards |

## Task 19: Register off-gate `emergent_prices@1`

### Intent

Provide a reproducible experiment that composes only already-owned seams:
`markets_credit`, `subjective_valuation`, and `resource_exchange_profile`.

### Implementation Steps

1. Create `src/experiments/emergent_prices_scenario.py` with
   `EMERGENT_PRICES_EXPERIMENT_ID: Final[str] = "emergent_prices@1"`.
2. Build a runner config on `RUNNER_SCHEMA_VERSION_V56` with
   `v4_capability_flags.markets_credit=True`,
   `subjective_valuation=SubjectiveValuationSpec(policy_id=
   SUBJECTIVE_VALUATION_POLICY_ID, horizon_ticks=8, max_bundle=8)`, and
   `resource_exchange_profile=ResourceExchangeProfileSpec(
   policy_id=RESOURCE_EXCHANGE_PROFILE_POLICY_ID, acceptance_window_ticks=32)`.
3. Define four arms with distinct ids:
   - `ep-flag-off`: no `markets_credit`, no valuation, no exchange profile;
   - `ep-valuation-only`: valuation + exchange profile, no `markets_credit`;
   - `ep-prices-on`: all three active;
   - `ep-prices-quotes`: all three plus `CommunicationStrategyMode.
     DETERMINISTIC`; the scenario must select at least one `Talk`/`Tell` so the
     optional `prc_v1` relation is exercised. No new command is introduced.
4. Use a deterministic roster and location layout reused from the market
   institution scenario where possible; do not import private world state.
5. Add `experiment_emergent_prices(base, *, seed_matrix=None, max_ticks=96)` to
   `catalog.py`, import lazily, and emit
   `INFO experiment_registered experiment_id=emergent_prices@1`.
6. Add `"emergent_prices@1"` to `OFF_GATE_MATRIX_EXPERIMENT_IDS`; never add it to
   `EXPERIMENT_A_V1_CONDITION_IDS`.
7. Re-export the scenario factory from `experiments/__init__.py`.

### Required Interfaces and Contracts

- Every arm differs only by declared seams; no hidden modes.
- Flag-off arm produces byte-identical legacy trajectories.
- The experiment is off the V1 A–E gate.
- No new command, event, observer semantic, write pair, runner schema, or
  migration.

### Requirement Evidence

- Registration pattern: `catalog.py:2800-2835,5671-5706`.
- V3 seams: `runner_models.py:5198-5265,5273-5352`.
- Off-gate discipline: `.ai-factory/ARCHITECTURE.md` requirement 3.

### Error Handling and Logging

- `INFO experiment_registered experiment_id=emergent_prices@1`; scenario
  validation errors use existing experiment error types.
- Never log arm configs containing item kinds or seed material.

### Tests

- `tests/unit/test_emergent_prices_experiment.py`: id present exactly once;
  off-gate; four arms; flag-off config equals baseline; no v57; no new command.

### Acceptance Criteria

- The experiment runs through `SimulationRunner` with the declared seams.
- The V1 gate set is unchanged.

### Verification

- `uv run pytest tests/unit/test_emergent_prices_experiment.py -q`
- Expected: all pass.

## Task 20: Add in-process price end-to-end coverage

### Intent

Prove the feature with real admission, real commands, real events, a real
snapshot, and a real API read, not only unit fixtures.

### Implementation Steps

1. Build a small deterministic world with two locations and three agents; give
   each agent portable item kinds and enough carry capacity.
2. Drive `WorldEngine`/`SimulationRunner` through at least three 32-tick windows:
   - tick set A: agent 1 offers kind `tool` for kind `grain`; agent 2 accepts;
   - tick set B: a second completed exchange at the same location with different
     counts so the ratio changes;
   - tick set C: a third exchange at a second location/venue, creating a second
     `mkt-ven-` and, through shared participants, a `mktc-` market membership.
3. Enable `markets_credit` + `subjective_valuation` +
   `resource_exchange_profile`; assert each owner's ledger has expectation rows
   with `unit_source` evidence and confidence in `[0, 1000]`.
4. Build the completed-run analysis and assert:
   - venue distributions contain sample counts, quantiles, `sample_source`, and
     five bin shares summing to 1000;
   - market distributions exist and keep completed/quoted sources separate;
   - at least one relation row is `converged` or `partially_converged` when the
     same ratio sample is repeated, and `divergent` when deliberately far apart;
   - no field named `price` exists.
5. Compose and publish a snapshot to a `tmp_path` store, then read it through
   the real filesystem reader.
6. Mount the FastAPI app with both settings pointing at the store and use
   `httpx.ASGITransport` exactly like
   `tests/unit/test_market_institutions_end_to_end.py:176`; call all seven routes
   with a `SUBJECTIVE_DEBUG` credential and assert 200 and page shapes.
7. Assert the source of truth is the real event stream: replaying the same seed
   yields the same snapshot digest.

### Required Interfaces and Contracts

- The E2E uses real `NegotiateExchange` admission; no test-only command is
  invented.
- The snapshot digest in the API response equals the published digest.
- Every route returns only published rows; no live analysis is computed in the
  API.

### Requirement Evidence

- Real-artifact E2E requirement: `aif-plan` reconciliation gate and
  `.ai-factory/ARCHITECTURE.md` requirements 2-4.
- Existing E2E pattern: `tests/unit/test_market_institutions_end_to_end.py`
  (lines 126-180, including `httpx.ASGITransport`).

### Error Handling and Logging

- Test logs are metadata-only; no owner, kind, unit, or ratio assertions in log
  text.
- Any route failure must surface the closed error code.

### Tests

- `tests/unit/test_emergent_prices_end_to_end.py` as above.
- `tests/integration/test_emergent_prices_store_api.py` repeats publish/read with
  the DB-free store; marked `integration`.

### Acceptance Criteria

- One test proves the whole chain end to end.
- Replay determinism holds for the same seed and config.

### Verification

- `uv run pytest tests/unit/test_emergent_prices_end_to_end.py -q`
- `uv run pytest tests/integration/test_emergent_prices_store_api.py -q -m integration`
- Expected: all pass.

## Task 21: Add determinism, property bounds, and leakage coverage

### Intent

Guarantee that no ordering, hash seed, cap edge, or accidental payload field can
change or leak the result.

### Implementation Steps

1. Determinism: run the harvest and snapshot twice in subprocesses with
   `PYTHONHASHSEED=0` and `PYTHONHASHSEED=12345`; assert identical canonical
   bytes and digest. Repeat with shuffled event/input order.
2. Cap properties with Hypothesis: generated counts around every cap
   (`max_exchange_events`, `max_quote_events`, `max_expectation_rows`,
   `max_distribution_rows`, `max_relation_rows`, `max_owner_quote_rows`) always
   produce sorted deterministic prefixes, `coverage="partial"`, and exactly one
   truncation notice per family.
3. Distribution properties: quantiles are non-decreasing; `sample_count` matches
   paired inputs; bin shares sum to 1000; overlap in `[0, 1000]`.
4. Leakage guards:
   - recursively inspect analysis/snapshot dataclasses for forbidden field names
     and for `AgentId`, `EntityId`, `WorldEvent`, `ValuationRow`,
     `SubjectiveValuationLedger`, and `MarketInstitutionLedger` types;
   - AST-scan `src/analysis/emergent_prices_*.py` for imports of `agents`,
     `persistence`, `observer`, `api`, `experiments`;
   - assert no `prc_v1` frame body, item kind, unit token, ratio, owner token, or
     cursor appears in captured logs at DEBUG.
5. Add a guard that no source or test file contains `runner-config-v57`, a
   `canonical_price` field, or a Godot overlay hook for this feature.
6. Add a guard that the seven routes never import analysis or experiments.

### Required Interfaces and Contracts

- Determinism is byte-level, not semantic-only.
- Property tests use bounded strategies so the default suite stays fast.
- Leakage tests fail on a field name or type, not only on values.

### Requirement Evidence

- Reproducibility axiom: `RULES.md` axioms 4 and 9.
- Logging safety: `RULES.md` Coding Standards; plan logging policy.
- Existing determinism/leakage patterns: `tests/unit/test_market_institutions_*`.

### Error Handling and Logging

- Tests must not suppress failures; no skip/xfail for missing scale hardware
  (these are unit properties).

### Tests

- `tests/unit/test_emergent_prices_determinism.py`
- `tests/unit/test_emergent_prices_bounds.py`
- `tests/unit/test_emergent_prices_leakage.py` (extended)

### Acceptance Criteria

- Identical inputs always produce identical bytes across hash seeds and ordering.
- Every cap boundary is safe and reported.
- No private or payload-bearing field reaches analysis, snapshot, API, or logs.

### Verification

- `uv run pytest tests/unit/test_emergent_prices_determinism.py tests/unit/test_emergent_prices_bounds.py tests/unit/test_emergent_prices_leakage.py -q`
- Expected: all pass.

## Phase Risks and Mitigations

- Risk: E2E becomes brittle because exchange admission depends on inventory.
  Mitigation: reuse the canonical exchange fixture and assert admission success
  before analysis.
- Risk: subprocess determinism tests are slow.
  Mitigation: two seeds and small fixtures only.
- Risk: leakage scan produces false positives on prose.
  Mitigation: scan dataclass field names and AST imports, not free text.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
