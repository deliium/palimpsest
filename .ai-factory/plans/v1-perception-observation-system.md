# Implementation Plan: Perception and Observation System

Branch: main (no new branch requested)
Created: 2026-09-21

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M3 - Cognition and Providers"
Rationale: Agent-specific, authority-safe observations are the required input boundary for concrete cognition policies and provider adapters.

## Goal

Introduce a deterministic `PerceptionService` that converts objective world state and committed occurrences into one immutable, agent-specific `Observation` per tick. Cognition must be able to make decisions from its own observation without receiving `WorldState`, another agent's observation, raw objective events, or hidden remote facts.

The service must account for observer location, nearby entities, effective visibility, day/night, weather, direct participation, and delivered communication. It may omit or redact unavailable facts, but it must never invent facts, reinterpret a communication as truth, or perform memory distortion.

## Design Decisions

- Keep the authority-facing service private as `world._perception.PerceptionService`, instantiated by `WorldEngine`. Only this private world module and approved simulation authority code may pass `WorldState`; the public surface exports observation DTOs, not the service's authority inputs.
- Replace full objective models in agent-facing collections where they expose non-perceptible policy fields with dedicated frozen, slotted projections such as observed location, item, resource, weather, body, event, and communication values. Exact self physiology may remain available through an explicit self projection, but other bodies remain coarse and never expose inventory or exact needs.
- Produce observations from the immutable tick-start snapshot. An observation for tick `N` may include redacted occurrences committed during tick `N-1`; it must never include submissions or outcomes from the still-open tick.
- Add explicit occurrence context to replayable objective events rather than inferring witnesses from `target_id` or the post-tick state. Context must distinguish origin, destination, affected entity, and private recipient as applicable. Version and persist this metadata so live and restored engines produce the same observations.
- Project events by audience: direct actors and targets receive suitably redacted participation details; visible local bystanders receive only public action facts; remote or low-visibility observers receive nothing; private communication text is delivered only to the intended recipient and sender unless a future explicit overhearing policy is added.
- Represent communication as an observed utterance with source event provenance: “entity A communicated text X to entity B.” The perception layer does not assert that X is true and does not create `MemoryTrace` or `Belief` values.
- Use narrow provenance containing the source kind and stable event/tick correlation useful to cognition and deduplication. Do not expose request IDs, system cause IDs, hidden actor/target identities, global event counts, or raw replay payloads merely for provenance.
- Preserve deterministic registration and event ordering. Repeated `observe()` calls during one open tick return equal values, and equivalent live/replayed engines issue equal observations.
- Keep pure projection code log-free. Orchestration logs only safe counts, tick/revision, visibility bands, projection decisions by stable reason code, and failures; it never logs observation contents, communication text, memories, private state, or hidden identifiers.

## Non-Goals

- Memory encoding, forgetting, confabulation, belief formation, or any other cognitive distortion.
- Deciding whether communicated claims are true.
- Adding LLM providers or concrete cognition policies.
- Runtime sandboxing against hostile Python reflection; architecture and typed orchestration boundaries remain the supported isolation mechanism.
- Adding an overhearing, sound propagation, or long-range messaging policy beyond direct delivered communication.
- Exposing `WorldState`, `World`, private projectors, objective event payloads, or all-agent observation batches to cognition strategies.

## Commit Plan
- **Commit 1** (after tasks 1-3): `feat(world): define agent-specific perception contracts`
- **Commit 2** (after tasks 4-6): `feat(simulation): integrate deterministic observation delivery`
- **Commit 3** (after tasks 7-9): `test(world): prove hidden information isolation`

## Tasks

### Phase 1: Contracts and Perception Policy

- [x] Task 1: Define the complete agent-facing observation vocabulary and visibility matrix.
  - Deliverable: Refine `Observation` into an immutable tick-scoped contract with dedicated redacted projections for self, nearby agents, current location/exits, visible items/resources, weather/time, observed actions/events, and delivered communications. Add closed provenance/source types and validation for observer ownership, source tick/revision, deterministic ordering, duplicate source IDs, and partial fields. Document, in code and tests, which fields are always self-known, visibility-gated, participant-only, recipient-only, or omitted. Do not reuse objective models when they expose capacities, regeneration settings, exact remote physiology, or placement facts that the policy does not grant.
  - Files: `src/world/observations.py`, `src/world/__init__.py`, `tests/unit/test_world_agent_contracts.py`, `tests/unit/test_world_perception.py`, `tests/typecheck/v1_domain_contracts.py`.
  - Logging: Observation values and validators remain log-free. Validation errors use stable field-oriented messages without embedding communication text or arbitrary payloads.
  - Dependencies: None. This contract anchors tasks 2-9.

- [x] Task 2: Add durable occurrence context required for event audience decisions.
  - Deliverable: Extend pending and committed event construction with explicit event-time context sufficient to determine origin/destination witnesses, direct participants, affected entities, and private recipients without consulting a later state. Introduce the next replay schema version, preserve decoding/replay support for existing versions, define canonical bytes and target semantics, and ensure system events carry only the context needed for perception. Never overload `WorldEvent.target_id` as an occurrence location. Include communication privacy metadata while keeping text in its existing objective detail payload.
  - Files: `src/world/events.py`, `src/world/effects.py`, `src/world/_operations.py`, `src/world/_rules.py`, `src/world/_physical.py`, `src/world/_replay.py`, `tests/unit/test_v1_world_events.py`, `tests/unit/test_event_projection.py`, `tests/unit/test_world_batch.py`.
  - Logging: World rule, event construction, and replay projection remain pure and log-free. Stable schema/context validation codes may be logged by simulation orchestration at ERROR without event details or text.
  - Dependencies: Depends on task 1 for the audience vocabulary; blocks event projection and durable replay work.

- [x] Task 3: Implement `PerceptionService` as the sole objective-to-subjective projector.
  - Deliverable: Replace the function-only projection boundary with a deterministic private `PerceptionService` that receives one world snapshot, ordered observer IDs, physical context, and the immediately preceding committed event window. Produce exactly one detached `Observation` per observer. Apply location and effective-visibility rules consistently across agents, ground items, resources, public events, and deaths; retain self/inventory and explicitly always-available environmental fields according to the matrix; redact event fields by audience; and emit direct communications as claims with provenance. Hidden input changes must not affect an observer's output, and no missing fact may be synthesized.
  - Files: `src/world/_perception.py`, optionally `src/world/_event_perception.py`, `src/world/observations.py`, `tests/unit/test_world_perception.py`, `tests/unit/physical/test_physical_projection.py`.
  - Logging: The service and helper projectors remain log-free and deterministic. Return safe projection statistics/reason codes only if the engine needs them for DEBUG diagnostics; never return raw hidden values for logging.
  - Dependencies: Depends on tasks 1 and 2.

### Phase 2: Tick, Cognition, and Durable Delivery

- [x] Task 4: Integrate per-agent perception into the world-engine tick lifecycle.
  - Deliverable: Make `WorldEngine.observe()` delegate all projection to `PerceptionService`, supplying only the current tick-start snapshot and committed tick `N-1` occurrence window. Carry the prior committed window in the immutable engine candidate/snapshot, including eventless ticks, and preserve atomic rollback, open-tick idempotence, deterministic observer order, and the rule that current-tick outcomes cannot appear early. Add explicit agent-addressed access or a trusted routing API so normal orchestration can retrieve one registration's observation without handing an all-agent batch to cognition.
  - Files: `src/simulation/engine.py`, `src/simulation/lifecycle.py`, `src/simulation/bootstrap.py`, `src/simulation/__init__.py`, `tests/unit/test_world_engine.py`, `tests/unit/test_world_engine_admission.py`.
  - Logging: Add DEBUG logs for tick/revision, observer count, prior-event count, visible/redacted event counts, visibility bands, and cache replay; INFO remains limited to tick commits; WARN covers routing/lifecycle misuse; ERROR covers projection invariants. Never log observation payloads, communication text, private state, or recipient inbox contents.
  - Dependencies: Depends on task 3.

- [x] Task 5: Make the cognition assembly boundary enforce observation ownership.
  - Deliverable: Add or tighten a trusted perspective/input factory that uses `RegistrationTranslator` to pair one `AgentId` with exactly its registered `EntityId` observation. Reject cross-agent observations and misaddressed communication envelopes before invoking `CognitionStrategy.propose()`. Keep memories and beliefs as separate subjective inputs, define whether the existing social `inbox` is strictly out-of-band or derived from observed communications, and prevent duplicate delivery semantics. Add type-level examples proving cognition requires `Observation`/`Perspective` and has no `WorldState`, `World`, engine snapshot, event batch, or all-agent observation batch parameter.
  - Files: `src/agents/cognition/contracts.py`, `src/agents/cognition/__init__.py`, `src/simulation/bootstrap.py`, `src/simulation/lifecycle.py`, optionally `src/simulation/perception.py`, `src/social/models.py`, `tests/unit/test_cognition_strategies.py`, `tests/unit/test_subjective_state_contracts.py`, `tests/typecheck/cognition_strategies.py`, `tests/typecheck/invalid/`.
  - Logging: Perspective values remain log-free. Trusted orchestration logs DEBUG agent/entity correlation success by safe stable IDs and WARN/ERROR ownership failures by reason code only; never log observations, memories, beliefs, inbox payloads, or communication text.
  - Dependencies: Depends on tasks 1 and 4.

- [x] Task 6: Version observation serialization and preserve live/replay parity.
  - Deliverable: Replace the currently lossy observation codec with a versioned, exact-key round trip for every observation field and provenance type. Persist the new occurrence context and repair the SQL event adapter so required event cause/context data survive round trips. Add the required ORM/Alembic migration, journal codec updates, snapshot/checkpoint handling, and replay loading window so a restored engine at tick `N` emits the same observation as a live engine, including the prior eventless or eventful tick. Existing event schema versions remain readable according to explicit compatibility rules and never gain fabricated context.
  - Files: `src/simulation/serialization.py`, `src/simulation/journal.py`, `src/simulation/persistence.py`, `src/simulation/replay.py`, `src/persistence/orm.py`, `src/persistence/readers.py`, `src/persistence/sqlalchemy.py`, `alembic/versions/`, `tests/unit/test_v1_domain_serialization.py`, `tests/unit/test_checkpoint_restoration.py`, `tests/unit/test_replay_service.py`, `tests/integration/`.
  - Logging: Codecs and domain migrations remain log-free. Persistence/replay orchestration logs DEBUG schema/cursor/count metadata, INFO successful migration/restore milestones, and ERROR stable failure codes; encoded observations, event details, text, and database credentials are forbidden.
  - Dependencies: Depends on tasks 2 and 4.

### Phase 3: Isolation Proofs and Completion

- [x] Task 7: Prove physical visibility, redaction, and noninterference.
  - Deliverable: Build parameterized and Hypothesis tests covering location, every weather condition, day/night boundary hours, visibility below/at/above the threshold, nearby/remote agents, held/ground/remote items, local/remote resources, exits, self knowledge, dead observers, and coarse health bands. Add paired-state noninterference tests: changing only hidden remote state or hidden fields of a nearby entity must leave the complete observation and canonical serialized bytes unchanged. Assert other agents' inventory, exact physiology, resource regeneration/capacity, remote weather/topology, and hidden identifiers cannot be recovered from public observation types.
  - Files: `tests/unit/test_world_perception.py`, `tests/unit/physical/test_physical_projection.py`, `tests/unit/physical/test_physiology.py`, `tests/unit/test_world_agent_contracts.py`, `tests/unit/test_v1_domain_serialization.py`, `tests/unit/determinism_helpers.py`.
  - Logging: Tests assert projection remains log-free and capture engine logs to prove DEBUG diagnostics contain counts/reason codes only, with no hidden values, observation reprs, or communication payloads.
  - Dependencies: Depends on tasks 3 and 6.

- [x] Task 8: Prove event, communication, routing, determinism, and authority isolation.
  - Deliverable: Test actors, direct targets, origin/destination witnesses, visible bystanders, remote observers, and low-visibility observers for representative movement, transfer, combat/help, death, weather/resource, needs/exposure, and communication events. Verify partial event fields, private recipient-only text, “claim not truth” semantics, next-tick delivery, no rejected/duplicate/conflicted action event, eventless windows, idempotent repeated observe, no cross-agent batch routing, and live-versus-restored equality. Expand AST/import-linter checks so agents, cognition, memory, social, LLM, API, and analysis cannot import `WorldState`, private perception, or authority-bearing routing types, while approved engine/private-world imports remain narrow.
  - Files: `tests/unit/test_world_perception.py`, `tests/unit/test_world_engine.py`, `tests/unit/test_cognition_strategies.py`, `tests/unit/test_replay_service.py`, `tests/unit/test_checkpoint_restoration.py`, `tests/unit/test_simulation_replay_determinism.py`, `tests/architecture/boundary_checker.py`, `tests/architecture/test_boundary_checker.py`, `tests/architecture/test_world_authority.py`, `tests/architecture/test_import_boundaries.py`, `pyproject.toml`.
  - Logging: Capture DEBUG/INFO/WARN/ERROR behavior for projection, routing, restore, and misuse paths; assert `PALIMPSEST_LOG_LEVEL` controls verbosity and that logs omit event text, observations, memories, private state, and hidden identities. Architecture checks themselves remain log-free.
  - Dependencies: Depends on tasks 4-7.

- [x] Task 9: Document the perception boundary and complete all project gates.
  - Deliverable: Run the mandatory `$aif-docs` checkpoint to document objective `WorldState` versus subjective `Observation`, the visibility/audience matrix, event timing, partial-information and provenance semantics, communication-as-claim behavior, cognition routing, replay guarantees, and the explicit boundary with memory distortion. Update project architecture artifacts if public contracts or dependency rules change, then run formatting, lint, type, unit/property, architecture, serialization, migration, and opt-in persistence checks.
  - Files: `README.md`, `docs/architecture.md`, `docs/physical-simulation.md`, `docs/development.md`, `docs/persistence.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`.
  - Logging: Documentation records the safe structured logging policy and diagnostic levels. Verification includes assertions that no test or production log emits observations, communications, memories, credentials, or private world state.
  - Dependencies: Depends on tasks 1-8.

## Verification Commands

```bash
uv sync --frozen --python 3.12.14
uv run --frozen --python 3.12.14 ruff format --check src tests
uv run --frozen --python 3.12.14 ruff check src tests
uv run --frozen --python 3.12.14 mypy src tests
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term-missing
uv run --frozen --python 3.12.14 lint-imports --config pyproject.toml --no-cache --no-logo
uv run --frozen --python 3.12.14 pytest -m integration
```

## Acceptance Criteria

- Every registered agent receives exactly one immutable observation for each observed tick, and repeated reads in the same open tick are equal.
- No cognition protocol, perspective builder, observation type, serialization path, or agent-facing facade accepts or returns `WorldState`, `World`, engine snapshots, private projectors, raw `WorldEvent`, or another agent's observation.
- Agent, item, resource, weather, location, and action/event availability follows the documented location, day/night, weather, and visibility matrix.
- Direct participants receive permitted partial information; visible bystanders receive only public local facts; remote and low-visibility observers receive no hidden event identity, payload, or event-count side channel.
- Delivered communication appears with explicit source provenance and claim semantics only. Perception creates no memories or beliefs and never treats message content as objective truth.
- Dedicated observation DTOs expose no exact remote physiology, other-agent inventory, hidden placement, remote weather/topology, private resource policy, authority IDs, or replay payloads.
- Objective events contain enough versioned occurrence context to reproduce audience decisions without guessing from `target_id` or post-tick state.
- Observation serialization is complete and canonical; persisted and restored engines emit the same next observation as live engines across eventful and eventless ticks.
- Paired-state noninterference tests prove that changes confined to hidden world information do not change an agent's observation or serialized observation bytes.
- Architecture, typing, and routing tests prove cognition receives only its own observation plus explicitly separate subjective inputs.
- Projection remains deterministic and log-free; orchestration logging is configurable, structured, and contains no observations, event/communication text, memories, credentials, or private world state.
- Ruff, mypy, unit/property tests, architecture/import checks, serialization tests, and persistence integration tests pass.
