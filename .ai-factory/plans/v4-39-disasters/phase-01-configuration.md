# Phase 1: Objective Configuration

Plan: [index.md](index.md)  
Tasks: 1  
Depends on: none

## Objective

Make disaster policies bounded, typed, reproducible, and validatable without enabling incomplete production paths.

## Current-Code Evidence

| Path | Symbols | Why it matters |
|---|---|---|
| `src/simulation/v4_architecture.py`, `src/simulation/versioning.py` | `DISASTERS` context and reserved write pair | Objective ownership, ecology prerequisite and reserved 26/`v24`. |
| `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py` | `SimulationRunnerConfig`, `_v60_family_root_keys`, `_v61_family_root_keys`, `_v62_family_root_keys` | Legacy family keys and exact codec precedents. |
| `src/simulation/ecological_resources_config.py` | managed stock and policy validation | Static targets are real managed nodes from the scenario. |
| `src/simulation/randomness.py` | `StreamScope`, `derive_stream_seed`, `create_named_stream` | Use existing versioned seed derivation and isolated streams. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/world/disasters.py` | Create | Frozen domain rule, target, schedule, candidate and result contracts; no simulation imports. |
| `src/simulation/disasters_config.py` | Create | Canonical policy codec, digest, static binding and validation; imports public world contracts only. |
| `src/simulation/disasters_randomness.py` | Create | Deterministic named draws and candidate selection; no policy or world mutation. |
| `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `src/simulation/__init__.py` | Modify | Exact v63 runner schema and facade; activate ownership only in Task 4. |
| `tests/unit/test_disaster_config.py`, `tests/unit/test_disaster_schedule.py` | Create | Codec, prerequisites, selection, and frozen RNG vectors. |

## Task 1: Define the closed disaster policy and trigger contract

### Intent

One policy controls timing and magnitude; it has no callable, prompt, arbitrary event name, or authority to mutate a world.

### Implementation Steps

1. Define `DisastersSpec(policy_id, rules, schedule)` and closed `DisasterKind`, rule, target and schedule types. Decode plain JSON objects only, exact keys and strings for IDs, exact ints (never bool) for clocks/strength. Use existing `EntityId`, `InfrastructureKind`, and resource/weather contracts. Convert arrays into tuples and reject reader-side noncanonical ordering rather than correcting the input silently.
2. Define `runner-config-v63` as exact `_v60_family_root_keys` plus mandatory `disasters`; allow optional inherited `overexploitation` and `commons_governance` on equivalent v61/v62 validation conditions, respectively. Retain optional measurement, disease, medical and v56 family fields only where already supported by those validators. Audit nested agent keysets, explicit schema membership and default write selection. No old root decodes `disasters`, and v56–v62 flags with `disasters=true` must fail at ordinary runner admission even after it is owned. Require both `disasters=true` and `ecological_feedback=true` in v63; preserve environmental dynamics, the `supply_chains` prerequisite, and managed renewable stock requirements. Require `epidemics` and `disease_mechanics` for surge, and `infrastructure_networks` for infrastructure rules; do not toggle those channels implicitly.
3. Validate each target statically against the scenario/location graph and managed-stock specification. Validate its dynamic state again in Task 2 or 3. Require a directed edge endpoint to be an actual neighbor, and validate node-versus-edge shape against the infrastructure kind's catalog topology. For an explicit finite tick cap, reject schedule ticks outside the runner's execution interval; unexecuted due ticks at early stop leave no receipt.
4. Canonicalize policy bytes with the project's sorted-key, compact UTF-8 JSON convention (no floating-point policy values); SHA-256 the `disasters` object only. Persist the digest for continuation, not as an RNG input or log field. Publish immutable typed contracts; retain effects internal to the engine and replay.
5. Candidate selection uses the current absolute pre-commit tick (`snap.tick.value`), never wall time or count of successfully delivered interventions. `create_named_stream(run_config, StreamScope("disasters.v1", (str(tick), rule_id, "occurrence"))).randrange(1_000_000) < chance_ppm` controls spontaneous rules. Reuse the same run config/derivation convention as existing physical channels. For zero probability, scheduled rules, or already-applied rules, omit the draw entirely. Dispatch scheduled candidates first, then spontaneous candidates, ordered by ASCII `rule_id` within each group. Distinct targets may be hit on the same tick, with no global cap beyond the rule limit. The per-recipient surge draw in Task 3 uses a separate named scope.

### Required Interfaces and Contracts

- Exact outer keys: `policy_id` (`disasters.v1`), `rules`, `schedule`. One to 32 rules, ordered by unique `rule_id` matching `[a-z][a-z0-9-]{0,31}`. Rule keys: `rule_id`, `kind`, `chance_ppm`, `target`, `effect`; spontaneous probabilities are 0–10,000 ppm per eligible tick per not-yet-applied rule. Document that this is a per-rule bound, not a global frequency guarantee.
- Exact keysets by kind:

  | Kind | Target keys | Effect keys |
  |---|---|---|
  | `flood_like`, `fire`, `drought` | `resource_id` | `loss_tenths` (1–10,000) |
  | `resource_collapse` | `resource_id` | `capacity_damage_tenths` (1–10,000); quantity depletes to zero |
  | `infrastructure_destruction` | `location_id`, `endpoint_location_id` (null for node), `infrastructure_kind` | empty object; fixed full integrity loss |
  | `epidemic_surge` | `location_id` | `extra_opportunity_milli` (1–1000); abstract exposure opportunity only |

- Reject duplicate `(kind, target)` bindings; normalize infrastructure edge comparisons according to existing asset topology while verifying the configured direction. Distinct stock shock kinds may share a stock and resolve against evolving state.
- A schedule row has only `tick` (strict nonnegative logical tick) and `rule_id`. Require canonical `(tick, rule_id)` order, known rule, at most one row per rule, and `chance_ppm == 0` for each scheduled rule. A schedule cannot change a rule's impact or target. A policy with no scheduled rows and zero chances is a valid inert control.
- One **applied** firing per rule for the life of the run. No persisted RNG position. A spontaneous no-effect attempt can be eligible again later and makes no receipt or consumed bit. A scheduled no-effect attempt emits a typed skip receipt with a bounded reason; the absolute tick means it will not auto-retry. Clock/index semantics are shared with Phase 3.
- `DisasterCandidate` carries the immutable rule and `scheduled|spontaneous` origin. Effects are closed discriminated values, not raw maps. The configured `kind` and structured `target` determine effect shape.

### Requirement Evidence

- Original Request: exact name, six objective kinds, explicit probabilities and controlled injection. `v4_architecture.py` closes objective context and ecology dependency. Existing v60–v62 codec/validation contracts distinguish actual supported compositions from arbitrary optional keys.

### Error Handling and Logging

- Fail closed with stable codes for version/flag mismatch, bad keysets, probability/strength range, duplicates, tick bounds and target mismatches. Log only code, schema version and aggregate counts; no policy documents, digest, target dumps or disease evidence.

### Tests

- `test_disaster_config.py`: exact six-kind round trips; active-only v63; inactive and legacy rejection; managed/type/weather prerequisites; optional siblings including v62 conditions; all invalid keys, bools, counts, duplicate IDs and schedule rule/clock bounds; unchanged v62 canonical bytes and default v4 write.
- `test_disaster_schedule.py`: freeze one trigger and one miss vector on explicit run seeds; round-trip seed/identity, scheduled due/not due, mixed priority, unrelated rule independence, multi-location order, consumed suppression, no calls on zero probability or schedule, and exact threshold equality misses.

### Acceptance Criteria

- A serialized policy produces exactly one canonical typed value and digest. No invalid shape or legacy flag path can enable disaster execution.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_disaster_config.py tests/unit/test_disaster_schedule.py tests/unit/test_commons_governance_config.py tests/unit/test_runner_config_v56.py -q`

## Phase Risks and Mitigations

- Adding one latest root can inadvertently alter prior exact-key tests. Exercise prior encoders/decoders and mirrored validation without editing any old schema contract.
- A stream based on traversal position couples unrelated rules. Key by absolute tick, stable rule ID, and purpose; do not include policy digest or treatment label.

## Phase Completion Checklist

- Config, canonical digest and trigger tests pass; production remains fail-closed until Task 4. Update Task 1 in `index.md`.
