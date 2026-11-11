# Phase 2: Analysis Evidence and Detection

Plan: [index.md](index.md)
Tasks: 5-7
Depends on: Phase 1 / Task 1

## Objective

Add a detached, event-sourced analysis package that reconstructs exchange
gatherings at logical locations, detects repeated venues, groups contemporaneous
venues into market candidates, and identifies broker-like participation. The
package reads committed events only and never reads `WorldState`, cognition
ledgers, or another agent's observation.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/analysis/trade_networks_contract.py` | policy version (39), prefixes (40-48), forbidden keys (81-112), error codes (114-145), candidate id (158-175) | Closest contract and identity pattern |
| `src/analysis/trade_networks_policy.py` | `TradeNetworksAnalysisPolicy` (55-72), window helpers (93-120) | Policy/caps/window pattern |
| `src/analysis/trade_networks_events.py` | `trade_transfer_rows_from_events` (206-603), occurrence origin (172-176), exchange rows (477), coverage (576-588) | Exchange evidence extraction from committed events |
| `src/analysis/trade_networks_detection.py` | corridors (83-131), locations (172-266), networks union-find (68-80,329-396) | Venue aggregation and connected components |
| `src/analysis/trade_networks_identity.py` | overlap coefficient (102-108), lineage (126-244), empty windows (63-95) | Forward-only lineage algorithm to mirror |
| `src/analysis/trade_networks_rows.py` | row dataclasses (75-339) | Frozen row validation pattern |
| `src/world/events.py` | `ExchangeProposed` (2456-2482), `ExchangeWithdrawn` (2485-2511), `ExchangeCompleted` (2514-2564) | Exact evidence types |
| `src/world/actions.py` | `NegotiateExchange` acts (758-760, 883-908) | Closed attempt vocabulary |
| `src/analysis/__init__.py` | trade facade (1199-1223, 1482-1485, 2077-2135) | Facade export pattern |
| `src/analysis/models.py` | `EvidenceStage`, `MetricCoverage` | Coverage vocabulary |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/analysis/market_institutions_contract.py` | create | Version, prefixes, forbidden vocabulary, error codes, enums, identity helper |
| `src/analysis/market_institutions_policy.py` | create | Policy, thresholds, caps, window helpers |
| `src/analysis/market_institutions_events.py` | create | Exchange/attempt evidence rows and coverage |
| `src/analysis/market_institutions_rows.py` | create | Detached detection/join/lineage row dataclasses |
| `src/analysis/market_institutions_detection.py` | create | Gatherings, venues, market clusters, broker-like participation |
| `src/analysis/__init__.py` | modify | Public facade exports |

## Task 5: Lock the `market-institutions.v1` analysis contract and caps

### Intent

Fix the analysis vocabulary before any detector exists, so venue statuses,
coverage, layers, caps, and thresholds cannot be chosen ad hoc by later tasks.

### Implementation Steps

1. Create `src/analysis/market_institutions_contract.py` with
   `MARKET_INSTITUTIONS_ANALYSIS_POLICY_VERSION = "market-institutions.v1"`,
   `MARKET_VENUE_PREFIX = "mkt-ven-"`, `MARKET_CANDIDATE_PREFIX = "mktc-"`,
   `MARKET_NONE_TOKEN = "none"`, and `MARKET_HEX_LEN = 16`.
2. Declare closed enums:
   - `MarketCoverage`: `complete`, `partial`, `missing`.
   - `MarketLayer`: `objective_exchange`, `owner_expectation`,
     `analytical_market`, `comparison_view`.
   - `MarketVenueStatus`: `single_gathering`, `recurring_gathering`,
     `market_like_persistent`, `dormant`.
   - `MarketGatheringStatus`: `gathering`, `below_threshold`.
   - `MarketLineageStatus`: `emerged`, `continued`, `transformed`, `split`,
     `merge`, `dissolved`.
   - `MarketAlignment`: `consistent`, `unresolved`, `inconsistent`,
     `not_applicable`.
   - `MarketAttemptKind`: `offer`, `counteroffer`, `withdraw`.
3. Declare `MARKET_FORBIDDEN_KEYS` = the cognition contract list minus
   cognitive-only names, plus `volume`, `turnover`, `liquidity`.
4. Declare `MARKET_LAYER_FORBIDDEN_PREFIXES`: objective rows forbid `mkt-ven-`
   and `mktc-`; owner rows forbid `mktc-`; analytical rows forbid objective
   event tokens; comparison rows forbid `event_token`.
5. Declare `MARKET_INSTITUTIONS_ERROR_CODES` with stable names:
   `market_institutions_invalid_input`, `market_institutions_invalid_policy`,
   `market_institutions_invalid_identity`,
   `market_institutions_invalid_window`,
   `market_institutions_duplicate_event`,
   `market_institutions_invalid_exchange`,
   `market_institutions_unknown_location`,
   `market_institutions_exchange_truncated`,
   `market_institutions_venue_truncated`,
   `market_institutions_gathering_truncated`,
   `market_institutions_market_truncated`,
   `market_institutions_expectation_truncated`,
   `market_institutions_role_truncated`,
   `market_institutions_record_truncated`,
   `market_institutions_lineage_truncated`,
   `market_institutions_layer_leak`.
6. Add `MarketInstitutionsError(ValueError)` exposing `reason_code`.
7. Add `market_venue_token(location_token: str) -> str` (SHA-256 over
   `"venue\x1f<location>"`, first 16 hex, prefixed `mkt-ven-`) and
   `market_candidate_token(venue_tokens: Sequence[str]) -> str` (SHA-256 over
   `"market\x1f" + "\x1e".join(sorted(unique venue tokens))`, first 16 hex,
   prefixed `mktc-`).
8. Add `require_market_venue_token` and `require_market_candidate_token`
   validators.

### Required Interfaces and Contracts

- `MarketInstitutionsAnalysisPolicy` (frozen, slots) defaults:
  `window_ticks=32`, `max_windows=512`, `max_exchange_events=200_000`,
  `max_attempt_rows=200_000`, `max_venue_rows=8_192`,
  `max_gathering_rows=8_192`, `max_participation_rows=8_192`,
  `max_expectation_rows=4_096`, `max_role_rows=4_096`,
  `max_record_rows=4_096`, `max_markets=1_024`, `max_locations=4_096`,
  `max_lineage_edges=16_384`, `max_dormant_windows_per_venue=1`,
  `min_gathering_exchanges=2`,
  `min_gathering_participants=2`, `min_recurring_windows=2`,
  `min_persistent_windows=3`, `persistent_recurrence_milli=500`,
  `expectation_min_evidence=2`, `broker_min_exchanges=3`,
  `broker_min_counterparties=2`, `broker_min_windows=2`,
  `alignment_high_milli=750`, `alignment_low_milli=250`,
  `lineage_overlap_milli=500`.
- Every int field rejects `bool`, non-`int`, and out-of-range values with
  `market_institutions_invalid_policy`.
- `default_market_institutions_analysis_policy()` returns the locked defaults;
  detectors and the harvest never construct a policy inline.
- `window_index_for_tick` and `window_bounds` reject negative ints and values
  beyond `max_windows` with `market_institutions_invalid_window`.
- The policy token equals the cognition token; a unit test asserts equality.

### Requirement Evidence

- Original Request: "Detect market-like persistence analytically."
- `src/analysis/trade_networks_policy.py:55-120` — locked policy and window
  helpers.
- `src/analysis/trade_networks_contract.py:81-175` — forbidden vocabulary and
  content-addressed identity.

### Error Handling and Logging

- Contract errors log `market_institutions_contract_invalid
  reason_code=<code>` at ERROR with no values.
- Policy validation logs `market_institutions_policy_invalid field=<name>` at
  WARN; the field name is safe metadata.

### Tests

- `tests/unit/test_market_institutions_analysis_contract.py`: enum closure,
  policy defaults/ranges, token equality with the cognition contract, identity
  stability and token grammar, forbidden keys, layer prefixes, window bounds.

### Acceptance Criteria

- No threshold or cap is duplicated outside the policy module.
- `mkt-ven-` and `mktc-` tokens are stable across processes and input order.

### Verification

- `uv run pytest tests/unit/test_market_institutions_analysis_contract.py -q`
- Expected result: all pass.

## Task 6: Extract bounded exchange-gathering evidence

### Intent

Convert committed exchange and attempt events into sorted, token-only rows with
authoritative locations, deterministic caps, and explicit coverage. No item ids,
kinds, or valuations are retained.

### Implementation Steps

1. Create `src/analysis/market_institutions_events.py` with:
   - `MarketExchangeRow(tick, window_index, location_token, event_token,
     actor_token, counterparty_token, party_tokens, source_kind)` where
     `party_tokens` is the sorted unique pair and `source_kind="exchange"`;
   - `MarketAttemptRow(tick, window_index, location_token, event_token,
     actor_token, counterparty_token, attempt_kind)`;
   - `MarketEvidenceHarvest(exchanges, attempts, coverage, notices,
     exchange_count, attempt_count)` with count/length equality checks.
2. Add `market_evidence_rows_from_events(events, *, policy) ->
   MarketEvidenceHarvest`:
   - sort events by `(tick, sequence)` and reject duplicate `event_id` values
     with `market_institutions_duplicate_event`;
   - handle `ExchangeCompleted`: require `actor_id != counterparty_id`, a
     non-empty location from `event.occurrence.origin_location_id`, and
     `act == "accept"`; emit one row;
   - handle `ExchangeProposed`: emit `MarketAttemptRow` with `offer` or
     `counteroffer`; handle `ExchangeWithdrawn` with `withdraw`;
   - ignore every other event kind and log
     `market_events_ignored_kind=<n>` at DEBUG with a count only;
   - missing/blank location on an exchange raises
     `market_institutions_unknown_location`; missing location on an attempt adds
     notice `market_institutions_attempt_location_unresolved` and drops the row;
   - sort exchanges `(tick, event_token, actor_token, counterparty_token)` and
     attempts `(tick, event_token, actor_token, attempt_kind)`;
   - apply `max_exchange_events` to exchanges and `max_attempt_rows` to
     attempts independently, retain each sorted prefix, and add
     `market_institutions_exchange_truncated` /
     `market_institutions_attempt_truncated`;
   - coverage: no exchanges and no attempts → `missing`; any notice, truncated
     rows, or unresolved attempt locations → `partial`; otherwise `complete`.
3. Add `market_evidence_digest(harvest)` producing lower-case SHA-256 over the
   canonical token rows, for determinism tests.

### Required Interfaces and Contracts

- Rows contain no item ids, item kinds, give/take bundles, valuations, prices,
  or free text.
- `location_token` is the occurrence origin location, never the observing actor
  location, because analysis consumes authoritative committed events.
- Duplicate event ids are a hard failure, not a warning.
- Exchanges and attempts are capped independently; truncating one family never
  silently drops the other, and any truncation sets `coverage=partial`.

### Requirement Evidence

- Original Request: "agents repeatedly trade at location".
- `src/analysis/trade_networks_events.py:206-603` — exchange extraction and
  occurrence-origin attribution.
- `src/world/events.py:2514-2564` — `ExchangeCompleted` fields.

### Error Handling and Logging

- DEBUG: `market_events_parsed exchanges=<n> attempts=<n> notices=<n>`.
- WARN: `market_events_truncated exchanges=<n>`; `market_events_location_missing
  attempts=<n>`.
- Never log location tokens, actor tokens, counterparties, or item ids.

### Tests

- `tests/unit/test_market_institutions_events.py`: one row per completion;
  canonical party ordering; attempt kinds; location from occurrence; duplicate
  event failure; unknown event ignored; missing location behavior; independent
  exchange and attempt truncation; coverage matrix
  (missing/partial/complete); digest determinism.

### Acceptance Criteria

- A stream with two completions at the same location and no notices yields two
  rows and `coverage=complete`.
- Reordering the input event sequence produces byte-identical rows.

### Verification

- `uv run pytest tests/unit/test_market_institutions_events.py -q`
- Expected result: all pass.

## Task 7: Detect venues, market clusters, and broker-like participation

### Intent

Produce the objective analytical layer: per-window venue activity, gathering
qualification, recurrence, persistence labels, market clusters, and broker-like
participation. This layer contains no owner beliefs and no recommendation.

### Implementation Steps

1. Create `src/analysis/market_institutions_rows.py` with frozen rows:
   - `MarketGatheringRow(venue_id, window_index, location_token, exchange_count,
     proposal_count, withdrawn_count, distinct_party_count,
     distinct_actor_count, status, coverage)` where `status` is a
     `MarketGatheringStatus`;
   - `MarketVenueRow(venue_id, window_index, location_token, exchange_count,
     proposal_count, withdrawn_count, distinct_party_count,
     distinct_actor_count, active_window_count, recurrence_milli, status,
     market_like, coverage)`;
   - `MarketCandidateRow(market_token, window_index, venue_ids, exchange_count,
     distinct_party_count, coverage)`;
   - `MarketParticipationRow(venue_id, window_index, actor_token,
     exchange_count, counterparty_count, active_window_count, broker_like,
     coverage)`.
2. Create `src/analysis/market_institutions_detection.py`:
   - `detect_gatherings(harvest, *, policy)` groups exchanges and attempts by
     `(window_index, location_token)`; a gathering requires
     `exchange_count >= min_gathering_exchanges` and
     `distinct_party_count >= min_gathering_participants`;
   - `detect_venues(harvest, *, policy, window_end)` emits one row per active
     window per venue, plus
     `min(policy.max_dormant_windows_per_venue,
     window_end - last_active_window)` dormant rows starting at
     `last_active_window + 1`; the locked default is `1`, so it never emits an
     unbounded tail; active windows count distinct windows with a gathering;
     recurrence is
     `active_window_count * 1000 // observed_window_count` where
     `observed_window_count = window_end - first_venue_window + 1`; status:
     `single_gathering` at one active window, `recurring_gathering` at two,
     `market_like_persistent` at three or more with
     `recurrence_milli >= persistent_recurrence_milli` and at least two active
     windows with `distinct_party_count >= min_gathering_participants`, and
     `dormant` only on the single follow-up row;
   - cap venue and gathering rows deterministically by `(window_index,
     venue_id)`, retain the sorted prefix, and rewrite row coverage to `partial`;
   - `detect_market_candidates(venues, *, policy)` builds an undirected graph
     where two active venue locations in the same window are connected when
     their participant token sets intersect; connected components mint
     `mktc-` ids from sorted venue ids; empty components are not emitted; cap
     `max_markets`;
   - `detect_participation(harvest, *, policy)` emits one row per
     `(window_index, venue_id, actor_token)` with total exchange count, distinct
     counterparty count, and active window count; `broker_like` is true when
     `exchange_count >= broker_min_exchanges` and
     `counterparty_count >= broker_min_counterparties` and
     `active_window_count >= broker_min_windows`; rows are sorted by
     `(window_index, venue_id, actor_token)`, capped at
     `max_participation_rows`, and the sorted prefix is retained with
     `market_institutions_participation_truncated` and `partial` coverage.
3. All detectors accept the policy explicitly and raise
   `market_institutions_invalid_input` for a foreign harvest/rows type.
4. Add `assert_market_layer_separation(layers)` implementing the contract
   prefix rules; raise `market_institutions_layer_leak` on the first violation.
5. Export rows through `src/analysis/__init__.py`.

### Required Interfaces and Contracts

- `market_like` is true only for `market_like_persistent`; no numeric score,
  rank, severity, or recommendation field exists.
- Venue status is objective: it never depends on owner expectation rows, which
  are joined into a separate analytical row family in Task 8.
- Recurrence is an integer milli ratio with denominator zero mapping to `0`.
- Venue ids are content-addressed from location tokens, so the same logical
  location keeps its id across windows and runs.
- Market cluster ids change when the venue set changes; lineage, not identity,
  expresses continuity.

### Requirement Evidence

- Original Request: "Detect market-like persistence analytically"; "exchange
  venues".
- `src/analysis/trade_networks_detection.py:83-266,329-396` — grouping,
  aggregation, union-find, deterministic caps.
- `src/analysis/trade_networks_contract.py:158-175` — content-addressed ids.

### Error Handling and Logging

- DEBUG: `market_venues_detected venues=<n> gatherings=<n> markets=<n>
  participants=<n>` (counts only).
- WARN: `market_venues_truncated venues=<n>`,
  `market_gatherings_truncated rows=<n>`,
  `market_candidates_truncated markets=<n>`.
- Never log venue locations, actor tokens, or party sets.

### Tests

- `tests/unit/test_market_institutions_detection.py`: gathering thresholds;
  recurrence boundaries (0/499/500/1000); status matrix; exactly one dormant row
  after the last active window and none beyond `window_end`; cluster
  connectivity and overlap; venue/gathering/participation caps and notices;
  participation/broker thresholds; layer leakage detection; input-type
  rejection.

### Acceptance Criteria

- Three active windows at one location with three exchanges and two parties
  yield `market_like_persistent` with `market_like=True` and
  `recurrence_milli >= 500`.
- A single exchange below the gathering threshold produces no gathering and no
  venue belief row.

### Verification

- `uv run pytest tests/unit/test_market_institutions_detection.py -q`
- Expected result: all pass.

## Phase Risks and Mitigations

- Risk: attributing an exchange to the observing actor's location instead of the
  authoritative occurrence origin. Mitigation: Task 6 reads
  `event.occurrence.origin_location_id` and tests the difference.
- Risk: recurrence denominators drift when a venue starts late. Mitigation:
  count from the venue's first active window and lock the formula in Task 5.
- Risk: cluster identity creates false continuity. Mitigation: identity is the
  sorted venue set; continuity is expressed only by lineage in Phase 3.

## Phase Completion Checklist

- Every Task 5-7 acceptance criterion is verified.
- Analysis modules import no API, persistence, experiments, cognition, or
  observer package.
- No price, money, score, ranking, severity, recommendation, allocation, or
  quota key exists in any row.
- `index.md` task checkboxes are updated immediately after verified completion.
