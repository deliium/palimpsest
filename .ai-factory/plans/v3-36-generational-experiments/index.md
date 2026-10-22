<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V3-36 Generational Experiments

Mode: ultra
Canonical stem: `v3-36-generational-experiments`
Branch: `main` (no branch creation)
Created: 2026-10-22
Planning baseline: `735884178aeba5054733552324994d89c354c888`
Status: implementation-ready; no implementation performed

## Original Request

v3-36 generational experiments Plan naming requirement: Use the canonical `v3-` prefix. Suggested stem: v3-36-generational-experiments Extend experiment configuration for population-level comparisons. Support variables such as: lifespan learning model teaching frequency record availability memory architecture innovation rate migration resource scarcity population size institution support cognitive architecture Support cohort/generation comparisons. Example experiments: oral transmission vs durable records short lifespan vs long lifespan isolated groups vs connected groups high teaching vs low teaching reconstructive memory vs reference memory Ensure treatment/control worlds can share comparable initial conditions.

## Settings

- Testing: yes; add focused unit and architecture coverage and preserve existing coverage.
- Logging: verbose metadata-only DEBUG for construction/application/assembly plus bounded INFO lifecycle events; no prompts, payloads, memories, or secrets.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 12.
- Git: enabled; base `main`; `create_branches=false`; do not create or switch branches/worktrees; skip push prompt after a later commit.
- Workflow: slug plan ID; verification mode normal; artifact/UI language English; keep English technical terms.
- Execution: planning only; run no application implementation, migration, or test execution in this invocation.
- Research: no research artifact or marked research bundle exists; no Research Context applies.

## Roadmap Linkage

Milestone: "M7 — V3 Generational Civilization"
Rationale: Add reproducible population-level experiment comparisons on the owned generational runner seam without acquiring new simulation authority, schema versions, or institutional-economy ownership.

This plan deepens experiment composition and detached analysis around the completed `v3-35-generational-runner` seam. It does not own `institutional_economy`, does not add `runner-config-v56`, does not close M7, and does not rewrite roadmap counts.

## Requirements Reconciliation

Authority: applicable `AGENTS.md` and project rules constrain all work. `.ai-factory/ARCHITECTURE.md` owns trust boundaries and versioned extension rules; `.ai-factory/RULES.md` owns determinism and import axioms; `src/experiments/models.py` owns paired-condition comparability; `docs/experiments.md` and `src/experiments/matrix_models.py` own matrix axes and schema finalize; `docs/generational-runner.md` and the completed `v3-35-generational-runner` bundle own generation/cohort semantics; the original request defines the comparison variables and examples. No unresolved material requirement conflict remains.

| Decision / supported behavior | Source path and section | Verification evidence |
| --- | --- | --- |
| Comparisons are experiment composition over an existing valid `runner-config-v55`, not a new runner schema | `.ai-factory/ARCHITECTURE.md` — Versioned Extension Contract; `src/simulation/runner_models.py` — v55 gates | Tasks 4–6 v55 roundtrip and no-default-writer-change tests. |
| Every paired arm shares seed, stochastic identity, world layout, founder roster, stop horizon, generation schedule, and initialization | `src/experiments/models.py` — `ExperimentDefinition.__post_init__`; original request — comparable initial conditions | Task 4 invariant tests; Tasks 5 and 10 real BM execution. |
| Only declared treatment axes differ; resource scarcity may change only resource quantities; population size may change only lifecycle capacity/entry rate | `src/experiments/models.py` — `_scenario_layout`; original request — variable list | Task 4 allowed/forbidden diff tests. |
| Axis levels are closed named presets; no arbitrary numeric matrix payload is introduced | `src/experiments/matrix_models.py` — `MatrixFactorLevel` and `LOCKED_FACTOR_LEVEL_IDS` | Tasks 1, 6 level-table and serialization tests. |
| Generational matrix factors require a v55 base and must not mutate `schema_version` | `src/experiments/matrix_factors.py` — `apply_factor_level`; `src/experiments/matrix_schema.py` — v55 first branch | Task 6 `generational_base_required` and schema-preservation tests. |
| Incompatible factor combinations fail closed instead of silently overriding another axis | `src/experiments/matrix_expand.py` — ordered level application; original request — independent variables | Task 6 `incompatible_factor_combination` tests. |
| Cohort/generation measurement is detached, scalar, and analysis-only; it never feeds cognition or admission | `.ai-factory/ARCHITECTURE.md` — Key Principles; `src/analysis/` analysis isolation | Tasks 8–9 metric and architecture tests. |
| Generation labels mean admitted generation, not age, kinship depth, or community membership | `docs/generational-runner.md` — generation/cohort semantics; `src/simulation/demographic_policy.py` — interval policy | Tasks 8–10 metric and real-run assertions. |
| Existing v1–v54 behavior, default writer `runner-config-v4`, result v2, commands 43, observer types 73, Alembic `0017`, and legacy experiments remain unchanged | `.ai-factory/ARCHITECTURE.md` — baseline; `src/simulation/runner_models.py` — version sets | Task 11 regression gates. |
| Exact cross-cell reproduction is not claimed for run-ID-scoped channels; comparability requires passthrough lifespan/initialization and deterministic schedules | `src/simulation/generational_seeds.py`; `src/simulation/new_agent_initialization.py`; `src/simulation/runner_models.py` — lifespan distribution | Task 4 passthrough gate and Task 11 seed-scope documentation test. |

### Supported Combinations

| ID | Accepted input / validation | Persisted state | Output / transition | Side effects / invariants | Verification scenario |
| --- | --- | --- | --- | --- | --- |
| C1 | New comparison spec over a valid v55 base; control and treatment levels valid for one closed axis | No new config schema; two conditions carry the exact v55 payload plus the declared axis change | `ExperimentDefinition` with control/treatment arms | Same seed, stochastic identity, scenario layout, founder roster, max ticks, generation schedule, initialization | Tasks 1, 4–5 model and scenario tests. |
| C2 | BM experiment builder with the five request examples | Ten v55 conditions in five paired groups | `generational_comparison@1` registered off the V1 gate | Oral/records, short/long lifespan, isolated/connected, low/high teaching, reference/reconstructive memory | Tasks 5, 10 build and execution tests. |
| C3 | Matrix with a v55 embedded base and new generational factor levels | Existing `experiment-matrix-v1` cells; no schema bump | v55 cells with control/treatment roles | New factors cannot change schema, seed, scenario, stochastic identity, or generation schedule | Tasks 6–7 expansion and serialization tests. |
| C4 | Matrix combo such as `learning_model=practice_only` plus `teaching_frequency=high`, or teaching/innovation without skill learning | No cell created | `MatrixValidationError("incompatible_factor_combination")` | Fail closed before `ExperimentDefinition` construction | Task 6 invalid-combination tests. |
| C5 | Generational run result with `PopulationProgress` | Detached `MetricComputationInputs.generational_progress` | New `generational_cohort_comparison@1` metric document | Totals, generation rows, cohort rows, survival shares, explicit zero/absent policy | Tasks 8–9 metric and collector tests. |
| C6 | Non-generational run or legacy result | No new input; no new family emitted | Existing metric bundle unchanged | No fabricated zeros; no v1/v2 behavior change | Task 9 absence and Task 11 regression tests. |
| C7 | Comparison config with a non-passthrough lifespan distribution, non-`none` initialization distribution, or mismatched schedule | Rejected before execution | Stable comparability error code | Prevents false “same initial conditions” claims across run-ID-scoped draws | Task 4 and Task 11 negative tests. |

## Architecture and Decisions

### Version and ownership budget

- Reuse `runner-config-v55` and `runner-result-v3`; do not add v56, a result v4, commands, events, observer semantics, SQL migrations, metric HTTP routes, or capability flags.
- Keep default config write `runner-config-v4`, default result write `runner-result-v2`, commands 43, observer semantic types 73, Alembic `0017`, and all current replay/codec pairs unchanged.
- New experiment code lives in `experiments`; new metric families live in `analysis`; `simulation`, `world`, `agents`, `memory`, `social`, `llm`, `api`, and `persistence` receive no new behavior.
- The comparison variables are experiment presets over existing owners: lifespan/population width use `PopulationLifecycleSpec`; learning/teaching/innovation use existing `AgentCognitionSpec` modes and rates; records use `cultural_feature_provenance` + `durable_records`; migration uses `multi_polity_migration` + `regions_migration`; institution support uses institution-concept and office-succession modes; memory uses `MemoryMode`; cognitive architecture composes registered architecture modes onto the v55 base without changing schema.
- `institutional_economy` remains unowned; no comparison axis creates exchange, currency, law, or polity authority.

### Comparison model

A comparison is a pair of named levels over one closed axis, applied to one common base. The generic builder builds each pair independently; it does not compute a cross-product of unrelated variables. Multi-axis matrix work remains the matrix layer's responsibility.

The canonical BM experiment contains five pairs: oral transmission vs durable records, short vs long lifespan, isolated vs connected migration, low vs high teaching, and reference vs reconstructive memory. Additional axes are available to later catalog/matrix authors but are not silently added as extra BM arms.

### Comparable initial conditions

Every pair must preserve:

- seed and `stochastic_identity`;
- world id/revision, physical rules, locations, bodies, weather, and non-resource scenario fields; resource quantities may differ only for the scarcity axis;
- agent ids, body ids, names, initial goals, and ordering;
- `RunnerStopPolicy` including `max_ticks`;
- demographic policy id, interval, generation length, entries per interval, spawn locations, and `GenerationalRunSpec`;
- `NewAgentInitializationSpec` and `PopulationLifecycleSpec.lifespan_distribution` as passthrough/fixed.

Lifespan, capacity, learning, teaching, records, migration, institution, memory, and architecture are allowed treatment fields. Founder bodies and initial locations are never changed by an axis.

### Matrix extension

New locked factors delegate to the same axis applicators as the scenario builder. They are valid only when `config.generational_run is not None` and `config.schema_version == runner-config-v55`. The final compatibility gate rejects combinations whose effective modes contradict one another. `matrix_schema.finalize_matrix_cell_config` already selects v55 first when `generational_run` is present; this plan verifies that behavior instead of adding a branch.

The new scarcity factor is named `generational_resource_scarcity` and scales resource `quantity`, `maximum_quantity`, and `regeneration_per_tick` proportionally. The legacy `resource_scarcity` factor keeps its existing fixed-layout contract and is not repurposed.

### Metrics and comparison semantics

`generational_cohort_comparison@1` is one new analysis-only metric family. It reports objective counts from the finalized `PopulationProgress`:

- totals (`admitted`, `living`, `dead`, generation/cohort count, boundary tick);
- dynamic `generation:<n>:*` and `cohort:<id>:*` scalar keys;
- survival shares derived from admitted/living counts;
- generation span and post-founder admission/living shares;
- cohort/generation alignment violations, expected zero for valid progress.

No nested maps are stored in `MetricDocument`; dynamic scalar keys follow the existing `regional_population@1` pattern. Cross-arm comparison uses the existing per-condition `matrix-metric-summary-v1` grouping by condition and `group_role`. Paired confidence intervals and effect-size documents are explicitly deferred; the plan does not pretend a new statistical layer exists.

### Compatibility and failure behavior

- A comparison axis applied to the wrong level raises a stable `GenerationalComparisonError` with a reason code.
- A matrix factor applied without a v55 base raises `MatrixValidationError("generational_base_required")`.
- A contradictory matrix combination raises `MatrixValidationError("incompatible_factor_combination")` before finalize.
- A comparability violation raises `ValueError` with stable codes such as `comparison_seed_mismatch`, `comparison_scenario_mismatch`, `comparison_schedule_mismatch`, or `comparison_initialization_not_passthrough`.
- Non-generational runs do not emit the new metric family and never receive fabricated counts.

## Phase Index

1. [Phase 1: Comparison contracts and axis engine](phase-01-contracts-and-axes.md) — Tasks 1–3
2. [Phase 2: Scenario, base, and matrix composition](phase-02-scenario-and-matrix.md) — Tasks 4–7
3. [Phase 3: Generational cohort analysis](phase-03-cohort-analysis.md) — Tasks 8–9
4. [Phase 4: Real-run and regression verification](phase-04-verification.md) — Tasks 10–11
5. [Phase 5: Documentation and release gates](phase-05-docs-and-release.md) — Task 12

## Cross-Phase Dependencies

- Task 1 is independent; Tasks 2–3 depend on 1.
- Task 4 depends on 1–3; Task 5 depends on 4; Task 6 depends on 2–4; Task 7 depends on 5–6.
- Task 8 depends on 1 and the finalized v55 result contract; Task 9 depends on 8 and Task 5.
- Task 10 depends on 5, 8–9; Task 11 depends on 6–10; Task 12 depends on all prior tasks.
- Execute phases in order. Shared edits to `generational_axes.py`, `matrix_factors.py`, `specifications.py`, and `metric_service.py` are sequential, not parallel agent work.

## Tasks

### Phase 1: Contracts and axes

- [x] Task 1: Add closed comparison axis and level contracts ([details](phase-01-contracts-and-axes.md#task-1-add-closed-comparison-axis-and-level-contracts)).
- [x] Task 2: Implement population, lifespan, records, migration, and scarcity axes ([details](phase-01-contracts-and-axes.md#task-2-implement-population-lifespan-records-migration-and-scarcity-axes)) (depends on 1).
- [x] Task 3: Implement cognition, teaching, innovation, institution, and architecture axes ([details](phase-01-contracts-and-axes.md#task-3-implement-cognition-teaching-innovation-institution-and-architecture-axes)) (depends on 1).

### Phase 2: Scenario and matrix composition

- [x] Task 4: Add the canonical generational comparison base and comparability gate ([details](phase-02-scenario-and-matrix.md#task-4-add-the-canonical-generational-comparison-base-and-comparability-gate)) (depends on 1–3).
- [x] Task 5: Add the generic pair builder and BM experiment ([details](phase-02-scenario-and-matrix.md#task-5-add-the-generic-pair-builder-and-bm-experiment)) (depends on 4).
- [x] Task 6: Add generational matrix factors and compatibility validation ([details](phase-02-scenario-and-matrix.md#task-6-add-generational-matrix-factors-and-compatibility-validation)) (depends on 2–4).
- [x] Task 7: Add matrix expansion, serialization, and schema integration tests ([details](phase-02-scenario-and-matrix.md#task-7-add-matrix-expansion-serialization-and-schema-integration-tests)) (depends on 5–6).

### Phase 3: Generational cohort analysis

- [x] Task 8: Add the generational cohort comparison metric family ([details](phase-03-cohort-analysis.md#task-8-add-the-generational-cohort-comparison-metric-family)) (depends on 1; v55 result contract).
- [x] Task 9: Wire generational progress into metric assembly and collectors ([details](phase-03-cohort-analysis.md#task-9-wire-generational-progress-into-metric-assembly-and-collectors)) (depends on 5 and 8).

### Phase 4: Real-run and regression verification

- [x] Task 10: Execute the BM real-world comparison experiment ([details](phase-04-verification.md#task-10-execute-the-bm-real-world-comparison-experiment)) (depends on 5, 8–9).
- [x] Task 11: Prove matrix cells, legacy gates, and seed-scope boundaries ([details](phase-04-verification.md#task-11-prove-matrix-cells-legacy-gates-and-seed-scope-boundaries)) (depends on 6–10).

### Phase 5: Documentation and release gates

- [x] Task 12: Document generational experiments and complete the docs checkpoint ([details](phase-05-docs-and-release.md#task-12-document-generational-experiments-and-complete-the-docs-checkpoint)) (depends on 1–11).

## Commit Plan

- Commit 1, after Tasks 1–3: `feat(experiments): define generational comparison axes`
- Commit 2, after Tasks 4–7: `feat(experiments): compose generational comparison matrices`
- Commit 3, after Tasks 8–9: `feat(analysis): measure generational cohort outcomes`
- Commit 4, after Tasks 10–11: `test(experiments): verify generational comparisons`
- Commit 5, after Task 12: `docs(experiments): document generational experiment contracts`

## Risks, Gaps, and Explicit Deferrals

- **Matrix coupling:** teaching/innovation axes require skill learning; the final compatibility gate rejects contradictory combinations instead of silently overriding a prior factor.
- **Run-ID-scoped draws:** demography, initialization, and lifespan streams retain durable run-ID scope. Comparability is guaranteed only for fixed/passthrough distributions and deterministic schedules; no arbitrary-new-RunId reproduction claim is made.
- **No paired statistical layer:** cross-arm comparison remains the existing per-condition metric summary. Paired confidence intervals, effect sizes, and significance tests are out of scope.
- **No per-cohort treatment:** every axis applies to the whole run or all agents. Comparing treated and control cohorts inside one run is not introduced and would require a later simulation authority change.
- **Short-horizon evidence:** BM tests may not observe durable records or teaching at very short horizons; tests assert configuration/behavior contracts and use a horizon long enough to produce at least two generations, not a guaranteed social outcome.
- **Count sweep:** adding one metric family requires updating every `METRIC_FAMILY_COUNT` pin and current docs. Historical roadmap counts are not rewritten.
- **Stale pre-existing v55 docs:** Task 12 updates current pins and v55 references it touches, but does not rewrite historical plans or roadmap history.
- **No new capability or migration:** no `institutional_economy`, no v56, no Alembic revision, no API route, and no Godot/research-UI change.

## Definition of Done

- All 12 tasks verified with the listed tests and matching implementation behavior.
- A generic comparison builder produces paired v55 conditions that pass the comparability gate; BM exposes five paired examples off the V1 gate.
- All requested variables are supported through closed named axis levels; matrix factors reuse the same implementation and preserve v55 without a schema bump.
- Incompatible matrix combinations and non-v55 bases fail closed with stable reason codes.
- `generational_cohort_comparison@1` reports objective generation/cohort totals, shares, and alignment from real `PopulationProgress`, remains absent for non-generational runs, and never feeds cognition.
- At least one real AY-derived BM run admits multiple generations and produces the new metric; no synthetic-only proof is accepted.
- V1 regression, V2 scientific invariants, architecture/import rules, Ruff, mypy, and metric catalog validation pass with coverage retained.
- Mandatory `$aif-docs` checkpoint completes; current code/docs pins are 130 metric families, while historical roadmap counts remain historical. No default writer, command count, observer count, or migration pin changes.
- No unrelated plans, requirements, roadmap, architecture, or application files are modified by this planning invocation.

## Execution Handoff

Read this index, then the complete linked phase before implementing its tasks. Checkboxes exist only here. Preserve all phase files; do not flatten this bundle into a single plan. Use an explicit plan path because branch creation is disabled and other plans coexist:

`$aif-implement @.ai-factory/plans/v3-36-generational-experiments/index.md`
