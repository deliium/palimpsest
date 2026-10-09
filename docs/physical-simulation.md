# V1 Physical Simulation

[← LLM providers](llm-providers.md) · [Back to README](../README.md) · [Next Page →](configuration.md)

Objective physical rules for a small discrete world (about 5–10 agents, 10–20 locations, several resource kinds). Physical death is authoritative in `WorldEngine`. Subjective fear-of-death appraisal, beliefs, goals, and drive activations live in cognition only — they never rewrite physical rules or declare an agent dead. See [Cognition and agent runtime](cognition-runtime.md).

## Topology and capacities

- Locations form an undirected connected graph with ordered unique adjacency (no self-edges, dangling edges, or asymmetric edges).
- Each location has positive `body_capacity`, non-negative `item_capacity`, base ambient temperature, shelter ∈ [0, 1], and base visibility ∈ [0, 1].
- All bodies (including dead) count toward body capacity. Ground items count toward item capacity; held items and resource nodes do not.
- Every portable item has positive integer load and exactly one placement (ground or held). Body `carry_capacity` bounds Take/Give.

## Conservation

- Item identity is conserved: ground, held, or consumed by an immutable event.
- Resource quantity never goes negative; harvest/drink decrement the amount recorded on the event; regeneration cannot exceed maximum.
- Extraction requires quantity ≥ 1.0; values in (0, 1) are present but depleted for Search and resource Drink.

## Time, weather, visibility

- One tick = one simulated hour. `hour = tick % 24`; day hours 06–17, night 18–05.
- Effective visibility = clamp(location_base × phase × weather, 0, 1): day 1.0 / night 0.5; clear 1.0, cloudy 0.9, rain 0.7, storm 0.5.
- Contents (ground items, resources, other bodies) expose only when visibility ≥ 0.5. Exits, self, weather, hour, phase, and visibility modifier always expose.
- Weather stores condition only. Ambient = location base + weather offset + phase offset. Transitions when `(tick + 1) % 6 == 0` per location from the ordered transition matrix.
- Agent-facing projections use dedicated observation DTOs (not objective models): exact self physiology may appear via `ObservedSelf`; nearby bodies are coarse; resource max/regen and location capacities never appear. Full matrix and audience rules: [Architecture — Perception boundary](architecture.md#perception-boundary).

## Observation timing

An observation for open tick `N` is projected from the tick-start snapshot plus committed occurrences from tick `N−1`. Current-tick submissions and outcomes never appear early. Eventless prior windows are empty but still carried for live/restored parity. Live and restored engines at the same tick emit equal observations (including canonical serialization).

**Domain-contract evolution gate:** any future Observation / command / communications wire bump must keep live/restored observation parity green (`test_live_and_restored_observations_match_with_prior_events` and related checkpoint tests). Policy details: [Architecture — Domain-contract evolution](architecture.md#domain-contract-evolution-observation--commands--communications).

## Actions (all applied / rejected / conflicted — none deferred)

| Action | Summary |
| --- | --- |
| Move | Adjacent free body slot; +5 fatigue |
| Search | Eligible local resource + free ground slot; Bernoulli success; miss is event-only; success extracts 1.0 and creates a ground item |
| Take / Drop / Give | Capacity-checked atomic transfers |
| Eat / Drink | Consume held food / held water or local water resource; hunger −30 / thirst −40 |
| Sleep | Fatigue −30 this tick (shelter does not gate). Recovery does not depend on consolidation mode. |
| Attack | Hit 0.75, damage [10, 20]; miss event-only; lethal hit emits Attacked then Died under the same action cause |
| Flee | Success 0.80 then uniform eligible destination; +10 fatigue on success |
| Help | Target health +10 (cap 100), helper +5 fatigue; no revival |
| Feed | Caregiver applies held `ItemKind.FOOD`/`WATER` relief to colocated DEPENDENT (policy-gated; no dependent self-Eat/Drink required) |
| Transport | Caregiver + colocated DEPENDENT relocate together; caregiver fatigue per `PhysicalRules` |
| Wait / Talk / Ask / Tell | Event-only; still receive autonomous physiology |

Structural impossibility is REJECTED (starting state) or CONFLICTED (earlier effect). Stochastic misses are APPLIED without mutation.

## Learnable skills

`SkillLearningMode` defaults to `DISABLED`. Off uses today's search, move, flee, and help formulas and does not call the skill helpers. `DETERMINISTIC` is opt-in and is not a capability flag. Objective levels live in a private ledger that only `WorldEngine` reads, and only while resolving an action that already has a probability or an efficiency constant. A level is a float in `[0, 1]`, quantized after every write with `round(value / 1e-6) * 1e-6`. Every enabled body starts at `0` in each domain. Level `0` is identity with today's constants.

Closed domains: `foraging`, `navigation`, `resource_detection`, `crafting`, `building`, `healing`, `communication`, `teaching`.

Search splits by the command. Untargeted search is foraging and multiplies only `search_base_probability`. Targeted search is resource detection and multiplies only the visibility term. The multiplier is `(1 + probability_gain * level)` with `probability_gain` `0.50`, then `clamp_unit_interval`. The Bernoulli purpose stays `search_success`. Move fatigue and flee fatigue are divided by `(1 + efficiency_gain * navigation_level)` before `round_physical`. Help health gain is multiplied by `(1 + efficiency_gain * healing_level)` before `round_physical`. Helper fatigue is unchanged. At level `0` those values stay `5.0`, `10.0`, and `10.0`. Crafting, building, and communication keep a multiplier of exactly `1`. Teaching scales instruction transfer only.

Growth folds committed facts. One tick uses start-of-tick levels and the start-of-tick world for witnesses. Deltas for that tick are summed per body and domain, quantized once, then clamped to `[0, 1]`. Practice is an admitted applied action: untargeted search, targeted search, move, flee, help, delivered talk/ask/tell, and delivered instruction on the speaker's teaching domain. Success adds `success_rate` on that domain. Stochastic search or flee misses add `failure_rate`. Rejected, conflicted, and deferred actions add nothing, and a rejected action is not a failure. Instruction is a delivered utterance with exactly one `instruct` relation whose object is one domain token. Transfer to the recipient is `instruction_rate * teacher_teaching_level` from the teacher's start-of-tick teaching level. A teacher at `0` transfers `0` and still practices teaching. A living enabled body at the action's origin location witnesses a successful public search, move, flee, or help when that location's effective visibility is at least `0.5`, and gains `observation_rate` on that action's domain. Same-tick moves do not change the witness set. Talk, ask, and tell are recipient-private. Crafting and building grow only through instruction. Attack adds nothing. A disabled actor in a mixed run uses the bypass formulas and is not written into the ledger.

Replay rebuilds the ledger by grouping committed events by tick, projecting earlier ticks, then folding tick T. World-snapshot JSON has no skill key. An unknown snapshot field still fails with `unknown_field`. A committed search stores the found resource, so resume classifies a search as foraging only when the caller passes that request id in `skill_untargeted_request_ids`. Omitting the set leaves a successful untargeted search on resource detection.

Teaching, when the policy is present, adds two more deltas on the ledger that skill growth already returned. A witnessed demonstration inside the offer window adds `demonstration_rate * (1 - recipient_start_level)` to the addressed recipient. Joint practice, when both bodies apply the same domain in that tick and share a start-of-tick location, adds `practice_together_rate * (1 - own_start_level)` to each. The default window is `8` ticks after the delivery tick. Neither bonus multiplies by the other body's level. The existing `instruct` channel stays `instruction_rate * teacher_teaching_level`. Offers are refolded from committed events. A disagreeing caller set fails with `teaching_offer_mismatch`. World-snapshot JSON still has no teaching key.

## Physiology and death

Close-of-tick order for living bodies: needs (+2 hunger, +3 thirst, +1 fatigue) → combined needs damage → optional Died(`combined_needs`) → else temperature lerp with shelter → exposure damage → optional Died(`exposure`). Health clamps to 0. Death is terminal; dead bodies occupy capacity and keep inventory.

## Tick finalization

Action resolution then autonomous effects accumulate pending details/causes/occurrence context against one evolving state. One finalizer decides mutation, advances revision at most once, assigns contiguous sequences and deterministic event IDs, and freezes schema-v4 `WorldEvent` values with action or system causes plus event-time audience context (origin, destination, affected entity, private recipient as applicable).

## Basic production

Production is off unless a run carries a non-empty `ProductionCatalog` or an agent sets `ProductionKnowledgeMode` to `DETERMINISTIC`. An empty catalog plus `DISABLED` does not change commands, probabilities, fatigue, events, memories, beliefs, or audits. It is not a capability flag.

The closed commands are `Harvest`, `Craft`, `Build`, `Repair`, and `Store`. The example catalog is six recipes and nothing else: `harvest_wood`, `harvest_stone`, `craft_tool`, `build_shelter`, `repair_shelter`, and `store_food`. Recipes are configuration. There is no profession, role, culture, or technology tier, and agents do not receive the catalog on `Observation`.

`WorldEngine` alone decides available materials, duration, success, inventory changes, and produced objects. Recipe beliefs store a recipe id and a supported flag on the owner. They do not store inputs, durations, or probabilities, and they are not an engine input. A provider may select only a recipe id already supported on that owner.

Rejections commit nothing: `unknown_recipe`, `materials_unavailable`, `actor_busy`, `structure_intact`, and `production_disabled`. A pending job makes the actor busy for every command, including move and eat. Harvest success is `0.80` and craft success is `0.70`; both draw `production_success` only when the adjusted probability is below `1`. Build, repair, and store stay at `1.00` and do not draw. Structures attach to a location id. They have no coordinates. A shelter changes exposure for that location without writing `Location.shelter_factor`.

Replay schema v6 and persistence codec `v3` (`structures`, `production_jobs`, `tool_marks`) are written only when the catalog is non-empty. The default event write stays replay-v5 and the default codec stays `v2`. `runner-config-v13` is accepted only when the catalog is non-empty or some mode is `DETERMINISTIC`. The default runner write stays `runner-config-v4`. A teaching-only run still writes `runner-config-v12`.

Loggers: `world.production`, `world.events`, `world._production`, `simulation.engine`, `simulation.replay`, `world._perception`, `agents.cognition.production`, `simulation.agent_runtime`, `simulation.runner`, `observer.project`, and `observer.adapt`. Catalog mismatch logs the SHA-256 digest only.

## Environmental dynamics

Seasons, temperature bands, resource seasonality, depletion, regeneration, temporary shortages, and hazards are off unless a run carries an `EnvironmentalDynamicsSpec`. `None` keeps the day/night cycle, the Markov weather chain, and constant `regeneration_per_tick`. It is not a capability flag. `multi_hop_testimony_tracking` stays unowned.

`WorldEngine` is the only writer. The calendar, multipliers, windows, and hazard rules live on the spec and on `runner-config-v14`. They are not fields of `WorldState` and they are not copied onto `Observation`. Agents see the current season, the current local temperature band, current local hazard kinds, and current resource quantities. A causal model may record which season followed the last one it saw when `predictive_world_model` is enabled. It does not receive the spec.

Season is `(tick // season_length_ticks) % 4`, in the order spring, summer, autumn, winter. Tick `0` is spring. Ambient with a spec is base + weather offset + phase offset + season offset. Bands are derived: cold below `10`, hot at or above `30`, otherwise mild. Regeneration is the configured rate times the season multiplier, then `0` inside a matching shortage window. Search extraction is not multiplied. A node witness records a quantity crossing zero. It does not apply a second delta on replay.

A hazard starts when its season, weather, and band match and that kind is not already active at the location. Exposure adds the rule extra only while `PhysicalRules.exposure_damage` is not `0`. Death cause stays `EXPOSURE`.

`runner-config-v14` is written only when the spec is set. Replay-v7 and persistence codec `v4` are written only for that run. Replay-v7 also accepts production details. A production-only run still writes replay-v6 and codec `v3`. The default event write stays replay-v5 and the default codec stays `v2`. A dynamics-off checkpoint rejects `active_hazards`.

Loggers: `world.environment`, `world.events`, `simulation.engine`, `world._perception`, `simulation.replay`, `simulation.runner`, `agents.cognition.world_model`, `observer.project`, `observer.adapt`, and `experiments.catalog`. Reason codes include `yield_undefined`, `duplicate_shortage_window`, `environment_witness_mismatch`, `environment_spec_mismatch`, and `presentation_instruction_forbidden`. Do not log seeds.

## External information artifacts

Artifacts are objective `WorldEngine` objects on `WorldState.artifacts` (default empty). They are not `Item`, `Structure`, `Resource`, or `MemoryTrace` values. Closed kinds: `mark`, `sign`, `note`, `map`, `record`, `memorial`. Content is structured marks and relations only — no free-form prose and no presentation or meaning fields. Existence does not download information into memory; meaning stays owner-scoped and opt-in (see [Memory reconstruction](memory-reconstruction.md)).

Portable kinds (`note`, `map`, `mark`) sit at exactly one of `location_id` or `holder_id`. Fixed kinds (`sign`, `record`, `memorial`) always use `location_id`. Held portable artifacts are parallel to inventory: they are not members of `AgentBody.inventory`, do not consume carry capacity, and transfer only via `TransferArtifact`. Cap is 8 held artifacts per living body (`artifact_hold_cap`). `Take` / `Drop` / `Give` reject artifact ids (`not_an_item`).

Closed commands: `Inscribe(kind, content, hold=False, record_genre=None)`, `Amend`, `Erase`, `TransferArtifact(artifact_id, mode, recipient_id=None)` with `mode` ∈ {`deposit`, `claim`, `give`}. Durable records (when `DurableRecordsSpec` is present on `runner-config-v33|v34`) add `CopyRecord`, `AnnotateRecord`, and `DamageRecord` (`mode` ∈ {`damage`, `partial_loss`, `destroy`}). Knowledge repositories (when `KnowledgeRepositoriesSpec` is present on **`runner-config-v34`**) add `EstablishRepository`, `DepositRecord`, `RetrieveRecord`, `MaintainRepository` (`mode` ∈ {`maintain`, `destroy`}), and `IndexRepository`. Dependency-care adds `Feed` / `Transport` when `dependency_care.care_action_policy` allows. The closed `AgentCommand` union is **35**. Bounded experimentation adds `Experiment` (operator, operand entity ids, process token, optional hypothesis id). It carries no physical delta. `WorldEngine` alone reads the private law catalog and assigns one of `success`, `partial_success`, `failure`, `harm`, or `unexpected`. Unlisted operand pairs are `failure` with no novel item kind. Harm uses the existing hunger and attack scalars. The law catalog is not copied onto `Observation`. World admission may accept artifact/durable/repository commands when tests or scripts submit them; cognition compiles Inscribe/Amend/Erase/Transfer, durable, and repository commands only when `ArtifactInterpretationMode` is `DETERMINISTIC` (durable/repository also require their channels on). Off is an empty artifacts/repositories map plus mode `DISABLED` — not a capability flag. Durable and repository deepen use owned `cultural_historical_memory` (no new V3 flag). No `LibraryInstitution`. `multi_hop_testimony_tracking` stays unowned.

Objective durable fields on `InformationArtifact` (channel-on): `record_genre`, `parent_artifact_id`, `source_artifact_id`, `copy_generation`, `integrity` (`intact`/`damaged`/`partially_lost`/`destroyed`), `annotation_revisions`, `lost_mark_count`, plus optional `custodian_repository_id` when repository custody holds the artifact. Genres are kind labels only — never truth. Copy fidelity follows `copy_fidelity_policy` (perfect / deterministic_mutation / lossy). Author death does not delete or auto-correct records. Genealogy/chronicle genres never write kinship edges or history.

`KnowledgeRepository` is a WorldEngine-owned storage container (`location_id`, optional `structure_id`, immutable `founder_ids`, `access_mode` ∈ {`open`, `colocated_only`, `founder_list`}, `status` ∈ {`intact`, `neglected`, `inaccessible`, `destroyed`}, membership, imperfect `index_entries`). Founder death does not delete repositories or members. Custody blocks `Take` / `TransferArtifact` / `Erase` while `custodian_repository_id` is set (`repository_custody_blocks_*`); retrieve then take/transfer succeeds. Neglect timers and `MaintainRepository` update integrity/decay; `WorldEngine.mark_repository_inaccessible` / `clear_repository_inaccessible` gate deposit/retrieve when policy blocks. Index tokens are organization metadata — never a truth catalog. Cultural labels (archive / library / sacred records / …) stay subjective only.

Reject reasons: `unknown_artifact`, `artifact_not_portable`, `artifact_not_held`, `artifact_not_colocated`, `artifact_content_invalid`, `invalid_artifact_kind`, `invalid_artifact_hold`, `artifact_transfer_mode_invalid`, `artifact_hold_cap`, `recipient_unavailable`, `not_an_item`, plus durable `durable_records_inactive`, generation/annotation caps, destroyed-parent copy blocks, and repository `knowledge_repositories_inactive`, `repository_access_denied`, `repository_inaccessible`, `repository_destroyed`, custody blocks, and capacity rejects. Perception exposes ground artifacts at the observer location when visibility ≥ 0.5, and always exposes artifacts held by self. Foreign held artifacts are omitted. When durable `perception_mode=marks_and_meta`, Observation may project lineage/integrity meta; `marks_only` omits meta. When repository channel on, Observation may project `ObservedRepository` (objective fields only; `perception_mode=container_and_meta` vs `container_only`). Occurrence `public_facts` may include only `artifact_id`, `artifact_kind`, and `content_revision`.

Event/codec write pair is chosen at run start and never mid-run (priority excerpt):

| Condition | Event schema | Codec |
| --- | --- | --- |
| `knowledge_repositories_active` | replay-v14 | `v11` |
| else `durable_records_active` | replay-v13 | `v10` |
| else dependency-care | replay-v12 | `v9` |
| else … | … | … |
| `artifacts_active` | replay-v8 | `v5` |
| else dynamics | replay-v7 | `v4` |
| else production | replay-v6 | `v3` |
| else | replay-v5 | `v2` |

Codec `v5` requires `artifacts` plus every v4 key. Codec `v10` carries durable additive artifact fields when the durable channel is on. Codec `v11` adds `repositories` (+ custody) when the repository channel is on. Detail types `ArtifactCreated` / `ArtifactModified` / `ArtifactMoved` / `ArtifactDestroyed` remain; durable adds `ArtifactCopied` / `ArtifactAnnotated` / `ArtifactDamaged` / `ArtifactPartiallyLost` (effect-complete on schema 13); repositories add `RepositoryEstablished` / `RepositoryMemberDeposited` / `RepositoryMemberRetrieved` / `RepositoryMaintained` / `RepositoryIndexed` / `RepositoryNeglected` (effect-complete on schema 14). Default event write stays replay-v5; default codec stays `v2`; `CURRENT_PHYSICAL_EVENT_SCHEMA_VERSION` stays 5. `runner-config-v19` carries every v18 cognition key plus `artifact_interpretation_mode` and is emitted only when some mode is `DETERMINISTIC`. Conventions-only configs still write v18. Experiment Z (`experiment-z-external-artifacts`) and `external_artifact_memory@1` stay analysis-only and unchanged when durable absent. Experiment AN (`durable_records`) and Experiment AO (`knowledge_repositories`) stay off the V1 gate.

Loggers: `world.artifacts`, `world.repositories`, `world.events`, `world._operations`, `world._perception`, `simulation.bootstrap`, `simulation.engine`, `simulation.persistence`, `simulation.replay`, `simulation.runner`, `agents.cognition.artifacts`, `observer.project`, `observer.adapt`, `experiments.external_artifacts`, `analysis.external_artifact_memory`, `analysis.durable_record_metrics`, `analysis.knowledge_repository_metrics`. Do not log mark tokens or seeds at INFO.

## Seeds and schemas

- Named streams: run, world, tick, ordinal or system entity, purpose, derivation-v2 (rules fingerprint). Never module-global RNG or Python `hash()`.
- **Never log seeds**, random draws, inventories, event payloads, observation contents, communication text, or full snapshots.
- Audit schema v1: decode/export only. Replay schema v2: legacy projector. Replay schema v3: physical runs without occurrence context (readable). Replay schema v4: physical runs with occurrence context (new writes). Replay-v7 is accepted and is written only when an environmental dynamics spec is set. Replay-v8 is accepted and is written only when artifacts are active at run start. The default write stays replay-v5. Runs do not mix replay schemas.

## Snapshot contents

Checkpoints capture locations (adjacency/capacities/environment), bodies (physiology + carry capacity), items (kind/load/placement), resources (kind/quantity/max/regen), weather (condition), revision, next tick, and integrity hashes. A dynamics-on checkpoint also stores active hazards. An artifacts-active checkpoint (codec `v5`) also stores `artifacts`. Physical rules version/fingerprint/canonical bytes persist on the run. `PhysicalRules` stays `physical-v1`.

## Tests

```bash
uv run --frozen --python 3.12.14 pytest tests/unit
uv run --frozen --python 3.12.14 pytest tests/unit/physical -q
# Optional Postgres integration:
# PALIMPSEST_TEST_DATABASE_URL=... uv run --frozen --python 3.12.14 pytest -m integration tests/integration
```

Resource depletion and tombstones stay physical facts. The analysis-only technique lifecycle does not add technology gates, and it does not block Harvest, Craft, or Experiment when materials are missing.

When `possession_succession` is present on `runner-config-v38`, every existing `Died` also opens corpse custody. The items stay on the dead body at the death location. They are not deleted, dropped, or given to a child, caregiver, or group. A colocated living agent may `Take` one on a later tick: commands in the death tick run before that system step. The take changes the physical holder only. `AssertPossessionClaim` records a doctrine and does not move the item. `Give` to a dead body stays rejected. Channel off leaves the inventory on the body and still rejects a take of a held item. Experiment harm that sets health to zero does not emit `Died` and does not open custody.

## See also

- [Architecture](architecture.md)
- [LLM providers](llm-providers.md)
- [Persistence](persistence.md)
- [Development](development.md)
