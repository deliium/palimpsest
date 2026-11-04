# Phase 4: Diplomacy Snapshot v1

Plan: [index.md](index.md)
Tasks: 16-17
Depends on: Task 9 / Phase 3 Tasks 12-15

## Objective

Define a new independent canonical `diplomacy-snapshot-v1` artifact, its digest
and publication identity, bounded paging, read/publication ports, and six
snapshot-pinned cursor purposes. Existing organization, formal-rule, dispute,
evidence, and representation snapshots remain byte-verifiable and unchanged.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/simulation/delegation_representation_models.py` | schema/policy constants; caps 8192/16384/4 MiB; `DelegationRepresentationSnapshot`; `empty_delegation_representation_snapshot`; error | Snapshot model and cap precedent |
| `src/simulation/delegation_representation_codec.py` | `_canonical`, duplicate hook, digest, `compute_delegation_representation_publication_id`, encode/decode | Canonical codec precedent |
| `src/simulation/delegation_representation_paging.py` | `RepresentationRowSelection`; five selectors | Bounded selection precedent |
| `src/simulation/delegation_representation_ports.py` | `DELEGATION_REPRESENTATION_CURSOR_PURPOSES` 39-164; `query_fingerprint`; `cursor_matches`; `bounded_detail_rows`; ports | Six-purpose cursor and port precedent |
| `src/simulation/evidence_testimony_codec.py` | 344-488 | Independent artifact precedent |
| `tests/unit/test_delegation_representation_snapshot.py` | snapshot/codec tests | Test shape to mirror |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/simulation/diplomacy_models.py` | create | Snapshot rows, caps, schema id, empty snapshot, error |
| `src/simulation/diplomacy_codec.py` | create | Canonical encode/decode, digest, publication id |
| `src/simulation/diplomacy_paging.py` | create | Bounded row selection |
| `src/simulation/diplomacy_ports.py` | create | Cursor purposes, fingerprint, read/publication ports |
| `tests/unit/test_diplomacy_snapshot.py` | create | Snapshot and codec tests |
| `tests/unit/test_diplomacy_ports.py` | create | Paging and cursor-binding tests |

## Task 16: Define diplomacy-snapshot-v1 and its codec

### Intent

Publication needs one canonical, bounded, immutable artifact. It must not reuse,
widen, or rewrite any existing snapshot schema.

### Implementation Steps

1. Create `src/simulation/diplomacy_models.py` with:
   `DIPLOMACY_SNAPSHOT_SCHEMA = "diplomacy-snapshot-v1"`,
   `DIPLOMACY_SNAPSHOT_POLICY = "diplomacy-snapshot-policy.v1"`.
2. Caps: `MAX_SNAPSHOT_RELATIONS = 4096`, `MAX_SNAPSHOT_PARTIES = 8192`,
   `MAX_SNAPSHOT_CONTACTS = 16384`, `MAX_SNAPSHOT_ENVOYS = 8192`,
   `MAX_SNAPSHOT_NEGOTIATIONS = 8192`, `MAX_SNAPSHOT_INSTRUMENTS = 16384`,
   `MAX_SNAPSHOT_DECLARATIONS = 32768`, `MAX_SNAPSHOT_LINEAGE = 8192`,
   `MAX_SNAPSHOT_CANDIDATES = 2048`, `MAX_SNAPSHOT_BYTES = 4 * 1024 * 1024`,
   `MAX_DETAIL_ROWS = 500`.
3. Rows: `DiplomacySnapshotSummaryRow`, `DiplomacySnapshotRelationRow`,
   `DiplomacySnapshotPartyRow`, `DiplomacySnapshotContactRow`,
   `DiplomacySnapshotEnvoyRow`, `DiplomacySnapshotNegotiationRow`,
   `DiplomacySnapshotInstrumentRow`, `DiplomacySnapshotDeclarationRow`,
   `DiplomacySnapshotMisrepresentationRow`, `DiplomacySnapshotTerminationRow`,
   `DiplomacySnapshotConflictRow`, `DiplomacySnapshotLineageRow`,
   `DiplomacySnapshotMetricProvenanceRow`. The snapshot prefix mirrors V4-09's
   `DelegationRepresentation*Row` and avoids colliding with analysis
   `Diplomacy*Row` types. Rows carry content-addressed
   `relation_id`/`instrument_id`/`contact_id`/... values, hashed
   `owner_token`/`party_token`/`envoy_token`/`actor_token` values, owner-safe
   `orgc-`/region anchors, and closed enums; never raw agent ids, free-text
   subjects, or frame bodies.
4. `DiplomacySnapshot` with `schema`, `policy_version`, `run_id`,
   `publication_id`, `created_revision`, `window_end`, ordered row tuples
   (including relations and terminations), `metric_families`, `coverage`, and
   `digest`.
5. Validation: canonical row order by `(tick, id)`; unique ids; every reference
   resolves inside the snapshot; relation party sets match instrument party sets;
   no raw agent id, free-text subject, or forbidden score field; per-table caps
   and total byte cap enforced.
6. `empty_diplomacy_snapshot(run_id, *, revision, window_end)` and
   `DiplomacyArtifactError(code)`.
7. Create `src/simulation/diplomacy_codec.py` with `_canonical` JSON
   (`sort_keys=True`, compact separators, `allow_nan=False`),
   `diplomacy_snapshot_digest`, and
   `compute_diplomacy_publication_id(run_id, digest)` mirroring
   `compute_delegation_representation_publication_id`
   (`src/simulation/delegation_representation_codec.py` 199-207), plus
   `finalize_diplomacy_snapshot`, `encode_diplomacy_snapshot`, and
   `decode_diplomacy_snapshot`.
8. Decoding validates schema, policy, digest, ordering, caps, and forbidden
   fields; an unknown key is a hard error; `dip-pub-` ids are excluded from
   candidate-id validation.

### Required Interfaces and Contracts

```python
DIPLOMACY_SNAPSHOT_SCHEMA: Final[str] = "diplomacy-snapshot-v1"
DIPLOMACY_SNAPSHOT_POLICY: Final[str] = "diplomacy-snapshot-policy.v1"

def compute_diplomacy_publication_id(
    run_id: str, digest: str
) -> str: ...            # "dip-pub-" + 16 hex, content-addressed

def encode_diplomacy_snapshot(snapshot: DiplomacySnapshot) -> bytes: ...
def decode_diplomacy_snapshot(payload: bytes) -> DiplomacySnapshot: ...
```

- The artifact is independent: `organization-snapshot-v1|v2|v3`,
  `formal-rule-snapshot-v1`, `dispute-resolution-snapshot-v1`,
  `evidence-testimony-snapshot-v1`, and
  `delegation-representation-snapshot-v1` keep their bytes and decoders.
- No identity, anchor, subject, or frame body appears in the artifact.
- Digest and publication id are content-addressed and stable.

### Requirement Evidence (when reconciliation applies)

- `.ai-factory/ARCHITECTURE.md` "Use accepted-set and exact-key-set schema
  evolution"; "Preserve append-only authoritative history".
- Original Request: "Do not create magical bilateral relationship scores" — the
  snapshot publishes counts and statuses, never a score.

### Error Handling and Logging

- Codes: `diplomacy_snapshot_schema_unknown`,
  `diplomacy_snapshot_digest_mismatch`, `diplomacy_snapshot_size_limit`,
  `diplomacy_snapshot_foreign_reference`,
  `diplomacy_snapshot_forbidden_field`.
- `INFO diplomacy_snapshot_finalized relations=%s instruments=%s bytes=%s`.

### Tests

- `tests/unit/test_diplomacy_snapshot.py`: round-trip equality and digest;
  deterministic two-argument publication id; unknown schema/key rejected;
  tampered digest rejected; every cap enforced; relation/termination rows
  present; relation and instrument party sets match; rows sorted; raw agent ids
  and free-text subjects absent while owner-safe `orgc-`/region anchors remain;
  forbidden field rejected; `dip-pub-` ids are not accepted as candidates; all
  five existing snapshots still decode from committed fixtures and keep their
  digests.

### Acceptance Criteria

- A canonical snapshot encodes, decodes, and verifies byte-identically.
- Existing snapshots are untouched.

### Verification

- `uv run pytest tests/unit/test_diplomacy_snapshot.py tests/unit/test_delegation_representation_snapshot.py tests/unit/test_evidence_testimony_snapshot.py -q`
- Expected: pass.

## Task 17: Add paging, read ports, and cursor support

### Intent

Every published read must be bounded and cursor-safe. A cursor binds to the run,
publication, digest, purpose, and filters so a changed artifact can never serve a
stale page.

### Implementation Steps

1. Create `src/simulation/diplomacy_paging.py` with
   `DiplomacyRowSelection` and selectors
   `select_diplomacy_relations`, `select_diplomacy_relation`,
   `select_diplomacy_instruments`, `select_diplomacy_instrument`, and
   `select_diplomacy_lineage`. Each takes a snapshot plus an optional
   `(after_key, limit)` cursor position, clamps `limit` to 1..500, and returns
   rows plus `next_key`. Relation detail includes its parties, contacts, envoys,
   negotiations, instruments, declarations, misrepresentations, and
   terminations; instrument detail includes its declarations and terminations.
   The six cursor purposes stay unchanged because terminations are bounded
   detail rows, not a seventh page.
2. Create `src/simulation/diplomacy_ports.py` with
   `DIPLOMACY_CURSOR_PURPOSES = ("summary", "relations", "relation",
   "instruments", "instrument", "lineage")`.
3. Define `DiplomacyPublication`, `DiplomacySummary`, `DiplomacyRelationDetail`,
   `DiplomacyInstrumentDetail`, `DiplomacyCursor`,
   `diplomacy_query_fingerprint`, `diplomacy_cursor_matches`,
   `bounded_detail_rows`, and `DiplomacyPortError(code)`.
4. Define `DiplomacyReadPort` (read summary/relations/relation/instruments/
   instrument/lineage) and `DiplomacyPublicationPort` (publish snapshot,
   read publication) protocols. Ports never expose an objective or world seam.
5. `diplomacy_query_fingerprint` hashes run id, publication id, snapshot digest,
   purpose, and sorted filter pairs. `diplomacy_cursor_matches` returns false on
   any mismatch.
6. Detail reads are bounded by `MAX_DETAIL_ROWS = 500`; exceeding it returns a
   truncation marker, never an unbounded list.
7. An unknown relation/instrument id raises
   `DiplomacyPortError("diplomacy_unknown_relation")` /
   `("diplomacy_unknown_instrument")`.

### Required Interfaces and Contracts

```python
DIPLOMACY_CURSOR_PURPOSES: Final[tuple[str, ...]] = (
    "summary", "relations", "relation", "instruments", "instrument", "lineage"
)

def diplomacy_query_fingerprint(
    *, run_id: str, publication_id: str, snapshot_digest: str,
    purpose: str, filters: Mapping[str, str],
) -> str: ...
```

- Cursor purposes are exactly six and closed.
- A fingerprint mismatch is a hard error, never a silent first page.
- Paging is pure and deterministic.

### Requirement Evidence (when reconciliation applies)

- `src/simulation/delegation_representation_ports.py`: purpose-bound cursors.
- `.ai-factory/ARCHITECTURE.md`: bounded read models, no world authority.

### Error Handling and Logging

- Codes: `diplomacy_cursor_invalid`, `diplomacy_cursor_expired`,
  `diplomacy_unknown_relation`, `diplomacy_unknown_instrument`,
  `diplomacy_detail_truncated`.
- `DEBUG diplomacy_page purpose=%s rows=%s next=%s`.
- Never log cursor values or row payloads.

### Tests

- `tests/unit/test_diplomacy_ports.py`: six purposes exactly; page boundaries at
  0/1/500/501; next-key stability; fingerprint changes for run, publication,
  digest, purpose, or filter change; unknown id errors; detail truncation; paging
  over an empty snapshot returns empty with no error.

### Acceptance Criteria

- Paging is bounded and cursor-bound.
- No route can read an unpublished or changed artifact.

### Verification

- `uv run pytest tests/unit/test_diplomacy_ports.py -q`
- Expected: pass.

## Phase Risks and Mitigations

- Risk: reusing the representation snapshot schema by widening it.
  Mitigation: new schema id, new codec, and an explicit legacy-decode test.
- Risk: cursor reuse serves stale pages.
  Mitigation: five-part fingerprint binding plus mismatch tests.
- Risk: snapshot leaks identities.
  Mitigation: token-only rows and a forbidden-field/raw-id scan.

## Phase Completion Checklist

- Every task in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
