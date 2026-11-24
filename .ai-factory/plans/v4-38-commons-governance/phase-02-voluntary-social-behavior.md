# Phase 2: Voluntary social behavior

Plan: [index.md](index.md)  
Tasks: 3–4  
Depends on: Phase 1

## Objective
Let owners negotiate, revise and sometimes act on a local arrangement while leaving physical draws open to anyone who can execute them.

## Current-Code Evidence

| Path | Symbols | Why it matters |
|---|---|---|
| `src/agents/cognition/social_norms.py` | `norm_response_penalties`, `_apply_withhold` | Norms express owner expectations and social responses, not extraction bans |
| `src/agents/cognition/formal_rules.py` | `apply_formal_rule_update`, `_collect_norms`, `FormalRuleScope` | Existing revisioned formal-rule ledger and RESOURCE scope |
| `src/agents/cognition/institution_concepts.py` | `_observe_norms`, `_record_evidence`, `InstitutionPatternChannel.PROCEDURE_RECURRENCE` | Existing owner-local concepts can retain recurring procedures |
| `src/agents/cognition/loop.py`, `src/agents/cognition/models.py` | `_prepare_formal_rules`, `_prepare_institution_concepts`, `CognitiveLoop.complete`, `CognitiveLoopProposal`, `CognitiveLoopResult` | Evidence preparation vs effective command and owner commit |
| `src/simulation/runner.py`, `src/simulation/agent_runtime.py`, `src/simulation/run_control.py`, `src/simulation/persistence.py` | `_medical_beliefs_loop_kwargs`, `PendingRuntimeFinalization`, `AgentRuntimeCheckpoint`, finalization codec versions | Versioned deferred owner transition, checkpoint and fork precedents |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/agents/cognition/commons_governance_actions.py` | Create | Deterministic optional command/appraisal/speech policy |
| `src/agents/cognition/{commons_governance,commons_governance_communication,social_norms,formal_rules,institution_concepts,deliberation}.py` | Modify | Linked proposals, existing social machinery, and scoped responses |
| `src/agents/cognition/{loop,models}.py` | Modify | Thread typed owner evidence and candidate through prepare/bind/finalize |
| `src/simulation/commons_governance_checkpoint.py` | Create | Canonical owner-state codec and digest |
| `src/simulation/{runner,agent_runtime,run_control,persistence,runner_serialization}.py` | Modify | Composition, pending validators and codecs, restore, detached owner export |
| `tests/unit/test_commons_governance_{behavior,runtime,checkpoint}.py` | Create | Policy, live behavior, off-path and codec tests |

## Task 3: Compose existing social ledgers and voluntary responses

### Intent
Make restriction, criticism, rotation and cooperation possible from local independent evidence, not inevitable or physically enforced.

### Implementation Steps
1. Select proposals from two consecutive visible declines within the last eight ticks (each decline requires a consecutive visibility pair). Compare entity-ID strings of self and visible living co-present peers; only the lexically first observed identity may originate on that tick, and select the first other identity as recipient. This is a local tie-break, not a global leader or knowledge of peer feature gates. Start with a rest proposal; if the same stock has further qualifying declines after that proposal becomes contested or expires, propose a two-person turn with the first locally known peer instead. Consume only one speech opportunity per tick.
2. Keep an outbound proposal head when ordinary delivery to the intended peer is confirmed, not solely because an utterance was planned. An addressed peer with at least one recent visible decline may support a rest proposal or a turn naming itself; a peer with urgent thirst, or a competing active claim that overlaps the proposed arrangement, may oppose instead. Otherwise allow silence. For either proposal, activation requires its proposer plus at least one distinct supporting speaker in the owner's evidence; for a turn, the supporter must be the other named actor. Any current opposition for that proposal or two competing eligible proposals for the stock makes the owner view contested; do not break a tie by making an arrangement binding. Expire 16 ticks from proposal origin, without refresh via replies. Turn preference alternates in two-tick slots, starting with proposer at the first slot from the proposal's originating committed speech tick; derive expected actor from absolute tick and origin, never from inferred missing turns. No later actor is made ineligible by a missing turn.
3. Reuse existing norm machinery: put the commons expectation adapter in `social_norms.py`, gated by the deterministic mode. It evaluates the owner proposal head and returns only typed expectation/response candidates, not a `SHARED_UPKEEP` belief. An eligible contradiction is a genuinely delivered `report_use` tied to an already-supported matching proposal, reporting the speaker's own draw tick when they were expected to rest by that owner's then-current view. Send optional addressed criticism of the report; reuse the existing criticism category and response selection pattern, never retaliation, automatic trust mutation, forced transfer or extraction denial. Silence or absent evidence cannot be sanctioned. Permit an ordinary competing `claim_access` on a speech opportunity when a visible owner has a recent own draw and no supported arrangement; this is a claim, not a grant.
4. Feed an unambiguous supported expectation into the existing formal-rule update as `RESOURCE`-scoped `feed` prohibition with CUSTOM authority, stage NORM and a tagged `commons:<proposal-id>` lineage witness. Apply existing revision/support semantics; absence/contest means no effective commons restriction regardless of retained historical rows. Exclude this tagged lineage from generic action-only formal-rule penalties in `deliberation.py`; the exact stock adapter below is the only behavioral consumer. Do not use a generated rule as independent evidence for the proposal or emit it through generic `fr_v1` speech; the distinct `cgo_v1` testimony path is authoritative for local proposal evidence only.
5. Reuse the existing institution-concept update. Each participant reports to the other; an owner can combine a confirmed outbound self-report and an addressed peer self-report. Require one `report_use` from each named participant for consecutive slots of the same turn proposal, each in the speaker's expected slot and after the owner first recognized support. Missing slots or contradictory claims about one speaker/tick cannot qualify. Deduplicate the `PROCEDURE_RECURRENCE` witness by `(stock, proposal, earlier slot, later slot)` and bind its evidence class to attributed reports, not witnessed compliance. Never count this derived procedure as independent support or legitimacy.
6. At effective-command binding, after higher-priority channels and only if not externally overridden, an existing `Drink` on that exact visible node may become `Wait` when an uncontested owner-accepted rest or out-of-turn preference applies, the owner's normalized thirst need is below 0.65, and the owner did not defer on the prior tick. Rest applies to ticks with the same parity as the proposal origin; turn preference applies only to the two participants. For every non-overridden `Drink` reaching this adapter, record a bounded consideration row with owner/tick/target, matching arrangement if any, opportunity (`wait_expected`, `turn_expected`, `not_applicable`) and choice (`deferred_draw`, `proceeded`). An explicit deferral counts only when the effective result remains `Wait` and owner finalization succeeds. Urgent thirst, no locally supported proposal, own turn, conflicting evidence, or a different node leaves the draw intact. No redirects, fabricated draws, or use of the ecology receipt to choose a command.
7. For speech, decorate only an existing eligible addressed `Talk`/`Tell` with spare capacity and native-origin provenance, or use a remaining ordinary `Wait` (not a deferred draw), at most once per owner per four ticks. Prioritize an unsent or changed stance, criticism, new proposal, access claim, then self-report; send each unchanged claim/report/criticism once per recipient within retention so higher-priority repeats cannot starve reports. Stage exact recipient, canonical frame and send tick for confirmation. Use exact own `ObservedOccurrence.other_entity_id` from an actor-role `drink` occurrence on the visible configured node, never a bystander inference. Report own rest only from finalized explicit deferral. Require `proposal_origin_tick < report_tick < send_tick`. Retain the historical expectation for criticism; do not apply later adoption or opposition retroactively.

### Required Interfaces and Contracts
All helpers consume owner-safe values. Existing stage updates receive only optional typed candidates; with no candidate their outputs are unchanged. The set of `AgentCommand` types and ordinary engine inputs are unchanged. No capture, global policy, mandatory rotation or third-party attribution enters deliberation.

### Requirement Evidence
Original Request — reuse norms, rules and institutions, and allow voluntary response, disagreement and overuse. Existing `test_formal_rule_physical_distinction.py` pins social-vs-physical authority.

### Error Handling and Logging
Unavailable target, full speech frame, stale proposal, missing relationship or disallowed override all fall back without aborting the tick. DEBUG closed reason counts only; no stock quantities, utterances, beliefs or identifiers derived from payloads.

### Tests
Use actual norm, formal rule and institution updates. Verify independent support, opposition/expiry, alternation including missed turns, institution evidence only from repeated matched receipts, criticism grounded in a self-report, urgent/ignored turns, another stock and no generic `feed` penalty, normal admission after violating a private claim, and ordinary syntax/admission for emitted speech.

### Acceptance Criteria
Every social effect is an owner interpretation or voluntary ordinary action; support is neither enforced compliance nor evidence of sustainability.

### Verification
`uv run --frozen --python 3.12.14 pytest tests/unit/test_commons_governance_behavior.py tests/unit/test_formal_rule_physical_distinction.py tests/unit/test_public_good_norms.py -q`

## Task 4: Wire runtime finalization and checkpoint parity

### Intent
Make opt-in owner state reproducible without introducing world replay state or leaking cross-owner information.

### Implementation Steps
1. Follow `_medical_beliefs_loop_kwargs` across founder, admitted-owner and configured rebuild paths. Pass only enabled owners' stock selector to `CognitiveLoop`. In prepare advance a candidate; in `AgentRuntime.bind_effective_command`, ensure `CognitiveLoop.complete().command` actually supplies the submission and pending effective kind. Install one immutable candidate only on successful deferred commit. Confirm speech at the next owner's observation, using Task 2's matched outbound rule, not a proposal or a successful overall tick.
2. Add `commons-governance-state-v1` and `finalization-command-v7`. In `FinalizationCommand` and `finalization_command_to_mapping`/`decode_finalization_command`, use the exact v6 keyset plus mandatory `commons_governance_state`; a v7 `medical_beliefs_state` key is required but nullable (v6's is required and non-null), and science leaves retain their correlated-payload constraints. Choose v7 only if the commons leaf is present. Register it in both `run_control.py` and `persistence.py`; thread it through `PendingRuntimeFinalization.to_finalization_command`, `pending_from_finalization_command`, owner checkpoint preflight and conditional fork digest. Use one shared v7 candidate-integrity builder for bind/write and recover/read, including actual effective command and canonical owner state, without altering v1–v6. Check enabled/gated state consistency before mutation. Do not claim a new durable subjective restart mode.
3. Add a guarded typed `SimulationRunner.export_commons_governance_ledgers()` research method, exposing only detached immutable evidence for finalized owners, with omission status for unavailable owners. Do not expose it to API, observer, stop selectors or live decision paths.

### Required Interfaces and Contracts
`encode_commons_governance_state`, `decode_commons_governance_state` and `commons_governance_state_digest` are canonical and owner-bound. Pending retry cannot duplicate an update. Override suppresses command and speech adaptation, not legitimate observed evidence. Disabled owners, including unqualified entrants, get no mutable state or transformation.

### Requirement Evidence
`.ai-factory/ARCHITECTURE.md` — versioned extension contract; `docs/overexploitation.md` — world replay/legacy pair; Original Request — optional and nonmandatory.

### Error Handling and Logging
Reject unknown versions/keys, owner mismatches and tampered order/digest before apply. Do not publish tentative or partial owner state as finalized. Log reason, codec and count only.

### Tests
Compare v62/v61 committed event/replay fingerprints and live/restored observations for equal submitted commands, not the intentionally different runner-config digest. Trace real prepare → bind → submission → commit → finalization, including an adapted speech or deferral that the world actually receives, and an override draw admitted despite active rest. Cover v7 alone/with medical/with correlated science, v1–v6 byte stability, tamper rejection, and crash/retry without duplicate owner or objective effects. Assert same next-decision evidence after supported fork/restore and unchanged unqualified entrant behavior. Re-run existing V4-37 controlled/replay tests.

### Acceptance Criteria
Owner state survives supported finalization/checkpoint paths, and the objective fold remains byte-equivalent for equal commands.

### Verification
`uv run --frozen --python 3.12.14 pytest tests/unit/test_commons_governance_runtime.py tests/unit/test_commons_governance_checkpoint.py tests/unit/test_overexploitation_feedback.py tests/unit/test_overexploitation_observer.py -q`

## Phase Risks and Mitigations
- Risk: reusing generic rules makes all drinking/eating socially prohibited. Mitigation: exclude tagged commons heads from action-token-only consumers; test an unrelated stock and unrelated feed future.
- Risk: inferred rotation or criticism becomes a governance truth signal. Mitigation: require exact prior local arrangement, independent stance and typed self-report; never consult physical pressure for peer blame.

## Phase Completion Checklist
- Tasks 3–4 meet each acceptance criterion; update only the index after verification.
