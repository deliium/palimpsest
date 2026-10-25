<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V3-41 Godot Civilization Overlays

Mode: ultra  
Canonical plan name: `v3-41-godot-civilization-overlays`  
Branch: `main` (existing; no branch/worktree creation)  
Created: 2026-10-25  
Status: implementation partially complete; Phase 1 (Tasks 1–3) verified; next: Task 4 (finalized capture)

Verification (Tasks 1–2): 159 coverage-enabled contract/projection/legacy/architecture tests passed; scoped Ruff and mypy checks passed. API routes, capture/publication, Godot overlays, and browser/release verification remain pending.

Verification (Tasks 1–3): 269 coverage-enabled contract/API/replay/legacy/settings/architecture tests passed; scoped Ruff and mypy checks passed. GET map pages are inspection-authorized, cursor-pinned, byte/row bounded, and independently serialized. Capture/publication, Godot overlays, and browser/release verification remain pending.

Refined: 2026-10-25 — eight approved code-backed refinements and one contract-order correction; all18 task IDs and unchecked statuses preserved.

## Original Request

v3-41 Godot civilization overlays

Plan naming requirement:

Generated plan artifact MUST begin `v3-`.

Suggested stem:

v3-41-godot-civilization-overlays

Extend the Godot observer for long-horizon societal change.

Visualize:

regions  
migration  
multiple settlements  
trade flows  
collective projects  
public goods  
archives  
technology diffusion  
institution locations where physically meaningful

Add optional overlays for:

population  
culture  
technology  
migration  
social groups  
institutions

Clearly distinguish:

OBJECTIVE

SUBJECTIVE

ANALYTICAL / INFERRED

A cultural trait frequency is an analytical overlay, not objective terrain.

Add historical playback support so researchers can visually watch:

settlement growth  
population movement  
technology spread  
institution appearance/disappearance

At high playback speed, aggressively simplify animations while preserving state correctness.

Maintain zero-install Web deployment.

## Settings

- Testing: yes; coverage-enabled Python/API/architecture checks, pinned headless Godot, real exported-browser/image acceptance and resource/state-equivalence tests.
- Logging: verbose, metadata-only; counters, ticks, layers and closed reason codes. No credentials, DSNs, messages, marks, memories, prompts, private labels, payload surrogates or raw cursors.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 18.
- Preferences: explicitly confirmed by user for this invocation; M7 linkage, tests, verbose safe logging and docs.
- Language: English UI/artifacts, technical terms retained.
- Git: enabled, base `main`, branch creation false, skip push prompt true. Planning creates only this bundle; no commits/pushes or implementation.
- Plan IDs: slug; this directory begins `v3-` exactly as required. Verification mode: normal; unmet browser/deployment prerequisites remain explicit release blockers.
- Research: no configured RESEARCH.md or research directory exists; no research snapshot is incorporated. Existing code/docs are compatibility evidence, not an invented research source.
- Execution: read this manifest then the complete linked phase before each task; progress checkboxes live here only. Use the explicit bundle path because multiple active plan artifacts exist.

## Roadmap Linkage

Milestone: "M7 — V3 Generational Civilization (in progress)"

Rationale: expose existing V3 physical, demographic, cultural, technological and institutional evidence in the read-only Godot Web observer, including honest historical availability and presentation-only high-speed playback.

This work does not close M7, own `institutional_economy`, implement kinship cultural/knowledge handoff, or own M6 `multi_hop_testimony_tracking`. No roadmap milestone is created or closed during planning; later roadmap changes use its owner workflow.

## Requirements Reconciliation

Authority: the explicit request defines feature scope, subject to repository `AGENTS.md`, `.ai-factory/RULES.md`, `.ai-factory/rules/base.md` and `.ai-factory/ARCHITECTURE.md` authority/privacy/compatibility boundaries. Executable schemas/code determine accepted existing inputs; roadmap items indicate direction. New visualization heuristics/budgets below are explicit plan decisions, not claims that existing requirements already prescribe them. No unresolved behavioral source conflict was found.

| Decision / supported combination | Source path and section | Verification evidence |
|---|---|---|
| Keep Godot `4.7.2-stable`, Compatibility renderer, nonthreaded Web and prebuilt published-image workflow | Original Request; `clients/godot-observer/export/pins.env`, `project.godot`, `export_presets.cfg`; `docs/development.md` | Task17 actual WASM/browser/image checks and unchanged pin tests |
| Read-only/location graph; no world coordinates, social authority or client command path | Original Request; ARCHITECTURE — Objective authority/Dependency Rules | Tasks2/10–13/16, unchanged journal/control state and GET-only browser requests |
| Expose richer physical facilities through independent sidecars, not silent legacy frame widening | `src/observer/contracts.py` versus `src/api/observer_schemas.py` and `observer_service.py::_frame_out`; ARCHITECTURE — Versioned Extension Contract | Tasks1–3 actual HTTP JSON and legacy fixture equality |
| Historical physical state uses selected replay prefix; never join live metadata | `src/api/observer_service.py::_history`, `_history_through_event`; `observer_replay_context.py`; `docs/observer.md` — cursor semantics | Tasks2/3 prefix/full-boundary and real checkpoint tests |
| Current labels/latest metric selection is not historical overlay evidence | `docs/observer.md` — subjective historical limitation; client `session.gd` overlay request paths | Tasks4–8 exact capture, stale-reply and missing-boundary tests |
| OBJECTIVE, SUBJECTIVE and ANALYTICAL are separate scopes/styles with owner identity | Original Request; client `presentation/evidence_class.gd`; ARCHITECTURE — Memory/testimony | Tasks7–12 privacy/scope/UI badge tests |
| Physical location population/infrastructure is objective; settlement candidates are a disclosed heuristic | Original Request refined by absence of settlement entities in `ObjectiveScene`; ARCHITECTURE — no scripted society | Tasks5/10 four-boundary criterion, two locations, gap/reactivation tests |
| Only completed exchanges count as trade; no gift-to-market, co-location-to-route or present-to-past endpoint inference | Original Request; `src/world/events.py::ExchangeCompleted`, `Given`; `src/observer/adapt.py` | Tasks5/11 event-time/item-kind tests |
| Projects/public goods/repositories are physical facts, not leadership/access rights/Library institutions | ARCHITECTURE — Important V3 seams; `src/world/collective_projects.py`; `src/observer/contracts.py` | Tasks2/10 contribution/benefit/custody tests |
| Culture frequencies are analytical, require complete relevant carrier denominators and exact identities | Original Request; `docs/cultural-evolution-metrics.md` — windows/populations/provenance; `InventoryBoundary` | Tasks5/11 absent versus empty/partial/zero-denominator tests |
| Technology diffusion requires retained attributable knowledge evidence; knowledge is not performability | ARCHITECTURE — practical knowledge; `TraitPresence`, `TransmissionEdge`, lineage qualified identities | Tasks5/11 before-acquisition and ambiguous-source tests |
| Institutions remain private concepts or detached inferred episodes; physical association needs an exact typed witness | Original Request; `institution_concepts.py::_observe_projects`, `_observe_repositories`; architecture — offices/institutions | Tasks4/5/12 positive exact-observation witness, unplaced/testimony/forged-anchor tests |
| Missing/cadence/evicted evidence is not disappearance or zero prevalence | Cultural metrics docs; lineage docs — Capture and availability | Tasks4–8/12/14 gap/transition tests |
| Analytics are composed in experiments/research_runner and published immutably; API/simulation never import analysis | ARCHITECTURE — Dependency Rules; `experiments/lineage_publication.py`, `research_runner/lineage_composition.py` | Tasks5–7/16 port/import/read-only filesystem tests |
| CLI production hooks and completed-adoption gates must be explicit; browser-targeted capture requires durable runs in the API's database | `experiments/matrix_runner.py::MatrixBatchDependencies`, `run_one_assignment`, three skip/adoption paths; `generational_execution.py::GenerationalExecutionContext` | Tasks6/15 actual durable CLI paths, all adoption exits, no rerun on missing capture |
| Event completeness is independent of snapshot cadence and cannot be inferred from an empty recovered TickResult | `simulation/runner.py::recover_pending_finalizations`; `simulation/persistence.py::TickJournalRepository`; `world/events.py` payloads | Tasks4/5 metadata-only receipts, journal-proven recovery, cadence3 and canary tests |
| Repeated institution exports need absolute-key normalization before lifecycle/lineage calculation | `analysis/institutional_decay.py::institution_decay_rows_from_ledgers`; `institution_lineage.py::compute_institution_lineage` duplicate/future checks | Task5 cumulative duplicate/pruning/conflict and boundary-mapping tests |
| Hashing is child-to-parent and pagination budgets include physical reads and nested row details | `persistence/lineage_filesystem.py` chunked catalogue and `_read_budgeted`; explicit sidecar design | Tasks1/6/7 known-answer digest DAG and measured file/byte/scan/progress tests |
| New analytical/owner-level catalogues require debug, even though existing aggregate metric endpoints use inspect | `src/api/routes/inspection.py` metrics route; lineage scope policy; explicit conservative plan decision | Task7 separate credentials, no preauthorization count leaks; existing metric auth unchanged |
| High speed simplifies actual session rendering, not scientific event history; helper-only coverage is insufficient | Original Request; `playback.gd` policy and unused coalescer; session ingestion | Tasks13/17 integrated slow/fast digest equality and bounded queue tests |
| Automatic playback must display cursor-matched bundles without canceling its own sidecars; semantic equality differs from LOD drawing equality | `session.gd::_begin_seek`, `_cancel_http`, `_apply_sought_frame`; `generational_source.gd::on_frame` | Tasks8/13/17 delayed-sidecar intermediate display, bounded deadline and common-LOD tests |
| Real UI scene and existing population signals must survive new controls/timeline nodes | `clients/godot-observer/scenes/ui/ui_layer.tscn`; `scripts/ui/ui_layer.gd`; `generational_panel.gd` | Tasks9/14 actual packed-scene instantiation and synchronized population controls |
| Civilization mounts/capabilities are delivered through a concrete optional published-image override | `run.sh` starts only `compose.yaml`; base API service has no civilization mount | Tasks6/17/18 `compose.civilization.yaml`, same database/read-only bind and unchanged plain startup |
| Real runs and constructed fixture evidence remain distinguishable | `observer_graphical_scenario.py` synthetic tick1000; `tests/compose/start_generational.py`, `seed_generational_evidence.py` | Tasks15/17 real256-tick producer plus separately identified constructed presentation packs |
| Current baseline remains43 commands/73 semantics/136 metric families/Alembic0017; no new core schema or capability | DESCRIPTION latest V3-39 and ARCHITECTURE baseline; older roadmap counts are dated | Task16 gates and unchanged pins |

### Supported combinations and state transitions

All GETs persist nothing. Producer publication is the only new write path and is outside the API. `B` is a full finalized boundary; `(T,S)` is an inclusive objective event prefix. New route/schema details are committed in Phases1/3/5.

| Input / selectors | Validation / retained state | Output / transition / invariant | Verification |
|---|---|---|---|
| Legacy or capture-off run, inspect allowed | Existing scene only, no new capture | Base observer and objective map work; unsupported layers disabled/unavailable, not zero | Tasks2/3/8/17 |
| Regions configured / unassigned locations | Exact config assignments/routes | Region envelopes/routes remain distinct; no invented adjacency | Tasks2/10 |
| Journey preparing/capacity-wait/arrived/ended | Actual participants/events at selected cursor | Bodies at origin until arrival; failed/ended distinct from completed movement | Tasks2/5/11/13 |
| Objective full boundaryB | Scene/revision/run/world match | Exact map plus matching captured layers if available | Tasks3/7/8 |
| Objective prefix(T,S) | Sequence requires tick and committed high water | Objective map only; captured layers require finalized boundary | Tasks3/8/14 |
| Accepted full frame with last-event resume cursor | Determine B from accepted frame world tick, not resume-pair presence | Correct B catalogue/private lookup | Tasks3/8 |
| Two locations satisfy settlement policy / one has missing streak | Four complete occupancy boundaries and intact structure atB | Two candidates or explicit censored/missing evidence; no objective settlement entity | Tasks5/10 |
| ExchangeCompleted versus proposed/withdrawn/gift | Count each committed completed exchange once; source event identity | Trade summary separate from transfer categories; no invented routes/value | Tasks5/11 |
| Complete living carrier coverage / empty eligible population | Exact trait and boundary, denominator known | Count/proportion or null if denominator0; analytical style | Tasks5/11 |
| Missing/disabled/partial cultural inventory | Unknown owners remain unknown | Partial known counts with null complete proportion; no0% substitution | Tasks5/9/11 |
| Technology attributable acquisition / unknown source / speech-only | Qualified identity and no future evidence | Edge only for attributable acquisition; unknown/rediscovery separate; speech not learning | Tasks5/11 |
| SUBJECTIVE groups/technology/institutions, debug enabled | Required selected owner; exact B; own publication rows | Owner-labeled scoped claims; no peer merge | Tasks7–9/12 |
| ANALYTICAL settlements/trade/culture/technology/groups/institutions, debug enabled | No scope owner; qualified provenance retained | Explicit inferred measurement/classification, not terrain/world permission | Tasks5/7/9–12 |
| OBJECTIVE migration captured summary | Inspection; no scope owner; exact B/window | Committed journey facts and counts, not inferred trade | Tasks5/7/11 |
| Unsupported layer/evidence/owner combination | Reject before reads | 400; no implicit promotion/downgrade | Tasks1/7/8 |
| Inspect-only or debug disabled/revoked | Auth before restricted metadata/counts | Private layers restricted/cleared; objective playback persists | Tasks7–9/16/17 |
| Institution has exact observed physical witness / opaque digest only | Validate source/tick/owner/observation-local identity | Evidence-site pin versus unplaced row; never guessed headquarters | Tasks4/5/12 |
| Confirmed institution transition / capture gap | Existing lifecycle policy/coverage, no future episode end | Appearance/disappearance marker versus uncertainty band | Tasks5/12/14 |
| Missing exact boundary/cadence gap | Never nearest/latest fallback | Explicit unavailable or user-selected recorded-boundary playback | Tasks6–8/14 |
| Empty source-filter page with continuation | Bound scan and advance last scanned key | Load more; no false complete-empty or hidden rows | Tasks3/7/8 |
| Row/byte/client-render cap | Bound independently, preserve coverage/totals | Truncated status and explicit continuation/counts, not scientific truncation | Tasks3–8/10–14 |
| Publication replaced/gone/expired/corrupt | Match digest/filter/purpose/expiry |410 explicit restart;503 corruption; no mixed-page cache | Tasks6–8/14 |
| Run/branch/owner/credential/seek changes in flight | Epoch/key every response including errors | Old replies ignored; private cache cleared as scoped | Tasks8/13/17 |
| Active run before finished publication | Objective state still usable; no published analytical history | Captured layers `publication_pending`/unavailable; no pretend live analytics | Tasks6–9 |
| Completed resume with missing required capture | No runner replay/backfill permitted | Preflight failure; scientific artifacts untouched | Tasks6/16 |
| Capture installed with existing lineage/cultural capture | Compose installers/finalizers explicitly | All independent sinks preserved; same scientific result | Tasks4/6/16 |
| Cadence>1 with complete journal-derived receipt coverage | Receipts collected every finalized tick; sampled inventories remain sparse | Flow window may be complete while private/settlement continuity is censored; no cross-channel gap repair | Tasks4/5 |
| Recovery has empty TickResult.events | Verify exact tick commit/count and bounded journal page sequence | Proven known-empty versus recovered receipts versus explicit event gap | Task4 |
| Cumulative institution exports repeat historical samples | Absolute owner/pattern/observation key, first-seen boundary, retention metadata separate | Deduplicated prefix lifecycle/lineage; conflicts fail and no future/pruning leakage | Task5 |
| Scientific completion exists but required publication failed/missing | Check each skip/adoption exit; preserve existing completion marker/archive | Non-ready sidecar/workflow failure, no scientific rerun or artifact deletion | Tasks6/15/16 |
| Non-durable matrix/generational config with capture root requested | Preflight before execution; never silently switch persistence/config | Unsupported prerequisite error; browser-serving capture requires API-visible durable run | Tasks6/15 |
| Unsupported path-dependence grouped capture invocation | Explicit CLI validation before start | Nonzero unsupported-combination error, no partial capture | Task6 |
| >=8× or backlog /16× | Reducer or authoritative replacement state remains correct | No transient animation;16× aggregates labels; scientific event pages intact | Tasks13/17 |
| Sidecars lag automatic forward targets | One active bundle/one latest desired target; fixed2second presentation deadline | Display matching intermediate bundles or explicit timed-out layers; no request-cancellation starvation | Tasks8/13/17 |
| Compare1× versus16× outputs | Same loaded scopes/cursor for semantic comparison; same paused LOD for draw comparison | Semantic equality preserved while intentional fast glyph/label differences remain allowed | Tasks13/17 |
| Published Web image/no local Godot | Existing static export and same-origin capabilities | Browser runs without editor/native/threads installation | Tasks17/18 |
| Optional civilization Web deployment / plain startup | Override mounts configured host root read-only with capabilities and persistent key; plain run.sh root-off | Published image works without editor/build/manual base-Compose edits; producer writes separately | Tasks6/17/18 |

## Architecture and Decisions

1. **No simulation feature expansion.** No commands/events/semantic types/metric families, coordinates, engine roles, permissions, social entities, capability ownership, SQL migration or core runner/result/replay/observer protocol changes. New settings/sidecar schemas are read-model composition only.
2. **Two data paths.** Objective map sidecars project existing detached scenes at arbitrary supported replay cursors. Optional finished-run historical publications retain scoped owner evidence and detached analytical results at exact finalized boundaries. Do not reconstruct private past state from objective replay or latest metrics.
3. **Explicit production producer.** Composition-only capture defaults off. `research_runner` wires separate installer/finalizer hooks through ordinary matrix and generational execution, with durable factories and all three matrix skip/adoption validations. Browser-targeted capture requires existing durable configs in the API's configured database; it does not mutate scientific configs. Publish after successful scientific completion through separate writer ports; publication failure preserves scientific completion, records non-ready status and never triggers backfill/rerun. API reads `PALIMPSEST_CIVILIZATION_ROOT` through a read-only port. API-created runs without publications remain objective-only. No live analytical publication/offline-only browser path/durable subjective restart is claimed.
4. **Independent endpoints.** GET `/v1/simulations/{run_id}/observer/civilization/{map,catalogue,overlays,markers}` use independent `observer-civilization-*-v1` schemas; storage uses `civilization-snapshot-v1`/`civilization-catalogue-v1`. Existing strict observer/lineage schemas and WS envelopes remain untouched.
5. **Bounded/secure.** Default100/max200 rows,2,000 decoded/scanned rows,16physical-files/12MiB physical reads and1MiB HTTP/request; <=64KiB metadata/row, <=1MiB/200rows per shard, <=64MiB encoded boundary, depth32;10,000 boundaries/1,000,000 retained rows/receipts/256MiB cumulative capture/storage per run. Inline refs/member details have explicit caps without changing scientific totals. Hash shards→boundary manifests→catalogue pages/index→atomic commit ref, never cyclic parent digests. Signed purpose-specific cursors bind every scope/filter/publication. New analytical/subjective routes require debug; independent capability credentials stay memory-only in client.
6. **Disclosed definitions.** Settlement candidates use four-boundary occupancy plus intact infrastructure; trade counts completed exchanges only; cultural prevalence uses exact inventory identities/denominators; technological diffusion follows attributable knowledge evidence. These are not new world entities, hidden rankings or shared reward scores.
7. **Physical grounding is optional evidence.** Institutions remain private concepts or analytical episodes. Capture an exact typed physical witness from native observed project/repository evidence when possible; never decode/invert anchors or testimony. Missing placement is a valid nonspatial row. No artificial origin marker.
8. **Client layering.** Separate strict parser/source/panel and facilities/flow/belief layers; reuse accepted cursor, positions, population and credential infrastructure. Instantiate new panel/timeline packed scenes through the actual `scenes/ui/ui_layer.tscn`; preserve existing generational nodes/signals and synchronize population controls through one boolean. Rendering separates canonical semantic state from LOD draw plans. All data controls default off; mixed-evidence categories have explicit submodes/badges. Marker API/schema work is in Task7 before the Task8 parser, not deferred to Task14 UI.
9. **State-correct visible speed.** >=8× snaps/suppresses effects;16× aggregates labels. Apply scientific transitions in order or adopt authoritative frames. Automatic history play stages one frame plus matching first-page sidecars, with one navigation epoch/latest target and a2second presentation deadline; explicit user seeks still cancel older epochs. Display intermediate coherent bundles rather than perpetually canceling sidecar requests. Live execution/journal progression is independent. Compare semantic state at a common loaded cursor and drawings only at a common paused LOD. Bounded queues/caches prevent request storms.
10. **Zero-install.** Preserve pinned4.7.2-stable editor/templates, nonthreaded Compatibility Web and ordinary published-image `run.sh`. Optional `compose.civilization.yaml` supplies a read-only host root, persistent cursor key and capability settings against the same database, using `docker compose -f compose.yaml -f compose.civilization.yaml up -d --wait`. No manual edits to base Compose, editor in runtime, threads/native extensions or researcher build requirement. Real Chromium/WASM acceptance is a release gate.

Capture keeps whitelisted event receipts every finalized tick independently of snapshot cadence. Missing recovery event evidence and missing private snapshots have separate coverage; neither repairs the other. Institution samples are normalized by absolute owner/pattern/observation identity, with first-seen boundaries and retention metadata separated so cumulative exports do not duplicate rows or leak later pruning into earlier views.

## Phase Index

1. [Phase 1: Objective map](phase-01-objective-map.md) — Tasks1–3
2. [Phase 2: Captured history](phase-02-captured-history.md) — Tasks4–6
3. [Phase 3: Query and client](phase-03-query-and-client.md) — Tasks7–9
4. [Phase 4: Spatial overlays](phase-04-spatial-overlays.md) — Tasks10–12
5. [Phase 5: Playback and fixtures](phase-05-playback-and-fixtures.md) — Tasks13–15
6. [Phase 6: Verification and Web](phase-06-verification-and-web.md) — Tasks16–18

## Cross-Phase Dependencies

- Task2 depends on1; Task3 on1/2. Objective sidecar remains independently useful without captured history.
- Task4 depends on1/2; Task5 on4; Task6 on4/5. Capture inputs/calculator output/store schemas must agree before publication.
- Task7 depends on1/3/6 and includes catalogue/overlay/marker HTTP contracts; Task8 on3/7; Task9 on8. Moving marker backend work from14 into7 removes the previous forward contract dependency. The parser consumes actual complete API shapes, not guessed future payloads.
- Task10 depends on2/8/9; Task11 on5/8/9/10; Task12 on4/5/8/9/10. All overlays share cursor/anchor/evidence contracts.
- Task13 depends on8/10/11/12 and orchestrates Task8's bundle-preparation primitives; Task14 on5/7/8/9/13 and consumes the already implemented marker route for UI/navigation only; Task15 on1–14. Fixtures exercise actual durable CLI producer/consumer/adoption paths.
- Task16 depends on1–15; Task17 on13–16; Task18 on16/17 and the mandatory docs checkpoint.
- Execute in indexed order; do not mark a downstream task complete on the strength of unexecuted tests or synthetic-only screenshots.

## Tasks

### Phase 1: Objective map

- [x] Task 1: Define independent civilization contracts ([details](phase-01-objective-map.md#task-1-define-independent-civilization-contracts))
- [x] Task 2: Project physical regions, facilities and location population ([details](phase-01-objective-map.md#task-2-project-physical-regions-facilities-and-location-population)) (depends on1)
- [x] Task 3: Serve bounded objective map pages at exact replay cursors ([details](phase-01-objective-map.md#task-3-serve-bounded-objective-map-pages-at-exact-replay-cursors)) (depends on1,2)

### Phase 2: Captured history

- [ ] Task 4: Capture bounded finalized owner and physical evidence ([details](phase-02-captured-history.md#task-4-capture-bounded-finalized-owner-and-physical-evidence)) (depends on1,2)
- [ ] Task 5: Compose detached analytical and scoped historical layers ([details](phase-02-captured-history.md#task-5-compose-detached-analytical-and-scoped-historical-layers)) (depends on4)
- [ ] Task 6: Publish immutable history and expose opt-in CLI composition ([details](phase-02-captured-history.md#task-6-publish-immutable-history-and-expose-opt-in-cli-composition)) (depends on4,5)

### Phase 3: Query and client

- [ ] Task 7: Serve exact captured overlay pages and catalogues ([details](phase-03-query-and-client.md#task-7-serve-exact-captured-overlay-pages-and-catalogues)) (depends on1,3,6)
- [ ] Task 8: Parse and fetch cursor-pinned civilization layers ([details](phase-03-query-and-client.md#task-8-parse-and-fetch-cursor-pinned-civilization-layers)) (depends on3,7)
- [ ] Task 9: Add optional evidence-labeled controls and visible availability ([details](phase-03-query-and-client.md#task-9-add-optional-evidence-labeled-controls-and-visible-availability)) (depends on8)

### Phase 4: Spatial overlays

- [ ] Task 10: Render regions, settlement growth and physical civic facilities ([details](phase-04-spatial-overlays.md#task-10-render-regions-settlement-growth-and-physical-civic-facilities)) (depends on2,8,9)
- [ ] Task 11: Render migration, exchange, culture and technology diffusion ([details](phase-04-spatial-overlays.md#task-11-render-migration-exchange-culture-and-technology-diffusion)) (depends on5,8,9,10)
- [ ] Task 12: Render scoped groups and physically grounded institution evidence ([details](phase-04-spatial-overlays.md#task-12-render-scoped-groups-and-physically-grounded-institution-evidence)) (depends on4,5,8,9,10)

### Phase 5: Playback and fixtures

- [ ] Task 13: Integrate high-speed level of detail without dropping state ([details](phase-05-playback-and-fixtures.md#task-13-integrate-high-speed-level-of-detail-without-dropping-state)) (depends on8,10,11,12)
- [ ] Task 14: Add bounded historical change markers and capture-aware navigation ([details](phase-05-playback-and-fixtures.md#task-14-add-bounded-historical-change-markers-and-capture-aware-navigation)) (depends on5,7,8,9,13)
- [ ] Task 15: Build representative producer-backed civilization fixtures ([details](phase-05-playback-and-fixtures.md#task-15-build-representative-producer-backed-civilization-fixtures)) (depends on1–14)

### Phase 6: Verification and Web

- [ ] Task 16: Enforce authority, privacy and compatibility gates ([details](phase-06-verification-and-web.md#task-16-enforce-authority-privacy-and-compatibility-gates)) (depends on1–15)
- [ ] Task 17: Prove exported-browser playback and bounded resource use ([details](phase-06-verification-and-web.md#task-17-prove-exported-browser-playback-and-bounded-resource-use)) (depends on13–16)
- [ ] Task 18: Document evidence semantics and complete the release handoff ([details](phase-06-verification-and-web.md#task-18-document-evidence-semantics-and-complete-the-release-handoff)) (depends on16,17)

## Commit Plan

- **Commit1** after Tasks1–3: `feat(observer): expose cursor-correct civilization map sidecars`.
- **Commit2** after Tasks4–6: `feat(research): publish retained civilization overlay history`.
- **Commit3** after Tasks7–9: `feat(observer): fetch scoped civilization history and evidence controls`.
- **Commit4** after Tasks10–12: `feat(godot): render evidence-scoped civilization overlays`.
- **Commit5** after Tasks13–15: `feat(godot): add bounded historical civilization playback`.
- **Commit6** after Tasks16–18: `test(observer): verify civilization overlays in zero-install web export`.

These are proposed implementation checkpoints, not permission to commit/push during planning. Keep each checkpoint buildable with its available tests and do not include unrelated user changes.

## Definition of Done

- Every requested category has an implemented positive visualization path plus explicit unavailable/empty/partial behavior, with real source identity and correct evidence class. Culture is never objective terrain, and institutions without physical evidence remain unplaced.
- Objective map uses the exact displayed replay cursor. Captured history is exact-boundary, publication-pinned, owner/capability-safe and never silently replaced by live/latest/nearest data. Missing intervals do not imply extinction/collapse.
- Completed exchanges, migration, knowledge attribution, project/public-good facts and physical repositories retain their distinct meanings. No scripted civilization, global cultural/institutional registry, objective membership, new simulation coordinates or authority leak exists.
- Fast playback demonstrably displays intermediate matching bundles, invokes integrated LOD, preserves semantic state/event navigation and stays within request/cache/node/effect limits. Fast/slow drawings are compared at common paused detail, not falsely equated while intentional LOD differs. Backward seeks and source/owner/credential changes clear stale visuals.
- Default-off capture/publication has an actual trusted producer and read-only API consumer; no backfill, hidden rerun or durable subjective restart claim. Legacy V2/V3 regression/architecture/version pins remain unchanged.
- Pinned headless checks and actual exported Chromium/WASM published-image browser tests pass. Researchers use the existing zero-install browser workflow with no local Godot/editor/build requirement. Missing prerequisites remain release blockers.
- Docs checkpoint, supported-combination tests, real-versus-constructed fixture provenance and measured verification handoff are complete. Only verified tasks are checked here.

## Open Questions, Existing Work and Boundaries

No blocking implementation question remains in this plan. Material interpretations are committed explicitly: analytical settlement heuristic, completed-exchange-only trade, typed institution evidence-site associations, finished-run publication and conservative debug authorization for new inferred layers. Expanding to objective settlements/institutions, inferred trade transport routes, live analytics, durable subjective restart or unsupported grouped-protocol capture requires a separately scoped change.

Existing dirty files observed during planning: `clients/godot-observer/scripts/net/generational_source.gd`, `scripts/net/http_client.gd`, `scripts/net/lineage_source.gd`; `src/api/routes/observer.py`; `src/simulation/engine.py`, `observer_demographics.py`, `observer_facts.py`. Preserve and reconcile these as user work, not disposable scaffolding. Do not reset/revert them or assume the clean main branch is equivalent to the current source.

The final status check showed additional concurrent edits across Godot UI/session/rendering, demographic/lineage API/replay/persistence, their tests/docs and the observer image workflow. This planning invocation changed only this bundle. Before Task1 execution, refresh the relevant scoped diffs/symbols against the current worktree; preserve all external edits. If that refresh reveals a material contract conflict with this plan, stop and report it rather than overwrite concurrent work or silently redesign the plan.

The V3-40 bundle is relevant dependency evidence: its task checkboxes are complete although its header still says planned. The actual implemented code and fixtures were inspected; this stale status metadata is not a reason to redo/reset V3-40. ROADMAP historical metric counts and older DESCRIPTION paragraphs are also dated; current executable contracts/latest sections determine compatibility. No source artifact is edited to resolve these documentation gaps during planning.

Planning/refinement validation covers bundle structure, task links, detail, source evidence and requirements only. No application test, Godot export, browser benchmark or deployment was executed by these invocations. Stop after refinement; implementation requires an explicit next command.

## Approved Refinements

The user approved all eight findings and the marker-contract ordering correction in this improve pass. No tasks were added/removed or marked complete; the Original Request remains byte-for-byte unchanged.

| Approved finding | Applied edits |
|---|---|
| Production execution/adoption/durability gaps | Tasks6/15 wire ordinary matrix and generational hooks/factories, all three skip/adoption exits, durable API-visible prerequisites and separate publication-readiness failure without rerun/deleting completion. |
| Cadence/recovery/raw-event ambiguity | Tasks4/5 define metadata-only receipts, continuous event-source accounting independent of snapshots, bounded journal-backed recovery and honest gaps/canary tests. |
| Duplicate cumulative institution samples | Task5 defines absolute keys, first-seen boundary, semantic conflict rules, retention/pruning metadata separation and explicit lifecycle→lineage input with correct observation/boundary mapping. |
| Recursive digest ambiguity | Tasks1/6/7 define child-first hashing and a committed catalogue-index pin without parent/self hashes inside children. |
| Unbounded physical reads/nested details | Tasks1/6/7 specify indexed shards, physical/decoded budgets, inline caps, correct byte-page progress and measured-read tests. |
| Overlay starvation and incompatible LOD equality | Tasks8/13/17 stage bounded matching bundles, preserve automatic request epochs, use a2second presentation deadline, prove intermediate display and separate semantic/common-LOD draw equality. |
| Incorrect UI scene/population wiring | Tasks9/14 use actual UI scene path, new explicit packed scenes and one synchronized population state while retaining generational nodes/signals. |
| Undelivered optional production mount/settings | Tasks6/17/18 add/test/document `compose.civilization.yaml` with read-only bind, same database, persistent key and capability settings; ordinary published-image startup remains unchanged. |
| Marker contract ordering | Task7 owns marker DTO serialization/route/cursor/API tests before Task8 parsing; Task14 owns timeline integration and navigation only. |
