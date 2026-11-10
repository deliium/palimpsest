# Phase 4: Snapshot and Publication

Plan: [index.md](index.md)
Tasks: 10-12
Depends on: Phase 3 / Tasks 7-9

## Objective

Define and publish a canonical, bounded `trade-networks-snapshot-v1` sibling
artifact through an atomic filesystem store. The snapshot is read-only research
evidence, not runner state, replay state, or a SQL schema.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/simulation/inter_society_relations_models.py` | constants 39-52; records 167-367; empty 368+ | New snapshot model pattern. |
| `src/simulation/inter_society_relations_codec.py` | canonical JSON 43-100; digest/publication 100-246 | Canonical codec pattern. |
| `src/simulation/inter_society_relations_ports.py` | cursor purposes 37-45; summary/publication/cursor 49-187 | Ports and cursor pattern. |
| `src/simulation/inter_society_relations_paging.py` | selections and page functions 23-121 | Bounded paging pattern. |
| `src/persistence/inter_society_relations_filesystem.py` | options 45-53; publisher 138-204; reader 205-260 | Atomic store pattern. |
| `src/experiments/inter_society_relations_completed_run.py` | analysis/compose 108-170 | Mapping pattern. |
| `src/experiments/inter_society_relations_publication.py` | receipt/harvest/publish/document | Publication pattern. |
| `src/infrastructure/settings.py` | fields 225-265; validators 390-425; enabled flags 740-790 | New root/cursor settings pattern. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/simulation/trade_networks_models.py` | create | Canonical snapshot records, caps, validation, empty snapshot. |
| `src/simulation/trade_networks_codec.py` | create | Canonical JSON, digest, publication id, finalize/encode/decode. |
| `src/simulation/trade_networks_ports.py` | create | Cursor purposes, summary/publication/cursor DTOs, fingerprint, reader/publisher protocols. |
| `src/simulation/trade_networks_paging.py` | create | Purpose-bound selections and page functions. |
| `src/simulation/__init__.py` | modify | Export public trade-network snapshot API. |
| `src/persistence/trade_networks_filesystem.py` | create | Atomic publisher/reader with duplicate, count, byte, and corruption guards. |
| `src/infrastructure/settings.py` | modify | `trade_networks_root`, `trade_networks_cursor_key`, validator, enabled flags. |
| `src/experiments/trade_networks_publication.py` | create | Map analysis rows to snapshot, harvest result, publication document. |
| `src/experiments/__init__.py` | modify | Export publication and composition helpers. |
| `tests/unit/test_trade_networks_snapshot.py` | create | Model/codec/finalize/round-trip tests. |
| `tests/unit/test_trade_networks_store.py` | create | Atomic store quota/corruption/duplicate tests. |
| `tests/unit/test_trade_networks_publication.py` | create | Analysis-to-snapshot mapping and publication tests. |
| `tests/unit/test_trade_networks_settings.py` | create | Root/cursor settings tests. |

## Task 10: Add `trade-networks-snapshot-v1` models codec ports and paging

### Intent

Give the API and clients a canonical, bounded artifact that can be written once
and read page by page without recomputing analysis.

### Implementation Steps

1. Create `src/simulation/trade_networks_models.py`:
   - Constants: `TRADE_NETWORKS_SNAPSHOT_VERSION =
     "trade-networks-snapshot-v1"`, `TRADE_NETWORKS_SNAPSHOT_POLICY =
     "trade-networks.v1"`, `MAX_TRADE_SNAPSHOT_CORRIDORS = 4_096`,
     `MAX_TRADE_SNAPSHOT_FLOWS = 3_072`, `MAX_TRADE_SNAPSHOT_LOCATIONS =
     4_096`, `MAX_TRADE_SNAPSHOT_DEPENDENCE = 8_192`,
     `MAX_TRADE_SNAPSHOT_CROSS_SOCIETY = 2_048`,
     `MAX_TRADE_SNAPSHOT_NETWORKS = 1_024`, `MAX_TRADE_SNAPSHOT_WINDOWS = 512`,
     `MAX_TRADE_SNAPSHOT_LINEAGE_EDGES = 16_384`.
   - `TradeFlowCountRecord(flow_class, count)`.
   - `TradeCorridorRecord(corridor_id, window_index, from_location_id,
     to_location_id, flow_counts, transfer_count, coverage)`.
   - `TradeFlowRecord(window_index, flow_class, transfer_count,
     cross_location_count, imported_count, exported_count, local_count,
     coverage)`. Imported/exported are non-disjoint location-role counts.
   - `TradeLocationRecord(location_id, window_index, inflow_count,
     outflow_count, local_count, corridor_degree, is_major,
     trade_post_present, flow_counts, coverage)`.
   - `TradeDependenceRecord(location_id, window_index, flow_class,
     imported_count, locally_originated_count, dependence_milli,
     high_dependence, coverage)`.
   - `CrossSocietyTradeRecord(pair_id, window_index, society_a, society_b,
     society_a_location_id, society_b_location_id, overlap_member_count,
     flow_counts, transfer_count, society_a_to_b_count,
     society_b_to_a_count, coverage)`.
   - `TradeNetworkRecord(network_id, window_index, corridor_ids, location_ids,
     flow_counts, transfer_count, status, previous_network_ids,
     next_network_ids, rerouted, sustained, coverage)`.
   - `TradeNetworksSummaryRecord(window_tick, corridor_count, flow_count,
     location_count, major_location_count, trade_post_location_count,
     network_count, cross_society_pair_count, transfer_count, emerged_count,
     continued_count, transformed_count, split_count, merge_count,
     dissolved_count, rerouted_count, sustained_network_count,
     lineage_edge_count, coverage, truncated)`.
   - `TRADE_SNAPSHOT_FLOW_CLASSES = ("food", "materials", "tools", "records",
     "durable_exchange_media", "other")` and
     `TRADE_SNAPSHOT_COVERAGES = ("complete", "partial", "missing")` as local
     closed tuples; `TRADE_SNAPSHOT_NETWORK_STATUSES = ("observed", "emerged",
     "continued", "transformed", "split", "merge", "dissolved")` as a local
     closed tuple; a test in Task 19 asserts parity with the analysis enums.
   - `TradeNetworksSnapshot(run_id, schema_version, policy_version, summary,
     corridors, flows, locations, dependence, cross_society, networks, digest,
     publication_id)`.
   - `empty_trade_networks_snapshot(run_id, *, digest="", publication_id="")`.
2. Validate every record: non-empty stable tokens, exact non-negative integers
   (except `TradeDependenceRecord.dependence_milli`, which is `None` or
   0-1000), closed coverage, sorted unique flow classes, ordered unique ids,
   bounded lengths, and no forbidden keys (`price`, `money`, `currency`,
   `planner`, `quota`, `allocation`, `score`, `ranking`). Record ids match
   `^trd-cor-`, `^trd-net-`, `^trd-pair-` as appropriate. Network `status` is in
   the local closed tuple; `previous_network_ids`/`next_network_ids` are sorted
   unique `trd-net-` ids; cross-society anchors are stable location tokens or
   `NONE_TOKEN`; `trade_post_present`/`rerouted`/`sustained`/`high_dependence`
   are exact bools;
   summary `lineage_edge_count` does not exceed
   `MAX_TRADE_SNAPSHOT_LINEAGE_EDGES`.
3. Create `src/simulation/trade_networks_codec.py`:
   - `trade_networks_digest(snapshot) -> str` over canonical JSON.
   - `compute_trade_networks_publication_id(snapshot) -> str`.
   - `finalize_trade_networks_snapshot(snapshot)` recomputes digest and
     publication id and returns a frozen replacement.
   - `encode_trade_networks_snapshot(snapshot) -> bytes` and
     `decode_trade_networks_snapshot(payload, *, run_id) -> snapshot`.
   - Reject duplicate keys, unknown fields, non-canonical ordering, and
     mismatched run id with `TradeNetworksArtifactError` safe codes.
4. Create `src/simulation/trade_networks_ports.py`:
   - `TRADE_NETWORKS_CURSOR_PURPOSES = ("summary", "corridors", "flows",
     "locations", "dependence", "cross-society", "networks")`.
   - `TradeNetworksSummary`, `TradeNetworksPublication`,
     `TradeNetworksCursor`, `trade_networks_query_fingerprint(filters)`, and
     `TradeNetworksReader`/`TradeNetworksPublisher` protocols. The fingerprint
     binds `window_index` and every other page filter.
5. Create `src/simulation/trade_networks_paging.py`:
   - `TradeCorridorRowSelection`, `TradeFlowRowSelection`,
     `TradeLocationRowSelection`, `TradeDependenceRowSelection`,
     `CrossSocietyTradeRowSelection`, `TradeNetworkRowSelection`; each carries
     `window_index: int | None` in addition to purpose/after_key/limit/fingerprint.
   - `page_trade_corridors`, `page_trade_flows`, `page_trade_locations`,
     `page_trade_dependence`, `page_cross_society_trades`,
     `page_trade_networks`.
   - Each selection carries purpose, `after_key`, limit, `window_index`, and
     fingerprint; reject a purpose mismatch with `trade_networks_cursor_purpose`.
   - Filter by `window_index` when present, then sort by `(window_index, row id)`
     and limit to 1..`MAX_PAGE_LIMIT`.
6. Export the public snapshot model/codec/ports/paging names from
   `src/simulation/__init__.py`.
7. Do not import `analysis` from any `simulation` trade-network module.

### Required Interfaces and Contracts

- `simulation` owns the snapshot contract and has no analysis import.
- `trade_networks_digest` is stable across processes and Python versions.
- The snapshot is bounded by the declared caps and deterministic row order.
- No runner/result/replay schema is changed.

### Error Handling and Logging

- Invalid rows raise `TradeNetworksArtifactError` with safe codes.
- Decode rejects unknown fields, duplicate keys, non-canonical JSON, and run-id
  mismatch.
- `DEBUG` only for encode/decode row counts; no payload bodies.

### Tests

- `tests/unit/test_trade_networks_snapshot.py`:
  - `test_empty_snapshot_is_canonical`
  - `test_snapshot_round_trips_exactly`
  - `test_digest_and_publication_id_change_with_rows`
  - `test_unknown_field_and_duplicate_key_rejected`
  - `test_wrong_run_id_rejected`
  - `test_caps_are_enforced`
  - `test_network_lineage_status_fields_round_trip`
  - `test_cross_society_anchor_fields_round_trip`
  - `test_trade_post_and_cross_location_fields_round_trip`
  - `test_window_filter_and_cursor_fingerprint`
  - Hypothesis `test_codec_round_trip_preserves_snapshot`

### Acceptance Criteria

- A present snapshot round-trips byte-identically after finalization.
- Tampering, unknown fields, and wrong run ids fail closed.
- No analysis import exists under `src/simulation/trade_networks_*`.

### Verification

- `uv run pytest tests/unit/test_trade_networks_snapshot.py -q`
- Expected result: all tests pass.

## Task 11: Add atomic filesystem store and settings

### Intent

Publish snapshots atomically with bounded retention and dual-gated reads, using
the same operational safety as the existing V4 stores.

### Implementation Steps

1. Add settings fields to `src/infrastructure/settings.py`:
   - `trade_networks_root: Path | None = None`
   - `trade_networks_cursor_key: SecretStr | None = Field(default=None,
     repr=False)`
2. Add `validate_trade_networks_cursor_key` requiring at least 32 UTF-8 bytes
   when set, with the error text
   `"trade_networks cursor key must be at least 32 UTF-8 bytes"`.
3. Add `has_trade_networks_root`, `has_trade_networks_cursor_key`,
   `trade_networks_enabled`, and `trade_networks_cursor_enabled` to the
   settings enabled-flags mapping. Never log the secret.
4. Create `src/persistence/trade_networks_filesystem.py`:
   - `TRADE_NETWORKS_STORE_VERSION = "trade-networks-store-v1"`.
   - `TradeNetworksPublisherOptions(max_publications=16,
     max_bytes=8_388_608)`.
   - Token guard; `_atomic_write` using a temporary file, `os.replace`, and
     `fsync`; `_locked` using `fcntl.flock`.
   - `_Publisher.publish(publication)`:
     - reject an empty or mismatched `publication_id`;
     - reject a duplicate publication id;
     - enforce `max_publications` and `max_bytes` before writing;
     - write `state.json` atomically and log counts only.
   - `_Reader.read_snapshot(run_id)`: read, decode, and raise
     `trade_networks_store_corrupt` on any corruption.
   - Factories `create_trade_networks_reader(root)` and
     `create_trade_networks_publisher(root, options=None)`.
5. Do not add a database table, migration, or Alembic revision.

### Required Interfaces and Contracts

- Store version is `trade-networks-store-v1`; snapshot version is
  `trade-networks-snapshot-v1`.
- Reads never repair, mutate, or rebuild an artifact.
- Duplicate ids, quota exhaustion, and corruption fail closed.
- The secret is `SecretStr` and is never in logs.

### Error Handling and Logging

- `ERROR trade_networks_store_corrupt` and
  `ERROR trade_networks_store_quota_exceeded` with counts only.
- `INFO trade_networks_store_published run=%s bytes=%s` safe metadata.
- No DSN, path content, or credential values.

### Tests

- `tests/unit/test_trade_networks_store.py`:
  - `test_publish_and_read_round_trip`
  - `test_duplicate_publication_rejected`
  - `test_publication_count_quota`
  - `test_byte_quota`
  - `test_corrupt_payload_rejected`
  - `test_reader_missing_run_returns_none`
- `tests/unit/test_trade_networks_settings.py`:
  - `test_trade_networks_settings_are_disabled_by_default`
  - `test_cursor_key_requires_32_bytes`
  - `test_enabled_flags_do_not_expose_secret`

### Acceptance Criteria

- Publishing twice with the same id fails closed.
- Count and byte quotas are enforced before writing.
- The reader returns `None` for an absent run and a safe error for corruption.

### Verification

- `uv run pytest tests/unit/test_trade_networks_store.py tests/unit/test_trade_networks_settings.py -q`
- Expected result: all tests pass; no SQL migration.

## Task 12: Compose and publish completed-run trade-network snapshots

### Intent

Map one analysis harvest into the canonical snapshot and publish it only after
successful scientific completion.

### Implementation Steps

1. Create `src/experiments/trade_networks_publication.py`:
   - `TradeNetworksReceipt(publication_id, digest, run_id, coverage,
     corridor_count, network_count, stored, reason_code)`.
   - `TradeNetworksHarvest(run_id, analysis, snapshot, coverage, receipts)`.
   - `compose_trade_networks_snapshot(analysis, *, run_id)`:
     - map `TradeNetworksAnalysis` rows into snapshot records;
     - join `analysis.lineage` onto each `TradeNetworkRecord`:
       `out_count >= 2` -> `split`; else `in_count >= 2` -> `merge`; else one
       incoming edge -> that relation; else `out_count >= 1` -> `emerged`; else
       `observed`. `previous_network_ids`/`next_network_ids` come from the
       lineage edges; `rerouted`/`sustained` come from the joined rows. A
       dissolved predecessor keeps `status="dissolved"` with no successor;
     - preserve row order and caps;
     - set summary counts, lineage status counts, sustained count, and
       trade-post count; set `truncated` only when a cap/truncation notice is
       present, never merely because cross-society coverage is missing;
     - derive `lineage_edge_count` from the mapped edges, never from a second
       recomputation;
     - finalize via the codec.
   - `build_trade_networks_harvest_result(runner_result, *,
     committed_events, run_id, macro_candidates=(), policy=None,
     recipe_item_kinds=None, item_kind_by_id=None, trade_post_locations=())`:
     - call the Task 9 analysis builder with the detached kind/venue inputs;
     - compose the snapshot;
     - return the harvest with coverage from the analysis.
   - `publish_trade_networks_snapshot(harvest, publisher)`:
     - skip when the snapshot has no rows and coverage is `missing`;
     - call publisher.publish;
     - return a receipt with a safe reason code.
   - `trade_networks_publication_document(harvest)` returning a bounded,
     secret-free document for experiment metadata.
2. Map analysis rows one-to-one; never re-derive counts in the publication
   layer.
3. Export `build_trade_networks_harvest_result`,
   `compose_trade_networks_snapshot`, `publish_trade_networks_snapshot`, and
   `trade_networks_publication_document` from `src/experiments/__init__.py`.
   The composition bridge also accepts `recipe_item_kinds`, `item_kind_by_id`,
   and `trade_post_locations` and forwards them to the analysis builder.
4. Ensure the API never imports `experiments`; publication is a composition
   bridge only.
5. Log `INFO trade_networks_publication run=%s corridors=%s networks=%s
   coverage=%s`; no person, item, or event payloads.

### Required Interfaces and Contracts

- Publication is opt-in and happens only after scientific completion.
- A missing analysis produces a `missing` harvest/receipt, not a fabricated
  empty success.
- Snapshot rows are exactly the analysis rows within caps.
- No publication data feeds cognition, prompts, memory, admission, or stop
  selectors.

### Error Handling and Logging

- Publisher quota/duplicate/corruption errors propagate as safe exceptions; the
  publication bridge records a receipt with a safe reason code.
- Partial/truncated analysis is published with `coverage="partial"` and a
  bounded notice.
- `WARN` only for truncation or skipped publication.

### Tests

- `tests/unit/test_trade_networks_publication.py`:
  - `test_compose_maps_every_analysis_row_family`
  - `test_compose_maps_all_six_lineage_statuses`
  - `test_compose_maps_sustained_and_venue_counts`
  - `test_compose_maps_cross_society_anchors`
  - `test_missing_analysis_produces_missing_receipt`
  - `test_partial_analysis_publishes_partial_snapshot`
  - `test_publish_round_trip_through_store`
  - `test_publication_document_is_secret_free`
  - `test_publication_never_imported_by_api_or_simulation`

### Acceptance Criteria

- A present analysis publishes a canonical snapshot with matching counts.
- A missing analysis does not create a false success.
- No API/simulation module imports the publication bridge.

### Verification

- `uv run pytest tests/unit/test_trade_networks_publication.py -q`
- Expected result: all tests pass; import-linter remains clean.

## Phase Risks and Mitigations

- Risk: snapshot models could duplicate analysis validation and drift.
  Mitigation: primitive records plus one mapping test per row family.
- Risk: filesystem stores are easy to make non-atomic.
  Mitigation: reuse the tested temporary-file + replace + flock pattern.
- Risk: a publication could be read before it is complete.
  Mitigation: single atomic `state.json` commit with digest verification.

## Phase Completion Checklist

- Every Task 10-12 acceptance criterion is satisfied.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
