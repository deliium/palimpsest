# Implementation Plan: Semantic Beliefs, Emergent Self-Model, and Subjective Relationships

Branch: main
Created: 2026-09-21

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M3 — Cognition and Providers"
Rationale: This feature replaces placeholder cognition state with experience-derived semantic beliefs, self-understanding, and subjective social assessments.

## Goal

Give each agent private, durable, and revisable semantic knowledge derived from its episodic memories. Use the same belief machinery to project an emergent self-model, and maintain independent directed relationship profiles for other agents without introducing friendship, enemy, morality, group, leadership, or culture classifications.

## Design Decisions

- Keep all beliefs, self-model projections, and relationship assessments subjective and owner-scoped; they must never become `WorldEvent` variants, authoritative replay state, or inputs obtained from objective event repositories.
- Represent a belief as a canonical structured claim with subject, predicate, and typed value, plus an append-only revision history. Preserve compatibility for the existing serialized `Belief` and `Relationship` forms by introducing versioned semantic types/tags rather than silently changing schema-v1 meanings.
- Record supporting and contradicting evidence separately. Evidence references owned `MemoryTrace` values and records stance, contribution, ordinal, and lineage/root grouping; it never dereferences objective events.
- Use explicit logical ticks, deterministic IDs, stable ordering, fixed score quantization, and a versioned revision policy. Decay confidence toward uncertainty, not toward contradiction, and avoid counting reconstructed descendants sharing the same episodic roots as independent evidence.
- Form or strengthen a belief only after the configured minimum number of independent episodic observations. A competing value for the same subject/predicate is contradictory evidence for the current value.
- Define `SelfModel` as a deterministic view over general beliefs relevant to the owner, including claims where the owner is subject or referenced value. Do not persist predefined traits, archetypes, moral alignments, or character classes.
- Model relationships as independent `source_id -> target_id` profiles. Each of trust, fear, affection, debt, respect, resentment, familiarity, and dependency has its own value, confidence, evidence, and revision metadata. Debt means the source believes it owes the target.
- Derive relationship evidence from owned episodes through a versioned low-level signal policy; never store derived `friend`, `enemy`, `leader`, group, morality, or culture labels.
- Build one frozen subjective snapshot per cognition invocation and commit episodic, belief, and relationship mutations through one owner-scoped, idempotent transaction. A failed component must leave no partial subjective updates.
- Keep semantic payloads out of operational logs and exception text. Logs may contain only run/owner/record IDs, logical ticks, policy versions, counts, statuses, and stable reason codes.

## Commit Plan
- **Commit 1** (after tasks 1-3): `feat(cognition): add semantic belief and relationship policies`
- **Commit 2** (after tasks 4-6): `feat(simulation): integrate atomic subjective cognition state`
- **Commit 3** (after tasks 7-9): `feat(persistence): persist and document subjective agent models`

## Tasks

### Phase 1: Subjective Domain Model

- [x] Task 1: Define structured semantic beliefs and append-only revision contracts.
  - Deliverable: Add canonical subject/predicate/typed-value claim values, evidence stance and contribution records, belief revision identity/history, confidence state, policy metadata, activation/retirement state, and owner-scoped requests/results. Retain the current `Belief` codec as a legacy projection or add an explicit new semantic type so existing strict decoders do not reinterpret old data.
  - Expected behavior: Claims have deterministic identity independent of display prose; supporting and contradicting memory references are ordered, unique, owner-valid, and mutually exclusive per revision; all numeric values are finite and bounded; revisions and ticks are monotonic; safe `repr` output exposes IDs/counts only.
  - Files: `src/memory/beliefs.py` (new), `src/memory/models.py`, `src/memory/contracts.py`, `src/memory/errors.py`, `src/memory/__init__.py`, `tests/unit/test_semantic_belief_models.py` (new), `tests/typecheck/semantic_belief_contracts.py` (new).
  - Logging requirements: Domain values, validators, and pure stores emit no logs. Service-facing errors use stable payload-free reason codes; tests must prove propositions, values, and evidence content do not appear in `repr` or errors.
  - Dependencies: None.

- [x] Task 2: Implement deterministic belief formation, contradiction handling, confidence revision, and decay from episodic evidence.
  - Deliverable: Add a versioned deterministic extractor/revision policy that converts normalized `MemoryTrace` concepts, entities, and relations into canonical evidence candidates, groups repeated independent episodes, creates beliefs after the minimum evidence threshold, revises existing beliefs, and exposes complete history. Use provenance weights for direct versus communicated memories and lineage-root deduplication for reconstructed traces.
  - Expected behavior: Repeated support raises confidence; competing values and explicit negative evidence lower it; balanced evidence approaches uncertainty; elapsed logical ticks decay accumulated evidence toward uncertainty; permutations of the same evidence produce identical IDs, ordering, and scores; retries with the same operation ID are idempotent; no wall clock, UUID default, global RNG, embedding-only identity, or Python `hash()` is used.
  - Files: `src/memory/belief_formation.py` (new), `src/memory/belief_service.py` (new), `src/memory/scoring.py`, `src/memory/__init__.py`, `tests/unit/test_semantic_belief_formation.py` (new), `tests/unit/test_semantic_belief_decay.py` (new), `tests/unit/test_semantic_belief_service.py` (new).
  - Logging requirements: Emit DEBUG metadata for revision start/result with owner ID, belief ID, tick, policy version, support/contradiction counts, and idempotency status; emit INFO only when a belief activates, retires, or materially changes revision; emit WARN/ERROR with stable reason codes for rejected ownership, chronology, or conflicting operation IDs. Never log claim text, typed values, memory contents, speaker content, or evidence payloads.
  - Dependencies: Task 1.

- [x] Task 3: Replace generic affinity with evidence-backed asymmetric relationship profiles and update policies.
  - Deliverable: Add owner-bound directed relationship snapshots/revisions and an extensible dimension model covering trust, fear, affection, debt, respect, resentment, familiarity, and dependency. Add an in-memory relationship service plus a versioned policy that converts low-level owned episodic interaction signals into per-dimension evidence and revisions without reciprocal writes.
  - Expected behavior: `Alice -> Bob` may exist without `Bob -> Alice`; updating either direction never creates or changes the reverse direction; each dimension carries a bounded value, confidence, evidence references, logical tick, and policy provenance; no high-level social category fields or enums are introduced; foreign-source and self-target records fail closed.
  - Files: `src/social/models.py`, `src/social/contracts.py`, `src/social/relationships.py` (new), `src/social/service.py` (new), `src/social/__init__.py`, `tests/unit/test_subjective_relationships.py` (new), `tests/typecheck/subjective_relationship_contracts.py` (new).
  - Logging requirements: Pure relationship values and update math stay log-free. The service logs DEBUG metadata for source/target IDs, tick, policy version, changed-dimension count, evidence count, and idempotency; WARN/ERROR logs use stable codes and must omit dimension values, labels, communications, memories, and evidence payloads.
  - Dependencies: Task 1 for shared evidence and deterministic revision conventions; `social` must remain independent of `memory`, so shared concepts must be passed through public cognition/service request values rather than imported privately.

### Phase 2: Cognition and Runtime Integration

- [x] Task 4: Project an emergent `SelfModel` from general semantic beliefs.
  - Deliverable: Replace the placeholder `SelfBeliefState` path with a versioned `SelfModel` projection that selects ordered self-relevant semantic beliefs, goal references, and confidence metadata from the same owner snapshot. Update self-state, future, motivation, boundary-record, default-component, and public-facade contracts without introducing predefined personality or role classes.
  - Expected behavior: Experiences such as repeated successful food discovery, protection of another agent, or evidence that others trust the owner can gradually produce self-relevant claims such as “I find food effectively,” “I protect others,” and “others trust me.” Identical belief snapshots produce identical self-models; weak, contradicted, decayed, or foreign-owner claims are excluded according to the explicit projection policy.
  - Files: `src/agents/cognition/models.py`, `src/agents/cognition/contracts.py`, `src/agents/cognition/defaults.py`, `src/agents/cognition/loop.py`, `src/agents/cognition/__init__.py`, `tests/unit/test_cognition_models.py`, `tests/unit/test_cognition_defaults.py`, `tests/unit/test_cognitive_loop.py`, `tests/unit/test_self_model_development.py` (new).
  - Logging requirements: Cognitive components log DEBUG stage name/version, owner ID, tick, candidate/selected belief counts, aggregate confidence, and completion status only. Never log self-belief subjects, predicates, values, reconstructed narratives, or hidden reasoning; boundary records remain scientific artifacts rather than log payloads.
  - Dependencies: Tasks 1-2.

- [x] Task 5: Feed one frozen subjective snapshot through cognition and emit deferred belief/relationship revisions.
  - Deliverable: Extend `Perspective` and `build_perspective()` with owned semantic beliefs and directed relationships, then carry that validated snapshot into `CognitiveLoopInput` instead of constructing and discarding it in `AgentRuntime`. Replace or generalize `MemoryUpdateIntent` with typed subjective intents for memory writes, belief revisions, and relationship revisions; update retrieval and formation hooks so current episodes propose changes only after cognition succeeds and become visible on the next invocation.
  - Expected behavior: Every stage observes one consistent owner snapshot; semantic content, not only belief IDs, can influence self-state and future/motivation policies; no retriever mutates stores; another agent's beliefs, reverse relationship, all-agent identity map, `WorldState`, `WorldEvent`, repositories, or mutation writers can enter cognition; malformed or foreign-owner outputs fail closed before any write.
  - Files: `src/agents/cognition/models.py`, `src/agents/cognition/contracts.py`, `src/agents/cognition/memory.py`, `src/agents/cognition/defaults.py`, `src/agents/cognition/loop.py`, `src/simulation/perception.py`, `src/simulation/agent_runtime.py`, `tests/unit/test_cognition_strategies.py`, `tests/unit/test_v1_episodic_memory_cognition.py`, `tests/unit/test_agent_runtime.py`.
  - Logging requirements: Add DEBUG metadata for snapshot revision/counts and proposed intent counts by kind; WARN/ERROR ownership and type failures include only component, owner/invocation IDs, ordinal, and stable reason code. Do not log observations, inbox content, memories, claims, relationship values, or intent payloads.
  - Dependencies: Tasks 1-4.

- [x] Task 6: Add an atomic, idempotent subjective-state commit boundary.
  - Deliverable: Introduce a simulation-owned `SubjectiveStateService`/batch protocol that can atomically apply episodic writes/accesses/reconstructions, belief revisions, and relationship revisions for one `(run_id, owner_id)` scope. Provide copy-then-swap in-memory behavior, expected-revision conflict detection, deterministic invocation operation IDs, and serialized per-runtime processing; adapt legacy readers/writers only where needed during composition.
  - Expected behavior: Full prevalidation occurs before mutation; any invalid intent or adapter failure rolls back every subjective change; duplicate retries return an idempotent receipt; conflicting reuse fails with a stable code; concurrent processing cannot commit the same observation twice; successful commits update runtime state only after the subjective transaction completes; objective world commit/replay remains unchanged.
  - Files: `src/simulation/subjective_state.py` (new), `src/simulation/agent_runtime.py`, `src/simulation/__init__.py`, `src/memory/service.py`, `src/social/service.py`, `tests/unit/test_subjective_state_service.py` (new), `tests/unit/test_agent_runtime.py`, `tests/unit/test_simulation_replay_determinism.py`.
  - Logging requirements: Emit DEBUG start/complete records with run/owner/invocation IDs, expected/result revision, tick, per-intent counts, and idempotency; INFO records only significant activation/retirement counts; WARN on optimistic conflicts and duplicate attempts; ERROR on rollback with adapter and stable reason code. Never use `exc_info` or include payload-bearing exception text.
  - Dependencies: Tasks 2-5.

### Phase 3: Serialization, Persistence, and Quality Gates

- [x] Task 7: Add canonical subjective-state codecs while preserving legacy schemas.
  - Deliverable: Add strict versioned encoders/decoders for semantic claims, belief revisions/evidence, self-model projections where persistence/export requires them, relationship profiles/revisions, and subjective mutation receipts. Keep existing `belief` and `relationship` schema-v1 decoding behavior intact or explicitly migrate it; reject unknown fields and noncanonical order.
  - Expected behavior: Canonical bytes round-trip deterministically; malformed wrappers, duplicate evidence, invalid dimension values, and unknown versions fail safely; subjective codecs remain separate from authoritative world journals/checkpoints and cannot alter objective replay hashes.
  - Files: `src/simulation/serialization.py` or `src/simulation/subjective_serialization.py` (new), relevant package facades, `tests/unit/test_v1_domain_serialization.py`, `tests/unit/test_persistence_serialization.py`, `tests/unit/test_subjective_state_serialization.py` (new), serialization golden fixtures if the existing suite uses them.
  - Logging requirements: Codec functions remain log-free. Decoder errors expose only schema/type/field reason codes and positions, never claim text, values, relationship assessments, or evidence content.
  - Dependencies: Tasks 1, 3-6.

- [x] Task 8: Persist append-only belief and relationship history in migration `0007`.
  - Deliverable: Add subjective ORM tables for canonical beliefs, belief revisions/evidence, directed relationship profiles, relationship revisions/dimension evidence, and idempotent owner-scoped operations. Implement a PostgreSQL adapter for the atomic subjective batch, register metadata, intentionally allow `persistence -> social` through the public facade, update migration head declarations, and keep every new table disjoint from `AUTHORITATIVE_TABLES`.
  - Expected behavior: Composite keys and foreign keys include run and owner/source scope; evidence references `memory_traces`, never `world_events`; append-only revisions reject update/delete; `Alice -> Bob` and `Bob -> Alice` persist independently; all bounded/finite/tick/order constraints are enforced in PostgreSQL; upgrades/downgrades and concurrent retries are deterministic and transactional.
  - Files: `src/persistence/subjective_orm.py` (new), `src/persistence/subjective_sqlalchemy.py` (new), `src/persistence/__init__.py`, `src/persistence/memory_orm.py`, `alembic/versions/0007_subjective_agent_models.py` (new), `alembic/env.py`, `pyproject.toml`, `tests/unit/test_sqlalchemy_repository.py`, `tests/integration/test_migrations.py`, `tests/integration/test_subjective_state_persistence.py` (new), `tests/integration/test_memory_concurrency.py`.
  - Logging requirements: Adapter DEBUG logs contain operation/scope IDs, expected revision, row counts, policy versions, latency metadata, and status; WARN logs conflicts/idempotent repeats; ERROR logs stable adapter codes only. Enable SQL parameter hiding and never log statements with values, claims, memory content, relationship dimensions, DSNs, or exception text.
  - Dependencies: Tasks 6-7.

- [x] Task 9: Enforce architecture, privacy, emergence, and documentation requirements end to end.
  - Deliverable: Expand architecture rules so `social` is protected as a subjective layer; assert public-facade-only imports and the intentional persistence dependency; add unit/property/integration coverage for evidence, contradiction, decay, self-model development, asymmetric relationships, owner isolation, rollback, idempotency, deterministic ordering, and payload-safe logging. Update contributor and user documentation through the mandatory `/aif-docs` checkpoint.
  - Expected behavior: Tests prove repeated independent evidence forms beliefs, contradictory evidence revises them, reconstructed lineage is not double-counted, self-beliefs emerge from episodes, reverse relationships remain independent, no prohibited high-level social states exist, objective replay is unchanged, and logs contain no subjective payloads. `ruff`, `mypy`, import-linter/architecture tests, default unit tests, and opt-in PostgreSQL tests pass.
  - Files: `tests/architecture/boundary_checker.py`, `tests/architecture/test_boundary_checker.py`, `tests/architecture/test_import_boundaries.py`, `tests/architecture/test_memory_isolation.py`, `tests/architecture/test_cognitive_loop_isolation.py`, `tests/architecture/test_social_isolation.py` (new), `tests/unit/test_v1_memory_social_models.py`, `tests/unit/test_subjective_state_contracts.py`, `tests/unit/test_v1_memory_service_logging.py`, `README.md`, `docs/architecture.md`, `docs/cognition-runtime.md`, `docs/memory-reconstruction.md`, `docs/persistence.md`, `docs/configuration.md`, `docs/development.md`, `docs/physical-simulation.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`.
  - Logging requirements: Add caplog and AST/static checks that reject logging of belief components, self-model claims, relationship dimensions, memory/communication payloads, prompts, embeddings, SQL parameters, and payload-bearing exception text. Verification output may report command/status/count metadata only.
  - Dependencies: Tasks 1-8.

## Verification

- Run `uv run ruff check .` and the configured formatting check.
- Run `uv run mypy src tests/typecheck` (or the repository's canonical mypy target).
- Run the default unit and architecture suites, including the new semantic belief, self-model, relationship, serialization, logging, and boundary tests.
- Run Hypothesis properties for evidence permutation invariance, confidence bounds/decay, lineage deduplication, and reverse-relationship independence.
- Run opt-in PostgreSQL migration and subjective-state persistence/concurrency tests against a disposable database whose name contains `palimpsest_test`.
- Confirm migration head `0007`, metadata parity, downgrade behavior, and disjointness from `AUTHORITATIVE_TABLES`.
- Confirm existing replay determinism and event-hash tests are unchanged by subjective state.
- Run `/aif-docs` and verify all documented contracts, migration references, logging prohibitions, and architecture matrices match the implementation.
