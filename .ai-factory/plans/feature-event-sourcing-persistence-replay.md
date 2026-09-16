# Implementation Plan: Event Sourcing, Persistence, and Deterministic Replay

Branch: feature/event-sourcing-persistence-replay
Created: 2026-09-16

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M4 - Persistence and Analysis"
Rationale: This plan delivers M4's durable simulation history, immutable event storage, checkpoint recovery, replay API, and queryable experiment metadata foundation.

## Goal

Make immutable objective `WorldEvent` records the historical ground truth for world evolution, persist complete simulation runs transactionally in PostgreSQL, and reconstruct the authoritative world at any committed tick from a checkpoint plus subsequent ordered events.

The implementation must support this durable lifecycle:

```text
create immutable run manifest and initial snapshot
-> observe and prepare tick N against authoritative state
-> produce effect-complete, deterministically ordered objective events
-> atomically append tick boundary, events, and optional checkpoint in PostgreSQL
-> publish the prepared in-memory state
-> restore from the latest valid checkpoint plus events through target tick
-> continue the run with the same deterministic ordering and identifiers
```

## Design Decisions

- Expand the objective event contract into a versioned, effect-complete envelope containing `event_id`, `run_id`, `world_id`, `tick`, intra-tick `sequence`, `event_type`, optional actor and target entity IDs, resulting world revision, request correlation, and a closed structured payload. To preserve `world`'s zero-dependency boundary, `WorldEvent` stores run identity as an opaque validated stable string and tick/sequence as exact non-negative integers; `simulation` alone converts to and from its `RunId` and `Tick` value types. Event `(run_id, tick, sequence)` is the canonical order; database insertion order and operational timestamps are never simulation semantics.
- Objective event payloads record committed outcomes rather than instructions to re-run current rules. For example, take/drop/give events identify the actor, affected item, counterparty or location, and resulting ownership/placement facts needed by a strict projector. Future mutating event variants must be similarly effect-complete before they can be emitted.
- Keep rejected, conflicted, duplicate, dead-actor, and deferred submissions out of the objective event stream. Persist a tick commit row even when a tick emits no events so logical tick continuity and checkpoint cursors remain auditable.
- Introduce an explicit persistence event schema/projector version independently from deterministic ID derivation and the existing external export schema. Preserve schema-v1 audit decoding where practical, but classify legacy under-specified events as non-replayable; only the new replay-capable schema may enter the authoritative persisted log.
- Add a private, pure world event projector that applies recorded effects with strict precondition checks and immutable state rebuilding. It must not invoke current command validation or behavioral rules, because later rule changes cannot reinterpret historical facts.
- A public immutable snapshot contains run/world identity, seed and configuration identity, exact ordered agent registrations, complete objective state, `next_tick`, world revision, event/projector versions, and an integrity hash. It contains no live `World`, `WorldState`, session, or capability token.
- `simulation` owns repository protocols, persistence DTOs, durable tick coordination, and replay policy. Domain and simulation code never import SQLAlchemy. A new outer `persistence` package implements those protocols with SQLAlchemy and may import only public `simulation` contracts plus generic `infrastructure` database facilities.
- Preserve `infrastructure` as domain-neutral. Update architecture checks to permit SQLAlchemy only in `infrastructure` and the new `persistence` adapter, while forbidding `simulation -> persistence`, `persistence -> world/private simulation`, and `infrastructure -> simulation` dependencies.
- Split engine tick resolution internally into prepare and finalize stages. The durable service prepares a complete candidate without mutating the live engine, writes the tick transaction, then performs an infallible in-memory reference swap. A database failure leaves the engine unchanged; a process crash after database commit is recovered from persisted history.
- Persist each tick with optimistic predecessor checks, a per-run transaction lock, an idempotency key, payload hashes, and a chained commit hash. Identical retries return the existing commit; the same tick or idempotency key with different content fails as a conflict rather than overwriting history.
- Store snapshots as immutable checkpoints, not mutable current-state rows. Normalized snapshot agent, location, item, resource, and weather rows are query projections tied to one immutable snapshot and written in the same transaction as its canonical payload/hash.
- Create a run atomically: the immutable manifest, seed/configuration, bootstrap checkpoint, normalized checkpoint projections, and optional experiment assignment commit together. The bootstrap checkpoint has `next_tick = 0`, initial revision, and no predecessor commit hash; no partially created run may be visible.
- Enforce append-only history in PostgreSQL with denied mutation paths in repository APIs, `ON DELETE RESTRICT`, and database triggers rejecting `UPDATE`, `DELETE`, and `TRUNCATE` on run history, tick, event, snapshot, and experiment assignment tables. Operational mutable data, if later required, must use separate non-authoritative tables.
- Provide a public asynchronous `ReplayService` that loads a run, selects a valid checkpoint at or before a target tick, validates hashes/version compatibility/stream continuity, and folds subsequent events. Recovery at the durable head may return a continuation-ready engine; historical targets return detached read-only replay results and cannot append to the same run unless a future explicit fork contract is added. No HTTP replay endpoint is required in this feature.
- Keep exact external LLM re-execution outside objective world replay. Full cognition replay continues to require recorded provider responses or deterministic stubs; objective state reconstruction depends only on the persisted snapshot, tick timeline, and objective events.

## Non-Goals

- Adding cognition policies, provider SDKs, prompt storage, or production LLM invocation.
- Reconstructing an agent's subjective memory from objective events or allowing memory claims to alter historical events.
- Inventing behavior for currently deferred movement, nutrition, sleep, help, combat, or flee commands.
- Building experiment analysis metrics or a user-facing HTTP simulation control API.
- Introducing Kafka, Celery, microservices, another database, or `metadata.create_all()` schema management.
- Treating wall-clock timestamps, database row order, or log order as domain time or replay order.

## Commit Plan
- **Commit 1** (after tasks 1-4): `feat(simulation): define replayable event and snapshot contracts`
- **Commit 2** (after tasks 5-8): `feat(persistence): add transactional PostgreSQL event store`
- **Commit 3** (after tasks 9-12): `feat(simulation): add deterministic persisted replay`

## Tasks

### Phase 1: Replayable Domain and Storage Contracts

- [x] Task 1: Define the versioned, effect-complete objective event contract.
  - Deliverable: Evolve `WorldEvent` and its closed payload union so every event carries unique run/world/request/event identity, tick, contiguous intra-tick sequence, explicit event type, optional actor and target, resulting revision, event schema version, and all committed effect facts required for projection. Keep `world` independent by representing run identity as an opaque validated stable string and tick/sequence as exact non-negative integers, with typed conversion owned by `simulation`. Specify field applicability for every event variant, keep communication text bounded, reject unknown fields/types and caller-controlled ordering, and define a migration policy in which legacy schema-v1 audit events remain immutable but are rejected as authoritative replay input when they lack required facts.
  - Files: `src/world/events.py`, `src/world/identifiers.py`, `src/world/_rules.py`, `src/simulation/actions.py`, `src/simulation/lifecycle.py`, `src/simulation/serialization.py`, `src/world/__init__.py`, `src/simulation/__init__.py`, `tests/unit/test_v1_world_events.py`, `tests/unit/test_v1_export_serialization.py`.
  - Logging: Event values and codecs remain log-free on success. Expose stable validation/version error codes; orchestration may log DEBUG IDs, event type, tick/sequence, and schema version, and ERROR failure code/path, but never payload bodies or communication text.
  - Dependencies: None. This contract anchors projection, storage, and replay.

- [x] Task 2: Define immutable run manifests, checkpoints, tick commits, experiment metadata, and repository ports.
  - Deliverable: Add framework-free frozen DTOs for run identity/configuration and seed, initial manifest/bootstrap, immutable `WorldSnapshot`, tick commit cursor/hash metadata, experiment metadata/run assignments, and replay requests/results. Define async protocols for run creation/loading, atomic tick append, snapshot lookup, ordered event reads, and experiment metadata without exposing ORM sessions or private world state. Snapshot values must preserve registration and inventory order, complete locations/agents/items/resources/weather, `next_tick`, revision, codec/projector versions, and integrity hash.
  - Files: `src/simulation/persistence.py`, `src/simulation/models.py`, `src/simulation/bootstrap.py`, `src/simulation/contracts.py`, `src/simulation/__init__.py`, `tests/unit/test_persistence_contracts.py`, `tests/typecheck/persistence_contracts.py`, `tests/typecheck/invalid/`.
  - Logging: DTO and protocol construction stays log-free. Define safe diagnostic fields for repository calls: run ID, tick/revision cursor, record counts, version, and hash prefix only; seeds, full configurations, snapshots, event payloads, and experiment metadata values must not be logged.
  - Dependencies: Depends on task 1 for the authoritative event type and ordering contract.

- [x] Task 3: Add canonical persistence codecs and integrity/hash-chain validation.
  - Deliverable: Create a persistence-specific canonical codec for run manifests, snapshots, tick commits, and objective events rather than widening the existing schema-v1 export allowlist. Use strict JSON with duplicate-key, unknown-field, non-finite-number, malformed-ID, and unsupported-version rejection; deterministic ordering; SHA-256 payload hashes; and a per-run commit chain covering predecessor hash, tick/revision coordinates, and ordered event hashes. Round-trip arbitrary non-negative Python seeds without silently truncating to 64-bit values.
  - Files: `src/simulation/journal.py`, `src/simulation/serialization.py`, `src/simulation/persistence.py`, `src/simulation/__init__.py`, `tests/unit/test_persistence_serialization.py`, `tests/unit/test_v1_domain_serialization.py`.
  - Logging: Codecs and hashing remain log-free during normal use. Return stable error code/path/version information suitable for ERROR logs; never include serialized documents, structured payloads, seeds, or configuration values in exceptions or logs.
  - Dependencies: Depends on tasks 1 and 2.

- [x] Task 4: Implement private event projection and authoritative checkpoint restoration.
  - Deliverable: Add an engine-only private projector that folds replay-capable objective events onto immutable world state using recorded outcomes, validates actor/target existence and preconditions, enforces run/world identity, contiguous tick/sequence order, revision transitions, duplicate event rejection, and post-state invariants, and never calls current command rules. Add internal engine restoration from a validated snapshot/projected state with the exact run ID, seed/config, ordered registrations, next tick, revision, deterministic ID context, and `AWAITING_OBSERVATION` phase; never restore observation tokens or expose a state-replacement hook.
  - Files: `src/world/_replay.py`, `src/world/_state.py`, `src/simulation/engine.py`, `src/simulation/bootstrap.py`, `pyproject.toml`, `tests/architecture/boundary_checker.py`, `tests/architecture/test_boundary_checker.py`, `tests/architecture/test_world_authority.py`, `tests/unit/test_event_projection.py`, `tests/unit/test_checkpoint_restoration.py`.
  - Logging: The pure projector remains log-free. Replay orchestration logs DEBUG run/tick/sequence/version checkpoints, INFO successful restoration bounds and counts, WARN incompatible optional checkpoint fallback, and ERROR stable corruption/mismatch codes without state or event payloads.
  - Dependencies: Depends on tasks 1-3.

### Phase 2: Durable Tick Transactions and PostgreSQL Adapter

- [x] Task 5: Introduce prepare/persist/finalize tick coordination without weakening `WorldEngine` authority.
  - Deliverable: Refactor the engine's internal resolution path into private candidate preparation and infallible finalization while preserving the existing in-memory `resolve_tick()` behavior. Add `PersistentSimulationService` (or equivalent public application service) that verifies the expected durable cursor, prepares a detached candidate and tick commit, awaits one repository transaction, and only then publishes the candidate. Ensure empty/event-only ticks persist, adapter failure leaves the entire engine snapshot unchanged, ambiguous commit outcomes fence/reload instead of blind retry, and no public prepared-candidate mutation capability escapes.
  - Files: `src/simulation/engine.py`, `src/simulation/service.py`, `src/simulation/lifecycle.py`, `src/simulation/persistence.py`, `src/simulation/__init__.py`, `tests/unit/test_world_engine.py`, `tests/unit/test_persistent_simulation_service.py`.
  - Logging: Emit DEBUG prepare, cursor, append attempt, and finalize diagnostics; one INFO durable commit with safe counts/cursors; WARN idempotent retry or fenced instance; and ERROR preparation/storage/finalization failure codes. Do not log commands, event payloads, snapshots, configurations, seeds, or private state.
  - Dependencies: Depends on tasks 2-4.

- [x] Task 6: Establish the dedicated `persistence` adapter package and enforce dependency rules.
  - Deliverable: Add a side-effect-free top-level adapter package whose public facade exposes SQLAlchemy repository factories/implementations. Permit it to import only public `simulation` contracts and generic `infrastructure`; forbid domain/private simulation imports and reverse dependencies. Register the package for building, coverage, import-linter, AST checks, and facade tests, and update the ORM-stack rule so only `infrastructure` and `persistence` may import SQLAlchemy/Alembic/asyncpg.
  - Files: `src/persistence/__init__.py`, `src/persistence/errors.py`, `pyproject.toml`, `tests/architecture/boundary_checker.py`, `tests/architecture/test_boundary_checker.py`, `tests/architecture/test_import_boundaries.py`, `tests/unit/test_packaging.py`.
  - Logging: Package imports, ORM declarations, and error construction remain silent. Adapter implementations use `infrastructure.logging` and stable operation/error names; never connect, migrate, or configure logging at import time.
  - Dependencies: Depends on task 2 for the public ports. Can proceed in parallel with tasks 3-5 after that contract is stable.

- [x] Task 7: Create the relational schema, append-only database guards, constraints, and query indexes.
  - Deliverable: Add SQLAlchemy 2 mappings and Alembic revision `0002` for immutable `experiments`, `experiment_runs`, `simulation_runs` (seed/config/bootstrap/version metadata), `tick_commits`, `world_events`, `world_snapshots`, and normalized snapshot locations, agents/bodies, items, resources, and weather. Use composite foreign keys to prevent cross-run/snapshot references; exact constraints for non-negative ticks/revisions, `resulting_tick = tick + 1`, revision delta 0..1, one item placement, finite resource values, and fixed hash lengths; unique event IDs and `(run_id, tick, sequence)` ordering; indexes for run/tick/revision, actor, target, event type, entity placement, latest snapshot, and experiment/run queries. Add `ON DELETE RESTRICT` and trigger guards rejecting `UPDATE`, `DELETE`, and `TRUNCATE` on authoritative tables, with documented runtime grants that exclude mutation privileges.
  - Files: `src/persistence/orm.py`, `src/infrastructure/orm.py`, `alembic/env.py`, `alembic/versions/0002_simulation_event_store.py`, `tests/integration/test_migrations.py`, `tests/integration/test_append_only.py`.
  - Logging: ORM models and migrations do not log row contents. Migration/adapter logs may include revision, table/constraint name, run ID, tick, and stable database error class at DEBUG/INFO/ERROR; redact DSNs and never log JSON/byte payloads or seeds.
  - Dependencies: Depends on tasks 2, 3, and 6 so persisted columns, versions, and hash constraints match the canonical codec contract.

- [x] Task 8: Implement atomic SQLAlchemy repositories, idempotency, and concurrent-writer protection.
  - Deliverable: Implement run, tick/event, snapshot, and experiment repositories against async SQLAlchemy. Create a run in one transaction containing its manifest, arbitrary non-negative seed/configuration, bootstrap checkpoint (`next_tick = 0`, initial revision, no predecessor hash), normalized checkpoint projections, and optional experiment assignment. For each later tick, acquire a deterministic per-run PostgreSQL advisory transaction lock, validate predecessor tick/revision/commit hash, insert the tick row and all ordered events plus optional snapshot/projections, and commit once. Detect identical retries by idempotency key and full hash; reject divergent duplicates, gaps, stale writers, and event-ID collisions without `ON CONFLICT DO NOTHING`. Provide ordered paginated reads and latest-valid-snapshot lookup, preserve detached return values after session close, and never issue history updates/deletes.
  - Files: `src/persistence/sqlalchemy.py`, `src/persistence/readers.py`, `src/persistence/errors.py`, `src/persistence/__init__.py`, `src/infrastructure/database.py` only if a generic transaction helper is justified, `tests/unit/test_sqlalchemy_repository.py`, `tests/integration/test_tick_journal.py`, `tests/integration/test_tick_concurrency.py`.
  - Logging: DEBUG transaction start/lock/cursor/counts/idempotency decisions, INFO run creation and durable tick/snapshot commits, WARN identical retry/stale writer, and ERROR conflict/rollback/corruption codes. Never log SQL parameters, DSNs, canonical blobs, JSON payloads, snapshots, configuration values, or seeds.
  - Dependencies: Depends on tasks 3, 5, 6, and 7.

### Phase 3: Replay API, End-to-End Proof, and Documentation

- [ ] Task 9: Implement the public replay/recovery service and composition API.
  - Deliverable: Add an async `ReplayService` that loads a run, chooses the latest verified snapshot at or before an optional target tick, validates run/config/event/projector/derivation versions and hash-chain continuity, folds subsequent events in canonical order, accounts for eventless tick commits, and verifies every resulting revision and checkpoint hash. Recovery at the durable head returns a continuation-ready engine; bounded historical replay returns a detached read-only result and must reject append attempts against the existing run. Support bootstrap-only full replay, snapshot-at-head restore, fallback to an older valid snapshot only under an explicit policy, and fail closed on gaps, corruption, mixed identities, or unsupported versions. Expose repository/service construction at the API composition boundary for later experimental-framework use without adding HTTP routes.
  - Files: `src/simulation/replay.py`, `src/simulation/service.py`, `src/simulation/__init__.py`, `src/api/app.py`, `src/api/dependencies.py`, `src/persistence/__init__.py`, `tests/unit/test_replay_service.py`, `tests/unit/test_api_composition.py`.
  - Logging: DEBUG selected checkpoint and validated event ranges, INFO replay start/completion with run/target/counts/version, WARN explicit older-checkpoint fallback, and ERROR stable gap/hash/version/projector mismatch codes. Never log objective payloads, state, configuration, seed, memory, or LLM data.
  - Dependencies: Depends on tasks 4, 5, and 8.

- [ ] Task 10: Prove event projection, transactional coordination, and replay validation in unit tests.
  - Deliverable: Add fixed and Hypothesis tests for canonical event ordering, all currently emitted event variants, effect-complete take/drop/give projection, event-only and empty ticks, revision rules, duplicate/gap/mixed-run/mixed-world/version/hash failures, snapshot ordering and detachment, engine unchanged on repository failure, idempotent durable retry, and continuation after restoration. Reuse/extract deterministic state fingerprints and trace builders rather than duplicating private-state comparisons.
  - Files: `tests/unit/determinism_helpers.py`, `tests/simulation_helpers.py`, `tests/unit/test_event_projection.py`, `tests/unit/test_persistence_serialization.py`, `tests/unit/test_persistent_simulation_service.py`, `tests/unit/test_replay_service.py`, `tests/unit/test_simulation_replay_determinism.py`, `tests/unit/test_reproducibility_contracts.py`.
  - Logging: Capture logs to assert verbose DEBUG flow, one INFO per durable commit/replay completion, WARN retry/fallback paths, ERROR abort/corruption paths, environment-driven level control, and absence of event payloads, state, text, seeds, configuration, DSNs, credentials, memories, and embeddings.
  - Dependencies: Depends on tasks 1-5 and 9.

- [ ] Task 11: Prove PostgreSQL persistence, append-only enforcement, concurrency, and snapshot-plus-event reconstruction end to end.
  - Deliverable: Extend disposable-database fixtures with deterministic per-test isolation, then run a real simulation that creates a run, persists several mutating/event-only/empty/conflicting ticks, writes a middle checkpoint, appends later ticks, reconstructs from checkpoint plus subsequent events, and compares objective state/tick/revision/event identity against both the uninterrupted engine and a bootstrap full replay. Cover atomic rollback on partial insert failure, immutable trigger enforcement, ordered reads independent of insertion/query plan, identical/divergent retries, two-session same-tick races, stale predecessor rejection, snapshot/append races, restart-and-continue, migration upgrade/head checks, and entity/experiment query indexes.
  - Files: `tests/integration/conftest.py`, `tests/integration/test_database.py`, `tests/integration/test_migrations.py`, `tests/integration/test_tick_journal.py`, `tests/integration/test_append_only.py`, `tests/integration/test_tick_concurrency.py`, `tests/integration/test_simulation_persistence_replay.py`.
  - Logging: Assert transaction logs expose only safe run/tick/count/error metadata, failures roll back with one ERROR diagnostic, concurrent losers emit deterministic WARN/conflict codes, and no DSN, SQL parameter, event payload, snapshot, seed, or experiment metadata value appears.
  - Dependencies: Depends on tasks 7-10.

- [ ] Task 12: Document the persistence/replay contract and complete all quality gates.
  - Deliverable: Complete the mandatory `$aif-docs` checkpoint. Document package boundaries, objective-versus-subjective history, event/version evolution, append-only database guarantees and role assumptions, table/query model, durable tick transaction and crash windows, checkpoint cursor semantics, restore/full-audit algorithms, idempotency/concurrency behavior, integration-test setup, and the recorded-response requirement for cognition replay. Update project context and roadmap wording without claiming analysis metrics are complete, then run formatting, typing, architecture, unit, and opt-in PostgreSQL integration checks.
  - Files: `README.md`, `docs/architecture.md`, `docs/development.md`, `docs/persistence.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/ROADMAP.md` through `$aif-roadmap` if milestone status changes, `pyproject.toml`.
  - Logging: Documentation must list safe structured event names/fields, `PALIMPSEST_LOG_LEVEL` control, and prohibited sensitive/domain payloads. Verification confirms production log levels can be reduced without code changes and logging never participates in deterministic ordering.
  - Dependencies: Depends on tasks 1-11.

## Verification Commands

```bash
uv sync --frozen --python 3.12.14
uv run --frozen --python 3.12.14 ruff check src tests
uv run --frozen --python 3.12.14 mypy src tests
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term-missing
uv run --frozen --python 3.12.14 lint-imports --config pyproject.toml --no-cache --no-logo
PALIMPSEST_TEST_DATABASE_URL=<disposable-palimpsest_test-dsn> uv run --frozen --python 3.12.14 pytest -m integration tests/integration
```

## Acceptance Criteria

- Every newly persisted `WorldEvent` is immutable, replay-capable, uniquely identified, correlated to one run/world/tick/request, explicitly typed, actor/target-aware where applicable, and canonically ordered by contiguous intra-tick sequence.
- Mutating event payloads contain committed effects sufficient to reconstruct objective state without running current command rules; under-specified legacy audit events cannot enter authoritative replay silently.
- Past events, run configuration, tick commits, snapshots, and experiment/run assignments cannot be updated, deleted, or truncated through the runtime repository or ordinary runtime database role; subjective memory discrepancies never alter objective history.
- A complete tick, including eventless ticks, is persisted in one PostgreSQL transaction with predecessor validation, idempotency, deterministic ordering, and all-or-nothing event/snapshot projections.
- Storage failure before commit leaves the live engine unchanged. Recovery after a database commit/process crash reconstructs the committed prefix rather than duplicating or skipping a tick.
- PostgreSQL stores simulation runs, arbitrary non-negative seeds/configuration, objective events, immutable snapshots, agents, locations, items/resources, weather, and experiment metadata with foreign keys, checks, uniqueness, and indexes appropriate to run/tick/revision/entity queries.
- Domain and simulation modules do not import SQLAlchemy or the concrete adapter. The `persistence` package depends only on public simulation contracts and generic infrastructure, and architecture checks prevent reverse/private dependencies.
- `ReplayService` can restore from bootstrap or a selected checkpoint plus subsequent events, target a committed historical tick, validate all identities/versions/hashes/gaps/revisions, return a continuation-ready engine only at the durable head, return read-only results for earlier targets, and fail closed on corruption.
- A PostgreSQL integration test proves that an uninterrupted simulation, bootstrap full replay, and checkpoint-plus-events replay produce equal canonical objective world state, tick, revision, and objective event identity/order.
- Concurrent writers cannot create divergent successors. Identical retries are idempotent; divergent reuse of a tick or key is a deterministic conflict and never overwrites history.
- Existing deterministic ID/RNG guarantees, private world authority, schema-v1 audit compatibility policy, secret-safe structured logging, and disposable-test-database safeguards remain enforced.
- Ruff, mypy, unit/property tests, architecture/import-linter checks, migration tests, and opt-in PostgreSQL integration tests pass.
