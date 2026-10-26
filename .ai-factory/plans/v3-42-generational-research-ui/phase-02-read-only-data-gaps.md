# Phase 2: Close bounded read-only data gaps

Plan: [index.md](index.md)  
Tasks: 4–6  
Depends on: Task 1 contracts

## Objective
Expose existing cultural sidecars and retained semantic history without running analysis in HTTP, introducing new capture, or claiming durable subjective restoration.

## Current-Code Evidence
| Path | Symbols | Why it matters |
|---|---|---|
| `src/api/routes/research_matrix.py` | `_resolve_under`, `_read_json`, `list_matrix_cells` | Allowlisted root exists; cultural siblings are not exposed and can be mislisted as cells |
| `src/experiments/cultural_evidence_serialization.py` | envelope/row key sets, digest encoding | `cultural-evolution-evidence-v1` is already metadata-only; use its exact existing wire structure |
| `src/experiments/cultural_metric_artifacts.py` | `CulturalCellMetrics`, `verify_cultural_pair` | Pair identities and capture window must agree; API cannot import this analysis-dependent module |
| `src/observer/labels.py` | additive projection functions | Existing detached observer projection pattern |
| `src/api/routes/observer.py` | `get_observer_labels`, `get_observer_symbolic_language` | Runtime checkpoints are owner-scoped and historical tick availability is limited |
| `src/agents/cognition/semantic_naming.py` | `NamingSenseRecord`, `sense_history` | Bounded records have absolute ordinal/tick/trigger and referent metadata |
| `src/agents/cognition/symbolic_language.py` | `SymbolicSenseRecord` | Composition histories have association IDs, not a mandatory single referent |

## Files to Change
Introduce `src/api/research_cultural_schemas.py`, `src/api/research_cultural_service.py`, `src/api/research_cultural_cursor.py`, `src/api/semantic_history_schemas.py`, `src/api/semantic_history_service.py`, `src/observer/semantic_history.py`. Modify `src/api/routes/research_matrix.py`, `src/api/routes/observer.py`, `src/api/app.py` at its existing service/cursor composition and lifespan setup, and public observer facade only for documented projection exports. Tests: new `tests/unit/test_research_cultural_api.py`, `test_semantic_history_api.py`, `test_semantic_history_projection.py`; extend `test_research_matrix_fs.py`; new `tests/architecture/test_generational_research_ui_boundaries.py`.

## Task 4: Safely expose cultural comparison and cell metric documents
### Intent
Let cohort/culture screens use already computed scientific artifacts; do not recompute metrics or intervals in API/UI.
### Implementation Steps
1. Add GET `/v1/research/matrices/{matrix_id}/cultural-comparison` and `/v1/research/matrices/{matrix_id}/cells/{cell_id}/cultural-metrics` using existing root/ID containment rules. Fixed filenames are `cultural-metric-comparison.json` and `cells/{cell_id}.cultural-metrics.json`. Both require objective inspection, matching stored-metric access policy.
2. Implement a bounded, duplicate-key-aware JSON reader in `research_cultural_service.py`: max 64 MiB input, max depth 32, reject nonfinite numbers, symlinks escaping configured root, unsupported schema and path traversal. Execute filesystem work through the existing project thread-offload pattern, never block the event loop with large reads.
3. Validate envelope schemas (`cultural-metric-comparison-v1`, `cultural-cell-metrics-v1`), canonical self digest when present, referenced cell/run/config identity and required provenance/window fields. The comparison has no self-digest: bind its `matrix_fingerprint` to the real runtime manifest, or visibly mark legacy export binding unverified rather than inventing a digest field. Validate cultural measurement strings under `documents[*].values.rows_json` separately: UTF-8 <=16 MiB, depth<=32, duplicate-key-aware/nonfinite-rejecting decoding and scalar-row shape/coverage checks. Outer JSON bounds do not constrain JSON encoded inside strings. Preserve original stored documents/intervals without recalculation; do not import analysis/experiments decoders.
4. Accept both existing exported `experiment-matrix-v1` manifests and real producer `matrix-manifest-v1` manifests with `matrix_schema_version=experiment-matrix-v1`; validate each shape separately and preserve its schema unchanged in GET output. Real runtime headers include `matrix_fingerprint` and `cell_ids`; cell records are schema-less state documents, not runner-result envelopes. For runtime manifests list only declared cell IDs with matching state documents. For legacy exported manifests retain safe filename discovery but exclude `.completion.json`, `.metrics.json`, `.cultural-evidence.json`, `.cultural-metrics.json` and other known sibling suffixes. Never overwrite a runtime manifest with the source experiment spec to satisfy the old API assumption. Update list response schema typing/client guards to accept both documented formats.
### Required Interfaces and Contracts
Responses retain original artifact schemas and payloads. Return `X-Palimpsest-Artifact-Binding: runtime_bound|legacy_unverified` as response metadata without widening stored schemas. Runtime cultural reads require a completed cell state and its fixed `.completion.json` proof with matching cell/run/stop reason; absent completion is 409 `research_cell_incomplete`, not successful verified completion. Comparison reads bind to manifest fingerprint and retain published excluded/inference status. Missing root503; missing artifact404 `matrix_file_missing`; unsupported/corrupt/digest mismatch400 safe codes; over bound413 `research_artifact_too_large`. `Cache-Control: no-store`. API never writes, repairs, calls manifest-store `open()` (which performs crash recovery writes), or starts a batch. Validate real artifact field names, not minimal synthetic fixtures.
- Initialize the optional cultural service/cursor only through `create_app`/a dedicated optional attach helper; do not make `_attach_persistence_services` depend on new settings/service state. Test both the production lifespan and a bare `FastAPI()` persistence-attachment call. An unset optional root must not break observer/replay attachment. Use existing safe `ApiError` mapping, including explicit 413 construction if no helper exists.
### Requirement Evidence
`docs/cultural-evolution-metrics.md`, V3-37 artifact and seed-block contracts; existing matrix route inspection policy. `ARCHITECTURE.md` forbids API imports of analysis and experiments.
### Error Handling and Logging
INFO route/outcome/count/duration; DEBUG schema and byte counts; WARN reason code only for malformed/oversize artifacts. Never log documents, digests as content surrogates, tokens, absolute storage paths or untrusted exception bodies.
### Tests
Real generated cultural pair/comparison served unchanged; wrong schemas, duplicate keys, nonfinite JSON, excessive size/depth, traversal/symlink escape, missing root, absent artifact, credentials and sidecar cell-list regression. Include duplicate keys/depth/nonfinite values inside `rows_json`, correct outer envelope with malformed nested rows, completed state without completion proof, mismatched completion, raw binding header parity, and real runtime versus legacy export cases. Snapshot file bytes before/after GET to prove no writes. Run `tests/unit/test_observer_population_replay.py` and verify bare-app optional attachment remains supported.
### Acceptance Criteria
Existing metrics can be read by the UI; cell discovery lists real result cells only; no analysis import or new scientific format.
### Verification
`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_research_matrix_fs.py tests/unit/test_research_cultural_api.py -q`.

## Task 5: Add a paged metadata projection over cultural evidence artifacts
### Intent
Plot vocabulary and trait inventory boundaries without downloading up to a million rows or exposing raw owner ledgers.
### Implementation Steps
1. Add GET `/v1/research/matrices/{matrix_id}/cells/{cell_id}/cultural-evidence` with `section=boundaries|traits|transmission|groups|archives`, optional inclusive `from_tick`, exclusive `to_tick`, `owner_id`, `dimension`, `limit` (default100/max200 constrained by API ceiling), `cursor`. Require subjective debug before filesystem access for every section because inventory and inferred memberships are research-sensitive.
2. Read the fixed cultural evidence and metrics pair under Task4 bounds. Require schema, canonical evidence digest, metrics self digest and evidence linkage; matching run ID, config fingerprint, capture options, window, and bound cell/matrix fingerprints. For runtime manifests require agreement with `manifest.matrix_fingerprint`, state-record `cell_id`, `cell_fingerprint`, `config_fingerprint`, completed `state` and `run_id`, plus a mandatory fixed `.completion.json` with matching cell/run/stop reason and supported version-identity shape. Completed state alone is insufficient; absence returns `research_cell_incomplete`. These checks bind read identity and do not claim to verify unavailable result payload bytes from `result_payload_hash`. For legacy exports validate pair identities and matching exported fields, mark `binding_state=legacy_unverified`, and never label the artifact runtime-completion-verified. Reuse exact wire key sets as structural specifications, not forbidden imports.
3. Return new `research-cultural-evidence-page-v1`: run/matrix/cell IDs, section, artifact digest, source revision, `binding_state=runtime_bound|legacy_unverified`, requested window, capture status/gaps, rows, next cursor, truncated and coverage. Rows are existing normalized metadata only. Traits expose owner/local entry/dimension/content digest/lineage/acquisition/status/refs; no tokens, marks, stories or ledgers. Boundaries retain living roster, generation mapping and owner/dimension coverage; cap serialized reply at2 MiB, reducing page length before encoding and rejecting a single over-size row with413 rather than cutting denominators silently. Keep read-binding state independent of scientific capture coverage and measurement availability.
4. Order boundary rows by tick; traits by tick/owner/dimension/local ID; transmission by acquisition boundary/edge ID; groups and archives by tick and their existing qualified IDs. Filter before slicing. Do not invent edges or group memberships.
5. Introduce purpose-specific HMAC cursors in `research_cultural_cursor.py`, app-lifetime secret, 15-minute TTL. Bind schema/purpose, matrix/cell/section, pair digests, normalized filters and offset; max4096 chars. Re-read current pair and reject changed digest with 409 `research_snapshot_changed`; expired/tampered/wrong query is 400 `invalid_research_cursor`. Explicit filters must agree with the cursor. Separate schema version from underlying scientific artifact version.
### Required Interfaces and Contracts
No new capture option, runner field, database table or analysis family. Coverage comes from existing gaps/status and the selected dimension's owner coverage; empty complete versus missing inventory remains distinct. API projection is not `verify_cultural_pair`'s full scientific validation; documentation must not claim replay reproducibility from HTTP structural validation. No unauthenticated discovery of owner counts.
### Requirement Evidence
`cultural_evidence_serialization.py` exact normalized schemas and `cultural_metric_artifacts.py` pair bindings; `RULES.md` owner scope and fail-closed input.
### Error Handling and Logging
As Task4; log cursor reason codes and returned/scanned counts without cursor tokens or full artifact hashes. Corrupt pair is an error, not unavailable-empty. Stop at resource bound before JSON decoding.
### Tests
Real pair pagination over >200 rows, filter/order parity, full union without duplicates, empty page, sparse coverage, failure/missing prefix, expired/wrong-owner/wrong-section cursor, file mutation between pages, pair mismatch, oversized row and debug auth before any read. Cross-check real fixture outputs; reject runtime completed-state-without-completion and show legacy binding as unverified even when both self-digests agree.
### Acceptance Criteria
Every page is stable and pinned to a verified byte identity; no raw narrative/lexical payload escapes; arbitrary paths cannot be requested.
### Verification
`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_research_cultural_api.py tests/architecture/test_generational_research_ui_boundaries.py -q`.

## Task 6: Expose retained owner semantic sense history with honest temporal limits
### Intent
Provide real semantic transition rows, not a falsely historical reinterpretation of the current label.
### Implementation Steps
1. Add detached `project_semantic_history(owner_id, checkpoint, source)` in `observer/semantic_history.py`; accept duck-typed owner checkpoint data as existing labels projections do, never import cognition or analysis. Source is `label|composition`; project absolute ordinals/ticks, trigger, local binding/composition ID, term digest, referent kind/digest, associated digests and confidence. Replicate the documented domain-separated metadata hashing used by semantic metrics and test digest parity with that existing implementation from tests only. Do not expose label tokens, composition parts or raw referent IDs.
2. Add GET `/v1/simulations/{run_id}/observer/agents/{agent_id}/semantic-history` requiring debug. Query `source`, optional `tick` (checkpoint observation key, not an arbitrary replay tick), `from_tick`, `to_tick`, `after`, `limit`. Use existing owner checkpoint lookup; confirm checkpoint owner matches route owner. `to_tick` is exclusive. Resolve a concrete checkpoint before pagination.
3. New `observer-semantic-history-v1` envelope contains requested tick, `checkpoint_tick`, `history_first_tick`, `history_last_tick`, `retained_only=true`, `prefix_complete=false` (conservative unless explicitly proven), per-term retained first ordinal and current sense revision, rows, availability/reason, continuation. A missing checkpoint or disabled ledger returns unavailable with distinct codes; enabled empty returns complete-empty for the retained inventory, never proof of lifetime absence.
4. Use signed opaque `after` bound to run/owner/source/filter and a canonical digest of projected checkpoint rows plus checkpoint key; reuse the Task5 cursor primitive with separate purpose. Changed live checkpoint returns409 `semantic_checkpoint_changed`. Requesting a different historical checkpoint tick returns explicit unavailable, never current data tagged as historical. Obtain optional checkpoint/service state defensively in minimal app/test adapters and keep observer/replay attachment independent of this optional route; include the predecessor population-replay attachment suite in verification.
### Required Interfaces and Contracts
Bound rows<=200; total projection constrained by existing bounded ledger histories; safe schema rejects extras. A retained history may contain old ticks but its as-of checkpoint remains visible. No durable subjective restart/capture added. Histories of different owners or term sources never merge by local ID.
### Requirement Evidence
Naming/Symbolic sense records are bounded and ordinal-based; observer label routes only promise available checkpoints; user asks semantic drift and epistemic distinction, not ground-truth correction.
### Error Handling and Logging
Safe source/checkpoint/count/duration metadata. Do not log terms, referents, digests or row payloads. Permission error precedes checkpoint access. Unsupported source 400; corrupted owner mismatch fails closed.
### Tests
Naming and symbolic fixtures with trimmed ordinals, same local IDs across owners, no referent for composition, enabled empty, disabled, absent checkpoint, tick mismatch, changed checkpoint cursor, metadata digest parity, no raw strings in response/logs, and route auth.
### Acceptance Criteria
UI can draw retained semantic changes with exact ticks and uncertainty; requests never imply arbitrary historical subjective restoration.
### Verification
`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_semantic_history_projection.py tests/unit/test_semantic_history_api.py tests/architecture/test_generational_research_ui_boundaries.py -q`.

## Phase Risks and Mitigations
Duplicate validation may drift from scientific codecs: keep read structural validation separate, use real encoded artifacts and parity tests. Large reads: byte/depth bounds, thread offload and paged replies. API must never import analysis/experiments, run calculators or add new capture behavior.

## Phase Completion Checklist
All API tests and import boundaries pass; progress lives only in `index.md`.
