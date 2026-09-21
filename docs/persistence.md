# Persistence and Deterministic Replay

[← Development](development.md) · [Back to README](../README.md)

## Boundaries

- `simulation` owns immutable DTOs, repository **ports**, journal codecs, `PersistentSimulationService`, and `ReplayService`.
- `persistence` implements simulation repository ports and the owner-scoped `MemoryService` with async SQLAlchemy. It may import public `simulation` contracts, public `memory` contracts, and generic `infrastructure`.
- Domain packages and `simulation` never import SQLAlchemy. `infrastructure` stays domain-neutral.
- Memory adapters must not import `world.events`, private world authority, event ORM classes, or replay readers.

## Objective history

Authoritative history is the ordered stream of replay-capable `WorldEvent` records plus per-tick commit rows (including eventless ticks). Payloads store committed effects, not instructions to re-run current rules. Subjective episodic memory is stored in separate mutable tables (Alembic `0005`) and is never joined into objective replay. LLM transcripts remain outside both streams; cognition replay still needs recorded provider responses or stubs.

## Episodic memory (subjective)

- `MemoryTrace` is a fragmentary structured record (concepts, entity mentions, relations, context, salience, confidence, provenance). It is not a chat transcript and does not require a sentence.
- Normal services bind `MemoryScope(run_id, owner_id)` via `persistence.create_memory_service(...)`. There is no unscoped admin API.
- Structured filters reduce candidates before optional pgvector cosine scoring. Retrieval works without embeddings.
- Scoring uses a versioned `MemoryScoringPolicy` with quantized scores and tie-break `score DESC, created_tick DESC, memory_id ASC` shared by Python and SQL adapters.
- Decay/forgetting use explicit simulation ticks only (no wall clocks). Soft-forget excludes traces from retrieval; V1 does not hard-delete.
- Domain serialization uses type `episodic_memory_trace` (`trace_version=1`). Legacy `memory_trace` / arbitrary `content` payloads are rejected.
- Safe log fields: operation, run/owner IDs, tick, policy version, enabled components, candidate/result/update counts, stable reason codes. Never log fragments, query text, vectors, communications, or SQL parameters.

## Versions

| Constant | Role |
| --- | --- |
| Event schema audit v1 | Decode/export only; not authoritative replay |
| Event schema replay v2 | Legacy projector (inventory transfers) |
| Event schema replay v3 | Physical runs; effect-complete + causes (readable; no fabricated occurrence context) |
| Event schema replay v4 | Physical runs (new writes); causes + occurrence context for perception audiences |
| `PROJECTOR_VERSION` | Private world projector compatibility |
| `PERSISTENCE_CODEC_VERSION` | Canonical JSON codec for manifests/snapshots/commits |
| Derivation v1 / v2 | Deterministic ID/stream derivation (v2 includes rules fingerprint) |

Runs never mix replay schema versions. Legacy schema-v1 audit events remain decodable for export but must not enter the authoritative log. Alembic revision `0004` persists SQL cause/occurrence columns so restored engines reproduce the same next observation as live engines (eventful and eventless prior windows). Revision `0005` adds owner-scoped episodic memory tables (mutable; not append-only). Observation codecs round-trip every field and provenance type with exact keys.

## Append-only store

Alembic revision `0002` creates experiments, experiment_runs, simulation_runs, tick_commits, world_events, world_snapshots, and normalized snapshot projection tables. Revision `0003_physical_simulation_state` adds physical-rules columns on runs and normalized topology/capacity/kind/load/regen fields on snapshot projections (weather is condition-only). Triggers reject `UPDATE`/`DELETE`/`TRUNCATE` on authoritative tables. Runtime roles should omit mutation privileges beyond `INSERT`/`SELECT`.

## Durable tick window

1. Prepare a detached candidate on `WorldEngine` (live state unchanged).
2. Append tick commit + events (+ optional snapshot) in one PostgreSQL transaction with advisory lock, predecessor checks, idempotency key, and commit-hash chain.
3. Finalize by swapping the in-memory snapshot only after commit success.

Adapter failure before commit leaves the engine unchanged. Crash after commit is recovered by replaying persisted history.

## Replay

`ReplayService` loads a run, selects a verified checkpoint at or before the target tick, validates versions and commit continuity, folds subsequent events, and accounts for eventless ticks via `committed_through_tick`. Recovery at the durable head is `CONTINUATION` (may `open_durable`); earlier targets are `READONLY`.

## Logging

Safe fields: run ID, tick/revision, record counts, version strings, hash prefixes, stable error codes, perception reason codes. Never log seeds, full configs, event payloads, observation bodies, communication text, snapshot bodies, DSNs, SQL parameters, memories, embeddings, or random draws. Control verbosity with `PALIMPSEST_LOG_LEVEL`.

## Integration tests

Set `PALIMPSEST_TEST_DATABASE_URL` to a disposable database, then:

```bash
uv run --frozen --python 3.12.14 pytest -m integration tests/integration
```

## See also

- [Physical simulation](physical-simulation.md)
- [Architecture](architecture.md)
- [Development](development.md)
