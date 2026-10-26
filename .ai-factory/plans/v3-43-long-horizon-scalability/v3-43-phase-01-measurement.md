# Phase 1: Reproducible measurement and scientific equivalence

Plan: [index.md](index.md)
Tasks: 1–3
Depends on: none

## Objective

Make 10k/100k-tick claims reproducible before changing execution or storage. Establish workloads, bounded measurement, and a semantic-equivalence oracle that every later phase must use. Tick counts are benchmark inputs, not promised supported limits.

## Current-Code Evidence

| Path | Symbols / section | Why it matters |
| --- | --- | --- |
| `pyproject.toml` | pytest markers, lines 99–114 | `scale` is opt-in and also integration; default tests exclude integration/Compose. |
| `.ai-factory/plans/v2-long-experiment-scalability.md` | Compatibility contract; Verification notes | Existing scale work must be extended, not repeated; measured long-horizon coverage is not established by checked task boxes. |
| `.ai-factory/ARCHITECTURE.md` | Current baseline; requirements for later changes | Stable schemas, deterministic execution, finalized evidence and owner isolation remain mandatory. |
| `tests/benchmarks/harness.py` | `ScaleBenchMetrics`, `resolve_tick_targets`, `build_scale_config` | Existing harness/environment variables must be extended, not replaced; snapshot time is currently a proxy. |
| `tests/integration/test_generational_scale.py` | 100k sparse-cohort fixture | Existing 100k coverage includes empty-population intervals and does not establish sustained cognition performance. |
| `src/experiments/generational_runner_scenario.py` | BL baseline | Reuse validated v55 construction for dense generational workloads. |
| `src/memory/service.py` | `InMemoryMemoryService` 65–148, 182–208, 269–334, 440–489 | Trace/provenance/idempotency collections and transaction copies grow; forgotten traces are tombstoned, not deleted. |
| `src/agents/cognition/practical_knowledge.py`, `src/agents/cognition/institutional_memory.py` | bounded ledger limits | Distinguish already-bounded per-owner ledgers from cumulative retained owners and audits. |

## Files to Change

All paths marked new below are proposed additions, not existing interfaces.

| Path | Action | Required change |
| --- | --- | --- |
| `tests/benchmarks/v3_workloads.py` | create | Deterministic workload builders and immutable workload manifest. |
| `tests/benchmarks/v3_measurement.py` | create | Bounded metadata-only samples and canonical measurement artifacts. |
| `tests/benchmarks/v3_supervisor.py` | create | Fresh-process repetitions, enforced timeout/RSS budgets, bounded worker heartbeats and truthful incomplete results. |
| `tests/benchmarks/harness.py` | modify | Reuse tick-target resolution/RSS helpers; replace the snapshot timing proxy with measured values while keeping legacy metric readers compatible. |
| `tests/benchmarks/test_v3_long_horizon.py` | create | Opt-in execution, queries and comparison driver. |
| `tests/unit/test_v3_scale_workloads.py` | create | Small network-free workload/measurement validation. |
| `tests/unit/test_v3_scale_equivalence.py` | create | Small exact scientific-history and evidence equivalence checks. |

## Task 1: Define realistic V3 workloads and measurement contracts

### Intent

Prevent a 100k-tick empty world or already-extinct population from being advertised as a multi-generation cognitive simulation.

### Implementation Steps

1. Introduce frozen `V3ScaleWorkload` and `V3ScaleMeasurement` test-helper records. Use strict canonical JSON with sibling identifier `v3-scale-measurement-v1`; do not modify runner/result, event, observer or metric schemas.
2. Define four workload lanes: a cheap flags-off/V1 control; sustained multi-generation v55 population with continuing admissions and bounded concurrent living population; an evidence-rich multi-generation lane using existing record/knowledge/cultural/institution modes; and a persisted historical-query lane built from the same completed scientific run. Reuse supported presets and applicators rather than inventing new scientific mechanisms. Keep an explicit cognitive architecture identity in the manifest.
3. Run each lane at a short smoke horizon, 10,000 ticks and 100,000 ticks. Reuse `PALIMPSEST_SCALE_BENCH_TICKS`/`resolve_tick_targets` for horizons; add `PALIMPSEST_SCALE_BENCH_REPETITIONS`, `PALIMPSEST_SCALE_BENCH_SEEDS`, `PALIMPSEST_SCALE_BENCH_OUTPUT`, `PALIMPSEST_SCALE_BENCH_TIMEOUT_SECONDS` and `PALIMPSEST_SCALE_BENCH_MAX_RSS_MB` only in test helpers. Validate positive bounds before database initialization; no benchmark starts by default in the unit suite.
4. Record exact workload configuration identity, seed/stochastic identity, source revision, Python/PostgreSQL/Godot/browser versions where used, CPU/RAM/storage, database settings, checkpoint cadence, capture/tracing modes, concurrency, coverage/profiler state and completed horizon. Seeds/configuration identities belong in scientific benchmark artifacts, not operational logs.
5. Include actual completed ticks, births/deaths, living/total roster sizes, cognitive invocations after death, event rows/bytes, snapshots/bytes, memory/provenance/record/lineage/trace counts, and capture publication availability. Assert multiple completed cohorts and continuing cognitive work for the generational lane; label any early stop or extinction explicitly.
6. Add `run_scale_worker(spec, *, timeout_seconds, max_rss_bytes) -> V3ScaleMeasurement` in `v3_supervisor.py`. The parent launches one fresh worker per repetition with an explicit worker-mode guard to prevent recursive spawning, monotonic deadline, bounded stdout/stderr capture, and periodic process RSS checks. On Linux read `/proc/<worker_pid>/status` and account worker descendants; unavailable RSS enforcement is explicit and cannot certify a memory-budgeted case. Terminate only the worker process group on exhaustion, allow a short bounded shutdown grace, then reap it. Never kill unrelated processes or delete source history.
7. Workers atomically write a bounded heartbeat only after verified finalized boundaries and a distinct terminal result only after successful scientific/evidence completion. The parent classifies deadline, observed RSS breach, unexpected exit, or missing terminal evidence separately; a heartbeat is not a completion. Record the last observed verified boundary without claiming it is necessarily the latest committed tick after a forced stop. A killed worker's open transaction rolls back through the existing durable transaction rules; inspect retained committed data with guarded readers.
8. Keep child coverage enabled using the same pytest/pytest-cov options as the parent, with a separate `COVERAGE_FILE` per worker under the configured output directory. Preserve coverage artifacts for explicit combination by coverage tooling; never read excluded generated coverage files into agent context. Record worker command/instrumentation identity. Reuse existing disposable-DB fixture lifecycle; baseline/candidate repetitions use separate guarded databases or schemas so identical scientific IDs cannot collide.

### Required Interfaces and Contracts

- `write_measurement(path, measurement)` validates metadata and writes atomically to an explicitly selected directory, normally `/tmp/opencode/v3-43-scale/`; committed source contains builders/schema tests, not machine-specific raw results.
- Result status is exactly `completed`, `timed_out`, `resource_exhausted`, `failed`, or `not_run`. Record the last verified committed boundary, exception reason code and elapsed time for incomplete runs. Incomplete work is never counted as supported.
- Use the existing disposable-database safety guard; database names must contain `palimpsest_test`. No production database discovery, cleanup or automatic destructive reset.
- Published measurement artifacts must omit credentials, DSNs, prompts, bodies, memory text and record marks. Detailed profiles stay local and require payload-safe filenames.
- Add `PALIMPSEST_SCALE_BENCH_WORKER` as an internal supervisor guard, not a user-facing production setting. Parent and child measurement files use separate attempt namespaces; workload `run_id`/world/branch identities stay identical across exact baseline/candidate pairs. The UUID-based `harness.unique_run_id()` remains valid for unrelated tests but is not used to construct paired scientific identities.

### Requirement Evidence

User request: 10k/100k, multiple generations, large logs, measured limits. `AGENTS.md`: coverage and excluded artifacts. Architecture: deterministic seeds and no scripted emergence.

### Error Handling and Logging

INFO logs: lane code, repetition, completed ticks, counts, elapsed duration, status. DEBUG: bounded stage timings. WARN: budget exhaustion or incomplete lane. Never emit per-event/payload logs or unbounded sample arrays. Validate artifact paths and database safety before writes.

### Tests

`tests/unit/test_v3_scale_workloads.py`: exact supported config decoding; invalid budget/horizon rejection; deterministic builders; small multiple-cohort completion; early extinction cannot pass the sustained lane; malformed measurement and secret-bearing metadata rejected; fake-worker success/timeout/RSS breach/nonzero exit/missing terminal file; heartbeat-only cannot pass; unsupported RSS accounting is labelled unenforced; child coverage and process reaping; identical paired IDs with separate storage namespaces.

### Acceptance Criteria and Verification

- `uv run pytest tests/unit/test_v3_scale_workloads.py --cov=simulation --cov=experiments --cov=research_runner --cov-report=term` passes.
- `PALIMPSEST_SCALE_BENCH_TICKS=10000 uv run pytest -m 'scale and integration' tests/benchmarks/test_v3_long_horizon.py --cov=simulation --cov=persistence --cov=experiments --cov=api --cov-report=term` selects only explicitly enabled workloads against a guarded disposable database; output distinguishes setup, execution, analytics and queries.

## Task 2: Capture bounded before-profiles and a storage/query cost ledger

### Intent

Identify costs attributable to history length, total population and concurrent living population separately. This task performs measurement, not speculative optimization.

### Implementation Steps

1. Extend `v3_measurement.py` with monotonic stage timers, process peak RSS with platform units recorded, bounded periodic RSS samples, SQL call/row/byte counters and bounded sampled allocation/cProfile collection. Use external wall clocks only in benchmark instrumentation, never domain policy.
2. Execute fresh-process repetitions of identical configurations; preserve a baseline code revision and pristine output namespace. At least three completed execution repetitions are required before describing an execution result as repeatable. Query distributions use at least 30 samples per named warm-cache case; label process-cold and database-cold conditions separately and do not claim OS-cache coldness without controlling it.
3. Measure prepare/resolve/finalize, population admission, checkpoint serialization/write, evidence capture/publication, final result construction, archive export, metric aggregation, historical seek, lineage traversal, observer event catch-up and Research UI history requests separately. Profile living-owner memory retrieval candidate scans, mutation/transaction copying, retained tombstones, reconstruction provenance and idempotency sets with increasing trace counts; compare in-memory and existing SQL candidate-limited paths without changing ranking semantics. Track transient peak at finalization/export, not only steady ticks.
4. Compare fixed living population with increasing total deceased population; compare equal history with different living caps; compare tracing/capture off/on; compare no checkpoints with the existing checkpoint presets. Keep one factor varied per paired performance comparison.
5. Save a cost ledger inside the measurement artifact: existing PK/index inventory, bounded `EXPLAIN (ANALYZE, BUFFERS)` for representative real queries, heap/index/TOAST sizes, returned versus scanned rows, snapshot fold distance, parsed shards/bytes and client cache counts. Investigate partitioning, materialized views and lossless compression using these costs. Record `retain_existing`, `implemented_in_task_N`, or `deferred_with_evidence` for each option; no invisible deferred decision.
6. Before later phases, record which hot path each fixed change addresses. If a proposed change has no measurable benefit on its target workload, retain the old implementation and record the negative finding; do not replace it with an unplanned architecture. DB partitioning, destructive tier migration and new approximate metrics are explicitly excluded from this plan even if suggested by profiling; open a separately scoped plan for those.

### Required Interfaces and Contracts

- Instrumentation is outside scientific state; it cannot change seed streams, admission ordering, stop criteria, retained evidence or exact hashes. Samples have a fixed configured capacity, not one item per event/tick.
- SQL plans run only against disposable benchmark databases after committing the same inputs as the measured run. Export-only archives do not authorize row removal.
- A missing 100k result remains `not_run`/incomplete; extrapolation is a capacity estimate with assumptions, never measured support.

### Requirement Evidence

User request: profile first; investigate snapshots, cold storage, partitions, indexes, materialized views, incremental metrics, compression and batch analytics. Earlier V2 plan: append-only triggers and existing optimizations.

### Error Handling and Logging

Measurement failure must not be confused with scientific failure. Mark unavailable counters explicitly, not zero. Fail a required baseline case on artifact corruption. INFO summaries and bounded DEBUG timing aggregates only; no SQL parameter/payload dumps.

### Tests

Helper tests cover sample-cap exhaustion, monotonic interval calculation, RSS units, absent platform counters, timeout artifacts, atomic publication and exact identity matching for paired comparisons.

### Acceptance Criteria and Verification

- Run the Task 1 command for 10k, then repeat with `PALIMPSEST_SCALE_BENCH_TICKS=100000`; preserve completion/failure artifacts for both.
- Baseline artifacts identify actual dominant costs and explicitly record all requested investigation options. Later commits cite these artifact identities, not fabricated timing numbers.

## Task 3: Establish exact equivalence and historical query oracles

### Intent

Make storage/layout optimizations provably invisible to scientific consumers.

### Implementation Steps

1. Add a reusable paired execution helper to `test_v3_scale_equivalence.py`: identical `run_id`, world/scenario IDs, parent/branch/intervention identity where applicable, configuration, seed, stochastic/comparison identity, deterministic fake/recorded provider identity and command sequence. Isolate storage/output namespaces instead of randomizing domain IDs. Compare canonical ordered events, exact trajectory hash, result counts, population/lifecycle records, reconstructed observations and selected complete subjective/evidence exports; do not normalize differing IDs out of event hashes.
2. Include a representative existing v55 generational experiment, not only synthetic empty histories. Test admission, dependent/active/elder stages, death, post-death finalized evidence and a later historical query. No newborn ledger copying is allowed.
3. Define historical seek targets at beginning, just before/at/after death and admission, checkpoint boundaries, middle and final committed tick. Compare snapshot-assisted reconstruction to the reference fold, including prior-event windows.
4. Define exact query oracles for long-dead owner data and all eight lineage families. Preserve qualified IDs, roots, uncertainty, partial/unavailable distinctions, coverage denominators, cursor authorization and evidence high-water marks.
5. Make later optimization tests import these helpers. Any opt-in scalable path must match the reference for complete outputs; partial evidence must report the same explicit availability rather than silently filling gaps.

### Required Interfaces and Contracts

No production interface is introduced here. Hashes are correctness evidence, not log payload surrogates. Full reference materialization is allowed only in small unit fixtures; scale verification streams canonical comparisons/digests to avoid creating a second unbounded benchmark implementation.

### Requirement Evidence

`.ai-factory/ARCHITECTURE.md`: versioned extension and owner-scope contracts. `docs/architecture.md`: Downstream V3 plan contract and live/restored observation parity. User: immutable scientific history and required provenance.

### Error Handling and Logging

Fail on the first differing qualified record/sequence with safe field/reason metadata. Do not dump observations, narrative contents, marks or memory text. A corrupt archive or missing required finalized evidence is a correctness failure, never a benchmark speedup.

### Tests

Cover flags-off defaults; v55 modes on; optional capture/tracing off and on; tampered event/lineage fixtures; cursor reuse across snapshots/credentials; final living and long-dead owner retrieval. A deliberate paired `run_id`/stochastic-identity mismatch must be rejected before comparison, not reported as a semantic optimization regression or hidden by hash normalization. Detailed production-path cases are added in the phase that changes that path.

### Acceptance Criteria and Verification

`uv run pytest tests/unit/test_v3_scale_equivalence.py tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py tests/unit/test_checkpoint_restoration.py --cov=simulation --cov=world --cov=experiments --cov-report=term` passes before and after optimizations.

## Phase Risks and Mitigations

- Instrumentation can dominate short ticks: report profiler/coverage state and measure paired runs under identical instrumentation; retain correctness coverage in every test invocation.
- Full feature combinations can be invalid: build only through existing validated presets/configuration seams and make unsupported combinations explicit.
- 100k may exceed this machine: bounded failure artifacts are valid findings; they do not establish support or justify deleting evidence.

## Phase Completion Checklist

- Tasks 1–3 meet their acceptance criteria; required commands pass or budget-limited scale cases are explicitly recorded as incomplete.
- Scientific parity is a hard gate, regardless of timing improvements.
- Update progress only in `index.md` after verification.
