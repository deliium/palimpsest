# Cognition and agent runtime

[← Previous Page](architecture.md) · [Back to README](../README.md) · [Next Page →](memory-reconstruction.md)

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
| `CognitiveLoopInput` | One `Observation` + owning `AgentId` + immutable `InternalAgentState` + frozen `SubjectiveSnapshot` |
| `SubjectiveSnapshot` | Owner-scoped semantic beliefs + directed relationships observed by every stage |
| Stage artifacts | Frozen perception/memory/situation/`SelfModel`/futures/motivation/intention/`ActionPlan` |
| `SelfModel` | Deterministic projection of self-relevant semantic beliefs (no predefined traits/roles) |
| `CognitiveLoopResult` | Exact closed `AgentCommand` + ordered boundary records + subjective update intents |
| `MemoryUpdateIntent` | Post-cognition intents (`WRITE_MEMORY` / `WRITE_BELIEF` / `REVISE_BELIEF` / `REVISE_RELATIONSHIP`); stores are not mutated inside the loop |

Every cognition invocation sees one frozen owner snapshot. Proposed belief and relationship revisions become visible only on the next invocation after an atomic commit. The synchronous `CognitionStrategy.propose(Perspective)` contract remains for existing callers. Prefer `CognitiveLoop` when async LLM-backed stages are needed later.

## Placeholders and fakes

`agents.cognition.defaults.default_cognitive_loop()` wires deterministic V1 placeholders (literal perception, empty memory retrieval unless a `MemoryService` is injected, stable motive/intention selection, `Wait` planner). These are **not** production memory or imagination quality and never call an LLM.

`agents.cognition.memory.ScopedMemoryRetriever` builds current context/beliefs, calls bound `MemoryService.recall()`, and maps results into `RetrievedMemoryContext`: **`reconstructions` are the remembered episodes**; ranked hits and pending access receipts are scientific metadata only. Optional `ReconsolidationIntent` stays pending until `AgentRuntime` applies it with access receipts via `MemoryService.apply()` after the whole loop succeeds. Inject `LLMMemoryReconstructor` only when provider-backed reconstruction is desired; the default path is deterministic and provider-free.

Details: [Memory reconstruction](memory-reconstruction.md).

`tests/fakes/cognition.py` and `tests/fakes/memory.py` provide scriptable fakes (including `FakeEmbedder` / `FakeLogicalTickSource`) with metadata-only call records.

## AgentRuntime

`simulation.AgentRuntime` is the trusted composition boundary:

1. `start()` → `ACTIVE`
2. `process_observation(observation, token=TickToken)` builds a perspective with a frozen subjective snapshot (ownership check), runs cognition, then commits episodic writes/accesses/reconstructions plus belief and relationship revisions through one owner-scoped `SubjectiveStateService` batch
3. Dead self in the observation → `TERMINAL` (no cognition, no submission)
4. Cognition failure → no submission and no subjective mutation (including no reconsolidation)
5. Subjective updates describe the committed observation and internal decision process — not uncommitted action outcomes

`SubjectiveStateService` prevalidates intents, applies copy-then-swap (in-memory) or one PostgreSQL transaction (durable), and rolls back every subjective change on any adapter failure. Retries with the same operation ID are idempotent. Cognition never sees `TickToken`, `WorldState`, or private world modules. Only simulation constructs submissions; engine admission still derives actor/request/world/revision authority.

## Logging (metadata only)

| Logger | Levels | Allowed fields |
| --- | --- | --- |
| `agents.cognition.loop` | DEBUG stage start/complete; ERROR failure codes | invocation/agent ids, component/version, ordinal, status, confidence, counts |
| `agents.cognition.memory` | DEBUG `memory_recall_mapped`; ERROR ownership codes | owner/tick, policy versions, source/reconstruction/pending counts, provider/fallback flags |
| `agents.cognition.reconstruction` | DEBUG/INFO/WARN LLM reconstruct path | reconstruction/request IDs, tick, prompt/policy versions, counts, fallback flags |
| `simulation.agent_runtime` | DEBUG lifecycle/cognition/apply; INFO start/terminal/`runtime_reconsolidation_committed`; WARN/ERROR codes | run/agent/tick/invocation/status/counts |

**Never log:** observations, memories, belief claims/values, self-model propositions, relationship dimension values, reconstructions/narratives, communications, cognitive artifact bodies, prompts, provider outputs, command arguments, seeds, or credentials. Logs may include run/owner/invocation IDs, ticks, policy versions, counts, statuses, and stable reason codes only.

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

- Production LLM-backed cognition stages (beyond optional reconstructive recall)
- Durable cognition-artifact persistence
- Concurrent agent execution
- General M4 analysis metrics over cognition receipts
- Marking roadmap **M3** complete (cognition policies still thin; providers exist separately)

## See Also

- [Architecture](architecture.md)
- [Memory reconstruction](memory-reconstruction.md)
- [LLM providers](llm-providers.md)
- [Development](development.md)
