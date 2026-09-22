# Implementation Plan: Agent Social Communication and Information Transmission

Branch: main
Created: 2026-09-21

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M3 — Cognition and Providers (in progress)"
Rationale: This feature completes the cognition-to-social-action path and connects communication to owner-scoped memory, beliefs, relationships, and analysis without weakening world authority.

## Scope and Invariants
- Preserve `WorldEngine` as the only objective mutation authority. An objective communication event proves only that an utterance was delivered, not that its content is true.
- Keep communication generation inside owner-scoped cognition. It may use only the current `Perspective`, reconstructed memories, semantic beliefs, goals, directed relationships, and confidence values; it must never receive or dereference `WorldEvent`, an event repository, replay state, another agent's memory, or private world state.
- Model source metadata as testimony with an explicit distinction between world-verified delivery fields and speaker-declared subjective lineage. A receiver may distrust, ignore, or reinterpret declared lineage.
- Store a fresh owner-scoped communicated trace for each receiver. Never copy or share the sender's `MemoryTrace`, reconstruction record, belief, or relationship state.
- Preserve a transitive transmission chain through opaque communication/event correlations and source-agent identifiers while retaining immediate speaker, hop count, content fingerprints, confidence-at-send, confidence-at-receipt, and per-hop distortion measurements.
- Keep the model domain-neutral: no rumor, myth, tradition, culture, role, morality, friend/enemy, or truth labels. Repeated retelling emerges from normal reconstruction, confidence policy, and communication selection.
- Do not log message text, structured claim contents, memory fragments, belief propositions, reconstruction narratives, prompts, provider output, or content fingerprints that could act as payload surrogates.

## Commit Plan
- **Commit 1** (after tasks 1-3): `feat: add governed social communication contracts`
- **Commit 2** (after tasks 4-6): `feat: integrate communication with subjective cognition`
- **Commit 3** (after tasks 7-9): `feat: persist and analyze social transmission`

## Tasks

### Phase 1: Communication Contracts and World Authority

- [x] Task 1: Define immutable structured communication and transmission-provenance contracts.

  Deliverable: Add a closed, Pydantic-free communication model shared by `Talk`, `Ask`, and `Tell`. Keep these three command variants explicit, but replace undifferentiated text-only payloads with bounded structured content that can represent ordinary conversation, a question, or testimony without encoding domain-specific rumor/culture categories. Add stable identifiers and metadata for the immediate source, optional parent communication correlation, ordered source-agent chain, hop count, sender confidence, source basis (`belief`, `reconstructed_memory`, `goal`, `relationship`, or unreferenced conversation), and canonical content fingerprint. Mark source basis and inherited chain data as speaker-declared; reserve event ID, actor, recipient, tick, and delivery outcome as world-verified fields. Enforce exact closed types, immutable ordered collections, chain continuity, bounded lengths, finite confidence, and no self/duplicate source-chain entries. Update public facades without allowing `world` to import `social`, `memory`, or cognition.

  Files: `src/world/communications.py` (new), `src/world/actions.py`, `src/world/events.py`, `src/world/observations.py`, `src/world/__init__.py`, `tests/unit/test_v1_action_commands.py`, `tests/unit/test_v1_world_events.py`.

  Logging requirements: Domain values remain log-free. Add safe `repr` output containing only IDs, action kind, hop count, confidence band, counts, and version/status metadata; never expose content, source record IDs beyond approved opaque correlations, or fingerprints. Log validation failures only at callers with stable reason codes.

  Dependencies: None.

- [x] Task 2: Enforce communication eligibility and private perception through one world-owned policy.

  Deliverable: Introduce a versioned communication eligibility policy under private world authority and use it consistently for admission and projection. Require a living sender, a distinct living recipient, compatible location/range, and the configured perception/visibility conditions at resolution time; fail closed if the recipient is absent or no longer reachable. Keep communication event-only, recipient-private, and visible on the next observation window. Do not auto-answer `Ask`, infer truth from `Tell`, mutate relationships, or deliver through the separate out-of-band inbox. Ensure cognition cannot bypass the rule by naming an unperceived entity and align planner feasibility with the same agent-facing evidence without importing private policy.

  Files: `src/world/models.py`, `src/world/_operations.py`, `src/world/_rules.py`, `src/world/_perception.py`, `src/world/_replay.py`, `src/simulation/actions.py`, `src/agents/cognition/deliberation.py`, `tests/unit/test_world_rules.py`, `tests/unit/test_world_engine_admission.py`, `tests/unit/test_world_perception.py`, `tests/unit/test_perception_event_isolation.py`.

  Logging requirements: At world/simulation boundaries log action kind, actor/recipient IDs, policy version, tick, accepted/rejected status, and stable eligibility reason code at DEBUG/WARN; do not log communication content, declared lineage payloads, or fingerprints. Preserve environment-controlled log levels.

  Dependencies: Task 1.

- [x] Task 3: Version communication serialization, persistence, and replay without breaking stored runs.

  Deliverable: Add a new event schema version for structured communication details and observation projection, update strict command/event/observation codecs and canonical event hashing, and preserve deterministic replay. Continue decoding accepted replay-v2/v3/v4 text-only communication records into an explicit legacy/unreferenced structured representation while writing only the new schema. Verify malformed lineage, unsupported kinds, forged world-owned metadata, and mixed schema versions fail closed. Keep communication events replay no-ops for world state.

  Files: `src/simulation/serialization.py`, `src/simulation/journal.py`, `src/simulation/persistence.py`, `src/simulation/replay.py`, `src/simulation/service.py`, `src/persistence/readers.py`, `tests/unit/test_v1_domain_serialization.py`, `tests/unit/test_persistence_serialization.py`, `tests/unit/test_simulation_replay_determinism.py`, `tests/integration/test_simulation_persistence_replay.py`.

  Logging requirements: Log schema/projector versions, record counts, event IDs, migration/compatibility path, and stable decode/replay reason codes at DEBUG/INFO/WARN. Never log serialized communication bodies, declared source chains, or canonical payload bytes.

  Dependencies: Tasks 1 and 2.

<!-- Commit checkpoint: tasks 1-3 -->

### Phase 2: Receiving, Remembering, and Communicating

- [x] Task 4: Capture received communication as fresh owner-scoped memory with transmission provenance.

  Deliverable: Add a production cognition memory-update policy that converts each owned `ObservedCommunication` into a newly constructed `MemoryTrace` for the listener. Preserve immediate speaker, world-verified source event/tick, speech action, parent communication correlation, declared source-agent chain, hop count, sender confidence, receiver confidence, and content fingerprint in explicit communicated provenance metadata. Build concepts/entities/relations from the received structured content without copying any sender memory/reconstruction ID as an owned lineage parent. Deduplicate by observed communication ID, keep writes deferred until cognition succeeds, and compose this policy with existing reconstruction and subjective revision hooks instead of moving memory formation into perception.

  Files: `src/memory/models.py`, `src/agents/cognition/communication.py` (new), `src/agents/cognition/defaults.py`, `src/agents/cognition/models.py`, `src/agents/cognition/__init__.py`, `src/simulation/agent_runtime.py`, `tests/unit/test_v1_episodic_memory_cognition.py`, `tests/unit/test_agent_runtime.py`, `tests/unit/test_memory_reconstruction_drift.py`.

  Logging requirements: Log owner ID, tick, communication/event ID, immediate source ID, action kind, hop count, confidence bands, deduplication result, and proposed/applied counts at DEBUG; log ownership or malformed-chain rejection with reason codes at WARN/ERROR. Never log text, concepts, relations, narratives, or fingerprints.

  Dependencies: Tasks 1 and 3.

- [x] Task 5: Generate `talk`, `ask`, and `tell` from the speaker's subjective state.

  Deliverable: Extend imagination/deliberation planning with a deterministic, replaceable social-message policy. `talk` may express a goal- or relationship-relevant conversational act; `ask` must arise from an information need, uncertainty, goal, or unresolved belief; `tell` must be grounded in the speaker's selected semantic belief or reconstructed memory evidence. Carry selected source references through cognition artifacts so the planner can construct declared lineage and confidence without accessing objective events. Permit retelling only from the speaker's own communicated trace/reconstruction and append the new sender/hop instead of copying the source trace. Select recipients only from currently allowed perceived counterparts, produce exactly one fresh closed `AgentCommand`, and fall back safely when no eligible target or grounded content exists. Provide policy ports/fakes so future LLM-backed wording remains structured, validated, and non-authoritative.

  Files: `src/agents/cognition/models.py`, `src/agents/cognition/contracts.py`, `src/agents/cognition/imagination.py`, `src/agents/cognition/deliberation.py`, `src/agents/cognition/communication.py`, `src/agents/cognition/defaults.py`, `src/agents/cognition/__init__.py`, `tests/unit/test_action_planner.py`, `tests/unit/test_cognitive_loop.py`, `tests/unit/test_subjective_snapshot_intents.py`, `tests/fakes/cognition.py`.

  Logging requirements: Log policy version, owner/recipient IDs, selected action kind, source-basis kind, candidate counts, hop count, confidence band, fallback flag, and stable rejection/tie-break codes at DEBUG/WARN. Do not log generated wording, beliefs, memory fragments, reconstruction narratives, goals, relationship values, or fingerprints.

  Dependencies: Tasks 1, 2, and 4.

- [x] Task 6: Apply trust-, confidence-, context-, and hop-aware belief updates without treating testimony as fact.

  Deliverable: Extend communicated evidence evaluation so a receiving agent always retains the observation/memory trace but may accept, discount, contradict, or defer semantic-belief revision according to a versioned policy using sender-declared confidence, receiver confidence, directed trust and trust-confidence, context relevance, corroboration/contradiction, and hop attenuation. Snapshot the applied factors and resulting confidence delta in belief evidence metadata for auditability. Keep memory independent of `social`: cognition must project the required relationship inputs into neutral policy values. Generic communication may increase familiarity, but trust must change only from explicit corroboration/contradiction or other existing evidence-backed interaction signals; do not equate repetition with independent support, and deduplicate reports sharing the same transmission root.

  Files: `src/memory/beliefs.py`, `src/memory/belief_formation.py`, `src/social/relationships.py`, `src/agents/cognition/communication.py`, `src/agents/cognition/defaults.py`, `src/agents/cognition/models.py`, `src/simulation/subjective_state.py`, `tests/unit/test_semantic_belief_formation.py`, `tests/unit/test_semantic_belief_service.py`, `tests/unit/test_subjective_relationships.py`, `tests/unit/test_subjective_state_service.py`.

  Logging requirements: Log owner/source IDs, policy versions, hop count, trust/confidence bands, evidence counts, decision (`accept`, `discount`, `contradict`, or `defer`), confidence delta band, deduplication root count, and commit status at DEBUG/INFO. Never log propositions, evidence content, relationship payloads, or exact content fingerprints.

  Dependencies: Tasks 4 and 5.

<!-- Commit checkpoint: tasks 4-6 -->

### Phase 3: Durability, Measurement, and Scenarios

- [x] Task 7: Persist communicated provenance and confidence history atomically.

  Deliverable: Add migration `0008` and SQLAlchemy mappings for transmission metadata on memory traces and belief evidence, including immediate source, parent communication correlation, ordered source chain, hop count, action kind, confidence-at-send/receipt, transmission-root correlation, and applied confidence factors/delta. Update in-memory and PostgreSQL adapters, subjective serialization, analysis evidence loading, transaction fingerprints, idempotency, and rollback behavior. Keep subjective records outside authoritative event history, preserve owner isolation, and reject cross-owner memory lineage even when communication source metadata references another agent.

  Files: `alembic/versions/0008_social_transmission_provenance.py` (new), `src/persistence/memory_orm.py`, `src/persistence/memory_sqlalchemy.py`, `src/persistence/subjective_orm.py`, `src/persistence/subjective_sqlalchemy.py`, `src/persistence/analysis_sqlalchemy.py`, `src/simulation/subjective_serialization.py`, `src/simulation/subjective_state.py`, `tests/integration/test_migrations.py`, `tests/integration/test_episodic_memory_pgvector.py`, `tests/integration/test_subjective_state_persistence.py`, `tests/integration/test_memory_concurrency.py`.

  Logging requirements: Log migration/schema version, run/owner IDs, operation IDs, row/count metadata, hop ranges, idempotency, transaction boundaries, and stable failure/rollback codes at DEBUG/INFO/ERROR. Never log communication payloads, memory content, belief claims, source-chain payloads, or fingerprints.

  Dependencies: Tasks 3, 4, and 6.

- [x] Task 8: Add read-only rumor-propagation and cross-hop distortion analysis.

  Deliverable: Add immutable analysis DTOs and a service that joins communication events with communicated traces/reconstructions after the fact to build transmission graphs. Report transmission root, ordered source chain, unique agents reached, branch/fan-out counts, maximum and per-record hop counts, timing, per-hop structured additions/losses/changes, cumulative distortion, sender/receiver confidence and deltas, provenance continuity, and unresolved/forged declared links. Derive metrics generically from communication and memory evidence; do not define rumor/myth/tradition categories and never feed analysis results back into live cognition. Extend persistence evidence loaders only through public read-only contracts.

  Files: `src/analysis/social_transmission.py` (new), `src/analysis/models.py`, `src/analysis/contracts.py`, `src/analysis/sources.py`, `src/analysis/__init__.py`, `src/persistence/analysis_sqlalchemy.py`, `tests/unit/test_social_transmission_analysis.py` (new), `tests/integration/test_social_transmission_analysis_persistence.py` (new), `tests/architecture/test_analysis_isolation.py`.

  Logging requirements: Log experiment/run IDs, metric/projector versions, event/trace/node/edge counts, maximum hop, unresolved-link counts, and completion/failure status at DEBUG/INFO/WARN. Never log message bodies, memory facts, narratives, propositions, or fingerprints.

  Dependencies: Tasks 3, 4, and 7.

- [x] Task 9: Prove multi-agent spreading, distortion, privacy, and boundaries with deterministic scenarios and documentation.

  Deliverable: Add an in-memory Alice -> Bob -> Carol scenario that begins with Alice's direct observation, records Alice's owner-scoped memory and reconstruction, emits a grounded `Tell`, records Bob's communicated trace, applies configurable trust-weighted belief handling, reconstructs with deterministic distortion, retells to Carol, and verifies the complete transmission chain without shared memories. Cover all `talk`/`ask`/`tell` actions; denied remote/dead/invisible recipients; next-tick private delivery; no bystander leakage; no automatic answer or belief update; low/high trust outcomes; repeated reports from one root not counting as independent corroboration; per-hop confidence changes; gradual scripted distortion; deterministic replay; persistence round trips; malformed/forged lineage rejection; and payload-free logs. Add Hypothesis coverage for bounded hop/distortion schedules and architecture tests forbidding cognition/memory access to objective event stores. Update contributor-facing architecture and memory documentation, including the distinction between objective delivery, declared testimony, owner-scoped derivation, and read-only analysis.

  Files: `tests/integration/test_multi_hop_communication_memory.py` (new), `tests/unit/test_v1_memory_property.py`, `tests/unit/test_perception_event_isolation.py`, `tests/architecture/test_cognitive_loop_isolation.py`, `tests/architecture/test_memory_isolation.py`, `tests/architecture/test_world_authority.py`, `tests/architecture/test_social_isolation.py`, `tests/architecture/boundary_checker.py`, `docs/architecture.md`, `docs/memory-reconstruction.md`, `docs/social-communication.md` (new), `README.md` if its feature index requires an entry.

  Logging requirements: Capture and assert only metadata allowlists: run/owner/source IDs, ticks, action kinds, policy/schema versions, counts, hop numbers, confidence bands/deltas, status, and reason codes. Add negative assertions that message text, memory concepts/relations, belief propositions, reconstruction narratives, prompts, raw provider output, and fingerprints never appear in logs.

  Dependencies: Tasks 2 through 8.

<!-- Commit checkpoint: tasks 7-9 -->

## Verification
- Run `uv run ruff check .` and `uv run ruff format --check .`.
- Run `uv run mypy src tests` using the repository's configured target if the command differs.
- Run the default unit and architecture suites, including the new communication, provenance, trust, property, replay, and log-redaction cases.
- Run opt-in PostgreSQL integration tests for migration `0008`, subjective-state persistence, replay compatibility, and transmission analysis evidence loading.
- Verify deterministic results under identical seeds and scripted reconstruction edits, with no global RNG or wall-clock domain defaults.
- Verify old replay-v2/v3/v4 records still decode/replay and new writes use only the new event schema.
- Verify every agent-facing path receives only its owned observation, memories, beliefs, goals, relationships, and reconstructed evidence; objective event joins occur only under `analysis`.
- Run `/aif-docs` as the mandatory documentation checkpoint after implementation.
