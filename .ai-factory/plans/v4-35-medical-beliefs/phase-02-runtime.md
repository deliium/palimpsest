# Phase 2: Actions, testimony and recovery

Plan: [index.md](index.md)
Tasks: 3–4
Depends on: Phase 1

## Objective

Make beliefs drive ordinary authorized actions and social uptake while preserving staged and recoverable owner finalization.

## Current-Code Evidence

| Path | Symbols | Why it matters |
|---|---|---|
| `src/agents/cognition/loop.py` | `prepare`, `complete`, `run`, `bind_measurement`, `restore_measurement_ledger` | `complete` can replace a baseline `Wait` with a science/measurement command or add speech frames |
| `src/agents/cognition/replication_communication.py` | `ingest_replication_communication` | Real delivered listener evidence, self-send exclusion |
| `src/simulation/runner.py` | `_channel_loop_kwargs`, `_finalize_and_acknowledge`, `recover_pending_finalizations` | Shared construction and live/durable seams |
| `src/simulation/agent_runtime.py` | `bind_effective_command`, `finalize_pending`, `export_runtime_checkpoint`, `restore_runtime_checkpoint` | Effective-command overrides and owner checkpoint seam |
| `src/simulation/fork_checkpoint.py` | `fork_state_digest` | Explicitly hashes new owner sidecars only when present |
| `src/world/actions.py`, `src/world/_rules.py` | `Move`, `Sleep`, `Wait`, `Talk`; `_mutate_sleep` | Existing ordinary effects; no fictional cure provided |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/agents/cognition/{medical_beliefs_actions,medical_beliefs_communication}.py` | create | Closed action policy and one bounded testimony relation |
| `src/agents/cognition/{loop,contracts}.py` | modify | Candidate, intent and finalization plumbing |
| `src/simulation/{runner,agent_runtime,run_control,runner_serialization,persistence,fork_checkpoint}.py` | modify | Runtime binding, pending serialization and checkpoint round trip |
| `src/simulation/medical_beliefs_checkpoint.py` | create | Strict candidate codec |
| `tests/unit/test_medical_beliefs_{actions,communication,recovery}.py` | create | Command, delivery and crash checks |

## Task 3: Route interventions and testimony through ordinary commands

### Implementation Steps

1. Pair `contact` and `location` with `leave` by default, `food` and `weather` with `rest`, and `cultural` with `ritual_pause`. Derive evidence in `prepare`; select the medical command at the end of `complete`, immediately before `CognitiveLoopResult`, after existing science action selection and speech attachments. Preserve their priority and leave earlier plan/stage records as baseline evidence. Only a remaining `Wait` can become an intervention. For a living settled owner with the cue, choose the highest-scored active cause and highest practice score ≥2 for it, tie breaking `leave`, `rest`, `ritual_pause`; default if none crosses the practice threshold. `leave` compiles to `Move` to the first visible exit by destination ID (no substitution with no exit), `rest` to `Sleep`, and `ritual_pause` to `Wait` with a private intent marker. Skip retry of the attempted pair until at least three ticks have elapsed. Do not classify an unrelated `Wait` as a ritual or bypass ordinary admission or travel constraints.
2. For testimony, add a single reserved relation with predicate `mb_v1`, canonical subject `medical_beliefs`, and object `<cause>|<practice>|<outlook>|<root>|<hop>`. Outlook is `uncertain`, `tentatively_helped` or `not_obviously_helped`; root is a declared 32-character lowercase hex token, hop is an ASCII digit 0–4. Use existing structured utterance builders and relation capacity; a reserved duplicate or insufficient room leaves the command alone. Prefer the pair's first accepted relayable root (same root, hop + 1); otherwise use a locally observed belief's digest-derived root, hop 0. A hop-4 root cannot be relayed and no new root is minted from testimony alone. Outlook is the owner's latest interpretation for the pair, or `uncertain` when none exists. Never label the root verified.
3. When an ordinary addressed `Talk`/`Tell` exists, attach the strongest supported pair to it (same ordering as intervention; skip pairs with no relay anchor); otherwise on a remaining unmarked `Wait` synthesize ordinary belief-basis `Talk` only when `tick % 4 == 0` and an eligible visible living co-present peer exists, selecting the lowest ID. Deduplicate outgoing `(recipient, root, outlook)` proposals with timestamps for the prior eight ticks (at most one per tick). Receivers ingest only actual addressed `Talk`/`Tell` from `ObservedCommunication`, never a speaker's own or overheard copy; require one valid frame and retain actual delivery occurrence ref separately from declared root. Conflicting outlooks can be retained even when a repeated root contributes no new support. No automatic spread, cure, susceptibility change, or inferred peer diagnosis.
4. Pass a medical-override boolean from `AgentRuntime.bind_effective_command` based on whether its `effective_command` argument was supplied, not equality of command values. When overridden, omit both medical command changes and medical submission metadata but keep owner evidence ingestion. The direct `CognitiveLoop.run()` path is not an override even though it supplies a command to `complete`. Record a marked attempt or outbound proposal only from `require_agent_command(loop_result.command)` actually bound as the submission; confirm the marker matches exact command kind and destination or recipient/frame, respectively. Do not record a proposal as delivery. At next consecutive living owner observation after an attempt, record cue outcome and interpretation; gaps observed later close as unknown, and unobserved run-end attempts remain open. This explicitly permits mistaken credit after a denied attempt; only detached research verifies application separately.

### Contracts, errors and logging

Intervention stage is priority-preserving and only runs when gated; no market, science or communication-inference mode is required. Malformed frames are ignored, ordinary commands still run, and test fixtures must use representative public `Observation`/`StructuredUtterance` values. DEBUG mode/decision/rejection codes and counts only, never belief scores, roots, utterance or symptoms.

### Tests and verification

In `tests/unit/test_medical_beliefs_actions.py`, cover priority, deterministic exit selection/no exit, rest, marked/unmarked wait, cooldown and override (including equal replacement). In `tests/unit/test_medical_beliefs_communication.py`, cover actual delivery, rejection, nonrecipient and speaker exclusion, full relations, malformed/duplicate frames, same-root relay, conflict retention and cue-free receivers retaining and relaying a practice before later selecting it if they observe their own cue. Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_medical_beliefs_actions.py tests/unit/test_medical_beliefs_communication.py -q`. Acceptance: only existing commands leave cognition, and receipt-free claims cannot change another agent's ledger.

## Task 4: Persist candidates with the existing finalization protocol

### Implementation Steps

1. Pass the config gate through `_channel_loop_kwargs` on all founder, injected-runtime and mid-run construction paths. Bind an empty owner ledger on admission, never copy/traverse another owner's ledger. Carry the prepared immutable candidate through `complete`, then append only exact bound submission metadata. Do not install candidate state in `prepare` or `complete`.
2. Add a required `medical-beliefs-state-v1` canonical mapping in the new `finalization-command-v6`. Use the v5 document keyset plus exactly `medical_beliefs_state` (typed DTO field `medical_belief_ledger`); existing candidate keys nullable, subject to correlated experiment/replication state and competing-theory ⇒ scientific-model presence. With medical mode off, emit v1–v5 unchanged. Add v6 to pending storage/decoder allowlists. Compute its candidate digest with a fixed-order, domain-tagged encoding of all present candidates; use the same v6 integrity builder on write and restore. In `restore_pending_from_command`, verify the expected owner/policy/tick and recompute integrity before idempotency or `_pending` mutation; retain v1–v5 hash behavior.
3. Add a typed optional ledger to `AgentRuntimeCheckpoint`. Add only a conditional medical-state digest to `fork_state_digest`, matching its existing optional-sidecar pattern. Preflight gate, owner and policy identity before mutating any runtime checkpoint or invoking `finalize_pending`; keep the field in retained terminal checkpoints. Install the candidate through the same idempotent owner-finalization path as measurement.
4. Distinguish in-process/checkpoint restoration from pending recovery: a valid v6 pending command restores the full candidate for that owner/tick after the relevant objective commit; it is not a new durable store for all finalized subjective state or inactive owners. Never join `ActionResolution` in cognition, rerun cognition for a pending record, or promise restart of an owner whose required ledger was never checkpointed. Treat a missing required ledger in a supplied runtime/fork checkpoint as incompatible, not as empty.

### Contracts, errors and logging

Checkpoint codec rejects unknown keys, version/policy/owner mismatches and invalid ordering, limits or references. Abort uncommitted candidate state on objective failure; repeated acknowledgment is idempotent. Keep the ledger outside world snapshots, events and observer API. Log only DEBUG codec/activation/counts and safe existing recovery failure codes.

### Tests and verification

Use `tests/unit/test_medical_beliefs_recovery.py` with `test_measurement_recovery.py` and `test_runner_finalization.py` as precedents. Verify crash before commit, crash after commit, retries, owner mismatch, fork restore and combination with science, instruments and competing theories. Mutate a valid same-owner ledger while keeping the original pending/fork digest and require rejection before mutation. Compare committed owner bytes and objective history to uninterrupted twins; no duplicate action or outcome row. Test science/measurement winning the final `Wait` when both can act, and full relation capacity after earlier attachments. Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_medical_beliefs_recovery.py tests/unit/test_measurement_recovery.py tests/unit/test_runner_finalization.py -q`.

## Phase Risks and Mitigations

- Effective-command replacement could be misattributed: explicitly carry the override bit across binding.
- A recovery receipt may omit action status: report unknown in detached research rather than altering cognition or inventing success.

## Phase Completion Checklist

- Ordinary command and listener-only behavior passes.
- Pending and checkpoint tests pass with medical mode alone, off, and composed.
- Update only the verified tasks in `index.md`.
