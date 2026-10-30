# Phase 4: Organization Snapshot Contract

Plan: [index.md](index.md)
Tasks: 12-13
Depends on: Phase 3 / Tasks 10-11

## Objective

Define the bounded, canonical, immutable `organization-snapshot-v1` document and
the read/publication ports that later composition, persistence, API, and CLI
layers implement. The artifact is independent of analysis types: `simulation`
owns the schema and never imports `analysis`.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/simulation/macro_society_models.py` | caps 40-45; `MacroSocietySnapshot` 310-400; `MacroSocietySnapshotRef` 291-307; id validators 61-93 | Exact precedent for a bounded analytical snapshot and identity grammar. |
| `src/simulation/macro_society_codec.py` | canonical encode 104-110; strict decode 276-361; exact keys 33-78 | Canonical JSON, duplicate-key rejection, exact-key sets, byte-equality check. |
| `src/simulation/macro_society_paging.py` | `MAX_PAGE_ROWS = 500`; `select_macro_society_rows` | Byte-bounded deterministic selection. |
| `src/simulation/macro_society_ports.py` | read/publication protocols 185-190; `MacroSocietyCursor` 56-101; `macro_society_query_fingerprint` 86-101 | Port separation and purpose-bound cursor DTO. |
| `src/api/macro_society_cursor.py` | HMAC codec 40-131; TTL 900s | Cursor signing precedent (implemented in Phase 6). |
| `tests/unit/test_macro_society_codec.py` | round trip, strict keys, oversize, digest | Test pattern. |
| `tests/unit/test_macro_society_contract.py` | id shape, reproducibility, evidence sensitivity | Test pattern. |
| `tests/unit/test_macro_society_end_to_end.py` | harvest -> publish -> read | Test pattern. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/simulation/organization_models.py` | create | Caps, schema version, DTOs, error, id validators. |
| `src/simulation/organization_codec.py` | create | Canonical encode/decode, exact-key validation, digest, publication id. |
| `src/simulation/organization_paging.py` | create | Byte/count-bounded deterministic row selection. |
| `src/simulation/organization_ports.py` | create | Read/publication protocols, publication DTO, cursor, summary, fingerprint. |
| `src/simulation/__init__.py` | modify | Export the snapshot DTOs, codec functions, paging selection, and read/publication ports. |
| `tests/unit/test_organization_codec.py` | create | Codec strictness and caps. |
| `tests/unit/test_organization_snapshot_contract.py` | create | DTO invariants and id grammar. |
| `tests/unit/test_organization_paging.py` | create | Bounded selection. |
| `tests/unit/test_organization_ports.py` | create | Cursor/fingerprint and protocol shape. |

## Task 12: Define snapshot models and the canonical codec

### Intent

Freeze the immutable artifact that all outer layers exchange. Its bytes are the
authority; its identities are content-addressed; its arrays are bounded; its keys
are exact.

### Implementation Steps

1. Create `src/simulation/organization_models.py` with:
   - `ORGANIZATION_SNAPSHOT_SCHEMA_VERSION = "organization-snapshot-v1"`;
   - `ORGANIZATION_SNAPSHOT_POLICY_VERSION = "organization-analysis.v1"`;
   - caps `MAX_SNAPSHOT_BYTES = 4 * 1024 * 1024`,
     `MAX_SNAPSHOT_CANDIDATES = 2048`, `MAX_SNAPSHOT_MEMBERS = 512`,
     `MAX_SNAPSHOT_EDGES = 16384`, `MAX_SNAPSHOT_WINDOWS = 512`,
     `MAX_SNAPSHOT_OBJECTIVE_ROWS = 4096`, `MAX_RESPONSE_BYTES = 2 * 1024 * 1024`,
     `MAX_PAGE_ROWS = 500`;
   - id patterns `^org-[0-9a-f]{16}$` and `^org-edge-[0-9a-f]{16}$`.
2. Define frozen slots DTOs:
   - `OrganizationSnapshotRef`: `publication_id`, `snapshot_digest` (64 hex),
     `schema_version`, `run_id`, `generated_tick`.
   - `OrganizationMemberRecord`: `member_id`, `status`, `basis`,
     `temporal_scope`, `first_tick`, `last_tick`, `expires_tick`, `strength`,
     `owner_support_count`.
   - `OrganizationStructuralRecord`: `kind` (`role`, `goal`, `resource`,
     `procedure`, `record`, `commitment`, `identity`), `anchor_id`, `status`,
     `first_tick`, `last_tick`, `resolved`.
   - `OrganizationCandidateRecord`: `organization_id`, `creation_tick`,
     `first_tick`, `last_tick`, `status`, `temporal_scope`, `self_identified`,
     `member_count`, `role_count`, `goal_count`, `resource_count`,
     `procedure_count`, `record_count`, `commitment_count`, `identity_count`,
     `structural_channel_count`, `members`, `structure`, `window_indexes`.
   - `OrganizationWindowRecord`: `window_index`, `start_tick`, `end_tick`,
     `candidate_ids`, `member_count`, `overlap_member_count`,
     `lane_presence`.
   - `OrganizationLineageEdgeRecord`: `kind`, `from_id`, `to_id`, `tick`,
     `jaccard`, `containment`.
   - `OrganizationObjectiveRow`: `window_index`, `tick`, `member_count`,
     `role_count`, `goal_count`, `resource_count`, `procedure_count`,
     `record_count`, `commitment_count`, `identity_count`,
     `resolved_anchor_count`, `unresolved_anchor_count`.
   - `OrganizationCoverage`: `observed`, `expected`, `ratio`.
   - `OrganizationSnapshot`: `schema_version`, `policy_version`, `run_id`,
     `input_revision`, `generated_tick`, `publication_id`, `windows`,
     `candidates`, `edges`, `objective_rows`, `coverage`, `provenance_code`.
   - `OrganizationArtifactError(ValueError)`.
3. Enforce in `__post_init__`:
   - exact types and enum values;
   - non-negative exact-int ticks; `first_tick <= last_tick`;
   - `member_count == len(members)` and each structural count matches its rows;
   - unique candidate ids; unique `(kind, anchor_id)` structural pairs; unique
     member ids per candidate;
   - every window candidate id and every edge endpoint references a known
     candidate, except `emerged.from_id` and `dissolved.to_id`;
   - overlap is derivable from member sets and reported only as a window count;
     no separate overlap id list is stored on a candidate;
   - array caps from step 1;
   - `coverage.observed <= coverage.expected`; ratio is `None` when expected is
     zero, otherwise finite and in `[0, 1]`;
   - `provenance_code` is one of `ok`, `member_list_truncated`,
     `history_truncated`, `lane_absent`;
   - `run_id` and `input_revision` are bounded safe tokens (1-128 chars from
     `[A-Za-z0-9._-]`, no `..`), and `run_id` is never used as a raw path
     component without this validation.
4. Provide `require_organization_id`, `require_publication_id`, and
   `empty_organization_snapshot(run_id, input_revision, generated_tick)`.
5. Create `src/simulation/organization_codec.py`:
   - `encode_organization_value(value)` uses `json.dumps` with
     `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`, plus one
     trailing newline;
   - `validate_organization_value` rejects non-finite floats, non-string dict
     keys, and unsupported types;
   - `decode_organization_value` rejects duplicate keys, `NaN`/`Infinity`,
     non-UTF-8, and payloads over `MAX_SNAPSHOT_BYTES`;
   - `encode_organization_snapshot`/`decode_organization_snapshot` enforce exact
     key sets, construct DTOs, and re-encode to demand byte equality; a mismatch
     raises `organization_digest_mismatch`;
   - `organization_digest(payload)` is SHA-256 hex;
   - `compute_organization_publication_id(snapshot)` normalizes
     `publication_id` to `""`, canonical-encodes, hashes `run_id + b"\x00" +
     encoded`, truncates to 16 hex, and prefixes `org-edge-`.
6. Exact key sets are module constants; no open-ended dictionaries are accepted.
7. Export `OrganizationSnapshot`, `OrganizationSnapshotRef`,
   `OrganizationCandidateRecord`, `OrganizationMemberRecord`,
   `OrganizationStructuralRecord`, `OrganizationCoverage`,
   `OrganizationArtifactError`, the encode/decode/digest/publication-id helpers,
   `OrganizationRowSelection`, `select_organization_rows`,
   `OrganizationReadPort`, `OrganizationPublicationPort`,
   `OrganizationPublication`, `OrganizationCursor`, `OrganizationSummary`,
   `OrganizationReadSession`, and `organization_query_fingerprint` through
   `src/simulation/__init__.py`, matching the macro-society facade.
8. Tests:
   - byte-for-byte round trip;
   - exact keys fail closed on extra/missing keys;
   - duplicate JSON keys and non-finite floats rejected;
   - oversize payload rejected with `organization_size_limit`;
   - publication id is stable, run-bound, and idempotent;
   - changing one member changes the digest and publication id;
   - unknown edge endpoint and duplicate candidate id rejected;
   - no owner id or `orgc-` id is present anywhere in the encoded snapshot;
   - no `hash()`, UUID, or wall-clock in the codec.

### Required Interfaces and Contracts

```python
ORGANIZATION_SNAPSHOT_SCHEMA_VERSION = "organization-snapshot-v1"
MAX_SNAPSHOT_BYTES = 4 * 1024 * 1024
MAX_SNAPSHOT_CANDIDATES = 2048
MAX_SNAPSHOT_MEMBERS = 512
MAX_SNAPSHOT_EDGES = 16384
MAX_SNAPSHOT_WINDOWS = 512

def encode_organization_snapshot(snapshot: OrganizationSnapshot) -> bytes: ...
def decode_organization_snapshot(payload: bytes) -> OrganizationSnapshot: ...
def organization_digest(payload: bytes) -> str: ...
def compute_organization_publication_id(snapshot: OrganizationSnapshot) -> str: ...
```

- `simulation` must not import `analysis`, `experiments`, `persistence`, `api`,
  `infrastructure`, or `observer`.
- The snapshot publishes objective aggregate rows plus analytical candidates.
  Owner-scoped claim detail stays in the detached analysis layer; member records
  carry aggregated `status` and `owner_support_count`, never owner ids or
  `orgc-` ids. No `orgc-` id appears as a candidate identity.
- The schema contains no raw labels, speech text, memory content, or resource
  balances.

### Requirement Evidence

- Original request: "historical lineage"; the artifact must carry lineage
  without becoming world authority.
- `.ai-factory/ARCHITECTURE.md` "Versioned Extension Contract": accepted-set and
  exact-key-set evolution; never silently widen.
- V4-02 `macro-society-snapshot-v1` precedent.

### Error Handling and Logging

- `OrganizationArtifactError` codes:
  `organization_invalid_value`, `organization_digest_mismatch`,
  `organization_size_limit`, `organization_unknown_candidate`,
  `organization_duplicate_candidate`, `organization_invalid_coverage`.
- No logging in the codec; callers log counts and codes.

### Tests

- `uv run pytest tests/unit/test_organization_codec.py tests/unit/test_organization_snapshot_contract.py -q`
- `uv run pytest tests/architecture/test_organization_boundaries.py -q -k simulation_imports`
- Expected: pass.

### Acceptance Criteria

- The snapshot is canonical, bounded, exact-key, and content-addressed.
- No analysis or outer-layer import exists in `simulation/organization_*`.
- The artifact is immutable after encoding.

### Verification

- `uv run python -c "from simulation.organization_models import ORGANIZATION_SNAPSHOT_SCHEMA_VERSION as v; print(v)"`
- Expected: `organization-snapshot-v1`

## Task 13: Add paging, read/publication ports, and cursor DTO

### Intent

Provide the neutral interfaces that persistence, API, and CLI implement or
consume. Paging must be deterministic and byte-bounded; the cursor must bind to
one publication and one filter set.

### Implementation Steps

1. Create `src/simulation/organization_paging.py`:
   - `OrganizationRowSelection` with `rows`, `next_offset`, `truncated`,
     `encoded_bytes`;
   - `select_organization_rows(rows, *, offset, limit, max_bytes)` validates
     `offset >= 0`, `1 <= limit <= MAX_PAGE_ROWS`, and stops before adding a row
     that would exceed `max_bytes`;
   - a row is never split; truncation sets `truncated=True` and
     `next_offset=offset+len(selected)`.
2. Create `src/simulation/organization_ports.py`:
   - `OrganizationReadPort` Protocol: `summary(run_id)`,
     `candidates(run_id, publication_id, offset, limit, status=None)`,
     `candidate(run_id, publication_id, organization_id)`,
     `lineage(run_id, publication_id, offset, limit, kind=None)`.
   - `OrganizationPublicationPort` Protocol:
     `publish(publication: OrganizationPublication) -> None`.
   - `OrganizationPublication`: `run_id`, `publication_id`, `snapshot_digest`,
     `payload` (bytes), `generated_tick`.
   - `OrganizationSummary`: `run_id`, `publication_id`, `schema_version`,
     `generated_tick`, `candidate_count`, `edge_count`, `window_count`,
     `coverage`, `provenance_code`.
   - `OrganizationCursor`: `purpose`, `run_id`, `publication_id`,
     `snapshot_digest`, `offset`, `query_fingerprint`.
   - `OrganizationReadSession`: a byte budget with `charge(bytes)`; exceeding
     `MAX_RESPONSE_BYTES` raises `organization_response_limit`.
   - `organization_query_fingerprint(run_id, publication_id, purpose,
     filters)` hashes canonical JSON to 64 hex.
   - `require_known_organization(snapshot, organization_id)` raises
     `organization_unknown_candidate`.
3. Define the closed cursor purposes:
   `organization_summary`, `organization_candidates`,
   `organization_candidate`, `organization_lineage`.
4. Tests:
   - paging selects at most 500 rows and never exceeds the byte cap;
   - offset/limit validation;
   - truncation reports the correct next offset;
   - fingerprint changes with purpose, filter, run, or publication;
   - cursor fields are immutable and exact;
   - unknown candidate rejected.

### Required Interfaces and Contracts

```python
class OrganizationReadPort(Protocol):
    def summary(self, run_id: str) -> OrganizationSummary | None: ...
    def candidates(self, run_id: str, publication_id: str, offset: int,
                   limit: int, status: str | None = None) -> OrganizationRowSelection: ...
    def candidate(self, run_id: str, publication_id: str,
                  organization_id: str) -> OrganizationCandidateRecord | None: ...
    def lineage(self, run_id: str, publication_id: str, offset: int,
                limit: int, kind: str | None = None) -> OrganizationRowSelection: ...

class OrganizationPublicationPort(Protocol):
    def publish(self, publication: OrganizationPublication) -> None: ...
```

- Ports are separate; a reader never mutates and a publisher never reads.
- The cursor is a DTO here; HMAC signing belongs to `api` in Phase 6.
- `simulation` owns the ports; `persistence` and `api` implement/consume them.

### Requirement Evidence

- Original request: "historical lineage"; bounded reads are required for a
  long-horizon research surface.
- `.ai-factory/ARCHITECTURE.md` "Read-only presentation": read and publication
  ports are separate; no contract grants world authority.
- V4-02 paging/ports precedent.

### Error Handling and Logging

- Codes `organization_page_limit`, `organization_page_offset`,
  `organization_response_limit`, `organization_cursor_invalid`,
  `organization_unknown_candidate`.
- No logging in paging/ports.

### Tests

- `uv run pytest tests/unit/test_organization_paging.py tests/unit/test_organization_ports.py -q`
- Expected: pass.

### Acceptance Criteria

- Paging is deterministic and bounded.
- Read and publication ports are distinct.
- Cursor/fingerprint bind purpose, run, publication, and filters.

### Verification

- `uv run python -c "from simulation.organization_models import MAX_PAGE_ROWS; print(MAX_PAGE_ROWS)"`
- Expected: `500`

## Phase Risks and Mitigations

- Risk: the artifact imports analysis types to reuse enums.
  Mitigation: duplicate the closed string values in `simulation`; Task 19 asserts
  no analysis import and value parity.
- Risk: a permissive dictionary payload allows schema drift.
  Mitigation: exact key sets and decode-by-reencode byte equality.
- Risk: paging returns a partial JSON row.
  Mitigation: row-atomic selection with a byte budget.
- Risk: cursor reuse across publications serves the wrong page.
  Mitigation: cursor DTO binds publication and query fingerprint; Phase 6 signs
  and validates both.

## Phase Completion Checklist

- Every Task 12-13 acceptance criterion is met.
- Codec, contract, paging, and port tests pass.
- `simulation/organization_*` imports no outer layer.
- No migration, event, command, or capability flag is added.
- `index.md` checkboxes are updated immediately after verified completion.
