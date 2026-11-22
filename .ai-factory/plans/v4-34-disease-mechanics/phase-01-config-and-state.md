# Phase 1: Activation and private objective state

Plan: [index.md](index.md)  
Tasks: 1–2  
Depends on: none

## Objective

Claim the existing `epidemics` slot through a strict opt-in configuration and define a private objective state representation before wiring ticks.

## Current-Code Evidence

| Path | Symbols / sections | Why it matters |
| --- | --- | --- |
| `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py` | `SimulationRunnerConfig`, `V4CapabilityFlags`, `_v56_family_root_keys`, `_v57_family_root_keys`, `encode_runner_config`, `decode_runner_config` | Explicit version gates and exact document shape |
| `src/simulation/v4_architecture.py`, `src/simulation/compatibility.py` | `V4ContextId.EPIDEMICS`, ownership maps | The epidemic context already declares infrastructure as its prerequisite |
| `src/simulation/runner.py`, `src/simulation/bootstrap.py` | `SimulationRunner.from_config`, `WorldBootstrap` | Fail-closed composition and initial body validation |
| `src/world/_state.py`, `src/world/_freeze.py` | `WorldState`, `rebuild_world_state`, detached state helpers | Immutable candidate state and copy rules |

## Files to Change

| Path | Action | Responsibility |
| --- | --- | --- |
| `src/simulation/disease_config.py` | Create | Strict spec and config-only validation |
| `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `src/simulation/v4_architecture.py`, `src/simulation/runner.py` | Modify | Ownership, exact version branch, semantic and prerequisite validation, bootstrap composition |
| `src/world/_disease.py` | Create | Private immutable rows, phase predicates, and live-row validation |
| `src/world/_state.py`, `src/world/_freeze.py`, `src/simulation/bootstrap.py` | Modify | Private world storage and bootstrap ownership |
| `src/simulation/__init__.py`, `pyproject.toml`, `tests/architecture/boundary_checker.py` | Modify | Public config facade, private world import enforcement |
| `tests/unit/test_disease_config.py`, `tests/unit/test_disease_state.py` | Create | Exact configuration and state invariants |

## Task 1: Define the exact opt-in runner configuration

### Intent

Only explicitly configured runs can reach disease mechanics; configs never supply runtime disease rows or change older contracts.

### Implementation Steps

1. Define frozen `DiseaseMechanicsSpec` in `simulation.disease_config`: mandatory exact fields `policy_id` (`disease-mechanics.v1`), `initial_latent_entity_ids` (unique sorted founder IDs, empty valid), `exposure_chance_milli`, `transmission_chance_milli`, `symptom_chance_milli`, `mortality_chance_milli` (all strict integers 0–1000), `latent_ticks`, `active_ticks` (strict integers 1–1024), and `immunity_after_recovery` (strict Boolean). Reject unknown keys, nulls, Boolean-as-integer, duplicate/malformed founder IDs, and unavailable or nonliving founders at bootstrap. Permanently immune means for this run only.
2. Add `SimulationRunnerConfig.disease_mechanics: DiseaseMechanicsSpec | None` and `RUNNER_SCHEMA_VERSION_V58`. v58 is `_v56_family_root_keys` plus mandatory `disease_mechanics`, and adds `measurement_instruments` if and only if that existing channel is selected. Extend the V4 family set, per-feature/model schema allowlists, and top-level and nested encoder/decoder dispatch where those inherited features already support v56/v57; do not turn v57's mandatory-measurement rule into a v58 requirement. Export the new config constant and spec from the simulation facade. Do not broaden accepted v56/v57 keys or change default v4; canonical writes choose v58 only for disease.
3. Prepare `epidemics` ownership in both existing allowlists, while retaining a separate fail-closed guard in `SimulationRunner.from_config` until Task 6. Require the flag, v58 spec and the existing valid `infrastructure_networks` capability/config together. `regions_migration` still enables travel under its existing conditions; science instruments still require their existing prerequisites. Reject unsupported old-version activation, flag/spec mismatch and missing prerequisites before providers or mutable runtime objects are created. Retain the V4 context prerequisite, context count and flag count; do not add a cognition policy or owner ledger.

### Contracts / evidence

- Roadmap M8 and `v4_architecture.py` establish the slot and prerequisite; the request supplies opt-in behavior. All error paths use the usual runner/config error types and stable safe reason codes. Log archival/version decisions only at metadata level; no config values or seeded founder identities.

### Tests, acceptance, and verification

- `tests/unit/test_disease_config.py`: exact v58 round trips for base infrastructure, travel, instruments, and travel + instruments; use real configured fixture builders to exercise inherited agent/schema checks, not just minimal dictionaries. Reject missing/extra fields, bad bounds/types, nonfounder IDs, invalid prerequisites and v56/v57 misuse; validate v58 empty seed list. Verify representative existing v4/v56/v57 round trips and fingerprints unchanged; use typed config tests before Task 6 activates public construction.
- Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_disease_config.py tests/unit/test_runner_config_v56.py tests/unit/test_v4_scaffolding_gate.py tests/unit/test_compatibility_matrix.py -q`. Acceptance: exact input combinations in the index are accepted or rejected, never silently ignored.

## Task 2: Add private disease rows and detached state invariants

### Intent

Support engine-owned state without exposing it through `Body`, agent-facing facades, step snapshots, or public inspection projections.

### Implementation Steps

1. In `world._disease` define private immutable rows with one of `latent`, `active`, `immune`. Absence means susceptible for a living body when the channel is on. Latent and active each have one absolute `due_tick`; only active can carry one Boolean symptom bit. Immune has neither deadline nor symptom bit. No source, strain or case registry. The private state is `None` while off, immutable sparse entity mapping while on (including empty).
2. Extend `WorldState` and rebuild/freeze/copy paths to preserve the distinction between off and enabled-empty. Validate row key/shape and detach at rebuild; require living-body and deadline invariants at bootstrap and finalized boundaries, not during intermediate death folds. Register `world._disease` in the same private-module contracts as `world._measurement` in `pyproject.toml` and `tests/architecture/boundary_checker.py`. Only `simulation.engine` and `simulation.bootstrap` may import it from outside private world modules; codecs use detached transport values.
3. Validate current deadlines at the boundary that knows the next tick; due ticks may equal the next executable tick but cannot be overdue. Founder bootstrap creates latent rows at first tick `t0` with deadline `t0 + latent_ticks`; nobody else has a row. Preserve row-free new entrants and dead-body cleanup invariants.

### Contracts / evidence

- Architecture requires detached candidate state; absence is not an infection projection or an immunity proof for an agent. Throw a typed invariant error on malformed rows. No private state data in logging or exception text.

### Tests, acceptance, and verification

- `tests/unit/test_disease_state.py`: copy/immutability, off versus enabled-empty, malformed phases, invalid deadline and unknown/dead entity, founder setup and deterministic sort.
- Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_disease_config.py tests/unit/test_disease_state.py -q` and `uv run --frozen --python 3.12.14 lint-imports`. Acceptance: state remains private and is preserved exactly by rebuild.

## Phase Risks and Mitigations

- The v56 family has optional inherited keys; use its exact helper, never parse v58 with an open dictionary schema.
- Stale version/ownership pins are not compatibility requirements; update executable current-count tests but retain historical fixture expectations.

## Phase Completion Checklist

- Verify Tasks 1–2 and update only `index.md` progress after each success.
