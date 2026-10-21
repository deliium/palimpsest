# Phase 4: Voluntary use, recording and atomic runtime flow

Plan: [index.md](index.md)
Tasks: 7–8
Depends on: Tasks 1–6

## Objective
Make acquired information available to ordinary cognition and existing selected commands, without forced reading, compulsory record keeping, or multiple actions per tick.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|---|---|---|
| `src/agents/cognition/artifacts.py` | `artifact_inscribe_preferred`, `artifact_inscribe_command` (498) | Selected communicate path can already become an empty `Inscribe`; do not bypass this selection. |
| `src/agents/cognition/deliberation.py` | office/decision/mediation speech decorators (1233–1278), `artifact_inscribe_command` (1295) | Preserve existing decorations and late durable/repository gating. |
| `src/agents/cognition/loop.py` | owner concept preparation (2005–2242), proposal/result construction, `mediation_actions` follow-through | Preparation and command compilation are separate. |
| `src/agents/cognition/models.py` | `ActionPlan` (3520), `CognitiveLoopProposal`, `CognitiveLoopResult` | Planner returns an immutable plan, not an updated ledger. |
| `src/agents/cognition/loop.py` | `_planner_options` (5787), `complete` mediation attempt recording (4573+) | Injected planners get accepted keywords only; attempts are derived from the effective command. |
| `src/simulation/agent_runtime.py` | `_commit_office_concepts`, `_commit_mediation`, deferred finalization near 2497 | Subjective state is committed after the objective attempt is finalized. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/agents/cognition/institutional_memory_actions.py` | create | Consultation, speech decoration and selected inscription content. |
| `src/agents/cognition/deliberation.py` | modify | Pass current owner ledger and invoke bounded decorator at specified location. |
| `src/agents/cognition/loop.py` | modify | Prepare update, decision context and proposal/result propagation. |
| `src/agents/cognition/models.py` | modify | Optional snapshot/proposal/result ledger and optional `ActionPlan.institutional_memory_selection`. |
| `src/agents/cognition/contracts.py` | modify | Perspective field/owner validation. |
| `src/simulation/perception.py` | modify | Carry owner-local ledger into perspective only. |
| `src/simulation/agent_runtime.py` | modify | State, validator, snapshot and deferred commit. |
| `tests/unit/test_institutional_memory_actions.py` | create | Voluntary behavior and bounded decoration. |
| `tests/unit/test_institutional_memory_runtime.py` | create | Pipeline/rollback/mixed owners. |

## Task 7: Expose consultation and compile only selected existing actions

### Intent
Institutional records must be usable, but not an invisible action scheduler or source of permissions.

### Implementation Steps
1. Add `consult_institutional_memory(ledger, *, channel_id, tick, policy=None)` returning a bounded owner-local tuple of active, nonignored entries plus a proposed local `InstitutionalMemoryUse`; no lookup by global role/sender root. Select newest acquisition then stable entry ID, at most one entry/three facts per decision. Unbound and explicitly ignored entries are not selected for institutional consultation.
2. Add `institutional_memory` and `institutional_memory_mode` keyword inputs to `CommandPlanner.plan`, following its existing office/mediation keyword inputs; carry the ledger in the owner snapshot for replacement policies. There is no existing `DecisionContext` class to extend and no new generic decision-context abstraction is required. The default adapter consults only after an existing communicate/inscribe intention wins and can choose no entry. Do not introduce utility bonuses, mandatory communication, read commands, or procedure execution. Consultation does not create facts or privileges.
3. Add `select_institutional_memory_use(ledger, *, owner_id, command, teaching_enabled, tick)` returning `InstitutionalMemorySelection | None`, and `institutional_memory_communicate_utterance(command, *, owner_id, observation, identity, ledger, selection, mode, teaching_enabled, tick)` returning the decorated command. For a winning `Talk`/`Tell` and a consulted entry, the default selector explicitly chooses `teach` when teaching mode is on, otherwise `transmit`; that is a cognition-level informational teaching choice, independent of skill-domain `AdviceAct`/`AdviceDomain`. This selection does not force a communicate intention, create an objective teaching offer, or add skills. Append at most one matching `im_teach`/`im_transmit` frame; a replacement planner may select only consultation or neither. Do not transform an ordinary `Ask` into testimony. Preserve immediate sender, target, utterance text, the entire existing declared envelope and all existing relations. At capacity leave command unchanged; never drop another channel's relation.
4. After existing `artifact_inscribe_command` and before late durable/repository gates, fill only an already selected `Inscribe` whose content is empty with `ArtifactContent(marks=encoded_frame, relations=())`. Preserve selected kind/placement/genre; no newly invented repository, target or genre. Nonempty inscriptions, `Amend`, `AnnotateRecord`, `CopyRecord`, transfers and other commands are not overwritten. Existing copy/access commands naturally preserve/degrade the marks and retain native provenance.
5. Add `ActionPlan.institutional_memory_selection: object | None = None` with exact type/owner validation. The default planner returns the immutable selected entry/kind after decoration; it never commits a ledger. For a selected empty inscription use `kind=record`; ineligible/full-capacity decoration falls back to `kind=consult`, not an emission claim. A replacement owner policy can return `kind=ignore, ignored=True|False` referencing a local entry to make ignore/unignore reachable without an admin API. Default `None` preserves old planners and off-path representations. Proposed selection is not a record/delivery success receipt.
6. Resolve last-stage composition explicitly: existing office/collective/mediation decorators run first, institutional speech appends next if capacity permits; existing artifact selection runs next; institutional empty-inscription fill follows; existing durable/repository gates remain last. The final command count remains exactly one.
7. Introduce `complete_institutional_memory_use(ledger, selection, *, owner_id, invocation_id, final_command, tick)` as a pure completion helper. Validate the selection entry/channel exists in the prepared local ledger. Apply ignore/unignore only here. Record `transmission_attempt`/`teaching_attempt` only if the effective command is `Talk`/`Tell` and its actual frame matches that entry's root/parent and encoded whole-fact prefix; record `recording_attempt` only if final `Inscribe` contains that selected frame. If an intervention replaces or late gate removes the command, record consultation plus `superseded`, never a fabricated emission. Deduplicate by `(invocation_id, entry_id, disposition)`; actual carrier creation or recipient acquisition still requires later evidence.

### Required Interfaces and Contracts
No direct `Give`, `Take`, transfer, debt collection, voting or office authority can be compiled from a fact triple. Procedure facts are informational, not an executable DSL. All action admission remains `WorldEngine` owned.

### Requirement Evidence
Original request — information may be ignored; successors learn/access it. Architecture — independent intention selection and no LLM/social-authority shortcuts.

### Error Handling and Logging
Disabled and ineligible paths return command unchanged. Reasons: `no_known_entry`, `ignored`, `unbound`, `frame_capacity`, `nonempty_inscription`, `no_selected_communicate`. Metadata-only DEBUG; no content-derived IDs in logs.

### Tests
Selected/unchosen communicate paths; ignored and empty ledgers; role-only recognition without knowledge; actual default-selector teach/transmit choice; valid Talk/Tell unchanged native envelope; Ask unchanged; coexistence with mediation/decision relations and full relation capacity; empty/nonempty Inscribe; failed inscription attempt; plan selection metadata; no added action; deterministic ordering. Drive ignore→not retransmitted→unignore through an injected owner planner and real completion, not direct setter-only tests.

### Acceptance Criteria
A successor can consult/retransmit only acquired facts; selecting another action leaves them unused. Existing non-institutional commands and payloads are not overwritten.

### Verification
`uv run --frozen --python 3.12.14 pytest tests/unit/test_institutional_memory_actions.py tests/unit/test_mediation_actions.py --cov=agents.cognition --cov-report=term -q`

## Task 8: Integrate preparation, owner context and deferred commit

### Intent
The ledger follows the existing owner-scoped prepare/finalize lifecycle rather than mutating during observation or policy selection.

### Implementation Steps
1. Add optional `institutional_memory` fields to `Perspective`, `SubjectiveSnapshot`, `CognitiveLoopProposal`, `CognitiveLoopResult`, and runtime state; proposal already retains the typed `ActionPlan` selection. Add exact owner validation at each boundary; do not place state or selection in `Observation` or observer frames.
2. In loop preparation compute new institutional memory after current artifact readings, office/institution concepts and teaching inputs are prepared, before invoking `CommandPlanner.plan`. Consume current owner's inputs only. Return proposed ledger/use changes through existing proposal/result values; no live runtime assignment during prepare.
3. Extend planner inputs for Task 7 through existing `_planner_options(self._planner.plan, ...)`, so old injected planners without new keywords still execute. Pass the same prepared local ledger into consultation/decorators, never another agent's batch. Do not rewrite `ActionPlanner`'s minimal protocol to require new keywords. Preserve `prepare_parallel=False`, selected intention and ordinary command admission.
4. Add `_commit_institutional_memory(value, tick)` in `AgentRuntime`: deterministic mode requires typed matching owner; disabled rejects non-None in incoming results and retains None. Commit from the deferred finalization path beside mediation/offices only after normal lifecycle checks. Export no state from aborted/failed preparations.
5. Ensure cancellation, replayed finalization receipt and repeated observation do not double-add entries/uses. A rejected objective action can still leave legitimate observation-derived learning after the normal finalized attempt, but must not create a fabricated successful write/delivery receipt.
6. Expose `institutional_memory` through owner perspective construction; no analytical source, inspector access or all-owner projection enters the loop.
7. In `CognitiveLoop.complete`, invoke `complete_institutional_memory_use` using `proposal.plan.institutional_memory_selection`, the prepared ledger and the effective `command`, beside existing mediation attempt finalization. Place the returned ledger in `CognitiveLoopResult`; only deferred runtime finalization commits it. Neither `prepare` nor `CommandPlanner.plan` mutates carried state. Validate selection ownership/type/entry before other new state effects; disabled mode rejects injected non-None selections.

### Required Interfaces and Contracts
One observation → one owner proposal → one command → existing finalized subjective commit. `None`/empty/retained partial have distinct meanings. No updates to ordinary scene traces to include artifact content.

### Requirement Evidence
Index C1/C4/C8/C10; architecture objective/subjective commit boundaries and mode-off invariance.

### Error Handling and Logging
Prevalidate type/owner/mode before any runtime writes. Follow existing fail-closed runtime statuses. Count receipt/entry/use totals, not payloads or chain identifiers; no broad exception swallowing.

### Tests
Enabled-empty and enabled-populated run; mixed enabled/disabled owners; foreign state/proposal/selection rejection; staged state invisible before finalize; injected planner with old signature and with explicit new keywords; real ignore/unignore completion; proposed Talk/inscription replaced by Wait before complete; late repository/durable gate fallback; cancellation and abort; failed objective action does not invent delivery/write; repeated finalization; preexisting artifact-memory boundary tests unchanged.

### Acceptance Criteria
Prepared state never leaks across owners or failed preparation; successful continuation carries acquired content without modifying objective observations.

### Verification
`uv run --frozen --python 3.12.14 pytest tests/unit/test_institutional_memory_runtime.py tests/unit/test_artifact_memory_boundary.py tests/unit/test_v2_scientific_invariants.py --cov=agents.cognition --cov=simulation --cov-report=term -q`

## Phase Risks and Mitigations
- Late decorators compete for bounded speech capacity. Mitigation: explicit priority, no dropping earlier content and no mandatory institution frame.
- A recordkeeping attempt can fail. Mitigation: retain attempt separately from observed carrier occurrence.

## Phase Completion Checklist
- Verify Tasks 7–8 and update index only.
- Commit checkpoint 2 follows Tasks 5–8.
