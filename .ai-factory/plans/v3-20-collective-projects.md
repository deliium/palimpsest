# Implementation Plan: V3-20 Collective Projects

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-13
Improved: 2026-10-13 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M7 — V3 Generational Civilization"
Rationale: Adds an opt-in WorldEngine project that several agents can advance over many ticks, with contribution provenance and no assigned leader, so later civilization work can study shared physical work while `institutional_economy` stays unowned.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M7 — V3 Generational Civilization
INFO [aif-plan] mode=ultra treated as full (richer plan); remaining args describe the feature
INFO [aif-plan] resolved plan file: .ai-factory/plans/v3-20-collective-projects.md (format=slug)
INFO [aif-plan] plan name prefix v3- applied per user request; suggested stem `v3-20-collective-projects`; git.create_branches=false so stem is description slug (branch-derived naming disabled)
INFO [aif-plan] RESEARCH.md absent; research_influenced_plan=false
INFO [aif-plan] plan_default_milestone=auto would surface M6 first; scope is explicitly v3-20 under M7 so linkage uses M7
INFO [aif-plan] skill-context `.ai-factory/skill-context/aif-plan/SKILL.md` absent; no project override applied
INFO [aif-improve] refined 2026-10-13: codec v17 joins every v16 membership set; profile agreement is guarded when projects are on; start and contribute read the working batch; winter start codes avoid the hunger substring; empty project observations omit the key; completion arms clamp the skill draw to 1

## Compatibility contract

This plan adds optional multi-agent, multi-tick physical work. It does **not** install a crew, a firm, or a leader, and it does **not** own `institutional_economy`.

1. V1/V2 invariants intact. `WorldEngine` remains the only objective mutation authority. Agents receive immutable per-agent `Observation` / `Perspective` only. `WorldEvent` records remain immutable and append-only. Subjective numbers stay outside the objective fold. Godot remains read-only. Deterministic replay continues. No scripted `project_succeeds` / `crew_forms` / `leader_assigned` / `institution_formed` outcomes.
2. Flag ownership unchanged: keep `cultural_historical_memory`, `generational_population`, and `kinship_inheritance` owned. Do **not** own `multi_polity_migration`, `institutional_economy`, or `multi_hop_testimony_tracking`. **No new V3 capability flag.**
3. Channel off = v3-19 baseline. With `collective_projects` absent, `Harvest` / `Craft` / `Build` / `Repair` / `Store` and the six-recipe `example_production_catalog()` behave as they do today. `ProductionJob` stays single-actor. `KnowledgeRepository` is unchanged. No project object on the observation, no new metric rows. `exact_trajectory_hash` for existing experiments stays the same.
4. Schema bumps use accepted-set + exact key-set discipline. Never drop accepted V1/V2/V3 versions in the same change that adds a write version.
5. **No leader object (locked).** Forbidden config and code aliases: `leader`, `leader_id`, `project_leader`, `foreman`, `chief`, `manager`, `coordinator_id`, `crew_boss`, `institution`, `work_crew`. None of those strings may be a config key, a metric value key, a project field, or an observation field. `created_by` is also forbidden as a stored role. The creating actor is only the `actor_id` on `ProjectCreated` and the first row in the contribution tail.
6. **The word `archive` is not a project kind (locked).** Repository isolation already rejects `archive`, `library`, `library_institution`, and `global_archive`. The example "build archive infrastructure" is the closed kind `record_site`: a physical structure only. Completion does **not** call `EstablishRepository` and does **not** write `founder_ids`.
7. **Existing production stays single-actor (locked).** Do not add an eighth recipe. Do not put contributors on `ProductionJob`. Do not change `MINIMUM_PRODUCTION_DURATION` or the six locked recipes. A collective shelter is not `build_shelter`.
8. **No single-threshold declaration (locked).** Metric documents expose counts and integer numerators/denominators. They do not contain a boolean, a `SupportBand`, or a label that the world has formed a crew. Do **not** add a `PhenomenonId`. Do **not** map the new families in `phenomenon_specifications._MAPPINGS`.
9. **Preserve v3-02–v3-19 locks:** reservations stay private; no currency; commitments stay unenforced; corpse custody is possession, not law; no global Culture / LibraryInstitution / `GlobalTechniqueRegistry`; a successful experiment is not knowledge; LLM drafts cannot name physics.

## Goal

Agents can already harvest, craft a tool across two ticks, and raise a shelter or a store in one command. Those jobs name one actor. This plan adds a world-owned work site that stays open across ticks. Any living agent at that location may spend their own action, and sometimes a held item, to move it forward. The engine records who contributed. It completes the physical result only when labor and materials both meet the closed catalog. It abandons the site when accepted work stops. It never chooses someone to be in charge.

The five examples are closed kinds, not free-text goals:

| Example | Kind token | Physical result |
| --- | --- | --- |
| build shared shelter | `shared_shelter` | `StructureKind.SHELTER` |
| construct bridge | `bridge` | new `StructureKind.BRIDGE` |
| create storage | `storage` | `StructureKind.STORE` with `stored_quantity` 0 |
| prepare winter reserve | `winter_reserve` | add 3 to an existing store's `stored_quantity` |
| build archive infrastructure | `record_site` | new `StructureKind.RECORD_SITE` |

`winter` is a name in the catalog. This plan does not add a season clock. `BRIDGE` does not add a map edge. `RECORD_SITE` does not store artifacts.

## Design Decisions

### Invariant freeze (non-negotiable)

1. `WorldEngine` does not read private goals, valuations, or acceptance memory when it admits `StartCollectiveProject` or `ContributeCollectiveProject`.
2. Agents never receive another agent's goal board. Contribution provenance on the project is objective, like a kinship edge, and is visible only through perception of that site.
3. Research rows must not bias live cognition. `src/agents` does not import `src/analysis`.
4. Godot remains read-only. No leader badge and no crew chrome.
5. Runs remain reproducible. The new draw uses an explicit purpose and only runs when the channel is on and the attempt is otherwise legal.
6. A completed project is a structure or a store increment. It is not an institution and it does not grant access, rank, or a claim.
7. High metric counts stay in the research document. They do not flip a world flag.

### Scope split (locked)

| This plan (v3-20) | Deferred |
| --- | --- |
| World-owned `CollectiveProject` with a closed five-kind catalog | A recipe language, a technology tree, or player-authored projects |
| Two commands: start and contribute | An abandon command, a vote, or a leader transfer |
| Idle abandonment and a shortage event | Refunds, wages, or partial structure salvage |
| Bounded contribution tail on the project | A SQL contributor table |
| Private goal code `collective_project:<project_id>` via existing `ACHIEVE_CODE` | A shared goal type or a `GOAL_MODEL_VERSION` bump |
| `runner-config-v42`, replay 19, codec `v17` while the channel is on | Alembic `0018+`, `/v2` HTTP, protocol rename, owning `institutional_economy` |

**Rationale:** v3-19 can show that a good was traded onward. It cannot show three agents spending several ticks and several items on one shelter. Putting that state on `WorldEngine` keeps the result objective. Leaving the decision to contribute in cognition keeps coordination from becoming a script.

### Capability / ownership (locked)

1. **No new V3 flag.** Enabling the channel requires exact `collective_projects` on `runner-config-v42`. Kinship, cultural memory, population lifecycle, production, repositories, commitments, valuation, and `resource_exchange_profile` are optional neighbors, not prerequisites.
2. **Do not** enable the channel implicitly when production, repositories, or valuation are on.
3. **v41 without `collective_projects`** stays valid. Schema `v42` always requires `collective_projects`. It does **not** require `subjective_valuation` or `resource_exchange_profile`.
4. Do **not** implement institutions, currency, kinship knowledge handoff, or cultural inheritance handoff.
5. Other unowned V3 flags still fail closed.
6. When the object is absent: behavior and hashes match the v3-19 channel for the same roster and seeds.
7. The world rule context carries only `collective_projects_active`. It does not carry private goals. The idle limit is read from the spec at bind time and stored on the engine, not on each agent.

### Flag × object gate matrix (locked)

| Config shape | Allowed? | Reject / notes |
| --- | --- | --- |
| Object absent, schema v4–v41 | Yes (off) | Passthrough |
| Object present, schema ≠ v42 | No | `collective_projects_requires_v42` |
| Schema v42 without the object | No | `v42_requires_collective_projects` |
| Object present, any V3 flag off | Yes | No flag is required |
| Any forbidden leader or institution alias | No | `collective_projects_leader_forbidden` |
| Kind token `archive` or `library` inside the object | No | `collective_projects_leader_forbidden` |
| `mode=disabled` present | No | `collective_projects_mode_invalid` — omit the object for off |
| Unowned V3 flag true | No | existing `capability_unimplemented` |

### Runner schema (locked)

Introduce `RUNNER_SCHEMA_VERSION_V42 = "runner-config-v42"`:

- Exact root key set = the v41 family with optional objects omitted when absent, plus required sibling **`collective_projects`**. `subjective_valuation` and `resource_exchange_profile` stay optional on v42.
- `collective_projects` present ⇒ `schema_version == runner-config-v42`.
- Decode v23–v41 synthesizes `collective_projects=None`.
- Gate rewrite: allowlists that were extended through v41 also accept v42. Do not require the new object for those channels.
- Default write stays `runner-config-v4` when all V3 flags are off and the new object is absent.
- **Write pair:** when the channel is active, `checkpoint_schema_for_production` returns `(EVENT_SCHEMA_REPLAY_V19, "v17")`, higher priority than `resource_exchange_profile_active` `(18, "v16")`. Channel off does not select `v17` or replay 19. Add keyword `collective_projects_active: bool = False`.
- **Agreement chain:** `select_checkpoint_schema` lives only in `src/simulation/engine.py` (three call sites). It checks the collective-projects clause first and agrees `(19, "v17")`. The profile disagreement warning and the profile agreement clause both require `not collective_projects_active`; profile-without-projects still agrees `(18, "v16")`. `runner.py` and `service.py` call `checkpoint_schema_for_production`, not `select_checkpoint_schema`. Pass the new keyword into those calls and into the three engine call sites. Bind it the same way `_bind_resource_exchange_profile_channel` binds the previous channel.
- **Loop kwargs:** `_collective_projects_loop_kwargs` in `src/simulation/runner.py` passes `collective_projects_active` into `CognitiveLoop`.
- **Matrix finalize (Task 9 only):** in `src/experiments/matrix_schema.py`, insert `collective_projects_on` immediately before `resource_exchange_profile_on`. Task 1 must **not** edit finalize priority.
- Alembic head stays `0017`. Protocol id stays `observer-protocol-v1`. Command count becomes **40**. Semantic tuple count becomes **66**.

### Serialization contract (locked)

Mirror the v41 helper pattern in `runner_serialization.py`:

- v42 root keys = v41 family helper ∪ `{collective_projects}` minus optional objects that are absent
- Exact child keyset `_COLLECTIVE_PROJECTS_KEYS`
- `_encode_collective_projects` / `_decode_collective_projects` with `_require_keys`
- Encode: `schema_version == V42` requires the object
- Decode: v23–v41 → `None`
- DEBUG log `present`, `policy_id`, `idle_ticks` on decode
- Reject forbidden leader aliases before key acceptance

Codec `v17` is a superset of codec `v16`. It adds `collective_projects` on the world snapshot. Codecs through `v16` omit that key and reject it if present. Every membership set that already includes `"v16"` also includes `"v17"`, in `src/simulation/runner.py`, `src/simulation/journal.py`, `src/simulation/serialization.py`, and `src/simulation/service.py`, so structures, jobs, hazards, artifacts, custody, and exchange offers still ride along. Add a `codec_version == "v17"` branch for the `collective_projects` rows in `runner.py` and `service.py`. Do not widen older service sets that never listed `v16`. `collective_projects` stays v17-only.

New `StructureKind` values `bridge` and `record_site` may appear only in codec `v17` snapshots. Older codecs reject those kind strings.

### `CollectiveProjectsSpec` (locked)

Root sibling object; omit for off. Exact keys (reject extras / missing):

| Key | Type / values | Role |
| --- | --- | --- |
| `policy_id` | `collective-projects-v1` only | Closed policy id |
| `idle_ticks` | int, `1..64` | Accepted-work gap after which an open project becomes abandoned |

No leader id, no wage, no success mandate, no per-kind override. Labor and material counts live in the code catalog so a config file cannot shrink a bridge to one tick.

### Runtime channel flags (locked)

1. `collective_projects_active = config.collective_projects is not None` at run start.
2. `evaluate_operation` receives `CollectiveProjectsRuleContext` only when the flag is on. The context holds `active: bool` and `idle_ticks: int`. It holds no goal ids.
3. Channel off: both new commands fail `RuleReason.COLLECTIVE_PROJECTS_CHANNEL_OFF` before any mutation. Existing commands do not consult the context.

### Catalog (locked)

Module `src/world/collective_projects.py`. Pure data. Not a `ProductionRecipe`.

| Kind | Labor | Material | Count | Skill domain | Start rejected when | Completion writes |
| --- | --- | --- | --- | --- | --- | --- |
| `shared_shelter` | 3 | held `ItemKind.MATERIAL` named `wood` | 2 | `BUILDING` | a `SHELTER` is already at the location (`shelter_already_present`) | `Structure` `SHELTER`, integrity `1.0`, `stored_quantity` 0 |
| `bridge` | 4 | held `ItemKind.MATERIAL` named `stone` | 2 | `BUILDING` | a `BRIDGE` is already at the location | `Structure` `BRIDGE`, integrity `1.0`, `stored_quantity` 0 |
| `storage` | 2 | held `ItemKind.MATERIAL` named `wood` | 1 | `BUILDING` | a `STORE` is already at the location (`store_already_present`) | `Structure` `STORE`, integrity `1.0`, `stored_quantity` 0 |
| `winter_reserve` | 2 | held `ItemKind.FOOD` | 3 | `FORAGING` | no `STORE` at the location (`collective_project_store_required`) | add `3` to the pinned store's `stored_quantity` |
| `record_site` | 3 | held `ItemKind.MATERIAL` named `wood` | 2 | `BUILDING` | a `RECORD_SITE` is already at the location | `Structure` `RECORD_SITE`, integrity `1.0`, `stored_quantity` 0 |

Item names are exact display names already used by production (`wood`, `stone`). Do not parse names for meaning beyond that equality. `FOOD` matches on kind only.

`WorldState` gains `collective_projects` (id → project). Cap **32** projects in the snapshot, counting open and terminal. The 33rd start fails `collective_project_cap`. At most **one** `OPEN` project per location (`collective_project_location_busy`). Terminal projects do not block a later start. Do not drop terminal rows to make room.

### Project record (locked)

`CollectiveProject` fields:

| Field | Rule |
| --- | --- |
| `project_id` | `EntityId`, minted by the engine |
| `location_id` | actor location at start |
| `kind` | closed enum above |
| `status` | `open`, `completed`, `abandoned` |
| `labor_done` / `labor_required` | ints, `labor_done <= labor_required` |
| `materials_done` / `materials_required` | ints, same bound |
| `opened_tick` | tick of creation |
| `last_accepted_tick` | creation tick, then each accepted contribution |
| `shortage_count` | `0..64` |
| `target_structure_id` | set only for `winter_reserve`: the `STORE` at the location with the lowest `entity_id` at start. Absent for the other kinds |
| `contributions` | tuple, newest at the end, cap **32** |

There is no `leader_id`, `founder_id`, `created_by`, or `owner_id` field.

Each `ProjectContribution` row: `actor_id`, `tick`, `accepted` (bool), `labor_delta` (`0` or `1`), `item_id` (`EntityId` or absent). Order is engine resolution order. A second contribution by the same actor on a later tick appends another row. The tail drops the oldest row past 32. Dropped rows remain in the event log.

### Commands and admission (locked)

`AgentCommand` gains:

- `StartCollectiveProject` with `kind` only. The actor does not name an id. The engine mints `project_id`.
- `ContributeCollectiveProject` with `project_id` and optional `item_id`.

Reject before mutation:

| Condition | Reason |
| --- | --- |
| Channel off | `collective_projects_channel_off` |
| Dead actor | `dead_actor` |
| Actor has a `ProductionJob` | `actor_busy` |
| Start or contribute away from the project location | `not_at_location` |
| Unknown project, or status is not `open` | `unknown_collective_project` |
| Second open project at the location, or 33rd project | `collective_project_location_busy` / `collective_project_cap` |
| Kind start precondition in the catalog table | the reason named there |
| `item_id` present but not held, or wrong kind/name | `not_held` / `wrong_kind` |

**Material versus labor.** While `materials_done < materials_required`, a legal contribution must name one matching held item. A contribute with no item in that state does not add labor. It increments `shortage_count` (clamp 64), emits `ProjectShortage`, and does not move `last_accepted_tick`. While materials are satisfied, a contribution with no item is a labor attempt. An extra matching item after materials are full is `wrong_kind` and does not mutate the project.

**Skill.** When the attempt is structurally legal (including a real held item if one is required), draw `collective_project_success` from the same seeded RNG table as `production_success`, using `adjusted_production_probability` for that row's `SkillDomain` and the actor's objective skill level. Base probability is `0.70` for every kind. Skip the draw when the adjusted chance is `1.0`, matching production. Default gain `0.50` reaches that clamp at skill level `1`. A miss emits `ProjectContributed` with `accepted=false`, consumes nothing, and does not add labor. A hit consumes the named item into the project (it leaves the holder and is not stored as a world `Item`), adds `1` material if an item was required, and adds `1` labor. Both counters clamp at their required values. If no skill ledger is bound, use the base probability, matching production. A shortage rejection happens before the draw.

**Same-tick batch.** The opening rule and `apply_operation` both read the working state, the same way `NegotiateExchange` does. A start earlier in the tick is visible to a later contribute. A material slot filled by an earlier contribute is no longer open for a later one. Same-tick contributes still follow the existing ordinal. Each actor still has only one command.

### Progress, completion, abandonment (locked)

Progress is the pair `(labor_done, materials_done)` on the project. It is not a second command.

Completion runs in the same resolution as the accepted contribution that makes both counters equal their required values. Event order for that actor: `ProjectContributed` (`accepted=true`), then `ProjectCompleted`. Status becomes `completed`. Shelter, bridge, storage, and record-site completion insert the structure at the project location. Winter-reserve completion adds `3` to `target_structure_id`. If that store was removed before completion, completion still closes the project and emits `ProjectCompleted` with `structure_id` absent and `stored_delta=0` (the food stays consumed). Do not emit `StructureBuilt` or `ItemStored`. Those stay on the single-actor production path.

Abandonment runs at end of tick, after admitted commands and after due `ProductionJob` completion. Each `open` project with `tick - last_accepted_tick >= idle_ticks` becomes `abandoned` and emits `ProjectAbandoned`. Shortage ticks do not refresh `last_accepted_tick`. No structure is created. Consumed items are not returned.

Death does not delete the project or rewrite past rows. A dead actor's later command is `dead_actor`.

### Perception (locked)

When location content is visible, the observation gains `collective_projects`: zero or more `ObservedCollectiveProject` rows for sites at that location, sorted by `project_id`. Fields mirror the project except the contribution tail is included (the same capped tuple). Channel off, or a hidden location, yields an empty tuple. `_encode_observation` omits the key when the tuple is empty, matching `repositories`, so channel-off observation JSON stays the v3-19 shape. Do not put the rows on `ObservedStructure`. Structures appear only after completion, through the existing structure list.

Each project event carries an `OccurrenceContext`. Public facts are `project_id`, `kind`, `labor_done`, `materials_done`, and `status`. Perception projects those occurrences when the channel is on and the audience is local. Channel off never emits them.

### Goals and planning (locked)

Do not add a `GoalOutcomeKind`. Do not bump `GOAL_MODEL_VERSION` (stays `3`). Goals stay owner-scoped.

When the channel is on, `HierarchicalGoalManager.manage` may append one private `CURRENT_INTENTION` goal per visible open project, outside `_TEMPLATE_REGISTRY`, with `parent_goal_id` absent, outcome `ACHIEVE_CODE`, and `outcome_code` `collective_project:<project_id>`. Cap one such goal per observed project. `_hunger_linked` treats an outcome code containing `food`, `hunger`, or `reserve` as a hunger goal, so start codes use `collective_project:start:shared_shelter`, `bridge`, `storage`, `winter_store`, or `record_site`. `winter_store` maps to world kind `winter_reserve` and is the only start code for that kind. The world kind string stays `winter_reserve`. Tests may seed either a contribute code or a start code. The manager does not mint a start code from drives, so the engine does not spontaneously found works. If eight `CURRENT_INTENTION` foci already exist (`_MAX_FOCI`), skip the new mint and log `collective_project_goal_skipped reason=foci_cap`. Do not evict an existing focus.

`propose_collective_project_command` runs in the same post-compile slot as the exchange proposer, only when `collective_projects_active` is true:

- Focus code `collective_project:start:<token>`, actor at a location that can legally start the mapped kind, and the actor holds the first required item → `StartCollectiveProject`.
- Focus code `collective_project:<project_id>`, that project is visible and `open`, and the actor can legally contribute labor or the next item → `ContributeCollectiveProject`.
- Otherwise leave the compiled command unchanged.
- Channel off never calls the proposer. A focus code is not written into the world.

Deliberation adds selection code `collective_project_focus` when a focus code matches a visible open project or a legal start. It does not add an `ActionDirection`. It does not rank agents or pick a partner to command.

### Observer (locked)

New semantic types, in this order, appended to `SEMANTIC_EVENT_TYPES`:

| Event detail | Semantic type |
| --- | --- |
| `ProjectCreated` | `PROJECT_CREATED` |
| `ProjectContributed` | `PROJECT_CONTRIBUTED` |
| `ProjectShortage` | `PROJECT_SHORTAGE` |
| `ProjectAbandoned` | `PROJECT_ABANDONED` |
| `ProjectCompleted` | `PROJECT_COMPLETED` |

`ProjectCreated` carries `project_id`, `location_id`, `kind`, `actor_id`, `labor_required`, `materials_required`. `ProjectContributed` carries `project_id`, `actor_id`, `accepted`, `labor_done`, `materials_done`, and `item_id` when an item was consumed. `ProjectShortage` carries `project_id`, `actor_id`, `shortage_count`. `ProjectAbandoned` carries `project_id` and `idle_ticks`. `ProjectCompleted` carries `project_id`, `kind`, optional `structure_id`, and `stored_delta` (`0` or `3`).

These details are legal only on `EVENT_SCHEMA_REPLAY_V19`.

The observer scene gains `collective_projects` (default empty): `project_id`, `location_id`, `kind`, `status`, `labor_done`, `labor_required`, `materials_done`, `materials_required`, `contributor_ids` sorted by first accepted tick then id. No leader field. If `clients/godot-observer` rejects unknown scene keys, tolerate this array and do not draw a leader glyph. If the client already ignores unknown keys, leave the client unchanged.

### Metrics (locked)

Three families, analysis-only, assembled only when the spec object is present:

| Family | Counts |
| --- | --- |
| `collective_project_progress` | per kind: `labor_done`, `labor_required`, `materials_done`, `materials_required` summed across projects |
| `collective_project_contribution` | `distinct_contributor_count`, `accepted_contribution_count`, `shortage_count` |
| `collective_project_outcome` | `completed_count`, `abandoned_count`, `open_count` |

`METRIC_FAMILY_COUNT` goes from **83** to **86**. Catalog version string stays `metric-catalog-v1`. Empty case when the object is absent: `availability=absent; no_collective_projects`.

### Experiment AW (locked)

`experiment_aw_collective_projects`, `experiment_id="collective_projects@1"`, off the V1 gate, schema `runner-config-v42` on the on-arms.

| Arm | What it shows |
| --- | --- |
| `aw-channel-off` | v41 config, object absent, no project events, hash matches a v3-19 production scene |
| `aw-single-contributor` | one agent, seeded start focus `collective_project:start:shared_shelter`, `BUILDING` skill level at least `1` so the `0.70` base clamps to `1.0` and the draw is skipped, enough wood, three accepted labor ticks, `completed_count == 1`, `distinct_contributor_count == 1` |
| `aw-two-contributors` | two colocated agents, each with `BUILDING` level at least `1`, contribute to one `storage` project; both ids appear in the tail; neither field is a leader |
| `aw-shortage` | contribute without the required item; `shortage_count >= 1`; status stays `open`; no structure; no `collective_project_success` draw |
| `aw-abandoned` | one accepted contribution from an actor at skill level at least `1`, then `idle_ticks` pass with no accepted work; status `abandoned`; items stay consumed |

Scripted arms may submit commands directly. They must not set a leader field.

## Commit Plan

- **Commit 1** (after tasks 1–3): `feat: add a world-owned multi-tick project without a leader`
- **Commit 2** (after tasks 4–6): `feat: record project progress, shortage, and abandonment`
- **Commit 3** (after tasks 7–9): `feat: let agents choose to contribute to a shared project`
- **Commit 4** (after task 10): `docs: describe collective projects and the v42 contract`

## Tasks

### Phase 1: Channel and world state

- [x] Task 1: Add `RUNNER_SCHEMA_VERSION_V42`, `CollectiveProjectsSpec`, exact encode/decode, and the flag×object reject codes.

  Deliver `runner-config-v42` in `src/simulation/runner_models.py` and the v42 helpers in `src/simulation/runner_serialization.py`. Exact child keys are `policy_id` (`collective-projects-v1`) and `idle_ticks` (`1..64`). v42 requires `collective_projects` and does not require `subjective_valuation` or `resource_exchange_profile`. v23–v41 decode the new object as `None`. v41 with only the exchange objects stays valid. Reject forbidden leader and institution aliases, including the tokens `archive` and `library`, with `collective_projects_leader_forbidden` before key acceptance. Extend the v41 allowlists through v42 without requiring the new object. Do not edit `matrix_schema.py` in this task. Do not add a V3 flag.

  LOGGING REQUIREMENTS:
  - DEBUG on decode: `present`, `policy_id`, `idle_ticks`
  - INFO when a config is rejected, including the stable reason code
  - ERROR with the schema version when encode is missing the required object
  - Logger name `simulation.runner_serialization`
  - Levels follow the process log config; no code edit is required to quiet production

  Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `tests/unit/test_runner_config_v42.py`

- [x] Task 2: Add the collective-project catalog, `CollectiveProject`, and the `WorldState` slot. (depends on 1)

  Add `src/world/collective_projects.py` with the five-kind catalog, status enum, contribution row, optional `target_structure_id`, and the cap of 32 projects and 32 contribution rows. Add `StructureKind.BRIDGE` and `StructureKind.RECORD_SITE` without changing shelter or store construction in `src/world/production.py`. Thread `collective_projects` through `WorldState` / `rebuild_world_state` the same way `production_jobs` is threaded. The project type has no leader, founder, or owner field. A unit test constructs one project of each kind and asserts the required labor and material counts. `target_structure_id` is absent until a `winter_reserve` start pins it in Task 4.

  LOGGING REQUIREMENTS:
  - DEBUG `collective_project_defined kind=… labor_required=… materials_required=…`
  - ERROR `collective_project_validation_failed field=… reason_code=…` on a bad row
  - Logger name `world.collective_projects`
  - Do not log item display names beyond the closed catalog tokens

  Files: `src/world/collective_projects.py`, `src/world/production.py`, `src/world/_state.py`, `tests/unit/test_collective_project_catalog.py`

- [x] Task 3: Admit `StartCollectiveProject` and `ContributeCollectiveProject`, including shortage and the skill draw. (depends on 2)

  Add both commands in `src/world/actions.py` and the matching operations, rules, and transitions. The opening rule and `apply_operation` both read the working batch state, as `NegotiateExchange` does. Enforce the rejection table, the one-open-project-per-location rule, the material-before-extra-labor rule, and item consumption only on an accepted hit. One `resolve_tick` test starts a project and contributes in that same tick. Another submits two material contributes when only one item is still required; the later command does not consume a second item. Draw `collective_project_success` in `src/simulation/engine.py` beside `production_success`, purpose string `collective_project_success` in `src/simulation/actions.py`, only after the attempt is structurally legal and only when the channel is on. Base probability `0.70`. Skip the draw when `adjusted_production_probability` is `1.0`. Use `SkillDomain.BUILDING` or `SkillDomain.FORAGING` from the catalog. A no-item shortage rejects before the draw. Channel off rejects both commands with `collective_projects_channel_off` and does not draw. Do not mark the actor `actor_busy` after a contribution; only an existing `ProductionJob` does that. Command count becomes 40. Update every existing `== 38` command pin in the same change, including `COMMAND_RULE_MATRIX` in `tests/unit/test_world_rules.py` and `_CLOSED_COMMAND_TYPES`. Keep the six production recipes unchanged.

  LOGGING REQUIREMENTS:
  - DEBUG `[FIX] collective_project_rule_state` with the actor and whether the rule read the working batch
  - DEBUG `collective_project_admitted action=… project_id=… actor_id=…`
  - DEBUG `collective_project_rejected reason=…` with the `RuleReason` value
  - DEBUG `collective_project_success_draw tick=… ordinal=… success=…` when a draw happens
  - INFO `collective_project_shortage project_id=… shortage_count=…` when a no-item contribute hits an unmet material count
  - Logger names `world._rules` and `simulation.engine`

  Files: `src/world/actions.py`, `src/world/_operations.py`, `src/world/_rules.py`, `src/world/_transitions.py`, `src/simulation/actions.py`, `src/simulation/engine.py`, `tests/unit/test_collective_project_commands.py`

### Phase 2: Outcomes, history, and observation

- [x] Task 4: Complete and abandon projects inside the tick. (depends on 3)

  On the accepted contribution that fills both counters, set status `completed` and write the catalog result in that same resolution. Shelter, bridge, storage, and record-site insert a structure. For `winter_reserve`, pin `target_structure_id` at start to the `STORE` at that location with the lowest `entity_id`, and add 3 to that store's `stored_quantity` when it is still there. Do not emit `StructureBuilt` or `ItemStored`. At end of tick, after due production jobs, abandon each open project whose `tick - last_accepted_tick >= idle_ticks`. Shortage does not refresh that tick. Consumed items are not refunded. A unit test covers single-agent shelter completion, two agents on one storage project in one tick, shortage leaving status open, abandonment after a quiet gap, and a winter reserve that credits the lowest store id when two stores are present.

  LOGGING REQUIREMENTS:
  - INFO `collective_project_completed project_id=… kind=… structure_id=…`
  - INFO `collective_project_abandoned project_id=… idle_ticks=…`
  - DEBUG `collective_project_progress project_id=… labor_done=… materials_done=…`
  - Logger name `world.collective_projects`

  Files: `src/world/collective_projects.py`, `src/world/_transitions.py`, `src/simulation/engine.py`, `tests/unit/test_collective_project_lifecycle.py`

- [x] Task 5: Add replay 19, codec `v17`, the five project events, and observer semantics. (depends on 4)

  Add `EVENT_SCHEMA_REPLAY_V19` and the five detail types in `src/world/events.py`, legal only on that schema. Each event carries an `OccurrenceContext`. Public facts are `project_id`, `kind`, `labor_done`, `materials_done`, and `status`. Fold them in `src/world/_replay.py` so a replay rebuilds status, counters, `target_structure_id`, the capped contribution tail, structures, and store quantity. `checkpoint_schema_for_production` returns `(19, "v17")` only when `collective_projects_active` is true, ahead of `(18, "v16")`. Codec `v17` stores `collective_projects` and may store `bridge` and `record_site`. `select_checkpoint_schema` is only in `src/simulation/engine.py`; its three call sites agree `(19, "v17")` first. Guard the profile disagreement warning and the profile agreement clause with `not collective_projects_active`. `runner.py` and `service.py` call `checkpoint_schema_for_production`; pass the keyword there too. Every membership set that already includes `"v16"` also includes `"v17"` in `runner.py`, `journal.py`, `serialization.py`, and `service.py`. Add the `collective_projects` snapshot rows only when `codec_version == "v17"`. Bind the engine flag from the config object. Append the five semantic types in `src/observer/version.py` (count **66**) and map them in `src/observer/adapt.py`. Update every existing `== 61` semantic pin in the same change. Add `collective_projects` to the observer scene in `src/observer/contracts.py` and `src/observer/project.py` with sorted contributor ids and no leader field. Protocol id stays `observer-protocol-v1`. If the Godot scene decoder rejects unknown keys, tolerate the new array and do not render a leader. Alembic head stays `0017`.

  LOGGING REQUIREMENTS:
  - INFO `checkpoint_schema_selected` with `schema_version`, `codec`, and `reason=collective_projects_active`
  - DEBUG when `collective_projects` is encoded or omitted, with project count
  - WARN if a pre-v17 payload contains `collective_projects` or kind `bridge` or `record_site`
  - WARN if `select_checkpoint_schema` is asked for the channel and the agreed pair is not `(19, "v17")`
  - WARN `checkpoint_schema_disagrees` for the profile only when `collective_projects_active` is false
  - DEBUG `observer_event_adapted kind=… semantic_type=…` for each new kind
  - Logger names `simulation.persistence`, `simulation.serialization`, `simulation.engine`, `observer.adapt`

  Files: `src/world/events.py`, `src/world/_replay.py`, `src/simulation/serialization.py`, `src/simulation/persistence.py`, `src/simulation/engine.py`, `src/simulation/runner.py`, `src/simulation/service.py`, `src/simulation/journal.py`, `src/observer/version.py`, `src/observer/adapt.py`, `src/observer/contracts.py`, `src/observer/project.py`, `tests/unit/test_collective_project_replay_schema.py`, `tests/unit/test_collective_project_observer.py`

- [x] Task 6: Project perception onto the colocated observation. (depends on 5)

  Add `ObservedCollectiveProject` in `src/world/observations.py` and fill it from `_perception.py` only when content at the location is visible and the channel is on. Sort by `project_id`. Include the capped contribution tail. Channel off and a hidden location yield an empty tuple. `_encode_observation` omits `collective_projects` when that tuple is empty, matching `repositories`. Project the new occurrences only while the channel is on, using the public facts from Task 5. Do not copy another location's projects. A unit test asserts a distant agent does not see the site, a colocated agent sees counters and both contributor ids, and a channel-off observation encode has no `collective_projects` key.

  LOGGING REQUIREMENTS:
  - DEBUG `collective_projects_perceived location_id=… count=…`
  - DEBUG `collective_projects_hidden reason=content_hidden` when the location is not visible
  - DEBUG `collective_projects_observation_omitted reason=empty` when encode skips the key
  - Logger names `world._perception` and `simulation.serialization`
  - Do not log goal codes or private ledgers

  Files: `src/world/observations.py`, `src/world/_perception.py`, `src/simulation/serialization.py`, `tests/unit/test_collective_project_perception.py`

### Phase 3: Choice, measures, and the experiment

- [x] Task 7: Let a private goal opt the owner into start or contribute. (depends on 6)

  In `src/agents/cognition/goal_manager.py`, when `collective_projects_active` is true, append at most one `CURRENT_INTENTION` goal per visible open project outside `_TEMPLATE_REGISTRY`, with `parent_goal_id` absent, outcome `ACHIEVE_CODE`, and `outcome_code` `collective_project:<project_id>`. If `_MAX_FOCI` (8) is already full, skip that mint and do not evict an existing focus. Accept a seeded start code `collective_project:start:shared_shelter`, `bridge`, `storage`, `winter_store`, or `record_site`. Map `winter_store` to world kind `winter_reserve`. Do not put `food`, `hunger`, or `reserve` in an outcome code. Do not invent start codes from drives. Do not bump `GOAL_MODEL_VERSION`. Add `propose_collective_project_command` and call it from `CommandPlanner` / `CognitiveLoop` only while the flag is on, in the post-compile slot. The proposer emits `StartCollectiveProject` or `ContributeCollectiveProject` only when the focus matches and the attempt would be legal; otherwise it leaves the compiled command. Add deliberation selection code `collective_project_focus` without a new `ActionDirection`. Pass the flag through `_collective_projects_loop_kwargs`. No path writes a leader. A unit test seeds `collective_project:start:winter_store` and asserts `_hunger_linked` stays false for that goal.

  LOGGING REQUIREMENTS:
  - DEBUG `collective_project_goal_minted owner_id=… project_id=…`
  - DEBUG `collective_project_goal_skipped reason=foci_cap owner_id=…`
  - DEBUG `collective_project_command_proposed owner_id=… action=… project_id=…`
  - DEBUG `collective_project_command_skipped reason=…` when the focus does not match a legal act
  - INFO when the loop flag is bound: `collective_projects_active=%s idle_ticks=%s`
  - Logger names `agents.cognition.goal_manager`, `agents.cognition.collective_projects`, `simulation.runner`

  Files: `src/agents/cognition/goal_manager.py`, `src/agents/cognition/collective_projects.py`, `src/agents/cognition/deliberation.py`, `src/agents/cognition/loop.py`, `src/simulation/runner.py`, `tests/unit/test_collective_project_proposer.py`

- [x] Task 8: Add the three analysis families. (depends on 5)

  Add `MetricFamilyId` members and `_BUILDERS` entries so `METRIC_FAMILY_COUNT` is **86**. Update every existing `== 83` metric pin in the same change. Assemble them from `metric_service.py` only when `collective_projects` is present, in `src/analysis/collective_project_metrics.py`. Expose the locked numerators and denominators. Do not add a `PhenomenonId` or a support band. Do not import this module from `src/agents`. Channel off logs the empty case and writes no rows.

  LOGGING REQUIREMENTS:
  - DEBUG `collective_project_metrics_assembled completed=… abandoned=… contributors=…`
  - INFO `collective_project_metrics_empty reason=collective_projects_absent` when the spec is missing
  - Logger name `analysis.collective_project_metrics`
  - Metric logs stay free of observation text and goal descriptions

  Files: `src/analysis/specifications.py`, `src/analysis/collective_project_metrics.py`, `src/analysis/metric_service.py`, `tests/unit/test_collective_project_metrics.py`

- [x] Task 9: Add Experiment AW and the matrix finalize bit. (depends on 7, 8)

  Register `experiment_aw_collective_projects` (`collective_projects@1`) in `src/experiments/catalog.py` and export it from `src/experiments/__init__.py`. Arms: `aw-channel-off`, `aw-single-contributor`, `aw-two-contributors`, `aw-shortage`, `aw-abandoned`, with the assertions in the experiment table. Completion and abandonment arms set the relevant skill level to at least `1` so the `0.70` base clamps to `1.0` and `collective_project_success` is not drawn. The shortage arm must show that no draw happened. Keep the experiment off the V1 gate. In `src/experiments/matrix_schema.py`, insert `collective_projects_on` immediately before `resource_exchange_profile_on`. Add an architecture isolation test that the new modules do not introduce a leader field, do not reference `LibraryInstitution`, and do not let `src/agents` import `src/analysis`.

  LOGGING REQUIREMENTS:
  - INFO `experiment_registered experiment_id=collective_projects@1 arms=5`
  - DEBUG per arm `collective_project_arm arm=… completed=… abandoned=… shortage=…`
  - WARN if an arm payload contains a forbidden leader alias
  - Logger name `experiments.catalog`

  Files: `src/experiments/catalog.py`, `src/experiments/__init__.py`, `src/experiments/matrix_schema.py`, `src/experiments/collectors.py`, `tests/unit/test_experiment_aw.py`, `tests/architecture/test_v3_collective_projects_isolation.py`

### Phase 4: Docs

- [x] Task 10: Update the downstream V3 contract. (depends on 9)

  Update `docs/architecture.md` so the write-pair priority names `(EVENT_SCHEMA_REPLAY_V19, "v17")` only while `collective_projects` is active, command count **40**, semantic count **66**, Experiment AW, and the statement that a contribution tail is not a leader. Update the V3 paragraph in `.ai-factory/DESCRIPTION.md` with the same pins. Do not rename the observer protocol. Do not claim `institutional_economy`.

  LOGGING REQUIREMENTS:
  - No runtime logger. The doc change is the deliverable.
  - Implementation notes for this task stay in the commit message, not in a new log line.

  Files: `docs/architecture.md`, `.ai-factory/DESCRIPTION.md`
