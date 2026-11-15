# Phase 1: Registry, Contract, and Objective Evidence

Plan: [index.md](index.md)
Tasks: 1-4
Depends on: none

## Objective

Register `economic_cascades` as the seventeenth V4 context (analysis-only, no
flag, `v4-context-map-v5`), lock the `economic-cascades.v1` contract, policy,
caps, and token-only row types, and harvest the five requested objective
disruption classes plus the production dependency structure from committed
events and detached recipe facts. After this phase the analysis owns closed
inputs and deterministic rows; no world rule, event, runner schema, or write
pair changes.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/simulation/v4_architecture.py` | `V4ContextSpec` (93-111), `V4_CONTEXT_MAP_VERSION` (41), `_REQUIRED_CONTEXT_COUNT` (59), `V4_CONTEXTS` (114-362), `V4_ANALYSIS_ONLY_CONTEXTS` (368-375), `validate_v4_contexts` (415-475) | Exact registry shape; a flagless context must be `DETACHED_ANALYSIS`, `("analysis",)`, `analysis_capture` |
| `src/simulation/versioning.py` | `V4_EVENT_REUSING_CONTEXTS` (102-117), `validate_write_pair_reservations` (131-177) | A new context must be reuse-only or coverage validation fails |
| `src/analysis/supply_chain_events.py` | `SupplyRecipeSpec` (77-120), `SupplyStageObservation` (122-160), `supply_evidence_from_events` (395-403) | Detached recipe structure; no `ProductionRecipe` import |
| `src/analysis/supply_chain_contract.py` | `SupplyEdgeKind` (85-96), `SupplyBottleneckKind` (98-106) | Existing dependency vocabulary to mirror, not re-export |
| `src/world/events.py` | `ResourceNodeDepleted` (1270), `ResourceHarvested` (1032), `RouteConditionChanged` (2921), `InfrastructureDestroyed` (2860), `Died` (991), `CraftStarted` (1076), `ItemCrafted` (1105) | Committed evidence for the five disruption classes |
| `src/world/_production.py` | `_availability` (287-367), `materials_unavailable` (251-263), tool duration/probability helpers (79-91) | Proves propagation is already emergent: missing inputs block admission; missing tools lower speed/probability |
| `src/analysis/economic_inequality_contract.py` | forbidden keys (131-143), layer separation (248-269) | Contract template for closed vocabulary and leakage guard |
| `src/analysis/economic_inequality_policy.py` | policy field/ranges (26-72), `default_*` (86-91) | Frozen validated policy template |
| `src/analysis/social_mobility_contract.py` | policy/token/error header (8-17) | Newest contract template |
| `src/analysis/economic_inequality_rows.py` | frozen token-only row dataclasses | Row DTO convention |
| `tests/architecture/test_v4_context_registry.py` | `DECLARED_ORDER` (31), counts (103-110), analysis-only set (113-155), doc heading count (195-202) | Pin sweep owned by Task 18 |
| `tests/architecture/test_v4_architecture_invariants.py` | 16/12/8/4 pins (174-226), v57 source scan (252-257) | Pin sweep owned by Task 18 |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/simulation/v4_architecture.py` | modify | Append `V4ContextId.ECONOMIC_CASCADES`, spec, analysis-only set entry, count 17, map `v4-context-map-v5` |
| `src/simulation/versioning.py` | modify | Append the id to `V4_EVENT_REUSING_CONTEXTS`; change nothing else |
| `src/analysis/economic_cascades_contract.py` | create | Policy token, closed disruption/dependency/state/layer enums, forbidden keys, token minting, layer guard, error codes |
| `src/analysis/economic_cascades_policy.py` | create | Frozen validated policy, defaults, caps, window/lag helpers |
| `src/analysis/economic_cascades_rows.py` | create | Token-only frozen row dataclasses |
| `src/analysis/economic_cascades_events.py` | create | Five-class disruption harvest from committed events |
| `src/analysis/economic_cascades_dependencies.py` | create | Recipe-stage graph and observed dependency edges |
| `src/analysis/__init__.py` | modify | Export contract, policy, rows, harvest, and dependency symbols |
| `tests/unit/test_economic_cascades_contract.py` | create | Closed vocabulary, forbidden keys, token minting |
| `tests/unit/test_economic_cascades_policy.py` | create | Defaults, ranges, frozen behavior |
| `tests/unit/test_economic_cascades_layers.py` | create | Leakage guard |
| `tests/unit/test_economic_cascades_events.py` | create | Five disruption classes from real event fixtures |
| `tests/unit/test_economic_cascades_events_properties.py` | create | Ordering/cap invariants |
| `tests/unit/test_economic_cascades_dependencies.py` | create | Recipe graph, depth bound, edge kinds |
| `tests/architecture/test_economic_cascades_invariants.py` | create | 17/12/8/4, no flag, no schema, no write pair |

## Task 1: Register the analysis-only `economic_cascades` V4 context

### Intent
Give the feature a declared home in the V4 registry without claiming a
capability flag, runner schema, command, event, or write pair. Later tasks use
`V4ContextId.ECONOMIC_CASCADES` and `economic-cascades.v1`.

### Implementation Steps
1. In `src/simulation/v4_architecture.py`:
   - Append `ECONOMIC_CASCADES = "economic_cascades"` last in `V4ContextId`.
   - Append a `V4ContextSpec` last in `V4_CONTEXTS` with:
     `context_id=V4ContextId.ECONOMIC_CASCADES`, `capability_flag=None`,
     `authority=V4Authority.DETACHED_ANALYSIS`, `owner_packages=("analysis",)`,
     `existing_mechanism="detached cascade analysis over committed production, route, infrastructure, lifecycle, and tool evidence"`,
     `required_config_seam=V4_ANALYSIS_CAPTURE_SEAM`, `uses_existing_events=True`,
     `prerequisite_contexts=(V4ContextId.SUPPLY_CHAINS,)`,
     and four non-goals: no cascade engine in `WorldEngine`; no new command,
     event, or write pair; no severity/impact/risk score; no scripted downstream
     outcome.
   - Add the id to `V4_ANALYSIS_ONLY_CONTEXTS`.
   - Set `_REQUIRED_CONTEXT_COUNT = 17` and
     `V4_CONTEXT_MAP_VERSION = "v4-context-map-v5"`.
   - Add `_LOG.info("economic_cascades_context_registered")` once at import, next
     to the existing registration logs.
2. In `src/simulation/versioning.py`, append the id to
   `V4_EVENT_REUSING_CONTEXTS`. Do not touch `V4_WRITE_PAIR_RESERVATIONS`,
   deepening pairs, migration stages, `runner_models.py`, `compatibility.py`, or
   `runner_serialization.py`.
3. Create `tests/architecture/test_economic_cascades_invariants.py` asserting:
   map `v4-context-map-v5`; `len(V4_CONTEXTS) == 17`;
   `len(V4_CAPABILITY_FLAGS) == 12`; owned flags stay the existing eight;
   four unowned; the id is last, analysis-only, reuse-only, prerequisite
   `supply_chains`; `"runner-config-v57"` is absent from `src/`; no
   `alembic/versions/0018*`; `ECONOMIC_CASCADES` has no capability flag.
4. Update only the registry-shape assertions that hard-code the previous last
   context: `test_v4_25_registers_analysis_only_social_mobility_context` in
   `tests/architecture/test_v4_architecture_invariants.py` must assert
   `V4_CONTEXTS[-2]` is `social_mobility` and `V4_CONTEXTS[-1]` is
   `economic_cascades`; `DECLARED_ORDER` and `DECLARED_PREREQUISITES` in
   `tests/architecture/test_v4_context_registry.py` gain the appended entry.
   Do not update the remaining 16-count literals, docs heading counts, or the
   metric catalog in this task; Task 18 sweeps them in one pass and the full
   suite stays expected-red until then.

### Required Interfaces and Contracts
- `V4ContextId.ECONOMIC_CASCADES` is the only new registry token.
- `validate_v4_contexts()` and `validate_write_pair_reservations()` pass.
- Prerequisite graph stays acyclic; `supply_chains` is a declared context.
- No reserved or deepening write pair is assigned.

### Requirement Evidence
- Original Request "Model objective disruptions to production networks" plus
  `.ai-factory/ARCHITECTURE.md` V4-01 seam (analysis-only contexts own no flag).
- `src/simulation/v4_architecture.py` rules at 438-460.
- Precedent: V4-24 `economic_inequality` and V4-25 `social_mobility`
  registrations (context appended last, map bump, no flag).

### Error Handling and Logging
- INFO `economic_cascades_context_registered` (no payload fields).
- Validation failures surface existing codes (`v4_context_count`,
  `v4_context_analysis_flag`, `v4_pair_uncovered_context`); never swallow them.
- Never log context payloads, owner tokens, or configuration values.

### Tests
- `tests/architecture/test_economic_cascades_invariants.py` as listed above.
- Extend the existing mutation test in
  `tests/architecture/test_v4_context_registry.py` in Task 18, not here.

### Acceptance Criteria
- Registry validates at 17 contexts / 12 flags / 8 owned / 4 unowned.
- `economic_cascades` is analysis-only, flagless, reuse-only.
- No runner, write-pair, or migration change exists.

### Verification
- `uv run python -c "from simulation.v4_architecture import validate_v4_contexts; validate_v4_contexts()"`
- `uv run python -c "from simulation.versioning import validate_write_pair_reservations as v; v()"`
- `uv run pytest tests/architecture/test_economic_cascades_invariants.py -q`
- Expected result: validators return cleanly and the new invariants pass. The
  shared 16-context pins remain expected-red until Task 18; record that state in
  the verification receipt rather than hiding it.

## Task 2: Lock the `economic-cascades.v1` contract, policy, caps, and row DTOs

### Intent
Make every downstream consumer depend on one closed vocabulary so no
implementation can invent a class, a severity, or a scripted outcome. The
contract is shared by analysis, snapshot, routes, and docs.

### Implementation Steps
1. Create `src/analysis/economic_cascades_contract.py`:
   - `ECONOMIC_CASCADES_POLICY_VERSION = "economic-cascades.v1"`;
     `CHAIN_TOKEN_PREFIX = "casc-"`; `PROXY_EVIDENCE_TOKEN = "proxy:tool-stage"`;
     `NONE_TOKEN = "none"`.
   - `CascadeDisruptionKind(StrEnum)`: `resource_loss`, `route_closure`,
     `infrastructure_destruction`, `population_loss`, `tool_shortage`.
   - `CascadeDependencyKind(StrEnum)`: `resource_input`, `item_input`,
     `tool_dependency`, `infrastructure_dependency`, `transport_dependency`.
     Labor participation is an explicit join passed to chain linking, not an edge
     row, because an actor is not a recipe node.
   - `CascadeChainState(StrEnum)`: `linked`, `unlinked`, `unresolved`,
     `unavailable`.
   - `CascadeCoverage(StrEnum)`: `complete`, `partial`, `missing`.
   - `CascadeAvailability(StrEnum)`: `available`, `insufficient_samples`,
     `unavailable`.
   - `CascadeLayer(StrEnum)`: `objective_disruption`, `dependency_structure`,
     `analytical_chain`.
   - `CASCADE_FORBIDDEN_KEYS`: frozenset of `class`, `caste`, `stratum`,
     `elite`, `underclass`, `severity`, `criticality`, `priority`,
     `impact_score`, `cascade_score`, `risk_score`, `blame`, `fault`,
     `root_cause`, `culprit`, `economic_damage`, `loss_value`, `price`,
     `money`, `status_label`.
   - `mint_chain_token(*, disruption_kind, upstream_token, downstream_recipe_id,
     depth, lag_windows, window_index, evidence_tokens) -> str` — SHA-256 over a
     canonical `\x1f`-joined string, take 16 hex chars, prefix `casc-`; reject
     empty parts and unstable ids.
   - `assert_economic_cascade_layer_separation(*, objective_rows,
     dependency_rows, analytical_rows)` — reject any forbidden key, any
     **agent-id owner token** in analytical rows, any analytical token in
     objective rows, and any objective row claiming a chain state. Objective
     entity and body tokens are allowed in the objective and dependency layers;
     snapshots and routes never expose them.
   - `ECONOMIC_CASCADES_ERROR_CODES` frozenset:
     `economic_cascades_invalid_policy`, `_invalid_cap`, `_invalid_chain`,
     `_invalid_event_order`, `_layer_violation`, `_unstable_token`,
     `_forbidden_key`, `_nonfinite_value`, `_invalid_recipe_spec`.
2. Create `src/analysis/economic_cascades_policy.py`:
   - `EconomicCascadesPolicy` frozen dataclass with
     `window_ticks=32`, `max_windows=512`, `max_events=200_000`,
     `max_disruptions=4_096`, `max_stages=4_096`,
     `max_dependency_edges=4_096`, `max_chains=2_048`,
     `max_propagation_rows=1_024`, `max_coverage_rows=1_024`,
     `max_notices=8`, `max_chain_depth=6`,
     `max_propagation_lag_windows=2`, `min_linked_chains=3`,
     `shortfall_share_milli=250`.
   - `__post_init__` rejects bools-as-ints, out-of-range values, and
     `shortfall_share_milli` outside `1..1000` with `_invalid_policy` /
     `_invalid_cap`.
   - `window_index(tick)`, `window_tick(index)`, `window_bounds(tick)`,
     `default_policy()`, `policy_with(**overrides)`.
3. Create `src/analysis/economic_cascades_rows.py` with frozen slots dataclasses,
   all tokens validated as non-empty stable strings and ints validated as
   non-negative (bools rejected):
   - `CascadeDisruptionRow(window_index, window_tick, sequence, kind,
     subject_token, magnitude_count, evidence_event_token, coverage)`
   - `CascadeEpisodeRow(window_index, window_tick, kind, disruption_count,
     magnitude_total, subject_count, first_sequence, last_sequence, coverage)`
   - `CascadeStageRow(window_index, window_tick, recipe_id, action, output_name,
     output_kind, location_token, demand_count, attempt_count, completion_count,
     tool_dependent, has_infrastructure, coverage)`
   - `CascadeDependencyEdgeRow(window_index, window_tick, upstream_token,
     downstream_recipe_id, kind, depth, evidence_count)`
   - `CascadeChainRow(chain_token, window_index, window_tick, disruption_kind,
     upstream_token, downstream_recipe_id, depth, lag_windows,
     shortfall_share_milli, state, coverage)`
   - `CascadePropagationRow(window_index, window_tick, disruption_kind,
     chain_count, linked_chain_count, unlinked_chain_count,
     unresolved_chain_count, mean_depth_milli, mean_lag_milli,
     downstream_stage_count, coverage, availability)`
   - `CascadeCoverageRow(window_index, window_tick, window_count, event_count,
     disruption_count, stage_count, dependency_edge_count, labor_join_count,
     chain_count, linked_chain_count, truncated, coverage, availability)`
4. Do not define any composite score, severity, ranking, or class field.

### Required Interfaces and Contracts
- Closed enums are the only vocabulary; `StrEnum` values are lower_snake.
- Every row rejects `CASCADE_FORBIDDEN_KEYS` at construction.
- `CascadeChainState` never contains `observed_cause`, `caused_by`, or
  `outcome`.
- Policy is frozen; helpers are pure and integer-only.

### Requirement Evidence
- Original Request "Do not script downstream outcomes" and "Provide
  dependency/cascade analytics".
- `.ai-factory/ARCHITECTURE.md` Key Principle 1 (objective, owner, analysis
  separation) and requirement 1 (accepted-set/exact-key-set evolution).
- `src/analysis/economic_inequality_contract.py:131-143,248-269`.

### Error Handling and Logging
- Raise the closed error codes above; never include tokens in messages.
- DEBUG `economic_cascades_policy_resolved` with counts only.
- ERROR `economic_cascades_contract_violation` with the code only.

### Tests
- `tests/unit/test_economic_cascades_contract.py`: every enum member set,
  forbidden key rejection per key, chain-token determinism across hash seeds
  (subprocess with `PYTHONHASHSEED=0/1`), empty-token rejection.
- `tests/unit/test_economic_cascades_policy.py`: defaults, boundary
  acceptance/rejection, frozen immutability, window arithmetic.
- `tests/unit/test_economic_cascades_layers.py`: objective row carrying
  `chain_token` rejected; analytical row carrying an owner token rejected;
  clean three-layer input accepted.

### Acceptance Criteria
- Contract and policy import with no dependency on `world`, `simulation`, or
  `experiments`.
- Chain tokens are stable and content-addressed.
- No forbidden key can be constructed in any row type.

### Verification
- `uv run pytest tests/unit/test_economic_cascades_contract.py tests/unit/test_economic_cascades_policy.py tests/unit/test_economic_cascades_layers.py -q`
- Expected result: pass.

## Task 3: Harvest the five objective disruption classes

### Intent
Turn committed objective evidence into one row type per disruption, so later
chain linking never invents a cause. Missing evidence stays absent, never zero.

### Implementation Steps
1. Create `src/analysis/economic_cascades_events.py`:
   - `CascadeDisruptionResult` dataclass: `rows`, `notices`, `coverage`,
     `event_count`, `kind_counts`.
   - `harvest_economic_cascade_disruptions(events, *, policy=None)` accepting
     only committed event objects, dispatched by exact class:
     - `resource_loss`: `ResourceNodeDepleted` (one row per zero crossing). The
       subject is the `recipe_id` of the most recent preceding
       `ResourceHarvested` for that node, because recipe inputs are named while
       nodes are opaque; when no harvest precedes the depletion the subject is
       `resource:<node_token>` and chain linking reports `unresolved` rather
       than guessing a recipe. `magnitude_count` is 1. This lookup is valid
       because `ResourceNodeDepleted` is emitted as `extra_event_details`
       **after** the primary `ResourceHarvested` for the same action
       (`src/world/_rules.py:3154-3157`); do not reverse the order.
     - `route_closure`: `RouteConditionChanged` where the current status is
       `closed` and the previous status was not `closed`. Subject is the
       ordered `(origin_token, destination_token)` edge token; magnitude is 1.
     - `infrastructure_destruction`: `InfrastructureDestroyed`; subject is the
       asset token; magnitude is 1.
     - `population_loss`: `Died`; subject is the objective body token; magnitude
       is 1. The body token stays in the objective layer and is never exposed by
       a snapshot or route.
     - `tool_shortage`: not emitted by this event harvest, because no committed
       event records tool stock or tool loss. Task 5 synthesizes the documented
       tool-production decline proxy from adjacent-window stage rows.
   - Sort rows by `(window_index, kind.value, sequence, subject_token)` before
     applying `policy.max_disruptions`; keep the deterministic prefix and:
     - append one `disruptions_truncated` notice,
     - set `coverage=partial`.
   - `policy.max_events` truncates the scanned event prefix deterministically
     and appends `events_truncated`.
2. Keep extraction class-based (`type(event) is ...` or a closed dispatch map);
   do not parse payloads by attribute guessing.
3. Do not import `WorldState`, `KinshipGraph`, runtime, or store objects.

### Required Interfaces and Contracts
- One row per observed disruption; no row is synthesized from a rate.
- `tool_shortage` is declared in the vocabulary but synthesized in Task 5 from
  stage rows; it is `unavailable` when no tool-output stage exists.
- A `closed` route that stays closed does not emit a repeated row.
- Event order is committed order; out-of-order ticks raise
  `_invalid_event_order`.

### Requirement Evidence
- Original Request five disruption classes.
- `src/world/events.py` class definitions cited in the evidence table.
- `src/world/_rules.py:3154-3157` (`RuleApplication.event_details` returns the
  primary event then `extra_event_details`), which proves the depletion witness
  follows the harvest event.
- `src/world/travel_network.py:103-119` (`RouteStatus.CLOSED`),
  `src/world/_infrastructure.py:636-687` (`InfrastructureDestroyed`),
  `src/world/_physical.py:528-550` (`Died`).

### Error Handling and Logging
- DEBUG `economic_cascades_disruptions_scanned` with
  `events=<n> kinds=<n> rows=<n>`.
- INFO `economic_cascades_disruptions_complete`.
- WARN `economic_cascades_events_truncated`,
  `economic_cascades_disruptions_truncated`,
  `economic_cascades_tool_evidence_unavailable`.
- ERROR `economic_cascades_invalid_event_order` with a code only.
- Never log subject tokens, magnitudes, or event tokens.

### Tests
- `tests/unit/test_economic_cascades_events.py`: one fixture per harvestable
  class built from the real event dataclasses; repeated closure not duplicated;
  depletion crossing only once; body-token population subject; truncation
  prefix stability; out-of-order rejection.
- `tests/unit/test_economic_cascades_events_properties.py`: Hypothesis over
  shuffled tick order (sorted input) proving output determinism and that no row
  exceeds the cap.

### Acceptance Criteria
- All five classes are declared; the four event-backed classes are harvested
  here and `tool_shortage` is left to Task 5's stage proxy.
- Truncation never drops the newest window.
- No event class outside the four mappings contributes a disruption row.

### Verification
- `uv run pytest tests/unit/test_economic_cascades_events.py tests/unit/test_economic_cascades_events_properties.py -q`
- Expected result: pass.

## Task 4: Build the dependency structure and stage rows

### Intent
Propagation must follow real dependencies. This task derives the recipe-stage
graph and observed stage counts from detached recipe specs, and attaches only
the topology facts that are observable (infrastructure presence, transport
locations, labor participation). This analysis module reads no `WorldState` and
imports no world catalog; the experiments bridge supplies detached
`SupplyRecipeSpec` values.

### Implementation Steps
1. Create `src/analysis/economic_cascades_dependencies.py`:
   - `EconomicCascadeDependencyResult` dataclass: `stage_rows`, `edges`,
     `labor_joins`, `notices`, `coverage`, `stage_count`, `edge_count`,
     `max_depth`.
   - `build_economic_cascade_dependencies(*, stages, recipes, infrastructure=(),
     routes=(), policy=None)` where `stages` are `SupplyStageObservation`
     values from `supply_evidence_from_events`, `recipes` are detached
     `SupplyRecipeSpec` values, `infrastructure` is a sequence of
     `(location_token, kind, operational)` tuples supplied by the completed-run
     bridge, and `routes` is a sequence of
     `(origin_token, destination_token, status)` tuples.
   - Stage rows: group observations by `(window_index, recipe_id,
     location_token)`; `attempt_count` counts attempts, `completion_count`
     counts completions, `demand_count` = attempts plus downstream attempts
     whose recipe inputs name this stage output (computed from the recipe
     graph); `tool_dependent` is true when the recipe declares `tool_role`;
     `has_infrastructure` is true when an operational asset at the location
     maps to the stage action.
   - Edges (five closed kinds) carry a generic `upstream_token` because a
     topology fact is not a recipe:
     - `resource_input` / `item_input`: upstream is the producer recipe id;
       downstream is the consumer recipe id; depth 1.
     - `tool_dependency`: upstream is the tool-output recipe id; downstream is a
       recipe with `tool_role`; depth 1.
     - `infrastructure_dependency`: upstream is
       `asset:<kind>@<location_token>`; downstream is a stage at that location,
       using the locked map
       `INFRASTRUCTURE_STAGE_ACTIONS = {"irrigation": {"harvest"},
       "storage": {"store"}, "trade_post": {"store", "craft"},
       "road": {"harvest", "craft", "build"}, "bridge": {"harvest", "craft"}}`.
     - `transport_dependency`: upstream is
       `route:<origin_token>-><destination_token>`; downstream is a stage at
       either endpoint, when the route status is not `open`.
   - Labor participation is not an edge. Return `labor_joins` as sorted
     `(actor_token, recipe_ids)` tuples for chain linking; it is never emitted
     as a row and never serialized.
   - Compute `depth` by breadth-first traversal from producer stages; cap at
     `policy.max_chain_depth`; deeper edges are dropped with
     `dependency_depth_truncated`.
   - Reject cycles with `_invalid_recipe_spec`; reject a consumer with no
     producer when `require_complete_graph=True` only for the supply-chain
     catalog, not the legacy catalog.
2. Cap edges and stage rows independently with deterministic sorted prefixes;
   append `stages_truncated` / `edges_truncated` and set `partial`.
3. Keep all rows token-only; `location_token` is allowed, owner tokens are not
   persisted.

### Required Interfaces and Contracts
- `SupplyRecipeSpec` is the only recipe contract; never import
  `ProductionRecipe` or the world catalog.
- Dependency kinds are the five closed values; unknown input names create no
  edge.
- `upstream_token` is either a recipe id, `asset:<kind>@<location>`, or
  `route:<origin>-><destination>`; no free-form text is accepted.
- `depth` is 1-based; `max_depth` is the maximum emitted depth.
- Labor participation is a join key, not an edge row.

### Requirement Evidence
- Original Request "Allow effects to propagate through real dependencies".
- `src/analysis/supply_chain_events.py:395-403` and
  `src/analysis/supply_chain_contract.py:85-96`.
- `src/world/supply_chain.py:85-127,205-218` (stage facts and skill domains).

### Error Handling and Logging
- DEBUG `economic_cascades_graph_built stages=<n> edges=<n> depth=<n>`.
- INFO `economic_cascades_graph_complete`.
- WARN `economic_cascades_stages_truncated`,
  `economic_cascades_edges_truncated`,
  `economic_cascades_dependency_depth_truncated`,
  `economic_cascades_recipe_cycle`.
- ERROR `economic_cascades_invalid_recipe_spec` with a code only.
- Never log recipe contents, locations, or tokens.

### Tests
- `tests/unit/test_economic_cascades_dependencies.py`: six-recipe chain fixture
  (harvest → mill → bake and harvest → craft head → assemble tool); depth bound
  drops a 7-deep chain; cycle rejection; infrastructure map; route dependency
  only when not `open`; stage demand from downstream attempts; upstream token
  forms (`recipe`, `asset:<kind>@<location>`, `route:<a>-><b>`); labor joins
  sorted and never emitted as edges; cap prefix stability; legacy catalog
  accepted without a complete graph.

### Acceptance Criteria
- Edges reproduce the real recipe inputs, not correlation.
- A chain that cannot be reached within six steps emits no edge.
- Stage rows never contain an owner token.

### Verification
- `uv run pytest tests/unit/test_economic_cascades_dependencies.py -q`
- Expected result: pass.

## Phase Risks and Mitigations
- Risk: appending a context perturbs shared pins before Task 18.
  Mitigation: this phase verifies registry validators directly; the pin sweep is
  a single later task with an explicit checklist.
- Risk: the tool-shortage proxy is mistaken for an objective stock measure.
  Mitigation: closed `unavailable` state, documented denominator, and a
  leakage/contract test forbidding `stock` and `inventory` keys in rows.
- Risk: dependency edges become implicit causal claims.
  Mitigation: three-layer separation, `linked|unlinked|unresolved` states, and
  no `caused_by` key anywhere.

## Phase Completion Checklist
- Registry and write-pair validators pass at 17 contexts.
- Contract, policy, rows, event harvest, and dependency graph tests pass.
- No `WorldState`, world-catalog import, or `ProductionRecipe` import exists in
  the new analysis modules; the experiments bridge performs the only catalog
  read and maps it to `SupplyRecipeSpec`.
- `index.md` Tasks 1-4 checkboxes are updated after verification.
