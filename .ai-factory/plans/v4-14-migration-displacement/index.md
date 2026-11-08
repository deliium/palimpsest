<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-14 Mass Migration and Displacement

Mode: ultra
Branch: main
Created: 2026-11-07

## Original Request

v4-14 mass migration

Naming requirement:

Use `v4-14-migration-displacement`.

Extend migration mechanics for population-scale movement.

Support migration driven by:

- resource scarcity
    
- climate/environment
    
- conflict
    
- opportunities
    
- social networks
    
- institutions
    
Do NOT create a hard-coded Refugee social category.

Research analytics may classify forced/displacement-like migration from causal evidence.

Track:

origin  
route  
destination  
cause evidence  
family/social clusters  
integration outcomes

Support migration waves without agents sharing collective telepathy.

## Settings

- Testing: yes; full strategy. Unit, architecture, determinism, integration,
  Compose/browser, Godot regression, Research UI, benchmark regression, and
  static gates, with coverage enabled for Python lanes.
- Logging: verbose, metadata-only. Bounded DEBUG flow/counts, INFO milestones,
  WARN unresolved references/truncation, ERROR safe codes.
  `PALIMPSEST_LOG_LEVEL` controls operational verbosity. Never log participant
  or actor identities, location or migration ids, cause or cluster ids, route
  bodies, frame bodies, observation bodies, prompts, credentials, tokens, DSNs,
  memories, embeddings, utterance bodies, or payload surrogates.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 26.
- Language: English UI and artifacts; technical terms preserved.
- Git: enabled; base `main`; no branch or worktree creation; skip-push
  preference retained. Commit checkpoints are suggestions, not authorization to
  commit during planning.
- Workflow: slug IDs; normal verification with explicit complete required-gate
  certification.
- Naming: canonical stem `v4-14-migration-displacement`; the ultra bundle
  directory is `.ai-factory/plans/v4-14-migration-displacement/`, phase files
  use `phase-NN-<slug>.md`, and `index.md` is the canonical entrypoint.
- Research source: `.ai-factory/RESEARCH.md` and `.ai-factory/research/` do not
  exist; no external research conclusions are invented.
- Execution: plan only. No implementation, commit, roadmap edit, or branch
  creation occurs in this invocation.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"
Rationale: V4-14 deepens the owned `organizations` V4 context and extends the
owned V3 `multi_polity_migration`/`regions_migration` seam with owner-scoped
migration intents, route beliefs, cause evidence, social-cluster beliefs,
integration beliefs, and wave observations; four detached analysis layers, four
metric families (176 -> 180), `migration-displacement-snapshot-v1`, a
`migration-displacement-store-v1` filesystem store, six read-only routes, a
Research UI panel, and four Godot overlay kinds, without adding a flag,
context, runner schema, command, event, write pair, observer semantic type,
`/v2` route, or migration. This plan does not edit or close the roadmap;
`$aif-roadmap` must register V4-14 in M8 and record the migration/displacement
deepening.

## Requirements Reconciliation

Authority: the Original Request defines scope; `.ai-factory/ARCHITECTURE.md`
("Key Principles", "Capability ownership", "Important V3 seams", "Versioned
Extension Contract", V3-22, V4-01 through V4-13 seams) and `.ai-factory/RULES.md`
constrain every edit; `.ai-factory/DESCRIPTION.md` and `.ai-factory/ROADMAP.md`
describe current state; completed V3 regional/migration, kinship, organization,
institution, diplomacy, conflict, and border code plus
`tests/architecture/test_v4_architecture_invariants.py`,
`test_regional_cross_feature_invariants.py`, `test_borders_boundaries.py`,
`test_organized_conflict_boundaries.py`, `test_diplomacy_boundaries.py`,
`test_treaty_boundaries.py`, `test_organization_boundaries.py`,
`test_formal_rule_boundaries.py`, and `test_analysis_isolation.py` govern
compatibility. V4-14 claims no new V4 flag and creates no context; it deepens
the owned `organizations` context and extends the owned V3
`multi_polity_migration` seam.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| V4-14 adds no V4 flag, context, `runner-config-v57`, runner root field, or per-agent runner key; it deepens the already-owned `organizations` context and the owned V3 migration seam | Original Request "Extend migration mechanics"; `.ai-factory/ARCHITECTURE.md` "Capability ownership"; `src/simulation/v4_architecture.py` 60-76, 110-127 | Task 3 tests; Task 23 pins; Task 27 v57 absence |
| Activation is `runner-config-v56` + `v4_capability_flags.organizations` + `v3_capability_flags.multi_polity_migration` + `regions_migration.cognition_mode=DETERMINISTIC`; legacy v15/v44/v55 behavior is unchanged | `src/simulation/runner.py` 1024-1050, 1187-1215, 2818-2866; `src/simulation/runner_models.py` 9379-9425, 9653-9685 | Task 3 tests |
| Migration cause is one owner's belief; no objective cause, hardship, displacement, refugee, asylum, or integration field exists | Original Request "Do NOT create a hard-coded Refugee social category"; `.ai-factory/ARCHITECTURE.md` Key Principle 1 | Task 1/4/23 tests |
| Origin, route, and destination are logical `EntityId` locations; a route is an ordered adjacent sequence of 2-4 locations; no grid, coordinate, polygon, area, or teleport exists | Original Request "origin route destination"; `src/world/regions.py` 39-224; `src/world/models.py` 81-111 | Task 1/8/23 tests |
| Physical movement remains existing `Move`/`Transport`/`Flee`; V4-14 adds no command, event, write pair, codec marker, or migration | `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime"; `src/world/_rules.py` 1167-1196, 1527-1569, 1621-1673 | Task 8/23/24 tests |
| The owner retains six row families: migration intent, route belief, cause evidence, social-cluster belief, integration belief, wave observation, plus notices | Original Request "Track origin route destination cause evidence family/social clusters integration outcomes" | Task 4/23 tests |
| A migration wave is an analytical candidate over independent committed movements; no world or cognition object is shared across owners | Original Request "migration waves without agents sharing collective telepathy" | Task 13/23/24 tests |
| Family/social clusters are owner beliefs or analytical candidates; no objective household, family, clan, refugee group, or resettlement registry exists | Original Request "family/social clusters"; `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts" | Task 4/13/23 tests |
| Integration outcomes are owner beliefs and researcher-only classifications; no wellbeing, assimilation, integration, or displacement score exists | Original Request "integration outcomes"; `.ai-factory/ARCHITECTURE.md` Key Principle 1 | Task 4/13/15/23 tests |
| Displacement-like classification is researcher-only, closed (`not_displacement_like`, `displacement_like`, `mixed`, `unknown`), and derived from independent causal evidence; it never creates a Refugee role | Original Request "Research analytics may classify forced/displacement-like migration from causal evidence"; `.ai-factory/ARCHITECTURE.md` "analysis is read-only" | Task 13/14/23 tests |
| Cause evidence uses closed cause kinds (`resource_scarcity`, `environmental_hazard`, `conflict`, `opportunity`, `social_network`, `institution`, `unknown`) and closed sources; missing anchors stay unresolved | Original Request six causes; `src/analysis/organized_conflict_contract.py` 35-91; `src/analysis/borders_contract.py` 28-96 | Task 1/4/23 tests |
| `mdp_v1` is 13 semantic fields, at most 256 characters per relation, at most 4 relations, carried only inside existing `Talk`/`Ask`/`Tell`; malformed/oversize/speaker-mismatched frames are dropped | Original Request "without agents sharing collective telepathy"; `src/agents/cognition/borders_communication.py` 33-42, 527-532 | Task 7/23 tests |
| Peer claims, origins, destinations, routes, causes, clusters, and declared provenance are untrusted; the receiver assigns provenance from delivery and resolves anchors locally | `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts" | Task 6/7/23 tests |
| The update order is own intents -> route beliefs -> cause evidence -> cluster beliefs -> frames -> anchor resolution -> integration beliefs -> wave observations -> expire -> caps -> digest | Original Request "Support"; `.ai-factory/ARCHITECTURE.md` Key Principle 1 | Task 6/23 tests |
| No migration helper returns, constructs, submits, resolves, or blocks an `AgentCommand`; every physical effect remains ordinary `WorldEngine` admission | `.ai-factory/ARCHITECTURE.md` "anti-patterns"; V4-13 non-goals | Task 8/23/24 tests |
| `WorldEngine`, perception, admission, stop selectors, memory, prompts, observer semantics, and Godot physics never read a migration ledger | `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime" | Task 9/23/24 tests |
| Detached analysis harvests four layers: objective movement from committed events; subjective cause from exported ledgers; analytical waves from the first two; integration outcomes from committed post-arrival evidence | Original Request four tracked dimensions; `.ai-factory/ARCHITECTURE.md` Key Principle 1 | Task 11/12/13/23 tests |
| A hard leakage guard keeps the four layers in separate types; a leak is a hard failure | `.ai-factory/ARCHITECTURE.md` Key Principle 1; `src/analysis/borders_layers.py` 28-182 | Task 12/23 tests |
| Migration candidates are content-addressed (`mig-`) and forward-only (`emerged`, `continued`, `transformed`, `split`, `merge`, `dissolved`); `org-`/`msoc-` joins are read-only | `.ai-factory/ARCHITECTURE.md` "analysis is read-only" | Task 14/23 tests |
| Alignment is researcher-only (`consistent`, `unresolved`, `inconsistent`, `not_applicable`); missing evidence is `unresolved`, never `inconsistent` | Original Request causal evidence; V4-08/V4-11 alignment precedent | Task 14/23 tests |
| Four families append (`migration_wave_structure@1`, `migration_cause_evidence@1`, `migration_cluster_cohesion@1`, `migration_integration_outcome@1`), raising the catalog 176 -> 180; the first 176 keep id, order, version, and value keys | Original Request "Research analytics"; `src/analysis/specifications.py` 52-53, 4067-4219, `_BUILDERS` tail 8354-8357, count check 8382 | Task 15/23/26 tests |
| `migration-displacement-snapshot-v1` is a new canonical bounded snapshot with a required summary row and a candidate row family; lineage and alignment tokens resolve to candidates; it does not rewrite `organized-conflict-snapshot-v1`, `borders-snapshot-v1`, `diplomacy-snapshot-v1`/`v2`, or any existing store | `.ai-factory/ARCHITECTURE.md` accepted-set/exact-key-set; V4-06/V4-13 snapshot precedent | Task 16/18/19/23 tests |
| Six GET routes under `/v1/simulations/{run_id}/migration` require `SUBJECTIVE_DEBUG`, return 503 `migration_displacement_disabled`, and 404 for unknown published records | `docs/research-api.md`; `src/api/routes/borders.py` 197-377 | Task 20/23/24 tests |
| Cursors bind run, publication, digest, purpose, and filters; mismatch is 400 and expiry 410 | `src/simulation/borders_ports.py` 54-91; `src/api/borders_cursor.py` | Task 17/20/24 tests |
| Publication is opt-in, post-completion, atomic, quota-bounded, and isolated from scientific status | `src/experiments/borders_publication.py` 66-340; `src/persistence/borders_filesystem.py` 35-268 | Task 18/19/24 tests |
| The migration E2E runs in-process in the focused/unit lane with real ticks, movements, causes, clusters, publication, and all six routes; it is never reported as integration-only | Plan Settings; `tests/unit/test_borders_e2e.py` | Task 24/25 tests |
| Every current 176 pin is swept to 180; historical revision statements and the first-176 digests remain unchanged | `src/analysis/specifications.py:53`; current 176 occurrences measured at plan time | Task 15 sweep; Task 26 re-run |
| The Godot evidence model stays three-valued (objective, subjective, analytical); four migration overlay kinds map onto it, with cause and wave visibly distinct | Original Request "Godot/research overlays must distinguish" (applied to migration); `clients/godot-observer/scripts/presentation/evidence_class.gd` 5-81 | Task 22/23 tests |
| The roadmap is owned by `$aif-roadmap` and is not edited here | `.ai-factory/ARCHITECTURE.md` requirement 7 | Task 25/27 `git status` |

### Supported combinations and availability transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| Default runner config, all flags off | No migration-displacement ledger | No migration metric, snapshot, publication, or route data | Task 3/24 tests |
| v15/v44/v55 + deterministic regional migration | Legacy regional ledger only | No migration-displacement ledger; byte-compatible behavior | Task 3/9 tests |
| v56 without `organizations` | No migration-displacement ledger | No migration beliefs or routes | Task 3 test |
| v56 + `organizations` without `regions_migration` | No migration-displacement ledger | No migration beliefs | Task 3 test |
| v56 + `organizations` + `regions_migration` with cognition disabled | No migration-displacement ledger | Physics-only migration unchanged | Task 3 test |
| v56 + `organizations` + `multi_polity_migration` + deterministic regional cognition | Migration-displacement ledger active | Intents, routes, causes, clusters, integration beliefs, wave observations | Task 3/6/24 tests |
| v56 + `organizations` + `multi_polity_migration` + deterministic regional cognition + `diplomacy` | Ledger active | Treaty anchors may resolve read-only; no treaty rewrite | Task 6/23 tests |
| v56 + `organizations` + deterministic regional cognition without `diplomacy` | Ledger active | Treaty anchors stay unresolved; no prerequisite failure | Task 3/6 tests |
| v56 + `organizations` + deterministic regional cognition + `organized_conflict` | Ledger active | Conflict cause refs may resolve read-only; no conflict rewrite | Task 6/23 tests |
| v56 + `organizations` + deterministic regional cognition + `formal_rules`/institution modes | Ledger active | Rule/institution cause refs may resolve; no rule or institution rewrite | Task 6/23 tests |
| Another unowned V4 flag | No behavior change | Still fails closed with `capability_unimplemented` | Task 3/23 tests |
| Owner plans one adjacent move | One intent + one route belief | `mdi-`/`mdr-` rows; no shared wave | Task 4/8 test |
| Owner plans a 2-4 location route | One intent | Ordered route; each hop remains an ordinary `Move` | Task 1/8 test |
| Two owners independently move to the same destination within the window | Two ledgers | One analytical wave candidate; no shared knowledge | Task 13/24 test |
| Two owners move on the same route without communication | Two ledgers | One analytical wave candidate; no telepathy | Task 13/23 test |
| Owner reports a cause in `mdp_v1` | Delivered frame | Owner-local cause evidence; declared provenance replaced | Task 7 test |
| Malformed/oversize/speaker-mismatched `mdp_v1` | No row | `malformed_frame`; frame dropped | Task 7 test |
| Cause evidence with an unresolved organization/institution/rule/diplomacy/treaty/conflict/border anchor | Row retained | `unresolved_anchor` notice; no invented anchor | Task 6 test |
| Same-root testimony repeated by peers | One independent cause | `same_root_suppressed`; no double counting | Task 13/23 test |
| Wave with only opportunity/social/institution causes | One wave | `not_displacement_like` | Task 13 test |
| Wave with only displacement bases | One wave | `displacement_like` | Task 13 test |
| Wave with mixed bases | One wave | `mixed` | Task 13 test |
| Wave with no cause evidence | One wave | `unknown`; no invented cause | Task 13 test |
| Participant returns to origin | One outcome | `returned`; no integration score | Task 13 test |
| Participant moves onward | One outcome | `onward`; no integration score | Task 13 test |
| Participant settles with evidence | One outcome | `settled`; counts and coverage only | Task 13 test |
| Cap exceeded with droppable terminal rows | Truncated ledger | `migration_displacement_truncated:<family>`; deterministic | Task 10 test |
| Cap exceeded with nothing droppable | Prior ledger retained | `migration_displacement_capacity_reached` | Task 10 test |
| Snapshot exceeds 4 MiB or row caps | No publication | `migration_displacement_size_limit` receipt | Task 16/18 test |
| Duplicate publication id with different bytes | Existing artifact untouched | `migration_displacement_publication_exists` | Task 19 test |
| `PALIMPSEST_MIGRATION_DISPLACEMENT_ROOT` unset | API state unset | 503 `migration_displacement_disabled`; CLI receipt `disabled` | Task 19/20/24 test |
| Cursor reused with the same binding | Same page | 200; digest matches | Task 17/20 test |
| Cursor reused after any binding change | No page served | 400 `migration_displacement_cursor_invalid`; expiry 410 | Task 17/20 test |
| Corrupt store payload | No false 404 | 500 `migration_displacement_store_corrupt` | Task 19/20 test |
| Run incomplete or publication failed | Scientific result unchanged | Receipt `unavailable`/`failed` only | Task 18/19/24 test |
| In-process migration E2E without PostgreSQL | No integration prerequisite | Runs in the focused/unit lane with real ticks, commands, publication, and routes | Task 24/25 test |
| Required Compose/browser/Godot/benchmark/UI lane with a missing prerequisite | No green certification | Recorded `unexecuted` with prerequisite | Task 25/27 |

No blocking open questions: every material decision is fixed below.

## Architecture and Decisions

1. **No new flag, no new context.** V4-14 deepens the owned `organizations`
   context and extends the owned V3 `multi_polity_migration` seam; the 14
   contexts, 12 flags, and `runner-config-v56` seam are unchanged.
2. **Legacy paths stay byte-compatible.** Migration-displacement beliefs are
   active only when `organizations`, `multi_polity_migration`, and deterministic
   regional migration are all on. v15/v44/v55 runs without `organizations`
   produce no new ledger.
3. **One owner, one belief.** An intent, route, cause, cluster, integration
   outcome, or wave observation belongs to exactly one owner. No shared wave,
   cause registry, refugee category, or truth store exists.
4. **Movement is physical.** Physical movement remains existing `Move`,
   `Transport`, and `Flee`; population-scale movement is composed of many
   independent ordinary commands, not a shared group command. A migration route
   is an owner belief about an ordered logical path, not a new command or
   teleport.
5. **A route is logical and directed.** An ordered sequence of 2-4 `EntityId`
   locations with consecutive directed hops (never undirected-collapsed); world
   adjacency is enforced at update time from visible exits/own journeys, not by
   sorting edge endpoints. No grid, coordinate, polygon, area, or
   region-to-border conversion.
6. **Six owner row families.** Migration intents, route beliefs, cause
   evidence, social-cluster beliefs, integration beliefs, wave observations;
   notices are retained.
7. **Causes are beliefs.** Closed cause kinds and sources; no objective cause,
   hardship, threat, displacement, or refugee status exists.
8. **Displacement is analytical.** `displacement_like` is a researcher-only
   classification over independent causal evidence; it never creates a social
   category, permission, or obligation.
9. **Waves are analytical.** A wave candidate groups independent committed
   movements by destination, window, and route/origin overlap; it is not a
   shared world object and does not imply shared intent.
10. **No collective telepathy.** Every owner derives its own beliefs; `mdp_v1`
    frames require actual delivery; co-movement alone transfers no knowledge.
11. **Clusters are beliefs or candidates.** Kinship is objective genealogy;
    family/social clusters remain owner beliefs or analytical candidates, never
    households or refugee groups.
12. **Integration is not a score.** Outcomes are closed labels with counts,
    durations, denominators, and coverage; no wellbeing, assimilation, or
    integration score exists.
13. **Speech is bounded.** `mdp_v1` is 13 semantic fields, 256 characters per
    relation, at most 4 relations, inside existing `Talk`/`Ask`/`Tell`.
14. **Peer claims are untrusted.** Speaker binding and local provenance are
    mandatory; declared provenance is replaced from delivery.
15. **Update order is fixed.** Own intents, route beliefs, cause evidence,
    clusters, frames, anchor resolution, integration beliefs, wave observations,
    expire, caps, digest.
16. **No command path.** No migration helper constructs, submits, resolves, or
    blocks an `AgentCommand`. Every physical effect remains ordinary admission.
17. **No world read.** `WorldEngine`, perception, admission, stop selectors,
    memory, prompts, observer semantics, and Godot physics never read the
    ledger.
18. **Four layers are separate.** Objective movement, subjective cause,
    analytical wave, integration outcome; a hard leakage guard fails the build.
19. **Patterns are descriptive.** Closed labels with counts and denominators; no
    composite migration, displacement, integration, or wellbeing score.
20. **Identity joins are read-only.** `mig-` candidates are content-addressed;
    `org-`/`msoc-` identities are never minted, renamed, split, merged, or
    dissolved.
21. **Alignment is researcher-only.** `consistent`, `unresolved`,
    `inconsistent`, `not_applicable`; it never reaches cognition, prompts,
    memory, world state, observer semantics, or stop selectors.
22. **Four metrics append.** 176 -> 180; the first 176 keep id, order, version,
    and value keys; no composite migration score.
23. **A new snapshot and store.** `migration-displacement-snapshot-v1` and
    `migration-displacement-store-v1` are additive; the snapshot has a required
    summary row and a candidate row family so lineage/alignment tokens resolve;
    existing snapshots/stores are unchanged.
24. **Six GET routes.** All require `SUBJECTIVE_DEBUG`, fail closed with
    `migration_displacement_disabled`, and never serve unpublished memory.
25. **Publication is opt-in and non-interfering.** A storage/composition failure
    changes only the receipt.
26. **The Research UI is read-only.** Four sections with epistemic badges; no
    authority, legitimacy, refugee status, enforcement, score, winner, or
    sovereignty.
27. **Godot keeps three evidence classes.** Four overlay kinds map onto
    objective, subjective, and analytical; cause is distinct from wave and
    integration.
28. **No new wire surface.** No event, command, observer semantic type, write
    pair, codec marker, `/v2` route, `observer-protocol-v2`, or SQL migration.
29. **Deterministic by construction.** Sorted ordering, content-addressed IDs,
    canonical JSON digests, quantized ratios, integer counts, no `hash()`, no
    UUID, no wall-clock domain values.
30. **Pin sweeps distinguish current from historical.** Current pins move to 180;
    historical revision statements and the first-176 order keep their numbers.
31. **No automatic generalization.** V4-14 implements no infrastructure,
    supply-chain, market, credit, science, epidemic, ecological, disaster,
    resilience, war, or macro-society behavior.
32. **The roadmap is not edited.** `$aif-roadmap` owns M8 registration and
    milestone closure.

### Compatibility pins

Default runner/result `v4`/`v2`; latest feature runner `v55`; accepted runner
`v56` only; events `EVENT_SCHEMA_REPLAY_V22` (22); codec `v20`; commands 43;
observer semantic types 73; metric families **180 (V4-14 change)**; Alembic
`0017` with no `0018`; `/v1`; `observer-protocol-v1`; observer layout
`observer-layout-v1`; observer capabilities 4 advertised / 6 reserved; four
reserved write pairs (events 23-26 / codecs `v21`-`v24`);
`prepare_parallel=False`; six GET organization, six GET formal-rule, six GET
dispute, six GET evidence, six GET representation, eight GET diplomacy, six GET
organized-conflict, six GET borders, and **six GET migration** routes; eight
cursor purposes per diplomacy context, six per organized-conflict context, six
per borders context, and **six per migration context**; snapshots
`organization-snapshot-v1`/`v2`/`v3`, `formal-rule-snapshot-v1`,
`dispute-resolution-snapshot-v1`, `evidence-testimony-snapshot-v1`,
`delegation-representation-snapshot-v1`, `diplomacy-snapshot-v1`/`v2`,
`organized-conflict-snapshot-v1`, `borders-snapshot-v1`, and
**`migration-displacement-snapshot-v1`**; stores `organization-store-v1`,
`formal-rule-store-v1`, `dispute-resolution-store-v1`,
`evidence-testimony-store-v1`, `delegation-representation-store-v1`,
`diplomacy-store-v1`, `organized-conflict-store-v1`, `borders-store-v1`, and
**`migration-displacement-store-v1`**; 14 V4 contexts / 12 flags / **5 owned
flags** (`organizations`, `formal_rules`, `legal_disputes`, `diplomacy`,
`organized_conflict`) / **7 unowned** (`infrastructure_networks`,
`supply_chains`, `markets_credit`, `science`, `epidemics`, `ecological_feedback`,
`disasters`). The owned V3 flag `multi_polity_migration` is unchanged.
`institutional_economy` and `multi_hop_testimony_tracking` remain unowned and
are not part of the 12 V4 flags. `/version` is unchanged; observer capabilities
are unchanged.

## Phase Index

1. [Phase 1: Migration-Displacement Contract and Seam](phase-01-migration-contract-and-seam.md) — Tasks 1-3
2. [Phase 2: Owner-Scoped Migration Beliefs](phase-02-owner-scoped-migration.md) — Tasks 4-10
3. [Phase 3: Detached Detection and Metrics](phase-03-detached-analysis.md) — Tasks 11-15
4. [Phase 4: Migration-Displacement Snapshot](phase-04-snapshot.md) — Tasks 16-17
5. [Phase 5: Composition and Durable Publication](phase-05-composition-publication.md) — Tasks 18-19
6. [Phase 6: Read-Only API, Research UI, and Godot Overlays](phase-06-read-only-surfaces.md) — Tasks 20-22
7. [Phase 7: Invariants, End-to-End Migration, and Regression](phase-07-invariants-and-regression.md) — Tasks 23-25
8. [Phase 8: Documentation and Final Verification](phase-08-docs-and-verification.md) — Tasks 26-27

## Cross-Phase Dependencies

- All phases assume the completed V3 regional/migration, kinship, organization,
  institution, diplomacy, conflict, and border stacks plus V4-01 through V4-13;
  V4-14 does not rewrite them, but Tasks 23/25 must keep their suites green.
- Task 2 depends on Task 1: the locked policy uses the frozen vocabulary.
- Task 3 depends on Tasks 1-2: activation consumes the contract and policy.
- Task 4 depends on Tasks 1-3: rows use the vocabulary and ledger seam.
- Task 5 depends on Task 4: IDs/digest cover the row families.
- Task 6 depends on Tasks 4-5 and 7: the pipeline mutates the complete ledger
  and applies delivered `mdp_v1` frames from Task 7.
- Task 7 depends on Task 4: `mdp_v1` encodes the row vocabulary.
- Task 8 depends on Tasks 4/6: route/destination cognition consumes the ledger.
- Task 9 depends on Tasks 6-8: carry consumes the prepared ledger and biases.
- Task 10 depends on Tasks 6-9: caps/export cover the complete ledger.
- Task 11 depends on Task 10: harvest reads exported ledgers and committed
  events.
- Task 12 depends on Task 11: layers consume harvested rows.
- Task 13 depends on Tasks 11-12: detection consumes the four layers.
- Task 14 depends on Tasks 11-13: alignment and identity consume causes, waves,
  and outcomes.
- Task 15 depends on Tasks 11-14: metrics consume rows, candidates, and
  alignment.
- Task 16 depends on Tasks 10-15: the snapshot mirrors derived state and metric
  provenance.
- Task 17 depends on Task 16: paging and ports select typed rows.
- Task 18 depends on Tasks 10, 13, 15, and 17: the composer derives
  classifications and analysis at publication time.
- Task 19 depends on Tasks 16-18: the store and CLI call the composer.
- Task 20 depends on Task 19: the API reads the committed store.
- Task 21 depends on Task 20: the panel consumes the new routes.
- Task 22 depends on Task 20: the overlays consume the new routes.
- Task 23 depends on Tasks 2-22: the suite asserts every authority claim.
- Task 24 depends on Tasks 8-22: the E2E uses real ticks, commands,
  publication, and routes.
- Task 25 depends on Tasks 23-24: regression runs after invariant/E2E gates.
- Task 26 depends on Tasks 2-25: documentation describes verified surfaces.
- Task 27 depends on Tasks 24-26: final certification needs receipts and docs.

## Tasks

### Phase 1: Migration-Displacement Contract and Seam
- [x] Task 1: Freeze the migration-displacement vocabulary, identifier grammar, and origin-route-destination contract ([details](phase-01-migration-contract-and-seam.md#task-1-freeze-the-migration-displacement-vocabulary-identifier-grammar-and-origin-route-destination-contract))
- [x] Task 2: Add the locked migration-displacement cognition and analysis policies ([details](phase-01-migration-contract-and-seam.md#task-2-add-the-locked-migration-displacement-cognition-and-analysis-policies)) (depends on 1)
- [x] Task 3: Activate migration-displacement cognition on the organizations and regional-migration seam without a new runner schema ([details](phase-01-migration-contract-and-seam.md#task-3-activate-migration-displacement-cognition-on-the-organizations-and-regional-migration-seam-without-a-new-runner-schema)) (depends on 1, 2)

### Phase 2: Owner-Scoped Migration Beliefs
- [x] Task 4: Define intents, route beliefs, cause evidence, social-cluster beliefs, integration beliefs, and wave observations ([details](phase-02-owner-scoped-migration.md#task-4-define-intents-route-beliefs-cause-evidence-social-cluster-beliefs-integration-beliefs-and-wave-observations)) (depends on 2, 3)
- [x] Task 5: Add content-addressed IDs, ledger digest, and canonical owner ledger ([details](phase-02-owner-scoped-migration.md#task-5-add-content-addressed-ids-ledger-digest-and-canonical-owner-ledger)) (depends on 4)
- [x] Task 6: Implement the ordered migration-displacement update pipeline ([details](phase-02-owner-scoped-migration.md#task-6-implement-the-ordered-migration-displacement-update-pipeline)) (depends on 4, 5, 7)
- [x] Task 7: Add bounded mdp_v1 migration speech frames ([details](phase-02-owner-scoped-migration.md#task-7-add-bounded-mdp_v1-migration-speech-frames)) (depends on 4)
- [x] Task 8: Extend deterministic route and destination cognition with cause-weighted multi-hop plans ([details](phase-02-owner-scoped-migration.md#task-8-extend-deterministic-route-and-destination-cognition-with-cause-weighted-multi-hop-plans)) (depends on 4, 6)
- [x] Task 9: Wire migration beliefs through cognition, runtime carry, checkpoints, and export ([details](phase-02-owner-scoped-migration.md#task-9-wire-migration-beliefs-through-cognition-runtime-carry-checkpoints-and-export)) (depends on 6-8)
- [x] Task 10: Enforce migration-displacement caps, notices, and owner export ([details](phase-02-owner-scoped-migration.md#task-10-enforce-migration-displacement-caps-notices-and-owner-export)) (depends on 6-9)

### Phase 3: Detached Detection and Metrics
- [x] Task 11: Harvest objective migration movement rows from committed events ([details](phase-03-detached-analysis.md#task-11-harvest-objective-migration-movement-rows-from-committed-events)) (depends on 10)
- [x] Task 12: Harvest owner migration rows and keep four layers separate ([details](phase-03-detached-analysis.md#task-12-harvest-owner-migration-rows-and-keep-four-layers-separate)) (depends on 11)
- [x] Task 13: Detect migration waves, displacement-like classification, social clusters, and integration outcomes ([details](phase-03-detached-analysis.md#task-13-detect-migration-waves-displacement-like-classification-social-clusters-and-integration-outcomes)) (depends on 11, 12)
- [x] Task 14: Add migration lineage, read-only identity joins, and researcher-only alignment ([details](phase-03-detached-analysis.md#task-14-add-migration-lineage-read-only-identity-joins-and-researcher-only-alignment)) (depends on 11-13)
- [x] Task 15: Add four metric families and raise the catalog to 180 ([details](phase-03-detached-analysis.md#task-15-add-four-metric-families-and-raise-the-catalog-to-180)) (depends on 11-14)

### Phase 4: Migration-Displacement Snapshot
- [x] Task 16: Define migration-displacement-snapshot-v1 and its canonical codec ([details](phase-04-snapshot.md#task-16-define-migration-displacement-snapshot-v1-and-its-canonical-codec)) (depends on 10-15)
- [x] Task 17: Add migration-displacement ports, cursor purposes, and bounded paging ([details](phase-04-snapshot.md#task-17-add-migration-displacement-ports-cursor-purposes-and-bounded-paging)) (depends on 16)

### Phase 5: Composition and Durable Publication
- [x] Task 18: Compose completed-run migration-displacement views and receipts ([details](phase-05-composition-publication.md#task-18-compose-completed-run-migration-displacement-views-and-receipts)) (depends on 10, 13, 15, 17)
- [x] Task 19: Add the filesystem store, settings, and CLI producer ([details](phase-05-composition-publication.md#task-19-add-the-filesystem-store-settings-and-cli-producer)) (depends on 16-18)

### Phase 6: Read-Only API, Research UI, and Godot Overlays
- [x] Task 20: Add six GET migration routes, schemas, and app wiring ([details](phase-06-read-only-surfaces.md#task-20-add-six-get-migration-routes-schemas-and-app-wiring)) (depends on 19)
- [x] Task 21: Add the read-only Research UI migration view ([details](phase-06-read-only-surfaces.md#task-21-add-the-read-only-research-ui-migration-view)) (depends on 20)
- [x] Task 22: Add the four-layer Godot migration overlays ([details](phase-06-read-only-surfaces.md#task-22-add-the-four-layer-godot-migration-overlays)) (depends on 20)

### Phase 7: Invariants, End-to-End Migration, and Regression
- [ ] Task 23: Add the migration-displacement boundary and determinism suite ([details](phase-07-invariants-and-regression.md#task-23-add-the-migration-displacement-boundary-and-determinism-suite)) (depends on 2-22)
- [ ] Task 24: Add the in-process migration end-to-end scenario ([details](phase-07-invariants-and-regression.md#task-24-add-the-in-process-migration-end-to-end-scenario)) (depends on 8-22)
- [ ] Task 25: Execute the full V1-V4 regression and qualification lanes ([details](phase-07-invariants-and-regression.md#task-25-execute-the-full-v1-v4-regression-and-qualification-lanes)) (depends on 23, 24)

### Phase 8: Documentation and Final Verification
- [ ] Task 26: Execute the documentation checkpoint ([details](phase-08-docs-and-verification.md#task-26-execute-the-documentation-checkpoint)) (depends on 2-25)
- [ ] Task 27: Perform final V4-14 verification ([details](phase-08-docs-and-verification.md#task-27-perform-final-v4-14-verification)) (depends on 24-26)

## Verification Receipt (Tasks 25 and 27)

To be completed by Task 25 and audited by Task 27. Every required lane must be
recorded as exactly one of `executed_passed`, `executed_failed`, or
`unexecuted`. An `unexecuted` lane carries its missing prerequisite and blocks
certification; it is never a skip-pass. The plan is created before
implementation, so every lane starts `unexecuted`.

| Lane | State | Evidence |
| --- | --- | --- |
| Python unit + architecture with coverage | unexecuted | Requires implementation; command recorded in Task 25. |
| Focused V4-14 suite | unexecuted | Requires `tests/unit/test_migration_displacement_*.py` and `tests/architecture/test_migration_displacement_boundaries.py`. |
| Focused in-process migration E2E | unexecuted | Requires the Task 24 scenario; no PostgreSQL. |
| V1/V2/V3/V4 regression selection | unexecuted | Requires the full unit+architecture run. |
| Documentation parity | unexecuted | Requires Task 26 docs and `test_migration_displacement_docs.py`. |
| Ruff | unexecuted | `uv run --frozen --python 3.12.14 ruff check src tests`. |
| Mypy | unexecuted | `uv run --frozen --python 3.12.14 mypy src tests`. |
| Import-linter | unexecuted | `uv run --frozen --python 3.12.14 lint-imports`. |
| Integration (`-m "integration and not scale"`) | unexecuted | Requires a disposable PostgreSQL/pgvector instance named with `palimpsest_test`; `PALIMPSEST_TEST_DATABASE_URL`. |
| Integration including scale | unexecuted | Requires the same disposable database plus the long-run harness. |
| Docker Compose config | unexecuted | `docker compose config --quiet`. |
| Compose/browser acceptance | unexecuted | Requires a real browser driver and source-attested image. |
| Godot 4.7.2 regression | unexecuted | Requires the pinned Godot 4.7.2 binary (`GODOT_BIN` or `godot`/`godot4`). |
| Benchmark/scale lane | unexecuted | Requires the multi-hour benchmark harness and a disposable database. |
| Research UI tests | unexecuted | `npx pnpm@10.34.9 test --run`. |
| Research UI type/static checks | unexecuted | `npx pnpm@10.34.9 check`. |
| Research UI build | unexecuted | `npx pnpm@10.34.9 build`. |

Certification outcome: **not yet executed (planning only)**. Tasks 25 and 27
must replace each lane with a truthful result and record any missing
prerequisite; an `unexecuted` required lane blocks certification.

## Commit Plan

Proposed implementation checkpoints; no commit is made by planning.

1. After Tasks 1-3: `feat(v4): add the migration-displacement contract and seam`
2. After Tasks 4-7: `feat(v4): add owner-scoped migration beliefs and mdp_v1 speech`
3. After Tasks 8-10: `feat(v4): carry, bound, and export migration beliefs`
4. After Tasks 11-15: `feat(v4): detect migration waves and append metrics`
5. After Tasks 16-19: `feat(v4): publish migration-displacement-snapshot-v1`
6. After Tasks 20-22: `feat(v4): serve read-only migration surfaces`
7. After Tasks 23-27: `test(v4): enforce and certify migration invariants`

## Blocking Conditions and Non-Goals

- Adding a new V4 flag, `runner-config-v57`, a new context, a runner root field,
  or a per-agent runner key to make this plan work is a blocking scope
  violation. Stop and re-plan.
- Claiming `infrastructure_networks`, `supply_chains`, `markets_credit`,
  `science`, `epidemics`, `ecological_feedback`, `disasters`,
  `institutional_economy`, or `multi_hop_testimony_tracking` is forbidden.
- Adding a hard-coded `Refugee`, `RefugeeStatus`, `AsylumSeeker`,
  `DisplacedPerson`, `RefugeeCamp`, `ResettlementAuthority`, `MigrationRegistry`,
  `WaveRegistry`, `CauseOracle`, `IntegrationOracle`, `AssimilationScore`,
  `WellbeingScore`, `ForcedMigrationClassifier`, `MigrationAuthority`, or
  `MigrationExecutor` class, field, role, or enum is forbidden.
- Adding an objective cause, hardship, threat, displacement, refugee, asylum,
  integration, or assimilation field to `WorldEngine`, `Observation`, events,
  or observer frames is forbidden.
- Adding a `Migrate`, `Evacuate`, `Resettle`, `Deport`, `Expel`, `Admit`,
  `Integrate`, or `FleeTo` command is forbidden. No new command type exists.
- Adding a new event, observer semantic type, write pair, codec marker, world
  artifact kind, `/v2` route, `observer-protocol-v2` serving, or SQL migration
  is forbidden.
- Editing `src/world/` to create a migration cause, wave, route owner, refugee
  status, integration status, or displacement state is forbidden. `WorldEngine`
  knows only locations, routes, occupancy, capacity, and ordinary movement.
- Letting `WorldEngine`, perception, admission, stop selectors, memory, prompts,
  observer semantics, or the Godot client read a migration ledger is forbidden.
- Letting any migration ledger, communication, analysis, snapshot, publication,
  or API helper return, construct, submit, resolve, block, or execute an
  `AgentCommand` is forbidden.
- Treating an intent, route belief, cause, cluster, integration belief, wave, or
  alignment as permission, obligation, prohibition, truth, threat, refugee
  status, legal status, guilt, liability, enforcement, or a binding finding is
  forbidden.
- Inferring a wave, cause, cluster, integration outcome, or displacement
  classification from silence, an unobserved act, or another owner's ledger is
  forbidden.
- Treating a peer-supplied `mdp_v1` frame's `subject_ref`, origin, route,
  destination, cause, cluster, or declared provenance as trusted is forbidden.
- Reading a peer owner's relationship, reputation, commitment, rule, office,
  institution, organization, decision, dispute, evidence, representation,
  diplomacy, treaty, conflict, border, territorial, or institutional-memory
  ledger to evaluate a migration is forbidden. The owner's own ledgers may
  supply local anchors.
- Reconciling conflicting intents, routes, causes, clusters, integration
  outcomes, or waves into one authoritative migration is forbidden. Analysis
  may classify waves and alignment for researchers only.
- Minting, renaming, splitting, merging, or dissolving `org-` or `msoc-`
  identities from migration analysis is forbidden.
- Computing, storing, publishing, or rendering a migration score, displacement
  score, integration score, wellbeing score, assimilation score, threat score,
  legitimacy score, winner, loser, or composite relation score is forbidden.
  All outputs are counts, durations, ratios, closed labels, and coverage.
- Rewriting `organized-conflict-snapshot-v1`, `borders-snapshot-v1`,
  `diplomacy-snapshot-v1`/`v2`, `diplomacy-store-v1`, `borders-store-v1`,
  `regional_population@1`, `regional_migration@1`,
  `regional_destination_beliefs@1`, `territorial-claims.v1`, `dip_v1`, `trt_v1`,
  `bdr_v1`, or the `diplomacy.v1`/`treaty.v1`/`borders-claims.v1` contracts is
  forbidden.
- Weakening an existing pin or assertion (catalog counts, Alembic `0017`, replay
  v22, codec v20, command count, observer semantic count, context count) is
  forbidden. The only intentional pin changes are 176 -> 180 metric families,
  the four migration families, the six migration GET routes, the new v1
  snapshot, and the new store.
- Claiming prevalence, emergence probability, predictive power, accuracy,
  reliability, moral correctness, refugee prevalence, displacement prevalence,
  or a composite migration score is forbidden.
- Editing `.ai-factory/ROADMAP.md` or closing M8 is out of scope;
  `$aif-roadmap` owns that.
- Changing the Godot observer protocol, observer capabilities, or `/version` is
  out of scope; the four migration overlays are client-side read-only additions
  on the existing three-class evidence model.
- Enabling V4 flags in matrix lanes is out of scope; `experiments.matrix_schema`
  keeps its rejection gate.
- V4-14 does not add a command selector, prompt, planning bias, or speech
  generation beyond the explicit cause-weighted route bias and `mdp_v1`
  attachment.
- Full qualification requires a disposable PostgreSQL/pgvector instance,
  Docker, a real browser driver, and the pinned Node/pnpm and Godot toolchains.
  A missing prerequisite leaves the lane unexecuted and blocks certification; it
  never becomes a skip-pass.
- Do not implement any other V4 context in this plan.

## Definition of Done

- All 27 indexed tasks have verified completion evidence; only this index holds
  task progress checkboxes.
- V4-14 adds no flag, context, `runner-config-v57`, root field, or per-agent
  runner key; the 14-context / 12-flag registry is unchanged and `organizations`
  remains the deepened owned context.
- Activation requires `runner-config-v56`, `organizations`,
  `multi_polity_migration`, and deterministic regional migration; legacy
  v15/v44/v55 paths stay byte-compatible.
- Origin, route, and destination are logical locations; a route is an ordered
  adjacent sequence of 2-4 locations; no grid, coordinate, polygon, area,
  teleport, or region-to-border conversion exists.
- The owner ledger retains migration intents, route beliefs, cause evidence,
  social-cluster beliefs, integration beliefs, wave observations, and notices
  with content-addressed IDs, a canonical digest, ordered updates, and bounded
  caps.
- Cause kinds and sources are closed; missing anchors stay unresolved; no
  objective cause, hardship, threat, refugee, asylum, displacement, or
  integration status exists.
- `mdp_v1` is 13 semantic fields, 256 characters per relation, at most 4
  relations, at most one group inside existing `Talk`/`Ask`/`Tell`; malformed,
  oversize, or speaker-mismatched frames are dropped.
- No migration helper returns, constructs, submits, resolves, or blocks an
  `AgentCommand`; every physical effect is ordinary `WorldEngine` admission.
- No collective telepathy: each owner derives its own ledger; `mdp_v1` requires
  delivery; co-movement alone transfers no knowledge; same-root testimony never
  counts as independent corroboration.
- Detached analysis harvests four layers from committed events and exported
  ledgers, keeps them in separate types with a hard leakage guard, detects
  waves, displacement-like classification, social clusters, and integration
  outcomes, derives forward-only `mig-` lineage, joins `org-`/`msoc-` read-only,
  and classifies researcher-only alignment.
- Displacement-like classification is closed and researcher-only; no
  `Refugee` social category, role, status, command, or field exists.
- The metric catalog is exactly 180 with four appended families; the first 176
  are unchanged; real completed-run assembly emits all four documents; no
  composite, displacement, integration, wellbeing, threat, or winner score
  exists.
- No test file or current-pin doc line still asserts 176; the stale-pin guard
  passes while historical revision statements and the first-176 order remain.
- `migration-displacement-snapshot-v1` and `migration-displacement-store-v1`
  are canonical, bounded, atomic, and immutable after publication; the snapshot
  carries a required summary and a candidate row family, and every
  lineage/alignment candidate token resolves; existing snapshots/stores remain
  unchanged.
- Snapshot rows and API responses contain only hashed tokens, content-addressed
  IDs, opaque anchors, and composer-derived labels; no raw agent/location id,
  free-text cause, route body, frame body, or evidence content is published.
- Six GET-only migration routes require `SUBJECTIVE_DEBUG`, have an explicit
  `migration_displacement_disabled` state, return 404 for unknown published
  records, and are consumed by a read-only Research UI panel and four Godot
  overlays.
- The Research UI distinguishes objective movement, subjective cause,
  analytical wave/displacement, and integration outcome; it derives no
  authority, legitimacy, refugee status, enforcement, score, winner, or
  sovereignty.
- Godot keeps the three-class evidence model and maps the four migration
  overlays onto it; cause is visibly distinct from wave and integration.
- Cursor reuse works on migration pages; a changed run/publication/digest/
  purpose/filter fails with 400 and expiry with 410.
- `WorldEngine` never reads a migration ledger; a cause, wave, or integration
  belief never blocks a physically possible command.
- The boundary suite proves owner-only authority, the absence of
  refugee/migration/registry/score objects, no command construction, no
  peer-ledger reads, no world-ledger reads, no `org-`/`msoc-` mutation, no
  grid/geometry, and no new commands/events/migrations; observer and migration
  pins are unchanged.
- The focused in-process migration E2E runs without PostgreSQL in the
  focused/unit lane and is never reported as an integration-only prerequisite.
- The full V1-V4 regression lanes and static gates execute and pass; any
  unexecuted required lane is reported with its blocker and is not certified.
- Documentation states what migration beliefs control (owner-scoped intents,
  routes, causes, clusters, integration beliefs, wave observations), what they
  never control (world state, admission, permission, truth, refugee status,
  enforcement, legitimacy, score, winner), how the four layers differ, how
  `mdp_v1` works, how routes are observed, and every count matches the code. The
  docs sweep updates every current 176 pin and leaves historical seam pins
  intact.
- `docs/migration-displacement.md` is the canonical contract;
  `docs/analysis-metrics.md` documents the four families,
  `docs/research-api.md` documents the six routes, `docs/research-ui.md`
  documents the panel, `docs/godot-civilization-overlays.md` and
  `docs/godot-observer.md` document the four overlays,
  `docs/v4-architecture.md` records the V4-14 seam, and README plus
  `docs/regions-migration.md`, `docs/organizations.md`,
  `docs/social-communication.md`, and `docs/borders-and-claims.md` link the
  contract. `.ai-factory/ARCHITECTURE.md` moves its baseline through V4-14 and
  `.ai-factory/DESCRIPTION.md` records the V4-14 project state.
