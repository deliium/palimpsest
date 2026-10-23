# Phase 2: Finalized-boundary replay continuation

Plan: [index.md](index.md)
Tasks: 4–6
Depends on: Tasks 1–3

## Objective

Provide a public, complete in-process fork API that restores objective replay and every owner runtime at a coherent finalized boundary.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|---|---|---|
| `src/simulation/runner.py` | `run_tick` 2599; `export_runtime_checkpoint` 3273; `apply_runtime_checkpoint` 3359 | Existing checkpoint is not a full world/store restore and skips absent owners. |
| `src/simulation/run_control.py` | `AgentRuntimeCheckpoint`; `rebase_runtime_checkpoint` 1335 | Extensive cultural ledgers exist; current rebase changes only outer run ID. |
| `src/simulation/replay.py` | `ReplayService`, continuation vs read-only modes | A historical parent seek is not a writable child. |
| `src/simulation/agent_runtime.py` | `restore_runtime_checkpoint` 3130 | Runtime restoration validates ledger ownership. |
| `src/simulation/agent_runtime.py` | `SequentialInvocationIds` 398; checkpoint 3256; `_cultural_channel_export` 3942 | Existing checkpoint omits runtime operation identity and fresh-empty coverage; it is not a complete fork state. |
| `src/simulation/runner.py` | `set_cultural_boundary_sink` 3143; `_publish_initial_cultural_boundary` 3245 | Sink installation is legal only before started/restored cursors; F=0 publication needs an explicit initialization seam. |
| `src/simulation/generational_seeds.py` | `build_generational_seed_manifest` | Run-ID-scoped channels differ between children. |
| `src/simulation/randomness.py` | `objective_stream_identity`, `create_named_stream` | Derivation-v3 shares only explicitly selected streams. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/simulation/fork_checkpoint.py` | create | Complete checkpoint, typed scope rebasing, capture validation. |
| `src/simulation/runner.py` | modify | Capture/restore factory; extract shared agent composition, preserve finalized boundaries. |
| `src/simulation/agent_runtime.py` | modify | Public complete runtime fork-state capture/restore, inventory and coverage witnesses. |
| `src/simulation/run_control.py` | modify | Explicit complete runtime fork rebasing helper without changing shallow legacy helper semantics. |
| `src/simulation/__init__.py` | modify | Export supported fork interfaces. |
| `src/experiments/path_dependence_identity.py` | create | Treatment-blind slots, assignment and channel comparability. |
| `tests/unit/test_runner_fork_checkpoint.py`, `tests/unit/test_path_dependence_identity.py`, `tests/unit/test_path_dependence_replay_parity.py` | create | Complete restore, identity and continuation proofs. |

## Task 4: Capture and restore coherent runner fork checkpoints

### Intent

Make a child continuation an actual continuation, including agents admitted before F, rather than a fresh simulation with its tick cursor moved forward.

### Implementation Steps

1. Introduce `RunnerForkCheckpoint` containing source run/config fingerprint, exact F/revision, complete objective snapshot reference and prefix-head reference, ordered registration roster, complete `AgentRuntimeForkState` values, per-owner complete store states, creation/bootstrap metadata needed to rebuild admitted runtimes, and capture-format version. Include terminated registered owners retained by the runner, not just living founders. `AgentRuntimeForkState` is a new process-local wrapper around the existing checkpoint plus actual processed-invocation/finalization-hash sets, `SequentialInvocationIds` counters, goal-revision counters, applied reflection/identity operation IDs, legacy reader/writer store states, cultural fresh-channel/completeness witnesses and diagnostic audit/capture state required for identical later exports. Inventory every `AgentRuntime.__slots__` field as immutable configuration, reconstructed resource or captured state; reject unsupported custom invocation/inbox/loop state rather than assuming it is stateless. Do not widen the legacy durable `AgentRuntimeCheckpoint` wire schema.
2. Add public `await runner.initialize_finalized_boundary()` that starts runtimes and publishes boundary zero without observing/resolving a tick. It is idempotent only at boundary zero and rejects pending/terminal state. `capture_fork_checkpoint()` requires this initialized state and is callable only between ticks after objective commit, pending subjective finalizations, roster synchronization, criterion evaluation, boundary/cultural publication and sink acknowledgement have completed. Validate stage, no open observation/token, no pending receipts, matching F/revision across components, exact unique runtime/store roster equality, no stop request/terminal receipt. The new runtime restore preserves known-empty cultural channels rather than setting every absent ledger to restored-missing; storage restoration provenance is recorded separately from semantic coverage. Existing narrow restore keeps its historical behavior.
3. Add public async factory `SimulationRunner.from_fork_checkpoint(config, *, run_id, checkpoint, restored_engine, factories, cultural_sink=None)` returning a runner used as `async with await ...`, matching `from_config`. `restored_engine` must be a child head restored by existing objective replay, matching F/revision/config/registrations. Install `cultural_sink` and factory boundary observers while the new runner is not started, before restoring cursors. After complete owner restoration validate and publish exactly one child-scope F baseline; set the publication high-water mark to F so the next normal publication is F+1. Add an explicit supported recorder `start_at_boundary(F)`/baseline import contract in Task 10; never call `set_cultural_boundary_sink()` after restore, clear missing-prefix fields from experiments, republish boundary zero, or claim pre-F capture. At F=0, initialization publication supplies this one baseline. Validate everything before exposing the runner.
4. Extract shared runtime/bundle construction from `from_config` and `_sync_mid_run_population_entries` into a simulation-private composition helper. Rebuild the checkpoint roster with historical initialized parameters and existing owner stores; do not call blank-slate admission for existing entrants, reapply initialization costs, issue new `AgentCreated` events, or draw initialization/lifespan randomness again.
5. Hydrate isolated owner services and legacy stores, then the full runtime fork state, cognition counters, goal transitions, finalized receipts and generational progress/control. Restore deduplication SETS, not their counts; preserve invocation counters and fresh-empty witnesses. Re-export the captured state after restore and require equality modulo the explicit typed run-scope/provenance allowlist before any command executes. Require exact roster matches in this strict fork path; leave legacy `apply_runtime_checkpoint` behavior unchanged unless covered by a separately justified compatibility fix. All future actual newborns still use normal empty species-default admission.
6. Recreate providers, arbiters and sinks independently per child. Support only stateless deterministic fakes in the initial execution contract. Reject live/record/cache and recorded-replay providers with `fork_provider_unsupported`; replay-provider branching is deferred until a complete per-request namespace/usage/cursor clone contract is owned. Do not silently fall back to fake.

### Required Interfaces and Contracts

No experiment/analysis/persistence imports enter simulation. Capture is immutable process-local state, not a new world event or durable checkpoint wire schema. Restored engine creation stays through `BranchService.materialize_objective_fork` and `ReplayService`; experiments do not access private world state.

### Requirement Evidence

ARCHITECTURE — Objective authority/runtime and blank-slate admission; user common-history/forked-replay requirement.

### Error Handling and Logging

`fork_boundary_not_finalized`, `fork_roster_mismatch`, `fork_engine_mismatch`, `fork_terminal_boundary`, `fork_provider_unsupported`. INFO F/runtime counts; DEBUG restoration stages; ERROR code plus run/owner IDs. Resource construction failure closes all newly created child resources and leaves parent untouched.

### Tests

`test_runner_fork_checkpoint.py`: initialized F=0/F>0, capture before initialization rejected, exactly one F baseline, sink installed before cursors, existing post-start setter still rejects, admitted entrant, retired owner, dead founder, nonempty modern ledgers, owner store histories and legacy beliefs, processed/finalized deduplication identities, invocation and goal revision counters, applied reflection IDs, fresh-empty vs unknown cultural channels, pending boundary rejection, criterion stop rejection, missing/excess/duplicate owners, provider/custom-state rejection, rollback on the third owner, lifecycle initialization not repeated. A repeated finalized command must remain idempotent after restore, not only in uninterrupted execution.

### Acceptance Criteria

The public factory restores the full registered population and private experience before executing any child tick; no synthetic birth or knowledge-transfer event occurs.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_runner_fork_checkpoint.py tests/unit/test_institutional_decay_checkpoints.py -q`

## Task 5: Rebase typed scope and record truthful branch identities

### Intent

Separate scientific lineage, storage run identity, and actual random-stream identity without redefining existing derivation semantics.

### Implementation Steps

1. In `fork_checkpoint.py` enumerate typed run-scoped fields of checkpoint receipts and owner envelopes. Preserve stable agent/entity/memory/belief/ledger IDs and original testimony/source IDs. Convert current-execution run envelopes to child scope; retain historical parent references in lineage. Reject an unknown receipt variant instead of applying generic string replacement.
2. Introduce canonical `fork_state_digest(checkpoint)` over explicit complete state values, using tagged deterministic encoding, stable tuple/map ordering and redacted repr. Do not use pickle, repr, global hash, wall time or mutable object identity. Digest scope is versioned and includes roster, hidden service state, complete runtime state and objective boundary. Exclude filesystem/attempt metadata, operational timing and storage capture-provenance labels from this scientific state digest; retain semantic cultural coverage and every behavior-significant state field. Record excluded provenance separately. Add typed encoding per supported value class and explicit set/map ordering; re-execution under the original logical parent identity must hash identically.
3. In `path_dependence_identity.py` define a separate versioned `slot_design_fingerprint`: hash base config, common setup, ordered numeric seeds, replica/F/slot counts, assignment seed and each arm ordinal's actual action schedules, excluding arm IDs/display labels, contrast labels, output paths and attempt metadata. Derive unique parent and opaque child slot IDs from this design fingerprint, numeric seed, seed ordinal, replicate, F and slot ordinal. Never include treatment labels in slot RunId or random-stream scope. Store arm assignment and full spec fingerprint separately. A label rename changes the ensemble document fingerprint but not simulation identities. One slot has exactly one scientific child RunId for its entire lifetime; attempt IDs describe storage/reconstruction, not replacement scientific runs.
4. Generate the predeclared random permutation of arms per replicate with `simulation.randomness.create_named_stream` and `StreamScope`, keyed by `assignment_seed`, slot-design identity, parent, F and replicate. Persist the full assignment before observing post-F outcomes; do not choose ordering or replacement identities based on results. Branch run IDs remain distinct, and resource execution order is sorted by opaque slot, independent of arm labels.
5. Compare full seed-channel manifests for every included pair. Record per-channel `shared`, `distinct`, `absent`, `reserved_ignored` or `unknown` using actual algorithm/scope/usage; collapse summary to shared/mixed/distinct/unknown conservatively across ALL pairs. Preserve derivation-v3 and existing run-ID scope for demography, initialization and lifespan. No claim that equal numeric seeds create common random numbers.
6. Initial recipe uses deterministic interval admissions, passthrough lifespan and no initialization parameter distributions (same constraints as BM), so unused draws are identified as such. Reject stochastic initialization/lifespan variants in v1. Still retain run-ID effects on generated identities and any other channels; report the estimand as the assigned intervention protocol under documented branch-identity noise, not a pathwise same-noise causal effect.

### Required Interfaces and Contracts

`build_branch_slots(spec, parent_identity, fork_tick) -> tuple[BranchSlot,...]`; `summarize_branch_channel_alignment(pairs) -> ...`. Labels renamed without changing the schedule or arm order cannot change opaque child IDs. Replicas and multiple F values from one parent seed never become independent inferential units.

### Requirement Evidence

`generational_seeds.py` actual channel manifest; user repeated seeds/branches and explicit intervention lineage; ARCHITECTURE deterministic identity rules.

### Error Handling and Logging

`fork_rebase_variant_unsupported`, `fork_random_policy_unsupported`, `assignment_identity_mismatch`. INFO policy/counts and coarse alignment; no complete-state digest, lineage payload or command fields in operational logs. Unknown alignment is disclosed, not repaired silently.

### Tests

`test_path_dependence_identity.py`: deterministic label-blind IDs, seed/replicate uniqueness, assignment reproducibility/order independence, duplicate seeds block together, mixed alignment in a later pair not masked by first pair, no global RNG access, supported distribution restrictions. `test_runner_fork_checkpoint.py`: nested typed receipt rebasing and old provenance retention.

### Acceptance Criteria

The protocol records its randomization before treatment; manifests truthfully distinguish shared objective streams from run-ID-scoped channels, and legacy derivation outputs do not change.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_path_dependence_identity.py tests/unit/test_generational_seed_manifest.py tests/unit/test_simulation_branch_runtime_rebase.py -q`

## Task 6: Prove replay and no-treatment continuation equivalence

### Intent

Provide a hard gate against losing subjective state or introducing hidden clone mutations.

### Implementation Steps

1. Build a real v55 fixture with interval admissions, a past death, kinship, dependency needs, a repository, and enabled norm/relationship/knowledge/narrative/institution ledgers. Use real in-memory services and deterministic fake provider.
2. Run to F, capture once, then compare uninterrupted continuation to a same-RunId restore in an isolated repository. Same-RunId reuse is test-only and never writes into the live parent repository. Require identical objective events/observations, action resolutions, owner service exports including legacy stores, complete runtime fork states, semantic channel coverage and future admission. Do not depend on Task 10–12 collectors/comparators here: full outcome-equivalence proof belongs to Task 16 after those interfaces exist. This avoids a hidden circular implementation dependency.
3. For production distinct child RunIds, verify exact pre-treatment semantic boundary equivalence and parent/sibling immutability; compare full child repeat executions with the SAME child identity in isolated test repositories for deterministic continuation. Production partial durable children are not automatically re-executed. Do not assert cross-child path equality where run-ID-scoped effects are documented. Include two untouched randomized slots as a negative-control diagnostic, not forced-zero statistical evidence.
4. Compare child live vs replay-restored observations at F and F+1 including committed prior-event window. Verify F=100 means ticks 0–99 are inherited and first intervention occurs on tick 100.

### Required Interfaces and Contracts

No normalization may erase agent behavior, roster, memories, lifespan or outcome differences. Envelope/hash normalization for cross-ID prefix comparison is an explicit allowlist; all other data must match.

### Requirement Evidence

User common-history requirement; ARCHITECTURE observation parity and append-only authority.

### Error Handling and Logging

Parity failures produce bounded field-path/count diagnostics, never subjective values. Do not loosen tests to accept lost fields. Failed parity blocks Tasks 7–18.

### Tests

New `test_path_dependence_replay_parity.py` performs the proofs above; mutate one copied ledger/history in a fault fixture and prove the comparison catches it. Include a representative existing `generational_comparison_base()` config rather than only custom stubs.

### Acceptance Criteria

All advertised continuation equivalences are demonstrated; distinct child-ID limitations remain explicit and do not masquerade as exact common random numbers.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_path_dependence_replay_parity.py tests/unit/test_experiment_bm_execution.py -q`

## Phase Risks and Mitigations

- Run identity can affect more than RNG: negative-control diagnostics and actual manifest comparisons qualify interpretation; no automatic causality label.
- Hidden runtime fields can escape a shallow rebase: explicit complete-state inventory, replay parity and exact roster tests are release gates.

## Phase Completion Checklist

- Tasks 4–6 pass, including same-identity uninterrupted continuation equivalence.
- Only `index.md` carries progress checkboxes.
