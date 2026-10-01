# Implementation Plan: Basic Physical Production

Branch: main
Created: 2026-09-30
Improved: 2026-09-30 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete roadmap milestone; this plan adds a small opt-in production catalog and leaves `multi_hop_testimony_tracking` unowned.

## Compatibility contract

This plan adds experimental production on top of the existing physical world. It must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants intact. `WorldEngine` remains the only objective mutation authority. It alone decides available materials, action duration, success probability, inventory changes, and produced objects. Cognition never receives `WorldState`, `PhysicalRules`, `ProductionCatalog`, or another agent's recipe beliefs.
2. Do not own a capability flag. Do not add a `V2CapabilityFlags` field. `multi_hop_testimony_tracking` stays unimplemented and still fails closed with `capability_unimplemented`. Off for this feature is an empty catalog plus `ProductionKnowledgeMode.DISABLED`. That pair does not change commands, probabilities, fatigue, events, memories, beliefs, or audits.
3. V1 regression gate stays green under flags-off, production mode `DISABLED`, empty catalog, and tracing-off. Catalog A–E and the reference scenario keep their current `exact_trajectory_hash` values. Do not append a production experiment to `tests/unit/test_v1_regression_gate.py`.
4. `runner-config-v13` is the only new runner schema. It is emitted only when the production catalog is non-empty or some agent's `ProductionKnowledgeMode` is `DETERMINISTIC`. `RUNNER_SCHEMA_VERSION` stays `runner-config-v4`. v13 cognition keys are the v12 key set plus `production_knowledge_mode` and `production_catalog`. Default writes stay replay-v5. `EVENT_SCHEMA_REPLAY_V6` is accepted and is written only by a run whose catalog is non-empty. `CURRENT_PHYSICAL_EVENT_SCHEMA_VERSION` stays replay-v5. Do not mix schemas inside one run.
5. No scripted emergence. Recipes are configuration. There is no profession, role, culture, or technology-tier label, and no milestone that grants recipes. Agents do not receive the catalog on `Observation`.
6. No LLM → world shortcuts. A provider may only choose a recipe id already on the owner's belief set. The provider never emits inputs, a duration, a probability, an `AgentCommand` the policy did not already allow, or a world mutation.
7. Experiments stay reproducible. Production is a unit-level world, not a new catalog arm. Paired checks share seed and scenario. Recipe beliefs are not fed back into the engine.
8. Optional cognition tracing stays outside the objective fold. Do not insert a `ComponentKind` or an ordinal in `_STAGE_ORDER`. Do not add a `CognitionTraceStageKind`. Do not bump `COGNITION_TRACE_SUMMARY_SCHEMA` or add an Alembic revision. Tracing on versus off must not change `exact_trajectory_hash` when production is off.

## Goal

Add a small, configurable production layer the engine resolves and an observer can display. Agents learn recipe ids or are seeded with beliefs, including false ones. They do not start with the transformation table.

Closed actions:

- harvest
- craft
- build
- repair
- store

Locked example transformations, used by tests and by `example_production_catalog()`:

- resource name `wood` → one `wood` material
- resource name `stone` → one `stone` material
- `wood` material + `stone` material → one tool
- one `food` item → stored food on a store structure
- one `material` item → a shelter structure at the actor's location
- one `material` item → repair of that shelter

`Location` stays a logical graph node. Structures are attached to a location id. No simulation x/y coordinates.

## Design Decisions (locked)

- **Empty catalog is the default.** `WorldEngine` takes `ProductionCatalog` as a keyword-only argument defaulting to `None`. `None` and an empty catalog are the same. Default bootstrap, V1 worlds, and `runner-config-v4` through `v12` pass neither. Those runs never sample `production_success` and never write replay-v6. A production command on an empty catalog rejects with `production_disabled` and commits nothing.
- **Catalog is not world state.** Recipes do not live on `WorldState` and are not replayed as events. A non-empty catalog is stored only on `runner-config-v13` and passed into the engine. Unit tests may pass the same catalog directly.
- **Six recipes, five actions.** The catalog is a tuple of `ProductionRecipe`. Duplicate recipe ids fail closed with `duplicate_recipe_id`. The example catalog is exactly:

| `recipe_id` | action | duration | success | inputs | output |
| --- | --- | --- | --- | --- | --- |
| `harvest_wood` | harvest | 1 | 0.80 | resource name `wood` at the actor's location | item kind `material`, name `wood` |
| `harvest_stone` | harvest | 1 | 0.80 | resource name `stone` at the actor's location | item kind `material`, name `stone` |
| `craft_tool` | craft | 2 | 0.70 | held `wood` and held `stone` | item kind `tool`, name `tool`, role `strike` |
| `build_shelter` | build | 1 | 1.00 | one held item kind `material` | structure kind `shelter` at the actor location |
| `repair_shelter` | repair | 1 | 1.00 | one held item kind `material` | integrity `+0.25` on the named shelter |
| `store_food` | store | 1 | 1.00 | one held item kind `food` | stored quantity `+1` on a store structure at the location |

  `build_store` is not a seventh recipe. The `store_food` recipe creates a store structure on first success at that location and then adds quantity. A second store at the same location is `store_already_present`. A second shelter at the same location is `shelter_already_present`.

- **Commands stay structured.** Add exact command classes `Harvest`, `Craft`, `Build`, `Repair`, and `Store` to the closed `AgentCommand` union, bringing it from fifteen variants to twenty. Each carries `recipe_id: RecipeId`. `Harvest` also carries `resource_id`. `Repair` also carries `structure_id`. `Store` also carries `item_id`. `Craft` and `Build` name only the recipe. The engine selects matching inputs. Raw mappings still fail `require_agent_command`. The same change lands with admission, rule evaluation, event details, and codecs.
- **RecipeId.** A new validated id in `world.identifiers`. Pattern is one lowercase letter followed by up to 31 characters from `[a-z0-9_]`. It is not an `EntityId` and is not a physical object.
- **WorldEngine owns the outcome.** Admission still checks liveness, placement, and one action slot. Production checks then run only when the catalog is non-empty:
  - unknown recipe id → reject `unknown_recipe`, no event
  - recipe action does not match the command → reject `recipe_action_mismatch`, no event
  - actor already has a pending job → reject `actor_busy` for every command, including move and eat, no event
  - missing or insufficient materials, resource quantity below one, or target not at the actor's location → reject `materials_unavailable`, no event
  - repair of integrity `1` → reject `structure_intact`, no event
  Success probability is the recipe value. When it is below `1`, draw one Bernoulli from purpose `production_success` in `src/simulation/actions.py`. A new purpose is a separate stream, so existing purposes stay bit-identical. When the recipe probability is `1`, do not draw. Harvest and craft are the only recipes below `1`. A failed harvest emits `ResourceHarvested` with `success=false` and no created item. A failed craft emits `CraftStarted` with `success=false` and no `ItemCrafted`. Build, repair, and store do not draw and do not emit a failure event. Success consumes inputs at resolution time. `store_food` emits only `ItemStored`, with `structure_id` and `resulting_stored_quantity`, and does not also emit `StructureBuilt`.
- **Duration.** `duration_ticks` is an integer `>= 1`. A matching held tool of role `strike` reduces duration by `1`, with a minimum of `1`. Only `craft_tool` declares `tool_role=strike`, so only that recipe changes. In the example catalog that changes duration from `2` to `1`. No tool leaves duration at `2`.
  - Duration `1`: result event is committed in the same tick as the attempt.
  - Duration `2`: tick `T` commits `CraftStarted` and consumes inputs. Tick `T+1` commits `ItemCrafted` during the autonomous step, before needs and exposure, and clears the job. The actor is busy on tick `T+1` before that completion. If the actor is dead at the due tick, clear the job and do not emit `ItemCrafted`.
- **Skill hooks that already exist.** When `SkillLearningMode` is `DISABLED`, do not call skill adjustment helpers for production. When it is `DETERMINISTIC`, crafting level adjusts only `craft_tool` success: `clamp_unit_interval(0.70 * (1 + probability_gain * crafting_level))`. Building level adjusts only `build_shelter` and `repair_shelter` success the same way, using their base `1.0`, which stays `1.0`. At level `0` the value equals the recipe base. Foraging, navigation, and the other existing modifiers stay on their current formulas. Do not call `adjusted_search_probability`. Do not change `search_success`.
- **Tools.** Add `ItemKind.TOOL = "tool"`. Old item kinds still decode. Tool role is not a field on `Item`, so v1 item key sets stay unchanged. The role is a `ToolMark` created by the `craft_tool` output and kept in the production fold. A later harvest or craft sees it only when that tool is in the actor's inventory. Tools do not change carry rules beyond ordinary `ItemLoad`. Example tool load is `1`.
- **Structures are location-based.** `Structure` has `entity_id`, `location_id`, `kind` (`shelter` or `store`), `integrity` in `[0, 1]`, and `stored_quantity` as a non-negative integer. No coordinates. Shelter starts at integrity `0.75`. Store starts at integrity `1` and stored quantity `1` on first `store_food`, then only quantity increases. Structure ids join the existing global `EntityId` uniqueness check. `Item.holder_id` still must be a body. Stored food is a quantity on the structure, not an `Item`. The consumed food item is removed. Withdrawal is out of scope.
- **Shelter and exposure.** `_physical.py` keeps the current temperature expression when the location has no shelter structure. When a shelter is present, replace only `location.shelter_factor.value` in that product with `clamp_unit_interval(location.shelter_factor.value + 0.25 * integrity)`. Do not write `Location.shelter_factor`. Do not add storm decay.
- **Events.** Add details `ResourceHarvested`, `CraftStarted`, `ItemCrafted`, `StructureBuilt`, `StructureRepaired`, and `ItemStored`. Each is effect-complete on replay-v6: resulting quantities, resulting holder or structure ids, `success`, and `duration_ticks`. `CraftStarted.success` false has no later `ItemCrafted`. These details are illegal on schemas below v6 (`invalid_event_schema_version`). Domain payloads have no fields named `pixels`, `sprite`, `animation`, `dx`, `dy`, `screen_x`, or `screen_y`.
- **Snapshots.** `PERSISTENCE_CODEC_VERSION` stays `v2`. Empty-catalog checkpoints keep today's exact journal key set. A non-empty catalog writes accepted codec `v3` and adds exactly three keys, `structures`, `production_jobs`, and `tool_marks`, plus `event_schema_version` `6`. v2 decode rejects those keys. v3 decode requires them. `PROJECTOR_VERSION` stays `v2`. New match arms run only for v6 details.
- **Agents do not receive the catalog.** `Observation` gains no recipe list, no input vector, and no duration or probability. Visible structures are `ObservedStructure` records (`entity_id`, `location_id`, `kind`, `integrity`, `stored_quantity`) under the existing `CONTENT_VISIBILITY_THRESHOLD` of `0.5`, the same gate as local resources. Production occurrences put `recipe_id` in `public_facts` for the actor and for a bystander who passes that visibility check. The actor always sees their own production occurrence.
- **Beliefs are separate.** `RecipeBeliefSet` is owner-scoped in `agents/cognition/production.py`. It stores recipe ids and a `supported` flag. It does not store inputs, durations, or probabilities. Seed entries may name ids absent from the catalog. The updater reads `recipe_id` only from `ObservedOccurrence.public_facts`, or from one `Talk` / `Ask` / `Tell` relation with predicate `recipe`. The predicate is not `instruct`. Teaching mode is not required. An unknown taught id is still stored. It rejects `WorldState` and `ProductionCatalog` by type name, without importing `ProductionCatalog`. Another owner's set is rejected the same way.
- **Cognition emits the new commands only when enabled.** `ProductionKnowledgeMode` is `DISABLED` or `DETERMINISTIC`, default `DISABLED`. `DISABLED` leaves `ActionDirection`, tie ranks, and `CommandPlanner` outputs unchanged. `DETERMINISTIC` may compile one production command only when the recipe id is supported on that owner, a matching visible target exists on the observation, and no higher existing veto fires. Unsupported ids and unseeded ids become `Wait`. A direct engine submission of a true recipe still resolves from the catalog. Belief is not an engine input. A test with no belief and a legal scripted `Craft(craft_tool)` succeeds when materials exist. A test with belief `craft_gold` submits that id and the engine rejects `unknown_recipe`.
- **Runner schema.** v13 is accepted only when the catalog is non-empty or some mode is `DETERMINISTIC`. A catalog present with every mode `DISABLED` is still v13, so resume can rebuild the catalog. v12 and earlier reject the new keys. Default write stays `runner-config-v4`. Do not add the catalog to `SimulationRunConfig`. `v1_regression_profile` still checks flags and tracing only. Skill learning stays legal on v11, v12, and v13. Teaching stays legal on v12 and v13. `v12_requires_teaching` stays an equality check, so a teaching-only run still writes v12.
- **Observer protocol stays v1.** Do not change `OBSERVER_PROTOCOL_VERSION`. Existing semantic types stay. Add the six semantic types to the closed Python set. The current Godot parser ignores unknown event types and unknown world keys, so a frame that adds `structures` still parses as protocol v1. This plan does not edit `clients/godot-observer/`.
- **Presentation is a projection.** `EntityPresentation` on observer items, resources, and structures may carry `visual_category`, `icon_key`, and `size_category`. The catalog is `src/observer/presentation.py`, keyed by kind and name token. Missing entries leave presentation empty. It is not stored on `Item`, `Resource`, `Structure`, or `Location`, and it is not copied onto `WorldEvent`. `ObserverEvent` may add optional `recipe_id` and `structure_id`. It still rejects `pixels`, `sprite`, `animation`, `dx`, `dy`, and any `AGENT_UN` type. API models use those optional ids. `ObserverEvent.public_mapping` includes `recipe_id` and `structure_id` only when they are set. Do not switch observer responses to `exclude_none`. Do not rewrite `clients/godot-observer/fixtures`. Golden event names stay a subset of `SEMANTIC_EVENT_TYPES`.

### Locked numbers

- Harvest success `0.80`. Craft success `0.70`. Build, repair, and store success `1.00`.
- Tool duration reduction `1`, minimum duration `1`.
- Shelter bonus coefficient `0.25`. Initial shelter integrity `0.75`. Repair delta `0.25`, clamped to `1`.
- Example material and tool `ItemLoad` is `1`.
- Created ids use `derive_entity_id(config, "produced-item", ...)` or `derive_entity_id(config, "produced-structure", ...)`. Search keeps the key `foraged-item`. Do not add an allocator.

## Non-Goals

- A survival game: hunger crafting chains, tech trees, fuel, decay, withdrawal, combat tools, or multi-step production beyond the six recipes
- Owning `multi_hop_testimony_tracking` or adding a `V2CapabilityFlags` field
- Putting a production experiment on the V1 regression gate
- Giving every agent the catalog, or letting belief change a Bernoulli input
- Exact x/y coordinates, sprite commands, or animation payloads on domain events
- Editing the Godot client or bumping `observer-protocol-v1`
- An Alembic revision or a cognition-trace stage
- Changing search so that it stops extracting resources

## Commit Plan

- **Commit 1** (after tasks 1–3 and 11): `feat(world): add opt-in production recipes and resolution`
- **Commit 2** (after tasks 4–6): `feat(cognition): learn recipe beliefs without the catalog`
- **Commit 3** (after tasks 7–9): `feat(observer): project production events without coordinates`
- **Commit 4** (after task 10): `docs(world): describe basic production and observer facts`

Each checkpoint is a git commit on `main` created when those tasks are done. Do not squash them into one commit at the end.

## Tasks

### Phase 1: Catalog, Events, and Resolution

- [x] Task 1: v2- Define the production catalog and commands.
  - Deliverable: `RecipeId`, `ProductionRecipe`, `ProductionCatalog`, `ToolRole`, `StructureKind`, and `Structure` in `src/world/production.py` (public facade re-export, no private-world import). `example_production_catalog()` returns the six locked recipes and nothing else. Commands `Harvest`, `Craft`, `Build`, `Repair`, and `Store` join `AgentCommand` and `require_agent_command`. Constructors reject a foreign recipe id, a duration below `1`, a probability outside `[0, 1]`, and a command whose action token does not match its class. `ItemKind.TOOL` is added. `world/__init__.py` exports the new commands and catalog types.
  - Logging: logger `world.production`. DEBUG on catalog build with `recipe_count` and the SHA-256 digest of the canonical sorted recipe-id list. Do not use Python `hash()`. ERROR on validation with field name and reason code. Do not log item names at INFO.
  - Files: `src/world/identifiers.py`, `src/world/production.py`, `src/world/actions.py`, `src/world/values.py`, `src/world/__init__.py`, `tests/unit/test_production_catalog.py`.

- [x] Task 2: v2- Add replay-v6 production events.
  - Deliverable: the six detail types join `EventDetails` and are effect-complete only when `schema_version` is `EVENT_SCHEMA_REPLAY_V6`. `CURRENT_PHYSICAL_EVENT_SCHEMA_VERSION` remains `5`. A v5 encoder rejects the new details with `invalid_event_schema_version`. A failed harvest is `ResourceHarvested` with `success=false` and no created item. A failed craft is `CraftStarted` with `success=false` and no later `ItemCrafted`. Build, repair, and store have probability `1` and emit no failure details. `ItemStored` carries `structure_id` and `resulting_stored_quantity` and is the only event for `store_food`. Domain codecs in `src/simulation/serialization.py` accept v6 and still reject unknown keys on v5. `_encode_command` and `_decode_command` gain exact-key arms for tags `harvest`, `craft`, `build`, `repair`, and `store`. Existing command tags stay unchanged. `SUPPORTED_EVENT_SCHEMA_VERSIONS` and `REPLAYABLE_EVENT_SCHEMA_VERSIONS` include `6`. Payloads have no presentation field.
  - Logging: logger `world.events`. DEBUG `production_event_built schema_version=%s kind=%s success=%s`. ERROR `invalid_event_schema_version` with kind and schema. No coordinates.
  - Depends on task 1.
  - Files: `src/world/events.py`, `src/simulation/serialization.py`, `tests/unit/test_production_events.py`.

- [x] Task 3: v2- Resolve harvest, craft, build, repair, and store in the engine.
  - Deliverable: private rule and operation arms in `src/world/_rules.py` and `src/world/_operations.py`, and admission wiring in `src/simulation/engine.py`, follow the existing command matrix. The catalog argument is keyword-only and defaults to `None`. An empty catalog rejects `Harvest`, `Craft`, `Build`, `Repair`, and `Store` with `production_disabled` and commits nothing. A non-empty catalog applies the locked success, duration, tool, skill, and consumption rules. `actor_busy` rejects every command while a job is pending. `production_success` is sampled only for a recipe whose probability is below `1`. Do not call `adjusted_search_probability`. Shelter exposure uses the structure bonus only when a shelter exists at that location. Pending craft jobs complete on the due tick before needs. If the actor is dead at that tick, clear the job and do not emit `ItemCrafted`. Created ids use `derive_entity_id(config, "produced-item", ...)` or `derive_entity_id(config, "produced-structure", ...)`. Search keeps `foraged-item`.
  - Logging: logger `world._production` for resolution and `simulation.engine` for the draw. DEBUG `production_resolved recipe_id=%s success=%s duration=%s reason_code=%s`. INFO one line per committed production event with event id, tick, and kind. WARNING `actor_busy`, `materials_unavailable`, and `production_disabled` with actor id and recipe id. Do not log probabilities at INFO.
  - Depends on tasks 1 and 2.
  - Files: `src/world/_production.py`, `src/world/_rules.py`, `src/world/_operations.py`, `src/world/_physical.py`, `src/world/_state.py`, `src/simulation/actions.py`, `src/simulation/engine.py`, `tests/unit/test_production_resolution.py`.

- [x] Task 11: v2- Project visible structures and recipe ids.
  - Deliverable: add `ObservedStructure` with `entity_id`, `location_id`, `kind`, `integrity`, and `stored_quantity`. Project structures at the observer's location when `effective_visibility` is at least `CONTENT_VISIBILITY_THRESHOLD` (`0.5`), the same gate local resources already use. For production occurrences only, put `recipe_id` in `public_facts` for the actor and for a bystander who passes that visibility check. Do not add a recipe list, inputs, durations, or probabilities to `Observation`. Existing occurrence facts for non-production events stay unchanged.
  - Logging: logger `world._perception`. DEBUG `production_observed recipe_id=%s structure_count=%s`. Do not log item names at INFO.
  - Depends on task 3.
  - Files: `src/world/_perception.py`, `src/world/observations.py`, `tests/unit/test_production_perception.py`.

### Phase 2: Replay, Beliefs, and Commands

- [x] Task 4: v2- Fold production state through replay without changing v2 checkpoints.
  - Deliverable: structures, tool marks, stored quantities, and pending jobs fold from v6 events plus the catalog. Codec `v3` adds exactly `structures`, `production_jobs`, and `tool_marks`. Resume of a v3 checkpoint restores those three collections and then folds later events. A v2 checkpoint still uses the current exact key set, rejects the three new keys, and restores empty production state. A catalog mismatch on resume fails with `production_catalog_mismatch`. Replaying a v5 stream with an empty catalog yields the same projected world as today.
  - Logging: logger `simulation.replay`. DEBUG `production_fold tick=%s structure_count=%s job_count=%s`. ERROR `production_catalog_mismatch` with the SHA-256 catalog digest only. No seeds.
  - Depends on task 3.
  - Files: `src/world/_replay.py`, `src/simulation/replay.py`, `src/simulation/persistence.py`, `src/simulation/journal.py`, `tests/unit/test_production_replay.py`.

- [x] Task 5: v2- Store recipe beliefs apart from the catalog.
  - Deliverable: `ProductionKnowledgeMode` and `RecipeBeliefSet` in `agents/cognition/production.py`. The updater accepts the owner's observation and optional seed ids. It records a `recipe_id` from `ObservedOccurrence.public_facts` or from a single relation predicate `recipe`. It does not import `ProductionCatalog`. It raises `TypeError` when the argument's type name is `WorldState` or `ProductionCatalog`, and when the set owner does not match. `instruct` remains a skill predicate. This module does not import `llm`. Beliefs checkpoint on the in-memory runtime the same way competence does, without an Alembic revision and without a subjective schema bump. `DISABLED` builds no set.
  - Logging: logger `agents.cognition.production`. DEBUG `recipe_belief_updated owner_id=%s recipe_count=%s supported_count=%s`. WARNING `recipe_relation_ignored` with reason code. No utterance text.
  - Depends on tasks 2 and 11.
  - Files: `src/agents/cognition/production.py`, `src/agents/cognition/configuration.py`, `src/simulation/agent_runtime.py`, `tests/unit/test_recipe_beliefs.py`.

- [x] Task 6: v2- Attempt production only from believed recipe ids.
  - Deliverable: when mode is `DETERMINISTIC`, deliberation may compile one of the five commands for a supported recipe id with a visible target from the observation. Unsupported and unknown believed ids compile to `Wait`. `DISABLED` does not add directions to the futures that exist today and does not change tie ranks among the current directions. The engine test from the design still succeeds for a scripted true recipe with an empty belief set, and fails `unknown_recipe` for `craft_gold`. `allow_provider` defaults false. When true, schema `production.selection.v1` may return only a recipe id already supported. Unknown tokens set `fallback_used` and keep the deterministic choice. Prompt package `llm/prompts/production/v1/`. Provider selection lives in `agents/cognition/production_selection.py` and imports the `llm` facade. `CognitiveLoop` loads that module only when `allow_provider` is true. Add `agents.cognition.production_selection -> llm` to `ignore_imports` in `pyproject.toml`. Do not import `llm.models`.
  - Logging: logger `agents.cognition.production`. DEBUG `production_command_selected recipe_id=%s command_kind=%s`. INFO `production_command_withheld reason_code=%s`. LLM path logs `production_llm_start`, `production_llm_complete`, and `production_llm_rejected` with counts and reason codes only.
  - Depends on tasks 3, 5, and 11.
  - Files: `src/agents/cognition/deliberation.py`, `src/agents/cognition/loop.py`, `src/agents/cognition/production_selection.py`, `llm/prompts/production/v1/`, `pyproject.toml`, `tests/unit/test_production_commands.py`.

### Phase 3: Runner, Observer, and Docs

- [x] Task 7: v2- Accept production only on runner-config-v13.
  - Deliverable: `runner-config-v13` carries every v12 cognition key plus `production_knowledge_mode` and `production_catalog`. It is emitted only for a non-empty catalog or a `DETERMINISTIC` production mode. v4 through v12 reject those keys. Skill learning is accepted on `{v11, v12, v13}`. Teaching is accepted on `{v12, v13}`. `v12_requires_teaching` stays an equality check, so a teaching-only config still writes v12. The runner passes the catalog into `WorldEngine` and the mode into cognition. Empty catalog leaves the engine argument `None` and the event schema at replay-v5. Codec `v3` is written only for a non-empty catalog. `simulation.compatibility` lists v13 and codec `v3` as accepted restores without making them the default write. `tests/unit/test_v1_regression_gate.py` is not extended.
  - Logging: logger `simulation.runner`. INFO `production_config schema_version=%s recipe_count=%s mode_count=%s`. ERROR `production_catalog_mismatch` and `unsupported_schema_version` with schema and reason code. DEBUG is ids and counts. No seeds.
  - Depends on tasks 4, 5, and 6.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/runner.py`, `src/simulation/compatibility.py`, `src/simulation/__init__.py`, `tests/unit/test_production_runner.py`, `tests/unit/test_compatibility_matrix.py`.

- [x] Task 8: v2- Project production entities and semantic events.
  - Deliverable: `ObjectiveFacts` and `ObjectiveScene` gain `structures`, default empty, so existing constructors keep working. `observer.project_frame` adds ordered `ObserverStructure` records at `location_id` and optional `EntityPresentation` from `src/observer/presentation.py`. `adapt_event` maps the six domain kinds to `RESOURCE_HARVESTED`, `CRAFT_STARTED`, `ITEM_CRAFTED`, `STRUCTURE_BUILT`, `STRUCTURE_REPAIRED`, and `ITEM_STORED`. `ObserverEvent` gains optional `recipe_id` and `structure_id`. `public_mapping` includes those two keys only when they are set. Do not switch observer `model_dump` calls to `exclude_none`. Protocol version stays `observer-protocol-v1`. API schemas mirror the optional ids. Update `tests/unit/test_observer_contracts.py` so `len(SEMANTIC_EVENT_TYPES)` is `26`. Location layout slots are unchanged. No screen coordinates are read from world models.
  - Logging: logger `observer.project` and `observer.adapt`. DEBUG `production_projected structure_count=%s event_kind=%s`. ERROR `unknown_event_kind` and `presentation_instruction_forbidden`. Do not log icon keys at INFO.
  - Depends on tasks 2 and 4.
  - Files: `src/simulation/observer_facts.py`, `src/observer/version.py`, `src/observer/contracts.py`, `src/observer/adapt.py`, `src/observer/project.py`, `src/observer/presentation.py`, `src/api/observer_schemas.py`, `src/api/observer_service.py`, `tests/unit/test_production_observer.py`, `tests/unit/test_observer_contracts.py`.

- [x] Task 9: v2- Prove observer compatibility without a Godot dependency.
  - Deliverable: a unit test builds a world, runs the example catalog through harvest, craft, build, repair, and store, projects the frame, and asserts the six semantic types, structure `location_id`s, and presentation tokens. The same test asserts domain events and `WorldState` contain no `screen_x`, `screen_y`, `pixels`, `sprite`, `animation`, `dx`, or `dy`. An architecture test asserts `src/` does not import `clients.godot-observer` or contain that string, and that `observer` does not import `simulation.engine`. Change `tests/unit/test_godot_observer_fixtures.py` so golden event names are a subset of `SEMANTIC_EVENT_TYPES` and still equal the previous twenty names. Do not add files under `clients/godot-observer/fixtures/`. A frame with empty `structures` still validates as protocol v1. An old event's `public_mapping` has no `recipe_id` or `structure_id` key.
  - Logging: no production logger. The test asserts the architecture contract ids already covering `observer`.
  - Depends on task 8.
  - Files: `tests/unit/test_production_observer.py`, `tests/unit/test_godot_observer_fixtures.py`, `tests/architecture/test_observer_isolation.py`, `tests/architecture/test_godot_client_isolation.py`.

- [x] Task 10: v2- Document production and the observer boundary.
  - Deliverable: update `docs/physical-simulation.md` and `docs/observer.md` with the five actions, the six recipes, engine authority, belief versus catalog, replay-v6 and codec v3 (`structures`, `production_jobs`, `tool_marks`) only when the catalog is non-empty, location-based structures, visible `ObservedStructure` records, and presentation-only metadata. State that Godot is not required to read the projection. Update the downstream-contract counts in `docs/architecture.md` from fifteen commands to twenty, and note replay-v6 as an accepted schema whose default write remains replay-v5. Do not invent a roadmap milestone.
  - Logging: no runtime logger. Docs name the logger channels from tasks 1–8 and 11 and the reason codes `unknown_recipe`, `materials_unavailable`, `actor_busy`, `structure_intact`, and `production_disabled`.
  - Depends on tasks 7, 8, and 9.
  - Files: `docs/physical-simulation.md`, `docs/observer.md`, `docs/architecture.md`.
