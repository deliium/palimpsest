# Phase 3: Ordinary execution, transactional state, and recovery

Plan: [index.md](index.md)
Tasks: 9–12
Depends on: Tasks 1–8

## Objective

Repeat another owner's described procedure through ordinary per-agent `Experiment`; preserve exactly-once owner state across commit, abort, pending recovery, forks, and retirement.

## Current-Code Evidence

| Path | Symbols / behavior | Required treatment |
| --- | --- | --- |
| `src/agents/cognition/loop.py` | `prepare`, `complete`, `_remember_experiments`, `_ingest_scientific_hypotheses` | Science currently installs `_experiment_ledger` during `complete`, before commit; do not reproduce this bug. |
| `src/agents/cognition/loop.py` | `experiment_ledger_for`, `experiment_ledger_if_present`, `restore_experiment_ledger`, `run` | The first accessor mutates on first read; the latter read/install helpers already exist. The one-call `run` wrapper invokes complete without runtime finalization. |
| `src/agents/cognition/experimentation.py` | `admit_hypothesis`, `apply_test_outcome`, `_find_hypothesis` | Admission may evict a pending test's row; exact outcome scoring requires it to remain present. |
| `src/agents/cognition/models.py` | `SubjectiveSnapshot`, `CognitiveLoopProposal`, `CognitiveLoopResult` | Explicit owner-safe state forwarding points. |
| `src/agents/cognition/contracts.py` | `Perspective.to_snapshot` | Carry only the selected owner's state. |
| `src/simulation/agent_runtime.py` | `bind_effective_command`, `finalize_pending`, `abort_pending`, `PendingRuntimeFinalization.to_finalization_command`, `pending_from_finalization_command`, `_pending_integrity_hash` | Final command, atomic finalization, abort and durable pending seams. |
| `src/simulation/run_control.py` | `AgentRuntimeCheckpoint`, `FinalizationCommand`, `encode_emotional_state`, `decode_emotional_state` | In-memory checkpoint and versioned pending contracts. |
| `src/simulation/runner_serialization.py` | `finalization_command_to_mapping`, `decode_finalization_command` | Exact v1 key set; cannot add fields to v1 silently. |
| `src/simulation/runner.py` | `export_experiment_ledgers`, `_pending_record_from_command`, `_command_from_pending_record`, `_freeze_retired_owner` | Exports, codec dispatch and terminal-owner retention. |
| `src/simulation/new_agent_initialization.py` | `SUBJECTIVE_COPY_DENY_LIST`, `BLANK_SLATE_SUBJECTIVE_STORES`, `BlankSlateStoreCounts` | Admission must start empty, not copy collaborators' science. |

## Files to Change

Create `src/agents/cognition/replication_actions.py`, `src/simulation/replication_checkpoint.py`; modify the paths above plus `src/agents/cognition/scientific_hypothesis_communication.py`, `src/simulation/perception.py`, `src/simulation/persistence.py`, `src/simulation/compatibility.py`, `src/simulation/runner_models.py`, public facades and the explicit fork state in `src/agents/cognition/fork_state.py` only if a behavior-significant loop-local field remains. Create `tests/unit/test_replication_runtime.py`, `test_replication_checkpoint.py`, `test_replication_recovery.py`, `test_replication_fork_retirement.py`.

## Task 9: Compile one receiver-owned ordinary experiment

### Intent

Execute replication without giving a design, invitation, or group command authority.

### Implementation Steps

1. Add `compile_replication_test(owner_id, replication_ledger, experiment_ledger, observation)` returning detached candidate ledgers, zero/one `Experiment`, selected attempt token and a closed reason.
2. Automatic selection requires both a complete delivered design and its delivered invitation, then owner-local acceptance; never execute from design delivery alone or arbitrary published analysis. Deterministic participation policy accepts a complete, currently testable invitation with trusted or unknown source appraisal; testing unknown testimony expresses inquiry, not belief. Contested testimony remains available for interpretation but is not automatically recruited. An explicit owner-local participation intent created through the pure `request_replication` ledger helper may request an already delivered design without an invitation and may test contested testimony. No forced agreement.
3. Sort ready requests by oldest accepted tick, then design token/invitation token. At most one command/owner/tick; share `ExperimentLedger.max_trials_per_tick` with ordinary scientific tests. Each accepted invitation schedules at most one attempt; another attempt requires a fresh delivered invitation or explicit owner-local `request_replication` intent. Duplicate invitations do not reset this bound.
4. Bind via Task 4. Generate a receiver-owned hypothesis ID from namespace, owner, frozen design token and concrete operand binding; do not reuse a source owner's hypothesis ID or silently merge two condition variants. Formulate/admit a local `ExperimentHypothesis` with source `COMMUNICATED`, local delivery provenance, confidence 500 and zero evidence.
5. Call `compile_scientific_test(..., hypothesis_id=local_id, formulate_if_missing=False, causal_model=None)` on the detached local candidate. Keep source identity separately in the replication sidecar. Return the ordinary command; do not submit or resolve it.
   Preserve existing `learn_into_genealogy` off/on settings and their independently gated direct-test learning; do not invent a replication-count uplift rule, copy practical knowledge, or equate learning with hypothesis truth.
6. Only replace a default `Wait`; preserve all meaningful commands and all engine validation. Accepted replication requests precede automatic self-formulated scientific tests within the existing science Wait-replacement block. If none is eligible, fall through to existing scientific selection, excluding IDs reserved for replication requests: add a default-empty `excluded_hypothesis_ids` argument to scientific selection so the old path cannot silently schedule untracked extra replications. Its default preserves existing callers.
7. Compute protected hypothesis IDs from every unresolved submitted attempt and unconsumed original source draft, plus the current proposed test. Extend `admit_hypothesis(..., protected_hypothesis_ids=frozenset())` so only unprotected rows can be evicted by the existing confidence/order rule. If all existing slots are protected, reject the new row unchanged; the replication compiler returns `replication_hypothesis_capacity`, not a half-created attempt.
8. Thread the same default-empty protection argument through `compile_scientific_test` and `adopt_communicated_hypothesis`, then pass it for all science-enabled admissions, including incoming `hyp_v1`. Legacy science-off callers retain the old default behavior. Completed measurements/designs remain immutable historical records even if their no-longer-pending hypothesis is later evicted.

### Required Interfaces and Contracts

The same `science` activation/prerequisites apply; no new flag/mode/root field. Source conditions must hold; variation requires an explicit child design. Operand visibility preflight is not authority. Capacity rejection yields no newly admitted hypothesis or orphan attempt.

Protection is temporary until result correlation or a deliberate cancellation resolves the pending record. Do not pin all historical hypotheses forever, increase configured caps, or bypass owner-local admission limits. Validate `actor_entity_id` against the runtime body binding before candidate acceptance.

### Error Handling and Logging

No material/condition mismatch/cap/untrusted source yields a skip reason, not a scientific failure. DEBUG candidates/skips; INFO one proposed test count/operator code. Never log source design, hypothesis payload, trust dimensions or bindings.

### Tests / Acceptance / Verification

`test_replication_runtime.py`: A shares procedure using tool A; B tests with tool B; preserved meaningful command; shared trial cap; invalid conditions; foreign-held operand; cap atomicity; two designs cannot conflate local hypothesis identity. Add max-hypotheses=1 cases with a pending test, a delayed result, and incoming `hyp_v1`: the pending row survives, the new admission is rejected without side effects, and only the matched hypothesis is scored. Verify protection releases after resolution and checkpoint/fork retains it through the pending references. Run `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_replication_runtime.py -q`.

## Task 10: Stage and finalize science/replication updates transactionally

### Intent

Fix the precommit installation in the science path as a prerequisite of reliable replication, without redesigning unrelated cognitive channels.

### Implementation Steps

1. Add optional owner-validated `replication_ledger` and `experiment_ledger` to `Perspective`, `SubjectiveSnapshot`, `CognitiveLoopProposal`, and `CognitiveLoopResult`; forward through `build_perspective` and every explicit constructor. These carry detached candidates/committed input, not changes to the existing `ExperimentLedger` shape. Runtime input uses the loop's committed science ledger and runtime's committed replication sidecar.
2. For science-enabled cognition, read an explicit snapshot ledger when present, otherwise `experiment_ledger_if_present()`; if absent construct `empty_experiment_ledger` as a local candidate only. Do not call the lazy-mutating `experiment_ledger_for()` anywhere on this science candidate path. Compute remembering, incoming `hyp_v1`, incoming `rep_v1`, interpretation and compilation on those candidates, passing Task 9's protected IDs. Refactor those science calls to return candidates rather than install `_experiment_ledger` during `prepare`/`complete`. Keep legacy science-off behavior and serialization unchanged.
3. Runtime owns the committed replication sidecar. `complete` returns candidates; it must not install replication or science candidates. At `finalize_pending`, validate both candidate owners, body bindings and live pending-hypothesis references before any side effects/installations, then use the existing owner-validating `CognitiveLoop.restore_experiment_ledger(candidate, owner_id)` as the installation primitive and `_commit_replication_ledger` for the sidecar. A new redundant science state store or alternate restore authority is unnecessary. Idempotent finalization must not recount any source/event.
   Capture a `ReplicationSourceDraft` for each actual original scientific Experiment command before submission; when its actor-visible result arrives, freeze the source design using the retained pre-action descriptors and create its original result report. A consumed operand therefore does not require post-hoc hidden-state access. Do not label an original test itself as a replication.
4. Bind proposed attempts only after `loop_result.command` is the actual effective command used by `bind_effective_command`. If an arbiter/boundary replaces Experiment with another verb, remove/cancel the proposed attempt and discard its test-formulated candidate changes; do not leave a pending phantom trial.
   Apply the same boundary to speech outbox state: only a final effective Talk/Tell retaining the complete canonical message stages an `attempted` outbox update for finalization and pending-v2 serialization. A replaced, stripped or aborted message cannot increment send-attempt count or create a delivered receipt.
5. At the next owner observation match at most one unresolved submitted attempt by actor identity, provenance `source_tick`, operator and operand-A target. Public perception does not expose operand B, process, hypothesis ID or attempt ID; never fabricate those from a `WorldEvent`. If matching is ambiguous/missing, retain `unresolved`.
6. Only actor-visible matching `experiment_resolved` contributes a local measurement. Bystander/witness reports remain observed speech/effects, not the owner's test. Deduplicate `source_event_id`. The uniquely matched attempt/source draft drives both measurement association and scientific scoring: call `apply_test_outcome` with that exact local hypothesis ID and the provenance execution tick, then `record_trial` once. The existing `score_remembered_experiment` / `_match_hypothesis` selects the newest operator/operand-A match and ignores conditions; do not use that fallback for science-enabled tracked tests. Route matched IDs explicitly and exclude consumed or ambiguous occurrences from legacy rescoring. Ambiguous events may be retained as unresolved, but must not support a different condition variant.
7. Distinguish an engine rejection from a resolved categorical failure. Rejection carries no measurement. A resolved failure with observable missing/unusable operand context gets an execution-limitation notice, not an unqualified contradiction of another source's procedure.
8. `abort_pending` discards both candidates and preserves the committed ledgers; callbacks/publication cannot influence cognition. No retroactive edits to committed objective events.
9. Preserve direct `CognitiveLoop.run()` as a one-call prepare/complete wrapper returning detached candidates, not an implicit scientific commit. Standalone callers/tests that continue cognition must explicitly carry accepted candidates into the next `SubjectiveSnapshot`; runtime-coordinated callers rely on objective commit/finalization instead. Update science-enabled direct-run tests to assert returned candidates rather than precommit installation. Do not add a `run()` shortcut that defeats abort safety.

### Required Interfaces and Contracts

Retain `prepare_parallel=False`. Empty replication sidecars are constructed only when science activates; science-off DTO defaults remain `None`. Owner admission initializes empty state. The transactional change is limited to the science-enabled experiment path required by replication.

### Error Handling and Logging

Owner mismatch fails before any installation; repeated finalization is a no-op for already installed transition identity. Missing outcome remains explicit unresolved evidence. DEBUG stage/commit/abort counts; WARN ambiguous matching; never raw observations/events or content fingerprints in logs.

### Tests / Acceptance / Verification

Add first-use prepare/run/abort with no pre-existing ledger (committed state stays absent), explicit direct-run candidate carry, ordinary runtime finalization commit, precommit exception, replaced command, duplicate finalize, matching actor vs witness, delayed event window, ambiguity, two condition variants sharing operator/operands, exact hypothesis scoring, and resolved-failure-vs-rejection cases. Assert aborted reply outboxes do not advance and normal finalized results enqueue the inviter reply exactly once. Run the Phase 3 focused command plus `tests/unit/test_scientific_hypotheses_test_wiring.py` and `tests/unit/test_runner_finalization.py`. No replication state or new scientific evidence is installed before objective commit.

## Task 11: Version pending payloads and preserve fork/checkpoint state

### Intent

Make pending owner updates recoverable without silently widening `finalization-command-v1` or claiming full subjective process restart.

### Implementation Steps

1. Add strict `replication-state-v1` checkpoint encoding in `simulation.replication_checkpoint` for the complete owner sidecar. Also encode the complete science candidate as nested `scientific-experiment-state-v1` using explicit `ExperimentLedger`/hypothesis/revision/trial fields. These are private subjective checkpoint records, not published research artifacts or objective codecs.
2. Add `replication_ledger=None` to `AgentRuntimeCheckpoint`; owner-validate, export and restore it. Missing legacy sibling means absent; malformed present data is rejected, never reset to empty. Existing runtime/fork checkpoints are process-local; do not pretend they already have a complete durable wire format.
3. Add `FINALIZATION_COMMAND_CODEC_VERSION_V2="finalization-command-v2"` while preserving the existing default-v1 constant. V1 has its exact old key set and no candidate payloads. V2 is exactly v1 keys plus `replication_state` and `scientific_experiment_state`; both are required valid owner records. Emit v2 only for a science-enabled transition carrying replication state.
4. Update `FinalizationCommand` accepted versions, `finalization_command_to_mapping`, `encode_finalization_command`, `decode_finalization_command`, pending conversion helpers and restore paths. V1 decoding produces absent candidates; v2 reconstructs both candidates without rerunning cognition/providers. Reject v1 with new keys, v2 missing keys, mixed owners, duplicate keys, unsupported nested versions and unresolved submitted attempt/draft references to missing hypotheses. Derive temporary protected IDs from restored pending references; no separate stale protection cache is serialized.
5. Extend pending record accepted versions in `simulation.persistence`, `simulation.compatibility` and runner dispatch. `_pending_record_from_command` must store `command.codec_version`, not always the old constant. Validate record/payload version agreement. Preserve existing fail-closed handling of ancient `pending-finalization-v1`; do not weaken its runtime rejection to make the compatibility table appear green.
6. For v2 only, include canonical full candidate-state SHA-256 in `_pending_integrity_hash` input and verify it during restore and idempotence checks. V1 hashes remain unchanged. Do not use the counts-only scientific analysis digest.
7. Runtime fork exports carry the committed sibling transitively through `AgentRuntimeCheckpoint`. Avoid a second replication authority in `CognitiveLoopForkState`; explicitly preserve any remaining loop-local scheduling counters only. Retirement stores frozen complete runtime/fork records; exports include retired owners.
8. Add replication to blank-slate deny/store/count lists. Probe actual new ledger counts in the admission regression rather than trusting `BlankSlateStoreCounts()`'s zero defaults.

### Required Interfaces and Contracts

No runner/result JSON schema bump, event marker, world codec bump, SQL migration, or new replay mode. Pending v2 recovery covers the serialized science/replication transition only; complete durable subjective resume remains unsupported. Default runner/result remain v4/v2; feature family remains v55/v56.

### Error Handling and Logging

Corrupt/foreign/tampered pending records fail closed before installation. Publication/logging never dumps subjective candidates. INFO restored transition version/counts; ERROR safe codec/owner/integrity codes.

### Tests / Acceptance / Verification

`test_replication_checkpoint.py`, `test_replication_recovery.py`, `test_replication_fork_retirement.py`: v1 golden bytes, v2 full-content round trip, field-only tampering at equal counts, crash before commit/after commit/during finalize, no provider rerun, record/payload version mismatch, restore idempotence, parent/child independence, retired-owner export, genuinely nonempty newborn rejection. Run all four Phase 3 test files plus `tests/unit/test_runner_finalization.py` and `tests/unit/test_compatibility_matrix.py` with coverage.

## Task 12: Lock activation, owner boundaries, and off-path compatibility

### Intent

Prove the new behavior deepens the owned science seam and does not reopen capability ownership.

### Implementation Steps

1. Extend `SimulationRunnerResult` with default-empty, ordered, duplicate-owner-rejecting in-memory `replication_ledgers`; add `SimulationRunner.export_replication_ledgers` using runtime/retired checkpoints. Do not add fields to existing result-v2/v3 wire mappings.
2. Keep science activation at accepted v56 + `science` + `predictive_world_model` + `bounded_experimentation` and existing cultural prerequisites. Do not introduce a new `formal_rules=True` executable requirement from registry prose.
3. Add tests for science off (no sidecar, same command/event/serialization bytes), on without messages (source recording only), on with replication, missing prereqs, restored old checkpoints, and non-science bounded experimentation.
4. Extend `tests/architecture/test_replication_boundaries.py` and new `test_replication_invariants.py`: no private world access, no new world actor/executor, no automatic truth, no scientific results fed from analysis/persistence/API, no changes to 43 commands/73 semantics.

### Error Handling and Logging

Use existing capability error codes/stages. Invalid export owners fail closed; missing retired evidence is partial, not synthesized. Logs contain activation/version/count metadata only.

### Tests / Acceptance / Verification

Run all `tests/unit/test_replication_*.py`, `tests/unit/test_scientific_hypotheses_*.py`, `tests/architecture/test_replication_*.py`, `tests/architecture/test_scientific_hypotheses_*.py`, `tests/unit/test_v1_regression_gate.py`, `tests/unit/test_v2_scientific_invariants.py`, and `tests/unit/test_runner_config_v56.py` with `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term ... -q`. Science-off parity and v1 pending bytes are mandatory.

## Phase Risks and Mitigations

- Existing precommit science mutation: remove it from the science-enabled path rather than layering a second sidecar on a nontransactional update.
- Insufficient observation correlation: preserve unresolved state; do not expand perception/event authority to obtain private request fields.
- Recovery shape change: new pending v2 with exact accepted sets; no silent legacy widening.

## Phase Completion Checklist

- Tasks 9–12 pass crash/abort/fork and compatibility verification.
- Index remains the sole progress ledger.
