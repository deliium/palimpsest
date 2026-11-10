# Phase 3: Metrics and Collection

Plan: [index.md](index.md)
Tasks: 7-9
Depends on: Phase 2 / Tasks 4-6

## Objective

Turn `TradeNetworksAnalysis` into six catalog metric families and wire the real
completed-run/experiment collector so trade metrics are populated from committed
events rather than synthetic fixtures.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/analysis/specifications.py` | `METRIC_FAMILY_COUNT = 192` 52-53; `MetricFamilyId` 75-269; `_BUILDERS` 9011-9205; `all_metric_specifications` 9207-9224 | Exact catalog append point. |
| `src/analysis/infrastructure_metrics.py` | `_document` 70-120; six travel calculators 383-575; `_reject_score_fields` 142 | Metric document and no-score pattern. |
| `src/analysis/metric_service.py` | input fields 300-380; existing infra/travel gate 2378-2410; `_safe` | Input and family dispatch pattern. |
| `src/analysis/exchange_functions_metrics.py` | `assemble_exchange_function_metrics` 29-73; forbidden-key rejection 75-110 | Existing exchange metric assembly. |
| `src/experiments/collectors.py` | `assemble_arm_metric_bundle` 187-275; event retrieval 286-290; migration injection 1039-1062 | Real collector event access and `replace` pattern. |
| `src/experiments/infrastructure_completed_run.py` | `build_completed_run_infrastructure_networks_analysis` 40; `compose_infrastructure_networks_snapshot` 89 | Completed-run analysis pattern. |
| `src/analysis/inter_society_relations_metrics.py` | four family calculators 121-290 | Metric naming and availability style. |
| `src/simulation/runner_models.py` | result fields 6363-6364 | Only existing infrastructure/travel finals; no trade field is added. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/analysis/trade_networks_metrics.py` | create | Six metric calculators and one assembly helper. |
| `src/analysis/specifications.py` | modify | Six `MetricFamilyId` members, keys, builders, count 198. |
| `src/analysis/metric_service.py` | modify | `trade_networks_analysis` input and six-family dispatch. |
| `src/experiments/trade_networks_completed_run.py` | create | Build analysis from a completed run's committed events and optional macro candidates. |
| `src/experiments/collectors.py` | modify | Inject the real analysis into `MetricComputationInputs`. |
| `src/experiments/__init__.py` | modify | Export the completed-run builder and public analysis helper. |
| `tests/unit/test_trade_networks_metrics.py` | create | Six calculators, availability, coverage, forbidden-key tests. |
| `tests/unit/test_trade_networks_catalog.py` | create | Count 198, first 192 unchanged, last six order/keys. |
| `tests/unit/test_trade_networks_collector.py` | create | Collector injection and completed-run builder tests. |

## Task 7: Add six trade-network metric calculators

### Intent

Give researchers six independent estimands matching the request. No family may
collapse into a composite trade score.

### Implementation Steps

1. Create `src/analysis/trade_networks_metrics.py` importing only
   `analysis.trade_networks_analysis`, `analysis.models`, `analysis.numerical`,
   `analysis.specifications`, and the trade contract.
2. Add a shared `_document(family, *, state, observed, expected, run_id,
   input_revision, values)` that follows `infrastructure_metrics._document`:
   - `state="unknown"` -> `MetricAvailability.UNKNOWN`, empty values;
   - `state="partial"` -> `MetricAvailability.PARTIAL`;
   - `state="present"` -> `MetricAvailability.PRESENT`;
   - `MetricCoverage(observed, expected, ratio)` when not unknown;
   - provenance `source_kind="trade_networks_analysis"`, source ids
     `(run_id, input_revision, TRADE_NETWORKS_ANALYSIS_POLICY_VERSION,
     "trade-networks")`, notes code `detached_trade_networks_analysis`.
3. Implement:
   - `compute_trade_corridor_structure(analysis, *, run_id, input_revision)`:
     keys `window_tick`, `corridor_count`, `active_location_count`,
     `major_location_count`, `max_corridor_degree`, `max_corridor_transfers`,
     `isolated_location_count`, `corridor_coverage_ratio_milli`.
   - `compute_trade_flow_composition`: keys `window_tick`, `transfer_count`,
     `cross_location_count`, `food_count`, `materials_count`, `tools_count`,
     `records_count`, `durable_exchange_media_count`, `other_count`,
     `imported_count`, `exported_count`, `local_count`, `unknown_class_count`.
     Imported/exported are documented as non-disjoint role counts.
   - `compute_trade_location_centrality`: keys `window_tick`, `location_count`,
     `major_location_count`, `trade_post_location_count`,
     `major_trade_post_location_count`, `max_inflow_count`, `max_outflow_count`,
     `max_local_count`, `max_corridor_degree`, `mean_corridor_degree_milli`,
     `major_share_milli`.
   - `compute_trade_dependence`: keys `window_tick`, `location_count`,
     `class_count`, `mean_dependence_milli`, `max_dependence_milli`,
     `high_dependence_count`, `unresolved_count`, `complete_coverage_count`,
     `partial_coverage_count`.
   - `compute_cross_society_trade_flows`: keys `window_tick`, `pair_count`,
     `society_count`, `transfer_count`, `food_count`, `materials_count`,
     `tools_count`, `records_count`, `durable_exchange_media_count`,
     `other_count`, `overlap_pair_count`, `anchor_resolved_pair_count`,
     `anchor_unresolved_pair_count`, `coverage`.
   - `compute_trade_network_lineage`: keys `window_tick`, `network_count`,
     `active_network_count`, `emerged_count`, `continued_count`,
     `transformed_count`, `split_count`, `merge_count`, `dissolved_count`,
     `rerouted_count`, `sustained_transition_count`, `sustained_network_count`,
     `coverage`.
4. `mean_*_milli` uses integer division over observed rows; return 0 when the
   denominator is zero. `high_dependence_count` counts rows whose
   `high_dependence` flag is true; the locked threshold is applied once in
   detection, not duplicated in the metric layer.
5. Reject any calculated key in `TRADE_FORBIDDEN_KEYS`; call a
   `_reject_score_fields(values)` guard before constructing a document.
6. Add `assemble_trade_network_metrics(analysis, *, run_id, input_revision)`
   returning the six documents in catalog order. Select coverage per family:
   corridor/flow/location/dependence use `analysis.evidence_coverage`;
   cross-society uses `analysis.cross_society_coverage`; lineage uses
   `analysis.lineage_coverage`. Only the selected family becomes `UNKNOWN` when
   its own coverage is `missing`.
7. Log `DEBUG trade_networks_metrics_emitted family=%s` with counts only.

### Required Interfaces and Contracts

- One document per family, never one document per row.
- Values are exact integers in `[0, ...]` or `None` where explicitly documented;
  no floats with platform-dependent formatting.
- No composite score, ranking, price, money, or planner key.
- `run_id` and `input_revision` use `require_stable_id`.

### Error Handling and Logging

- Non-`TradeNetworksAnalysis` input raises
  `TradeNetworksError("trade_networks_metrics_invalid_analysis")`.
- Forbidden key detection raises before emission.
- `WARN` only for a forbidden-key attempt; `DEBUG` for family emission.

### Tests

- `tests/unit/test_trade_networks_metrics.py`:
  - `test_corridor_structure_values`
  - `test_flow_composition_counts_all_six_classes`
  - `test_location_centrality_uses_major_threshold`
  - `test_dependence_mean_and_high_count`
  - `test_cross_society_counts_and_coverage`
  - `test_network_lineage_status_counts`
  - `test_missing_analysis_is_unknown_for_all_six`
  - `test_missing_macro_candidates_only_cross_society_is_unknown`
  - `test_missing_evidence_does_not_unknown_cross_society_when_candidates_exist`
  - `test_sustained_and_trade_post_keys`
  - `test_forbidden_score_key_is_rejected`
  - Hypothesis `test_metric_values_are_non_negative_exact_ints`

### Acceptance Criteria

- Six documents are emitted in catalog order for a present analysis.
- A missing analysis yields six `UNKNOWN` documents with empty values.
- No family exposes a composite or forbidden key.

### Verification

- `uv run pytest tests/unit/test_trade_networks_metrics.py -q`
- Expected result: all tests pass; no float score fields.

## Task 8: Append six trade-network families to 198

### Intent

Make the six estimands first-class catalog families while preserving every prior
id, order, version, and value key.

### Implementation Steps

1. In `src/analysis/specifications.py` add `MetricFamilyId` members:
   - `TRADE_CORRIDOR_STRUCTURE = "trade_corridor_structure"`
   - `TRADE_FLOW_COMPOSITION = "trade_flow_composition"`
   - `TRADE_LOCATION_CENTRALITY = "trade_location_centrality"`
   - `TRADE_DEPENDENCE = "trade_dependence"`
   - `CROSS_SOCIETY_TRADE_FLOWS = "cross_society_trade_flows"`
   - `TRADE_NETWORK_LINEAGE = "trade_network_lineage"`
2. Add six `_trade_*_specification()` builders following the existing
   `_infrastructure_*`/`_travel_*` builders: `algorithm_version="1"`,
   `schema_version=METRIC_DOCUMENT_SCHEMA_VERSION`,
   `evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE})`,
   `cohort_window="trade_networks_window_tick"`, population per family, an
   explicit `DenominatorKind`, and the exact value keys from Task 7 in the same
   order. Use `ACTIVE_EDGES` for corridor/location/lineage, `OCCURRENCE` for
   flow/cross-society, and `OPPORTUNITY` for dependence.
3. Append the six builders to `_BUILDERS` after the travel families; do not
   reorder or rewrite earlier entries. Set `METRIC_FAMILY_COUNT = 198`.
4. In `src/analysis/metric_service.py`:
   - add `trade_networks_analysis: TradeNetworksAnalysis | None = None` to
     `MetricComputationInputs`;
   - import the six calculators;
   - after the travel gate, add `if inputs.trade_networks_analysis is not None:`
     and call `_safe` for each family in catalog order;
   - log `INFO trade_networks_metrics_emitted families=6` or
     `DEBUG trade_networks_metrics_disabled`.
5. Do not add a new runner result field, experiment schema field, or database
   column.

### Required Interfaces and Contracts

- `METRIC_FAMILY_COUNT` must equal `len(all_metric_specifications())`.
- Every new family keeps `algorithm_version="1"` and the shared document schema.
- First 192 families remain byte-identical in id order, version, and value keys.
- No family is added to a V1-gate-only list.

### Error Handling and Logging

- Catalog validation raises `MetricCatalogError` on duplicate ids, missing
  builders, or count mismatch.
- No runtime log at import; service logs only family counts.

### Tests

- `tests/unit/test_trade_networks_catalog.py`:
  - `test_catalog_count_is_198`
  - `test_first_192_ids_order_versions_and_keys_are_unchanged`
  - `test_six_trade_families_are_last_and_distinct`
  - `test_trade_family_value_keys_match_documents`
- Update existing count assertions that still say 192 in Task 19; do not
  weaken them to `>=`.
- `uv run pytest tests/unit/test_trade_networks_catalog.py -q`

### Acceptance Criteria

- Catalog count is exactly 198.
- The six new families are the last six in the declared order.
- Prior 192 families have an unchanged structural digest.

### Verification

- `uv run pytest tests/unit/test_trade_networks_catalog.py -q`
- Expected result: all tests pass; no duplicate family id.

## Task 9: Wire completed-run analysis and experiment collectors

### Intent

A real experiment must populate trade metrics from its own committed events. The
collector may not rely on a caller manually constructing a synthetic analysis.

### Implementation Steps

1. Create `src/experiments/trade_networks_completed_run.py`:
   - `build_completed_run_trade_networks_analysis(runner_result=None, *,
     committed_events, run_id, macro_candidates=(), policy=None,
     window_tick=None, recipe_item_kinds=None, item_kind_by_id=None,
     trade_post_locations=()) -> TradeNetworksAnalysis`.
   - Resolve events from `committed_events`; reject `None` with
     `trade_networks_completed_run_requires_events`.
   - Resolve `run_id` with `require_stable_id`.
   - When `recipe_item_kinds` is not supplied, build it from a runner config
     reachable on `runner_result` if present; otherwise leave it empty. The
     collector always supplies it from `arm.assignment.runner_config` agents'
     production catalogs, using only `ItemProduct` outputs. Reject conflicting
     recipe-to-kind entries with a safe code and leave only unique entries.
   - Build `trade_post_locations` from operational `TRADE_POST` assets in
     `runner_result.infrastructure_networks_analysis` or
     `final_infrastructure_assets` when not supplied.
   - If `macro_candidates` is empty, accept an optional
     `runner_result.macro_society_analysis`, call
     `macro_candidates_from_analysis(analysis)`, and expand each candidate
     across **every 32-tick window overlapping `tick_start..tick_end`**,
     deduplicated by `(society_id, window_tick)`. Do not use only `tick_end`.
   - Call `harvest_trade_networks_analysis` with the detached kind, venue, and
     candidate inputs.
   - Log `INFO trade_networks_completed_run transfers=%s corridors=%s
     networks=%s coverage=%s` only.
2. In `src/experiments/collectors.py`, after the existing event retrieval
   (`events = getattr(arm, "committed_events", None)` and result fallback) and
   after the infrastructure/travel `replace`:
   - build `trade_analysis` when events are not `None`:
     `build_completed_run_trade_networks_analysis(arm.runner_result,
     committed_events=events, run_id=arm.assignment.run_id.value,
     window_tick=max(ticks - 1, 0))`;
   - pass `macro_candidates` from `getattr(arm, "macro_society_analysis",
     None)` when present, else `()`;
   - pass recipe kinds extracted from the arm's production catalogs and
     operational trade-post locations extracted from the result's infrastructure
     analysis/assets;
   - `inputs = replace(inputs, trade_networks_analysis=trade_analysis)`.
   - If events are absent, leave the field `None` and log
     `DEBUG trade_networks_collector_missing_events`.
3. Export the builder from `src/experiments/__init__.py` and add it to
   `__all__`.
4. Keep the V1 regression gate unchanged: no trade builder is added to the
   fixed A-E catalog list.

### Required Interfaces and Contracts

- Analysis construction is pure and deterministic over event order.
- The collector never reads `WorldState`; it uses the arm's committed events.
- No runner/result schema field is added; the analysis lives only in the
  in-process metric input and publication path.
- Missing events produce no metrics, not an exception, when the collector is
  used for a legacy run.

### Error Handling and Logging

- A `None` committed-event source in the direct builder raises a safe
  `ValueError`.
- Collector failure is isolated: a trade-analysis exception logs
  `ERROR trade_networks_collector_failed code=%s` and leaves the input `None`;
  it must not fail the whole metric bundle.
- `WARN` for partial/truncated analysis; `INFO` once per completed run.

### Tests

- `tests/unit/test_trade_networks_collector.py`:
  - `test_completed_run_builder_uses_committed_events`
  - `test_builder_accepts_macro_society_analysis`
  - `test_macro_candidate_expands_across_overlapping_windows`
  - `test_builder_uses_production_catalog_recipe_kinds`
  - `test_builder_uses_operational_trade_posts`
  - `test_builder_without_events_raises_safe_error`
  - `test_collector_injects_trade_analysis`
  - `test_collector_missing_events_leaves_none`
  - `test_v1_gate_catalog_does_not_include_trade`
- `uv run pytest tests/unit/test_trade_networks_collector.py -q`

### Acceptance Criteria

- A completed run with exchange events populates trade metrics without manual
  fixture construction.
- A run without events leaves the input unset and does not break the bundle.
- The V1 gate remains unchanged.

### Verification

- `uv run pytest tests/unit/test_trade_networks_collector.py -q`
- Expected result: all tests pass; no new result field.

## Phase Risks and Mitigations

- Risk: metric values drift from the snapshot row definitions.
  Mitigation: both consume the same `TradeNetworksAnalysis`; Task 10 maps rows,
  not re-derives them.
- Risk: collector event retrieval differs across arm/result shapes.
  Mitigation: preserve the existing `arm` then `runner_result` fallback and test
  both.
- Risk: a new family could silently reorder the catalog.
  Mitigation: explicit first-192 digest pin and last-six order test.

## Phase Completion Checklist

- Every Task 7-9 acceptance criterion is satisfied.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
