# Implementation Plan: V3-03 New Agent Creation and Generational Bootstrap

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-05
Improved: 2026-10-05 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M7 — V3 Generational Civilization"
Rationale: M7 owns generational population mechanics; this plan is the next owning layer after v3-02 — explicit blank-slate NewAgentInitialization for mid-run agents without claiming kinship/culture flags.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M7 — V3 Generational Civilization
INFO [aif-plan] mode=ultra treated as full (richer plan); remaining args describe the feature
INFO [aif-plan] resolved plan file: .ai-factory/plans/v3-03-new-agent-bootstrap.md (format=slug)
INFO [aif-plan] plan name prefix v3- applied per user request; git.create_branches=false so stem is description slug `v3-03-new-agent-bootstrap` (branch-derived naming disabled — does not replace `v3-` prefix)
INFO [aif-plan] RESEARCH.md absent; research_influenced_plan=false
INFO [aif-plan] plan_default_milestone=auto would surface M6 first; scope matches M7 next-plan list so linkage uses M7
INFO [aif-improve] applied refinement: lock AgentInitializationRecorded + AGENT_INITIALIZED (semantic count 40); species_defaults_id registry; v24|v25 gate rewrite; spawn-location precedence; exact objective_inheritance/parameter_distributions key sets; expanded blank-slate deny-list (relationships/naming/norm/convention/skill); StreamScope pin on SimulationRunConfig; Task 6/7 ownership split; tick-path + admit_population_entry shared body builder; checkpoint_schema new_agent_provenance_active; candidate fields before pipeline; AF depends on v25 gate; out-of-scope subjective birth beliefs

## Compatibility contract

This plan **extends** the already-owned `V3CapabilityFlags.generational_population` channel (v3-02). It does **not** claim a new V3 flag and must not own `kinship_inheritance`, `multi_polity_migration`, `institutional_economy`, `cultural_historical_memory`, or `multi_hop_testimony_tracking`.

1. V1/V2 invariants intact. `WorldEngine` remains the only objective mutation authority. Agents never directly mutate objective reality. Agents receive immutable per-agent `Observation` / `Perspective` only. `WorldEvent` records remain immutable and append-only. Subjective state stays outside the objective fold. Godot remains read-only. Deterministic replay continues. No scripted civilization outcomes.
2. Flag ownership unchanged: `generational_population` stays in `_V3_OWNED_CAPABILITY_FLAGS`. Other V3 flags stay unowned and fail closed.
3. Flags-off = V2-equivalent. With all V3 flags off, stage order, policies, objective trajectories, and `exact_trajectory_hash` for V1 gate / V2 scientific-invariant scenarios match the pre-v3-03 baseline (modulo intentional non-behavioral metadata).
4. Schema bumps use accepted-set + exact key-set discipline. Never drop accepted V1/V2/V3 versions in the same change that adds a write version. Keep `runner-config-v24` decodable; synthesize default init when the new object is absent.
5. **No silent cross-agent subjective copy.** A new agent must never receive another agent's episodic memory, beliefs, self-model, Theory of Mind, goals, cultural narratives, or cognitive trace — including via the current mid-run `agents[0]` cognition-template shortcut when an explicit init blueprint is required.
6. Cultural information (map completeness, language/labels, social norms, history/narratives) is learned later through perception, communication, teaching, and artifacts — never injected at creation.
7. Parent/origin references on provenance are **experimental origin labels**, not kinship graphs, parentage edges, or inheritance of subjective state (`kinship_inheritance` remains unowned).
8. Optional tracing/analysis/observer presentation stay outside the objective fold / `EvidenceManifest`.
9. Alembic head stays `0017` unless a proven inspection need appears (default: no `0018`; init config lives in runner JSON + event/snapshot payloads).

## Goal

Implement configurable creation of new agents during a running simulation via an explicit **NewAgentInitialization** pipeline that blank-slates all subjective stores, samples only allowed objective/innate inputs from seeded distributions, records creation provenance, and reproduces exactly under replay and forked replay.

Deliver:

- Closed `NewAgentInitializationSpec` + pipeline that constructs mid-run agents without copying forbidden subjective stores
- Closed `species_defaults_id` registry (at least `species_default_v1`) producing fresh cognition/drive baselines for the new owner
- Initialization sources: species/system defaults, experimental parameter distributions, limited innate drives, physical conditions, location, dependency relationships, and explicitly configured objective-attribute inheritance only
- Deterministic seed-derived draws (named RNG stream scopes on `SimulationRunConfig`)
- Provenance via sibling `AgentInitializationRecorded` (why, origin refs, initial conditions, creation config)
- Event schema v10 / codec v7 / Observer `AGENT_INITIALIZED` (semantic count 40) co-landed
- Replay + forked-replay proofs that agent creation is bit-identical
- Architecture/unit tests enforcing the subjective-copy deny-list (including empty cultural/skill/relationship ledgers)
- Off-gate Experiment AF on `runner-config-v25` proving blank-slate bootstrap

## Design Decisions

### Invariant freeze (non-negotiable)

1. `WorldEngine` remains the only authority over objective physical reality and objective lifecycle mutations (create/enter/stage-change/death).
2. Agents receive immutable agent-specific `Observation` only — never `WorldState`, private `world._*`, another agent's observation, or an all-agent batch as cognition input.
3. `WorldEvent` records remain immutable; authoritative history stays append-only.
4. Subjective beliefs, memories, ToM, narratives, goals, and cognition traces are owner-scoped and never copied across agents at creation.
5. LLM output remains non-authoritative.
6. No scripted “culture transferred / language known / map known / kinship formed” booleans.
7. Godot remains a read-only observer; presentation coordinates remain non-semantic.
8. Runs remain reproducible where claimed (explicit seeds, deterministic streams).

### Capability ownership (locked)

1. Do **not** add a new V3 flag. Work rides the owned `generational_population` channel.
2. When the flag is **off**, NewAgentInitialization must not execute (no mid-run admits; no new provenance event kinds from this plan).
3. When the flag is **on**, mid-run `_AgentBundle` construction **must** go through `NewAgentInitialization` (replace the `self._config.agents[0]` template clone in `SimulationRunner._sync_mid_run_population_entries`).
4. Other V3 flags still fail closed at `from_config`.

### Runner configuration versioning (locked)

Introduce `RUNNER_SCHEMA_VERSION_V25 = "runner-config-v25"`:

- Exact key set = **full `runner-config-v24` keyset** ∪ root object `new_agent_initialization` with an exact child key set (see `NewAgentInitializationSpec`).
- Default write remains `runner-config-v4` when all V3 flags are off and no existing mode requires a higher schema.
- Decode of `v1`…`v24`: synthesize a closed **default** `NewAgentInitializationSpec` (species_defaults_id=`species_default_v1`, empty distributions, no objective inheritance, empty origin-ref policy) when lifecycle channel would need it — so v24 lifecycle-on runs remain restorable.
- Decode of `v25` requires the exact `new_agent_initialization` object. All-off `v25` round-trips are legal (mirror v23/v24 all-off policy).
- **Gate rewrite:** `generational_population=True` requires `schema_version in {runner-config-v24, runner-config-v25}` (replace exact-equality `generational_population_requires_v24`). When the wire includes an explicit `new_agent_initialization` object (or non-default init is requested), schema **must** be `v25` (`new_agent_initialization_requires_v25`). v24 lifecycle-on continues via synthesized defaults (AE stays green).
- Widen **every** mode allowlist currently capped at `v24` to also accept `v25` (artifact/convention/naming/narrative/budget/territorial/group/norm/… schemas and budget equality set → `{v22,v23,v24,v25}`).
- `experiments/matrix_schema.py` finalize/allowlist accepts `v25`; default finalize stays `v4` when V3 flags off.
- Extend `generational_population_profile` (and AF helper) to accept `v24|v25` with the same flag/lifecycle rules; AF requires `v25` + explicit init object.

### NewAgentInitializationSpec (exact child keys — locked shape)

Closed, frozen run-level spec under root key `new_agent_initialization` on v25:

| Key | Role |
| --- | --- |
| `species_defaults_id` | Closed string id resolved by species-defaults registry (at least `species_default_v1`) |
| `parameter_distributions` | Exact frozen object: `{ "distribution_id": <id>, "params": {…} }` where each `distribution_id` has its own exact param key set |
| `innate_drive_policy` | Closed policy id + exact params for limited innate drives (baseline + optional seeded deltas within closed bounds); never copies another agent's `DriveProfile` |
| `physical_condition_policy` | Closed policy id + exact params for body physiology at entry (health/hunger/thirst/fatigue/temperature/carry bounds) — objective only |
| `spawn_location_policy` | Closed policy (see spawn-location precedence below) |
| `dependency_binding` | Locked to `from_lifecycle_stage` in this plan |
| `objective_inheritance` | Exact object `{ "allowed_keys": [<closed keys>] }`; default `allowed_keys=[]` |
| `creation_reason_policy` | Closed reason codes: at least `demographic_policy`, `external_entry`, `experiment_inject` |
| `provenance_policy` | Exact object controlling whether origin refs are recorded (ids + role labels only; no kinship graph) |

**Shipped `parameter_distributions.distribution_id` registry (exact):**

| Id | Exact `params` keys |
| --- | --- |
| `none` | _(empty)_ |
| `uniform_drive_delta` | `drive_kind`, `min_delta`, `max_delta` (unit-interval deltas applied to innate baseline only) |

**Shipped `objective_inheritance.allowed_keys` closed set:** only `carry_capacity` may appear; default is empty. Any other key (including every subjective store name) fails closed at decode/construction.

Forbidden on this object and on `objective_inheritance` allowlist: episodic memory, beliefs, self-model, theory-of-mind / social-inference state, goals / goal boards, cultural narratives, semantic naming ledgers, social norms/conventions, cognition-trace rows, relationships, skill ledgers, full map knowledge, language packs, history dumps.

### Species defaults registry (locked)

- Closed registry keyed by `species_defaults_id`.
- Ship at least `species_default_v1`: builds a **fresh** `AgentCognitionSpec(agent_id=new_owner)` with default modes (no copy from another live runtime or from `config.agents[0]` state), default drive baseline via innate policy, and empty cultural/skill ledger policy.
- Unknown `species_defaults_id` fails closed at construction/decode (`unknown_species_defaults_id`).
- Cognition **modes** may be enabled by the pack (capacity to learn later); ledger **content** must start empty.

### Spawn-location precedence (locked)

1. **Demographic admits** (`OriginProvenance.DEMOGRAPHIC_POLICY`): `DemographicEntryCandidate.spawn_location_id` is authoritative.
2. `spawn_location_policy` must be either:
   - `defer_to_candidate` (exact policy id; empty/no location params), or
   - an allowlist policy whose exact location-id allowlist **contains** the candidate location (else fail closed `spawn_location_not_allowed`).
3. **External entry** (`EXTERNAL_ENTRY`): resolve location solely via `spawn_location_policy` (`fixed` with exact `location_id`, or `seeded_allowlist` with exact `location_ids` tuple); never invent locations absent from world state.

### Subjective-copy deny-list (locked)

At mid-run construction, assert empty/fresh owner-scoped stores and never read another agent's:

1. Episodic memory / `MemoryService` traces
2. Semantic beliefs / belief history
3. Self-model / extended identity beliefs
4. Theory of Mind / advanced social-inference hypotheses
5. Goals / `GoalBoard` / `initial_goals` from another agent
6. Cultural narratives / narrative lineage ledgers
7. Cognition-trace invocations/stages for another owner
8. Relationship profiles
9. Semantic naming ledgers
10. Social-norm / social-convention ledgers
11. Skill-learning ledgers

**Mode vs content:** species defaults may enable learning **modes**; blank-slate asserts **empty content**. Architecture test: mid-run path must not call copy helpers from another owner's scope. Unit test: after admit, all listed stores for the new owner are empty even if bootstrap agents are richly populated.

### NewAgentInitialization pipeline (locked stages + ownership)

**WorldEngine / shared body builder (pre-admit, Task 9 orchestration):**

1. **Resolve creation request** — from demographic candidate / external entry; attach `creation_reason`, optional origin refs, config fingerprint.
2. **Draw seeded parameters** — `create_named_stream(run_config, StreamScope(namespace="new_agent_init", names=(run_id, agent_id, draw_name)))`; never wall clock.
3. **Build objective body** — physical conditions + spawn location per precedence (shared helper used by both `admit_population_entry` and tick-path demographic admit — replace bare `default_entrant_body` when policy active).
4. **Bind lifecycle/dependency** — existing stage/dependency resolution at age 0; no subjective maturity beliefs.
5. **Apply objective inheritance** — only `allowed_keys` from origin body facts when configured; fail closed on forbidden keys.
6. **Admit via WorldEngine** — emit `AgentCreated` → `AgentInitializationRecorded` → `AgentEnteredWorld`; create lifecycle record.

**Runner (post-admit, Task 7 bundle bind):**

7. **Construct blank subjective bundle** — fresh `MemoryScope`, empty stores per deny-list, drives from innate policy, cognition from species defaults registry (not live `agents[0]` clone).
8. **Bind runtime** — `_AgentBundle` + translator rebuild (v3-02 ordinal semantics).

Cultural knowledge remains absent: no map completeness injection, no naming/norm/narrative/history seeds.

### Provenance payload (locked — sibling detail)

Do **not** extend the v9 `AgentCreated` field set (keeps existing lifecycle decode stable).

Add sibling detail `AgentInitializationRecorded` (system / `SystemEffectFamily.LIFECYCLE`), emitted immediately after `AgentCreated` and before `AgentEnteredWorld`:

| Field | Notes |
| --- | --- |
| `body_id` / `agent_id` | Same identity as the paired `AgentCreated` |
| `creation_reason` | Closed stable id |
| `origin_refs` | Tuple of `{agent_id?, body_id?, role}` — optional; empty when none; **not** kinship edges |
| `initial_conditions` | Exact structured summary: `location_id`, `dependency_status`, `stage`, physical scalars (`health`, `hunger`, `thirst`, `fatigue`, `temperature`, `carry_capacity`) |
| `creation_config_id` | Stable fingerprint of `NewAgentInitializationSpec` (+ demographic policy id) |

### Event / persistence write-pair (locked)

- Introduce `EVENT_SCHEMA_REPLAY_V10` when the new-agent provenance channel is active (`AgentInitializationRecorded` emitted).
- Pair persistence codec `"v7"` with event schema 10.
- Extend `checkpoint_schema_for_production(*, …, new_agent_provenance_active: bool = False)`:
  1. `new_agent_provenance_active` → `(EVENT_SCHEMA_REPLAY_V10, "v7")`
  2. Else lifecycle → `(EVENT_SCHEMA_REPLAY_V9, "v6")`
  3. Else artifacts → `(v8, "v5")`
  4. Else dynamics → `(v7, "v4")`
  5. Else production → `(v6, "v3")`
  6. Else → `(replay-v5, "v2")`
- Wire callers in `engine` / `service` / `runner` to pass the new flag when v25 init provenance is active.
- When only v3-02 lifecycle fields are present without extended provenance, keep `(9, "v6")`.
- Legacy decode of v9 / codec v6 remains accepted; v10 detail union accepts lower-channel kinds when those channels are also active. `AgentInitializationRecorded` illegal on schemas &lt; 10.
- Update `schema_projector_compatible`, journal encode/decode, and `world/_replay` projector for the new kind.

### Observer Protocol (locked)

- Keep `observer-protocol-v1` (no rename).
- Append semantic type `AGENT_INITIALIZED` (detail kind `agent_initialization_recorded`) to `SEMANTIC_EVENT_TYPES` / `SEMANTIC_TYPE_BY_KIND` and Godot `models.gd` mirrors.
- Update all `len(SEMANTIC_EVENT_TYPES) == 39` pins (and suffix/prefix slices) to **40**.
- Route `AGENT_INITIALIZED` under Godot timeline `birth` category with `AGENT_CREATED` / `AGENT_ENTERED_WORLD`; do not invent births from roster alone.
- Map new detail kind in `simulation.causal_debugger._DETAIL_KIND_TO_SEMANTIC_TYPE`.

### Replay / fork (locked)

- Snapshots restore init config fingerprint, lifecycle records, registration order, and `AgentInitializationRecorded` fields needed for exact continuation.
- Live continuation after restore must reproduce the next demographic admit identically (same agent_id, body, location, physical draws, provenance).
- Research-fork from a lifecycle+init checkpoint must preserve blank-slate subjective stores for agents created after the fork point and identical objective creation events.
- Twin same-seed runs with v25 init on prove identical creation event sequences and empty subjective-store invariants.

### Non-Goals

- Biological sex, mating, pregnancy, gestation, parentage graphs, kinship inheritance (`kinship_inheritance`).
- Migration / multi-polity / institutions / cultural-historical memory flags.
- Owning `multi_hop_testimony_tracking`.
- Auto-forming subjective age/maturity/social-role/map/language/norm/"I was just born" beliefs at birth (later cognition plan).
- Teaching complete culture at creation; culture is learned post-entry.
- New inspection HTTP fields for dynamic roster (still deferred from v3-02).
- Scripted civilization or “population must grow / culture must transfer” mandates.
- `prepare_parallel=True`.
- Alembic `0018` by default; `/v2` HTTP; renaming `observer-protocol-v1`.
- LLM → world shortcuts for spawning agents.
- Dropping legacy replay/runner/codec decode sets.
- Extending the v9 `AgentCreated` field set (use sibling `AgentInitializationRecorded` instead).

## Commit Plan
- **Commit 1** (after tasks 1–4): `feat(simulation): add NewAgentInitialization types, deny-list, and species defaults`
- **Commit 2** (after tasks 5–7): `feat(simulation): own runner-config-v25 and blank-slate mid-run bind`
- **Commit 3** (after tasks 8–12): `feat(world,simulation): init pipeline, provenance events, and schema v10 write-pair`
- **Commit 4** (after tasks 13–15): `feat(persistence,observer): codec v7 and AGENT_INITIALIZED timeline`
- **Commit 5** (after tasks 16–18): `test(v3): blank-slate bootstrap, replay, and fork proofs`
- **Commit 6** (after task 19): `docs(v3): document NewAgentInitialization seams and contracts`

## Tasks

### Phase 1: Domain contracts and deny-list

- [x] Task 1: Define closed NewAgentInitialization domain types.
  - Deliverable: Add frozen types for `NewAgentInitializationSpec` with the exact child keys locked above, including `CreationProvenance` / `OriginRef` (agent_id?, body_id?, role) forbidding kinship-shaped fields. Enforce shipped `parameter_distributions` ids (`none`, `uniform_drive_delta`) with exact param key sets and `objective_inheritance.allowed_keys ⊆ {carry_capacity}`. Unit-test construction reject paths for forbidden inheritance keys and invalid distribution shapes. Include `canonical_payload()` / fingerprint helper suitable for `creation_config_id`.
  - Files: `src/simulation/new_agent_initialization.py`, `src/simulation/__init__.py`, `tests/unit/test_new_agent_initialization_domain.py`.
  - Logging: Module may be log-free for pure types; tests DEBUG case ids only; never dump distribution payloads as free text.
  - Dependencies: None.

- [x] Task 2: Lock subjective-copy deny-list helpers and architecture guard.
  - Deliverable: Implement a closed forbid set + `assert_blank_slate_subjective_state(owner, …)` covering memory, beliefs, self-model, ToM, goals, narratives, cognition-trace, **relationships, semantic naming, social norms/conventions, and skill ledgers**. Document mode-vs-content rule. Add architecture/unit tests that mid-run construction must not copy another owner's stores.
  - Files: same init module as Task 1, `tests/architecture/test_v3_new_agent_blank_slate.py` (or extend `tests/architecture/test_v3_scaffolding_invariants.py`), `tests/unit/test_new_agent_blank_slate_guard.py`.
  - Logging: ERROR on deny-list violation with reason codes only (`subjective_copy_forbidden`, store name); never payloads.
  - Dependencies: Task 1.

- [x] Task 3: Register closed species-defaults packs.
  - Deliverable: Implement `species_defaults_for(species_defaults_id) -> SpeciesDefaultsPack` producing a fresh `AgentCognitionSpec` for the new owner plus innate drive baseline hooks. Ship `species_default_v1`. Fail closed on unknown ids. Unit-test that two resolutions for different agent ids never share mutable ledger state and never read `config.agents[0]` live stores.
  - Files: `src/simulation/new_agent_initialization.py` (or `species_defaults.py`), `tests/unit/test_species_defaults_registry.py`.
  - Logging: DEBUG species_defaults_id + agent_id; ERROR `unknown_species_defaults_id`.
  - Dependencies: Task 1.

- [x] Task 4: Define seeded parameter-draw helpers on SimulationRunConfig streams.
  - Deliverable: Implement deterministic draws from `parameter_distributions` using `create_named_stream` / `StreamScope(namespace="new_agent_init", names=(run_id, agent_id, draw_name))` on the runner's `SimulationRunConfig` (same pattern as demographic streams in `engine.py`). Pure unit tests for same-seed identity and cross-agent stream isolation. No wall clock.
  - Files: init module or `src/simulation/new_agent_rng.py`, `tests/unit/test_new_agent_init_rng.py`.
  - Logging: DEBUG scope namespace + draw name + agent_id only; never sampled values at INFO.
  - Dependencies: Task 1.

### Phase 2: Runner schema and blank-slate bind

- [x] Task 5: Introduce `runner-config-v25` + `new_agent_initialization` encode/decode and gate rewrite.
  - Deliverable: Add `RUNNER_SCHEMA_VERSION_V25`, exact `_require_keys` = v24 ∪ `new_agent_initialization`, encode/decode, fingerprint inclusion when present. Synthesize defaults on v24 decode. Reject v25 without exact object. Rewrite `generational_population` gate to accept `{v24,v25}`; require `v25` when explicit init object present. Widen every mode allowlist / budget set currently capped at `v24` to include `v25`. Update compatibility matrix + matrix schema allowlist. Keep default write v4 when flags off.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `src/simulation/__init__.py`, `src/experiments/matrix_schema.py`, `tests/unit/test_runner_config_v25_new_agent_initialization.py`, `tests/unit/test_compatibility_matrix.py`.
  - Logging: DEBUG encode/decode schema_version + key counts; ERROR on `new_agent_initialization_requires_v25` / key-set violations; never log full distribution payloads.
  - Dependencies: Task 1.

- [x] Task 6: Wire `SimulationRunner.from_config` for init spec availability.
  - Deliverable: When `generational_population` is on, resolve `NewAgentInitializationSpec` (explicit v25 or synthesized default). Pass into runner state for mid-run pipeline. Flag-off path must not allocate init hooks. Keep fail-closed for other V3 unimplemented flags. Log construction with `new_agent_init=on|default|off`.
  - Files: `src/simulation/runner.py`, `src/simulation/runner_models.py` (helpers), `tests/unit/test_simulation_runner_construction.py` (or sibling).
  - Logging: Keep existing `runner_construction_*` patterns; add `new_agent_init=` and `species_defaults_id=` fields only.
  - Dependencies: Tasks 3, 5.

- [x] Task 7: Blank-slate mid-run `_AgentBundle` bind from species defaults (no `agents[0]` clone).
  - Deliverable: Replace `_sync_mid_run_population_entries` template clone with `construct_blank_agent_bundle(...)` using species defaults + innate drives + deny-list assert. **Do not** own pre-admit orchestration here (Task 9). Keep translator rebuild + ordinal semantics from v3-02. Unit-test that populating bootstrap agent memory/beliefs/goals/narratives/relationships/naming/norms/skills does not appear on the mid-run agent.
  - Files: `src/simulation/runner.py`, `src/simulation/new_agent_initialization.py`, `tests/unit/test_mid_run_agent_bundle.py`, `tests/unit/test_new_agent_no_subjective_copy.py`.
  - Logging: DEBUG `new_agent_bundle_constructed` agent_id + ordinal + species_defaults_id; INFO on bind as today.
  - Dependencies: Tasks 2, 3, 6.

### Phase 3: Pipeline, events, WorldEngine integration

- [ ] Task 8: Extend demographic candidates / admission facts for init blueprint + provenance.
  - Deliverable: Extend `DemographicEntryCandidate` and/or `PopulationEntryAdmission` with fields needed for `creation_reason`, `origin_refs` (optional), and init fingerprint without biology fields. Update `fixed_interval_entry` to populate `creation_reason=demographic_policy` and empty `origin_refs` by default. Keep exact demographic param key sets unless a new policy_id is added with its own exact set. Enforce spawn-location precedence rules against `spawn_location_policy`.
  - Files: `src/simulation/demographic_policy.py`, `src/simulation/engine.py`, `src/simulation/runner_models.py` (param keys if extended), `tests/unit/test_demographic_policy.py`, `tests/unit/test_mid_run_agent_entry.py`.
  - Logging: DEBUG policy_id + candidate_count + creation_reason; never free-text backstories.
  - Dependencies: Task 5.

- [ ] Task 9: Implement NewAgentInitialization pre-admit orchestration.
  - Deliverable: Ordered stages 1–6 per Design Decisions (resolve → draws → body → dependency → objective inheritance → WorldEngine admit call). Shared body/provenance builder consumed by both public `admit_population_entry` and tick-path demographic admit. Fail closed on forbidden inheritance keys, unknown/disallowed location, population cap, lifecycle channel off. Unit-test stage order with fakes. Bundle bind remains Task 7.
  - Files: `src/simulation/new_agent_initialization.py`, `src/simulation/engine.py`, `tests/unit/test_new_agent_initialization_pipeline.py`.
  - Logging: DEBUG stage name + agent_id + reason codes; INFO creation accepted with agent_id/body_id/tick/creation_reason; never observation/memory payloads.
  - Dependencies: Tasks 4, 7, 8.

- [ ] Task 10: Add `AgentInitializationRecorded` + event schema v10 (keep `AgentCreated` v9 field set unchanged).
  - Deliverable: Add detail type `AgentInitializationRecorded` with exact provenance fields locked above. Introduce `EVENT_SCHEMA_REPLAY_V10`. Detail illegal on schemas &lt; 10; v10 union accepts lower-channel kinds. Update normalize/validate/encode paths, journal codec, and fixtures. Do **not** add provenance fields to `AgentCreated`.
  - Files: `src/world/events.py`, `src/world/__init__.py`, `src/world/_replay.py`, `src/simulation/serialization.py`, `src/simulation/journal.py`, `src/simulation/compatibility.py`, `tests/unit/test_new_agent_events_schema_v10.py`.
  - Logging: ERROR on schema/channel mismatch reason codes; DEBUG event_type + schema version only.
  - Dependencies: Tasks 8, 9.

- [ ] Task 11: Extend `checkpoint_schema_for_production` with `new_agent_provenance_active`.
  - Deliverable: Add `new_agent_provenance_active: bool = False` parameter; priority `(10, "v7")` before lifecycle `(9, "v6")`. Wire `engine` / `service` / `runner` callers. Update `schema_projector_compatible` for schema 10. Unit-test priority matrix including lifecycle-only vs provenance-active.
  - Files: `src/simulation/persistence.py`, `src/simulation/engine.py`, `src/simulation/service.py`, `src/simulation/runner.py`, `tests/unit/test_checkpoint_schema_new_agent_provenance.py`.
  - Logging: DEBUG selected event_schema + codec + flag booleans only.
  - Dependencies: Task 10.

- [ ] Task 12: WorldEngine admit paths emit provenance-bearing creation event triple.
  - Deliverable: Both `admit_population_entry` and tick-path demographic admit emit `AgentCreated` → `AgentInitializationRecorded` → `AgentEnteredWorld` under `SystemEffectFamily.LIFECYCLE` when provenance channel active; use shared body builder from Task 9. Bootstrap agents still do not emit created/entered/initialized events. Preserve append-only immutability and max_population enforcement.
  - Files: `src/simulation/engine.py`, `tests/unit/test_mid_run_agent_entry.py`, `tests/unit/test_new_agent_provenance_events.py`.
  - Logging: INFO entry accepted with agent_id/body_id/tick/creation_reason/population_count; ERROR reject reason codes.
  - Dependencies: Tasks 9, 10, 11.

### Phase 4: Persistence, observer, causal debugger

- [ ] Task 13: Persistence codec `v7` + snapshot/projector/branch restore for init provenance.
  - Deliverable: Pair codec `"v7"` with event schema 10 when new-agent provenance channel active. Snapshots restore lifecycle records, registration order, init fingerprint, and fields needed for exact continuation. Prove research-fork restore preserves next admit identity. Legacy codecs v1–v6 remain accepted. Flag-off / lifecycle-only default write stays non-v10.
  - Files: `src/simulation/persistence.py`, projector/replay modules, `src/simulation/branch_service.py` / branching tests as needed, `tests/unit/test_new_agent_snapshot_codec_v7.py`.
  - Logging: ERROR on codec/schema mismatch; DEBUG codec version + provenance_field_count.
  - Dependencies: Tasks 11, 12.

- [ ] Task 14: Observer Protocol + Godot timeline for `AGENT_INITIALIZED`.
  - Deliverable: Append `AGENT_INITIALIZED` to Python `SEMANTIC_EVENT_TYPES` / maps and Godot `models.gd` mirrors. Update all `len(SEMANTIC_EVENT_TYPES) == 39` pins to **40**. Map `agent_initialization_recorded` → `AGENT_INITIALIZED`. Add type to Godot `birth` category alongside created/entered. Keep `observer-protocol-v1`. Extend protocol mirror tests.
  - Files: `src/observer/version.py`, `src/observer/adapt.py`, `src/observer/contracts.py` (if touched), `clients/godot-observer/scripts/protocol/models.gd`, `clients/godot-observer/scripts/ui/timeline.gd`, `clients/godot-observer/scripts/protocol/event_router.gd` (as needed), `tests/unit/test_godot_protocol_mirror.py`, `tests/unit/test_observer_contracts.py`, related observer unit tests.
  - Logging: DEBUG semantic map misses as `unknown_event_kind`; never simulation mutation from observer.
  - Dependencies: Task 10.

- [ ] Task 15: Causal debugger maps for `agent_initialization_recorded`.
  - Deliverable: Add detail-kind → semantic mapping for `agent_initialization_recorded` → `AGENT_INITIALIZED` in `simulation.causal_debugger._DETAIL_KIND_TO_SEMANTIC_TYPE` (and inverse/router tables that must stay in sync). Unit-test resolve paths.
  - Files: `src/simulation/causal_debugger.py`, causal debugger unit tests.
  - Logging: DEBUG unmapped_kind reason codes only.
  - Dependencies: Tasks 10, 14.

### Phase 5: Compatibility proofs, experiment, docs

- [ ] Task 16: V2 / v3-02 flags-off and v24 lifecycle compat tests.
  - Deliverable: Prove V3 flags off keep identical `exact_trajectory_hash` / objective commit chains vs baseline. Prove v24 lifecycle-on synthesized defaults still run without requiring v25 and without emitting `AgentInitializationRecorded`. Keep `test_v1_regression_gate.py` and `test_v2_scientific_invariants.py` green under flags-off. Init-on arms stay off the V1 gate.
  - Files: `tests/unit/test_v3_new_agent_flags_off_compat.py`, updates to golden/scaffolding gates as needed.
  - Logging: Test INFO start/end with experiment_id + hash prefixes only.
  - Dependencies: Tasks 6, 13.

- [ ] Task 17: Blank-slate + seeded init determinism, replay, and forked-replay proofs.
  - Deliverable: Same-seed twin runs with v25 init on prove identical creation event sequences (including `AgentInitializationRecorded`), provenance fields, physical draws, and empty subjective stores for new agents. Replay from snapshot mid-run matches live continuation for the next admit. Forked replay from a checkpoint reproduces subsequent agent creation exactly. Assert new agents lack map/language/norm/narrative/history/skill ledger content at entry.
  - Files: `tests/unit/test_new_agent_bootstrap_replay_determinism.py`, `tests/unit/test_new_agent_fork_replay.py`.
  - Logging: DEBUG tick + event_type counts; never full event/memory payloads.
  - Dependencies: Tasks 9, 12, 13.

- [ ] Task 18: Off-gate Experiment AF for new-agent bootstrap on v25.
  - Deliverable: Add Experiment AF (`experiment-af-new-agent-bootstrap` or similar) on `runner-config-v25` with explicit `new_agent_initialization`, proving mid-run agents are blank-slate and `AgentInitializationRecorded` appears. Extend `generational_population_profile` (or add `new_agent_bootstrap_profile`) to accept v25. Keep AE on v24. Off V1 gate. Do not claim scientific emergence.
  - Files: `src/experiments/catalog.py`, `src/experiments/__init__.py`, `tests/unit/test_new_agent_bootstrap_catalog_arm.py`.
  - Logging: INFO experiment_id + schema_version + tick_count; DEBUG creation/init event counts + blank_slate assertions.
  - Dependencies: Tasks 5, 9, 16, 17.

- [ ] Task 19: Mandatory docs checkpoint (`/aif-docs` scope).
  - Deliverable: Update `docs/architecture.md` V3 extension seams for NewAgentInitialization / blank-slate deny-list / species defaults / spawn precedence / provenance sibling event; Downstream V3 checklist note that this plan extends owned `generational_population` (no new flag); document v25 / event v10 / codec v7 write-pair priority and `new_agent_provenance_active`; document no cultural/map/language injection at birth; update `docs/persistence.md`, `docs/observer.md` / `docs/godot-observer.md`, `docs/cognition-runtime.md`; update `.ai-factory/DESCRIPTION.md` and `.ai-factory/ARCHITECTURE.md` briefly. Explicit non-goals: kinship, culture transfer at birth, inspection HTTP, extending `AgentCreated` fields. Do not edit ROADMAP as owned artifact (coordinate via `/aif-roadmap` if milestone text should change).
  - Files: `docs/architecture.md`, `docs/persistence.md`, `docs/observer.md`, `docs/godot-observer.md`, `docs/cognition-runtime.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`.
  - Logging: n/a (docs).
  - Dependencies: Tasks 16–18.

## Implementation notes for `/aif-implement`

- Prefer extending existing bounded packages (`simulation`, `world`, `observer`, `experiments`) over new top-level packages.
- Keep import-linter contracts; private `world._*` remain engine-only.
- Every new public type stays Pydantic-free in domain packages.
- Verbose logging: IDs, counts, reason codes, schema versions — never observation/communication/memory/belief/narrative payloads.
- When touching Godot, keep presentation-only and update Python↔GDScript protocol mirror tests in the same change.
- Reuse v3-02 admit/translator/ordinal paths; this plan owns **initialization semantics**, not a second roster authority.
- Parent/origin refs are provenance labels only — never open `kinship_inheritance`.
- Keep v9 `AgentCreated` wire stable; all new provenance fields live on `AgentInitializationRecorded`.
