# Phase 2: Identity and Cross-Society Harvest

Plan: [index.md](index.md)
Tasks: 4-6
Depends on: Phase 1 / Tasks 1-3

## Objective

Turn detected corridors into stable network identities with forward-only
lineage, derive cross-society rows from existing `msoc-` candidates, and expose
one bounded `TradeNetworksAnalysis` object with separated objective and
analytical layers.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/analysis/migration_displacement_identity.py` | `link_migration_lineage` 159-252; `_overlap` 124-129 | Forward-only lineage and overlap-threshold pattern. |
| `src/analysis/inter_society_relations_detection.py` | `InterSocietyMacroCandidate` 47-74; `detect_inter_society_pairs` 96-150 | Existing `msoc-` candidate contract and overlap handling. |
| `src/analysis/inter_society_relations_layers.py` | `InterSocietyLayer` 28-45; `assert_layer_separation` 159-190 | Separated-layer and leak-guard pattern. |
| `src/analysis/migration_displacement_layers.py` | `MigrationLayer` 54-62; `_FORBIDDEN` 67-105; `assert_migration_layer_separation` 156-205 | Four-layer separation pattern. |
| `src/analysis/inter_society_relations_contract.py` | `INTER_SOCIETY_RELATIONS_POLICY_VERSION` 46-53 | Versioned analysis policy style. |
| `src/analysis/trade_networks_contract.py` | created in Task 1 | Shared ids, classes, layers, errors. |
| `src/analysis/trade_networks_rows.py` | created in Task 3 | Rows consumed by lineage and harvest. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/analysis/trade_networks_identity.py` | create | Corridor/network content addresses, network lineage, forward-only invariants. |
| `src/analysis/trade_networks_cross_society.py` | create | Join transfer participants to contemporaneous `msoc-` candidates; bounded rows. |
| `src/analysis/trade_networks_layers.py` | create | Four separated layer views and hard leakage guard. |
| `src/analysis/trade_networks_analysis.py` | create | Bounded `TradeNetworksAnalysis` harvest and public entry point. |
| `src/analysis/__init__.py` | modify | Export public trade analysis names; no private world or engine imports. |
| `tests/unit/test_trade_networks_identity.py` | create | Determinism, lineage statuses, forward-only tests. |
| `tests/unit/test_trade_networks_cross_society.py` | create | Candidate join, overlap, missing coverage tests. |
| `tests/unit/test_trade_networks_layers.py` | create | Layer leak tests. |
| `tests/unit/test_trade_networks_analysis.py` | create | Harvest composition, caps, determinism, coverage tests. |

## Task 4: Mint deterministic trade identities and forward-only lineage

### Intent

Networks must be able to emerge, disappear, split, merge, and reroute without
rewriting previous identities. Content-addressed IDs make the same window
reproducible across replay and processes.

### Implementation Steps

1. Create `src/analysis/trade_networks_identity.py` with:
   - `mint_corridor_token(from_location: str, to_location: str) -> str` over
     the exact ordered pair using `analysis_trade_candidate_id("corridor",
     ...)`. The token is stable across windows and preserves direction; reverse
     trajectories mint distinct corridor tokens. `canonical_trade_pair` is used
     only for cross-society pairs.
   - `mint_network_token(corridor_tokens: Sequence[str]) -> str` over the sorted,
     de-duplicated corridor tokens using
     `analysis_trade_candidate_id("network", "\x1e".join(tokens))`.
   - `mint_cross_society_pair_token(society_a: str, society_b: str) -> str`
     using `canonical_trade_pair` and the `pair` kind.
2. Implement `group_networks_by_window(networks, *, first_window: int = 0,
   last_window: int | None = None) -> tuple[tuple[int,
   tuple[TradeNetworkRow, ...]], ...]` sorted by window index. When a range is
   supplied, emit an empty tuple for every policy window in the range; this is
   how empty gaps remain visible to lineage.
3. Implement `link_trade_network_lineage(previous: Sequence[TradeNetworkRow],
   current: Sequence[TradeNetworkRow], policy) -> tuple[TradeLineageRow, ...]`:
   - Reject non-`TradeNetworkRow` entries, mixed window indexes, and backwards
     windows with `trade_networks_invalid_lineage`.
   - For each previous/current pair, compute corridor-set overlap in integer
     milli: `len(intersection) * 1000 // min(len(previous_set), len(current_set))`.
     If both sets are empty, overlap is 1000 when tokens match, else 0.
   - A link exists when overlap >= `policy.lineage_overlap_milli`.
   - For each link: `split` when the previous network has at least two
     successors; `merge` when the current network has at least two
     predecessors; otherwise `continued` when corridor sets are equal and
     `transformed` when they differ. `rerouted = relation == "transformed"`.
   - For every previous network without a successor emit
     `relation="dissolved"`, `previous_token=network_token`,
     `network_token=NONE_TOKEN`; for every current network without a
     predecessor emit `relation="emerged"`, `previous_token=NONE_TOKEN`.
   - Set `sustained=True` only for `continued`/`transformed` links; all other
     relations are false. A sustained link spans exactly two adjacent policy
     windows, which is the locked definition of a sustained network.
   - `first_tick`/`last_tick` are derived from window bounds; never negative.
   - Sort by `(first_tick, network_token, previous_token)` and log only counts.
4. Ensure lineage is forward-only: previous rows are inputs only and are never
   mutated or replaced. `TradeLineageRow.relation` is closed to the six values
   and carries `sustained: bool`. The caller must feed every consecutive policy
   window, including empty windows, so disappearance and reappearance are not
   collapsed into `continued`.
5. Do not mint societies, offices, organizations, or locations. Existing
   `msoc-`/`org-`/world location tokens are read-only strings.

### Required Interfaces and Contracts

- IDs match `^trd-(cor|net|pair)-[0-9a-f]{16}$`.
- `TradeNetworkRow` ids in one window are unique.
- Lineage edges never point backwards in window order.
- No shortest path or route choice participates in identity.

### Error Handling and Logging

- Invalid or mixed windows raise `TradeNetworksError` with safe codes.
- `DEBUG trade_networks_lineage previous=%s current=%s edges=%s` only.

### Tests

- `tests/unit/test_trade_networks_identity.py`:
  - `test_corridor_and_network_ids_are_stable`
  - `test_identical_corridor_sets_are_continued`
  - `test_changed_corridor_set_is_transformed_and_rerouted`
  - `test_two_successors_are_split`
  - `test_two_predecessors_are_merge`
  - `test_absent_successor_is_dissolved`
  - `test_absent_predecessor_is_emerged`
  - `test_empty_window_forces_dissolved_then_emerged`
  - `test_continued_and_transformed_are_sustained`
  - `test_reverse_corridors_mint_distinct_tokens`
  - Hypothesis `test_lineage_is_forward_only`

### Acceptance Criteria

- Same corridors always mint the same network token.
- All six lineage relations are reachable and deterministic.
- Rerouting is represented only by `transformed` with `rerouted=true`.
- Empty gaps produce `dissolved` then `emerged`, never a silent `continued`.
- Sustained is true only for continued/transformed transitions.

### Verification

- `uv run pytest tests/unit/test_trade_networks_identity.py -q`
- Expected result: all tests pass; no route planner import.

## Task 5: Derive cross-society trade flows from msoc candidates

### Intent

The request asks for cross-society flows. Existing `msoc-` candidates are the
only legal society identity; V4-18 reads them and never mints a society.

### Implementation Steps

1. Create `src/analysis/trade_networks_cross_society.py` importing
   `InterSocietyMacroCandidate` from
   `analysis.inter_society_relations_detection` (same package, public class).
2. Implement `detect_cross_society_trade(
   transfers: Sequence[TradeTransferRow],
   candidates: Sequence[InterSocietyMacroCandidate],
   policy: TradeNetworksAnalysisPolicy,
) -> tuple[CrossSocietyTradeRow, ...]`:
   - Group candidates by `window_index_for_tick(candidate.window_tick, policy)`.
     Reject candidates outside the policy window range with
     `trade_networks_invalid_candidate`.
   - Build `member -> frozenset[society_id]` for each trade window. A member may
     belong to multiple overlapping candidates; that is legal.
   - For each transfer, resolve `actor_token` and `counterparty_token` memberships.
     For every ordered pair of distinct societies `(A, B)` with actor/source in
     A and counterparty/destination in B, add one transfer to the canonical
     unordered pair `(A, B)`. For `direction="take"`, source and destination are
     reversed for the directional counters.
   - Aggregate `flow_counts`, `society_a_to_b_count`, `society_b_to_a_count`,
     `transfer_count`, and `overlap_member_count = len(members_a & members_b)`
     per pair/window.
   - Compute `society_a_location_id`/`society_b_location_id` as the most
     frequent `location_token` among transfers involving that society in the
     window; break ties by lexicographic location token and use `NONE_TOKEN`
     when no location exists. These are analytical anchors for read-only
     clients, not society territory.
   - Pair token is `mint_cross_society_pair_token(A, B)`.
   - Sort by `(window_index, pair_token)`.
   - Apply `max_cross_society_pairs` by deterministic prefix; truncation sets
     coverage `partial` and appends `trade_networks_cross_society_truncated`.
3. Coverage is `missing` when no candidates exist, `partial` when any transfer
   cannot be mapped or truncation occurred, otherwise `complete`.
4. If a participant belongs to multiple candidates, count each legal pair and
   append notice `trade_networks_overlap_membership` at most once per window.
   Never partition persons and never choose one society.
5. Log `DEBUG trade_networks_cross_society pairs=%s mapped=%s coverage=%s`.

### Required Interfaces and Contracts

- Input candidates are existing `msoc-` values; no new society model.
- Cross-society rows are analytical comparison rows, never objective state.
- No objective organization, polity, or civilization identity is minted.
- Overlap is legal; the same transfer may appear in multiple pair rows.

### Error Handling and Logging

- Reject non-`msoc-` ids, empty member sets, and out-of-range window ticks with
  `TradeNetworksError` safe codes.
- `WARN trade_networks_cross_society_truncated retained=%s cap=%s` only.

### Tests

- `tests/unit/test_trade_networks_cross_society.py`:
  - `test_no_candidates_yields_missing_coverage`
  - `test_two_societies_get_one_canonical_pair`
  - `test_direction_counts_follow_exchange_bundle_side`
  - `test_overlapping_candidates_are_legal_and_not_partitioned`
  - `test_unmapped_participant_marks_partial`
  - `test_dominant_location_anchor_is_deterministic`
  - `test_missing_anchor_uses_none_token`
  - `test_overlap_member_count_is_retained`
  - `test_pair_cap_truncates_deterministically`

### Acceptance Criteria

- Cross-society rows exist only when `msoc-` candidates are supplied.
- No new society or organization identity is created.
- Pair direction, dominant location anchors, and overlap are deterministic.
- Unresolved anchors use `NONE_TOKEN`; no location is guessed.

### Verification

- `uv run pytest tests/unit/test_trade_networks_cross_society.py -q`
- Expected result: all tests pass; candidate ids unchanged.

## Task 6: Compose the bounded `TradeNetworksAnalysis` harvest

### Intent

Provide one stable object for metrics, snapshots, and experiments, with the
objective evidence separated from analytical corridors, networks, and
cross-society comparisons.

### Implementation Steps

1. Create `src/analysis/trade_networks_layers.py`:
   - `TradeLayerView` containing `objective_transfers`, `analytical_corridors`,
     `analytical_networks`, `comparison_view`.
   - `project_trade_layers(transfers, corridors, networks, cross_society)`.
   - `assert_trade_layer_separation(view)`:
     - objective layer must not contain `trd-cor-`/`trd-net-`/`trd-pair-`;
     - corridor layer must not contain `trd-net-`/`trd-pair-`;
     - network layer must not contain raw event tokens or `trd-pair-`;
     - comparison layer must not contain raw item/artifact tokens.
   - Raise `TradeNetworksError("trade_networks_layer_leak")` on violation.
2. Create `src/analysis/trade_networks_analysis.py`:
   - `@dataclass(frozen=True, slots=True) class TradeNetworksAnalysis` with
     `window_tick`, `transfers`, `supplies`, `corridors`, `flows`, `locations`,
     `dependence`, `networks`, `lineage`, `cross_society`, `layers`,
     `evidence_coverage`, `cross_society_coverage`, `lineage_coverage`,
     `coverage`, `notices`, `transfer_count`, `corridor_count`,
     `network_count`, `cross_society_pair_count`, `trade_post_location_count`.
   - `harvest_trade_networks_analysis(*, events=(), macro_candidates=(),
     policy=None, window_tick=None, recipe_item_kinds=None,
     item_kind_by_id=None, trade_post_locations=()) -> TradeNetworksAnalysis`:
     - resolve policy default;
     - call Task 2 evidence extraction with the detached kind mappings;
     - call Task 3 detection for corridors/flows/locations/dependence/networks
       with `trade_post_locations`;
     - call Task 4 lineage over **every consecutive policy window** from the
       first to the last observed window, passing empty tuples for empty
       windows;
     - call Task 5 cross-society;
     - apply `policy.max_lineage_edges` by deterministic prefix; truncation sets
       `lineage_coverage="partial"` and appends
       `trade_networks_lineage_truncated`;
     - project layers and assert separation;
     - resolve `window_tick` from the argument, else the maximum event tick, else
       0; validate exact non-negative int;
     - set `evidence_coverage` from transfer/supply evidence,
       `cross_society_coverage` from Task 5, and `lineage_coverage` from
       network/lineage availability (`missing` when no network rows exist,
       `partial` when lineage truncation occurs, otherwise `complete` even with
       a single-window zero-edge lineage); set aggregate `coverage` as `missing` only
       when all three are missing, `partial` when any component is missing or
       partial or any notice exists, and `complete` only when all three are
       complete and there are no notices;
     - de-duplicate and sort notices;
     - log `INFO trade_networks_harvest transfers=%s corridors=%s networks=%s
       pairs=%s evidence_coverage=%s cross_society_coverage=%s
       lineage_coverage=%s` with counts only.
   - Add `empty_trade_networks_analysis(window_tick=0)`.
3. Add public exports in `src/analysis/__init__.py`:
   `TradeNetworksAnalysis`, `harvest_trade_networks_analysis`,
   `default_trade_networks_analysis_policy`, `TradeFlowClass`,
   `TradeCoverage`, and the row types needed by simulation/tests.
4. Ensure `analysis.trade_networks_analysis` imports no
   `simulation.engine`, `world._*`, `experiments`, `api`, `persistence`, or
   `observer` module.

### Required Interfaces and Contracts

- `TradeNetworksAnalysis` is frozen and contains tuples only.
- `evidence_coverage`, `cross_society_coverage`, `lineage_coverage`, and the
  aggregate `coverage` are closed values; callers must not collapse them.
- The object is serializable by the later snapshot mapper without recomputation.
- No metric, snapshot, or API code is imported here.

### Error Handling and Logging

- Invalid analysis dimensions raise `TradeNetworksError` with stable codes.
- Leakage raises before any object is returned.
- `INFO` at harvest start/end; `WARN` only for truncation/partial evidence.

### Tests

- `tests/unit/test_trade_networks_layers.py`:
  - `test_layers_keep_objective_and_analytical_rows_separate`
  - `test_network_token_leak_in_objective_layer_is_rejected`
  - `test_pair_token_leak_in_corridor_layer_is_rejected`
- `tests/unit/test_trade_networks_analysis.py`:
  - `test_empty_harvest_is_missing_and_bounded`
  - `test_harvest_combines_evidence_detection_and_lineage`
  - `test_missing_macro_candidates_leave_evidence_coverage_complete`
  - `test_harvest_retains_per_family_coverage`
  - `test_harvest_feeds_empty_windows_to_lineage`
  - `test_harvest_is_deterministic_across_event_order`
  - `test_harvest_notices_are_sorted_and_deduplicated`
  - Hypothesis `test_harvest_never_exceeds_caps`

### Acceptance Criteria

- One call produces a complete, bounded analysis object from events alone.
- Objective and analytical layers never mix identifier families.
- Missing cross-society candidates do not invalidate other families; each
  family reads its own coverage.

### Verification

- `uv run pytest tests/unit/test_trade_networks_layers.py tests/unit/test_trade_networks_analysis.py -q`
- Expected result: all tests pass; no engine import in analysis modules.

## Phase Risks and Mitigations

- Risk: `msoc-` candidate windows and 32-tick trade windows may not align.
  Mitigation: map candidates with `window_index_for_tick`; absent alignment
  yields `missing`, never a guessed society.
- Risk: overlapping society candidates could double-count a transfer.
  Mitigation: document legal overlap explicitly; counts are analytical pair
  views, not a partition or objective total.
- Risk: lineage over sparse windows could hide disappearance.
  Mitigation: every consecutive policy window is compared, with empty tuples for
  gaps; no interpolation and no silent continuation.

## Phase Completion Checklist

- Every Task 4-6 acceptance criterion is satisfied.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
