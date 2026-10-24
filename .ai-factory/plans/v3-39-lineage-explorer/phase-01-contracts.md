# Phase 1: Query contracts and evidence boundaries

Plan: [index.md](index.md)  
Tasks: 1–2  
Depends on: none

## Objective
Define a framework-free, client-neutral historical lineage protocol before implementing adapters.

## Current-Code Evidence

| Path | Symbols / sections | Relevance |
|---|---|---|
| `src/simulation/debugger_lineage.py` | `DebuggerLineageEntry`, `DebuggerLineageResponse` | Existing closed, metadata-only lineage DTO pattern; not a paginated graph. |
| `src/simulation/inspection.py` | `InspectionAvailability`, `EventKeysetCursor` | Explicit availability and detached inspection conventions. |
| `.ai-factory/ARCHITECTURE.md` | Dependency Rules; Versioned Extension Contract | API/simulation cannot import analysis; historical artifacts are not objective authority. |

## Files to Change

Create `src/simulation/lineage_models.py`, `src/simulation/lineage_ports.py`, `src/simulation/lineage_identity.py`, and `tests/unit/test_lineage_contracts.py`. Modify `src/simulation/__init__.py` only for intentional public exports; new public submodules declare `__all__`.

## Task 1: Define qualified identities and closed graph DTOs

### Intent
Prevent local ID collisions and preserve the difference between objective facts, private claims, and detached research inference.

### Implementation Steps
1. Introduce frozen, defensively detached dataclasses: `LineageNodeRef`, `LineageNode`, `LineageEdge`, `LineageEvidenceRef`, `LineageScope`, `LineageSnapshotRef`, `LineageCoverage`, `LineageQuery`, `LineagePage`, and `LineageError(code)`.
2. Define exactly eight `LineageFamily` values: `genealogy`, `mentorship`, `technology`, `knowledge`, `record`, `narrative`, `institution`, `office_succession`. Define evidence classes `objective`, `subjective`, `analytical`.
3. Node identity is the tuple `(run_id, family, evidence_class, identity_owner, native_kind, native_id)`. Serialize a structured reference plus a deterministic SHA-256 key of canonical JSON of that tuple. Define identity ownership by kind: objective agent/artifact references have no owner; all subjective nodes/references are namespaced to the selected owner; analytical owner-local entries/variants/episodes retain their source owner, while analytical agent/event reference nodes have no owner. Thus one analytical Bob reference can be both teacher and learner without merging Bob's private entries with another owner's. The analytical query's absent owner selector does not forbid owner-qualified entry nodes. Preserve `claim_owner_id` on analytical edges separately from endpoint identity. Do not concatenate ambiguous delimiters or use Python `hash()`. Edge identity includes its relation, source/target keys, claim owner where applicable, and native evidence identity; preserve parallel edges with distinct evidence.
4. Allow only typed metadata fields: source/observation ticks, native revision/policy IDs, agent/artifact IDs, relation/status codes, bounded counts, nullable native confidence, explicit unresolved reason, and source references. No generic arbitrary attribute dictionary. Native opaque content keys can be references, never labels or log fields. No narrative, utterance, proposition, artifact-mark, prompt, or memory text.
5. Define node states `observed`, `archived`, `unresolved`; an archived node is retained evidence, not proof of death, forgetting, or institutional collapse. `living` is nullable and meaningful only for an agent at the snapshot boundary.
6. Define `MentorshipLineageRecord` as the safe metadata input shared by owner projection and detached analysis: owner, teacher/learner IDs, lineage/root/parent IDs, content kind/key, hop, acquisition/update ticks, attempts, learning-evidence count, confidence band, mutation flag, bounded evidence refs, policy version and observed boundary. Exclude `content_fingerprint`. Store this typed record on the corresponding captured entry node; do not attempt to reconstruct it from `MentorshipAudit` summaries. Add per-record `source_observed_boundary`, native status and source revision metadata for deterministic retention merges.

### Required Interfaces and Contracts
- `LineageQuery(scope, snapshot, root, direction, max_depth, max_nodes, max_edges, living_only, page_size)`; one family and one evidence class per query. Directions: `ancestors`, `descendants`, `both`; edges retain their native direction in all modes.
- Snapshot schema: `lineage-snapshot-v1`; page schema: `lineage-graph-page-v1`. These are sibling research/query schemas, not runner, replay, result, or observer protocol versions.
- `LineageCoverage` distinguishes `complete`, `partial`, `unavailable`, `disabled`; stores bounded reason codes, capture start/end, missing prefix, pruned/unresolved counts, and policy version. Complete means complete for the declared captured evidence, never complete knowledge of society.
- `LineagePage` contains qualified root, snapshot descriptor, nodes, edges, matched node keys, context-only flags, coverage, traversal counters/stop reasons, and nullable continuation. Every returned edge endpoint must have a descriptor in that page, even when repeated across pages. Confidence uses an optional native categorical `confidence_code` and optional finite numeric value; never manufacture a probability from a categorical code.

### Requirement Evidence
User request: all eight families and both-client APIs. Project rules: `.ai-factory/RULES.md` axioms 1–6. Existing debugger module forbids text payloads. Tests assert every allowed family/scope combination and reject all others.

### Error Handling and Logging
Reject unknown enums, bool-as-int, negative ticks, run mismatches, invalid kind-specific identity ownership, duplicate conflicting IDs within one source revision, NaN confidence, and payload-bearing fields. In subjective scopes every local node belongs to the selected owner; analytical nodes may retain different source owners only according to the closed kind rules above. Logs contain family/class, safe run/owner IDs, counts and reason codes only; never node keys derived from content, full source refs, or DTO reprs.

### Tests / Acceptance / Verification
`tests/unit/test_lineage_contracts.py`: frozen nested values; stable identity across insertion order; same local entry ID in two owners/families/runs never collides; one analytical agent reference joins teacher/learner roles while local entries stay distinct; selected-owner isolation; mentorship record round trip excluding fingerprints; parallel-edge preservation; unknown-field rejection; no body fields; disabled versus empty. Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_lineage_contracts.py --cov=simulation --cov-report=term-missing -q`. All cases pass and no dependency/import changes are required outside public facades.

## Task 2: Freeze source ports, budgets, and historical semantics

### Intent
Make bounded work and boundary-valid evidence enforceable throughout the implementation.

### Implementation Steps
1. Define `LineageReadPort.open_read(run_id, budget, commit_ref=None)` as an async context manager returning `LineageReadSession`. It pins a committed immutable run catalogue generation, owns one request-local verified-file cache, and exposes async `resolve_snapshot(scope, boundary_tick_or_none)`, `get_node(snapshot, key)`, `neighbors(snapshot, key, direction, after, limit)`, `node_page(snapshot, after, limit)`, `lookup_nodes(snapshot, native_kind, native_id, after, limit)`, and `snapshot_page(scope, after, limit)`. The session descriptor exposes its `run_commit_ref` for catalogue cursors. Page methods return at most `limit` rows plus a continuation and declared counts; any look-ahead read is charged. No reader method is usable without the shared budget/session.
   `LineageReadBudget` owns remaining physical-file reads and UTF-8 source bytes plus counters. Adapters reserve a physical read and the verified file size before reading/decoding; reject before I/O when either allowance is insufficient. Actual bytes may not exceed that reservation. Manifests, heads, catalogue/index shards, descriptors, pages and missing-file probes all count. Cache hits do not count as new physical reads. Catalogue, exact lookup and traversal reuse this same session and budget; the query core must not infer file costs from port-call count.
2. Define `LineagePublicationPort.publish(publication)` and async `LineageBoundarySink.capture(frame)`. Publishers and readers are different capabilities. Query services accept only the reader. Introduce typed detached `LineageBoundaryFrame` with objective facts and owner-local source records; do not pass an engine, runner, services, or callbacks into queries.
3. Fix query defaults/hard ceilings: depth 4/32; visited nodes 200/1,000; visited edges 500/4,000; page graph records 100/200 (also respect a smaller `api_max_page_size`); source page 128/256; source page reads 128; decoded source bytes 8 MiB; response bytes 1 MiB. Root counts toward node budget. Reject requests above ceilings, never silently widen them. A graph record is one node discovery or one admitted edge; endpoint descriptors may repeat as page context.
   These ceilings are for HTTP/query sessions. Trusted capture's prior-publication merge uses a separately constructed finite read budget of at most 65,536 file reads and 256 MiB source bytes per scoped publication; graph row/normalized-byte and cumulative artifact quotas still apply. This larger producer budget is never selectable through an HTTP query/cursor. Capture streams pages and does not reset budget while processing one scope.
4. Fix capture caps: 20,000 nodes, 40,000 edges, 64 MiB normalized publication; default cumulative per-run quotas are 1,000 scoped publication reservations and 256 MiB encoded artifact file bytes, excluding OS block/journal overhead. A reservation is one `(family,class,owner,B)` publication attempt, not one tick or whole-run frame. Quotas include committed artifacts, reserved staging/orphan bytes and publication/catalogue metadata; restarting a capture session never resets them. Failed/abandoned reservations remain charged until an explicit out-of-band operator cleanup, which this plan does not implement. An identical successful retry consumes no new reservation. Cap exceedance records a gap and stops capture without eviction or changing simulation behavior. Budgets are composition settings, not domain capability flags or runner fields.
5. A boundary `B` means finalized state after exactly `B` ticks: initial state is B=0; events admitted into that state have tick `< B`. Normalize ledger source timing through explicit adapter tests. Keep `observed_boundary` separate from native acquisition/event ticks.
6. An omitted boundary resolves once to an immutable latest publication. Explicit boundary requests require an exact captured boundary; no nearest/latest substitution. Source not captured at B is unavailable. A continuation pins publication ID/digest, not a moving `latest` alias.
7. Use purpose-specific continuation types: traversal pins snapshot/root/effective-query fingerprint and record offset; node catalogue pins snapshot/filter fingerprint and last node key; snapshot catalogue pins scope/run-commit catalogue generation and last boundary key. Catalogue cursors have no fabricated root or graph-publication field. Native-ID lookup requires `native_kind` and uses a direct identity index with bounded match pages, never an unfiltered node-catalogue scan.

### Required Interfaces and Contracts
Supported combinations: objective genealogy/record with no owner; subjective mentorship/knowledge/technology/narrative/office succession with exactly one owner; analytical mentorship/knowledge/technology/narrative/institution with no selected owner and owner-qualified nodes. Institution inference stays analytical. Unsupported combinations return `invalid_lineage_scope` before reads. `living_only` is valid for genealogy agent results only; it filters output, not traversal through dead ancestors. Other families reject it.

### Error Handling and Logging
Separate source absence from exhausted work. Domain errors include `invalid_lineage_scope`, `invalid_lineage_budget`, `snapshot_unavailable`, `snapshot_corrupt`, and `lineage_source_budget`. Authentication is enforced outside the port before any source lookup. Log budget counters, not payloads.

### Tests / Acceptance / Verification
Extend `test_lineage_contracts.py` with the complete combination matrix, B=0/B=1 timing, explicit missing boundary, cumulative reservation semantics, cursor-purpose types, and counting fake sessions. A fake method that performs three file reads must consume three read slots, including when its public API is called once. Verify budget rejection before reading an oversized file, and shared accounting across snapshot resolution, catalogue and graph reads. Use the Task 1 command. Acceptance: no task downstream needs to choose budgets, history semantics, ownership or cursor purpose.

## Phase Risks and Mitigations
- Ambiguous source tick meanings: dedicated B=0/B=1 adapter fixtures, not global `<=` filtering.
- New DTOs becoming a truth registry: mandatory class/owner identity and no live consumers.

## Phase Completion Checklist
- Both task contracts and tests pass; update progress only in `index.md`.
