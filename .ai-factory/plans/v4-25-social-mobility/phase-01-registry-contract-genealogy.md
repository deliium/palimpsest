# Phase 1: Registry, Contract, and Genealogy Evidence

Plan: [index.md](index.md)
Tasks: 1-4
Depends on: none

## Objective

Register the analysis-only `social_mobility` V4 context and produce a bounded,
token-only genealogy harvest plus a closed `social-mobility.v1` contract and one
identity map that later phases consume. After this phase the registry validates
at 16 contexts, the contract rejects class/rank vocabulary, both identifier
spaces resolve into one token space, and committed `KinshipEdgeRecorded` and
`AgentCreated` evidence yields ancestor/descendant chains without reading any
runtime object.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/simulation/v4_architecture.py` | `V4_CONTEXT_MAP_VERSION` (41), `_REQUIRED_CONTEXT_COUNT` (59), `V4ContextId` (63-80), `V4ContextSpec` (92-110), `V4_CONTEXTS` (113-342), `V4_ANALYSIS_ONLY_CONTEXTS` (348-354), `validate_v4_contexts` (394-452) | Exact append point and validation rules for a new analysis-only context |
| `src/simulation/versioning.py` | `V4_EVENT_REUSING_CONTEXTS` (102-116), `validate_write_pair_reservations` (130-176) | A 16th context must join the reusing set or validation fails with `v4_pair_uncovered_context` |
| `src/analysis/economic_inequality_contract.py` | `economic_inequality_token_hash` (192-197), `economic_inequality_owner_token` (200-207), `ECONOMIC_INEQUALITY_FORBIDDEN_KEYS` (131-143), `assert_economic_inequality_layer_separation` (248-269), `EconomicInequalityError` (182-189) | Contract/token/leakage pattern to mirror with social-mobility vocabulary |
| `src/analysis/economic_inequality_policy.py` | `EconomicInequalityAnalysisPolicy` (43-72), `_INT_RANGES` (26-40), `window_index_for_tick` (119-130), `validate_window_index` (133-146), `window_bounds` (149-157) | Locked policy shape, inclusive validation ranges, window arithmetic |
| `src/world/events.py` | `AgentCreated` (1707-1756: `body_id`, `agent_id`, `generation_index`, `cohort_id`), `KinshipEdgeRecorded` (1946-1990: `parent_agent_id`, `child_agent_id`, `established_tick`, `edge_id`) | Only committed generation and parent→child evidence |
| `src/world/kinship.py` | `KinshipGraph.ancestors_of` (392-422), `descendants_of` (425-455), `stable_kinship_edge_id` (38-47) | Reference semantics for depth-bounded multi-generation traversal; the new analysis must not import `world.kinship` private state |
| `src/analysis/economic_inequality_rows.py` | `_forbid_keys`/`_count`/`_token`/`_enum`/`_shares` (40-89), `EconomicPossessionRow` (92-119), `EconomicCohortMembership` (208-224) | Fail-closed row validation and token-only DTO conventions |
| `src/simulation/runner_models.py` | `AgentRunnerSpec.agent_id`/`.entity_id` (7471-7485), `TeachingAudit.agent_id` (841), `SkillAudit.agent_id` (805) | Founder identity mapping and agent-id-keyed detached evidence |
| `src/agents/cognition/practical_knowledge.py` | `PracticalKnowledgeAudit.owner_id: AgentId` (423) | Agent-id-keyed skill evidence that must be translated |
| `src/analysis/organization_operations.py` | `OrganizationAssignmentRow.occupant_id` (283) | Agent-id-keyed role evidence that must be translated |
| `tests/architecture/test_v4_context_registry.py` | `DECLARED_ORDER` (31-47), `DECLARED_PREREQUISITES` (49-67), map assertions (101-108), `text.count("\n### ") == 15` (190) | Exact registry/doc assertions that must move to 16 |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/simulation/v4_architecture.py` | modify | Append `SOCIAL_MOBILITY`, its spec, analysis-only membership, count 16, map `v4-context-map-v4` |
| `src/simulation/versioning.py` | modify | Add `V4ContextId.SOCIAL_MOBILITY` to `V4_EVENT_REUSING_CONTEXTS`; touch nothing else |
| `src/analysis/social_mobility_contract.py` | create | Closed enums, forbidden keys, error class, token helpers, identity map, layer guard |
| `src/analysis/social_mobility_policy.py` | create | Frozen policy, locked defaults, window helpers |
| `src/analysis/social_mobility_rows.py` | create | Token-only evidence and analytical DTOs |
| `src/analysis/social_mobility_genealogy.py` | create | Committed-event genealogy/generation harvest |
| `src/analysis/__init__.py` | modify | Export the new public symbols |
| `tests/architecture/test_v4_context_registry.py` | modify | `DECLARED_ORDER`, `DECLARED_PREREQUISITES`, count/map assertions |
| `tests/architecture/test_v4_architecture_invariants.py` | modify | 16-context / `v4-context-map-v4` assertions |
| `tests/unit/test_social_mobility_contract.py` | create | Contract/forbidden-key/token/layer tests |
| `tests/unit/test_social_mobility_policy.py` | create | Defaults, ranges, window arithmetic |
| `tests/unit/test_social_mobility_layers.py` | create | Layer separation and token-only rows |
| `tests/unit/test_social_mobility_identity.py` | create | Agent-id ↔ body-token translation, conflicts, unmapped owners |
| `tests/unit/test_social_mobility_genealogy.py` | create | Event-fold genealogy tests |
| `tests/unit/test_social_mobility_genealogy_properties.py` | create | Hypothesis depth/cap/determinism properties |

## Task 1: Register the analysis-only `social_mobility` V4 context

### Intent
Make `social_mobility` a first-class detached-analysis V4 context so downstream
consumers can look it up, validate it, and document it without claiming any
capability flag or write pair.

### Implementation Steps
1. In `src/simulation/v4_architecture.py`, add
   `SOCIAL_MOBILITY = "social_mobility"` as the last `V4ContextId` member after
   `ECONOMIC_INEQUALITY`.
2. Append a `V4ContextSpec` after the existing `ECONOMIC_INEQUALITY` spec with:
   - `context_id=V4ContextId.SOCIAL_MOBILITY`
   - `capability_flag=None`
   - `authority=V4Authority.DETACHED_ANALYSIS`
   - `owner_packages=("analysis",)`
   - `existing_mechanism="generational kinship, practical knowledge, teaching receipts, organization operations, and committed communication"`
   - `required_config_seam=V4_ANALYSIS_CAPTURE_SEAM`
   - `uses_existing_events=True`
   - `prerequisite_contexts=()` (evidence is committed events plus detached rows,
     not another context's artifact)
   - `non_goals` exactly:
     `"no social class, caste, stratum, elite, or underclass label"`,
     `"no objective mobility verdict, merit, desert, or prestige score"`,
     `"no composite cross-domain mobility index"`,
     `"no feedback into cognition, prompts, memory, admission, or stop selectors"`.
3. Set `_REQUIRED_CONTEXT_COUNT = 16` and
   `V4_CONTEXT_MAP_VERSION = "v4-context-map-v4"`.
4. Add `V4ContextId.SOCIAL_MOBILITY` to `V4_ANALYSIS_ONLY_CONTEXTS`.
5. In `src/simulation/versioning.py`, add the id to
   `V4_EVENT_REUSING_CONTEXTS`. Do not touch `V4_WRITE_PAIR_RESERVATIONS`,
   deepening pairs, migration stages, runner models, or compatibility ownership
   tuples.
6. Extend `validate_v4_contexts` only if a new context-specific INFO milestone
   is required; reuse the existing generic validation path and emit
   `_LOG.info("social_mobility_context_registered")` from it once, guarded by
   `context_id is V4ContextId.SOCIAL_MOBILITY`.

### Required Interfaces and Contracts
- `V4_CONTEXTS` remains an ordered tuple; the new spec is last.
- `V4_CAPABILITY_FLAGS` stays 12; owned flags stay 8; unowned stay 4.
- `v4_owner_packages()` gains `"analysis"` already present; no new package.
- No new `runner-config` schema, root field, or per-agent key.

### Requirement Evidence
- Original Request: "Use V3 genealogy and V4 economic/institutional data" and
  "Do not encode social classes" → detached analysis, no flag.
- `.ai-factory/ARCHITECTURE.md` V4-01 seam: analysis-only contexts own no world
  state and cannot reserve write pairs.

### Error Handling and Logging
- Validation failures keep existing codes: `v4_context_count`,
  `v4_context_duplicate`, `v4_context_analysis_authority`,
  `v4_pair_uncovered_context`.
- INFO `social_mobility_context_registered` with the context token only.
- Never log owner ids, generations of named agents, or evidence counts here.

### Tests
- `tests/architecture/test_v4_context_registry.py`: update `DECLARED_ORDER` to
  append `V4ContextId.SOCIAL_MOBILITY`; add
  `V4ContextId.SOCIAL_MOBILITY: frozenset()` to `DECLARED_PREREQUISITES`; assert
  `V4_CONTEXT_MAP_VERSION == "v4-context-map-v4"`, `len(V4_CONTEXTS) == 16`,
  flags 12, order equality.
- `tests/architecture/test_v4_architecture_invariants.py`: update context-count
  assertions to 16 and the map-version token.
- Add a unit assertion that `validate_v4_contexts()` passes and that
  `social_mobility` is in `V4_ANALYSIS_ONLY_CONTEXTS` and
  `V4_EVENT_REUSING_CONTEXTS`.

### Acceptance Criteria
- Registry imports and validates; 16 contexts, 12 flags, 8 owned, 4 unowned.
- `social_mobility` appears exactly once in `V4_CONTEXTS`, last.
- No write-pair, migration, runner, or compatibility change.

### Verification
- `uv run pytest tests/architecture/test_v4_context_registry.py tests/architecture/test_v4_architecture_invariants.py -q`
- Expected result: pass with 16-context assertions.

## Task 2: Lock the `social-mobility.v1` contract, policy, caps, identity map, and DTOs

### Intent
Freeze vocabulary, caps, the agent-id/body-id translation layer, and leakage
guards before any harvest so the implementer cannot invent class labels,
unbounded structures, mixed identifier spaces, or raw owner ids in
snapshot-facing rows.

### Implementation Steps
1. Create `src/analysis/social_mobility_contract.py`:
   - `SOCIAL_MOBILITY_ANALYSIS_POLICY_VERSION: Final[str] = "social-mobility.v1"`.
   - Token prefixes `smo-` (owner), `smp-` (parent→child pair), `sml-`
     (lineage); 16 lowercase hex suffix.
   - `SocialMobilityDomain` closed StrEnum with values
     `resources`, `skills`, `social_influence`, `organization_roles`,
     `educational_access`, `productive_assets`.
   - `SocialMobilityMeasure` closed StrEnum with values
     `observed_resource_item_count`, `known_technique_count`,
     `inbound_communication_partner_count`, `held_organization_role_count`,
     `educational_access_receipt_count`, `observed_productive_asset_count`.
   - `social_mobility_measures_for(domain)` returns exactly one measure.
   - `SocialMobilityLayer` with `OBJECTIVE_OUTCOME`, `OWNER_OUTCOME`,
     `ANALYTICAL_MOBILITY`.
   - `SocialMobilityCoverage` (`complete`, `partial`, `missing`) and
     `SocialMobilityAvailability` (`available`, `insufficient_samples`,
     `unavailable`).
   - `SocialMobilityPersistence` (`persistent`, `mobile`,
     `insufficient_samples`, `unavailable`).
   - `SOCIAL_MOBILITY_FORBIDDEN_KEYS` frozenset: `class`, `social_class`,
     `caste`, `stratum`, `stratum_label`, `elite`, `underclass`, `wealth`,
     `prestige`, `merit`, `desert`, `mobility_score`, `social_score`, `rank`,
     `score`, `status_label`, `legitimate_heir`, `inheritance_right`.
   - `SocialMobilityError(ValueError)` with stable `reason_code` in `args[0]`.
   - `social_mobility_token_hash(prefix, *parts)` using length-prefixed SHA-256
     exactly like `economic_inequality_token_hash`.
   - `social_mobility_owner_token(owner_id)`, `social_mobility_pair_token(
     parent_id, child_id)`, `social_mobility_lineage_token(root_id, tail_id)`.
   - `assert_social_mobility_layer_separation(*row_groups)`: each group must be
     homogeneous in `layer`; objective, owner, and analytical groups may not be
     mixed; reject any row carrying a forbidden key.
2. Add `SocialMobilityIdentityMap` to the contract module:
   - `forward: Mapping[str, str]` (`agent_id -> body_token`) and `reverse:
     Mapping[str, str]` (`body_token -> agent_id`), both immutable.
   - `token_for_agent(agent_id) -> str | None`, `agent_for_token(token) ->
     str | None`, and `require_token(agent_id)` raising
     `social_mobility_unmapped_owner`.
   - `build_social_mobility_identity_map(*, runner_config, events)`:
     founders come from `runner_config.agents` (`AgentRunnerSpec.agent_id` and
     `.entity_id`); mid-run owners come from committed `AgentCreated`,
     `AgentEnteredWorld`, and `AgentInitializationRecorded` (`agent_id` plus
     `body_id`). A later duplicate that disagrees with an existing mapping is
     rejected with `social_mobility_identity_conflict`; agreement is a no-op.
   - Owners with neither a config entry nor a committed mapping stay unmapped
     and are reported by their consumers, never guessed.
   - Body ids and agent ids are different identifier spaces: objective events
     (`actor_id`, `recipient_id`, `resulting_holder_id`) are `EntityId`, while
     `KinshipEdgeRecorded`, `PracticalKnowledgeAudit.owner_id`,
     `TeachingAudit.agent_id`, and `OrganizationAssignmentRow.occupant_id` are
     stable `AgentId` strings. Every harvest translates through this map.
3. Create `src/analysis/social_mobility_policy.py`:
   - `SocialMobilityAnalysisPolicy` frozen slots dataclass with defaults:
     `window_ticks=32`, `max_windows=512`, `min_mobility_pairs=8`,
     `rank_bins=5`, `max_generation_lag=4`, `max_lineage_depth=8`,
     `max_generation_index=32`, `max_event_rows=200_000`, `max_owners=4_096`,
     `max_pairs=4_096`, `max_domain_rows=4_096`,
     `max_generation_rows=1_024`, `max_coverage_rows=1_024`,
     `max_notices=8`, `persistence_share_milli=500`.
   - `_INT_RANGES` inclusive ranges: windows 1-512, `min_mobility_pairs` 2-64,
     `rank_bins` 2-10, `max_generation_lag` 1-4, `max_lineage_depth` 1-8,
     `max_generation_index` 0-32, caps 0-1_000_000,
     `persistence_share_milli` 0-1000.
   - `SOCIAL_MOBILITY_ANALYSIS_LOCKED_POLICY` read-only mapping and
     `default_social_mobility_analysis_policy()` singleton.
   - `with_window_end(window_end, policy=None)` truncating `max_windows` to
     `window_end // window_ticks + 1`.
   - `window_index_for_tick`, `validate_window_index`, `window_bounds` matching
     the economic helpers' arithmetic and error codes
     (`social_mobility_window_out_of_range`).
4. Create `src/analysis/social_mobility_rows.py` with token-only frozen
   dataclasses and `__post_init__` validation:
   - `SocialMobilityOutcomeRow(owner_token, generation_index, tick,
     window_index, domain, measure, quantity, layer)`; `quantity >= 0`.
   - `SocialMobilityGenealogyRow(parent_token, child_token, parent_generation,
     child_generation, established_tick, window_index)`.
   - `SocialMobilityPairRow(ancestor_token, descendant_token, generation_lag,
     domain, ancestor_quantity, descendant_quantity, ancestor_bin,
     descendant_bin, ancestor_window_index, descendant_window_index, resolved)`.
   - `SocialMobilityDomainRow` fields: `window_index`, `window_tick`, `domain`,
     `measure`, `pair_count`, `resolved_pair_count`,
     `rank_correlation_milli` (-1000..1000), `same_bin_share_milli`,
     `upward_share_milli`, `downward_share_milli`,
     `mean_absolute_rank_change_milli`, `persistence_direction`, `coverage`,
     `availability`.
   - `SocialMobilityGenerationRow(window_index, window_tick,
     generation_index, owner_count, pair_count, comparable,
     same_bin_share_milli, upward_share_milli, downward_share_milli,
     coverage, availability)`.
   - `SocialMobilityCoverageRow(window_index, window_tick, generation_count,
     owner_count, genealogy_edge_count, pair_count, resolved_pair_count,
     unresolved_pair_count, domain_available_count, truncated, coverage)`.
   - `SocialMobilityLayerBundle(objective_rows, owner_rows, pair_rows,
     domain_rows, generation_rows, coverage_row)` asserting separation.
   - Shared helpers `_forbid_keys`, `_count`, `_milli`, `_token`, `_enum`.
5. Add exports to `src/analysis/__init__.py` next to the economic-inequality
   block, with `__all__` entries.

### Required Interfaces and Contracts
- Every snapshot-facing row stores tokens, never raw `owner_id` strings.
- Every agent-id-keyed source is translated through `SocialMobilityIdentityMap`
  before a token is minted; an unmapped id never becomes a fabricated owner.
- `rank_correlation_milli` never carries `-0`; use `0` when the rounded value is
  zero.
- `persistence_direction` must be a closed enum value, never free text.
- Policy validation fails closed with `ValueError` carrying
  `social_mobility_policy_<field>`.

### Requirement Evidence
- Original Request "Do not encode social classes" → forbidden-key set and
  enum-only persistence vocabulary.
- `.ai-factory/ARCHITECTURE.md` Key Principle 3 (frozen contracts, fail-closed
  unknown fields) and Key Principle 5 (metadata-only logging).

### Error Handling and Logging
- DEBUG accepted/rejected row counts at module boundaries.
- WARN `social_mobility_invalid_input` with a reason code only.
- ERROR stable codes `social_mobility_policy_range`,
  `social_mobility_row_invalid`; never log quantities, tokens, or generations.

### Tests
- `tests/unit/test_social_mobility_contract.py`: enum closure, measure lookup,
  forbidden-key rejection, token prefix/length/determinism, layer guard
  acceptance/rejection.
- `tests/unit/test_social_mobility_policy.py`: defaults, inclusive bounds,
  rejection of out-of-range values, `window_index_for_tick` boundaries,
  `with_window_end` truncation.
- `tests/unit/test_social_mobility_layers.py`: objective/owner/analytical
  separation; a raw-owner-id row is rejected.
- `tests/unit/test_social_mobility_identity.py`: founder mapping from
  `runner_config.agents`, mid-run mapping from `AgentCreated` /
  `AgentEnteredWorld` / `AgentInitializationRecorded`, agreeing duplicates,
  conflicting duplicate rejection, unmapped owner returns `None` and
  `require_token` raises, and deterministic token stability across a body-id
  and agent-id round trip.

### Acceptance Criteria
- Contract and policy are importable from `analysis`.
- No forbidden vocabulary can be constructed through the public row types.
- Policy defaults match the locked summary in `index.md`.
- A founder parent and a mid-run child resolve to the same body-token space
  used by objective events.

### Verification
- `uv run pytest tests/unit/test_social_mobility_contract.py tests/unit/test_social_mobility_policy.py tests/unit/test_social_mobility_layers.py tests/unit/test_social_mobility_identity.py -q`
- Expected result: pass.

## Task 3: Harvest committed genealogy and generation labels

### Intent
Turn `AgentCreated` and `KinshipEdgeRecorded` into bounded, deterministic
genealogy rows with ancestor depth information, so mobility pairing never
touches `WorldState`, `KinshipGraph`, or runtime registries.

### Implementation Steps
1. Create `src/analysis/social_mobility_genealogy.py`:
   - `SocialMobilityGenealogyHarvest` dataclass: `edges`, `generations`
     (token→generation mapping as sorted tuple of `(owner_token, generation)`),
     `lineages`, `notices`, `coverage`, `event_count`, `owner_count`,
     `max_generation_index`.
   - `harvest_social_mobility_genealogy(events, *, identity_map,
     policy=None)`:
     1. Sort committed `WorldEvent` values by `(tick, sequence)`.
     2. Fold `AgentCreated` rows: resolve `event.body_id.value` through
        `identity_map.require_token(event.agent_id)` so generation labels live
        in the same body-token space as objective events; `generation =
        event.generation_index`. Reject negative or
        `> policy.max_generation_index` generations into a notice rather than
        inventing a number.
     3. For any owner seen in events but absent from `AgentCreated`, assign
        generation 0 (bootstrap rule) and record it in `generations`.
     4. Fold `KinshipEdgeRecorded` into `SocialMobilityGenealogyRow` by
        translating `parent_agent_id` and `child_agent_id` through
        `identity_map`; an unmapped side emits
        `social_mobility_unmapped_owner`, drops the edge, and sets coverage
        `partial`. Deduplicate by `(parent_token, child_token)` keeping the
        earliest tick. Self-edges are impossible upstream but are rejected with
        `social_mobility_edge_invalid`.
     5. Build adjacency lists from edges and compute depth-bounded ancestor
        chains per child with BFS up to `max_lineage_depth`; store only
        `social_mobility_lineage_token(root_token, tail_token)` plus lag ints,
        never raw ids.
     6. Apply `max_owners` and `max_event_rows` deterministically: sort tokens,
        keep the prefix, append `social_mobility_owners_truncated` or
        `social_mobility_events_truncated` notices, set coverage `partial`.
     7. Missing generation or missing child creation evidence yields
        `coverage=partial` and `social_mobility_missing_generation` notice; no
        fabricated edge.
2. Do not import `world.kinship`, `world._*`, `simulation`, or experiments.

### Required Interfaces and Contracts
- `harvest_social_mobility_genealogy(events, *, identity_map, policy=None) ->
  SocialMobilityGenealogyHarvest` is pure.
- Identical input events produce identical row order; sort key is
  `(established_tick, parent_token, child_token)`.
- Empty events return an empty harvest with `coverage=missing`; it does not
  raise.
- An unmapped agent id is reported and dropped; it never mints an owner token.

### Requirement Evidence
- `src/world/events.py:AgentCreated` (generation label) and
  `src/world/events.py:KinshipEdgeRecorded` (objective parent→child edge).
- `.ai-factory/ARCHITECTURE.md` authority rule: analysis may read committed
  events only.

### Error Handling and Logging
- DEBUG event count, accepted edge count, owner count, max generation.
- WARN `social_mobility_missing_generation`,
  `social_mobility_generation_out_of_range`,
  `social_mobility_unmapped_owner`, `social_mobility_genealogy_truncated`.
- ERROR `social_mobility_genealogy_invalid` with a code; never log owner ids.

### Tests
- `tests/unit/test_social_mobility_genealogy.py`: bootstrap generation 0,
  mid-run `AgentCreated` with founder config mapping, multi-generation chain
  depth, duplicate edge dedupe, unmapped parent notice, missing generation
  notice, owner/event caps and partial coverage.
- `tests/unit/test_social_mobility_genealogy_properties.py`: Hypothesis
  properties for deterministic ordering, token-only output, lag ≤
  `max_generation_lag`, and prefix stability under appended events.

### Acceptance Criteria
- A 3-generation fixture yields lag 1, 2, and 3 lineage entries.
- A founder parent and a mid-run child resolve into the same token space as
  objective rows.
- No raw owner id appears in any emitted row or repr.
- Caps truncate deterministically and report `partial`.
- Unmapped ids are reported, never guessed.

### Verification
- `uv run pytest tests/unit/test_social_mobility_genealogy.py tests/unit/test_social_mobility_genealogy_properties.py -q`
- Expected result: pass.

## Task 4: Harvest the six outcome domains

### Intent
Produce one quantity per owner per domain and window with an explicit evidence
source, so mobility is computed over observed outcomes rather than inferred
class membership.

### Implementation Steps
1. Create `src/analysis/social_mobility_outcomes.py`:
   - `SocialMobilityOutcomeHarvest` dataclass: `rows`, `notices`, `coverage`,
     `event_count`, `owner_count`, `domain_counts`, `unknown_kind_count`.
   - `harvest_social_mobility_outcomes(events, *, identity_map,
     practical_knowledge_audits=(), teaching_audits=(),
     organization_operation_rows=(), recipe_output_kinds=None,
     recipe_structure_kinds=None, policy=None)`.
2. Resolve every source into the body-token space before counting:
   - objective event rows already carry `EntityId`; mint
     `social_mobility_owner_token(entity_id)`.
   - `PracticalKnowledgeAudit.owner_id` (`AgentId`), `TeachingAudit.agent_id`
     (`AgentId`), and `OrganizationAssignmentRow.occupant_id` (agent-id string)
     are translated with `identity_map.require_token(...)`.
   - Skip speech events whose `event.actor_id` is `None`; skip audit/assignment
     rows whose owner is unmapped and emit `social_mobility_unmapped_owner`
     once, with coverage `partial`.
3. Sources, one per domain (exact mapping):
   - `resources` → reuse `analysis.economic_inequality_events
     .harvest_economic_inequality_evidence` possession rows; quantity is
     `max(0, observed_item_count - observed_tool_count)`. Layer
     `OBJECTIVE_OUTCOME`.
   - `productive_assets` → reuse the same possession/access rows; quantity is
     `observed_tool_count + accessible_infrastructure_count +
     accessible_storage_count`, clamped at `policy.max_pairs * 10_000` to keep
     values bounded. Document it as an additive count of observed physical
     assets, not a wealth score. Layer `OBJECTIVE_OUTCOME`.
   - `skills` → group active `PracticalKnowledgeAudit` rows by
     `audit.owner_id`; quantity is the count of distinct active `content_key`
     values acquired at or before the window end. Layer `OWNER_OUTCOME`.
   - `educational_access` → count distinct educational receipts per owner:
     `TeachingAudit.agent_id` rows (any `store`) plus
     `RepositoryMemberRetrieved.actor_id` committed events. Layer
     `OBJECTIVE_OUTCOME`.
   - `social_influence` → for committed `Talked`/`Asked`/`Told` events, count
     distinct `event.actor_id` values whose `recipient_id` equals the owner
     within the window. This is observed inbound communication, never
     authority. Layer `OBJECTIVE_OUTCOME`.
   - `organization_roles` → from `OrganizationOperationHarvestRows.assignments`,
     count distinct `office_id` values where `occupant_id` equals the owner and
     the row stance is not `rejected`; retain `contested_count` only as a
     diagnostic notice. Layer `OWNER_OUTCOME`.
4. Emit `SocialMobilityOutcomeRow` sorted by
   `(window_index, domain.value, owner_token)`.
5. Missing source data marks that domain `unavailable` through the harvest's
   `domain_counts`; never zero-fill an unobserved owner.
6. Populate `window_index` with `window_index_for_tick(event.tick, policy)`.

### Required Interfaces and Contracts
- One measure name per domain, exactly as `social_mobility_measures_for`
  returns.
- `quantity` is a non-negative int; floats are rejected.
- The harvest never reads `WorldState`, `AgentRuntime`, stores, or APIs.
- `recipe_output_kinds`/`recipe_structure_kinds` are optional mappings; an
  empty mapping leaves kinds `unknown` and excludes unknown tools from counts.
- Every owner token is minted after identity translation; a raw `AgentId` never
  appears in a row.

### Requirement Evidence
- Original Request six outcome domains.
- `src/world/events.py:AgentCreated` (`body_id` + `agent_id`),
  `AgentEnteredWorld`, and `AgentInitializationRecorded` (identity sources).
- `src/analysis/economic_inequality_events.py:harvest_economic_inequality_evidence`
  (possession/access evidence).
- `src/agents/cognition/practical_knowledge.py:PracticalKnowledgeAudit` (419-501).
- `src/simulation/runner_models.py:TeachingAudit` (837-868) and
  `export_teaching_audits` (`src/simulation/runner.py:6157-6232`).
- `src/world/events.py:RepositoryMemberRetrieved` (2068-2098),
  `Talked`/`Asked`/`Told` (707-763).
- `src/analysis/organization_operations.py:OrganizationAssignmentRow`
  (274-299).

### Error Handling and Logging
- DEBUG per-domain row counts and unknown-kind count.
- WARN `social_mobility_unknown_item_kind`,
  `social_mobility_domain_unavailable`, `social_mobility_unmapped_owner`,
  `social_mobility_outcome_truncated`.
- ERROR `social_mobility_outcome_invalid` with a reason code only.

### Tests
- `tests/unit/test_social_mobility_outcomes.py`: each domain from real event
  shapes, tool exclusion from resources, repository+teaching receipts, inbound
  speech partners with and without `actor_id`, assignment occupants, an
  agent-id-only audit row translated to the body-token owner, unmapped-owner
  skip, missing-source unavailability.
- `tests/unit/test_social_mobility_outcomes_properties.py`: Hypothesis for
  non-negative quantities, deterministic order, one measure per domain.

### Acceptance Criteria
- All six domains can be produced from committed evidence plus detached audits.
- Unknown evidence is `unavailable`, never `0`.
- A detached audit keyed only by `AgentId` lands on the same token as the
  owner's objective events.
- No class/rank vocabulary or raw owner ids in rows.

### Verification
- `uv run pytest tests/unit/test_social_mobility_outcomes.py tests/unit/test_social_mobility_outcomes_properties.py -q`
- Expected result: pass.

## Phase Risks and Mitigations
- Risk: `WorldEvent` ordering or field names differ from the cited ranges.
  Mitigation: reuse `economic_inequality_events` ordering and inspect only the
  cited fields; add a fixture test per event shape.
- Risk: `TeachingAudit` shape differs between runner versions.
  Mitigation: accept only rows exposing `agent_id`, `store`, and `tick`; skip
  malformed rows with a bounded notice rather than raising.
- Risk: a reviewer reads the additive `productive_assets` count as a wealth
  score. Mitigation: the metric spec opportunity text and docs state it is a
  descriptive physical-asset count, and no cross-domain composite exists.

## Phase Completion Checklist
- Every Task in this phase satisfies its acceptance criteria.
- `uv run pytest tests/architecture/test_v4_context_registry.py tests/architecture/test_v4_architecture_invariants.py tests/unit/test_social_mobility_*.py -q` passes.
- `index.md` Task 1-4 checkboxes are updated after verification.
