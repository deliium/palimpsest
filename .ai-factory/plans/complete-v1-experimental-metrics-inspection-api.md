# Implementation Plan: Complete V1 with Experimental Metrics, Inspection API, Realtime Observation, and End-to-End Validation

Branch: main (no new branch)
Created: 2026-09-22

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M3 — Cognition and Providers (in progress)"
Rationale: This plan closes M3's remaining runtime/API composition and cognition integration gaps, completes M4's deferred analysis scope, and uses both as the final V1 delivery gate.

## Goal

Complete Palimpsest V1 as a reproducible research simulation system with versioned experimental metrics, a durable FastAPI inspection/control surface, resumable WebSocket observation, and a canonical five-agent reference scenario that runs entirely through the real architecture.

The delivered system must preserve five distinct evidence classes rather than flattening them into one narrative:

1. immutable objective `WorldEvent` and replayed world-state evidence;
2. owner-scoped direct or communicated `MemoryTrace` evidence;
3. reconstructed-memory evidence and derivation lineage;
4. append-only semantic `Belief` evidence and revisions;
5. socially transmitted versions, including world-verified delivery, speaker-declared lineage, receiver-owned traces, and analysis-only truth specifications.

The API is for research and inspection, not a production public service. No production frontend is required. Completion of all tasks and acceptance criteria in this plan constitutes V1 completion.

## Design Decisions

- Keep metrics in read-only `analysis`; compute them only from detached, run-scoped evidence after authoritative commit/finalization. Metrics, truth specifications, objective history, and experiment labels must never flow into cognition, memory formation, prompts, or action selection.
- Add NumPy, pandas, SciPy, and NetworkX as explicit runtime dependencies. Use NumPy/SciPy for finite numerical summaries and distributions, pandas for typed tabular aggregation/export, and NetworkX for directed trust/transmission graphs and deterministic community indicators. Pin compatible minimum versions in `pyproject.toml` and `uv.lock`; sort all inputs and specify algorithm seeds/tie-breaking so dependency iteration order cannot change results.
- Every metric document is immutable, schema-versioned, names its population, denominator, evidence class, availability/coverage, algorithm version, and input revision. Missing or unobservable evidence is `unknown`, never silently interpreted as zero or false.
- Belief accuracy and false-belief persistence require an explicit versioned truth evaluator. Controlled `StoryTruthSpec` data is analysis-only; ordinary claims without objective evaluability remain unknown and are excluded from accuracy denominators.
- Distinguish applied event rates from attempted/rejected/conflicted action rates. Persist detached `ActionResolution` evidence if attempted behavior is reported; never infer rejected attempts from absent events.
- Resource inequality is reported over explicitly named measures such as inventory count, inventory load, extraction, transfer, and consumption access. Do not call these measures generic wealth.
- Convention detection and specialization are neutral primitives: repeated action/interaction motifs, entropy, concentration, and divergence. Do not hard-code roles, culture, morality, leader, friend, or enemy labels.
- Keep FastAPI and Pydantic models in `api`; expose framework-free run-control, inspection, replay, and metric read models through public `simulation` contracts and concrete `persistence` factories. Do not relax existing domain import boundaries.
- Store full canonical runner configuration, lifecycle transitions, execution lease/heartbeat, progress cursor, final result, metric documents, and resumable stream records durably. Process-local runner objects, tasks, locks, and subscriber queues are caches/owners, not the source of truth.
- Use detached replay for objective and agent-visible inspection. Inspection must never expose live `WorldEngine`, private `WorldState`, or mutate engine phase by observing a live run.
- Subjective debug endpoints are disabled by default and require an explicit secret-backed research/debug gate. Logs never contain observations, events, communication bodies, memory/reconstruction content, belief claims/values, relationships, prompts, outputs, seeds, configuration documents, or credentials.
- WebSocket delivery uses a versioned envelope, durable monotonic cursor, catch-up then live subscription, bounded per-subscriber queues, and reconnect/resume. Slow consumers are disconnected without blocking simulation progress.
- The reference scenario uses deterministic provider behavior and production cognition/memory/imagination paths. Sparse trusted command overrides may guarantee milestone events, but must still produce fresh structured commands that pass normal runtime binding, admission, world resolution, observation, and subjective finalization.
- V1 remains single-process execution by default. Cross-process leases prevent duplicate execution; PostgreSQL is the durable stream source. `LISTEN/NOTIFY` may be a wake-up optimization but is never authoritative.

## Non-Goals

- A production frontend, public multi-tenant authentication system, billing, or internet-facing deployment hardening.
- Kafka, Celery, microservices, a generic workflow engine, or an additional database/vector store.
- Concurrent agent cognition, completion-order scheduling, or nondeterministic wall-clock simulation.
- Treating declared testimony as truth, reconstruction as objective history, or analysis output as agent context.
- Persisting chain-of-thought, raw prompts/provider output, unrestricted free-form reports, or arbitrary exception text.
- Claiming exact replay for unrecorded external LLM calls.

## Commit Plan
- **Commit 1** (after tasks 1-5): `feat(simulation): complete recoverable scientific evidence foundations`
- **Commit 2** (after tasks 6-8): `feat(persistence): add durable run control and evidence revisions`
- **Commit 3** (after tasks 9-12): `feat(analysis): establish the reference scenario and objective metrics`
- **Commit 4** (after tasks 13-16): `feat(analysis): add subjective network and transmission metrics`
- **Commit 5** (after tasks 17-19): `feat(api): add simulation inspection and realtime streaming`
- **Commit 6** (after tasks 20-22): `feat(v1): enforce end-to-end completion gates`

## Tasks

### Phase 1: Simulation-Owned Evidence and Recovery Foundations

- [x] Task 1: Version runner configuration/results and define simulation-owned scientific receipts.
  - Deliverable: Introduce explicit `runner-config-v2` and `runner-result-v2` codecs for agent names, ordered goals, detached finalized tick receipts, ordered `ActionResolution` evidence, cognition/imagination counters, objective-state hashes, and exact versus replica-normalized trajectory identity. Preserve explicit V1 decode/upgrade or rejection behavior; exact hashes include run-scoped identity, while normalized hashes remove documented run-derived IDs without collapsing different trajectories.
  - Define immutable goal-transition receipts and a deterministic post-finalization evaluator over observable evidence. Specify completion, abandonment, death, and run-end semantics for every supported goal outcome; do not treat imagined `GoalEffect` values as committed outcomes.
  - Honor checkpoint cadence, page replay reads, expose detached final objective projections, and retain enough public receipt data for tests without private engine access.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/runner.py`, `src/simulation/lifecycle.py`, `src/simulation/replay.py`, `src/simulation/persistence.py`, `src/simulation/contracts.py`, `src/simulation/__init__.py`, `tests/unit/test_runner_models.py`, `tests/unit/test_runner_serialization.py`, `tests/unit/test_runner_results.py`, `tests/unit/test_simulation_runner.py`, `tests/unit/test_replay_service.py`, `tests/typecheck/simulation_runner.py`.
  - Logging: DEBUG receipt/checkpoint/goal boundaries with IDs, cursors, counts, versions, status codes, and hash prefixes; INFO finalized ticks/checkpoints; WARN legacy/recovery/cancellation/fencing states; ERROR stable codec/lifecycle codes. Never log names, goals, seeds, commands, events, state, cognition artifacts, canonical JSON, or raw exceptions.
  - Dependencies: None. These contracts are simulation-owned and must not import `analysis`.

- [x] Task 2: Define analysis evidence, metric-document contracts, and deterministic numerical policy.
  - Deliverable: Add immutable analysis DTOs with a closed evidence-stage enum covering objective event/state, agent-visible projection, direct trace, communicated trace, reconstruction, reconsolidated trace, belief revision/testimony, relationship revision, goal transition, and action resolution. Every result carries run scope, stable provenance, availability, population, denominator, coverage, algorithm/library versions, and immutable input revision.
  - Add NumPy, pandas, SciPy, and NetworkX to `pyproject.toml`/`uv.lock`. Define dtypes, accumulation/rounding, signed-zero and non-finite handling, pandas ordering/null policies, SciPy degenerate behavior, exact graph algorithms/projections/weights/seeds, canonical Python conversion, and supported dependency versions. Claim canonical quantized output, not unconstrained BLAS/platform bit identity.
  - Correct in-memory run/owner scoping by placing scope on evidence/edge storage rather than filtering unscoped `SubjectiveDerivationEdge` values after the fact.
  - Files: `pyproject.toml`, `uv.lock`, `src/analysis/evidence.py`, `src/analysis/models.py`, `src/analysis/contracts.py`, `src/analysis/sources.py`, `src/analysis/serialization.py`, `src/analysis/__init__.py`, `tests/unit/test_analysis_contracts.py`, `tests/unit/test_analysis_sources.py`, `tests/unit/test_analysis_serialization.py`, `tests/unit/test_packaging.py`.
  - Logging: Numerical/model code is log-free. DEBUG service boundaries may report run/owner IDs, versions, row/node and availability counts, and duration; WARN/ERROR use stable scope/version/non-finite codes. Never log evidence, claims, graph labels, seeds, or metric documents.
  - Dependencies: Task 1 for simulation-owned receipts and goal/action evidence.

- [x] Task 3: Establish the legal evidence composition boundary, immutable evidence manifests, and claim-level truth contracts.
  - Deliverable: Resolve the current import-contract deadlock by defining neutral detached persistence rows/repository protocols and an allowed outer composition service that may assemble persistence readers into `analysis` sources without permitting `analysis -> persistence`, `persistence -> analysis`, or `api -> analysis`. Encode this decision in import-linter and AST tests.
  - Define an immutable evidence manifest with objective commit/hash plus per-source high-water marks for direct/communicated memories, reconstructions, beliefs, relationships, goals, resolutions, and truth specs. Require repeatable-read loading constrained to the manifest and use its hash in metric idempotency keys.
  - Replace concept-only truth input for metric purposes with versioned claim identities, typed expected values, validity intervals/ticks, units/tolerances/evaluator policy, and intervention/objective provenance. Truth specifications remain analysis-only and may never enter runner configuration, cognition, prompts, or memory formation.
  - Files: `src/simulation/evidence.py`, `src/analysis/contracts.py`, `src/analysis/evidence.py`, `src/experiments/interventions.py`, `src/experiments/persistence.py`, `src/persistence/analysis_sqlalchemy.py`, `pyproject.toml`, `tests/architecture/test_analysis_isolation.py`, `tests/architecture/test_experiment_instrumentation_isolation.py`, `tests/unit/test_evidence_manifest.py`, `tests/unit/test_truth_specifications.py`.
  - Logging: DEBUG manifest/source versions, high-water counts, transaction status, and hash prefixes; WARN incomplete/legacy evidence; ERROR stable manifest/scope/version codes. Never log truth values, claims, source rows, canonical manifests, or SQL parameters.
  - Dependencies: Tasks 1-2.

- [x] Task 4: Build one coherent async subjective pipeline with direct memory and reconstruction.
  - Deliverable: Replace disconnected `MemoryStore`/`BeliefStore` reads with an async owner-scoped bundle protocol providing memory, belief, relationship, reconstruction, snapshot, and atomic commit services. Generalize runner fields/factories to protocols so persistence adapters can be injected at the API composition boundary.
  - Add production direct-observation memory formation using only owner-visible `Observation` data and opaque source IDs. Introduce a typed pending-evidence accumulator so direct/communicated traces proposed by one hook can drive belief and relationship revisions in the same atomic batch without mutating stores between hooks. Reuse `RegistrationTranslator` for entity-to-agent resolution.
  - Wire deterministic and optional LLM-backed reconstruction through the provider-neutral boundary; deterministic-fake mode must be a real closeable deterministic provider/reconstructor, not the disabled provider. Preserve direct -> reconstructed -> reconsolidated provenance.
  - Files: `src/simulation/runner.py`, `src/simulation/agent_runtime.py`, `src/simulation/subjective_state.py`, `src/simulation/perception.py`, `src/agents/cognition/configuration.py`, `src/agents/cognition/defaults.py`, `src/agents/cognition/communication.py`, `src/agents/cognition/memory.py`, `src/agents/cognition/reconstruction.py`, `src/memory/service.py`, `src/memory/belief_service.py`, `src/social/service.py`, `tests/unit/test_direct_observation_memory.py`, `tests/unit/test_communicated_memory_cognition.py`, `tests/unit/test_subjective_relationships.py`, `tests/unit/test_simulation_runner_construction.py`.
  - Logging: DEBUG owner/tick/invocation IDs, stage/policy IDs, counts, and status codes; INFO successful bundle construction/finalization; WARN deterministic fallback/idempotent retry; ERROR stable provider/snapshot/finalization codes. Never log observations, traces, reconstructions, beliefs, relationships, utterances, prompts, outputs, or commands.
  - Dependencies: Task 1 for runtime receipts and Task 3 for injectable boundary contracts.

- [x] Task 5: Make subjective finalization recoverable and rehydrate runnable simulations.
  - Deliverable: Replace metadata-only pending rows with a versioned, privacy-reviewed finalization command containing the complete idempotent runtime transition and subjective mutation data required after restart. Add a `SimulationRunner` resume/rehydration path restoring runtime statuses, invocation/internal state, goals, provider resources, subjective readers, committed tick count, and pending finalizers without rerunning cognition/provider calls.
  - Distinguish objective replay, pending-subjective recovery, and continued execution. Add crash tests before objective commit, after commit, during each owner finalization, before collector/stream publication, and after acknowledgement; committed objective history is never rolled back or duplicated.
  - Files: `src/simulation/runner.py`, `src/simulation/agent_runtime.py`, `src/simulation/subjective_serialization.py`, `src/simulation/runner_serialization.py`, `src/simulation/run_control.py`, `src/simulation/persistence.py`, `src/persistence/runner_sqlalchemy.py`, `tests/unit/test_runner_finalization.py`, `tests/unit/test_runner_pending_ports.py`, `tests/integration/test_runner_finalization_recovery.py`, `tests/integration/test_simulation_runner.py`.
  - Logging: DEBUG recovery boundary, run/tick/owner/delivery IDs, versions, counts, and state codes; INFO recovered/finalized transitions; WARN ambiguous/idempotent/fenced outcomes; ERROR stable corruption/recovery codes. Never log serialized finalization payloads, internal state, subjective mutations, commands, prompts, or raw exceptions.
  - Dependencies: Tasks 1 and 4.

### Phase 2: Durable Run Control, Evidence, and Inspection

- [x] Task 6: Persist runner configuration V2, lifecycle transitions, leases, and experiment assignments.
  - Deliverable: Define and test the lifecycle graph, including a resumable `ready`/`paused` state for one-tick execution, plus configured/starting/running/stopping/completed/failed/fenced/recovery-required/interrupted states. Implement canonical configuration storage, optimistic transitions, execution claims/heartbeats/expiry, and process-restart classification.
  - Add migration `0011_v1_run_control.py`. Keep legacy runs explicitly configuration-unavailable rather than fabricating names/goals/configuration. Reconcile legacy `ExperimentRunOrm` with `ExperimentAssignmentOrm`, define canonical membership, handle orphan rows before adding foreign keys, and update all coordinator/loader paths atomically.
  - Files: `src/simulation/run_control.py`, `src/simulation/persistence.py`, `src/experiments/persistence.py`, `src/persistence/run_control_sqlalchemy.py`, `src/persistence/experiment_sqlalchemy.py`, `src/persistence/orm.py`, `src/persistence/__init__.py`, `alembic/versions/0011_v1_run_control.py`, `tests/unit/test_run_control_contracts.py`, `tests/unit/test_run_control_repository.py`, `tests/integration/test_run_control_repository.py`, `tests/integration/test_experiment_repository.py`, `tests/integration/test_migrations.py`.
  - Logging: DEBUG operation/run/lease IDs, lifecycle codes, versions, counts, and durations; INFO claims/transitions; WARN contention/expiry/legacy/recovery states; ERROR stable persistence/conflict codes. Never log configuration, seeds, DSNs, SQL parameters, or credentials.
  - Dependencies: Tasks 1, 3, and 5.

- [x] Task 7: Persist scientific evidence manifests, goals, resolutions, truth specs, metric state, results, and the unified stream.
  - Deliverable: Add migration `0012_v1_scientific_evidence.py` with append-only/versioned goal revisions, action resolutions keyed by `(run,tick,ordinal)`, claim-level truth specs, evidence manifests/high-water marks, metric-set lifecycle (`pending|running|complete|partial|failed`), immutable metric documents/results, and a unified stream/outbox with one monotonic per-run cursor for status, eventless tick, event, metric, result, recoverable error, and completion records.
  - Define codecs/content hashes, identical-retry behavior, divergent conflicts, foreign keys/indexes, update/delete/truncate protections, legacy availability, metric/evidence-revision linkage, and atomic finalized-boundary stream publication. Update migration-head, ORM-table parity, and append-only registries/tests.
  - Files: `src/simulation/evidence.py`, `src/simulation/run_control.py`, `src/experiments/persistence.py`, `src/persistence/run_control_sqlalchemy.py`, `src/persistence/experiment_sqlalchemy.py`, `src/persistence/orm.py`, `src/persistence/__init__.py`, `alembic/versions/0012_v1_scientific_evidence.py`, `tests/integration/test_migrations.py`, `tests/integration/test_append_only.py`, `tests/integration/test_metric_persistence.py`, `tests/integration/test_stream_repository.py`.
  - Logging: DEBUG record kind, run/cursor/revision IDs, versions, counts, and hash prefixes; INFO immutable manifest/result commits; WARN identical retry/partial metric state; ERROR stable constraint/corruption codes. Never log evidence, resolution commands, truth specs, metrics, stream bodies, SQL, or DSNs.
  - Dependencies: Tasks 2-3 and 6.

- [x] Task 8: Implement detached objective/subjective loaders and visibility-correct inspection projection.
  - Deliverable: Add separate run-scoped objective, subjective, and inspection loaders constrained by one evidence manifest under repeatable-read semantics. Support optional experiment membership rather than requiring `ExperimentRunOrm`; enforce run/owner scope, deterministic keyset pagination, maximum page sizes, chunked replay, and explicit unavailable/partial reconstruction content.
  - Add a simulation-owned detached projector that can produce objective world state and the exact agent-visible historical projection without calling mutating live `WorldEngine.observe()`. Preserve hidden-state filtering, agent/entity mapping, and public versus debug boundaries; never expose `ReplayOutcome.engine` through API DTOs.
  - Files: `src/simulation/inspection.py`, `src/simulation/engine.py`, `src/simulation/replay.py`, `src/simulation/__init__.py`, `src/persistence/analysis_sqlalchemy.py`, `src/persistence/inspection_sqlalchemy.py`, `src/persistence/readers.py`, `src/persistence/subjective_sqlalchemy.py`, `src/persistence/memory_sqlalchemy.py`, `src/persistence/__init__.py`, `src/analysis/sources.py`, `tests/unit/test_analysis_sources.py`, `tests/unit/test_simulation_inspection.py`, `tests/integration/test_analysis_persistence.py`, `tests/integration/test_inspection_pagination.py`.
  - Logging: DEBUG query/projection type, run/owner/agent IDs, cursor/limit/counts, availability, integrity, and duration; WARN legacy/partial/missing evidence; ERROR stable scope/query/replay/privacy codes. Never log rows, projected state, observations, events, claims, memories, relationships, SQL, or DSNs.
  - Dependencies: Tasks 3 and 6-7.

### Phase 3: Reference Scenario and Objective Metrics

- [x] Task 9: Add the canonical five-agent reference scenario and typed milestone arbitration.
  - Deliverable: Create a reusable 48-tick/two-day scenario with five named agents, structured goals, connected locations, food/water extraction and consumption, actual resource depletion/regeneration, survival needs, normal communication, direct/reconstructive memory, relationships, imagination, and one death early enough to prove N+1 terminal observation and a later no-action tick.
  - Define a typed arbiter protocol returning a fresh command plus milestone ID; acknowledge one-shot status from the committed `ActionResolution`. Use fresh deterministic communication IDs and record proposed-versus-effective metadata. Set a numeric override budget so most of the 240 cognition invocations remain production-policy decisions.
  - Files: `src/experiments/reference_scenario.py`, `src/experiments/interventions.py`, `src/experiments/__init__.py`, `src/simulation/runner.py`, `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `tests/reference_scenario_helpers.py`, `tests/unit/test_reference_scenario_spec.py`, `tests/unit/test_experiment_interventions.py`.
  - Logging: INFO scenario IDs, counts, versions, max ticks, and fingerprint prefixes; DEBUG milestone IDs/ticks/status only; WARN unmet milestone preconditions; ERROR stable scenario/arbiter codes. Never log names, goals, locations/resources, seeds, commands, utterances, memories, beliefs, truth labels, or config payloads.
  - Dependencies: Tasks 1 and 4-5. The scenario is an input fixture for metric implementation, not a consumer of metrics.

- [x] Task 10: Specify formulas, populations, denominators, and edge-case policy for all V1 metrics.
  - Deliverable: Publish executable metric specifications for all fifteen required families before implementation. Define cohort/time windows, deceased/zero-holding treatment, opportunity versus occurrence denominators, self-edge/exclusion rules, censoring, action vocabulary, motif tokenization/gaps/support, adoption stages, evidence-stage deduplication, signed trust handling, graph projection/community algorithm, and empty/one/all-zero/unknown cases.
  - Define known-answer fixtures from Task 9 plus small degenerate fixtures. Every formula names evidence inputs, availability behavior, exact NumPy/pandas/SciPy/NetworkX policy, canonical quantization, and version identifier.
  - Files: `src/analysis/specifications.py`, `src/analysis/models.py`, `docs/analysis-metrics.md`, `tests/unit/metric_fixtures.py`, `tests/unit/test_metric_specifications.py`.
  - Logging: Specification/model code is log-free. Validation errors expose only metric/version and stable reason codes, never fixture values or evidence content.
  - Dependencies: Tasks 2-3, 8, and 9.

- [x] Task 11: Implement objective outcome metrics.
  - Deliverable: Implement resource inequality, cooperation/conflict occurrence and attempted/rejected/conflicted rates, survival, and goal completion from immutable events, replayed state, action resolutions, registrations, and goal revisions. Use explicitly named inventory count/load, extraction, transfer, and consumption-access measures; distinguish attacks, fleeing, helping, giving, and communication rather than silently combining them.
  - Add known-answer, unknown/legacy, censoring, permutation-determinism, finite-output, and Hypothesis invariant tests.
  - Files: `src/analysis/objective_metrics.py`, `src/analysis/models.py`, `src/analysis/serialization.py`, `src/analysis/__init__.py`, `tests/unit/test_objective_metrics.py`, `tests/unit/test_metric_properties.py`.
  - Logging: DEBUG metric/version, run scope, input/output counts, population/denominator, availability, and duration; WARN insufficient/degenerate/legacy evidence; ERROR stable non-finite/calculation codes. Never log events, inventories, goals, rows, or results.
  - Dependencies: Tasks 7-10.

- [x] Task 12: Implement repeated-convention and behavioral-specialization indicators.
  - Deliverable: Implement neutral repeated action/interaction n-grams and actor/location/target motifs with support, recurrence, opportunity coverage, and gap policy. Implement per-agent action/resource distributions, entropy/concentration, normalized divergence from the population, and idle/dead-period handling without assigning culture or role labels.
  - Use deterministic pandas tables and NumPy/SciPy calculations per Task 10; include input permutation, zero-action, one-agent, terminal-agent, and known-answer tests.
  - Files: `src/analysis/behavior_metrics.py`, `src/analysis/models.py`, `src/analysis/serialization.py`, `src/analysis/__init__.py`, `tests/unit/test_behavior_metrics.py`, `tests/unit/test_metric_determinism.py`.
  - Logging: DEBUG metric/version, action/motif/population counts, availability, and duration; WARN sparse/degenerate evidence; ERROR stable vocabulary/non-finite codes. Never log behavior rows, command payloads, motifs containing content, or metric documents.
  - Dependencies: Tasks 8-10.

### Phase 4: Subjective, Network, and Experiment Metrics

- [x] Task 13: Implement visibility-aware memory drift, belief accuracy, and false-belief persistence.
  - Deliverable: Compare direct memory first against the exact agent-visible projection, then optionally report a separately labeled authoritative-world gap. Preserve direct/communicated/reconstructed/reconsolidated/belief/testimony stages on every row and deduplicate corroboration by lineage root.
  - Evaluate only claims covered by Task 3's typed truth specs. Implement categorical/numeric policies, validity intervals, confidence-weighted accuracy, onset/correction/retirement, right-censored persistence, and unknown/unobservable exclusion; objective truth never enters live cognition.
  - Files: `src/analysis/memory_drift.py`, `src/analysis/belief_metrics.py`, `src/analysis/service.py`, `src/analysis/models.py`, `src/analysis/__init__.py`, `tests/unit/test_memory_drift_analysis.py`, `tests/unit/test_reconstruction_analysis_service.py`, `tests/unit/test_belief_metrics.py`, `tests/architecture/test_analysis_isolation.py`.
  - Logging: DEBUG scope, metric/projector/evaluator versions, chain/revision/evaluable/unknown/censored counts; WARN incomplete lineage/truth; ERROR stable evaluator/scope codes. Never log observations, narratives, claims, truth values, memories, beliefs, or results.
  - Dependencies: Tasks 3-4, 8, and 10.

- [x] Task 14: Implement relationship stability, signed trust networks, and community indicators.
  - Deliverable: Compute tick- or revision-weighted directed relationship stability with explicit missing-dimension, activation/retirement, sign-change, variance, delta, and duration policy. Build sorted signed trust/interaction graphs with confidence/threshold/self-loop/isolate rules and report density, reciprocity, weighted degrees, components, centralization, and one named deterministic community algorithm over an explicit nonnegative projection.
  - Canonicalize community labels and validate library version, node/edge ordering, negative/zero weights, disconnected graphs, and input permutations.
  - Files: `src/analysis/relationship_metrics.py`, `src/analysis/network_metrics.py`, `src/analysis/models.py`, `src/analysis/__init__.py`, `tests/unit/test_relationship_metrics.py`, `tests/unit/test_network_metrics.py`, `tests/unit/test_metric_determinism.py`.
  - Logging: DEBUG graph/metric versions, run scope, node/edge/component/community counts, availability, and duration; WARN disconnected/insufficient graphs; ERROR stable graph/non-finite codes. Never log relationship values by named pair, membership lists, graph payloads, or results.
  - Dependencies: Tasks 8 and 10.

- [x] Task 15: Repair transmission lineage and implement stage-specific diffusion and rumor distortion.
  - Deliverable: Correct root/parent propagation in `StructuredUtterance`, world events, communicated-memory provenance, subjective codecs, and persistence mappings. Prefer explicit root identity with an event/schema migration when necessary; reject cycles, preserve unresolved testimony, and never infer parents from sorted hop order.
  - Implement separate world-delivery, receiver-trace, belief-candidate, belief-activation, reconstruction, and retell adoption metrics. Report first adoption, reach, hops/time, branching, structured concept/relation edits, unsupported additions/losses, confidence attenuation, and unresolved coverage without merging declared lineage with verified truth.
  - Files: `src/world/communications.py`, `src/world/events.py`, `src/agents/cognition/communication.py`, `src/memory/models.py`, `src/simulation/subjective_serialization.py`, `src/persistence/transmission_mapping.py`, `src/analysis/social_transmission.py`, `src/analysis/transmission_metrics.py`, `src/analysis/models.py`, `tests/unit/test_multi_hop_communication_memory.py`, `tests/unit/test_social_transmission_analysis.py`, `tests/unit/test_transmission_metrics.py`, `tests/integration/test_social_transmission_analysis_persistence.py`.
  - Logging: DEBUG lineage/metric versions, run scope, stage/hop/branch/unresolved counts, and duration; WARN cycle/unresolved/partial evidence; ERROR stable schema/lineage codes. Never log utterances, claims, memories, concept/relation payloads, truth values, or metric documents.
  - Dependencies: Tasks 3-4, 7-10, and 13.

- [x] Task 16: Add run-level metric orchestration, durable experiment collection, and compatible comparison.
  - Deliverable: Assemble all metric families from one evidence manifest, maintain a separate metric-set lifecycle from objective run completion, emit canonical quantized documents, and persist each family idempotently through neutral repository protocols at the composition boundary defined in Task 3.
  - Replace placeholder collectors, attach canonical experiment assignments, support run-level metrics without experiment membership, and compare only compatible schema/algorithm/library/population/denominator/evidence revisions. Repeated computation over the same manifest must produce the same canonical hashes.
  - Files: `src/analysis/metric_service.py`, `src/analysis/serialization.py`, `src/experiments/metric_collection.py`, `src/experiments/collectors.py`, `src/experiments/coordinator.py`, `src/experiments/models.py`, `src/persistence/experiment_sqlalchemy.py`, `tests/unit/test_metric_service.py`, `tests/unit/test_experiment_collectors.py`, `tests/unit/test_experiment_coordinator.py`, `tests/integration/test_metric_persistence.py`.
  - Logging: DEBUG manifest/family/version/count/duration/hash-prefix boundaries; INFO metric-set state changes; WARN partial/unknown/incompatible comparisons; ERROR stable collector/persistence codes. Never log metric bodies, evidence, truth specs, condition values, seeds, or canonical documents.
  - Dependencies: Tasks 7-15.

### Phase 5: Research API and Realtime Observation

- [ ] Task 17: Implement API security, schemas, errors, and the recoverable simulation manager.
  - Deliverable: Define separate capabilities for simulation control, objective inspection/streaming, agent-visible projection, and subjective debug. Add bounded `PALIMPSEST_API_*` settings, disabled-by-default debug access, strong `SecretStr` credentials, safe header/WebSocket-subprotocol transport, and explicit prohibition on query-string secrets.
  - Add strict Pydantic schemas, stable problem details, and an API manager for per-run locks, leases/heartbeats, one-tick ready-state transitions, run-to-stop tasks, stop-at-finalized-boundary, rehydration, metric lifecycle, and graceful draining.
  - Files: `src/infrastructure/settings.py`, `src/infrastructure/logging.py`, `src/api/schemas.py`, `src/api/errors.py`, `src/api/security.py`, `src/api/simulation_manager.py`, `src/api/dependencies.py`, `src/api/app.py`, `.env.example`, `tests/unit/test_settings.py`, `tests/unit/test_logging.py`, `tests/unit/test_api_security.py`, `tests/unit/test_api_simulation_manager.py`, `tests/unit/test_api_composition.py`.
  - Logging: DEBUG manager/lease/task boundaries with request/run/connection IDs, lifecycle codes, counts, and duration; INFO create/start/stop/completion; WARN conflict/expiry/shutdown/recovery; ERROR stable API codes. Allow bounded route templates, never raw paths/query strings, bodies, tokens, configuration, seeds, evidence, metrics, prompts, credentials, or exceptions.
  - Dependencies: Tasks 5-8 and 16.

- [ ] Task 18: Add versioned REST control, inspection, debug, metric, and replay endpoints.
  - Deliverable: Add `/v1` create/configure/start/tick/run/stop/list/status endpoints; objective world, commits/events, agent-visible observation, metadata-only experimental state, gated owner-scoped memories/beliefs/relationships, metric catalog/documents, and replay-to-tick endpoints.
  - Enforce capability checks, lifecycle conflicts, idempotency, bounded keyset pagination, run/owner scope, disabled debug routes, legacy/unavailable evidence semantics, and stable replay/corruption responses. API imports only allowed public `simulation`, `infrastructure`, and `persistence` surfaces.
  - Files: `src/api/routes/simulations.py`, `src/api/routes/inspection.py`, `src/api/routes/replay.py`, `src/api/routes/__init__.py`, `src/api/app.py`, `src/api/dependencies.py`, `src/api/schemas.py`, `tests/unit/test_api_simulation_routes.py`, `tests/unit/test_api_inspection_routes.py`, `tests/unit/test_api_replay_routes.py`, `tests/integration/test_api_simulation_lifecycle.py`, `tests/integration/test_api_event_pagination.py`, `tests/integration/test_api_debug_scope.py`.
  - Logging: INFO route template/method/status/request/run ID and bounded counts; DEBUG manager/projection timing; WARN auth/lifecycle/conflict codes; ERROR stable internal codes. Never log raw paths/query strings, bodies, state/evidence/metrics, credentials, or exception text.
  - Dependencies: Tasks 8, 16, and 17.

- [ ] Task 19: Implement resumable WebSocket progress and event streaming from the durable outbox.
  - Deliverable: Add `/v1/simulations/{run_id}/stream` with authenticated pre-accept, versioned envelopes, one durable cursor, catch-up/high-water/live handoff, eventless ticks, status/metric/result/error/completion frames, bounded queues, non-blocking fan-out, heartbeats, slow-consumer reconnect, disconnect cleanup, and graceful shutdown.
  - Consume Task 7's stream/outbox as the sole replayable source; PostgreSQL polling or `LISTEN/NOTIFY` is only a wake-up optimization. Specify an in-process Starlette/AnyIO WebSocket test harness because `httpx.ASGITransport` does not support WebSockets.
  - Files: `src/api/streaming.py`, `src/api/routes/streams.py`, `src/api/routes/__init__.py`, `src/api/app.py`, `src/api/dependencies.py`, `src/api/schemas.py`, `src/persistence/run_control_sqlalchemy.py`, `tests/unit/test_api_streaming.py`, `tests/integration/test_api_stream_resume.py`, `tests/integration/test_api_stream_backpressure.py`.
  - Logging: DEBUG connection/run IDs, cursors, counts, queue/high-water state, and close codes; INFO accepted/completed sessions; WARN invalid cursor/slow consumer/auth failure; ERROR stable stream codes. Never log query strings, auth data, frame bodies, events, observations, metrics, subjective content, or exceptions.
  - Dependencies: Tasks 7 and 17-18.

### Phase 6: V1 Completion Gates and Documentation

- [ ] Task 20: Add default-suite reference, metric, determinism, architecture, and privacy proofs.
  - Deliverable: Run the five-agent scenario for 48 ticks through production in-memory architecture and prove the nine mandatory invariants with public receipts/projections only. Include day/night, actual food/water extraction/consumption/regeneration, direct/reconstructed divergence, communication propagation, imagination, asymmetric relationships, goal outcomes, early death/N+1 terminal/no later action, all metric families, same-input canonical hashes, and seed-sensitive divergence.
  - Add short bounded Hypothesis variants for topology/seed/order invariants rather than repeating the full scenario per example. Forbid new tests from reading `runner.engine`, `_snapshot`, private `world._*`, or `WorldState`.
  - Files: `tests/unit/test_reference_scenario_e2e.py`, `tests/unit/test_reference_scenario_properties.py`, `tests/unit/test_metric_properties.py`, `tests/architecture/test_world_authority.py`, `tests/architecture/test_cognitive_loop_isolation.py`, `tests/architecture/test_memory_isolation.py`, `tests/architecture/test_analysis_isolation.py`, `tests/architecture/test_experiment_instrumentation_isolation.py`, `tests/typecheck/`.
  - Logging: Capture owned loggers at every level and assert only IDs, route templates, cursors, versions, counts, codes, durations, and hash prefixes appear. Reject raw paths/query strings, seeds, state, observations, actions/events, communications, subjective content, metrics, prompts/outputs, credentials, and exception text.
  - Dependencies: Tasks 1-16.

- [ ] Task 21: Add PostgreSQL recovery, persistence, API, WebSocket, and replay completion proofs.
  - Deliverable: Use globally unique run/test namespaces so append-only rows survive safely across tests and workers. Prove migration/trigger parity, experiment reconciliation, finalization recovery at every crash boundary, evidence-manifest consistency, keyset pagination, durable metric recomputation, API lifecycle/debug scope, stream resume/backpressure without gaps/duplicates, checkpoint cadence, continuation at head, and final objective replay equality.
  - Tests may target only explicitly validated databases containing `palimpsest_test`; Alembic receives the validated URL directly and fails closed on conflicting ambient URLs.
  - Files: `tests/integration/test_migrations.py`, `tests/integration/test_append_only.py`, `tests/integration/test_runner_finalization_recovery.py`, `tests/integration/test_experiment_repository.py`, `tests/integration/test_analysis_persistence.py`, `tests/integration/test_inspection_pagination.py`, `tests/integration/test_social_transmission_analysis_persistence.py`, `tests/integration/test_metric_persistence.py`, `tests/integration/test_api_simulation_lifecycle.py`, `tests/integration/test_api_event_pagination.py`, `tests/integration/test_api_debug_scope.py`, `tests/integration/test_api_stream_resume.py`, `tests/integration/test_api_stream_backpressure.py`, `tests/integration/test_reference_scenario_persistence.py`, `tests/integration/test_v1_api_e2e.py`.
  - Logging: Filter assertions to owned logger names and verify metadata allowlists across success/conflict/recovery/error paths. Never expose DSNs, SQL, payloads, state/evidence, metrics, secrets, or raw exceptions.
  - Dependencies: Tasks 5-19.

- [ ] Task 22: Enforce final architecture gates and complete V1 documentation.
  - Deliverable: Strengthen import-linter/AST/facade/type checks for the evidence composition boundary, simulation authority, recovery, analysis isolation, persistence adapters, API projections, debug contracts, scenario overrides, and truth/metric exclusion from cognition. Ensure no live `WorldEngine` or private state crosses API schemas.
  - Complete the mandatory `/aif-docs` checkpoint. Document metric formulas/evidence stages/unknown handling/library determinism, lifecycle/resume/recovery, REST capabilities/errors, debug security, WebSocket cursors/backpressure, reference scenario, and exact verification commands. Update roadmap/project artifacts only through owner workflows after all gates pass.
  - Files: `pyproject.toml`, `README.md`, `docs/architecture.md`, `docs/configuration.md`, `docs/persistence.md`, `docs/simulation-runner.md`, `docs/experiments.md`, `docs/analysis-metrics.md`, `docs/research-api.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, `tests/architecture/boundary_checker.py`, `tests/architecture/test_import_boundaries.py`, `tests/unit/test_packaging.py`.
  - Logging: Document safe levels and fields; architecture failures may report file/symbol/field/route-template/rule names only. Verify verbosity changes require no code edits.
  - Dependencies: Tasks 1-21 and successful verification.

## Verification

Run focused runner, evidence, and metric gates:

```bash
uv sync --frozen --python 3.12.14
uv run --frozen --python 3.12.14 pytest \
  tests/unit/test_runner_models.py \
  tests/unit/test_runner_serialization.py \
  tests/unit/test_simulation_runner.py \
  tests/unit/test_analysis_contracts.py \
  tests/unit/test_analysis_sources.py \
  tests/unit/test_analysis_serialization.py \
  tests/unit/test_evidence_manifest.py \
  tests/unit/test_truth_specifications.py \
  tests/unit/test_metric_specifications.py \
  tests/unit/test_memory_drift_analysis.py \
  tests/unit/test_objective_metrics.py \
  tests/unit/test_behavior_metrics.py \
  tests/unit/test_belief_metrics.py \
  tests/unit/test_relationship_metrics.py \
  tests/unit/test_network_metrics.py \
  tests/unit/test_social_transmission_analysis.py \
  tests/unit/test_transmission_metrics.py \
  tests/unit/test_metric_determinism.py \
  tests/unit/test_metric_service.py -q
```

Run API, streaming, and reference-scenario gates:

```bash
uv run --frozen --python 3.12.14 pytest \
  tests/unit/test_api_simulation_manager.py \
  tests/unit/test_api_simulation_routes.py \
  tests/unit/test_api_inspection_routes.py \
  tests/unit/test_api_replay_routes.py \
  tests/unit/test_api_streaming.py \
  tests/unit/test_reference_scenario_spec.py \
  tests/unit/test_reference_scenario_e2e.py \
  tests/unit/test_reference_scenario_properties.py -q
```

Run architecture/privacy gates:

```bash
uv run --frozen --python 3.12.14 lint-imports --config pyproject.toml --no-cache --no-logo
uv run --frozen --python 3.12.14 pytest tests/architecture -q
uv run --frozen --python 3.12.14 mypy src tests
```

Run PostgreSQL integration gates against a disposable database:

```bash
PALIMPSEST_TEST_DATABASE_URL=<disposable-palimpsest_test-dsn> \
uv run --frozen --python 3.12.14 pytest -m integration \
  tests/integration/test_migrations.py \
  tests/integration/test_append_only.py \
  tests/integration/test_run_control_repository.py \
  tests/integration/test_runner_finalization_recovery.py \
  tests/integration/test_experiment_repository.py \
  tests/integration/test_analysis_persistence.py \
  tests/integration/test_inspection_pagination.py \
  tests/integration/test_social_transmission_analysis_persistence.py \
  tests/integration/test_metric_persistence.py \
  tests/integration/test_api_simulation_lifecycle.py \
  tests/integration/test_api_event_pagination.py \
  tests/integration/test_api_debug_scope.py \
  tests/integration/test_api_stream_resume.py \
  tests/integration/test_api_stream_backpressure.py \
  tests/integration/test_reference_scenario_persistence.py \
  tests/integration/test_v1_api_e2e.py -q
```

Run repository-wide quality gates:

```bash
uv run --frozen --python 3.12.14 ruff format --check src tests
uv run --frozen --python 3.12.14 ruff check src tests
uv run --frozen --python 3.12.14 mypy src tests
uv run --frozen --python 3.12.14 lint-imports --config pyproject.toml --no-cache --no-logo
uv run --frozen --python 3.12.14 pytest
uv run --frozen --python 3.12.14 pytest tests/unit/test_packaging.py -q
```

## Acceptance Criteria

- NumPy, pandas, SciPy, and NetworkX are integrated with deterministic ordering/seeding rules and used where appropriate for numerical, tabular, statistical, and graph analysis.
- Versioned metrics exist for memory drift, belief accuracy, false-belief persistence, relationship stability, trust network structure, resource inequality, cooperation, conflict, survival, goal completion, knowledge diffusion, rumor distortion, repeated conventions, behavioral specialization, and group/community structure.
- Every metric has an executable definition for populations, denominators, censoring, degenerate cases, evidence stages, numerical policy, and graph projection; outputs identify availability, coverage, algorithm/library versions, and an immutable evidence-manifest revision.
- Objective history, agent-visible projections, direct/communicated memories, reconstructions/reconsolidations, beliefs/testimony, relationships, goals, and action resolutions are never conflated. Claim truth is typed, versioned, durable, and inaccessible to cognition.
- A machine-enforced composition boundary can assemble persistence readers into read-only analysis without relaxing world authority or introducing forbidden `analysis <-> persistence` imports.
- Full simulation configuration, lifecycle, leases, progress, results, action-resolution evidence, goal history, subjective state needed for research, truth specifications, evidence manifests, stream records, and metric documents survive process restart and are queryable deterministically.
- A committed objective tick with interrupted subjective finalization can be rehydrated and completed idempotently without rerunning cognition/provider calls or rewriting objective history.
- FastAPI supports create/configure, start/tick/run/stop, status/list, objective world, event/commit history, agent-visible public state, privileged experimental/debug state, metrics, and replay without violating package or authority boundaries.
- Subjective debug access is disabled by default, explicitly authenticated when enabled, owner/run scoped, paginated, and payload-free in logs.
- WebSocket observers receive ordered resumable progress/events with durable cursors, eventless-tick progress, bounded queues, slow-consumer recovery, and no simulation backpressure or private-state leakage.
- The canonical scenario runs five named agents for at least 48 ticks across connected locations with food/water, day/night, survival needs, communication, reconstructive memory, relationships, imagination, meaningful goals, and death through real runtime/world architecture.
- Tests prove all nine mandatory invariants, deterministic replay for deterministic provider behavior, objective-history immutability, subjective divergence/propagation, metric comparison across evidence classes, and long-run domain invariants.
- No production frontend is introduced.
- Logs remain configurable and metadata-only at every level.
- Ruff, strict mypy, import-linter, architecture/privacy tests, default tests, opt-in PostgreSQL integration tests, migration tests, packaging checks, API/WebSocket tests, and the reference scenario all pass.
- Documentation and owner-managed roadmap/project artifacts identify the verified delivery as V1 complete only after every preceding gate passes.
