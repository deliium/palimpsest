# Phase 2: Backend-only participant and knowledge evidence

Plan: [index.md](index.md)  
Tasks: 4–5  
Depends on: none; integrate with Phase 1 cursor semantics

## Objective

Make teachers, students and transmitted-content records navigable using captured backend projections, including learner-side discovery that existing mentorship graph edges do not provide.

## Current-Code Evidence

| Path | Symbols / section | Why it matters |
|---|---|---|
| `src/simulation/lineage_subjective.py` | `_project_mentorship` | Teacher points to entry; learner is ensured as a node but not connected to entry. Traversing a learner root alone cannot discover teachers reliably. |
| `src/simulation/lineage_models.py` | `MentorshipLineageRecord` | Already captured safe owner/teacher/learner/content identity, counts, confidence, roots and evidence; excludes text/fingerprints. |
| `src/api/routes/lineage.py` | `_node_out`, `lineage_nodes`, `lineage_traverse` | HTTP omits the native mentorship record; existing routes are strict, bounded and capability scoped. |
| `src/api/lineage_service.py` | `LineageApiService`, `ArtifactLineageApiService.nodes`, `_read_port` | One bounded read session and neutral ports; do not bypass filesystem reader validation. |
| `src/api/lineage_cursor.py` | `_PURPOSE_KEYS`, `LineageCursorPayload`, `LineageCursorCodec` | Purpose-specific signed continuation, 15-minute expiry. |
| `src/persistence/lineage_filesystem.py` | `node_page` | Existing early stop counts nodes before applying `after`; a450-node publication reproduced200+56 rows followed by false exhaustion. Participant scans require fixing this reader path. |
| `docs/lineage-explorer.md` | Authority, Capture, HTTP | Capture default off; exact boundaries; subjective/analytical require debug. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/simulation/lineage_participants.py` | create | Pure filtering and card projection of native mentorship records. |
| `src/api/lineage_participant_schemas.py` | create | Strict independent participant page schema. |
| `src/api/lineage_service.py` | modify | Bounded participant scan method over existing node catalogue. |
| `src/api/lineage_cursor.py` | modify | New purpose with snapshot/filter binding, preserving old purposes. |
| `src/api/routes/lineage.py` | modify | GET-only mentorship participant route. |
| `src/persistence/lineage_filesystem.py` | modify | Correct native node catalogue keyset pagination without changing captured artifact formats. |
| `tests/unit/test_lineage_participants.py` | create | Pure projection and read-budget tests. |
| `tests/unit/test_lineage_participant_api.py` | create | Auth, scoped scan, cursors and availability. |
| `tests/unit/test_lineage_pagination.py` | modify | Cross-purpose rejection. |
| `tests/unit/test_lineage_filesystem.py` | modify | Multi-physical-page catalogue completeness and budget regression. |

## Task 4: Project captured teacher–learner–content participant records

### Intent

The backend, not Godot, identifies teachers/students and distinguishes attempts from learning evidence. Avoid rewriting sealed captures to add learner edges or inferring teaching from delivered speech.

### Implementation Steps

1. Create frozen `LineageParticipantCard` and `project_participant_card(node, *, agent_id, role)` in `src/simulation/lineage_participants.py`. Only nodes with `mentorship_record` qualify; accept `role="teacher"|"learner"|"both"` and match the explicit teacher/learner fields. Return no card for unrelated/metadata-absent nodes.
2. Card fields: original qualified node `ref`, `teacher_id`, `learner_id`, `owner_id`, `lineage_id`, `root_id`, `parent_ids`, `content_kind`, opaque `content_key`, `hop`, acquisition/update ticks, attempts, learning-evidence count, confidence band, mutation flag, native status, evidence references, policy version, observed/source-observed boundaries, and `learning_state` (`attempt_only` when evidence count zero, otherwise `learning_evidence`). Copy, do not recalculate scientific claims.
3. Keep analytical versus subjective identity from node scope; do not replace `identity_owner`, merge same IDs across owners, normalize conflicting claims, or call a teacher authoritative. Analytical cards remain analytical evidence and need debug.
4. Add a pure ordering helper for a displayed page: learning-evidence count descending, attempts descending, acquisition tick ascending, qualified node key ascending. This is a disclosed evidence-priority ordering **within retrieved records**, not global cultural importance or causal influence. Include attempted-only records in a separate group.

### Required Interfaces and Contracts

The content key is an opaque captured identifier, not a natural-language explanation or guaranteed practical-knowledge entry ID. A card links to its own mentorship node/root. Never create a cross-family knowledge edge from equal labels/content keys. Knowledge-family exploration uses server-returned native node identities through existing `nodes`/`traverse` APIs.

No new stored artifact schema, graph edge, capability, cognition state, metric, prompt, or objective event. Existing `LineageNodeOut` and `lineage-graph-page-v1` stay unchanged.

### Requirement Evidence

User request — teachers, students, important transmitted knowledge, all lineage from backend APIs. `docs/lineage-explorer.md` — qualified identity, unavailable history, evidence classes. `MentorshipLineageRecord` documents safe native metadata.

### Error Handling and Logging

Unknown role and mismatched family/scope fail closed. Metadata-absent nodes are counted as unprojectable, never turned into zero-learning records. DEBUG only scanned/matched/unprojectable counts; no content keys, record bodies, beliefs or credentials in logs.

### Tests

Teacher-side and learner-side matching; attempt-only versus evidence-positive; teacher/learner same agent; repeated local IDs in two owners; analytical owner provenance; empty/archived/unresolved records; deterministic ordering ties; absent metadata. Assert no mutation and no text/fingerprint field in card contract.

### Acceptance Criteria and Verification

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_lineage_participants.py tests/unit/test_lineage_subjective_sources.py -q`

Expected: explicit native participants are preserved, learner discovery needs no graph inference, and no raw content is exposed.

## Task 5: Add a bounded, snapshot-pinned participant query API

### Intent

Permit direct discovery for a selected teacher or learner without loading a whole lineage archive or broadening an owner's scope.

### Implementation Steps

1. First correct `_FilesystemReadSession.node_page` in `src/persistence/lineage_filesystem.py`: walk verified catalogue pages in canonical key order, apply `node.key > after` before counting eligible output, and gather at least `limit+1` eligible records (or establish true exhaustion) before deciding continuation. Do not stop after reading `limit` total pre-filter records. Preserve publication/digest verification and the request's physical-read/source-byte budget; exhaustion of that budget raises the existing source-budget error, never a complete empty page. Preserve legacy schema IDs and do not add a new index artifact. Do not treat `declared_count` of a bounded native read as a proven global matching-participant total. Add a450-node real-publisher regression walking pages of200, expecting200/200/50 and all450 distinct keys; repeat with page sizes100/256 and after keys beyond the first physical page.
2. Add GET `/v1/simulations/{run_id}/lineage/mentorship/participants`. Parameters: required `evidence_class` (`subjective` or `analytical`), `agent_id`; optional `owner_id` (required for subjective), `role` default both, `boundary_tick`, opaque `after`, and `limit` default100/max200. Reject unknown/duplicate parameters and other evidence classes. Authorize before opening any reader.
3. Add `participants` to `LineageApiService` and implement in `ArtifactLineageApiService` using one `open_read` session and `LineageReadBudget.for_query()`. Resolve the exact snapshot or use its pinned continuation reference. Walk the corrected node catalogue in canonical key order; examine at most200 candidate nodes per HTTP request and stop earlier after `limit` matching cards. Native read lookahead does not create another candidate match or get exposed as scanned. Physical reads remain independently charged. Use no filesystem enumeration, live ledger, analysis import, cross-owner search, or repeated unbounded `get_node` calls.
4. Continuation position is the last **examined** node key, not last matched card. When the200-candidate scan limit ends with no matches but verified further nodes exist, return empty items with continuation and `scan_limited=true`; this is not complete absence of teachers/students. Physical-byte/read-budget failure remains an error, not a fabricated continuation. Detect non-progressing catalogue continuation and fail with a safe corruption/budget code.
5. Extend cursor codec with purpose `participants`, snapshot ID/digest/boundary, filter fingerprint (agent, role, page size), last scanned node key. Preserve exact legacy purpose keysets and validation. Bind scope/run/owner/family/evidence; reject use on `nodes`, `snapshots`, or `traverse` and vice versa. TTL remains15 minutes. On continuation compare the signed publication ID/digest as well as boundary; a replacement publication at the same boundary must never receive an old cursor.
6. New strict `lineage-participants-v1` envelope: snapshot, requested/captured boundary, scope/evidence/owner, agent/role, items, scanned count, unprojectable count, `scan_limited`, coverage, next cursor and effective page size. Reuse existing availability envelope on explicit uncaptured boundary; honor byte ceiling over the complete response including cards.
7. Preserve existing errors: disabled503, forbidden debug403, unknown run404, initial missing exact snapshot availability response, expired/gone continuation410, corrupt/oversize/budget failures safe503. Header `Cache-Control: no-store`. No API read creates capture or repairs files.

### Required Interfaces and Contracts

Only mentorship receives the participant route. Genealogy and knowledge continue to use the existing eight-family APIs. Subjective queries require explicit owner and show only that owner's view; selecting a student is not permission to query every teacher's ledger. The UI can offer an explicit analytical scope only when debug is authorized.

The scan budget bounds backend work, while `limit` bounds returned cards. Completion requires exhausted catalogue plus suitable coverage; `coverage.partial`, unresolved nodes, unprojectable records and scan continuation remain visible. Sorting a page must not change continuation position.

### Requirement Evidence

User request — backend-only lineage. `docs/lineage-explorer.md` — scope, budgets, signed cursors, partial coverage. Architecture — API excludes analysis and GET-only observer authority.

### Error Handling and Logging

INFO route template/status/scanned/matched counts/duration; DEBUG scope class, boundary, limit and reason codes. Do not log tokens, cursor strings, content IDs, whole URLs or returned participant records. Authorization failures cannot reveal restricted counts or roots.

### Tests

Publish real native mentorship records through the existing filesystem publisher fixtures, then query via ASGI. Cover both participant roles, owner isolation, analytical access, more than400 nonmatching nodes before a match in a later physical page, empty intermediate pages with cursor, exact exhaustion, repeated local IDs, tampered/scope-changed/role-changed/cross-purpose cursors, same-boundary publication replacement, expiry/gone snapshot, disabled service, future/missing boundary, physical-budget exhaustion, corrupt metadata and response byte ceiling. Assert reads leave publications/journal unchanged.

### Acceptance Criteria and Verification

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_lineage_participants.py tests/unit/test_lineage_participant_api.py tests/unit/test_lineage_filesystem.py tests/unit/test_lineage_api.py tests/unit/test_lineage_pagination.py tests/architecture/test_lineage_explorer_boundaries.py -q`

Expected: all pages remain on one publication; learner-side records are discoverable without new captured edges; existing endpoints retain their schemas and cursor behavior.

## Phase Risks and Mitigations

- Captured graphs do not connect every learner: query native records through a bounded backend scan, not client graph repair.
- Large nonmatching scopes produce sparse pages: expose scan continuation and explicit Load more; never report global absence prematurely.
- Important knowledge is underspecified scientifically: disclose the evidence-based page ordering and expose exact content provenance, not an invented importance score.

## Phase Completion Checklist

- Participant DTO, service, cursor and route tests pass.
- Existing capture artifacts and eight-family contracts remain readable unchanged.
- Update only `index.md` progress.
