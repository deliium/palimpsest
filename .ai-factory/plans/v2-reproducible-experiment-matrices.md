# Implementation Plan: Reproducible Experiment Matrices

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-03
Improved: 2026-10-03 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete milestone; this plan adds research batch orchestration over already-owned modes/flags and does not claim `multi_hop_testimony_tracking`.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M6 — Remaining V2 Capability Flags
INFO [aif-plan] mode=ultra treated as full (richer plan); remaining args describe the feature
INFO [aif-plan] resolved plan file: .ai-factory/plans/v2-reproducible-experiment-matrices.md (format=slug)
INFO [aif-plan] plan name prefix v2- applied per user request; git.create_branches=false so stem is description slug
INFO [aif-improve] applied refinement: schema finalize, group_role rules, crash resume, closed factor levels, drop optional DB Task 8

## Compatibility contract

This plan extends trusted experiment orchestration from single-factor catalog arms to configuration-driven multi-factor experiment matrices. It must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants intact. `WorldEngine` remains the only objective mutation authority. Cognition still receives immutable per-agent `Observation` / `Perspective` only. Matrix orchestration never feeds collectors, aggregates, or treatment labels back into cognition, memory, prompts, or action selection.
2. Capability flags stay opt-in and default-off. Do **not** add a new `V2CapabilityFlags` slot. Do **not** own `multi_hop_testimony_tracking`. Matrix factor values may enable already-owned flags (e.g. `advanced_social_inference` for ToM) only through normal runner config expansion; unowned flags still fail closed.
3. V1 regression gate stays green under flags-off and tracing-off. Catalog A–E and the reference scenario keep current trajectories. Matrix batch runs, CLI, and multi-factor expansions stay **off** `tests/unit/test_v1_regression_gate.py`.
4. **No runner-config schema bump required for matrices.** Default write surface and accepted runner schema sets stay as today. Matrix documents are a new experiment-layer schema (`experiment-matrix-v1`) that expands into existing `experiment-definition-v1` + `SimulationRunnerConfig` documents. Exact key-set discipline on runner JSON is unchanged. Factor combinations select the existing runner schema version via a locked highest-wins finalize step (v4–v22 as already defined).
5. No scripted emergence. Factor ids and control/treatment labels are researcher metadata, not friend/enemy/leader/culture roles or milestone scripts.
6. No LLM → world shortcuts. Batch runners only invoke `SimulationRunner` / existing experiment collectors after authoritative commit.
7. Experiments stay reproducible. All cells in a matrix share the declared base scenario layout and stochastic-identity policy; seeds and factor levels are explicit. Prefer deterministic fakes / stubs. Aggregation is analysis-only and post-run.
8. Optional cognition tracing stays outside the objective fold. Matrix resume validity must not depend on tracing being on.
9. **No HTTP coupling.** Matrix expansion, scheduling, resume, and aggregation must not import `api`, call FastAPI routes, or require a running research API. Composition for CLI / internal runner lives outside `experiments` (new thin composition package) so import-linter remains satisfied (`experiments` still forbids `api` / `infrastructure` / `persistence`). `research_runner` resolves `package_version` via `importlib.metadata.version("palimpsest")` — never via `api.presentation_static`.

## Goal

Extend the experimental framework from individual / paired catalog runs to **reproducible experiment matrices** suitable for automated research.

Support Cartesian (and constrained) combinations of axes such as:

| Axis id | Maps to today |
| --- | --- |
| `memory_type` | `AgentCognitionSpec.memory_mode` (`REFERENCE` / `RECONSTRUCTIVE` / `RECONSTRUCTIVE_V2`) |
| `mortality` | `SimulationRunnerConfig.mortality_mode` |
| `imagination` | `AgentCognitionSpec.imagination_mode` (+ prospective only when explicitly listed as a separate factor level, not silently) |
| `reflection` | `AgentCognitionSpec.reflection_mode` |
| `tom` | owned flag `advanced_social_inference` (fail-closed if unowned flags appear) |
| `resource_scarcity` | scenario resource quantities / locked scarce-vs-abundant layout helpers (layout identity rules already in `ExperimentDefinition`) |
| `seasonality` | presence/absence of `EnvironmentalDynamicsSpec` (reuse Experiment U helpers) |
| `cognitive_budget` | `CognitiveBudgetMode` + locked low/high presets from Experiment AD |

Provide configuration-driven:

- parameter grids
- repeated seeds
- control/treatment groups
- run counts
- concurrency limits
- failure recovery
- run manifests
- result aggregation

Preserve exact configuration and code/schema version identity per run. Support CLI or internal runner execution. Ensure large batches can resume without rerunning completed valid runs.

```text
ExperimentMatrixSpec (experiment-matrix-v1)
  → apply factor levels (modes/flags/resources only)
  → finalize_matrix_cell_config (highest-wins schema_version)
  → expand factors × seeds × replicates
  → ExperimentDefinition (experiment-definition-v1) + MatrixManifest
  → MatrixBatchRunner (concurrency, resume, recovery)
  → per-cell SimulationRunner + collectors
  → MatrixAggregateDocument (analysis-only)
```

## Locked scope decisions

1. **Matrix schema is additive.** Keep `experiment-definition-v1` as the expanded arm document. Add `EXPERIMENT_MATRIX_SCHEMA_VERSION = "experiment-matrix-v1"`. Do not silently reinterpret old definition rows as matrices.
2. **Catalog A–AD stay.** Existing single-factor builders remain the source of factor applicators and scenario helpers. Matrices compose those applicators; they do not replace the catalog.
3. **Process-local concurrency only.** `asyncio.Semaphore` (or equivalent) inside one process. No Celery/Kafka/distributed workers in this plan.
4. **Filesystem manifests are primary.** Default durable resume store is a versioned JSON manifest directory under a researcher-chosen root. SQLAlchemy / `ExperimentRecordRepository` matrix membership is **out of scope** for this plan (follow-up if needed).
5. **Composition package name:** `research_runner` under `src/research_runner/`. It may import `experiments`, `simulation`, `persistence`, `infrastructure`, and `analysis`. It must not import `api` or start an HTTP server. `experiments` remains free of `api` / `infrastructure` / `persistence`.
6. **CLI entry:** `[project.scripts] palimpsest-matrix = research_runner.cli:main` plus `python -m research_runner`. No FastAPI dependency for the happy path.
7. **Fix assignment materialization.** `materialize_assignments` today rebuilds a partial `SimulationRunnerConfig` and drops V2 fields (`environmental_dynamics`, `artifacts_enabled`, `cognition_trace`, `experiment`, and any future fields). Switch to `dataclasses.replace(condition.runner_config, seed=seed)` so matrix cells retain full cognition/flags/dynamics/budget state.
8. **Validity for resume** requires matching: matrix fingerprint, cell factor fingerprint, runner config fingerprint, schema versions, and recorded code/version identity. Mismatch → fail closed (do not silently reuse).
9. **No Alembic revision** in this plan. Filesystem manifests carry matrix/cell/version identity.
10. **Aggregation is read-only.** Emit canonical metric summaries / counts / group contrasts; never write aggregates into agent-visible state.
11. **Expand requires ≥2 conditions.** After constraints, fail closed if fewer than two factor combinations remain (`ExperimentDefinition` requires ≥2 arms). Degenerate single-cell grids are not supported via `ExperimentDefinition` in this plan.

## Design Decisions (locked)

### Factor model and closed level ids

```text
MatrixFactorId (StrEnum): memory_type | mortality | imagination | reflection
  | tom | resource_scarcity | seasonality | cognitive_budget

MatrixFactorLevel
  level_id, label_code, group_role (control|treatment|neutral)
  → applicator clones SimulationRunnerConfig (modes/flags/resources only; no schema pick)

ExperimentMatrixSpec
  matrix_id, schema_version=experiment-matrix-v1
  base: SimulationRunnerConfig (embedded canonical JSON) or catalog base builder id + params
  factors: ordered MatrixFactor[]
  seed_matrix: ExperimentSeedMatrix (reuse)
  constraints: exclude_combos only (see below)
  execution: max_concurrency (default 1), retry_policy, stop_on_first_error
  groups: optional named overlays that override derived cell group_role
```

**Locked level tables (v1 registry):**

| Factor | Level ids | Effect |
| --- | --- | --- |
| `memory_type` | `reference`, `reconstructive`, `reconstructive_v2` | `MemoryMode` |
| `mortality` | `disabled`, `enabled` | `MortalityMode` |
| `imagination` | `disabled`, `enabled` | `ImaginationMode` only (no silent prospective/counterfactual) |
| `reflection` | `disabled`, `deterministic` | `ReflectionMode` |
| `tom` | `off`, `on` | `advanced_social_inference` False/True only |
| `resource_scarcity` | `scarce`, `abundant` | scenario resource quantities via territorial/scarce helpers; layout identity preserved |
| `seasonality` | `off`, `on` | clear / set `EnvironmentalDynamicsSpec` via Experiment U helpers |
| `cognitive_budget` | `disabled`, `low_cost`, `high_cost` | `DISABLED` / `ENFORCED` + `low_cost_budget_limits()` / `high_cost_budget_limits()` (AD pattern via `dataclasses.replace`) |

- Expansion order: factors in declaration order (outer→inner), then seeds, then replicates.
- Condition ids: human-readable join of ordered `(factor_id, level_id)` with charset/length guard; overflow → short hash suffix.
- **Constraints (locked):** only `exclude_combos: tuple[Mapping[factor_id, level_id], ...]`. Unknown ops / unknown factor keys fail closed. No open-ended include DSL in this plan.

### Cell `group_role` composition

1. If optional named `groups` overlay matches the cell’s level tuple → use that role.
2. Else: `treatment` if any selected level is `treatment`; else `control` if any is `control`; else `neutral`.

### Schema finalize (highest-wins)

Factor applicators **must not** set `schema_version`. After all levels for a cell are applied, call `finalize_matrix_cell_config(config) -> SimulationRunnerConfig`:

Highest-wins table (first match wins):

1. any agent `cognitive_budget_mode == ENFORCED` → `runner-config-v22`
2. else any agent cultural narratives on → `runner-config-v21`
3. else any agent semantic naming on → `runner-config-v20`
4. else artifacts interpretation / artifacts active path as required by existing runner rules → `runner-config-v19` (only if matrix factors ever enable them; v1 registry does not)
5. else `environmental_dynamics is not None` → `runner-config-v14`
6. else any agent `reflection_mode != DISABLED` → `runner-config-v6`
7. else → `runner-config-v4`

Then construct/validate the config so exact-version gates (`v22_requires_cognitive_budget`, `v6_requires_reflection`, `v14` dynamics, etc.) hold. Unit-prove: reflection+budget → v22; seasonality-only → v14; memory/mortality/tom-only → v4.

### Version identity per run

Frozen `RunVersionIdentity` on every completion record (metadata only):

| Field | Source |
| --- | --- |
| `package_version` | `importlib.metadata.version("palimpsest")` in `research_runner` (not HTTP, not `api`) |
| `runner_schema_version` | expanded config |
| `experiment_schema_version` | `experiment-definition-v1` |
| `matrix_schema_version` | `experiment-matrix-v1` |
| `derivation_version` | config |
| `matrix_fingerprint` / `cell_fingerprint` / `config_fingerprint` | SHA-256 of canonical JSON |
| `code_revision` | optional injected / `PALIMPSEST_CODE_REVISION`; empty allowed; never invent wall-clock surrogate |

### Batch runner, resume, crash recovery

```text
MatrixBatchRunner.run(spec, store, deps):
  expand → cells
  write/validate MatrixManifest (fail closed on divergent rewrite)
  on open: any cell state `running` without valid completion → reset to `pending`
  for each pending/failed cell (respecting concurrency):
    if store.has_valid_completion(cell): mark skipped_valid; continue
    else run SimulationRunner; on success append result; on failure apply retry_policy
  aggregate completed cells → MatrixAggregateDocument
```

- **Default success stop set:** `max_ticks`, `all_agents_terminal`, `injected_stop`. Not success: `cancelled`, `cognition_failure`, `authority_failure`, `finalization_recovery_required`.
- **Completed valid run:** result present + fingerprints match + stop_reason in success set + `RunVersionIdentity` present.
- **Retry:** only configured transient reason codes (not config/validation errors); exhausted retries leave cell `failed` without deleting valid siblings.
- **Resume:** same `matrix_fingerprint` continues `pending` / `failed` / crash-reset cells; never rerun `skipped_valid` / valid `completed`.
- **Concurrency:** default `max_concurrency=1`. If any cell config has `persistence.durable=True`, force concurrency `1` or fail closed (`durable_requires_serial_matrix`). Each cell = fresh runner + unique `run_id`.

### Collectors and aggregation

- Matrix experiment ids do not match catalog `experiment-a…e` prefixes. Lock collector policy to `collect_for_experiment` fallback: **summary + trajectory + catalog** only (no catalog-A memory-drift path unless a later plan adds `metric_families` on the spec).
- Aggregate as `matrix-aggregate-v1` by factor levels and `group_role`; per-cell references (run ids + payload hashes) only; no observation/prompt payloads.

### Non-goals

- Distributed workers, queue brokers, Kubernetes operators.
- HTTP/WebSocket experiment control endpoints or Godot UI for matrices.
- Replacing catalog A–AD or changing V1 gate trajectories.
- Owning `multi_hop_testimony_tracking`.
- Guaranteeing bit-identity across concurrent durable DB writers beyond existing runner isolation (each cell = fresh runner / run id).
- YAML dependency (canonical JSON only, consistent with V1 runner specs).
- SQLAlchemy / `ExperimentRecordRepository` matrix membership columns (deferred follow-up).
- Full 8-way Cartesian products in CI (researcher-facing examples only; CI uses tiny fixtures).

## Commit Plan
- **Commit 1** (after tasks 1–4): `feat(experiments): add experiment-matrix contracts, factors, and expansion`
- **Commit 2** (after tasks 5–7): `feat(experiments): add resumable concurrent matrix batch runner`
- **Commit 3** (after tasks 8–9): `feat(research_runner): add CLI composition and matrix docs`
- **Commit 4** (after tasks 10–11): `test(experiments): prove matrix resume, version identity, and isolation`

## Tasks

### Phase 1: Contracts and factor expansion

- [x] Task 1: Define immutable `experiment-matrix-v1` contracts and fingerprints.
  - Deliverable: Add frozen slotted models for `MatrixFactorId` (closed StrEnum of the eight axes), level-id tokens, `MatrixFactorLevel`, `MatrixFactor`, `ExperimentMatrixSpec`, `MatrixCell`, `MatrixExecutionPolicy`, `RetryPolicy`, `GroupRole`, `MatrixCellState` (`pending` / `running` / `completed` / `failed` / `skipped_valid`), `RunVersionIdentity`, and fingerprint helpers. Default success stop set as frozen tuple of `RunnerStopReasonCode` values listed above. Strict canonical JSON codec; reject unknown fields, duplicate factor/level ids, empty grids, non-positive concurrency, unsupported schema versions, and unknown constraint ops. Reuse `ExperimentSeedMatrix`. Constraints accept only `exclude_combos`.
  - Files: `src/experiments/matrix_models.py` (new), `src/experiments/matrix_serialization.py` (new), `src/experiments/__init__.py`, `tests/unit/test_experiment_matrix_models.py`, `tests/unit/test_experiment_matrix_serialization.py`.
  - Logging: DEBUG factor/level counts, schema version, fingerprint prefixes; never log seeds, full configs, or credentials. ERROR stable validation reason codes.
  - Dependencies: None.

- [x] Task 2: Implement closed factor applicators for the eight research axes.
  - Deliverable: Registry mapping each `MatrixFactorId` + locked level id → pure function that clones a base `SimulationRunnerConfig` and applies modes/flags/resources only (**does not** set `schema_version`). Fail closed on unknown factor/level ids and on attempts to enable unowned capability flags (`multi_hop_testimony_tracking` never set). Resource scarcity / seasonality reuse catalog/scenario helpers without new world semantics. Cognitive budget levels follow Experiment AD: `expand`/`replace` agents with `CognitiveBudgetMode` + `CognitiveBudgetLimits` from `low_cost_budget_limits()` / `high_cost_budget_limits()` / disabled. Provide a small multi-axis reference fixture for CI (not full 8-way product).
  - Files: `src/experiments/matrix_factors.py` (new), `src/experiments/catalog.py` (reuse helpers only), `src/experiments/environmental_scenario.py` / `territorial_scenario.py` (read-only reuse), `tests/unit/test_experiment_matrix_factors.py`.
  - Logging: INFO matrix id + axis ids; DEBUG per-level mode/flag codes; never log resource quantities or seeds.
  - Dependencies: Task 1.

- [x] Task 3: Implement `finalize_matrix_cell_config` highest-wins schema resolution.
  - Deliverable: After factor application, set `schema_version` per the locked table (budget→v22, …, dynamics→v14, reflection→v6, else v4). Validate the resulting config against existing `SimulationRunnerConfig` gates. Unit tests: reflection+budget→v22; seasonality-only→v14; memory/mortality/tom-only→v4; illegal combinations fail closed with stable reason codes.
  - Files: `src/experiments/matrix_factors.py` (or `matrix_schema.py` new), `tests/unit/test_experiment_matrix_schema.py`.
  - Logging: DEBUG chosen schema_version and winning rule code; ERROR on finalize validation failure.
  - Dependencies: Task 2.

- [x] Task 4: Expand matrices into `ExperimentDefinition` / assignments with complete config cloning.
  - Deliverable: `expand_matrix(spec) -> (ExperimentDefinition, tuple[MatrixCell, ...])` producing deterministic condition ids, composed `group_role` (overlay → treatment-any → control-any → neutral), and seed×replicate cells. Apply factors then `finalize_matrix_cell_config` per condition. Fail closed when constraint-filtered conditions `< 2`. Fix `materialize_assignments` to `dataclasses.replace(condition.runner_config, seed=seed)` and prove `environmental_dynamics`, `artifacts_enabled`, `cognition_trace`, `capability_flags`, `experiment`, and cognition budget fields survive. Prove layout constraints when scarcity levels differ only by allowed resource quantities.
  - Files: `src/experiments/matrix_expand.py` (new), `src/experiments/coordinator.py`, `src/experiments/models.py` (only if shared helpers needed), `tests/unit/test_experiment_matrix_expand.py`, `tests/unit/test_experiment_coordinator.py`.
  - Logging: DEBUG expansion ordinals and condition id prefixes; WARN oversize condition id hash fallback; ERROR constraint / `<2` conditions.
  - Dependencies: Tasks 1–3.

### Phase 2: Batch execution, manifests, resume

- [x] Task 5: Define run manifest store ports and filesystem implementation (incl. crash recovery).
  - Deliverable: Framework-free ports for matrix manifest create/open, cell state transitions, validity checks, and `RunVersionIdentity` on completion sidecars. Filesystem layout: root / `manifest.json` + `cells/<cell_id>.json` (atomic replace). Divergent rewrite of the same `matrix_fingerprint` fails closed. **Crash recovery:** on open/resume, any cell in `running` without a valid completion sidecar resets to `pending` and is rerunnable; never classify as `skipped_valid`.
  - Files: `src/experiments/matrix_manifest.py` (new), `tests/unit/test_experiment_matrix_manifest.py`.
  - Logging: INFO manifest open/create with matrix id + fingerprint prefix; DEBUG state transitions including crash-reset; ERROR conflict/validity codes without payloads.
  - Dependencies: Task 4.

- [x] Task 6: Implement `MatrixBatchRunner` with concurrency limits and failure recovery.
  - Deliverable: Async runner that schedules cells with `max_concurrency` (default 1), skips completed valid cells, retries only transient failures, never reruns valid completions. Force serial execution when any cell is durable (`durable_requires_serial_matrix`). Each cell uses a fresh `SimulationRunner.from_config` + unique `run_id`. Keep sequential `ExperimentCoordinator` for catalog A–E; extract shared “run one assignment” helper if needed. Matrix collectors use summary+trajectory+catalog fallback only.
  - Files: `src/experiments/matrix_runner.py` (new), `src/experiments/coordinator.py`, `tests/unit/test_experiment_matrix_runner.py`.
  - Logging: INFO batch start/complete with pending/completed/failed/skipped counts; DEBUG concurrency slots; WARN retries; ERROR exhausted retries / durable+concurrent rejection. Metadata only.
  - Dependencies: Task 5.

- [x] Task 7: Record per-run version identity and produce matrix aggregates.
  - Deliverable: Every completion record includes `RunVersionIdentity`. Add `matrix-aggregate-v1` builder grouping by factor levels and `group_role`. Deterministic for equal completed sets; omit narrative/prompt/credential material. Document/test that matrix ids use collector fallback (summary+trajectory+catalog).
  - Files: `src/experiments/matrix_aggregate.py` (new), `src/experiments/matrix_manifest.py`, `src/experiments/collectors.py` (reuse only), `tests/unit/test_experiment_matrix_aggregate.py`.
  - Logging: INFO aggregate counts by group_role; DEBUG metric family lists; never log metric payloads at INFO.
  - Dependencies: Tasks 1, 5, 6.

### Phase 3: Composition CLI and docs

- [x] Task 8: Add `research_runner` composition package and CLI.
  - Deliverable: New package `src/research_runner/` with argparse CLI: `run`, `resume`, `status`, `aggregate`. Load matrix JSON, resolve `package_version` via `importlib.metadata.version("palimpsest")`, `code_revision` from inject/`PALIMPSEST_CODE_REVISION`, wire filesystem manifest store and deterministic LLM resolver. **Must not import `api`.** Register console script `palimpsest-matrix`. Update `pyproject.toml` package lists, hatch wheel packages, `tool.palimpsest.packages`, and import-linter (`research_runner` forbids `api`).
  - Files: `src/research_runner/__init__.py`, `src/research_runner/__main__.py`, `src/research_runner/cli.py`, `src/research_runner/composition.py`, `pyproject.toml`, `tests/unit/test_research_runner_cli.py`, `tests/architecture/` (boundary `research_runner` ↔ `api`).
  - Logging: infrastructure logging when wired; CLI INFO for command, matrix id, cell counts; never print secrets or full config dumps by default (`--print-fingerprint` optional).
  - Dependencies: Tasks 6–7.

- [x] Task 9: Documentation checkpoint (`Docs: yes`).
  - Deliverable: Update `docs/experiments.md` with matrix schema, locked axes/levels table, schema finalize rules, group_role composition, resume/crash semantics, CLI examples, and trust boundaries. Update `docs/architecture.md` package table / downstream notes for `research_runner` and `experiment-matrix-v1`. Brief README pointer if entry points are listed. Update `.ai-factory/DESCRIPTION.md` / `ARCHITECTURE.md` package inventory if required. Route through `/aif-docs` conventions during implement.
  - Files: `docs/experiments.md`, `docs/architecture.md`, `README.md` (only if entry-point list exists), `.ai-factory/DESCRIPTION.md` / `ARCHITECTURE.md` as needed.
  - Logging: N/A for docs prose; examples must show metadata-safe commands.
  - Dependencies: Task 8.

### Phase 4: Proofs and isolation

- [x] Task 10: Unit/integration proofs for resume, concurrency, and version identity.
  - Deliverable: Tests proving (a) interrupted batch resumes without rerunning valid cells, (b) crash-`running` resets to pending and reruns, (c) fingerprint mismatch fails closed, (d) `max_concurrency=1` ordering for a tiny fixture, (e) durable config rejects concurrency >1, (f) version identity fields present/stable, (g) factor expansion differs only along declared axes while sharing stochastic identity / layout rules, (h) group_role composition cases. Network-free deterministic fakes; tiny tick budgets.
  - Files: `tests/unit/test_experiment_matrix_runner.py`, `tests/unit/test_experiment_matrix_resume.py`, `tests/integration/test_experiment_matrix_batch.py` (opt-in marker if durable), architecture isolation updates.
  - Logging: Assert log extras exclude seeds and payloads where existing audit patterns apply.
  - Dependencies: Tasks 6–8.

- [x] Task 11: Architecture and V1 regression confirmation.
  - Deliverable: Confirm import-linter: `experiments` still forbids `api`/`infrastructure`/`persistence`; `research_runner` forbids `api`. Run `tests/unit/test_v1_regression_gate.py` green (do not append matrix cases). Instrumentation isolation: matrix aggregates/collectors not importable from domain packages.
  - Files: `pyproject.toml` import-linter contracts, `tests/architecture/test_experiment_instrumentation_isolation.py`, `tests/unit/test_v1_regression_gate.py` (run only).
  - Logging: N/A beyond existing patterns.
  - Dependencies: Tasks 8–10.

## Implementation notes for `/aif-implement`

- Prefer short ticks and 2×2×seeds=1 fixtures in CI; document fuller grids as researcher-facing examples only.
- Extract shared “run one assignment” logic carefully so catalog coordinator behavior remains stable.
- Factor applicators never pick schema versions; only `finalize_matrix_cell_config` does.
- ToM factor enables only `advanced_social_inference`; it must not enable `multi_hop_testimony_tracking`.
- Imagination factor is `ImaginationMode` only; prospective/counterfactual stay out of the v1 level table.
- Deferred follow-up (not this plan): SQLAlchemy matrix membership / `ExperimentRecordRepository` linkage.
