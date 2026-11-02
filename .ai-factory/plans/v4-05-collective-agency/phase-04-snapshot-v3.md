# Phase 4: Organization Snapshot v3

Plan: [index.md](index.md)
Tasks: 13-14
Depends on: Phase 3 / Tasks 11-12

## Objective

Define canonical `organization-snapshot-v3` models and codec, keep v1/v2
decodable and byte-verifiable, add bounded collective-agency paging, and expose
the publication digest needed for correct cursor reuse.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/simulation/organization_models.py` | schema constants 63-69; caps 71-80; ID prefixes 82-95; provenance codes 98-108; operation enums 120-240; `OrganizationOperationRecord` 457-528; `OrganizationCandidateRecord` 531-632; `OrganizationWindowRecord` 634-679; `OrganizationObjectiveRow` 710-742; `OrganizationSnapshot` 769-804; `upgrade_organization_snapshot` | Exact v2 model pattern to extend additively |
| `src/simulation/organization_codec.py` | v1/v2 key sets 39-146; `_operation_to_value`/`_operation_from_value` 268-310; `_snapshot_to_value_v1/v2` 313-437; `encode_organization_snapshot` 440-449; decode dispatch | Exact-key-set codec pattern; v3 must be byte-round-trip stable |
| `src/simulation/organization_paging.py` | `select_organization_rows`, `OrganizationRowSelection`, `row_encoded_bytes`, `MAX_PAGE_BYTES_GUARD` | Paging never splits a row and enforces the byte guard |
| `src/simulation/organization_ports.py` | `ORGANIZATION_CURSOR_PURPOSES` 36-42; `OrganizationReadPort` 45-80; `OrganizationSummary` 108-136; `OrganizationCursor` 139-159; `organization_query_fingerprint` 177-194 | Where the new purpose, read method, and summary digest belong |
| `src/persistence/organization_filesystem.py` | `_StoredState` 96-101; `_load` 232-261; `summary` 263-287 | The store already has the digest; the summary must carry it to the route |
| `tests/unit/test_organization_operations_snapshot.py` | v2 canonical round trip 73-128; v1 decode 207-212 | Test pattern for v3 compatibility |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/simulation/organization_models.py` | modify | v3 schema constant, supported tuple, caps, published decision/implementation records, candidate/window/objective fields, upgrade path, provenance codes |
| `src/simulation/organization_codec.py` | modify | v3 key sets, record encode/decode, v3 snapshot encode/decode, exact-key validation |
| `src/simulation/organization_paging.py` | modify | Support published collective-decision rows in selection and byte accounting |
| `src/simulation/organization_ports.py` | modify | `organization_collective_agency` cursor purpose, `collective_agency` read method, summary digest and counts |
| `src/simulation/__init__.py` | modify | Export new models/constants |
| `tests/unit/test_organization_agency_snapshot.py` | create | v1/v2/v3 canonical tests |
| `tests/unit/test_organization_agency_paging.py` | create | Paging/byte guard tests |

## Task 13: Define snapshot v3 models and the canonical codec

### Intent

Publish bounded collective-agency records without changing v1/v2 decoding or
byte verification. New publications are v3; old publications remain readable.

### Implementation Steps

1. In `organization_models.py`:
   - Add `ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V2 = "organization-snapshot-v2"`.
   - Set `ORGANIZATION_SNAPSHOT_SCHEMA_VERSION = "organization-snapshot-v3"`.
   - Set `SUPPORTED_ORGANIZATION_SNAPSHOT_SCHEMAS = (v1, v2, v3)`.
   - Add caps: `MAX_CANDIDATE_COLLECTIVE_DECISIONS = 64`,
     `MAX_DECISION_IMPLEMENTATIONS = 32`,
     `MAX_SNAPSHOT_COLLECTIVE_DECISIONS = 4096`,
     `MAX_SNAPSHOT_COLLECTIVE_IMPLEMENTATIONS = 8192`.
   - Add prefixes `orgcpd-` and `orgcpi-` plus exact validators
     `require_collective_decision_publication_id` and
     `require_implementation_publication_id`.
2. Add `OrganizationCollectiveDecisionRecord`:
   `decision_id` (`orgcpd-`), `organization_id` (`org-`), `proposal_ref`,
   `revision`, `procedure_ref`, `recognition`, `authority_basis`,
   `support_count`, `oppose_count`, `abstain_count`, `contest_count`,
   `implementation_mode`, `effect`, `target_kind`, `target_ref`,
   `decided_tick`, `window_end_tick`, `implementation_status`,
   `provenance_code`, `resolved`, `implementations`.
3. Add `OrganizationImplementationRecord`:
   `implementation_id` (`orgcpi-`), `decision_id` (`orgcpd-`), `actor_ref`
   (16-hex, never a raw agent id), `status`, `effect`, `observed_tick`,
   `provenance_code`, `resolved`.
4. Validate:
   - `recognition` is a closed agency recognition token.
   - `authority_basis` reuses the existing operation authority tokens.
   - `implementation_mode`/`effect` agree (physical vs testimonial).
   - `target_kind` is one of `item`, `resource`, `artifact`, `structure`,
     `repository`, `collective_project`, `commitment`, `location`, `agent`,
     `none`, `unknown`.
   - `resolved is (target_kind != "unknown")`.
   - `decided_tick <= window_end_tick`.
   - `support/oppose/abstain/contest` are nonnegative and bounded.
   - Implementations are sorted by `(observed_tick, actor_ref,
     implementation_id)`; ids are unique; at most
     `MAX_DECISION_IMPLEMENTATIONS`.
   - A decision's `implementations` reference its own `decision_id`.
   - No owner-local `orgp-`/`orgcd-`/`orgci-`/`orgcev-` id or raw actor id is
     present.
5. Add `collective_decisions: tuple[OrganizationCollectiveDecisionRecord, ...]`
   to `OrganizationCandidateRecord`; validate cap, uniqueness, sort by
   `(decided_tick, decision_id)`, and total snapshot cap.
6. Add published candidate counts:
   `collective_proposal_count`, `collective_amendment_count`,
   `collective_support_count`, `collective_oppose_count`,
   `collective_abstain_count`, `collective_decision_count`,
   `collective_implementation_count`, `unimplemented_decision_count`,
   `contested_decision_count`. Validate nonnegative and consistent with the
   nested decisions where checkable.
7. Add to `OrganizationWindowRecord`: `collective_decision_count`,
   `collective_implementation_count`.
8. Add to `OrganizationObjectiveRow`: `collective_decision_count`,
   `collective_implementation_count`.
9. Keep candidate properties `collective_decision_count` and
   `collective_implementation_count` as computed views over the nested records;
   the stored counts must equal them. Reject a mismatch.
10. Add provenance codes:
    `collective_agency_truncated`, `collective_decision_unrecognized`,
    `collective_implementation_incomplete`, `collective_implementation_expired`,
    `collective_sabotage_attributed`.
11. Extend `upgrade_organization_snapshot`:
    - v1 → v2 → v3; v2 → v3 adds empty `collective_decisions`, zero counts.
    - v3 stays v3.
    - An unknown version fails closed.
12. In `organization_codec.py`:
    - `_SNAPSHOT_KEYS_V3 = _SNAPSHOT_KEYS_V2`.
    - `_CANDIDATE_KEYS_V3 = _CANDIDATE_KEYS_V2 | {"collective_decisions",
      "collective_proposal_count", "collective_amendment_count",
      "collective_support_count", "collective_oppose_count",
      "collective_abstain_count", "collective_decision_count",
      "collective_implementation_count", "unimplemented_decision_count",
      "contested_decision_count"}`.
    - `_WINDOW_KEYS_V3 = _WINDOW_KEYS_V2 | {"collective_decision_count",
      "collective_implementation_count"}`.
    - `_OBJECTIVE_KEYS_V3 = _OBJECTIVE_KEYS_V2 | {"collective_decision_count",
      "collective_implementation_count"}`.
    - `_COLLECTIVE_DECISION_KEYS`, `_COLLECTIVE_IMPLEMENTATION_KEYS`.
    - `_collective_decision_to_value`/`_from_value`,
      `_implementation_to_value`/`_from_value`.
    - `_snapshot_to_value_v3` calls v2 and appends the new fields.
    - `encode_organization_snapshot` dispatches v1/v2/v3.
    - `decode_organization_snapshot` accepts v1/v2/v3 and defaults missing
      fields to empty/zero for older versions.
    - `encode(decode(payload)) == payload` for all three versions.
13. Do not change any v1/v2 key set or their encoded bytes.

### Required Interfaces and Contracts

- New publications are `organization-snapshot-v3`.
- v1/v2 remain decodable and byte-verifiable.
- Published decision/implementation ids are `orgcpd-`/`orgcpi-`; owner-local
  ids never appear.
- Caps are hard; overflow raises `organization_size_limit` or trims with an
  explicit `collective_agency_truncated` notice at the publication boundary
  (Task 15), never silently.
- No analysis type is imported by simulation/persistence.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "Use accepted-set and exact-key-set schema
  evolution".
- V4-04 `organization-snapshot-v2` codec contract.
- Original Request: recognized decisions, implementation tracking, provenance.

### Error Handling and Logging

- Invalid records raise `OrganizationArtifactError` with a closed code:
  `organization_invalid_value`, `organization_size_limit`,
  `organization_duplicate_operation`, `organization_digest_mismatch`.
- Log INFO `organization_snapshot_encoded schema=%s decisions=%s implementations=%s`
  (counts only); never ids or actor sets.

### Tests

Create `tests/unit/test_organization_agency_snapshot.py`:
- v3 canonical byte round trip with decisions and implementations.
- v1 and v2 payloads decode to the same semantic snapshot as before; re-encode
  is byte-identical.
- v3 exact-key sets reject missing/extra keys.
- Unknown `v9` fails closed.
- A decision with a foreign/orphan implementation id fails.
- More than 64 decisions per candidate or 32 implementations per decision fails
  with `organization_size_limit`.
- A raw actor id or `orgp-`/`orgcd-`/`orgci-`/`orgcev-` token in a published
  record fails.
- `upgrade_organization_snapshot` v1/v2 → v3 preserves all earlier fields and
  adds empty agency records.
- `SUPPORTED_ORGANIZATION_SNAPSHOT_SCHEMAS == (v1, v2, v3)`.

Run:
`uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_snapshot.py tests/unit/test_organization_operations_snapshot.py tests/unit/test_organization_codec.py -q`

### Acceptance Criteria

- v3 is canonical, exact-key, bounded, and deterministic.
- v1/v2 remain readable and byte-identical.
- No owner-local id or raw actor id reaches a published record.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_snapshot.py -q`
- Expected: all tests pass.

## Task 14: Add collective-agency paging, read port, and cursor digest support

### Intent

Expose a bounded read surface for collective decisions and fix the publication
digest plumbing so every paged organization route can issue reusable cursors.

### Implementation Steps

1. In `organization_paging.py`:
   - Add `select_organization_collective_decision_rows(rows, offset, limit,
     max_bytes)` or extend `select_organization_rows` to accept
     `OrganizationCollectiveDecisionRecord`.
   - Ensure `row_encoded_bytes` encodes a decision and all nested
     implementations through the canonical codec/value encoder.
   - Never split a decision from its implementations; the byte guard counts the
     whole row.
2. In `organization_ports.py`:
   - Add `"organization_collective_agency"` to
     `ORGANIZATION_CURSOR_PURPOSES` (six entries).
   - Add `collective_agency(run_id, publication_id, offset, limit, recognition=None,
     organization_id=None) -> OrganizationRowSelection` to `OrganizationReadPort`.
   - Add `snapshot_digest: str` to `OrganizationSummary`; validate with
     `require_snapshot_digest`.
   - Add `collective_proposal_count`, `collective_amendment_count`,
     `collective_support_count`, `collective_oppose_count`,
     `collective_abstain_count`, `collective_decision_count`,
     `collective_implementation_count`, and `unimplemented_decision_count` to
     `OrganizationSummary` (default 0).
   - Keep `OrganizationCursor` unchanged; it already requires a 64-hex
     `snapshot_digest`.
3. Update all `OrganizationSummary` constructors in `src/` and tests to pass the
   digest and counts. The filesystem reader will supply the real digest in Task
   16; until then, tests may use a fixed 64-hex digest.
4. Add a pure helper `organization_cursor_matches(cursor, summary, purpose,
   fingerprint)` that checks run id, publication id, snapshot digest, and
   fingerprint; use it in Task 17. Keep the error code
   `organization_cursor_invalid`.
5. Export the new model/port symbols from `src/simulation/__init__.py`.

### Required Interfaces and Contracts

- Cursor purposes are exactly six; the new one is last.
- A cursor is valid only when its `snapshot_digest` equals the committed
  publication digest.
- Paging never returns a partial decision row; nested implementations are
  bounded by `MAX_DECISION_IMPLEMENTATIONS`.
- `OrganizationSummary.snapshot_digest` is content-addressed and never empty.
- No new API route is added in this task; Task 17 wires HTTP.

### Requirement Evidence

- `docs/research-api.md` organization cursor contract.
- `src/api/routes/organization.py` 245-256, 376-387, 461-472 (empty digest bug).
- V4-04 paging/port pattern.

### Error Handling and Logging

- Invalid digest/cursor raises `organization_cursor_invalid` or
  `organization_digest_mismatch`.
- Page offset/limit errors reuse `organization_page_offset`/
  `organization_page_limit`.
- Log DEBUG `organization_agency_page offset=%s limit=%s rows=%s bytes=%s`
  (counts only).

### Tests

Create `tests/unit/test_organization_agency_paging.py`:
- Page selection returns whole decisions including nested implementations.
- Offset/limit and byte guard behave like existing organization paging.
- A decision that would exceed the byte guard is not split.
- Six cursor purposes in exact order.
- A cursor with the real digest matches; an empty/mismatched digest fails with
  `organization_cursor_invalid`.
- `OrganizationSummary` rejects an empty/malformed digest.
- Existing candidate/lineage/operations paging tests still pass with the new
  summary field.

Run:
`uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_paging.py tests/unit/test_organization_paging.py tests/unit/test_organization_operations_paging.py tests/unit/test_organization_ports.py -q`

### Acceptance Criteria

- The read port can page collective decisions deterministically.
- Cursors bind to the publication digest.
- The cursor plumbing is ready for the Task 17 route fix.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_organization_agency_paging.py tests/unit/test_organization_ports.py -q`
- Expected: all tests pass.

## Phase Risks and Mitigations

- Risk: adding a v3 constant changes v2 publication behavior.
  Mitigation: v2 remains in the supported tuple and byte-round-trip tests prove
  it; only new publications use v3.
- Risk: nested implementations make a page row exceed the response budget.
  Mitigation: decisions are atomic rows; a single oversized decision fails with
  `organization_response_limit` rather than truncating silently.
- Risk: the cursor digest fix changes existing route behavior.
  Mitigation: it restores the documented behavior (valid reuse) and adds
  regression tests for reuse, changed filter, and expiry.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
