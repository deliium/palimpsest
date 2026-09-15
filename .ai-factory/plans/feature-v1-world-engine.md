# Implementation Plan: Authoritative Deterministic V1 World Engine

Branch: feature/v1-core-domain-model-contracts (branch creation skipped to preserve the dirty worktree; intended feature branch: feature/v1-world-engine)
Created: 2026-09-15

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M2 - Simulation Loop"
Rationale: This plan implements the authoritative tick loop, observations, deterministic action resolution, and behavioral enforcement that define M2.

## Goal

Implement the sole public authority for objective world evolution with this lifecycle:

```text
tick N
-> produce immutable observations from one starting snapshot
-> receive an explicitly ordered batch of typed agent actions
-> admit and validate every action
-> resolve actions in deterministic order
-> atomically install the resulting authoritative world snapshot
-> emit ordered immutable WorldEvents and typed action results
-> advance to tick N+1
```

The implementation must prove that an equivalent public bootstrap, seed, and ordered action sequence produce identical final state, typed results, objective event order, identifiers, and canonical schema-1 export bytes. Agent cognition and LLM invocation remain out of scope.

## Design Decisions

- `simulation.WorldEngine` is the sole public component that can advance objective world state. Private world modules validate requests, evaluate rules, and prepare candidate snapshots; they never expose mutation hooks or commit independently.
- A public immutable bootstrap contains the initial world identity/revision, ordered objective models, and ordered `AgentId` to `EntityId` registrations. The engine validates it and constructs private authority values internally.
- A tick starts from one immutable private snapshot and explicit `Tick`. Observation production returns one immutable batch with an engine-issued tick token. Public submissions contain that token, authenticated `AgentId`, and an exact `AgentCommand`; callers never provide actor IDs, request IDs, event IDs, revisions, canonical ID keys, or action ordinals.
- Tick and world revision are independent. Every successfully resolved tick advances the tick exactly once. World revision advances exactly once when at least one semantic state effect is committed; event-only and wholly unsuccessful ticks retain the revision.
- Ordered input position is the V1 resolution priority and is assigned internally. Lower ordinals resolve first. If an action was valid against the starting snapshot but becomes invalid against the evolving snapshot because of an earlier committed effect, it receives a conflict result. Actions invalid in the starting snapshot receive a rejection result.
- Each registered agent may submit at most one action per tick. A duplicate consumes its own input position and receives a typed duplicate result. An omitted agent has no implicit `Wait`, result, event, or random draw.
- Every typed submission yields one immutable `ActionResolution`. Applied objective occurrences emit correlated immutable `WorldEvent`s. Rejected, dead-actor, duplicate, conflicted, and deferred-policy resolutions never mutate state and never become objective world events, preserving the established occurrence-only event model.
- All fifteen V1 command variants receive an explicit rule outcome. `Take`, `Drop`, and `Give` implement currently representable physical mutations. `Search`, `Talk`, `Ask`, `Tell`, and `Wait` implement validated event-only behavior. `Move`, `Eat`, `Drink`, `Sleep`, `Help`, `Attack`, and `Flee` return stable deferred-policy results until topology, nutrition, recovery, combat, or escape semantics are explicitly defined.
- Dead actors are rejected for every V1 command before command-specific behavior. A command outcome matrix defines validation precedence, target/dead-target rules, placement, ownership, co-location, no-op, deferred-policy, and conflict behavior.
- Rules are pure, scheduler-independent functions over immutable starting/working snapshots and validated operations. They do not import simulation, logging, wall clocks, UUID factories, or randomness.
- The explicit run seed remains mandatory. IDs and any future random effects use canonical simulation-owned scopes containing run/world/tick/action ordinal/actor/purpose. V1 adds no unused random draws or speculative randomized rule inputs.
- Private world code prepares a complete immutable batch candidate. `WorldEngine` validates the candidate, builds a complete immutable next engine snapshot containing private world authority, next tick/phase, resolutions, objective events, and history, then swaps one internal reference. Unexpected failures before the swap retain the prior snapshot and allow a deterministic retry.
- All objective events in a mutating batch carry the final committed batch revision. Event-only batches retain and use the starting revision. Each `ActionResolution` records both base and resulting revision plus tick and ordinal.

## Non-Goals

- Agent cognition, LLM calls, autonomous action selection, memory updates, and social interpretation.
- Inventing V1 topology, nutrition, combat, healing, sleep-duration, resource consumption, hidden-object, or environmental progression policy not represented by current contracts.
- Database persistence or API endpoints for running simulations.
- Exposing or serializing `World`, `WorldState`, private operations, rule internals, or mutable engine collections.
- Serializing tick tokens, submissions, `ActionResolution`, `TickResult`, bootstrap state, or a replay-input format. Schema-1 export remains an objective-event audit artifact, not a complete replay source.

## Commit Plan
- **Commit 1** (after tasks 1-4): `feat(simulation): define world engine lifecycle contracts`
- **Commit 2** (after tasks 5-8): `feat(world): implement authoritative tick resolution`
- **Commit 3** (after tasks 9-11): `test(simulation): prove deterministic world engine replay`

## Tasks

### Phase 1: Lifecycle and Authority Contracts

- [x] Task 1: Define immutable tick lifecycle, token, submission, and result contracts.
  - Deliverable: Add frozen, slotted public types for engine-issued tick tokens, ordered observation batches, authenticated action submissions, per-action `ActionResolution`, closed status/reason codes, tick event records with engine-assigned intra-tick sequence, and `TickResult`. A submission contains only token, `AgentId`, and exact `AgentCommand`; reject mappings, sets, subclasses, stale/replayed/cross-engine tokens, private authority values, and caller-provided ordinals or request metadata. Define base/resulting tick and revision correlation. Tighten `Tick` and `SimulationRunConfig.seed` to exact non-boolean integers.
  - Files: `src/simulation/lifecycle.py`, `src/simulation/models.py`, `src/simulation/clock.py`, `src/simulation/__init__.py`.
  - Logging: Keep immutable value construction side-effect-free. Add stable non-sensitive diagnostic codes for engine DEBUG logs; never include command text, private state, or arbitrary payloads.
  - Dependencies: None. This contract anchors tasks 2-11.

- [x] Task 2: Define a public bootstrap and deterministic agent registration boundary.
  - Deliverable: Add an immutable public bootstrap/factory input built only from public `WorldId`, `WorldRevision`, objective models, and ordered `(AgentId, EntityId)` registrations. Validate ordered containers, duplicate identities, missing body mappings, cross-category IDs, round-trip translation, and canonical registration ordering before constructing private `WorldState`/`World` values inside the engine. Define whether dead bodies may be registered (allowed for observation/history but unable to act) and ensure no private authority type appears in the public constructor or return annotations.
  - Files: `src/simulation/bootstrap.py`, `src/simulation/lifecycle.py`, `src/simulation/__init__.py`, `tests/unit/test_world_engine_bootstrap.py`.
  - Logging: Bootstrap values and validation remain side-effect-free. The engine logs DEBUG counts, world/revision, and stable validation stages; invalid bootstrap logs ERROR through existing orchestration helpers without dumping registrations or state.
  - Dependencies: Depends on task 1.

- [x] Task 3: Add private deterministic perception with immediate authority protection.
  - Deliverable: Add a private state-to-`Observation` projector with a minimal documented V1 policy: each registered body receives its detached `self_body` plus deterministically EntityId-sorted location/item/resource/weather projections allowed by that policy; no other full `AgentBody` is exposed. Define stable observation ordering by registration, behavior for missing/dead bodies, idempotent repeated reads within one open tick, and failure behavior before token issuance. Protect `_perception` in import-linter and the AST checker in the same task.
  - Files: `src/world/_perception.py`, `src/world/observations.py` only if required, `pyproject.toml`, `tests/architecture/boundary_checker.py`, `tests/architecture/test_boundary_checker.py`, `tests/architecture/test_world_authority.py`, `tests/unit/test_world_perception.py`.
  - Logging: Perception remains pure and log-free. Return only detached observations; the engine logs DEBUG observer/count/revision metadata without observation or body content.
  - Dependencies: Depends on task 2.

- [x] Task 4: Define pure action rule interfaces and the complete V1 outcome matrix.
  - Deliverable: Introduce private rule/effect result types and document/test a table for all fifteen commands covering validation precedence, dead actor/target handling, target category, placement, ownership, co-location, current-location/no-op behavior, one-action slot consumption, deferred-policy precedence, and emitted objective event eligibility. Extend structural validation while preserving the closed private operation union. Rules evaluate immutable snapshots without scheduler, RNG, or logging dependencies. Protect `_rules` immediately and permit the complete private-world importer mesh without broadening access outside private world modules and `simulation.engine`.
  - Files: `src/world/_rules.py`, `src/world/_operations.py`, `src/world/actions.py`, `pyproject.toml`, `tests/architecture/boundary_checker.py`, `tests/architecture/test_boundary_checker.py`, `tests/unit/test_v1_world_operations.py`, `tests/unit/test_world_rules.py`.
  - Logging: Rules and validators remain log-free. Stable reason codes let the engine log action kind, actor/request IDs, validation stage, and outcome at DEBUG; free-form text and full state remain excluded.
  - Dependencies: Depends on tasks 1-3.

### Phase 2: Deterministic Resolution and Mutation

- [x] Task 5: Implement physical, event-only, and deferred V1 rule handlers.
  - Deliverable: Implement immutable physical effects for `Take`, `Drop`, and `Give`, including item placement, inventory/holder agreement, ownership, recipient co-location, and deterministic inventory ordering. Implement validated occurrence-only handlers for `Search`, `Talk`, `Ask`, `Tell`, and `Wait`. Implement explicit deferred-policy outcomes for `Move`, `Eat`, `Drink`, `Sleep`, `Help`, `Attack`, and `Flee` without events, mutation, or random draws. Preserve existing occurrence event detail types and validate every precondition before constructing an effect/event.
  - Files: `src/world/_rules.py`, `src/world/_transitions.py`, `src/world/_state.py`, `src/world/events.py`, `tests/unit/test_world_rules.py`, `tests/unit/test_v1_world_events.py`, `tests/unit/test_v1_world_state.py`.
  - Logging: Handlers remain pure and log-free. Effect/reason values expose only safe IDs, action kind, and changed/not-changed metadata for engine DEBUG diagnostics; never expose communication text or snapshots.
  - Dependencies: Depends on task 4.

- [x] Task 6: Implement private batch preparation, conflict provenance, and revision correlation.
  - Deliverable: Add one private batch preparation operation that receives the starting snapshot and engine-ordered admitted requests, validates each request against both starting and evolving snapshots, applies successful effects to a private working snapshot, and classifies a failure as conflict only when it was initially valid and an earlier effect invalidated it. Return a fully validated immutable candidate state, semantic-mutation flag, typed private outcomes, and ordered objective events without installing state. Increment revision once for any semantic mutation; stamp all objective events in a mutating batch with the final revision and event-only batches with the unchanged starting revision. Validate event IDs, request/world correlation, and duplicate IDs before returning.
  - Files: `src/world/_state.py`, `src/world/_operations.py`, `src/world/_rules.py`, `src/world/_transitions.py`, `tests/unit/test_world_batch.py`, `tests/unit/test_v1_world_events.py`.
  - Logging: Batch preparation remains pure and log-free. Private outcomes provide stable stages/reasons for engine DEBUG logs; invariant/correlation failures raise typed exceptions for engine ERROR logging and atomic retry tests.
  - Dependencies: Depends on tasks 4 and 5.

- [x] Task 7: Centralize engine-owned deterministic admission, IDs, and RNG boundaries.
  - Deliverable: Replace caller-controlled admission keys at the engine boundary with canonical proposal/request/event identifiers derived from seed, run/world identity, tick, engine-assigned ordinal, actor, purpose, and event sequence. Keep `simulation.randomness` as the only random importer and define canonical future effect scopes, but add no unused draws or RNG-bearing rule interfaces. Prove invalid/deferred actions cannot change IDs assigned to later fixed ordinals and process-global random state cannot affect or be affected by admission/resolution.
  - Files: `src/simulation/actions.py`, `src/simulation/identifiers.py`, `src/simulation/randomness.py`, `tests/unit/test_v1_action_admission.py`, `tests/unit/test_v1_stable_identifiers.py`, `tests/unit/test_reproducibility_contracts.py`.
  - Logging: Admission helpers remain log-free. The engine may log DEBUG tick/ordinal/action kind, safe IDs, derivation version, and canonical purpose; retain the established seed diagnostic policy, never log random state/draws or command text.
  - Dependencies: Depends on tasks 1, 2, and 4.

- [x] Task 8: Implement `WorldEngine` as one atomic tick state machine.
  - Deliverable: Add a public engine that owns one immutable internal snapshot containing private world authority, current tick/phase, current token, registrations, resolution history, and objective event history. Expose separate observation and ordered-resolution methods so cognition remains external. Enforce legal phase transitions; validate tokens and one-action-per-agent policy; assign input ordinals; admit requests; invoke private batch preparation; construct and validate the complete next engine snapshot and `TickResult`; then commit with one reference swap. Repeated observations in an open tick are identical; omitted agents produce nothing; unexpected preparation/result failures preserve the prior snapshot and permit deterministic retry. Expose only detached tick/revision/result/event/export views.
  - Files: `src/simulation/engine.py`, `src/simulation/contracts.py`, `src/simulation/__init__.py`, `tests/unit/test_world_engine.py`, `tests/unit/test_world_engine_admission.py`.
  - Logging: Follow the existing stdlib `logging.getLogger(...)` orchestration pattern routed through configured infrastructure. Define stable event names/fields; DEBUG normal phase, admission, rejection, conflict, deferred, and commit detail; INFO one successful tick commit; WARN stale/reentrant/lifecycle misuse; ERROR invariant failures and aborted candidates. Retain existing seed diagnostics and exclude communication text, observations, registrations, full IDs where current redaction applies, and private state.
  - Dependencies: Depends on tasks 1-7.

### Phase 3: Persistence Boundaries and Proof

- [ ] Task 9: Make `WorldEngine` the sole supported public authority path.
  - Deliverable: Audit and retire or internalize authority-shaped legacy surfaces after the engine is usable. Remove public `WorldGateway`/`accept_action_request`/transition outcome exports when no concrete external consumer requires them; keep `ActionRequest` explicitly non-authoritative and wire-ineligible; make admission with canonical keys engine-internal; remove or guard direct `World.replace_state`; and narrow private batch/commit imports so only `simulation.engine` and designated private world modules can use them. Update existing trust-boundary tests without weakening cognition/LLM isolation.
  - Files: `src/world/actions.py`, `src/world/_state.py`, `src/world/__init__.py`, `src/simulation/actions.py`, `src/simulation/__init__.py`, `pyproject.toml`, `tests/architecture/boundary_checker.py`, `tests/architecture/test_import_boundaries.py`, `tests/architecture/test_world_authority.py`, `tests/unit/test_world_agent_contracts.py`, `tests/unit/test_llm_trust_boundary.py`, `tests/unit/test_v1_world_operations.py`.
  - Logging: Removed/internalized authority helpers emit no logs. Architecture violations identify symbol/module/caller only; engine logs unsupported boundary attempts at WARN without payloads or text.
  - Dependencies: Depends on task 8.

- [ ] Task 10: Preserve schema-1 compatibility and enforce lifecycle typing/boundaries.
  - Deliverable: Keep `WorldEvent` occurrence details and `SimulationExport(metadata, events)` on schema version 1; do not serialize bootstrap, tick tokens, submissions, resolutions, results, or private state. Verify existing objective events from the engine round-trip canonically and remain ordered. Complete facade, packaging, architecture, and positive/negative mypy coverage for public bootstrap/lifecycle types, token/ID distinctions, exact ordered submission inputs, closed result matching, nondeterministic-call bans, and private authority exclusion.
  - Files: `src/simulation/models.py`, `src/simulation/serialization.py`, `src/simulation/__init__.py`, `pyproject.toml`, `tests/unit/test_v1_domain_serialization.py`, `tests/unit/test_v1_export_serialization.py`, `tests/unit/test_v1_e2e_contracts.py`, `tests/unit/test_v1_typing.py`, `tests/unit/test_packaging.py`, `tests/typecheck/v1_domain_contracts.py`, `tests/typecheck/invalid/`, `tests/architecture/test_import_boundaries.py`, `tests/architecture/test_world_authority.py`.
  - Logging: Codec and type/architecture checks remain log-free in normal operation. Codec errors retain stable code/path only; engine export logs DEBUG event count/schema/derivation metadata and ERROR failures without encoded documents or event text.
  - Dependencies: Depends on tasks 8 and 9.

- [ ] Task 11: Prove deterministic reruns and document the World Engine contract.
  - Deliverable: Add a deterministic test-only canonical projection of private `WorldState`, then use fixed and Hypothesis-generated short traces to construct two independent equivalent engines and prove identical final projections, ticks/revisions, `ActionResolution`s, objective event order/details/IDs, and canonical schema-1 export bytes for identical bootstrap, seed, and ordered submissions. Cover empty and event-only ticks, `Take`/`Drop`/`Give`, same-item and indirect ownership/location conflicts, invalid targets, duplicate/omitted agents, dead actors, deferred commands, stale/replayed tokens, mixed final-revision correlation, global RNG perturbation/non-mutation, failed candidate preparation, unchanged snapshot after failure, and deterministic retry. Test rules directly without the engine and engine execution without cognition/LLM dependencies. Complete the mandatory `$aif-docs` checkpoint and run all locked project checks.
  - Files: `tests/unit/determinism_helpers.py`, `tests/unit/test_simulation_replay_determinism.py`, `tests/unit/test_world_engine.py`, `tests/unit/test_world_batch.py`, `tests/unit/test_world_rules.py`, `tests/unit/test_reproducibility_contracts.py`, `README.md`, `docs/architecture.md`, `docs/development.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`.
  - Logging: Capture logs to assert DEBUG normal outcomes, one INFO commit per successful tick, WARN lifecycle misuse, ERROR aborted candidates, `PALIMPSEST_LOG_LEVEL` control, and absence of text/observations/registrations/private state. Do not use log order as simulation semantics.
  - Dependencies: Depends on tasks 1-10.

## Verification Commands

```bash
uv sync --frozen --python 3.12.14
uv run --frozen --python 3.12.14 ruff check src tests
uv run --frozen --python 3.12.14 mypy src tests
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term-missing
uv run --frozen --python 3.12.14 lint-imports --config pyproject.toml --no-cache --no-logo
```

## Acceptance Criteria

- `WorldEngine` can be constructed from public immutable bootstrap values and is the sole supported public mutation authority; no facade, constructor, return type, or alternate gateway exposes private state or commit hooks.
- The explicit observation/token/submission/resolution lifecycle is enforced, observations come from tick N's immutable starting snapshot, and one-reference commit advances to tick N+1 only after the complete candidate validates.
- Resolution order and first-valid-wins behavior depend only on ordered sequence position. Initially invalid actions are rejected; actions invalidated by earlier effects are conflicted; omitted agents do not imply actions.
- Every typed submission has one immutable `ActionResolution`. Only applied objective occurrences have `WorldEvent`s; invalid, dead-agent, conflict, duplicate, and deferred-policy outcomes produce no mutation or world event.
- Dead agents cannot perform any of the fifteen normal V1 actions.
- `Take`, `Drop`, and `Give` mutate state correctly; `Search`, `Talk`, `Ask`, `Tell`, and `Wait` are validated event-only handlers; `Move` and the remaining policy-dependent commands are explicit deferred outcomes.
- Tick and revision are distinct; semantic mutation increments revision once, all events in that batch use the final revision, and event-only ticks retain revision.
- The explicit seed is required and all IDs/future random scopes are simulation-owned; global random state, wall clocks, LLMs, UUIDs, and Python object hashes cannot affect resolution.
- Pure rule tests execute without constructing a scheduler/engine, and engine tests use supplied actions without cognition or provider dependencies.
- Schema-1 event/export compatibility is preserved; runtime tick lifecycle and replay-input state are not added to the wire format.
- Fixed and property-based tests prove equivalent bootstrap + identical seed + identical ordered submissions produce identical final state projection, results, events, identifiers, and canonical export bytes.
- Failed candidate preparation leaves the full engine snapshot unchanged and retrying produces the same result as a fresh equivalent engine.
- Unit, architecture, serialization, typing, lint, and import-boundary checks pass.
