# Phase 2: Outcome Detection, Generation Lags, and Metrics

Plan: [index.md](index.md)
Tasks: 5-8
Depends on: Phase 1 (Tasks 1-4)

## Objective

Convert genealogy plus outcome rows into deterministic, quantized
mobility/persistence rows, add generation-lag strata, bound the whole harvest,
and publish eight metric families at catalog positions 228-235. After this phase
the analysis produces `SocialMobilityAnalysis` values and
`MetricComputationInputs.social_mobility_analysis` drives eight
`MetricDocument` outputs.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/analysis/inequality_indices.py` | `inequality_distribution_summary` (194-247), `quantized_gini` (137-143) | Quantized-output convention; social mobility adds its own rank statistics rather than changing these |
| `src/analysis/economic_inequality_detection.py` | `_latest_by_owner` (122-132), `detect_economic_inequality_rows` (157-322), `EconomicDetectionResult` (96-119) | Window-vector and availability pattern |
| `src/analysis/economic_inequality_comparisons.py` | `_latest_values` (95-111), `compare_economic_inequality_strata` (118-294) | Stratum comparison shape without ranking |
| `src/analysis/economic_inequality_analysis.py` | `_cap_rows` (174-184), `harvest_economic_inequality_analysis` (212-498), digest (187-209) | Deterministic caps, notices, coverage composition, canonical digest |
| `src/analysis/economic_inequality_metrics.py` | `_document` (90-142), `_compute_dimension` (191-251), eight compute functions (254-544) | Metric document mapping and unknown-state handling |
| `src/analysis/specifications.py` | `MetricFamilyId` (75-309), `ECONOMIC_INEQUALITY_*_KEYS` (9090-9132), `_economic_inequality_spec` (9628-9665), `_BUILDERS` (10272-10279), `METRIC_FAMILY_COUNT` (53) | Exact append points and locked-case builder |
| `src/analysis/metric_service.py` | `MetricComputationInputs` (293-443), economic emission block (2701-2753) | New input field and emission block |
| `src/analysis/models.py` | `MetricAvailability` (508-514), `MetricCoverage` (517-547), `MetricDocument` (584-605) | Output contract |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/analysis/social_mobility_detection.py` | create | Pair resolution, quantile bins, shares, rank correlation |
| `src/analysis/social_mobility_generations.py` | create | Per-generation and per-lag comparison rows |
| `src/analysis/social_mobility_analysis.py` | create | Bounded `SocialMobilityAnalysis` and digest |
| `src/analysis/social_mobility_metrics.py` | create | Eight metric-document compute functions |
| `src/analysis/social_mobility_rows.py` | modify | Add `SocialMobilityLagRow` |
| `src/analysis/specifications.py` | modify | Eight enum members, three key tuples, `_social_mobility_spec`, eight `_spec_*`, builder append, count 236 |
| `src/analysis/metric_service.py` | modify | Input field, imports, emission block, `catalog=236` log |
| `src/analysis/__init__.py` | modify | Export detection/generation/analysis/metric symbols |
| `tests/unit/test_social_mobility_detection.py` | create | Pair/bin/share/correlation cases |
| `tests/unit/test_social_mobility_detection_properties.py` | create | Hypothesis invariants |
| `tests/unit/test_social_mobility_generations.py` | create | Generation and lag strata |
| `tests/unit/test_social_mobility_analysis.py` | create | Caps, coverage, notices, digest |
| `tests/unit/test_social_mobility_bounds.py` | create | Independent cap assertions |
| `tests/unit/test_social_mobility_metrics.py` | create | Eight documents and state mapping |
| `tests/unit/test_social_mobility_catalog.py` | create | 228→236 append discipline |
| `tests/unit/test_metric_specifications.py` | modify | Family count 228→236 |

## Task 5: Compute quantized mobility and persistence statistics

### Intent
Define the one statistical procedure that turns ancestor/descendant quantities
into rank bins, persistence, and mobility shares, so every domain and lag uses
identical arithmetic and there is no room for a class-like label.

### Implementation Steps
1. Create `src/analysis/social_mobility_detection.py`:
   - `SocialMobilityDetectionResult` dataclass: `pair_rows`, `domain_rows`,
     `notices`, `coverage`, `window_count`, `resolved_pair_count`.
   - `detect_social_mobility_rows(*, genealogy, outcomes, policy=None)`.
2. Build pair candidates from lineage evidence, not only direct edges:
   - Index `outcomes.rows` by `(domain, owner_token, window_index)`.
   - For each `genealogy.lineages` entry (ancestor token, descendant token,
     `generation_lag` in `1..policy.max_generation_lag`), and for each window
     `w` in ascending order and each domain:
     ancestor quantity = latest row for `ancestor_token` with
     `window_index <= w`; descendant quantity = latest row for
     `descendant_token` with `window_index <= w`.
   - Emit one `SocialMobilityPairRow` per
     `(window, domain, ancestor_token, descendant_token)` with the lag and both
     generations; `resolved=True` only when both sides exist, otherwise
     `resolved=False` with zero quantities and bin `-1`.
   - A lag-2+ pair is a genuine ancestor/descendant pair from the depth-bounded
     chain, not a chained recomputation of lag-1 rows.
3. Cap pair rows per `(window_index, domain)` group after sorting by
   `(window_index, domain.value, ancestor_token, descendant_token)`; keep the
   deterministic prefix within each group so the latest window survives a
   global overflow. Append one `social_mobility_pairs_truncated` notice per
   truncated group (deduplicated in the analysis notice list) and set coverage
   `partial`. Cap the window set to `policy.max_windows`, keeping the newest
   windows.
4. For each `(window, domain)` group with resolved pairs:
   - If `resolved < policy.min_mobility_pairs`: emit
     `SocialMobilityDomainRow` with `availability=insufficient_samples`,
     `persistence_direction=insufficient_samples`, zeroed indices, counts
     retained.
   - Else compute bins: sort resolved pairs by `(quantity, pair_token)` for the
     ancestor vector and independently for the descendant vector; assign
     `bin = min(rank_bins - 1, (position * rank_bins) // resolved)`. Pair rows
     carry both bins.
   - `same_bin_share_milli`, `upward_share_milli`, `downward_share_milli` are
     `round(1000 * count / resolved)`.
   - `mean_absolute_rank_change_milli = round(1000 * mean(|Δbin|) /
     (rank_bins - 1))`, clamped 0..1000.
   - `rank_correlation_milli` = quantized Spearman over the raw quantities.
     Implement `spearman_rank_correlation_milli(ancestor, descendant)` with
     average ranks for ties, the integer Pearson-on-ranks formula, and
     `Decimal(str(x)).quantize(Decimal("1"), ROUND_HALF_UP)`; clamp to
     `[-1000, 1000]` and normalize `-0` to `0`.
   - All-zero/all-equal special case: when both vectors have zero variance,
     every pair takes bin 0, `same_bin_share_milli=1000`, upward/downward `0`,
     `rank_correlation_milli=0`.
   - `persistence_direction = persistent` when
     `same_bin_share_milli >= policy.persistence_share_milli`, else `mobile`.
   - `coverage=complete` when all pairs resolved and no truncation, else
     `partial`.
5. Emit at most `policy.max_domain_rows` domain rows, sorted by
   `(window_index, domain.value)`.
6. Empty evidence returns an empty result with `coverage=missing`.

### Required Interfaces and Contracts
- `spearman_rank_correlation_milli(ancestor: Sequence[int],
  descendant: Sequence[int]) -> int` is public and pure.
- Bins are statistical rank positions, never stored as a label; the snapshot
  schema does not expose bin names.
- No domain row may contain a forbidden key or a raw owner id.
- Windows with zero pairs emit no row; absence is `unavailable` downstream.

### Requirement Evidence
- Original Request "Detect mobility and persistence analytically" and
  "Do not encode social classes".
- `src/analysis/inequality_indices.py` quantization precedent.

### Error Handling and Logging
- DEBUG window/domain vector counts.
- INFO `social_mobility_detection_complete windows=<n> rows=<n>`.
- WARN `social_mobility_insufficient_samples` and
  `social_mobility_out_of_range` counts; terminate on non-finite input with
  ERROR `social_mobility_nonfinite_input`.
- Never log quantities, tokens, or bins.

### Tests
- `tests/unit/test_social_mobility_detection.py`: 4-pair threshold boundary,
  perfect persistence, perfect reversal, tie handling, all-zero, unresolved
  pair, lag-2 pair generation from lineage chains, per-group truncation that
  preserves the latest window, `-0` normalization.
- `tests/unit/test_social_mobility_detection_properties.py`: Hypothesis for
  shares summing to ≤1000, index ranges, bin range, monotone prefix stability.

### Acceptance Criteria
- Statistics are deterministic across hash seeds.
- Fewer than 8 resolved pairs yields `insufficient_samples` with counts only.
- No label outside `persistent|mobile|insufficient_samples|unavailable` exists.
- Lag-2+ pairs come from lineage chains and carry their true lag.
- A global pair overflow never drops the newest window.

### Verification
- `uv run pytest tests/unit/test_social_mobility_detection.py tests/unit/test_social_mobility_detection_properties.py -q`
- Expected result: pass.

## Task 6: Compose generation and generation-lag rows

### Intent
Support many-generation studies by reporting outcomes per descendant
generation and by ancestor distance (lag 1..4), without ranking generations or
implying inherited advantage.

### Implementation Steps
1. Add `SocialMobilityLagRow(window_index, window_tick, generation_lag,
   pair_count, comparable, same_bin_share_milli, upward_share_milli,
   downward_share_milli, coverage, availability)` to
   `src/analysis/social_mobility_rows.py`.
2. Create `src/analysis/social_mobility_generations.py`:
   - `SocialMobilityGenerationResult` dataclass with `generation_rows`,
     `lag_rows`, `notices`, `coverage`, `comparable_generation_count`,
     `comparable_lag_count`.
   - `compare_social_mobility_generations(*, genealogy, outcomes, pair_rows,
     policy=None)`.
3. Generation rows: group resolved pair rows by
   `(window_index, descendant_generation)`; compute owner count from outcomes,
   pair count, and the same bin-share arithmetic restricted to that generation.
   Emit `availability=insufficient_samples` below `min_mobility_pairs`.
4. Lag rows: for lag `L` in `1..policy.max_generation_lag`, select pair rows
   whose `generation_lag == L` (already emitted by Task 5 from the lineage
   chains) and recompute bins and shares within that lag sample. Do not
   rebuild chains or derive a lag by chaining lag-1 rows. Emit one row per
   `(window, lag)`.
5. Cap generation rows at `policy.max_generation_rows` and lag rows at
   `policy.max_generation_lag * max_windows`, sorted deterministically; append
   `social_mobility_generations_truncated` / `social_mobility_lags_truncated`
   notices.
6. Missing generation membership drops the pair from generation/lag grouping
   only; it is never fabricated.

### Required Interfaces and Contracts
- `comparable` is true only when `pair_count >= min_mobility_pairs`.
- No best/worst, high/low, elite, or advantaged vocabulary exists.
- Generation index is bounded by `policy.max_generation_index`; out-of-range
  rows are excluded with one notice.

### Requirement Evidence
- Original Request "Support many-generation studies".
- `src/world/events.py:AgentCreated.generation_index` and
  `src/analysis/economic_inequality_comparisons.py:compare_economic_inequality_strata`
  (cohort comparison precedent).

### Error Handling and Logging
- DEBUG generation/lag counts and comparable strata.
- WARN `social_mobility_insufficient_generations`,
  `social_mobility_generation_out_of_range`.
- INFO `social_mobility_generations_complete`.

### Tests
- `tests/unit/test_social_mobility_generations.py`: 3-generation fixture,
  lag-1 vs lag-2 difference, insufficient generation, out-of-range generation,
  deterministic ordering.

### Acceptance Criteria
- Lag 1..4 rows exist only when their pair threshold is met.
- Generation rows never rank or label generations.
- Many-generation fixture with 4 generations yields lag 3 evidence.

### Verification
- `uv run pytest tests/unit/test_social_mobility_generations.py -q`
- Expected result: pass.

## Task 7: Compose the bounded `SocialMobilityAnalysis` harvest

### Intent
Create the single immutable analysis value that the metric service, snapshot
composer, and publication bridge consume, with independent caps and an explicit
coverage story.

### Implementation Steps
1. Create `src/analysis/social_mobility_analysis.py`:
   - `SocialMobilityAnalysis` frozen dataclass: `policy_version`,
     `window_tick`, `window_count`, `coverage`, `evidence_coverage`,
     `domain_coverage`, `generation_coverage`, `domain_rows`,
     `generation_rows`, `lag_rows`, `coverage_row`, `layers`, `notices`,
     `owner_count`, `generation_count`, `genealogy_edge_count`,
     `pair_count`, `resolved_pair_count`, `unresolved_pair_count`,
     `domain_available_count`; properties `row_count`, `source_layers`.
   - `empty_social_mobility_analysis()` with `missing` coverage and empty rows.
   - `social_mobility_analysis_digest(analysis)` — SHA-256 over policy version,
     window bounds, coverage tokens, row counts, and notices only.
   - `harvest_social_mobility_analysis(*, genealogy, outcomes, policy=None,
     window_end=None)`:
     1. Empty genealogy or empty outcomes → empty analysis (not zeros).
     2. Apply `with_window_end` and filter rows to `window_end`.
     3. Cap owners by sorted owner token, then pairs, domain rows, generation
        rows, lag rows, coverage rows; each cap appends one bounded notice and
        sets `partial`.
     4. Run Task 5 detection and Task 6 generation comparison on the capped
        evidence.
     5. Compose a single `SocialMobilityCoverageRow` for the latest window.
     6. Call `assert_social_mobility_layer_separation` over objective rows,
        owner rows, and analytical rows.
     7. Merge and deduplicate notices, truncate to `max_notices`, and derive
        `coverage`/`evidence_coverage`/`domain_coverage`/`generation_coverage`
        from child coverage plus truncation.
2. Export from `src/analysis/__init__.py`.

### Required Interfaces and Contracts
- `harvest_social_mobility_analysis` is pure and deterministic.
- `coverage=missing` never coexists with non-empty rows.
- `window_tick` is the highest window tick present in surviving rows.
- No metric or snapshot reads a private analysis helper.

### Requirement Evidence
- `.ai-factory/ARCHITECTURE.md` Key Principle 4 (optional channels leave off-path
  behavior unchanged) and analysis isolation rules.
- `src/analysis/economic_inequality_analysis.py` cap/notice/coverage template.

### Error Handling and Logging
- DEBUG counts per layer and family.
- INFO `social_mobility_analysis_complete windows=<n> rows=<n>`.
- WARN `social_mobility_truncated`, `social_mobility_partial_coverage`.
- ERROR `social_mobility_analysis_invalid` with a code only.

### Tests
- `tests/unit/test_social_mobility_analysis.py`: empty input, single pair,
  full evidence, cap per family, coverage composition, digest stability.
- `tests/unit/test_social_mobility_bounds.py`: each cap independently, prefix
  stability, notice bound.

### Acceptance Criteria
- Empty evidence yields empty analysis, no zero-filled domains.
- Every cap is independently enforced and reported once.
- Layer separation is asserted before the value is returned.

### Verification
- `uv run pytest tests/unit/test_social_mobility_analysis.py tests/unit/test_social_mobility_bounds.py -q`
- Expected result: pass.

## Task 8: Append eight metric families (228 → 236) and wire the service

### Intent
Expose mobility results through the existing closed metric catalog without
renaming, reordering, or re-versioning the first 228 families.

### Implementation Steps
1. In `src/analysis/specifications.py`, append after
   `ECONOMIC_INEQUALITY_SOCIETY_COMPARISON`:
   `RESOURCE_MOBILITY`, `SKILL_MOBILITY`, `SOCIAL_INFLUENCE_MOBILITY`,
   `ORGANIZATION_ROLE_MOBILITY`, `EDUCATIONAL_ACCESS_MOBILITY`,
   `PRODUCTIVE_ASSET_MOBILITY`, `SOCIAL_MOBILITY_GENERATION_LAG`,
   `SOCIAL_MOBILITY_COVERAGE` with lower-snake string values.
2. Add key tuples before `_trade_spec`:
   - `SOCIAL_MOBILITY_DOMAIN_KEYS` =
     `("social_mobility_window_tick", "window_count", "pair_count",
     "resolved_pair_count", "rank_correlation_milli",
     "same_bin_share_milli", "upward_share_milli", "downward_share_milli",
     "mean_absolute_rank_change_milli", "persistence_direction", "coverage",
     "availability")`.
   - `SOCIAL_MOBILITY_GENERATION_KEYS` =
     `("social_mobility_window_tick", "max_generation_lag",
     "lag1_pair_count", "lag1_same_bin_share_milli",
     "lag1_upward_share_milli", "lag1_downward_share_milli",
     "lag2_pair_count", "lag2_same_bin_share_milli",
     "lag2_upward_share_milli", "lag2_downward_share_milli",
     "lag3_pair_count", "lag3_same_bin_share_milli",
     "lag3_upward_share_milli", "lag3_downward_share_milli",
     "lag4_pair_count", "lag4_same_bin_share_milli",
     "lag4_upward_share_milli", "lag4_downward_share_milli",
     "coverage", "availability")`.
   - `SOCIAL_MOBILITY_COVERAGE_KEYS` =
     `("social_mobility_window_tick", "generation_count", "owner_count",
     "genealogy_edge_count", "pair_count", "resolved_pair_count",
     "unresolved_pair_count", "domain_available_count", "truncated", "coverage",
     "availability")`.
3. Add `_social_mobility_spec(*, family_id, population,
   denominator, denominator_kind, keys, opportunity, owner_claims=False)`
   mirroring `_economic_inequality_spec`, but with
   `cohort_window="social_mobility_window_tick"`, the same deceased/zero/self/
   censoring/empty/one/all-zero/unknown cases, and
   `availability_behavior="explicit_unknown_without_genealogy_or_outcome_evidence"`.
   `owner_claims=True` adds `EvidenceStage.AGENT_VISIBLE_PROJECTION` and
   `EvidenceStage.BELIEF_REVISION_TESTIMONY`; use it for
   `SOCIAL_INFLUENCE_MOBILITY`, `ORGANIZATION_ROLE_MOBILITY`, and
   `EDUCATIONAL_ACCESS_MOBILITY`.
4. Add eight `_spec_*` builders with explicit populations/denominators:
   - resource: `observed_owner_generations`, `resolved_parent_child_pairs`,
     `POPULATION_SIZE`, "observed resource items only; never legitimate
     inheritance".
   - skill: `owners_with_observed_practical_knowledge`,
     `resolved_parent_child_pairs`, "active owner-scoped techniques only; no
     capability truth".
   - influence: `owners_with_observed_inbound_communication`,
     `resolved_parent_child_pairs`, "distinct observed communication partners;
     never authority or status".
   - role: `owners_with_observed_organization_role_claims`,
     `resolved_parent_child_pairs`, "believed role assignments; never objective
     office truth".
   - education: `owners_with_observed_educational_receipts`,
     `resolved_parent_child_pairs`, "teaching and repository receipts; never
     guaranteed learning".
   - assets: `owners_with_observed_productive_assets`,
     `resolved_parent_child_pairs`, "additive observed physical-asset count; not
     wealth".
   - lags: `generation_lag_strata_with_resolved_pairs`,
     `comparable_lag_rows`, "per-lag descriptive persistence; no ranking".
   - coverage: `observed_owner_generations`, `resolved_parent_child_pairs`,
     "genealogy and outcome coverage only".
   All use `formulas={key: key.replace("_", " ") for key in keys}`.
5. Append the eight builders to `_BUILDERS` in position 228-235 and set
   `METRIC_FAMILY_COUNT = 236`.
6. Create `src/analysis/social_mobility_metrics.py`:
   - `_document(...)` copied in spirit from
     `economic_inequality_metrics._document`: `unknown` →
     `MetricAvailability.UNKNOWN` and empty payload; `present`/`partial` →
     `PRESENT`/`PARTIAL` with a coverage ratio.
   - `_compute_domain(analysis, domain, *, run_id, input_revision)` selects the
     latest domain row, maps `persistence_direction`, and builds values.
   - `compute_resource_mobility`, `compute_skill_mobility`,
     `compute_social_influence_mobility`, `compute_organization_role_mobility`,
     `compute_educational_access_mobility`, `compute_productive_asset_mobility`,
     `compute_social_mobility_generation_lag`, `compute_social_mobility_coverage`
     with signature `(analysis, *, run_id: str, input_revision: str) ->
     MetricDocument`.
7. In `src/analysis/metric_service.py`, add
   `social_mobility_analysis: SocialMobilityAnalysis | None = None` to
   `MetricComputationInputs`, import the eight compute functions, and add an
   emission block after the economic block:
   `if inputs.social_mobility_analysis is not None:` → eight `_safe(...)` calls
   → `_LOG.info("social_mobility_metrics_emitted families=8 catalog=236")`;
   `else:` → `_LOG.debug("social_mobility_metrics_disabled")`.
8. Update `tests/unit/test_metric_specifications.py` expectations to 236.

### Required Interfaces and Contracts
- The first 228 specifications keep ids, order, versions, value keys, and
  formulas byte-identically.
- Every new family has non-empty `formulas` and `evidence_inputs` or
  `MetricSpecification.__post_init__` rejects it.
- No family aggregates domains; each domain family reports one domain only.
- `social_mobility_window_tick` is the cohort window for all eight families.
- Unused lag keys (when `max_generation_lag < 4`) emit `0` counts and `0`
  shares; availability derives only from lags that are comparable.

### Requirement Evidence
- Original Request six outcome domains plus analytic persistence.
- `src/analysis/specifications.py:METRIC_FAMILY_COUNT` and
  `validate_metric_catalog` are the closed catalog gate.
- `.ai-factory/ARCHITECTURE.md` "Versioned Extension Contract" requirement 1
  (accepted-set and exact key-set evolution).

### Error Handling and Logging
- INFO `social_mobility_metrics_emitted families=8 catalog=236`.
- DEBUG `social_mobility_metrics_disabled` when the input is `None`.
- ERROR `social_mobility_metric_invalid` with a code only.

### Tests
- `tests/unit/test_social_mobility_metrics.py`: each family, unknown/absent
  mapping, partial coverage, forbidden keys rejected, latest-window selection.
- `tests/unit/test_social_mobility_catalog.py`: count 236,
  `_FIRST_228_DIGEST = "c8ac976ec9ae568d337835d4b0879850c4864040e4d338e663a3c13a83dc3dff"`,
  appended ids exactly in order, locked cases.
- `tests/unit/test_metric_specifications.py`: 236 families, unique ids.

### Acceptance Criteria
- `validate_metric_catalog()` passes with 236 families.
- The first 228 digest is unchanged.
- Eight metric documents are emitted when the analysis is present and none
  when it is `None`.

### Verification
- `uv run pytest tests/unit/test_social_mobility_metrics.py tests/unit/test_social_mobility_catalog.py tests/unit/test_metric_specifications.py -q`
- Expected result: pass.

## Phase Risks and Mitigations
- Risk: Spearman quantization drifts with float rounding.
  Mitigation: compute on integer ranks, quantize once with `Decimal`, and test
  exact reversal/perfect persistence cases.
- Risk: additive `productive_assets` is read as a composite score.
  Mitigation: documented opportunity text, no cross-domain family, and a
  leakage test that rejects `score`/`wealth` keys.
- Risk: catalog append reorders existing families.
  Mitigation: first-228 digest test and builder-position test.

## Phase Completion Checklist
- Every Task in this phase satisfies its acceptance criteria.
- `uv run pytest tests/unit/test_social_mobility_*.py tests/unit/test_metric_specifications.py -q` passes.
- `index.md` Task 5-8 checkboxes are updated after verification.
