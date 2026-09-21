# Cognition and agent runtime

[← Previous Page](architecture.md) · [Back to README](../README.md) · [Next Page →](llm-providers.md)

V1 adds an explicit async cognitive pipeline and a per-agent runtime on top of observation, command, `WorldEngine`, and provider-neutral LLM boundaries. World mutation remains exclusively in `WorldEngine`.

## Pipeline

```text
Observation
→ perception interpretation
→ memory retrieval
→ situation model
→ beliefs/self state
→ possible futures
→ motivation evaluation
→ intention selection
→ planning
→ one structured AgentCommand
```

Each stage is a narrow async protocol under `agents.cognition`. Components are constructor-injected into `CognitiveLoop` with plain Python control flow (no LangGraph/LangChain/DAG engine). Every completed stage appends a versioned `ComponentBoundaryRecord` (typed I/O artifacts, confidence, status, decision metadata). Records are scientific receipts — not chain-of-thought, prompts, or raw provider responses.

`final_confidence` on a successful result is the **planner-supplied** confidence only. It is not an aggregate statistical estimate.

## Contracts

| Type | Role |
| --- | --- |
| `CognitiveLoopInput` | One `Observation` + owning `AgentId` + immutable `InternalAgentState` |
| Stage artifacts | Frozen perception/memory/situation/self/futures/motivation/intention/`ActionPlan` |
| `CognitiveLoopResult` | Exact closed `AgentCommand` + ordered boundary records + memory-update intents |
| `MemoryUpdateIntent` | Post-cognition write intents (`WRITE_MEMORY` / `WRITE_BELIEF`); stores are not mutated inside the loop |

The synchronous `CognitionStrategy.propose(Perspective)` contract remains for existing callers. Prefer `CognitiveLoop` when async LLM-backed stages are needed later.

## Placeholders and fakes

`agents.cognition.defaults.default_cognitive_loop()` wires deterministic V1 placeholders (literal perception, empty memory retrieval unless a `MemoryService` is injected, stable motive/intention selection, `Wait` planner). These are **not** production memory or imagination quality and never call an LLM.

`agents.cognition.memory.ScopedMemoryRetriever` derives an owner-scoped query from the loop input, calls a bound `MemoryService.retrieve()`, and maps ranked snapshots into `RetrievedMemoryContext` plus pending access receipts. `AgentRuntime` applies receipts and write intents atomically through `MemoryService.apply()` only after cognition succeeds.

`tests/fakes/cognition.py` and `tests/fakes/memory.py` provide scriptable fakes (including `FakeEmbedder` / `FakeLogicalTickSource`) with metadata-only call records.

## AgentRuntime

`simulation.AgentRuntime` is the trusted composition boundary:

1. `start()` → `ACTIVE`
2. `process_observation(observation, token=TickToken)` builds a perspective (ownership check), runs cognition, applies validated memory intents / pending access receipts, returns `ActionSubmission(token, agent_id, command)`
3. Dead self in the observation → `TERMINAL` (no cognition, no submission)
4. Cognition failure → no submission and no memory mutation
5. Memory updates describe the committed observation and internal decision process — not uncommitted action outcomes

Cognition never sees `TickToken`, `WorldState`, or private world modules. Only simulation constructs submissions; engine admission still derives actor/request/world/revision authority.

## Logging (metadata only)

| Logger | Levels | Allowed fields |
| --- | --- | --- |
| `agents.cognition.loop` | DEBUG stage start/complete; ERROR failure codes | invocation/agent ids, component/version, ordinal, status, confidence, counts |
| `simulation.agent_runtime` | DEBUG lifecycle/cognition; INFO start/terminal; WARN/ERROR codes | run/agent/tick/invocation/status/counts |

**Never log:** observations, memories, beliefs, communications, cognitive artifact bodies, prompts, provider outputs, command arguments, seeds, or credentials.

Safe example:

```text
runtime_cognition_complete agent_id=agent-1 tick=3 invocation_id=agent-1-t3-i0 boundary_count=9 memory_update_count=0 command_type=Wait
```

Control verbosity with `PALIMPSEST_LOG_LEVEL`.

## Tests

```bash
uv run --frozen --python 3.12.14 pytest \
  tests/unit/test_cognition_models.py \
  tests/unit/test_cognitive_loop.py \
  tests/unit/test_cognition_defaults.py \
  tests/unit/test_agent_runtime.py \
  tests/architecture/test_cognitive_loop_isolation.py -q

uv run --frozen --python 3.12.14 pytest \
  -m integration tests/integration/test_agent_runtime_world_engine.py -q
```

Integration coverage is in-memory (no PostgreSQL/Docker/network/LLM).

## Deferred

- Production LLM-backed cognition stages
- Durable cognition-artifact persistence
- Concurrent agent execution
- General M4 analysis metrics over cognition receipts
- Marking roadmap **M3** complete (cognition policies still thin; providers exist separately)

## See Also

- [Architecture](architecture.md)
- [LLM providers](llm-providers.md)
- [Development](development.md)
