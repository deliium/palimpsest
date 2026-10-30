# Phase 5: Snapshot Artifact Contract

Plan: [index.md](index.md)
Tasks: 10-11
Depends on: Phase 3 (Task 7), Phase 4 (Task 8)

## Objective

Define an immutable, versioned, bounded snapshot document for macro-society
analysis plus the read/publication ports behind it. The contract lives in
`simulation` (so `analysis`, `api`, and `persistence` stay independent) and
carries no analysis implementation types.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/simulation/civilization_codec.py` | `civilization_digest`, `validate_civilization_value`, `encode_civilization_value`, `decode_civilization_value` | Canonical JSON + trailing LF digest and strict decode pattern. |
| `src/simulation/civilization_models.py` | `CivilizationError`, `CivilizationCoverage`, `CivilizationSourceRef`, `CivilizationHashManifest` | Error/coverage/source-reference conventions. |
| `src/simulation/civilization_paging.py` | `CivilizationRowSelection`, `select_civilization_rows` | Byte/budget-aware keyset selection pattern. |
| `src/simulation/lineage_ports.py` | `LineageReadPort`, `LineagePublicationPort`, `LineageReadSession`, read budgets, `MAX_RESPONSE_BYTES`, cursor types, `lineage_query_fingerprint` | Port and cursor contract to mirror. |
| `src/simulation/civilization_store_index.py` | `build_index_root`, `lineage_object_path`, `compute_store_publication_id` | Content-addressed object naming already shared by both stores. |
| `src/simulation/lineage_codec.py` | manifest/node/page encode-decode, `compute_publication_id`, size limits | Publication id and strict-key codec shape. |
| `tests/architecture/test_lineage_explorer_boundaries.py` | simulation-module import restrictions | Import rules the new `simulation/macro_society_*.py` modules must satisfy. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/simulation/macro_society_models.py` | create | DTOs, coverage, errors, limits, schema constants. |
| `src/simulation/macro_society_codec.py` | create | Canonical encode/decode, digest, publication id. |
| `src/simulation/macro_society_paging.py` | create | Deterministic bounded row selection. |
| `src/simulation/macro_society_ports.py` | create | Read and publication ports, cursors, query fingerprint. |
| `src/simulation/__init__.py` | modify | Export the public contract. |
| `tests/unit/test_macro_society_codec.py` | create | Strict encoding proofs. |
| `tests/unit/test_macro_society_paging.py` | create | Bounded selection proofs. |
| `tests/unit/test_macro_society_ports.py` | create | Port and cursor contract proofs. |

## Task 10: Define snapshot models and the canonical codec

### Intent

One canonical byte representation makes publication ids, digests, and
reproducibility independent of Python object layout or dict ordering.

### Implementation Steps

1. Create `src/simulation/macro_society_models.py` importing only the standard
   library and `world.identifiers` (no `analysis`, `experiments`, `api`,
   `persistence`, `observer`, `infrastructure`).
2. Constants:
   - `MACRO_SOCIETY_SNAPSHOT_SCHEMA_VERSION = "macro-society-snapshot-v1"`
   - `MACRO_SOCIETY_STORE_SCHEMA_VERSION = "macro-society-store-v1"`
   - `MAX_SNAPSHOT_BYTES = 4 * 1024 * 1024`
   - `MAX_SNAPSHOT_CANDIDATES = 4096`
   - `MAX_SNAPSHOT_MEMBERS = 512`
   - `MAX_SNAPSHOT_EDGES = 16384`
   - `MAX_SNAPSHOT_WINDOWS = 512`
   - `MAX_SNAPSHOT_OBJECTIVE_ROWS = 4096`
3. `class MacroSocietyArtifactError(ValueError)` with a stable `reason_code` and
   `_LOG.debug("macro_society_artifact_invalid reason_code=%s", ...)`.
4. Frozen slotted DTOs:
   - `MacroSocietyCoverage(observed, expected, ratio)` — same semantics as the
     analysis type but independently defined (no analysis import).
   - `MacroSocietyWindowRecord(window_index, tick_start, tick_end, candidate_ids, overlap_person_count, known_person_count, lane_presence)`
     where `lane_presence` is a sorted tuple of `(lane, bool)`.
   - `MacroSocietyCandidateRecord(macro_society_id, creation_tick, first_tick, last_tick, status, member_ids, lane_signature, overlap_person_ids)`
     with `len(member_ids) <= MAX_SNAPSHOT_MEMBERS`.
   - `MacroSocietyLineageEdgeRecord(from_id, to_id, kind, from_tick, to_tick, jaccard)`
     where exactly one endpoint may be `None` for `emerged`/`dissolved`.
   - `MacroSocietyObjectiveRow(region_id, tick, population_count, cohort_id, stage_id)`.
   - `MacroSocietySnapshotRef(publication_id, digest, schema_version)`.
   - `MacroSocietySnapshot(schema_version, policy_version, run_id, input_revision, generated_tick, publication_id, windows, candidates, edges, objective_rows, coverage, provenance_code)`.
5. Validation rules: ids match `msoc-` + 16 hex for candidates and
   `msoc-edge-` + 16 hex for publication ids; ticks non-negative and monotone
   inside records; sorted unique member ids; candidate ids unique; edge endpoints
   refer to known candidate ids or `None`; window indexes strictly increasing;
   all caps enforced with `macro_society_size_limit`; unknown field names in
   decoded input rejected with `macro_society_unknown_field`.
6. Create `src/simulation/macro_society_codec.py`:
   - `validate_macro_society_value(value)` — recursive: reject non-finite floats,
     non-string mapping keys, and unsupported types.
   - `encode_macro_society_value(value) -> bytes` — canonical compact JSON
     (`sort_keys=True, separators=(",", ":"), ensure_ascii=False`) plus one
     trailing `\n`, encoded UTF-8.
   - `decode_macro_society_value(payload: bytes)` — reject duplicate keys
     (`macro_society_duplicate_key`), trailing garbage, invalid UTF-8, and
     non-object roots.
   - `macro_society_digest(value) -> str` — SHA-256 hex over the encoded bytes.
   - `encode_macro_society_snapshot(snapshot) -> bytes` and
     `decode_macro_society_snapshot(payload) -> MacroSocietySnapshot` with strict
     exact key sets per schema version.
   - `compute_macro_society_publication_id(snapshot_payload: bytes, *, run_id: str) -> str`
     = `msoc-edge-` + first 16 hex of SHA-256 over `run_id + "\0"` + payload.
7. Enforce `MAX_SNAPSHOT_BYTES` after encoding; reject larger snapshots with
   `macro_society_size_limit`.

### Required Interfaces and Contracts

- Encoding is byte-stable: equal values produce equal bytes on every platform.
- Decoding is fail-closed: no extra keys, no defaulted missing keys, no float
  NaN/Infinity, no implicit schema upgrade.
- Snapshot version `macro-society-snapshot-v1` is accepted only; a future version
  must be a new schema constant, never a widened identifier.

### Error Handling and Logging

- Codes: `macro_society_duplicate_key`, `macro_society_unknown_field`,
  `macro_society_missing_field`, `macro_society_invalid_value`,
  `macro_society_size_limit`, `macro_society_unsupported_schema`,
  `macro_society_digest_mismatch`.
- `_LOG.debug` records codes and byte counts only, never snapshot content.

### Tests

`tests/unit/test_macro_society_codec.py`:
- Round-trip a representative snapshot byte-for-byte.
- Inserting an unknown key raises `macro_society_unknown_field`.
- Removing a required key raises `macro_society_missing_field`.
- Duplicate JSON keys raise `macro_society_duplicate_key`.
- `NaN`/`Infinity` raise `macro_society_invalid_value`.
- A 4 MiB + 1 byte snapshot raises `macro_society_size_limit`.
- Digests are stable across calls and change with one member.
- Publication ids are prefixed `msoc-edge-`, 16 hex, and differ per run id.

### Acceptance Criteria

- Snapshot bytes are canonical and independently reproducible from the DTOs.
- No analysis, persistence, API, or experiment type appears in the module.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_macro_society_codec.py -q`
- `uv run --frozen --python 3.12.14 mypy src/simulation/macro_society_models.py src/simulation/macro_society_codec.py`

## Task 11: Add bounded paging and read/publication ports

### Intent

Readers must not be able to pull an unbounded snapshot, and writers must publish
one immutable revision. Ports keep the API and the filesystem store independent
of analysis.

### Implementation Steps

1. Create `src/simulation/macro_society_paging.py`:
   - `@dataclass(frozen=True, slots=True) class MacroSocietyRowSelection` with
     `rows: tuple[object, ...]`, `next_offset: int | None`, `bytes_used: int`.
   - `select_macro_society_rows(rows, *, offset, limit, max_bytes) -> MacroSocietyRowSelection`:
     deterministic order-preserving selection, `limit` clamped to a documented
     `MAX_PAGE_ROWS = 500`, byte accounting via the codec, and a truncation rule
     that always returns at least one row even when it alone exceeds
     `max_bytes` (documented explicitly, mirroring civilization paging).
2. Create `src/simulation/macro_society_ports.py`:
   - `MAX_RESPONSE_BYTES = 2 * 1024 * 1024`.
   - `MacroSocietyReadPort` protocol with
     `read_summary(run_id)`, `read_candidates(run_id, *, publication_id, offset, limit)`,
     `read_candidate(run_id, macro_society_id, *, publication_id)`,
     `read_lineage(run_id, *, publication_id, offset, limit)`.
   - `MacroSocietyPublicationPort` protocol with
     `publish(publication: MacroSocietyPublication) -> MacroSocietySnapshotRef`.
   - `MacroSocietyPublication` dataclass wrapping the snapshot payload plus
     storage hints (`run_id`, `created_at_utc` as metadata only).
   - `MacroSocietyCursor` with `purpose`, `run_id`, `publication_id`,
     `snapshot_digest`, `offset`, and `query_fingerprint`.
   - `macro_society_query_fingerprint(run_id, publication_id, purpose, filters) -> str`
     using canonical JSON and SHA-256.
   - `MacroSocietyReadSession` dataclass carrying the pinned publication id,
     digest, and remaining byte budget.
3. Document that ports carry no world authority, no command, and no write path
   other than publication of a completed run.

### Required Interfaces and Contracts

- Pages are keyset-safe: `next_offset` is `None` exactly at the end.
- A cursor is bound to purpose, run, publication, digest, and filter fingerprint;
  any mismatch fails closed.
- Publication is append-only: an existing `publication_id` is never rewritten.
- No port method accepts a `WorldEngine`, `WorldState`, or command type.

### Error Handling and Logging

- `macro_society_cursor_mismatch`, `macro_society_publication_missing`,
  `macro_society_response_too_large`.
- `_LOG.debug("macro_society_port method=%s run=%s rows=%s bytes=%s", ...)`.

### Tests

`tests/unit/test_macro_society_paging.py`:
- Offset/limit selection returns stable slices and `next_offset`.
- `limit > MAX_PAGE_ROWS` is clamped.
- A single oversized row is still returned alone with `next_offset` set.
- Repeated selection with the same arguments is identical.

`tests/unit/test_macro_society_ports.py`:
- A cursor round-trips through its fingerprint and rejects a changed purpose,
  run, publication, or filter.
- `MAX_RESPONSE_BYTES` is enforced by the session helper.
- Protocol conformance: a stub reader/publisher satisfies the protocols.
- Ports import no analysis or persistence module (AST check).

### Acceptance Criteria

- Paging is deterministic and bounded.
- Ports are protocol-only; no concrete storage leaks into `simulation`.
- Cursor mismatch is impossible to ignore.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_macro_society_paging.py tests/unit/test_macro_society_ports.py -q`
- `uv run --frozen --python 3.12.14 pytest tests/architecture/test_lineage_explorer_boundaries.py -q`

## Phase Risks and Mitigations

- Risk: duplicating analysis DTOs invites drift.
  Mitigation: the artifact is an explicitly independent schema; Task 12 maps
  analysis → artifact once, and round-trip tests pin the mapping.
- Risk: paging semantics diverge from civilization/lineage paging.
  Mitigation: mirror the documented truncation rule and cite it in the module
  docstring.
- Risk: snapshot growth beyond memory.
  Mitigation: hard caps at validation time plus byte caps at encode time.

## Phase Completion Checklist

- Every Task 10-11 acceptance criterion is satisfied.
- `simulation/macro_society_*` imports only standard library and `world`.
- Artifact schema is versioned, closed, and byte-stable.
- `index.md` task checkboxes are updated immediately after verified completion.
