# Phase 5: Composition and Durable Publication

Plan: [index.md](index.md)
Tasks: 18-19
Depends on: Tasks 9-10 and 15 / Phase 4 Tasks 16-17

## Objective

Compose a completed run's detached diplomacy analysis into one canonical snapshot
and receipt, then publish it atomically through a quota-bounded filesystem store
driven by an opt-in CLI producer. Publication failures never change the
scientific result.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/experiments/delegation_representation_harvest.py` | `RepresentationHarvest`; `build_completed_run_representation_harvest` | Completed-run harvest precedent |
| `src/experiments/delegation_representation_publication.py` | `RepresentationHarvestResult`; receipt states `disabled`/`unavailable`/`ready`/`published`/`failed` | Receipt/state precedent |
| `src/experiments/evidence_testimony_publication.py` | 57-341 | Post-completion publication precedent |
| `src/persistence/delegation_representation_filesystem.py` | `DELEGATION_REPRESENTATION_STORE_SCHEMA`; atomic `state.json`; `publications/<id>.json`; reader/publisher factories | Store precedent |
| `src/persistence/evidence_testimony_filesystem.py` | 52-327 | Quota and lock precedent |
| `src/research_runner/delegation_representation_composition.py` | `REPRESENTATION_ROOT_ENV`; `producer_options_from_args`; `publish_representation_harvest`; `write_representation_receipt` | CLI producer precedent |
| `src/research_runner/cli.py` | `--representation-root`, `--representation-max-publications`, `--representation-max-bytes` | Flag and bound precedent |
| `src/experiments/metric_collection.py` | 226 `inputs_with_opt_in_metric_rows` | Opt-in harvest wiring |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/experiments/diplomacy_harvest.py` | modify | Add completed-run harvest builder |
| `src/experiments/diplomacy_publication.py` | create | Harvest result, receipt, snapshot composition |
| `src/persistence/diplomacy_filesystem.py` | create | `diplomacy-store-v1` atomic store |
| `src/research_runner/diplomacy_composition.py` | create | Opt-in producer bridge |
| `src/research_runner/cli.py` | modify | Three diplomacy flags and receipt fields |
| `tests/unit/test_diplomacy_publication.py` | create | Composition/receipt tests |
| `tests/unit/test_diplomacy_store.py` | create | Store tests |

## Task 18: Compose completed-run snapshots and receipts

### Intent

The composer is the only bridge from analysis to artifact. It must be opt-in,
post-completion, and incapable of changing the run result.

### Implementation Steps

1. Extend `src/experiments/diplomacy_harvest.py` with
   `build_completed_run_diplomacy_harvest(runner_result, *, objective_events,
   entity_to_agent, analysis_inputs) -> DiplomacyHarvest`, mirroring
   `build_completed_run_representation_harvest` (54-66) and returning `None`-safe
   empty harvests when the diplomacy ledger or lane inputs are absent.
2. Create `src/experiments/diplomacy_publication.py` with
   `DiplomacyHarvestResult` (harvest, snapshot, summary, analysis, layers,
   publication id), `build_diplomacy_harvest_result(harvest, *, run_id,
   revision, window_end)`, `publish_diplomacy_snapshot(result, port)`, and
   `diplomacy_publication_document(receipt)`. The builder re-derives current
   envoy standings and instrument statuses with Task 9 at `window_end` and
   includes relation/termination rows; it never publishes the accreditation-time
   snapshot as current.
3. Receipt states are exactly `disabled`, `unavailable`, `ready`, `published`,
   `failed`; each carries a safe reason code only.
4. `build_diplomacy_harvest_result` returns `unavailable` when the run is
   incomplete, the diplomacy ledger is absent, or required lane inputs are
   missing. It never invents zero-filled rows.
5. `publish_diplomacy_snapshot` uses the Task 17 publication port. A duplicate
   publication id with identical bytes is idempotent (`published`); with
   different bytes it returns `failed` / `diplomacy_publication_exists` and
   leaves the existing artifact untouched.
6. Size/cap overflow returns `failed` / `diplomacy_size_limit` and publishes
   nothing.
7. Record publication readiness separately from scientific status; never mutate
   `runner_result`, `RunnerResultDocument`, or the metric bundle.

### Required Interfaces and Contracts

```python
def build_diplomacy_harvest_result(
    harvest: DiplomacyHarvest,
    *,
    run_id: str,
    revision: str,
    window_end: int,
) -> DiplomacyHarvestResult: ...

def publish_diplomacy_snapshot(
    result: DiplomacyHarvestResult,
    port: DiplomacyPublicationPort,
) -> DiplomacyPublicationReceipt: ...
```

- The composer imports `analysis`, `agents.cognition.diplomacy` contracts, and
  `simulation` contracts only; it never imports the runner, engine, or API.
- Publication is idempotent and failure-isolated.
- No receipt carries party, envoy, subject, or mandate data.
- Current standings are computed at `window_end`; a revoked/superseded mandate
  publishes the post-revocation status, not the accreditation snapshot.

### Requirement Evidence (when reconciliation applies)

- `.ai-factory/ARCHITECTURE.md`: publication readiness is separate from
  scientific status; analysis never feeds cognition.
- `src/experiments/evidence_testimony_publication.py` 57-341: identical receipt
  discipline.

### Error Handling and Logging

- Codes: `diplomacy_run_incomplete`, `diplomacy_input_unavailable`,
  `diplomacy_size_limit`, `diplomacy_publication_exists`.
- `INFO diplomacy_publication state=%s reason=%s`.
- `ERROR diplomacy_publication_failed reason=storage` on an adapter fault.
- Never log publication ids, paths, or payload bytes.

### Tests

- `tests/unit/test_diplomacy_publication.py`: disabled when no ledger;
  unavailable when incomplete; ready with a complete fixture; published on a
  successful port; idempotent identical re-publish; conflicting bytes rejected;
  size ceiling; relation/termination rows published; a mandate revoked before
  `window_end` publishes the current status rather than the accreditation
  snapshot; receipt has no identity payload; runner result unchanged
  (deep-equality before/after).

### Acceptance Criteria

- Exactly one canonical snapshot per completed run.
- A failure changes only the receipt.

### Verification

- `uv run pytest tests/unit/test_diplomacy_publication.py -q`
- Expected: pass.

## Task 19: Add the atomic filesystem store and CLI producer

### Intent

Researchers need a durable, atomic, quota-bounded read model and an opt-in CLI
path that never starts HTTP and never touches the simulation loop.

### Implementation Steps

1. Create `src/persistence/diplomacy_filesystem.py` with
   `DIPLOMACY_STORE_SCHEMA = "diplomacy-store-v1"`,
   `FilesystemDiplomacyPublisher`, `FilesystemDiplomacyReader`,
   `create_diplomacy_publisher`, and `create_diplomacy_reader`.
2. Layout: a run root containing `state.json` (atomic replace via temp file +
   `os.replace`) and `publications/<publication_id>.json`; a lock file guards
   concurrent publication; a partially written publication is never visible.
   `state.json` indexes publication ids/digests only; relation, termination, and
   other scientific rows live inside the encoded snapshot, never in the index.
3. Enforce cumulative per-run quotas: max publications (default 16, range
   1..1024) and max bytes (default 8 MiB, range 1..268435456). Exceeding a quota
   returns `diplomacy_quota_exceeded` and leaves prior publications intact.
4. Readers verify the digest on load and reject mismatches with
   `diplomacy_publication_digest_mismatch`.
5. Create `src/research_runner/diplomacy_composition.py` with
   `DIPLOMACY_ROOT_ENV = "PALIMPSEST_DIPLOMACY_ROOT"`,
   `DiplomacyProducerOptions`, `producer_options_from_args`,
   `publish_diplomacy_harvest`, and `write_diplomacy_receipt`.
6. Add CLI flags to `src/research_runner/cli.py`: `--diplomacy-root`,
   `--diplomacy-max-publications`, `--diplomacy-max-bytes`; print
   `diplomacy_publication_status`, `diplomacy_publication_reason`, and
   `diplomacy_publication_id` fields in the existing receipt format.
7. An unset root yields a `disabled` receipt and no filesystem access.
8. The producer runs only after the run completes successfully; it never imports
   `api`.

### Required Interfaces and Contracts

```python
DIPLOMACY_STORE_SCHEMA: Final[str] = "diplomacy-store-v1"
DIPLOMACY_ROOT_ENV: Final[str] = "PALIMPSEST_DIPLOMACY_ROOT"

class DiplomacyProducerOptions:
    root: Path | None
    max_publications: int = 16
    max_bytes: int = 8 * 1024 * 1024
```

- Atomic visibility: a reader sees either the previous state or the new complete
  state.
- Quotas are cumulative per run and never delete existing publications.
- CLI composition imports no HTTP server and no client.

### Requirement Evidence (when reconciliation applies)

- `src/persistence/evidence_testimony_filesystem.py` 52-327 and
  `src/research_runner/evidence_testimony_composition.py` 39-185: store and
  producer discipline.
- `.ai-factory/ARCHITECTURE.md`: persistence adapters implement ports; the
  producer is composition-only.

### Error Handling and Logging

- Codes: `diplomacy_quota_exceeded`,
  `diplomacy_publication_digest_mismatch`, `diplomacy_store_lock_timeout`,
  `diplomacy_store_unavailable`.
- `INFO diplomacy_store_published publications=%s bytes=%s`.
- `WARN diplomacy_store_quota reason=%s`.
- Never log paths, publication ids, or snapshot bytes.

### Tests

- `tests/unit/test_diplomacy_store.py`: atomic publish/read; concurrent publish
  leaves one complete artifact; quota rejection preserves prior publications;
  digest mismatch rejected; unset root disables; CLI flags parse and bounds fail
  closed; producer imports neither `api` nor `simulation.runner`.

### Acceptance Criteria

- Durable, atomic, quota-bounded publication works without affecting the run.
- The CLI path is opt-in and HTTP-free.

### Verification

- `uv run pytest tests/unit/test_diplomacy_store.py tests/unit/test_research_runner_cli.py -q`
- Expected: pass.

## Phase Risks and Mitigations

- Risk: publication mutates the scientific result.
  Mitigation: composer takes a frozen harvest and a deep-equality test.
- Risk: partial files are visible after a crash.
  Mitigation: temp-file + atomic replace plus a concurrency test.
- Risk: quotas silently delete data.
  Mitigation: rejection preserves prior publications and returns a safe code.

## Phase Completion Checklist

- Every task in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
