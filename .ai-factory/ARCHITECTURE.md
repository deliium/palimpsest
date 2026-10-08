# Architecture: Structured Modules (Technical Layer / Bounded Packages)

## Overview

Palimpsest uses a modular-monolith layout of bounded packages under `src/`. Each package owns a clear responsibility and a public facade (`__init__.py` / `__all__`). This is Structured Modules organized by technical concern at package granularity (world authority, cognition, memory, social, simulation, persistence, analysis), adapted to Python research-simulation needs rather than Controllers/Services folders.

The layout exists to keep trust boundaries machine-checkable: `WorldEngine` is the only objective mutation authority; agents receive immutable observations only; cognition and memory stay owner-scoped and never dereference `WorldEvent` stores; LLM output is shape-validated and non-authoritative; read-only `analysis` may join objective events with subjective evidence after the fact.

## Decision Rationale

- **Project type:** Research / multi-agent society simulation (contracts-first)
- **Tech stack:** Python ≥3.12, FastAPI, SQLAlchemy async, PostgreSQL/pgvector, uv
- **Key factor:** Hard dependency and trust-stage boundaries must be enforceable before and during simulation behavior (import-linter + AST checks)
- **Organization variant:** Technical Layer at package level — adapted to existing bounded packages (not Controllers/Services/Repositories folders)

## Folder Structure

```text
src/
  world/                 # agent-facing Observation/commands/events + communications.py
                         # private _state/_perception/_rules/_operations/_replay (authority)
  agents/                # identity, Agent, goals
  agents/cognition/      # CognitiveLoop, stage protocols, architecture registry, imagination/motivation/deliberation
                         # communication.py (communicated memory + social-message policy)
  memory/                # owner-scoped MemoryTrace, semantic beliefs, recall, formation
  social/                # envelopes + directed relationship profiles (no friend/enemy labels)
  llm/                   # provider-neutral StructuredOutput / LLMResult (no vendor SDKs)
  llm/prompts/           # immutable versioned prompt package resources
  llm/providers/         # OpenAI-compatible HTTP adapter + pure codec
  llm/recording/         # exchange records, safe cache keys, filesystem store, recording provider
  observer/              # read-only presentation: contracts, layouts, frames, semantic events
                         # no tick authority; must not import the engine or private world
  simulation/            # WorldEngine, AgentRuntime, SimulationRunner, codecs, replay
                         # run_control.py (resume modes + finalization-command contracts)
                         # inspection.py (detached objective/agent-visible projection; no live observe)
                         # causal_debugger.py / debugger_lineage.py (read-only research debugger)
  experiments/           # trusted experiment catalog/coordinator (A–Z plus AA–AD; F–AD off the V1 gate); never imported by domain
                         # benchmark_suite.py / benchmark_scenarios/ / benchmark_smoke.py: V2 validation suite (off V1 gate)
                         # observer_graphical_scenario.py: deterministic Godot validation world (off V1 gate)
                         # matrix_*.py: experiment-matrix-v1 expand/batch/aggregate (filesystem manifests)
                         # composition.py maps neutral persistence snapshots → analysis sources
                         # reference_scenario.py: canonical five-agent / 48-tick fixture + milestone arbiter
  research_runner/       # thin CLI composition for matrix batches (forbids api); palimpsest-matrix entry
  persistence/           # SQLAlchemy adapters (simulation, memory, subjective, analysis loaders)
                         # inspection_sqlalchemy.py (keyset pagination + manifest-constrained reads)
                         # may implement experiments.persistence ports; transmission_mapping.py
  analysis/              # read-only analysis: drift/transmission, spatial_control@1,
                         # external_artifact_memory@1, metric DTOs, evidence stages, claim truth,
                         # numerical policy, canonical codecs, phenomenon-indicators-v1 panels,
                         # matrix-metric-summary-v1 (no cognition feedback)
                         # MemoryDriftAnalysisService + SocialTransmissionAnalysisService
                         # historical_memory.py / historical_memory_metrics.py (Assmann layers analysis-only)
  api/                   # FastAPI composition root: /health + /v1 simulation
                         # control/inspection/replay/observer + WebSocket stream
                         # security.py (capability credentials), simulation_manager.py
                         # streaming.py (durable outbox catch-up + live handoff)
                         # research_static.py mounts /research/ before presentation /
                         # research_matrix.py: read-only experiment-matrix-v1 FS allowlist
  infrastructure/        # settings (PALIMPSEST_*), logging, database adapters
clients/godot-observer/  # read-only presentation client; not a Python package; the API serves its prebuilt tree
                         # HTTP GET + observer WebSocket only; no import from src/
clients/research-ui/     # researcher Svelte SPA (not a Python package); built dist served at /research/
                         # graphs/metrics/matrix/traces; HTTP to /v1 only; no import from src/
alembic/versions/        # migrations through 0017 (memory HNSW; 0016 event indexes; 0015 branch lineage; 0013 cognition-trace)
                         # V2/V3 capability flags stay runner JSON only (not Alembic columns; no 0018 in V3 scaffolding)
docs/                    # contributor docs (architecture, memory, social-communication, …)
tests/
  unit/ architecture/ integration/ compose/ typecheck/ fakes/
```

## Dependency Rules

- ✅ `world` imports no other bounded module (structured communication lives in `world.communications`)
- ✅ Base `agents` may import agent-facing `world` only; never `agents.cognition`
- ✅ `memory` / `social` may import `world` + `agents`; remain independent of each other
- ✅ `llm` imports no domain, simulation, API, persistence, or infrastructure module
- ✅ `llm` uses stdlib `logging` only (metadata allowlist; no `exc_info` / structlog / payload fields)
- ✅ `agents.cognition` may import public contracts from agents/world/memory/social/llm
- ✅ `simulation` may import domain public contracts; must not import `api`, `analysis`, `experiments`, `infrastructure`, `persistence`, or `observer`
- ✅ `observer` may import public `world` and detached simulation facts; must not import `simulation.engine`, private `world._*` modules, `api`, `persistence`, or frameworks
- ✅ Simulation owns immutable `EvidenceManifest` high-water marks (counts/hashes only — never truth payloads)
- ✅ `experiments` may import public `simulation`, read-only `analysis`, and `memory` contracts; must not import `api`, `infrastructure`, or concrete SQLAlchemy/`persistence`
- ✅ `research_runner` may import `experiments`, `simulation`, `persistence`, `infrastructure`, and `analysis`; must not import `api` or start an HTTP server
- ✅ `experiments.composition` is the legal outer composition boundary that maps neutral detached persistence rows into analysis sources; persistence adapters implement `experiments.persistence` ports only
- ✅ `persistence` may import public `simulation` contracts, public `memory` and `social` facades, `infrastructure`, and `experiments.persistence` ports only
- ✅ `persistence` identity types for subjective/transmission mapping come from `memory.models` (re-exported `EntityId`) — never import `world` from persistence
- ✅ `api` may import `simulation`, `infrastructure`, `persistence`, and `observer`
- ✅ `analysis` is read-only; may import `world`, `simulation`, and `memory` contracts (not live infra/agents/persistence)
- ✅ `infrastructure` imports no domain policy
- ❌ `analysis` and `persistence` must not import each other
- ❌ `api` must not import `analysis`
- ❌ Domain packages must not import `infrastructure`, FastAPI, or ORM stacks
- ❌ `world`, `agents`, `agents.cognition`, `memory`, and `social` must not import `experiments`
- ❌ Non-simulation packages must not import private `world._*` authority modules
- ❌ Only `simulation.engine` / `simulation.bootstrap` and private `world._*` may import world authority internals
- ❌ Only `infrastructure` and `persistence` may import SQLAlchemy/Alembic/asyncpg
- ❌ Vendor LLM SDKs (`openai`, `anthropic`, …) are forbidden everywhere in `src/`
- ❌ Cross-module imports of private modules or transitive re-exports
- ❌ Agents, cognition, memory, reconstruction protocols, and runtime composition must not import, receive, or dereference `WorldEvent`, event repositories, replay services, snapshots, or private world state (opaque `EventId` only)
- ❌ Cognition must not feed analysis results back into live planning or memory formation
- ❌ Experiment collectors, truth specifications, and objective snapshots must never flow into cognition, memory formation, prompts, or action selection
- ❌ `src/` must not import `clients/godot-observer` or `clients/research-ui` (or contain those client package paths). The API serves prebuilt trees and still does not import the clients
- ❌ `api` must not import `analysis` when serving Research UI matrix FS JSON (allowlisted files only; no batch starts)

## Layer/Module Communication

- Composition root (`api`) loads settings, configures logging, owns database lifespan, recoverable `SimulationManager`, and resumable stream fan-out
- Research API capabilities: `simulation_control`, `objective_inspection` (incl. WebSocket stream), `agent_visible`, `subjective_debug` (disabled by default); credentials via header / WS subprotocol only — never query strings
- LLM settings exist under `PALIMPSEST_LLM_*`; factory construction stays standalone in `llm.factory` until a cognition consumer owns lifecycle composition
- `WorldEngine` owns observation tokens, ordered admission, private batch preparation, and atomic commit
- Communication (`Talk` / `Ask` / `Tell`) is event-only: world verifies delivery eligibility and records `Talked` / `Asked` / `Told`; content truth is never world-owned. Declared lineage on `StructuredUtterance` is speaker testimony. Writes use event schema **replay-v5**; legacy replay-v2/v3/v4 text-only records decode into an explicit unreferenced structured form. WorldEngine-owned information artifacts are a separate physical channel (replay-v8 / codec `v5` when active); objective marks never download meaning into memory

- Private communication eligibility policy (living sender/recipient, colocation/range, visibility) is shared by admission and perception; delivery is recipient-private on the next observation window
- `AgentRuntime` owns per-agent cognition invocation, deferred subjective commits (episodic + beliefs + relationships) via `SubjectiveStateService`, and `ActionSubmission` construction from an engine-issued token; cognition never sees `TickToken` or `WorldState`
- Communicated observations become **fresh** owner-scoped `MemoryTrace` values with `CommunicatedTransmissionMeta` (never copy sender memory/reconstruction/belief/relationship state). `DeterministicSocialMessagePolicy` selects talk/ask/tell from subjective evidence; belief-grounded `Tell` requires explicit selected belief IDs (bare `COMMUNICATE` does not auto-testify)
- Trust-aware belief updates treat testimony as evidence (`accept` / `discount` / `contradict` / `defer`); cognition projects relationship trust into neutral floats so `memory` stays independent of `social`
- Owner-scoped episodic memory uses structured `MemoryTrace` values and reconstructive `MemoryService.recall`; durable adapter is `persistence.create_memory_service(scope=..., ...)`; semantic beliefs and directed relationships use `persistence.create_subjective_state_service(...)`; subjective tables (`0005`–`0008`) stay outside append-only authoritative history
- Emergent `SelfModel` is a deterministic projection over owner-relevant semantic beliefs — no predefined personality traits, archetypes, or role classes
- Directed relationship profiles are independent `source → target` assessments across fixed low-level dimensions; no friend/enemy/leader/group/morality/culture/rumor labels
- Private `PerceptionService` projects one agent-specific `Observation` from tick-start state + prior committed events; cognition receives it only via `observation_for` / `AgentRuntime` / `build_perspective`
- Async `LLMProvider.generate(LLMRequest[T]) -> LLMResult[T]` returns only strict `StructuredOutput` plus normalized metadata; raw provider text/mappings never leave the adapter
- Structurally valid LLM output remains non-authoritative. Cognition must translate an exact decision schema into a fresh `AgentCommand`, then use normal `ActionSubmission` / admission / world-operation gates
- Analysis consumes immutable exports/events and may join subjective reconstruction **and** communicated-transmission evidence after the fact (`MemoryDriftAnalysisService`, `SocialTransmissionAnalysisService`); it never feeds objective events or analysis reports into agents, memory, or reconstructors

## Key Principles

1. World state is authoritative; agents receive immutable, agent-specific observations only
2. Objective and subjective state remain separate; perception does not form memories or beliefs; reconstruction and testimony evaluation are explicitly subjective
3. A delivered utterance proves delivery, not truth; declared lineage is distrustable testimony
4. Randomness and IDs derive from an explicit seed (no Python `hash()`, no global RNG)
5. Operational metadata (HTTP request IDs, log timestamps) never become domain IDs or seeds
6. Enforce boundaries with import-linter + AST checks, not convention alone
7. LLM validation proves shape only—never truth, policy, actor identity, or world authority
8. Logs expose IDs, counts, hops, confidence bands, and reason codes — never message text, propositions, narratives, prompts, or fingerprints as payload surrogates

## Code Organization Note

- **New Features:** Follow the bounded-package rules and facades in this document and `docs/architecture.md` where practical
- **Existing Code:** Document the current structure as-is (including reconstructive memory and social transmission). When modifying existing code, prefer these conventions without forcing unrelated rewrites
- **Interoperability:** Wire infrastructure only at the API/composition boundary; do not allocate LLM providers in API lifespan until cognition consumers own them
- **Domain-contract evolution:** Observation, closed `AgentCommand` (29 variants including `Feed`/`Transport` plus durable `CopyRecord`/`AnnotateRecord`/`DamageRecord`), and `world.communications` follow accepted-set discipline (see `docs/architecture.md`). Channel-off Observation wire stays unchanged; channel-on adds closed optional `lifecycle` on `ObservedSelf` / `VisibleBody` (`chronological_age`, `stage`, `dependency_status` only); dependency-care may add optional need-deficit summaries when `perception_mode=self_and_colocated`. Mid-run roster, kinship-visible, and dependency-need facts still require versioned seams + live/restored observation parity. Version taxonomy: `simulation.compatibility`
- **V2 extension seams:** Later plans plug into CognitiveLoop stage protocols, `AgentCognitionSpec` modes, run-level `V2CapabilityFlags` (default-off = V1 wiring; **owned** flags `advanced_social_inference`, `predictive_world_model`, `extended_self_model`, and `short_term_emotional_state` may enable; `multi_hop_testimony_tracking` still fails closed with `capability_unimplemented`), optional `CognitionTraceSpec` / Alembic `0013` (default-off; non-authoritative; observational debugger HTTP under `subjective_debug` — see `docs/research-causal-debugger.md`), research branch lineage on Alembic `0015` (`simulation_branches`, control-plane only; no new capability flag), `AgentRuntime` subjective finalization, observe-only perception, event-only communication eligibility, `experiments.catalog` arms (A–E on the V1 gate; Experiments F–Z and AA–AE stay off that gate), analysis-only evidence stages, and API/`llm.factory` LLM lifecycle composition (not a runner flag). `extended_self_model` is history-derived revisable self-beliefs, not a person class or a second belief store. `advanced_social_inference` is an owner-scoped first-order mind plus a flat epistemic ledger (`max_depth` default 2, hard cap 3). Judgments are new, already known, secret, uncertain, or contradictory; secret is not a stored attitude. One agent does not receive another's private cognition, and `theory_of_mind@1` is analysis-only. Experiment M stays off the V1 regression gate. `CommunicationStrategyMode` defaults to `DISABLED` and is not a capability flag. `runner-config-v9` carries every `runner-config-v8` cognition key plus `communication_strategy_mode` and is emitted only when that mode is `DETERMINISTIC`. `communication_strategy@1` is analysis-only and assigns `memory_error` only when `cited_event_id` names a committed occurrence whose public tokens do not cover the source tokens. Experiments N, O, and P stay off the V1 regression gate. `ReputationMode` defaults to `DISABLED` and is not a capability flag. `runner-config-v10` carries every `runner-config-v9` cognition key plus `reputation_mode` and is emitted only when that mode is `DETERMINISTIC`. `distributed_reputation@1` is analysis-only. Experiment Q stays off the V1 regression gate. `SkillLearningMode` defaults to `DISABLED` and is not a capability flag. `runner-config-v11` carries every `runner-config-v10` cognition key plus `skill_learning_mode` and the locked rate keys, and is emitted only when that mode is `DETERMINISTIC`. `skill_learning@1` is analysis-only. Experiment R stays off the V1 regression gate. `TeachingInteractionMode` defaults to `DISABLED` and is not a capability flag. `runner-config-v12` carries every `runner-config-v11` cognition key plus `teaching_interaction_mode` and the locked teaching weights, and is emitted only when that mode is `DETERMINISTIC`. `cultural_transmission@1` is analysis-only. Experiments S and T stay off the V1 regression gate. `TerritorialClaimMode` defaults to `DISABLED` and is not a capability flag. `runner-config-v15` is emitted only when some agent's mode is `DETERMINISTIC`. Experiment V and `spatial_control@1` stay off the V1 regression gate. The metric is analysis-only and is not an input to cognition. `ArtifactInterpretationMode` defaults to `DISABLED` and is not a capability flag. `runner-config-v19` is emitted only when some agent's mode is `DETERMINISTIC`. Replay-v8 / codec `v5` write only when artifacts are active at run start; default event write stays replay-v5. Experiment Z and `external_artifact_memory@1` stay off the V1 regression gate. Closed `AgentCommand` count is 29 (`Feed`/`Transport` with dependency care; `CopyRecord`/`AnnotateRecord`/`DamageRecord` with durable records). `v1_regression_profile` is unchanged. `multi_hop_testimony_tracking` remains unowned. Off-limits: WorldEngine admission, event immutability, Observation trust boundaries. See `docs/architecture.md` and `docs/cognition-runtime.md`.
- **Downstream V2 plan contract:** Every later V2 feature plan must keep V1 invariants, opt-in fail-closed flags, V1 regression gate green (flags-off and tracing-off), accepted-set + exact key-set schema bumps, no scripted emergence, no LLM→world shortcuts, reproducible experiments, and optional tracing outside the objective fold. Checklist: `docs/architecture.md` (Downstream V2 plan contract). Roadmap milestones via `/aif-roadmap` only.
- **V3 extension seams:** Closed `V3CapabilityFlags` on `runner-config-v23`+ (sibling `v3_capability_flags`; default-off = V2 wiring). **Owned by v3-02–v3-08:** `generational_population` on `runner-config-v24|…|v35` with `population_lifecycle`, `admit_population_entry`, lifecycle events (replay-v9 / codec v6), Observation `lifecycle` object, Experiments AE–AK; v3-06 `dependency_care` on **v28+**; v3-07 `developmental_learning` on **v29+**; v3-08 `mentorship` on **v30+** (never internal-state copy). **Owned by v3-05:** `kinship_inheritance` on `runner-config-v27|…|v35` with exact `kinship`, objective parent→child graph (`world.kinship`), `KinshipEdgeRecorded` (replay-v11 / codec v8), Experiment AH — never auto-writes social valence; kinship-only forbids lifecycle siblings but may co-exist with cultural on v31–v35. **Owned by v3-09 (deepened by v3-10/v3-11/v3-12/v3-13/v3-14):** `cultural_historical_memory` on **`runner-config-v31|…|v36`** with exact `cultural_feature_provenance`, owner-scoped `agents.cognition.cultural_features` (`SubjectiveCulturalBelief`) vs analysis-only `AnalyticalCulturalTrait`, Experiment AL — no global Culture controller; kinship cultural inheritance handoff still deferred. v3-10 adds sibling `historical_memory_layers` on **v32** (optional on v33–v35; analysis-only Assmann layers + Experiment AM — never cognition/Observation). v3-11 adds sibling `durable_records` on **`{v33..v35}`** (no new flag; physical genres/lineage/imperfect copy; write-pair replay-v13/codec v10; Experiment AN; marks ≠ truth). v3-12 adds sibling `knowledge_repositories` on **`{v34,v35}`** (requires durable + provenance; no new flag; no LibraryInstitution; write-pair replay-v14/codec v11; Experiment AO; cultural archive/library labels subjective only). v3-13 adds sibling `knowledge_genealogy` on **v35** (requires provenance; no new flag; no write-pair; owner-scoped practical-knowledge DAG + analysis queries; Experiment AP; triple representation; no `GlobalTechniqueRegistry`). v3-14 adds `bounded_experimentation` on **v36** with no new flag. Closed `AgentCommand` count is **35** (`Experiment`). SEMANTIC observer types are **54** (`EXPERIMENT_RESOLVED`). Protocol id stays `observer-protocol-v1`. Unowned V3 flags still fail closed at `from_config`. Pins: `prepare_parallel=False`; no scripted civilization helpers; no Alembic `0018` by default. See `docs/architecture.md` (V3 extension seams + Downstream V3 plan contract). Milestone: **M7 — V3 Generational Civilization** in `.ai-factory/ROADMAP.md`.

## Code Examples

### Public facade import

```python
from simulation import (
    ActionSubmission,
    SimulationRunConfig,
    WorldBootstrap,
    WorldEngine,
    build_perspective,
)
from world import Observation, Talk, Tell, Wait
from world.communications import origin_utterance, retell_utterance
from llm import LLMProvider, LLMRequest, LLMResult, StructuredOutput
from memory import MemoryRecallRequest, MemoryService, DeterministicMemoryReconstructor
from analysis import MemoryDriftAnalysisService, SocialTransmissionAnalysisService
from agents.cognition import DeterministicSocialMessagePolicy
```

### Forbidden authority import outside simulation

```python
# Not allowed from agents/memory/api/analysis/llm:
from world._state import WorldState  # private authority
from world._perception import PerceptionService  # private projector
```

### Forbidden objective events in subjective paths

```python
# Not allowed — reconstructors, MemoryService, and cognition never take WorldEvent:
reconstructor.reconstruct(world_event)  # no such API
MemoryRecallRequest(..., world_event=...)  # does not exist
# SocialTransmissionAnalysisService may join events only under analysis/
```

### Forbidden persistence → world import

```python
# Not allowed in persistence adapters:
from world.identifiers import EntityId
# Use the memory facade re-export instead:
from memory.models import EntityId, CommunicatedTransmissionMeta
```

### Forbidden LLM trust bypass

```python
# Not allowed — no direct conversion; cognition translation is a separate stage:
require_agent_command(llm_result)           # TypeError
require_action_submission(structured_output)  # TypeError
llm_result.to_agent_command()               # does not exist
```

## Anti-Patterns

- Passing `LLMResult` / `StructuredOutput` / model dumps into `WorldEngine`, `ActionSubmission`, admission, or world operations
- Treating `ActionRequest` as authoritative without private world validation
- Handing an all-agent `ObservationBatch` or another agent's observation to cognition
- Sharing mutable memory payloads across agents, or copying sender `MemoryTrace` / reconstruction IDs into a listener's lineage
- Treating delivered `Tell` content or declared source chains as world-verified truth
- Auto-upgrading bare `COMMUNICATE` to belief-grounded `Tell` without explicit selected belief IDs
- Equating repeated reports that share one transmission root with independent corroboration
- Injecting `WorldEvent` or event repositories into agents, cognition, `MemoryService`, or reconstruction policies
- Feeding `SocialTransmissionAnalysisService` / drift reports back into live cognition
- Treating reconstructions as objective truth or correcting agents against ground truth during recall
- Destructively overwriting source traces when reconsolidating
- Reading `PALIMPSEST_` secrets or opening DB connections at import time
- Importing vendor LLM SDKs or logging prompt/output/schema/endpoint/memory/narrative/communication content
- Using Docker/PostgreSQL inside default unit tests

## See Also

- `docs/architecture.md` — contributor-facing matrix, WorldEngine lifecycle, perception boundary, and invariants
- `docs/memory-reconstruction.md` — reconstructive recall, reconsolidation, drift analysis, logging allowlists
- `docs/social-communication.md` — objective delivery vs declared testimony vs owner-scoped derivation vs analysis
- `.ai-factory/plans/v1-agent-social-communication-transmission.md` — social communication and transmission plan
- `.ai-factory/plans/v1-reconstructive-memory-reconsolidation.md` — reconstructive memory plan
- `.ai-factory/plans/v1-agent-runtime-cognitive-loop.md` — cognitive loop and AgentRuntime plan
- `.ai-factory/plans/v1-llm-provider-abstraction.md` — provider-neutral LLM boundary plan
- `.ai-factory/plans/v1-perception-observation-system.md` — perception plan
