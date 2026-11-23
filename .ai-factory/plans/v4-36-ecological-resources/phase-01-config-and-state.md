# Phase 1: Config and state

Plan: [index.md](index.md)  
Tasks: 1–2  
Depends on: none

## Objective

Claim the reserved ecology capability with a bounded, exact opt-in config and an engine-owned per-node damage channel.

## Current-Code Evidence

| Path | Symbols / sections | Why it matters |
|---|---|---|
| `src/simulation/runner_models.py`, `src/simulation/compatibility.py` | `SimulationRunnerConfig`, `V4CapabilityFlags`, closed accepted and owned sets | Encoding id, flag ownership, and active feature inputs are separate gates. |
| `src/simulation/runner_serialization.py` | `_v56_family_root_keys`, `_encode_runner_document`, `decode_runner_config` | V57–59 are feature-specific roots, not a single ever-growing required key set. |
| `src/simulation/v4_architecture.py` | `V4ContextId.ECOLOGICAL_FEEDBACK` | Existing objective context has a `SUPPLY_CHAINS` prerequisite. |
| `src/simulation/bootstrap.py`, `src/world/_state.py`, `src/simulation/runner.py` | `WorldBootstrap`, `WorldState`, `rebuild_world_state`, `SimulationRunner.from_config` | Immutable bootstrap and candidate rebuild are the paths into objective state. |
| `src/world/environment.py`, `src/world/values.py` | `EnvironmentalDynamicsSpec`, `round_physical` | Reuse season/yield and the existing tenth-unit stock grid. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/simulation/ecological_resources_config.py` | create | Typed spec, exact canonical payload/digest, scenario/rules validation. |
| `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `src/simulation/__init__.py` | modify | Accept named opt-in v60 with existing flag and exact layered siblings. |
| `src/world/_ecological_resources.py` | create | Frozen private stock state and shared bounds checks; Phase 2 adds transition. |
| `src/world/_state.py`, `src/simulation/bootstrap.py`, `src/simulation/engine.py`, `src/simulation/runner.py` | modify | Carry validated state and bind the trusted policy without broadening owner-visible contracts. |
| `pyproject.toml`, `tests/architecture/boundary_checker.py` | modify | Register the new private module in both architecture enforcement layers. |
| `tests/unit/test_ecological_resources_config.py`, `tests/unit/test_ecological_resources_state.py` | create | Cover strict configuration and boundary copying; add focused assertions to existing compatibility tests in Phase 4. |

## Task 1: Claim ecology with an exact v60 policy

### Intent

Select a small explicit set of existing renewable nodes. No implicit opt-in by resource kind, location, population, or a new global season clock.

### Implementation Steps

1. Define `EcologicalResourcesSpec(policy_id, nodes)` and `EcologicalResourceNodeSpec(resource_id, minimum_capacity_tenths, withdrawal_allowance_tenths, recovery_tenths_per_idle_tick)` in `simulation.ecological_resources_config`. Exact root keys are `policy_id`, `nodes`; exact row keys use the four field names above. Require policy `ecological-resources.v1`, 1–128 unique existing `EntityId` values, strict integers (reject bool/float), minimum and recovery in `[1, 10000]`, allowance in `[0, 10000]`. Sort typed rows by ID when encoding; strict wire input requires that same order. SHA-256 the canonical JSON section using the project's canonical serializer.
2. At construction validate each selected node exists in the scenario, has a positive baseline regeneration rate, and has exact-tenth initial quantity and baseline maximum with `1 <= minimum_capacity_tenths < baseline_tenths <= 10000`. Require world extraction amount on the tenth grid when active; do not quantize the user's input silently. Reuse existing environmental coverage validation. Existing nonselected definitions keep their legacy validation.
3. Add `RUNNER_SCHEMA_VERSION_V60`, public compatibility entry and optional `SimulationRunnerConfig.ecological_resources`. Exactly v60 requires the flag true, a non-null spec, `supply_chains=True` and existing `environmental_dynamics`; v1–v59 reject the active flag/spec. Claim the existing flag in private and public owned sets; `disasters` still fails closed. Use the objective context's existing prerequisite rather than changing the graph.
4. Add exact v60 root construction from the active v56 family plus mandatory `ecological_resources` and only the present `measurement_instruments`, `disease_mechanics`, `medical_beliefs` siblings. Reuse all respective v57–59 prerequisites and exact per-channel shapes; no `null` placeholders or mandatory disease on v60. Update all applicable serializer/model version allowlists, including nested modes and generational branches. Do not select v60 by numeric max or rewrite old configs. Full config fingerprint changes with ecology policy; no new cognition identity field.

### Required Interfaces and Contracts

- Export version and public policy types via `simulation`; keep raw row state private. No settings, public route, CLI factor, or artifact store added.
- Input/rejection source: Original Request; `.ai-factory/ARCHITECTURE.md` → Requirements for later changes; `src/simulation/v4_architecture.py` → existing ecology entry.

### Error Handling and Logging

Fail before bootstrap with closed reason codes for flag/version/spec mismatch, missing environment or supply prerequisite, unknown/duplicate IDs, caps and invalid stock grid. One DEBUG bind receipt may log schema, managed count and reason code but not the configuration or raw rows.

### Tests

`tests/unit/test_ecological_resources_config.py`: strict keysets, ordering and round-trip bytes, missing/false/mismatched flag/spec/version, missing prerequisites, duplicate/unknown/too many rows, nonrenewable, out-of-range and off-grid values, nested inherited combinations and illegal medical-without-disease. Load `tests/fixtures/runner_configs/bf_baseline_v4.json` unchanged and assert golden re-encode and identity; assert prior environment and v57–59 semantic round-trips via their established tests.

### Acceptance Criteria

One stable canonical v60 document binds only an explicit valid node set; the same policy cannot be smuggled into earlier version roots or activated from defaults.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_ecological_resources_config.py tests/unit/test_medical_beliefs_config.py tests/unit/test_compatibility_matrix.py -q` passes.

## Task 2: Bind the engine-owned stock damage channel

### Intent

Keep ecological memory as bounded objective data; reuse the existing `Resource` for actual stock and baseline maximum.

### Implementation Steps

1. Add private `EcologicalStockRow(resource_id, minimum_capacity_tenths, damage_tenths)` and an immutable mapping plus policy digest to the world state. Start every configured row at damage zero. Store the floor for validation without the full policy during replay; allowance and recovery remain trusted live policy only. Off is `None`, never an empty active section.
2. Pass the typed `EcologicalResourcesSpec` from `SimulationRunner.from_config` to a new `simulation.bootstrap.build_initial_ecological_resources` helper. Bootstrap, not runner, constructs private rows from typed inputs. `WorldBootstrap` validates/copies the rows in ID order and passes them into `WorldState`; `rebuild_world_state` preserves both rows and digest on unrelated operations and applies replacements only when explicit. Only engine/bootstrap and other private world modules may import `world._ecological_resources`. Outer consumers use typed detached checkpoint rows, not `object` or a private-world import.
3. `WorldEngine` binds the trusted spec for live ticks. Validate row IDs and floor against the spec, active section versus bound spec, and digest equality. Reuse a validator for bootstrapping and restoring: check row count/order/uniqueness, node presence, baseline grid and bounds, `damage <= base-floor` and `Resource.quantity <= base-damage`. Make the same invariant available to replay and checkpoint restoration in Phase 3. Translate configuration into a typed bounded read-only mapping of per-node allowance/recovery integers before calling world physics; the `world` package never imports the simulation config.
4. Register `world._ecological_resources` beside `world._disease` in the private-world import-linter contract and both private-world prefix checks in `tests/architecture/boundary_checker.py`. Follow `.ai-factory/patches/2026-11-22-19.51.md` → Prevention: check these gates before marking the task complete, not only at final qualification.

### Required Interfaces and Contracts

- No fields on `Resource`, `Observation`, `PerceptionService` output, `RunnerResult`, or agent state; no owner data crosses this channel.
- Existing default remains `None`; immutable state must not share caller-owned mutable containers.

### Error Handling and Logging

Malformed or inconsistent active state is rejected at construction, never silently converted into a valid reset. No per-row logs. Pure rebuild does not log.

### Tests

`tests/unit/test_ecological_resources_state.py`: initial row order and zero damage, immutable copy plus exact preservation across an unrelated world rebuild, invalid resources and digest mismatch, over-cap state rejection, and absent state when flag off.

### Acceptance Criteria

Only the engine/private world retains bounded active state, and legacy bootstrap/read paths below the opt-in do not change public values.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_ecological_resources_state.py tests/architecture/test_boundary_checker.py tests/architecture/test_v4_context_registry.py -q` and `uv run --frozen --python 3.12.14 lint-imports` pass.

## Phase Risks and Mitigations

- Forgetting branch-specific schema allowlists: test v60 on the actual active roots, not by renaming a single minimal JSON fixture.
- Treating private state like a second stock model: store damage and floor only; all extraction and regrowth still change the existing `Resource.quantity`.

## Phase Completion Checklist

- Exact root, opt-in validation and immutable channel are in place; update verified task checkboxes in `index.md`.
