# Phase 3: Detached research

Plan: [index.md](index.md)  
Tasks: 5–6  
Depends on: Phase 2 / Tasks 3–4

## Objective

Expose evidenced support networks and matched predictive performance as independent views of the same retained theory claims.

## Current-Code Evidence

| Path | Symbols / contract | Why it matters |
|---|---|---|
| `src/experiments/scientific_models_completed_run.py`, `src/analysis/scientific_models_analysis.py` | `scientific_model_facts`, `harvest_scientific_models_analysis` | Trusted owner export bridge, detached recomputation |
| `src/experiments/collectors.py`, `src/analysis/metric_service.py`, `src/analysis/specifications.py` | `assemble_arm_metric_bundle`, optional analysis inputs, ordered specs | Metrics registration without legacy output changes |
| `src/experiments/scientific_models_publication.py`, `src/persistence/scientific_models_filesystem.py` | Compose then publish canonical children and atomic manifest | Opt-in immutable filesystem sidecar |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/analysis/competing_theories_models.py`, `competing_theories_analysis.py`; `src/experiments/competing_theories_completed_run.py` | Create | Frozen detached contracts, graph, comparison, token bridge |
| `src/analysis/metric_service.py`, `specifications.py`, `src/experiments/collectors.py` | Modify | Append six metric specs; optional arm contribution only |
| `src/simulation/competing_theories_models.py`, `competing_theories_codec.py`, `competing_theories_paging.py`, `competing_theories_ports.py` | Create | Canonical bounded document, section rows, queries, ports |
| `src/experiments/competing_theories_publication.py`, `src/persistence/competing_theories_filesystem.py` | Create | Whole-bundle publisher and verified filesystem store |
| `tests/unit/test_competing_theories_analysis.py`, `test_competing_theories_metrics.py`, `test_competing_theories_store.py` | Create | Detached semantics and immutable persistence |

## Task 5: Build support networks and performance views

### Intent

Represent different support communities without installing a global group model or awarding a winning label.

### Implementation Steps

1. Tokenize frozen completed-run ledgers using the V4-30 bridge pattern; token namespaces include run and type for owner, case, location and provenance. Preserve equality needed for joins without exporting raw observation bodies, utterances or source refs. Sort/dedup exact rows. Analysis accepts detached validated facts only; validate context, claim links, attribution, ordered tick keys, alphabet, closure and probability sums. Conflicting duplicate identity is invalid. Missing inputs mean unavailable, not zero support or failure.
2. Build fixed 32-tick windows, retain at most 512 nonempty evidence windows and report the omitted boundaries. Shared claim key/token joins owners; a support edge is owner→claim from the owner’s latest admitted stance as of the inclusive window end, not from speech or membership alone. Attribute peer support receipt separately from local stance, and communication/teaching as directed speaker→learner edges by canonical recipient occurrence. Omit sender echoes in graph counts. Derive optional **support communities** per theory/window as weakly connected components of unique active supporters linked by observed `support` declarations or delivered `teach` edges of that same claim during that window; include isolated supporters and do not link by `share` alone. Identifier is content-addressed from window, theory and sorted owner tokens. Communities are analytical, not durable organizations, and no group inherits a member’s truth or authority.
3. Aggregate citations by kind, polarity, distinct verified roots and declared/unresolved pointer counts; preserve source qualifiers. Pair forecasts only within the same owner case ID, context and canonical alphabet, bucket by issue window, and recompute hits, failures, Brier numerators and paired sample count; require at least three observed pairs for descriptive loss difference. Keep unscored and pending separate. Return raw support denominator (owners with explicit active stance in that context), evidence coverage and retained matched performance, never ranks or labels such as “correct,” “winning,” or “dominant.” Sort by keys, not prevalence or predictive loss. Do not recompute owner support from analysis.
4. Append six `@1` families, in order: `competing_theory_structure`, `competing_theory_support_network`, `competing_theory_citations`, `competing_theory_predictions`, `competing_theory_failures`, `competing_theory_transmission`. Use bounded count keys respectively: `claim_count/rival_pair_count`, `support_edge_count/community_count`, `citation_count/verified_root_count`, `prediction_count/scored_count`, `failure_count/unscored_count`, `delivered_count/teaching_count`. Count from unique retained facts, not repeated window edges where a stance persists (network counts unique window-qualified edges; prediction metrics count unique case/claim rows). No input emits no families. Leave the first 262 family definitions and order unchanged; audit/update only affected catalog count pins, to 268.
5. Use `(run, owner, row type, local key)` for private IDs; tokenized canonical theory IDs are run-qualified but not owner-qualified, and declared citation pointers must use a namespace distinct from verified evidence roots. For support denominators use only owners with retained explicit active stances; report observed-owner coverage separately using each owner's last finalized theory tick (persist this watermark even when the update has no changed rows). At the trusted bridge, join committed `Died.body_id` only through a verified run-scoped owner/body binding; exclude at and after a known death boundary from current support, never count unobserved/uncertain owners as against, and keep historical stance rows. Clamp the last window end to the completed run high-water mark. Unavailable binding/terminal tick stays unknown; absence of a death record is not sufficient to carry a stale stance past its owner's finalized-observation watermark.
6. Define prediction buckets precisely: `prediction_count` includes pending; `scored_count` includes hits and failures; `unscored_count` includes only terminal non-scoring outcomes, with pending separately reported in coverage. Count pair denominators only where both predictions were frozen on the exact same case and observed; use stable `a,b` key order and a signed paired Brier difference, not separately aggregated owner-loss means. Validate non-overlap between terminal and pending classes and do not treat a `teach` receipt or relayed pointer as a verified evidence root.
7. At `assemble_arm_metric_bundle`, build facts once from `arm.runner_result` and the authoritative run assignment, then harvest once and pass the typed normalized result through the optional `MetricInputs` field; `metric_service` projects it and never reruns the harvester. Explicit activated-empty facts return six zero-valued families with coverage; absent capture returns none. Reject malformed facts, and record a safe collector failure reason without emitting plausible empty data. Exercise this exact collector path on Task 8's nonempty completed run.

### Required Interfaces and Contracts

`competing_theory_facts(result)` → detached frozen facts; `harvest_competing_theories_analysis(facts)` → independent graph, performance and coverage sections. Neither analysis nor the bridge is callable by cognition. No shared denominator for social and predictive axes.

### Requirement Evidence

`index.md` Original Request: support networks, evidence, predictions, failures, communication and teaching without a winner. `.ai-factory/ARCHITECTURE.md` “Key Principles”; `docs/scientific-models.md` “Performance”.

### Error Handling and Logging

Invalid/conflicting detached facts fail closed; absent or truncated capture is explicit. DEBUG reports safe counts and reason codes only.

### Tests

`test_competing_theories_analysis.py`: two separate components, overlapping differently across claims/windows, disconnected supporters, historical switch, teaching dedup, no support inferred from contact, contradictory and repeated citation roots, missing vs zero, invalid closure, three paired misses vs hits; popularity matrix with lower-loss minority. `test_competing_theories_metrics.py`: 268 catalog entries, frozen prefix, absent-input byte parity and exact value keys.

### Acceptance Criteria and Verification

Popular but less accurate and minority but more accurate theories appear side-by-side without global ranking. `uv run --frozen --python 3.12.14 pytest -q tests/unit/test_competing_theories_analysis.py tests/unit/test_competing_theories_metrics.py` passes.

## Task 6: Publish a bounded snapshot and verified read model

### Intent

Persist completed-run theory evidence programmatically, without placing analysis or new authority in the API/store.

### Implementation Steps

1. Define `competing-theories-snapshot-v1` with `run_id`, `publication_id`, strict version, and sorted sections `theories`, `support`, `citations`, `predictions`, `failures`, `transmission`, `coverage`. Include retained matched comparison and separate denominator fields in prediction/theory summaries; case section carries outcome status and frozen vectors; failures are projections of observed misses only. Keep rows case/claim/owner/window/token scoped. Exact keysets, typed row unions, finite values, closure and duplicate rejection; canonical bytes and digest independent of input ordering. Apply existing V4-30 ceilings of 8192 rows/section and 8 MiB total, or lower enclosing limits.
2. Use deterministic newest-window-first admission: add a whole window and its claim dependencies, build/recompute all retained sections, stop before any overflow, report omitted windows and first retained boundary. Materialize the beginning stance of each retained window from covered frozen history before truncation; omitted earlier windows do not erase known continuing stances or turn unknown coverage into zero. Put each matched forecast and its outcome/failure projection in its issuance window even if settlement crosses a boundary. Never retain an edge or failure without its associated claim/case rows. Reserve room for coverage counters before accepting a window; if the non-data envelope cannot fit, emit `quota_exceeded`, not a partial artifact. Programmatic publication receives an explicit publisher; missing composition produces `disabled`. No capture, DB schema or auto-publication.
3. Implement separate read/publish protocols and `competing-theories-store-v1`: follow `FilesystemScientificModelsStore` for path validation, cumulative per-run quotas, child-before-manifest atomicity and digest checks. Exact duplicate publication is idempotent; conflicting reuse fails closed. The reader does not mutate/repair; absence and corruption distinct. Publication receipt (`published`, `disabled`, `missing`, `quota_exceeded`, `corrupt`) is independent of experiment status. Add pure paging by canonical row order `(window, claim_token, row_key)` with optional exact `window` and `theory_id` filters supported by every row section (coverage selects only by window; reject `theory_id` there). Summary is not paged.

### Required Interfaces and Contracts

Snapshot/read/publication contracts live under `simulation`; `experiments` alone composes analysis and publication; persistence imports contracts only. Strict canonical encoding, whole-window denominators, no API imports by runner or producer.

### Requirement Evidence

`docs/scientific-models.md` “Publication, store and reads”; `.ai-factory/ARCHITECTURE.md` “Dependency Rules”.

### Error Handling and Logging

Fail closed on digest, run/path ID, quotas and canonical decode. DEBUG counts and status only; logs omit payloads, raw filesystem paths, cursors and keys.

### Tests

`test_competing_theories_store.py`: reordered input bytes, corruption, oversized window, retained cross-window forecast/failure closure, carried stance across dropped windows, absent store, exact duplicate, conflicting duplicate, cumulative bytes across two individually valid publications, quota race and staging/manifest fault injection; no write during reads.

### Acceptance Criteria and Verification

`uv run --frozen --python 3.12.14 pytest -q tests/unit/test_competing_theories_store.py tests/architecture/test_competing_theories_boundaries.py` passes.

## Phase Risks and Mitigations

- Sparse receipt data cannot prove a social group: label components retained support communities, not populations or schools.
- An overfull snapshot can bias endpoints: truncate all dependent displays on the same window boundary and recompute denominators.

## Phase Completion Checklist

- Detached analyses pass with no cognition imports and canonical read-model tests pass.
- Update only the Task 5–6 checkboxes in `index.md`.
