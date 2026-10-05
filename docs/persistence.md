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

Canonical taxonomy (write version, accepted restore set, bump trigger, owner,
V1 fixture impact) lives in `simulation.compatibility.COMPATIBILITY_MATRIX`.
Contributor summary:

| Constant | Role |
| --- | --- |
| Event schema audit v1 | Decode/export only; not authoritative replay |
| Event schema replay v2 | Legacy projector (inventory transfers) |
| Event schema replay v3 | Physical runs; effect-complete + causes (readable; no fabricated occurrence context) |
| Event schema replay v4 | Causes + occurrence context for perception audiences |
| Event schema replay v5 | Default write when lifecycle/artifacts/dynamics/production channels are off |
| Event schema replay v6–v8 | Production / dynamics / artifacts write pairs (see priority below) |
| Event schema replay v9 | Lifecycle channel write (`AgentCreated`, `AgentEnteredWorld`, `LifecycleStageChanged`); accepts lower-channel detail kinds |
| Event schema replay v10 | New-agent provenance write (`AgentInitializationRecorded` after `AgentCreated`, before `AgentEnteredWorld`); accepts lower-channel kinds |
| `PROJECTOR_VERSION` | Private world projector compatibility (`v2` write; accept `v1`/`v2`) |
| `PERSISTENCE_CODEC_VERSION` | Canonical JSON codec for manifests/snapshots/commits (`v2` default write; accept `v1`…`v7`) |
| Persistence codec v6 | Pairs with event schema 9 when lifecycle channel is active without new-agent provenance; restores `lifecycle_records` |
| Persistence codec v7 | Pairs with event schema 10 when `new_agent_provenance_active`; restores `lifecycle_records` |
| Derivation v1 / v2 / v3 | Deterministic ID/stream derivation (v2 includes rules fingerprint) |
| Subjective codec v1 | Semantic beliefs, relationship profiles, mutation receipts (non-authoritative) |
| Runner config | Write `runner-config-v4` when all V3 flags are off; accept `v1`…`v25` decode; `v24` = v23 ∪ `population_lifecycle`; `v25` = v24 ∪ exact `new_agent_initialization` (synthesized default on v24 decode for lifecycle restore) |
| Alembic head | Pin **`0017`** — hybrid memory retrieve shortlist readiness (HNSW deferred: untyped `vector` column); prior `0016` event filter indexes and `0015` branch lineage remain; V2/V3 capability flags, lifecycle, and new-agent init stay runner JSON / event+snapshot payloads (no `0018` in v3-03) |

**Checkpoint write-pair priority:** `new_agent_provenance_active` → `(replay-v10, codec v7)`; else lifecycle on → `(replay-v9, codec v6)`; else artifacts → `(v8, v5)`; else dynamics → `(v7, v4)`; else production → `(v6, v3)`; else → `(replay-v5, v2)`.

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

## Cognition execution trace (`0013`)

- **`0013_v2_cognition_trace`:** append-only `cognition_trace_invocations` outside `AUTHORITATIVE_TABLES` / `EvidenceManifest` / objective high-water. Indexed for inspection: `(run_id, tick)` and `(run_id, agent_id, tick)`. Payload is `cognition-trace-v1` codec bytes + content hash; FK to `simulation_runs` RESTRICT.
- Factory: `persistence.create_cognition_trace_repository(...)`. Composition injects SQLAlchemy only when tracing is enabled + durable; otherwise Null / in-memory.
- Optional default-off soft stop-append caps (`PALIMPSEST_COGNITION_TRACE_SOFT_CAP_INVOCATIONS` / `..._BYTES`) fail-soft with `soft_cap_reached` and never `DELETE` prior rows. Read-only `export_cognition_trace_invocations` copies pages for offline archival only.
- Not folded into objective replay; stream-outbox / manifest integration is deferred. HTTP read routes are deferred — use `CognitionTraceRepository` ports.

## Research branch lineage (`0015`)

- **`0015_simulation_branches`:** control-plane genealogy (`parent_run_id`, `child_run_id`, `fork_tick`, intervention fingerprint/canonical, `branch_id`) **outside** `AUTHORITATIVE_TABLES`. Forking rematerializes a child journal under a new `run_id` and never rewrites parent history. Default seed stream **inherits** parent `stochastic_identity` unless intervention kind `alternate_seed_stream` is selected.
- Factory: `persistence.create_branch_lineage_repository(...)`. Observer manifests stay on `observer-protocol-v1` with required `run_id` plus optional fork fields.

## Long-run snapshot cadence and indexes (`0016` / `0017`)

- **Write-time sparseness only.** `world_snapshots` and snapshot projection tables are authoritative and **DELETE-rejected**. Bound snapshot storage by enabling `RunnerCheckpointPolicy` with a positive `cadence_ticks` (helpers: `long_run_checkpoint_policy` / `long_run_persistence_spec` for 100 / 500 / 1000). Do **not** implement in-DB snapshot GC. Optional offline **export copies** of snapshot payloads are allowed; copies never authorize deleting live append-only rows.
- Short-run default remains checkpoints **off** (bootstrap snapshot only). Seek uses `ix_world_snapshots_run_next_tick` via nearest verified snapshot at-or-before the target, then folds events.
- **`0016_long_run_event_indexes`:** additive indexes `ix_world_events_run_event_type`, `ix_world_events_run_actor_id`, `ix_world_events_run_target_id` for run-scoped observer filters. PK `(run_id, tick, sequence)` continues to serve keyset pages. No authoritative column semantics change; append-only triggers unchanged.
- **`0017_memory_embedding_hnsw`:** documents hybrid retrieve readiness. HNSW/IVFFlat are **not** created yet because `memory_traces.embedding` is untyped `vector` (fixed `vector(N)` required for ANN indexes). Runtime still shortlists via SQL cosine distance + `LIMIT` when `query_embedding` is set, then `rank_traces`. `PALIMPSEST_MEMORY_RETRIEVE_MAX_CANDIDATES` (default 4096) caps SQL materialization before ranking.

Migration head is `0017`. V2/V3 capability flags are **not** Alembic columns — they are carried only inside canonical runner-config JSON stored in existing `run_control.config_payload` (`0011`). V3 scaffolding does **not** add `0018`; do not invent indexed V3 flag columns without a later justified plan. Tests may target only databases whose name contains `palimpsest_test`; Alembic receives the validated URL directly and fails closed on conflicting ambient URLs.

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
