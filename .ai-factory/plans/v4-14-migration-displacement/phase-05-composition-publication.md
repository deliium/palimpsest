# Phase 5: Composition and Durable Publication

Plan: [index.md](index.md)
Tasks: 18-19
Depends on: Phase 3 / Tasks 11-15 and Phase 4 / Tasks 16-17

## Objective

Compose a completed run's migration-displacement harvest into a canonical
snapshot, publish it opt-in through an atomic filesystem store, and expose a
thin CLI producer. Publication failure changes only the receipt; scientific
status is unchanged.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/experiments/borders_harvest.py` | `BordersHarvest` 52; `build_completed_run_borders_harvest` 66-138; `harvest_notices` 138 | Exact completed-run harvest pattern |
| `src/experiments/borders_publication.py` | `BordersReceipt` 66-83; `BordersHarvestResult` 84-88; `_snapshot` 110-277; `build_borders_harvest_result` 278-318; `publish_borders_snapshot` 319-339; `borders_publication_document` 340 | Exact receipt/publication pattern |
| `src/experiments/collectors.py` | border harvest attach 918-927 | Metric-input composition pattern |
| `src/persistence/borders_filesystem.py` | options 35-45; reader 264; publisher 268; corruption codes 57-61, 150-154; quota 109-114 | Exact atomic store pattern |
| `src/infrastructure/settings.py` | `borders_root` 234; `borders_cursor_key` 235; validators 368-370; safe summary 683-689 | Settings pattern |
| `src/research_runner/borders_composition.py` | options 36-44; from args 46-56; publish 58-90; receipt 92-110 | CLI bridge pattern |
| `src/research_runner/cli.py` | border options 1039-1046; publication 1503-1523; flags 1712-1714 | CLI integration pattern |
| `tests/unit/test_borders_harvest.py` | completed-run harvest and receipt | Test shape to mirror |
| `tests/unit/test_borders_store.py` | atomic publication, duplicate, quota, corruption | Test shape to mirror |
| `tests/unit/test_borders_cli.py` | disabled/published/failed receipts | Test shape to mirror |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/experiments/migration_displacement_harvest.py` | create | Completed-run harvest and token-only view rows |
| `src/experiments/migration_displacement_publication.py` | create | Receipt, snapshot composition, publication entrypoint |
| `src/experiments/collectors.py` | modify | Attach migration rows to metric inputs |
| `src/persistence/migration_displacement_filesystem.py` | create | Atomic `state.json` store, quotas, reader/publisher |
| `src/infrastructure/settings.py` | modify | Root and cursor settings plus safe summary |
| `src/research_runner/migration_displacement_composition.py` | create | Producer options and CLI bridge |
| `src/research_runner/cli.py` | modify | Flags and publication receipt printing |
| `tests/unit/test_migration_displacement_harvest.py` | create | Harvest and receipt |
| `tests/unit/test_migration_displacement_store.py` | create | Atomic store, duplicate, quota, corruption |
| `tests/unit/test_migration_displacement_settings.py` | create | Env settings and safe summary |
| `tests/unit/test_migration_displacement_cli.py` | create | Disabled/published/failed CLI receipts |

## Task 18: Compose completed-run migration-displacement views and receipts

### Intent

Build one canonical snapshot from a completed run's committed events and
exported owner ledgers. The composer is the only bridge from analysis to
artifact; it never runs inside simulation, API, or persistence.

### Implementation Steps

1. Create `src/experiments/migration_displacement_harvest.py` with:
   - `MigrationDisplacementHarvest`:
     `run_id`, `rows`, `snapshot`, `coverage`, `notices`.
   - `build_completed_run_migration_displacement_harvest(runner_result, *,
     committed_events, run_id, policy=None)`:
     - require a completed `runner_result` with `status=completed`;
     - extract `migration_displacement_ledgers` from the result; if absent or
       empty, return `coverage=missing` and an empty snapshot;
     - export token-only owner rows with `migration_displacement_owner_export`;
     - extract objective movement rows with
       `migration_movement_rows_from_events`;
     - harvest rows with `harvest_migration_displacement_rows`;
     - build the snapshot rows and candidate family;
     - finalize the snapshot with `finalize_migration_displacement_snapshot`;
     - return the harvest with sorted notices.
2. Create `src/experiments/migration_displacement_publication.py` with:
   - `MigrationDisplacementReceipt`:
     `status`, `reason`, `publication_id`, `digest`, `row_count`,
     `byte_count`, `coverage`, `notices`.
   - `MigrationDisplacementHarvestResult`:
     `receipt`, `snapshot`.
   - `_snapshot(harvest, run_id)` mapping all layers to snapshot rows and
     rejecting unresolved candidate tokens.
   - `build_migration_displacement_harvest_result(runner_result, *,
     committed_events, run_id)`.
   - `publish_migration_displacement_snapshot(runner_result, publisher, *,
     committed_events, run_id)`:
     - if publisher is `None`, return `status=disabled`, `reason=root_unset`;
     - if the run is incomplete, return `status=unavailable`;
     - if harvest fails, return `status=failed` with a safe code;
     - if the snapshot exceeds 4 MiB or row caps, return
       `status=size_limit`, reason `migration_displacement_size_limit`;
     - call `publisher.publish(snapshot)`;
     - map `migration_displacement_publication_exists` to
       `status=publication_exists`;
     - map `migration_displacement_quota_exceeded` to
       `status=quota_exceeded`;
     - otherwise `status=published`.
   - `migration_displacement_publication_document(receipt) -> dict[str,
     object]` with only safe metadata.
3. In `src/experiments/collectors.py`, attach
   `migration_displacement_rows=harvest.rows` to `MetricComputationInputs` when
   the feature is active; otherwise leave it `None`.
4. Ensure the composer imports analysis and simulation public contracts, never
   `agents.cognition`, `api`, `persistence`, or `observer`.
5. A publication failure never changes `runner_result.status`, stop reason,
   scientific evidence, or metrics.
6. Add `__all__` entries.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class MigrationDisplacementReceipt:
    status: str
    reason: str | None = None
    publication_id: str | None = None
    digest: str | None = None
    row_count: int = 0
    byte_count: int = 0
    coverage: str = "missing"
    notices: tuple[str, ...] = ()
```

Closed statuses: `disabled`, `unavailable`, `failed`, `size_limit`,
`publication_exists`, `quota_exceeded`, `published`.
- A disabled receipt is not an error.
- A failed receipt carries a safe code only.
- The snapshot is immutable after publication.
- The composer never reads another run's memory.

### Requirement Evidence (when reconciliation applies)

- Source: `.ai-factory/ARCHITECTURE.md` — publication is opt-in, post-
  completion, and isolated from scientific status.
- Source: `src/experiments/borders_harvest.py` and `borders_publication.py`.
- Supported combinations: incomplete run; no ledgers; empty harvest; complete
  harvest; size limit; duplicate publication; quota; publisher exception; each
  is tested.

### Error Handling and Logging

- Receipts use safe codes: `migration_displacement_harvest_failed`,
  `migration_displacement_size_limit`,
  `migration_displacement_publication_exists`,
  `migration_displacement_quota_exceeded`.
- Log `INFO migration_displacement_publication status=%s rows=%s bytes=%s
  coverage=%s`; never log tokens, ids, routes, causes, or participants.
- A publisher exception is caught and returned as `failed`, never raised into
  simulation.

### Tests

- `tests/unit/test_migration_displacement_harvest.py`
  - `test_completed_run_builds_all_four_layers`
  - `test_incomplete_run_is_unavailable`
  - `test_missing_ledgers_is_missing_coverage`
  - `test_snapshot_carries_summary_and_candidates`
  - `test_publication_receipt_statuses`
  - `test_size_limit_and_duplicate_and_quota_receipts`
  - `test_publication_failure_does_not_change_scientific_status`
  - `test_harvest_does_not_import_cognition_api_or_persistence`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_harvest.py -q`
- Expected: all pass.

### Acceptance Criteria

- One completed run yields one canonical snapshot and receipt.
- Every failure is receipt-only.
- The composer imports neither cognition nor API/persistence.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_harvest.py -q`
- `uv run --frozen --python 3.12.14 lint-imports`
- Expected: pass.

## Task 19: Add the filesystem store, settings, and CLI producer

### Intent

Persist publications atomically with quotas and a corrupt-store error, expose
settings without secrets, and let the research CLI opt in after a completed run.

### Implementation Steps

1. Create `src/persistence/migration_displacement_filesystem.py` with:
   - `MIGRATION_DISPLACEMENT_STORE_VERSION =
     "migration-displacement-store-v1"`.
   - `MigrationDisplacementPublisherOptions`:
     `max_publications=16`, `max_bytes=8_388_608`; reject non-positive values
     with `migration_displacement_publications_range` /
     `migration_displacement_bytes_range`.
   - `create_migration_displacement_reader(root: Path) -> _Reader`.
   - `create_migration_displacement_publisher(root: Path, options) ->
     _Publisher`.
   - Store layout: `<root>/<run_id>/state.json` with
     `{"store_version", "publications": {publication_id: {bytes,
     digest}}}` and child payloads under
     `<root>/<run_id>/<publication_id>.json`.
   - Single atomic `state.json` commit via `os.replace`; use a file lock for
     concurrent publishers.
   - `publish(snapshot)`: validate, encode, reject duplicate publication id with
     `migration_displacement_publication_exists`, enforce per-run publication
     and byte quotas, write payload, write index, fsync.
   - `read_summary(run_id)`: latest publication summary or `None`.
   - `read_snapshot(run_id, publication_id=None)`: decode; a corrupt payload
     raises `ValueError("migration_displacement_store_corrupt")`.
   - `list_publications(run_id)`.
2. In `src/infrastructure/settings.py`:
   - add `migration_displacement_root: Path | None = None`;
   - add `migration_displacement_cursor_key: SecretStr | None = Field(
     default=None, repr=False)`;
   - validate the cursor key is non-empty when provided;
   - add safe summary keys `has_migration_displacement_root`,
     `has_migration_displacement_cursor_key`,
     `migration_displacement_cursor_enabled`.
   - Env names: `PALIMPSEST_MIGRATION_DISPLACEMENT_ROOT`,
     `PALIMPSEST_MIGRATION_DISPLACEMENT_CURSOR_KEY`.
3. Create `src/research_runner/migration_displacement_composition.py` with:
   - `MIGRATION_DISPLACEMENT_ROOT_ENV`;
   - `MigrationDisplacementProducerOptions(root, max_publications, max_bytes)`
     with `enabled` property;
   - `migration_displacement_producer_options_from_args(args)`;
   - `publish_migration_displacement_harvest(runner_result, options, *,
     committed_events, run_id)`;
   - `write_migration_displacement_receipt(artifact_root, run_id, receipt)`.
4. In `src/research_runner/cli.py`:
   - parse options after the border options:
     `--migration-displacement-root`,
     `--migration-displacement-max-publications` (default 16),
     `--migration-displacement-max-bytes` (default 8_388_608);
   - after the border publication block, publish and print
     `migration_displacement_publication_status`,
     `migration_displacement_publication_reason`,
     `migration_displacement_publication_id`;
   - never print tokens or row contents.
5. A storage failure must not change the scientific completion status or exit
   code beyond writing the receipt; follow the existing border CLI contract.
6. Add `__all__` entries.

### Required Interfaces and Contracts

```python
MIGRATION_DISPLACEMENT_STORE_VERSION: Final[str] = (
    "migration-displacement-store-v1"
)

@dataclass(frozen=True, slots=True)
class MigrationDisplacementPublisherOptions:
    max_publications: int = 16
    max_bytes: int = 8_388_608
```

- Publication is atomic and immutable after the `state.json` commit.
- Duplicate publication ids never overwrite existing bytes.
- Quotas are per run, not global.
- Corrupt state or payload is `migration_displacement_store_corrupt`, never a
  false `not_found`.
- `PALIMPSEST_MIGRATION_DISPLACEMENT_ROOT` unset means disabled, not an error.

### Requirement Evidence (when reconciliation applies)

- Source: `.ai-factory/ARCHITECTURE.md` — persistence adapters implement inner
  ports; no domain policy in storage.
- Source: `src/persistence/borders_filesystem.py`; `src/infrastructure/settings.py`
  234-235, 683-689; `src/research_runner/borders_composition.py`.
- Supported combinations: disabled; first publish; duplicate; quota exceeded;
  corrupt index; corrupt payload; concurrent publish; reader; CLI receipt; each
  is tested.

### Error Handling and Logging

- Store errors use stable codes: `migration_displacement_store_corrupt`,
  `migration_displacement_publication_exists`,
  `migration_displacement_quota_exceeded`,
  `migration_displacement_publications_range`,
  `migration_displacement_bytes_range`.
- Log `INFO migration_displacement_store_published rows=%s bytes=%s`; never log
  run ids, publication ids, tokens, or payloads.
- Settings summary logs booleans only; never log the cursor key.

### Tests

- `tests/unit/test_migration_displacement_store.py`
  - `test_publish_and_read_round_trip`
  - `test_duplicate_publication_id_does_not_overwrite`
  - `test_publication_quota`
  - `test_byte_quota`
  - `test_corrupt_state_and_payload_are_store_corrupt`
  - `test_reader_returns_none_for_unknown_run`
  - `test_concurrent_publishers_commit_one_state`
- `tests/unit/test_migration_displacement_settings.py`
  - `test_root_and_cursor_key_default_none`
  - `test_env_prefix_and_non_empty_cursor_key`
  - `test_safe_summary_never_exposes_the_key`
  - `test_unset_root_disables_the_reader`
- `tests/unit/test_migration_displacement_cli.py`
  - `test_disabled_root_prints_disabled_receipt`
  - `test_published_run_prints_publication_id`
  - `test_storage_failure_does_not_fail_scientific_run`
  - `test_cli_never_prints_tokens`
- Commands:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_store.py tests/unit/test_migration_displacement_settings.py tests/unit/test_migration_displacement_cli.py -q`
- Expected: all pass.

### Acceptance Criteria

- Publications are atomic, immutable, quota-bounded, and isolated from science.
- Settings are secret-safe and disabled by default.
- The CLI prints safe receipt fields only.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_store.py tests/unit/test_migration_displacement_settings.py tests/unit/test_migration_displacement_cli.py -q`
- `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_store.py tests/unit/test_borders_settings.py tests/unit/test_borders_cli.py -q`
- Expected: pass.

## Phase Risks and Mitigations

- Risk: publication failure aborts a scientific run.
  Mitigation: Task 18 catches every composition/storage failure and returns a
  receipt only.
- Risk: a duplicate publication overwrites bytes.
  Mitigation: Task 19 rejects a duplicate id before writing.
- Risk: a corrupt store becomes a false 404.
  Mitigation: Task 19 raises `migration_displacement_store_corrupt`; Task 20
  maps it to 500.
- Risk: the CLI prints raw tokens.
  Mitigation: Task 19 prints status, reason, and publication id only; Task 23
  scans output fields.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
