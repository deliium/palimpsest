# Phase 5: Composition and Durable Publication

Plan: [index.md](index.md)
Tasks: 16-17
Depends on: Phase 4 / Task 15

## Objective

Compose a completed run's evidence analysis into `evidence-testimony-snapshot-v1`,
publish it through an atomic quota-bounded filesystem store, and expose an
opt-in CLI producer whose receipt never changes the scientific result.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/experiments/dispute_harvest.py` | `DisputeHarvest` 36-50; entity resolution 60-95; `build_completed_run_dispute_harvest` 106-185 | Harvest precedent and entity mapping |
| `src/experiments/dispute_publication.py` | harvest result 361-367; draft builders 369-1093; `build_dispute_harvest_result` 1096-1304; `_finalize` 1307-1386; publication document 1389-1395 | Snapshot composition and receipts |
| `src/persistence/dispute_filesystem.py` | store schema 48-52; lock/read/atomic JSON 79-129; publisher 132-210; reader 213-418; factories 421-439 | Atomic store precedent |
| `src/research_runner/dispute_composition.py` | env root 32; stop codes 34-43; options 46-78; publish 107-165; receipt 186-216 | CLI producer and failure isolation |
| `src/research_runner/cli.py` | dispute options 978-989; publish/receipt 1310-1335; flags 1509-1511 | CLI wiring points |
| `src/research_runner/__init__.py` | exports 4-17 | Public producer facade |
| `tests/unit/test_dispute_publication.py` | composition and failure-isolation tests | Test shape |
| `tests/unit/test_dispute_filesystem.py` | quota and duplicate tests | Test shape |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/experiments/evidence_testimony_harvest.py` | create | Harvest, entity mapping, coverage/receipt |
| `src/experiments/evidence_testimony_publication.py` | create | Snapshot drafting, caps, finalize, receipts |
| `src/experiments/__init__.py` | modify | Public facade exports |
| `src/persistence/evidence_testimony_filesystem.py` | create | Atomic publisher/reader, quotas |
| `src/research_runner/evidence_testimony_composition.py` | create | CLI producer, env root, status isolation, receipt |
| `src/research_runner/cli.py` | modify | Three flags and producer call |
| `src/research_runner/__init__.py` | modify | Re-export producer options/functions |
| `tests/unit/test_evidence_testimony_publication.py` | create | Composition, caps, receipts |
| `tests/unit/test_evidence_testimony_filesystem.py` | create | Store atomicity, quotas, duplicate handling |
| `tests/unit/test_evidence_testimony_cli.py` | create | Options, receipts, disabled/unavailable/failed |

## Task 16: Compose completed-run snapshots and receipts

### Intent

Turn detached harvest output into one canonical snapshot and a receipt whose
status is independent of scientific success. Composition must be pure and
bounded.

### Implementation Steps

1. Create `src/experiments/evidence_testimony_harvest.py`:
   - `EvidenceTestimonyHarvest` frozen slots: `rows`, `windows`, `analysis`,
     `summary`, `layers`, `coverage`, `receipt_status`, `receipt_reason`,
     `truncated`.
   - `build_completed_run_evidence_harvest(runner_result, *,
     committed_events=(), entity_to_agent=None, window_ticks=100)`:
     - read `runner_result.evidence_ledgers`; require an ordered sequence;
     - resolve entity→agent from an explicit map, then
       `runner_config.agents`, then owner fallback;
     - harvest rows, build windows, derive lineage, summarize, project layers;
     - map committed events to objective anchors only when supplied; otherwise
       coverage is `partial` with reason `evidence_testimony_no_objective_events`;
     - receipt status `empty` when no owner rows exist, otherwise `ok`;
       reason `evidence_testimony_truncated` when any ledger notice or pruned
       counter exists.
2. Create `src/experiments/evidence_testimony_publication.py`:
   - `EvidenceTestimonyHarvestResult(harvest, snapshot, receipt, published)`.
   - Draft builders for each snapshot table, copying only closed fields and
     content-addressed ids.
   - Apply caps: candidates 2048, items per candidate 64, contradictions per
     candidate 32, sources 8192, testimony 8192, items 16384, custody 16384,
     contradictions 8192, evaluations 16384.
   - Prune contradiction refs that point to dropped candidates/items and record
     truncation.
   - Build the snapshot via `_finalize`: publication id, digest, encode/decode
     round-trip, receipt status `published`/`empty`, reason
     `evidence_testimony_published`/`evidence_testimony_truncated`.
   - `publish_evidence_testimony_snapshot(snapshot, *, publisher)` publishes
     exactly once and returns the publication receipt.
   - `evidence_testimony_publication_document(result)` returns canonical
     metadata only (run id, publication id, digest, counts, coverage).
3. Composition must not import `api`, `persistence`, or `research_runner`.
4. `src/experiments/__init__.py`: export `EvidenceTestimonyHarvest`,
   `build_completed_run_evidence_harvest`,
   `EvidenceTestimonyHarvestResult`, `build_evidence_testimony_harvest_result`,
   `publish_evidence_testimony_snapshot`, and
   `evidence_testimony_publication_document`, and add them to `__all__`,
   mirroring the dispute exports at 238-246 and 595-746.

### Required Interfaces and Contracts

- The snapshot is immutable after finalization.
- Receipt statuses are exactly `empty`, `ok`, `published`, `unavailable`, and
  `failed` across the harvest/composition boundary; scientific status is never
  changed.
- Missing objective events never fabricate anchors; coverage becomes `partial`.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "analysis is read-only"; "Publication is opt-in,
  post-completion".
- `src/experiments/dispute_harvest.py` 106-185;
  `src/experiments/dispute_publication.py` 1096-1395.

### Error Handling and Logging

- Composition failures raise `EvidenceTestimonyArtifactError`.
- WARN `evidence_testimony_harvest_partial reason=%s` (code only).
- INFO `evidence_testimony_snapshot_built candidates=%s items=%s coverage=%s`
  (counts only).

### Tests

- Create `tests/unit/test_evidence_testimony_publication.py`:
  - a completed run with two owners produces ordered candidates and one
    snapshot;
  - no objective events yields partial coverage and no anchors;
  - caps truncate deterministically and set receipt reason;
  - an empty ledger set yields `empty`;
  - composition does not import API/persistence/research_runner;
  - the snapshot decodes and re-encodes byte-identically.
- Command: `uv run pytest tests/unit/test_evidence_testimony_publication.py -q`.

### Acceptance Criteria

- One canonical snapshot per run with deterministic bytes.
- Scientific result is untouched by composition.

### Verification

- `uv run pytest tests/unit/test_evidence_testimony_publication.py -q`
- Expected: pass.

## Task 17: Add the atomic filesystem store and CLI producer

### Intent

Persist and serve published snapshots through the same filesystem pattern as
other V4 contexts, with quotas, idempotent duplicate handling, and a CLI
receipt that records publication separately from scientific status.

### Implementation Steps

1. Create `src/persistence/evidence_testimony_filesystem.py`:
   - `EVIDENCE_TESTIMONY_STORE_SCHEMA = "evidence-testimony-store-v1"`.
   - Layout: `<root>/state.json`, `<root>/publications/<publication_id>.json`,
     `<root>/.publish.lock`.
   - `_publish_lock`, `_read_state`, `_atomic_json`.
   - `FilesystemEvidenceTestimonyPublisher(publisher, *, max_publications=16,
     max_bytes=8 * 1024 * 1024)`:
     - verify digest;
     - same id + same bytes is idempotent;
     - same id + different bytes raises
       `evidence_testimony_publication_exists`;
     - enforce per-run publication and cumulative byte quota with
       `evidence_testimony_size_limit`;
     - atomic replace and state update.
   - `FilesystemEvidenceTestimonyReader(reader)`:
     - latest publication per run;
     - summary/candidates/candidate/sources/contradictions/lineage;
     - verify digest and decode;
     - cap each detail relation set at 500 and set `truncated`.
   - Factories `create_evidence_testimony_publisher`,
     `create_evidence_testimony_reader`.
2. Create `src/research_runner/evidence_testimony_composition.py`:
   - `EVIDENCE_ROOT_ENV = "PALIMPSEST_EVIDENCE_ROOT"`.
   - Incomplete stop codes tuple for `unavailable`.
   - `EvidenceTestimonyProducerOptions` and `producer_options_from_args`
     reading `evidence_root`, `evidence_max_publications` (1..1024),
     `evidence_max_bytes` (1..268435456).
   - `publish_evidence_testimony_harvest(...)`:
     - no root → status `disabled`, no write;
     - missing/incomplete scientific result → status `unavailable` with a
       prerequisite code;
     - artifact/OSError → status `failed`, `published=False`, no re-raise;
     - success → publication receipt.
   - `write_evidence_testimony_receipt(...)` writes
     `<artifact_root>/evidence-publication-<run_id>.json` atomically; failures
     are logged and ignored.
3. `src/research_runner/cli.py`: add `--evidence-root`,
   `--evidence-max-publications`, `--evidence-max-bytes` to the same generator
   argument group as the dispute flags (1509-1511); parse them beside the
   dispute options (978-989); publish after successful scientific completion
   (1310-1335); print the receipt. Add the bounds (1..1024 and
   1..268435456) to the parser and extend the CLI help/option test so an
   unchanged help snapshot cannot silently omit the new flags.
4. `src/research_runner/__init__.py`: export the options, producer, and receipt
   functions.

### Required Interfaces and Contracts

- Store and producer never import `api`, `analysis`, or `simulation` engine
  internals.
- A publication failure changes only the receipt.
- The receipt filename and envelope are distinct from the dispute receipt.

### Requirement Evidence

- `src/persistence/dispute_filesystem.py` 48-439;
  `src/research_runner/dispute_composition.py` 32-216.
- `.ai-factory/ARCHITECTURE.md` "Publication is opt-in, post-completion,
  atomic".

### Error Handling and Logging

- Store errors use safe codes only.
- WARN `evidence_testimony_publication_failed reason=%s` (code only).
- INFO `evidence_testimony_published status=%s` (status only).
- Never log paths, ids, digests, or payloads at INFO.

### Tests

- Create `tests/unit/test_evidence_testimony_filesystem.py`:
  - publish then read summary/candidates/detail;
  - duplicate same bytes is idempotent;
  - duplicate different bytes fails;
  - quota and byte limits fail closed;
  - concurrent lock acquisition is safe;
  - a corrupted publication fails digest verification.
- Create `tests/unit/test_evidence_testimony_cli.py`:
  - no root → `disabled`;
  - incomplete run → `unavailable` with a prerequisite;
  - storage error → `failed` and scientific status unchanged;
  - successful publish writes the receipt atomically;
  - option bounds are validated;
  - the parser help includes all three `--evidence-*` flags and rejects
    out-of-range publication/byte limits.
- Commands:
  `uv run pytest tests/unit/test_evidence_testimony_filesystem.py tests/unit/test_evidence_testimony_cli.py -q`

### Acceptance Criteria

- Publication is atomic, quota-bounded, idempotent, and isolated.
- The CLI receipt is written even when publication is disabled or fails.

### Verification

- `uv run pytest tests/unit/test_evidence_testimony_filesystem.py tests/unit/test_evidence_testimony_cli.py -q`
- Expected: pass.

## Phase Risks and Mitigations

- Risk: composition accidentally reads live cognition.
  Mitigation: it accepts only `runner_result` and detached events.
- Risk: quota accounting drifts from the dispute store pattern.
  Mitigation: mirror the tested dispute publisher and reuse its atomic helpers
  where imports allow.
- Risk: CLI failure changes scientific status.
  Mitigation: explicit `failed`/`unavailable` receipts and exception swallowing
  with WARN.

## Phase Completion Checklist

- Every Task 16-17 in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
