# Phase 4: Collection and Publication

Plan: [index.md](index.md)
Tasks: 13-16
Depends on: Phase 3 / Tasks 10-12

## Objective

Wire the detached analysis into completed-run collection, then add a canonical
`market-institutions-snapshot-v1` document, an atomic `market-institutions-store-v1`
filesystem store, dual-gated settings, and a programmatic publication bridge.
Publication is opt-in and post-completion; disabled publication writes nothing
and never changes scientific status.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/experiments/collectors.py` | trade block (290-320), migration block (1102) | Collector injection point |
| `src/experiments/trade_networks_completed_run.py` | builder (118-169), wrappers (172-186) | Completed-run analysis pattern |
| `src/simulation/runner_models.py` | `SimulationResult` ledgers (6404), validation (6838-6867) | Result ledger field added in Task 3 |
| `src/simulation/trade_networks_models.py` | versions/caps (44-53), rows (161-451), snapshot (454-501) | Snapshot model pattern |
| `src/simulation/trade_networks_codec.py` | canonical JSON (69-76), digest (79-90), publication id (93-96), decode (244-275) | Canonical codec pattern |
| `src/simulation/trade_networks_ports.py` | protocols (132-151), summary/publication (39-57), cursor (60-84), purposes (27-35) | Port contract |
| `src/simulation/trade_networks_paging.py` | limit (38), filter/window validation (107-117) | Purpose-bound paging |
| `src/persistence/trade_networks_filesystem.py` | tokens (35-55), atomic write (83-94), lock (97-108), publish (132-167), quota (38-47), read (191-231) | Atomic store pattern |
| `src/infrastructure/settings.py` | fields (248-249), validator (422-431), bootstrap flags (794-803) | Dual-gate settings |
| `src/experiments/trade_networks_publication.py` | receipt/harvest (47-65), compose (148-263), publish (309-361) | Publication bridge |
| `src/experiments/__init__.py` | trade exports (457-466, 652-835) | Facade export pattern |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/experiments/market_institutions_completed_run.py` | create | Completed-run analysis builder |
| `src/experiments/collectors.py` | modify | Inject analysis into metric inputs |
| `src/simulation/market_institutions_models.py` | create | Snapshot models and caps |
| `src/simulation/market_institutions_export.py` | create | Token-only owner export projection |
| `src/simulation/market_institutions_codec.py` | create | Canonical encode/decode, digest, publication id |
| `src/simulation/market_institutions_ports.py` | create | Reader/publisher protocols, summary, cursor |
| `src/simulation/market_institutions_paging.py` | create | Bounded purpose-bound paging |
| `src/simulation/__init__.py` | modify | Public exports |
| `src/persistence/market_institutions_filesystem.py` | create | Atomic store |
| `src/infrastructure/settings.py` | modify | Two gated settings |
| `src/experiments/market_institutions_publication.py` | create | Compose and publish |
| `src/experiments/__init__.py` | modify | Public exports |

## Task 13: Wire completed-run analysis and experiment collectors

### Intent

Make the metric service receive a real market analysis for completed runs that
export owner ledgers, without adding a runner flag or a second event read.

### Implementation Steps

1. Create `src/simulation/market_institutions_export.py`:
   - `MarketOwnerExportRow(owner_token, venue_token, family, expectation,
     cadence, interval_ticks, phase_tick, schedule_window_index,
     confidence_milli, evidence_count, role_kind, role_basis, recognized,
     actor_token, record_kind, anchor_token, first_tick, last_tick, coverage)`;
   - `market_institution_owner_export(ledgers, *, allowed_owner_ids=None)`
     projecting owner ledgers into sorted token-only rows, rejecting a non-ledger,
     a foreign owner, or a duplicate owner;
   - `market_institution_export_notices(rows)` and
     `market_institution_export_digest(rows)` over canonical rows.
2. Create `src/experiments/market_institutions_completed_run.py`:
   - `build_completed_run_market_institutions_analysis(runner_result, *,
     committed_events, run_id, policy=None, input_revision="rev-run",
     window_end=None)`; `committed_events` is required and a `None` value raises
     `ValueError("market_institutions_completed_run_requires_events")`;
   - read `runner_result.market_institution_ledgers` via `getattr(..., ())`;
   - call `market_institution_owner_export` to project rows, then map them to
     the Task 8 analysis inputs `MarketOwnerExpectationInput`,
     `MarketOwnerRoleInput`, and `MarketOwnerRecordInput` by `family`;
   - call `harvest_market_institutions_analysis` with the events, mapped inputs,
     policy, and `window_end`;
   - log `market_institutions_completed_run run_id_present=true
     owners=<n> events=<n> coverage=<state>`.
3. In `src/experiments/collectors.py`, after the trade-network block and before
   or after the supply-chain block (keep append order stable):
   - call the builder with `arm.runner_result`, `arm.committed_events`, and the
     run id used by neighbouring blocks;
   - `inputs = replace(inputs, market_institutions_analysis=analysis)`.
4. Export the builder through `src/experiments/__init__.py`, and export
   `MarketOwnerExportRow` plus `market_institution_owner_export` through
   `src/simulation/__init__.py`.

### Required Interfaces and Contracts

- Missing ledgers do not abort collection: the analysis still uses committed
  evidence and marks owner lanes `missing`.
- The builder never imports `analysis` internals beyond the public facade and
  never imports API, persistence, or cognition.
- `run_id` is passed through for metric provenance only; it is not stored in the
  analysis object.

### Requirement Evidence

- `src/experiments/collectors.py:290-320` — trade analysis injection.
- `src/experiments/migration_displacement_harvest.py:399-435` — result-ledger
  harvest.

### Error Handling and Logging

- WARN: `market_institutions_completed_run_missing_ledgers`.
- DEBUG: `market_institutions_collector_injected coverage=<state>`.
- ERROR: `market_institutions_completed_run_rejected
  reason_code=events_required`.
- Never log owner counts per owner, venue ids, or anchors.

### Tests

- `tests/unit/test_market_institutions_completed_run.py`: events required;
  missing ledgers → owner lanes missing; ledgers projected once; collector
  injection; deterministic repeat.
- `tests/unit/test_market_institutions_export.py`: a non-ledger value raises
  `invalid_item`; a foreign owner and a duplicate owner raise `foreign_owner` /
  `duplicate_owner`; non-monotonic or unsorted owner input is rejected or
  returned owner-sorted exactly once; the exported rows contain no objective
  event tokens or payload text.

### Acceptance Criteria

- A completed run with three exchange events and two ledgers produces an
  analysis with `coverage` in `{complete, partial}` and non-empty owner rows.
- A completed run with no ledgers still produces objective venue rows.

### Verification

- `uv run pytest tests/unit/test_market_institutions_completed_run.py -q`
- Expected result: all pass.

## Task 14: Add `market-institutions-snapshot-v1` models, codec, ports, and paging

### Intent

Define the canonical read artifact and its purpose-bound paging before any store
or route exists.

### Implementation Steps

1. Create `src/simulation/market_institutions_models.py`:
   - `MARKET_INSTITUTIONS_SNAPSHOT_VERSION = "market-institutions-snapshot-v1"`,
     `MARKET_INSTITUTIONS_SNAPSHOT_POLICY = "market-institutions.v1"`,
     `MARKET_INSTITUTIONS_PUBLICATION_PREFIX = "mkt-pub-"`;
   - caps: venues 4,096; gatherings 4,096; expectations 2,048; roles 2,048;
     records 2,048; markets 1,024; lineage 16,384; windows 512; payload 8 MiB;
   - frozen rows with `__post_init__` validation:
     - `MarketVenueRecord(venue_id, window_index, location_id, exchange_count,
       proposal_count, withdrawn_count, distinct_party_count,
       distinct_actor_count, active_window_count, recurrence_milli, status,
       market_like, coverage)`;
     - `MarketGatheringRecord(venue_id, window_index, location_id,
       exchange_count, proposal_count, withdrawn_count, distinct_party_count,
       status, coverage)`;
     - `MarketExpectationRecord(venue_id, window_index, owner_token,
       expectation, cadence, interval_ticks, phase_tick, schedule_window_index,
       confidence_milli, evidence_count, alignment, coverage)`;
     - `MarketRoleRecord(venue_id, window_index, actor_token, role_kind,
       role_basis, recognized, exchange_count, counterparty_count,
       active_window_count, coverage)`;
     - `MarketRecordAnchorRecord(venue_id, window_index, record_kind,
       anchor_token, owner_row_count, coverage)`;
     - `MarketCandidateRecord(market_id, window_index, venue_ids,
       exchange_count, distinct_party_count, coverage)`;
     - `MarketLineageRecord(window_index, market_id, venue_ids, party_count,
       status, previous_market_ids, next_market_ids, rerouted, sustained,
       coverage)`;
     - `MarketInstitutionsSummaryRecord(window_tick, venue_count,
       gathering_count, market_like_venue_count, recurring_venue_count,
       expected_venue_count, market_count, expectation_row_count,
       role_row_count, record_anchor_count, emerged_count, continued_count,
       transformed_count, split_count, merge_count, dissolved_count,
       sustained_market_count, lineage_edge_count, coverage, truncated)`;
     - `MarketInstitutionsSnapshot(run_id, schema_version, policy_version,
       summary, venues, gatherings, expectations, roles, records, markets,
       lineage, digest, publication_id)`;
   - `empty_market_institutions_snapshot(run_id, *, digest="",
     publication_id="")`;
2. Create `src/simulation/market_institutions_codec.py`:
   - `finalize_market_institutions_snapshot(snapshot)` assigning digest and
     publication id, imported by experiments/publication code but never by
     models;
   - canonical JSON (`sort_keys`, compact separators, `ensure_ascii=True`,
     `allow_nan=False`, trailing newline);
   - digest over the payload with blank `digest`/`publication_id`;
   - publication id
     `sha256("market-institutions-pub|{run_id}|{digest}")[:32]` prefixed
     `mkt-pub-`;
   - strict decode: duplicate keys, unknown/missing keys, wrong schema, run-id
     mismatch, digest mismatch, non-canonical bytes, and >8 MiB all fail with
     `market_institutions_artifact_*` codes;
   - never expose wall-clock time, host, or request IDs.
3. Create `src/simulation/market_institutions_ports.py`:
   - `MarketInstitutionsReader.read_summary(run_id)`,
     `read_snapshot(run_id, publication_id=None)`,
     `list_publications(run_id)`;
   - `MarketInstitutionsPublisher.publish(snapshot)` plus the read methods;
   - `MarketInstitutionsSummary`, `MarketInstitutionsPublication`,
     `MarketInstitutionsCursor` with purpose, fingerprint, optional `after_key`,
     optional `window_index` in `0..511`;
   - purposes: `summary`, `venues`, `gatherings`, `expectations`, `roles`,
     `records`, `markets`;
   - `market_institutions_query_fingerprint(...)` binds run id, publication id,
     digest, purpose, sorted filters, limit, and token
     `"palimpsest.market_institutions.cursor.v1"`.
4. Create `src/simulation/market_institutions_paging.py`:
   - `MARKET_INSTITUTIONS_PAGE_DEFAULT = 100`,
     `MARKET_INSTITUTIONS_PAGE_MAX = 500`;
   - per-purpose sort keys and `page_market_institutions(rows, *, purpose,
     after_key, limit, window_index)`;
   - reject `window_index < 0` or `>= 512` with
     `market_institutions_invalid_window`; reject unknown purpose and limit
     outside `1..500`.
5. Export the snapshot models, codec, ports, and paging surface through
   `src/simulation/__init__.py`.

### Required Interfaces and Contracts

- Snapshot is a sibling artifact; it is not a runner config, result schema,
  replay schema, or SQL schema.
- All ids in the snapshot are analysis ids (`mkt-ven-`, `mktc-`) or opaque
  owner/actor tokens; no owner-local belief ids (`mktb-`) appear.
- Snapshot rows are sorted by their paging key before encoding; encoding is
  byte-identical for equal rows.
- `schedule_window_index` exists only because `MarketExpectationRecord` needs
  both the row window and the schedule's periodic window.
- `MarketInstitutionsSummaryRecord` counts are exactly:
  `venue_count` = distinct `venue_id` across venue rows; `gathering_count` =
  gathering rows with status `gathering`; `market_like_venue_count` = distinct
  venue ids whose latest row is `market_like_persistent`;
  `recurring_venue_count` = distinct venue ids whose latest row is
  `recurring_gathering`; `expected_venue_count` = distinct venue ids in
  expectation rows whose level is `expected` or `strong`; `market_count` =
  distinct `market_id` in the last window with a candidate row;
  `expectation_row_count`, `role_row_count`, `record_anchor_count` =
  corresponding tuple lengths or distinct anchors; `emerged_count`,
  `continued_count`, `transformed_count`, `split_count`, `merge_count`,
  `dissolved_count` = lineage rows by status; `sustained_market_count` =
  distinct `market_id` with `sustained=true` in the last comparison;
  `lineage_edge_count` = number of lineage rows; `truncated=true` when any
  snapshot family was capped; `coverage` = the worst source lane
  (`missing` > `partial` > `complete`).

### Requirement Evidence

- `src/simulation/trade_networks_models.py:44-501` — model/caps/snapshot pattern.
- `src/simulation/trade_networks_codec.py:69-96,244-275` — canonical digest and
  strict decode.
- `src/simulation/trade_networks_ports.py:27-151` — ports and cursor purposes.

### Error Handling and Logging

- ERROR: `market_institutions_artifact_invalid reason_code=<code>`; no payload
  echo.
- WARN: `market_institutions_snapshot_truncated rows=<n>` when caps trim.
- Never log digests, publication ids, owner tokens, or anchors.

### Tests

- `tests/unit/test_market_institutions_snapshot.py`: byte-identical round trip;
  exact key sets; unknown/missing key rejection; digest/publication id recipes;
  run mismatch; non-canonical rejection; 8 MiB cap; no wall-clock field; no
  `mktb-` ids in the artifact.
- `tests/unit/test_market_institutions_paging.py`: purpose sort keys; cursor
  binding to `window_index`; limit bounds; unknown purpose; window range.

### Acceptance Criteria

- Encoding a finalized snapshot twice yields identical bytes and one digest.
- A cursor created for `window_index=1` cannot page `window_index=2` rows.

### Verification

- `uv run pytest tests/unit/test_market_institutions_snapshot.py tests/unit/test_market_institutions_paging.py -q`
- Expected result: all pass.

## Task 15: Add the atomic filesystem store and dual-gated settings

### Intent

Provide an opt-in, corruption-safe artifact store and the two settings that
gate every read surface, without creating a default-on persistence path.

### Implementation Steps

1. Create `src/persistence/market_institutions_filesystem.py` with
   `MARKET_INSTITUTIONS_STORE_VERSION = "market-institutions-store-v1"`,
   token regex `^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$` rejecting `..`, `/`, `\`,
   and the layout:
   - `<root>/<run_id>/state.json`;
   - `<root>/<run_id>/<publication_id>.json`;
   - `<root>/<run_id>/store.lock`.
2. Implement `MarketInstitutionsPublisherOptions(max_publications=16,
   max_bytes=8_388_608)` with positive-int validation.
3. Implement `create_market_institutions_reader(root)` and
   `create_market_institutions_publisher(root, options=None)`:
   - `flock` the lock file for publish;
   - write the payload atomically (`mkstemp`, `fsync`, `os.replace`) before
     updating `state.json` atomically;
   - idempotent identical bytes; different bytes for an existing publication id
     raise `market_institutions_publication_exists`;
   - enforce count quota first, then total stored bytes plus payload length;
   - reads with no state return `None`/`()`; latest publication is the
     lexicographically last sorted id; decode failures wrap as
     `market_institutions_store_corrupt`;
   - verify the decoded publication id and digest against the state entry.
4. Add to `src/infrastructure/settings.py`:
   - `market_institutions_root: Path | None = None`;
   - `market_institutions_cursor_key: SecretStr | None = None`;
   - validator: when set, the secret is at least 32 UTF-8 bytes;
   - bootstrap flags `has_market_institutions_root`,
     `has_market_institutions_cursor_key`, `market_institutions_enabled`
     (both), `market_institutions_cursor_enabled` (key only).
5. Do not add the settings to any default deployment file; absence means the
   feature is disabled.

### Required Interfaces and Contracts

- The store never deletes publications and never mutates a published payload.
- A write failure leaves the previous `state.json` valid; a crash between payload
  and state leaves an unreferenced file, never a referenced corrupt payload.
- The cursor key is a `SecretStr`; its value never appears in logs, reprs, or
  error messages.
- No database, broker, or new dependency is introduced.

### Requirement Evidence

- `src/persistence/trade_networks_filesystem.py:35-231` — store layout, atomic
  commit, quotas, corruption wrapping.
- `src/infrastructure/settings.py:248-249,422-431,794-803` — dual-gate
  settings.

### Error Handling and Logging

- INFO: `market_institutions_snapshot_published publication_count=<n>
  bytes=<n>`.
- WARN: `market_institutions_store_quota_exceeded`; `market_institutions_store_corrupt`.
- ERROR: `market_institutions_store_invalid_input reason_code=<code>`; never log
  the root path, cursor key, payload, or publication id.

### Tests

- `tests/unit/test_market_institutions_store.py`: first publish; idempotent
  publish; conflicting bytes; count and byte quotas; atomic replacement; latest
  id ordering; missing state; corrupt payload; invalid run/publication ids;
  no delete path.
- `tests/unit/test_market_institutions_settings.py`: unset defaults; root-only
  and key-only gates; 31/32-byte key boundary; secret not in repr.

### Acceptance Criteria

- Publishing 17 snapshots fails with the quota code and leaves 16 readable.
- A corrupted `state.json` yields `market_institutions_store_corrupt` rather
  than partial data.

### Verification

- `uv run pytest tests/unit/test_market_institutions_store.py tests/unit/test_market_institutions_settings.py -q`
- Expected result: all pass.

## Task 16: Compose and publish completed-run market snapshots

### Intent

Map the analysis into the canonical snapshot and expose one programmatic,
post-completion publication bridge. Publication remains opt-in; there is no CLI
producer and no runner flag.

### Implementation Steps

1. Create `src/experiments/market_institutions_publication.py`:
   - `MarketInstitutionsReceipt(run_id, publication_id, digest, stored,
     reason_code, coverage, notices)`;
   - `MarketInstitutionsHarvest(run_id, analysis, snapshot, receipt)`;
   - `compose_market_institutions_snapshot(analysis, *, run_id) -> 
     MarketInstitutionsSnapshot`: map rows one-to-one, compute summary counts,
     cap rows deterministically, set `truncated`, finalize digest/publication id;
   - `build_market_institutions_harvest_result(runner_result, *,
     committed_events, run_id, publisher=None, policy=None, input_revision=
     "rev-run", window_end=None)` returning analysis + snapshot + receipt;
   - `publish_market_institutions_snapshot(snapshot, publisher)` returning a
     receipt: `stored=False` with reason `market_institutions_publication_missing`
     when the snapshot is `None` or coverage is `missing`; otherwise call
     `publisher.publish(snapshot)` and return `reason_code="published"`;
   - `market_institutions_publication_document(receipt)` returning a secret-free
     dict with run id, publication id, digest, stored, reason code, coverage,
     and notices.
2. Export the functions and receipt through `src/experiments/__init__.py`.
3. Do not add a `research_runner` flag, environment option, or CLI branch.
   Document that callers opt in by constructing a publisher.

### Required Interfaces and Contracts

- Publication runs only after scientific completion; the receipt's `stored`
  value never changes scientific status.
- The snapshot contains analysis rows only; it never includes owner-local belief
  ids, prompts, memories, or raw observation bodies.
- A missing analysis publishes nothing and returns a receipt instead of raising.
- Repeated publication of an identical snapshot is idempotent through the
  store.

### Requirement Evidence

- `src/experiments/trade_networks_publication.py:47-65,148-361` — compose and
  publish bridge.
- `src/experiments/collectors.py` — post-completion analysis availability.

### Error Handling and Logging

- INFO: `market_institutions_publication stored=<bool>
  coverage=<state>`.
- WARN: `market_institutions_publication_missing`.
- ERROR: `market_institutions_publication_rejected reason_code=<code>`; never
  log the digest, publication id, or row contents.

### Tests

- `tests/unit/test_market_institutions_publication.py`: row mapping; summary
  counts; deterministic caps; a snapshot cap sets `truncated=true` and
  `coverage=partial`; digest stability; missing analysis receipt; publisher
  called once; disabled publisher writes nothing; secret-free document.

### Acceptance Criteria

- The same analysis composed twice yields identical snapshot bytes.
- A missing analysis returns `stored=False` and creates no file.

### Verification

- `uv run pytest tests/unit/test_market_institutions_publication.py -q`
- Expected result: all pass.

## Phase Risks and Mitigations

- Risk: snapshot ids leak owner-local belief ids. Mitigation: Task 14 tests that
  no `mktb-` token appears in the artifact, and Task 16 maps only analysis rows.
- Risk: atomicity is claimed but payload/state ordering is wrong. Mitigation:
  payload first, state second, `fsync`, `os.replace`, and a crash-simulation
  test.
- Risk: dual gates drift. Mitigation: one settings test per gate combination and
  one route test per missing setting in Phase 5.

## Phase Completion Checklist

- Every Task 13-16 acceptance criterion is verified.
- The snapshot and store are siblings, not runner/result/replay/SQL schemas.
- Publication is opt-in and programmatic; no CLI flag exists.
- `index.md` task checkboxes are updated immediately after verified completion.
