# Phase 5: Composition and Durable Publication

Plan: [index.md](index.md)
Tasks: 17-18
Depends on: Phase 4

## Objective

Compose completed-run treaty views into `diplomacy-snapshot-v2`, publish them
atomically through the existing `diplomacy-store-v1`, and keep publication
opt-in, post-completion, quota-bounded, and isolated from scientific status.
V1 publications remain readable.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/experiments/diplomacy_publication.py` | `DiplomacyHarvestResult` 62-68; `_receipt` 70-82; `_snapshot` 85-324; `build_diplomacy_harvest_result` 327-379; `publish_diplomacy_snapshot` 382-414; `diplomacy_publication_document` 417+ | Exact composition, receipt, and failure-isolation pattern. |
| `src/experiments/diplomacy_harvest.py` | `DiplomacyHarvest` 31-42; `build_completed_run_diplomacy_harvest` 50-88 | Harvest object to extend with treaty rows and alignment. |
| `src/persistence/diplomacy_filesystem.py` | `FilesystemDiplomacyPublisher` 83-141; `_encode` 144-147; `FilesystemDiplomacyReader` 150-202; `DIPLOMACY_STORE_SCHEMA` | Atomic commit, publication dedupe, quotas, and reader v1/v2 support. |
| `src/research_runner/diplomacy_composition.py` | `DIPLOMACY_ROOT_ENV` 31; `DiplomacyProducerOptions` 44-52; `publish_diplomacy_harvest` 79+ | Opt-in CLI producer that must emit v2 without touching results. |
| `src/simulation/diplomacy_codec.py` | `finalize_diplomacy_snapshot` 133-173; `encode` 176-185 | Snapshot finalization and byte cap. |
| `tests/unit/test_diplomacy_publication.py` | completion, failure, receipt tests | Exact receipt and non-interference tests to extend. |
| `tests/unit/test_diplomacy_store.py` | atomic/quota tests | Store behavior to extend for v2. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/experiments/diplomacy_harvest.py` | modify | Include treaty rows, version lineage, and recollection alignment in `DiplomacyHarvest`. |
| `src/experiments/diplomacy_publication.py` | modify | Build v2 treaty rows/lineage and extend receipts with treaty counts. |
| `src/persistence/diplomacy_filesystem.py` | modify | Accept v1/v2 snapshots; keep store schema and quotas; expose treaty read methods. |
| `src/research_runner/diplomacy_composition.py` | modify | Publish v2 and return treaty counts in the CLI receipt. |
| `tests/unit/test_diplomacy_treaty_publication.py` | create | Completed-run composition, receipts, failure isolation. |
| `tests/unit/test_diplomacy_treaty_store.py` | create | Atomic v2 publication, v1/v2 reads, quotas, duplicate bytes. |

## Task 17: Compose completed-run treaty views and receipts

### Intent

Produce one canonical v2 snapshot from the completed-run harvest. The composer
derives current treaty/version statuses, includes retained declarations and
recollections, emits version lineage, and records treaty metric provenance.
Publication readiness is separate from scientific status.

### Implementation Steps

1. Extend `DiplomacyHarvest` with:
   - `treaties`, `treaty_versions`, `treaty_declarations`,
     `treaty_recollections`, `treaty_misrepresentations`, `treaty_lineage`
     (analysis rows);
   - `treaty_alignment` (researcher-only rows);
   - `treaty_statuses` (derived `(treaty_id, version_id, status, basis)`
     tuples from the owner ledgers).
   Append every new field with an empty-tuple default so existing constructors
   remain valid, then populate them in
   `build_completed_run_diplomacy_harvest` without changing existing fields.
2. In `_snapshot`, after the existing V4-10 rows, append:
   - `DiplomacySnapshotTreatyRow` from each treaty, with owner token,
     participant tokens, subject kind, current version ID, current derived
     status, ticks, and provenance;
   - `DiplomacySnapshotTreatyVersionRow` from each version, with the exact
     provision kinds, terms digest, record refs, institutional-memory refs,
     proposer token, ticks, derived `status`, and `acceptance_basis`;
   - `DiplomacySnapshotTreatyDeclarationRow` from each declaration;
   - `DiplomacySnapshotTreatyRecollectionRow` from each recollection;
   - `DiplomacySnapshotTreatyMisrepresentationRow` from each observation;
   - `DiplomacySnapshotTreatyLineageRow` from each lineage edge.
   Use content-addressed IDs from the ledger where available; for rows whose
   analysis projection loses the local ID, mint a deterministic snapshot ID
   from the sorted tuple, the same way V4-10 remaps parties/envoys.
3. When a treaty/version/declaration/recollection ID must be reminted to a
   snapshot ID, build one `owner -> record` id table before constructing rows
   and map every referencing field through it: declaration `treaty_id`/
   `version_id`, recollection `treaty_ref`/`version_ref`, misrepresentation
   `version_id`, and lineage `from_version_id`/`to_version_id`. Add a test that
   every v2 reference resolves inside the same snapshot.
4. Extend `_receipt` with `treaties`, `treaty_versions`,
   `treaty_accepted`, and `treaty_recollections` integer counts. Keep
   status/reason/publication/digest and existing counts unchanged.
5. Extend `diplomacy_publication_document` with the same treaty counts. Keep
   the document schema and status vocabulary unchanged.
6. Derive current treaty/version statuses at composition time using the
   owner's representation ledger. Do not trust an accreditation-time status.
   Set `treaty.status` to the current version's status; set each version's
   `status`/`acceptance_basis` from Task 6. The summary's
   `treaty_accepted_count` is the count of version rows with
   `apparently_accepted`.
7. Include the four treaty metric family documents in the snapshot
   `metric_provenance` rows and `metric_families` tuple. If a family is
   absent, omit it; never invent a zero-value document.
8. On composition error, return `status="failed"` with the stable code and
   `snapshot=None`; the scientific result is untouched.
9. On incomplete stop codes, return `status="unavailable"` with reason
   `diplomacy_run_incomplete`.
10. Type every new harvest field and snapshot row concretely. Where a port or
    runner result exposes `tuple[object, ...]`, narrow with `cast` or
    `isinstance` before reading treaty fields; do not add `# type: ignore`.
11. On no treaty or diplomacy rows, keep the existing `disabled` behavior; a
    diplomacy run with only V4-10 rows still publishes v2 with empty treaty
    tuples.

### Required Interfaces and Contracts

- V2 snapshot is the only new document emitted by V4-11.
- Receipts remain metadata-only: counts, status, stable reason codes. Never
  include treaty/version IDs, participants, terms, anchors, or digests beyond
  the existing publication digest.
- Publication never changes `runner_result`, stop reason, experiment status,
  or metric scientific status.
- `published` is true only after a successful store commit.
- A failed publication leaves the snapshot available in the result object but
  does not claim success.

### Requirement Evidence (when reconciliation applies)

- `.ai-factory/ARCHITECTURE.md` "analysis is read-only" and V4-10 publication
  isolation.
- Original Request "Treaties must exist through records, participants,
  recognized representatives, institutional memory, agent beliefs" requires
  the snapshot to carry each visible dimension.
- `src/experiments/diplomacy_publication.py` 327-414.

### Error Handling and Logging

- Stable receipt reasons: `diplomacy_run_incomplete`,
  `diplomacy_input_unavailable`, `diplomacy_size_limit`, or the artifact error
  code.
- Log `treaty_publication state=ready treaties=%s versions=%s` and
  `treaty_publication state=published` at INFO with counts only.
- Log `treaty_publication state=failed reason=<code>` at ERROR; never the
  exception payload.

### Tests

`tests/unit/test_diplomacy_treaty_publication.py`:

- Completed run with treaties/versions/declarations/recollections/lineage
  produces a v2 snapshot with exact rows.
- Receipts include treaty counts and no private identifiers.
- Incomplete stop -> `unavailable`; composition error -> `failed`; no
  scientific field changes.
- Publication failure changes only the receipt.
- A diplomacy run with zero treaty rows publishes v2 with empty tuples.
- `DiplomacyHarvest` and `DiplomacyHarvestRows` still construct without treaty
  fields and report empty treaty values.
- If any treaty/version ID is reminted, every declaration, recollection,
  misrepresentation, and lineage reference resolves in the same snapshot.
- A v1-only legacy artifact remains readable and is not rewritten.
- Metric provenance includes the four treaty families when present.

### Acceptance Criteria

- Completed-run composition emits v2 with every treaty row family.
- Receipts are additive and metadata-only.
- Publication failure never changes scientific status.
- V1 artifacts remain untouched.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_diplomacy_treaty_publication.py tests/unit/test_diplomacy_publication.py -q`
- Expected: all tests pass.

## Task 18: Extend the filesystem store and CLI producer

### Intent

Store and serve v1 and v2 through the existing atomic store without a new store
schema. The CLI producer publishes v2 opt-in and returns treaty counts.

### Implementation Steps

1. In `persistence/diplomacy_filesystem.py`:
   - keep `DIPLOMACY_STORE_SCHEMA = "diplomacy-store-v1"`;
   - `FilesystemDiplomacyPublisher.publish` accepts any supported snapshot
     schema (v1/v2) and writes it unchanged;
   - duplicate `publication_id` handling stays: identical bytes are idempotent;
     different bytes raise `diplomacy_publication_exists`;
   - `FilesystemDiplomacyReader._snapshot` uses
     `decode_diplomacy_snapshot`, which dispatches v1/v2;
   - add `treaties_page`, `treaty_detail`, and `treaty_versions_page` methods
     that delegate to Task 16 selectors;
   - extend `read_summary` with treaty counts; compute
     `treaty_accepted_count` from version rows whose stored `status` is
     `apparently_accepted`;
2. In `research_runner/diplomacy_composition.py`:
   - `publish_diplomacy_harvest` builds a v2 snapshot through Task 17;
   - the returned receipt includes treaty counts;
   - `--diplomacy-root` / `PALIMPSEST_DIPLOMACY_ROOT` remains the only
     enablement;
   - the CLI never imports analysis or API and never starts HTTP.
3. Do not add new settings, root keys, store versions, or file layouts. Store
   v2 snapshots under `publications/<publication_id>.json` exactly as v1.
4. Keep the atomic temporary-write + `os.replace` + `state.json` commit order.
   Preserve the publish lock and cumulative byte quota.
5. Keep v1 publication bytes byte-identical when read; never re-encode or
   upgrade an existing v1 artifact in place.

### Required Interfaces and Contracts

- Store schema remains `diplomacy-store-v1`.
- V1 and v2 snapshots coexist under one root.
- Quotas count bytes across both schemas.
- The reader selects the latest publication for a run and validates its digest.
- The CLI receipt statuses remain `disabled`, `unavailable`, `ready`,
  `published`, `failed`.
- No SQL, HTTP, or analysis import.

### Requirement Evidence (when reconciliation applies)

- `.ai-factory/ARCHITECTURE.md` "Persistence" and V4-10 store seam.
- V4-04/V4-05 organization store serving v1/v2/v3 precedent.
- Original Request "records ... institutional memory" requires durable,
  atomic publication.

### Error Handling and Logging

- Quota errors keep `diplomacy_quota_exceeded`; duplicate bytes keep
  `diplomacy_publication_exists`; digest mismatch keeps
  `diplomacy_publication_digest_mismatch`.
- Log `diplomacy_store_published schema=diplomacy-snapshot-v2` at INFO without
  run/publication IDs.
- Log quota/failure at WARN/ERROR with stable codes only.

### Tests

`tests/unit/test_diplomacy_treaty_store.py`:

- Publish v2, read it back, and assert digest/publication identity.
- Publish v1 and v2 under one root; both read correctly.
- Duplicate publication with identical bytes is idempotent; different bytes
  fail.
- Quota cap counts both schemas.
- Atomic failure leaves no partial state and no partial `state.json`.
- Reader summary includes treaty counts.
- CLI producer disabled/unavailable/ready/published/failed paths.
- No analysis import in persistence or research_runner producer.

### Acceptance Criteria

- Store schema remains v1 and serves both snapshot schemas atomically.
- CLI producer emits v2 opt-in and never affects scientific status.
- V1 artifacts are never rewritten.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_diplomacy_treaty_store.py tests/unit/test_diplomacy_store.py -q`
- Expected: all tests pass.

## Phase Risks and Mitigations

- Risk: V2 composition accidentally rewrites V1 rows.
  Mitigation: append treaty rows after existing rows; v1 decode path remains
  separate.
- Risk: A receipt leaks treaty identifiers.
  Mitigation: receipts carry only integer counts, status, reason, publication
  digest.
- Risk: Store quotas are bypassed by v2.
  Mitigation: byte and publication counts are schema-agnostic; tests cover
  mixed roots.
- Risk: CLI publication changes the runner result.
  Mitigation: publication consumes a completed result and returns a separate
  receipt; tests assert the result object is untouched.

## Phase Completion Checklist

- Every Task 17-18 acceptance criterion is met.
- V2 composition is complete and metadata-only.
- Store schema is unchanged and both schemas are served atomically.
- CLI publication is opt-in and isolated.
- `index.md` checkboxes are updated only after verification passes.
