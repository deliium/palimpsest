# Phase 5: Experiment and Certification Paths

Plan: [index.md](index.md)
Tasks: 15-17
Depends on: Phase 3 (Tasks 9-12) for the real path; Phase 4 (Task 13) for reads

## Objective

Register an off-gate `scientific_hypotheses@1` experiment with three arms,
prove the full in-process path from real admission through a real `Experiment`
command, real `ExperimentResolved` events, real ledger updates, real snapshot,
real store, and real API reads, and certify determinism, cap bounds, and
no-objective-rule leakage. The experiment stays off the V1 A-E gate.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/experiments/catalog.py` | `OFF_GATE_MATRIX_EXPERIMENT_IDS` (2800-2841), registration wrappers (5715-5833), experiment I channel config (4510-4565) | Exact registration and bounded-experimentation composition |
| `src/experiments/economic_cascades_scenario.py` | scenario id (46), arm construction (92-172) | Three-arm off-gate template |
| `src/experiments/civilization_benchmark_technology.py` | `_experimentation` (209-216) and arm composition (254-282) | `BoundedExperimentationSpec` fixture pattern |
| `src/simulation/runner_models.py` | `example_bounded_experimentation_spec`, `example_experiment_law` (4853-4877) | Law fixture helpers |
| `tests/unit/test_economic_cascades_experiment.py` | registration/off-gate/arms (55-106) | Experiment test template |
| `tests/unit/test_v1_regression_gate.py` | A-E only (47-53, 217-224) | The gate the new experiment must stay out of |
| `tests/unit/test_economic_cascades_end_to_end.py` | real engine/store/API flow (159-164) | E2E template |
| `tests/integration/test_economic_cascades_store_api.py` | real store plus TestClient | Integration template |
| `tests/unit/test_economic_cascades_leakage.py` | row/snapshot/route scans (36-78) | Leakage test template |
| `tests/unit/test_economic_cascades_determinism.py` | hash-seed independence | Determinism template |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/experiments/scientific_hypotheses_scenario.py` | create | Three-arm off-gate scenario |
| `src/experiments/catalog.py` | modify | Register `scientific_hypotheses@1`; add to off-gate ids |
| `src/experiments/__init__.py` | modify | Export the scenario |
| `tests/unit/test_scientific_hypotheses_experiment.py` | create | Registration, arms, off-gate, inert baseline |
| `tests/unit/test_scientific_hypotheses_end_to_end.py` | create | Real command/events/ledger/snapshot/store/routes |
| `tests/integration/test_scientific_hypotheses_store_api.py` | modify | Add the experiment-backed real path if the unit E2E uses a fake clock |
| `tests/unit/test_scientific_hypotheses_determinism.py` | create | Hash-seed and repeat determinism |
| `tests/unit/test_scientific_hypotheses_bounds.py` | create | Independent caps and monotonicity |
| `tests/unit/test_scientific_hypotheses_leakage.py` | create | No objective-rule/truth/score leakage |
| `tests/architecture/test_scientific_hypotheses_boundaries.py` | create | Import and wire-surface boundaries |

## Task 15: Register off-gate `scientific_hypotheses@1`

### Intent
Provide a reproducible three-arm comparison over the owned `science` flag. The
baseline arm is provably inert: it carries bounded experimentation but no
science, so the legacy ledger is untouched, no test replacement occurs, and no
science metric or snapshot exists.

### Implementation Steps
1. Create `src/experiments/scientific_hypotheses_scenario.py`:
   - `SCIENTIFIC_HYPOTHESES_EXPERIMENT_ID = "scientific_hypotheses@1"`.
   - Build one shared base from an existing experiment-friendly scenario (use
     `experiment_i_causal`'s base or `economic_cascades_scenario`'s base) with
     `schema_version=RUNNER_SCHEMA_VERSION_V56`,
     `v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True)`,
     `cultural_feature_provenance` present, exact
     `BoundedExperimentationSpec(laws=(example_experiment_law(...),),
     max_hypotheses=8, max_trials_per_tick=1, repeat_threshold=2,
     learn_into_genealogy=False, allow_provider=False)`, and a deterministic
     stop policy with `max_ticks >= 64`.
   - Arms in fixed order:
     - `science-baseline`: `V4CapabilityFlags()` all off,
       `capability_flags.predictive_world_model=False`; bounded experimentation
       remains on. This arm must produce zero test replacements and zero
       science metrics.
     - `science-enabled`: `V4CapabilityFlags(science=True)`,
       `predictive_world_model=True`.
     - `science-communicated`: same as enabled plus
       `CommunicationStrategyMode.DETERMINISTIC` and a paired channel that must
       produce at least one `hyp_v1` adoption. Assert one adopted row with
       `source_kind=communicated`, zero support/contradictions, and a delivery
       event source token; if the deterministic channel cannot produce one, mark
       this arm `unexecuted` with the prerequisite instead of passing it
       silently.
   - Use `paired_world_group=f"{SCIENTIFIC_HYPOTHESES_EXPERIMENT_ID}-world"`.
   - Reject `max_ticks < 64`.
2. In `src/experiments/catalog.py`:
   - Add `"scientific_hypotheses@1"` to `OFF_GATE_MATRIX_EXPERIMENT_IDS`.
   - Add `experiment_scientific_hypotheses(base, *, seed_matrix=None,
     max_ticks=...)` following the `experiment_economic_cascades` wrapper
     (5776-5792), logging
     `experiment_registered experiment_id=scientific_hypotheses@1 arms=3`.
   - Do not add it to `EXPERIMENT_A_V1_CONDITION_IDS` or
     `tests/unit/test_v1_regression_gate.py`.
3. Export the scenario from `src/experiments/__init__.py`.

### Required Interfaces and Contracts
- Exactly three ordered arms; all use v56 and the accepted exact key set.
- Every unowned V4 flag stays false.
- Baseline science is off; the other two arms are on.
- The experiment is off the V1 A-E gate and does not alter its builders.
- No new capability flag, context, runner schema, command, event, write pair,
  route, or migration is introduced.

### Requirement Evidence
- `src/experiments/economic_cascades_scenario.py:46,92-172`.
- `src/experiments/catalog.py:2800-2841,5776-5792`.
- `tests/unit/test_v1_regression_gate.py:47-53,217-224`.
- `.ai-factory/ARCHITECTURE.md` requirement 3 (feature experiments stay off the
  V1 gate).

### Error Handling and Logging
- INFO `experiment_registered experiment_id=scientific_hypotheses@1 arms=3`.
- WARN `scientific_hypotheses_scenario_invalid reason_code=<token>` for
  unsupported ticks or missing bounded spec.
- Never log arm payloads, laws, or agent configs.

### Tests
- `tests/unit/test_scientific_hypotheses_experiment.py`:
  - registered once; in `OFF_GATE_MATRIX_EXPERIMENT_IDS`; not in
    `EXPERIMENT_A_V1_CONDITION_IDS`.
  - exactly three ordered arms; all v56; unowned flags false; science on only
    for arms 2-3; predictive world model on only for arms 2-3.
  - the communicated arm is configured for deterministic communication and
    records the adoption prerequisite; actual adoption is exercised in Task 16.
  - baseline produces no hypothesis replacement and no science metric docs.
  - `max_ticks < 64` rejected.
  - the V1 A-E catalog remains exactly A-E.

### Acceptance Criteria
- The experiment is registered and off-gate.
- The baseline arm is inert by construction.
- The communicated arm is configured for deterministic communication, and Task
  16 proves one adopted `hyp_v1` row or records the arm `unexecuted`.
- No V1 gate change exists.

### Verification
- `uv run pytest tests/unit/test_scientific_hypotheses_experiment.py tests/unit/test_v1_regression_gate.py -q`
- Expected result: pass.

## Task 16: Add in-process end-to-end coverage

### Intent
Prove the whole feature with real components: a real v56 runner, a real agent
tick, a real `Experiment` command admitted by the engine, a real
`ExperimentResolved` event, a real ledger update, a real completed-run bridge, a
real canonical snapshot, a real filesystem store, and all seven real API reads.
At least one arm must produce a contradicted hypothesis, proving wrong
hypotheses survive rather than being deleted.

### Implementation Steps
1. Create `tests/unit/test_scientific_hypotheses_end_to_end.py`:
   - Build a v56 config with science, predictive world model, bounded
     experimentation, cultural history/provenance, mortality disabled, and a
     deterministic world containing exactly one observed non-consumable operand
     (for example a tool item in `observation.items`), no consumable resources,
     no other agents, and no unmet needs, so the deterministic selected command
     is `Wait` on the test ticks and `observed_experiment_operand_ids`
     (`agents/cognition/production.py:403-415`) is non-empty.
   - Use two law fixtures: one `success` law for support and one `failure` law
     for contradiction. Both match the observed operand kind and the
     deterministic `vary_process`/`harvest` test path (one operand), for example
     `example_experiment_law(operator="vary_process",
     operand_a_kind="item:tool", operand_b_kind="", process_token="harvest",
     outcome_class="failure", delta="none")`. The deterministic test action
     predicts `success`, so the failure law produces `counter=1`. The locked
     policy uses `min_evidence=2`; therefore one contradiction leaves the row
     `provisional` with the contradiction retained, and two contradictions make
     it `contradicted`. Run long enough for two failed trials
     (`max_trials_per_tick=1`) and assert `status=contradicted` plus two
     retained contradictory evidence ids. Separately unit-test the
     one-contradiction `provisional` state in Task 4.
   - Run the real `SimulationRunner` for enough ticks to admit at least two
     `Experiment` commands; assert committed `ExperimentResolved` events exist.
   - Assert the final `SimulationRunnerResult.experiment_ledgers` contains a
     hypothesis with claim, conditions, predicted outcome, confidence milli,
     supporting and contradicting evidence, source kind, and at least two
     revisions.
   - Call `build_completed_run_scientific_hypotheses_analysis` with the real
     committed events, compose the snapshot, publish through the real store to
     `tmp_path`, attach the reader through the app factory with both settings,
     and read all seven routes with `TestClient`.
   - Assert the summary, one hypothesis row, one test row, one revision row,
     one source row, and coverage; assert a contradiction is visible.
   - Assert no response contains `law`, `laws`, `rule`, `rules`, `delta`,
     `product_id`, `harm_band`, `health_delta`, `truth`, `verified`, `proven`,
     `accuracy`, `calibration`, or `score`.
   - Run the `science-communicated` arm or a focused two-loop harness and assert
     one adopted `hyp_v1` row with `source_kind=communicated`, zero
     support/contradictions, and a delivery event source token; if the
     deterministic channel produces no exchange, record the arm `unexecuted`
     with its prerequisite rather than accepting a no-op.
2. Extend `tests/integration/test_scientific_hypotheses_store_api.py` with the
   same real publication/read path using the actual store directory, marked
   `integration`, so the integration lane in Task 21 has a named file.
3. Do not mock the engine, the command admission, the event stream, the ledger,
   the codec, the store, or the routes.

### Required Interfaces and Contracts
- The test uses real admission and real commands; no synthetic event list is
  substituted for the event stream.
- The snapshot and store are real; the API uses the real app factory.
- A wrong prediction is retained as a contradiction; no truth assertion is made.
- The E2E asserts no objective-rule payload crosses any layer.

### Requirement Evidence
- Original Request "Agents may intentionally formulate tests", "Hypotheses can
  be wrong", "Do not expose objective rules".
- `tests/unit/test_economic_cascades_end_to_end.py` and
  `tests/integration/test_economic_cascades_store_api.py`.

### Error Handling and Logging
- The test captures logs and asserts metadata-only messages: no claim operands,
  conditions, evidence ids, owner ids, or rule payloads.
- A failed publication returns a closed receipt and fails the test explicitly.

### Tests
- The E2E file itself is the test. Include:
  - real test command and event proof;
  - ledger field proof;
  - contradiction retention proof;
  - snapshot/store/API proof for all seven routes;
  - forbidden-field scan of every response body;
  - a second run with science off proving no test replacement, no analysis, and
    no route data.

### Acceptance Criteria
- The full path passes without mocks.
- A contradicted hypothesis is visible end to end.
- Science-off is inert.

### Verification
- `uv run pytest tests/unit/test_scientific_hypotheses_end_to_end.py -q`
- `uv run pytest tests/integration/test_scientific_hypotheses_store_api.py -q -m integration`
- Expected result: pass.

## Task 17: Add determinism, property bounds, and no-rule leakage coverage

### Intent
Prove the feature is deterministic across process hash seeds, that every cap is
independent and monotone, and that objective rules, owner ids, truth, and scores
cannot leak through rows, snapshots, routes, or the UI contract.

### Implementation Steps
1. `tests/unit/test_scientific_hypotheses_determinism.py`:
   - Run the same ledger/analysis fixture in subprocesses with
     `PYTHONHASHSEED=0` and `PYTHONHASHSEED=1`; assert identical hypothesis
     tokens, revision order, analysis digest, and snapshot bytes.
   - Assert repeat composition is idempotent.
   - Assert canonical JSON key order and trailing newline.
2. `tests/unit/test_scientific_hypotheses_bounds.py`:
   - Independent caps for hypotheses, conditions, revisions, evidence, trials,
     objective evidence, and coverage; exceeding one truncates only that family
     and sets `partial`.
   - Property tests: confidence in `0..1000`; revision indexes strictly
     increasing; status always in the closed set; condition count in `0..8`;
     trial count never exceeds the configured cap.
   - Property test: a hypothesis with counter > support is never reported as
     `supported`.
3. `tests/unit/test_scientific_hypotheses_leakage.py`:
   - Every row and serialized snapshot has no `law`, `laws`, `rule`, `rules`,
     `delta`, `product_id`, `harm_band`, `health_delta`, `truth`, `verified`,
     `proven`, `accuracy`, `calibration`, `score`, or `owner_id`.
   - No condition pair contains a raw owner/agent id; `counterpart` values are
     opaque tokens.
   - Route responses and UI fixtures contain no forbidden vocabulary.
   - A communicated hypothesis has zero support/contradiction and copies no
     evidence id.
   - An objective `ExperimentResolved` delta/product/harm is never copied.
4. `tests/architecture/test_scientific_hypotheses_boundaries.py`:
   - `analysis` imports no `agents`, `api`, `persistence`, `experiments`,
     `infrastructure`, `observer`, `world._experiment_laws`, or `world._rules`.
   - `simulation` imports no `analysis`, API, or persistence.
   - `experiments` imports no API or concrete persistence.
   - no `runner-config-v57`; no `alembic/versions/0018*`; no `/v2`; no new
     `AgentCommand`; no Godot source change.

### Required Interfaces and Contracts
- Determinism is over tokens, ordering, digests, and bytes, not over unconstrained
  float bits.
- Cap behavior is deterministic prefixes, never random sampling.
- Leakage checks are field-name and value scans, not documentation-only claims.
- Architecture checks are AST/source checks.

### Requirement Evidence
- Original Request "Hypotheses can be wrong" and "Do not expose objective
  rules".
- `.ai-factory/ARCHITECTURE.md` Key Principles 1, 2, and 4.
- V4-26 determinism/bounds/leakage test layout.

### Error Handling and Logging
- Tests assert WARN/ERROR codes only; no payload appears in captured logs.
- A failed deterministic assertion reports the differing token path, not the
  payload.

### Tests
- The three unit files and one architecture file listed above.

### Acceptance Criteria
- Hash-seed and repeat runs are identical.
- Every cap is independent and monotone.
- No objective rule, truth, score, or owner id leaks.
- Import and wire-surface boundaries hold.

### Verification
- `uv run pytest tests/unit/test_scientific_hypotheses_determinism.py tests/unit/test_scientific_hypotheses_bounds.py tests/unit/test_scientific_hypotheses_leakage.py tests/architecture/test_scientific_hypotheses_boundaries.py -q`
- Expected result: pass.

## Phase Risks and Mitigations
- Risk: the deterministic test action always predicts success, so no
  contradiction ever appears.
  Mitigation: configure a `failure` law in the E2E arm; the predicted success is
  then contradicted and retained.
- Risk: the E2E mocks the engine and proves nothing.
  Mitigation: Task 16 forbids mocks for admission, commands, events, ledger,
  codec, store, or routes.
- Risk: a leakage test checks only dataclass fields but not serialized bytes.
  Mitigation: scan rows, snapshot bytes, route responses, and UI fixtures.

## Phase Completion Checklist
- The off-gate experiment is registered with three arms and an inert baseline.
- The real end-to-end path passes with a contradicted hypothesis.
- Determinism, bounds, and leakage suites pass.
- `index.md` Tasks 15-17 checkboxes are updated after verification.
