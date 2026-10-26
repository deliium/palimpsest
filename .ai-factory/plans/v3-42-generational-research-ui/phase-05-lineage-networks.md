# Phase 5: Genealogy, teaching and knowledge/technology lineage

Plan: [index.md](index.md)  
Tasks: 12–14  
Depends on: Tasks 7–9

## Objective
Deliver qualified, bounded, evidence-labelled networks over the existing lineage explorer—not new social ontologies.

## Current-Code Evidence
| Path | Symbols | Why it matters |
|---|---|---|
| `clients/research-ui/src/graphs/ResearchGraph.svelte` | Cytoscape component props | Reuse engine; add selection/layout/individual class support |
| `clients/research-ui/src/views/GraphsPanel.svelte` | `expandLineage` | Existing debugger lineage is not the general eight-family explorer |
| `src/api/routes/lineage.py` | snapshots/nodes/traverse/participants | Existing signed/pinned graph surface |
| `src/simulation/lineage_models.py` | qualified refs and graph budgets | Owner/class/family/native kind all affect identity |
| `clients/godot-observer/fixtures/protocol/generational/` | lineage graph/nodes/participants fixtures | Representative protocol evidence |

## Files to Change
Modify `clients/research-ui/src/graphs/ResearchGraph.svelte`; introduce `src/research/lineage.ts`, `src/graphs/LineageGraph.svelte`, `src/views/LineagePanel.svelte`, `src/views/TeachingPanel.svelte`, `src/views/TechnologyPanel.svelte`, and sibling tests. Integrate panels in RunOverview/lineage family selector; old GraphsPanel remains available.

## Task 12: Implement genealogy and reusable lineage explorer
### Intent
Provide objective parent/child ancestry and the shared infrastructure for all lineage families.
### Implementation Steps
1. Discover family capabilities and snapshots per run/evidence/scope owner; use inspection descriptors for objective families and explicit `include_restricted=true` under debug for private/analytical ones. Default genealogy to objective at selected finalized boundary. For an explicit lineage publication, page snapshots until the exact ID is found within the client budget, retain boundary/digest and query only that boundary; absent publication is unresolved, not latest. API nodes/traverse do not accept a publication-ID query parameter. Validate returned snapshot ID/digest against the requested selection. Otherwise offer earlier captured boundaries explicitly and disclose requested/captured time; never relabel earlier capture as current.
2. Build bounded root-node list and explicit traversal expansion with direction/depth. Keep query `scopeOwnerId` distinct from ref `identity_owner`: analytical scope omits `owner_id` but native-owner equality is mandatory when matching an owned analytical node. Use supplied validated node key for direct traversal where available; otherwise bounded native kind/ID lookup selects exactly the returned qualified ref. Never use first native-ID match across owners. Cytoscape node/edge IDs are returned node/edge keys. Preserve returned unresolved nodes; do not invent parent facts.
3. Extend ResearchGraph with `onNodeSelect`, `onEdgeSelect`, layout selection and per-element epistemic/status styles. Genealogy/DAG defaults to built-in breadthfirst directed layout; arbitrary networks use existing COSE. No new layout plugin. A cycle is surfaced and rendered with graph fallback, never silently removed.
4. Render inspector with qualified ref, status, owner/class, evidence refs, source tick and coverage. Distinguish matched nodes from context-only connectors. `living_only` applies only to genealogy and must retain dead connecting ancestors supplied by the server.
### Required Interfaces and Contracts
Default traversal depth2; local caps500/1500 and server smaller caps win. Explicit Load more/expand only. Family/owner/class/snapshot changes reset graph. Initial nodes→traverse requests must retain the discovered expected publication/digest even before a signed continuation exists; a mismatch clears the attempted merge and offers restart. No edge joins by names, term digest alone or unqualified native ID. Genealogy does not imply care/trust/inheritance rights.
### Requirement Evidence
User genealogy; `docs/lineage-explorer.md` qualified identities, connectors, capture limits and snapshot pinning.
### Error Handling and Logging
No snapshot is unavailable, not complete-empty. Expired cursor offers restart at the pinned selector. Logs family/class/count/stop reasons only; no labels/evidence payloads.
### Tests
Real lineage fixtures; dead connector, same native ID in different owners/classes/families, missing root, cycles, partial/unresolved nodes, prefix rejection, snapshot changes, budget stop and keyboard selection. Analytical identity owner must never become API scope owner; debug discovery must reveal restricted families; an initial publication change between node lookup and traversal must fail without mixed data; an unavailable explicit publication must not fall back to latest.
### Acceptance Criteria
Genealogy can be navigated by root and direction; all displayed edges remain scoped and evidence-labelled.
### Verification
`pnpm --dir clients/research-ui test src/research/lineage.test.ts src/graphs/LineageGraph.test.ts src/views/LineagePanel.test.ts`.

## Task 13: Render teacher/student networks and participant evidence
### Intent
Expose mentorship and teaching attempts without claiming delivery guarantees learning.
### Implementation Steps
1. Add mentorship family mode and TeachingPanel with teacher/learner/owner filters. Use participants endpoint for evidence table; graph uses returned mentorship edges, not participant co-occurrence as a synthetic teaching relation.
2. Show attempted teaching separately from learning evidence, mutation, acquisition/update tick, hop and status. Teacher/learner clicks focus agents; content clicks open knowledge-family root using exact qualified identities.
3. Keep subjective single-owner claims separate from analytical cross-owner view. Require debug for both per existing API. Preserve `scan_limited` and allow empty page continuation; no endless autoload.
### Required Interfaces and Contracts
Teacher/student roles are observed or claimed relationships in evidence, not objective social ranks. No automatic parent→teacher connection. Cohort/generation filters use known demographic metadata only; unknown generation remains unknown, never founder0.
### Requirement Evidence
User teacher/student networks; mentorship participant API semantics and V3 mentorship blank-slate/no-copy rules.
### Error Handling and Logging
Denied debug shows permission notice; absent mentorship capture states the missing source. Counters may be logged but never content keys or evidence bodies.
### Tests
Controlled real participant fixture, empty scan page with next cursor, attempt without uptake, successful learning evidence, non-kin teacher, different owner claims and agent/content navigation.
### Acceptance Criteria
Network and table distinguish teaching attempts, claims and uptake; graph identity and paging remain stable.
### Verification
`pnpm --dir clients/research-ui test src/views/TeachingPanel.test.ts`.

## Task 14: Render knowledge genealogy, technology lineage and diffusion map
### Intent
Separate subjective practical knowledge, analytical transmission and objective physical place/capability.
### Implementation Steps
1. Reuse LineageGraph for knowledge and technology families with root, parent/child, modality and status controls. Preserve multi-parent edges and lineage roots. TechnologyPanel includes separate Lineage and Diffusion modes.
2. Diffusion loads civilization technology overlays at captured catalogue boundaries, plus objective location/region map rows at the same boundary for anchors. Show acquisition/loss, attributable/unknown/ambiguous/rediscovery and source-owner links only when returned.
3. Render deterministic SVG location/region topology, never claimed geographic coordinates. Resolve overlay placement from returned `context.anchors` first: validate location/entity/source-ref/evidence-tick agreement. An anchor at an earlier evidence tick is historical grounding and must not be presented as current holder residence; show its tick or leave current-holder placement unlocated. For current-at-boundary placement only, fallback to an objective observer frame at the exact overlay boundary, matching agent ID→entity/body ID→location, and reject prefix/current-latest substitution. Demographics has no location field and is not a grounding source. Use explicit supported layout metadata when requesting observer frames; missing/unsupported regional layout yields unlocated data, not reference-layout assumptions. Routes/regions/locations remain usable through layout-independent civilization map rows.
4. Display holder/eligible denominator and coverage; marker stepping uses captured boundaries. Diffusion arrows require attributable supported edges, not merely time order or shared technology ID.
### Required Interfaces and Contracts
Knowledge local ID/content key and technology analytical node are not interchangeable. A technology civilization row's `knowledge_id` is a content key, while its knowledge `source_ref.source_id` identifies the owner-local entry. A civilization-source focus retains row ID/content key/source refs; a lineage-source link is emitted only after resolving an exact returned qualified node ref. Do not pass a content key as a native entry ID or expect civilization `entity_id` filtering to search `knowledge_id` (it does not). Bounded overlay paging plus exact row/source matching resolves civilization technology focus. Objective backdrop does not make claims objective; no technique registry/progression tree.
### Requirement Evidence
User knowledge genealogy, technology lineage/diffusion; civilization technology row attribution and architecture's three representations of knowledge.
### Error Handling and Logging
Missing map does not hide lineage; missing grounding produces unlocated items. Request/cap counts only in logs; do not infer diffusion from incomplete frames.
### Tests
Multi-parent mutation graph, rediscovery, ambiguous source, valid published anchor, old evidence anchor distinctly labelled, exact-boundary fallback, body-versus-agent ID, missing grounding, travelling holder, stale latest location, unsupported regional layout, partial denominators and capture gaps. Include repeated content keys with different owner-local entry source refs and verify the selected technology row/node stays exact.
### Acceptance Criteria
Technology lineage and a functioning topology diffusion map are available with explicit uncertainty and matching temporal identity.
### Verification
`pnpm --dir clients/research-ui test src/views/TechnologyPanel.test.ts`; real `overlay_technology.json` fixture must be exercised.

## Phase Risks and Mitigations
Graph explosion is capped; Cytoscape is destroyed on unmount. Coordinate layout is presentation-only. Cross-owner joins require returned source evidence rather than string equality.

## Phase Completion Checklist
Network/interaction tests pass; update progress in index only.
