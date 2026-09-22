# Implementation Plan: V2 Architectural Evolution Scaffolding

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-09-22
Improved: 2026-09-22 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "none"
Rationale: Skipped — ROADMAP.md has no incomplete milestone after V1 (M1–M4 complete); register an M5/V2 milestone via `/aif-roadmap` after this plan lands.

## Goal

Establish the architectural substrate for Palimpsest V2 as an **additive evolution of completed V1**, without implementing new social or cognitive behavior in this plan.

This plan freezes V1 invariants, defines versioning and compatibility contracts, introduces explicit **V2 capability flags** (opt-in, not mandatory cognition), and delivers migration + acceptance tests proving existing V1 simulations, experiments A–E, and deterministic replay remain executable under the V2-ready codebase.

Later V2 feature plans must fit into the seams defined here; they must not re-open WorldEngine authority, Observation trust boundaries, or replay identity.

## Design Decisions

### Invariant freeze (non-negotiable)

1. `WorldEngine` remains the only authority over objective physical reality.
2. Agents receive immutable agent-specific `Observation` only — never `WorldState`, private `world._*`, another agent's observation, or an all-agent batch as cognition input.
3. `WorldEvent` records remain immutable; authoritative history stays append-only (`AUTHORITATIVE_TABLES` + reject-mutation triggers).
4. Memory, beliefs, predictions, reconstructions, and relationships remain subjective and may be wrong; they never enter objective replay folding.
5. LLM output is shape-validated and non-authoritative; it never directly mutates objective world state and never becomes `ActionSubmission` without cognition translation + normal admission.
6. Information moves only through perception, communication (Talk/Ask/Tell delivery events), or physical external artifacts — never silent cross-agent memory/belief copy.
7. Runs remain reproducible where possible (explicit seeds, deterministic streams, recorded or stubbed LLM paths).
8. Existing V1 experiments and deterministic replay must continue working.
9. Emergent phenomena must not be converted into hard-coded scripted behavior (no friend/enemy/leader/culture roles; no scripted “emergence” outcomes).

### Compatibility strategy

- **Additive by default.** Prefer new accepted schema versions and capability flags over breaking V1 codecs.
- **Accepted-set discipline.** Follow the existing pattern in `simulation.persistence`: write version vs `ACCEPTED_*` restore/decode sets. Never drop accepted V1 versions in this plan.
- **Strict runner JSON key sets.** `runner_serialization._require_keys` rejects both missing and extra fields (`invalid_fields`). New runner fields therefore require a **versioned key set** (same pattern as `runner-config-v1` → `v2` agent `name`/`initial_goals`), not silent additive keys on `runner-config-v2`.
- **Current V1 write surface (baseline to preserve for decode/restore):**
  - Event schema write: `EVENT_SCHEMA_REPLAY_V5` (5); accepted: 2–5
  - Persistence codec: `"v2"`; accepted: `"v1"`, `"v2"`
  - Projector: `"v2"`; accepted: `"v1"`, `"v2"`
  - Runner config write today: `runner-config-v2` (legacy decode `v1`); **this plan introduces `runner-config-v3` for capability flags** while keeping v1/v2 decode + default-off upgrade
  - Result: `runner-result-v2` (bump only if flag digests must appear in results; prefer leaving v2 and putting flag digest in diagnostics/fingerprints)
  - Experiment definition: `experiment-definition-v1`
  - Subjective codec: `subjective-v1`
  - Stream records: `stream-record-v1` / API envelope `stream-envelope-v1`
  - Cognition policy: `cognition-policy-v1`
  - Finalization: `finalization-command-v1` (legacy `pending-finalization-v1` still recognized)
  - Evidence manifest: `evidence-manifest-v1`; metric document schema `"1"` / catalog `metric-catalog-v1`
  - HTTP API: `/v1/simulations/*` + `/health`; WS subprotocol `palimpsest.v1`
  - Alembic head: **`0012` (no `0013` in this plan)**
- **Default execution profile remains V1-equivalent for behavior.** With all flags off, stage wiring and objective trajectories match V1 for the same seed/scenario. `config_fingerprint` **may** change under `runner-config-v3` (new canonical bytes); `exact_trajectory_hash`, commit chains, and objective state hashes must not.
- **No mixed event-schema versions within a single run.** Cross-run restore continues via accepted version sets.
- **API:** Keep `/v1` stable. Introduce `/v2` only when a response/request shape cannot be expressed as optional additive fields on `/v1`. Do not add `/v2` routes in this plan. Capability credentials (`ApiCapability`) remain research gates, not product auth. Note: `SimulationManager` stores opaque config bytes + fingerprint; decode happens on runner construction — both paths must accept legacy v2 payloads.
- **Do not bump event schema to v6 in this plan.** Reserve bump policy only.
- **Database:** **No Alembic migration.** Capability flags live only in canonical runner JSON inside existing `run_control` `config_payload` (`0011`). A later plan may add `0013` only if indexed SQL columns are proven necessary for inspection.

### Domain-contract evolution (agent-facing)

- Observation, closed `AgentCommand` set, and `world.communications` evolve under the same accepted-set discipline as events: new write versions only when wire shape changes; legacy decode remains; cognition inputs must not silently widen to authority types.
- This plan does **not** add Observation fields, commands, or communication variants.
- Live/restored observation parity remains a hard gate for any future domain bump.

### Capability flags (explicit, not mandatory cognition)

Extend the existing closed-mode pattern (`MemoryMode`, `ImaginationMode`, `MortalityMode`) rather than inventing a plugin system.

Introduce a frozen, closed `V2CapabilityFlags` (or `CapabilityProfile`) on **run-level** `SimulationRunnerConfig` (not only per-agent cognition), encoded in `runner-config-v3`, included in `runner_config_fingerprint` / diagnostics:

| Flag (reserved closed identifiers) | Default | Slot purpose (later plans only) |
| --- | --- | --- |
| `advanced_social_inference` | off | Future social cognition |
| `multi_hop_testimony_tracking` | off | Future transmission cognition/analysis arms |
| `predictive_world_model` | off | Future subjective prediction |
| `extended_self_model` | off | Future self-model elaboration |

Rules:

- Flags are **configuration identifiers only** in this plan. With all flags off, stage order, policies, and objective outputs match V1 for the same seed/scenario (modulo intentional non-behavioral metadata such as schema_version / config fingerprint).
- **Do not wire new policies** when a flag is on — enabling a flag before a later plan owns it must fail closed or no-op identically to off (prefer fail closed at construction with a stable reason code if on).
- Reserved names must not imply implemented behavior; later V2 plans own semantics.
- Cognition loop stage protocols stay constructor-injected; no hidden callbacks, LangGraph, or discovery plugins.
- Analysis may later consume flag metadata; flags must never inject analysis results into live cognition.

### LLM lifecycle composition (not a runner flag)

LLM provider lifespan remains an API/`llm.factory` composition concern (ARCHITECTURE: deferred until a cognition consumer owns it). Document the extension seam in Task 8/12; do **not** put `llm_lifecycle_composed` on runner config fingerprints or experiment arms.

### Module boundary stance

- Keep the Structured Modules layout and import-linter contracts.
- Do **not** create new top-level packages in this plan unless a seam cannot live under `simulation` / `agents.cognition` / `experiments`.
- Allowed scaffolding:
  - Version/capability contracts in `simulation.runner_models` (+ serialization with versioned `_require_keys` sets)
  - Compatibility matrix / policy modules under `simulation` (framework-free)
  - Docs + architecture gap tests asserting V1 invariants and flag defaults
  - Experiment helpers (`v1_regression_profile`) without experiment schema bump
- Forbidden in this plan: implementing new stage policies, social heuristics, predictive models, or scripted “emergent” outcomes.

### Snapshot / replay / experiment compatibility

- `ReplayService` continues to validate `ACCEPTED_*` sets; keep V1 fixtures green.
- Subjective tables (`0005`–`0008`) remain outside authoritative replay.
- Experiments stay on `experiment-definition-v1`; flags ride inside runner config JSON.
- Catalog experiments A–E (`experiment-a-memory` … `experiment-e-false-story`) and `experiments.reference_scenario` remain the canonical V1 regression fixtures.
- Golden `runner-config-v2` byte fixtures prove legacy decode after the v3 write bump.

## Non-Goals

- Implementing new social, cultural, moral, leadership, or multi-agent negotiation behavior.
- Implementing predictive world models, extended self-models, or new CognitiveLoop stages beyond reserved flag identifiers.
- Hard-coding emergent phenomena as scripted tick outcomes or milestone overrides beyond existing V1 trusted override patterns.
- Dropping legacy replay-v2/v3/v4 decode, runner-config-v1/v2 decode, or persistence codec v1.
- Replacing `/v1` API routes or changing WS auth to query-string credentials.
- Adding Alembic `0013` or rewriting authoritative history.
- Concurrent agent cognition, multi-process simulation as default, Kafka/Celery/microservices.
- Claiming exact replay for unrecorded external LLM calls.
- Updating ROADMAP milestones as an owned artifact of this command (coordinate via `/aif-roadmap`).
- Composing LLM providers into API lifespan (document seam only).

## Commit Plan
- **Commit 1** (after tasks 1–3): `docs(architecture): freeze V1 invariant gaps and V2 versioning charter`
- **Commit 2** (after tasks 4–7): `feat(simulation): add runner-config-v3 capability flags without Alembic bump`
- **Commit 3** (after tasks 8–11): `test(v1): prove replay, golden configs, experiments, and API under V2 scaffolding`
- **Commit 4** (after task 12): `docs(v2): document seams, migration matrix, and downstream plan contract`

## Tasks

### Phase 1: Charter, Inventory, and Contract Policy

- [x] Task 1: Close gaps in V1 invariant architecture tests (audit, do not duplicate).
  - Deliverable: Inventory existing gates in `tests/architecture/` (`test_world_authority`, `test_cognitive_loop_isolation`, `test_llm_provider_isolation`, `test_social_isolation`, `test_experiment_instrumentation_isolation`, `test_analysis_isolation`, import-linter). Add **only missing** assertions (examples: strengthen analysis/experiment → cognition feedback prohibition if thin; document physical-external-artifact information channel in architecture prose + a minimal check if enforceable). Explicit non-goal: rewriting suites that already cover WorldState/WorldEvent/LLM→command/friend-enemy-leader bans.
  - Files: `tests/architecture/` (gap-only edits), `tests/architecture/boundary_checker.py` (only if a new rule needs AST support), `docs/architecture.md`, `pyproject.toml` (import-linter only if a real contract gap is found).
  - Logging: Test helpers remain log-free. Any new diagnostic helpers log only module paths and rule IDs at DEBUG; never payloads.
  - Dependencies: None.

- [x] Task 2: Produce the V2 version taxonomy and compatibility matrix (code + docs).
  - Deliverable: Single source of truth enumerating schema/protocol constants (event, projector, persistence codec, derivation, runner config/result including planned v3, cognition policy, subjective, stream/envelope, finalization, experiment, evidence/metric, API path/WS protocol) with columns: current write version, accepted restore set, bump trigger, owner package, V1 fixture impact. Implement as framework-free `simulation.compatibility` (or equivalent) plus contributor docs. Record decisions: event schema stays at v5 writes; Alembic head stays `0012`; runner write becomes v3 in Task 4.
  - Files: `src/simulation/compatibility.py` (or equivalent), `src/simulation/__init__.py`, `src/simulation/persistence.py` (cross-links only), `docs/persistence.md`, `docs/architecture.md`, `tests/unit/test_compatibility_matrix.py`.
  - Logging: Module may be log-free. If present, DEBUG on matrix load with version strings/counts only; never seeds or payloads.
  - Dependencies: Task 1 for invariant language consistency.

- [x] Task 3: Define domain-contract evolution rules (Observation / commands / communications).
  - Deliverable: Written + tested policy for how agent-facing domain contracts may evolve in later V2 plans: accepted-set discipline for Observation and related codecs; closed `AgentCommand` set remains closed unless a versioned bump + admission/world-operation updates land together; communications stay event-only with testimony distrust; cognition must never gain `WorldState`/`WorldEvent` store access. This plan implements **no** new fields/commands — only the rules and a regression that live/restored observation parity helpers remain the required gate for future bumps.
  - Files: `docs/architecture.md`, `docs/physical-simulation.md` or perception docs as needed, `.ai-factory/ARCHITECTURE.md` (short pointer), `tests/unit/test_domain_contract_evolution_policy.py` (or architecture test documenting the policy invariants), existing observation parity tests (reference only).
  - Logging: Docs/tests primarily; DEBUG only for policy module IDs if code is added.
  - Dependencies: Task 2.
  <!-- Commit checkpoint: tasks 1-3 -->

### Phase 2: Capability Flags, Golden Fixtures, and Persistence Decision

- [x] Task 4: Introduce `runner-config-v3` with run-level V2 capability flags.
  - Deliverable: Add frozen `V2CapabilityFlags` / `CapabilityProfile` on `SimulationRunnerConfig` (run-level). Introduce `RUNNER_SCHEMA_VERSION_V3 = "runner-config-v3"` as the new write default; keep `SUPPORTED_RUNNER_SCHEMA_VERSIONS` including v1/v2. Update `_encode_runner_document` / `decode_runner_config` with versioned exact `_require_keys` sets (patch rule: new fields update required sets in the same change). Decode v1/v2 → default-off flags. Encode v3 with all flags present (default false). Include flags in fingerprints/diagnostics. Construction: flags-off wires existing V1 policies only; flags-on without an owning later plan fail closed with a stable reason code (or identical no-op — prefer fail closed). Do **not** change `COGNITION_POLICY_VERSION` unless the policy contract itself changes. Do **not** add `llm_lifecycle_composed` here.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/runner.py`, `src/simulation/__init__.py`, `tests/unit/test_runner_models.py`, `tests/unit/test_runner_serialization.py`, `tests/unit/test_simulation_runner_construction.py`, `tests/typecheck/simulation_runner.py` (if present).
  - Logging: DEBUG construction with run_id/schema_version/flag names/values; INFO when any flag is true (IDs/counts only); WARN on legacy schema decode/upgrade; ERROR stable `unsupported_version` / `capability_unimplemented` codes. Never log seeds, goals, observations, or command bodies.
  - Dependencies: Task 2.

- [x] Task 5: Capture golden V1 runner-config payloads and fingerprint/trajectory identity rules.
  - Deliverable: Golden byte fixtures for representative `runner-config-v2` payloads (at least one catalog condition and the reference scenario config). Assert V2-ready decoders still accept them and upgrade to default-off flags. Document and test: after v3 write bump, `config_fingerprint` may differ from golden v2 bytes, but for flags-off equivalent scenarios `exact_trajectory_hash` / objective commit identity remain stable vs a pre-recorded baseline (short horizon). Prefer extending existing determinism tests over new engines.
  - Files: `tests/unit/fixtures/` (or `tests/fixtures/runner_configs/`), `tests/unit/test_v2_golden_runner_configs.py`, `tests/unit/test_runner_serialization.py`, `docs/simulation-runner.md` (identity rules).
  - Logging: Tests assert hashes/version codes; DEBUG fixture names and schema_version only.
  - Dependencies: Task 4.

- [x] Task 6: Experiment compatibility and V1 regression profile helper.
  - Deliverable: Keep `experiment-definition-v1`. Catalog A–E and reference scenario stay on default-off flags (builders may still emit `runner-config-v3` bytes with all flags false, or continue emitting v2 if decode upgrade is the path — pick one and test both decode and catalog construction). Add `v1_regression_profile()` (name flexible) asserting all capability flags off. Fix catalog module docstring if it still says A–D. Extend existing tests; do not create a non-existent `test_reference_scenario.py`.
  - Files: `src/experiments/models.py`, `src/experiments/catalog.py`, `src/experiments/reference_scenario.py`, `src/experiments/__init__.py`, `tests/unit/test_experiment_definitions.py`, `tests/unit/test_experiment_coordinator.py`, `tests/unit/test_reference_scenario_spec.py`, `tests/unit/test_v2_flag_defaults.py`.
  - Logging: DEBUG experiment_id/condition_id/schema_version/flag digest prefixes; never log full runner JSON or seeds in INFO+.
  - Dependencies: Task 4.

- [x] Task 7: Record the no-Alembic-migration decision and head pin.
  - Deliverable: Document that capability flags are carried only in runner JSON (`run_control.config_payload`); Alembic head remains `0012`. Add a small test or docs assertion that no `0013_*.py` is introduced by this plan and that authoritative table semantics are unchanged. Explicitly forbid inventing indexed flag columns without a later justified plan.
  - Files: `docs/persistence.md`, `tests/unit/test_compatibility_matrix.py` or `tests/unit/test_alembic_head_pin.py`, `.ai-factory/ARCHITECTURE.md` (migration head note).
  - Logging: N/A beyond existing Alembic conventions if touched (should not be).
  - Dependencies: Task 4.
  <!-- Commit checkpoint: tasks 4-7 -->

### Phase 3: Seams, Replay, API, and V1 Executability

- [x] Task 8: Document V2 extension seams without implementing behavior.
  - Deliverable: Map plug-in points for later V2 plans: `CognitiveLoop` stage protocols, `AgentCognitionSpec` modes, run-level `V2CapabilityFlags`, `AgentRuntime` subjective finalization, PerceptionService (observe-only), communication eligibility (world-private), `experiments.catalog` arms, analysis-only evidence stages, and **API/`llm.factory` LLM lifecycle composition** (not a runner flag). State off-limits seams (WorldEngine admission, event immutability, Observation trust). Capture “default-off flags → V1-equivalent wiring; flags-on fail closed until a later plan owns them.”
  - Files: `.ai-factory/ARCHITECTURE.md`, `docs/architecture.md`, `docs/cognition-runtime.md`, `.ai-factory/DESCRIPTION.md` (V2 scaffolding note only).
  - Logging: Docs-only; N/A.
  - Dependencies: Tasks 2, 4.

- [x] Task 9: Snapshot/replay compatibility acceptance suite.
  - Deliverable: Focused replay/restore proofs: (a) V1 event fixtures at schemas 2–5 still restore; (b) flags-off equivalent runs preserve objective trajectory/commit identity (not config fingerprint equality); (c) subjective table divergence does not change objective fold. Extend `test_replay_service`, `test_simulation_replay_determinism`, integration replay suites; add `tests/unit/test_v2_v1_replay_compat.py` if needed. Do **not** duplicate full catalog/reference execution (Task 11).
  - Files: `tests/unit/test_replay_service.py`, `tests/unit/test_simulation_replay_determinism.py`, `tests/integration/test_simulation_persistence_replay.py`, `tests/integration/test_physical_simulation_replay.py`, `tests/unit/test_v2_v1_replay_compat.py`.
  - Logging: Tests assert on hashes/version codes; runner DEBUG may emit run_id/tick/version; never event payloads.
  - Dependencies: Tasks 4, 5.

- [x] Task 10: API versioning policy and `/v1` regression coverage.
  - Deliverable: Document `/v1` stability and “no `/v2` routes in this plan.” Keep `WS_PROTOCOL_VERSION = palimpsest.v1`. Prove create/configure accept legacy `runner-config-v2` payloads (opaque store + fingerprint) and that runner start/decode accepts v2 upgrade and v3 flags-off. Extend `test_api_simulation_manager`, lifecycle, replay routes, and `test_v1_api_e2e` as needed.
  - Files: `docs/research-api.md`, `src/api/schemas.py`, `src/api/simulation_manager.py`, `src/api/security.py` (comments only unless needed), `tests/unit/test_api_simulation_manager.py`, `tests/unit/test_api_replay_routes.py`, `tests/integration/test_v1_api_e2e.py`.
  - Logging: Existing route INFO templates; WARN on unsupported `config_schema_version`; never log `config_payload`.
  - Dependencies: Task 4.

- [x] Task 11: End-to-end V1 experiment executability gate.
  - Deliverable: Acceptance tests that construct and run (short tick counts, deterministic fakes) catalog experiments A–E and the five-agent reference scenario under V2-ready code with all flags off. Assert schema/decode path, stop reasons where applicable, and `v1_regression_profile()`. Mark heavy paths with existing pytest markers; default unit path stays network-free and DB-free. Own execution breadth here (not Task 9).
  - Files: `tests/unit/test_v1_regression_gate.py` (new), `tests/integration/test_experiment_framework.py`, `tests/unit/test_reference_scenario_e2e.py` (extend if appropriate), `src/experiments/catalog.py`, `src/experiments/reference_scenario.py`.
  - Logging: INFO gate start/end with experiment_id, tick counts, flag digest; DEBUG per-condition fingerprints; ERROR stable failure codes; never observations/memories.
  - Dependencies: Tasks 5, 6, 9, 10.
  <!-- Commit checkpoint: tasks 8-11 -->

### Phase 4: Docs Checkpoint and Downstream Plan Contract

- [x] Task 12: Contributor documentation, migration matrix, and downstream plan contract.
  - Deliverable: `/aif-docs` checkpoint updating architecture/persistence/simulation-runner/experiments/research-api with the compatibility matrix, `runner-config-v3` + default-off flags, no-`0013` decision, API versioning policy, domain-contract evolution rules, fingerprint vs trajectory identity, and LLM lifecycle composition seam. Include a concise checklist every future V2 feature plan must satisfy: invariants intact; flags opt-in and fail closed until owned; V1 regression gate green; schema bumps follow accepted-set + exact key-set discipline; no scripted emergence; no LLM→world shortcuts; experiments remain reproducible. Add a short “V2 scaffolding” section to DESCRIPTION. Do not invent ROADMAP milestones; link to `/aif-roadmap` for M5.
  - Files: `docs/architecture.md`, `docs/persistence.md`, `docs/simulation-runner.md`, `docs/experiments.md`, `docs/research-api.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, `README.md` (landing pointers only if needed).
  - Logging: N/A (docs).
  - Dependencies: Tasks 2–11.
  <!-- Commit checkpoint: task 12 -->

## Acceptance Criteria

1. Architecture gap audit complete; existing isolation suites remain green; only justified new gates added (Task 1).
2. Compatibility matrix documents every version constant, including `runner-config-v3` write and `0012` head pin (Tasks 2, 7).
3. Domain-contract evolution rules published; no Observation/command/communications wire changes in this plan (Task 3).
4. With all V2 capability flags off, catalog experiments A–E and the reference scenario still construct and execute under deterministic fakes (Task 11).
5. Golden `runner-config-v2` fixtures still decode; flags-off objective trajectory/commit identity remains stable even if `config_fingerprint` changes (Tasks 5, 9).
6. `/v1` simulation control/inspection/replay clients using legacy runner-config-v2 payloads remain functional (Task 10).
7. No new social/cognitive behavior; flags-on without an owning plan fail closed (or documented identical no-op — prefer fail closed).
8. No Alembic `0013`; flags live only in runner JSON (Task 7).
9. Docs checkpoint completed with downstream plan contract checklist (Task 12).

## Notes for `/aif-implement`

- Prefer smallest diffs that establish contracts and tests.
- When adding serialized fields, update exact `_require_keys` sets and round-trip tests in the same change.
- Do not “use” capability flags to sneak in behavior.
- After merge, run `/aif-roadmap` to add **M5 — V2 Architecture Scaffolding** (or equivalent) and link this plan.
- Subsequent V2 plans should reference this file’s extension seams and Acceptance Criteria.
