# Implementation Plan: V3-22 Regions and Migration

Branch: main (current branch; `git.create_branches: false`)
Created: 2026-10-15
Improved: 2026-10-15 (`/aif-improve`; seven refinements and two dependency fixes approved)
Mode: full

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes — mandatory `/aif-docs` checkpoint during implementation.
- Artifact naming: every plan artifact produced for this feature begins `v3-`; canonical file is `.ai-factory/plans/v3-22-regions-migration.md`.
- Implementation scope: optional logical regions, discrete edge travel, subjective destination knowledge, and read-only demographic analysis.

## Roadmap Linkage
Milestone: "M7 — V3 Generational Civilization"
Rationale: Owns the reserved migration capability through optional regions and meaningful location-based relocation, while retaining V1/V2 authority, epistemic isolation, and replay invariants.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M7 — V3 Generational Civilization
INFO [aif-plan] full mode confirmed by user; git.create_branches=false; resolved plan file: .ai-factory/plans/v3-22-regions-migration.md (format=slug)
INFO [aif-plan] plan_default_milestone=auto surfaces M6 first; explicit V3 scope uses M7, following v3-21 precedent; this plan does not close M6
INFO [aif-plan] RESEARCH.md and skill-context/aif-plan/SKILL.md absent; research_influenced_plan=false
INFO [aif-improve] refined exact v44 family roots, working-state travel gates, flee destination identity, prefix-safe events/consumers, recall namespaces/budgets, residence accounting, and Godot verification; Task 6 precedes Task 4; 15 tasks retained
INFO [aif-implement] Task 7 + Task 9 durable integration tests passed against disposable palimpsest_test database (9 passed); repaired v21/v19 run-create pair handling and replay journal event decoding discovered by integration
INFO [aif-implement] Task 10 deterministic destination deliberation implemented; 90 focused cognition, memory, runner, replay, and checkpoint tests passed; Ruff checks passed
INFO [aif-implement] Task 11 regional folds and metric families implemented; 108 focused metric/composition tests and 12 disposable-PostgreSQL integrations passed; Ruff checks passed
INFO [aif-implement] Task 12 reconciled AY diagnostic arms with ordinary admitted overrides and an untouched production-cognition arm; matrix runs now collect detached regional evidence; 42 focused AY/matrix/cognition/demography/config tests passed. Full mypy currently reports 2891 errors across 117 files; Task 14 remains open for gate reconciliation.
INFO [aif-implement] Task 13 added detached region labels, origin-anchored journey DTOs, 72 semantic events, API omission gates, Godot parsing/reduction/envelopes/busy status, and backward-seek coverage; 25 Python projection/API/contract tests and the registered regional Godot suite passed using checksum-verified Godot 4.7.2. Full Godot suite currently reports one existing graphical-controls follow-agent failure and a nil transport error; Task 14 owns full-suite reconciliation.
INFO [aif-implement] Task 14 partial reconciliation: repaired legacy pre-care PhysicalRules shape/hash decoding, updated semantic assertions to 72, fixed benchmark collection and graphical-controls test setup. Required six-file V1/V2 compatibility gate: 35 passed. Focused regional/observer checks: 57 passed. Full registered Godot 4.7.2 suite: failed=0 with no script errors. Full pytest: 4220 passed, 44 failed, 104 deselected; architecture: 209 passed, 7 failed; import-linter: 19 kept, 6 broken; full Ruff: 397 findings at initial gate; mypy: 2891 errors at initial gate; format check failed. Durable integration: 1 passed, 8 skipped because PALIMPSEST_TEST_DATABASE_URL was unavailable. Task 14 is NOT complete; remaining repository-wide gates require reconciliation, including stale flag/schema tests and existing boundary/type failures.
INFO [aif-implement] Mandatory aif-docs checkpoint executed: updated six planned documentation pages and AGENTS documentation index; reviewed changed links/anchors and ran both codec round-trip and six-arm AY reproduction examples successfully. Documentation was completed while Task 14 gate reconciliation remained open; this does not waive the prerequisite or imply whole-plan verification.
INFO [aif-implement] Task 14 continued: initialized restore channel bindings before skill refolding; moved regional snapshot-to-evidence conversion into the experiment contract boundary; removed world-to-agent identity dependencies while retaining AgentId re-exports; repaired omitted public-goods physiology activation; reconciled owned/unowned capability tests and exhaustive command typing fixtures. Added regional public-benefit/event-prefix composition and assigned/unassigned conservation property coverage. Disposable PostgreSQL/pgvector integration: 12 passed, including travel, two-lane recall, and regional analysis. Last full pytest: 4257 passed, 13 failed, 104 deselected. Import-linter improved to 21 kept / 4 broken. Further typing and architecture reconciliation remains in progress; Task 14 is not complete.

INFO [aif-implement] Verification remediation: corrected first-residence qualification to require the configured dwell threshold. Added initial-unassigned and mid-run-unassigned known-answer regressions; all 13 demographic tests pass. Task 14 remains open while boundary, runtime, static, and durable gates are reconciled.

INFO [aif-implement] Task 14 resumed 2026-10-16: reconciled remaining Ruff/format findings; tightened detached collective-project, observer serializer, journey replay/codec, runner-result, production, lifecycle/skill-candidate, and deliberation annotations without weakening mypy configuration. Journey-end decoding now explicitly rejects unknown reason strings at the reason field; four malformed-wire regressions pass. Latest full pytest: 4276 passed, 104 deselected. Architecture: 219 passed. Required six-file V1/V2 compatibility gate: 35 passed. Import-linter: 25 kept, 0 broken. Full Ruff and format checks pass (1152 files formatted). Registered Godot 4.7.2 suite: failed=0. Requested disposable PostgreSQL/pgvector integration: 9 passed against validated palimpsest_test_regions database. IDE build reports success with limited diagnostics. Full mypy improved from 608 errors / 86 files at session start to 495 errors / 79 files; this is the remaining failing required gate. Task 14 remains unchecked; whole-plan completion is not claimed. Next continuation should reconcile the remaining concrete typing errors across cognition, serialization, simulation, experiment composition, and persistence rather than suppress or exclude them.

INFO [aif-implement] Task 14 completed 2026-10-17: reconciled the remaining 495 strict typing errors with concrete contracts, typed adapter/factory returns, correctly narrowed optional values, generic stage protocols, and validated boundary conversions; mypy configuration and source coverage were not relaxed. Final required gates: Ruff passed; format passed (1152 files); mypy passed (373 source files); import-linter 25 kept / 0 broken; architecture 219 passed; required six-file compatibility gate 35 passed; full pytest 4276 passed / 104 deselected; checksum-verified pinned Godot 4.7.2 registered suite failed=0 with no script errors; requested PostgreSQL/pgvector integrations 9 passed on disposable palimpsest_test_regions. The temporary database was recreated after the earlier verification container disappeared; Docker bridge port forwarding was unavailable, so the successful final run used an isolated disposable PostgreSQL instance bound to loopback port 55432 with host networking. All 15 task checkboxes are now complete; the previously executed documentation checkpoint is retained and its Task 14 prerequisite is satisfied.

## Goal

Extend the existing connected location graph with optional `World -> Region -> Location` organization. Agents still occupy and act at locations. Regions group locations; they are not coordinates, governments, admission rights, or agents. Agents can undertake costly journeys across region boundaries, stay, return, or relocate, and form fallible beliefs about distant destinations from experience and testimony. Researchers can reconstruct regional populations and distinguish temporary travel from sustained migration.

## Current Implementation Evidence

- `src/world/models.py`: frozen `Location` contains adjacency, capacities, temperature, shelter, and visibility. `src/world/_state.py` requires a connected, symmetric graph and valid body locations; dead bodies consume capacity.
- `src/world/_rules.py`: `Move` immediately traverses one adjacent edge and charges fatigue. `Flee` and dependency-care `Transport` can also relocate bodies. There is no journey state or edge duration.
- `src/simulation/engine.py`: ordered action preparation, due production completion, public-goods processing, physical evolution, and lifecycle processing provide deterministic integration seams.
- `src/simulation/runner_models.py`: schemas accepted through `runner-config-v43`; `multi_polity_migration` is reserved/default-off/unowned. Public goods use replay 20 / codec `v18`; default writes remain runner v4 and replay 5 / codec `v2`.
- `src/agents/cognition/memory.py`: ordinary retrieval is current-location filtered; distant memories need an explicit bounded retrieval path. `scarcity_beliefs.py` is keyed by item kind, not destination, and must not become a regional truth registry.
- Baseline: 43 command variants, 69 observer semantic types, Alembic `0017`, observer protocol/layout v1, latest experiment AX. Recheck these selectors before implementation if other feature work lands first.

## Compatibility and Authority Contract

1. `WorldEngine` remains the sole objective mutation authority. Domain contracts are frozen/detached; cross-package imports use facades. Only authorized simulation modules import private world internals.
2. Own the existing `V3CapabilityFlags.multi_polity_migration` slot for this location/region migration substrate. No new capability flag. Document that polity formation, citizenship, border enforcement, and dynamic settlements remain separate work; enabling this flag does not create them. `institutional_economy` and `multi_hop_testimony_tracking` remain fail-closed.
3. Off means exact baseline: no new world collections in legacy wire payloads, no journey events, observation additions, RNG consumption, ID allocation, cognition bias, or trajectory changes. Other owned V3 flags remain independently optional.
4. Add `runner-config-v44` with required exact `regions_migration` sibling and a new family-root selector, not an unconditional union with the required v43 roots. Reuse the v43 family rules, remove `public_goods` and `collective_projects` when absent, and add `regions_migration`. Preserve prerequisite validation for present channels (`public_goods` requires `collective_projects`; exchange profile requires valuation; other existing prerequisites still apply). All earlier versions stay accepted with their exact keysets. v44 may compose previous optional channels without requiring public goods, population lifecycle, kinship, or cultural memory. Absent optional objects are omitted, not encoded as null; unknown keys reject.
5. Enabled regional objective state/journey events use `(EVENT_SCHEMA_REPLAY_V21, "v19")`. Codec v19 carries all older active-channel payloads. A run without this channel retains the existing highest-active-channel write selector, not automatically replay 21. Reject newer payloads under older schemas/codecs.
6. Keep 43 commands: `Move` requests the next adjacent location, not a region or a remote teleport. `Transport` remains a grouped adjacent move. No `Migrate` command or engine-selected destination. Add three effect-complete world events, proposed names `JourneyStarted`, `JourneyArrived`, `JourneyEnded`; migration classification is analysis-only.
7. No continuous x/y, distance from rendering, grid conversion, regional resource oracle, or shared agent atlas. Godot coordinates, route animation, and region envelopes are visual-only. A bridge does not add an edge or change route costs in this plan.
8. Subjective beliefs, motives, destination preferences, reconstructed memories, and declared testimony never become objective admission criteria or truth corrections. No agent receives `WorldEvent`, snapshot, metric rows, or another owner's state.
9. Bootstrap topology remains connected and symmetric. Remote means costly/multi-hop or poorly known, not a disconnected node. No dynamic topology, automatic political membership, scripted exodus, or compulsory family migration.
10. Use logical ticks and explicit seed streams only. No new randomness is necessary for deterministic route travel. Keep Alembic `0017`, `/v1`, and existing protocol names unless implementation uncovers a concrete incompatible consumer contract; do not silently widen an exact wire contract.

## Design Decisions

### Optional region and route model

- New `src/world/regions.py` owns public immutable region, edge-travel specification, channel specification, and journey contracts; facade exports are explicit. Use validated opaque IDs, not overloaded display names. Labels do not imply agent knowledge or semantic interpretations.
- `regions_migration` has exact keys: `regions`, `location_regions`, `routes`, `max_arrival_wait_ticks`, `residence_min_ticks`, `destination_memory_limit`, `destination_hop_limit`, `cognition_mode`. Modes are `disabled` and `deterministic`; enabling physics does not force cognitive migration behavior.
- Nested wire shapes are exact: each `regions` entry is `{region_id, label}`; `location_regions` is an ordered list of `{location_id, region_id}` entries, not a JSON mapping that silently collapses duplicates; each `routes` entry is `{endpoint_a, endpoint_b, duration_ticks, fatigue_cost}`. IDs/labels are nonempty validated strings; canonical encoding sorts regions and memberships by ID and routes by canonical endpoint pair. Reject unknown fields and null values. `max_arrival_wait_ticks` is an exact integer >= 0; `residence_min_ticks`, `destination_memory_limit`, `destination_hop_limit`, and `duration_ticks` are exact integers >= 1 (booleans reject). `fatigue_cost` is finite and >= 0. `regions` must be nonempty; membership/routes may be empty. All keys are supplied explicitly, with no implicit wire defaults.
- A region has an id and label; `location_regions` maps existing location IDs to a single region ID. Missing membership is legal and explicitly unassigned, not an implicit global region. Reject unknown IDs, duplicate IDs/memberships, empty region definitions, invalid integers/booleans, and unknown fields. No nested regions in this iteration.
- Route entries name one existing undirected adjacent edge, positive integer `duration_ticks`, and finite nonnegative `fatigue_cost`. Canonicalize endpoint order and reject duplicate/reverse duplicates and nonedges. Unlisted edges retain duration 1 and the existing physical move fatigue. No cost from region labels, screen position, or Euclidean distance.
- Apply existing skill/development effects exactly once to the base movement cost; travel physiology/exposure remains a per-tick cost. For an explicit route, `Move` uses its `fatigue_cost`; `Transport` uses `PhysicalRules.transport_fatigue + max(0, route.fatigue_cost - PhysicalRules.move_fatigue)` before existing adjustments. An unlisted route keeps the existing transport cost. Charge only the caregiver for transport, with no duplicate move charge.
- Resource/environment differences remain location-owned: use existing local resource quantities/regeneration, temperature, shelter, weather, and optional environmental dynamics. Region summaries are researcher aggregations; this plan adds no second environment simulator or implicit region-wide modifier.
- Flag/object gate: flag off + object absent is legacy; flag on requires nonempty valid regional configuration on v44; object with flag off, flag on without object, object on pre-v44, or v44 without object rejects with stable safe reason codes. Empty region collections do not count as an implemented enabled capability. Partial location membership remains supported.

### Discrete journey lifecycle and location authority

- A body always has one valid `location_id`. During a multi-tick journey it remains at the origin location and is busy. This is an abstract departure/preparation interval, not physical mid-edge position; origin weather, visibility, hazards, attacks, occupancy, and physiology apply until arrival. Arrival atomically changes location. This rule is explicit in UI/docs and avoids a hidden continuous transit layer.
- Store journey ID, ordered participant body IDs, actor, origin/destination location IDs, source/destination region IDs if assigned, start/due tick, charged cost, and capacity-wait deadline. Held items follow the participants through existing custody rules. Do not store private motives, a migration label, or inferred citizenship.
- Start on tick `t` with duration `d`; first arrival attempt is `t + d - 1`. Duration 1 starts and arrives in the same action resolution, preserving ordinary move timing. For `d > 1`, beginning a journey consumes the action and charges fatigue once, and subsequent ticks advance through world-owned autonomous processing even without submissions.
- Multi-tick departure validates living participants, adjacency, busy state, and valid costs but does not reserve destination capacity. At arrival, require enough slots for the whole group. If full, retain origin placement and retry in canonical `(due_tick, journey_id)` order. Attempt through `due_tick + max_arrival_wait_ticks` inclusive; after the final failed attempt, end the journey at origin. No partial group arrival, over-capacity state, or reservation system. Duration-1 moves retain immediate capacity rejection.
- Busy travellers may submit `Wait` only; other self-initiated actions reject `actor_travelling`. External origin-local interactions retain ordinary gates; travel does not make a body invisible or invulnerable. Reject conflicting production participation and external transport of an already travelling body. No new cancel command; timeout and participant death end the journey.
- Enabled travel admission checks every participant against the evolving working state, including the opening rule and the application recheck. Do not extend the existing tick-start-only opening rule to travel-dependent eligibility. In one batch, an earlier transport may make a dependent busy before that dependent's own command or a second caregiver's transport resolves. Allow that participant's `Wait`; reject/conflict other commands consistently without allocating a second journey or charging a second cost. Keep legacy opening-rule/conflict behavior when the channel is off.
- `Transport` starts one grouped journey and keeps caregiver/dependent together, with existing dependency-care admission and fatigue effects. Any participant death ends the entire pending journey at origin; corpses and held possessions use current death/custody rules. No automatic parent/kin following. `Flee` considers only duration-1 routes and retains existing flee cost; it cannot bypass a long route. If none qualify, retain the existing failed-flee semantics.
- Use one route-aware flee-eligibility policy in engine random-effect resolution, rule checks, and application. In enabled mode, bind the sampled eligible-list index to a concrete destination identity in the resolved effect; if that destination is unavailable at application, conflict deterministically rather than reinterpret the index against a shortened list or redraw. A traveller or actor with no legal short route consumes no flee RNG draw. Because existing engine resolution precedes action application, enabled flee resolution must be gated by working-state eligibility via a deferred callback (following existing per-action callback patterns), including travel begun earlier in the same batch; a tick-start busy check alone is insufficient. Channel-off resolved-effect representation, draws, and behavior remain unchanged. Successful fleeing remains a `Fled` event and must count as relocation in regional analysis.
- Process due journeys after ordered actions and before autonomous physical evolution. A participant killed during actions cancels before arrival. After physical/lifecycle death, end any remaining affected journey in that same prepared candidate. Successful arrival receives destination exposure that tick; blocked travellers receive origin exposure. Shared arrival ordering, deaths, and capacity effects are pinned by tests.
- `JourneyStarted` records complete pending-state/cost effects; `JourneyArrived` records complete placement/removal effects; `JourneyEnded` records removal and safe reason (`participant_dead` or `arrival_timeout`). Each has explicit participant IDs and occurrence context. Elapsed progress derives from tick/start/due values; do not emit a redundant progress event every tick. No duplicate `Moved` effect for the same relocation.
- Every event prefix is projectable. A prefix ending after `JourneyStarted` contains the journey and charged fatigue at origin, even for duration 1; the next `JourneyArrived` applies placement/removal only. A prefix after `Died` may temporarily contain a journey with a dead participant until its ordered `JourneyEnded`. Structural state construction must allow that replay intermediate; a separate finalized-boundary validator requires all pending participants alive and forbids overdue unresolved/cancelled journeys. This also permits live death processing before cleanup. Do not remove a journey silently as a side effect of replaying death and then remove it again on `JourneyEnded`.
- Reuse `RuleApplication.all_event_details()` and `PendingEvent` ordering for multi-event movement. Extend `build_occurrence_context` for each new detail type, rather than treating all details from one action as origin-local. Audit action/skill folds, observed-event projection, and analysis movement classifiers: departure records the admitted command/effort once; arrival records relocation once; cancellation is not arrival. For example, `analysis.prospective_imagination_metrics._DIRECTION` must recognize a move-start attempt instead of silently losing it when `Moved` is replaced. Grouped transport preserves its own command identity, not a fabricated second `Move`.
- Event privacy is phase-specific: start/end belong to origin; arrival belongs to destination. A witness to departure does not learn remote arrival. The traveller's next observation can describe its own journey/arrival through normal self perception without disclosing the destination to origin witnesses.

### Perception and subjective destination knowledge

- Channel-on observations add closed optional local region and self-journey facts; local exits may expose physically inspectable edge cost/duration and destination region identity when visible. They do not expose regional inventories, demographics, weather, the full graph, or hidden route continuations. Channel-off JSON stays exact.
- Reuse owner-scoped episodic traces, generic semantic beliefs, evidence/revision services, communication, and reconstructive recall. Destination-indexed predicates can represent reported resources, conditions, accessibility, and past visits. Beliefs carry evidence time, source/channel, confidence, and contradictions; a stale report is not current objective state.
- Add a bounded destination-memory retrieval lane alongside ordinary local retrieval. It reads only the owner's evidence, uses deterministic ordering and configured count/hop budgets, and respects cognition budgets. It never queries world snapshots or uses the kind-only scarcity ledger as a destination index.
- Preserve existing local-lane IDs byte-for-byte; namespace destination `operation_id`, `ReconstructionId`, and any reconsolidated `derived_memory_id` by owner/tick/policy plus a stable destination-lane token. Retry of the same lane is idempotent, and different lanes cannot reuse conflicting IDs. Deterministically deduplicate selected memory IDs before reconstruction/access updates; one trace is charged/reconstructed at most once across the combined recall. Local retrieval gets first use of the existing effective memory-selection budget, destination retrieval receives only its remainder capped by `destination_memory_limit`, and zero remainder skips the destination service call. Both lanes share existing provider/timeout/reconstruction budgets rather than each receiving a full allowance.
- Derive bounded known-route adjacency from persisted owner semantic evidence and reconstructed own traces on each invocation. Do not introduce an unpersisted route atlas/cache as the source of decision continuity. Checkpoint/resume with the same subjective evidence must reproduce destination recall and the next adjacent-step command.
- Deterministic destination planning is optional under the channel. Agents may choose to stay, explore an observed exit, return, or seek a remembered/reported region by selecting one known adjacent step. Paths beyond the agent's known graph stay unknown. Resource needs, own evidence, uncertainty, and known travel costs can bias existing deliberation; they do not create a global reward, forced migration, or privileged truth.
- Test accurate, wrong, stale, contradictory, and absent evidence. Identical public facts with different private evidence can produce different choices; changing hidden remote resources alone cannot alter the current agent's choices before evidence arrives.

### Migration and demographic flows are research interpretations

- Persist objective crossing evidence through relocations, not a world-level `is_migrant` field. Analysis folds `JourneyArrived`, successful `Fled`, and any accepted legacy `Moved`/transport relocation effects exactly once per participant using pre/post placement. A rejected move, failed flee, departure, or timeout is not an arrival. Same-region moves do not count as interregional flows. Moving into/out of an unassigned location has explicit unknown-region coverage, not an invented region ID. Start from detached initial placement and apply event order before computing each completed boundary.
- Report raw origin–destination arrival counts separately from dwell-qualified relocation events. `residence_min_ticks` is a positive analysis parameter, not an agent trait or world rule. Track per living person `established_residence`, `candidate_region`, `candidate_arrival_tick`, and `consecutive_boundary_count`. Initial placement and mid-run entry establish an assigned-region baseline without a migration; unassigned entry starts with no baseline.
- At a completed boundary in a different assigned region, start/continue that region's candidate. The arrival boundary counts as dwell tick 1 only if the person is alive and still there at boundary end. At the threshold, emit one analytical migration row from the established residence, retain the candidate's arrival tick, then replace established residence and clear the candidate. If there was no prior residence, qualification establishes the first residence without counting migration. Movement within a candidate region preserves dwell. A boundary at the established residence cancels an unqualified excursion, so a short visit followed by return is not a migration. A later return after residence actually changed can qualify as a new migration. A boundary in a third region replaces the candidate; an unassigned boundary clears it but retains the last established residence. Death clears the candidate and cannot qualify dwell that boundary. These private-to-analysis records never enter snapshots, observations, or admission.
- Use completed-boundary living populations, person-ticks, entries, deaths, arrivals/departures, qualified migrations, return flows, and stage/cohort composition only when lifecycle data exists. Transport counts each person exactly once. Bodies waiting at origin remain in origin population. Dead bodies occupy physical slots but are excluded from living demographics.
- Preserve conservation: for every region/boundary, living population change equals arrivals minus departures plus admitted entries minus deaths, with explicit assigned/unassigned transition terms. Qualified migration counts need not equal raw crossings. Incomplete prefixes and missing subjective evidence expose coverage, not inferred zeroes.
- New analysis families: `regional_population@1`, `regional_migration@1`, and `regional_destination_beliefs@1`. Quantize by existing numerical policy; expose numerators/denominators and observation coverage. Belief analysis compares available owner evidence after the run, never feeds truth into cognition. No civilization success, native/foreigner moral labels, or `PhenomenonId` is introduced.

## Commit Plan

Commit messages are suggestions for implementation; this planning command creates no commits.

- **Commit 1** (tasks 1–3): `feat(v3): add optional regions and versioned migration contracts`
- **Commit 2** (tasks 4–6): `feat(v3): resolve deterministic location-based journeys`
- **Commit 3** (tasks 7–9): `feat(v3): persist journeys and form subjective destination beliefs`
- **Commit 4** (tasks 10–12): `feat(v3): expose regional flows and reproducible migration experiments`
- **Commit 5** (tasks 13–15): `feat(v3): present and document replayable regional migration`

## Tasks

### Phase 1 — Contracts, configuration, and spatial state

- [x] **Task 1: Define immutable regional and journey contracts with exact validation.**
  - Files: create `src/world/regions.py`, update `src/world/__init__.py`; create `tests/unit/test_regions_contracts.py`.
  - Deliver the exact nested wire/model contracts and numeric bounds above, canonical undirected edge identity, optional single membership, detached collection validation, and finite costs. Reuse opaque identifier conventions without adding world coordinates or political fields. Reject duplicate membership list entries before constructing indexes.
  - Acceptance: reject malformed/unknown/duplicate membership and route values; accept partial assignment and connected remote multi-hop examples. Round-trip ordering is canonical and caller mutation cannot alter contracts.
  - Logging: DEBUG at spec-validation boundaries with counts/IDs; safe rejection codes only, no labels or payload dumps. Pure value constructors need no side-effect logs.
  - Dependencies: none.

- [x] **Task 2: Gate and serialize the migration capability on runner-config-v44.**
  - Files: `src/simulation/runner_models.py`, `runner_serialization.py`, `runner.py`, `compatibility.py`, `__init__.py`; `src/experiments/matrix_schema.py`; create `tests/unit/test_runner_config_v44.py`; update `tests/unit/test_v3_flag_defaults.py`, `test_compatibility_matrix.py`.
  - Add exact `regions_migration` config, both capability ownership mirrors, strict flag/object/schema gate matrix, highest-active-schema selection, and matrix round trips. Implement `_v44_family_root_keys` with required migration and optional-when-absent public-goods/collective-project siblings, retaining each present channel's prerequisites and old selectors unchanged. Keep cognitive mode disabled by default even with physics enabled.
  - Acceptance: v1–v43 keysets unchanged, channel-off default still v4, migration-only v44 and v44 plus each legal prior-channel combination round-trip; public goods without projects and unknown/null optional objects reject. Unowned capabilities still reject. Record fail-closed reason codes.
  - Logging: INFO at runner activation with schema/mode/counts; DEBUG gate decisions; WARN invalid combinations with code only. No config dumps.
  - Dependencies: 1.

- [x] **Task 3: Carry regions, route rules, and journeys through authoritative state and bootstrap.**
  - Files: `src/world/_state.py`, `src/simulation/bootstrap.py`, `src/simulation/engine.py`; create `tests/unit/test_regions_bootstrap.py`.
  - Materialize optional definitions through `WorldBootstrap`, private state, state rebuilding, and engine contexts. Validate all references, journey participants/origins, unique participation, graph invariants, and busy-state conflicts. Separate prefix-safe structural invariants from finalized-boundary liveness/cleanup validation; a death prefix can retain its not-yet-ended journey. Maintain channel-off representation and partial region assignment.
  - Acceptance: every unrelated state rebuild preserves enabled region/journey state; disconnected graph, nonedge route, invalid journey, and ambiguous membership reject. Existing local resource/environment fields remain authoritative.
  - Logging: DEBUG bootstrap/state validation counts and safe codes; INFO enabled topology summary at composition only. No location labels or subjective data.
  - Dependencies: 1, 2.

### Phase 2 — Travel admission and deterministic lifecycle

- [x] **Task 6: Define effect-complete journey events and replay projection.**
  - Files: `src/world/events.py`, `_replay.py`, `__init__.py`; `src/simulation/serialization.py`; `src/analysis/prospective_imagination_metrics.py` and other existing movement consumers identified in the audit; create `tests/unit/test_regional_travel_events.py`, `tests/unit/test_regional_travel_replay.py`.
  - Implement the three closed event variants, original command identity, cost/resulting-state fields, per-detail occurrence contexts, canonical serialization, replay 21 registration, and projection that applies recorded effects without rerunning costs or decisions. Use the existing multi-detail application path. Audit skill/action folds, observation evidence, and analytical movement classifiers for command-start versus actual-arrival semantics. Do not emit duplicate relocation effects.
  - Acceptance: event-only projection reproduces every prefix, including duration-1 start-before-arrival and death-before-end; finalized validation rejects missing cleanup. Pin projection tests with explicit event fixtures before live producers land, then compare against those producers in Tasks 4–5/14. Costs/skill effort count once, start-only attempts remain recognizable by existing command metrics, and grouped transport retains its identity. Malformed effects and old-schema journey events reject. Origin witnesses cannot receive remote-arrival events.
  - Logging: DEBUG codec/projection counts, event IDs, and schema; ERROR safe validation codes. No event bodies or full exported records in logs.
  - Dependencies: 1, 3. This task intentionally precedes Tasks 4–5 so producers consume fixed event/prefix contracts; task IDs are preserved.

- [x] **Task 4: Start journeys from existing movement commands.**
  - Files: `src/world/_operations.py`, `_rules.py`, `_skills.py`, `effects.py`, `src/simulation/actions.py`, `engine.py` (`_resolve_flee_effect`); create `tests/unit/test_regional_travel_actions.py`.
  - Implement route duration/cost selection, duration-1 compatibility, grouped `Transport`, working-state participant validation at opening/application, and shared route-aware flee eligibility. Defer enabled flee random resolution until working-state eligibility passes, using the existing per-action callback pattern; keep the legacy pre-resolution path when off. Bind enabled flee resolution to a destination identity and conflict if it becomes unavailable; never reinterpret an index or redraw. Charge movement fatigue exactly once with existing skill/development adjustments; reject busy production/travel overlap.
  - Acceptance: `Move` accepts locations only; nonadjacent regional teleports reject; duration-1 conflict/capacity ordering matches baseline; grouped transport is atomic. Within one `resolve_tick`, test two caregivers targeting one dependent and the dependent acting after a transport start, including legal `Wait`. Mixed short/long flee routes select only short edges; busy/no-short-route cases consume no flee RNG draw. Earlier capacity changes cannot redirect a sampled flee. Channel-off draws/effects remain exact; closed command count remains 43.
  - Logging: DEBUG admission/start/rejection metadata with actor, endpoints, duration and reason; no motives or destination-belief payloads. Follow existing domain logging conventions.
  - Dependencies: 3, 6.

- [x] **Task 5: Advance, arrive, wait, and end journeys atomically in WorldEngine.**
  - Files: create `src/world/_travel.py`; update `src/world/_operations.py`, `_state.py`, `src/simulation/engine.py`; create `tests/unit/test_regional_travel_lifecycle.py`.
  - Add deterministic due processing, whole-group capacity checks, bounded waiting/timeout, pre-arrival and post-physical death cancellation, canonical ordering, and no-submission advancement. Keep a single candidate/commit boundary and all body placements valid.
  - Acceptance: test exact tick arithmetic, repeated empty ticks, capacity competition, swaps under existing capacity semantics, timeout, exposure location, attacked traveller, caregiver/dependent death, corpse capacity, and no partial group arrival. Compare complete ticks and event prefixes against Task 6 fixtures, including same-batch busy conflicts and post-death cleanup. Avoid double advancement on restore/retry.
  - Logging: DEBUG scheduled/due/wait transitions; INFO committed start/arrival/end metadata at engine commit boundary only; ERROR invariant failure with safe code. Never log prepared events as committed.
  - Dependencies: 4 (which depends on 6).

### Phase 3 — Persistence and agent-facing evidence

- [x] **Task 7: Extend checkpoint, replay, resume, and fork compatibility with codec v19.**
  - Files: `src/simulation/persistence.py`, `journal.py`, `replay.py`, `service.py`, `compatibility.py`; inspect/update `src/persistence/sqlalchemy.py` and snapshot mappings as necessary; create `tests/unit/test_regional_travel_checkpoint.py`, `tests/integration/test_regional_travel_persistence.py`.
  - Include immutable region definitions/routes/pending journeys in canonical enabled snapshots and integrity hashes. Update every snapshot construction, restore, accepted-version guard, branch/recovery path, and write-pair selector. Preserve prior active-channel fields in v19 and prior codec exactness.
  - Acceptance: checkpoint mid-journey or capacity-wait, replay tail, resume, idempotent durable retry, and fork/continue match uninterrupted state and subsequent observations. Only finalized-boundary-valid state may become a durable checkpoint; intermediate seek prefixes remain read-only projections. No new SQL tables/migration are required for canonical snapshot JSON; prove stored snapshot authority survives adapter round trips.
  - Logging: DEBUG checkpoint/restore versions/counts and journey count; INFO successful resume/fork metadata; ERROR hash/version mismatch safe codes, never DSNs or snapshot contents.
  - Dependencies: 2, 3, 5, 6. Task 5 is now an explicit prerequisite because live journey checkpoint parity needs its producers.

- [x] **Task 8: Expose only perceivable region, route, and personal journey facts.**
  - Files: `src/world/observations.py`, `_perception.py`; `src/simulation/serialization.py`, `perception.py`; create `tests/unit/test_regional_travel_perception.py`; update `tests/unit/test_domain_contract_evolution_policy.py`.
  - Add gated immutable local-region, visible-exit travel, and self-journey projections. Pin exact channel-on observation shapes, sorted collections, unknown membership, phase-specific witnessing, and live/restored parity.
  - Acceptance: no hidden topology, destination resources, remote population, or distant weather leaks. Departure witness and arrival witness have different evidence; busy body stays visible at origin until arrival. Live/restored observations and event-prefix inspection agree on pending/dead-before-cleanup/arrived facts without treating a prefix as a completed tick. Off-channel JSON is unchanged.
  - Logging: DEBUG projection counts/owner IDs/revision and optional-field presence; no observations, names, resources, or memory text in logs.
  - Dependencies: 5, 6, 7.

- [x] **Task 9: Form owner-scoped destination beliefs and retrieve distant evidence within budgets.**
  - Files: create `src/agents/cognition/regional_migration.py`; update `src/agents/cognition/memory.py`, `src/memory/belief_formation.py`, `beliefs.py` only where generic contracts require it, and relevant facades; inspect `src/memory/reconstruction.py`, `models.py`, `service.py` for shared selection/idempotence integration; create `tests/unit/test_regional_destination_beliefs.py`; extend `tests/integration/test_episodic_memory_pgvector.py` for durable two-lane recall parity.
  - Convert own observations/visits and delivered testimony into existing trace/belief evidence, with destination predicates, timestamps, revisions, contradiction, and confidence. Add bounded owner-only destination recall alongside local retrieval with separate deterministic destination-lane operation/reconstruction/derived IDs. Keep local IDs unchanged, deduplicate overlapping selected memories before reconstruction/access updates, and give destination recall only the remainder of shared memory/provider/timeout budgets. Reuse existing commit/reconstruction protocols rather than copying peer memories or building a global atlas.
  - Acceptance: wrong testimony remains possible; stale reports are not silently refreshed; two owners remain isolated; deterministic count/hop caps and disabled-mode passthrough hold. In-memory and durable memory adapters agree on two-lane ID uniqueness, retry-idempotence, shared-trace deduplication, reconsolidation lineage, zero-budget skip, and low/high budget degradation. Test the actual retrieve/recall path, not just a count helper. No engine or analysis import in cognition/memory.
  - Logging: DEBUG owner, evidence count, source-channel code, selected count, revision, and budget-degradation code; never proposition, utterance, recall contents, or confidence payload dumps.
  - Dependencies: 8.

### Phase 4 — Decisions, demographic analysis, and experiments

- [x] **Task 10: Integrate optional evidence-driven destination deliberation.**
  - Files: `src/agents/cognition/regional_migration.py`, existing imagination/motivation/deliberation integration points and facades; `src/simulation/runner.py`, `agent_runtime.py` where mode composition is owned; create `tests/unit/test_regional_migration_cognition.py`.
  - Bias existing alternatives using needs, private destination evidence, uncertainty, and known route costs. Return one normal adjacent `Move`/`Wait` through existing submission; travellers choose `Wait`. Retain local survival choices and bounded known-route search rebuilt from persisted owner beliefs/traces each invocation, with no automatic region-to-region planner over objective topology or unpersisted decision-authoritative route cache.
  - Acceptance: demonstrate staying, temporary exploration, evidence-led relocation, return, mistaken choice, and unknown destination behavior. Same private inputs reproduce commands; hidden-world changes alone do not change them; disabled mode leaves cognition unchanged. Checkpoint/resume with restored subjective evidence reproduces destination recall and the next command under the same budget, including graceful zero-remainder behavior.
  - Logging: DEBUG candidate counts, selected command kind, budget and safe rationale code; no private goals, beliefs, imagined scenarios, or motives.
  - Dependencies: 2, 9.

- [x] **Task 11: Implement regional population and migration evidence folds.**
  - Files: create `src/analysis/regional_population.py`, `regional_migration_metrics.py`, `regional_destination_beliefs.py`; update `src/analysis/metric_service.py`, catalog/specification/facade integration; `src/experiments/composition.py` and experiment persistence ports for detached evidence loading; create `tests/unit/test_regional_demographics.py`.
  - Implement the three metric families and analytical migration rows with explicit raw-crossing/dwell separation, assigned/unassigned coverage, entries/deaths, return flows, cohort composition, person-ticks, and available subjective-evidence coverage. Fold every actual relocation exactly once, including successful `Fled` and accepted legacy move/transport effects, from ordered pre/post placement. Implement the defined established-residence/candidate state machine without persisting it in world state. Read detached evidence only; no new `PhenomenonId` or live feedback.
  - Acceptance: conservation property tests and known-answer event timelines; grouped transport counts persons; successful cross-region fleeing changes population and failed fleeing does not; failed starts/timeouts produce no arrivals. Test entrant baseline/no-prior-residence, arrival-boundary tick 1, exact qualification, short visit then return, qualified migration then return, third-region replacement, unassigned interruption, death on threshold, multiple same-tick relocations, and partial-prefix coverage. Register three families against the current catalog baseline, updating only relevant count assertions.
  - Logging: DEBUG evidence coverage/counts and INFO completed family summaries at collection boundaries; no owner belief content. ERROR inconsistent evidence with safe code rather than fabricated counts.
  - Dependencies: 6, 7, 9.

- [x] **Task 12: Add Experiment AY and reproducible regional migration matrix arms.**
  - Files: create `src/experiments/regional_migration_scenario.py`; update `src/experiments/catalog.py`, `matrix_schema.py`, metric collection/composition; create `tests/unit/test_experiment_ay.py` and relevant matrix round-trip tests.
  - Register AY / `regional_migration@1` off the V1 gate. Use a connected graph with multiple regions and remote multi-hop area, contrasting local resources/temperature and optional seasonal conditions. Include off, physics-only, accurate-evidence, false/stale-testimony, visit/return, and blocked-arrival arms. Keep diagnostic scripted commands distinct from at least one real cognition-driven arm.
  - Acceptance: same seeds reproduce trajectories/results; off arm matches its baseline; evidence-driven decisions arise through perception/cognition, not direct goal/command injection by the collector. Population-entry and transport composition are separate testable factors, not prerequisites. No hard-coded civilization or migration success threshold.
  - Logging: INFO experiment/arm/run identifiers and result counts; DEBUG matrix schema and evidence coverage; no seeds, testimony, config dumps, or cognition payloads.
  - Dependencies: 7, 10, 11.

### Phase 5 — Presentation, regressions, and documentation

- [x] **Task 13: Present regions and discrete journeys without spatial authority leakage.**
  - Files: `src/simulation/observer_facts.py`; `src/observer/contracts.py`, `adapt.py`, `project.py`, `layout.py`, `version.py`; `src/api/observer_schemas.py`; `clients/godot-observer/scripts/protocol/models.gd`, `event_router.gd`, `scripts/view/location_layer.gd` and related existing views; create `tests/unit/test_regional_migration_observer.py`, `clients/godot-observer/tests/test_regional_travel.gd`; register it in `clients/godot-observer/tests/run_protocol.gd`.
  - Add read-only region labels/envelopes and journey status/phase facts. Extend semantic events with `JOURNEY_STARTED`, `JOURNEY_ARRIVED`, `JOURNEY_ENDED` (69 -> 72); keep existing movement handling for old events. Render origin-anchored busy travel and optional visual-only progress, never an authoritative in-between coordinate. Keep researcher population metrics and selected-agent subjective destination beliefs epistemically distinct.
  - Acceptance: live/replay/seek frames agree; protocol consumers accept explicit optional additions while older fixtures remain exact; if a pinned exact schema prevents additive evolution, version that DTO explicitly rather than silently loosening it. Headless client tests drive payload -> model -> router/reducer -> rendered state and frame replacement/backward seek for start, capacity wait, arrival, and end. Origin-anchored preparation never becomes an authoritative mid-edge marker; seek does not create a live arrival animation or duplicate move. Camera/layout/animation changes never alter world hashes; agent-view overlays expose only that owner's evidence.
  - Logging: DEBUG detached frame/event counts and client parse reason codes; no subjective strings or full frames in operational logs.
  - Dependencies: 8, 11, 12.

- [x] **Task 14: Enforce cross-feature compatibility and deterministic invariant gates.**
  - Files: `tests/unit/test_v3_v2_replay_compat.py`, `test_v3_population_flags_off_compat.py`, `test_v2_scientific_invariants.py`, `test_v1_regression_gate.py`, `test_domain_contract_evolution_policy.py`; `tests/architecture/` boundary tests; targeted new regional tests from tasks 1–13.
  - Add meaningful regression/property cases for state conservation, deterministic ordering, all off-channel payload/hash invariants, exact old-version rejection, no shared knowledge, and presentation isolation. Cover composition with public goods, dependency care, lifecycle entry/death, custody/inheritance, production busy state, and cultural memories without making those channels mandatory.
  - Acceptance: run the verification commands below, including the registered headless Godot suite, and the disposable-DB integration case when its database is available. Audit all command/relocation consumers for one-time effort/arrival handling and event-prefix parity. Record any external blocker in implementation progress rather than marking an unrun gate passed. Tests must accompany each preceding implementation task; this task owns cross-cutting coverage, not delayed basic tests.
  - Logging: use metadata-only log assertions to detect leaks and duplicate commit logs; normal pytest diagnostics, no new runtime telemetry or report artifact.
  - Dependencies: 1–13.

- [x] **Task 15: Document enabled travel semantics and the migration research contract.**
  - Files via `/aif-docs`: `docs/architecture.md`, `docs/physical-simulation.md`, `docs/experiments.md`, `docs/observer.md`, `docs/development.md`, `docs/configuration.md`; `README.md` only for landing-page links if needed.
  - Document region membership, exact flag/spec gates, runner v44 and replay 21/codec v19, origin-anchored abstract travel, cost/time formula, full-destination behavior, grouped transport/flee rules, remote evidence limits, metric denominators/dwell policy, AY reproduction, and Godot visual-only coordinates. Explain migration-substrate ownership without claiming polity simulation.
  - Acceptance: examples decode through the real config codec, commands match available tooling, all changed links resolve, and mandatory documentation checkpoint is satisfied. Any roadmap/status changes belong to `/aif-roadmap`; this plan does not authorize editing that artifact directly.
  - Logging: document supported metadata events and `PALIMPSEST_LOG_LEVEL`; no new domain logs for documentation work.
  - Dependencies: 12, 13, 14.

## Verification Commands and Completion Criteria

Run targeted new regional tests as each phase lands, then the existing required gates:

```bash
uv run --frozen --python 3.12.14 ruff check src tests
uv run --frozen --python 3.12.14 ruff format --check src tests
uv run --frozen --python 3.12.14 mypy src
uv run --frozen --python 3.12.14 lint-imports
uv run --frozen --python 3.12.14 pytest tests/architecture -q
uv run --frozen --python 3.12.14 pytest tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py tests/unit/test_v3_v2_replay_compat.py tests/unit/test_v3_population_flags_off_compat.py tests/unit/test_compatibility_matrix.py tests/unit/test_domain_contract_evolution_policy.py -q
uv run --frozen --python 3.12.14 pytest -q
```

Run the registered Godot protocol/client suite with the Godot 4.7.2 executable used by `.github/workflows/observer-image.yml`. Set `GODOT_BIN` to its executable path in the environment:

```bash
"${GODOT_BIN}" --headless --path clients/godot-observer --script res://tests/run_protocol.gd
```

Opt-in durable integration (requires the existing validated disposable `palimpsest_test` database settings):

```bash
uv run --frozen --python 3.12.14 pytest -m integration tests/integration/test_regional_travel_persistence.py tests/integration/test_episodic_memory_pgvector.py -q
```

- All 15 tasks and their acceptance checks pass; previous runner/event/codec accepted sets remain supported.
- Channel off preserves existing trajectories, observation JSON, write-pair selection, and RNG behavior.
- Channel on demonstrates ordinary location moves, long remote travel, grouped arrivals, timeout/death, sustained relocation versus visits, and distinct regional resources/environment without coordinates.
- Replay, checkpoint/resume, fork, and detached observation/observer projections agree at mid-journey and post-arrival boundaries.
- Subjective distant-region beliefs can be wrong, stale, or unknown; no objective researcher evidence reaches live decisions.
- AY is reproducible and off the V1 gate; migration/population accounting conserves living persons and reports coverage.
- Docs checkpoint is complete; Godot remains read-only and its coordinates remain non-semantic.
