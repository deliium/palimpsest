# Phase 4: Evidence-Testimony Snapshot v1

Plan: [index.md](index.md)
Tasks: 14-15
Depends on: Phase 3 / Task 13

## Objective

Define the independent canonical `evidence-testimony-snapshot-v1` document and
its strict codec, then add bounded paging, read/publication ports, and
purpose-bound cursor matching. Existing dispute, organization, and formal-rule
snapshots must remain byte-verifiable and unchanged.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/simulation/dispute_models.py` | schema/policy 16-18; prefixes 20-25; bounds 27-40; error codes 56-75; derivation 396-550; records 608-1117; snapshot 1119-1418 | Canonical record and snapshot precedent |
| `src/simulation/dispute_codec.py` | key sets 57-261; canonical value encoding 285-332; encode 630-662; publication id 665-681; decode 717-950 | Strict codec and digest rules |
| `src/simulation/dispute_paging.py` | `DisputeRowSelection` 30-45; `_select` 65-105; selectors 108-177 | Offset/limit/byte-budget paging |
| `src/simulation/dispute_ports.py` | cursor purposes 50-57; publication/summary/detail/cursor 72-213; protocols 216-263; fingerprint/match 266-308 | Port and cursor contract |
| `src/simulation/formal_rule_models.py` | `FORMAL_RULE_SNAPSHOT_SCHEMA` | Independent snapshot precedent |
| `tests/unit/test_dispute_snapshot.py` | round-trip and digest tests | Test shape |
| `tests/unit/test_dispute_ports.py` | paging and cursor tests | Test shape |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/simulation/evidence_testimony_models.py` | create | Schema, bounds, records, snapshot, validation |
| `src/simulation/evidence_testimony_codec.py` | create | Exact key sets, canonical encode/decode, digest, publication id |
| `src/simulation/evidence_testimony_paging.py` | create | Row selection and four selectors |
| `src/simulation/evidence_testimony_ports.py` | create | Publication, summary, detail, cursor, protocols, fingerprint |
| `tests/unit/test_evidence_testimony_snapshot.py` | create | Records, bounds, canonical round-trip, digest mismatch |
| `tests/unit/test_evidence_testimony_ports.py` | create | Paging limits, cursor binding, detail caps |

## Task 14: Define evidence-testimony-snapshot-v1 and its codec

### Intent

Publish one bounded immutable analytical document per run. The document is a
new sibling schema; it does not widen or reinterpret any existing snapshot.

### Implementation Steps

1. Create `src/simulation/evidence_testimony_models.py`:
   - `EVIDENCE_TESTIMONY_SNAPSHOT_SCHEMA = "evidence-testimony-snapshot-v1"`
   - `EVIDENCE_TESTIMONY_SNAPSHOT_POLICY_VERSION = "evidence-testimony-analysis.v1"`
   - supported schema tuple containing exactly the v1 schema.
   - analytical prefixes `evid-`, `evid-item-`, `evid-edge-`, `evid-pub-`.
   - Bounds: 4 MiB snapshot; 2048 candidates; 8192 sources; 8192 testimony;
     16384 items; 16384 custody links; 8192 contradictions; 16384 evaluations;
     512 windows; 4096 objective rows; 64 items per candidate; 32 contradictions
     per candidate; 2 MiB per response page; 500 page limit.
   - `EVIDENCE_TESTIMONY_ARTIFACT_ERROR_CODES`:
     `evidence_testimony_invalid_snapshot`,
     `evidence_testimony_digest_mismatch`, `evidence_testimony_size_limit`,
     `evidence_testimony_not_found`, `evidence_testimony_publication_exists`.
   - `EVIDENCE_TESTIMONY_PORT_ERROR_CODES`:
     `evidence_testimony_not_found`, `evidence_testimony_cursor_invalid`,
     `evidence_testimony_cursor_expired`, `evidence_testimony_disabled`,
     `evidence_testimony_size_limit`.
   - Owner-local/foreign token guards.
   - Content-addressed derivation helpers mirroring analysis row ids.
   - `EvidenceTestimonySnapshotRef`, `EvidenceTestimonyCoverage`.
2. Add frozen records: `EvidenceSourceRecord` (including the opaque
   `correlation_token`), `EvidenceTestimonyRecord`, `EvidenceItemRecord`,
   `EvidenceCustodyRecord`, `EvidenceContradictionRecord`,
   `EvidenceEvaluationRecord`, `EvidenceCandidateRecord`,
   `EvidenceObjectiveRow`, `EvidenceWindowRecord`,
   `EvidenceLineageEdgeRecord`, `EvidenceTestimonyCounts`.
3. Add `EvidenceTestimonySnapshot` with ordered tables, `snapshot_digest`,
   `publication_id`, `run_id`, `generated_tick`, policy/schema versions, and
   counts. Validate:
   - sorted tables and unique ids;
   - cross-table references;
   - items per candidate ≤ 64 and contradictions per candidate ≤ 32;
   - unique objective ticks and window bounds;
   - acyclic lineage;
   - absence of owner ids in objective/analytical records and absence of
     `evid-` ids in owner records;
   - no forbidden result field.
4. Add `empty_evidence_testimony_snapshot(run_id, *, generated_tick)`.
5. Create `src/simulation/evidence_testimony_codec.py`:
   - exact top-level key set and exact per-table key sets;
   - canonical JSON: sorted keys, compact separators, `allow_nan=False`;
   - strict decode rejects duplicate keys, NaN/Infinity, unknown fields, and
     missing fields;
   - `evidence_testimony_snapshot_digest` excludes the digest field itself;
   - `finalize_evidence_testimony_snapshot` sets digest and publication id;
   - `compute_evidence_testimony_publication_id` substitutes publication
     placeholders to stay non-circular;
   - `decode_evidence_testimony_snapshot` verifies the embedded digest and
     byte-for-byte re-encoding.

### Required Interfaces and Contracts

- The snapshot contains no owner id, witness id, token value, confidence value
  beyond a closed band, or free text.
- `publication_id` is `evid-pub-` + 16 hex; snapshot digest is 64 hex.
- Decoding unknown schemas fails closed; v1 only.
- Dispute/formal-rule/organization codecs are untouched.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "Use accepted-set and exact-key-set schema
  evolution"; "Versioned Extension Contract" requirement 1.
- `src/simulation/dispute_models.py` 16-40, 1119-1418;
  `src/simulation/dispute_codec.py` 57-332, 630-950.

### Error Handling and Logging

- Construction errors raise `EvidenceTestimonyArtifactError` with safe codes.
- WARN `evidence_testimony_snapshot_bounded candidates=%s sources=%s` (counts
  only).
- Never log row content, ids, tokens, or payload bytes.

### Tests

- Create `tests/unit/test_evidence_testimony_snapshot.py`:
  - an empty snapshot encodes/decodes byte-identically;
  - every record rejects an unknown/forbidden field;
  - duplicate ids, dangling refs, >64 items per candidate, and cyclic lineage
    fail;
  - over-budget tables truncate only via the documented constructors or raise
    `evidence_testimony_size_limit` (no silent partial snapshot);
  - a mutated payload fails `evidence_testimony_digest_mismatch`;
  - dispute/organization/formal-rule snapshot fixtures still decode.
- Command: `uv run pytest tests/unit/test_evidence_testimony_snapshot.py -q`.

### Acceptance Criteria

- `evidence-testimony-snapshot-v1` is canonical and independent.
- Existing snapshots are byte-identical after the change.

### Verification

- `uv run pytest tests/unit/test_evidence_testimony_snapshot.py tests/unit/test_dispute_snapshot.py tests/unit/test_formal_rule_snapshot.py -q`
- Expected: pass.

## Task 15: Add paging, read ports, and cursor support

### Intent

Offer the same bounded read shape as other V4 contexts: run-scoped publication,
offset/limit/byte-budget paging, and cursors bound to run, publication, digest,
purpose, and filter.

### Implementation Steps

1. Create `src/simulation/evidence_testimony_paging.py`:
   - `EvidenceTestimonyRowSelection` with `rows`, `offset`, `next_offset`,
     `truncated`.
   - `_select(rows, offset, limit, byte_budget)` validates non-negative offset,
     clamps limit to 500 and bytes to 2 MiB, fails `evidence_testimony_size_limit`
     when one row exceeds the budget.
   - Selectors: `select_evidence_candidates`, `select_evidence_sources`,
     `select_evidence_contradictions`, `select_evidence_lineage`.
2. Create `src/simulation/evidence_testimony_ports.py`:
   - `EVIDENCE_TESTIMONY_CURSOR_PURPOSES = ("summary", "candidates",
     "candidate", "sources", "contradictions", "lineage")`.
   - `MAX_CANDIDATE_DETAIL_ROWS = 500`.
   - `EvidenceTestimonyPublication(run_id, publication_id, snapshot_digest,
     payload, generated_tick)`.
   - `EvidenceTestimonySummary(run_id, publication_id, snapshot_digest,
     generated_tick, candidate_count, source_count, testimony_count,
     item_count, custody_link_count, contradiction_count, evaluation_count,
     edge_count, coverage, schema_version, window_count, provenance_code)`.
   - `EvidenceTestimonyCandidateDetail` with candidate fields, bounded sources,
     bounded contradictions, custody status counts, and `truncated` flags.
   - `EvidenceTestimonyCursor(purpose, run_id, publication_id, snapshot_digest,
     offset, query_fingerprint)`.
   - Protocols `EvidenceTestimonyReadPort` (summary/candidates/candidate/sources/
     contradictions/lineage) and `EvidenceTestimonyPublicationPort`.
   - `evidence_testimony_query_fingerprint`, `evidence_testimony_cursor_matches`,
     `require_known_evidence_candidate`.
   - Cursor mismatch or expiry raises the port error code; the API maps codes to
     status codes later.
3. Do not import `api`, `analysis`, `experiments`, or `persistence` here.

### Required Interfaces and Contracts

- Cursor purposes are exactly six and stable.
- A cursor never authorizes a different run, publication, digest, purpose, or
  filter.
- Detail pages cap each related row set at 500 and set `truncated=True` rather
  than exceeding the byte budget.

### Requirement Evidence

- `src/simulation/dispute_ports.py` 50-308; `src/simulation/dispute_paging.py`
  30-177.
- `docs/research-api.md` cursor semantics.

### Error Handling and Logging

- Invalid cursors raise `evidence_testimony_cursor_invalid`; expired cursors are
  detected by the API codec as `evidence_testimony_cursor_expired`.
- DEBUG `evidence_page purpose=%s offset=%s returned=%s truncated=%s` (counts
  only).

### Tests

- Create `tests/unit/test_evidence_testimony_ports.py`:
  - limit clamps at 500;
  - a single row over 2 MiB raises `evidence_testimony_size_limit`;
  - `next_offset` is correct on the last and non-last pages;
  - a cursor matches only the same run/publication/digest/purpose/filter;
  - unknown candidates fail closed;
  - detail caps and truncation flags are set;
  - cursor purposes are exactly six.
- Command: `uv run pytest tests/unit/test_evidence_testimony_ports.py -q`.

### Acceptance Criteria

- Paging is deterministic and bounded.
- Cursor binding is complete and refuses every mismatch.

### Verification

- `uv run pytest tests/unit/test_evidence_testimony_ports.py -q`
- Expected: pass.

## Phase Risks and Mitigations

- Risk: accidental schema widening of the dispute snapshot.
  Mitigation: separate modules, separate schema constant, and regression tests
  that decode existing snapshots.
- Risk: unbounded pages or detail payloads.
  Mitigation: byte budget, 500-row cap, explicit truncation flags.
- Risk: cursor purpose drift.
  Mitigation: exact six-element tuple asserted in Task 15 and Task 20.

## Phase Completion Checklist

- Every Task 14-15 in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
