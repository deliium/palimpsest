# Implementation Plan: V3-04 Aging and Developmental Stages

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-05
Improved: 2026-10-05 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M7 — V3 Generational Civilization"
Rationale: Extends owned `generational_population` with configurable developmental-stage capability effects, gradual aging, lifespan distributions, and deterministic EOL — without claiming kinship/social-authority flags.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M7 — V3 Generational Civilization
INFO [aif-plan] mode=full; remaining args describe the feature
INFO [aif-plan] resolved plan file: .ai-factory/plans/v3-04-developmental-stages.md (format=slug)
INFO [aif-plan] plan name prefix v3- applied per user request; git.create_branches=false so stem is description slug `v3-04-developmental-stages` (branch-derived naming disabled — does not replace `v3-` prefix)
INFO [aif-plan] RESEARCH.md absent; research_influenced_plan=false
INFO [aif-plan] plan_default_milestone=auto would surface M6 first; scope is explicitly v3-04 under M7 so linkage uses M7
INFO [aif-improve] applied refinement: lock denied_command_kinds→AgentCommand.kind map; extend population_lifecycle only on v26 (full v25 keyset incl. new_agent_initialization); synthesize developmental passthrough on v24/v25; dedicated lifespan_distribution StreamScope; assigned_lifespan on record/checkpoint only (not AgentInitializationRecorded); dual-key codec v6|v7 decode (no v11 default); ephemeral capacity + inventory policy; fatigue/learning composition vs skill helpers; matrix finalize→v26; AE/AF bit-identity synthesis proofs; Observer SEMANTIC count stays 40; drop Godot elder chrome

## Compatibility contract

This plan **deepens** owned `V3CapabilityFlags.generational_population` (v3-02/v3-03). It does **not** claim a new V3 flag. It must preserve V1/V2 and existing AE/AF behavior when developmental-effect / lifespan-distribution features are off or absent.

1. V1/V2 invariants intact. `WorldEngine` remains the only objective mutation authority. Agents never directly mutate objective reality. Agents receive immutable per-agent `Observation` / `Perspective` only. `WorldEvent` records remain immutable and append-only. Subjective state stays outside the objective fold. Godot remains read-only. Deterministic replay continues. No scripted civilization outcomes.
2. Flag ownership unchanged. Keep `generational_population` in `_V3_OWNED_CAPABILITY_FLAGS`. Do **not** own `kinship_inheritance`, `multi_polity_migration`, `institutional_economy`, `cultural_historical_memory`, or `multi_hop_testimony_tracking`.
3. Flags-off / effects-off = prior baseline. With all V3 flags off, trajectories and `exact_trajectory_hash` match the pre-plan baseline. With `generational_population` on but developmental effects / lifespan distribution absent or default-passthrough, AE (v24) and AF (v25) trajectories remain bit-identical to pre-v3-04 (modulo intentional non-behavioral metadata).
4. Schema bumps use accepted-set + exact key-set discipline. Never drop accepted V1/V2/V3 versions in the same change that adds a write version.
5. No biological sex, mating, pregnancy, parentage graphs, or human reproductive mechanics.
6. Death remains an objective `WorldEngine` `Died` event (`DeathCause.LIFESPAN` when natural EOL is enabled). Stages never invent a second death authority.
7. **Objective lifecycle ≠ subjective SelfModel.** Stage transitions, age, and capability effects must not auto-write age/maturity/elder-respect/leader beliefs into memory, semantic beliefs, identity aspects, or `SelfModel`. Respect for elders, if any, must emerge socially from agent interaction — never from stage id.
8. **ELDER ≠ leader.** Stage ids and effects must never grant social authority, command privileges over others, relationship dimension presets, or analysis labels like `leader`/`elder_authority`. Action availability gates are physical/capability legality only (self body), not hierarchy.
9. Preserve v3-03 locks: blank-slate deny-list; no `AgentCreated` field widen; closed `AgentInitializationRecorded.initial_conditions`; spawn-location precedence; bootstrap without Created/Entered/Initialized; `dependency_binding=from_lifecycle_stage`.
10. Optional tracing/analysis/observer presentation stay outside the objective fold / `EvidenceManifest`.
11. Alembic head stays `0017` unless a proven inspection need appears (default: no `0018`; developmental config lives in runner JSON + checkpoint/event/lifecycle-record payloads).

## Goal

Implement configurable aging and developmental stages on top of the v3-02/v3-03 lifecycle foundation:

- Configurable stage vocabulary (example ids: `dependent`, `learning`, `independent`, `elder` — **not** a hardcoded human lifecycle enum)
- Deterministic stage transitions from age/lifecycle policy
- Per-stage objective capability effects: physical capacity, dependency coupling, learning rate, fatigue accrual, action availability
- Gradual aging (tick-continuous age + optional intra-stage interpolation of continuous effects)
- Lifespan distributions with per-agent assigned lifespan drawn from seed-derived streams
- Natural end-of-life when enabled, using assigned lifespan
- Strict separation from agent subjective self-model
- Long-running aging + deterministic replay tests

## Design Decisions

### Invariant freeze (non-negotiable)

1. `WorldEngine` remains the only authority over objective physical reality and objective lifecycle mutations (create/enter/stage-change/death/effect application).
2. Agents receive immutable agent-specific `Observation` only.
3. `WorldEvent` records remain immutable; authoritative history stays append-only.
4. Subjective beliefs about age/maturity/social role may be wrong and never enter objective replay folding.
5. LLM output remains non-authoritative.
6. No scripted “elder became leader / respect-for-elders emerged / civilization matured” booleans.
7. Godot remains a read-only observer; **no** elder-authority presentation chrome in this plan.
8. Runs remain reproducible where claimed (explicit seeds, deterministic streams).

### Capability ownership (locked)

1. Remain on owned `generational_population`. Enabling developmental features requires the lifecycle channel on (`generational_population=True`).
2. Other V3 flags still fail closed.
3. When developmental effects are **absent / default passthrough**, physical/learning/fatigue/action behavior matches pre-v3-04 for the same roster and seeds.
4. When lifespan distribution is **fixed / absent**, EOL continues to use run-level `lifespan_ticks` exactly as v3-02 (`assigned_lifespan_ticks == lifespan_ticks`).

### Runner configuration versioning (locked)

Introduce `RUNNER_SCHEMA_VERSION_V26 = "runner-config-v26"`:

- Exact root key set = **full `runner-config-v25` keyset** (including required `new_agent_initialization`) ∪ extended exact children under **`population_lifecycle` only** (no new root sibling object).
- Default write remains `runner-config-v4` when all V3 flags are off and no existing mode requires a higher schema.
- When `generational_population` is true:
  - Without developmental extensions → still accept `v24` / `v25` as today.
  - When any v26-only lifecycle child is present / non-default → `schema_version` **must** be `runner-config-v26` (stable reject `developmental_stages_require_v26`).
- Explicit/non-default `new_agent_initialization` still requires at least `v25`; with developmental extensions require `v26`.
- Gate rewrite: `generational_population=True` requires `schema_version in {runner-config-v24, runner-config-v25, runner-config-v26}`.
- Decode of `v24`/`v25` synthesizes developmental passthrough defaults (exact objects below).
- Widen **every** mode allowlist currently capped at `v25` to also accept `v26`.
- `experiments/matrix_schema.py` finalize/allowlist accepts `v26`; finalize selects `v26` when non-default developmental children are present; AE stays v24 finalize; AF stays v25; default finalize stays `v4` when V3 flags off.

**Synthesized passthrough on v24/v25 decode (exact):**

| Key | Synthesized value |
| --- | --- |
| `gradual_aging` | `{ "intra_stage_interpolation": false }` |
| `lifespan_distribution` | `{ "distribution_id": "fixed", "params": {} }` |
| `stage_capability_effects` | absent/empty — resolvers treat missing effects as all continuous factors `1.0` and empty `denied_command_kinds` (do **not** require a cover-every-stage table when effects absent) |

### PopulationLifecycleSpec extensions (exact new child keys — locked)

Add exact optional children (present on v26; synthesized as above on v24/v25 decode):

| Key | Role |
| --- | --- |
| `stage_capability_effects` | When present: ordered exact list covering **every** configured stage exactly once; each entry has exact child keys (below). When absent/empty: passthrough factors |
| `gradual_aging` | Exact object: `intra_stage_interpolation` (bool) |
| `lifespan_distribution` | Exact object: `distribution_id` + `params` with per-id exact key set |

Keep existing keys unchanged: `lifespan_ticks`, `stage_thresholds`, `dependent_until_stage`, `demographic_policy_id`, `demographic_policy_params`, `max_population`, `natural_death_on_lifespan`.

**`stage_capability_effects` entry exact keys:**

| Key | Role |
| --- | --- |
| `stage_id` | Must match a configured threshold stage id |
| `physical_capacity_factor` | Positive float in closed range `(0, 2]` scaling **ephemeral** effective carry capacity at rule checks — never invents a second body store; never rewrites stored `CarryCapacity` for stage effects |
| `learning_rate_factor` | Positive float in `(0, 2]`; applied only when objective skill growth is active; multiplies growth deltas — does not invent skills or auto-enable learning mode |
| `fatigue_accrual_factor` | Positive float in `(0, 2]` scaling fatigue **gains** |
| `denied_command_kinds` | Frozen tuple of concrete `AgentCommand.kind` strings from the closed deny-allowlist (Task 2); empty = no extra denies. Self-legality only |

Forbidden on effect entries: `authority`, `leader`, `social_rank`, `respect`, `role`, kinship keys, relationship-dimension presets, invented class tokens (`heavy_labor`, `long_travel`, `teach`, `combat_initiate`).

**`lifespan_distribution` closed ids (initial):**

| `distribution_id` | Exact `params` keys | Behavior |
| --- | --- | --- |
| `fixed` | `{}` (empty exact set) | `assigned_lifespan_ticks = lifespan_ticks` for every agent (v3-02 behavior) |
| `uniform_int` | `min_ticks`, `max_ticks` | Inclusive ints; `1 ≤ min ≤ max`; per-agent draw at entry; reject if draws can violate stage coverage through `assigned - 1` |
| `discrete_table` | `weights` exact map age→nonneg weight | Seed-derived categorical draw; ages must be positive ints covered by stage thresholds through `age−1` |

Assigned lifespan is stored on `AgentLifecycleRecord.assigned_lifespan_ticks` so replay/refold never re-draws. Bootstrap agents assign once in `seed_bootstrap_lifecycle_records`; mid-run admits assign once before lifecycle-record commit. **Do not** put assigned lifespan in `AgentInitializationRecorded`, `creation_config_id` fingerprint, or Observation.

### Denied command kinds (locked)

There is **no** abstract “command class” layer in the codebase. Denies use concrete `command.kind` values from the closed `AgentCommand` set.

Ship a frozen allowlist of kinds that may appear in `denied_command_kinds` (exact membership table co-located with the config type). Initial allowlist (adjust only with tests):

- `attack`
- `harvest`
- `craft`
- `build`
- `repair`
- `flee`

Unknown kinds fail closed at decode/construction (`lifecycle_denied_command_kind_unknown`). Teaching remains a cognition mode — **not** a deny token. No social/authority kind families.

Admission: early reject in `prepare_action_batch` (or equivalent pre-`evaluate_operation` gate) with batch reason string `lifecycle_stage_action_denied` mapping to `ActionResolutionReason.STRUCTURAL_REJECTION` (do not invent a new `ActionResolutionReason` enum member unless required by existing maps).

### Stage naming policy (locked)

1. Stage ids remain opaque stable strings (`LifecycleStageId`) — **no** Python enum of DEPENDENT/LEARNING/INDEPENDENT/ELDER.
2. Reference/example config for Experiment AG uses lowercase ids: `dependent`, `learning`, `independent`, `elder` (docs may show UPPERCASE labels; wire values stay lowercase). AE fixtures may keep `infant`/`juvenile`/`adult` — both are opaque.
3. Experiments and docs must state that names are configurable and encode **no** human-specific or authority assumptions.
4. Keep binary `DependencyStatus` derivation from `dependent_until_stage` (v3-02). Do **not** expand `DependencyStatus` into LEARNING/ELDER.

### Gradual aging (locked)

1. Chronological age remains `current_tick − entry_tick` (pure function).
2. Every tick while the lifecycle channel is on: recompute age → stage → dependency; emit `LifecycleStageChanged` only when `previous_stage != new_stage` (event contract). Dependency is stage-derived; do not claim dependency-only events.
3. When `gradual_aging.intra_stage_interpolation` is false (default): apply the current stage’s continuous factors as constants for the whole stage band.
4. When true: for continuous factors only, linearly interpolate by age position within `[prev_max + 1, inclusive_max_age]` toward the **next** stage’s factors; final stage holds factors flat. `denied_command_kinds` stay discrete (current stage only).
5. Interpolation is objective and deterministic; log factor inputs at DEBUG without body payload dumps.

### Objective effect application seams (locked)

Apply effects **only** inside WorldEngine / private world rules — never in `SelfModel`, identity, relationship profiles, or analysis feedback:

| Effect | Seam |
| --- | --- |
| Physical capacity | Ephemeral effective capacity = round policy on `stored CarryCapacity × physical_capacity_factor` at `_evaluate_take` / `_evaluate_give` (and related load checks). Stored body capacity unchanged by stage. **Age-0 uses current stage factor immediately** (first-stage factor ≠ 1.0 is intentional). When effective capacity falls below current inventory load: deny new takes only — **no forced drops**. Recipient give checks use the recipient’s effective capacity |
| Fatigue | Multiply fatigue **gains**: compose as `lifecycle_fatigue_factor * adjusted_move_fatigue(...)` / `adjusted_flee_fatigue(...)` for move/flee; also scale `metabolism_fatigue` in autonomous physical step; optionally scale `help_fatigue` the same way (include help in the factor surface). Skill adjustment **divides** cost; lifecycle **multiplies** accrual — compose explicitly, do not “mirror” skill helper semantics |
| Learning rate | Extend `fold_skill_growth` with per-entity factor plumbing (e.g. `learning_rate_by_entity: Mapping[EntityId, float]`); multiply growth deltas when skill ledger active; skill-mode-off ⇒ no-op / no new events. Do not write stage into `CompetenceSelfModel` |
| Action availability | `denied_command_kinds` gate as locked above |
| Dependency | Observational + configured denies only — never auto-grant authority |

### Observation / events / write pairs (locked)

1. **Observation `lifecycle` object stays closed**: `{ chronological_age, stage, dependency_status }` only.
2. **`LifecycleStageChanged` field set unchanged** — no `assigned_lifespan_ticks` on the event.
3. **Default write pair unchanged**: provenance → `(EVENT_SCHEMA_REPLAY_V10, codec v7)`; else lifecycle → `(v9, v6)`; … No replay-v11 / codec v8 in this plan unless dual-key checkpoint decode proves insufficient (escape hatch only; prefer dual-key).
4. Checkpoint: extend `journal` lifecycle-record encode/decode with **dual key sets** on codec v6|v7 — optional `assigned_lifespan_ticks`; when absent on restore, synthesize `assigned_lifespan_ticks = run lifespan_ticks` (fixed equivalence). New writes always include the field.
5. Observer: **SEMANTIC_EVENT_TYPES count stays 40** — no new semantic type for AG. No elder-leader chrome.

### Lifespan RNG (locked)

- Dedicated stream: `create_named_stream(..., StreamScope(namespace="lifespan_distribution", names=(run_id, world_id_or_stable_run_token, agent_id, entry_tick, "assigned_lifespan")))`.
- **Do not** reuse `namespace="new_agent_init"` (avoids draw-order coupling with v3-03 innate/drive draws).
- Never wall clock / global `random`.

### SelfModel / cognition separation (locked)

1. No CognitiveLoop stage that auto-ingests chronological age into identity aspects or self-beliefs.
2. Lifecycle channel must not inject tokens like `elder`, `leader`, `dependent_person` into identity/self-model paths.
3. Architecture tests: forbid imports from `world.lifecycle` / lifecycle effect applicators into `agents.cognition.identity`, self-model projectors, and `CompetenceSelfModel` writers.
4. Blank-slate mid-run agents (v3-03) stay without copied maturity beliefs; developmental effects apply objectively from their stage only.

### Experiment AG (locked)

- Catalog arm `experiment-ag-developmental-stages` on **runner-config-v26**, off the V1 gate.
- Profile: `developmental_stages_profile` requiring `generational_population`, with example stages `dependent` / `learning` / `independent` / `elder`, non-trivial effect table (including at least one non-empty `denied_command_kinds` on `dependent`), `uniform_int` or `discrete_table` lifespan distribution, `natural_death_on_lifespan=true`.
- Arms: gradual aging on vs off; skill-learning mode **on** on at least one arm so learning-rate proofs are meaningful; skill-mode-off arm proves learning factor no-op.
- Prove: stage transitions; capacity/fatigue/learning/action denies; EOL uses assigned lifespan; no social-authority side effects; ELDER grants no extra commands vs `independent` with empty denies; flags-off / effects-off hashes stable.
- AE stays on v24; AF stays on v25; AG does not replace them. Observer count stays 40.

### Out of scope

- Kinship, inheritance, parentage, multi-polity migration, institutions, cultural-historical memory
- Social respect/authority systems, elder councils, leadership succession
- Auto-written subjective age/maturity beliefs
- New inspection HTTP for roster
- Alembic `0018`
- Claiming `multi_hop_testimony_tracking`
- Godot protocol rename or elder-authority presentation chrome
- Invented command-class vocabularies disconnected from `AgentCommand.kind`

## Commit Plan

- **Commit 1** (after tasks 1–4): `feat(v3): add developmental stage contracts, deny kinds, and runner-config-v26`
- **Commit 2** (after tasks 5–6): `feat(v3): assign lifespan distributions and dual-key lifecycle checkpoint fields`
- **Commit 3** (after tasks 7–9): `feat(v3): apply stage capability effects and assigned-lifespan EOL in WorldEngine`
- **Commit 4** (after tasks 10–12): `feat(v3): developmental replay parity, Experiment AG, and SelfModel separation gates`
- **Commit 5** (after tasks 13–15): `test(v3): long-run aging proofs, AE/AF bit-identity, and docs`

## Tasks

### Phase 1: Domain & config contracts

- [x] Task 1: Extend lifecycle domain types for assigned lifespan and stage capability effects
  - Add frozen `StageCapabilityEffect` with exact keys including `denied_command_kinds` (not classes) and `ContinuousLifecycleFactors` helper type.
  - Extend `AgentLifecycleRecord` with `assigned_lifespan_ticks: int` (positive); validate `>= 1` and stage coverage through `assigned_lifespan_ticks - 1`.
  - Add pure functions: `resolve_stage_effect`, `interpolate_continuous_factors(age, thresholds, effects, *, enabled)` with lerp domain `[prev_max + 1, inclusive_max_age]` and final-stage flat; denied kinds non-interpolated.
  - Keep stage ids opaque; fixtures may use `dependent`/`learning`/`independent`/`elder` without enums.
  - LOGGING: DEBUG on resolve/interpolate `{stage_id, age, factors}`; ERROR/WARN with stable `code=` on validation failures; no body/inventory payloads.
  - Files: `src/world/lifecycle.py` and/or `src/world/lifecycle_effects.py`, `src/world/__init__.py`, `tests/unit/test_lifecycle_stage_effects.py`

- [x] Task 2: Lock `denied_command_kinds` vocabulary to concrete `AgentCommand.kind` values
  - Ship frozen allowlist membership table co-located with config/domain types (initial set per Design Decisions).
  - Reject unknown kinds at construction/decode (`lifecycle_denied_command_kind_unknown`).
  - Unit-test allowlist membership and reject paths; document that teaching is not a command kind.
  - LOGGING: DEBUG on deny-kind validation counts; ERROR on unknown kind with code.
  - Files: `src/world/lifecycle_effects.py` (or sibling), `tests/unit/test_lifecycle_denied_command_kinds.py`
  - Depends on: Task 1

- [x] Task 3: Extend `PopulationLifecycleSpec` + runner serialization for v26
  - Add `stage_capability_effects`, `gradual_aging`, `lifespan_distribution` under `population_lifecycle` only; reject forbidden authority/biology keys.
  - Introduce `RUNNER_SCHEMA_VERSION_V26`; exact root = full v25 keyset including required `new_agent_initialization`; synthesize passthrough developmental defaults on v24/v25 decode; require v26 when non-default developmental children present; widen `generational_population` allowlist to `{v24,v25,v26}` and all mode allowlists capped at v25.
  - LOGGING: INFO on schema select `{schema_version, generational_population, developmental_extensions}`; DEBUG on decoded effect counts; fail closed with stable codes.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, related allowlist sites, `tests/unit/test_runner_config_v26_*.py`
  - Depends on: Task 1, Task 2

- [x] Task 4: Matrix finalize + `developmental_stages_profile` for v26
  - Extend `experiments/matrix_schema.py` finalize so non-default developmental children select `runner-config-v26`; keep AE finalize on v24 and AF on v25; allowlist accepts v26.
  - Add/extend `developmental_stages_profile` accepting v26 with `generational_population` rules.
  - LOGGING: DEBUG finalize choice `{schema_version, reason}`; metadata-only.
  - Files: `src/experiments/matrix_schema.py`, `src/experiments/catalog.py` (profile helpers), related unit tests
  - Depends on: Task 3

### Phase 2: Lifespan assignment & checkpoint encoding

- [x] Task 5: Seed-derived lifespan assignment API
  - Implement distribution draw helpers via dedicated `StreamScope(namespace="lifespan_distribution", …)` — never `new_agent_init`, wall clock, or global `random`.
  - Assign once in `seed_bootstrap_lifecycle_records` and mid-run admit paths before lifecycle-record commit; fixed distribution copies `lifespan_ticks`.
  - Persist on lifecycle record only — **not** in `AgentInitializationRecorded` / init fingerprint / Observation.
  - LOGGING: INFO on assign `{agent_id, distribution_id, assigned_lifespan_ticks}`; DEBUG on draw inputs; ERROR on invalid params.
  - Files: `src/simulation/lifespan_distribution.py` (and/or demographic helpers), `src/simulation/engine.py`, `src/simulation/runner_models.py` (bootstrap seed), unit tests
  - Depends on: Task 3

- [x] Task 6: Dual-key lifecycle checkpoint encode/decode for `assigned_lifespan_ticks`
  - Extend `journal._encode_lifecycle_record` / `_decode_lifecycle_record` with dual key sets on codec v6|v7: optional field on decode; when absent synthesize `assigned_lifespan_ticks = run lifespan_ticks`; new writes always include the field.
  - Default: **no** replay-v11 / codec v8.
  - Tests: old v6/v7 snaps without the field restore; new snaps round-trip assigned values; live continuation after restore does not redraw lifespan.
  - LOGGING: DEBUG on decode path `{has_assigned_lifespan, synthesized}`; ERROR on key-set violations.
  - Files: journal/serialization checkpoint modules under `src/simulation/` / persistence, `tests/unit/test_lifecycle_snapshot_assigned_lifespan.py`
  - Depends on: Task 5

### Phase 3: WorldEngine application

- [x] Task 7: Apply physical capacity + fatigue factors in objective resolution
  - Ephemeral effective capacity at take/give/load checks; stored `CarryCapacity` unchanged by stage; age-0 uses current stage factor; overload ⇒ deny new takes only (no forced drops).
  - Fatigue composition: `lifecycle_factor * adjusted_move_fatigue` / `adjusted_flee_fatigue`; also scale metabolism fatigue; include help fatigue in the same factor surface.
  - Effects-off / missing table ⇒ factor `1.0` bit-identical to pre-plan behavior.
  - LOGGING: DEBUG `{body_id, stage, factor, reason_code}`; never log full body state; skip spam when factor==1.0 if matching existing skill DEBUG noise policy.
  - Files: `src/simulation/engine.py`, `src/world/_physical.py`, `src/world/_rules.py` (capacity checks), `tests/unit/test_lifecycle_capacity_fatigue_effects.py`
  - Depends on: Task 1, Task 3

- [x] Task 8: Apply learning-rate factor via extended `fold_skill_growth`
  - Extend `fold_skill_growth` / `_fold_skill_ledger` with per-entity `learning_rate_by_entity` (or equivalent); multiply growth deltas when skill ledger active.
  - Skill-mode-off ⇒ no behavioral change and no new events; do not write stage into `CompetenceSelfModel`.
  - LOGGING: DEBUG `{entity_id, stage, learning_rate_factor, domain}` when factor applied; respect existing noise policy for factor==1.0.
  - Files: `src/world/_skills.py`, `src/simulation/engine.py`, `tests/unit/test_lifecycle_learning_rate_effects.py`
  - Depends on: Task 1, Task 7

- [x] Task 9: Action kind denies + assigned-lifespan EOL
  - Gate denied kinds in `prepare_action_batch` (or equivalent) with reason `lifecycle_stage_action_denied` → `STRUCTURAL_REJECTION`.
  - EOL: when `natural_death_on_lifespan` and `age >= record.assigned_lifespan_ticks`, emit `Died(death_cause=lifespan)`; clamp pre-death stage resolution with assigned lifespan (not only run-level `lifespan_ticks`).
  - Tests: ELDER with empty denies grants no extra commands vs `independent`; no relationship/SelfModel writes on stage change.
  - LOGGING: INFO on stage transition and lifespan death `{body_id, age, stage, assigned_lifespan_ticks}`; WARN on deny with reason code.
  - Files: `src/simulation/engine.py`, `src/world/_operations.py`, `tests/unit/test_lifecycle_action_denies_and_eol.py`
  - Depends on: Task 2, Task 5, Task 7

### Phase 4: Integration, experiment, separation gates

- [x] Task 10: Checkpoint / replay / observation parity for assigned lifespan + effects
  - Live vs restored engines at the same tick emit equal observations and continue identical trajectories under developmental configs.
  - Keep Observation and `LifecycleStageChanged` unchanged; rely on Task 6 dual-key decode (no v11).
  - LOGGING: DEBUG on restore lifecycle record counts; parity assertions in tests.
  - Files: serialization/checkpoint/replay under `src/simulation/`, `src/world/_replay.py`, `tests/unit/test_lifecycle_developmental_replay.py`, extend checkpoint restoration siblings
  - Depends on: Task 6, Task 9

- [x] Task 11: Experiment AG + catalog profile
  - Add `experiment-ag-developmental-stages` / wire `developmental_stages_profile` on v26 with locked example stages, effect table, lifespan distribution, gradual-aging on/off arms, skill-mode on/off arms; off V1 gate.
  - Ensure AE/AF unchanged; matrix allowlist includes AG without enabling on default batches; Observer SEMANTIC count stays 40.
  - LOGGING: experiment coordinator metadata-only (ids, arm names, tick counts).
  - Files: `src/experiments/catalog.py`, `tests/unit/test_developmental_stages_catalog_arm.py`
  - Depends on: Task 4, Task 10

- [x] Task 12: SelfModel / social-authority separation architecture gates
  - Architecture/unit tests: no auto identity/self-belief writes on `LifecycleStageChanged`; no elder→leader mapping; cognition identity / self-model / CompetenceSelfModel writers do not import lifecycle effect applicators; forbidden authority keys rejected on effect config.
  - One short invariant comment near effect application (not essays).
  - LOGGING: N/A for architecture tests; production paths must not log subjective belief content.
  - Files: `tests/architecture/test_v3_developmental_stage_invariants.py` (and/or extend scaffolding invariants)
  - Depends on: Task 9

### Phase 5: Long-run proofs and docs

- [x] Task 13: Long-running aging + deterministic twin-run replay tests
  - Run enough ticks to cross all example stage boundaries and hit assigned-lifespan EOL for ≥1 agent; assert ordered `LifecycleStageChanged` sequence and final `Died(LIFESPAN)`.
  - Twin-run same seed ⇒ identical projected world/lifecycle hashes; different seed ⇒ divergent assigned lifespans when distribution is non-fixed.
  - Gradual aging on/off: continuous factors differ where expected; stage-id event equality at thresholds preserved.
  - LOGGING: tests may enable DEBUG; assert operational logs remain metadata-safe.
  - Files: `tests/unit/test_lifecycle_long_run_aging.py`, `tests/unit/test_lifecycle_developmental_replay_determinism.py`
  - Depends on: Task 10, Task 11

- [x] Task 14: Flags-off / effects-off / AE/AF bit-identity regression
  - Prove V1 gate + `test_v2_scientific_invariants` under V3 flags off.
  - Explicit synthesis proofs: decode v24/v25 → passthrough developmental defaults; fixed/absent distribution ⇒ `assigned_lifespan_ticks == lifespan_ticks`; effects-off ⇒ factors `1.0` / empty denies; AE/AF `exact_trajectory_hash` unchanged without catalog schema bumps.
  - v26 all-off / passthrough round-trips.
  - LOGGING: follow existing regression helper patterns.
  - Files: extend `tests/unit/test_v3_*_flags_off_compat.py`, golden runner config tests, AE/AF determinism tests
  - Depends on: Task 11

- [x] Task 15: Documentation checkpoint (`/aif-docs`)
  - Update `docs/architecture.md` V3 seams: developmental stage effects, lifespan distributions, gradual aging, SelfModel separation, ELDER≠leader, Experiment AG, `runner-config-v26` exact keys; correct stale write-pair text to include v10/v7 provenance priority already shipped by v3-03.
  - Cross-link configuration / physical simulation docs as needed; keep README lean; note no Godot elder-authority chrome.
  - LOGGING: N/A (docs only).
  - Files: `docs/architecture.md`, relevant `docs/*.md`, optionally `.ai-factory/DESCRIPTION.md` V3 scaffolding blurb
  - Depends on: Tasks 1–14

## Implementation notes for `/aif-implement`

- Prefer extending owned `generational_population` over inventing a new flag.
- Prefer ephemeral effective factors over mutating stored body capacity every tick.
- Prefer no Observation / `LifecycleStageChanged` / write-pair v11 changes; dual-key checkpoint decode for assigned lifespan.
- Deny concrete `AgentCommand.kind` values only — never invented class tokens.
- Example stage names in AG tests/docs: `dependent`, `learning`, `independent`, `elder`.
- Commit after each Commit Plan checkpoint when the user asks to commit (do not auto-commit unless requested).
