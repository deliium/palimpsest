<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-16 Infrastructure Networks

Mode: ultra
Branch: main
Created: 2026-11-09
Plan identifier: `v4-16-infrastructure`
Refined: 2026-11-09 (`$aif-improve` — dual owned-flag frozensets, locked
catalog constants, explicit PUBLIC_GOOD_KINDS, command serialize/op/target
pipeline, cognition proposers, ROAD structure for Repair, drop
`under_construction`, observer semantic reuse map, codec v21 structure gates +
runner snapshot branches, MetricComputationInputs emit gate, off-gate
experiment)

## Original Request

v4-16 infrastructure

Naming requirement:

Use `v4-16-infrastructure`.

Extend collective projects into persistent infrastructure.

Examples:

- roads
    
- bridges
    
- storage
    
- wells
    
- irrigation
    
- communication markers
    
- trade posts
    
- large shelters
    

Infrastructure may objectively modify WorldEngine rules such as:

travel time  
capacity  
resource production  
storage  
risk

Infrastructure must require:

resources  
labor/actions  
maintenance

Support:

construction  
damage  
repair  
decay  
destruction

Keep simulation location-based.

## Settings

- Testing: yes; full strategy. Unit, architecture, determinism, integration,
  Compose/browser, Godot regression, Research UI, benchmark regression, and
  static gates, with coverage enabled for Python lanes.
- Logging: verbose, metadata-only. Bounded DEBUG flow/counts, INFO milestones,
  WARN unresolved adjacency/truncation/partial coverage, ERROR safe codes.
  `PALIMPSEST_LOG_LEVEL` controls operational verbosity. Never log person sets,
  `infra-`/`msoc-`/`org-` payload bodies beyond safe counts, observation bodies,
  prompts, credentials, tokens, DSNs, memories, embeddings, utterance bodies, or
  payload surrogates.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 26.
- Language: English UI and artifacts; technical terms preserved.
- Git: enabled; base `main`; no branch or worktree creation; skip-push
  preference retained. Commit checkpoints are suggestions, not authorization to
  commit during planning or implementation unless the user explicitly asks.
- Workflow: slug IDs; normal verification with explicit complete required-gate
  certification.
- Naming: canonical stem `v4-16-infrastructure`; the ultra bundle directory is
  `.ai-factory/plans/v4-16-infrastructure/`, phase files use `phase-NN-<slug>.md`,
  and `index.md` is the canonical entrypoint.
- Research source: `.ai-factory/RESEARCH.md` and `.ai-factory/research/` do not
  exist; no external research conclusions are invented.
- Execution: plan only in this invocation. No implementation, commit, roadmap
  edit, or branch creation occurs while planning.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"
Rationale: V4-16 owns the reserved objective-world context
`infrastructure_networks` as the first reserved write-pair activation (event 23 /
codec `v21`), extending collective projects into persistent location-based
infrastructure that objectively modifies travel, capacity, production, storage,
and risk, with construction/damage/repair/decay/destruction requiring
resources, labor, and maintenance. This plan does not edit or close the
roadmap; `$aif-roadmap` must register V4-16 in M8 and record the ownership.

## Requirements Reconciliation

Authority: the Original Request defines scope; `.ai-factory/ARCHITECTURE.md`
("Key Principles", "Capability ownership", "Versioned Extension Contract",
V4-01 through V4-15 seams) and `.ai-factory/RULES.md` constrain every edit;
`.ai-factory/DESCRIPTION.md` and `.ai-factory/ROADMAP.md` describe current
state; `docs/v4-architecture.md` ("infrastructure_networks", "Downstream V4
plan checklist") and `src/simulation/v4_architecture.py` /
`src/simulation/versioning.py` declare the reserved write pair;
`tests/architecture/test_v4_architecture_invariants.py` and related boundary
suites govern compatibility. Collective-project / public-good /
production / regions seams supply the construction and effect baselines.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| V4-16 owns `infrastructure_networks` on accepted `runner-config-v56`; updates **both** `runner_models._V4_OWNED_CAPABILITY_FLAGS` and `compatibility.V4_OWNED_CAPABILITY_FLAGS` (must stay equal); adds no `runner-config-v57`; does not own `supply_chains` | Original Request; `.ai-factory/ROADMAP.md` M8 next; `v4_architecture.py` 185-197; `runner_models.py` 325-333; `compatibility.py` 156-163; `tests/unit/test_runner_config_v4_flags.py` | Task 1/23/27 |
| Claims reserved write pair event **23** / codec **`v21`**; remaining reservations 24–26 / `v22`–`v24` stay reserved; epidemic codec string `v22` stays unaccepted | `versioning.py` 39-49; `persistence.py` `ACCEPTED_PERSISTENCE_CODEC_VERSIONS` | Task 14/15/23 |
| Authority is `OBJECTIVE_WORLD`; owners `world` + `simulation`; no abstract grid planner; no automatic maintenance policy | `v4_architecture.py` non-goals; Original Request | Task 1/9/23 |
| Eight closed kinds with **locked** catalog constants (see Architecture); statuses are `operational` / `damaged` / `destroyed` only (no `under_construction` asset row) | Original Request; refine pass | Task 2/3/7/23 |
| `PUBLIC_GOOD_KINDS` / `DRAW_PUBLIC_KINDS` / `PRESENCE_PUBLIC_KINDS` become **explicit** frozensets preserving pre-V4-16 membership; infra-only kinds (`road`, `irrigation`, `trade_post`, `large_shelter`) are excluded | `collective_projects.py` 209-227 | Task 2/5/23 |
| Location-based nodes/edges only; no grid/coords/polygons | Original Request; `Location.adjacent` | Task 3/10/23 |
| Construction reuses `StartCollectiveProject` / `ContributeCollectiveProject`; full pipeline includes action field, `_StartCollectiveProjectOp`, serialization encode/decode, `CollectiveProject.target_location_id`, mutate/start events; command **count stays 43** | `actions.py` 777-798; `serialization.py` 2593-2925; `_operations.py` 493-1071 | Task 5/23 |
| Cognition proposers gain focus codes for new kinds + road adjacent target selection | `agents/cognition/collective_projects.py` `_START_KIND` 28-34 | Task 6/24 |
| Completion registers `infra-` assets; `road` also creates anchor `StructureKind.ROAD` for `Repair`; no infra actor/crew/owner | CollectiveProject non-goals | Task 7/8/23 |
| `well` / `communication_marker` (`warning_post`) still require `public_goods` to **start**; other infra kinds need only flag + `collective_projects` | `_collective_projects.py` 106-109 | Task 5/27 combinations |
| Maintain/Oppose when public goods active; `Repair` on linked structure (including ROAD) when production-linked; tick decay never auto-repairs | public-good decay; `Structure.integrity` | Task 8/9/23 |
| Objective modifiers only while `operational` and integrity ≥ catalog min | Original Request; `_travel_duration` | Task 10-13/23 |
| Alembic `0017` unchanged; no `v4-m02` SQL claim | `migration_plan.py` 48-57 | Task 15/23/27 |
| Observer semantics stay **73**; new event kinds alias existing `SEMANTIC_TYPE_BY_KIND` entries (no new semantic strings) | `observer/version.py` 11-85, 87-161 | Task 14/23 |
| Four metric families 184 → **188** via optional `MetricComputationInputs.infrastructure_networks_analysis` | `metric_service.py` `MetricComputationInputs` | Task 18/23/26 |
| Off-gate experiment `infrastructure_networks@1` registered; not on V1 gate | `experiments/catalog.py` AW/AX precedent | Task 25/27 |
| Research surfaces dual-gated and read-only | V4-13/14 precedent | Task 19-22/23 |
| Roadmap owned by `$aif-roadmap` | ARCHITECTURE requirement 7 | Task 27 `git status` |

### Supported combinations and availability transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| Default runner, all V4 flags off | No infrastructure channel | Checkpoint ≤ replay-v22/v20; no `infra-` assets | Task 1/15/24 |
| v56 + `infrastructure_networks` without `collective_projects` | Rejected | Fail closed `infrastructure_requires_collective_projects` | Task 1/5 |
| v56 + flag + `collective_projects` | Channel active | Write pair (23, v21); infra-only kinds startable | Task 1/15/24 |
| Same without `public_goods` | Channel active | `well`/`warning_post` starts still rejected; road/irrigation/trade_post/large_shelter/bridge/storage OK; Repair maintains linked structures | Task 5/8/24 |
| Same + `public_goods` | Channel active | Maintain/Oppose sync infra integrity for public-good kinds | Task 8/24 |
| Start `road` with adjacent `target_location_id` | Open edge project | Edge asset + anchor `ROAD` structure on complete | Task 5/7/10 |
| Start `road` missing/non-adjacent target | No project | Reject | Task 5 |
| Cognition focus `collective_project:start:road` with visible adjacent exit | Proposed start | Includes `target_location_id` | Task 6/24 |
| Tick decay / repair / destroy | Status transitions | Modifiers cease when not operational | Task 9-13 |
| Dual-gate unset | No reader | 503 `infrastructure_networks_disabled` | Task 20/21 |
| Another unowned V4 flag | Unchanged | `capability_unimplemented` | Task 1/23 |
| Env-gated lane missing prerequisite | No green certification | `unexecuted` + prerequisite | Task 27 |

No blocking open questions: every material decision is fixed below.

## Architecture and Decisions

1. **Own `infrastructure_networks`.** Update **both** owned-flag frozensets so they remain equal. Enable only on accepted `runner-config-v56`. No `runner-config-v57`.
2. **Claim write pair (23, `v21`).** Highest priority in `checkpoint_schema_for_production` when the channel is active.
3. **Do not own `supply_chains`.** Activate the reserved pair for infrastructure only.
4. **Locked policy `infrastructure-networks.v1`** with the exact catalog table below.
5. **Extend collective projects** end-to-end (action → op → serialize → mutate → events → cognition). Command count remains **43**.
6. **Explicit public-good frozensets** so new CollectiveProjectKind values do not auto-join Use/Maintain/Oppose/presence sets.
7. **Objective graph** in `world.infrastructure` / `_infrastructure.py`; assets exist only after completion (`operational` initial status).
8. **`StructureKind.ROAD`**, `IRRIGATION`, `TRADE_POST` added; road completion places an anchor ROAD structure for Repair.
9. **Effects derived** from operational assets in rules (travel, capacity, regen, storage, risk).
10. **Lifecycle:** operational → damaged → destroyed; decay ticks; repair/maintain restore; destroyed terminal for modifiers.
11. **No automatic maintenance**, grid planner, infra actor, nation, or civilization score.
12. **Alembic stays `0017`.**
13. **Observer:** alias new event detail kinds onto existing semantic types (pin 73).
14. **Research surfaces** dual-gate FS store + six GET routes + Research UI + Godot overlays.
15. **Metrics 184 → 188**; optional analysis input on `MetricComputationInputs`.
16. **Off-gate experiment** `infrastructure_networks@1`.
17. **Roadmap not edited here.**

### Locked `INFRASTRUCTURE_CATALOG` constants

| Kind | Topology | Collective kind | StructureKind | Labor | Material | Decay/tick | Op min | Key effects |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `road` | edge | `road` | `ROAD` (anchor) | 5 | stone×3 | 0.01 | 0.35 | duration −1; fatigue −1.0 |
| `bridge` | node | `bridge` | `BRIDGE` | 4 | stone×2 | 0.01 | 0.35 | fatigue −2.0 from location |
| `storage` | node | `storage` | `STORE` | 2 | wood×1 | 0.01 | 0.35 | store_capacity +3 |
| `well` | node | `well` | `WELL` | 3 | stone×2 | 0.01 | 0.35 | public-good draw unchanged |
| `irrigation` | node | `irrigation` | `IRRIGATION` | 4 | stone×2 | 0.015 | 0.40 | regen +0.05 |
| `communication_marker` | node | `warning_post` | `WARNING_POST` | 2 | wood×1 | 0.01 | 0.35 | exposure_relief 0.5 |
| `trade_post` | node | `trade_post` | `TRADE_POST` | 4 | wood×2 | 0.01 | 0.35 | item_cap +2; store_cap +2 |
| `large_shelter` | node | `large_shelter` | `SHELTER` | 5 | wood×3 | 0.01 | 0.35 | body_cap +2; exposure_relief 0.25 |

Caps: `MAX_INFRASTRUCTURE_ASSETS = 64`; `MAX_INFRA_BODY_BONUS = 8`; `MAX_INFRA_ITEM_BONUS = 8`; `REPAIR_INTEGRITY_DELTA = 0.15`.

### Observer semantic reuse map (Task 14)

| Event detail kind | `SEMANTIC_TYPE_BY_KIND` target |
| --- | --- |
| `infrastructure_constructed` | `STRUCTURE_BUILT` |
| `infrastructure_repaired` | `STRUCTURE_REPAIRED` |
| `infrastructure_damaged` | `PUBLIC_GOOD_OPPOSED` |
| `infrastructure_decayed` | `ARTIFACT_DAMAGED` |
| `infrastructure_destroyed` | `ARTIFACT_DESTROYED` |

No new entries in `SEMANTIC_EVENT_TYPES`.

## Phase Index

1. [Phase 1: Ownership and contract](phase-01-ownership-and-contract.md) — Tasks 1-2
2. [Phase 2: World network models](phase-02-world-network-models.md) — Tasks 3-4
3. [Phase 3: Construction bridge](phase-03-construction-bridge.md) — Tasks 5-7
4. [Phase 4: Lifecycle](phase-04-lifecycle.md) — Tasks 8-9
5. [Phase 5: Objective rule effects](phase-05-objective-rule-effects.md) — Tasks 10-13
6. [Phase 6: Write pair, replay, observation](phase-06-write-pair-replay.md) — Tasks 14-17
7. [Phase 7: Metrics and read-only surfaces](phase-07-metrics-and-surfaces.md) — Tasks 18-22
8. [Phase 8: Invariants, E2E, experiment](phase-08-invariants-and-e2e.md) — Tasks 23-25
9. [Phase 9: Docs and verification](phase-09-docs-and-verification.md) — Tasks 26-27

## Cross-Phase Dependencies

- Tasks 3-4 depend on 1-2.
- Tasks 5-7 depend on 3-4 (6 also on 5).
- Tasks 8-9 depend on 7.
- Tasks 10-13 depend on 3-4 and 8-9.
- Tasks 14-17 depend on 5-13 (17 also on 6).
- Tasks 18-22 depend on 14-17.
- Tasks 23-25 depend on 1-22 (24 on 23; 25 on 23).
- Tasks 26-27 depend on 23-25.

## Tasks

### Phase 1: Ownership and contract
- [x] Task 1: Own `infrastructure_networks` on both flag frozensets ([details](phase-01-ownership-and-contract.md#task-1-own-infrastructure_networks-on-both-flag-frozensets))
- [x] Task 2: Locked kinds catalog and explicit public-good sets ([details](phase-01-ownership-and-contract.md#task-2-locked-kinds-catalog-and-explicit-public-good-sets))

### Phase 2: World network models
- [x] Task 3: `InfrastructureAsset` / network WorldState types ([details](phase-02-world-network-models.md#task-3-infrastructureasset--network-worldstate-types))
- [x] Task 4: Content-addressed `infra-` identity helpers ([details](phase-02-world-network-models.md#task-4-content-addressed-infra--identity-helpers))

### Phase 3: Construction bridge
- [x] Task 5: Extend kinds and full start pipeline ([details](phase-03-construction-bridge.md#task-5-extend-kinds-and-full-start-pipeline)) (depends on 1, 2, 3)
- [x] Task 6: Cognition proposers for new kinds and roads ([details](phase-03-construction-bridge.md#task-6-cognition-proposers-for-new-kinds-and-roads)) (depends on 5)
- [x] Task 7: Completion registers assets and ROAD anchors ([details](phase-03-construction-bridge.md#task-7-completion-registers-assets-and-road-anchors)) (depends on 4, 5)

### Phase 4: Lifecycle
- [x] Task 8: Damage and repair command wiring ([details](phase-04-lifecycle.md#task-8-damage-and-repair-command-wiring)) (depends on 7)
- [x] Task 9: Tick decay and destruction ([details](phase-04-lifecycle.md#task-9-tick-decay-and-destruction)) (depends on 7, 8)

### Phase 5: Objective rule effects
- [x] Task 10: Travel time and fatigue modifiers ([details](phase-05-objective-rule-effects.md#task-10-travel-time-and-fatigue-modifiers)) (depends on 3, 9)
- [x] Task 11: Location capacity modifiers ([details](phase-05-objective-rule-effects.md#task-11-location-capacity-modifiers)) (depends on 3, 9)
- [x] Task 12: Resource production and storage modifiers ([details](phase-05-objective-rule-effects.md#task-12-resource-production-and-storage-modifiers)) (depends on 3, 9)
- [x] Task 13: Risk and exposure modifiers ([details](phase-05-objective-rule-effects.md#task-13-risk-and-exposure-modifiers)) (depends on 3, 9)

### Phase 6: Write pair, replay, observation
- [x] Task 14: Event schema replay-v23 and semantic aliases ([details](phase-06-write-pair-replay.md#task-14-event-schema-replay-v23-and-semantic-aliases)) (depends on 7, 8, 9)
- [x] Task 15: Codec v21, gates, and checkpoint selection ([details](phase-06-write-pair-replay.md#task-15-codec-v21-gates-and-checkpoint-selection)) (depends on 14)
- [x] Task 16: Replay projection for infrastructure events ([details](phase-06-write-pair-replay.md#task-16-replay-projection-for-infrastructure-events)) (depends on 14, 15)
- [x] Task 17: Observation projection for colocated assets ([details](phase-06-write-pair-replay.md#task-17-observation-projection-for-colocated-assets)) (depends on 3, 6, 9)

### Phase 7: Metrics and read-only surfaces
- [x] Task 18: Four metric families (184→188) ([details](phase-07-metrics-and-surfaces.md#task-18-four-metric-families-184188)) (depends on 14)
- [x] Task 19: Snapshot, ports, paging, filesystem store ([details](phase-07-metrics-and-surfaces.md#task-19-snapshot-ports-paging-filesystem-store)) (depends on 18)
- [x] Task 20: Settings dual-gate, CLI, publication ([details](phase-07-metrics-and-surfaces.md#task-20-settings-dual-gate-cli-publication)) (depends on 19)
- [x] Task 21: API routes and Research UI panel ([details](phase-07-metrics-and-surfaces.md#task-21-api-routes-and-research-ui-panel)) (depends on 20)
- [x] Task 22: Godot infrastructure overlays ([details](phase-07-metrics-and-surfaces.md#task-22-godot-infrastructure-overlays)) (depends on 19)

### Phase 8: Invariants, E2E, experiment
- [x] Task 23: Architecture invariants and pin sweeps ([details](phase-08-invariants-and-e2e.md#task-23-architecture-invariants-and-pin-sweeps)) (depends on 1-22)
- [x] Task 24: In-process infrastructure E2E ([details](phase-08-invariants-and-e2e.md#task-24-in-process-infrastructure-e2e)) (depends on 23)
- [x] Task 25: Off-gate experiment `infrastructure_networks@1` ([details](phase-08-invariants-and-e2e.md#task-25-off-gate-experiment-infrastructure_networks1)) (depends on 23)

### Phase 9: Docs and verification
- [x] Task 26: Documentation via `$aif-docs` ([details](phase-09-docs-and-verification.md#task-26-documentation-via-aif-docs)) (depends on 23)
- [x] Task 27: Required-gate verification certification ([details](phase-09-docs-and-verification.md#task-27-required-gate-verification-certification)) (depends on 24, 25, 26)

## Commit Plan

- **Commit 1** (after tasks 1-4): `feat(world): add infrastructure networks contract and WorldState graph`
- **Commit 2** (after tasks 5-9): `feat(world): construct, propose, damage, repair, decay, and destroy infrastructure`
- **Commit 3** (after tasks 10-13): `feat(world): apply infrastructure travel, capacity, production, and risk effects`
- **Commit 4** (after tasks 14-17): `feat(simulation): activate replay-v23/codec v21 for infrastructure`
- **Commit 5** (after tasks 18-22): `feat(research): publish infrastructure metrics, API, UI, and overlays`
- **Commit 6** (after tasks 23-27): `test,docs: certify infrastructure networks ownership and pins`

Commit checkpoints are suggestions only. Do not commit during `$aif-implement`
unless the user explicitly authorizes commits.

## Definition of Done

- `infrastructure_networks` owned on both frozensets; unowned flags still fail closed.
- Persistent location-based assets for all eight kinds with locked catalog;
  construction through collective projects + cognition proposers; lifecycle
  damage/repair/decay/destruction; ROAD anchors for Repair.
- Objective modifiers for travel, capacity, production, storage, and risk;
  no automatic maintenance; no grid planner; no civilization infrastructure score.
- Write pair (23, `v21`) with structure-kind gates and replay round-trips;
  Alembic `0017`; commands 43; semantics 73; metrics 188; six owned V4 flags.
- Off-gate experiment registered; research surfaces dual-gated; docs landed;
  required gates certified or explicitly `unexecuted`; roadmap untouched.
