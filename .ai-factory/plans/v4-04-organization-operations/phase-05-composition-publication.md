# Phase 5: Composition and Durable Publication

Plan: [index.md](index.md)
Tasks: 15-16
Depends on: Phase 4 / Tasks 13-14

## Objective

Compose `organization-snapshot-v2` from a completed-run harvest, publish it
opt-in and atomically, and serve v1/v2 publications from the filesystem store.
Composition failures change only the publication receipt; they never change the
scientific result.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/experiments/organization_publication.py` | `OrganizationHarvestResult` 68-78; member/structural helpers 80-131; candidate/dissolved records 133-179; build 181-294; finalize 296-327; receipt 347-366 | Add operation records, counts, v2 upgrade, and truncation provenance. |
| `src/experiments/organization_harvest.py` | harvest 46-117 | Carries operation rows and summary into the publisher. |
| `src/research_runner/organization_composition.py` | options 34-70; publish 73-135 | No new CLI flag; receipt gains operation counts and schema version. |
| `src/persistence/organization_filesystem.py` | schema constant 43; `_StoredState` 92-98; publisher 100-220; reader 222-322; factories 324-346 | Accept v1/v2, publish v2, expose operation counts/pages. |
| `src/simulation/organization_models.py` | v2 contract from Task 13 | The composer targets the exact v2 schema. |
| `src/simulation/organization_ports.py` | `OrganizationPublication` 78-95; summary 97-124 | The publication payload is opaque bytes; the store verifies by decode. |
| `tests/unit/test_organization_publication.py` | 250-290 | v1 assertions must be updated to accept v2 while keeping v1 compatibility. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/experiments/organization_publication.py` | modify | Build operation records/counts, upgrade to v2, cap/truncate, receipt fields. |
| `src/experiments/organization_harvest.py` | modify | Pass operation rows/summary into the result. |
| `src/research_runner/organization_composition.py` | modify | Receipt logging/fields only; no new options. |
| `src/persistence/organization_filesystem.py` | modify | Supported schemas, summary operation count, reader operations page. |
| `src/persistence/__init__.py` | modify only if exports change | Keep factories; no new adapter. |
| `tests/unit/test_organization_operations_publication.py` | create | v2 composition, caps, ids, receipts, failure isolation. |
| `tests/unit/test_organization_operations_filesystem.py` | create | v1/v2 store, quotas, locks, duplicates, reader pages. |

## Task 15: Compose completed-run v2 snapshots and receipts

### Intent

Turn the detached operation summary into published `orgop-` records with stable
ids and no owner-local provenance ids. Truncation and unresolved anchors are
explicit, never silent.

### Implementation Steps

1. Extend `OrganizationHarvestResult` with `operation_count: int = 0` and
   `schema_version: str = "organization-snapshot-v2"`.
2. Add `_operation_records(candidate_operations)`:
   - for each operation source (control, admission, departure, assignment,
     procedure action, commitment, decision, action), create one
     `OrganizationOperationRecord` with this fixed act/stance/outcome mapping:
     | Source | `act` | `stance` | `outcome` |
     | --- | --- | --- | --- |
     | control, stance in `claimed`/`recognized`/`shared` | `authorize_control` | stored stance | `observed` |
     | control, stance `former` | `revoke_control` | `former` | `observed` |
     | admission | `admit` | stored stance | `observed` |
     | departure | `depart` | stored stance | `observed` |
     | assignment, stance in `assigned`/`claimed`/`vacant` | `assign` | stored stance | `observed` |
     | assignment, stance `removed` | `remove` | `removed` | `observed` |
     | procedure action | `invoke_procedure` | `disputed` if contested else `claimed` | its stored outcome |
     | commitment, stance in `declared`/`accepted` | `declare_commitment` | stored stance | `observed` |
     | commitment, stance `fulfilled` | `fulfill_commitment` | `fulfilled` | `completed` |
     | decision | its stored act | `disputed` if contested, else `unknown` if authority is unknown, else `claimed` | `observed` |
     | action | its stored act or `record_decision` | `disputed` if contested else `claimed` | its stored outcome |
   - `operation_id = organization_publication_operation_id(
     candidate.organization_id, domain, tick, ordinal, content_digest)` where
     `content_digest` is a SHA-256 over the record's non-id publication fields;
   - sort by `(tick, domain, operation_id)`;
   - deduplicate equal records by the full publication-visible content:
     `(domain, act, stance, authority_basis, provenance_code, outcome,
     command_kind, tick, first_tick, last_tick, anchor_kind, anchor_id,
     target_kind, support_count, contest_count, resolved)`; or dedupe by the
     computed `content_digest` before assigning `orgop-` ids. Never collapse
     records that differ only in outcome/command/support/contest;
   - cap at 64 per candidate; if truncated, add
     `provenance_code="operations_truncated"` to the snapshot and do not silently
     drop the last row;
   - map owner-local office/commitment anchors to `anchor_kind="owner_local"`,
     `anchor_id=None`;
   - map unresolved anchors to `anchor_kind="unknown"`, `anchor_id=None`,
     `resolved=False`;
   - derive `provenance_code` deterministically: use the stored code for
     decisions/actions; for controls/admissions/departures/assignments/
     commitments use `contested` if contested, else `self_authored`/
     `role_authorized`/`decision_supported` from the authority basis, else
     `unknown_authority`; for procedure actions use `contested` if contested,
     else `procedure_recognized` when authorized by a procedure, else
     `observed_effect`, else `unknown_authority`;
   - derive `target_kind` deterministically: admission/departure and decision/
     action acts `admit`/`depart` → `member`; assignment and acts `assign`/
     `remove` → `office`; control/procedure/commitment and other decision/action
     acts → `anchor` when `anchor_id` is present, otherwise `none`;
   - never publish `orgd-`/`orga-`/`orgc-`/owner ids or a target id; `target_kind`
     is the only target marker.
3. Extend `_candidate_record` and `_dissolved_record` to include
   `operations=_operation_records(...)`.
4. Extend window records with `operation_count`/`contested_operation_count` and
   objective rows with `operation_action_count`.
5. In `build_organization_harvest_result`:
   - read the operation summary from the harvest;
   - build operations before candidates;
   - enforce the global 4096-operation cap across candidate tuples in
     `(organization_id, tick, domain, operation_id)` order and add
     `operations_truncated` if needed;
   - call `upgrade_organization_snapshot` on the assembled snapshot before
     `_finalize`;
   - `_finalize` computes the v2 publication id and re-encodes/decodes for
     byte identity;
   - receipt adds `schema_version`, `operation_count`, `contested_operation_count`.
6. In `organization_publication_document`, include only counts/schema/provenance;
   never ids, labels, anchors, or owner ids.
7. In `research_runner/organization_composition.py`, keep the same options and
   failure isolation; log `organization_operation_publication_published
   run_id=%s publication_id=%s operations=%s`.

### Required Interfaces and Contracts

- Publication is opt-in and post-completion; an incomplete run remains
  `unavailable` and a storage failure remains `failed`.
- The scientific result is never mutated or re-run.
- `orgop-` ids are deterministic from publication-visible content only; they do
  not depend on owner-local ids or a mutable counter.
- A duplicate publication id with different bytes is rejected by the store, not
  overwritten.
- The artifact is v2; v1 remains readable.
- No new CLI flag or environment variable is added.

### Requirement Evidence

- V4-03 decision 11 and 19: opt-in publication, failure isolation, no owner
  claim detail in the artifact.
- V3-39/V4-02 publication precedent.
- Original Request: "Record provenance of decisions and actions"; the published
  records carry provenance codes and authority basis.

### Error Handling and Logging

- `OrganizationArtifactError` is caught by the producer; receipt status
  `failed`/`unavailable` with a safe code.
- WARN on truncation/orphaning counts only.
- INFO on successful publication with counts and publication id.

### Tests

- `tests/unit/test_organization_operations_publication.py`:
  - a harvest with operations publishes v2 and the expected counts;
  - owner ids, `orgd-`, `orga-`, `orgc-`, and office ids do not appear in bytes;
  - `orgop-` ids are stable across repeated builds and differ when content
    changes;
  - records differing only in outcome, command kind, support, or contest remain
    distinct and receive different ids;
  - 65 operations on one candidate truncate with `operations_truncated`;
  - unresolved anchors publish `resolved=False` and no anchor id;
  - an incomplete run produces `unavailable`, not a publication;
  - a storage failure changes only the receipt;
  - the receipt is id-free.
- Command:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_publication.py tests/unit/test_organization_publication.py tests/unit/test_organization_cli.py -q`

### Acceptance Criteria

- Completed runs compose deterministic v2 snapshots.
- Operation provenance is published without owner-local identifiers.
- Failure isolation is preserved.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_publication.py tests/unit/test_organization_publication.py tests/unit/test_organization_cli.py -q`
- Expected: pass.

## Task 16: Extend the atomic filesystem store for v1/v2

### Intent

Keep the existing append-only, single-writer, quota-bounded store. It must accept
legacy v1 publications, publish v2, report operation counts in the summary, and
serve operation pages without repair or mutation.

### Implementation Steps

1. Replace the single `_SNAPSHOT_SCHEMA` constant with
   `_SUPPORTED_SNAPSHOT_SCHEMAS = SUPPORTED_ORGANIZATION_SNAPSHOT_SCHEMAS`.
2. `FilesystemOrganizationReader._load`:
   - decode with the v1/v2-aware codec;
   - reject an unknown schema;
   - keep the publication-id and SHA-256 digest checks.
3. `summary`:
   - set `operation_count=sum(len(candidate.operations) for candidate in
     snapshot.candidates)`;
   - pass through the accepted `schema_version`.
4. Add `operations(run_id, publication_id, offset, limit, domain=None,
   organization_id=None) -> OrganizationRowSelection`:
   - load the snapshot;
   - flatten candidate operations, then filter by exact domain and candidate id;
   - sort by `(tick, domain, operation_id)` before selecting;
   - call `select_organization_rows` with `MAX_RESPONSE_BYTES`.
5. `candidate` returns the candidate record with its `operations` tuple.
6. `publish` remains schema-agnostic and byte-preserving; it does not decode or
   rewrite v1/v2. The digest and manifest are unchanged.
7. Keep the store schema `organization-store-v1`, quotas, lock, duplicate-id,
   and corruption behavior unchanged.
8. Log INFO `organization_loaded run_id=%s schema=%s operations=%s`.

### Required Interfaces and Contracts

- Existing v1 directories remain readable with `operation_count=0`.
- New publications are v2 because the composer upgrades them; the store does not
  force an upgrade on read.
- The store never imports analysis or agents.
- The store flattens candidate operations for paging; detail uses the candidate
  tuple. No duplicate top-level operation list exists.
- Quota accounting remains payload bytes plus the existing allowance.

### Requirement Evidence

- V4-03 filesystem store contract.
- `.ai-factory/ARCHITECTURE.md` "Read-only presentation" and "no SQL migration".
- Original Request: durable provenance with no organization-owned store.

### Error Handling and Logging

- Missing publication → `organization_publication_missing` (reader returns
  `None` from `summary`).
- Corrupt state/schema/digest → `organization_store_corrupt` or
  `organization_digest_mismatch`.
- Lock/quota/duplicate semantics unchanged.
- Logs are counts/schema only.

### Tests

- `tests/unit/test_organization_operations_filesystem.py`:
  - write a v2 snapshot and read it back with operation counts/pages;
  - a hand-written v1 fixture remains readable with zero operations;
  - unknown schema fails closed;
  - duplicate id with different bytes fails; identical bytes are idempotent;
  - quota and lock behavior unchanged;
  - operations filter by domain and candidate id;
  - the store imports no analysis/agents modules.
- Command:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_filesystem.py tests/unit/test_organization_filesystem.py -q`

### Acceptance Criteria

- v1/v2 publications are readable; v2 is written by the composer.
- Operation counts/pages are served without mutation.
- Quotas, locks, atomicity, and failure codes are unchanged.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_filesystem.py tests/unit/test_organization_filesystem.py -q`
- Expected: pass.

## Phase Risks and Mitigations

- Risk: the v2 composer leaks owner-local ids.
  Mitigation: the publication record has no such field and the test scans bytes.
- Risk: v1 publications stop loading.
  Mitigation: the reader uses the v1/v2-aware codec and a v1 fixture test.
- Risk: a publication failure changes the run result.
  Mitigation: the existing producer catch/isolation path is preserved and tested.

## Phase Completion Checklist

- Every Task 15-16 acceptance criterion is met.
- v2 composition and v1/v2 storage work end to end.
- No new CLI option, migration, event, or write pair exists.
- `index.md` task checkboxes are updated immediately after verified completion.
