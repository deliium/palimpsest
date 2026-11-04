# Phase 2: Owner-Scoped Evidence Beliefs

Plan: [index.md](index.md)
Tasks: 4-9
Depends on: Phase 1 / Task 3

## Objective

Implement one owner's general evidence ledger: closed records for sources,
witness statements, interpretations, custody links, contradictions, and
evaluations; a bounded `ev_v1` speech frame; deterministic collection from
owner-visible observations, recall, agreements, and reputation; provenance and
custody beliefs; owner-relative evaluation; and full cognition/runtime carry.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/agents/cognition/legal_disputes.py` | `_apply_claim_frame` 2899-3018; `_apply_frame` 3021-3286; `enforce_dispute_limits` 2150-2419; `apply_dispute_update` 3542-3695; `record_dispute_utterance` 3698-3762 | Collection, truncation, and utterance-recording precedent |
| `src/agents/cognition/legal_dispute_communication.py` | `DISPUTE_FRAME_SUBJECT` 61; `DisputeAct` 75-88; predicates 90-106; `DisputeFrame` 314-454; encode/parse 457-619; attribution 622-629; attach 644-696 | Frame shapes, strict parsing, attribution, relation attachment |
| `src/agents/cognition/reputation.py` | `ReputationProfile` 320-377; `_trust_for_speaker` 846-858; `_apply_testimony` 861-977 | Owner-relative trust bands and testimony adoption |
| `src/agents/cognition/communication.py` | trust projection 88-109; receiver confidence 181-197; communicated trace 265-403 | Direct vs communicated confidence precedent |
| `src/world/communications.py` | `DeclaredTransmission` 222-313; `origin_utterance` 346-374; `retell_utterance` 377-420 | Root/lineage vocabulary |
| `src/memory/models.py` | `RecallSourceEvidence` 2376-2486; `ReconstructedMemory` 2657-2837 | Remembered-event and reconstruction anchors |
| `src/world/artifacts.py` | `RecordIntegrity` 110-117; `InformationArtifact` 314-527 | Integrity and custody beliefs |
| `src/world/repositories.py` | `KnowledgeRepository` 148-278 | Repository custodian anchor |
| `src/agents/cognition/structured_commitments.py` | `CommitmentInterpretation` 88-202 | Prior-agreement source |
| `src/social/relationships.py` | `RelationshipDimensionState` 247-302; `DirectedRelationshipProfile` 305-386 | Trust input |
| `src/agents/cognition/contracts.py` | `Perspective.disputes` 195 | Where the parallel `evidence` field goes |
| `src/agents/cognition/models.py` | `SubjectiveSnapshot.disputes` 763; owner check 969-975; proposal 3973; result 4299 | Carry pattern |
| `src/agents/cognition/loop.py` | `_prepare_disputes` 2547-2625; proposal 4709/5079; result 5443; utterance 5383-5401 | Preparation and attachment points |
| `src/agents/cognition/fork_state.py` | `prepared_disputes` 64; write 1482; restore 1530 | Fork carry |
| `src/simulation/agent_runtime.py` | `_disputes` 626; `_commit_disputes` 1400-1428; finalize 2825-2828; restore 3411-3419; export 3532 | Runtime commit and checkpoint |
| `src/simulation/run_control.py` | `AgentRuntimeCheckpoint.disputes` 618; owner validation 799-805 | Checkpoint contract |
| `src/simulation/runner.py` | checkpoint export 4591-4638; dispute export 5487-5500; result assembly 5061 | Result assembly |
| `src/simulation/runner_models.py` | `SimulationRunnerResult.dispute_ledgers` 6381; validation 6697-6709 | Ordered ledger validation |
| `src/simulation/perception.py` | `build_perspective` disputes 161, 373 | Perspective wiring |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/agents/cognition/evidence_testimony.py` | modify | Records, ledger, limits, update, collection, provenance, custody, evaluation, hooks |
| `src/agents/cognition/evidence_testimony_communication.py` | create | `ev_v1` frame, predicates, parser, attribution, attachment |
| `src/agents/cognition/contracts.py` | modify | `Perspective.evidence` |
| `src/agents/cognition/models.py` | modify | Snapshot, proposal, result fields and owner checks |
| `src/agents/cognition/loop.py` | modify | `_prepare_evidence`, proposal/result attachment, utterance recording |
| `src/agents/cognition/fork_state.py` | modify | `prepared_evidence` |
| `src/simulation/agent_runtime.py` | modify | `_evidence`, commit, finalize, restore, export |
| `src/simulation/run_control.py` | modify | Checkpoint field and owner validation |
| `src/simulation/perception.py` | modify | `evidence` parameter and perspective construction |
| `src/simulation/runner.py` | modify | Ledger export and result assembly |
| `src/simulation/runner_models.py` | modify | `evidence_ledgers` field and validation |
| `src/agents/cognition/__init__.py` | modify | Public facade exports for the evidence ledger and frames |
| `src/simulation/__init__.py` | modify | Public re-exports |
| `tests/unit/test_evidence_testimony_records.py` | create | Record/ledger invariants |
| `tests/unit/test_evidence_testimony_communication.py` | create | Frame bounds, parsing, attribution |
| `tests/unit/test_evidence_testimony_collection.py` | create | Source/testimony/item collection |
| `tests/unit/test_evidence_testimony_provenance.py` | create | Provenance and custody chains |
| `tests/unit/test_evidence_testimony_evaluation.py` | create | Trust bases, contradictions, hooks |
| `tests/unit/test_evidence_testimony_runtime.py` | create | Perspective, loop, checkpoint, result carry |
| `tests/unit/test_evidence_testimony_physical_distinction.py` | create | No admission effect |
| `tests/unit/evidence_testimony_helpers.py` | create | Synthetic ledgers/rows shared by later tests |

## Task 4: Define evidence records and ledger invariants

### Intent

Materialize the frozen vocabulary into immutable, content-addressed records and
one ordered owner ledger whose invariants prevent cross-owner, dangling,
duplicate, or truth-like state.

### Implementation Steps

1. In `src/agents/cognition/evidence_testimony.py`, add `_reject_forbidden_fields`
   (same shape as `legal_disputes.py` 363-397) and `_quantize_confidence(value)`
   returning `round(value / quantum) * quantum` with `[0.0, 1.0]` enforcement.
2. Add frozen slots records (all reject forbidden field names, validate owner
   and tick, and recompute their own id):
   - `EvidenceSource`: `source_id`, `owner_id`, `source_kind`, `reference_kind`,
     `reference_id`, `correlation_id: str | None`, `provenance`, `tick`,
     `actor_id: str | None`, `confidence`,
     `integrity: EvidenceIntegrityBelief`, `root_ref: str | None`, `ordinal: int`,
     `independently_evidenced: bool`.
   - `EvidenceWitnessStatement`: `testimony_id`, `owner_id`, `speaker_id`,
     `subject_token`, `channel`, `root_ref`, `independently_evidenced`,
     `confidence`, `provenance`, `tick`, `source_id: str | None`,
     `context_ref: str | None`, `ordinal: int`.
   - `EvidenceItem`: `item_id`, `owner_id`, `source_id: str | None`,
     `testimony_id: str | None`, `interpretation`, `subject_token`,
     `confidence`, `tick`, `status`, `provenance`, `contradiction_refs`,
     `context_ref: str | None`, `reason_code: str`, `ordinal: int`.
   - `EvidenceCustodyLink`: `custody_id`, `owner_id`, `source_id`, `link_index`,
     `role`, `subject_token`, `holder_token: str | None`,
     `custodian_token: str | None`, `location_token: str | None`, `tick`,
     `provenance`, `integrity`, `witnessed: bool`.
   - `EvidenceContradiction`: `contradiction_id`, `owner_id`, `first_ref`,
     `second_ref`, `kind`, `status`, `provenance`, `tick`, `context_ref:
     str | None`, `ordinal: int`.
   - `EvidenceEvaluation`: `evaluation_id`, `owner_id`, `item_id`,
     `bases: tuple[EvidenceTrustBasis, ...]`, `confidence`, `kind`, `tick`,
     `provenance`, `relationship_ref: str | None`, `reputation_ref: str | None`,
     `rule_ref: str | None`, `office_ref: str | None`,
     `institution_ref: str | None`, `ordinal: int`.
3. Record invariants:
   - `EvidenceSource`: `reference_kind is UNKNOWN` only when
     `provenance is UNKNOWN`; `recorded` provenance requires
     `source_kind in {WRITTEN_RECORD, ARTIFACT}`; `independent` is never true for
     communicated provenance; `correlation_id` is an opaque token used only for
     researcher-only alignment and is never dereferenced or treated as a
     `WorldEvent`.
   - `EvidenceWitnessStatement`: `channel is COMMUNICATED` requires a non-empty
     `root_ref` and `independently_evidenced is False`; `channel is DIRECT`
     requires `root_ref is None`; `speaker_id` must be non-empty and must not be
     the owner when `channel is COMMUNICATED` and `provenance is COMMUNICATED`
     only if the frame attributed it (the frame guard is Task 5).
   - `EvidenceItem`: exactly one of `source_id`/`testimony_id` is non-empty;
     `status is RETRACTED` implies a non-empty `reason_code`; contradiction refs
     are sorted and unique.
   - `EvidenceCustodyLink`: `role is HOLDER` requires `holder_token` and forbids
     `custodian_token`; `REPOSITORY_CUSTODIAN` requires `custodian_token`;
     `LOCATION` requires `location_token`; `OBSERVER` requires
     `witnessed is True`; `tick` is non-decreasing with `link_index`.
   - `EvidenceContradiction`: refs are distinct owner-local evidence ids
     (`evs-`/`evw-`/`evi-`/`evc-`); both belong to the ledger owner.
   - `EvidenceEvaluation`: `bases` is non-empty, sorted, and unique; `UNKNOWN`
     cannot be combined with another basis; `NONE` must be the only basis.
4. Add `EvidenceLedger` frozen slots with ordered tuples `sources`,
   `custody_links`, `testimony`, `items`, `contradictions`, `evaluations`,
   `notices` (max 16), `policy_version`, `observation_start_tick`,
   `observation_end_tick`, `observation_count`, and six `pruned_*` counters.
   Validate owner consistency, id uniqueness, sorted order, cross-references,
   contiguous custody indices per source, contradictions referencing existing
   rows, evaluations referencing existing items, and notice vocabulary.
5. Add `empty_evidence_ledger(owner_id, *, tick=0)`,
   `require_owner_evidence(ledger, owner_id)`, `evidence_ledger_digest(ledger)`,
   properties `enabled`, `has_content`, `coverage` (`"partial"` when any
   `pruned_*` is non-zero or a truncation notice exists), and
   `active_items`.
6. Add `enforce_evidence_limits(ledger) -> EvidenceLedger`:
   - per-table caps from `EvidencePolicy`;
   - total-record cap 640;
   - deterministic overflow drop order: evaluations → contradictions → custody
     links → items → testimony → sources, each sorted by id before truncation;
   - after dropping sources, drop dependent items/testimony/custody links and
     sanitize `contradiction_refs`;
   - increment the matching `pruned_*`, append `evidence_truncated`, and never
     silently drop. Preserve `coverage="partial"`.

### Required Interfaces and Contracts

- Every record and the ledger are immutable frozen slots; all sequences are
  tuples sorted by their stable id.
- Ids are content-addressed and recomputed on construction; mismatch raises
  `evidence_invalid_id`.
- No record carries `WorldEvent`, `WorldState`, a payload body, or free text
  other than bounded opaque tokens (`subject_token`, `reference_id`,
  `reason_code` ≤ 64 chars).
- `EvidenceLedger.policy_version` must equal
  `EVIDENCE_TESTIMONY_POLICY_VERSION`.

### Requirement Evidence

- Original Request "Track: source, provenance, chain of custody where
  applicable, confidence, agent interpretation, contradictions."
- `.ai-factory/ARCHITECTURE.md` "Key Principles" 1-2 and "Versioned Extension
  Contract" requirement 1.
- `src/agents/cognition/legal_disputes.py` 1750-2419 — ledger and truncation
  precedent.

### Error Handling and Logging

- All failures raise `EvidenceError` with one of the closed error codes.
- WARN `evidence_truncated owner_count=%s pruned=%s` with counts only.
- INFO `evidence_ledger_committed sources=%s testimony=%s items=%s
  contradictions=%s evaluations=%s coverage=%s` at most once per owner commit.
- Never log subject tokens, reference ids, custody tokens, witness ids, or
  confidence values.

### Tests

- Create `tests/unit/test_evidence_testimony_records.py`:
  - every record rejects a forbidden field and an owner mismatch;
  - id recomputation fails on a mutated id;
  - communicated testimony cannot be independently evidenced;
  - custody role/token combinations and link index ordering are enforced;
  - contradiction refs must be owner-local and distinct;
  - evaluation basis combinations are enforced;
  - limits truncate in the documented order and set `coverage="partial"`;
  - no truth-like field exists on any record (`dataclasses.fields` scan).
- Command: `uv run pytest tests/unit/test_evidence_testimony_records.py -q`.

### Acceptance Criteria

- A ledger can represent every requested source kind, provenance channel,
  interpretation, custody status, contradiction kind, and trust basis.
- All invariants fail closed with stable codes and no partial mutation.

### Verification

- `uv run pytest tests/unit/test_evidence_testimony_records.py -q`
- Expected: pass.

## Task 5: Add bounded ev_v1 evidence speech frames

### Intent

Let an owner assert, testify, cite a record, claim custody, interpret,
contradict, and retract through existing `Talk`/`Ask`/`Tell` speech, with strict
bounds and verified-speaker attribution.

### Implementation Steps

1. Create `src/agents/cognition/evidence_testimony_communication.py`:
   - `EVIDENCE_FRAME_SUBJECT = "ev_v1"`
   - `EVIDENCE_COMMUNICATION_POLICY_VERSION = "evidence-communication.v1"`
   - `EVIDENCE_FRAME_FIELD_COUNT = 17`, `EVIDENCE_FRAME_TOKEN_MAX = 128`,
     `EVIDENCE_FRAME_TERMS_MAX = 4`.
2. Add `EvidenceAct(StrEnum)`: `assert_source`, `testify`, `cite_record`,
   `claim_custody`, `interpret`, `contradict`, `retract`.
3. Add predicates: `ev_source`, `ev_testify`, `ev_record`, `ev_custody`,
   `ev_interpret`, `ev_contradict`, `ev_retract`.
4. Add `EvidenceFrame` frozen slots with exactly these fields: `act`,
   `subject_token`, `source_kind`, `reference_kind`, `reference_id`,
   `witness_id`, `testimony_channel`, `root_ref`, `confidence_band`,
   `interpretation`, `contradiction_kind`, `first_ref`, `second_ref`,
   `custody_role`, `counterparty_token`, `location_token`, `custodian_token`.
   `confidence_band` is closed `low`/`mid`/`high` mapped by
   `EVIDENCE_CONFIDENCE_BANDS = {"low": 0.25, "mid": 0.55, "high": 0.85}`.
5. Per-act required/forbidden fields (exact):
   - `assert_source`: subject_token, source_kind, reference_kind, reference_id,
     confidence_band; all custody/contradiction fields empty.
   - `cite_record`: same as `assert_source` with `source_kind=written_record`.
   - `testify`: subject_token, testimony_channel, confidence_band, witness_id;
     `root_ref` required only for `communicated`; `first_ref`/`second_ref`
     empty.
   - `claim_custody`: subject_token, custody_role, confidence_band,
     `reference_id` (source ref); exactly one of holder/location/custodian
     token according to role.
   - `interpret`: subject_token, interpretation, confidence_band,
     `reference_id` (source/testimony ref).
   - `contradict`: subject_token, contradiction_kind, first_ref, second_ref,
     confidence_band.
   - `retract`: subject_token, `reference_id` (item ref), confidence_band.
6. Add `encode_evidence_frame(frame) -> str` (canonical JSON, sorted keys,
   compact separators, `allow_nan=False`, no unknown fields) and
   `parse_evidence_frame(text) -> EvidenceFrame | None` returning `None` for any
   malformed shape, length, token, enum, or field-count violation.
7. Add `evidence_frame_relation(frame) -> str` and
   `parse_evidence_frame_relation(relation) -> EvidenceFrame | None`.
8. Add `evidence_frame_party_matches(frame, verified_speaker) -> bool`: the
   `witness_id`, when present, must equal the verified speaker; an absent
   witness id is allowed only for non-testimony acts.
9. Add `evidence_communicate_utterance(command, frame, *, max_relations=32)`:
   attach at most one `ev_v1` relation; refuse a foreign actor, an invalid
   frame, or a relation-limit overflow by returning the original command
   unchanged; never change command type or recipient.

### Required Interfaces and Contracts

- The frame carries no free text, no claim body, no record content, and no
  objective event body.
- A communicated testimony frame always carries `root_ref`; a direct frame never
  does.
- `parse_evidence_frame` is total: it never raises for attacker-controlled
  speech; malformed input returns `None`.
- The frame max is `EvidencePolicy.max_frame_chars` (768).

### Requirement Evidence

- Original Request "Witnesses may misremember", "Records may be wrong",
  "Artifacts may be misinterpreted".
- `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts".
- `src/agents/cognition/legal_dispute_communication.py` 61-696 — bounded frame
  and attribution precedent.

### Error Handling and Logging

- Malformed frames are ignored with DEBUG `evidence_frame_rejected reason=%s`
  using only a closed reason token.
- WARN when a frame is rejected for a foreign witness:
  `evidence_frame_foreign_witness` (no ids).
- Never log the encoded frame or any token value.

### Tests

- Create `tests/unit/test_evidence_testimony_communication.py`:
  - every act round-trips through encode/parse;
  - each missing required field returns `None`;
  - direct testimony with a root, communicated without a root, or communicated
    marked independent all return `None`;
  - foreign witness id is rejected by `evidence_frame_party_matches` and by
    attachment;
  - a 769-character frame is rejected;
  - a command at 32 relations is returned unchanged;
  - the frame contains exactly 17 fields.
- Command: `uv run pytest tests/unit/test_evidence_testimony_communication.py -q`.

### Acceptance Criteria

- No new command, event, or communication type is added; frames travel as one
  existing speech relation.
- Every malformed or foreign frame is refused without mutating the command.

### Verification

- `uv run pytest tests/unit/test_evidence_testimony_communication.py -q`
- Expected: pass.

## Task 6: Collect sources, testimony, and interpretations

### Intent

Turn owner-visible inputs into evidence rows deterministically, with no world
reads and no peer-ledger reads. The owner's own observation, recall,
commitments, and reputation provide the inputs; the loop builds bounded DTOs.

### Implementation Steps

1. Add input DTOs to `evidence_testimony.py`:
   - `EvidenceObservedReference(reference_kind, reference_id,
     correlation_id: str | None, tick, actor_id: str | None, integrity,
     holder_token: str | None, custodian_token: str | None,
     location_token: str | None)`.
   - `EvidenceRememberedReference(memory_id, source_event_id: str | None, tick,
     confidence, reconstruction_id: str | None)`; `memory_id` becomes the source
     `reference_id` and `source_event_id` becomes the opaque `correlation_id`.
   - `EvidencePriorAgreement(local_ref, parties, kind, tick, confidence)`.
   - `EvidenceReputationInput(target_token, band, confidence)`.
   - `EvidenceOwnerContext(relationship_trust: tuple[tuple[str, float], ...],
     reputation_bands: tuple[tuple[str, str], ...],
     governing_rule_ids: tuple[str, ...], office_refs: tuple[str, ...],
     institution_refs: tuple[str, ...])`.
2. Add `apply_evidence_update(ledger, *, owner_id, tick, frames=(),
   observed=(), remembered=(), prior_agreements=(), reputation=()) ->
   EvidenceLedger`. The signature must not accept `Observation`, `WorldState`,
   `WorldEvent`, an event store, a repository, another owner's ledger, or a
   command.
3. Apply frames in a fixed act order: `assert_source`, `cite_record`,
   `testify`, `claim_custody`, `interpret`, `contradict`, `retract`. Reject
   frames whose `tick` is not the update tick or whose witness is not the
   verified actor.
4. Collect non-speech inputs:
   - `observed` → `EvidenceSource` with `provenance=direct_observation`,
     `source_kind` mapped by reference kind (`artifact`→artifact,
     `durable_record`→written_record, `observed_occurrence`→physical_state,
     `observed_communication`→witness_testimony, `repository_entry`→written_record,
     otherwise `unknown`); carry `reference_id` (the owner-visible anchor) and
     `correlation_id` (the opaque event token) separately.
   - `remembered` → `EvidenceSource` with `provenance=remembered`,
     `source_kind=remembered_event`, `reference_kind=memory_trace` or
     `reconstructed_memory`, `reference_id=memory_id`, and
     `correlation_id=source_event_id` when present; never dereference the
     correlation token.
   - `prior_agreements` → `EvidenceSource` with `source_kind=prior_agreement`,
     `reference_kind=commitment`, `provenance=remembered`.
   - `reputation` → `EvidenceSource` with `source_kind=reputation`,
     `reference_kind=reputation_record`, `provenance=inferred`.
5. Resolve `interpret`, `contradict`, and `retract` only against existing
   owner-local rows; an unknown reference adds `evidence_reference_unknown` and
   leaves the ledger otherwise unchanged.
6. Normalize confidence from the frame band and from DTO confidence, then call
   `enforce_evidence_limits`.
7. Add `evidence_source_from_observation` mapping helpers as pure functions so
   the loop can build DTOs without importing `world`.
8. Add `record_evidence_utterance(ledger, command, *, owner_id, tick)`:
   - read at most one `ev_v1` relation from the owner's selected command;
   - verify the actor is the owner and the frame party matches the actor;
   - apply the frame through `apply_evidence_update` with
     `frames=(frame,)` and return the updated ledger;
   - never mint, replace, or re-resolve a command.
   The loop parses at most one `ev_v1` relation from each owner-visible
   communication into a frame and passes `frames` to
   `apply_evidence_update`; the update never receives an `ObservedCommunication`
   or `Observation` object.

### Required Interfaces and Contracts

- `apply_evidence_update` is a pure function: same inputs produce an identical
  ledger and digest.
- The owner id in every input must equal `ledger.owner_id`; mismatch raises
  `evidence_owner_mismatch`.
- Callers pass only frames whose witness id equals the verified speaker (the
  loop performs `evidence_frame_party_matches` before the update). A testimony
  frame without a witness id is rejected.
- The only helper that accepts an `AgentCommand` is
  `record_evidence_utterance`, and it only reads at most one `ev_v1` relation
  from the owner's selected command and returns a ledger. No helper constructs,
  submits, replaces, or resolves a command.
- Communication-derived rows never copy an utterance body; only closed tokens
  and reference ids are stored.
- A source without a resolvable anchor stays `source_kind=unknown`,
  `reference_kind=unknown`, `provenance=derived`, with a notice.

### Requirement Evidence

- Original Request "Potential evidence sources" and "Evidence != truth".
- `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts".
- `src/agents/cognition/legal_disputes.py` 3542-3695 — owner-scoped update
  precedent.
- `src/memory/models.py` 2376-2486; `src/world/artifacts.py` 314-527.

### Error Handling and Logging

- Unknown references are durable notices, not exceptions.
- WARN `evidence_reference_unknown kind=%s` (enum name only).
- INFO `evidence_update_applied tick=%s sources=%s testimony=%s items=%s
  contradictions=%s` at most once per update; no ids.

### Tests

- Create `tests/unit/test_evidence_testimony_collection.py`:
  - each source kind is produced from its matching input DTO;
  - an observed artifact becomes a direct-observation artifact source;
  - an observed occurrence keeps `reference_id` and `correlation_id` distinct;
  - a remembered event retains a memory id plus the opaque event correlation;
  - a prior agreement references the owner's own commitment;
  - reputation uses the owner's band and never a shared score;
  - a foreign owner input raises `evidence_owner_mismatch`;
  - an unknown reference adds a notice and does not invent a row;
  - repeated application with identical inputs produces the same digest;
  - the update signature contains no world/event/peer type and no command
    construction (AST assertion).
- Command: `uv run pytest tests/unit/test_evidence_testimony_collection.py -q`.

### Acceptance Criteria

- Every requested source kind is reachable without reading objective history.
- No observation payload, utterance body, or peer ledger enters the model.

### Verification

- `uv run pytest tests/unit/test_evidence_testimony_collection.py -q`
- Expected: pass.

## Task 7: Derive provenance and chain-of-custody beliefs

### Intent

Make provenance explicit for every source and give artifact, written-record, and
physical-state sources an ordered custody belief chain, including gaps and
conflicts, without any objective audit claim.

### Implementation Steps

1. Add `EvidenceProvenanceSummary` frozen slots: `source_id`, `channel`,
   `root_ref`, `opaque_correlation_present`, `attributed_actor`,
   `independent_root`, `tick`.
2. Add `derive_provenance_summary(ledger, source_id) ->
   EvidenceProvenanceSummary` and `derive_all_provenance(ledger) ->
   tuple[EvidenceProvenanceSummary, ...]`.
3. Add `EvidenceCustodyChain` frozen slots: `source_id`, `status`,
   `links`, `first_tick`, `last_tick`, `gap_count`, `conflict_count`.
4. Add `build_custody_chain(ledger, source_id) -> EvidenceCustodyChain`:
   - `not_applicable` unless `source_kind in {artifact, written_record,
     physical_state}`;
   - sort links by `(link_index, tick, custody_id)`;
   - `complete_belief` when indices are contiguous from 0 and no gap exists;
   - `incomplete_belief` when an index or tick gap exists;
   - `conflicting_belief` when two links at the same tick disagree on
     holder/custodian/location;
   - `unknown` when no links exist.
5. Add `apply_custody_links(ledger, pending: Sequence[EvidenceCustodyLink])`
   that appends only validated, owner-matching links and re-derives the chain
   status. Custody links may also be created by `claim_custody` frames and by
   observed artifact/repository state.
6. Add `custody_gap_count` and `custody_conflict_count` ledger properties used
   by analysis.
7. Never compare custody beliefs with objective state here; that is Task 12.

### Required Interfaces and Contracts

- Chain of custody is per source, bounded by
  `max_custody_links_per_source=16`.
- Missing links are never synthesized; the status is explicit.
- `witnessed` records only that the owner believes the link was witnessed, not
  that a witness exists objectively.

### Requirement Evidence

- Original Request "chain of custody where applicable".
- `src/world/artifacts.py` 314-527; `src/world/repositories.py` 148-278.
- `.ai-factory/ARCHITECTURE.md` "Physical records/repositories preserve marks,
  custody, access, and lineage, never guaranteed meaning or truth."

### Error Handling and Logging

- Inconsistent link indices raise `evidence_chain_conflict`.
- WARN `evidence_chain_incomplete source_count=%s` (count only).
- DEBUG `evidence_chain_status status=%s link_count=%s` (no ids/tokens).

### Tests

- Create `tests/unit/test_evidence_testimony_provenance.py`:
  - a reputation source is `not_applicable`;
  - contiguous links are `complete_belief`;
  - a missing index is `incomplete_belief`;
  - two same-tick conflicting claims are `conflicting_belief` and both links
    are retained;
  - a chain with zero links is `unknown`;
  - provenance of communicated testimony references a root;
  - no objective state or event object is imported.
- Command: `uv run pytest tests/unit/test_evidence_testimony_provenance.py -q`.

### Acceptance Criteria

- Every source has a provenance summary; applicable sources have an explicit
  custody status.
- Conflicts and gaps are visible and never silently repaired.

### Verification

- `uv run pytest tests/unit/test_evidence_testimony_provenance.py -q`
- Expected: pass.

## Task 8: Evaluate evidence and retain contradictions

### Intent

Let each owner evaluate evidence using only the owner's own trust inputs, and
detect/retain contradictions without ever resolving them into truth.

### Implementation Steps

1. Add `EvidenceEvaluationPolicy` locked constants (already declared in Task 1):
   integer basis-point weights 5000/2500/2000/500, neutral confidence 0.5.
2. Add `evaluate_evidence(ledger, *, owner_id, tick, context:
   EvidenceOwnerContext) -> EvidenceLedger`:
   - for each `active` item without an evaluation at the current policy version,
     determine the counterparty token (the source `actor_id`, or the testimony
     `speaker_id`) and bases in this fixed order: `direct_experience` when the
     source provenance is `direct_observation`; `relationship_trust` when the
     counterparty token is in `context.relationship_trust`;
     `reputation` when the counterparty band is present; `role_authority` when
     the source `reference_kind` is `office_record` and `context.office_refs` is
     non-empty; `rule_authority` when `reference_kind` is `rule_record` and
     `context.governing_rule_ids` is non-empty; `institution_membership` when
     `reference_kind` is `institution_record` and `context.institution_refs` is
     non-empty; otherwise `none`.
   - compute confidence as the weighted normalized blend of the item confidence
     and the available trust values in basis points; when no real basis exists,
     use `neutral_confidence` and append `evidence_trust_basis_missing`.
   - classify `corroborated` when a second active item exists for the same
     subject with a distinct `root_ref` and a non-opposing interpretation;
     `contested` when an `unresolved`/`owner_prefers_*` contradiction references
     the item; `uncorroborated` when neither; `excluded_by_owner` when the item
     status is `retracted`; otherwise `unknown`.
   - record only the owner's own reference ids (`relationship_ref`,
     `reputation_ref`, `rule_ref`, `office_ref`, `institution_ref`); never read
     a peer ledger.
3. Add `detect_evidence_contradictions(ledger, *, owner_id, tick) ->
   EvidenceLedger`:
   - opposing interpretations for the same `subject_token` and same
     `reference_id` → `interpretation_conflict`;
   - two witness statements for the same subject with different roots and
     opposing interpretation items → `testimony_conflict`;
   - a written-record source and a remembered-event source for the same subject
     with opposing interpretations → `record_conflict`/`memory_conflict`;
   - same-tick custody links that disagree → `custody_conflict`;
   - a communicated root shared by two testimonies → `provenance_conflict`
     only when their interpretations oppose; otherwise append
     `evidence_testimony_root_shared`.
   - Default status `unresolved`; never auto-prefer.
4. Add `set_contradiction_preference(ledger, contradiction_id, status, *,
   owner_id)` accepting only `unresolved`, `owner_prefers_first`,
   `owner_prefers_second`, `withdrawn`; append a notice when the preference
   changes; never delete either side.
5. Add deliberation hooks (no commands):
   - `evidence_confidence_bias(ledger, subject_token) -> float` bounded
     `[-0.25, 0.25]`;
   - `evidence_contradiction_penalty(ledger, subject_token) -> float` bounded
     `[0.0, 0.5]`;
   - `evidence_case_summary(ledger) -> str` returning counts only.

### Required Interfaces and Contracts

- Evaluation is monotone in inputs and deterministic; repeated calls with the
  same tick/context produce the same ledger digest.
- `bases` never contains a basis for which no owner-local reference exists.
- Contradictions never encode a truth claim and never mark a side as false.
- No evaluation writes to memory, beliefs, relationships, reputation, rules, or
  world state.

### Requirement Evidence

- Original Request "confidence", "contradictions", "their own beliefs and trust
  models".
- `src/social/relationships.py` 176-302; `src/agents/cognition/reputation.py`
  320-459, 846-977.
- `src/agents/cognition/mediation.py` 599-682 — attributed account with
  contradiction refs and uncertainty.

### Error Handling and Logging

- Missing trust information is a notice, never an error.
- WARN `evidence_contradiction_retained kind=%s` (enum only).
- INFO `evidence_evaluated items=%s corroborated=%s contested=%s` (counts
  only).
- Never log confidence values, tokens, or reference ids.

### Tests

- Create `tests/unit/test_evidence_testimony_evaluation.py`:
  - direct observation yields `direct_experience`;
  - relationship trust and reputation produce bounded, deterministic weights;
  - missing trust yields `none` and neutral confidence plus a notice;
  - shared roots are not corroboration;
  - opposing interpretations create a retained contradiction;
  - preferring a side is explicit, reversible, and keeps both rows;
  - repeated evaluation is deterministic;
  - hooks return bounded values and never construct a command.
- Command: `uv run pytest tests/unit/test_evidence_testimony_evaluation.py -q`.

### Acceptance Criteria

- Evaluation depends only on the owner's own context and ledger.
- Contradictions remain visible and unresolved by default.

### Verification

- `uv run pytest tests/unit/test_evidence_testimony_evaluation.py -q`
- Expected: pass.

## Task 9: Carry the ledger through cognition and runtime

### Intent

Make the evidence ledger a first-class owner-scoped carried value through
perception, cognition, fork state, runtime finalization, checkpoints, and the
runner result, without exposing it to perception internals or admission.

### Implementation Steps

1. `src/agents/cognition/contracts.py`: add `evidence: object | None = None`
   after `disputes`; copy it in `Perspective.to_snapshot` next to disputes.
2. `src/agents/cognition/models.py`: add `evidence` to `SubjectiveSnapshot`,
   owner check beside 969-975, `CognitionLoopProposal.evidence`, and
   `CognitionLoopResult.evidence`.
3. `src/agents/cognition/loop.py`:
   - add `_prepare_evidence(tick, snapshot)` beside `_prepare_disputes`:
     when mode is `DETERMINISTIC`, require an `EvidenceLedger` of the same owner,
     build DTOs from the already-prepared observation/recall/commitments/
     reputation surfaces available to the loop, build `EvidenceOwnerContext`
     from `snapshot.relationships` (directed trust dimension values),
     `snapshot.reputation` (source-trust bands), `snapshot.formal_rules`
     (rule ids), `snapshot.office_concepts` (office ids), and
     `snapshot.institution_concepts` (institution ids) — never a peer ledger —
     call `apply_evidence_update`, `detect_evidence_contradictions`, and
     `evaluate_evidence`, cache the result; when disabled, return `None` and
     allocate nothing;
   - attach `prepared_evidence` to the proposal and final result;
   - record the owner's own `ev_v1` frame through
     `evidence_communicate_utterance` when the selected command carries one, then
     call `record_evidence_utterance` so the owner's declaration is retained in
     its own ledger.
4. `src/agents/cognition/fork_state.py`: add
   `prepared_evidence: object | None = None`, write it next to disputes (1482),
   restore it (1530), and reject foreign owners. Keep
   `COGNITIVE_LOOP_FORK_STATE_VERSION = "cognitive-loop-fork-state-v1"` unchanged;
   the new field is an additive default and must not bump the state version.
5. `src/simulation/agent_runtime.py`: add `_evidence`, `_commit_evidence`
   mirroring `_commit_disputes` (owner check, disabled gate), call it from
   `finalize_pending` beside disputes (2825-2828), validate on restore
   (3411-3419), and export in the checkpoint (3532).
6. `src/simulation/run_control.py`: add `AgentRuntimeCheckpoint.evidence`,
   ordered-sequence and owner validation beside disputes (799-805).
7. `src/simulation/perception.py`: add `evidence: object | None = None` to
   `build_perspective` and pass it through (161, 373). Perception must treat it
   as opaque and must not inspect rows.
8. `src/simulation/runner.py`: export `evidence_ledgers` in
   `export_runtime_checkpoint` and assemble them in the result (5061) beside
   disputes (5487-5500).
9. `src/simulation/runner_models.py`: add
   `evidence_ledgers: tuple[object, ...] = ()` and validate ordered sequence +
   `EvidenceLedger` items beside disputes (6381, 6697-6709).
10. `src/simulation/__init__.py`: re-export `EvidenceLedger`,
    `empty_evidence_ledger`, `require_owner_evidence`,
    `EVIDENCE_TESTIMONY_POLICY_VERSION`.
11. `src/agents/cognition/__init__.py`: add the evidence ledger and
    communication symbols to the public facade and `__all__`, mirroring the
    dispute exports at 574-611. No caller should need a deep import.

### Required Interfaces and Contracts

- The ledger is carried by reference to the same immutable value within one
  tick; no owner sees another owner's ledger.
- Disabled mode leaves every field `None`/`()`.
- Admission, perception projection, and world rules never read the ledger.
- `SimulationRunnerResult.evidence_ledgers` is an ordered tuple of
  `EvidenceLedger`.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime".
- `src/simulation/perception.py` 161/373; `src/simulation/runner_models.py`
  6381/6697-6709; `src/agents/cognition/loop.py` 2547-2625.

### Error Handling and Logging

- Foreign-owner carry raises `evidence_owner_mismatch` at validation.
- INFO `evidence_runtime_committed owners=%s ledgers=%s` (counts only).
- DEBUG `evidence_mode_disabled` once per loop build; never log ledger content.

### Tests

- Create `tests/unit/test_evidence_testimony_runtime.py`:
  - `Perspective(evidence=ledger).to_snapshot().evidence is ledger`;
  - a foreign-owner ledger is rejected at snapshot, checkpoint, and result;
  - disabled runner yields empty `evidence_ledgers`;
  - enabled runner yields one ledger per owner and survives checkpoint
    round-trip;
  - fork state preserves `prepared_evidence`;
  - ordering is stable across owners.
- Create `tests/unit/test_evidence_testimony_physical_distinction.py`:
  - a socially contested but physically possible command is admitted;
  - a physically impossible command is rejected by existing rules;
  - no evidence row changes admission.
- Commands:
  `uv run pytest tests/unit/test_evidence_testimony_runtime.py tests/unit/test_evidence_testimony_physical_distinction.py -q`

### Acceptance Criteria

- The ledger reaches analysis through the runner result.
- Perception, admission, and world rules remain unaware of evidence semantics.

### Verification

- `uv run pytest tests/unit/test_evidence_testimony_runtime.py tests/unit/test_evidence_testimony_physical_distinction.py tests/unit/test_v1_regression_gate.py -q`
- Expected: pass.

## Phase Risks and Mitigations

- Risk: the evidence model duplicates an existing domain evidence type.
  Mitigation: it references them by closed anchor kind and opaque id, and never
  imports or mutates them.
- Risk: hidden peer-ledger reads enter evaluation.
  Mitigation: evaluation receives only `EvidenceOwnerContext` DTOs; Task 20
  asserts the signature and import graph.
- Risk: custody beliefs are mistaken for objective audit.
  Mitigation: explicit `*_belief` statuses and Task 12 separation guard.
- Risk: runtime carry breaks existing checkpoint compatibility.
  Mitigation: additive fields with empty defaults; owner checks and round-trip
  tests.

## Phase Completion Checklist

- Every Task 4-9 in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
