# Phase 1: World Chain Mechanics

Plan: [index.md](index.md)
Tasks: 1-4
Depends on: none

## Objective

Own the declared `supply_chains` V4 capability and make multi-stage production
chains real world mechanics: a validated chain contract, a closed chain recipe
set that is never merged into the legacy default catalog, engine activation that
threads through construction and replay, a real tool-harvest success bonus, and
a local stage-readiness production choice in cognition. No new command, event,
observer semantic type, write pair, runner schema, or migration is introduced.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/simulation/v4_architecture.py` | `SUPPLY_CHAINS` 198-211; `_REQUIRED_CONTEXT_COUNT = 14` 56; `V4_CONTEXTS` 109+; `V4_CAPABILITY_FLAGS` 330-332 | Declares the owned seam, `uses_existing_events=True`, owners `("world","simulation")`, prerequisite `INFRASTRUCTURE_NETWORKS`, non-goals "no central planner or quota" and "no automatic allocation of items"; prerequisite is planning order only (92-93) |
| `src/simulation/compatibility.py` | `V4_OWNED_CAPABILITY_FLAGS` 155-164 | Single source of truth for owned V4 flags; currently six names |
| `src/simulation/runner_models.py` | `_V4_OWNED_CAPABILITY_FLAGS` 327; `V4CapabilityFlags` 1133-1180; v56 validation 8107-8165; `AgentCognitionSpec.production_catalog` 7053; `production_knowledge_mode` 7050 | Private owned copy, flag dataclass, and the activation block this task mirrors |
| `src/simulation/runner.py` | unimplemented gate 2361-2405; engine construction 2665; restore 7184; `CognitionLoopConfig` builder 1639 | Where unowned flags fail closed and where activation reaches the engine and cognition |
| `src/simulation/engine.py` | constructor 840-875; `production_catalog` 821/915; `from_snapshot` 1260/1335/1353/1453; activation pattern 409-425; `_resolve_production_effect` 6624-6746; probability/skill 6661-6700 | Established `*_active` propagation and the probability draw to extend |
| `src/world/production.py` | `ProductionAction` 71-79; `ToolRole` 81-85; `ResourceNameInput` 160-177; `HeldItemNameInput`/`HeldItemKindInput` 180-198; `ItemProduct` 201-278; `ProductionRecipe` 307-354; `example_production_catalog()` 471-528; `MINIMUM_PRODUCTION_DURATION` 23-24 | Exact input/output types, tool-role validation, and the locked six-recipe factory |
| `src/world/_production.py` | `_availability` 282-362; `_held_named` 365-385; `effective_duration` 74-86; `apply_resolved` 104-154; `_apply_harvest` 434-497; `_apply_craft` 500-564 | Harvest resource-match rule, craft input consumption, and one-tick vs multi-tick behaviour |
| `src/world/events.py` | `ResourceHarvested` 1031-1072; `CraftStarted` 1075-1101; `ItemCrafted` 1104-1126; `OccurrenceContext` 344-390; envelope 3938-3960 | Event fields the mechanics must preserve |
| `src/agents/cognition/production.py` | `ProductionKnowledgeMode` 44-52; `RecipeBeliefSet` 54-120; `compile_production_command` 225-272; `_command_for_recipe` 284-315 | Owner-scoped recipe ids and the one-command compiler |
| `src/agents/cognition/configuration.py` | `CognitionLoopConfig.production_knowledge_mode` 765; validation 1488; `build_cognitive_loop` 1815/2095 | The real cognition composition seam |
| `src/agents/cognition/deliberation.py` | `_with_production_command` 798-820; call 1165-1169 | Where one compiled production command replaces a non-veto command |
| `src/world/identifiers.py` | `RecipeId` 137-148 | `^[a-z][a-z0-9_]{0,31}$` bounds new recipe ids |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/world/supply_chain.py` | create | Frozen policy, stage derivation, validation, chain recipes, catalog extension, tool-probability helper |
| `src/world/__init__.py` | modify | Facade export of the public supply-chain world symbols |
| `src/world/_production.py` | modify | Extend `_SKILL_RECIPES` for the new craft recipes only |
| `src/simulation/engine.py` | modify | `supply_chains_active` parameter, validation, propagation, probability bonus |
| `src/simulation/runner.py` | modify | Pass activation from the v56 flag; pass it into cognition config |
| `src/simulation/runner_models.py` | modify | Add `supply_chains` to `_V4_OWNED_CAPABILITY_FLAGS`; v56 activation block; docstring |
| `src/simulation/compatibility.py` | modify | Add `supply_chains` to `V4_OWNED_CAPABILITY_FLAGS` |
| `src/agents/cognition/production.py` | modify | `production_stage_priority`, stage-readiness ordering |
| `src/agents/cognition/configuration.py` | modify | `CognitionLoopConfig.supply_chains_active`, validation, factory pass-through |
| `src/agents/cognition/loop.py` | modify | Store and thread `supply_chains_active` |
| `src/agents/cognition/deliberation.py` | modify | Forward the boolean to the compiler |
| `tests/unit/test_supply_chain_contract.py` | create | Policy, stage derivation, validation, catalog extension |
| `tests/unit/test_supply_chain_mechanics.py` | create | Flag activation, probability bonus, planning order |
| `tests/architecture/test_supply_chain_boundaries.py` | create | World/simulation boundary allowlists for the new module |
| `tests/unit/test_v4_scaffolding_gate.py` | modify | Move `supply_chains` from the unowned list to the owned list |

## Task 1: Lock `supply-chains.v1` stage contract and catalog validation

### Intent

Give the chain one validated objective contract shared by mechanics and analysis.
Later phases consume `SupplyStageSpec`; without it analysis would import
`world.production` and the chain would have no cycle protection.

### Implementation Steps

1. Create `src/world/supply_chain.py` with `__all__` exporting only:
   `SUPPLY_CHAIN_POLICY_VERSION`, `SUPPLY_CHAIN_HARVEST_TOOL_PROBABILITY_GAIN`,
   `SUPPLY_CHAIN_MAX_STAGE_DEPTH`, `SupplyChainContractError`,
   `SupplyStageSpec`, `SupplyChainSummary`, `production_chain_stages`,
   `validate_production_chain_catalog`, `supply_chain_production_catalog`,
   `harvest_tool_probability_gain`, `SUPPLY_CHAIN_RECIPES`.
2. Constants: `SUPPLY_CHAIN_POLICY_VERSION = "supply-chains.v1"`,
   `SUPPLY_CHAIN_HARVEST_TOOL_PROBABILITY_GAIN = 0.10`,
   `SUPPLY_CHAIN_MAX_STAGE_DEPTH = 8`.
3. `SupplyStageSpec` is frozen/slots with: `recipe_id: str`,
   `action: str` (`harvest|craft|build|repair|store`),
   `resource_input_names: tuple[str, ...]`,
   `item_input_names: tuple[str, ...]`,
   `input_kinds: tuple[str, ...]`,
   `output_name: str`, `output_kind: str`
   (`food|water|material|medical|generic|tool|structure|storage`),
   `skill_domain: str | None`, `tool_role: str | None`,
   `requires_tool: bool`. Sort and deduplicate every name tuple; reject unknown
   action/kind tokens.
4. Output mapping in `production_chain_stages(catalog)`:
   - `ItemProduct` → `(output.name, output.item_kind.value)`;
   - `ShelterProduct` → `("shelter", "structure")`;
   - `RepairProduct` → `("repair", "structure")`;
   - `StoreProduct` → `("store", "storage")`.
   Map inputs: `ResourceNameInput` → `resource_input_names`,
   `HeldItemNameInput` → `item_input_names`, `HeldItemKindInput` →
   `input_kinds`. `requires_tool = output_kind == "tool"`;
   `tool_role` from the recipe.
5. `validate_production_chain_catalog(catalog, *, require_chain=True) -> SupplyChainSummary`:
   - build `producer_by_name` from item-producing stages only;
   - `edge_count` counts each **item** input name that has a producer; resource
     names and kind inputs never create edges;
   - detect a cycle over produced item names with an iterative colour DFS in
     sorted order and raise `SupplyChainContractError("supply_chain_catalog_cycle")`;
   - raise `supply_chain_catalog_empty` when there are no recipes,
     `supply_chain_catalog_no_chain` when `edge_count == 0`, both only when
     `require_chain`;
   - return `SupplyChainSummary(stage_count, item_stage_count, edge_count,
     max_depth, policy_version)` with `max_depth` capped at
     `SUPPLY_CHAIN_MAX_STAGE_DEPTH`.
6. `SupplyChainContractError(ValueError)` carries a `code` attribute and never
   embeds recipe inputs, item names, or catalogs in its message.

### Required Interfaces and Contracts

- `SupplyChainSummary` fields: `stage_count: int`, `item_stage_count: int`,
  `edge_count: int`, `max_depth: int`, `policy_version: str`.
- Validation is pure, never mutates the catalog, and never reads `WorldState`.
- A legacy catalog (`harvest_wood`, `harvest_stone`, `craft_tool`,
  `build_shelter`, `repair_shelter`, `store_food`) must validate with
  `edge_count == 2` (`wood→tool`, `stone→tool`), proving resource inputs are
  excluded.
- Public import surface is the module; no private `world._*` import is added for
  analysis.

### Requirement Evidence

- Source anchors: `v4_architecture.py` 198-211; `production.py` 160-198/307-354;
  `_production.py` 282-302 (harvest resource match) and 365-385.
- Supported combinations: item-output recipe, structure/repair/store terminal
  recipe, harvest recipe with a resource input, kind-input recipe, cyclic
  catalog (rejected), legacy catalog (valid), empty catalog (rejected only when
  `require_chain=True`).

### Error Handling and Logging

- `WARN supply_chain_catalog_invalid code=<code> stage_count=<n> edge_count=<n>`
  before raising; never log recipe inputs or item names.
- `DEBUG supply_chain_stages_built stage_count=<n> edge_count=<n> max_depth=<n>
  policy=<version>` on success.

### Tests

- `tests/unit/test_supply_chain_contract.py`:
  `test_stage_spec_rejects_unknown_action`,
  `test_harvest_stage_separates_resource_inputs`,
  `test_kind_inputs_are_not_item_edges`,
  `test_legacy_catalog_validates_with_two_edges`,
  `test_validation_rejects_cycle`, `test_validation_rejects_no_chain`,
  `test_validation_accepts_multi_stage_catalog`,
  `test_summary_max_depth_is_capped`, `test_stage_spec_is_frozen`,
  `test_non_item_output_tokens`.
- `uv run pytest tests/unit/test_supply_chain_contract.py -q`.

### Acceptance Criteria

- The legacy catalog validates with `edge_count == 2` and no self-edge.
- A multi-stage catalog yields `edge_count >= 2` and `max_depth >= 2`.
- A cyclic generated catalog raises `supply_chain_catalog_cycle`.

### Verification

- `uv run pytest tests/unit/test_supply_chain_contract.py -q` → all pass.

## Task 2: Add the multi-stage chain recipe set

### Intent

Provide the concrete chain from the request without touching any legacy
catalog: resource → intermediate material → tool → improved harvesting → food.
The legacy six-recipe catalog and digest stay byte-identical.

### Implementation Steps

1. In `src/world/supply_chain.py`, define `SUPPLY_CHAIN_RECIPES` as a frozen
   tuple of six valid `ProductionRecipe` values in this exact order:
   - `harvest_grain`: `HARVEST`, `2`, `0.90`,
     `inputs=(ResourceNameInput("grain"),)`,
     output `ItemProduct(ItemKind.FOOD, "grain", load=1, tool_role=None)`.
   - `mill_grain`: `CRAFT`, `2`, `0.85`,
     `inputs=(HeldItemNameInput("grain"),)`,
     output `ItemProduct(ItemKind.MATERIAL, "flour", 1, None)`.
   - `bake_bread`: `CRAFT`, `3`, `0.80`,
     `inputs=(HeldItemNameInput("flour"),)`,
     output `ItemProduct(ItemKind.FOOD, "bread", 1, None)`.
   - `craft_plank`: `CRAFT`, `2`, `0.90`,
     `inputs=(HeldItemNameInput("wood"),)`,
     output `ItemProduct(ItemKind.MATERIAL, "plank", 1, None)`.
   - `craft_tool_head`: `CRAFT`, `2`, `0.90`,
     `inputs=(HeldItemNameInput("stone"),)`,
     output `ItemProduct(ItemKind.MATERIAL, "tool_head", 1, None)`.
   - `assemble_tool`: `CRAFT`, `3`, `0.85`,
     `inputs=(HeldItemNameInput("plank"), HeldItemNameInput("tool_head"))`,
     output `ItemProduct(ItemKind.TOOL, "fine_tool", 1, ToolRole.STRIKE)`,
     `tool_role=ToolRole.STRIKE`.
   `harvest_grain` uses the `harvest_<resource-name>` convention so
   `_command_for_recipe` resolves the visible `grain` resource, and
   `_availability` matches `recipe.inputs[0].name`.
2. `supply_chain_production_catalog(base: ProductionCatalog) -> ProductionCatalog`:
   return `ProductionCatalog(tuple(base.recipes) + SUPPLY_CHAIN_RECIPES)` **in
   base order then append order** (do not re-sort, to keep serialized config
   order stable); raise `SupplyChainContractError("supply_chain_recipe_collision")`
   on id collision; never mutate `base`.
3. In `src/world/_production.py`, extend `_SKILL_RECIPES` with
   `mill_grain`, `bake_bread`, `craft_plank`, `craft_tool_head`,
   `assemble_tool` → `"crafting"`. Leave `harvest_grain` ungated.
4. Export `supply_chain_production_catalog`, `production_chain_stages`, and
   `SupplyChainContractError` from `src/world/__init__.py` by importing from
   `world.supply_chain` (the facade already re-exports
   `example_production_catalog` at line 312). Do not re-export through
   `world.production`.
5. Do **not** modify `example_production_catalog()` or
   `production_catalog_digest`.

### Required Interfaces and Contracts

- `SUPPLY_CHAIN_RECIPES` has length 6 and every recipe passes
  `ProductionRecipe.__post_init__` (resource input for harvest; tool output
  paired with `tool_role=STRIKE`).
- `supply_chain_production_catalog` is pure and idempotent over distinct ids.
- Chain item edges: `grain→flour`, `flour→bread`, `wood→plank`,
  `stone→tool_head`, `plank→fine_tool`, `tool_head→fine_tool`; `max_depth`
  is at least 3.
- No legacy recipe id, order, output, or digest changes.

### Requirement Evidence

- Original Request chain; `production.py` 23-24/160-278/307-354/471-528;
  `_production.py` 289-302 (harvest expects `ResourceNameInput`) and 342-354
  (tool-role pairing).
- Supported combinations: base without chain recipes (unchanged digest),
  extension applied twice (collision error), legacy catalog then extension.

### Error Handling and Logging

- `DEBUG supply_chain_catalog_extended base_stages=<n> added_stages=<n>
  total_stages=<n>`.
- `WARN supply_chain_recipe_collision recipe_id=<id>` then raise; id only.

### Tests

- `tests/unit/test_supply_chain_contract.py` additions:
  `test_legacy_default_catalog_is_unchanged`,
  `test_extension_adds_six_recipes`, `test_extension_preserves_base_order`,
  `test_extension_rejects_collision`, `test_extended_catalog_is_acyclic`,
  `test_chain_depth_reaches_three`, `test_tool_output_carries_strike_role`,
  `test_harvest_recipe_uses_resource_input`,
  `test_skill_domains_cover_new_craft_recipes`,
  `test_world_facade_exports_supply_chain`.
- `uv run pytest tests/unit/test_supply_chain_contract.py tests/unit/test_production_catalog.py -q`.

### Acceptance Criteria

- `tests/unit/test_production_catalog.py` still passes with `recipe_count == 6`.
- The extended catalog validates with `edge_count == 6`.
- `assemble_tool` constructs and yields a `STRIKE` tool.

### Verification

- `uv run pytest tests/unit/test_supply_chain_contract.py tests/unit/test_production_catalog.py -q` → all pass.

## Task 3: Own the `supply_chains` flag and thread engine activation

### Intent

Claim the declared flag so enabling it is validated, visible to the engine, and
consistent across construction and restore. Activation must fail closed when no
chain catalog exists.

### Implementation Steps

1. `src/simulation/compatibility.py`: add `"supply_chains"` to
   `V4_OWNED_CAPABILITY_FLAGS` (after `"infrastructure_networks"`); keep seven
   names.
2. `src/simulation/runner_models.py`:
   - add `"supply_chains"` to `_V4_OWNED_CAPABILITY_FLAGS` (line ~327);
   - update the `V4CapabilityFlags` docstring for V4-19;
   - after the infrastructure block (8107-8165), add a `supply_chains` block:
     require `RUNNER_SCHEMA_VERSION_V56`
     (`code=supply_chains_requires_v56`), emit
     `INFO supply_chains_enabled policy_id=supply-chains.v1`, and
     `DEBUG supply_chains_bind schema_v56=%s catalog_present=%s`.
     Do **not** require `collective_projects`, `infrastructure_networks`, or
     `regions_migration` at runtime.
3. `src/simulation/engine.py`:
   - add `supply_chains_active: bool = False` after `travel_network_active`
     (constructor ~849) and to `from_snapshot` (~1260);
   - validate the boolean; when active:
     - `self._production_catalog is None` → raise
       `ValueError("supply_chain_catalog_missing")` after
       `ERROR supply_chain_activation_rejected code=supply_chain_catalog_missing`;
     - otherwise call
       `validate_production_chain_catalog(self._production_catalog,
       require_chain=True)` and re-raise a `SupplyChainContractError` as
       `ValueError(code=...)` after a single `ERROR`;
   - store `self._supply_chains_active` and emit
     `DEBUG supply_chains_active enabled=%s policy=supply-chains.v1`;
   - propagate the boolean through every reconstruction site listed in
     Current-Code Evidence (1426, 1756, 2186, 2432, 4209, 4742) and through
     `from_snapshot` (1335/1353/1453).
4. `src/simulation/runner.py`: pass
   `supply_chains_active=config.v4_capability_flags.supply_chains` at engine
   construction (2665) and restore (7184); pass the same boolean into the
   cognition config builder at 1639.
5. `tests/unit/test_v4_scaffolding_gate.py`: move `"supply_chains"` from the
   unowned-flag list (line 44) to the owned-flag list so the fail-closed matrix
   stays truthful. Broader fixture repointing is Task 12.
6. `RunnerResult` stays unchanged: activation is runner JSON plus engine state.

### Required Interfaces and Contracts

- Counts: 14 contexts / 12 flags / 7 owned / 5 unowned.
- `supply_chains` requires `runner-config-v56`; no `runner-config-v57`.
- Flag on + no catalog → `supply_chain_catalog_missing`; flag on + legacy
  catalog → `supply_chain_catalog_no_chain`; flag off → no validation.
- No per-agent mode or root field is added.

### Requirement Evidence

- `v4_architecture.py` 92-93/198-211; `compatibility.py` 155-164;
  `runner_models.py` 8107-8165; `runner.py` 2361-2405/2665/7184;
  `engine.py` 821/915/1260/1353/1453; `test_v4_scaffolding_gate.py` 44/133-152.
- Supported combinations: off, on with extended catalog, on with legacy
  catalog, on with no catalog, another unowned flag, restore parity.

### Error Handling and Logging

- `ERROR supply_chain_activation_rejected code=<code>` once per rejection.
- `INFO supply_chains_enabled policy_id=supply-chains.v1`.
- `DEBUG supply_chains_bind` / `supply_chains_active` carry booleans only.
- Never log catalogs, item names, or recipe inputs.

### Tests

- `tests/unit/test_supply_chain_mechanics.py`:
  `test_flag_is_owned_counts_are_seven`, `test_flag_requires_v56`,
  `test_engine_rejects_missing_catalog_when_active`,
  `test_engine_rejects_legacy_catalog_when_active`,
  `test_engine_accepts_extended_catalog`,
  `test_engine_inactive_does_not_validate`,
  `test_runner_passes_flag_to_engine`, `test_restore_preserves_activation`,
  `test_other_v4_flag_still_fails_closed`,
  `test_no_runner_config_v57_added`.
- `uv run pytest tests/unit/test_supply_chain_mechanics.py tests/unit/test_v4_scaffolding_gate.py tests/architecture/test_v4_architecture_invariants.py -q`.

### Acceptance Criteria

- Flag on + extended catalog constructs and restores an engine.
- Flag on + missing/legacy catalog fails closed with the locked code.
- Every other unowned flag still raises `capability_unimplemented`.
- The scaffolding gate reflects seven owned flags and five unowned.

### Verification

- `uv run pytest tests/unit/test_supply_chain_mechanics.py tests/unit/test_v4_scaffolding_gate.py tests/architecture/test_v4_architecture_invariants.py -q` → all pass.

## Task 4: Add tool-assisted harvesting and local stage-readiness planning

### Intent

Make the tool chain mechanically meaningful: a held `STRIKE` tool must improve
harvest reliability, and owners must choose locally ready stages. Both are
deterministic, observation-only, one command per tick, and inactive when the
flag is off.

### Implementation Steps

1. `src/world/supply_chain.py`: add pure helper
   `harvest_tool_probability_gain(state, actor_id, recipe) -> float` returning
   `SUPPLY_CHAIN_HARVEST_TOOL_PROBABILITY_GAIN` only when
   `recipe.action is ProductionAction.HARVEST` **and** the actor holds an item
   whose `state.tool_marks[item_id].role is ToolRole.STRIKE`; otherwise `0.0`.
   It never mutates state and never reads flags.
2. `src/simulation/engine.py` `_resolve_production_effect` (6661-6700): after
   the existing skill probability adjustment and before the Bernoulli draw:
   - if `self._supply_chains_active`, compute
     `gain = harvest_tool_probability_gain(starting_state, request.actor_id,
     recipe)` and set
     `probability = clamp_unit_interval(probability + gain)`;
   - log `DEBUG harvest_tool_assist gain=<n> clamped=<bool>` (numbers only).
   Do **not** change `world/effects.py`, `apply_resolved`, or `effective_duration`:
   harvest duration stays recorded metadata, not a scheduling effect.
3. `src/agents/cognition/production.py`:
   - add `production_stage_priority(recipe_id) -> int` (`harvest_` 0, `craft_` 1,
     `build_` 2, `repair_` 3, `store_` 4, else 5);
   - add keyword-only `supply_chains_active: bool = False` to
     `compile_production_command`;
   - inactive → keep the current first-match order byte-for-byte;
   - active → iterate supported beliefs sorted by
     `(production_stage_priority(recipe_id), recipe_id.value)`, compile each
     with `_command_for_recipe`, and return the first non-`None` command;
     `selected_recipe_id` still wins and `vetoed` still returns `None`;
   - log `DEBUG production_plan_selected stage=<priority> recipe_id=<id>
     command_kind=<kind>`.
4. `src/agents/cognition/configuration.py`:
   - add `supply_chains_active: bool = False` to `CognitionLoopConfig` (~765)
     with type validation next to `production_knowledge_mode` (~1488);
   - pass it into the `CognitiveLoop(...)` construction in
     `build_cognitive_loop` (~2095).
5. `src/agents/cognition/loop.py`: add and store
   `supply_chains_active: bool = False` in `CognitiveLoop.__init__` and pass it
   to `_with_production_command`.
6. `src/agents/cognition/deliberation.py`: add the keyword to
   `_with_production_command` and forward it to `compile_production_command`.
7. `src/simulation/runner.py`: pass
   `supply_chains_active=config.v4_capability_flags.supply_chains` at all three
   live loop construction sites (2904, 6694, 7076) and in the config builder
   (1639). Organizations get no executor: planning stays member commands plus
   owner procedure claims.

### Required Interfaces and Contracts

- Off-path behavior: with the flag off, probability, command order, durations,
  and logs for existing runs are unchanged.
- Tool bonus applies only to `HARVEST`, only with a held `STRIKE` mark, is
  clamped to `[0.0, 1.0]`, and does not consume the tool.
- Planning is one step deep: no lookahead, optimizer, price, quota, or
  cross-agent state; only believed ids plus the current observation.
- Stage ordering is total; ties break on `recipe_id.value`.

### Requirement Evidence

- Original Request example and "plan locally"; `engine.py` 6661-6700;
  `_production.py` 74-86/434-497; `production.py` 225-315;
  `configuration.py` 765/1488/1815/2095; `runner.py` 1639/2904/6694/7076;
  `deliberation.py` 798-820; `loop.py` 4835-4849/5483-5484.
- Supported combinations: flag off; flag on with/without a tool; non-harvest
  recipe; probability already 1.0; selected recipe override; veto; disabled
  production knowledge.

### Error Handling and Logging

- Non-boolean activation raises `TypeError` in the config and loop constructors.
- `production_plan_selected` logs priority/ids only.
- `production_command_withheld` keeps existing reason codes.
- Never log inventories, item ids, tool marks, or observation bodies.

### Tests

- `tests/unit/test_supply_chain_mechanics.py` additions:
  `test_harvest_probability_gain_with_strike_tool`,
  `test_harvest_probability_gain_without_tool`,
  `test_probability_gain_ignored_for_craft`,
  `test_probability_clamped_to_one`,
  `test_plan_prefers_harvest_over_craft`,
  `test_plan_orders_craft_before_build`,
  `test_plan_tie_breaks_on_recipe_id`,
  `test_selected_recipe_overrides_stage_order`,
  `test_veto_returns_none`, `test_inactive_flag_preserves_legacy_order`,
  `test_loop_config_validates_activation`,
  `test_all_loop_construction_sites_forward_activation`.
- `uv run pytest tests/unit/test_supply_chain_mechanics.py tests/unit/test_recipe_beliefs.py -q`.

### Acceptance Criteria

- With a `STRIKE` tool and flag on, `harvest_grain` probability is `1.0`
  (0.90 + 0.10) and the draw is skipped.
- Without a tool or with the flag off, probability is `0.90`.
- With the flag on, a supported `harvest_grain` is chosen before `craft_plank`.
- With the flag off, the command sequence is identical to today.

### Verification

- `uv run pytest tests/unit/test_supply_chain_mechanics.py tests/unit/test_recipe_beliefs.py -q` → all pass.

## Phase Risks and Mitigations

- Risk: chaining resource inputs into item edges creates a legacy self-cycle.
  Mitigation: Task 1 separates resource/item/kind inputs and pins the legacy
  two-edge result.
- Risk: recipe validation rejects the chain catalog (bad harvest input or tool
  role). Mitigation: Task 2 uses the exact valid field shapes and tests
  construction.
- Risk: a timestamp-only "tool bonus" with no mechanical effect.
  Mitigation: Task 4 uses success probability, pinned by a unit test.
- Risk: one of the seven engine/cognition propagation sites is missed.
  Mitigation: Task 3/4 enumerate each site and Task 21 adds restore parity.

## Phase Completion Checklist

- Every Task 1-4 satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
