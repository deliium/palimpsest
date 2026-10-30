# Phase 5: Composition and Durable Publication

Plan: [index.md](index.md)
Tasks: 14-15
Depends on: Phase 4 / Task 13

## Objective

Compose a completed run's organization evidence into one canonical snapshot,
then store it atomically and immutably behind the read/publication ports. The
bridge lives in `experiments`; the store lives in `persistence`. Neither imports
the other's outer layers, and a publication failure never changes scientific
status.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/experiments/macro_society_publication.py` | `MacroSocietyHarvest` 60-79; `build_macro_society_harvest_result` 147-239; `publish_macro_society_snapshot` 242-261; document 264-280 | Exact bridge pattern: harvest -> analysis -> DTO -> publication -> safe receipt. |
| `src/experiments/macro_society_completed_run.py` | `build_completed_run_harvest` 175-236 | Completed-run harvest and empty-window error. |
| `src/experiments/lineage_publication.py` | `publish_completed_lineage` 874-975 | Per-family failure isolation and status document. |
| `src/persistence/macro_society_filesystem.py` | publisher 89-205; reader 208-290; factories 293-315; atomic write 67-86; quotas 54-56, 96-105 | Atomic single-commit store with lock and quota. |
| `src/persistence/lineage_filesystem.py` | `_RunLock` 306-331; `_atomic_write` 342-356; two-phase publish | Richer staging pattern if needed. |
| `src/research_runner/macro_society_composition.py` | options 36-66; publish 69-123 | CLI receipt and failure isolation. |
| `tests/unit/test_macro_society_publication.py` | deterministic ids, no member ids, truncation | Test pattern. |
| `tests/unit/test_macro_society_filesystem.py` | lock, quota, corruption, disabled root | Test pattern. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/experiments/organization_harvest.py` | create | Read `RunnerResult` ledgers and build detached harvest. |
| `src/experiments/organization_publication.py` | create | Build analysis, map to snapshot, publish, safe receipt. |
| `src/experiments/__init__.py` | modify | Export the harvest, builder, publisher, and receipt document. |
| `src/persistence/organization_filesystem.py` | create | Atomic publisher/reader with lock and quota. |
| `src/persistence/__init__.py` | modify | Export the filesystem publisher/reader and factories. |
| `tests/unit/test_organization_harvest_completed_run.py` | create | RunnerResult -> harvest. |
| `tests/unit/test_organization_publication.py` | create | Build/publish/receipt. |
| `tests/unit/test_organization_end_to_end.py` | create | Harvest -> publish -> read. |
| `tests/unit/test_organization_filesystem.py` | create | Store behavior. |

## Task 14: Compose completed-run organization snapshots

### Intent

Turn one completed run's exported organization ledgers into the canonical
snapshot. The bridge is the only place that may import both `analysis` and
`simulation` organization contracts.

### Implementation Steps

1. Create `src/experiments/organization_harvest.py`:
   - `OrganizationHarvest`: `run_id`, `input_revision`, `generated_tick`,
     `owner_rows`, `windows`, `objective_rows`, optional `coverage`, optional
     `provenance_code`.
   - `build_completed_run_harvest(runner_result, *, run_id, input_revision,
     generated_tick, window_ticks=100)`:
     - read `getattr(runner_result, "organization_concept_ledgers", ())`;
     - call `harvest_organization_rows`;
     - build windows and analysis via the Phase 3 functions;
     - an empty tuple yields an empty harvest (valid when the run produced no
       owner ledgers); the CLI decides `organization_run_incomplete` from the
       scientific stop status, never from an empty organization tuple;
     - reject non-monotonic `generated_tick`/`input_revision` with stable codes.
2. Create `src/experiments/organization_publication.py`:
   - `OrganizationHarvestResult`: `snapshot`, `publication_id`,
     `snapshot_bytes`, `provenance_code`.
   - `build_organization_harvest_result(harvest)`:
     - build identity assignment, layer view, lineage, and analysis once;
     - map records to `OrganizationCandidateRecord` and
       `OrganizationMemberRecord`;
     - apply deterministic member truncation to `MAX_SNAPSHOT_MEMBERS`, sorted
       by `(status, -strength, member_id)`; set
       `provenance_code="member_list_truncated"` when truncated;
     - map lineage edges and objective rows;
     - compute `coverage` from observed/expected windows and lanes;
     - compute the publication id with
       `compute_organization_publication_id`;
     - encode the snapshot and verify byte equality and the 4 MiB cap.
   - `publish_organization_snapshot(result, port)` injects exactly one
     `OrganizationPublication`; it never retries or mutates the snapshot.
   - `organization_publication_document(result)` returns safe receipt fields:
     `status`, `schema_version`, `publication_id`, `window_count`,
     `candidate_count`, `edge_count`, `coverage_observed`, `coverage_expected`,
     `coverage_ratio`, `provenance_code`, `snapshot_bytes`.
     No owner ids, member ids, labels, or anchor ids.
3. Add a module docstring: this is the only bridge from analysis to artifact; it
   never runs inside simulation, API, or persistence; a storage failure changes
   only the publication receipt.
4. Export `OrganizationHarvest`, `OrganizationHarvestResult`,
   `build_completed_run_harvest`, `build_organization_harvest_result`,
   `publish_organization_snapshot`, and `organization_publication_document`
   through `src/experiments/__init__.py`.
5. Tests:
   - deterministic snapshot and publication id for the same harvest;
   - changing one member changes the digest;
   - receipt contains no person/owner ids;
   - truncation discloses `member_list_truncated` and keeps the first 512 sorted
     members;
   - non-monotonic ticks and empty required windows rejected;
   - exactly one publication is injected;
   - the bridge does not import `api`, `persistence`, or `observer`.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class OrganizationHarvest:
    run_id: str
    input_revision: str
    generated_tick: int
    owner_rows: tuple[OrganizationHarvestRows, ...]
    objective_rows: tuple[OrganizationObjectiveAnchorRow, ...]
    window_ticks: int = 100

def build_completed_run_harvest(
    runner_result: object,
    *,
    run_id: str,
    input_revision: str,
    generated_tick: int,
    window_ticks: int = 100,
) -> OrganizationHarvest: ...
```

- The bridge maps analysis records to `simulation` DTOs; it does not pass
  analysis types across the port.
- Members are bounded; no silent loss: truncation is explicit.
- Publication id is content-addressed and idempotent.
- No owner-local `orgc-` id crosses into the snapshot.

### Requirement Evidence

- Original request: "historical lineage"; publication preserves the analytical
  history without granting world authority.
- `.ai-factory/ARCHITECTURE.md` "Dependency Rules": `experiments` may import
  simulation and analysis; it must not import API, infrastructure, persistence,
  or observer.
- `.ai-factory/ARCHITECTURE.md` "Read-only presentation": publication is opt-in
  and non-interfering.

### Error Handling and Logging

- Codes `organization_run_incomplete`, `organization_harvest_invalid`,
  `organization_harvest_tick`, `organization_size_limit`,
  `organization_digest_mismatch`.
- INFO `organization_publication_built run_id=%s publication_id=%s
  candidates=%s edges=%s bytes=%s`.
- WARN `organization_publication_partial reason=%s` with codes only.
- Never log member sets or labels.

### Tests

- `uv run pytest tests/unit/test_organization_harvest_completed_run.py tests/unit/test_organization_publication.py -q`
- `uv run pytest tests/unit/test_organization_end_to_end.py -q`
- Expected: pass.

### Acceptance Criteria

- A completed run produces one bounded, canonical snapshot.
- Truncation is explicit; no silent loss.
- The receipt is id-free.
- Storage ports are used, not concrete persistence.

### Verification

- `uv run pytest tests/unit/test_organization_publication.py -q -k receipt`
- Expected: pass.

## Task 15: Implement the atomic quota-bounded filesystem store

### Intent

Persist snapshots locally with one atomic commit point, immutable bytes, a
writer lock, and cumulative quotas. The reader is read-only and never repairs.

### Implementation Steps

1. Create `src/persistence/organization_filesystem.py`:
   - `FilesystemOrganizationPublisher` implements
     `OrganizationPublicationPort`.
   - `FilesystemOrganizationReader` implements `OrganizationReadPort`.
   - `create_organization_publisher(root, *, max_publications=16,
     max_artifact_bytes=8 * 1024 * 1024)` and
     `create_organization_reader(root)` return `None` when `root is None`.
2. Layout:
   - `<root>/<run_id>/state.json` — the single commit point;
   - `<root>/<run_id>/publications/<publication_id>/snapshot.json`;
   - `<root>/<run_id>/publications/<publication_id>/manifest.json`;
   - `<root>/<run_id>/writer.lock`.
3. `publish`:
   - validate `run_id` and `publication_id` with the snapshot validators before
     touching the filesystem; reject `..`, path separators, NUL, and overlong
     tokens with `organization_invalid_value`;
   - create parent directories;
   - acquire `writer.lock` with `O_CREAT|O_EXCL`; an existing lock raises
     `organization_store_locked`;
   - reject a duplicate publication id with different bytes with
     `organization_publication_exists`; identical bytes are idempotent;
   - enforce `max_publications` and `max_artifact_bytes + 256 KiB` allowance;
   - write `snapshot.json` and `manifest.json` with `_atomic_write`
     (`O_NOFOLLOW`, temp file, fsync file, `os.replace`, fsync parent);
   - write `state.json` last with the publication id, digest, byte size, and
     generated tick;
   - release the lock in `finally`.
4. `read`:
   - read and strictly decode `state.json` and `snapshot.json`;
   - verify the SHA-256 digest matches `state.json`;
   - never create, repair, or delete files;
   - `summary` returns `None` when the run has no committed publication;
   - `candidates`/`lineage` page through the decoded snapshot with
     `select_organization_rows`;
   - `candidate` returns `None` when unknown.
5. Caps: `_STATE_MAX_BYTES = 4096`, `_MANIFEST_MAX_BYTES = 16384`.
6. Error codes: `organization_store_corrupt`, `organization_store_locked`,
   `organization_publication_exists`, `organization_quota_exceeded`,
   `organization_publication_missing`, `organization_digest_mismatch`,
   `organization_size_limit`, `organization_invalid_value`,
   `organization_store_unavailable`.
7. Export `FilesystemOrganizationPublisher`,
   `FilesystemOrganizationReader`, `create_organization_publisher`, and
   `create_organization_reader` through `src/persistence/__init__.py`.
8. Tests:
   - publish/read round trip;
   - idempotent identical bytes; conflicting bytes rejected;
   - quota count and bytes enforced;
   - lock blocks concurrent publish;
   - corrupt/missing digest rejected;
   - missing publication/run returns `None`;
   - disabled root returns `None` adapters;
   - reader does not create the root;
   - symlink target refused;
   - paging respects page/response caps.

### Required Interfaces and Contracts

```python
def create_organization_publisher(
    root: Path | None,
    *,
    max_publications: int = 16,
    max_artifact_bytes: int = 8 * 1024 * 1024,
) -> FilesystemOrganizationPublisher | None: ...

def create_organization_reader(
    root: Path | None,
) -> FilesystemOrganizationReader | None: ...
```

- No SQLAlchemy, Alembic, or database import.
- No analysis, experiments, API, or observer import.
- Publication bytes are immutable after commit.
- Reader never writes.

### Requirement Evidence

- Original request: "historical lineage"; durable history is needed for
  researcher inspection.
- `.ai-factory/ARCHITECTURE.md` "Dependency Rules": persistence implements inner
  ports; it does not import analysis or experiments.
- `.ai-factory/ARCHITECTURE.md` requirement 5: no SQL migration without a proven
  indexed-inspection need; a filesystem artifact is sufficient.

### Error Handling and Logging

- Every failure raises `OrganizationArtifactError` with a stable code.
- WARN `organization_store_locked root=%s` (path only, no payload).
- INFO `organization_published run_id=%s publication_id=%s bytes=%s`.
- ERROR `organization_store_corrupt run_id=%s code=%s`.

### Tests

- `uv run pytest tests/unit/test_organization_filesystem.py -q`
- `uv run pytest tests/architecture/test_organization_boundaries.py -q -k persistence`
- Expected: pass.

### Acceptance Criteria

- One atomic commit point; readers never observe partial state.
- Quotas and locks fail closed.
- No database or analysis dependency.
- Disabled root yields absent adapters, not an empty publication.

### Verification

- `uv run pytest tests/unit/test_organization_filesystem.py -q -k quota`
- Expected: pass.

## Phase Risks and Mitigations

- Risk: a partial write becomes visible.
  Mitigation: write snapshot/manifest first, `state.json` last; reader trusts only
  `state.json`.
- Risk: the bridge imports concrete persistence.
  Mitigation: it accepts a port; Task 19 asserts no persistence import.
- Risk: publication failure changes the scientific result.
  Mitigation: the CLI wraps publication and records only a receipt/status.
- Risk: member truncation silently drops people.
  Mitigation: deterministic truncation plus `member_list_truncated`.
- Risk: a duplicate id with different bytes overwrites history.
  Mitigation: content-addressed id plus conflict rejection.

## Phase Completion Checklist

- Every Task 14-15 acceptance criterion is met.
- Harvest, publication, end-to-end, store, and boundary tests pass.
- No analysis import exists in persistence; no persistence import exists in the
  bridge.
- `index.md` checkboxes are updated immediately after verified completion.
