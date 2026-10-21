# Phase 3: Grounded acquisition and occupant provenance

Plan: [index.md](index.md)
Tasks: 5–6
Depends on: Tasks 1–4

## Objective
Create content from an owner's evidence and acquire content through actual marks or deliveries, never through office succession, repository existence or shared state.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|---|---|---|
| `src/agents/cognition/offices.py` | `apply_office_concept_update`, `OfficeEvidence`, `OfficeConcept.occupants/succession` | Owner-local recognition and attributed role history. |
| `src/agents/cognition/institution_concepts.py` | `_observe_occurrences`, `_observe_memories`, `apply_institution_concept_update` | Recurrence evidence exists; memory/advice arguments do not already provide content uptake. |
| `src/agents/cognition/artifacts.py` | `apply_artifact_interpretation_update`, `ArtifactInterpretation` | Fallible readings retained by artifact revision, including old nonvisible readings. |
| `src/agents/cognition/teaching.py` | `record_teaching` (317), `_parse_act` | Existing advice handles closed skill-domain acts only. |
| `src/world/observations.py` | `ObservedOccurrence` (973), `ObservedCommunication` (1020), `ObservedArtifact` | Only one owner's redacted current evidence is valid input. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/agents/cognition/institutional_memory.py` | modify | Binding, evidence projection, update and acquisition receipt rules. |
| `src/agents/cognition/institutional_memory_frames.py` | modify | Source-specific parser helpers using the fixed frame. |
| `tests/unit/test_institutional_memory_updates.py` | create | Grounding, binding, ambiguity and local retention tests. |
| `tests/unit/test_institutional_memory_acquisition.py` | create | Physical/read/communication/teaching matrix. |

## Task 5: Ground channels and locally produced information

### Intent
Role labels and procedure familiarity must not conjure historical information. Produce only explicit, bounded claims supported by locally held evidence.

### Implementation Steps
1. Introduce `apply_institutional_memory_update(*, owner_id, observation, identity, previous=None, office_concepts=None, institution_concepts=None, artifact_interpretations=None, retrieved_memory_context=None, relationships=None, teaching_enabled=False, policy=None) -> InstitutionalMemoryLedger`. Validate one exact `Observation`, local ownership of supplied stores, and observer-to-owner identity mapping. `relationships` is only the owner's directed trust input to received-confidence calculation.
2. Create role channels only from locally recognized/vacant/disputed retained office concepts, using stable office ID/function/context. Create procedure channels only from local concepts with positive `procedure_recurrence` and retained `PROCEDURE_RECURRENCE` evidence; do not treat another institution strength or label as a procedure. Preserve disputed/uncertain associations as such, not authoritative roles.
3. Bind incoming role headers only to a unique local function/context match; procedure headers only to a unique retained local procedure anchor matching the context digest. Zero or multiple matches leave an unbound received entry. Never import sender office/concept IDs, or call analysis alignment at runtime. Reconsider existing unbound entries when local recognition later supplies a unique match, without adding content.
4. Produce new local fact candidates from explicit owner evidence: office duty claims `(role_token, duty, duty_kind_token)`, occupant claims `(role_token, occupant_claim, e_<24hex entity/agent digest>)`, succession kinds `(role_token, succession_claim, kind_token)`, and observed occurrence facts `(e_<24hex observed actor>, normalized_kind, e_<24hex observed other/destination>)`. Skip occurrence facts without actor/target instead of inventing unknown entities; represent success/failure only if explicitly present. Normalize overlength/non-token kind names to `k_<24hex>` and retain the local mapping with the source receipt, never derive behavior by reversing hashes.
5. Only attach an occurrence to a channel when its event reference/actor/context is present in that channel's locally retained office/institution evidence. No 'everything at this location belongs to this institution' fallback. Procedure evidence may produce `(procedure, observed_pattern, a_<anchor digest>)` claims; this records familiarity, not an executable recipe or hidden sequence.
6. Select up to three fact candidates per entry in deterministic source-tick/source-reference order. Keep distinct claim revisions and local source evidence. Do not synthesize completed trades, votes, teaching success or succession from a requested command. Explicit supported episode facts from `RetrievedMemoryContext.episode_facts` may reinforce/recall a previously known source, but ranked hits, access receipts and reference-only memories may not introduce content.
7. Repeated observation of the same source is idempotent. A new occurrence/revision can produce a new entry. After receipt-key eviction, a retained entry's native source key still deduplicates; re-exposure to fully pruned evidence is marked re-observed, not independent corroboration.

### Required Interfaces and Contracts
Owner-produced information is a fallible selection of the owner's evidence. Missing private history stays missing. A duty/occupant claim is not validated against world truth. Channels do not create social concepts or elevate their recognition strength merely by existing.

### Requirement Evidence
Original request — associated with long-lived roles/procedures, incomplete/wrong, provenance across occupants. Architecture — no scripted institutions, analysis feedback, or cross-owner knowledge.

### Error Handling and Logging
Reject foreign stores/authority objects before mutation. Skip unsupported evidence with safe reasons (`unbound`, `ambiguous_binding`, `no_content`, `unresolved_actor`). Count-only update logs; no label, anchor, fact or reference logging.

### Tests
Seed local recognized office/procedure fixtures through existing update APIs; test occupant replacement retains channel ID but adds no successor content, role-signature change does not reset channel identity, procedure ambiguity, evidence-qualified occurrence projection, reference-only recall exclusion, duplicate observations, pruned history and source-local revision retention.

### Acceptance Criteria
Every newly produced fact names an actual locally available source receipt; no local evidence means no entry, even when a role exists.

### Verification
`uv run --frozen --python 3.12.14 pytest tests/unit/test_institutional_memory_updates.py --cov=agents.cognition --cov-report=term -q`

## Task 6: Acquire records, procedural transmission and teaching

### Intent
Close the gap between physically available records, received public statements and actual owner-local uptake.

### Implementation Steps
1. For record acquisition intersect `observation.artifacts` with that owner's freshly prepared `ArtifactInterpretationLedger` by exact artifact ID and current observed revision. Decode `reading_marks`, not inspector snapshots, native event bodies or raw nonvisible record content. Retained old readings remain remembered information but never qualify as a new physical access.
2. No reading ledger/mode, no complete surviving fact, destroyed/hidden record, unrelated marks, or repository-without-visible-member-content → no record acquisition. Record author/root/integrity metadata is retained only when actually exposed; `marks_only` supplies no fabricated lineage. Damaged readings retain reduced confidence/distorted status; native physical damage and subjective omission are distinct.
3. Process only `ObservedCommunication` addressed to `observation.observer_id`, with a resolvable actual speaker and one recognized frame relation. `im_transmit` is procedural/public transmission. `im_teach` additionally requires receiver teaching mode on; missing teaching mode ignores this institutional teaching relation. The sender factory emits `im_teach` only when its own teaching mode is on. This is a new cognition-level teaching-content path, not an expansion of objective skill domains or `AdviceStore` contents.
4. Receipt identity combines actual delivery event/occurrence with frame ordinal, or current artifact/revision plus frame root. Multiple conflicting institutional frames in one utterance are not arbitrarily selected: skip institutional uptake and record ambiguity. Unrelated extra relations stay available to their existing consumers.
5. Receiver creates a fresh local entry with actual immediate source, channel, confidence and declared institutional root/parent; separately retain the received public envelope's declared transmission metadata. Frame root and native envelope communication root are different namespaces and need not match. Never fetch sender ledger by either root, copy support counts, resolve declared parents against peer state, or upgrade a statement to independent evidence through retelling.
6. Preserve wrong but valid claims and competing versions. Confidence defaults: local observation 0.7, clean record reading uses reading confidence, transmission/teaching 0.5; existing owner-directed trust may scale received confidence using `0.5 + 0.5*trust` with missing trust=0.5. Clamp/quantize to six decimals. No correctness appraisal via authoritative history. Do not treat teacher status or current office occupant as a truth multiplier.
7. Acquired information defaults active. Add pure owner-policy API `set_institutional_entry_ignored(ledger, entry_id, *, ignored: bool, tick)` returning a revised ledger; unknown entry fails code-only. Only that owner's decision policy may propose this through an `InstitutionalMemorySelection(kind=ignore, ignored=...)` in the normal `ActionPlan` → proposal → complete/result path specified in Phase 4, never an observer/admin side channel or immediate mutation in planning. Explicit local ignore state and bounded use policy exclude it from consultation/transmission without deleting source provenance. Damaging/destroying a record later does not erase an already learned entry, and does not leak its surviving hidden source content.

### Required Interfaces and Contracts
No changes to `world._teaching`, world skill effects, artifact perception, repository permissions, event schemas or scene-memory content. Teaching here transfers bounded claims through existing speech; it grants no objective skill/capability.

### Requirement Evidence
Index C5–C10. Existing `_project_artifact` visibility is the access boundary; repository custody checks are mutation/retrieval rules, not confidentiality.

### Error Handling and Logging
Malformed external payloads cause skip plus bounded reason counts. Ownership/type violations fail before any update. Logs distinguish `observed`, `acquired`, `partial`, `ignored`, `ambiguous`, but never payload, root, chain or fact digests.

### Tests
Visible/readable, artifact-mode off, stale interpretation, foreign-held, nonlocal, tombstone, partial frame, valid wrong frame, missing metadata, visible repository without member, founder-list denied retrieval with still-visible marks, addressed/unaddressed transmission, unknown speaker, enabled/disabled teaching, duplicate delivery, conflicting frame relations and competing claims. Assert teacher skill unchanged and receiver skill not copied.

### Acceptance Criteria
Successors gain information only at a specific observable record-reading or delivery receipt; accession alone does nothing. Unsupported/inaccessible sources cannot acquire content.

### Verification
`uv run --frozen --python 3.12.14 pytest tests/unit/test_institutional_memory_acquisition.py tests/unit/test_artifact_perception.py tests/unit/test_teaching_opportunities.py --cov=agents.cognition --cov=world --cov-report=term -q`

## Phase Risks and Mitigations
- Existing written practical-knowledge uptake accepts coarse cues. Mitigation: do not delegate institutional content acquisition to it; require current visible matching reading and full facts.
- Existing teaching accepts only skill-domain advice. Mitigation: use a separate bounded speech-frame consumer without altering objective skill semantics.

## Phase Completion Checklist
- Complete and verify Tasks 5–6; mark only index checkboxes.
