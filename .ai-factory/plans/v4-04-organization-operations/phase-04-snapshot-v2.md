# Phase 4: Organization Snapshot v2

Plan: [index.md](index.md)
Tasks: 13-14
Depends on: Phase 3 / Tasks 9-12

## Objective

Extend the published artifact from `organization-snapshot-v1` to
`organization-snapshot-v2` with bounded operation records, operation counts, and
operation paging, while keeping every v1 artifact decodable and byte-verifiable.
The snapshot remains canonical, immutable, analysis-independent, and under the
existing 4 MiB cap.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/simulation/organization_models.py` | constants 48-60; member/structural records 195-254; candidate 256-328; window 330-366; edge 368-394; objective row 396-427; coverage 429-451; snapshot 453-530 | V2 adds fields to candidate/window/objective records and one new operation record. |
| `src/simulation/organization_codec.py` | v1 key sets 36-112; `_snapshot_to_value` 234-328; encode 331-339; decode 341-469; digest 472-477; publication id 479-489 | V2 needs version dispatch, new exact key sets, and v1/v2 byte equality. |
| `src/simulation/organization_paging.py` | `OrganizationRowSelection` 21-35; `select_organization_rows` 58-96 | Operation pages reuse the same row/byte selection. |
| `src/simulation/organization_ports.py` | cursor purposes 36-41; read port 44-69; publication 78-95; summary 97-124; cursor 126-147; fingerprint 164-182 | Add one cursor purpose, one read method, and a summary count. |
| `src/persistence/organization_filesystem.py` | `_SNAPSHOT_SCHEMA` 43; publisher 100-220; reader 222-322 | The store must accept v1 and v2 and publish v2. |
| `src/experiments/organization_publication.py` | `_member_records` 80-105; `_candidate_record` 133-153; `_dissolved_record` 155-179; build 181-294; finalize 296-327; receipt 347-366 | The v2 composer is a later phase; this phase fixes the contract it targets. |
| `tests/unit/test_organization_snapshot_contract.py` | 100-130 and codec cases | Existing v1 exact-key/byte tests must keep passing. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/simulation/organization_models.py` | modify | v2 schema, supported set, operation record, candidate/window/objective additions, provenance codes, upgrade helper. |
| `src/simulation/organization_codec.py` | modify | v1/v2 key sets, dispatch, v1/v2 encode/decode, upgrade-aware publication id. |
| `src/simulation/organization_paging.py` | modify only if needed | Keep whole-row byte selection; no new algorithm. |
| `src/simulation/organization_ports.py` | modify | Cursor purpose, operations read method, summary count, supported-schema acceptance. |
| `src/simulation/__init__.py` | modify | Re-export v2 symbols and the upgrade helper. |
| `tests/unit/test_organization_operations_snapshot.py` | create | v2 exact keys, caps, v1 compatibility, determinism. |
| `tests/unit/test_organization_operations_paging.py` | create | Operation rows, byte caps, cursor filters. |

## Task 13: Define snapshot v2 models and the canonical codec

### Intent

Publish operation provenance as bounded, immutable records without exposing
owner-local `orgd-`/`orga-` ids or office ids. V1 publications remain readable.

### Implementation Steps

1. In `organization_models.py`:
   - set `ORGANIZATION_SNAPSHOT_SCHEMA_VERSION = "organization-snapshot-v2"`;
   - add `ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V1 = "organization-snapshot-v1"`;
   - add `SUPPORTED_ORGANIZATION_SNAPSHOT_SCHEMAS = (V1, V2)`;
   - add `MAX_CANDIDATE_OPERATIONS = 64` and `MAX_SNAPSHOT_OPERATIONS = 4096`;
   - extend `PROVENANCE_CODES` with `operations_truncated`,
     `operation_anchor_unresolved`, and `operation_expired`.
2. Add `OrganizationOperationRecord`:
   - `operation_id` (`orgop-` + 16 hex);
   - `domain` (one of the eight operation domains);
   - `act` (one of the ten acts);
   - `stance` (one of the five operational stance vocabularies; validate by act
     family);
   - `authority_basis` (one of seven);
   - `provenance_code` (one of nine);
   - `outcome` (one of five);
   - `command_kind` (a bounded token; `"none"` for non-action records);
   - `target_kind` (`member`, `office`, `anchor`, `none`);
   - `anchor_kind` (`item`, `resource`, `artifact`, `structure`, `repository`,
     `collective_project`, `commitment`, `owner_local`, `unknown`);
   - `anchor_id: str | None` (only for objective/known anchors; `None` for
     `owner_local`/`unknown`);
   - `tick`, `first_tick`, `last_tick`, `support_count`, `contest_count`,
     `resolved: bool`.
   Validate: `last_tick >= first_tick`; `tick` in `[first_tick, last_tick]`;
   `anchor_id` iff `anchor_kind` is objective; counts non-negative; `resolved` is
   `False` exactly for `unknown`. Do not publish a `target_id`; the candidate
   member list already carries visible member ids, and office/anchor targets are
   owner-local or objective anchors described by `anchor_kind`.
3. Extend `OrganizationCandidateRecord`:
   - `operations: tuple[OrganizationOperationRecord, ...] = ()`;
   - cap 64, unique `operation_id`, sorted by
     `(tick, domain, operation_id)`;
   - properties `operation_count` and `contested_operation_count` (any
     `stance == "disputed"` or `contest_count > 0`).
4. Extend `OrganizationWindowRecord` with `operation_count: int = 0` and
   `contested_operation_count: int = 0`.
5. Extend `OrganizationObjectiveRow` with `operation_action_count: int = 0`.
6. Extend `OrganizationSnapshot`:
   - `schema_version` accepts any supported version;
   - do **not** duplicate operations at the top level; the canonical operation
     rows live in each candidate's `operations` tuple, and the reader flattens
     them for paging;
   - validate that the sum of candidate operation counts is ≤
     `MAX_SNAPSHOT_OPERATIONS`, operation ids are globally unique, and every
     operation belongs to exactly one candidate;
   - keep the candidate/window/edge caps and coverage rules.
7. Add `upgrade_organization_snapshot(snapshot)`:
   - v2 → unchanged;
   - v1 → v2 with `operations=()`, candidate `operations=()`, window counts 0,
     objective `operation_action_count=0`;
   - never mutates the input.
8. In `organization_codec.py`:
   - rename the current key sets to `_SNAPSHOT_KEYS_V1`, `_WINDOW_KEYS_V1`,
     `_CANDIDATE_KEYS_V1`, `_OBJECTIVE_KEYS_V1`; keep `_MEMBER_KEYS`,
     `_STRUCTURAL_KEYS`, `_EDGE_KEYS`, `_COVERAGE_KEYS`;
   - add `_SNAPSHOT_KEYS_V2`, `_WINDOW_KEYS_V2`, `_CANDIDATE_KEYS_V2`,
     `_OBJECTIVE_KEYS_V2`, `_OPERATION_KEYS`;
   - `decode_organization_snapshot` parses JSON, reads `schema_version`, then
     validates the exact key set for that version and dispatches to
     `_decode_v1`/`_decode_v2`;
   - v1 decode produces a v1 object with empty operations; v1 re-encode must be
     byte-identical;
   - v2 decode produces a v2 object and re-encode must be byte-identical;
   - unknown/mixed schemas fail with `organization_invalid_value`;
   - `encode_organization_snapshot` dispatches on `snapshot.schema_version`;
   - `compute_organization_publication_id` encodes the normalized snapshot as
     given; the publication composer upgrades to v2 first.
9. Re-export the new constants/record/helper from `simulation/__init__.py`.

### Required Interfaces and Contracts

- V1 artifacts remain decodable and byte-verifiable; no v1 field is removed or
  renamed.
- V2 adds only optional/defaulted fields plus the new operation record; no
  analysis type is imported.
- `orgop-` is the only operation id published; `orgd-`, `orga-`, `orgc-`, owner
  ids, and office ids never appear.
- `command_kind` is a bounded command tag, not a command object or payload.
- Operations are sorted canonically; every operation belongs to exactly one
  candidate and the global count is bounded.
- The artifact remains ≤4 MiB and canonical compact JSON with one trailing
  newline.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "Use accepted-set and exact-key-set schema
  evolution": a new write version preserves legacy decoding.
- V4-03 `organization-snapshot-v1` contract.
- Original Request: "Record provenance of decisions and actions"; v2 publishes it
  without owner-local ids.

### Error Handling and Logging

- Caps raise `organization_size_limit`; malformed values raise
  `organization_invalid_value`; duplicate ids raise
  `organization_duplicate_candidate` or a new
  `organization_duplicate_operation` (add to the error code set).
- DEBUG: `organization_snapshot_v2_encoded candidates=%s operations=%s bytes=%s`.
  No ids or anchors.

### Tests

- `tests/unit/test_organization_operations_snapshot.py`:
  - v2 encode/decode is byte-identical and canonical;
  - v1 fixtures still decode and re-encode byte-identically;
  - `upgrade_organization_snapshot` lifts v1 with empty operations;
  - exact key sets reject extra/missing v2 fields;
  - 65 operations on one candidate and 4097 total fail;
  - duplicate operation ids fail;
  - owner/`orgd-`/`orga-`/office ids do not appear in encoded bytes;
  - publication id is stable for v2 and differs from the v1 id for the same
    content;
  - unknown schema fails closed.
- Command:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_snapshot.py tests/unit/test_organization_snapshot_contract.py tests/unit/test_organization_codec.py -q`

### Acceptance Criteria

- `organization-snapshot-v2` is canonical, bounded, immutable, and v1-compatible.
- Operation provenance is published without owner-local ids.
- No analysis import exists in models/codec.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_snapshot.py tests/unit/test_organization_snapshot_contract.py tests/unit/test_organization_codec.py -q`
- Expected: pass.

## Task 14: Add operation paging, read port, and cursor support

### Intent

Let the read-only surfaces page operations independently of candidates and
lineage, with purpose-bound cursors and the same byte budget.

### Implementation Steps

1. In `organization_ports.py`:
   - append `"organization_operations"` to `ORGANIZATION_CURSOR_PURPOSES`;
   - add `operations(run_id, publication_id, offset, limit, domain=None,
     organization_id=None) -> OrganizationRowSelection` to
     `OrganizationReadPort`;
   - add `operation_count: int = 0` to `OrganizationSummary`;
   - make `OrganizationSummary.schema_version` accept any supported schema;
   - keep `organization_query_fingerprint` filters generic; the operations route
     passes `{"domain": domain, "organization_id": organization_id}`.
2. `organization_paging.py`:
   - keep `select_organization_rows`; operation records are whole rows with
     `row_encoded_bytes` support;
   - if `row_encoded_bytes` has a closed type switch, add
     `OrganizationOperationRecord`; otherwise rely on dataclass serialization.
3. Add `require_known_organization` unchanged; operations are not candidates.
4. Re-export `OrganizationOperationRecord` and the new cursor purpose.

### Required Interfaces and Contracts

- The operations page returns `OrganizationOperationRecord` rows only.
- Filters are exact string matches; `domain=None` means all.
- A cursor is bound to purpose, run, publication, and the filter fingerprint; a
  changed filter, run, or publication yields `organization_cursor_invalid`.
- Expired cursors yield `organization_cursor_expired` (the API maps it to 410).
- The page respects the 500-row and 4 MiB response limits.

### Requirement Evidence

- V4-03 paging/cursor contract.
- `docs/research-api.md` cursor semantics.
- Original Request: provenance must be inspectable, not a write channel.

### Error Handling and Logging

- Unknown purpose/offset/fingerprint raises `organization_cursor_invalid`.
- A page that would exceed the response budget raises
  `organization_response_limit`.
- DEBUG: `organization_operations_page offset=%s limit=%s rows=%s`.

### Tests

- `tests/unit/test_organization_operations_paging.py`:
  - operation pages filter by domain and organization id;
  - cursor reuse with a changed filter fails;
  - expired cursor maps to the expired code;
  - 501 rows and byte-cap cases are bounded;
  - summary includes `operation_count`.
- Command:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_paging.py tests/unit/test_organization_paging.py tests/unit/test_organization_ports.py -q`

### Acceptance Criteria

- Operations page deterministically with purpose-bound cursors.
- No write method or new route is added in this phase.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_operations_paging.py tests/unit/test_organization_paging.py tests/unit/test_organization_ports.py -q`
- Expected: pass.

## Phase Risks and Mitigations

- Risk: v2 breaks v1 readers.
  Mitigation: version dispatch plus v1 byte-equality tests.
- Risk: operation rows are duplicated or exceed the artifact size.
  Mitigation: operations live only in candidate tuples; the snapshot validates a
  global cap and unique ids.
- Risk: owner-local ids leak into the artifact.
  Mitigation: the operation record has no `orgd-`/`orga-`/office field and the
  test scans encoded bytes.

## Phase Completion Checklist

- Every Task 13-14 acceptance criterion is met.
- V1 remains decodable; v2 is canonical and bounded.
- Operations page through a purpose-bound read port.
- `index.md` task checkboxes are updated immediately after verified completion.
