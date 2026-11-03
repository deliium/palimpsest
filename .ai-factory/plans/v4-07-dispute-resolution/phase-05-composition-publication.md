# Phase 5: Composition and Durable Publication

Plan: [index.md](index.md)
Tasks: 16-17
Depends on: Phase 4 / Tasks 14-15

## Objective

Compose completed-run dispute analysis into immutable snapshots, publish them
through an injected port, and add the opt-in atomic filesystem store and CLI
producer. Publication failure must never change the scientific result.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/experiments/formal_rule_harvest.py` | `FormalRuleHarvest`, `build_completed_run_formal_rule_harvest` | Completed-run harvest composition. |
| `src/experiments/formal_rule_publication.py` | `FormalRuleHarvestResult`, `build_formal_rule_harvest_result`, `publish_formal_rule_snapshot`, `formal_rule_publication_document` | Snapshot/receipt composition and one-time publication. |
| `src/persistence/formal_rule_filesystem.py` | `_STORE_SCHEMA` 43-46; publisher 73-159; reader 160-309; factories 310-330 | Atomic store, quotas, digest verification, reader/publisher split. |
| `src/research_runner/formal_rule_composition.py` | `FormalRuleProducerOptions`, `producer_options_from_args`, `publish_formal_rule_harvest`, `write_formal_rule_receipt` 65-135 | CLI producer and receipt pattern. |
| `src/research_runner/cli.py` | formal-rule flags 1472-1474; publication call 1271-1292 | CLI wiring point. |
| `src/persistence/organization_filesystem.py` | atomic `state.json` and publication layout | Compatibility precedent. |
| `src/experiments/collectors.py` | completed-run metric assembly | The scientific result must remain unchanged by publication. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/experiments/dispute_harvest.py` | create | Completed-run harvest. |
| `src/experiments/dispute_publication.py` | create | Snapshot build, receipt, publish once. |
| `src/experiments/__init__.py` | modify | Export the dispute harvest/publication contracts. |
| `src/persistence/dispute_filesystem.py` | create | Atomic store and separate reader/publisher. |
| `src/persistence/__init__.py` | modify | Export the dispute reader/publisher factories. |
| `src/research_runner/dispute_composition.py` | create | CLI producer, receipt, disabled/unavailable/failed states. |
| `src/research_runner/cli.py` | modify | Add `--dispute-root`, `--dispute-max-publications`, `--dispute-max-bytes`. |
| `tests/unit/test_dispute_publication.py` | create | Harvest/snapshot/receipt/failure isolation. |
| `tests/unit/test_dispute_filesystem.py` | create | Atomic store/quotas/reader. |
| `tests/unit/test_dispute_cli.py` | create | CLI flags and receipt states. |

## Task 16: Compose completed-run snapshots and receipts

### Intent

Provide the only bridge from detached analysis to a durable artifact. The bridge
runs after scientific completion and never inside simulation, API, or persistence.

### Implementation Steps

1. Create `src/experiments/dispute_harvest.py`:
   - `DisputeHarvest` with `rows`, `windows`, `analysis`, `summary`, `layers`,
     `coverage`, and `receipt`.
   - `build_completed_run_dispute_harvest(runner_result, *, run_id,
     input_revision, generated_tick) -> DisputeHarvest`.
   - Read `runner_result.dispute_ledgers` and
     `runner_result.committed_events`.
   - Build an `entity_to_agent` map from the run assignment if available; pass
     events to `dispute_objective_anchor_rows_from_events`.
   - Harvest rows with `window_ticks=100`; build windows; detect candidates;
     assign identities; derive lineage; summarize; project layers.
   - If no dispute ledgers exist, return an empty harvest with
     `coverage=complete` and zero counts; do not fabricate a case.
   - If ledgers exist but objective events are unavailable, set
     `coverage=partial` and leave objective counts at zero; never invent anchors.
2. Create `src/experiments/dispute_publication.py`:
   - `DisputeHarvestResult(harvest, snapshot, receipt, published)`.
   - `build_dispute_harvest_result(runner_result, *, run_id, input_revision,
     generated_tick, max_candidates, max_claims) -> DisputeHarvestResult`.
   - Build `DisputeSnapshot` from the harvest:
     - candidate/case/claim/testimony/evidence/rule/authority/mediation/
       resolution/response records;
     - objective rows, windows, lineage, counts, coverage;
     - publication ref with a content-addressed `disp-pub-` id.
   - Deterministic truncation: cap candidates at 2048, cases at 4096, claims at
     8192, windows at 512, claims per candidate at 64, resolutions per candidate
     at 32. Append `dispute_truncated` and set `coverage=partial`.
   - Oversize or invalid snapshot: raise `DisputeArtifactError` with a safe code;
     the caller receives `published=False`.
   - `publish_dispute_snapshot(result, port)` publishes exactly once through
     `DisputePublicationPort`; the port returns the publication id, the composer
     records it in the receipt, and a port failure propagates to the caller but
     never mutates `runner_result`.
   - `dispute_publication_document(result)` returns metadata-only receipt fields:
     `run_id`, `publication_id`, `snapshot_digest`, `generated_tick`,
     `candidate_count`, `case_count`, `claim_count`, `resolution_count`,
     `coverage`, `status`, `reason_code`.
3. Do not include claim text, evidence payloads, rule bodies, mediation
   recommendations, party labels, or owner-local ids in the receipt.
4. Export `DisputeHarvest`, `DisputeHarvestResult`, `build_completed_run_dispute_harvest`,
   `build_dispute_harvest_result`, and `publish_dispute_snapshot` from
   `src/experiments/__init__.py` alongside the formal-rule exports.
5. The composer must not import `simulation` engine internals, `api`,
   `persistence`, or `research_runner`.

### Required Interfaces and Contracts

```python
def build_completed_run_dispute_harvest(
    runner_result: object,
    *,
    run_id: str,
    input_revision: str,
    generated_tick: int,
) -> DisputeHarvest: ...

def build_dispute_harvest_result(
    runner_result: object,
    *,
    run_id: str,
    input_revision: str,
    generated_tick: int,
    max_candidates: int = 2048,
    max_claims: int = 8192,
) -> DisputeHarvestResult: ...

def publish_dispute_snapshot(
    result: DisputeHarvestResult,
    port: object,
) -> bool: ...
```

Compatibility invariants:

- Empty evidence produces an empty snapshot, not a fabricated dispute.
- Publication is post-completion and opt-in.
- A publisher failure never changes the scientific result.
- Snapshot bytes are canonical and immutable.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "experiments is the only bridge from analysis to
  artifact" and "Publication is opt-in and non-interfering."
- `src/experiments/formal_rule_harvest.py`;
  `src/experiments/formal_rule_publication.py`.
- `src/simulation/dispute_models.py` and `dispute_codec.py` from Phase 4.

### Error Handling and Logging

- No ledgers: `status="empty"`, zero counts, no error.
- Oversize: `status="failed"`, `reason_code=dispute_size_limit`; scientific
  result unchanged.
- Publisher error: `status="failed"`, safe code; re-raise only to the producer.
- INFO: `dispute_publication status=%s candidates=%s bytes=%s`.
- Never log claim/evidence/rule content.

### Tests

`tests/unit/test_dispute_publication.py`:

- `test_empty_run_produces_empty_snapshot`
- `test_completed_run_builds_candidates_claims_and_resolutions`
- `test_truncation_is_explicit_and_bounded`
- `test_oversize_snapshot_fails_without_mutating_runner_result`
- `test_publish_is_called_once`
- `test_publication_failure_leaves_scientific_result_unchanged`
- `test_receipt_contains_no_private_content`
- `test_experiments_facade_exports_dispute_publication`

Run: `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_publication.py -q`.

### Acceptance Criteria

- Completed-run harvest produces a canonical snapshot.
- Empty evidence stays empty.
- Truncation is explicit.
- Publication failure is isolated from science.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_publication.py -q`
- Expected result: all tests pass.

## Task 17: Add the atomic filesystem store and CLI producer

### Intent

Provide an opt-in, durable, quota-bounded store and a production CLI producer
that matches the established V4 publication pattern.

### Implementation Steps

1. Create `src/persistence/dispute_filesystem.py`:
   - `_STORE_SCHEMA = "dispute-resolution-store-v1"`, `_STATE_FILE =
     "state.json"`, `_PUBLICATION_DIR = "publications"`.
   - `FilesystemDisputePublisher`:
     - duplicate publication id with identical bytes is idempotent;
     - different bytes → `dispute_publication_exists`;
     - publication-count quota default 16 and cumulative byte ceiling default
       8 MiB;
     - atomic write: temp file → `fsync` → `os.replace`; directory `fsync`;
       `state.json` committed last via temp + `os.replace`.
   - `FilesystemDisputeReader`:
     - select the latest publication per `run_id` by
       `(generated_tick, publication_id)`;
     - verify `dispute_snapshot_digest(payload) == entry["snapshot_digest"]`;
     - implement the six read methods and return `DisputeRowSelection`.
   - Factories `create_dispute_publisher(root, *, max_publications=16,
     max_artifact_bytes=8 MiB)` and `create_dispute_reader(root)`, both returning
     `None` when `root is None`.
   - Reader and publisher are separate classes. API imports only the reader.
2. Create `src/research_runner/dispute_composition.py`:
   - `DisputeProducerOptions(root, max_publications, max_bytes)`.
   - `producer_options_from_args(args)`.
   - `publish_dispute_harvest(result, options)`:
     - disabled root → `{"status": "disabled", "reason_code": "dispute_disabled"}`;
     - incomplete result → `{"status": "unavailable", "reason_code":
       "dispute_unavailable"}`;
     - exception → `{"status": "failed", "reason_code": <safe code>}`;
     - success → `{"status": "published", ...}`.
   - `write_dispute_receipt(root, run_id, document)`: sibling
     `dispute-publication-{run_id}.json`, atomic write, receipt-write failure
     ignored.
3. In `src/research_runner/cli.py`:
   - add `--dispute-root`, `--dispute-max-publications` (default 16),
     `--dispute-max-bytes` (default 8 MiB);
   - after successful scientific completion, build the harvest, publish, and
     write the receipt;
   - never run publication on a failed or incomplete run;
   - never change the scientific exit code because publication failed.
4. Export `create_dispute_publisher`, `create_dispute_reader`,
   `FilesystemDisputePublisher`, and `FilesystemDisputeReader` from
   `src/persistence/__init__.py`.
5. No API import, no HTTP server, no simulation import beyond public result
   contracts.

### Required Interfaces and Contracts

```python
def create_dispute_publisher(
    root: Path | None,
    *,
    max_publications: int = 16,
    max_artifact_bytes: int = 8 * 1024 * 1024,
) -> FilesystemDisputePublisher | None: ...

def create_dispute_reader(root: Path | None) -> FilesystemDisputeReader | None: ...

@dataclass(frozen=True, slots=True)
class DisputeProducerOptions:
    root: Path | None
    max_publications: int = 16
    max_bytes: int = 8 * 1024 * 1024

def publish_dispute_harvest(result: object, options: DisputeProducerOptions) -> dict[str, object]: ...
def write_dispute_receipt(root: Path, run_id: str, document: Mapping[str, object]) -> None: ...
```

Compatibility invariants:

- Store schema is `dispute-resolution-store-v1`; existing stores are untouched.
- Atomic commit leaves no partial publication visible.
- Quotas are cumulative and fail closed.
- CLI producer never starts HTTP and never imports `api`.

### Requirement Evidence

- `src/persistence/formal_rule_filesystem.py` 43-330.
- `src/research_runner/formal_rule_composition.py` 65-135; CLI 1271-1292,
  1472-1474.
- `.ai-factory/ARCHITECTURE.md` "research_runner must not import api or start an
  HTTP server."

### Error Handling and Logging

- Duplicate id/different bytes: `dispute_publication_exists`.
- Quota exceeded: `dispute_quota_exceeded`.
- Digest mismatch: `dispute_digest_mismatch`.
- Receipt write failure: WARN `dispute_receipt_failed`; publication remains
  valid.
- INFO: `dispute_store published=%s run=%s`; never log payloads.

### Tests

`tests/unit/test_dispute_filesystem.py`:

- `test_publisher_is_atomic_and_idempotent`
- `test_duplicate_id_with_different_bytes_fails`
- `test_publication_and_byte_quotas`
- `test_reader_verifies_digest`
- `test_reader_selects_latest_publication`
- `test_reader_and_publisher_are_separate`
- `test_persistence_facade_exports_dispute_store`

`tests/unit/test_dispute_cli.py`:

- `test_disabled_root_writes_disabled_receipt`
- `test_incomplete_run_is_unavailable`
- `test_publication_failure_is_failed_but_science_preserved`
- `test_receipt_is_written_next_to_artifacts`
- `test_cli_has_no_http_or_api_import`

Run: `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_filesystem.py tests/unit/test_dispute_cli.py -q`.

### Acceptance Criteria

- Store commits atomically and verifies digests.
- Quotas and duplicate handling fail closed.
- CLI producer supports disabled/unavailable/failed/published states.
- Publication never changes the scientific outcome.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_filesystem.py tests/unit/test_dispute_cli.py -q`
- Expected result: all tests pass.

## Phase Risks and Mitigations

- Risk: Publication runs inside simulation or API.
  Mitigation: Task 16 package guards and Task 20 import scans.
- Risk: A failed publication changes the scientific result.
  Mitigation: Task 16 failure-isolation test and Task 21 E2E.
- Risk: Partial state is visible after a crash.
  Mitigation: Task 17 atomic commit and fsync tests.
- Risk: Quota exhaustion corrupts existing publications.
  Mitigation: Task 17 quota test; existing publications remain readable.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
