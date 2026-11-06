# Phase 5: Composition and Durable Publication

Plan: [index.md](index.md)
Tasks: 18-19
Depends on: Phase 4

## Objective

Compose a completed run's organized-conflict analysis into the canonical
snapshot, publish it opt-in and atomically, serve it from a filesystem store, and
expose it through the existing CLI without changing the scientific result.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/experiments/diplomacy_harvest.py` | `DiplomacyHarvest` 42-61; builder 69-128 | Harvest composition pattern |
| `src/experiments/diplomacy_publication.py` | incomplete codes 56-65; result 68-74; receipt 76-102; snapshot 105-503; statuses 506-558; publish 561-593; document 596-607 | Receipt/snapshot/publish pattern |
| `src/persistence/diplomacy_filesystem.py` | store schema 49; atomic write 52-58; lock 61-69; state 72-84; quotas 87-103; idempotency/quotas 116-126; read 160-181; factories 322-331 | Store pattern |
| `src/research_runner/diplomacy_composition.py` | env 31; options 44-52; root 55-59; producer options 62-76; publish 79-140; receipt 149-174 | Producer pattern |
| `src/research_runner/cli.py` | args 1636-1638; options 1014-1025; publish/receipt 1428-1453 | CLI wiring |
| `src/infrastructure/settings.py` | diplomacy root/cursor 230-231; summary flags 654-660 | Settings pattern |
| `tests/unit/test_diplomacy_publication.py` | disabled 82-87; unavailable 90+; ready 102+; failure isolation 117-134 | Publication tests |
| `tests/unit/test_diplomacy_store.py` | publish/read 85+; quota 104-115; tamper 117+; unset root 129-135 | Store tests |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/experiments/organized_conflict_harvest.py` | create | Completed-run harvest bridge |
| `src/experiments/organized_conflict_publication.py` | create | Snapshot/receipt composition and publish |
| `src/experiments/__init__.py` | modify | Public facade exports |
| `src/persistence/organized_conflict_filesystem.py` | create | Atomic store, quotas, reader/publisher |
| `src/persistence/__init__.py` | modify | Public facade exports |
| `src/infrastructure/settings.py` | modify | Root and cursor-key settings and summary flags |
| `src/research_runner/organized_conflict_composition.py` | create | CLI producer and receipt |
| `src/research_runner/cli.py` | modify | Args, options, publish/receipt wiring |
| `tests/unit/test_organized_conflict_publication.py` | create | Receipt statuses and failure isolation |
| `tests/unit/test_organized_conflict_store.py` | create | Atomicity, idempotency, quotas, unset root |

## Task 18: Compose completed-run conflict views and receipts

### Intent

Turn exported owner ledgers plus committed events into one snapshot and one
metadata-only receipt, without changing the run result or scientific status.

### Implementation Steps

1. Create `src/experiments/organized_conflict_harvest.py`:
   - `OrganizedConflictHarvest` frozen dataclass with `rows`, `candidates`,
     `lineage`, `layers`, `alignment`, `summary`, `episodes`, `notices`.
   - `build_completed_run_organized_conflict_harvest(runner_result,
     committed_events, policy)`:
     * read `runner_result.organized_conflict_ledgers` via `getattr(..., ())` so
       legacy results remain readable;
     * call `harvest_organized_conflict_rows`;
     * call `detect_organized_conflict_episodes` on objective rows;
     * call `assign_organized_conflict_identities`, `derive_organized_conflict_lineage`,
       and `join_organized_conflict_identities` with existing `org-`/`msoc-`
       candidates from the runner result if present;
     * call `align_conflict_interpretations` and
       `summarize_organized_conflict`;
     * return the harvest.
2. Create `src/experiments/organized_conflict_publication.py`:
   - `INCOMPLETE_CONFLICT_STOP_CODES = frozenset({"cancelled",
     "cognition_failure", "authority_failure", "finalization_recovery_required",
     "experiment_criterion_failure", "historical_artifact_failure"})`, matching
     `src/experiments/diplomacy_publication.py` 56-65.
   - `OrganizedConflictHarvestResult` with `receipt`, `snapshot`.
   - `_receipt` fields: `status`, `reason`, `publication_id`, `digest`,
     `episodes`, `plans`, `interpretations`, `coverage`.
   - `_snapshot` maps harvest rows into `OrganizedConflictSnapshot` rows:
     summary counts, episodes, participants, plans, interpretations, outcomes,
     contradictions, terminations, lineage, metric provenance.
   - Composer-derived labels: episode classification and alignment are copied
     from analysis, never recomputed from owner claims during publication.
   - `build_organized_conflict_harvest_result(...)` returns:
     * `unavailable` when the run is incomplete;
     * `disabled` when the harvest is empty and no conflict ledger exists;
     * `failed` on artifact composition error (reason code only);
     * `ready` otherwise.
   - `publish_organized_conflict_snapshot(...)` publishes through the port;
     a failure changes only the receipt.
   - `organized_conflict_publication_document(...)` returns a JSON-safe receipt.
3. Add tests for disabled, unavailable, ready, failed, empty, idempotent, and
   scientific-result-unchanged cases.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class OrganizedConflictHarvest: ...
def build_completed_run_organized_conflict_harvest(...) -> OrganizedConflictHarvest: ...

@dataclass(frozen=True, slots=True)
class OrganizedConflictHarvestResult: ...
def build_organized_conflict_harvest_result(...) -> OrganizedConflictHarvestResult: ...
def publish_organized_conflict_snapshot(...) -> OrganizedConflictHarvestResult: ...
```

Compatibility: only `experiments` composes analysis into the snapshot. `analysis`
never imports `experiments`, `persistence`, or `api`.

### Requirement Evidence

- Source: `src/experiments/diplomacy_publication.py` 76-607 — receipt and
  composition pattern.
- Source: `.ai-factory/ARCHITECTURE.md` "analysis is read-only".
- Supported combinations: incomplete; empty; ready; composition failure;
  publication failure; duplicate publication.

### Error Handling and Logging

- Receipt `reason` is a stable code (`incomplete_run`, `no_rows`,
  `composition_failed`, `publication_failed`), never an exception body.
- INFO `organized_conflict_publication status=%s episodes=%s plans=%s`.
- WARN `organized_conflict_publication_failed reason_code=%s`.
- ERROR only safe code; never row content or ids.

### Tests

- `tests/unit/test_organized_conflict_publication.py`
  - `test_incomplete_run_is_unavailable`
  - `test_no_ledger_is_disabled`
  - `test_ready_receipt_counts_match_snapshot`
  - `test_publication_failure_does_not_change_result`
  - `test_receipt_is_metadata_only`
- Command: `uv run pytest tests/unit/test_organized_conflict_publication.py -q`

### Acceptance Criteria

- The snapshot contains all populated row families.
- The receipt is metadata-only and status-correct.
- Publication failure never changes the scientific result.
- No owner claim determines episode classification.

### Verification

- `uv run pytest tests/unit/test_organized_conflict_publication.py -q`
- Expected: all pass.

## Task 19: Add the filesystem store settings and CLI producer

### Intent

Publish snapshots atomically, bound retention, and expose a CLI switch without
starting HTTP or changing scientific schemas.

### Implementation Steps

1. Create `src/persistence/organized_conflict_filesystem.py`:
   - `ORGANIZED_CONFLICT_STORE_SCHEMA = "organized-conflict-store-v1"`.
   - `OrganizedConflictPublisherOptions` with defaults
     `max_publications=16`, `max_bytes=8 * 1024 * 1024`, ranges 1..1024 and
     1..268_435_456.
   - Atomic write: temp file in the target directory + `os.replace`.
   - Publish lock: `fcntl.flock` on a lock file.
   - State document: `schema`, `publications` list.
   - Idempotency: same publication id and identical bytes returns success;
     different bytes raises `organized_conflict_publication_exists`.
   - Per-run publication cap and cumulative byte cap raise
     `organized_conflict_quota_exceeded`.
   - Reader selects the last entry for the run id, verifies digest and schema,
     and returns the decoded snapshot.
   - Factories `create_organized_conflict_reader(root)` and
     `create_organized_conflict_publisher(root, options)`, following the existing
     `create_diplomacy_reader`/`create_diplomacy_publisher` naming.
2. In `src/infrastructure/settings.py`:
   - add `organized_conflict_root: Path | None = None`
   - add `organized_conflict_cursor_key: SecretStr | None = None`
   - add both to the settings summary with names only, never values.
3. Create `src/research_runner/organized_conflict_composition.py`:
   - `ORGANIZED_CONFLICT_ROOT_ENV = "PALIMPSEST_ORGANIZED_CONFLICT_ROOT"`.
   - `OrganizedConflictProducerOptions`.
   - `producer_options_from_args`.
   - `publish_organized_conflict_harvest(...)`: disabled when root unset;
     unavailable on incomplete stop; builds the publisher, harvest, and snapshot;
     publishes; returns the receipt.
   - `write_organized_conflict_receipt(...)`: metadata-only, atomic temp +
     replace, safe run-id check.
4. In `src/research_runner/cli.py`:
   - add `--organized-conflict-root`,
     `--organized-conflict-max-publications`,
     `--organized-conflict-max-bytes`.
   - wire options, producer, and receipt after the diplomacy block.
5. Add tests for atomicity, lock, idempotency, changed-bytes rejection, quota
   preservation, failed publish with no partial state, unset root, and CLI
   receipt.

### Required Interfaces and Contracts

```python
ORGANIZED_CONFLICT_STORE_SCHEMA: Final[str] = "organized-conflict-store-v1"
ORGANIZED_CONFLICT_ROOT_ENV: Final[str] = "PALIMPSEST_ORGANIZED_CONFLICT_ROOT"
```

Compatibility: new store schema only; `diplomacy-store-v1` is untouched. No
HTTP server is started by `research_runner`.

### Requirement Evidence

- Source: `src/persistence/diplomacy_filesystem.py` 49-331 — atomic store/quota
  pattern.
- Source: `src/research_runner/diplomacy_composition.py` 31-174 — producer
  pattern.
- Source: `src/infrastructure/settings.py` 230-231, 654-660 — settings pattern.
- Supported combinations: unset root; fresh publish; duplicate identical;
  duplicate changed; per-run quota; byte quota; atomic failure; read last.

### Error Handling and Logging

- `organized_conflict_publication_exists`,
  `organized_conflict_quota_exceeded`,
  `organized_conflict_store_corrupt`.
- INFO `organized_conflict_store_published publications=%s bytes=%s`.
- WARN `organized_conflict_store_quota kind=%s`.
- Never log publication ids, digests, or snapshot content.

### Tests

- `tests/unit/test_organized_conflict_store.py`
  - `test_publish_then_read_round_trip`
  - `test_duplicate_identical_is_idempotent`
  - `test_changed_bytes_are_rejected`
  - `test_quota_preserves_prior_publication`
  - `test_failed_publish_leaves_no_partial_state`
  - `test_unset_root_disables_producer`
- Command: `uv run pytest tests/unit/test_organized_conflict_store.py -q`

### Acceptance Criteria

- Publication is atomic and lock-protected.
- Quotas preserve prior artifacts.
- Duplicate IDs with changed bytes are rejected.
- Unset root disables publication and the API remains 503.
- No scientific schema changes.

### Verification

- `uv run pytest tests/unit/test_organized_conflict_store.py -q`
- Expected: all pass.

## Phase Risks and Mitigations

- Risk: publication failure changes the run result.
  Mitigation: receipt-only error path and a scientific-result-unchanged test.
- Risk: a partial file is visible during write.
  Mitigation: temp file + `os.replace` under a lock.
- Risk: quotas delete prior publications.
  Mitigation: reject over-quota and leave prior state untouched.
- Risk: CLI imports API.
  Mitigation: import-linter and a no-HTTP test.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
