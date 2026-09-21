# Implementation Plan: V1 Episodic Memory Traces

Branch: main (branch creation disabled by project config)
Created: 2026-09-21

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M3 — Cognition and Providers"
Rationale: Owner-scoped episodic retrieval is a required cognition capability and connects agent-specific observations to later reconstruction and reconsolidation policies.

## Goal

Implement V1 episodic memory as immutable, fragmentary experience traces rather than chat transcripts or required natural-language sentences. A `MemoryTrace` records structured concepts, perceived entities, relations, temporal and situational context, emotional salience, confidence, provenance, creation/access history, and whether information was directly observed or communicated.

Provide an owner-bound asynchronous `MemoryService` that stores, retrieves, records access, and forgets traces without exposing another agent's memory or the objective event journal. PostgreSQL remains the durable store; normalized relational fields remain queryable and authoritative for filtering, while an optional pgvector embedding augments ranking when semantic retrieval is available.

## Design Decisions

- Replace the arbitrary `MemoryTrace.content` mapping with explicit frozen, slotted values for concept mentions, entity mentions, relations, provenance, context, and lifecycle metadata. Ordered tuples and stable trace-local mention IDs make serialization, relation endpoints, and ranking deterministic; no complete sentence or narrative summary is required.
- Treat every trace as an agent's subjective record. Grounded `EntityId` or source-event correlation may identify what was perceived, but neither implies truth and neither permits dereferencing objective state. Communicated claims retain sender/communication provenance and remain distinguishable from direct observation.
- Scope durable memory by both simulation run and owner. Construct normal runtime services with a fixed `MemoryScope(run_id, owner_id)` and expose no unscoped `get`, `list`, or query method. Every database key, predicate, update, and relation includes the same scope; foreign and nonexistent memory IDs produce indistinguishable not-found behavior.
- Define the framework-free `MemoryService`, query, result, score-policy, access receipt, and forgetting contracts in `memory`. Permit `persistence` to implement public `memory` contracts while preserving the reverse dependency ban and all ORM/framework bans in `memory`, cognition, and simulation domain code.
- Keep structured selection first-class: owner/run, active state, creation/source tick range, location/context, provenance kind, direct-versus-communicated source, concept/entity/relation predicates, and confidence/salience thresholds reduce the candidate set before optional vector similarity is calculated. Relations are normalized records, not opaque text or embedding-only facts.
- Store an optional fixed-dimension embedding plus embedding model/version metadata on a trace. Embedding generation is an injected port and is not implemented by querying the existing completion-only `LLMProvider`; retrieval without an embedding remains fully functional. V1 uses exact pgvector cosine scoring within the structured candidate set and adds no approximate index until workload evidence justifies it.
- Make retrieval scoring a versioned immutable policy with validated non-negative weights for semantic relevance, recency, emotional salience, current-context overlap, social relevance, and access history. Normalize active weights, quantize the final score at one documented boundary, and use `score DESC, created_tick DESC, memory_id ASC` as the total ordering in both Python and SQL.
- Pass current simulation tick and query context explicitly. Recency and decay never use wall-clock time, operational timestamps, database row order, Python `hash()`, global RNG, or hidden clocks. Context and social relevance arrive as owner-safe query signals rather than imports from `world` authority or the independent `social` package.
- Model forgetting as deterministic retention decay plus an explicit soft-forget transition. Retrieval excludes forgotten traces; a maintenance operation marks traces forgotten at a supplied tick when their versioned retention policy falls below threshold or expiry is reached. V1 does not hard-delete evidence or reconstruct forgotten traces from objective events.
- Keep `MemoryRetriever.retrieve()` observational. It returns ranked trace snapshots and idempotent pending access receipts; `AgentRuntime` applies accesses and new memory writes only after successful cognition through one validated `MemoryService.apply()` batch. This preserves failure semantics and prevents retries from inflating access counts.
- Make trace creation immutable and reject conflicting ID reuse. Access metadata and forgotten status are controlled lifecycle updates, not replacement of remembered content. Reserve explicit lineage fields such as `supersedes_memory_id` and generation for later reconsolidation without implementing reconstruction or reconsolidation policy in V1.
- Store memory in mutable subjective tables separate from append-only authoritative history. The memory adapter must not query, join, import, or deserialize `WorldEvent`/event ORM payloads to build or retrieve a trace; source IDs are opaque correlation metadata copied from the agent's redacted observation only.
- Keep all memory content, query text, relation values, communication text, and embeddings out of logs. Safe diagnostics are limited to operation name, run/owner IDs, tick, policy version, enabled score components, candidate/result/update counts, duration metadata, and stable reason/error codes.

## Non-Goals

- Reconstructing an agent's memory from `WorldEvent`, snapshots, replay data, or objective world state.
- Allowing agents, cognition stages, analysis code, or ordinary repositories to inspect another agent's memory.
- Implementing natural-language recollection, generative reconstruction, reconsolidation policy, belief revision, confabulation, or memory sharing.
- Treating communicated information as verified truth or automatically converting every observation into a durable memory.
- Adding an embedding network provider, vendor SDK, approximate vector index, separate vector database, HTTP memory API, or background worker.
- Hard-deleting forgotten evidence or changing authoritative event replay because subjective memory changed.

## Commit Plan
- **Commit 1** (after tasks 1-3): `feat(memory): define structured episodic memory contracts`
- **Commit 2** (after tasks 4-7): `feat(memory): add owner-scoped PostgreSQL retrieval`
- **Commit 3** (after tasks 8-10): `test(memory): prove deterministic retrieval and decay`

## Tasks

### Phase 1: Domain Contracts and Deterministic Policy

- [x] Task 1: Replace arbitrary memory payloads with a closed structured `MemoryTrace` model.
  - Deliverable: Define frozen values for trace-local concept and entity mentions, typed relation endpoints, temporal/location/current-context fields, emotional salience, confidence, direct-observation versus communicated provenance, optional opaque observed-source correlation, creation/source tick, last-access tick, access count, optional expiry/forgotten tick, and reserved reconsolidation lineage. Enforce exact runtime types, bounded finite scores, non-negative logical ticks, owner identity, unique ordered mention IDs, valid relation endpoints, deterministic tuple ordering, and defensive detachment. Remove the requirement or implication that a memory is a complete sentence; reject raw `WorldEvent`, replay, request, cause, hidden-observer, or arbitrary payload containers. Update the public facade and replace existing constructor call sites without retaining an untyped compatibility field.
  - Files: `src/memory/models.py`, `src/memory/__init__.py`, `src/agents/cognition/models.py`, `src/simulation/perception.py`, `tests/unit/test_v1_memory_social_models.py`, `tests/unit/test_subjective_state_contracts.py`, `tests/unit/test_cognition_models.py`, `tests/typecheck/v1_domain_contracts.py`.
  - Logging: Domain values and validation remain log-free. Exceptions expose stable field/reason codes only and never include concepts, entity labels, relations, location context, communicated text, or provenance payloads.
  - Dependencies: None. This schema anchors all service, persistence, cognition, and codec work.

- [x] Task 2: Define owner-bound service, query, retrieval, scoring, access, and forgetting contracts.
  - Deliverable: Add `MemoryScope`, structured filters, explicit current-context/social signals, optional query embedding, `MemoryScoringPolicy`, per-component score breakdown, ranked trace snapshot, pending access receipt, batch mutation, retention policy, and `MemoryService` async protocol. Require a service instance to bind one run and owner; expose create/apply, retrieve, snapshot/fetch, and forget operations that cannot override that scope. Validate weight normalization, fixed embedding dimension, finite vectors, limits, tick monotonicity, policy/version identifiers, quantization, and canonical tie-breaking. Ensure result metadata supports later reconstruction/reconsolidation by preserving the retrieved snapshot, rank, matched structural IDs, score-policy version, retrieval tick, and source lineage without implementing those later policies.
  - Files: `src/memory/models.py`, `src/memory/contracts.py`, `src/memory/__init__.py`, `tests/unit/test_v1_episodic_memory_models.py`, `tests/typecheck/episodic_memory_contracts.py`.
  - Logging: Protocols and values remain log-free. Define an explicit safe diagnostic allowlist of scope IDs, ticks, policy versions, component names, and counts; prohibit trace/query/vector values and full filter objects.
  - Dependencies: Depends on task 1 for the trace vocabulary.

- [x] Task 3: Implement the pure deterministic scoring, decay, and in-memory service reference behavior.
  - Deliverable: Implement structured candidate matching, exact optional cosine similarity, recency, emotional salience, current-context overlap, social relevance, access-history contribution, weight normalization, final quantization, and total ordering in pure `memory` code. Implement retention decay from explicit logical ticks and an owner-bound in-memory `MemoryService` with atomic prevalidation of writes/accesses/forget transitions, conflicting-ID rejection, idempotent access receipts, soft forgetting, deterministic snapshots, and no wall-clock or random dependencies. Define whether access history represents familiarity or novelty entirely through the scoring policy rather than hidden branching.
  - Files: `src/memory/scoring.py`, `src/memory/service.py`, `src/memory/models.py`, `src/memory/__init__.py`, `tests/unit/test_v1_memory_retrieval_scoring.py`, `tests/unit/test_v1_memory_decay.py`, `tests/unit/test_v1_episodic_memory_ownership.py`, `tests/unit/determinism_helpers.py`.
  - Logging: Pure scoring and decay remain log-free. The in-memory application boundary may emit DEBUG operation/policy/tick and candidate/result/update counts plus WARN/ERROR reason codes; it must never log trace content, query signals, relation values, communication text, or vectors.
  - Dependencies: Depends on tasks 1 and 2; supplies the executable contract used to verify SQL parity.

### Phase 2: Cognition and Durable PostgreSQL Storage

- [x] Task 4: Integrate owner-scoped retrieval and deferred access application into cognition runtime.
  - Deliverable: Add a production cognition `MemoryRetriever` adapter that derives only the current agent's structured query from `CognitiveLoopInput` and interpreted perception, calls its bound `MemoryService`, rejects any foreign-owner result, and maps ordered trace snapshots and rank metadata into an expanded `RetrievedMemoryContext`. Extend the loop receipt with pending access receipts, then make `AgentRuntime` apply those receipts and all memory update intents as one prevalidated idempotent service batch only after cognition succeeds. Validate newly encoded traces against observation owner, tick, and revision; preserve no-mutation behavior on failed cognition and prevent direct event-log, world-state, repository, or foreign-service access.
  - Files: `src/agents/cognition/models.py`, `src/agents/cognition/contracts.py`, `src/agents/cognition/defaults.py`, `src/agents/cognition/memory.py`, `src/agents/cognition/loop.py`, `src/agents/cognition/__init__.py`, `src/simulation/agent_runtime.py`, `src/simulation/__init__.py`, `tests/fakes/cognition.py`, `tests/fakes/memory.py`, `tests/unit/test_v1_episodic_memory_cognition.py`, `tests/unit/test_cognitive_loop.py`, `tests/unit/test_agent_runtime.py`, `tests/integration/test_agent_runtime_world_engine.py`.
  - Logging: Cognition adapters log DEBUG owner/tick, policy version, enabled-component names, and candidate/result counts only. Runtime logs DEBUG batch counts and idempotency outcome, WARN rejected scope/tick updates, and ERROR stable retrieval/application codes; no memory, observation, communication, query, score-detail, or embedding values are logged.
  - Dependencies: Depends on tasks 2 and 3.

- [x] Task 5: Establish the durable memory adapter boundary and dependency enforcement.
  - Deliverable: Allow `persistence` to implement and import only the public `memory` service contracts in addition to its existing public dependencies, while preserving `memory -> persistence/infrastructure/SQLAlchemy` and cognition/simulation ORM bans. Add a side-effect-free memory adapter factory that always requires `MemoryScope`, an async session factory, and explicit policy/configuration; expose no unscoped administrative repository through normal runtime composition. Add architecture rules forbidding memory adapter imports of `world.events`, private world authority, event ORM classes, replay readers, or objective event repositories.
  - Files: `src/persistence/__init__.py`, `src/persistence/errors.py`, `pyproject.toml`, `tests/architecture/boundary_checker.py`, `tests/architecture/test_boundary_checker.py`, `tests/architecture/test_import_boundaries.py`, `tests/architecture/test_memory_isolation.py`, `tests/unit/test_packaging.py`.
  - Logging: Package imports, factories, ORM declarations, and architecture checks remain silent. Adapter construction logs no DSN or policy values; runtime adapter logs use the safe metadata allowlist and stable operation/error names only.
  - Dependencies: Depends on task 2. Can proceed in parallel with task 4 after service contracts stabilize.

- [x] Task 6: Add normalized owner-scoped episodic memory schema and pgvector support.
  - Deliverable: Create Alembic revision `0005` and SQLAlchemy mappings for trace lifecycle/context/provenance, concepts, entity mentions, and relations, with `(run_id, owner_id, memory_id)` scope carried through primary/foreign keys. Store an optional fixed-dimension `Vector` plus embedding model/version on the trace. Add exact checks for ticks, access counts, finite bounded values, source-kind applicability, relation endpoint integrity, lineage, expiry/forgotten state, and embedding metadata; add structured B-tree/GIN indexes beginning with run/owner/active state and useful concept/entity/relation/context fields. Keep these mutable subjective tables out of `AUTHORITATIVE_TABLES` and append-only triggers. Repair the existing Alembic head/log/test mismatch so revision reporting and metadata parity identify the actual new head.
  - Files: `src/persistence/orm.py`, optionally `src/persistence/memory_orm.py`, `src/infrastructure/orm.py`, `alembic/env.py`, `alembic/versions/0005_owner_scoped_episodic_memory.py`, `tests/integration/test_migrations.py`, `tests/unit/test_sqlalchemy_repository.py`.
  - Logging: Mappings and migrations never log rows, vectors, JSON, SQL parameters, or relation/context values. Migration diagnostics may log revision, table/index/constraint name, and stable failure class at DEBUG/INFO/ERROR only.
  - Dependencies: Depends on tasks 1, 2, and 5 so columns and constraints implement the final public contract.

- [x] Task 7: Implement the asynchronous SQLAlchemy ``MemoryService`` with structured-first retrieval.
  - Deliverable: Implement scoped trace insertion, exact structured candidate queries, optional pgvector cosine scoring within the filtered set, Python/SQL score parity, deterministic ordering/pagination, snapshot/fetch, idempotent additive access updates, atomic batched writes/accesses, and owner-scoped soft forgetting. Every statement must predicate run and owner; retrieval must apply ownership and structured filters before limit/vector scoring, tolerate traces without embeddings, reject vector dimension/model mismatches, and never join objective event tables. Use one explicit transaction per mutation, concurrency-safe updates, rollback on any invalid batch member, and operation IDs so retries count each successful retrieval once.
  - Files: `src/persistence/memory_sqlalchemy.py`, optionally `src/persistence/readers.py`, `src/persistence/__init__.py`, `src/persistence/errors.py`, `src/infrastructure/database.py` only if a generic transaction helper is justified, `tests/unit/test_sqlalchemy_repository.py`, `tests/integration/test_episodic_memory_pgvector.py`, `tests/integration/test_memory_concurrency.py`.
  - Logging: Emit DEBUG scope/tick/policy, structured-filter count, semantic-enabled flag, candidate/result/update counts, transaction and idempotency decisions; INFO successful write/forget batch counts; WARN duplicate/stale operations; ERROR rollback/conflict codes. Never log trace/query content, source IDs beyond approved opaque IDs, vectors, SQL parameters, DSNs, or score inputs.
  - Dependencies: Depends on tasks 3, 5, and 6.

### Phase 3: Codecs, Proofs, and Documentation

- [ ] Task 8: Update strict memory serialization and deterministic fakes without inventing legacy meaning.
  - Deliverable: Replace the old arbitrary-content memory codec with exact codecs for every structured trace, query-independent lifecycle value, and lineage/provenance variant. Use a distinct episodic trace type/version so old arbitrary `memory_trace` payloads are not silently reinterpreted; because current memory is not durably persisted, reject unsupported legacy trace payloads rather than fabricating concepts or prose. Add canonical golden bytes, duplicate/unknown field rejection, finite-number checks, and round trips. Add a scripted fake embedder and logical tick source that use canonical keys, fixed dimensions, immutable vectors, no Python hashing, no network, and metadata-only call records.
  - Files: `src/simulation/serialization.py`, `tests/fakes/memory.py`, `tests/unit/test_v1_domain_serialization.py`, `tests/unit/test_fake_memory_components.py`, `tests/typecheck/episodic_memory_contracts.py`.
  - Logging: Codecs and deterministic fakes remain log-free on success and never retain content/vector values in `repr` or exceptions. Stable schema/type/path/error codes are the only permitted failure diagnostics.
  - Dependencies: Depends on tasks 1-3. Must be complete before final runtime and persistence parity proofs.

- [ ] Task 9: Prove storage, ranking, ownership, decay, and authority isolation deterministically.
  - Deliverable: Add fixed and Hypothesis tests for relation validation, defensive immutability, conflicting IDs, two owners with colliding IDs and adversarially higher foreign scores, same owner IDs across different runs, structured-filter-before-limit behavior, all six configurable score components, disabled components, known cosine vectors, score quantization/ties, insertion-order independence, explicit-tick recency/decay, half-life boundaries, expiry/soft forgetting, access-history updates, failed-cognition no-mutation, idempotent retries, atomic batches, and concurrency-safe access counts. Prove SQL and pure Python return identical ordered IDs/scores for a fixed corpus. Extend AST/import checks to prove no memory path can query objective event logs, import authority state, use wall clocks/global randomness, or expose another owner's scope; integration tests remain opt-in and use only disposable `palimpsest_test` databases.
  - Files: `tests/unit/test_v1_episodic_memory_models.py`, `tests/unit/test_v1_episodic_memory_ownership.py`, `tests/unit/test_v1_memory_retrieval_scoring.py`, `tests/unit/test_v1_memory_decay.py`, `tests/unit/test_v1_episodic_memory_cognition.py`, `tests/unit/test_agent_runtime.py`, `tests/integration/test_episodic_memory_pgvector.py`, `tests/integration/test_memory_concurrency.py`, `tests/architecture/test_memory_isolation.py`, `tests/architecture/test_cognitive_loop_isolation.py`, `tests/architecture/test_import_boundaries.py`.
  - Logging: Capture DEBUG/INFO/WARN/ERROR paths and assert `PALIMPSEST_LOG_LEVEL` controls verbosity. Tests must prove logs contain only approved IDs, ticks, versions, component names, counts, and reason codes, with no memory/query/observation/communication content, relation values, source payloads, vectors, SQL parameters, credentials, or foreign-owner results.
  - Dependencies: Depends on tasks 3-8.

- [ ] Task 10: Document the episodic memory boundary and complete project quality gates.
  - Deliverable: Complete the mandatory `$aif-docs` checkpoint. Document fragmentary trace semantics, direct observation versus communicated claims, owner/run isolation, normalized schema, optional embeddings, structured-first retrieval, score formula/versioning, access accounting, logical-tick decay/forgetting, service composition, transaction behavior, event-log prohibition, safe logging, and deferred reconstruction/reconsolidation. Update project context and architecture artifacts for the `persistence -> memory` adapter dependency without marking objective replay or M4 analysis as changed, then run all formatting, linting, typing, architecture, unit/property, migration, and opt-in PostgreSQL/pgvector checks.
  - Files: `README.md`, `docs/architecture.md`, `docs/cognition-runtime.md`, `docs/persistence.md`, `docs/development.md`, `.env.example` only if composition settings are added, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`.
  - Logging: Documentation lists safe event names/fields and explicitly prohibits memory fragments, query context, communications, embeddings, and objective event payloads. Verification includes log-capture assertions and confirms production verbosity changes require no code edits.
  - Dependencies: Depends on tasks 1-9.

## Verification Commands

```bash
uv sync --frozen --python 3.12.14
uv run --frozen --python 3.12.14 ruff format --check src tests
uv run --frozen --python 3.12.14 ruff check src tests
uv run --frozen --python 3.12.14 mypy src tests
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term-missing
uv run --frozen --python 3.12.14 lint-imports --config pyproject.toml --no-cache --no-logo
PALIMPSEST_TEST_DATABASE_URL=<disposable-palimpsest_test-dsn> uv run --frozen --python 3.12.14 pytest -m integration tests/integration
```

## Acceptance Criteria

- `MemoryTrace` represents validated concepts, perceived entities, relations, context, salience, confidence, provenance, logical creation/access metadata, and direct-versus-communicated origin without requiring a sentence or retaining an arbitrary payload escape hatch.
- Every normal memory service is bound to one run and owner. Domain, cognition, service, SQL, and test defenses prevent reads, writes, access updates, forgetting, limits, and vector ranking from revealing or mutating another agent's memory.
- No agent memory API, adapter, query, or reconstruction path reads or joins the objective event store, world snapshots, replay service, or private world state. Opaque observed-source correlation never grants dereference authority.
- Structured owner/context/concept/entity/relation/provenance filters execute before semantic scoring and limiting. Retrieval remains correct when pgvector input or stored embeddings are absent.
- A versioned policy deterministically combines semantic relevance, recency, emotional salience, current context, social relevance, and access history with validated configurable weights, quantization, and a documented total tie-break order shared by Python and PostgreSQL.
- Decay and forgetting use explicit simulation ticks only. Fixed-policy retrieval and forgetting produce equal outputs across repeated runs, and no wall clock, global RNG, Python `hash()`, database row order, or vector-index order affects results.
- Successful cognition applies new traces and idempotent access receipts atomically; failed cognition and failed batches leave all trace content and access metadata unchanged. Conflicting memory ID reuse never overwrites prior subjective evidence.
- PostgreSQL persists normalized trace, concept, entity, and relation data plus optional fixed-dimension vectors under composite run/owner keys. Mutable subjective tables remain separate from append-only authoritative history.
- Unit/property tests deterministically prove model validation, storage, all score components, ownership, access history, and decay; opt-in PostgreSQL tests prove round trips, pgvector parity, filtering order, concurrency, rollback, migration constraints, and cross-run/cross-owner isolation.
- Memory, query, communication, relation, source payload, and embedding values never appear in operational logs or exception representations; verbose logging remains metadata-only and environment-controlled.
- The `MemoryService` and retrieval result preserve stable snapshots, rank/match metadata, policy version, tick, and lineage needed for later reconstruction and reconsolidation without implementing those future behaviors.
- Ruff, mypy, unit/property tests, architecture/import-linter checks, serialization tests, migration checks, and opt-in PostgreSQL/pgvector integration tests pass.
