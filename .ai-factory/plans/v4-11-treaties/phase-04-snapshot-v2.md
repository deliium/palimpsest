# Phase 4: Diplomacy Snapshot v2

Plan: [index.md](index.md)
Tasks: 15-16
Depends on: Phase 3

## Objective

Add a canonical, bounded `diplomacy-snapshot-v2` that carries treaty anchors,
immutable versions, participant declarations, later-generation recollections,
treaty misrepresentation observations, anchor coverage, version lineage, and
treaty metric provenance. `diplomacy-snapshot-v1` remains decodable and
byte-verifiable so every V4-10 publication remains readable.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/simulation/diplomacy_models.py` | `DIPLOMACY_SNAPSHOT_SCHEMA` 50-54; caps 56-65; row types 224-548; `DiplomacySnapshot` 551-729; `empty_diplomacy_snapshot` | Exact bounded snapshot shape and row validation to extend additively. |
| `src/simulation/diplomacy_codec.py` | `_payload` 93-113; `diplomacy_snapshot_digest` 114-119; `compute_diplomacy_publication_id` 120-130; `finalize_diplomacy_snapshot` 133-173; `encode` 176-185; `_TOP_KEYS`/`_ROW_TYPES` decode 188-239 | Content-addressed publication and strict exact-key decoding. |
| `src/simulation/diplomacy_paging.py` | `DiplomacyRowSelection` 28-32; `select_diplomacy_relations` 61-72; `select_diplomacy_relation` 73-130; `select_diplomacy_instruments` 131-145; `select_diplomacy_instrument` 146-175; `select_diplomacy_lineage` 176-185 | Pure bounded selection patterns for treaty and version pages. |
| `src/simulation/diplomacy_ports.py` | `DiplomacySummary` 72-81; `DiplomacyRelationDetail` 82-88; `DiplomacyInstrumentDetail` 89-95; `DiplomacyCursor` 96-108; query fingerprint 109-156; `bounded_detail_rows` 157-165; read/publisher ports 166-209 | Port shapes, cursor binding, and detail caps. |
| `src/simulation/organization_models.py` | `ORGANIZATION_SNAPSHOT_SCHEMA_VERSION` 68-74; supported tuple | Exact precedent for a current schema plus retained v1/v2 schemas. |
| `src/simulation/organization_codec.py` | 634-645, 820-860 | Exact precedent for version-dispatched decode. |
| `tests/unit/test_diplomacy_snapshot.py` | 160-294 | Round-trip, digest, schema, raw-ID, and historical-schema tests to extend. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/simulation/diplomacy_models.py` | modify | Add schema v1/v2 constants, treaty row types, caps, snapshot fields, and summary/empty helpers. |
| `src/simulation/diplomacy_codec.py` | modify | Add version-specific top keys/row maps, v2 payload, v2 decode, and v1 fallback. |
| `src/simulation/diplomacy_paging.py` | modify | Add treaty and version selection functions. |
| `src/simulation/diplomacy_ports.py` | modify | Add treaty summary/detail ports and treaty cursor purposes. |
| `tests/unit/test_diplomacy_snapshot.py` | modify | Assert v1 remains unchanged and v2 round-trips. |
| `tests/unit/test_diplomacy_treaty_snapshot.py` | create | Treaty rows, caps, digest, foreign refs, raw-ID rejection. |
| `tests/unit/test_diplomacy_treaty_ports.py` | create | Paging, detail caps, cursor binding. |

## Task 15: Define diplomacy-snapshot-v2 and preserve v1 decoding

### Intent

Publish treaty beliefs without changing the V4-10 snapshot contract. V2 is an
additive sibling; v1 stays readable, byte-verifiable, and digest-checked.

### Implementation Steps

1. In `diplomacy_models.py`:
   - Keep `DIPLOMACY_SNAPSHOT_SCHEMA` as the current schema name, but add
     `DIPLOMACY_SNAPSHOT_SCHEMA_VERSION_V1 = "diplomacy-snapshot-v1"` and
     `DIPLOMACY_SNAPSHOT_SCHEMA_VERSION_V2 = "diplomacy-snapshot-v2"`.
   - Set `DIPLOMACY_SNAPSHOT_SCHEMA = DIPLOMACY_SNAPSHOT_SCHEMA_VERSION_V2`.
   - Set `SUPPORTED_DIPLOMACY_SNAPSHOT_SCHEMAS = (V1, V2)`.
   - Add `DIPLOMACY_SNAPSHOT_POLICY_V1 = "diplomacy-snapshot-policy.v1"`
     and `DIPLOMACY_SNAPSHOT_POLICY_V2 = "diplomacy-snapshot-policy.v2"`.
     Set `DIPLOMACY_SNAPSHOT_POLICY = DIPLOMACY_SNAPSHOT_POLICY_V2` so new
     v2 snapshots default to policy v2. The v1 decoder accepts only policy v1
     and the v2 decoder accepts only policy v2.
2. Add caps:
   - `MAX_SNAPSHOT_TREATIES = 8192`
   - `MAX_SNAPSHOT_TREATY_VERSIONS = 32768`
   - `MAX_SNAPSHOT_TREATY_DECLARATIONS = 65536`
   - `MAX_SNAPSHOT_TREATY_RECOLLECTIONS = 32768`
   - `MAX_SNAPSHOT_TREATY_LINEAGE = 32768`
   Keep the existing 4 MiB byte cap.
3. Add row types with exact fields and validation:
   - `DiplomacySnapshotTreatyRow`: `treaty_id`, `relation_id`,
     `owner_token`, `party_tokens`, `subject_kind`, `current_version_id`,
     `status`, `opened_tick`, `last_tick`, `provenance`.
   - `DiplomacySnapshotTreatyVersionRow`: `version_id`, `treaty_id`,
     `owner_token`, `version_index`, `parent_version_ids`, `change_kind`,
     `status`, `acceptance_basis`, `party_tokens`, `provision_kinds`,
     `terms_digest`, `record_refs`, `institutional_memory_refs`,
     `effective_tick`, `end_tick`, `proposer_party_token`,
     `proposer_envoy_token`, `provenance`.
   - `DiplomacySnapshotTreatyDeclarationRow`: `declaration_id`, `treaty_id`,
     `version_id`, `owner_token`, `party_token`, `envoy_token`, `act`,
     `declared_tick`, `provenance`.
   - `DiplomacySnapshotTreatyRecollectionRow`: `recollection_id`,
     `owner_token`, `treaty_ref`, `version_ref`, `subject_kind`, `basis`,
     `stance`, `claimed_terms_digest`, `confidence`, `first_tick`, `last_tick`,
     `provenance`.
   - `DiplomacySnapshotTreatyMisrepresentationRow`: `misrepresentation_id`,
     `version_id`, `owner_token`, `kind`, `observed_tick`, `envoy_token`,
     `party_token`, `provenance`.
   - `DiplomacySnapshotTreatyLineageRow`: `edge_id` (`dip-edge-` prefix),
     `treaty_id`, `from_version_id`, `to_version_id`, `change_kind`, `tick`.
     Derive one row per retained version parent link; the edge is analysis
     output, not a second owner ledger row.
   Every text field is bounded; every token is an agent or party token; every
   record ID uses the correct prefix; every digest is 64 lowercase hex; every
   list is sorted and unique; `status` and `acceptance_basis` are closed
   values derived by the composer, never authority; forbidden fields fail
   `diplomacy_snapshot_forbidden_field`.
4. Extend `DiplomacySnapshot` with defaulted tuple fields:
   `treaties`, `treaty_versions`, `treaty_declarations`,
   `treaty_recollections`, `treaty_misrepresentations`, `treaty_lineage`.
   Keep existing fields and order. Do not add treaty counts to the existing
   `DiplomacySnapshotSummaryRow`; v2 derives counts from rows so v1 summary
   keys stay exact.
5. Update `DiplomacySnapshot.__post_init__` to:
   - accept both policy versions for v1 and only policy v2 for v2;
   - enforce row caps only for v2; v1 rows must be empty;
   - reject a v1 payload carrying treaty rows;
   - enforce v2 cross-references: treaty `current_version_id` resolves,
     version `treaty_id` resolves, declaration version resolves, lineage
     version refs resolve, owner tokens match the row owner, and all
     participant tokens are present in the party token set.
6. Update `empty_diplomacy_snapshot` to emit v2 with empty treaty tuples and
   policy v2 by default; add an explicit `schema_version` parameter so tests
   can build v1.

### Required Interfaces and Contracts

- V1 documents keep their exact top-level keys, row keys, digest algorithm, and
  policy v1; decoding a v1 document yields empty treaty tuples.
- V2 is canonical, bounded, content-addressed, and immutable after
  publication.
- V2 row identities are never raw agent IDs; only hashed tokens and
  content-addressed record IDs.
- `terms_digest` is publishable; free-text terms are not.
- Recollections may reference absent/foreign `treaty_ref`/`version_ref`
  values and remain `unresolved`; they do not fail the snapshot.
- A raw agent ID, free-text subject, or frame body fails closed.
- No treaty row contains a score, truth, legitimacy, enforcement, or
  misremembered field.

### Requirement Evidence (when reconciliation applies)

- `.ai-factory/ARCHITECTURE.md` "Use accepted-set and exact-key-set schema
  evolution" and V4-04/V4-05 organization snapshot v1/v2/v3 precedent.
- Original Request "records, participants, recognized representatives,
  institutional memory, agent beliefs" requires v2 to carry each visible
  dimension.
- V4-10 `diplomacy-snapshot-v1` must remain decodable.

### Error Handling and Logging

- Stable codes: `diplomacy_snapshot_invalid`,
  `diplomacy_snapshot_schema_unknown`, `diplomacy_snapshot_digest_mismatch`,
  `diplomacy_snapshot_foreign_reference`,
  `diplomacy_snapshot_forbidden_field`, `diplomacy_snapshot_size_limit`.
- Log `treaty_snapshot_built schema=diplomacy-snapshot-v2 treaties=%s` at
  DEBUG with counts only.

### Tests

`tests/unit/test_diplomacy_treaty_snapshot.py`:

- Build a v2 snapshot with every treaty row type; round-trip and assert
  digest/publication ID stability.
- Assert v1 bytes from the existing fixture still decode, keep policy v1, and
  yield empty treaty tuples.
- Assert v1 with treaty rows fails; v2 with v1 policy fails; unknown schema
  fails.
- Assert each treaty cap fails closed and the 4 MiB cap fails closed.
- Assert raw agent IDs, free-text subjects, unsorted lists, duplicate IDs,
  foreign refs, and forbidden fields fail.
- Assert `terms_digest` must be 64 lowercase hex.
- Assert treaty/version `status` and `acceptance_basis` are closed values and
  round-trip as derived labels, not authority.
- Assert a recollection with an absent treaty/version still round-trips.

`tests/unit/test_diplomacy_snapshot.py` additions:

- Existing v1 round-trip/digest assertions remain unchanged.
- Add a v2 assertion that the first V4-10 rows are unchanged.

### Acceptance Criteria

- `diplomacy-snapshot-v2` is canonical and bounded.
- `diplomacy-snapshot-v1` remains decodable and byte-verifiable.
- V2 carries every treaty row family with tokens only.
- No raw IDs, free text, frame bodies, scores, or truth fields are published.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_diplomacy_treaty_snapshot.py tests/unit/test_diplomacy_snapshot.py -q`
- Expected: all tests pass.

## Task 16: Add treaty paging ports and cursor purposes

### Intent

Serve treaty and version pages with the same bounded, snapshot-pinned,
purpose-specific cursor contract as V4-10. Cursor reuse must work only when
run, publication, digest, purpose, and filters match.

### Implementation Steps

1. In `diplomacy_paging.py`, add:
   - `select_diplomacy_treaties(snapshot, *, offset, limit)` returning a
     `DiplomacyRowSelection` over `treaties` sorted by
     `(opened_tick, treaty_id)`.
   - `select_diplomacy_treaty(snapshot, treaty_id)` returning the treaty row
     plus its versions, declarations, recollections, misrepresentations, and
     lineage edges, bounded by `MAX_DETAIL_ROWS`.
   - `select_diplomacy_treaty_versions(snapshot, *, treaty_id, offset, limit)`
     for a version-only page if the detail response is too large.
   - `select_diplomacy_treaty_lineage(snapshot, *, offset, limit)` sorted by
     `(tick, edge_id)`.
   Use the existing `_clamp` and `_page` helpers; never mutate the snapshot.
2. In `diplomacy_ports.py`:
   - extend `DiplomacySummary` with `treaty_count`, `treaty_version_count`,
     `treaty_accepted_count`, `treaty_recollection_count`, appending defaults
     so existing keyword and positional constructors remain valid;
   - add `DiplomacyTreatyDetail` with treaty, versions, declarations,
     recollections, misrepresentations, and lineage tuples;
   - add `treaty` and `treaties` to `DIPLOMACY_CURSOR_PURPOSES` exported from
     `diplomacy_models.py`;
   - keep `DiplomacyReadPort` method additions explicit; do not widen the
     publisher port.
3. In `diplomacy_models.py`, extend `DIPLOMACY_CURSOR_PURPOSES` with
   `"treaties"` and `"treaty"` after the existing purposes. Keep order stable.
4. Define query fingerprints for treaty pages using the same
   run/publication/digest/purpose/filter tuple as existing pages. A changed
   treaty filter invalidates the cursor.
5. Bound detail rows to `MAX_DETAIL_ROWS`; if a treaty detail exceeds the cap,
   return the treaty row and versions page plus explicit truncation metadata;
   never silently drop lineage.
6. Keep all selection pure and sorted. No analysis import, no mutation, no
   command construction. Type the new selectors as returning concrete snapshot
   row tuples (or narrow `object` with `cast` at the first read) so strict mypy
   does not see `tuple[object, ...]` field access.

### Required Interfaces and Contracts

- Cursor purposes are exactly the existing six plus `treaties` and `treaty`.
- Cursor binding includes run, publication, digest, purpose, and filters.
- Unknown published treaty/version -> 404; changed binding -> 400; expired
  -> 410 (Task 19 wires HTTP).
- Detail rows are bounded and deterministic.
- A v1 snapshot has no treaty pages and returns an explicit empty/unsupported
  result, not invented rows.

### Requirement Evidence (when reconciliation applies)

- `.ai-factory/ARCHITECTURE.md` "read-only surfaces" and V4-10 cursor
  contract.
- `docs/research-api.md` 242-256 and `src/simulation/diplomacy_ports.py`
  39-164.
- Original Request "Track versions and lineage" requires version and lineage
  pages.

### Error Handling and Logging

- Invalid/oversized page arguments clamp deterministically or fail with
  `diplomacy_snapshot_invalid`; never raise from a read.
- Log `treaty_page_served purpose=<closed> rows=%s` at DEBUG with counts only.

### Tests

`tests/unit/test_diplomacy_treaty_ports.py`:

- Page treaties and versions with offsets/limits; assert stable ordering,
  clamping, and no mutation.
- Detail includes bounded versions/declarations/recollections/lineage.
- Cursor reuse with the same binding works; changed run, publication, digest,
  purpose, or filter fails.
- Expired cursor fails with the existing `diplomacy_cursor_invalid` or
  expiry code.
- V1 snapshot yields no treaty rows and no invention.
- Read ports import no analysis and construct no command.

### Acceptance Criteria

- Treaty pages and details are bounded and deterministic.
- Cursors bind to the publication and filters.
- V1 snapshots remain readable without treaty rows.
- No read path mutates state or imports analysis.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_diplomacy_treaty_ports.py tests/unit/test_diplomacy_ports.py -q`
- Expected: all tests pass.

## Phase Risks and Mitigations

- Risk: V2 changes the v1 digest or key set.
  Mitigation: separate v1/v2 top-key and row-type maps; v1 decode path never
  constructs treaty rows.
- Risk: A treaty detail response grows unbounded.
  Mitigation: per-family caps, `MAX_DETAIL_ROWS`, and explicit truncation
  metadata.
- Risk: Cursors are reused across a different publication.
  Mitigation: bind run, publication, digest, purpose, and filters; test every
  binding change.

## Phase Completion Checklist

- Every Task 15-16 acceptance criterion is met.
- V1 remains byte-verifiable; v2 is canonical and bounded.
- Treaty pages and details are cursor-bound.
- No raw IDs, free text, scores, or truth fields are published.
- `index.md` checkboxes are updated only after verification passes.
