# Phase 4: Real-run and regression verification

Plan: [index.md](index.md)
Tasks: 10-11
Depends on: Phase 2 / Tasks 5-7 and Phase 3 / Tasks 8-9

## Objective

Prove the feature with real AY-derived BM runs and matrix cells, then verify that legacy V1/V2 behavior, schema pins, metric pins, seed-scope boundaries, and package boundaries remain intact.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `tests/unit/test_experiment_bl.py` | `test_bl_runs_produce_multiple_generations_and_movement` (58) | Existing real v55 generational execution pattern. |
| `tests/unit/test_generational_matrix_schema.py` | v55 matrix base and finalize tests | Existing matrix v55 preservation. |
| `tests/unit/test_v1_regression_gate.py` | V1 A–E gate | Must stay green with new families absent. |
| `tests/unit/test_v2_scientific_invariants.py` | V2 invariants | Must stay green. |
| `tests/unit/test_metric_specifications.py` | `METRIC_FAMILY_COUNT` assertion | Count pin moves 129 → 130. |
| `tests/unit/test_compatibility_matrix.py`, `test_v2_golden_runner_configs.py`, `test_alembic_head_pin.py` | Version/default/migration pins | Must not change. |
| `tests/architecture/test_analysis_isolation.py` | Analysis import isolation | New metric module must stay analysis-only. |
| `tests/architecture/` | Import boundary checks | New experiments modules must not import API/persistence/analysis in forbidden directions. |
| `src/simulation/generational_seeds.py` | Run-ID-scoped demography/init/lifespan channels | Comparability claims must stay honest. |
| `pyproject.toml` | import-linter contracts, Ruff, mypy, pytest markers | Verification commands. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `tests/unit/test_experiment_bm_execution.py` | create | Real BM execution over AY with generations and metrics. |
| `tests/unit/test_generational_matrix_execution.py` | create | Expanded v55 matrix cell execution and factor effect checks. |
| `tests/architecture/test_v3_generational_experiments_isolation.py` | create | Import-boundary checks for new modules. |
| `tests/unit/test_metric_specifications.py` | modify | Count 130 and function name if needed. |
| every `tests/unit` file containing `METRIC_FAMILY_COUNT` | modify | Update literal count 129 → 130. |
| any test enumerating matrix factor ids | modify | Add the new additive factor ids where the assertion is exact. |

## Task 10: Execute the BM real-world comparison experiment

### Intent

Run the five BM pairs on the real AY-derived world and prove that multiple generations, cohort rows, and the new metric occur without synthetic-only fixtures.

### Implementation Steps

1. Create `tests/unit/test_experiment_bm_execution.py` marked as a normal unit test (network-free, no Docker/Postgres). Use `max_ticks=12` so short-lifespan founders reach natural death and at least two admission waves occur; use the deterministic fake provider already used by the AY/BL tests.
2. Build `definition = generational_comparison_scenario(seed=23, max_ticks=12)`.
3. Run `await ExperimentCoordinator(definition).run_all()`; do not use the matrix archive path in this test.
4. Assert:
   - exactly ten results, one per expected condition id, with no failure;
   - every result has `runner_result.generational_progress is not None`;
   - at least one result has `max_generation_index_seen >= 1`, and preferably every generational arm has at least generation 0 + one entrant generation; assert the weaker `>= 1` for stability;
   - cohort rows are non-empty in the arms with admitted entrants, and the short-lifespan pair records at least one objective death by the final boundary;
   - `generation:` and `cohort:` dynamic keys exist in the assembled metric document and are consistent with the progress rows;
   - the metric family availability is `PRESENT`;
   - every condition has at least one lifecycle record for its founders, and entrants have `generation_index >= 1` and a non-bootstrap cohort id when they exist.
5. Pair assertions:
   - `bm-oral-vs-records-treatment` has `durable_records is not None`; control is `None`; both have equal seed/scenario/roster/schedule.
   - `bm-short-vs-long-lifespan` has exact `lifespan_ticks` 8 and 24 and equal schedules.
   - `bm-isolated-vs-connected` has no regions/flag for isolated and both for connected.
   - `bm-low-vs-high-teaching` has the exact rate presets and equal skill learning.
   - `bm-reference-vs-reconstructive-memory` has `REFERENCE` vs `RECONSTRUCTIVE_V2`.
6. Assert `assert_comparable_generational_conditions` passes for all ten conditions and that no pair changes founder body ids/locations.
7. Collect metrics with `assemble_arm_metric_bundle` or `collect_catalog_metrics` for every result and assert the family is present and deterministic on a second assembly.
8. Do not assert a guaranteed social outcome such as a durable record being created, a teaching act occurring, or migration happening; those depend on cognition and horizon. Structural configuration, generation admission, cohort rows, and metric wiring are the contract.
9. Log only test-level counts through pytest output; no production logging changes.

### Required Interfaces and Contracts

- BM runs through the ordinary `SimulationRunner` executed by `ExperimentCoordinator`; no generational archive is required for this library path.
- `runner_result.generational_progress` is the sole source for the new metric.
- The BM experiment remains off the V1 gate and is not added to `EXPERIMENT_A_V1_CONDITION_IDS`.

### Error Handling and Logging

- If an arm fails, pytest reports the condition id and exception; do not catch and continue silently.
- No new production logs are added in this task.

### Tests

Commands:

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_experiment_bm.py tests/unit/test_experiment_bm_execution.py -q
uv run --frozen --python 3.12.14 pytest tests/unit/test_experiment_bm_execution.py -q -x
```

### Acceptance Criteria

- All ten BM arms execute on the real AY-derived base.
- At least one admitted generation beyond founders is observed, with cohort rows.
- The new metric is present and consistent with progress.
- Pair configurations differ only by the declared axis.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_experiment_bm_execution.py -q`
- Expected: all arms complete; no traceback; metric family present.

## Task 11: Prove matrix cells, legacy gates, and seed-scope boundaries

### Intent

Close the verification loop: a generational matrix cell must execute with the new factors, legacy gates must remain unchanged, and the comparability gate must reject false same-seed claims.

### Implementation Steps

1. Create `tests/unit/test_generational_matrix_execution.py`:
   - Build an `ExperimentMatrixSpec` with `MatrixEmbeddedBase(generational_comparison_base(seed=23, max_ticks=8))` and two factors:
     - `lifespan` `short`/`long`, group roles control/treatment;
     - `teaching_frequency` `low`/`high`, group roles control/treatment.
   - Call `expand_matrix`; assert every condition is v55 and comparability passes.
   - Execute one definition through `ExperimentCoordinator(definition, generational_contexts={"*": context})` using `GenerationalExecutionContext` and the existing `PLAIN_RECIPE_ID`, as in `tests/unit/test_experiment_bl.py`.
   - Assert the selected cell produces `PopulationProgress`, the new metric, correct lifespan/teaching settings, and no schema change.
   - Do not require PostgreSQL; the test uses the in-memory coordinator and a temporary artifact root for the context.
2. Create `tests/architecture/test_v3_generational_experiments_isolation.py`:
   - Follow the existing architecture-test style and assert the new modules obey package boundaries:
     - `analysis.generational_cohort` does not import `experiments`, `api`, `persistence`, `infrastructure`, `agents.cognition`, or runtime engine modules beyond public read-only contracts.
     - `experiments.generational_comparison*` does not import `analysis`, `api`, `persistence`, or concrete infrastructure.
     - `simulation` does not import the new experiments modules.
   - Prefer the existing AST/import-linter helpers over duplicating a checker; if a simple import check is used, assert the module set by path.
3. Update the metric count pins:
   - `METRIC_FAMILY_COUNT = 130` in `src/analysis/specifications.py`.
   - Update every literal `129` associated with `METRIC_FAMILY_COUNT` under `tests/unit/`. Use `rg -l "METRIC_FAMILY_COUNT" tests/unit` and inspect each match; do not change unrelated `129` values, command counts, or historical docs.
   - Update `tests/unit/test_analysis_serialization.py` and any exact family-set assertion to include `generational_cohort_comparison`; keep unknown-family rejection covered.
   - Rename `test_catalog_has_109_unique_families` to reflect 130 if it still carries the stale name.
4. Add a seed-scope boundary test:
   - Build two identical BM conditions; comparability passes.
   - Replace `population_lifecycle.lifespan_distribution` with a non-passthrough `uniform_int` spec; comparability raises `comparison_lifespan_distribution_not_passthrough`.
   - Replace `new_agent_initialization.parameter_distributions` with a non-`none` distribution; comparability raises `comparison_initialization_not_deterministic`.
   - Document in the test docstring that run-ID-scoped channels remain honest and this gate is about the declared comparable base, not arbitrary RunId reproduction.
5. Run the legacy gates:

```bash
uv run --frozen --python 3.12.14 pytest \
  tests/unit/test_v1_regression_gate.py \
  tests/unit/test_v2_scientific_invariants.py \
  tests/unit/test_compatibility_matrix.py \
  tests/unit/test_v2_golden_runner_configs.py \
  tests/unit/test_metric_specifications.py \
  tests/unit/test_alembic_head_pin.py -q
```

6. Run import boundaries and static checks:

```bash
uv run --frozen --python 3.12.14 lint-imports
uv run --frozen --python 3.12.14 ruff check src tests
uv run --frozen --python 3.12.14 mypy src tests
```

7. Run the relevant unit suites, then the default full suite:

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_generational_matrix_execution.py tests/unit/test_experiment_bm_execution.py tests/unit/test_generational_cohort_metrics.py tests/unit/test_generational_cohort_collectors.py -q
uv run --frozen --python 3.12.14 pytest
```

8. If any count assertion outside `tests/unit` or a documentation pin fails, report it in the task notes and fix only current pins; do not rewrite historical plans or roadmap history.

### Required Interfaces and Contracts

- No production interface is added in this task; it adds tests and updates count pins.
- Matrix cells remain `experiment-matrix-v1` and v55; no archive schema changes.
- Legacy V1/V2 paths remain byte-identical when the new feature is off.

### Error Handling and Logging

- Test failures must show the condition/cell id and stable validation code.
- No production logging changes.
- No secrets or payloads in test assertions/logs.

### Tests

Commands as listed in steps 5-7. Expected:

- V1 regression and V2 invariants pass with the new family absent.
- Metric catalog validation passes at 130.
- Compatibility matrix/golden configs/Alembic `0017` pins unchanged.
- Import-linter, Ruff, and mypy pass.
- Full default pytest passes.

### Acceptance Criteria

- A generational matrix cell executes with the new factors and emits the new metric.
- Legacy gates, schema pins, command/observer counts, and default writers are unchanged.
- False comparability claims fail closed.
- Count pins are consistent everywhere.

### Verification

- The commands in steps 5-7.
- Expected: all pass; no skipped unit tests; integration/compose remain opt-in.

## Phase Risks and Mitigations

- Risk: real BM runs are slow or cognitively sparse at eight ticks.
  Mitigation: assert structural generation admission and metric evidence, not social outcomes; keep the horizon at the minimum that yields entrants.
- Risk: matrix cell execution requires archive context unexpectedly.
  Mitigation: use the existing `GenerationalExecutionContext` + `plain-generational` recipe pattern from BL.
- Risk: count sweep misses a pin.
  Mitigation: run `rg -l "METRIC_FAMILY_COUNT" tests/unit` and the full default suite.
- Risk: a new module violates import boundaries.
  Mitigation: dedicated architecture test plus `lint-imports`.
- Risk: non-passthrough distributions make a false comparability claim.
  Mitigation: explicit negative tests and stable error codes.

## Phase Completion Checklist

- Tasks 10-11 acceptance criteria are met.
- Real BM and matrix execution both produce the new metric.
- V1/V2, architecture, lint, typing, and count gates pass.
- `index.md` checkboxes are updated immediately after verified completion.
