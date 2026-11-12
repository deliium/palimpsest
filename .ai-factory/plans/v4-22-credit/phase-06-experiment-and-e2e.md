# Phase 6: Experiment and End-to-End

Plan: [index.md](index.md)
Tasks: 17-19
Depends on: Phase 1 (activation/carry), Phase 3 (metrics/analysis), Phase 4 (publication)

## Objective

Register the off-gate `credit_relationships@1` experiment, prove the feature
end-to-end through real engine admission, a real snapshot, and a real API read,
and add determinism, cap-bound property, and leakage coverage. No experiment
enters the V1 A-E gate.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/experiments/emergent_prices_scenario.py` | 38-145 | Exact four-arm off-gate scenario pattern |
| `src/experiments/catalog.py` | off-gate set 2800-2835, registration 5691-5707 | Exact registration points |
| `src/experiments/__init__.py` | price exports 262-274, 496-836 | Exact façade exports |
| `tests/unit/test_emergent_prices_end_to_end.py` | 57-180+ | Exact real-engine/snapshot/API pattern |
| `tests/unit/test_emergent_prices_determinism.py` | 1-80 | Exact hash-seed and shuffled-order pattern |
| `tests/unit/test_emergent_prices_bounds.py` | 1-50+ | Exact Hypothesis cap-bound pattern |
| `tests/unit/test_emergent_prices_leakage.py` | forbidden payload/authority scans | Exact leakage pattern |
| `src/simulation/runner_models.py` | `StructuredCommitmentsSpec` 5133-5193, `SubjectiveValuationSpec` 5213-5268 | Exact experiment specs |
| `src/world/actions.py` | `Talk`, `Tell`, `Give` | Real speech and transfer commands for E2E |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/experiments/credit_relationship_scenario.py` | create | Four-arm `credit_relationships@1` definition |
| `src/experiments/catalog.py` | modify | Off-gate set entry and `experiment_credit_relationships` |
| `src/experiments/__init__.py` | modify | Public scenario id/function exports |
| `tests/unit/test_credit_relationships_experiment.py` | create | Arms, schemas, prerequisites, off-gate membership |
| `tests/unit/test_credit_relationships_end_to_end.py` | create | Real engine, commands, snapshot, store, API |
| `tests/integration/test_credit_relationships_store_api.py` | create | Real filesystem publish/read/idempotent republish |
| `tests/unit/test_credit_relationships_determinism.py` | create | Hash-seed and shuffled-order byte identity |
| `tests/unit/test_credit_relationships_bounds.py` | create | Hypothesis caps and partial coverage |
| `tests/unit/test_credit_relationships_leakage.py` | create | Forbidden field, payload, authority, and import scans |

## Task 17: Register off-gate credit_relationships@1

### Intent

Provide a reproducible composition that exercises promises, credit terms, and
price expectations without joining the V1 gate or changing any default.

### Implementation Steps

1. Create `src/experiments/credit_relationship_scenario.py`:
   - `CREDIT_RELATIONSHIPS_EXPERIMENT_ID = "credit_relationships@1"`;
   - import `StructuredCommitmentsSpec`, `STRUCTURED_COMMITMENTS_POLICY_ID`,
     `SubjectiveValuationSpec`, `SUBJECTIVE_VALUATION_POLICY_ID`,
     `RUNNER_SCHEMA_VERSION_V56`, `CommunicationStrategyMode`,
     `RunnerStopPolicy`, `SimulationRunnerConfig`;
   - `_commitments(config, enabled)` replaces
     `structured_commitments` with
     `StructuredCommitmentsSpec(policy_id=..., horizon_ticks=16,
     max_open_interpretations=8)` or `None`, and sets
     `subjective_valuation` only when enabled;
   - `_markets(config, enabled)` toggles `v4_capability_flags.markets_credit`;
   - `_dialogue(config)` sets every agent's
     `communication_strategy_mode=CommunicationStrategyMode.DETERMINISTIC`;
   - `credit_relationship_scenario(base, *, seed_matrix=None, max_ticks=96)`:
     require `max_ticks >= 96`; build four conditions:
     1. `cr-flag-off` (`credit_relationships_flag_off`): schema v56, markets off,
        commitments `None`, valuation `None`;
     2. `cr-promises-only` (`credit_relationships_promises_only`): schema v56,
        markets off, commitments on, valuation on;
     3. `cr-credit-on` (`credit_relationships_on`): schema v56, markets on,
        commitments on, valuation on;
     4. `cr-credit-dialogue` (`credit_relationships_dialogue`): same as 3 plus
        deterministic communication strategy.
   - all arms share `RunnerStopPolicy(max_ticks=max_ticks)`, the same seed
     matrix, and `paired_world_group="credit_relationships@1-world"`;
   - log `INFO experiment_registered experiment_id=credit_relationships@1
     arms=4 off_gate=true` and return an `ExperimentDefinition` with
     `EXPERIMENT_SCHEMA_VERSION`.
2. In `src/experiments/catalog.py`:
   - add `"credit_relationships@1"` to `OFF_GATE_MATRIX_EXPERIMENT_IDS`;
   - add `experiment_credit_relationships(base, *, seed_matrix=None,
     max_ticks=96)` importing the scenario and logging
     `experiment_registered experiment_id=credit_relationships@1 arms=%s`.
3. In `src/experiments/__init__.py`, export the id and scenario function.
4. Do not add the experiment to any V1 A-E gate, default runner selection, or
   matrix preset.
5. Verify the four arms differ only by declared seams; no hidden command,
   event, or schema difference exists.

### Required Interfaces and Contracts

```python
CREDIT_RELATIONSHIPS_EXPERIMENT_ID = "credit_relationships@1"

def credit_relationship_scenario(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 96,
) -> ExperimentDefinition: ...
```

- All arms are `runner-config-v56`; V3-17 and V3-18 specs are root fields, not
  new schemas.
- `markets_credit` off means credit mode is disabled even when commitments are
  present.
- No arm enables an unowned V4 flag.
- The experiment stays off the V1 gate.

### Requirement Evidence

- Price experiment composition:
  `src/experiments/emergent_prices_scenario.py:38-145`.
- Off-gate registration: `src/experiments/catalog.py:2800-2835, 5691-5707`.
- V3-17/V3-18 specs: `src/simulation/runner_models.py:5133-5268`.

### Error Handling and Logging

- `max_ticks < 96` raises
  `ValueError("credit_relationships_requires_three_windows")`.
- Invalid base config fails in the existing `SimulationRunner.from_config`
  path; the scenario adds no bypass.
- `INFO experiment_registered experiment_id=credit_relationships@1 arms=4
  off_gate=true`.

### Tests

- `tests/unit/test_credit_relationships_experiment.py`: four condition ids;
  each arm's schema/flags/specs; shared seed/world/stop; `max_ticks` guard;
  catalog membership; absent from V1 gate; no unowned flag.

### Acceptance Criteria

- The catalog exposes `credit_relationships@1` and leaves A-E unchanged.
- Each arm is a valid v56 config with only the declared differences.
- The scenario is deterministic for one seed matrix.

### Verification

- `uv run pytest tests/unit/test_credit_relationships_experiment.py -q`
- Expected: all pass.

## Task 18: Add in-process credit end-to-end coverage

### Intent

Prove the feature with real `WorldEngine` admission, real `Talk`/`Tell`/`Give`
commands, real committed events, a real analysis, a real snapshot, a real
filesystem store, and a real API read. No fake world, no direct state mutation.

### Implementation Steps

1. Create `tests/unit/test_credit_relationships_end_to_end.py` with two real
   paths:
   - **World path:** bootstrap two locations and four bodies with food/material
     items; construct `WorldEngine` with `SimulationRunConfig` and
     `non_lethal_physical_rules`; submit real `Talk`/`Tell` proposals and
     acceptance plus a real `Give` repayment through
     `ActionSubmission`/`resolve_tick`; assert the resulting `Talked`/`Told`/
     `Given` events are committed; parse the committed relations with
     `world.credit_relationships.parse_credit_claim_relation`; construct the
     owner ledger through the public
     `apply_credit_relationship_update` API from those committed claims and the
     real `StructuredCommitmentLedger`; build a `SimpleNamespace` runner result
     carrying `credit_relationship_ledgers=(ledger,)`; run through
     `build_credit_relationships_harvest_result` with a real publisher; assert
     at least one relationship, claim, performance, and distribution or
     `insufficient_samples`; compose a FastAPI app with the real reader/codec
     and `SUBJECTIVE_DEBUG` credentials; call all seven routes and assert 200
     plus a row/count.
   - **Runner path:** build a real `runner-config-v56` config with
     `markets_credit=True`, `StructuredCommitmentsSpec`, and
     `SubjectiveValuationSpec` using `base_runner_config_from_scenario`; run
     `SimulationRunner.from_config`; assert the result exports an ordered
     `credit_relationship_ledgers` tuple and that the mode is deterministic.
     This path proves activation/carry/export without forcing a scripted speech
     outcome.
2. Create `tests/integration/test_credit_relationships_store_api.py` marked
   `integration`:
   - publish a real snapshot to `tmp_path`;
   - read it back through the reader and API;
   - republish the identical snapshot and assert idempotence;
   - corrupt `state.json` and assert the API returns 500
     `credit_relationships_store_corrupt`.
3. Do not mock `WorldEngine`, admission, event commit, the snapshot codec, or
   the filesystem store.
4. Assert no command class changed and no event count increased relative to the
   same scenario without credit.

### Required Interfaces and Contracts

- Test uses real `ActionSubmission`/`resolve_tick` and real `AgentCommand`
  values.
- Test uses the public publication and read ports, not private functions.
- The API app is composed exactly like `api.app.create_app` or a minimal app
  with the same dependencies and error handler.

### Requirement Evidence

- Real-engine E2E precedent:
  `tests/unit/test_emergent_prices_end_to_end.py:57-180+`.
- Real `SimulationRunner` activation/export precedent:
  `tests/unit/test_formal_rule_end_to_end.py:364-407`.
- Real store/API integration precedent:
  `tests/integration/test_emergent_prices_store_api.py`.
- No command/event additions: `.ai-factory/ARCHITECTURE.md` "Requirements for
  later changes" 2.

### Error Handling and Logging

- Test failures print only safe counts/statuses; never owner tokens, anchors,
  item kinds, or ratios.
- No production logging changes.

### Tests

- `tests/unit/test_credit_relationships_end_to_end.py`
- `tests/integration/test_credit_relationships_store_api.py`

### Acceptance Criteria

- The E2E produces a real publication and seven successful API reads.
- Re-running the same scenario yields the same snapshot bytes for one seed.
- The integration test proves atomic publish, idempotent republish, and
  corruption failure.

### Verification

- `uv run pytest tests/unit/test_credit_relationships_end_to_end.py -q`
- `uv run pytest tests/integration/test_credit_relationships_store_api.py -q -m integration`
- Expected: all pass.

## Task 19: Add determinism, property bounds, and leakage coverage

### Intent

Prove byte-level determinism across hash seeds and event order, cap-bound
partial coverage, and the absence of payload/authority leakage.

### Implementation Steps

1. Create `tests/unit/test_credit_relationships_determinism.py`:
   - harvest the same events twice and assert analysis digest and snapshot bytes
     are identical;
   - shuffle event order deterministically and assert identical digest/bytes;
   - run a subprocess with `PYTHONHASHSEED` in `{"0","12345"}` and compare the
     digest to the in-process value.
2. Create `tests/unit/test_credit_relationships_bounds.py`:
   - Hypothesis generates claim counts, transfer counts, and owner row counts;
   - assert each cap is a deterministic prefix, retained rows are sorted, and
     `coverage=partial` plus one notice appears when capped;
   - assert distribution bins sum to 1000 and quantiles are ordered;
   - assert `insufficient_samples` below four and `available` at four.
3. Create `tests/unit/test_credit_relationships_leakage.py`:
   - AST/field scan of every credit module for forbidden names
     (`bank`, `loan`, `interest`, `credit_score`, `money`, `currency`,
     `enforceable_debt`, `canonical_credit`); allow only the single declared
     `CREDIT_FORBIDDEN_FIELD_NAMES`/`CREDIT_ANALYSIS_FORBIDDEN_KEYS` constants
     and their string members;
   - assert no credit module imports `simulation`, `analysis`, `experiments`,
     `persistence`, `api`, or `observer` outside the declared direction;
   - assert no analysis row carries `WorldState`, `AgentCommand`, item ids,
     raw event bodies, peer ledgers, memories, or embeddings;
   - assert owner export contains no counterparty ids or raw anchors;
   - assert no `crd_v1` frame appears in a non-`Talk`/`Tell` command.
4. Add a regression assertion that credit-disabled runs produce the same event
   count and command names as the same scenario before V4-22.

### Required Interfaces and Contracts

- Determinism is byte-level, not just equality of counts.
- Cap truncation is always a stable prefix with one notice per family.
- Leakage guard fails closed on a forbidden field or import.

### Requirement Evidence

- Determinism and bounds patterns:
  `tests/unit/test_emergent_prices_determinism.py`,
  `tests/unit/test_emergent_prices_bounds.py`,
  `tests/unit/test_emergent_prices_leakage.py`.
- Logging and payload prohibitions: `.ai-factory/RULES.md` coding standards;
  `.ai-factory/ARCHITECTURE.md` "Key Principles" 5.

### Error Handling and Logging

- Tests do not add production logs.
- On failure, assertion messages contain only counts, field names, and module
  names.

### Tests

- `tests/unit/test_credit_relationships_determinism.py`
- `tests/unit/test_credit_relationships_bounds.py`
- `tests/unit/test_credit_relationships_leakage.py`

### Acceptance Criteria

- Two hash seeds and shuffled event order produce identical bytes.
- Every cap has a deterministic prefix and explicit partial coverage.
- No forbidden field/import/payload surrogate exists in credit code.
- Credit-disabled behavior is unchanged.

### Verification

- `uv run pytest tests/unit/test_credit_relationships_determinism.py tests/unit/test_credit_relationships_bounds.py tests/unit/test_credit_relationships_leakage.py -q`
- Expected: all pass.

## Phase Risks and Mitigations

- Risk: E2E accidentally relies on a private test bypass.
  Mitigation: use real admission and the real publication/read ports; no
  production-only flag is added.
- Risk: the experiment changes default behavior.
  Mitigation: off-gate registration and explicit `markets_credit`/commitment
  toggles only.
- Risk: determinism only covers ordering, not bytes.
  Mitigation: compare encoded snapshot bytes and analysis digests.
- Risk: leakage scan is too narrow.
  Mitigation: field, import, payload, and non-speech-command checks.

## Phase Completion Checklist

- Every Task 17-19 in this phase satisfies its acceptance criteria.
- Experiment, E2E, integration, determinism, bounds, and leakage tests pass.
- `index.md` checkboxes are updated only after verified completion.
