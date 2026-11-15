<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: Social Mobility

Mode: ultra
Branch: main
Created: 2026-11-14

## Original Request

v4-25 social mobility

Naming requirement:

Use `v4-25-social-mobility`.

Use V3 genealogy and V4 economic/institutional data to measure persistence across generations.

Compare ancestor conditions with descendant outcomes:

- resources
- skills
- social influence
- organization roles
- educational access
- productive assets

Do not encode social classes.

Detect mobility and persistence analytically.

Support many-generation studies.

## Settings

- Testing: yes; full strategy. Unit, architecture, determinism, properties,
  integration, Compose config/browser, Godot regression (existing suite only),
  Research UI, benchmark regression, and static gates, with coverage enabled
  for Python lanes.
- Logging: verbose, metadata-only. Bounded DEBUG window/owner/domain counts,
  detection milestones, and selected status tokens; INFO analysis composition
  and publication milestones; WARN truncation, partial coverage, unresolved
  pairs, malformed rows, and oversize payloads; ERROR safe codes.
  `PALIMPSEST_LOG_LEVEL` controls verbosity. Never log owner tokens, pair
  tokens, generation labels tied to named agents, quantities, distributions,
  cursor keys, digests, credentials, DSNs, memories, embeddings, or payload
  surrogates.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 19.
- Language: English UI and artifacts; technical terms preserved.
- Git: enabled; base `main`; no branch or worktree creation; skip-push
  preference retained. Commit checkpoints are suggestions, not authorization to
  commit during planning or implementation unless the user explicitly asks.
- Workflow: slug IDs; normal verification with explicit complete required-gate
  certification.
- Naming: canonical stem `v4-25-social-mobility`; this plan is the ultra bundle
  `.ai-factory/plans/v4-25-social-mobility/`. Python tokens use `social_mobility`
  / `social-mobility-*`; the feature name is "social mobility".
- Research source: `.ai-factory/RESEARCH.md` and `.ai-factory/research/` do not
  exist; no external research conclusions are invented.
- Execution: plan only in this invocation. No implementation, commit, roadmap
  edit, or branch creation occurs while planning.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"
Rationale: V4-25 adds a sixteenth, analysis-only V4 context that measures
intergenerational persistence over already-owned V3 genealogy and V4
economic/institutional seams; it claims no V4 capability flag, runner schema,
command, event, write pair, API version, or migration, and it does not close M8
or edit other milestones.

## Requirements Reconciliation

Authority: the Original Request defines scope. `.ai-factory/ARCHITECTURE.md`
("Key Principles", "Versioned Extension Contract", V3-05, V3-07, V3-08, V3-11,
V3-12, V3-13, V3-17, V3-18, V3-19, V4-02, V4-03, V4-04, V4-06, V4-09, V4-10,
V4-18 through V4-24 seams) and `.ai-factory/RULES.md` constrain every edit.
`.ai-factory/DESCRIPTION.md` describes the implemented state;
`.ai-factory/ROADMAP.md` is stale for V4-23, V4-24, and V4-25 and stays owned by
`$aif-roadmap`. Concrete contracts come from the source paths below. No
requirement source is edited to create this plan.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| V4-25 declares a sixteenth V4 context `social_mobility` with authority `detached_analysis`, owning package `analysis`, seam `analysis_capture`, and no capability flag; contexts 15 -> 16, flags stay 12, owned stay 8, unowned stay 4, map revision becomes `v4-context-map-v4` | Original Request "Use V3 genealogy and V4 economic/institutional data"; `src/simulation/v4_architecture.py:38-110,113-354,394-452` | Task 1/18/21 |
| The new context must be added to `V4_ANALYSIS_ONLY_CONTEXTS` and to `V4_EVENT_REUSING_CONTEXTS`; it may not own a reserved or deepening write pair and needs no migration stage | `src/simulation/versioning.py:102-176`; `src/simulation/migration_plan.py` | Task 1/18 |
| No `runner-config-v57`, runner root field, per-agent key, capability flag, command, event, observer semantic type, write pair, `/v2` route, or SQL migration is added; `runner-config-v56` remains the accepted seam | `src/simulation/compatibility.py`; `src/simulation/runner_models.py`; `.ai-factory/ARCHITECTURE.md` V4-24 seam | Task 1/18/21 |
| Genealogy uses committed objective evidence only: `KinshipEdgeRecorded` parent→child edges and `AgentCreated.generation_index`; bootstrap owners are generation 0; no `WorldState`, `KinshipGraph`, runtime, or store object is read | `src/world/events.py:1707-1756,1946-1990`; `src/world/kinship.py:392-455` | Task 3/16/17 |
| Agent id and body id are different identity spaces: kinship edges, `PracticalKnowledgeAudit.owner_id`, `TeachingAudit.agent_id`, and `OrganizationAssignmentRow.occupant_id` carry stable `AgentId` strings, while objective events carry `EntityId`; every join translates through one identity map built from `runner_config.agents` founders plus committed `AgentCreated`/`AgentEnteredWorld`/`AgentInitializationRecorded` rows | `src/world/events.py:1707-1880,1946-1990,3957`; `src/simulation/runner_models.py:7471-7485,837-868`; `src/agents/cognition/practical_knowledge.py:419-501`; `src/analysis/organization_operations.py:274-299` | Task 2/3/4/9 |
| Six outcome domains are measured independently with one measure each: `resources`, `skills`, `social_influence`, `organization_roles`, `educational_access`, `productive_assets`; no class, caste, stratum, elite, underclass, merit, prestige, or composite mobility score exists | Original Request six domains + "Do not encode social classes"; `src/analysis/economic_inequality_events.py:166-476`; `src/agents/cognition/practical_knowledge.py:419-501`; `src/world/events.py:707-763,2068-2098`; `src/analysis/organization_operations.py:274-299` | Task 2/4/5/9/17 |
| Outcome layers are hard-separated: objective committed outcomes (resources, assets, influence, education), owner-scoped outcomes (skills, organization roles), and analytical mobility rows; no objective row may carry a claim, and no claim may be labeled possession | Original Request "Do not encode social classes"; `.ai-factory/ARCHITECTURE.md` Key Principle 1; `src/analysis/economic_inequality_contract.py:248-269` | Task 2/4/7/17 |
| Mobility is computed over ancestor quantities observed at or before a window boundary and descendant quantities observed at or before the same boundary; ancestor observation never uses a post-birth value | Original Request "Compare ancestor conditions with descendant outcomes"; `src/analysis/economic_inequality_detection.py:122-132` | Task 5/16 |
| Statistics are quantile rank bins (`rank_bins=5`), same-bin persistence share, upward/downward shares, mean absolute rank change, and quantized Spearman rank correlation in integer milli; fewer than 8 resolved pairs is `insufficient_samples` and no index is invented | Original Request "Detect mobility and persistence analytically"; `src/analysis/inequality_indices.py:137-247` | Task 5/6/17 |
| Persistence labels are closed to `persistent`, `mobile`, `insufficient_samples`, `unavailable`; no class label, rank order, best/worst generation, or social-status vocabulary is permitted anywhere in rows, metrics, snapshots, or docs | Original Request "Do not encode social classes"; `src/analysis/economic_inequality_contract.py:131-143` | Task 2/5/17/20 |
| Many-generation support uses depth-bounded ancestor chains (`max_lineage_depth=8`), generation indices capped at 32, and lag strata 1-4; each lag recomputes its own bins and shares and never aggregates into one score | Original Request "Support many-generation studies"; `src/world/kinship.py:392-455`; `src/analysis/knowledge_genealogy.py:319-331` | Task 3/6/17 |
| Activation requires committed events, at least one committed `KinshipEdgeRecorded`, and at least one outcome channel (economic/institutional config seam or detached practical-knowledge/teaching/organization-operation evidence); otherwise no analysis, metric input, or snapshot field is produced and off-path behavior is unchanged | Original Request; `src/experiments/collectors.py:474-537`; `.ai-factory/ARCHITECTURE.md` Key Principle 4 | Task 9/15/16 |
| Eight metric families append 228 -> **236**: six domain families, one generation-lag family, and one coverage family. The first 228 ids, order, versions, and value keys stay unchanged | `src/analysis/specifications.py:52-53,298-309,9090-9132,9628-9765,10272-10285`; `src/analysis/metric_service.py:293-443,2701-2753` | Task 8/18/20/21 |
| Snapshot is a sibling `social-mobility-snapshot-v1` with store `social-mobility-store-v1`, two dual-gated settings, window-bound cursors, and seven GET-only routes failing closed with `social_mobility_disabled`; it is not a runner/result/replay/SQL schema | `src/simulation/economic_inequality_models.py:26-339`; `src/simulation/economic_inequality_ports.py:18-85`; `src/persistence/economic_inequality_filesystem.py:37-250`; `src/infrastructure/settings.py:268-334,509-518,942-954` | Task 10/11/12/13/21 |
| Publication is programmatic and post-completion; no CLI producer and no runner flag is added | `src/experiments/economic_inequality_publication.py:73-243`; V4-20 through V4-24 have no CLI producer | Task 12/21 |
| No Godot overlay is added: mobility is detached analysis, not a presentation fact; the presentation client is unchanged and its existing suite is the regression gate | Original Request; `.ai-factory/ARCHITECTURE.md` V3-40 through V3-42 seam | Task 14/18/21 |
| Off-gate experiment `social_mobility@1` composes existing flags/specs in three arms and never enters the V1 A-E gate; the baseline arm has no kinship evidence and is provably inert | `src/experiments/catalog.py:244-246,2800-2839,5734-5752`; `src/experiments/economic_inequality_scenario.py:43-139` | Task 15/21 |
| Documentation covers `docs/social-mobility.md`, README, ARCHITECTURE, DESCRIPTION, `docs/architecture.md`, `docs/configuration.md`, `docs/analysis-metrics.md`, `docs/research-api.md`, `docs/v4-architecture.md`, `docs/research-ui.md`, and cross-links in `docs/generational-runner.md`, `docs/lineage-explorer.md`, `docs/organizations.md`, and `docs/economic-inequality.md`; roadmap registration stays with `$aif-roadmap` | `.ai-factory/ARCHITECTURE.md` requirement 7; `.ai-factory/ROADMAP.md`; `docs/economic-inequality.md` | Task 19/20/21 |

### Supported combinations and coverage transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| No kinship edge and no outcome channel | Untouched run | No analysis, no `social_mobility_*` metric input, no snapshot field | Task 9/15 |
| Kinship edge, no outcome evidence | Genealogy harvest | All domains `unavailable`; no zero-filled pair | Task 4/7 |
| Outcome evidence, no kinship edge | Outcome harvest dropped | No analysis; activation guard fails | Task 9/15 |
| Parent outcome exists, child outcome missing | Unresolved pair | Pair retained as unresolved; domain needs 8 resolved pairs | Task 5/16 |
| Child outcome exists, parent outcome missing | Unresolved pair | No ancestor inference from later values | Task 5 |
| Fewer than 8 resolved pairs in a window/domain | `insufficient_samples` | Counts retained; no bins, shares, or correlation invented | Task 5/7/17 |
| 8 or more resolved pairs | `available` | Bins, four statistics, persistence label, coverage | Task 5/17 |
| All ancestor and descendant values equal | `available` | All pairs bin 0; same-bin share 1000; correlation 0 | Task 5/17 |
| Generation 0 bootstrap owner | Generation 0 | Eligible as ancestor or descendant when paired evidence exists | Task 3/6 |
| Agent-id row maps to a body-token owner | Same token space | Detached audit and objective outcome join correctly | Task 2/4/9 |
| Agent id has no config or committed mapping | Unmapped | Row/edge dropped with `social_mobility_unmapped_owner`; coverage `partial` | Task 3/4 |
| Generation index above 32 | Excluded | Bounded notice; no clamped generation label | Task 3/6 |
| Overlapping or repeated generation lags | Rows retained | Per-lag recomputation; no pooled score | Task 6/17 |
| Cap exceeded for events, owners, pairs, domain, generation, or lag rows | Deterministic prefix | `coverage="partial"` plus one bounded notice per family | Task 2/3/5/6/7 |
| Snapshot dual gate unset | No reader | 503 `social_mobility_disabled` on all seven routes | Task 11/13 |
| Corrupt snapshot payload | No data | 500 `social_mobility_store_corrupt` | Task 11/13 |
| Paged route with `window_index` | Filter-bound cursor | Only matching rows; cursor for another window rejected 400 | Task 10/13 |
| Publication disabled by the caller | No artifact | Nothing written; scientific status unchanged | Task 12 |
| Env-gated lane missing prerequisite | No green certification | `unexecuted` plus prerequisite | Task 21 |

No blocking open questions: every material decision is fixed below.

## Architecture and Decisions

1. **Add one analysis-only context, claim no flag.** `social_mobility` is a
   detached analytical context. It owns no world state, no owner state, and no
   capability slot. Counts become 16 contexts / 12 flags / 8 owned / 4 unowned.
2. **Genealogy is objective, and identity is translated once.** Parent→child
   edges come from committed `KinshipEdgeRecorded`; generation indices come
   from committed `AgentCreated`; bootstrap owners are generation 0. No
   `KinshipGraph`, `WorldState`, runtime, or store is read. Agent-id-keyed
   evidence (kinship, practical knowledge, teaching, organization assignments)
   and body-id-keyed objective events are joined through one explicit
   `SocialMobilityIdentityMap` built from founder config plus committed
   identity events; unmapped owners are reported, never guessed.
3. **Outcomes are observed, not inferred.** Each domain has exactly one
   measure over observed evidence. Missing evidence is `unavailable`, never
   zero, and no domain is imputed from another domain.
4. **No social classes.** The contract rejects `class`, `caste`, `stratum`,
   `elite`, `underclass`, `wealth`, `prestige`, `merit`, `desert`, `rank`,
   `score`, `status_label`, `inheritance_right`, and `mobility_score` in rows,
   metrics, snapshots, and docs. Quantile bins are statistical positions, not
   named strata.
5. **Mobility is analytical.** Ancestor values are observed at or before a
   window boundary, descendant values at or before the same boundary. The
   analysis reports same-bin persistence, upward/downward shares, mean absolute
   rank change, and quantized Spearman rank correlation.
6. **One measure per domain.** `resources` = observed resource items;
   `skills` = active practical-knowledge entries; `social_influence` = distinct
   observed inbound communication partners; `organization_roles` = distinct
   believed role assignments; `educational_access` = teaching plus repository
   receipts; `productive_assets` = observed tools plus operational
   infrastructure plus accessible storage, documented as an additive physical
   count rather than wealth.
7. **Layers stay separate.** Objective committed outcomes, owner-scoped
   outcomes, and analytical mobility rows are three types with a hard leakage
   guard. A claim row can never be read as possession or merit.
8. **Many generations.** Depth-bounded ancestor chains, generation indices
   capped at 32, and lag strata 1-4. Each lag recomputes its own statistics; no
   lag is ranked against another.
9. **Longitudinal windows.** `window_ticks=32`, `max_windows=512`. Domain and
   generation rows carry window index and tick; metric documents summarize the
   latest window and window count.
10. **Bounded everything.** Events, owners, pairs, domain rows, generation rows,
    lag rows, coverage rows, notices, and snapshot bytes have independent caps
    with deterministic prefixes and `coverage="partial"`.
11. **Activation is opt-in and evidence-driven.** Requires committed events, a
    kinship edge, and an outcome channel. No kinship means no analysis and no
    metric documents, so default V1/V2 bundles are unchanged.
12. **Read-only surfaces.** `social-mobility-snapshot-v1` is canonical,
    digest-addressed, and wall-clock-free. `social-mobility-store-v1` is atomic,
    quota-bounded, idempotent, and corruption-safe. Seven GET-only dual-gated
    routes serve it. Publication is programmatic after completion.
13. **No presentation physics.** No Godot overlay and no client write path; the
    Research UI panel is read-only.
14. **Catalog discipline.** Eight families append exactly at positions 228-235;
    every active pin and doc footer is swept from 228 to 236 in one change.

### Locked social-mobility summary

| Surface | Locked behavior |
| --- | --- |
| Policy | `social-mobility.v1` (analysis and snapshot share the token) |
| V4 ownership | New analysis-only `social_mobility`; 16 contexts / 12 flags / 8 owned / 4 unowned; map `v4-context-map-v4` |
| Runner schema | `runner-config-v56` only; no v57, no new root/per-agent key |
| Activation | Committed events **and** ≥1 `KinshipEdgeRecorded` **and** an outcome channel; otherwise disabled |
| Domains | `resources`, `skills`, `social_influence`, `organization_roles`, `educational_access`, `productive_assets` |
| Measures | `observed_resource_item_count`, `known_technique_count`, `inbound_communication_partner_count`, `held_organization_role_count`, `educational_access_receipt_count`, `observed_productive_asset_count` |
| Layers | objective outcome, owner outcome, analytical mobility; hard separation guard |
| Genealogy | `KinshipEdgeRecorded` edges; `AgentCreated.generation_index`; bootstrap = 0; depth cap 8 |
| Identity | One `SocialMobilityIdentityMap` (`AgentId` ↔ body token) from founder config plus committed identity events; unmapped ids reported, never guessed |
| Window | 32 ticks; index `tick // 32`; at most 512 windows |
| Statistics | 5 rank bins; same-bin/upward/downward shares; mean absolute rank change; quantized Spearman milli; minimum 8 resolved pairs |
| Persistence | `persistent` (same-bin ≥ 500 milli), `mobile`, `insufficient_samples`, `unavailable` |
| Generation lags | 1-4; per-lag recomputation; no pooled score |
| Caps | 200k events; 4,096 owners; 4,096 pairs; 4,096 domain rows; 1,024 generation rows; 2,048 lag rows; 1,024 coverage rows; 8 notices |
| Snapshot | `social-mobility-snapshot-v1`; store `social-mobility-store-v1`; 16 publications / 8 MiB; no wall-clock field |
| Routes | 7 GET-only under `SUBJECTIVE_DEBUG`; default limit 100; max 500; `window_index` ≤ 511; `social_mobility_disabled` when unset |
| Catalog | 228 -> 236 families; first 228 unchanged; active suite and docs pins swept to 236 |
| Clients | Research UI panel; no new Godot overlay |
| Experiment | `social_mobility@1`, off the V1 gate, three arms |
| Pins | 43 commands; 73 observer semantics; replay-v27/codec `v25`; Alembic `0017`; `/v1`; `observer-protocol-v1` |

## Phase Index

1. [Phase 1: Registry, Contract, and Genealogy Evidence](phase-01-registry-contract-genealogy.md) — Tasks 1-4
2. [Phase 2: Outcome Detection, Generation Lags, and Metrics](phase-02-outcomes-detection.md) — Tasks 5-8
3. [Phase 3: Completed-Run Inputs, Snapshot, Store, and Publication](phase-03-artifact-publication.md) — Tasks 9-12
4. [Phase 4: Read Surfaces](phase-04-read-surfaces.md) — Tasks 13-14
5. [Phase 5: Experiment and Certification Paths](phase-05-experiment-certification.md) — Tasks 15-17
6. [Phase 6: Invariants, Documentation, and Certification](phase-06-invariants-docs.md) — Tasks 18-21

## Cross-Phase Dependencies

- Task 2 depends on Task 1 for the context token used in contract policy names.
- Task 3 and Task 4 depend on Task 2 for tokens, policy, and row types.
- Task 5 depends on Tasks 3 and 4 for genealogy and outcome rows.
- Task 6 depends on Task 5 for pair rows and bin arithmetic.
- Task 7 depends on Tasks 5 and 6 for detected and generation rows.
- Task 8 depends on Task 7 for `SocialMobilityAnalysis`.
- Task 9 depends on Tasks 3, 7, and 8 for the genealogy signature, identity
  sources, analysis, and metric input.
- Task 10 depends on Task 8 for metric availability tokens.
- Task 11 depends on Task 10 for snapshot encode/decode.
- Task 12 depends on Tasks 7, 10, and 11 for analyze → compose → store.
- Task 13 depends on Tasks 10 and 11 for paging, cursors, and the reader.
- Task 14 depends on Task 13 for the route contract.
- Task 15 depends on Tasks 1, 9, and 12 for context, collector, and publication.
- Task 16 depends on Tasks 9, 12, 13, and 15 for the real path.
- Task 17 depends on Task 16 for deterministic fixtures.
- Task 18 depends on Tasks 1-17 for the final pin sweep.
- Task 19 depends on Task 18 for the docs count sweep.
- Task 20 depends on Task 19 for the section-count assertion.
- Task 21 depends on Tasks 16-20.

## Tasks

### Phase 1: Registry, Contract, and Genealogy Evidence
- [x] Task 1: Register the analysis-only `social_mobility` V4 context ([details](phase-01-registry-contract-genealogy.md#task-1-register-the-analysis-only-social_mobility-v4-context))
- [x] Task 2: Lock the `social-mobility.v1` contract, policy, caps, identity map, and DTOs ([details](phase-01-registry-contract-genealogy.md#task-2-lock-the-social-mobilityv1-contract-policy-caps-identity-map-and-dtos))
- [x] Task 3: Harvest committed genealogy and generation labels ([details](phase-01-registry-contract-genealogy.md#task-3-harvest-committed-genealogy-and-generation-labels))
- [x] Task 4: Harvest the six outcome domains ([details](phase-01-registry-contract-genealogy.md#task-4-harvest-the-six-outcome-domains))

### Phase 2: Outcome Detection, Generation Lags, and Metrics
- [x] Task 5: Compute quantized mobility and persistence statistics ([details](phase-02-outcomes-detection.md#task-5-compute-quantized-mobility-and-persistence-statistics)) (depends on 3, 4)
- [x] Task 6: Compose generation and generation-lag rows ([details](phase-02-outcomes-detection.md#task-6-compose-generation-and-generation-lag-rows)) (depends on 5)
- [x] Task 7: Compose the bounded `SocialMobilityAnalysis` harvest ([details](phase-02-outcomes-detection.md#task-7-compose-the-bounded-socialmobilityanalysis-harvest)) (depends on 5, 6)
- [x] Task 8: Append eight metric families (228 → 236) and wire the service ([details](phase-02-outcomes-detection.md#task-8-append-eight-metric-families-228--236-and-wire-the-service)) (depends on 7)

### Phase 3: Completed-Run Inputs, Snapshot, Store, and Publication
- [x] Task 9: Wire completed-run inputs and collector injection ([details](phase-03-artifact-publication.md#task-9-wire-completed-run-inputs-and-collector-injection)) (depends on 3, 7, 8)
- [x] Task 10: Add snapshot models, codec, paging, and ports ([details](phase-03-artifact-publication.md#task-10-add-snapshot-models-codec-paging-and-ports)) (depends on 8)
- [x] Task 11: Add the atomic store and dual-gated settings ([details](phase-03-artifact-publication.md#task-11-add-the-atomic-store-and-dual-gated-settings)) (depends on 10)
- [x] Task 12: Compose and publish completed-run snapshots ([details](phase-03-artifact-publication.md#task-12-compose-and-publish-completed-run-snapshots)) (depends on 7, 10, 11)

### Phase 4: Read Surfaces
- [x] Task 13: Add seven GET-only dual-gated routes ([details](phase-04-read-surfaces.md#task-13-add-seven-get-only-dual-gated-routes)) (depends on 10, 11)
- [x] Task 14: Add the Research UI client and panel ([details](phase-04-read-surfaces.md#task-14-add-the-research-ui-client-and-panel)) (depends on 13)

### Phase 5: Experiment and Certification Paths
- [x] Task 15: Register off-gate `social_mobility@1` ([details](phase-05-experiment-certification.md#task-15-register-off-gate-social_mobility1)) (depends on 1, 9, 12)
- [x] Task 16: Add in-process end-to-end coverage ([details](phase-05-experiment-certification.md#task-16-add-in-process-end-to-end-coverage)) (depends on 9, 12, 13, 15)
- [x] Task 17: Add determinism, property bounds, and leakage coverage ([details](phase-05-experiment-certification.md#task-17-add-determinism-property-bounds-and-leakage-coverage)) (depends on 16)

### Phase 6: Invariants, Documentation, and Certification
- [x] Task 18: Sweep context, catalog, and ownership pins ([details](phase-06-invariants-docs.md#task-18-sweep-context-catalog-and-ownership-pins)) (depends on 1-17)
- [x] Task 19: Documentation via `$aif-docs` ([details](phase-06-invariants-docs.md#task-19-documentation-via-aif-docs)) (depends on 18)
- [x] Task 20: Add documentation pin and negative parity checks ([details](phase-06-invariants-docs.md#task-20-add-documentation-pin-and-negative-parity-checks)) (depends on 19)
- [x] Task 21: Required-gate verification certification ([details](phase-06-invariants-docs.md#task-21-required-gate-verification-certification)) (depends on 16-20)

## Commit Plan

- **Commit 1** (after tasks 1-4): `feat(analysis): add social mobility contract and genealogy evidence`
- **Commit 2** (after tasks 5-9): `feat(analysis): compose social mobility detection and metrics`
- **Commit 3** (after tasks 10-14): `feat(simulation): publish social mobility snapshots and read surfaces`
- **Commit 4** (after tasks 15-17): `test: certify social mobility experiment and end-to-end paths`
- **Commit 5** (after tasks 18-21): `test,docs: sweep V4 context and catalogue pins`

Commit checkpoints are suggestions only. Do not commit during `$aif-implement`
unless the user explicitly authorizes commits.

## Definition of Done

- V4-25 adds exactly one analysis-only context, `social_mobility`; counts are
  16 contexts / 12 flags / 8 owned / 4 unowned; the map is `v4-context-map-v4`;
  no capability flag, `runner-config-v57`, runner root field, per-agent key,
  command, event, observer semantic type, write pair, `/v2` route, or migration
  is added.
- Genealogy comes from committed `KinshipEdgeRecorded` and
  `AgentCreated.generation_index`; bootstrap owners are generation 0; no
  `WorldState`, `KinshipGraph`, runtime, store, or API object is read.
- Agent-id-keyed evidence and body-id-keyed objective events join through one
  explicit identity map built from founder config plus committed identity
  events; unmapped owners are reported and never guessed.
- Six domains are measured independently with one documented measure each:
  resources, skills, social influence, organization roles, educational access,
  and productive assets.
- Objective outcomes, owner-scoped outcomes, and analytical mobility rows are
  separate layers with a hard leakage guard; no composite wealth, class, merit,
  prestige, or mobility score exists.
- Statistics are 5-bin persistence, upward/downward shares, mean absolute rank
  change, and quantized Spearman milli; fewer than 8 resolved pairs is
  `insufficient_samples`.
- Generation indices are capped at 32 and lag strata 1-4 recompute their own
  statistics; many-generation fixtures cover at least three generations.
- Eight metric families append exactly at positions 228-235; the first 228 ids,
  order, versions, and value keys are unchanged; every active pin and docs
  footer is swept to 236.
- Analysis activates only with committed events, a kinship edge, and an outcome
  channel; otherwise no metric input, no snapshot field, and no off-path change.
- `social-mobility-snapshot-v1` round-trips canonically with no wall-clock
  field; `social-mobility-store-v1` is atomic, quota-bounded, idempotent, and
  corruption-safe.
- Seven GET-only dual-gated routes fail closed with
  `social_mobility_disabled`, default limit 100, max 500, `window_index` ≤ 511;
  the Research UI panel is read-only; no new Godot overlay exists.
- Publication is programmatic and post-completion; no CLI producer or runner
  flag is added.
- Off-gate `social_mobility@1` is registered with three arms and is absent from
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
  cross-links in `docs/generational-runner.md`, `docs/lineage-explorer.md`,
  `docs/organizations.md`, and `docs/economic-inequality.md`, with positive and
  negative parity checks.
- Required gates are certified or explicitly `unexecuted`; the roadmap remains
  owned by `$aif-roadmap`, which must register V4-23, V4-24, and V4-25 later.

## Verification Receipt

Filled by Task 21. No lane is green until its command and result are recorded
here.

| Lane | Command | Result | Prerequisite / note |
| --- | --- | --- | --- |
| Unit + architecture correctness | `uv run pytest tests/unit tests/architecture -q` | passed: 11,779 passed in 11:50 | includes the 228->236 and 15->16 pin sweep and the V4-25 regression fixes; one later admission-identity regression is covered in the focused 157 |
| Focused social-mobility suites | `uv run pytest tests/unit/test_social_mobility_*.py tests/architecture/test_social_mobility_*.py tests/integration/test_social_mobility_store_api.py -q` | passed: 157 unit+architecture and 2 integration | integration lane run separately with `-m integration` |
| Python coverage (focused) | `uv run pytest tests/unit/test_social_mobility_*.py tests/architecture/test_social_mobility_*.py -q --cov=src --cov-report=term` | passed: 157 passed; focused-lane total 22% of `src` | coverage is lane-scoped, not repository-wide |
| Python coverage (full lane) | `uv run pytest tests/unit tests/architecture -q --cov=src --cov-report=term` | unexecuted: timed out after 40 minutes at ~1% | rerun with an extended timeout; non-coverage full lane passed 11,779 tests |
| Static: Ruff | `uv run ruff check src tests` | passed: all checks passed |  |
| Static: mypy | `uv run mypy src tests` | passed: no issues in 2,760 source files | no per-file ignore directives in the V4-25 modules |
| Static: import boundaries | `uv run lint-imports` | passed: 25 contracts kept, 0 broken |  |
| Integration (non-scale) | `uv run pytest tests/integration -m "not scale" -q` | passed: 59 passed, 60 skipped, 5 deselected |  |
| Social-mobility store/API integration | `uv run pytest tests/integration/test_social_mobility_store_api.py -q -m integration` | passed: 2 passed |  |
| Compose config | `docker compose config` | passed: exit 0 |  |
| Research UI tests | `cd clients/research-ui && ./node_modules/.bin/vitest run` | passed: 68 files, 321 tests |  |
| Research UI types | `cd clients/research-ui && ./node_modules/.bin/svelte-check --tsconfig ./tsconfig.app.json` | passed: 0 errors, 0 warnings |  |
| Godot regression | `GODOT_BIN=~/.cache/palimpsest-godot/Godot_v4.7.2-stable_linux.x86_64 "$GODOT_BIN" --headless --path clients/godot-observer --script res://tests/run_protocol.gd` | passed: `godot_protocol_tests failed=0` | existing suite only; no client change |
| Compose/browser acceptance | attested image + headed browser harness | unexecuted | requires an attested image; no browser harness run |
| Benchmark regression (non-scale) | `PALIMPSEST_V4_SCALE_IDS=100000 uv run pytest tests/benchmarks -m "not scale" -q` | passed: 1 passed, 20 deselected |  |

`git status` must confirm no `.ai-factory/ROADMAP.md` edit from this plan, no
`alembic/versions/0018*` file, no `clients/godot-observer/` source change, no
`/v2` route, and no new V4 capability flag. The new context registration,
analysis modules, snapshot/store, seven routes, Research UI panel, eight metric
families, docs, and off-gate experiment are the only V4-25 surfaces changed.
