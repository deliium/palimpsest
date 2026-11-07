# Phase 4: Borders Snapshot

Plan: [index.md](index.md)
Tasks: 16-17
Depends on: Phase 3 / Tasks 11-15

## Objective

Define the canonical, bounded, immutable `borders-snapshot-v1` document and its
typed read/publication ports. The snapshot mirrors the four analysis layers and
their provenance without creating an objective border object, a country owner, a
truth, or a composite score. It does not rewrite `organized-conflict-snapshot-v1`,
`diplomacy-snapshot-v1`/`v2`, or any existing store.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/simulation/organized_conflict_models.py` | schema/policy 38-49; forbidden names 51-94; rows 109-273; snapshot 276-370; empty 373-383 | Newest canonical snapshot pattern |
| `src/simulation/organized_conflict_codec.py` | top keys 39-59; canonical JSON 73-80; digest 83-90; publication id 93-95; encode/decode 126-178 | Codec and digest pattern |
| `src/simulation/organized_conflict_ports.py` | cursor purposes 27-29; summary/publication/cursor 32-63; fingerprint 66-85; protocols 99-125 | Port and cursor pattern |
| `src/simulation/organized_conflict_paging.py` | sorted page 22-77 | Bounded paging pattern |
| `src/simulation/diplomacy_models.py` | schema set 97-125; forbidden fields 154-187; snapshot 846-878 | Additive v1/v2 compatibility precedent |
| `src/simulation/diplomacy_codec.py` | payload 121-144; digest 147-150; id 153-163 | Compatibility precedent |
| `src/simulation/diplomacy_ports.py` | 41-237 | Richer cursor/filter precedent |
| `src/analysis/borders_contract.py` | four layer/row contracts | Source of snapshot row types |
| `src/analysis/borders_metrics.py` | metric documents | Provenance rows |
| `src/analysis/specifications.py` | catalog 176 after Task 15 | Metric family names |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/simulation/borders_models.py` | create | Snapshot schema, policy, row models, caps, forbidden-field guard |
| `src/simulation/borders_codec.py` | create | Canonical JSON, digest, publication id, encode/decode |
| `src/simulation/borders_ports.py` | create | Summary/publication/cursor types and read/publisher protocols |
| `src/simulation/borders_paging.py` | create | Deterministic bounded paging |
| `src/simulation/__init__.py` | modify | Export the public snapshot and port symbols |
| `tests/unit/test_borders_snapshot.py` | create | Snapshot bounds, sorting, refs, forbidden fields |
| `tests/unit/test_borders_codec.py` | create | Canonical bytes, digest, round trip, legacy isolation |
| `tests/unit/test_borders_ports.py` | create | Cursor purposes, fingerprint, match |
| `tests/unit/test_borders_paging.py` | create | Page bounds, stable keys, detail cap |

## Task 16: Define borders-snapshot-v1 and its canonical codec

### Intent

Give the completed-run border analysis one immutable artifact with a stable
schema, exact row families, canonical bytes, and a content-addressed publication
id. The snapshot is a read model, not a world authority.

### Implementation Steps

1. Create `src/simulation/borders_models.py`:
   - `BORDERS_SNAPSHOT_SCHEMA: Final[str] = "borders-snapshot-v1"`
   - `BORDERS_SNAPSHOT_POLICY: Final[str] = "borders-snapshot.v1"`
   - `BORDERS_SNAPSHOT_MAX_BYTES: Final[int] = 4 * 1024 * 1024`
   - `BORDERS_MAX_ROWS_PER_FAMILY: Final[int] = 5000`
   - `BORDERS_MAX_LINEAGE_EDGES: Final[int] = 32`
   - `BORDERS_MAX_DETAIL_ROWS: Final[int] = 500`
   - `BORDERS_PUBLICATION_PREFIX: Final[str] = "bd-pub-"`
2. Add `BORDERS_FORBIDDEN_FIELD_NAMES`:
   `country_owner`, `sovereignty`, `sovereign`, `legitimate`, `legitimacy`,
   `winner`, `loser`, `score`, `composite`, `enforced`, `enforcement`,
   `border_truth`, `ownership`, `title`, `raw_owner_id`, `raw_entity_id`,
   `raw_agent_id`, `frame_body`, `evidence_body`.
   The guard checks every snapshot row's dataclass field names and every
   published string key; a match raises
   `ValueError("borders_forbidden_field:<name>")`.
3. Define the frozen rows:
   - `BordersSummaryRow`: `run_id`, `publication_id`, `digest`,
     `schema_version`, `policy_version`, `catalog_version`, `claim_count`,
     `agreement_count`, `dispute_count`, `physical_row_count`,
     `pattern_count`, `candidate_count`, `coverage`.
   - `BordersCandidateRow`: `candidate_token`, `location_tokens`,
     `boundary_edge_tokens`, `status`, `evidence_count`, `first_tick`,
     `last_tick`.
   - `BordersClaimRow`: `claim_token`, `owner_token`, `domain_token`,
     `location_tokens`, `boundary_edge_tokens`, `status`, `strength`,
     `anchor_token`.
   - `BordersRecognitionRow`: `recognition_token`, `domain_token`,
     `edge_tokens`, `basis`, `status`.
   - `BordersAccessRow`: `access_token`, `domain_token`, `subject_token`,
     `mode`, `status`.
   - `BordersAgreementRow`: `agreement_token`, `domain_token`,
     `counterparty_token`, `provision_tokens`, `status`, `recognition`,
     `effective_tick`, `expiry_tick`.
   - `BordersDisputeRow`: `dispute_token`, `domain_token`,
     `counterparty_token`, `contested_location_tokens`, `status`.
   - `BordersPhysicalRow`: `location_token`, `window_start`, `window_end`,
     `actor_count`, `action_count`, `hostile_count`, `assistance_count`,
     `presence_ticks`, `classification`.
   - `BordersPatternRow`: `pattern_token`, `domain_token`, `location_tokens`,
     `pattern`, `physical_actions`, `claim_count`, `agreement_count`,
     `dispute_count`.
   - `BordersOverlapRow`: `left_domain_token`, `right_domain_token`,
     `overlap_location_tokens`, `overlap_count`, `dispute_status`.
   - `BordersLineageRow`: `edge_token`, `parent_token`, `child_token`,
     `kind`, `first_tick`, `last_tick`.
   - `BordersAlignmentRow`: `candidate_token`, `alignment`, `claim_alignment`,
     `agreement_alignment`, `pattern_alignment`, `basis_counts`.
   - `BordersMetricProvenanceRow`: `family`, `algorithm_version`,
     `catalog_version`, `value_keys`.
4. Define `BordersSnapshot` with a required `summary: BordersSummaryRow` and
   every row tuple, sorted by its primary key:
   - candidates by `candidate_token`
   - claims by `(domain_token, owner_token)`
   - recognitions by `(domain_token, basis)`
   - access by `(domain_token, subject_token, mode)`
   - agreements by `(domain_token, agreement_token)`
   - disputes by `(domain_token, dispute_token)`
   - physical by `(location_token, window_start)`
   - patterns by `(domain_token, pattern_token)`
   - overlaps by `(left_domain_token, right_domain_token)`
   - lineage by `(parent_token, child_token, edge_token)`
   - alignment by `candidate_token`
   - provenance by `family`
5. `BordersSnapshot.__post_init__` validates:
   - `summary` is exactly `BordersSummaryRow` and its counts equal the row
     tuple lengths and `candidate_count`;
   - exact types and sorted order;
   - unique primary keys;
   - no duplicate row tokens;
   - every domain reference resolves to a claim row;
   - every lineage parent/child and alignment `candidate_token` resolves to a
     candidate row, except an explicit `emerged` parent or `dissolved` child
     endpoint;
   - row caps;
   - forbidden fields;
   - no raw `AgentId`, `EntityId`, `EventId`, or `RunId` objects in any token
     field (tokens must be bounded strings).
6. Add `empty_borders_snapshot(run_id, publication_id, digest, ...)`.
7. Create `src/simulation/borders_codec.py`:
   - `BORDERS_TOP_LEVEL_KEYS` exact set: `schema_version`, `policy_version`,
     `catalog_version`, `run_id`, `publication_id`, `digest`, `summary`,
     `candidates`, `claims`, `recognitions`, `access_expectations`,
     `agreements`, `disputes`, `physical`, `patterns`, `overlaps`, `lineage`,
     `alignment`, `metric_provenance`.
   - `canonical_borders_payload(snapshot) -> dict` with sorted keys and stable
     row order.
   - `canonical_borders_json(snapshot) -> str` with `sort_keys=True`,
     `separators=(",", ":")`, `ensure_ascii=False`, no whitespace.
   - `borders_snapshot_digest(snapshot) -> str` over the canonical payload
     excluding `digest` and `publication_id` at the top level **and** inside the
     nested `summary` row; `finalize` re-injects both after hashing.
   - `borders_publication_id(digest) -> str` = `bd-pub-` + first 16 hex.
   - `finalize_borders_snapshot(snapshot) -> BordersSnapshot` sets the digest and
     publication id and revalidates.
   - `encode_borders_snapshot`/`decode_borders_snapshot` with exact-key
     rejection and stable round trip.
8. The codec never reads a live engine, cognition ledger, observer frame, or
   another analysis artifact. Decode validates the schema/policy and rejects an
   unknown top-level or row key.

### Required Interfaces and Contracts

```python
BORDERS_SNAPSHOT_SCHEMA: Final[str] = "borders-snapshot-v1"
BORDERS_SNAPSHOT_POLICY: Final[str] = "borders-snapshot.v1"
BORDERS_SNAPSHOT_MAX_BYTES: Final[int] = 4 * 1024 * 1024

def canonical_borders_json(snapshot: BordersSnapshot) -> str: ...
def borders_snapshot_digest(snapshot: BordersSnapshot) -> str: ...
def finalize_borders_snapshot(snapshot: BordersSnapshot) -> BordersSnapshot: ...
def encode_borders_snapshot(snapshot: BordersSnapshot) -> bytes: ...
def decode_borders_snapshot(payload: bytes | str) -> BordersSnapshot: ...
```

- The snapshot is immutable after `finalize`.
- The digest is canonical and independent of process, platform, and input order.
- The publication id is content-addressed.
- No raw ids, free text, frame bodies, or evidence bodies are published.
- `organized-conflict-snapshot-v1`, `diplomacy-snapshot-v1`/`v2`, and their stores
  remain byte-identical.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — four overlays must distinguish physical control,
  subjective claim, agreement, analytical control pattern.
- Source: `.ai-factory/ARCHITECTURE.md` — accepted-set/exact-key-set evolution;
  canonical snapshots.
- Source: `src/simulation/organized_conflict_models.py` 38-383.
- Supported combinations: empty snapshot; one row per family; all rows; duplicate
  key; broken ref; over-cap; forbidden field; non-canonical key; each tested.

### Error Handling and Logging

- Decode rejects unknown keys with `borders_schema_unknown_key`.
- A broken reference raises `ValueError("borders_snapshot_ref:<name>")`.
- A size overflow raises `ValueError("borders_size_limit")`.
- Logs: `INFO borders_snapshot_finalized rows=%s digest_prefix=%s` (prefix only).
- Never log publication ids, row tokens, or row bodies.

### Tests

- `tests/unit/test_borders_snapshot.py`
  - `test_schema_policy_and_caps_are_frozen`
  - `test_summary_is_required_and_counts_match`
  - `test_rows_are_sorted_and_unique`
  - `test_domain_refs_must_resolve`
  - `test_candidate_refs_must_resolve_for_lineage_and_alignment`
  - `test_lineage_refs_must_resolve_or_be_terminal`
  - `test_forbidden_fields_and_raw_ids_are_rejected`
  - `test_empty_and_full_snapshots_validate`
  - `test_existing_snapshots_are_unchanged`
- `tests/unit/test_borders_codec.py`
  - `test_canonical_json_is_stable_across_input_order`
  - `test_digest_excludes_top_level_and_summary_publication_fields`
  - `test_publication_id_is_content_addressed`
  - `test_encode_decode_round_trip`
  - `test_unknown_top_level_and_row_keys_are_rejected`
  - `test_size_limit`
- Commands:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_snapshot.py tests/unit/test_borders_codec.py -q`
- Expected: all pass.

### Acceptance Criteria

- `borders-snapshot-v1` is canonical, bounded, immutable, and exact-key.
- All four layers and their provenance are present.
- No raw ids, forbidden fields, or composite/winner/sovereignty fields exist.
- Existing snapshots are unchanged.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_snapshot.py tests/unit/test_borders_codec.py -q`
- Expected: pass.

## Task 17: Add border ports, cursor purposes, and bounded paging

### Intent

Provide typed read and publication ports and deterministic paging so the API can
serve a committed snapshot without rebuilding analysis or reading memory. Cursors
bind run, publication, digest, purpose, and filters.

### Implementation Steps

1. Create `src/simulation/borders_ports.py`:
   - `BORDERS_CURSOR_PURPOSES = frozenset({"summary", "claims", "claim",
     "agreements", "agreement", "control"})`.
   - `BordersSummary` with run/publication/digest/schema, `candidate_count`,
     claim/agreement/dispute/physical/pattern counts, and coverage.
   - `BordersPublication` with run/publication/digest/schema/summary.
   - `BordersCursor` with `purpose`, `fingerprint`, `after_key`.
   - `borders_query_fingerprint(*, run_id, publication_id, digest, purpose,
     filters)`:
     material = `palimpsest.borders.cursor.v1`, run, publication, digest,
     purpose, sorted `key=value` filters; SHA-256.
   - `borders_cursor_matches(cursor, fingerprint) -> bool`.
   - `bounded_border_detail_rows(rows, cursor, limit)` with the same cap as
     organized conflict.
   - `BordersReadPort` and `BordersPublisherPort` protocols with `read_summary`,
     `read_claims`, `read_claim`, `read_agreements`, `read_agreement`,
     `read_control`, `publish`.
2. Create `src/simulation/borders_paging.py`:
   - `page_border_rows(rows, *, after_key, limit)`:
     - sort by the caller-provided stable key;
     - return `(rows, next_key)` where `next_key` is the last row key or `None`;
     - reject `limit < 1` and `limit > 500`;
     - never mutate the input.
   - `page_border_detail(rows, *, after_key, limit)` caps at
     `BORDERS_MAX_DETAIL_ROWS = 500`.
3. Cursor rules:
   - purpose must be one of the six;
   - fingerprint must be a non-empty bounded string;
   - a changed run/publication/digest/purpose/filter yields no match (400 at the
     API);
   - the codec expiry remains the shared 900-second TTL.
4. No port imports `analysis`, `experiments`, `api`, `persistence`, or
   `observer`.
5. Logs: `DEBUG borders_page purpose=%s rows=%s next=%s` (booleans/counts only).

### Required Interfaces and Contracts

```python
BORDERS_CURSOR_PURPOSES: Final[frozenset[str]] = frozenset(
    {"summary", "claims", "claim", "agreements", "agreement", "control"}
)

@dataclass(frozen=True, slots=True)
class BordersCursor:
    purpose: str
    fingerprint: str
    after_key: str | None = None

def borders_query_fingerprint(...) -> str: ...
def borders_cursor_matches(cursor: BordersCursor, fingerprint: str) -> bool: ...
```

- Six cursor purposes exactly.
- A mismatched binding is never served.
- Paging is deterministic and bounded.
- Ports select typed rows only; they never rebuild analysis.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — read-only overlays for four layers.
- Source: `src/simulation/organized_conflict_ports.py` 27-125 and
  `organized_conflict_paging.py` 22-77.
- Supported combinations: first page, next page, last page, empty page, invalid
  limit, changed filter, changed digest, expired cursor; each tested.

### Error Handling and Logging

- Invalid purpose/limit raises `ValueError("borders_cursor_purpose")` or
  `ValueError("borders_page_limit")`.
- A cursor mismatch returns `False`, never a partial page.
- Logs counts only; never log cursor values, run ids, or publication ids.

### Tests

- `tests/unit/test_borders_ports.py`
  - `test_exactly_six_cursor_purposes`
  - `test_fingerprint_binds_run_publication_digest_purpose_filters`
  - `test_cursor_match_rejects_any_changed_binding`
  - `test_detail_cap`
- `tests/unit/test_borders_paging.py`
  - `test_first_next_last_and_empty_pages`
  - `test_page_limit_bounds_and_invalid_limit`
  - `test_paging_is_stable_and_non_mutating`
  - `test_detail_page_cap`
- Commands:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_ports.py tests/unit/test_borders_paging.py -q`
- Expected: all pass.

### Acceptance Criteria

- Six purposes exist and match the six routes.
- Cursors bind all five dimensions.
- Paging is deterministic and bounded.
- Ports never rebuild analysis or read memory.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_ports.py tests/unit/test_borders_paging.py -q`
- Expected: pass.

## Phase Risks and Mitigations

- Risk: the snapshot becomes a second world state.
  Mitigation: it is a read model with hashed tokens and no world field; Task 16
  rejects raw ids and objective owner/control fields.
- Risk: a cursor reuses a page after a publication change.
  Mitigation: fingerprint binds run/publication/digest/purpose/filters; Task 17
  tests every change.
- Risk: snapshot growth breaks the 4 MiB bound.
  Mitigation: row caps, size limit, and explicit `borders_size_limit`.
- Risk: existing snapshots are rewritten.
  Mitigation: new schema/policy only; existing codecs untouched.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
