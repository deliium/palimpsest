# Phase 1: Activation and evidence

Plan: [index.md](index.md)  
Tasks: 1–2  
Depends on: none

## Objective
Enable an exact opt-in and derive fallible, private commons evidence without changing perception or stock physics.

## Current-Code Evidence

| Path | Symbols | Why it matters |
|---|---|---|
| `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py` | `SimulationRunnerConfig`, `RUNNER_SCHEMA_VERSION_V61` | Exact legacy family and activation pattern |
| `src/simulation/overexploitation_config.py`, `src/simulation/ecological_resources_config.py` | `OverexploitationSpec`, `EcologicalResourcesSpec` | Existing water stock and policy validation |
| `src/world/observations.py`, `src/world/_perception.py` | `ObservedResource`, `_other_entity_for_role`, `_project_communication` | Visibility only; ordinary bystanders do not get exact draw targets |
| `src/agents/cognition/medical_beliefs_communication.py` | `attach_medical_belief_message`, `build_medical_belief_talk` | Strict bounded relations and ordinary speech integration precedent |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/simulation/commons_governance_config.py` | Create | Typed exact v62 leaf and codec |
| `src/simulation/{runner_models,runner_serialization,compatibility,__init__}.py` | Modify | Accepted-set, gate, round trip and public facade |
| `src/agents/cognition/{commons_governance,commons_governance_communication}.py` | Create | Owner evidence fold and strict addressed frames |
| `tests/unit/test_commons_governance_{config,evidence}.py` | Create | Gate, legacy, fold and communication checks |

## Task 1: Add exact opt-in v62 config

### Intent
Allow the experiment to opt in without silently widening any legacy schema.

### Implementation Steps
1. Introduce frozen `CommonsGovernanceSpec` with `policy_id="commons-governance.v1"` and `stock_ids` of 1–8 unique, lexically sorted nonempty entity IDs. Codec accepts only `{"policy_id":"commons-governance.v1","stock_ids":[...]}` and never coerces types or sorts malformed input.
2. Add `RUNNER_SCHEMA_VERSION_V62` as the exact v61 family plus mandatory `commons_governance`. In `runner_serialization.py`, derive `_v62_family_root_keys` from `_v61_family_root_keys`; route v62 through inherited decode/encode and agent-key branches without widening v61. In `runner_models.py`, separate “uses v61 ecology” membership sets from strict v61 root checks; extend `compatibility.py`'s accepted set and named pin. V62 requires the typed overexploitation channel, `formal_rules=True`, and deterministic `social_norm_mode` and `institution_concept_mode` on all configured founders. Match stock IDs against both the ecology registry and typed scenario resources; require WATER and positive renewal. Use owned existing gates, not a new flag.
3. Keep default serialization and feature selection unchanged except explicit v62. In runtime, configure later admitted owners individually: participate only with their own deterministic modes, start empty, and never copy founder state. Do not reject or alter ordinary admission when an entrant lacks those modes.

### Required Interfaces and Contracts
Public simulation exports include the spec and schema constant. Config contains a research stock selector, not an entitlement or policy over resource use; owner cognition only matches the selector against what it can see. Preserve every inherited v61 feature combination. No changes to `WorldEngine`, observation schema or replay selection.

### Requirement Evidence
Original Request requires optional governance; `docs/overexploitation.md` requires exact v61 ecology and unchanged legacy bytes.

### Error Handling and Logging
Closed config validation errors for bad keys, flags, modes, stock selection and wrong schema; DEBUG only schema/reason/count, never config or payloads.

### Tests
Cover v62 canonical round trip alone and with inherited medical, measurement and generational options using combinations already accepted by v61. Assert exact keysets and inherited replay selection. Keep old v61 and v60 documents byte-stable; reject missing/extra/cross-version keys, unmanaged/nonrenewable/nonwater/duplicate/unsorted IDs and missing modes/flags. Reuse the V4-37 water fixture through test helpers only.

### Acceptance Criteria
Exact v62 activates only the intended subjective feature; absolute replay and version pins outside the new config are unchanged.

### Verification
`uv run --frozen --python 3.12.14 pytest tests/unit/test_commons_governance_config.py tests/unit/test_overexploitation_config.py tests/unit/test_compatibility_matrix.py -q`

## Task 2: Fold bounded owner-local commons evidence

### Intent
Represent stock monitoring, distinct support, competing access claims and possible turn arrangements without granting knowledge of hidden events.

### Implementation Steps
1. Add frozen `CommonsLedger`, `CommonsStockEvidence` and immutable `CommonsTransition` rows. Key by owner plus currently visible configured stock ID; read `Observation` and prior owner ledger only. Store last tick and quantity in integer tenths. Two consecutive visible ticks can record `decline` or `nondecline`; a gap, darkness or first sighting starts a new baseline. Never infer cause, peer use, pressure, threshold or renewal from net quantity.
2. Use a one-relation `cgo_v1` frame. Mandatory fields: stock ID, act and topic. `propose/rest` has no extra fields; `propose/turn` adds one peer entity ID and requires the addressed peer to be that participant. `support`/`oppose` (`rest` or `turn`) add exact proposal ID; `claim_access/access` adds no fields and claims only for the speaker. `report_use`/`report_rest` and `criticize` (`rest` or `turn`) add exact proposal ID and the reported action tick. Criticism is addressed only to the reporting actor; it never conveys a third-party observation. Absent fields use a single canonical sentinel and all other combinations fail closed. Hash canonical `(stock, authenticated proposer, topic, optional peer, originating committed speech tick)` into a proposal ID so later otherwise-identical proposals are distinct. Support/opposition must reference an exact prior proposal, sent by the speaker in their own name. Version and encode via the existing utterance relation helper; maximum one relation and 256 encoded characters, reject rather than truncate and require canonical round trip.
3. Fold actual `ObservedCommunication` for ordinary `Talk`/`Tell` only. Separate inbound (`listener_id == self`, speaker is another entity) from confirmed outbound (`speaker_id == self`, listener matches an exact staged frame from the preceding tick). Use event provenance for the committed speech tick and existing native origin checks, not a tick or actor declared inside speech. Require currently visible stock for new inbound evidence. Outbound proves the owner's authored delivery, not peer uptake; a matched outbound support establishes the supporter's own stance, but a proposer cannot support their own proposal. Expire unmatched staged frames. Require strictly earlier committed proposal origin before a reply. Deduplicate delivered occurrence and origin root within attributed speaker and order same-window processing by `(source_tick, event_id)`. Keep the latest valid stance per speaker and proposal, preserving distinct opponents. No relays or third-party draw accusations. Reports remain testimony; self-attributed access claims carry no entitlement.
4. Bound per-owner retention to 8 stock heads, 8 proposals per stock, 8 distinct contributor heads per proposal, 32 ticks of evidence and 128 transition rows. Evict oldest by `(tick, stable id)`, record bounded omissions, and make expired or capped evidence ineligible for new adoption. Do not treat missing evidence as approval or compliance.

### Required Interfaces and Contracts
`advance_commons_evidence(owner_id, prior, observation, stock_ids)` is pure and monotonic by finalized observation tick; an exact repeat is a no-op, older observations fail closed. Retain detached typed codes for `stock_checked`, `stock_declined`, `stance`, `access_claim`, and each reported act, with source tick and owner-scoped provenance. No `WorldEvent`, peer ledger, or analysis import.

### Requirement Evidence
Original Request — monitoring, claims, cooperation; `.ai-factory/ARCHITECTURE.md` — owner evidence and delivery boundaries; `docs/overexploitation.md` — private pressure receipts.

### Error Handling and Logging
Wrong-owner state fails closed. Malformed, oversized, duplicate or out-of-scope frames cannot change evidence; aggregate DEBUG reason/count only, no raw speech, roots or observations.

### Tests
Test first sighting, consecutive decline, gap, two independent stocks, unverified use, competing claims, rejected forgery/duplicate/malformed frames, expiry/eviction and order stability. Use actual `ObservedCommunication`/ordinary relations for both inbound and outbound cases; test matched outbound support, wrong listener, absent delivery and same-tick origin/reply rejection independently.

### Acceptance Criteria
Owner evidence distinguishes stock monitoring from peer testimony and cannot manufacture a withdrawal or an entitlement.

### Verification
`uv run --frozen --python 3.12.14 pytest tests/unit/test_commons_governance_evidence.py tests/unit/test_overexploitation_inference.py -q`

## Phase Risks and Mitigations
- Risk: pressure evidence or globally selected stock IDs leak hidden facts. Mitigation: only present visible stock IDs enter owner state; pressure data is detached exclusively.

## Phase Completion Checklist
- Both tasks meet acceptance criteria; run listed tests with coverage and update the index only after verification.
