# Implementation Plan: V1 Simulation Runner and Experimental Framework

Branch: main (no new branch)
Created: 2026-09-22

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M3 — Cognition and Providers"
Rationale: This plan extends M3's cognition/provider work with runner-owned configuration and lifecycle composition, then uses it to deliver part of M4's open experimental analysis scope; it does not claim the remaining API/Compose provider-lifecycle item is complete.

## Goal

Implement reproducible, configuration-driven simulation execution and a trusted experimental framework that can compare cognitive conditions over the same initial world and stochastic seed. `SimulationRunner` constructs and owns the run lifecycle, schedules each registered `AgentRuntime` in canonical order, advances only the authoritative `WorldEngine`, persists committed ticks and checkpoints, emits structured experimental observations, and returns a versioned machine-readable result with an explicit stop reason.

The supported run configuration must cover:

- seed and comparison/stochastic identity;
- world topology, physical rules, resources, agents, and per-agent initial conditions;
- cognitive architecture, memory mode, imagination mode, mortality mode, and per-agent drive parameters;
- maximum ticks and closed stop/failure policies;
- LLM adapter/model/request settings without storing credentials in experiment artifacts;
- persistence/checkpoint settings and experiment condition/replicate identity.

The reusable experiment catalog must define:

- Experiment A: exact/reference memory versus reconstructive memory;
- Experiment B: future simulation disabled versus enabled;
- Experiment C: mortality disabled versus enabled;
- Experiment D: controlled curiosity, safety, belonging, and status drive profiles;
- Experiment E: inject one controlled false story through normal communication and measure its propagation without exposing the objective truth label to any agent.

## Design Decisions

- Keep `SimulationRunConfig` focused on replay-significant world configuration. Add separate immutable runner, agent, cognition, provider, persistence, and experiment specifications rather than turning the existing objective config into an unbounded settings object.
- Use strict, versioned canonical JSON for run specifications, metadata, observations, and results. Reject unknown fields, duplicate keys, non-finite numbers, unordered inputs, unsupported versions, and invalid cross-references. Do not add a YAML dependency for V1.
- Separate durable `RunId` from a persisted stochastic/comparison identity. Objective RNG and derived world identifiers for paired arms must use the same explicit stochastic identity, seed, world specification, and initial state even though each arm has a unique durable run ID. Cognition condition identity must not perturb world randomness.
- Add `SimulationRunner.from_config(...)` (or an equivalent constructor) that receives immutable configuration plus narrow dependency factories/ports. It may construct `WorldEngine`, per-agent cognition, memory/subjective services, and `AgentRuntime` values, but it must not import environment settings, SQLAlchemy adapters, or API code.
- Schedule cognition sequentially in bootstrap registration order for V1. Submission order is behaviorally significant, so concurrent scheduling is out of scope until its side effects and provider calls can be made reproducible.
- Resolve every committed tick through exactly one authority path: `WorldEngine.resolve_tick()` for in-memory runs or `PersistentSimulationService.resolve_tick()` for durable runs. Never fall back to in-memory mutation after a persistence failure or fenced durable service.
- Introduce a top-level `experiments` package as trusted experiment orchestration and observation code. It may coordinate public `simulation` and read-only `analysis` contracts, but agents, cognition, memory, social policy, and world code must not import it or receive its collectors, truth specifications, objective events, snapshots, or results.
- Treat objective instrumentation as post-action observation, not agent context. Runner receipts may expose safe objective records to injected experiment collectors only after authoritative commit; collectors and analysis outputs never flow back into cognition, memory formation, prompts, or future action selection.
- Make runtime processing staged: cognition prepares a proposed command, trusted runner intervention selects the effective command, runtime binding creates one submission plus an owner-scoped pending subjective batch for that effective command, the pending finalization is durably recorded, the objective tick commits, and only then does the runner finalize subjective updates. A post-objective subjective failure blocks the next tick and remains explicitly recoverable/idempotent across process restart; it must never be hidden as a completed run.
- Represent memory, imagination, and mortality treatments with explicit closed modes and policy versions. "Imagination disabled" must use a non-counterfactual present-state policy rather than silently reusing the existing placeholder future simulator. Mortality disabled must consistently disable all current physical death paths and mortality appraisal while preserving non-lethal metabolism/action behavior.
- Inject Experiment E's story as a normal structured `Tell` command at a configured tick/source/recipient through ordinary world admission and perception. The utterance contains no `is_false` marker; a separate analysis-only truth specification and intervention fingerprint identify the controlled treatment.
- Persist condition specifications, assignments, structured observations, and final results as immutable/versioned experiment records. Narrative reports, free-form conclusions, hidden reasoning, prompt bodies, provider responses, and agent-visible truth labels are out of scope.
- External LLM runs are reproducible only with deterministic fakes or recorded validated outputs. Provider credentials remain environment/composition concerns and never enter canonical experiment specifications, hashes, persistence rows, logs, or result documents.

## Non-Goals

- Adding HTTP simulation-control endpoints, a browser UI, distributed workers, Kafka, Celery, or a generic workflow engine.
- Parallel agent cognition, wall-clock scheduling, real-time simulation, or using completion order as simulation order.
- Feeding objective metrics, drift reports, propagation reports, or experiment labels back into live agents.
- Treating delivered testimony as objective truth or bypassing normal communication eligibility/admission for Experiment E.
- Persisting chain-of-thought, raw prompts, raw model output, credentials, endpoint URLs, narrative reports, or arbitrary exception text.
- Guaranteeing bit-for-bit reproduction of unrecorded external LLM calls.

## Commit Plan
- **Commit 1** (after tasks 1-3): `feat(simulation): define reproducible runner configuration`
- **Commit 2** (after tasks 4-7): `feat(simulation): implement configured simulation runner`
- **Commit 3** (after tasks 8-10): `feat(experiments): add reusable treatments and results`
- **Commit 4** (after tasks 11-13): `feat(experiments): persist and verify reproducible runs`

## Tasks

### Phase 1: Reproducibility and Configuration Contracts

- [x] Task 1: Separate durable run identity from shared stochastic identity.
  - Deliverable: Add an explicit, validated stochastic/comparison identity to replay-significant simulation configuration and propagate it through named RNG streams, deterministic ID derivation, manifests, snapshots, canonical codecs, replay validation, and restoration. A unique `RunId` remains the storage/correlation identity, while equal world configuration, bootstrap, seed, and stochastic identity produce equal objective random streams across different cognitive conditions and durable run IDs.
  - Define compatibility/version behavior for existing derivation-v1/v2 runs; do not silently reinterpret persisted history. Make the new derivation version fail closed when stochastic identity is absent, mismatched, or changed during replay.
  - Prove that cognition/experiment condition fingerprints do not enter objective world RNG scopes, while genuinely different stochastic identities or seeds do. Preserve canonical registration/submission order as another explicit determinant.
  - Files: `src/simulation/models.py`, `src/simulation/randomness.py`, `src/simulation/identifiers.py`, `src/simulation/engine.py`, `src/simulation/persistence.py`, `src/simulation/journal.py`, `src/simulation/replay.py`, `src/simulation/serialization.py`, `src/simulation/__init__.py`, `tests/unit/test_reproducibility_contracts.py`, `tests/unit/test_persistence_serialization.py`, `tests/unit/test_simulation_replay_determinism.py`, `tests/unit/test_checkpoint_restoration.py`.
  - Logging: Keep seed, stochastic identity source material, full configuration, and canonical payloads out of logs. DEBUG may include derivation version, run ID, world ID, and hash prefixes; WARN/ERROR must use stable mismatch/version codes without raw values or exception text.
  - Dependencies: None. This contract is required before paired experiment arms can be valid.

- [x] Task 2: Define immutable, versioned simulation runner configuration and canonical codecs.
  - Deliverable: Add frozen, slotted contracts for `SimulationRunnerConfig`, world/bootstrap specification, resource and agent initial conditions, per-agent cognition/memory/imagination/mortality/drive configuration, maximum ticks, stop/failure/checkpoint policy, and provider-neutral LLM settings. Validate exact agent/registration ownership, stable ordering, complete drive sets, finite bounded values, resource/entity references, positive limits, and mutually compatible modes.
  - Add a strict canonical JSON codec and SHA-256 fingerprints for the full runner specification and separately for scenario/world, cognitive condition, and provider settings. Preserve arbitrary non-negative seeds and stable sequence order; reject credentials, unknown fields, duplicate keys, non-finite values, and unsupported schema/policy versions.
  - Represent LLM adapter kind, model, structured-output mode, temperature, `top_p`, provider seed, maximum output tokens, stop sequences, retry count, per-attempt timeout, total deadline, request/response/header byte limits, correlation-header behavior, and recording policy with explicit defaults and fingerprint inclusion. Reject unsupported provider/request options rather than inheriting hidden provider defaults. Use an injected credential/provider resolver so API keys and base URLs are neither serialized nor fingerprinted. Require deterministic fake/recorded mode when exact reproducibility is requested.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/contracts.py`, `src/simulation/__init__.py`, `src/llm/factory.py` only if a public safe config projection is needed, `tests/unit/test_runner_models.py`, `tests/unit/test_runner_serialization.py`, `tests/typecheck/simulation_runner.py`, `tests/typecheck/invalid/`.
  - Logging: Configuration values and codecs are log-free. Add a metadata-only diagnostic projection containing schema/policy versions, entity/agent counts, mode codes, max ticks, and fingerprint prefixes; never include seed, drive values, initial conditions, provider model/endpoint, story content, credentials, prompts, or serialized documents.
  - Dependencies: Task 1 for stochastic identity and derivation semantics.

- [x] Task 3: Add configurable cognition treatments and factories.
  - Deliverable: Add cognition-owned factories/configuration that assemble the existing fixed `CognitiveLoop` from explicit policies without exposing simulation or experiment types to cognition. Implement exact/reference memory retrieval as a lossless owner-scoped projection of stored traces into the same cognition-consumed episodic channel used by reconstructed memories, with a distinct reference episode type/provenance that does not fabricate reconstruction lineage; preserve the current reconstructive path through `ScopedMemoryRetriever`. Add tests proving both arms consume equivalent source episodes while differing only in reconstruction treatment. Add a non-counterfactual imagination-disabled policy and retain `ImaginationEngine` for enabled future simulation.
  - Add sparse, canonical drive-profile overrides for curiosity, safety, belonging, and status while retaining all required independent drives and owner scoping. Add an explicit mortality-appraisal-disabled policy; pair it later with non-lethal physical rules under the runner's single mortality mode.
  - Make policy IDs/versions part of condition fingerprints and scientific boundary records. Preserve `default_cognitive_loop()` by delegating to the new factory with current production defaults rather than adding compatibility branches throughout cognition.
  - Define a closed cognition episode union (or separate exact-reference episode field) in `RetrievedMemoryContext` and update every consumer to handle exact and reconstructed episodes explicitly. Communication and imagination may consume both through shared read-only episode facts, but reconstruction-only generation/provider/lineage fields remain unavailable on reference episodes.
  - Files: `src/agents/models.py`, `src/agents/cognition/models.py`, `src/agents/cognition/configuration.py`, `src/agents/cognition/memory.py`, `src/agents/cognition/imagination.py`, `src/agents/cognition/communication.py`, `src/agents/cognition/motivation.py`, `src/agents/cognition/defaults.py`, `src/agents/cognition/__init__.py`, `tests/unit/test_cognition_models.py`, `tests/unit/test_cognition_configuration.py`, `tests/unit/test_cognition_strategies.py`, `tests/unit/test_v1_episodic_memory_cognition.py`, `tests/unit/test_imagination_engine.py`, `tests/unit/test_motivation_appraisal.py`.
  - Logging: Policies and factories remain payload-free and deterministic. DEBUG boundary metadata may identify mode, policy/version, owner ID, counts, and status; never log memories, reconstructions, imagined futures, beliefs, drive values, prompts, provider output, or commands. ERROR paths use closed configuration/component codes.
  - Dependencies: Task 2 for the runner-facing mode definitions or a narrow translation contract.

### Phase 2: Runner Construction and Tick Lifecycle

- [x] Task 4: Implement configuration-driven construction of world, agents, cognition, and runtime services.
  - Deliverable: Create `SimulationRunner.from_config(...)` and narrow injected factory/port bundles that build `WorldBootstrap`, `SimulationRunConfig`, `WorldEngine`, agents, owner-scoped memory/subjective services, cognition loops, LLM-backed reconstruction components when configured, and one `AgentRuntime` per registration. Validate that configured agent IDs and body mappings are unique, complete, canonically ordered, and exactly match runtime ownership.
  - Translate mortality disabled into one named, versioned non-lethal `PhysicalRules` variant that covers starvation, dehydration, fatigue, exposure, and combat without disabling unrelated metabolism or actions. Reject future unclassified death paths until the mode mapping is updated and tested.
  - Own provider close/lifecycle through an injected async resource factory. Construction failure must close already-created providers/services in reverse order and must not start runtimes or create a partially visible run.
  - Files: `src/simulation/runner.py`, `src/simulation/runner_models.py`, `src/simulation/contracts.py`, `src/simulation/bootstrap.py`, `src/simulation/agent_runtime.py`, `src/world/models.py`, `src/simulation/__init__.py`, `tests/unit/test_simulation_runner_construction.py`, `tests/unit/test_llm_factory.py`.
  - Logging: DEBUG validated counts, factory stage, policy versions, and resource lifecycle; INFO successful runner construction with run/world IDs and config fingerprint prefixes; WARN optional deterministic fallback selection; ERROR stable construction/cleanup codes. Never log seeds, initial state, agent names, drives, story data, provider model/endpoint, credentials, prompts, or memory content.
  - Dependencies: Tasks 1-3.

- [x] Task 5: Make runtime cognition and subjective updates a two-phase commit boundary.
  - Deliverable: Refactor `CognitiveLoop` and `AgentRuntime` processing into explicit stages. Cognition deliberation runs perception through planning and returns a proposed command plus pre-update scientific artifacts without creating command-dependent memory intents or next `InternalAgentState`. Trusted binding accepts the selected effective command, runs the memory-update/internal-state completion stage against that effective command, constructs at most one submission, and derives a detached, prevalidated pending subjective batch/runtime transition. Finalization applies that pending transition only after successful objective commit. Add abort/retry paths for uncommitted ticks.
  - Explicitly prohibit command-dependent memory hooks or `last_command_kind` state from using a suppressed proposal. Experiment interventions bind before pending state is created, so finalized subjective state always describes the command actually submitted (regardless of later authoritative acceptance/rejection, whose outcome remains observable only on a later tick).
  - Add framework-free durable pending-finalization/outbox contracts and repository ports with deterministic recovery/idempotency keys. Persist the complete runtime transition: subjective batch, invocation and processed-observation identities, prior/next runtime status, terminal transition, effective command kind, and next `InternalAgentState`, encoded with a versioned canonical codec and integrity hash. For durable runs, record this transition and collector delivery intent before objective append; after restart, validate and compare it with the authoritative tick commit, abort it if no tick committed, or restore/finalize it without rerunning cognition/provider calls if the tick committed. Mark subjective/runtime finalization and post-finalization delivery acknowledgement idempotently and in registration order.
  - Preserve exact once-only invocation and terminal semantics without allowing a failed durable append to advance subjective state. Define the unavoidable post-objective failure window: stop before the next tick, restore the stable pending batch after process restart, retry subjective finalization and receipt delivery idempotently, and keep the attempt recovery-required until all finalizers succeed. Never roll back or rewrite an already committed objective tick.
  - Keep direct one-call `process_observation()` only if an existing shipped caller requires it; otherwise migrate callers/tests to prepare/finalize rather than adding speculative compatibility behavior. Ensure `SubjectiveStateService` remains the atomic owner-scoped write path and fail closed when only non-atomic fallback writers are available for durable runs.
  - Add Alembic revision `0009` for append-only pending-finalization/outbox and attempt-state records so durable runner recovery is available before experiment-result persistence is built.
  - Files: `src/agents/cognition/loop.py`, `src/agents/cognition/contracts.py`, `src/agents/cognition/models.py`, `src/agents/cognition/memory.py`, `src/simulation/agent_runtime.py`, `src/simulation/subjective_state.py`, `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/persistence.py`, `src/simulation/contracts.py`, `src/simulation/__init__.py`, `src/persistence/orm.py`, `src/persistence/sqlalchemy.py`, `alembic/versions/0009_runner_finalization_outbox.py`, `tests/unit/test_cognitive_loop.py`, `tests/unit/test_agent_runtime.py`, `tests/unit/test_subjective_state_service.py`, `tests/unit/test_runner_finalization.py`, `tests/integration/test_agent_runtime_world_engine.py`, `tests/integration/test_runner_finalization_recovery.py`, `tests/integration/test_migrations.py`, `tests/integration/test_append_only.py`.
  - Logging: DEBUG prepare/finalize/abort boundaries with run/agent/tick/invocation IDs, update counts, and status codes; INFO successful subjective finalization or terminal transition; WARN idempotent retry/recovery-required state; ERROR stable prepare/finalize codes. Never log observations, submissions, memory/belief/relationship content, prompts, commands, seeds, or raw exceptions.
  - Dependencies: Tasks 3 and 4. This boundary must exist before runner tick orchestration.

- [x] Task 6: Implement deterministic tick scheduling, persistence, checkpointing, and stop semantics.
  - Deliverable: Implement `SimulationRunner.run_tick()` and `run()` with the exact sequence: observe once, route one observation per registration, prepare cognition sequentially in registration order, apply trusted command arbitration, bind effective commands into submissions/pending batches, durably record pending finalizations for durable runs, commit exactly once through the selected authority path, finalize all pending subjective batches deterministically, deliver post-finalization receipts exactly once, and evaluate stop conditions at fully finalized committed boundaries.
  - Support maximum ticks, all-agents-terminal, explicit injected stop condition, and external cancellation with closed `RunnerStopReason` values. Define fail-closed cognition policy (default abort with the tick left open) and an explicit omit-failed-agent option. Preserve N-to-N+1 death observation semantics and resolve the open tick before reporting all-terminal when required by engine phase invariants.
  - Generate deterministic idempotency/checkpoint IDs and honor checkpoint cadence for durable runs. Propagate append failures and `DurableCommitAmbiguity`; never silently switch authority paths, continue a fenced service, or claim a result for an uncommitted tick.
  - Return immutable `RunnerAttemptReceipt` values for started, aborted, committed-awaiting-finalization, recovery-required, and finalized attempts. Return a final `SimulationRunnerResult` only after the objective tick, every subjective finalization, and required receipt/outbox delivery have succeeded; recovery-required is never represented or persisted as a final result.
  - Files: `src/simulation/runner.py`, `src/simulation/runner_models.py`, `src/simulation/contracts.py`, `src/simulation/service.py`, `src/simulation/__init__.py`, `tests/unit/test_simulation_runner.py`, `tests/unit/test_persistent_simulation_service.py`.
  - Logging: DEBUG tick phase, registration ordinal, submission count, checkpoint decision, and commit cursors; INFO runner start, each committed tick, and terminal stop metadata; WARN omitted agent/fenced/cancellation policy paths; ERROR stable cognition/authority/persistence codes. Never log observations, commands, events, snapshots, seeds, configs, story content, memory, prompts, or raw exceptions.
  - Dependencies: Tasks 4 and 5 plus the existing `WorldEngine` and `PersistentSimulationService` contracts.

- [x] Task 7: Add versioned structured run observations and canonical results.
  - Deliverable: Define a narrow idempotent `ExperimentalObservationSink`/collector protocol that receives detached post-finalization deliveries with a stable durable delivery ID and returns an acknowledgement bound to that ID/content hash. Re-delivery of identical content must return the same acknowledgement without duplicating persisted effects; divergent reuse must fail. Add a versioned machine-readable result document and canonical codec containing condition/replicate metadata, configuration fingerprint references, ordered tick outcomes, aggregate counts, final objective-state/export hashes, subjective/analysis result references, replay verification status, and exact versus replica-normalized trajectory hashes.
  - Allow trusted collector implementations to receive only an explicit allowlist of detached public contracts such as committed `TickResult`, `SimulationExport`, verified `WorldSnapshot`, and metadata-only subjective finalization receipts. Prohibit live `WorldEngine` references, private `WorldState`, mutable repositories, or authority capabilities. Define crash semantics as at-least-once sink invocation with exactly-once persisted observation effects through delivery-ID deduplication and durable acknowledgement. The public result stores structured metrics and fingerprints rather than narrative text or payload dumps. Normalize run-derived IDs only in the documented replica comparison hash while retaining an exact identity hash for replay/audit.
  - Fix raw seed exposure in `simulation.contracts.describe_run()`/`log_run_configured()` and align runner diagnostics with the existing persistence allowlist.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/contracts.py`, `src/simulation/__init__.py`, `tests/unit/test_runner_results.py`, `tests/unit/determinism_helpers.py`, `tests/unit/test_v1_export_serialization.py`, `tests/unit/test_logging.py`.
  - Logging: Result collection and hashing are log-free. Runner logs only result schema/version, counts, status/stop codes, and hash prefixes. Tests must prove that seeds, canonical JSON, objective payloads, observations, commands, memory, experiment labels, and provider data never appear at DEBUG through ERROR.
  - Dependencies: Tasks 2 and 6.

### Phase 3: Reusable Experiment Definitions and Instrumentation

- [x] Task 8: Establish the trusted experiment package and reusable A-D condition definitions.
  - Deliverable: Add a packaged top-level `experiments` module with immutable `ExperimentDefinition`, `ExperimentCondition`, seed/replicate matrix, paired-world grouping, and stable condition fingerprints. Provide named builders for A (reference/reconstructive memory), B (imagination disabled/enabled), C (mortality disabled/enabled), and D (curiosity/safety/belonging/status profiles) that expand into complete runner configurations without mutating a shared base specification.
  - Ensure scenario/world/bootstrap/seed/stochastic identity remain identical across paired arms while durable run ID, condition ID, cognition fingerprint, and replicate metadata remain unique. Validate incompatible overrides and prove builder order does not affect canonical definitions.
  - Before adding the dependency, run the mandatory targeted `/aif-docs` checkpoint to update `.ai-factory/ARCHITECTURE.md` with the new outer package and adapter rule. Then register `experiments` in packaging, coverage, import-linter, and public facade checks. Allow it to coordinate public simulation and analysis contracts, but prohibit reverse imports from domain/simulation and prohibit agents/cognition/memory/social/world from importing it. Put experiment-specific persistence DTOs and repository protocols in `src/experiments/persistence.py`; explicitly permit only the concrete `persistence` adapter to implement/import those ports, while `experiments` itself never imports concrete persistence or SQLAlchemy. Keep generic run manifests and optional experiment assignment references in `simulation.persistence`.
  - Files: `.ai-factory/ARCHITECTURE.md` through `/aif-docs`, `src/experiments/__init__.py`, `src/experiments/models.py`, `src/experiments/catalog.py`, `src/experiments/coordinator.py`, `src/experiments/persistence.py`, `pyproject.toml`, `tests/unit/test_experiment_definitions.py`, `tests/unit/test_packaging.py`, `tests/architecture/test_import_boundaries.py`, `tests/architecture/boundary_checker.py`.
  - Logging: Definition construction is log-free. Coordinator DEBUG/INFO logs may include experiment/condition/run IDs, ordinals, replicate counts, mode codes, and fingerprint prefixes only; no labels, seeds, parameter values, world setup, or cognitive/story payloads. Invalid definitions emit stable ERROR codes.
  - Dependencies: Tasks 2, 3, and 7.

- [x] Task 9: Implement controlled false-story intervention and propagation observation for Experiment E.
  - Deliverable: Define separate `StoryIntervention` and analysis-only `StoryTruthSpec` contracts. Add a deterministic runner-level pre-admission intervention arbiter that replaces the source agent's normally prepared command with exactly one normal structured `Tell` at the configured tick and recipient, then passes that effective command through Task 5's runtime binding stage before submission and pending subjective state are created. Preserve the suppressed command only as a non-payload status code/count; never submit two actions for the source, finalize command-dependent state for the suppressed proposal, or expose the intervention/truth spec to cognition. The replacement remains subject to ordinary world eligibility, admission, delivery, memory formation, trust, reconstruction, and retelling behavior. Do not directly write another agent's memory or mark the utterance false.
  - Define one-shot semantics precisely: storage/objective commit failure retries the same intervention without consuming it; a successfully committed tick consumes it even if world admission rejects delivery, and the structured result records accepted/rejected reason metadata for analysis.
  - Strengthen communication lineage with an explicit root and parent communication identity through utterances, events, communicated-memory provenance, persistence mapping, and analysis hop records. Update propagation analysis to traverse real parent edges, handle branching/unresolved testimony deterministically, and report structured reach, adoption/evidence, hop, confidence, and exact concept/relation fidelity changes.
  - Correct `InMemoryMemoryEvidenceSource` run/owner scoping so multi-run experiments cannot contaminate traces or derivation edges. Keep the truth specification and objective comparison entirely inside trusted experiment/analysis code.
  - Files: `src/experiments/interventions.py`, `src/experiments/catalog.py`, `src/world/communications.py`, `src/world/events.py`, `src/agents/cognition/communication.py`, `src/memory/models.py`, `src/persistence/transmission_mapping.py`, `src/analysis/models.py`, `src/analysis/social_transmission.py`, `src/analysis/sources.py`, `src/analysis/__init__.py`, `tests/unit/test_experiment_interventions.py`, `tests/unit/test_social_transmission_analysis.py`, `tests/unit/test_multi_hop_communication_memory.py`.
  - Logging: Intervention scheduling may log experiment/run IDs, tick, source/recipient IDs, intervention ID, policy version, and status/reason code; never log payload fingerprints, story text, concepts, relations, truth label, memory content, communication body, or analysis payload. Analysis failures use stable graph/scope/version codes.
  - Dependencies: Tasks 6-8 and existing structured communication/transmission support.

- [x] Task 10: Implement experiment coordination and objective/subjective observation collectors.
  - Deliverable: Implement an async experiment coordinator that materializes condition/seed/replicate assignments, constructs one fresh runner per assignment, runs or safely resumes it, invokes registered post-commit and post-run collectors, and returns ordered structured run results. Add collectors for authoritative trajectory statistics, memory drift, imagination/mortality/drive outcomes, and Experiment E propagation while keeping each metric versioned and independently replaceable.
  - Define minimal versioned metrics per family: A records reference/reconstruction episode usage, source equivalence, reconstruction/reconsolidation counts, and drift deltas; B records generated-future counts/modes and selected future/intention/action outcomes; C records mortality appraisals, authoritative deaths/causes, terminal transitions, and survival ticks; D records configured profile fingerprints, drive activations, selected motives/intentions, goals, and action outcomes; E records delivery/adoption, reach, parent/root hops, confidence changes, and exact concept/relation fidelity. Label every field as authoritative, subjective, or derived and encode it canonically with explicit denominators where rates are reported.
  - Use read-only analysis sources after commits; do not pass analysis services, objective event repositories, snapshots, truth specs, or experiment results into `AgentRuntime`, `CognitiveLoop`, memory hooks, provider requests, or prompts. Define partial-failure semantics so a failed arm cannot be mistaken for a completed result and successful immutable arms are not rerun unnecessarily.
  - Add deterministic result ordering by condition ordinal, seed ordinal, and replicate index, independent of mapping/database row order. V1 execution remains sequential; future parallel execution must preserve the same ordering contract.
  - Files: `src/experiments/coordinator.py`, `src/experiments/collectors.py`, `src/experiments/models.py`, `src/experiments/__init__.py`, `src/analysis/contracts.py`, `src/analysis/service.py`, `tests/unit/test_experiment_coordinator.py`, `tests/unit/test_experiment_collectors.py`, `tests/architecture/test_experiment_instrumentation_isolation.py`.
  - Logging: DEBUG assignment/collector boundaries and metric versions; INFO arm start/completion with IDs, counts, status, and result hash prefix; WARN resume/skip/partial-result decisions; ERROR closed run/collector/persistence codes. Never log seeds, treatment values, objective/subjective payloads, story truth/content, prompts, model output, or raw exceptions.
  - Dependencies: Tasks 7-9.

### Phase 4: Durable Experiment Records, Proof, and Documentation

- [ ] Task 11: Persist immutable experiment definitions, assignments, observations, and results.
  - Deliverable: Implement the experiment-owned persistence DTOs/ports from Task 8 and add Alembic revision `0010` plus SQLAlchemy adapter mappings/repositories for versioned experiment definitions, condition cells, seed/replicate assignments, append-only structured observations, and one immutable final result per assigned run. Store canonical JSONB plus schema/version and SHA-256, scenario/condition/config fingerprints, stop status, final cursors/counts, exact and normalized trajectory hashes, replay status, and optional checkpoint/head-commit references.
  - Add create/get/list/resume operations with uniqueness on experiment/condition and experiment/condition/seed-ordinal/replicate, membership validation, deterministic ordering, idempotent identical writes, and conflicts for divergent reuse. Persist append-only runner attempt/recovery/finalization/outbox history as a mandatory separate record stream; write the single immutable final experiment result only after objective commit, all subjective finalizations, required collectors, and result hashing succeed.
  - Preserve append-only guarantees with `ON DELETE RESTRICT`, update/delete/truncate rejection triggers, strict foreign keys/checks/indexes, arbitrary non-negative seed storage, and disposable `palimpsest_test` integration safeguards. Never edit prior migrations.
  - Files: `src/experiments/persistence.py`, `src/experiments/__init__.py`, `src/simulation/persistence.py` only for generic assignment references if required, `src/persistence/orm.py`, `src/persistence/sqlalchemy.py`, `src/persistence/readers.py`, `src/persistence/errors.py`, `src/persistence/__init__.py`, `alembic/versions/0010_experiment_framework.py`, `tests/unit/test_experiment_persistence_contracts.py`, `tests/unit/test_sqlalchemy_repository.py`, `tests/integration/test_migrations.py`, `tests/integration/test_experiment_repository.py`, `tests/integration/test_append_only.py`.
  - Logging: DEBUG transaction/operation names, IDs, ordinals, record counts, versions, and hash prefixes; INFO immutable definition/assignment/result commits; WARN idempotent resume/duplicate-identical writes; ERROR stable constraint/conflict/rollback codes. Never log seeds, canonical JSON, condition parameters, labels, observations, result payloads, story data, DSNs, SQL parameters, or credentials.
  - Dependencies: Tasks 7, 8, and 10.

- [ ] Task 12: Add deterministic end-to-end runner and experiment integration proofs.
  - Deliverable: Add network-free integration tests using production in-memory memory/subjective services and deterministic cognition/provider fakes. Run independently constructed copies of the same configuration and assert equal canonical results, exact hashes when run identity is reused, replica-normalized hashes when durable IDs differ, and divergence when seed/stochastic identity or the intended cognitive treatment changes.
  - Exercise the complete runner loop, canonical registration order, staged command binding, durable pending-finalization/outbox restoration at every crash boundary, exactly-once subjective finalization and collector receipt delivery, terminal agents, maximum ticks, cognition abort/omit policy, checkpoint cadence, durable append/replay/resume, storage failure/fencing, and objective instrumentation isolation. Include explicit setup/expansion assertions for every A-E condition and prove paired arms preserve world/bootstrap/seed/stochastic identity while changing only declared treatment dimensions.
  - Always assert that intended treatment changes alter the condition/configuration fingerprint. Assert trajectory or metric divergence only in purpose-built fixtures that activate the treatment (memory-dependent choice, consequential counterfactual, lethal hazard, drive-sensitive tie, or retell opportunity); allow equal trajectories in neutral scenarios.
  - For Experiment E, prove the intervention enters through ordinary `Tell`, only intended recipients observe it, communicated memories remain owner-scoped, multi-hop lineage is parent/root correct, the objective false label never reaches agents, and repeated seeded runs produce equal structured propagation metrics.
  - Add PostgreSQL coverage for idempotent experiment restart, immutable results, migration constraints, assignment ordering, checkpoint replay, and no cross-run evidence leakage. Use databases containing `palimpsest_test` only.
  - Files: `tests/integration/test_simulation_runner.py`, `tests/integration/test_experiment_framework.py`, `tests/integration/test_experiment_repository.py`, `tests/unit/determinism_helpers.py`, `tests/simulation_helpers.py`, `tests/cognition_helpers.py`, `tests/fakes/cognition.py`, `tests/fakes/llm.py`, `tests/fakes/scripted_reconstructor.py`.
  - Logging: Capture all levels and assert deterministic metadata-only event sequences where promised. Verify logs contain only IDs/cursors/counts/versions/codes/hash prefixes and exclude seeds, world state, observations, actions, events, memory, story content/truth, drive values, config/result JSON, prompts, outputs, endpoints, credentials, and raw exception text.
  - Dependencies: Tasks 1-11.

- [ ] Task 13: Enforce architecture/privacy gates and document configuration-driven experiments.
  - Deliverable: Strengthen AST/import-linter tests so `experiments` is trusted outer orchestration, objective collectors cannot enter agents/cognition/memory/social/world, runner construction cannot import infrastructure or concrete persistence, and no agent-facing contract gains event stores, snapshots, truth labels, condition metadata, or analysis reports. Add schema/facade/type checks for configuration and result contracts.
  - Complete the mandatory `/aif-docs` checkpoint. Document the runner lifecycle, strict JSON configuration schema, stochastic versus durable identity, canonical scheduling, stop/failure/checkpoint behavior, LLM reproducibility limits, experiment A-E builders, result schemas, false-story trust boundary, persistence/resume workflow, safe logging, and exact test commands.
  - Update `README.md`, `docs/architecture.md`, `docs/cognition-runtime.md`, `docs/persistence.md`, add `docs/simulation-runner.md` and `docs/experiments.md`, and update `.ai-factory/DESCRIPTION.md` / `.ai-factory/ARCHITECTURE.md`. Update `.ai-factory/ROADMAP.md` only through its owner workflow after implementation and verification establish delivered scope.
  - Files: `pyproject.toml`, `tests/architecture/boundary_checker.py`, `tests/architecture/test_import_boundaries.py`, `tests/architecture/test_world_authority.py`, `tests/architecture/test_analysis_isolation.py`, `tests/architecture/test_experiment_instrumentation_isolation.py`, `tests/typecheck/`, `README.md`, `docs/architecture.md`, `docs/cognition-runtime.md`, `docs/persistence.md`, `docs/simulation-runner.md`, `docs/experiments.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`.
  - Logging: Document DEBUG/INFO/WARN/ERROR events, `PALIMPSEST_LOG_LEVEL`, safe fields, and the full prohibited payload list. Architecture/privacy failures may report file, symbol, field, and rule names only; verification must prove production verbosity changes require no code edits.
  - Dependencies: Tasks 1-12.

## Verification

Run focused unit and architecture gates first:

```bash
uv run --frozen --python 3.12.14 pytest \
  tests/unit/test_runner_models.py \
  tests/unit/test_runner_serialization.py \
  tests/unit/test_cognition_configuration.py \
  tests/unit/test_simulation_runner_construction.py \
  tests/unit/test_simulation_runner.py \
  tests/unit/test_runner_results.py \
  tests/unit/test_experiment_definitions.py \
  tests/unit/test_experiment_interventions.py \
  tests/unit/test_experiment_coordinator.py \
  tests/unit/test_experiment_collectors.py \
  tests/unit/test_experiment_persistence_contracts.py -q
uv run --frozen --python 3.12.14 pytest \
  tests/architecture/test_experiment_instrumentation_isolation.py \
  tests/architecture/test_analysis_isolation.py \
  tests/architecture/test_world_authority.py \
  tests/architecture/test_import_boundaries.py -q
uv run --frozen --python 3.12.14 pytest \
  -m integration \
  tests/integration/test_simulation_runner.py \
  tests/integration/test_experiment_framework.py -q
```

Run PostgreSQL integration gates against a disposable database:

```bash
PALIMPSEST_TEST_DATABASE_URL=<disposable-palimpsest_test-dsn> \
uv run --frozen --python 3.12.14 pytest -m integration \
  tests/integration/test_migrations.py \
  tests/integration/test_experiment_repository.py \
  tests/integration/test_append_only.py \
  tests/integration/test_simulation_persistence_replay.py -q
```

Run repository-wide quality gates:

```bash
uv run --frozen --python 3.12.14 ruff format --check src tests
uv run --frozen --python 3.12.14 ruff check src tests
uv run --frozen --python 3.12.14 mypy src tests
uv run --frozen --python 3.12.14 lint-imports --config pyproject.toml --no-cache --no-logo
uv run --frozen --python 3.12.14 pytest tests/architecture -q
uv run --frozen --python 3.12.14 pytest
uv run --frozen --python 3.12.14 pytest tests/unit/test_packaging.py -q
```

## Acceptance Criteria

- One strict, versioned configuration can construct a complete run with seed/stochastic identity, world and resources, agents and initial conditions, cognition/memory/imagination/mortality/drive policies, maximum ticks, LLM settings, and persistence/checkpoint behavior.
- `SimulationRunner` owns deterministic construction and the observe -> per-agent cognition -> ordered submissions -> authoritative commit lifecycle, and returns an explicit structured stop result without bypassing `WorldEngine` or durable commit semantics.
- Equal world/bootstrap/seed/stochastic identity values produce equal objective stochastic streams across different durable run IDs and cognitive conditions; paired experiment arms vary only declared treatment dimensions.
- Experiments A-E are reusable immutable definitions with stable fingerprints, deterministic matrix expansion, machine-readable assignments/results, and no narrative report dependency.
- Reference and reconstructive memory, imagination disabled/enabled, mortality disabled/enabled, and drive-profile treatments use explicit versioned policies rather than placeholder labels.
- Experiment E injects ordinary structured testimony through normal admission/perception, preserves owner-scoped subjective derivation and explicit root/parent lineage, and measures propagation without exposing objective truth or instrumentation to agents.
- Objective observations, snapshots, event sources, truth specifications, condition metadata, and analysis results are inaccessible from agents, cognition, memory, social policy, prompts, and action selection; architecture tests enforce the boundary.
- Durable experiment definitions, assignments, observations, and results are versioned, canonical, hash-verified, idempotent for identical retries, conflict on divergent reuse, queryable in deterministic order, and append-only in PostgreSQL.
- Repeated independently constructed seeded runs pass exact or replica-normalized canonical comparisons as appropriate. Seed/identity/treatment changes always alter their declared fingerprints, and purpose-built treatment-sensitive fixtures demonstrate metric or trajectory divergence without requiring divergence in neutral scenarios.
- All tests use deterministic fakes or recorded outputs for LLM-backed paths; unrecorded external LLM calls are explicitly classified as non-exactly-reproducible.
- Logs remain configurable and metadata-only at every level, with no seeds, state, observations, actions/events, memory, story content/truth labels, drive values, canonical documents, prompts, outputs, endpoints, credentials, or raw exceptions.
- Ruff, strict mypy, import-linter, architecture/privacy checks, default tests, opt-in runner/experiment integration tests, disposable PostgreSQL migration/repository tests, and packaging checks pass.
