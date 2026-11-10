# Phase 3: Bottlenecks, Identity, Metrics, and Pins

Plan: [index.md](index.md)
Tasks: 8-12
Depends on: Phase 2 (Tasks 5-7)

## Objective

Add descriptive bottleneck detection with locked thresholds, content-addressed
supply identities with forward-only lineage across every window (including
empty windows), the bounded top-level analysis object, six metric families that
append the catalog from 198 to 204, and the suite-wide pin/fixture sweep that
keeps the existing gate truthful after ownership moves to seven flags.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/analysis/trade_networks_analysis.py` | result 75-98; harvest 154; lineage truncation 208 | Orchestration and bounded lineage |
| `src/analysis/migration_displacement_identity.py` | lineage 159-252 | Forward-only lineage pattern |
| `src/analysis/trade_networks_identity.py` | grouping/linking 26-32 | Per-window overlap linking |
| `src/analysis/trade_networks_metrics.py` | `_document` 90-140; `_milli` 65-69; calculators 163-489; assembler 547-574 | Metric document/quantization pattern |
| `src/analysis/specifications.py` | `METRIC_CATALOG_VERSION` 52; `METRIC_FAMILY_COUNT = 198` 53; last six enum ids 270-275; key sets 8723-8802; `_trade_spec` 8805-8833; builder tail 9387-9392; count assertion 9414-9422 | Exact append pattern 198 → 204 |
| `src/analysis/metric_service.py` | `MetricComputationInputs` 371; trade branch 2449-2489 | New input and branch |
| `src/analysis/__init__.py` | trade exports 1147+ | Facade pattern to mirror |
| `tests/unit/test_metric_specifications.py` | full file | Catalog structure tests |
| `tests/unit/test_trade_networks_catalog.py` | 37-84 | First-N-unchanged/order pin pattern |
| `tests/unit/test_v4_scaffolding_gate.py` | unowned list 44; fail-closed 133; owned 152-207 | Ownership fixture to sweep |
| `tests/unit/test_organization_gate.py` | 39 | Same unowned-flag fixture pattern |
| `tests/unit/test_runner_config_v56.py` | 253 | Flag wire-key list |
| `tests/unit/test_diplomacy_config.py` | 209 | Same |
| `tests/unit/test_formal_rule_regression.py` | 90 | Same |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/analysis/supply_chain_bottlenecks.py` | create | Seven closed rules with locked thresholds |
| `src/analysis/supply_chain_identity.py` | create | Stage/edge/chain tokens, empty-window lineage |
| `src/analysis/supply_chain_analysis.py` | create | `SupplyChainAnalysis`, harvest, empty, layers |
| `src/analysis/supply_chain_metrics.py` | create | Six calculators + assembler |
| `src/analysis/specifications.py` | modify | Append six families, raise count to 204 |
| `src/analysis/metric_service.py` | modify | `supply_chain_analysis` input and branch |
| `src/analysis/__init__.py` | modify | Facade exports for the new analysis modules |
| `tests/unit/test_supply_chain_bottlenecks.py` | create | Rule/threshold/determinism tests |
| `tests/unit/test_supply_chain_identity.py` | create | Lineage tests |
| `tests/unit/test_supply_chain_analysis.py` | create | Composition/coverage tests |
| `tests/unit/test_supply_chain_metrics.py` | create | Metric values/provenance |
| `tests/unit/test_supply_chain_catalog.py` | create | 204 append/order tests |
| `tests/unit/test_supply_chain_pins.py` | create | Suite pin sweep assertions |
| `tests/unit/*.py`, `tests/architecture/*.py` | modify | Catalog/ownership pin sweep (Task 12) |

## Task 8: Detect bounded supply bottlenecks

### Intent

Report where an observed dependency is constrained, using the six requested
dimensions plus one skill rule, without recommending actions or ranking
severity.

### Implementation Steps

1. Create `src/analysis/supply_chain_bottlenecks.py` with `__all__`:
   `SupplyBottleneck`, `detect_bottlenecks`.
2. `SupplyBottleneck` frozen/slots: `bottleneck_token`, `window_index`, `kind`,
   `stage_token`, `edge_token` (at most one may be `-`, never both),
   `observed_count`, `demand_count`, `supply_count`, `ratio_milli`,
   `location_token`, `organization_token`, `skill_domain`, `coverage`.
3. `detect_bottlenecks(graph, evidence, *, policy)` applies exactly these rules
   over completed rows grouped by `(window_index, recipe_id)`:
   - `upstream_shortfall`: for an item edge, `demand = attempt_count +
     unpaired_completions` (equivalently `max(attempts, completions)`), `supply`
     = upstream completions; fire when `demand >= 3` and
     `(demand - supply) * 1000 // demand >= 250`.
   - `single_location_concentration`: `completed >= 3` and top-location share
     `>= 750` milli.
   - `transport_dependency`: `completed >= 3` and `created_elsewhere` share
     `>= 750` milli.
   - `tool_dependency`: recipe `tool_role` not `None`, `completed >= 3`, and
     downstream stage attempts exceed tool-stage completions with a shortfall
     `>= 250` milli.
   - `infrastructure_dependency`: `completed >= 3` and infra-backed share
     `>= 750`; skipped when infrastructure coverage is `missing`.
   - `organization_dependency`: `completed >= 3` and one organization token's
     actor-attributed share `>= 750`; skipped when organization coverage is
     `missing`.
   - `skill_constraint`: non-`None` skill domain, `completed >= 3`, and share of
     performers with `level <= 0.125` `>= 750`; skipped when skill coverage is
     `missing`.
4. Sort by `(window_index, kind.value, stage_token, location_token,
   organization_token, skill_domain)`; token payload is the same sorted tuple.
5. Cap at `policy.max_bottlenecks` with notice `bottleneck_truncated` and
   `partial` coverage.

### Required Interfaces and Contracts

- No `severity`, `rank`, `priority`, `score`, `recommendation`, or
  `suggested_action` field exists.
- Ratios are integer milli rounded down; demand/supply retained.
- Rules never merge; a stage may emit several kinds.
- One-tick crafts with unresolved inputs still contribute demand.

### Requirement Evidence

- Original Request bottlenecks; locked thresholds (Task 5); attempt/completion
  semantics (Task 6); trade truncation pattern.
- Supported combinations: no completions, each rule fires, each under
  threshold, missing dimension (skipped), cap.

### Error Handling and Logging

- `WARN supply_chain_bottleneck_truncated kept=<n> dropped=<n>`.
- `DEBUG supply_chain_bottlenecks_detected count=<n> kinds=<n>`.
- Kinds/counts only; no item names or claim bodies.

### Tests

- `tests/unit/test_supply_chain_bottlenecks.py`:
  `test_upstream_shortfall_threshold`, `test_shortfall_below_threshold`,
  `test_demand_counts_unpaired_completions`,
  `test_single_location_concentration`, `test_transport_dependency`,
  `test_tool_dependency_requires_tool_stage`,
  `test_infrastructure_rule_skipped_without_coverage`,
  `test_organization_rule_requires_actor_attribution`,
  `test_skill_constraint_uses_low_level_share`,
  `test_rows_have_no_score_fields`, `test_sort_is_deterministic`,
  `test_cap_sets_partial_and_notice`, `test_bottleneck_token_is_stable`.
- `uv run pytest tests/unit/test_supply_chain_bottlenecks.py -q`.

### Acceptance Criteria

- Demand 4 / supply 2 yields `upstream_shortfall` with `ratio_milli == 500`.
- Missing optional coverage yields zero rows for that kind.
- Input reordering does not change the output tuple.

### Verification

- `uv run pytest tests/unit/test_supply_chain_bottlenecks.py -q` → all pass.

## Task 9: Mint deterministic supply identities and forward-only lineage

### Intent

Make chains stable analytical objects across windows so structure can emerge,
persist, reroute, split, merge, and disappear, and sustained structure is
countable without a score.

### Implementation Steps

1. Create `src/analysis/supply_chain_identity.py` with `__all__`:
   `mint_stage_token`, `mint_edge_token`, `mint_chain_token`,
   `group_chains_by_window`, `link_supply_chain_lineage`.
2. Token payloads: stage `window|recipe_id`; edge
   `window|edge_kind|from|to`; chain `window|edge|edge|...`.
3. `group_chains_by_window` returns every window from first to last observed,
   including empty tuples.
4. `link_supply_chain_lineage(chains, *, policy)`:
   - compare consecutive windows only;
   - overlap = `shared * 1000 // max(min(prev_edges, curr_edges), 1)`;
   - link when overlap `>= 500`; equal edge sets → `continued`, else
     `transformed`; two or more successors → `split`; two or more predecessors
     → `merge`; no successor → `dissolved`; no predecessor → `emerged`;
   - empty windows produce `dissolved` then `emerged`, never `continued`;
   - cap at `policy.max_lineage_edges` with `lineage_truncated`.
5. `SupplyChainLineageRow`: `chain_token`, `window_index`, `status`,
   `predecessor_tokens`, `successor_tokens`, `shared_edge_count`,
   `overlap_milli`, `coverage`.

### Required Interfaces and Contracts

- Parents are never rewritten; status is the closed six-token set.
- Sustained counts derive from adjacent `continued`/`transformed`; no score.

### Requirement Evidence

- `migration_displacement_identity.py` 159-252; trade identity 26-32.
- Supported combinations: single window, equal/changed edges, split, merge,
  dissolve, emerge, empty gap, cap.

### Error Handling and Logging

- `WARN supply_chain_lineage_truncated kept=<n>`.
- `DEBUG supply_chain_lineage_linked status=<status> count=<n>`.
- No chain tokens or payload bodies in logs.

### Tests

- `tests/unit/test_supply_chain_identity.py`:
  `test_tokens_are_deterministic`, `test_group_includes_empty_windows`,
  `test_equal_edges_continue`, `test_changed_edge_transforms`, `test_split`,
  `test_merge`, `test_dissolve`, `test_emerge`,
  `test_empty_window_breaks_continuity`, `test_parents_are_immutable`,
  `test_overlap_is_floor_milli`, `test_cap_sets_notice`.
- `uv run pytest tests/unit/test_supply_chain_identity.py -q`.

### Acceptance Criteria

- Half-set overlap links as continued/transformed.
- A one-window gap yields dissolved then emerged.
- No row references a later window.

### Verification

- `uv run pytest tests/unit/test_supply_chain_identity.py -q` → all pass.

## Task 10: Compose the bounded `SupplyChainAnalysis` harvest

### Intent

Provide one stable result object for publication and metrics, with
per-dimension coverage, aggregate summary, and a hard layer-separation guard,
and expose it through the analysis facade.

### Implementation Steps

1. Create `src/analysis/supply_chain_analysis.py` with `__all__`:
   `SupplyChainAnalysis`, `harvest_supply_chain_analysis`,
   `empty_supply_chain_analysis`, `SupplyChainLayerView`,
   `project_supply_chain_layers`, `assert_supply_chain_layer_separation`.
2. `harvest_supply_chain_analysis(events, *, recipes, policy=None,
   window_tick=None, skill_levels=None, infrastructure=None,
   organization_claims=None)` runs evidence → graph → bottlenecks → lineage →
   stage/location/organization rows → layer projection.
3. `SupplyChainAnalysis` fields: `window_tick`, `stages`, `edges`, `chains`,
   `lineage`, `bottlenecks`, `locations`, `organizations`, `layers`,
   `evidence_coverage`, `skill_coverage`, `infrastructure_coverage`,
   `organization_coverage`, `lineage_coverage`, `coverage`, `notices`,
   `stage_count`, `edge_count`, `chain_count`, `bottleneck_count`,
   `location_count`, `organization_count`, `sustained_chain_count`, `max_depth`.
4. Aggregate coverage: `missing` when no stages; `partial` when any dimension is
   partial/missing or any truncation notice exists; else `complete`.
   `lineage_coverage` is `missing` under two observed windows.
5. `sustained_chain_count` counts chains with at least one incoming and one
   outgoing continued/transformed transition.
6. `empty_supply_chain_analysis(window_tick=0)` returns empty tuples, `missing`
   coverage, zero counts.
7. Layers: `objective_derived` stages/edges/locations, `analytical`
   chains/lineage/bottlenecks, `owner_claims` organization rows;
   `assert_supply_chain_layer_separation` rejects wrong-layer rows and
   forbidden key prefixes.
8. `src/analysis/__init__.py`: add facade imports/exports for
   `supply_chain_analysis`, `supply_chain_contract`, `supply_chain_events`,
   `supply_chain_policy`, `supply_chain_rows`, `supply_chain_graph`,
   `supply_chain_layers` mirroring the trade block at 1147+.

### Required Interfaces and Contracts

- Types checked; foreign inputs rejected by type name.
- No forbidden imports (see Task 21).
- Notices sorted unique; counts equal tuple lengths.

### Requirement Evidence

- `trade_networks_analysis.py` 75-98/154/208; `trade_networks_layers.py` 20-24;
  `analysis/__init__.py` 1147+.
- Supported combinations: empty, single window, multi-window, partial
  dimensions, truncation, sustained chain.

### Error Handling and Logging

- `INFO supply_chain_analysis_built stages=<n> edges=<n> chains=<n>
  bottlenecks=<n> coverage=<value>`.
- `WARN supply_chain_analysis_partial dimensions=<codes>`.
- Layer leak raises `SupplyChainError("supply_chain_layer_leak")`.

### Tests

- `tests/unit/test_supply_chain_analysis.py`:
  `test_empty_analysis_is_missing`, `test_counts_match_rows`,
  `test_partial_dimension_sets_partial_aggregate`,
  `test_lineage_coverage_requires_two_windows`,
  `test_sustained_chain_count`, `test_layers_project_rows`,
  `test_layer_leak_raises`, `test_rejects_foreign_input`,
  `test_analysis_is_frozen`, `test_analysis_facade_exports`.
- `uv run pytest tests/unit/test_supply_chain_analysis.py -q`.

### Acceptance Criteria

- Harvest + craft + assemble events over two windows yield non-zero stages,
  edges, chains, and lineage.
- Coverage mirrors the weakest dimension.
- Every row appears in exactly one layer.

### Verification

- `uv run pytest tests/unit/test_supply_chain_analysis.py -q` → all pass.

## Task 11: Add six supply-chain metric families to 204

### Intent

Expose the analysis through the governed catalog with stable ids, value keys,
order, and provenance, so experiments and clients see the same thresholds.

### Implementation Steps

1. Create `src/analysis/supply_chain_metrics.py` with `__all__`: the six
   `compute_*` functions and `assemble_supply_chain_metrics`.
2. Each calculator takes `analysis: object`, keyword-only `run_id`,
   `input_revision`, validates `type(analysis) is SupplyChainAnalysis`, and
   returns a `MetricDocument` via a local `_document` with
   `source_kind="supply_chain_analysis"`.
3. Exact ids and keys, appended after the six trade families:
   1. `supply_chain_structure@1` — `stage_count`, `edge_count`, `chain_count`,
      `max_chain_depth`, `sustained_chain_count`, `window_tick`, `coverage`.
   2. `supply_dependency_graph@1` — `resource_edge_count`, `item_edge_count`,
      `structure_edge_count`, `storage_edge_count`, `transport_edge_count`,
      `location_node_count`, `window_tick`, `coverage`.
   3. `supply_bottleneck_pressure@1` — the seven `*_count` keys,
      `max_ratio_milli`, `window_tick`, `coverage`.
   4. `supply_resource_tool_dependency@1` — `harvest_stage_count`,
      `craft_stage_count`, `tool_stage_count`, `tool_downstream_stage_count`,
      `resource_edge_count`, `window_tick`, `coverage`.
   5. `supply_location_infrastructure_reliance@1` — `location_count`,
      `infrastructure_backed_stage_count`, `infrastructure_location_count`,
      `single_location_stage_count`, `window_tick`, `coverage`.
   6. `supply_organization_coordination@1` — `organization_count`,
      `organization_stage_count`, `organization_claim_count`,
      `organization_dependency_count`, `window_tick`, `coverage`.
4. `max_ratio_milli` is 0 with no rows; all other values are counts or the
   window tick.
5. `assemble_supply_chain_metrics(analysis, *, run_id, input_revision)` returns
   the six documents in order.
6. `src/analysis/specifications.py`: add six enum members after
   `TRADE_NETWORK_LINEAGE`; add key tuples after 8723-8802; add `_supply_spec`
   mirroring `_trade_spec` with `cohort_window="supply_chain_window_tick"` and
   `EvidenceStage.OBJECTIVE_EVENT_STATE`; extend the builder tail
   (9387-9392); set `METRIC_FAMILY_COUNT = 204`.
7. `src/analysis/metric_service.py`: add `supply_chain_analysis: object | None`
   to `MetricComputationInputs` (near 371) and a branch after the trade branch
   (2449-2489) calling the six calculators via `_safe`, logging
   `metric_families_assembled source=supply_chain families=6`.

### Required Interfaces and Contracts

- The first 198 ids/order/versions/value keys stay byte-identical.
- Catalog version stays `metric-catalog-v1`; no `@2` versions.
- All new values are ints except the existing coverage ratio field.
- No composite score or optimization ratio family.

### Requirement Evidence

- `specifications.py` 52-53/270-275/8723-8899/9387-9392/9414-9422;
  `trade_networks_metrics.py` 65-140/547-574; `metric_service.py` 371/2449-2489.
- Supported combinations: empty analysis, single window, multi-window,
  bottlenecks present/absent, partial dimensions.

### Error Handling and Logging

- Calculator mismatch raises `TypeError` before document creation.
- `_safe` keeps existing reason codes.
- `INFO metric_families_assembled source=supply_chain families=6` once.

### Tests

- `tests/unit/test_supply_chain_metrics.py`:
  `test_six_documents_in_order`, `test_value_keys_match_contract`,
  `test_empty_values_are_zero`, `test_max_ratio_milli_is_zero_when_empty`,
  `test_provenance_source_kind`, `test_rejects_foreign_analysis`,
  `test_no_float_values`, `test_no_score_key`.
- `tests/unit/test_supply_chain_catalog.py`:
  `test_catalog_count_is_204`, `test_first_198_ids_unchanged`,
  `test_last_six_ids_and_order`, `test_last_six_versions_and_cohort`,
  `test_last_six_value_keys`, `test_no_duplicate_ids`.
- `uv run pytest tests/unit/test_supply_chain_metrics.py tests/unit/test_supply_chain_catalog.py tests/unit/test_metric_specifications.py tests/unit/test_trade_networks_catalog.py -q`.

### Acceptance Criteria

- `METRIC_FAMILY_COUNT == 204` and catalog validation passes.
- The six families appear last in the locked order.
- Prior catalog tests pass after the sweep in Task 12.

### Verification

- `uv run pytest tests/unit/test_supply_chain_metrics.py tests/unit/test_supply_chain_catalog.py tests/unit/test_metric_specifications.py -q` → all pass.

## Task 12: Sweep suite-wide ownership and metric-catalog pins

### Intent

Keep the existing gate truthful after the catalog and ownership move. Without
this task the full suite cannot pass: 71 test files pin the catalog at 198 and
several activation suites use `supply_chains` as the sample unowned flag.

### Implementation Steps

1. Catalog pin sweep: replace every assertion that `METRIC_FAMILY_COUNT` (or a
   literal metric-family count) equals `198` with `204`. At minimum this
   includes all `tests/unit/*catalog*.py`, `tests/unit/*metrics*.py`,
   `tests/unit/*_docs.py`, `tests/unit/test_metric_specifications.py`,
   `tests/unit/test_bounded_experiment_metrics.py`, and every
   `tests/architecture/*_boundaries.py` that asserts the count. Use a
   repository-wide search for `== 198` and `198 metric` to enumerate.
2. Update the trade catalog regression so it asserts "first **198** unchanged,
   last 6 are supply-chain families" (currently first 192 / last 6 trade).
3. Ownership fixture sweep: every test that enables `supply_chains` expecting
   `capability_unimplemented` must use a still-unowned flag
   (`markets_credit`). At minimum:
   `tests/unit/test_v4_scaffolding_gate.py`,
   `tests/unit/test_organization_gate.py`,
   `tests/unit/test_borders_activation.py`,
   `tests/unit/test_diplomacy_config.py`,
   `tests/unit/test_diplomacy_treaty_config.py`,
   `tests/unit/test_formal_rule_regression.py`,
   `tests/unit/test_migration_displacement_activation.py`,
   `tests/unit/test_runner_config_v56.py`.
   Keep `test_runner_config_v56.py`'s wire-key list including
   `supply_chains` (it asserts the accepted keyset, not ownership).
4. Update owned-count assertions (`six` → `seven`) wherever the V4 owned set is
   enumerated; leave `14`/`12` unchanged.
5. Add `tests/unit/test_supply_chain_pins.py`:
   `test_catalog_pins_are_204` (scans the suite for stale `== 198`),
   `test_no_test_expects_supply_chains_unimplemented` (AST/text scan),
   `test_owned_flag_count_is_seven`.
6. Do not edit docs pins here; docs are Task 24.

### Required Interfaces and Contracts

- The scan tests fail if a stale pin or stale unowned expectation returns.
- No production code changes in this task.
- The sweep preserves every "first N unchanged" convention by shifting N to
  198.

### Requirement Evidence

- `grep -rn "== 198" tests` returns 71 files at plan time; the search is the
  enumeration contract. `test_v4_scaffolding_gate.py` 44/133-152 proves the
  unowned fixture pattern.
- Supported combinations: stale pin (test fails), stale fixture (test fails),
  clean suite (passes).

### Error Handling and Logging

- Tests only; failure messages name the file and stale token.

### Tests

- `uv run pytest tests/unit/test_supply_chain_pins.py -q`
- `uv run pytest tests/unit/test_v4_scaffolding_gate.py tests/unit/test_organization_gate.py tests/unit/test_runner_config_v56.py -q`
- `uv run pytest tests/unit tests/architecture -q` (full local pin gate; may be
  run in Task 25 if too slow here, but must pass before certification).

### Acceptance Criteria

- No `tests/` file pins the catalog at 198.
- No test expects `supply_chains` to fail as unowned.
- Owned-flag enumerations read seven.

### Verification

- `uv run pytest tests/unit/test_supply_chain_pins.py tests/unit/test_v4_scaffolding_gate.py tests/unit/test_trade_networks_catalog.py -q` → all pass.

## Phase Risks and Mitigations

- Risk: catalog append reorders prior entries. Mitigation: Task 11 pins the
  first 198 and Task 12 updates the trade "first N" assertion.
- Risk: bottleneck rules drift into ranking. Mitigation: forbidden keys, no
  severity field, deterministic sort, negative test.
- Risk: lineage treats an empty window as continuation. Mitigation: explicit
  test.
- Risk: the pin sweep is missed and the gate stays red. Mitigation: dedicated
  Task 12 plus a scan test.

## Phase Completion Checklist

- Every Task 8-12 satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
