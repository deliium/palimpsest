# Phase 3: Bounded durable reads, verified replay and indexed observer access

Plan: [index.md](index.md)
Tasks: 7–9
Depends on: Tasks 1–3; Task 6 for derived-state parity

## Objective

Remove full-journal work from page/head/event lookup, and verify large replay ranges in bounded database batches without weakening commit-chain checks. Keep snapshot cadence explicit and measured.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/simulation/persistence.py` | `TickJournalRepository` 1615; `ReplayCommitPage` 1688 | Existing protocol lacks bounded commit pages/latest commit/event-ID lookup. |
| `src/persistence/sqlalchemy.py` | `SqlAlchemyTickJournalRepository`; snapshot lookup 505 | Keyset event reads and indexed snapshot selection already exist. |
| `src/simulation/replay.py` | replay 502–649; `read_commit_page` 891; `_durable_head_next_tick` 932 | Loads all commits and a ten-million-event suffix before restore. |
| `src/simulation/engine.py` | `restore_from_snapshot` 838–1032 and subsequent channel refolds | Projection and channel restoration must stay inside engine authority. |
| `src/persistence/inspection_sqlalchemy.py` | `load_events_page` 71–175 | Manifest-pinned page currently decodes the entire journal. |
| `src/simulation/evidence.py`, `src/simulation/inspection.py`, `src/persistence/analysis_sqlalchemy.py` | `EvidenceManifest`; `constrain_events_to_manifest` 1099; commit/bootstrap resolution 185–204 | Objective high-water is a whole commit hash; the inspection clamp currently validates run scope only. Existing analysis loading already resolves the real boundary. |
| `src/simulation/journal.py` | `hash_tick_payload`, `compute_commit_hash`, `verify_commit_chain` | Chain validation does not rehash event payloads; canonical payload/commit hashes need explicit streamed verification. |
| `src/api/observer_service.py` | `events` 411; `event` 547; `_history_through_event` 654 | Head replay per page, 10k-event search ceiling, duplicate prefix restoration. |
| `src/persistence/orm.py` | `WorldEventOrm` 323–355 | Event ID already has a unique index; PK orders run/tick/sequence. |
| `src/simulation/runner_models.py` | `RunnerCheckpointPolicy` 7185; presets 7234 | Defaults off; existing 100/500/1000 cadence helpers are not measured guarantees. |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/simulation/persistence.py` | modify | Add separate extended bounded journal protocol and detached head DTO; keep legacy protocol accepted. |
| `src/persistence/sqlalchemy.py` | modify | Indexed head/commit pages/event-ID reads with upper-bound pinning. |
| `src/persistence/inspection_sqlalchemy.py` | modify | SQL-level verified manifest high-water and bounded decoding. |
| `src/persistence/evidence_boundary.py` | create | Shared run-scoped commit-hash/bootstrap-boundary resolver extracted from existing analysis-loader behavior. |
| `src/persistence/analysis_sqlalchemy.py` | modify | Reuse the shared resolver without changing its existing manifest semantics. |
| `src/simulation/journal.py` | modify | Incremental canonical tick-payload/commit verification with exact legacy hash parity. |
| `src/simulation/replay.py`, `src/simulation/engine.py` | modify | Batch verification/fold and stable head resolution; legacy callers preserved. |
| `src/api/observer_service.py` | modify | Use head/event-ID ports; avoid redundant head restore for prefix seeks. |
| `tests/unit/test_replay_bounded_reads.py`, `tests/integration/test_replay_bounded_reads.py` | create | Exactness and fetched-row bounds. |
| `tests/unit/test_observer_replay.py`, `tests/integration/test_long_run_checkpoints.py` | modify | Late IDs, seek parity, cadence cost measurements. |

## Task 7: Add bounded journal/head ports and push manifest bounds into SQL

### Implementation Steps

1. Introduce a separate `BoundedTickJournalRepository` protocol with `get_latest_tick_commit(run_id, *, through_tick=None)`, `list_tick_commits_keyset(run_id, *, after_tick, through_tick, limit)`, and `get_event_by_id(run_id, event_id, *, through_tick=None)`. Exact positive page cap reuses the replay event-page maximum (1000); keysets are exclusive and upper bounds inclusive. Do not make new methods mandatory on legacy `TickJournalRepository` implementations.
2. Implement SQL queries using existing run/tick primary keys and unique event-ID index. Always constrain event-ID lookup by authorized run; a valid event ID from another run is not found. `get_latest` uses descending tick and `LIMIT 1` plus manifest/bootstrap semantics for empty runs.
3. Add detached `DurableHead` metadata containing run/schema identity, next tick, revision, last commit hash and latest event cursor. Resolve it from one verified head commit and bounded latest-event query; no retained engine or mutable API cache. Pin a request to that head so concurrent appends cannot change page coverage mid-request.
4. Extract `resolve_objective_evidence_boundary(session, *, run_id, manifest) -> ObjectiveEvidenceBoundary` into `persistence/evidence_boundary.py`, reusing the exact `SqlAlchemyAnalysisEvidenceLoader.load` branch at lines 185–204. Resolve `manifest.objective_commit_hash` under the same run using existing unique `(run_id, commit_hash)` indexing; a matched commit supplies inclusive `through_tick` and `resulting_tick`. A hash equal to that run's verified bootstrap snapshot integrity hash means boundary zero and an empty event page. An unknown or cross-run anchor raises `manifest_objective_commit_not_found`. Validate the immutable manifest's own hash through the existing DTO contract.
5. Push the resolved whole-commit tick bound into the event SQL query before ordering/`LIMIT limit+1`, alongside the exclusive page cursor. `EvidenceManifest` has no mid-tick event mark or event-count high-water; its subjective high-water counts are unrelated to objective event pagination. `constrain_events_to_manifest` currently validates run scope only, so describe this as restoring the intended commit-bound inspection contract, not preserving nonexistent prefix/count checks. Reuse the same resolver in analysis loading and inspection; no full-prefix verification cache or O(history) verification scan is required for a page. Replay verifies requested event payloads separately in Task 8.
6. Retain explicit compatibility adapters for in-memory/test/third-party legacy repositories. A legacy materializing path is permitted only for those adapters and is labelled in benchmark output; the durable SQL scale path must never silently select it. Update relevant fakes.

### Required Interfaces and Contracts

No database schema change is needed: existing indexes serve these exact queries, including `uq_tick_commits_hash`. Keep `ReplayCommitPage` semantics and previous read methods. `ObjectiveEvidenceBoundary` is a detached persistence helper value with boundary tick and optional inclusive commit tick, not a new scientific schema. Page materialization is at most cap+1 ORM/DTO event rows plus bounded anchor/bootstrap metadata. There is no per-page or cached full-prefix scan.

### Requirement Evidence

User: indexes, pagination, bounded loading and immutable history. Architecture: inward ports and signed high-water identity. Source anchors: repository/inspection implementation above.

### Error Handling and Logging

Missing/corrupt commit anchor produces the existing discontinuity/inspection error, not an empty successful page. DEBUG: repository path, fetched/decoded row count, page size, resolved boundary, duration. Never log query parameters containing credentials or evidence bodies.

### Tests

Add exact SQL count/fake-row tests for 1 versus many pages, all events of the anchored commit included and later commits excluded, bootstrap-only manifest, cursor at/past the anchored commit, eventless anchored commit, concurrent append, unknown/cross-run anchor and legacy adapters. Inspection and analysis must resolve identical boundaries. Invalid event payload/commit hash tests belong to Task 8, not fictitious mid-tick manifest marks. Query bounds must be asserted independently of elapsed time.

### Acceptance Criteria and Verification

`uv run pytest tests/unit/test_replay_bounded_reads.py --cov=simulation --cov=persistence --cov-report=term`; then `uv run pytest -m integration tests/integration/test_replay_bounded_reads.py --cov=simulation --cov=persistence --cov-report=term`. A deep page fetches only cap+1 event rows plus bounded anchor metadata, not the journal prefix.

## Task 8: Verify and fold replay in bounded batches

### Implementation Steps

1. Resolve manifest, pinned head and nearest compatible snapshot once. Keep `REQUIRE_EXACT`, fallback policy, snapshot hash/version checks and predecessor validation unchanged.
2. Read commit pages and matching event keysets under a fixed upper head. Carry expected next tick, predecessor hash, revision, per-commit event count and sequence across page boundaries. Eventless ticks advance from commits. A page may split a high-event tick; maintain per-commit verification state instead of requiring all events for one tick in RAM.
   Introduce `StreamedTickCommitVerifier` in `simulation.journal`: feed each ordered event's existing `hash_world_event` result into incremental SHA-256 encoders for the canonical `hash_tick_payload` and `compute_commit_hash` JSON forms. Preserve exact sorted-key ordering, separators, JSON escaping and array punctuation, including the empty-array case. Compare both resulting digests and event count to the stored `TickCommit` before accepting that tick. Validate run/world/schema/tick/sequence and revision continuity using the existing version-selected contracts. `verify_commit_chain` alone only checks predecessor links; do not call it payload verification or blindly use the legacy `verify_tick_events` accepted-schema list for newer V3 events.
3. Factor `WorldEngine.restore_from_snapshot` into an engine-owned private restore builder and its existing public wrapper. Introduce async `WorldEngine.restore_from_verified_batches(snapshot, *, batches: AsyncIterable[VerifiedReplayBatch], committed_through_tick, **existing_channel_arguments) -> WorldEngine` as an internal-to-simulation entry point. Define frozen `VerifiedReplayBatch` beside replay contracts with ordered events, verified commit cursor/predecessor and partial-tick continuation metadata; retain explicit typed channel arguments in actual code, not an open `**kwargs` schema. The verifier yields bounded chunks, the engine initializes objective/channel state once, consumes them through the same private projector, then finalizes tick cursor and prior-event window. `simulation.replay` never imports private world modules or mutates `WorldState`.
4. Preserve population admissions/initialization, kinship, custody, skills, teaching, records, journeys and every existing version-selected channel refold. For refolds currently requiring a complete prefix, add engine-owned incremental fold state with exact batch-boundary tests; do not omit them to obtain a faster base-state projection.
5. Do not expose a partially restored engine. Only after all range/chain/count checks and finalization succeed return the existing `ReplayOutcome`. On corruption/cancellation discard the builder and return the existing safe failure result.
6. Preserve complete public event-history exports using `HistorySequence` chunks; avoid duplicate tuple/ORM copies. Thus database/working-batch loading is bounded, but a legacy caller requesting a full event suffix still retains O(suffix) history. Record that residual cost honestly; do not silently empty `ReplayOutcome.engine.export_events()` or change observer overlay evidence.
7. Replace `read_commit_page` materialize-then-slice and head-from-tick-zero logic with Task 7 ports. Keep legacy compatibility tested. Count fetched events, commit pages and replay distance using actual timers.
8. Replace the separate `scene_through_event` whole-tick `list_events(limit=10_000_000)` path with the same bounded verifier. Fetch the tick commit and stream its complete event pages to validate payload/commit identity; feed only events through the requested sequence into an engine-owned private prefix builder. Do not advance the engine tick/revision at intermediate batch ends. Finalize `includes_last_event` from verified complete tick metadata, preserve the existing partial-prefix scene semantics, and expose no prefix result until full tick verification succeeds. Missing requested sequence, corrupt later suffix or cancellation discards the private builder. This path may retain the explicitly requested event prefix in public history, but must not materialize the rest of the tick merely to find its last event.

### Required Interfaces and Contracts

Streaming verification is not permission to trust gaps or reset hash-chain state per page. Provisional chunks stay private until the containing tick and complete requested range validate; a partially consumed async iterator is never a successful restore. `events_applied`, restored phase, prior committed window, continuation eligibility and final predecessor hash are unchanged. This task introduces no new replay/codec identifier. Existing canonical hash functions remain the small-fixture oracle for streamed encoding.

### Requirement Evidence

User: snapshot strategy, large logs, historical seek and streaming. Architecture: engine-only authority and live/restored canonical parity. Existing `ReplayService.replay` checks are mandatory, not optional overhead.

### Error Handling and Logging

Reuse version/corruption/discontinuity reason codes. DEBUG aggregated pages/rows/fold distance; INFO completed restore summary. A failed page never returns a partial success or writes a replacement snapshot. Cancellation closes database sessions promptly.

### Tests

Batch sizes 1/2/cap against the reference restore; eventless gaps; one tick exceeding a page; omitted/duplicate/reordered events; cross-page predecessor corruption; concurrent head append; cancellation; exact snapshot and fallback cases. Streamed hashes must equal `hash_tick_payload`/`compute_commit_hash` for empty, Unicode-containing and split-page ticks. Tamper a payload while keeping event count and predecessor links unchanged: replay and event-prefix seek must fail. Test prefix sequence before/at the last event, page boundaries, corrupt later suffix and explicit requested-sequence absence. Parameterize representative old schemas and current feature-selected replay-v22/codec-v20, including teaching, kinship and migration. Extend existing checkpoint parity and prior-window tests.

### Acceptance Criteria and Verification

`uv run pytest tests/unit/test_replay_bounded_reads.py tests/unit/test_checkpoint_restoration.py tests/unit/test_v3_scale_equivalence.py --cov=simulation --cov=world --cov-report=term` passes. Durable Task 7 integration tests assert page-sized fetches even when replay spans many pages.

## Task 9: Remove redundant observer restores and benchmark checkpoint strategies

### Implementation Steps

1. Use `DurableHead` for `ObserverService.events` ahead-cursor validation and metadata-only `run` responses where no scene is required. Keep capability admission and manifest/schema checks before repository reads. Do not replace scene construction for endpoints that actually need scene facts.
2. Replace the fixed 100×100 scan in `event()` with run-scoped indexed lookup. Add `ReplayService` delegation rather than importing a persistence adapter into API. Preserve `observer_event_not_found` for genuine absence, not merely deep position.
3. Resolve the head once for `_history_through_event`, then restore the requested event prefix directly under that head; preserve event-prefix versus end-of-tick semantics and return detached facts only. No engine cache.
4. Measure snapshot serialization, normalized graph writes, canonical payload bytes and seek folds under existing cadence 100/500/1000 and checkpoint-off, using identical histories. Recommend a cadence only in the measured profile in Task 20; do not change defaults or introduce adaptive cadence dependent on machine wall time.
5. Record `EXPLAIN` results for existing event filter/order queries and index write/storage cost. This plan ships no speculative composite indexes and no Alembic migration. If existing indexes fail the measured target, mark that envelope unverified/limited and scope a separate exact-index migration rather than guessing during implementation. Likewise document partitioning findings without changing append-only table ownership.

### Required Interfaces and Contracts

Stable `/v1`, observer protocol v1, existing page limits/filter meanings and snapshot formats. Snapshot sparseness changes growth rate, not total storage bounds. No snapshot GC or redundant event-ID index.

### Requirement Evidence

User: historical seek/playback, indexes/partitioning/snapshots and measured supported limits. Existing indexed unique event ID and snapshot seek already supply necessary primitives.

### Error Handling and Logging

Preserve safe not-found/ahead/forbidden distinctions. DEBUG head lookups and restore count; no payload-bearing exception text. Required snapshot corruption still fails, never falls back to an unverified head.

### Tests

Late event ID beyond the old 10k ceiling, cross-run ID, filtered empty continuations, eventless head, append during paging, backward/forward prefix parity and read-only/no-retained-engine assertions. Instrument call counts: event pages perform zero scene restores and prefix seek does not restore head first.

### Acceptance Criteria and Verification

`uv run pytest tests/unit/test_observer_replay.py tests/unit/test_replay_bounded_reads.py --cov=api --cov=simulation --cov-report=term`; durable checkpoint/cadence suite with `-m integration`. Benchmark actual checkpoint duration, never `elapsed / snapshot_count` or another proxy.

## Phase Risks and Mitigations

- Channel refolding can depend on earlier event prefixes: engine-owned incremental state plus all-version/reference parity is a merge gate.
- A fast head lookup alone does not prove historical prefix integrity: still verify the requested snapshot→target chain and manifest anchor.
- Total restored/public history remains O(history): differentiate working-fetch bounds from retained-history limits in the final envelope.

## Phase Completion Checklist

- Tasks 7–9 pass bounded-row, exact replay, capability and observer tests.
- Existing append-only triggers and Alembic `0017` remain unchanged.
- Update progress only in `index.md`.
