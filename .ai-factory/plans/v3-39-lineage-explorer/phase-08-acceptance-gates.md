# Phase 8: Scientific acceptance, security and bounded-work gates

Plan: [index.md](index.md)  
Tasks: 15–16  
Depends on: Tasks 1–14

## Objective
Prove the four requested questions and all eight graph families work end-to-end, while preserving scientific and privacy boundaries.

## Current-Code Evidence

| Path | Existing coverage | Relevance |
|---|---|---|
| `tests/unit/test_knowledge_genealogy_queries.py` | Teaching, unresolved transmission, dead holders and combinations | Real native provenance fixtures. |
| `tests/unit/test_institution_lineage.py` | Absolute identity, transformation/split/reappearance, pruning | Native institution oracle. |
| `tests/unit/test_offices_succession.py` | Vacancy, disputes and predecessor roles | Preserve subjective succession semantics. |
| `tests/unit/test_experiment_bm.py` | Existing generational experiment | Representative first-party scenario, not only fabricated graph fixtures. |
| `tests/unit/test_generational_cli.py`; `tests/unit/test_generational_execution.py` | Actual CLI/archive dispatch and configurator context | Production installation and archive-result truthfulness, not just helper tests. |
| `tests/unit/test_cultural_evidence_capture.py` | Capture isolation | Pattern for observing without changing outcomes. |
| `tests/architecture/test_causal_debugger_boundaries.py` | Read-only assembly and GET-only routes | Template for dedicated lineage boundary tests. |
| `tests/architecture/test_import_boundaries.py` | AST and import-linter gates | Preserve package allowlists without new exceptions. |

## Files to Change
Create `tests/unit/test_lineage_end_to_end.py`, `tests/unit/test_lineage_limits.py`, `tests/unit/test_lineage_noninterference.py`, and `tests/architecture/test_lineage_explorer_boundaries.py`. Extend the new API/source/storage tests rather than duplicating their fixtures.

## Task 15: Verify the four questions and every family through persisted HTTP data

### Intent / Implementation Steps
1. Build a deterministic fixture using public native constructors and existing scenario helpers: Alice→Bob→Cara genealogy, Bob dead while Cara lives; a taught technique that later combines; a physical record copy chain; owner-local narrative branch/merge with a claimed original event; native institution episodes with a split; office succession with a disputed successor.
2. Project and publish using production codec/writer, reconstruct a fresh reader/API service, and page only through HTTP. No query-time access to the fixture runner or original ledgers. Check every result's scope, boundary, evidence class, source coverage and edge semantics.
3. Question mapping:
   - “Who learned this technique from whom?”: qualified knowledge/technology entry, ancestors, analytical or selected-owner view; distinguish inferred transmission, supported uptake, failed teaching and unresolved teacher.
   - “Which living agents descend from Alice?”: objective genealogy, Alice's stable agent root, descendants, `living_only=true`; Cara matches through dead Bob, with Bob only as context.
   - “How did this institution develop?”: analytical episode root, ancestors/descendants, native continued/transformed/split/reappeared relations, confidence code and ambiguity; no official institutional registry.
   - “Which narrative variants descend from the original event?”: narrative claimed-event root, descendants; keep claimed-origin and variant-parent edges distinct. Analytical aggregation never equates testimony with event truth.
4. Cover record, mentorship and office families explicitly as separate requests, not just indirectly through a combined knowledge graph. Verify page size 1 and multi-page unions, missing ancestor stubs, and exact earlier boundary before the technique/child/successor appears.
5. Execute a small actual BM scenario from public `generational_comparison_scenario(seed=23, max_ticks=12)`, selecting condition `bm-low-vs-high-teaching-treatment`, with capture on and off through the real `execute_generational_assignment` and Task 9 optional installer. Preserve seeds/configuration/assignment identity and the existing plain-generational execution recipe. Assert scientific result/replay identity; then read its committed objective/owner views through a fresh API after discarding runner/session state. Disabled modes stay unavailable; do not silently enable them to manufacture lineage. Task 9's separate real CLI smoke covers flag dispatch and installation.
6. Extend the native-source end-to-end fixture across B1/B2/B3: failed teaching then supported uptake, Bob shared between teacher/learner analytical roles without merging private entries, concrete resolution of a missing parent, archival after source eviction and later reappearance. Verify old pinned snapshot pages remain unchanged, new pages show current status, and the detailed teaching chain survives a new reader without any `MentorshipAudit` fallback. Node and snapshot catalogue pages use their own cursors, including a concurrent catalogue append.

### Required Interfaces and Contracts
Acceptance runs through native source → normalization → immutable publication → fresh reader → bounded traversal → cursor → HTTP. Fixture IDs are assertions, not names parsed by the service. Compare output independently with native kinship/knowledge/institution oracles where applicable.

### Requirement Evidence
The user's four questions, eight requested families and two-client contract; core authority axioms and historical source limits discovered during planning.

### Error Handling and Logging
Capture and corrupt-source failures must be tested at the HTTP boundary; log capture with sentinel secrets/text verifies no payload, cursor, root path or raw exception leaks.

### Tests / Acceptance / Verification
Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_lineage_end_to_end.py tests/unit/test_experiment_bm.py --cov=simulation --cov=experiments --cov=persistence --cov=api --cov-report=term-missing -q`. Acceptance: every question is answered from persisted evidence after process-local state is discarded, with uncertainty visible and no scientific behavior changes.

## Task 16: Gate adversarial limits, privacy and architecture

### Intent / Implementation Steps
1. `test_lineage_limits.py`: instrument actual filesystem read-session counts/bytes, not only mocked port-call counts, with a high-degree graph and a long cycle. Include head/commit resolution, index reads, exact native-kind/ID lookup, catalogues and adjacency in one budget. Refuse oversized files before read/decode. Prove hard ceilings apply before work/allocation, not just to output; repeated page requests each stay bounded. Assert no recursive directory walk, unfiltered exact-ID scan, full event scan, on-demand replay or graph build during HTTP requests. Use counter assertions rather than flaky wall-clock thresholds.
2. `test_lineage_noninterference.py`: capture disabled/enabled/failing yields identical events, observations, commands, subjective ledgers, runner config/result bytes and stop reasons for fixed seeded runs. Include death, admitted newborn, pending finalization/recovery, fork baseline and capture cap exhaustion. Querying must never call a mutation API or change capture state.
3. Test owner/run/family/class/cursor substitution, kind-specific analytical actor versus entry identity, disabled debug, changed credentials between pages, missing sources, path-shaped IDs, symlinks, file corruption and log sentinels. Unauthorized requests must never open a read session. Reject duplicate/deep/nonfinite JSON in graph and control files, embedded institution JSON and each signed cursor purpose. Add reader concurrency during every writer commit stage and restarted quota/reservation recovery; pending exact-B files are never visible as committed and abandoned bytes remain charged.
4. `test_lineage_explorer_boundaries.py` follows current AST tests: simulation lineage modules cannot import API/analysis/experiments/persistence/observer/infrastructure or retain `WorldEngine`; API cannot import analysis/experiments; persistence cannot import analysis or private world. Analytical graph assembly/publication orchestration is experiment-only; concrete filesystem writes correctly remain in persistence behind the publisher port, and trusted research_runner wires those ports. All new lineage routes are GET-only. Allow operational cryptographic randomness only in API cursor composition, never domain identity.
5. Assert no new SQL migration/head, command, observer semantic, metric family, runner/result schema, cognitive mode, capability ownership or API version. Existing `multi_hop_testimony_tracking` and `institutional_economy` remain unimplemented/fail-closed. Keep legacy debugger route tests and V1/V2 scientific gates intact.

### Required Interfaces and Contracts
No rule relaxation/import-linter exception is needed. `LineageReadPort` cannot publish. DTOs do not carry raw `WorldEvent`, complete memory/checkpoint bodies or a live runner. Existing SQL integrations remain unchanged; a filesystem-only feature must not falsely claim a new PostgreSQL durability gate was run.

### Error Handling and Logging
Every tested failure emits safe stable codes; never source body/path/DSN/credential/traceback content. Expected missing evidence and bounded truncation are not server errors. Corrupt source is not “empty.”

### Tests / Acceptance / Verification
Run:

```sh
uv run --frozen --python 3.12.14 pytest tests/unit/test_lineage_limits.py tests/unit/test_lineage_noninterference.py tests/architecture/test_lineage_explorer_boundaries.py tests/architecture/test_causal_debugger_boundaries.py tests/architecture/test_import_boundaries.py tests/architecture/test_observer_isolation.py --cov=simulation --cov=api --cov=persistence --cov-report=term-missing -q
uv run --frozen --python 3.12.14 pytest tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py tests/unit/test_alembic_head_pin.py --cov=simulation --cov-report=term-missing -q
```

Acceptance: authorization, actual physical-read/byte bounds, crash-consistent discovery, cumulative quotas, import isolation and baseline identities all hold without weakening tests or disabling coverage. These are planned checks, not tests run by the improve invocation.

## Phase Risks and Mitigations
- Synthetic-only tests conceal real schema mismatches: include existing generational scenario and native constructors in end-to-end tests.
- “Bounded output” conceals unbounded work: count source reads/bytes and prohibit scans/replay in query tests.

## Phase Completion Checklist
- All family acceptance, noninterference, privacy and architecture gates pass; update `index.md` only.
