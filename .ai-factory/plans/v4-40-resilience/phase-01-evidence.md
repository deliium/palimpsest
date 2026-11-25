# Phase 1: Shock clocks and finalized evidence

Plan: [index.md](index.md)  
Tasks: 1–3  
Depends on: V4-39's committed v63 behavior being available in the implementation tree.

## Objective

Collect bounded, detached evidence exactly once per finalized boundary and index real shock episodes without treating skipped receipts, a planned schedule, or an empty event batch as the same thing.

## Current-Code Evidence

| Path | Symbols | Why it matters |
|---|---|---|
| `src/simulation/v4_architecture.py` | `V4ContextId.SOCIETAL_RESILIENCE` | Existing detached context, no flag or registry change. |
| `src/world/events.py` | `DisasterResolved`, `DisasterOutcome`, `WorldEvent` | Private objective receipt; only `APPLIED` anchors an episode. |
| `src/simulation/runner.py` | `initialize_finalized_boundary`, `run_tick`, `finish_run`, `_detached_boundary_inputs`, `_engine_snapshot` | Authoritative sampling timing; current research export contains unnecessary full owner state and a repeated event prefix. |
| `src/simulation/runner_models.py`, `src/simulation/persistence.py` | `FinalizedTickReceipt`, `WorldSnapshot` | Independent finalized event counts; objective stock, body, item and infrastructure facts. |
| `src/simulation/engine.py`, `src/simulation/_history.py` | `last_tick_result`, `_prepare_tick_candidate`, `admit_population_entry`, `HistorySequence.__len__` | Normal admissions can be inside a tick batch, but direct admission can append outside it. Last-batch reads avoid whole-history `export_events()`. |
| `src/simulation/agent_runtime.py` | `_cultural_channel_export`, `export_civilization_owner_state` | Channel enablement is independent of ledger presence. |
| `src/experiments/science_diffusion_capture.py` | `run_with_science_diffusion_capture` | Existing single-execution wrapper and post-finish terminal sampling pattern. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/analysis/resilience_windows.py` | Create | Closed policy, evidence interval validation, episode and window selection. |
| `src/simulation/resilience_evidence.py`, `src/simulation/runner.py`, `src/simulation/engine.py`, `src/simulation/agent_runtime.py` | Create / modify | Narrow, inspect-only point witness; reuse finalized boundary guards, ecology capacity and owner channel evidence. |
| `src/experiments/resilience_capture.py` | Create | Default-off driver, bounded accumulator, sealed evidence and receipt projection. |
| `tests/unit/test_resilience_windows.py`, `tests/unit/test_resilience_capture.py` | Create | Pure policy tests, finalized-boundary and failure-path tests. |

## Task 1: Define committed shocks and window coverage

### Intent

Make “before” and “after” reproducible without interpreting a plan as an event or attributing one shock's aftermath to another.

### Implementation Steps

1. In `resilience_windows.py` define `RESILIENCE_POLICY_ID = "societal-resilience.v1"`, `ShockReceipt(tick, sequence, event_id, kind, origin, outcome)`, `ShockEpisode`, `WindowSpec`, and closed coverage/state enums. A shock's identity is run-qualified by `(run_id, tick)`; attach all and only applied receipts at that tick, sorted by `(sequence, event_id)`. Keep separate aggregate non-applied receipt counts by outcome (including `no_effect`); no skipped receipt starts or censors an episode. Independently classify each configured schedule entry by `(tick, rule_id)`: `applied` or `not_applied` only for a matching committed **scheduled** receipt; `not_reached` if `tick >= finalized_through`; `unverified` if the tick ran but is beyond the sealed prefix; `receipt_missing` if the tick is verified and there was no matching receipt. An unmatched or duplicate scheduled receipt within a batch is an evidence mismatch, not a new schedule entry. Never expose effects, targets, or private disease rows in the report.
2. `build_shock_windows(receipts, *, finalized_through, capture_through)` constructs one baseline and eight follow-up slots, indexed `-1, 0..7`. For shock event tick `s`, baseline is `[s-8,s)` and post slot `i` is `[s+8*i,s+8*(i+1))`. Boundary `b` is state after ticks `< b`; snapshot sample is at the interval's exclusive end. Thus event `s` is never in the baseline. Keep signed conceptual interval coordinates even when a slot predates run start.
3. A window is structurally usable only if all eight ticks and both endpoint boundaries are in the sealed prefix. A prior applied shock inside the baseline invalidates it (`overlapping_baseline`). Censor the first post slot containing any later shock and all following slots (`later_shock`); a later shock exactly at a slot's exclusive end does not invalidate that slot. Never shorten or blend slots, shift anchors, extrapolate, or use “last event” as a snapshot. If baseline is censored but a post slot is usable, emit raw measures, not baseline-relative measures.
4. For otherwise eligible windows distinguish `complete`, `partial`, `unavailable`, `censored`; closed reason precedence is overlap, pre-run, run end, capture gap, channel off, projection gap. Record expected and observed interval ticks (0–8) and report nullable values for non-complete lanes. Complete, applicable empty sets can emit count zero. Ratios with a zero denominator remain null with numerator/denominator retained.
5. Each episode also has an immediate state point at boundary `s+1`, separate from the nine cells. It uses only verified boundary `s+1` and looks no further. A later shock at tick `s+1` cannot censor this point. Compare its point values with boundary `s` if that boundary is verified, even if the eight-tick pre window extends before the run; if a prior applied shock falls in `[max(0,s-8),s)`, publish raw point values but no immediate deltas. Keep immediate deltas separate from window deltas. Only a full post window can contribute to the two-consecutive-post-points technology statistic.

### Required Interfaces and Contracts

- Deterministic sorting, no wall clock; reject duplicate event IDs or duplicate cursor keys, non-canonical event order, and receipts beyond the sealed prefix. Validate bounded integer fields as exact integers. A fully captured run with no applied receipts and no missing scheduled receipt has `no_shock`; capture gaps or unexpected missing receipts cannot attest that no shock occurred.
- Requirement evidence: original request, roadmap M8 next plans, `docs/disasters.md` scope, and architecture's versioned-extension contract.

### Error Handling and Logging

Pure code: no logs; reject invalid input with closed `ResilienceError` codes, not evidence-bearing exception strings. Right-censoring is a normal result, not an error.

### Tests / Acceptance / Verification

`tests/unit/test_resilience_windows.py`: tick zero; event exactly at `s`, `s+1`, `s+8` and `s+64`; co-tick and later applied receipts; scheduled/no-effect/skipped/not-reached/unverified/receipt-missing; overlapping baseline; short horizon; gap before shock; empty full vs empty partial; duplicate identifiers. Assert one immutable ordered window axis for all ten lanes, a separate immediate state point, and no shock inferred from config alone.

Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_resilience_windows.py -q`; all policy cases pass.

## Task 2: Export narrow finalized boundary evidence

### Intent

Use a fixed boundary clock for both stock and owner/physical state; do not add another event, persisted world format, or private-state dependency in analysis.

### Implementation Steps

1. Add `ResilienceBoundaryFacts` and frozen, sorted row DTOs in `simulation.resilience_evidence`. `await SimulationRunner.export_resilience_boundary()` shares an extracted guard with `_detached_boundary_inputs` for started state, runner/engine agreement, pending finalizations, and terminal rules (`allow_terminal=True`); preserve all existing fork/research guards and error precedence. A terminal point is exportable only after `finish_run` has succeeded, and a nonzero boundary must have its preceding finalized tick receipt. Compute the live body projection hash independently via `objective_projection_hash(WorldEngine.detached_objective_projection())` and compare it with the receipt (null witness at zero); do not copy the receipt hash as its own corroboration. Return run/config identity, boundary tick, revision, independently calculated body hash witness, history length and safe rows only. Expose history length as a read-only engine property backed by `len(self._snapshot.event_history)`. No invocation from ordinary runner execution.
2. Project engine-owned physical data using the existing `_engine_snapshot` read inside `simulation/runner.py`; do not hold or export `WorldSnapshot`. Keep living registered body tokens and their held-item counts (include zero; no items in stores or on corpses); track registered body tokens also for entry identity. Keep managed stock ID, kind, unit and quantity/capacity in tenths, and infrastructure asset ID, kind, topology endpoints, and status. For capacity, project the existing `world._ecological_resources.effective_capacity_tenths` via an engine-owned detached helper in `src/simulation/engine.py` (only the engine imports private world modules); do not duplicate renewal or re-fold pressure-stage receipts. Project absent infrastructure as off, present-empty as enabled. Keep region assignment from `RegionsMigrationSpec.location_regions` as IDs only.
3. Add `AgentRuntime.export_resilience_owner_keys()` in `src/simulation/agent_runtime.py`, projecting only recognized concept IDs and active practical-knowledge content keys, with separate per-source states. Reuse `_cultural_channel_export`'s disable/fresh-empty/carried/missing decisions for knowledge and the runtime's active institution-mode predicate used by `export_civilization_owner_state`; do not build full checkpoints/owner exports. For institution concepts, active mode plus no ledger is known fresh-empty only at a proven fresh founder or admission boundary before the first executed update, otherwise unsupported. For either lane validate the typed ledger and its owner against the registration; project `off`, `complete` (including empty), or `unsupported`, never infer off from `None`. Knowledge measures carried inventory scope, not eligibility to update it on the current tick. Use each admitted owner's actual runtime mode, not the founder template. A missing living runtime/source is not a death; a proven dead owner never calls the exporter. No memories, labels, raw checkpoints, disease states, observations, prompts, seed payload, or messages cross the witness.

### Required Interfaces and Contracts

- This is a standalone public research submodule; preserve observer DTOs, default execution and all persistence codecs. Only simulation reads the snapshot; analysis reads the sanitized neutral contract. Source authority: architecture dependency and finalized-boundary rules, existing snapshot and ledger contracts.
- Caps: check registered roster ≤128 before owner projection, ≤256 managed stocks, ≤512 infrastructure assets and ≤4,096 total normalized row entries per frame; overflow of a whole frame is not a truncated complete snapshot. Use bounded validation before copying further into the accumulator.

### Error Handling and Logging

Known unsupported owner lane becomes a local gap, not failure of physical lanes. Invalid run/tick identity, inconsistent roster or cap overflow rejects the frame. No logging raw values here; wrapper logs closed stage/reason and counts.

### Tests / Acceptance / Verification

`tests/unit/test_resilience_capture.py`: valid zero, finalized point, abort/pending/unfinished terminal rejected, terminal sampled once after finish, bad body-hash witness, no raw checkpoints/ledgers in DTO, disabled vs fresh-empty vs missing, newborn using a different mode than founders, and known dead holder excluded rather than counted as a missing living owner. Check v63 stock quantity directly against physical boundaries around the post-pressure disaster stage.

Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_resilience_capture.py tests/unit/test_disaster_stock_effects.py -q`; projection contains only allowlisted fields and leaves the runner state unchanged.

## Task 3: Seal capture without steering execution

### Intent

Give the analysis an auditable single-run prefix and keep research failures away from the scientific result.

### Implementation Steps

1. In `experiments.resilience_capture` add `async run_with_resilience_capture(runner, *, capture: bool = False) -> ResilienceCaptureResult` returning the original result and a closed status; keep sealed inputs internal to the bridge. Accept fresh disasters-active v63 runs with horizon ≤512 and empty engine history at boundary zero; disabled/unsupported/pre-start roster too large calls `runner.run()` unchanged and returns no report. Do not install an arbiter, stop selector, observer mode, runtime callback, or runner-config sibling.
2. For eligible runs follow the existing wrapper: initialize and sample boundary zero; drive `run_tick()` with exactly the normal stop semantics; sample only `FINALIZED` nonterminal boundaries; `finish_run` once; sample a successful terminal boundary after finish, without duplication. Capture exceptions seal immediately at the last fully accepted point and continue ordinary runner execution. Scientific abort or recovery-required results never produce a reportable prefix; do not catch `run_tick` or `finish_run` failures as analytical failures. Close the runner only if the caller already owns that responsibility.
3. At each finalized sample use the existing `WorldEngine.last_tick_result.events` tuple and the boundary's history length; never call whole-history `export_events()`. Before projecting any rows, check the batch fits the remaining budget, that its tick and resulting revision match the point, and that history length advanced by exactly the batch count since the previous accepted point (zero is valid). Validate the consecutive batch cursor, unique event IDs, and event tick/run/world identity. Tick-batch admissions are accepted normally; out-of-band append (including direct engine admission) is not a batch and seals before its first affected boundary with a distinct `history_append_mismatch` reason. After finish check each accepted batch against the corresponding `result.finalized_tick_receipts` count, resulting revision and independent body hash; do not require base revision to equal prior resulting revision as a substitute for the batch/append checks. Keep bootstrap facts as frame zero with no events. The receipt hash attests only the body projection. Cap at 50,000 events cumulative, 65,536 normalized frame entries cumulative, and 32 applied shock ticks, sealing **before** the first overflow/mismatch with no later resumption. Use committed end for right-censoring and verified end for capture gaps. This is in-process evidence, not durable journal verification.
4. In the experiment bridge project committed `Died`, `JourneyArrived`, `Helped`, `Fed`, `ProjectContributed`, and `ExchangeCompleted` into typed row facts as specified in Phase 2. Project the typed schedule to `(tick, rule_id)` and join committed scheduled receipts using the same fields. Retain only safe schedule status/outcome/receipt reference metadata; drop targets, effects and all other raw events. Only dimensions' aggregate output enters the report.

### Required Interfaces and Contracts

- Capture states `disabled`, `unsupported`, `captured`, `sealed`, `aborted`; `captured` means all requested capture boundaries, not all ten dimensions observable. No implicit recovery/resume or capture from sparse history. Use `runner_config_fingerprint`, no changed world/result bytes or old API exposure. Caps and prefix behavior are analysis constraints, never world limits.
- Requirement evidence: `AGENTS.md`, architecture's trusted capture/physics split, `run_with_science_diffusion_capture`, and runner finalization receipts (not event count inferred from lack of events).

### Error Handling and Logging

DEBUG accepted boundary tick plus row count; INFO completion/status and prefix size; WARN once on seal with reason/stage and run ID. Do not log rows, raw exception messages, health/exposure, payload hashes, or owner values.

### Tests / Acceptance / Verification

`tests/unit/test_resilience_capture.py`: failed capture, cap atomicity (including an oversized last batch without projecting its rows), rollback/abort, pending recovery, unknown batch versus verified empty batch, normal committed population entry, an extra out-of-band history append that seals explicitly and preserves earlier frames, no double-run/finish or sampler call with capture disabled. Make whole-history export raise in the capture path to catch regressions; compare off/on normalized objective events outside capture, plus state hash, cognition counters and stop evidence.

Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_resilience_windows.py tests/unit/test_resilience_capture.py -q`; capture never controls world execution.

## Phase Risks and Mitigations

- Disaster stock effects run after pressure receipts; sample the sealed objective boundary instead of applying the older pressure-only history fold.
- Distinguish incomplete capture from an originally short run and from incomplete owner sources. Keep coverage independently of arrays.

## Phase Completion Checklist

- Tasks 1–3 satisfy acceptance; targeted tests pass; mark their boxes only in `index.md`.
