# Phase 5: Finalization, recovery and lifecycle

Plan: [index.md](index.md)
Tasks: 17–20
Depends on: Tasks 13–16

## Objective

Carry measurement beliefs through the same transaction, supported checkpoint, fork and retirement paths as existing science state, without claiming full durable subjective resume.

## Current-Code Evidence

| Path | Symbols / evidence | Why it matters |
|---|---|---|
| `src/simulation/agent_runtime.py` | `PendingRuntimeFinalization`, `to_finalization_command`, `pending_from_finalization_command`, `finalize_pending` | Proposed sidecars install after objective commit only. |
| `src/simulation/run_control.py` | `FinalizationCommand`, `AgentRuntimeCheckpoint`, accepted v1/v2 codecs | Do not silently add fields to pending v2. |
| `src/simulation/runner_serialization.py` | pending-command serialization near 12132 | Canonical recovery payload must version its new state. |
| `src/simulation/replication_checkpoint.py` | strict state codecs/digests | Follow the structure in a new measurement-named module. |
| `src/simulation/perception.py` | `build_perspective` science sidecar args | Restore/export only the owner's ledger. |
| `src/simulation/new_agent_initialization.py` | blank-slate science restrictions | Birth/admission does not transfer beliefs or references. |
| `tests/unit/test_replication_recovery.py`, `tests/unit/test_replication_fork_retirement.py` | existing recovery/fork cases | Measurement must participate in every supported science lifecycle lane. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/simulation/measurement_checkpoint.py` | create | Exact `measurement-state-v1` codec/digest. |
| `src/simulation/agent_runtime.py`, `src/simulation/run_control.py`, `src/simulation/runner_serialization.py`, `src/simulation/persistence.py`, `src/simulation/runner.py` | modify | Candidate commit, pending-v3 constants/accepted sets and stored-record recovery gates. |
| `src/simulation/perception.py`, `src/agents/cognition/models.py`, `src/simulation/runner.py` | modify | Owner-safe snapshot, checkpoint and initialization composition. |
| `src/simulation/new_agent_initialization.py` | modify | Explicit blank-slate measurement exclusion. |
| `src/experiments/civilization_benchmark_evidence.py`, `tests/unit/test_new_agent_blank_slate_guard.py` | modify | Real content probes and exhaustive blank-slate store enumerations. |
| `tests/unit/test_measurement_checkpoint.py`, `tests/unit/test_measurement_recovery.py`, `tests/unit/test_measurement_fork_retirement.py`, `tests/unit/test_measurement_lifecycle.py` | create | Strict roundtrip, crash/idempotency, clone isolation and newborn cases. |

## Task 17: Add measurement-state-v1 and pending finalization v3

### Intent

Recovery must preserve the exact proposed subjective transition without altering established pending-v1/v2 bytes.

### Implementation Steps

1. Add strict `encode_measurement_state`, `decode_measurement_state` and canonical digest helpers in `measurement_checkpoint.py`. Envelope keys: `codec_version`, `owner_id`, `policy_version`, `ledger`. Codec is `measurement-state-v1`.
2. Serialize the bounded owner reading/report/belief/revision/receipt arrays and explicit notices with exact record keys, sorted deterministic ordering and source distinctions. Do not serialize objective instrument/reference records into the subjective envelope.
3. Add `FINALIZATION_COMMAND_CODEC_VERSION_V3 = "finalization-command-v3"` and accepted-set membership in run control. Its exact payload is pending-v2 plus `measurement_state`; retain v2 science/replication fields as already versioned nested envelopes.
4. Select v3 only when a measurement-enabled owner transition carries measurement state, including an empty enabled ledger. Absent-spec science continues to emit pending-v2; default non-science stays pending-v1.
5. Decode v1/v2 with measurement state absent, not an invented empty enabled ledger. Reject measurement fields under v1/v2, missing state under v3, owner mismatch, extra fields, duplicate rows or inconsistent digests.
6. Add `PENDING_FINALIZATION_CODEC_VERSION_V3` to `simulation.persistence.PENDING_FINALIZATION_ACCEPTED_VERSIONS`, keeping default v1 and historical v2 constants unchanged. Update the mirror in run control and compatibility tests together. In `FinalizationCommand.__post_init__`, v1 forbids all candidate sidecars, v2 requires its existing experiment/replication pair and forbids measurement state, and v3 requires all three. Broaden existing v2 science-envelope branches in serialization explicitly to `{v2,v3}`, then add the v3-only measurement envelope. A v3 record must not accidentally omit the existing science payloads.

### Required Interfaces and Contracts

No bump to objective replay based on this subjective codec; event28/v26 already belongs to physical instruments. No SQL schema change: existing opaque recovery payload stores the new version.

### Requirement Evidence

Architecture extension rules and existing V4-28 pending-v2 contract; Original Request requires agent-specific fallible interpretation, not shared physical truth.

### Error Handling and Logging

Follow metadata-only codec errors and payload-safe repr. State digests are integrity machinery and must not be logged as content surrogates.

### Tests

New envelope/pending roundtrips; canonical ordering; unknown/duplicate keys; tampered digest, wrong owner/policy, caps, communicated/direct mismatch; unchanged v1/v2 golden bytes and legacy decoder output. Assert persistence/run-control accepted-set parity and all three codec versions' candidate-presence rules, including v3 missing either existing science sidecar.

### Acceptance Criteria

Supported recovery can represent one owner's measurement proposal exactly without widening previous pending schemas.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_measurement_checkpoint.py tests/unit/test_replication_checkpoint.py --cov=simulation --cov-report=term-missing -q`

Expected: new strict codecs and old golden fixtures pass.

## Task 18: Commit and recover measurement state atomically

### Intent

No failed or replaced proposed action may create a phantom physical reading, and no observed reading may be committed twice.

### Implementation Steps

1. Carry candidate measurement state through `PendingRuntimeFinalization`, `to_finalization_command`, `pending_from_finalization_command` and `AgentRuntime.finalize_pending`.
2. Include its digest in the same proposed-state integrity and effective-command checks used for science sidecars. Install the ledger only after committed objective action resolution and successful subjective mutation handling.
3. Distinguish ingestion of an already committed prior observation from speculative bookkeeping about the current proposed command. Replacing a proposed Measure cancels only its speculative send/action marker, not legitimate evidence acquired from the previous tick.
4. Reject/abort before objective commit leaves current physical instrument state and committed subjective ledger unchanged. After physical commit but before subjective finalize, recorded recovery replays the exact v3 transition once.
5. Test all supported crash points using existing crash-injection patterns, including repeat finalization and mismatched effective commands. Never synthesize a reading from the submitted command when its result is unavailable.
6. Update `runner._command_from_pending_record`: replace its hard-coded v1/v2 accepted set with the public `PENDING_FINALIZATION_ACCEPTED_VERSIONS` contract containing v3, while retaining the separate legacy-pending rejection. Exercise the real `_pending_record_from_command` → `PendingFinalizationRecord` persistence encode/decode → `_command_from_pending_record` → pending reconstruction/finalize chain. Do not settle for direct `decode_finalization_command` unit success.

### Required Interfaces and Contracts

Physical readings originate from committed events and are normally ingested on the next observation. An accepted calibration doesn't imply the owner believes it succeeded accurately. Subjective state installation does not mutate the physical sidecar.

### Error Handling and Logging

On hash/owner/transition mismatch, fail closed with safe code and leave committed state intact. INFO/DEBUG logs use owner/run/tick, phase and counts only. No payload or digest logging.

### Tests

Abort before commit; crash after objective commit; crash during subjective finalize; replay exact-once; rejected/overridden instrument command; legitimate previous-window reading survives next-command replacement; reading not yet visible remains absent; repeated v3 recovery idempotence. Persist/restore an actual pending-v3 record through the runner's stored-record gate; v1/v2 still recover and an unknown future codec still fails closed.

### Acceptance Criteria

Live and recovered supported transitions yield identical owner ledger digests and physical histories; no phantom display or duplicate belief revision.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_measurement_recovery.py tests/unit/test_replication_recovery.py --cov=simulation --cov=agents.cognition --cov-report=term-missing -q`

Expected: transaction and crash-injection cases pass.

## Task 19: Preserve owner-safe checkpoints, forks and retirement

### Intent

Scientific fork/retirement behavior must include measurement beliefs without sharing mutable state or granting subjective restart promises.

### Implementation Steps

1. Add the optional ledger to `build_perspective`, committed owner snapshot/checkpoint export and restore using `measurement-state-v1`. Only the matching owner may receive it.
2. Follow the actual V4-28 fork/retirement call chain exercised by `test_replication_fork_retirement.py`; propagate the new field through each fork-capable runtime export/clone/retired record constructor it uses. No unrelated retention refactor.
3. Clone immutable measurement state into process-local fork children. Physical instrument state comes from the child's objective snapshot; subjective reliability starts from the captured owner's process-local ledger, then diverges independently.
4. Preserve state and processed receipts for fully finalized retired dead owners. Historical reading inspection remains qualified and read-only.
5. Missing capture is explicitly unavailable; do not reconstruct lost owner beliefs from objective instrument parameters or event truth. Completed historical replay remains objective inspection, not full durable subjective resume.
6. Add `SimulationRunner.export_measurement_ledgers() -> tuple[MeasurementLedger, ...]`, sorted by owner ID, following `export_replication_ledgers`: export each runtime checkpoint's committed measurement ledger and fall back to `retired_record.runtime_checkpoint` for retired owners. Enabled empty ledgers are retained; spec-off owners are absent. Return immutable detached rows with a count-only log. Do not add `measurement_ledgers` to serialized `SimulationRunnerResult` v2/v3 or silently widen result JSON; tests and trusted experiment callers use the explicit runner method.

### Required Interfaces and Contracts

Opaque lineage IDs do not grant cross-owner lookup. Forks may share immutable source rows, never a mutable belief ledger. Same instrument may have different beliefs in different branches and owners.

### Error Handling and Logging

Wrong-owner/version/hash restore fails closed; unsupported subjective resume stays unsupported. Emit availability notices rather than empty-as-known evidence.

### Tests

Snapshot ownership rejection; fork twin initial parity then diverging calibration/appraisal; no mutation across children; retirement preserves readings/revisions/receipts; missing owner capture unavailable; physical-only replay does not recover reliability beliefs. Assert real runner exports include active and retired owners, preserve owner order, do not alias mutable state and leave existing result-v2/v3 bytes unchanged.

### Acceptance Criteria

All already-supported science checkpoint/fork/retirement lanes preserve qualified owner state and privacy.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_measurement_fork_retirement.py tests/unit/test_replication_fork_retirement.py --cov=simulation --cov-report=term-missing -q`

Expected: state fidelity and branch isolation pass without new resume claims.

## Task 20: Enforce blank-slate admission and spec-off parity

### Intent

New agents can learn to use visible instruments but cannot inherit another owner's calibration beliefs or knowledge automatically.

### Implementation Steps

1. Add singular/plural measurement-ledger names to `SUBJECTIVE_COPY_DENY_LIST`, add the singular store to `BLANK_SLATE_SUBJECTIVE_STORES`, and add an integer `measurement_ledger=0` to `BlankSlateStoreCounts` in `new_agent_initialization.py`. Extend the exact pinned store tuple in `tests/unit/test_new_agent_blank_slate_guard.py`; adding only a deny string is insufficient.
2. When the run spec is present and the admitted agent's existing science prerequisites are enabled, initialize only an empty owner ledger. Do not copy parent/founder readings, reliability, reference values or processed roots. Existing disabled science profiles remain disabled.
3. Physical ownership changes still require ordinary existing item transfer/admission rules; a birth does not create or gift an instrument.
4. Exercise present/absent spec composition and existing species profiles. Do not add a new species profile, per-agent runner key or capability flag.
5. Compare an actual existing science-v56 run fixture before and after integration: same commands, objective fingerprints, pending-v2 bytes, categorical ledgers and outcome counts. Default v4 remains unchanged as well.
6. Expose `CognitiveLoop.measurement_ledger_if_present()` for an actual-content probe. Extend `runner._blank_slate_counts` to count measurement evidence/reports/beliefs/revisions/receipts/notices as well as existing replication content; remove the replication-only early return that would hide measurement content when replication state is absent. Empty frozen ledgers count0, not opaque-object1.
7. Add `measurement_ledger: ("runtime", "measurement_ledger")` to `experiments.civilization_benchmark_evidence.STORE_PROBE_PATHS` and a typed measurement content-count helper analogous to `_replication_content_count`. `_measure_owner` must count real rows for the new store, not mark it unmeasured or use generic opaque-object counting. This is existing admission/benchmark invariant maintenance, not a new benchmark feature.

### Required Interfaces and Contracts

Enabling physical instruments does not assert a scientist identity, mentorship, trust, shared measurement standard or automatic skill. Capability to act physically is separate from owner knowledge.

### Error Handling and Logging

Reject prohibited inherited state; safe initialization reason codes/counts only. No silent enabling of an old disabled profile.

### Tests

Founder/newborn owner separation, explicit inherited-ledger rejection, empty ledger initialization, disabled profiles, no gifted tools, v56/default byte and trajectory parity, and empty enabled state uses pending-v3 only on the new path. Test all store enumerations/probe-map parity, empty versus populated frozen measurement ledgers, actual admission rejection with nonempty content, and measurement content detected even when replication state is absent.

### Acceptance Criteria

Population admission respects blank-slate cognition and legacy off-path behavior stays deterministic.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_measurement_lifecycle.py tests/unit/test_new_agent_blank_slate_guard.py tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py --cov=simulation --cov=agents.cognition --cov=experiments --cov-report=term-missing -q`

Expected: lifecycle and existing flags-off invariants pass.

## Phase Risks and Mitigations

- New sidecar omitted from a fork/hash path: trace and extend the existing replication lifecycle tests, not just constructor signatures.
- Existing observed evidence discarded on command replacement: separate evidence ingestion from speculative command bookkeeping.
- Full subjective resume accidentally implied: document and test explicit unavailability outside already-supported lanes.

## Phase Completion Checklist

- Tasks 17–20 meet recovery, owner isolation, lifecycle and legacy parity criteria.
- Update progress only in `index.md`.
