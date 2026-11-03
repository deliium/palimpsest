# Phase 4: Dispute-Resolution Snapshot v1

Plan: [index.md](index.md)
Tasks: 14-15
Depends on: Phase 3 / Tasks 10-13

## Objective

Define the bounded canonical `dispute-resolution-snapshot-v1` artifact, its
strict codec, paging, read ports, and publication/cursor contracts. The snapshot
is independent of organization and formal-rule snapshots.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/simulation/formal_rule_models.py` | schema 16-26; limits 28-37; snapshot records 247-718 | Snapshot model/limit/validation pattern. |
| `src/simulation/formal_rule_codec.py` | `validate_formal_rule_value`, `encode_formal_rule_value`, `decode_formal_rule_value`, digest/publication id | Canonical JSON pattern. |
| `src/simulation/formal_rule_paging.py` | row selection, byte budget, `MAX_PAGE_ROWS` | Whole-row paging pattern. |
| `src/simulation/formal_rule_ports.py` | six cursor purposes 37-46; publication/summary/cursor/read session 48-160; protocols 116-165; fingerprint/match 166-232 | Port and cursor pattern. |
| `src/simulation/organization_models.py` | organization snapshot v1/v2/v3 compatibility | Independent snapshot versioning precedent. |
| `src/simulation/organization_codec.py` | canonical encoding and byte verification | Must remain unchanged. |
| `src/api/formal_rule_cursor.py` | HMAC cursor 26-135 | Cursor codec to mirror. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/simulation/dispute_models.py` | create | Snapshot schema, limits, records, validation, ids. |
| `src/simulation/dispute_codec.py` | create | Canonical JSON codec, digest, publication id. |
| `src/simulation/dispute_paging.py` | create | Candidate/claim/resolution/lineage row selection. |
| `src/simulation/dispute_ports.py` | create | Publication, summary, cursor, read session, protocols, fingerprint. |
| `tests/unit/test_dispute_snapshot.py` | create | Models, limits, codec, byte verification. |
| `tests/unit/test_dispute_ports.py` | create | Paging, cursor binding, read session. |

## Task 14: Define dispute-resolution-snapshot-v1 and its codec

### Intent

Freeze a bounded, immutable, canonical artifact that researchers can read
without exposing owner-local ids or implying a verdict.

### Implementation Steps

1. Create `src/simulation/dispute_models.py`:
   - `DISPUTE_SNAPSHOT_SCHEMA = "dispute-resolution-snapshot-v1"`;
   - `DISPUTE_SNAPSHOT_POLICY_VERSION = "dispute-analysis.v1"`;
   - `SUPPORTED_DISPUTE_SNAPSHOT_SCHEMAS = (DISPUTE_SNAPSHOT_SCHEMA,)`;
   - id prefixes `disp-`, `dispcl-`, `dispres-`, `disp-edge-`, `disp-pub-`;
   - bounds `MAX_DISPUTE_SNAPSHOT_BYTES = 4 MiB`,
     `MAX_DISPUTE_CANDIDATES = 2048`, `MAX_DISPUTE_CASES = 4096`,
     `MAX_DISPUTE_CLAIMS = 8192`, `MAX_DISPUTE_TESTIMONY = 8192`,
     `MAX_DISPUTE_EVIDENCE = 16384`, `MAX_DISPUTE_RESOLUTIONS = 4096`,
     `MAX_DISPUTE_RESPONSES = 16384`, `MAX_DISPUTE_WINDOWS = 512`,
     `MAX_DISPUTE_OBJECTIVE_ROWS = 4096`,
     `MAX_DISPUTE_CLAIMS_PER_CANDIDATE = 64`,
     `MAX_DISPUTE_RESOLUTIONS_PER_CANDIDATE = 32`,
     `MAX_RESPONSE_BYTES = 2 MiB`, `MAX_PAGE_ROWS = 500`.
2. Define frozen slotted records:
   - `DisputeSnapshotRef(run_id, input_revision, generated_tick, publication_id,
     snapshot_digest, policy_version)`.
   - `DisputeCoverage(observed, expected, ratio, note)`.
   - `DisputeCaseRecord(case_ref, kind, subject_kind, subject_token, status,
     party_ids, first_tick, last_tick, coverage)` — `case_ref` is the portable
     thread digest over `(subject_token, party_set_digest)`, not an owner-local
     `dsc-` id.
   - `DisputeClaimRecord(claim_id, case_ref, claimant_id, respondent_id, role,
     claim_kind, polarity, subject_token, counters_claim_ref, evidence_count,
     first_tick, last_tick)` — `claim_id` is `dispcl-`.
   - `DisputeTestimonyRecord(testimony_id, case_ref, claim_id, speaker_id,
     channel, root_token, independently_evidenced, tick)`.
   - `DisputeEvidenceRecord(evidence_id, case_ref, claim_id, channel,
     reference_kind, reference_token, tick, independently_evidenced)` — reference
     token is an opaque digest, never a raw event/memory/artifact id.
   - `DisputeRuleReferenceRecord(rule_reference_id, case_ref, claim_ref,
     system_token, rule_token, version_number, applicability, interpretation,
     status)`.
   - `DisputeAuthorityReferenceRecord(authority_reference_id, case_ref,
     authority_kind, reference_token, strength, uncertainty, dissenting)`.
   - `DisputeMediationReferenceRecord(mediation_reference_id, case_ref,
     mediation_case_token, recommendation_token, response_token, outcome_token,
     link_status)`.
   - `DisputeResolutionRecord(resolution_id, resolution_ref, case_ref,
     proposer_id, source, terms_digest, status, first_tick, last_tick,
     expires_tick, accepted_party_count, rejected_party_count)` —
     `resolution_id` is `dispres-`.
   - `DisputeResolutionResponseRecord(response_id, resolution_ref, party_id,
     kind, tick, terms_digest, active)`.
   - `DisputeCandidateRecord(candidate_id, kind, subject_token, party_count,
     owner_count, case_count, claim_count, counterclaim_count,
     testimony_count, evidence_count, resolution_count, disagreement_count,
     status, first_tick, last_tick, coverage)`.
   - `DisputeObjectiveRow(tick, observed_occurrence_count,
     observed_transfer_count, observed_harm_count, observed_commitment_count,
     observed_record_count, observed_communication_count)`.
   - `DisputeWindowRecord(start_tick, end_tick, owner_count, candidate_count,
     claim_count)`.
   - `DisputeLineageEdgeRecord(edge_id, source, target, kind, tick)`.
   - `DisputeCounts(candidate_count, case_count, claim_count,
     counterclaim_count, testimony_count, evidence_count, resolution_count,
     accepted_count, rejected_count, owner_count)`.
   - `DisputeSnapshot(ref, coverage, candidates, cases, claims, testimony,
     evidence, rule_references, authority_references, mediation_references,
     resolutions, responses, objective_rows, windows, lineage, counts)`.
3. Validate every enum, id prefix, count, ratio, tick, and reference. Reject:
   - published owner-local ids (`dsc-`, `dcl-`, `dts-`, `dev-`, `drf-`, `dmr-`,
     `dar-`, `drs-`, `drp-`);
   - `verdict`, `judgment`, `guilty`, `liable`, `true_owner`, `winner`,
     `binding`, `enforced_by_world`, `global_dispute_registry`;
   - duplicate ids;
   - cycles in lineage;
   - counts that do not match `len(records)` for every family (candidates,
     cases, claims, testimony, evidence, resolutions, responses, edges);
   - any family exceeding its `MAX_DISPUTE_*` bound.
4. Add `empty_dispute_snapshot(...)` for absent runs and
   `derive_dispute_claim_id` / `derive_dispute_resolution_id` content-addressed
   publication ids.
5. Create `src/simulation/dispute_codec.py`:
   - `validate_dispute_value`, `encode_dispute_value`, `decode_dispute_value`;
   - canonical JSON with `sort_keys=True`, `separators=(",", ":")`,
     `ensure_ascii=False`, `allow_nan=False`;
   - duplicate JSON keys fail closed; non-finite floats fail closed; exact key
     sets are required;
   - `encode_dispute_snapshot`, `decode_dispute_snapshot`,
     `dispute_snapshot_digest`, `compute_dispute_publication_id`.
6. The codec must be byte-stable across dictionary insertion orders and must
   reject a payload whose digest does not match the ref.
7. Organization v1/v2/v3 and `formal-rule-snapshot-v1` codecs are untouched.

### Required Interfaces and Contracts

```python
DISPUTE_SNAPSHOT_SCHEMA: Final[str] = "dispute-resolution-snapshot-v1"

def encode_dispute_snapshot(snapshot: DisputeSnapshot) -> bytes: ...
def decode_dispute_snapshot(payload: bytes) -> DisputeSnapshot: ...
def dispute_snapshot_digest(payload: bytes) -> str: ...
def compute_dispute_publication_id(snapshot: DisputeSnapshot) -> str: ...
```

Compatibility invariants:

- `dispute-resolution-snapshot-v1` is independent; no organization or formal-rule
  schema is widened.
- Published tokens are not owner-local ids.
- No record carries a verdict, guilt, liability, or binding settlement.
- A snapshot is immutable after publication.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "Use accepted-set and exact-key-set schema
  evolution" and "A new snapshot, not an organization v4."
- `src/simulation/formal_rule_models.py` 16-37, 247-718.
- `src/simulation/formal_rule_codec.py`.
- `src/simulation/organization_codec.py` (unmodified compatibility).

### Error Handling and Logging

- Invalid value: `DisputeArtifactError("dispute_invalid_value")`.
- Oversize: `DisputeArtifactError("dispute_size_limit")`.
- Foreign id: `DisputeArtifactError("dispute_owner_local_id")`.
- Digest mismatch: `DisputeArtifactError("dispute_digest_mismatch")`.
- INFO: `dispute_snapshot_encoded candidates=%s bytes=%s`; never log content.

### Tests

`tests/unit/test_dispute_snapshot.py`:

- `test_snapshot_round_trip_is_byte_stable`
- `test_snapshot_rejects_owner_local_ids`
- `test_snapshot_rejects_verdict_and_binding_fields`
- `test_limits_are_enforced`
- `test_each_record_family_bound_is_enforced`
- `test_counts_must_match_record_families`
- `test_duplicate_json_keys_and_nonfinite_values_fail`
- `test_digest_and_publication_id_are_content_addressed`
- `test_organization_and_formal_rule_snapshots_remain_decodable`

Run: `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_snapshot.py -q`.

### Acceptance Criteria

- Snapshot models and codec are canonical and bounded.
- No owner-local id or verdict field can appear.
- Organization/formal-rule snapshots remain byte-verifiable.
- Duplicate keys and non-finite values fail closed.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_snapshot.py -q`
- Expected result: all tests pass.

## Task 15: Add paging, read ports, and cursor support

### Intent

Give the API and filesystem store a typed, bounded read contract with signed
cursor semantics identical to the established V4 contexts.

### Implementation Steps

1. Create `src/simulation/dispute_paging.py`:
   - `DisputeRowSelection(items, truncated, next_offset, encoded_bytes)`.
   - `row_encoded_bytes(row)` canonical size.
   - `_select(rows, *, offset, limit, max_bytes)` whole-row selection; never
     split a row.
   - `select_dispute_candidate_rows`, `select_dispute_claim_rows`,
     `select_dispute_resolution_rows`, `select_dispute_lineage_rows`.
   - Cap `limit` at `MAX_PAGE_ROWS`; cap bytes at `MAX_RESPONSE_BYTES`; explicit
     `truncated`.
2. Create `src/simulation/dispute_ports.py` mirroring
   `src/simulation/formal_rule_ports.py`:
   - `DISPUTE_CURSOR_PURPOSES = ("summary", "candidates", "candidate", "claims",
     "resolutions", "lineage")`.
   - `DisputePublication(run_id, publication_id, snapshot_digest, payload:
     bytes, generated_tick)`.
   - `DisputeSummary(run_id, publication_id, snapshot_digest, generated_tick,
     candidate_count, case_count, claim_count, counterclaim_count,
     testimony_count, evidence_count, resolution_count, accepted_count,
     rejected_count, edge_count, coverage, schema_version=
     "dispute-resolution-snapshot-v1", window_count=0,
     provenance_code="ok")`. The analysis-side summary is
     `DisputeAnalysisSummary`; do not overload that name here.
   - `DisputeCursor(purpose, run_id, publication_id, snapshot_digest, offset,
     query_fingerprint)`; expiry is added only by the API cursor codec.
   - `DisputeReadPort(Protocol)` methods:
     `summary(run_id)`, `candidates(run_id, *, status, offset, limit)`,
     `candidate(run_id, candidate_id)`,
     `claims(run_id, *, candidate_id, role, offset, limit)`,
     `resolutions(run_id, *, candidate_id, status, offset, limit)`, and
     `lineage(run_id, *, kind, offset, limit)`.
   - `DisputePublicationPort(Protocol).publish(publication) -> str`.
   - `dispute_query_fingerprint(purpose, run_id, publication_id, filters)` and
     `dispute_cursor_matches(cursor, ...)`.
   - `require_known_dispute_candidate(value, field_name)`.
   Do not introduce a `DisputeReadSession`; the established V4 ports are
   run-id/filter/offset based, and cursor packaging belongs to the API.
3. Cursor binding in the port: purpose, run, publication, digest, offset, and
   filter fingerprint. Expiry is enforced by `api/dispute_cursor.py` and maps to
   410. A cursor from another purpose or publication is invalid.
4. Paging must be deterministic for the same snapshot and filter; a changed
   filter produces a different fingerprint and therefore a 400 at the API.
5. The read port never exposes owner-local ids or raw evidence references.

### Required Interfaces and Contracts

```python
DISPUTE_CURSOR_PURPOSES: Final[tuple[str, ...]] = (
    "summary", "candidates", "candidate", "claims", "resolutions", "lineage"
)

class DisputeReadPort(Protocol):
    def summary(self, run_id: str) -> DisputeSummary: ...
    def candidates(self, run_id: str, *, status: str | None, offset: int, limit: int) -> DisputeRowSelection: ...
    def candidate(self, run_id: str, candidate_id: str) -> DisputeCandidateRecord: ...
    def claims(self, run_id: str, *, candidate_id: str, role: str | None, offset: int, limit: int) -> DisputeRowSelection: ...
    def resolutions(self, run_id: str, *, candidate_id: str, status: str | None, offset: int, limit: int) -> DisputeRowSelection: ...
    def lineage(self, run_id: str, *, kind: str | None, offset: int, limit: int) -> DisputeRowSelection: ...

class DisputePublicationPort(Protocol):
    def publish(self, publication: DisputePublication) -> str: ...
```

Compatibility invariants:

- Six purposes, no more and no fewer.
- Whole-row paging only.
- Cursors bind to the publication digest and query fingerprint.
- The read port is read-only; no write method exists.

### Requirement Evidence

- `src/simulation/formal_rule_ports.py` 37-232.
- `src/simulation/formal_rule_paging.py`.
- `.ai-factory/ARCHITECTURE.md` "Cursors bind to the publication digest" and
  "read and publication ports are separate."

### Error Handling and Logging

- Unknown purpose: `DisputePortError("dispute_cursor_purpose")`.
- Invalid cursor: `DisputePortError("dispute_cursor_invalid")`.
- Missing run/publication: `DisputePortError("dispute_not_found")`; the API maps
  it to `404`.
- Overflow: return `truncated=True` with a bounded next offset.
- DEBUG: `dispute_page purpose=%s rows=%s truncated=%s`.

### Tests

`tests/unit/test_dispute_ports.py`:

- `test_six_cursor_purposes_are_exact`
- `test_paging_is_deterministic_and_whole_row`
- `test_cursor_binds_run_publication_digest_filter_and_offset`
- `test_changed_filter_invalidates_cursor`
- `test_read_port_has_no_write_method`
- `test_port_is_run_id_filter_offset_based_without_session`
- `test_unknown_candidate_fails_closed`

Run: `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_ports.py -q`.

### Acceptance Criteria

- Exactly six cursor purposes exist.
- Paging is deterministic, bounded, and whole-row.
- Cursor binding covers run, publication, digest, filter, and offset.
- The read port is read-only.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_dispute_ports.py -q`
- Expected result: all tests pass.

## Phase Risks and Mitigations

- Risk: A snapshot field leaks an owner-local id or raw evidence.
  Mitigation: Task 14 `_reject_published_owner_ids` and tests.
- Risk: A snapshot version silently widens organization or formal-rule schemas.
  Mitigation: Task 14 compatibility tests; Phase 7 pins.
- Risk: Cursor reuse serves a stale page.
  Mitigation: Task 15 digest/filter binding and Task 18 API tests.
- Risk: Paging splits a row and changes bytes.
  Mitigation: Task 15 whole-row selection test.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
