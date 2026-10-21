# Phase 1: Owner-local information and carrier contracts

Plan: [index.md](index.md)
Tasks: 1–2
Depends on: none

## Objective
Define bounded, fallible information associated with a locally recognized role or procedure, and a public encoding that fits existing physical and speech carriers.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|---|---|---|
| `src/agents/cognition/offices.py` | `office_concept_id`, `OfficeConcept` (778), `office_role_signature` | Stable local office identity is separate from occupant and revision-sensitive signature. |
| `src/agents/cognition/institution_concepts.py` | `InstitutionConcept` (395), `InstitutionConceptEvidence` | Procedure recurrence exists, but no procedure-content store exists. Concept IDs are derived from anchors, not guaranteed stable procedure identities. |
| `src/world/artifacts.py` | `ArtifactContent`, `MAX_ARTIFACT_MARKS=16`, `MAX_ARTIFACT_RELATIONS=8` | Physical marks accept only `[a-z][a-z0-9_]{0,31}` tokens. |
| `src/world/communications.py` | `CommunicationContent`, `CommunicationRelation`, `DeclaredTransmission` | Bounded public speech; declared lineage is testimony. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/agents/cognition/institutional_memory.py` | create | Immutable local contracts, policy, owner validators and stable IDs. |
| `src/agents/cognition/institutional_memory_frames.py` | create | Versioned bounded mark/speech frame codec; no world semantics. |
| `src/agents/cognition/__init__.py` | modify | Deliberate public exports only. |
| `tests/unit/test_institutional_memory_contracts.py` | create | Contract, bounds, identity and ownership cases. |
| `tests/unit/test_institutional_memory_frames.py` | create | Codec known answers and malformed/truncated cases. |

## Task 1: Define owner-local channels, entries and provenance

### Intent
Separate physical survival, personal learning, role association, and retrospective alignment. There is no institution-owned mind or shared content store.

### Implementation Steps
1. Introduce frozen/slotted `InstitutionalMemoryPolicy`, `InstitutionalMemoryLedger`, `InstitutionalChannel`, `InstitutionalMemoryEntry`, `InstitutionalFact`, `InstitutionalProvenance`, `InstitutionalOccupantClaim`, `InstitutionalMemorySelection`, and `InstitutionalMemoryUse` in the new module. Lock policy version `institutional-memory.v1`; expose `default_institutional_memory_policy()`, `empty_institutional_memory_ledger(owner_id)`, and `require_owner_institutional_memory(ledger, owner_id, *, field_name)`.
2. A channel has `owner_id`, stable `channel_id`, `binding_kind` (`role` or `procedure`), inception reference, current local reference, public function token, context digest, first/last tick, revision count, and at most 16 retained occupant claims. Each occupant claim retains attributed actor, observed/claimed start/end ticks, source evidence reference and status; absent end/occupant is unknown, not verified vacancy. Copy only this owner's explicitly held role claims into these records. Role references are the owner's `OfficeConcept.office_id`; they never change on occupant replacement. Procedure channels mint an inception identity on first qualifying local concept, then retain it on uniquely overlapping local anchors. Ambiguous/no overlap creates no automatic merge; retain separate channels and an ambiguity notice.
3. An entry has owner/local entry ID, channel ID or `None` (unbound received information), revision, 1–3 ordered facts, declared fact count, acquisition tick, confidence, distorted/partial flags, active/ignored state, provenance, and superseded-entry reference. An entry is not a `Belief` or executable permission. Conflict preserves competing entries; no last-writer truth election.
4. Provenance retains immediate channel (`observation`, `record`, `transmission`, `teaching`, `recall`), actual observed speaker/author entity when available, resolved source agent only through the owner's identity bindings, opaque event/occurrence reference, artifact ID/revision/native parent/root when observed, declared frame root/parent, and optional local predecessor entry reference. Retain received public `DeclaredTransmission` metadata separately from institutional frame roots; no prior message body is stored merely to reconstruct an envelope. Both kinds of declared lineage remain testimony, not native delivery facts. Unknown stays `None`. Local predecessor/supersession references have `retained`, `pruned` or `unresolved` state: validate existence only for retained references, and mark them pruned when deterministic eviction removes their target. Do not drop provenance simply to avoid dangling-reference errors.
5. Stable local IDs use SHA-256 over explicit owner/inception material, never label, occupant, Python `hash`, clock time or UUID. Wire roots use `r_` plus 24 hex digits and parents `p_` plus 24 hex digits or `p_none`; local full IDs are not replaced by truncated wire IDs. Conflicting short references remain ambiguous, never silently equated.
6. Policy caps: 32 channels, 128 entries, 32 uses, 16 retained provenance references per entry, and 256 recent acquisition receipt keys. On cap pressure deterministically evict oldest `(acquisition_tick, entry_id)` entries/oldest receipt keys; count pruning and mark coverage partial. Never evict a channel still referenced by a retained entry. If no channel slot can be reclaimed, keep received entry unbound. Validate exact types, finite unit confidence, nonnegative integer counters (reject bool), unique IDs and local references.
7. `InstitutionalMemorySelection` is proposal metadata: `owner_id`, `entry_id`, `channel_id`, `tick`, `kind` (`consult`, `transmit`, `teach`, `record`, `ignore`), and `ignored: bool | None` (required only for `ignore`). Maximum one selection per decision. It refers to the supplied local ledger and contains no command, new facts or external lookup reference. `InstitutionalMemoryUse` additionally records invocation ID and effective disposition (`consulted`, `transmission_attempt`, `teaching_attempt`, `recording_attempt`, `ignored`, `unignored`, `superseded`); only loop completion produces these receipts. Claims that a carrier was created or somebody learned are not use dispositions.

### Required Interfaces and Contracts
- `InstitutionalFact(subject: str, predicate: str, object: str)` uses the existing artifact-token grammar; claims, not world facts. No built-in trade/archive/project/decision/succession institution-type enum.
- Ledger contains owner, channels, entries, uses, acquisition receipts, observation-window bounds and pruning counters. `None` means disabled; an empty typed ledger means enabled without acquired information.
- Local reference validation rejects foreign ledgers. Dependencies remain public `agents`, `world`, and cognition contracts; no `analysis`, engine, repository, `WorldEvent` or private world inputs.
- `repr` of facts, entries and ledgers exposes counts/modes only, not content tokens, roots or payload-derived digests.

### Requirement Evidence
- Original request: persistent channels; incomplete/wrong/ignored information; provenance across occupants.
- `.ai-factory/ARCHITECTURE.md` — Memory, testimony, and subjective concepts; deterministic identity; no social authority injection.

### Error Handling and Logging
Invalid explicit contracts raise code-only `TypeError`/`ValueError`. DEBUG logs contain owner ID, counts, channel enum and reason code; WARN once per update on pruning. Never log channel IDs derived from content, frame roots, context digests, facts, labels, memory text or whole exceptions.

### Tests
Test stable role association through occupant/duty revisions, procedure anchor ambiguity, owner mismatch, frozen values, duplicate IDs, dangling local links, bool-as-int, NaN, cap eviction, retained-channel protection, conflicting entries, separate frame/envelope lineage, selection type/owner/kind validation, ignored state and safe repr. Hypothesis covers deterministic identity and bounded pruning.

### Acceptance Criteria
A role can outlive occupants without the new occupant receiving any entry; the same public claim received by two owners creates two independent local entries.

### Verification
`uv run --frozen --python 3.12.14 pytest tests/unit/test_institutional_memory_contracts.py --cov=agents.cognition --cov-report=term -q`

Expected: contracts pass without network, PostgreSQL or Docker.

## Task 2: Define bounded physical and speech frames

### Intent
Information must actually fit, survive, degrade and travel inside existing carriers; no reference may remotely dereference a predecessor ledger.

### Implementation Steps
1. Introduce `InstitutionalMemoryFrame`, `encode_institutional_marks(frame)`, `decode_institutional_marks(marks)`, `institutional_frame_relation(frame, *, teaching=False)`, and `parse_institutional_frame_relation(relation)` in the frame module. Keep this vocabulary cognition-owned, not a new `world` schema field.
2. Fix mark layout: `im_v1`, binding kind, function token, `c_<16 hex context>`, declared root `r_<24 hex>`, declared parent `p_<24 hex>` or `p_none`, `n_1|n_2|n_3`, then 1–3 consecutive subject/predicate/object triples. Maximum 7+9=16 marks; do not copy body facts into artifact relations. Ordered repeated marks are permitted by existing `ArtifactContent`.
3. Decode only exact header grammar and complete surviving triples. A valid header with fewer triples than `n_*` yields partial information; trailing one/two body tokens never form a fact. No surviving full triple yields no acquired entry. Extra body triples, unknown version, invalid header, or out-of-range counts reject the frame. Token swaps producing valid different claims remain possible: syntactic validity is not truth.
4. Speech uses one `CommunicationRelation`: subject `im_v1`, predicate `im_transmit` or `im_teach`, object the remaining mark sequence joined with `|`. Enforce length ≤256 characters without truncation. Choose the largest whole-fact prefix that fits, preserve the original declared fact count and mark the receipt partial; if even one triple plus header does not fit, do not append a frame. Existing text and other relations are never parsed as a fallback.
5. Preserve institutional declared root on retransmission; frame parent points to the selected source entry's wire reference. When appending a frame, preserve the selected command's existing `StructuredUtterance.declared` exactly: it describes the whole utterance, including other channels' relations. Do not call `retell_utterance` on this envelope or rewrite it to match an institutional source. That helper rejects speakers already in its chain (`src/world/communications.py:395`), and a decorator cannot change the attribution of unrelated content. Ordinary planner origin/retell construction remains outside this decorator. Require the existing immediate source to equal the acting entity; otherwise withhold institutional decoration without fixing or laundering the envelope.
6. Outgoing frames serialize only the selected local entry, not a channel ledger, current occupant's private memories, or an analytical join. Unknown roots create a new explicitly declared root; no root is a lookup endpoint.

### Required Interfaces and Contracts
Codec returns typed decoded-frame/partial results or `None` for unrelated/invalid public material, not raw parser exceptions. Internal programmer misuse remains an exception. Content counts and order round-trip canonically; encoders enforce physical and communication limits separately.

### Requirement Evidence
- Original request — physical records/artifacts, procedural transmission/teaching, damage and wrong information.
- `src/world/artifacts.py` — physical token/cap constraints; `src/world/communications.py` — bounded atoms and declared provenance.

### Error Handling and Logging
Malformed external frames are skipped with bounded reason counts (`invalid_frame`, `partial_frame`, `frame_capacity`, `ambiguous_reference`); no raw token or relation logging. No exception string from public content reaches logs.

### Tests
Known-answer 1/2/3-fact mark frames; 16-mark maximum; every truncation point; duplicates; long but valid tokens; no header; invalid n/version; partial triples; valid wrong token swaps; full/partial/unencodable speech; unrelated frame predicates; preserved non-institutional relations and native envelope. Test a current-speaker origin, a legitimate existing retell, repeated A→B→A institutional claims, capacity exhaustion, and a mismatched immediate source. No decorator calls `retell_utterance`, invents a new independent institutional root or throws on a cyclic claim. Assert physical body loss cannot be reconstructed from unchanged relations or root references.

### Acceptance Criteria
A real `ArtifactContent` and `CommunicationContent` accept encoded frames without changing world contracts. Loss reduces available claims or prevents acquisition; it never restores a missing claim.

### Verification
`uv run --frozen --python 3.12.14 pytest tests/unit/test_institutional_memory_frames.py --cov=agents.cognition --cov-report=term -q`

Expected: deterministic known answers and all existing carrier bounds respected.

## Phase Risks and Mitigations
- A full local ID does not fit a physical token. Mitigation: native opaque references stay outside the bounded semantic header; short declared references never acquire lookup or identity authority.
- A frame can be syntactically intact but wrong. Mitigation: preserve it as attributed belief, never validate it against world history in cognition.

## Phase Completion Checklist
- Every task meets acceptance criteria and verification passes.
- Update progress only in `index.md` after verification.
