# Phase 6: Composition and Durable Publication

Plan: [index.md](index.md)
Tasks: 12-13
Depends on: Phase 3 (Task 7), Phase 5 (Tasks 10-11)

## Objective

Map a completed run's detached evidence into a macro-society snapshot and store
it atomically with quotas. Composition happens in `experiments`; storage happens
in `persistence`; neither the engine nor the API participates.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/experiments/lineage_publication.py` | `AnalyticalLineageInputs`, `CompletedLineageHarvest`, `publish_analytical_lineage`, `publish_completed_lineage` | Completed-run harvest → artifact publication bridge. |
| `src/experiments/civilization_publication.py` | composition bridge from retained capture to analysis calculators | Precedent for analysis-owned calculators behind an experiments composer. |
| `src/persistence/lineage_filesystem.py` | `FilesystemLineagePublisher`, `FilesystemLineageReader`, `_RunLock`, `_atomic_write`, pending reservation, quota accounting | Atomic, quota-bounded, crash-recoverable store pattern. |
| `src/persistence/civilization_filesystem.py` | single atomic `state.json` commit point, child-first hashing | Alternative publication model. |
| `src/persistence/__init__.py` | adapter export convention | Where the new adapters are exposed. |
| `tests/unit/test_lineage_filesystem.py` | lock, atomicity, quota, recovery cases | Test shape to mirror. |
| `tests/unit/test_lineage_noninterference.py` | failure isolation from scientific execution | Non-interference contract to copy. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/experiments/macro_society_publication.py` | create | Harvest inputs, analysis build, artifact mapping, publish entry point. |
| `src/experiments/__init__.py` | modify | Export public names. |
| `src/persistence/macro_society_filesystem.py` | create | Atomic publisher and reader with quotas. |
| `src/persistence/__init__.py` | modify | Export adapters. |
| `tests/unit/test_macro_society_publication.py` | create | Mapping and non-interference proofs. |
| `tests/unit/test_macro_society_filesystem.py` | create | Atomicity, quota, recovery proofs. |

## Task 12: Compose completed-run harvests into snapshots

### Intent

One deterministic mapping from analysis to artifact. The bridge is the only
place that knows both vocabularies, so neither layer imports the other's
internals.

### Implementation Steps

1. Create `src/experiments/macro_society_publication.py` importing
   `analysis.macro_society_*`, `simulation.macro_society_*`, and standard
   library helpers. It must not import `api`, `persistence`, `infrastructure`, or
   `observer`.
2. Define `@dataclass(frozen=True, slots=True) class MacroSocietyHarvest` with
   `run_id`, `input_revision`, `windows: tuple[MacroSocietyWindowEvidence, ...]`,
   `objective_rows: tuple[MacroSocietyObjectiveRow, ...]`,
   `subjective_rows: tuple[MacroSocietySubjectiveRow, ...]`, `generated_tick`.
   Validation: non-empty windows, strictly increasing window indexes, bounded by
   the analysis caps, string ids validated with `require_stable_id`.
3. Define `@dataclass(frozen=True, slots=True) class MacroSocietyHarvestResult`
   with `analysis: MacroSocietyAnalysis`, `snapshot: MacroSocietySnapshot`,
   `publication_id: str`, `snapshot_bytes: int`.
4. Implement `build_macro_society_harvest_result(harvest) -> MacroSocietyHarvestResult`:
   1. `detect_macro_society_candidates` per window.
   2. `project_macro_society_layers` per window with the harvest's objective and
      subjective rows filtered to that window's known persons.
   3. `assign_macro_society_identities`, then
      `build_macro_society_analysis`.
   4. Map analysis records to `MacroSocietyCandidateRecord` (bounded member
      lists; when a candidate exceeds `MAX_SNAPSHOT_MEMBERS`, truncate
      deterministically by sorted member id and record
      `provenance_code="member_list_truncated"`).
   5. Map windows, edges, and objective rows.
   6. Encode the snapshot, compute the publication id, return the result.
5. Implement `publish_macro_society_snapshot(*, harvest, port: MacroSocietyPublicationPort) -> MacroSocietySnapshotRef`
   that builds the result and calls `port.publish`. It never catches storage
   errors silently: failures propagate to the caller, which reports them as a
   non-scientific publication failure.
6. Implement `macro_society_publication_document(result) -> dict[str, object]`
   for CLI receipts: schema version, publication id, digest, candidate count,
   edge count, window count, coverage ratios, `member_list_truncated` flag. No
   member ids.
7. Assert non-interference by construction: this module is never imported by
   `simulation`, `api`, or `persistence`, and it does not mutate the harvest.

### Required Interfaces and Contracts

- Truncation is deterministic and disclosed; it never silently drops evidence
  without setting `provenance_code`.
- The mapping is total: every analysis record becomes exactly one candidate
  record, every edge exactly one edge record.
- The snapshot digest is computed before publication and never recomputed after.

### Error Handling and Logging

- Reuse `MacroSocietyError` and `MacroSocietyArtifactError`; add no new codes.
- `INFO macro_society_published run=%s publication=%s candidates=%s edges=%s bytes=%s`
  on success (counts and safe ids only).
- `WARN macro_society_publication_incomplete reason_code=%s` when coverage is
  partial; the publication still succeeds if the schema is valid.

### Tests

`tests/unit/test_macro_society_publication.py`:
- A two-window harvest yields one snapshot with the expected candidate and edge
  counts, and `publication_id` is stable across repeated builds.
- A candidate with 600 members is truncated to 512 with
  `provenance_code="member_list_truncated"`.
- Objective rows without matching persons are preserved as counts (no identity).
- An empty window list raises the documented code.
- A stub publisher receives exactly one publication and its id matches the
  result.
- Importing the module does not import `api`, `persistence`, or `observer`
  (AST/sys.modules check).

### Acceptance Criteria

- One call produces one artifact and one publication attempt.
- The receipt document contains no member or owner ids.
- Publication failure never alters the analysis result.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_macro_society_publication.py -q`
- `uv run --frozen --python 3.12.14 pytest tests/unit/test_lineage_noninterference.py -q`

## Task 13: Implement the atomic quota-bounded filesystem store

### Intent

Durable snapshots must be crash-safe and bounded so a research run cannot fill a
disk or leave a half-written state. The store is a dumb adapter: it validates
bytes, writes once, and serves pages.

### Implementation Steps

1. Create `src/persistence/macro_society_filesystem.py` importing
   `simulation.macro_society_*`, the standard library, and `persistence`
   helpers. It must not import `analysis`, `experiments`, `api`, or `observer`.
2. Layout under `<root>/<run_id>/`:
   - `state.json` — `{"store_schema_version", "run_id", "publication_id",
     "snapshot_digest", "catalogue_generation", "publications": <count>,
     "total_bytes": <int>}`; the only commit point.
   - `publications/<publication_id>/snapshot.json` — immutable snapshot bytes.
   - `publications/<publication_id>/manifest.json` — `{"publication_id",
     "snapshot_digest", "run_id", "created_at_utc"}` (metadata only).
3. `class FilesystemMacroSocietyPublisher(MacroSocietyPublicationPort)`:
   - Constructor caps `max_publications` (default `16`) and `max_artifact_bytes`
     (default `8 MiB`).
   - `publish(publication)`: acquire `_RunLock` (`writer.lock`, `O_CREAT|O_EXCL`,
     stale-lock timeout documented), re-encode and verify the digest, charge
     `bytes + 256 KiB` against the quota (`macro_society_quota_exceeded`,
     `macro_society_publication_exists` for a duplicate id), stage the snapshot
     and manifest, `os.replace` the snapshot directory, fsync file and parent
     directory, then atomically replace `state.json`.
   - `started = True`/`flushes` follow the lineage publisher's pattern for
     `state.json` size caps (4 KiB) and manifest caps (16 KiB).
4. `class FilesystemMacroSocietyReader(MacroSocietyReadPort)`:
   - Resolve the pinned publication id from the caller (or `state.json` when
     omitted), verify the digest on read, and serve summary, candidate pages,
     lineage pages, and single-candidate reads through
     `select_macro_society_rows`.
   - Reject a publication id that is not the committed id
     (`macro_society_publication_missing`).
   - Enforce `MAX_RESPONSE_BYTES`.
5. Factories `create_macro_society_publisher(root, *, max_publications, max_artifact_bytes)`
   and `create_macro_society_reader(root)`; both return `None` when `root is None`
   so disabled composition is a supported state.
6. Export the adapters from `src/persistence/__init__.py`.

### Required Interfaces and Contracts

- `state.json` is replaced atomically and is the single source of the committed
  publication.
- Snapshot directories are immutable once committed; a re-publish with different
  bytes fails.
- The reader never repairs, rewrites, or recomputes a snapshot.
- No PostgreSQL, Alembic, or SQLAlchemy participation.

### Error Handling and Logging

- Codes: `macro_society_quota_exceeded`, `macro_society_publication_exists`,
  `macro_society_publication_missing`, `macro_society_digest_mismatch`,
  `macro_society_store_locked`, `macro_society_store_corrupt`.
- `INFO macro_society_store_published run=%s publication=%s bytes=%s`;
  `WARN macro_society_store_corrupt run=%s reason_code=%s`;
  `ERROR macro_society_store_publish_failed reason_code=%s`.
- Never log snapshot content, member ids, or root paths beyond the run id.

### Tests

`tests/unit/test_macro_society_filesystem.py`:
- Publish then read returns byte-identical snapshot bytes.
- Re-publishing the same id with different bytes raises
  `macro_society_publication_exists`.
- Publishing beyond `max_publications` or `max_artifact_bytes` raises
  `macro_society_quota_exceeded` and leaves `state.json` unchanged.
- A corrupt snapshot (mutated byte) raises `macro_society_digest_mismatch`.
- A concurrent publish attempt raises `macro_society_store_locked`.
- A page beyond the last row returns `next_offset=None`.
- `create_*` with `None` root returns `None`.

### Acceptance Criteria

- Committed state is atomic and self-describing.
- Quotas are enforced before staging.
- The reader is stateless apart from `state.json`.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_macro_society_filesystem.py -q`
- `uv run --frozen --python 3.12.14 pytest tests/unit/test_lineage_filesystem.py -q`

## Phase Risks and Mitigations

- Risk: publication failure is treated as a scientific failure.
  Mitigation: `publish_macro_society_snapshot` returns a receipt; the CLI in
  Task 15 records a separate publication status, exactly like lineage.
- Risk: truncation hides large candidates.
  Mitigation: explicit `provenance_code` and a metric-relevant count, plus a
  documented cap.
- Risk: two writers race on the same run root.
  Mitigation: exclusive lock file plus an atomic commit point.

## Phase Completion Checklist

- Every Task 12-13 acceptance criterion is satisfied.
- `experiments` bridges both vocabularies; `persistence` imports neither
  `analysis` nor `experiments`.
- Store is atomic, quota-bounded, and immutable.
- `index.md` task checkboxes are updated immediately after verified completion.
