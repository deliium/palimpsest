# Phase 2: Bounded social transport

Plan: [index.md](index.md)
Tasks: 5–8
Depends on: Tasks 1–4

## Objective

Share complete bounded designs, results, and participation declarations through actual delivery, preserving provenance and social disagreement.

## Current-Code Evidence

| Path | Symbols / behavior | Significance |
| --- | --- | --- |
| `src/agents/cognition/scientific_hypothesis_communication.py` | `attach_scientific_hypothesis_claim`, `parse_scientific_hypothesis_claim_relation`, `adopt_communicated_hypothesis` | Existing Talk/Tell-only, evidence-free testimony pattern. |
| `src/agents/cognition/loop.py` | `_ingest_scientific_hypotheses`, `_select_scientific_hypothesis` | Existing selector excludes adopted hypotheses; replication needs its own selector. |
| `src/agents/cognition/collective_decision_communication.py` | `ParsedCollectiveRelation` | Speaker is the observed delivery speaker, not a trusted payload claim. |
| `src/world/observations.py` | `ObservedCommunication` | Public verified speaker, listener, delivery event, and delivered utterance; sender also receives this projection. |
| `src/world/communications.py` | `CommunicationRelation.__post_init__`, `_MAX_CONCEPT_CHARS=256` | Object fields are bounded at 256, including every multipart header; a feature-local cap cannot widen this. |
| `tests/unit/test_scientific_hypotheses_communication.py` | attachment, cap, provisional adoption tests | Legacy `hyp_v1` bytes/behavior must remain valid. |

## Files to Change

Create `src/agents/cognition/replication_communication.py`, `replication_codec.py`, `tests/unit/test_replication_communication.py`, and `test_replication_social_exchange.py`; extend `src/agents/cognition/loop.py` in Phase 3 using the helpers defined here. Add intentional facade exports.

## Task 5: Specify and encode the `rep_v1` protocol

### Intent

Transmit enough procedure and result data to repeat work, not just an opaque hash a recipient cannot execute.

### Implementation Steps

1. Add typed wire documents for `design`, `result`, `invite`, `participate`, `decline`, and `interpret`. Use exact-key canonical JSON with compact, documented keys, sorted JSON keys, ASCII escapes, no floats/NaN, duplicate keys, or arbitrary extra fields.
2. All documents carry `v=1`, `kind`, `design` token and source root. Design documents additionally carry the complete Phase 1 design payload, not a remote lookup URL. Result documents carry immutable report identity, source trial, category, uncertainty, condition snapshot, optional collaboration token, and declared performer token. Invitation/participation/decline carry invitation and optional group claim. Interpretation carries referenced report, appraisal and reason codes, never hypothesis truth.
3. Introduce `encode_replication_message(document) -> tuple[CommunicationRelation, ...]`: subject `rep_v1`, predicate `part`, object `<message-token>:<zero-based-index>:<count>:<payload>`. Message token is the first 32 SHA-256 hex characters of canonical document bytes. At most eight parts (indices 0–7, count 1–8). The header is exactly 37 ASCII characters, so payload is at most 219 characters/part and the entire object at most the existing 256. Document maximum is 1,752 encoded bytes. Every nonfinal chunk is exactly 219 characters; the last is 1–219; count equals ceiling(length/219). Parse with a maximum of three separator splits. Construct actual `CommunicationRelation` objects in encoder tests, not mock tuples.
4. `decode_replication_message(relations)` assembles parts only within one delivered utterance, rejects missing/duplicate/out-of-order indices, mixed tokens/counts, digest mismatch, unknown fields, unknown enum values and oversize documents. Never maintain a cross-utterance reassembly cache.
5. An oversize design remains valid owner state but is not shareable: return `replication_message_oversize`; never truncate conditions, bindings, lineage, or uncertainty. Preserve the existing `hyp_v1` encoder, its feature-local 384-character check, and its one-relation shape unchanged; the shared world relation bound of 256 still applies to any constructed atom. Fixing that older feature-local discrepancy is not this task.

### Required Interfaces and Contracts

Exact document key sets (nullable keys are present with JSON null; do not omit them):

| Kind | Keys beyond common `v`, `kind`, `design`, `root` |
| --- | --- |
| `design` | `payload` |
| `result` | `report`, `attempt`, `source_trial`, `performer`, `measurement`, `conditions`, `collaboration` |
| `invite` | `invitation`, `group`, `source_trial` |
| `participate` | `invitation`, `group` |
| `decline` | `invitation`, `group`, `reason` |
| `interpret` | `report`, `appraisal`, `condition_comparison`, `source_appraisal`, `uncertainty_notice` |

`payload` uses the exact `ExperimentDesign` field names defined in Task 1; selectors use `family`, `kind`, `binding_mode`, `exact_entity_id`. Conditions are arrays of exact `{slot, value_token}` records, canonical slot order. `measurement` uses exact Task 2 fields: `outcome`, `resolution`, `uncertainty_kind`, `possible_outcomes`, `basis`. `design` must equal `payload.design_token`. Result `report` is the immutable origin report token, not a receiver-local handle. Decline reasons are `not_testable`, `source_contested`, `capacity`, `declined`; interpretation notice is `unreported`, `ambiguous_set`, or `none`. Other tokens are opaque bounded stable references; actual speaker/recipient/delivery always come from perception.

`root` is the declared evidence origin relevant to the message kind, preserved on re-delivery: for a design it is its founding source trial; for an invite/participate/decline it is the trial the invitation requests repeating; for a result it is that report's own measured trial, which may differ from the original source trial; for an interpretation it is the referenced report's origin. Result `source_trial` identifies the prior test being repeated (or the original trial itself for an original report); result `root` identifies this report's measurement. Thus two real replications of one source retain distinct result roots rather than being deduplicated as one source occurrence.

One replication document per utterance. Existing total relation cap remains 32. Complete delivery means speech delivery only, not source authenticity, experiment occurrence, or group endorsement. Protocol v1 is immutable; future widening requires a new wire version.

### Error Handling and Logging

Pure encoding errors use safe codes; parser returns no message with a bounded warning reason. Log size/count/kind codes only, never canonical body, digest, conditions, outcome content, or exceptions containing payloads.

### Tests / Acceptance / Verification

`test_replication_communication.py`: each kind round-trips, boundary sizes, multipart canonicality, forged IDs, unknown keys, invalid condition slots, booleans-as-counts, Unicode byte limits, partial delivery, duplicates, and all-or-nothing rejection. Run `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_replication_communication.py -q`.

## Task 6: Ingest delivered designs and reports without borrowed evidence

### Intent

Convert delivered testimony into receiver-local records while keeping independent trials distinct from repeated claims.

### Implementation Steps

1. Add `ingest_replication_communication(owner_id, ledger, observation, source_context)` that reads only `observation.communications`. Bind speaker/recipient/delivery event from the observed envelope, never wire-supplied sender identity. Ingest incoming content only when the observed listener matches the owner's body identity. An observed own-speaker message is a send receipt, not fresh incoming scientific testimony; other private observers must not adopt an invitation addressed to someone else.
2. Designs create receiver-local adoption receipts; results create communicated reports. A report can precede its design and stays unresolved until that exact design arrives. Do not fetch a private ledger or infer a missing design from matching `hyp_v1`.
3. Invitations refer to previously delivered/current complete designs; unknown-design invitations remain pending, not executable. Persist verified inviter identity and the invitation's source-trial reference at receipt. Participation records only the observed speaker's declaration. A wire claim that someone else participated remains a claim, never a roster entry.
4. Deduplicate by delivery ID for replay idempotence and by declared source-root/report identity for evidence multiplicity. A new result report from a distinct actual test may share a design without being deduplicated. Reused source identity with changed content is disputed, not silently overwritten.
5. Interpret through `ReplicationOwnerContext`; do not call hypothesis evidence updates. General multi-hop testimony tracking remains unowned: retain bounded declared source references, not a global testimony graph or inferred independent corroboration.

### Required Interfaces and Contracts

Return a new owner ledger and safe receipt counts. A report is never promoted from communicated to own observation. Source and performer claims remain unverified in cognition.

Received measurement `basis` is normalized to `communicated`, even if the sender's document says `own_observation`. Preserve that declared origin separately from the receiver's acquisition basis; the payload cannot self-authorize a firsthand measurement. Compute `claim_digest` from the original canonical wire result before receiver-local normalization; the same delivered claim must not become a conflicting content version merely because its acquisition basis/local handle changed.

### Error Handling and Logging

Malformed or speaker-inconsistent groups drop atomically; unsupported hypothesis/data references remain explicit unknowns. Receipt/report caps yield partial notices without erasing evidence. DEBUG accepted/deduplicated/dropped counts and reasons.

### Tests / Acceptance / Verification

`test_replication_social_exchange.py`: actual A→B delivery, unaddressed C unchanged, spoofed participant, result-before-design, duplicate deliveries, same-root repeated testimony, conflicting same-root reports, and no sender evidence transfer. Run the Phase 2 command with both new files and `tests/unit/test_scientific_hypotheses_communication.py`.

## Task 7: Select replication speech and preserve existing commands

### Intent

Enable communication by agent communities without turning scientific recruitment into compulsory action.

### Implementation Steps

1. Add `select_replication_speech(ledger, observation, command)` returning a detached candidate ledger and one bounded document, never an action. Require an already selected eligible Talk/Tell and derive its actual recipient from that command. Lazily create at most one source-owner collaboration offer per `(owner, recipient, completed source design/trial)`: queue its design, one stable invitation, then its source result. Derive invitation identity from that tuple, not current tick; retries reuse it and do not create a new offer every tick. This is the production invitation-generation transition, not a preseeded request. An optional owner-local group-claim token may connect offers; it asserts no roster or authority.
2. Select dependency-ready messages only. Priority among ready messages: participation/decline; invitation; newly observed result; source design; revised interpretation. If a higher-priority item awaits its complete design, select that prerequisite design first. Sort ties by oldest pending tick/local token. Mark oversize documents `unsendable`, leave dependent invitations/results unresolved and skip that dependency chain so it cannot starve unrelated work. Outbox deduplication is `(recipient, design, kind, invitation/report token)`; checkpoint all statuses and prerequisite links.
   Attachment stages `proposed`. Only finalization of an effective submitted command still containing the complete message commits `attempted` and increments attempt count/tick. A later `ObservedCommunication` with owner as speaker, intended listener, exact `rep_v1` message token and source tick marks `delivery_observed`. This public sender projection exists in `ObservedCommunication`; it proves eligible speech delivery, not recipient adoption/participation. No private event lookup or new acknowledgement is needed. Failed/replaced/aborted speech does not advance attempted state. If no echo appears by the next executed owner observation after an attempted tick, retry the same identity up to three committed attempts; exhaustion marks `delivery_unknown` and blocks only dependent messages. Duplicate actual deliveries remain receiver-idempotent.
3. `attach_replication_message(command, message)` accepts only an already selected `Talk`/`Tell` with an eligible utterance. Preserve verb, recipient, existing relations, and source envelope; append an entire message only if it fits the 32-relation ceiling and no replication message already exists.
4. Preserve existing hypothesis attachment priority, then append replication only if capacity remains. A full relation list leaves the command byte-identical. Do not decorate `Ask`, `Experiment`, other commands, or introduce new speech solely from this helper.
5. Do not use `_select_scientific_hypothesis` for participation/results: its adopted-source exclusion is correct for legacy claims but wrong for a new receiver's independently performed replication. A recipient may share its own new result; that is not automatic retransmission of the sender's evidence.

### Required Interfaces and Contracts

Outbox producers and destinations are fixed:

| Transition | Enqueued document / destination | Idempotence and prerequisite |
| --- | --- | --- |
| Existing Talk/Tell opportunity to a new recipient | Source design → invitation → source result, for an actually completed own trial | One offer per owner/recipient/design/source-trial tuple; same identity on retry |
| Delivered invitation changes pending → accepted | `participate` to verified inviter | One per invitation/owner; no acknowledgement claims about others |
| Owner declines an invitation | `decline` to verified inviter | One per invitation/owner/reason; retain original inviter |
| Unambiguous own replication result arrives | `result` to that attempt's verified inviter | One per origin report/recipient; never enqueue a missing/unobserved result |
| Owner revises appraisal of an invitation-linked report | `interpret` to the verified inviter | One per report/appraisal-revision/recipient; no source trust copied |
| Explicit owner-local request without invitation | Own result retained locally; offer only at an ordinary selected speech opportunity | No invented recipient or implicit group broadcast |

On the receiver's reply path the already delivered invitation proves the inviter has sent that exact design; treat its design prerequisite as satisfied for that inviter only. Otherwise queue the complete design before a result/interpretation for a different actual speech recipient. A queued reply is selected only when the current Talk/Tell's recipient matches; it never retargets speech or initiates it. If there is no opportunity, the reply remains pending with explicit coverage.

Recruitment is opportunity-based piggybacking on ordinary speech; absence of eligible speech is a legal null. Automatic test requests require both a complete delivered design and its delivered invitation, then the recipient's local acceptance; design delivery alone is not an execution request. A pure explicit owner-local `request_replication` may request an already delivered design without an invitation. No guarantee that a community agrees or participates.

### Error Handling and Logging

No room, unavailable design, unsendable body or absent recipient returns the original command and a safe reason. DEBUG proposal counts; INFO successful observed send counts. Never log content or recipient relationship appraisals.

### Tests / Acceptance / Verification

Add deterministic dependency-ready priority, production invitation creation, design-before-invite ordering, oversize-head nonstarvation, sender receipt vs incoming adoption, recipient isolation, missing-echo retry exhaustion, aborted/replaced speech, repeated invitation producing at most one attempt, all-or-nothing cap, legacy `hyp_v1` preservation, adopted-source/new-result speech, Talk/Tell preservation and Ask exclusion tests to `test_replication_communication.py`. Exercise every producer row above without preinstalling an outbox; a completed receiver result must reach the inviter through real eligible speech. The focused Phase 2 command must pass.

## Task 8: Prove social interpretation and transport boundaries

### Intent

Establish an executable community protocol before live runtime wiring.

### Implementation Steps

1. Build owner-safe delivered-observation fixtures for A sharing a design, B/C independently declaring participation, B reporting a result, and C retaining a differing appraisal.
2. Show invitation acknowledgement alone produces no attempt result and that a claimed group of eight cannot manufacture eight sources.
3. Property-test insertion order, repeated delivery, malformed multipart groups, source-root deduplication, and permutation-invariant interpretation over canonical retained evidence.
4. Add AST/boundary assertions to new `tests/architecture/test_replication_boundaries.py`: replication helpers never import private world state, event repositories, simulation, analysis, persistence or API. Public `Experiment` construction is reserved for the Phase 3 action compiler.

### Required Interfaces and Contracts

The social protocol is one-hop delivered testimony and individual intent; it does not claim `multi_hop_testimony_tracking`, change collective-decision topics, or authorize an organization to act.

### Error Handling and Logging

Assert malformed speech logs contain only allowlisted reason/kind/count metadata. Test payload strings and canary credentials absent from captured logs.

### Tests / Acceptance / Verification

Run `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_replication_communication.py tests/unit/test_replication_social_exchange.py tests/architecture/test_replication_boundaries.py -q`. Multiple interpretations must coexist without consensus or a truth field.

## Phase Risks and Mitigations

- Large designs cannot fit the existing envelope: report unsendable explicitly; never partial-design adoption.
- Sending is not delivery: observe actual delivery before resolving send receipts.
- Scripted recruitment: tests may control ordinary speech, but production helpers only decorate already selected Talk/Tell.

## Phase Completion Checklist

- Tasks 5–8 pass focused verification.
- No progress checkboxes outside the index; no changes to world communication limits.
