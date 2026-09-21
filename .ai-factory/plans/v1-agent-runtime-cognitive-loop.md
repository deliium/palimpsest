# Implementation Plan: V1 Agent Runtime and Cognitive Loop

Branch: main (no new branch)
Created: 2026-09-21

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M3 - Cognition and Providers"
Rationale: This plan delivers the first concrete cognition orchestration and runtime layer on top of the completed observation, command, WorldEngine, and provider-neutral LLM boundaries.

## Scope

Implement an explicit, async-capable Python cognitive pipeline and a per-agent runtime lifecycle without LangGraph or another graph/orchestration framework. Cognition receives one immutable, agent-specific `Observation` plus agent-owned internal state, never `WorldState`, engine snapshots, tick capabilities, repositories, or mutation authority. The loop returns exactly one fresh, closed `AgentCommand`; only simulation-layer runtime code may bind that command to an engine-issued `ActionSubmission`.

The V1 pipeline order is:

```text
Observation
-> perception interpretation
-> memory retrieval
-> situation model
-> beliefs/self state
-> possible futures
-> motivation evaluation
-> intention selection
-> planning
-> one structured AgentCommand
```

Each boundary produces a typed, immutable artifact and a structured boundary record containing the component identity/version, typed input and output artifacts, confidence, status, and decision metadata. These records capture inspectable claims and choices for scientific analysis, not hidden reasoning, prompts, raw model responses, or private chain-of-thought. Operational logs use metadata-only projections and never serialize observation, memory, belief, communication, prompt, or artifact payloads.

V1 includes deterministic placeholder memory retrieval and future-imagination components, plus deterministic fakes for all boundaries. Production LLM-backed cognition, durable cognition-artifact persistence, general M4 analysis metrics, concurrent agent execution, and changes to `WorldEngine` authority or admission rules remain out of scope.

## Design Decisions

- Keep the existing synchronous `CognitionStrategy` contract intact; introduce an async `CognitiveLoop` alongside it so later LLM-backed stages can use `LLMProvider.generate()` without blocking adapters or a breaking migration.
- Put cognition contracts and orchestration under `src/agents/cognition/`; this package may use public `agents`, `world`, `memory`, `social`, and `llm` contracts but may not import `simulation`, private `world._*`, persistence, infrastructure, API, or analysis.
- Put `AgentRuntime` under `src/simulation/`; it is the trusted composition boundary that owns lifecycle state, builds the existing `Perspective`, invokes cognition, applies agent-owned memory hooks, and constructs `ActionSubmission` with a token supplied by orchestration.
- Keep submission resolution in `WorldEngine.resolve_tick()`. `AgentRuntime` must not call private admission or world-operation functions, and the cognitive loop must never see a `TickToken`.
- Treat a dead self in the current committed `Observation` as terminal for that runtime. Terminal runtimes do not invoke cognition or submit actions; engine/run termination when all agents are dead remains caller policy.
- Apply memory updates only after successful cognition. Updates describe the committed observation and internal decision process, not an uncommitted action outcome; outcome memories must wait for a later observation.
- Return scientific artifacts in memory through public immutable result types. Persistence and query APIs are deferred, avoiding an unrequested schema/migration expansion.
- Execute agents and pipeline components sequentially in V1. Preserve explicit deterministic invocation/stage ordinals so later concurrency cannot change artifact ordering or identity semantics.

## Commit Plan
- **Commit 1** (after tasks 1-3): `feat(cognition): add explicit cognitive pipeline`
- **Commit 2** (after tasks 4-6): `feat(simulation): add agent runtime lifecycle`
- **Commit 3** (after tasks 7-8): `docs: document agent runtime and cognition boundaries`

## Tasks

### Phase 1: Cognition Contracts and Orchestration

- [x] Task 1: Define immutable cognitive inputs, stage outputs, and scientific boundary artifacts.
  - Create `src/agents/cognition/models.py` with frozen, slotted, defensively detached values for interpreted perception, retrieved memory references/context, situation model, self/belief state, possible futures, motivation scores, selected intention, action plan, internal agent state, confidence, decision metadata, and the final loop result.
  - Model confidence with validated finite values in `[0, 1]`; use closed enums/codes for component kind, status, and failure reason rather than arbitrary strings.
  - Define a versioned `ComponentBoundaryRecord` that identifies the invocation, component, component version, deterministic ordinal, typed input artifact, typed output artifact, confidence, and metadata. Exclude raw prompts, raw provider responses, hidden rationale/chain-of-thought, credentials, endpoints, and arbitrary exception text.
  - Ensure the final result contains exactly one value accepted by `world.require_agent_command`, ordered boundary records, and explicit memory-update intents; do not embed `WorldState`, `ObservationBatch`, `TickToken`, `ActionSubmission`, or repositories in any cognition model.
  - Update `src/agents/cognition/__init__.py` to export only intended public contracts and values, preserving the rule that base `agents` does not re-export cognition.
  - Add model validation, immutability, defensive-copy, confidence, exact-type, and safe-`repr` tests in `tests/unit/test_cognition_models.py`.
  - Logging requirements: keep domain models log-free; provide an explicit metadata-only diagnostic projection for the trusted runtime, and test that representations/projections contain no observation, memory, belief, communication, prompt, or decision payload content. Failures use stable codes suitable for WARN/ERROR logs.
  - Dependencies: none.

- [x] Task 2: Define independently replaceable component protocols for every cognitive stage.
  - Extend `src/agents/cognition/contracts.py` with narrow protocols for perception interpretation, memory retrieval, situation modeling, beliefs/self-state projection, future imagination, motivation evaluation, intention selection, planning/action selection, and memory update hooks.
  - Give each protocol one typed input and one typed output from Task 1. Component calls may be async so pure deterministic stages and future LLM-backed stages remain substitutable without changing orchestration.
  - Define a loop input that contains one `Observation`, the owning `AgentId`, and immutable internal state only. Keep the existing `Perspective` and synchronous `CognitionStrategy` behavior compatible; add an adapter contract only if needed to host existing deterministic strategies.
  - Make ownership and exact-type validation fail closed at every boundary. Memory retrieval remains read-only; update hooks return intents rather than receiving mutable stores.
  - Add positive typing coverage in `tests/typecheck/cognitive_loop.py`, negative fixtures under `tests/typecheck/invalid/`, and extend `tests/unit/test_v1_typing.py` to prove that `WorldState`, `ObservationBatch`, engine tokens, writers, repositories, `LLMResult`, and mappings cannot substitute for cognition inputs or commands.
  - Logging requirements: component protocols do not accept loggers and do not prescribe payload logging. Contract errors expose component name, ordinal, and closed reason code only; the runtime may log those at ERROR without exception text or component payloads.
  - Dependencies: Task 1.

- [x] Task 3: Implement the explicit `CognitiveLoop` sequence and boundary recording.
  - Create `src/agents/cognition/loop.py` with constructor-injected components and straightforward Python control flow in the exact required order; do not add LangGraph, LangChain, a generic DAG engine, dynamic plugin discovery, or hidden callbacks.
  - Validate each component's exact output before passing it onward, append one boundary record per completed component, and stop deterministically on cancellation or failure without returning a partial command.
  - Require the final planner/action selector to construct a fresh closed `AgentCommand`, then call `require_agent_command` at runtime before returning it. Never deserialize provider output directly into a command.
  - Keep prior completed boundary records available in a typed failure result or exception-safe receipt without including private model reasoning. Define whether confidence is component-supplied and how aggregate/final confidence is represented without inventing unsupported statistical meaning.
  - Add `tests/unit/test_cognitive_loop.py` covering exact order, one-call-per-stage behavior, input/output propagation, component replacement, exact one-action output, wrong-type rejection, failure/cancellation short-circuiting, deterministic artifacts, and absence of world authority.
  - Logging requirements: `CognitiveLoop` emits no payload logs. If it emits operational records, use DEBUG for component start/completion with invocation ID, component/version, ordinal, status, confidence, and counts only; use ERROR with a stable failure code and no `exc_info`, raw exception text, or artifact body.
  - Dependencies: Tasks 1 and 2.

### Phase 2: Deterministic Baseline and Runtime Lifecycle

- [x] Task 4: Add deterministic placeholder components and reusable cognition fakes.
  - Create `src/agents/cognition/defaults.py` with minimal deterministic V1 implementations: literal observation interpretation, owner-scoped pass-through or empty memory retrieval, direct situation/self-state construction, bounded placeholder future generation, stable motivation/intention selection, and a safe `Wait` fallback planner.
  - Keep placeholder behavior explicit and replaceable; do not pretend empty retrieval or simple futures are production memory/imagination quality, and do not import or invoke a real LLM.
  - Create `tests/fakes/cognition.py` and update `tests/fakes/__init__.py` with scriptable per-stage fakes keyed by deterministic invocation/stage ordinals, typed outcomes/failures, defensive copies, and metadata-only call records.
  - Add `tests/unit/test_cognition_defaults.py` for deterministic same-input results, ownership isolation, stable ordering/tie-breaking, replaceability, and valid command construction. Extend fake tests to prove no full observation, memory, prompt, or output payload is retained in call history.
  - Logging requirements: defaults stay log-free and deterministic. Fakes may record component name, invocation ID, ordinal, status, and counts for assertions, but never payload bodies; harness failures expose stable safe codes.
  - Dependencies: Tasks 1-3.

- [x] Task 5: Implement the per-agent `AgentRuntime` lifecycle and memory update hooks.
  - Create `src/simulation/agent_runtime.py` with explicit runtime states such as created, active, and terminal, plus immutable step/submission results. Inject the owning `Agent`, identity translator, `CognitiveLoop`, memory/belief readers and writers or a narrow subjective-state adapter, inbox source, and deterministic invocation-ID source through public contracts.
  - Implement alive-agent start, processing of exactly one own `Observation`, existing `build_perspective` ownership checks where needed, cognition invocation, post-cognition memory update hooks, exact command validation, and construction of one `ActionSubmission` from a caller-supplied engine token.
  - Keep the token and submission machinery outside `CognitiveLoop`; the loop receives only its observation/internal state input. Do not expose `WorldEngine`, `WorldState`, private world modules, action admission, proposal IDs, revisions, or another agent's observation to cognition.
  - Define fail-closed lifecycle behavior: start is idempotent or explicitly rejects repeats; processing before start fails; duplicate processing of the same observation/invocation cannot double-apply updates; cognition failure produces no submission or memory mutation; a dead self observation transitions once to terminal; terminal processing never invokes cognition or submits an action.
  - Prevalidate all returned memory/belief update intents for owner and exact type before applying any update. Preserve deterministic update order and avoid recording proposed-action success before it is observed in a later committed tick.
  - Export the runtime and public result/status types from `src/simulation/__init__.py` without exporting internal update helpers or private world authority.
  - Add `tests/unit/test_agent_runtime.py` for lifecycle transitions, ownership rejection, one-action submission, exact token binding, update timing/atomicity, duplicate calls, failures, cancellation, and terminal death behavior.
  - Logging requirements: use metadata-only DEBUG logs for lifecycle transitions and component invocation boundaries, INFO for runtime start and terminal transition, WARN for rejected duplicate/invalid lifecycle calls, and ERROR for closed failure codes. Include run/agent/tick/invocation/component/status/count metadata only; never log observations, memories, beliefs, inbox/communications, cognitive artifacts, prompts, command payloads, seeds, credentials, or raw exceptions.
  - Dependencies: Tasks 1-4.

- [x] Task 6: Integrate `AgentRuntime` with `WorldEngine` through normal observation and admission paths.
  - Add `tests/integration/test_agent_runtime_world_engine.py` using an in-memory bootstrapped `WorldEngine`, deterministic IDs/clocks, placeholder or fake cognitive components, and no real LLM, network, Docker, or PostgreSQL dependency.
  - Exercise `engine.observe()` / `engine.observation_for(agent_id)` -> runtime processing -> exact `ActionSubmission` -> `engine.resolve_tick()` for one and multiple agents in registration order.
  - Prove each runtime sees only its own observation and state, generated commands follow the existing exact-class trust boundary, and engine admission still derives actor/request/world/revision authority rather than accepting it from cognition.
  - Cover a non-`Wait` fake command, autonomous world progression, cognition failure policy, stale/wrong token rejection, cross-agent observation rejection, death during tick N becoming terminal at observation N+1, omission of terminal-agent submissions, and all-terminal caller behavior without adding an engine terminal phase.
  - Add or extend `tests/unit/test_llm_trust_boundary.py` and `tests/unit/test_world_agent_contracts.py` to prove `LLMResult`, `StructuredOutput`, cognitive artifacts, mappings, and command subclasses cannot cross directly into `ActionSubmission` or world admission.
  - Logging requirements: assert runtime/engine integration logs expose correlation and lifecycle metadata only. Test that DEBUG/INFO/WARN/ERROR events do not contain observation, internal-state, artifact, memory, communication, prompt, provider-output, or command payload values.
  - Dependencies: Tasks 3-5.

### Phase 3: Enforcement, Verification, and Documentation

- [x] Task 7: Strengthen architecture, privacy, and deterministic behavior gates for cognition/runtime.
  - Add `tests/architecture/test_cognitive_loop_isolation.py` and extend `tests/architecture/test_world_authority.py`, `tests/architecture/test_import_boundaries.py`, `tests/architecture/test_llm_provider_isolation.py`, and `tests/architecture/boundary_checker.py` only where needed.
  - Enforce that cognition imports no simulation/infrastructure/persistence/API/analysis or private world authority; stage signatures omit world state, engine/tick authority, repositories, and mutable writers; no generic mapping or `LLMResult` conversion helper can produce commands; and only trusted simulation code constructs submissions.
  - Enforce metadata-only logging and artifact schemas: no chain-of-thought/rationale field, raw prompt/output, credentials, endpoint, arbitrary exception, full observation, memory/belief content, or communication body in diagnostics.
  - Add deterministic/property tests, using Hypothesis where practical, for same-input stage ordering, confidence validation, owner isolation, update all-or-nothing behavior, and terminal idempotence. Preserve existing import-linter boundaries unless a narrower check is required; do not loosen package dependencies for convenience.
  - Run targeted and full quality gates: `ruff format --check`, `ruff check`, strict `mypy`, `lint-imports`, architecture tests, cognition/runtime unit tests, the new WorldEngine integration test, default `pytest`, and packaging tests.
  - Logging requirements: test all configured log levels and `PALIMPSEST_LOG_LEVEL` control. Architecture and privacy failures should identify only file/symbol/field names; they must not print captured sensitive values.
  - Dependencies: Tasks 1-6.

- [x] Task 8: Document the V1 cognitive pipeline, runtime lifecycle, and extension boundaries.
  - Update `README.md`, `docs/architecture.md`, `docs/llm-providers.md`, and `docs/development.md` with the explicit stage sequence, async replacement model, runtime/engine trust boundary, typed action flow, memory-hook timing, death/terminal semantics, scientific artifact policy, deterministic fake usage, and exact test commands.
  - Update `.ai-factory/DESCRIPTION.md` and `.ai-factory/ARCHITECTURE.md` through the mandatory `/aif-docs` checkpoint so they no longer describe cognition/runtime composition as wholly deferred. Update `.ai-factory/ROADMAP.md` through its owner workflow only after implementation and verification establish the delivered M3 scope.
  - State clearly that V1 placeholders are not production memory/imagination, no real LLM is required by tests, cognitive artifacts are returned but not durably persisted, hidden chain-of-thought is neither requested nor stored, and all world mutation remains in `WorldEngine`.
  - Logging requirements: document metadata fields, DEBUG/INFO/WARN/ERROR event meanings, `PALIMPSEST_LOG_LEVEL`, and the prohibited payload list. Include a safe example that contains IDs/codes/counts only and no observations, memories, beliefs, communications, prompts, outputs, command arguments, seeds, or credentials.
  - Dependencies: Tasks 1-7.

## Verification

Run the targeted gates first:

```bash
uv run --frozen --python 3.12.14 pytest \
  tests/unit/test_cognition_models.py \
  tests/unit/test_cognitive_loop.py \
  tests/unit/test_cognition_defaults.py \
  tests/unit/test_agent_runtime.py \
  tests/unit/test_llm_trust_boundary.py \
  tests/unit/test_world_agent_contracts.py \
  tests/architecture/test_cognitive_loop_isolation.py \
  tests/unit/test_v1_typing.py -q
uv run --frozen --python 3.12.14 pytest \
  -m integration tests/integration/test_agent_runtime_world_engine.py -q
```

Then run repository-wide checks:

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

- `CognitiveLoop` uses explicit Python sequencing for all required stages and every component is replaceable through a narrow typed protocol.
- Cognition receives exactly one agent-owned `Observation` plus immutable internal state and cannot import, accept, inspect, or mutate `WorldState`.
- Every successful loop invocation returns exactly one fresh member of the closed `AgentCommand` union and cannot return provider output, mappings, subclasses, or authority-bearing submission/request values.
- Every component boundary yields a versioned structured record with typed inputs/outputs, confidence, status, and decision metadata, without storing or requiring private chain-of-thought.
- Placeholder memory retrieval and imagination work deterministically and can be replaced independently; all tests run without a real LLM.
- `AgentRuntime` covers start, observation processing, cognition, action submission construction, memory hooks, and terminal-on-death behavior with fail-closed lifecycle transitions.
- Integration tests prove the runtime uses normal `WorldEngine` observation, submission, admission, resolution, and death paths without bypassing authority boundaries.
- Logs and diagnostic projections remain metadata-only and secret-safe at every configured level.
- Existing unit, architecture, typing, import, packaging, determinism, and WorldEngine tests continue to pass.
