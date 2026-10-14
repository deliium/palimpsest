# Implementation Plan: V3-21 Public Goods

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-14
Improved: 2026-10-14 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M7 — V3 Generational Civilization"
Rationale: Extends the world-owned collective project so a finished well, bridge, store, shelter, or warning post can be used and maintained by anyone present, while contribution and benefit stay measurable and `institutional_economy` stays unowned.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M7 — V3 Generational Civilization
INFO [aif-plan] mode=ultra treated as full (richer plan); remaining args describe the feature
INFO [aif-plan] resolved plan file: .ai-factory/plans/v3-21-public-goods.md (format=slug)
INFO [aif-plan] plan name prefix v3- applied per user request; suggested stem `v3-21-public-goods`; git.create_branches=false so stem is description slug (branch-derived naming disabled)
INFO [aif-plan] RESEARCH.md absent; research_influenced_plan=false
INFO [aif-plan] plan_default_milestone=auto would surface M6 first; scope is explicitly v3-21 under M7 so linkage uses M7
INFO [aif-plan] skill-context `.ai-factory/skill-context/aif-plan/SKILL.md` absent; no project override applied
INFO [aif-improve] refined 2026-10-14: v17 project keys stay exact; decay runs once per structure before the physical step; draw events carry the resulting need; use goals mint only for drawable kinds; inequality folds the event log; AX channel-off checks the v17 pair and the low-use arm draws a winter reserve

## Compatibility contract

This plan adds optional shared benefit, upkeep, and opposition on collective projects. It does **not** install a toll, a wage, a membership test, or a judgment that someone who benefits without contributing is at fault.

1. V1/V2 invariants intact. `WorldEngine` remains the only objective mutation authority. Agents receive immutable per-agent `Observation` / `Perspective` only. `WorldEvent` records remain immutable and append-only. Subjective numbers stay outside the objective fold. Godot remains read-only. Deterministic replay continues. No scripted `public_good_succeeds` / `free_rider_punished` / `access_granted` outcomes.
2. Flag ownership unchanged: keep `cultural_historical_memory`, `generational_population`, and `kinship_inheritance` owned. Do **not** own `multi_polity_migration`, `institutional_economy`, or `multi_hop_testimony_tracking`. **No new V3 capability flag.**
3. Channel off = v3-20 baseline. With `public_goods` absent, start and contribute, the five existing project kinds, shelter bonus, production `Repair` / `Store`, and Experiment AW behave as they do today. No benefit, maintain, or oppose events. `exact_trajectory_hash` for existing experiments stays the same. A production shelter or store that was never the completion target of a collective project is unchanged even when the channel is on.
4. Schema bumps use accepted-set + exact key-set discipline. Never drop accepted V1/V2/V3 versions in the same change that adds a write version.
5. **No moral role (locked).** Forbidden config, metric, project, observation, and command strings: `free_rider`, `freerider`, `free_rider_id`, `cheater`, `selfish`, `guilty`, `fair`, `unfair`, `deserved`, `sanction`, `punish`, `punishment`, `exclude`, `exclusion`, `toll`, `wage`, `membership`. None of those may be a config key, a metric value key, a project field, an observation field, a rule reason, or a command name. Analysis may still expose the family id `public_good_free_rider_pattern` as a count of co-occurring benefits and contributions. That family does not write a role onto an agent.
6. **No access test (locked).** A living agent at the location may receive a non-rival benefit or draw a rival benefit whether or not their id appears in the contribution tail. The engine does not read reputation, norm beliefs, or valuations when it admits use, maintenance, or opposition.
7. **v3-20 leader lock stands.** Forbidden leader and institution aliases from v3-20 stay rejected. `record_site` is not a public good. `BRIDGE` still does not add a map edge. Do not add a production recipe. Do not put contributors on `ProductionJob`.
8. **No single-threshold declaration (locked).** Metric documents expose counts and integer numerators/denominators, plus the existing quantized float policy where a Gini is already the project pattern. They do not contain a boolean, a `SupportBand`, or a label that cooperation succeeded. Do **not** add a `PhenomenonId`. Do **not** map the new families in `phenomenon_specifications._MAPPINGS`.
9. **Preserve v3-02–v3-20 locks:** reservations stay private; no currency; commitments stay unenforced; corpse custody is possession, not law; no global Culture / LibraryInstitution / `GlobalTechniqueRegistry`; a successful experiment is not knowledge; LLM drafts cannot name physics; a contribution tail is not a leader.

## Goal

v3-20 can finish a shelter, a bridge, a store, a winter reserve, or a record site and remember who contributed. It does not record who later receives the benefit, who spends labor keeping the structure up, or who acts against it. This plan adds that layer for goods whose benefit can be shared:

| Example | Kind token | Physical result | Benefit once the site is completed and integrity is above 0 |
| --- | --- | --- | --- |
| well | `well` | new `StructureKind.WELL` | chosen draw: thirst drops by `5.0` |
| bridge | `bridge` | existing `StructureKind.BRIDGE` | presence: fatigue drops by `2.0 * integrity` |
| shared storage | `storage` | existing `StructureKind.STORE` | chosen draw: hunger drops by `5.0` and `stored_quantity` drops by 1 |
| shelter | `shared_shelter` | existing `StructureKind.SHELTER` | presence: the existing shelter term already applies; this plan only records the receipt |
| warning system | `warning_post` | new `StructureKind.WARNING_POST` | presence while a hazard is active: hazard extra damage is scaled by `(1 - 0.5 * integrity)` |

`winter_reserve` does not become its own good. Its pinned store accepts the same rival draw as `storage`. `record_site` stays a structure with no public benefit.

Agents can contribute and draw, contribute and then leave, draw without having contributed, oppose the site, or maintain it. Those are private goals and admitted commands. The world stores the acts. It does not grade them.

## Design Decisions

### Invariant freeze (non-negotiable)

1. `WorldEngine` does not read private goals, valuations, reputation, norm ledgers, or the contribution tail when it admits `UsePublicGood`, `MaintainPublicGood`, or `OpposePublicGood`.
2. Benefit, maintenance, and opposition are objective events. They are visible only through perception of that location.
3. Research rows must not bias live cognition. `src/agents` does not import `src/analysis`.
4. Godot remains read-only. No toll badge and no exclusion chrome.
5. Runs remain reproducible. The maintenance draw uses an explicit purpose and only runs when the channel is on and the attempt is otherwise legal. Use and oppose do not draw.
6. A public good does not grant a claim, a rank, or a right to refuse the next user.
7. High metric counts stay in the research document. They do not flip a world flag and they do not feed back into rules.

### Scope split (locked)

| This plan (v3-21) | Deferred |
| --- | --- |
| Shared benefit, upkeep, and opposition on collective completions | A recipe language, a toll, or a membership roster |
| Two new kinds: `well`, `warning_post` | A map edge for `bridge`, or a season clock |
| Three commands: use, maintain, oppose | A vote, a wage, or a refund of consumed materials |
| Optional integrity decay on linked public structures | Salvage, or decay of production-built structures that no project links |
| Private goal codes for use, maintain, and oppose | A `GOAL_MODEL_VERSION` bump, or an auto-minted oppose goal |
| Reputation and norm updates from witnessed upkeep and opposition | A norm whose violation is "benefited without contributing" |
| Five analysis families, including co-occurrence counts | A `PhenomenonId` or a support band |

**Rationale:** v3-20 already records labor. The missing piece is that a finished shelter helps whoever stands there, a store can be drawn down by someone who never hauled wood, and a later agent can shore the structure up or cut into it. Putting the benefit in the world and the names in analysis keeps the engine from punishing a pattern the researcher still needs to count.

### Capability / ownership (locked)

1. **No new V3 flag.** Enabling the channel requires exact `public_goods` on `runner-config-v43` and a present `collective_projects` object. Kinship, cultural memory, population lifecycle, production, repositories, commitments, valuation, exchange profile, and reputation or norm modes are optional neighbors, not prerequisites.
2. **Do not** enable the channel implicitly when `collective_projects` is on.
3. **v42 without `public_goods`** stays valid. Schema `v43` always requires both `collective_projects` and `public_goods`.
4. Do **not** implement institutions, currency, kinship knowledge handoff, or cultural inheritance handoff.
5. Other unowned V3 flags still fail closed.
6. When the object is absent: behavior and hashes match the v3-20 channel for the same roster and seeds.
7. The world rule context carries `public_goods_active` and `decay_millis`. It does not carry private goals or reputation.

### Flag × object gate matrix (locked)

| Config shape | Allowed? | Reject / notes |
| --- | --- | --- |
| Object absent, schema v4–v42 | Yes (off) | Passthrough |
| Object present, schema ≠ v43 | No | `public_goods_requires_v43` |
| Schema v43 without the object | No | `v43_requires_public_goods` |
| Object present, `collective_projects` absent | No | `public_goods_requires_collective_projects` |
| Object present, any V3 flag off | Yes | No flag is required |
| Any forbidden moral, toll, or leader alias | No | `public_goods_role_forbidden` |
| Kind token `archive` or `library` inside the object | No | `public_goods_role_forbidden` |
| `mode=disabled` present | No | `public_goods_mode_invalid` — omit the object for off |
| Unowned V3 flag true | No | existing `capability_unimplemented` |

### Runner schema (locked)

Introduce `RUNNER_SCHEMA_VERSION_V43 = "runner-config-v43"`:

- Exact root key set = the v42 family with optional objects omitted when absent, plus required siblings **`collective_projects`** and **`public_goods`**.
- `public_goods` present ⇒ `schema_version == runner-config-v43` and `collective_projects` is present.
- Decode v23–v42 synthesizes `public_goods=None`.
- Gate rewrite: allowlists that were extended through v42 also accept v43. Do not require the new object for those channels.
- Default write stays `runner-config-v4` when all V3 flags are off and the new object is absent.
- **Write pair:** when the channel is active, `checkpoint_schema_for_production` returns `(EVENT_SCHEMA_REPLAY_V20, "v18")`, higher priority than `collective_projects_active` `(19, "v17")`. Channel off does not select `v18` or replay 20. Add keyword `public_goods_active: bool = False`.
- **Agreement chain:** `select_checkpoint_schema` lives only in `src/simulation/engine.py`. It checks the public-goods clause first and agrees `(20, "v18")`. The collective-projects agreement clause requires `not public_goods_active`. Profile clauses keep the v3-20 guard. `runner.py` and `service.py` call `checkpoint_schema_for_production`. Pass the new keyword into those calls and into the engine call sites. Bind it the same way `_bind_collective_projects_channel` binds the previous channel.
- **Loop kwargs:** `_public_goods_loop_kwargs` in `src/simulation/runner.py` passes `public_goods_active` into `CognitiveLoop`.
- **Matrix finalize (Task 9 only):** in `src/experiments/matrix_schema.py`, insert `public_goods_on` immediately before `collective_projects_on`. Task 1 must **not** edit finalize priority.
- Alembic head stays `0017`. Protocol id stays `observer-protocol-v1`. Command count becomes **43**. Semantic tuple count becomes **69**.

### Serialization contract (locked)

Mirror the v42 helper pattern in `runner_serialization.py`:

- v43 root keys = v42 family helper ∪ `{public_goods}` minus optional objects that are absent, and `collective_projects` is required on v43
- Exact child keyset `_PUBLIC_GOODS_KEYS`
- `_encode_public_goods` / `_decode_public_goods` with `_require_keys`
- Encode: `schema_version == V43` requires the object and the collective-projects object
- Decode: v23–v42 → `None`
- DEBUG log `present`, `policy_id`, `decay_millis` on decode
- Reject forbidden moral and leader aliases before key acceptance

Codec `v18` is a superset of codec `v17`. It adds `public_acts` and `linked_structure_id` on each collective project and may store structure kinds `well` and `warning_post`. The v17 encoder in `src/simulation/journal.py` keeps today's exact project key set (`project_id` through `contributions`). Codecs through `v17` omit `public_acts` and `linked_structure_id` and reject either key if present. Every membership set that already includes `"v17"` also includes `"v18"`, in `src/simulation/runner.py`, `src/simulation/journal.py`, `src/simulation/serialization.py`, and `src/simulation/service.py`. Add a `codec_version == "v18"` branch for `public_acts`. Do not widen older service sets that never listed `v17`. `public_acts` stays v18-only. An empty `public_acts` tuple is omitted on encode.

### `PublicGoodsSpec` (locked)

Root sibling object; omit for off. Exact keys (reject extras / missing):

| Key | Type / values | Role |
| --- | --- | --- |
| `policy_id` | `public-goods-v1` only | Closed policy id |
| `decay_millis` | int, `0..250` | Integrity lost per tick on a linked completed structure, in thousandths. `0` leaves integrity unchanged |

No wage, no user list, no success mandate, no per-kind override. Labor, materials, and benefit magnitudes live in code.

### Runtime channel flags (locked)

1. `public_goods_active = config.public_goods is not None` at run start. This implies `collective_projects` is present.
2. `evaluate_operation` receives `PublicGoodsRuleContext` only when the flag is on. The context holds `active: bool` and `decay_millis: int`.
3. Channel off: the three new commands fail `RuleReason.PUBLIC_GOODS_CHANNEL_OFF` before any mutation. `StartCollectiveProject` of `well` or `warning_post` also fails that reason when the channel is off. Existing commands, including start and contribute of the five v3-20 kinds, do not consult the context.

### Catalog additions (locked)

Keep the five v3-20 rows. Add two rows in `src/world/collective_projects.py`. They are not `ProductionRecipe`s.

| Kind | Labor | Material | Count | Skill domain | Start rejected when | Completion writes |
| --- | --- | --- | --- | --- | --- | --- |
| `well` | 3 | held `ItemKind.MATERIAL` named `stone` | 2 | `BUILDING` | a `WELL` is already at the location (`well_already_present`), or the channel is off | `Structure` `WELL`, integrity `1.0`, `stored_quantity` 0 |
| `warning_post` | 2 | held `ItemKind.MATERIAL` named `wood` | 1 | `BUILDING` | a `WARNING_POST` is already at the location (`warning_post_already_present`), or the channel is off | `Structure` `WARNING_POST`, integrity `1.0`, `stored_quantity` 0 |

Start codes use `collective_project:start:well` and `collective_project:start:warning_post`. Do not put `food`, `hunger`, or `reserve` in those codes. The world kind string for the warning example is `warning_post`.

Public kinds, and only these, receive a link at completion:

| Project kind | Linked structure | Rivalry | Benefit code | How the benefit is applied |
| --- | --- | --- | --- | --- |
| `shared_shelter` | the structure just inserted | non-rival | `shelter` | during the physical step, every living body at the location, `source=presence`. The existing shelter term is the body effect. The benefit event is a witness |
| `bridge` | the structure just inserted | non-rival | `span` | during the physical step, after the metabolism fatigue gain and before `NeedsApplied` is built. Fatigue drops by `2.0 * integrity`, floored at `0`, `source=presence`. `NeedsApplied` already stores the resulting fatigue, so replay does not subtract again |
| `storage` | the structure just inserted | rival | `draw` | `UsePublicGood` only. Hunger `-5.0`, `stored_quantity - 1`. No item is minted. The event carries `resulting_hunger` |
| `winter_reserve` | the already pinned `target_structure_id` | rival | `draw` | same draw as `storage` |
| `well` | the structure just inserted | non-rival | `draw` | `UsePublicGood` only. Thirst `-5.0`. No item is minted. One draw per actor per project per tick. The event carries `resulting_thirst` |
| `warning_post` | the structure just inserted | non-rival | `warning` | during the physical step, only while a hazard is active at the location. Scale that location's hazard extra by `(1 - 0.5 * integrity)` before `ExposureApplied` is built. `source=presence`. Replay copies `ExposureApplied` and does not scale again |
| `record_site` | none | — | — | use, maintain, and oppose fail `not_a_public_good` |

Closed constants in `src/world/collective_projects.py`: `PUBLIC_WELL_THIRST_RELIEF = 5.0`, `PUBLIC_STORE_HUNGER_RELIEF = 5.0`, `PUBLIC_BRIDGE_FATIGUE_RELIEF = 2.0`, `WARNING_EXPOSURE_RELIEF_COEFFICIENT = 0.5`. Integrity steps use the existing `REPAIR_INTEGRITY_DELTA` (`0.25`) from `src/world/production.py`. Need writes go through the existing `round_physical` / `clamp_need` path. Integrity writes stay inside `[0, 1]`.

`StructureKind.WELL` and `StructureKind.WARNING_POST` may appear only in codec `v18` snapshots. Older codecs reject those kind strings. Single-actor `Build` cannot produce them.

### Act record (locked)

On `CollectiveProject`, add `public_acts`: a tuple, newest at the end, cap **32**, default `()`. Add `linked_structure_id: EntityId | None = None`. The v17 decoder constructs projects without passing either field. Dropped act rows remain in the event log. v17 snapshots omit both fields.

Each `PublicGoodAct` row: `actor_id`, `tick`, `act` (`benefit`, `draw`, `maintain`, `oppose`), `source` (`presence` or `command`). There is no role field.

A completed public project also stores `linked_structure_id` once completion inserts or pins the structure. `winter_reserve` reuses `target_structure_id` as that link. Other v3-20 kinds set `linked_structure_id` only when this channel is on; when the channel is off, completion stays the v3-20 write and `linked_structure_id` stays absent. Codec `v17` omits `linked_structure_id`.

### Commands and admission (locked)

`AgentCommand` gains:

- `UsePublicGood` with `project_id`.
- `MaintainPublicGood` with `project_id` and optional `item_id`.
- `OpposePublicGood` with `project_id`.

Reject before mutation:

| Condition | Reason |
| --- | --- |
| Channel off | `public_goods_channel_off` |
| Dead actor | `dead_actor` |
| Actor has a `ProductionJob` | `actor_busy` |
| Actor is away from the project location | `not_at_location` |
| Unknown project | `unknown_collective_project` |
| Kind is `record_site` | `not_a_public_good` |
| Use or maintain while status is not `completed`, or the link is missing | `public_good_not_ready` |
| Use or maintain while linked integrity is `0` | `public_good_inert` |
| Rival draw while `stored_quantity` is `0` | `public_good_empty` |
| Second draw by the same actor on the same project in the same tick | `public_good_already_drawn` |
| Maintain item present but not held, or not the catalog material for that kind | `not_held` / `wrong_kind` |
| Oppose while status is `abandoned` | `unknown_collective_project` |

**Use.** Legal on a completed linked good. Shelter, bridge, and warning posts reject use with `public_good_presence_only` because their benefit is presence, not a draw. Well and storage (including a winter-reserve store) accept use. A draw does not consult the contribution tail.

**Maintain.** Legal on a completed linked good with integrity below `1.0` or equal to `1.0` (a hit at `1.0` still emits the event and clamps). The attempt is structurally legal before the draw. Draw `public_good_maintain` from the same seeded RNG table as `collective_project_success`, using `adjusted_production_probability` for `SkillDomain.BUILDING`. Base probability is `0.70`. Skip the draw when the adjusted chance is `1.0`. A miss emits `PublicGoodMaintained` with `accepted=false` and changes nothing. A hit adds `REPAIR_INTEGRITY_DELTA`, consumes one held item, and appends a `maintain` act. The item follows the linked structure kind: `wood` for `SHELTER`, `STORE`, and `WARNING_POST`; `stone` for `BRIDGE` and `WELL`. A winter-reserve link is a store, so it requires `wood`. If no skill ledger is bound, use the base probability.

**Oppose.** Legal on an `open` or `completed` public project. No item. No draw. On an open project the command appends an `oppose` act and does not change labor, materials, or `last_accepted_tick`. On a completed project it also subtracts `REPAIR_INTEGRITY_DELTA`, floored at `0`, and still does not refresh `last_accepted_tick`. It does not delete history, refund items, or alter the actor's health. One oppose per actor per project per tick; a second fails `public_good_already_opposed`.

**Same-tick batch.** The opening rule and `apply_operation` both read the working state. A completion earlier in the tick is visible to a later use. Two draws against one stored unit: the first succeeds, the second fails `public_good_empty`. Each actor still has only one command.

### Benefit pass, decay, and upkeep (locked)

Tick order in `src/simulation/engine.py` stays: commands, due production jobs, `abandon_idle_projects`, then `apply_autonomous_physical_step`. Decay is inserted after abandonment and before that physical step. Presence benefits are recorded inside the physical step, using the integrity decay just wrote.

1. For each linked structure id, once per tick, if `decay_millis > 0` and integrity `> 0`, subtract `decay_millis / 1000` and clamp at `0`. Two projects that pin the same store decay that store once. Emit no event for the decay itself. Log the new integrity at DEBUG.
2. The physical step then reads that integrity. Shelter keeps the existing shelter term. Bridge relief is applied after the metabolism fatigue gain and before `NeedsApplied` is built. Warning scale is applied to hazard extra before `ExposureApplied` is built. After those writes, emit one `PublicGoodBenefit` per living body at a shelter or bridge whose integrity is still `> 0`, and one per living body at a warning post when a hazard at that location contains the tick.
3. Bodies that are absent receive nothing. A non-contributor who is present receives the same presence benefit as a contributor.
4. Draws stay on `UsePublicGood`. This pass does not repeat them. A draw event stores `resulting_hunger` or `resulting_thirst`. Shelter, span, and warning events do not store a second body delta.

Death does not delete the project, the link, or past acts.

### Perception (locked)

When location content is visible and the channel is on, each observed project includes `public_acts` (the capped tuple) and `linked_structure_id` when present. Channel off omits both keys even if a test fixture left them empty. `_encode_observation` keeps omitting `collective_projects` when the tuple is empty.

New occurrences, projected only while the channel is on, for a local audience:

| Event | Occurrence kind | Public facts |
| --- | --- | --- |
| `PublicGoodBenefit` | `public_good_benefit` | `project_id`, `kind`, `benefit_code`, `source`, and `resulting_hunger` or `resulting_thirst` on a draw |
| `PublicGoodMaintained` | `public_good_maintained` | `project_id`, `kind`, `accepted` |
| `PublicGoodOpposed` | `public_good_opposed` | `project_id`, `kind`, `status` |

When the channel is on, a local `ProjectContributed` occurrence also gains `accepted` and `public_good` (`true` only for a public kind). Channel off does not add those keys, so v3-20 observation JSON for project events stays put.

### Goals and planning (locked)

Do not add a `GoalOutcomeKind`. Do not bump `GOAL_MODEL_VERSION` (stays `3`). Goals stay owner-scoped.

When the channel is on, `HierarchicalGoalManager.manage` may append one private `CURRENT_INTENTION` per visible **completed** `well`, `storage`, or `winter_reserve`, outside `_TEMPLATE_REGISTRY`, with outcome `ACHIEVE_CODE` and `outcome_code` `public_good:use:<project_id>`. Shelter, bridge, and warning post do not mint a use goal. Their receipt is the presence benefit. Cap one such goal per drawable project. If eight `CURRENT_INTENTION` foci already exist, skip the mint and log `public_good_goal_skipped reason=foci_cap`. Do not evict an existing focus. Do not mint oppose or maintain from drives.

Seeded codes the proposer accepts:

- `public_good:use:<project_id>`
- `public_good:maintain:<project_id>`
- `public_good:oppose:<project_id>`

`propose_public_good_command` runs in the same post-compile slot as the collective-project proposer, only when `public_goods_active` is true. It emits `UsePublicGood` only for `well`, `storage`, and `winter_reserve`. A seeded use code on a shelter, bridge, or warning post logs `public_good_command_skipped reason=presence_only` and leaves the compiled command unchanged. Maintain and oppose emit only when the focus matches and the attempt would be legal. The proposer does not read another agent's ledger to deny a draw. Channel off never calls it.

Deliberation adds selection code `public_good_focus` when a focus code matches a visible public project. It does not add an `ActionDirection`. It does not rank agents.

The five researcher-facing patterns are produced by seeds and placement, not by a role enum:

| Pattern | What the arm or seed does |
| --- | --- |
| contribute and use | contribute until completion, remain at the location, use or receive presence |
| contribute but barely use | contribute until completion, then leave before any benefit event |
| do not contribute but use | never contribute; be present for a presence benefit, or submit `UsePublicGood` |
| oppose project | seed `public_good:oppose:<project_id>` or submit `OpposePublicGood` |
| maintain project | seed `public_good:maintain:<project_id>` or submit `MaintainPublicGood` |

### Reputation and norms (locked)

These hooks run only inside the existing owner-scoped updates. Disabled reputation does not call `apply_reputation_update`. Disabled norms do not call `apply_norm_update`. Neither hook reads the analysis families.

**Reputation.** When the occurrence is perceived:

| Kind | Delta row | Condition |
| --- | --- | --- |
| `public_good_maintained` | the existing `help` row | `accepted` is true |
| `public_good_opposed` | the existing `attack` row | always |
| `project_contributed` | the existing `help` row | `accepted` is true and `public_good` is true |
| `public_good_benefit` | none | stay `ignored_kind` |

A missed maintain does not move reputation. A draw does not move reputation. Using a good without contributing does not by itself lower generosity or raise harm.

**Norms.** Add one pattern `NormPattern.SHARED_UPKEEP` with expectation `NormExpectation.MAINTAIN_STRUCTURE`. Conforming evidence is a witnessed accepted `public_good_maintained`. Violation evidence is a witnessed `public_good_opposed`. Benefit and draw occurrences stay `ignored_kind` and are not violations. Do not add a pattern whose violation is benefiting without contributing. Do not wire `NormResponse.ENFORCE` to block `UsePublicGood`, to reduce integrity, or to edit reputation beyond the table above. Existing sanction tokens stay unused by this channel.

### Observer (locked)

New semantic types, appended after `PROJECT_COMPLETED`:

| Event detail | Semantic type |
| --- | --- |
| `PublicGoodBenefit` | `PUBLIC_GOOD_BENEFIT` |
| `PublicGoodMaintained` | `PUBLIC_GOOD_MAINTAINED` |
| `PublicGoodOpposed` | `PUBLIC_GOOD_OPPOSED` |

`PublicGoodBenefit` carries `project_id`, `actor_id`, `kind`, `benefit_code`, `source`, `integrity_millis`, and, for a draw, exactly one of `resulting_hunger` or `resulting_thirst`. `PublicGoodMaintained` carries `project_id`, `actor_id`, `accepted`, and `integrity_millis`. `PublicGoodOpposed` carries `project_id`, `actor_id`, `status`, and `integrity_millis` (`0` when the project is still open). On replay 20, `ProjectCompleted` also carries `decay_millis`. Replay 19 rejects that key.

These details are legal only on `EVENT_SCHEMA_REPLAY_V20`. Replay sets structure integrity from the latest `integrity_millis` on a benefit, maintain, or oppose event. It also applies `decay_millis` from `ProjectCompleted` at the end of the completion tick and at the end of each later tick, once per linked structure id. Shelter, span, and warning benefits do not change bodies in the fold. A draw fold writes the stored resulting need once. Store quantity drops by 1 on a storage draw.

The observer scene's `collective_projects` rows gain `linked_structure_id` (empty when absent) and `public_act_count`. No role field. If the Godot scene decoder rejects unknown keys, tolerate the new fields and do not draw an exclusion glyph.

### Metrics (locked)

Five families, analysis-only, assembled only when the spec object is present. Counts are integers. An actor may appear in more than one pattern count when they both maintain and draw. Do not emit a boolean.

| Family | Counts |
| --- | --- |
| `public_good_contribution_inequality` | `contributor_count`, `recorded_actor_count`, `labor_sum`, `max_labor`, `min_labor` among contributors (`0` when there are none), and `gini_millis` (the resource-inequality Gini over accepted labor of actors named on that project's contribution, benefit, maintain, or oppose events, quantized then stored as millionths). Labor `0` is included only for an actor already on a benefit, maintain, or oppose event. `gini_millis` is `0` when `recorded_actor_count < 2` |
| `public_good_benefit_distribution` | per public kind: `benefit_event_count`, `distinct_beneficiary_count`, `beneficiary_without_labor_count`, `contributor_without_benefit_count` |
| `public_good_maintenance_burden` | `maintain_attempt_count`, `maintain_accepted_count`, `oppose_count`, `decay_tick_count`, `integrity_millis_sum` across linked structures at the window end |
| `public_good_free_rider_pattern` | `contribute_and_use_count` (accepted labor `>= 1` and benefit events `>= 1`), `contribute_low_use_count` (accepted labor `>= 1` and benefit events `<= 1` — the "barely use" count, so a single presence tick still counts as low use), `use_without_contribution_count` (benefit events `>= 1` and accepted labor `0`), `oppose_actor_count`, `maintain_actor_count` |
| `public_good_cooperation_stability` | `completed_public_count`, `open_public_count`, `abandoned_public_count`, `ticks_with_accepted_work`, `ticks_observed`, `longest_quiet_gap` |

`contribute_low_use_count` uses `<= 1` so the named pattern "barely use" includes a contributor who receives one presence tick and then leaves. `contribute_and_use_count` uses `>= 1`, so that same actor is also in the joint count. The document does not collapse the overlap.

The assembler folds `WorldEvent` rows only. It reads the same tuple `MetricComputationInputs.collective_project_events` already carries, plus a new `public_goods_spec` beside `collective_projects_spec`. `src/experiments/collectors.py` passes that spec. There is no per-tick location census. The assembler does not import agent ledgers.

`METRIC_FAMILY_COUNT` goes from **86** to **91**. Catalog version string stays `metric-catalog-v1`. Empty case when the object is absent: `availability=absent; no_public_goods`.

### Experiment AX (locked)

`experiment_ax_public_goods`, `experiment_id="public_goods@1"`, off the V1 gate, schema `runner-config-v43` on the on-arms. `decay_millis` is `0` except on the maintain arm.

| Arm | What it shows |
| --- | --- |
| `ax-channel-off` | v42 config, object absent, one `shared_shelter` completion, checkpoint pair `(19, "v17")`, zero `PublicGood*` events |
| `ax-contribute-and-use` | one contributor finishes `shared_shelter` at skill level at least `1`; a second agent never contributes and stays; both ids appear in shelter benefit events; the second id is in `use_without_contribution_count` |
| `ax-use-without-contribution` | a finished `well`; an agent with no contribution row draws once; thirst drops by `5.0`; no oppose event; reputation is left disabled so the draw alone creates no reputation evidence |
| `ax-contribute-low-use` | a production store starts at quantity `1`. One agent completes `winter_reserve` (`+3`, quantity `4`) and leaves before any draw. A second agent draws once (quantity `3`). The contributor's benefit count is `0`, so that id is in `contribute_low_use_count` and absent from `contribute_and_use_count` |
| `ax-oppose` | open `bridge` project with `idle_ticks` `8`; one `OpposePublicGood`; labor and `last_accepted_tick` stay unchanged; status stays `open`; `oppose_actor_count == 1` |
| `ax-maintain` | completed `warning_post`, `decay_millis=250`, one tick of decay, then one accepted maintain from an actor at `BUILDING` level at least `1` so the draw is skipped; integrity rises by `0.25` from the post-decay value |

Scripted arms may submit commands directly. They must not set a forbidden role field. The low-use arm's contributor must have benefit events `<= 1`.

## Commit Plan

- **Commit 1** (after tasks 1–3): `feat: record shared use of a finished collective project`
- **Commit 2** (after tasks 4–6): `feat: let agents draw, maintain, or oppose a public good`
- **Commit 3** (after tasks 7–9): `feat: count benefit, upkeep, and contribution together`
- **Commit 4** (after task 10): `docs: describe public goods and the v43 contract`

## Tasks

### Phase 1: Channel and shared benefit

- [x] Task 1: Add `RUNNER_SCHEMA_VERSION_V43`, `PublicGoodsSpec`, exact encode/decode, and the flag×object reject codes.

  Deliver `runner-config-v43` in `src/simulation/runner_models.py` and the v43 helpers in `src/simulation/runner_serialization.py`. Exact child keys are `policy_id` (`public-goods-v1`) and `decay_millis` (`0..250`). v43 requires `public_goods` and `collective_projects`. v23–v42 decode the new object as `None`. v42 with only `collective_projects` stays valid. Reject forbidden moral, toll, and leader aliases with `public_goods_role_forbidden` before key acceptance. Extend the v42 allowlists through v43 without requiring the new object. Do not edit `matrix_schema.py` in this task. Do not add a V3 flag.

  LOGGING REQUIREMENTS:
  - DEBUG on decode: `present`, `policy_id`, `decay_millis`
  - INFO when a config is rejected, including the stable reason code
  - ERROR with the schema version when encode is missing the required object
  - Logger name `simulation.runner_serialization`
  - Levels follow the process log config; no code edit is required to quiet production

  Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `tests/unit/test_runner_config_v43.py`

- [x] Task 2: Add `well` and `warning_post`, the public link, and the act tail. (depends on 1)

  Extend `src/world/collective_projects.py` with the two catalog rows, `PublicGoodAct`, `linked_structure_id: EntityId | None = None`, and `public_acts` capped at 32 with default `()`. The v17 decoder must keep constructing a project without passing those fields. Add `StructureKind.WELL` and `StructureKind.WARNING_POST` in `src/world/production.py` without a new recipe and without changing shelter or store construction. Do not write the new fields from the v17 encoder. A unit test asserts labor and material counts for both new kinds, rejects a 33rd act, and constructs a v3-20-shaped project with an empty act tail and an absent link.

  LOGGING REQUIREMENTS:
  - DEBUG `collective_project_defined kind=… labor_required=… materials_required=…` for the new rows, using the existing logger line
  - DEBUG `public_good_act_appended project_id=… act=… source=…` when a row is appended
  - ERROR `collective_project_validation_failed field=… reason_code=…` on a bad act
  - Logger name `world.collective_projects`
  - Do not log forbidden role strings

  Files: `src/world/collective_projects.py`, `src/world/production.py`, `tests/unit/test_public_good_catalog.py`

- [x] Task 3: Admit use, maintain, and oppose, and apply presence benefits plus decay. (depends on 2)

  Add the three commands in `src/world/actions.py` and the matching operations, rules, and transitions. Add the three `RuleReason` values and three `COMMAND_RULE_MATRIX` rows in `src/world/_rules.py`, following the `ContributeCollectiveProject` policy shape. The opening rule and `apply_operation` both read the working batch state. Enforce the rejection table, the one-draw and one-oppose limits, and item consumption only on an accepted maintain hit. The maintain item follows the linked structure kind (`wood` for shelter, store, and warning post; `stone` for bridge and well). A hit adds `REPAIR_INTEGRITY_DELTA`. Oppose subtracts that same delta on a completed link and does not refresh `last_accepted_tick`. After `abandon_idle_projects` and before `apply_autonomous_physical_step`, decay each linked structure id once. Inside the physical step, apply bridge fatigue relief after the metabolism gain and before `NeedsApplied`, and scale hazard extra for a linked `warning_post` before `ExposureApplied`. Emit presence `PublicGoodBenefit` rows from that step. A draw event stores `resulting_hunger` or `resulting_thirst`. Draw `public_good_maintain` in `src/simulation/engine.py` beside `collective_project_success`, purpose string `public_good_maintain` in `src/simulation/actions.py`, only after the attempt is structurally legal and only when the channel is on. Base probability `0.70`. Skip the draw when `adjusted_production_probability` is `1.0`. Channel off rejects the new commands and the two new start kinds with `public_goods_channel_off` and does not draw, decay, or emit benefits. Command count becomes 43. Update every existing `== 40` command pin in the same change, including `COMMAND_RULE_MATRIX` and `_CLOSED_COMMAND_TYPES`. Keep the six production recipes unchanged. One `resolve_tick` test completes a well and draws in that same tick.

  LOGGING REQUIREMENTS:
  - DEBUG `public_good_admitted action=… project_id=… actor_id=…`
  - DEBUG `public_good_rejected reason=…` with the `RuleReason` value
  - DEBUG `public_good_maintain_draw tick=… ordinal=… success=…` when a draw happens
  - INFO `public_good_benefit project_id=… actor_id=… benefit_code=… source=…`
  - DEBUG `public_good_decay project_id=… integrity_millis=…`
  - Logger names `world._rules`, `world.collective_projects`, and `simulation.engine`

  Files: `src/world/actions.py`, `src/world/_operations.py`, `src/world/_rules.py`, `src/world/_transitions.py`, `src/world/_physical.py`, `src/simulation/actions.py`, `src/simulation/engine.py`, `tests/unit/test_public_good_commands.py`

### Phase 2: History, observation, and choice

- [x] Task 4: Add replay 20, codec `v18`, and the three public-good events. (depends on 3)

  Add `EVENT_SCHEMA_REPLAY_V20` and the three detail types in `src/world/events.py`, legal only on that schema. Each event carries an `OccurrenceContext`. On replay 20, `ProjectCompleted` carries `decay_millis`; replay 19 rejects that key. Fold the new events in `src/world/_replay.py`. Set structure integrity from the latest `integrity_millis`. Apply `decay_millis` at the end of the completion tick and each later tick, once per linked structure id. A draw fold writes the stored resulting need once and drops store quantity by 1. Shelter, span, and warning folds do not change bodies, because `NeedsApplied` and `ExposureApplied` already hold those results. The v17 project encoder keeps the exact key set in `_encode_collective_project`. Codec `v18` adds `public_acts` and `linked_structure_id` and may store `well` and `warning_post`. `checkpoint_schema_for_production` returns `(20, "v18")` only when `public_goods_active` is true, ahead of `(19, "v17")`. `select_checkpoint_schema` agrees `(20, "v18")` first. Guard the collective-projects agreement clause with `not public_goods_active`. Pass the keyword through `runner.py` and `service.py`. Every membership set that already includes `"v17"` also includes `"v18"`. Append the three semantic types in `src/observer/version.py` (count **69**) and map them in `src/observer/adapt.py`. Update every `len(SEMANTIC_EVENT_TYPES) == 66` pin. In `tests/unit/test_observer_contracts.py`, keep the five `PROJECT_*` names as their own block and assert the three new names as the tail (`SEMANTIC_EVENT_TYPES[-3:]`). Shift any other slice that assumed `PROJECT_COMPLETED` was the last entry. Extend the observer scene row with `linked_structure_id` and `public_act_count`. Protocol id stays `observer-protocol-v1`. Alembic head stays `0017`.

  LOGGING REQUIREMENTS:
  - INFO `checkpoint_schema_selected` with `schema_version`, `codec`, and `reason=public_goods_active`
  - DEBUG when `public_acts` is encoded or omitted, with act count
  - WARN if a pre-v18 payload contains `public_acts`, `linked_structure_id`, kind `well` or `warning_post`, or `decay_millis` on `ProjectCompleted`
  - WARN if `select_checkpoint_schema` is asked for the channel and the agreed pair is not `(20, "v18")`
  - DEBUG `observer_event_adapted kind=… semantic_type=…` for each new kind
  - Logger names `simulation.persistence`, `simulation.serialization`, `simulation.engine`, `observer.adapt`

  Files: `src/world/events.py`, `src/world/_replay.py`, `src/simulation/serialization.py`, `src/simulation/persistence.py`, `src/simulation/engine.py`, `src/simulation/runner.py`, `src/simulation/service.py`, `src/simulation/journal.py`, `src/observer/version.py`, `src/observer/adapt.py`, `src/observer/contracts.py`, `src/observer/project.py`, `tests/unit/test_public_good_replay_schema.py`, `tests/unit/test_public_good_observer.py`

- [x] Task 5: Project public acts and the new occurrences onto the colocated observation. (depends on 4)

  Extend observed collective projects in `src/world/observations.py` and `_perception.py` so a visible location includes `public_acts` and `linked_structure_id` only when the channel is on. Project the three new occurrence kinds with the public facts from Task 4. When the channel is on, add `accepted` and `public_good` to local `ProjectContributed` facts. Channel off omits those keys. A hidden location yields no public-good occurrences. A unit test asserts a distant agent does not see a draw, a colocated agent sees a non-contributor's benefit, and a channel-off project occurrence has neither `public_good` nor `public_acts`.

  LOGGING REQUIREMENTS:
  - DEBUG `public_goods_perceived location_id=… act_count=…`
  - DEBUG `public_goods_hidden reason=content_hidden` when the location is not visible
  - DEBUG `public_good_occurrence_projected kind=… project_id=…`
  - Logger name `world._perception`
  - Do not log goal codes, reputation values, or norm belief text

  Files: `src/world/observations.py`, `src/world/_perception.py`, `src/simulation/serialization.py`, `tests/unit/test_public_good_perception.py`

- [x] Task 6: Let a private goal opt the owner into use, maintain, or oppose. (depends on 5)

  In `src/agents/cognition/goal_manager.py`, when `public_goods_active` is true, append at most one `CURRENT_INTENTION` per visible completed `well`, `storage`, or `winter_reserve` with `outcome_code` `public_good:use:<project_id>`. Do not mint a use goal for shelter, bridge, or warning post. If `_MAX_FOCI` (8) is already full, skip that mint and do not evict. Accept seeded `public_good:maintain:<project_id>` and `public_good:oppose:<project_id>`. Do not mint oppose or maintain from drives. Do not bump `GOAL_MODEL_VERSION`. Add `propose_public_good_command` and call it from `CommandPlanner` / `CognitiveLoop` only while the flag is on, in the post-compile slot, after the collective-project proposer. `UsePublicGood` is proposed only for the three drawable kinds. A seeded use code on a presence good logs `reason=presence_only` and leaves the compiled command unchanged. The proposer does not deny a draw because the owner is missing from the contribution tail. Add deliberation selection code `public_good_focus` without a new `ActionDirection`. Pass the flag through `_public_goods_loop_kwargs`. A unit test seeds each of the three codes, asserts `_hunger_linked` stays false, and asserts a shelter use code does not mint or replace the compiled command.

  LOGGING REQUIREMENTS:
  - DEBUG `public_good_goal_minted owner_id=… project_id=…`
  - DEBUG `public_good_goal_skipped reason=foci_cap owner_id=…`
  - DEBUG `public_good_command_proposed owner_id=… action=… project_id=…`
  - DEBUG `public_good_command_skipped reason=…` when the focus does not match a legal act, including `reason=presence_only`
  - INFO when the loop flag is bound: `public_goods_active=%s decay_millis=%s`
  - Logger names `agents.cognition.goal_manager`, `agents.cognition.collective_projects`, `simulation.runner`

  Files: `src/agents/cognition/goal_manager.py`, `src/agents/cognition/collective_projects.py`, `src/agents/cognition/deliberation.py`, `src/agents/cognition/loop.py`, `src/simulation/runner.py`, `tests/unit/test_public_good_proposer.py`

### Phase 3: Natural reaction, measures, and the experiment

- [x] Task 7: Let witnessed upkeep and opposition move reputation and norms. (depends on 5)

  In `src/agents/cognition/reputation.py`, map accepted `public_good_maintained` and accepted public `project_contributed` through the existing `help` delta row, and map `public_good_opposed` through the existing `attack` delta row. Leave `public_good_benefit` as `ignored_kind`. Do not add a reputation dimension. In `src/agents/cognition/social_norms.py`, add `NormPattern.SHARED_UPKEEP` and `NormExpectation.MAINTAIN_STRUCTURE`. Conforming evidence is accepted maintenance. Violation evidence is opposition. Benefit and draw are not violations. Do not wire enforcement to the public-good commands. Channel-off observations never carry the new kinds, so disabled and pre-v21 runs do not gain evidence. A unit test covers one witnessed maintain, one witnessed oppose, and a draw that leaves both ledgers unchanged.

  LOGGING REQUIREMENTS:
  - DEBUG `reputation_public_good_applied owner_id=… target_id=… kind=…` when a delta row is used
  - DEBUG `reputation_public_good_ignored kind=… reason=ignored_kind` for a benefit
  - DEBUG `norm_shared_upkeep owner_id=… sign=…` when evidence is recorded
  - DEBUG `norm_public_good_ignored kind=… reason=not_a_violation` for a benefit or draw
  - Logger names `agents.cognition.reputation` and `agents.cognition.social_norms`
  - Do not log a forbidden role string

  Files: `src/agents/cognition/reputation.py`, `src/agents/cognition/social_norms.py`, `tests/unit/test_public_good_reputation.py`, `tests/unit/test_public_good_norms.py`

- [x] Task 8: Add the five analysis families. (depends on 4)

  Add `MetricFamilyId` members and `_BUILDERS` entries so `METRIC_FAMILY_COUNT` is **91**. Update every existing `== 86` metric pin in the same change. Add `public_goods_spec` on `MetricComputationInputs` beside `collective_projects_spec`, and pass it from `src/experiments/collectors.py`. Assemble the families from `metric_service.py` only when that spec is present, in `src/analysis/public_good_metrics.py`, folding the same event tuple already passed as `collective_project_events`. The Gini population is actors named on that project's contribution, benefit, maintain, or oppose events. `gini_millis` is `0` when fewer than two such actors exist. Expose the locked counts. `gini_millis` reuses the resource-inequality Gini and stores millionths. Do not add a `PhenomenonId` or a support band. Do not import this module from `src/agents`. Channel off logs the empty case and writes no rows. A unit test builds the contribute-and-use, low-use, and use-without-contribution counts from a fixed event list without asserting a boolean.

  LOGGING REQUIREMENTS:
  - DEBUG `public_good_metrics_assembled benefits=… maintains=… opposes=…`
  - INFO `public_good_metrics_empty reason=public_goods_absent` when the spec is missing
  - Logger name `analysis.public_good_metrics`
  - Metric logs stay free of observation text, goal descriptions, and forbidden role strings

  Files: `src/analysis/specifications.py`, `src/analysis/public_good_metrics.py`, `src/analysis/metric_service.py`, `src/experiments/collectors.py`, `tests/unit/test_public_good_metrics.py`

- [x] Task 9: Add Experiment AX and the matrix finalize bit. (depends on 6, 7, 8)

  Register `experiment_ax_public_goods` (`public_goods@1`) in `src/experiments/catalog.py` and export it from `src/experiments/__init__.py`. Arms: `ax-channel-off`, `ax-contribute-and-use`, `ax-use-without-contribution`, `ax-contribute-low-use`, `ax-oppose`, `ax-maintain`, with the assertions in the experiment table. `ax-channel-off` asserts checkpoint pair `(19, "v17")` and zero `PublicGood*` events. `ax-contribute-low-use` starts from a production store at quantity `1`, completes `winter_reserve`, moves the contributor away, and draws once down to quantity `3`. `ax-oppose` sets `idle_ticks` to `8` and leaves `last_accepted_tick` unchanged. Completion and maintain arms set the relevant skill level to at least `1` so the `0.70` base clamps to `1.0` and the success draw is not taken. Keep the experiment off the V1 gate. In `src/experiments/matrix_schema.py`, insert `public_goods_on` immediately before `collective_projects_on`. Add an architecture isolation test that the new modules do not introduce a forbidden role field, do not reference `LibraryInstitution`, and do not let `src/agents` import `src/analysis`.

  LOGGING REQUIREMENTS:
  - INFO `experiment_registered experiment_id=public_goods@1 arms=6`
  - DEBUG per arm `public_good_arm arm=… benefits=… maintains=… opposes=…`
  - WARN if an arm payload contains a forbidden role alias
  - Logger name `experiments.catalog`

  Files: `src/experiments/catalog.py`, `src/experiments/__init__.py`, `src/experiments/matrix_schema.py`, `src/experiments/collectors.py`, `tests/unit/test_experiment_ax.py`, `tests/architecture/test_v3_public_goods_isolation.py`

### Phase 4: Docs

- [x] Task 10: Update the downstream V3 contract. (depends on 9)

  Update `docs/architecture.md` so the write-pair priority names `(EVENT_SCHEMA_REPLAY_V20, "v18")` only while `public_goods` is active, command count **43**, semantic count **69**, Experiment AX, and the statement that a benefit event is not an access grant and not a moral role. Update `docs/analysis-metrics.md` with the five families and the note that `public_good_free_rider_pattern` is a co-occurrence count. Update the V3 paragraph in `.ai-factory/DESCRIPTION.md` with the same pins. Do not rename the observer protocol. Do not claim `institutional_economy`.

  LOGGING REQUIREMENTS:
  - No runtime logger. The doc change is the deliverable.
  - Keep command, schema, and codec tokens exact

  Files: `docs/architecture.md`, `docs/analysis-metrics.md`, `.ai-factory/DESCRIPTION.md`
