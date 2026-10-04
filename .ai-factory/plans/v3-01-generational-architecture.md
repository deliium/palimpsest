# Implementation Plan: V3-01 Generational Architecture Evolution Scaffolding

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-04
Improved: 2026-10-04 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete registered milestone under `plan_default_milestone: auto`; this plan establishes V3 compatibility scaffolding and does not own `multi_hop_testimony_tracking` — register a dedicated M7/V3 milestone via `/aif-roadmap` after this plan lands.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M6 — Remaining V2 Capability Flags
INFO [aif-plan] mode=ultra treated as full (richer plan); remaining args describe the feature
INFO [aif-plan] resolved plan file: .ai-factory/plans/v3-01-generational-architecture.md (format=slug)
INFO [aif-plan] plan name prefix v3- applied per user request; git.create_branches=false so stem is description slug `v3-01-generational-architecture`
INFO [aif-plan] RESEARCH.md absent; research_influenced_plan=false
INFO [aif-improve] applied refinement: locked v23=v22∪v3_capability_flags + allowlist widen incl. budget `{v22,v23}`; sibling wire key; fail-closed at from_config; matrix_schema in Task 4; v2_regression_profile contract; Task 11 keeps scientific invariants + v3_scaffolding_gate; Task 8 ordinal/parallel pins; Task 9 Godot↔Python protocol mirror; Task 11 depends on Task 4; GET /version V3 fields non-goal

## Compatibility contract

This plan is a **compatibility-foundation** plan (V2 → V3 architecture evolution). It must preserve completed V1/V2 executability while reserving seams for later generational-civilization plans. It must **not** implement demographic, kinship, institutional, migration, or language-evolution behavior.

1. V1/V2 invariants intact. `WorldEngine` remains the only objective mutation authority. Agents never directly mutate objective reality. Agents receive immutable per-agent `Observation` / `Perspective` only — never `WorldState`, private `world._*`, another agent's observation, or an all-agent batch as cognition input. `WorldEvent` records remain immutable and append-only. Subjective state stays outside the objective fold. Godot remains a read-only observer. Presentation coordinates remain non-semantic. Deterministic replay/forking continues to work. Agent-private cognition remains inaccessible to other agents. Emergent structures must not become scripted outcomes.
2. V2 surfaces stay green. `V2CapabilityFlags` remain as shipped (owned flags may enable; `multi_hop_testimony_tracking` still fails closed). Runner ladder `runner-config-v1`…`v22` (plus accepted `v23` when V3 flags require it), event schemas 2–8, persistence codecs `v1`–`v5`, observer `observer-protocol-v1`, HTTP `/v1`, WS `palimpsest.v1`, Alembic head `0017`, Research UI `/research/`, and the V2 benchmark / scientific-invariant gates remain executable.
3. Capability flags stay opt-in and default-off. This plan introduces reserved `V3CapabilityFlags` only. Enabling any V3 flag before an owning later plan fails closed at **`SimulationRunner.from_config` / runner construction** with `capability_unimplemented`. Do **not** own or implement `multi_hop_testimony_tracking` here.
4. V1 regression gate stays green under flags-off and tracing-off. Catalog A–E and the reference scenario keep current trajectory identity. New V3 scaffolding tests stay **off** `tests/unit/test_v1_regression_gate.py`.
5. V2 regression stays green under V3 scaffolding with V3 flags off. Keep `tests/unit/test_v2_scientific_invariants.py` as the V2 gate; add `v2_regression_profile()` + `tests/unit/test_v3_scaffolding_gate.py`. Do not create a parallel `test_v2_regression_gate.py`. Do not dump V3 cases into the V1 gate or claim V2 benchmark suite ownership.
6. Schema bumps use accepted-set + exact key-set discipline. Never drop accepted V1/V2 versions in the same change that adds a write version. No silent extra fields on an existing runner schema id.
7. No scripted emergence. Forbidden: boolean `civilization_emerged` / `institution_formed` / `kinship_must_form` / `culture_emerged` fields or assertions. Reserved seams describe mechanisms later plans may own — not mandated outcomes.
8. No LLM → world shortcuts. Prefer deterministic fakes; recorded LLM paths remain composition-only.
9. Optional tracing, Research UI chrome, matrix metrics, and observer presentation stay outside the objective fold / `EvidenceManifest`.

## Goal

Establish the architectural substrate for Palimpsest **V3 generational civilization simulation** as an **additive evolution of completed V2**, without implementing population change, lifetimes, kinship, institutions, migration, language evolution, or other generational behavior in this plan.

This plan freezes V1/V2 invariants, extends the versioning and compatibility contracts, introduces explicit **V3 capability flags** (opt-in, fail closed, not mandatory cognition), defines module/schema/Observer/Research-UI extension strategies, and delivers migration + acceptance tests proving existing V1/V2 simulations, replay, Observer Protocol, Godot visualization, and research tooling remain executable under the V3-ready codebase.

Later V3 feature plans must fit into the seams defined here; they must not re-open WorldEngine authority, Observation trust boundaries, replay identity, or Godot write authority.

## Design Decisions

### Invariant freeze (non-negotiable)

1. `WorldEngine` remains the only authority over objective physical reality.
2. Agents receive immutable agent-specific `Observation` only — never `WorldState`, private `world._*`, another agent's observation, or an all-agent batch as cognition input.
3. `WorldEvent` records remain immutable; authoritative history stays append-only (`AUTHORITATIVE_TABLES` + reject-mutation triggers).
4. Memory, beliefs, predictions, reconstructions, relationships, and owner-scoped cultural ledgers remain subjective and may be wrong; they never enter objective replay folding.
5. LLM output is shape-validated and non-authoritative; it never directly mutates objective world state and never becomes `ActionSubmission` without cognition translation + normal admission.
6. Information moves only through perception, communication (Talk/Ask/Tell delivery events), or physical external artifacts — never silent cross-agent memory/belief/ledger copy.
7. Runs remain reproducible where claimed (explicit seeds, deterministic streams, recorded or stubbed LLM paths).
8. Existing V1 and V2 experiments, deterministic replay, research forks, Observer Protocol clients, Godot presentation, and Research UI inspection remain executable.
9. Emergent phenomena must not be converted into hard-coded scripted behavior (no friend/enemy/leader/culture/institution/kinship role scripts; no mandated “civilization emerged” outcomes).
10. Godot remains a read-only observer; presentation coordinates remain non-semantic and must not affect simulation outcomes.
11. Agent-private cognition remains inaccessible to other agents.

### Compatibility strategy

- **Additive by default.** Prefer new accepted schema versions and capability flags over breaking V1/V2 codecs.
- **Accepted-set discipline.** Follow `simulation.persistence` / `simulation.compatibility`: write version vs `ACCEPTED_*` restore/decode sets. Never drop accepted V1/V2 versions in this plan.
- **Strict runner JSON key sets.** `runner_serialization._require_keys` rejects missing and extra fields. New runner fields require a **versioned key set**, not silent additive keys on an existing schema id.
- **Current V2 write surface (baseline to preserve for decode/restore — inspect and pin in Task 2):**
  - Event schema write: `EVENT_SCHEMA_REPLAY_V5` (5); accepted: 2–8 (v6/v7/v8 written only when production / dynamics / artifacts channels require them)
  - Persistence codec: `"v2"` write; accepted: `"v1"`…`"v5"`
  - Projector: `"v2"`; accepted: `"v1"`, `"v2"`
  - Runner config default write: `runner-config-v4`; accepted: `runner-config-v1`…`v22` with mode-driven higher writes (v5–v22); this plan adds accepted `runner-config-v23`
  - Result: `runner-result-v2`
  - Experiment definition: `experiment-definition-v1`
  - Subjective codec: `subjective-v1`
  - Stream records / API envelope: `stream-record-v1` / `stream-envelope-v1`
  - Cognition policy: `cognition-policy-v1`
  - Finalization: `finalization-command-v1` (legacy `pending-finalization-v1` still recognized)
  - Evidence manifest: `evidence-manifest-v1`; metric document schema `"1"` / catalog `metric-catalog-v1`
  - HTTP API: `/v1/simulations/*` + `/health`; WS subprotocol `palimpsest.v1`
  - Observer protocol: `observer-protocol-v1` (layout `observer-layout-v1`) — not currently a `COMPATIBILITY_MATRIX` row; keep identity unless wire break forces dual-accept
  - Alembic head: **`0017`** (no `0018` in this plan)
- **Default execution profile remains V2-equivalent for behavior** when all `V3CapabilityFlags` are off (and existing V2 flags/modes unchanged). `config_fingerprint` may change only if a chosen encode path intentionally writes a new schema; `exact_trajectory_hash`, commit chains, and objective state hashes must not change for V1 regression scenarios and for V2 equivalents covered by `tests/unit/test_v2_scientific_invariants.py`.
- **No mixed event-schema versions within a single run.** Cross-run restore continues via accepted version sets.
- **API:** Keep `/v1` stable. Introduce `/v2` only when a response/request shape cannot be expressed as optional additive fields on `/v1`. Do not add `/v2` routes in this plan.
- **Do not bump default event schema write away from replay-v5 in this plan.** Reserve bump policy only.
- **Database:** **No Alembic migration.** V3 capability flags live only in canonical runner JSON inside existing `run_control` `config_payload`. A later plan may add `0018+` only if indexed SQL columns are proven necessary for inspection.

### Run configuration versioning (locked)

Unlike early V2 scaffolding (which made `runner-config-v3` the universal write default), the runner ladder is now **mode-driven** with default write `runner-config-v4`. Builders set `schema_version` explicitly; `encode_runner_config` writes `config.schema_version` as-is (no silent encode-time bump).

**Locked decision for this plan:**

1. Introduce frozen `V3CapabilityFlags` on run-level `SimulationRunnerConfig` (parallel to `V2CapabilityFlags`, not a replacement).
2. Introduce `RUNNER_SCHEMA_VERSION_V23 = "runner-config-v23"` as an **accepted** schema whose exact key set is the **full `runner-config-v22` superset** (root + agent cognition keys) **plus** the sibling root object `v3_capability_flags` with an exact child key set of the five reserved flag names. Do **not** define v23 as “v4 + flags.”
3. **Default write remains `runner-config-v4`** when all V3 flags are off and no existing mode/spec requires a higher schema (preserves V1 gate catalog A–E byte path and avoids churning the entire V2 surface).
4. When any `V3CapabilityFlags` value is true, `schema_version` **must** be `runner-config-v23` (reject in `SimulationRunnerConfig.__post_init__` with a stable reason such as `v3_capability_requires_v23`, mirroring `capability_requires_v3`). Builders/`replace` set the version before encode; encode must not auto-bump.
5. Widen every mode allowlist that currently tops out at `v22` to accept `v23`, and change the budget equality (`cognitive_budget_mode` requires exact `v22`) to accept `{v22, v23}`. Mode-required keys remain mandatory on v23 when those modes are on; v23 without budgets is legal when only V3 flags force v23.
6. Decode of `runner-config-v1`…`v22` synthesizes default-off `V3CapabilityFlags`. Decode of `v23` requires the exact `v3_capability_flags` object (all-off is legal for round-trip tests even if writers only emit v23 when some flag is true).
7. Wire shape is a **sibling root key** `v3_capability_flags` (parallel to V2 `capability_flags`). Never mutate or overload the V2 `capability_flags` exact child key set.
8. Also widen `experiments/matrix_schema.py` finalize/allowlist to accept `v23` while keeping default finalize at `v4` when all V3 flags are off.

### Capability flags (explicit, not mandatory cognition)

Introduce a frozen, closed `V3CapabilityFlags` on **run-level** `SimulationRunnerConfig`, encoded under root key `v3_capability_flags` on `runner-config-v23` documents, included in fingerprints/diagnostics when present on the encoded document:

| Flag (reserved closed identifiers) | Default | Slot purpose (later plans only) |
| --- | --- | --- |
| `generational_population` | off | Population change, finite lifetimes, births/new agents, developmental stages |
| `kinship_inheritance` | off | Kinship, intergenerational learning, cultural inheritance, knowledge preservation/loss pathways |
| `multi_polity_migration` | off | Migration, multiple settlements/societies |
| `institutional_economy` | off | Deeper economic interaction, collective projects, institutional emergence/succession |
| `cultural_historical_memory` | off | Historical memory, innovation, language evolution, long-horizon historical experiments |

Rules:

- Flags are **configuration identifiers only** in this plan. With all V3 flags off, stage order, policies, and objective outputs match the pre-V3-scaffolding baseline for the same seed/scenario (modulo intentional non-behavioral metadata).
- **Do not wire new policies** when a V3 flag is on — enabling a flag before a later plan owns it must fail closed at **`SimulationRunner.from_config` / runner construction** with stable reason code `capability_unimplemented` (same stage pattern as V2 unimplemented flags). `SimulationRunnerConfig` construction and encode/decode of flag-true v23 documents remain allowed so golden/round-trip tests can assert fail-closed create without implying runnable behavior.
- Reserved names must not imply implemented behavior; later V3 plans own semantics and may refine sub-capabilities without renaming these slots unless a versioned bump is justified.
- Do **not** add one flag per bullet in the product vision; coarse architectural slots keep the closed set stable. Feature-level modes (if needed later) follow the existing V2 pattern: cognition/world modes on versioned runner schemas, not new top-level packages of boolean soup.
- `V2CapabilityFlags` remain unchanged; this plan does not own `multi_hop_testimony_tracking`.
- Cognition loop stage protocols stay constructor-injected; no hidden callbacks, LangGraph, or discovery plugins.
- Analysis may later consume flag metadata; flags must never inject analysis results into live cognition.

### Domain-contract evolution (agent-facing)

- Observation, closed `AgentCommand` set (currently 24), and `world.communications` evolve under accepted-set discipline: new write versions only when wire shape changes; legacy decode remains; cognition inputs must not silently widen to authority types.
- This plan implements **no** new Observation fields, commands, communication variants, birth events, kinship facts, settlement entities, or institution world rules.
- Live/restored observation parity (`tests/unit/test_checkpoint_restoration.py` and siblings) remains the hard gate for any future domain bump.
- Document that future birth/roster/kinship-visible facts are domain bumps gated by parity + event/codec/admission co-landing — not silent Observation widenings.

### Module evolution stance (seams only)

Keep the Structured Modules layout and import-linter contracts. Do **not** create new top-level packages in this plan unless a seam cannot live under existing packages (prefer documenting future homes).

| Future concern | Existing hook today | Fixed assumption to reserve against | Scaffolding action in this plan |
| --- | --- | --- | --- |
| Population change / new agents | Bootstrap `AgentRegistration` + fixed `SimulationRunner`/`WorldEngine` roster | Registration frozen for the run; no mid-run spawn/unbind | Document reserved dynamic-roster seam; no API yet |
| Finite lifetimes / developmental stages | Physiology, `Died`, `LifeStatus`, `MortalityMode`, runtime `TERMINAL` | One-way death; no age/birth lifecycle | Reserve under `generational_population`; no behavior |
| Kinship | — | No parent/child model | Reserve under `kinship_inheritance`; no types yet |
| Intergenerational learning / cultural inheritance | Owner-scoped ledgers (narrative/naming/convention/norm/group/territorial) + teaching modes | Ledgers die with owner; no handoff path | Document inheritance/handoff seam as subjective-only unless a later plan proves otherwise |
| Historical memory / knowledge loss / innovation | Memory/belief/narrative ledgers + analysis metrics | No society-wide memory authority | Reserve under `cultural_historical_memory` |
| Migration / multi-settlement | Location graph + Move + capacities + structures | Topology bootstrap-fixed; no settlement entity | Reserve under `multi_polity_migration`; no new nodes |
| Economy / collective projects / institutions | Structures, production, group/norm/convention ledgers | Beliefs ≠ world authority; no institution engine | Reserve under `institutional_economy`; forbid scripted institution outcomes |
| Language evolution | Semantic naming + narratives (owner-scoped) | No world dictionary / NL authority | Reserve under `cultural_historical_memory` |
| Long-horizon experiments | Scale infra, matrix runner, branching, checkpoints | Already research-capable | Document experiment/matrix extension seam only |

**Runtime ordinal / parallelism pins (document in Task 8):**

- No mid-run roster/spawn/unbind in this plan.
- Per-tick agent ordinal = bootstrap registration order.
- `prepare_parallel` remains `False` until a later owned plan changes it (`simulation.runner` today hardcodes false).
- New generational cognition must plug in as constructor-injected stage slots / modes — not by renumbering fixed `CognitiveLoop` ordinals.
- No scripted civilization/institution/kinship helpers.

Allowed scaffolding in this plan:

- Version/capability contracts in `simulation.runner_models` (+ serialization with versioned `_require_keys` sets)
- Compatibility matrix / policy modules under `simulation` (framework-free), including observer/research protocol rows if mirrors are needed
- `experiments/matrix_schema.py` allowlist widen for `v23` (default finalize stays `v4` when V3 flags off)
- Docs + architecture gap tests asserting V1/V2 invariants and V3 flag defaults
- Experiment helpers (`v3_scaffolding_profile`, new `v2_regression_profile`) without experiment schema bump

Forbidden in this plan: implementing births, ages, kinship graphs, settlement creation, institutional engines, migration policies, language mutation, economic markets, collective-project resolution, or scripted “emergent” civilization outcomes.

### Event versioning strategy

- Keep default event write at replay-v5.
- Keep accepted set `{2…8}`; do not drop legacy decode.
- Document bump triggers for later V3 plans: new objective occurrence kinds (e.g. birth-class events) require a new `EVENT_SCHEMA_REPLAY_V*` member, codec/projector updates, replay fixtures, and Observer semantic-type entries landed together.
- Godot birth timeline category stays empty until a birth-class semantic type exists (do not invent births from roster).

### Snapshot compatibility strategy

- `ReplayService` continues to validate `ACCEPTED_*` sets; keep V1/V2 fixtures green.
- Subjective tables remain outside authoritative replay.
- Research forks (`0015` / `ResearchIntervention`) remain control-plane only; no new capability flag and no parent-history rewrite.
- Prefer no persistence codec write bump in this plan; if checkpoint shape must mention V3 flag digests, put digests in runner/diagnostics fingerprints rather than objective snapshot payloads.

### Observer Protocol extension strategy

- **Keep `observer-protocol-v1`.** Prefer additive optional fields, additive semantic event types, and presentation-only chrome.
- Rename/bump protocol id only if wire identity cannot remain backward compatible; then dual-accept like other schemas (out of scope to rename in this plan).
- Document reserved future semantic categories (birth/roster/settlement/institution overlays) as **presentation mappings over committed facts**, never simulation authority.
- Godot remains read-only: HTTP GET + observer WebSocket only; no import from `src/` into clients; presentation coordinates non-semantic.
- Add `observer-protocol` / layout rows to `simulation.compatibility` (or a documented adjacent registry) so V3 plans do not invent a second source of truth.
- Add a **Godot↔Python mirror pin**: `clients/godot-observer/scripts/protocol/models.gd` `PROTOCOL_VERSION` / layout const must equal `OBSERVER_PROTOCOL_VERSION` / `OBSERVER_LAYOUT_SCHEMA_VERSION` (extend compatibility or architecture mirror tests; do not invent a second protocol id).
- **Non-goal:** no V3 fields on `GET /version` / `presentation_static.version_payload` (application/protocol/export/revision/research_ui only).

### Research UI extension strategy

- Keep `/research/` mount and `/v1` data origin.
- Prefer additive inspect views, optional query params, and epistemic chrome classes already used (`agent_belief` vs `research_inference`).
- V3 researcher surfaces (lineage, settlements, institutions, long-horizon compare) are **planned as additive routes/components** consuming existing inspection/matrix/branch APIs first; new HTTP shapes only when optional fields cannot express them.
- Matrix FS schemas (`experiment-matrix-v1`, aggregates, metric summaries) stay v1 unless a later plan needs a versioned bump; this plan does not change them.
- Research UI must not start batches, mutate world state, or treat analytical labels as agent-visible truth.

### Migration strategy

| Layer | This plan | Later V3 plans |
| --- | --- | --- |
| Runner JSON | Decode v1–v22 → default-off V3 flags; `schema_version` must be `v23` when any V3 flag is true (v23 = v22 keyset ∪ `v3_capability_flags`; widen mode allowlists incl. budget `{v22,v23}`); default write stays `v4` when all V3 flags off | Owning plan may promote v23 (or successor) to broader write defaults if justified |
| Events | No write bump; accepted set unchanged | Co-land schema + codec + fixtures for new objective kinds |
| Snapshots / codecs | No objective codec bump | Only when checkpoint bytes must carry new objective structure |
| Alembic | Head stays `0017`; no `0018` | New revision only for proven inspection/index needs |
| API / WS | `/v1` + `palimpsest.v1` stable; no V3 fields on `/version` | `/v2` only if non-additive |
| Observer | Protocol id unchanged; Godot↔Python mirror pin | Additive fields/types; dual-accept if rename ever required |
| Experiments | Stay on `experiment-definition-v1`; flags in runner JSON; matrix finalize allowlists accept v23 | New catalog letters off V1 gate; no scripted emergence |

### Snapshot / replay / experiment compatibility

- Catalog experiments A–E and `experiments.reference_scenario` remain the canonical V1 regression fixtures (`v1_regression_profile`).
- V2 scientific invariants / benchmark suite remain off the V1 gate; V3 scaffolding must not break `tests/unit/test_v2_scientific_invariants.py`.
- Golden `runner-config-v2` / `v4` (and representative higher) fixtures prove legacy decode after V3 scaffolding.
- Add `v3_scaffolding_profile()` asserting all V3 flags off.
- Add **new** `v2_regression_profile()` that: (a) requires `v3_scaffolding_profile` / all V3 flags off; (b) reuses `v1_regression_profile` rules for V2 capability flags + tracing; (c) does **not** require every V2 cognition mode to be `DISABLED` (scientific invariants already compose owned V2 surfaces). Used by Task 11; not a second V1 gate.

## Non-Goals

- Implementing population dynamics, births, finite-age schedules, developmental-stage behavior, kinship graphs, intergenerational teaching/learning policies, cultural inheritance transfer, historical-memory engines, knowledge-loss models, innovation processes, migration policies, multi-settlement world topology mutation, deeper markets, collective-project resolution, institutional engines/succession, or language evolution.
- Hard-coding emergent civilization/institution/kinship outcomes as scripted tick results.
- Dropping legacy replay-v2…v8 decode, runner-config-v1…v22 decode, or persistence codec v1–v5.
- Replacing `/v1` API routes, renaming `observer-protocol-v1`, or changing WS auth to query-string credentials.
- Adding V3 fields to `GET /version` / `presentation_static.version_payload`.
- Adding Alembic `0018` or rewriting authoritative history.
- Owning or implementing `multi_hop_testimony_tracking`.
- Concurrent multi-process simulation as default, Kafka/Celery/microservices.
- Claiming exact replay for unrecorded external LLM calls.
- Updating ROADMAP milestones as an owned artifact of this command (coordinate via `/aif-roadmap` for M7/V3).
- Composing LLM providers into API lifespan (document seam only if touched).

## Commit Plan
- **Commit 1** (after tasks 1–3): `docs(architecture): freeze V3 invariant gaps and versioning charter`
- **Commit 2** (after tasks 4–7): `feat(simulation): add V3CapabilityFlags and runner-config-v23 without Alembic bump`
- **Commit 3** (after tasks 8–11): `test(v3): prove V1/V2 regression, replay, observer, and API under V3 scaffolding`
- **Commit 4** (after task 12): `docs(v3): document seams, migration matrix, and downstream plan contract`

## Tasks

### Phase 1: Charter, Inventory, and Contract Policy

- [x] Task 1: Close gaps in V1/V2 invariant architecture tests for V3 scaffolding (audit, do not duplicate).
  - Deliverable: Inventory existing gates in `tests/architecture/` including at least `test_world_authority`, `test_cognitive_loop_isolation`, `test_llm_provider_isolation`, `test_social_isolation`, `test_experiment_instrumentation_isolation`, `test_analysis_isolation`, `test_godot_client_isolation`, `test_observer_isolation`, `test_cognitive_architecture_boundaries`, import-linter, and V2 scientific invariants. Add **only missing** assertions that protect V3-relevant invariants: fixed-roster/no silent mid-run authority widening today; Godot/presentation non-authority; no scripted civilization/institution/kinship mandate helpers; analysis/experiment → cognition feedback still forbidden. Explicit non-goal: rewriting suites that already cover WorldState/WorldEvent/LLM→command bans.
  - Files: `tests/architecture/` (gap-only edits), `tests/unit/test_v2_scientific_invariants.py` (reference/extend only if a one-line invariant pin is missing), `docs/architecture.md`, `pyproject.toml` (import-linter only if a real contract gap is found).
  - Logging: Test helpers remain log-free. Any new diagnostic helpers log only module paths and rule IDs at DEBUG; never payloads.
  - Dependencies: None.

- [x] Task 2: Produce the V3 version taxonomy and compatibility matrix extension (code + docs).
  - Deliverable: Extend the single source of truth in `simulation.compatibility` so it enumerates V2 pins accurately (refresh stale module header that still mentions Alembic `0012` / runner write v3 — hard acceptance, not optional) and adds V3 scaffolding rows: planned `runner-config-v23`, `V3CapabilityFlags` ownership policy, observer-protocol/layout identity, Research UI mount stability, Alembic head `0017`, default event write still 5. Also correct stale contributor docs that still claim current runner write is `runner-config-v3` (e.g. `docs/research-api.md` if present). Columns remain: current write version, accepted restore set, bump trigger, owner package, V1/V2 fixture impact. Record locked decisions: default runner write stays `runner-config-v4` when all V3 flags are off; `v23` = v22 keyset ∪ `v3_capability_flags`; event schema stays at v5 writes; Alembic head stays `0017`.
  - Files: `src/simulation/compatibility.py`, `src/simulation/__init__.py`, `docs/persistence.md`, `docs/architecture.md`, `docs/research-api.md` (stale write-version note), `tests/unit/test_compatibility_matrix.py`, `tests/unit/test_alembic_head_pin.py` (pin remains `0017`).
  - Logging: Module may be log-free. If present, DEBUG on matrix load with version strings/counts only; never seeds or payloads.
  - Dependencies: Task 1 for invariant language consistency.

- [x] Task 3: Define domain-contract evolution rules for V3 (Observation / commands / communications / roster).
  - Deliverable: Written + tested policy for how agent-facing domain contracts may evolve in later V3 plans: accepted-set discipline for Observation and related codecs; closed `AgentCommand` set remains closed unless a versioned bump + admission/world-operation updates land together; communications stay event-only with testimony distrust; cognition must never gain `WorldState`/`WorldEvent` store access; mid-run roster/birth/kinship-visible facts require explicit versioned seams and live/restored observation parity. This plan implements **no** new fields/commands — only the rules and regressions that parity helpers remain the required gate for future bumps.
  - Files: `docs/architecture.md`, perception/physical docs as needed, `.ai-factory/ARCHITECTURE.md` (short pointer), `tests/unit/test_domain_contract_evolution_policy.py` (extend), existing observation parity tests (reference only).
  - Logging: Docs/tests primarily; DEBUG only for policy module IDs if code is added.
  - Dependencies: Task 2.
  <!-- Commit checkpoint: tasks 1-3 -->

### Phase 2: V3 Capability Flags, Golden Fixtures, and Persistence Decision

- [x] Task 4: Introduce `V3CapabilityFlags` and `runner-config-v23` encode/decode without changing default write.
  - Deliverable: Add frozen `V3CapabilityFlags` on `SimulationRunnerConfig` (run-level) with the five reserved identifiers and empty owned allowlist. Add `RUNNER_SCHEMA_VERSION_V23` to `SUPPORTED_RUNNER_SCHEMA_VERSIONS`. Implement versioned exact `_require_keys` for v23 where **v23 keyset = full v22 root/cognition keyset ∪ root `v3_capability_flags`** (exact child keys = the five reserved names). Decode v1–v22 → default-off V3 flags. When any V3 flag is true, `__post_init__` requires `schema_version == runner-config-v23` (`v3_capability_requires_v23`); do **not** silent-bump in encode. Widen every mode allowlist ending at v22 to include v23, and change budget equality to accept `{v22, v23}`. Widen `experiments/matrix_schema.py` finalize/allowlist for v23; default finalize stays v4 when all V3 flags are off. Include V3 flags in fingerprints/diagnostics when present on the encoded document (optional sibling digest helper if V2 already has `capability_flags_digest`). Fail-closed: any V3 flag on → `SimulationRunner.from_config` raises `capability_unimplemented`; config+encode of flag-true v23 must still round-trip. V3 flags-off leaves existing wiring unchanged. Do **not** change `COGNITION_POLICY_VERSION`. Do **not** alter `V2CapabilityFlags` ownership or the V2 `capability_flags` child key set.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/runner.py`, `src/simulation/__init__.py`, `src/experiments/matrix_schema.py`, `tests/unit/test_runner_models.py`, `tests/unit/test_runner_serialization.py`, `tests/unit/test_simulation_runner_construction.py`, `tests/unit/test_matrix_schema.py` (or existing matrix schema tests), `tests/typecheck/simulation_runner.py` (if present).
  - Logging: DEBUG construction with run_id/schema_version/flag names/values; INFO when any V3 flag is true (IDs/counts only); WARN on legacy schema decode/upgrade; ERROR stable `unsupported_version` / `v3_capability_requires_v23` / `capability_unimplemented` codes. Never log seeds, goals, observations, or command bodies.
  - Dependencies: Task 2.

- [x] Task 5: Capture golden V1/V2 runner-config payloads and fingerprint/trajectory identity rules under V3 scaffolding.
  - Deliverable: Ensure golden fixtures for representative `runner-config-v2` / `v4` (and at least one higher mode-driven schema if already present) still decode with default-off V3 flags. Add at least one encode/decode golden for `runner-config-v23` with a V3 flag true (create must fail closed; encode/decode must succeed). Document and test: after V3 scaffolding, V1 regression scenarios keep objective trajectory/commit identity; `config_fingerprint` changes only when encode path intentionally differs. Prefer extending `tests/unit/test_v2_golden_runner_configs.py` over new engines.
  - Files: `tests/unit/fixtures/` or `tests/fixtures/runner_configs/`, `tests/unit/test_v2_golden_runner_configs.py` (extend; add `test_v3_golden_runner_configs.py` only if needed), `tests/unit/test_runner_serialization.py`, `docs/simulation-runner.md` (identity rules).
  - Logging: Tests assert hashes/version codes; DEBUG fixture names and schema_version only.
  - Dependencies: Task 4.

- [x] Task 6: Experiment compatibility helpers and V2/V3 profiles.
  - Deliverable: Keep `experiment-definition-v1`. Catalog A–E and reference scenario stay on default-off V2/V3 flags (builders continue emitting their current schemas; decode upgrades synthesize V3 defaults). Add `v3_scaffolding_profile()` asserting all V3 flags off. Add **new** `v2_regression_profile()` that composes: all V3 flags off + existing `v1_regression_profile` rules (V2 capability flags off + tracing off); do **not** mandate every V2 cognition mode `DISABLED`. Export both helpers from `experiments`. Do not add V3 catalog experiments in this plan.
  - Files: `src/experiments/catalog.py`, `src/experiments/reference_scenario.py`, `src/experiments/__init__.py`, `tests/unit/test_experiment_definitions.py`, `tests/unit/test_v2_flag_defaults.py` (extend), `tests/unit/test_v3_flag_defaults.py` (new if needed).
  - Logging: DEBUG experiment_id/condition_id/schema_version/flag digest prefixes; never log full runner JSON or seeds in INFO+.
  - Dependencies: Task 4.

- [x] Task 7: Record the no-Alembic-migration decision and head pin at `0017`.
  - Deliverable: Document that V3 capability flags are carried only in runner JSON (`run_control.config_payload`); Alembic head remains `0017`. Extend `tests/unit/test_alembic_head_pin.py` (already forbids capability-flag table names) and/or compatibility pins so no `0018_*.py` is introduced by this plan and authoritative table semantics are unchanged. Explicitly forbid inventing indexed V3 flag columns without a later justified plan.
  - Files: `docs/persistence.md`, `tests/unit/test_alembic_head_pin.py`, `tests/unit/test_compatibility_matrix.py` (cross-link only if needed), `.ai-factory/ARCHITECTURE.md` (migration head note).
  - Logging: N/A beyond existing Alembic conventions if touched (should not be).
  - Dependencies: Task 4.
  <!-- Commit checkpoint: tasks 4-7 -->

### Phase 3: Module Seams, Observer/Research UI, Replay, API, and Regression Gates

- [ ] Task 8: Document V3 module evolution seams without implementing behavior.
  - Deliverable: Map plug-in points for later V3 plans: dynamic roster / birth registration (future), lifetime/developmental stage hooks beside physiology/`Died`/`TERMINAL`, kinship/inheritance beside owner-scoped ledgers + teaching, multi-settlement/migration beside location graph + Move, institutional/economy beside group/norm/convention/production, cultural-historical memory beside narrative/naming/memory analysis, long-horizon matrix/branch/scale tooling, run-level `V3CapabilityFlags`, and **API/`llm.factory` LLM lifecycle composition** (not a runner flag). Explicitly pin: no mid-run roster; per-tick ordinal = registration order; `prepare_parallel=False` until owned; new cognition = slots/modes not renumbered loop ordinals; no scripted civilization helpers. State off-limits seams (WorldEngine admission, event immutability, Observation trust, Godot write authority, scripted emergence). Capture “default-off V3 flags → V2-equivalent wiring; flags-on fail closed at from_config until a later plan owns them.”
  - Files: `.ai-factory/ARCHITECTURE.md`, `docs/architecture.md`, `docs/cognition-runtime.md` (pointer), `.ai-factory/DESCRIPTION.md` (V3 scaffolding note only).
  - Logging: Docs-only; N/A.
  - Dependencies: Tasks 2, 4.

- [ ] Task 9: Observer Protocol and Research UI extension strategy (docs + minimal pins).
  - Deliverable: Publish the locked strategies: keep `observer-protocol-v1` / `observer-layout-v1`; additive optional fields and semantic types only; birth/settlement/institution overlays reserved as presentation mappings; Godot read-only + non-semantic coordinates; Research UI additive inspect/chrome only under `/research/` + `/v1`; no protocol rename and no `/v2` HTTP in this plan. Add compatibility-matrix/registry pins. Add a **Godot↔Python mirror assertion** that `clients/godot-observer/scripts/protocol/models.gd` `PROTOCOL_VERSION` / layout const equals `OBSERVER_PROTOCOL_VERSION` / `OBSERVER_LAYOUT_SCHEMA_VERSION` (extend `test_compatibility_matrix.py` cross-package mirrors or a focused unit test). Explicit non-goal: no V3 fields on `GET /version`. Do not build new Godot features.
  - Files: `src/observer/version.py` (comments/exports only if needed), `src/simulation/compatibility.py`, `docs/research-api.md`, `docs/research-ui.md`, `clients/godot-observer/scripts/protocol/models.gd` (read-only pin target), `tests/unit/test_compatibility_matrix.py` and/or `tests/unit/test_godot_protocol_mirror.py`.
  - Logging: Existing API WARN on protocol mismatch only; never frame payloads.
  - Dependencies: Tasks 2, 8.

- [ ] Task 10: Snapshot/replay and `/v1` API compatibility acceptance suite.
  - Deliverable: Focused proofs: (a) V1/V2 event fixtures at accepted schemas still restore; (b) V3 flags-off equivalent runs preserve objective trajectory/commit identity for V1 regression scenarios; (c) subjective table divergence does not change objective fold; (d) create/configure accept legacy runner payloads; runner start/decode accepts upgrade to default-off V3 flags; (e) research branch lineage and observer protocol identity remain unchanged. Extend existing replay/API suites; add `tests/unit/test_v3_v2_replay_compat.py` only if needed.
  - Files: `tests/unit/test_replay_service.py`, `tests/unit/test_simulation_replay_determinism.py`, `tests/integration/test_simulation_persistence_replay.py`, `tests/unit/test_api_simulation_manager.py`, `tests/integration/test_v1_api_e2e.py`, `docs/research-api.md`.
  - Logging: Tests assert on hashes/version codes; runner DEBUG may emit run_id/tick/version; never event payloads or `config_payload`.
  - Dependencies: Tasks 4, 5.

- [ ] Task 11: End-to-end V1 + V2 regression gates under V3 scaffolding.
  - Deliverable: (1) Keep `tests/unit/test_v1_regression_gate.py` green (catalog A–E + reference; flags-off; tracing-off; V3 flags off). (2) Keep `tests/unit/test_v2_scientific_invariants.py` as the V2 gate; add only a short V3-off pin there if needed (do **not** create `test_v2_regression_gate.py`). (3) Add `tests/unit/test_v3_scaffolding_gate.py` (network-free) asserting `v3_scaffolding_profile()`, `v2_regression_profile()` on a base config, and that enabling any V3 flag fails closed at `from_config` while encode/decode of that config succeeds. Hard rule: do not append V3 demographic/institutional cases into the V1 gate; do not import the full 16-scenario benchmark suite into the default unit path.
  - Files: `tests/unit/test_v1_regression_gate.py` (untouched except fixes if scaffolding breaks it), `tests/unit/test_v2_scientific_invariants.py` (optional one-line V3-off pin), `tests/unit/test_v3_scaffolding_gate.py` (new), `src/experiments/catalog.py`.
  - Logging: INFO gate start/end with experiment_id/tick counts/flag digests; DEBUG per-condition fingerprints; ERROR stable failure codes; never observations/memories.
  - Dependencies: Tasks 4, 5, 6, 9, 10.
  <!-- Commit checkpoint: tasks 8-11 -->

### Phase 4: Docs Checkpoint and Downstream Plan Contract

- [ ] Task 12: Contributor documentation, migration matrix, and Downstream V3 plan contract.
  - Deliverable: `/aif-docs` checkpoint updating architecture/persistence/simulation-runner/experiments/research-api/research-ui with the V3 compatibility matrix, `V3CapabilityFlags` + sibling `v3_capability_flags` wire + `runner-config-v23` = v22∪flags rule, allowlist widen incl. budget `{v22,v23}`, matrix finalize note, no-`0018` decision, Observer/Research UI extension strategies (incl. Godot mirror + **no V3 fields on `/version`**), domain-contract evolution rules, fingerprint vs trajectory identity, and module seams table (incl. ordinal/parallel pins). Include a concise **Downstream V3 plan contract** checklist every future V3 feature plan must satisfy: V1/V2 invariants intact; V3 flags opt-in and fail closed at from_config until owned; V1 gate + `test_v2_scientific_invariants` green with V3 flags off; schema bumps follow accepted-set + exact key-set discipline; no scripted emergence; no LLM→world shortcuts; Godot read-only / non-semantic coordinates; experiments remain reproducible; optional tracing/analysis outside the objective fold. Add a short “V3 scaffolding” section to DESCRIPTION/ARCHITECTURE. Do not invent ROADMAP milestones; link to `/aif-roadmap` for M7/V3.
  - Files: `docs/architecture.md`, `docs/persistence.md`, `docs/simulation-runner.md`, `docs/experiments.md`, `docs/research-api.md`, `docs/research-ui.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, `README.md` (landing pointers only if needed).
  - Logging: N/A (docs).
  - Dependencies: Tasks 2–11.
  <!-- Commit checkpoint: task 12 -->

## Acceptance Criteria

1. Architecture gap audit complete; existing isolation suites remain green; only justified new gates added (Task 1).
2. Compatibility matrix documents V2 pins accurately and V3 scaffolding rows, including conditional `runner-config-v23` and Alembic head `0017` (Tasks 2, 7).
3. Domain-contract evolution rules published; no Observation/command/communications/roster wire changes in this plan (Task 3).
4. With all V3 capability flags off, catalog experiments A–E and the reference scenario still construct and execute under deterministic fakes; V1 regression gate green (Task 11).
5. `tests/unit/test_v2_scientific_invariants.py` and `v2_regression_profile()` remain green under V3 scaffolding with V3 flags off (Task 11).
6. Golden legacy runner-config fixtures still decode; V3 flags-off objective trajectory/commit identity remains stable for covered scenarios; v23 flag-true encode/decode works while `from_config` fails closed (Tasks 5, 10, 11).
7. `/v1` simulation control/inspection/replay clients using legacy runner payloads remain functional; `observer-protocol-v1` unchanged; Godot↔Python protocol mirror pin green; no V3 fields on `/version` (Tasks 9, 10).
8. No new demographic/institutional/kinship/migration/language behavior; any V3 flag on fails closed at from_config (Task 4).
9. No Alembic `0018`; V3 flags live only in runner JSON (Task 7).
10. Docs checkpoint completed with Downstream V3 plan contract checklist (Task 12).

## Notes for `/aif-implement`

- Prefer smallest diffs that establish contracts and tests.
- When adding serialized fields, update exact `_require_keys` sets and round-trip tests in the same change.
- Do not “use” V3 capability flags to sneak in generational behavior.
- Keep default runner write at `runner-config-v4` unless a V3 flag is true (then `schema_version` must be `v23` = v22∪`v3_capability_flags`; widen mode allowlists including budget `{v22,v23}`).
- Fail-closed means `SimulationRunner.from_config`, not config dataclass construction.
- After merge, run `/aif-roadmap` to add **M7 — V3 Generational Architecture Scaffolding** (or equivalent) and relink this plan away from the interim M6 auto-link if desired.
- Subsequent V3 plans should reference this file’s extension seams and Acceptance Criteria, and must keep filename / bundle stems prefixed with `v3-`.
