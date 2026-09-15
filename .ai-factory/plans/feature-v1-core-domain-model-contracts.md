# Implementation Plan: V1 Core Domain Model and Contracts

Branch: feature/v1-core-domain-model-contracts
Created: 2026-09-15

## Settings

- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage

Milestone: "M2 — Simulation Loop"
Rationale: These typed domain contracts, trust stages, and immutable event schemas are prerequisites for implementing M2 action resolution and perception without leaking world authority.

## Goal

Implement the V1 contracts-first domain model for a reproducible multi-agent simulation. Define strongly typed objective and subjective state, a closed action vocabulary, explicit promotion from agent command to validated world operation, immutable resulting events, stable identifiers, and strict versioned serialization without adding a tick loop or behavioral simulation rules.

## Architectural Decisions

- Keep `World` and `WorldState` in the private `world` authority surface. `World` owns a `WorldId` and the current immutable, revisioned `WorldState`; agents and cognition receive only immutable `Observation` values. `WorldState(WorldRevision(0))` remains valid for existing unscoped tests, while production admission is scoped by the owning `World`.
- Keep objective `AgentBody` state in `world` and subjective `Agent` identity, goals, memories, beliefs, and relationships in their existing bounded packages. Preserve explicit `AgentId` to `EntityId` translation at the simulation boundary.
- Use frozen, slotted standard-library dataclasses, `StrEnum`, `Literal` discriminators, tuples, and defensively detached mappings. Do not use FastAPI, Pydantic, ORM, or LLM-provider types in domain models.
- Retain `EntityId` as the opaque stable identity shared by physical world entities, including bodies, locations, items, and resources. `Weather` is a location-bound value, not a separately identified entity. Add stable aggregate and subjective IDs where no existing identifier applies. Constructors remain available for explicit decoding/tests; production creation uses deterministic purpose-specific simulation factories.
- All ID wrappers accept only exact `str` values of 1-128 Unicode code points, reject leading/trailing whitespace and control characters, preserve accepted values verbatim without normalization, and use `ValueError` for invalid values. `WorldRevision` accepts only non-boolean `int >= 0`.
- Use one closed immutable content grammar for serializable metadata: `None`, `bool`, signed 64-bit integers, finite floats, valid Unicode strings without surrogate code points, tuples of allowed values, and immutable mappings with string keys and allowed values. Reject bytes-like values, sets, non-string keys, out-of-range/non-finite numbers, and arbitrary/custom objects at model construction.
- Replace the generic action `kind` and payload escape hatch with separate nominal types for agent commands, non-authoritative proposals/requests, private validated operations, and resulting event details. Only a private operation produced by world validation is authority-bearing.
- Keep validation limited to type invariants, required fields, finite/ranged scalar values, identity distinctions, explicit revision binding, discriminator exhaustiveness, and strict wire shape. Defer reachability, ownership, consumption effects, combat, social permission, resource depletion, scheduling, and all other action-resolution policy.
- Use a dedicated integer wire schema version `1`, independent of deterministic ID derivation version. One simulation-layer adapter serializes an explicit allowlist of immutable public values; it never decodes `ActionRequest`, `World`, `WorldState`, private operations, validators, transitions, stores, gateways, or protocols.
- Replace `AgentState` with `Agent` and `MemoryRecord` with `MemoryTrace` as the canonical V1 public contracts, updating all internal callers and tests in the same commit. Preserve existing public names only where they remain semantically correct (`Belief`, `Observation`, `WorldEvent`, `ActionProposal`, `ActionRequest`).

## Scope Exclusions

- No simulation tick loop, scheduler, resolver policy, pathfinding, perception algorithm, weather progression, metabolism, resource regeneration, inventory capacity, combat calculation, or social behavior.
- No direct LLM parsing, provider adapter, prompt, FastAPI endpoint, persistence schema, Alembic migration, or ORM mapping.
- No implicit IDs, UUID or wall-clock defaults, global randomness, Python `hash()`, or operational request/log identifiers in domain identity.
- No logging from pure domain values, validators, codecs, deterministic ID functions, or package imports. Verbose diagnostics belong only to future orchestration/adapters and must omit action text, observations, memories, beliefs, and full world state.

## Commit Plan

- **Commit 1** (after tasks 1-4): `feat: add v1 domain entities and subjective models`
- **Commit 2** (after tasks 5-8): `feat: define closed action admission operation and event contracts`
- **Commit 3** (after tasks 9-11): `feat: add v1 serialization tests and documentation`

## Tasks

### Phase 1: Identity and State Models

- [x] Task 1: Complete stable identifier and scalar value contracts
  - Deliverable: Consolidate world envelope IDs (`ProposalId`, `RequestId`, `EventId`) in `world.identifiers`; add `WorldId`, `GoalId`, and `RelationshipId`; and retain `EntityId`, `AgentId`, `MemoryId`, `BeliefId`, `EnvelopeId`, and `RunId` as nominally distinct wrappers. Apply the exact shared ID rule from Architectural Decisions and integer-only `WorldRevision`. Define `Health`, `Hunger`, `Thirst`, and `Fatigue` as finite canonical floats in `[0.0, 100.0]` (`0` health is terminal; `0` hunger/thirst/fatigue means no need and `100` means maximum need), and `TemperatureCelsius` as any finite canonical float; reject booleans and normalize `-0.0` to `0.0`. Add typed deterministic factories for world/entity/proposal/request/event/goal/relationship/memory/belief/envelope IDs using fixed internal purpose tags plus scheduling-independent canonical keys. Keep existing `derive_run_id` and `derive_scoped_id` bytes/golden vectors unchanged.
  - Files: `src/world/identifiers.py`, `src/world/actions.py`, `src/world/events.py`, `src/world/values.py`, `src/agents/models.py`, `src/memory/models.py`, `src/social/models.py`, `src/simulation/models.py`, `src/simulation/identifiers.py`, affected package `__init__.py` files, `tests/unit/test_v1_stable_identifiers.py`, `tests/unit/test_v1_domain_values.py`, `tests/unit/test_reproducibility_contracts.py`, `tests/unit/test_world_agent_contracts.py`.
  - Expected behavior: Important entities and envelopes have explicit stable IDs; equal raw strings in different wrappers remain distinct types; whitespace/control/oversized/non-string IDs, non-integer revisions, and invalid scalar values fail predictably; same canonical inputs produce stable IDs while purpose namespaces and ambiguous component boundaries cannot alias.
  - Logging requirements: Constructors and deterministic factories emit no logs. Future orchestration callers may log only ID type, safe opaque ID, derivation version, and validation stage at DEBUG; never log seeds alongside generated IDs, operational IDs, or entity content.
  - Dependencies: None.

- [x] Task 2: Define immutable objective world entity models and agent physical state
  - Deliverable: Add frozen models with exact minimum schemas: `Location(entity_id, name)`, `Item(entity_id, name, location_id | holder_id)` with exactly one placement, `Resource(entity_id, name, location_id, quantity, unit)` with finite non-negative quantity, `Weather(location_id, condition, temperature)`, and `AgentBody(entity_id, location_id, health, hunger, thirst, fatigue, temperature, inventory, life_status)`. `AgentBody` contains no `AgentId`; `LifeStatus.ALIVE` requires positive health and `DEAD` requires zero health, while hunger/thirst/fatigue do not imply death. Ordered sequence inputs are copied to tuples with order preserved; sets/unordered iterables and duplicates are rejected. Add the closed immutable content grammar used by all metadata-bearing V1 models and tighten `world._freeze` to reject unsupported values rather than passing custom objects through.
  - Files: `src/world/_freeze.py`, `src/world/models.py`, `src/world/values.py`, `src/world/__init__.py`, `tests/unit/test_v1_world_models.py`, `tests/unit/test_v1_domain_values.py`.
  - Expected behavior: Physical values are immutable, runtime validated, detached, and serialization-closed; each item has one authoritative placement; inventory order is deterministic and caller-preserved; objective models do not import agents, FastAPI, Pydantic, persistence, or provider code.
  - Logging requirements: Pure world models and validators emit no logs. Callers may log model type, entity ID, and validation result at DEBUG, but never inventory contents, full body state, or location/resource details.
  - Dependencies: Task 1.

- [x] Task 3: Extend private `World` and `WorldState` authority contracts and typed observations
  - Deliverable: Introduce private mutable `World(world_id, initial_state)` as the sole holder/replacer of an immutable `WorldState`. Extend `WorldState(revision, *, locations=(), items=(), resources=(), bodies=(), weather=())` so the existing revision-only constructor remains valid; build read-only indexes from ordered iterables and reject globally duplicate physical `EntityId`s, key/model mismatches, dangling locations/items, duplicate inventory ownership, and disagreement between `Item.holder_id` and body inventory. Define exactly one weather value per referenced location when weather is supplied. Replace generic `Observation.payload` with `Observation(world_id, observer_id, revision, self_body, locations, items, resources, weather)` typed partial projections; partial observations need only reference values included or the observer's known context, not satisfy full authority graph completeness. Retain `detached_mapping` only as the shared constrained-content helper needed by memory/social during migration. Add `World` to authority symbol/module tests immediately.
  - Files: `src/world/_state.py`, `src/world/observations.py`, `src/world/__init__.py`, `tests/unit/test_v1_world_state.py`, `tests/unit/test_world_agent_contracts.py`, `tests/unit/test_cognition_strategies.py`, `tests/architecture/test_world_authority.py`.
  - Expected behavior: `World` scopes revisions to a stable world identity and exposes immutable replacement snapshots; authoritative graphs are structurally coherent; observations are typed, partial, detached, and cannot mutate or expose authority; no transition or progression policy is introduced.
  - Logging requirements: Authority values and snapshot creation emit no logs. Future simulation orchestration may log world ID, revision, entity counts, and snapshot stage at DEBUG; never log full state or observation content.
  - Dependencies: Tasks 1-2.

- [x] Task 4: Complete agent, goal, memory, belief, and relationship models
  - Deliverable: Replace `AgentState` with immutable `Agent(agent_id, name, goals)` and define `Goal(goal_id, owner_id, description, priority, status)` with verbatim nonblank bounded text, priority `[0.0, 1.0]`, and a closed status enum. Replace `MemoryRecord` with `MemoryTrace(memory_id, owner_id, world_revision, content)`; strengthen `Belief(belief_id, owner_id, proposition, confidence, evidence_memory_ids)` with confidence `[0.0, 1.0]`; and add constructor-only directed `Relationship(relationship_id, source_id, target_id, kind, affinity)` that rejects self-links and uses finite affinity `[-1.0, 1.0]`. Update memory stores/protocols to tuple snapshots, explicit last-write-wins replacement by equal ID, insertion-order preservation, owner checks, and the closed content grammar. Normalize all existing/new `Perspective` sequences to tuples, validate memory/belief/goal ownership, and keep concrete memory/social values out of `Agent` except goals owned by `agents`.
  - Files: `src/agents/models.py`, `src/agents/__init__.py`, `src/agents/cognition/contracts.py`, `src/memory/models.py`, `src/memory/contracts.py`, `src/memory/__init__.py`, `src/social/models.py`, `src/social/__init__.py`, `tests/unit/test_v1_agent_models.py`, `tests/unit/test_v1_memory_social_models.py`, `tests/unit/test_subjective_state_contracts.py`, `tests/unit/test_cognition_strategies.py`, `tests/typecheck/cognition_strategies.py`.
  - Expected behavior: Subjective state stays distinct from `AgentBody`; old internal `AgentState`/`MemoryRecord` uses are migrated in one commit; all records are owner-bound and immutable; store replacement/order semantics are deterministic; memory and social remain independent; cognition receives no authority or mutable stores.
  - Logging requirements: Pure models, stores, and protocols emit no logs. Adapter callers may log owner ID, record ID, relationship ID, operation name, and pass/fail stage at DEBUG; never log goal text, memory/belief content, relationship metadata, or cognition context.
  - Dependencies: Tasks 1 and 3.

<!-- Commit checkpoint: tasks 1-4 -->

### Phase 2: Action Trust Pipeline

- [x] Task 5: Replace generic action payloads with a closed agent-command union
  - Deliverable: Define exact, frozen, final command variants with `Literal` fields set `init=False`: `Move(destination_id)`, `Search(target_id=None)`, `Take(item_id)`, `Drop(item_id)`, `Give(recipient_id,item_id)`, `Eat(item_id)`, `Drink(source_id)`, `Sleep()`, `Talk(recipient_id,text)`, `Ask(recipient_id,text)`, `Tell(recipient_id,text)`, `Help(target_id)`, `Attack(target_id)`, `Flee(threat_id=None)`, and `Wait()`. Text is exact `str`, 1-4096 code points after rejecting whitespace-only/control-containing input, preserved verbatim without trimming/normalization. Use an explicit exact-class allowlist for runtime discrimination; reject subclasses, mappings, unknown tags, and wrong ID classes. Make `CognitionStrategy.propose()` return `AgentCommand`; redefine `ActionProposal` as only `proposal_id + command` and `ActionRequest` as non-authoritative `request_id + proposal_id + world_id + actor_id + revision + command`.
  - Files: `src/world/actions.py`, `src/world/identifiers.py`, `src/world/__init__.py`, `src/agents/cognition/contracts.py`, `tests/unit/test_v1_action_commands.py`, `tests/unit/test_llm_trust_boundary.py`, `tests/unit/test_cognition_strategies.py`, `tests/typecheck/cognition_strategies.py`, `tests/typecheck/v1_domain_contracts.py`.
  - Expected behavior: All fifteen commands have one exact schema; commands and proposals carry no actor authority; invalid text/types/tags/extra data fail closed; provider text and shape-compatible mappings remain untrusted inputs.
  - Logging requirements: Commands and trust-boundary validators emit no logs. Future parsing/orchestration adapters may log proposal/request IDs, actor ID, command discriminator, revision, and validation stage at DEBUG; never log talk/ask/tell text or arbitrary source payloads.
  - Dependencies: Tasks 1 and 4.

- [x] Task 6: Add simulation-owned command admission and request binding
  - Deliverable: Add `admit_agent_command(...)` in `simulation.actions` to receive authenticated `AgentId` context and an exact `AgentCommand`, allocate deterministic proposal/request IDs from explicit run/scope inputs, translate the agent with `IdentityTranslator`, and bind `WorldId` plus expected `WorldRevision` into a non-authoritative `ActionRequest`. Keep `ActionProposal` optional audit data created by simulation, not cognition. Reject operational request IDs, raw provider/mapping input, translation mismatches, and caller-supplied actor IDs.
  - Files: `src/simulation/actions.py`, `src/simulation/identifiers.py`, `src/simulation/__init__.py`, `src/agents/contracts.py`, `tests/unit/test_v1_action_admission.py`, `tests/unit/test_llm_trust_boundary.py`, `tests/typecheck/v1_domain_contracts.py`.
  - Expected behavior: Only the simulation admission path binds agent identity and world/revision context; public construction or decoding of commands/proposals does not create authority; deterministic admission IDs do not depend on scheduling, wall time, UUIDs, or HTTP/log metadata.
  - Logging requirements: Admission emits no logs. Future orchestration callers may log proposal/request IDs, actor/world IDs, discriminator, revision, and validation stage at DEBUG; never log text, command bodies, observations, or identity-map contents.
  - Dependencies: Tasks 1, 3, 4, and 5.

- [x] Task 7: Add private validated world operations and atomic promotion
  - Deliverable: Define a private nominal operation variant for each command, a closed `ValidatedWorldOperation`, and `OperationAccepted`/`OperationRejected` results with stable rejection codes for wrong trust stage/type, wrong world, stale revision, invalid actor binding, missing actor body, missing/wrong-category structural target, and malformed envelope. Validation may check exact types, world/revision equality, authoritative actor-body existence, target existence/category, and distinct-ID constraints. It must defer reachability, visibility, item ownership/inventory membership, alive/awake state, resource availability, consent, combat eligibility/effects, duration, cooldowns, scheduling, and probability. Keep operation constructors internal to the validator and perform validation plus transition application through one `World` authority method that rechecks the base revision atomically; document that Python privacy/import checks prevent accidental bypass, not hostile reflection.
  - Files: `src/world/_operations.py`, `src/world/_transitions.py`, `src/world/_state.py`, `pyproject.toml`, `tests/architecture/boundary_checker.py`, `tests/architecture/test_import_boundaries.py`, `tests/architecture/test_boundary_checker.py`, `tests/architecture/test_world_authority.py`, `tests/unit/test_v1_world_operations.py`.
  - Expected behavior: Commands, proposals, mappings, decoded documents, and unvalidated requests cannot reach transitions through supported application paths; stale or cross-world requests fail without events; operations carry request ID, authoritative actor ID, world ID, and base revision and are never public exports.
  - Logging requirements: Validation and transition protocols emit no logs. Future orchestration may log safe IDs, discriminator, base/current revisions, validation stage, and rejection code at DEBUG/WARNING; never log command/event contents or full world state.
  - Dependencies: Tasks 3, 5, and 6.

- [x] Task 8: Define immutable closed world events and transition results
  - Deliverable: Replace generic events with `WorldEvent(event_id, request_id, world_id, revision, details)` and a closed V1 detail union parallel to all fifteen actions. Use the detail's `kind` as the sole discriminator and occurrence-only fields matching the command schema; do not add damage, quantities/effects, discoveries, durations, paths, or health deltas. Redefine `ActionOutcome` as a post-validation transition outcome with only `APPLIED` or `NOT_APPLIED`; validation failures remain separate `OperationRejected` values and never become events. Define private `TransitionResult(base_revision, resulting_revision, outcome, events)` after event types exist; normalize events to a tuple, require every event to match world/request/resulting revision, reject duplicate event IDs, and preserve emission order without requiring any event count or revision increment. Replace placeholder `spawned`/`tick`/`observed` test events with defined V1 details; require `SimulationExport` and `analysis.EventSource` to normalize/return immutable tuples.
  - Files: `src/world/events.py`, `src/world/actions.py`, `src/world/_transitions.py`, `src/world/__init__.py`, `src/simulation/models.py`, `src/simulation/contracts.py`, `src/analysis/contracts.py`, `tests/unit/test_v1_world_events.py`, `tests/unit/test_world_agent_contracts.py`, `tests/unit/test_reproducibility_contracts.py`, `tests/unit/test_analysis_contracts.py`.
  - Expected behavior: V1 events are closed, detached, immutable, consistently correlated, and serialization-safe; additions require a future schema revision; malformed input never emits a world fact; exports preserve transition emission order and cannot retain caller-owned lists.
  - Logging requirements: Events and transition results emit no logs. Export/orchestration callers may log event ID, request ID, discriminator, revision, count, and outcome category at DEBUG/INFO; never log event text/content or serialize whole events into logs.
  - Dependencies: Task 7.

<!-- Commit checkpoint: tasks 5-8 -->

### Phase 3: Serialization, Enforcement, and Verification

- [x] Task 9: Implement one strict versioned serialization boundary
  - Deliverable: Add `encode_domain(value) -> bytes` and `decode_domain(data: bytes) -> SerializableDomainValue` in `simulation.serialization` using envelope `{"schema_version":1,"type":"<tag>","data":{...}}`. Top-level round-trip support is limited to immutable objective models, `Agent`, `Goal`, `MemoryTrace`, `Belief`, `Relationship`, `CommunicationEnvelope`, `AgentCommand`, `ActionProposal`, `Observation`, `WorldEvent`, and `SimulationExport`; IDs/scalars/enums/details are nested-only. Explicitly reject `ActionRequest`, all authority/private types, mutable stores, gateways, protocols, helper functions, and unknown tags. Encode UTF-8 with `ensure_ascii=False`, sorted keys, compact separators, and `allow_nan=False`; nested bytes-like values remain forbidden. Decode strict UTF-8 without BOM/trailing data, reject duplicate object keys and non-finite constants, require exact fields/runtime types, and reconstruct exact wrappers/tuples. Define `DomainSerializationError(code, path)` without retaining or printing source content, plus golden canonical documents and a registry test covering every supported type/variant.
  - Files: `src/simulation/serialization.py`, `src/simulation/__init__.py`, affected public package facades, `tests/unit/test_v1_domain_serialization.py`, `tests/unit/test_v1_export_serialization.py`.
  - Expected behavior: Every supported value round-trips exactly and canonicalizes to one byte representation; encoded/decoded values are detached; malformed, duplicate-key, unsafe, unsupported, request-shaped, or authority-shaped input fails closed without granting authority or leaking content.
  - Logging requirements: Codecs emit no logs and errors include only stable code/path metadata, never source documents or domain content. Operational boundary logging is deferred until a concrete import/persistence/API adapter exists.
  - Dependencies: Tasks 2-8.

- [x] Task 10: Enforce public facades, private authority, dependency rules, and exhaustive typing
  - Deliverable: Curate `__all__` exports for public immutable contracts and the simulation codec while keeping `World`, `WorldState`, operations, validators, transitions, and private results hidden. Verify Task 7's `world._operations` import-linter/AST protection with focused facade and importer fixtures. Add import-linter and AST rules forbidding `pydantic`/`pydantic_core` in domain/simulation/analysis packages while retaining infrastructure usage. Keep one whole-tree architecture assertion. Add a passing mypy fixture using `match` plus `assert_never`; put intentionally invalid snippets in non-`.py` fixtures and test separate mypy failures/codes for ID, command/request/operation, and tuple mutability errors. Verify existing `py.typed` markers and installed-wheel imports include the new serialization API.
  - Files: `src/world/__init__.py`, `src/agents/__init__.py`, `src/memory/__init__.py`, `src/social/__init__.py`, `src/simulation/__init__.py`, `pyproject.toml`, `tests/architecture/boundary_checker.py`, `tests/architecture/test_import_boundaries.py`, `tests/architecture/test_boundary_checker.py`, `tests/architecture/test_world_authority.py`, `tests/typecheck/v1_domain_contracts.py`, `tests/typecheck/invalid/*.txt`, `tests/unit/test_v1_typing.py`, `tests/unit/test_packaging.py`.
  - Expected behavior: Public imports expose only intended immutable values; authority and Pydantic cannot leak into domain packages; architecture checks have no duplicate whole-tree scans; strict typing proves exhaustive unions and nominal trust stages; the installed wheel remains typed and exposes the codec.
  - Logging requirements: Package imports and successful architecture/type checks emit no logs. Test failures must identify the file, symbol, boundary, and violated rule; optional DEBUG diagnostics may list checked modules but never import-time domain values.
  - Dependencies: Tasks 7 and 9.

- [x] Task 11: Close coverage gaps, complete documentation checkpoint, and verify end to end
  - Deliverable: Review the focused tests from Tasks 1-10 against one coverage matrix rather than duplicating them. Add only missing Hypothesis properties and one end-to-end contract test covering decoded command to simulation admission to private validation/typed transition boundary, plus parametrized registries proving every requested model and all fifteen command/event variants are tested and serializable where supported. Remove obsolete generic payload/proposal/event fixtures. After code/tests pass, invoke the mandatory `$aif-docs` checkpoint and update only factual ownership, exact trust pipeline, public facade, wire support/versioning, deferred policy, and final command documentation; synchronize AI Factory description/architecture context.
  - Files: `tests/unit/test_v1_*.py`, affected existing unit/architecture/typecheck tests, `README.md`, `docs/architecture.md`, `docs/development.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`.
  - Expected behavior: At least one Hypothesis property covers each invariant family where practical; every requested model/action appears in the matrix; obsolete open payload paths are gone; all locked checks pass; docs distinguish structural contracts from deferred M2 behavior and match the implemented public/private surface.
  - Logging requirements: Tests assert pure domain operations and imports emit no logs. Verification may show verbose command diagnostics and redacted failure context only; documentation defines allowed boundary fields and `PALIMPSEST_LOG_LEVEL` control, and no generated report artifact is added.
  - Dependencies: Tasks 1-10.

<!-- Commit checkpoint: tasks 9-11 -->

## Verification Commands

```bash
uv sync --frozen --python 3.12.14
uv run --frozen --python 3.12.14 ruff check src tests
uv run --frozen --python 3.12.14 mypy
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term-missing
```

## Acceptance Criteria

- `World`, `WorldState`, `Agent`, `AgentBody`, `Location`, `Item`, `Resource`, `Weather`, `WorldEvent`, `Observation`, `Relationship`, `MemoryTrace`, `Belief`, and `Goal` exist as strongly typed domain contracts in their owning bounded packages.
- Agent physical state explicitly includes location, health, hunger, thirst, fatigue, temperature, immutable inventory, and alive/dead status with tested structural invariants.
- The fifteen requested actions form a closed discriminated command union; unknown actions and arbitrary payload fields fail closed.
- Agent commands, proposals, non-authoritative requests, validated private operations, and immutable resulting events are nominally separate; only private validation promotes a request to authority through supported application paths.
- Every important aggregate, entity, command envelope, subjective record, and event has an explicit stable ID; deterministic factories are namespaced, reproducible, and independent of wall-clock, UUID, global RNG, Python hashing, and operational metadata.
- Domain contracts and codecs have no dependency on FastAPI, Pydantic, ORM/infrastructure, or LLM providers, and imports remain side-effect free.
- Versioned serialization round-trips its explicit immutable allowlist canonically, preserves exact typed identities and immutable collections, rejects unknown/unsafe/request/authority input, and never grants authority by decoding.
- Unit, Hypothesis property, architecture, type, lint, packaging, and coverage checks pass without requiring PostgreSQL or Docker.
- No simulation behavior beyond domain/type validation is introduced, and the deferred M2 rules are documented explicitly.
- Documentation is completed through the mandatory `$aif-docs` checkpoint.
