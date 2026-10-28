# Phase 2: Execution, evidence and benchmark artifacts

Plan: [index.md](index.md)
Tasks: 4–5
Depends on: Tasks 1–3

## Objective

Execute genuine generational assignments with independent coverage and publication receipts. Preserve actual before-first-cognition evidence and never equate capture failure with scientific absence.

## Current-Code Evidence

| Path | Symbols | Why it matters |
| --- | --- | --- |
| `src/experiments/generational_execution.py` | `GenerationalExecutionContext`, `execute_generational_assignment`, `_validate_recipe` | Synchronous configurator; plain/BL recipe allowlist; capture exceptions do not fail scientific results |
| `src/experiments/generational_archive.py` | `GenerationalExecutionRecipe`, `open_generational_archive` | Canonical immutable recipe/source/provider identity |
| `src/experiments/interventions.py` | `MilestoneOverride`, `MilestoneInterventionArbiter` | Overrides traverse normal binding/admission; acknowledgements distinguish applied/rejected |
| `src/simulation/runner.py` | `initialize_finalized_boundary`, `run_tick`, `capture_fork_checkpoint`, `set_intervention_arbiter` | Public stepped fixture execution and detached complete owner state |
| `src/research_runner/lineage_composition.py`, `src/research_runner/civilization_composition.py` | producer install/finalize functions | Optional production publication bridges |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/experiments/civilization_benchmark_execution.py` | create | Dispatcher, stepped acceptance lane and detached probes |
| `src/experiments/civilization_benchmark_evidence.py` | create | Closed metadata receipts and selector evaluation |
| `src/experiments/civilization_benchmark_artifacts.py` | create | Strict sibling report codecs and verification |
| `src/experiments/generational_execution.py` | modify | Closed benchmark recipe validation and optional execution-observer integration |
| `src/simulation/runner.py` | modify | Terminal-safe detached research projection; preserve strict fork guards and ordinary stop/finalization behavior |
| `src/research_runner/civilization_benchmark_composition.py`, `src/research_runner/civilization_benchmark_cli.py` | create | Outer adapters and CLI parser/dispatch |
| `src/research_runner/cli.py` | modify | Register benchmark subcommand |
| `tests/unit/test_v3_benchmark_execution.py`, `tests/unit/test_v3_benchmark_artifacts.py`, `tests/unit/test_v3_benchmark_cli.py` | create | Execution/failure/artifact tests |

## Task 4: Execute independent lanes with real owner and admission probes

### Intent

Use existing generational execution for research arms; use a stepped runner for controlled mechanism fixtures. Do not duplicate world rules or silently execute grouped forks as independent arms.

### Implementation Steps

1. Implement `execute_civilization_benchmark(recipe, context) -> V3BenchmarkRunResult`, with a discriminated independent/grouped recipe. `CivilizationBenchmarkContext` supplies per-assignment context factories, grouped adapter, detached evidence observer and publication receipt collector. Use coordinator assignment materialization and existing archive/session helpers.
2. Add a closed `v3-benchmark` / version `1` recipe descriptor to `_validate_recipe`, accepting exactly scenario ID, lane, profile and command-plan ID/version. No arbitrary executable import, callback name or JSON patch in persisted recipes. Independent research lanes are unassisted and have no command-plan ID or arbiter. Grouped research cases 29–30 instead retain their predeclared BN prefix controls and experimental Give/Wait treatment; those interventions are the research design, not a claim of unassisted emergence. Their results must say `grouped_intervention`, not `unassisted`.
3. Controlled execution initializes boundary zero, probes actual owner state, calls `run_tick`, then probes each fully finalized boundary before the next tick. Implement `execute_stepped_benchmark_runner` in the new execution module using `RunnerAttemptReceipt.status`/`stop_reason`, exactly matching `SimulationRunner.run()`'s closed loop and calling `finish_run` exactly once. Do not duplicate stop-selector evaluation or change runner policy. Compare normal versus stepped execution for horizon, generation, extinction, cancellation and failure stops. Add an optional async callback `boundary_observer: Callable[[SimulationRunner, RunnerAttemptReceipt | None], Awaitable[None]] | None` to `GenerationalExecutionContext`; `None` receipt denotes initialized boundary zero. When present, generational execution uses the same stepped helper; when absent its existing `runner.run()` path remains unchanged. The helper wraps only observer calls in exception isolation and records `probe_unavailable` in benchmark receipts without converting successful scientific execution into failure. Observers remain trusted read-only outer consumers; no callback enters cognition or changes scheduling.
4. Use `capture_fork_checkpoint().owner_state()` and `.runtime_state()` at supported nonterminal boundaries plus instrumented owner-service factories to measure actual counts at bind. Refactor `SimulationRunner.export_finalized_research_boundary()` to assemble its existing detached projection from finalized engine/runtime/owner inputs without calling `capture_fork_checkpoint()`: its current implementation delegates to that method and therefore cannot serve terminal inspection. Share pure input/projection helpers with checkpoint capture where appropriate, but leave `capture_fork_checkpoint()` terminal/provider/fork-capability guards unchanged. The research exporter may read a terminal boundary only when objective and owner cursors agree, no pending owner finalization/publication remains, and required owner snapshots are available; reject pending, aborted-incomplete or unsupported snapshots explicitly. Capture after `finish_run` before closing resources and record that result-stage identity; do not substitute the previous boundary or compare pre-finish goal state with post-finish state. Inspect every deny-listed subjective store, including institutional memory/decay even if the old count DTO omits it. Synthetic `BlankSlateStoreCounts()` zeros are not evidence. Track invocation counts and first eligible observation tick.
5. Install controlled `MilestoneInterventionArbiter` with exact budgets. Resolve created record/project IDs from earlier committed public event exports in trusted closures. Record proposed/effective commands, acknowledgement and unused milestones as metadata. Assertions about successful actions require APPLIED acknowledgements, not scheduled milestones.
6. Install cultural/lineage/civilization capture before execution. Return their setup/finalization receipts independently of scientific run completion. Failure/disabled/quota states remain explicit; capture off/on/failure must not change objective results or subjective continuation.

### Required Interfaces and Contracts

Benchmark evidence is outer trusted inspection, never an agent input. No benchmark code imports `world._*`, edits runtime private stores, installs facts in an owner ledger, or bypasses engine admission. Probe factories are read-only and must not consume extra random draws or clock calls. Complete results retain source/recipe/config/seed/stochastic identities and evidence high-water boundaries.

### Requirement Evidence

Original Request — all generational invariants; `.ai-factory/ARCHITECTURE.md` — Objective authority and runtime. Existing `runner.py` blank-slate assertion uses zero counts; this task requires independently measured content, not reliance on that assertion.

### Error Handling and Logging

Fail required coverage on rejected/unused overrides; capture publication failure leaves scientific status intact but fails that required acceptance lane. Safe codes include `required_action_not_applied`, `probe_unavailable`, `capture_incomplete`, `publication_failed`. DEBUG aggregate counts, INFO assignment boundaries, ERROR reason codes; never log checkpoint bodies or proposed dialogue.

### Tests and Verification

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_v3_benchmark_execution.py tests/unit/test_generational_matrix_execution.py -q`.

Test real entrant before first invocation, poisoned test-double store detected, terminal fork capture still rejected, terminal research projection available after successful finalization/finish, pending-finalization/publication rejection, missing owner snapshots, rejected command, observer/sink exception, quotas, stepped/normal stop parity, no arbiter in independent research, two assignments with isolated sinks, capture-on/off canonical twins. Compare final projected boundary with the finished result and assert observer failures leave result and command/admission sequence unchanged. A grouped recipe sent to independent executor fails closed.

### Acceptance Criteria

Actual store and admission evidence distinguish unexercised mechanisms from null phenomena. Existing generational execution is unchanged when new optional hooks are absent.

## Task 5: Publish reproducible sibling reports and a bounded CLI

### Intent

Make suite claims independently verifiable and usable without a new API or runner/result schema.

### Implementation Steps

1. Add canonical `civilization-benchmark-run-v1` and `civilization-benchmark-suite-v1` sibling documents. Include suite/scenario/lane/profile, source revision/dirty-state artifact identity, environment, config and recipe references, numeric seed, execution IDs, qualified parent/child references, boundary coverage, checks, outcomes, publication receipts and comparison metadata. Hash canonical artifacts using existing scientific canonical helpers; no operational log digest surrogates.
2. Write immutable per-attempt artifacts and atomically publish the final suite manifest only after referenced bytes verify. Constrain output paths beneath the selected root and refuse symlink/path escapes, identity collisions and completed-artifact overwrite. Store references to existing archives/recordings rather than duplicate private content.
3. Register `palimpsest-matrix civilization-benchmark list`, `run`, `verify`. `run` accepts `--scenario ID` (repeatable), `--profile smoke|research|visual`, `--lane mechanism|research`, `--output PATH`, explicit `--timeout-seconds` (positive), required `--code-revision REV`, and exactly one of `--source-clean` or `--source-artifact-digest SHA256`. Reuse `source_identity_preflight`; revision must be nonempty, digest must be a canonical SHA256 and neither/both source assertions fail preflight. These are caller-supplied attestations, not proof inferred from a missing `.git` directory or a revision string. `list` needs no source assertion; `verify` validates the recorded identity against the manifest and referenced source artifact. For smoke/research profiles default selection is all 30. `run --profile visual --lane mechanism` with no `--scenario` selects only `build_v3_visual_benchmark` and records recipe ID `v3-visual-integration-v1`, outside the 30-case registry/count. Reject visual plus any `--scenario` or `--lane research` with `visual_selection_invalid`; do not silently run all cases or permit arbitrary config-file execution. Default output examples use `/tmp/opencode/v3-44/`.
4. Return exit 0 only when every required execution/invariant/coverage/publication check completed and passed; detected and not-detected outcomes are equally eligible. Exit 1 for failed required gates, 2 for invalid preflight. Required missing prerequisites are `unexecuted`/not-run, never a green release. `verify --require-complete` rejects missing gates. Document no subjective resume: completed artifacts can be verified/reused, incomplete experiments restart in a new attempt namespace with deterministic identity validation.
5. Production composition injects existing SQL repositories and lineage/civilization publishers in `research_runner`, never from `experiments`. Thread the same explicit source identity into independent archive contexts, BN grouped designs, recording manifests and benchmark siblings. Container producers receive it from verified image-build metadata/arguments, never by probing nonexistent Git state. Raw reports contain no credentials, recording payloads, memory or narrative text. Retain safe metadata necessary for audit.

### Required Interfaces and Contracts

Strict unknown-field rejection, exact schema IDs and qualified references; finite numeric values; no NaN/Infinity. Required artifact availability is assessed per arm and selector, not the maximum availability found anywhere in a suite. Receipts identify explicitly absent evidence and eligible denominators. Output status is deterministic except separately labeled operational durations/resources.

### Requirement Evidence

Original Request — auditability and reproducibility; `docs/cultural-evolution-metrics.md` — coverage and seed-block inference; `src/experiments/generational_archive.py` — immutable manifests.

### Error Handling and Logging

Use safe CLI codes for corrupt/missing references and prerequisite failures; redact exceptions at outer boundaries. DEBUG verifier counts, INFO paths/status counts, ERROR codes; no expanded Compose configuration, DSNs or artifact contents.

### Tests and Verification

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_v3_benchmark_artifacts.py tests/unit/test_v3_benchmark_cli.py -q`.

Test deterministic serialization, tampered bytes, mismatched run/seed/high-water/source identity, unknown fields, missing required capture, partial versus empty evidence, symlink escape, interrupted publish, duplicate attempt, visual-only dispatch/rejected combinations and CLI exit codes. Cover missing revision, neither/both assertions, invalid digest, dirty artifact identity and a container-like environment with no Git metadata; no case may silently become source-clean. `uv run --frozen --python 3.12.14 palimpsest-matrix civilization-benchmark list` prints all 30 IDs without DB/network access.

### Acceptance Criteria

A reviewer can verify a report from retained sources. A scientific null passes; a missing required measurement does not.

## Phase Risks and Mitigations

- Shared recorder callbacks can contaminate runs: factories are assignment-scoped and IDs checked on every receipt.
- Probe execution can perturb science: compare clocks/draw counts and canonical twins, including capture failure.

## Phase Completion Checklist

- Verify Tasks 4–5 and update only the index.
- Preserve independent scientific and publication statuses throughout CLI aggregation.
