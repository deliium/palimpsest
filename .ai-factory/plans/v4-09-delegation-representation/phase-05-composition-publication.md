# Phase 5: Composition and Durable Publication

Plan: [index.md](index.md)
Tasks: 16-17
Depends on: Tasks 13 and 15

## Objective

Compose the snapshot only after successful scientific completion, publish it
opt-in through an atomic filesystem store with quotas, and expose a CLI producer
whose failures change only the publication receipt.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/experiments/evidence_testimony_publication.py` | result 57; build 75; caps/finalize 255-285; receipt 287-300; publish 315; metadata 341 | Publication template |
| `src/experiments/dispute_publication.py` | receipt and composition | Sibling bridge |
| `src/persistence/evidence_testimony_filesystem.py` | store schema 52; atomic write 55; lock 65; publisher 97; reader 169; factories 314/327 | Store template |
| `src/research_runner/evidence_testimony_composition.py` | env root 39; options 54; from-args 71; publish 120; receipt 185 | CLI bridge |
| `src/research_runner/cli.py` | flags 1550-1552; parsing 990-1001; invocation 1348-1373 | CLI wiring |
| `src/experiments/civilization_publication.py` | publication readiness separate from scientific status | Non-interference precedent |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/experiments/delegation_representation_publication.py` | create | Completed-run composition and receipt |
| `src/experiments/__init__.py` | modify | Harvest/publication exports |
| `src/persistence/delegation_representation_filesystem.py` | create | Atomic store and reader |
| `src/research_runner/delegation_representation_composition.py` | create | Producer options and receipts |
| `src/research_runner/cli.py` | modify | Three CLI flags and invocation |
| `tests/unit/test_delegation_representation_publication.py` | create | Composition/receipt |
| `tests/unit/test_delegation_representation_filesystem.py` | create | Store/quotas/idempotency |
| `tests/unit/test_delegation_representation_cli.py` | create | CLI and failure isolation |

## Task 16: Compose completed-run snapshots and receipts

### Intent

An incomplete or failed run must still produce a scientific result. Publication
is a separate, opt-in side effect with an honest receipt.

### Implementation Steps

1. Create `src/experiments/delegation_representation_publication.py` with
   `RepresentationHarvestResult` carrying `snapshot`, `receipt: Mapping[str,
   object]`, and `published: bool`.
2. Implement `build_representation_harvest_result(*, runner_result, stop_reason,
   analysis_summary, candidates, lineage, metric_provenance, policy=None)`:
   - return `status="unavailable"`, `reason="representation_run_incomplete"`
     when the run did not complete successfully;
   - return `status="disabled"` when no representation ledgers exist;
   - otherwise assemble row tuples, call
     `finalize_delegation_representation_snapshot`, and return
     `status="ready"`.
3. Implement `publish_representation_snapshot(result, publisher)`:
   - `disabled`/`unavailable` → no publisher call, unchanged receipt;
   - `ready` → call the publisher once and map the outcome to
     `published`/`failed` with a safe code.
4. Add `representations_publication_document(result)` returning the
   metadata-only JSON document with schema, publication id, digest, counts,
   receipt status/reason, and coverage.
5. Map size failures to `representation_size_limit`; any other publisher error to
   `representation_publication_failed`; a duplicate id with different bytes to
   `representation_publication_exists`.
6. Never mutate `runner_result`, metrics, stop selectors, or the scientific
   status.
7. Export `build_completed_run_representation_harvest`,
   `build_representation_harvest_result`,
   `publish_representation_snapshot`, and
   `representations_publication_document` from `src/experiments/__init__.py`
   beside the evidence exports at lines 254-262, and add them to `__all__`.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class RepresentationHarvestResult:
    snapshot: DelegationRepresentationSnapshot | None
    receipt: Mapping[str, object]
    published: bool

def build_representation_harvest_result(...) -> RepresentationHarvestResult: ...
def publish_representation_snapshot(
    result: RepresentationHarvestResult,
    publisher: DelegationRepresentationPublicationPort,
) -> RepresentationHarvestResult: ...
```

- Receipt keys are exactly: `status`, `reason`, `publication_id`, `digest`,
  `mandates`, `positions`, `revocations`, `coverage`.
- `reason` is a safe code or `None`.
- The document contains no owner, principal, representative, or scope subject.

### Error Handling and Logging

- `INFO representation_publication status=%s reason=%s` with safe values only.
- WARN `representation_publication_skipped` for incomplete/disabled runs.
- ERROR `representation_publication_failed` without a traceback containing
  domain values.

### Tests

- `tests/unit/test_delegation_representation_publication.py`: disabled and
  unavailable paths; ready path; size failure; duplicate failure; failure
  isolation (runner result and scientific status unchanged); receipt key set;
  metadata document has no domain tokens.

### Acceptance Criteria

- Publication never changes the scientific result.
- Every outcome is represented in the receipt.

### Verification

- `uv run pytest tests/unit/test_delegation_representation_publication.py -q`
- Expected: pass.

## Task 17: Add the atomic filesystem store and CLI producer

### Intent

The store is a durable read model for the API; the CLI is the only opt-in
producer. Neither may serve as a cognition input.

### Implementation Steps

1. Create `src/persistence/delegation_representation_filesystem.py` with
   `DELEGATION_REPRESENTATION_STORE_SCHEMA = "delegation-representation-store-v1"`.
2. Implement `FilesystemDelegationRepresentationPublisher`:
   - decode and verify the snapshot before taking the lock;
   - take an `fcntl.flock` publish lock;
   - return the existing publication for an identical duplicate;
   - raise `representation_publication_exists` for a conflicting duplicate;
   - write to a temp file and `os.replace` a single `state.json`;
   - enforce `max_publications=16` and `max_bytes=8 MiB` cumulative per run.
3. Implement `FilesystemDelegationRepresentationReader` with `summary`,
   `candidates`, `candidate`, `mandates`, `positions`, `revocations`, and
   `lineage` methods that never build, repair, or mutate an artifact.
4. Add `create_delegation_representation_publisher(...)` and
   `create_delegation_representation_reader(...)` factories.
5. Create `src/research_runner/delegation_representation_composition.py` with
   `PALIMPSEST_REPRESENTATION_ROOT`, `RepresentationProducerOptions`, and
   `producer_options_from_args(args)` reading `representation_root`,
   `representation_max_publications`, `representation_max_bytes`.
6. Implement `publish_representation_harvest(...)` that returns a failed receipt
   for `RepresentationArtifactError` or `OSError` and never raises into the
   scientific path.
7. Implement `write_representation_receipt(root, run_id, receipt)` writing
   `representation-publication-{run_id}.json` atomically.
8. In `src/research_runner/cli.py`, add `--representation-root`,
   `--representation-max-publications` (default 16), and
   `--representation-max-bytes` (default `8_388_608`); parse them beside the
   evidence flags, invoke publication after successful completion, and print
   `representation_publication_status/reason/id`.
9. Do not install the producer in `api`, `simulation`, or `experiments`.
10. `dense`/incomplete stop codes block publication exactly like evidence.

### Required Interfaces and Contracts

- Store layout: `<root>/<run_id>/state.json` plus sidecar receipt.
- Reader methods return typed paging results, never raw JSON.
- CLI flags are opt-in; absence produces a `disabled` receipt and no directory.
- The producer imports `experiments`, `persistence`, and `simulation` only.

### Error Handling and Logging

- `INFO representation_store_published run=%s publications=%d` (run id is a safe
  token).
- WARN `representation_store_restricted` on quota exhaustion.
- ERROR `representation_store_failed code=%s` with no path payloads or digests.

### Tests

- `tests/unit/test_delegation_representation_filesystem.py`: atomic replace;
  lock serialization (two publishers, one winner); identical duplicate returns
  the same id; conflicting duplicate raises; publication quota; byte quota;
  reader page parity with the snapshot; no mutation on read.
- `tests/unit/test_delegation_representation_cli.py`: flag defaults and bounds;
  disabled receipt; publish success; failed publication leaves the runner result
  and metrics unchanged; receipt filename and atomic write.

### Acceptance Criteria

- The store and CLI are opt-in, atomic, quota-bounded, and non-interfering.
- A failure changes only the receipt.

### Verification

- `uv run pytest tests/unit/test_delegation_representation_filesystem.py tests/unit/test_delegation_representation_cli.py -q`
- Expected: pass; `uv run pytest tests/unit/test_evidence_testimony_filesystem.py tests/unit/test_evidence_testimony_cli.py -q` stays green.

## Phase Risks and Mitigations

- Risk: publication runs before scientific completion.
  Mitigation: the composer checks the stop reason first and returns `unavailable`.
- Risk: a partial write corrupts the read model.
  Mitigation: temp file + `os.replace` + flock, with a decode-before-write step.
- Risk: quotas are counted per publication rather than cumulatively.
  Mitigation: the publisher sums existing publication bytes under the lock and is
  tested for the cumulative cap.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
