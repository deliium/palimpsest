# Phase 2: Advancing generations and finalized population stops

Plan: [index.md](index.md)
Tasks: 4–6
Depends on: Tasks 1–3

## Objective

Create multiple realized generations through existing atomic engine admission and evaluate population stops from finalized objective facts.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/simulation/demographic_policy.py` | `FixedIntervalEntryPolicy` 165–238; closed registry 241–260 | Current scheduled cohorts share one constant generation label. |
| `src/simulation/engine.py` | `_apply_lifecycle_channel` 2267–2674 | Deaths occur before policy capacity calculation; scheduled entries join the tick candidate. |
| `src/simulation/runner.py` | initialization forwarding 1839–1860; `run_tick` 2452–2466; `_sync_mid_run_population_entries` 3888–4077 | Newer schemas lose objective initialization forwarding; empty-population ticks unconditionally stop; newcomers bind next tick. |
| `src/world/lifecycle.py` | `AgentLifecycleRecord`, `OriginProvenance` | Labels are objective admission metadata, not inferred genealogy. |
| `tests/unit/test_demographic_policy.py`, `tests/unit/test_lifecycle_long_run_aging.py`, `tests/unit/test_runner_lifecycle_export.py` | policy, lifespan, ledger tests | Existing lifecycle mechanisms must be reused. |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/simulation/demographic_policy.py` | modify | New closed `GenerationalIntervalEntryPolicy`. |
| `src/simulation/runner_models.py` | modify | Exact policy params and top-level version gate. |
| `src/simulation/runner.py` | modify | Initialization forwarding, generation progress, shared empty/nonempty finalized path. |
| `src/simulation/generational_progress.py` | create | Pure detached population fold and stop-condition evaluation. |
| `tests/unit/test_generational_demographic_policy.py`, `tests/unit/test_generational_population_runner.py`, `tests/unit/test_generational_stopping.py` | create | Realized generations, blank entrants, and boundary/stop tests. |
| `tests/unit/test_simulation_runner.py` | modify | Reproduce and guard all-terminal behavior. |

## Task 4: Implement deterministic multi-location generational entry

### Intent

Provide an indefinitely repeatable schedule without pre-enumerating births or manufacturing biological parentage.

### Implementation Steps

1. Register `generational_interval_entry`. Exact params: `interval_ticks`, `entries_per_interval`, `generation_length_ticks`, `name_prefix`, `cohort_id_prefix`, `spawn_location_ids`. Require positive intervals/length, nonnegative entry count, unique nonempty ordered spawn IDs, and a generation length divisible by interval. Preserve spawn order as experimental input.
2. Consult at engine tick `t > 0` when `t % interval_ticks == 0`. Set `generation_index = 1 + (t - 1) // generation_length_ticks`; bootstrap remains generation 0. More than one cohort can share a generation.
3. Compute available capacity after deaths. For each ordinal below `min(entries_per_interval, capacity)`, choose spawn index `(((t // interval_ticks - 1) * entries_per_interval) + ordinal) % len(spawn_location_ids)`. This schedule balances creation locations, not communities or territorial entitlement.
4. Generate IDs from stable prefix, absolute tick, and ordinal using the existing widening numeric-format convention. Define cohort as prefix + tick + spawn-index, so each cohort has exactly one entry tick, spawn stratum, and generation. Return deterministic sorted candidates with demographic provenance and empty parent/origin-content references.
5. Capacity-denied slots are dropped, not retried. IDs and generation labels are scheduled from absolute tick, not the count of successful admissions; missing generations are legal. Preserve old disabled/fixed policies byte-for-byte.

### Required Interfaces and Contracts

Use existing `DemographicEntryCandidate`, snapshot, and proposal-only port. No `WorldState`, mating, fertility, biological birth event, parent selection, or subjective content enters the policy. Validate every spawn ID against scenario locations at runner construction.

### Requirement Evidence

User population creation/cohorts/generation requirements; `PopulationLifecycleSpec` no-biology contract; index generation definition and C2/C3/C7.

### Error Handling and Logging

DEBUG policy ID, tick, scheduled/realized candidate counts, capacity, and closed skip reasons. Duplicate generated IDs are skipped with an explicit collision code, matching existing policy behavior; never mint random fallback IDs. Invalid spawn configuration fails before run creation.

### Tests

Two cohorts per generation, multiple spawns, large ticks beyond 9999, cap clips/drops, zero entry count, collision skip, capacity freed by death, skipped entire generation, repeatability independent of RNG consult count, and unchanged fixed-policy labels.

### Acceptance Criteria

The same schedule realizes the same IDs/order/labels; reaching a scheduled generation without admission does not advance realized progress.

### Verification

`uv run --frozen pytest --cov --cov-report=term-missing tests/unit/test_generational_demographic_policy.py tests/unit/test_demographic_policy.py -q`

Expected: new and legacy policy cases pass.

## Task 5: Bind correctly initialized entrants through atomic tick admission

### Intent

Reuse engine-owned lifecycle death/admission and fresh runtime construction, including the latest schema family.

### Implementation Steps

1. First reproduce the v36–v54 initialization-forwarding omission with non-default parameter distribution/body initialization and a population entry. Assert objective initialization provenance/body parameters and runtime profile agree; do not write a test that checks only config presence.
2. Replace the stale v25–v35 list in `SimulationRunner.from_config` with a centralized accepted initialization-version predicate that covers every schema whose validator admits explicit initialization, including v55. Keep v24 legacy implicit initialization untouched.
3. Route the new policy through the engine's existing `_apply_lifecycle_channel` candidate transaction. Do not call public `admit_population_entry` from the runner; that boundary path is not the durable tick transaction.
4. Keep engine ordering: physical actions/effects, lifecycle changes/deaths, post-death capacity, admission, commit, runner synchronization, owner finalization. New runtimes begin acting at observation tick `t+1` after admission in tick `t`.
5. Use the explicitly chosen existing species profile and parameter distributions for every entrant. Require empty goals, memories, beliefs, relationships, and ledgers at admission; mode-enabled/content-empty profiles remain legal. Do not inherit founder cognition settings or create a new species profile for this plan.
6. Test initial parent links under existing kinship configs remain valid, but the new policy must always supply no parents. Do not expand or repair the independent public-admission parent-link mechanism in this feature.

### Required Interfaces and Contracts

Existing event/write-pair selection applies: creation and initialization facts use their existing events. Atomic candidate failure must leave registrations, translator, lifecycle, IDs, and durable journal unchanged. Replay consumes committed facts rather than resampling initialization.

### Requirement Evidence

`.ai-factory/ARCHITECTURE.md` — blank-slate entry and world authority; runner/engine call-order evidence; C2 and C7. The forwarding correction is a scoped correctness fix, not a promise to reproduce the prior bug when re-executing affected configs.

### Error Handling and Logging

Use existing safe construction/admission errors; initialization mismatch aborts before publish. INFO entrant count/profile ID, DEBUG owner IDs and initialization reason codes; never log draw payloads or owner content.

### Tests

v25, v35, v36, v44, v54, v55 initialization forwarding; fresh owner stores; first-action tick; lifecycle death plus entry in one tick; rollback on invalid candidate; replay/live lifecycle and observation parity. Existing persisted events remain decodable.

### Acceptance Criteria

Objective creation and runtime initialization agree, and every entrant follows normal atomic authority and owner isolation.

### Verification

`uv run --frozen pytest --cov --cov-report=term-missing tests/unit/test_generational_population_runner.py tests/unit/test_new_agent_fork_replay.py tests/unit/test_lifecycle_long_run_aging.py -q`

Expected: fresh-entry, lifecycle, and replay tests pass.

## Task 6: Unify empty-population progression and built-in stopping

### Intent

Make `run()` and tick-by-tick callers observe identical finalized stopping semantics.

### Implementation Steps

1. Reproduce both empty-submission defects: false all-terminal policy still stops; admission on the same empty tick still reports all-terminal. Keep regression cases in `test_simulation_runner.py`.
2. Remove the unconditional return in `run_tick`. Empty and nonempty commits must share synchronization, finalized receipt recording, cursor advancement, and stop evaluation exactly once. Preserve legacy all-terminal behavior when its policy is true and the post-sync runtime roster is actually terminal.
3. Add pure `build_population_progress(lifecycle_records, detached_bodies, boundary_tick)` and `evaluate_generational_stops(spec, progress)`. Use the entire objective lifecycle ledger and registered body identities, with sorted rows; detect missing/duplicate bindings as authority/invariant errors rather than silently undercounting.
4. At completed boundary B, evaluate horizon against `ticks_committed == B`; generation horizon against max ever admitted label; extinction against living==0; threshold with inclusive configured comparator. Death and admission on the same tick are observed together.
5. With extinction disabled and legacy all-terminal disabled, permit empty ticks until another scheduled admission or max-tick horizon. With extinction enabled, zero living after admission stops immediately even if a future cohort is scheduled.
6. Preserve cancellation, pending-finalization recovery, and cognition/authority failure precedence. Never evaluate successful demographic criteria while owner finalization is incomplete. As soon as a terminal decision is emitted, latch its reason/evidence/receipt before returning. Until `finish_run`, another `run_tick` returns that same terminal receipt without observing, committing, invoking criteria, or publishing again. After `finish_run`, further ticks are rejected. A reached horizon or post-finalized artifact failure is not a pause that callers can bypass by ignoring the receipt.

### Required Interfaces and Contracts

No mutable demographic scheduler state is introduced: proposals derive from absolute tick; progress is reconstructible from finalized facts. Stop results/evidence use Phase 1 precedence. A generation limit stops on admission, not adulthood or death of that generation.

### Requirement Evidence

User stopping list; `run_tick`/`_evaluate_stop`; index finalized-boundary order and C3–C6.

### Error Handling and Logging

INFO stop code, completed boundary and population totals. DEBUG matched built-ins. Do not infer extinction from an empty submission batch or runtime status.

### Tests

All-terminal regression cases; scheduled revival across a gap; true extinction; inclusive thresholds (including at_most zero); simultaneous tick/generation/extinction matches; overlapping cohorts; cap denying the target generation; deaths in transit; `run()` versus repeated `run_tick()` receipt/hash equivalence; repeated tick calls after each terminal condition leave engine cursor/events and callback counts unchanged.

### Acceptance Criteria

No extra tick occurs after a reached horizon; no successful stop is emitted before finalization; empty-population continuation honors its explicit policy.

### Verification

`uv run --frozen pytest --cov --cov-report=term-missing tests/unit/test_generational_stopping.py tests/unit/test_simulation_runner.py tests/unit/test_runner_lifecycle_export.py -q`

Expected: new stop semantics and legacy runners pass.

## Phase Risks and Mitigations

- Runtime terminal state can lag objective death: use body status for population, post-sync runtime status only for the legacy terminal policy.
- Generation labels may skip under a cap: expose realized max and counts; never count unadmitted scheduled cohorts.
- Genealogy is independent: omit parent-producing policies and defer their separate admission bugs.

## Phase Completion Checklist

- Tasks 4–6 meet acceptance criteria and commands pass.
- Update only the index progress ledger.
