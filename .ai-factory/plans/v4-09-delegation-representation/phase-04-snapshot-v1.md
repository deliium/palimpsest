# Phase 4: Delegation-Representation Snapshot v1

Plan: [index.md](index.md)
Tasks: 14-15
Depends on: Phase 3 / Tasks 10-13

## Objective

Define the canonical, bounded, immutable
`delegation-representation-snapshot-v1` document; add a strict codec with
deterministic digests; and expose typed paging selectors and read ports bound to
publication digests and query fingerprints.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/simulation/evidence_testimony_models.py` | schema 44; policy 45-46; caps 83-114; snapshot 511 | Snapshot contract template |
| `src/simulation/evidence_testimony_codec.py` | canonical 344; digest 354; publication id 367; finalize 376; encode 405; decode 488 | Codec template |
| `src/simulation/evidence_testimony_paging.py` | `EvidenceTestimonyRowSelection` 30; `_select` 47; selectors 102-132 | Paging template |
| `src/simulation/evidence_testimony_ports.py` | publication 61; summary 76; candidate detail 98; cursor 123; purposes 39-46; fingerprint 140; match 164; detail cap 47 | Ports/cursor template |
| `src/simulation/dispute_codec.py` | versioned decode and byte-verification | Sibling snapshot that must stay unchanged |
| `src/simulation/formal_rule_codec.py` | versioned decode | Sibling snapshot that must stay unchanged |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/simulation/delegation_representation_models.py` | create | Snapshot schema, caps, rows, finalization invariants |
| `src/simulation/delegation_representation_codec.py` | create | Canonical encode/decode/digest/publication id |
| `src/simulation/delegation_representation_paging.py` | create | Typed row selection |
| `src/simulation/delegation_representation_ports.py` | create | Read/publication ports, cursor purposes, fingerprint |
| `src/simulation/__init__.py` | modify | Public exports |
| `tests/unit/test_delegation_representation_snapshot.py` | create | Contract/codec |
| `tests/unit/test_delegation_representation_ports.py` | create | Paging/ports/cursors |

## Task 14: Define delegation-representation-snapshot-v1 and its codec

### Intent

The artifact must be independent of dispute, evidence, organization, and
formal-rule snapshots, bounded, canonical, and immutable after publication.

### Implementation Steps

1. Create `src/simulation/delegation_representation_models.py` with:
   `DELEGATION_REPRESENTATION_SNAPSHOT_SCHEMA =
   "delegation-representation-snapshot-v1"`,
   `DELEGATION_REPRESENTATION_SNAPSHOT_POLICY =
   "delegation-representation-snapshot-policy.v1"`,
   `SUPPORTED_DELEGATION_REPRESENTATION_SNAPSHOT_SCHEMAS =
   (DELEGATION_REPRESENTATION_SNAPSHOT_SCHEMA,)`, and caps
   `MAX_SNAPSHOT_MANDATES = 8192`, `MAX_SNAPSHOT_POSITIONS = 16384`,
   `MAX_SNAPSHOT_BYTES = 4 * 1024 * 1024`, `MAX_SNAPSHOT_CONFLICTS = 4096`,
   `MAX_SNAPSHOT_LINEAGE_EDGES = 8192`.
2. Define frozen rows mirroring the analysis layer:
   `DelegationRepresentationSummaryRow`,
   `DelegationRepresentationCandidateRow`,
   `DelegationRepresentationMandateRow`,
   `DelegationRepresentationPositionRow`,
   `DelegationRepresentationRevocationRow`,
   `DelegationRepresentationConflictRow`,
   `DelegationRepresentationLineageRow`, and
   `DelegationRepresentationMetricProvenanceRow`. Every identity field is a
   token, exactly as listed under Required Interfaces; a raw agent id or
   free-text scope subject is rejected in `__post_init__`.
3. Define `DelegationRepresentationSnapshot` with `schema_version`,
   `policy_version`, `run_id`, `publication_id`, `digest`, `created_from`
   (harvest digest), summary, candidates, mandates, positions, revocations,
   conflicts, lineage, metric provenance, and coverage.
4. Validate in `__post_init__`: exact schema/policy, run id token, every
   collection a tuple of the exact row type, sorted deterministic order, unique
   mandate/candidate/edge ids, positions referencing existing mandates, and no
   row exceeding its cap.
5. Create `src/simulation/delegation_representation_codec.py` with:
   - `_canonical(snapshot) -> bytes` using sorted keys, compact separators,
     UTF-8, no NaN.
   - `delegation_representation_snapshot_digest(snapshot) -> str`.
   - `compute_delegation_representation_publication_id(run_id, digest) -> str`
     (content-addressed, 16 hex).
   - `finalize_delegation_representation_snapshot(snapshot)` that sorts rows,
     enforces caps, recomputes the digest, and returns a new frozen snapshot.
   - `encode_delegation_representation_snapshot(snapshot) -> bytes`.
   - `decode_delegation_representation_snapshot(payload) -> snapshot` rejecting
     unknown/extra keys, wrong schema, unknown row types, and digest mismatch.
6. Decode v1 only; a `delegation-representation-snapshot-v2` payload fails with
   `delegation_representation_snapshot_unsupported`.
7. Export the schema, caps, and codec from `src/simulation/__init__.py`.

### Required Interfaces and Contracts

```python
DELEGATION_REPRESENTATION_SNAPSHOT_SCHEMA = "delegation-representation-snapshot-v1"

@dataclass(frozen=True, slots=True)
class DelegationRepresentationMandateRow:
    mandate_id: str
    owner_token: str
    principal_kind: str
    principal_token: str | None      # hashed agent id, or orgc-/region id
    representative_token: str        # hashed agent id
    scope_kind: str
    scope_subject_token: str | None  # bounded token; never free text
    duration_kind: str
    start_tick: int
    end_tick: int | None
    provenance: str
    status: str
    recognition_basis: str
    support_roots: int
    opposition_roots: int
    confidence_band: str
    coverage: str

@dataclass(frozen=True, slots=True)
class DelegationRepresentationPositionRow:
    position_id: str
    mandate_id: str
    owner_token: str
    actor_token: str
    stance: str
    provenance: str
    tick: int
    active: bool

@dataclass(frozen=True, slots=True)
class DelegationRepresentationRevocationRow:
    revocation_id: str
    mandate_id: str
    owner_token: str
    actor_token: str
    kind: str
    provenance: str
    tick: int
    contested: bool

@dataclass(frozen=True, slots=True)
class DelegationRepresentationConflictRow:
    conflict_id: str
    owner_token: str
    mandate_ids: tuple[str, ...]
    kind: str
    status: str
    tick: int

@dataclass(frozen=True, slots=True)
class DelegationRepresentationCandidateRow:
    candidate_id: str               # rep-<16 hex>, analytical
    principal_kind: str
    principal_token: str | None
    scope_kind: str
    scope_subject_token: str | None
    status: str
    representative_tokens: tuple[str, ...]
    lineage_kind: str
    coverage: str

@dataclass(frozen=True, slots=True)
class DelegationRepresentationLineageRow:
    edge_id: str                    # rep-edge-<16 hex>
    from_candidate_id: str
    to_candidate_id: str
    kind: str
    tick: int

@dataclass(frozen=True, slots=True)
class DelegationRepresentationMetricProvenanceRow:
    family_id: str
    family_version: int
    document_digest: str

def finalize_delegation_representation_snapshot(
    snapshot: DelegationRepresentationSnapshot,
) -> DelegationRepresentationSnapshot: ...
def encode_delegation_representation_snapshot(
    snapshot: DelegationRepresentationSnapshot,
) -> bytes: ...
def decode_delegation_representation_snapshot(
    payload: bytes,
) -> DelegationRepresentationSnapshot: ...
def delegation_representation_snapshot_digest(
    snapshot: DelegationRepresentationSnapshot,
) -> str: ...
def compute_delegation_representation_publication_id(
    run_id: str, digest: str
) -> str: ...
```

- `owner_token`, `representative_token`, and `actor_token` are the analysis
  hashes, never raw agent ids. `principal_token` is the hashed agent id for
  `agent`, the `orgc-` id for a collective, and the region id for a settlement.
- `mandate_ids` in conflicts remain owner-local `rmd-` ids; they are opaque
  content addresses, not identities.
- The summary row contains aggregate counts only and no tokens.
- Encoding is canonical: the same snapshot always yields the same bytes.
- Digest covers every published field except `digest` and `publication_id`.
- Caps are checked before hashing so an oversized snapshot never gets an id.
- The snapshot carries no objective event bodies, commands, free text, or peer
  owner ids.

### Error Handling and Logging

- Codes: `delegation_representation_snapshot_unsupported`,
  `delegation_representation_size_limit`,
  `delegation_representation_snapshot_invalid`,
  `delegation_representation_digest_mismatch`.
- `INFO delegation_representation_snapshot_finalized mandates=%d bytes=%d` with
  counts only.
- Never log mandate ids, principals, representatives, or scope subjects.

### Tests

- `tests/unit/test_delegation_representation_snapshot.py`: round-trip; canonical
  byte stability under row permutation; digest excludes its own fields; cap
  enforcement for each collection and byte limit; unknown schema/v2 rejected;
  extra keys rejected; digest tamper rejected; raw agent id in any token field
  rejected; empty snapshot valid.

### Acceptance Criteria

- Snapshot v1 is canonical, bounded, and immutable.
- No sibling snapshot schema or codec is modified.

### Verification

- `uv run pytest tests/unit/test_delegation_representation_snapshot.py -q`
- Expected: pass; `uv run pytest tests/unit/test_dispute_snapshot.py tests/unit/test_evidence_testimony_snapshot.py tests/unit/test_organization_snapshot.py -q` stays green.

## Task 15: Add paging, read ports, and cursor support

### Intent

Every public read must be typed, bounded, and digest-bound so a cursor cannot be
replayed against a different run, filter, publication, or digest.

### Implementation Steps

1. Create `src/simulation/delegation_representation_paging.py` with
   `RepresentationRowSelection` and pure selectors:
   `select_representation_candidates`, `select_representation_mandates`,
   `select_representation_positions`,
   `select_representation_revocations`, `select_representation_lineage`.
2. Each selector accepts `(snapshot, *, cursor_offset=0, limit=100)`, clamps
   `limit` to `1..500`, slices deterministically, and returns the page plus
   `next_offset` and `has_more`.
3. Create `src/simulation/delegation_representation_ports.py` with:
   - `DELEGATION_REPRESENTATION_CURSOR_PURPOSES = ("summary", "mandates",
     "mandate", "positions", "revocations", "lineage")`.
   - `DelegationRepresentationPublication`, `Summary`,
     `CandidateDetail`, `Cursor` frozen types.
   - `delegation_representation_query_fingerprint(run_id, purpose, filters)`.
   - `delegation_representation_cursor_matches(cursor, *, run_id, publication_id,
     digest, fingerprint)`.
   - `DelegationRepresentationReadPort` and
     `DelegationRepresentationPublicationPort` protocols with GET-equivalent
     read methods and one publish method.
   - `MAX_CANDIDATE_DETAIL_ROWS = 500`.
4. Define the read methods: `summary(run_id)`, `candidates(run_id, cursor)`,
   `candidate(run_id, candidate_id)`,
   `mandates(run_id, cursor, *, candidate_id=None)`,
   `positions(run_id, mandate_id, cursor)`,
   `revocations(run_id, mandate_id, cursor)`, `lineage(run_id, cursor)`. The
   optional `candidate_id` narrows the mandate page and is part of the cursor
   fingerprint.
5. Ensure the detail method clamps to `MAX_CANDIDATE_DETAIL_ROWS` and reports
   truncation explicitly in the response.
6. Export the purposes and ports from `src/simulation/__init__.py`.

### Required Interfaces and Contracts

- Cursor purpose is one of the six exact strings; adding a seventh requires a
  new plan.
- Fingerprint binds run, purpose, and every filter field in sorted order.
- A cursor minted for one purpose cannot be used for another.

### Error Handling and Logging

- Raising `delegation_representation_cursor_invalid` is the API layer's job;
  ports return a typed mismatch signal instead of raising.
- DEBUG `representation_page purpose=%s offset=%d limit=%d`.
- Never log filter values that contain principal tokens.

### Tests

- `tests/unit/test_delegation_representation_ports.py`: selector determinism;
  limit clamping; next-offset correctness; six purposes exact; fingerprint
  changes with each field; cursor mismatch for run/publication/digest/purpose;
  detail cap; protocol conformance via a fake reader.

### Acceptance Criteria

- Paging is bounded and deterministic.
- Cursor bindings cover run, publication, digest, purpose, and filters.

### Verification

- `uv run pytest tests/unit/test_delegation_representation_ports.py -q`
- Expected: pass.

## Phase Risks and Mitigations

- Risk: a snapshot grows without bound on dense runs.
  Mitigation: per-collection and byte caps with explicit failure before hashing.
- Risk: cursor reuse serves the wrong page.
  Mitigation: digest + fingerprint binding tested for each field.
- Risk: editing a sibling snapshot to share code.
  Mitigation: V4-09 creates independent modules; sibling codec tests stay green.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
