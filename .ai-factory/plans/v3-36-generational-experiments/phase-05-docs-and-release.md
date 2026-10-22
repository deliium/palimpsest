# Phase 5: Documentation and release gates

Plan: [index.md](index.md)
Task: 12
Depends on: Tasks 1-11

## Objective

Document the comparison contract, the five BM examples, every matrix axis, the comparability gate, and the new metric; update current count pins; and complete the mandatory `$aif-docs` checkpoint without rewriting historical plans or roadmap history.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `docs/experiments.md` | catalog (11), matrix axes (72-95), sidecars/CLI (110-125), BL section (440-457) | Primary experiment and matrix documentation. |
| `docs/analysis-metrics.md` | header (5), catalog (41), family sections (181+) | Metric family documentation and stale counts. |
| `docs/generational-runner.md` | generation/cohort (33-49), stopping (71), archives (103), CLI (164) | Existing v55 contract that the new metric must not contradict. |
| `docs/configuration.md` | generational runs (284) | Configuration version/gate documentation. |
| `docs/development.md` | pins and verification commands (37-52, 335) | Test commands and count pins. |
| `docs/architecture.md` | analysis/catalog mention (44), V3-34 counts (445-447) | Current-pin and boundary documentation. |
| `README.md` | documentation index (58-61), CLI (48) | Landing-page discovery. |
| `.ai-factory/ARCHITECTURE.md` | current baseline table (177-193), V3 seams | Current pins and ownership record. |
| `.ai-factory/DESCRIPTION.md` | core features (18), V3 state (39-106) | Current feature and schema description; it currently stops at V3-34/v54. |
| `.ai-factory/ROADMAP.md` | M7 section | Roadmap history; this task must not rewrite counts or close M7. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `docs/experiments.md` | modify | Add BM, axis/level table, matrix factor table, comparability rules, metric linkage. |
| `docs/analysis-metrics.md` | modify | Add `generational_cohort_comparison@1`, formulas/keys, count 130, fix touched stale counts. |
| `docs/generational-runner.md` | modify | Document the experiment/metric composition without conflating generation, cohort, kinship, or community. |
| `docs/configuration.md` | modify | State that generational experiments reuse `runner-config-v55`; list preset meanings and no-v56 decision. |
| `docs/simulation-runner.md` | modify | Correct the stale decodable-range statement to include v55 and the generational result v3; no new schema. |
| `docs/development.md` | modify | Update metric pin and add focused verification commands. |
| `docs/architecture.md` | modify | Update current family count and restate the analysis-only boundary. |
| `README.md` | modify if needed | Add the generational experiments section/link to the documentation index. |
| `.ai-factory/ARCHITECTURE.md` | modify | Update current baseline to 130 families, keep latest runner v55, and describe v3-36 as experiment/analysis-only. |
| `.ai-factory/DESCRIPTION.md` | modify | Add V3-36 and correct the stale v3-35/v55 omission in current-feature prose. |
| `.ai-factory/ROADMAP.md` | do not modify | Historical roadmap counts and milestone ownership stay with the roadmap owner. |

## Task 12: Document generational experiments and complete the docs checkpoint

### Intent

Make the new surface discoverable and prevent future implementers from inventing a v56, treating cohorts as communities, or claiming paired statistical effects the code does not provide.

### Implementation Steps

1. Update `docs/experiments.md`:
   - Add a `## Experiment BM — generational comparison (`generational_comparison@1`)` section near the BL section.
   - List the ten condition ids and five pairs, exact control/treatment axis levels, default seed/horizon (`seed=23`, `max_ticks=12`, minimum 8), and that BM is off the V1 A–E gate.
   - State that each pair shares seed, stochastic identity, world layout, founder roster, stop horizon, generation schedule, and initialization.
   - Add the closed axis/level table for all eleven variables and the exact preset meanings from Phase 1.
   - Add the matrix factor table with the ten new factors plus the existing `memory_type` and `resource_scarcity` note. Explain that `generational_resource_scarcity` is the proportional generational factor and legacy `resource_scarcity` keeps its fixed-layout contract.
   - Document `generational_base_required` and `incompatible_factor_combination`.
   - Correct the stale matrix-finalize sentence that still says v23 (or an older version) is the highest accepted finalize; state that v55 is selected first for generational cells.
   - State that BM does not guarantee a record, teaching act, migration, or institution outcome; it guarantees configuration, generations, and measurement.
2. Update `docs/analysis-metrics.md`:
   - Add `generational_cohort_comparison@1` with population, denominator, formulas, generation/cohort dynamic key grammar, zero/extinction policy, absent policy, and provenance.
   - State that the family is analysis-only and never feeds cognition.
   - Update the header current-pin count from **109** to **130** and fix touched stale counts (the file also contains older “nineteen”/“109” prose); do not rewrite historical plan counts.
3. Update `docs/generational-runner.md`:
   - Add a short “Experiment comparisons” subsection linking to BM.
   - State that `generational_cohort_comparison@1` folds finalized `PopulationProgress` and that cohort ids are admission cohorts, not observed activity cohorts.
   - Restate that generation means admitted generation label, not age/kinship depth/community.
   - Do not claim paired effect sizes; point to `matrix-metric-summary-v1`.
4. Update `docs/configuration.md`:
   - State that v3-36 adds no runner schema; comparisons reuse `runner-config-v55` and `runner-result-v3`.
   - List the closed axis presets and the fixed/passthrough comparability requirements.
   - State explicitly that no `runner-config-v56` exists.
5. Update `docs/development.md`:
   - Update the metric family pin from 129 to 130.
   - Add focused commands:
     ```bash
     uv run --frozen --python 3.12.14 pytest tests/unit/test_experiment_bm.py tests/unit/test_experiment_bm_execution.py tests/unit/test_generational_matrix_factors.py tests/unit/test_generational_cohort_metrics.py tests/unit/test_generational_cohort_collectors.py -q
     uv run --frozen --python 3.12.14 pytest tests/unit/test_generational_matrix_execution.py tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py -q
     ```
   - Keep the existing full-suite, Ruff, mypy, and import-linter commands.
6. Update `docs/architecture.md`:
   - Change the current baseline heading from V3-34 to V3-36, the current metric family count to 130, and mention the new analysis-only family.
   - Keep the default writer, command count, observer count, replay/codec, and Alembic pins unchanged.
7. Update `/README.md` only if its documentation index or feature list needs the new experiment/metric references. Preserve the existing structure and do not add a new top-level section unless it improves discovery.
8. Update `.ai-factory/ARCHITECTURE.md`:
   - Rename the current baseline heading from V3-34 to V3-36; metric families `130`; latest feature runner remains `runner-config-v55`; default runner write remains `runner-config-v4`.
   - Add a short V3-36 seam paragraph: experiment-only comparison axes, no new simulation authority, no new flag, no new schema.
   - Keep historical accepted-version language intact.
9. Update `docs/simulation-runner.md`:
   - Replace the stale “`runner-config-v1`…`v46` remain decodable” statement with the current accepted range through v55.
   - Keep the existing v55/result-v3 description and do not claim a v56.
10. Update `.ai-factory/DESCRIPTION.md`:
   - Add V3-36 to the V3 state/current-feature prose.
   - Correct the pre-existing omission of v3-35/`runner-config-v55` because current documentation otherwise contradicts code.
   - State that the comparison variables are experiment presets and that `generational_cohort_comparison@1` raises the catalog from 129 to 130.
   - Do not claim a new capability flag, schema, event, command, migration, or institutional-economy ownership.
11. Run the mandatory `$aif-docs` checkpoint after the manual edits:
    - Invoke `$aif-docs` and reconcile its output with the edits above.
    - Do not let the docs checkpoint rewrite `.ai-factory/ROADMAP.md`, historical plans, or unrelated pages.
    - Preserve exact commands, paths, config keys, schema ids, and counts.
12. Verify current-count consistency:
    - `rg -n "129|109" docs .ai-factory README.md` (inspect every match; historical prose may stay).
    - `rg -n "METRIC_FAMILY_COUNT" src tests`.
    - Confirm commands 43, observer semantic types 73, Alembic `0017`, `/v1`, `observer-protocol-v1`, default v4, result v2, and latest v55 are unchanged.
13. Do not create a migration, changelog, release note, or report task. The documentation checkpoint is the final deliverable.

### Required Documentation Contracts

- BM section must list exactly the five example pairs and ten condition ids.
- Axis table must list exact level ids and state which variables are scenario/matrix-supported.
- Metric section must use the exact family string `generational_cohort_comparison@1`.
- Comparability section must name the fixed/passthrough requirements and the run-ID-scoped limitation.
- No doc may claim paired significance, effect sizes, per-cohort treatment, new simulation authority, or a new schema.
- Current family count must be 130 everywhere it is a current pin.

### Error Handling and Logging

- Documentation has no runtime logging.
- If `$aif-docs` proposes a conflicting current count, the code and executable tests win; record the conflict in the implementation notes and fix the doc, not the code.
- Do not add payload examples, secrets, prompts, or agent data to docs.

### Verification

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_metric_specifications.py tests/unit/test_experiment_bm.py tests/unit/test_generational_cohort_metrics.py -q
uv run --frozen --python 3.12.14 pytest tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py -q
uv run --frozen --python 3.12.14 ruff check src tests
uv run --frozen --python 3.12.14 mypy src tests
uv run --frozen --python 3.12.14 lint-imports
```

Expected:

- Metric catalog validates at 130.
- BM docs match the executable condition ids and presets.
- V1/V2 gates remain green.
- Ruff, mypy, and import-linter pass.
- No current pin claims a new schema, command, observer type, or migration.

### Acceptance Criteria

- A new contributor can find and reproduce BM from `docs/experiments.md`.
- The new metric is documented with its zero/absent policy and analysis-only boundary.
- `.ai-factory` current pins and the docs agree at 130 families and v55/v4 defaults.
- The `$aif-docs` checkpoint is complete and no historical roadmap/plan content was rewritten.
- No report, changelog, or release-note artifact is required.

## Phase Risks and Mitigations

- Risk: docs conflict with existing stale v55/v54 prose.
  Mitigation: update only current pins and the touched V3-36/V3-35 passages; leave historical roadmap counts labeled historical.
- Risk: `$aif-docs` rewrites unrelated pages.
  Mitigation: constrain the checkpoint to experiments, metrics, configuration, generational runner, development, architecture, README, and current `.ai-factory` pins.
- Risk: count 130 is applied to a historical 129 reference.
  Mitigation: inspect every `129` match and update only current catalog pins.
- Risk: docs imply causal or statistical effects.
  Mitigation: explicit “descriptive/detached” and “no paired effect layer” language.

## Phase Completion Checklist

- Task 12 acceptance criteria are met.
- Current docs and `.ai-factory` pins agree with the executable code.
- `$aif-docs` checkpoint completed.
- `index.md` checkbox is updated immediately after verified completion.
- All 12 index tasks are checked and the bundle remains intact.
