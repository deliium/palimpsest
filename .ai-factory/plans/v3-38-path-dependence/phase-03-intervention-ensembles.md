# Phase 3: Early-intervention ensembles and generational continuation

Plan: [index.md](index.md)
Tasks: 7–9
Depends on: Tasks 1–6

## Objective

Execute small, predeclared child-only command interventions from an actual common replay prefix, then let normal production cognition continue for generations.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|---|---|---|
| `src/experiments/interventions.py` | `MilestoneOverride`, `CommandOverrideArbiter`, lines 252–307 | Existing trusted override boundary. |
| `src/simulation/runner.py` | effective-command binding/admission, lines 2653–2711 | Replacements still use normal admission and subjective finalization. |
| `src/world/actions.py` | `Give`, lines 93–104; `Wait` | Existing commands suffice; refusal is operationalized as no transfer, not a moral state. |
| `src/experiments/generational_comparison_base.py` | `generational_comparison_base`, `assert_comparable_generational_conditions` | Rich v55 scenario and deterministic distribution restrictions. |
| `src/experiments/generational_execution.py` | `GenerationalExecutionContext`, `execute_generational_assignment` | Archive/factory lifecycle pattern, not a shared-prefix executor. |
| `src/simulation/branch_service.py` | `materialize_objective_fork`, line 994 | Rematerialize actual objective prefix before restoring child. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/experiments/path_dependence_interventions.py` | create | Closed scheduled action arbiter and treatment ledger. |
| `src/experiments/path_dependence_scenario.py` | create | Experiment BN recipes and exact pre-treatment eligibility. |
| `src/experiments/path_dependence_catalog.py` | create | Typed grouped-only registration and ID guard; not an `ExperimentDefinition`. |
| `src/experiments/path_dependence_runner.py` | create | Prefix capture and child continuation executor. |
| `src/experiments/path_dependence_ports.py` | create | Injected fork materializer/replay and execution context protocols. |
| `src/experiments/catalog.py`, `src/experiments/__init__.py` | modify | Add off-gate BN discovery without pretending independent cells share history. |
| `src/experiments/coordinator.py`, `src/experiments/matrix_runner.py`, `src/experiments/matrix_expand.py` | modify | Reject grouped IDs before independent assignment expansion or manifest writes. |
| `tests/unit/test_path_dependence_interventions.py`, `tests/unit/test_path_dependence_scenario.py`, `tests/unit/test_path_dependence_runner.py` | create | Scheduled action, scenario and group-execution tests. |

## Task 7: Apply bounded interventions through ordinary admission

### Intent

Distinguish requested treatment, command replacement and actually committed action. A rejected Give is not evidence that food was shared.

### Implementation Steps

1. Implement `PathDependenceArbiter` conforming to `CommandOverrideArbiter`, compiled from validated closed descriptors into fresh `Give` or `Wait` values. Install only after child restoration. Untouched arms install no arbiter.
2. At exactly the scheduled tick/actor replace the proposed command, call existing effective-command binding, and let the engine admit/resolve it normally. A schedule is selected once and acknowledged only after committed resolutions; no retry on a more favorable later tick, event deletion, forced transfer or belief editing.
3. Record a research-only treatment ledger with requested ID/tick/actor, proposed/effective kinds, resolution status/reason, event/receipt correlation and selected/committed/missed status. If actor is terminal/missing or schedule is not reached, mark missed; do not silently consume as applied. Preserve bounded descriptor provenance in the sealed branch artifact.
4. Enforce max replacements and no duplicate actor/tick slots. After the last configured tick, the arbiter is a passthrough and cannot sustain cooperation or inject culture. Multiple small actions form one named compound protocol; report effects for that protocol, not separate per-action effects.

### Required Interfaces and Contracts

Arbiter schedules are immutable per child and acknowledgements are child-local. A process-loss recovery may reconstruct a fresh arbiter only for a child whose durable RunId has never been created; partially written child runs are not retried or replaced in v1. Primary comparison is intention-to-intervene (assigned arm), including rejection/missed treatment counts. Applied-only subsets are diagnostic and never the default estimand. The shared setup compiler uses the separate Task 1 command allowlist; its final action is before `min(F)`, it is detached before capture, and it never carries consumed setup state into a child treatment arbiter.

### Requirement Evidence

User shares/refuses example and small-intervention ensembles; existing admission authority and fail-closed rules.

### Error Handling and Logging

INFO selection/completion counts and safe intervention ID; DEBUG proposed/effective kinds and status, not item/recipient payloads; WARN missed/rejected reason codes. Malformed schedule fails preflight; engine rejection is valid experiment evidence, not a technical run failure.

### Tests

`test_path_dependence_interventions.py`: Give vs Wait vs untouched; fresh commands; no pre-F override; one acknowledgement per slot; rejection, death, missing actor, early stop, multiple actions, duplicate keys and cap; same schedule child independence; bound effective command drives normal subjective finalization.

### Acceptance Criteria

All treatments flow through normal admission; manifests separate assignment from realized exposure and no post-hoc retries manufacture exposure.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_path_dependence_interventions.py -q`

## Task 8: Define Experiment BN and pre-treatment eligibility

### Intent

Provide a reproducible food-sharing demonstration and a general bounded schedule recipe without promising emergent social effects.

### Implementation Steps

1. Add `historical_contingency_scenario()` returning a `PathDependenceSpec` and catalog wrapper `experiment_bn_historical_contingency`. ID is `historical_contingency@1`; it remains outside V1 A–E. Introduce frozen `GroupedExperimentRegistration(experiment_id, label_code, execution_kind)` with `execution_kind='path_dependence'` and `GROUPED_EXPERIMENT_IDS` in `path_dependence_catalog.py`; the builder registry has a separate typed callable returning `PathDependenceSpec`. Do not widen `ExperimentDefinition` or its codec with an unversioned metadata field, and never add BN to `OFF_GATE_MATRIX_EXPERIMENT_IDS`. Existing standard catalog builder return types remain unchanged; BN discovery explicitly identifies grouped-only execution.
2. Build the named `bn-food-opportunity-v1` shared diagnostic fixture from `generational_comparison_base`, retaining its graph, founder IDs, default seed derivation and normal objective authority but explicitly replacing physical setup, not silently inheriting AY's empty inventories and exhausted resources. At tick zero co-locate `body-origin` and `body-spring` at `loc-origin`, give `body-origin` one `ItemKind.FOOD` item `bn-reserved-food` with `ItemLoad(1)` and matching inventory, and set every location body capacity to 16 and item capacity to at least 24. Reset all initial bodies to health 100, hunger/thirst/fatigue 0 and temperature 37. Use common replay-significant rules with `metabolism_hunger=metabolism_thirst=metabolism_fatigue=0.1`, `temperature_lerp_factor=0.0`; leave damage, action relief and lifecycle death rules active. At every location install named food/water resources with quantity/maximum 100, regeneration 10 per tick and the appropriate resource units; retain existing IDs where present and derive stable `bn-food-<location>` / `bn-water-<location>` IDs for missing nodes. These are declared benign physical-fixture choices shared by every arm, not claims about ecological realism or social outcomes. Use a common setup of `Wait` for `agent-origin` and `agent-spring` on every tick before F, sealed in the spec; at F the setup ends and the item/custody/co-location witness must still be checked. No food, resource or body is injected after tick zero. For this default single-F demonstration the setup count is `2*F`; multi-F custom recipes must obey the `min(F)` cutoff instead of continuing setup through earlier child treatments.
3. Explicitly set long-run controls: F=100, H=1100, fixed lifespan 240, interval admissions every 20 ticks, generation labels every 40 ticks, cap 16, maximum generation index 40, extinction stopping disabled and `stop_on_all_agents_terminal=False`. The smoke profile uses F=4/H=36, fixed lifespan 12, admissions every two ticks, generation labels every four ticks, cap 16 and maximum generation index 16 (not the BM default of six); disable extinction/runtime-terminal stopping identically. Both use deterministic initialization/lifespan distributions. This preserves founder survival to the treatment opportunity without guaranteeing survival afterward, cooperation or institutions.
4. At finalized F, resolve configured founder `agent-origin`, recipient `body-spring` and item `bn-reserved-food` once from detached pre-treatment evidence. Require a living original founder, distinct living co-located recipient, founder possession of the named transferable food item and ordinary admission prerequisites. Freeze targets for all children. Custom configurations use their explicitly named targets, not these demonstration defaults. Do not substitute a later-born agent or pick a target from post-treatment outcomes.
5. If prerequisites are absent, mark the parent/F `prefix_ineligible` with counts/reason and no branches. Report these blocks in denominators. Do not move food, resurrect founders, re-seed repeatedly until eligible, or silently select a different F. User-supplied common setup uses the separate bounded Task 1 physical command schedule and is recorded as setup, not treatment; it never bypasses normal admission. A setup rejection yields an honest eligibility failure rather than direct world repair.
6. Default scientific contrast: `share` schedules `Give` at F; `withhold` schedules `Wait` at F. Optional `untouched` and two identical untreated negative-control arms are separate named comparisons. “Refuses” means no transfer that tick; no explicit refusal communication, moral label or guaranteed recipient interpretation is invented. Ensembles vary named early schedules and F values with explicit contrasts rather than a combinatorial automatic causal search.
7. For the demonstration's founders set existing `social_norm_mode`, `social_convention_mode`, `semantic_naming_mode`, `artifact_interpretation_mode`, `cultural_narrative_mode` and `institution_concept_mode` to `DETERMINISTIC`, retaining BM's deterministic skill/teaching/communication modes. Set run `knowledge_genealogy=example_knowledge_genealogy_spec()` and keep explicit cultural provenance plus its owned flag. Use the accepted `species_default_developmental_v1` empty initialization profile for entrants; it enables learning/norm/narrative channels but not institution concepts. Report that institution-channel coverage limit rather than silently enabling a new profile. Keep remaining run/mode prerequisites exact under v55 validation; all ledgers start empty and no technique, narrative, norm or institution is seeded as knowledge. Do not enable `institutional_economy` or claim complete cultural transmission. Empty cultural baselines legitimately make retention selectors unknown; Task 11 fixtures separately prove nonempty-baseline computation.
8. Add `require_independent_execution(experiment_id)` using `GROUPED_EXPERIMENT_IDS`; call it in `ExperimentCoordinator.run_all()` before `materialize_assignments`, and in matrix base resolution/`MatrixBatchRunner.run()` before expansion or manifest creation. Guard both `MatrixCatalogBase` grouped IDs and embedded config `experiment` metadata; a plain copied v55 config with no grouped identity remains an ordinary config and does not claim shared-prefix lineage. Raise safe `grouped_execution_required` without constructing a runner or writing a cell. Task 15 connects CLI discovery to the separate registry.

### Required Interfaces and Contracts

All arms of one parent/F have identical configs, complete prefix and evaluation windows; only scheduled commands/assignment differ. Catalog metadata advertises grouped execution requirement and does not add a synthetic metric family. Scenario construction itself cannot query post-F outcomes.

### Requirement Evidence

User tick-100 example, generations and seven outcome domains; ARCHITECTURE no scripted emergence and explicit initialization gates.

### Error Handling and Logging

`prefix_ineligible` is an explicit scientific eligibility result. Invalid lifespan/horizon/stop configuration or unsupported modes fail preflight. Logs contain profile IDs, F/H, agent counts and safe reason codes only.

### Tests

`test_path_dependence_scenario.py`: real BM base converted through declared fixture builder, exact initial food-holder/inventory consistency, distinct resource IDs/regeneration, common setup codec/budget, long profile founder lifespan exceeds F, founder absent/dead/ineligible, co-location/custody checks, smoke horizon not preempted by inherited generation limit, multiple post-F cohorts, exact enabled/disabled founder/entrant mode table, no knowledge injection or flag leakage, same configs in every arm, setup included in prefix identity, typed grouped discovery and coordinator/matrix rejection before any provider/repository/manifest side effects.

### Acceptance Criteria

The food-sharing example is operationally precise and can produce either an eligible experiment or an honest ineligibility result; no social outcome is installed to make it visually convincing.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_path_dependence_scenario.py tests/unit/test_experiment_bm_execution.py -q`

## Task 9: Execute shared prefixes and isolated child continuations

### Intent

Compute each common history once per fresh group, materialize replay children, then run many generations with normal production policy.

### Implementation Steps

1. Define `PathDependenceExecutionContext` with runner dependency factories, injected fork materializer and replay opener, artifact sink, source identity and capture configuration. `experiments` depends only on public simulation ports; concrete repositories/SQL composition belong to `research_runner`.
2. Implement `PathDependenceBatchRunner.run(spec, context)` grouped by numeric seed/ordinal/replicate. Build one parent from tick zero, install the declared common-setup arbiter, call `initialize_finalized_boundary()`, and execute `run_tick()` to each ascending F without calling `finish_run`, then freeze a complete checkpoint. Detach the consumed setup arbiter before capture; it never schedules an action at/after `min(F)`. Parent continues unchanged to later F values; children execute serially initially (`prepare_parallel=False`) with independent resources. Detect terminal/aborted receipts without tick progress rather than looping forever waiting for F.
3. For each eligible F, precommit slot assignments, materialize each child using `BranchService.materialize_objective_fork`, restore child replay at its own head through `ReplayService`, then use `from_fork_checkpoint`. Validate pre-treatment state equivalence before installing an arbiter. Do not use legacy `create_research_fork` with a fake no-op intervention or assume communication-remove is implemented.
4. Construct child collectors before invoking `from_fork_checkpoint(..., cultural_sink=recorder)`; factory-owned baseline publication occurs after owner restoration but before returning the started runner. Validate the one boundary-F baseline witness, install the branch treatment arbiter, then continue `runner.run()` to absolute H or an actual stop reason. Do not install a cultural sink afterward. Before writing any seal classify `result.stop_reason` using `runner_stop_is_failure`; technical/finalization/historical-artifact failures produce failure records only, while genuine early scientific stops retain censored endpoint outcomes. Finalize artifacts and close child resources. Parent snapshots/commits and complete owner-state digest must remain unchanged after each child. Parent is a prefix source, not a completed generational result with an invented terminal reason.
5. Treat all branches/F values/replicas under the same numeric seed as dependent. Preserve root lineage even when resuming from another attempt. Bound live memory to one parent checkpoint plus one child; release old checkpoint state after all its children finish. Explicit configured caps bound seeds, F values, replicas and total branches before starting.

### Required Interfaces and Contracts

`await PathDependenceBatchRunner.run(...) -> PathDependenceExecutionSummary`. Real objective repositories are mandatory for production replay materialization. Unit tests inject real-contract fake repositories. No independent-cell matrix wrapper may claim a shared prefix; generic matrix remains unchanged. Default fake provider only; unsupported providers rejected before any writes.

### Requirement Evidence

User forked replay/common-history/ensemble requirements; current branch service and replay head authority; configured no-branch planning preference does not constrain simulation research branches.

### Error Handling and Logging

Typed `PathDependenceExecutionError(code)`; parent checkpoint failure blocks all associated slots, child technical failure marks only that child failed, treatment rejection remains a completed branch. INFO group/F/child state transitions and counts, DEBUG safe stage/timing/counters; ERROR no payload-bearing exception text. Partial writes remain unsealed and never count as completed. Created partial child runs are never automatically retried under a new scientific identity; validated resume may launch only untouched slots.

### Tests

`test_path_dependence_runner.py`: one prefix execution per group, star F design, exact tick 100 boundary, no finalization used as pause, modern child replay restore, parent/sibling isolation, per-child cleanup after failure, no automatic rerun of ineligible prefix, budget preflight, production policy resumes after schedule, admitted entrants carry no copied founder knowledge.

### Acceptance Criteria

An eligible group yields genuine replay children with identical pre-treatment experience and explicit lineage, not independent fresh runs with coincident seeds.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_path_dependence_runner.py tests/unit/test_path_dependence_replay_parity.py -q`

## Phase Risks and Mitigations

- Long histories may eliminate the founder/opportunity: pre-treatment eligibility is reported and never patched after seeing outcomes.
- More interventions increase interpretation ambiguity: fixed small budgets and explicit compound-protocol contrasts prevent unrecorded searching.

## Phase Completion Checklist

- Tasks 7–9 pass; grouped replay execution does not use independent-cell shortcuts.
- Progress remains exclusively in `index.md`.
