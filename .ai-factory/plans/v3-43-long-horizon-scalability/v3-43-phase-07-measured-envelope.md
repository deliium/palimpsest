# Phase 7: Repeated scale acceptance and evidence-backed operating envelope

Plan: [index.md](index.md)
Tasks: 19–21
Depends on: Tasks 1–18

## Objective

Finish with reproducible measurements and exact, qualified support statements—not a promise that any 100k-tick population, feature mix or browser will work. Missing infrastructure cannot silently waive acceptance.

## Current-Code Evidence

| Path | Symbols / section | Why it matters |
| --- | --- | --- |
| `tests/benchmarks/harness.py` | metric/target helpers | Existing timing proxy and process-lifetime RSS require honest before/after interpretation. |
| `tests/integration/test_generational_scale.py` | sparse 100k fixture | Preserve it as a sparse durability lane, not the dense scalability certificate. |
| `tests/integration/test_append_only.py` | scale-table mutation rejection | No optimization may weaken history triggers. |
| `tests/unit/test_v1_regression_gate.py`, `tests/unit/test_v2_scientific_invariants.py` | flags-off baseline | New infrastructure must preserve scientific gates. |
| `docs/development.md` | scale and pinned Godot commands | Extend the documented workflow, not a parallel unsupported toolchain. |
| `docs/generational-runner.md` | historical archive contract | Objective historical inspection is not full subjective restart. |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `tests/benchmarks/test_v3_long_horizon.py`, `test_v3_historical_queries.py`, `v3_measurement.py` | modify | Paired before/after execution and actual query/playback/storage measurements. |
| `tests/benchmarks/v3_support.py` | create | Evidence-backed envelope generation/validation. |
| `tests/unit/test_v3_scale_support.py` | create | Reject unsupported/extrapolated claims. |
| `tests/integration/test_append_only.py` | modify | Cover preserved immutable tables and archive-copy noninterference. |
| `docs/long-horizon-scalability.md` | create | Reproduction, measured envelope, resource trade-offs and explicit exclusions. |
| `docs/development.md`, `docs/generational-runner.md`, `docs/persistence.md` | modify | Benchmarks, retirement/checkpoint/archive semantics and operational prerequisites. |
| `docs/lineage-explorer.md`, `docs/cultural-evolution-metrics.md`, `docs/observer.md`, `docs/research-ui.md` | modify | Deep paging, coverage, incremental subset and client constraints. |
| `README.md` | modify | One concise documentation-index link. |

The three V3 benchmark paths in the first row are introduced by earlier tasks in this bundle; they are modifications by the time Phase 7 starts, not existing baseline files.

## Task 19: Run paired 10k/100k, dense-generation and historical-query acceptance

### Implementation Steps

1. Repeat Task 2 baselines through Task 1's supervised fresh worker processes with identical domain run/world/branch identities, seeds/stochastic identities/configurations, budgets and profiler/coverage state after each optimization group. Use separate disposable storage/output namespaces for baseline/candidate/repetition isolation, not UUID changes to scientific IDs. Artifacts must identify source revisions and immutable input hashes. Do not compare different scientific workloads or a sampled capture against an originally complete capture.
2. Execute 10k and 100k for sparse/control, sustained-generation and evidence-rich lanes; record explicit incomplete outcomes when a budget is reached. Retain at least three completed repetitions for a repeatable execution claim. Measure large-event logs independently so an empty/extinct 100k run cannot satisfy high-volume coverage.
3. Collect execution throughput, peak RSS, live/frozen owner counts, actual checkpoint serialization/write cost, SQL/segment bytes and rows, evidence/finalization peaks, archive export/verify time, exact incremental/batch metrics cost, historical seek/event-prefix latency and lineage physical read amplification.
4. Measure warm query p50/p95 over at least 30 samples and separate process-cold samples. Run browser/playback acceptance with at least 50 alternating seeks and several observer clients; report browser frame time/heap only when actually measured. Backend-only/synthetic evidence is never presented as interactive browser performance.
5. Require exact Task 3 parity and long-dead queryability in every completed candidate. A speedup achieved by truncated required provenance, changed metrics, fewer active cognitive ticks or reduced scientific stop horizon is invalid.
6. Add cost assertions for operation counts and resource caps to routine tests. Exercise the actual supervisor against a controllable short worker to prove timeout, memory breach, unexpected exit and missing completion cannot pass. Timed-out/killed runs retain a partial measurement with last observed verified boundary and source history intact. Unsupported process RSS accounting is recorded as unenforced, not zero or a satisfied budget. Do not put noisy universal wall-time thresholds in unit CI. An optimization retained as enabled/recommended must improve its targeted measured cost; if the improvement is within observed noise, keep the reference implementation/path and report the finding rather than inventing an unplanned optimization.

### Required Interfaces and Contracts

No new production interface. Budget exhaustion is a recorded experimental result, not authorization to delete evidence. A completed scientific run with failed required capture is not a complete evidence-rich scale case. DB/browser/Godot prerequisite failures remain visible blockers to the corresponding support claim.

### Requirement Evidence

User: all named benchmark categories and measured limits. Plan Task 1 measurement status/identity and Task 3 equivalence oracle.

### Error Handling and Logging

INFO lane/repetition/count/duration/status summaries; WARN incomplete/failed measurement. Avoid per-tick verbose floods in timed runs: verbosity means bounded diagnostic aggregation, never payload logging. Record profiler state instead of disabling coverage silently.

### Tests and Verification

Run Task 1's durable command at `PALIMPSEST_SCALE_BENCH_TICKS=10000` and `100000`, Task 18's query/browser commands, and existing sparse generational scale integration suite. Store outputs under `/tmp/opencode/v3-43-scale/` or an explicitly configured CI artifact directory. These commands are implementation gates; no successful execution is claimed by this planning invocation.

### Acceptance Criteria

Every requested benchmark category has completed or explicitly failed/unexecuted artifacts with reasons. At least one genuine sustained multi-generation lane completes and preserves history. If 100k cannot complete, the envelope explicitly stops at the largest verified workload/horizon, with the 100k limitation documented; no 100k support claim is allowed.

## Task 20: Validate the measured support envelope and operational recommendations

### Implementation Steps

1. Add a benchmark-only `v3-scale-envelope-v1` generator/validator. Each row references exact complete measurement artifact identities, scenario/configuration, horizon, living/total population, generations, event/evidence volume, enabled modes, capture coverage, checkpoint cadence, retirement/spool/layout selection, hardware/software, repetitions, resource use and observed latency distributions.
2. Support statuses are `verified`, `tested_incomplete`, and `unverified`. `verified` requires the relevant completed repetitions, correctness gates, coverage and platform/client prerequisites. Largest measured successful horizon is verified-through coverage, not a hard universal maximum. Never infer 100k from 10k, dense from sparse, browser from backend, or arbitrary population capacity from tick count.
3. Derive checkpoint recommendations only from tested existing cadence candidates and their measured storage/write/seek trade-off. State which limiting resource dominated. Runtime retirement, optional disk spool and physical paging stay explicit composition choices with tested off/on rows; no scientific feature gets silently disabled to fit the profile.
4. Record remaining cumulative costs: objective bodies/genealogy/records, complete event/resolution exports, immutable owner DTOs, fork/result materialization, global graph algorithms and total disk. Estimates of future storage are labelled extrapolation with measured per-unit costs and assumptions, not supported limits.
5. Require an investigation disposition for snapshots, cold tier, partitioning, indexes, analytical views, incremental metrics, lossless lineage compression, bounded loading, pagination, streaming and batch analytics. This plan's fixed implementation choices are documented in the index; measured results may narrow support, not authorize unplanned destructive or semantic changes.

### Required Interfaces and Contracts

The envelope is a benchmark/documentation artifact, not runner validation or a scientific schema field. It must not reject formerly accepted configs merely because that workload has not been benchmarked. No capability flag, `/v2`, SQL head bump or arbitrary default maximum.

### Requirement Evidence

User's final requirement: actual supported limits from measured repository performance. Architecture: compatibility and default-off behavior; current docs explicitly disclaim constant-memory/bounded-disk guarantees.

### Error Handling and Logging

Reject mismatched baseline/config identity, missing evidence, false completion, insufficient repetitions or missing client measurements with safe validation codes. INFO verified/incomplete/unverified row counts; no payload content.

### Tests

`test_v3_scale_support.py`: sparse cannot certify dense; 10k cannot certify 100k; extrapolated values cannot become verified; truncated capture cannot certify complete evidence; missing DB/browser gates; paired identity mismatch; checked sample counts; failed correctness overrides fast timing; measured-through label versus universal maximum.

### Acceptance Criteria and Verification

`uv run pytest tests/unit/test_v3_scale_support.py --cov=experiments --cov=research_runner --cov-report=term` passes. The generated envelope contains no unsupported capacity claim and every verified row is traceable to actual completed measurements.

## Task 21: Complete regression/security boundaries and mandatory documentation checkpoint

### Implementation Steps

1. Run unit/architecture, Ruff, mypy and import-linter gates. Add/extend append-only integration checks for authoritative events/commits/snapshots/projections, scientific outbox and cognition traces; archive exports and analytical views must not weaken any trigger or mutate source rows.
2. Reconfirm flags-off V1/V2 gates, default runner v4/result v2, latest feature runner v55, 43 commands, 73 observer semantic types, 136 metric families, replay-v22/codec-v20 selection, Alembic `0017`, stable `/v1` and observer protocol. Physical archive/layout/derived-view siblings are explicitly separate from these scientific versions.
3. Invoke `$aif-docs` as the mandatory implementation documentation checkpoint. Write `docs/long-horizon-scalability.md` with exact commands/prerequisites, measured envelope references, sparse/dense/evidence-rich distinctions, budgets, archive verification, no-source-deletion rule, retirement/fork semantics, historical availability, client paging controls and remaining limits. Update only relevant sections of the listed existing pages plus README index.
4. Include safe operation guidance: disposable benchmark DBs, storage permissions for private exports, archive hash verification, resource monitoring, disabled/default paths, explicit capture budgets, restart limitations and how to diagnose/continue limited queries. Document that cold copies add storage and cannot authorize DELETE/TRUNCATE/partition detach/GC.
5. Do not create/close roadmap milestones from this plan. M7 linkage is supporting infrastructure and does not own `institutional_economy`, kinship handoff or remaining V2 testimony tracking. The implementation's verification output must enumerate skipped infrastructure gates instead of equating them with passes.

### Required Interfaces and Contracts

No new implementation interface beyond earlier tasks. Documentation must reflect measured evidence or explicitly state unverified status. No final narrative-report deliverable substitutes for runnable tests and the maintained documentation checkpoint.

### Requirement Evidence

User preservation constraints; project rules; configured tests/docs preferences; architecture's downstream V3 checklist.

### Error Handling and Logging

Fail completion on correctness/security regression or altered append-only behavior. Missing optional environments limit claims and remain explicit; no secret-bearing logs or full artifact dumps. Documentation must not conceal residual O(history) costs.

### Tests and Verification

- `uv run ruff check src tests`
- `uv run mypy`
- `uv run lint-imports`
- `uv run pytest --cov --cov-report=term`
- `uv run pytest -m integration tests/integration/test_append_only.py tests/integration/test_history_archive.py tests/integration/test_replay_bounded_reads.py tests/integration/test_v3_historical_query_safety.py --cov --cov-report=term`
- Task 16 pinned Godot commands, `pnpm --dir clients/research-ui check`, `pnpm --dir clients/research-ui test`, and Task 18 configured browser acceptance.

### Acceptance Criteria

All applicable correctness/quality gates pass; mandatory docs checkpoint completes; exact measured support statements and unexecuted environments are visible. No provenance is removed. Update Task 21 only after these requirements are satisfied.

## Phase Risks and Mitigations

- Time/infra budget may prevent 100k or browser execution: disclose and narrow the verified envelope; do not fabricate or extrapolate support.
- CI and developer machines vary: pin configuration/instrumentation and publish environment-qualified measurements, not universal latency promises.
- A complete fork/export may still peak in memory: measure it as a distinct operation and state its separate envelope.

## Phase Completion Checklist

- Tasks 19–21 have real evidence, exact gates and maintained documentation.
- Support claims distinguish verified, incomplete and unverified work.
- Update progress only in `index.md`.
