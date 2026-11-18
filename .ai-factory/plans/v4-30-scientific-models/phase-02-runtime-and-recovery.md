# Phase 2: Temporal lifecycle and recoverable owner state

Plan: [index.md](index.md)
Tasks: 5–8
Depends on: Tasks 1–4

## Objective

Carry predictive state through ordinary candidate/finalization, recovery,
checkpoint and fork paths. Outcomes must occur after committed issuance.

## Current-Code Evidence

| Path | Symbols / section | Why it matters |
| --- | --- | --- |
| `src/agents/cognition/loop.py` | `complete`, experiment/replication/measurement candidate blocks; ledger accessors | Prepare candidates without installing committed owner state. |
| `src/agents/cognition/models.py` | snapshot/proposal/result sidecar fields, `CognitiveLoopResult` | All transport boundaries must carry the new optional sidecar. |
| `src/simulation/agent_runtime.py` | `PendingRuntimeFinalization`, `finalize_pending`, `_pending_integrity_hash`, checkpoint/fork methods | Post-world-commit owner state and exactly-once recovery. |
| `src/simulation/run_control.py` | `FinalizationCommand`, `AgentRuntimeCheckpoint` | v1/v2/v3 have distinct exact candidate payload contracts. |
| `src/simulation/runner_serialization.py` | `finalization_command_to_mapping`, `decode_finalization_command` | Exact codec evolution; do not widen old payloads. |
| `src/simulation/engine.py` | `_EngineSnapshot` advances to `Tick(tick.value + 1)` | Explains why target observation `t+1` is too early for a forecast finalized after tick `t`. |
| `src/world/_perception.py` | `_experiment_public_facts` | Actor facts expose operator/outcome, not the complete process/operand payload; correlate with a separate owner action binding. Read as evidence only; no changes planned. |
| `src/simulation/runner.py` | `_finalize_and_acknowledge`, `recover_pending_finalizations`, `export_measurement_ledgers` | Recovery without cognition reruns and retired-owner exports. |

## Files to Change

| Path | Action | Responsibility |
| --- | --- | --- |
| `src/agents/cognition/scientific_model_observation.py` | create | Closed, owner-visible outcome adapters and due-case settlement. |
| `src/agents/cognition/scientific_model_lifecycle.py` | create | Ordered settlement, derivation, forecast and retention transition. |
| `src/agents/cognition/models.py`, `src/agents/cognition/loop.py` | modify | Optional owner state transport, accessors, candidate generation. |
| `src/simulation/agent_runtime.py`, `src/simulation/run_control.py` | modify | Pending candidate, v4 validation, finalization and checkpoint fields. |
| `src/simulation/scientific_model_checkpoint.py` | create | Strict `scientific-model-state-v1` canonical codec/digest. |
| `src/simulation/runner_serialization.py` | modify | Exact pending v4 and checkpoint encoding/decoding. |
| `src/simulation/runner.py`, `src/simulation/fork_checkpoint.py` | modify | Restore/fork/export coverage including retired owners. |
| `src/simulation/runner_models.py` | modify | Composition-only predictive ledgers in completed results. |
| `src/simulation/new_agent_initialization.py` | modify | Copy deny/store lists and actual content counts. |
| `src/experiments/civilization_benchmark_evidence.py` | modify | Existing blank-slate probe map/count dispatch only. |
| `tests/unit/test_scientific_models_lifecycle.py` | create | Observation matching and timing. |
| `tests/unit/test_scientific_models_runtime.py` | create | Candidate commit and failure boundaries. |
| `tests/unit/test_scientific_models_checkpoint.py` | create | Leaf and pending payload integrity. |
| `tests/unit/test_scientific_models_recovery.py` | create | Retry, crash and fork continuity. |
| `tests/unit/test_new_agent_blank_slate_guard.py` | modify | Store enumeration and actual empty/populated ledger checks. |
| `tests/unit/test_scientific_models_result.py` | create | Completed-result construction, validation and live/retired exports. |

## Task 5: Settle future outcomes from actual owner observations

### Implementation Steps

1. Implement `resolve_due_model_cases(ledger, observation)` returning a new ledger.
   Cases issued from observation tick `t` resolve only from the exact target
   observation `t+2`; do not reinterpret a later sample as the missed target.
   If the next consumed observation is later than the target, close the case as
   `unavailable_missing_observation`. Preserve separate sample/event and receipt
   ticks, source observation key and evidence channel.
2. Season: use only `Observation.season` at the target boundary. Missing season
   is unavailable. Resource: require the same visible entity, location, kind and
   unit; compare target quantity milli to frozen issuance quantity milli.
   No visibility, location change, changed unit or identity ambiguity yields no
   scored outcome. Never read `ResourceRegenerated` or private resource state.
3. Production: inspect only the owner's eligible `ObservedOccurrence` from the
   prior-event window at target observation `t+2`. Require occurrence event tick
   `t+1`, ACTOR audience, the observation's self-entity as actor, a matching
   operator and a visible categorical experiment result. Require a separate
   `ModelExecutionBinding` for the exact frozen operator/operands/process at
   `t+1`; it records the owner's actual effective command, not event-store data.
   The actor's redacted facts do not expose full process/operands: never pretend
   they do or use the legacy loose latest-hypothesis match. Check exposed
   operand fields for contradictions, and require exactly one matching own
   occurrence for the bound tick. Do not add hidden fields to perception.
   Zero matching executions is
   `not_attempted`; several distinct matches are `not_comparable_ambiguous`.
   A command denial without a completed categorical result is not a forecast
   failure. Old events received late are ineligible.
   If the bound action's required source conditions changed or were unknown at
   execution-time observation, close `not_comparable` even if its exact command
   executed; do not score it under the issuance conditions.
4. Outcome states are `pending`, `observed`, `unavailable`, `not_attempted`,
   `not_comparable`. Only `observed` cases enter scores. Preserve raw observed
   resource start/end milli values in private owner state, plus the derived
   class. Absence of a fact is never a negative fact.
5. Execute lifecycle in this exact order on a detached candidate:
   settle prior cases → score both frozen candidates → update empirical
   parameters and append revisions → derive/update hypotheses from current
   owner evidence → issue a new pair → enforce retention. A new case cannot
   consume evidence already used in that same update as its future outcome.

### Interfaces, Errors and Logging

Add `advance_scientific_models(ledger, observation, *, experiment_ledger,
causal_world_model)` as the loop-facing pure transition. Reject mismatched owner
or inconsistent prior temporal bounds. Optional missing data produces explicit
coverage; repeated observations/outcomes are idempotent. Log counts/reasons only.

### Tests

At ticks 10/11/12, issue at 10, finalize tick 10, reject observation 11 as target,
settle observation 12. Production event tick 11 is eligible, event 10 or 9 is
not. Cover skipped target observations, foreign actors, bystander redaction,
duplicate receipts, no action, denial, ambiguous execution, intervening harvest
and resource occlusion.

### Acceptance Criteria and Verification

No scored outcome has a physical event/sample boundary at or before committed
issuance; missing data never enters a performance denominator.

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_scientific_models_lifecycle.py -q`

## Task 6: Integrate staged cognition without adding action authority

### Implementation Steps

1. Add optional `scientific_model_ledger` transport fields beside existing science
   sidecars in snapshot, proposal and loop-result contracts. Follow each
   existing model's validation/copy convention rather than inserting a shared
   mutable reference.
2. Add private committed ledger storage plus `scientific_model_ledger_if_present`
   and `restore_scientific_model_ledger` accessors on `CognitiveLoop`. Restore
   requires the correct owner and policy. New owners start empty; initialization
   profiles transfer no model, training counts or predictions.
3. Enable candidate creation only on the already-owned `science` path after its
   normal prerequisites have been validated. With `science=False`, transport
   remains `None` and no derivation, audit, serialization change, RNG draw or
   command change occurs. No new flag, per-agent mode or runner key.
4. In `complete`, obtain the prior snapshot/committed ledger, call the pure
   transition with owner observations and detached science sources, and attach
   the resulting candidate. Never mutate the loop ledger during prepare or
   submit a command. Existing replication, scientific-test and measurement action
   selection retains its precedence.
5. Carry the candidate into `PendingRuntimeFinalization`; install only after
   the objective commit and ordinary subjective transaction succeeds. A prepare
   exception, cancelled invocation or rejected candidate persistence leaves no
   installed forecast. Ordinary effective-command replacement does not cancel
   a future observational case; a future unexecuted production case becomes
   `not_attempted` at its target, not retrospectively rewritten.
6. Before the pending integrity hash is sealed, call
   `bind_scientific_model_execution(candidate, effective_command, tick,
   observation)` using
   the final effective command, not the original proposal. For previously
   committed production cases issued at `tick-1`, append an immutable
   `ModelExecutionBinding` only if that exact owner command is `Experiment` and
   matches the frozen claim. This record contains tick/operator/operand/process
   and case ID plus a closed condition-comparability status, never an outcome or
   revised prediction. Compare only required frozen source conditions against
   this owner's action-time observation; missing is unknown, not a match.
   At most one binding
   per case; unknown/mismatched commands leave it unbound. Persist bindings in
   the candidate and digest. This is action correlation, not command generation.
   Exact placement in `AgentRuntime.bind_effective_command`: after
   `command = require_agent_command(loop_result.command)`, before
   `candidate_digest`/`_pending_integrity_hash`. Replace the frozen loop result's
   predictive candidate with the binding-adjusted candidate before constructing
   pending state. Never bind the pre-`complete` argument: loop-boundary modifiers
   may replace it. Binding, submission and integrity digest describe the same
   final command.

### Errors, Logging and Tests

Source owner mismatch is a safe hard error; absence is an empty source with
coverage. Add candidate-count DEBUG logs only. Test science off byte-equivalence,
prepare-before-finalize accessors, failed prepare, failed subjective commit,
meaningful-command preservation, command substitution and independent owners.
Include pre-loop `Wait` changed into `Experiment` by `complete()` and original
`Experiment` replaced by another final command. Only the submitted command is
bound and hashed.

### Acceptance Criteria and Verification

Only ordinary finalized state exposes forecasts; scientific models never create
or replace any `AgentCommand` and cannot consult global state.

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_scientific_models_runtime.py tests/unit/test_measurement_recovery.py -q`

## Task 7: Add strict predictive state and pending-finalization codecs

### Implementation Steps

1. Add explicit allowlisted dataclass/enum encoding and decoding for
   `scientific-model-state-v1`, modeled on `measurement_checkpoint.py`.
   Include all model hypotheses, pinned revisions, distributions, temporal
   bounds, empirical counts, pending/terminal cases, sequences, selection cursor,
   last observation key and retention watermarks. Canonical digest changes on
   any content change, not merely count changes. Include separate execution
   bindings (at most one per retained case) with owner/tick/claim closure.
   Validate Task 1's nested evidence/vector bounds and aggregated notice keys.
   Old opaque evidence/parent references can be explicitly unavailable after
   retention; a retained forecast's source/model revision cannot be missing.
2. Introduce `finalization-command-v4`. Its exact payload is the existing common
   fields plus all four named candidate keys:
   `experiment_ledger`, `replication_ledger`, `measurement_ledger`,
   `scientific_model_ledger`. Scientific-model state is mandatory/non-null in
   v4; other sidecars are nullable, with experiment and replication either both
   present or both absent. Measurement requires its existing science prerequisites.
3. v1/v2/v3 keep their exact old keysets and candidate requirements, and forbid
   scientific-model state. Select v4 only when predictive candidate state is
   present; otherwise preserve existing selection and default v1 bytes.
   Do not require measurement merely to persist season/resource models.
4. Include the predictive digest independently in `_pending_integrity_hash`,
   outside replication/measurement nesting. Validate run/owner/tick and pinned
   revision closure during decode and before installation. Do not widen world
   replay/domain envelopes or runner config schemas.
5. Extend `AgentRuntimeCheckpoint` and its actual encode/decode call sites with
   optional predictive state using the existing additive checkpoint convention.
   Legacy absence restores `None`; unknown predictive payload versions fail
   closed. Pending-v4 recovery reconstructs the stored candidate without invoking
   cognition, sources, providers or scoring a second time.

### Errors, Logging and Tests

Use `scientific_model_state_invalid`, `scientific_model_owner_mismatch`,
`scientific_model_revision_missing` and existing pending-integrity errors.
Never log serialized payloads or content hashes. Test exact round trips, unknown
keys/version, foreign owner, same-count probability/tick/count tampering,
missing pinned revisions, all-null v4 rejection and unchanged legacy bytes.

### Acceptance Criteria and Verification

Recovery has every frozen prediction and receipt needed for exactly-once
continuation, while old codecs retain their accepted sets.

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_scientific_models_checkpoint.py tests/unit/test_replication_checkpoint.py tests/unit/test_measurement_recovery.py -q`

## Task 8: Preserve fork, retry, retirement and completed-run exports

### Implementation Steps

1. Extend runtime checkpoint export/restore with committed predictive state.
   `AgentRuntimeForkState.checkpoint` already carries it, and
   `restore_fork_state` restores that checkpoint before loop continuation.
   Do not duplicate the ledger in `CognitiveLoopForkState` or add prepared state:
   forks already reject open finalizations. In `fork_state_digest`, include
   `scientific_model_state_digest` for each non-null runtime predictive ledger;
   omit that key entirely when absent, preserving science-off digest material.
   Preserve the same
   owner-local frozen case IDs in fork children; run publication tokens later
   distinguish runs. Child containers must not alias parent mutable state.
2. Add `SimulationRunner.export_scientific_model_ledgers()` returning detached
   owner ledgers, including owners retained via the existing retired-owner
   mechanism. Do not restore retired runtime graphs merely to export data.
   Add `SimulationRunnerResult.scientific_model_ledgers: tuple[object, ...] = ()`
   in `runner_models.py`, with ordered-sequence, exact ledger-type and
   duplicate-owner validation following `replication_ledgers`. Populate the
   actual result construction in `SimulationRunner.run`. This is composition-only
   owner state, not a new runner-result wire field/schema. Completed results
   remain sufficient after the live runner is discarded.
3. Ensure bootstrap/admission starts an empty owner ledger; checkpoint restore is
   explicitly distinct from newborn initialization. No model sharing, global
   leaderboard or durable subjective-resume promise is introduced.
   Add singular/plural field names to `SUBJECTIVE_COPY_DENY_LIST`, the singular
   store to `BLANK_SLATE_SUBJECTIVE_STORES`, and `scientific_model_ledger: int`
   to `BlankSlateStoreCounts`. Define public typed
   `scientific_model_content_count` in `agents/cognition/scientific_models.py`,
   export it through the cognition facade, and reuse it in `runner._blank_slate_counts` and
   `civilization_benchmark_evidence.STORE_PROBE_PATHS`/probe dispatch.
   Count actual hypotheses/models/samples/revisions/cases/bindings/context bins/
   summaries/notices and non-default behavioral watermark/cursor state.
   `None` and a pristine frozen ledger count zero; populated/advanced state
   cannot pass through zero defaults or generic opaque-object counting.
   Invalid owner/type fails closed; extend the pinned blank-slate guard test.
4. Reuse recovery idempotency hashes and observation high-water keys: crashes
   after stored pending command, after world commit, after subjective commit and
   before acknowledgment produce the same ledger as uninterrupted execution.
   A case remains pending if no later owner observation occurs, including death
   or run termination; exporters report it pending/right-censored, never failed.

### Errors, Logging and Tests

Refuse an owner/policy/digest mismatch before installing any state. Use safe
recovery count logs. Test fork-before-outcome divergent children, identical twins,
source revision trimming with pending cases, dead-owner export, fresh newborns,
repeated recovery and restart without cognition/provider invocation.
Test same-count probability/count changes affect the fork digest, absent state
preserves off-path digests, results contain live and retired owners, duplicate
owners fail validation, and admission rejects a real populated ledger while
accepting a pristine empty one.

### Acceptance Criteria and Verification

Uninterrupted, retried and restored continuations have identical canonical
predictive state; independent fork outcomes do not rewrite parent forecasts.

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_scientific_models_recovery.py -q`

## Phase Risks and Mitigations

- An observation tick is not an outcome event tick: retain both and enforce
  exact target matching with the two-boundary protocol.
- Existing pending codecs require correlated sidecars: use a new exact v4 shape,
  not silent widening or artificial mandatory measurement state.
- Recovery can double-train: only stored transitions and exactly-once owner
  finalization may install counts/revisions.

## Phase Completion Checklist

- Candidate, finalization, checkpoint, fork and retired-owner paths are tested.
- Legacy pending payloads and science-off runs remain unchanged.
- Update only the matching `index.md` task checkboxes.
