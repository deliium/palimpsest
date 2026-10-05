# Implementation Plan: V3-05 Objective Kinship and Genealogy

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-05
Improved: 2026-10-05 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M7 — V3 Generational Civilization"
Rationale: Owns reserved `kinship_inheritance` for configurable objective genealogy (parent/child/sibling/ancestor/descendant) while keeping it strictly separate from subjective social relationships and deferring cultural inheritance handoff.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M7 — V3 Generational Civilization
INFO [aif-plan] mode=ultra treated as full (richer plan); remaining args describe the feature
INFO [aif-plan] resolved plan file: .ai-factory/plans/v3-05-kinship-genealogy.md (format=slug)
INFO [aif-plan] plan name prefix v3- applied per user request; suggested stem `v3-05-kinship-genealogy`; git.create_branches=false so stem is description slug (branch-derived naming disabled)
INFO [aif-plan] RESEARCH.md absent; research_influenced_plan=false
INFO [aif-plan] plan_default_milestone=auto would surface M6 first; scope is explicitly v3-05 under M7 so linkage uses M7
INFO [aif-improve] applied refinement: v27 root = v23 ∪ kinship with flag-conditional lifecycle/init gates (kinship-only fixed roster without generational_population); kinship graph on engine snapshot/journal like lifecycle_records; co-land replay-v11/codec v8 + ACCEPTED sets + compatibility matrix + select_checkpoint_schema agreed-or chain; kinship_edge_recorded event kind; extend DemographicEntryCandidate parent_agent_ids; from_config owned-flag wiring; kinship_genealogy_profile separate from generational_population_profile; MetricFamilyId registration pattern; observer SEMANTIC count 41 + update closed-catalog tests; dual-flag AH arms; forbid world→social imports for kinship

## Compatibility contract

This plan **owns** `V3CapabilityFlags.kinship_inheritance` for **objective genealogy only**. It must preserve V1/V2 and AE/AF/AG behavior when the flag is off. Cultural inheritance, knowledge handoff, and intergenerational learning policies remain deferred under the same flag slot (later plans), matching how `generational_population` was split across v3-02/v3-03/v3-04.

1. V1/V2 invariants intact. `WorldEngine` remains the only objective mutation authority. Agents receive immutable per-agent `Observation` / `Perspective` only. `WorldEvent` records remain immutable and append-only. Subjective state stays outside the objective fold. Godot remains read-only. Deterministic replay continues. No scripted civilization outcomes.
2. Flag ownership. Add `kinship_inheritance` to `_V3_OWNED_CAPABILITY_FLAGS`. Keep `generational_population` owned. Do **not** own `multi_polity_migration`, `institutional_economy`, `cultural_historical_memory`, or `multi_hop_testimony_tracking`.
3. Flags-off = prior baseline. With all V3 flags off (and kinship off), trajectories and `exact_trajectory_hash` match the pre-plan baseline. AE (v24) / AF (v25) / AG (v26) remain bit-identical when kinship is off.
4. Schema bumps use accepted-set + exact key-set discipline. Never drop accepted V1/V2/V3 versions in the same change that adds a write version.
5. No biological sex, mating, pregnancy, gestation, or human reproductive mechanics. Parent/child edges are **configured / experiment-admitted objective facts**, not biology simulation.
6. **Objective genealogy ≠ subjective social relationships.** Kinship edges must never auto-write `DirectedRelationshipProfile` dimensions (`trust`, `affection`, `loyalty`-shaped debt/respect, etc.), SelfModel / identity aspects, semantic beliefs, group/norm/convention ledgers, or inheritance/ownership rights.
7. Being related must **not** imply affection, trust, loyalty, inheritance rights, obligation, or shared group identity — neither in engine policy nor in analysis labels that feed cognition.
8. Agents may learn or **misunderstand** genealogy only through normal information channels (communication/testimony; optional gated perception). Hidden objective genealogy must not auto-enter cognition.
9. Genealogy persists across deaths (edges survive `Died`; dead agents remain addressable by id for queries).
10. Preserve v3-03/v3-04 locks: blank-slate deny-list; provenance `OriginRef` roles stay non-kinship (`_KINSHIP_ORIGIN_ROLES` remain banned on provenance); Observation `lifecycle` object stays closed; ELDER ≠ leader.
11. Optional tracing/analysis/observer presentation stay outside the objective fold / `EvidenceManifest`.
12. Alembic head stays `0017` unless a proven inspection need appears (default: no `0018`; kinship lives in runner JSON + event/checkpoint/world-state payloads).

## Goal

Implement configurable **objective** kinship/genealogy where the capability is enabled:

- Parent / child edges as authoritative directed facts
- Sibling / ancestor / descendant as **derived** queries (not separately stored edge kinds unless needed for events)
- Strict separation from subjective social relationship profiles
- Survival of the genealogy graph across deaths
- Efficient ancestor/descendant queries with bounded depth
- Research/analysis/inspection exposure for genealogy query + visualization scaffolding for later UI plans
- Fail-closed prevention of hidden genealogical knowledge auto-entering agent cognition
- Off-gate Experiment AH proving the channel

## Design Decisions

### Invariant freeze (non-negotiable)

1. `WorldEngine` remains the only authority over objective kinship mutations (edge establish / optional revoke if ever needed — prefer append-only establish in this plan).
2. Agents receive immutable agent-specific `Observation` only; they never receive the full hidden kinship graph by default.
3. `WorldEvent` records remain immutable; authoritative history stays append-only.
4. Subjective kinship beliefs may be wrong and never fold into objective replay.
5. LLM output remains non-authoritative.
6. No scripted “kinship_must_form / dynasty_emerged / inheritance_settled / family_loyal” booleans.
7. Godot remains read-only; this plan may add a single observer semantic type for kinship edge events but **no** dynasty/loyalty chrome.
8. Runs remain reproducible where claimed (explicit seeds, deterministic streams).

### Capability ownership (locked)

1. Own `kinship_inheritance`. Enabling kinship requires `kinship_inheritance=True` and `schema_version == runner-config-v27` when kinship config is present / non-empty.
2. **Independence from biology:** kinship does **not** require reproductive mechanics.
3. **Roster coupling:**
   - Bootstrap / fixed-roster kinship edges among registered agents are allowed with kinship on even if `generational_population` is off (edges reference existing agent/body ids).
   - Mid-run edge establishment at `admit_population_entry` requires **both** `kinship_inheritance` and `generational_population` (stable reject if kinship admit links requested without lifecycle channel).
4. Other unowned V3 flags still fail closed.
5. When `kinship_inheritance=False`, no kinship graph, no kinship events, no research kinship projection side effects on cognition paths; AE/AF/AG hashes unchanged.

### Scope split inside the flag slot (locked)

| This plan (v3-05) | Deferred (later under same flag) |
| --- | --- |
| Objective parent→child edges | Cultural inheritance / knowledge handoff |
| Derived sibling / ancestor / descendant queries | Intergenerational teaching/learning policies |
| Death-stable genealogy index | Automatic estate / ownership transfer |
| Research query + analysis metric + viz DTOs | Full Research UI / Godot family-tree chrome |
| Optional gated kin-visible perception | Rich kin terminology / naming systems |

### Runner configuration versioning (locked)

Introduce `RUNNER_SCHEMA_VERSION_V27 = "runner-config-v27"`:

- Exact root key set = **full `runner-config-v23` keyset** ∪ sibling root object **`kinship`** (same pattern as v24 adding `population_lifecycle` — **not** an unconditional copy of v26 lifecycle/init requirements).
- Default write remains `runner-config-v4` when all V3 flags are off and no existing mode requires a higher schema.
- `kinship_inheritance=True` requires `schema_version == runner-config-v27` and exact `kinship` object present (stable reject `kinship_requires_v27` / `kinship_config_required`).
- `kinship_inheritance=False` forbids non-empty kinship config on any schema (reject `kinship_config_without_flag`).
- Decode of v23–v26 synthesizes no `kinship` object (absent ≡ flag-off channel).
- **Flag-conditional requirements on v27 (critical — enables kinship-only fixed roster):**
  - `generational_population=True` on v27 ⇒ same rules as today for v24|v25|v26: require `population_lifecycle`; require `new_agent_initialization` when schema carries that key (v27 documents with lifecycle use v25+ init rules); developmental extensions still require v26-equivalent lifecycle children and reject `developmental_stages_require_v26` when non-default developmental children present without v26-compatible lifecycle encoding (prefer AH combined arm on explicit v27 + full lifecycle block copied from AG fixtures).
  - `generational_population=False` on v27 ⇒ **forbid** root `population_lifecycle` and `new_agent_initialization` (reject `kinship_only_forbids_lifecycle_spec` / `kinship_only_forbids_new_agent_init`) — kinship-only profiles use fixed bootstrap roster + `bootstrap_edges` only.
  - Both flags on v27 ⇒ require both `kinship` and `population_lifecycle` (+ `new_agent_initialization` per v25+ rules when mid-run blank-slate admits are used).
- Widen **every** mode allowlist currently capped at `v26` to also accept `v27`.
- Gate rewrite: `generational_population=True` accepts `{v24,v25,v26,v27}`; `kinship_inheritance=True` accepts `{v27}` only.
- `experiments/matrix_schema.py` finalize/allowlist accepts `v27`; finalize selects `v27` when kinship flag/config present; AE stays v24; AF stays v25; AG stays v26; default finalize stays `v4` when V3 flags off.
- Update `simulation/compatibility.py` version matrix row for v27 + kinship write-pair note.

### KinshipSpec (exact root sibling — locked)

Root key `kinship` exact children:

| Key | Role |
| --- | --- |
| `bootstrap_edges` | Ordered frozen list of parent→child edges among bootstrap agents (may be empty) |
| `max_query_depth` | Positive int hard cap for ancestor/descendant traversal (default recommendation: `8`; hard ceiling e.g. `32`) |
| `max_parents_per_child` | Positive int (default `2`; ceiling e.g. `4`) |
| `perception_mode` | Closed id controlling agent-visible kin facts (below) |
| `admit_link_policy` | Exact object controlling whether mid-run admits may establish edges |

**`bootstrap_edges` entry exact keys:**

| Key | Role |
| --- | --- |
| `parent_agent_id` | Existing bootstrap agent id |
| `child_agent_id` | Existing bootstrap agent id; ≠ parent |
| `established_tick` | Non-negative int; usually `0` for bootstrap |

Forbidden on edges / kinship config: `affection`, `trust`, `loyalty`, `obligation`, `inheritance_rights`, `group_id`, `clan`, `dynasty`, `spouse`/`mate` as social bonding, relationship-dimension presets, biology keys (`sex`, `fertility`, `pregnancy`, …).

**`perception_mode` closed ids (initial):**

| Id | Behavior |
| --- | --- |
| `none` | **Default.** No kinship fields on Observation; agents learn only via communication/testimony (may be wrong) |
| `self_incident_public` | Agent may observe only closed kin facts that **directly involve self** and are marked public by edge metadata / policy (never the full graph, never other agents' hidden lineages) |

Forbidden perception modes in this plan: `omniscient`, `full_graph`, `clan_broadcast`.

**`admit_link_policy` exact keys:**

| Key | Role |
| --- | --- |
| `allow_parent_links_on_admit` | bool — when true and both flags on, admit candidates may carry parent agent ids that become objective edges |
| `require_living_parent` | bool — when true, reject admit links if named parent is dead or unknown |

Mid-run parent links use dedicated admit fields (not `OriginRef.role`). Provenance remains banned from kinship-shaped roles.

### Objective domain model (locked)

Prefer package home under `world` (authority) + thin `simulation` wiring — e.g. `world/kinship.py` (pure graph + queries) owned/mutated only via `WorldEngine` / private world modules. Do **not** put objective kinship in `social/` (that package owns subjective directed relationships). `world` must not import `social` (existing import-linter contract).

**Runtime storage (locked):** mirror `lifecycle_records` — keep `KinshipGraph` on the engine snapshot (`WorldEngine._kinship_graph` + journal/checkpoint field e.g. `kinship_edges`), not inside subjective stores and not auto-folded into relationship profiles. Replay rebuilds graph from bootstrap seed + `KinshipEdgeRecorded` projections.

Frozen types (names illustrative; keep Pydantic-free domain style):

- `KinshipEdge` — `{ parent_agent_id, child_agent_id, established_tick, edge_id }` directed parent→child only; `edge_id` from stable id helper (optional deterministic hash of parent|child|tick — no wall clock)
- `KinshipGraph` — adjacency indexes: `children_by_parent`, `parents_by_child` (multi-parent allowed; cap `max_parents_per_child` default `2` in `KinshipSpec` with reject `kinship_too_many_parents`)
- Query API (pure functions):
  - `parents_of(agent_id)` / `children_of(agent_id)`
  - `siblings_of(agent_id)` — agents sharing ≥1 parent, excluding self
  - `ancestors_of(agent_id, *, max_depth)` / `descendants_of(agent_id, *, max_depth)` — BFS/DFS with depth bound; stable tie-break by agent id
  - `related(a, b, *, max_depth)` — optional convenience; does **not** imply social valence

Rules:

1. Store **only** parent→child edges; derive the rest.
2. Reject cycles at establish time (`kinship_cycle_rejected`).
3. Reject duplicate identical parent→child edges (`kinship_duplicate_edge`).
4. Self-parent forbidden.
5. Unknown agent ids rejected at establish (must already be registered or co-admitted in the same atomic batch per engine rules).
6. Edges are not deleted on death; queries include dead agents by default (`include_dead=True` default for research queries).

### Events / write pairs / Observation (locked)

1. New occurrence detail: `KinshipEdgeRecorded` (exact fields: `parent_agent_id`, `child_agent_id`, `established_tick`, `edge_id`; wire kind string **`kinship_edge_recorded`** — snake_case like `lifecycle_stage_changed`). Add to closed `EventDetails` union; `WorldEvent` accepts only when `schema_version == EVENT_SCHEMA_REPLAY_V11` (same pattern as lifecycle v9 details).
2. Introduce `EVENT_SCHEMA_REPLAY_V11` + checkpoint codec **`v8`** when kinship channel is active at run start. **Co-land in one change:** `ACCEPTED_EVENT_SCHEMA_VERSIONS`, `ACCEPTED_PERSISTENCE_CODEC_VERSIONS`, `world/_replay.py` projector, `simulation/serialization.py` encode/decode, `simulation/journal.py` snapshot field, `simulation/compatibility.py` matrix, `tests/unit/test_v3_v2_replay_compat.py` (or sibling), golden round-trip fixtures.
3. Write-pair priority extension (both `checkpoint_schema_for_production` **and** `engine.select_checkpoint_schema` agreed-or validation):

   `kinship_active` → `(EVENT_SCHEMA_REPLAY_V11, "v8")`;  
   else provenance → `(v10, "v7")`;  
   else lifecycle → `(v9, "v6")`; … (unchanged remainder).

   Add `WorldEngine.kinship_channel_active` (and pass `kinship_active=` from runner) parallel to `lifecycle_channel_active` / `new_agent_provenance_active`.

4. **Observation:** default `perception_mode=none` ⇒ **no** new Observation kinship fields (channel-off wire unchanged).  
   When `self_incident_public`: add closed optional object (e.g. `kinship_visible`) on self/other visibility surfaces with **exact minimal keys only** (e.g. `parents`, `children` agent-id tuples involving self that policy marks public). Never ancestors/descendants dump. Live/restored observation parity remains the hard gate (`tests/unit/test_checkpoint_restoration.py` siblings).
5. Observer: add semantic type `KINSHIP_EDGE_RECORDED` (SEMANTIC count **41**). Map `kinship_edge_recorded` → that type. Update closed-catalog tests that assert `len(SEMANTIC_EVENT_TYPES) == 40` → **41**. Extend `causal_debugger` semantic tables if kinship is user-visible in debugger (metadata-only). No loyalty/dynasty presentation chrome in Godot this plan.

### Death persistence (locked)

1. `Died` does not remove kinship edges.
2. Checkpoint/restore round-trips the full graph including edges involving dead agents.
3. Research queries default to including dead nodes; cognition never receives the research projection.
4. Analysis may report living-only filters as optional parameters — still analysis-only.

### Cognition / social separation (locked)

1. Establishing a kinship edge must not call relationship revision, belief formation, SelfModel, group formation, norms, conventions, reputation, or teaching APIs.
2. Architecture tests: forbid imports from objective kinship modules into `social.relationships` writers, `agents.cognition.identity` / SelfModel projectors, and belief auto-writers.
3. Communication remains the primary learning channel: speakers may claim kinship in ordinary `Talk`/`Ask`/`Tell` content; receivers form **fresh** subjective evidence that may be false. No automatic “download objective edge → belief”.
4. Optional `self_incident_public` perception is observe-only — perception must not form memories/beliefs (existing invariant).

### Efficient queries (locked)

1. Maintain bidirectional adjacency maps updated on edge establish (O(1) parent/child lookup).
2. Ancestor/descendant: iterative BFS with `max_depth` from config (per-call override allowed up to config cap).
3. Sibling: union of children of each parent, minus self; deterministic sorted ids.
4. Unit-test depth bounding and cycle rejection; property tests for determinism of query order.

### Research tooling & viz scaffolding (locked)

Expose genealogy **outside** cognition:

| Surface | Deliverable in this plan |
| --- | --- |
| `analysis` | Analysis-only family `kinship_genealogy@1` (graph stats: edge count, component sizes, mean depth reached, orphan count) — NetworkX allowed inside analysis only; never feeds cognition |
| `simulation.inspection` | Detached objective kinship projection DTO + bounded query helpers (`parents`/`children`/`siblings`/`ancestors`/`descendants`) |
| `api` | Prefer extending existing objective inspection with a read-only kinship query document under `objective_inspection` capability **or** document a stable DTO + loader port if HTTP is deferred; do **not** require new Alembic tables |
| Research UI / Godot | **Scaffolding only:** frozen DTO/schema comments + docs noting later UI plans consume inspection/analysis outputs; no mandatory SPA/Godot tree view in this plan |

Hard boundary: experiment collectors / inspection / analysis outputs must not flow into CognitiveLoop, memory formation, prompts, or action selection (existing architecture gates).

### Experiment AH (locked)

- Catalog arm `experiment-ah-kinship-genealogy` on **runner-config-v27**, off the V1 gate.
- Profile: `kinship_genealogy_profile` requiring `kinship_inheritance=True` + exact `kinship` object — **do not** reuse `generational_population_profile` (that profile forbids other V3 flags). Profile allows kinship-only **or** kinship+generational combined arms.
- Arms (minimal set):
  - **kinship-only** (`generational_population=false`): bootstrap multi-generation parent chain + sibling set on fixed roster
  - death of an ancestor mid-run with query persistence (kinship-only arm)
  - `perception_mode=none` (default) vs `self_incident_public`
  - **combined** arm: `generational_population=true` + lifecycle/init + mid-run admit with `parent_agent_ids` on `DemographicEntryCandidate`
- Prove: derived sibling/ancestor/descendant; depth bound; no relationship-dimension side effects; flags-off hashes stable; AE/AF/AG unchanged when kinship off.
- Matrix allowlist includes AH without enabling on default batches.

### Out of scope

- Biological sex, mating, pregnancy, gestation, fertility
- Cultural inheritance / knowledge preservation-loss engines
- Automatic inheritance of items, territory, roles, or obligations
- Spouse/mate social bonding systems
- Scripted dynasty / clan / loyalty outcomes
- Owning `multi_polity_migration`, `institutional_economy`, `cultural_historical_memory`, `multi_hop_testimony_tracking`
- Full Research UI family-tree page / Godot dynasty chrome (scaffold DTOs/docs only)
- Alembic `0018` by default
- Widening `OriginRef` to accept kinship roles (keep provenance separate)
- Auto-writing kinship into SelfModel or relationship dimensions

## Commit Plan

- **Commit 1** (after tasks 1–3): `feat(v3): add kinship graph contracts and own kinship_inheritance on runner-config-v27`
- **Commit 2** (after tasks 4–6): `feat(v3): record kinship edges in WorldEngine with replay-v11/codec v8`
- **Commit 3** (after tasks 7–9): `feat(v3): bounded genealogy queries, death persistence, and cognition isolation gates`
- **Commit 4** (after tasks 10–12): `feat(v3): research kinship projection, analysis metric, and Experiment AH`
- **Commit 5** (after tasks 13–14): `docs(v3): kinship genealogy seams and flags-off regression proofs`

## Tasks

### Phase 1: Domain & config contracts

- [x] Task 1: Add objective kinship domain types and pure query helpers
  - Deliverable: Frozen `KinshipEdge` / `KinshipGraph` (or equivalent) with bidirectional indexes; pure `parents_of` / `children_of` / `siblings_of` / `ancestors_of` / `descendants_of` with `max_depth`; cycle/duplicate/self-parent validators.
  - Package under `world/kinship.py` (preferred) — **not** `social/`.
  - LOGGING: DEBUG on query `{agent_id, relation, depth, result_count}`; ERROR on validation with stable `code=`; never log social valence.
  - Files: `src/world/kinship.py`, `src/world/__init__.py`, `tests/unit/test_kinship_graph_queries.py`
  - Depends on: —

- [x] Task 2: Own `kinship_inheritance` + introduce `KinshipSpec` / runner-config-v27
  - Add flag to `_V3_OWNED_CAPABILITY_FLAGS`; introduce `RUNNER_SCHEMA_VERSION_V27`; exact root = `_RUNNER_ROOT_KEYS_V23` ∪ `{kinship}`; encode/decode exact keys; implement **flag-conditional v27 gates** (kinship-only forbids lifecycle/init root objects; combined/both-flag rules per Design Decisions); reject biology/social-valence forbidden keys; widen allowlists capped at v26; matrix finalize selects v27 when kinship present; update `SimulationRunner.from_config` so owned `kinship_inheritance` is not in `v3_unimplemented`.
  - Fail closed still for other unowned V3 flags.
  - LOGGING: INFO on schema select `{schema_version, kinship_inheritance, generational_population, edge_count, perception_mode}`; stable reject codes.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `src/simulation/runner.py`, `src/experiments/matrix_schema.py`, unit tests `tests/unit/test_runner_config_v27_*.py`, extend `tests/unit/test_v3_scaffolding_gate.py`
  - Depends on: Task 1

- [x] Task 3: Bootstrap edge validation against registrations
  - At `SimulationRunner.from_config` / engine bootstrap, validate `bootstrap_edges` reference registered agents; establish graph before tick 0 observations; reject unknown ids / cycles.
  - Kinship-off ⇒ no graph allocated (or empty inert).
  - LOGGING: INFO `{bootstrap_edge_count}`; ERROR codes on invalid bootstrap.
  - Files: `src/simulation/runner.py`, `src/simulation/engine.py` (bootstrap seam), tests
  - Depends on: Task 2

### Phase 2: Engine events & persistence

- [x] Task 4: `KinshipEdgeRecorded` event + replay-v11 / codec v8 write pair
  - Add `KinshipEdgeRecorded` + kind `kinship_edge_recorded` to closed event union; extend replay projector; bump `EVENT_SCHEMA_REPLAY_V11` + codec `v8` journal field for kinship edges; extend `checkpoint_schema_for_production` **and** `select_checkpoint_schema` agreed-or chain (`kinship_active` first); wire `WorldEngine.kinship_channel_active`.
  - Co-land: `ACCEPTED_EVENT_SCHEMA_VERSIONS`, `ACCEPTED_PERSISTENCE_CODEC_VERSIONS`, compatibility matrix, serialization round-trip, replay restore of bootstrap + mid-run edges.
  - LOGGING: INFO on edge recorded `{parent_agent_id, child_agent_id, tick, edge_id}`; DEBUG on schema pair choice `{kinship_active, event_schema, codec}`.
  - Files: `src/world/events.py`, `src/world/_replay.py`, `src/simulation/persistence.py`, `src/simulation/serialization.py`, `src/simulation/journal.py`, `src/simulation/engine.py`, `tests/unit/test_kinship_events_replay.py`, `tests/unit/test_v3_v2_replay_compat.py` (extend)
  - Depends on: Task 1, Task 2

- [x] Task 5: WorldEngine establish API + mid-run admit parent links
  - Internal/engine API to establish edges (bootstrap + explicit admit path). Extend `DemographicEntryCandidate` with exact optional `parent_agent_ids: tuple[AgentId, ...]` (empty when absent) — **not** `OriginRef.role`. When `admit_link_policy.allow_parent_links_on_admit` and both flags on, validate parents (living/known per policy), enforce `max_parents_per_child`, emit `KinshipEdgeRecorded` in the same atomic commit as `AgentCreated`/`AgentEnteredWorld`.
  - Reject admit kinship without `generational_population`; keep `OriginRef` / `_KINSHIP_ORIGIN_ROLES` banned on provenance.
  - LOGGING: INFO/WARN with stable codes; no relationship payloads.
  - Files: `src/simulation/engine.py`, `src/simulation/demographic_policy.py` (or candidate module), `src/simulation/new_agent_initialization.py` (no provenance role overload), tests
  - Depends on: Task 3, Task 4

- [x] Task 6: Observer semantic mapping for kinship edges
  - Add `KINSHIP_EDGE_RECORDED` to `SEMANTIC_EVENT_TYPES` (count **41**) + `SEMANTIC_TYPE_BY_KIND` mapping; update `tests/unit/test_observer_contracts.py`, `test_artifact_observer.py`, `test_developmental_stages_catalog_arm.py`, and other `len(SEMANTIC_EVENT_TYPES) == 40` assertions; causal debugger label if required by existing tables; no dynasty chrome.
  - LOGGING: follow existing observer metadata-only patterns.
  - Files: `src/observer/version.py`, `src/simulation/causal_debugger.py` (if needed), observer unit tests
  - Depends on: Task 4

### Phase 3: Perception isolation, death, cognition gates

- [ ] Task 7: Perception modes — default none; optional self-incident public
  - Implement `perception_mode=none` (no Observation change) and `self_incident_public` closed optional visibility object with live/restored parity tests.
  - Perception must not form memories/beliefs; never project full graph.
  - LOGGING: DEBUG on visible kin fact counts; never log claimed social meaning.
  - Files: `src/world/_perception.py`, observation contracts, `tests/unit/test_kinship_perception_parity.py`
  - Depends on: Task 4, Task 5

- [ ] Task 8: Death persistence + checkpoint/replay proofs
  - Prove edges survive `Died`; restored engines answer the same ancestor/descendant queries including dead nodes; twin-run determinism with kinship on.
  - LOGGING: DEBUG on restore edge counts.
  - Files: checkpoint/replay tests `tests/unit/test_kinship_death_persistence.py`, `tests/unit/test_kinship_replay_determinism.py`
  - Depends on: Task 4, Task 5

- [ ] Task 9: Architecture gates — no auto social/SelfModel/belief writes
  - Tests asserting kinship establish does not revise relationship dimensions; forbidding kinship→social/identity imports; asserting related≠trust/affection/loyalty/obligation/inheritance/group identity in engine policy comments + tests.
  - LOGGING: N/A for architecture tests; production paths metadata-only.
  - Files: `tests/architecture/test_v3_kinship_isolation.py`, possibly extend scaffolding invariants
  - Depends on: Task 5, Task 7

### Phase 4: Research surfaces & experiment

- [ ] Task 10: Inspection projection + bounded query helpers for research
  - Detached objective kinship DTO + query helpers suitable for later UI (parents/children/siblings/ancestors/descendants with depth). Wire read path via existing inspection loader patterns; HTTP route only if it fits current `/v1/simulations/...` inspection style under `objective_inspection` without Alembic.
  - LOGGING: INFO/DEBUG on query `{run_id, agent_id, relation, depth, result_count}` — no cognition feedback.
  - Files: `src/simulation/inspection.py`, `src/api/` inspection routes if applicable, `src/persistence/` if loader needed, unit tests
  - Depends on: Task 1, Task 8

- [ ] Task 11: Analysis metric `kinship_genealogy@1`
  - Analysis-only specification + collector following `spatial_control@1` pattern (`MetricFamilyId` in `analysis/specifications.py`, compute module, wire in `metric_service.py`); NetworkX ok inside analysis only; register in phenomenon/metric catalog; never imported by cognition.
  - LOGGING: metadata-only metric ids/counts.
  - Files: `src/analysis/kinship_genealogy_metrics.py` (or sibling), `src/analysis/specifications.py`, `src/analysis/metric_service.py`, `tests/unit/test_kinship_genealogy_metric.py`
  - Depends on: Task 1, Task 8

- [ ] Task 12: Experiment AH + catalog profile
  - Add `experiment-ah-kinship-genealogy` / `kinship_genealogy_profile` on v27; arms per Design Decisions; off V1 gate; AE/AF/AG unchanged; matrix allowlist includes AH.
  - LOGGING: experiment coordinator metadata-only.
  - Files: `src/experiments/catalog.py`, `tests/unit/test_kinship_catalog_arm.py`
  - Depends on: Task 2, Task 5, Task 7, Task 8

### Phase 5: Regression & docs

- [ ] Task 13: Flags-off / AE/AF/AG bit-identity regression
  - Prove V1 gate + `test_v2_scientific_invariants` under V3 flags off; kinship-off leaves AE/AF/AG hashes unchanged; unowned V3 flags still `capability_unimplemented`; v27 round-trip.
  - LOGGING: follow existing regression helpers.
  - Files: extend `tests/unit/test_v3_*` compat/flag tests
  - Depends on: Task 12

- [ ] Task 14: Documentation checkpoint (`/aif-docs`)
  - Update `docs/architecture.md` V3 seams: own `kinship_inheritance`; objective genealogy vs subjective social; perception modes; death persistence; write-pair v11/v8; research/query scaffolding for later UI; Experiment AH; Downstream V3 checklist.
  - Update configuration / social-communication / observer docs as needed; brief `.ai-factory/DESCRIPTION.md` / `ARCHITECTURE.md` blurb.
  - Explicit non-goals: biology; cultural inheritance; auto social valence; full UI trees.
  - Do not edit ROADMAP as owned artifact (coordinate via `/aif-roadmap` if milestone text should change).
  - LOGGING: N/A (docs only).
  - Files: `docs/architecture.md`, relevant `docs/*.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`
  - Depends on: Tasks 1–13

## Implementation notes for `/aif-implement`

- Own `kinship_inheritance` for **objective genealogy only**; defer cultural inheritance handoff to a later plan under the same flag.
- Store parent→child edges only; derive sibling/ancestor/descendant.
- Default `perception_mode=none` — research sees the graph; agents do not auto-know it.
- Keep provenance `OriginRef` non-kinship; use dedicated admit/bootstrap edge APIs.
- Related ≠ trust/affection/loyalty/obligation/inheritance/group identity — enforce with architecture tests.
- Prefer analysis + inspection DTOs for later UI; do not build the full Research UI tree in this plan.
- v27 kinship-only profiles must not require `population_lifecycle` / `new_agent_initialization` when `generational_population` is false.
- Commit after each Commit Plan checkpoint when the user asks to commit (do not auto-commit unless requested).
