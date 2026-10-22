# Phase 3: Experiment criteria, final results, and consumers

Plan: [index.md](index.md)
Tasks: 7–9
Depends on: Tasks 1–6

## Objective

Provide trusted injected experiment stopping without giving analysis authority over live world or owner state; finish runs exactly once.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/simulation/runner.py` | `RunnerDependencyFactories` 366+; `run_tick`; `run` 3025–3138; goal evaluation 3837–3866 | Dependencies are injected; `run` currently owns end-of-run goal effects. |
| `src/simulation/runner.py` | `_finalize_and_acknowledge` 2658–2666; `recover_pending_finalizations` 2775–2813 | Receipt deduplication scans the full list; recovery currently fabricates an empty TickResult and bypasses stopping/publication. |
| `src/api/simulation_manager.py` | tick driving 599–659 | Any non-null stop reason completes API execution. |
| `src/experiments/matrix_models.py` | `DEFAULT_SUCCESS_STOP_REASONS` | New scientific stops must not be mislabeled failures. |
| `src/experiments/matrix_manifest.py` | completion validation 553–588 | Matrix resume validates successful reasons, not tick-level continuation. |
| `.ai-factory/ARCHITECTURE.md` | Dependency Rules; Layer/Module Communication | Simulation cannot import analysis or experiments. |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/simulation/generational_control.py` | create | Criterion/observer ports, typed orchestration errors and decisions. |
| `src/simulation/runner.py` | modify | Inject callbacks, execute shared finalized-boundary pipeline, idempotent finishing. |
| `src/simulation/run_control.py` | modify | Optional in-process generational control carry on RunnerRuntimeCheckpoint; no durable subjective codec. |
| `src/simulation/__init__.py` | modify | Public ports and DTOs. |
| `src/api/simulation_manager.py` | modify | Correct completion path and safe new result/reason propagation. |
| `src/experiments/matrix_models.py`, `src/experiments/matrix_runner.py`, `src/experiments/matrix_manifest.py` | modify | Success classification and result compatibility. |
| `tests/unit/test_generational_criteria.py`, `tests/unit/test_runner_finish_run.py`, `tests/unit/test_generational_consumers.py` | create | Callback and consumer tests. |

## Task 7: Add trusted, versioned experiment criterion injection

### Intent

Allow experiment-specific termination without serializing Python code or importing analytical implementations into simulation.

### Implementation Steps

1. Define `ExperimentStopCriterion` protocol: stable `criterion_id`, `version`, and `async evaluate(boundary: GenerationalBoundary) -> CriterionDecision`. Decision is frozen with exact bool `matched` and sorted finite scalar measurement pairs; no free-form messages, commands, or owner content.
2. Extend dependency factories with a criterion factory accepting `ExperimentCriterionSpec`. Default factory rejects any requested criterion with a safe unsupported-ID construction error. Factory must resolve every configured criterion before durable run creation.
3. Evaluate only at finalized boundaries divisible by `criterion_cadence_ticks`, after built-in stops. If a successful built-in/injected stop already matched, do not invoke expensive custom criteria; record `custom_evaluation=skipped_builtin_stop` in stop evidence. At a cadence boundary evaluate all criteria in sorted identity order, retaining every matching ID and selecting the first for the primary experiment criterion.
4. Criterion implementations receive detached objective facts and can close over a read-only evidence reader bound by outer composition. They cannot receive the runner, engine, owner stores, tokens, mutable state, or world mutation callbacks. Analysis implementations remain in `experiments`.
5. Convert both typed and unexpected criterion execution exceptions into `EXPERIMENT_CRITERION_FAILURE` at the finalized boundary; suppress raw exception text/tracebacks and do not retry the objective tick. Place this catch outside the precommit authority/abort-pending exception region so a callback failure never aborts already finalized owners or reports objective rollback. Treat `CancelledError` separately as specified in Task 8, not as a criterion match or an ordinary Exception.

### Required Interfaces and Contracts

No `eval`, import path from JSON, arbitrary plugin discovery, or process-global registry mutation. Unknown IDs/versions or malformed params fail before any world effects. Criterion evaluation must use logical ticks and versioned deterministic policy, never elapsed wall time.

### Requirement Evidence

User experiment-specific stop requirement; architecture trust/dependency boundaries; C6 and C8.

### Error Handling and Logging

DEBUG criterion ID/version, boundary, matched bool and closed failure code; INFO final primary reason only. Do not log params, reader contents, exception payloads, or measurement values capable of containing subjective text.

### Tests

Trusted fake criterion stops at a specified finalized tick; canonical simultaneous matches; cadence; unknown version rejection; pending-finalization failure prevents invocation; callback failure does not duplicate commit; cancellation; no custom invocation after a built-in stop.

### Acceptance Criteria

Both `run` and `run_tick` exercise exactly the same criterion policy and failure behavior; no analysis import enters simulation.

### Verification

`uv run --frozen pytest --cov --cov-report=term-missing tests/unit/test_generational_criteria.py -q`

Expected: callback and authority tests pass.

## Task 8: Centralize finalized-boundary publication and idempotent finishing

### Intent

Prevent a custom driver or historical sampler from skipping/doubling goal finalization or observing half-finalized state.

### Implementation Steps

1. Add `FinalizedBoundaryObserver` port with `async observe(boundary, stop_evidence) -> None`, injected through dependencies. Default is a no-op only when no historical artifact was requested. An observer may persist detached output but cannot return commands or mutate stop policy.
2. Centralize the post-commit pipeline for empty ticks, active ticks, and supported in-process finalization recovery: synchronize entrants; finish owner finalizations/acknowledgements; record tick and goal receipts; advance completed cursor; build progress; evaluate built-ins then criteria; call boundary observer; latch any terminal decision and emit the attempt receipt. Maintain a per-boundary state (`owner_finalization_pending`, `publication_pending`, `published`, or `terminal`) and cached decisions. A repeated call cannot commit another tick while the previous boundary is incomplete.
3. Historical observer failures produce `HISTORICAL_ARTIFACT_FAILURE` with `FINALIZED` attempt status and the actual completed cursor. Preserve any scientific stop matches in evidence. If a criterion already failed, preserve criterion failure as primary and attach the observer failure as secondary diagnostic; never overwrite the more specific earlier failure with success.
4. Extract `async finish_run(stop_reason: RunnerStopReasonCode) -> SimulationRunnerResult` from the terminal portion of `run`. Apply run-ending goal evaluation once and cache the finished result. Repeated identical finishing returns the same value; conflicting reasons or further tick execution after finishing fail closed. Move attempt-receipt accumulation from run's local list into one runner-owned ledger populated by the common receipt-emission path, including direct run_tick driving. Re-reading a latched terminal receipt does not append a new attempt. Finishing both driver styles therefore sees the same attempts/counts; run must not accumulate a second copy.
5. `run()` remains the primary convenience method: loop `run_tick`, then call `finish_run` once. Do not call `run()` repeatedly for chunking. Finalization-recovery-required boundaries must not be converted into successful finished runs or historical samples.
6. On supported in-process recovery, reuse the exact committed `engine.last_tick_result` only after verifying its tick/revision against the pending boundary. Run the shared publication/stopping path once after owner recovery. Do not use the current synthetic empty result with guessed base revision to compute generational hashes or event facts. If exact committed evidence is unavailable, report recovery-required and stop; this plan does not reconstruct arbitrary cross-process subjective state.
7. Cancellation before commit follows existing policy. During owner finalization it preserves recovery-required state. After all owners finalize, cancellation latches `CANCELLED` at the actual boundary when cancellation is allowed; it does not rewind the cursor or rerun cognition. If cancellation is disallowed, preserve the interrupted boundary state and propagate CancelledError for recovery rather than fabricate successful completion. Pending observer writes use immutable `(run_id, boundary_tick)` keys and idempotent same-bytes publication. Delivery may be retried after interruption; exactly-once external callback invocation is not promised. Read-only deterministic criteria must tolerate reevaluation after interruption, while completed cached decisions are reused. A cancelled archive is incomplete unless final required artifact checks succeed; it is never a successful scientific completion.
8. Add a tick-ID set alongside retained finalized receipts; consult it instead of the full-list `any(...)` scan. Initialize it on construction and rebuild once during supported runtime-checkpoint application; detect duplicate/conflicting restored ticks. Preserve existing receipt/hash wire formats. Add optional frozen `generational_control_state` to the Python-only `RunnerRuntimeCheckpoint`, default null for legacy runs, carrying boundary stage, cached decisions, terminal receipt/evidence, attempt receipts, and finish status/result when present. v55 supported checkpoint carry requires it and rejects inconsistent cursors or missing control state; it cannot silently reopen a terminal run. Restore handles/readers/sinks only through injected dependencies, never checkpoint data. This is in-process/fork carry with verified objective-state parity, not a durable restart codec. Task 13 supplies structural complexity tests for lookup/reindexing.

### Required Interfaces and Contracts

Observer publication is post-objective/post-subjective; it is not transactionally rolled back with the already committed world. Its logical boundary record is unique through idempotency, not a guarantee of exactly one I/O callback invocation. Full durable subjective restart is explicitly out of scope. Run-ending goal transitions are not part of a historical objective checkpoint. `finish_run` on a precommit failure may construct a failure result at B=0 but must not claim a finalized tick; it must not apply run-ending goal effects while owner finalization remains incomplete.

### Requirement Evidence

User historical checkpoint request and inspection/replay clarification; existing `run` goal-evaluation behavior; C4/C6/C8.

### Error Handling and Logging

INFO completion once, DEBUG observer begin/end and finish-cache hit using safe IDs/counts. ERROR stable artifact/criterion reason and boundary; no raw filesystem paths, payload exceptions, or configured contents.

### Tests

Observer ordering relative to finalizations/cursor; empty/recovered tick same path; typed/unexpected sink and criterion errors after commit; criterion+sink double failure; precommit B=0 failure result; cancellation during finalization/criterion/observer; retry of an already-published immutable boundary; exact live TickResult recovery versus unavailable-evidence rejection; terminal latch; checkpoint lookup reconstruction; idempotent finishing and no duplicate goal receipts. Stopping drivers produce identical results/hashes.

### Acceptance Criteria

One logical boundary publication per finalized tick through idempotent keys, no skipped stopping after supported recovery, no tick after a latched terminal result, and at most one terminal goal evaluation per finished run.

### Verification

`uv run --frozen pytest --cov --cov-report=term-missing tests/unit/test_runner_finish_run.py tests/unit/test_generational_criteria.py -q`

Expected: no double finalization or misreported rollback.

## Task 9: Update API and matrix stop/result consumers

### Intent

Make new scientific stops usable through existing public execution surfaces without a protocol rename.

### Implementation Steps

1. In `simulation_manager.py`, preserve the reason and actual completed boundary. Use the simulation-owned classifier, not `stop is not None`, for terminal lifecycle selection: max-tick/all-terminal/injected and the four scientific generational stops become `COMPLETED`; cognition/authority/criterion/artifact failures become `FAILED`. Retain existing cancellation and recovery control paths rather than treating them as scientific completion. Propagate actual progress when recording failure, and release the lease on either terminal outcome. Call `finish_run` once for fully finalized terminal attempts before completion publication; do not force finishing an owner-recovery-required boundary.
2. Keep API composition fail closed for criteria or historical sinks it cannot inject. A request must fail construction rather than silently omit requested orchestration. No API LLM lifecycle expansion is included.
3. Add generation horizon, population extinction, population threshold, and experiment criterion to `DEFAULT_SUCCESS_STOP_REASONS`; do not add artifact/criterion failures. Reuse the classification in completion validation.
4. Preserve runner-result-v3 payloads, stop evidence, and actual generation mappings across coordinator/matrix results. Do not classify extinction as execution failure merely because the outcome is demographically negative.
5. Add consumer tests for result serialization/projection, typed failure propagation, and old matrix completion acceptance. Keep `/v1`, WebSocket protocol, observer semantics, and existing response fields stable; additional structured result data travels through the existing versioned result envelope only.

### Required Interfaces and Contracts

Matrix resume still reruns incomplete cells from origin. No checkpoint-resume command or cross-process subjective restoration is claimed. Do not silently reinterpret stored old completions as v3 outputs.

### Requirement Evidence

User stop support; existing API tick driver; default success allowlist; C1/C3–C6.

### Error Handling and Logging

Keep existing safe API/matrix errors; INFO terminal code and completed tick. Output must distinguish a valid scientific stop from orchestration failure.

### Tests

API tick-driven generation stop becomes COMPLETED; criterion/artifact/cognition/authority failures become FAILED with exact committed progress and lease release; cancellation/recovery never becomes false completion; missing callback dependency rejected before run creation. Extinction matrix completion is accepted; failures are not. Test old manifests and result-v3 roundtrip. Drive the real manager transition path, not only the classification helper.

### Acceptance Criteria

No consumer converts a new scientific stop to generic failure or loses its reproducibility evidence.

### Verification

`uv run --frozen pytest --cov --cov-report=term-missing tests/unit/test_generational_consumers.py tests/unit/test_experiment_matrix_resume.py -q`

Expected: legacy resume and new consumer tests pass.

## Phase Risks and Mitigations

- Callback side effects cannot be rolled back after world commit: fail at the recorded boundary and never automatically replay it.
- API and matrix may lack optional dependencies: reject requested unsupported features at construction rather than falling back.
- Preserve sequential preparation (`prepare_parallel=False`) and ordinary engine admission.

## Phase Completion Checklist

- Tasks 7–9 meet acceptance criteria and commands pass.
- Update only the index progress ledger.
