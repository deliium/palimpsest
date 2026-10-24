<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V3-39 Lineage Explorer Backend

Mode: ultra  
Canonical stem: `v3-39-lineage-explorer`  
Branch: `main` (existing branch; automatic branch creation disabled)  
Created: 2026-10-24  
Status: implemented; verification fixes applied 2026-10-24
Refined: 2026-10-24 (seven improvements approved by user; task IDs/statuses preserved)

## Original Request

v3-39 lineage explorer backend

Plan naming requirement:

Generate a plan whose canonical stem begins `v3-`.

Suggested stem:

v3-39-lineage-explorer

Create backend/query services for navigating historical lineage.

Support graph queries for:

genealogy  
teacher/student chains  
technology lineage  
knowledge lineage  
record lineage  
narrative lineage  
institution lineage  
office succession

Provide bounded and paginated traversal.

Support questions such as:

Who learned this technique from whom?

Which living agents descend from Alice?

How did this institution develop?

Which narrative variants descend from the original event?

Design APIs usable by both Godot and Research UI.

## Settings

- Testing: yes, confirmed by user; native-source, artifact restart, property, HTTP, privacy and scientific regression tests; coverage remains enabled.
- Logging: verbose metadata-only, confirmed; no source text, graph payloads, cursors, root paths, credentials or content-derived fingerprints in logs.
- Docs: yes, confirmed; mandatory `$aif-docs` checkpoint in Task 17.
- Git: enabled; base `main`; create branches false; no branch/worktree/commit created by planning. Later commits are checkpoints, not authorization to commit now.
- Language: English artifacts/UI; English technical terms retained.
- Workflow: slug ID, normal verification, explicit bundle path for implementation because multiple historical plans exist.
- Research: no selected research artifact; configured research file/directory absent. This plan is based on the request, project rules and focused current-code evidence, not historical plans.

## Roadmap Linkage

Milestone: "M7 — V3 Generational Civilization"

Rationale: Historical navigation makes existing generational, knowledge, cultural and institutional evidence accessible without inventing new civilization behavior or claiming remaining capability slots.

M7 remains open for `institutional_economy` and deferred kinship knowledge/cultural handoff; M6 remains open for `multi_hop_testimony_tracking`. Roadmap milestone registration/status changes belong to `/aif-roadmap`, not this planning invocation. The roadmap's older metric-count pins are historical; this plan preserves the current 136-family baseline documented in DESCRIPTION/ARCHITECTURE.

## Requirements Reconciliation

Authority: no additional source-priority hierarchy declared. User scope is implemented within project axioms and enforced package/authority boundaries. Existing source contracts refine the request; roadmap summaries are scope indicators, not detailed lineage semantics. No unresolved source conflict requires user arbitration.

| Decision / supported behavior | Source path and section | Verification evidence |
|---|---|---|
| All eight families; four example questions; one API for both clients | Original Request | Task 15 persisted HTTP acceptance; Task 14 OpenAPI cases |
| World alone owns objective facts; cognition remains owner-safe | `.ai-factory/RULES.md` Axioms; `.ai-factory/ARCHITECTURE.md` Objective authority | Task 16 AST/noninterference gates |
| Genealogy is parent→child, death-stable, not affection or inheritance rights | `src/world/kinship.py` public graph/query contract | Task 3 native-oracle tests; dead-parent/living-grandchild case |
| Teaching attempt ≠ uptake; hops start at zero; summary audits cannot reconstruct content/parent identity | `src/agents/cognition/mentorship.py:213–234,1142–1155` native entry versus audit fields | Tasks 4–5 detailed metadata, local-parent, shared-actor and ambiguity cases |
| Objective capability ≠ owner knowledge ≠ analytical transmission | `src/agents/cognition/practical_knowledge.py`; `src/analysis/knowledge_genealogy.py` graph builder | Tasks 4–5 equal-content independent roots and prefiltered historical audits |
| Records preserve physical copying/marks, not truth; narrative event roots can be testimony | `src/world/artifacts.py`; `src/observer/narrative_hops.py`; `.ai-factory/ARCHITECTURE.md` Important V3 seams | Tasks 3–5 copy/tombstone and claimed-origin cases |
| Institution graph is existing detached inference; office claims are owner-local | `src/analysis/institution_lineage.py`; `src/agents/cognition/offices.py` | Task 5 native episode parity; Task 4 disputed office |
| Historical private ledgers are not generally reconstructible from SQL snapshots/replay | `src/api/simulation_manager.py` `owner_runtime_checkpoint`; `src/persistence/debugger_sqlalchemy.py` checkpoint lookup | Tasks 7–10 artifact restart, explicit missing capture, no replay fallback |
| Simulation/API/persistence do not import analysis; outer composition publishes detached analysis | `.ai-factory/ARCHITECTURE.md` Dependency Rules; `tests/architecture/test_causal_debugger_boundaries.py` | Task 16 import gates without exceptions |
| Subjective metadata and analytical cross-owner lineage are debug-gated | `src/api/security.py`; `src/api/routes/debugger.py`; existing summary routes | Task 14 capability matrix; zero reads before authorization |
| No SQL migration or legacy schema widening | `.ai-factory/ARCHITECTURE.md` Versioned Extension Contract; `tests/unit/test_alembic_head_pin.py` | Artifact-backed index; Task 16 existing head/version gates |
| Capture is installed through the actual generational execution owner, independently of recipe configurators | `src/experiments/generational_execution.py:70–97,119–178,233–278`; `src/research_runner/cli.py` `_cmd_generational` | Task 9 real CLI/assignment tests, preserved default/custom arbiter and archive completion |
| Every read path has adapter-enforced file/byte limits; artifact/control/embedded JSON decoding is duplicate/depth aware | Task 2 read-session contract; `src/experiments/cultural_metric_artifacts.py:200–278` decoding pattern | Tasks 6–7 and 10–16 actual-file counters, malformed JSON, catalogue/cursor tests |
| Repository exploration stays focused; no excluded artifacts | `AGENTS.md`; `.ai-factory/skill-context/aif-plan/SKILL.md` | Planning touched only this plan bundle; implementation uses targeted files/tests |

### Family and evidence-class combinations

| Family | Accepted class / owner | Persisted evidence and returned graph | Invariants / scenario |
|---|---|---|---|
| Genealogy | objective; owner forbidden | Captured parent edges and agent lifecycle facts | Dead intermediate ancestors traversed; only living matches when requested |
| Mentorship | subjective; exactly one owner | Owner bonds/content acquisition records | No reciprocal bond or uptake invented |
| Mentorship | analytical; owner selector forbidden | Shared agent references plus owner-qualified teaching entries/claims | Agent-level claim chain is not proof of one content ancestry; peer-content parents need unique explicit agreement |
| Knowledge | subjective owner OR analytical no owner selector | Local practical entries OR existing analytical transmission/combination graph | Owner collisions impossible; no future audit normalization |
| Technology | subjective owner OR analytical no owner selector | Technique/capability-anchored knowledge view | Archived knowledge is not objective ability; independent roots stay separate |
| Record | objective; owner forbidden | Physical artifact copy graph and retained revisions/tombstones | Destroyed/missing source represented honestly; no marks/text |
| Narrative | subjective owner OR analytical no owner selector | Owner variants/merges OR detached evidence links and claimed event roots | No truth correction; no root-ID-only cross-owner equivalence |
| Institution | analytical; owner selector forbidden | Existing episode graph with absolute IDs, confidence codes and ambiguity | No global institution registry; labels/occupants do not establish ancestry |
| Office succession | subjective; exactly one owner | Local role identity, claim and transition records | Disputes/vacancy remain claims; no authoritative occupant or permission |

Every other family/class/owner combination is invalid before source reads. Objective endpoints need OBJECTIVE_INSPECTION; every subjective/analytical endpoint needs SUBJECTIVE_DEBUG, not an additional inspect token. All persisted data stays in a researcher read model and never feeds cognition or world state.

### Historical, activation and traversal combinations

| Input / source state | Validation and persisted state | Output / invariant | Verification |
|---|---|---|---|
| Latest, available capture | Resolve latest once; immutable publication remains unchanged | Pinned B/digest; new latest cannot shift cursor pages | Tasks 10, 12 |
| Explicit captured B | Require exact finalized boundary; events have ticks `< B` | Historical graph contains no future facts | Tasks 2–5, 15 |
| Missing B, disabled channel, no capture, pruned history | Preserve each distinct availability/coverage reason; no inferred private backfill | Unavailable or partial, never a measured complete zero | Tasks 4, 8, 10 |
| Known root, no edges | Root descriptor retained | Valid empty neighborhood | Tasks 10–12 |
| Proven missing root in available source | No write | 404 after authorization; missing source cannot prove absence | Tasks 10, 14 |
| Ancestors/descendants/both with finite budget | Indexed immutable adjacency reads only | Deterministic cycle-safe selection; native edge orientation preserved | Task 11 oracle/property tests |
| `living_only=true`, genealogy | Match filter only, historical living facts at B | Dead ancestors remain context; unknown living is not true | Tasks 11, 15 |
| `living_only=true`, other family | Reject before reads | No guessed “living technique/institution” semantics | Tasks 2, 14 |
| Graph bound reached versus response page full | Keep graph selection separate from page offset | Explicit selection stop; cursor pages cannot bypass graph limits | Tasks 11–12, 16 |
| Discovery, native-ID lookup or traversal needs several underlying files | One read session charges head/index/descriptor/page/probe work before I/O | No fresh budget at each port method; exact lookup requires paired kind/ID and index | Tasks 2, 7, 10–11, 16 |
| Snapshot catalogue append during pagination | Cursor pins committed run/scope catalogue generation, not a root/publication | Stable keyset continuation; node and traversal cursors have different closed field sets | Tasks 7, 10, 12, 14 |
| Crash after reservation/staging but before publication pointer | Reader uses only `state.json.committed_ref`; writer alone recovers explicit pending transaction | No pending B visible; abandoned slot/bytes remain charged across restart | Tasks 2, 7, 16 |
| Current entry revises or resolves an archived/stub identity | Current valid source replaces prior descriptor; missing-current evidence retains its old observed boundary | No conflicting duplicate for normal updates; no stale evidence laundered into current authority | Tasks 1, 4, 8, 15 |
| Capture/retry/failure/fork | Publish only finalized state, idempotently; separate run scope/baseline | No scientific behavior change; missing prefixes explicit | Tasks 8–9, 16 |
| Invalid/reused/expired cursor | Authenticate, verify MAC/purpose/query/scope, then source | 400/410 safe codes, no broader access or moving-source substitution | Tasks 12, 14, 16 |

## Architecture and Decisions

1. **Federated evidence, not one truth graph.** Eight families share closed DTOs, qualified identity and traversal, while objective, subjective and analytical sources remain explicit. Cross-owner stitching belongs to detached analysis and is published by trusted experiments composition.
2. **Neutral query core.** New `simulation.lineage_*` modules own immutable contracts, pure projections, capture merge/session, catalogue and traversal. One adapter-enforced read session pins the run commit, budgets every underlying file/byte and owns the verified-file cache. Exact native-ID lookup uses a separate paired-kind/ID index. No HTTP/ORM/client dependency; existing debugger routes/DTOs are unchanged.
3. **Durable indexed sibling artifacts.** `persistence.lineage_filesystem` implements separate read/publish ports. One atomic `state.json.committed_ref` transition publishes a snapshot and its discovery indexes together. Writer-only pending recovery and cumulative per-run reservations include staged/abandoned content; queries ignore pending/unreachable artifacts and never repair/reset quotas. All files use duplicate-aware, depth-32, finite/exact-key decoding; embedded institution JSON is independently checked. No SQL migration; head stays `0017`.
4. **Honest historical scope.** Optional post-finalization capture stores metadata-only lineage evidence and retains previously observed ancestry across native ledger eviction. It cannot recover unobserved past beliefs. Exact B queries never substitute latest state. Analytical graphs are published only for boundaries with detailed valid inputs, normally the completed captured boundary.
5. **Default-off production composition.** The CLI threads an independent optional installer into `GenerationalExecutionContext`/`execute_generational_assignment`, preserving cultural capture, default/custom recipe arbiters and archive completion. Detailed mentorship comes from captured entry metadata, not lossy completed audits. Analytical publication failure stays outside scientific completion/failure decisions. Fork injection installs before restored start state and publishes only the child's actual F baseline. API root is reader-only; no runner fields/capability flags are added.
6. **Bounded graph selection and purpose-specific pages.** Defaults/maxima: depth 4/32; visited nodes 200/1,000; edges 500/4,000; graph-record pages 100/200; all query/discovery source reads 128, source bytes 8 MiB; whole response 1 MiB. Signed traversal cursors pin snapshot/root/record offset; node cursors pin snapshot/filter/key; snapshot cursors pin catalogue generation/boundary key, without a fake root. No unbounded sessions. Trusted capture has a separate finite producer budget, never selectable via HTTP.
7. **Safe identity, retention and uncertainty.** Owner-local entries stay owner-qualified; analytical actor/event references can be shared, with claim ownership on edges. Current observations replace valid older descriptors, stubs upgrade in place, and absent-current evidence remains archived with its real last-observed boundary. Detailed teaching inputs exclude fingerprints. Narrative origins, institutional confidence, succession claims and unresolved history remain evidence, not world truth. No bodies or arbitrary attribute dictionaries.
8. **GET-only shared HTTP.** `/v1/simulations/{run_id}/lineage/{family}/{snapshots|nodes|traverse}` plus `/lineage/families`. Objective data uses inspect; private and analytical data uses debug. Both clients receive the same protocol; no UI code, layout, observer protocol or WebSocket changes.
9. **Compatibility unchanged.** No new world command/event, replay/codec marker, runner/result version, metric family, SQL migration, capability ownership or `/v2` route. Baseline: runner default v4/result v2, feature runner v55, 43 commands, 73 observer semantics, 136 metrics, replay-v22/codec v20 where selected, SQL `0017`, observer-protocol-v1. Preserve legacy accepted schemas and `prepare_parallel=False`.

### Deliberate exclusions and limitations

- No natural-language query/LLM endpoint, name-based identity inference, UI implementation, graph layout or network graph database.
- No general artifact-upload/import endpoint, query-triggered capture, auto-repair, garbage collection, arbitrary source path, or unbounded archive/event scan.
- No full subjective restart, retrospective recovery of uncaptured ledgers, institution/office world authority, inferred property rights, automatic kinship cultural transfer, or proof of successful teaching from attempts alone.
- Default cumulative per-run quotas are 1,000 scoped publication reservations and 256 MiB encoded artifact bytes, not 1,000 ticks or an OS disk quota. Abandoned reservations stay charged; successful identical retries are free. Capture can stop before a long run ends, especially with many owners/families. Existing publications remain usable with explicit incomplete coverage; operators choose capacity/cadence in advance.
- Cursors expire after 15 minutes. Optional shared signing key supports multi-worker/restart use; process-local keys require restarting a query after rotation.

Blocking open questions: none. New paths/symbols in phases are proposed implementation targets; existing paths/symbols are reconnaissance evidence. Each task's phase is mandatory implementation context.

Working-tree note: V3-38 runner/fork changes that appeared during initial planning are now present in the clean application tree and were rechecked during refinement. This invocation did not modify application code. Task 8 must preserve current finalization, recovery and fork behavior; evidence locations are symbol anchors, not a frozen revision.

### Approved refinement record

1. Replace audit-only teaching-chain inputs with captured safe native-entry metadata (Tasks 1, 4, 5, 9).
2. Wire capture through real generational execution and the fork baseline seam without suppressing recipe arbiters or changing scientific completion (Tasks 8, 9, 13, 15).
3. Specify adapter-enforced shared read budgets and indexed native-kind/ID discovery (Tasks 2, 7, 10, 11, 14, 16).
4. Define one atomic publication point, bounded writer recovery and consistent cumulative reservation accounting (Tasks 2, 7–9, 16).
5. Require duplicate/depth/finite/exact-key decoding across artifacts, control records, embedded institution JSON and cursor payloads (Tasks 5–7, 12, 16).
6. Separate snapshot-catalogue, node-catalogue and traversal cursor contracts and pin the right source generation (Tasks 2, 10, 12, 14).
7. Freeze kind-specific owner/actor identity and deterministic current/prior/stub merge rules (Tasks 1, 4–5, 8, 15).

All seven were approved for application. No new task IDs, progress changes, dependency changes, scope removals or implementation work were introduced. Tests named in the bundle remain planned acceptance, not verification executed by `$aif-improve`.

## Phase Index

1. [Phase 1: Contracts](phase-01-contracts.md) — Tasks 1–2
2. [Phase 2: Source projections](phase-02-source-projections.md) — Tasks 3–4
3. [Phase 3: Analysis and publication](phase-03-analysis-publication.md) — Tasks 5–6
4. [Phase 4: Storage and capture](phase-04-storage-capture.md) — Tasks 7–8
5. [Phase 5: Composition and history](phase-05-composition-history.md) — Tasks 9–10
6. [Phase 6: Traversal and pagination](phase-06-traversal-pagination.md) — Tasks 11–12
7. [Phase 7: HTTP API](phase-07-http-api.md) — Tasks 13–14
8. [Phase 8: Acceptance gates](phase-08-acceptance-gates.md) — Tasks 15–16
9. [Phase 9: Docs and verification](phase-09-docs-verification.md) — Tasks 17–18

## Cross-Phase Dependencies

- Tasks 1–2 define identities, scope matrix, budgets, ports and B semantics for every later task.
- Task 3 depends on 1–2; Task 4 depends on 1–3; Task 5 depends on 1–4; Task 6 depends on 1–5.
- Task 7 depends on 1–6; Task 8 depends on 1–7. Reader and publisher capabilities remain separate.
- Task 9 depends on 3–8; Task 10 depends on 1–2 and 6–9. Producer/discovery cannot invent missing history.
- Task 11 depends on 1–2, 7 and 10; Task 12 depends on 6–7 and 10–11.
- Task 13 depends on 1–12; Task 14 depends on 10–13 and existing API security contracts.
- Task 15 depends on 3–14; Task 16 depends on 1–15; Task 17 depends on 1–16; Task 18 depends on 1–17.
- Execute sequentially by task ID. No new parallel agents/worktrees are required for implementation.

## Tasks

### Phase 1: Contracts
- [x] Task 1: Define qualified identities and closed graph DTOs ([details](phase-01-contracts.md#task-1-define-qualified-identities-and-closed-graph-dtos))
- [x] Task 2: Freeze source ports, budgets, and historical semantics ([details](phase-01-contracts.md#task-2-freeze-source-ports-budgets-and-historical-semantics)) (depends on 1)

### Phase 2: Source projections
- [x] Task 3: Project genealogy and physical record ancestry ([details](phase-02-source-projections.md#task-3-project-genealogy-and-physical-record-ancestry)) (depends on 1–2)
- [x] Task 4: Project mentorship, knowledge, technology, narratives, and offices ([details](phase-02-source-projections.md#task-4-project-mentorship-knowledge-technology-narratives-and-offices)) (depends on 1–3)

### Phase 3: Analysis and publication
- [x] Task 5: Adapt knowledge, technology, narrative and institution inference ([details](phase-03-analysis-publication.md#task-5-adapt-knowledge-technology-narrative-and-institution-inference)) (depends on 1–4)
- [x] Task 6: Specify and implement canonical lineage snapshot serialization ([details](phase-03-analysis-publication.md#task-6-specify-and-implement-canonical-lineage-snapshot-serialization)) (depends on 1–5)

### Phase 4: Storage and capture
- [x] Task 7: Implement immutable indexed filesystem publications ([details](phase-04-storage-capture.md#task-7-implement-immutable-indexed-filesystem-publications)) (depends on 1–6)
- [x] Task 8: Capture lineage only after complete finalization ([details](phase-04-storage-capture.md#task-8-capture-lineage-only-after-complete-finalization)) (depends on 1–7)

### Phase 5: Composition and history
- [x] Task 9: Wire an opt-in trusted producer and analytical publication ([details](phase-05-composition-history.md#task-9-wire-an-opt-in-trusted-producer-and-analytical-publication)) (depends on 3–8)
- [x] Task 10: Resolve publications, catalogue roots, and retain honest coverage ([details](phase-05-composition-history.md#task-10-resolve-publications-catalogue-roots-and-retain-honest-coverage)) (depends on 1–2, 6–9)

### Phase 6: Traversal and pagination
- [x] Task 11: Implement deterministic cycle-safe neighborhood traversal ([details](phase-06-traversal-pagination.md#task-11-implement-deterministic-cycle-safe-neighborhood-traversal)) (depends on 1–2, 7, 10)
- [x] Task 12: Bind opaque continuation to snapshot, query and authorization scope ([details](phase-06-traversal-pagination.md#task-12-bind-opaque-continuation-to-snapshot-query-and-authorization-scope)) (depends on 6–7, 10–11)

### Phase 7: HTTP API
- [x] Task 13: Compose lineage reader, catalogue, query service and strict API schemas ([details](phase-07-http-api.md#task-13-compose-lineage-reader-catalogue-query-service-and-strict-api-schemas)) (depends on 1–12)
- [x] Task 14: Add GET routes with evidence-specific authorization ([details](phase-07-http-api.md#task-14-add-get-routes-with-evidence-specific-authorization)) (depends on 10–13)

### Phase 8: Acceptance gates
- [x] Task 15: Verify the four questions and every family through persisted HTTP data ([details](phase-08-acceptance-gates.md#task-15-verify-the-four-questions-and-every-family-through-persisted-http-data)) (depends on 3–14)
- [x] Task 16: Gate adversarial limits, privacy and architecture ([details](phase-08-acceptance-gates.md#task-16-gate-adversarial-limits-privacy-and-architecture)) (depends on 1–15)

### Phase 9: Docs and verification
- [x] Task 17: Complete the mandatory documentation checkpoint ([details](phase-09-docs-verification.md#task-17-complete-the-mandatory-documentation-checkpoint)) (depends on 1–16)
- [x] Task 18: Run complete checks and reconcile implementation with this plan ([details](phase-09-docs-verification.md#task-18-run-complete-checks-and-reconcile-implementation-with-this-plan)) (depends on 1–17)

## Commit Plan

- **Commit 1** (after Tasks 1–3): `feat(lineage): define query contracts and objective projections`
- **Commit 2** (after Tasks 4–6): `feat(lineage): project subjective and analytical provenance`
- **Commit 3** (after Tasks 7–9): `feat(lineage): persist opt-in finalized lineage snapshots`
- **Commit 4** (after Tasks 10–12): `feat(lineage): add bounded historical traversal and cursors`
- **Commit 5** (after Tasks 13–15): `feat(api): expose evidence-scoped lineage explorer queries`
- **Commit 6** (after Tasks 16–18): `test(lineage): verify isolation limits and document explorer`

These are implementation checkpoints only. Respect configured local-commit/no-push preferences if commits are later requested.

## Definition of Done

- All 18 tasks and their phase acceptance/verification requirements are satisfied; phase files carry no progress checkboxes.
- Eight families and all four questions pass source-to-artifact-to-fresh-reader-to-HTTP acceptance, including a representative existing generational scenario.
- Selection and response pagination are deterministic, bounded in work and bytes, snapshot-pinned, cycle-safe and authorization-scoped.
- Catalogue and exact-ID paths obey the same adapter-accounted query budgets; all three cursor purposes remain stable through catalogue appends.
- Objective, owner-subjective and analytical claims remain distinct; missing/pruned/disabled/unavailable evidence cannot appear as complete measured zero or verified truth.
- Read-only clients and queries cannot mutate the world, start capture, reconstruct private past, confer institutional permissions or reveal restricted metadata with inspect credentials.
- Durable artifact capture is optional, bounded, atomic and scientifically observational; failure or process loss never implies subjective runtime restart support.
- Actual CLI/assignment and fork installation are covered, detailed teaching chains survive a fresh reader, pending publications are invisible, quotas survive restarts, and normal observation revisions/stub upgrades preserve honest history.
- Existing schema/version/head/metric/command/protocol pins and fail-closed unowned flags are unchanged.
- Mandatory docs checkpoint, default suite with coverage, Ruff, mypy and explicit `$aif-verify` completed; unrun optional checks reported honestly.

## Resume

Review this bundle, then run `$aif-implement` with explicit plan path `.ai-factory/plans/v3-39-lineage-explorer/index.md`. Read this index plus the linked complete phase for the current task; update progress only here. Planning stops without implementation.
