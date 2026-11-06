# Phase 4: Organized-Conflict Snapshot

Plan: [index.md](index.md)
Tasks: 16-17
Depends on: Phase 3

## Objective

Define a new bounded canonical `organized-conflict-snapshot-v1` document, its
codec, ports, cursor purposes, and paging. The snapshot is additive: diplomacy
v1/v2, its codec, and its store remain unchanged.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/simulation/diplomacy_models.py` | schema constants 97-106; caps 108-123; cursor purposes 126-135; summary 294-318; row types 321-878; validation 880-1164 | Snapshot model and cap pattern |
| `src/simulation/diplomacy_codec.py` | top keys 45-104; payload 121-144; digest 147-150; publication id 153-163; finalize 166-212; encode/decode 215-286 | Canonical codec and size guard |
| `src/simulation/diplomacy_ports.py` | publication/summary 64-84; detail wrappers 86-105; cursor 107-118; fingerprint 121-138; match 141-166; read/publisher ports 178-240 | Port and cursor contract |
| `src/simulation/diplomacy_paging.py` | clamp 38-41; page 44-68; selectors 71-291 | Bounded paging pattern |
| `src/simulation/diplomacy_status.py` | derived labels 19-66 | Composer-derived status labels |
| `tests/unit/test_diplomacy_snapshot.py` | round-trip 160-178; tamper 193-200; caps/foreign refs 203-225; historical pins 275-294 | Snapshot tests to mirror |
| `tests/unit/test_diplomacy_ports.py` | purposes 83+; paging 96-126; fingerprint 128-190 | Port/cursor tests to mirror |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/simulation/organized_conflict_models.py` | create | Snapshot constants, caps, row types, summary, validation |
| `src/simulation/organized_conflict_codec.py` | create | Canonical payload, digest, publication id, encode/decode, 4 MiB guard |
| `src/simulation/organized_conflict_ports.py` | create | Publication/summary, detail wrappers, six cursor purposes, fingerprint, read/publisher ports |
| `src/simulation/organized_conflict_paging.py` | create | Bounded selectors for episodes, participants, plans, interpretations |
| `src/simulation/__init__.py` | modify | Public facade exports |
| `tests/unit/test_organized_conflict_snapshot.py` | create | Round-trip, digest, tamper, caps, foreign refs |
| `tests/unit/test_organized_conflict_ports.py` | create | Six purposes, paging, cursor binding |

## Task 16: Define organized-conflict-snapshot-v1 and canonical codec

### Intent

Create a canonical publication document that carries objective summaries,
owner-token rows, and analytical episode rows without raw ids or free text.

### Implementation Steps

1. Create `src/simulation/organized_conflict_models.py` with:
   - `ORGANIZED_CONFLICT_SNAPSHOT_SCHEMA = "organized-conflict-snapshot-v1"`
   - `ORGANIZED_CONFLICT_SNAPSHOT_POLICY = "organized-conflict-snapshot.v1"`
   - `MAX_SNAPSHOT_EPISODES = 4096`
   - `MAX_SNAPSHOT_PARTICIPANTS = 16384`
   - `MAX_SNAPSHOT_PLANS = 8192`
   - `MAX_SNAPSHOT_INTERPRETATIONS = 16384`
   - `MAX_SNAPSHOT_OUTCOMES = 32768`
   - `MAX_SNAPSHOT_CONTRADICTIONS = 8192`
   - `MAX_SNAPSHOT_LINEAGE = 16384`
   - `MAX_SNAPSHOT_CANDIDATES = 2048`
   - `MAX_SNAPSHOT_BYTES = 4 * 1024 * 1024`
   - `MAX_DETAIL_ROWS = 500`
2. Define row dataclasses:
   - `OrganizedConflictSummaryRow`
   - `OrganizedConflictEpisodeRow`
   - `OrganizedConflictParticipantRow`
   - `OrganizedConflictPlanRow`
   - `OrganizedConflictInterpretationRow`
   - `OrganizedConflictOutcomeRow`
   - `OrganizedConflictContradictionRow`
   - `OrganizedConflictTerminationRow`
   - `OrganizedConflictLineageRow`
   - `OrganizedConflictMetricProvenanceRow`
3. Token rules:
   - agent/participant/side/owner tokens are exactly 16 lowercase hex;
   - episode ids are `oc-` + 16 hex;
   - plan/interpretation/outcome/contradiction/termination ids are `ocp-`,
     `oci-`, `ocx-`, `occ-`, `oct-` + 16 hex;
   - lineage ids are `oc-edge-` + 16 hex;
   - `org-`/`msoc-` ids are opaque anchors; `region` anchors are opaque.
4. Define `OrganizedConflictSnapshot` with `schema_version`, `policy_version`,
   `run_id`, `publication_id`, `digest`, `summary`, all row tuples, `coverage`,
   `notices`.
5. Validation:
   - exact schema/policy;
   - `run_id` is a stable id; `publication_id` is `oc-pub-` + 16 hex;
   - digest is 64 lowercase hex;
   - rows sorted by primary id; no duplicates;
   - episode foreign references resolve for participants/interpretations;
   - plan references resolve for outcomes/terminations/contradictions;
   - lineage endpoints resolve;
   - caps and 4 MiB limit;
   - no raw ids, free-text target, or forbidden result fields.
6. Add `empty_organized_conflict_snapshot(run_id, ...)`.
7. Create `src/simulation/organized_conflict_codec.py`:
   - `ORGANIZED_CONFLICT_TOP_KEYS` exact set;
   - `ORGANIZED_CONFLICT_ROW_MAP` exact row keys;
   - `_canonical_payload` sorted JSON, compact separators, UTF-8;
   - `organized_conflict_snapshot_digest`;
   - `compute_organized_conflict_publication_id` -> `oc-pub-` + 16 hex of
     SHA-256(`run_id\x1fdigest`);
   - `finalize_organized_conflict_snapshot` fills digest/publication id,
     re-encodes, and enforces 4 MiB;
   - `encode_organized_conflict_snapshot` / `decode_organized_conflict_snapshot`
     with exact-key and exact-schema checks.
8. Add tests for round-trip, digest stability, tamper rejection, wrong schema,
   duplicate rows, foreign refs, cap overflow, size overflow, and raw-id
   rejection.

### Required Interfaces and Contracts

```python
ORGANIZED_CONFLICT_SNAPSHOT_SCHEMA: Final[str] = "organized-conflict-snapshot-v1"
ORGANIZED_CONFLICT_SNAPSHOT_POLICY: Final[str] = "organized-conflict-snapshot.v1"
MAX_SNAPSHOT_BYTES: Final[int] = 4 * 1024 * 1024

@dataclass(frozen=True, slots=True)
class OrganizedConflictSnapshot: ...
def finalize_organized_conflict_snapshot(snapshot: OrganizedConflictSnapshot) -> OrganizedConflictSnapshot: ...
def encode_organized_conflict_snapshot(snapshot: OrganizedConflictSnapshot) -> bytes: ...
def decode_organized_conflict_snapshot(payload: bytes) -> OrganizedConflictSnapshot: ...
```

Compatibility: a new schema identifier only. No existing diplomacy schema,
codec, or store identifier changes.

### Requirement Evidence

- Source: `.ai-factory/ARCHITECTURE.md` requirement 1 — accepted-set and exact
  key-set evolution.
- Source: `src/simulation/diplomacy_models.py` 97-123 and `diplomacy_codec.py`
  45-286 — snapshot/codec pattern.
- Supported combinations: empty snapshot; populated snapshot; tampered bytes;
  wrong schema; over-cap; over-4-MiB; raw id.

### Error Handling and Logging

- `ValueError("organized_conflict_snapshot_schema")`,
  `("organized_conflict_snapshot_digest")`,
  `("organized_conflict_snapshot_size_limit")`,
  `("organized_conflict_snapshot_duplicate_id")`,
  `("organized_conflict_snapshot_foreign_reference")`.
- WARN `organized_conflict_snapshot_cap family=%s count=%s cap=%s`.
- INFO `organized_conflict_snapshot_finalized episodes=%s plans=%s bytes=%s`.
- Never log row content or ids.

### Tests

- `tests/unit/test_organized_conflict_snapshot.py`
  - `test_snapshot_round_trip_preserves_digest`
  - `test_tampered_payload_is_rejected`
  - `test_duplicate_and_foreign_rows_are_rejected`
  - `test_caps_and_size_limit_fail_closed`
  - `test_raw_ids_and_free_text_are_rejected`
- Command: `uv run pytest tests/unit/test_organized_conflict_snapshot.py -q`

### Acceptance Criteria

- `organized-conflict-snapshot-v1` is canonical, bounded, and immutable.
- Encode/decode round-trips exactly and rejects tampering.
- No raw agent id, free-text target, or frame body is present.
- Diplomacy v1/v2 remain decodable and unchanged.

### Verification

- `uv run pytest tests/unit/test_organized_conflict_snapshot.py -q`
- Expected: all pass.

## Task 17: Add conflict ports cursor purposes and bounded paging

### Intent

Let the store and API select typed snapshot rows with purpose-bound cursors and
hard row limits.

### Implementation Steps

1. Create `src/simulation/organized_conflict_ports.py`:
   - `ORGANIZED_CONFLICT_CURSOR_PURPOSES` exactly:
     `summary`, `episodes`, `episode`, `plans`, `plan`, `interpretations`.
   - `OrganizedConflictPublication` with `run_id`, `publication_id`, `digest`,
     `schema_version`, `summary`.
   - `OrganizedConflictSummary` with counts and coverage.
   - Detail wrappers for episode, plan, interpretation, and participant rows.
   - `OrganizedConflictCursor` with purpose validation.
   - `organized_conflict_query_fingerprint` binding run, publication, digest,
     purpose, and sorted filters.
   - `organized_conflict_cursor_matches`.
   - `bounded_conflict_detail_rows`.
   - `OrganizedConflictReadPort` protocol with summary, episode page, episode
     detail, plan page, plan detail, interpretation page.
   - `OrganizedConflictPublisherPort` and `OrganizedConflictPublicationPort`.
2. Create `src/simulation/organized_conflict_paging.py`:
   - `OrganizedConflictRowSelection` dataclass.
   - `_clamp` to `1..MAX_DETAIL_ROWS`.
   - `_page` sorts by key and returns `after_key`, `next_key`.
   - selectors:
     `select_conflict_episodes`, `select_conflict_episode_detail`,
     `select_conflict_plans`, `select_conflict_plan_detail`,
     `select_conflict_interpretations`.
   - detail concatenates participants for an episode and outcomes/contradictions/
     terminations for a plan, with a `truncated` flag at 500.
3. Add tests for six purposes, unknown purpose rejection, page clamping, after-key
   behavior, truncation, fingerprint binding, and mismatch.

### Required Interfaces and Contracts

```python
ORGANIZED_CONFLICT_CURSOR_PURPOSES: Final[frozenset[str]] = frozenset(
    {"summary", "episodes", "episode", "plans", "plan", "interpretations"}
)

@dataclass(frozen=True, slots=True)
class OrganizedConflictCursor: ...
def organized_conflict_query_fingerprint(...) -> str: ...
def organized_conflict_cursor_matches(cursor, fingerprint) -> bool: ...
class OrganizedConflictReadPort(Protocol): ...
```

Compatibility: six purposes only; the diplomacy eight-purpose set is unchanged.

### Requirement Evidence

- Source: `src/simulation/diplomacy_ports.py` 107-240 and `diplomacy_paging.py`
  31-291 — cursor/paging pattern.
- Source: `src/api/diplomacy_cursor.py` — later signing of the same fingerprint.
- Supported combinations: each purpose; unknown purpose; same binding; changed
  binding; expired; truncated detail.

### Error Handling and Logging

- Unknown purpose -> `ValueError("organized_conflict_cursor_purpose")`.
- Unknown after-key -> empty page, not an error.
- DEBUG `organized_conflict_page purpose=%s limit=%s after=%s rows=%s`.
- Never log cursor payloads, filters, or row ids.

### Tests

- `tests/unit/test_organized_conflict_ports.py`
- Command: `uv run pytest tests/unit/test_organized_conflict_ports.py -q`

### Acceptance Criteria

- Exactly six purposes exist.
- Pages are sorted, bounded, and deterministic.
- Cursor fingerprint binds run, publication, digest, purpose, and filters.
- Detail truncation is explicit.

### Verification

- `uv run pytest tests/unit/test_organized_conflict_ports.py -q`
- Expected: all pass.

## Phase Risks and Mitigations

- Risk: extending diplomacy v2 causes a schema rewrite.
  Mitigation: new `organized-conflict-snapshot-v1`; diplomacy files are not
  edited.
- Risk: snapshot rows leak raw ids.
  Mitigation: token validators at construction and decode.
- Risk: paging reads past the detail cap.
  Mitigation: `_clamp` and `truncated` tests.
- Risk: cursor purposes drift.
  Mitigation: exact-set test.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
