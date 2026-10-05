# Implementation Plan: V3-02 Population and Lifecycle Domain Foundation

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-05
Improved: 2026-10-05 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M7 — V3 Generational Civilization"
Rationale: ROADMAP M7 next plans explicitly call for owning `generational_population` with population/lifetime mechanisms; this plan is that first owning plan.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M7 — V3 Generational Civilization
INFO [aif-plan] mode=ultra treated as full (richer plan); remaining args describe the feature
INFO [aif-plan] resolved plan file: .ai-factory/plans/v3-02-population-lifecycle.md (format=slug)
INFO [aif-plan] plan name prefix v3- applied per user request; git.create_branches=false so stem is description slug `v3-02-population-lifecycle` (branch-derived naming disabled — does not replace `v3-` prefix)
INFO [aif-plan] RESEARCH.md absent; research_influenced_plan=false
INFO [aif-plan] plan_default_milestone=auto would surface M6 first; scope matches M7 next-plan list so linkage uses M7
INFO [aif-improve] applied refinement: lock v9/v6 write-pair priority over artifacts/dynamics/production; SystemEffectFamily.LIFECYCLE; bootstrap lifecycle seeding without birth events; admit_population_entry + translator rebuild; demographic tick schedule + exact policy params; mid-run _AgentBundle construction; pinned Observation lifecycle object; causal debugger maps; observer tuple pins to 39; v24 allowlist + schema gate rewrite; projector/branch restore; dep fixes; out-of-scope inspection HTTP and subjective age beliefs

## Compatibility contract

This plan is the **first owning plan** for `V3CapabilityFlags.generational_population`. It must preserve completed V1/V2 executability when the flag is off, and introduce opt-in population/lifecycle mechanics only when the flag is on.

1. V1/V2 invariants intact. `WorldEngine` remains the only objective mutation authority. Agents never directly mutate objective reality. Agents receive immutable per-agent `Observation` / `Perspective` only. `WorldEvent` records remain immutable and append-only. Subjective state stays outside the objective fold. Godot remains read-only. Deterministic replay continues. No scripted civilization outcomes.
2. Flag ownership. Add `generational_population` to `_V3_OWNED_CAPABILITY_FLAGS`. Other V3 flags stay unowned and fail closed. Do **not** own `multi_hop_testimony_tracking` or any kinship/migration/institution/cultural-history flag.
3. Flags-off = V2-equivalent. With all V3 flags off, stage order, policies, objective trajectories, and `exact_trajectory_hash` for V1 gate / V2 scientific-invariant scenarios match the pre-ownership baseline (modulo intentional non-behavioral metadata).
4. Schema bumps use accepted-set + exact key-set discipline. Never drop accepted V1/V2/V3-scaffolding versions in the same change that adds a write version.
5. No biological sex, mating, pregnancy, parentage graphs, or human reproductive mechanics. New-agent creation uses configurable experimental **demographic policies** (seed-derived, deterministic).
6. Death remains an objective `WorldEngine` `Died` event. Lifecycle stages and chronological age never invent a second death authority.
7. Separate **objective chronological age** from **agent subjective beliefs** about age, maturity, or social role. This plan does not auto-write age/maturity beliefs into memory or semantic beliefs.
8. Optional tracing/analysis/observer presentation stay outside the objective fold / `EvidenceManifest`.
9. Alembic head stays `0017` unless a proven inspection need appears (default: no `0018` in this plan; lifecycle lives in runner JSON + checkpoint/event payloads).

## Goal

Own `generational_population` and introduce population + lifetime **domain foundation** for Palimpsest V3: birth/entry tick, chronological age, lifecycle stage, lifespan configuration, dependent/independent status, alive/dead state, generation/cohort metadata, and origin provenance — without reproduction-specific human biology.

Deliver:

- Domain types and deterministic stage progression suitable for replay
- WorldEngine-owned lifecycle events (`AgentCreated`, `AgentEnteredWorld`, `LifecycleStageChanged`) plus existing `Died`
- Configurable lifespan + demographic-policy seams for experimental new-agent creation
- Mid-run roster entry path when the flag is on (flag-off keeps fixed bootstrap roster)
- Persistence / snapshot / Observer Protocol extensions co-landed with event schema
- V2 compatibility tests proving old simulations without lifecycle features behave unchanged

## Design Decisions

### Invariant freeze (non-negotiable)

1. `WorldEngine` remains the only authority over objective physical reality and objective lifecycle mutations (create/enter/stage-change/death).
2. Agents receive immutable agent-specific `Observation` only — never `WorldState`, private `world._*`, another agent's observation, or an all-agent batch as cognition input.
3. `WorldEvent` records remain immutable; authoritative history stays append-only.
4. Subjective beliefs about age/maturity/social role may be wrong and never enter objective replay folding.
5. LLM output remains non-authoritative.
6. No scripted “population emerged / civilization emerged / kinship must form” booleans.
7. Godot remains a read-only observer; presentation coordinates remain non-semantic.
8. Runs remain reproducible where claimed (explicit seeds, deterministic streams).

### Capability ownership (locked)

1. Add `"generational_population"` to `_V3_OWNED_CAPABILITY_FLAGS` in `src/simulation/runner_models.py`.
2. Enabling `generational_population=True` no longer fails closed at `from_config` for that flag; other V3 flags still fail closed.
3. When the flag is **off**, lifecycle progression, mid-run roster mutation, lifecycle events, and lifecycle observation fields must not execute (passthrough / absent channel).
4. When the flag is **on**, `schema_version` must be `runner-config-v24` (see below). Construction still rejects other unimplemented V3 flags.

### Runner configuration versioning (locked)

Introduce `RUNNER_SCHEMA_VERSION_V24 = "runner-config-v24"`:

- Exact key set = **full `runner-config-v23` keyset** ∪ root object `population_lifecycle` with an exact child key set (see `PopulationLifecycleSpec`).
- Default write remains `runner-config-v4` when all V3 flags are off and no existing mode requires a higher schema.
- When `generational_population` is true, `schema_version` **must** be `runner-config-v24` (reject with stable reason e.g. `generational_population_requires_v24`). Replace/extend the existing `v3_capability_requires_v23` gate so: other-only V3 flags still require at least `v23`; `generational_population` requires `v24` (alone or with other flags that are still unimplemented and fail closed at `from_config`).
- Decode of `v1`…`v23` synthesizes absent/`None` population lifecycle (or default inactive). Decode of `v24` requires the exact `population_lifecycle` object. All-off `v24` round-trips are legal (mirror `v23` all-off policy).
- Widen **every** mode allowlist currently capped at `v23` to also accept `v24` (artifact/convention/naming/narrative/budget/territorial/group/norm/… schemas and budget equality set → `{v22,v23,v24}`).
- `experiments/matrix_schema.py` finalize/allowlist accepts `v24`; default finalize stays `v4` when V3 flags off.

### PopulationLifecycleSpec (exact child keys — locked shape)

Closed, frozen run-level spec under root key `population_lifecycle` on v24:

| Key | Role |
| --- | --- |
| `lifespan_ticks` | Positive int max chronological age in ticks (finite lifetime) |
| `stage_thresholds` | Ordered exact map/list of closed stage id → inclusive max chronological age for that stage (deterministic boundaries) |
| `dependent_until_stage` | Closed stage id; agents below this stage are `DEPENDENT`, at/above are `INDEPENDENT` |
| `demographic_policy_id` | Closed string id for experimental entry policy (no biology) |
| `demographic_policy_params` | Exact frozen param object for the selected policy; **each** `demographic_policy_id` has its own exact child key set enforced at decode (seed-derived draws only via WorldEngine/simulation RNG streams — never wall clock) |
| `max_population` | Positive int hard cap; entry attempts beyond cap fail closed with stable reason (no silent drop) |
| `natural_death_on_lifespan` | Bool; when true, chronological age ≥ lifespan emits objective `Died` with new `DeathCause.LIFESPAN` |

Forbidden on this object: sex, fertility, mating, pregnancy, gestation, parent/child ids, kinship edges (those belong to `kinship_inheritance`).

### Domain concepts (objective)

Introduce world/simulation-owned immutable types (prefer `world` for authority-visible facts; simulation for runner wiring). Suggested homes:

| Concept | Type (suggested) | Notes |
| --- | --- | --- |
| Birth/entry tick | `entry_tick: int` on lifecycle record | Tick when agent entered the world; bootstrap agents use `0` |
| Chronological age | derived `current_tick - entry_tick` | Objective; never stored as mutable wall-clock age; recomputed deterministically |
| Lifecycle stage | `LifecycleStageId` closed enum/str set from spec | Progressed only by WorldEngine using thresholds |
| Lifespan configuration | `PopulationLifecycleSpec.lifespan_ticks` | Run-level |
| Dependent/independent | `DependencyStatus` enum | Derived from stage vs `dependent_until_stage` |
| Alive/dead | existing `LifeStatus` | Death still via `Died` |
| Generation / cohort | `generation_index: int`, `cohort_id: str` (stable id) | Metadata on lifecycle record; researcher/experiment labels — not social roles |
| Origin provenance | `OriginProvenance` closed enum | `BOOTSTRAP`, `DEMOGRAPHIC_POLICY`, `EXTERNAL_ENTRY` — **not** biological birth |

`AgentLifecycleRecord` (name flexible) binds `body_id` / `agent_id` registration, entry tick, stage, dependency status, generation, cohort, provenance. Chronological age is a function, not a free field that can drift.

### Bootstrap vs mid-run lifecycle records (locked)

- When the lifecycle channel is on at construction, **seed** an `AgentLifecycleRecord` for every bootstrap registration: `entry_tick=0`, `OriginProvenance.BOOTSTRAP`, initial stage/dependency from age 0 thresholds, generation/cohort from experiment/bootstrap defaults (pinned in Task 5).
- Do **not** emit `AgentCreated` / `AgentEnteredWorld` for bootstrap agents. Those events are reserved for mid-run demographic (or external) entry.
- Mid-run successful entry: emit `AgentCreated` then `AgentEnteredWorld`, create lifecycle record with `entry_tick = commit tick`, provenance from policy.

### Deterministic lifecycle progression (locked)

1. Progression runs inside the authoritative tick path (alongside autonomous physical step), **only when** `generational_population` is on.
2. For each living registered body, compute chronological age from logical tick − entry tick.
3. Stage = first matching threshold from ordered `stage_thresholds` (exact algorithm pinned in code + tests).
4. On stage change, emit `LifecycleStageChanged` (and update dependency status if crossed) with `SystemCause` / `SystemEffectFamily.LIFECYCLE`.
5. If `natural_death_on_lifespan` and age ≥ lifespan, emit `Died` with `DeathCause.LIFESPAN` and `SystemEffectFamily.LIFECYCLE` (one-way; runtime `TERMINAL` as today).
6. Same seed + same spec + same admissions ⇒ identical stage timelines and event sequences (replay proofs).

### New-agent creation / demographic policies (locked)

1. **No** reproduction mechanics. Policies are experiment configuration that propose deterministic entry candidates (identity, body bootstrap fields, generation/cohort/provenance, spawn location, **and** an agent blueprint: cognition template / goals / drives / bounded name).
2. WorldEngine owns admission via a channel-gated public method **outside** the architecture deny-list names (`register_agent`, `unregister_agent`, `unbind_agent`, `spawn_agent`, `add_agent`, `remove_agent`, `bind_agent`). Locked public name: `admit_population_entry` (engine) with runner orchestration that rebuilds/replaces `RegistrationTranslator` for all live runtimes after append (translator is frozen-from-bootstrap today).
3. Successful entry co-lands: new body in world state, registration append, translator rebuild, `AgentCreated` + `AgentEnteredWorld` events, lifecycle record, and runner construction of a full `_AgentBundle` (memory/belief/relationship scopes + `AgentRuntime`) before subsequent cognition ticks.
4. Per-tick ordinal = **current registration order** including mid-run appends (bootstrap-only ordinal assumption lifted only when the flag is on).
5. `prepare_parallel` remains `False` in this plan.
6. Flag-off: reject any mid-run admit; roster frozen as today. Architecture tests: keep forbidding deny-list mutators; allow only `admit_population_entry` as the gated path when channel on.
7. Population cap and invalid policy params fail closed with stable reason codes; log counts/ids only.
8. **Policy schedule (locked):** once per tick when channel on, **after** autonomous physical step (including lifecycle progression/lifespan death for that tick), consult the demographic policy with a seed-derived RNG stream + current population snapshot; admit 0..N candidates under `max_population` using a deterministic candidate sort key; unknown `demographic_policy_id` fails closed at construction/decode.

### Event schema and write-pair priority (locked)

Introduce `EVENT_SCHEMA_REPLAY_V9` (9) for lifecycle occurrence kinds. Written **only** when the generational population channel is active for the run. Default writes stay at replay-v5 when the channel is off.

New detail types (domain names; Observer semantic mapping separate):

| Detail | Observer semantic type |
| --- | --- |
| `AgentCreated` | `AGENT_CREATED` |
| `AgentEnteredWorld` | `AGENT_ENTERED_WORLD` |
| `LifecycleStageChanged` | `LIFECYCLE_STAGE_CHANGED` |
| existing `Died` | `AGENT_DIED` (unchanged authority) |

**Write-pair priority** (extends `checkpoint_schema_for_production`):

1. Lifecycle channel on → `(EVENT_SCHEMA_REPLAY_V9, "v6")`
2. Else artifacts → `(v8, "v5")`
3. Else dynamics → `(v7, "v4")`
4. Else production → `(v6, "v3")`
5. Else → `(replay-v5, "v2")`

When lifecycle selects v9/v6, the v9 detail union **must accept** lower-channel detail kinds (production / dynamics / artifacts) so co-enabled channels remain foldable — same pattern as replay-v8 accepting production/dynamics payloads. Lifecycle detail kinds remain illegal on schemas &lt; 9.

Rules:

- Accepted event schemas become `{2…9}`; never drop legacy decode.
- Persistence codec `"v6"` pairs with event schema 9; accepted codecs keep `v1`…`v5` for restore. Flag-off default write stays non-lifecycle.
- Projector/replay must fold new lifecycle details; live/restored parity required.
- Extend `DeathCause` with `LIFESPAN` and `SystemEffectFamily` with `LIFECYCLE`.

### Observation / domain-contract evolution (locked)

- Channel-off: Observation JSON / dataclasses expose **no** new lifecycle keys (flags-off wire unchanged).
- Channel-on: additive optional closed `lifecycle` object on `ObservedSelf` / `VisibleBody` with exact fields: `chronological_age` (int), `stage` (closed stage id), `dependency_status` (`DEPENDENT` | `INDEPENDENT`). Do **not** put generation/cohort/provenance into perception in this plan.
- Live/restored observation parity is a hard gate.
- Subjective maturity/social-role beliefs remain **out of scope** for automatic formation (document seam only).

### Snapshots / persistence / runner restore

- Checkpoint / snapshot payloads must round-trip lifecycle records, registration order (including mid-run entries), translator order, and stage state when the channel is active.
- Flag-off restore of legacy V1/V2 snapshots remains bit-compatible for objective trajectory identity.
- Research-fork restore of a lifecycle-on checkpoint must preserve roster + lifecycle records (control-plane fork; no parent rewrite).
- Subjective tables remain outside authoritative replay.
- Prefer no Alembic `0018`; lifecycle authority stays in event/snapshot/runner JSON.

### Observer Protocol

- Keep `observer-protocol-v1`.
- Append semantic types `AGENT_CREATED`, `AGENT_ENTERED_WORLD`, `LIFECYCLE_STAGE_CHANGED` to `SEMANTIC_EVENT_TYPES` / `SEMANTIC_TYPE_BY_KIND` and Godot `models.gd` mirror (exact parity test).
- Update all hard pins that currently assert `len(SEMANTIC_EVENT_TYPES) == 36` (and suffix/prefix slices) to **39** with the three new types appended.
- Wire Godot timeline `birth` category to created/entered types (no inventing births from roster alone).
- Map new detail kinds in `simulation.causal_debugger._DETAIL_KIND_TO_SEMANTIC_TYPE`; lifespan death remains `AGENT_DIED` with `DeathCause.LIFESPAN`.
- Presentation-only; no simulation authority in Godot.

### Analysis / experiments

- Catalog experiments using lifecycle stay **off** the V1 regression gate.
- Add a small off-gate experiment arm or reference helper proving stage progression + demographic entry under the flag.
- Analysis may later consume cohort/generation metadata; do not inject analysis into cognition.
- Existing `survival_cohort_contrast` remains researcher-label-only and is not rewritten into objective roles.

### Non-Goals

- Biological sex, mating, pregnancy, gestation, parentage, kinship graphs (`kinship_inheritance`).
- Migration / multi-polity / institutions / cultural-historical memory flags.
- Owning `multi_hop_testimony_tracking`.
- Auto-forming subjective age/maturity/social-role beliefs (seam docs only).
- New inspection HTTP fields for dynamic roster (existing inspection follows engine registration unless parity proves otherwise — defer).
- Scripted civilization or “population must grow” mandates.
- `prepare_parallel=True`.
- Alembic `0018` by default; `/v2` HTTP; renaming `observer-protocol-v1`.
- LLM → world shortcuts for spawning agents.
- Dropping legacy replay/runner/codec decode sets.

## Commit Plan
- **Commit 1** (after tasks 1–3): `feat(world): add population lifecycle domain types and lifespan death cause`
- **Commit 2** (after tasks 4–6): `feat(simulation): own generational_population with runner-config-v24`
- **Commit 3** (after tasks 7–10b): `feat(world): emit lifecycle events, mid-run entry, and deterministic stage progression`
- **Commit 4** (after tasks 11–13b): `feat(persistence,observer): lifecycle codec v6, snapshots, and protocol types`
- **Commit 5** (after tasks 14–16): `test(v3): V2 compatibility and lifecycle replay proofs`
- **Commit 6** (after task 17): `docs(v3): document population lifecycle seams and contracts`

## Tasks

### Phase 1: Domain foundation

- [x] Task 1: Define closed population/lifecycle domain types (no biology).
  - Deliverable: Add frozen types for `LifecycleStageId` (or closed stage strings validated by spec), `DependencyStatus` (`DEPENDENT` / `INDEPENDENT`), `OriginProvenance` (`BOOTSTRAP`, `DEMOGRAPHIC_POLICY`, `EXTERNAL_ENTRY`), and `AgentLifecycleRecord` (body/agent binding, `entry_tick`, current stage, dependency status, `generation_index`, `cohort_id`, provenance). Chronological age is a pure function of `(entry_tick, current_tick)` — do not store a mutable age field that can desync. Forbid sex/fertility/parent fields. Unit-test construction validation and age derivation edge cases (entry at 0; age at entry tick = 0).
  - Files: `src/world/` (new module e.g. `lifecycle.py` or extend `models.py` if small), `src/world/__init__.py`, `tests/unit/test_population_lifecycle_domain.py`.
  - Logging: Module may be log-free. Tests log DEBUG case ids only; never payloads.
  - Dependencies: None.

- [x] Task 2: Extend `DeathCause` with `LIFESPAN`, `SystemEffectFamily` with `LIFECYCLE`, and pin validation.
  - Deliverable: Add `DeathCause.LIFESPAN` and `SystemEffectFamily.LIFECYCLE`. Ensure `Died` and `SystemCause` validation accept them. Update any exhaustive match/tests that enumerate death causes or effect families. Do not change attack/needs/exposure behavior. Lifespan deaths and stage-change system causes must use `LIFECYCLE` family.
  - Files: `src/world/effects.py`, `src/world/events.py` (if needed), `src/world/_physical.py` (cause derivation helpers if touched), `tests/unit/` covering death-cause / effect-family accept/reject.
  - Logging: DEBUG on unexpected death-cause / effect-family reject reason codes only.
  - Dependencies: None.

- [x] Task 3: Define deterministic stage-resolution pure function.
  - Deliverable: Implement `resolve_lifecycle_stage(age, stage_thresholds) -> stage` and `resolve_dependency_status(stage, dependent_until_stage) -> DependencyStatus` as pure, framework-free functions with locked ordering semantics and exhaustive unit tests (boundaries inclusive as documented). No I/O, no RNG.
  - Files: same lifecycle module as Task 1, `tests/unit/test_lifecycle_stage_resolution.py`.
  - Logging: log-free pure functions.
  - Dependencies: Task 1.

### Phase 2: Own the flag and runner wiring

- [x] Task 4: Own `generational_population` and introduce `PopulationLifecycleSpec` + `runner-config-v24`.
  - Deliverable: Add `"generational_population"` to `_V3_OWNED_CAPABILITY_FLAGS`. Introduce frozen `PopulationLifecycleSpec` with the exact child keys locked above (including per-`demographic_policy_id` exact param key sets). Add `RUNNER_SCHEMA_VERSION_V24`, exact `_require_keys` set = v23 ∪ `population_lifecycle`, encode/decode, fingerprint inclusion when present. Rewrite schema gates: `generational_population=True` requires `v24`; other-only V3 flags still require ≥ `v23`; reject `v24` without exact `population_lifecycle`; allow all-off `v24` round-trips. Widen **every** mode allowlist / budget set currently capped at `v23` to include `v24`. Default write stays v4 when flags off. Update `simulation.compatibility` matrix row for v24 + owned flag policy. Update matrix schema allowlist. Scaffolding gate: owned flag may enable; other V3 flags still fail closed.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `src/simulation/__init__.py`, `src/experiments/matrix_schema.py`, `tests/unit/test_runner_config_v24_population_lifecycle.py`, `tests/unit/test_compatibility_matrix.py`, `tests/unit/test_v3_flag_defaults.py`, `tests/unit/test_v3_scaffolding_gate.py`.
  - Logging: DEBUG encode/decode schema_version + flag names + key counts; ERROR on `generational_population_requires_v24` / key-set violations; never log policy param payloads.
  - Dependencies: Task 1.

- [x] Task 5: Wire `SimulationRunner.from_config` for owned flag, lifecycle channel, and bootstrap lifecycle seeding.
  - Deliverable: When `generational_population` enabled and owned, construct runner with lifecycle channel active (pass `PopulationLifecycleSpec` into engine/bootstrap context). Seed bootstrap `AgentLifecycleRecord`s (`entry_tick=0`, `OriginProvenance.BOOTSTRAP`, stage/dependency from age-0 resolution, default generation/cohort). Do not emit created/entered events for bootstrap. Keep fail-closed for other V3 unimplemented flags. Flag-off path must not allocate lifecycle progression hooks or lifecycle records. Log construction with flag ownership counts as today.
  - Files: `src/simulation/runner.py`, `src/simulation/runner_models.py` (helpers if needed), `src/simulation/engine.py` / bootstrap wiring as needed, `tests/unit/test_simulation_runner_construction.py` (or sibling).
  - Logging: Keep existing `runner_construction_*` DEBUG/ERROR patterns; add `lifecycle_channel=on|off` and `bootstrap_lifecycle_record_count=` fields only.
  - Dependencies: Tasks 3, 4.

- [x] Task 6: Demographic policy port (experiment-compatible, non-biological).
  - Deliverable: Define a closed policy protocol/registry keyed by `demographic_policy_id` that, given seed-derived RNG stream + exact params + current population snapshot, returns deterministic entry candidates (body blueprint + generation/cohort/provenance + **agent blueprint**: cognition template, goals/drives, bounded name, spawn location). Ship at least one deterministic policy suitable for tests (e.g. `fixed_interval_entry` or `seeded_quota_entry`) and a `disabled`/no-op path. Each policy_id has an exact `demographic_policy_params` key set. Policies must not encode sex/reproduction. Fail closed on unknown policy ids. Document schedule: consulted once per tick after autonomous physical/lifecycle progression when channel on; admit 0..N under `max_population` with deterministic sort.
  - Files: `src/simulation/` (e.g. `demographic_policy.py`), `src/experiments/` helper if catalog needs it, `tests/unit/test_demographic_policy.py`.
  - Logging: DEBUG policy_id + candidate_count + reject reason codes; never names/backstories as free text dumps beyond existing bounded name rules.
  - Dependencies: Task 4.

### Phase 3: WorldEngine events and progression

- [x] Task 7: Add lifecycle WorldEvent detail types, schema v9, and write-pair priority.
  - Deliverable: Add `AgentCreated`, `AgentEnteredWorld`, `LifecycleStageChanged` to the closed event detail union. Introduce `EVENT_SCHEMA_REPLAY_V9`. Update `checkpoint_schema_for_production` (or successor) with locked priority: lifecycle → `(9, "v6")` else artifacts → `(8, "v5")` else dynamics → `(7, "v4")` else production → `(6, "v3")` else default. v9 detail union accepts lower-channel kinds when those channels are also active; lifecycle kinds illegal on schemas &lt; 9. Update `SUPPORTED_EVENT_SCHEMA_VERSIONS`, compatibility matrix, normalize/validate paths, and unit encode/decode fixtures.
  - Files: `src/world/events.py`, `src/simulation/persistence.py`, `src/simulation/compatibility.py`, `tests/unit/test_lifecycle_events_schema_v9.py`.
  - Logging: ERROR on schema/channel mismatch reason codes; DEBUG event_type + schema version + channel flags only.
  - Dependencies: Tasks 1, 2.

- [x] Task 8: Implement mid-run `admit_population_entry` under WorldEngine authority.
  - Deliverable: When lifecycle channel is on, implement engine-owned `admit_population_entry` that appends body + registration, rebuilds `RegistrationTranslator`, emits `AgentCreated` then `AgentEnteredWorld`, creates lifecycle record (`entry_tick`, provenance, generation/cohort), and returns public facts for runner bind. Flag-off must reject entry attempts. Enforce `max_population`. Preserve append-only event immutability. Do not use deny-listed public method names. Rewrite `tests/architecture/test_v3_scaffolding_invariants.py` so deny-list mutators remain forbidden and only the gated admit path is allowed when channel on. Update `tests/unit/test_domain_contract_evolution_policy.py` scaffolding “no birth fields” assertions to versioned-seam expectations.
  - Files: `src/simulation/engine.py`, `src/simulation/bootstrap.py`, private world ops as needed (`src/world/_state.py` / `_operations.py` / `_rules.py`), `tests/unit/test_mid_run_agent_entry.py`, `tests/architecture/test_v3_scaffolding_invariants.py`, `tests/unit/test_domain_contract_evolution_policy.py`.
  - Logging: INFO/DEBUG entry accepted with agent_id/body_id/tick/population_count; ERROR reject reason codes (`population_cap`, `lifecycle_channel_off`, …).
  - Dependencies: Tasks 5, 6, 7.

- [x] Task 9: Implement deterministic lifecycle progression + lifespan death in the tick path.
  - Deliverable: On each tick when channel is on, after logical tick advances and for living agents: recompute age/stage/dependency; emit `LifecycleStageChanged` on change with `SystemEffectFamily.LIFECYCLE`; if `natural_death_on_lifespan` and age ≥ lifespan, emit `Died(death_cause=LIFESPAN)` via the same death authority path (runtime becomes `TERMINAL`). Then run demographic policy consult/admit per Task 6 schedule. Progression must be replay-stable. Flag-off: zero new events/types from this hook.
  - Files: `src/world/_physical.py` and/or `src/simulation/engine.py` (prefer private world autonomous step consistency), `tests/unit/test_lifecycle_progression_determinism.py`.
  - Logging: DEBUG stage_changed count + lifespan_death count + demographic_admit_count per tick; never observation payloads.
  - Dependencies: Tasks 2, 3, 7, 8.

- [x] Task 10: Mid-run `_AgentBundle` construction (memory/cognition parity with bootstrap).
  - Deliverable: When entry commits, construct a full `_AgentBundle` for the new agent using the same dependency path as `from_config` agent construction: `MemoryScope`, memory/belief/relationship services, subjective commit service, cognitive loop from the demographic agent blueprint’s cognition template, `Agent` + `AgentRuntime` with the **rebuilt** translator. Do not leave a runtime shell without subjective services. Unit-test that mid-run agents can observe/act on the next eligible tick.
  - Files: `src/simulation/runner.py`, helpers extracted if needed for shared construct path, `tests/unit/test_mid_run_agent_bundle.py`.
  - Logging: DEBUG bundle_constructed agent_id + ordinal + memory_mode; never payloads.
  - Dependencies: Task 8.

- [x] Task 10b: Runner ordinal semantics and stop reasons for dynamic roster.
  - Deliverable: After Task 10 bind, document and test per-tick ordinal = registration order including mid-run appends. Propagate rebuilt translator to all existing runtimes. Dead/terminal agents remain non-acting as today. No `prepare_parallel=True`. Ensure stop reasons (`ALL_AGENTS_TERMINAL`, etc.) still make sense with dynamic population.
  - Files: `src/simulation/runner.py`, `src/simulation/agent_runtime.py` (if needed), `tests/unit/test_runner_dynamic_roster_ordinal.py`.
  - Logging: DEBUG runtime_bind agent_id + ordinal + population_count.
  - Dependencies: Task 10.

### Phase 4: Observation, persistence, observer

- [x] Task 11: Observation lifecycle-visible facts + live/restored parity (flag-on only).
  - Deliverable: Channel-off Observation wire unchanged (no new keys). Channel-on: additive closed `lifecycle` object on `ObservedSelf` / `VisibleBody` with exact fields `chronological_age`, `stage`, `dependency_status` only. Add live/restored observation parity tests for lifecycle-on runs. Do not auto-create subjective age beliefs. Update domain-contract evolution tests accordingly.
  - Files: `src/world/observations.py`, `src/world/_perception.py`, `src/simulation/serialization.py` (encode/decode), `tests/unit/test_lifecycle_observation_parity.py`, `tests/unit/test_domain_contract_evolution_policy.py` as needed.
  - Logging: DEBUG perception lifecycle_field_count only; never dump ages beyond ints/enums.
  - Dependencies: Tasks 8, 9.

- [x] Task 12: Persistence codec `v6` + snapshot/projector/branch restore for lifecycle state.
  - Deliverable: Pair persistence codec `"v6"` with event schema 9 when lifecycle channel active (priority from Task 7). Snapshots restore lifecycle records, registration order, translator order, and stage state. Update replay projector to fold v9 lifecycle details. Prove research-fork restore of a lifecycle-on checkpoint preserves roster + lifecycle records. Legacy codecs v1–v5 remain accepted for restore. Flag-off default write stays current non-lifecycle codec.
  - Files: `src/simulation/persistence.py`, projector/replay modules, `src/simulation/branch_service.py` / branching tests as needed, `tests/unit/test_lifecycle_snapshot_codec_v6.py`.
  - Logging: ERROR on codec/schema mismatch reason codes; DEBUG codec version + lifecycle_record_count.
  - Dependencies: Tasks 7, 8, 9.

- [x] Task 13: Observer Protocol + Godot birth category wiring.
  - Deliverable: Append `AGENT_CREATED`, `AGENT_ENTERED_WORLD`, `LIFECYCLE_STAGE_CHANGED` to Python `SEMANTIC_EVENT_TYPES` / maps and Godot `models.gd` mirrors. Update all `len(SEMANTIC_EVENT_TYPES) == 36` (and suffix/prefix) pins to **39**. Map domain kinds → semantic types in adapt/router. Fill Godot timeline `birth` category with created/entered types (still must not invent births from roster alone). Keep `observer-protocol-v1`. Extend protocol mirror tests.
  - Files: `src/observer/version.py`, `src/observer/adapt.py`, `src/observer/contracts.py` (if touched), `clients/godot-observer/scripts/protocol/models.gd`, `clients/godot-observer/scripts/ui/timeline.gd`, `clients/godot-observer/scripts/protocol/event_router.gd` (as needed), `tests/unit/test_godot_protocol_mirror.py`, `tests/unit/test_observer_contracts.py`, `tests/unit/test_artifact_observer.py`, `tests/unit/test_environmental_dynamics_observer.py`, Godot tests if present.
  - Logging: DEBUG semantic map misses as `unknown_event_kind`; never simulation mutation from observer.
  - Dependencies: Task 7.

- [x] Task 13b: Causal debugger maps for lifecycle semantics.
  - Deliverable: Add detail-kind → semantic mappings for `agent_created`, `agent_entered_world`, and `lifecycle_stage_changed` in `simulation.causal_debugger._DETAIL_KIND_TO_SEMANTIC_TYPE` (and any inverse/router tables that must stay in sync). Lifespan death remains `AGENT_DIED` / `died` with `DeathCause.LIFESPAN` (no new death semantic). Unit-test resolve paths for the new types.
  - Files: `src/simulation/causal_debugger.py`, `tests/unit/test_causal_debugger_command_map.py` / resolve tests as appropriate.
  - Logging: DEBUG unmapped_kind reason codes only.
  - Dependencies: Tasks 7, 13.

### Phase 5: Compatibility proofs, experiment seam, docs

- [x] Task 14: V2 compatibility / flags-off unchanged behavior tests.
  - Deliverable: Add focused tests proving simulations **without** lifecycle features (V3 flags off) keep identical `exact_trajectory_hash` / objective commit chains versus baseline (extend `tests/unit/test_v2_golden_runner_configs.py` pattern and/or new `tests/unit/test_v3_population_flags_off_compat.py`). Assert no lifecycle progression/admit hooks run when channel off. Keep `test_v1_regression_gate.py` and `test_v2_scientific_invariants.py` green under flags-off. Lifecycle-on tests stay off the V1 gate.
  - Files: `tests/unit/test_v3_population_flags_off_compat.py`, updates to golden/scaffolding gates as needed.
  - Logging: Test INFO start/end with experiment_id + hash prefixes only.
  - Dependencies: Tasks 5, 12.

- [x] Task 15: Lifecycle-on determinism + replay proofs.
  - Deliverable: Multi-seed and same-seed twin runs with `generational_population` on prove identical lifecycle event sequences, stage timelines, and restored observation parity. Include lifespan death path and demographic entry path. Replay from snapshot mid-run matches live continuation.
  - Files: `tests/unit/test_lifecycle_replay_determinism.py`.
  - Logging: DEBUG tick + event_type counts; never full event payloads.
  - Dependencies: Tasks 9, 10b, 11, 12.

- [x] Task 16: Off-gate experiment/catalog seam for demographic lifecycle.
  - Deliverable: Add a small trusted catalog arm or reference helper that enables `generational_population` + v24 spec with deterministic policy (off V1 gate). Prove it constructs and runs N ticks emitting expected lifecycle event kinds. Do not claim scientific “emergence.” Keep `v3_scaffolding_profile` requiring all V3 flags off; add `generational_population_profile` (or similar) for owned-flag experiments.
  - Files: `src/experiments/catalog.py` (or sibling), `tests/unit/test_generational_population_catalog_arm.py`.
  - Logging: INFO experiment_id + flag + tick_count; DEBUG lifecycle event counts.
  - Dependencies: Tasks 6, 10b, 14.

- [ ] Task 17: Mandatory docs checkpoint (`/aif-docs` scope).
  - Deliverable: Update `docs/architecture.md` V3 extension seams row for dynamic roster/lifetimes to “owned by v3-02”; document Downstream V3 checklist compliance for this flag; note objective age vs subjective belief separation (seam only — no auto beliefs); document v24 / event v9 / codec v6 write-pair priority; document `admit_population_entry` + translator rebuild; update `docs/persistence.md`, `docs/observer.md` / `docs/godot-observer.md` for new semantic types and birth markers; update `docs/cognition-runtime.md` ordinal/roster pin; update `.ai-factory/DESCRIPTION.md` and `.ai-factory/ARCHITECTURE.md` briefly for owned `generational_population`. Explicit non-goals: sex/reproduction/kinship; no new inspection HTTP in this plan. Do not edit ROADMAP as owned artifact (coordinate via `/aif-roadmap` if milestone text should change).
  - Files: `docs/architecture.md`, `docs/persistence.md`, `docs/observer.md`, `docs/godot-observer.md`, `docs/cognition-runtime.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`.
  - Logging: n/a (docs).
  - Dependencies: Tasks 14–16.

## Implementation notes for `/aif-implement`

- Prefer extending existing bounded packages (`world`, `simulation`, `observer`, `experiments`) over new top-level packages.
- Keep import-linter contracts; private `world._*` remain engine-only.
- Every new public type stays Pydantic-free in domain packages.
- Verbose logging: IDs, counts, reason codes, schema versions — never observation/communication/memory/belief payloads.
- When touching Godot, keep presentation-only and update Python↔GDScript protocol mirror tests in the same change.
- Extract shared agent-construction helpers from `SimulationRunner.from_config` if needed so Task 10 does not fork a divergent mid-run path.
