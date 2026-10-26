<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V3-43 Long-Horizon Scalability

Mode: ultra
Branch: main (stay on current branch; `git.create_branches: false`)
Created: 2026-10-26
Improved: 2026-10-26 (`$aif-improve`; seven approved refinements, task IDs preserved)
Plan identifier: `v3-43-long-horizon-scalability`
Status: Tasks 4–12 complete (Phases 2–4 done); Task 13 next

## Original Request

v3-43 long horizon scalability

Plan naming requirement:

Plan artifacts MUST start with `v3-`.

Suggested stem:

v3-43-long-horizon-scalability

Profile and optimize V3 for multi-generation simulations.

Potential scale problems include:

WorldEvent count  
population history  
dead-agent data  
memory traces  
records  
culture provenance  
genealogy  
technology lineage  
institution lineage  
cognitive traces  
Godot replay  
Research UI historical queries

Preserve immutable scientific history.

Do not solve scale by deleting required provenance.

Investigate:

snapshot strategy  
cold historical storage  
partitioning  
indexes  
materialized analytical views  
incremental metrics  
lineage compression  
bounded hot-state loading  
pagination  
streaming  
batch analytics

Dead agents should not remain unnecessarily loaded into active cognition.

Long-dead agents must remain queryable historically.

Benchmark:

10k ticks  
100k ticks  
multiple generations  
large event logs  
historical seek  
lineage queries  
observer playback

Choose actual supported limits based on measured repository performance rather than arbitrary promises.

## Settings

- Testing: yes; coverage remains enabled; scale/DB/browser gates opt-in and explicitly recorded.
- Logging: verbose, bounded metadata-only DEBUG aggregates and INFO summaries; never per-event payload floods.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 21.
- Language: English artifacts/UI; retain technical terms.
- Git: no branch/worktree creation or automatic implementation; base `main`, configured skip-push preference retained.
- Naming: bundle stem and every phase filename start with `v3-`; `index.md` is the required canonical ultra entrypoint inside that bundle.
- Research: no research file/bundle available; this plan uses the raw request, project contracts and repository reconnaissance, not external or inferred research conclusions.
- Baseline measurements: not executed during planning. Source inspection establishes code paths, not a supported capacity. Tasks 1–3 establish the baseline and equivalence gates.

## Roadmap Linkage

Milestone: "M7 — V3 Generational Civilization"
Rationale: Make existing V3 generational experiments and read-only historical research practical at measured longer horizons without owning a new capability or scripting civilization.

M7 remains open for `institutional_economy` and deferred kinship cultural/knowledge handoff; M6 remains open for `multi_hop_testimony_tracking`. This plan neither claims those flags nor independently closes a roadmap milestone.

## Requirements Reconciliation

Authority: repository/project instructions constrain all work; the user defines this task's scope. Existing scientific/persistence/API contracts define compatibility and authority. No conflicting behavioral requirement was found. Dated roadmap/description paragraphs retain historical counts; use `.ai-factory/ARCHITECTURE.md` Current baseline and executable `simulation.compatibility` for current pins, not old V2/V3 historical tables.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| Never delete/rewrite required events, commits, snapshots, trace rows or provenance | Original Request; `.ai-factory/RULES.md` Axioms; `docs/persistence.md` append-only/export contract | Tasks 3, 10, 19, 21: canonical parity, source row/hash equality and trigger rejection |
| Sole objective mutation authority; subjective state and analytical views remain distinct | `.ai-factory/ARCHITECTURE.md` Dependency Rules / Key Principles; `docs/architecture.md` Downstream V3 plan contract | Engine-owned restore, import-linter/AST gates, no analysis/API writer imports |
| Dead runtime scheduling can stop only after terminal/finalization semantics are preserved; retired state remains complete and deeply detached | `src/simulation/runner.py` tick loop / fork checks / factory clones; `src/agents/cognition/loop.py` fork export; `src/agents/cognition/budget.py` mutable ledger; owner fork DTO | Tasks 4–5: invocation ordering, live-graph release, mutable-leaf/clock isolation, factory-policy propagation and full audit/fork/query parity |
| Long-dead objective and captured evidence remain queryable; do not fabricate uncaptured subjective history | `docs/generational-runner.md` historical inspection; `docs/cultural-evolution-metrics.md` coverage; Original Request | Death-boundary queries in Tasks 5, 10–12, 18; restart queries and honest availability |
| Snapshots accelerate seeks; cadence reduces growth rate, not immutable storage to a constant | `RunnerCheckpointPolicy`; `docs/persistence.md`; earlier V2 scale plan locked D1/D2 | Task 9 actual serialization/write/seek measurements; no defaults/GC changes |
| Manifest-pinned objective pages resolve a whole commit hash or the verified bootstrap hash, not an invented event-count/mid-tick mark | `src/simulation/evidence.py` EvidenceManifest; `src/persistence/analysis_sqlalchemy.py` 185–204; `src/simulation/inspection.py` 1099 | Task 7: shared scoped boundary resolver, all anchored-commit events included, later commits excluded, bootstrap empty, bounded SQL rows |
| Replay chain linkage does not itself authenticate event payloads | `src/simulation/journal.py` 244–310; `src/simulation/replay.py` event-count checks and event-prefix read | Task 8: streamed canonical payload/commit hashes, tampering with unchanged counts/links, split-tick and event-prefix parity |
| Pagination must be physically bounded and logically complete, including empty continuations and bounded root metadata | Lineage/civilization metadata/read budgets and signed cursors; existing `ExplicitPager` | Tasks 7–12, 17–18: fetched-read limits, hierarchical authenticated directories, deep cursors, lossless suffix delivery |
| New physical archive/index/view metadata uses new identifiers; old published logical formats remain readable | `.ai-factory/ARCHITECTURE.md` Versioned Extension Contract | Old/new format dispatch, immutable publication and digest/cursor tests |
| Incremental analytics preserve exact estimands/coverage and never feed live cognition; final trait rows depend on the complete window's trait union | `src/analysis/generational_cohort.py`; `src/analysis/cultural_trait_dynamics.py` 219–262, 677–704; architecture analysis boundary | Task 14 sealed-window two-pass canonical batch parity, late-trait earlier-zero rows; remaining families labelled budgeted batch/global |
| No promise of dense 100k support from sparse durability or synthetic playback tests | Existing `tests/integration/test_generational_scale.py`; `tests/benchmarks/harness.py`; Original Request | Tasks 1–2, 19–20: separate lanes, actual counts, repeated complete measurements |
| Preserve current scientific version surface and optional/default behavior | `.ai-factory/ARCHITECTURE.md` Current baseline / capability ownership | Task 21: runner v4 default/v55 latest, result v2 default, 43 commands, 73 semantics, 136 metrics, selected replay-v22/codec-v20, Alembic 0017, `/v1`, observer-protocol-v1 |

### Supported combinations and failure states

| Input/state and validation | Retained/persisted state | Output/transition and invariants | Verification |
| --- | --- | --- | --- |
| Retention policy off | Existing complete runtime/owner storage | Legacy behavior, identical science and serialization | Tasks 3–5 flags-off/reference twin |
| Retention on, objectively dead, terminal and fully finalized, fork-capable bundle with detached supported leaves | One complete deeply frozen process-local owner/runtime record; all original objective/captured history | Active ordinal removed, all bundle service/retriever references released; full exports/fork roster and mode metadata preserved | Task 5 death/finalization/graph-release/fork mutation/clock tests |
| Retention on, pending finalization/custom unsupported bundle/error-terminal but not confirmed dead | Original live bundle remains | No unsafe eviction; explicit unsupported count; existing stop/error semantics | Tasks 4–5 failure/fallback cases |
| SQL journal, current or legacy accepted schema | Unchanged append-only tables and snapshots | Bounded commit-bound pages, streamed payload/commit/chain verification and restored observations | Tasks 7–9 old/current schema, bootstrap-anchor and split-tick tests |
| Explicit complete offline archive | Original SQL rows plus verified immutable copy and segment indexes | Read-only offline historical queries/replay; no automatic SQL failover or subjective resume | Task 10 cold replay/restart/tamper tests |
| Old/new physical lineage/civilization publication | Both remain immutable; reader dispatches explicit layout version | Same logical graph/rows, qualified IDs, coverage and cursor scope | Tasks 11–12 deep-page/old-format parity |
| Optional capture off/on/failed/quota-exhausted | None when off; retained committed spool/publications when on | Disabled is not empty; source-backed production publication avoids hidden raw-frame tuples; failed/truncated/oversize is explicit; science unchanged | Task 13 production-composition, failure and noninterference suite |
| Two selected exact incremental families versus other families | Rebuildable primitive/checkpoint views plus all original evidence | Sealed-window two-pass trait output includes future-trait earlier-zero rows; other families retain exact budgeted batch paths and separate scale limits | Tasks 14–15 batch parity/loader tests, changed union/window invalidation |
| Objective inspection versus subjective debug; valid versus stale/expired cursor | No new client persistent private cache | Existing capability separation; exact pinned history or explicit error/limited availability, never first-snapshot substitution | Tasks 16–18 client/API tests |
| Supervised benchmark completed versus timed out/resource-exhausted/not run | Metadata-only results including last observed verified boundary; isolated storage with identical paired scientific IDs | Only valid terminal evidence qualifies as complete; unenforced RSS is explicit; no horizon extrapolation | Tasks 1, 3, 19–20 process-budget/identity/envelope validation |

## Architecture and Decisions

1. **Measure first.** Extend existing scale helpers and keep sparse 100k durability, sustained-generation cognition, evidence-rich execution, synthetic large logs, backend query timings and actual browser playback separate. Fresh worker supervision enforces configured time/RSS budgets where supported and records truthful incomplete results. Exact pairs keep identical domain run/world/branch/stochastic identities in separate storage namespaces. No measurements are invented in this plan.
2. **Active versus historical state.** A stable active ordinal index avoids preparing every historical runtime. Opt-in retirement freezes complete fork state only after explicitly detaching mutable budget/dictionary leaves and releases every retained live cognition/service/retriever reference; original runtime identity, full owner exports and fork roster remain. Factory clones preserve the policy. Frozen DTOs/objective history still grow: bounded active cognition is not constant total RSS.
3. **No premature history eviction.** The engine retains complete objective history/records/genealogy. Optimize known scans/indexes and loading first. Objective bodies, forgotten traces, operation IDs and required audits are not garbage-collected to achieve benchmark numbers. Profile living-owner memory retrieval/transaction costs explicitly; this plan does not change recall ranking, forgetting semantics or already-bounded knowledge/institution ledger policies. Long-lived in-memory trace/provenance/idempotency growth remains an explicit measured envelope constraint, not a hidden constant-memory claim.
4. **Verified batched replay.** Add bounded journal/head ports, engine-owned incremental restoration and whole-commit/bootstrap manifest bounds using the existing analysis-loader resolution contract. Incrementally recompute canonical payload and commit hashes, not just chain links/counts, including event-prefix seeks. Preserve eventless ticks, prior-event windows and all version-selected channel folds. Full public event-history exports can still cost O(history).
5. **Snapshot strategy stays deterministic.** Compare existing checkpoint-off/100/500/1000 cadences, measure actual write cost and folds, and recommend only tested combinations. No machine-time adaptive scientific policy or snapshot deletion.
6. **Cold tier is a copy.** Explicit offline segmented exports behind read ports can serve old history without a live runner. Source SQL/history and all append-only guards remain. No automatic API tier router, destructive migration, partition detach or durable subjective restart.
7. **Lossless lineage compression.** Fix continuation completeness, physically page catalogue/adjacency/row shards and reuse byte-identical content-addressed objects. New physical roots reference bounded hierarchical authenticated directories rather than an unbounded flat list of page digests. No edge/root/owner/institution identity merging or lossy narrative summaries. Maintain metadata/request/logical quotas; old formats remain readable.
8. **Capture and batch work.** Optional append-only disk spooling bounds hot capture buffers without changing logical quotas/coverage. Source-based normalizers, civilization composition and matrix artifact writers must avoid hidden all-frame tuple conversion. Explicit global batch-analysis materialization remains a separately measured/budgeted stage, not a bounded-publication claim. Only population comparison and sealed-window two-pass trait dynamics gain exact incremental machinery initially; all 136 families are not claimed streamable.
9. **Derived analytical views.** Rebuildable sidecars bind exact source/high-water/algorithm/window/pass identities. Future-dependent trait rows finalize only after the complete union is known; sparse prefix state is distinct from final documents. Views neither replace source evidence nor become cognition, world policy or stop-selector inputs.
10. **Indexes/partitioning are evidence questions.** Use existing PK, unique event ID and snapshot/filter indexes first. Collect plans, scanned/returned rows and write/storage cost. This fixed plan makes no SQL schema/migration changes; a demonstrated residual index/partition need gets a separate exact migration plan, not speculative changes or arbitrary support claims.
11. **Read-only presentation.** Preserve Godot bounded queues/LOD, fix lossless Research UI paging and scope cancellation, and expose incomplete discovery honestly. No new observer protocol or world write authority.
12. **Measured operating envelope.** Final verified-through rows are qualified by workload, population/events/provenance, modes, storage, coverage, platform and repeated evidence. Incomplete 100k is a documented limitation; no universal maximum, throughput, RSS, FPS or latency SLA is invented.

### Investigation disposition fixed by this plan

| Requested option | Planned treatment |
| --- | --- |
| Snapshot strategy | Measure full payload/projection cost and existing deterministic cadence trade-offs; Tasks 2, 9, 20 |
| Cold historical storage | Verified copy-only segments and offline read adapter; Task 10 |
| Partitioning | Measure temporal/scope segment layout and DB cost; SQL partition migration deferred, no destructive tiering |
| Indexes | Reuse existing SQL indexes; add versioned physical range/adjacency indexes; Tasks 7, 9, 11–12 |
| Materialized analytical views | Disposable exact sidecar checkpoints, not new authoritative DB tables; Task 14 |
| Incremental metrics | Two exact families, sealed-window two-pass trait rows, existing batch oracle and unchanged remaining families; Tasks 14–15 |
| Lineage compression | Lossless page/content reuse, preserve every edge/witness; Task 11 |
| Bounded hot-state loading | Active index/frozen owner graphs, bounded fetches/spool/cache; Tasks 4–8, 13–15 |
| Pagination | SQL keysets, physical pages, lossless UI continuation; Tasks 7–12, 17 |
| Streaming | Batched verification, archive/spool iteration and canonical publication; Tasks 8, 10, 13 |
| Batch analytics | Pinned shared evidence sessions, exact reducers, explicit global-family limits; Tasks 14–15 |

## Phase Index

1. [Phase 1: Measurement and equivalence](v3-43-phase-01-measurement.md) — Tasks 1–3
2. [Phase 2: Active runtime and retired owners](v3-43-phase-02-active-runtime.md) — Tasks 4–6
3. [Phase 3: Replay and historical queries](v3-43-phase-03-replay-and-queries.md) — Tasks 7–9
4. [Phase 4: Historical storage and lineage paging](v3-43-phase-04-historical-storage.md) — Tasks 10–12
5. [Phase 5: Capture and analytics](v3-43-phase-05-capture-and-analytics.md) — Tasks 13–15
6. [Phase 6: Read-only presentation](v3-43-phase-06-presentation.md) — Tasks 16–18
7. [Phase 7: Measured envelope and acceptance](v3-43-phase-07-measured-envelope.md) — Tasks 19–21

## Cross-Phase Dependencies

- Tasks 1→2→3 establish workload identity, baseline and correctness before optimization. Each later phase reuses Task 3's oracle.
- Task 4 precedes Task 5; Task 6 uses Task 3 and can be developed after scheduling is stable. Phase 2 is complete before final runtime benchmarking.
- Task 7 precedes Task 8; Task 8 also verifies Task 6's derived state. Task 9 depends on Tasks 7–8.
- Task 10 depends on bounded verified reads (7–9). Tasks 11–12 share only immutable layout/cursor contracts and may be developed independently after those gates, then verified together.
- Task 13 consumes frozen owner exports (5) and append-only archive patterns (10), not the independent lineage/civilization physical paging changes (11–12). Task 14 depends on 6 and 13. Task 15 depends on 7, 13 and 14.
- Task 16 depends on 9/11/12; Task 17 depends on 11/12, not the offline batch path in Task 15. Task 18 depends on 16–17 and the historical fixtures.
- Task 19 requires all implementation phases; Task 20 requires actual Task 19 results; Task 21 requires the qualified envelope and all correctness gates.
- Execute the listed order by default. Parallel file edits are not required; no agent may mark a downstream task complete before dependency evidence exists.

## Tasks

### Phase 1
- [x] Task 1: Define realistic V3 workloads and measurement contracts ([details](v3-43-phase-01-measurement.md#task-1-define-realistic-v3-workloads-and-measurement-contracts))
- [x] Task 2: Capture bounded before-profiles and a storage/query cost ledger ([details](v3-43-phase-01-measurement.md#task-2-capture-bounded-before-profiles-and-a-storagequery-cost-ledger)) (depends on 1)
- [x] Task 3: Establish exact equivalence and historical query oracles ([details](v3-43-phase-01-measurement.md#task-3-establish-exact-equivalence-and-historical-query-oracles)) (depends on 1, 2)

### Phase 2
- [x] Task 4: Schedule only active runtime ordinals ([details](v3-43-phase-02-active-runtime.md#task-4-schedule-only-active-runtime-ordinals)) (depends on 3)
- [x] Task 5: Freeze dead-owner state and release live cognition graphs ([details](v3-43-phase-02-active-runtime.md#task-5-freeze-dead-owner-state-and-release-live-cognition-graphs)) (depends on 4)
- [x] Task 6: Increment population progress and eliminate same-tick prefix scans ([details](v3-43-phase-02-active-runtime.md#task-6-increment-population-progress-and-eliminate-same-tick-prefix-scans)) (depends on 3, 4)

### Phase 3
- [x] Task 7: Add bounded journal/head ports and push manifest bounds into SQL ([details](v3-43-phase-03-replay-and-queries.md#task-7-add-bounded-journalhead-ports-and-push-manifest-bounds-into-sql)) (depends on 3)
- [x] Task 8: Verify and fold replay in bounded batches ([details](v3-43-phase-03-replay-and-queries.md#task-8-verify-and-fold-replay-in-bounded-batches)) (depends on 6, 7)
- [x] Task 9: Remove redundant observer restores and benchmark checkpoint strategies ([details](v3-43-phase-03-replay-and-queries.md#task-9-remove-redundant-observer-restores-and-benchmark-checkpoint-strategies)) (depends on 8)

### Phase 4
- [x] Task 10: Export immutable segmented historical copies and verify offline replay ([details](v3-43-phase-04-historical-storage.md#task-10-export-immutable-segmented-historical-copies-and-verify-offline-replay)) (depends on 9)
- [x] Task 11: Preserve all lineage continuations and paginate adjacency physically ([details](v3-43-phase-04-historical-storage.md#task-11-preserve-all-lineage-continuations-and-paginate-adjacency-physically)) (depends on 3, 9)
- [x] Task 12: Index civilization shard ranges before reading old pages ([details](v3-43-phase-04-historical-storage.md#task-12-index-civilization-shard-ranges-before-reading-old-pages)) (depends on 3, 9)

### Phase 5
- [ ] Task 13: Spool optional capture through append-only neutral ports ([details](v3-43-phase-05-capture-and-analytics.md#task-13-spool-optional-capture-through-append-only-neutral-ports)) (depends on 5, 10)
- [ ] Task 14: Add exact incremental population and trait-dynamics calculations ([details](v3-43-phase-05-capture-and-analytics.md#task-14-add-exact-incremental-population-and-trait-dynamics-calculations)) (depends on 6, 13)
- [ ] Task 15: Page batch evidence and reuse pinned historical samples ([details](v3-43-phase-05-capture-and-analytics.md#task-15-page-batch-evidence-and-reuse-pinned-historical-samples)) (depends on 7, 13, 14)

### Phase 6
- [ ] Task 16: Keep Godot replay bounded under long seek/catch-up workloads ([details](v3-43-phase-06-presentation.md#task-16-keep-godot-replay-bounded-under-long-seekcatch-up-workloads)) (depends on 9, 11, 12)
- [ ] Task 17: Make Research UI historical paging lossless and scope-safe ([details](v3-43-phase-06-presentation.md#task-17-make-research-ui-historical-paging-lossless-and-scope-safe)) (depends on 11, 12)
- [ ] Task 18: Exercise real historical safety across backend and clients ([details](v3-43-phase-06-presentation.md#task-18-exercise-real-historical-safety-across-backend-and-clients)) (depends on 16, 17)

### Phase 7
- [ ] Task 19: Run paired 10k/100k, dense-generation and historical-query acceptance ([details](v3-43-phase-07-measured-envelope.md#task-19-run-paired-10k100k-dense-generation-and-historical-query-acceptance)) (depends on 1–18)
- [ ] Task 20: Validate the measured support envelope and operational recommendations ([details](v3-43-phase-07-measured-envelope.md#task-20-validate-the-measured-support-envelope-and-operational-recommendations)) (depends on 19)
- [ ] Task 21: Complete regression/security boundaries and mandatory documentation checkpoint ([details](v3-43-phase-07-measured-envelope.md#task-21-complete-regressionsecurity-boundaries-and-mandatory-documentation-checkpoint)) (depends on 20)

## Commit Plan

Commit checkpoints are proposed implementation boundaries, not authorization to commit during planning.

1. After Tasks 1–3: `test(scale): add reproducible V3 workloads and parity oracles`
2. After Tasks 4–6: `perf(simulation): separate active cognition from retired owner history`
3. After Tasks 7–9: `perf(replay): batch verified history reads and index observer lookup`
4. After Tasks 10–12: `feat(persistence): add verified cold copies and paged historical indexes`
5. After Tasks 13–15: `perf(analysis): spool evidence and increment exact V3 metrics`
6. After Tasks 16–18: `fix(observer): bound historical playback and lossless research paging`
7. After Tasks 19–21: `test(scale): qualify measured V3 operating envelopes`

## Blocking Questions and Measurement Gates

No unresolved architecture choice blocks starting Task 1. Performance numbers, recommended cadences/budgets and verified workload horizons are deliberately not selected before measurement. Their decision procedure is fixed in Tasks 2 and 19–20; implementation must narrow claims when evidence is missing, not guess.

Required environments for complete qualification: a disposable PostgreSQL/pgvector database, enough explicit time/disk/RAM budget for long runs, pinned Godot 4.7 and the existing configured real-browser suite. Missing prerequisites block only the corresponding acceptance/support claim, not permission to work on network-free tests. All skipped gates remain visible.

If complete frozen-owner exports, incremental channel replay or canonical metric parity cannot be preserved, stop the affected task with a concrete blocker. Do not weaken the contract or replace it with an unplanned lossy/approximate implementation.

## Approved Refinements

Approved during `$aif-improve` on 2026-10-26; original request, task IDs and all unchecked statuses preserved.

- Tasks 1, 3, 19: supervised resource enforcement and identical paired scientific IDs, with isolated storage and truthful interrupted-run evidence.
- Task 5: deeply detached mutable fork leaves, zero extra clock calls, complete bundle graph release, mode-safe exports and retention propagation through factory clones.
- Task 7: shared whole-commit/bootstrap boundary resolver, replacing the speculative full-prefix cache and nonexistent mid-tick manifest semantics.
- Task 8: streamed canonical payload/commit verification and bounded full-tick authentication for event-prefix seeks.
- Tasks 11–12: bounded hierarchical authenticated metadata roots, unchanged old formats/limits and explicit logical-versus-physical quota accounting.
- Task 13: real source-backed normalizer/publication/artifact composition, distinct from budgeted global batch analysis.
- Task 14: sealed-window two-pass trait union/output with late-trait zero rows and exact canonical ordering.
- Dependencies: remove Task 13's unnecessary dependencies on 11/12 and Task 17's unnecessary dependency on 15. No task added, removed or marked complete.

## Implementation Verification Notes

- Tasks 1–2 (2026-10-26): added deterministic `v3_workloads.py`, strict `v3_measurement.py`, fresh-process `v3_supervisor.py`, bounded `v3_profiling.py`, the opt-in long-horizon driver, and harness snapshot timing replacement. `tests/unit/test_v3_scale_workloads.py` passes (19 tests, including fake-worker success/timeout/RSS/nonzero/missing-terminal, recursion guard, coverage paths, cost ledger and measurement secrecy).
- 10k baseline (guarded disposable PostgreSQL, `/tmp/opencode/v3-43-scale/baseline-10k-v3`, not committed): generational completed 10,000 ticks / 5 cohorts in 126.2 s; evidence-rich completed 10,000 ticks / 5 cohorts in 158.6 s; flags-off control exceeded the 1,800 s budget at 5,651 verified ticks (truthful `timed_out`). Completed artifacts record stage durations, 71,838 SQL calls / 40,204 rows, RSS samples (peak ≈274 MiB), index inventory and table sizes; SQL byte counters are explicitly unavailable.
- 100k attempt (same database, `/tmp/opencode/v3-43-scale/baseline-100k`, 300 s per lane): all lanes are truthfully incomplete (`timed_out`) at verified boundaries 2,208 (control), 24,144 (generational) and 16,444 (evidence). No 100k dense support is claimed. Longer budgets and separate per-attempt storage namespaces remain required for qualified Task 19/20 measurements.

- Task 3–4 (2026-10-26): added paired exact-execution/query-oracle helpers and covered all eight lineage families, cursor scope, coverage denominators and high-water checks. `tests/unit/test_v3_scale_equivalence.py` plus V1/V2/checkpoint gates pass (26 tests). `SimulationRunner` now keeps permanent registration ordinals but iterates a derived active-ordinal registry; terminal owners leave scheduling only after finalization, mid-run admissions append permanent ordinals, restore rebuilds the index from runtime status, and capture still stages detached observations for retired owners. `tests/unit/test_runner_active_owners.py` and `test_runner_fork_checkpoint.py` pass (13 tests).

- Task 6 (2026-10-26): added `PopulationProgressAccumulator` with exact full-fold bootstrap, incremental admission/death application, replay/gap rejection and runner integration; replaced same-tick event-prefix scans with chunk-metadata counting and added range/suffix traversal to `HistorySequence`. `tests/unit/test_incremental_population_progress.py`, `test_engine_history_sequence.py` and `test_v3_scale_equivalence.py` pass (14 tests). Task 5 remained pending at that point because complete frozen-owner graph replacement and all export consumers required a larger isolated change; no partial freeze was introduced then.

- Task 7 (2026-10-26): added the extended `BoundedTickJournalRepository`, detached `DurableHead`, legacy-compatible head resolution, SQL keyset commit/event-ID/latest-event reads, shared `resolve_objective_evidence_boundary`, and SQL-level manifest-bounded inspection pages. Unit (`5 passed`) and guarded-PostgreSQL integration (`1 passed`) bounded-read tests pass; analysis and inspection share the same whole-commit/bootstrap resolver. No schema or migration change.

- Task 8 (2026-10-26): completed bounded verified replay. Added frozen `VerifiedReplayBatch`, engine-owned `WorldEngine.restore_from_verified_batches` with an incremental tick builder (objective projection, population pending reservations, skill growth, kinship edges, chunked event history and window-bounded teaching offers), and `_replay_bounded` commit/event keyset streaming with per-tick payload/commit verification and predecessor/revision continuity. `scene_through_event` now authenticates the complete tick while retaining only the requested prefix. Added tests for legacy/bounded parity across targets, empty-tick chains, split pages, tampered payloads, predecessor corruption and reordered events; `tests/unit/test_replay_bounded_reads.py` passes (18 tests), the focused checkpoint/observer/equivalence/architecture suites pass, and the default suite passes (6365 passed, 121 deselected). The guarded-PostgreSQL integration test remains skipped without `PALIMPSEST_TEST_DATABASE_URL`; no durable-page bound is claimed from that skip. `src/persistence/evidence_boundary.py` now validates run IDs locally so persistence retains no `world` import.

- Task 9 (2026-10-26): observer `events()` now validates its cursor against a detached `DurableHead` and `run()` returns manifest/head metadata without a scene restore; `_history_through_event` resolves the head once and performs one prefix replay. Added `ReplayService.head`, `run_manifest` and indexed `read_event`; `event()` no longer performs the fixed 100×100 scan. Added an instrumented unit test proving event/run reads make zero scene restores and prefix state makes exactly one; a guarded-PostgreSQL cadence profiler measures checkpoint-off/100/500/1000 with identical projection/event identities and records actual snapshot read/hash timings, and the bounded-read integration test records `EXPLAIN` plans for keyset and event-ID lookups. Default suite passes (6367 passed, 122 deselected); DB/scale gates remain opt-in and were skipped without `PALIMPSEST_TEST_DATABASE_URL`.

- Task 5 (2026-10-27): added composition-only `RuntimeRetentionPolicy` (default off) propagated through both factory clones, frozen `RetiredOwnerRecord`, read-only owner adapters, and `AgentRuntime.freeze_terminal`. At each finalized boundary, confirmed-terminal owners export runtime/subjective fork state and audit inventory once, then release loop/readers/writers/services/retriever references and replace the bundle with read-only memory/belief/relationship/commit views. Fork capture merges frozen records in registration order; regional destination traces, final research/cultural/civilization exports and audit harvesters remain exact. Added detached `TickBudgetForkState` and clock-free ledger restore plus immutable translation-application pairs. Unsupported/non-fork-capable bundles stay live and increment `retirement_unsupported_count`; metadata-only recovery cannot fabricate a retired record. `tests/unit/test_retired_owners.py` passes (6 tests, including fork restore and unsupported fallback), budget/translation isolation tests pass, and the default suite passes (6374 passed, 122 deselected).

- Task 10 (2026-10-27): added neutral `simulation.history_archive` manifest/segment/index contracts, content-addressed `persistence.history_archive_filesystem` writer and read-only adapter, and `research_runner.history_archive_composition` export/verify composition plus `history-export` / `history-verify` CLI commands. Events, commits and snapshots use separate canonical lanes with row/byte segment caps, globally sorted event-ID and snapshot-ID index pages, pinned verified durable heads, exact split-tick coverage, immutable object/manifest publication behind one atomic run-state reference, auxiliary hashed sibling copies with declared omissions, and a read-only adapter implementing the bounded runs/journal/snapshot ports (append attempts fail closed). Added `SqlAlchemySnapshotRepository.list_snapshots` for explicit offline enumeration; no schema or migration change. `tests/unit/test_history_archive.py` passes (9 tests: split ticks, deep event-ID lookup beyond early segments, retry/idempotence, hidden uncommitted publication, conflicting publication, missing/tampered objects, restart queries, auxiliary/omissions, CLI success/tamper, composition through-tick pinning). Guarded disposable PostgreSQL `tests/integration/test_history_archive.py` passes (1 test: source counts unchanged, full verification, archive/SQL replay parity at ticks 0/2/4/6, restart event lookup, tamper rejection). A completed 6-tick export was also exercised end-to-end: `uv run palimpsest-matrix history-export --run-id ... --output /tmp/opencode/v3-43-scale/archive` and `history-verify --archive ... --full` both exited 0; tampered input returns nonzero. Default unit suite run: 6102 passed, 6 deselected, with one pre-existing institutional-memory idempotency failure that passed immediately on isolated rerun.

- Task 11 (2026-10-27): fixed lineage capture to consume every adjacency continuation with non-advancing-cursor rejection and exact edge deduplication; the high-degree regression (259 edges on one node across physical pages) confirms capture and paged reads preserve every edge. Added strict `lineage-store-index-v2` physical roots/index pages in `simulation.lineage_store_index` (max 256 entries/page, existing 256 KiB record/root caps, bottom-up authenticated page trees, no flat descendant digest list) and switched new publications to content-addressed run-level objects with `store/root.json`, atomic publication/commit ordering, and preserved logical `lineage-snapshot-v1` content digests. Four fixed-purpose roots cover node catalogue, adjacency, identity lookup and object integrity; node catalogue pages, adjacency pages and identity objects are content-addressed and reused across publications while quota charging remains logical. The reader dispatches v1 manifest/object layouts and v2 root/index layouts; node catalogue paging selects pages before filtering, exact identity lookup reads one identity object and one node descriptor, adjacency reads only the indexed pages for the requested node/direction and loads endpoints only for the selected response rows, and request-local index/object caches use the existing read budget. Tests: `test_lineage_filesystem.py`, `test_lineage_limits.py`, `test_lineage_pagination.py`, `test_lineage_api.py`, all `test_lineage_*`, lineage capture/institution/mentorship/knowledge suites, architecture boundary and V3 equivalence suites pass (190 focused tests); acceptance coverage command passes (17 tests). Added old-v1/new-v2 parity, 259-edge high-degree capture/pagination, 3,000-node root-size/object-cap/deep-page/exact-lookup and cross-publication object-reuse regressions. No schema, migration, API-protocol or file-format rewrite of sealed v1 publications.

- Task 12 (2026-10-27): added `civilization-store-index-v2` with a bounded `store/root.json` and authenticated paged directories for boundary catalogue ranges and scope-qualified row-shard ranges. Row-shard entries carry `(scope, boundary, first_row, last_row)`, row/byte counts and original digests, built from a small per-boundary row-bounds sidecar so v1 manifest ordering and sealed files stay unchanged. New publications write child-first index/root objects before the atomic state reference; old publications without the root keep the v1 catalogue/manifest read path. The reader dispatches explicitly, selects catalogue pages and row shards by authenticated range before reading/hashing them, validates ordered non-overlapping ranges and child digests, preserves cursor/coverage/scan-budget semantics, and does not cache across requests. Tests: 9 civilization filesystem tests incl. dense 450-row deep pagination (physical files <=10, scanned rows <=60 on the final page), bounded root/index objects (<=64 KiB), new-publication cursor invalidation, v1/v2 parity by removing the v2 root, and tampered-index rejection; all civilization/observer suites pass (267 focused tests) and the dense civilization playback benchmark passes (2 tests). No SQL migration, API-protocol/version change, or rewrite of sealed v1 publications. Deep-page and playback tests now measure selected physical reads rather than only returned row counts; residual read amplification is one bounded directory descent plus candidate shards.

## Definition of Done

- All 21 tasks meet their linked acceptance criteria; only this index carries task progress.
- Original events, commits, snapshots, required memories/provenance and published history remain immutable and queryable; dead-owner optimization preserves full fork/export evidence and appropriate historical access.
- Runtime, replay, capture, analytics and clients have exact parity plus bounded-operation evidence; residual cumulative history/materialization costs are documented.
- Every requested benchmark category has reproducible complete/incomplete/unexecuted evidence. At least one sustained multi-generation lane completes. No unmeasured dense-100k, population capacity, universal maximum or browser-performance promise appears.
- Old/new artifact layouts, capability separation, corruption failures, signed cursors, append-only triggers and flags-off regressions remain correct.
- Mandatory documentation checkpoint records the measured qualified envelope, reproduction commands, remaining limitations and explicit unsupported/unverified cases.
