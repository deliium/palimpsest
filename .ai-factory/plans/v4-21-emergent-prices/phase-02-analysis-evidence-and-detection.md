# Phase 2: Analysis Evidence and Detection

Plan: [index.md](index.md)
Tasks: 5-7
Depends on: Phase 1 / Tasks 1-4

## Objective

Build the detached, bounded analysis contract and reconstruct exchange-implied
ratios, owner expectations, venue distributions, and cross-market
convergence/divergence from committed events and exported owner rows only. No
runtime, store, API object, `WorldState`, or peer ledger is read.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/analysis/exchange_functions.py` | module doc 1-43, `AcceptanceShareRow` 46-76, `classify_exchange_functions` 120-238 | V3-19 medium/quote evidence to build on; forbids money labels |
| `src/analysis/exchange_functions_metrics.py` | 29-73 | Existing three exchange-function families and censoring text |
| `src/world/events.py` | `ExchangeProposed` 2456-2482, `ExchangeWithdrawn` 2485-2511, `ExchangeCompleted` 2514-2564 | Only exchange primitives; client-kind tuples enable ratios |
| `src/world/events.py` | `OccurrenceContext` 344-390, `build_occurrence_context` 4327-4413 | Authoritative venue attribution |
| `src/analysis/market_institutions_events.py` | 54-153, 168-320 | Exact evidence-harvest pattern (rows, caps, digest) |
| `src/analysis/market_institutions_policy.py` | 27-166 | Caps and window helpers to mirror |
| `src/analysis/market_institutions_detection.py` | 76-490 | Detection and layer-separation pattern |
| `src/analysis/market_institutions_contract.py` | 45-245 | Tokens, enums, forbidden keys, errors |
| `src/analysis/trade_networks_policy.py` | 55-120 | Integer milli ratio conventions |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/analysis/emergent_prices_contract.py` | create | Tokens, enums, forbidden keys, errors, content-addressed ids |
| `src/analysis/emergent_prices_policy.py` | create | Locked caps/thresholds and window helpers |
| `src/analysis/emergent_prices_rows.py` | create | Evidence, expectation, quote, distribution, market, relation rows |
| `src/analysis/emergent_prices_events.py` | create | Bounded exchange/quote evidence harvest |
| `src/analysis/emergent_prices_detection.py` | create | Distributions, market aggregation, convergence/divergence |
| `src/analysis/__init__.py` | modify | Public exports |

## Task 5: Lock the `emergent-prices.v1` analysis contract and caps

### Intent

Fix detached vocabulary, identifiers, error codes, and caps before any detector
exists. Analysis ids are content-addressed and never depend on wall clock,
enumeration order, or Python `hash()`.

### Implementation Steps

1. Create `src/analysis/emergent_prices_contract.py` with
   `EMERGENT_PRICES_ANALYSIS_POLICY_VERSION = "emergent-prices.v1"`,
   `PRICE_EXPECTATION_PREFIX = "prce-"`,
   `PRICE_QUOTE_PREFIX = "prcq-"`,
   `PRICE_DISTRIBUTION_PREFIX = "prcd-"`,
   `PRICE_RELATION_PREFIX = "prcr-"`,
   `PRICE_MARKET_NONE_TOKEN = "none"`, `PRICE_ANALYSIS_HEX_LEN = 16`.
2. Add `PriceCoverage(StrEnum)` = `complete | partial | missing`.
3. Add `PriceLayer(StrEnum)` = `objective_exchange | owner_expectation |
   analytical_distribution | comparison_view`.
4. Add `PriceUnitSource(StrEnum)` = `owner_reference | observed_medium |
   exchange_counterpart | quoted | unknown` (must match the cognition enum
   values exactly; no cross-package import from `agents`).
5. Add `PriceQuoteDirection(StrEnum)` = `give_for_unit | unit_for_give`.
6. Add `PriceQuoteSource(StrEnum)` = `observed_offer | communicated |
   self_authored`.
7. Add `PricePairing(StrEnum)` = `paired | heterogeneous | same_kind |
   out_of_range`.
8. Add `PriceDistributionStatus(StrEnum)` = `available | insufficient_samples`
   and `PriceSampleSource(StrEnum)` = `completed | quoted`.
9. Add `PriceRelation(StrEnum)` = `converged | partially_converged | divergent |
   insufficient_evidence`.
10. Add `PriceAlignment(StrEnum)` = `consistent | unresolved | inconsistent |
    not_applicable`.
11. Add `PRICE_FORBIDDEN_KEYS` containing `price`, `canonical_price`,
    `price_index`, `clearing_price`, `rate`, `money`, `currency`, `numeraire`,
    `bid`, `ask`, `spread`, `fee`, `commission`, `tax`, `debt`, `credit_limit`,
    `market_score`, `ranking`, `severity`, `recommendation`, `allocation`,
    `quota`, `is_money`, `medium_of_exchange`, `store_of_value`,
    `unit_of_account`, `central_planner`.
12. Add `PRICE_LAYER_FORBIDDEN_PREFIXES` (for example `canonical_`, `global_`,
    `authoritative_`) used by `assert_price_layer_separation`.
13. Add `PRICE_ANALYSIS_ERROR_CODES` frozenset with exactly
    `price_analysis_invalid_policy`, `price_analysis_invalid_row`,
    `price_analysis_invalid_window`, `price_analysis_cap_exceeded`,
    `price_analysis_forbidden_key`, `price_analysis_layer_leak`,
    `price_analysis_missing_input`.
14. Add `EmergentPriceAnalysisError(ValueError)` with `reason_code` and
    `_fail(code)` logging `ERROR emergent_prices_analysis_invalid code=<code>`.
15. Add content-addressed id helpers using SHA-256 over sorted, length-prefixed
    canonical tokens:
    - `price_expectation_token(owner_token, item_kind, unit_token, window_index)`;
    - `price_quote_token(owner_token, venue_id, item_kind, unit_token,
      direction, window_index)`;
    - `price_distribution_token(group_token, window_index, item_kind,
      unit_token)`.
    - `price_relation_token(window_index, group_kind, group_a, group_b,
      item_kind, unit_token)`.
    Each returns `<prefix><16 hex>` and rejects non-string tokens.
16. Create `src/analysis/emergent_prices_policy.py` with
    `EmergentPricesAnalysisPolicy` frozen dataclass, validated integer ranges,
    `EMERGENT_PRICE_ANALYSIS_LOCKED_POLICY`, and
    `default_emergent_prices_analysis_policy()`.
17. Locked caps/thresholds: `window_ticks=32`, `max_windows=512`,
    `max_exchange_events=200_000`, `max_quote_events=200_000`,
    `max_expectation_rows=4_096`, `max_owner_quote_rows=4_096`,
    `max_distribution_rows=8_192`, `max_market_rows=1_024`,
    `max_relation_rows=16_384`, `max_owners=4_096`, `max_item_kinds=1_024`,
    `max_units=64`, `min_distribution_samples=4`,
    `convergence_high_milli=750`, `convergence_low_milli=250`,
    `max_ratio_milli=64_000`, `alignment_high_milli=750`,
    `alignment_low_milli=250`.
18. Add `window_index_for_tick(tick, policy)` and
    `window_bounds(window_index, policy)` mirroring
    `market_institutions_policy.py:135-166`.

### Required Interfaces and Contracts

- Every row dataclass is frozen/slots with `__post_init__` type and range
  validation.
- `level` is a closed string validated against
  `PRICE_EXPECTATION_LEVELS = frozenset({"none", "weak", "expected",
  "strong"})`; analysis does not import the cognition enum.
- `window_index ∈ [0, 511]`; a later tick fails closed with
  `price_analysis_invalid_window`.
- Ids are deterministic across hash seeds and process restarts.
- No analysis module imports `agents`, `simulation` (except public detached
  contracts), `experiments`, `persistence`, `api`, or `observer`.

### Requirement Evidence

- No global price table; distributions only: user request; existing forbidden
  keys in `trade_networks_contract.py:81-99` and
  `market_institutions_contract.py:120-147`.
- Integer milli conventions: `trade_networks_detection.py:269-319`.

### Error Handling and Logging

- Invalid policy/row/window raises the closed error codes above.
- `DEBUG price_analysis_contract_locked policy=emergent-prices.v1` only.

### Tests

- `tests/unit/test_emergent_prices_analysis_contract.py`: exact enum sets
  (including `PriceSampleSource`), id determinism, forbidden-key rejection,
  window boundaries, cap boundaries.
- `tests/unit/test_emergent_prices_analysis_policy.py`: locked policy equality
  and every threshold boundary.

### Acceptance Criteria

- The contract has no field named `price` and no canonical/authoritative token.
- Ids are content-addressed and stable under row reordering.

### Verification

- `uv run pytest tests/unit/test_emergent_prices_analysis_contract.py tests/unit/test_emergent_prices_analysis_policy.py -q`
- Expected: all pass.

## Task 6: Extract bounded exchange-gathering evidence

### Intent

Turn committed exchange events into ratio evidence without reading item ids into
the analysis result and without inventing a ratio when a side is heterogeneous.

### Implementation Steps

1. Create `src/analysis/emergent_prices_rows.py` with
   `ExchangePriceEvidenceRow(tick, window_index, venue_token, event_token,
   event_kind, actor_token, counterparty_token, item_kind, unit_kind,
   item_count, unit_count, ratio_milli, pairing, coverage)`.
   `event_kind ∈ {"completed","proposed","withdrawn"}`.
2. Add `PriceQuoteEvidenceRow(tick, window_index, venue_token, event_token,
   actor_token, counterparty_token, item_kind, unit_kind, direction,
   ratio_milli, pairing, coverage)`.
3. Add `PriceEvidenceHarvest(exchanges, quotes, coverage, notices,
   exchange_count, quote_count)` and `price_evidence_digest(harvest)`.
4. Create `src/analysis/emergent_prices_events.py` with
   `price_evidence_rows_from_events(events, *, policy=None) -> PriceEvidenceHarvest`.
5. For each committed `ExchangeCompleted`:
   - venue token = content address of `occurrence.origin_location_id` using the
     same canonical helper as `analysis.market_institutions_contract.
     market_venue_token` (call it, do not duplicate the algorithm);
   - build per-side `Counter(kind)` from `give_item_ids`/`give_item_kinds` and
     `take_item_ids`/`take_item_kinds`;
   - homogeneous iff exactly one distinct kind on that side;
   - canonical direction is lexicographic: `item_kind` is the smaller kind token
     and `unit_kind` the larger, independent of actor;
   - if both sides homogeneous and kinds differ:
     `ratio_milli = unit_side_count * 1000 // item_side_count`, clamp to
     `max_ratio_milli`; `pairing=paired`;
   - if both sides homogeneous and the same kind: `pairing=same_kind`, no ratio;
   - if either side is heterogeneous: `pairing=heterogeneous`, no ratio;
   - if the computed ratio exceeds `max_ratio_milli`: `pairing=out_of_range`,
     no ratio.
6. For `ExchangeProposed`/`ExchangeWithdrawn`, emit `PriceQuoteEvidenceRow` with
   the same pairing rules. Direction is `give_for_unit` when the actor gives the
   item kind and wants the unit kind, otherwise `unit_for_give`.
7. Canonical ordering: `(tick, event_token, item_kind.value, unit_kind.value,
   event_kind)`. Cap exchanges at `max_exchange_events` and quote events at
   `max_quote_events`; deterministic prefix; `coverage="partial"` plus one
   `price_evidence_truncated` notice.
8. Deduplicate identical `(event_token, item_kind, unit_kind, direction)` rows;
   the first in canonical order wins.
9. Any malformed event (mismatched kind/id tuple lengths, empty side,
   non-string kind) is skipped and counted; it never raises out of the harvest.

### Required Interfaces and Contracts

- Rows never carry item ids, inventories, owners' valuations, or raw event
  bodies.
- `ratio_milli` is present only for `pairing=paired`.
- `venue_token` is `none` when `occurrence.origin_location_id` is absent; such a
  row has `coverage="partial"`.
- `ExchangeCompleted` remains the only completed-exchange primitive.

### Requirement Evidence

- Exchange fields: `src/world/events.py:2456-2564`.
- Venue attribution: `OccurrenceContext` at `src/world/events.py:344-390`.
- V3-19 quote homogeneity semantics: `exchange_functions.py:203-238`.
- No price/money field: `trade_networks_contract.py:1-9,81-99`.

### Error Handling and Logging

- `WARN price_evidence_skipped reason_code=<code> count=<n>` only.
- `DEBUG price_evidence_harvested exchanges=<n> quotes=<n> coverage=<token>`.
- Never log item kinds, unit tokens, ratios, actors, counterparties, or venue
  tokens.

### Tests

- `tests/unit/test_emergent_prices_events.py`: paired / heterogeneous /
  same-kind / out-of-range; missing venue; duplicate dedupe; cap truncation;
  malformed events skipped; exactly two completed parties retained; proposal
  quote rows follow the same pairing rule.
- `tests/unit/test_emergent_prices_evidence_bounds.py`: Hypothesis-generated id
  tuples never produce a ratio without one homogeneous kind per side.

### Acceptance Criteria

- The harvest is a pure function of committed events and policy.
- Reordering input events produces canonical output order and digest.
- No output field name is in `PRICE_FORBIDDEN_KEYS`.

### Verification

- `uv run pytest tests/unit/test_emergent_prices_events.py tests/unit/test_emergent_prices_evidence_bounds.py -q`
- Expected: all pass.

## Task 7: Detect price distributions and cross-market relations

### Intent

Produce analytical distributions per venue/window and per market/window, plus
pairwise convergence/divergence. There is no canonical price, score, ranking, or
severity.

### Implementation Steps

1. Extend `emergent_prices_rows.py` with:
   - `PriceDistributionRow(distribution_id, window_index, venue_id,
     market_token, item_kind, unit_kind, unit_source, sample_source,
     sample_count, min_ratio_milli, p25_ratio_milli, median_ratio_milli,
     p75_ratio_milli, max_ratio_milli, iqr_milli, dispersion_milli,
     bin_shares_milli, status, coverage)`;
   - `PriceMarketRow(market_token, window_index, venue_count,
     distribution_count, sample_count, item_kind_count, unit_count, coverage)`;
   - `PriceRelationRow(relation_id, window_index, group_kind,
     group_a_token, group_b_token, item_kind, unit_kind, unit_source,
     sample_source, overlap_milli, median_gap_milli, relation, sample_a,
     sample_b, coverage)`; `group_kind ∈ {"venue","market"}`.
2. Create `src/analysis/emergent_prices_detection.py`.
3. `detect_venue_distributions(evidence, policy)`: for each
   `sample_source` in `completed`, `quoted`, group the matching paired rows
   (`evidence.exchanges` or `evidence.quotes`) by
   `(window_index, venue_token, item_kind, unit_kind, sample_source)`; require
   `min_distribution_samples`; quantiles use nearest-rank over the sorted ratio
   list (`p25 = sorted[(n-1)//4]`, `median = sorted[(n-1)//2]`,
   `p75 = sorted[(3*(n-1))//4]`); `iqr_milli = p75 - p25`;
   `dispersion_milli = iqr_milli * 1000 // max(1, median_ratio_milli)`.
4. Compute `bin_shares_milli` from the raw sorted samples with five quintile
   bins using nearest-rank boundaries `q20 = sorted[(n-1)//5]`,
   `q40 = sorted[(2*(n-1))//5]`, `q60 = sorted[(3*(n-1))//5]`,
   `q80 = sorted[(4*(n-1))//5]`:
   `[min, q20)`, `[q20, q40)`, `[q40, q60)`, `[q60, q80)`, `[q80, max]`
   with the last bin inclusive. Each share is `count * 1000 // sample_count`;
   the five shares must sum to 1000. Store them on the distribution row so
   relations never need raw samples.
5. `detect_price_relations(distributions, policy)`: accepts any distribution rows
   whose group token is `venue_id` or `market_token`; Task 9 supplies the
   market-level rows.
   - compare ordered group pairs within a window for the same
     `(item_kind, unit_kind, unit_source, sample_source)`; canonical pair order is
     lexicographic `(group_a_token, group_b_token)`;
   - read `bin_shares_milli` from both rows; `overlap_milli =
     sum(min(share_a_bin, share_b_bin))` over the five bins;
   - `median_gap_milli = abs(a.median - b.median) * 1000 //
     max(1, max(a.median, b.median))`;
   - relation: `insufficient_evidence` if either sample <
     `min_distribution_samples`; `converged` if overlap ≥
     `convergence_high_milli`; `divergent` if overlap <
     `convergence_low_milli`; otherwise `partially_converged`.
6. Cap distributions at `max_distribution_rows` and relations at
   `max_relation_rows`; deterministic prefix and one
   `price_distribution_truncated` / `price_relation_truncated` notice.
7. Add `assert_price_layer_separation(rows)` rejecting any field whose name is
   forbidden or whose layer marker conflicts with its row family.

### Required Interfaces and Contracts

- `unit_source` on distribution/relation rows is the source that produced the
  unit; mixed-source observations are never merged into one distribution.
- `sample_source` is closed to `completed` and `quoted`; the two sources are
  never pooled, and a quoted distribution is still a distribution, never a
  canonical quote.
- `bin_shares_milli` has exactly five entries, each in `[0, 1000]`, summing to
  1000 for `status=available`.
- `sample_count` is the number of paired rows for that source, not party count.
- No output contains a single "the price" for a market.
- Convergence compares distributions, not medians alone.

### Requirement Evidence

- User request: "Support analytical price distributions rather than one
  canonical price", "Measure convergence/divergence between markets".
- Detection/caps/lineage patterns: `market_institutions_detection.py:76-423`,
  `market_institutions_identity.py:38-242`.
- Integer ratios: `trade_networks_detection.py:269-319`.

### Error Handling and Logging

- Empty evidence → no rows and `coverage="missing"`, never zeros presented as
  observations.
- Below-threshold groups emit `status=insufficient_samples` with counts, not an
  invented ratio.
- `WARN price_distribution_truncated count=<n>`; `DEBUG
  price_distributions_computed distributions=<n> relations=<n>`.
- Never log item kinds, unit tokens, ratios, market tokens, or venue tokens.

### Tests

- `tests/unit/test_emergent_prices_distributions.py`: quantile nearest-rank,
  sample thresholds, heterogeneous evidence excluded, unit-source separation,
  completed/quoted separation, and five bin shares summing to 1000.
- `tests/unit/test_emergent_prices_relations.py`: identical distributions →
  `converged`; disjoint distributions → `divergent`; overlapping → partial;
  fewer than four samples → `insufficient_evidence`; pair order deterministic;
  distributions with different `sample_source` never pair.
- `tests/unit/test_emergent_prices_detection_properties.py`: Hypothesis ensures
  all five bin shares sum to 1000 and overlap ∈ [0, 1000].

### Acceptance Criteria

- Every distribution reports sample count, five quantiles, IQR, and dispersion.
- Cross-group rows are pairwise and symmetric in content, with a stable
  canonical id; Task 9 applies the same detector at market level.
- No canonical, global, or composite price value exists anywhere.

### Verification

- `uv run pytest tests/unit/test_emergent_prices_distributions.py tests/unit/test_emergent_prices_relations.py tests/unit/test_emergent_prices_detection_properties.py -q`
- Expected: all pass.

## Phase Risks and Mitigations

- Risk: ratio extraction silently treats a multi-kind bundle as one price.
  Mitigation: explicit `heterogeneous` pairing and exclusion tests.
- Risk: market attribution requires V4-20 analysis and couples pipelines.
  Mitigation: memberships are detached input rows; absence yields `missing`
  coverage, not a fabricated market.
- Risk: integer binning loses a sample.
  Mitigation: property tests assert every sample lands in exactly one bin.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
