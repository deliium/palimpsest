# Implementation Plan: Cognitive Architecture Variants as Experiment Configurations

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-03
Improved: 2026-10-03 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete milestone; this plan formalizes named architecture compositions over already-owned cognition modes/flags and does not claim `multi_hop_testimony_tracking`.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M6 — Remaining V2 Capability Flags

## Compatibility contract

This plan introduces first-class named cognitive architecture variants that **expand** into existing `AgentCognitionSpec` modes and `V2CapabilityFlags`. It must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants intact. `WorldEngine` remains the only objective mutation authority. Cognition still receives immutable per-agent `Observation` / `Perspective` only — never `WorldState`, `WorldEvent` stores, or another agent's private cognition.
2. Capability flags stay opt-in and default-off. Do **not** add a new `V2CapabilityFlags` slot. Do **not** own `multi_hop_testimony_tracking`. Owned flags (`advanced_social_inference`, `predictive_world_model`, `extended_self_model`, `short_term_emotional_state`) may be enabled by architecture expansion only when that architecture declares them.
3. V1 regression gate stays green under flags-off and tracing-off. Catalog A–E and the reference scenario keep current trajectories. Architecture-matrix experiments stay **off** `tests/unit/test_v1_regression_gate.py`.
4. **No runner-config schema bump for `architecture_id`.** Default write surface and accepted sets stay as today. Architecture ids live on the experiments / cognition registry layer; runner JSON continues to encode expanded modes and flags only. Exact key-set discipline is unchanged. Per-architecture arms still select an **existing** schema version required by those modes (v4 / v6 / v7) — they do not invent a new schema id.
5. No scripted emergence. Architecture names are configuration labels, not friend/enemy/leader/culture roles or milestone scripts.
6. No LLM → world shortcuts. Structured LLM output still requires cognition translation + normal admission.
7. Experiments stay reproducible. Architecture arms share world scenario, seed matrix, and stochastic identity; only architecture expansion differs. Prefer deterministic fakes / stubs.
8. Optional cognition tracing stays outside the objective fold. Tracing on vs off must not change `exact_trajectory_hash` when architectures expand to V1-equivalent (flags-off) wiring.

## Goal

Formalize interchangeable cognitive architecture variants as **first-class experiment configurations** so the same objective world and seed can run under:

| Architecture id | Role |
| --- | --- |
| `reactive_baseline` | Minimal reactive agent (reference memory, imagination off) |
| `v1_memory_agent` | V1 production memory + imagination defaults |
| `reconstructive_memory_agent` | Reconstructive-v2 memory focus |
| `imagination_agent` | Imagination (+ prospective) focus |
| `reflection_agent` | Reflection-enabled metacognition |
| `theory_of_mind_agent` | First-order ToM (`advanced_social_inference`) |
| `full_v2_agent` | Cognitive-core V2: reconstructive_v2 + imagination + reflection + all **owned** capability flags |

Define stable stage-slot interfaces for:

perception · retrieval · reconstruction · beliefs · world_model · reflection · imagination · motivation · theory_of_mind · planning

Compose architectures from slot bindings + capability declarations. **Forbid** runtime `if architecture == ...` in `CognitiveLoop`, `AgentRuntime`, or `SimulationRunner` tick paths. Prefer composition tables and injected implementations (including passthrough / null-object stages).

Provide capability declarations, fail-closed compatibility validation, and contract tests proving each architecture produces a valid closed `AgentCommand` (`require_agent_command`).

## Locked scope decisions

1. **`full_v2_agent` = cognitive core only.** Owned `V2CapabilityFlags` + `RECONSTRUCTIVE_V2` + imagination enabled + `ReflectionMode.DETERMINISTIC`. Opt-in social ledger modes (reputation, norms, conventions, naming, narratives, territorial, group, communication strategy, skill/teaching, artifacts, production) stay `DISABLED` unless a later plan composes them into additional architecture ids. Prospective stays `DISABLED` on `full_v2_agent` so its schema can be `runner-config-v6` (reflection) without also requiring v7.
2. **`architecture_id` is experiments/registry metadata only.** No `runner-config-v22`. Expansion materializes ordinary `SimulationRunnerConfig` bytes; fingerprints remain mode/flag based. Experiment conditions carry architecture id in `condition_id` / `label_code`; `architecture_definition_digest` is diagnostics-only (logs / label), never a runner JSON key.

## Design Decisions (locked)

### Composition over switches

```text
ArchitectureDefinition
  ├── architecture_id (stable token)
  ├── CapabilityDeclaration (required / forbidden flags + modes)
  └── StageSlotBindings (slot → implementation_key)
        │
        ▼
 validate_architecture(def, mode_snapshot)  -- fail closed
        │
        ▼
 expand_architecture(def, base_runner) → SimulationRunnerConfig   # AUTHORITATIVE
        │
        ▼
 SimulationRunner._cognition_config_for + _memory_retriever_for
        │
        ▼
 build_cognitive_loop(CognitionLoopConfig)    -- injected stages only
```

- `CognitiveLoop` **never** stores or branches on `architecture_id`.
- Mode enums on `CognitionLoopConfig` / injected policies remain the execution surface.
- **Single composition path:** `expand_architecture` → `SimulationRunnerConfig` is authoritative for experiments. Cognition helpers compose service-free stage objects from an `ArchitectureModeSnapshot` (or from modes/flags already on the expanded config). They must **not** re-derive flag→mode mapping differently from `simulation.runner._cognition_config_for`.
- A closed `STAGE_FACTORY_TABLE` builds **service-free** implementations from binding keys. Retrieval / reconstruction slots are **declaration keys** that expand to `MemoryMode`; concrete `ScopedMemoryRetriever` / reconstructor wiring stays in `simulation.runner._memory_retriever_for` (needs `MemoryService`).
- Forbidden pattern in production tick/cognition paths:

```python
# FORBIDDEN
if architecture_id == "theory_of_mind_agent":
    ...
```

Allowed: table lookup by `(slot, implementation_key)` and existing per-stage passthrough objects.

### Stable stage-slot interfaces

Add (or promote) Protocols under `src/agents/cognition/contracts.py` (and thin wrappers where policies already exist):

| Slot | Protocol (locked name) | Existing seam |
| --- | --- | --- |
| `perception` | `PerceptionInterpreter` | already |
| `retrieval` | `MemoryRetriever` | already (runner injects) |
| `reconstruction` | `ReconstructionStage` (new cognition Protocol; **does not** redefine `memory.contracts.MemoryReconstructor`) | wraps / selects among existing `memory.contracts.MemoryReconstructor` impls (`DeterministicMemoryReconstructor`, `LLMMemoryReconstructor`) |
| `beliefs` | `BeliefRevisionStage` (new Protocol; owner-scoped belief/relationship revision intent production — a memory-update slot, **not** a new `CognitiveLoop` ordinal) | `SubjectiveRevisionHook` / memory updates |
| `world_model` | `WorldModelStage` (new Protocol) | `WorldModelPolicy` + mode |
| `reflection` | `ReflectionStage` (new Protocol) | `ReflectionPolicy` / engine |
| `imagination` | `FutureImagination` | already |
| `motivation` | `MotivationEvaluator` | already |
| `theory_of_mind` | `TheoryOfMindStage` (new Protocol) | `TheoryOfMindPolicy` |
| `planning` | `Planner` (+ intention selection remains `IntentionSelector`, bound under planning compose) | already |

Rules:

- Each Protocol documents inputs/outputs with existing cognition models (`InterpretedPerception`, `RetrievedMemoryContext`, `PossibleFutures`, `ActionPlan`, …).
- Missing capability ⇒ bind the slot's **passthrough / empty** implementation (not a mid-loop architecture switch).
- New Protocols must remain Pydantic-free and must not import `simulation` / `experiments` / `WorldState`.
- Never shadow the name `MemoryReconstructor` from `memory.contracts`.

### Capability declarations

```text
CapabilityDeclaration:
  required_flags: frozenset[str]      # subset of V2CapabilityFlags names
  forbidden_flags: frozenset[str]
  required_modes: Mapping[str, str]   # e.g. memory_mode → reconstructive_v2
  forbidden_modes: Mapping[str, frozenset[str]]
  required_slots: frozenset[StageSlot]
  implementation_keys: Mapping[StageSlot, str]
```

`validate_architecture_compatibility(definition, mode_snapshot) -> None`:

- Take a cognition-local `ArchitectureModeSnapshot` (flag name→bool, mode tokens as strings) filled at the experiments/simulation boundary — do **not** import `simulation` from cognition.
- Fail closed with stable reason codes (`architecture_missing_flag`, `architecture_forbidden_flag`, `architecture_mode_mismatch`, `architecture_slot_unbound`, `architecture_unknown_impl`, `architecture_unimplemented_flag`).
- Enabling `multi_hop_testimony_tracking` via any architecture fails closed (`capability_unimplemented`) — architectures must not declare it required.
- Log DEBUG validation inputs (architecture_id, flag names, mode tokens) without observation/memory payloads; INFO on successful expand; ERROR on fail-closed codes.

### Preset expansion table (locked)

Shared base: identical `WorldScenarioSpec`, agent identities, tracing off, social ledger modes `DISABLED`.

| architecture_id | memory | imagination | reflection | prospective | mortality appraisal | owned flags | schema_version | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `reactive_baseline` | `REFERENCE` | `DISABLED` | `DISABLED` | `DISABLED` | `DISABLED` | all off | `runner-config-v4` | reference retrieval; present-state imagination path |
| `v1_memory_agent` | `RECONSTRUCTIVE` | `ENABLED` | `DISABLED` | `DISABLED` | `ENABLED` | all off | `runner-config-v4` | production V1-equivalent defaults |
| `reconstructive_memory_agent` | `RECONSTRUCTIVE_V2` | `ENABLED` | `DISABLED` | `DISABLED` | `ENABLED` | all off | `runner-config-v4` | dynamics via existing retriever path |
| `imagination_agent` | `RECONSTRUCTIVE` | `ENABLED` | `DISABLED` | `DETERMINISTIC` | `ENABLED` | all off | `runner-config-v7` | mirrors Experiment J deep arm schema rule |
| `reflection_agent` | `RECONSTRUCTIVE` | `ENABLED` | `DETERMINISTIC` | `DISABLED` | `ENABLED` | all off | `runner-config-v6` | mirrors Experiment G schema rule |
| `theory_of_mind_agent` | `RECONSTRUCTIVE` | `ENABLED` | `DISABLED` | `DISABLED` | `ENABLED` | `advanced_social_inference=True` only | `runner-config-v4` | other owned flags off |
| `full_v2_agent` | `RECONSTRUCTIVE_V2` | `ENABLED` | `DETERMINISTIC` | `DISABLED` | `ENABLED` | all four owned `True` | `runner-config-v6` | social ledgers remain disabled |

Schema selection must satisfy existing exclusivity rules (`v6_requires_reflection`, `v7_requires_prospective`, etc.). Expansion sets cognition modes **and** `capability_flags` so `_cognition_config_for` produces the intended loop config without architecture-aware branches.

### Architecture digest (diagnostics only)

`architecture_definition_digest(definition) -> str` in `agents.cognition.architectures`:

- Stable hash over `architecture_id`, capability declaration fields, and `implementation_keys` (canonical key order, LF, no payloads).
- Experiments log the digest at expand/matrix build; may embed a short prefix in `label_code`.
- Must **not** become a runner JSON field or alter `runner_config_fingerprint` beyond the expanded modes/flags themselves.

### Module placement

- `src/agents/cognition/architectures.py` — `StageSlot`, `CapabilityDeclaration`, `ArchitectureDefinition`, registry, validate, digest, service-free stage factory table, snapshot→`CognitionLoopConfig` helpers that cognition owns.
- `src/experiments/architectures.py` — experiment-facing `expand_architecture`, schema selection, shared-seed matrix builder; imports cognition registry + public simulation contracts only (never API/persistence). Reuse/extend catalog `_with_agent_modes` **plus** `dataclasses.replace(..., capability_flags=...)` (same pattern as Experiments H/I/L).
- Do **not** create a new top-level package.
- `experiments` must not be imported by `agents.cognition` (import-linter `cognition_must_not_import_orchestration`).

### Same world + seed contract

Locked experiment: **`experiment-ac-cognitive-architectures`** (metric family name if needed: `cognitive_architecture_matrix@1` stays analysis-only / optional; not required for this plan’s gate).

- Builder: `experiment_ac_cognitive_architectures` in `src/experiments/catalog.py`.
- Condition ids: `ac-<architecture_id>` (e.g. `ac-reactive_baseline`).
- One `ExperimentDefinition` with one condition per architecture id.
- Shared `ExperimentSeedMatrix`, shared scenario layout (`paired_world_group`), shared stochastic identity.
- Arms differ only by architecture expansion (modes/flags/schema version required by those modes).
- Off the V1 regression gate; do not import AC from `tests/unit/test_v1_regression_gate.py`.
- Export from `src/experiments/__init__.py`.
- Objective scenario fingerprint equal across arms; `runner_config_fingerprint` / cognition fingerprint may differ by design.

### Contract tests (mandatory)

For **each** registered architecture:

1. Expand against a shared miniature world bootstrap + seed.
2. Build loop via the authoritative path (expand → runner binding / `_cognition_config_for` + `build_cognitive_loop`) with deterministic fixtures.
3. Run at least one cognition invocation (deterministic fakes; no network).
4. Assert `require_agent_command(result.command)` succeeds (exact closed class).
5. Assert no architecture switches in hot paths (Task 11).

Also test:

- validation rejects mismatched flags/modes with stable codes
- `full_v2_agent` enables all owned flags and still fails closed if `multi_hop_testimony_tracking` is forced on
- reactive vs full_v2 share scenario fingerprint / seed matrix identity fields
- per-architecture schema versions construct without schema reason codes
- V1 regression gate module does not import Experiment AC

### Logging

- Module loggers: `agents.cognition.architectures`, `experiments.architectures`.
- DEBUG: architecture_id, slot→impl keys, required/forbidden flag names, expand diffs (mode tokens only), digest.
- INFO: `architecture_expanded`, `architecture_validated`, `experiment_ac_built` with condition ids.
- ERROR: fail-closed reason codes only; never log observations, reconstructions, beliefs, prompts, or utterance text.

### Docs

Mandatory docs checkpoint (`Docs: yes`): update `docs/cognition-runtime.md` with architecture registry, stage slots (including `ReconstructionStage` naming), expansion rules, schema table, digest semantics, and the no-`if architecture` rule. Cross-link from `docs/architecture.md` Downstream checklist note that architecture variants are composition presets, not new flags. README needs no marketing rewrite — link only if the docs landing already indexes cognition-runtime.

## Non-Goals

- Claiming or implementing `multi_hop_testimony_tracking`
- New `V2CapabilityFlags` fields
- New runner-config schema version for `architecture_id`
- Rewriting every mode check inside `CognitiveLoop` in one pass (only introduce Protocols + factories + passthrough bindings; leave orthogonal social-ledger mode checks as-is unless a binding already replaces them)
- Constructing `ScopedMemoryRetriever` inside cognition factories (runner owns service injection)
- Putting architecture matrix on the V1 regression gate
- Godot / observer presentation work
- LLM provider API lifecycle composition
- Collapsing all social ledger modes into `full_v2_agent`

## Commit Plan

- **Commit 1** (after tasks 1–3): `feat(cognition): add architecture stage slots and capability declarations`
- **Commit 2** (after tasks 4–7): `feat(cognition): compose architecture variants without runtime switches`
- **Commit 3** (after tasks 8–11): `feat(experiments): shared-seed cognitive architecture matrix`
- **Commit 4** (after tasks 12–13): `test(cognition): contract-test architecture structured actions`
- **Commit 5** (after task 14): `docs(cognition): document architecture variant registry`

## Tasks

### Phase 1: Stage slots and capability contracts

- [x] Task 1: Define `StageSlot`, `CapabilityDeclaration`, and `ArchitectureDefinition`
  - Create `src/agents/cognition/architectures.py` with frozen dataclasses / `StrEnum` for the ten slots.
  - Include `architecture_id`, capability declaration, and `implementation_keys: Mapping[StageSlot, str]`.
  - Validate types in `__post_init__`; reject blank ids; reject unknown slot keys.
  - LOGGING: DEBUG construct; ERROR on invalid enum/id with `reason_code`.
  - Files: `src/agents/cognition/architectures.py`, export from `src/agents/cognition/__init__.py` only the public registry API needed by experiments/tests.
  - Depends on: none

- [x] Task 2: Add missing stage Protocols for reconstruction, beliefs, world model, reflection, ToM
  - Extend `src/agents/cognition/contracts.py` with `ReconstructionStage`, `BeliefRevisionStage`, `WorldModelStage`, `ReflectionStage`, `TheoryOfMindStage`.
  - **Do not** define a cognition Protocol named `MemoryReconstructor` — that name belongs to `memory.contracts.MemoryReconstructor`.
  - `ReconstructionStage` documents how cognition selects/wraps existing memory reconstructors; `BeliefRevisionStage` is a memory-update slot, not a new loop ordinal.
  - Wrap or adapt existing policy/engine call shapes; do not invent second belief stores or objective world access.
  - Document Protocol methods with existing artifact types; fail closed on owner mismatch via existing `CognitionContractError` patterns where applicable.
  - LOGGING: no payload logs in Protocol modules; adapters log DEBUG entry/exit metadata only.
  - Files: `src/agents/cognition/contracts.py`, thin adapter modules only if needed beside existing `reconstruction.py` / `world_model.py` / `reflection.py` / `theory_of_mind.py`.
  - Depends on: none (parallel with Task 1)

- [x] Task 3: Implement `validate_architecture_compatibility` with stable reason codes
  - Validate against cognition-local `ArchitectureModeSnapshot` (flags + mode tokens), not a live `SimulationRunnerConfig` import.
  - Reject unbound slots, unknown implementation keys, and any required `multi_hop_testimony_tracking`.
  - Unit tests for each reason code.
  - LOGGING: INFO validated; ERROR `architecture_*` reason codes.
  - Files: `src/agents/cognition/architectures.py`, `tests/unit/test_cognitive_architecture_validation.py`.
  - Depends on: Task 1

<!-- Commit checkpoint: tasks 1-3 -->

### Phase 2: Composition factory, presets, digest, expand

- [x] Task 4: Build closed `STAGE_FACTORY_TABLE` and compose helpers (service-free only)
  - Map `(StageSlot, implementation_key)` → callable for **service-free** stages: perception, imagination, motivation, planning/intention, passthrough/enabled world-model / ToM / reflection **policies**, belief-revision hooks that need no `MemoryService`.
  - Retrieval / reconstruction keys (`reference`, `reconstructive`, `reconstructive_v2`, …) are **declaration tokens** recorded on the definition and expanded to `MemoryMode`; they do **not** construct `ScopedMemoryRetriever` here.
  - `compose_loop_config_from_snapshot(snapshot) -> CognitionLoopConfig` iterates bindings / mode tokens only — never branches on `architecture_id`. Must stay consistent with `simulation.runner._cognition_config_for` flag→mode mapping (no second divergent mapper).
  - LOGGING: DEBUG per-slot bind; INFO `cognitive_loop_composed_from_snapshot` with factory_version (architecture_id only when caller supplies it for logs).
  - Files: `src/agents/cognition/architectures.py`, wire into `build_cognitive_loop` / `CognitionLoopConfig` only through explicit fields (no architecture field on the loop).
  - Depends on: Tasks 2, 3

- [x] Task 5: Register the seven locked architecture presets
  - Populate registry `ARCHITECTURES: Mapping[str, ArchitectureDefinition]` from the locked preset table (including schema_version, prospective, mortality appraisal).
  - `get_architecture(architecture_id)` fail closed on unknown id (`architecture_unknown`).
  - Ensure `full_v2_agent` declares all four owned flags required, prospective disabled, social ledger modes untouched/disabled.
  - LOGGING: ERROR on lookup miss with `architecture_unknown`.
  - Files: `src/agents/cognition/architectures.py`, `tests/unit/test_cognitive_architecture_registry.py`.
  - Depends on: Task 4

- [x] Task 6: Add `architecture_definition_digest`
  - Pure function hashing canonical architecture_id + capability declaration + implementation_keys.
  - Unit test: stable across process; changes when a binding or required flag changes.
  - LOGGING: DEBUG digest value (hex only).
  - Files: `src/agents/cognition/architectures.py`, `tests/unit/test_cognitive_architecture_registry.py`.
  - Depends on: Task 5

- [x] Task 7: Expand architectures to runner config (authoritative path + schema selection)
  - Add `src/experiments/architectures.py` with `expand_architecture(base, architecture_id) -> SimulationRunnerConfig`.
  - Set per-agent modes via extending `_with_agent_modes` (or equivalent) **and** `replace(..., capability_flags=..., schema_version=..., mortality_mode=...)` as required by the preset table.
  - Lock schema selection: v4 / v6 / v7 per preset; unit-test each architecture constructs without `reflection_mode_requires_v6`, `prospective_mode_requires_v7`, `v6_requires_reflection`, or `v7_requires_prospective`.
  - Build `ArchitectureModeSnapshot` from the expanded config; call `validate_architecture_compatibility`; log `architecture_definition_digest`.
  - Preserve agent ids, scenario, seeds, stochastic identity, tracing-off; do not invent architecture schema keys.
  - LOGGING: INFO expand summary (architecture_id, schema_version, enabled_flags, memory_mode, reflection_mode, prospective_mode, digest).
  - Files: `src/experiments/architectures.py`, `src/experiments/catalog.py` (`_with_agent_modes` extension if needed), `tests/unit/test_experiment_architecture_expand.py`.
  - Depends on: Tasks 5, 6

<!-- Commit checkpoint: tasks 4-7 -->

### Phase 3: Guards and shared-world experiment matrix

- [x] Task 8: Guard import boundaries for architecture composition
  - Architecture/import test: `agents.cognition.architectures` must not import `simulation` or `experiments`.
  - Assert retrieval/reconstruction factory entries are declaration tokens (or raise if someone adds a service-bound constructor that imports runner/persistence).
  - LOGGING: none beyond assertion messages.
  - Files: `tests/architecture/test_cognitive_architecture_boundaries.py`.
  - Depends on: Task 4

- [x] Task 9: Add `experiment-ac-cognitive-architectures`
  - Catalog builder `experiment_ac_cognitive_architectures` with conditions `ac-<architecture_id>` for all seven presets.
  - Shared `ExperimentSeedMatrix` and `paired_world_group`; prove scenario fingerprint equality across arms.
  - Export from `src/experiments/__init__.py`.
  - Assert `tests/unit/test_v1_regression_gate.py` does not import AC (static import scan or explicit allowlist equality for A–E only).
  - Keep off V1 gate; do not append AC to the gate module.
  - LOGGING: INFO `experiment_ac_built` with condition_ids and digests.
  - Files: `src/experiments/catalog.py`, `src/experiments/architectures.py`, `src/experiments/__init__.py`, unit catalog tests.
  - Depends on: Task 7

- [x] Task 10: Prove objective world + seed invariance across architectures
  - Property/unit test: for fixed seed + scenario, architecture arms share scenario fingerprint and stochastic identity fields; only cognition/capability/schema digests differ as expected.
  - LOGGING: DEBUG digest comparisons (hashes/ids only).
  - Files: `tests/unit/test_cognitive_architecture_world_seed_parity.py`.
  - Depends on: Task 9

- [x] Task 11: Guard against architecture switches in hot paths
  - Scan `src/agents/cognition/loop.py` and `src/simulation/agent_runtime.py` for forbidden patterns (`architecture_id ==`, `if architecture`).
  - Allow the identifier only inside `architectures.py` modules / experiments expand / tests.
  - LOGGING: none required beyond assertion messages.
  - Files: `tests/architecture/test_no_architecture_switches.py`.
  - Depends on: Task 1

<!-- Commit checkpoint: tasks 8-11 -->

### Phase 4: Contract tests for structured actions

- [x] Task 12: Contract test — each architecture yields a valid closed `AgentCommand`
  - Parametrize over all registry architecture ids.
  - Expand → build loop via authoritative runner/cognition binding with deterministic memory/perspective fixtures.
  - Assert `require_agent_command(command)` and exact closed class from `world.actions`.
  - No network; use production deterministic policies / fakes.
  - LOGGING: DEBUG architecture_id + command tag via `agent_command_tag`.
  - Files: `tests/unit/test_cognitive_architecture_action_contracts.py`.
  - Depends on: Tasks 5, 7

- [x] Task 13: Contract test — capability validation blocks incompatible expands
  - Mutate a snapshot to drop a required flag / set a forbidden mode; expect validate failure codes.
  - Attempt to require `multi_hop_testimony_tracking` in a forged definition; expect fail closed.
  - LOGGING: expect ERROR reason codes in test hooks if using caplog.
  - Files: `tests/unit/test_cognitive_architecture_validation.py` (extend).
  - Depends on: Task 3

<!-- Commit checkpoint: tasks 12-13 -->

### Phase 5: Documentation

- [x] Task 14: Document architecture variants and stage slots (docs checkpoint)
  - Update `docs/cognition-runtime.md` with registry, preset+schema table, `ReconstructionStage` naming, digest semantics, expansion/single-path rules, validation reason codes, and the composition rule (no architecture switches in the loop).
  - Brief Downstream-contract cross-link in `docs/architecture.md` if a single paragraph fits.
  - Satisfy mandatory `Docs: yes` checkpoint; no README marketing rewrite.
  - LOGGING: n/a (docs).
  - Files: `docs/cognition-runtime.md`, optionally `docs/architecture.md`.
  - Depends on: Tasks 1–13

<!-- Commit checkpoint: task 14 -->

## Acceptance criteria

- Seven architectures registered and expandable without a new runner schema id for `architecture_id`
- Per-architecture schema versions (v4/v6/v7) construct under existing exclusivity rules
- Stage-slot Protocols exist for all ten named interfaces; `ReconstructionStage` does not collide with `memory.contracts.MemoryReconstructor`
- Factories bind service-free stages; retrieval/reconstruction remain declaration→`MemoryMode`→runner injection
- Compatibility validation fail-closed with stable reason codes; digest is diagnostics-only
- `experiment-ac-cognitive-architectures` shares world+seed across arms and stays off the V1 gate
- Each architecture contract-tested to emit a valid closed `AgentCommand`
- No `if architecture == ...` in `CognitiveLoop` / `AgentRuntime` hot paths; cognition architectures module stays import-clean
- Docs updated (`Docs: yes`)

## Next steps

Plan file: `.ai-factory/plans/v2-cognitive-architecture-variants.md`

To start implementation, run:
`/aif-implement`

To view tasks:
`/tasks` (or use TaskList)

Suggest `/clear` or `/compact` if context is large after planning.
