<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-19 Supply Chains

Mode: ultra
Branch: main
Created: 2026-11-10
Plan identifier: `v4-19-supply-chains`

## Original Request

v4-19 supply chains

Naming requirement:

Use `v4-19-supply-chains`.

Extend V3 crafting into multi-stage production chains.

Example:

ore  
→ processed material  
→ tool  
→ improved harvesting  
→ food

Track dependencies between:

resources  
skills  
tools  
locations  
infrastructure  
organizations

Do not create a globally optimized supply-chain planner.

Agents/organizations plan locally.

Add analytics for dependency graphs and bottlenecks.

## Settings

- Testing: yes; full strategy. Unit, architecture, determinism, integration,
  Compose/browser, Godot regression (existing suites only), Research UI,
  benchmark regression, and static gates, with coverage enabled for Python
  lanes.
- Logging: verbose, metadata-only. Bounded DEBUG stage/edge/chain counts and
  selected stage priorities, INFO activation/publication/build milestones, WARN
  truncation/partial coverage/unresolved evidence, ERROR safe codes.
  `PALIMPSEST_LOG_LEVEL` controls operational verbosity. Never log item names,
  recipe inputs, inventories, organization claim bodies, observation bodies,
  actor or location sets in bulk, cursor keys, credentials, tokens, DSNs,
  memories, embeddings, utterance bodies, or payload surrogates.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 23.
- Language: English UI and artifacts; technical terms preserved.
- Git: enabled; base `main`; no branch or worktree creation; skip-push
  preference retained. Commit checkpoints are suggestions, not authorization to
  commit during planning or implementation unless the user explicitly asks.
- Workflow: slug IDs; normal verification with explicit complete required-gate
  certification.
- Naming: canonical stem `v4-19-supply-chains`; the ultra bundle directory is
  `.ai-factory/plans/v4-19-supply-chains/`, phase files use
  `phase-NN-<slug>.md`, and `index.md` is the canonical entrypoint.
- Research source: `.ai-factory/RESEARCH.md` and `.ai-factory/research/` do not
  exist; no external research conclusions are invented.
- Execution: plan only in this invocation. No implementation, commit, roadmap
  edit, or branch creation occurs while planning.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"
Rationale: V4-19 claims the already-declared `supply_chains` V4 context and
deepens V3 crafting, storage, and transport into validated multi-stage chains
with local planning and detached dependency/bottleneck analytics, adding no
central planner, quota, or automatic allocation. This plan does not edit or
close the roadmap; `$aif-roadmap` must register V4-19 in M8 and record that the
owned V4 flag count moves from six to seven. The same roadmap pass must also
register the currently unregistered V4-17 travel-network and V4-18 trade-network
landings.

## Requirements Reconciliation

Authority: the Original Request defines scope; `.ai-factory/ARCHITECTURE.md`
("Key Principles", "Versioned Extension Contract", V4-01 through V4-18 seams)
and `.ai-factory/RULES.md` constrain every edit; `.ai-factory/DESCRIPTION.md` and
`.ai-factory/ROADMAP.md` describe current state; `src/world/production.py`,
`src/world/_production.py`, `src/world/events.py`, `src/world/actions.py`,
`src/agents/cognition/production.py`, `src/agents/cognition/configuration.py`,
`src/agents/cognition/loop.py`, `src/agents/cognition/deliberation.py`,
`src/simulation/v4_architecture.py`, `src/simulation/compatibility.py`,
`src/simulation/runner_models.py`, `src/simulation/runner.py`,
`src/simulation/engine.py`, `src/analysis/trade_networks_*`,
`src/analysis/specifications.py`, `src/analysis/organization_operations.py`,
`src/simulation/trade_networks_*`, `src/persistence/trade_networks_filesystem.py`,
`src/api/routes/trade_networks.py`, and `src/experiments/catalog.py` define the
concrete contracts. `tests/architecture/test_v4_architecture_invariants.py`,
`tests/unit/test_v4_scaffolding_gate.py`, and the trade-network boundary suites
govern compatibility.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| V4-19 owns the declared `supply_chains` V4 context; contexts stay 14, flags 12, owned 7, unowned 5; no new context, flag slot, `runner-config-v57`, root field, or per-agent key | Original Request; `v4_architecture.py` 198-211; `compatibility.py` 155-164; `runner_models.py` 327/1133-1180 | Task 3/22/25 |
| The registry declares `uses_existing_events=True`, `authority=OBJECTIVE_WORLD`, owners `("world","simulation")`, prerequisite `INFRASTRUCTURE_NETWORKS`; prerequisites are planning order and never a runtime gate, so infrastructure may stay off | `v4_architecture.py` 92-93/198-211 | Task 3/6/25 |
| No new command, event, observer semantic type, replay marker, codec marker, write pair, API version, or Alembic migration; commands 43, semantics 73, replay max `EVENT_SCHEMA_REPLAY_V27`/`v25`, Alembic `0017` | Original Request; `actions.py` 911-1003; `observer/version.py` 11-167; `versioning.py` 40-100; `events.py` 3938-3960 | Task 2/3/22/25 |
| No central planner, optimizer, quota, automatic allocation, price, money, currency, score, ranking, severity, or recommendation; the registry's non-goals are preserved verbatim | Original Request; `v4_architecture.py` 207-210; `RULES.md` axioms | Task 1/3/5/8/9/22/24 |
| Multi-stage chains use existing recipe primitives: one output per recipe, harvest recipes take a `ResourceNameInput`, item intermediates are `HeldItemNameInput`, so produced items feed later recipes with no new event field | `production.py` 160-354/471-528; `_production.py` 289-302/365-385/500-564 | Task 1/2/20 |
| The legacy six-recipe `example_production_catalog()` and its digest stay byte-identical; chain recipes live in `SUPPLY_CHAIN_RECIPES` and are applied only by `supply_chain_production_catalog()` from an explicit scenario | Original Request; `production.py` 357-398/471-528; `tests/unit/test_production_catalog.py` 68 | Task 2/19/22 |
| Tool-assisted harvesting is the chain's terminal mechanic: a held `STRIKE` tool adds 0.10 to harvest success probability (clamped to 1.0) only when `supply_chains` is active, never consuming the tool; harvest duration is not a scheduling effect | Original Request example; `engine.py` 6661-6700; `_production.py` 434-497 | Task 4/20 |
| Agents plan locally with a one-step stage-readiness order (`harvest → craft → build → repair → store`), deterministic ties by recipe id, using only believed recipe ids and the current observation; no lookahead, optimizer, price, or cross-agent state | Original Request; `agents/cognition/production.py` 225-315; `configuration.py` 765/1488/1815/2095; `runner.py` 1639/2904/6694/7076 | Task 4/20/21 |
| Organizations plan only as compositions of member commands plus owner `org_op_v1` procedure claims; no organization actor, executor, treasury, or allocation exists | Original Request; `agents/cognition/organization_operations.py` 89-171; `analysis/organization_operations.py` 302-330/414-453/814-869 | Task 4/6/13/18 |
| Analysis evidence is committed events only (`ResourceHarvested`, `CraftStarted`, `ItemCrafted`, `StructureBuilt/Repaired`, `ItemStored`, movement events) plus explicitly detached recipe specs, objective skill levels, operational infrastructure facts, and owner organization claims; no `WorldState` read | Original Request; `events.py` 602-1237/344-390/3960; `runner_models.py` 6364/6375/6394; `_production.py` 500-564 | Task 6/13/21 |
| Six requested dependency dimensions are tracked with ten closed edge kinds; each optional dimension has its own coverage state and fabricates no edge when its input is `missing` | Original Request; `trade_networks_events.py` 576-588 | Task 6/7/10/22 |
| Chains are observed dependency paths of depth 2-8 with content-addressed `sc-chain-` ids; lineage is forward-only across every window from first to last, including empty windows | Original Request "emerge, disappear and reroute" applied to chains; `migration_displacement_identity.py` 159-252 | Task 7/9/20 |
| Bottlenecks use seven closed kinds and the locked thresholds (min 3 events, 750 milli share, 250 milli shortfall, demand ≥ 3); rows carry counts and integer ratios, never severity, rank, or a recommendation | Original Request; `trade_networks_detection.py` 40-46 | Task 5/8/22/24 |
| Six metric families append 198 → **204**; the first 198 ids, order, versions, and value keys stay unchanged, and every suite pin is swept in the same change | `specifications.py` 52-53/8723-8899/9387-9392/9414-9422; 71 files pin `198` at plan time | Task 11/12/22/24 |
| Snapshot is a sibling `supply-chains-snapshot-v1` with store `supply-chains-store-v1`, two dual-gated settings, window-bound cursors, and seven GET-only routes failing closed with `supply_chains_disabled`; it is not a runner/result/replay/SQL schema | `trade_networks_models.py`; `trade_networks_ports.py`; `trade_networks_filesystem.py`; `settings.py` 248-249; `api/app.py` 479-506 | Task 14/15/16/17 |
| No Godot overlay is added: dependency graphs and bottleneck rows are non-spatial analytical structures; the presentation client is unchanged and its existing suite is the regression gate | Original Request; Phase 5 objective; `clients/godot-observer/tests/run_protocol.gd` | Task 18/25 |
| Off-gate experiment `supply_chains@1` is registered and never enters the V1 A–E gate | `catalog.py` 244-246/2800-2833/5611-5667 | Task 19/25 |
| Documentation covers the page, README, ARCHITECTURE, DESCRIPTION, `docs/architecture.md`, `docs/configuration.md`, and the infrastructure ownership note; roadmap registration stays with `$aif-roadmap` | ARCHITECTURE requirement 7; `.ai-factory/ROADMAP.md` 118-162; `docs/configuration.md` 539-548 | Task 23/24/25 `git status` |

### Supported combinations and coverage transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| Flag off, legacy catalog | Legacy six recipes | Byte-identical construction, order, durations, probability; no supply metrics inputs | Task 3/4/20 |
| Flag on, no catalog | No recipes | Construction fails closed `supply_chain_catalog_missing` | Task 3 |
| Flag on, legacy catalog | Two item edges only | Construction fails closed `supply_chain_catalog_no_chain` | Task 1/3 |
| Flag on, extended catalog | Six chain stages | Validated acyclic graph, `edge_count == 6`, `max_depth >= 3` | Task 1/2/3 |
| Harvest at a location with a `grain` resource | `ResourceHarvested` | `grain` item created; `resource→item` edge on success | Task 2/6/7 |
| Harvest failure | Attempt row only | No edge; success-rate evidence retained | Task 6/8 |
| Multi-tick craft | `CraftStarted` + next-tick `ItemCrafted` | Paired completion inherits consumed input names; `item→item` edge | Task 6/7 |
| One-tick craft | `ItemCrafted` only | Completed, no input evidence, notice `unresolved_craft_inputs`, no edge | Task 6/8 |
| Craft attempt without completion | `CraftStarted` only | Demand counted; no edge; shortfall candidate | Task 6/8 |
| Held `STRIKE` tool, flag on | Harvest probability 0.90 + 0.10 = 1.0 | Draw skipped on clamp; tool not consumed | Task 4/20 |
| Same actor, no tool or flag off | Probability 0.90 | No bonus; no fabricated tool evidence | Task 4 |
| Tool stage below downstream demand | Tool completion count | `tool_dependency` when shortfall ≥ 250 milli and demand ≥ 3 | Task 8 |
| Structure build/repair/store completion | Terminal completed stage | `item→structure` / `item→storage` edge | Task 6/7 |
| Consumed item created at another location | `SupplyItemCreation.location` differs | `transport` edge plus `created_elsewhere_count`; `transport_dependency` at ≥750 milli | Task 7/8 |
| No operational infrastructure facts | Infrastructure coverage `missing` | No infrastructure edges or dependency rows | Task 6/7/8 |
| Operational infrastructure facts | Location→kind facts | `infrastructure_to_stage` edges; dependency at ≥750 milli | Task 6/7/8 |
| No objective skill levels | Skill coverage `missing` | No skill edges; `skill_constraint` skipped | Task 6/7/8 |
| Objective skill levels | `SkillAuditSide.OBJECTIVE` rows | `skill_to_stage` edges; constraint at low-level share ≥750 milli | Task 6/7/8 |
| No organization claims | Organization coverage `missing` | No organization edges; row family empty | Task 6/7/13 |
| Organization claims supplied | Owner-local tokens + actor ids | `organization_to_stage` only for claimed performers; dependency at ≥750 milli | Task 6/7/8 |
| Two consecutive windows share ≥ 500 milli of the smaller chain edge set | Same chain identity | `continued` (equal edges) or `transformed` (reroute) | Task 9 |
| One previous chain, two successors | Forward lineage | `split`; parents never rewritten | Task 9 |
| Two previous chains, one successor | Forward lineage | `merge`; parents never rewritten | Task 9 |
| No successor / no predecessor | Forward lineage | `dissolved` / `emerged` | Task 9 |
| One or more empty windows | Empty-window lineage | `dissolved` then `emerged`; never a silent `continued` | Task 9/21 |
| Chain persists through continued/transformed | Sustained chain | Sustained counts retained; no score | Task 9/10 |
| Row or cap exceeded | Deterministic prefix | `coverage="partial"` plus one bounded truncation notice | Task 6/7/8/14/21 |
| Snapshot dual gate unset | No reader | 503 `supply_chains_disabled` on all seven routes | Task 15/17 |
| Corrupt snapshot payload | No data | 500 `supply_chains_store_corrupt` | Task 15/17 |
| Paged route with `window_index` | Filter-bound cursor | Only matching rows; cursor for another window rejected 400 | Task 14/17 |
| Publication disabled in CLI | No artifact | Nothing written; scientific status unchanged | Task 16 |
| Another unowned V4 flag | Unchanged | `capability_unimplemented`; fixtures repointed to `markets_credit` | Task 3/12/22 |
| Env-gated lane missing prerequisite | No green certification | `unexecuted` plus prerequisite | Task 25 |

No blocking open questions: every material decision is fixed below.

## Architecture and Decisions

1. **Own the declared seam.** V4-19 claims `supply_chains`, which already
   declares objective-world authority, existing events, and the non-goals "no
   central planner or quota" and "no automatic allocation of items". Counts
   become 14 contexts / 12 flags / 7 owned / 5 unowned.
2. **Legacy catalogs are immutable.** `example_production_catalog()` and
   `production_catalog_digest` do not change. Chain recipes are a closed tuple in
   `world.supply_chain` applied by `supply_chain_production_catalog()` in base
   order plus append order, so serialized config order stays stable.
3. **Inputs are typed, not flattened.** `SupplyStageSpec` separates resource
   inputs, item inputs, and kind inputs so harvest recipes never create
   self-edges and the legacy catalog validates unchanged.
4. **No new write pair.** V4-19 adds no event, command, observer semantic type,
   replay marker, codec marker, or migration. Supply-chain runs write 23/`v21`
   or 27/`v25` only when the infrastructure or travel channel is active;
   `supply_chains` activates no pair by itself.
5. **Chain mechanics are ordinary production.** Admission stays in
   `world._production`; the additions are the explicit chain catalog, catalog
   validation, and a flag-gated harvest probability bonus. No new command or
   event carries chain structure.
6. **Tool assistance is a real outcome.** A held `STRIKE` tool raises harvest
   success probability by 0.10 (clamped); duration alone is metadata and is not
   used as the mechanic.
7. **Local planning is one step deep.** Cognition orders believed recipe ids by
   locally ready stage, compiles at most one existing command, and keeps all
   veto/target rules. No lookahead, global catalog read, price, quota, or
   cross-agent planning.
8. **Organizations compose, never execute.** Organizational planning remains
   member commands plus owner procedure claims; analysis joins claims to
   observed stages by performer actor, read-only.
9. **Evidence is event-sourced plus explicitly detached.** Committed events
   provide stages, attempts, completions, locations, and movement. Recipe
   structure, objective skill levels, operational infrastructure, and owner
   organization claims arrive detached with per-dimension coverage.
10. **Ten edge kinds cover six dimensions.** `resource_to_item`, `item_to_item`,
    `item_to_structure`, `item_to_storage`, `transport`,
    `location_to_stage`, `infrastructure_to_stage`, `organization_to_stage`,
    `tool_to_stage`, and `skill_to_stage`.
11. **Chains and lineage.** Chains are depth 2-8 observed dependency paths with
    content-addressed `sc-chain-` ids; lineage compares consecutive windows by
    edge-set overlap (≥ 500 milli of the smaller set) and yields
    `emerged/continued/transformed/split/merge/dissolved`, including empty-window
    gaps. Sustained counts exist; no score does.
12. **Bottlenecks are descriptions.** Seven closed kinds with fixed thresholds
    produce counts and integer milli ratios. No severity, ranking, priority,
    recommendation, or suggested action exists.
13. **Bounded everything.** Evidence, stages, edges, chains, bottlenecks,
    locations, organizations, and lineage edges truncate deterministically with
    `coverage="partial"` and one bounded notice.
14. **Snapshot and read-only surfaces.** `supply-chains-snapshot-v1` is a
    canonical sibling with digest/publication id and no wall-clock field; the
    `supply-chains-store-v1` store is atomic; cursors bind `window_index`; seven
    GET-only dual-gated routes serve it.
15. **Clients and pins.** The Research UI adds one read-only panel; Godot gets no
    new overlay. Six metrics append 198 → 204, every suite pin is swept, and
    `supply_chains@1` stays off the V1 gate. `$aif-roadmap` registers V4-19 (and
    the missing V4-17/V4-18 entries).

### Locked supply-chain summary

| Dimension | Locked behavior |
| --- | --- |
| Policy | `supply-chains.v1` (world and analysis share the version token) |
| V4 ownership | `supply_chains` owned; 14 contexts / 12 flags / 7 owned / 5 unowned |
| Runner schema | `runner-config-v56` only; no v57, no new root/per-agent field |
| Legacy catalog | Unchanged six recipes, order, and digest |
| Chain catalog | `harvest_grain`, `mill_grain`, `bake_bread`, `craft_plank`, `craft_tool_head`, `assemble_tool` |
| Chain edges | `grain→flour`, `flour→bread`, `wood→plank`, `stone→tool_head`, `plank→fine_tool`, `tool_head→fine_tool` |
| Tool mechanic | Held `STRIKE` tool adds +0.10 harvest success probability (clamped 1.0) only when active |
| Local plan | Stage order `harvest, craft, build, repair, store`; ties by recipe id; one command; no lookahead |
| Window | 32 ticks; index `tick // 32`; at most 512 windows |
| Node kinds | `resource`, `item`, `structure`, `storage`, `location`, `infrastructure`, `organization`, `tool`, `skill` |
| Edge kinds | `resource_to_item`, `item_to_item`, `item_to_structure`, `item_to_storage`, `transport`, `location_to_stage`, `infrastructure_to_stage`, `organization_to_stage`, `tool_to_stage`, `skill_to_stage` |
| Coverage | `complete`/`partial`/`missing` for evidence, skill, infrastructure, organization, lineage, plus aggregate |
| Chain | Depth 2-8; `sc-chain-` content address; cap 4096 |
| Lineage | Consecutive windows incl. empty; overlap ≥ 500 milli; emerged/continued/transformed/split/merge/dissolved |
| Bottleneck kinds | `upstream_shortfall`, `single_location_concentration`, `transport_dependency`, `tool_dependency`, `infrastructure_dependency`, `organization_dependency`, `skill_constraint` |
| Thresholds | min events 3; share 750 milli; shortfall 250 milli; demand min 3; low skill 0.125 |
| Caps | Evidence 200,000; stages 4,096; edges 16,384; chains 4,096; bottlenecks 4,096; locations 4,096; organizations 2,048; lineage 16,384 |
| Snapshot | `supply-chains-snapshot-v1`; store `supply-chains-store-v1`; 16 publications / 8 MiB; no wall-clock field |
| Routes | 7 GET-only under `SUBJECTIVE_DEBUG`; default limit 100; `supply_chains_disabled` when unset |
| Catalog | 198 → 204 families; suite pins swept to 204 |
| Clients | Research UI panel; no new Godot overlay |
| Pins | 43 commands; 73 observer semantics; replay-v27/codec `v25` max; Alembic `0017`; `/v1`; `observer-protocol-v1` |

## Phase Index

1. [Phase 1: World Chain Mechanics](phase-01-world-chain-mechanics.md) — Tasks 1-4
2. [Phase 2: Analysis Contract and Evidence](phase-02-analysis-contract-and-evidence.md) — Tasks 5-7
3. [Phase 3: Bottlenecks, Identity, Metrics, and Pins](phase-03-bottlenecks-identity-metrics.md) — Tasks 8-12
4. [Phase 4: Collection and Publication](phase-04-collection-and-publication.md) — Tasks 13-16
5. [Phase 5: Read-Only Surfaces](phase-05-read-only-surfaces.md) — Tasks 17-18
6. [Phase 6: Experiment and End-to-End](phase-06-experiment-and-e2e.md) — Tasks 19-21
7. [Phase 7: Invariants and Pins](phase-07-invariants-and-pins.md) — Task 22
8. [Phase 8: Documentation and Verification](phase-08-docs-and-verification.md) — Tasks 23-25

## Cross-Phase Dependencies

- Task 2 depends on Task 1 (stage derivation and validation).
- Tasks 3-4 depend on Tasks 1-2 (catalog and contract).
- Task 6 depends on Task 5 (policy/caps/contract).
- Task 7 depends on Task 6 (evidence rows).
- Task 8 depends on Task 7 (graph edges and shares).
- Task 9 depends on Task 7 (chains to link).
- Task 10 depends on Tasks 7-9 (graph, bottlenecks, lineage).
- Task 11 depends on Task 10 (analysis object) and the locked value keys.
- Task 12 depends on Task 11 (catalog count and ownership set).
- Task 13 depends on Tasks 10-11 (analysis and metrics).
- Task 14 depends on Tasks 10-11 (row families and counts).
- Task 15 depends on Task 14 (snapshot codec).
- Task 16 depends on Tasks 13-15 (builder, snapshot, store).
- Task 17 depends on Tasks 14-16 (snapshot, store, publication).
- Task 18 depends on Task 17 (routes and schemas).
- Task 19 depends on Tasks 3-4, 11, and 13 (flag, catalog, metrics, collector).
- Task 20 depends on Tasks 16, 17, and 19 (publication, API, scenario).
- Task 21 depends on Task 20 (stable E2E fixtures).
- Task 22 depends on Tasks 1-21 (all pins).
- Task 23 depends on Task 22 (pins before prose).
- Task 24 depends on Task 23 (docs to pin).
- Task 25 depends on Tasks 20-22 and 24 (gates and docs).

## Tasks

### Phase 1: World Chain Mechanics
- [x] Task 1: Lock `supply-chains.v1` stage contract and catalog validation ([details](phase-01-world-chain-mechanics.md#task-1-lock-supply-chainsv1-stage-contract-and-catalog-validation))
- [x] Task 2: Add the multi-stage chain recipe set ([details](phase-01-world-chain-mechanics.md#task-2-add-the-multi-stage-chain-recipe-set)) (depends on 1)
- [x] Task 3: Own the `supply_chains` flag and thread engine activation ([details](phase-01-world-chain-mechanics.md#task-3-own-the-supply_chains-flag-and-thread-engine-activation)) (depends on 1, 2)
- [x] Task 4: Add tool-assisted harvesting and local stage-readiness planning ([details](phase-01-world-chain-mechanics.md#task-4-add-tool-assisted-harvesting-and-local-stage-readiness-planning)) (depends on 1, 3)

### Phase 2: Analysis Contract and Evidence
- [x] Task 5: Lock `supply-chains.v1` analysis contract and caps ([details](phase-02-analysis-contract-and-evidence.md#task-5-lock-supply-chainsv1-analysis-contract-and-caps))
- [x] Task 6: Extract bounded production evidence and detached dependency inputs ([details](phase-02-analysis-contract-and-evidence.md#task-6-extract-bounded-production-evidence-and-detached-dependency-inputs)) (depends on 5)
- [x] Task 7: Build the observed dependency graph and chain paths ([details](phase-02-analysis-contract-and-evidence.md#task-7-build-the-observed-dependency-graph-and-chain-paths)) (depends on 6)

### Phase 3: Bottlenecks, Identity, Metrics, and Pins
- [x] Task 8: Detect bounded supply bottlenecks ([details](phase-03-bottlenecks-identity-metrics.md#task-8-detect-bounded-supply-bottlenecks)) (depends on 7)
- [x] Task 9: Mint deterministic supply identities and forward-only lineage ([details](phase-03-bottlenecks-identity-metrics.md#task-9-mint-deterministic-supply-identities-and-forward-only-lineage)) (depends on 7)
- [x] Task 10: Compose the bounded `SupplyChainAnalysis` harvest ([details](phase-03-bottlenecks-identity-metrics.md#task-10-compose-the-bounded-supplychainanalysis-harvest)) (depends on 7, 8, 9)
- [x] Task 11: Add six supply-chain metric families to 204 ([details](phase-03-bottlenecks-identity-metrics.md#task-11-add-six-supply-chain-metric-families-to-204)) (depends on 10)
- [x] Task 12: Sweep suite-wide ownership and metric-catalog pins ([details](phase-03-bottlenecks-identity-metrics.md#task-12-sweep-suite-wide-ownership-and-metric-catalog-pins)) (depends on 11)

### Phase 4: Collection and Publication
- [x] Task 13: Wire completed-run analysis and experiment collectors ([details](phase-04-collection-and-publication.md#task-13-wire-completed-run-analysis-and-experiment-collectors)) (depends on 10, 11)
- [x] Task 14: Add `supply-chains-snapshot-v1` models codec ports and paging ([details](phase-04-collection-and-publication.md#task-14-add-supply-chains-snapshot-v1-models-codec-ports-and-paging)) (depends on 10, 11)
- [x] Task 15: Add atomic filesystem store and dual-gated settings ([details](phase-04-collection-and-publication.md#task-15-add-atomic-filesystem-store-and-dual-gated-settings)) (depends on 14)
- [x] Task 16: Compose and publish completed-run supply-chain snapshots ([details](phase-04-collection-and-publication.md#task-16-compose-and-publish-completed-run-supply-chain-snapshots)) (depends on 13, 14, 15)

### Phase 5: Read-Only Surfaces
- [x] Task 17: Add seven GET-only dual-gated supply-chain API routes ([details](phase-05-read-only-surfaces.md#task-17-add-seven-get-only-dual-gated-supply-chain-api-routes)) (depends on 14, 15, 16)
- [x] Task 18: Add Research UI supply-chain client and panel ([details](phase-05-read-only-surfaces.md#task-18-add-research-ui-supply-chain-client-and-panel)) (depends on 17)

### Phase 6: Experiment and End-to-End
- [x] Task 19: Register off-gate `supply_chains@1` experiment ([details](phase-06-experiment-and-e2e.md#task-19-register-off-gate-supply_chains1-experiment)) (depends on 3, 4, 11, 13)
- [x] Task 20: Add in-process supply-chain end-to-end coverage ([details](phase-06-experiment-and-e2e.md#task-20-add-in-process-supply-chain-end-to-end-coverage)) (depends on 16, 17, 19)
- [x] Task 21: Add determinism property bounds and leakage coverage ([details](phase-06-experiment-and-e2e.md#task-21-add-determinism-property-bounds-and-leakage-coverage)) (depends on 20)

### Phase 7: Invariants and Pins
- [x] Task 22: Enforce architecture invariants and pin sweeps ([details](phase-07-invariants-and-pins.md#task-22-enforce-architecture-invariants-and-pin-sweeps)) (depends on 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21)

### Phase 8: Documentation and Verification
- [x] Task 23: Documentation via `$aif-docs` ([details](phase-08-docs-and-verification.md#task-23-documentation-via-aif-docs)) (depends on 22)
- [x] Task 24: Add documentation pin and negative parity checks ([details](phase-08-docs-and-verification.md#task-24-add-documentation-pin-and-negative-parity-checks)) (depends on 23)
- [x] Task 25: Required-gate verification certification ([details](phase-08-docs-and-verification.md#task-25-required-gate-verification-certification)) (depends on 20, 21, 22, 24)

## Commit Plan

- **Commit 1** (after tasks 1-4): `feat(world): own supply_chains and add multi-stage production chains`
- **Commit 2** (after tasks 5-7): `feat(analysis): add supply-chain evidence and dependency graph`
- **Commit 3** (after tasks 8-12): `feat(analysis): add supply bottlenecks, lineage, metrics, and pin sweep`
- **Commit 4** (after tasks 13-18): `feat(simulation): publish supply-chain snapshots and read surfaces`
- **Commit 5** (after tasks 19-25): `test,docs: certify supply-chain experiment and required gates`

Commit checkpoints are suggestions only. Do not commit during `$aif-implement`
unless the user explicitly authorizes commits.

## Definition of Done

- V4-19 owns `supply_chains`; 14 contexts / 12 flags / 7 owned / 5 unowned; no
  `runner-config-v57`, root field, or per-agent key.
- The legacy six-recipe `example_production_catalog()`, its order, and its digest
  are unchanged.
- The closed chain catalog validates acyclic, produces the six locked item
  edges, and reaches depth ≥ 3; resource and kind inputs never become item
  edges.
- Tool-assisted harvesting adds +0.10 harvest success probability (clamped to
  1.0) only when active, without consuming the tool, and the legacy/off path is
  unchanged.
- Local planning is a one-step deterministic stage order with no lookahead,
  optimizer, price, quota, allocation, score, ranking, or recommendation.
- Organizations remain compositions of member commands plus owner procedure
  claims; no organization actor or executor exists; analysis attributes stages
  only by claimed performer actor.
- Analysis reconstructs stages from committed events only, pairs multi-tick
  craft starts with completions, and marks one-tick crafts with
  `unresolved_craft_inputs`.
- Ten edge kinds represent resources, items, structures, storage, transport,
  locations, infrastructure, organizations, tools, and skills; missing optional
  inputs yield `missing` coverage and no fabricated edges.
- Chains are depth-bounded observed paths with content-addressed ids; lineage is
  forward-only across every window including empty gaps.
- Bottlenecks use the seven locked kinds and thresholds with counts and integer
  ratios only.
- Six metric families append to exactly 204; prior ids/order/versions/value keys
  are unchanged; every suite pin is swept from 198 to 204 and no test expects
  `supply_chains` to be unowned.
- `supply-chains-snapshot-v1` round-trips canonically with no wall-clock field;
  `supply-chains-store-v1` is atomic, quota-bounded, idempotent, and
  corruption-safe; cursors bind the `window_index` filter.
- Seven GET-only dual-gated routes fail closed with `supply_chains_disabled`,
  default limit 100, `window_index` ≤ 511; the Research UI panel is read-only;
  no new Godot overlay exists.
- Off-gate `supply_chains@1` is registered and absent from the V1 gate.
- Commands stay 43; observer semantics stay 73; replay-v27/codec `v25` stay the
  maximum; Alembic stays `0017`; `/v1` and `observer-protocol-v1` stay.
- The in-process E2E uses real `WorldEngine` admission, real commands, real
  events, a real snapshot, and a real API read.
- Determinism across hash seeds, cap-bound properties, and leakage guards pass.
- Docs cover the page, README, ARCHITECTURE, DESCRIPTION,
  `docs/architecture.md`, `docs/configuration.md`, and the infrastructure
  ownership note, with positive and negative parity checks; required gates are
  certified or explicitly `unexecuted`; the roadmap is untouched and its
  follow-up registration is stated.

## Verification Receipt

Recorded 2026-11-10 after the verification remediation. Every lane is green with
its exact command or explicitly `unexecuted` with the missing prerequisite.

| Lane | Command | Result | Prerequisite / note |
| --- | --- | --- | --- |
| Python unit + architecture (coverage) | `uv run pytest tests/unit tests/architecture -q --cov=src --cov-report=term` | **10,440 passed**, 79% coverage (38:32) | Complete; two collector/E2E test additions were made afterward and are covered by the focused lane |
| Focused supply chain | `uv run pytest tests/unit/test_supply_chain_*.py tests/architecture/test_supply_chain_*.py -q` | **263 passed** | Complete |
| Docs parity | `uv run pytest tests/unit/test_supply_chain_docs.py tests/unit/test_trade_networks_docs.py tests/unit/test_infrastructure_docs.py tests/unit/test_travel_network_docs.py -q` | **26 passed** | Complete |
| Static — Ruff | `uv run ruff check src tests` | **All checks passed** | Complete |
| Static — mypy | `uv run mypy src tests` | **Success: no issues found in 2,413 files** | Complete |
| Static — import-linter | `uv run lint-imports` | **25 contracts kept, 0 broken** | Complete |
| Integration (non-scale) | `uv run pytest tests/integration -m "not scale" -q` | **52 passed**, 60 skipped, 5 deselected | PostgreSQL-backed cases skipped (no disposable database) |
| Supply-chain store → API integration | `uv run pytest tests/integration/test_supply_chain_store_api.py -q -m integration` | **4 passed** | Complete (DB-free) |
| Compose configuration | `docker compose config` | **exit 0** | Complete |
| Research UI unit tests | `cd clients/research-ui && npx vitest run` | **296 passed** (61 files) | Complete |
| Research UI type check | `cd clients/research-ui && npx svelte-check --tsconfig ./tsconfig.app.json` | **0 errors, 0 warnings** | Complete |
| Godot regression | pinned editor + `tests/run_protocol.gd` (existing suites) | **unexecuted** | Godot editor/export templates are not installed in this environment |
| Compose/browser acceptance | browser harness | **unexecuted** | Requires an attested image and a headed browser harness; Compose config itself is green |
| Benchmark / scale regression | `tests/benchmarks` scale lanes | **unexecuted** | Requires scale hardware and a disposable PostgreSQL instance |

Roadmap state: `.ai-factory/ROADMAP.md` is untouched. `$aif-roadmap` must register
V4-17, V4-18, and V4-19 in M8 and record the owned V4 flag count as seven.

Remediation record: `uv run mypy src tests` was initially failing with 97 errors
in 15 new supply-chain test files; the missing bounds, leakage, settings, and
store-to-API integration suites were added; route and end-to-end API coverage
was expanded; chain-cap enforcement and truncation-notice propagation were fixed.
See `.ai-factory/patches/2026-11-10-21.57.md`.
