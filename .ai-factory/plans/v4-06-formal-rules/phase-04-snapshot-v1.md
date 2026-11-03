# Phase 4: Formal-Rule Snapshot v1

Plan: [index.md](index.md)
Tasks: 13-14
Depends on: Phase 3 / Task 12

## Objective

Define an independent, canonical, bounded `formal-rule-snapshot-v1` artifact and
its read/publication ports. Organization snapshots v1/v2/v3 must remain
untouched and byte-verifiable.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/simulation/organization_models.py` | snapshot versions 68-76; limits 78-91; prefixes 93-98; DTOs 452-1073; snapshot invariants 1087-1176 | Exact model/cap/validator pattern to mirror. |
| `src/simulation/organization_codec.py` | key sets 42-59; v1/v2/v3 serializers 465-641; decode dispatch 820-843; digest 886; publication id 893 | Exact-key-set codec and byte-equality contract. |
| `src/simulation/organization_paging.py` | selection 27; row bytes 55; selection 63; agency rows 105 | Bounded row selection pattern. |
| `src/simulation/organization_ports.py` | cursor purposes 36-43; read port 46; publication port 94; publication 101; summary 120; cursor 169; session 192; fingerprint 206; matches 226 | Port and cursor contract to mirror. |
| `src/api/organization_cursor.py` | signed cursor codec | Cursor signing/expiry is added in Phase 6, but the cursor struct belongs here. |
| `tests/unit/test_organization_agency_codec.py` | negative codec tests | Negative-test precedent. |
| `tests/architecture/test_organization_agency_boundaries.py` | snapshot pins 100-105 | Pin style. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/simulation/formal_rule_models.py` | create | Schema, ids, limits, DTOs, snapshot invariants. |
| `src/simulation/formal_rule_codec.py` | create | Canonical value codec, exact key sets, digest, publication id. |
| `src/simulation/formal_rule_paging.py` | create | Candidate/rule/version/lineage row selection. |
| `src/simulation/formal_rule_ports.py` | create | Cursor purposes, read/publication ports, cursor/fingerprint. |
| `src/simulation/__init__.py` | modify | Export the public snapshot, codec, paging, and port names. |
| `tests/unit/test_formal_rule_snapshot.py` | create | Models, limits, codec negatives, digest. |
| `tests/unit/test_formal_rule_paging.py` | create | Selection, bytes, offsets, truncation. |

## Task 13: Define snapshot models, limits, and the canonical codec

### Intent

Commit the exact published shape before composition and API work so no later
phase invents fields or changes the meaning of counts.

### Implementation Steps

1. Create `src/simulation/formal_rule_models.py` with:
   - `FORMAL_RULE_SNAPSHOT_SCHEMA = "formal-rule-snapshot-v1"`
   - `FORMAL_RULE_SNAPSHOT_POLICY_VERSION = "formal-rule-analysis.v1"`
   - `SUPPORTED_FORMAL_RULE_SNAPSHOT_SCHEMAS = ("formal-rule-snapshot-v1",)`
   - id prefixes/hex:
     `frule-` candidate, `frul-` published rule, `fruv-` published version,
     `frule-edge-` lineage edge, `frule-pub-` publication id; 16 hex chars.
   - `FormalRuleArtifactError(code)`.
   - limits: `MAX_FORMAL_RULE_SNAPSHOT_BYTES = 4 * 1024 * 1024`,
     `MAX_FORMAL_RULE_CANDIDATES = 2048`, `MAX_FORMAL_RULE_RULES = 4096`,
     `MAX_FORMAL_RULE_VERSIONS = 8192`, `MAX_FORMAL_RULE_WINDOWS = 512`,
     `MAX_FORMAL_RULE_OBJECTIVE_ROWS = 4096`,
     `MAX_FORMAL_RULE_RULES_PER_CANDIDATE = 64`,
     `MAX_FORMAL_RULE_VERSIONS_PER_RULE = 32`,
     `MAX_RESPONSE_BYTES = 2 * 1024 * 1024`,
     `MAX_PAGE_ROWS = 500`.
2. Define validators and minters:
   `require_formal_rule_candidate_id`, `require_formal_rule_rule_id`,
   `require_formal_rule_version_id`, `require_formal_rule_edge_id`,
   `require_formal_rule_publication_id`, `require_snapshot_digest`.
3. Define publication id derivation explicitly:
   - `frul-` = SHA-256 of candidate id + stage + constraint kind + action token
     + authority kind (sorted canonical fields), domain-separated by
     `formal-rule-public`;
   - `fruv-` = SHA-256 of published rule id + version number + version content
     digest, domain-separated by `formal-rule-public-version`;
   - neither derivation includes an owner id, owner-local id, scope anchor, or
     artifact id.
4. Define frozen DTOs:
   - `FormalRuleSnapshotRef(run_id, input_revision, generated_tick,
     publication_id)`; the digest is derived from the encoded bytes and is not
     stored inside the snapshot payload.
   - `FormalRuleCoverage(observed, expected, partial)`
   - `FormalRuleCandidateRecord(candidate_id, status, scope_kind, scope_digest,
     action_token, constraint_kinds, stage, authority_kinds, system_count,
     rule_count, version_count, competing_candidate_ids, first_tick, last_tick,
     coverage)`
   - `FormalRuleWrittenRepresentationRecord(status, artifact_present,
     artifact_revision, repository_present)`
   - `FormalRuleRecord(rule_id, candidate_id, stage, constraint_kind,
     scope_kind, action_token, authority_kind, recognition,
     written_representation, sanction_kinds, exception_count, version_count,
     latest_version, proponent_count, response_counts)`
   - `FormalRuleVersionRecord(version_id, rule_id, version_number, stage,
     constraint_kind, scope_kind, scope_digest, action_token, authority_kind,
     recognition, written_representation, sanction_kinds, exception_count, tick,
     revision_kind, supersedes_version_id)`
   - `FormalRuleObjectiveRow(tick, observed_artifact_count,
     observed_repository_count, observed_occurrence_count)`
   - `FormalRuleWindowRecord(start_tick, end_tick, owner_count,
     candidate_count)`
   - `FormalRuleLineageEdgeRecord(edge_id, source_candidate_id,
     target_candidate_id, kind, tick, jaccard, containment)`
   - `FormalRuleSnapshot(ref, candidates, rules, versions, lineage,
     objective_rows, windows, coverage, counts, provenance_code)` where
     `provenance_code` is one of `ok`, `partial`, `truncated`, `empty`.
5. `FormalRuleSnapshot.__post_init__` enforces:
   - schema/policy exact;
   - candidates/rules/versions sorted by id and unique;
   - every rule candidate exists; every version rule exists;
   - competing candidate ids exist and are symmetric;
   - lineage endpoints exist, edges forward in tick order, no cycles;
   - global caps and per-candidate/per-rule caps;
   - floats quantized to six decimals; no NaN/Inf;
   - no owner-local id (`frs-`/`frl-`/`frv-`/`fre-`/`frp-`/`frr-`/`frx-`)
     appears in a published record;
   - no `org-`, `msoc-`, `orgc-`, `orgd-`, `orga-`, `orgp-` id appears.
6. Add `empty_formal_rule_snapshot(ref, *, coverage)` returning an empty but
   valid snapshot.
7. Create `src/simulation/formal_rule_codec.py`:
   - exact top-level key set:
     `schema_version`, `policy_version`, `run_id`, `input_revision`,
     `generated_tick`, `publication_id`, `candidates`, `rules`, `versions`,
     `lineage`, `objective_rows`, `windows`, `coverage`, `counts`,
     `provenance_code`. The digest is not a payload field; it is computed from
     the encoded bytes so encoding stays non-circular.
   - exact candidate key set, rule key set, version key set,
     written-representation key set (`status`, `artifact_present`,
     `artifact_revision`, `repository_present`), objective row key set, window
     key set, edge key set,
     coverage key set, counts key set. Each decoder rejects missing and extra
     keys with `formal_rule_invalid_value`.
   - `validate_formal_rule_value`, `encode_formal_rule_value`,
     `decode_formal_rule_value`, `_reject_duplicate_keys`.
   - `encode_formal_rule_snapshot`, `decode_formal_rule_snapshot`; decode must
     re-encode and compare bytes exactly, raising
     `formal_rule_digest_mismatch` on any difference.
   - `formal_rule_digest(payload)` returning SHA-256 over the encoded bytes, and
     `compute_formal_rule_publication_id(snapshot)` returning
     `frule-pub-<16hex>` from SHA-256 over run id + NUL + the canonical encoding
     with `publication_id=""` (non-circular, mirroring the organization codec).
8. Do not import organization models/codecs. Formal-rule snapshots are
   independent; only the patterns are shared.
9. Do not modify `organization_models.py`, `organization_codec.py`, or any
   organization snapshot version.

### Required Interfaces and Contracts

```python
def encode_formal_rule_snapshot(snapshot: FormalRuleSnapshot) -> bytes: ...
def decode_formal_rule_snapshot(payload: bytes) -> FormalRuleSnapshot: ...
def formal_rule_digest(payload: bytes) -> str: ...
def compute_formal_rule_publication_id(snapshot: FormalRuleSnapshot) -> str: ...
def empty_formal_rule_snapshot(ref: FormalRuleSnapshotRef, *, coverage: FormalRuleCoverage) -> FormalRuleSnapshot: ...
```

Pinned top-level value shape:

```json
{
  "schema_version": "formal-rule-snapshot-v1",
  "policy_version": "formal-rule-analysis.v1",
  "run_id": "...",
  "input_revision": "...",
  "generated_tick": 0,
  "publication_id": "frule-pub-<16hex>",
  "candidates": [],
  "rules": [],
  "versions": [],
  "lineage": [],
  "objective_rows": [],
  "windows": [],
  "coverage": {"observed": 0, "expected": 0, "partial": false},
  "counts": {"candidates": 0, "rules": 0, "versions": 0, "objective_rows": 0, "windows": 0},
  "provenance_code": "empty"
}
```

Compatibility invariants:

- A decoded snapshot is byte-identical to its source encoding.
- Unknown keys, duplicate keys, owner-local ids, and cross-context ids fail
  closed.
- Organization snapshots remain decodable through their own codec with no
  behavioral change.
- `frule-pub-` is content-addressed; identical payloads produce identical ids.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "Use accepted-set and exact-key-set schema
  evolution".
- `organization_models.py` 68-91, 452-1176.
- `organization_codec.py` 42-59, 820-893.

### Error Handling and Logging

- Bad type/enum/float: `formal_rule_invalid_value`.
- Missing/extra key: `formal_rule_invalid_value` with the key name only.
- Digests mismatch: `formal_rule_digest_mismatch`.
- Oversize snapshot: `formal_rule_size_limit`.
- INFO on encode: `formal_rule_snapshot_encoded candidates=%s rules=%s
  versions=%s` (counts only).
- Never log payloads, ids, scope digests, action tokens, or owner ids.

### Tests

`tests/unit/test_formal_rule_snapshot.py`:

- `test_empty_snapshot_is_canonical_and_round_trips`
- `test_exact_top_level_keys_reject_missing_and_extra`
- `test_candidate_rule_version_window_edge_and_coverage_keys_are_exact`
- `test_duplicate_json_keys_are_rejected`
- `test_owner_local_and_cross_context_ids_are_rejected`
- `test_candidate_and_rule_caps_are_enforced`
- `test_competing_candidate_links_are_symmetric`
- `test_digest_and_publication_id_are_content_addressed`
- `test_organization_snapshot_v1_v2_v3_remain_byte_verifiable`

Run: `uv run pytest tests/unit/test_formal_rule_snapshot.py -q`.

### Acceptance Criteria

- The snapshot shape is exact and canonical.
- No owner-local or cross-context id can be published.
- Organization snapshot tests remain green.

### Verification

- `uv run pytest tests/unit/test_formal_rule_snapshot.py -q`
- `uv run pytest tests/unit/test_organization_agency_codec.py tests/unit/test_organization_operations_codec.py -q`
  (adjust to actual organization codec tests; keep them green)
- `uv run mypy src/simulation/formal_rule_models.py src/simulation/formal_rule_codec.py`

## Task 14: Add paging, read ports, and cursor digest support

### Intent

Provide deterministic, bounded selection for candidates, rules, versions, and
lineage, and a cursor contract that binds run, publication, digest, filter, and
offset before the API layer signs it.

### Implementation Steps

1. Create `src/simulation/formal_rule_paging.py`:
   - `FormalRuleRowSelection(rows, next_offset, truncated, encoded_bytes)`.
   - `row_encoded_bytes(row)` using canonical JSON plus newline.
   - `select_formal_rule_candidate_rows(rows, *, offset, limit, byte_budget)`.
   - `select_formal_rule_rows(rows, *, candidate_id, offset, limit,
     byte_budget)`.
   - `select_formal_rule_version_rows(rows, *, candidate_id, offset, limit,
     byte_budget)`.
   - `select_formal_rule_lineage_rows(rows, *, offset, limit, byte_budget)`.
   - Reject negative offset/limit with `formal_rule_page_offset` /
     `formal_rule_page_limit`; reject a single row over budget and any result
     over `MAX_RESPONSE_BYTES` with `formal_rule_size_limit`.
   - Only whole rows; never slice a row.
2. Create `src/simulation/formal_rule_ports.py`:
   - `FORMAL_RULE_CURSOR_PURPOSES = ("summary", "candidates", "candidate",
     "rules", "versions", "lineage")`.
   - `FormalRuleReadPort` Protocol with exactly six methods: `summary`,
     `candidates`, `candidate`, `rules`, `versions`, `lineage`.
   - `FormalRulePublicationPort` Protocol with `publish`.
   - `FormalRulePublication(run_id, publication_id, snapshot_digest, payload,
     generated_tick)`.
   - `FormalRuleSummary` with counts and coverage.
   - `FormalRuleCursor(purpose, run_id, publication_id, snapshot_digest, offset,
     query_fingerprint)`; fingerprint is 64 hex chars.
   - `FormalRuleReadSession` with a response byte budget.
   - `formal_rule_query_fingerprint(purpose, *, run_id, publication_id,
     candidate_id, filters)` using sorted canonical JSON.
   - `formal_rule_cursor_matches(cursor, *, purpose, run_id, publication_id,
     snapshot_digest, fingerprint)`.
   - `require_known_formal_rule(...)` raising
     `formal_rule_unknown`.
3. Cursor binding rules:
   - summary/candidates/lineage bind run/publication/digest/offset/fingerprint;
   - candidate/rules/versions also bind `candidate_id` in the fingerprint;
   - filters (stage/status/constraint/authority) are sorted and included;
   - a digest change invalidates every page.
4. Do not import `api`, `analysis`, `experiments`, `persistence`, or
   `infrastructure`.
5. Add tests:
   - `test_selection_is_whole_row_and_bounded`
   - `test_offset_limit_and_byte_budget_errors`
   - `test_candidate_rules_versions_and_lineage_filters`
   - `test_cursor_fingerprint_changes_with_any_bound_field`
   - `test_cursor_match_rejects_changed_run_publication_digest_or_filter`
   - `test_six_cursor_purposes_are_closed`
   - `test_no_analysis_or_api_import`

### Required Interfaces and Contracts

```python
FORMAL_RULE_CURSOR_PURPOSES: Final[tuple[str, ...]] = (
    "summary", "candidates", "candidate", "rules", "versions", "lineage",
)

class FormalRuleReadPort(Protocol):
    def summary(self, run_id: str) -> FormalRuleSummary: ...
    def candidates(self, run_id: str, *, status: str | None, offset: int, limit: int) -> FormalRuleRowSelection: ...
    def candidate(self, run_id: str, candidate_id: str) -> FormalRuleCandidateRecord: ...
    def rules(self, run_id: str, *, candidate_id: str, stage: str | None, offset: int, limit: int) -> FormalRuleRowSelection: ...
    def versions(self, run_id: str, *, candidate_id: str, rule_id: str | None, offset: int, limit: int) -> FormalRuleRowSelection: ...
    def lineage(self, run_id: str, *, kind: str | None, offset: int, limit: int) -> FormalRuleRowSelection: ...
```

Compatibility invariants:

- Six purposes, six methods, no extra page kind.
- A cursor never authorizes a different publication or digest.
- Paging never mutates a snapshot.
- The API layer signs/encrypts cursors; simulation owns only the payload.

### Requirement Evidence

- `organization_paging.py` 23-105.
- `organization_ports.py` 36-247.
- `docs/research-api.md` line 30 (route/cursor precedent).

### Error Handling and Logging

- Bad offset/limit: `formal_rule_page_offset` / `formal_rule_page_limit`.
- Oversize: `formal_rule_size_limit`.
- Unknown candidate/rule: `formal_rule_unknown`.
- Cursor mismatch: `formal_rule_cursor_invalid` (API maps to 400).
- INFO: `formal_rule_page purpose=%s rows=%s truncated=%s` (counts only).
- Never log row content, ids, or fingerprints.

### Tests

`tests/unit/test_formal_rule_paging.py`:

- as listed in step 5.

Run: `uv run pytest tests/unit/test_formal_rule_paging.py -q`.

### Acceptance Criteria

- Every page is deterministic and byte-bounded.
- Cursor matching fails on any changed binding.
- No API or analysis type is imported by simulation ports.

### Verification

- `uv run pytest tests/unit/test_formal_rule_paging.py -q`
- `uv run lint-imports`
- Expected: 25 contracts kept, 0 broken.

## Phase Risks and Mitigations

- Risk: the new snapshot accidentally reuses organization key names and breaks
  organization decoding.
  Mitigation: separate modules, separate schema string, separate tests, and no
  edits to organization files.
- Risk: a published record contains an owner-local id.
  Mitigation: `FormalRuleSnapshot.__post_init__` rejects every owner-local
  prefix and the codec negative tests cover it.
- Risk: cursor binding omits the digest.
  Mitigation: `formal_rule_cursor_matches` requires all six fields and tests
  mutate one field at a time.
- Risk: paging slices a row and produces invalid JSON.
  Mitigation: select whole rows only; reject a single oversized row.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
- Organization snapshot v1/v2/v3 remain byte-verifiable.
- No analysis/API/persistence import enters simulation.
