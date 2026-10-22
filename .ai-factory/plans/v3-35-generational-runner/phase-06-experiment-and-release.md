# Phase 6: Reproducible experiment entrypoints and release gates

Plan: [index.md](index.md)
Tasks: 16–18
Depends on: Tasks 1–15

## Objective

Ship an executable multi-generation experiment through library/matrix/CLI composition, with real historical replay proofs, scale coverage, and accurate documentation.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/experiments/regional_migration_scenario.py` | `regional_migration_scenario`, diagnostic arbiter | Real AY regions, routes, migration and admission-neutral treatment. |
| `src/experiments/multiple_societies_scenario.py` | `multiple_societies_scenario`, diagnostic arbiter | Existing isolated/contact topologies; base argument does not preserve arbitrary lifecycle settings. |
| `src/experiments/coordinator.py` | `ExperimentCoordinator.run_all` 109–259 | Per-assignment construction and generation mapping already exist. |
| `src/experiments/matrix_runner.py` | `MatrixBatchDependencies`, `run_one_assignment` 61–117 | Currently does not inject durable/recording factories; retains complete arm results. |
| `src/experiments/matrix_schema.py` | `finalize_matrix_cell_config`; called by `expand_matrix` | v55 must survive the independent highest-wins selector added in Task 2. |
| `src/experiments/coordinator.py` | `ExperimentAssignment` 24–34 | A standalone config is not already a materialized assignment; CLI must define its construction and recipe. |
| `src/persistence/sqlalchemy.py` | `create_run` 139–141; `src/experiments/matrix_runner.py` — two skip checks and retry loop | Durable origin reruns conflict; both skip paths must validate/adopt archival completion before execution. |
| `src/research_runner/cli.py` | `build_parser`, `_cmd_run`, `_cmd_resume` | Existing CLI is matrix-only; resume reruns whole cells. |
| `src/research_runner/composition.py` | dependency/version composition | Add durable dependencies here without importing API. |
| `tests/benchmarks/harness.py` | `build_scale_config`, `durable_factories`, `count_snapshots` | Existing benchmark and disposable persistence helpers. |
| `pyproject.toml` | entry point and pytest/coverage settings 98–144 | Keep existing CLI binary, test markers and coverage. |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/experiments/generational_runner_scenario.py` | create | New off-V1-gate BL scenario, `generational_runner@1`. |
| `src/experiments/generational_execution.py` | create | Per-assignment artifact/provenance lifecycle and runner configuration callback contract. |
| `src/experiments/catalog.py`, `src/experiments/__init__.py` | modify | Register/export scenario using existing catalog conventions. |
| `src/experiments/coordinator.py`, `src/experiments/matrix_runner.py` | modify | Optional assignment dependency injection and generational execution routing. |
| `src/experiments/matrix_manifest.py` | modify | Validated archive-to-matrix completion reconciliation without re-execution. |
| `src/research_runner/generational_composition.py`, `src/research_runner/cli.py` | modify | New `generational` subcommand and durable/recording/source composition. |
| `tests/unit/test_experiment_bl.py`, `tests/unit/test_generational_execution.py`, `tests/unit/test_generational_cli.py` | create | Scenario, assignment, CLI and provenance gates. |
| `tests/integration/test_generational_scale.py` | create | Opt-in long-horizon durable proof. |
| `docs/generational-runner.md` | create | Complete experiment/operator contract. |
| `docs/simulation-runner.md`, `docs/configuration.md`, `docs/experiments.md`, `docs/development.md`, `README.md` | modify | Focused references/version/verification updates through `$aif-docs`. |

## Task 16: Add a real multi-generation experiment and per-assignment execution context

### Intent

Exercise existing objective mechanics and detached analysis together rather than validating only synthetic counters.

### Implementation Steps

1. Add `generational_runner_scenario(seed=23, max_ticks=...)` with experiment ID `generational_runner@1` and catalog label BL (first verify BL is still unused). Keep it outside the V1 A–E/reference gate; add no metric family merely for orchestration metadata.
2. Compose the real AY regional scenario's immutable world/regions/routes, then explicitly replace lifecycle/initialization/generational settings on the final config. Do not rely on the AZ `base` parameter preserving lifecycle. Keep lifecycle and finite resources explicit so deaths can occur without scripted institutional outcomes.
3. Provide paired conditions `bl-single-cohort` (demography disabled), `bl-generational-unassisted` (advancing entries at multiple locations, no diagnostic migration treatment), and `bl-generational-contact` (same entry schedule with declared AY-style treatment). Unassisted cognition may still choose migration; do not label its absence of intervention as guaranteed isolation. Actual isolated-community evidence is covered by the AZ-derived sampler fixture. Modes remain explicit/content-empty; no founder state is copied to entrants.
4. A diagnostic arbiter may issue documented existing migration commands for known eligible actors, using normal admission and accurate treatment evidence. Never force arrival, fabricate a community, or generate a new command. Off/isolated conditions must not receive that intervention.
5. Introduce `GenerationalExecutionContext` in `generational_execution.py`: per-assignment dependency factories, artifact store/header identity, required frozen execution-recipe descriptor, optional registered runner-configurator callback, and completion/failure methods. Require exact agreement between callback registration and the descriptor's ID/version/params/intervention fields; reject arbitrary untracked callbacks for exact archives. Validate source/recording/durability dependencies before run creation. Factories are injected from outer composition, not imported from persistence/infrastructure. Register `plain-generational@1` with empty params/no intervention and `bl-diagnostic@1` with exact params `{treatment}` in `{single_cohort, unassisted, contact}`; only contact installs the versioned BL migration intervention. Bind the correct recipe explicitly per library assignment, rather than infer behavior from a condition label.
6. `execute_generational_assignment` writes the header/config, constructs a fresh runner with context dependencies, invokes the existing trusted assignment configurator, runs to completion, harvests final result/generation mappings, persists required artifacts, then returns the normal `ExperimentArmResult`. Artifact completion must occur before the caller marks the matrix cell complete.
7. Add optional per-assignment context/factories injection to coordinator and matrix dependencies with legacy defaults unchanged. Generational configs require an archival context in experiment execution; reject missing context rather than silently run an untracked v55 experiment. Keep existing diagnostic wiring in its current owners and pass a configurator into the helper; do not rewrite unrelated experiment arbiters.
8. Before creating a durable runner, check for existing durable run identity and a verified completed archive. Reconcile a valid completed archive to missing matrix completion metadata without construction or execution. If there is an existing durable run without a valid completed archive, fail non-retryably with `durable_origin_rerun_unsupported`. A new artifact attempt directory alone cannot fix this. Preserve same-ID origin retries only for non-durable execution or a user-selected fresh isolated persistence destination. Add full embedded-matrix expansion-to-execution coverage using Task 2's selector, not a direct `run_one_assignment` test that bypasses expansion.

### Required Interfaces and Contracts

Arm identity includes config/seed/source/assignment metadata; repeated runs for comparison use separate stores and the same complete run identity when demanding exact hashes. The generation mapping includes entrants, not only config founders. BL metadata is not a new analysis metric catalog family.

### Requirement Evidence

User multi-generation/migration/communities requirements; existing AY/AZ representative artifacts; C2/C7–C9. All optional behavior stays off the V1 gate.

### Error Handling and Logging

INFO assignment ID, condition, seed ordinal, finalized boundary, stop code and counts. Missing context/source/recording fails preflight. Failure during execution writes a safe failure artifact, not successful completion; no best-effort success when required provenance is missing.

### Tests

Real AY-derived config encode/decode/run/export/replay path; at least three realized generation labels including founders; overlapping cohorts; deaths and fresh initialization; actual movement; full-identity twin hashes/different-seed stochastic divergence; unassisted/contact observations without guaranteed isolation; versioned recipe/intervention persistence and mismatch rejection. Test coordinator versus expanded matrix execution, missing context, legacy parity, existing durable identity refusal, and archive-completion adoption with zero new runner/provider calls.

### Acceptance Criteria

A real catalog experiment produces generations, deaths, movement, truthful community samples, and complete artifacts through both assignment execution surfaces.

### Verification

`uv run --frozen pytest --cov --cov-report=term-missing tests/unit/test_experiment_bl.py tests/unit/test_generational_execution.py tests/unit/test_experiment_ay.py tests/unit/test_experiment_matrix_resume.py -q`

Expected: BL and representative existing assignment paths pass.

## Task 17: Expose generational CLI composition and reproducibility preflight

### Intent

Make long historical runs executable without HTTP and without claiming a new restart mechanism.

### Implementation Steps

1. Add `palimpsest-matrix generational --config <runner.json> --execution-recipe <recipe.json> --artifact-root <dir> --run-id <id> --code-revision <revision> [--source-clean | --source-artifact-digest <sha256>]`. Recipe JSON is the exact nested `execution_recipe` object from Task 11, resolved by Task 16's closed registry; it is a reproducibility input, not an arbitrary Python import path. Require clean assertion or source digest for exact archives; `PALIMPSEST_CODE_REVISION` remains allowed. Decode v55 strictly; never transform an older schema.
2. Construct one `ExperimentAssignment` explicitly. If `config.experiment` is present, retain its experiment/condition/replicate/seed-ordinal identity and use condition_ordinal=0 for this standalone command. If absent, replace the v55 config's experiment field before hashing/archiving with `ExperimentAssignmentRef(experiment_id="generational_runner_ad_hoc@1", condition_id="standalone", replicate_index=0, seed_ordinal=0)` and use ordinal 0. Use `--run-id` as scientific RunId and config.seed as seed. Validate recipe treatment against the resulting config (single_cohort requires disabled demography; other BL treatments require the generational schedule). Named config metadata alone never silently installs an intervention. Use the ordinary execution context and `SimulationRunner.run`, not a custom tick loop. Existing commands still mean matrix operations.
3. For configured durable historical runs, build database resources with existing infrastructure settings and public persistence factories (run, journal, snapshots, pending finalizations, scientific evidence). Use `async with`/finally resource cleanup. Do not import API or allocate resources at import time. Real-run DB selection follows existing runtime settings; test-only database guards remain strict in tests.
4. Add composition-only replay flags `--recording-root`, `--recording-artifact-id`, `--recording-namespace`, and `--recording-lookup-mode`. Require a complete set when replay is selected; fake mode rejects irrelevant recording flags. Never copy root paths into metadata or config fingerprints. Namespace sharing is explicit; no default reuse across independent cells.
5. Add `--generational-artifact-root`, `--execution-recipe`, optional recording/source flags, and injected assignment context construction to existing matrix run/resume when expanded cells are generational. Recipe applies explicitly to those assignments; library contexts may bind different registered recipes per assignment, each archived. Enforce durable concurrency=1. Non-durable retries use attempt-specific directories with unchanged scientific RunId; durable incomplete runs with an existing RunId fail closed rather than pretend to restart. Never auto-delete runs or substitute attempt ordinal into RNG identity. Document reproduction in a user-provided fresh isolated persistence destination as a distinct explicit action.
6. Preflight the source identity, config/schema, criterion registry, artifact destination, and recording metadata before starting runs. Return exit 0 only for a valid scientific stop with all required artifacts; exit 1 for execution/orchestration failure and exit 2 for preflight/usage/integrity conflicts. Existing command behavior remains unchanged when no generational cells exist.
7. On matrix rerun/skip, compare current source/config/seed/recording/recipe identities and all required archival hashes before accepting generational completion. Apply this gate in both MatrixBatchRunner skip paths, including rows already marked COMPLETED/SKIPPED_VALID (the current state-only shortcut is insufficient). A fully verified archive may repair missing matrix completion metadata; conflicting or incomplete output cannot become valid by changing cell state. Never construct a runner for completion adoption. Restrict stronger checks to generational artifacts; old manifests retain existing policy.

### Required Interfaces and Contracts

CLI/environment composes credentials/roots without entering deterministic config identity; source/recording/recipe identities are archival inputs. `resume` never means restored subjective continuation. Non-durable incomplete cells may rerun from origin; durable incomplete cells in the same persistence destination must be reported unsupported. Valid completed archives can be reconciled without re-execution. Incomplete historical artifacts are retained for inspection, not used as a runner checkpoint.

### Requirement Evidence

User reproducibility/long experiment needs; existing matrix CLI and provenance gaps; checkpoint scope clarification; C8/C9.

### Error Handling and Logging

Safe reason codes and booleans for configured recording/DB/source settings; no DSNs, root paths, credentials, prompts or arbitrary config errors. Logs must identify preflight versus post-finalized failure. Resource cleanup is tested on construction and mid-run failure.

### Tests

CLI fake run including absent/present config.experiment and explicitly archived normalized config; plain/BL registered recipes and treatment validation; unknown/untracked recipe rejection; changed intervention identity; missing source assertion; durable dependency injection; replay miss/drift; artifact conflicts; unsupported criterion; both matrix skip paths check source/recipe/recording identity. Crash after archive completion is adopted without rerunning; partial durable RunId is a non-retryable refusal; non-durable retries preserve identity in new attempt directories. Verify import boundaries, cleanup and old command behavior.

### Acceptance Criteria

An operator can run and verify a long generational configuration with one documented command and cannot mistake archive inspection for process restart.

### Verification

`uv run --frozen pytest --cov --cov-report=term-missing tests/unit/test_generational_cli.py tests/unit/test_research_runner_cli.py tests/unit/test_generational_execution.py -q`

`uv run --frozen palimpsest-matrix generational --help`

Expected: CLI/context tests pass and help describes the new command without changing old subcommands.

## Task 18: Prove long-horizon gates and document exact guarantees

### Intent

Close the feature with executable durability/scale/reproducibility guarantees and an accurate operator contract, not a separate report artifact.

### Implementation Steps

1. Add `tests/integration/test_generational_scale.py`, marked both integration and scale. Use the existing benchmark harness and disposable DB guard. Configure 100000 ticks, one new entrant per 1000 ticks, generation length 1000, short lifespans, extinction disabled, bounded living-population cap, and historical cadence 1000. No generation stop in this case. Demonstrate empty-population gaps and at least 90 admitted generations, depending only on the explicit schedule/cap.
2. Assert exact 100000 committed ticks, expected realized admission labels/counts, valid snapshot cadence and immutable history references, no accidental four-digit truncation, complete final manifest/result hashes, and historical seek parity at early/middle/late sample boundaries. Run a smaller deterministic twin for exact artifact comparison; use operation/allocation-shape tests for structural complexity rather than timing thresholds.
3. Keep default coverage enabled. Run the focused new suites, architecture checks, V1 regression gate, V2 scientific invariants, lint, types, and integration/scale commands listed below. Do not lower coverage thresholds or disable checks to pass long tests.
   Include Task 13's receipt-membership operation-count proof; event chunks alone are not a sufficient scale gate. Pin exact expected schedule counts: with births due at positive multiples of 1000 and executed ticks 0 through 99999, there are 99 due cohorts (subject to the explicitly tested physical admission invariants), not an invented entry at tick 100000.
4. Invoke `$aif-docs` as the mandatory documentation checkpoint. Create `docs/generational-runner.md` and add its README index link. Explain config v55/result v3, generation-versus-cohort-versus-kinship/community, admission/death order, cap-drop semantics, stop precedence, threshold inclusivity, custom-criterion cadence/failures, artifact layout, CLI examples, and replay/source validation.
5. Update focused sections in simulation-runner/configuration/experiments/development docs. State: fake/recordings are needed for exact LLM output; replay use is recorded only after validation and ordered canonically; demography/init/lifespan remain run-ID-scoped; source revision alone cannot identify dirty code; recipe/intervention identity is necessary; historical replay is not subjective restart. Matrix resume can adopt complete verified archives or rerun non-durable cells, but cannot recreate an incomplete durable RunId in place. Total storage/RAM remain history-sized; optional full-history channels may dominate cost.
6. Document unchanged pins: commands 43, observer semantic types 73, metric families 129, Alembic 0017, stable `/v1` and observer protocol, default runner v4, legacy result default v2. New runner v55/result v3 are feature-selected only. No capability flag is newly owned. Route any roadmap update through its owner command; this plan does not close M7.

### Required Interfaces and Contracts

Scale is opt-in; routine unit tests do not require Docker/PostgreSQL. A skipped DB/scale suite is a verification gap, not success. No invented benchmark numbers or claims of bounded total memory.

### Requirement Evidence

User very long horizons and reproducible metadata; configured docs/tests preference; project coverage, architecture and disposable-DB rules; C1–C10.

### Error Handling and Logging

Run scale verification at an operationally practical log level while retaining metadata-only logging tests. ERROR failures contain safe codes and boundary counts only. Docs must describe artifact failure after commit honestly.

### Tests and Verification

Default gates:

```bash
uv run --frozen pytest --cov --cov-report=term-missing tests/unit/test_runner_config_v55.py tests/unit/test_generational_models.py tests/unit/test_generational_result_codec.py tests/unit/test_generational_demographic_policy.py tests/unit/test_generational_population_runner.py tests/unit/test_generational_stopping.py tests/unit/test_generational_criteria.py tests/unit/test_runner_finish_run.py tests/unit/test_generational_consumers.py tests/unit/test_generational_seed_manifest.py tests/unit/test_generational_recording.py tests/unit/test_generational_artifacts.py tests/unit/test_engine_history_sequence.py tests/unit/test_streaming_trajectory_hashes.py tests/unit/test_generational_sampling.py tests/unit/test_experiment_bl.py tests/unit/test_generational_execution.py tests/unit/test_generational_cli.py tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py tests/architecture -q
uv run --frozen ruff check src tests
uv run --frozen mypy src tests
uv run --frozen lint-imports
```

Also run `uv run --frozen pytest --cov --cov-report=term-missing tests/unit/test_generational_matrix_schema.py -q` for the real embedded-matrix selection path.

Durability and scale gates (explicit disposable `PALIMPSEST_TEST_DATABASE_URL` required):

```bash
uv run --frozen pytest --cov --cov-report=term-missing -m integration tests/integration/test_generational_history.py tests/integration/test_long_run_checkpoints.py tests/integration/test_regional_travel_persistence.py -q
uv run --frozen pytest --cov --cov-report=term-missing -m 'integration and scale' tests/integration/test_generational_scale.py -q
```

Expected: focused, architecture, type/lint, actual database and scale gates pass. Run under the project's pinned Python 3.12.14 environment; do not change the pin for this feature.

### Acceptance Criteria

100000-tick historical execution and inspection work with multiple realized generations; regression/invariant gates remain green; documentation explains both guarantees and remaining resource/restart limits.

## Phase Risks and Mitigations

- Default unit runs must stay practical: mark the 100000-tick proof integration+scale and retain smaller unit equivalence tests.
- Diagnostic treatments can be mistaken for emergence: label interventions in config/provenance and never assert that community/institution outcomes are guaranteed.
- Existing matrix completion writes before best-effort metric sidecars: generational required artifacts must complete before cell completion, while unrelated legacy metric policy stays unchanged.

## Phase Completion Checklist

- Tasks 16–18 meet acceptance criteria; mandatory docs checkpoint and available verification gates complete.
- Any unavailable integration environment is explicitly recorded as unverified, not silently passed.
- Update only the index progress ledger.
