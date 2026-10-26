<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V3-42 Generational Research UI

Mode: ultra  
Branch: main (existing branch; no branch creation)  
Created: 2026-10-26  
Status: implemented; mandatory verification recorded 2026-10-26 (Godot/browser compose gates unexecuted: prerequisites absent)  
Refined: 2026-10-26 — seven approved task improvements and two explicit dependency fixes  
Canonical stem: `v3-42-generational-research-ui`

## Original Request
v3-42 generational research UI

Plan naming requirement:

Use the canonical `v3-` plan prefix.

Suggested stem:

v3-42-generational-research-ui

Extend the existing Research UI.

Add:

population timeline  
demographic charts  
genealogy  
cohort comparison  
teacher/student networks  
knowledge genealogy  
technology lineage  
technology diffusion maps  
cultural trait timelines  
vocabulary evolution  
semantic drift  
migration flows  
society comparison  
historical narrative lineage  
institution timeline  
office succession  
institution lineage  
economic exchange networks  
collective project history

Provide generation-based navigation in addition to tick navigation.

Support deep links with Godot:

run  
tick  
agent  
location  
institution  
narrative  
technology

Maintain objective/subjective/analytical visual distinctions.

## Settings
- Testing: yes; unit, mounted component, API, architecture, Godot and browser acceptance.
- Logging: verbose metadata-only. DEBUG counts/state/reason codes; INFO bounded completion; WARN safe failures. Never payloads, raw URLs, credentials, private terminology, narratives or fingerprints as payload surrogates.
- Docs: yes; mandatory `$aif-docs` checkpoint at Task24.
- Language: English artifacts/UI; preserve English technical terms.
- Git: enabled; base `main`; `create_branches=false`; no worktree, commit or push during planning. Suggested commits below are implementation checkpoints only.
- Verification: normal project default; preserve coverage and distinguish unavailable external prerequisites from passing gates.
- No selected research source: `.ai-factory/RESEARCH.md` is absent. Code reconnaissance is evidence, not a new research-requirements artifact.

## Roadmap Linkage
Milestone: "M7 — V3 Generational Civilization"

Rationale: Extend research presentation over existing generational, cultural, institutional and civilization evidence without acquiring simulation authority or claiming a remaining capability flag. M7 remains open for `institutional_economy` and deferred kinship handoff; this UI plan cannot close the whole milestone. M6 `multi_hop_testimony_tracking` remains unrelated and unowned.

## Requirements Reconciliation
Authority: the user's scope and accepted preferences constrain the deliverable; repository `AGENTS.md`, rules and architecture constrain implementation. Existing versioned wire schemas/code define accepted data shapes. Roadmap summaries indicate milestone scope, not detailed behavioral contracts. Historical counts in roadmap/older description sections are dated, not current pins. This invocation does not edit source requirements.

| Decision / supported behavior | Source path and section | Verification evidence |
|---|---|---|
| Extend existing Svelte5/Vite/Cytoscape SPA at `/research/`; preserve old views | Original Request; `clients/research-ui/package.json`, `src/router.ts`, `src/views/RunOverview.svelte` | Tasks1–3 mounted router and legacy route tests |
| WorldEngine alone mutates objective state; presentation cannot command it | `.ai-factory/RULES.md` — Axioms; `.ai-factory/ARCHITECTURE.md` — Dependency Rules / Objective authority | Task23 read-only/AST tests and V1/V2 regression |
| Generation/cohort/genealogy/community differ; markers use independent discovery high-water H, not view T; cohort identity includes generation and entry tick | `docs/generational-runner.md`; `src/simulation/observer_demographics.py` — `_cohort_key`, `project_generation_markers`; `docs/observer.md` | Tasks1,8–11 repeated cohort IDs and T=0→Next→back tests |
| Qualified lineage separates scope owner from required native identity owner; publication selection resolves through snapshots, not an unsupported query key | `docs/lineage-explorer.md`; `src/simulation/lineage_identity.py` — owner matrices; `src/api/routes/lineage.py` — query allowlists | Tasks1,7,12,20–22 exact root/ref/publication tests |
| Objective map and scoped civilization overlays retain coverage/grounding | `src/simulation/civilization_rows.py`; `src/api/civilization_schemas.py` | Tasks14,15,17–20 fixture/browser tests |
| Cultural inventories/seed-block intervals use existing `values.rows_json` and comparison payloads; nested JSON is bounded/duplicate-aware; runtime completion and legacy binding differ | `docs/cultural-evolution-metrics.md`; `src/experiments/cultural_metric_artifacts.py`; `src/experiments/matrix_manifest.py` — completion; `src/analysis/cultural_metric_comparison.py` — payload/row decoding | Tasks4,5,7,11,15 real encoded measurement/completion/binding tests |
| API imports neither experiments nor analysis; no calculator execution in HTTP | `.ai-factory/ARCHITECTURE.md` — Dependency Rules | Tasks4–6 architecture tests |
| Matrix API exported fixture shape differs from actual producer: accept separate known schemas | `src/api/routes/research_matrix.py` expects `experiment-matrix-v1`; `src/experiments/matrix_manifest.py` writes `matrix-manifest-v1` plus state/completion docs; `tests/unit/test_benchmark_research_ui_artifacts.py` uses synthetic exported tree | Task4 real producer + legacy exported-tree tests; no producer rewrite |
| No arbitrary historical subjective restart; semantic view uses retained checkpoint records | `src/api/routes/observer.py` — owner checkpoint checks; `.ai-factory/DESCRIPTION.md` — V3-38; bounded naming/symbolic sense records | Tasks6,16 tick mismatch/trimmed history/as-of display |
| Links actually seek/select, distinguish lineage versus civilization focus and mount a real inspector | Original Request; `src/observer/research_ui_state.py`; Godot `origin.gd`, `session.gd`, `lineage_source.gd`, `scripts/ui/ui_layer.gd`, `research_ui_link.gd` | Tasks1,7,20–22 shared corpus plus session-dispatch/scene/browser proof |
| Published anchors are evidence-at-tick grounding, not current residence; missing regional layout stays unlocated | `src/simulation/civilization_models.py` — `CivilizationAnchor`; `src/api/observer_demographic_schemas.py` — no locations; `src/persistence/civilization_filesystem.py` — entity filters | Tasks14,17 anchor/fallback/regional and repeated content-key tests |
| Optional new services cannot break minimal persistence/replay attachment | `src/api/app.py` — `_attach_persistence_services`; `.ai-factory/patches/2026-10-26-01.22.md` — Prevention | Tasks4,6,23 bare-app/lifespan tests plus `test_observer_population_replay.py` |
| Scientific/API/protocol version baseline stays unchanged | `.ai-factory/ARCHITECTURE.md` — Versioned Extension Contract and V3-39 section | Task23 pin/compatibility tests |

### Supported combinations
Validate selectors before reads. Persist only credential-free selection in browser URL/history; data results remain bounded ephemeral memory. No row below permits server writes or capture activation.

| Inputs / selectors | Validation and state | Output / transition | Invariant / evidence |
|---|---|---|---|
| Lifecycle enabled + full boundary | Nonnegative tick; pinned revision | Objective totals/charts, complete zero allowed | Never sum repeated page totals; Task10 |
| Lifecycle off / replay unavailable | Retain requested tick | Distinct unavailable reason; tick navigation remains | Not zero/dead population; Task10 |
| Generation without tick | Discover markers at independent run high-water H; URL gains selected tick T | Actual seek tick or unresolved generation; keep H after seek | No schedule arithmetic/denied-entry marker or loss of Next after backward seek; Tasks8,9 |
| Explicit tick plus generation | Tick wins; generation retained | Exact tick, mismatch warning when necessary | Overlapping generations are not exclusive eras; Task9 |
| Tick+sequence prefix | Complete event cursor required | Objective prefix reads; finalized capture panels offer explicit full-boundary transition | No silent seek; Tasks9,21 |
| Objective genealogy/record/map | Inspection credential | Qualified objective nodes/rows | No affection/meaning inferred; Tasks12,19 |
| Subjective lineage/history | Debug; required owner; available snapshot/checkpoint | Owner claims and retained history, actual time shown | No other-owner leak/historical relabelling; Tasks6,12,16,20 |
| Analytical lineage/civilization | Debug; lineage scope owner absent but required native identity owner retained; source-specific publication | Retrospective inference with exact root/row identity | No forbidden scope/query keys or world registry; Tasks7,12,14–22 |
| Stored metrics/cultural comparison | Inspection; known schema, units/window/provenance | Published values; stored seed-block intervals only | p05/p95 remain percentiles; Tasks4,11 |
| Cultural inventory | Debug; explicit matrix/cell/run, pair binding/digest | Paged metadata, coverage and gaps | No backfill; Tasks5,15 |
| Runtime versus exported matrix | Separate guards; runtime fingerprint/completed-state/mandatory completion proof; legacy missing bindings disclosed | Both readable unchanged with `runtime_bound|legacy_unverified` metadata | State/self-digests alone do not prove completed execution; Tasks4,5 |
| Nested cultural measurements/comparisons |16MiB/depth32 duplicate-aware `rows_json`; exact scientific selectors and row status | Numeric values/coverage/censoring and stored interval status | PARTIAL not pooled/inferred; no invented comparison self-digest; Tasks4,7,11,15 |
| Empty / partial / unavailable / forbidden | Preserve coverage/continuation/capability | Distinct notice and optional Load more | Missing denominator is null, not0; Tasks3,8 |
| Changed publication/checkpoint / stale response | Signed cursor and client epoch |409/restart or obsolete response ignored | No mixed owner/publication data; Tasks5–8 |
| Entity focus with run/optional tick | One ID; source/family/row, native kind, scope versus identity owner, separate publications; generation resolved first | Seek, dispatch to focus controller, mount exact inspector or explicit unavailable | Subjective concepts use civilization, offices use succession lineage; no label matching; Tasks20–22 |
| Reused cohort ID | Full `(run,generation,entry_tick,cohort_id)`; separate navigation generation | Exact comparison selection and URL reload | No first-match/label merge; Tasks1,11 |
| Evidence anchor versus current map position | Match anchor source/tick; exact-boundary objective fallback only | Historical anchor labelled by evidence tick or current witness/unlocated | No latest-location or reference-layout substitution; Tasks14,17 |
| Within-run/cross-run comparison | Explicit independent ticks/markers, units/bases/policy | Descriptive facets; no unsupported pooling | Same generation number does not align age/community; Tasks11,17 |

## Architecture and Decisions
1. **Presentation extension.** Keep Svelte5 runes, Vite, Cytoscape and current shell. Use SVG charts/topology maps plus accessible tables, no new framework/chart/state library. Preserve old views, capabilities and mounts.
2. **Minimal read gaps only.** Reuse demographic/marker, eight-family lineage, civilization, owner projections, metrics and matrix routes. Add cultural artifact GET/projection and retained semantic-history GET. No new capture channel, archive format, runner field, analytical family or event fold.
3. **Honest history.** Uncaptured boundaries are unknown; retained semantics are as-of an available checkpoint with possibly missing prefix. Current labels/narrative projections are not restored historical state. Every requested surface remains reachable and has a populated tested case plus clear prerequisites.
4. **Bounded loading.** URL is canonical selection. Keep marker-discovery high-water H separate from view tick T; refresh H explicitly. Four concurrent reads, max32 sampled boundaries per load, explicit paging, local graph caps500/1500, smaller server caps win. No unbounded per-tick replay or scanning every matrix/run.
5. **Qualified evidence.** Preserve run/family/class/native kind/native ID/identity owner separately from API scope owner, plus source/row/publication identity. Analytical lineage omits scope owner while preserving owned native refs; subjective concept focus uses civilization, not an invalid lineage family. Cohort selection is a composite generation/entry/ID tuple. Seven epistemic classes remain; no label-based inference.
6. **Safe artifact reads.** Fixed matrix-root paths,64MiB/depth32 outer bounds,16MiB/depth32 nested measurement JSON,2MiB projection replies, duplicate-aware decoding, pair identity and signed cursors. Runtime completion is mandatory for runtime-bound reads; legacy missing bindings stay unverified. Thread-offload reads, never call recovering manifest-store open. Validation does not replace science or break optional persistence attachment.
7. **Functional Godot links.** Shared corpus; tick-only seek and pending agent focus repaired. A session-owned bounded focus controller with explicit response dispatch and mounted ui_layer/main inspector resolves source-specific institution/narrative/technology metadata. No unsupported lineage publication query; publication selection resolves through snapshot discovery and exact returned identity checks.
8. **Stable baseline.** Default runner/result v4/v2; latest feature runner v55; selected replay-v22/codec v20;43 commands;73 observer semantics;136 metric families; Alembic0017; `/v1`; `observer-protocol-v1`. New independent presentation schemas do not widen legacy wire IDs. Unowned flags remain fail-closed.

### Requested surface coverage
| Feature | UI home / interaction | Data / evidence | Tasks |
|---|---|---|---|
| Population timeline | Population, point→tick | Demographic totals / objective |9,10 |
| Demographic charts | Stage/generation bars and tables | Counts / objective |9,10 |
| Genealogy | Lineage parent/child traversal | Genealogy / objective |12 |
| Cohort comparison | Composite cohort selection + Matrix | Objective census; stored analytical measurement rows |1,11 |
| Teacher/student networks | Teaching mode, participant/content clicks | Mentorship / subjective, analytical |13 |
| Knowledge genealogy | Multi-parent knowledge roots | Knowledge / subjective, analytical |14 |
| Technology lineage | Technology Lineage | Technology / subjective, analytical |14 |
| Technology diffusion maps | Technology Diffusion, boundary stepping | Scoped overlays + objective map |14,17 |
| Cultural trait timelines | Culture dimension/basis/trait | Captured carriage/analysis |15 |
| Vocabulary evolution | Language Vocabulary, owner/generation | Captured inventory + descriptive summaries |15 |
| Semantic drift | Language Semantics, retained transitions | Subjective history + analytical aggregate |6,16 |
| Migration flows | Route/window/participant selection | Migration / objective |17 |
| Society comparison | Candidates or2 explicitly aligned runs | Analytical groups/metrics; separate private claims |17 |
| Historical narrative lineage | Root/variant/source inspector | Subjective/analytical lineage; objective record existence |16 |
| Institution timeline | Institutions Timeline; civilization-source concept focus | Private concepts; analytical lifecycle |20 |
| Office succession | Institutions Succession | Subjective office claims |20 |
| Institution lineage | Institutions Lineage | Analytical episode lineage |20 |
| Economic exchange networks | Economy network/detail | Analytical completed-event summary |18 |
| Collective project history | Projects progress/receipt table | Objective state and accepted receipts |19 |
| Generation and tick navigation | Shared navigator; discovery H versus view T | Actual admissions / objective |1,2,8,9 |
|7 Godot focus dimensions | Share/open + Godot inspector | Credential-free, class/owner retained |1,21,22 |
| Visual distinctions throughout | Text/badges/pattern/source/window/owner | Per series/node/edge/row, not just heading |3,9,12–23 |

## Phase Index
1. [Phase 1: Navigation contracts](phase-01-navigation-contract.md) — Tasks1–3
2. [Phase 2: Read-only data gaps](phase-02-read-only-data-gaps.md) — Tasks4–6
3. [Phase 3: Client read layer](phase-03-client-read-layer.md) — Tasks7–8
4. [Phase 4: Population and cohorts](phase-04-population-cohorts.md) — Tasks9–11
5. [Phase 5: Lineage networks](phase-05-lineage-networks.md) — Tasks12–14
6. [Phase 6: Culture, language, narrative](phase-06-culture-language-narrative.md) — Tasks15–16
7. [Phase 7: Space, economy, projects](phase-07-space-economy-projects.md) — Tasks17–19
8. [Phase 8: Institution history](phase-08-institution-history.md) — Task20
9. [Phase 9: Godot interoperability](phase-09-godot-interoperability.md) — Tasks21–22
10. [Phase 10: Acceptance and docs](phase-10-acceptance-documentation.md) — Tasks23–24

## Cross-Phase Dependencies
| Task | Depends on | Reason |
|---|---|---|
|1|none|Canonical state/corpus |
|2|1|URL integration; introduce minimal mounted-test harness here |
|3|1|Evidence and selection agree |
|4|1|Artifact read/schema/producer compatibility |
|5|4|Reader, pair identity, cursor infrastructure |
|6|1,5|Retained projection and purpose-separated cursor primitive |
|7|3,4,5,6|Complete typed read surface |
|8|7|Cancellation/paging over validated reads |
|9|2,3,7,8|Navigator/visual primitives |
|10|9|Population dashboard |
|11|1,4,7,8,9,10|Composite cohort selection, census + stored inference |
|12|7,8,9|Qualified graph explorer |
|13|12|Mentorship evidence |
|14|12,13|Knowledge/technology/topology foundation |
|15|4,5,7,8,9|Captured culture/vocabulary |
|16|6,12,15|Retained meaning/narrative lineage |
|17|9,10,14|Reusable topology/spatial comparison |
|18|8,12,17|Trade network/window semantics |
|19|8,9,17|Sampled project history |
|20|9,12,16,17|Institution timeline/succession/lineage |
|21|1,7,9,12,14,16,20|Verified endpoint/identity mapping, actual entity/time resolution |
|22|2,21|Bidirectional links/embed fallback |
|23|1–22|All-surface acceptance/regression |
|24|23|Docs/final verification |

Execute tasks in index order. This plan does not authorize automatic parallel implementation. Task2 sets up minimal Svelte mounting in Vitest before its first component tests; Task23 expands that harness. Task14 may introduce a local topology renderer which Task17 moves into the reusable named component without behavior changes.

## Tasks
### Phase 1
- [x] Task 1: Define canonical selection and link fixtures ([details](phase-01-navigation-contract.md#task-1-define-canonical-research-selection-and-cross-client-link-fixtures))
- [x] Task 2: Integrate URL state into the shell ([details](phase-01-navigation-contract.md#task-2-integrate-url-state-into-the-existing-research-ui-shell)) (depends on1)
- [x] Task 3: Define availability and evidence discovery ([details](phase-01-navigation-contract.md#task-3-define-evidence-aware-availability-and-feature-discovery)) (depends on1)
### Phase 2
- [x] Task 4: Expose cultural metrics and real manifests ([details](phase-02-read-only-data-gaps.md#task-4-safely-expose-cultural-comparison-and-cell-metric-documents)) (depends on1)
- [x] Task 5: Add paged cultural inventory metadata ([details](phase-02-read-only-data-gaps.md#task-5-add-a-paged-metadata-projection-over-cultural-evidence-artifacts)) (depends on4)
- [x] Task 6: Expose retained semantic history ([details](phase-02-read-only-data-gaps.md#task-6-expose-retained-owner-semantic-sense-history-with-honest-temporal-limits)) (depends on1,5)
### Phase 3
- [x] Task 7: Implement typed research clients ([details](phase-03-client-read-layer.md#task-7-implement-typed-clients-and-runtime-guards-for-research-apis)) (depends on3–6)
- [x] Task 8: Implement safe paging/cancellation/sampling ([details](phase-03-client-read-layer.md#task-8-implement-cancellation-safe-paging-and-bounded-timeline-sampling)) (depends on7)
### Phase 4
- [x] Task 9: Build charts and generation/tick navigator ([details](phase-04-population-cohorts.md#task-9-build-accessible-common-charts-and-generationtick-navigator)) (depends on2,3,7,8)
- [x] Task 10: Render population and demographics ([details](phase-04-population-cohorts.md#task-10-render-population-timeline-and-demographic-charts)) (depends on9)
- [x] Task 11: Add cohort/repeated-run comparisons ([details](phase-04-population-cohorts.md#task-11-add-cohort-and-repeated-run-comparison-views)) (depends on1,4,7–10)
### Phase 5
- [x] Task 12: Implement genealogy/lineage explorer ([details](phase-05-lineage-networks.md#task-12-implement-genealogy-and-reusable-lineage-explorer)) (depends on7–9)
- [x] Task 13: Render teacher/student networks ([details](phase-05-lineage-networks.md#task-13-render-teacherstudent-networks-and-participant-evidence)) (depends on12)
- [x] Task 14: Render knowledge/technology lineage/diffusion ([details](phase-05-lineage-networks.md#task-14-render-knowledge-genealogy-technology-lineage-and-diffusion-map)) (depends on12,13)
### Phase 6
- [x] Task 15: Render culture/vocabulary timelines ([details](phase-06-culture-language-narrative.md#task-15-render-cultural-trait-timelines-and-vocabulary-evolution)) (depends on4,5,7–9)
- [x] Task 16: Render semantic drift/narrative lineage ([details](phase-06-culture-language-narrative.md#task-16-render-semantic-drift-and-historical-narrative-lineage)) (depends on6,12,15)
### Phase 7
- [x] Task 17: Render migration/society comparison ([details](phase-07-space-economy-projects.md#task-17-render-migration-flows-and-society-comparison)) (depends on9,10,14)
- [x] Task 18: Render exchange networks ([details](phase-07-space-economy-projects.md#task-18-render-economic-exchange-networks)) (depends on8,12,17)
- [x] Task 19: Render collective project history ([details](phase-07-space-economy-projects.md#task-19-render-collective-project-history)) (depends on8,9,17)
### Phase 8
- [x] Task 20: Render institution/office history and lineage ([details](phase-08-institution-history.md#task-20-render-institution-timeline-office-succession-and-institution-lineage)) (depends on9,12,16,17)
### Phase 9
- [x] Task 21: Resolve Godot deep-link seek/focus ([details](phase-09-godot-interoperability.md#task-21-extend-godot-parsing-pending-seek-and-focus-resolution)) (depends on1,7,9,12,14,16,20)
- [x] Task 22: Complete bidirectional qualified links ([details](phase-09-godot-interoperability.md#task-22-complete-outbound-links-and-research-uigodot-round-trips)) (depends on2,21)
### Phase 10
- [x] Task 23: Prove populated surfaces/regressions ([details](phase-10-acceptance-documentation.md#task-23-add-behavioral-end-to-end-and-compatibility-gates)) (depends on1–22)
- [x] Task 24: Complete docs and final verification ([details](phase-10-acceptance-documentation.md#task-24-complete-mandatory-documentation-and-final-requirements-verification)) (depends on23)

## Commit Plan
- **Commit 1**, Tasks1–4: `feat(research): define generational navigation and cultural artifact reads`
- **Commit 2**, Tasks5–8: `feat(research): add bounded inventory and semantic history clients`
- **Commit 3**, Tasks9–12: `feat(research-ui): add demographic charts cohorts and genealogy`
- **Commit 4**, Tasks13–16: `feat(research-ui): visualize teaching technology and cultural lineage`
- **Commit 5**, Tasks17–20: `feat(research-ui): add spatial economic and institutional histories`
- **Commit 6**, Tasks21–24: `feat(research): complete Godot focus links and generational acceptance`

Require task-local verification at each checkpoint. Planning makes no commits. Record implementation verification/progress notes here; phase files contain detail, not duplicate checkboxes.

## Implementation Verification Notes
- Verification remediation (2026-10-26): repaired the opt-in compose browser harness (`playwright_api` is an imported helper, not an injected pytest fixture), added a cross-panel tick/credential-hygiene workflow smoke, and confirmed `pytest -m compose tests/compose/test_generational_research_ui_browser.py` collects and skips cleanly when prerequisites are unset. Cleared all Svelte `state_referenced_locally` warnings (0 errors / 0 warnings) by syncing selection-derived panel state (and documenting intentional initial-only family selection with `untrack`); client suite remains 44 files / 202 tests. Updated `.ai-factory/DESCRIPTION.md` for the V3-42 surfaces. Compose stack and Godot execution still require the pinned image/run and Godot 4.7.2 binary.
- Tasks21–22: Godot canonical parser, tick-only/pending agent-location seek, session-owned research focus transport/panel, outbound qualified links, and iframe new-tab fallback. Godot 4.7.2 is not installed in this environment, so the headless protocol suite was not executed; TS link/embed tests pass.
- Task23–24: added populated acceptance mounts for all 12 new panels, opt-in Playwright browser acceptance, and documentation for the 19 surfaces, H vs T, composite cohorts, sampling, artifact/auth limits, and seven Godot focus dimensions.
- Verification (2026-10-26): client `npm test` 44 files / 202 tests passed; `svelte-check` 0 errors; `npm run build` passed; Python targeted suite 396 passed with coverage; `ruff check src tests`, `mypy src`, and `lint-imports` passed. `pnpm` is unavailable, so equivalent npm commands were used.
- Unexecuted external gates: Godot 4.7.2 headless editor/protocol suite (`GODOT_BIN` absent) and Docker/Playwright compose browser suite (explicit prerequisites absent). These are reported as unexecuted, not passing. Constructed presentation fixtures do not claim emergent science.
- Task20: institution timeline lanes, private office-claim succession, analytical episode lineage, and exact owner/native/publication identity; 42 client test files / 185 tests pass.
- Tasks17–19: reusable deterministic topology, migration, society lanes, exchange hubs, and sampled collective-project history over real civilization fixtures; 41 client test files / 181 tests pass.
- Tasks15–16: cultural inventory and vocabulary adapters, retained semantic-history transitions with as-of limits, narrative metadata lineage, and shared metric display adapters; 35 client test files / 167 tests pass.
- Tasks12–14: qualified lineage explorer from real Godot fixtures, reusable Cytoscape graph with keyboard/accessible nodes and cycle fallback, mentorship teaching/uptake evidence, and technology lineage/diffusion with boundary-pinned anchors and unlocated semantics; 29 client test files / 154 tests pass.
- Tasks9–11: common SVG/table primitives, generation/tick navigator with actual-admission H pinning, population dashboard, composite cohort comparison, and matrix metric facets (scalar + nested `rows_json`, intervals only when supplied with `present` status); 24 client test files / 143 tests and `svelte-check` pass.
- Tasks7–8: typed, cancellation-safe research clients, bounded duplicate-aware `rows_json` decoding, signed publication resolution, explicit paging/graph caps and marker high-water H independent of view T; 16 client test files / 119 tests and `svelte-check` pass.
- Tasks4–6: real runtime/legacy artifact binding, duplicate/nonfinite/depth/row checks, paged cultural evidence with signed cursors, and retained semantic history with as-of checkpoints; API modules import neither `analysis` nor `experiments`; 34 focused tests plus `test_observer_population_replay.py` pass.
- Tasks1–3: shared `research-links.json` corpus (18 valid / 26 invalid) round-trips in TS and Python; lineage fixtures cross-check `require_supported_scope_owner` / `require_lineage_owner_for_kind`; 51 client tests, 15 Python tests, and `svelte-check`/`tsc` pass. Minimal Svelte mount harness added in `src/test/mount.ts`; `pnpm` was unavailable, so the equivalent `npm test`/`npm run check` commands were used.

## Approved Refinement Record
2026-10-26: `$aif-improve`; user approved all seven findings and two dependency clarifications. All24 task IDs and their unchecked progress are preserved; no tasks added/removed and no implementation performed.

1. Tasks8–9: marker discovery uses pinned run high-water H independently of view T; backward navigation retains later-generation markers.
2. Tasks1,7,12,20–22: identity owner differs from scope owner; lineage publication is resolved through snapshots; concepts/technology retain their lineage versus civilization source, exact row/ref and publication identity.
3. Task21: explicit session-owned research-focus transport, response dispatch, epoch invalidation, GET allowlist and mounted ui_layer/main scene wiring; tests drive the real dispatch/UI path.
4. Tasks1,11: cohort selection preserves generation, entry tick and cohort ID, independent of generation navigation.
5. Tasks4–5,7,11,15: bounded duplicate-aware nested `rows_json` adapters, exact comparison fields/status, mandatory runtime completion proof and distinct unverified legacy export binding.
6. Tasks14,17: validate evidence anchors first, label their actual time, use exact-boundary placement fallback only, preserve regional/unlocated data and distinguish content keys from owner-local entry refs.
7. Tasks4,6,23: optional service attachment remains safe on minimal FastAPI apps; predecessor `test_observer_population_replay.py` is required in verification.

Explicit dependency clarifications: Task11→Task1; Task21→Task7. Task count/phase order/commit groups remain24/10/6. Original Request is immutable. No research rebase, scope expansion, source-requirement rewrite or remaining capability ownership was approved or applied.

## Scope Limits and Risks
- No new cognition/world behavior, scripted emergence, capability ownership, subjective restart, capture channel or analytical metric. Old uncaptured runs do not gain history.
- Semantic history is bounded retained checkpoint evidence; full arbitrary-tick subjective time travel is out of scope. Aggregate drift stays separate and analytical.
- Population/project series may be sampled and contributions truncated; visible schedule/gaps are required. Differences are not invented events/rates.
- Cultural read validation is not trusted scientific re-analysis. Input/response bounds, pair identity and event-loop offload are mandatory.
- Real producer manifests differ from existing API fixtures. Test both; never replace runtime identity with a synthetic source spec.
- Qualified graph collisions, mixed evidence, missing grounding and overlapping cumulative windows are correctness issues, not styling issues.
- Godot/Docker/browser gates need installed pinned prerequisites. Report unavailable gates as unexecuted. Constructed presentation fixtures do not prove emergent learning/institutions.
- No blocking product questions remain for this scoped plan. A new authority/availability/schema conflict must stop implementation for explicit refinement.

## Definition of Done
All24 tasks implemented/verified and each maps to one linked phase section. All19 requested surfaces have a populated behavioral test and meaningful visual/table interaction. Generation and tick navigation both work; all7 Godot focus dimensions round-trip exact time/qualified identity. Coverage, owner, evidence and temporal provenance stay visible. No unsupported history, confidence interval, social authority or economic ontology is fabricated. Existing regression/import/client/Godot and available browser gates pass; missing external prerequisites are reported. Mandatory docs and `$aif-verify` complete before closing verified progress. No whole-M7 closure or new scientific pin/capability ownership is implied.
