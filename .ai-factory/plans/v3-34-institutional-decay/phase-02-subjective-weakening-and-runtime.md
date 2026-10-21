# Phase 2: Subjective weakening and runtime continuity

Plan: [index.md](index.md)
Tasks: 4–6
Depends on: Tasks 1–3

## Objective

Replace coarse all-or-nothing fading only on the enabled path, retain evidence without infinite refresh from stale facts, and commit bounded measurements through normal runtime finalization.

## Current-Code Evidence

| Path | Symbols / sections | Why it matters |
|---|---|---|
| `src/agents/cognition/institution_concepts.py` | `_record_evidence` 779, `_observe_*`, `_decay` 1312, `apply_institution_concept_update` 1388 | Any touched channel currently shields all channels; evidence cap stops strength updates; retained norms/projects can be seen again. |
| `src/agents/cognition/loop.py` | `_prepare_institution_concepts`, preparation sequence 4060–4091 | Concepts precede fresh offices/memory; avoid a dependency cycle by using previous owner snapshot for those inputs. |
| `src/agents/cognition/deliberation.py` | `institution_communicate_utterance` call near 1207 | Existing commands consume recognized concepts; weakening can affect speech without a new command. |
| `src/agents/cognition/models.py` | `SubjectiveSnapshot`, `CognitiveLoopProposal`, `CognitiveLoopResult` | Owner-local staged state transport. |
| `src/agents/cognition/contracts.py` | `Perspective`, `Perspective.to_snapshot` | Explicit intermediate carry fields; adding only the snapshot field loses state. |
| `src/simulation/perception.py` | `build_perspective` parameters and `Perspective(...)` construction | Runtime builds the next invocation through this trusted owner-safe assembler. |
| `src/simulation/agent_runtime.py` | `_commit_institution_concepts`, `_commit_institutional_memory`, checkpoint preflight/restore/export | Deferred subjective commit and owner validation pattern. |
| `src/simulation/run_control.py` | `AgentRuntimeCheckpoint` | Runtime continuation, not universal durable subjective restart. |
| `src/simulation/runner.py` | rehydration preflight, `export_institution_concept_ledgers`, result assembly | Export and all-owner checkpoint validation before mutation. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/agents/cognition/institution_concepts.py` | modify | Isolated signal-aware kernel and enabled-only per-channel attrition seam. |
| `src/agents/cognition/institutional_decay.py` | modify | Evidence receipts, dimension measurement, update and bounded sample retention. |
| `src/agents/cognition/loop.py` | modify | Prepare new paired update using prior offices/memory; forward sidecar through completion. |
| `src/agents/cognition/models.py` | modify | Owner-validated snapshot/proposal/result field. |
| `src/agents/cognition/contracts.py` | modify | Owner-validated `Perspective.institutional_decay` and `to_snapshot` forwarding. |
| `src/simulation/perception.py` | modify | Optional decay input and trusted perspective forwarding. |
| `src/simulation/agent_runtime.py` | modify | State carry, deferred commit, checkpoint preflight/restore/export. |
| `src/simulation/run_control.py` | modify | Optional runtime checkpoint field and validation. |
| `src/simulation/runner.py` | modify | Atomic checkpoint preflight and detached exports. |
| `src/simulation/runner_models.py` | modify | Ordered optional result ledger export. |
| `src/simulation/new_agent_initialization.py` | modify | Explicit decay-state copy denial; preserve existing empty profiles. |
| `tests/unit/test_institutional_decay_updates.py` | create | Evidence freshness, independent channel attrition and recovery. |
| `tests/unit/test_institutional_decay_runtime.py` | create | Loop, behavior, measurements and failure isolation. |
| `tests/unit/test_institutional_decay_checkpoints.py` | create | Checkpoint continuation, preflight and cap determinism. |

## Task 4: Implement fresh-evidence channel attrition

### Intent

Persistent support must be renewed by evidence, not by repeatedly reading the same retained fact. Weakening changes a private concept and its ordinary downstream use; it does not destroy an objective institution.

### Implementation Steps

1. Extract the existing institution-concept update pipeline into a same-package private kernel. Keep the public legacy `apply_institution_concept_update` signature, return type, locked policy and execution path unchanged. The new `apply_institution_decay_update` invokes the kernel with an explicit signal/receipt context. Avoid import cycles through TYPE_CHECKING/local imports; do not import private world modules.
2. In the enabled path only, capture source metadata before the 32-entry history cap. Separate history retention from fresh strength admission: a full evidence history must not prevent real renewed practice or freeze freshness forever. Legacy cap behavior stays unchanged. Duplicate inputs may retain notices but do not increase strength, freshness or participation.
3. Build native-source adapters using the binding/dedup table below before mutating enabled drafts. Canonical keys use opaque event provenance where present and native projection fields otherwise. Never use observation ordinal or current observation tick to make a retained old fact new. Where a native source lacks revision identity, hash its semantic evidence fields excluding access/current tick; an identical source is counted once. Separate the canonical **action key** (one participation occurrence) from `(pattern, channel, action_key)` (per-channel belief credit), so one action may legitimately support role and procedure without counting as two participants/actions. For native structural components, hash versioned action-kind tokens and visible native target/context tokens separately; procedure patterns retain their observed ordered kind sequence plus its component set. Explicit `success=False` or a projected `accepted=False` never counts as accepted participation. Actor identity belongs in the participant evidence, not as the only structural identity. No new observation fields are added. Missing/redacted targets give incomplete structure, not invented anchors.
4. Receipt admission is per pattern/channel/source. Communicated claims refresh only the communicated channel they explicitly express, not observed participation or independent support. Same-root retellings do not become multiple supporters. Recalled evidence can inform a belief once but never counts as current procedure performance or a fresh succession. When receipts are pruned, sources with source tick at/before the retained receipt high-water boundary are ineligible for fresh positive credit and coverage is partial.
5. Enabled channel update: start from previous strength; admit each fresh positive using its existing channel delta and unit clamp; subtract `0.04` only from channels receiving no fresh credit in this executed update; quantize at each update. Do not also run the legacy draft-wide `_decay`. An unrelated refreshed channel must not shield the rest. New patterns start at zero. Use existing `_freeze` thresholds to derive candidate/recognized/fading/retired states; do not alter its enum/schema.
6. Replace `_social_draft`'s arbitrary lowest-group choice on the enabled path with the explicit cold-start binding rules below. A fresh local norm/convention evidence source may establish its first association with a structural pattern through an exact shared native occurrence key; a previously established association is not required for that first match. Uniquely bound evidence can refresh only its relevant expectation/legitimacy channel. Otherwise keep the social signal unbound/partial; the off-path behavior is unchanged. Do not count one source as multiple independent supporters or lower `_freeze`'s three-channel recognition requirement to conceal an unreachable path.
7. Repeated same-tick calls with identical inputs return equivalent values and no second sample/loss; conflicting same-tick inputs and decreasing ticks fail closed. For skipped ticks, apply one cognitive update, not synthetic elapsed-tick loss; retain the gap in coverage. Rehearsal, surveillance or observer reads do not advance state.

### Enabled-Path Source Binding and Cold-Start Reachability

| Native input | Binding and freshness contract | Exclusions |
|---|---|---|
| `ObservedOccurrence` with resolved actor and supported function kind | Use `provenance.source_event_id`/`source_tick`; retain observed location/day phase and an explicitly projected target. Bucket compatible native occurrences by `(world, location, day_phase, target kind, target ID)`. Within one bucket, the ordered supported-function sequence defines the structural signature. Derive the enabled group using existing `_group_digest` over versioned canonical bucket/signature material, **without actor identity**. Credit role evidence and performed procedure evidence to this same enabled group, rather than separate legacy role/sequence groups. | Do not merge different targets, owners, contexts or unknown target associations. Targetless observations remain isolated/unbound when no unique native scope can be established. Preserve the legacy grouping path when decay is off. |
| Project contribution projection | Native key contains `project_id`, resolved actor and contribution `tick`; retain `accepted`, `labor_delta` and `item_id` as validation/disambiguation data. Match an occurrence only when native actor/source tick/project and outcome agree uniquely; alias both views to one action key and one enabled binding. | Projection has no event ID: never claim equality by ordinal or label. If matching is ambiguous, keep occurrence evidence as the primary action view, exclude the ambiguous projection from additional participation credit, and report the exclusion. Projection-only evidence can inform retained belief once but is not current performed activity when its source is older than the observation's current/prior tick. |
| Public-good native target/outcome | Explicit allowlist: read `public_facts["project_id"]` as a validated `EntityId` string and `public_facts["accepted"]` as an exact boolean for supported public-good kinds. These are existing public perception fields, not arbitrary content parsing. `public_good_maintained` needs `accepted is True`. | No generic scan of `public_facts`, name parsing, replay lookup, or new observation fields. Unknown/redacted target/outcome is excluded or partial, never invented. |
| Local norm/convention evidence | First try exact native lineage equality: `NormEvidenceItem.lineage_ref` equals a currently available occurrence's event-ID token, with compatible action semantics and the same owner. For a cold-start fixture, fresh conforming `NormPattern.SHARED_UPKEEP` evidence from an accepted `public_good_maintained` occurrence supplies `SOCIAL_EXPECTATION` to that occurrence's role/procedure binding. Later evidence may reuse a recorded association, but only new evidence keys refresh it. Convention binding requires exact source identity plus compatible typed `ConventionContent`; context coincidence alone does not establish an association. | Global norm presence, participant-count similarity, prior `last_tick`, a label, or an arbitrary minimum group key cannot create a binding. Shared evidence across channels is not independent corroboration. |
| Prior local office or acquired memory | Associate only through retained office ID or a unique evidenced function/context/structural binding. Record source revision/entry/evidence IDs and their original interval. | No office/knowledge association is required to bootstrap the concepts+decay+norm route. Optional disabled sources remain disabled; unbound sources do not create global identities. |
| Delivered speech / recall | Use actual delivery/source IDs for a fresh belief input, but preserve testimony versus performed-action distinctions. An incoming opaque sender group does not identify a local structural pattern without the owner's separate binding evidence. | Do not fabricate a `MemoryTrace` source from `_observe_memories`' synthetic `remembered-...` string; if no actual owner memory source exists, give no fresh recall credit. |

The enabled grouping is a versioned policy change, not a rewrite of legacy v49–v53 payloads. Retained legacy groups without an exact native association remain unbound; do not silently rename or merge restored concepts. Normal v54 experiments begin with empty state.

Required cold-start proof: start with empty concept/decay/norm ledgers; drive a normal owner loop through repeated accepted maintenance of one native public good in a stable visible context. Prepared norm evidence and each occurrence share native event provenance, so role, procedure and expectation strengths accumulate in one group until existing `_freeze` recognizes it. Then stop maintenance while keeping covered observations, verify weakening and loss of communication eligibility, and renew maintenance to recover recognition. Never preconstruct a `RECOGNIZED` concept, manually boost strengths, or require the ordinary BK experiment to produce this controlled demonstration.

### Required Interfaces and Contracts

The new update returns both an ordinary `InstitutionConceptLedger` with adjusted strengths/status and its sidecar. The six strengths remain subjective; no institutional-memory entries, office claims, memories, norms, relationships or world state are rewritten. Pattern tombstones preserve recoverability; fresh legitimate evidence can strengthen a retired pattern again.

### Requirement Evidence

User request — loss of support/participation and non-scripted weakening; existing `_decay`/`_record_evidence` — behavioral seam; architecture — unchanged default-off path and testimony boundaries.

### Error Handling and Logging

Reject foreign carry, unsupported signal types, conflicting duplicate keys and time reversal. Log DEBUG fresh/duplicate/unbound counts and per-channel refreshed counts; WARN pruning/gaps using counts and reason codes only. No source keys or content in logs.

### Tests

`test_institutional_decay_updates.py`: one channel refreshed while five decline; stale norm/project/repository repetition; fresh activity after evidence cap; real occurrence/project-projection aliasing and ambiguous-match exclusion; one action credited to two channels but one participation count; shared-root retellings; actual recall versus synthetic `_observe_memories` refresh; native multi-kind procedure component extraction and failed-action exclusion; redacted targets/unknown binding; cold-start shared-upkeep recognition, weakening and renewed recognition; same-tick idempotence/conflict; skipped ticks; all-zero retirement; receipt/sample caps and no accidental resurrection from evicted receipts. Golden comparison proves the off-path kernel remains identical to legacy concept updates.

### Acceptance Criteria

Fresh evidence renews only relevant channels. Stale evidence cannot indefinitely sustain recognition. Retired concepts retain lineage, and recovery remains possible without a collapse/rebirth event.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_institutional_decay_updates.py tests/unit/test_institution_concepts_loop.py tests/unit/test_institution_concepts_contracts.py -q`

Expected: enabled attrition tests and unchanged legacy tests pass.

## Task 5: Measure five dimensions and integrate ordinary cognition

### Intent

Expose interpretable evidence-based continuity, and let weakened concepts influence existing cognition without a collapse action or forced withdrawal.

### Implementation Steps

1. In `_prepare_institution_concepts`, branch only on deterministic decay. Feed the new update current owner observation/identity and existing prepared norm/convention/group/possession inputs, plus **previous snapshot** offices/institutional memory. Do not reorder the existing concepts → offices → memory sequence. The one-update lag for office/knowledge assessment is explicit in sample source intervals.
2. Return/carry the paired state internally. Add `institutional_decay: object | None = None` to **`Perspective` in `agents/cognition/contracts.py`**, `SubjectiveSnapshot`, proposal and result, with owner/type validation. Extend `simulation.perception.build_perspective`'s optional parameter and its `Perspective(...)` forwarding, `Perspective.to_snapshot()`, and the `AgentRuntime` call near line 2034 to forward `_institutional_decay`. Introduce the runtime slot initialized to `None` in this task so forwarding is safe; Task 6 adds the commit/checkpoint path that populates it. Forward through prepare and completion constructors as well. Disabled mode leaves every boundary `None` and calls legacy concept preparation unchanged. Do not modify `simulation/models.py`: the actual `Perspective` lives in cognition contracts.
3. For each update, record the binding's **observed opportunity cohort** from resolved currently visible bodies at its evidenced native scope, including the owner only when its current self observation belongs to that scope. This is not a world eligibility/capability/rights registry or an enumeration of all population. Retain actor IDs needed for deduplication, plus native source keys and availability; compute no four-tick ratios in cognition.
4. Record fresh independently resolved supporter/root pairs from uniquely bound office or local norm evidence, and accepted participant/action keys from the native adapters. Self-endorsement, an alleged unresolved supporter, and same-root retellings do not add independent support. A private legitimacy strength is not a substitute support count. One canonical accepted action contributes at most once to participation per pattern/update, regardless of its multiple observation views or belief channels. Mark whether the native ordered procedure actually performed in this update's evidence, rather than counting repeated access to an old projection.
5. For succession, record eligible locally evidenced loss/relinquishment/abandonment transition IDs and completed locally supported resumption IDs, with their actual source ticks and supporting roots. No transition is `not_applicable`, disabled office mode is `disabled`, unresolved or competing successors are partial/unknown. Absence alone is not vacancy. The same retained transition cannot be recounted every tick.
6. For knowledge, record locally known entry IDs before each eligible bound role/procedure transition and the IDs still active/nonignored afterward; keep transition/source IDs and original assessment interval. Disabled memory is disabled; no opportunity is not applicable; pruned or ambiguous binding is partial. This measures one owner's retained knowledge, not successor acquisition. Cross-owner handoff is measured retrospectively from actual delivery/reading provenance in Phase 3. Lost carriers never delete acquired entries.
7. Record per-pattern scope coverage only when its native target/context is currently observable. Known patterns receive an explicit covered-zero-activity sample when the owner observes the relevant scope but no fresh associated practice, rather than disappearing from the sample stream. Hidden scope, unsupported binding or a skipped update is unknown, not zero. Preserve `observation_tick` and `source_tick` separately: measurement windows below use observation/update ticks, describing **observed evidence renewal**, while native action timing remains available in source intervals. Only current/prior-tick native actions count as fresh performed activity; first access to older retained facts may inform belief but not present participation.
8. Pass adjusted concepts to existing office inference and planner, so normal `institution_communicate_utterance` can stop selecting no-longer-recognized concepts and later resume selecting recovered ones. No change to action types, planner reward structure, office support/vacancy rules, emission precedence, or speech schema. Do not force a `Wait`, `Give`, resignation, endorsement or resource transfer.

### Single-Window Measurement Contract

Task 7 is the only four-tick aggregation layer. For a complete window `W`, let `E_t` be the resolved observed cohort in update `t`, and `E(W)` its intersection across the four covered updates. This explicitly measures a stable **observed cohort**, not total social support or population participation. Empty `E(W)` gives an unknown actor-ratio denominator, never division by zero or an observed zero. Preserve excluded/transient-actor counts separately.

- Support: distinct independently evidenced supporters received in `W`, restricted to `E(W)`, divided by `len(E(W))`. Deduplicate roots before attributing independent supporters; unsupported/disabled source channels do not yield false observed zeros.
- Participation: distinct actors with fresh accepted action keys received in `W`, restricted to `E(W)`, divided by `len(E(W))`. Count a person once even if they acted repeatedly or one action populated several belief channels.
- Procedure repetition: covered updates in `W` with fresh associated native procedure performance, divided by covered eligible updates (four for a complete window). Multiple occurrences in one update do not increase that numerator beyond one.
- Succession: distinct eligible transition IDs in the window assessment, with distinct completed IDs as numerator; no transition is not applicable. Retained prior office state is assessed with its original one-update-lag interval, not stamped into each new tick as a new transition.
- Knowledge: sum of retained-before-entry intersections across distinct eligible transition assessments, divided by the sum of their before-entry counts; deduplicate `(transition_id, entry_id)` pairs. An empty before-entry population is not applicable, not perfect continuity. This remains owner-local.

For adjacent-window decline comparisons, recompute actor ratios on the **intersection of both windows' observed cohorts**, using retained raw sets, rather than comparing ratios over different people. No common cohort means incomparable/unknown decline. Keep population/cohort change as a separate descriptive panel. Never average ratios, aggregate already-windowed samples, or apply a second rolling window.

### Required Interfaces and Contracts

Behavioral effect is narrower than analytical lifecycle: private confidence and recognized-concept use change, while collapse/transform/split classifications exist only in analysis. Optional office/memory dimensions must remain distinguishable from observed zero. Freshly prepared office/memory results are not fed back into concept preparation in the same tick.

### Requirement Evidence

Five user-required tracking dimensions; `docs/institutional-memory.md` learning/knowledge constraints; office absence rule; architecture non-authoritative commands and subjective analysis boundary.

### Error Handling and Logging

Invalid foreign source ledger fails closed; valid absent optional inputs return unknown/disabled measurements. DEBUG counts/availability codes; no actor lists, claims, context hashes or sample payload dumps. Preserve the runtime's existing failure semantics.

### Tests

`test_institutional_decay_runtime.py`: trusted `build_perspective` → `Perspective.to_snapshot` forwarding with a real owner ledger from the public update, foreign-owner rejection at both boundaries, and disabled `None` throughout. Also cover direct-loop concepts-only, office evidence, memory-enabled, all enabled, mixed owners; no-transition versus failure; duplicate roots; empty/changing cohorts; unseen actors; covered zeros versus hidden scope; missing/pruned records; retained knowledge after carrier loss; conflicting succession; one-update lag; cold-start recognition and ordinary `Talk` eligibility loss/recovery; off-path command equality. Check actual final command precedence rather than a superseded utterance. **Task 6**, after commit exists, adds the mandatory actual-runtime two-tick carry test; do not make Task 5 depend on unimplemented Task 6 behavior.

### Acceptance Criteria

All five dimensions are exported with honest availability. Enabled attrition changes actual recognized-concept use through existing commands; it does not create authority or automatically collapse social activity.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_institutional_decay_runtime.py tests/unit/test_offices_succession.py tests/unit/test_institutional_memory_invariants.py -q`

Expected: ordinary cognition behavior is demonstrated and existing succession/knowledge invariants remain green.

## Task 6: Commit, checkpoint and export bounded owner histories

### Intent

Temporal analysis needs actual intermediate samples, not an invented history reconstructed from a final high/low snapshot. Continuation must not apply attrition twice.

### Implementation Steps

1. Add runtime carry and `_commit_institutional_decay` following institutional-memory commit semantics. Validate the complete adjusted-concept/sidecar pair, owner/type and mode **before either of these two fields is committed**; a malformed sidecar must not leave newly committed concepts behind. Enabled `None` results preserve carried state, disabled owners reject nonempty restored state. Commit only through the existing deferred finalization path, with adjusted concepts and sidecar from the same proposal.
2. Add optional decay state to `AgentRuntimeCheckpoint`; include all raw samples, bindings, receipts, per-pattern sample pruning boundaries, separate receipt boundary, last update tick and retained absolute identity/activity witnesses in runtime export/restore. Validate that paired concept groups match sidecar bindings before mutating live runtime state. Restore carry through the complete runtime → perspective → snapshot chain, not only a checkpoint comparison map. Preserve existing staged failure/receipt semantics; do not introduce a second transaction system.
3. Extend runner rehydration preflight to validate every owner's new state, mode and paired concepts before engine/runtime mutation. A malformed last owner must leave earlier owners and engine cursor untouched. Update initial subjective-copy deny lists to reject decay state. All existing newborn profiles remain decay-disabled and content-empty; no profile clones a predecessor's history.
4. Add `SimulationRunner.export_institutional_decay_ledgers()` and `SimulationRunnerResult.institutional_decay_ledgers`, ordered and owner/type validated like institutional memory. Export retained state for terminated owners as well as live owners when available from registered runtimes; report lifecycle termination separately rather than appending fake postmortem observations.
5. Keep histories bounded by Task 1 caps; do not synthesize samples for skipped/dead/unregistered owners. Default-off exports are empty and must not change the existing serialized result document wire keyset. These exports are in-process detached research inputs, following current ledger exports, not a new durable subjective table or restart promise.
6. Retain identity witnesses when their full samples are evicted. A pruned predecessor reference is an explicit stub, not evidence for its former stability, collapse or knowledge continuity. Once a later four-tick interval has complete raw samples again, old unrelated pruning counters do not censor that interval forever. If the prior stable interval itself is unavailable, current collapse remains unconfirmed/censored; do not manufacture a retained analytical stability latch in live cognition. Whole-run lifecycle graphs are not promised beyond retained evidence.

### Required Interfaces and Contracts

Checkpoint continuation of the owner-local ledger is supported. General API/durable recovery of all subjective stores is not added. Objective replay remains event-only and unchanged. Result serialization must not silently widen an existing result schema for an in-process-only field.

### Requirement Evidence

Architecture — subjective checkpoints outside objective event fold; existing `agent_runtime.py`/`runner.py` preflight pattern; user lineage requirement needs retained temporal evidence.

### Error Handling and Logging

Fail preflight on foreign owners, disabled state, inconsistent pair, future samples, duplicate samples or unsupported policy. WARN history truncation with counts. Never dump ledger/checkpoint payloads.

### Tests

Add the mandatory test to `test_institutional_decay_runtime.py`: actual `AgentRuntime` tick-one commit → `build_perspective` → `Perspective.to_snapshot` → tick-two loop input, proving carried receipt/strength/sample continuity without injecting a hand-built snapshot. `test_institutional_decay_checkpoints.py`: real export/apply roundtrip followed by another actual runtime tick versus uninterrupted continuation, including raw samples/future commands/identity witnesses; restore at same tick; failed prepare/finalization does not double-append; mixed-owner all-or-nothing preflight; disabled/foreign/mismatched pairs; default newborn profile/no state copy; terminated owner export; over-256-sample pruning with 16 patterns (only 16 ticks retained); factual pattern/recovery witnesses unchanged after eviction; per-pattern pruning boundaries and exported immutable detachment; legacy result-document keyset unchanged. Analytical node-ID/stub/window usability assertions belong to Tasks 7–9, after those functions exist, not to Task 6's pre-analysis checkpoint tests.

### Acceptance Criteria

Continuation and uninterrupted execution produce equal future behavior and retained sample histories. Pruning/termination is explicit, never represented as collapse.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_institutional_decay_checkpoints.py tests/unit/test_institutional_memory_checkpoints.py tests/unit/test_institutional_decay_runtime.py -q`

Expected: checkpoint equality, preflight safety and export cases pass.

## Phase Risks and Mitigations

- Legacy evidence often embeds current tick/ordinal: build native receipt keys at extraction, not from opaque display lineage strings.
- Previous snapshots create an intentional one-update measurement lag: source intervals and tests make it visible.
- Loss of sight is not observed nonparticipation: carry coverage and require covered windows for later collapse classification.
- Evidence/sample caps can mimic social loss: preserve pruning counters and censor classifications across incomplete intervals.

## Phase Completion Checklist

- Tasks 4–6 pass their acceptance criteria and focused verification.
- Update task progress only in `index.md` after verification.
