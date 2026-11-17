# Phase 5: Immutable publication and bounded reads

Plan: [index.md](index.md)
Tasks: 17–20
Depends on: Tasks 13–16

## Objective

Publish a self-contained replication sibling with full trial/report lineage, canonical integrity and snapshot-pinned pagination.

## Current-Code Evidence

| Path | Symbols / behavior | Significance |
| --- | --- | --- |
| `src/simulation/scientific_hypotheses_models.py` | `ScientificHypothesesSnapshot`, 8 MiB cap | Existing strict sibling pattern, not a schema to widen. |
| `src/simulation/scientific_hypotheses_codec.py` | `_TOP_KEYS`, finalize/encode/decode helpers | Exact canonical JSON and full-content digest pattern. |
| `src/simulation/scientific_hypotheses_ports.py` | reader/publisher, query fingerprint | Separate read/publication authority. |
| `src/experiments/scientific_hypotheses_publication.py` | compose/publish/harvest receipts | Trusted analysis-to-artifact bridge. |
| `src/persistence/scientific_hypotheses_filesystem.py` | publisher options, atomic state commit, quota accounting | Store implementation precedent. |
| `src/simulation/scientific_hypotheses_paging.py` | bounded sorted keyset selection | Extend through a sibling, not existing routes. |

## Files to Change

Create `src/simulation/replication_models.py`, `replication_codec.py`, `replication_ports.py`, `replication_paging.py`, `src/experiments/replication_publication.py`, `src/persistence/replication_filesystem.py`; update intentional facades. Create `tests/unit/test_replication_snapshot.py`, `test_replication_publication.py`, `test_replication_store.py`, `test_replication_paging.py`.

## Task 17: Define and encode the replication snapshot

### Intent

Freeze complete bounded research evidence independently of legacy scientific snapshots.

### Implementation Steps

1. Introduce canonical `scientific-replication-snapshot-v1`, policy `scientific-replication.v1`, publication prefix `srep-`. Exact top keys: `snapshot_version`, `policy_version`, `run_id`, `generated_from_tick`, `summary`, `designs`, `attempts`, `results`, `comparisons`, `interpretations`, `collaborations`, `coverage`, `internal_digest`, `publication_id`.
2. Define the frozen DTOs by the exact Phase 4 field tables and the collection mapping below; do not invent a second row schema or remint references during publication. Preserve per-attempt source trial, design/parent references, actual condition comparison, per-result source root, category, uncertainty, and qualified execution token. No raw executable operand IDs, owner IDs, source message body, world law, truth or wall-clock field.
3. Include all retained windows, not just latest-window counts. Window indices 0–511; collection caps match Phase 4. Maximum snapshot bytes 8,388,608. Reports/attempts excluded by caps must appear in coverage; do not emit broken known edges without an unresolved reference status.
4. Canonical JSON: sorted keys, compact separators, ASCII, no NaN, exactly one final LF. Compute SHA-256 over the full document with digest/publication fields blanked; publication ID `srep-` plus first 16 digest hex. Canonicalize row ordering with stable IDs, not set iteration.
5. Decoder rejects duplicate JSON keys, unknown/missing keys at every level, unsupported versions, wrong run, invalid row caps/enums/references, tampering and noncanonical encoding. Keep existing scientific-hypotheses v1 exact bytes and decoders untouched.

### Required Interfaces and Contracts

New `ScientificReplicationSnapshot`, finalize/encode/decode/canonical helpers in simulation only; no analysis imports. Full-content integrity includes condition, uncertainty and source changes even at equal counts.

### Exact Snapshot Collection Mapping

Simulation record types reproduce the exact common/output fields from Phase 4, using their own frozen public DTOs (not analysis imports). The trusted experiment composer maps field by field after normalization and verifies references against one publication-wide identity table.

| Snapshot field | Simulation record type / source | Collection cap |
| --- | --- | --- |
| `designs` | `ScientificReplicationDesignRecord` ← `ReplicationDesignRow` | 4,096 |
| `attempts` | `ScientificReplicationAttemptRecord` ← `ReplicationAttemptRow` | 4,096 |
| `results` | Tagged union of `ScientificReplicationExecutionRecord` (`row_kind="execution"`, `layer="objective"`) and `ScientificReplicationReportRecord` (`row_kind="report"`, `layer="owner_scoped"`) | 4,096 execution + 8,192 report rows |
| `comparisons` | `ScientificReplicationComparisonRecord` ← `ReplicationComparisonRow` | 8,192 |
| `interpretations` | `ScientificReplicationInterpretationRecord` ← `ReplicationInterpretationRow` | 8,192 |
| `collaborations` | `ScientificReplicationCollaborationRecord` ← `ReplicationCollaborationRow` | 2,048 (64 owners × 32 owner contexts) |
| `coverage` | `ScientificReplicationCoverageRecord` ← `ReplicationCoverageRow` | 512 |

The `results` tagged union provides an explicit place to publish committed execution receipts without adding a ninth route or presenting reports as objective outcomes. Each variant has its own exact key set; an execution record cannot contain report/uncertainty/source-appraisal fields and a report cannot claim `layer="objective"`. A comparison carries `basis` so reported disagreements and different physical outcomes remain separate.

`ScientificReplicationSummaryRecord` has exactly `design_count`, `attempt_count`, `execution_count`, `report_count`, `comparison_count`, `interpretation_count`, `collaboration_count`, `participant_count`, `first_tick`, `last_tick`, `coverage`, `availability`, `reason_codes`. Count fields are exact nonnegative integers; first/last tick are explicit null for verified empty input. Counts cover all retained windows and both result variants independently; partial coverage derives from all lanes/notices, not one selected table.

Row identity is `rrow-` plus the full SHA-256 hex digest of canonical ASCII JSON `{"policy_version": policy, "record_type": type_name, "row": <all record fields except row_token>}`, with compact separators/sorted keys and no final LF. The closed record-type strings are `design`, `attempt`, `execution`, `report`, `comparison`, `interpretation`, `collaboration`, `coverage`, independent of Python module/class naming. Canonical snapshot bytes use the separate trailing-LF rule. Deduplicate only byte-identical rows of the same type; conflicting content yields different row IDs. Shared parent/source/report references are mapped once, not rebuilt from projected condition values.

Decode validates record variants, duplicate row IDs, all known in-publication references and closed unresolved statuses. A genuinely missing external source/parent is permitted only as an explicitly unresolved reference; a known existing row reminted inconsistently is corruption. `source_design_digest` is preserved opaque original identity; verify snapshot integrity over projected fields, not by recomputing the original executable design digest.

### Error Handling and Logging

Use `replication_snapshot_invalid`, `replication_snapshot_oversize`, `replication_snapshot_digest_mismatch` safe errors. Codec is log-free; callers log codes/counts only.

### Tests / Acceptance / Verification

`test_replication_snapshot.py`: roundtrip all sections/windows and both result variants, exact top/row key sets, noncanonical/duplicate keys, byte caps, equal-count payload tampering, dangling/unknown reference distinction, every cross-table identity mapping and unchanged legacy scientific fixture bytes. Reject mixed-layer result records and altered row identity. A false report and its contradictory committed execution must both survive in distinct records. Run with coverage.

## Task 18: Add publication/read ports and trusted composition

### Intent

Keep artifact creation outside simulation/API and separate scientific completion from publication readiness.

### Implementation Steps

1. Add `ScientificReplicationReader.read_snapshot(run_id, publication_id=None)` and `ScientificReplicationPublisher.publish(snapshot)` protocols, frozen refs/receipts/options and safe exceptions. Add pure full-filter query fingerprint helper.
2. `compose_replication_snapshot` in experiments maps typed detached analysis into the new DTOs and finalizes canonical identity. Do not import analysis into simulation/persistence/API.
   Reuse the normalized references from the completed-run bridge; do not tokenize a second time, recreate parent IDs from privacy-projected conditions, or derive origin report identity from a receiver-local report token.
3. `publish_replication_snapshot` takes an explicit publisher port; publication is opt-in programmatic composition after successful finalized execution. Add `build_replication_harvest_result` with outcomes `published`, `disabled`, `missing`, `quota_exceeded`, `corrupt` and independent scientific status.
4. Missing exports never produce a fabricated complete-zero snapshot. A valid partial snapshot may publish with partial coverage. No API GET creates, repairs or backfills artifacts; no new CLI capture option is required.

### Required Interfaces and Contracts

No runner/result JSON changes, SQL tables or migration. New API settings later attach readers only; they do not enable capture, science or publication.

### Error Handling and Logging

INFO publication status/count/byte metadata; WARN unavailable/quota safe reasons; ERROR corruption codes. Never exception repr containing subjective snapshot bytes or file content.

### Tests / Acceptance / Verification

`test_replication_publication.py`: explicit disabled path, completed/partial result mapping, scientific-complete/publication-failed distinction, no objective mutation and no concrete adapter imports. Run with snapshot tests and coverage.

## Task 19: Implement atomic quota-bounded filesystem storage

### Intent

Retain immutable publications safely and support explicit historical publication reads.

### Implementation Steps

1. Introduce `scientific-replication-store-v1`; run-safe directory layout follows scientific hypothesis storage: publication files, `state.json`, `store.lock`. Defaults: at most 16 publications and cumulative 8 MiB/run.
2. Under the per-run lock, validate finalized snapshot, inspect current state/quota, write/fsync a temporary publication file, atomically replace publication, then atomically commit the validated state pointer. Never replace existing publication content with differing bytes.
3. Same publication/digest retry is idempotent (`stored=False`, reason `published`). Any existing-ID/content mismatch is corruption. Quotas are cumulative, including already stored publications; no automatic pruning.
4. Reader opens requested publication or latest, verifies state/ref/hash/run/version/canonical bytes and returns a detached snapshot. Reject traversal/symlink escape using the existing adapter's safe-path discipline; roots are configured explicit paths, not payload paths.
5. Preserve old latest/explicit reads across newer publications. A failed write must leave the prior committed state queryable. No SQL dependency.

### Required Interfaces and Contracts

Reader/publisher factory functions `replication_store_reader` / `replication_store_publisher`; separate authority. Adopt existing store lock/fsync primitives locally without importing another bounded feature's private helper.

### Error Handling and Logging

Map missing run, corrupt state, invalid publication, quota and I/O errors to safe feature errors. Do not log snapshots, absolute secret-bearing paths or cursor keys. INFO status/byte/publication counts only.

### Tests / Acceptance / Verification

`test_replication_store.py`: idempotence, cumulative quota, explicit old publication, concurrent writers, failed state commit, missing file, same-ID tampering, malformed state, path escape/symlink, corrupt canonical bytes and retained last-good state. Run snapshot/publication/store tests with coverage; test directories use pytest temporary paths.

## Task 20: Define stable keyset paging and query identity

### Intent

Avoid latest-publication cursor drift and silent first-page truncation.

### Implementation Steps

1. Add pure `page_replication_rows(snapshot, purpose, query, after, limit)`. Purposes: `designs`, `attempts`, `results`, `comparisons`, `interpretations`, `collaborations`, `coverage`.
2. Filters are optional `window_index`, `design_token`, `collaboration_token`; apply only to sections carrying that reference and reject unsupported filter/purpose combinations. All filters are exact equality, no free-text search.
3. Keyset order is `(window_index, stable_row_token)`; designs use creation window/design token, coverage uses window index alone. Require unique keys; preserve conflicting result rows with different stable tokens.
   Results page both execution/report variants in this one stable order. Canonical row tokens include record type, so variants cannot collide. Do not deduplicate a report merely because its `result_root_token` names the same experiment as an execution record.
4. Limits default 100, maximum 500. Return rows, after key and coverage; missing/unavailable sections remain distinguished from known-empty. Bind all filters and purpose in the canonical query fingerprint.
5. HTTP must resolve an explicit publication from the first response/cursor and read that immutable publication on subsequent pages; never substitute the latest snapshot while validating a previous cursor.

### Required Interfaces and Contracts

Simulation paging is pure and has no signing key/clock/HTTP imports. No page selection mutates storage or cognition.

Exact filter matrix (`publication_id`, cursor and limit apply to every page):

| Purpose | `window_index` | `design_token` | `collaboration_token` |
| --- | --- | --- | --- |
| designs | yes | yes | no |
| attempts | yes | yes | yes |
| results | yes | no | no |
| comparisons | yes | yes | yes |
| interpretations | yes | yes | yes |
| collaborations | yes | yes | yes |
| coverage | yes | no | no |

Do not put a subjective design/collaboration field on an objective execution row merely to permit filtering. Results return both typed lanes for the selected window. UI must omit unsupported filters per purpose and explicitly label results/coverage as window-scoped when a design/collaboration filter narrows other sections.

### Error Handling and Logging

Invalid purpose/filter/after tuple raises safe query errors. Paging logs are optional DEBUG counts/purpose only; never cursor contents or selected rows.

### Tests / Acceptance / Verification

`test_replication_paging.py`: 501+ rows including both result variants, no duplicates/omissions, conflicting reports across pages, exact-filter identity, unsupported combinations, zero/negative/bool limits, stable order and complete all-page equality. Run all Phase 5 tests with coverage.

## Phase Risks and Mitigations

- Aggregate-only evidence cannot support lineage: publish bounded per-trial/per-report rows.
- New publication invalidates browsing: pin pages to publication identity.
- Oversize evidence: partial coverage/quota receipt, never silent truncation or mutation of an old artifact.

## Exact Task Verification Commands

```bash
# Task 17
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_replication_snapshot.py tests/unit/test_scientific_hypotheses_snapshot.py -q
# Task 18
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_replication_publication.py tests/unit/test_replication_snapshot.py -q
# Task 19
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_replication_store.py tests/unit/test_replication_publication.py tests/unit/test_replication_snapshot.py -q
# Task 20
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_replication_paging.py tests/unit/test_replication_store.py -q
```

## Phase Completion Checklist

- Tasks 17–20 pass canonical integrity, store fault, and complete pagination tests.
- Existing scientific snapshot/store contracts remain unchanged.
