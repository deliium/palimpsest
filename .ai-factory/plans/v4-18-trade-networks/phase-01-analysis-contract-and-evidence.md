# Phase 1: Analysis Contract and Evidence

Plan: [index.md](index.md)
Tasks: 1-3
Depends on: none

## Objective

Lock the `trade-networks.v1` analytical contract and reconstruct bounded,
deterministic transfer and local-supply evidence from committed world events.
The phase produces no world state, command, event, runner schema, or database
change.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/world/values.py` | `ItemKind` 81-88 | Closed physical item taxonomy. |
| `src/world/resource_profile.py` | `physical_profile` 16-48 | Portability/fate tokens; used for the media rule. |
| `src/world/artifacts.py` | `ArtifactKind` 78-87, portable/fixed sets 89-124 | Records are artifacts, not items. |
| `src/world/events.py` | `OccurrenceContext` 344-390; `JourneyArrived` 433-462; `Given` 638-655; `ResourceHarvested` 1032-1073; `ItemCrafted` 1105-1133; `ArtifactCreated` 1401-1435; `ArtifactMoved` 1474-1507; `ArtifactCopied` 1549-1593; `ExchangeCompleted` 2514-2564; `build_occurrence_context` 4327-4520 | Exact event fields and location metadata. |
| `src/world/actions.py` | `Give` 92-102; `NegotiateExchange` 882-908 | Existing individual exchange mechanics; no new command. |
| `src/world/_operations.py` | 1787-1800 | Generic occurrence origin is the actor's pre-command location. |
| `src/analysis/exchange_functions.py` | `FORBIDDEN_KEYS` 10-43; `classify_exchange_functions` 85-120 | Existing forbidden currency vocabulary and event-scan style. |
| `src/analysis/migration_displacement_policy.py` | policy fields 33-70 | Bounded-window policy pattern. |
| `src/analysis/inter_society_relations_contract.py` | policy constants 46-53; layers 99-104 | Detached-analysis contract and layer pattern. |
| `src/analysis/civilization_overlays.py` | `compose_trade_rows` 408-469 | Existing minimal trade row; must not be duplicated as a new objective registry. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/analysis/trade_networks_contract.py` | create | Policy version, flow/layer/coverage enums, candidate prefixes, forbidden keys, deterministic id helper, error type. |
| `src/analysis/trade_networks_policy.py` | create | Validated policy dataclass, constants, window helpers, default policy. |
| `src/analysis/trade_networks_events.py` | create | Committed-event scan into `TradeTransferRow` and `TradeLocalSupplyRow` with origins, previous locations, media classification, coverage, and bounded notices. |
| `src/analysis/trade_networks_rows.py` | create | Normalized corridor/location/dependence/network/lineage/cross-society rows and harvest container. |
| `src/analysis/trade_networks_detection.py` | create | Corridor, location, dependence, and network detection; deterministic sorting and caps. |
| `src/analysis/__init__.py` | modify | Export only the public analysis API required by metrics, experiments, and tests; no private-world imports. |
| `tests/unit/test_trade_networks_contract.py` | create | Policy, enum, forbidden-key, id, and window tests. |
| `tests/unit/test_trade_networks_policy.py` | create | Policy values, validation, and window helper tests. |
| `tests/unit/test_trade_networks_events.py` | create | Event extraction, media rule, origin/previous-location, coverage, and cap tests. |
| `tests/unit/test_trade_networks_detection.py` | create | Corridor, dependence, major-location, network, and same-location tests. |

## Task 1: Lock `trade-networks.v1` policy and flow taxonomy

### Intent

Every later module must share one closed vocabulary and one set of bounds so the
analytics cannot drift into a price, money, planner, or score model.

### Implementation Steps

1. Create `src/analysis/trade_networks_contract.py` with:
   - `TRADE_NETWORKS_ANALYSIS_POLICY_VERSION = "trade-networks.v1"`.
   - `TRADE_CORRIDOR_PREFIX = "trd-cor-"`, `TRADE_NETWORK_PREFIX = "trd-net-"`,
     `TRADE_PAIR_PREFIX = "trd-pair-"`, `NONE_TOKEN = "none"`.
   - `TradeFlowClass(StrEnum)` with exactly `FOOD = "food"`,
     `MATERIALS = "materials"`, `TOOLS = "tools"`, `RECORDS = "records"`,
     `DURABLE_EXCHANGE_MEDIA = "durable_exchange_media"`, `OTHER = "other"`.
   - `TradeCoverage(StrEnum)` with `COMPLETE = "complete"`,
     `PARTIAL = "partial"`, `MISSING = "missing"`.
   - `TradeLayer(StrEnum)` with `OBJECTIVE_TRANSFER = "objective_transfer"`,
     `ANALYTICAL_CORRIDOR = "analytical_corridor"`,
     `ANALYTICAL_NETWORK = "analytical_network"`,
     `COMPARISON_VIEW = "comparison_view"`.
   - `TradeNetworksError(ValueError)` with a stable `code` attribute.
   - `TRADE_FORBIDDEN_KEYS` as a `frozenset` containing `price`, `rate`,
     `money`, `currency`, `numeraire`, `is_money`, `medium_of_exchange`,
     `store_of_value`, `unit_of_account`, `central_planner`, `route_plan`,
     `allocation`, `quota`, `score`, `ranking`.
   - `TRADE_LAYER_FORBIDDEN_PREFIXES` mapping: objective transfer forbids
     `trd-cor-` and `trd-net-`; analytical corridor forbids `trd-net-`;
     analytical network forbids `trd-pair-`; comparison view forbids raw
     objective event tokens.
   - `analysis_trade_candidate_id(kind: str, material: str) -> str`:
     lowercase kind, SHA-256 over `kind + "\x1f" + material`, return
     `<prefix><16 hex>`, where the prefix is selected by kind
     (`corridor` -> `trd-cor-`, `network` -> `trd-net-`, else `trd-pair-`).
   - `canonical_trade_pair(left: str, right: str) -> tuple[str, str]` sorted by
     value, rejecting equal or empty tokens.
2. Create `src/analysis/trade_networks_policy.py` with
   `@dataclass(frozen=True, slots=True) class TradeNetworksAnalysisPolicy`:
   `window_ticks=32`, `max_windows=512`, `max_transfer_rows=200_000`,
   `max_corridors=4_096`, `max_networks=1_024`, `max_locations=4_096`,
   `max_cross_society_pairs=2_048`, `max_lineage_edges=16_384`,
   `media_min_transfers=2`, `media_min_distinct_parties=2`,
   `major_min_corridors=2`, `major_min_transfers=3`,
   `lineage_overlap_milli=500`, `high_dependence_milli=500`.
   Validate exact `int` (not `bool`) ranges: window 4-256, windows 1-2048,
   transfer rows 1-1,000,000, corridors 1-16,384, networks 1-4,096, locations
   1-16,384, pairs 1-8,192, lineage edges 1-65,536, media transfers 2-16, media
   parties 2-64, major corridors 1-16, major transfers 1-1,024, overlap
   1-1,000, dependence 1-1,000. Raise `ValueError` with a stable field name on
   violation.
3. Add `default_trade_networks_analysis_policy()` returning the frozen default.
4. Add `window_index_for_tick(tick: int) -> int` and
   `window_bounds(window_index: int, policy) -> tuple[int, int]`. Reject
   `bool`, negative ticks, and windows beyond `max_windows` with
   `TradeNetworksError("trade_networks_window_out_of_range")`.
5. Add `flow_class_for_item(kind: ItemKind) -> TradeFlowClass` and
   `is_media_candidate(kind: ItemKind, transfer_count: int,
   distinct_parties: int, consumed: bool) -> bool`. `FOOD`/`WATER` map to
   `FOOD`; `MATERIAL` to `MATERIALS`; `TOOL` to `TOOLS`; `GENERIC` maps to
   `OTHER` unless `is_media_candidate` (transfer count >=
   `media_min_transfers`, distinct counterparties >=
   `media_min_distinct_parties`, not consumed); `MEDICAL` and every unknown
   value map to `OTHER`. Import `ItemKind` from public `world.values` only.
6. Log `INFO` once at module import? No. Log nothing at import. Policy
   construction logs `DEBUG trade_networks_policy_resolved window_ticks=%s
   max_corridors=%s` with counts only.

### Required Interfaces and Contracts

- Pure analysis module; no `WorldState`, `WorldEngine`, `ActionSubmission`,
  `experiments`, `api`, `persistence`, `observer`, or cognition imports.
- `TradeFlowClass` is closed; unknown persisted values fail closed.
- No enum value or field name may contain `price`, `money`, `currency`,
  `planner`, `quota`, `allocation`, `score`, or `ranking`.
- `analysis_trade_candidate_id` is stable for the same input and independent of
  process, time, event order, or Python `hash()`.

### Error Handling and Logging

- Invalid policy dimensions raise `ValueError` with the field name.
- Candidate-id kind or material validation raises `TradeNetworksError` with
  `trade_networks_invalid_identity`.
- Debug logs contain only window counts and cap values; never item, person, or
  event payloads.

### Tests

- `tests/unit/test_trade_networks_contract.py`:
  - `test_contract_is_closed_and_forbidden_keys_present`
  - `test_candidate_ids_are_deterministic_and_prefixed`
  - `test_canonical_pair_rejects_equal_and_empty`
  - `test_window_bounds_and_out_of_range`
  - `test_item_kind_and_media_classification`
  - `test_media_requires_distinct_parties`
  - Hypothesis `test_candidate_id_is_stable_for_arbitrary_safe_material`
- `tests/unit/test_trade_networks_policy.py`:
  - `test_default_policy_values`
  - `test_policy_rejects_bool_and_out_of_range`
  - `test_window_helpers_match_locked_32_tick_window`

### Acceptance Criteria

- The contract exposes exactly six flow classes, three coverage values, and four
  layers.
- Forbidden vocabulary and layer prefixes are machine-readable.
- Candidate IDs are content-addressed and deterministic.

### Verification

- `uv run pytest tests/unit/test_trade_networks_contract.py tests/unit/test_trade_networks_policy.py -q`
- Expected result: all tests pass; no import of private world or outer layers.

## Task 2: Extract objective transfer and local-supply evidence

### Intent

Turn committed events into a normalized evidence stream. This is the only place
that knows event shapes; later detection and metrics consume rows.

### Implementation Steps

1. Create `src/analysis/trade_networks_events.py` with frozen rows:
   - `TradeTransferRow`: `entity_kind` (`"item"` or `"artifact"`),
     `entity_token`, `flow_class`, `tick`, `event_token`, `location_token`,
     `previous_location_token`, `origin_location_token`, `actor_token`,
     `counterparty_token`, `direction` (`"give"`/`"take"`), `source_kind`
     (`"exchange"`, `"gift"`, `"artifact_move"`, `"artifact_copy"`),
     `consumed` bool.
   - `TradeLocalSupplyRow`: `flow_class`, `location_token`, `tick`,
     `entity_token`, `source_kind` (`"harvest"`, `"craft"`, `"artifact_create"`,
     `"artifact_copy"`, `"search"`).
   - `TradeEvidenceHarvest`: `transfers`, `supplies`, `coverage`, `notices`,
     `transfer_count`, `supply_count`.
2. Implement `trade_transfer_rows_from_events(events: Sequence[WorldEvent], *,
   policy: TradeNetworksAnalysisPolicy,
   recipe_item_kinds: Mapping[str, ItemKind] | None = None,
   item_kind_by_id: Mapping[str, ItemKind] | None = None) ->
   TradeEvidenceHarvest`:
   - Iterate in canonical `(tick, sequence)` order; reject duplicate event
     tokens with `trade_networks_duplicate_event`.
   - Build `item_kinds: dict[str, ItemKind]` from, in precedence order:
     explicit `item_kind_by_id`, `ExchangeCompleted` bundle kinds,
     `ItemCrafted.recipe_id` and `ResourceHarvested.recipe_id` resolved through
     `recipe_item_kinds`. Conflicting mappings for one item id are a safe
     `trade_networks_conflicting_item_kind` error. Missing recipe entries add
     `trade_networks_missing_recipe_kind` and leave the class unknown.
   - Maintain `item_origins: dict[str, str | None]`, `artifact_origins:
     dict[str, str | None]`, `entity_locations: dict[str, str]`,
     `transfer_counts: dict[str, int]`, `transfer_parties:
     dict[str, set[str]]`, and `consumed_items: set[str]`.
   - Index `ExchangeCompleted.give_item_ids`/`give_item_kinds` and
     `take_item_ids`/`take_item_kinds` positionally; detect length mismatch and
     raise `trade_networks_invalid_exchange`.
   - On `ResourceHarvested` success: record `created_item_id` origin from
     `event.occurrence.origin_location_id` and emit a `harvest` supply row.
   - On `ItemCrafted`: record `created_item_id` origin and emit `craft` supply.
   - On `Searched` success with `created_item_id`: record origin and emit
     `search` supply.
   - On `ArtifactCreated`: record artifact origin and emit `artifact_create`
     supply. On `ArtifactCopied`: record `child_artifact_id` origin and emit
     `artifact_copy` supply.
   - On `ArtifactMoved`: update artifact location from
     `resulting_location_id` when present, else use `event.occurrence.origin_location_id`;
     emit a `records` transfer only when previous and current locations differ
     and both are known.
   - On `ExchangeCompleted`: location is
     `event.occurrence.origin_location_id`. For each give item, emit an
     `exchange` transfer with `direction="give"`, actor and counterparty; for
     each take item, emit `direction="take"` with reversed actor/counterparty.
     Previous location is `entity_locations.get(item_id, origin)`; if neither
     exists, record `previous_location_token=NONE_TOKEN` and add notice
     `trade_networks_unresolved_item_origin`.
   - On `Given`: emit a `gift` transfer from actor to `recipient_id`; class from
     `item_kinds` or `OTHER` plus notice `trade_networks_unknown_item_kind`.
   - Track consumption on `Eaten`, `CraftStarted.consumed_item_ids`,
     `StructureBuilt.consumed_item_id`, `StructureRepaired.consumed_item_id`,
     and `ItemStored.consumed_item_id`.
   - After scanning, compute `transfer_counts` and `len(transfer_parties[item])`
     per item. Reclassify every `GENERIC` item with
     `transfer_count >= policy.media_min_transfers`, at least
     `policy.media_min_distinct_parties` distinct counterparties, and no
     observed consumption as `DURABLE_EXCHANGE_MEDIA`; all other generic items
     stay `OTHER`. Reclassification is retrospective over the completed run and
     must not change row order.
   - Sort transfers by `(tick, event_token, entity_token, direction)` and
     supplies by `(tick, entity_token, source_kind)`.
   - Apply `max_transfer_rows` by deterministic prefix. If truncated, set
     `coverage="partial"` and append `trade_networks_transfer_truncated`.
3. Coverage: `missing` when no transfers and no supplies; `partial` when any
   notice exists, any location/origin is unresolved, or truncation occurred;
   otherwise `complete`.
4. Unknown event detail types are ignored silently at `DEBUG`; no exception.
5. Never read `WorldState` or final inventories. Kinds missing from exchange
   evidence stay `OTHER`.

### Required Interfaces and Contracts

- Rows validate non-empty stable tokens, closed classes, exact non-negative
  ticks, and tuple immutability.
- `TradeTransferRow.previous_location_token` may be `NONE_TOKEN`; it is never
  guessed from a later location.
- `TradeLocalSupplyRow` never creates a corridor by itself.
- The function is pure: identical events + policy + detached kind mappings
  produce identical rows, notices, and coverage.
- `recipe_item_kinds` and `item_kind_by_id` are detached `Mapping[str, ItemKind]`
  inputs; no production catalog or world state is imported.
- No event payload bodies, person sets, or item names are logged.

### Error Handling and Logging

- Reject duplicate event tokens, malformed exchange bundles, mismatched kind
  lengths, and negative ticks with `TradeNetworksError` safe codes.
- Emit `WARN trade_networks_unknown_item_kind count=%s` and
  `WARN trade_networks_transfer_truncated retained=%s cap=%s`.
- Emit `DEBUG trade_networks_evidence transfers=%s supplies=%s coverage=%s`.

### Tests

- `tests/unit/test_trade_networks_events.py`:
  - `test_exchange_creates_two_sided_transfer_rows`
  - `test_given_uses_unknown_kind_fallback`
  - `test_gift_of_crafted_food_uses_recipe_kind`
  - `test_item_kind_by_id_overrides_recipe_fallback`
  - `test_item_trajectory_previous_location_is_consecutive`
  - `test_artifact_move_and_copy_are_record_flows`
  - `test_generic_media_requires_two_transfers_and_no_consumption`
  - `test_generic_media_requires_distinct_parties`
  - `test_consumed_generic_is_never_media`
  - `test_unresolved_origin_marks_partial`
  - `test_conflicting_item_kind_is_rejected`
  - `test_transfer_cap_truncates_deterministically`
  - `test_duplicate_event_rejected`
  - Hypothesis `test_rows_are_bounded_and_ordered`

### Acceptance Criteria

- Every supported event that moves or creates an exchangeable entity yields a
  row or an explicit coverage notice.
- Media classification is retrospective and never uses a currency label.
- Row order and truncation are deterministic.

### Verification

- `uv run pytest tests/unit/test_trade_networks_events.py -q`
- Expected result: all tests pass; no world-state imports.

## Task 3: Detect corridors, dependence, exchange locations, and networks

### Intent

Derive the four objective-to-analytical outputs requested by the user without a
routing algorithm or a global trade registry.

### Implementation Steps

1. Create `src/analysis/trade_networks_rows.py` with frozen rows:
   - `TradeCorridorRow`: `corridor_token`, `window_index`,
     `from_location_token`, `to_location_token`, `flow_counts`
     (`tuple[tuple[str, int], ...]` sorted by class), `transfer_count`,
     `coverage`.
   - `TradeFlowRow`: `window_index`, `flow_class`, `transfer_count`,
     `cross_location_count`, `imported_count`, `exported_count`, `local_count`,
     `coverage`. `imported_count` and `exported_count` are non-disjoint
     location-role counts for the same cross-location transfer;
     `cross_location_count` is the distinct transfer count.
   - `TradeLocationRow`: `location_token`, `window_index`, `inflow_count`,
     `outflow_count`, `local_count`, `corridor_degree`, `is_major`,
     `trade_post_present`, `flow_counts`, `coverage`.
   - `TradeDependenceRow`: `location_token`, `window_index`, `flow_class`,
     `imported_count`, `locally_originated_count`, `dependence_milli`,
     `high_dependence`, `coverage`.
   - `TradeNetworkRow`: `network_token`, `window_index`, `corridor_tokens`,
     `location_tokens`, `flow_counts`, `transfer_count`, `coverage`.
   - `TradeLineageRow`: `network_token`, `previous_token`, `relation`,
     `first_tick`, `last_tick`, `rerouted`, `sustained`.
   - `CrossSocietyTradeRow`: `pair_token`, `window_index`, `society_a`,
     `society_b`, `society_a_location_id`, `society_b_location_id`,
     `overlap_member_count`, `flow_counts`, `transfer_count`,
     `society_a_to_b_count`, `society_b_to_a_count`, `coverage`.
   - `TradeNetworksHarvestRows`: `transfers`, `supplies`, `corridors`, `flows`,
     `locations`, `dependence`, `networks`, `lineage`, `cross_society`,
     `coverage`, `notices`, and counts.
2. Implement `detect_corridors(transfers, policy)`:
   - Ignore transfers whose previous location is `NONE_TOKEN` or equal to the
     current location.
   - Use the ordered edge `(previous, current)`; mint `trd-cor-` from the exact
     pair. Aggregate class counts and transfer count per window. A reverse
     trajectory is a distinct corridor.
   - Sort by `(window_index, corridor_token)`.
3. Implement `detect_flows(transfers, policy)`:
   - For each window and class, `cross_location_count` = transfers whose
     previous location differs from current; `imported_count` = those transfers
     counted at the destination as a location-role; `exported_count` = the same
     transfers counted at the origin as a location-role; `local_count` =
     same-location transfers. Imported and exported are deliberately
     non-disjoint role counts, not a partition.
   - Emit one `TradeFlowRow` per observed class; no composite.
4. Implement `detect_locations(transfers, supplies, policy,
   trade_post_locations=())`:
   - Inflow/outflow/local counts per location; corridor degree from detected
     corridors; `is_major = degree >= policy.major_min_corridors and
     (inflow + outflow + local) >= policy.major_min_transfers`;
     `trade_post_present = location_token in trade_post_locations`.
   - Emit rows for every location with at least one transfer or supply, sorted
     by `(window_index, location_token)`.
5. Implement `detect_dependence(transfers, policy)`:
   - Imported = transfers whose previous location differs.
   - Locally originated = transfers where the entity origin equals the current
     location and previous location equals the current location.
   - Denominator = imported + locally originated. If zero, emit
     `dependence_milli=None` and `high_dependence=False` with coverage
     `partial`; otherwise `imported * 1000 // denominator` and
     `high_dependence = dependence_milli >= policy.high_dependence_milli`.
   - Emit per location/window/class, sorted deterministically. Never infer
     consumption, welfare, or scarcity.
6. Implement `detect_networks(corridors, policy)`:
   - Build an undirected graph over corridor endpoints per window; `(A, B)` and
     `(B, A)` are the same graph edge even though they are distinct corridor
     tokens.
   - Connected components become `TradeNetworkRow` rows; `trd-net-` id is minted
     from sorted corridor tokens; location set is sorted endpoints.
   - Sort by `(window_index, network_token)`. Apply `max_networks` by
     deterministic prefix with a `trade_networks_network_truncated` notice.
7. Apply `max_corridors` and `max_locations` similarly. Any truncation sets
   `coverage="partial"` and keeps the deterministic prefix.
8. Log `DEBUG trade_networks_detected corridors=%s networks=%s locations=%s
   coverage=%s`; no person or item tokens.

### Required Interfaces and Contracts

- No shortest path, graph search, route planning, quota, or allocation.
- Corridors are directed ordered edges; the network graph unions reverse edges
  into one undirected component. Flow rows retain non-disjoint import/export
  role counts and a distinct `cross_location_count`.
- Networks are connected components, never authoritative entities.
- Every row validates closed coverage and non-negative exact integers.

### Error Handling and Logging

- Invalid rows or policy raise `TradeNetworksError` with safe codes.
- Caps truncate deterministically, set `coverage="partial"`, and append one
  notice per capped row family.
- `WARN` only for truncation; `DEBUG` for counts.

### Tests

- `tests/unit/test_trade_networks_detection.py`:
  - `test_same_location_transfer_is_local_not_corridor`
  - `test_consecutive_locations_create_directed_corridor`
  - `test_reverse_corridors_share_one_network`
  - `test_flow_rows_count_import_export_roles_and_cross_location`
  - `test_dependence_ratio_uses_observed_denominator`
  - `test_major_location_thresholds_are_exact`
  - `test_operational_trade_post_marks_location`
  - `test_connected_corridors_form_one_network`
  - `test_corridor_and_network_caps_truncate_deterministically`
  - Hypothesis `test_corridors_and_networks_are_bounded`

### Acceptance Criteria

- Same-location exchanges never create corridors.
- A two-location item trajectory creates exactly one corridor and one network.
- A reverse trajectory is a distinct corridor but the same undirected network.
- Operational trade-post evidence marks a location without changing admission.
- Dependence, major-location, and network outputs are deterministic and bounded.

### Verification

- `uv run pytest tests/unit/test_trade_networks_detection.py -q`
- Expected result: all tests pass; no routing or score fields.

## Phase Risks and Mitigations

- Risk: item kind is absent on some gift events.
  Mitigation: use exchange-kind indexing plus `OTHER` fallback and a bounded
  `trade_networks_unknown_item_kind` notice; never guess from names.
- Risk: final inventories would make trajectory reconstruction easier but would
  violate event-only analysis.
  Mitigation: accept unresolved origins as `partial` coverage; never read
  `WorldState`.
- Risk: connected components can explode with many locations.
  Mitigation: explicit corridor/network/location caps and deterministic
  truncation.

## Phase Completion Checklist

- Every Task 1-3 acceptance criterion is satisfied.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
