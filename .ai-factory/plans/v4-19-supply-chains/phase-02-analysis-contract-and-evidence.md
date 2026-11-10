# Phase 2: Analysis Contract and Evidence

Plan: [index.md](index.md)
Tasks: 5-7
Depends on: Phase 1 (Task 1 stage contract)

## Objective

Lock the detached analytical policy for `supply-chains.v1`, reconstruct bounded
production evidence from committed events plus explicitly detached objective
inputs (recipe specs, skill levels, operational infrastructure, organization
claims), and derive an observed dependency graph with chain paths. The analysis
never imports `WorldState`, `WorldEngine`, experiments, API, persistence,
observer, or cognition.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/analysis/trade_networks_contract.py` | `__all__` 22-37; policy 39; prefixes 40-48; enums 53-78; error codes 114-135 | Sibling contract shape |
| `src/analysis/trade_networks_policy.py` | window 32; `_INT_RANGES` 37-52; validation 74-85 | Bounded policy/caps pattern |
| `src/analysis/trade_networks_events.py` | `__all__` 45-50; harvest 206-212; sorting/duplicates 214-226; two-pass indexing 234-280; branch set 396-530; coverage 576-588; truncation 567-574 | Evidence extraction and coverage pattern |
| `src/analysis/trade_networks_detection.py` | truncation notices 113/245/371 | Derived-row family pattern |
| `src/analysis/trade_networks_identity.py` | minting 26-32 | Content-addressed analytical ids |
| `src/analysis/trade_networks_layers.py` | `__all__` 20-24 | Three-layer separation |
| `src/analysis/trade_networks_rows.py` | `__all__` 23-32; rows 76-308 | Frozen row schema style |
| `src/analysis/infrastructure_networks_analysis.py` | asset rows 48; result 163; harvest 229-259 | Detached objective enrichment input |
| `src/analysis/organization_operations.py` | `OrganizationProcedureActionRow` 302-330; `OrganizationOperationHarvestRows` 414-453; harvest 814-858; snapshot 861-869 | Exact organization claim fields (no recipe, no location) |
| `src/world/events.py` | `ResourceHarvested` 1031-1072; `CraftStarted` 1075-1101; `ItemCrafted` 1104-1126; `StructureBuilt` 1129-1164; `StructureRepaired` 1167-1201; `ItemStored` 1204-1237; `Given` 638-656; `Taken` 602-617; `Dropped` 620-635; `Transported` 816-840 | Production event fields |
| `src/world/events.py` | `OccurrenceContext` 344-390 (`origin_location_id: EntityId | None`); envelope 3938-3960 (`occurrence: OccurrenceContext | None`) | Optional location evidence |
| `src/world/_production.py` | `_apply_craft` 500-564; `complete_due_jobs` 157-235 | One-tick vs multi-tick craft evidence |
| `src/simulation/runner_models.py` | `SkillAudit` 798-823; `SkillAuditSide.OBJECTIVE` 777-781 | Detached skill input |
| `tests/architecture/test_trade_networks_boundaries.py` | `_trade_paths` 54-55; `_ast_names` 58-68; denylist 124-143 | Boundary-test approach |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/analysis/supply_chain_contract.py` | create | Version, prefixes, enums, error class/codes, token helpers |
| `src/analysis/supply_chain_policy.py` | create | Window, caps, thresholds, validation, window math |
| `src/analysis/supply_chain_events.py` | create | Recipe specs, evidence rows, pairing, bounded harvest |
| `src/analysis/supply_chain_graph.py` | create | Dependency nodes/edges and chain paths |
| `src/analysis/supply_chain_rows.py` | create | Frozen analytical rows and bundle |
| `src/analysis/supply_chain_layers.py` | create | Three-layer projection and separation assertion |
| `tests/unit/test_supply_chain_contract.py` | modify | Contract/policy tests |
| `tests/unit/test_supply_chain_events.py` | create | Evidence extraction tests |
| `tests/unit/test_supply_chain_graph.py` | create | Graph and chain tests |
| `tests/architecture/test_supply_chain_boundaries.py` | modify | Analysis boundary checks |

## Task 5: Lock `supply-chains.v1` analysis contract and caps

### Intent

Fix every identifier, enum, cap, and threshold before evidence extraction so no
implementer chooses a taxonomy. The closed dimensions are the six requested
dependencies plus the traversal associations the graph needs.

### Implementation Steps

1. Create `src/analysis/supply_chain_contract.py` with `__all__`:
   `SUPPLY_CHAIN_ANALYSIS_POLICY_VERSION`, `SUPPLY_STAGE_PREFIX`,
   `SUPPLY_EDGE_PREFIX`, `SUPPLY_CHAIN_PREFIX`, `SUPPLY_BOTTLENECK_PREFIX`,
   `NONE_TOKEN`, `SUPPLY_FORBIDDEN_KEYS`, `SUPPLY_LAYER_FORBIDDEN_PREFIXES`,
   `SUPPLY_CHAIN_ERROR_CODES`, `SupplyCoverage`, `SupplyLayer`,
   `SupplyNodeKind`, `SupplyEdgeKind`, `SupplyBottleneckKind`,
   `SupplyChainError`, `analysis_supply_token`, `canonical_supply_pair`.
2. Constants: policy `supply-chains.v1`; prefixes `sc-stage-`, `sc-edge-`,
   `sc-chain-`, `sc-neck-`; `NONE_TOKEN = "-"`; token regex
   `^sc-(stage|edge|chain|neck)-[0-9a-f]{16}$`.
3. `SupplyCoverage`: `complete`, `partial`, `missing`.
   `SupplyLayer`: `objective_derived`, `analytical`, `owner_claims`.
4. `SupplyNodeKind`: `resource`, `item`, `structure`, `storage`, `location`,
   `infrastructure`, `organization`, `tool`, `skill`.
5. `SupplyEdgeKind` (exactly ten): `resource_to_item`, `item_to_item`,
   `item_to_structure`, `item_to_storage`, `transport`, `location_to_stage`,
   `infrastructure_to_stage`, `organization_to_stage`, `tool_to_stage`,
   `skill_to_stage`.
6. `SupplyBottleneckKind`: `upstream_shortfall`,
   `single_location_concentration`, `transport_dependency`, `tool_dependency`,
   `infrastructure_dependency`, `organization_dependency`,
   `skill_constraint`.
7. `SUPPLY_CHAIN_ERROR_CODES` is a frozen frozenset of exactly:
   `supply_chain_invalid_policy`, `supply_chain_invalid_cap`,
   `supply_chain_invalid_window`, `supply_chain_invalid_recipe_spec`,
   `supply_chain_duplicate_event`, `supply_chain_invalid_event_order`,
   `supply_chain_evidence_truncated`, `supply_chain_stage_truncated`,
   `supply_chain_edge_truncated`, `supply_chain_chain_truncated`,
   `supply_chain_bottleneck_truncated`, `supply_chain_lineage_truncated`,
   `supply_chain_location_truncated`, `supply_chain_organization_truncated`,
   `supply_chain_invalid_token`, `supply_chain_layer_leak`.
8. `analysis_supply_token(prefix, payload)` hashes `prefix + payload` with
   `hashlib.blake2b(digest_size=8)`; `canonical_supply_pair(left, right)` sorts
   two non-empty tokens with `-`.
9. Create `src/analysis/supply_chain_policy.py` with
   `DEFAULT_SUPPLY_WINDOW_TICKS = 32`, `SupplyChainAnalysisPolicy`,
   `default_supply_chain_analysis_policy`, `window_bounds`,
   `window_index_for_tick`, and the locked thresholds:
   `BOTTLENECK_MIN_EVENTS = 3`, `BOTTLENECK_SHARE_MILLI = 750`,
   `BOTTLENECK_SHORTFALL_MILLI = 250`, `BOTTLENECK_DEMAND_MIN = 3`,
   `CHAIN_OVERLAP_MILLI = 500`, `LOW_SKILL_LEVEL = 0.125`,
   `MAX_CHAIN_DEPTH = 8`.
10. Policy fields/ranges (reject bools used as ints): `window_ticks` 8..256
    (32); `max_windows` 1..512 (512); `max_evidence_rows` 1..200000 (200000);
    `max_stages` 1..4096 (4096); `max_edges` 1..16384 (16384); `max_chains`
    1..4096 (4096); `max_bottlenecks` 1..4096 (4096); `max_locations` 1..4096
    (4096); `max_organizations` 1..2048 (2048); `max_lineage_edges` 1..16384
    (16384).

### Required Interfaces and Contracts

- Every analytic id is content-addressed; no counters, `hash()`, or UUID.
- `window_index_for_tick` is floor division; `window_bounds` returns
  `(index*ticks, index*ticks + ticks)`.
- `SUPPLY_FORBIDDEN_KEYS` includes `price`, `cost`, `currency`, `money`,
  `quota`, `allocation`, `optimizer`, `plan_score`, `priority_score`,
  `recommendation`, `rank`, `severity`.
- Caps reject rather than silently clamp; truncation is an analysis notice.

### Requirement Evidence

- Original Request dimensions and "no global planner"; sibling contract/policy
  modules; `.ai-factory/ARCHITECTURE.md` Key Principles 2 and 4.
- Supported combinations: defaults, each cap at min/max, invalid values,
  unknown prefix, pair ordering.

### Error Handling and Logging

- Invalid values raise `SupplyChainError(code=...)` after
  `WARN supply_chain_policy_invalid field=<name> code=<code>`.
- `DEBUG supply_chain_token_minted prefix=<prefix>`; never the payload.

### Tests

- `tests/unit/test_supply_chain_contract.py` additions:
  `test_policy_defaults`, `test_policy_rejects_bool_as_int`,
  `test_policy_cap_ranges`, `test_error_codes_are_closed`,
  `test_tokens_are_deterministic`, `test_token_rejects_unknown_prefix`,
  `test_window_math_matches_floor_division`,
  `test_forbidden_keys_include_optimizer_terms`,
  `test_pair_is_order_independent`, `test_edge_kinds_are_closed_to_ten`.
- `uv run pytest tests/unit/test_supply_chain_contract.py -q`.

### Acceptance Criteria

- Identical payloads mint identical tokens; different payloads differ.
- All caps/thresholds have one definition.
- No enum or prefix exists outside the closed sets above.

### Verification

- `uv run pytest tests/unit/test_supply_chain_contract.py -q` → all pass.

## Task 6: Extract bounded production evidence and detached dependency inputs

### Intent

Turn committed events into honest, bounded stage observations without reading
world state, using explicit pairing for craft attempts/completions and explicit
detached inputs for every optional dimension.

### Implementation Steps

1. In `src/analysis/supply_chain_events.py`, define `__all__`:
   `SupplyRecipeSpec`, `SupplyStageObservation`, `SupplyItemCreation`,
   `SupplySkillLevel`, `SupplyInfrastructureFact`, `SupplyOrganizationClaim`,
   `SupplyEvidenceHarvest`, `supply_evidence_from_events`.
2. `SupplyRecipeSpec` frozen/slots: `recipe_id`, `action`,
   `resource_input_names`, `item_input_names`, `input_kinds`,
   `output_name`, `output_kind`, `skill_domain`, `tool_role`; validate the
   closed tokens and a non-empty `output_name`.
3. `SupplyOrganizationClaim` frozen/slots: `organization_token`,
   `command_kinds: tuple[str, ...]`, `actor_tokens: tuple[str, ...]`,
   `first_tick: int | None`, `last_tick: int | None`, `claim_count: int`.
   There is no recipe id and no location — those fields do not exist on the
   source rows.
4. `supply_evidence_from_events(events, *, policy, recipes, skill_levels=None,
   infrastructure=None, organization_claims=None) -> SupplyEvidenceHarvest`:
   - require a `Sequence`; sort by `(tick, sequence)`; reject duplicate
     `event_id.value` with `supply_chain_duplicate_event`;
   - build `recipe_by_id` and `output_by_recipe`;
   - pass 1 builds `item_name_by_id` from `ItemCrafted` and successful
     `ResourceHarvested` rows that carry `created_item_id`;
   - pass 2 emits `SupplyStageObservation` rows:
     - `ResourceHarvested`: `success` false → attempt only; true → completed,
       `duration_ticks` retained;
     - `CraftStarted`: attempt row with `started_success = details.success` and
       resolved `item_names` (empty on failure);
     - `ItemCrafted`: completed row; actor from
       `details.resulting_holder_id` (fallback `event.actor_id`); location from
       occurrence;
     - `StructureBuilt` / `StructureRepaired` / `ItemStored`: terminal
       completed rows with `consumed_item_id` resolved when present;
     - `Given` / `Taken` / `Dropped` / `Transported`: movement evidence only;
     - other event kinds: `DEBUG supply_chain_event_ignored event_kind=<kind>`;
   - **pairing:** for each successful `CraftStarted`, pair the earliest
     unpaired `ItemCrafted` with the same actor token and recipe id at a later
     tick; the completion inherits the start's `item_names` and
     `duration_ticks`. A successful `ItemCrafted` with no start (one-tick
     craft, `_apply_craft` duration branch) keeps `item_names=()` and emits
     notice `unresolved_craft_inputs`; it still counts as completed but creates
     no `item_to_item` edge. Unpaired failed starts remain attempts only;
   - location resolution: `event.occurrence` is optional
     (`OccurrenceContext | None`); use `origin_location_id` when present, else
     `NONE_TOKEN` plus `unresolved_location`;
   - consume ids through `item_name_by_id`; unknown ids → `NONE_TOKEN` plus
     `unresolved_item_name`;
   - normalize `skill_levels` to `SupplySkillLevel(agent_id, domain, level)`
     with `0.0 <= level <= 1.0`; `infrastructure` to
     `SupplyInfrastructureFact(location_id, kinds)` only for status
     `operational`; organization claims to the shape above;
   - sort by `(tick, sequence, recipe_id)`; truncate at
     `policy.max_evidence_rows` with notice `evidence_truncated`.
5. Coverage: `missing` when no rows; `partial` when any notice exists or any
   row token is `NONE_TOKEN`; else `complete`. Return per-dimension coverage for
   evidence, skill, infrastructure, and organization.

### Required Interfaces and Contracts

- `SupplyStageObservation` fields: `tick`, `sequence`, `window_index`,
  `recipe_id`, `action`, `location_token`, `actor_token`,
  `item_names`, `completed`, `attempt`, `started_success` (bool | None),
  `duration_ticks`, `created_item_token`, `cause`
  (`harvest|craft|structure|storage`).
- Notice codes exactly: `unknown_recipe`, `unresolved_item_name`,
  `unresolved_location`, `unresolved_craft_inputs`,
  `missing_skill_levels`, `missing_infrastructure`,
  `missing_organization_claims`, `evidence_truncated`.
- No `world` import; recipe structure arrives only via `SupplyRecipeSpec`.

### Requirement Evidence

- `_apply_craft` 500-564 and `complete_due_jobs` 157-235 (pairing/one-tick);
  `events.py` 344-390/3960 (optional occurrence); `SkillAuditSide.OBJECTIVE`
  (777-781); organization row fields 302-330; trade extraction pattern
  206-588.
- Supported combinations: harvest success/failure, multi-tick craft pair,
  one-tick craft, failed start, missing occurrence, unknown item, each optional
  input absent, truncation.

### Error Handling and Logging

- `WARN supply_chain_evidence_partial notices=<codes>` once.
- `DEBUG supply_chain_evidence_rows rows=<n> windows=<n>`.
- `DEBUG supply_chain_event_ignored` capped at 20 distinct kinds.
- Never log item names, actor ids in bulk, or observation bodies.

### Tests

- `tests/unit/test_supply_chain_events.py`:
  `test_requires_sequence`, `test_sorts_by_tick_and_sequence`,
  `test_rejects_duplicate_event_id`, `test_harvest_failure_is_attempt_only`,
  `test_harvest_success_is_completed`,
  `test_craft_start_completion_pairing`,
  `test_one_tick_craft_sets_unresolved_inputs`,
  `test_failed_start_has_no_completion`,
  `test_completion_actor_uses_resulting_holder`,
  `test_missing_occurrence_sets_notice`,
  `test_consumed_ids_resolve_to_input_names`,
  `test_structure_and_storage_rows`,
  `test_missing_optional_inputs_set_missing_coverage`,
  `test_operational_infrastructure_only`,
  `test_organization_claim_shape_has_no_recipe_or_location`,
  `test_truncation_sets_partial`, `test_no_rows_is_missing`,
  `test_rows_are_frozen`.
- `uv run pytest tests/unit/test_supply_chain_events.py -q`.

### Acceptance Criteria

- A `CraftStarted` + later `ItemCrafted` for `mill_grain` produce one attempt
  and one completed row whose `item_names == ("grain",)`.
- A one-tick craft completion is completed, has no item names, and sets
  `unresolved_craft_inputs`.
- Absent optional inputs never fail; they set `missing` coverage.

### Verification

- `uv run pytest tests/unit/test_supply_chain_events.py -q` → all pass.

## Task 7: Build the observed dependency graph and chain paths

### Intent

Turn stage observations into the six requested dependency dimensions plus the
traversable chain structure. Every edge is observed or comes from an explicit
detached fact; nothing is inferred from catalog possibility alone.

### Implementation Steps

1. In `src/analysis/supply_chain_graph.py`, define `__all__`:
   `SupplyDependencyNode`, `SupplyDependencyEdge`, `SupplyChainPath`,
   `SupplyDependencyGraph`, `build_dependency_graph`.
2. `SupplyDependencyNode`: `node_token`, `node_kind`, `label_token`,
   `window_index`, `observation_count`, `completed_count`, `coverage`.
   Nodes are created for item/resource/structure/storage outputs, locations,
   infrastructure kinds, organization tokens, tool roles, and skill domains.
3. `SupplyDependencyEdge`: `edge_token`, `window_index`, `from_kind`,
   `from_token`, `to_kind`, `to_token`, `edge_kind`, `recipe_id`,
   `observed_count`, `completed_count`, `share_milli`,
   `created_elsewhere_count`, `coverage`.
4. `SupplyChainPath`: `chain_token`, `window_index`, `stage_tokens`,
   `edge_tokens`, `depth`, `location_tokens`, `organization_tokens`,
   `completed_count`, `coverage`.
5. `build_dependency_graph(evidence, *, policy) -> SupplyDependencyGraph`:
   - group completed rows by `(window_index, recipe_id)`;
   - `resource_to_item` for successful harvest completions;
   - `item_to_item` for each resolved `item_names` entry → `output_name` of a
     paired completion;
   - `item_to_structure` / `item_to_storage` for terminal completed rows;
   - `transport` when a consumed item's `SupplyItemCreation.location` differs
     from the row location; retain `created_elsewhere_count`;
   - `location_to_stage` for every completed row with a real location;
   - `infrastructure_to_stage` only when infrastructure coverage is not
     `missing`, from `SupplyInfrastructureFact` kinds at the row location;
   - `organization_to_stage` only when organization coverage is not `missing`
     **and** the performer `actor_token` appears in a claim's `actor_tokens`;
     the organization token is the opaque owner-local token from the claim;
   - `tool_to_stage` for every completed row whose recipe `tool_role` is not
     `None`, keyed by the role token;
   - `skill_to_stage` only when skill coverage is not `missing`, keyed by the
     recipe skill domain;
   - `share_milli = completed_count * 1000 // max(observed_count, 1)` for
     association edges;
   - cap nodes at `policy.max_stages` and edges at `policy.max_edges` with
     notices `stage_truncated`/`edge_truncated`;
   - emit location rows and organization rows from the same evidence.
6. Chains: build a DAG over item nodes from `resource_to_item`/`item_to_item`
   within a window; enumerate maximal paths iteratively in
   `(window_index, start_token, edge_token)` order, depth `2..MAX_CHAIN_DEPTH`,
   cap at `policy.max_chains` (notice `chain_truncated`); chain token is
   `analysis_supply_token(SUPPLY_CHAIN_PREFIX, "|".join(edge_tokens))`.
7. Return `SupplyDependencyGraph(nodes, edges, chains, locations,
   organization_rows, coverage_dimensions, notices)`.

### Required Interfaces and Contracts

- Edges only from completed observations plus explicit detached facts;
  attempts never create edges.
- No shortest path, optimization, ranking, score, or recommendation.
- Organization attribution is actor membership only; no invented
  `stage_recipe_ids` or location anchors.

### Requirement Evidence

- Original Request dimensions; `trade_networks_detection.py`/`identity.py`;
  organization rows 302-330; `_state.py` immutability norms.
- Supported combinations: single stage, two-stage chain, branching chain,
  missing infra/org/skill coverage, actor not in claims, cap exhaustion.

### Error Handling and Logging

- `WARN supply_chain_graph_partial notices=<codes>`; counts only.
- `DEBUG supply_chain_graph_built nodes=<n> edges=<n> chains=<n>`.
- Never log node labels in bulk or organization claim bodies.

### Tests

- `tests/unit/test_supply_chain_graph.py`:
  `test_harvest_emits_resource_to_item`,
  `test_craft_emits_input_to_output_edges`,
  `test_attempt_only_rows_emit_no_edge`,
  `test_structure_and_storage_edges`,
  `test_transport_edge_uses_creation_location`,
  `test_location_edge_for_each_completed_row`,
  `test_infrastructure_edge_requires_coverage`,
  `test_organization_edge_joins_actor_tokens`,
  `test_organization_edge_absent_when_actor_unclaimed`,
  `test_tool_edge_for_tool_recipe`,
  `test_skill_edge_requires_levels`, `test_share_milli_is_floor`,
  `test_chain_requires_two_stages`, `test_chain_depth_is_capped`,
  `test_chain_tokens_are_deterministic`, `test_truncation_sets_partial`,
  `test_graph_rows_are_frozen`.
- `uv run pytest tests/unit/test_supply_chain_graph.py -q`.

### Acceptance Criteria

- The extended catalog plus events yields `grain→flour→bread` and
  `plank/tool_head→fine_tool` edges.
- A completed `assemble_tool` produces `tool_to_stage` and a depth-2 chain.
- Missing optional dimensions never fabricate edges.

### Verification

- `uv run pytest tests/unit/test_supply_chain_graph.py -q` → all pass.

## Phase Risks and Mitigations

- Risk: analysis imports `world.production`. Mitigation: `SupplyRecipeSpec` only;
  boundary scan in Task 21.
- Risk: unknown item ids invent names. Mitigation: `NONE_TOKEN` + notice +
  partial coverage.
- Risk: chain enumeration explodes. Mitigation: depth/chain caps with notice.
- Risk: organization attribution is fabricated. Mitigation: actor-token join
  only, with a negative test.

## Phase Completion Checklist

- Every Task 5-7 satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
