# Phase 1: Versioned generational execution contracts

Plan: [index.md](index.md)
Tasks: 1–3
Depends on: none

## Objective

Define an opt-in runner surface without changing legacy config keysets, objective event formats, or capability ownership.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/simulation/runner_models.py` | version constants 90–208; `PopulationLifecycleSpec` 1274–1457; `RunnerStopPolicy` 6897–6916; `SimulationRunnerConfig` 7168+ | v54 is the current accepted feature surface; default writer is v4; demography is scheduled creation, not biology. |
| `src/simulation/runner_serialization.py` | version-specific cognition keysets; `encode_runner_config` / `decode_runner_config`; `build_runner_result_document` 11478–11522 | Strict versioned mappings and result hashing already exist. |
| `src/simulation/compatibility.py` | owning-package imports and literal mirrors | No imports from experiments/analysis into simulation. |
| `src/simulation/runner_serialization.py` | `_v46_family_root_keys` through `_v54_family_root_keys` 4576–4682 | v54 has feature-selected exact root families, not a universal root keyset. |
| `src/simulation/runner_models.py` | mode activation gates 10644–10719 | v54 specifically requires decay; v55 must instead require generational execution. |
| `src/experiments/matrix_schema.py` | `finalize_matrix_cell_config` 69–362 | Matrix expansion independently selects/reconstructs the runner version. |
| `tests/unit/test_runner_config_v54.py` | `_base`, roundtrip and rejection cases | Follow exact-keyset testing patterns, not a permissive new decoder. |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/simulation/generational_models.py` | create | Frozen run, threshold, criterion, progress, boundary, stop-evidence contracts. |
| `src/simulation/runner_models.py` | modify | v55 config support, optional sibling, cross-field gates, new stop codes, optional generational result fields. |
| `src/simulation/generational_serialization.py` | create | Exact-keyset nested mappings and canonical progress/stop-evidence serialization. |
| `src/simulation/runner_serialization.py` | modify | v55 root dispatch and runner-result-v3; preserve legacy writers/readers. |
| `src/simulation/compatibility.py`, `src/simulation/__init__.py` | modify | Accepted-version taxonomy and public exports. |
| `src/experiments/matrix_schema.py` | modify | Highest-priority v55 selection when generational execution is present. |
| `tests/unit/test_generational_matrix_schema.py` | create | Embedded config/factor expansion/roundtrip gate. |
| `tests/unit/test_runner_config_v55.py`, `tests/unit/test_generational_models.py`, `tests/unit/test_generational_result_codec.py` | create | Contract, compatibility, and result tests. |

## Task 1: Add immutable run and boundary models

### Intent

Commit the meanings of generation, cohort, population, horizons, and callback inputs before orchestration changes.

### Implementation Steps

1. Introduce `GenerationalRunSpec` in the new `generational_models.py`. Its exact fields are `max_generation_index: int | None`, `stop_on_extinction: bool = True`, `population_threshold: PopulationThresholdSpec | None`, `experiment_criteria: tuple[ExperimentCriterionSpec, ...] = ()`, `criterion_cadence_ticks: int = 1`, `historical_checkpoint_cadence_ticks: int | None = None`, and `sample_on_generation_change: bool = True`.
2. `PopulationThresholdSpec` has `comparison` in `{at_most, at_least}` and exact nonnegative integer `value`. `ExperimentCriterionSpec` has stable `criterion_id`, stable `version`, and recursively frozen JSON `params`; reject non-finite numbers, non-string keys, duplicate IDs, and executable objects. Preserve declaration order in config but evaluate criteria by `(criterion_id, version)`.
3. Add `PopulationProgress`: completed `boundary_tick`, `living_population`, `total_admitted` (includes founders), `total_deaths`, `max_generation_index_seen`, and sorted tuples of `CohortPopulationRow` / `GenerationPopulationRow`. Rows carry admitted/living/dead totals; cohort rows also carry generation and entry tick. All IDs come from objective lifecycle records, not inferred social labels.
4. Add `GenerationalBoundary` with progress, objective revision, last completed tick (`boundary_tick - 1`, or null at B=0), objective commit identity when durable, and immutable current-tick event facts. Facts are public detached objective records, not world state or owner stores. Add `StopEvidence` containing boundary, ordered matched condition codes, primary code, ordered matched criterion identities, closed custom-evaluation status (`not_due`, `evaluated`, `skipped_builtin_stop`, `failed`, or `not_configured`), optional failed stage/reason code, and safe scalar measurements. Measurements admit finite numbers/bools only; text belongs only in validated identity/reason-code fields. Precommit failure at B=0 has no last tick or last-tick events and must not invent an objective commit.
5. Add `generational_run: GenerationalRunSpec | None = None` to `SimulationRunnerConfig`. Require owned `generational_population`, explicit lifecycle and explicit blank-slate `new_agent_initialization`, and `stop_policy.stop_on_all_agents_terminal=False` when present. Require `max_ticks` as the unconditional finite positive safety limit. Generation limit, if set, must be >=1. Historical cadence requires matching enabled durable checkpoint cadence.

### Required Interfaces and Contracts

- Generation is the immutable label assigned at actual admission; cohort is an admission-tick/spawn stratum. Neither is genealogy or a community.
- Population counts registered bodies with objective living status; terminal runtime status is not a population measure. An in-transit living body counts exactly once.
- Threshold and generation conditions are evaluated after the first completed tick, not against bootstrap before any tick. `max_generation_index_seen` never falls when a generation dies.
- Exact bool/int discrimination is mandatory. No artificial maximum of 9999 ticks or generations.

### Requirement Evidence

User request: cohorts/generations/stops; `world/lifecycle.py` — `AgentLifecycleRecord`; `runner_models.py` — lifecycle no-biology contract; index combinations C1–C8.

### Error Handling and Logging

Reject invalid configurations before provider allocation or durable run creation. DEBUG records field names and stable validation codes only; do not log criterion params or arbitrary invalid values.

### Tests

Cover booleans as integers, zero/negative cadences, huge positive horizons, all optional-stop combinations, invalid criterion JSON, missing feature dependencies, transit population accounting, and immutability.

### Acceptance Criteria

All generational settings have frozen, validated values; absence is a true passthrough. Unsupported flag slots remain fail closed.

### Verification

`uv run --frozen pytest --cov --cov-report=term-missing tests/unit/test_generational_models.py -q`

Expected: all contract cases pass without network or database access.

## Task 2: Add exact v55 config encoding and compatibility gates

### Intent

Make new orchestration reproducible through a new schema instead of widening v54.

### Implementation Steps

1. Add `RUNNER_SCHEMA_VERSION_V55` to the accepted set. Keep `RUNNER_SCHEMA_VERSION` at v4.
2. Add `_v55_family_root_keys(data)` rather than inventing a universal v54 root. Select the existing active lower family with `_v54_family_root_keys` on the mapping without `generational_run`, then require `v3_capability_flags`, `population_lifecycle`, `new_agent_initialization`, and `generational_run`. In the population-only fallback, start from the existing v26/v26-with-dynamics population root; include present `kinship`, `dependency_care`, `developmental_learning`, and `mentorship` only under their existing dependency validators. Preserve the selected lower-family exact-key rules for all other siblings. Explicitly include environmental dynamics in the selected population root when enabled. Reject unknown siblings and nulls for old optional root objects; do not widen v1–v54 helpers.
3. Use the full v54 per-agent cognition keyset unchanged. Change mode-enabled accepted-version sets to admit v55, but do not copy feature-write triggers such as `schema_version == v54 requires decay` to v55. v55 is activated by `generational_run` alone; every institutional mode may be disabled. Existing per-owner mode dependencies still apply when enabled. Put new nested mappings in `generational_serialization.py`; only optional children of `generational_run` have explicit nulls. Existing optional root siblings retain omission semantics. Older roots reject the new sibling.
4. Extend lifecycle/initialization/region/contact and profile version guards to the selected v55 combinations without changing objective write-pair selection. In `finalize_matrix_cell_config`, add the first selection branch `generational_run is not None -> v55` before existing highest-wins logic. Reconstruct and validate the same explicit lifecycle/initialization/stop settings; do not synthesize new defaults or downgrade v55 after factors. Leave old matrix version selection unchanged. Keep `experiment-matrix-v1`; this is runner-version dispatch, not a new matrix schema.
5. Permit the new demographic policy ID only when the enclosing runner schema is v55 and the generational sibling is present. A bare `PopulationLifecycleSpec` may validate its closed params, but older top-level configs must reject that policy.
6. Export the new public contracts and mirror the accepted version in `compatibility.py`. Do not alter the experiment-definition/matrix schemas.

### Required Interfaces and Contracts

- Explicit v55 with null generational settings is invalid; old explicit schemas keep their existing semantics.
- Encode/decode/encode is canonical and preserves fingerprint. The writer must not silently upgrade or downgrade caller schemas.
- No migration, new world event/command, replay marker, or derivation version is required.

### Requirement Evidence

`.ai-factory/ARCHITECTURE.md` — Versioned Extension Contract; `runner_serialization.py` strict dispatch; combinations C1, C2, C7, C8.

### Error Handling and Logging

Use existing `RunnerSerializationError` safe reason codes for unknown/missing keys and unsupported combinations. Never log full configs.

### Tests

Roundtrip the real AY-derived regional config and a population-only config on v55, both with every institutional mode disabled. Cover dynamics on/off, optional kinship, and supported later modes independently; distinguish accepted-version gates from old feature-write triggers. Test missing/extra root/nested keys, omitted versus null old siblings, v54 rejection, unowned flags, and legacy byte/fingerprint preservation. Add an embedded v55 matrix with two allowed factor levels: expand, assert retained sibling/schema/settings, encode/decode and compare cell fingerprints. Invalid factor combinations must fail validation rather than erase generational settings.

### Acceptance Criteria

v55 accepts only the specified extension; v1–v54 acceptance and off-path canonical output remain intact.

### Verification

`uv run --frozen pytest --cov --cov-report=term-missing tests/unit/test_runner_config_v55.py tests/unit/test_runner_config_v54.py tests/unit/test_v1_regression_gate.py -q`

`uv run --frozen pytest --cov --cov-report=term-missing tests/unit/test_generational_matrix_schema.py -q`

Expected: legacy and new config/regression suites pass.

## Task 3: Version generational results and stop evidence

### Intent

Expose reasons and denominators without silently extending runner-result-v2.

### Implementation Steps

1. Add stop codes `generation_horizon`, `population_extinction`, `population_threshold`, `experiment_criterion`, `experiment_criterion_failure`, and `historical_artifact_failure` to `RunnerStopReasonCode`.
2. Add optional `generational_progress` and `stop_evidence` to in-process `SimulationRunnerResult`; both must be absent for legacy runs and present for generational results. Failure evidence records the actual committed/finalized boundary and never implies rollback.
3. Add accepted `runner-result-v3`, selected by `build_runner_result_document` only for generational configs. Its exact keyset is v2 plus `generational_progress` and `stop_evidence`. Retain the v2 default constant for legacy writers and both existing readers.
4. Update result encode/decode and compatibility mirrors. Counters and hashes retain their original meaning; additional metadata is not mixed into existing trajectory hashes.
5. Add deterministic helpers to order matched conditions and validate evidence-primary consistency. Fatal orchestration errors outrank successful conditions. Otherwise precedence is injected stop, max ticks, generation horizon, extinction, population threshold, experiment criterion; retain all simultaneously matching built-in codes. Preserve all matching criterion identities, not just the primary one. Failure results before any commit use the B=0 representation from Task 1. Add a simulation-owned success/failure classification helper for API consumers; experiments may use it but API must not import experiment allowlists.

### Required Interfaces and Contracts

Results distinguish a population cap (admission rule) from a population threshold (termination condition). Experiment criterion IDs/versions are evidence, not executable callbacks serialized into results.

### Requirement Evidence

User request — reproducibility and stops; `build_runner_result_document`; index stop-order contract and combinations C3–C6.

### Error Handling and Logging

INFO reports primary stop code, boundary, and counts. DEBUG may list closed matched codes. Criterion parameters, messages, and subjective evidence must never enter logs.

### Tests

v1/v2 legacy decode, v2 unchanged writes, exact v3 keyset, inconsistent evidence rejection, simultaneous matches, failure-after-commit boundary, and canonical result hashes.

### Acceptance Criteria

Every new termination mode has an explicit result representation; old result payloads remain readable.

### Verification

`uv run --frozen pytest --cov --cov-report=term-missing tests/unit/test_generational_result_codec.py -q`

Expected: strict result compatibility and ordering cases pass.

## Phase Risks and Mitigations

- Large existing schema dispatch tables are easy to partially extend: test every v54-compatible channel family on v55, not just the new sibling.
- Avoid import cycles: `generational_models.py` must not import `runner_models.py`; use stable strings for stop-evidence codes and validate conversion at the runner/result boundary.

## Phase Completion Checklist

- Tasks 1–3 meet acceptance criteria and commands pass.
- Only `index.md` carries task progress checkboxes.
