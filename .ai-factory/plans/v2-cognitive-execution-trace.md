# Implementation Plan: V2 Structured Cognitive Execution Trace

Branch: none (git.create_branches=false; current branch `main`)
Created: 2026-09-23
Improved: 2026-09-23 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "none"
Rationale: Skipped — ROADMAP has no incomplete / not-started milestone (`WARN [aif-plan] no incomplete roadmap milestone; skipping linkage`). Register an M5/V2 milestone via `/aif-roadmap` separately if desired.

## Downstream V2 plan contract
This plan must satisfy `docs/architecture.md` Downstream V2 plan contract:
1. V1 invariants intact (WorldEngine authority, Observation trust, subjective ≠ objective fold, no CoT/payload logging).
2. Capability flags remain default-off; this plan does **not** enable reserved cognitive flags (`advanced_social_inference`, etc.). Tracing is a separate optional recording spec.
3. V1 regression gate stays green with tracing off (and with tracing on must not change objective trajectories).
4. Runner schema bumps use accepted-set + exact key-set discipline.
5. No scripted emergence / no LLM→world shortcuts.
6. Experiments remain reproducible; catalog A–E stay flags-off and tracing-off by default.

## Overview

V1 already emits in-memory `ComponentBoundaryRecord` scientific receipts on each `CognitiveLoop` stage (typed I/O artifacts, confidence, status, `DecisionMetadata`) and forbids chain-of-thought / prompts / raw provider responses. Those records are **not** durable, volume-gated, or exposed as a stable repository API for debugger / experiment consumers.

This plan adds an **optional, configurable cognitive execution trace**: structured stage envelopes (summaries + typed artifact references/summaries + operational metadata) captured at major cognitive boundaries, persisted outside authoritative world history, and readable via simulation ports / persistence adapters — without influencing `WorldEngine` admission, mutation, or objective replay.

### Target stage sequence (trace view)

```text
Observation
→ retrieved memories
→ reconstructed memories
→ situation model
→ beliefs
→ emotional state (structured projection; no free-form affect narrative)
→ goals
→ imagined futures
→ theory-of-mind models when available (else explicit unavailable)
→ selected intention
→ planned action
```

Map onto existing `ComponentKind` stages where possible; introduce **trace-view projections** (not new CognitiveLoop stages) for beliefs/goals/emotional-state and for ToM-unavailable placeholders so consumers see a stable scientific sequence even when a cognitive stage is not yet owned.

## Design Decisions (locked by `/aif-improve`)

1. **Package split (import-linter safe).** `agents.cognition` owns pure stage projection helpers and closed summary types (no `run_id`, no persistence). `simulation` owns run-scoped `CognitionTraceInvocation` / stage records, repository Protocol, codec, and in-memory/Null implementations. `persistence` imports **only** simulation DTOs (forbidden: `persistence → agents`). Later analysis/debugger consumers read via simulation contracts (analysis may import `simulation`, not `agents.cognition` privately).
2. **Not a V2 capability flag.** Tracing uses top-level frozen `CognitionTraceSpec` on `SimulationRunnerConfig` (default disabled). Do not overload `advanced_social_inference` / other reserved flags.
3. **Runner schema.** Write `runner-config-v4` with versioned exact `_require_keys` including `cognition_trace`. Decode v1/v2/v3 → disabled `CognitionTraceSpec`. `config_fingerprint` may change; `exact_trajectory_hash` must not when only tracing differs.
4. **V1 regression profile.** Extend `experiments.catalog.v1_regression_profile` to also reject enabled tracing (stable code `v1_regression_trace_enabled`). Catalog A–E + reference scenario stay tracing-off.
5. **Latency / tokens.** Stage `latency_ms` is omit-by-default (CognitiveLoop has no stage timer today). Provider/model/token fields come only from existing allowlisted `LLMResultMetadata` when present; never invent wall-clock domain defaults.
6. **Append timing.** Append once after successful cognition **bind** (when a `CognitiveLoopResult` / partial failure records exist), via injected repository. Soft-fail default: sink errors → WARN + drop; never alter `ActionSubmission`, subjective decision inputs, or WorldEngine admission. Idempotent on `(run_id, agent_id, tick, invocation_id, content_hash)`. Do **not** embed full traces in run-control / `PendingRuntimeFinalization` checkpoint bytes.
7. **Alembic `0013` justified.** Indexed query columns `(run_id, tick)` and `(run_id, agent_id, tick)` are required for debugger/experiment inspection — satisfies scaffolding’s “0013 only if indexed SQL columns are proven necessary for inspection.” Update `simulation.compatibility.ALEMBIC_HEAD_REVISION` and invert `tests/unit/test_alembic_head_pin.py`.
8. **Outside objective evidence fold.** Cognition-trace tables are non-authoritative (like subjective/scientific-evidence class) and are **not** part of `EvidenceManifest` / objective high-water / authoritative replay. Stream-outbox / manifest integration is deferred.
9. **HTTP deferred.** Repository Protocol is the debugger/experiment read surface; no new `/v2` routes and no `subjective_debug` HTTP expansion in this plan.

## Non-goals
- Storing private free-form chain-of-thought, prompts, raw provider text, or credentials
- Changing production deliberation policy or enabling reserved V2 cognitive capability flags
- Feeding traces into live cognition, memory formation, prompts, or `WorldEngine`
- Shipping debugger UI / experiment analysis consumers / HTTP read routes (APIs/ports only)
- Implementing theory-of-mind cognition (record `unavailable` until a later plan owns `advanced_social_inference`)
- Folding traces into `EvidenceManifest`, objective high-water, or stream outbox
- Adding stage wall-clock timers to `CognitiveLoop` unless needed later (omit latency for now)

## Commit Plan
- **Commit 1** (after tasks 1–3): `feat(cognition,simulation): add cognition trace projection and runner-config-v4 spec`
- **Commit 2** (after tasks 4–7): `feat(simulation): cognition trace ports, codec, null sink, and runtime wiring`
- **Commit 3** (after tasks 8–10): `feat(persistence): durable cognition trace store and architecture isolation`
- **Commit 4** (after tasks 11–12): `test(docs): cognition trace regression gates and documentation`

## Tasks

### Phase 1: Projection helpers and runner config

- [x] Task 1: Define cognition-owned stage projection helpers (no run scope)
  - Deliverable: Under `agents.cognition` (prefer `trace.py` re-exported from the facade), add frozen closed summary / ref types and helpers used by the projector — **without** `run_id` or persistence concerns. Include:
    - `CognitionTraceStageKind` covering the scientific sequence (map to `ComponentKind` where 1:1; projection-only kinds for `retrieved_memories`, `reconstructed_memories`, `beliefs`, `emotional_state`, `goals`, `theory_of_mind` as needed)
    - Structured summary types (closed codes/counts/bands/ID refs — not free-text CoT)
    - Explicit forbid attributes on any new public types: `rationale`, `chain_of_thought`, `prompt`, `raw_response`, `credentials`, `endpoint` (mirror `ComponentBoundaryRecord`)
  - Durable run-scoped envelopes stay in Task 4 (`simulation`).
  - LOGGING REQUIREMENTS: DEBUG construction with kinds/counts only; ERROR validation with stable reason codes; never log observation/memory/belief text.
  - Files: `src/agents/cognition/trace.py` (new), `src/agents/cognition/__init__.py`, `tests/unit/test_cognition_trace_models.py` (or equivalent)
  - Dependencies: None

- [x] Task 2: Project `ComponentBoundaryRecord` + snapshot context into ordered stage summaries
  - Deliverable: Pure projector `project_cognition_trace_stages(...)` in cognition that:
    - Takes `CognitiveLoopResult` (and/or ordered boundary records), `CognitiveLoopInput` / `SubjectiveSnapshot` context, agent/tick/invocation ids, optional LLM metadata map keyed by stage
    - Emits an ordered tuple of stage summaries covering the scientific sequence (run_id applied later in simulation)
    - Splits `MEMORY_RETRIEVAL` into retrieved vs reconstructed views (`RetrievedMemoryContext` hits vs reconstructions)
    - Projects beliefs and active goals from frozen snapshot / self-state as summaries + ID refs
    - Projects emotional state from motivation/drive activations and `emotional_salience` aggregates — **not** a new CognitiveLoop stage
    - Emits `theory_of_mind` with status `unavailable` / reason code when no ToM artifact exists
    - Maps intention → selected intention and planning → planned action (`ActionPlan.command` **type** only in summaries)
    - Rejects embedding full `Observation` / `WorldEvent` / prompt bodies
    - **Latency:** omit `latency_ms` by default; do not invent wall-clock timings
    - **Tokens/provider:** copy only allowlisted fields from existing `LLMResultMetadata` when supplied; otherwise omit
  - LOGGING REQUIREMENTS: DEBUG `cognition_trace_projected` with invocation_id, agent_id, tick, stage_count; WARN truncation with reason codes; ERROR ownership/schema mismatches; metadata-only.
  - Files: `src/agents/cognition/trace.py`; tests for stage order, forbidden fields, deterministic summary hashing for identical inputs
  - Depends on: Task 1

- [x] Task 3: Add top-level `CognitionTraceSpec` via `runner-config-v4` (default off)
  - Deliverable:
    - Frozen `CognitionTraceSpec` on `SimulationRunnerConfig` (top-level, not nested under persistence): `enabled: bool = False`; `detail` enum (`summary` | `structured`, ignored when disabled); optional sampling / max-bytes soft limit with **truncate + reason code** (not hard-fail of the run)
    - Write schema `runner-config-v4`; keep v1/v2/v3 in `SUPPORTED_RUNNER_SCHEMA_VERSIONS`; versioned exact `_require_keys`; decode prior versions → disabled spec
    - Update `simulation.compatibility` matrix for runner write/accepted sets
    - Include trace spec in `config_fingerprint` / diagnostics
    - Extend `v1_regression_profile` to reject enabled tracing (`v1_regression_trace_enabled`) in addition to capability flags
    - Catalog A–E + reference scenario remain tracing-off; update golden runner fixtures for v3→v4 decode upgrade (default-off)
    - Do **not** prove trajectory-hash stability here (Task 11 owns that after the sink exists)
  - LOGGING REQUIREMENTS: INFO when constructing a runner with tracing enabled (detail level only); DEBUG encode/decode schema version; ERROR unused for tracing (capability_unimplemented path unchanged for reserved cognitive flags); never log secrets.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `src/experiments/catalog.py`, golden fixtures / `tests/unit/test_v2_golden_runner_configs.py`, `tests/unit/test_runner_serialization.py`, `tests/unit/test_v2_flag_defaults.py`
  - Depends on: Task 1

<!-- Commit checkpoint: tasks 1-3 -->

### Phase 2: Simulation ports, codec, and runtime wiring

- [x] Task 4: Define run-scoped simulation DTOs + `CognitionTraceRepository` Protocol
  - Deliverable: In `simulation` (new `cognition_trace.py` or section of persistence ports):
    - `CognitionTraceStageRecord` / `CognitionTraceInvocation` with `run_id`, agent_id, tick, invocation_id, ordered stages, command kind / final confidence metadata, schema id `cognition-trace-v1`, content_hash
    - Builder that attaches `run_id` to cognition stage summaries from Task 2
    - Protocol: `append_invocation(...)` (idempotent identical hash); `get_invocation(...)`; keyset/page query by `(run_id, agent_id?, tick_range?)`
    - `InMemoryCognitionTraceRepository` for unit tests (mirror scientific-evidence style)
    - Docstring: scientific observability only; never imported by `WorldEngine`, admission, perception, or live cognition inputs; not part of `EvidenceManifest`
  - LOGGING REQUIREMENTS: DEBUG append start/complete with run/agent/tick/invocation/hash prefix; WARN identical retry; ERROR divergent conflict; no payload fields.
  - Files: `src/simulation/cognition_trace.py` (preferred), `src/simulation/__init__.py`, unit tests
  - Depends on: Task 1

- [x] Task 5: Add `cognition-trace-v1` encode/decode codec
  - Deliverable: Versioned codec in `simulation` producing canonical bytes + content_hash for durable storage (same pattern as scientific evidence / subjective envelopes). Persistence adapters must store codec output only — no ad-hoc JSON in SQLAlchemy. Accepted-set ready for a single write version in this plan.
  - LOGGING REQUIREMENTS: DEBUG encode/decode with schema_version and hash prefix; ERROR `unsupported_version` / `invalid_fields`; never log stage summaries at INFO+.
  - Files: `src/simulation/cognition_trace_serialization.py` (or beside Task 4 module), tests for round-trip + hash stability
  - Depends on: Task 4

- [x] Task 6: Provide `NullCognitionTraceRepository` and construction injection rules
  - Deliverable: No-op Null implementation that records zero state and succeeds all appends/queries as empty. Document: runner / `AgentRuntime` always receives a repository instance; when `CognitionTraceSpec.enabled` is false, inject Null (zero durable calls). When enabled, inject in-memory or SQLAlchemy adapter from composition root. Keep `runner.py` `AgentRuntime(...)` construction minimal.
  - LOGGING REQUIREMENTS: DEBUG optional `cognition_trace_null_append` only under verbose tests if needed; default Null is silent at INFO+.
  - Files: same module as Task 4, `src/simulation/runner.py` construction helpers as needed, unit tests
  - Depends on: Task 4

- [x] Task 7: Wire optional sink in `AgentRuntime` / runner bind path
  - Deliverable: When tracing enabled, after successful cognition **bind** produces `CognitiveLoopResult` (or structured failure with partial boundary records):
    - Project stages (Task 2) → attach `run_id` (Task 4) → encode hash (Task 5) → `append_invocation`
    - Soft-fail: catch sink errors → WARN `cognition_trace_sink_failed` + continue; never change command/submission/subjective decision inputs
    - Idempotent retries on finalize/re-bind paths
    - Do not serialize full traces into `PendingRuntimeFinalization` / run-control checkpoint payloads
    - When disabled (Null): behavioral parity with V1
  - LOGGING REQUIREMENTS: DEBUG `cognition_trace_appended` / skipped; WARN sink failures with reason codes; ERROR only for projection invariant violations; metadata-only.
  - Files: `src/simulation/agent_runtime.py`, `src/simulation/runner.py`, unit tests for soft-fail + disabled path
  - Depends on: Tasks 2, 3, 5, 6

<!-- Commit checkpoint: tasks 4-7 -->

### Phase 3: Durable persistence and isolation

- [x] Task 8: Alembic `0013` cognition-trace tables + head-pin update
  - Deliverable:
    - Migration `0013_*`: append-only run-scoped cognition trace table(s) **outside** `AUTHORITATIVE_TABLES`
    - Indexed columns for inspection: `(run_id, tick)`, `(run_id, agent_id, tick)`; PK supporting idempotent retries (e.g. run_id + agent_id + tick + invocation_id)
    - BYTEA/JSONB payload = codec bytes + content_hash + schema_version; FK to `simulation_runs` RESTRICT
    - Set `ALEMBIC_HEAD_REVISION = "0013"` in `simulation.compatibility`; update matrix entry
    - Invert/replace `tests/unit/test_alembic_head_pin.py` (head is `0013`; `0013_*.py` exists; still assert no capability-flag SQL tables; trace tables ∉ `AUTHORITATIVE_TABLES`)
    - Explicitly document: not part of `EvidenceManifest` / objective high-water
  - LOGGING REQUIREMENTS: Alembic INFO start/complete with revision id; no payload dumps.
  - Files: `alembic/versions/0013_*.py`, `src/persistence/orm.py`, `src/simulation/compatibility.py`, `tests/unit/test_alembic_head_pin.py`, `tests/unit/test_compatibility_matrix.py`
  - Depends on: Task 4

- [x] Task 9: SQLAlchemy adapter + factory
  - Deliverable: `SqlAlchemyCognitionTraceRepository` implementing the Protocol using Task 5 codec bytes; `persistence.create_cognition_trace_repository(...)`; composition injects it only when tracing enabled + durable (otherwise Null / in-memory). Idempotent identical retry; conflict on divergent hash.
  - LOGGING REQUIREMENTS: Mirror scientific evidence (`*_append_started`, `*_committed`, `*_identical_retry`, `*_divergent_conflict`).
  - Files: `src/persistence/cognition_trace_sqlalchemy.py` (new), `src/persistence/__init__.py`, unit tests with fakes; integration marked opt-in
  - Depends on: Tasks 5, 8

- [x] Task 10: Architecture isolation gates (trace cannot influence WorldEngine)
  - Deliverable: Add/extend architecture tests:
    - Trace ORM table names disjoint from `AUTHORITATIVE_TABLES`
    - `world` / private `_perception` / engine admission do not import cognition-trace types
    - `persistence` does not import `agents` / `agents.cognition` for this feature
    - Cognition does not import analysis; analysis must not be required for append path
    - Forbidden patterns: feeding `CognitionTraceInvocation` into `WorldEngine`, `ActionSubmission`, or `CognitiveLoopInput`
    - import-linter updates only if a new module needs an allowlist exception (prefer none)
  - LOGGING REQUIREMENTS: N/A for tests; production allowlists in Task 12.
  - Files: `tests/architecture/*`, `pyproject.toml` only if required
  - Depends on: Tasks 4, 8

<!-- Commit checkpoint: tasks 8-10 -->

### Phase 4: Regression and docs

- [ ] Task 11: Tests for volume control, determinism, and V1 regression
  - Deliverable:
    - Unit: projector stage order, unavailable ToM, no CoT fields, summary hash stability
    - Unit: codec round-trip; repository idempotency + page queries (in-memory)
    - Unit: Null vs enabled injection; soft-fail sink does not change command kind
    - Determinism: short seeded run with tracing ON vs OFF → identical `exact_trajectory_hash` / objective commit chains under deterministic fakes (`config_fingerprint` may differ)
    - `tests/unit/test_v1_regression_gate.py` green; `v1_regression_profile` rejects enabled flags **and** enabled tracing
    - Sampling/truncation tests for volume controls
  - LOGGING REQUIREMENTS: Assert selected log extras stay metadata-only.
  - Files: `tests/unit/test_cognition_trace*.py`, extend V1/V2 regression suites
  - Depends on: Tasks 7, 9

- [ ] Task 12: Documentation checkpoint (`/aif-docs` scope)
  - Deliverable: Update:
    - `docs/cognition-runtime.md` — trace sequence, relation to `ComponentBoundaryRecord`, package split, optional config, no-CoT, ToM unavailable, logging allowlist
    - `docs/architecture.md` — seam table entry; isolation; Alembic `0013`; Downstream V2 checklist still satisfied
    - `docs/persistence.md` — tables, non-authoritative, not in EvidenceManifest, factory, head pin
    - `docs/simulation-runner.md` — `CognitionTraceSpec`, `runner-config-v4`, fingerprint vs trajectory
    - `docs/experiments.md` — `v1_regression_profile` also asserts tracing off
    - `.ai-factory/DESCRIPTION.md` / `ARCHITECTURE.md` — brief seam + head note
    - Explicit: HTTP/debugger UI deferred; ports are the consumer API
  - LOGGING REQUIREMENTS: Document allowlisted fields for new logger names in the cognition-runtime table.
  - Files: docs listed above
  - Depends on: Tasks 3, 7, 9

<!-- Commit checkpoint: tasks 11-12 -->

## Acceptance criteria
1. With tracing disabled (default), behavior and objective trajectories match V1 for the same seed/scenario under deterministic fakes; V1 regression gate green; `v1_regression_profile` rejects enabled tracing.
2. With tracing enabled, structured stage envelopes are appendable/queryable via repository ports for the scientific sequence above, including explicit ToM-unavailable records.
3. Trace payloads contain summaries, references, confidence/uncertainty, and allowlisted operational metadata — never chain-of-thought, prompts, or raw provider bodies.
4. Trace data cannot influence `WorldEngine` behavior (architecture tests + trajectory hash ON vs OFF proof).
5. Volume is configurable; long runs can keep tracing off or summary-only with truncation reason codes.
6. Package boundaries hold: cognition has no `run_id`/persistence; persistence does not import agents; codec owns durable bytes.
7. Docs and compatibility matrix reflect `runner-config-v4`, `cognition-trace-v1`, and Alembic head `0013`.

## Key integration points (existing code)
- `agents.cognition.models.ComponentBoundaryRecord` / `ComponentKind` / `CognitiveLoopResult` / `RetrievedMemoryContext` / `MotivationEvaluation`
- `agents.cognition.loop.CognitiveLoop` stage order
- `simulation.agent_runtime.AgentRuntime` bind/finalize (`loop_result.boundary_records`); construction at `simulation.runner`
- `simulation.runner_models.SimulationRunnerConfig` / `V2CapabilityFlags` (do not overload flags)
- `simulation.persistence.ScientificEvidenceRepository` pattern for ports + in-memory + SQLAlchemy
- `simulation.compatibility.ALEMBIC_HEAD_REVISION` + `tests/unit/test_alembic_head_pin.py`
- `experiments.catalog.v1_regression_profile`
- `llm.models.LLMResultMetadata` / `TokenUsage` (allowlisted metadata only)
- `docs/architecture.md` Downstream V2 plan contract + extension seams
- `docs/cognition-runtime.md` pipeline + logging allowlists
- Import-linter: `persistence` ↛ `agents`; `agents.cognition` ↛ `simulation`
