# Phase 2: Owner-Scoped Conflict Beliefs

Plan: [index.md](index.md)
Tasks: 4-10
Depends on: Phase 1

## Objective

Implement one owner's conflict coordination beliefs, the ordered update pipeline,
the bounded `ocf_v1` speech frame, cognition/runtime carry, and the deterministic
`Wait` replacement that compiles active plans into existing commands. No world
authority is added; every physical effect remains ordinary admission.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/agents/cognition/diplomacy.py` | policy 501-606; rows 848-1535; ledger 1876-2213; update 5424-5635 | Row, policy, ledger, digest, and update patterns |
| `src/agents/cognition/diplomacy_communication.py` | frame constants 84-95; `TreatyFrame` 378-498; encode/decode 509-629; chunking 632-704; trust 707-774; attach 788-844, 1063-1132 | Bounded speech-frame pattern; `ocf_v1` is simpler (one frame, no chunks) |
| `src/agents/cognition/models.py` | `SubjectiveSnapshot` 714-766, validation 991-993; `CognitiveLoopProposal` 3994, 4213-4219; `CognitiveLoopResult` 4330, 4535-4541 | Ledger fields and owner validation |
| `src/agents/cognition/loop.py` | `_prepare_diplomacy` 2979-3034; call 5127-5135; own-utterance recording 5869-5892; fork state 1538-1629 | Prepare/record/fork pattern |
| `src/simulation/agent_runtime.py` | `_commit_diplomacy` 1496-1528; snapshot assembly 2431; finalize 2940-2943; checkpoint export 3669; restore 3544 | Runtime carry and commit pattern |
| `src/simulation/run_control.py` | checkpoint validation 821-827 | Owner validation for carried ledgers |
| `src/agents/cognition/territorial.py` | `territorial_wait_replacement` 1221-1378 | The only existing `Wait` replacement pattern and its audit shape |
| `src/agents/cognition/deliberation.py` | replacement call 1156-1171; command compilation 2604-2758 | Exact insertion point after territorial defense |
| `src/world/observations.py` | `ObservedOccurrence` 972-1016; `Observation` 1301-1330 | Owner-visible inputs; no world state |
| `src/world/actions.py` | `Move` 52-59; `Take` 72-79; `Give` 92-102; `Help` 189-196; `Feed` 199-211; `Transport` 214-226; `Attack` 229-236; `Flee` 239-246; `OpposePublicGood` 847-858 | The only commands the screen may return |
| `src/simulation/runner.py` | `export_diplomacy_ledgers` 5609-5622; result assembly 5153 | Ledger export pattern |
| `src/simulation/runner_models.py` | `SimulationRunnerResult.diplomacy_ledgers` 6386, validation 6739-6755 | Result validation pattern |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/agents/cognition/organized_conflict.py` | modify | Rows, ledger, digest, update pipeline, caps, export |
| `src/agents/cognition/organized_conflict_communication.py` | create | `ocf_v1` encode/decode/trust/attach |
| `src/agents/cognition/organized_conflict_actions.py` | create | Deterministic `Wait` replacement and audit |
| `src/agents/cognition/__init__.py` | modify | Public facade exports |
| `src/agents/cognition/models.py` | modify | Snapshot/proposal/result fields and validation |
| `src/agents/cognition/loop.py` | modify | Prepare, record, fork state, replacement call |
| `src/agents/cognition/deliberation.py` | modify | Apply replacement after territorial and before communication decorators |
| `src/simulation/agent_runtime.py` | modify | Commit, snapshot, checkpoint, finalize |
| `src/simulation/run_control.py` | modify | Checkpoint field and validation |
| `src/simulation/runner.py` | modify | Export ledgers and assemble result |
| `src/simulation/runner_models.py` | modify | Result ledger field and validation |
| `tests/unit/test_organized_conflict_ledger.py` | create | Rows, digest, IDs, caps |
| `tests/unit/test_organized_conflict_update.py` | create | Pipeline and contradictions |
| `tests/unit/test_organized_conflict_communication.py` | create | Frame bounds and trust |
| `tests/unit/test_organized_conflict_actions.py` | create | Eight operation screens and non-`Wait` preservation |
| `tests/unit/test_organized_conflict_carry.py` | create | Snapshot/proposal/result/checkpoint carry |
| `tests/unit/test_organized_conflict_export.py` | create | Runner export and owner ordering |

## Task 4: Define conflict plans participations observations interpretations outcomes and contradictions

### Intent

Define the complete owner-scoped row vocabulary before any update logic. Every
row is immutable, bounded, and carries provenance. There is no global episode or
war row.

### Implementation Steps

1. In `src/agents/cognition/organized_conflict.py`, define frozen dataclasses:
   - `ConflictEpisode`: `episode_id`, `start_tick`, `end_tick`, `participant_refs`,
     `opponent_refs`, `event_classes`, `interpretation_ids`, `provenance`,
     `last_tick`.
   - `ConflictPlan`: `plan_id`, `operation`, `target_kind`, `target_ref`, `role`,
     `side_ref`, `participant_refs`, `opponent_refs`, `coordinator_ref`,
     `start_tick`, `end_tick`, `status`, `provenance`, `evidence_refs`,
     `revision`, `last_tick`.
   - `ConflictParticipation`: `participation_id`, `plan_id`, `participant_ref`,
     `role`, `stance`, `provenance`, `tick`, `active`, `evidence_refs`.
   - `ConflictObservation`: `observation_id`, `event_class`, `actor_ref`,
     `other_ref`, `tick`, `source_event_token`, `success`, `magnitude`,
     `provenance`.
   - `ConflictInterpretation`: `interpretation_id`, `episode_ref`, `kind`,
     `basis`, `confidence_band`, `tick`, `evidence_refs`.
   - `ConflictOutcome`: `outcome_id`, `plan_id`, `kind`, `target_ref`, `tick`,
     `magnitude`.
   - `ConflictContradiction`: `contradiction_id`, `member_ids`, `kind`, `tick`,
     `status` fixed `"unresolved"`.
   - `ConflictTermination`: `termination_id`, `plan_id`, `kind`, `tick`.
   - `ConflictActionAudit`: `owner_id`, `tick`, `plan_id`, `operation`, `role`,
     `reason_code`, `target_kind`; runtime metadata only, never published raw.
2. Enforce exact types in `__post_init__`; no `EntityId` requirement for peer
   refs (they are opaque tokens), but owner/self refs must match the ledger owner.
3. Define `ConflictObservationKind` closed enum:
   `attack`, `flee`, `help`, `feed`, `transport`, `take`, `give`, `move`,
   `journey`, `structure_opposition`, `contact`, `unknown`.
4. Define `ConflictBasis` closed enum: `self_declared`, `communicated`,
   `observed`, `remembered`, `inferred`, `record`.
5. Add `assert_conflict_no_forbidden_fields` calls in every `__post_init__`.
6. Add tests for required fields, bounded refs, and forbidden fields.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class ConflictPlan: ...
@dataclass(frozen=True, slots=True)
class ConflictParticipation: ...
@dataclass(frozen=True, slots=True)
class ConflictObservation: ...
@dataclass(frozen=True, slots=True)
class ConflictInterpretation: ...
@dataclass(frozen=True, slots=True)
class ConflictOutcome: ...
@dataclass(frozen=True, slots=True)
class ConflictContradiction: ...
@dataclass(frozen=True, slots=True)
class ConflictTermination: ...
```

Compatibility: rows use `str` opaque refs, not raw `EntityId`, except the ledger
owner. This keeps peer and target refs tokenizable for publication.

### Requirement Evidence

- Source: Original Request — plans, targets, roles, sides, interpretations,
  outcomes, contradictions, and terminations.
- Source: `src/agents/cognition/diplomacy.py` 848-1535 — row/provenance pattern.
- Supported combinations: a plan may have zero or more participations and
  outcomes; an interpretation may reference a local episode or `None`; a
  contradiction retains at least two member IDs; a termination references one
  plan.

### Error Handling and Logging

- `TypeError` names only the field, never the value.
- DEBUG `organized_conflict_rows_built plans=%s participations=%s
  observations=%s interpretations=%s`.
- Never log target refs or frame content.

### Tests

- `tests/unit/test_organized_conflict_ledger.py`
  - `test_rows_are_frozen_and_typed`
  - `test_contradiction_requires_two_members`
  - `test_forbidden_war_fields_are_rejected`
  - `test_opaque_refs_are_bounded`
- Command: `uv run pytest tests/unit/test_organized_conflict_ledger.py -q`

### Acceptance Criteria

- All eight ledger row families exist and are immutable; the runtime audit is a
  separate typed value.
- Every row validates its own bounds and rejects forbidden fields.
- No row claims objective group membership, war status, or authority.

### Verification

- `uv run pytest tests/unit/test_organized_conflict_ledger.py -q`
- Expected: all pass.

## Task 5: Add content-addressed ids ledger digest and canonical owner ledger

### Intent

Make every row stable and deduplicated, and make the whole owner ledger
digestible for carry, comparison, and publication provenance.

### Implementation Steps

1. Add ID functions in `organized_conflict.py`:
   - `conflict_episode_id(owner_id, start_tick, participant_refs, event_classes)`
   - `conflict_plan_id(owner_id, operation, target_kind, target_ref, start_tick,
     participant_refs)`
   - `conflict_participation_id(plan_id, participant_ref, stance, tick)`
   - `conflict_observation_id(owner_id, source_event_token, event_class, tick)`
   - `conflict_interpretation_id(owner_id, episode_ref, kind, tick, basis)`
   - `conflict_outcome_id(plan_id, kind, target_ref, tick)`
   - `conflict_contradiction_id(owner_id, kind, tick, member_ids)`
   - `conflict_termination_id(plan_id, kind, tick)`
2. All IDs use `conflict_record_id(prefix, *parts)` with canonical JSON
   (`sort_keys=True`, separators `(",", ":")`) and SHA-256. The first 16 hex
   characters are the suffix.
3. Define `ConflictLedger` frozen dataclass:
   - `owner_id: AgentId`
   - `tick: int`
   - `revision: int`
   - `policy_version: str`
   - `contract_version: str`
   - `episodes`, `plans`, `participations`, `observations`, `interpretations`,
     `outcomes`, `contradictions`, `terminations` tuples
   - `notices: tuple[str, ...]`
4. Validate:
   - owner is `AgentId`; tick/revision non-negative;
   - policy/contract versions exact;
   - every tuple sorted by primary ID;
   - no duplicate IDs;
   - every plan reference resolves to a plan;
   - every participation/interpretation/outcome/termination reference resolves;
   - contradiction member IDs resolve to a plan or interpretation;
   - caps are not exceeded (Task 10 enforces at update time; ledger rejects).
5. Add `empty_organized_conflict_ledger(owner_id, tick)` and
   `require_owner_conflict(ledger, owner_id, field_name=...)`.
6. Add `organized_conflict_ledger_digest(ledger)` using canonical JSON over all
   row families and `sha256`.
7. Add tests for stability, distinctness, ordering, foreign references, and
   digest sensitivity.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class ConflictLedger: ...
def empty_organized_conflict_ledger(owner_id: AgentId, *, tick: int) -> ConflictLedger: ...
def require_owner_conflict(ledger: object | None, owner_id: AgentId, *, field_name: str = "conflict") -> None: ...
def organized_conflict_ledger_digest(ledger: ConflictLedger) -> str: ...
```

Compatibility: the digest domain is `palimpsest.organized_conflict.ledger.v1`.
The ledger is not serialized into runner JSON or events.

### Requirement Evidence

- Source: `.ai-factory/ARCHITECTURE.md` Key Principle 2 — namespaced IDs and
  deterministic identity.
- Source: `src/agents/cognition/diplomacy.py` 1538-1834, 2248-2334 — ID/digest
  pattern.
- Supported combinations: identical inputs produce identical IDs; different
  owners produce different IDs; digest changes on any row or notice change.

### Error Handling and Logging

- Duplicate ID raises `ValueError("conflict_duplicate_id")`.
- Foreign reference raises `ValueError("conflict_foreign_reference")`.
- DEBUG `organized_conflict_ledger_digest plans=%s observations=%s digest_prefix=%s`
  using only a short digest prefix, never row content.

### Tests

- `tests/unit/test_organized_conflict_ledger.py`
  - `test_ids_are_stable_and_content_addressed`
  - `test_ledger_rejects_foreign_references`
  - `test_ledger_requires_sorted_unique_rows`
  - `test_digest_changes_with_any_row`
- Command: `uv run pytest tests/unit/test_organized_conflict_ledger.py -q`

### Acceptance Criteria

- Every ID is prefix + 16 lowercase hex and stable across runs.
- The ledger rejects duplicates, unordered rows, and foreign references.
- The digest is canonical and deterministic.

### Verification

- `uv run pytest tests/unit/test_organized_conflict_ledger.py -q`
- Expected: all pass.

## Task 6: Implement the ordered conflict update pipeline

### Intent

Turn owner-visible observations and speech claims into retained beliefs in a
fixed order, with no world read and no inference from silence.

### Implementation Steps

1. Add `apply_organized_conflict_update(*, owner_id, tick, observation, prior,
   representation, diplomacy, identity, relationships, policy)` in
   `organized_conflict.py`.
2. Validate owner, tick, prior owner, and `isinstance(observation, Observation)`.
   Reject any object whose module starts `world._`, `simulation.engine`,
   `persistence`, or `api`; reject `WorldState` and `WorldEvent` by type name.
3. Pipeline order:
   1. **Collect** owner-visible `ObservedOccurrence` rows into
      `ConflictObservation` for `attack`, `flee`, `help`, `feed`, `transport`,
      `take`, `give`, `move`, `journey`, `structure_opposition`, and `contact`.
   2. **Collect** `ocf_v1` frames from `observation.communications` and the
      owner's own selected command (Task 7).
   3. **Derive** plans from `propose`/`coordinate` frames and from repeated
      observed co-participation when no frame exists.
   4. **Derive** participations from `join`/`decline`/`withdraw` frames and from
      the owner's own roles.
   5. **Interpret** observed patterns into `ConflictInterpretation` rows
      (`individual_violence`, `coordinated_conflict`, `defense`, `retreat`,
      `assistance`, `resource_capture`, `route_blocking`, `structure_attack`,
      `unclear`). This is the owner's belief, not the analysis classification.
   6. **Derive** outcomes from observations linked to active plans.
   7. **Detect** contradictions (step 6 rules below) without reconciliation.
   8. **Expire** plans with `tick >= end_tick` or `tick - start_tick >
      policy.plan_ttl_ticks`; append `ConflictTermination(EXPIRED)`.
   9. **Enforce** limits (Task 10).
4. Plan derivation rules:
   - A `propose` frame names one operation, target kind/ref, role, side, window,
     and participant refs. The owner retains it as `proposed`.
   - A `join` frame for a known plan adds a participation with the claimed role;
     the owner does not gain authority over the other participant.
   - A `coordinate` frame updates target/window only for an existing plan and
     only if the speaker is the claimed coordinator or an active participant;
     otherwise retain a contradiction.
   - An observed sequence with at least two hostile events by the owner or
     visible others may create an `inferred` plan only when the owner is a
     participant; it never creates a plan for another owner alone.
5. Interpretation rules:
   - One attacker and one target with no shared co-participation and no
     recurrence -> `individual_violence`.
   - At least two actors on one side with repeated hostile events ->
     `coordinated_conflict`.
   - `help`/`feed`/`transport` after an attack -> `assistance` or `defense`.
   - `flee` with a threat -> `retreat`.
   - `take` from ground/corpse -> `resource_capture`.
   - `structure_opposition` -> `structure_attack`.
   - movement toward one destination by at least two participants ->
     `movement_group` (stored as `coordinated_conflict` with a movement basis).
   - No hostile event -> no conflict interpretation.
6. Contradiction rules:
   - Duplicate plan IDs with different content -> `duplicate_plan`.
   - Two plans naming the same owner in opposing sides -> `contradictory_plan`.
   - Two interpretations by the same owner of one episode with different kinds ->
     `contradictory_interpretation`.
   - Two `side_ref` values for one participant in one window ->
     `conflicting_side`.
   - Contradictions are `unresolved` forever.
7. Return a new ledger with incremented revision and sorted rows. Never mutate
   `prior`.

### Required Interfaces and Contracts

```python
def apply_organized_conflict_update(
    *,
    owner_id: AgentId,
    tick: int,
    observation: Observation,
    prior: ConflictLedger,
    representation: object | None,
    diplomacy: object | None,
    identity: OwnerSafeSocialIdentity | None,
    relationships: Sequence[object] | None,
    policy: OrganizedConflictPolicy,
) -> ConflictLedger: ...
```

Compatibility: `representation` and `diplomacy` are read-only owner ledgers used
only to resolve participant authority/standing; no peer ledger is read.

### Requirement Evidence

- Source: Original Request — plans, roles, targets, interpretations, and
  differing interpretations.
- Source: `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective
  concepts" — delivery proves speech only.
- Source: `src/agents/cognition/diplomacy.py` 5424-5518 — ordered pipeline.
- Supported combinations covered in the index table.

### Error Handling and Logging

- Unresolved target -> `notices=("unresolved_target",)` and no plan action.
- Malformed frame -> `notices=("malformed_frame",)` and drop.
- Unknown plan reference -> `notices=("unknown_plan",)` and drop.
- DEBUG `organized_conflict_update owner_token=%s plans=%s participations=%s
  observations=%s interpretations=%s contradictions=%s` (owner token, never raw
  agent id).
- WARN `organized_conflict_unresolved_target count=%s` and
  `organized_conflict_unknown_plan count=%s`.
- Never log frame body, target ref, or participant ref.

### Tests

- `tests/unit/test_organized_conflict_update.py`
  - `test_propose_join_and_coordinate_update_plan`
  - `test_observed_coordination_infers_owner_plan_only`
  - `test_opposing_interpretations_are_both_retained`
  - `test_contradictions_are_unresolved_and_never_reconciled`
  - `test_expiry_appends_termination`
  - `test_update_rejects_world_state_and_events`
- Command: `uv run pytest tests/unit/test_organized_conflict_update.py -q`

### Acceptance Criteria

- The pipeline is exactly the nine ordered steps.
- No plan is created for another owner without observed owner participation.
- Interpretations are owner beliefs and may differ.
- Contradictions are retained and unresolved.
- World state/event inputs are rejected.

### Verification

- `uv run pytest tests/unit/test_organized_conflict_update.py -q`
- Expected: all pass.

## Task 7: Add bounded ocf_v1 conflict speech frames

### Intent

Give agents a bounded, untrusted claim channel for plans and interpretations
inside existing speech, without a new command or event.

### Implementation Steps

1. Create `src/agents/cognition/organized_conflict_communication.py`.
2. Define `ConflictAct`: `propose`, `join`, `decline`, `withdraw`,
   `coordinate`, `report`, `interpret`, `conclude`, `unknown`.
3. Define `ConflictFrame` frozen dataclass with exactly 12 fields:
   1. `subject` = `ocf_v1`
   2. `act`
   3. `plan_ref` (`ocp-` + 16 hex or `none`)
   4. `episode_ref` (`oce-` + 16 hex or `none`)
   5. `operation`
   6. `target_kind`
   7. `target_ref` (opaque token or `none`; covers agent/group/location/route/
      resource/structure)
   8. `role`
   9. `side_ref` (opaque token or `none`)
   10. `window_start` (non-negative int or `none`)
   11. `window_end` (non-negative int or `none`)
   12. `participant_refs` (comma-separated 0-4 tokens or `none`)
   Durable-record anchors stay in the owner ledger, not in speech, so the frame
   fits the 256-character relation-object bound.
4. `encode_conflict_frame(frame) -> str` joins with `|`, enforces 256 chars,
   rejects `|`, whitespace, and control characters.
5. `parse_conflict_frame(text) -> ConflictFrame | None` enforces exact field
   count, subject, known act, closed enum constructors, tick order, ref caps, and
   returns `None` on malformed input.
6. Add the relation bridge used by existing speech:
   - `conflict_frame_relation(frame) -> CommunicationRelation` with
     `subject="ocf_v1"`, `predicate=frame.act.value`, and `object` equal to the
     remaining fields joined by `|`.
   - `parse_conflict_frame_relation(subject, predicate, object) -> ConflictFrame | None`
     reassembles `subject|predicate|object` and calls `parse_conflict_frame`;
     reject a non-`ocf_v1` subject or an object over the relation bound.
   - These helpers are the only mapping between `ConflictFrame` and
     `CommunicationRelation`; they never create a new command.
7. `conflict_frame_party_matches(frame, verified_speaker)` requires the frame's
   `side_ref` to equal `conflict_target_token(verified_speaker.value)` for every
   act. For `join`/`decline`/`withdraw`, `participant_refs` must contain exactly
   one token, and it must equal `side_ref`. A frame that attributes a claim to
   another party is dropped.
8. `conflict_frames_from_observation(observation)` scans
   `observation.communications`, verifies `speaker_id`, assigns
   `provenance=COMMUNICATED`, drops mismatches with a DEBUG count.
9. `conflict_frames_from_command(command, owner_id)` accepts only `Talk`, `Ask`,
   `Tell`; the frame's `side_ref`/participant must equal the owner; assigns
   `provenance=SELF_DECLARED`.
10. `conflict_communicate_utterance(command, frame, owner_id, tick)` attaches at
    most one `ocf_v1` relation to an already-selected `Talk`/`Ask`/`Tell`; the
    utterance text is the fixed subject `ocf_v1` (no free text), and all
    semantics live in the relation. Reject a second conflict relation, oversize
    text, missing speaker, or relation cap.
11. Tests for exact field count, max length, malformed input, speaker mismatch,
    duplicate relation, chunk-free behavior, and relation round-trip.

### Required Interfaces and Contracts

```python
CONFLICT_FRAME_VERSION: Final[str] = "ocf_v1"
CONFLICT_FRAME_MAX_CHARS: Final[int] = 256
CONFLICT_FRAME_FIELD_COUNT: Final[int] = 12

@dataclass(frozen=True, slots=True)
class ConflictFrame: ...
def encode_conflict_frame(frame: ConflictFrame) -> str: ...
def parse_conflict_frame(text: str) -> ConflictFrame | None: ...
def conflict_frame_relation(frame: ConflictFrame) -> CommunicationRelation: ...
def parse_conflict_frame_relation(subject: str, predicate: str, object: str) -> ConflictFrame | None: ...
def conflict_frames_from_observation(observation: Observation) -> tuple[ConflictFrame, ...]: ...
def conflict_frames_from_command(command: AgentCommand, owner_id: AgentId) -> tuple[ConflictFrame, ...]: ...
def conflict_communicate_utterance(command: AgentCommand, frame: ConflictFrame, *, owner_id: AgentId, tick: int) -> AgentCommand: ...
```

Compatibility: `ocf_v1` is a new speech subject inside existing speech, not a new
wire event or command. It never carries free text.

### Requirement Evidence

- Source: `src/agents/cognition/diplomacy_communication.py` 84-95, 215-303,
  509-629, 707-774 — bounded frame and trust pattern.
- Source: `src/world/communications.py` 50-137 — existing `Talk`/`Ask`/`Tell`
  relation limits.
- Supported combinations: valid frame, malformed frame, oversize frame, speaker
  mismatch, self command, duplicate relation.

### Error Handling and Logging

- `diplomacy_frame_too_large` analogue: `organized_conflict_frame_too_large`.
- DEBUG `organized_conflict_frame_dropped reason=malformed|speaker_mismatch|oversize
  count=%s`.
- Never log the frame text, target ref, or participant refs.

### Tests

- `tests/unit/test_organized_conflict_communication.py`
  - `test_frame_has_exactly_twelve_fields_and_256_char_bound`
  - `test_parse_rejects_wrong_count_and_control_chars`
  - `test_speaker_mismatch_is_dropped`
  - `test_attach_respects_relation_cap_and_duplicate_subject`
  - `test_frame_relation_round_trips_and_rejects_wrong_subject`
  - `test_own_command_requires_owner_side`
- Command: `uv run pytest tests/unit/test_organized_conflict_communication.py -q`

### Acceptance Criteria

- `ocf_v1` is 12 fields and at most 256 characters.
- Malformed, oversize, or speaker-mismatched frames never become beliefs.
- At most one conflict relation is attached to a speech command.
- No new command or event exists.

### Verification

- `uv run pytest tests/unit/test_organized_conflict_communication.py -q`
- Expected: all pass.

## Task 8: Wire conflict beliefs through cognition and runtime carry

### Intent

Make the ledger part of one owner's cognition snapshot, proposal, result,
runtime carry, checkpoint, and export, without changing runner JSON or event
wire formats.

### Implementation Steps

1. Add `organized_conflict: object | None = None` to `SubjectiveSnapshot`,
   `CognitiveLoopProposal`, and `CognitiveLoopResult` after `diplomacy`.
2. Add `organized_conflict_audits: tuple[object, ...] | None = None` to
   `CognitiveLoopResult` only. Validate that it is `None` or an ordered tuple of
   `ConflictActionAudit` values; reject sets, mappings, and foreign audit types.
3. Validate ledgers with `require_owner_conflict(...)` in each `__post_init__`.
4. In `CognitiveLoop`:
   - Add `_organized_conflict_mode`, `_organized_conflict_policy`,
     `_prepared_organized_conflict` slots.
   - Add `_prepare_organized_conflict(loop_input, representation, diplomacy,
     identity, relationships)` and call it after `_prepare_diplomacy`.
   - Pass `organized_conflict` into the proposal.
   - After command selection, call `record_organized_conflict_utterance` when
     the selected command carries an `ocf_v1` relation.
   - Include `prepared_organized_conflict` in fork-state export/restore.
5. In `AgentRuntime`:
   - Add `_organized_conflict` slot and initialize `None`.
   - Add `_commit_organized_conflict` mirroring `_commit_diplomacy`: disabled
     clears; deterministic type/owner checks; stores ledger; DEBUG counts.
   - Add `organized_conflict=self._organized_conflict` to snapshot assembly.
   - Call `_commit_organized_conflict` in `finalize_pending`.
   - Add `organized_conflict=self._organized_conflict` to checkpoint export and
     restore.
6. In `simulation/run_control.py`, add the field and owner validation.
7. In `SimulationRunner`, add `export_organized_conflict_ledgers()` iterating
   runtime checkpoints and returning owner-sorted non-`None` ledgers; add
   `organized_conflict_ledgers` to `SimulationRunnerResult` and validation.
8. Address deferred finalization explicitly: do not change the
   `FinalizationCommand` codec. If a pending finalization is rehydrated without
   the ledger, `_commit_organized_conflict(None)` leaves the prior carried ledger
   unchanged; the next tick rebuilds from that ledger and the next observation.
   Add a test documenting this recovery behavior; do not claim durable subjective
   restart.
9. Add tests for snapshot/proposal/result validation, the audit field, carry,
   checkpoint round-trip, export ordering, and the deferred-finalization recovery
   case.

### Required Interfaces and Contracts

```python
def require_owner_conflict(ledger: object | None, owner_id: AgentId, *, field_name: str = "conflict") -> None: ...
```

Compatibility: no runner JSON field, no event field, no checkpoint schema bump
that changes existing codec versions; the checkpoint dataclass gains one
optional field with a default. `CognitiveLoopResult` also carries
`organized_conflict_audits`; it is runtime metadata, not a runner or event field.

### Requirement Evidence

- Source: `src/agents/cognition/loop.py` 2979-3034 and 5869-5892 — prepare/record
  pattern.
- Source: `src/simulation/agent_runtime.py` 1496-1528, 2940-2943, 3669, 3544 —
  commit/carry/checkpoint pattern.
- Source: `src/simulation/runner.py` 5609-5622 and `runner_models.py` 6739-6755 —
  export/validation pattern.
- Supported combinations: enabled carry, disabled clear, owner mismatch error,
  checkpoint round-trip, rehydrated pending without ledger.

### Error Handling and Logging

- Owner mismatch -> `AgentRuntimeError(OWNERSHIP)`.
- Wrong type -> `TypeError("organized_conflict must be ConflictLedger")`.
- DEBUG `organized_conflict_ledger_carried plans=%s observations=%s tick=%s`.
- WARN `organized_conflict_pending_ledger_missing tick=%s` on rehydration; no
  participant or target refs.

### Tests

- `tests/unit/test_organized_conflict_carry.py`
  - `test_disabled_mode_allocates_nothing`
  - `test_snapshot_rejects_foreign_owner`
  - `test_checkpoint_round_trips_ledger`
  - `test_runner_exports_owner_sorted_ledgers`
  - `test_organized_conflict_audits_are_ordered_and_typed`
  - `test_rehydrated_pending_preserves_prior_ledger`
- Command: `uv run pytest tests/unit/test_organized_conflict_carry.py -q`

### Acceptance Criteria

- The ledger is carried only when the mode is deterministic.
- Owner validation is enforced at every boundary.
- Checkpoints and runner exports preserve owner order.
- No runner schema or event schema changes.

### Verification

- `uv run pytest tests/unit/test_organized_conflict_carry.py -q`
- Expected: all pass.

## Task 9: Compile active plans to existing commands on Wait

### Intent

Provide the actual low-level primitive: when an owner has no better selected
action and is committed to a plan, it performs one existing command for its role.
No new command type exists.

### Implementation Steps

1. Create `src/agents/cognition/organized_conflict_actions.py`.
2. Reuse `ConflictActionAudit` from `organized_conflict.py` (defined with the
   row vocabulary): `owner_id`, `tick`, `plan_id`, `operation`, `role`,
   `reason_code`, `target_kind`.
3. Implement
   `organized_conflict_wait_replacement(command, *, owner_id, tick, observation,
   identity, ledger, policy) -> tuple[AgentCommand, tuple[ConflictActionAudit, ...] | None]`.
4. Return immediately unchanged when:
   - the command is not exactly `Wait`;
   - the mode is disabled or the ledger is not `ConflictLedger`;
   - no active plan resolves to a visible target or coordination recipient.
5. Plan selection: filter `status in {proposed, joined, active}`, sort by
   `(start_tick, plan_id)`, choose the first whose role has a legal command and
   whose target resolves locally.
6. Target resolution from `Observation` only:
   - build a local map from every visible body, location, exit, item, resource,
     structure, and collective project to `conflict_target_token(value)`;
   - `agent`: visible body with matching token or `identity.counterparts`.
   - `group`: visible body set; choose the lexicographically smallest member.
   - `location`: visible location or exit destination.
   - `route`: visible exit destination.
   - `resource`: visible item or resource.
   - `structure`: visible structure or collective project.
   - `unknown`: no replacement.
7. Operation screens:
   - Before the physical screen, if the selected plan is `proposed` and a visible
     recipient exists, return `Tell(recipient_id, origin_utterance(...))` with an
     `ocf_v1` `propose`/`coordinate` relation. If the plan was received and has
     not been joined, return `Tell` with an `ocf_v1` `join` relation. Send at
     most one coordination `Tell` per plan per `plan_ttl_ticks`, using
     `plan.last_tick`; this is the only coordination-speech action and it uses
     existing `Tell`.
   - `coordinated_attack` -> `Attack(target_id)`.
   - `defense` -> `Help(ally)` if an attacked ally is visible; else
     `Attack(hostile)`; else `Move(ally_location)`.
   - `movement_group` -> `Move(destination_id)`.
   - `resource_capture` -> `Take(item_id)` for a visible ground/corpse item;
     else `Give(recipient_id, item_id)` only when the owner holds the item and
     the recipient is visible; otherwise unchanged.
   - `structure_attack` -> `OpposePublicGood(project_id)` only for a visible
     completed public-good project; else `Attack(occupant)`; otherwise
     unchanged.
   - `route_blocking` -> `Move(endpoint)`; if a hostile traveler is visible,
     `Attack`; if the owner is in danger and `Flee` is legal, `Flee`.
   - `retreat` -> `Flee(threat_id)` when a threat is visible; else unchanged.
   - `assistance` -> `Help(target)`, `Feed(target, item_id)` when an item is
     held, or `Transport(target, destination_id)` when the target is dependent
     and the destination is visible.
8. Emit exactly one audit for a replacement and `None` for no replacement.
9. In `deliberation.py`, call the replacement after
   `territorial_wait_replacement` and before `norm_communicate_utterance`; store
   the returned audits in `CognitiveLoopResult.organized_conflict_audits` and
   preserve them through the result construction.
10. Add tests for all eight operations, non-`Wait` preservation, missing target,
    illegal structure/project target, and deterministic plan order.

### Required Interfaces and Contracts

```python
def organized_conflict_wait_replacement(
    command: AgentCommand,
    *,
    owner_id: AgentId,
    tick: int,
    observation: Observation,
    identity: OwnerSafeSocialIdentity | None,
    ledger: object | None,
    policy: OrganizedConflictPolicy,
) -> tuple[AgentCommand, tuple[ConflictActionAudit, ...] | None]: ...
```

Compatibility: the screen returns only existing command types. It does not call
`WorldEngine`, submit an action, resolve an effect, or mutate the ledger.

### Requirement Evidence

- Source: Original Request — coordinated attack, defense, movement groups,
  resource capture, structure attack, route blocking, retreat, assistance.
- Source: `src/world/actions.py` 52-246, 830-858 — legal command types.
- Source: `src/agents/cognition/territorial.py` 1221-1378 — `Wait`-only
  replacement and audit pattern.
- Supported combinations: all eight operations; non-`Wait`; unresolved target;
  illegal structure; legal structure project.

### Error Handling and Logging

- DEBUG `organized_conflict_action owner_token=%s operation=%s role=%s
  reason_code=%s` — no target ref.
- WARN `organized_conflict_action_unresolved_target count=%s` and
  `organized_conflict_action_illegal_target count=%s`.
- Never log command payloads, target ids, or frame bodies.

### Tests

- `tests/unit/test_organized_conflict_actions.py`
  - `test_plan_coordination_uses_tell_with_ocf_v1`
  - `test_non_wait_command_is_never_replaced`
  - `test_coordinated_attack_returns_attack`
  - `test_defense_prefers_help_then_attack_then_move`
  - `test_movement_group_and_route_blocking_return_move`
  - `test_resource_capture_never_seizes_from_living_holder`
  - `test_structure_attack_requires_completed_public_good`
  - `test_retreat_returns_flee_and_assistance_returns_help`
  - `test_plan_order_is_deterministic`
  - `test_replacement_emits_exactly_one_audit`
  - `test_non_wait_emits_no_audit`
- Command: `uv run pytest tests/unit/test_organized_conflict_actions.py -q`

### Acceptance Criteria

- All eight operations can produce at least one legal existing command.
- Non-`Wait` selections are returned exactly unchanged.
- Resource capture never seizes from a living holder.
- Structure attack only uses `OpposePublicGood` on a completed public-good
  project.
- No new command type exists.

### Verification

- `uv run pytest tests/unit/test_organized_conflict_actions.py -q`
- Expected: all pass.

## Task 10: Enforce conflict caps notices and owner export

### Intent

Keep the ledger bounded and exportable without deleting active plans, accepted
participations, contradictions, or terminations.

### Implementation Steps

1. Add `_drop_oldest` and `enforce_organized_conflict_limits(ledger, policy)`.
2. Prune order:
   1. Observations older than `tick - plan_ttl_ticks`.
   2. Interpretations older than `tick - plan_ttl_ticks` with no active plan
      referencing their episode.
   3. Plans in `completed`/`abandoned`/`expired` older than `tick -
      plan_ttl_ticks`, plus their participations/outcomes; retain terminations.
   4. If still over a hard cap, raise `OrganizedConflictCapacityError` with a
      stable code.
3. Add notices: `organized_conflict_truncated:observations`,
   `:interpretations`, `:plans`.
4. Add `OrganizedConflictCapacityError` with code
   `organized_conflict_capacity_reached`.
5. Add `export_organized_conflict_ledger` returning a detached tuple of row
   families with opaque refs; used by runner export.
6. Add tests for each prune stage, hard-cap failure, deterministic ordering, and
   retained terminations/contradictions.

### Required Interfaces and Contracts

```python
class OrganizedConflictCapacityError(ValueError):
    code = "organized_conflict_capacity_reached"

def enforce_organized_conflict_limits(ledger: ConflictLedger, policy: OrganizedConflictPolicy) -> ConflictLedger: ...
def export_organized_conflict_ledger(ledger: ConflictLedger) -> ConflictLedger: ...
```

Compatibility: caps are private cognition policy, not runner configuration.

### Requirement Evidence

- Source: `src/agents/cognition/diplomacy.py` 3447-3865 — cap enforcement pattern.
- Source: `src/agents/cognition/delegation_representation.py` 1317-1465 —
  terminal-then-droppable pruning.
- Supported combinations: droppable observations, droppable interpretations,
  droppable terminal plans, nothing droppable.

### Error Handling and Logging

- WARN `organized_conflict_truncated family=%s count=%s`.
- ERROR `organized_conflict_capacity_reached plans=%s observations=%s`.
- Never log row references.

### Tests

- `tests/unit/test_organized_conflict_ledger.py`
  - `test_caps_prune_observations_first`
  - `test_caps_retain_active_plans_and_terminations`
  - `test_hard_cap_fails_closed`
  - `test_export_is_detached_and_sorted`
- Command: `uv run pytest tests/unit/test_organized_conflict_ledger.py -q`

### Acceptance Criteria

- Active plans, active participations, contradictions, and terminations are
  retained.
- Only observations, old interpretations, and terminal plans are droppable.
- Hard-cap overflow fails closed.
- Export is deterministic and owner-scoped.

### Verification

- `uv run pytest tests/unit/test_organized_conflict_ledger.py -q`
- Expected: all pass.

## Phase Risks and Mitigations

- Risk: the `Wait` replacement becomes a hidden command authority.
  Mitigation: it is a pure function, returns only existing commands, never
  submits, and is tested to leave non-`Wait` commands untouched.
- Risk: `ocf_v1` grows free text or unbounded refs.
  Mitigation: exact 12 fields, 256 chars, no whitespace/control chars, max 4
  participant refs, and a test for every bound.
- Risk: the update pipeline reads world state or committed events.
  Mitigation: type/name rejection tests and an architecture AST check.
- Risk: caps silently delete active plans.
  Mitigation: explicit prune order and fail-closed hard cap.
- Risk: deferred finalization loses a tick's update.
  Mitigation: documented recovery from the carried ledger; no durable subjective
  restart claim.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
