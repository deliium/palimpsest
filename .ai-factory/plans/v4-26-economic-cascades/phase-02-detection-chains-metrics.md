# Phase 2: Episode Detection, Chains, Analysis, and Metrics

Plan: [index.md](index.md)
Tasks: 5-8
Depends on: Phase 1 (Tasks 1-4)

## Objective

Turn disruption rows, stage counts, and the dependency graph into deterministic
episodes, quantized shortfalls, bounded dependency-conditioned chains, and
propagation rows; compose the single immutable `EconomicCascadesAnalysis`; and
append eight metric families at catalog positions 236-243 so the count becomes
244. No world rule changes and no causal-truth assertion is introduced.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/analysis/inequality_indices.py` | `quantized_gini` (137-143), `inequality_distribution_summary` (194-247) | Integer-milli quantization convention |
| `src/analysis/supply_chain_bottlenecks.py` | `UPSTREAM_SHORTFALL` (171-205), `TOOL_DEPENDENCY` (261-290), `SKILL_CONSTRAINT` (353-365) | Existing shortfall inference to refine temporally, not duplicate |
| `src/analysis/economic_inequality_analysis.py` | caps (253-450), layer assertion (387-392), digest (187-209) | Caps/coverage/notices template |
| `src/analysis/social_mobility_analysis.py` | analysis dataclass (48-73), harvest/digest (38-43) | Newest aggregate template |
| `src/analysis/economic_inequality_metrics.py` | `_document` (90-142), eight compute functions | Metric document mapping |
| `src/analysis/specifications.py` | `MetricFamilyId` append block (300-317), V4-24 keys (9098-9149), `_economic_inequality_spec` (9686-9725), `_BUILDERS` tail (10463-10478), `METRIC_FAMILY_COUNT` (53) | Exact append points |
| `src/analysis/metric_service.py` | `MetricComputationInputs` (436-437), social block (2766-2816) | Input field and emission pattern |
| `src/analysis/models.py` | `MetricAvailability` (508-514), `MetricCoverage` (517-547), `MetricDocument` (584-605) | Output contract |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/analysis/economic_cascades_detection.py` | create | Episode aggregation and quantized stage shortfalls |
| `src/analysis/economic_cascades_chains.py` | create | Dependency-conditioned chain linking and propagation rows |
| `src/analysis/economic_cascades_analysis.py` | create | Bounded `EconomicCascadesAnalysis`, digest, coverage |
| `src/analysis/economic_cascades_metrics.py` | create | Eight metric-document compute functions |
| `src/analysis/specifications.py` | modify | Eight enum members, four key tuples, `_economic_cascades_spec`, eight builders, count 244 |
| `src/analysis/metric_service.py` | modify | Input field, imports, emission block, `catalog=244` |
| `src/analysis/__init__.py` | modify | Export detection, chain, analysis, and metric symbols |
| `tests/unit/test_economic_cascades_detection.py` | create | Episode/shortfall cases |
| `tests/unit/test_economic_cascades_detection_properties.py` | create | Hypothesis invariants |
| `tests/unit/test_economic_cascades_chains.py` | create | Linking, depth, lag, states |
| `tests/unit/test_economic_cascades_chains_properties.py` | create | Monotone prefix, no back-dating |
| `tests/unit/test_economic_cascades_analysis.py` | create | Caps, coverage, notices, digest |
| `tests/unit/test_economic_cascades_bounds.py` | create | Independent cap assertions |
| `tests/unit/test_economic_cascades_metrics.py` | create | Eight documents and state mapping |
| `tests/unit/test_economic_cascades_catalog.py` | create | 236→244 append discipline |
| `tests/unit/test_metric_specifications.py` | modify | Family count 236→244 |

## Task 5: Detect disruption episodes and quantized stage shortfalls

### Intent
Collapse disruption rows into per-window episodes and compute one shortfall
statistic per stage, so chain linking compares like with like and no severity is
invented.

### Implementation Steps
1. Create `src/analysis/economic_cascades_detection.py`:
   - `EconomicCascadeDetectionResult` dataclass: `episodes`, `stage_rows`,
     `notices`, `coverage`, `window_count`, `shortfall_stage_count`,
     `disruption_count`, `tool_shortage_available`.
   - `detect_economic_cascade_episodes(*, disruptions, stages, policy=None)`.
2. Episodes: group `CascadeDisruptionRow` by `(window_index, kind)`, ordered by
   `(window_index, kind.value)`. Emit `CascadeEpisodeRow` with
   `disruption_count`, `magnitude_total`, distinct `subject_count`,
   `first_sequence`, `last_sequence`; `coverage=partial` if any source row is
   partial. Cap at `policy.max_disruptions` episodes with a
   `disruptions_truncated` notice.
3. Stage shortfall:
   - `demand_count` comes from Task 4; `completion_count` counts completed
     observations only.
   - If `demand_count == 0`: `shortfall_share_milli=0`,
     `availability=unavailable`, row retained for coverage.
   - Else `shortfall_share_milli = min(1000, max(0, round(1000 * (demand_count
     - completion_count) / demand_count)))` using integer arithmetic
     (`(1000 * shortfall + demand // 2) // demand`), never floats.
   - A stage is in shortfall when
     `shortfall_share_milli >= policy.shortfall_share_milli`.
   - `availability=available` when the stage has at least one attempt; else
     `insufficient_samples` when demand exists but attempts are zero; else
     `unavailable`.
   - Cap stage rows at `policy.max_stages` with `stages_truncated`.
4. Tool-shortage proxy (this task owns it): for each tool-output stage
   (`output_kind == "tool"`), compare `completion_count` in adjacent windows. A
   drop of `d >= 1` emits
   `CascadeDisruptionRow(kind=tool_shortage, subject_token=recipe_id,
   magnitude_count=d, evidence_event_token=PROXY_EVIDENCE_TOKEN,
   coverage=partial)` in the later window, then re-aggregates episodes so the
   proxy participates like any other disruption. When no tool-output stage
   exists, emit no row and set `tool_shortage_available=False`.
5. Empty evidence returns empty episodes and rows with `coverage=missing`.

### Required Interfaces and Contracts
- All arithmetic is integer; no `float` enters a row or statistic.
- `shortfall_share_milli` is a share, never a severity or priority.
- Episodes never merge different disruption kinds.
- Detector is pure and deterministic; no locale or hash-order dependence.

### Requirement Evidence
- Original Request "Track causal chains" and "Provide dependency/cascade
  analytics".
- `src/analysis/supply_chain_bottlenecks.py:171-205` (shortfall precedent).
- `src/analysis/inequality_indices.py` quantization convention.

### Error Handling and Logging
- DEBUG `economic_cascades_detection_scanned events=<n> stages=<n>`.
- INFO `economic_cascades_detection_complete episodes=<n> shortfall=<n>`.
- WARN `economic_cascades_insufficient_stage_samples`,
  `economic_cascades_nonfinite_input`.
- ERROR `economic_cascades_invalid_event_order` with a code only.
- Never log quantities, recipe ids, or locations.

### Tests
- `tests/unit/test_economic_cascades_detection.py`: zero-demand stage,
  threshold boundary at 250, one completion short, episode grouping, partial
  propagation, tool proxy absent, cap prefix.
- `tests/unit/test_economic_cascades_detection_properties.py`: Hypothesis for
  `0 <= shortfall_share_milli <= 1000`, episode counts summing to source rows,
  and order stability.

### Acceptance Criteria
- Shortfall shares are exact integer shares of demand.
- No stage with demand 0 is reported as available.
- Episode counts reconcile with disruption rows after truncation.

### Verification
- `uv run pytest tests/unit/test_economic_cascades_detection.py tests/unit/test_economic_cascades_detection_properties.py -q`
- Expected result: pass.

## Task 6: Link dependency-conditioned chains and compose propagation rows

### Intent
Connect each observed disruption to downstream stage shortfalls only along
emitted dependency edges, bounded by depth and lag, and report whether the
connection is `linked`, `unlinked`, or `unresolved`. This is the feature's
causal-chain output; it is explicitly analytical, not an objective cause claim.

### Implementation Steps
1. Create `src/analysis/economic_cascades_chains.py`:
   - `EconomicCascadeChainResult` dataclass: `chains`, `propagation_rows`,
     `notices`, `coverage`, `chain_count`, `linked_count`, `unlinked_count`,
     `unresolved_count`, `max_depth`.
   - `link_economic_cascade_chains(*, episodes, disruptions, stages, edges,
     labor_joins=(), policy=None)`.
2. Build an adjacency map from `upstream_token` to
   `(downstream_recipe_id, kind, depth)` using only emitted edges. Build
   subject maps:
   - resource subject (recipe id) → that harvest stage and its dependency
     descendants; a `resource:<node>` subject has no recipe and is
     `unresolved`.
   - route subject `route:<origin>-><destination>` → stages at either endpoint
     with a `transport_dependency` edge.
   - infrastructure subject `asset:<kind>@<location>` → stages through the
     `infrastructure_dependency` edge for that asset.
   - population subject (body token) → recipes in `labor_joins` for that actor;
     each chain's `upstream_token` is `labor:<recipe_id>`, never the body token;
     when the join is absent the chain is `unresolved`.
   - tool subject (recipe id) → stages with `tool_dependency` edges from that
     recipe.
3. For each episode, traverse from the matched stage(s) breadth-first to at most
   `policy.max_chain_depth`, and consider stage rows in windows
   `w .. w + policy.max_propagation_lag_windows`. For each reachable downstream
   stage:
   - emit `CascadeChainRow` with `depth`, `lag_windows = downstream_window -
     upstream_window`, `shortfall_share_milli` from the downstream stage,
     `chain_token = mint_chain_token(...)`, and
     `state=linked` when the stage is in shortfall, else `unlinked`.
   - emit `state=unresolved` when a dependency edge exists but the downstream
     stage row is missing or the join is absent; never back-date a downstream
     row into an earlier window.
   - Deduplicate by `(chain_token, window_index)`; sort by
     `(window_index, disruption_kind.value, depth, downstream_recipe_id,
     chain_token)`.
4. Propagation rows: per `(window_index, disruption_kind)`, aggregate chain
   counts and statuses; `mean_depth_milli = round(1000 * total_depth /
   chain_count)`; `mean_lag_milli = round(1000 * total_lag / chain_count)`;
   `propagation_share_milli = round(1000 * linked_chain_count / chain_count)`
   (0 when `chain_count == 0`); `downstream_stage_count` = distinct downstream
   recipe ids. `availability=available` when
   `linked_chain_count >= policy.min_linked_chains`; `insufficient_samples` when
   `0 < linked < min`; `unavailable` when no chain exists.
5. Cap chains at `policy.max_chains` and propagation rows at
   `policy.max_propagation_rows`; append `chains_truncated` /
   `propagation_truncated` and set `partial`.

### Required Interfaces and Contracts
- A chain's `state` is closed to `linked|unlinked|unresolved|unavailable`.
- `depth >= 1`, `lag_windows >= 0`, and `lag_windows <= max lag`.
- No chain row contains an agent-id owner token or a raw body token; objective
  topology tokens (`recipe`, `asset:<kind>@<location>`,
  `route:<origin>-><destination>`) are allowed.
- A downstream shortfall earlier than the disruption is never linked.

### Requirement Evidence
- Original Request chain example "mine loss → material shortage → tool shortage
  → food productivity decline" and "Do not script downstream outcomes".
- Phase 1 `CascadeDependencyKind` and the recipe graph from Task 4.
- `src/world/_production.py:287-367` proves input/tool propagation is objective
  and already emergent; the chain row measures it instead of asserting it.

### Error Handling and Logging
- DEBUG `economic_cascades_chain_traversal nodes=<n> depth=<n>`.
- INFO `economic_cascades_chains_complete chains=<n> linked=<n>`.
- WARN `economic_cascades_chain_unresolved`,
  `economic_cascades_chains_truncated`,
  `economic_cascades_labor_join_missing`.
- ERROR `economic_cascades_invalid_chain` with a code only.
- Never log chain tokens, subjects, or lag values per row.

### Tests
- `tests/unit/test_economic_cascades_chains.py`: the four-step mine chain
  (resource depletion → ore stage → tool stage → grain stage) linked at depth
  3; missing intermediate row → unresolved; downstream row in an earlier window
  → unresolved, never linked; route closure → endpoint stage; infrastructure
  destruction → mapped stage; population loss without a labor join →
  unresolved; depth 7 excluded; lag 3 windows excluded; threshold 3 linked
  chains for availability; deterministic token stability.
- `tests/unit/test_economic_cascades_chains_properties.py`: Hypothesis proving
  no back-dating, depth/lag bounds, and prefix stability under truncation.

### Acceptance Criteria
- Every chain follows an emitted dependency edge.
- Shortfall before disruption never becomes `linked`.
- Per-kind availability is deterministic and count-based.

### Verification
- `uv run pytest tests/unit/test_economic_cascades_chains.py tests/unit/test_economic_cascades_chains_properties.py -q`
- Expected result: pass.

## Task 7: Compose the bounded `EconomicCascadesAnalysis` harvest

### Intent
Produce the single immutable value the metric service, snapshot composer, and
publication bridge consume, with independent caps, notice deduplication, and a
hard three-layer separation check.

### Implementation Steps
1. Create `src/analysis/economic_cascades_analysis.py`:
   - `EconomicCascadesAnalysis` frozen slots dataclass: `policy_version`,
     `window_tick`, `window_count`, `coverage`, `evidence_coverage`,
     `chain_coverage`, `disruptions`, `episodes`, `stages`, `edges`, `chains`,
     `propagation_rows`, `coverage_row`, `layers`, `notices`, `event_count`,
     `disruption_count`, `stage_count`, `dependency_edge_count`,
     `labor_join_count`, `chain_count`, `linked_chain_count`,
     `unlinked_chain_count`, `unresolved_chain_count`,
     `disruption_kind_count`, `max_depth`; properties `row_count`,
     `source_layers`.
   - `empty_economic_cascades_analysis()` with `missing` coverage and empty
     tuples.
   - `economic_cascades_analysis_digest(analysis)` — SHA-256 over policy
     version, window bounds, coverage tokens, row counts, linked counts, and
     notices only.
   - `harvest_economic_cascades_analysis(*, events, recipe_specs, stages=None,
     infrastructure=(), routes=(), labor_joins=(), policy=None,
     window_end=None)`:
     1. Empty events or empty recipe specs → empty analysis (not zeros).
     2. Apply `window_end` and drop later rows.
     3. When `stages` is `None`, build it inside the analysis with
        `supply_evidence_from_events(events, policy=<supply-chain analysis
        policy>, recipes=recipe_specs, skill_levels=(),
        infrastructure=(), organization_claims=())`; never import the
        `experiments` or `simulation` packages.
     4. Harvest disruptions (Task 3), build dependencies (Task 4), detect
        episodes/shortfalls including the tool proxy (Task 5), link chains
        (Task 6).
     5. Enforce caps in order events → disruptions → stages → edges → chains →
        propagation → coverage; each appends one bounded notice and sets
        `partial`.
     6. Compose `CascadeCoverageRow` for the latest surviving window.
     7. Call `assert_economic_cascade_layer_separation` over objective
        disruptions/stages, dependency edges, and analytical episodes/chains/
        propagation rows before returning.
     8. Merge and deduplicate notices, truncate to `policy.max_notices`, and
        derive `coverage`/`evidence_coverage`/`chain_coverage` from child
        coverage plus truncation.
   - Export every public symbol from `src/analysis/__init__.py`.
2. `coverage=missing` must never coexist with non-empty rows.
3. `window_tick` is the highest window tick present in surviving rows.

### Required Interfaces and Contracts
- Pure and deterministic; no clocks, no environment reads, no stores.
- The analysis never imports `simulation`, `experiments`, `persistence`, or
  `api`.
- No metric or snapshot reads a private helper; only the exported harvest and
  value are used.

### Requirement Evidence
- `.ai-factory/ARCHITECTURE.md` Key Principle 1 and analysis isolation rules.
- `src/analysis/economic_inequality_analysis.py:253-450` (cap/coverage
  template) and `:387-392` (layer assertion).

### Error Handling and Logging
- DEBUG counts per layer.
- INFO `economic_cascades_analysis_complete windows=<n> rows=<n>`.
- WARN `economic_cascades_partial_coverage`,
  `economic_cascades_truncated`.
- ERROR `economic_cascades_analysis_invalid` with a code only.
- Never log tokens, distributions, or evidence contents.

### Tests
- `tests/unit/test_economic_cascades_analysis.py`: empty input, one episode,
  full chain, partial coverage, digest stability across hash seeds, layer
  assertion invoked, window_end filtering.
- `tests/unit/test_economic_cascades_bounds.py`: each cap independently,
  deterministic prefix, notice bound, coverage downgrade.

### Acceptance Criteria
- Empty evidence yields an empty analysis with `missing` coverage.
- Every cap is independently enforced and reported once.
- Layer separation is asserted before the value escapes.

### Verification
- `uv run pytest tests/unit/test_economic_cascades_analysis.py tests/unit/test_economic_cascades_bounds.py -q`
- Expected result: pass.

## Task 8: Append eight metric families (236 → 244) and wire the service

### Intent
Expose cascade results through the closed metric catalog without touching the
first 236 families' ids, order, versions, or value keys.

### Implementation Steps
1. In `src/analysis/specifications.py`, append after `SOCIAL_MOBILITY_COVERAGE`:
   `RESOURCE_LOSS_CASCADE`, `ROUTE_CLOSURE_CASCADE`,
   `INFRASTRUCTURE_DESTRUCTION_CASCADE`, `POPULATION_LOSS_CASCADE`,
   `TOOL_SHORTAGE_CASCADE`, `CASCADE_DEPENDENCY_STRUCTURE`,
   `CASCADE_PROPAGATION`, `CASCADE_COVERAGE` with lower-snake string values.
2. Append four key tuples immediately after the social-mobility keys:
   - `CASCADE_KIND_KEYS = ("cascade_window_tick", "disruption_count",
     "stage_shortfall_count", "linked_chain_count", "unlinked_chain_count",
     "unresolved_chain_count", "mean_chain_depth_milli", "mean_lag_milli",
     "propagation_share_milli", "coverage", "availability")`.
   - `CASCADE_DEPENDENCY_KEYS = ("cascade_window_tick", "stage_count",
     "dependency_edge_count", "resource_edge_count", "item_edge_count",
     "tool_edge_count", "infrastructure_edge_count", "transport_edge_count",
     "labor_join_count", "max_depth", "coverage", "availability")`.
   - `CASCADE_PROPAGATION_KEYS = ("cascade_window_tick",
     "disruption_kind_count", "chain_count", "linked_chain_count",
     "unlinked_chain_count", "unresolved_chain_count", "mean_depth_milli",
     "mean_lag_milli", "downstream_stage_count", "coverage", "availability")`.
   - `CASCADE_COVERAGE_KEYS = ("cascade_window_tick", "window_count",
     "event_count", "disruption_count", "stage_count",
     "dependency_edge_count", "chain_count", "linked_chain_count",
     "truncated", "coverage", "availability")`.
3. Add `_economic_cascades_spec(*, family_id, population, denominator,
   denominator_kind, keys, opportunity, owner_claims=False)` mirroring
   `_economic_inequality_spec`, with `cohort_window="cascade_window_tick"`,
   the same deceased/zero/self/censoring/empty/one/all-zero/unknown cases, and
   `availability_behavior="explicit_unknown_without_supply_chain_or_disruption_evidence"`.
   No family sets `owner_claims=True`.
4. Add eight `_spec_*` builders:
   - five kind families: population `disruption_episodes`,
     denominator `linked_or_unlinked_chains`, opportunity text naming only the
     one kind and stating `dependency-conditioned observation, not proof of
     cause`.
   - dependency: `production_stages`, `dependency_edges`, `"observed recipe and
     topology edges only"`.
   - propagation: `disruption_kinds_with_chains`, `propagation_rows`,
     `"per-kind descriptive linkage; no severity or ranking"`.
   - coverage: `observed_windows`, `disruption_episodes`, `"evidence coverage
     only"`.
   Every builder sets `formulas={key: key.replace("_", " ") for key in keys}`.
5. Append the eight builders to `_BUILDERS` in positions 236-243 and set
   `METRIC_FAMILY_COUNT = 244`.
6. Capture the first-236 digest before appending:
   `uv run python -c "import hashlib,json; from analysis.specifications import all_metric_specifications as a; print(hashlib.sha256(json.dumps([s.family_id.value for s in a()[:236]], separators=(',',':')).encode()).hexdigest())"`
   Paste the printed value into the catalog test as `_FIRST_236_DIGEST`.
7. Create `src/analysis/economic_cascades_metrics.py`:
   - `_document(...)` maps absent/missing → `MetricAvailability.UNKNOWN` with an
     empty payload; `available`/`insufficient_samples` →
     `PRESENT`/`PARTIAL` with a coverage ratio.
   - `compute_resource_loss_cascade`, `compute_route_closure_cascade`,
     `compute_infrastructure_destruction_cascade`,
     `compute_population_loss_cascade`, `compute_tool_shortage_cascade`,
     `compute_cascade_dependency_structure`, `compute_cascade_propagation`,
     `compute_cascade_coverage`, each
     `(analysis, *, run_id: str, input_revision: str) -> MetricDocument`.
8. In `src/analysis/metric_service.py`, add
   `economic_cascades_analysis: EconomicCascadesAnalysis | None = None` to
   `MetricComputationInputs`, import the eight functions, and add an emission
   block after the social-mobility block that calls all eight under `_safe(...)`
   and logs `INFO economic_cascades_metrics_emitted families=8 catalog=244`;
   the `else` branch logs `DEBUG economic_cascades_metrics_disabled`.
9. Update `tests/unit/test_metric_specifications.py` expectations to 244.

### Required Interfaces and Contracts
- The first 236 specifications keep ids, order, versions, keys, and formulas
  byte-identically; only the count and tail change.
- Every new family has non-empty `formulas`, `evidence_inputs`, and a
  non-empty opportunity text, or `MetricSpecification.__post_init__` rejects it.
- No family aggregates the five kinds into one score; `CASCADE_PROPAGATION`
  reports counts and means per kind, not a composite.
- `cascade_window_tick` is the cohort window for all eight families.

### Requirement Evidence
- Original Request "Provide dependency/cascade analytics".
- `src/analysis/specifications.py` closed catalog and
  `.ai-factory/ARCHITECTURE.md` requirement 1.
- V4-24/V4-25 append discipline (228→236) proves the tail-only pattern.

### Error Handling and Logging
- INFO `economic_cascades_metrics_emitted families=8 catalog=244`.
- DEBUG `economic_cascades_metrics_disabled`.
- ERROR `economic_cascades_metric_invalid` with a code only.
- Never log values, run ids beyond the existing safe field, or tokens.

### Tests
- `tests/unit/test_economic_cascades_metrics.py`: each family, absent input,
  `insufficient_samples` mapping, partial coverage, latest-window selection,
  forbidden keys rejected.
- `tests/unit/test_economic_cascades_catalog.py`: count 244, first-236 digest,
  appended ids exactly in order, locked cases.
- `tests/unit/test_metric_specifications.py`: 244 families, unique ids.

### Acceptance Criteria
- `validate_metric_catalog()` passes with 244 families.
- Eight documents emit with an analysis and none with `None`.
- No composite score exists in any family.

### Verification
- `uv run pytest tests/unit/test_economic_cascades_metrics.py tests/unit/test_economic_cascades_catalog.py tests/unit/test_metric_specifications.py -q`
- Expected result: pass.

## Phase Risks and Mitigations
- Risk: chain linking is read as proof of objective causality.
  Mitigation: `linked|unlinked|unresolved` states, opportunity text, and a
  leakage test rejecting `caused_by`, `root_cause`, and `severity`.
- Risk: a single upstream event fans out beyond caps.
  Mitigation: per-window cap, depth/lag bounds, deterministic prefix, and
  `partial` coverage.
- Risk: catalog append reorders existing families.
  Mitigation: first-236 digest and builder-position assertions.

## Phase Completion Checklist
- Tasks 5-8 acceptance criteria met.
- Targeted Phase 2 tests pass.
- `METRIC_FAMILY_COUNT == 244` with the first 236 unchanged.
- `index.md` Tasks 5-8 checkboxes are updated after verification.
