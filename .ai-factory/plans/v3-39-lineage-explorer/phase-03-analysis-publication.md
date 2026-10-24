# Phase 3: Detached analysis adapters and artifact codec

Plan: [index.md](index.md)  
Tasks: 5–6  
Depends on: Tasks 1–4

## Objective
Expose existing research lineage inference through explicit analytical artifacts without adding analysis imports to the API, simulation or persistence.

## Current-Code Evidence

| Path | Symbols | Relevance |
|---|---|---|
| `src/analysis/knowledge_genealogy.py` | `build_knowledge_genealogy_graph`, `query_who_taught` | Existing cross-owner inference; caller must prefilter boundary-valid audits. |
| `src/analysis/institution_lineage.py` | `compute_institution_lineage`, `InstitutionEpisode`, `InstitutionEpisodeStub` | Existing continued/transformed/split/reappeared inference with ambiguity. |
| `src/analysis/institutional_decay_metrics.py` | `INSTITUTION_LINEAGE_GRAPH_SCHEMA` | Existing `institution-lineage-graph-v1` canonical JSON output. |
| `src/analysis/cultural_narrative_survival.py` | Owner/local variant graph identity | Cross-owner narrative evidence remains analytical. |
| `src/experiments/composition.py` | Detached harvest-to-analysis composition | Correct layer for conversion/publication; no concrete persistence imports. |
| `src/agents/cognition/mentorship.py:213–234,1142–1155` | Native entry and summary audit fields | Only native entries supply the parent/root/content identities needed for detailed teaching chains. |
| `src/experiments/cultural_metric_artifacts.py:200–278` | `_pairs`, `_depth_ok`, `decode_cultural_cell_metrics` | Existing duplicate-aware and depth-bounded JSON behavior to match without importing outer/private helpers into simulation. |

## Files to Change
Create `src/experiments/lineage_publication.py`, `src/analysis/mentorship_lineage.py`, `src/simulation/lineage_codec.py`, `tests/unit/test_lineage_analytical_sources.py`, and `tests/unit/test_lineage_codec.py`. Modify `src/analysis/knowledge_genealogy.py` to add the backwards-compatible identity-safe explorer projection entrypoint specified below; legacy calculator IDs/output stay unchanged.

## Task 5: Adapt knowledge, technology, narrative and institution inference

### Intent / Implementation Steps
1. Put analytical composition in `experiments.lineage_publication`. It imports public analysis functions and produces simulation-owned neutral publication DTOs through the publication port. API and persistence only consume those DTOs/artifacts.
2. Filter input audits to boundary-valid rows before last-revision normalization. For knowledge's existing `entry:{entry_id}` scheme, add a separate `build_qualified_knowledge_lineage` adapter in the analysis module using `(owner_id, entry_id)` keys throughout. Reuse the existing transmission eligibility/tie-breaking algorithm; do not rewrite native metric graphs or mutate input IDs/content keys. Preserve `holds`, `transmitted_from`, `combined_from`, `mutated_from`, and unresolved classifications exactly. Analytical transmission is not verified teaching.
3. Technology analytical view filters the qualified knowledge graph by actual technique/capability anchors and retains supporting ancestor stubs. It does not interpret record preservation as performance capability.
4. Institution projection uses `compute_institution_lineage` result, or strictly decodes an existing verified `institution-lineage-graph-v1` payload. For embedded JSON in a metric string, enforce a 16 MiB byte cap, maximum nesting depth 32, duplicate-key rejection at every object depth, finite numbers, exact schema/key sets and B-valid source revision before graph construction. Outer-envelope validation does not validate the inner string. Preserve policy version, absolute episode IDs, continuation/transformation/split/reappearance edges, confidence code, overlap, ambiguity and pruned stubs. Do not mint objective institutions or derive lineage from labels, occupants or support-set similarity.
5. Narrative analytical projection links owner-qualified variants only through explicit existing transmission/source evidence. Declared shared event/root IDs alone produce separate `claimed_event_origin` edges, not cross-owner equivalence. Aggregate event-root browsing keeps these edge classifications visible.
6. Preserve input revision/digest, boundary, evidence coverage and algorithm version in the publication. Missing detailed source data yields unavailable, not a graph guessed from metric totals or office occupant digests.
7. Add detached `analysis.mentorship_lineage.build_mentorship_lineage` accepting only the detailed safe `MentorshipLineageRecord` metadata supplied by Task 4, not `MentorshipAudit`. Use shared analytical agent-reference nodes (identity owner absent) for teacher/student navigation, but owner-qualify each content entry and preserve its claim owner. Agent-to-agent teaching-claim edges can form Alice→Bob→Cara even when no record proves one identical content lineage; each edge retains its own kind/key and uptake evidence. Different contents or independent roots are not thereby merged into one technique ancestry.
8. Resolve an entry's native parent first in its own owner namespace. A peer-parent linkage is a separate analytical relation requiring explicit parent native ID, named source teacher, matching root/content and boundary-valid timing to uniquely agree. Preserve zero-based hop semantics; missing or multiple eligible peer parents remain unresolved with candidate counts. Failed attempts remain distinct from learning evidence. This is analytical linkage of claims/evidence, not objective successful teaching, automatic reciprocity or a new metric family. The graph must not require private local-entry nodes to share identity merely because both mention Bob.

### Required Interfaces and Contracts
`publish_analytical_lineage(inputs, publisher, options)` is trusted, offline/experiment composition; HTTP GET never calls it. Existing scientific calculators and scalar metric families retain their outputs/counts. This plan owns no new metric family, causal claim, or office alignment algorithm.

### Requirement Evidence
User institution development / technique provenance / original-event narrative questions; `.ai-factory/ARCHITECTURE.md` analysis-only classification and one-way composition rules; native algorithms above.

### Error Handling and Logging
Reject future or conflicting source revisions and unsupported policy/schema versions; preserve unresolved/pruned observations. Log only class/family, input row counts, versions and reason codes, never content keys or graph payloads/digests as payload surrogates.

### Tests / Acceptance / Verification
`test_lineage_analytical_sources.py`: two owners with identical local entry IDs; future revision must not replace historical row; native tie-break parity; unresolved teacher; same-content independent roots; institution split/reappearance/ambiguity; same labels not lineage; narrative event roots remain testimony. Teach-chain cases use real detailed entries: shared Bob actor reference, distinct Bob/Cara private entries, agent-level chain with different content roots, a separately proven same-lineage parent, owner-local parent before peer inference, failed uptake, ambiguous and missing parents. Reject audit-only detailed inputs. Add embedded institution JSON duplicate-key/depth/size/nonfinite/future-revision cases. Cross-check existing fixtures in `test_knowledge_genealogy_queries.py`, `test_mentorship_lineage.py` and `test_institution_lineage.py`.

Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_lineage_analytical_sources.py tests/unit/test_knowledge_genealogy_queries.py tests/unit/test_institution_lineage.py --cov=analysis --cov=experiments --cov-report=term-missing -q`. Acceptance: existing outputs unchanged and explorer identities never merge owners accidentally.

## Task 6: Specify and implement canonical lineage snapshot serialization

### Intent / Implementation Steps
1. In `simulation.lineage_codec`, implement strict `encode_lineage_publication` / `decode_lineage_publication` and public typed manifest/index/page decoding functions for `lineage-snapshot-v1`. Canonical UTF-8 JSON: sorted keys, compact separators, LF final newline, finite numbers; explicit field sets per record type. Check byte and maximum nesting-depth-32 limits before `json.loads`; reject duplicate keys recursively with `object_pairs_hook` and nonfinite constants with `parse_constant`. Reject invalid UTF-8, trailing JSON values and scalar envelopes. Decode checks configured row/list ceilings before allocating a complete graph. Implement the bounded decoder locally in this inner module; simulation/persistence must not import private experiment artifact helpers.
2. A manifest declares run, family, evidence class, owner scope, finalized boundary, publication ID, native source versions/revisions, coverage, node/edge totals and file-page digests. Publication ID is the digest of its canonical content manifest excluding itself. Native source evidence and observation boundaries remain separate.
3. Define indexed storage records: node descriptor by node key; incoming/outgoing adjacency pages of at most 256 edges; sorted node catalogue pages of at most 256 nodes. Individual decoded files are at most 256 KiB; descriptors at most 8 KiB. Reject oversized individual records; do not split opaque IDs/text into hidden payload fields.
4. File paths derive only from fixed literals, enum values, numeric page indices and SHA-256 identity keys. The manifest cannot supply arbitrary file paths. API-supplied native IDs never become file names.
5. Treat artifact hashes as integrity/reproducibility checks, not authenticity, source truth or authorization. Root is trusted operator-controlled storage; source manifest/run identity checks still apply.
6. Decode every control record with the same duplicate/depth/finite/exact-key policy: run-state pointers, quota reservations, commit manifests, snapshot manifests, catalogue pages, integrity indexes and graph records. Bound each file before decode and pack variable-size pages by both byte count and at most 256 records. Current-observation replacement and stub upgrades are performed by Task 4's explicit merge before encoding; conflicting duplicates remaining within the finished publication are invalid.

### Required Interfaces and Contracts
Artifacts are immutable sibling research documents. No runner JSON, archived result, replay marker, SQL table, or observer wire protocol changes. No arbitrary migration of unknown artifact schemas. A corrupted snapshot fails as a unit; no partially decoded data is returned as complete.

### Error Handling and Logging
Codes: `unsupported_lineage_schema`, `lineage_record_oversize`, `lineage_digest_mismatch`, `lineage_identity_conflict`, `lineage_scope_mismatch`. Error responses/logs never include raw paths or decoder exception text.

### Tests / Acceptance / Verification
`test_lineage_codec.py`: byte-identical round trips across insertion order, unsupported/extra fields, duplicate conflicting records, duplicate JSON keys at the top level and inside nested metadata/indexes, valid hash over a duplicate-key payload still rejected, maximum depth and depth+1, invalid UTF-8/trailing JSON/scalar envelopes, wrong run/identity owner, oversized JSON/page/record, nonfinite numbers, manifest tampering, path-shaped IDs, forbidden bodies and byte-packed short pages. Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_lineage_codec.py --cov=simulation --cov-report=term-missing -q`. Acceptance: schema and every artifact/control decoder are deterministic and strictly bounded.

## Phase Risks and Mitigations
- Existing analysis IDs are not owner-qualified: add an additive explorer entrypoint, preserve all legacy graph/metric contracts.
- Trust laundering through artifacts: evidence class and source policy are mandatory and never downgraded.

## Phase Completion Checklist
- Analytical adapters and strict codec pass; progress lives only in `index.md`.
