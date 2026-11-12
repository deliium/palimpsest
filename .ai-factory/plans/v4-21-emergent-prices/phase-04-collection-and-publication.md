# Phase 4: Collection and Publication

Plan: [index.md](index.md)
Tasks: 13-16
Depends on: Phase 3 / Tasks 8-12

## Objective

Wire the completed-run analysis into experiment collection, define the canonical
`emergent-prices-snapshot-v1` document with paging and ports, store it atomically
under `emergent-prices-store-v1`, and publish it programmatically after
successful completion.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/experiments/market_institutions_completed_run.py` | 28-109 | Completed-run harvest + owner export pattern |
| `src/experiments/collectors.py` | 340-377 | Collector injection point right after market institutions |
| `src/experiments/market_institutions_publication.py` | 51-67, 294-411 | Receipt/harvest/compose/publish pattern |
| `src/simulation/market_institutions_models.py` | 39-51, 72-364 | Snapshot token/caps/record/summary pattern |
| `src/simulation/market_institutions_codec.py` | 39-269 | Canonical bytes, digest, strict decode |
| `src/simulation/market_institutions_paging.py` | 24-85 | Purpose-bound paging |
| `src/simulation/market_institutions_ports.py` | 23-129 | Cursor token, purposes, fingerprint, reader/publisher |
| `src/simulation/market_institutions_export.py` | 56-247 | Token-only owner export pattern |
| `src/persistence/market_institutions_filesystem.py` | 37-288 | Atomic store, lock, quotas, corruption code |
| `src/analysis/market_institutions_analysis.py` | 285-293 | Analysis digest convention |
| `src/experiments/catalog.py` | 5653-5706 | Off-gate experiment registration pattern (Task 19) |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/experiments/emergent_prices_completed_run.py` | create | Completed-run harvest and owner-input projection |
| `src/experiments/collectors.py` | modify | Inject `emergent_prices_analysis` |
| `src/simulation/emergent_prices_models.py` | create | Snapshot records, caps, summary |
| `src/simulation/emergent_prices_codec.py` | create | Canonical encode/decode, digest, publication id |
| `src/simulation/emergent_prices_paging.py` | create | Purpose-bound paging |
| `src/simulation/emergent_prices_ports.py` | create | Cursor, fingerprint, reader/publisher |
| `src/simulation/__init__.py` | modify | Facade imports and `__all__` for the new snapshot surface |
| `src/persistence/emergent_prices_filesystem.py` | create | Atomic store, quotas, corruption handling |
| `src/infrastructure/settings.py` | modify | Root + cursor key settings and summary entries |
| `src/experiments/emergent_prices_publication.py` | create | Snapshot composer, receipt, programmatic publish |
| `src/experiments/__init__.py` | modify | Public exports |

## Task 13: Wire completed-run analysis and experiment collectors

### Intent

Make the harvest available to completed-run metrics and publication from real
runner results, without reading live services and without failing a run when
owner export or V4-20 membership evidence is absent.

### Implementation Steps

1. Create `src/experiments/emergent_prices_completed_run.py` with
   `build_completed_run_emergent_prices_analysis(runner_result, *,
   committed_events, run_id, policy=None, input_revision="rev-run",
   window_end=None)`.
2. Require non-`None` committed events; otherwise raise a typed
   `emergent_prices_analysis_missing_events` error used by collectors.
3. Read `getattr(runner_result, "emergent_price_ledgers", ())`; call
   `simulation.emergent_prices_export.price_owner_export` and map the neutral
   `EmergentPriceOwnerRow` values into `PriceOwnerExpectationInput` and
   `PriceOwnerQuoteInput` rows owned by `analysis`. The mapping converts only
   strings/integers and never re-reads a ledger.
4. Attempt V4-20 membership evidence:
   - import `experiments.market_institutions_completed_run` lazily;
   - call `build_completed_run_market_institutions_analysis` only when
     `runner_result` exposes market ledgers and committed events exist;
   - take the latest `markets` window and, for each `MarketCandidateRow`, emit one
     `PriceMarketMembershipInput` per `venue_id` in its ordered `venue_ids`
     tuple, preserving `market_token`, `window_index`, and `coverage`;
   - deduplicate `(market_token, venue_id, window_index)`, sort by that key, and
     apply `max_market_rows`; a venue may appear in only one market per window;
   - any exception is caught, logged as
     `WARN price_market_membership_unavailable code=<safe-code>`, and yields an
     empty membership tuple. Never fail the run for missing V4-20 evidence.
5. Call `harvest_emergent_prices_analysis` and return the analysis.
6. `collectors.py`: add a block immediately after the market-institution block:
   when `events is not None`, the runner config enables `markets_credit`, and
   `runner_config.subjective_valuation is not None`, build the price analysis and
   `replace(inputs, emergent_prices_analysis=price_analysis)`; catch any
   exception and log `ERROR emergent_prices_collector_failed code=<safe-code>`
   while continuing.
7. Re-export the builder from `experiments/__init__.py`.

### Required Interfaces and Contracts

- The builder accepts only a completed `SimulationRunnerResult`, committed
  events, and policy; no `WorldState`, runtime, store, or API object.
- Owner inputs are token-only; counterparty ids never leave the export.
- Missing V4-20 analysis yields empty memberships and `market_coverage="missing"`.
- Collector failure never changes scientific status.

### Requirement Evidence

- Completed-run pattern: `market_institutions_completed_run.py:28-109`.
- Collector injection: `collectors.py:340-377`.
- Owner export: `market_institutions_export.py:56-232`.

### Error Handling and Logging

- `ERROR emergent_prices_collector_failed code=<safe-code>` and
  `WARN price_market_membership_unavailable code=<safe-code>`.
- Never log events, owner tokens, item kinds, units, or ratios.

### Tests

- `tests/unit/test_emergent_prices_completed_run.py`: owner ledgers project to
  inputs; missing ledgers → missing coverage; missing events raises;
  membership failure is contained.
- `tests/unit/test_emergent_prices_collector.py`: input is injected only when
  events, `markets_credit`, and `subjective_valuation` are present; metric
  documents appear; failure is logged with a safe code.

### Acceptance Criteria

- A completed run with price ledgers produces a non-empty analysis.
- A run without V4-20 or owner export still produces objective distributions.
- No live service is imported by the builder.

### Verification

- `uv run pytest tests/unit/test_emergent_prices_completed_run.py tests/unit/test_emergent_prices_collector.py -q`
- Expected: all pass.

## Task 14: Add `emergent-prices-snapshot-v1` models, codec, ports, and paging

### Intent

Define the canonical read model before storage or HTTP exists, with bounded
records and no wall-clock field.

### Implementation Steps

1. `src/simulation/emergent_prices_models.py`:
   - tokens: `EMERGENT_PRICES_SNAPSHOT_VERSION =
     "emergent-prices-snapshot-v1"`,
     `EMERGENT_PRICES_SNAPSHOT_POLICY = "emergent-prices.v1"`,
     `EMERGENT_PRICES_PUBLICATION_PREFIX = "prc-pub-"`;
   - caps: `MAX_UNITS=64`, `MAX_EXPECTATIONS=2_048`, `MAX_QUOTES=2_048`,
     `MAX_DISTRIBUTIONS=4_096`, `MAX_MARKETS=1_024`, `MAX_RELATIONS=16_384`,
     `MAX_WINDOWS=512`, `ARTIFACT_MAX_BYTES=8_388_608`.
2. Record dataclasses:
   - `PriceUnitRecord(unit_token, unit_source, owner_count, expectation_count,
     distribution_count, median_confidence_milli, unit_alignment, coverage)`;
   - `PriceExpectationRecord(expectation_id, window_index, owner_token,
     item_kind, unit_kind, unit_source, expected_ratio_milli, confidence_milli,
     level, valuation_reservation, observation_count, quote_count,
     distribution_source, alignment, coverage)`;
   - `PriceQuoteRecord(quote_id, window_index, venue_id, actor_token,
     counterparty_token, item_kind, unit_kind, direction, ratio_milli,
     confidence_milli, source, source_tick, coverage)`;
   - `PriceDistributionRecord(distribution_id, window_index, venue_id,
     market_token, item_kind, unit_kind, unit_source, sample_source,
     sample_count, min_ratio_milli, p25_ratio_milli, median_ratio_milli,
     p75_ratio_milli, max_ratio_milli, iqr_milli, dispersion_milli,
     bin_shares_milli, status, coverage)`;
   - `PriceMarketRecord(market_token, window_index, venue_count,
     distribution_count, sample_count, item_kind_count, unit_count, coverage)`;
   - `PriceRelationRecord(relation_id, window_index, group_kind,
     group_a_token, group_b_token, item_kind, unit_kind, unit_source,
     sample_source, overlap_milli, median_gap_milli, relation, sample_a,
     sample_b, coverage)`;
   - `EmergentPricesSummaryRecord` with counts, family coverages, `truncated`,
     and `window_count`.
3. `EmergentPricesSnapshot(run_id, schema_version, policy_version, summary,
   units, expectations, quotes, distributions, markets, relations, digest,
   publication_id)` plus `empty_emergent_prices_snapshot(run_id)`.
4. `src/simulation/emergent_prices_codec.py`: canonical JSON bytes with sorted
   keys, compact separators, ASCII, trailing newline; duplicate-key rejection;
   strict top-level and row key sets; `encode_emergent_prices_snapshot`,
   `decode_emergent_prices_snapshot`, `emergent_prices_artifact_digest`,
   `finalize_emergent_prices_snapshot`.
5. Publication id is `prc-pub-` plus the first 32 hex characters of the SHA-256
   of canonical payload bytes; `digest` is `sha256:` plus the full hex.
6. `src/simulation/emergent_prices_paging.py`: purposes `units`,
   `expectations`, `quotes`, `distributions`, `markets`, `relations`; per-purpose
   row models and sort keys; `PRICE_PAGE_DEFAULT = 100`,
   `PRICE_PAGE_MAX = 500`; `page_emergent_prices(rows, *, purpose,
   after_key=None, limit=100, window_index=None)`.
7. `src/simulation/emergent_prices_ports.py`:
   - `EMERGENT_PRICES_CURSOR_TOKEN = "palimpsest.emergent_prices.cursor.v1"`;
   - `EMERGENT_PRICES_PURPOSES = ("summary", "units", "expectations", "quotes",
     "distributions", "markets", "relations")`;
   - `EmergentPricesSummary`, `EmergentPricesPublication`,
     `EmergentPricesCursor` dataclasses;
   - `emergent_prices_query_fingerprint(...)` binds cursor token, run id,
     publication id, digest, purpose, filters, and limit; HMAC when a key is
     supplied, SHA-256 otherwise;
   - `EmergentPricesReader` and `EmergentPricesPublisher` protocols.
8. `src/simulation/__init__.py`: add alphabetical imports and `__all__` entries
   for every public model, codec, paging, port, and export symbol, matching the
   existing market-institution block (lines 822-862). Public consumers import
   from `simulation`, not deep modules.

### Required Interfaces and Contracts

- No `created_at`, wall clock, or filesystem mtime appears in the document.
- The `quotes` family contains owner-exported quotes
  (`observed_offer`/`communicated`/`self_authored`); objective proposal evidence
  informs distributions but is never exposed as a quote row.
- The snapshot is a sibling artifact; it is not a runner, result, replay, or SQL
  schema.
- `window_index` filters are part of the cursor fingerprint.
- Decode fails closed on version, run id, digest, non-canonical bytes, unknown
  keys, duplicate keys, or size over `ARTIFACT_MAX_BYTES`.

### Requirement Evidence

- Snapshot/codec/paging/ports pattern:
  `market_institutions_models.py:39-364`, `market_institutions_codec.py:39-269`,
  `market_institutions_paging.py:24-85`, `market_institutions_ports.py:23-129`.

### Error Handling and Logging

- `WARN price_snapshot_truncated purpose=<token> count=<n>` only.
- Decode/codec errors use `emergent_prices_snapshot_invalid` and
  `emergent_prices_snapshot_oversize`.

### Tests

- `tests/unit/test_emergent_prices_snapshot.py`: round-trip canonical bytes;
  digest/publication id stability; no wall-clock field; duplicate/unknown key
  rejection; oversize rejection; cap truncation; `sample_source` and five
  `bin_shares_milli` round-trip; public symbols import from `simulation`.
- `tests/unit/test_emergent_prices_paging.py`: purpose sort keys, limit bounds,
  `window_index` filter, cursor rejection for another window; Hypothesis page
  concatenation equals full set.

### Acceptance Criteria

- Identical analysis input yields identical snapshot bytes across processes.
- Every purpose pages deterministically without duplicates or omissions.

### Verification

- `uv run pytest tests/unit/test_emergent_prices_snapshot.py tests/unit/test_emergent_prices_paging.py -q`
- Expected: all pass.

## Task 15: Add the atomic filesystem store and dual-gated settings

### Intent

Persist and serve snapshots safely with quotas, idempotence, and corruption
containment, and expose two explicit settings that fail closed.

### Implementation Steps

1. `src/persistence/emergent_prices_filesystem.py`:
   - `EMERGENT_PRICES_STORE_VERSION = "emergent-prices-store-v1"`;
   - `_STATE_FILE = "state.json"`, `_LOCK_FILE = "store.lock"`;
   - `EmergentPricesPublisherOptions(max_publications=16,
     max_bytes=8_388_608)`;
   - `_atomic_write` via `tempfile.mkstemp` in the target directory, write,
     flush, `os.fsync`, `os.replace`, unlink temp;
   - `_locked` via `fcntl.flock(LOCK_EX)` on `store.lock`;
   - publish encodes canonical bytes, is idempotent for identical
     digest/publication id, rejects a digest conflict with
     `emergent_prices_publication_exists`, enforces quotas with
     `emergent_prices_store_quota_exceeded`, writes the payload and
     `state.json`;
   - reader lists publications, defaults to the latest sorted publication,
     validates tokens, decodes, and maps corruption to
     `emergent_prices_store_corrupt`;
   - factories `create_emergent_prices_reader(root)` and
     `create_emergent_prices_publisher(root)`.
2. `settings.py`: add `emergent_prices_root: Path | None = None` and
   `emergent_prices_cursor_key: SecretStr | None = Field(default=None,
   repr=False)`; validate the cursor key at ≥32 UTF-8 bytes; add summary entries
   `has_emergent_prices_root`, `has_emergent_prices_cursor_key`,
   `emergent_prices_enabled` (both), and `emergent_prices_cursor_enabled`.
3. Environment names are exactly
   `PALIMPSEST_EMERGENT_PRICES_ROOT` and
   `PALIMPSEST_EMERGENT_PRICES_CURSOR_KEY`.

### Required Interfaces and Contracts

- Store tokens and errors are closed; no path appears in an error payload beyond
  the configured root abstraction.
- A corrupt payload returns no rows; it is never partially decoded.
- Publication is atomic; readers never observe a partial state.
- Settings are frozen with `extra="forbid"`.

### Requirement Evidence

- Store/quota/corruption pattern: `market_institutions_filesystem.py:37-288`.
- Settings/dual-gate pattern: `settings.py:248-255,422-457,831-843`.

### Error Handling and Logging

- `INFO emergent_prices_snapshot_published publications=<n> bytes=<n>` counts
  only; `ERROR emergent_prices_store_corrupt code=...` without path or payload.
- Never log cursor keys, publication ids, digests, or snapshot content.

### Tests

- `tests/unit/test_emergent_prices_store.py`: atomic publish, idempotent
  republish, quota rejection, corrupt payload, reader latest selection,
  symlink/permission safety where supported.
- `tests/unit/test_emergent_prices_settings.py`: defaults off, cursor-key
  length, summary flags, `PALIMPSEST_` prefix only.

### Acceptance Criteria

- Store operations are crash-safe and deterministic.
- Unset settings keep every reader path closed.

### Verification

- `uv run pytest tests/unit/test_emergent_prices_store.py tests/unit/test_emergent_prices_settings.py -q`
- Expected: all pass.

## Task 16: Compose and publish completed-run price snapshots

### Intent

Map one analysis into the canonical snapshot and publish it only after
successful completion, programmatically, with an honest receipt.

### Implementation Steps

1. `src/experiments/emergent_prices_publication.py`:
   - `EmergentPricesReceipt(run_id, publication_id, digest, stored,
     reason_code, coverage, notices)`;
   - `EmergentPricesHarvest(run_id, analysis, snapshot, receipt)`;
   - row mappers for units, expectations, quotes, distributions, markets, and
     relations, applying snapshot caps and preserving `sample_source`,
     `bin_shares_milli`, and `distribution_source` exactly;
   - `compose_emergent_prices_snapshot(analysis, *, run_id)` finalizes digest
     and publication id;
   - `build_emergent_prices_harvest_result(runner_result, *, committed_events,
     run_id, publisher=None, policy=None, input_revision="rev-run",
     window_end=None)`;
   - `publish_emergent_prices_snapshot(snapshot, publisher)`:
     coverage `missing` → receipt
     `emergent_prices_publication_missing`; publisher `None` → receipt
     `emergent_prices_publication_disabled`; success → `published`; never raises
     for a disabled or missing publication.
2. Map the analysis' latest window per family into the snapshot; counts come
   from the analysis object, never recomputed from capped rows.
3. Ensure the snapshot summary records every family coverage and `truncated`.
4. Re-export from `experiments/__init__.py`.
5. Do not add a CLI producer and do not add a runner flag; publication remains
   callable only from composition/tests.

### Required Interfaces and Contracts

- Publication is post-completion and never mutates the runner result.
- A disabled publisher writes nothing and leaves scientific status unchanged.
- The receipt code set is exactly `published`, `publication_disabled`,
  `publication_missing`, `store_quota_exceeded`, `store_corrupt`.
- Snapshot caps are applied before encoding, and truncation is reported.

### Requirement Evidence

- Publication pattern: `market_institutions_publication.py:51-411`.
- User request: analytical distributions, no global price table.
- Architecture: publication is the only analysis-to-artifact bridge.

### Error Handling and Logging

- `INFO emergent_prices_publication_completed stored=<bool>
  reason_code=<token>`; `WARN price_snapshot_partial coverage=<token>`.
- Never log publication ids, digests, owner tokens, kinds, units, or ratios.

### Tests

- `tests/unit/test_emergent_prices_publication.py`: compose from analysis;
  missing coverage; disabled publisher; quota/corrupt propagation; receipt codes;
  snapshot caps; no wall-clock field.
- `tests/integration/test_emergent_prices_store_api.py` (DB-free): publish then
  read through the filesystem reader, including idempotent republish.

### Acceptance Criteria

- Programmatic publish works end-to-end without HTTP.
- No CLI or runner surface is added.

### Verification

- `uv run pytest tests/unit/test_emergent_prices_publication.py tests/integration/test_emergent_prices_store_api.py -q -m "not scale"`
- Expected: all pass.

## Phase Risks and Mitigations

- Risk: snapshot caps hide rows while summary counts claim completeness.
  Mitigation: summary `truncated` is derived from cap application, and tests
  compare capped vs uncapped counts.
- Risk: store publication leaks path/content in errors.
  Mitigation: closed error tokens and metadata-only logging.
- Risk: collector imports experiments into analysis.
  Mitigation: composition stays in `experiments`; analysis remains dependency
  closed.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
