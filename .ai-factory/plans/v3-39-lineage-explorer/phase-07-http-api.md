# Phase 7: Client-neutral API services and HTTP routes

Plan: [index.md](index.md)  
Tasks: 13–14  
Depends on: Tasks 1–12

## Objective
Expose the same evidence-aware historical query surface to Godot and Research UI without client-specific graph assembly or new write authority.

## Current-Code Evidence

| Path | Symbols | Relevance |
|---|---|---|
| `src/api/services.py` | `CausalDebuggerApiService`, `InspectionService` | Injectable API service protocols. |
| `src/api/persistence_services.py` | `PersistenceCausalDebuggerService` | Composition over simulation DTOs and persistence adapters, not analysis. |
| `src/api/app.py` | `_attach_persistence_services` | Preserve injected test services; standard composition root. |
| `src/api/routes/debugger.py` | `_subjective_debug`, `debugger_lineage` | Existing GET-only debug gate; preserve these routes unchanged. |
| `src/api/security.py` | `require_http_capability`, `ApiCapability` | Debug enablement plus debug credential; capabilities not hierarchical. |
| `src/api/errors.py` | `ApiError`, `bad_request`, `gone`, `service_unavailable` | Safe problem-detail mapping. |

## Files to Change
Create `src/api/lineage_service.py`, `src/api/lineage_schemas.py`, `src/api/routes/lineage.py`, and `tests/unit/test_lineage_api.py`. Modify `src/api/services.py`, `src/api/dependencies.py`, `src/api/app.py`, `src/infrastructure/settings.py`, and the existing route registration location in `api.app`. Keep family DTOs out of the already-large general schema module except deliberate re-exports if its convention requires them.

## Task 13: Compose lineage reader, catalogue, query service and strict API schemas

### Intent / Implementation Steps
1. Add `LineageApiService` protocol with `families`, `snapshots`, `nodes`, and `traverse` methods and implement `ArtifactLineageApiService` over the new read port/catalog/query services. Each authenticated method owns one Task 2 read session, including run/snapshot resolution and any catalogue/traversal call, and passes it through without resetting counters. No concrete filesystem access in handlers and no analysis imports.
2. Add optional `Settings.lineage_root` (`PALIMPSEST_LINEAGE_ROOT`) and secret `lineage_cursor_key` (`PALIMPSEST_LINEAGE_CURSOR_KEY`). Validate root configuration without opening files at import. Root absent means the service is disabled, not an empty graph. The setting grants read access only; it does not start capture or mutate source artifacts.
3. Add `_attach_lineage_service(app)` in `api.app`, separate from `_attach_persistence_services` and its SQL/session-factory guard. Call it during app construction after settings are assigned and before catch-all static mounts; preserve an already injected service. It creates a lazy reader and operational cursor signer without opening the artifact root or contacting SQL. Filesystem research runs can lack SQL run rows. Existing database lifespan behavior remains unchanged; lineage root outage is a request-level 503 and must not prevent unrelated health/control routes from working.
4. Add `get_lineage_service` dependency. Missing/disabled source service returns the standard 503 problem code after authorization. Existing debugger services, graph summaries, observer sources and clients are untouched.
5. Implement frozen Pydantic schemas with `extra='forbid'`, bounded strings/lists and explicit evidence/source/coverage fields. Mirror the kind-specific identity rules: analytical actor/event references can be shared, owner-local entries cannot; claim ownership remains on edges. Outputs include opaque purpose-specific cursors, `matched_node_keys`, `context_only`, effective limits and requested/captured boundary. Do not export free-form source payloads, fingerprints, paths or raw checkpoints. Detailed safe mentorship metadata is reference/count/code data only, not the complete native entry.

### Required Interfaces and Contracts
No new package dependency, SQL migration, API version prefix, runner/result schema, observer semantic type or protocol rename. Public `LineageApiService` is test-injectable. Supported family/scope matrix is exactly Task 2; schema/DTO conversions cannot widen it.

### Requirement Evidence
Both clients use existing HTTP transport and header capabilities; architecture composition boundaries and current API service patterns. New root setting is a trusted local source, not a request-supplied path.

### Error Handling and Logging
Startup logs only enabled/disabled state; never root/key values. Map typed service errors to stable problem codes, no `str(exc)` leakage. Reader-only deployments work with prebuilt artifacts and never require a live runner.

### Tests / Acceptance / Verification
In `test_lineage_api.py`: injected service preservation, disabled root, invalid key, root outage with healthy `/health`, strict schemas, non-SQL artifact run, no live-runner fallback. Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_lineage_api.py --cov=api --cov=infrastructure --cov-report=term-missing -q`. Acceptance: service can be consumed/tested without either client or PostgreSQL.

## Task 14: Add GET routes with evidence-specific authorization

### Intent / Implementation Steps
1. Register these GET-only routes under `/v1/simulations/{run_id}/lineage`:
   - `/families`: objective-only catalogue by default; `include_restricted=true` requires subjective debug and returns the fixed restricted family capabilities without enumerating other owners.
   - `/{family}/snapshots`: bounded boundary discovery for `evidence_class` and optional `owner_id`.
   - `/{family}/nodes`: bounded root catalogue; same scope plus `boundary_tick`, optional paired exact `native_kind`/`native_id`, `after`, `limit`.
   - `/{family}/traverse`: same scope plus `root_key`, `direction`, `boundary_tick`, `max_depth`, `max_nodes`, `max_edges`, `living_only`, `after`, `limit`.
2. Use OBJECTIVE_INSPECTION for objective genealogy/record only. Use SUBJECTIVE_DEBUG for every subjective or analytical query, including metadata and analytical institution graphs. Debug requires enabled setting and debug credential. Because capabilities are separate, debug routes do not additionally require an inspect credential; do not create accidental capability hierarchy.
3. Evaluate authorization before any run/root existence or availability lookup. Unsupported scope combinations, query ceilings and unknown parameters return stable validation errors. Reject duplicate scalar query parameters to avoid divergent cursor fingerprints. Use existing global credential-in-query rejection.
4. First traversal/node page resolves default B once; later pages verify the correct purpose-specific cursor before opening its pinned run/snapshot session, not a fresh latest catalogue. Require the effective original parameters to match, with omitted boundary normalized to the pinned B. Snapshot discovery uses its pinned catalogue generation and keyset, never a fabricated root or one graph publication. Native-kind/ID filters must be paired and their fingerprint must match continuation. No natural-language question endpoint: examples map questions to typed IDs, directions and filters.
5. Map malformed query/cursor to 400 (framework structural field errors may remain the existing 422 convention); proven absent run/root to 404; expired/removed pinned snapshot to 410; unavailable/disabled family at an otherwise valid scope to a 200 availability envelope; disabled service/storage corruption/outage to 503. Never report unavailable history as a valid empty complete graph.
6. Return `Cache-Control: no-store` for lineage responses, including objective responses, to keep one simple safe client policy; add no public response cache. Existing browser CORS/header policy remains unchanged. No WebSocket protocol or client code changes.
7. Emit one INFO completion log with route template, family/class, status, counts, elapsed operational time and bounded stop/availability codes. DEBUG logs counters. Never log URLs/query strings, cursors, content-derived root IDs or graph responses.

### Required Interfaces and Contracts
All graph construction is backend-owned and presentation-neutral. Clients render edge types/evidence badges, page until no cursor, deduplicate descriptors by qualified key, and distinguish partial selection from unavailable history. No layout positions or Godot/Svelte-specific response variants.

### Requirement Evidence
User both-client API requirement; `src/api/security.py` distinct capabilities; existing debugger/summary routes gate subjective metadata. All eight families have a route through the supported class matrix.

### Tests / Acceptance / Verification
Extend `test_lineage_api.py`: every family/class combination; unauthorized/disabled-debug/wrong credential; inspect token cannot see subjective metadata or analytical totals; debug token alone works for restricted endpoints; auth before `open_read` spy; all route methods; paired native-kind/ID validation and direct lookup; node/snapshot/traversal cursors and cross-purpose rejection; catalogue append during paging; one shared budget across resolution and traversal; safe JSON/cursor failures; no-store header; OpenAPI bounds/enums; legacy debugger unchanged. Verify the new lazy attachment with a fake database resource that has no session factory, and verify an unavailable artifact root does not break `/health`.

Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_lineage_api.py tests/unit/test_debugger_api_routes.py tests/unit/test_subjective_graph_summary.py tests/unit/test_api_security.py --cov=api --cov=simulation --cov-report=term-missing -q`. Acceptance: one usable HTTP contract for both clients, with no extra authority or information leak.

## Phase Risks and Mitigations
- Metadata assumed public: restricted queries always require existing subjective debug gate.
- Moving latest during paging: cursor pins B/publication; never read a replacement publication silently.

## Phase Completion Checklist
- API/security/OpenAPI tests pass and old routes remain stable; update only `index.md`.
