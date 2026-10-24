# Phase 6: Bounded traversal and stable pagination

Plan: [index.md](index.md)  
Tasks: 11–12  
Depends on: Tasks 1–7 and 10

## Objective
Navigate a fixed historical graph with deterministic limits and safe resumable pages, without hiding full-history scans behind pagination.

## Current-Code Evidence

| Path | Symbols | Relevance |
|---|---|---|
| `src/world/kinship.py` | `ancestors_of`, `descendants_of` | Native semantic oracle for small genealogy fixtures, not the generic query implementation. |
| `src/persistence/inspection_sqlalchemy.py` | `load_events_page`, `load_graph_summary_page` | Existing bounded page and explicit continuation conventions. |
| `src/api/persistence_services.py` | `_parse_memory_cursor` | Existing invalid-cursor safe-code pattern; lineage needs stronger snapshot/scope binding. |

## Files to Change
Create `src/simulation/lineage_query.py`, `src/api/lineage_cursor.py`, `tests/unit/test_lineage_traversal.py`, and `tests/unit/test_lineage_pagination.py`. Modify the new models/ports for traversal record metadata and explicit stop reasons.

## Task 11: Implement deterministic cycle-safe neighborhood traversal

### Intent / Implementation Steps
1. Implement async `LineageQueryService(reader).traverse(query, *, session=None)` using only Task 2 indexed reads. With no supplied session, open one budgeted read session covering resolution and traversal; with an API/catalogue-supplied session, reuse it without resetting its counters/cache. Validate scope/root/snapshot before expansion; no runner, replay, whole graph loader or analysis callback. The API must not resolve a snapshot with one budget and start traversal with a fresh one.
2. BFS uses frontier ordered by `(depth, node_key)`; read canonical adjacency in native edge-key order. For `ancestors`, follow incoming edges; for `descendants`, outgoing; for `both`, incoming then outgoing, deduplicating by edge identity. Never reverse the serialized native edge endpoints.
3. Maintain visited node keys and admitted edge keys, with explicit depth/node/edge/read/byte counters. Root counts as one visited node at depth zero. Cycles, diamonds, repeated references and parallel edges terminate deterministically. Admit an edge only if both endpoint descriptors fit budgets; otherwise record the stop reason without dangling output.
4. Process adjacency pages through the session continuation and verified-file cache. The filesystem adapter calls the shared `LineageReadBudget` before each head/manifest/index/page/descriptor read; the core consumes its counters and must not estimate physical work from method-call count. No adjacency or full graph is loaded before applying limits. On deterministic budget exhaustion after a validated root, return the validated prefix with partial traversal status. If the budget cannot resolve/validate the snapshot or root, return unavailable with `lineage_source_budget`; do not fabricate root presence or absence. Use the same budget for depth-limit look-ahead probes.
5. Produce an internal canonical record stream: root-discovery record, subsequent node-discovery records and admitted edge records in traversal order. A graph-record page contains at most `page_size` records; translate it into deduplicated node/edge DTO lists. Include endpoint descriptors as context when an edge crosses pages. Root and isolated nodes therefore have pageable representation too.
6. `living_only` marks only known-living genealogy agent nodes as matches; dead/unknown nodes can still be traversed and returned as `context_only` endpoint descriptors. Include `matched_node_keys` so context is never mistaken for a living answer. Root remains an envelope reference. With filter off all eligible discovered nodes match.
7. Return independent source coverage and traversal completeness. Reasons include `depth_limit`, `node_limit`, `edge_limit`, `source_read_limit`, `source_byte_limit`, `source_pruned`, `unresolved_parent`. No next cursor can bypass graph-selection ceilings; clients re-root to explore beyond the selected neighborhood.

### Required Interfaces and Contracts
Pure graph selection is deterministic for a pinned publication, query and budgets. `max_depth=0` returns root only. Finite cycles in testimony/claims are valid navigable data; do not force all families into a DAG. Depth exhaustion is reported only when evidenced unexpanded adjacency exists, not when a leaf happens to sit at the limit.

### Requirement Evidence
User bounded/paginated traversal and living-descendant question; native genealogy depth ceiling; unresolved provenance contracts. Task 2 hard budgets are authoritative.

### Error Handling and Logging
Unavailable root source returns unavailable with coverage; proven missing root is distinct. Corrupt indexed file aborts safely rather than returning a budget-prefix as trusted data. Cancellation propagates. Log query family/class, counters and stop codes, not root content IDs, full queries or file names.

### Tests / Acceptance / Verification
`test_lineage_traversal.py`: chain, diamond, split/merge, cycle, self-reference, parallel evidence, leaf at limit, depth zero, dead intermediate ancestor, unknown living state, missing-parent stub, read/byte budget at every boundary, huge-degree lazy session, deterministic order under randomized insertion. Include a real filesystem session whose single `neighbors` call reads an integrity index plus several pages; prove each read is charged and oversized files are refused before reading. Assert supplied-session counters include prior snapshot/root lookup, and budget exhaustion before root validation is unavailable rather than an empty graph/404. Hypothesis compares bounded traversal with a small in-memory oracle and asserts no dangling endpoints and no duplicate edge identities.

Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_lineage_traversal.py --cov=simulation --cov-report=term-missing -q`. Acceptance: all budgets are observed in source reads as well as returned output.

## Task 12: Bind opaque continuation to snapshot, query and authorization scope

### Intent / Implementation Steps
1. Implement `api.lineage_cursor.LineageCursorCodec` using versioned canonical JSON, URL-safe base64 and HMAC-SHA256 with constant-time verification. All payloads carry version, purpose, run/family/class/owner, issued/expiry times, page-size/effective-filter fingerprint and committed run reference. Define exact discriminated field sets:
   - `traverse`: immutable snapshot ref/digest, root key, full effective query fingerprint including budgets/living filter, and next graph-record offset.
   - `nodes`: immutable snapshot ref/digest, native-kind/ID filter fingerprint, and last qualified node key; no root or traversal offset.
   - `snapshots`: pinned run-commit/scope-catalogue generation and last `(boundary_tick, publication_id)` key; no graph snapshot/root/record offset.
   Tokens are at most 4 KiB and expire after 15 minutes. Reject unknown/missing purpose-specific fields. Bound base64 input and verify MAC before JSON decoding; the payload decoder rejects duplicate keys, depth above 32, nonfinite values, invalid UTF-8 and trailing/scalar JSON just like artifact decoding. Clock fields and offsets are exact nonnegative integers, not bools.
2. Inject operational clock and signing key at API composition. An optional `PALIMPSEST_LINEAGE_CURSOR_KEY` secret of at least 32 UTF-8 bytes supports multi-worker/restart continuity; otherwise generate an in-process key using infrastructure-side cryptographic randomness. It must never be a domain seed or derived from credentials. Process-key rotation invalidates cursors; clients restart from the qualified root.
3. Authenticate each page request before cursor parsing/source access. Revalidate current authorization and compare scope/query fingerprint exactly. A cursor is not a credential. No token can switch owner, run, evidence class or graph family.
4. Traversal continuations rerun bounded deterministic selection against the same committed snapshot and validate the signed offset against the actual bounded stream before slicing. Do not silently clamp negative/out-of-range offsets or return a different graph when budgets truncate selection. Node and snapshot catalogue continuations resume their own keyset pages against the pinned snapshot or run-catalogue generation; they do not rerun graph traversal or resolve latest first. This trades bounded repeated traversal work for no unbounded server sessions/frontier tokens. A moving run head cannot shift any purpose's pages; removed/corrupt source is never silently replaced.
5. Apply the 1-MiB response ceiling to the complete encoded envelope, including coverage, endpoint descriptors and the actual next cursor, not only graph records. Advance continuation only for fully included records. Oversized individual descriptors fail publication earlier; valid nonempty pages must make progress. Graph limits are independent of response-byte pagination. Node/snapshot catalogue cursors bind their native filters and last key, so changing kind/ID/page size on a later request is rejected.

### Required Interfaces and Contracts
Page size counts canonical graph records, not raw edges; default 100, max 200. Document this consistently in DTOs/OpenAPI. Node and snapshot catalogue cursors use the same signer with separate purpose. Changing query parameters during paging is invalid even if a source would accept them. Publication retention is operator-controlled; API never evicts snapshots to manage cursor TTL.

### Error Handling and Logging
Malformed/oversized/bad-signature/scope-mismatched token: `invalid_lineage_cursor` (400). Valid expired token or missing pinned publication: `lineage_cursor_expired` / `lineage_snapshot_gone` (410). Corrupt publication: 503 with safe code. Do not log tokens, signatures, signing keys, fingerprints or raw decode errors.

### Tests / Acceptance / Verification
`test_lineage_pagination.py`: union of traversal pages equals the bounded oracle; no skipped discovery records; context repeats allowed; page sizes 1/200; isolated root; moving latest; exact scope/filter mismatch; cross-purpose use; tamper/expiry/rotation; header reauthentication; source deletion/corruption; full-envelope byte-triggered continuation; graph limits cannot be bypassed. Add separate node and snapshot catalogue cursor tests (without fake root/snapshot fields), stable catalogue append during pagination, native-kind/ID filtering, malformed signed offsets/keys and signed duplicate/deep JSON payloads produced by a test signer. No decode/validation error may expose token bytes or exception text.

Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_lineage_pagination.py tests/unit/test_lineage_traversal.py --cov=simulation --cov=api --cov-report=term-missing -q`. Acceptance: bounded, stable continuation never broadens access or explores beyond selection caps.

## Phase Risks and Mitigations
- Pagination confused with unlimited traversal: separate graph selection limits, response pages and explicit reroot behavior.
- Cursor replay after permissions change: authenticate every page; signer proves integrity only.

## Phase Completion Checklist
- Oracle/property tests, source-read bounds and all cursor cases pass; update `index.md` only.
