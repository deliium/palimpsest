# Phase 4: Migration-Displacement Snapshot

Plan: [index.md](index.md)
Tasks: 16-17
Depends on: Phase 3 / Tasks 11-15

## Objective

Define the bounded, canonical `migration-displacement-snapshot-v1` document and
its strict codec, then add read and publication ports with six cursor purposes
and bounded paging. The snapshot is additive; it does not rewrite any existing
snapshot or store.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/simulation/borders_models.py` | token helpers 74-123; summary row 124-167; candidate row 168-192; snapshot 439-592; `empty_borders_snapshot` 597 | Exact model pattern to mirror |
| `src/simulation/borders_codec.py` | `canonical_borders_payload` 83-90; digest 99-114; publication id 114-119; finalize 120-162; encode/decode 163-180 | Exact canonical codec pattern |
| `src/simulation/borders_ports.py` | `BordersSummary` 30-44; `BordersPublication` 45-53; `BordersCursor` 54-65; fingerprint 66-87; match 88-93; protocols 104-140 | Exact port and cursor pattern |
| `src/simulation/borders_paging.py` | `BorderRowSelection` 19-24; `page_border_rows` 31-47; `page_border_detail` 48-60 | Exact bounded paging pattern |
| `src/simulation/borders_export.py` | token-only owner export | Bridge from cognition to analysis without a cognition import |
| `src/analysis/borders_contract.py` | forbidden fields 73-96; layer enums 121-147 | Closed vocabulary and forbidden-field pattern |
| `src/api/borders_cursor.py` | HMAC cursor codec | API cursor pattern |
| `tests/unit/test_borders_snapshot.py` | canonical encode/decode, digest, bounds | Test shape to mirror |
| `tests/unit/test_borders_paging.py` | six purposes and bounded pages | Test shape to mirror |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/simulation/migration_displacement_models.py` | create | Snapshot rows, summary, candidate family, bounds, empty snapshot |
| `src/simulation/migration_displacement_codec.py` | create | Canonical payload, JSON, digest, publication id, finalize, encode/decode |
| `src/simulation/migration_displacement_ports.py` | create | Summary, publication, cursor, fingerprint, read/publish protocols |
| `src/simulation/migration_displacement_paging.py` | create | Bounded row/detail paging |
| `tests/unit/test_migration_displacement_snapshot.py` | create | Canonical snapshot and codec |
| `tests/unit/test_migration_displacement_paging.py` | create | Six purposes, cursor binding, bounds |

## Task 16: Define migration-displacement-snapshot-v1 and its canonical codec

### Intent

Produce one immutable, bounded publication document that a read-only API can
serve without importing analysis or reconstructing classifications. The
document carries a required summary row and a candidate row family so lineage
and alignment tokens always resolve.

### Implementation Steps

1. Create `src/simulation/migration_displacement_models.py` with:
   - constants:
     `MIGRATION_DISPLACEMENT_SNAPSHOT_VERSION =
     "migration-displacement-snapshot-v1"`;
     `MIGRATION_DISPLACEMENT_PUBLICATION_PREFIX = "md-pub-"`;
     `MIGRATION_DISPLACEMENT_MAX_BYTES = 4 * 1024 * 1024`.
   - token validators for lowercase `[a-z0-9][a-z0-9-]{0,63}`.
   - `MigrationDisplacementSummaryRow` (required):
     `run_id`, `publication_id`, `digest`, `schema_version`, `policy_version`,
     `candidate_count`, `wave_count`, `cluster_count`, `outcome_count`,
     `movement_count`, `cause_count`, `displacement_like_count`, `mixed_count`,
     `not_displacement_like_count`, `unknown_count`, `integration_settled_count`,
     `integration_transient_count`, `integration_returned_count`,
     `integration_onward_count`, `integration_unknown_count`,
     `coverage`, `unresolved_anchor_count`, `truncated`.
   - `MigrationDisplacementCandidateRow`:
     `candidate_token`, `kind` (`wave`, `cluster`, `outcome`), `status`,
     `first_tick`, `last_tick`, `member_count`, `origin_token`,
     `destination_token`, `classification`, `coverage`.
   - `MigrationMovementRow` (objective): `participant_token`, `origin_token`,
     `destination_token`, `route_tokens`, `start_tick`, `end_tick`,
     `relocation_kind`, `group_size`, `arrival_status`, `coverage`.
   - `MigrationCauseSnapshotRow` (subjective): `owner_token`, `cause_token`,
     `cause_kind`, `source_kind`, `anchor_token`, `confidence`, `tick`,
     `status`.
   - `MigrationRouteSnapshotRow` (subjective): `owner_token`, `route_token`,
     `origin_token`, `destination_token`, `route_tokens`,
     `observed_duration_ticks`, `fatigue_cost`, `basis`, `status`,
     `first_tick`, `last_tick`.
   - `MigrationClusterSnapshotRow` (analytical): `cluster_token`,
     `member_tokens`, `basis_counts`, `coverage`, `first_tick`, `last_tick`.
   - `MigrationWaveSnapshotRow` (analytical): `wave_token`, `origin_token`,
     `destination_token`, `participant_tokens`, `route_tokens`, `start_tick`,
     `end_tick`, `cause_support_counts`, `displacement_classification`,
     `displacement_bases`, `independent_cause_count`, `cluster_tokens`,
     `coverage`.
   - `MigrationOutcomeSnapshotRow` (integration): `outcome_token`,
     `participant_token`, `destination_token`, `residence_ticks`,
     `access_evidence_count`, `participation_evidence_count`,
     `relationship_evidence_count`, `conflict_evidence_count`,
     `classification`, `coverage`, `censored`.
   - `MigrationLineageSnapshotRow`: `candidate_token`, `previous_token`,
     `relation`, `first_tick`, `last_tick`.
   - `MigrationAlignmentSnapshotRow`: `owner_token`, `candidate_token`,
     `alignment`, `basis`.
   - `MigrationMetricProvenanceRow`: `family`, `version`, `document_digest`,
     `coverage`.
   - `MigrationDisplacementSnapshot`: `summary`, `candidates`, `movements`,
     `causes`, `routes`, `clusters`, `waves`, `outcomes`, `lineage`,
     `alignment`, `metric_provenance`, `digest`, `publication_id`,
     `schema_version`, `policy_version`.
2. Validate every row in `__post_init__`:
   - tokens match the token grammar;
   - ticks non-negative and ordered;
   - confidence quantized `[0,1]`;
   - closed labels only;
   - `kind`/`status`/`classification`/`alignment`/`relation` are in their closed
     sets;
   - candidate, lineage, and alignment tokens resolve to a candidate token in
     the same snapshot;
   - no raw `AgentId`/`EntityId`, free text, frame body, cause text, or evidence
     content.
3. Enforce row caps exactly:
   - 1 summary;
   - 2048 candidates;
   - 4096 movements;
   - 4096 causes;
   - 4096 routes;
   - 2048 clusters;
   - 2048 waves;
   - 2048 outcomes;
   - 4096 lineage;
   - 4096 alignment;
   - 64 metric provenance.
4. Add `empty_migration_displacement_snapshot(run_id, *, digest, publication_id,
   policy_version)` for disabled/unavailable receipts.
5. Create `src/simulation/migration_displacement_codec.py` with:
   - `canonical_migration_displacement_payload(snapshot)`;
   - `canonical_migration_displacement_json(snapshot)`;
   - `migration_displacement_snapshot_digest(snapshot)`;
   - `migration_displacement_publication_id(digest)`;
   - `finalize_migration_displacement_snapshot(snapshot)`;
   - `encode_migration_displacement_snapshot(snapshot) -> bytes`;
   - `decode_migration_displacement_snapshot(payload) -> snapshot`.
6. Canonical JSON uses `sort_keys=True`, `separators=(",", ":")`,
   `ensure_ascii=True`, LF, and one trailing newline only for the byte payload.
   The digest covers the canonical payload without `digest`/`publication_id`.
7. Reject an encoded payload over 4 MiB with
   `ValueError("migration_displacement_size_limit")`.
8. Add `__all__` entries.

### Required Interfaces and Contracts

```python
MIGRATION_DISPLACEMENT_SNAPSHOT_VERSION: Final[str] = (
    "migration-displacement-snapshot-v1"
)
MIGRATION_DISPLACEMENT_MAX_BYTES: Final[int] = 4 * 1024 * 1024

@dataclass(frozen=True, slots=True)
class MigrationDisplacementSnapshot:
    summary: MigrationDisplacementSummaryRow
    candidates: tuple[MigrationDisplacementCandidateRow, ...] = ()
    movements: tuple[MigrationMovementRow, ...] = ()
    causes: tuple[MigrationCauseSnapshotRow, ...] = ()
    routes: tuple[MigrationRouteSnapshotRow, ...] = ()
    clusters: tuple[MigrationClusterSnapshotRow, ...] = ()
    waves: tuple[MigrationWaveSnapshotRow, ...] = ()
    outcomes: tuple[MigrationOutcomeSnapshotRow, ...] = ()
    lineage: tuple[MigrationLineageSnapshotRow, ...] = ()
    alignment: tuple[MigrationAlignmentSnapshotRow, ...] = ()
    metric_provenance: tuple[MigrationMetricProvenanceRow, ...] = ()
    digest: str = ""
    publication_id: str = ""
    schema_version: str = MIGRATION_DISPLACEMENT_SNAPSHOT_VERSION
    policy_version: str = "migration-displacement-analysis.v1"
```

- Every lineage/alignment candidate token resolves to a candidate row.
- Every summary count equals the corresponding row count.
- The summary row is required; an empty snapshot still has one.
- Existing `borders-snapshot-v1`, `organized-conflict-snapshot-v1`,
  `diplomacy-snapshot-v1`/`v2`, and their stores are untouched.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — track origin, route, destination, cause evidence,
  clusters, integration outcomes, waves.
- Source: `.ai-factory/ARCHITECTURE.md` — accepted-set / exact-key-set;
  bounded snapshots.
- Source: `src/simulation/borders_models.py` and `borders_codec.py`.
- Supported combinations: empty; one row per family; all labels; max rows;
  over-cap; unresolved lineage token; unresolved alignment token; oversized
  payload; each is tested.

### Error Handling and Logging

- Invalid rows raise `ValueError("migration_displacement_snapshot: <code>")`.
- An unresolved candidate token raises
  `ValueError("migration_displacement_snapshot: unresolved_candidate")`.
- An oversized payload raises
  `ValueError("migration_displacement_size_limit")`.
- Log `DEBUG migration_displacement_snapshot_finalized rows=%s digest_prefix=%s`;
  never log tokens or row contents.

### Tests

- `tests/unit/test_migration_displacement_snapshot.py`
  - `test_snapshot_requires_a_summary_row`
  - `test_summary_counts_match_rows`
  - `test_every_lineage_and_alignment_token_resolves`
  - `test_closed_labels_and_token_grammar`
  - `test_no_raw_identity_or_free_text_is_accepted`
  - `test_row_caps_are_enforced`
  - `test_canonical_digest_and_publication_id_are_stable`
  - `test_encode_decode_round_trip`
  - `test_oversize_payload_is_rejected`
  - `test_existing_snapshots_are_unchanged`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_snapshot.py -q`
- Expected: all pass.

### Acceptance Criteria

- The snapshot is canonical, bounded, and immutable after finalization.
- Summary and candidate families resolve every lineage/alignment token.
- Existing snapshots and stores are untouched.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_snapshot.py -q`
- `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_snapshot.py tests/unit/test_organized_conflict_snapshot.py -q`
- Expected: pass.

## Task 17: Add migration-displacement ports, cursor purposes, and bounded paging

### Intent

Expose a typed read contract for the six API routes without giving the API
analysis authority. Cursors bind the exact publication and query so a stale or
cross-run cursor cannot serve a different page.

### Implementation Steps

1. Create `src/simulation/migration_displacement_ports.py` with:
   - `MIGRATION_DISPLACEMENT_CURSOR_PURPOSES = (
     "summary", "waves", "wave", "routes", "causes", "outcomes")`.
   - `MigrationDisplacementSummary`: `run_id`, `publication_id`, `digest`,
     `schema_version`, counts, coverage.
   - `MigrationDisplacementPublication`: `publication_id`, `digest`,
     `snapshot`.
   - `MigrationDisplacementCursor`: `purpose`, `after_key: str | None`,
     `limit: int`, `fingerprint: str`, `expires_at_tick: int | None`.
   - `migration_displacement_query_fingerprint(*, run_id, publication_id,
     digest, purpose, filters, after_key, limit) -> str` using canonical JSON
     and SHA-256.
   - `migration_displacement_cursor_matches(cursor, fingerprint) -> bool`.
   - `bounded_migration_detail_rows(snapshot, purpose, after_key, limit)`.
   - `MigrationDisplacementReadPort` Protocol:
     `summary`, `waves`, `wave`, `routes`, `causes`, `outcomes`.
   - `MigrationDisplacementPublisherPort` Protocol:
     `publish`, `read_summary`, `read_snapshot`.
2. Create `src/simulation/migration_displacement_paging.py` with:
   - `MigrationRowSelection`: `purpose`, `after_key`, `limit`, `rows`,
     `next_key`.
   - `page_migration_rows(snapshot, selection) -> MigrationRowSelection`.
   - `page_migration_detail(snapshot, purpose, key) -> object | None`.
   - Clamp `limit` to `1..500`; reject `0`, negative, non-int, or greater than
     500 with `ValueError("migration_displacement_page_limit")`.
   - Sort rows by stable keys:
     waves by `(start_tick, wave_token)`;
     routes by `(owner_token, first_tick, route_token)`;
     causes by `(owner_token, tick, cause_token)`;
     outcomes by `(participant_token, destination_token, outcome_token)`;
     summary is a single row.
3. Cursor binding includes run id, publication id, digest, purpose, filters,
   after key, and limit. A mismatch returns `False` from
   `migration_displacement_cursor_matches`.
4. A detail lookup returns `None` for an unknown token; the API maps it to 404.
5. No port builds or repairs a snapshot; it reads the committed publication.

### Required Interfaces and Contracts

```python
MIGRATION_DISPLACEMENT_CURSOR_PURPOSES: Final[tuple[str, ...]] = (
    "summary",
    "waves",
    "wave",
    "routes",
    "causes",
    "outcomes",
)
MAX_PAGE_LIMIT: Final[int] = 500
```

- Six purposes, no more.
- A cursor is opaque; it carries no raw identity.
- A changed run, publication, digest, purpose, filter, after key, or limit
  invalidates the cursor.
- Expiry is an absolute tick; the API maps it to 410.
- Paging never reorders a published snapshot.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — read-only research tracking.
- Source: `src/simulation/borders_ports.py` 54-140; `borders_paging.py` 19-60.
- Supported combinations: each purpose; empty page; last page; limit 1; limit
  500; limit 501; invalid cursor; changed publication; changed digest; expiry;
  each is tested.

### Error Handling and Logging

- Invalid limit raises `ValueError("migration_displacement_page_limit")`.
- Unknown purpose raises `ValueError("migration_displacement_cursor_purpose")`.
- Cursor mismatch logs `WARN migration_displacement_cursor_invalid` without the
  cursor body.
- Log `DEBUG migration_displacement_page purpose=%s rows=%s` with counts only.

### Tests

- `tests/unit/test_migration_displacement_paging.py`
  - `test_six_cursor_purposes_exist`
  - `test_page_limit_is_bounded`
  - `test_rows_are_sorted_by_stable_keys`
  - `test_cursor_binds_run_publication_digest_purpose_filters_and_limit`
  - `test_changed_binding_does_not_match`
  - `test_detail_lookup_returns_none_for_unknown_token`
  - `test_paging_never_reorders_a_published_snapshot`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_paging.py -q`
- Expected: all pass.

### Acceptance Criteria

- Exactly six purposes exist.
- Paging is bounded and deterministic.
- Cursor reuse works only for the same binding.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_paging.py -q`
- `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_paging.py -q`
- Expected: pass.

## Phase Risks and Mitigations

- Risk: the snapshot becomes a second analysis engine.
  Mitigation: Task 16 only mirrors already-derived rows; it never imports
  analysis.
- Risk: lineage or alignment tokens dangle.
  Mitigation: Task 16 requires every token to resolve to a candidate.
- Risk: a cursor serves a page from a different publication.
  Mitigation: Task 17 binds run, publication, digest, purpose, filters, after
  key, and limit.
- Risk: existing stores are rewritten.
  Mitigation: new module names and new version strings only; existing snapshot
  tests stay green.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
