# Phase 6: Experiments, documentation and completion gates

Plan: [index.md](index.md)
Tasks: 21–24
Depends on: Tasks 17–20

## Objective

Demonstrate useful but fallible measurements in real runs, document the limits, and verify compatibility without inventing emergence/capacity or infrastructure certification.

## Current-Code Evidence

| Path | Symbols / evidence | Why it matters |
|---|---|---|
| `src/experiments/replication_scenario.py` | `scientific_replication_scenario` | Off-gate, paired-seed configuration opportunities; no forced science outcomes. |
| `src/experiments/catalog.py` | replication catalog entry and `experiment_scientific_replication` | Register measurement separately; don't extend the V1 A–E gate. |
| `tests/unit/test_replication_real_runner.py` | real runner → evidence test | Use a real V4-28 base fixture, not mocks alone. |
| `tests/unit/test_runner_config_v56.py` | v56 exact keys, old unsupported-v57 pin | Update current accepted-set pins without weakening old exact-key checks. |
| `tests/unit/test_replication_pins.py` | historical family suffix, routes and schemas | Measurement adds no metric family or replication snapshot change. |
| `docs/development.md` | frozen Python commands, coverage, infrastructure gates | Verification commands retain pinned interpreter and coverage. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/experiments/measurement_scenario.py` | create | Four explicit off-gate opportunity arms. |
| `src/experiments/catalog.py`, `src/experiments/__init__.py` | modify | Experiment registration/facade only. |
| `tests/unit/test_measurement_scenario.py`, `tests/unit/test_measurement_end_to_end.py`, `tests/unit/test_measurement_pins.py` | create | Scenario determinism, real pipeline, current version/count pins. |
| `tests/architecture/test_measurement_boundaries.py` | extend | Source/input/logging/presentation trust checks. |
| `tests/integration/test_measurement_journal.py` | create | Opt-in actual journal durability with disposable database. |
| `docs/measurement-instruments.md` | create | Physical, epistemic, configuration and reproduction contracts. |
| `README.md`, `docs/configuration.md`, `docs/physical-simulation.md`, `docs/scientific-hypotheses.md`, `docs/scientific-replication.md`, `docs/persistence.md`, `docs/development.md` | modify | Focused links and new seams only. |
| `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md` | modify during implementation docs checkpoint | Current V4-29 facts/pins, not retroactive rewriting of history. |

## Task 21: Register a reproducible measurement opportunity experiment

### Intent

Provide controlled examples of inaccurate readings and mistaken reliability without scripting scientific success.

### Implementation Steps

1. Add `measurement_instruments_scenario(base, *, seed_matrix=None, max_ticks=64)` in `experiments/measurement_scenario.py`; ID `measurement_instruments@1`, policy `measurement-instruments.v1`. Require at least two configured founders and finite horizon ≥64.
2. Derive one shared world from the supplied base: add one explicitly named ambient instrument TOOL item and one physical temperature-reference TOOL item for each of the first two founders. Resolve founder agent IDs through their `AgentRunnerSpec.entity_id` body mapping; TOOL `holder_id` is the body entity, not the cognitive AgentId. Add both item IDs to each holder's `AgentBody.inventory` in stable existing-plus-new order. Assign each new tool/reference `ItemLoad(1)`, preserve existing capacity/rules/items, and reject a base lacking two free load units with `measurement_scenario_carry_capacity`—never silently raise capacity, create weightless items or drop existing inventory. All arms have identical complete items/bodies, layout, roster, seed/stochastic identity, initial reference physical values and stop horizon. Use stable namespaced IDs; fail on collisions instead of replacing user scenario objects.
3. Keep science prerequisites and deterministic communication identical across arms. Baseline is existing v56 science with no instrument spec; enabled arms use v57. Arms: `measurement-absent`, `measurement-unbiased`, `measurement-biased`, `measurement-damaged`. Enabled controls share step=1000 milli-C, noise bound=0, initial damage=0, correction=0. Biased changes only intrinsic bias to +5000 milli-C. Damaged changes only initial damage to 750 milli from unbiased control. Reference nominal=20000 and hidden physical=21000 milli-C in every arm, so a completed calibration is not guaranteed accurate.
4. Preserve all other supplied fields and active-family semantics. This experiment focuses on ambient tools; all five dimensions are covered by dedicated physical/e2e fixtures. Do not automatically invent regions/routes.
5. Register in catalog/facade outside the V1 gate. State that autonomous non-use, disagreement and no calibration are legal outcomes; controlled tests can submit ordinary commands but production scenarios do not force successful cognition.
6. Validate/materialize the complete shared `WorldScenarioSpec` through ordinary bootstrap before deriving arms; both placement graph and carrying-capacity invariants must pass. Validate every arm through `SimulationRunner.from_config`, not merely scenario/config dataclass construction.

### Required Interfaces and Contracts

Paired seed identity does not prove single-run causality. Baseline's absence of a physical sidecar is the declared treatment difference; its otherwise identical TOOL items have no hidden measurement powers.

### Error Handling and Logging

Reject invalid horizon, fewer than two founders, ID collisions and incompatible base configs with safe codes. Registration logs ID/arm counts only.

### Tests

Four closed arm IDs, seed equality and deterministic config bytes, declared one-factor differences for biased/damaged versus unbiased, same complete world items/bodies, baseline no spec/v56, enabled v57, invalid input, no silent route creation or V1 gate registration. Instantiate a real runner for every arm; assert bidirectional holder/inventory consistency, distinct AgentId/body-ID mapping, exactly two extra load units per selected founder, and rejection of an initially full founder inventory without changing the caller's base.

### Acceptance Criteria

A reusable off-gate experiment exposes fallibility and physical condition as declared treatments without guaranteeing emergence.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_measurement_scenario.py tests/unit/test_replication_scenario.py --cov=experiments --cov-report=term-missing -q`

Expected: deterministic scenarios and unchanged replication scenario pass.

## Task 22: Prove the full physical-reading-evidence lifecycle

### Intent

Validate actual supported combinations through real engine/runtime execution and preserve a representative existing science run.

### Implementation Steps

1. Reuse the real V4-28 runner fixture/pattern from `test_replication_real_runner.py`, loading its actual v56 config before deriving v57; keep the original fixture as an unmodified regression input.
2. Build an explicit five-dimension physical fixture with TOOL instruments/references, local resource, carried/ground item, timer and regional route. Through normal admitted commands collect readings, wear and calibrate; ingest actor observations, send/receive a bounded report using actual64-character event roots and full source IDs, finalize owner state, checkpoint, restore and continue. Validate complete item/inventory/capacity graphs before execution.
3. Assert displayed values/evidence bases and instrument hidden-state redaction at each boundary. Demonstrate wrong fine-precision reading, biased physical reference worsening accuracy, two owners with different reliability beliefs, and travel duration changing without invented route length.
4. Compare deterministic twins; compare uninterrupted versus supported checkpoint/pending recovery and process-local forks. Include rejected/overridden action, broken tool, target loss, absent source and receipt/row-cap cases. Assert committed measurement events and `runner.export_measurement_ledgers()` from the real prepare/bind/finalize path; direct `CognitiveLoop.run()` output is not enough. Include an autonomous eligible-Wait fixture where existing science candidates are legitimately exhausted/ineligible so a measurement candidate reaches engine submission.
5. Add opt-in `tests/integration/test_measurement_journal.py` using actual current persistence/journal fixtures and a disposable `palimpsest_test` database. Persist event28/v26 and pending-v3 through existing opaque stores, replay after process-local reconstruction, and verify full hashes/observations. Do not claim full durable subjective resume.
6. Run inherited V4-28 test suites unchanged except current global pin updates required by deliberate new accepted versions/command count.

### Required Interfaces and Contracts

No standalone synthetic reading object is sufficient as end-to-end evidence. The test must include real admitted command → committed event → redacted observation → candidate/finalized owner evidence → supported restore.

### Error Handling and Logging

Assert exceptions/log capture never contains prompts, readings, sampled values, corrections, hidden reference parameters or payload fingerprints. Missing DB prerequisites are `unexecuted`/skipped, not certified.

### Tests

`test_measurement_end_to_end.py` covers all index combination rows. The integration file covers actual storage rather than assuming an in-memory journal proves durability.

### Acceptance Criteria

At least one representative existing v56 run remains byte/trajectory-compatible and one new v57 run proves the complete measurement/evidence/replay path.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_measurement_end_to_end.py tests/unit/test_replication_real_runner.py --cov=world --cov=simulation --cov=agents.cognition --cov-report=term-missing -q`

Optional durability: `uv run --frozen --python 3.12.14 pytest -m integration tests/integration/test_measurement_journal.py --cov=simulation --cov=persistence --cov-report=term-missing -q`, with a validated `PALIMPSEST_TEST_DATABASE_URL`. Record prerequisite failures separately.

## Task 23: Complete the mandatory documentation checkpoint

### Intent

Explain operational use and epistemic limits precisely; avoid suggesting that measurement creates objective scientific truth.

### Implementation Steps

1. Invoke `$aif-docs` at implementation completion, then create `docs/measurement-instruments.md` and a README index link. Document the exact v57 spec, TOOL anchoring, five dimensions, fixed-point display, ordinary command costs and example admitted flow.
2. Distinguish precision, intrinsic bias/noise, objective damage/calibration and owner reliability beliefs. Explain flawed physical references, calibration not repair/certification, negative temperatures and simulation-only amount/load/travel units.
3. Document source provenance, actor-only readings, communicated testimony, bounded retention/unavailability and the fact that legacy exact resource/load/tick/body-temperature observations were not removed.
4. Update focused configuration/persistence/science pages for event28/v26, domain-envelope2, pending-v3/measurement-state-v1 and unchanged categorical `rep_v1`/hypothesis scoring. Explain observer coarse aliases, no new dashboard/routes/metric families, and replay versus subjective resume.
5. Update DESCRIPTION/current architecture baseline to V4-29: 45 commands, 73 semantic types, 256 families, 17 contexts, 12 flags, 9 owned/3 unowned; replay28/v26 when instrument channel active; absent channel keeps prior pairs. Default runner/result remain v4/v2; latest new opt-in schema is v57.
6. Link to M8 without closing the milestone. Roadmap edits belong to `$aif-roadmap`; request/route a V4-29 completion receipt through that owner command rather than independently declaring M8 complete.

### Required Interfaces and Contracts

Documentation must not claim physical distance, SI mass, calibration truth, automatic instrument manufacture, objective reliability available to agents, or infrastructure certification that was not executed.

### Error Handling and Logging

Examples contain safe synthetic IDs and no credentials. Record missing prerequisites as limitations rather than hiding them.

### Tests

Extend docs/pin checks in `test_measurement_pins.py` for links, current baseline and documented version/quantity contract; do not normalize unrelated stale historical paragraphs as part of this task.

### Acceptance Criteria

A contributor can configure, execute, reproduce and correctly interpret instrument readings from the documented example.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_measurement_pins.py --cov=simulation --cov-report=term-missing -q`

Additionally check all new relative Markdown links resolve and examples use valid exact-key configuration.

## Task 24: Run compatibility, architecture and quality gates

### Intent

Complete the plan only after the new physical seam and existing invariants are verified together.

### Implementation Steps

1. Add measurement pin assertions for current accepted versions and counts. Update obsolete global “v57 unsupported”/43-command pins to intentional new expectations; retain legacy exact-key fixtures, historical family prefix/suffix order and unsupported reserved codec tests.
2. Extend architecture tests: cognition has no import/signature path to `InstrumentState`, `MeasurementReference`, private world modules, events or objective error calculators; observer/API remain read-only; no analysis-to-cognition dependency; no payload-bearing logs. Audit the `pyproject.toml` and AST private-world lists together for `_measurement`/`_ambient`, including allowed-importer closure and negative cognition/API/analysis fixtures. Physical measurement tests may inspect objective state as trusted tests, not agent inputs.
3. Run focused feature suites plus the full unit/architecture suite with coverage enabled, Ruff, mypy and import-linter. Correct implementation issues, not unrelated user changes; document pre-existing failures.
4. Run non-DB integration lanes affected by runtime/engine contracts, then optional actual persistence, existing observer client protocol, Compose/browser or scale lanes only when prerequisites are available. No client/infrastructure file changes are authorized merely to turn an unrelated lane green.
5. Record exact commands/results, versions, coverage and unexecuted prerequisite-bound lanes in the plan completion summary. Do not add an orphan verification markdown file to this ultra bundle. Do not claim throughput/scale capacity or full certification on skipped lanes.
6. Mark index tasks complete only after their acceptance checks. Stop for review; don't commit/push automatically.

### Required Interfaces and Contracts

Completion pins: 45 commands; 73 semantic types; 256 metric families; 17 contexts/12 flags/9 owned; new optional v57; default v4/result v2; active event28/v26; otherwise prior pairs; Alembic0017; `/v1`; `observer-protocol-v1`; `prepare_parallel=False`.

### Error Handling and Logging

Report safe bounded failure summaries and relevant file paths. Do not dump dependency locks, excluded artifacts or full generated coverage reports into context.

### Tests

Feature, regression, architecture and current-pin suites below are mandatory. Integration/client lanes remain explicitly prerequisite-bound.

### Verification

Run separately, not as a noisy shell chain:

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_measurement_*.py tests/unit/test_runner_config_v57.py tests/architecture/test_measurement_boundaries.py --cov --cov-report=term-missing -q
uv run --frozen --python 3.12.14 pytest tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py tests/unit/test_replication_*.py tests/unit/test_runner_config_v56.py tests/unit/test_compatibility_matrix.py --cov --cov-report=term-missing -q
uv run --frozen --python 3.12.14 pytest tests/unit tests/architecture --cov --cov-report=term-missing -q
uv run --frozen --python 3.12.14 ruff check src tests
uv run --frozen --python 3.12.14 mypy src tests
uv run --frozen --python 3.12.14 lint-imports
```

Use exact discovered current integration fixture paths when extending the existing runtime integration lane. Existing optional client command: `"${GODOT_BIN}" --headless --path clients/godot-observer --script res://tests/run_protocol.gd`; expected `failed=0` with pinned 4.7.2. No browser or database pass is inferred from unit success.

### Acceptance Criteria

All mandatory gates pass, legacy no-instrument behavior is stable, all requested properties and examples have verification evidence, and any optional unexecuted lanes are clearly named.

## Phase Risks and Mitigations

- Tests “pass” only because data was synthetic: mandatory real-v56 fixture and full admitted v57 lifecycle.
- Causal or scientific certainty overstated: legal nulls and explicit difference between observations and target truth.
- Pin updates erase history: change current accepted-set/count assertions only; keep all historical wire inputs executable.

## Phase Completion Checklist

- Tasks 21–24 pass their acceptance checks.
- Documentation checkpoint is complete, optional gates are honestly reported, and only `index.md` stores progress.
