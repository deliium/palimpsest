# Implementation Plan: Reconstructive Memory, Distortion, and Reconsolidation

Branch: main (branch creation disabled by project config)
Created: 2026-09-21

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M3 — Cognition and Providers"
Rationale: Reconstructive recall is the next production cognition policy built on the delivered episodic-memory and structured LLM-provider foundations; its read-only drift metrics also establish part of M4 analysis.

## Goal

Replace literal trace return during agent recall with a typed, auditable reconstruction pipeline:

```text
MemoryRecallRequest
-> owner-scoped retrieval
-> normalized recall evidence
-> deterministic or LLM-backed reconstruction
-> ReconstructedMemory
-> optional append-only reconsolidation
```

The reconstruction must be explicitly subjective and permitted to omit, blend, reinterpret, or invent details. It must use only agent-available evidence: retrieved traces, current context, current beliefs, emotional significance, memory age, social significance, and source confidence. It must never receive objective `WorldEvent` content or other world authority.

Persist enough provenance to audit chains such as `objective event -> root trace -> reconstruction -> derived trace -> later reconstruction/story`, while keeping objective events immutable and old traces intact. Read-only experiment analysis may join opaque source-event correlation with objective events after reconstruction to quantify per-step and cumulative drift; normal agents, memory services, and cognition components may not perform that join.

## Design Decisions

- Keep `MemoryRetrieveRequest` as the lower-level ranking contract and compose `MemoryRecallRequest` around it. Retrieval remains owner/run scoped and produces ranked evidence; recall is the public behavioral operation that returns `ReconstructedMemory` rather than treating stored `MemoryTrace` rows as remembered episodes.
- Add frozen, strictly validated recall-domain values in `memory`: `ReconstructionId`, `MemoryRecallContext`, normalized `RecallEvidence`, a versioned reconstruction policy, `MemoryRecallRequest`, `ReconstructedMemory`, and append-only reconstruction/derivation records. A reconstructed episode contains bounded subjective narrative plus normalized concepts/entities/relations/context so it can be consumed by cognition and, when requested, encoded as a new trace.
- Represent sensory origin and reconstruction derivation separately. `MemoryProvenance` continues to describe direct observation or communicated origin with an opaque `observed_source_id`; derivation records and lineage identify every direct source trace and the reconstruction that produced a derived trace. Preserve the existing principal `supersedes_memory_id` field for persisted compatibility, but define it as a non-destructive principal predecessor, not permission to replace or deactivate the parent.
- Persist ordered direct-source edges instead of only one predecessor. Require same run/owner scope, pre-existing source traces, fresh derived IDs, dense generation (`1 + max(source generations)`), deterministic edge order, and no cycles. Full ancestry is traversed from direct edges, while roots retain opaque event correlation.
- Never overwrite, delete, soft-forget, or deactivate a source trace merely because reconsolidation occurred. Reconsolidation inserts a reconstruction record, source edges, and optional derived `MemoryTrace` in one atomic batch. Existing access and explicit forgetting semantics remain separate.
- Make old and derived evidence compete through explicit, versioned retrieval policy rather than destructive replacement. Continue logical-tick recency/retention decay, add derivation-aware weighting or ancestry de-duplication where configured, and document whether age means episode age (`current_tick - source_tick`) or storage age (`current_tick - created_tick`). No hidden wall-clock or random behavior is allowed.
- Keep reconstruction policy independent from transport. Define the reconstruction protocol and deterministic fallback in domain/cognition code; inject an optional `LLMProvider` implementation. The LLM receives a bounded canonical evidence DTO, never repositories, raw observations, event records, prompts from memory content, or world state.
- Define the LLM candidate as an exact `StructuredOutput` subtype and apply a second semantic-validation/translation gate. Reject unknown source/belief IDs, foreign owners, invalid relation endpoints, unbounded text, non-finite scores, invented authority IDs, invalid generations, and duplicate or unordered references. Structurally valid output remains subjective and non-authoritative.
- Preserve deterministic offline behavior. With no provider, provider failure, or semantic rejection, use a versioned deterministic reconstructor that projects ranked evidence without inventing objective facts. Propagate cancellation. Record provider/fallback status and policy/prompt versions as metadata without logging or persisting raw provider responses.
- Integrate recall into the existing cognition memory-retrieval stage rather than adding a new top-level `CognitiveLoop` stage initially. `RetrievedMemoryContext` exposes reconstructed episodes for downstream situation modeling and retains source metadata/pending accesses as scientific evidence. Optional derived writes remain deferred until the whole cognitive loop succeeds and are committed by `AgentRuntime` with access receipts.
- Add reconstruction records to subjective scientific persistence, not authoritative event history or replay. Objective `WorldEvent` tables, event codecs, hashes, and replay paths remain unchanged. Reconstruction records may be append-only even though trace access/forgetting metadata remains mutable.
- Put objective comparison entirely in `analysis`. A memory-only reconstructor signature must make it impossible to receive `WorldEvent`; an experiment analysis service independently reads immutable events and subjective provenance chains, then joins them to calculate versioned structured drift metrics. Missing objective sources are reported as unknown/unlinked, never inferred.
- Measure drift over structured facts and narrative fingerprints: retained/lost/added concepts, entity grounding changes, relation mutations, context changes, confidence/salience deltas, provenance continuity, and exact canonical equality. Event-to-memory comparison uses versioned event-kind projectors and distinguishes absent/unknown information from contradictions or unsupported additions.
- Preserve log hygiene. Memories, beliefs, narratives, relations, communications, embeddings, prompts, schemas, provider outputs, and objective event payloads never enter operational logs. Safe metadata is limited to run/owner/invocation/request/reconstruction IDs, logical tick, policy/prompt/model versions, counts, generation, fallback/provider flags, durations, and stable reason/error codes.

## Non-Goals

- Giving agents, cognition, ordinary `MemoryService` instances, or reconstruction policies access to objective `WorldEvent`, event repositories, replay services, snapshots, or private world state.
- Treating a reconstruction as truth, correcting an agent against objective history during recall, or automatically revising beliefs to match experiment ground truth.
- Destructively updating or deleting old trace content, reusing a memory ID, or making reconsolidation equivalent to forgetting.
- Replacing the existing provider-neutral `LLMProvider`, adding vendor SDKs, or requiring network access in default tests.
- Guaranteeing bit-for-bit replay of live external LLM calls without recorded validated outputs; deterministic fakes or persisted reconstruction evidence remain required for exact experimental replay.
- Exposing reconstruction or objective-comparison APIs over FastAPI in this feature.

## Commit Plan
- **Commit 1** (after tasks 1-3): `feat(memory): add reconstructive recall contracts and policies`
- **Commit 2** (after tasks 4-6): `feat(memory): integrate and persist reconsolidation provenance`
- **Commit 3** (after tasks 7-9): `feat(analysis): measure auditable memory drift`

## Tasks

### Phase 1: Recall Contracts and Reconstruction Policies

- [x] Task 1: Define strict reconstructive-recall and provenance contracts.
  - Deliverable: Add frozen, slotted domain values for reconstruction identity, current recall context, normalized source evidence, policy/version settings, `MemoryRecallRequest`, `ReconstructedMemory`, reconstruction records, and optional reconsolidation intent. Compose the request with `MemoryRetrieveRequest`; include current beliefs, current context, explicit episode/storage ages, emotional and social significance, source confidence, and a caller-supplied stable reconstruction/derived-memory identity. Extend `MemoryLineage` with ordered direct source memory IDs and an optional producing reconstruction ID while retaining `supersedes_memory_id` as the principal non-destructive predecessor. Enforce owner consistency, unique ordered references, non-empty sources for derived output, fresh IDs, bounded subjective narrative and structured fragments, finite unit-interval scores, logical-tick ordering, dense generation, safe `repr`, and no objective-event-bearing field beyond existing opaque `EventId` correlation.
  - Files: `src/memory/models.py`, `src/memory/contracts.py`, `src/memory/__init__.py`, `tests/unit/test_v1_episodic_memory_models.py`, `tests/unit/test_memory_reconstruction.py`, `tests/unit/test_v1_memory_property.py`, `tests/typecheck/episodic_memory_contracts.py`.
  - Logging: Domain values and protocols remain log-free. Validation errors expose field names and stable reason codes only; they never include trace content, beliefs, narrative, relation values, context, source IDs, or embeddings.
  - Dependencies: None. This contract fixes the vocabulary used by policies, cognition, persistence, and analysis.

- [x] Task 2: Implement deterministic reconstruction, reconsolidation planning, and derivation-aware retrieval policy.
  - Deliverable: Add a pure recall orchestrator that executes owner-scoped retrieval, converts ranked hits plus supplied beliefs/context into bounded `RecallEvidence`, invokes an injected reconstructor, semantically validates the result, and returns `ReconstructedMemory` with pending access receipts and optional derived-trace intent. Implement a deterministic default reconstructor with documented confidence/salience aggregation, source-priority and tie-breaking rules, explicit age semantics, no free-form invention, and stable ordering. Extend scoring/policy behavior so callers can configure logical-age decay, lineage-generation influence, and ancestry de-duplication without hiding old traces or changing existing policy behavior by default. Validate append-only reconsolidation plans against all direct parents before mutation and require caller-injected deterministic ID allocation rather than UUIDs, Python `hash()`, wall clocks, or global RNG.
  - Files: `src/memory/reconstruction.py`, `src/memory/scoring.py`, `src/memory/models.py`, `src/memory/service.py`, `src/memory/__init__.py`, `tests/unit/test_memory_reconstruction.py`, `tests/unit/test_v1_memory_retrieval_scoring.py`, `tests/unit/test_v1_memory_decay.py`, `tests/unit/test_v1_episodic_memory_ownership.py`, `tests/unit/determinism_helpers.py`.
  - Logging: Pure scoring, evidence normalization, and deterministic reconstruction remain log-free. The orchestration boundary may emit DEBUG policy/tick/generation and candidate/source/output counts, INFO fallback selection and reconsolidation intent counts, and WARN/ERROR stable rejection codes; no evidence or reconstructed payload is logged.
  - Dependencies: Depends on task 1 for requests, results, policy, and lineage invariants.

- [x] Task 3: Add an optional structured LLM reconstruction adapter with fail-closed translation.
  - Deliverable: Implement a cognition-side reconstructor that maps bounded canonical `RecallEvidence` into `LLMRequest`, calls an injected `LLMProvider`, and translates an exact `StructuredOutput` candidate into project-owned `ReconstructedMemory` values only after semantic validation. Add a recall-specific immutable prompt resource and digest-pinned manifest rather than modifying existing prompt versions. Treat memory/communication text as untrusted data, cap source/belief/text sizes, reference supplied IDs rather than accepting arbitrary authority IDs, use deterministic request correlation/options where supported, propagate `CancelledError`, and fall back to the deterministic policy on configured provider/validation failures. Preserve provider neutrality and do not import Pydantic directly into domain packages or add cognition knowledge to `llm`.
  - Files: `src/agents/cognition/reconstruction.py`, `src/agents/cognition/__init__.py`, `src/llm/prompts/reconstructive_memory/v1/manifest.json`, `src/llm/prompts/reconstructive_memory/v1/system.txt`, `src/llm/prompts/reconstructive_memory/v1/user.txt`, `tests/fakes/llm.py`, `tests/unit/test_memory_llm_reconstruction.py`, `tests/unit/test_llm_prompts.py`, `tests/unit/test_llm_trust_boundary.py`, `tests/unit/test_fake_llm_provider.py`.
  - Logging: Emit DEBUG request/reconstruction IDs, tick, prompt/policy/model versions, source counts, and attempt counts; INFO provider-versus-fallback outcome; WARN semantic/provider reason codes; ERROR terminal safe codes. Never log evidence, beliefs, narratives, prompts, schemas, output bodies, endpoints, credentials, exception text, or provider request/response payloads.
  - Dependencies: Depends on tasks 1 and 2; reuses `LLMProvider` without changing its trust contract.

### Phase 2: Cognition Integration and Durable Reconsolidation

- [x] Task 4: Replace literal cognition retrieval output with reconstructed memories and deferred reconsolidation.
  - Deliverable: Upgrade `ScopedMemoryRetriever` or add a reconstructive wrapper so the cognition memory stage builds current context/social signals, supplies actual owner-scoped belief snapshots, recalls through the new service, and returns reconstructed episodes for downstream situation modeling instead of using stored traces as remembered episodes. Preserve ranked source evidence and pending access receipts only as typed scientific metadata. Extend `RetrievedMemoryContext`, memory-update intents, loop validation, diagnostics, defaults, and fakes; keep the default loop deterministic and provider-free unless a reconstructor is injected. Extend `AgentRuntime` prevalidation/application so optional reconstruction records and derived traces commit only after the entire cognition run succeeds, in the same mutation batch as access receipts, while later cognition failure, provider cancellation, or invalid output leaves memory unchanged.
  - Files: `src/agents/cognition/models.py`, `src/agents/cognition/contracts.py`, `src/agents/cognition/defaults.py`, `src/agents/cognition/memory.py`, `src/agents/cognition/loop.py`, `src/agents/cognition/__init__.py`, `src/simulation/agent_runtime.py`, `tests/fakes/cognition.py`, `tests/fakes/memory.py`, `tests/unit/test_v1_episodic_memory_cognition.py`, `tests/unit/test_cognitive_loop.py`, `tests/unit/test_cognition_defaults.py`, `tests/unit/test_agent_runtime.py`, `tests/integration/test_agent_runtime_world_engine.py`.
  - Logging: Cognition emits DEBUG owner/tick/invocation, retrieval/reconstruction policy versions, source/reconstruction/pending-write counts, generation, and provider/fallback flags. Runtime emits DEBUG prevalidation/apply counts, INFO successful reconsolidation count, and WARN/ERROR stable failure codes. No observation, communication, memory, belief, narrative, command argument, or provider payload is logged.
  - Dependencies: Depends on tasks 1-3. Must preserve the existing no-mutation-on-failed-cognition contract.

- [x] Task 5: Add append-only reconstruction and multi-source derivation persistence.
  - Deliverable: Create Alembic revision `0006` and SQLAlchemy mappings for append-only reconstruction records, ordered reconstruction source edges, and derived-trace source edges under composite `(run_id, owner_id, ...)` scope. Add same-scope foreign keys to source/derived traces, unique ordinals and edge identities, generation/shape checks, reconstruction policy/schema/prompt/provider metadata, canonical payload hash where needed for audit, and indexes for root/parent/descendant traversal plus opaque observed-source lookup. Backfill the current single `supersedes_memory_id` as a direct edge where valid. Keep old trace rows and objective event rows unchanged; do not add a memory-layer event dereference or require an objective-event FK. Add selective immutability enforcement for reconstruction records, derivation edges, and trace content while allowing existing access-count and explicit-forgetting updates. Keep all new tables outside `AUTHORITATIVE_TABLES` and objective replay.
  - Files: `src/persistence/memory_orm.py`, `src/persistence/orm.py`, `alembic/versions/0006_memory_reconstruction_lineage.py`, `tests/integration/test_migrations.py`, `tests/unit/test_sqlalchemy_repository.py`.
  - Logging: ORM declarations remain silent. Migration diagnostics may log revision/table/index/constraint names and aggregate backfill counts at INFO/DEBUG plus stable failure classes at ERROR; never log row content, reconstructed narratives, memory fragments, event payloads, hashes paired with payloads, SQL parameters, or DSNs.
  - Dependencies: Depends on task 1 for the final lineage/reconstruction shape. Can proceed in parallel with task 4 after contracts stabilize.

- [x] Task 6: Implement atomic in-memory/PostgreSQL reconsolidation and versioned codecs.
  - Deliverable: Extend `MemoryMutationBatch` and both memory-service implementations to atomically validate and insert reconstruction records, ordered source edges, optional derived traces, and access receipts. Require all sources to pre-exist in the bound scope, enforce fresh IDs and dense generation, reject dangling/cross-owner/cross-run/cyclic/self references, make retry behavior idempotent, and roll back every component on conflict. Never modify source trace content or mark a source forgotten/superseded as a side effect. Add concurrency control so competing reconsolidations remain independently append-only without partial edges. Upgrade strict memory serialization for the expanded lineage/reconstruction schema with explicit version handling and legacy trace decoding where persisted data requires it; update fakes so they reject duplicate IDs instead of overwriting them.
  - Files: `src/memory/models.py`, `src/memory/service.py`, `src/persistence/memory_sqlalchemy.py`, `src/persistence/__init__.py`, `src/simulation/serialization.py`, `tests/fakes/memory.py`, `tests/unit/test_memory_reconstruction.py`, `tests/unit/test_v1_domain_serialization.py`, `tests/unit/test_fake_memory_components.py`, `tests/integration/test_episodic_memory_pgvector.py`, `tests/integration/test_memory_concurrency.py`, `tests/typecheck/episodic_memory_contracts.py`.
  - Logging: Services emit DEBUG scope/tick/operation/reconstruction IDs, policy version, generation, and write/edge/access counts; INFO committed reconsolidation counts; WARN idempotent/stale/conflict reason codes; ERROR rollback codes. Codecs remain log-free. Never log trace/reconstruction content, source payloads, vectors, SQL/DSN values, or foreign-owner evidence.
  - Dependencies: Depends on tasks 1, 2, and 5; supports task 4's deferred side effects.

### Phase 3: Experiment Analysis, Scientific Proofs, and Documentation

- [x] Task 7: Add experiment-only provenance traversal and measurable memory-drift analysis.
  - Deliverable: Expand the read-only `analysis` package with immutable reconstruction-chain and drift DTOs, memory-evidence source protocols, versioned event-kind fact projectors, pure comparison functions, and an experiment analysis service. The service may independently read immutable objective events and subjective memory/reconstruction evidence, correlate roots by run/owner plus opaque `observed_source_id`, traverse ordered derivation edges, and compare objective source (when available), root trace, each reconstruction, and final derived story. Report per-step and cumulative retained/lost/added concepts, entity/relation/context changes, confidence/salience deltas, provenance breaks, and canonical equality while distinguishing unknown/absent from contradicted/unsupported facts. Ensure the reconstructor capability receives only memory evidence; objective truth is joined after reconstruction and is never injected into `AgentRuntime`, `CognitiveLoop`, `MemoryService`, or a reconstruction policy. Add a read-only persistence adapter scoped by explicit experiment/run membership if durable evidence queries are required.
  - Files: `src/analysis/models.py`, `src/analysis/contracts.py`, `src/analysis/memory_drift.py`, `src/analysis/service.py`, `src/analysis/__init__.py`, `src/persistence/analysis_sqlalchemy.py`, `src/persistence/__init__.py`, `pyproject.toml`, `tests/unit/test_analysis_contracts.py`, `tests/unit/test_memory_drift_analysis.py`, `tests/unit/test_reconstruction_analysis_service.py`, `tests/unit/test_sqlalchemy_repository.py`.
  - Logging: Pure metrics remain log-free. Analysis orchestration may log DEBUG experiment/run/owner IDs, policy/schema versions, chain lengths, linked/unlinked counts, and metric names; INFO completed comparison counts; WARN missing/broken provenance reason codes; ERROR read/validation codes. Never log event details, memory content, narratives, communications, reconstructed facts, or SQL parameters.
  - Dependencies: Depends on tasks 1, 5, and 6 for stable, traversable evidence. It must not become a dependency of memory, cognition, simulation, or API code.

- [x] Task 8: Prove controlled repeated drift, auditability, isolation, and replay independence.
  - Deliverable: Add a deterministic scripted reconstructor whose versioned schedule removes, mutates, and adds structured details across repeated recalls. Prove that repeated recall can measurably drift; every reconstruction and derived trace retains ordered direct sources, immediate parent, root correlation, dense generation, owner/run scope, and policy version; original traces and objective events remain byte/canonically unchanged; per-step and cumulative metrics match expected transformations; and identical inputs/policy produce identical reports. Add property tests over bounded edit sequences, concurrent reconsolidation rollback/idempotency tests, provider success/failure/cancellation tests, and SQL/in-memory parity. Extend AST/import-linter checks to prohibit `WorldEvent`, event readers, replay/journal repositories, and private world authority in `agents`, `agents.cognition`, `memory`, reconstruction protocols, and runtime composition while allowing opaque `EventId`; prove only read-only analysis can hold both objective and subjective source capabilities. Add replay regressions showing subjective recall cannot change objective event hashes, revisions, continuation eligibility, or replay output.
  - Files: `tests/unit/test_memory_reconstruction_drift.py`, `tests/unit/test_memory_drift_analysis.py`, `tests/unit/test_memory_llm_reconstruction.py`, `tests/unit/test_v1_memory_property.py`, `tests/unit/test_agent_runtime.py`, `tests/unit/test_replay_service.py`, `tests/unit/test_simulation_replay_determinism.py`, `tests/integration/test_episodic_memory_pgvector.py`, `tests/integration/test_memory_concurrency.py`, `tests/integration/test_simulation_persistence_replay.py`, `tests/architecture/boundary_checker.py`, `tests/architecture/test_boundary_checker.py`, `tests/architecture/test_import_boundaries.py`, `tests/architecture/test_memory_isolation.py`, `tests/architecture/test_cognitive_loop_isolation.py`, `tests/architecture/test_analysis_isolation.py`, `pyproject.toml`.
  - Logging: Capture verbose paths and assert `PALIMPSEST_LOG_LEVEL` controls output. Tests must prove logs and exceptions contain only approved metadata/reason codes and never memories, beliefs, narratives, prompts, provider bodies, communications, event details, embeddings, SQL parameters, credentials, or hidden identities.
  - Dependencies: Depends on tasks 1-7. This is the controlled scientific acceptance proof requested by the feature.

- [x] Task 9: Document reconstructive-memory semantics and run all quality gates.
  - Deliverable: Complete the mandatory `/aif-docs` checkpoint. Document subjective reconstruction, deterministic and LLM-backed policy composition, exact structured validation versus semantic validation, current-context/belief/emotional/social/age/source-confidence inputs, non-destructive reconsolidation, lineage traversal, retrieval weighting/decay, migration and transaction behavior, experiment-only objective comparison, drift metrics, replay limitations, and metadata-only logging. Update architecture/project context to remove reconstruction from deferred scope, permit `analysis -> memory` read-only contracts, and explicitly forbid objective events in agent/memory/reconstruction APIs. Update the roadmap only through its owner workflow if milestone status changes. Run formatting, linting, typing, architecture, unit/property, migration, serialization, and opt-in PostgreSQL/pgvector checks.
  - Files: `README.md`, `docs/architecture.md`, `docs/cognition-runtime.md`, `docs/persistence.md`, `docs/development.md`, optionally `docs/memory-reconstruction.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`.
  - Logging: Documentation defines safe event names and metadata allowlists for recall, LLM fallback, reconsolidation, and analysis, and explicitly prohibits subjective/objective payloads. Verification includes log-capture tests and confirms verbosity remains environment-controlled without code changes.
  - Dependencies: Depends on tasks 1-8.

## Verification Commands

```bash
uv sync --frozen --python 3.12.14
uv run --frozen --python 3.12.14 ruff format --check src tests
uv run --frozen --python 3.12.14 ruff check src tests
uv run --frozen --python 3.12.14 mypy src tests
uv run --frozen --python 3.12.14 lint-imports --config pyproject.toml --no-cache --no-logo
uv run --frozen --python 3.12.14 pytest tests/unit tests/architecture tests/typecheck --cov --cov-report=term-missing
PALIMPSEST_TEST_DATABASE_URL=<disposable-palimpsest_test-dsn> uv run --frozen --python 3.12.14 pytest -m integration tests/integration
```

## Acceptance Criteria

- Agent recall accepts a validated `MemoryRecallRequest`, performs owner-scoped retrieval internally, and returns one or more validated `ReconstructedMemory` episodes; downstream cognition does not treat raw stored traces as the remembered episode.
- Reconstruction can use retrieved traces, current context, current beliefs, explicit episode/storage age, emotional significance, social significance, and source confidence. Every input is bounded, typed, owner-safe, and visible in a versioned policy rather than hidden global state.
- Deterministic recall works without an LLM. Optional `LLMProvider` reconstruction uses exact structured output plus semantic validation, remains non-authoritative, propagates cancellation, and fails over according to explicit policy without leaking payloads.
- A reconstruction is explicitly subjective and may be wrong. Its narrative and structured claims cannot become objective events, world commands, event corrections, or trusted facts without the normal downstream cognition/world trust stages.
- Optional reconsolidation atomically adds reconstruction evidence, derivation edges, and fresh derived traces. It never overwrites, deactivates, forgets, or deletes objective events or prior trace content, and duplicate/conflicting batches cannot leave partial provenance.
- Every derived trace identifies all direct source traces and its producing reconstruction; generations are dense, scope is unchanged, sources pre-exist, cycles/self-links are rejected, and roots retain opaque source-event correlation where originally available.
- Retrieval/retention policies can make older evidence less influential through explicit logical-tick decay, recency, generation weighting, or ancestry de-duplication while keeping old evidence available for audit and analysis.
- Read-only experiment analysis can traverse `WorldEvent -> root trace -> reconstruction -> derived trace/reconstruction -> later story` when correlation exists and can calculate versioned per-step/cumulative drift. Missing objective truth is reported as unavailable, not inferred.
- Agents, cognition, memory, runtime, and reconstruction components cannot import, receive, query, or dereference objective events, event stores, replay services, snapshots, or private world state. Architecture tests enforce the boundary; only analysis may join objective and subjective evidence.
- Controlled deterministic tests demonstrate repeated recall drift while proving immutable objective/root evidence, complete provenance, reproducible metrics, transaction rollback, concurrency behavior, and objective replay independence.
- All operational logs remain metadata-only at verbose level and are reducible through `PALIMPSEST_LOG_LEVEL`; no memory, belief, reconstruction, communication, prompt, provider, event, embedding, SQL, or credential payload appears in logs or exception representations.
- Ruff, mypy, import-linter, unit/property, architecture, typecheck, serialization, migration, PostgreSQL/pgvector integration, concurrency, and replay tests pass.
