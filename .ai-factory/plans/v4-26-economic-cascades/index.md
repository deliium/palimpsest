<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: Economic Cascades

Mode: ultra
Branch: main
Created: 2026-11-15

## Original Request

v4-26 economic cascades

Naming requirement:

Use `v4-26-economic-cascades`.

Model objective disruptions to production networks:

- resource loss
    
- route closure
    
- infrastructure destruction
    
- labor/population loss
    
- tool shortage

Allow effects to propagate through real dependencies.

Do not script downstream outcomes.

Track causal chains:
mine loss  
→ material shortage  
→ tool shortage  
→ food productivity decline

Provide dependency/cascade analytics.

## Settings

- Testing: yes; full strategy. Unit, architecture, determinism, properties,
  integration, Compose config/browser, Godot regression (existing suite only),
  Research UI, benchmark regression, and static gates, with coverage enabled
  for Python lanes.
- Logging: verbose, metadata-only. Bounded DEBUG window/stage/edge counts and
  detection milestones; INFO analysis composition and publication milestones;
  WARN truncation, partial coverage, unresolved chains, missing labor joins, and
  oversize payloads; ERROR safe codes. `PALIMPSEST_LOG_LEVEL` controls
  verbosity. Never log owner tokens, chain tokens, recipe ids, locations,
  quantities, distributions, cursor keys, digests, credentials, DSNs, memories,
  embeddings, or payload surrogates.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 19.
- Language: English UI and artifacts; technical terms preserved.
- Git: enabled; base `main`; no branch or worktree creation; skip-push
  preference retained. Commit checkpoints are suggestions, not authorization to
  commit during planning or implementation unless the user explicitly asks.
- Workflow: slug IDs; normal verification with explicit complete required-gate
  certification.
- Naming: canonical stem `v4-26-economic-cascades`; this plan is the ultra
  bundle `.ai-factory/plans/v4-26-economic-cascades/`. Python tokens use
  `economic_cascades` / `economic-cascades-*`; the feature name is
  "economic cascades".
- Research source: `.ai-factory/RESEARCH.md` and `.ai-factory/research/` do not
  exist; no external research conclusions are invented.
- Execution: plan only in this invocation. No implementation, commit, roadmap
  edit, or branch creation occurs while planning.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"
Rationale: V4-26 adds a seventeenth, analysis-only V4 context that measures how
objective disruptions propagate through already-owned production, route,
infrastructure, and population seams; it claims no V4 capability flag, runner
schema, command, event, write pair, API version, or migration, and it does not
close M8 or edit other milestones.

## Requirements Reconciliation

Authority: the Original Request defines scope. `.ai-factory/ARCHITECTURE.md`
("Key Principles", "Versioned Extension Contract", V3-05, V3-07, V3-11, V3-18,
V3-24, V4-01, V4-03, V4-16, V4-17, V4-18, V4-19, V4-24, V4-25 seams) and
`.ai-factory/RULES.md` constrain every edit. `.ai-factory/DESCRIPTION.md`
describes the implemented state; `.ai-factory/ROADMAP.md` is stale for V4-23
through V4-26 and stays owned by `$aif-roadmap`. Concrete contracts come from the
source paths below. No requirement source is edited to create this plan.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| V4-26 declares a seventeenth V4 context `economic_cascades` with authority `detached_analysis`, owning package `analysis`, seam `analysis_capture`, and no capability flag; contexts 16 -> 17, flags stay 12, owned stay 8, unowned stay 4, map revision becomes `v4-context-map-v5` | Original Request "Model objective disruptions to production networks"; `src/simulation/v4_architecture.py:41,59,93-111,368-375,415-475` | Task 1/18/21 |
| The new context is reuse-only and must be added to `V4_EVENT_REUSING_CONTEXTS`; it may not own a reserved or deepening write pair and needs no migration stage | `src/simulation/versioning.py:102-177`; `src/simulation/migration_plan.py:24-126` | Task 1/18 |
| No `runner-config-v57`, runner root field, per-agent key, capability flag, command, event, observer semantic type, write pair, `/v2` route, or SQL migration is added; `runner-config-v56` remains the accepted seam | `src/simulation/compatibility.py:154-166,541-551,778-801`; `src/simulation/runner_models.py:307-339`; `.ai-factory/ARCHITECTURE.md` V4-25 seam | Task 1/18/21 |
| Propagation is already emergent: missing recipe inputs reject with `materials_unavailable`; missing tools reduce craft duration and harvest probability; routes gate `Move`/`Transport`/`Flee`; destroyed infrastructure drops bonuses; dead actors issue no commands. V4-26 therefore adds no world rule and no write pair, and measures the resulting chains instead of scripting them | `src/world/_production.py:79-91,251-367`; `src/world/travel_network.py:384-457`; `src/world/_infrastructure.py:306-504,636-687`; `src/world/supply_chain.py:353-372`; `src/simulation/engine.py:6777-6790` | Task 3-6/16 |
| Silently rejected attempts (`materials_unavailable`, route rejection, stage denial) emit no event today; adding rejection events would silently widen replay-v27, so V4-26 does not add them and documents shortfall as a demand/completion gap | `src/world/_production.py:251-263`; `src/world/_rules.py:3112-3119`; `.ai-factory/ARCHITECTURE.md` requirement 1 | Task 3/19 |
| The five disruption classes map to committed events: `ResourceNodeDepleted`, `RouteConditionChanged` closed transitions, `InfrastructureDestroyed`, `Died`, and a documented tool-production decline proxy | `src/world/events.py:991,1032,1270,2860,2921`; `src/world/_physical.py:528-550`; `src/world/_travel_network.py:97-139` | Task 3/16 |
| The dependency structure comes from detached `SupplyRecipeSpec` and `SupplyStageSpec` facts plus observable topology: recipe inputs, `tool_role`, operational infrastructure kinds, non-open routes, and labor participation. No `WorldState`, `KinshipGraph`, runtime, or store object is read; the experiments bridge reads only the run's declared `ProductionCatalog` and immediately maps it to `SupplyRecipeSpec` | `src/analysis/supply_chain_events.py:77-160,395-403`; `src/world/supply_chain.py:85-127,205-218`; `src/experiments/supply_chain_completed_run.py:40-83,181-228` | Task 4/9 |
| Chains are dependency-conditioned analytical links with closed states `linked`, `unlinked`, `unresolved`, `unavailable`; they never assert objective cause and never carry severity, impact, priority, blame, class, or a composite score | Original Request "Do not script downstream outcomes"; `.ai-factory/ARCHITECTURE.md` Key Principle 1; `src/analysis/economic_inequality_contract.py:131-143` | Task 2/6/17/20 |
| Statistics are integer-milli shortfall shares, per-kind chain counts, mean depth and lag milli, and availability at 3 linked chains; windows are 32 ticks with at most 512, chain depth 6, lag 2 windows | Original Request "Track causal chains"; `src/analysis/inequality_indices.py:137-247`; `src/analysis/supply_chain_bottlenecks.py:171-205` | Task 2/5/6/17 |
| Eight metric families append 236 -> **244**: five disruption kinds, dependency structure, propagation, and coverage. The first 236 ids, order, versions, and value keys stay unchanged | `src/analysis/specifications.py:53,300-317,9098-9149,9686-9725,10463-10478`; `src/analysis/metric_service.py:436-437,2766-2816` | Task 8/18/20/21 |
| Snapshot is a sibling `economic-cascades-snapshot-v1` with store `economic-cascades-store-v1`, two dual-gated settings, window-bound cursors, and seven GET-only routes failing closed with `economic_cascades_disabled`; it is not a runner/result/replay/SQL schema | `src/simulation/economic_inequality_models.py:26-339`; `src/simulation/economic_inequality_ports.py:18-85`; `src/persistence/economic_inequality_filesystem.py:37-250`; `src/infrastructure/settings.py:268-275,317-339,514-534,958-982` | Task 10-13/21 |
| Publication is programmatic and post-completion; no CLI producer and no runner flag is added | `src/experiments/economic_inequality_publication.py:73-237`; V4-20 through V4-25 have no CLI producer | Task 12/21 |
| No Godot overlay is added: cascades are detached analysis, not a presentation fact; the presentation client is unchanged and its existing suite is the regression gate | Original Request; `.ai-factory/ARCHITECTURE.md` V3-40 through V3-42 seam | Task 14/18/21 |
| Off-gate experiment `economic_cascades@1` composes existing flags and specs in three arms and never enters the V1 A-E gate; the baseline arm has no `supply_chains` evidence and is provably inert | `src/experiments/catalog.py:5735-5772`; `src/experiments/social_mobility_scenario.py:50,146-190`; `tests/unit/test_v1_regression_gate.py` | Task 15/21 |
| Documentation covers `docs/economic-cascades.md`, README, ARCHITECTURE, DESCRIPTION, `docs/architecture.md`, `docs/configuration.md`, `docs/analysis-metrics.md`, `docs/research-api.md`, `docs/v4-architecture.md`, `docs/research-ui.md`, and cross-links in `docs/supply-chains.md`, `docs/trade-networks.md`, `docs/economic-inequality.md`, `docs/social-mobility.md`, and `docs/infrastructure-networks.md`; roadmap registration stays with `$aif-roadmap` | `.ai-factory/ARCHITECTURE.md` requirement 7; `.ai-factory/ROADMAP.md`; `docs/social-mobility.md` | Task 19/20/21 |
| Known drift to correct: `docs/economic-inequality.md` and its docs test still assert 15 current contexts; V4-26 normalizes current-state wording to 17 while leaving historical landing notes intact | `docs/economic-inequality.md:15,154`; `tests/unit/test_economic_inequality_docs.py:53,65` | Task 18/19/20 |

### Supported combinations and coverage transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| No `supply_chains` seam | Untouched run | No analysis, no `economic_cascades_*` metric input, no snapshot field | Task 9/15 |
| `supply_chains` seam, no disruption evidence | Stage and edge facts | Empty analysis with `missing` coverage; no metric documents | Task 7/9 |
| Resource depletion observed | Disruption row | One `resource_loss` row per zero crossing; no repeat while depleted | Task 3/16 |
| Route closes then stays closed | One disruption row | Repeated closed windows add no duplicate row | Task 3 |
| Route reopens | No new row | Later closure emits a new row | Task 3/5 |
| Infrastructure destroyed | Disruption row | One `infrastructure_destruction` row; asset retained as non-operational | Task 3/9 |
| Agent dies with a labor join | Disruption row plus join | Population loss may link to stages the actor worked | Task 3/6 |
| Agent dies without a labor join | Disruption row | Chain state `unresolved`, never guessed | Task 6 |
| Tool-producing stage declines | Proxy row | `tool_shortage` row with documented denominator | Task 3/5 |
| No tool-output stage | No proxy row | Kind reports `unavailable` | Task 3/7 |
| Stage demand 0 | Stage row retained | `shortfall_share_milli=0`, `availability=unavailable` | Task 5 |
| Shortfall at or above 250 milli | Stage in shortfall | Eligible for a `linked` chain | Task 5/6 |
| Reachable downstream stage in shortfall within lag | Chain row | `state=linked` with depth and lag | Task 6/17 |
| Reachable downstream stage not in shortfall | Chain row | `state=unlinked` | Task 6/17 |
| Downstream row earlier than the disruption | No link | `state=unresolved`; never back-dated | Task 6/17 |
| Depth above 6 or lag above 2 windows | Excluded | Bounded notice; no clamped chain | Task 4/6 |
| Fewer than 3 linked chains for a kind | `insufficient_samples` | Counts retained; no availability claim | Task 6/7 |
| Cap exceeded for events, disruptions, stages, edges, chains, propagation, or coverage | Deterministic prefix | `coverage="partial"` plus one bounded notice per family | Task 3/4/5/6/7 |
| Snapshot dual gate unset | No reader | 503 `economic_cascades_disabled` on all seven routes | Task 11/13 |
| Corrupt snapshot payload | No data | 500 `economic_cascades_store_corrupt` | Task 10/13 |
| Paged route with `window_index` | Filter-bound cursor | Only matching rows; cursor for another window rejected 400 | Task 10/13 |
| Publication disabled by the caller | No artifact | Nothing written; scientific status unchanged | Task 12 |
| Env-gated lane missing prerequisite | No green certification | `unexecuted` plus prerequisite | Task 21 |

No blocking open questions: every material decision is fixed below.

## Architecture and Decisions

1. **Add one analysis-only context, claim no flag.** `economic_cascades` is a
   detached analytical context. It owns no world state, no owner state, and no
   capability slot. Counts become 17 contexts / 12 flags / 8 owned / 4 unowned;
   the map becomes `v4-context-map-v5`.
2. **No objective cascade engine.** The requested chain already propagates
   through real dependencies: recipe inputs block downstream crafting, tools
   change speed and harvest probability, routes gate movement, destroyed
   infrastructure drops every service, and dead actors stop acting. V4-26
   measures that propagation and does not script it.
3. **No new events or write pair.** Rejections are silent today; adding rejection
   events would widen replay-v27. Shortfalls are reconstructed as a documented
   demand/completion gap, and the page states that limit.
4. **Dependencies are real, not correlated.** Edges come from the detached recipe
   catalog (`SupplyRecipeSpec`), tool roles, operational infrastructure kinds,
   non-open routes, and stage actor participation. No `WorldState`, runtime, or
   store object is read; only the completed-run bridge reads the run's declared
   `ProductionCatalog` (`src/experiments/supply_chain_completed_run.py`) and
   immediately maps it to `SupplyRecipeSpec`.
5. **Chains are analytical, not causal truth.** A chain is `linked` only when an
   observed disruption reaches an observed downstream shortfall along an emitted
   dependency edge within the depth and lag bounds. `unlinked` and `unresolved`
   are first-class, and no row claims a cause.
6. **No classes and no scores.** Forbidden vocabulary covers class, caste,
   stratum, elite, underclass, severity, criticality, priority, impact score,
   cascade score, risk score, blame, fault, root cause, culprit, economic
   damage, loss value, price, and money. Shares are statistical, not rank labels.
7. **One measure per class.** Resource loss = node zero crossings;
   route closure = closed transitions; infrastructure destruction = destroyed
   assets; population loss = deaths joined to stage participation; tool shortage
   = documented tool-production decline.
8. **Layers stay separate.** Objective disruptions and stage facts, dependency
   structure, and analytical chains are three types with a hard leakage guard.
   An analytical token can never appear in an objective row.
9. **Longitudinal windows.** `window_ticks=32`, `max_windows=512`. Rows carry
   window index and tick; the summary reports the latest window and window count.
10. **Bounded everything.** Events, disruptions, stages, edges, chains,
    propagation rows, coverage rows, notices, and snapshot bytes have independent
    caps with deterministic prefixes and `coverage="partial"`.
11. **Activation is opt-in and evidence-driven.** Requires committed events, the
    owned `supply_chains` seam, and at least one disruption class. No supply
    chain means no analysis and no metric documents, so default V1/V2 bundles are
    unchanged.
12. **Read-only surfaces.** `economic-cascades-snapshot-v1` is canonical,
    digest-addressed, and wall-clock-free. `economic-cascades-store-v1` is
    atomic, quota-bounded, idempotent, and corruption-safe. Seven GET-only
    dual-gated routes serve it. Publication is programmatic after completion.
13. **No presentation physics.** No Godot overlay and no client write path; the
    Research UI panel is read-only.
14. **Catalog discipline.** Eight families append exactly at positions 236-243;
    every active pin and doc footer is swept from 236 to 244 in one change.

### Locked economic-cascades summary

| Surface | Locked behavior |
| --- | --- |
| Policy | `economic-cascades.v1` (analysis and snapshot share the token) |
| V4 ownership | New analysis-only `economic_cascades`; 17 contexts / 12 flags / 8 owned / 4 unowned; map `v4-context-map-v5` |
| Runner schema | `runner-config-v56` only; no v57, no new root/per-agent key |
| Activation | Committed events **and** the `supply_chains` seam **and** at least one disruption class; otherwise disabled |
| Disruption classes | `resource_loss`, `route_closure`, `infrastructure_destruction`, `population_loss`, `tool_shortage` |
| Dependency kinds | `resource_input`, `item_input`, `tool_dependency`, `infrastructure_dependency`, `transport_dependency` |
| Labor join | Explicit actor→recipe join passed to chain linking; never an edge row and never serialized |
| Layers | objective disruption, dependency structure, analytical chain; hard separation guard |
| Evidence | `ResourceNodeDepleted`, `RouteConditionChanged` closed transitions, `InfrastructureDestroyed`, `Died`, tool-stage decline |
| Window | 32 ticks; index `tick // 32`; at most 512 windows |
| Chain bounds | Depth 6; lag 2 windows; minimum 3 linked chains for availability |
| Chain states | `linked`, `unlinked`, `unresolved`, `unavailable` |
| Shortfall | Integer milli of demand minus completions over demand; threshold 250 |
| Caps | 200k events; 4,096 disruptions; 4,096 stages; 4,096 edges; 2,048 chains; 1,024 propagation rows; 1,024 coverage rows; 8 notices |
| Snapshot | `economic-cascades-snapshot-v1`; store `economic-cascades-store-v1`; 16 publications / 8 MiB; no wall-clock field |
| Routes | 7 GET-only under `SUBJECTIVE_DEBUG`; default limit 100; max 500; `window_index` <= 511; `economic_cascades_disabled` when unset |
| Catalog | 236 -> 244 families; first 236 unchanged; active suite and docs pins swept to 244 |
| Clients | Research UI panel; no new Godot overlay |
| Experiment | `economic_cascades@1`, off the V1 gate, three arms |
| Pins | 43 commands; 73 observer semantics; replay-v27/codec `v25`; Alembic `0017`; `/v1`; `observer-protocol-v1` |

## Phase Index

1. [Phase 1: Registry, Contract, and Objective Evidence](phase-01-registry-contract-evidence.md) — Tasks 1-4
2. [Phase 2: Episode Detection, Chains, Analysis, and Metrics](phase-02-detection-chains-metrics.md) — Tasks 5-8
3. [Phase 3: Completed-Run Inputs, Snapshot, Store, and Publication](phase-03-artifact-publication.md) — Tasks 9-12
4. [Phase 4: Read Surfaces](phase-04-read-surfaces.md) — Tasks 13-14
5. [Phase 5: Experiment and Certification Paths](phase-05-experiment-certification.md) — Tasks 15-17
6. [Phase 6: Invariants, Documentation, and Certification](phase-06-invariants-docs.md) — Tasks 18-21

## Cross-Phase Dependencies

- Task 2 depends on Task 1 for the context token used in policy names.
- Tasks 3 and 4 depend on Task 2 for tokens, policy, and row types.
- Task 5 depends on Tasks 3 and 4 for disruption rows, stage rows, and edges.
- Task 6 depends on Task 5 for episodes and shortfalls, and Task 4 for edges.- Task 7 depends on Tasks 3-6 for harvest composition.
- Task 8 depends on Task 7 for `EconomicCascadesAnalysis`.
- Task 9 depends on Tasks 4, 7, and 8 for recipe extraction, analysis, and
  metric input.
- Task 10 depends on Task 8 for metric availability tokens.
- Task 11 depends on Task 10 for snapshot encode/decode.
- Task 12 depends on Tasks 7, 9, 10, and 11 for analyze → compose → store.
- Task 13 depends on Tasks 10 and 11 for paging, cursors, and the reader.
- Task 14 depends on Task 13 for the route contract.
- Task 15 depends on Tasks 1, 9, and 12 for context, collector, and publication.
- Task 16 depends on Tasks 9, 12, and 13 for the real path; it does not depend on
  the experiment registration because it builds its own V56 run.
- Task 17 depends on Task 16 for deterministic fixtures.
- Task 18 depends on Tasks 1-17 for the final pin sweep.
- Task 19 depends on Task 18 for the docs count sweep.
- Task 20 depends on Task 19 for the parity assertions.
- Task 21 depends on Tasks 16-20.

## Tasks

### Phase 1: Registry, Contract, and Objective Evidence
- [x] Task 1: Register the analysis-only `economic_cascades` V4 context ([details](phase-01-registry-contract-evidence.md#task-1-register-the-analysis-only-economic_cascades-v4-context))
- [x] Task 2: Lock the `economic-cascades.v1` contract, policy, caps, and row DTOs ([details](phase-01-registry-contract-evidence.md#task-2-lock-the-economic-cascadesv1-contract-policy-caps-and-row-dtos))
- [x] Task 3: Harvest the five objective disruption classes ([details](phase-01-registry-contract-evidence.md#task-3-harvest-the-five-objective-disruption-classes))
- [x] Task 4: Build the dependency structure and stage rows ([details](phase-01-registry-contract-evidence.md#task-4-build-the-dependency-structure-and-stage-rows))

### Phase 2: Episode Detection, Chains, Analysis, and Metrics
- [x] Task 5: Detect disruption episodes and quantized stage shortfalls ([details](phase-02-detection-chains-metrics.md#task-5-detect-disruption-episodes-and-quantized-stage-shortfalls)) (depends on 3, 4)
- [x] Task 6: Link dependency-conditioned chains and compose propagation rows ([details](phase-02-detection-chains-metrics.md#task-6-link-dependency-conditioned-chains-and-compose-propagation-rows)) (depends on 4, 5)
- [x] Task 7: Compose the bounded `EconomicCascadesAnalysis` harvest ([details](phase-02-detection-chains-metrics.md#task-7-compose-the-bounded-economiccascadesanalysis-harvest)) (depends on 5, 6)
- [x] Task 8: Append eight metric families (236 → 244) and wire the service ([details](phase-02-detection-chains-metrics.md#task-8-append-eight-metric-families-236--244-and-wire-the-service)) (depends on 7)

### Phase 3: Completed-Run Inputs, Snapshot, Store, and Publication
- [x] Task 9: Wire completed-run inputs and collector injection ([details](phase-03-artifact-publication.md#task-9-wire-completed-run-inputs-and-collector-injection)) (depends on 4, 7, 8)
- [x] Task 10: Add snapshot models, codec, paging, and ports ([details](phase-03-artifact-publication.md#task-10-add-snapshot-models-codec-paging-and-ports)) (depends on 8)
- [x] Task 11: Add the atomic store and dual-gated settings ([details](phase-03-artifact-publication.md#task-11-add-the-atomic-store-and-dual-gated-settings)) (depends on 10)
- [x] Task 12: Compose and publish completed-run snapshots ([details](phase-03-artifact-publication.md#task-12-compose-and-publish-completed-run-snapshots)) (depends on 7, 9, 10, 11)

### Phase 4: Read Surfaces
- [x] Task 13: Add seven GET-only dual-gated routes ([details](phase-04-read-surfaces.md#task-13-add-seven-get-only-dual-gated-routes)) (depends on 10, 11)
- [x] Task 14: Add the Research UI client and panel ([details](phase-04-read-surfaces.md#task-14-add-the-research-ui-client-and-panel)) (depends on 13)

### Phase 5: Experiment and Certification Paths
- [x] Task 15: Register off-gate `economic_cascades@1` ([details](phase-05-experiment-certification.md#task-15-register-off-gate-economic_cascades1)) (depends on 1, 9, 12)
- [x] Task 16: Add in-process end-to-end coverage ([details](phase-05-experiment-certification.md#task-16-add-in-process-end-to-end-coverage)) (depends on 9, 12, 13)
- [x] Task 17: Add determinism, property bounds, and leakage coverage ([details](phase-05-experiment-certification.md#task-17-add-determinism-property-bounds-and-leakage-coverage)) (depends on 16)

### Phase 6: Invariants, Documentation, and Certification
- [x] Task 18: Sweep context, catalog, and ownership pins ([details](phase-06-invariants-docs.md#task-18-sweep-context-catalog-and-ownership-pins)) (depends on 1-17)
- [x] Task 19: Documentation via `$aif-docs` ([details](phase-06-invariants-docs.md#task-19-documentation-via-aif-docs)) (depends on 18)
- [x] Task 20: Add documentation pin and negative parity checks ([details](phase-06-invariants-docs.md#task-20-add-documentation-pin-and-negative-parity-checks)) (depends on 19)
- [x] Task 21: Required-gate verification certification ([details](phase-06-invariants-docs.md#task-21-required-gate-verification-certification)) (depends on 16-20)

## Commit Plan

- **Commit 1** (after tasks 1-4): `feat(analysis): add economic cascade contract and disruption evidence`
- **Commit 2** (after tasks 5-9): `feat(analysis): compose economic cascade chains and metrics`
- **Commit 3** (after tasks 10-14): `feat(simulation): publish economic cascade snapshots and read surfaces`
- **Commit 4** (after tasks 15-17): `test: certify economic cascade experiment and end-to-end paths`
- **Commit 5** (after tasks 18-21): `test,docs: sweep V4 context and catalogue pins`

Commit checkpoints are suggestions only. Do not commit during `$aif-implement`
unless the user explicitly authorizes commits.

## Definition of Done

- V4-26 adds exactly one analysis-only context, `economic_cascades`; counts are
  17 contexts / 12 flags / 8 owned / 4 unowned; the map is `v4-context-map-v5`;
  no capability flag, `runner-config-v57`, runner root field, per-agent key,
  command, event, observer semantic type, write pair, `/v2` route, or migration
  is added.
- The five requested disruption classes are measured from committed objective
  evidence only, and no new world rule or rejection event exists.
- Propagation follows real dependency edges derived from detached recipe facts,
  tool roles, operational infrastructure, non-open routes, and labor
  participation; no `WorldState`, runtime, or store object is read, and the
  declared production catalog is read only by the experiments bridge.
- Chains are `linked`, `unlinked`, `unresolved`, or `unavailable`; no row asserts
  objective causality, and shortfall-before-disruption is never linked.
- Objective disruptions, dependency structure, and analytical chains are separate
  layers with a hard leakage guard; no composite severity, impact, risk, class,
  merit, or cascade score exists.
- Statistics are integer-milli shortfall shares, chain counts, mean depth and
  lag, and availability at 3 linked chains; depth is capped at 6 and lag at 2
  windows.
- Eight metric families append exactly at positions 236-243; the first 236 ids,
  order, versions, and value keys are unchanged; every active pin and docs
  footer is swept to 244.
- Analysis activates only with committed events, the `supply_chains` seam, and a
  disruption class; otherwise no metric input, no snapshot field, and no off-path
  change.
- `economic-cascades-snapshot-v1` round-trips canonically with no wall-clock
  field; `economic-cascades-store-v1` is atomic, quota-bounded, idempotent, and
  corruption-safe.
- Seven GET-only dual-gated routes fail closed with
  `economic_cascades_disabled`, default limit 100, max 500, `window_index` <=
  511; the Research UI panel is read-only; no new Godot overlay exists.
- Publication is programmatic and post-completion; no CLI producer or runner
  flag is added.
- Off-gate `economic_cascades@1` is registered with three arms and is absent from
  the V1 A-E gate; the baseline arm is inert.
- Commands stay 43; observer semantics stay 73; replay-v27/codec `v25` stay the
  maximum; Alembic stays `0017`; `/v1` and `observer-protocol-v1` stay.
- The in-process E2E uses real admission, real commands, real events, a real
  snapshot, a real store, and a real API read.
- Determinism across hash seeds, cap-bound properties, and leakage guards pass;
  cross-seam coverage exercises collector → analysis, multi-window paging,
  cumulative publication bytes, corrupt-store handling, and dual-gate failure.
- Docs cover the new page plus README, ARCHITECTURE, DESCRIPTION,
  `docs/architecture.md`, `docs/configuration.md`, `docs/analysis-metrics.md`,
  `docs/research-api.md`, `docs/v4-architecture.md`, `docs/research-ui.md`, and
  cross-links in `docs/supply-chains.md`, `docs/trade-networks.md`,
  `docs/economic-inequality.md`, `docs/social-mobility.md`, and
  `docs/infrastructure-networks.md`, with positive and negative parity checks.
- Required gates are certified or explicitly `unexecuted`; the roadmap remains
  owned by `$aif-roadmap`, which must register V4-23 through V4-26 later.

## Verification Receipt

Filled by Task 21. No lane is green until its command and result are recorded
here.

| Lane | Command | Result | Prerequisite / note |
| --- | --- | --- | --- |
| Unit + architecture correctness | `uv run pytest tests/unit tests/architecture -q` | 11989 passed, 1 skipped | re-run after the verification test-gap fix |
| Focused economic-cascade suites | `uv run pytest tests/unit/test_economic_cascades_*.py tests/architecture/test_economic_cascades_*.py tests/integration/test_economic_cascades_store_api.py -q` | 209 passed, 1 skipped, 3 deselected | integration lane runs separately with `-m integration` |
| Python coverage (focused) | `uv run pytest tests/unit/test_economic_cascades_*.py tests/architecture/test_economic_cascades_*.py -q --cov=src --cov-report=term` | 209 passed, 1 skipped; lane-scoped total 26% | lane-scoped coverage only |
| Python coverage (full lane) | `uv run pytest tests/unit tests/architecture -q --cov=src --cov-report=term` | 11985 passed, 1 skipped; total 79% | pre-fix full-coverage run; not re-measured after adding three tests, and no production code changed |
| Static: Ruff | `uv run ruff check src tests` | All checks passed |  |
| Static: mypy | `uv run mypy src tests` | Success: no issues found in 2813 source files |  |
| Static: import boundaries | `uv run lint-imports` | 25 contracts kept, 0 broken |  |
| Integration (non-scale) | `uv run pytest tests/integration -m "not scale" -q` | 62 passed, 60 skipped, 5 deselected | PostgreSQL-free lanes |
| Economic-cascade store/API integration | `uv run pytest tests/integration/test_economic_cascades_store_api.py -q -m integration` | 3 passed |  |
| Compose config | `docker compose config` | exit 0 |  |
| Research UI tests | `cd clients/research-ui && ./node_modules/.bin/vitest run` | 70 files, 327 tests passed |  |
| Research UI types | `cd clients/research-ui && ./node_modules/.bin/svelte-check --tsconfig ./tsconfig.app.json` | 0 errors, 0 warnings |  |
| Godot regression | `GODOT_BIN=~/.cache/palimpsest-godot/Godot_v4.7.2-stable_linux.x86_64 "$GODOT_BIN" --headless --path clients/godot-observer --script res://tests/run_protocol.gd` | `godot_protocol_tests failed=0` | existing suite only; no client change |
| Compose/browser acceptance | attested image + headed browser harness | unexecuted | requires an attested image |
| Benchmark regression (non-scale) | `PALIMPSEST_V4_SCALE_IDS=100000 uv run pytest tests/benchmarks -m "not scale" -q` | 1 passed, 20 deselected |  |

`git status` must confirm no `.ai-factory/ROADMAP.md` edit from this plan, no
`alembic/versions/0018*` file, no `clients/godot-observer/` source change, no
`/v2` route, and no new V4 capability flag. The new context registration,
analysis modules, snapshot/store, seven routes, Research UI panel, eight metric
families, docs, and off-gate experiment are the only V4-26 surfaces changed.
