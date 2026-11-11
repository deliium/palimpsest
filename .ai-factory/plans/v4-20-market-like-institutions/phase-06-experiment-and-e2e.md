# Phase 6: Experiment and End-to-End

Plan: [index.md](index.md)
Tasks: 19-21
Depends on: Phase 4 / Task 16, Phase 5 / Task 17

## Objective

Register an off-gate `market_institutions@1` experiment with control and
treatment arms, prove the whole path with a real `WorldEngine` run, and lock
determinism, cap bounds, and leakage with focused property tests.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/experiments/trade_network_scenario.py` | id (31), exchange specs (34-46), scenario (49-87) | Scenario composition pattern |
| `src/experiments/catalog.py` | V1 gate (244-246), off-gate set (2795-2834), builder (5652-5667) | Registration mechanics |
| `src/experiments/civilization_benchmark_exchange.py` | `build_exchange_benchmark` (221-251), venue setup (142-196), arbiter (472-493) | Real co-located holders/items and ordinary-command scheduling |
| `src/simulation/runner.py` | `set_intervention_arbiter` (3354-3360), admission/commit cycle | Public test hook for trusted milestone overrides |
| `src/simulation/compatibility.py` | `RUNNER_SCHEMA_VERSION_V56`, accepted versions | Treatment must write v56 only |
| `tests/unit/test_trade_networks_experiment.py` | off-gate and V1 exclusion (90-93,136-139) | Experiment pin pattern |
| `tests/unit/test_supply_chain_determinism.py` | subprocess hash-seed pattern | Determinism test pattern |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/experiments/market_institution_scenario.py` | create | Control/treatment scenario |
| `src/experiments/catalog.py` | modify | Register builder and off-gate id |
| `src/experiments/__init__.py` | modify | Export scenario |
| `tests/unit/test_market_institutions_experiment.py` | create | Experiment pins |
| `tests/unit/test_market_institutions_end_to_end.py` | create | Real-engine E2E |
| `tests/unit/test_market_institutions_determinism.py` | create | Hash-seed and cap properties |
| `tests/unit/test_market_institutions_leakage.py` | create | Authority and vocabulary leakage |

## Task 19: Register off-gate `market_institutions@1`

### Intent

Add a trusted, off-gate experiment that compares the owned market cognition
channel against an otherwise identical control, using existing exchange and
valuation seams. The scenario creates no price, money, market object, or
scheduled exchange.

### Implementation Steps

1. Create `src/experiments/market_institution_scenario.py` with
   `MARKET_INSTITUTIONS_EXPERIMENT_ID = "market_institutions@1"` and
   `market_institution_scenario(base, *, seed_matrix=None, max_ticks=96) ->
   ExperimentDefinition`:
   - require `base.regions_migration is not None`, otherwise raise
     `ValueError("market_institutions_requires_regions")`;
   - `_with_exchange(config)` sets `ResourceExchangeProfileSpec(
     policy_id="resource-exchange-profile-v1", acceptance_window_ticks=8)` and
     `SubjectiveValuationSpec(policy_id="subjective-valuation-v1",
     horizon_ticks=8, max_bundle=2)`;
   - `_with_flags(config, *, enabled)` returns a copy with
     `schema_version=RUNNER_SCHEMA_VERSION_V56` and
     `v4_capability_flags=replace(config.v4_capability_flags,
     markets_credit=enabled)`; every other flag is preserved;
   - two conditions: `market-institutions-control` (`enabled=False`) and
     `market-institutions-treatment` (`enabled=True`), with label codes
     `market_institutions_control` / `market_institutions_treatment`;
   - both arms share seed matrix, world scenario, exchange/valuation specs, and
     `max_ticks`;
   - log `experiment_registered experiment_id=market_institutions@1 arms=2
     off_gate=true`.
2. In `src/experiments/catalog.py`:
   - add `"market_institutions@1"` to `OFF_GATE_MATRIX_EXPERIMENT_IDS`;
   - add `experiment_market_institutions(base, *, seed_matrix=None,
     max_ticks=96)` delegating to the scenario and logging registration;
   - do not add the id to `EXPERIMENT_A_V1_CONDITION_IDS` or any V1 gate set.
3. Export the scenario and builder through `src/experiments/__init__.py`.

### Required Interfaces and Contracts

- Control and treatment differ only in `markets_credit`; all other fields are
  equal after replacing the flag.
- Treatment writes `runner-config-v56`; the control also uses v56 so the pair is
  schema-identical. No v57 is emitted.
- The scenario installs no interval arbiter, no market object, no price, and no
  money.
- `max_ticks=96` gives three 32-tick windows; a caller may pass a larger value
  but not less than 96.

### Requirement Evidence

- Original Request: "Enable repeated trade gatherings and exchange venues to
  become socially expected institutions."
- `src/experiments/trade_network_scenario.py:31-87` — control/treatment over
  existing exchange seams.
- `src/simulation/v4_architecture.py:212-228` — `markets_credit` prerequisites
  are planning order, so the scenario does not require the flags to be on.

### Error Handling and Logging

- ERROR: `market_institutions_scenario_invalid reason_code=requires_regions`.
- INFO: `experiment_registered experiment_id=market_institutions@1 arms=2`.
- Never log seeds, item ids, or world contents.

### Tests

- `tests/unit/test_market_institutions_experiment.py`: id is off-gate; control
  and treatment share everything except the flag; treatment is v56; no v57; both
  arms carry exchange and valuation specs; V1 gate excludes the id; missing
  regions fails closed.

### Acceptance Criteria

- `market_institutions@1` is a member of `OFF_GATE_MATRIX_EXPERIMENT_IDS` and not
  a member of `EXPERIMENT_A_V1_CONDITION_IDS`.
- Exactly two arms exist with the documented condition ids.

### Verification

- `uv run pytest tests/unit/test_market_institutions_experiment.py -q`
- Expected result: all pass.

## Task 20: Add in-process market-institution end-to-end coverage

### Intent

Prove the feature with real admission, real commands, real committed events, a
real snapshot, and a real API read. The test must not inject events or build
analysis rows by hand.

### Implementation Steps

1. Create `tests/unit/test_market_institutions_end_to_end.py`:
   - build a config with `build_exchange_benchmark(V3_BENCH_14_SUBJECTIVE_BARTER)`
     and take `arms[0].config`; this fixture already co-locates two holders with
     known inventories;
   - read the two agents and their inventories from the config; build a
     `MilestoneInterventionArbiter` with three offer/accept pairs at ticks 0, 32,
     and 64 using the inventory item ids, so every offer/accept is an ordinary
     `NegotiateExchange` command;
   - set `schema_version=RUNNER_SCHEMA_VERSION_V56`,
     `v4_capability_flags=V4CapabilityFlags(markets_credit=True)`,
     `ResourceExchangeProfileSpec`, and `SubjectiveValuationSpec` on the config;
   - construct `SimulationRunner` through `from_config`, call
     `set_intervention_arbiter`, and run to tick 80;
   - assert at least three `ExchangeCompleted` events share one
     `occurrence.origin_location_id`;
   - call `build_completed_run_market_institutions_analysis` with the real
     committed events and `runner_result`;
   - assert the venue status is `market_like_persistent`, lineage has no
     `dissolved` gap, and `coverage` is not `missing`;
   - compose and finalize the snapshot, publish it to a temporary
     `market_institutions_root`, and build the API app with both settings;
   - use `fastapi.testclient.TestClient` with a valid debug credential to GET
     the summary and the venues page; assert 200, the summary counts, and the
     venue row.
2. Assert the analysis call receives only committed events and the runner-result
   ledger export; no `WorldState`, private module, or agent runtime is imported.
3. Clean up the temporary root with `tmp_path`.

### Required Interfaces and Contracts

- The E2E uses `markets_credit=True`, so `from_config` must accept the flag.
- The arbiter schedules ordinary commands; it never injects an event or mutates
  world state.
- The API read uses the same published snapshot bytes written by the store.
- The test is deterministic and does not depend on wall-clock time or network.

### Requirement Evidence

- `src/experiments/civilization_benchmark_exchange.py:221-251,472-493` — fixture
  and arbiter reuse.
- `src/simulation/runner.py:3354-3360` — public arbiter hook.
- Original Request: "agents repeatedly trade at location".

### Error Handling and Logging

- Test failures must identify the missing stage: no completion events, no
  gathering, wrong status, or non-200 read.
- No assertion prints full event bodies or inventories.

### Tests

- `tests/unit/test_market_institutions_end_to_end.py` as described.

### Acceptance Criteria

- The test passes with real engine admission and no synthetic event list.
- The published snapshot read through the API contains the same venue id that
  the analysis produced.

### Verification

- `uv run pytest tests/unit/test_market_institutions_end_to_end.py -q`
- Expected result: pass.

## Task 21: Add determinism, property bounds, and leakage coverage

### Intent

Prove that identity, ordering, caps, and layers are stable across processes and
that analysis never leaks objective or owner evidence across authorities.

### Implementation Steps

1. `tests/unit/test_market_institutions_determinism.py`:
   - subprocess test running a fixed synthetic event+owner-row fixture with
     `PYTHONHASHSEED=0` and `=1`, comparing the snapshot digest and analysis
     digest byte-for-byte;
   - Hypothesis properties: venue/gathering/expectation/role/record/market/
     lineage row counts never exceed policy caps; `window_index` is in
     `0..511`; `recurrence_milli` and `alignment_milli` are in `0..1000`;
     status/label tokens belong to the closed sets;
   - a property that adding an unrelated event kind does not change the digest.
2. `tests/unit/test_market_institutions_leakage.py`:
   - objective rows contain no `mktb-`, owner token, or record anchor;
   - owner rows contain no objective `event_token`;
   - analytical rows contain no raw observation body or memory text;
   - no dataclass field name in `src/agents/cognition/market_institutions*.py`,
     `src/analysis/market_institutions_*.py`, `src/simulation/market_institutions_*.py`,
     or `src/api/market_institutions_*.py` matches a forbidden commercial key;
   - `analysis` imports no API, persistence, experiments, cognition, or observer
     module;
   - `agents.cognition` market modules import no `WorldState`, `WorldEngine`,
     `ActionSubmission`, or event store;
   - no analysis identifier appears in the Research UI or Godot client except as
     a read-only field name.
3. Add a small integration case in
   `tests/integration/test_market_institutions_store_api.py` (Task 17) that
   reads a snapshot twice and asserts identical bytes and ids.

### Required Interfaces and Contracts

- Tests never weaken a production guard to pass; a leak is fixed in the source.
- Hypothesis deadlines are disabled only where subprocess startup requires it.
- Determinism compares canonical bytes and digests, not Python object equality.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "Key Principles" 1-5 and "Anti-Patterns".
- `tests/unit/test_supply_chain_determinism.py` and
  `tests/unit/test_supply_chain_leakage.py` — existing patterns.

### Error Handling and Logging

- No production logging is added by tests.
- Property failures print the offending minimal case only, never full rows.

### Tests

- `tests/unit/test_market_institutions_determinism.py`
- `tests/unit/test_market_institutions_leakage.py`

### Acceptance Criteria

- Both hash seeds produce identical snapshot digests.
- Every cap property holds for at least 50 generated examples.
- The leakage suite reports zero offenders.

### Verification

- `uv run pytest tests/unit/test_market_institutions_determinism.py tests/unit/test_market_institutions_leakage.py -q`
- Expected result: all pass.

## Phase Risks and Mitigations

- Risk: the E2E depends on private benchmark ids. Mitigation: read item ids from
  the built config inventories instead of importing module constants.
- Risk: the arbiter pair is ordered incorrectly and only one side commands.
  Mitigation: mirror the existing barter benchmark's same-tick offer/accept pair
  and assert at least three completions.
- Risk: property tests hide nondeterminism behind sorting. Mitigation: compare
  canonical bytes and run in separate hash-seeded subprocesses.

## Phase Completion Checklist

- Every Task 19-21 acceptance criterion is verified.
- The E2E uses real admission, real events, a real snapshot, and a real API read.
- Determinism, cap bounds, and leakage guards pass.
- `index.md` task checkboxes are updated immediately after verified completion.
