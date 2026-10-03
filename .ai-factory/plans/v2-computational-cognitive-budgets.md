# Implementation Plan: Explicit Computational / Cognitive Budgets

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-03
Improved: 2026-10-03 (`/aif-improve` ×2)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete milestone; this plan adds a default-off per-tick cognition budget (not a capability flag) and does not claim `multi_hop_testimony_tracking`.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M6 — Remaining V2 Capability Flags
INFO [aif-plan] resolved plan file: .ai-factory/plans/v2-computational-cognitive-budgets.md (format=slug)

## Compatibility contract

This plan adds an explicit per-tick computational/cognitive budget so complex V2 agents cannot make an unbounded number of LLM calls, simulations, recalls, or ToM updates in one cognition prepare. It must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants intact. `WorldEngine` remains the only objective mutation authority. Cognition still receives immutable per-agent `Observation` / `Perspective` only — never `WorldState`, `WorldEvent` stores, or another agent's private cognition. Budget exhaustion never mutates the world and never skips producing exactly one closed `AgentCommand`.
2. No new capability flag. `CognitiveBudgetMode` defaults to `DISABLED`. Off leaves today's behavior: stage-local caps (e.g. `ProspectivePolicy`, `TheoryOfMindPolicy.max_hypotheses`, memory retriever `limit`, `ReflectionPolicy.interval_ticks`) apply as today with no cross-stage tick ledger. Do **not** own `multi_hop_testimony_tracking`. Owned flags stay owned and are not required for the budget path.
3. V1 regression gate stays green under flags-off, tracing-off, and budget-disabled. Catalog A–E and the reference scenario keep current `exact_trajectory_hash` values. Experiment AD is additive and must not be appended to `tests/unit/test_v1_regression_gate.py`.
4. Schema bump only when the mode is on. Default write stays `runner-config-v4`. `RUNNER_SCHEMA_VERSION` stays `runner-config-v4`. Add `runner-config-v22` to the accepted set. v22 carries every `runner-config-v21` cognition key plus the nine budget keys on each agent when `cognitive_budget_mode` is `enforced`. Emit v22 only when some agent's `CognitiveBudgetMode` is `ENFORCED`. A narratives-only config still writes v21. Reject v22 when every budget mode is `DISABLED` (`v22_requires_cognitive_budget`). Reject `ENFORCED` on v1–v21 (`cognitive_budget_mode_requires_v22`). **Widen every existing mode and spec allowlist that currently ends at v21 so v22 remains legal** for consolidation, reflection, prospective imagination, counterfactual reasoning, communication strategy, reputation, skill learning, teaching, production knowledge, environmental dynamics, territorial claims, group formation, social norms, social conventions, artifact interpretation, semantic naming, and cultural narratives. That includes the named frozensets in `src/simulation/runner_serialization.py` (`_SKILL_SCHEMA_VERSIONS`, `_COGNITION_SCHEMA_*`, and every peer set that currently ends at v21) and every local set in `SimulationRunnerConfig.__post_init__` that currently ends at v21. Encode and decode `capability_flags` and `cognition_trace` on v22. Encode and decode `environmental_dynamics` on v22 when the spec is present, using the same rule as v21. **Encode and decode `cultural_narrative_mode` on both v21 and v22** (today it is exact-equality on v21 only — a narratives+budgets config writes v22 and must not drop the narrative field). Encode `semantic_naming_mode` on `{v20, v21, v22}` and widen every other prior-mode membership set that currently ends at v21 the same way. Encode the nine budget keys only on v22. Decode v22 agent cognition with `_COGNITION_KEYS_V22`, defined as `_COGNITION_KEYS_V21` plus the nine budget keys, before the v21 branch. `_require_keys` is an exact key check. Narratives-only equality (`v21_requires_cultural_narratives`) stays an equality check on v21. A config that enables both cultural narratives and cognitive budgets writes v22, so `cultural_narrative_mode_requires_v21` becomes membership in `{v21, v22}`. `semantic_naming_mode_requires_v20` becomes membership in `{v20, v21, v22}`. Leave `v1_regression_profile` unchanged. Baseline: the accepted set already ends at `runner-config-v21`.
5. No scripted emergence. Friend, enemy, leader, and culture labels stay forbidden. The experiment does not add a milestone script or a new physical rule.
6. No LLM → world shortcuts. Budget accounting may refuse further provider calls; it never lets LLM output become a world mutation. Structured LLM output still requires cognition translation + normal admission.
7. Experiments stay reproducible. Experiment AD's low-cost and high-cost arms share seed, scenario, stochastic identity, and architecture composition; only budget limits differ. Prefer deterministic fakes / stubs. Analysis comparison runs after the run and is not fed back into cognition. Experiment AD and `cognitive_budget@1` stay analysis-only and off the V1 regression gate.
8. Optional cognition tracing stays outside the objective fold. Budget consumption is projected into cognition-trace summaries when tracing is on. Do **not** insert a `ComponentKind` or an ordinal in `_STAGE_ORDER`. Do **not** bump `COGNITION_TRACE_SUMMARY_SCHEMA` (stay on `cognition-trace-stage-summary-v1`); new closed `CognitionTraceCountKey` / `CognitionTraceStageKind` members are allowed. Do **not** add an Alembic revision. Tracing on versus off must not change `exact_trajectory_hash` when budget mode is `DISABLED`.

## Goal

A complex V2 agent must not make an unlimited number of LLM calls or simulations per tick. Support configurable per-agent limits:

| Cap | Meaning |
| --- | --- |
| `max_llm_calls_per_tick` | Provider `generate` invocations across all stages this prepare |
| `max_tokens_per_tick` | Sum of allowlisted input+output tokens charged this prepare |
| `max_imagination_branches` | Expanded prospective nodes beyond root + each kept counterfactual scenario |
| `max_planning_depth` | Effective prospective/counterfactual depth (`min` with local policy); **not** epistemic nesting |
| `max_recalled_memories` | Ranked memory hits retained after retrieval |
| `max_tom_targets` | Distinct other-agent ToM / epistemic targets updated this tick |
| `reflection_interval_ticks` | Floor on reflection cadence (effective ≥ `ReflectionPolicy` gap) |
| `timeout_seconds` | Injected monotonic clock budget for the prepare (0 disables) |

When a budget is exhausted, cognition **degrades gracefully** (truncate / skip optional depth / refuse LLM / keep deterministic fallback) and still compiles exactly one closed `AgentCommand`. Budgets are measurable, configurable per architecture/experiment, and visible in cognitive execution traces (and a light in-run audit when tracing is off).

```text
CognitiveLoop.prepare start
  → TickBudgetLedger(limits)
  → each stage: try_consume / clamp / degrade
  → always: CommandPlanner → one AgentCommand
  → CognitiveBudgetAudit + optional CognitionTrace BUDGET_SUMMARY projection
```

## Design Decisions (locked)

### Mode and schema (not a flag)

- Add lockstep enums `CognitiveBudgetMode` in `src/simulation/runner_models.py` and `CognitionBudgetMode` in `src/agents/cognition/configuration.py`: `DISABLED`, `ENFORCED`. Default is `DISABLED`. This is **not** a `V2CapabilityFlags` slot.
- Nested frozen `CognitiveBudgetLimits | None` on `AgentCognitionSpec` (simulation): required / non-`None` iff mode is `ENFORCED`, else `None`. Mirrored as `CognitiveBudgetPolicy` version `cognitive-budget-v1` on `CognitionLoopConfig` (cognition), including optional `clock: Callable[[], float] | None = None` (same shape as `ProspectivePolicy.clock`). Runner encode/decode owns the simulation types and **flattens** nested limits to the eight numeric runner keys; `_cognition_config_for` maps them into the policy (clock stays cognition/test-only — never a runner JSON key).
- **Runner JSON keys (v22 cognition dict only when mode is `ENFORCED`):**
  - `cognitive_budget_mode` (`enforced`)
  - `max_llm_calls_per_tick` (int ≥ 0)
  - `max_tokens_per_tick` (int ≥ 0)
  - `max_imagination_branches` (int ≥ 1)
  - `max_planning_depth` (int ≥ 1)
  - `max_recalled_memories` (int ≥ 1)
  - `max_tom_targets` (int ≥ 0)
  - `reflection_interval_ticks` (int ≥ 1)
  - `timeout_seconds` (finite float ≥ 0; `0` disables wall-clock check)
- When mode is `DISABLED`, omit all nine keys (v1–v21 decode). Construction fails closed with stable reason codes for invalid types/ranges, or when `ENFORCED` is set on a schema older than v22 (`cognitive_budget_mode_requires_v22`), or when v22 is used without any agent `ENFORCED` (`v22_requires_cognitive_budget`).
- Default write surface stays `runner-config-v4`. Preset helpers `low_cost_budget_limits()` / `high_cost_budget_limits()` live in cognition (and are re-exported for experiments) so arms do not invent ad-hoc numbers in catalog code.

### Tick ledger (cross-stage)

- New module `src/agents/cognition/budget.py` owns:
  - `CognitiveBudgetPolicy` / presets
  - `BudgetDimension` / `BudgetExhaustedReason` closed enums
  - `TickBudgetLedger` (per-prepare mutable account; not frozen)
  - `CognitiveBudgetAudit` (frozen end-of-prepare snapshot)
- `CognitiveLoop.prepare` constructs one ledger when mode is `ENFORCED` (else `None`). Pass the ledger into stages that can consume resources via keyword-only optional arguments so existing call sites stay valid.
- **Charge rules (locked):**
  - **LLM:** every cognition-boundary `LLMProvider.generate` counts `1` call — including reflection, prospective selection, counterfactual selection, theory-of-mind, world-model, memory reconstruction, and production/competence/teaching assist paths that run inside `prepare`. Add `total_tokens` from allowlisted `LLMResultMetadata` when present (else charge `0` tokens for that call, still count the call). Charge only when `provider.generate` is entered; local pre-checks that refuse before the boundary do not charge. Attempted calls that leave the boundary count even when they fall back. Consolidation stays out of prepare charging unless it actually runs inside `prepare`.
  - **Imagination branches:** charge `1` per expanded prospective node beyond the root **and** `1` per kept `CounterfactualScenario`. One-step V1 imagination (`ProspectiveImaginationMode.DISABLED` / `None` policy) charges `0` branches. Effective branch cap = `min(ProspectivePolicy.max_branches, tick_remaining, max_imagination_branches)` (and counterfactual kept-scenario charge against the same tick dimension).
  - **Planning depth:** effective depth = `min(local_policy_depth, remaining_depth_budget, max_planning_depth)` for prospective and counterfactual search only (`ProspectivePolicy.max_depth` / horizon). **Do not** clamp `EpistemicPolicy.max_depth` with this cap.
  - **Recalled memories:** after ranking, truncate to `min(retriever_limit, max_recalled_memories, remaining)`.
  - **ToM targets:** number of distinct other `AgentId`s whose mind and/or epistemic rows are updated this prepare; stop updating further targets when exhausted (keep already-updated ones). **Not** `TheoryOfMindPolicy.max_hypotheses` (store eviction size).
  - **Reflection:** effective gap = `max(ReflectionPolicy.interval_ticks, ReflectionPolicy.min_gap_ticks, reflection_interval_ticks)`. If the gap is not met, or the ledger marks `BUDGET_REFLECTION`, skip the reflection body this tick (passthrough / no revision).
  - **Timeout:** only an injected monotonic callable on the policy/ledger may trip `BUDGET_TIMEOUT`. Cognition never calls `time.time` / `time.monotonic`. Missing/non-callable clock ⇒ timeout check disabled (deterministic). Tick-level timeout is **independent** of `ProspectivePolicy.timeout_seconds` / `ProspectivePolicy.clock` (both may trip via their own clocks). Check at stage boundaries before expensive expansion / provider calls.
- **Local policy interaction:** when `ENFORCED`, effective cap = `min(local_cap, tick_remaining, tick_limit)` for every overlapping dimension (`ProspectivePolicy.max_llm_calls` / `max_tokens` / `max_branches` / `max_depth`, `CounterfactualPolicy.max_llm_calls` / `max_tokens` / `max_decisions`, memory retriever `limit`, reflection gaps). When `DISABLED`, do not consult the ledger; ProspectivePolicy / ToM / memory / reflection behave exactly as today.
- **Reason-code namespaces stay distinct.** Tick ledger uses `BudgetExhaustedReason` / `BudgetDimension`. Stage-local prospective pruning keeps `ProspectivePruneReason.BUDGET_*`. Adapters may translate for logs/audits but must not merge the enums.

### Graceful degradation (never fail the tick)

Priority when a dimension is exhausted (stable reason codes):

1. `BUDGET_TIMEOUT` / `BUDGET_LLM` / `BUDGET_TOKENS` → refuse further provider calls; continue deterministic stage bodies; set `fallback_used` where those stages already have it.
2. `BUDGET_BRANCHES` / `BUDGET_DEPTH` → stop expanding prospective/counterfactual; collapse to current one-step / Wait-capable path already owned by those engines.
3. `BUDGET_MEMORIES` → truncate ranked hits / reconstructions; empty recall is legal.
4. `BUDGET_TOM` → stop adding new ToM targets; existing mind state for this owner remains; action bias uses whatever was updated.
5. `BUDGET_REFLECTION` → skip reflection revisions this tick.
6. Intention + planning always run and still emit exactly one closed `AgentCommand` (`Wait` on existing planner fallback).

Budget exhaustion is **not** a hard error and must not raise out of `prepare` / `bind`. Log WARN once per exhausted dimension per prepare (metadata only: agent_id, tick, dimension, used, limit).

### Audits and traces

- `CognitiveBudgetAudit` fields: owner, tick, mode, limits snapshot (ints/floats only), used counts per dimension, exhausted reason codes (tuple), `degraded` bool, first exhausted dimension (or none). Forbidden: prompts, observation text, memory payloads, CoT.
- Append audits on `AgentRuntime` and export onto `SimulationRunnerResult.cognitive_budget_audits` (in-memory, default empty, not written by runner-result serialization) — same pattern as `prospective_audits` / `export_prospective_audits`.
- When `CognitionTraceSpec.enabled`, project budget consumption into cognition traces:
  - Add closed `CognitionTraceCountKey` values: `llm_calls_used`, `tokens_used`, `imagination_branches_used`, `planning_depth_reached`, `memories_recalled`, `tom_targets_used`, `reflection_ran` (and matching `*_limit` keys only if needed for consumers; prefer putting limits once on the summary stage).
  - **Status mapping (locked):** use existing `CognitionTraceStageStatus.TRUNCATED` for memory/branch/depth cuts; use `SKIPPED` for reflection body skip and refused additional ToM targets / refused LLM stages. Do **not** add a `DEGRADED` status. Attach stable reason code `budget_exhausted` on those summaries (closed code field / existing reason slot — no free text).
  - **Always** emit a projection-only `CognitionTraceStageKind.BUDGET_SUMMARY` at the end of the scientific sequence (no `ComponentKind`, no `_STAGE_ORDER` ordinal). Keep `COGNITION_TRACE_SUMMARY_SCHEMA` = `cognition-trace-stage-summary-v1`.
- Do **not** add Alembic columns; reuse existing structured trace JSON. Do **not** feed audits/traces into live planning.

### Architecture / experiment configuration

- Experiment AD (`experiment-ad-cognitive-budgets`) locked composition via `experiment_ad_cognitive_budgets` in `src/experiments/catalog.py` (export from `src/experiments/__init__.py`):
  1. Build a shared base runner (reference-scale or existing AD-adjacent scenario helper; shared seed + stochastic identity).
  2. `expanded = expand_architecture(shared, "full_v2_agent")` — note today's preset ships `prospective_mode=disabled` and architecture `schema_version` v6; both must be overridden below.
  3. For every agent cognition row: set `prospective_mode=DETERMINISTIC`, `cognitive_budget_mode=ENFORCED`, and nested `CognitiveBudgetLimits` from the preset; leave cultural narratives / social ledgers / artifact / naming modes `DISABLED`.
  4. Set runner `schema_version=runner-config-v22` on both arms (after expand; do not leave architecture v6).
  5. Arms differ **only** by limits:
     - `ad-low-cost`: `low_cost_budget_limits()`
     - `ad-high-cost`: `high_cost_budget_limits()`
- Preset magnitudes (locked defaults; tune only with a plan amend if proofs require):

  | Cap | low_cost | high_cost |
  | --- | ---: | ---: |
  | `max_llm_calls_per_tick` | 0 | 4 |
  | `max_tokens_per_tick` | 0 | 2048 |
  | `max_imagination_branches` | 2 | 16 |
  | `max_planning_depth` | 1 | 3 |
  | `max_recalled_memories` | 2 | 12 |
  | `max_tom_targets` | 1 | 6 |
  | `reflection_interval_ticks` | 16 | 8 |
  | `timeout_seconds` | 0 | 0 |

  (`timeout_seconds=0` keeps both arms deterministic without a wall clock; timeout is proven in unit tests with an injected scripted clock.)

- **This plan does not** add new architecture ids, put `architecture_id` into runner JSON, or attach default budget profiles onto `ArchitectureDefinition`. Catalog helpers set limits explicitly after expand.
- Analysis metric `cognitive_budget@1` in `src/analysis/cognitive_budget_metrics.py` builds a `MetricDocument` from caller-supplied audit rows (and optional committed events). **Duck-type with `getattr`.** Must not import `agents`, `TickBudgetLedger`, `CognitiveLoop`, or `AgentRuntime`. Register `MetricFamilyId.COGNITIVE_BUDGET` (or equivalent token) in `src/analysis/specifications.py` beside peer V2 families and export from `src/analysis/__init__.py`. Report consumption totals, degradation counts, and whether the low-cost arm shows strictly fewer charged LLM calls / branches than high-cost under the shared seed. Analysis-only; never an input to cognition.

## Non-Goals

- Owning `multi_hop_testimony_tracking` or adding any new `V2CapabilityFlags` slot
- Changing WorldEngine admission, Observation trust, or authoritative replay
- Hard-failing a tick when a budget is exhausted
- Putting budget accounting into `EvidenceManifest` / objective high-water / stream outbox
- New Alembic revision or HTTP debugger routes for budgets
- Making `ProspectivePolicy` / ToM / reflection knobs into runner JSON beyond the tick-level keys above
- Wall-clock domain defaults (`time.time` / `time.monotonic` inside cognition)
- Feeding `cognitive_budget@1` or traces back into live planning or memory formation
- Putting Experiment AD on the V1 regression gate
- Free-form CoT / prompt / payload logging of budget decisions
- Attaching budget profiles to `ArchitectureDefinition` / registering new architecture ids (deferred; AD sets limits after expand)
- Adding `CognitionTraceStageStatus.DEGRADED` or bumping `COGNITION_TRACE_SUMMARY_SCHEMA`
- Clamping `EpistemicPolicy.max_depth` via `max_planning_depth`

## Commit Plan
- **Commit 1** (after tasks 1–3): `feat(cognition,simulation): add cognitive budget contracts and runner-config-v22`
- **Commit 2** (after tasks 4–6): `feat(cognition): enforce tick budget ledger with graceful degradation`
- **Commit 3** (after tasks 7–8): `feat(cognition,simulation): expose budget audits and cognition-trace consumption`
- **Commit 4** (after tasks 9–11): `feat(experiments,analysis,docs): low-cost vs high-cost cognition budget experiment`

## Tasks

### Phase 1: Contracts and runner schema

- [x] Task 1: Define cognition budget contracts and presets
  - Deliverable: Add `src/agents/cognition/budget.py` with frozen `CognitiveBudgetPolicy` (`cognitive-budget-v1`) including optional `clock: Callable[[], float] | None = None` (same shape as `ProspectivePolicy.clock`; missing/non-callable disables timeout; never call `time.time` / `time.monotonic`), `BudgetDimension`, `BudgetExhaustedReason` (distinct from `ProspectivePruneReason`), mutable `TickBudgetLedger`, frozen `CognitiveBudgetAudit`, and presets `low_cost_budget_limits()` / `high_cost_budget_limits()` / disabled mapping helpers. Export from `src/agents/cognition/__init__.py`. Add `CognitionBudgetMode` (`DISABLED`, `ENFORCED`) on `CognitionLoopConfig` + validation (policy required iff `ENFORCED`). Constructors fail closed with stable reason codes; `timeout_seconds` must be finite and `>= 0`; zero LLM/token caps are legal (means no provider use).
  - LOGGING REQUIREMENTS: logger `agents.cognition.budget`. DEBUG on policy construction with all caps (no payloads). DEBUG `tick_budget_created` with agent_id/tick/mode. WARN `tick_budget_exhausted` once per dimension with used/limit. ERROR only on validation failures with reason codes. Never log observation/memory/prompt text.
  - Files: `src/agents/cognition/budget.py`, `src/agents/cognition/configuration.py`, `src/agents/cognition/__init__.py`, `tests/unit/test_cognitive_budget.py`
  - Dependencies: none

- [x] Task 2: Wire `CognitiveBudgetMode` + limits through `AgentCognitionSpec` and `runner-config-v22` (exact key-set + allowlist widen)
  - Deliverable:
    - Add simulation enums/types on `AgentCognitionSpec`: `cognitive_budget_mode` default `DISABLED` plus nested `cognitive_budget_limits: CognitiveBudgetLimits | None` (`None` when `DISABLED`; required / validated iff `ENFORCED`). Encode/decode **flattens** nested limits to the eight numeric runner keys + `cognitive_budget_mode` on v22 only.
    - Add `RUNNER_SCHEMA_VERSION_V22 = "runner-config-v22"`; keep `RUNNER_SCHEMA_VERSION` as `runner-config-v4`.
    - `_COGNITION_KEYS_V22 = _COGNITION_KEYS_V21` plus the nine budget keys; decode v22 **before** the v21 branch; `_require_keys` remains exact.
    - Encode budget keys **only** on v22 when mode is `ENFORCED`. Encode `cultural_narrative_mode` on `{v21, v22}`. Encode `semantic_naming_mode` on `{v20, v21, v22}`. Widen every named frozenset in `runner_serialization.py` that currently ends at v21 to include v22 (including social convention / artifact / naming / prior peer sets). Widen every local membership set in `SimulationRunnerConfig.__post_init__` that currently ends at v21 the same way. Change exact `== v21` narrative requirement to membership in `{v21, v22}`; keep `v21_requires_cultural_narratives` as v21-only equality. Fail closed: `cognitive_budget_mode_requires_v22`, `v22_requires_cognitive_budget`.
    - Encode/decode `capability_flags`, `cognition_trace`, and optional `environmental_dynamics` on v22.
    - Map in `simulation.runner._cognition_config_for` to `CognitionBudgetMode` + `CognitiveBudgetPolicy` (limits → policy ints/floats; clock stays unset/`None` from runner). v1–v21 omit keys → `DISABLED` + `limits=None`.
    - Update `src/simulation/compatibility.py` accepted/write notes.
  - LOGGING REQUIREMENTS: INFO when constructing a runner with any `ENFORCED` budget (agent count + schema only). DEBUG encode/decode schema version and mode. ERROR unused for budgets (keep `capability_unimplemented` path unchanged for unowned flags). Never log secrets.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `src/simulation/runner.py`, `src/simulation/__init__.py`, golden fixtures / `tests/unit/test_runner_serialization.py`, `tests/unit/test_v2_flag_defaults.py`
  - Depends on: Task 1

- [x] Task 3: Prove DISABLED parity, fail-closed schema gates, and v22 widen membership
  - Deliverable: Unit tests that (a) budget-disabled configs on v4 match prior cognition wiring and do not construct a ledger, (b) `ENFORCED` on v4/v21 fails with `cognitive_budget_mode_requires_v22`, (c) v22 without any `ENFORCED` fails with `v22_requires_cognitive_budget`, (d) v22 + `ENFORCED` + reflection + prospective constructs (widened allowlists), (e) v22 + cultural narratives + budgets encodes both `cultural_narrative_mode` and budget keys, (f) unowned `multi_hop_testimony_tracking` still fails closed, (g) catalog A–E / `v1_regression_profile` remain budget-disabled and tracing-off.
  - LOGGING REQUIREMENTS: assert metadata-only log expectations in tests where practical; no payload assertions.
  - Files: `tests/unit/test_cognitive_budget.py`, `tests/unit/test_v1_regression_gate.py` (read-only assertions that AD is absent), existing runner serialization tests
  - Depends on: Task 2

<!-- Commit checkpoint: tasks 1-3 -->

### Phase 2: Enforcement and graceful degradation

- [x] Task 4: Integrate `TickBudgetLedger` into `CognitiveLoop.prepare`
  - Deliverable: Construct the ledger at prepare start when `ENFORCED`. Thread it through memory retrieval (truncate hits → `TRUNCATED`), prospective expansion (charge nodes beyond root; clamp depth), counterfactual generation (charge each kept scenario against branches; clamp depth), theory-of-mind / epistemic **target** updates (cap distinct other agents via `max_tom_targets` — **not** `TheoryOfMindPolicy.max_hypotheses`; do not clamp epistemic nesting depth), reflection gating (effective gap floor + skip → `SKIPPED`), and every cognition-boundary LLM call that enters `provider.generate` inside `prepare`. Effective caps use `min(local_cap, tick_remaining, tick_limit)` against `ProspectivePolicy` / `CounterfactualPolicy` / retriever / reflection locals. Tick timeout is independent of `ProspectivePolicy.timeout_seconds`. Keep `BudgetExhaustedReason` distinct from `ProspectivePruneReason`. Intention and planning always run. On any exhaustion, degrade per locked priority and continue. Expose `last_cognitive_budget_audit()` on the loop (side channel; no proposal-schema bump). Consolidation stays out of prepare charging unless it actually runs inside `prepare`.
  - LOGGING REQUIREMENTS: DEBUG `tick_budget_charge` with dimension/used/remaining. WARN on first exhaustion per dimension. INFO not required per charge. Never log stage payloads.
  - Files: `src/agents/cognition/loop.py`, `src/agents/cognition/memory.py`, `src/agents/cognition/prospective.py`, `src/agents/cognition/prospective_selection.py`, `src/agents/cognition/imagination.py`, `src/agents/cognition/counterfactual.py`, `src/agents/cognition/counterfactual_selection.py`, `src/agents/cognition/theory_of_mind.py`, `src/agents/cognition/theory_of_mind_selection.py`, `src/agents/cognition/epistemic.py`, `src/agents/cognition/reflection.py`, `src/agents/cognition/world_model_selection.py`, `src/agents/cognition/reconstruction.py`, `src/agents/cognition/production_selection.py`, `src/agents/cognition/competence_selection.py`, `src/agents/cognition/teaching_selection.py`, `tests/unit/test_cognitive_budget.py`
  - Depends on: Task 1, Task 2

- [x] Task 5: Prove graceful degradation still yields one command
  - Deliverable: Property/unit tests covering: zero LLM budget with LLM-assisted stages → deterministic fallback command; branch/depth budget forcing shallow prospective + limited counterfactuals but valid command (`min` with `ProspectivePolicy` locals); memory budget `1` → at most one ranked hit; ToM target budget `0` → no new targets but valid command (`max_tom_targets` unaffected by `TheoryOfMindPolicy.max_hypotheses`); epistemic nesting still follows `EpistemicPolicy.max_depth` (unaffected by planning-depth budget); reflection interval floor skips reflection; injected policy/ledger `clock` trips timeout and stops further expansion (no domain wall clock); identical seeds with `DISABLED` remain bitwise-equal to pre-budget trajectories for a V1-equivalent agent.
  - LOGGING REQUIREMENTS: tests may capture WARN reason codes; forbid assertions on prompt/memory text.
  - Files: `tests/unit/test_cognitive_budget.py`, optionally `tests/unit/test_prospective_imagination.py` / ToM tests for effective-min interaction
  - Depends on: Task 4

- [x] Task 6: Runtime export of budget audits
  - Deliverable: `AgentRuntime` collects per-tick audits; `SimulationRunner.export_cognitive_budget_audits()` harvests typed audits (mirror `export_prospective_audits`); `SimulationRunnerResult.cognitive_budget_audits` exports the in-memory tuple (default empty). `DISABLED` leaves the tuple empty. Do not serialize audits into runner-result JSON in this plan. Checkpointing: audits are not required in `AgentRuntimeCheckpoint` (ephemeral per tick); do not add Alembic.
  - LOGGING REQUIREMENTS: DEBUG `cognitive_budget_audit_exported` with run_id/agent_id/tick/exhausted_count. Never log limits as free text beyond numeric fields already on the audit.
  - Files: `src/simulation/agent_runtime.py`, `src/simulation/runner.py`, `src/simulation/runner_models.py` (result type), tests
  - Depends on: Task 4

<!-- Commit checkpoint: tasks 4-6 -->

### Phase 3: Trace projection

- [x] Task 7: Expose budget consumption on cognition traces
  - Deliverable: Extend `CognitionTraceCountKey` and add projection-only `CognitionTraceStageKind.BUDGET_SUMMARY`. **Append `BUDGET_SUMMARY` as the final member of `SCIENTIFIC_TRACE_STAGE_SEQUENCE`** in `src/agents/cognition/trace.py` so sequence walkers emit it. Projector consumes the audit / ledger snapshot and emits `BUDGET_SUMMARY` last. Stage cuts use `TRUNCATED` / `SKIPPED` + existing `reason_code` slot with closed token `budget_exhausted` (no free text; do not add `DEGRADED` status). Keep `COGNITION_TRACE_SUMMARY_SCHEMA` unchanged. Tracing-off path unchanged. Soft-fail sink behavior unchanged. Wire audit into `project_cognition_trace_stages` / `maybe_append_cognition_trace` call path without a CognitiveLoop ordinal / `_STAGE_ORDER` entry.
  - LOGGING REQUIREMENTS: DEBUG `cognition_trace_budget_projected` with invocation_id, exhausted_count, stage_count. Never log payloads.
  - Files: `src/agents/cognition/trace.py`, `src/agents/cognition/__init__.py`, `src/simulation/cognition_trace.py` (if projector args need the audit), `tests/unit/test_cognition_trace_models.py` (or equivalent)
  - Depends on: Task 1, Task 4, Task 6

- [x] Task 8: Trace/trajectory isolation proofs
  - Deliverable: Tests that enabling tracing with budget `DISABLED` does not change `exact_trajectory_hash`; enabling budget `ENFORCED` may change subjective decisions and therefore trajectories (expected) but never WorldEngine event schema; forbidden attributes remain absent on new trace types; `BUDGET_SUMMARY` appears only when tracing is on and an audit/snapshot is supplied.
  - LOGGING REQUIREMENTS: metadata-only.
  - Files: tests under `tests/unit/` adjacent to existing cognition-trace / trajectory tests
  - Depends on: Task 7

<!-- Commit checkpoint: tasks 7-8 -->

### Phase 4: Experiment, analysis, docs

- [x] Task 9: Register Experiment AD (low-cost vs high-cost)
  - Deliverable: Add `experiment_ad_cognitive_budgets` building `experiment-ad-cognitive-budgets` in `src/experiments/catalog.py` and export it from `src/experiments/__init__.py`. Arms `ad-low-cost` / `ad-high-cost` use the locked composition: `expand_architecture(..., "full_v2_agent")` (today: `prospective_mode=disabled`, architecture schema v6) → for every agent set `prospective_mode=DETERMINISTIC`, `cognitive_budget_mode=ENFORCED`, nested limits from `low_cost_budget_limits()` / `high_cost_budget_limits()` → leave cultural narratives / social ledgers / artifact / naming `DISABLED` → set runner `schema_version=runner-config-v22` on both arms. Shared seed, scenario, stochastic identity; only limits differ. Keep AD off the V1 regression gate. Prefer deterministic stubs / no network. Prove low-cost charges fewer LLM calls / branches than high-cost under the shared seed when both arms run (unit or short integration).
  - LOGGING REQUIREMENTS: INFO `experiment_ad_built` with condition ids and budget digest prefixes (hashes of numeric limits only).
  - Files: `src/experiments/catalog.py`, `src/experiments/__init__.py`, `tests/unit/test_experiment_ad_cognitive_budgets.py` (or extend catalog tests)
  - Depends on: Task 2, Task 4, Task 6

- [x] Task 10: Analysis metric `cognitive_budget@1`
  - Deliverable: Add `src/analysis/cognitive_budget_metrics.py` implementing `compute_cognitive_budget_metrics` / `cognitive_budget@1`. Duck-type audit rows with `getattr` (used counts, exhausted codes, owner/tick). Must not import `agents`, `TickBudgetLedger`, or `AgentRuntime`. Register `MetricFamilyId` + `metric_specification` entry in `src/analysis/specifications.py`; export version + compute from `src/analysis/__init__.py`. Report consumption totals, degradation counts, and a low-vs-high comparison suitable for the AD arms. Empty audit sequence → appropriate `MetricAvailability.ABSENT` keys, not a crash.
  - LOGGING REQUIREMENTS: DEBUG metric assembly with run_id and count fields only. ERROR on schema/ownership mismatches with stable codes.
  - Files: `src/analysis/cognitive_budget_metrics.py`, `src/analysis/specifications.py`, `src/analysis/__init__.py`, unit tests
  - Depends on: Task 6, Task 9

- [x] Task 11: Documentation checkpoint (`/aif-docs`)
  - Deliverable: Update `docs/cognition-runtime.md` (budget mode, ledger, charge rules, degradation, presets, trace `BUDGET_SUMMARY`, and the existing **Preset → schema table**), `docs/architecture.md` Downstream V2 contract mention for Experiment AD / `cognitive_budget@1` / `runner-config-v22` widen rules, and any simulation-runner schema table that lists runner-config versions. Keep README lean; no new top-level doc island. Note that budgets are not a capability flag and AD stays off the V1 gate.
  - LOGGING REQUIREMENTS: n/a for prose; code samples must not invent wall-clock domain defaults.
  - Files: `docs/cognition-runtime.md`, `docs/architecture.md`, optionally `docs/simulation-runner.md`
  - Depends on: Tasks 1–10

<!-- Commit checkpoint: tasks 9-11 -->

## Implementation notes for `/aif-implement`

- Prefer composition (ledger injection) over `if architecture == ...` switches.
- Reuse existing soft-fail / fallback patterns from prospective + reflection LLM paths.
- Keep import-linter edges: `budget.py` must not import `analysis`, `api`, `persistence`, or private `world._*`. Analysis must not import `agents`.
- Register any new `agents.cognition` → `llm` edge only if budget accounting needs a wrapper; prefer charging at existing call sites that already import `llm`.
- Verbose logging is required at ledger boundaries; strip payloads.
- Schema widen is load-bearing: grepping for `RUNNER_SCHEMA_VERSION_V21` membership sets that omit v22 is a required review checklist before Commit 1.
- Nested `CognitiveBudgetLimits` on the simulation side must round-trip as flat v22 JSON keys; clock stays off the runner surface.
- After Commit 4, run unit + architecture suites relevant to cognition/experiments/analysis; do not add AD to `test_v1_regression_gate.py`.
