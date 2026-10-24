<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V3-40 Godot Generational Observer

Mode: ultra  
Canonical plan name: `v3-40-godot-generations`  
Branch: `main` (existing; no branch creation)  
Created: 2026-10-24  
Status: planned; implementation not started

Refined: 2026-10-24 — approved second-pass corrections; task IDs/count preserved

## Original Request

v3-40 Godot generational observer

Plan naming requirement:

Use a canonical plan name starting `v3-`.

Suggested stem:

v3-40-godot-generations

Extend the existing V2 Godot observer for V3 demographics.

Continue using the Godot version already pinned by the completed V2 unless a deliberate compatibility upgrade is separately required.

Do not require users to install Godot.

Preserve prebuilt Web export and zero-install browser workflow.

Godot remains read-only.

Visualize:

new-agent arrival/birth  
aging/lifecycle stage  
death  
kinship links on demand  
population changes  
caregiving  
teaching  
mentor/apprentice relationships

Keep simulation location-based.

Do not add simulation coordinates.

Add researcher overlays for:

generation  
cohort  
age/lifecycle stage

Timeline should support generation markers.

Allow selecting an agent and navigating:

parents  
children  
teachers  
students  
important transmitted knowledge

All lineage data must come from backend projection APIs.

## Settings

- Testing: yes; Python unit/API/architecture, pinned headless Godot, real exported-browser acceptance. Keep coverage enabled.
- Logging: verbose, metadata-only; never credentials, DSNs, private records/content, cursor tokens or payload surrogates.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 12.
- Language: English UI/artifacts, preserve technical terms.
- Git: enabled, base `main`, create branches false, skip push prompt true. No branch/worktree, application code, experiment or config is changed by planning.
- Verification: normal; skipped prerequisites are reported, not counted as passes. Published-image browser proof is required for release readiness.
- Research: no research artifact/bundle exists; no research requirements copied. Existing documentation and code are evidence, not a new research source.
- Execution: read this manifest, then each complete linked phase before its tasks. Only this file owns progress. Invoke implementation with the explicit bundle path because multiple other plans exist.

## Roadmap Linkage

Milestone: "M7 — V3 Generational Civilization (in progress)"

Rationale: present existing V3 demographic and captured learning/kinship evidence in the V2 read-only browser observer without acquiring simulation authority or owning another capability flag.

M7 remains open. This work does not own `institutional_economy`, deferred kinship cultural inheritance, or M6 `multi_hop_testimony_tracking`. Do not create/close roadmap milestones during implementation outside the roadmap owner workflow.

## Requirements Reconciliation

Authority: explicit user request defines this feature's scope, subject to repository `AGENTS.md`, `.ai-factory/RULES.md`, configured base rules and `.ai-factory/ARCHITECTURE.md` authority/security boundaries. Existing schemas/code define compatibility; roadmap entries indicate direction, not new behavior. No unresolved behavioral source conflict was found.

| Decision / supported combination | Source path and section | Verification evidence |
|---|---|---|
| Keep exact Godot `4.7.2-stable`, matching SHA512 editor/templates, Compatibility renderer and nonthreaded Web | Original Request; `clients/godot-observer/export/pins.env`; `project.godot`; `export_presets.cfg` | Task 11 pin test, version endpoint and real export smoke |
| No end-user editor install/build; published image serves prebuilt Web files | Original Request; `run.sh`; `scripts/export-observer-web.sh`; `tests/compose/test_observer_browser.py` | Image/browser acceptance and no-editor process check |
| Read-only/location graph; token positions are presentation only | Original Request; architecture — Objective authority, Dependency Rules | Architecture tests, unchanged fingerprints/journal, GET-only navigation |
| Arrival is admission, not evidence of biology; generation/cohort/age/kinship differ | Original Request refined by `docs/generational-runner.md` — Generation, cohort, and community | Tasks 1–3/9 tests; no roster-diff births or calendar-to-family inference |
| Historical facts use exact state/event prefix; no live joins | `docs/observer.md` — Cursor semantics; `scene_through_event` | Before/after entry/death and partial/full-prefix tests |
| Scene replay needs trusted stored configuration and an explicit objective population metadata fold | `src/simulation/replay.py::scene_at_tick`, `ReplayService.replay`; `src/simulation/engine.py::restore_from_snapshot`, `_apply_event_prefix` | Task1 real replay-service tests with checkpoints before entries/stage changes and incomplete admission witnesses |
| Add independent projection schemas rather than silently widening existing frame/lineage schemas | Architecture — Versioned Extension Contract; current strict frame/lineage DTOs | Legacy fixture equivalence and protocol mirror tests |
| Family-care chrome is newly in scope; old docs explicitly said it was absent | Original Request refines `docs/observer.md` / `docs/godot-observer.md` existing limitation | Task 12 replaces that limitation only after implementation |
| Kinship is objective; care is action; mentorship/learning are scoped evidence | Architecture — Memory/testimony; `docs/lineage-explorer.md` — Authority | Non-kin care, owner isolation, attempt-only versus learning evidence |
| All lineage comes from backend APIs; no client pedigree/teaching inference | Original Request; lineage docs — HTTP/qualified identities | API response→parser→view fixtures and request-chain tests |
| Participant projection reads already captured native records; learner graph root alone is insufficient | `src/simulation/lineage_subjective.py::_project_mentorship`; `MentorshipLineageRecord`; `_node_out` | Learner-side participant API test without adding capture edges |
| Native catalogue pagination must be corrected before participant scanning can claim exhaustion | `src/persistence/lineage_filesystem.py::_FilesystemReadSession.node_page`; reproduced450-node publication stopping after256 returned keys | Task5 real-publisher200/200/50 pagination and late-match tests |
| Browser HTTP transport must accept the actual array family response and preserve safe problem codes | `src/api/routes/lineage.py::lineage_families`; `src/api/errors.py::ProblemDetail`; `scripts/net/http_client.gd::_on_completed` | Task6 adapter-level array/object/error tests |
| Inspection and debug use independent, memory-only runtime credentials | `src/api/security.py::_configured_secret`; current `scripts/net/session.gd::_token` | Task7 distinct-secret protected API/browser tests; no export/query/storage secrets |
| Bound every demographic row section; selected-agent lookup does not depend on loaded roster pages | Task2 sidecar contract; `build_population_progress` cohort/generation rows can grow with run length | Large roster/cohort, section cursor and1MiB response-ceiling tests |
| Important transmitted knowledge means evidence-prioritized loaded records, not a new universal importance score | Original Request operationalized by this plan; existing mentorship record counts/provenance | Disclosed ranking, deterministic ties, partial coverage and attempt-only group |
| Eight lineage families/capture artifacts unchanged; exact missing boundary remains unavailable | `docs/lineage-explorer.md` — Capture and availability, HTTP | Disabled/partial/uncaptured/cursor-gone cases; no query writes |
| Current counts are 43 commands / 73 semantic types / 136 metric families; no new counts here | DESCRIPTION latest V3-39; ARCHITECTURE baseline and V3-39 seam | Regression/architecture tests and unchanged pins |

### Supported combinations and state transitions

| Input / selectors | Validation and persisted state | Returned UI state / transition | Verification |
|---|---|---|---|
| Legacy run or lifecycle off, inspect allowed | Existing run/cursor only; reads persist nothing | Base observer works; demographics N/A, no generation/age defaults | Tasks 1/2/7 |
| Lifecycle active with empty population | Active-empty distinct from absent | Complete zero counts and empty roster; no invented founders | Tasks 1–3 |
| Lifecycle active at full boundary B | All pages pinned to B; records/bodies from same fold | Objective population/badges; markers only for successful admissions | Tasks 2/3/9/10 |
| Event prefix `(T,S)` | Sequence requires tick; same prefix as state | Objective sidecar at prefix; complete prefix matches T+1; private lineage disabled until full boundary | Tasks 2/7/8 |
| Full frame carries last-event resume pair `(T,S)` with `world.tick > T` | Classify from accepted frame, not transport event cursor alone | Canonical full-boundary demographics and private capture lookup at `world.tick` | Tasks 7/8 |
| Prefix after Created/Initialization but before EnteredWorld | Keep pending identity witness; no admitted body/record yet | No phantom arrival/population; missing restore context is a safe unavailable error | Tasks 1/2 |
| Agent selected beyond cached roster, or very many cohorts | Exact agent filter and independent bounded group sections; fixed objective cursor | One selected row and paged groups; scalar totals remain full-population | Tasks 2/7/9 |
| Dead body with recorded stage | Stage is last recorded; no postmortem age arithmetic | Death cross, last stage, age unavailable | Tasks 2/9 |
| Genealogy capture present, inspect allowed | Objective scope and exact snapshot; server qualified roots/edges | Direct parent/child rows and on-demand links, including dead ancestors | Tasks 8/10/11 |
| Lifecycle present but lineage disabled/uncaptured | No read-triggered capture or fallback to generation | Demographics available, lineage visibly unavailable | Tasks 5/8/11 |
| Subjective mentorship/knowledge, debug allowed | Explicit owner; same owner across pages | Owner-labeled claims/records; no cross-owner merge | Tasks 4/5/8/10 |
| Analytical mentorship/knowledge, debug allowed | Separate ownerless analytical scope retaining native owner provenance | Analytical cards/graphs, never objective teaching truth | Tasks 4/5/8 |
| Restricted scope with inspect-only/debug disabled | Auth before reading/counting private evidence | Private cards cleared/restricted; objective observer unaffected | Tasks 5/8/11 |
| Protected inspect and debug scopes have different credentials | Top-level masked runtime entry and request capability routing; nothing persisted in browser/export | Both authorized views work; replacing debug secret clears only private state, not objective stream | Tasks 6–8/11 |
| Captured learning attempt with zero uptake evidence | Copy native metadata, no speech inference | Attempt-only group; not successful learning | Tasks 4/9/10 |
| Sparse participant scan page | Maximum200 scanned nodes; continuation after last scanned key | Empty page + Load more/scan-limited, not complete no-teacher claim | Tasks 5/8 |
| Missing exact capture boundary | Return existing availability envelope; no latest substitution | Explicit missing boundary or user-selected older snapshot labeled separately | Tasks 5/8 |
| Partial/truncated graph, unresolved node or client cap | Preserve coverage/stop reasons; bounded fetch | Warning plus explicit further query/re-root, never complete-empty | Tasks 6/8/10 |
| Expired/gone/tampered continuation | Purpose/scope/snapshot/filter verification | 410 requires explicit restart; invalid cursor safely rejected | Tasks 5/8 |
| Run/branch/owner/source/selection changes mid-request | Stamp epoch, selection and scope; reads persist nothing | Ignore stale replies; clear private data/cache as scoped | Tasks 7/8/10 |
| Streamed event advances beyond accepted sidecar before state refresh | Mark summaries/badges stale and clear private cursor-sensitive panels | Refresh once after accepted state frame, not a replay fetch per event | Tasks 7/9 |
| Agent selection uses an ID different from its body ID | Map only through accepted backend registration bindings | Focus mapped body; absent historical agent retains logical card and Back | Tasks 9/10 |

Representative acceptance uses unmodified real Experiment BL (`generational_runner_scenario`, seed23, horizon16) for population/arrival/aging/death/generation navigation. A separate test producer persists a controlled world through real manager/runner/database composition, commits ordinary care commands, projects actual objective genealogy, and publishes explicitly constructed native mentorship/knowledge presentation fixtures for the same run/boundary. Those private fixtures prove rendering and API provenance handling, not spontaneous teaching or successful live learner cognition. The API mounts captures read-only; the producer alone writes its test volume.

## Architecture and Decisions

1. Preserve `observer-protocol-v1`, `observer-layout-v1`, `/v1`, closed semantic count73, commands43, metrics136, Alembic0017, default runner v4/result v2 and latest feature runner v55. No new capability, runner/result schema, event/replay/codec, migration, simulation coordinate or agent behavior.
2. Carry optional lifecycle metadata through detached objective facts/scenes and repair its checkpoint/event-prefix reconstruction under simulation ownership. Inject trusted replay context from validated stored runner config into the observer composition; missing required context is unavailable, never inferred from a live engine. Expose independently versioned GET sidecars; do not append fields to strict existing frame DTOs/stream envelopes or alter durable codecs.
3. New GET projections:
   - `/v1/simulations/{run_id}/observer/demographics` → `observer-demographics-v1`.
   - `/v1/simulations/{run_id}/observer/generation-markers` → `observer-generation-markers-v1`.
   - `/v1/simulations/{run_id}/lineage/mentorship/participants` → `lineage-participants-v1`.
   Their exact selectors, pagination, errors and caps are committed in Phases1/2. All are read-only/no-store, capability-gated, and use existing replay/reader ports.
4. Correct the native node catalogue's keyset completeness, then scan captured mentorship metadata with at most200 candidate nodes per participant request and independently enforced physical-read/byte budgets. Signed continuations bind publication ID/digest and filter. This does not rewrite snapshots, construct a global social registry or recover uncaptured private history. Existing graph routes remain genealogy/knowledge/bond topology sources.
5. Generation is the backend admission-calendar label; cohort is backend admission stratum; age is backend-projected for living bodies. Arrival is not biological birth, and generation is not pedigree depth. Marker click seeks the committed post-admission boundary.
6. Important knowledge is a transparently evidence-prioritized list in loaded records, with opaque content identity and exact evidence counts/provenance. No new metric, natural-language content generation, false teacher attribution or label-based cross-family join.
7. New parsers/source/panel/layer own presentation only. Register every new overlay's evidence class, map agent IDs to existing body tokens through backend registrations, and place global population controls outside the selection-hidden inspector. Token placement and regional journeys stay location-based; links attach to presentation points. No client family inference from events, names, ages or calendar labels.
8. Data controls default off; Credentials remains accessible before protected bootstrap. Use independent origin-scoped, memory-only inspection/debug credentials with explicit request routing and generation guards. HTTP adapter supports the real array/object/error response shapes. Full-boundary detection uses accepted frame tick versus event tick, not presence of a resume cursor. Live events invalidate sidecars until state refresh. Unsupported/missing/partial data never breaks base playback or becomes complete zero.
9. Preserve pin file/URLs/hashes and export setup unchanged. The only CI preparation correction is the already-documented headless editor registration pass before script tests. Runtime users still consume a prebuilt image/Web export.
10. Demographics uses paged agents/cohorts/generations sections, direct selected-agent lookup, exact scalar totals and a1MiB response ceiling. No unbounded group arrays or hidden requirement to load the first800 agents before inspecting a later one. All fetches remain on demand with explicit Load more and bounded caches.

## Phase Index

1. [Phase 1: Objective projections](phase-01-objective-projections.md) — Tasks 1–3
2. [Phase 2: Lineage projections](phase-02-lineage-projections.md) — Tasks 4–5
3. [Phase 3: Client data](phase-03-client-data.md) — Tasks 6–8
4. [Phase 4: Generational UI](phase-04-generational-ui.md) — Tasks 9–10
5. [Phase 5: Acceptance and docs](phase-05-acceptance-and-docs.md) — Tasks 11–12

## Cross-Phase Dependencies

- Task 2 depends on 1; Task 3 depends on 1 and 2 for shared cursor/DTO conventions.
- Task 4 is independent of Phase1; Task 5 depends on 4.
- Task 6 depends on 2, 3 and 5 so fixtures match committed response schemas.
- Task 7 depends on 6; Task 8 depends on 5, 6 and 7 for shared session/epoch guards.
- Task 9 depends on 2 and 7; it does not require lineage fetching. Task 10 depends on 3, 8 and 9.
- Task 11 depends on Tasks1–10; Task 12 depends on 11 and includes the mandatory docs checkpoint.
- Execute in listed task order by default; do not mark later tasks complete merely because an independent branch of the plan is ready.

## Tasks

### Phase 1: Objective projections

- [x] Task 1: Carry lifecycle facts through detached replay scenes ([details](phase-01-objective-projections.md#task-1-carry-lifecycle-facts-through-detached-replay-scenes))
- [x] Task 2: Publish demographic population and selected-roster projections ([details](phase-01-objective-projections.md#task-2-publish-demographic-population-and-selected-roster-projections)) (depends on 1)
- [x] Task 3: Publish admitted-generation timeline markers ([details](phase-01-objective-projections.md#task-3-publish-admitted-generation-timeline-markers)) (depends on 1, 2)

### Phase 2: Lineage projections

- [x] Task 4: Project captured teacher–learner–content participant records ([details](phase-02-lineage-projections.md#task-4-project-captured-teacherlearnercontent-participant-records))
- [x] Task 5: Add a bounded, snapshot-pinned participant query API ([details](phase-02-lineage-projections.md#task-5-add-a-bounded-snapshot-pinned-participant-query-api)) (depends on 4)

### Phase 3: Client data

- [x] Task 6: Parse sidecar projections and preserve lineage query parameters ([details](phase-03-client-data.md#task-6-parse-sidecar-projections-and-preserve-lineage-query-parameters)) (depends on 2, 3, 5)
- [x] Task 7: Fetch demographic pages and marker windows for the displayed cursor ([details](phase-03-client-data.md#task-7-fetch-demographic-pages-and-marker-windows-for-the-displayed-cursor)) (depends on 6)
- [x] Task 8: Fetch on-demand genealogy, mentorship and knowledge projections ([details](phase-03-client-data.md#task-8-fetch-on-demand-genealogy-mentorship-and-knowledge-projections)) (depends on 5, 6, 7)

### Phase 4: Generational UI

- [x] Task 9: Render population, lifecycle, arrival, death and care ([details](phase-04-generational-ui.md#task-9-render-population-lifecycle-arrival-death-and-care)) (depends on 2, 7)
- [x] Task 10: Add generation timeline and selected-agent lineage navigation ([details](phase-04-generational-ui.md#task-10-add-generation-timeline-and-selected-agent-lineage-navigation)) (depends on 3, 8, 9)

### Phase 5: Acceptance and docs

- [ ] Task 11: Prove exported browser behavior and architecture noninterference ([details](phase-05-acceptance-and-docs.md#task-11-prove-exported-browser-behavior-and-architecture-noninterference)) (depends on 1–10)
- [ ] Task 12: Document evidence semantics and release the browser workflow ([details](phase-05-acceptance-and-docs.md#task-12-document-evidence-semantics-and-release-the-browser-workflow)) (depends on 11)

## Commit Plan

- **Commit 1** (after Tasks1–4): `feat(observer): project demographic and native learning evidence`.
- **Commit 2** (after Tasks5–8): `feat(observer): consume scoped generational projection APIs`.
- **Commit 3** (after Tasks9–12): `feat(observer): visualize generations with browser acceptance`.

These are proposed implementation checkpoints, not authorization to create commits during planning. Preserve user changes and keep every checkpoint buildable with its available tests.

## Definition of Done

- Every requested visualization/overlay/navigation category is implemented with explicit backend evidence, cursor correctness and availability semantics.
- Generation/cohort/age are not conflated with genealogy or social authority. Care and teaching attempts are not promoted into permanent family roles or successful learning.
- Captured parents/children/teacher/student/content links are obtained through GET backend projections only; private/debug boundaries and owner isolation survive pagination/seek/source changes.
- Historical lifecycle/registration facts are folded from the selected checkpoint and committed events, including incomplete admission prefixes. Catalogue pagination reaches every eligible native node or reports budget failure; protected browser sessions work with different inspection/debug credentials.
- Pinned Godot4.7.2-stable produces the prebuilt nonthreaded Compatibility Web export; published-image/browser workflow requires no local Godot installation and no runtime editor.
- Python/API/architecture and pinned Godot suites pass; real exported-browser acceptance and V2 smoke pass, with actual visible model assertions and safe diagnostics. Missing prerequisites remain explicit release blockers.
- No simulation coordinates, mutation authority, new capability/event/command/replay/runner/result/migration/metric identity, or unrelated refactor is introduced. Existing version gates and default-off trajectories remain green.
- Mandatory documentation checkpoint and exact source/availability descriptions are complete; only verified task checkboxes are marked here.

## Open Questions and Boundaries

No blocking implementation question is currently identified. Two bounded interpretations are committed rather than delegated: “birth” is an observed admission/arrival (not biology), and “important” knowledge is evidence-prioritized within loaded records (not a novel importance metric). Any request to add biological births, objective teaching truth, global cultural ranking, simulation coordinates, an engine upgrade or automatic lineage capture requires a separately scoped decision.

Do not start implementation as part of this planning invocation.

## Approved Refinements

The user approved all eight findings and the dependency correction in the 2026-10-24 improve pass. All12 task IDs and unchecked statuses remain unchanged.

| Finding | Applied plan changes |
|---|---|
| Historical replay cannot be assumed to rebuild V3 population metadata | Task1 adds stored-config context injection and explicit registration/lifecycle checkpoint/prefix fold, with real replay-service tests. |
| Catalogue scan can falsely exhaust | Task5 repairs native filesystem pagination before participant queries and adds450-node/late-match regressions; reproduction returned200+56 of450 before correction. |
| HTTP adapter rejects arrays and loses error detail | Task6 extends actual transport response-shape/error-code handling and adapter tests. |
| One credential cannot authorize two protected capabilities | Tasks7–8 add independent browser-entered memory-only credentials, routing and revocation guards. |
| Resume cursor and partial frame were conflated | Tasks7–8 define canonical frame-based cursor classification and live-event invalidation. |
| Group sections and selected-agent lookup were not bounded/addressable | Tasks2/7 page all growing row sections, enforce response ceiling and fetch exact selected rows independently of cache. |
| Evidence registration/body-ID/global-panel wiring was incomplete | Tasks9–10 register evidence kinds, map backend agent→body identity and expose population controls without selection. |
| Browser evidence production was underspecified | Task11 defines the durable producer, test-only writer service, shared run/publication identities, protected stack modes and real rendered-control interactions. |
| Unnecessary dependency | Task9 no longer depends on Task8; Task10 retains its lineage dependency. |
