# Phase 5: Composition and Durable Publication

Plan: [index.md](index.md)
Tasks: 18-19
Depends on: Phase 2 / Tasks 4-10, Phase 3 / Tasks 11-15, Phase 4 / Tasks 16-17

## Objective

Compose completed-run border analysis and publish `borders-snapshot-v1` through
an opt-in, post-completion, atomic `borders-store-v1` filesystem store with
quotas and a CLI producer. Publication failure changes only the receipt, never
the scientific result.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/experiments/organized_conflict_harvest.py` | harvest dataclass 57-97 | Composition order to mirror |
| `src/experiments/organized_conflict_publication.py` | stop codes 49-58; families 59-64; receipt 67-76; snapshot builder 138-301; publish 366-393; metadata 396-409 | Publication and receipt pattern |
| `src/experiments/diplomacy_publication.py` | receipt/status 56-125; snapshot 105-505; publish 506-593 | Richer publication precedent |
| `src/persistence/organized_conflict_filesystem.py` | store schema 31-45; atomic write 67-78; lock/quota 81-131; reader 134-171 | Store pattern |
| `src/persistence/diplomacy_filesystem.py` | 39-331 | Older store compatibility precedent |
| `src/research_runner/organized_conflict_composition.py` | env root 32; options 35-55; publish 58-83; receipt 86-100 | CLI producer pattern |
| `src/research_runner/cli.py` | flags 1673-1678; call 1466-1490 | Exact CLI integration point |
| `src/infrastructure/settings.py` | fields 220-233; safe status 650-680 | Settings and safe status pattern |
| `src/analysis/borders_metrics.py` | four metric documents | Provenance source |
| `src/simulation/borders_codec.py` | finalize/encode/decode | Publication artifact |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/experiments/borders_harvest.py` | create | Completed-run harvest composition |
| `src/experiments/borders_publication.py` | create | Snapshot composition, receipt, publish helper |
| `src/experiments/collectors.py` | modify | Attach detached border rows to metric inputs |
| `src/persistence/borders_filesystem.py` | create | Atomic `borders-store-v1` reader/publisher |
| `src/infrastructure/settings.py` | modify | `PALIMPSEST_BORDERS_ROOT` and cursor key + safe status |
| `src/research_runner/borders_composition.py` | create | Opt-in producer bridge and receipt writer |
| `src/research_runner/cli.py` | modify | Three border flags and the post-completion call |
| `tests/unit/test_borders_harvest.py` | create | Composition order and inactive paths |
| `tests/unit/test_borders_publication.py` | create | Receipts, incomplete runs, non-interference |
| `tests/unit/test_borders_store.py` | create | Atomicity, lock, quota, idempotency, corruption |
| `tests/unit/test_borders_settings.py` | create | Settings and cursor-key validation |
| `tests/unit/test_borders_cli.py` | create | CLI flags and receipt output |

## Task 18: Compose completed-run border views and receipts

### Intent

Turn one completed `SimulationRunnerResult` plus committed events into a
deterministic border harvest and, when explicitly enabled, a published snapshot.
The scientific result is never modified by publication success or failure.

### Implementation Steps

1. Create `src/experiments/borders_harvest.py`:
   - `BordersHarvest` dataclass:
     `rows`, `overlaps`, `patterns`, `candidates`, `lineage`, `layers`,
     `alignment`, `summary`, `notices`, `has_ledger`.
   - `build_completed_run_borders_harvest(runner_result, committed_events,
     policy=None)` with this exact order:
     1. read `runner_result.border_ledgers`;
     2. `harvest_border_rows`;
     3. `detect_border_overlaps`;
     4. `detect_border_disputes`;
     5. `detect_boundary_recognitions`;
     6. `detect_control_patterns`;
     7. `assign_border_identities`;
     8. `derive_border_lineage`;
     9. `join_border_identities` with `runner_result.organization_candidates`
        and `runner_result.macro_society_analysis.candidates`;
     10. `project_border_layers`;
     11. `align_border_interpretations`;
     12. `summarize_borders`.
   - Never mutate the runner result, the ledgers, the events, or the analysis
     rows.
2. Create `src/experiments/borders_publication.py`:
   - `INCOMPLETE_BORDER_STOP_CODES` = `cancelled`, `cognition_failure`,
     `authority_failure`, `finalization_recovery_required`,
     `experiment_criterion_failure`, `historical_artifact_failure`.
   - `_FAMILIES = ("border_claim_structure", "border_overlap_contest",
     "border_agreement_recognition", "border_control_alignment")`.
   - `BordersReceipt`:
     `status`, `reason`, `publication_id`, `digest`, `candidates`, `claims`,
     `agreements`, `disputes`, `patterns`, `coverage`.
   - `BordersHarvestResult`: `receipt`, optional `snapshot`.
   - `_snapshot(harvest, run_id)`:
     - build every snapshot row from the four-layer view, candidates, lineage,
       alignment, and metric documents;
     - build the required `summary` row with counts matching the row tuples;
     - hash owner/location/anchor tokens;
     - add metric provenance with exact family/algorithm/catalog/value keys;
     - finalize with `finalize_borders_snapshot`.
   - `build_borders_harvest_result(runner_result, committed_events, run_id)`:
     - incomplete stop -> `unavailable` with the stop code;
     - no ledgers -> `disabled` with `borders_disabled`;
     - otherwise build harvest and snapshot;
     - size/cap failure -> `failed` with `borders_size_limit`.
   - `publish_borders_snapshot(runner_result, options, committed_events,
     run_id)`:
     - build the result;
     - if publisher present and snapshot valid, publish;
     - return the receipt only;
     - never raise a storage exception into the scientific path.
   - `borders_publication_document(receipt)` returns the small metadata
     document written next to the run receipt.
3. Publication is opt-in and post-completion:
   - only after the runner result is finalized;
   - only when `PALIMPSEST_BORDERS_ROOT` and a cursor key are configured for the
     API, or the CLI root flag is supplied;
   - no publication during a tick, admission, or cognition.
4. In `src/experiments/collectors.py`, after the organized-conflict block
   (895-914):
   - read `arm.runner_result.border_ledgers`;
   - call `harvest_border_rows` with committed events and the default analysis
     policy;
   - attach `border_claim_rows`, `border_agreement_rows`,
     `border_physical_rows`, `border_pattern_rows`, `border_alignment_rows`,
     and `border_overlap_rows` to the metric inputs with `dataclasses.replace`;
   - leave the runner-result document unchanged; these rows are collector-only.
   A missing ledger attaches empty sequences and leaves the border families
   absent/`not_applicable`, never a synthetic zero.
5. The composer imports `analysis.borders_*` and `simulation.borders_*` only.
   It never imports `agents.cognition`, `api`, `persistence`, or `observer`.
6. Logging:
   - `INFO borders_publication status=%s reason=%s` (no ids);
   - `WARN borders_publication_failed reason_code=%s`;
   - never log publication ids, digests, row tokens, or run ids.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class BordersReceipt:
    status: str
    reason: str
    publication_id: str = ""
    digest: str = ""
    candidates: int = 0
    claims: int = 0
    agreements: int = 0
    disputes: int = 0
    patterns: int = 0
    coverage: str = "not_applicable"

def build_completed_run_borders_harvest(...) -> BordersHarvest: ...
def build_borders_harvest_result(...) -> BordersHarvestResult: ...
def publish_borders_snapshot(...) -> BordersReceipt: ...
```

- Receipt statuses are exactly `published`, `unavailable`, `disabled`, `failed`.
- A storage/composition failure changes only the receipt.
- No receipt field is a scientific truth or a composite score.
- The snapshot is built only from detached rows.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — read-only overlays and researcher distinction.
- Source: `.ai-factory/ARCHITECTURE.md` — analysis-to-artifact bridge is
  composition-only; publication never changes scientific status.
- Source: `src/experiments/organized_conflict_publication.py` 49-409.
- Supported combinations: complete run with ledgers; complete run without
  ledgers; incomplete stop; size overflow; storage failure; each tested.

### Error Handling and Logging

- `unavailable` carries the exact stop code.
- `disabled` is not an error.
- `failed` carries `borders_size_limit` or `borders_publication_failed`.
- The scientific result, stop reason, and objective events are unchanged in all
  cases.
- No raw ids or row content in logs.

### Tests

- `tests/unit/test_borders_harvest.py`
  - `test_harvest_order_and_inactive_paths`
  - `test_no_ledgers_yields_disabled`
  - `test_incomplete_stop_is_unavailable`
  - `test_harvest_does_not_mutate_the_result`
  - `test_org_and_macro_joins_are_read_only`
  - `test_collector_inputs_include_border_rows_without_changing_the_result`
- `tests/unit/test_borders_publication.py`
  - `test_complete_run_publishes_all_four_families`
  - `test_size_overflow_is_failed_receipt_only`
  - `test_storage_failure_changes_only_the_receipt`
  - `test_metadata_document_has_no_raw_ids`
  - `test_publication_is_post_completion_and_opt_in`
- Commands:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_harvest.py tests/unit/test_borders_publication.py -q`
- Expected: all pass.

### Acceptance Criteria

- Harvest order is exact and deterministic.
- Publication is opt-in, post-completion, and non-interfering.
- Receipts are truthful and contain no scientific status claim.
- No raw ids or row content are published.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_harvest.py tests/unit/test_borders_publication.py -q`
- Expected: pass.

## Task 19: Add the filesystem store, settings, and CLI producer

### Intent

Persist published border snapshots atomically and serve them read-only through a
bounded store. Add the two `PALIMPSEST_` settings and the CLI producer without
touching the scientific result or the existing stores.

### Implementation Steps

1. Create `src/persistence/borders_filesystem.py`:
   - `BORDERS_STORE_SCHEMA: Final[str] = "borders-store-v1"`
   - `_STATE_FILE = "state.json"`, `_LOCK_FILE = "store.lock"`
   - `BordersPublisherOptions(max_publications=16, max_bytes=8*1024*1024)`:
     `1..1024` publications and `1..268_435_456` bytes.
   - `_empty_state`, `_load_state`, `_atomic_write` (temp file, fsync, replace)
     mirroring `organized_conflict_filesystem.py` 67-78.
   - `_Publisher.publish(snapshot)`:
     - lock with `fcntl.flock(LOCK_EX)`;
     - reject a duplicate `publication_id` with different bytes
       (`borders_publication_exists`);
     - return idempotently for identical bytes;
     - enforce per-run publication and byte quotas
       (`borders_quota_exceeded`);
     - append `run_id`, `publication_id`, `digest`, `schema_version`, base64
       payload; write canonical JSON atomically.
   - `_Reader`:
     - `summary(run_id)` -> `BordersSummary` or `None`;
     - `snapshot(run_id)` -> decoded `BordersSnapshot` or `None`;
     - reject corrupt state/decoded bytes with `borders_store_corrupt`;
     - verify the decoded publication id matches the entry.
   - `create_borders_reader(root)` and
     `create_borders_publisher(root, options=None)`.
2. In `src/infrastructure/settings.py`:
   - Add `borders_root: Path | None = None` and
     `borders_cursor_key: SecretStr | None = Field(default=None, repr=False)`
     after `organized_conflict_*`.
   - Add a cursor-key validator mirroring the diplomacy 32-byte requirement.
   - Add safe status fields near 650-680:
     `has_borders_root`, `has_borders_cursor_key`, `borders_enabled`,
     `borders_cursor_enabled`.
   - Never log a root path or key value.
3. Create `src/research_runner/borders_composition.py`:
   - `BordersOptions` with `root`, `max_publications`, `max_bytes`, `enabled`.
   - `publish_borders_harvest(runner_result, options, committed_events, run_id)`
     creates the publisher and returns the receipt.
   - `write_borders_receipt(artifact_root, run_id, receipt)` writes a small JSON
     document under the existing artifact root.
   - A missing root yields `disabled`; a storage failure yields `failed`; neither
     raises.
4. In `src/research_runner/cli.py`:
   - Add after the organized-conflict flags (1673-1678) on the **generational**
     subcommand only:
     `--borders-root`, `--borders-max-publications` (default 16),
     `--borders-max-bytes` (default 8_388_608).
   - After organized-conflict publication (1466-1490), call the border producer
     with `arm.runner_result`, `arm.committed_events or ()`, and the assigned
     run id.
   - Print `borders_publication_status`, `..._reason`, and `..._id` only when
     present.
   - Do not add a new CLI subcommand.
   - Do not add the flags to `_add_generational_matrix_args` or wire
     `_cmd_run`/`_cmd_resume`; matrix batch publication is explicitly out of
     scope for V4-13 and matches the V4-12 producer scope. Add a test asserting
     `run --help` does not expose border flags.
5. No migration, SQL column, `/v2` route, or event write is added.

### Required Interfaces and Contracts

```python
BORDERS_STORE_SCHEMA: Final[str] = "borders-store-v1"

@dataclass(frozen=True, slots=True)
class BordersPublisherOptions:
    max_publications: int = 16
    max_bytes: int = 8 * 1024 * 1024

def create_borders_reader(root: Path) -> BordersReadPort: ...
def create_borders_publisher(root: Path, options: BordersPublisherOptions | None = None) -> BordersPublisherPort: ...
```

- Store writes are atomic under a lock.
- Duplicate identical publication is idempotent.
- Different bytes for the same publication id are rejected.
- Quotas are per run and cumulative.
- Existing stores and `PALIMPSEST_` settings are unchanged.

### Requirement Evidence (when reconciliation applies)

- Source: `.ai-factory/ARCHITECTURE.md` — persistence adapters implement ports;
  no domain policy in adapters; settings use `PALIMPSEST_` only.
- Source: `src/persistence/organized_conflict_filesystem.py` 31-181 and
  `src/infrastructure/settings.py` 220-233, 650-680.
- Supported combinations: unset root; empty store; first publication; identical
  duplicate; differing duplicate; quota exceeded; corrupt state; each tested.

### Error Handling and Logging

- Unset root -> `disabled`, no exception.
- Duplicate/changed bytes -> `borders_publication_exists`.
- Quota -> `borders_quota_exceeded`.
- Corrupt store -> `borders_store_corrupt`; never invent a snapshot.
- Logs: `INFO borders_store_published publications=%s` (count only); no path,
  publication id, digest, or payload.

### Tests

- `tests/unit/test_borders_store.py`
  - `test_atomic_publish_and_read_round_trip`
  - `test_identical_duplicate_is_idempotent`
  - `test_changed_duplicate_is_rejected`
  - `test_publication_and_byte_quota`
  - `test_corrupt_state_fails_closed`
  - `test_reader_returns_none_for_unknown_run`
  - `test_store_schema_is_borders_store_v1`
- `tests/unit/test_borders_settings.py`
  - `test_borders_root_and_cursor_key_are_optional`
  - `test_cursor_key_requires_32_bytes`
  - `test_safe_status_fields_are_booleans`
- `tests/unit/test_borders_cli.py`
  - `test_generational_flags_and_defaults`
  - `test_matrix_run_does_not_expose_border_flags`
  - `test_missing_root_reports_disabled`
  - `test_receipt_is_written_after_completion`
  - `test_publication_failure_does_not_change_scientific_output`
- Commands:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_store.py tests/unit/test_borders_settings.py tests/unit/test_borders_cli.py -q`
- Expected: all pass.

### Acceptance Criteria

- The store is atomic, locked, quota-bounded, and idempotent.
- Settings are optional and fail closed.
- The CLI producer is opt-in and post-completion.
- Existing stores/settings are unchanged.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_store.py tests/unit/test_borders_settings.py tests/unit/test_borders_cli.py -q`
- `docker compose config --quiet` (no new service or env secret)
- Expected: pass.

## Phase Risks and Mitigations

- Risk: publication runs inside a tick.
  Mitigation: Task 18/19 call it only after `runner_result` is finalized; tests
  assert no tick-time call.
- Risk: a storage error aborts the run.
  Mitigation: receipt-only failure; Task 18/19 tests assert scientific outputs
  unchanged.
- Risk: the new store collides with `organized-conflict-store-v1`.
  Mitigation: distinct `borders-store-v1` schema and root setting.
- Risk: duplicate publications grow without bound.
  Mitigation: lock, idempotency, per-run publication/byte quotas.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
