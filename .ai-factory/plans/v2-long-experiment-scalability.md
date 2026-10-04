# Implementation Plan: Long-Experiment Scalability and Observer Backpressure

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-04
Improved: 2026-10-04 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete milestone; this plan adds infrastructure so V2 experiments can run and be observed at much longer tick horizons without claiming `multi_hop_testimony_tracking` or any new capability flag.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M6 — Remaining V2 Capability Flags
INFO [aif-plan] mode=ultra treated as full (richer plan); remaining args describe the feature
INFO [aif-plan] resolved plan file: .ai-factory/plans/v2-long-experiment-scalability.md (format=slug)
INFO [aif-plan] plan name prefix v2- applied per user request; git.create_branches=false so stem is description slug
INFO [aif-improve] applied refinement: rewrite D1/Task5/Task13 away from DELETE on append-only tables; fix index/memory/marker/ANN/prepare tasks; append-only gate + observer-protocol lock

## Compatibility contract

This plan prepares the modular monolith for substantially longer experiments (hundreds/thousands → tens/hundreds of thousands of ticks where practical) with efficient live graphical observation and historical replay. It must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. **V1 invariants intact.** `WorldEngine` remains the only objective mutation authority. Append-only immutable `WorldEvent` history stays authoritative. Live/restored observation parity and exact trajectory hashes must not change for identical seeds/config when scaling knobs are at their default/off settings.
2. **No new capability flag.** Do not add a `V2CapabilityFlags` slot. Do not own `multi_hop_testimony_tracking`. Scaling knobs are settings / runner persistence / API / observer presentation policy — not emergence features.
3. **V1 regression gate stays green** under flags-off and tracing-off. Long-run benchmarks and observer scale suites stay **off** `tests/unit/test_v1_regression_gate.py`.
4. **Schema discipline.** Prefer settings and optional runner persistence keys with exact key-set bumps only when a new write version is required. Do not drop accepted V1/V2 versions in the same change. Default write surfaces stay compatible; long-run defaults must be opt-in or documented recommendations that do not silently rewrite short V1 runs.
5. **No scripted emergence.** Benchmarks and filters do not invent friend/enemy/leader/culture roles.
6. **No LLM → world shortcuts.** Concurrency limits and parallel prepare (if introduced) still translate through cognition → `ActionSubmission` → admission. Submission order for resolve remains the registered runtime ordinal order.
7. **Experiments stay reproducible.** Do not weaken deterministic semantics merely for speed. Parallelism is allowed only where commit order, seed streams, event sequences, and hashes stay identical to the sequential baseline for the same inputs.
8. **Optional tracing stays outside the objective fold.** Cognition-trace export / soft stop-append must never enter `EvidenceManifest` / objective high-water or change `exact_trajectory_hash`. Do not `DELETE` cognition-trace rows (Alembic `0013` installs `reject_history_mutation`).
9. **Observer presentation ≠ science.** Presentation coalescing / frame skipping is allowed only in `observer` projection or `clients/godot-observer`. Never coalesce, drop, rewrite, or reorder immutable `WorldEvent` rows or durable scientific outbox payloads used for analysis.
10. **No premature distributed architecture.** Do not introduce Kafka, Kubernetes, or a microservice split unless a concrete repository bottleneck proves the modular monolith cannot meet the target with indexes, bounded queues, snapshot cadence, and query limits. Current evidence: `StreamFanout`, `ObserverStreamSession`, keyset event pages, and checkpoint cadence already exist in-process — extend them first.
11. **No observer protocol bump.** Stay on `observer-protocol-v1` / `observer-layout-v1`. Additive optional GET query params (filters, larger page sizes within settings caps) are allowed. Do not rename the protocol, add a presentation-only WS mode that mutates science payloads, or require a layout id change for scale features.
12. **Do not weaken append-only triggers.** `reject_history_mutation` on `AUTHORITATIVE_TABLES` (including `world_snapshots` and projection tables), `run_stream_records`, and `cognition_trace_invocations` must remain. Scale work bounds growth by write cadence, query limits, export copies, and soft stop-append — never by disabling DELETE rejection.

## Goal

Make long experiments practical to run, store, analyze, and watch:

```text
WorldEngine commit (unchanged semantics)
  → durable tick + events (+ optional cadence snapshot)
  → stream/outbox + cognition-trace (append-only; export/soft-cap only)
  → Observer API / WS (bounded queues, batch catch-up, snapshot seek)
  → Godot presentation (may coalesce frames; never mutates history)
```

Target architecture progression: hundreds/thousands of ticks today → tens or hundreds of thousands where practical, with:

- efficient live graphical observation that cannot block simulation
- historical replay / arbitrary-tick reconstruction via snapshot + fold
- bounded memory/query/LLM pressure
- benchmark scenarios proving live, paused-behind, seek, reconnect, and multi-observer cases

## Baseline (repository evidence)

| Area | Today | Scale gap |
| --- | --- | --- |
| Event persistence | Append-only `world_events` + triggers; PK `(run_id,tick,sequence)`; indexes on `(run_id,tick,revision)`, actor, target, type | Volume/IO at 10⁴–10⁵ ticks; seek fold cost if checkpoints sparse |
| Snapshots | `RunnerCheckpointPolicy(enabled, cadence_ticks)` default **off**; snapshots are authoritative (DELETE rejected) | Long seeks fold large event ranges when cadence off; storage bounded only by **write** cadence, not post-hoc GC |
| Stream / API WS | `StreamFanout` + `asyncio.Queue(maxsize=api_stream_queue_size)` default 64; `SlowConsumerError` disconnects; integration `test_api_stream_backpressure.py` | Proven for control stream; keep as pattern. `run_stream_records` also DELETE-rejected |
| Observer WS | `ObserverStreamSession` polls journal with bounded queue + slow-consumer disconnect; reconnect docs use `GET .../events` gap fill | Need hardened multi-observer + lag benchmarks; producer batch size hard-coded 50 |
| Godot client | Live buffer 256; discard → `behind_live`; client-side filters; speed skip at ≥8× | Presentation coalescing incomplete vs stated high-speed policy; no scale harness |
| Memory / pgvector | SQL loads filtered candidates then ranks in Python; `MemoryRetrieveRequest.limit` already ≤256; embedding column exists; no ANN index | Unbounded **candidate** load before rank grows with owner memory size |
| Cognition prepare | Sequential `for runtime in self._runtimes` await prepare/bind | LLM-on multi-agent ticks serialize wall time |
| Cognitive budgets | `CognitiveBudgetMode` / `TickBudgetLedger` on `runner-config-v22` | Per-agent tick caps exist; no process-wide LLM concurrency knob |
| Matrix batches | `MatrixBatchRunner` semaphore; durable forces `max_concurrency=1` | Long cells need persistence/observer scale more than more process concurrency |
| Cognition traces | Append-only `0013` with DELETE rejection; keyset page reads | Unbounded growth when tracing on; no in-DB prune without trigger change |
| Analytics / inspection | Keyset pagination in `inspection_sqlalchemy` | Large timeline/metrics scans need explicit limits + useful filter indexes |

## Locked design decisions

### D1 — Immutable / append-only history is never deleted in place
- `world_events`, `tick_commits`, `world_snapshots`, snapshot projection tables, and other `AUTHORITATIVE_TABLES` remain append-only with existing `reject_history_mutation` triggers (UPDATE/DELETE/TRUNCATE rejected).
- `run_stream_records` and `cognition_trace_invocations` are also DELETE-rejected (Alembic `0012` / `0013`). Treat them as append-only for this plan.
- Allowed storage bounds (compatible with triggers):
  - **Write-time snapshot sparseness:** enable `RunnerCheckpointPolicy` with a positive `cadence_ticks` so long runs write fewer snapshots. Do **not** `DELETE` snapshot or projection rows after write.
  - **Export copies:** optional read-only offline archives of events / traces / stream ranges. Copies never authorize deleting the live append-only rows.
  - **Soft stop-append (non-authoritative only):** optional default-off caps that stop accepting new cognition-trace appends (fail-soft / documented reason code) once a limit is hit — without deleting prior rows and without changing objective hashes when tracing is off.
- Out of scope: relaxing DELETE triggers to enable true snapshot GC (separate architecture decision).

### D2 — Snapshot cadence is the primary seek accelerator
- Keep `RunnerCheckpointPolicy.cadence_ticks` as the user-facing interval.
- Add documented long-run presets (e.g. enable checkpoints every 100 / 500 / 1000 committed ticks) via helpers or documented runner persistence examples — without changing short-run defaults.
- Seek/replay continues: nearest verified snapshot at-or-before target → fold events → drop engine. Optimize selection/logging; do not invent inverse events.

### D3 — Observer backpressure never blocks ticks
- Server: bounded per-subscriber queues; on overflow disconnect that subscriber with `slow_consumer` (already present). Simulation commit path must not `await` subscriber drains.
- Client: keep discard-behind-live buffer; after discard, catch up via batch `GET .../events` using `(after_tick, after_sequence)`, then resume WS.
- Multi-observer: each subscriber has its own queue; one slow client must not affect others or the runner.

### D4 — Presentation coalescing only
- Optional coalescing (tick envelopes, motion skip, high-speed frame merge) lives in Godot / `observer` projection helpers.
- Scientific event pages, analysis loaders, durable history, and the observer WebSocket journal path remain complete and uncoalesced.

### D5 — Memory retrieval is hard-capped at the candidate layer
- Keep existing `MemoryRetrieveRequest.limit` max (`_MAX_QUERY_LIMIT` = 256); do not invent a parallel request max unless settings need a lower operational default.
- Push SQL prefilters and a **candidate** `LIMIT` before `rank_traces`; add pgvector ANN index when embeddings are present.
- **Hybrid ranking (locked):** ANN/SQL distance produces a candidate shortlist only; final hits still go through existing deterministic `rank_traces` scoring. Embeddings-off / deterministic fake paths unchanged.
- Document that ANN shortlist is for semantic retrieval latency, not objective replay.

### D6 — LLM concurrency without semantic drift
- Add a process-scoped concurrency limit (settings / runner provider knob) around `LLMProvider.generate` (default 1).
- Optional parallel agent prepare stays **default off**. Before enabling: audit `AgentRuntime` / shared LLM provider for shared mutable state under `asyncio.gather`. When on: gather prepares, then **assemble submissions in fixed runtime ordinal order** before `resolve_tick`.
- Property/unit test required: same seed/config → same event sequence and `exact_trajectory_hash` as sequential prepare.

### D7 — No Kafka / K8s / microservices in this plan
- Extend PostgreSQL outbox, in-process fan-out, Alembic indexes, and research_runner/matrix process-local concurrency.

## Non-Goals

- Claiming `multi_hop_testimony_tracking` or any new `V2CapabilityFlags` value
- Rewriting parent branch history or weakening append-only / `reject_history_mutation` triggers
- In-database `DELETE` of `world_snapshots`, `run_stream_records`, or `cognition_trace_invocations`
- Server-side playback speed as a simulation control
- Pausing the simulation from the graphical observer
- Distributed stream brokers, service meshes, or splitting `api` / `persistence` into separate deployables
- Guaranteeing interactive Godot FPS at 100k ticks without presentation skip — science completeness beats pretty animation
- Bumping `observer-protocol-v1`

## Commit Plan

- **Commit 1** (after tasks 1–3): `feat(scale): add long-run profiling harness and baseline metrics`
- **Commit 2** (after tasks 4–6): `feat(persistence): snapshot cadence presets and long-run indexes`
- **Commit 3** (after tasks 7–9): `feat(memory): candidate caps and hybrid pgvector path`
- **Commit 4** (after tasks 10–12): `feat(observer): backpressure, batch seek, filters, presentation coalesce`
- **Commit 5** (after tasks 13–15): `feat(runtime): LLM concurrency limits and cognition-trace soft caps`
- **Commit 6** (after tasks 16–18): `test(scale): benchmark scenarios + docs for long experiments`

Each checkpoint is a git commit on `main` when those tasks are done. Do not squash into one final commit. `git.create_branches` is false.

## Tasks

### Phase 0: Profile and contracts

- [x] Task 1: Add a long-run profiling / benchmark harness (deterministic fake cognition).
  - Deliverable: A pytest suite under `tests/benchmarks/` (or `tests/integration/`) using `@pytest.mark.integration` and, if desired, a newly registered `@pytest.mark.scale` marker in `pyproject.toml` (`markers =` + keep `--strict-markers` green). Do **not** use unregistered `benchmark` markers. Harness runs durable simulations to configurable tick targets (1k / 10k, optional 50k+ behind env flag) with deterministic fakes, measuring wall time, events/sec, snapshot write cost, peak RSS (or documented proxy), observer catch-up latency, and seek latency. Emit structured logs only (IDs, counts, durations) — never seeds, payloads, or embeddings. Document how to enable against `PALIMPSEST_TEST_DATABASE_URL`.
  - Logging: `[scale.bench] scenario=%s ticks=%s elapsed_ms=%s events=%s snapshots=%s` at INFO; per-phase DEBUG with `phase=` and `duration_ms=`.
  - Files: `tests/benchmarks/` (or agreed path), `pyproject.toml` (marker registration), helpers under `tests/`, optional `docs/development.md` pointer.

- [x] Task 2: Instrument hot paths and capture baseline profiles (artifact, not plan file).
  - Deliverable: Add metadata-only timers around snapshot write, `scene_at_tick`, and memory retrieve `candidate_count` if missing. Run the harness against current main behaviors; write results to `docs/` draft notes or `tests/benchmarks/` artifacts (e.g. checked-in template + local/CI output). Identify top 3 bottlenecks with file references. Do **not** edit this plan’s Verification notes as the system of record during implementation — leave pointers only.
  - Logging: `[scale.profile] component=%s operation=%s duration_ms=%s count=%s` at DEBUG.
  - Depends on task 1.
  - Files: instrumentation in `src/simulation/replay.py`, `src/persistence/sqlalchemy.py` / memory adapter, `src/api/observer_service.py` as needed; `tests/benchmarks/` or `docs/` artifact paths.

- [x] Task 3: Lock scale settings surface (no capability flag).
  - Deliverable: Define `PALIMPSEST_*` / optional runner persistence knobs for: stream/observer queue sizes, observer catch-up page size, long-run checkpoint cadence **preset helpers** (not silent default flips), memory retrieve **max candidates** (SQL prefilter), process LLM concurrency, optional cognition-trace soft stop-append caps. Invalid values fail closed. Defaults preserve today’s short-run behavior. Do **not** add settings that imply in-DB `DELETE` of snapshots, stream records, or cognition traces.
  - Logging: `[infrastructure.settings] scale_knob name=%s value=%s` at DEBUG on load (never secrets).
  - Files: `src/infrastructure/settings.py`, `src/simulation/runner_models.py` / serialization only if a new write schema is truly required (prefer settings + helpers), unit tests for validation.

<!-- Commit checkpoint: tasks 1–3 -->

### Phase 1: Event persistence, snapshots, indexes

- [x] Task 4: Configurable snapshot intervals + long-run checkpoint presets.
  - Deliverable: Keep `RunnerCheckpointPolicy`; add a documented durable long-run preset helper that enables checkpoints at a positive `cadence_ticks`. Ensure runner logs cadence hits at INFO already present remain; add DEBUG when a seek uses `snapshot_next_tick` distance. Tests: enabling cadence writes snapshots at expected ticks; disabled remains default.
  - Logging: existing `checkpoint_cadence_hit`; add `[simulation.replay] seek_snapshot_selected run_id=%s target_tick=%s snapshot_next_tick=%s fold_event_count=%s` at DEBUG.
  - Depends on task 3.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner.py`, `src/simulation/replay.py`, tests under `tests/unit/` / integration.

- [x] Task 5: Write-time snapshot sparseness (no snapshot DELETE).
  - Deliverable: Bound snapshot storage solely by write policy (`RunnerCheckpointPolicy` + long-run presets from task 4). Document that `world_snapshots` / projection tables are authoritative and DELETE-rejected — implementers must not add snapshot GC. Optional offline **export** of snapshot payloads for cold storage is allowed as a copy. Tests: long-run preset produces expected snapshot counts; seek to sampled ticks with cadence snapshots matches fold correctness; attempting DELETE via the normal DB role still fails (covered with task 17 / `test_append_only`).
  - Logging: `[persistence.snapshots] write_policy run_id=%s cadence_ticks=%s snapshot_count=%s` at DEBUG/INFO as appropriate — **no** `retention_applied removed=` delete logs.
  - Depends on task 4.
  - Files: docs + preset helpers near runner persistence; tests. Avoid Alembic changes that relax triggers.

- [x] Task 6: Database indexes for real long-run query gaps.
  - Deliverable: Static audit of ORM/SQL. **Do not** add a redundant index for `(run_id, tick, sequence)` — that is already the `world_events` primary key used by `list_events_keyset`. Confirm `ix_world_snapshots_run_next_tick` serves seek. Add only missing useful indexes (candidates: `(run_id, event_type)` and/or actor/target composites for observer filters; memory embedding ANN in task 8; confirm stream/trace indexes from `0012`/`0013`). Migration head beyond `0015` only for additive indexes; no authoritative column semantics change.
  - Logging: migration log module name; optional slow-path DEBUG via task 2 timers.
  - Depends on task 3 (settings/filter needs). Baseline profiling from task 2 is informational only.
  - Files: `alembic/versions/0016_*.py` (or next head) only if a real gap exists, `src/persistence/orm.py`, tests if the project pattern allows.

<!-- Commit checkpoint: tasks 4–6 -->

### Phase 2: Memory retrieval and pgvector

- [x] Task 7: Enforce SQL candidate prefilter caps (request limit already exists).
  - Deliverable: Keep `MemoryRetrieveRequest.limit` ≤ `_MAX_QUERY_LIMIT` (256). Add settings-driven **max candidate** prefilter in `memory_sqlalchemy` so `_load_filtered_traces` cannot load an unbounded owner corpus before `rank_traces`. Cognition stages continue to pass explicit recall limits. Tests: large corpora only materialize ≤ candidate cap; oversized candidate setting fails closed; existing limit>256 still rejects.
  - Logging: `[memory.retrieve] candidate_count=%s result_count=%s limit=%s candidate_cap=%s` at DEBUG; WARN on reject.
  - Depends on task 3.
  - Files: `src/persistence/memory_sqlalchemy.py`, `src/infrastructure/settings.py`, `src/agents/cognition/memory.py` only if call sites need wiring, unit tests.

- [x] Task 8: Hybrid pgvector shortlist + `rank_traces`.
  - Deliverable: When `query_embedding` is set, use SQL prefilter + optional vector distance / ANN to build a candidate shortlist, then run existing deterministic `rank_traces` for final hits. Add ANN index (HNSW preferred if extension supports) in Alembic for non-null embeddings. Embeddings-off and deterministic fake paths keep today’s behavior (`path=python_rank` or `sql_limit` without ANN). Document hybrid ranking and that ANN is not used for objective replay.
  - Logging: `[memory.retrieve] path=%s semantic=%s candidate_count=%s` at DEBUG (`path=python_rank|sql_limit|sql_ann_shortlist`).
  - Depends on tasks 6, 7.
  - Files: `src/persistence/memory_sqlalchemy.py`, Alembic revision, `docs/memory-reconstruction.md` (finalized in docs task).

- [x] Task 9: Analytics pagination and scan guards for long runs.
  - Deliverable: Ensure analysis/inspection loaders used after long runs cannot default to unbounded full-journal loads (watch `limit=10_000_000` call sites in branch compare — leave research compare as explicit opt-in with WARN). Observer ticks/events pages honor `api_max_page_size`. Add/extend tests for large timeline pagination stability (keyset monotonicity).
  - Logging: `[analysis.load] reason_code=unbounded_limit_rejected` or WARN when explicit huge limits are used in research tools.
  - Depends on task 6.
  - Files: `src/persistence/inspection_sqlalchemy.py`, `src/persistence/analysis_sqlalchemy.py`, `src/api/observer_service.py`, targeted tests.

<!-- Commit checkpoint: tasks 7–9 -->

### Phase 3: Observer API, seeking, WebSocket, presentation

- [x] Task 10: Harden bounded live observer buffers and multi-observer isolation.
  - Deliverable: Wire observer stream queue size and catch-up batch size to scale settings (today queue uses `api_stream_queue_size`; producer batch is hard-coded 50 — make configurable). Prove N concurrent read-only observer sockets: one paused/slow disconnects with `slow_consumer` while others and the runner continue. Extend unit tests around `ObserverStreamSession` and add integration coverage mirroring `test_api_stream_backpressure.py`.
  - Logging: existing `observer_stream_slow_consumer`; add `[api.observer_stream] catchup_batch run_id=%s count=%s queue_size=%s` at DEBUG.
  - Depends on task 3.
  - Files: `src/api/routes/observer_stream.py`, `src/infrastructure/settings.py`, `tests/unit/` + `tests/integration/`.

- [x] Task 11: Reconnect-by-sequence, batch event retrieval, snapshot-assisted seek.
  - Deliverable: Ensure reconnect uses exclusive `(after_tick, after_sequence)` pages until caught up; support larger batch retrieval within `api_max_page_size`. Optimize `scene_at_tick` / `scene_through_event` for 10k+ tick jumps via cadence snapshots (tasks 4–5). Add server tests for jump 10k+ ticks and reconnect after many missed events (synthetic journal). Godot session path already gap-fills — add GDScript tests for buffer discard → batch GET → resume.
  - Logging: `[api.observer] reconnect_catchup run_id=%s pages=%s events=%s` at INFO; seek snapshot DEBUG from task 4.
  - Depends on tasks 4, 5, 10.
  - Files: `src/api/observer_service.py`, `src/api/routes/observer.py`, `src/simulation/replay.py`, `clients/godot-observer/scripts/net/session.gd`, tests.

- [x] Task 12: Large timeline pagination, event filters, presentation-only coalescing.
  - Deliverable: (a) Server-side optional filters on `GET .../observer/events` for agent id / semantic type / location id using indexed columns where possible; keep client filters as an additional UX layer on the loaded page. Stay on `observer-protocol-v1` — additive query params only. (b) Efficient `ticks` pagination for large runs. (c) Optional presentation coalescing in Godot / observer projection only; scientific WS journal stays complete. Never alter stored events.
  - Logging: `[api.observer] events_filtered run_id=%s limit=%s filter_codes=%s result_count=%s` at DEBUG; `[observer.playback] presentation_coalesced skipped=%s` at DEBUG in Godot.
  - Depends on tasks 6, 10.
  - Files: `src/api/routes/observer.py`, `src/api/observer_service.py`, `src/persistence` event readers, `clients/godot-observer/scripts/protocol/playback.gd`, `docs/observer.md`.

<!-- Commit checkpoint: tasks 10–12 -->

### Phase 4: Cognition traces, batch runs, LLM concurrency

- [ ] Task 13: Cognition-trace soft caps and export (no DELETE).
  - Deliverable: Optional default-off soft stop-append when a configured invocation/byte cap is hit (fail-soft with stable reason code; prior rows remain). Optional read-only export copy for offline archival. Do **not** `DELETE`/`TRUNCATE` `cognition_trace_invocations` (triggers must keep rejecting). Paginated reads remain; stress test with tracing on for moderate tick counts. Tracing-off trajectories / `exact_trajectory_hash` unchanged.
  - Logging: `[cognition_trace] soft_cap_reached run_id=%s reason_code=%s count=%s` at WARN; export DEBUG counts — **no** `archive_applied removed=` delete logs.
  - Depends on task 3.
  - Files: `src/persistence/cognition_trace_sqlalchemy.py`, settings, tests proving tracing-off hash stability + DELETE still rejected.

- [ ] Task 14: Batch / matrix long-cell guidance and resource bounds.
  - Deliverable: Document and optionally enforce that durable matrix cells use `max_concurrency=1` (already) plus recommended checkpoint cadence for long cells. Add matrix/research_runner validation WARN when durable long `max_ticks` runs with checkpoints disabled. No HTTP matrix API.
  - Logging: `[matrix] long_run_checkpoint_recommended cadence_ticks=%s` at WARN.
  - Depends on task 4.
  - Files: `src/experiments/matrix_runner.py` / models, `docs/experiments.md`, tests for WARN path.

- [ ] Task 15: Process-wide LLM concurrency limits (determinism-preserving).
  - Deliverable: Settings/runner knob `llm_max_concurrency` (default 1). Gate `LLMProvider.generate` (composition/factory wrapper) with a semaphore. Parallel agent prepare remains **default off**. Before enabling: audit shared mutable state across `AgentRuntime.prepare_observation` and the shared provider. When enabled: `asyncio.gather` prepares, then bind/submit in runtime ordinal order. Property test: parallel prepare + concurrency>1 with deterministic fake LLM matches sequential `exact_trajectory_hash`. `CognitiveBudgetMode` remains the per-agent tick budget.
  - Logging: `[llm.concurrency] acquired in_flight=%s max=%s` at DEBUG; `[simulation.runner] prepare_parallel enabled=%s agent_count=%s` at INFO once per run.
  - Depends on task 3.
  - Files: `src/llm/factory.py` or recording wrapper, `src/simulation/runner.py`, `src/simulation/agent_runtime.py` (audit), `src/infrastructure/settings.py`, unit/property tests.

<!-- Commit checkpoint: tasks 13–15 -->

### Phase 5: Benchmark scenarios, verification, docs

- [ ] Task 16: Implement required observer/scale benchmark scenarios.
  - Deliverable: Automated scenarios (Python integration and/or Godot protocol tests) covering:
    1. live observation while simulation runs
    2. viewer paused far behind live (buffer discard + catch-up)
    3. jumping 10k+ ticks (snapshot-assisted)
    4. reconnect after many missed events (sequence resume)
    5. multiple read-only observers (one slow, others healthy)
    Assert: runner tick progress continues under slow consumer; reconnect completeness; seek frame equals fold from earlier snapshot; no `WorldEvent` mutation.
  - Logging: `[scale.bench] scenario_complete name=%s passed=%s` at INFO.
  - Depends on tasks 1, 10–12.
  - Files: `tests/benchmarks/` / integration / `clients/godot-observer/tests/`.

- [ ] Task 17: Regression, architecture, and append-only gates for scale changes.
  - Deliverable: V1 regression gate green flags-off/tracing-off; import-linter/AST boundaries unchanged (`observer` still read-only; no engine commit from API stream). Add architecture test that presentation coalesce helpers do not import persistence event writers. Exact trajectory hash tests for concurrency defaults. **Re-run / extend** `tests/integration/test_append_only.py` (or equivalent) so `DELETE` on `world_snapshots`, `run_stream_records`, and `cognition_trace_invocations` still fails after scale work — fail the plan if any path disabled those triggers.
  - Logging: standard pytest; no new payload logs.
  - Depends on tasks 5, 13, 15, 16.
  - Files: `tests/unit/test_v1_regression_gate.py` (run only), `tests/integration/test_append_only.py`, new architecture/unit tests.

- [ ] Task 18: Documentation checkpoint (`/aif-docs`).
  - Deliverable: Update `docs/persistence.md`, `docs/observer.md`, `docs/research-api.md`, `docs/memory-reconstruction.md`, `docs/development.md` (and README links if needed) with: long-run checkpoint guidance, write-time sparseness (no snapshot DELETE), observer backpressure/reconnect, `observer-protocol-v1` stability, presentation vs scientific history, memory candidate caps + hybrid pgvector, LLM concurrency, cognition-trace soft caps/export, benchmark how-to. No Kafka/K8s recommendations. No advice to prune append-only tables in place.
  - Logging: n/a for docs prose; code samples follow existing metadata-only log rules.
  - Depends on tasks 16–17.
  - Files: `docs/*.md`, possibly `README.md` landing links only.

<!-- Commit checkpoint: tasks 16–18 -->

## Verification notes (fill during implementation)

- Baseline profile artifact path: `tests/benchmarks/BASELINE_TEMPLATE.md` (task 2)
- Top bottlenecks: see artifact (seek fold / durable tick append / memory candidate load)
- Target tick horizons proven in CI vs optional nightly: _TBD_ (suggest CI ≤10k durable fake; longer behind env)
- Append-only DELETE rejection reconfirmed: _TBD after task 17_

## Implementation order reminder

Profile → write-time snapshot cadence + real indexes → memory candidate/hybrid ANN → observer backpressure/seek/filters → trace soft caps / matrix WARN / LLM concurrency → benchmarks + append-only gate + docs. Prefer measuring before micro-optimizing. Never trade deterministic event order or append-only triggers for wall-clock speed.

## Out of scope (surfaced by `/aif-improve`, not scheduled)

Privileged snapshot GC by relaxing `reject_history_mutation` on `world_snapshots` — useful for disk pressure at extreme horizons, but a separate trust-boundary / architecture decision. Capture elsewhere if needed; do not implement in this plan.
