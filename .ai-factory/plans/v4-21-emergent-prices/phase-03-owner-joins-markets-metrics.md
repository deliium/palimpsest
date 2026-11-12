# Phase 3: Owner Joins, Market Distributions, Metrics, and Pins

Plan: [index.md](index.md)
Tasks: 8-12
Depends on: Phase 2 / Tasks 5-7

## Objective

Join detached owner expectations and V3-19 unit evidence to the analytical
distributions, lift venue distributions to market distributions through detached
V4-20 memberships, compose one bounded `EmergentPricesAnalysis`, append four
metric families (208 → 212), and sweep every catalog/ownership pin.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/analysis/market_institutions_expectations.py` | 50-59, 123-395 | Owner-input join, alignment, coverage, cap/notice pattern |
| `src/analysis/market_institutions_analysis.py` | 64-150, 172-293 | Harvest dataclass, pipeline, digest pattern |
| `src/analysis/market_institutions_layers.py` | 26-72 | Four-layer projection and separation |
| `src/analysis/market_institutions_metrics.py` | 1-120, 401-422 | Metric document construction and four-family assembly |
| `src/analysis/specifications.py` | `MetricFamilyId` 75-285, keys 8869-8917, `_market_spec` 9113-9141, builders 9480-9690 | Catalog registration order and value-key convention |
| `src/analysis/metric_service.py` | `MetricComputationInputs` 261-389, emission 2549-2577 | Input field and emission convention |
| `src/experiments/market_institutions_completed_run.py` | 28-109 | Detached owner export → analysis pattern |
| `src/simulation/market_institutions_export.py` | 56-232 | Token-only owner export pattern |
| `src/analysis/supply_chain_metrics.py` | 1 | Confirms catalog 198 → 204 before V4-20; V4-20 204 → 208 |
| `src/analysis/specifications.py` | `METRIC_FAMILY_COUNT` 53 | Single catalog count source to raise to 212 |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/analysis/emergent_prices_rows.py` | modify | Owner expectation/quote/unit rows, market membership input, market row |
| `src/analysis/emergent_prices_expectations.py` | create | Owner joins, alignment, coverage |
| `src/analysis/emergent_prices_markets.py` | create | Membership join, market distributions, market-level relations |
| `src/analysis/emergent_prices_analysis.py` | create | Harvest composition and digest |
| `src/analysis/emergent_prices_layers.py` | create | Four-layer projection |
| `src/analysis/emergent_prices_metrics.py` | create | Four metric calculators and assembly |
| `src/analysis/specifications.py` | modify | Four `MetricFamilyId` members, keys, `_price_spec`, builders, count 212 |
| `src/analysis/metric_service.py` | modify | Input field and emission block |
| `src/analysis/__init__.py` | modify | Public exports |
| `src/simulation/emergent_prices_export.py` | modify | Expose owner inputs for composition |
| `tests/unit/test_*_catalog.py`, `tests/architecture/test_*_boundaries.py` | modify | Sweep current-state 208 → 212 (docs in Task 24) |

## Task 8: Join detached expectations, quotes, and reference-unit alignment

### Intent

Attach owner beliefs to the objective distributions without letting owner rows
create, change, or dominate a distribution. Alignment is researcher-only and
never returns to cognition.

### Implementation Steps

1. Extend `emergent_prices_rows.py` with:
   - `PriceOwnerExpectationInput(owner_token, window_index, item_kind,
     unit_kind, unit_source, expected_ratio_milli, confidence_milli, level,
     valuation_reservation, observation_count, quote_count, first_tick,
     last_tick, coverage)`;
   - `PriceOwnerQuoteInput(owner_token, venue_id, window_index, item_kind,
     unit_kind, direction, ratio_milli, confidence_milli, source, source_tick,
     first_tick, last_tick, coverage)`;
   - `OwnerPriceExpectationRow(expectation_id, window_index, owner_token,
     item_kind, unit_kind, unit_source, expected_ratio_milli, confidence_milli,
     level, valuation_reservation, observation_count, quote_count,
     distribution_source, alignment, coverage)`;
   - `OwnerPriceQuoteRow(quote_id, window_index, venue_id, actor_token,
     counterparty_token, item_kind, unit_kind, direction, ratio_milli,
     confidence_milli, source, source_tick, coverage)`;
   - `PriceUnitRow(unit_token, unit_kind, unit_source, owner_count,
     expectation_count, distribution_count, median_confidence_milli,
     unit_alignment, coverage)`.
2. Create `emergent_prices_expectations.py` with
   `join_price_expectations(inputs, distributions, *, policy)`.
3. For each owner expectation input, find candidate distributions matching
   `(window_index, item_kind, unit_kind)` across venues and unit sources. Prefer
   `sample_source="completed"`; use `"quoted"` only when no completed candidate
   exists. Within the chosen source, choose the candidate with the largest
   `sample_count`, then the lexicographically smallest `venue_id`; mark
   `coverage="partial"` when more than one candidate matches. Record the chosen
   source in `distribution_source` (`completed`, `quoted`, or `none`).
   Unit-source agreement is reported separately by the unit summary, not used to
   suppress the comparison. When no candidate matches, keep the owner row with
   `alignment="not_applicable"` and `distribution_source="none"`.
4. Compute alignment with the distribution median:
   `gap = abs(expected - median) * 1000 // max(1, max(expected, median))`;
   `consistent` when `gap <= alignment_low_milli`; `inconsistent` when
   `gap >= alignment_high_milli`; otherwise `unresolved`; `not_applicable` when
   no distribution exists. Alignment is stored only in this analysis row.
5. `join_price_quotes(inputs, *, policy)`: emit `OwnerPriceQuoteRow` per input,
   canonical order `(window_index, venue_id, actor_token, item_kind.value,
   unit_kind.value, direction.value, ratio_milli)`; cap at
   `max_owner_quote_rows`.
6. `summarize_price_units(expectations, quotes, distributions, *, policy)`:
   group by `(unit_kind, unit_source)`; `unit_token` is the kind token or
   `none`; unit alignment is `consistent` when the same `unit_kind` appears in an
   `exchange_counterpart` distribution, `inconsistent` when distributions exist
   for the item kind but no distribution uses that unit, `unresolved` when no
   distribution exists at all, and `not_applicable` for `unknown`.
7. When `expectation_inputs` is empty: return no expectation rows, no quote
   rows, `expectation_coverage="missing"`, `quote_coverage="missing"`, and one
   `price_owner_rows_missing` notice. Never invent a row.
8. Caps: `max_expectation_rows`, `max_owner_quote_rows`, `max_owners`,
   `max_units`; truncate deterministically and append one notice each.

### Required Interfaces and Contracts

- Owner tokens are opaque strings; no agent id, ledger id, or counterparty id is
  emitted.
- Owner inputs never override `sample_count`, quantiles, or market membership.
- `alignment` is researcher-only and never appears in cognition, prompts,
  memory, world state, observer semantics, or stop selectors.
- Missing input is `missing`, not `complete` with zeros.

### Requirement Evidence

- User request: represent "agent valuation, observed past exchanges, quoted
  offers, reference units, confidence".
- Join/alignment/coverage pattern: `market_institutions_expectations.py:50-395`.
- Owner export token-only pattern: `market_institutions_export.py:56-232`.

### Error Handling and Logging

- Malformed owner rows are rejected with `price_analysis_invalid_row`; a foreign
  owner token is a malformed row.
- `DEBUG price_owner_join expectations=<n> quotes=<n> coverage=<token>` only.
- Never log owner tokens, item kinds, units, ratios, or alignments.

### Tests

- `tests/unit/test_emergent_prices_expectations.py`: consistent/unresolved/
  inconsistent/not_applicable; completed preferred over quoted with
  `distribution_source` recorded; missing inputs; unit alignment for each source;
  cap truncation; owner rows never change distributions.
- `tests/unit/test_emergent_prices_leakage.py`: analysis rows expose no agent id,
  ledger id, item id, counterparty id, valuation component, or raw quote.

### Acceptance Criteria

- Alignment is computed only from detached rows.
- A run with no exported owner ledgers yields objective distributions and
  `missing` owner coverage, with no fabricated expectation rows.

### Verification

- `uv run pytest tests/unit/test_emergent_prices_expectations.py tests/unit/test_emergent_prices_leakage.py -q`
- Expected: all pass.

## Task 9: Join market memberships and lift distributions to markets

### Intent

Measure convergence and divergence between markets, not just venues, while
keeping market identity owned by the V4-20 analysis and never minting or
changing it here.

### Implementation Steps

1. Add `PriceMarketMembershipInput(market_token, venue_id, window_index,
   coverage)` to `emergent_prices_rows.py`. Require `market_token` to match
   `^mktc-[0-9a-f]{16}$` or be `none`; `venue_id` must match
   `^mkt-ven-[0-9a-f]{16}$`.
2. Create `emergent_prices_markets.py` with
   `join_market_memberships(memberships, evidence, venue_distributions, *,
   policy) -> PriceMarketJoin`.
3. `PriceMarketJoin` fields: `distributions`, `markets`, `relations`,
   `market_coverage`, `relation_coverage`, `notices`.
4. Validate memberships: no duplicate `(market_token, venue_id, window_index)`;
   a venue may appear in at most one market per window (V4-20 candidates are
   window components). A conflict skips the later row and appends
   `price_market_membership_conflict`.
5. Regroup paired evidence rows by `(window, market_token, item_kind, unit_kind,
   unit_source, sample_source)` and recompute quantiles and five bin shares from
   raw ratios. Do not average venue quantiles or pool completed and quoted
   samples.
6. Emit `PriceDistributionRow` with `venue_id="none"`,
   `market_token=<token>`, and the recomputed `bin_shares_milli` for market-level
   rows, using the same quantile and bin function as Task 7.
7. Emit `PriceMarketRow` per market/window with venue, distribution, sample,
   item-kind, and unit counts and `coverage`.
8. Run `detect_price_relations` on the market distributions; ids use the
   contract relation helper and canonical pair order.
9. When memberships are absent or empty: no market rows, no market-level
   relations, `market_coverage="missing"`, and one
   `price_market_membership_missing` notice. Venue distributions remain valid.
10. Cap markets at `max_market_rows` and relations at `max_relation_rows`;
    deterministic order.

### Required Interfaces and Contracts

- V4-21 mints no `mktc-` or `mkt-ven-` id and never changes V4-20 identity.
- A market distribution may aggregate multiple venues but remains a distribution
  with sample count, quantiles, and five bin shares, never a single market price.
  Completed and quoted distributions remain separate.
- Convergence uses the same overlap coefficient and thresholds as Task 7.
- `PriceRelation` rows record `sample_a`/`sample_b`; insufficient samples are
  explicit.

### Requirement Evidence

- User request: "Measure convergence/divergence between markets".
- V4-20 market identity: `analysis/market_institutions_identity.py:38-98`,
  `market_institutions_detection.py:273-365`.
- Detached composition boundary: `.ai-factory/ARCHITECTURE.md` V4-20 seam.

### Error Handling and Logging

- Invalid market/venue token, duplicate membership, or cross-window membership
  fails closed with `price_analysis_invalid_row`; a venue conflict is skipped
  with one notice.
- `WARN price_market_membership_conflict count=<n>`;
  `DEBUG price_markets_joined markets=<n> relations=<n>`.
- Never log market tokens, venue ids, item kinds, units, or ratios.

### Tests

- `tests/unit/test_emergent_prices_markets.py`: two venues → one market; two
  markets compared; duplicate/conflicting membership; absent membership; market
  quantiles and bin shares recomputed from raw samples; completed and quoted
  market distributions stay separate; no V4-20 id mutation.
- `tests/unit/test_emergent_prices_market_relations.py`: cross-market converged,
  partial, divergent, and insufficient cases; deterministic ordering.

### Acceptance Criteria

- Market rows never exist without membership evidence.
- Market-level convergence is computed from distributions, not from owner
  expectations.
- No global market registry or price table is created.

### Verification

- `uv run pytest tests/unit/test_emergent_prices_markets.py tests/unit/test_emergent_prices_market_relations.py -q`
- Expected: all pass.

## Task 10: Compose the bounded `EmergentPricesAnalysis` harvest

### Intent

Provide one deterministic entry point that composes evidence, venue and market
distributions, owner joins, and relations with explicit coverage.

### Implementation Steps

1. Create `emergent_prices_analysis.py` with
   `EmergentPricesAnalysis(window_tick, policy_version, evidence_coverage,
   expectation_coverage, quote_coverage, distribution_coverage,
   market_coverage, relation_coverage, coverage, units, expectations, quotes,
   distributions, markets, relations, notices, exchange_count, quote_count)`.
2. Add `empty_emergent_prices_analysis()`.
3. Add `harvest_emergent_prices_analysis(*, committed_events,
   expectation_inputs=(), quote_inputs=(), membership_inputs=(), policy=None,
   window_end=None)`:
   - extract evidence;
   - detect venue distributions;
   - join memberships and market distributions;
   - join owner expectations/quotes and unit summaries;
   - run relations on market distributions when memberships exist, otherwise on
     venue distributions with `relation_coverage="partial"`;
   - derive overall coverage: `missing` when no exchange evidence,
     `partial` when any family is partial/missing, else `complete`.
4. Add `emergent_prices_analysis_digest(analysis)` using the canonical
   `analysis.models` JSON encoder conventions.
5. Create `emergent_prices_layers.py` with `PriceLayerView` and
   `project_price_layers(analysis)` returning objective exchange,
   owner expectation, analytical distribution, and comparison view groups.
6. Reject any layer field whose name is in `PRICE_FORBIDDEN_KEYS` or starts with
   a forbidden prefix.

### Required Interfaces and Contracts

- `window_end` is inclusive; a window index beyond `max_windows` fails closed.
- `committed_events` is an iterable of committed event objects; no store or
  runtime is accepted.
- The harvest never mutates inputs and returns only frozen values.
- `coverage` is derived from family coverages, never hard-coded.

### Requirement Evidence

- Harvest/composition pattern: `market_institutions_analysis.py:64-293`.
- Four-layer separation: `market_institutions_contract.py:59-117`,
  `market_institutions_layers.py:26-72`.

### Error Handling and Logging

- Invalid analysis object/type raises `price_analysis_invalid_row`.
- `INFO price_analysis_harvested distributions=<n> markets=<n> relations=<n>
  coverage=<token>`.
- Never log any row content.

### Tests

- `tests/unit/test_emergent_prices_analysis.py`: empty events → missing; venues
  only → partial; venues + memberships + owner rows → complete; digest stable;
  layer separation; window bound rejection.
- `tests/unit/test_emergent_prices_analysis_determinism.py`: shuffled inputs
  produce identical analysis bytes and digest.

### Acceptance Criteria

- One call produces the complete analysis object used by metrics and
  publication.
- Coverage is explicit and truthful at family and overall levels.

### Verification

- `uv run pytest tests/unit/test_emergent_prices_analysis.py tests/unit/test_emergent_prices_analysis_determinism.py -q`
- Expected: all pass.

## Task 11: Append four price metric families to 212

### Intent

Expose distributions, dispersion, unit alignment, and convergence as four
detached families in catalog order without changing any earlier family.

### Implementation Steps

1. `specifications.py`: append `MetricFamilyId` members in this exact order:
   `PRICE_EXPECTATION_STRUCTURE`, `PRICE_DISTRIBUTION_DISPERSION`,
   `PRICE_REFERENCE_UNIT_ALIGNMENT`, `MARKET_PRICE_CONVERGENCE`.
2. Add key tuples immediately after `MARKET_ROLE_STRUCTURE_KEYS`:
   - `PRICE_EXPECTATION_STRUCTURE_KEYS = ("window_tick",
     "expectation_row_count", "strong_count", "expected_count", "weak_count",
     "valuation_row_count", "mean_confidence_milli", "expectation_coverage")`;
   - `PRICE_DISTRIBUTION_DISPERSION_KEYS = ("window_tick",
     "distribution_count", "completed_distribution_count",
     "quoted_distribution_count", "available_count", "insufficient_count",
     "mean_iqr_milli", "mean_dispersion_milli", "item_kind_count",
     "unit_count", "distribution_coverage")`;
   - `PRICE_REFERENCE_UNIT_ALIGNMENT_KEYS = ("window_tick", "unit_row_count",
     "owner_reference_count", "observed_medium_count",
     "exchange_counterpart_count", "quoted_count", "consistent_count",
     "unresolved_count", "inconsistent_count", "unit_coverage")`;
   - `MARKET_PRICE_CONVERGENCE_KEYS = ("window_tick", "relation_count",
     "converged_count", "partially_converged_count", "divergent_count",
     "insufficient_count", "mean_overlap_milli", "market_pair_count",
     "relation_coverage")`.
3. Add `_price_spec(...)` with required `family_id`, `population`,
   `denominator`, `denominator_kind`, `keys`, and `opportunity`, plus
   `evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE})` (matching
   the existing owner-analysis market families, because the closed
   `EvidenceStage` taxonomy has no separate subjective-export member),
   `cohort_window="emergent_prices_window_tick"`,
   `censoring_policy="insufficient samples remain explicit"`,
   `empty_case="unavailable_unknown"`, `availability_behavior=
   "explicit_unknown_without_exchange_evidence"`.
4. Add four builder functions and append them at the end of `_BUILDERS` after the
   market builders, with these exact population/denominator/kind triples:
   - expectation: `owner_scoped_price_expectations` /
     `observed_expectation_rows` / `DenominatorKind.EVALUABLE_CLAIMS`;
   - dispersion: `analytical_price_distributions` /
     `observed_distribution_samples` / `DenominatorKind.ACTIVE_EDGES`;
   - unit alignment: `owner_scoped_price_units` / `observed_unit_rows` /
     `DenominatorKind.EVALUABLE_CLAIMS`;
   - convergence: `analytical_price_relations` / `observed_relation_pairs` /
     `DenominatorKind.ACTIVE_EDGES`.
5. Before changing any specification, compute and pin
   `_BASELINE_208_DIGEST` over the pre-change `specs[:208]` using the existing
   `test_market_institutions_catalog.py` material convention. Keep the existing
   `_BASELINE_DIGEST` over `specs[:204]` unchanged.
6. Set `METRIC_FAMILY_COUNT: Final[int] = 212`.
7. Create `emergent_prices_metrics.py` with `compute_price_expectation_structure`,
   `compute_price_distribution_dispersion`,
   `compute_price_reference_unit_alignment`, `compute_market_price_convergence`,
   and `assemble_emergent_price_metrics` returning families in catalog order.
   Dispersion counts `completed` and `quoted` distributions separately;
   convergence consumes only relations that already matched `sample_source`.
8. Use the existing `_document`/`MetricDocument` conventions from
   `market_institutions_metrics.py:83-120`: unknown state emits an empty payload
   and `MetricAvailability.UNKNOWN`; forbidden fields raise
   `price_analysis_forbidden_key`.
9. `metric_service.py`: add
   `emergent_prices_analysis: EmergentPricesAnalysis | None = None` to
   `MetricComputationInputs`, import the four calculators, and emit them in a new
   block after market institutions with
   `INFO emergent_prices_metrics_emitted families=4 catalog=212`.

### Required Interfaces and Contracts

- The first 208 family ids, order, algorithm versions, and value keys are
  unchanged.
- Every new family's `value_keys` exactly equals its key tuple; no `price` key.
- Metric values are counts and integer milli ratios only.
- No composite price, convergence score, ranking, severity, or recommendation.

### Requirement Evidence

- User request: "Support analytical price distributions rather than one
  canonical price"; "Measure convergence/divergence between markets".
- Catalog conventions: `specifications.py:359-435,573-652,8869-8917,9113-9141`;
  `market_institutions_metrics.py:83-120,401-422`.

### Error Handling and Logging

- A calculator failure is isolated by the existing `_safe` wrapper in
  `metric_service.py`; it emits an unknown document, never a partial value.
- `INFO emergent_prices_metrics_emitted families=4 catalog=212`; per-family
  DEBUG counts only.
- Never log metric row contents or item/unit tokens.

### Tests

- `tests/unit/test_emergent_prices_metrics.py`: each family's keys/order,
  unknown vs partial vs present, values, forbidden-key rejection.
- `tests/unit/test_emergent_prices_catalog.py`: `_BASELINE_208_DIGEST` over the
  first 208 specs unchanged; new ids appended at 209-212;
  `METRIC_FAMILY_COUNT == 212`; each new spec's `denominator_kind` matches the
  locked triple.
- `tests/unit/test_metric_specifications.py`: update the total pin.

### Acceptance Criteria

- Catalog validation passes with 212 unique families.
- Existing families are byte-identical to the pre-change baseline.
- Four families emit in deterministic catalog order.

### Verification

- `uv run pytest tests/unit/test_emergent_prices_metrics.py tests/unit/test_emergent_prices_catalog.py tests/unit/test_metric_specifications.py -q`
- Expected: all pass.

## Task 12: Sweep suite-wide ownership and catalog pins

### Intent

Remove every stale `208` expectation and any test that treats `markets_credit`
as unowned or V4-21 as unimplemented, without weakening unrelated gates.

### Implementation Steps

1. Replace literal `208` catalog pins with `212` in every unit, architecture,
   and docs test that asserts the current catalog; keep the historical
   `_BASELINE_DIGEST` over `specs[:204]` and the new `_BASELINE_208_DIGEST` over
   `specs[:208]` unchanged, and append a 209-212 slice assertion. At minimum
   update `test_market_institutions_catalog.py`,
   `test_market_institutions_pins.py`, `test_metric_specifications.py`,
   `test_supply_chain_pins.py`, `test_supply_chain_catalog.py`,
   `test_trade_networks_catalog.py`, and every
   `tests/architecture/test_*_boundaries.py` that imports
   `METRIC_FAMILY_COUNT`.
2. Rename stale test functions that still say `204`/`154` only when they assert
   the *current* count; do not rename historical regression tests that assert a
   preserved prefix.
3. Keep `V4_OWNED_CAPABILITY_FLAGS` at eight entries; assert `markets_credit`
   remains owned and that V4-21 adds no flag/context.
4. Keep the `runner-config-v57` guard test; add a guard that no
   `emergent_prices` module or test encodes a v57.
5. Update `tests/unit/test_market_institutions_pins.py` and
   `tests/unit/test_supply_chain_pins.py` stale-count scans so they scan for
   stale `== 208` and `== 204` current claims while allowing historical prose.
6. Leave documentation files and their parity tests to Task 23/Task 24; Task 12
   changes only code and current-state test pins.

### Required Interfaces and Contracts

- No test is skipped, xfailed, or deleted to make a lane pass.
- Historical counts in archived plan text and changelog-like prose stay intact.
- Every current-state pin names 212.

### Requirement Evidence

- Single count source: `specifications.py:53`.
- Existing sweep pattern: `tests/unit/test_market_institutions_pins.py:26-76`,
  `tests/unit/test_supply_chain_pins.py:27-68`.

### Error Handling and Logging

- Not applicable beyond test failure output; never suppress a failing pin.

### Tests

- `tests/unit/test_emergent_prices_pins.py`: owned flags eight, contexts
  fourteen, flags twelve, catalog 212, commands 43, semantics 73, replay v27 /
  codec v25, Alembic 0017.
- Run the full unit and architecture suites after the sweep.

### Acceptance Criteria

- No current-state test expects 208.
- No test expects `markets_credit` to be unowned.
- The catalog prefix digest and the 209-212 digest both pass.

### Verification

- `uv run pytest tests/unit tests/architecture -q`
- Expected: all pass.

## Phase Risks and Mitigations

- Risk: owner rows accidentally override distributions.
  Mitigation: joins are one-way; tests mutate owner rows and assert identical
  distributions.
- Risk: market membership double-counts a venue.
  Mitigation: one-market-per-venue-per-window validation with a bounded notice.
- Risk: pin sweep rewrites historical evidence.
  Mitigation: keep prefix digests and only change current-state assertions.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
