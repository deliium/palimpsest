# Phase 4: Verified cold copies and physically paged lineage/history artifacts

Plan: [index.md](index.md)
Tasks: 10–12
Depends on: Tasks 3, 7–9

## Objective

Provide a verified offline historical read tier and make existing lineage/civilization continuation physically bounded. Preserve every original scientific row and immutable publication.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/persistence/sqlalchemy.py` | snapshot insert/load 792/913 | Canonical payload and normalized projection rows both exist; do not silently change authoritative storage. |
| `src/persistence/lineage_filesystem.py` | `_encode_snapshot_files` 359; `neighbors` 994; `node_page` 1045 | Adjacency is one large file; page readers can load all preceding data. |
| `src/simulation/lineage_capture.py` | `_read_previous` 248–281 | Only one 200-neighbor page per node is consumed; investigate with a high-degree preservation regression. |
| `src/persistence/civilization_filesystem.py` | row reader 813–850 | Shards are read/hashed before cursor skipping. |
| `src/simulation/lineage_ports.py`, `src/simulation/civilization_ports.py` | read and publication budgets | Preserve physical-read/byte quotas and explicit partial coverage. |
| `src/simulation/lineage_codec.py` | `LINEAGE_MANIFEST_MAX_BYTES` 75; `LineageSnapshotManifest.page_digests` 502 | A flat digest list can exceed the root metadata budget even when individual data reads are paged. |
| `src/research_runner/cli.py` | `build_parser` 1033 | Add offline commands at the existing CLI composition root, not HTTP. |
| `docs/persistence.md` | append-only/export contracts | Cold copies never authorize deleting source history. |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/simulation/history_archive.py` | create | New neutral archive manifest/segment contracts and read/export ports. |
| `src/persistence/history_archive_filesystem.py` | create | Immutable segmented copy writer and bounded read-only journal/snapshot adapter. |
| `src/research_runner/history_archive_composition.py` | create | SQL→archive export and replay verification composition. |
| `src/research_runner/cli.py` | modify | `history-export` and `history-verify` subcommands. |
| `src/persistence/lineage_filesystem.py`, `src/simulation/lineage_capture.py` | modify | Fully consumed continuations and indexed physical pages. |
| `src/simulation/lineage_codec.py` | modify | Extend explicit manifest-version dispatch around `LineageSnapshotManifest`; keep logical lineage DTO schema unchanged. |
| `src/simulation/lineage_store_index.py` | create | Strict v2 root/index-page contracts and bounded authenticated directory traversal. |
| `src/persistence/civilization_filesystem.py` | modify | Versioned shard-range directory and cursor-first physical selection. |
| `src/simulation/civilization_models.py`, `src/simulation/civilization_codec.py` | modify | Separate strict v2 physical root/index metadata, keeping old hash manifests/logical rows decodable. |
| `tests/unit/test_history_archive.py`, `tests/integration/test_history_archive.py` | create | Cold-copy parity and fail-closed corruption tests. |
| `tests/unit/test_lineage_filesystem.py`, `tests/unit/test_lineage_limits.py`, `tests/unit/test_civilization_filesystem.py` | modify | Deep-cursor, high-degree and physical-read budgets. |

## Task 10: Export immutable segmented historical copies and verify offline replay

### Implementation Steps

1. Introduce strict `objective-history-archive-v1` manifest and `objective-history-segment-v1` segment metadata. Record run/world identity, accepted event/projector/codec identifiers, manifest identity, pinned end commit, segment first/last tick+sequence, row/byte counts, predecessor/end commit hashes and content digests. Keep events, commits and snapshots in separate canonical lanes using existing codecs.
2. Export under one pinned verified durable head using Task 7 keysets. Split event and commit lanes at configured positive row/byte limits, never truncating a record. A single oversized record is a safe error, not dropped evidence. Include compatible snapshots with original canonical hashes. Segment boundaries may split a tick; manifest coverage must represent that exactly.
3. Write content-addressed files first, then an immutable manifest, then one atomic committed reference. Uncommitted files are not discoverable. Retry of identical input reuses verified objects; conflicting content at the same identity fails. Reject symlinks/path escapes, enforce maximum record/manifest sizes, and never deserialize pickle or executable objects.
4. Implement a read-only adapter for snapshot lookup, pinned head, commit/event keyset pages and event-ID lookup. Use sorted tick/identity index pages so deep historical lookup reads only required segments; charge compressed and decompressed bytes if compression is enabled. This task uses uncompressed canonical segments by default; optional filesystem compression is not needed to establish correctness.
5. `history-export --run-id ... --output ...` composes only existing configured SQL readers and the filesystem writer. `history-verify --archive ...` validates all file hashes, run/schema identity, complete commit/event coverage and sampled replay/observation parity, with an explicit full verification option. No source mutation, source cleanup, SQL failover, API route or automatic cold routing.
6. Trace/subjective data are not folded into objective segments. Copy already-versioned trace/evidence/publication artifacts as independently hashed siblings with their original availability and capability classification. Omitted/disabled evidence is declared, never reconstructed from objective events. Filesystem permissions must protect subjective copies; a path is not an authorization credential.

### Required Interfaces and Contracts

The offline adapter can be supplied explicitly to `ReplayService` in CLI/tests. It rejects append operations. An archive is a queryable copy, not a durable subjective continuation bundle or a replacement authority while SQL remains primary. Original rows, snapshots, triggers and committed publications remain untouched. Auxiliary indexes are rebuildable from retained data; indexes are not substitutes for evidence.

### Requirement Evidence

User: cold storage, historical access, immutable provenance and streaming. Architecture: ports, accepted codecs, no analysis↔persistence imports. `docs/persistence.md`: export-copy-only retention.

### Error Handling and Logging

Fail closed on any missing/tampered required segment, discontinuity, schema mismatch or path violation; do not silently query SQL to hide archive corruption. INFO lane/segment counts, bytes and verified boundary; DEBUG durations. No payload/DSN/credential logs. Partial export failure leaves source intact and no committed archive reference.

### Tests

Round-trip eventless and high-event ticks; split ticks; legacy/current codecs; missing segment; wrong run; decompression bomb if compressed readers are later enabled; interrupted publication; duplicate retry; event-ID index beyond first segments; long-dead objective queries after process restart. Guarded integration asserts source row counts/hashes unchanged and archive replay equals SQL at death/checkpoint/final boundaries.

### Acceptance Criteria and Verification

`uv run pytest tests/unit/test_history_archive.py --cov=simulation --cov=persistence --cov=research_runner --cov-report=term`; then `uv run pytest -m integration tests/integration/test_history_archive.py --cov=simulation --cov=persistence --cov=research_runner --cov-report=term`. `uv run palimpsest-matrix history-verify --archive /tmp/opencode/v3-43-scale/archive --full` succeeds for a completed export and fails for tampered input.

## Task 11: Preserve all lineage continuations and paginate adjacency physically

### Implementation Steps

1. Add the high-degree regression before editing capture. Construct a retained archived graph where relevant edges cannot be accidentally recovered through another enumerated endpoint. Iterate every neighbor continuation in `_read_previous`, deduplicate by exact edge identity, reject repeated/nonadvancing cursors, and preserve coverage if capture budget is exhausted. Never publish a complete graph after an incomplete merge.
2. Introduce strict physical layout marker `lineage-store-index-v2`, separate from logical `lineage-snapshot-v1`, with a new `LineageStoreRootV2` rather than widening the exact v1 `LineageSnapshotManifest`. The v2 root contains fixed context/coverage/counts and only fixed-purpose root references for node catalogue, adjacency, identity lookup and object integrity; it must not retain a flat digest per descendant file. Index pages contain at most 256 entries and also obey existing metadata/record byte caps; entries contain exact first/last composite sort key, subtree count/bytes and child digest. Build extra directory levels bottom-up when one page would exceed either cap. A root-to-leaf lookup verifies each digest/range and charges every index page to the existing read budget. Root/index JSON depth and metadata bytes remain within current limits; do not solve root growth by raising `LINEAGE_MANIFEST_MAX_BYTES`.
   Keep explicit v1/v2 root codec dispatch, old v1 publication hashing and readers. Derive new v2 publication IDs from its closed root context and authenticated directory roots; logical graph digest stays based on the unchanged full projection. The entire directory tree and data objects are written before the atomic committed reference. Never rewrite old publication files or silently add fields under old schema IDs.
3. Physically split adjacency in the exact existing continuation order `(observed_tick or 0, edge_key)` and direction semantics. Split by both row and byte caps. `neighbors` selects the relevant indexed pages before reading edges and loads endpoint descriptors only for candidate rows within the requested scan/response budget.
4. Store catalogue range indexes for `node_page`; select pages by continuation first, then apply eligibility filters. Empty continuation pages, `scan_limited`, count meanings and archived presence remain unchanged. No omitted node can become known absent just because a resource budget was reached.
5. Reuse byte-identical node/edge/index page objects by content address across new publications where possible. This is lossless physical deduplication, not collapsing roots, merging people/techniques/institutions or replacing edges with a summary. Preserve owner-qualified identity, all edge metadata, ambiguity and structural witnesses. Keep cumulative publication/logical-reservation quota semantics unchanged: physical object reuse does not reset quota counters or allow more logical evidence than the configured cap. Measure unique physical bytes and charged logical bytes separately.
6. Keep request-local decoded index caches with explicit byte accounting in the existing read session. Do not retain complete graphs in an API-global cache. Old formats may retain legacy read costs; display/measure those separately rather than mutating sealed snapshots.

### Required Interfaces and Contracts

Unchanged lineage API, signed cursor scope/TTL, eight families, authorization and logical digest. Physical layout identity participates in publication fingerprinting so cursors cannot silently traverse a different representation. Existing budgets are not raised to hide unbounded reads. New continuation starts near its index position, not catalogue page zero.

### Requirement Evidence

User: genealogy/technology/institution lineage scaling and lossless compression. `lineage_capture.py` archival merge; existing lineage cursor/budget contracts.

### Error Handling and Logging

Tampered range indexes are storage corruption, not missing history. Budget exhaustion reports the existing bounded/partial state and usable continuation if valid. INFO publication counts; DEBUG physical files/source bytes/decoded endpoints. No owner labels or narrative payloads.

### Tests

Degree >200 across several physical pages; BOTH/ancestor/descendant ordering; sparse filtered pages; deep catalogue cursor; archived edges survive successive captures; old-v1/new-v2 parity; count/digest equality; cursor replacement; corrupt index/child; byte and read-count budgets; cross-owner forbidden access. Add a graph whose equivalent v1 flat digest list exceeds 256 KiB while each v2 root/index page remains within existing caps, then perform exact deep lookup/traversal. Verify missing/swapped directory child, overlapping ranges, wrong subtree counts, atomic interrupted publication, deduplicated-object integrity and unchanged logical quota charging.

### Acceptance Criteria and Verification

`uv run pytest tests/unit/test_lineage_filesystem.py tests/unit/test_lineage_limits.py --cov=simulation --cov=persistence --cov-report=term` passes. Exact deep lookup/read-count assertions remain bounded by relevant index/data pages rather than preceding catalogue size.

## Task 12: Index civilization shard ranges before reading old pages

### Implementation Steps

1. Introduce separate strict physical marker `civilization-store-index-v2` with a bounded root and authenticated paged directory, not a flat `CivilizationHashManifest.children` entry for every shard. Use the same capped fanout/byte-bounded bottom-up tree pattern as Task 11, specialized to `(scope, row_id)` and boundary catalogue sort keys. Directory entries carry scope-qualified shard first/last row IDs, subtree counts/bytes and original content digests. Every root/index page obeys existing civilization metadata caps and read-budget charging. Publish it child-first under the existing atomic state reference; preserve v1 reader/hash dispatch and all logical civilization snapshot/row schemas.
2. Change deep row pagination to binary-search authenticated range metadata before reading/hashing candidate shards. Validate ranges are ordered/nonoverlapping and consistent with decoded selected shard endpoints. Filtered requests advance an honest scan cursor and may return empty continuation pages without re-reading old shards.
3. Keep existing response/scanned-row/physical-read budgets. Budget metadata reads and decompressed contents as applicable; byte-bounded request-local manifest caches cannot skip integrity checks. Use no cross-credential private response cache.
4. Add repeated deep historical boundary and row lookup tests against the real publisher/reader. Include records, culture, technology and institution rows for long-dead owners; unavailable capture remains unavailable, not an empty layer.
5. Record logical/physical bytes saved and read amplification. Investigate further materialized views and partitioned cold directories in the cost ledger, but keep this fixed indexed-shard architecture; no DB table partitioning or mutable analytical registry.

### Required Interfaces and Contracts

Existing immutable publication IDs, evidence classes, quota accounting, original rows, GET-only API and cursor fingerprints remain. Physical layout metadata is versioned explicitly; no change to `observer-protocol-v1` or runner/result schemas.

### Requirement Evidence

User: bounded historical queries, partitioning investigation and provenance retention. Existing reader's pre-skip hashing is the concrete target.

### Error Handling and Logging

Corrupt/overlapping index or wrong child hash fails closed. Continuation/budget results keep their existing distinctions. DEBUG files/rows/bytes and duration; no private labels/marks.

### Tests

Deep page after more shards than the old per-request read ceiling; sparse filter continuation; first/last/between-boundary query; old/new formats; tampered range versus child; repeated reads with bounded cache; concurrent new publication pinned to old cursor. Include enough shards to overflow a flat metadata manifest and prove v2 root/index pages stay below current metadata limits, with charged logarithmic directory descent and only relevant data-shard reads. Preserve logical quota charging despite reused physical objects.

### Acceptance Criteria and Verification

`uv run pytest tests/unit/test_civilization_filesystem.py --cov=simulation --cov=persistence --cov-report=term` passes; `uv run pytest -m 'integration and scale' tests/benchmarks/test_civilization_playback.py --cov=persistence --cov=api --cov-report=term` measures selected-page physical reads, not merely stable returned row counts.

## Phase Risks and Mitigations

- New physical versions can strand old artifacts: dispatch by explicit marker, keep v1 fixtures and never rewrite sealed publications.
- Deduplication can be mistaken for lost provenance: compare complete logical graphs/rows and archive digests, not only totals.
- Copy-only cold storage increases total disk initially: measure duplicate bytes; do not promise disk reclamation or relax triggers.

## Phase Completion Checklist

- Tasks 10–12 pass old/new format, corruption, deep-pagination and long-dead-query tests.
- All original scientific history remains intact.
- Update progress only in `index.md`.
