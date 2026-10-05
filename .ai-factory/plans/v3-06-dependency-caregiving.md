# Implementation Plan: V3-06 Dependency and Caregiving Mechanics

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-05
Improved: 2026-10-05 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M7 — V3 Generational Civilization"
Rationale: Deepens owned `generational_population` so DEPENDENT agents have configurable unmet-need consequences and caregiving can emerge from cognition/social factors without hard-coding parent→caregiver or claiming a new V3 flag slot.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M7 — V3 Generational Civilization
INFO [aif-plan] mode=ultra treated as full (richer plan); remaining args describe the feature
INFO [aif-plan] resolved plan file: .ai-factory/plans/v3-06-dependency-caregiving.md (format=slug)
INFO [aif-plan] plan name prefix v3- applied per user request; suggested stem `v3-06-dependency-caregiving`; git.create_branches=false so stem is description slug (branch-derived naming disabled)
INFO [aif-plan] RESEARCH.md absent; research_influenced_plan=false
INFO [aif-plan] plan_default_milestone=auto would surface M6 first; scope is explicitly v3-06 under M7 so linkage uses M7
INFO [aif-improve] applied refinement: lock need-state (physiology-backed + explicit learning/movement register on codec v9); shelter→existing shelter_factor/StructureKind.SHELTER; self_satisfy denial gate via prepare_action_batch; v28 = v27 accepted roots ∪ dependency_care with flag-conditional gates; Feed/Transport co-land PhysicalRules + denied allowlist + ItemKind.FOOD/WATER + domain-contract/typecheck + select_checkpoint_schema agreed-or; Godot catch-up KINSHIP_EDGE_RECORDED + care semantics; caregiving_cognition_mode config-only under dependency_care (no AgentCognitionSpec schema bump); COOPERATION_ACTION_KINDS + four MetricFamilyIds; Task 8←4, Task 12←7 deps

## Compatibility contract

This plan **does not own a new `V3CapabilityFlags` slot**. It deepens owned **`generational_population`** with objective dependency-need mechanics and optional caregiving cognition bias. It must preserve V1/V2 and AE–AH behavior when the new channel is off / defaults are passthrough.

1. V1/V2 invariants intact. `WorldEngine` remains the only objective mutation authority. Agents receive immutable per-agent `Observation` / `Perspective` only. `WorldEvent` records remain immutable and append-only. Subjective state stays outside the objective fold. Godot remains read-only. Deterministic replay continues. No scripted civilization / family-care outcomes.
2. Flag ownership unchanged. Keep `generational_population` and `kinship_inheritance` owned. Do **not** own `multi_polity_migration`, `institutional_economy`, `cultural_historical_memory`, or `multi_hop_testimony_tracking`.
3. Flags-off / channel-off = prior baseline. With all V3 flags off, or with lifecycle on but `dependency_care` absent/passthrough, trajectories and `exact_trajectory_hash` match the pre-plan baseline for AE/AF/AG/AH (kinship-only and combined) where applicable.
4. Schema bumps use accepted-set + exact key-set discipline. Never drop accepted V1/V2/V3 versions in the same change that adds a write version.
5. No biological sex, mating, pregnancy, gestation, or lactation simulation. Dependency is stage-derived status + configurable need deficits — not biology.
6. **Never hard-code parent → caregiver.** Objective kinship edges must not auto-assign caregivers, auto-emit care commands, or auto-write relationship valence. Care may involve kin, non-kin, shared caregivers, or **neglect**.
7. **WorldEngine determines objective physical consequences.** Agent cognition determines whether care is offered. Analysis metrics never feed cognition.
8. Preserve v3-02–v3-05 locks: binary `DependencyStatus` (`DEPENDENT` | `INDEPENDENT`); closed Observation `lifecycle` object; blank-slate deny-list; ELDER ≠ leader; related ≠ affection/trust/loyalty; Alembic head `0017` by default.
9. Optional tracing/analysis/observer presentation stay outside the objective fold / `EvidenceManifest`.
10. Cultural inheritance / knowledge handoff remains deferred under the `kinship_inheritance` flag slot (not this plan).

## Goal

Implement dependency mechanics for agents that cannot yet fully satisfy their own survival (and related) needs:

- Configurable objective need kinds that DEPENDENT agents may fail to self-satisfy: `food`, `water`, `safety`, `movement`, `shelter`, `learning`
- Objective unmet-need consequences applied by `WorldEngine` (physiology / placement / learning-rate coupling as configured)
- Caregiving as an **emergent** behavior from relationships, goals, norms, kinship *beliefs*, attachment-shaped dimensions, and social expectations — not from genealogy hardwiring
- Structured care/help actions only where existing `Give` / `Help` / teaching / movement commands are insufficient
- Explicit allowance for neglect, shared caregiving, and non-relative caregiving
- Experimental metrics: dependency survival, caregiver diversity, caregiving burden, intergenerational cooperation
- Off-gate Experiment AI proving the channel

## Design Decisions

### Invariant freeze (non-negotiable)

1. `WorldEngine` remains the only authority over objective need deficits, care-action physical effects, and death/physiology outcomes.
2. Agents receive immutable agent-specific `Observation` only; they never receive a “must_care_for” assignment from the engine.
3. `WorldEvent` records remain immutable; authoritative history stays append-only.
4. Subjective caregiving motives / kinship beliefs may be wrong and never fold into objective replay.
5. LLM output remains non-authoritative.
6. No scripted “parents_always_care / family_bonded / neglect_forbidden / village_raised_child” booleans.
7. Godot remains read-only; this plan may add semantic types for new care events but **no** family-care presentation chrome.
8. Runs remain reproducible where claimed (explicit seeds, deterministic streams).

### Capability ownership (locked)

1. Remain on owned `generational_population`. Enabling dependency-care mechanics requires the lifecycle channel on (`generational_population=True`) plus exact `dependency_care` config on `runner-config-v28`.
2. `kinship_inheritance` remains optional. When kinship is on, objective edges are **available as research facts and optional gated perception only**; cognition may use *subjective* kinship beliefs / relationship dimensions — never an engine rule `if parent then Care`.
3. Other unowned V3 flags still fail closed.
4. When `dependency_care` is absent / passthrough defaults: physical, action, and AE–AH bit-identity match pre-plan for the same roster and seeds (no new events/types from this channel).

### Scope split (locked)

| This plan (v3-06) | Deferred |
| --- | --- |
| Configurable DEPENDENT need deficits + unmet consequences | Cultural inheritance / estate transfer |
| Minimal structured care actions (Feed / Transport / need-tagged Help reuse) | Full affective attachment subsystem |
| Emergent care selection via relationships/goals/norms/beliefs | Hard-coded household / nursery roles |
| Neglect / shared / non-kin care as first-class outcomes | Godot family-care chrome / Research UI dashboards |
| Four analysis metrics + Experiment AI | Owning remaining V3 flag slots |

### Runner configuration versioning (locked)

Introduce `RUNNER_SCHEMA_VERSION_V28 = "runner-config-v28"`:

- Exact root key set = **v27 accepted roots** ∪ sibling root object **`dependency_care`**. Preserve v27’s flag-conditional gates (kinship-only forbids lifecycle/init; generational requires lifecycle/init rules as today). Do **not** treat “full v27” as an unconditional copy of every optional root.
- Default write remains `runner-config-v4` when all V3 flags are off and no existing mode requires a higher schema.
- `dependency_care` present / non-passthrough ⇒ `schema_version == runner-config-v28` and `generational_population=True` with exact `population_lifecycle` (stable reject `dependency_care_requires_v28` / `dependency_care_requires_lifecycle`). Mid-run blank-slate admits still follow v25+ `new_agent_initialization` rules when used.
- `generational_population=False` forbids non-empty `dependency_care` (reject `dependency_care_without_lifecycle_flag`) — kinship-only v27/v28 profiles cannot enable dependency care.
- Decode of v23–v27 synthesizes no `dependency_care` object (absent ≡ channel off / passthrough).
- Widen **every** mode allowlist currently capped at `v27` to also accept `v28`.
- Gate rewrite: `generational_population=True` accepts `{v24,v25,v26,v27,v28}`; `kinship_inheritance=True` still accepts `{v27,v28}` (kinship config rules unchanged; v28 may carry kinship + dependency_care together).
- `experiments/matrix_schema.py` finalize/allowlist accepts `v28`; finalize selects `v28` when `dependency_care` present; AE stays v24; AF v25; AG v26; AH v27; default finalize stays `v4` when V3 flags off.
- Update `simulation/compatibility.py` version matrix row for v28 + dependency-care write-pair note.

### DependencyCareSpec (exact root sibling — locked)

Root key `dependency_care` exact children:

| Key | Role |
| --- | --- |
| `enabled_needs` | Ordered frozen list of closed need ids (subset of the closed set below; empty forbidden when object present — use absent object for off) |
| `need_policies` | Exact map need_id → policy object (must cover every `enabled_needs` entry exactly once) |
| `care_action_policy` | Exact object gating which structured care actions are legal |
| `perception_mode` | Closed id for dependent-need visibility (below) |
| `caregiving_cognition_mode` | Closed id: `disabled` (default) \| `deterministic` — **not** a `V3CapabilityFlags` bit and **not** an `AgentCognitionSpec` / runner cognition-mode enum (lives only under this object; no extra schema bump for teaching-style mode keys) |

**Closed need ids (exact):**

| Id | Objective meaning (WorldEngine) |
| --- | --- |
| `food` | Hunger / food intake self-satisfaction (`ItemKind.FOOD` / eat path) |
| `water` | Thirst / drink self-satisfaction (`ItemKind.WATER` / drink path) |
| `safety` | Health protection / help-relief pathway |
| `movement` | Self-initiated relocation (`Move` / `Flee` legality interaction) |
| `shelter` | Access via existing `location.shelter_factor` and/or `StructureKind.SHELTER` — **do not** invent a parallel shelter ontology |
| `learning` | Ability to accrue skill/learning without external teaching assist |

Forbidden need ids / aliases: `love`, `attention`, `emotion`, `parenting`, `attachment` as objective needs, biology keys, role tokens (`nanny`, `guardian`).

**`need_policies[need_id]` exact keys:**

| Key | Role |
| --- | --- |
| `self_satisfy` | bool — when false and agent is `DEPENDENT`, self-path for that need is blocked via admission denial (Task 4) and/or ineffective |
| `unmet_accrual_per_tick` | Non-negative float — objective deficit progression while unmet (need-specific mapping documented in Task 1/5) |
| `critical_threshold` | Float in `[0, 1]` — above which WorldEngine applies the configured critical consequence |
| `critical_consequence` | Closed id per need (below) |

**Critical consequences (closed, per need family):**

| Need | Allowed `critical_consequence` ids |
| --- | --- |
| `food` / `water` | `accelerate_hunger` / `accelerate_thirst`, `health_damage`, `death_when_physiology_terminal` (reuse existing death authority — do not invent parallel death) |
| `safety` | `health_damage`, `no_extra` |
| `movement` | `no_extra` (effect is action denial + optional fatigue; no teleport) |
| `shelter` | `fatigue_accrual`, `health_damage`, `no_extra` (compose with existing exposure/`shelter_factor` path in `world/_physical.py`) |
| `learning` | `learning_rate_zero`, `no_extra` (never invents skills; only scales/blocks existing skill growth when skill mode active) |

**`care_action_policy` exact keys:**

| Key | Role |
| --- | --- |
| `allow_feed` | bool — caregiver applies consume effects to colocated DEPENDENT using held item |
| `allow_transport` | bool — caregiver relocates colocated DEPENDENT with self |
| `allow_help_safety` | bool — existing `Help` counts as safety care when target is DEPENDENT |
| `allow_teach_learning` | bool — existing teaching interaction may satisfy `learning` need markers (no new Teach command) |
| `require_colocated` | bool — default `true`; care actions fail closed if not colocated |

**`perception_mode` closed ids:**

| Id | Behavior |
| --- | --- |
| `none` | **Default.** No new Observation fields for dependency needs |
| `self_and_colocated` | Agent may observe closed need-deficit summaries for self and colocated bodies that already expose `lifecycle` (never omniscient roster dump) |

Forbidden: `omniscient`, `assigned_caregiver_broadcast`.

**Self-satisfy → denied command kinds (locked):**

When `self_satisfy=false` for an enabled need and the agent is `DEPENDENT`, WorldEngine denies the corresponding self-path kinds at `prepare_action_batch` (compose with stage `denied_command_kinds`; union of denials). Initial map:

| Need | Denied self kinds (DEPENDENT only) |
| --- | --- |
| `food` | `eat` |
| `water` | `drink` |
| `movement` | `move`, `flee` |
| `shelter` | (no extra kind if shelter is environmental; optional `sleep` only if tests prove self-sleep bypasses shelter policy — default: no sleep deny) |
| `safety` | (no self-help deny — safety is received care) |
| `learning` | (no command deny — learning-rate gate only) |

Stable reject reason string e.g. `dependency_care_self_satisfy_denied` → `ActionResolutionReason.STRUCTURAL_REJECTION`. Caregiver `Feed`/`Transport`/`Help`/`Give` remain legal when policy allows. `INDEPENDENT` agents are never denied by this map.

### Objective domain model (locked)

Prefer package home under `world` (authority) + thin `simulation` / cognition wiring:

- `world/dependency_care.py` (pure types + resolvers) — **not** `social/`
- Mutated only via `WorldEngine` / private world modules
- `world` must not import `social` (existing import-linter contract)

**Need-state storage (locked):**

1. Prefer **physiology-backed** signals for `food` / `water` / `safety` / `shelter` (hunger, thirst, health, existing `shelter_factor` / exposure path) — do not invent a second body store for those.
2. Maintain a small explicit per-agent **deficit register** only for needs physiology cannot express (`learning`, and optional movement-assist markers if denial alone is insufficient for metrics/perception).
3. Any explicit register must live on the engine snapshot / journal (codec **v9** field, e.g. `dependency_need_registers`) and round-trip on checkpoint/restore; never subjective stores.
4. Tick progression that only mutates physiology needs no extra register fields beyond events already produced by the physical step.

Frozen types (names illustrative; Pydantic-free domain style):

- `CareNeedId` — closed string enum / StrEnum for the six ids
- `DependencyNeedRegister` — sparse per-agent map of non-physiology need deficits (checkpointed)
- `CareAssistKind` — closed: `feed`, `transport`, `help_safety`, `teach_learning`
- Pure helpers: `needs_requiring_assistance(status, policies)`, `is_need_critical(...)`, `care_action_legal(...)`, `self_satisfy_denied_kinds(...)`

Rules:

1. Binary `DependencyStatus` stays; do **not** expand to caregiver/ward roles.
2. `INDEPENDENT` agents are not forced into care recipient mechanics by this channel (they may still receive ordinary `Help`/`Give`).
3. Unmet need progression is deterministic and seed-free given state + config (no hidden RNG in deficit accrual).
4. Care actions never write relationship dimensions, norms, beliefs, or SelfModel from WorldEngine.

### Structured actions (locked — minimal set)

Reuse first; add only two command kinds if policy enables them:

| Action | Status | Role |
| --- | --- | --- |
| `Give` | Existing | Transfer food/water **items** to dependent inventory when dependents can still `Eat`/`Drink` |
| `Help` | Existing | Safety care → health/fatigue effects already implemented; tag analysis as care when target DEPENDENT + `allow_help_safety` |
| Teaching interaction | Existing mode | Learning care — cognition mode only; WorldEngine records teaching occurrence as today |
| **`Feed`** | **New iff `allow_feed`** | Caregiver holds item; **discriminate by `ItemKind.FOOD` vs `ItemKind.WATER`**; applies eat/drink relief to **colocated DEPENDENT** without requiring dependent self-`Eat`/`Drink` legality |
| **`Transport`** | **New iff `allow_transport`** | Caregiver + colocated DEPENDENT move together to `destination_id` (movement + shelter relocation via destination’s existing shelter_factor); fatigue on caregiver per `PhysicalRules` |

Do **not** add: `Parent`, `AssignCaregiver`, `Bond`, `Nurture`, `Adopt`, or social-role commands.

`Feed` / `Transport` join the closed `AgentCommand` union with accepted-set discipline (`tests/unit/test_domain_contract_evolution_policy.py`, typecheck exhaust). Extend `LIFECYCLE_DENIED_COMMAND_KINDS_ALLOWLIST` with `feed` / `transport` so stage effects may deny them for caregiver stages when configured. Co-land `PhysicalRules` constants for feed relief / transport fatigue (mirror `help_health_gain` / `help_fatigue`).

Event details:

- Prefer extend `Helped` only if fields stay compatible; otherwise add `Fed` / `Transported` occurrence details with exact physiology/location deltas (mirror `Helped`/`Moved` patterns).
- Introduce `EVENT_SCHEMA_REPLAY_V12` + codec **`v9`** when dependency-care channel is active at run start; else keep existing pair when channel off.
- **Co-land in one change:** `ACCEPTED_EVENT_SCHEMA_VERSIONS`, `ACCEPTED_PERSISTENCE_CODEC_VERSIONS`, `world/_replay.py`, `simulation/serialization.py`, `simulation/journal.py` snapshot field(s) (`dependency_need_registers` and/or care graph none), `simulation/compatibility.py` matrix, both `checkpoint_schema_for_production` **and** `engine.select_checkpoint_schema` agreed-or chain:

  `dependency_care_active` → `(EVENT_SCHEMA_REPLAY_V12, "v9")`;  
  else kinship → `(v11, "v8")`; else provenance → `(v10, "v7")`; … unchanged remainder.

  Add `WorldEngine.dependency_care_channel_active` (pass `dependency_care_active=` from runner) parallel to lifecycle/kinship channel flags.

### Cognition / emergence (locked)

1. **No engine caregiver assignment.** WorldEngine never selects who must care.
2. When `caregiving_cognition_mode=disabled` (default): existing deliberation only; no care-specific candidate scoring. Channel may still apply objective need deficits if `dependency_care` is present — enabling “neglect under physics” without care bias.
3. When `caregiving_cognition_mode=deterministic`: add a **bias / candidate ranking** module (e.g. `agents/cognition/caregiving.py`) that may boost care-shaped futures (`Feed`/`Transport`/`Help`/`Give`/teach) using **only** owner-scoped subjective inputs:
   - `DirectedRelationshipProfile` dimensions (`affection`, `trust`, `familiarity`, `debt`, `respect`, subjective `dependency`, etc.)
   - Active goals / drives (safety, belonging, etc.)
   - Social norms / conventions ledgers when those modes are on
   - Subjective kinship **beliefs** or communicated testimony (may be false)
   - Optional perceived need deficits when `perception_mode=self_and_colocated`
4. **Mode wiring (locked):** read mode only from `dependency_care.caregiving_cognition_mode`. Do **not** add `CaregivingMode` to `AgentCognitionSpec` or bump runner schema for a teaching-style cognition-mode key. Runner binds the bias module when the dependency-care object is present and mode is `deterministic`.
5. **Anti-hardcode:** bias module must **not** import or query objective `world.kinship` / engine kinship APIs. Parent/child objective edge alone must not force care; non-kin with high affection may outrank kin; zero care acts is a legal trajectory (neglect).
6. Shared caregiving: multiple agents may care for the same DEPENDENT across ticks; no exclusive caregiver lock.
7. Care bias must not call analysis metrics APIs and must not read other agents’ private cognition.

### Observation (locked)

1. Default `perception_mode=none` ⇒ **no** new Observation keys (channel-off wire unchanged aside from optional new command kinds appearing in legality only when enabled).
2. When `self_and_colocated`: additive closed optional object (e.g. `dependency_needs`) with **exact minimal keys** only (need id → quantized deficit band / critical flag). Live/restored observation parity is the hard gate.
3. Do not widen closed `lifecycle` object (`chronological_age`, `stage`, `dependency_status` only).

### Analysis metrics (locked)

Register analysis-only families (never imported by cognition):

| Family id | Version string | Core signals |
| --- | --- | --- |
| `dependency_survival` | `dependency_survival@1` | Survival / lifespan outcomes of agents while `DEPENDENT` (and cohort contrast vs `INDEPENDENT` when sample allows) |
| `caregiver_diversity` | `caregiver_diversity@1` | Unique caregiver agents per dependent; entropy / concentration of care acts |
| `caregiving_burden` | `caregiving_burden@1` | Care acts, helper fatigue deltas, care-time share per caregiver |
| `intergenerational_cooperation` | `intergenerational_cooperation@1` | Care/help/give/teach/`feed`/`transport` acts whose actor/target `generation_index` differ (requires lifecycle records; kinship optional) |

Follow `kinship_genealogy@1` / `spatial_control@1` registration: `MetricFamilyId`, specification, compute module, `metric_service` wiring, unit tests. Extend `COOPERATION_ACTION_KINDS` (or cooperation counting set) with `feed` / `transport`. Keep `all_metric_specifications` / `frozenset(MetricFamilyId)` tests green. NetworkX allowed inside analysis only if needed for diversity graphs.

### Experiment AI (locked)

- Catalog arm `experiment-ai-dependency-caregiving` on **runner-config-v28**, off the V1 gate.
- Profile: `dependency_caregiving_profile` requiring `generational_population=True` + exact `dependency_care` (+ lifecycle). May optionally enable `kinship_inheritance` on a dual-flag arm **without** treating kinship as caregiver assignment.
- Arms (minimal set):
  - **neglect**: needs enabled, cognition mode `disabled` or care-averse goals → DEPENDENT unmet needs progress / survival drops; self_satisfy denials prevent self-rescue
  - **emergent care (non-kin)**: no kinship edges; high affection / norms bias → care acts from non-relatives
  - **shared caregiving**: ≥2 caregivers assist one DEPENDENT across ticks
  - **kinship-belief bias (optional)**: kinship on with perception none/self; prove objective parent edge alone does not force care; subjective belief/relationship path may bias
  - **teach-learning**: `learning` need + teaching mode satisfies learning marker without inventing skills when skill mode off
- Prove: flags-off / channel-off hashes stable; AE–AH unchanged when `dependency_care` absent; V1 gate + `test_v2_scientific_invariants` green under V3 flags-off.
- Matrix allowlist includes AI without enabling on default batches.

### Observer (locked)

- If `Fed` / `Transported` (or equivalent) events land: append semantic types (e.g. `AGENT_FED`, `AGENT_TRANSPORTED`) and bump `len(SEMANTIC_EVENT_TYPES)` from **41 → 43** (exact count = 41 + number of new types; if catching up Godot-only gaps, Python count remains authoritative). Update closed-catalog pins.
- Mirror new types (and catch up missing `KINSHIP_EDGE_RECORDED`) in Godot `models.gd` / event_log labels so presentation stays aligned; protocol stays `observer-protocol-v1`. No family-care / nursery chrome.
- Extend `causal_debugger` semantic tables if user-visible (metadata-only).

### Out of scope

- Hard-coded parent→caregiver or household roster roles
- Biological nursing / pregnancy / mating
- New V3 capability flag for caregiving
- Cultural inheritance / knowledge handoff engines
- Full attachment Personality subsystem
- Scripted “successful parenting” mandates
- Owning `multi_polity_migration`, `institutional_economy`, `cultural_historical_memory`, `multi_hop_testimony_tracking`
- Full Research UI / Godot caregiving dashboards
- Alembic `0018` by default
- Auto-writing care obligations into SelfModel or relationship dimensions from WorldEngine
- New `AgentCognitionSpec` caregiving enum / teaching-style runner schema bump for the bias mode

## Commit Plan

- **Commit 1** (after tasks 1–3): `feat(v3): add dependency-care contracts and runner-config-v28`
- **Commit 2** (after tasks 4–7): `feat(v3): self-satisfy denials, unmet needs, Feed/Transport, observer semantics`
- **Commit 3** (after tasks 8–10): `feat(v3): caregiving cognition bias without parent hardcoding`
- **Commit 4** (after tasks 11–13): `feat(v3): dependency-care metrics and Experiment AI`
- **Commit 5** (after tasks 14–15): `docs(v3): dependency caregiving seams and flags-off regression proofs`

## Tasks

### Phase 1: Domain & config contracts

- [x] Task 1: Add objective dependency-care domain types and pure resolvers
  - Deliverable: Frozen `CareNeedId`, need policy types, `DependencyNeedRegister` (sparse non-physiology deficits), pure helpers including `self_satisfy_denied_kinds`. Package under `world/dependency_care.py` — **not** `social/`. No parent/caregiver role types. **Lock storage:** physiology-backed for food/water/safety/shelter via existing hunger/thirst/health/`shelter_factor`/`StructureKind.SHELTER`; explicit register only for `learning` (+ optional movement markers); register is engine/journal state for codec v9 — never subjective.
  - LOGGING: DEBUG on resolve `{agent_id, need, deficit, critical}`; ERROR with stable `code=`; never log social valence or “caregiver_id”.
  - Files: `src/world/dependency_care.py`, `src/world/__init__.py`, `tests/unit/test_dependency_care_resolvers.py`
  - Depends on: —

- [x] Task 2: Introduce `DependencyCareSpec` / runner-config-v28 (no new V3 flag)
  - Add `RUNNER_SCHEMA_VERSION_V28`; exact root = **v27 accepted roots** ∪ `{dependency_care}` preserving v27 flag-conditional kinship-only vs lifecycle gates; encode/decode exact keys; reject forbidden need/role keys; `dependency_care` requires `generational_population=True` + exact `population_lifecycle` (+ init rules when mid-run admits apply); widen allowlists capped at v27; matrix finalize selects v28 when dependency_care present; update compatibility matrix notes.
  - Fail closed still for unowned V3 flags. Do **not** add a new flag to `_V3_OWNED_CAPABILITY_FLAGS`. `caregiving_cognition_mode` stays under `dependency_care` only (no `AgentCognitionSpec` enum).
  - LOGGING: INFO on schema select `{schema_version, generational_population, enabled_needs, caregiving_cognition_mode, perception_mode}`; stable reject codes.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `src/simulation/runner.py`, `src/experiments/matrix_schema.py`, `tests/unit/test_runner_config_v28_*.py`, extend `tests/unit/test_v3_scaffolding_gate.py`
  - Depends on: Task 1

- [x] Task 3: Wire channel-active flag into engine/bootstrap without behavior change
  - Pass `DependencyCareSpec` into engine context; expose `dependency_care_channel_active`; channel-off allocates nothing and emits no new events. Unit-test construction logging and reject paths.
  - LOGGING: INFO `{dependency_care_active, need_count}` at construction.
  - Files: `src/simulation/engine.py`, `src/simulation/runner.py`, unit tests
  - Depends on: Task 2

### Phase 2: Objective consequences & care actions

- [x] Task 4: Self-satisfy admission denials for DEPENDENT agents
  - Deliverable: Map `self_satisfy=false` → concrete `AgentCommand.kind` denials per Design Decisions table; apply in `prepare_action_batch` (or equivalent) composed with stage `denied_command_kinds` (union). DEPENDENT only; `INDEPENDENT` untouched. Stable reason `dependency_care_self_satisfy_denied` → `STRUCTURAL_REJECTION`. Unit-test: Eat/Drink/Move blocked for DEPENDENT while caregiver `Feed`/`Transport`/`Help`/`Give` still legal when policy allows.
  - LOGGING: DEBUG on denial `{agent_id, need, command_kind, code=dependency_care_self_satisfy_denied}`; never log caregiver assignment.
  - Files: `src/simulation/engine.py`, `src/world/_operations.py` (or batch prep), `src/world/dependency_care.py`, `tests/unit/test_dependency_care_self_satisfy_denials.py`
  - Depends on: Task 3

- [x] Task 5: Unmet-need tick progression in WorldEngine
  - While channel on: for living `DEPENDENT` agents, apply configured unmet accrual / critical consequences using existing physiology/death/learning-rate/`shelter_factor` seams (compose with v3-04 stage factors and Task 4 denials; document composition order). Persist explicit registers on codec v9 snapshot. `INDEPENDENT` skip recipient deficits. Deterministic twin-run proof.
  - LOGGING: DEBUG per-tick unmet `{agent_id, need, deficit}` (metadata only); INFO on critical transitions; ERROR never for expected neglect.
  - Files: `src/simulation/engine.py`, `src/world/_physical.py` or sibling helpers, journal/serialization register field, `tests/unit/test_dependency_need_progression.py`
  - Depends on: Task 3, Task 4

- [x] Task 6: Add minimal `Feed` / `Transport` commands + events + replay write pair
  - Extend closed `AgentCommand` with `Feed` / `Transport`; evaluate/mutate (colocated, DEPENDENT target, `ItemKind.FOOD`/`WATER` for Feed, destination for Transport); add `Fed`/`Transported` details; co-land `EVENT_SCHEMA_REPLAY_V12` + codec `v9` + ACCEPTED sets + compatibility matrix + **both** `checkpoint_schema_for_production` and `engine.select_checkpoint_schema` agreed-or (`dependency_care_active` first); `PhysicalRules` feed/transport constants; extend `LIFECYCLE_DENIED_COMMAND_KINDS_ALLOWLIST`; update `test_domain_contract_evolution_policy.py` + typecheck exhaust.
  - Reuse `Help` for safety without schema break when possible.
  - LOGGING: INFO on successful care mutate `{actor, target, assist_kind, tick}`; WARN/DEBUG on structural rejects with stable reason codes.
  - Files: `src/world/actions.py`, `src/world/events.py`, `src/world/_rules.py`, `src/world/_operations.py`, `src/world/_replay.py`, `src/world/lifecycle_effects.py`, `src/simulation/serialization.py`, `src/simulation/persistence.py`, `src/simulation/journal.py`, `src/simulation/engine.py`, `tests/unit/test_dependency_care_actions_replay.py`, domain-contract/typecheck tests
  - Depends on: Task 3, Task 4, Task 5

- [x] Task 7: Observer semantic mapping for new care events (+ Godot catch-up)
  - Append new semantic types; update `len(SEMANTIC_EVENT_TYPES)` pins (41 → exact new count); map domain kinds; catch up Godot `models.gd` / event_log with `KINSHIP_EDGE_RECORDED` plus new care types; causal debugger labels if required; no family-care chrome; protocol stays v1.
  - LOGGING: follow existing observer metadata-only patterns.
  - Files: `src/observer/version.py`, `clients/godot-observer/scripts/protocol/models.gd`, event_log/router as needed, causal debugger, observer unit tests
  - Depends on: Task 6

### Phase 3: Perception, cognition emergence, isolation

- [x] Task 8: Perception modes — default none; optional self_and_colocated needs
  - Implement perception modes; live/restored observation parity tests; do not widen `lifecycle` object; perception must not form memories/beliefs.
  - LOGGING: DEBUG on visible need fact counts; never log assigned caregiver.
  - Files: `src/world/_perception.py`, observation contracts, `tests/unit/test_dependency_care_perception_parity.py`
  - Depends on: Task 5, Task 6

- [x] Task 9: Deterministic caregiving cognition bias (no parent hardcode)
  - Implement bias when `dependency_care.caregiving_cognition_mode=deterministic` using relationships, goals/drives, norms/conventions (when on), subjective kinship beliefs/testimony, and optional perceived needs. Mode `disabled` is passthrough. Bind from runner via dependency_care config only (no `AgentCognitionSpec` enum). **Forbid** imports of objective kinship APIs into the bias module. Prove: objective parent edge alone does not force care; non-kin care possible; neglect possible; shared caregivers possible across ticks.
  - LOGGING: DEBUG on candidate scores `{owner_id, target_id, assist_kind, score_components_hash}` — no payload dumps; INFO when mode enabled at runtime bind.
  - Files: `src/agents/cognition/caregiving.py` (or sibling), deliberation/intention integration, `src/simulation/runner.py` bind, `tests/unit/test_caregiving_bias_emergence.py`
  - Depends on: Task 4, Task 5, Task 6, Task 8

- [x] Task 10: Architecture gates — WorldEngine ≠ caregiver assignment; no auto social writes
  - Tests: care mutate paths do not revise relationship dimensions / SelfModel / beliefs; forbid world→social imports for dependency_care; assert no `parent_id` caregiver map in engine; analysis metrics not imported by cognition; caregiving bias does not import `world.kinship`.
  - LOGGING: N/A for architecture tests; production paths metadata-only.
  - Files: `tests/architecture/test_v3_dependency_care_isolation.py`, scaffolding invariant extensions
  - Depends on: Task 6, Task 9

### Phase 4: Metrics & experiment

- [x] Task 11: Analysis metrics for dependency survival, caregiver diversity, burden, intergenerational cooperation
  - Add four `MetricFamilyId`s + specs + compute modules; wire `metric_service`; extend `COOPERATION_ACTION_KINDS` (or equivalent) with `feed`/`transport`; keep family-count / `all_metric_specifications` tests green; unit tests with synthetic events/lifecycle records; never feed cognition.
  - LOGGING: metadata-only metric ids/counts.
  - Files: `src/analysis/dependency_survival_metrics.py`, `src/analysis/caregiver_diversity_metrics.py`, `src/analysis/caregiving_burden_metrics.py`, `src/analysis/intergenerational_cooperation_metrics.py` (names flexible), `src/analysis/specifications.py`, `src/analysis/metric_service.py`, `src/analysis/__init__.py`, unit tests
  - Depends on: Task 5, Task 6

- [x] Task 12: Inspection scaffolding for dependency-need / care-act research DTOs
  - Detached objective projection suitable for later UI (per-agent need deficits, recent care acts). Prefer existing inspection patterns; HTTP only if it fits current objective inspection without Alembic.
  - LOGGING: INFO/DEBUG on query counts — no cognition feedback.
  - Files: `src/simulation/inspection.py`, optional `src/api/` route, unit tests
  - Depends on: Task 5, Task 6

- [x] Task 13: Experiment AI + catalog profile
  - Add `experiment-ai-dependency-caregiving` / `dependency_caregiving_profile` on v28; arms per Design Decisions (including self_satisfy denial neglect); off V1 gate; AE–AH unchanged when channel absent; matrix allowlist includes AI.
  - LOGGING: experiment coordinator metadata-only.
  - Files: `src/experiments/catalog.py`, `tests/unit/test_dependency_care_catalog_arm.py`
  - Depends on: Task 2, Task 4, Task 6, Task 8, Task 9, Task 11

### Phase 5: Regression & docs

- [x] Task 14: Channel-off / AE–AH bit-identity regression
  - Prove V1 gate + `test_v2_scientific_invariants` under V3 flags off; dependency_care absent leaves AE/AF/AG/AH hashes unchanged; unowned V3 flags still `capability_unimplemented`; v28 round-trip.
  - LOGGING: follow existing regression helpers.
  - Files: extend `tests/unit/test_v3_*` compat/flag tests
  - Depends on: Task 13

- [x] Task 15: Documentation checkpoint (`/aif-docs`)
  - Update architecture/downstream V3 contract notes: v28 + `dependency_care`, self_satisfy denials, Feed/Transport, emergent caregiving invariants (no parent hardcode; neglect/shared/non-kin allowed), metrics, Experiment AI off V1 gate. DESCRIPTION.md V3 paragraph if required by docs skill.
  - LOGGING: N/A.
  - Files: `docs/architecture.md`, related docs pages, `.ai-factory/DESCRIPTION.md` as needed
  - Depends on: Task 14

## Implementation Notes

- Prefer extending existing physiology / `Help` / teaching / `shelter_factor` seams over inventing parallel body stores.
- Compose carefully with v3-04 `stage_capability_effects` (denied kinds, learning_rate_factor, fatigue) **and** Task 4 self_satisfy denials: document and test the order of application (union of denials; physiology accrual after admission).
- Subjective `RelationshipDimension.DEPENDENCY` is **not** the same as objective `DependencyStatus` — do not conflate in APIs or metrics labels that could leak into cognition prompts.
- Keep experiment collectors and metric documents out of CognitiveLoop / memory formation / prompts / action selection.

## Next Steps

Plan refined with 15 tasks.
Plan file: `.ai-factory/plans/v3-06-dependency-caregiving.md`

To start implementation, run:
`/aif-implement`

To view tasks:
`/tasks` (or use TaskList)

Suggest `/clear` or `/compact` if context is getting heavy before implementation.
