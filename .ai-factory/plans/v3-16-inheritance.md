# Implementation Plan: V3-16 Inheritance and Succession of Possessions

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-09
Improved: 2026-10-09 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M7 — V3 Generational Civilization"
Rationale: Defines what physically happens to held items when an agent dies, and lets agents argue about who should have them, without installing an inheritance law.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M7 — V3 Generational Civilization
INFO [aif-plan] mode=ultra treated as full (richer plan); remaining args describe the feature
INFO [aif-plan] resolved plan file: .ai-factory/plans/v3-16-inheritance.md (format=slug)
INFO [aif-plan] plan name prefix v3- applied per user request; suggested stem `v3-16-inheritance`; git.create_branches=false so stem is description slug (branch-derived naming disabled)
INFO [aif-plan] RESEARCH.md absent; research_influenced_plan=false
INFO [aif-plan] plan_default_milestone=auto would surface M6 first; scope is explicitly v3-16 under M7 so linkage uses M7
INFO [aif-improve] refined 2026-10-09: corpse_here placement without foreign holder ids; occurrence public facts for custody, corpse take, and claims; deterministic claim/take proposer; lifespan death in engine.py; commands resolve before system death so Take is a later tick; journal WorldSnapshot stores corpse_custody_item_ids on codec v13; WorldState in _state.py; _experiment_schemas accepts v38 and keeps bounded_experimentation_requires_v36; semantic count 54→57; experiment harm _set_health stays without Died

## Compatibility contract

This plan adds an opt-in death-custody channel. It does **not** own a new `V3CapabilityFlags` slot and it does **not** turn `kinship_inheritance` into an inheritance law.

1. V1/V2 invariants intact. `WorldEngine` remains the only objective mutation authority. Agents receive immutable per-agent `Observation` / `Perspective` only. `WorldEvent` records remain immutable and append-only. Subjective legitimacy stays outside the objective fold. Godot remains read-only. Deterministic replay continues. No scripted `heir_receives_inventory` / `children_must_inherit` / `group_confiscates` outcomes.
2. Flag ownership unchanged: keep `cultural_historical_memory`, `generational_population`, and `kinship_inheritance` owned. Do **not** own `multi_polity_migration`, `institutional_economy`, or `multi_hop_testimony_tracking`. **No new V3 capability flag.**
3. Channel off = prior baseline. With `possession_succession` absent, death still sets `LifeStatus.DEAD` and leaves `AgentBody.inventory` on that body. `Take` still rejects any item with `holder_id` set. `exact_trajectory_hash` for existing experiments stays the same. No new event, no new command, no ledger.
4. Schema bumps use accepted-set + exact key-set discipline. Never drop accepted V1/V2/V3 versions in the same change that adds a write version.
5. **No inheritance law (locked).** The engine never reads parentage, caregiving, group membership, claim order, or a doctrine token when it places items. Forbidden config and code aliases include `heir`, `heir_policy`, `primogeniture`, `spouse_inherits`, `children_inherit_law`, `escheat`, `inheritance_law`, `auto_transfer_to_child`, `auto_transfer_to_caregiver`, `auto_transfer_to_group`, `estate_executor`.
6. **Physical possession ≠ legitimate ownership (locked).** After death, items are in corpse custody (still held by the dead body at the death location). A later `Take` changes physical holder only. A claim, a doctrine, or a sanction never moves an item and never changes health, inventory, or command legality.
7. **Items are not deleted (locked).** Custody opening copies the inventory id tuple into the event. It does not drop, destroy, eat, store, or deposit those items. Ground `item_capacity` is not consulted. Repository membership is not an estate. Resource nodes stay on locations.
8. **One physical mechanism in this plan (locked).** `custody_mechanism` accepts only `corpse`. Location piles and separate container entities are deferred. Passing them is a reject, not a silent fallback.
9. **Beliefs are owner-scoped and revisable (locked).** Closed doctrine tokens an agent may hold: `children_should_inherit`, `group_owns`, `caregiver_inherits`, `first_claimant_owns`, `nobody_owns`. None is seeded as truth. Blank-slate entrants start with an empty ledger. Kinship, dependency care, and group formation may be *read by that agent's cognition* when those channels are already on. They are not consulted by `WorldEngine`.
10. **Claims, conflict, transfer, appropriation, sanctions (locked).**
    - Claim: new command `AssertPossessionClaim` emits a public assertion and does not move items.
    - Conflict: two or more assertions about the same decedent (or the same item) have no engine winner.
    - Voluntary transfer: existing `Give` between living agents. `Give` to a dead body stays `DEAD_TARGET`.
    - Appropriation: `Take` from corpse custody by a living colocated agent. Legal whenever capacity allows. Doctrine does not gate it.
    - Sanction: subjective ledger row only. Reuse no new damage rule. Existing `Attack` stays the only physical harm command, and this plan does not auto-select it.
11. **Preserve v3-02–v3-15 locks:** blank-slate deny-list gains only `possession_legitimacy`; closed Observation `lifecycle` unchanged; ELDER ≠ leader; related ≠ affection; no parent→caregiver hardwiring; no global Culture / LibraryInstitution / `GlobalTechniqueRegistry`; durable marks ≠ truth; historical layers and technique lifecycle stay analysis-only; a successful experiment is not knowledge; LLM drafts cannot name physics; kinship cultural / knowledge inheritance handoff stays deferred; triple representation stays intact. Author death still does not delete records, repositories, or practical-knowledge audits.
12. **`api` must not import `analysis`.** `simulation` and `persistence` must not import `analysis`. `world` must not import `agents` or `analysis`.

## Goal

When the channel is on and an agent dies, every item in that body's inventory remains physically on the corpse, in an explicit lootable custody state, at the death location.

Living agents may assert who *should* receive those items, disagree, take them, give them, or privately treat a taking as a sanctionable wrong. Research can see which doctrine is spreading. The world never enforces one.

## Design Decisions

### Invariant freeze (non-negotiable)

1. `WorldEngine` does not read doctrine ledgers, kinship edges, caregiver bonds, or group rolls when opening custody or resolving `Take` / `Give` / `AssertPossessionClaim`.
2. Agents never receive another agent's legitimacy ledger.
3. `WorldEvent` records remain immutable; authoritative history stays append-only.
4. Research convention rows must not bias live cognition.
5. No scripted heir, confiscation, or "fair share" boolean.
6. Godot remains read-only. New semantics are labels over events. No map chrome that draws a legal owner.
7. Runs remain reproducible (explicit seeds, no succession RNG).

### Scope split (locked)

| This plan (v3-16) | Deferred |
| --- | --- |
| Corpse custody on every existing `Died` emission | Dropping the estate onto the ground or into a new container entity |
| `Take` from a colocated corpse when the channel is on | `Take` from a corpse in another location |
| Public `AssertPossessionClaim` with a closed doctrine token | Natural-language wills, executors, notarized artifacts |
| Owner-scoped doctrine / claim / sanction ledger | Copying a parent's doctrine into a newborn (cultural handoff) |
| Analysis of emerging doctrines vs physical holders | Kinship knowledge / cultural inheritance handoff |
| `corpse_here` placement and public facts for colocated witnesses | Showing another living agent's inventory |
| Deterministic proposer for `AssertPossessionClaim` and corpse `Take` | LLM-authored doctrines or free-text wills |
| `runner-config-v38` + replay-v16 / codec v13 only while the channel is on | Alembic `0018+`, `/v2` HTTP, protocol rename |
| Experiment AS off the V1 gate | Owning `multi_polity_migration` or `institutional_economy` |
| Custody only beside an existing `Died` | Treating experiment harm `_set_health` zero as death |

**Rationale:** Death already leaves inventory on the dead `AgentBody` (`_project_died` only flips health and `LifeStatus`). `Take` requires `holder_id is None` and a ground `location_id`, so those items are stuck. This plan makes that custody explicit and lootable without choosing an heir. `kinship_inheritance` stays a parent→child graph (v3-05). Related ≠ inheritance rights.

### Capability / ownership (locked)

1. **No new V3 flag.** Enabling succession requires exact `possession_succession` on `runner-config-v38` only. `generational_population`, `kinship_inheritance`, and `cultural_historical_memory` are optional neighbors, not prerequisites.
2. **Do not** enable the channel implicitly when kinship, caregiving, or groups are on.
3. **v37 without `possession_succession`** stays valid (AR baseline). Schema `v38` always requires `possession_succession`.
4. Do **not** implement kinship knowledge or cultural inheritance handoff.
5. Other unowned V3 flags still fail closed.
6. When the object is absent: AE–AR bit-identity matches pre-plan for the same roster and seeds. Channel-off death with a non-empty inventory still cannot be `Take`n.
7. Optional read-only cognition context, ignored by the engine:
   - Kinship graph present → an agent *may* update support for `children_should_inherit` from its own observations of parent/child ids. Absence → that doctrine can still be asserted, and analysis marks `kinship_alignment=not_applicable`.
   - Dependency-care bonds present → same for `caregiver_inherits`. Never treat parent as caregiver.
   - Group-formation membership present → same for `group_owns`. No group entity receives items.
   - `first_claimant_owns` updates from the first observed corpse `Take` after `CorpseCustodyOpened`. The engine does not reserve the items for that agent.
   - `nobody_owns` is a belief that corpse `Take` is not a wrong. It does not clear other agents' claims.

### Flag × object gate matrix (locked)

| Config shape | Allowed? | Reject / notes |
| --- | --- | --- |
| Object absent, schema v4–v37 | Yes (off) | Passthrough |
| Object present, schema ≠ v38 | No | `possession_succession_requires_v38` |
| Schema v38 without the object | No | `v38_requires_possession_succession` |
| Object present, any V3 flag off | Yes | Death exists in V1; no flag prerequisite |
| Object present, kinship on, schema v38 | Yes | Graph is not an heir table |
| Object present, cultural / lifecycle / genealogy / experimentation on v38 | Yes | Widen those schema allowlists through v38; add v38 to the local `_experiment_schemas` set; keep reject code `bounded_experimentation_requires_v36`; do not require those objects |
| `custody_mechanism=corpse` | Yes | Only accepted mechanism |
| `custody_mechanism=location` or `container` | No | `custody_mechanism_unsupported` |
| Any forbidden heir alias | No | `possession_succession_law_forbidden` |
| `mode=disabled` present | No | `possession_succession_mode_invalid` — omit the object for off |
| Unowned V3 flag true | No | existing `capability_unimplemented` |

### Runner schema (locked)

Introduce `RUNNER_SCHEMA_VERSION_V38 = "runner-config-v38"`:

- Exact root key set = **v37 accepted roots** ∪ sibling **`possession_succession`**. `technique_lifecycle`, genealogy, durable records, repositories, experimentation, kinship, and population objects stay optional.
- `possession_succession` present ⇒ `schema_version == runner-config-v38`.
- Decode v23–v37 synthesizes `possession_succession=None`.
- Gate rewrite: cultural, durable, historical-layer, repository, genealogy, and experimentation allowlists that were extended to v37 in v3-15 also accept v38. Cultural-only still forbids `population_lifecycle`. It allows `possession_succession` and `technique_lifecycle`.
- Default write stays `runner-config-v4` when all V3 flags are off and this object is absent.
- **Write pair:** when the channel is active, `checkpoint_schema_for_production` returns `(EVENT_SCHEMA_REPLAY_V16, "v13")`, higher priority than `bounded_experimentation_active` (v15/v12). Channel off does not select v16.
- **Matrix finalize (Task 14 only):** in `src/experiments/matrix_schema.py`, insert `possession_succession_on` immediately before `technique_lifecycle_on`. Task 1 must **not** edit finalize priority.
- Alembic head stays `0017`. Protocol id stays `observer-protocol-v1`.

### Serialization contract (locked)

Mirror the v37 helper pattern in `runner_serialization.py`:

- v38 root keys = v37 family helper ∪ `{possession_succession}` minus optional objects that are absent
- Exact child keyset `_POSSESSION_SUCCESSION_KEYS`
- `_encode_possession_succession` / `_decode_possession_succession` with `_require_keys`
- Encode: `schema_version == V38` requires the object
- Decode: v23–v37 → `None`
- DEBUG log `present`, `custody_mechanism` on decode
- Reject forbidden law aliases before key acceptance

### `PossessionSuccessionSpec` (locked)

Root sibling object; omit for off. Exact keys (reject extras / missing):

| Key | Type / values | Role |
| --- | --- | --- |
| `policy_id` | `possession-succession-v1` only | Closed policy id |
| `custody_mechanism` | `corpse` only | Physical placement rule. Not an heir rule |

No doctrine default, no heir id, no share table, no sanction damage.

### Runtime channel flags (locked)

1. `possession_succession_active = config.possession_succession is not None` at run start.
2. Pass a `PossessionSuccessionRuleContext(allow_corpse_take=True, allow_claim=True)` into `evaluate_operation` only when active. `WorldEngine.tick` passes it beside `dependency_care_context`. `None` context ⇒ corpse `Take` and `AssertPossessionClaim` reject with `POSSESSION_SUCCESSION_CHANNEL_OFF`.
3. Subjective checkpoint field `possession_legitimacy` (owner id → ledger). Blank-slate key of the same name. Not a SQLAlchemy table.
4. Objective `corpse_custody_item_ids: frozenset[EntityId]` lives on `WorldState` (`src/world/_state.py`), default empty, threaded through `rebuild_world_state`, and rebuilt by replay from `CorpseCustodyOpened` / corpse-take events. Journal `WorldSnapshot` persists the id list only on codec `v13`. Older codecs decode it as empty. Flags-off folds never add ids.

### Physical custody (locked)

On each existing `Died` emission, in the same rule application or system step, when the channel is on:

1. Read `body.inventory` after the death flip (ids unchanged).
2. Emit `CorpseCustodyOpened(body_id, location_id, item_ids)` with those ids in inventory order.
3. Projection adds those ids to `corpse_custody_item_ids`. Holder stays the dead body. `location_id` on the item stays unset (still held). The body is not moved.
4. Empty inventory still emits the event with `item_ids=()`.
5. Do **not** add a `Died` on a path that does not emit one today. Custody attaches beside every existing `Died`: needs and exposure in `src/world/_physical.py`, attack in `src/world/_rules.py`, and lifespan in `src/simulation/engine.py` (`DeathCause.LIFESPAN`). Commands resolve before system effects, so a `Take` or claim in the death tick cannot see custody opened later that same tick. Scripted takes and claims run on a later tick.
6. `src/world/_experiment_apply.py` `_set_health` may set `LifeStatus.DEAD` with no `Died`. Leave that path unchanged. Do not emit `Died` or open custody from experiment harm. Log ERROR `death_without_died` only when the channel is on and some other new `DEAD` write has no paired `Died`.
7. Channel off: no `CorpseCustodyOpened`. Inventory behavior matches today.

### Perception (locked)

`ObservedItemPlacement` today is `held_by_self` and `ground_here`. `_project_item` hides every item held by someone else, so a corpse inventory is invisible.

When the channel is on, a custody item whose holder is `DEAD` and at the observer's location projects as `corpse_here` with entity id, name, kind, and load. No foreign holder id on the item row. Channel off does not emit `corpse_here`.

`build_occurrence_context` and `_public_facts_for_role` grow arms for the three new details. Colocated witnesses receive `decedent_id`, `item_ids`, and, for a claim, the doctrine token. The actor of a corpse take is in the occurrence the same way other action occurrences expose `actor_id`. Hypothesis-style private fields do not exist on these events. `target_id_for_details` returns the decedent body for custody and claims, and the item id for `TakenFromCorpse`.

`Take` when the channel context is present:

- Existing ground `Take` is unchanged (`holder_id is None`, same location, capacity).
- Additionally accept `Take` when the item id is in `corpse_custody_item_ids`, the holder body is `DEAD`, and that body is at the actor's location.
- Success: remove the id from the corpse inventory and from `corpse_custody_item_ids`; holder becomes the actor; emit `TakenFromCorpse(item_id, source_body_id, resulting_holder_id)` rather than overloading `Taken` (exact key sets stay stable on replay-v15).
- Ground `Taken` is unchanged.
- Rejects: not colocated, not in custody, actor dead, over capacity. Never reject because of a claim or doctrine.
- `Give` to `DEAD` stays rejected. A corpse cannot be the recipient of a voluntary transfer.
- `Drop` still requires the actor to hold the item. Dropping after a corpse `Take` is an ordinary ground drop.

### Claims and sanctions (locked)

New command `AssertPossessionClaim`:

| Field | Rule |
| --- | --- |
| `decedent_id` | `EntityId` of a body that is `DEAD` |
| `doctrine` | one of the five tokens |
| `item_id` | `EntityId` or omitted (`None` = the whole custody set) |

Success requires the channel, a living actor, a dead decedent, and (if `item_id` is set) that id currently in that body's custody set. Actor must be colocated with the corpse. Emit `PossessionClaimAsserted`. Do not mutate items, health, or ledgers inside `WorldEngine`.

The owner's cognition, after it sees its own successful assertion or a perceived one, appends a ledger claim. Two assertions are a conflict only in analysis and in each owner's ledger. There is no `ClaimResolved` event.

Sanction tokens on the ledger (subjective, closed): `none`, `criticism`, `shun`, `retaliation_considered`. Writing `retaliation_considered` does not enqueue `Attack`. Perception of a corpse `Take` that contradicts the owner's active doctrine may append `criticism` or `shun`. `nobody_owns` does not append a sanction for that take. No new `NormSanction` world effect.

### Subjective ledger (locked)

Module `src/agents/cognition/possession_legitimacy.py`. Owner-scoped. Not on `Observation`.

Each owner stores:

- doctrine supports: token → non-negative int count, only tokens the owner has actually adopted
- claims they have made or witnessed: `(tick, decedent_id, claimant_id, doctrine, item_id|None)`
- sanction notes: `(tick, decedent_id, target_id, token)`

Updater inputs are that owner's observations of `CorpseCustodyOpened`, `TakenFromCorpse`, `PossessionClaimAsserted`, and `Given` of an item id they previously saw taken from a corpse. No peer-ledger copy. Support increments are deterministic (+1 per witnessed event class). Cap each count at 32. No decay in this plan.

Blank slate: add `possession_legitimacy` to `BLANK_SLATE_SUBJECTIVE_STORES` in `src/simulation/new_agent_initialization.py`. A newborn does not receive a parent's doctrines.

### Analytical conventions (locked)

`src/analysis/possession_succession.py`. Pure functions over detached events plus optional detached ledger snapshots. `WorldEngine` does not import this module.

Per decedent episode (`CorpseCustodyOpened`):

| Field | Meaning |
| --- | --- |
| `physical_possession` | `corpse` until a `TakenFromCorpse`; then the living holder id. Later `Given` updates the holder. This is not legitimacy |
| `legitimacy_claims` | asserted doctrines and claimants. Empty is allowed |
| `conflict` | true when two different claimant ids, or two different doctrines, were asserted before the first take, or after it about the same item |
| `appropriation` | true when a corpse take's actor had no assertion, or their latest assertion's doctrine does not match the analysis alignment note below |
| `voluntary_transfer` | true when a later `Given` moves an item id that was in this episode |
| `convention_token` | plurality doctrine among *living* owners' support counts at `as_of_tick` in the death location. Tie → `contested`. No supports → `unformed` |

Alignment notes (analysis only, never a reject reason):

- `children_should_inherit` aligns only when kinship is in the harvest and the taker is in `children_of(decedent)`. Otherwise `not_applicable` or `unaligned`.
- `caregiver_inherits` aligns only when a dependency-care bond names the taker as caregiver of the decedent. Parent edges do not count.
- `group_owns` aligns only when group harvest shows taker and decedent co-members. No group id becomes a holder.
- `first_claimant_owns` aligns when the taker is the earliest `PossessionClaimAsserted.actor` for that episode.
- `nobody_owns` aligns for any corpse take. It still does not erase other agents' claims.

Loss of a holder (second death) opens a new episode for the items still held. It does not reopen the first decedent's law.

### Observer (locked)

Add exactly two semantic types, protocol id unchanged:

- `CORPSE_CUSTODY_OPENED`
- `POSSESSION_CLAIM_ASSERTED`

`TakenFromCorpse` maps to a third semantic `AGENT_TOOK_FROM_CORPSE`. Ground `Taken` stays `AGENT_TOOK_ITEM`. The tuple length is 54 today, including `EXPERIMENT_RESOLVED`. Three additions make 57. Sweep every `len(SEMANTIC_EVENT_TYPES) == 54` pin.

Command count becomes **36** (`AssertPossessionClaim` only). `Take` is not duplicated.

### Experiment AS (locked)

Id `possession_succession@1`. Off `OFF_GATE_MATRIX_EXPERIMENT_IDS` / V1 gate. Four arms, same seed and roster:

| Arm | Setup | Assertion |
| --- | --- | --- |
| `as-channel-off` | no object; scripted death while holding one item; on a later tick the other agent issues `Take` | `Take` rejected; item still on the dead inventory; no custody event; hash equals the pre-plan fixture |
| `as-custody-take` | v38 + object; same death; `Take` on a later tick | `CorpseCustodyOpened` lists the item; `TakenFromCorpse` moves it; decedent inventory no longer contains it; no doctrine field on the event |
| `as-no-auto-heir` | v38 + kinship edge parent→child; child colocated; no `Take` | after `Died`, child inventory unchanged; item still on the corpse |
| `as-claim-conflict` | v38; on a later tick two living agents assert different doctrines; neither is forced to `Take` | both `PossessionClaimAsserted` events exist; item still on the corpse; no resolution event |

Default batches do not enable AS.

### Metric families (locked)

Three siblings. Pin `METRIC_FAMILY_COUNT` from 71 to **74**. Empty harvest when the channel is off.

| Family id | Reads | Does not |
| --- | --- | --- |
| `possession_custody_outcomes` | custody events, corpse takes, later gives | doctrine text as physical fact |
| `possession_claim_conflict` | claim events, conflict flag | pick a winner |
| `inheritance_convention_distribution` | plurality `convention_token` per episode | write the token back into any ledger |

Research UI Analytics badges for these three ids only, overlay kind `research_inference`.

## Docs (mandatory checkpoint)

`/aif-implement` must route this through `/aif-docs` before done:

- `docs/physical-simulation.md` — corpse custody vs stuck pre-plan inventory; `Take` from corpse; `corpse_here`; items never deleted; system death is after commands
- `docs/cognition-runtime.md` — ledger, five doctrines, proposer, sanctions are not damage
- `docs/analysis-metrics.md` — three families, possession ≠ legitimacy
- `docs/architecture.md` — v38, replay-v16/codec v13 only when active, command 36, semantic count 57
- `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/ROADMAP.md` — M7 note; kinship still does not grant inheritance rights; knowledge handoff still deferred

Docs must not describe a doctrine as a world rule.

## Commit Plan

- **Commit 1** (after tasks 1–3): `feat: add possession succession config on runner-config-v38`
- **Commit 2** (after tasks 4–8): `feat: open corpse custody on death and allow claims without heirs`
- **Commit 3** (after tasks 9–11): `feat: record subjective possession legitimacy separate from holders`
- **Commit 4** (after tasks 12–14): `feat: measure emerging inheritance conventions`
- **Commit 5** (after task 15): `docs: describe possession succession without an inheritance law`

## Tasks

### Phase 1: Schema

- [x] Task 1: Add `RUNNER_SCHEMA_VERSION_V38`, `PossessionSuccessionSpec` (`policy_id`, `custody_mechanism=corpse` only), `SimulationRunnerConfig.possession_succession`, exact encode/decode, forbidden-law alias frozenset, and the reject codes in the flag×object matrix. Decode v23–v37 synthesizes `None`. Widen cultural, durable, historical-layer, repository, and genealogy schema allowlists through v38 without requiring those objects. Add v38 to the local `_experiment_schemas` set in `SimulationRunnerConfig` post-init and keep reject code `bounded_experimentation_requires_v36`. Cultural-only still forbids `population_lifecycle`. Do not edit matrix finalize priority (Task 14). Do not add a V3 flag.
  - Deliverable: Round-trip tests; rejects for v38 without the object, object on v37, `location`/`container`, `mode=disabled`, and each forbidden heir alias; v37 technique-lifecycle config still loads; v38 with only `possession_succession` loads with all V3 flags off; v38 plus optional kinship loads; v38 plus `bounded_experimentation` loads without `bounded_experimentation_requires_v36`.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `tests/unit/test_possession_succession_spec.py`
  - Logging: DEBUG decode with `present` and `custody_mechanism` only; INFO/raise stable reject codes; never log item ids at INFO
  - Depends on: none

- [x] Task 2: Add `EVENT_SCHEMA_REPLAY_V16` and codec `v13`. `checkpoint_schema_for_production` selects that pair only when `possession_succession_active` is true, ahead of experimentation v15/v12. Channel off keeps the previous pair. Accept `CorpseCustodyOpened`, `TakenFromCorpse`, and `PossessionClaimAsserted` only on v16. Replay-v15 decode rejects those kinds.
  - Deliverable: Version-selection tests for channel off, experimentation on without this object, and this object on (with and without experimentation). Unknown kind on v15 fails closed.
  - Files: `src/simulation/serialization.py`, `src/simulation/persistence.py`, `src/simulation/compatibility.py`, `src/world/events.py`, `tests/unit/test_possession_succession_replay_schema.py`
  - Logging: INFO `checkpoint_schema_selected` with replay version and codec; DEBUG channel flag; ERROR on kind/schema mismatch with the kind name only
  - Depends on: 1

- [x] Task 3: Add `corpse_custody_item_ids` on `WorldState` in `src/world/_state.py` (default empty) and thread it through `rebuild_world_state`. Add event dataclasses with exact fields: `CorpseCustodyOpened(body_id, location_id, item_ids)`, `TakenFromCorpse(item_id, source_body_id, resulting_holder_id)`, `PossessionClaimAsserted(decedent_id, doctrine, item_id|None)`. Add them to the `EventDetails` union, `require_event_details`, `target_id_for_details`, and the replay `match` arms. Projection updates the set and inventories. Persist the id list on the journal `WorldSnapshot` only when codec is `v13`; older codecs decode empty. Fold of a v15 log leaves the set empty.
  - Deliverable: Project a custody event, a corpse take, and a claim that does not change items. Reject a take projection whose item was not in the set. A v13 snapshot round-trips the ids; a v12 snapshot loads an empty set.
  - Files: `src/world/events.py`, `src/world/_state.py`, `src/world/_replay.py`, `src/simulation/journal.py`, `tests/unit/test_corpse_custody_projection.py`
  - Logging: DEBUG `corpse_custody_projected` with `item_count` and disposition (`opened`, `taken`, `claimed`); no item id lists at INFO
  - Depends on: 2

<!-- Commit checkpoint: tasks 1–3 -->

### Phase 2: WorldEngine behavior

- [x] Task 4: When the channel is on, every existing `Died` emission also emits `CorpseCustodyOpened` for that body's inventory in the same step. Cover needs death, exposure death, attack death, and lifespan death in `src/simulation/engine.py`. Do not add `Died` where it does not already exist. Do not emit `Died` from `src/world/_experiment_apply.py` `_set_health`. Channel off emits nothing new. Items stay on the dead body. Do not consult kinship, groups, caregivers, or doctrines. Do not delete items when the location is at `item_capacity`. Commands in the death tick run before this system step.
  - Deliverable: Tests for each of the four death causes with one held item and with an empty inventory; channel-off snapshots match the pre-plan event kinds; a full ground location does not drop or destroy the item; an experiment harm that zeroes health still has no custody event.
  - Files: `src/world/_physical.py`, `src/world/_rules.py`, `src/simulation/engine.py`, `src/world/_replay.py`, `tests/unit/test_death_corpse_custody.py`
  - Logging: INFO `corpse_custody_opened` with `body_id` and `item_count`; DEBUG death cause; ERROR `death_without_died` only for a new `DEAD` write that has no paired `Died` while the channel is on
  - Depends on: 3

- [ ] Task 5: Extend `Take` evaluation with `PossessionSuccessionRuleContext`. `WorldEngine.tick` passes that context beside `dependency_care_context`, or `None` when the object is absent. Ground take unchanged. Corpse take requires channel, item in `corpse_custody_item_ids`, holder `DEAD`, same location, and carry capacity. Success emits `TakenFromCorpse` and clears corpse holder. Context `None` rejects with `POSSESSION_SUCCESSION_CHANNEL_OFF` only for the corpse branch; ground take must not start returning that reason. `Give` to a dead recipient stays `DEAD_TARGET`.
  - Deliverable: Tests for ground take unchanged, corpse take success, remote corpse rejected, over-capacity rejected, channel-off corpse take rejected, give-to-corpse rejected, and a doctrine fixture that is not read (passing a ledger object is a type error).
  - Files: `src/world/_rules.py`, `src/world/possession_succession.py`, `src/simulation/engine.py`, `tests/unit/test_take_from_corpse.py`
  - Logging: DEBUG `take_evaluated` with `source` (`ground` or `corpse`) and reason code; INFO on success with source only; never log doctrine
  - Depends on: 4

- [ ] Task 6: When the channel is on, project a custody item held by a dead body at the observer's location as `ObservedItemPlacement.CORPSE_HERE` (`corpse_here`): entity id, name, kind, and load only. Do not put the holder's id on the item. Channel off never yields that placement. Add `build_occurrence_context` arms and `_public_facts_for_role` facts for `CorpseCustodyOpened`, `TakenFromCorpse`, and `PossessionClaimAsserted`: colocated witnesses get `decedent_id`, `item_ids`, and the doctrine token on a claim. `target_id_for_details` returns the decedent for custody and claims, and the item id for `TakenFromCorpse`.
  - Deliverable: A colocated living agent sees the corpse item and the custody occurrence; an agent in another location sees neither; channel off hides the item; the item projection has no holder id.
  - Files: `src/world/observations.py`, `src/world/_perception.py`, `src/world/events.py`, `tests/unit/test_corpse_custody_perception.py`
  - Logging: DEBUG `corpse_item_projected` with `item_count`; DEBUG `possession_occurrence` with kind and `item_count`; no holder id at INFO
  - Depends on: 4, 5

- [ ] Task 7: Add command `AssertPossessionClaim` (command count 36) and rule evaluation. Living colocated actor, dead decedent, doctrine in the closed five, optional item id must be in that corpse's custody. Emit `PossessionClaimAsserted`. No item, health, or ledger mutation in the engine. Second claim does not delete the first. Channel off rejects `POSSESSION_SUCCESSION_CHANNEL_OFF`. Wire the operation arm in `src/world/_operations.py` (missing arm is `MALFORMED_ENVELOPE`), command encode/decode in `src/simulation/serialization.py`, and causal-debugger kind maps in `src/simulation/causal_debugger.py`. Do not add `assert_possession_claim` to `LIFECYCLE_DENIED_COMMAND_KINDS_ALLOWLIST`.
  - Deliverable: Two different doctrines both succeed; item ids unchanged; dead actor rejected; missing item id rejected; command registry / proposal union includes the new command exactly once; a serialized command round-trips; a dependent stage can still select it.
  - Files: `src/world/actions.py`, `src/world/_rules.py`, `src/world/_operations.py`, `src/simulation/serialization.py`, `src/simulation/causal_debugger.py`, `tests/unit/test_assert_possession_claim.py`
  - Logging: INFO `possession_claim_asserted` with doctrine token and `item_scoped` bool; DEBUG reject reason; no ledger dump
  - Depends on: 5

- [ ] Task 8: Observer semantics for `CORPSE_CUSTODY_OPENED`, `AGENT_TOOK_FROM_CORPSE`, and `POSSESSION_CLAIM_ASSERTED`. Protocol id unchanged. Map kinds in `SEMANTIC_TYPE_BY_KIND` and the causal-debugger semantic map. Godot stays read-only (no new owner overlay). Length is 54 today and 57 after. Sweep `len(SEMANTIC_EVENT_TYPES) == 54` in `tests/unit/test_observer_contracts.py`, `test_experiment_perception.py`, `test_repository_observer.py`, `test_artifact_observer.py`, `test_developmental_stages_catalog_arm.py`, `test_environmental_dynamics_observer.py`, and the v3 regression tests for repositories, genealogy, durable records, developmental learning, mentorship, and cultural features.
  - Deliverable: Semantic tuple length is 57; old `AGENT_TOOK_ITEM` still maps from `take`/`taken`; a fixture event of each new kind exports the new label; no remaining `== 54` pin.
  - Files: `src/observer/version.py`, `src/observer/contracts.py`, `src/simulation/causal_debugger.py`, and the pin files named above
  - Logging: DEBUG `observer_semantic_mapped` with kind and semantic; no payload bodies
  - Depends on: 7

<!-- Commit checkpoint: tasks 4–8 -->

### Phase 3: Subjective legitimacy

- [ ] Task 9: Add owner-scoped `possession_legitimacy` ledger: doctrine supports (cap 32), witnessed claims, sanction tokens `none|criticism|shun|retaliation_considered`. Export types from the cognition package. Add the store name to `BLANK_SLATE_SUBJECTIVE_STORES`. Checkpoint field round-trips only on codec v13; absent on older codecs.
  - Deliverable: Blank-slate assert fails if a newborn ledger is non-empty; cap test; codec v12 checkpoint has no field; codec v13 round-trips supports without item-name strings.
  - Files: `src/agents/cognition/possession_legitimacy.py`, `src/simulation/new_agent_initialization.py`, `src/simulation/serialization.py`, `tests/unit/test_possession_legitimacy_ledger.py`
  - Logging: DEBUG `possession_ledger_updated` with owner id, doctrine token, and new count; INFO `blank_slate_asserted` includes the new store in the count; never log another owner's ledger
  - Depends on: 2

- [ ] Task 10: Cognition updater from the owner's own observations only, using the public facts from Task 6. +1 support when they witness a claim of that doctrine or when they themselves assert it. On a witnessed `TakenFromCorpse`, if their highest support contradicts alignment *as they locally believe* (they are applying their own doctrine, not the engine's), append `criticism` unless the doctrine is `nobody_owns`. `retaliation_considered` is writable only by an explicit owner update API used in tests, not by the engine, and it does not submit `Attack`. Do not read peer ledgers. Do not copy doctrines onto new agents. Kinship / care / group reads are optional and skipped with DEBUG when those channels are off.
  - Deliverable: Tests for each doctrine increment, `nobody_owns` take without sanction, two owners disagreeing after the same public claim, blank child after parent death, and no `Attack` command emitted by the updater.
  - Files: `src/agents/cognition/possession_legitimacy.py`, cognition observation hook used by the loop (same pattern as `apply_norm_update`), `tests/unit/test_possession_legitimacy_update.py`
  - Logging: DEBUG `possession_support` and `possession_sanction` with token; INFO only when a sanction token other than `none` is stored; no observation text
  - Depends on: 6, 7, 9

- [ ] Task 11: Deterministic proposer used only when the channel is on. If the observation contains a `corpse_here` item, the proposer may emit `AssertPossessionClaim` for that item using one of the five doctrine tokens, or `Take` of that item. The owner's highest support biases the choice. An empty ledger may still `Take` and may assert `nobody_owns`. Do not read kinship, the law catalog, or another agent's ledger. Do not submit `Attack`. Channel off leaves the existing command ranking unchanged.
  - Deliverable: Tests for empty-ledger take, empty-ledger `nobody_owns` claim, highest-support doctrine selected for a claim, channel-off ranking unchanged, and no `Attack` in the proposal.
  - Files: `src/agents/cognition/possession_legitimacy.py`, `src/agents/cognition/deliberation.py`, `tests/unit/test_possession_succession_proposer.py`
  - Logging: DEBUG `possession_proposal` with command tag and doctrine token or `take`; INFO only when a proposal is selected; never log another owner's supports
  - Depends on: 6, 10

<!-- Commit checkpoint: tasks 9–11 -->

### Phase 4: Analytical conventions

- [ ] Task 12: Implement `classify_possession_episodes` in `src/analysis/possession_succession.py` from the analytical conventions table. Inputs are detached events plus optional ledger snapshots, kinship children, care bonds, and group co-membership. Output separates `physical_possession` from `legitimacy_claims`. Ties yield `contested`. No supports yield `unformed`. Missing optional graphs yield `not_applicable` for that doctrine's alignment, not a false heir.
  - Deliverable: Known-answer tests for corpse-only, take, give-after-take, two-claim conflict, first-claimant alignment, child alignment only with a kinship harvest, caregiver not implied by a parent edge, and channel-off empty episode list.
  - Files: `src/analysis/possession_succession.py`, `src/analysis/__init__.py`, `tests/unit/test_possession_succession_classify.py`, `tests/architecture/test_v3_possession_succession_isolation.py`
  - Logging: DEBUG `possession_episode` with `convention_token`, `conflict`, and `appropriation`; no agent rosters at INFO
  - Depends on: 8, 10

- [ ] Task 13: Add the three metric families and pin `METRIC_FAMILY_COUNT` to 74. Sweep unit tests that assert `== 71`. Assemble only when the spec was present. Empty harvest when the object is absent. Research UI Analytics badges for the three family ids, kind `research_inference`, same pattern as technique-lifecycle badges. No new graph panel.
  - Deliverable: Known-answer metric rows; channel-off empty; badge test; no remaining `METRIC_FAMILY_COUNT == 71` pin.
  - Files: `src/analysis/specifications.py`, `src/analysis/possession_succession_metrics.py`, `src/analysis/metric_service.py`, `src/experiments/composition.py`, `src/experiments/collectors.py`, `clients/research-ui/src/epistemic.ts`, `clients/research-ui/src/views/AnalyticsPanel.svelte`, `clients/research-ui/src/epistemic.test.ts`, tests that pin the family count
  - Logging: DEBUG `possession_succession_metrics_assembled` with family ids and row counts; UI must not print doctrines as facts in badge titles
  - Depends on: 12

- [ ] Task 14: Register off-gate Experiment AS (`possession_succession@1`) with the four arms in the design section. Scripted `Take` and `AssertPossessionClaim` run on a tick after the death tick, because system death runs after commands. Insert `possession_succession_on` in `src/experiments/matrix_schema.py` immediately before `technique_lifecycle_on`. Add the id to `OFF_GATE_MATRIX_EXPERIMENT_IDS`. Export the builder. AS stays off the V1 gate. `as-channel-off` hash matches the pre-plan fixture.
  - Deliverable: Catalog tests for each arm; V1 regression gate and `test_v2_scientific_invariants` green with V3 flags off and without `possession_succession`; `as-no-auto-heir` proves the child inventory is unchanged; `as-custody-take` fails if the take is submitted on the death tick before system resolution and passes on the next tick.
  - Files: `src/experiments/catalog.py`, `src/experiments/__init__.py`, `src/experiments/matrix_schema.py`, `tests/unit/test_experiment_as.py`
  - Logging: INFO `experiment_arm_start` with arm id and schema version; DEBUG `possession_succession_active`
  - Depends on: 5, 7, 13

<!-- Commit checkpoint: tasks 12–14 -->

### Phase 5: Docs

- [ ] Task 15: Docs checkpoint listed in the Docs section. Confirm Alembic head `0017`, protocol id unchanged, command count 36, semantic count 57, write pair v16/v13 only when the channel is on, and no heir helper in `src/world`. Run `ruff check` on the changed Python set before this commit.
  - Deliverable: Doc updates; architecture isolation green; ruff clean on the changed set.
  - Files: `docs/architecture.md`, `docs/cognition-runtime.md`, `docs/analysis-metrics.md`, `docs/physical-simulation.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/ROADMAP.md`
  - Logging: none in docs; docs must say corpse custody is physical possession and doctrines are beliefs
  - Depends on: 14

<!-- Commit checkpoint: task 15 -->
