# Implementation Plan: V1 Physical Simulation Rules

Branch: main (no new branch requested)
Created: 2026-09-19

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M2.5 — V1 Physical Simulation"
Rationale: Extend the completed deterministic simulation loop with the objective physical world mechanics required before cognition and provider work.

## Scope

Implement a small discrete physical world designed for 5-10 agents, 10-20 locations, and several resource types while preserving the existing modular-monolith boundaries, immutable state snapshots, ordered action resolution, one-revision-per-mutating-tick rule, durable prepare/persist/finalize transaction, and replay without rerunning current rules or randomness.

In scope:
- Graph topology, occupancy/content capacity, local environment, and adjacent movement.
- Portable food, water, material, medical, and generic items; finite and renewable resource nodes; inventory load and transfer rules.
- Hunger, thirst, health, fatigue, body temperature, and irreversible alive-to-dead transitions.
- Logical simulation time, day/night, seeded weather, visibility, passive physiology, and configured resource regeneration.
- Physical behavior for `Move`, `Search`, `Take`, `Drop`, `Give`, `Eat`, `Drink`, `Sleep`, `Attack`, `Flee`, `Help`, and `Wait`.
- Immutable, effect-complete `WorldEvent` records for every committed physical change.

Out of scope:
- Psychological fear of death, death awareness, beliefs, memories, goals, or emotional responses.
- Agent cognition loops, LLM/provider behavior, pathfinding beyond one adjacent edge, equipment systems, diseases, crafting, revival, or multi-tick sleeping state.
- API endpoints or UI for controlling the simulation.

## V1 Rule Contract

### Numeric and ordering rules
- One logical tick equals one simulated hour. `hour = tick % 24`; day is hours 06-17 inclusive and night is hours 18-05.
- Keep physical quantities finite and bounded. Health, hunger, thirst, and fatigue remain in `[0.0, 100.0]`; temperature remains finite but is not clamped to that interval. Round calculated decimals once, to one decimal place using Python's ties-to-even rule, after each complete effect and then clamp bounded values.
- Resolve agent submissions in existing input order, then apply autonomous effects in this fixed order: weather, resource regeneration, per-body metabolism, temperature/exposure, and atomic death handling.
- Iterate system effects by canonical `EntityId` order. A tick with any semantic mutation advances world revision exactly once; every event in that tick carries the same resulting revision and contiguous sequence numbers.
- Pure `world` rule modules do not log or draw randomness. `simulation` resolves named seeded draws and logs IDs, ticks, kinds, counts, statuses, and bounded numeric summaries, never complete snapshots, inventories, event payloads, communication text, or random draws.
- Action and autonomous stages accumulate world-owned pending effects/events against one evolving state. Only a final tick coordinator decides whether state changed, advances revision once, allocates event IDs/sequences, and freezes all `WorldEvent` values with the final revision.

### Locations, contents, and visibility
- Model an undirected graph with an ordered unique adjacency tuple. Reject self-edges, dangling edges, asymmetric edges, duplicate neighbors, and disconnected bootstrap worlds.
- Each location has positive `body_capacity`, non-negative `item_capacity`, a base ambient temperature, a shelter factor in `[0.0, 1.0]`, and a base visibility factor in `[0.0, 1.0]`.
- All bodies, including dead bodies, count toward body capacity. Ground items count toward item capacity; held items and resource nodes do not.
- Expose the current location and adjacent exits at all visibility levels. Expose local ground items, resource nodes, and other bodies only when effective visibility is at least `0.5`; always expose self, current weather, hour, day phase, and the numeric visibility modifier.
- Effective visibility is `clamp(location base * phase factor * weather factor, 0.0, 1.0)`: day `1.0`, night `0.5`; clear `1.0`, cloudy `0.9`, rain `0.7`, storm `0.5`.
- Exits expose destination IDs and names only. Other bodies use a limited visible-body DTO containing identity, life status, and coarse health state, never inventory or exact physiology. Self and held inventory remain visible below `0.5`; dead registered observers continue to receive self/time/environment observations. Physical target validation uses authoritative co-location and is not visibility-gated, allowing remembered IDs.
- New schema-v3 bootstraps require at least one location, explicit adjacency, and exactly one weather condition per location; a one-location graph is connected. Legacy schema-v2 decoding supplies versioned minimal defaults but new worlds never infer missing edges or weather.

### Items, resources, and conservation
- Item kinds are `food`, `water`, `material`, `medical`, and `generic`. Every portable item has a positive integer load and exactly one placement: ground location or body inventory.
- Each body has a positive integer carry capacity. `Take` and `Give` reject an operation that would exceed it. `Drop` rejects a full location. Transfers are atomic and preserve item identity.
- Resource kinds are `food`, `water`, and `material`. Each node has current quantity, maximum quantity, fixed extraction amount `1.0`, and regeneration amount per tick. Finite nodes use regeneration `0.0`; renewable nodes regenerate after action resolution up to maximum quantity.
- Resource quantity never becomes negative. A successful harvest or drink decrements exactly the amount recorded by its event; regeneration cannot exceed maximum quantity.
- A node is eligible for extraction only when quantity is at least `1.0`; quantities in `(0.0, 1.0)` are physically present but depleted for `Search` and resource-backed `Drink`.
- Consumed one-use food/water items are removed atomically from both the item index and inventory. Conservation tests account for each identity as exactly one of ground, held, or consumed by an immutable event.

### Actions
- `Move(destination)`: require an adjacent destination with a free body slot; move the body and add `5` fatigue immediately.
- `Search(target=None)`: require a local supported-kind node with quantity at least `1.0` and a free ground-item slot before drawing. If omitted, choose the first eligible node by `EntityId`. Initially missing capacity/quantity is rejected; invalidation by an earlier ordered effect is conflicted. Success probability is `clamp(0.25 + 0.75 * visibility, 0.0, 1.0)` using an action-scoped stream. A probability miss is applied/event-only. Success atomically extracts `1.0` and creates one deterministic-ID portable item of the matching kind on the ground.
- `Take(item)`: require a local ground item and sufficient carry capacity; move it into the actor inventory.
- `Drop(item)`: require actor ownership and free local item capacity; place it at the actor location.
- `Give(recipient, item)`: require a living colocated recipient, actor ownership, and recipient capacity; transfer atomically.
- `Eat(item)`: require a held food item; consume it and reduce hunger by `30`, clamped at zero.
- `Drink(source)`: accept either a held water item, which is consumed, or a local water resource with quantity at least `1.0`, which loses `1.0`; reduce thirst by `40`, clamped at zero.
- `Sleep()`: apply one-tick recovery immediately by reducing fatigue by `30`; shelter does not gate sleep, but close-of-tick metabolism and temperature rules still apply.
- `Attack(target)`: require a distinct living colocated target. Use independent action-scoped draws for a `0.75` hit probability and integer damage in `[10, 20]`; a miss is event-only. Apply damage immediately and emit death immediately if health reaches zero.
- `Flee(threat=None)`: if supplied, require a distinct living colocated threat. Require at least one adjacent destination with free capacity before drawing. Use one scoped draw for `0.80` success; only after success, use an independent uniform index draw over the canonically sorted currently eligible destinations. Success moves the actor and adds `10` fatigue; a probability failure is applied/event-only.
- `Help(target)`: require a distinct living colocated target; increase target health by `10` up to `100` and add `5` fatigue to the helper. It cannot revive a dead target.
- `Wait()`: remains an event-only action; the actor still receives close-of-tick autonomous effects.
- Existing `Talk`, `Ask`, and `Tell` behavior remains event-only and continues to receive baseline autonomous physiology like any other living actor.
- Stochastic misses/failures are `APPLIED` and emit an occurrence event without immediate mutation. Structural impossibility is `REJECTED` when invalid in the starting state and `CONFLICTED` when invalidated by an earlier ordered effect. `Sleep` at zero fatigue is an applied occurrence; `Help` at full target health still applies helper fatigue unless already capped. Eating or drinking at zero need is allowed and still consumes the item/resource. Revision advances only when the complete tick's objective state differs.

### Physiology, environment, and death
- At tick close, every living body gains `2` hunger, `3` thirst, and `1` fatigue, after immediate action costs/recovery.
- After need updates, apply health damage additively: hunger at `100` causes `2`, thirst at `100` causes `5`, and fatigue at `100` causes `1` damage.
- `Weather` stores condition only; ambient temperature is derived from location base plus weather offset (clear `0`, cloudy `-1`, rain `-3`, storm `-5`) plus phase offset (day `+2`, night `-2`). Compute body temperature as `current + 0.25 * (ambient - current) * (1 - shelter)`, then round once to one decimal. Body temperature below `35.0` or above `39.0` causes `5` health damage; exact thresholds are safe.
- Transition weather after completing ticks 5, 11, 17, ... when `(tick + 1) % 6 == 0`, independently per location, using this ordered matrix: clear `(clear .60, cloudy .30, rain .10, storm .00)`, cloudy `(clear .30, cloudy .40, rain .25, storm .05)`, rain `(clear .25, cloudy .35, rain .30, storm .10)`, storm `(clear .30, cloudy .30, rain .30, storm .10)`. An unchanged sampled condition emits no weather-change event; exposure events still record the derived ambient used.
- For each living body, first update needs and aggregate hunger/thirst/fatigue damage into one `combined_needs` effect. Apply health and death atomically; a body killed by needs skips temperature processing. Otherwise update temperature, then apply exposure damage and atomic death if required. Health is clamped to zero.
- The first transition to zero atomically sets `LifeStatus.DEAD` and emits exactly one `Died` event with closed cause `attack`, `combined_needs`, or `exposure`. Death is terminal: dead bodies cannot act, receive help, move, metabolize, regenerate, or return to life; their body and inventory remain in place and continue to occupy capacity.

### Seed and event rules
- Use fresh named streams derived from run, world, tick, original action ordinal or system entity ID, effect purpose, and an explicit physical-rules derivation version. Bernoulli uses `random() < probability`; damage uses `randrange(10, 21)`; destination uses `randrange(len(sorted_destinations))`; weather uses `random()` against cumulative half-open intervals. Structural failures draw nothing. Unrelated draws must not perturb one another; never use module-global RNG or Python `hash()`.
- Canonical physical-rules bytes/fingerprint participate in derivation-v2 run IDs, deterministic IDs, and stream seeds so equal seeds with different rules cannot alias. Legacy records retain derivation-v1 behavior.
- Compatibility matrix: audit schema v1 remains decode/export-only and non-replayable; replay schema v2 remains decodable/projectable by its legacy projector; replay schema v3 is emitted for new physical runs and uses the v3 projector. Runs never mix replay schema versions.
- Use a closed world-owned cause union: action cause retains `request_id` and actor ID; system cause uses a deterministic system request/cause ID derived from run, world, tick, effect family, entity ID, and per-family ordinal. Attack-caused `Died` retains the attack action cause. Every event receives its own deterministic ID, and one request may cause multiple events.
- Every mutating event stores resulting facts sufficient for projection without rules or RNG: placements, quantities, physiology, life status, weather, chosen destination, hit/miss, damage/healing, and consumed/created identities as applicable. `Died` is a separate objective event for attack, combined-needs, or exposure death.

## Commit Plan
- **Commit 1** (after tasks 1-4): `feat(world): define physical contracts and tick finalization`
- **Commit 2** (after tasks 5-8): `feat(simulation): implement physical actions and autonomous effects`
- **Commit 3** (after tasks 9-11): `feat(persistence): version and persist physical simulation state`
- **Commit 4** (after tasks 12-14): `test: verify physical simulation invariants and document rules`

## Tasks

### Phase 1: Physical Contracts

- [x] Task 1: Add the versioned physical ruleset and immutable domain values/models.
  - Deliverable: represent the rule contract above with validated enums/value objects and frozen models for adjacency, capacities, item/resource kinds and effects, location environment, resource maxima/regeneration, body carry capacity, day phase, weather condition, and visibility. Add a versioned world-owned `PhysicalRules` value carried by `SimulationRunConfig`; define canonical rules bytes/fingerprint and derivation-v2 identity so replay-significant constants are persisted and equal seeds with different rules do not alias. Retain derivation-v1 dispatch for legacy records and fail closed on contradictory values.
  - Files: `src/world/values.py`, `src/world/models.py`, `src/world/__init__.py`, `src/simulation/models.py`, `src/simulation/bootstrap.py`, `src/simulation/identifiers.py`, `src/simulation/randomness.py`, `tests/unit/test_v1_domain_values.py`, `tests/unit/test_v1_world_models.py`, `tests/unit/test_bootstrap.py`, `tests/unit/test_reproducibility_contracts.py`, `tests/unit/test_v1_stable_identifiers.py`.
  - Logging: do not log from immutable constructors or `world`; add DEBUG validation summaries at simulation bootstrap/run creation and ERROR diagnostics with stable codes for invalid physical configuration, without logging seeds, full entities, or payloads.
  - Dependencies: none.

- [x] Task 2: Enforce topology, capacity, placement, and conservation invariants in authoritative state and observations.
  - Deliverable: validate the undirected connected graph, occupancy, ground-item capacity, carry load, resource bounds, item placement, schema-v3 weather coverage, and legacy defaults; broaden `rebuild_world_state` to replace locations/items/resources/bodies/weather atomically; centralize immutable body/item/resource copy helpers. Add world-owned observation context plus limited exit/visible-body DTOs, then project time, phase, visibility, adjacent exits, visible contents, held inventory, and local bodies without exposing `WorldState` or another body's inventory/exact physiology.
  - Files: `src/world/_state.py`, `src/world/_perception.py`, `src/world/observations.py`, `src/simulation/engine.py`, `tests/unit/test_v1_world_state.py`, `tests/unit/test_world_perception.py`, `tests/unit/test_world_engine_bootstrap.py`.
  - Logging: keep world validation/projection log-free; have `simulation.engine` emit DEBUG counts for observers, visible entities, phase, and visibility band, and ERROR stable invariant codes on candidate aborts. Never log inventories, body snapshots, or observation payloads.
  - Dependencies: Task 1.

- [x] Task 3: Define resolved effects, event causation, and schema-v3 physical payloads.
  - Deliverable: add world-owned immutable resolved-action/system-effect unions keyed by original `RequestId` or system cause ID, with strict presence/alignment validation. Cover search outcome/created ID, attack hit/damage, flee success/selector, and weather outcome without passing RNG objects, callbacks, or simulation types into `world`. Add a closed action/system cause union and effect-complete frozen details with explicit minimum fields for movement, search, consumption, sleep, help, attack, flee, physiology, weather, regeneration, and `Died`. Define the v1 decode-only/v2 replay/v3 replay compatibility matrix and exact random purpose labels/sampling algorithms.
  - Files: `src/world/events.py`, `src/world/_operations.py`, `src/world/_transitions.py`, `src/world/__init__.py`, `src/simulation/actions.py`, `src/simulation/identifiers.py`, `tests/unit/test_v1_world_events.py`, `tests/unit/test_v1_world_operations.py`, `tests/unit/test_v1_stable_identifiers.py`, `tests/unit/test_world_agent_contracts.py`.
  - Logging: event/projector code remains log-free; replay orchestration logs DEBUG schema/projector selection and event counts, INFO successful projection checkpoints, and ERROR stable incompatibility/effect-validation codes without event details.
  - Dependencies: Tasks 1-2.

- [x] Task 4: Refactor tick preparation around pending effects and one final revision/event pass.
  - Deliverable: replace `prepare_action_batch`'s early revision/event materialization and the engine's one-event-ID-per-request assumption with a world-owned pending-effect/pending-event result. Resolve ordered actions against one evolving state, append one-to-many unfrozen details with causes, then provide a finalizer that determines semantic mutation once, advances revision at most once, assigns global contiguous sequences and deterministic event IDs, and freezes every event with the final revision. Preserve initial-state versus evolving-state conflict classification and key random effects by `RequestId`, not compressed admitted-batch index.
  - Files: `src/world/_operations.py`, `src/world/_transitions.py`, `src/world/events.py`, `src/simulation/actions.py`, `src/simulation/engine.py`, `src/simulation/lifecycle.py`, `tests/unit/test_world_batch.py`, `tests/unit/test_world_engine.py`, `tests/unit/test_v1_world_events.py`.
  - Logging: pending/finalization helpers remain log-free; engine DEBUG logs pending action/effect/event counts and final mutation status, INFO remains one tick commit, and ERROR uses stable finalization/alignment codes without payloads or random values.
  - Dependencies: Task 3.

### Phase 2: Rules and Tick Evolution

- [x] Task 5: Implement deterministic movement, inventory, search, and consumption rules.
  - Deliverable: replace deferred policies for `Move`, `Eat`, and `Drink`; tighten `Search`, `Take`, `Drop`, and `Give`; change `Drink` admission to accept an item-or-resource union followed by rule-stage kind/placement validation. Generate search facts via the Task 3 contract and enforce quantity/capacity checks before RNG, atomic extraction/item creation, exact applied-miss semantics, and rejection/conflict provenance. Consume pending effects rather than constructing final events directly.
  - Files: `src/world/actions.py`, `src/world/_operations.py`, `src/world/_rules.py`, `src/world/_transitions.py`, `src/simulation/actions.py`, `src/simulation/engine.py`, `src/simulation/lifecycle.py`, `tests/unit/test_v1_world_operations.py`, `tests/unit/test_world_rules.py`, `tests/unit/test_world_batch.py`, `tests/unit/test_world_engine.py`.
  - Logging: `simulation.engine` logs DEBUG action kind, ordinal, request ID, scoped outcome category, quantities changed, and reason code; INFO remains one aggregate tick commit; WARN lifecycle misuse; ERROR candidate abort. Do not log RNG draws or item/body payloads.
  - Dependencies: Tasks 1-4.

- [x] Task 6: Implement sleep, help, attack, flee, and terminal objective death.
  - Deliverable: apply the exact recovery, healing, hit, damage, escape, capacity, fatigue, no-op, and outcome-status rules above; generate purpose-separated resolved effects in simulation and pass only world-owned facts to pure rules. Select flee destinations against the current evolving eligible set after success, classify earlier move/death/capacity invalidation as conflict, emit one-to-many pending attack/`Died` details under the same action cause, and prohibit revival or later dead-body actions.
  - Files: `src/world/_operations.py`, `src/world/_rules.py`, `src/world/_transitions.py`, `src/world/events.py`, `src/simulation/actions.py`, `src/simulation/engine.py`, `src/simulation/lifecycle.py`, `tests/unit/test_world_rules.py`, `tests/unit/test_world_batch.py`, `tests/unit/test_world_engine_admission.py`.
  - Logging: add stable DEBUG resolution codes for hit/miss, flee success/failure, healing, and death cause; INFO only aggregate tick/death counts; WARN rejected misuse; ERROR impossible duplicate-death or invalid-effect candidates. Log IDs and bounded summaries, never exact random draws or complete physiology.
  - Dependencies: Tasks 3-5.

- [x] Task 7: Implement the pure autonomous physical step.
  - Deliverable: add a protected private world module that accepts world-owned `PhysicalRules`, primitive tick/hour context, and pre-resolved weather effects, never `SimulationRunConfig`, `Tick`, logger, or RNG. Apply scheduled weather changes, capped regeneration, per-body needs damage, exact sheltered temperature formula, exposure, and atomic death in canonical order; skip temperature after needs death and emit no pending weather/regeneration event when the value is unchanged. Return evolving state plus pending system details/causes without revision or final event allocation.
  - Files: `src/world/_physical.py` (new), `src/world/_state.py`, `src/world/events.py`, `pyproject.toml`, `tests/architecture/boundary_checker.py`, `tests/architecture/test_world_authority.py`, `tests/architecture/test_boundary_checker.py`, `tests/unit/physical/test_physiology.py` (new), `tests/unit/physical/test_survival_and_death.py` (new).
  - Logging: the physical step is log-free; architecture tests prohibit logging, randomness, clocks, persistence, and any `simulation` import from the new module. Simulation logging is added only in Task 8.
  - Dependencies: Tasks 1-4.

- [x] Task 8: Integrate autonomous effects into detached engine candidate preparation.
  - Deliverable: generate per-location weather effects from purpose/version-scoped streams, resolve actions first, invoke the pure physical step, and send the combined action/system pending stream through Task 4's single finalizer. Support no-submission autonomous ticks, event-only actions followed by autonomous mutation, all-dead no-op ticks, one revision/publication boundary, and persistence rollback without partially publishing physical changes. Pass tick/rules observation context from `WorldEngine.observe()`.
  - Files: `src/simulation/engine.py`, `src/simulation/actions.py`, `src/simulation/clock.py`, `src/simulation/lifecycle.py`, `src/world/_perception.py`, `tests/unit/test_world_engine.py`, `tests/unit/test_world_batch.py`, `tests/unit/test_world_perception.py`, `tests/unit/test_persistent_simulation_service.py`.
  - Logging: engine emits DEBUG start/end summaries per effect family and counts of changed resources/weather/bodies/deaths, one INFO tick commit, WARN lifecycle misuse, and ERROR stable physical-prepare/finalize codes. Never log seeds, draws, payloads, inventories, or exact body state.
  - Dependencies: Tasks 2, 4, 5, 6, and 7.

### Phase 3: Serialization, Replay, and Durability

- [x] Task 9: Implement version-dispatched domain/journal codecs and strict journal verification.
  - Deliverable: preserve legacy canonical encoders/hashes; separate accepted decode/restore versions from the current new-write versions; round-trip physical rules, models, closed causes, and every schema-v3 detail. Dispatch audit-v1 decode-only, replay-v2 projection, and replay-v3 projection without mixed-version runs. On reads, verify event payload hashes, normalized event identity, tick/sequence/revision consistency, tick payload hashes, predecessor links, and recomputed commit hashes with the codec selected by the manifest; add corruption tests for every layer.
  - Files: `src/simulation/serialization.py`, `src/simulation/journal.py`, `src/simulation/persistence.py`, `src/simulation/replay.py`, `src/persistence/readers.py`, `tests/unit/test_v1_domain_serialization.py`, `tests/unit/test_persistence_serialization.py`, `tests/unit/test_persistence_contracts.py`, `tests/unit/test_replay_service.py`, `tests/integration/test_tick_journal.py`.
  - Logging: codecs/hash helpers remain log-free; replay/read boundaries log DEBUG version selection, IDs, counts, and hash prefixes, INFO successful verification, WARN supported legacy dispatch, and ERROR stable corruption/version codes without canonical bytes, seeds, or full events.
  - Dependencies: Tasks 1, 3, 4, and 8.

- [x] Task 10: Make checkpoints candidate-owned and preserve replay continuation.
  - Deliverable: construct optional checkpoints from `_PreparedTickCandidate.next_snapshot` (preferred) rather than caller-supplied world content; otherwise require exact candidate equality and verify the original snapshot integrity before binding. Persist physical rules/state, restore without invoking rules or RNG, and use `snapshot.predecessor_commit_hash` when replay starts at an exact head checkpoint with no later commits. Cover event-only actions plus autonomous mutations, exact-head durable reopen/append, persistence failure rollback, and candidate/checkpoint mismatch rejection.
  - Files: `src/simulation/service.py`, `src/simulation/journal.py`, `src/simulation/persistence.py`, `src/simulation/replay.py`, `src/simulation/engine.py`, `tests/unit/test_checkpoint_restoration.py`, `tests/unit/test_replay_service.py`, `tests/unit/test_persistent_simulation_service.py`, `tests/integration/test_simulation_persistence_replay.py`.
  - Logging: service/replay logs DEBUG checkpoint source, IDs, tick/revision, versions, and hash prefixes, INFO durable restore/append completion, WARN supported fallback, and ERROR stable mismatch/integrity codes without snapshot content or seeds.
  - Dependencies: Tasks 8-9.

- [x] Task 11: Persist physical configuration and normalized state with a mandatory migration.
  - Deliverable: add a canonical versioned run-config/manifest representation and normalized snapshot columns/tables for topology, capacities, environment, item/resource kinds, quantities/regeneration, and carry capacity. Update ORM writers/readers, constraints, append-only protections, and direct repository validation for world/schema/revision/event consistency. Add a migration from revision `0002` with explicit legacy backfill defaults, upgrade tests containing representative legacy run/snapshot/event rows, updated head/table assertions, and v2 replay after upgrade.
  - Files: `src/persistence/orm.py`, `src/persistence/sqlalchemy.py`, `src/persistence/readers.py`, `alembic/versions/` (new revision), `tests/unit/test_sqlalchemy_repository.py`, `tests/integration/test_migrations.py`, `tests/integration/test_append_only.py`, `tests/integration/test_tick_journal.py`, `tests/integration/test_simulation_persistence_replay.py`.
  - Logging: repository boundaries log DEBUG row/count/version metadata and hash prefixes, INFO migration/append completion through existing orchestration, WARN recoverable legacy backfill selection, and ERROR constraint/integrity codes. Migration tests pass the validated disposable DSN directly to Alembic and never rely on ambiguous ambient URLs.
  - Dependencies: Tasks 1-3 and 9-10.

### Phase 4: Verification and Documentation

- [x] Task 12: Add property and rule tests for conservation, actions, physiology, and death.
  - Deliverable: build typed physical-world fixtures and Hypothesis state transitions; prove item placement/load conservation, resource extraction/regeneration bounds, no mutation on rejection/conflict, exact needs/temperature/health formulas, all requested action outcomes, one-to-many final event sequencing, immediate/autonomous death, exactly-one `Died`, and terminal dead-body behavior. Explicitly cover day boundaries 05/06 and 17/18; weather ticks 0/5/6/11; visibility `0.5`; quantities `0`, `0.5`, `1`, and max; full/contended capacities; slots vacated earlier in a tick; dead-body capacity/inventory; combined-needs versus exposure death; shelter `0`/`1`; ties-to-even rounding; action no-ops; and all-dead ticks.
  - Files: `tests/physical_helpers.py` (new), `tests/unit/physical/__init__.py` (new), `tests/unit/physical/test_conservation_invariants.py` (new), `tests/unit/physical/test_action_effects.py` (new), `tests/unit/physical/test_action_rejections.py` (new), `tests/unit/physical/test_action_conflicts.py` (new), `tests/unit/physical/test_physiology.py` (new), `tests/unit/physical/test_survival_and_death.py` (new), plus existing world rule/state suites as needed.
  - Logging: use `caplog` to require DEBUG physical resolution codes and INFO aggregate commits, assert ERROR diagnostics for invalid candidates, and maintain forbidden-fragment assertions for snapshots, inventories, payloads, seeds, and RNG draws.
  - Dependencies: Tasks 5-8. Domain tests do not wait for persistence work.

- [x] Task 13: Prove seeded determinism, effect-complete replay, durability, and target world scale.
  - Deliverable: test same-seed byte-for-byte trajectories, selected golden seed-pair divergence, distinct raw stream samples/scopes, rules-fingerprint separation, mapping-order independence, and replay with RNG/rules patched to fail if called. Exercise 5 agents/10 locations and 10 agents/20 locations over mixed movement, contention, search, consumption, combat, flee, weather, regeneration, survival, and death; compare complete fingerprints across live state, bootstrap replay, legacy-v2 restore, checkpoint replay, and PostgreSQL round trips. Verify autonomous-only persistence, exact-head continuation, migration upgrade, and failure rollback.
  - Files: `tests/unit/physical/test_seeded_outcomes.py` (new), `tests/unit/physical/test_event_effect_completeness.py` (new), `tests/unit/physical/test_physical_projection.py` (new), `tests/unit/physical/test_world_scale.py` (new), `tests/unit/test_reproducibility_contracts.py`, `tests/unit/test_simulation_replay_determinism.py`, `tests/integration/test_physical_simulation_replay.py` (new), `tests/integration/test_physical_event_storage.py` (new), `tests/integration/test_scaled_world_persistence.py` (new), `tests/integration/test_tick_journal.py`.
  - Logging: assert deterministic diagnostic codes/counts independently of seed outcomes, DEBUG scoped-purpose metadata without draw values, INFO durable completion, and ERROR rollback/corruption diagnostics with no sensitive payload leakage.
  - Dependencies: Tasks 8-12.

- [x] Task 14: Document the physical model, compatibility contract, and developer workflow.
  - Deliverable: replace the deferred physical-action matrix; document topology, capacities, conservation equations, exact action and physiology rules, tick ordering, weather/day visibility, seeded scopes, terminal objective death, schema-v3 compatibility, snapshot contents, and test commands. Explicitly state that psychological fear of death is not implemented. Resolve the existing seed-logging documentation inconsistency in favor of never logging seeds.
  - Files: `docs/architecture.md`, `docs/persistence.md`, `docs/development.md`, `docs/configuration.md`, `README.md`.
  - Logging: document DEBUG/INFO/WARN/ERROR responsibilities, `PALIMPSEST_LOG_LEVEL` control, stable diagnostic fields, and prohibited seed/draw/payload fields; no code-level logging changes beyond alignment found during the checkpoint.
  - Dependencies: Tasks 1-13. This is the mandatory documentation checkpoint and should be routed through `$aif-docs`.

## Acceptance Criteria
- A bootstrap containing 5-10 registered bodies, 10-20 connected locations, multiple item kinds, and finite/renewable resource nodes validates and runs without bypassing `WorldEngine`.
- Every requested action has explicit applied/rejected/conflicted behavior and no physical command remains `DEFERRED_POLICY`.
- Equivalent bootstrap, configuration, seed, and ordered submissions produce identical resolutions, immutable events, snapshots, hashes, and replayed state; unrelated random scopes do not perturb one another.
- All action and autonomous effects are finalized together: one mutation decision, at most one revision increment, globally contiguous event sequences, and one-to-many events under explicit action/system causes.
- Items and resource quantities obey placement/load/depletion/regeneration conservation, including contention and failed actions.
- Physiology advances on every committed tick for every living body, death is emitted as an objective event exactly once, and dead state is terminal without any fear/emotion feature.
- Day/night, weather, visibility, and regeneration follow the rule contract and are replayable from recorded facts.
- Live execution, bootstrap replay, checkpoint replay, and persisted replay produce the same complete objective state without invoking current rules or RNG during projection.
- Audit-v1 remains decode/export-only, replay-v2 histories remain restorable after migration, and new physical histories use replay-v3 without mixed schemas or changed legacy hashes.
- `uv run ruff check src tests`, `uv run mypy`, the default pytest suite, architecture tests, and the new PostgreSQL integration scenarios pass.
