# Persistence and Deterministic Replay

[← Development](development.md) · [Back to README](../README.md)

## Boundaries

- `simulation` owns immutable DTOs, repository **ports**, journal codecs, `PersistentSimulationService`, and `ReplayService`.
- `persistence` implements simulation repository ports, the owner-scoped `MemoryService`, and the durable `SubjectiveStateService` with async SQLAlchemy. It may import public `simulation` contracts, public `memory` and `social` facades, and generic `infrastructure`.
- Domain packages and `simulation` never import SQLAlchemy. `infrastructure` stays domain-neutral.
- Memory and subjective adapters must not import `world.events`, private world authority, event ORM classes, or replay readers.
- `analysis` may read subjective memory evidence and objective events independently for drift metrics; that join is never available to memory/cognition/runtime APIs.

## Objective history

Authoritative history is the ordered stream of replay-capable `WorldEvent` records plus per-tick commit rows (including eventless ticks). Payloads store committed effects, not instructions to re-run current rules. Subjective episodic memory, reconstruction provenance, semantic beliefs, directed relationships, and transmission provenance live in separate tables (Alembic `0005`/`0006`/`0007`/`0008`) and are never joined into objective replay. LLM transcripts remain outside both streams; cognition replay still needs recorded provider responses or stubs.

## Episodic memory (subjective)

- `MemoryTrace` is a fragmentary structured record (concepts, entity mentions, relations, context, salience, confidence, provenance). It is not a chat transcript and does not require a sentence.
- Normal services bind `MemoryScope(run_id, owner_id)` via `persistence.create_memory_service(...)`. There is no unscoped admin API.
- Structured filters reduce candidates before optional pgvector cosine scoring. Retrieval works without embeddings.
- Scoring uses a versioned `MemoryScoringPolicy` with quantized scores and tie-break `score DESC, created_tick DESC, memory_id ASC` shared by Python and SQL adapters.
- Decay/forgetting use explicit simulation ticks only (no wall clocks). Soft-forget excludes traces from retrieval; V1 does not hard-delete.
- Reconstructive recall (`MemoryService.recall`) returns `ReconstructedMemory`; optional reconsolidation appends provenance without mutating source content. See [Memory reconstruction](memory-reconstruction.md).
- Domain serialization uses type `episodic_memory_trace` (`trace_version=1`) plus reconstruction/lineage codecs. Legacy `memory_trace` / arbitrary `content` payloads are rejected.
- Safe log fields: operation, run/owner/reconstruction IDs, tick, policy version, enabled components, candidate/result/update/reconsolidation counts, stable reason codes. Never log fragments, narratives, query text, vectors, communications, or SQL parameters.

## Reconstruction provenance (`0006`)

| Table | Role | Mutability |
| --- | --- | --- |
| `memory_reconstructions` | Reconstruction records (policy/prompt metadata + payload hash) | Append-only trigger |
| `memory_reconstruction_sources` | Ordered source edges per reconstruction | Append-only trigger |
| `memory_derivation_sources` | Derived trace → parents + producing reconstruction (incl. `supersedes_memory_id` backfill) | Append-only trigger |
| Fragment tables | Concept/entity/relation rows | Append-only trigger |
| `memory_traces` | Trace content vs access/forget metadata | **Selective** content immutability; access/forgetting still mutable |

All of the above are listed in `SUBJECTIVE_MEMORY_TABLES` and are **outside** `AUTHORITATIVE_TABLES` / objective replay. No objective-event foreign key. Atomic `MemoryMutationBatch` applies reconstruction + edges + optional derived trace + access receipts in one transaction (in-memory and PostgreSQL).

## Subjective agent models (`0007`)

| Table | Role | Mutability |
| --- | --- | --- |
| `semantic_beliefs` | Owner-scoped canonical claims + activation state | Mutable header; content keyed by revisions |
| `semantic_belief_revisions` | Append-only revision history (confidence, policy, tick) | Append-only trigger |
| `semantic_belief_evidence` | Support/contradiction rows referencing `memory_traces` | Append-only trigger |
| `directed_relationships` | Independent `source_id → target_id` profiles | Mutable header |
| `relationship_revisions` | Append-only per-profile revision history | Append-only trigger |
| `relationship_dimension_evidence` | Per-dimension evidence with opaque memory refs | Append-only trigger |
| `subjective_operations` | Idempotent owner-scoped batch receipts | Insert for new ops; conflict on reuse |

All of the above are listed in `SUBJECTIVE_AGENT_TABLES` and are **outside** `AUTHORITATIVE_TABLES`. Belief evidence FKs target `memory_traces`, never `world_events`. `Alice → Bob` and `Bob → Alice` persist independently. Durable commits go through `persistence.create_subjective_state_service(...)` (one transaction with episodic mutations). Subjective-v1 codecs live under `simulation` and remain separate from schema-v1 legacy `belief` / `relationship` decoding.

Relationship dimensions are only: trust, fear, affection, debt, respect, resentment, familiarity, dependency. No friend/enemy/leader/group/morality/culture labels are stored.

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
| Subjective codec v1 | Semantic beliefs, relationship profiles, mutation receipts (non-authoritative) |

Runs never mix replay schema versions. Legacy schema-v1 audit events remain decodable for export but must not enter the authoritative log. Alembic revision `0004` persists SQL cause/occurrence columns so restored engines reproduce the same next observation as live engines (eventful and eventless prior windows). Revision `0005` adds owner-scoped episodic memory tables. Revision `0006` adds reconstruction/derivation provenance with selective immutability. Revision `0007` adds semantic belief and directed relationship tables. Revision `0008` adds communicated transmission metadata and testimony-factor columns. Observation codecs round-trip every field and provenance type with exact keys.

## Append-only store

Alembic revision `0002` creates experiments, experiment_runs, simulation_runs, tick_commits, world_events, world_snapshots, and normalized snapshot projection tables. Revision `0003_physical_simulation_state` adds physical-rules columns on runs and normalized topology/capacity/kind/load/regen fields on snapshot projections (weather is condition-only). Triggers reject `UPDATE`/`DELETE`/`TRUNCATE` on authoritative tables. Runtime roles should omit mutation privileges beyond `INSERT`/`SELECT`. Subjective reconstruction tables use their own append-only / selective triggers and are not part of that authoritative set.

## Durable tick window

1. Prepare a detached candidate on `WorldEngine` (live state unchanged).
2. Append tick commit + events (+ optional snapshot) in one PostgreSQL transaction with advisory lock, predecessor checks, idempotency key, and commit-hash chain.
3. Finalize by swapping the in-memory snapshot only after commit success.

Adapter failure before commit leaves the engine unchanged. Crash after commit is recovered by replaying persisted history. Subjective reconsolidation commits are separate memory-service transactions and cannot alter objective hashes.

## Replay

`ReplayService` loads a run, selects a verified checkpoint at or before the target tick, validates versions and commit continuity, folds subsequent events, and accounts for eventless ticks via `committed_through_tick`. Recovery at the durable head is `CONTINUATION` (may `open_durable`); earlier targets are `READONLY`. Subjective reconstructions do not participate in objective replay folding. Exact LLM reconstructive recall still requires recorded responses or deterministic stubs.

## Experiment records (`0010`)

Append-only `experiment_definitions`, `experiment_assignments`, and `experiment_results` store versioned fingerprints and one immutable final result per assigned run. Adapter: `persistence.create_experiment_record_repository(...)`. These tables use the same `reject_history_mutation` update/delete/truncate triggers as authoritative history but are experiment-framework records (not folded into objective world replay). See [Experiments](experiments.md).

## Run control and scientific evidence (`0011` / `0012`)

- **`0011_v1_run_control`:** canonical runner configuration V2, lifecycle transitions, execution leases/heartbeats, experiment assignment reconciliation.
- **`0012_v1_scientific_evidence`:** append-only goal revisions, action resolutions, claim-level truth specs, evidence manifests, metric-set lifecycle + immutable metric documents, unified stream/outbox with one monotonic per-run cursor.

Migration head is `0012`. Tests may target only databases whose name contains `palimpsest_test`; Alembic receives the validated URL directly and fails closed on conflicting ambient URLs.

## Logging

Safe fields: run ID, tick/revision, record counts, version strings, hash prefixes, stable error codes, perception reason codes, reconstruction IDs, policy versions, reconsolidation counts, belief/relationship operation IDs and dimension-change counts. Never log seeds, full configs, event payloads, observation bodies, communication text, snapshot bodies, DSNs, SQL parameters, memories, belief claims/values, relationship assessments, reconstructions/narratives, embeddings, or random draws. Control verbosity with `PALIMPSEST_LOG_LEVEL`.

## Integration tests

Set `PALIMPSEST_TEST_DATABASE_URL` to a disposable database, then:

```bash
uv run --frozen --python 3.12.14 pytest -m integration tests/integration
```

## See also

- [Memory reconstruction](memory-reconstruction.md)
- [Physical simulation](physical-simulation.md)
- [Simulation runner](simulation-runner.md)
- [Experiments](experiments.md)
- [Architecture](architecture.md)
- [Development](development.md)
